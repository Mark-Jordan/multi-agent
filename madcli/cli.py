from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

from .config import (
    DEFAULT_CONFIG_PATH,
    app_config_to_dict,
    app_config_from_dict,
    default_config,
    load_config,
    save_config,
    validate_config,
)
from .crewai_adapter import CrewAIUnavailableError, run_crewai_workflow
from .crewai_flow_backend import run_flow_workflow
from .hitl import approve_task, reject_task
from .run_store import RunStore
from .orchestrator import WorkflowOrchestrator
from .planner import parse_planned_tasks, plan_tasks_with_agent
from .task_runner import AgentTaskRequest, run_agent_task
from .workflow_store import PlannedTask, WorkflowStore
from .workflow_templates import (
    list_templates,
    load_template,
    render_template,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="madcli",
        description="Run coding tasks through OpenCode, Codex, or Claude Code.",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to madcli JSON config.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Write a default config file.")
    init_parser.add_argument("--force", action="store_true", help="Overwrite config.")

    subparsers.add_parser("doctor", help="Validate config and runtime commands.")

    run_parser = subparsers.add_parser("run", help="Create a run and dispatch a task.")
    run_parser.add_argument("task", help="Task to send to the configured coding agent.")
    run_parser.add_argument(
        "--agent",
        default="strategy_engineer",
        help="Agent key from config.",
    )
    run_parser.add_argument(
        "--workdir",
        default=None,
        help="Repository directory for the coding runtime.",
    )
    run_parser.add_argument(
        "--context",
        default=None,
        help="Extra context text to write into the run context package.",
    )
    run_parser.add_argument(
        "--context-file",
        action="append",
        default=[],
        help="Markdown context file to copy into the run context package. Can be repeated.",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the runtime command without executing it.",
    )
    run_parser.add_argument(
        "--credential",
        default=None,
        help="Credential profile name for the selected runtime. Defaults to trying profiles in config order.",
    )
    run_parser.add_argument(
        "--prompt-mode",
        choices=["context", "task"],
        default="context",
        help="Use context handoff prompt or send the task text directly to the runtime.",
    )

    status_parser = subparsers.add_parser("status", help="List recent runs.")
    status_parser.add_argument("--limit", type=int, default=20)

    logs_parser = subparsers.add_parser("logs", help="Print run events and output.")
    logs_parser.add_argument("run_id")

    credentials_parser = subparsers.add_parser(
        "credentials", help="Manage runtime credential profiles."
    )
    credential_subparsers = credentials_parser.add_subparsers(
        dest="credentials_command", required=True
    )

    credentials_list = credential_subparsers.add_parser(
        "list", help="List credential profiles."
    )
    credentials_list.add_argument("--runtime", default=None)

    credentials_add = credential_subparsers.add_parser(
        "add", help="Add or replace a credential profile."
    )
    credentials_add.add_argument("--runtime", required=True)
    credentials_add.add_argument("--name", required=True)
    credentials_add.add_argument("--base-url", default=None)
    key_group = credentials_add.add_mutually_exclusive_group(required=True)
    key_group.add_argument("--api-key", default=None)
    key_group.add_argument("--api-key-env", default=None)

    credentials_remove = credential_subparsers.add_parser(
        "remove", help="Remove a credential profile."
    )
    credentials_remove.add_argument("--runtime", required=True)
    credentials_remove.add_argument("--name", required=True)

    workflow_parser = subparsers.add_parser(
        "workflow", help="Run autonomous multi-agent workflows."
    )
    workflow_subparsers = workflow_parser.add_subparsers(
        dest="workflow_command", required=True
    )
    workflow_run = workflow_subparsers.add_parser(
        "run", help="Run a planned autonomous workflow."
    )
    workflow_run.add_argument("goal", help="Workflow goal.")
    workflow_run.add_argument(
        "--plan-file",
        help="JSON plan file containing a tasks array.",
    )
    workflow_run.add_argument(
        "--planner-agent",
        default=None,
        help="Agent key to use as commander/planner when --plan-file is not provided.",
    )
    workflow_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Create workflow and run artifacts without invoking runtimes.",
    )
    workflow_run.add_argument(
        "--template",
        default=None,
        help="Workflow template name. Use 'workflow templates' to list available templates.",
    )
    workflow_run.add_argument(
        "--var",
        dest="variables",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Template variable in KEY=VALUE format. Can be repeated. Example: --var engineer_agent=strategy_engineer",
    )
    workflow_run.add_argument(
        "--templates-dir",
        default=None,
        help="Additional directory to search for workflow templates.",
    )
    workflow_run.add_argument(
        "--backend",
        choices=["madcli", "crewai", "crewai-flow"],
        default="madcli",
        help="Workflow backend: madcli (deterministic), crewai (hierarchical), crewai-flow (state machine).",
    )
    workflow_run.add_argument(
        "--manager-agent",
        default=None,
        help="Agent key to use as CrewAI manager/commander. Defaults to --planner-agent or codex_reviewer.",
    )
    workflow_status = workflow_subparsers.add_parser(
        "status", help="List workflows or show one workflow."
    )
    workflow_status.add_argument("workflow_id", nargs="?")
    workflow_logs = workflow_subparsers.add_parser(
        "logs", help="Print workflow event logs."
    )
    workflow_logs.add_argument("workflow_id")

    workflow_approve = workflow_subparsers.add_parser(
        "approve", help="Approve a task awaiting human approval."
    )
    workflow_approve.add_argument("workflow_id")
    workflow_approve.add_argument("task_id")
    workflow_approve.add_argument("--comment", default=None)

    workflow_reject = workflow_subparsers.add_parser(
        "reject", help="Reject a task awaiting human approval."
    )
    workflow_reject.add_argument("workflow_id")
    workflow_reject.add_argument("task_id")
    workflow_reject.add_argument("--reason", default=None)

    workflow_resume = workflow_subparsers.add_parser(
        "resume", help="Resume a paused workflow from its last checkpoint."
    )
    workflow_resume.add_argument("workflow_id")

    workflow_subparsers.add_parser(
        "templates", help="List available workflow templates."
    )

    return parser


