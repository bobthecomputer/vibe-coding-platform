# Baseline Audit - Agent Workspace Cleanup

Date: 2026-05-19
Branch: `refactor/agent-workspace-cleanup-redesign`

## Current Stack

- App type: Tauri 2 desktop app with a Vite web frontend and a Python local backend/harness.
- Frontend: React 19, Vite 7, Tailwind CSS 4 via `@tailwindcss/vite`.
- Desktop shell: Rust/Tauri in `src-tauri/`.
- Backend/runtime harness: Python package `grant_agent` in `src/grant_agent/`.
- Package manager: npm (`package-lock.json` present). `node_modules` is present, so no install was run.
- Routing: no formal router. `FluxioApp.tsx` switches between public page, login, and `/control` shell by pathname. `FluxioShell.jsx` then uses query params/local storage for mode and surface.
- State management: React local state plus localStorage persistence. Backend data is fetched through Tauri commands or `/api/backend`.
- Styling: one very large global stylesheet at `web/src/fluxio/styles.css`.
- Tests: Python `pytest` suite. Frontend has fixture-backed contract tests in Python, but no declared frontend unit test runner.
- Lint/typecheck: no `lint`, `typecheck`, `tsconfig.json`, ESLint config, or Prettier config found.
- Deployment: Vercel config exists for web serving; Tauri config builds frontend before desktop packaging.

## Commands Run

- `git switch -c refactor/agent-workspace-cleanup-redesign`: passed.
- `npm run frontend:build`: passed in 17.09s. Warning: `assets/index-*.js` is 603.83 kB minified and CSS is 294.44 kB.
- `python -m pytest tests -q`: first run timed out at 124s; rerun with 600s timeout passed, `231 passed in 198.26s`.
- `cargo check` in `src-tauri`: passed in 35.03s.
- `npm run frontend:dev`: first `Start-Process npm` failed on Windows with `%1 n'est pas une application Win32 valide`; retry with `npm.cmd` started Vite on `http://127.0.0.1:1420/`.
- Browser smoke: public route and fixture-backed control surfaces loaded with no browser console errors. `/control` without a valid fixture/backend falls into "Loading live control-room state" and Vite logs `/api/backend` `ECONNREFUSED` when backend port 47880 is not running.

## Current Routes and Screens

- `/`: public product page with marketing copy, roadmap preview, and synthetic app preview.
- `/control?preview-control=1&fixture=first_run&mode=agent&surface=agent`: fixture-backed first-run Agent state.
- `/control?preview-control=1&fixture=live_review&mode=agent&surface=agent`: fixture-backed running Agent state.
- `/control?preview-control=1&fixture=verification_failure&mode=agent&surface=agent`: fixture-backed failed/blocked-ish Agent state.
- `/control?preview-control=1&fixture=approval_resumed&mode=agent&surface=agent`: fixture-backed approval/resume state.
- `/control?preview-control=1&fixture=live_review&mode=builder&surface=builder`: Builder overview/detail.
- `/control?preview-control=1&fixture=live_review&mode=builder&surface=skills`: Skill Studio with embedded Rule Sets.
- `/control?preview-control=1&fixture=live_review&mode=builder&surface=images`: Image workbench.
- `/control?preview-control=1&fixture=live_review&mode=builder&surface=settings`: Settings.
- `/control?preview-control=1&fixture=live_review&mode=builder&surface=workbench`: Home/workbench picker. In current behavior `surface=home` and `surface=workbench` render the same picker.

## Component Tree Map

- `web/src/main.tsx`
  - imports global `web/src/fluxio/styles.css`
  - renders `FluxioApp`
- `web/src/fluxio/FluxioApp.tsx`
  - `PublicProductPage`
  - `LiveReviewWorkbench`
  - `GrandAgentLogin`
  - `FluxioErrorBoundary`
  - `FluxioShellApp`
- `web/src/fluxio/FluxioShell.jsx`
  - imports legacy `desktop-ui` helpers/primitives/model builder
  - owns most application state, backend calls, forms, chat sessions, storage, surface switching, command dispatch, and render composition
  - delegates larger redesigned surfaces to `FluxioReferenceShell`
- `web/src/fluxio/FluxioReferenceShell.jsx`
  - contains redesigned Agent, Builder, Skill Hub, Settings, Workbench, and preview surfaces
  - currently a second large monolith rather than feature folders
- `web/src/fluxio/ImagePlayground.jsx`
  - image artifact surface backed by `imagePlaygroundState.js` and `imageProviderAdapters.js`
- `desktop-ui/*`
  - legacy helper/model primitive layer still imported by the web app
- `src/grant_agent/*`
  - mission store, runtime supervisor, workspace actions, web backend, provider/auth state, skill library, verification
- `src-tauri/src/lib.rs`
  - Tauri command bridge into mission/workspace operations

