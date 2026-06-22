# Mission 33 - GitHub Action Runtime Guard

## Result

Fluxio now has a lightweight CI guard for GitHub Action majors that are known to produce Node 20 runner warnings when left on stale releases.

Protected action floors:

- `actions/checkout@v5`
- `actions/setup-node@v5`
- `actions/setup-python@v6`
- `actions/upload-artifact@v6`
- `actions/upload-pages-artifact@v5`
- `actions/deploy-pages@v5`

The guard scans workflow `uses:` lines, writes a machine-readable proof artifact, and fails with path/line/action details when a protected action falls below the Node 24-compatible floor.

## Validation

- `python -m unittest tests.test_github_action_runtimes`
- `python scripts/verify_github_action_runtimes.py --output artifacts/mission33-action-runtime-guard/github-action-runtime-guard.json`
- `python -m py_compile scripts/verify_github_action_runtimes.py`
- `git diff --check`

## CI path

`.github/workflows/action-runtime-guard.yml` runs on workflow/script/package changes and uploads `artifacts/github-action-runtime-guard/github-action-runtime-guard.json`.
