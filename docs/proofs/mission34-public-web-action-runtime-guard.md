# Mission 34 - Public Web Action Runtime Guard

## Result

The public web distribution verifier now consumes the GitHub Action runtime guard. A Pages workflow can no longer pass `verify:web-distribution` only because it has the right broad shape; it must also use the protected Node 24-compatible action majors.

New public web check:

- `github_action_runtime_guard`

The check embeds the guard schema, workflow count, checked action-ref count, and violations in the public web distribution proof output.

`Fluxio Release Proof` now watches this verifier and the action-runtime guard tests/scripts, because release-proof already runs `npm run verify:web-distribution`.

## Validation

- `python -m unittest tests.test_public_web_distribution tests.test_github_action_runtimes`
- `python scripts/verify_public_web_distribution.py`
- `npm run verify:web-distribution`
- `python -m py_compile scripts/verify_public_web_distribution.py scripts/verify_github_action_runtimes.py`
- `git diff --check`
