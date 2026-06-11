# Desktop Chat Settings Workspace Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the desktop app use a conversation-first layout, with agent/runtime configuration in settings, an explicit missing-configuration prompt, collapsible sessions, and user-selectable workspace files.

**Architecture:** Keep `madcli` as the runtime bridge. Electron main owns filesystem, dialog, config, and CLI calls; React owns presentation and user interaction state. The selected workspace is persisted in the desktop config as `default_workdir`, while CLI commands still execute from the `multi-agent` project root and pass `--workdir` explicitly.

**Tech Stack:** Electron main/preload CommonJS, React/TypeScript, Vite, Node built-in test runner, Python unittest.

---

### Task 1: Add Service Tests

**Files:**
- Modify: `apps/desktop/electron/main.test.cjs`

**Steps:**
1. Add tests for saving a workspace path into config and using that workspace for file listing.
2. Add tests for detecting whether an agent can run based on credentials/runtime diagnostics.
3. Run `node "electron/main.test.cjs"` and verify the new tests fail before implementation.

### Task 2: Extend Electron Service and IPC

**Files:**
- Modify: `apps/desktop/electron/main.cjs`
- Modify: `apps/desktop/electron/preload.cjs`
- Modify: `apps/desktop/src/types.ts`

**Steps:**
1. Add `workspaceRoot` to startup diagnostics.
2. Add `chooseWorkspace`, `getSettingsState`, and `canRunAgent`.
3. Make project file operations use `workspaceRoot`.
4. Make `runDryRun` pass `--workdir <workspaceRoot>`.
5. Expose the new IPC methods through preload and TypeScript types.

### Task 3: Restructure React Layout

**Files:**
- Modify: `apps/desktop/src/App.tsx`
- Modify: `apps/desktop/src/styles.css`

**Steps:**
1. Remove the agent rail, runtime strip, and setup panel from the conversation surface.
2. Add a settings drawer containing agent selection, model/profile form, runtime checks, and diagnostic actions.
3. Add a modal prompt shown when sending without required model/runtime configuration, with actions to open settings.
4. Add a left sidebar collapse button and grid state.
5. Add a workspace selector in the right project panel.

### Task 4: Verify and Sync Packaged App

**Files:**
- Generated: `apps/desktop/dist/**`
- Generated ignored resources under `apps/desktop/release/madcli-workbench-win-x64/resources/app`

**Steps:**
1. Run `node "electron/main.test.cjs"`.
2. Run `npm run build` in `apps/desktop`.
3. Run `python -m unittest discover -s tests -v`.
4. Run a service smoke for `runDoctor`.
5. Copy updated `dist`, `electron`, and `package.json` into the existing packaged app resource directory.