## Main Data and State Flows

- Tauri mode calls Rust commands through `@tauri-apps/api/core.invoke`.
- Browser/web mode posts command names and payloads to `/api/backend`, proxied by Vite to `127.0.0.1:47880`.
- `get_control_room_snapshot_command` produces the core snapshot used by `buildMissionControlModel`.
- Fixture mode uses `desktop-ui/fixtures.js` when `preview-control=1` and `fixture` is one of `live_review`, `first_run`, `verification_failure`, `approval_resumed`, or `long_run_resumed`.
- UI mode/surface/chat/session options are persisted through many localStorage keys in `FluxioShell.jsx`.
- Image workbench persists its project state through `imagePlaygroundState.js`.

## Broken or Suspicious Areas

- `/control` tries live backend by default in Vite dev and fails into a loading/retry state if `npm run web:backend` is not running.
- Fixture IDs are not discoverable in the UI; invalid fixture query params silently return to live mode and can look like a broken shell.
- Rule Sets are present inside Skill Studio, not a first-class global surface.
- Settings contains "Rules & Routing", which risks burying execution policy even though permissions are central to agent trust.
- `FluxioShell.jsx` is 15,849 lines and mixes domain constants, storage, data fetching, reducers, rendering, and event handling.
- `FluxioReferenceShell.jsx` is 5,340 lines and contains many separate screens in one file.
- `styles.css` is 17,047 lines and mixes public marketing, shell layout, reference shell, drawer, image workbench, and state styling.
- `FluxioApp.tsx` public page still reads like a landing page, while the product north star is a workstation-first agent shell.
- Several route/surface states show synthetic/fixture data. Some labels are product-like but not clearly marked as fixture/dev when browsing the shell.
- Two frontend roots exist: `web/src/fluxio` and `desktop-ui`. The active app imports from both, so ownership boundaries are unclear.
- `tmp-ui-checks/`, `.tmp-*` screenshots/logs, and generated artifact folders are present in the worktree and make repo scans noisy.
- There is no JS/TS typecheck gate despite TypeScript files.
- There is no frontend lint/format gate.

## Duplicated Components and Styles

- `desktop-ui/MissionControlPrimitives.jsx` overlaps with custom components inside `FluxioShell.jsx` and `FluxioReferenceShell.jsx`.
- Status tone logic appears in `desktop-ui/fluxioHelpers.js`, `desktop-ui/missionControlModel.js`, and local UI render branches.
- Model/provider/effort/route options are defined directly in `FluxioShell.jsx`.
- Sidebar/nav/surface concepts are encoded in render logic rather than a single navigation model.
- Button, pill, drawer-card, settings-card, and metric-card styling appears as global class families instead of tokenized primitives.

## Obvious UX Issues

- Agent status is visible, but too much status competes at once: topbar, sidebar, mission header, drawers, and runtime compartments all speak at similar weight.
- Agent idle state exposes a large amount of configuration immediately. It needs a cleaner pre-chat flow with model, effort, rule set, workspace, and execution mode summarized in one compact control band.
- Agent running state is denser and closer to the target, but the user still has to parse multiple panes to answer "what is happening now?"
- Builder shows useful status and timeline structure, but it feels subordinate to the Agent shell rather than a durable project overview.
- Skill Studio includes both skills and rule sets; the distinction is underdeveloped.
- Rule Sets are not elevated as a core workspace feature.
- Error states exist, but live backend failure reads as "loading live control-room state" before it reads as "backend unavailable".
- Visual system is dark and premium-ish, but the palette mixes warm gold, green, slate, and many custom local choices. The system lacks a small semantic token set.
- Typography and spacing vary across public page, shell, reference shell, and image workbench.
- Public route is still marketing-first; the core workstation should be the first mental model.

## Build and Test Failures

- Full pytest failed only because the first timeout was too short. With 600s, it passed.
- Dev server start failed once because Windows needs `npm.cmd` for `Start-Process`.
- Vite dev logs backend proxy errors when `/api/backend` is requested without `npm run web:backend`.
- Vite build warns about bundle size.

## Screenshot Inventory

Baseline screenshots are in `docs/cleanup/baseline-screenshots/2026-05-19/`:

- `public-home.png`
- `control-agent-idle.png` (invalid fixture/backend-loading state)
- `control-agent-running.png` (invalid fixture/backend-loading state)
- `control-builder-overview.png` (invalid fixture/backend-loading state)
- `control-settings.png` (invalid fixture/backend-loading state)
- `agent-first-run-empty.png`
- `agent-live-review-running.png`
- `agent-verification-failure.png`
- `agent-approval-resumed.png`
- `builder-live-review.png`
- `settings-live-review.png`
- `skills-live-review.png`
- `images-live-review.png`
- `workbench-live-review.png`
- `home-live-review.png`

