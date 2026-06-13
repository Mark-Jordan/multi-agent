const electron = require("electron");
const { spawn } = require("child_process");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const { app, BrowserWindow, dialog, ipcMain } =
  typeof electron === "object" ? electron : {};
const isDev = process.env.MADCLI_DESKTOP_DEV === "1";
const runtimeCommands = {
  codex: "codex",
  claude_code: "claude",
  opencode: "opencode"
};
const installCommands = {
  codex: ["npm", ["install", "-g", "@openai/codex"]],
  claude_code: ["npm", ["install", "-g", "@anthropic-ai/claude-code"]],
  opencode: ["npm", ["install", "-g", "opencode-ai"]]
};

const excludedDirs = new Set([".git", ".madcli", "node_modules", "__pycache__", ".pytest_cache"]);
const artifactFiles = [
  "metadata.json",
  "events.jsonl",
  "context/user_goal.md",
  "context/agent_context.md",
  "context/engineering_task.md",
  "outputs/command.json",
  "outputs/attempts.json",
  "outputs/stdout.txt",
  "outputs/stderr.txt",
  "outputs/last_message.txt"
];

function createWindow() {
  const window = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1120,
    minHeight: 720,
    title: "madcli Workbench",
    backgroundColor: "#111316",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  if (isDev) {
    window.loadURL("http://127.0.0.1:5173");
    window.webContents.openDevTools({ mode: "detach" });
    return;
  }

  window.loadFile(path.join(__dirname, "..", "dist", "index.html"));
}

function registerIpcHandlers(services) {
  ipcMain.handle("diagnostics:startup", async () => services.getStartupDiagnostics());
  ipcMain.handle("config:saveCredential", async (_event, payload) =>
    services.saveCredentialProfile(payload)
  );
  ipcMain.handle("runtime:install", async (_event, runtimeName) =>
    services.installRuntime(runtimeName)
  );
  ipcMain.handle("sessions:list", async () => services.listSessions());
  ipcMain.handle("sessions:create", async (_event, payload) =>
    services.createSession(payload)
  );
  ipcMain.handle("sessions:load", async (_event, sessionId) =>
    services.loadSession(sessionId)
  );
  ipcMain.handle("sessions:delete", async (_event, sessionId) =>
    services.deleteSession(sessionId)
  );
  ipcMain.handle("project:listFiles", async () => services.listProjectFiles());
  ipcMain.handle("project:readFile", async (_event, relativePath) =>
    services.readProjectFile(relativePath)
  );
  ipcMain.handle("workspace:choose", async () => services.chooseWorkspace());
  ipcMain.handle("settings:get", async () => services.getSettingsState());
  ipcMain.handle("roles:saveTemplate", async (_event, payload) =>
    services.saveRoleTemplate(payload)
  );
  ipcMain.handle("roles:saveAgentRoles", async (_event, payload) =>
    services.saveAgentRoles(payload)
  );
  ipcMain.handle("agents:canRun", async (_event, agentId) =>
    services.canRunAgent(agentId)
  );
  ipcMain.handle("madcli:doctor", async () => services.runDoctor());
  ipcMain.handle("madcli:status", async () => services.runStatus());
  ipcMain.handle("madcli:runTask", async (_event, payload) =>
    services.runTask(payload)
  );
  ipcMain.handle("madcli:runDryRun", async (_event, payload) =>
    services.runDryRun(payload)
  );
  ipcMain.handle("madcli:runWorkflow", async (_event, payload) =>
    services.runWorkflow(payload)
  );
  ipcMain.handle("artifacts:list", async (_event, runId) =>
    services.listArtifacts(runId)
  );
  ipcMain.handle("artifacts:read", async (_event, payload) =>
    services.readArtifact(payload.runId, payload.artifactPath)
  );
}

function getDefaultProjectRoot() {
  if (process.env.MADCLI_PROJECT_ROOT) {
    return path.resolve(process.env.MADCLI_PROJECT_ROOT);
  }
  return findProjectRoot([
    __dirname,
    process.cwd(),
    path.resolve(__dirname, "..", "..", "..")
  ]);
}

