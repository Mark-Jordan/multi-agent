# CrewAI Autonomous Orchestration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an autonomous workflow layer where a commander plan can dispatch tasks to configured runtime agents, pass worker results to reviewers, and persist workflow state.

**Architecture:** Keep `madcli run` as the single-agent execution primitive. Add a workflow store and orchestrator above it, with an optional CrewAI integration adapter that can use CrewAI for planning when installed while keeping the core CLI testable without network or external packages.

**Tech Stack:** Python 3.11 standard library, existing `madcli` executor/config/run-store modules, optional CrewAI dependency exposed through an extra.

---

### Task 1: Workflow Store

**Files:**
- Create: `madcli/workflow_store.py`
- Test: `tests/test_workflow_store.py`

**Steps:**
1. Write tests for creating a workflow, saving tasks, updating task run IDs/status, and appending events.
2. Run the workflow store tests and confirm they fail because the module is missing.
3. Implement minimal dataclasses and JSON persistence under `.madcli/workflows/<workflow-id>/`.
4. Re-run the workflow store tests.

### Task 2: Reusable Agent Task Runner

**Files:**
- Create: `madcli/task_runner.py`
- Modify: `madcli/cli.py`
- Test: existing `tests/test_cli.py`

**Steps:**
1. Extract the single-agent run behavior from `cmd_run` into `run_agent_task`.
2. Keep CLI output and existing run artifacts compatible.
3. Run existing CLI tests.

### Task 3: Workflow Orchestrator

**Files:**
- Create: `madcli/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Steps:**
1. Write tests that a plan with a worker task and `review_by` automatically runs worker then reviewer.
2. Verify the reviewer receives worker result artifacts as context files.
3. Implement sequential dependency-aware orchestration.
4. Persist task status, worker run ID, review run ID, and workflow events.

### Task 4: CLI Workflow Commands

**Files:**
- Modify: `madcli/cli.py`
- Test: `tests/test_cli.py`

**Steps:**
1. Add `workflow run <goal> --plan-file <json> [--dry-run]`.
2. Add `workflow status [workflow-id]`.
3. Add `workflow logs <workflow-id>`.
4. Verify dry-run creates a workflow and uses existing run artifacts.

### Task 5: Optional CrewAI Integration Layer

**Files:**
- Create: `madcli/crewai_adapter.py`
- Modify: `pyproject.toml`
- Test: `tests/test_crewai_adapter.py`

**Steps:**
1. Add optional dependency extra `crewai`.
2. Implement lazy import helpers and clear error messages when CrewAI is unavailable.
3. Expose planner adapter functions that can be used by future `--planner crewai` mode without making tests require CrewAI.

### Task 6: Documentation and Verification

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`

**Steps:**
1. Document CrewAI's role as orchestration layer, not coding runtime replacement.
2. Document workflow commands and artifacts.
3. Run `python -m unittest discover -s tests -v`.
4. Run a workflow dry-run smoke test.
