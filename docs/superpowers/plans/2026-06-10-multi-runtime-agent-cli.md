# Multi Runtime Agent CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a first CLI-only version of a multi-agent development runner that can configure OpenCode, Codex, and Claude Code as interchangeable coding executors.

**Architecture:** The CLI owns run creation, context-package generation, executor selection, process invocation, logs, and run status. OpenCode, Codex, and Claude Code remain external coding runtimes; this project wraps them behind one `CodingExecutor` interface and passes structured context files instead of raw chat history.

**Tech Stack:** Python 3.11+ standard library, `argparse`, JSON configuration, subprocess execution, markdown context artifacts, JSONL event logs.

---

## Purpose And Requirements

This project exists to support research-oriented multi-agent workflows where a higher-level manager such as CrewAI can delegate engineering work to mature coding agents without reimplementing their file editing, shell, permission, and repository understanding capabilities.

The first implementation intentionally focuses on CLI mode only. It must be useful before a web UI exists.

Required behavior:

- Provide a CLI command namespace runnable as `python -m madcli`.
- Support `init`, `run`, `status`, `logs`, and `doctor` commands.
- Use a single JSON config file to define coding agents and their runtime backend.
- Support three runtime names: `opencode`, `codex`, and `claude_code`.
- Generate a durable context package for every run under `.madcli/runs/<run-id>/context/`.
- Save command output and metadata under `.madcli/runs/<run-id>/outputs/`.
- Avoid requiring OpenCode, Codex, or Claude Code for local unit tests.
- Surface missing runtime binaries as a clear runtime error instead of crashing.

Non-goals for the first CLI:

- No web UI.
- No CrewAI dependency yet.
- No direct model API calls.
- No parallel write-agent merging.
- No custom provider adapter.
- No backtesting framework integration.

## File Structure

- `pyproject.toml`: package metadata and console script entry point.
- `README.md`: local usage, config format, and examples.
- `madcli/__init__.py`: package version.
- `madcli/__main__.py`: enables `python -m madcli`.
- `madcli/cli.py`: argparse command definitions and command handlers.
- `madcli/config.py`: config dataclasses, default config generation, JSON load/save, validation.
- `madcli/context.py`: run id generation and context package creation.
- `madcli/executors.py`: unified executor interface and runtime-specific command builders.
- `madcli/run_store.py`: run directory layout, metadata persistence, event logging, status loading.
- `tests/test_config.py`: config default and validation tests.
- `tests/test_context.py`: context package creation tests.
- `tests/test_executors.py`: runtime command-building and missing-binary behavior tests.

## CLI Shape

```bash
python -m madcli init
python -m madcli doctor
python -m madcli run "研究一个均值回归策略" --agent strategy_engineer --dry-run
python -m madcli status
python -m madcli logs <run-id>
```

Default config file:

```json
{
  "runs_dir": ".madcli/runs",
  "default_workdir": ".",
  "runtimes": {
    "opencode": { "command": "opencode" },
    "codex": { "command": "codex" },
    "claude_code": { "command": "claude" }
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

## Task 1: Project Skeleton And Config

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `madcli/__init__.py`
- Create: `madcli/__main__.py`
- Create: `madcli/config.py`
- Test: `tests/test_config.py`

- [x] **Step 1: Create package metadata and entry point**

`pyproject.toml` defines the `madcli` package and a console script named `madcli`.

- [x] **Step 2: Implement config dataclasses**

`madcli/config.py` defines `RuntimeConfig`, `AgentConfig`, and `AppConfig`, plus `default_config()`, `load_config()`, `save_config()`, and `validate_config()`.

- [x] **Step 3: Add config tests**

Tests verify that default config includes all three runtimes, validates known agents, and rejects agents that reference unknown runtimes.

## Task 2: Run Store And Context Package

**Files:**
- Create: `madcli/run_store.py`
- Create: `madcli/context.py`
- Test: `tests/test_context.py`

- [x] **Step 1: Implement run directory layout**

Each run creates:

```text
.madcli/runs/<run-id>/
  metadata.json
  events.jsonl
  context/
  outputs/
```

- [x] **Step 2: Implement context package creation**

The context package writes:

```text
context/user_goal.md
context/engineering_task.md
context/agent_context.md
```

- [x] **Step 3: Add context tests**

Tests verify stable file creation and metadata persistence.

## Task 3: Runtime Executors

**Files:**
- Create: `madcli/executors.py`
- Test: `tests/test_executors.py`

- [x] **Step 1: Implement `CodingExecutor` result types**

Define `ExecutorRequest`, `ExecutorResult`, and runtime-specific executor classes.

- [x] **Step 2: Implement command builders**

Build commands as argument arrays, not shell strings:

```text
opencode run --agent <agent> --model <model> --dir <workdir> --file <file> --format json <prompt>
codex exec --cd <workdir> <prompt>
claude -p --agent <agent> --model <model> --output-format stream-json <prompt>
```

- [x] **Step 3: Implement dry-run and missing-binary handling**

Dry-run returns the command without invoking it. Missing binaries return a failed `ExecutorResult` with a clear message.

## Task 4: CLI Commands

**Files:**
- Create: `madcli/cli.py`
- Modify: `madcli/__main__.py`
- Test indirectly via `python -m madcli ...`

- [x] **Step 1: Implement `init`**

Writes `madcli.config.json` unless it already exists.

- [x] **Step 2: Implement `doctor`**

Loads config, validates agent/runtime wiring, and reports whether each runtime binary is available.

- [x] **Step 3: Implement `run`**

Creates a run, writes context files, selects the configured executor, and either dry-runs or invokes the runtime.

- [x] **Step 4: Implement `status` and `logs`**

`status` lists recent runs. `logs <run-id>` prints the run event log and saved output summary.

## Task 5: Verification

**Files:**
- Modify: `README.md`

- [x] **Step 1: Run unit tests**

Run:

```bash
python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [x] **Step 2: Run CLI smoke tests**

Run:

```bash
python -m madcli init --force
python -m madcli doctor
python -m madcli run "smoke test task" --agent strategy_engineer --dry-run
python -m madcli status
```

Expected: commands complete without requiring external coding runtimes.

## Self-Review

Spec coverage:

- CLI mode is covered by Task 4.
- OpenCode, Codex, and Claude Code configuration is covered by Tasks 1 and 3.
- Context handoff for better coding-agent performance is covered by Task 2.
- Fast construction is supported by using only Python standard library.

Placeholder scan:

- The plan contains no unresolved implementation placeholders.

Scope check:

- This is intentionally the first CLI layer. CrewAI integration and UI are excluded from this plan to keep the first deliverable small and testable.