function createDesktopServices(options = {}) {
  const appDir = options.appDir || app.getPath("userData");
  const packagedAppRoot = path.resolve(options.appRoot || path.resolve(__dirname, ".."));
  const resourcesRoot = path.resolve(
    options.resourcesRoot || path.resolve(packagedAppRoot, "..")
  );
  const projectRoot = path.resolve(options.projectRoot || getDefaultProjectRoot());
  const runCommand = options.runCommand || runProcess;
  const existsCommand = options.commandExists || commandExists;
  const chooseDirectory = options.chooseDirectory || chooseDirectoryWithDialog;
  const configPath = path.join(appDir, "madcli.config.json");
  const sessionsDir = path.join(appDir, "sessions");
  const pythonExecutable = resolvePythonExecutable(resourcesRoot);

  function readDesktopConfig() {
    let config;
    if (!fs.existsSync(configPath)) {
      config = defaultDesktopConfig(projectRoot);
    } else {
      try {
        config = JSON.parse(fs.readFileSync(configPath, "utf8"));
      } catch (_error) {
        config = defaultDesktopConfig(projectRoot);
      }
    }
    const migration = migrateDesktopConfig(config);
    if (migration.changed) {
      writeDesktopConfig(migration.config);
    }
    return ensureRoleConfig(migration.config);
  }

  function writeDesktopConfig(config) {
    fs.mkdirSync(path.dirname(configPath), { recursive: true });
    fs.writeFileSync(configPath, `${JSON.stringify(config, null, 2)}\n`, "utf8");
  }

  function ensureDesktopConfig() {
    if (!fs.existsSync(configPath)) {
      writeDesktopConfig(defaultDesktopConfig(projectRoot));
    }
  }

  async function runMadcli(args, streamHandlers = {}) {
    ensureDesktopConfig();
    return runCommand(pythonExecutable, ["-m", "madcli", "--config", configPath, ...args], {
      cwd: projectRoot,
      env: {
        ...process.env,
        PYTHONPATH: buildPythonPath(packagedAppRoot, process.env.PYTHONPATH),
        PYTHONUTF8: "1",
        PYTHONIOENCODING: "utf-8"
      },
      ...streamHandlers
    });
  }

  function getWorkspaceRoot() {
    const config = readDesktopConfig();
    const configured = config.default_workdir || projectRoot;
    return path.isAbsolute(configured)
      ? path.resolve(configured)
      : path.resolve(projectRoot, configured);
  }

  function buildDiagnostics() {
    const config = readDesktopConfig();
    const installedRuntimes = Object.entries(runtimeCommands).map(([runtime, command]) => ({
      runtime,
      command,
      installed: existsCommand(command)
    }));
    const hasApiCredentials = ["codex", "claude_code"].some(
      (runtime) => (config.runtimes?.[runtime]?.credentials ?? []).length > 0
    );
    const hasRuntime = installedRuntimes.some((runtime) => runtime.installed);
    const messages = [];
    if (!hasApiCredentials) {
      messages.push("请至少配置一个 Codex 或 Claude Code 模型 API Profile。");
    }
    if (!hasRuntime) {
      messages.push("请至少安装一个编码运行时。");
    }
    return {
      configPath,
      projectRoot,
      workspaceRoot: getWorkspaceRoot(),
      needsModelApiConfig: !hasApiCredentials,
      needsRuntimeInstall: !hasRuntime,
      installedRuntimes,
      messages
    };
  }

  return {
    configPath,
    projectRoot,
    async getStartupDiagnostics() {
      return buildDiagnostics();
    },
    async getSettingsState() {
      const config = readDesktopConfig();
      return {
        configPath,
        projectRoot,
        workspaceRoot: getWorkspaceRoot(),
        config: redactConfigForRenderer(config),
        agents: config.agents ?? {},
        roleTemplates: config.role_templates ?? {},
        agentRoles: config.agent_roles ?? {},
        agentInstances: buildAgentInstances(config),
        credentialsByRuntime: Object.fromEntries(
          Object.entries(config.runtimes ?? {}).map(([runtimeName, runtime]) => [
            runtimeName,
            sanitizeCredentialsForRenderer(runtime.credentials ?? [])
          ])
        ),
        diagnostics: buildDiagnostics()
      };
    },
    async canRunAgent(agentId) {
      const config = readDesktopConfig();
      const agent = config.agents?.[String(agentId)];
      if (!agent) {
        return { ok: false, reason: "unknown_agent" };
      }
      const runtime = config.runtimes?.[agent.runtime];
      if (!runtime) {
        return { ok: false, reason: "unknown_runtime" };
      }
      if (!existsCommand(runtime.command || runtimeCommands[agent.runtime])) {
        return { ok: false, reason: "missing_runtime_install" };
      }
      if (
        ["codex", "claude_code"].includes(agent.runtime) &&
        (runtime.credentials ?? []).length === 0
      ) {
        return { ok: false, reason: "missing_model_api_config" };
      }
      return { ok: true, reason: "" };
    },
    async saveRoleTemplate(payload) {
      const roleId = String(payload.id ?? "").trim() || slugify(String(payload.name ?? ""));
      const name = String(payload.name ?? "").trim();
      const prompt = String(payload.prompt ?? "").trim();
      if (!roleId || !name || !prompt) {
        throw new Error("角色名称和提示词不能为空");
      }
      const config = readDesktopConfig();
      config.role_templates ??= defaultRoleTemplates();
      if (config.role_templates[roleId]?.system) {
        throw new Error("系统默认角色不能修改，请新增自定义角色提示词");
      }
      config.role_templates[roleId] = {
        id: roleId,
        name,
        prompt,
        system: false
      };
      writeDesktopConfig(config);
      return this.getSettingsState();
    },
    async saveAgentRoles(payload) {
      const agentId = String(payload.agentId ?? "").trim();
      const roleIds = Array.isArray(payload.roleIds)
        ? payload.roleIds.map((roleId) => String(roleId)).filter(Boolean)
        : [];
      const config = readDesktopConfig();
      if (!config.agents?.[agentId]) {
        throw new Error(`未知智能体：${agentId}`);
      }
      const validRoleIds = roleIds.filter((roleId) => config.role_templates?.[roleId]);
      if (validRoleIds.length === 0) {
        throw new Error("至少需要为智能体选择一个角色");
      }
      config.agent_roles ??= {};
      config.agent_roles[agentId] = Array.from(new Set(validRoleIds));
      writeDesktopConfig(config);
      return this.getSettingsState();
    },
    async chooseWorkspace() {
      const selectedPath = await chooseDirectory(getWorkspaceRoot());
      if (!selectedPath) {
        return buildDiagnostics();
      }
      const config = readDesktopConfig();
      config.default_workdir = path.resolve(selectedPath).replaceAll("\\", "/");
      writeDesktopConfig(config);
      return buildDiagnostics();
    },
    async saveCredentialProfile(payload) {
      const runtime = String(payload.runtime ?? "");
      const profileName = String(payload.profileName ?? "").trim();
      const baseUrl = String(payload.baseUrl ?? "").trim();
      const apiKey = String(payload.apiKey ?? payload.apiKeyEnv ?? "").trim();
      const model = String(payload.model ?? "").trim();
      const agentId = String(payload.agentId ?? "").trim();
      if (!runtime || !profileName) {
        throw new Error("运行时和 Profile 名称不能为空");
      }
      const config = readDesktopConfig();
      config.runtimes ??= {};
      config.runtimes[runtime] ??= {
        command: runtimeCommands[runtime] ?? runtime,
        credentials: []
      };
      const credentials = config.runtimes[runtime].credentials ?? [];
      const existingProfile = credentials.find((credential) => credential.name === profileName);
      const retainedApiKey = existingProfile?.api_key ? String(existingProfile.api_key) : "";
      if (!baseUrl || (!apiKey && !retainedApiKey)) {
        throw new Error("Base URL 和 API Key 必须成对配置");
      }
      const nextProfile = {
        name: profileName,
        ...(baseUrl ? { base_url: baseUrl } : {}),
        api_key: apiKey || retainedApiKey
      };
      config.runtimes[runtime].credentials = [
        ...credentials.filter((credential) => credential.name !== profileName),
        nextProfile
      ];
      if (agentId && config.agents?.[agentId]) {
        config.agents[agentId].active_credential = profileName;
        if (model) {
          config.agents[agentId].active_model = model;
        }
      }
      writeDesktopConfig(config);
      return this.getStartupDiagnostics();
    },
    async installRuntime(runtimeName) {
      return installRuntime(runtimeName);
    },
    async listSessions() {
      return listStoredSessions(sessionsDir, null);
    },
    async createSession(payload = {}) {
      const title = String(payload.title || "New session").trim() || "New session";
      const activeAgent = String(payload.activeAgent || "codex_reviewer");
      const session = createStoredSession(sessionsDir, {
        title,
        workspace: projectRoot,
        activeAgent
      });
      return formatSessionSummary(session, session.session_id);
    },
    async loadSession(sessionId) {
      return formatSessionDetail(readSession(sessionsDir, String(sessionId)));
    },
    async deleteSession(sessionId) {
      deleteStoredSession(sessionsDir, String(sessionId));
      return this.listSessions();
    },
    async listProjectFiles() {
      return normalizeProjectTree(listProjectTree(getWorkspaceRoot()));
    },
    async readProjectFile(relativePath) {
      const content = readProjectFile(getWorkspaceRoot(), String(relativePath));
      return { path: String(relativePath), content };
    },
    async runDoctor() {
      const result = await runMadcli(["doctor"]);
      return { ...result, title: "诊断" };
    },
    async runStatus() {
      const result = await runMadcli(["status"]);
      return { ...result, title: "运行状态" };
    },
    async runTask(payload = {}) {
      const task = String(payload.task || "").trim();
      const agent = String(payload.agent || "codex_reviewer");
      const sessionId = String(payload.sessionId || "");
      const roleId = String(payload.roleId || "");
      if (!task) {
        throw new Error("task is required");
      }
      const commandArgs = buildRunArgs({
        task,
        agent,
        roleId,
        dryRun: false,
        promptMode: "task",
        getWorkspaceRoot,
        readDesktopConfig
      });
      let statusMessageId = null;
      if (sessionId) {
        appendSessionMessage(sessionsDir, sessionId, {
          role: "user",
          content: task
        });
        statusMessageId = appendSessionMessage(sessionsDir, sessionId, {
          role: "agent",
          content: "",
          agent_name: agent,
          runtime: null,
          run_id: null,
          status: "running"
        });
      }
      let runtimeLog = "";
      const updateRunningSummary = (chunk) => {
        runtimeLog += String(chunk ?? "");
        if (!sessionId || !statusMessageId) {
          return;
        }
        const summary = summarizeRuntimeLog(runtimeLog);
        if (!summary) {
          return;
        }
        updateSessionMessage(sessionsDir, sessionId, statusMessageId, {
          content: summary,
          status: "running"
        });
      };
      void runMadcli(commandArgs, {
        onStdout: updateRunningSummary,
        onStderr: updateRunningSummary
      })
        .then((result) => {
          const runId = parseCliValue(result.stdout, "run_id");
          if (sessionId && statusMessageId) {
            const finalContent =
              result.ok && runId
                ? readRunLastMessage(readDesktopConfig(), projectRoot, runId) ||
                  `运行完成${runId ? `：${runId}` : "。"}`
                : formatFailedRunMessage(runId, result);
            updateSessionMessage(sessionsDir, sessionId, statusMessageId, {
              content: finalContent,
              runtime: parseCliValue(result.stdout, "runtime") || null,
              run_id: runId || null,
              status: result.ok ? "succeeded" : "failed"
            });
          }
        })
        .catch((error) => {
          if (sessionId && statusMessageId) {
            updateSessionMessage(sessionsDir, sessionId, statusMessageId, {
              content: error instanceof Error ? error.message : String(error),
              status: "failed"
            });
          }
        });
      return {
        ok: true,
        code: null,
        stdout: "",
        stderr: "",
        runId: null,
        title: "任务已提交"
      };
    },
    async runDryRun(payload = {}) {
      const task = String(payload.task || "").trim();
      const agent = String(payload.agent || "codex_reviewer");
      const sessionId = String(payload.sessionId || "");
      const roleId = String(payload.roleId || "");
      if (!task) {
        throw new Error("task is required");
      }
      const commandArgs = buildRunArgs({
        task,
        agent,
        roleId,
        dryRun: true,
        getWorkspaceRoot,
        readDesktopConfig
      });
      const result = await runMadcli(commandArgs);
      const runId = parseCliValue(result.stdout, "run_id");
      if (sessionId) {
        appendSessionMessage(sessionsDir, sessionId, {
          role: "user",
          content: task
        });
        appendSessionMessage(sessionsDir, sessionId, {
          role: "agent",
          content: result.ok
            ? `已创建 dry-run${runId ? `：${runId}` : "。"}`
            : result.stderr || result.stdout,
          agent_name: agent,
          runtime: parseCliValue(result.stdout, "runtime"),
          run_id: runId || null,
          status: result.ok ? "dry_run" : "failed"
        });
      }
      return { ...result, runId };
    },
    async runWorkflow(payload = {}) {
      const goal = String(payload.goal || "").trim();
      const plannerAgent = String(payload.plannerAgent || "codex_reviewer").trim();
      const backend = String(payload.backend || "madcli").trim();
      const sessionId = String(payload.sessionId || "");
      if (!goal) {
        throw new Error("goal is required");
      }
      if (!plannerAgent) {
        throw new Error("plannerAgent is required");
      }
      const commandArgs =
        backend === "crewai"
          ? [
              "workflow",
              "run",
              goal,
              "--backend",
              "crewai",
              "--manager-agent",
              plannerAgent
            ]
          : [
              "workflow",
              "run",
              goal,
              "--planner-agent",
              plannerAgent
            ];
      let statusMessageId = null;
      if (sessionId) {
        appendSessionMessage(sessionsDir, sessionId, {
          role: "user",
          content: goal
        });
        statusMessageId = appendSessionMessage(sessionsDir, sessionId, {
          role: "agent",
          content: "自动编排运行中。",
          agent_name: plannerAgent,
          runtime: null,
          run_id: null,
          status: "running"
        });
      }
      void runMadcli(commandArgs)
        .then((result) => {
          const workflowId = parseCliValue(result.stdout, "workflow_id");
          if (sessionId && statusMessageId) {
            updateSessionMessage(sessionsDir, sessionId, statusMessageId, {
              content:
                result.ok && workflowId
                  ? `自动编排完成：${workflowId}`
                  : formatFailedRunMessage(workflowId, result),
              status: result.ok ? "succeeded" : "failed"
            });
          }
        })
        .catch((error) => {
          if (sessionId && statusMessageId) {
            updateSessionMessage(sessionsDir, sessionId, statusMessageId, {
              content: error instanceof Error ? error.message : String(error),
              status: "failed"
            });
          }
        });
      return {
        ok: true,
        code: null,
        stdout: "",
        stderr: "",
        runId: null,
        title: "自动编排已提交"
      };
    },
    async listArtifacts(runId) {
      const runDir = getRunDir(readDesktopConfig(), projectRoot, String(runId));
      return artifactFiles
        .filter((artifactPath) => fs.existsSync(path.join(runDir, artifactPath)))
        .map((artifactPath) => ({ path: artifactPath, name: path.basename(artifactPath) }));
    },
    async readArtifact(runId, artifactPath) {
      const runDir = getRunDir(readDesktopConfig(), projectRoot, String(runId));
      const content = readSafeFile(runDir, String(artifactPath));
      return { path: String(artifactPath), content };
    }
  };
}

