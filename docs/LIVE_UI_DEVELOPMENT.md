# Live UI Development

Fluxio now runs with a T3-owned shell and style system under `t3code/apps/web/src/fluxio/*`.

## What changed

- `t3code/apps/web/src/fluxio/FluxioShell.jsx` now owns layout, state composition, and mission thread rendering.
- `t3code/apps/web/src/fluxio/FluxioApp.tsx` now wraps the shell in a real error boundary with recoverable diagnostics.
- `t3code/apps/web/src/fluxio/styles.css` now owns the visual system for the shell.
- `desktop-ui/FluxioDesktop.jsx` is now a compatibility wrapper only.
- `desktop-ui/styles.css` now imports the T3 shell stylesheet as a shim.

This removes split ownership between `t3code` and `desktop-ui` for the main app experience.

## Current local setup

- `package.json`
  - `npm run frontend:dev` starts Vite for `t3code/apps/web`
  - `npm run frontend:build` builds `t3code/apps/web/dist`
- `src-tauri/tauri.conf.json`
  - `beforeDevCommand` runs the Vite dev server
  - `devUrl` points Tauri at the live frontend
  - `frontendDist` points packaged builds to `t3code/apps/web/dist`
- `t3code/apps/web/src/main.tsx`
  - mounts `FluxioApp`
  - imports `t3code/apps/web/src/fluxio/styles.css`

## Runtime review loop

1. Run `npm run tauri:dev`.
2. Use `Agent` mode for normal operator supervision.
3. Switch to `Builder` mode and open the Builder drawer to access:
   - fixture selection
   - live-sync cadence
   - feature-truth audit
   - core-state audit
4. Keep `Preview = Live Backend` for real mission validation.
5. Use fixtures only for review states where backend mutation is undesirable.

## Live behavior notes

- Snapshot refresh still supports push events (`control-room://changed`, `control-room://delta`) plus optional polling fallback.
- Polling suspends when the window is hidden and resumes on visibility restore.
- Activity, runtime events, and proof deltas are shown in the mission thread and review drawers.
- Render-time crashes now show a recoverable error panel with failing action context and boot diagnostics.

Official references:

- Tauri develop docs: <https://v2.tauri.app/develop/>
- Tauri config reference: <https://tauri.app/es/reference/config/>
- Tauri + Vite frontend guide: <https://v2.tauri.app/start/frontend/vite/>
- Vite HMR docs: <https://vite.dev/guide/features.html#hot-module-replacement>
