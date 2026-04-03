import { defineConfig } from 'vite';
import { resolve } from 'node:path';

const host = process.env.TAURI_DEV_HOST || '127.0.0.1';
const port = Number(process.env.TAURI_DEV_PORT || '1420');

export default defineConfig({
  root: resolve(process.cwd(), 'desktop-ui'),
  server: {
    host,
    port,
    strictPort: true,
    hmr: {
      protocol: 'ws',
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
    outDir: resolve(process.cwd(), 'desktop-ui', 'dist'),
    emptyOutDir: true,
  },
});