function resolvePythonExecutable(resourcesRoot) {
  const candidates = [
    path.join(resourcesRoot, "python", "python.exe"),
    path.join(resourcesRoot, "python", "Scripts", "python.exe")
  ];
  if (process.platform === "win32") {
    const bundledPython = candidates.find((candidate) => fs.existsSync(candidate));
    if (bundledPython) {
      return bundledPython;
    }
  }
  return process.env.MADCLI_PYTHON || "python";
}

function buildPythonPath(packagedAppRoot, existingPythonPath = "") {
  const entries = [packagedAppRoot];
  if (existingPythonPath) {
    entries.push(existingPythonPath);
  }
  return entries.join(path.delimiter);
}

function findProjectRoot(startDirs) {
  const seen = new Set();
  for (const startDir of startDirs) {
    let current = path.resolve(startDir);
    while (!seen.has(current)) {
      seen.add(current);
      if (
        fs.existsSync(path.join(current, "madcli", "cli.py")) &&
        fs.existsSync(path.join(current, "apps", "desktop"))
      ) {
        return current;
      }
      const parent = path.dirname(current);
      if (parent === current) {
        break;
      }
      current = parent;
    }
  }
  return path.resolve(startDirs[0] || process.cwd());
}

function defaultDesktopConfig(projectRoot = ".") {
  return ensureRoleConfig({
    runs_dir: ".madcli/runs",
    default_workdir: projectRoot.replaceAll("\\", "/"),
    runtimes: {
      opencode: { command: "opencode", credentials: [] },
      codex: { command: "codex", credentials: [] },
      claude_code: { command: "claude", credentials: [] }
    },
    agents: {
      strategy_engineer: {
        runtime: "opencode",
        agent: "engineer",
        model: "anthropic/claude-sonnet-4-20250514",
        description: "Implements strategy code using OpenCode."
      },
      codex_reviewer: {
        runtime: "codex",
        agent: "reviewer",
        model: "gpt-5-codex",
        description: "Reviews diffs through Codex."
      },
      claude_engineer: {
        runtime: "claude_code",
        agent: "strategy-engineer",
        model: "sonnet",
        description: "Implements code through Claude Code."
      }
    }
  });
}

