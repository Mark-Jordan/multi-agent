const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const root = path.resolve(__dirname, "..");
const vendorDir = path.join(root, "vendor", "python");

function findPython() {
  const candidates = [];

  const paths = (process.env.PATH || "").split(path.delimiter);
  const exts = (process.env.PATHEXT || "").split(path.delimiter).concat([""]);

  for (const dir of paths) {
    for (const name of ["python", "python3"]) {
      for (const ext of exts) {
        const full = path.join(dir, name + ext);
        if (fs.existsSync(full)) {
          try {
            if (fs.statSync(full).isFile()) {
              candidates.push(full);
            }
          } catch (_) {}
        }
      }
    }
  }

  const commonDirs = [
    "D:\\MyApplications\\anaconda3",
    "D:\\MyApplications\\python3",
    "C:\\Python39",
    "C:\\Python310",
    "C:\\Python311",
    "C:\\Python312",
    "C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python",
  ];

  for (const dir of commonDirs) {
    if (!fs.existsSync(dir)) continue;
    const dirCandidates = fs.readdirSync(dir)
      .filter(f => /^python3?\.exe$/i.test(f))
      .map(f => path.join(dir, f));
    for (const c of dirCandidates) {
      if (!candidates.includes(c)) candidates.push(c);
    }
    for (const f of fs.readdirSync(dir)) {
      if (!f.endsWith(".exe")) continue;
      try {
        const fullPath = path.join(dir, f);
        if (fs.statSync(fullPath).isFile() && !candidates.includes(fullPath)) {
          candidates.push(fullPath);
        }
      } catch (_) {}
    }
  }

  for (const candidate of candidates) {
    const result = spawnSync(candidate, ["-c", "import sys; print(sys.executable); print(sys.prefix); print('.'.join(map(str, sys.version_info[:2])))"], {
      encoding: "utf8",
      windowsHide: true,
      timeout: 10000,
    });
    if (result.status === 0 && result.stdout.trim()) {
      const lines = result.stdout.trim().split(/\r?\n/);
      if (lines.length >= 3) {
        return {
          executable: lines[0].trim(),
          prefix: lines[1].trim(),
          versionShort: lines[2].trim(),
        };
      }
    }
  }

  throw new Error(
    "Could not find a working Python installation. Please install Python 3.9+ and try again."
  );
}

function copyDir(src, dest, options = {}) {
  const { filter, excludeDirs } = options;
  if (!fs.existsSync(src)) return;

  fs.mkdirSync(dest, { recursive: true });
  const entries = fs.readdirSync(src);

  for (const entry of entries) {
    const srcPath = path.join(src, entry);
    const destPath = path.join(dest, entry);
    const stat = fs.statSync(srcPath);

    if (stat.isDirectory()) {
      if (excludeDirs && excludeDirs.has(entry)) continue;
      if (filter && !filter(srcPath, true)) continue;
      copyDir(srcPath, destPath, options);
    } else {
      if (filter && !filter(srcPath, false)) continue;
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

function bundlePython(pythonInfo) {
  const prefix = pythonInfo.prefix;
  const exeDir = path.dirname(pythonInfo.executable);
  const versionShort = pythonInfo.versionShort;

  if (fs.existsSync(vendorDir)) {
    fs.rmSync(vendorDir, { recursive: true, force: true });
  }
  fs.mkdirSync(vendorDir, { recursive: true });

  const pythonExe = path.join(exeDir, "python.exe");
  if (fs.existsSync(pythonExe)) {
    fs.copyFileSync(pythonExe, path.join(vendorDir, "python.exe"));
    console.log(`  python.exe copied`);
  }

  const dllPatterns = [
    `python${versionShort}.dll`,
    `python3.dll`,
    "vcruntime140.dll",
    "vcruntime140_1.dll",
  ];
  for (const dll of dllPatterns) {
    const src = path.join(exeDir, dll);
    const alt = path.join(prefix, dll);
    if (fs.existsSync(src)) {
      fs.copyFileSync(src, path.join(vendorDir, dll));
      console.log(`  ${dll} copied`);
    } else if (fs.existsSync(alt)) {
      fs.copyFileSync(alt, path.join(vendorDir, dll));
      console.log(`  ${dll} copied`);
    }
  }

  const libDir = path.join(prefix, "Lib");
  if (fs.existsSync(libDir)) {
    const excludeDirs = new Set([
      "__pycache__",
      "site-packages",
      "test",
      "tests",
      "idlelib",
      "turtledemo",
      "ensurepip",
      "distutils",
      "lib2to3",
      "tkinter",
      "turtledemo",
    ]);

    copyDir(libDir, path.join(vendorDir, "Lib"), { excludeDirs });
    console.log(`  Lib/ copied`);
  }

  const dllsDir = path.join(prefix, "DLLs");
  if (fs.existsSync(dllsDir)) {
    copyDir(dllsDir, path.join(vendorDir, "DLLs"));
    console.log(`  DLLs/ copied`);
  }

  const scriptsDir = path.join(prefix, "Scripts");
  const scriptsDest = path.join(vendorDir, "Scripts");
  fs.mkdirSync(scriptsDest, { recursive: true });
  console.log(`  Scripts/ created`);
}

function main() {
  console.log("Bundling Python for madcli Workbench...\n");

  console.log("Searching for Python installation...");
  const pythonInfo = findPython();
  console.log(`  Found: ${pythonInfo.executable}`);
  console.log(`  Prefix: ${pythonInfo.prefix}`);
  console.log(`  Version: ${pythonInfo.versionShort}\n`);

  bundlePython(pythonInfo);

  console.log(`\nPython ${pythonInfo.versionShort} bundled to vendor/python/`);
  console.log("Ready to run: npm run dist:win");
}

main();
