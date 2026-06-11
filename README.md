# Multi Agent Dev CLI

`multi-agent-dev-cli` is a CLI-first runner for sending coding tasks to mature coding agents while preserving explicit, durable context files for every run.

The project is intended to sit between a research or orchestration layer and coding runtimes such as OpenCode, Codex, and Claude Code:

```text
Research manager / human operator
  -> madcli
    -> context package
    -> OpenCode / Codex / Claude Code
```

The first version is intentionally small. It does not implement its own LLM agent, code editor, shell sandbox, or multi-agent planner. It wraps existing coding runtimes behind one config and one CLI.

## Current Status

Implemented:

- Python standard-library CLI runnable with `python -m madcli`.
- JSON config for runtime and agent mapping.
- Runtime wrappers for `opencode`, `codex`, and `claude_code`.
- Runtime credential profiles with API key and base URL pairs.
- Ordered fallback credentials for Codex and Claude Code execution.
- Durable run storage under `.madcli/runs/<run-id>/`.
- Context package generation for each task.
- Existing markdown context files can be attached with repeatable `--context-file`.
- Agent configs can store active credential/model selections so the next run uses changed URL, API key source, and model without restarting.
- Desktop app skeleton under `apps/desktop` with sessions, Codex-like messages, multi-agent labels, project files, and a hidden code editor drawer.
- Commands: `init`, `doctor`, `run`, `status`, `logs`, `credentials`.
- Unit tests for config, context package generation, run storage, project files, sessions, CLI behavior, and executor command construction.

Not implemented yet:

- CrewAI integration.
- Fully wired desktop backend API and streaming execution.
- Backtest tools.
- Parallel engineer coordination.
- Git worktree isolation.
- Runtime SDK integrations.
- Provider adapters for direct model APIs.

## Installation

This project currently has no third-party Python dependencies.

Use it from the project directory:

```bash
cd D:\selfworkspace\multi-agent-dev-cli
python -m madcli --help
```

Optional editable install:

```bash
python -m pip install -e .
madcli --help
```

## Quick Start

Create a config:

```bash
python -m madcli init
```

Check config and runtime availability:

```bash
python -m madcli doctor
```

Create a dry-run task without invoking a real coding runtime:

```bash
python -m madcli run "Implement a simple mean reversion strategy" --agent strategy_engineer --dry-run
```

List runs:

```bash
python -m madcli status
```

Read logs for one run:

```bash
python -m madcli logs <run-id>
```

## Configuration

`madcli.config.json` maps high-level agent names to coding runtimes.

Default shape:

```json
{
  "runs_dir": ".madcli/runs",
  "default_workdir": ".",
  "runtimes": {
    "opencode": {
      "command": "opencode",
      "credentials": []
    },
    "codex": {
      "command": "codex",
      "credentials": [
        {
          "name": "primary",
          "base_url": "https://api.openai.com/v1",
          "api_key_env": "OPENAI_API_KEY_PRIMARY"
        },
        {
          "name": "backup",
          "base_url": "https://backup-gateway.example/v1",
          "api_key_env": "OPENAI_API_KEY_BACKUP"
        }
      ]
    },
    "claude_code": {
      "command": "claude",
      "credentials": []
    }
  },
  "agents": {
    "strategy_engineer": {
      "runtime": "opencode",
      "agent": "engineer",
      "model": "anthropic/claude-sonnet-4-20250514",
      "description": "Implements strategy code using the selected coding runtime."
    },
    "codex_reviewer": {
      "runtime": "codex",
      "agent": "reviewer",
      "model": "gpt-5-codex",
      "description": "Reviews diffs and implementation reports."
    },
    "claude_engineer": {
      "runtime": "claude_code",
      "agent": "strategy-engineer",
      "model": "sonnet",
      "description": "Implements code through Claude Code."
    }
  }
}
```

Fields:

- `runs_dir`: where run metadata, context files, and outputs are stored.
- `default_workdir`: repository path passed to the coding runtime when `--workdir` is not provided.
- `runtimes.<name>.command`: executable name or absolute path for the runtime.
- `runtimes.<name>.credentials`: ordered API credential profiles. Each profile can define `name`, `base_url`, `api_key`, or `api_key_env`.
- `agents.<name>.runtime`: one of `opencode`, `codex`, or `claude_code`.
- `agents.<name>.agent`: runtime-specific agent name.
- `agents.<name>.model`: runtime-specific model name. Use `null` to let the runtime pick its default.
- `agents.<name>.description`: human-readable purpose.

Use a different config path with:

```bash
python -m madcli --config path\to\config.json doctor
```

## Credential Profiles

Credential profiles bind an API key source to a request base URL.

Use `--api-key-env` for normal use so secrets stay out of the config file:

```bash
python -m madcli credentials add ^
  --runtime codex ^
  --name primary ^
  --base-url https://api.openai.com/v1 ^
  --api-key-env OPENAI_API_KEY_PRIMARY

python -m madcli credentials add ^
  --runtime codex ^
  --name backup ^
  --base-url https://backup-gateway.example/v1 ^
  --api-key-env OPENAI_API_KEY_BACKUP
```

For quick local tests, inline keys are also supported:

```bash
python -m madcli credentials add --runtime codex --name local --base-url https://api.openai.com/v1 --api-key sk-...
```

List profiles:

```bash
python -m madcli credentials list
python -m madcli credentials list --runtime codex
```

Remove a profile:

```bash
python -m madcli credentials remove --runtime codex --name backup
```

Run with a specific profile:

```bash
python -m madcli run "review the current diff" --agent codex_reviewer --credential primary
```

Run without `--credential` to try profiles in config order. If the current profile fails with common auth, quota, or rate-limit errors, the executor tries the next profile.

### Codex Immediate Config Refresh

Codex interactive sessions can hold provider configuration until the process is restarted. `madcli` avoids that problem for CLI runs by starting a fresh `codex exec` process and injecting provider settings on every run:

```text
codex exec
  -c model_provider="madcli_primary"
  -c model_providers.madcli_primary.base_url="..."
  -c model_providers.madcli_primary.env_key="OPENAI_API_KEY"
  -c model_providers.madcli_primary.wire_api="responses"
```

The selected key is passed through the child process environment as `OPENAI_API_KEY`. Updating `madcli.config.json` or using `madcli credentials add` takes effect on the next `madcli run`; no Codex interactive restart is required.

`command.json` and event logs do not store raw API keys. If you use inline `api_key`, the key is stored in `madcli.config.json`; prefer `api_key_env` for persistent configs.

## Context Package

Each `run` creates:

```text
.madcli/runs/<run-id>/
  metadata.json
  events.jsonl
  context/
    user_goal.md
    agent_context.md
    engineering_task.md
    extra_context.md        # only when --context is provided
    context_file_1_*.md     # copied files from --context-file
  outputs/
    command.json
    attempts.json
    stdout.txt
    stderr.txt
```

The context package is the source of truth for handoff from a manager agent to a coding runtime. Important requirements should be written into context files, not assumed to exist in hidden chat history.

## Commands

Initialize config:

```bash
python -m madcli init [--force]
```

Validate config and runtime binaries:

```bash
python -m madcli doctor
```

Credential profile management:

```bash
python -m madcli credentials list
python -m madcli credentials list --runtime codex
python -m madcli credentials add --runtime codex --name primary --base-url https://api.openai.com/v1 --api-key-env OPENAI_API_KEY_PRIMARY
python -m madcli credentials remove --runtime codex --name primary
```

Run a task:

```bash
python -m madcli run "task text" --agent strategy_engineer
```

Dry-run command construction:

```bash
python -m madcli run "task text" --agent codex_reviewer --dry-run
```

Run with a selected credential:

```bash
python -m madcli run "task text" --agent codex_reviewer --credential primary
```

Use a different repository workdir:

```bash
python -m madcli run "task text" --agent claude_engineer --workdir D:\path\to\repo
```

Add short extra context:

```bash
python -m madcli run "task text" --agent strategy_engineer --context "Use daily bars and include transaction costs."
```

Attach an existing markdown context file:

```bash
python -m madcli run "task text" --agent strategy_engineer --context-file docs\research_state.md
```

Repeat `--context-file` to attach multiple files. `madcli` copies each file into the run context package so the run keeps a durable snapshot.

List runs:

```bash
python -m madcli status --limit 20
```

Print logs:

```bash
python -m madcli logs <run-id>
```

## Runtime Notes

The first version uses CLI wrappers:

- OpenCode: `opencode run --agent ... --model ... --dir ... --file ... --format json`
- Codex: `codex exec --cd ... -c model_provider=... -c model_providers... --model ...`
- Claude Code: `claude -p --agent ... --model ... --output-format stream-json`

The wrappers build argument arrays rather than shell strings. Missing runtime commands are reported as runtime errors. Credential API keys are injected through subprocess environment variables, not shell arguments.

## Desktop App

The desktop application scaffold lives in `apps/desktop`.

```bash
cd apps/desktop
npm install
npm run dev
```

Build the desktop app and create a Windows executable:

```bash
npm run build
npm run dist:win
```

The generated executable is:

```text
apps/desktop/release/madcli-workbench-win-x64/madcli-workbench.exe
```

Double-click `madcli-workbench.exe` to open the application window. Keep the generated directory together with the `.exe`; it contains the Electron runtime files required by the app.

The current shell is an Electron/React workbench with:

- Session list and Codex-like conversation stream.
- Distinct visual identity for `strategy_engineer`, `codex_reviewer`, and `claude_engineer`.
- Agent, model, and credential profile controls.
- Project file panel and run artifact list.
- Code editor drawer hidden by default and expandable from the composer.
- Startup setup panel for missing model API profiles.
- In-app runtime installation prompts for Codex, Claude Code, or OpenCode. Install commands require user confirmation before running.

Credential/profile changes are persisted in config as active agent selections. `madcli run` reloads config per invocation, so changed base URLs, API key sources, and model selections apply to the next run without restarting the app.

## Verification

Run all tests:

```bash
python -m unittest discover -s tests -v
```

Expected result:

```text
Ran 30 tests
OK
```

## Roadmap

Planned next steps:

1. Add stronger credential failure classification per runtime instead of the current broad stderr/stdout marker matching.
2. Add explicit git worktree isolation for coding runs.
3. Add structured `result.json` output parsing for each runtime.
4. Add a CrewAI tool that calls `madcli run` and reads run artifacts.
5. Add backtest and experiment registry tools for quant research workflows.
6. Wire the desktop UI to a local API and WebSocket run streaming.
7. Add a lightweight browser-hosted web UI after desktop workflows stabilize.
8. Replace CLI wrappers with runtime SDKs where that gives better streaming, cancellation, and structured events.
