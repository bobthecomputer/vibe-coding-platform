# PR Stack Health

Fluxio uses the PR stack health guard to keep automation work reviewable. It catches the failure mode where many open PRs form one long branch-on-branch chain instead of one finished compartment.

## Local Checks

Run the quick guard before opening or merging automation PRs:

```bash
npm run verify:pr-stack
```

Write a reusable proof artifact when you need evidence for a report or handoff:

```bash
npm run proof:pr-stack
```

The proof script writes `artifacts/pr-stack-health-local/pr-stack-health.json`. A healthy report has `ok=true`, `staleStackDetected=false`, and a `longestChainLength` at or below the configured limit.

For ordered landing work, run the same script with `--landing-readiness`. When all stack PRs are already merged or closed, the readiness report returns `status=no_open_prs` plus `continuationPolicy.automationDecision=skip_completed_pr_stack`. Automations should treat that as a hard handoff: stop reopening PR-stack landing work and start the next fresh compartment from current `origin/master`.

## GitHub Check

The scheduled/manual workflow lives at `.github/workflows/pr-stack-health.yml`. It runs `python -m unittest tests.test_pr_stack_health`, then writes and uploads `artifacts/pr-stack-health/pr-stack-health.json`.

Use the workflow dispatch input `max_chain` only when the team intentionally changes the allowed stack depth. The default limit is `5`.

## If It Fails

Stop opening new broad PRs. Merge, close, or split the current chain until the longest open chain is back under the limit. Preserve branches when recovery might still be useful; close stale PRs with a superseded note instead of deleting evidence.

The intended end state is boring: `gh pr list --state open` should be short, each PR should target the default branch or one clearly necessary base branch, and the guard should report no stale stack.