def cmd_init(args: argparse.Namespace) -> int:
    path = Path(args.config)
    if path.exists() and not args.force:
        print(f"config already exists: {path}")
        print("use --force to overwrite")
        return 1
    save_config(default_config(), path)
    print(f"wrote {path}")
    return 0


def _load_config_or_print(path: Path):
    try:
        return load_config(path)
    except FileNotFoundError:
        print(f"config not found: {path}", file=sys.stderr)
        print("run: python -m madcli init", file=sys.stderr)
        return None
    except ValueError as exc:
        print(f"invalid config: {exc}", file=sys.stderr)
        return None


def cmd_doctor(args: argparse.Namespace) -> int:
    config = _load_config_or_print(Path(args.config))
    if config is None:
        return 1
    errors = validate_config(config)
    if errors:
        print("config: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("config: OK")
    print(f"runs_dir: {config.runs_dir}")
    print(f"default_workdir: {config.default_workdir}")
    for name, runtime in config.runtimes.items():
        status = "found" if shutil.which(runtime.command) else "missing"
        print(f"runtime {name}: {runtime.command} ({status})")
        if runtime.credentials:
            for profile in runtime.credentials:
                key_source = (
                    f"env:{profile.api_key_env}"
                    if profile.api_key_env
                    else "inline-api-key"
                )
                base_url = profile.base_url or "runtime default"
                print(
                    f"  credential {profile.name}: base_url={base_url}, key={key_source}"
                )
        else:
            print("  credentials: none")
    print(f"agents: {', '.join(sorted(config.agents))}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config = _load_config_or_print(Path(args.config))
    if config is None:
        return 1
    if args.agent not in config.agents:
        print(f"unknown agent: {args.agent}", file=sys.stderr)
        print(f"available agents: {', '.join(sorted(config.agents))}", file=sys.stderr)
        return 1
    try:
        result = run_agent_task(
            AgentTaskRequest(
                config=config,
                task=args.task,
                agent_name=args.agent,
                workdir=Path(args.workdir) if args.workdir else None,
                extra_context=args.context,
                context_files=[Path(path) for path in args.context_file],
                dry_run=args.dry_run,
                credential_name=args.credential,
                prompt_mode=args.prompt_mode,
            )
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"run_id: {result.run_id}")
    print(f"status: {result.status}")
    print(f"runtime: {result.runtime}")
    print(f"agent: {result.agent_name}")
    if result.credential_name:
        print(f"credential: {result.credential_name}")
    print(f"run_dir: {result.run_dir}")
    if args.dry_run:
        print("command:")
        print(json.dumps(result.command, indent=2, ensure_ascii=False))
    elif not result.ok:
        print(result.stderr, file=sys.stderr)
        return 1
    return 0


def _workflow_store_for(config) -> WorkflowStore:
    return WorkflowStore(config.runs_dir.parent / "workflows")


def _planned_tasks_from_file(path: Path, config=None) -> list[PlannedTask]:
    return parse_planned_tasks(path.read_text(encoding="utf-8"), config=config)


def _parse_variables(var_args: list[str]) -> dict[str, str]:
    variables: dict[str, str] = {}
    for arg in var_args:
        if "=" not in arg:
            raise ValueError(f"variable must be in KEY=VALUE format: {arg}")
        key, _, value = arg.partition("=")
        variables[key.strip()] = value.strip()
    return variables


def _resolve_tasks(
    args: argparse.Namespace, config: AppConfig
) -> list[PlannedTask]:
    """Resolve tasks from --template, --plan-file, or --planner-agent."""
    if args.template:
        variables = _parse_variables(args.variables)
        templates_dir = Path(args.templates_dir) if args.templates_dir else None
        template_data = load_template(args.template, templates_dir=templates_dir)
        tasks = render_template(template_data, variables)
        if not tasks:
            raise ValueError(f"template '{args.template}' produced no tasks")
        return tasks
    if args.plan_file:
        plan_path = Path(args.plan_file)
        if not plan_path.is_file():
            raise ValueError(f"workflow plan not found: {plan_path}")
        return _planned_tasks_from_file(plan_path, config=config)
    if args.planner_agent:
        if args.dry_run:
            raise ValueError(
                "dry-run workflows require --plan-file or --template because "
                "planner agents must execute to produce a plan"
            )
        return plan_tasks_with_agent(
            config=config,
            goal=args.goal,
            planner_agent=args.planner_agent,
        )
    raise ValueError(
        "workflow run requires --plan-file, --template, or --planner-agent"
    )


def cmd_workflow(args: argparse.Namespace) -> int:
    config = _load_config_or_print(Path(args.config))
    if config is None:
        return 1
    store = _workflow_store_for(config)

    if args.workflow_command == "run":
        if args.backend == "crewai":
            if args.dry_run:
                print("CrewAI backend does not support --dry-run", file=sys.stderr)
                return 1
            manager_agent = args.manager_agent or args.planner_agent or "codex_reviewer"
            if manager_agent not in config.agents:
                print(f"unknown manager agent: {manager_agent}", file=sys.stderr)
                print(
                    f"available agents: {', '.join(sorted(config.agents))}",
                    file=sys.stderr,
                )
                return 1
            try:
                result = run_crewai_workflow(
                    config=config,
                    store=store,
                    goal=args.goal,
                    manager_agent_name=manager_agent,
                )
            except CrewAIUnavailableError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            except ValueError as exc:
                print(f"invalid CrewAI workflow: {exc}", file=sys.stderr)
                return 1
            print(f"workflow_id: {result.workflow_id}")
            print(f"status: {result.status}")
            print(f"workflow_dir: {result.workflow_dir}")
            return 0 if result.status == "succeeded" else 1

        if args.backend == "crewai-flow":
            try:
                tasks = _resolve_tasks(args, config)
                result = run_flow_workflow(
                    config=config,
                    store=store,
                    goal=args.goal,
                    tasks=tasks,
                    dry_run=args.dry_run,
                )
            except (ValueError, json.JSONDecodeError) as exc:
                print(f"flow error: {exc}", file=sys.stderr)
                return 1
            print(f"workflow_id: {result.workflow_id}")
            print(f"status: {result.status}")
            print(f"workflow_dir: {result.workflow_dir}")
            return 0 if result.status == "succeeded" else 1

        try:
            tasks = _resolve_tasks(args, config)
            result = WorkflowOrchestrator(config, store).run_plan(
                goal=args.goal,
                tasks=tasks,
                dry_run=args.dry_run,
            )
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"invalid workflow plan: {exc}", file=sys.stderr)
            return 1
        print(f"workflow_id: {result.workflow_id}")
        print(f"status: {result.status}")
        print(f"workflow_dir: {result.workflow_dir}")
        return 0 if result.status == "succeeded" else 1

    if args.workflow_command == "status":
        if args.workflow_id:
            try:
                workflow = store.load_workflow(args.workflow_id)
            except FileNotFoundError:
                print(f"workflow not found: {args.workflow_id}", file=sys.stderr)
                return 1
            print(f"{workflow.workflow_id}  {workflow.status:<9}  {workflow.goal}")
            for task in store.list_tasks(workflow.workflow_id):
                print(
                    f"  {task.task_id}  {task.status:<13}  "
                    f"{task.agent}  run={task.run_id or '-'}  "
                    f"review={task.review_run_id or '-'}"
                )
            return 0
        workflows = store.list_workflows()
        if not workflows:
            print("no workflows")
            return 0
        for workflow in workflows:
            print(f"{workflow.workflow_id}  {workflow.status:<9}  {workflow.goal}")
        return 0

    if args.workflow_command == "logs":
        if not store.workflow_dir(args.workflow_id).exists():
            print(f"workflow not found: {args.workflow_id}", file=sys.stderr)
            return 1
        print(f"# Workflow Events: {args.workflow_id}")
        for line in store.read_events(args.workflow_id):
            print(line)
        return 0

    if args.workflow_command == "approve":
        if not store.workflow_dir(args.workflow_id).exists():
            print(f"workflow not found: {args.workflow_id}", file=sys.stderr)
            return 1
        approve_task(store, args.workflow_id, args.task_id, comment=args.comment)
        print(f"task {args.task_id} approved in workflow {args.workflow_id}")
        return 0

    if args.workflow_command == "reject":
        if not store.workflow_dir(args.workflow_id).exists():
            print(f"workflow not found: {args.workflow_id}", file=sys.stderr)
            return 1
        reject_task(store, args.workflow_id, args.task_id, reason=args.reason)
        print(f"task {args.task_id} rejected in workflow {args.workflow_id}")
        return 0

    if args.workflow_command == "resume":
        if not store.workflow_dir(args.workflow_id).exists():
            print(f"workflow not found: {args.workflow_id}", file=sys.stderr)
            return 1
        try:
            orchestrator = WorkflowOrchestrator(config, store)
            result = orchestrator.resume_workflow(args.workflow_id)
        except ValueError as exc:
            print(f"cannot resume: {exc}", file=sys.stderr)
            return 1
        print(f"workflow_id: {result.workflow_id}")
        print(f"status: {result.status}")
        print(f"workflow_dir: {result.workflow_dir}")
        return 0 if result.status == "succeeded" else 1

    if args.workflow_command == "templates":
        templates = list_templates()
        if not templates:
            print("no templates available")
            return 0
        for name, description in sorted(templates.items()):
            print(f"  {name:<32}  {description}")
        return 0

    print(f"unknown workflow command: {args.workflow_command}", file=sys.stderr)
    return 1


def cmd_status(args: argparse.Namespace) -> int:
    config = _load_config_or_print(Path(args.config))
    if config is None:
        return 1
    runs = RunStore(config.runs_dir).list_runs()[: args.limit]
    if not runs:
        print("no runs")
        return 0
    for run in runs:
        print(
            f"{run.run_id}  {run.status:<9}  {run.agent:<18}  "
            f"{run.runtime:<12}  {run.task}"
        )
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    config = _load_config_or_print(Path(args.config))
    if config is None:
        return 1
    store = RunStore(config.runs_dir)
    run_dir = store.run_dir(args.run_id)
    if not run_dir.exists():
        print(f"run not found: {args.run_id}", file=sys.stderr)
        return 1
    print(f"# Events: {args.run_id}")
    for line in store.read_events(args.run_id):
        print(line)
    stderr_path = run_dir / "outputs" / "stderr.txt"
    stdout_path = run_dir / "outputs" / "stdout.txt"
    if stdout_path.exists() and stdout_path.read_text(encoding="utf-8").strip():
        print("\n# stdout")
        print(stdout_path.read_text(encoding="utf-8"))
    if stderr_path.exists() and stderr_path.read_text(encoding="utf-8").strip():
        print("\n# stderr")
        print(stderr_path.read_text(encoding="utf-8"))
    return 0


def _load_config_dict_or_print(path: Path):
    try:
        if not path.exists():
            return app_config_to_dict(default_config())
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"invalid JSON config: {exc}", file=sys.stderr)
        return None


