# Desktop Agent Roles Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add configurable role prompts and multi-role agent identities to the desktop app.

**Architecture:** Keep model connection settings in runtime credential Profiles. Add desktop-only `role_templates` and `agent_roles` to the desktop config. A runnable identity is `agentId + roleId`; `madcli run` still dispatches to the underlying agent, while the selected role prompt is injected through `--context`.

**Tech Stack:** Electron main/preload CommonJS, React/TypeScript, Vite, Node built-in tests, Python unittest.

---

### Task 1: Service Tests

**Files:**
- Modify: `apps/desktop/electron/main.test.cjs`

**Steps:**
1. Add tests that default settings include `commander`, `worker`, and `reviewer` role templates.
2. Add tests that assigning multiple roles to one agent yields multiple agent instances.
3. Add tests that `runDryRun` passes the selected role prompt through `--context`.

### Task 2: Electron Service

**Files:**
- Modify: `apps/desktop/electron/main.cjs`
- Modify: `apps/desktop/electron/preload.cjs`

**Steps:**
1. Add polished default prompts for Commander, Worker, Reviewer.
2. Add `saveRoleTemplate` and `saveAgentRoles`.
3. Add `agentInstances` to `getSettingsState`.
4. Accept `roleId` in `runDryRun` and include role prompt in CLI context.

### Task 3: Types and UI

**Files:**
- Modify: `apps/desktop/src/types.ts`
- Modify: `apps/desktop/src/App.tsx`
- Modify: `apps/desktop/src/styles.css`

**Steps:**
1. Add role and agent-instance types.
2. Add a role selector in the conversation header/composer.
3. Add a settings menu page for role prompt editing and per-agent role assignment.
4. Keep Model Profile page focused on runtime credentials only.

### Task 4: Verification and Packaging Sync

**Steps:**
1. Run `node "electron/main.test.cjs"`.
2. Run `npm run build`.
3. Run `python -m unittest discover -s tests -v`.
4. Run desktop service smoke.
5. Sync `dist` and `electron` into packaged exe resources.
