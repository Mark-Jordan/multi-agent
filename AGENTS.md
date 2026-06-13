# AGENTS.md

This file is durable context for coding agents working on `multi-agent-dev-cli`.

## Project Purpose

`multi-agent-dev-cli` is a CLI-first bridge between higher-level research or orchestration agents and mature coding runtimes.

The project should let a manager agent, a human operator, or a future CrewAI workflow delegate implementation tasks to OpenCode, Codex, or Claude Code without reimplementing their repository inspection, editing, shell, and coding capabilities.

The key design principle is context handoff:

```text
manager decides task
  -> madcli writes context package
  -> coding runtime reads context package and repository
  -> madcli stores command, stdout, stderr, events, and metadata
```

For autonomous workflows:

```text
planner/commander decides task graph
  -> madcli stores workflow metadata
  -> madcli dispatches each task through the existing run path
  -> worker result.md/stdout/stderr become reviewer context
  -> madcli stores task run IDs, review run IDs, events, and status
```

Do not rely on hidden conversation history for important requirements. Write durable context files.

## Current Task

The current implemented task includes the first CLI mode and the first autonomous workflow mode:

- Configure `opencode`, `codex`, and `claude_code`.
- Configure logical agents that map to one of those runtimes.
- Configure runtime credential profiles as API key and base URL pairs.
- Create run directories and context packages.
- Attach existing markdown files to context packages with `--context-file`.
- Store active agent credential/model selections so URL, API key source, and model switches apply on the next run without restarting the app.
- Provide an Electron/React desktop app skeleton for sessions, conversations, multi-agent labels, project files, startup setup, runtime install prompts, and a hidden code editor drawer.
- Build runtime-specific commands.
- Try ordered fallback credentials for Codex and Claude Code when auth, quota, or rate-limit style failures occur.
- Support dry-run and basic execution.
- List status and logs.
- Run sequential autonomous workflows from a JSON plan.
- Let a configured planner agent generate a JSON task plan for a workflow.
- Automatically dispatch reviewer runs after worker tasks when `review_by` is set.
- Persist workflow metadata and events under `.madcli/workflows/`.
- Run CrewAI hierarchical workflows through `--backend crewai`.
- Expose CrewAI adapter tools for running madcli agent tasks and reading run artifacts.

The current implementation intentionally does not include direct model APIs, git worktree isolation, or backtest integration.

## Current Status

Working commands:

```bash
python -m madcli init
python -m madcli doctor
python -m madcli run "task" --agent strategy_engineer --dry-run
python -m madcli workflow run "goal" --plan-file workflow-plan.json --dry-run
python -m madcli workflow run "goal" --planner-agent codex_reviewer
python -m madcli workflow run "goal" --template implement-review --var engineer_agent=strategy_engineer --var reviewer_agent=codex_reviewer --var goal="Build feature X" --dry-run
python -m madcli workflow run "goal" --backend crewai --manager-agent codex_reviewer
python -m madcli workflow run "goal" --backend crewai-flow --plan-file workflow-plan.json
python -m madcli workflow templates
python -m madcli workflow status
python -m madcli workflow logs <workflow-id>
python -m madcli workflow approve <workflow-id> <task-id>
python -m madcli workflow reject <workflow-id> <task-id>
python -m madcli workflow resume <workflow-id>
python -m madcli credentials list
python -m madcli credentials add --runtime codex --name primary --base-url https://api.openai.com/v1 --api-key-env OPENAI_API_KEY_PRIMARY
python -m madcli credentials remove --runtime codex --name primary
python -m madcli status
python -m madcli logs <run-id>
```

Implemented files:

