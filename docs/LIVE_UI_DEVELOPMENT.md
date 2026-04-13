# Live UI Development

Fluxio's desktop frontend now uses the official Tauri `devUrl` development flow with a real Vite dev server.

What this means in practice:

- editing `t3code/apps/web/src/**/*` updates the running desktop app through Vite HMR + React Fast Refresh
- editing some structural files still triggers a full page reload instead of state-preserving replacement
- this is the correct Tauri development model for a desktop app backed by a frontend dev server
- control-room mission state now refreshes on desktop-emitted change events, with live-sync polling kept as a fallback instead of the primary mechanism
- mission and delegated-runtime JSONL events are also pushed into the desktop UI as deltas so the activity feed and delegated lane can patch immediately before the next full snapshot refresh

Important distinction:

- `HMR` means the browser or webview can replace changed modules without restarting the whole Tauri app
- `Fast Refresh` is a framework-specific experience layered on top of HMR, most commonly in React
- Fluxio now uses a React entrypoint in `t3code/apps/web/src/main.tsx`, so Fast Refresh is active for most component edits

Official references:

- Tauri develop docs: <https://v2.tauri.app/develop/>
- Tauri config reference (`beforeDevCommand`, `devUrl`): <https://tauri.app/es/reference/config/>
- Tauri frontend guide for Vite: <https://v2.tauri.app/start/frontend/vite/>
- Vite HMR docs: <https://vite.dev/guide/features.html#hot-module-replacement>

## Current local setup

- `package.json`
  - `npm run frontend:dev` starts Vite
  - `npm run frontend:build` builds the desktop frontend bundle
- `src-tauri/tauri.conf.json`
  - `beforeDevCommand` runs the Vite dev server
  - `devUrl` points the Tauri window at the live dev server
  - `frontendDist` points packaged builds to `t3code/apps/web/dist`
- `t3code/apps/web/index.html`
  - mounts the React workbench root
- `t3code/apps/web/src/main.tsx`
  - bootstraps `FluxioApp` and imports shared desktop styles
- `desktop-ui/FluxioDesktop.jsx`
  - remains the shared workbench implementation consumed by `t3code/apps/web`

## Operator review loop

For product review, use this sequence:

1. Run `npm run tauri:dev`
2. Leave `Preview` on `Live Backend` when validating real mission state
3. Switch `Preview` to a fixture when reviewing UI states without mutating backend data
4. Use `Live Sync` for real supervision, or turn it off during visual design work

The app now pauses polling when the window is backgrounded, then refreshes when it becomes visible again. That keeps the review loop live without wasting work while the desktop window is hidden.
The top bar also shows whether the current feed is coming from push events, fallback polling, or fixture review.

For control-room data, "fully live" still has an engineering limit:

- UI code edits can update immediately through HMR
- backend mission state can refresh as soon as Fluxio detects file-backed state changes and emits a desktop event
- a true zero-latency system would require every runtime and planner path to publish native structured events directly into the desktop app, not only persisted state transitions

This repo is now on the right path: push first, polling second.