function defaultRoleTemplates() {
  return {
    commander: {
      id: "commander",
      name: "Commander",
      system: true,
      prompt:
        "你是 Commander，负责统筹本次工作。先澄清目标、边界和验收标准，再把任务拆成可执行步骤，决定哪些专业角色应当介入，并持续维护关键上下文、约束、风险和决策记录。除非委派没有实际价值，否则不要亲自承担实现细节；你的重点是让多个智能体协同得清晰、可追踪、可验证。"
    },
    worker: {
      id: "worker",
      name: "Worker",
      system: true,
      prompt:
        "你是 Worker，负责完成被分派的实现任务。先阅读相关代码和项目约定，再做最小且完整的一组变更；遵循 KISS、YAGNI、DRY 和现有架构边界。不要扩展未被要求的功能，不做无关重构。完成后明确说明修改内容、影响范围、验证命令和剩余风险。"
    },
    reviewer: {
      id: "reviewer",
      name: "Reviewer",
      system: true,
      prompt:
        "你是 Reviewer，负责以代码评审视角发现问题。优先检查正确性、回归风险、缺失测试、安全与密钥处理、可维护性和用户可见行为变化。输出时先列出具体问题，并关联到文件、行为和可复现条件；如果没有发现问题，也要明确剩余风险、验证缺口和你实际检查过的范围。"
    }
  };
}