- `madcli/cli.py`: command-line interface and command handlers.
- `madcli/config.py`: JSON config model, default config, validation, load/save.
- `madcli/context.py`: run id generation and context package writing.
- `madcli/session_store.py`: durable JSON session and message storage for the desktop app.
- `madcli/project_files.py`: project file listing and safe file reads for the desktop app.
- `madcli/executors.py`: `opencode`, `codex`, and `claude_code` executor wrappers.
- `madcli/run_store.py`: run metadata, event log, status listing.
- `madcli/task_runner.py`: reusable single-agent task runner shared by CLI and workflows.
- `madcli/workflow_store.py`: durable workflow and task state with retry/fallback/acceptance/HITL fields.
- `madcli/orchestrator.py`: parallel task dispatcher with topological scheduling, retry, fallback, review handoff, dynamic replan, human-in-the-loop.
- `madcli/planner.py`: planner-agent JSON task-plan extraction with plan validation.
- `madcli/plan_validator.py`: cycle detection, reachability, duplicate/unknown agent checks for generated plans.
- `madcli/event_bus.py`: singleton pub-sub event bus for real-time workflow event streaming.
- `madcli/agent_message.py`: structured TaskHandoff protocol for inter-agent communication.
- `madcli/hitl.py`: human-in-the-loop approval gates (request/approve/reject).
- `madcli/workflow_templates.py`: built-in workflow template engine with variable substitution.
- `madcli/templates/`: 5 built-in workflow template JSON files.
- `madcli/crewai_adapter.py`: CrewAI hierarchical backend, tool factories, manager toolkit.
- `madcli/crewai_agent_factory.py`: agent role classification and multi-agent crew builder.
- `madcli/crewai_flow_backend.py`: CrewAI Flow state-machine backend with deterministic state transitions.
- `apps/desktop/`: Electron/React desktop application scaffold.
- `apps/desktop/release/madcli-workbench-win-x64/madcli-workbench.exe`: generated local Windows executable after `npm run dist:win`; ignored by git.
- `tests/`: 100 unit tests across 20 test modules.
- `README.md`: user-facing usage manual.
- `AGENTS.md`: durable project context and planning file for future coding agents.
- `docs/superpowers/plans/2026-06-10-multi-runtime-agent-cli.md`: implementation plan used to build the first CLI.

Verification command:

```bash
python -m pytest tests/ -v
```

Expected: 100 passed.

## Architecture Rules

- Keep `madcli` as a thin runtime bridge, not a full LLM agent.
- Keep deterministic workflow orchestration in `madcli/orchestrator.py`; do not embed runtime-specific behavior there.
- Keep runtime-specific behavior inside `madcli/executors.py`.
- Keep durable run state under `.madcli/runs/`.
- Keep durable workflow state under `.madcli/workflows/`.
- Keep context files markdown-readable and easy for coding agents to inspect.
- Pass command arguments as lists to `subprocess.run`; do not build shell command strings.
- Never write API keys to `command.json`, event logs, stdout summaries, or docs.
- Prefer `api_key_env` over inline `api_key` in persistent config files.
- Codex credentials must be injected per `codex exec` invocation with `-c model_provider=...` and `model_providers.<id>.*` overrides so config changes take effect on the next run.
- Prefer Python standard library unless a dependency clearly removes meaningful complexity.
- Do not add CrewAI as a hard dependency. CrewAI belongs behind optional adapters or explicit workflow backends.
- Do not let multiple write-capable coding agents modify the same worktree in parallel until git worktree isolation exists.

## Configuration Model

Default config path:

```text
madcli.config.json
```

Default runtime keys:

- `opencode`
- `codex`
- `claude_code`

Default logical agents:

- `strategy_engineer`: OpenCode-backed implementation agent.
- `codex_reviewer`: Codex-backed review agent.
- `claude_engineer`: Claude Code-backed implementation agent.

Runtime credential profiles:

- Stored under `runtimes.<runtime>.credentials`.
- Each profile has `name`, optional `base_url`, and exactly one of `api_key` or `api_key_env`.
- Profiles are tried in config order when `madcli run` does not pass `--credential`.
- Passing `--credential <name>` restricts execution to one profile.
- For Codex, each profile produces a dynamic provider id such as `madcli_primary`.

When adding new runtime behavior, update:

- `madcli/executors.py`
- `madcli/config.py`
- `tests/test_executors.py`
- `README.md`

When adding workflow behavior, update:

- `madcli/orchestrator.py`
- `madcli/workflow_store.py`
- `madcli/planner.py` if task planning changes
- `madcli/plan_validator.py` if validation rules change
- `tests/test_orchestrator.py`
- `tests/test_workflow_store.py`
- `tests/test_planner.py`
- `README.md`

