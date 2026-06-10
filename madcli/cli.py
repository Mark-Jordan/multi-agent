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
from .context import make_run_id, write_context_package
from .executors import ExecutorRequest, executor_for
from .run_store import RunStore


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
        "--dry-run",
        action="store_true",
        help="Build the runtime command without executing it.",
    )
    run_parser.add_argument(
        "--credential",
        default=None,
        help="Credential profile name for the selected runtime. Defaults to trying profiles in config order.",
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
    agent = config.agents[args.agent]
    runtime = config.runtimes[agent.runtime]
    workdir = Path(args.workdir) if args.workdir else config.default_workdir
    workdir = workdir.resolve()
    run_id = make_run_id(args.task)
    store = RunStore(config.runs_dir)
    metadata = store.create_run(
        run_id=run_id,
        task=args.task,
        agent=agent.name,
        runtime=agent.runtime,
        workdir=workdir,
    )
    context_files = write_context_package(
        context_dir=store.run_dir(run_id) / "context",
        task=args.task,
        agent=agent,
        extra_context=args.context,
    )
    store.append_event(
        run_id,
        "context_written",
        {"files": [str(path) for path in context_files]},
    )

    executor = executor_for(agent.runtime)
    request = ExecutorRequest(
        runtime=runtime,
        agent=agent,
        task=args.task,
        workdir=workdir,
        context_files=[path.resolve() for path in context_files],
        dry_run=args.dry_run,
        credential_name=args.credential,
    )
    try:
        result = executor.run(request)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        store.update_status(run_id, "failed")
        return 1
    outputs_dir = store.run_dir(run_id) / "outputs"
    (outputs_dir / "command.json").write_text(
        json.dumps(result.command, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (outputs_dir / "attempts.json").write_text(
        json.dumps(result.attempts or [], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (outputs_dir / "stdout.txt").write_text(result.stdout, encoding="utf-8")
    (outputs_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
    store.append_event(
        run_id,
        "executor_finished",
        {
            "ok": result.ok,
            "dry_run": args.dry_run,
            "returncode": result.returncode,
            "command": result.command,
            "credential": result.credential_name,
            "attempts": result.attempts or [],
        },
    )
    final_status = "dry_run" if args.dry_run else "succeeded" if result.ok else "failed"
    store.update_status(run_id, final_status)

    print(f"run_id: {metadata.run_id}")
    print(f"status: {final_status}")
    print(f"runtime: {agent.runtime}")
    print(f"agent: {agent.name}")
    if result.credential_name:
        print(f"credential: {result.credential_name}")
    print(f"run_dir: {store.run_dir(run_id)}")
    if args.dry_run:
        print("command:")
        print(json.dumps(result.command, indent=2, ensure_ascii=False))
    elif not result.ok:
        print(result.stderr, file=sys.stderr)
        return 1
    return 0


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
    }
    return handlers[args.command](args)