function defaultAgentRoles() {
  return {
    strategy_engineer: ["worker"],
    codex_reviewer: ["reviewer"],
    claude_engineer: ["worker"]
  };
}

function ensureRoleConfig(config) {
  const defaultTemplates = defaultRoleTemplates();
  const customTemplates = Object.fromEntries(
    Object.entries(config.role_templates ?? {})
      .filter(([roleId]) => !defaultTemplates[roleId])
      .map(([roleId, role]) => [
        roleId,
        {
          id: String(role.id || roleId),
          name: String(role.name || roleId),
          prompt: String(role.prompt || ""),
          system: false
        }
      ])
  );
  config.role_templates = {
    ...customTemplates,
    ...defaultTemplates
  };
  config.agent_roles = {
    ...defaultAgentRoles(),
    ...(config.agent_roles ?? {})
  };
  for (const agentId of Object.keys(config.agents ?? {})) {
    const roleIds = config.agent_roles[agentId] ?? ["worker"];
    config.agent_roles[agentId] = roleIds.filter((roleId) => config.role_templates[roleId]);
    if (config.agent_roles[agentId].length === 0) {
      config.agent_roles[agentId] = ["worker"];
    }
  }
  return config;
}

function migrateDesktopConfig(config) {
  let changed = false;
  for (const runtime of Object.values(config.runtimes ?? {})) {
    for (const credential of runtime.credentials ?? []) {
      if (
        !credential.api_key &&
        credential.api_key_env &&
        looksLikeApiKey(String(credential.api_key_env))
      ) {
        credential.api_key = credential.api_key_env;
        delete credential.api_key_env;
        changed = true;
      }
    }
  }
  return { config, changed };
}

function looksLikeApiKey(value) {
  const trimmed = String(value ?? "").trim();
  if (!trimmed) {
    return false;
  }
  if (/^sk-[A-Za-z0-9_-]{8,}/.test(trimmed)) {
    return true;
  }
  return trimmed.length >= 32 && /[a-z]/i.test(trimmed) && /\d/.test(trimmed) && !/^[A-Z0-9_]+$/.test(trimmed);
}

