# Fluxio System Improvement Audit - 2026-05-29

## Current Verified State

- NAS web control room is reachable at `https://sysnology.tail602108.ts.net:47880/control`.
- Authenticated live checks show `52` mission rows, `2` running Hermes missions, `0` queued, `0` blocked, and `44` completed.
- The original fusion mission `mission_f4743514ab` is completed with proof artifacts.
- Current active missions are:
  - `mission_e55b280fee`: legal defensive RF/wireless mapping, Hermes, running.
  - `mission_343715c7a1`: public-data investigation suite, Hermes, running.
- Current system audit score is `19.6/20` versus a T3 Code-style reference average of `16.7/20`.
- Current operator confidence is `92/100`; `6/6` route categories are value-scored, so route trust no longer caps user-facing maturity.
- Current T3 Code benchmark evidence observes `v0.0.24` stable and `v0.0.25-nightly.20260515.295` pre-release from `github.com/pingdotgg/t3code`.
- Red-team escalation advanced again: `10` history rows, latest resistance `100`, pass streak `9`, next attempt budget `29`.

## Bad Parts First

- The system now beats the current T3 Code reference in `7/7` audit categories, but that must remain a live evidence claim. Stale local reports must not override fresher NAS evidence.
- Public distribution remains the main product gap: launcher/package receipts exist, but actual public registry publication or signed installer distribution is still unproven.
- The UI has live data now, but it still feels like a control room built by accretion rather than a simple app. The next design pass should reduce panels, unify mission selection, and make the active mission thread the primary object.
- A mission could previously appear active while the planner loop was idle. That is now patched in the watchdog so the system flags the mismatch instead of making the UI look healthier than reality.
- Notification delivery is better than before, but still not complete. Browser notifications and receipts exist; Telegram or another out-of-band mobile channel remains unconfigured.
- Beginner launch is improved but not finished. Local `fluxio`/`npx`-style entrypoints exist; public registry publishing, signed installer, and first-run hosted onboarding remain unproven.
- Web availability exists, but the next bar is a public release path where a new user can open a link, connect providers, launch a mission, and understand proof without handholding.
- Harness parity should keep being measured by live outcomes and provider-auth proof, not by availability labels. Hermes is the dominant current runtime (`48` rows); OpenClaw has `4` rows.

## T3 Code Comparison Targets

Fluxio must beat the current T3 Code baseline on:

- Lower-friction start: `npx t3`, desktop installers, provider connection, existing-project start.
- Multi-agent orchestration: Claude Code, Codex CLI, OpenCode, Cursor, model/provider switching.
- Worktree and diff flow: branch/worktree isolation, diff review, one-click PR.
- Perceived speed: fast thread switching, lightweight mission list, no heavy first paint.
- Beginner clarity: fewer modes before first successful run.

Fluxio advantages to preserve:

- Durable mission proof and proof digests.
- NAS-first long-running mission continuity.
- Watchdog repair loop and problem registry.
- Route-trust learning from operator-value closeouts.
- Multi-project Builder with context roots, sync state, and progress history.

## Improvement Order

1. Make active mission truth impossible to miss: status, planner loop, latest event age, current sub-agent lane, next repair action.
2. Promote route trust only through live value-scored missions. Do not raise category scores from static claims.
3. Finish the phone/tablet notification story: browser notifications first, Telegram or another out-of-band channel second.
4. Simplify Builder into a multi-project queue and launch surface, not a mixed dashboard.
5. Simplify Agent into a live thread plus trace/proof rail, not several competing panels.
6. Make Skills beginner-visible: what skill exists, where it came from, current score, system loss, and next repair.
7. Make Workbench artifact-first: if a preview URL does not exist, say exactly which artifact contract is missing.
8. Publish beginner launch proof: packaged entrypoint, first-run tutorial, and a verified browser/mobile path.

## Patch From This Audit

- Fixed system-audit evidence ordering: an older local low-value route-trust closeout is now retained as history but cannot downgrade a fresher synced NAS operator-proven audit.
- Added a watchdog issue type for `running_planner_loop_idle`.
- The watchdog now flags a mission whose row says `running` or `launching` while the planner loop is `idle`, `stopped`, or missing and there is no approval gate.
- The repair step tells the operator to resume asynchronously after extending budget if needed.
- The current live Agent and Builder checks still pass against the NAS, including message-click switching and no demo/fallback labels.
