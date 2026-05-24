# Cleanup Checkpoint Report

Date: 2026-05-19
Branch: `refactor/agent-workspace-cleanup-redesign`

## Scope Completed

This checkpoint completed the repository reconnaissance, external UI research, product/UX model, design-system plan, and first conservative implementation slice. It does not claim the full north-star redesign is complete; the repo is large and still has major architecture work remaining.

## Research Summary

References inspected and captured:

- T3 Code
- OpenAI Codex
- Cursor
- Claude Code Desktop
- VS Code Copilot Agents Window
- Replit Agent
- Windsurf Cascade
- Bolt
- Zed Agent Panel
- Blackcrab
- Raycast
- Linear
- Superhuman
- Arc

Main principles extracted:

- Agent status, branch/worktree, model, effort, provider, and permission mode must remain visible during active work.
- Diff review must be a primary surface with changed-file state, hunk/file review, and feedback loops.
- Terminal output capture must be explicit and reliable.
- Long threads need collapse/windowing modes to prevent UI degradation.
- Preview screenshots need target metadata and must show the changed area.
- Rule Sets are core workspace governance, not a buried Settings subsection.

Research docs:

- `docs/ui-research/reference-board.md`
- `docs/ui-research/user-feedback-findings.md`
- `docs/ui-research/screenshots/2026-05-19/`

## Redesign Strategy

The strategy is incremental:

1. Stabilize product model and shared vocabulary.
2. Add semantic design tokens without breaking existing surfaces.
3. Pull domain constants out of the shell monolith.
4. Promote core surfaces, starting with Rule Sets.
5. Later split the monolith by feature only after tests and route contracts are in place.

UX/design docs:

- `docs/product/agent-workspace-ux-model.md`
- `docs/design-system/design-system-plan.md`
- `docs/cleanup/baseline-audit.md`

## Implementation Summary

Files changed:

- `web/src/fluxio/workspaceModel.js`
  - Added a shared workspace model for surfaces, statuses, route roles, model providers, effort options, execution targets, and permission modes.
  - Added `WORKSPACE_SURFACE_IDS` so route validation uses the shared source of truth.
- `web/src/fluxio/FluxioShell.jsx`
  - Imported route/model/execution constants from `workspaceModel.js`.
  - Replaced the hard-coded surface validation array with `WORKSPACE_SURFACE_IDS`.
- `web/src/fluxio/FluxioReferenceShell.jsx`
  - Added Rule Sets as a first-class Home card and sidebar item.
  - Added a dedicated `RuleSetsSurface` backed by existing rule-set state.
  - Renamed the nav label from "Skill Studio" to "Skills" to separate skills from governance.
  - Reduced remaining home-card purple usage for Agent/Images tones.
- `web/src/fluxio/styles.css`
  - Added semantic dark-mode tokens for surfaces, text, borders, statuses, diff colors, radii, and spacing.
- `tests/test_workspace_model_contract.py`
  - Added focused contract coverage for Rule Sets as a core workspace surface and explicit permission modes.
- `tests/test_runtime_visualization_contract.py`
  - Added contract coverage for runtime operations visualization, executable service action routing, and automatic verify metadata.

Follow-up runtime slice:

- Added a Workbench runtime operations panel for runtime/service health, update candidates, auto-verify counts, current/latest versions, and service actions.
- Preserved `autoRunVerify` and `followUp` metadata in `desktop-ui/missionControlModel.js` so automatic update support is visible instead of hidden inside setup data.

## Verification Results

- `npm run frontend:build`: passed.
  - Remaining warning: main bundle is 613.51 kB minified; CSS is 296.85 kB. Code splitting is still needed.
- `python -m pytest tests -q`: passed, `238 passed in 247.94s`.
- `cargo check` in `src-tauri`: passed.
- Browser smoke:
  - Public route loaded with no console errors.
  - Fixture-backed Agent/Builder/Skills/Images/Settings routes loaded with no browser console errors during baseline capture.
  - New Rule Sets route loaded with heading `Rule Sets`, visible `Core policy`, and no browser console errors.
  - Workbench runtime operations route loaded with visible `Runtime operations`, `Automatic verify`, OpenClaw, and Hermes service cards.
  - Workbench runtime screenshot capture timed out in the browser CDP screenshot backend; DOM verification and console checks passed, and the failure is recorded in `after-runtime-workbench-screenshot-failed.txt`.