function sanitizeCredentialsForRenderer(credentials) {
  return credentials.map((credential) => ({
    name: credential.name,
    base_url: credential.base_url,
    api_key_env: credential.api_key_env,
    api_key_set: Boolean(credential.api_key)
  }));
}

function redactConfigForRenderer(config) {
  const copy = JSON.parse(JSON.stringify(config));
  for (const runtime of Object.values(copy.runtimes ?? {})) {
    runtime.credentials = sanitizeCredentialsForRenderer(runtime.credentials ?? []);
  }
  return copy;
}

function buildAgentInstances(config) {
  const roleTemplates = config.role_templates ?? {};
  return Object.entries(config.agents ?? {}).flatMap(([agentId, agent]) => {
    const roleIds = config.agent_roles?.[agentId] ?? ["worker"];
    return roleIds
      .map((roleId) => roleTemplates[roleId])
      .filter(Boolean)
      .map((role) => ({
        id: `${agentId}:${role.id}`,
        agentId,
        roleId: role.id,
        label: `${agentId} / ${role.name}`,
        runtime: agent.runtime,
        roleName: role.name,
        prompt: role.prompt
      }));
  });
}

function buildRunArgs({
  task,
  agent,
  roleId,
  dryRun,
  promptMode,
  getWorkspaceRoot,
  readDesktopConfig
}) {
  const commandArgs = [
    "run",
    task,
    "--agent",
    agent,
    "--workdir",
    getWorkspaceRoot()
  ];
  if (dryRun) {
    commandArgs.push("--dry-run");
  }
  if (promptMode) {
    commandArgs.push("--prompt-mode", promptMode);
  }
  const role = roleId ? readDesktopConfig().role_templates?.[roleId] : null;
  if (role) {
    commandArgs.push(
      "--context",
      `Role: ${role.name}\n\nRole prompt:\n${role.prompt}`
    );
  }
  return commandArgs;
}

function readRunLastMessage(config, projectRoot, runId) {
  const runDir = getRunDir(config, projectRoot, runId);
  const lastMessagePath = path.join(runDir, "outputs", "last_message.txt");
  if (!fs.existsSync(lastMessagePath)) {
    return "";
  }
  return fs.readFileSync(lastMessagePath, "utf8").trim();
}

function formatFailedRunMessage(runId, result) {
  const summary = summarizeRuntimeLog(`${result.stderr || ""}\n${result.stdout || ""}`);
  return summary || "未完成，未产生可展示的摘要。";
}

function summarizeRuntimeLog(logText) {
  const lines = stripAnsi(String(logText ?? ""))
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const actions = [];
  const errors = [];

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const commandLine = line === "exec" ? lines[index + 1] ?? "" : line.startsWith("exec ") ? line.slice(5) : "";
    if (commandLine) {
      const action = summarizeCommand(commandLine);
      if (action) {
        actions.push(action);
      }
      if (line === "exec") {
        index += 1;
      }
      continue;
    }
    if (isImportantErrorLine(line)) {
      errors.push(cleanLogLine(line));
    }
  }

  const sections = [];
  const uniqueActions = uniqueLimited(actions, 8);
  const uniqueErrors = uniqueLimited(errors, 6);
  if (uniqueActions.length > 0) {
    sections.push(uniqueActions.map((item) => `- ${item}`).join("\n"));
  }
  if (uniqueErrors.length > 0) {
    sections.push(uniqueErrors.map((item) => `- ${item}`).join("\n"));
  }
  return sections.join("\n\n");
}

function summarizeCommand(commandLine) {
  const command = cleanLogLine(commandLine);
  const shellCommand = extractShellCommand(command);
  const target = extractGetContentTarget(shellCommand);
  if (target) {
    const normalizedTarget = target.replaceAll("\\", "/");
    const skillMatch = normalizedTarget.match(/\/skills\/(?:\.system\/)?([^/]+)\/SKILL\.md$/i);
    if (skillMatch) {
      return `读取 Skill：${skillMatch[1]}`;
    }
    return `读取文件：${normalizedTarget}`;
  }
  return `执行命令：${shellCommand || command}`;
}

