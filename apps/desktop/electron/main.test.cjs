const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  createDesktopServices,
  defaultDesktopConfig,
  findProjectRoot,
  formatSessionSummary,
  normalizeProjectTree
} = require("./main.cjs");

test("formatSessionSummary maps stored sessions to renderer rows", () => {
  const row = formatSessionSummary(
    {
      session_id: "session-1",
      title: "Review code",
      active_agent: "codex_reviewer",
      updated_at: "2026-06-11T08:00:00.000Z",
      messages: [{ message_id: "m-1" }]
    },
    "session-1"
  );

  assert.deepEqual(row, {
    id: "session-1",
    title: "Review code",
    agentId: "codex_reviewer",
    status: "active",
    updatedAt: "2026-06-11T08:00:00.000Z",
    messageCount: 1
  });
});

test("normalizeProjectTree adds stable depth for nested file rows", () => {
  const rows = normalizeProjectTree([
    { path: "madcli", name: "madcli", type: "directory" },
    { path: "madcli/cli.py", name: "cli.py", type: "file" },
    { path: "apps/desktop/src/App.tsx", name: "App.tsx", type: "file" }
  ]);

  assert.deepEqual(rows.map((row) => [row.path, row.depth]), [
    ["madcli", 0],
    ["madcli/cli.py", 1],
    ["apps/desktop/src/App.tsx", 3]
  ]);
});

