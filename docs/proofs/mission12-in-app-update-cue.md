# Mission 12 - In-App Update Cue

## Route

- App route: `http://127.0.0.1:5190/control?preview-control=1&fixture=live_review&mode=agent&surface=agent`
- Runtime signal: `fluxio:pwa-status`
- Activation signal: `fluxio:pwa-activate-update`
- Settings action: `app-update:review` opens Settings > Updates.

## Behavior

The PWA registrar no longer auto-activates a waiting service worker as soon as it is discovered. It emits a real `updated` status with `waiting: true`; the Fluxio shell listens for that event and shows one compact update rail with Review, Reload, and Dismiss controls.

The rail is outside the Agent Live top strip because the focused Agent surface intentionally hides the global top strip. This preserves the clean Agent Live layout while keeping app updates visible.

## Proof Artifacts

- Before screenshot: `C:\Users\paul\Projects\vibe-coding-platform-mission1-image-playground\artifacts\mission12-in-app-update-cue\before-agent-no-update-cue.png`
- After screenshot: `C:\Users\paul\Projects\vibe-coding-platform-mission1-image-playground\artifacts\mission12-in-app-update-cue\after-app-update-cue.png`
- Review route screenshot: `C:\Users\paul\Projects\vibe-coding-platform-mission1-image-playground\artifacts\mission12-in-app-update-cue\after-review-opens-settings-updates.png`
- Playwright proof JSON: `C:\Users\paul\Projects\vibe-coding-platform-mission1-image-playground\artifacts\mission12-in-app-update-cue\app-update-cue-playwright-proof.json`

Proof JSON key results:

- `responseStatus`: `200`
- `cueVisible`: `true`
- `cueStatus`: `updated`
- `cueRect`: `720 x 40.9375`
- `beforeHadCue`: `false`
- `afterHasCue`: `true`
- `reviewOpenedUpdates`: `true`

## Checks

- `python -m pytest tests/test_desktop_ui_contract.py::DesktopUiContractTests::test_web_shell_is_installable_pwa_with_offline_fallback tests/test_desktop_ui_contract.py::DesktopUiContractTests::test_fluxio_shell_surfaces_real_app_update_cue -q`
- `python -m pytest tests/test_desktop_ui_contract.py -q`
- `npm run frontend:build`
- `git diff --check`

All checks passed. The Vite production build still reports the existing large-chunk warning for the main app bundle.
