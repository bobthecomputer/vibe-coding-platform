# Mission 11 - Update Management Readiness

## What Changed

- Added `get_update_management_readiness_command` / `update_management_readiness_command` to the web backend.
- Added a Settings > Updates surface with one live `Capture update proof` action.
- The contract is Hermes-first, keeps OpenClaw/OpenCode as fallback runtime lanes, and checks update readiness for app dependencies, provider/model definitions, runtime adapters, web/app shell, and release proof workflow.
- The surface is read-only by design: it does not update packages or providers automatically.

## Runtime Proof

- Command result: `artifacts/mission11-update-management/update-management-readiness-command-result.json`
- Durable artifact: `.agent_control/update_management_readiness/mission11-local-proof.json`
- Schema: `fluxio.update_management_readiness.v1`
- Primary lane: `hermes`
- Fallback lanes: `openclaw`, `opencode`
- Local status: `ready_for_safe_update_window`

## UI Proof

- Before: `artifacts/mission11-update-management/before-settings-team.png`
- After: `artifacts/mission11-update-management/after-settings-updates.png`
- After DOM: `artifacts/mission11-update-management/after-settings-updates.html`
- After check: `artifacts/mission11-update-management/after-settings-updates-check.json`

## Verification

- `python -m pytest tests/test_web_backend.py::FluxioWebBackendTests::test_update_management_readiness_command_writes_safe_update_contract tests/test_desktop_ui_contract.py::DesktopUiContractTests::test_settings_surface_exposes_update_management_readiness -q`
- `python -m pytest tests/test_web_backend.py tests/test_desktop_ui_contract.py tests/test_fluxio_harness.py -q`
- `npm run frontend:build`
- `git diff --check`

## Note

An extra live Playwright click proof was attempted against the Vite app and local web backend, but the live browser navigation hung before exposing a readable body. The mission proof therefore relies on the deterministic backend command artifact plus the rendered Settings screenshot and source-level UI contract tests.
