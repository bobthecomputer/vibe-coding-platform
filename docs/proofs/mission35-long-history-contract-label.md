# Mission 35 - Long-History Contract Label

## Result

The desktop UI contract test now matches the current long-history verifier command. The release-proof path expects the compact proof status text `fixture proof`, which is what `npm run verify:long-history` already uses and what PR132 proved in CI.

This removes a stale contract failure without changing runtime behavior.

The new `Desktop UI Contract` workflow now runs `tests.test_desktop_ui_contract` for future contract, package, desktop UI, and web UI changes.

## Validation

- `python -m unittest tests.test_desktop_ui_contract.DesktopUiContractTests.test_responsive_visual_smoke_covers_phone_tablet_desktop`
- `npm run verify:long-history`
- `git diff --check`