When adding event streaming, update:

- `madcli/event_bus.py`
- Tests that subscribe to relevant events

When adding inter-agent communication, update:

- `madcli/agent_message.py`
- `tests/test_agent_message.py`

When adding human-in-the-loop features, update:

- `madcli/hitl.py`
- `madcli/cli.py` workflow approve/reject/resume handlers

When adding workflow templates, update:

- `madcli/workflow_templates.py`
- `madcli/templates/` JSON files
- `tests/test_workflow_templates.py`

When adding CrewAI features, update:

- `madcli/crewai_adapter.py` (hierarchical orchestration)
- `madcli/crewai_agent_factory.py` (role classification and crew building)
- `madcli/crewai_flow_backend.py` (state-machine backend)
- `tests/test_crewai_adapter.py`
- `tests/test_crewai_agent_factory.py`
- `tests/test_crewai_flow_backend.py`

## Context Package Contract

Each run must create:

```text
.madcli/runs/<run-id>/
  metadata.json
  events.jsonl
  context/
    user_goal.md
    agent_context.md
    engineering_task.md
  outputs/
    command.json
    attempts.json
    stdout.txt
    stderr.txt
    result.md
```

If the user provides `--context`, also create:

```text
context/extra_context.md
```

If the user provides `--context-file`, copy each source file into:

```text
context/context_file_<n>_<source-name>.md
```

Workflow reviewer handoff automatically attaches worker artifacts when present:

```text
.madcli/runs/<worker-run-id>/outputs/result.md
.madcli/runs/<worker-run-id>/outputs/stdout.txt
.madcli/runs/<worker-run-id>/outputs/stderr.txt
```

CrewAI or future manager integrations should write richer context files before calling a coding runtime. Examples:

- `research_state.md`
- `hypothesis.md`
- `data_profile.md`
- `experiment_plan.md`
- `reviewer_notes.md`
- `decisions.md`

## Planning

Completed work (2026-06-12 — 13 sub-plans):

1. Parallel task execution engine with topological scheduling and ThreadPoolExecutor.
2. Plan validation (cycles, duplicates, unknown agents, reachability).
3. Task retry with configurable count/delay and fallback task IDs.
4. Dynamic agent list from config (eliminated hardcoded agent names).
5. CrewAI multi-agent roles with independent agent creation and role classification.
6. Agent-to-agent structured communication via TaskHandoff protocol.
7. Dynamic replanning on task failure (max 3 replans with context).
8. Manager agent toolkit (status, progress, worker list, task detail).
9. Acceptance criteria injected into review context with evaluation.
10. Human-in-the-loop (approve/reject/resume workflow commands).
11. Event streaming via singleton pub-sub EventBus.
12. CrewAI Flow state-machine backend with deterministic state transitions.
13. Workflow template library (5 built-in templates with variable substitution).

Near-term planned work:

1. Add stronger credential failure classification per runtime.
2. Add git worktree isolation for real coding runs.
3. Add structured runtime result parsing.
4. Add quant research helpers: experiment registry, backtest command wrapper, and metrics artifact capture.
5. Expand desktop workflow UI with workflow status/task timeline and workflow artifact browsing.
6. Add a FastAPI service and browser-hosted web UI only after desktop workflows are stable.

## Development Guidance

Before changing behavior:

1. Read `README.md`.
2. Read this `AGENTS.md`.
3. Read the relevant module and its matching tests.

Before finishing changes:

1. Run tests:

```bash
python -m unittest discover -s tests -v
```

2. If CLI behavior changed, run at least one dry-run:

```bash
python -m madcli init --force
python -m madcli credentials add --runtime codex --name smoke --base-url https://api.openai.com/v1 --api-key-env OPENAI_API_KEY
python -m madcli run "smoke task" --agent codex_reviewer --dry-run
python -m madcli workflow run "smoke workflow" --plan-file <temporary-plan.json> --dry-run
python -m madcli status
```

3. Clean generated `.madcli/`, `madcli.config.json`, and Python cache files unless the user asked to keep them.
