#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const launcher = resolve(packageRoot, "scripts", "launch_fluxio.py");
const pythonCandidates = [
  process.env.PYTHON,
  process.platform === "win32" ? "python" : "python3",
  "python",
].filter(Boolean);

if (!existsSync(launcher)) {
  console.error(`Fluxio launcher is missing: ${launcher}`);
  process.exit(1);
}

let lastError = "";
for (const python of pythonCandidates) {
  const result = spawnSync(python, [launcher, ...process.argv.slice(2)], {
    cwd: packageRoot,
    stdio: "inherit",
    env: process.env,
  });
  if (result.error) {
    lastError = result.error.message;
    continue;
  }
  process.exit(result.status ?? 0);
}

console.error(`Fluxio could not find a working Python executable. ${lastError}`);
process.exit(1);