test("createDesktopServices creates and loads sessions", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-desktop-"));
  try {
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async () => ({ ok: true, code: 0, stdout: "ok", stderr: "" }),
      commandExists: () => true
    });

    const created = await services.createSession({
      title: "New work",
      activeAgent: "strategy_engineer"
    });
    const loaded = await services.loadSession(created.id);
    const sessions = await services.listSessions();

    assert.equal(created.title, "New work");
    assert.equal(loaded.id, created.id);
    assert.equal(sessions[0].id, created.id);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("desktop services prefer bundled Python and packaged madcli sources", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-bundled-python-"));
  try {
    const resourcesRoot = path.join(tempDir, "resources");
    const appRoot = path.join(resourcesRoot, "app");
    const bundledPython = path.join(resourcesRoot, "python", "python.exe");
    fs.mkdirSync(path.dirname(bundledPython), { recursive: true });
    fs.mkdirSync(path.join(appRoot, "madcli"), { recursive: true });
    fs.writeFileSync(bundledPython, "", "utf8");
    fs.writeFileSync(path.join(appRoot, "madcli", "cli.py"), "", "utf8");

    let capturedExecutable = "";
    let capturedArgs = [];
    let capturedOptions = {};
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      resourcesRoot,
      appRoot,
      runCommand: async (executable, args, options) => {
        capturedExecutable = executable;
        capturedArgs = args;
        capturedOptions = options;
        return { ok: true, code: 0, stdout: "doctor ok", stderr: "" };
      },
      commandExists: () => true
    });

    await services.runDoctor();

    assert.equal(capturedExecutable, bundledPython);
    assert.deepEqual(capturedArgs.slice(0, 2), ["-m", "madcli"]);
    assert.ok(capturedOptions.env.PYTHONPATH.split(path.delimiter).includes(appRoot));
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("deleteSession removes stored session and returns remaining sessions", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-delete-session-"));
  try {
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async () => ({ ok: true, code: 0, stdout: "ok", stderr: "" }),
      commandExists: () => true
    });

    const first = await services.createSession({
      title: "First",
      activeAgent: "codex_reviewer"
    });
    const second = await services.createSession({
      title: "Second",
      activeAgent: "codex_reviewer"
    });

    const remaining = await services.deleteSession(first.id);

    assert.deepEqual(remaining.map((session) => session.id), [second.id]);
    assert.equal(
      fs.existsSync(path.join(tempDir, "sessions", `${first.id}.json`)),
      false
    );
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("findProjectRoot resolves repository root from packaged app resources", () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-root-"));
  try {
    const repoRoot = path.join(tempDir, "repo");
    const nestedElectronDir = path.join(
      repoRoot,
      "apps",
      "desktop",
      "release",
      "madcli-workbench-win-x64",
      "resources",
      "app",
      "electron"
    );
    fs.mkdirSync(path.join(repoRoot, "madcli"), { recursive: true });
    fs.writeFileSync(path.join(repoRoot, "madcli", "cli.py"), "", "utf8");
    fs.mkdirSync(nestedElectronDir, { recursive: true });

    assert.equal(findProjectRoot([nestedElectronDir]), repoRoot);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("chooseWorkspace persists selected workspace and lists files from it", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-workspace-"));
  try {
    const appDir = path.join(tempDir, "app");
    const projectRoot = path.join(tempDir, "project");
    const workspaceRoot = path.join(tempDir, "workspace");
    fs.mkdirSync(path.join(projectRoot, "madcli"), { recursive: true });
    fs.writeFileSync(path.join(projectRoot, "madcli", "cli.py"), "", "utf8");
    fs.mkdirSync(workspaceRoot, { recursive: true });
    fs.writeFileSync(path.join(workspaceRoot, "strategy.py"), "print('ok')", "utf8");

    const services = createDesktopServices({
      appDir,
      projectRoot,
      chooseDirectory: async () => workspaceRoot,
      runCommand: async () => ({ ok: true, code: 0, stdout: "ok", stderr: "" }),
      commandExists: () => true
    });

    const diagnostics = await services.chooseWorkspace();
    const files = await services.listProjectFiles();

    assert.equal(diagnostics.workspaceRoot, workspaceRoot);
    assert.deepEqual(files.map((file) => file.path), ["strategy.py"]);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("canRunAgent reports missing credential before running api-backed agent", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-can-run-"));
  try {
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async () => ({ ok: true, code: 0, stdout: "ok", stderr: "" }),
      commandExists: () => true
    });

    const result = await services.canRunAgent("codex_reviewer");

    assert.equal(result.ok, false);
    assert.equal(result.reason, "missing_model_api_config");
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("saveCredentialProfile requires base url and api key as a pair", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-profile-pair-"));
  try {
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async () => ({ ok: true, code: 0, stdout: "ok", stderr: "" }),
      commandExists: () => true
    });

    await assert.rejects(
      () =>
        services.saveCredentialProfile({
          runtime: "codex",
          agentId: "codex_reviewer",
          profileName: "primary",
          baseUrl: "",
          apiKey: "sk-test-key",
          model: "gpt-5-codex"
        }),
      /Base URL 和 API Key 必须成对配置/
    );
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("saveCredentialProfile stores desktop api key directly instead of env name", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-profile-api-key-"));
  try {
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async () => ({ ok: true, code: 0, stdout: "ok", stderr: "" }),
      commandExists: () => true
    });

    await services.saveCredentialProfile({
      runtime: "codex",
      agentId: "codex_reviewer",
      profileName: "primary",
      baseUrl: "https://api.openai.com/v1",
      apiKey: "sk-test-key",
      model: "gpt-5-codex"
    });
    const config = JSON.parse(
      fs.readFileSync(path.join(tempDir, "madcli.config.json"), "utf8")
    );
    const profile = config.runtimes.codex.credentials[0];

    assert.equal(profile.api_key, "sk-test-key");
    assert.equal(profile.api_key_env, undefined);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("getSettingsState migrates api-key-shaped api_key_env values to api_key", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-profile-migrate-key-"));
  try {
    fs.writeFileSync(
      path.join(tempDir, "madcli.config.json"),
      JSON.stringify(
        {
          runs_dir: ".madcli/runs",
          default_workdir: tempDir,
          runtimes: {
            opencode: { command: "opencode", credentials: [] },
            codex: {
              command: "codex",
              credentials: [
                {
                  name: "primary",
                  base_url: "https://api.openai.com/v1",
                  api_key_env: "sk-legacy-key"
                }
              ]
            },
            claude_code: { command: "claude", credentials: [] }
          },
          agents: {
            codex_reviewer: {
              runtime: "codex",
              agent: "reviewer",
              model: "gpt-5-codex"
            }
          }
        },
        null,
        2
      ),
      "utf8"
    );
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async () => ({ ok: true, code: 0, stdout: "ok", stderr: "" }),
      commandExists: () => true
    });

    const state = await services.getSettingsState();
    const config = JSON.parse(
      fs.readFileSync(path.join(tempDir, "madcli.config.json"), "utf8")
    );
    const profile = config.runtimes.codex.credentials[0];

    assert.equal(profile.api_key, "sk-legacy-key");
    assert.equal(profile.api_key_env, undefined);
    assert.equal(state.credentialsByRuntime.codex[0].api_key_set, true);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("getSettingsState returns credential profiles grouped by runtime", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-settings-state-"));
  try {
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async () => ({ ok: true, code: 0, stdout: "ok", stderr: "" }),
      commandExists: () => true
    });
    await services.saveCredentialProfile({
      runtime: "codex",
      agentId: "codex_reviewer",
      profileName: "primary",
      baseUrl: "https://api.openai.com/v1",
      apiKey: "sk-openai-key",
      model: "gpt-5-codex"
    });
    await services.saveCredentialProfile({
      runtime: "claude_code",
      agentId: "claude_engineer",
      profileName: "anthropic",
      baseUrl: "https://api.anthropic.com",
      apiKey: "sk-ant-key",
      model: "sonnet"
    });

    const state = await services.getSettingsState();

    assert.equal(state.credentialsByRuntime.codex[0].name, "primary");
    assert.equal(state.credentialsByRuntime.claude_code[0].name, "anthropic");
    assert.equal(state.agents.codex_reviewer.active_credential, "primary");
    assert.equal(state.agents.claude_engineer.active_credential, "anthropic");
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("getSettingsState includes default role templates and agent instances", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-roles-default-"));
  try {
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async () => ({ ok: true, code: 0, stdout: "ok", stderr: "" }),
      commandExists: () => true
    });

    const state = await services.getSettingsState();

    assert.equal(state.roleTemplates.commander.name, "Commander");
    assert.equal(state.roleTemplates.worker.name, "Worker");
    assert.equal(state.roleTemplates.reviewer.name, "Reviewer");
    assert.ok(state.roleTemplates.commander.prompt.includes("统筹"));
    assert.ok(state.agentInstances.some((instance) => instance.roleId === "reviewer"));
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("saveAgentRoles lets one agent appear as multiple role identities", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-agent-roles-"));
  try {
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async () => ({ ok: true, code: 0, stdout: "ok", stderr: "" }),
      commandExists: () => true
    });

    await services.saveAgentRoles({
      agentId: "codex_reviewer",
      roleIds: ["commander", "worker", "reviewer"]
    });
    const state = await services.getSettingsState();

    const codexInstances = state.agentInstances.filter(
      (instance) => instance.agentId === "codex_reviewer"
    );
    assert.deepEqual(
      codexInstances.map((instance) => instance.roleId).sort(),
      ["commander", "reviewer", "worker"]
    );
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("saveRoleTemplate rejects system role edits and allows custom roles", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-system-role-readonly-"));
  try {
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async () => ({ ok: true, code: 0, stdout: "ok", stderr: "" }),
      commandExists: () => true
    });

    await assert.rejects(
      () =>
        services.saveRoleTemplate({
          id: "reviewer",
          name: "Reviewer",
          prompt: "overwritten"
        }),
      /系统默认角色不能修改/
    );

    const state = await services.saveRoleTemplate({
      id: "qa-reviewer",
      name: "QA Reviewer",
      prompt: "检查测试覆盖和验收条件。"
    });

    assert.equal(state.roleTemplates.reviewer.system, true);
    assert.equal(state.roleTemplates["qa-reviewer"].name, "QA Reviewer");
    assert.equal(state.roleTemplates["qa-reviewer"].system, false);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("getSettingsState restores built-in system role templates from config overrides", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-system-role-restore-"));
  try {
    fs.writeFileSync(
      path.join(tempDir, "madcli.config.json"),
      JSON.stringify(
        {
          runs_dir: ".madcli/runs",
          default_workdir: tempDir,
          runtimes: {
            opencode: { command: "opencode", credentials: [] },
            codex: { command: "codex", credentials: [] },
            claude_code: { command: "claude", credentials: [] }
          },
          agents: {
            codex_reviewer: {
              runtime: "codex",
              agent: "reviewer",
              model: "gpt-5-codex"
            }
          },
          role_templates: {
            reviewer: {
              id: "reviewer",
              name: "Reviewer",
              system: true,
              prompt: "modified prompt"
            },
            custom: {
              id: "custom",
              name: "Custom",
              prompt: "custom prompt"
            }
          },
          agent_roles: {
            codex_reviewer: ["reviewer", "custom"]
          }
        },
        null,
        2
      ),
      "utf8"
    );
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async () => ({ ok: true, code: 0, stdout: "ok", stderr: "" }),
      commandExists: () => true
    });

    const state = await services.getSettingsState();

    assert.notEqual(state.roleTemplates.reviewer.prompt, "modified prompt");
    assert.equal(state.roleTemplates.reviewer.system, true);
    assert.equal(state.roleTemplates.custom.prompt, "custom prompt");
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("runDryRun injects selected role prompt into context", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-role-context-"));
  try {
    let capturedArgs = [];
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async (_executable, args) => {
        capturedArgs = args;
        return {
          ok: true,
          code: 0,
          stdout: "run_id: role-run\nstatus: dry_run\nruntime: codex\nagent: codex_reviewer\n",
          stderr: ""
        };
      },
      commandExists: () => true
    });
    await services.saveCredentialProfile({
      runtime: "codex",
      agentId: "codex_reviewer",
      profileName: "primary",
      baseUrl: "https://api.openai.com/v1",
      apiKey: "sk-test-key",
      model: "gpt-5-codex"
    });

    await services.runDryRun({
      sessionId: "",
      task: "review task",
      agent: "codex_reviewer",
      roleId: "reviewer"
    });

    const contextIndex = capturedArgs.indexOf("--context");
    assert.notEqual(contextIndex, -1);
    assert.match(capturedArgs[contextIndex + 1], /Role: Reviewer/);
    assert.match(capturedArgs[contextIndex + 1], /review/i);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("runTask enqueues immediately without waiting for the runtime process", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-real-run-"));
  try {
    let capturedArgs = [];
    let finishRun;
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async (_executable, args) => {
        capturedArgs = args;
        return new Promise((resolve) => {
          finishRun = () =>
            resolve({
              ok: true,
              code: 0,
              stdout: "run_id: real-run\nstatus: succeeded\nruntime: codex\nagent: codex_reviewer\n",
              stderr: ""
            });
        });
      },
      commandExists: () => true
    });
    await services.saveCredentialProfile({
      runtime: "codex",
      agentId: "codex_reviewer",
      profileName: "primary",
      baseUrl: "https://api.openai.com/v1",
      apiKey: "sk-test-key",
      model: "gpt-5-codex"
    });
    const session = await services.createSession({
      title: "Real run",
      activeAgent: "codex_reviewer"
    });

    const result = await services.runTask({
      sessionId: session.id,
      task: "implement task",
      agent: "codex_reviewer",
      roleId: "worker"
    });
    const queued = await services.loadSession(session.id);

    assert.equal(result.ok, true);
    assert.equal(result.runId, null);
    assert.equal(capturedArgs.includes("--dry-run"), false);
    assert.equal(capturedArgs.includes("--context"), true);
    assert.equal(capturedArgs.includes("--prompt-mode"), true);
    assert.equal(capturedArgs[capturedArgs.indexOf("--prompt-mode") + 1], "task");
    assert.equal(queued.messages[0].content, "implement task");
    assert.equal(queued.messages[1].status, "running");
    assert.equal(queued.messages[1].content, "");

    finishRun();
    await waitFor(() => services.loadSession(session.id), (loaded) => {
      return loaded.messages[1].status === "succeeded";
    });
    const completed = await services.loadSession(session.id);
    assert.equal(completed.messages[1].runId, "real-run");
    assert.match(completed.messages[1].content, /运行完成/);
    assert.doesNotMatch(completed.messages[1].content, /command:/);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("runWorkflow enqueues autonomous workflow through planner agent", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-workflow-run-"));
  try {
    let capturedArgs = [];
    let finishRun;
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async (_executable, args) => {
        capturedArgs = args;
        return new Promise((resolve) => {
          finishRun = () =>
            resolve({
              ok: true,
              code: 0,
              stdout: "workflow_id: wf-1\nstatus: succeeded\nworkflow_dir: .madcli/workflows/wf-1\n",
              stderr: ""
            });
        });
      },
      commandExists: () => true
    });
    await services.saveCredentialProfile({
      runtime: "codex",
      agentId: "codex_reviewer",
      profileName: "primary",
      baseUrl: "https://api.openai.com/v1",
      apiKey: "sk-test-key",
      model: "gpt-5-codex"
    });
    const session = await services.createSession({
      title: "Workflow",
      activeAgent: "codex_reviewer"
    });

    const result = await services.runWorkflow({
      sessionId: session.id,
      goal: "build autonomous orchestration",
      plannerAgent: "codex_reviewer",
      backend: "madcli"
    });
    const queued = await services.loadSession(session.id);

    assert.equal(result.ok, true);
    assert.deepEqual(capturedArgs.slice(-5), [
      "workflow",
      "run",
      "build autonomous orchestration",
      "--planner-agent",
      "codex_reviewer"
    ]);
    assert.equal(queued.messages[0].content, "build autonomous orchestration");
    assert.equal(queued.messages[1].status, "running");
    assert.equal(queued.messages[1].content, "自动编排运行中。");

    finishRun();
    await waitFor(() => services.loadSession(session.id), (loaded) => {
      return loaded.messages[1].status === "succeeded";
    });
    const completed = await services.loadSession(session.id);
    assert.match(completed.messages[1].content, /自动编排完成：wf-1/);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("runWorkflow can launch CrewAI backend with manager agent", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-crewai-workflow-run-"));
  try {
    let capturedArgs = [];
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async (_executable, args) => {
        capturedArgs = args;
        return {
          ok: true,
          code: 0,
          stdout: "workflow_id: crew-wf\nstatus: succeeded\nworkflow_dir: .madcli/workflows/crew-wf\n",
          stderr: ""
        };
      },
      commandExists: () => true
    });
    const session = await services.createSession({
      title: "CrewAI Workflow",
      activeAgent: "codex_reviewer"
    });

    await services.runWorkflow({
      sessionId: session.id,
      goal: "coordinate crew",
      plannerAgent: "codex_reviewer",
      backend: "crewai"
    });

    assert.deepEqual(capturedArgs.slice(-7), [
      "workflow",
      "run",
      "coordinate crew",
      "--backend",
      "crewai",
      "--manager-agent",
      "codex_reviewer"
    ]);
    await waitFor(() => services.loadSession(session.id), (loaded) => {
      return loaded.messages[1].status === "succeeded";
    });
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("runWorkflow shows actionable CrewAI backend failures", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-crewai-workflow-fail-"));
  try {
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async () => ({
        ok: false,
        code: 1,
        stdout: "",
        stderr:
          'CrewAI is not installed. Install it with: python -m pip install "multi-agent-dev-cli[crewai]"\n'
      }),
      commandExists: () => true
    });
    const session = await services.createSession({
      title: "CrewAI Workflow",
      activeAgent: "codex_reviewer"
    });

    await services.runWorkflow({
      sessionId: session.id,
      goal: "coordinate crew",
      plannerAgent: "codex_reviewer",
      backend: "crewai"
    });

    await waitFor(() => services.loadSession(session.id), (loaded) => {
      return loaded.messages[1].status === "failed";
    });
    const completed = await services.loadSession(session.id);
    assert.match(completed.messages[1].content, /CrewAI is not installed/);
    assert.doesNotMatch(completed.messages[1].content, /未完成，未产生可展示的摘要/);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("runTask keeps runtime logs out of the conversation and shows final response", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-stream-run-"));
  try {
    let finishRun;
    const runsDir = path.join(tempDir, "runs");
    const runDir = path.join(runsDir, "stream-run", "outputs");
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async () => {
        return new Promise((resolve) => {
          finishRun = () =>
            {
              fs.mkdirSync(runDir, { recursive: true });
              fs.writeFileSync(path.join(runDir, "last_message.txt"), "你好！", "utf8");
              return resolve({
                ok: true,
                code: 0,
                stdout: "run_id: stream-run\nstatus: succeeded\nruntime: codex\nagent: codex_reviewer\n",
                stderr: "exec internal tool log\nREADME.md content\n"
              });
            };
        });
      },
      commandExists: () => true
    });
    const config = {
      ...defaultDesktopConfig(tempDir),
      runs_dir: runsDir
    };
    fs.writeFileSync(services.configPath, JSON.stringify(config, null, 2), "utf8");
    await services.saveCredentialProfile({
      runtime: "codex",
      agentId: "codex_reviewer",
      profileName: "primary",
      baseUrl: "https://api.openai.com/v1",
      apiKey: "sk-test-key",
      model: "gpt-5-codex"
    });
    const session = await services.createSession({
      title: "Stream run",
      activeAgent: "codex_reviewer"
    });

    await services.runTask({
      sessionId: session.id,
      task: "stream task",
      agent: "codex_reviewer",
      roleId: "worker"
    });

    const queued = await services.loadSession(session.id);
    assert.equal(queued.messages[1].status, "running");
    assert.equal(queued.messages[1].content, "");
    assert.doesNotMatch(queued.messages[1].content, /internal tool log/);

    finishRun();
    await waitFor(() => services.loadSession(session.id), (loaded) => {
      return loaded.messages[1].status === "succeeded";
    });
    const completed = await services.loadSession(session.id);
    assert.equal(completed.messages[1].content, "你好！");
    assert.doesNotMatch(completed.messages[1].content, /internal tool log/);
    assert.doesNotMatch(completed.messages[1].content, /README/);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("runTask streams filtered runtime actions while the process is running", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-stream-actions-"));
  try {
    let finishRun;
    let capturedOptions = {};
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async (_executable, _args, options) => {
        capturedOptions = options;
        setTimeout(() => {
          options.onStderr(
            [
              "exec",
              '"C:\\\\Program Files\\\\PowerShell\\\\7\\\\pwsh.exe" -Command \'Get-Content -Path "C:/Users/Administrator/.codex/skills/.system/using-superpowers/SKILL.md"\' in D:\\CodeWorkspace\\multi-agent',
              ""
            ].join("\n")
          );
        }, 5);
        return new Promise((resolve) => {
          finishRun = () =>
            resolve({
              ok: false,
              code: 1,
              stdout: "run_id: streamed-run\nstatus: failed\nruntime: codex\nagent: codex_reviewer\n",
              stderr: "Cannot find path 'C:\\Users\\Administrator\\.codex\\skills\\.system\\using-superpowers\\SKILL.md'\n"
            });
        });
      },
      commandExists: () => true
    });
    await services.saveCredentialProfile({
      runtime: "codex",
      agentId: "codex_reviewer",
      profileName: "primary",
      baseUrl: "https://api.openai.com/v1",
      apiKey: "sk-test-key",
      model: "gpt-5-codex"
    });
    const session = await services.createSession({
      title: "Stream actions",
      activeAgent: "codex_reviewer"
    });

    await services.runTask({
      sessionId: session.id,
      task: "stream actions",
      agent: "codex_reviewer",
      roleId: "worker"
    });

    const streamed = await waitFor(() => services.loadSession(session.id), (loaded) => {
      return loaded.messages[1].content.includes("读取 Skill：using-superpowers");
    });
    assert.equal(capturedOptions.env.PYTHONUTF8, "1");
    assert.equal(capturedOptions.env.PYTHONIOENCODING, "utf-8");
    assert.equal(streamed.messages[1].status, "running");
    assert.doesNotMatch(streamed.messages[1].content, /SKILL.md' because it does not exist/);

    finishRun();
    await waitFor(() => services.loadSession(session.id), (loaded) => {
      return loaded.messages[1].status === "failed";
    });
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("runTask shows filtered actions and errors instead of raw command output", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "madcli-compact-failure-"));
  try {
    let finishRun;
    const services = createDesktopServices({
      appDir: tempDir,
      projectRoot: tempDir,
      runCommand: async () => {
        return new Promise((resolve) => {
          finishRun = () =>
            resolve({
              ok: false,
              code: 1,
              stdout: "run_id: failed-run\nstatus: failed\nruntime: codex\nagent: codex_reviewer\n",
              stderr: [
                "Reading additional input from stdin...",
                "exec",
                '"C:\\\\Program Files\\\\PowerShell\\\\7\\\\pwsh.exe" -Command \'Get-Content -Path "C:/Users/Administrator/.codex/skills/.system/using-superpowers/SKILL.md"\' in D:\\CodeWorkspace\\multi-agent',
                "Exit code: 1",
                "Output:",
                "Cannot find path 'C:\\Users\\Administrator\\.codex\\skills\\.system\\using-superpowers\\SKILL.md' because it does not exist.",
                "exec",
                '"C:\\\\Program Files\\\\PowerShell\\\\7\\\\pwsh.exe" -Command \'Get-Content -Path "D:/CodeWorkspace/multi-agent/README.md"\' in D:\\CodeWorkspace\\multi-agent',
                "succeeded in 17421ms:",
                "# Multi Agent Dev CLI",
                "This README content must not be shown.",
                "exec",
                '"C:\\\\Program Files\\\\PowerShell\\\\7\\\\pwsh.exe" -Command \'git status --short\' in D:\\CodeWorkspace\\multi-agent',
                "succeeded in 23504ms:",
                " M apps/desktop/electron/main.cjs"
              ].join("\n")
            });
        });
      },
      commandExists: () => true
    });
    await services.saveCredentialProfile({
      runtime: "codex",
      agentId: "codex_reviewer",
      profileName: "primary",
      baseUrl: "https://api.openai.com/v1",
      apiKey: "sk-test-key",
      model: "gpt-5-codex"
    });
    const session = await services.createSession({
      title: "Stream run",
      activeAgent: "codex_reviewer"
    });

    await services.runTask({
      sessionId: session.id,
      task: "failure task",
      agent: "codex_reviewer",
      roleId: "worker"
    });

    finishRun();
    await waitFor(() => services.loadSession(session.id), (loaded) => {
      return loaded.messages[1].status === "failed";
    });
    const completed = await services.loadSession(session.id);
    assert.doesNotMatch(completed.messages[1].content, /运行失败/);
    assert.doesNotMatch(completed.messages[1].content, /stderr\.txt/);
    assert.doesNotMatch(completed.messages[1].content, /错误摘要/);
    assert.match(completed.messages[1].content, /读取 Skill：using-superpowers/);
    assert.match(completed.messages[1].content, /读取文件：D:\/CodeWorkspace\/multi-agent\/README\.md/);
    assert.match(completed.messages[1].content, /执行命令：git status --short/);
    assert.match(completed.messages[1].content, /Cannot find path/);
    assert.doesNotMatch(completed.messages[1].content, /This README content must not be shown/);
    assert.doesNotMatch(completed.messages[1].content, /Multi Agent Dev CLI/);
    assert.doesNotMatch(completed.messages[1].content, /M apps\/desktop\/electron\/main\.cjs/);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

async function waitFor(getValue, predicate) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const value = await getValue();
    if (predicate(value)) {
      return value;
    }
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  throw new Error("condition was not met");
}
