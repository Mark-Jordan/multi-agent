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

Do not rely on hidden conversation history for important requirements. Write durable context files.

## Current Task

The current implemented task is the first CLI mode:

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

The current implementation intentionally does not include CrewAI, a fully wired desktop backend API, direct model APIs, or backtest integration.

## Current Status

Working commands:

```bash
python -m madcli init
python -m madcli doctor
python -m madcli run "task" --agent strategy_engineer --dry-run
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
- `apps/desktop/`: Electron/React desktop application scaffold.
- `apps/desktop/release/madcli-workbench-win-x64/madcli-workbench.exe`: generated local Windows executable after `npm run dist:win`; ignored by git.
- `tests/`: unit tests for config, context, run store, and executors.
- `README.md`: user-facing usage manual.
- `AGENTS.md`: durable project context and planning file for future coding agents.
- `docs/superpowers/plans/2026-06-10-multi-runtime-agent-cli.md`: implementation plan used to build the first CLI.

Verification command:

```bash
python -m unittest discover -s tests -v
```

Expected result:

```text
Ran 30 tests
OK
```

## Architecture Rules

- Keep `madcli` as a thin runtime bridge, not a full LLM agent.
- Keep runtime-specific behavior inside `madcli/executors.py`.
- Keep durable run state under `.madcli/runs/`.
- Keep context files markdown-readable and easy for coding agents to inspect.
- Pass command arguments as lists to `subprocess.run`; do not build shell command strings.
- Never write API keys to `command.json`, event logs, stdout summaries, or docs.
- Prefer `api_key_env` over inline `api_key` in persistent config files.
- Codex credentials must be injected per `codex exec` invocation with `-c model_provider=...` and `model_providers.<id>.*` overrides so config changes take effect on the next run.
- Prefer Python standard library unless a dependency clearly removes meaningful complexity.
- Do not add CrewAI as a hard dependency until there is a dedicated integration layer.
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
```

If the user provides `--context`, also create:

```text
context/extra_context.md
```

If the user provides `--context-file`, copy each source file into:

```text
context/context_file_<n>_<source-name>.md
```

Future CrewAI integration should write richer context files before calling a coding runtime. Examples:

- `research_state.md`
- `hypothesis.md`
- `data_profile.md`
- `experiment_plan.md`
- `reviewer_notes.md`
- `decisions.md`

## Planning

Near-term planned work:

1. Add stronger credential failure classification per runtime.
2. Add git worktree isolation for real coding runs.
3. Add structured runtime result parsing.
4. Add a CrewAI tool wrapper around `madcli run`.
5. Add quant research helpers: experiment registry, backtest command wrapper, and metrics artifact capture.
6. Wire the desktop app to a local API and WebSocket run streaming.
7. Add a FastAPI service and browser-hosted web UI only after desktop workflows are stable.

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
python -m madcli status
```

3. Clean generated `.madcli/`, `madcli.config.json`, and Python cache files unless the user asked to keep them.
