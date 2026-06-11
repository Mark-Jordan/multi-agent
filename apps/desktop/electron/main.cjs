const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

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

app.whenReady().then(() => {
  registerIpcHandlers();
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

function registerIpcHandlers() {
  ipcMain.handle("diagnostics:startup", async () => getStartupDiagnostics());
  ipcMain.handle("config:saveCredential", async (_event, payload) =>
    saveCredentialProfile(payload)
  );
  ipcMain.handle("runtime:install", async (_event, runtimeName) =>
    installRuntime(runtimeName)
  );
}

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

function getConfigPath() {
  return path.join(app.getPath("userData"), "madcli.config.json");
}

function readDesktopConfig() {
  const configPath = getConfigPath();
  if (!fs.existsSync(configPath)) {
    return defaultDesktopConfig();
  }
  try {
    return JSON.parse(fs.readFileSync(configPath, "utf8"));
  } catch (_error) {
    return defaultDesktopConfig();
  }
}

function writeDesktopConfig(config) {
  const configPath = getConfigPath();
  fs.mkdirSync(path.dirname(configPath), { recursive: true });
  fs.writeFileSync(configPath, `${JSON.stringify(config, null, 2)}\n`, "utf8");
}

function defaultDesktopConfig() {
  return {
    runs_dir: ".madcli/runs",
    default_workdir: ".",
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
  };
}

function commandExists(command) {
  const checker = process.platform === "win32" ? "where" : "which";
  const result = spawnSync(checker, [command], {
    encoding: "utf8",
    windowsHide: true
  });
  return result.status === 0;
}

function getStartupDiagnostics() {
  const config = readDesktopConfig();
  const installedRuntimes = Object.entries(runtimeCommands).map(([runtime, command]) => ({
    runtime,
    command,
    installed: commandExists(command)
  }));
  const hasApiCredentials = ["codex", "claude_code"].some(
    (runtime) => (config.runtimes?.[runtime]?.credentials ?? []).length > 0
  );
  const hasRuntime = installedRuntimes.some((runtime) => runtime.installed);
  const messages = [];
  if (!hasApiCredentials) {
    messages.push("Configure at least one Codex or Claude API profile.");
  }
  if (!hasRuntime) {
    messages.push("Install at least one coding runtime.");
  }
  return {
    configPath: getConfigPath(),
    needsModelApiConfig: !hasApiCredentials,
    needsRuntimeInstall: !hasRuntime,
    installedRuntimes,
    messages
  };
}

function saveCredentialProfile(payload) {
  const runtime = String(payload.runtime ?? "");
  const profileName = String(payload.profileName ?? "").trim();
  const baseUrl = String(payload.baseUrl ?? "").trim();
  const apiKeyEnv = String(payload.apiKeyEnv ?? "").trim();
  const model = String(payload.model ?? "").trim();
  const agentId = String(payload.agentId ?? "").trim();
  if (!runtime || !profileName || !apiKeyEnv) {
    throw new Error("runtime, profile name, and API key env are required");
  }
  const config = readDesktopConfig();
  config.runtimes ??= {};
  config.runtimes[runtime] ??= {
    command: runtimeCommands[runtime] ?? runtime,
    credentials: []
  };
  const credentials = config.runtimes[runtime].credentials ?? [];
  const nextProfile = {
    name: profileName,
    ...(baseUrl ? { base_url: baseUrl } : {}),
    api_key_env: apiKeyEnv
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
  return getStartupDiagnostics();
}

async function installRuntime(runtimeName) {
  const runtime = String(runtimeName ?? "");
  const command = installCommands[runtime];
  if (!command) {
    throw new Error(`unsupported runtime: ${runtime}`);
  }
  const response = await dialog.showMessageBox({
    type: "warning",
    buttons: ["Install", "Cancel"],
    defaultId: 1,
    cancelId: 1,
    title: "Install coding runtime",
    message: `Install ${runtime} globally?`,
    detail: `This will run: ${command[0]} ${command[1].join(" ")}`
  });
  if (response.response !== 0) {
    return { ok: false, cancelled: true, stdout: "", stderr: "" };
  }
  return runInstallCommand(command[0], command[1]);
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
