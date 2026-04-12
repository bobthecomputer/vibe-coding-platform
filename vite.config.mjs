import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { resolve } from "node:path";

const host = process.env.TAURI_DEV_HOST || "127.0.0.1";
const port = Number(process.env.TAURI_DEV_PORT || "1420");
const repoRoot = process.cwd();
const webRoot = resolve(repoRoot, "t3code", "apps", "web");
const webSrc = resolve(webRoot, "src");

function manualChunks(id) {
  if (!id.includes("node_modules")) {
    return undefined;
  }
  if (id.includes("react-dom") || id.includes(`${resolve(repoRoot, "node_modules", "react")}`)) {
    return "react-core";
  }
  if (id.includes("@base-ui")) {
    return "base-ui";
  }
  if (id.includes("lucide-react")) {
    return "icons";
  }
  if (id.includes("@tauri-apps")) {
    return "tauri";
  }
  if (id.includes("effect") || id.includes("class-variance-authority") || id.includes("tailwind-merge")) {
    return "fluxio-utils";
  }
  return "vendor";
}

export default defineConfig({
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
    rollupOptions: {
      output: {
        manualChunks,
      },
    },
  },
});
