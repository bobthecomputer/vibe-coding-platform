import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { resolve } from "node:path";

const host = process.env.TAURI_DEV_HOST || "127.0.0.1";
const port = Number(process.env.TAURI_DEV_PORT || "1420");
const backendTarget = process.env.FLUXIO_WEB_BACKEND_URL || "http://127.0.0.1:47880";
const repoRoot = process.cwd();
const webRoot = resolve(repoRoot, "web");
const webSrc = resolve(webRoot, "src");

function manualVendorChunks(id) {
  if (!id.includes("node_modules")) {
    return undefined;
  }
  if (id.includes("node_modules/react") || id.includes("node_modules/scheduler")) {
    return "vendor-react";
  }
  if (id.includes("node_modules/react-dom")) {
    return "vendor-react-dom";
  }
  if (id.includes("node_modules/@tauri-apps")) {
    return "vendor-tauri";
  }
  if (
    id.includes("node_modules/lucide-react") ||
    id.includes("node_modules/@phosphor-icons")
  ) {
    return "vendor-icons";
  }
  if (
    id.includes("node_modules/effect") ||
    id.includes("node_modules/class-variance-authority") ||
    id.includes("node_modules/tailwind-merge")
  ) {
    return "vendor-utils";
  }
  return "vendor";
}

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
    proxy: {
      "/api": backendTarget,
      "/health": backendTarget,
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
        manualChunks: manualVendorChunks,
      },
    },
  },
}));
