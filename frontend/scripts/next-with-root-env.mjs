import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import nextEnv from "@next/env";

const { loadEnvConfig } = nextEnv;

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendDir = resolve(__dirname, "..");
const projectRoot = resolve(frontendDir, "..");

loadEnvConfig(projectRoot);

const [, , command = "dev", ...extraArgs] = process.argv;
const nextBin = resolve(
  frontendDir,
  "node_modules",
  ".bin",
  process.platform === "win32" ? "next.cmd" : "next",
);

const args = [command, ...extraArgs];

if (command === "dev" || command === "start") {
  const host = process.env.FRONTEND_HOST?.trim();
  const port = process.env.FRONTEND_PORT?.trim();

  if (host) {
    args.push("-H", host);
  }

  if (port) {
    args.push("-p", port);
  }
}

const child = spawn(nextBin, args, {
  cwd: frontendDir,
  env: process.env,
  stdio: "inherit",
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});

child.on("error", (error) => {
  console.error("[frontend] Failed to start Next.js:", error.message);
  process.exit(1);
});

// test updade