const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const ROOT = path.resolve(__dirname, "..");
const REPO_ROOT = path.resolve(ROOT, "..", "..");
const WATCH_DIR = path.join(REPO_ROOT, "madcli");
const DEBOUNCE_MS = 3000;

let buildTimer = null;
let running = false;

function log(msg) {
  const ts = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  console.log(`[${ts}] ${msg}`);
}

function buildEXE() {
  if (running) return;
  running = true;
  log("检测到变更，开始编译 EXE...");

  const child = spawn("npm", ["run", "dist:win"], {
    cwd: ROOT,
    shell: true,
    stdio: "inherit",
    windowsHide: true,
  });

  child.on("close", (code) => {
    running = false;
    if (code === 0) {
      log(`EXE 编译完成 ✅`);
    } else {
      log(`EXE 编译失败 (exit code: ${code}) ❌`);
    }
  });

  child.on("error", (err) => {
    running = false;
    log(`编译进程错误: ${err.message}`);
  });
}

function onChanged(filePath) {
  const relative = path.relative(REPO_ROOT, filePath);
  log(`变更: ${relative}`);

  clearTimeout(buildTimer);
  buildTimer = setTimeout(buildEXE, DEBOUNCE_MS);
}

function startWatcher(dir) {
  if (!fs.existsSync(dir)) {
    console.error(`Watching directory does not exist: ${dir}`);
    return;
  }

  const watchRecursive = (currentDir) => {
    try {
      const watcher = fs.watch(currentDir, { persistent: true }, (eventType, filename) => {
        if (!filename) return;
        if (filename.endsWith(".pyc") || filename.startsWith(".")) return;
        if (filename === "__pycache__") return;

        const fullPath = path.join(currentDir, filename);
        try {
          const stat = fs.statSync(fullPath);
          if (stat.isDirectory()) {
            watchRecursive(fullPath);
            return;
          }
        } catch (_) {}

        onChanged(fullPath);
      });

      watcher.on("error", () => {});
    } catch (_) {}
  };

  watchRecursive(dir);

  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.isDirectory() && entry.name !== "__pycache__") {
      startWatcher(path.join(dir, entry.name));
    }
  }
}

log(`开始监听: ${WATCH_DIR}`);
log("每次修改 madcli/ 中的 .py 文件，EXE 将自动重新编译");

startWatcher(WATCH_DIR);

process.on("SIGINT", () => {
  log("停止监听");
  process.exit(0);
});
