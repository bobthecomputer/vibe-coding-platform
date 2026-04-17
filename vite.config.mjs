import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { resolve } from "node:path";

const host = process.env.TAURI_DEV_HOST || "127.0.0.1";
const port = Number(process.env.TAURI_DEV_PORT || "1420");
const repoRoot = process.cwd();
const webRoot = resolve(repoRoot, "t3code", "apps", "web");
const webSrc = resolve(webRoot, "src");

export default defineConfig(({ command }) => ({
  // Packaged Tauri builds need relative asset URLs instead of /assets/... .
  base: command === "serve" ? "/" : "./",
  plugins: [react(), tailwindcss()],
  root: webRoot,
  resolve: {
    alias: {
      "~": webSrc,
    },
  },
  server: {
    host,
    port,
    strictPort: true,
    fs: {
      allow: [repoRoot],
    },
    hmr: {
      protocol: "ws",
      host,
      port,
    },
  },
  preview: {
    host,
    port,
    strictPort: true,
  },
  build: {
    outDir: resolve(webRoot, "dist"),
    emptyOutDir: true,
  },
}));
