# Touched Files and Integration Sources

Date: 2026-05-20
Branch: `refactor/agent-workspace-cleanup-redesign`

## Goal

`/goal Build a non-void verification loop for the workspace: inventory every touched area, document runtime/browser/OpenCode integration sources, add one repeatable command that verifies tests, build, browser HTML smoke, and visual screenshot smoke, then run it and fix any failures.`

## Files Touched in This Verification Slice

- `package.json`
  - Added `npm run verify:control`.
- `scripts/control_route_smoke.mjs`
  - Earlier fixed the HTML smoke so it accepts both Vite dev entrypoints and production `/assets/` output.
- `scripts/control_route_visual_smoke.py`
  - Added screenshot-based smoke testing.
  - Checks expected rendered DOM fragments when Chromium is used.
  - Checks image dimensions and sampled color variance so blank screenshots do not pass.
  - Supports Chrome/Chromium/Edge and Zen Browser screenshot capture.
- `scripts/verify_control_workspace.py`
  - Added the full verification loop: Python library import, Python tests, Rust check, frontend build, dev-server probe, HTML smoke, Chromium visual smoke, and Zen Workbench smoke when Zen is installed.
- `scripts/control_route_interaction_smoke.py`
  - Added live Chrome DevTools Protocol interaction proof.
  - Clicks Workbench, Rule Sets, Settings, and Home in the rendered app.
  - Verifies expected visible text after each click.
  - Captures screenshots from the same interacted browser session.
- `web/src/fluxio/styles.css`
  - Fixed direct-body surface layout so Home, Builder, Skills, Rule Sets, Settings, and Workbench are not trapped in the old `102px` top grid row.
  - Tightened dark Settings controls and static fields.
  - Kept Workbench runtime operations visible in the first viewport.
- `tests/test_runtime_visualization_contract.py`
  - Added contract coverage for the extracted runtime panel and layout guard.
- `docs/cleanup/final-report.md`
  - Added visual verification repair and final verification results.
- `docs/cleanup/verification/control-workspace-verify-2026-05-20.json`
  - Machine-readable output from `npm run verify:control`.
- `docs/cleanup/before-after/2026-05-20/`
  - Current screenshots and check JSON for Home, Agent, Builder, Skills, Rule Sets, Settings, Chromium Workbench, and Zen Workbench.

## Existing Dirty Worktree Areas

The worktree still includes many pre-existing modified and untracked files outside this slice. I did not revert them. Notable dirty areas include:

- `desktop-ui/*`
- `src/grant_agent/*`
- `src-tauri/src/lib.rs`
- existing tests under `tests/*`
- `web/src/fluxio/FluxioApp.tsx`
- `web/src/fluxio/fluxioBridge.ts`
- generated logs such as `.tmp-control-frontend.*.log`
- generated docs and screenshot artifacts under `docs/cleanup/`, `docs/design-system/`, `docs/product/`, and `docs/ui-research/`

Before committing, review `git status --short` and decide whether to split this branch into commits by concern.

## Verification Loop

Canonical command:

```powershell
npm run verify:control
```

Current result:

- Passed: `true`
- Report: `docs/cleanup/verification/control-workspace-verify-2026-05-20.json`
- Step count: `14`
- Step count: `15`
- Python library import: passed
- Python tests: `240 passed`
- Rust `cargo check`: passed
- Frontend build: passed
- Browser HTML smoke: passed
- Chromium visual smoke: passed for Home, Agent, Builder, Skills, Rule Sets, Settings, and Workbench
- Zen visual smoke: passed for Workbench
- Live click interaction smoke: passed for Workbench, Rule Sets, Settings, and Home

Known remaining warning:

- Vite still warns that the main app chunk is over `500 kB`; route-level code splitting remains the next architecture task.

## Browser Verification Notes

Chromium/Chrome is the strict browser verification backend because it supports both screenshot capture and rendered DOM dump from the CLI. Zen Browser is also installed locally at:

```text
C:\Program Files\Zen Browser\zen.exe
```

Zen Browser can capture the Workbench screenshot in headless mode, but it does not provide the same CLI DOM dump path used by Chromium. Therefore:

- Chromium check = screenshot + rendered DOM fragments + non-blank pixel checks.
- Zen check = screenshot + non-blank pixel checks.

Zen artifact:

- `docs/cleanup/before-after/2026-05-20/runtime-workbench-zen-proof.png`
- `docs/cleanup/before-after/2026-05-20/runtime-workbench-zen-proof-check.json`

## OpenCode Integration Sources

Primary sources inspected:

- OpenCode GitHub repository: `https://github.com/opencode-ai/opencode`
- OpenCode MCP server docs: `https://opencode.ai/docs/mcp-servers/`
- Zen Browser docs: `https://docs.zen-browser.app/`

Relevant OpenCode facts from the docs:

- OpenCode is a terminal coding agent.
- It supports self-hosted OpenAI-compatible providers with `LOCAL_ENDPOINT`.
- It supports MCP servers through `opencode.json` under `mcp`.
- MCP servers can be local or remote.
- Local MCP servers are configured with `type: "local"` and a `command` array.
- Remote MCP servers are configured with `type: "remote"` and a `url`.
- OAuth-backed remote MCP servers can be authenticated with `opencode mcp auth <server-name>`.
- `opencode mcp list`, `opencode mcp auth list`, and `opencode mcp debug <server-name>` are relevant for connection checks.

## OpenCode Connection Plan

Treat OpenCode as an external agent/runtime lane, not as a UI dependency.

1. Add an adapter boundary under runtime/provider services.
2. Detect OpenCode availability:
   - `opencode --version`
   - config path existence
   - MCP list/auth status when configured
3. Represent OpenCode in the existing runtime operations model:
   - service id: `opencode`
   - category: `runtime`
   - status: healthy, missing, auth-required, config-error
   - actions: install docs, open config, verify MCP, debug MCP auth
4. Surface it in Workbench beside OpenClaw, Hermes, WSL2, and image tools.
5. Do not enable broad write/command permissions automatically. Route OpenCode through the Rule Sets permission model.
6. Add a visual smoke route with fixture data showing OpenCode connected, auth-required, and failed states.

## Sources To Recheck Before Implementation

OpenCode and Zen Browser are active projects. Before implementing the adapter, re-check:

- OpenCode current config schema.
- OpenCode CLI command names for MCP auth/list/debug.
- Whether OpenCode exposes a stable machine-readable status output.
- Whether Zen Browser adds a better automation/debugging interface than the headless screenshot path.
