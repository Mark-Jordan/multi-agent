# Desktop Agent Workbench Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a desktop application shell for `madcli` with sessions, Codex-like conversation display, multi-agent identity, project file browsing, a collapsible code editor, and runtime credential/model switching that applies immediately to new runs.

**Architecture:** Keep `madcli` as the core bridge. Add a small standard-library backend API layer for local app state and project inspection, plus an Electron/React desktop frontend under `apps/desktop`. Session data is durable JSON under `.madcli/app/`, while existing run artifacts remain under `.madcli/runs/`.

**Tech Stack:** Python 3.11 standard library for backend state/API primitives, Electron + React + Vite + TypeScript for the desktop frontend, CSS modules/plain CSS for the first UI shell.

---

### Task 1: Session Store

**Files:**
- Create: `madcli/session_store.py`
- Test: `tests/test_session_store.py`

**Step 1: Write the failing test**

Create tests proving:
- `SessionStore.create_session()` persists a session JSON file.
- `SessionStore.append_message()` appends user and agent messages with stable metadata.
- `SessionStore.list_sessions()` returns newest sessions first.

**Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s tests -p "test_session_store.py" -v`
Expected: FAIL because `madcli.session_store` does not exist.

**Step 3: Write minimal implementation**

Implement dataclasses for `SessionRecord` and `MessageRecord`; store each session as `.madcli/app/sessions/<session-id>.json`.

**Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s tests -p "test_session_store.py" -v`
Expected: PASS.

### Task 2: Project File Service

**Files:**
- Create: `madcli/project_files.py`
- Test: `tests/test_project_files.py`

**Step 1: Write the failing test**

Create tests proving:
- File tree listing excludes `.git`, `.madcli`, `node_modules`, and Python caches.
- File reads reject paths outside the configured project root.

**Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s tests -p "test_project_files.py" -v`
Expected: FAIL because `madcli.project_files` does not exist.

**Step 3: Write minimal implementation**

Implement `list_project_tree(root)` and `read_project_file(root, relative_path)` with path containment checks.

**Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s tests -p "test_project_files.py" -v`
Expected: PASS.

### Task 3: Immediate Runtime Configuration Switching

**Files:**
- Modify: `madcli/config.py`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

Create a test proving an agent can select a named credential profile and model override without restarting by saving config and reloading it for the next request.

**Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s tests -p "test_config.py" -k "active_profile" -v`
Expected: FAIL because active profile fields do not exist yet.

**Step 3: Write minimal implementation**

Add optional `active_credential` and `active_model` to `AgentConfig`. Preserve existing config compatibility.

**Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s tests -p "test_config.py" -k "active_profile" -v`
Expected: PASS.

### Task 4: Desktop Frontend Skeleton

**Files:**
- Create: `apps/desktop/package.json`
- Create: `apps/desktop/index.html`
- Create: `apps/desktop/electron/main.cjs`
- Create: `apps/desktop/electron/preload.cjs`
- Create: `apps/desktop/src/App.tsx`
- Create: `apps/desktop/src/main.tsx`
- Create: `apps/desktop/src/styles.css`
- Create: `apps/desktop/src/types.ts`
- Create: `apps/desktop/tsconfig.json`
- Create: `apps/desktop/vite.config.ts`

**Step 1: Create the UI shell**

Implement:
- Left sidebar session list.
- Agent rail with distinct visual identity per agent.
- Central conversation transcript.
- Bottom prompt composer with agent/model/profile selectors.
- Right project panel with file tree.
- Collapsible code editor drawer, hidden by default.

**Step 2: Add frontend scripts**

Add `npm run dev`, `npm run build`, and `npm run electron:dev`.

**Step 3: Verify dependency availability**

Run `npm install` only after explicit approval if network dependency installation is required.

### Task 5: Documentation and Verification

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`

**Step 1: Document app architecture**

Add a Desktop App section with the intended command flow and immediate credential-switching behavior.

**Step 2: Run backend tests**

Run: `python -m unittest discover -s tests -v`
Expected: all Python tests pass.

**Step 3: Run frontend verification if dependencies are installed**

Run: `npm run build` from `apps/desktop`.
Expected: TypeScript/Vite build succeeds.