function extractShellCommand(commandLine) {
  const commandMatch = commandLine.match(/\s-Command\s+(['"])([\s\S]+)\1/i);
  return cleanLogLine(commandMatch ? commandMatch[2] : commandLine);
}

function extractGetContentTarget(command) {
  const match = command.match(/Get-Content(?:\s+-Raw)?(?:\s+-Path)?\s+(['"])([^'"]+)\1/i);
  return match ? match[2] : "";
}

function isImportantErrorLine(line) {
  if (/^(ERROR|Error|Traceback|FileNotFoundError|UnicodeDecodeError|Exception in thread)/.test(line)) {
    return true;
  }
  if (
    /^(CrewAI is not installed|config not found:|run: python -m madcli init|invalid CrewAI workflow:|unknown manager agent:|workflow run requires|dry-run workflows require|CrewAI backend does not support)/i.test(
      line
    )
  ) {
    return true;
  }
  if (/Cannot find path|Exit code:\s*[1-9]\d*|exited\s+[1-9]\d*|timed out/i.test(line)) {
    return true;
  }
  return false;
}

function stripAnsi(value) {
  return value.replace(/\x1B\[[0-?]*[ -/]*[@-~]/g, "");
}

function cleanLogLine(value) {
  return String(value ?? "")
    .replace(/^\[(stdout|stderr|summary)\]\s*/i, "")
    .replace(/\s+/g, " ")
    .trim();
}

function uniqueLimited(items, limit) {
  const seen = new Set();
  const result = [];
  for (const item of items) {
    if (!item || seen.has(item)) {
      continue;
    }
    seen.add(item);
    result.push(item);
    if (result.length >= limit) {
      break;
    }
  }
  return result;
}

function slugify(value) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]+/gi, "-")
    .replace(/^-+|-+$/g, "");
}

function commandExists(command) {
  const checker = process.platform === "win32" ? "where" : "which";
  const result = spawnSync(checker, [command], {
    encoding: "utf8",
    windowsHide: true
  });
  return result.status === 0;
}

async function installRuntime(runtimeName) {
  const runtime = String(runtimeName ?? "");
  const command = installCommands[runtime];
  if (!command) {
    throw new Error(`unsupported runtime: ${runtime}`);
  }
  const response = await dialog.showMessageBox({
    type: "warning",
    buttons: ["安装", "取消"],
    defaultId: 1,
    cancelId: 1,
    title: "安装编码运行时",
    message: `是否全局安装 ${runtime}？`,
    detail: `将执行命令：${command[0]} ${command[1].join(" ")}`
  });
  if (response.response !== 0) {
    return { ok: false, cancelled: true, stdout: "", stderr: "" };
  }
  return runInstallCommand(command[0], command[1]);
}

async function chooseDirectoryWithDialog(defaultPath) {
  const result = await dialog.showOpenDialog({
    title: "选择工作目录",
    defaultPath,
    properties: ["openDirectory"]
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
}

function runProcess(executable, args, options = {}) {
  return new Promise((resolve) => {
    const child = spawn(executable, args, {
      cwd: options.cwd,
      env: options.env,
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      const text = chunk.toString();
      stdout += text;
      options.onStdout?.(text);
    });
    child.stderr.on("data", (chunk) => {
      const text = chunk.toString();
      stderr += text;
      options.onStderr?.(text);
    });
    child.on("close", (code) => {
      resolve({ ok: code === 0, code, stdout, stderr });
    });
    child.on("error", (error) => {
      resolve({ ok: false, code: null, stdout, stderr: `${stderr}${error.message}` });
    });
  });
}

function runInstallCommand(executable, args) {
  return new Promise((resolve) => {
    const child = spawn(executable, args, {
      shell: process.platform === "win32",
      windowsHide: true
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("close", (code) => {
      resolve({ ok: code === 0, cancelled: false, code, stdout, stderr });
    });
    child.on("error", (error) => {
      resolve({
        ok: false,
        cancelled: false,
        code: null,
        stdout,
        stderr: `${stderr}${error.message}`
      });
    });
  });
}

function listStoredSessions(sessionsDir, activeSessionId) {
  if (!fs.existsSync(sessionsDir)) {
    return [];
  }
  return fs
    .readdirSync(sessionsDir)
    .filter((name) => name.endsWith(".json"))
    .map((name) => readSession(sessionsDir, path.basename(name, ".json")))
    .sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)))
    .map((session) => formatSessionSummary(session, activeSessionId));
}

function createStoredSession(sessionsDir, payload) {
  fs.mkdirSync(sessionsDir, { recursive: true });
  const now = new Date().toISOString();
  const session = {
    session_id: `session-${crypto.randomBytes(6).toString("hex")}`,
    title: payload.title,
    workspace: payload.workspace.replaceAll("\\", "/"),
    active_agent: payload.activeAgent,
    created_at: now,
    updated_at: now,
    messages: []
  };
  writeSession(sessionsDir, session);
  return session;
}

function readSession(sessionsDir, sessionId) {
  const sessionPath = path.join(sessionsDir, `${sessionId}.json`);
  return JSON.parse(fs.readFileSync(sessionPath, "utf8"));
}

function deleteStoredSession(sessionsDir, sessionId) {
  const sessionPath = path.join(sessionsDir, `${sessionId}.json`);
  if (fs.existsSync(sessionPath)) {
    fs.unlinkSync(sessionPath);
  }
}

function writeSession(sessionsDir, session) {
  fs.mkdirSync(sessionsDir, { recursive: true });
  fs.writeFileSync(
    path.join(sessionsDir, `${session.session_id}.json`),
    `${JSON.stringify(session, null, 2)}\n`,
    "utf8"
  );
}

function appendSessionMessage(sessionsDir, sessionId, payload) {
  const session = readSession(sessionsDir, sessionId);
  const now = new Date().toISOString();
  const messageId = `message-${crypto.randomBytes(6).toString("hex")}`;
  session.messages.push({
    message_id: messageId,
    role: payload.role,
    content: payload.content,
    created_at: now,
    agent_name: payload.agent_name ?? null,
    runtime: payload.runtime ?? null,
    run_id: payload.run_id ?? null,
    status: payload.status ?? null
  });
  session.updated_at = now;
  writeSession(sessionsDir, session);
  return messageId;
}

function updateSessionMessage(sessionsDir, sessionId, messageId, patch) {
  const session = readSession(sessionsDir, sessionId);
  const now = new Date().toISOString();
  const message = session.messages.find((item) => item.message_id === messageId);
  if (!message) {
    return false;
  }
  if (Object.prototype.hasOwnProperty.call(patch, "content")) {
    message.content = patch.content;
  }
  if (Object.prototype.hasOwnProperty.call(patch, "runtime")) {
    message.runtime = patch.runtime;
  }
  if (Object.prototype.hasOwnProperty.call(patch, "run_id")) {
    message.run_id = patch.run_id;
  }
  if (Object.prototype.hasOwnProperty.call(patch, "status")) {
    message.status = patch.status;
  }
  session.updated_at = now;
  writeSession(sessionsDir, session);
  return true;
}

function appendSessionMessageOutput(sessionsDir, sessionId, messageId, streamName, chunk) {
  const text = String(chunk ?? "");
  if (!text) {
    return false;
  }
  const session = readSession(sessionsDir, sessionId);
  const now = new Date().toISOString();
  const message = session.messages.find((item) => item.message_id === messageId);
  if (!message) {
    return false;
  }
  const label = streamName === "summary" ? "summary" : streamName;
  const existing = String(message.content ?? "");
  const needsSeparator = existing && !existing.endsWith("\n");
  message.content = `${existing}${needsSeparator ? "\n" : ""}[${label}] ${text}`;
  message.status = message.status ?? "running";
  session.updated_at = now;
  writeSession(sessionsDir, session);
  return true;
}

function formatSessionSummary(session, activeSessionId) {
  return {
    id: session.session_id,
    title: session.title,
    agentId: session.active_agent,
    status: session.session_id === activeSessionId ? "active" : "idle",
    updatedAt: session.updated_at,
    messageCount: Array.isArray(session.messages) ? session.messages.length : 0
  };
}

function formatSessionDetail(session) {
  return {
    id: session.session_id,
    title: session.title,
    agentId: session.active_agent,
    status: "active",
    updatedAt: session.updated_at,
    messages: (session.messages ?? []).map((message) => ({
      id: message.message_id,
      role: message.role,
      content: message.content,
      agentId: message.agent_name ?? undefined,
      runtime: message.runtime ?? undefined,
      runId: message.run_id ?? undefined,
      status: message.status ?? undefined
    }))
  };
}

function listProjectTree(projectRoot, maxDepth = 4) {
  const root = path.resolve(projectRoot);
  const rows = [];
  collectTree(root, root, rows, 0, maxDepth);
  return rows;
}

function collectTree(root, current, rows, depth, maxDepth) {
  if (depth >= maxDepth) {
    return;
  }
  for (const name of fs.readdirSync(current).sort((a, b) => a.localeCompare(b))) {
    const absolutePath = path.join(current, name);
    const stats = fs.statSync(absolutePath);
    if (stats.isDirectory() && excludedDirs.has(name)) {
      continue;
    }
    const relative = path.relative(root, absolutePath).replaceAll("\\", "/");
    rows.push({
      path: relative,
      name,
      type: stats.isDirectory() ? "directory" : "file"
    });
    if (stats.isDirectory()) {
      collectTree(root, absolutePath, rows, depth + 1, maxDepth);
    }
  }
}

function normalizeProjectTree(rows) {
  return rows.map((row) => ({
    ...row,
    depth: row.path.split("/").length - 1
  }));
}

function readProjectFile(projectRoot, relativePath) {
  return readSafeFile(projectRoot, relativePath);
}

function readSafeFile(root, relativePath) {
  const resolvedRoot = path.resolve(root);
  const target = path.resolve(resolvedRoot, relativePath);
  const relative = path.relative(resolvedRoot, target);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error(`file is outside root: ${relativePath}`);
  }
  if (!fs.statSync(target).isFile()) {
    throw new Error(`file not found: ${relativePath}`);
  }
  return fs.readFileSync(target, "utf8");
}

function parseCliValue(output, key) {
  const prefix = `${key}:`;
  const line = output
    .split(/\r?\n/)
    .find((candidate) => candidate.toLowerCase().startsWith(prefix));
  return line ? line.slice(prefix.length).trim() : "";
}

function getRunDir(config, projectRoot, runId) {
  const runsDir = config.runs_dir || ".madcli/runs";
  const resolvedRunsDir = path.isAbsolute(runsDir)
    ? runsDir
    : path.resolve(projectRoot, runsDir);
  return path.join(resolvedRunsDir, runId);
}

if (app) {
  app.whenReady().then(() => {
    registerIpcHandlers(createDesktopServices());
    createWindow();
    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
      }
    });
  });

  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") {
      app.quit();
    }
  });
}

module.exports = {
  createDesktopServices,
  defaultDesktopConfig,
  findProjectRoot,
  formatSessionSummary,
  normalizeProjectTree,
  parseCliValue
};