def _save_config_dict(data: dict, path: Path) -> None:
    config = app_config_from_dict(data)
    errors = validate_config(config)
    if errors:
        raise ValueError("; ".join(errors))
    save_config(config, path)


def cmd_credentials(args: argparse.Namespace) -> int:
    path = Path(args.config)
    data = _load_config_dict_or_print(path)
    if data is None:
        return 1
    config = app_config_from_dict(data)
    errors = validate_config(config)
    if errors:
        print(f"invalid config: {'; '.join(errors)}", file=sys.stderr)
        return 1

    if args.credentials_command == "list":
        runtimes = (
            {args.runtime: config.runtimes[args.runtime]}
            if args.runtime
            else config.runtimes
        )
        if args.runtime and args.runtime not in config.runtimes:
            print(f"unknown runtime: {args.runtime}", file=sys.stderr)
            return 1
        for runtime_name, runtime in runtimes.items():
            print(f"{runtime_name}:")
            if not runtime.credentials:
                print("  no credential profiles")
            for profile in runtime.credentials:
                key_source = (
                    f"env:{profile.api_key_env}"
                    if profile.api_key_env
                    else "inline-api-key"
                )
                print(
                    f"  - {profile.name}: base_url={profile.base_url or 'runtime default'}, key={key_source}"
                )
        return 0

    if args.runtime not in config.runtimes:
        print(f"unknown runtime: {args.runtime}", file=sys.stderr)
        return 1

    runtime_data = data.setdefault("runtimes", {}).setdefault(
        args.runtime,
        {"command": config.runtimes[args.runtime].command, "credentials": []},
    )
    credentials = runtime_data.setdefault("credentials", [])

    if args.credentials_command == "add":
        new_profile = {
            "name": args.name,
            "base_url": args.base_url,
            "api_key": args.api_key,
            "api_key_env": args.api_key_env,
        }
        new_profile = {key: value for key, value in new_profile.items() if value}
        remaining = [
            profile for profile in credentials if profile.get("name") != args.name
        ]
        remaining.append(new_profile)
        runtime_data["credentials"] = remaining
        try:
            _save_config_dict(data, path)
        except ValueError as exc:
            print(f"invalid config: {exc}", file=sys.stderr)
            return 1
        print(f"saved credential {args.runtime}/{args.name} to {path}")
        return 0

    if args.credentials_command == "remove":
        remaining = [
            profile for profile in credentials if profile.get("name") != args.name
        ]
        if len(remaining) == len(credentials):
            print(f"credential not found: {args.runtime}/{args.name}", file=sys.stderr)
            return 1
        runtime_data["credentials"] = remaining
        try:
            _save_config_dict(data, path)
        except ValueError as exc:
            print(f"invalid config: {exc}", file=sys.stderr)
            return 1
        print(f"removed credential {args.runtime}/{args.name} from {path}")
        return 0

    print(f"unknown credentials command: {args.credentials_command}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "init": cmd_init,
        "doctor": cmd_doctor,
        "run": cmd_run,
        "status": cmd_status,
        "logs": cmd_logs,
        "credentials": cmd_credentials,
        "workflow": cmd_workflow,
    }
    return handlers[args.command](args)
