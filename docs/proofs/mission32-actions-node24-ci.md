# Mission 32 - GitHub Actions Node 24 Compatibility

## Result

Fluxio workflows now use Node 24-compatible GitHub Action majors for the actions that were producing Node 20 deprecation warnings in CI:

- `actions/checkout@v5`
- `actions/setup-node@v5`
- `actions/setup-python@v6`
- `actions/upload-artifact@v6`

The workflow Node toolchain remains `node-version: 22`; this change updates the JavaScript runtime used by GitHub Actions themselves, not the app's package runtime.

## Rationale

The latest CI proof emitted GitHub's Node 20 deprecation annotation for `actions/checkout@v4`, `actions/setup-node@v4`, `actions/setup-python@v5`, and `actions/upload-artifact@v4`. GitHub's changelog says Node 20 has reached EOL and runners are moving JavaScript actions to Node 24. Official action release notes document Node 24-compatible majors for `setup-node`, `setup-python`, `checkout`, and `upload-artifact`.

## Verification

- `python -m unittest tests.test_pr_stack_health tests.test_mission_control`
- `python -m py_compile scripts/pr_stack_health.py src/grant_agent/mission_control.py`
- `git diff --check`
- PR and post-merge GitHub workflow runs must confirm the warning is gone on real runners.
