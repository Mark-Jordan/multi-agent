const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const electronDist = path.join(root, "node_modules", "electron", "dist");
const releaseDir = path.join(root, "release", "madcli-workbench-win-x64");
const appDir = path.join(releaseDir, "resources", "app");

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

ensureExists(electronDist, "Electron runtime");
ensureExists(path.join(root, "dist", "index.html"), "Vite build output");

fs.rmSync(releaseDir, { force: true, recursive: true });
fs.mkdirSync(appDir, { recursive: true });
fs.cpSync(electronDist, releaseDir, { recursive: true });

const electronExe = path.join(releaseDir, "electron.exe");
const appExe = path.join(releaseDir, "madcli-workbench.exe");
ensureExists(electronExe, "Electron executable");
fs.renameSync(electronExe, appExe);

copyIntoApp("dist");
copyIntoApp("electron");
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
