# PR Stack Audit - 2026-06-21

## Decision

Close and supersede the open PR stack instead of merging it.

The audited set contained 109 open PRs, from #3 through #112. They are not independent changes. They form one stacked chain where each PR targets the previous branch, ending at:

`codex/112-image-vision-ui-self-repair-loop` -> `codex/111-intent-drift-recovery` -> ... -> `codex/current-shell-proof-workstreams` -> `master`

## Why The Stack Was Not Merged

- The top branch is not based on current `master`, so merging it would pull unrelated compartments together.
- PR112 resurrects obsolete `web/src/fluxio/image-studio/` files while current `master` uses `web/src/fluxio/ImagePlayground.jsx` and related provider/state modules.
- The stack diff against `master` deletes or regresses current live systems, including the current Image Playground and provider adapters.
- PR112's proof is contradictory: its raw fallback output says the selected fallback could not process the screenshot image directly, while the saved proof JSON claims image-read capability.
- The stack contains large generated proof dumps and broad artifact churn mixed with source changes.
- Several good product concepts from the stack are already present on current `master`, including Image Playground, provider adapters, route/proof queues, annotation controls, skill surfaces, voice controls, benchmark/fusion/red-team panels, and runtime proof receipts.

## Salvaged Good Parts

Only the durable skill-contract idea from PR112 was ported:

- `image_vision_breakdown`
- `ui_self_repair_planner`
- `self_repair_verifier`

These were added to `config/skills.json` with stricter truthfulness rules. The image breakdown route must record whether the selected model can actually inspect image pixels. If it cannot, the output must label findings as DOM/code-assisted instead of vision-read.

## Bad Parts Rejected

- Obsolete `web/src/fluxio/image-studio/` implementation.
- Generated HTML/PNG proof dumps as source-controlled product work.
- False or ambiguous proof claims around model image-reading capability.
- The stacked PR structure itself, because it hides unrelated work behind later PRs and makes review/merge safety poor.

## Audit Evidence

Local audit artifacts were generated under:

- `tmp-pr-audit/open-prs.json`
- `tmp-pr-audit/pr-incremental-audit.csv`
- `tmp-pr-audit/PR_STACK_AUDIT.md`

An isolated cherry-pick attempt of PR112 onto `origin/master` was made in:

`C:\Users\paul\Projects\vibe-coding-platform-pr-audit-consolidation`

It conflicted immediately on the obsolete Image Studio subtree and backend/test changes, so the cherry-pick was aborted and the salvage was applied manually as a clean, scoped change.
