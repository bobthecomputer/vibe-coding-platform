# Mission 6 Provider Orchestration Proof

Checked: 2026-06-22 01:34 Europe/Paris

## Route contract

- Command: `get_provider_orchestration_command`
- Local result: `artifacts/mission6-provider-orchestration/provider-orchestration-command-result.json`
- Runtime artifact: `.agent_control/provider_orchestration/mission6-local-proof.json`
- Selected route on this machine: `openrouter / openrouter/z-ai/glm-5.2`
- Selection mode: `auth_required_best_fit`
- Primary runtime lane: `hermes`
- Fallback lanes: `openclaw`, `opencode` at contract level; selected OpenRouter route exposes `openclaw`
- Reason: GLM/Z.AI is the best vision/UI-review match, but OpenRouter auth was not visible locally.

## UI proof

- Screenshot: `artifacts/mission6-provider-orchestration/provider-settings-orchestration.png`
- Browser check JSON: `artifacts/mission6-provider-orchestration/provider-settings-orchestration-check.json`
- DOM capture: `artifacts/mission6-provider-orchestration/provider-settings-orchestration.html`
- Route: `http://127.0.0.1:5182/control?preview-control=1&fixture=live_review&mode=settings&surface=settings&settingsTab=providers`
- Required visible text passed: `Models & Accounts`, `Provider orchestration`, `Capture route proof`, `Hermes is the primary lane`, `OpenCodeGo`

## Checks

- `python -m pytest tests/test_web_backend.py -k "provider_orchestration or provider_secret_presence" -q`
- `python -m pytest tests/test_desktop_ui_contract.py -k "settings_models_accounts_card_opens_real_provider_panel" -q`
- `python scripts/control_route_visual_smoke.py --url "http://127.0.0.1:5182/control?preview-control=1&fixture=live_review&mode=settings&surface=settings&settingsTab=providers" --out-dir "artifacts\mission6-provider-orchestration" --name "provider-settings-orchestration" --width 1440 --height 1100 --expect "Models & Accounts" --expect "Provider orchestration" --expect "Capture route proof" --expect "Hermes is the primary lane" --expect "OpenCodeGo"`
- `python -m pytest tests/test_web_backend.py tests/test_desktop_ui_contract.py -q`
- `npm run frontend:build`
- `git diff --check`