## Screenshots Captured

Baseline:

- `docs/cleanup/baseline-screenshots/2026-05-19/`

Before/after checkpoint:

- `docs/cleanup/before-after/2026-05-19/after-rule-sets-surface.png`
- `docs/cleanup/before-after/2026-05-19/after-home-core-surfaces.png`
- `docs/cleanup/before-after/2026-05-19/rule-sets-browser-check.json`
- `docs/cleanup/before-after/2026-05-19/runtime-workbench-browser-check.json`
- `docs/cleanup/before-after/2026-05-19/after-runtime-workbench-screenshot-failed.txt`

External research:

- `docs/ui-research/screenshots/2026-05-19/`

## Remaining Risks

- `FluxioShell.jsx` and `styles.css` remain very large and still mix many responsibilities.
- `FluxioReferenceShell.jsx` remains a multi-surface monolith.
- No real JS/TS typecheck, ESLint, or formatter is configured.
- Vite dev `/control` without backend still logs `/api/backend` `ECONNREFUSED` and shows a loading/retry state.
- Rule Sets now have a first-class surface, but the data is still the existing fixture/state model. Backend persistence and rule validation need a dedicated pass.
- Runtime operations are now visualized, but full command execution still depends on live backend mode and configured workspace actions.
- Bundle size warning remains and worsened slightly due to the new surface being included in the same bundle.
- Worktree already had many pre-existing modifications/untracked files before this checkpoint, so no baseline commit was created to avoid mixing unrelated user changes.

## Recommended Next Goal

Phase 4 should split `FluxioReferenceShell.jsx` and `FluxioShell.jsx` along feature boundaries:

- `features/agent`
- `features/builder`
- `features/skills`
- `features/rule-sets`
- `components/workspace`
- `components/ui`

Start with read-only extraction of Rule Sets and navigation because they now have a clear shared model and contract tests.

## 2026-05-20 Runtime Architecture Checkpoint

Self-set goal:

`/goal Split the runtime/workbench UI into clearer feature-owned modules, keep the current visual behavior intact, and verify runtime/update visualization through tests, build, and browser smoke checks.`

Changes:

- Extracted the Workbench runtime operations UI into `web/src/fluxio/RuntimeOperationsPanel.jsx`.
- Moved runtime service filtering, update detection, action enrichment, auto-verify counts, and update-action counts into `deriveRuntimeOperations` in `web/src/fluxio/workspaceModel.js`.
- Updated `FluxioShell.jsx` to use the shared runtime operation derivation instead of inline filtering.
- Updated `FluxioReferenceShell.jsx` to compose the extracted runtime panel.
- Updated runtime visualization contract tests so they protect the new component/model boundary.
- Fixed `scripts/control_route_smoke.mjs` so automatic browser smoke verification accepts both production `/assets/` HTML and Vite dev entrypoints.

Verification:

- `npm run frontend:build`: passed. Remaining warning: main app chunk is still over 500 kB.
- `python -m pytest tests/test_runtime_visualization_contract.py tests/test_workspace_model_contract.py tests/test_desktop_ui_contract.py -q`: passed, `23 passed`.
- `python -m pytest tests -q`: passed, `239 passed in 231.39s`.
- `cargo check` in `src-tauri`: passed.
- `npm run verify:browser -- http://127.0.0.1:1420/control?preview-control=1`: passed after the smoke script was made dev-server aware.
- Browser Workbench smoke passed with visible `Runtime operations`, `Automatic verify`, `Update actions`, OpenClaw, and Hermes, and no console errors.

New screenshot/check artifacts:

- `docs/cleanup/before-after/2026-05-20/runtime-workbench-extracted-panel.png`
- `docs/cleanup/before-after/2026-05-20/runtime-workbench-extracted-panel-check.json`

## 2026-05-20 Visual Verification Repair

Issue found:

- The first Workbench screenshot proof was effectively void. It captured only the header and a mostly empty canvas while the DOM check still passed.
- Root cause: non-Agent surfaces were placed into the first `102px` grid row of `.reference-main`, because those surfaces render `.reference-main-body` directly without the Agent topbar row.
- Impact: Workbench, Home, Settings, and other direct-body surfaces could have content below the visible capture while text-based checks still passed.

Fixes:

- Added a non-flow-sidebar layout guard so direct-body surfaces use `grid-template-rows: minmax(0, 1fr)` and normal full-height scrolling.
- Kept the Workbench-specific compact runtime grid so `Runtime operations`, service health, OpenClaw, Hermes, update counts, and auto-verify indicators are visible in the first viewport.
- Darkened Settings static fields, inputs, selects, read-only fields, and action buttons so Settings no longer falls back to bright white controls inside the dark workstation UI.
- Added `scripts/control_route_visual_smoke.py`, which:
  - uses local Chrome/Chromium/Edge in headless mode,
  - captures a real PNG screenshot,
  - dumps rendered DOM,
  - checks expected rendered text,
  - checks screenshot dimensions and sampled pixel variance to reject blank/void screenshots.

Final verification:

- `python -m pytest tests -q`: passed, `240 passed in 207.56s`.
- `cargo check` in `src-tauri`: passed.
- `npm run frontend:build`: passed.
  - Remaining warning: main app chunk is still over 500 kB; code splitting remains recommended.
- `npm run verify:browser -- http://127.0.0.1:1420/control?preview-control=1`: passed.
- Visual smoke screenshots passed for:
  - Home: `docs/cleanup/before-after/2026-05-20/surface-home.png`
  - Agent: `docs/cleanup/before-after/2026-05-20/surface-agent.png`
  - Builder: `docs/cleanup/before-after/2026-05-20/surface-builder.png`
  - Skills: `docs/cleanup/before-after/2026-05-20/surface-skills.png`
  - Rule Sets: `docs/cleanup/before-after/2026-05-20/surface-rule-sets.png`
  - Settings: `docs/cleanup/before-after/2026-05-20/surface-settings.png`
  - Workbench runtime: `docs/cleanup/before-after/2026-05-20/runtime-workbench-visual-proof.png`

Workbench visual proof:

- `docs/cleanup/before-after/2026-05-20/runtime-workbench-visual-proof-check.json`
- Width: `1440`
- Height: `1200`
- Sampled unique colors: `726`
- Required fragments present: `Runtime operations`, `Automatic verify`, `OpenClaw`, `Hermes`
- Result: passed, non-blank, runtime panel visible in the screenshot.

## 2026-05-20 Full Verification Loop

Goal:

`/goal Build a non-void verification loop for the workspace: inventory every touched area, document runtime/browser/OpenCode integration sources, add one repeatable command that verifies tests, build, browser HTML smoke, and visual screenshot smoke, then run it and fix any failures.`

Changes:

- Added `npm run verify:control`.
- Added `scripts/verify_control_workspace.py` as the canonical verification loop.
- Extended `scripts/control_route_visual_smoke.py` to support Chrome/Chromium/Edge plus Zen Browser screenshot capture.
- Added `scripts/control_route_interaction_smoke.py` for live Chrome DevTools click verification across Workbench, Rule Sets, Settings, and Home.
- Added `docs/cleanup/touched-files-and-integration-sources.md`.
- Added Zen Browser Workbench visual proof.

Final full loop:

- Command: `npm run verify:control`
- Result: passed
- Report: `docs/cleanup/verification/control-workspace-verify-2026-05-20.json`
- Step count: `15`
- Python library import: passed
- Python tests: `240 passed`
- Rust `cargo check`: passed
- Frontend build: passed with the existing chunk-size warning
- HTML browser smoke: passed
- Live browser click interaction smoke: passed
- Chromium visual smoke: passed for Home, Agent, Builder, Skills, Rule Sets, Settings, and Workbench
- Zen Browser visual smoke: passed for Workbench

Interaction proof:

- `docs/cleanup/before-after/2026-05-20/interaction-smoke-check.json`
- `docs/cleanup/before-after/2026-05-20/interaction-workbench.png`
- `docs/cleanup/before-after/2026-05-20/interaction-rule-sets.png`
- `docs/cleanup/before-after/2026-05-20/interaction-settings.png`
- `docs/cleanup/before-after/2026-05-20/interaction-home.png`

Zen Browser proof:

- `docs/cleanup/before-after/2026-05-20/runtime-workbench-zen-proof.png`
- `docs/cleanup/before-after/2026-05-20/runtime-workbench-zen-proof-check.json`

OpenCode/Zen integration source map:

- `docs/cleanup/touched-files-and-integration-sources.md`
