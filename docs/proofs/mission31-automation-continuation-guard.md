# Mission 31 - Automation Continuation Guard

## Result

PR-stack landing readiness now emits a `continuationPolicy` handoff. When the stack is empty, the report explicitly says `automationDecision=skip_completed_pr_stack`, `shouldContinueStackWork=false`, and instructs the automation to start a fresh mission from current `origin/master`.

The backend also treats an explicit empty runtime payload (`prRows: []`) as real evidence of an empty stack instead of falling through to a GitHub CLI fetch or missing-evidence state.

## Proof

- Local handoff artifact: `artifacts/mission31-continuation-guard/pr-stack-continuation-handoff.json`
- Settings screenshot: `artifacts/mission31-continuation-guard/pr-stack-continuation-settings.png`
- Settings DOM capture: `artifacts/mission31-continuation-guard/pr-stack-continuation-settings.html`
- Settings visual check: `artifacts/mission31-continuation-guard/pr-stack-continuation-settings-check.json`

## Verification

- `python -m pytest tests/test_pr_stack_health.py tests/test_web_backend.py::FluxioWebBackendTests::test_pr_stack_landing_readiness_command_blocks_at_oldest_failed_pr tests/test_web_backend.py::FluxioWebBackendTests::test_pr_stack_landing_readiness_command_accepts_empty_runtime_rows_as_completion tests/test_desktop_ui_contract.py::DesktopUiContractTests::test_settings_updates_surface_exposes_pr_stack_landing_readiness -q` - 9 passed.
- `python scripts/pr_stack_health.py --landing-readiness --output artifacts/mission31-continuation-guard/pr-stack-continuation-handoff.json` - passed with `status=no_open_prs`, primary lane `hermes`, fallback lanes `openclaw` and `opencode`.
- `python -m py_compile scripts/pr_stack_health.py src/grant_agent/web_backend.py` - passed.
- `npm run frontend:build` - passed.
- `VITE_FLUXIO_ALLOW_PREVIEW_FIXTURES=1 npm run frontend:build` - passed for visual fixture proof.
- `python scripts/control_route_visual_smoke.py --url "http://127.0.0.1:5197/control?preview-control=1&fixture=live_review&mode=settings&surface=settings&settingsTab=updates" --out-dir artifacts/mission31-continuation-guard --name pr-stack-continuation-settings --width 1440 --height 1100 --min-width 1200 --min-height 800 --expect "PR landing readiness" --expect "Continuation" --expect "Capture PR proof"` - passed.
- `git diff --check` - passed.
