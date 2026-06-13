const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const repoRoot = path.resolve(root, "..", "..");
const electronDist = path.join(root, "node_modules", "electron", "dist");
const releaseDir = path.join(root, "release", "madcli-workbench-win-x64");
const appDir = path.join(releaseDir, "resources", "app");
const resourcesDir = path.join(releaseDir, "resources");
const vendorPythonDir = path.join(root, "vendor", "python");

function ensureExists(target, label) {
  if (!fs.existsSync(target)) {
    throw new Error(`${label} not found: ${target}`);
  }
}

function copyIntoApp(relativePath) {
  fs.cpSync(path.join(root, relativePath), path.join(appDir, relativePath), {
    recursive: true
  });
}

function copyRepoPathIntoApp(relativePath) {
  fs.cpSync(path.join(repoRoot, relativePath), path.join(appDir, relativePath), {
    recursive: true,
    filter: (source) => {
      const name = path.basename(source);
      return name !== "__pycache__" && !name.endsWith(".pyc");
    }
  });
}

ensureExists(electronDist, "Electron runtime");
ensureExists(path.join(root, "dist", "index.html"), "Vite build output");
ensureExists(path.join(repoRoot, "madcli", "cli.py"), "madcli Python package");

fs.rmSync(releaseDir, { force: true, recursive: true });
fs.mkdirSync(appDir, { recursive: true });
fs.cpSync(electronDist, releaseDir, { recursive: true });

const electronExe = path.join(releaseDir, "electron.exe");
const appExe = path.join(releaseDir, "madcli-workbench.exe");
ensureExists(electronExe, "Electron executable");
fs.renameSync(electronExe, appExe);

copyIntoApp("dist");
copyIntoApp("electron");
copyRepoPathIntoApp("madcli");

if (fs.existsSync(vendorPythonDir)) {
  fs.cpSync(vendorPythonDir, path.join(resourcesDir, "python"), {
    recursive: true
  });
  const bundledPythonCandidates = [
    path.join(resourcesDir, "python", "python.exe"),
    path.join(resourcesDir, "python", "Scripts", "python.exe")
  ];
  if (!bundledPythonCandidates.some((candidate) => fs.existsSync(candidate))) {
    throw new Error(
      `Bundled Python executable not found. Expected one of: ${bundledPythonCandidates.join(", ")}`
    );
  }
  console.log(`Bundled Python detected at ${vendorPythonDir}`);
} else {
  console.warn(
    `Bundled Python not found at ${vendorPythonDir}; attempting auto-bundle...`
  );
  try {
    const bundleScript = path.join(root, "scripts", "bundle-python.cjs");
    const { spawnSync } = require("child_process");
    const result = spawnSync(
      process.execPath,
      [bundleScript],
      {
        stdio: "inherit",
        windowsHide: true,
        timeout: 60000,
      }
    );
    if (result.status === 0 && fs.existsSync(vendorPythonDir)) {
      fs.cpSync(vendorPythonDir, path.join(resourcesDir, "python"), {
        recursive: true
      });
      console.log(`Auto-bundled Python to ${vendorPythonDir}`);
    } else {
      console.warn(
        "Auto-bundle failed or timed out; packaged app will fall back to system Python."
      );
    }
  } catch (_err) {
    console.warn(
      `Auto-bundle error: ${_err.message}; packaged app will fall back to system Python.`
    );
  }
}

fs.writeFileSync(
  path.join(appDir, "package.json"),
  JSON.stringify(
    {
      name: "madcli-desktop",
      version: "0.1.0",
      main: "electron/main.cjs"
    },
    null,
    2
  ) + "\n",
  "utf8"
);

console.log(`Windows app created: ${appExe}`);
