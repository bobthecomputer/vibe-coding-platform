# Fluxio Operator UI Visual Audit - 2026-06-07

This audit captures the research-backed UI correction for Fluxio Agent Live and Builder/Gantt. It exists because the recurring product failure was not missing data. The failure was misplaced data: proof, runtime, provider, quota, notification, and diagnostic details were being treated as first-class UI beside the actual operator task.

Companion research comparison:

- `C:\Users\paul\Projects\vibe-coding-platform\docs\OPERATOR_UI_BAD_VS_BEST_RESEARCH_2026-06-08.md`

Completion audit:

- `C:\Users\paul\Projects\vibe-coding-platform\docs\OPERATOR_UI_GOAL_COMPLETION_AUDIT_2026-06-08.md`

## Working Principle

One sentence target:

> Fluxio should let a human operator see the active mission, continue or modify it, inspect real dialogue, and verify proof without interpreting a wall of logs.

First-viewport priority:

1. Primary canvas: Agent dialogue, Gantt/timeline, queue, launcher, review, or artifact.
2. Immediate controls: continue, modify, launch, verify, summarize, Agent/thread.
3. Compact proof state.
4. Secondary state: notifications, provider route, queue counts.
5. Diagnostics and raw receipts.

If levels 3-5 visually dominate level 1, the screen is wrong.

## Source Patterns

| Reference | What It Teaches | Fluxio Translation |
| --- | --- | --- |
| OpenAI Codex app | Agent work is organized by project threads. Users delegate, supervise, review changes, comment, and continue long-running tasks. | Agent Live must be thread-first. Runtime/proof data supports the thread; it is not the thread. |
| OpenAI Codex product page | Codex is positioned as a command center for parallel agentic coding with worktrees, cloud environments, and team-aligned skills. | Fluxio should make parallel missions understandable through clear surfaces: Builder for mission rows, Agent for conversation, Workbench for proof/artifacts. |
| Linear Timeline | Timeline is high-level project planning; granular issues stay out of the planning canvas. | Builder/Gantt rows should be missions/projects, not checkpoint logs or provider receipts. |
| Linear Display Options | Mature planning views expose layout, grouping, ordering, visible properties, completed visibility, and zoom controls. | Fluxio should eventually add density/zoom/display controls near the Gantt rather than adding more dashboard cards. |
| Asana Gantt/Timeline | Gantt is for durations, dates, dependencies, baselines, and stakeholder alignment. | Bars, markers, dependencies, blockers, and status chips belong in the timeline. Paragraphs and receipts belong in detail. |
| Jira Timeline | Timelines plan work, track progress, and map dependencies through parent/child work and bars. | Mission rows can show parent/queue relation, but the visual unit remains a row plus bar, not a prose card. |
| Progressive disclosure | Show the current-step controls first; reveal advanced options on demand. | Proof is required, but raw proof should be in Details, drawers, Workbench, or selected evidence views. |

## Bad Pattern Diagnosis

| Surface | Bad Fluxio Symptom | Best-App Pattern | Required Change |
| --- | --- | --- | --- |
| Agent Live | Provider admission, proof brief, selected report, notifications, progress, preview, evidence rail, and diagnostics competed with dialogue. | Codex-style thread: real user/operator/agent conversation is central; proof/diffs/terminal output are supporting surfaces. | Hide secondary panels in Agent focus. Main area becomes mission controls, live dialogue, and composer. |
| Agent Live messages | Checkpoints, lane-control rows, dispatch text, and runtime output could look like messages. | Agent thread contains conversational turns only. | Promote only real operator follow-ups and explicit Hermes replies. Keep proof/runtime activity out of chat. |
| Builder/Gantt desktop | Timeline existed but risked being surrounded by dashboard/proof clutter. | Timeline should be the dominant planning canvas. | Keep focus mode timeline-first and fold diagnostics/proof panels. |
| Builder/Gantt phone | Row chips and dependency labels overflowed or clipped, and desktop grid pushed bars off-row. | Mobile timeline should show current item, one state, bar/progress, and next action. | Use one-column mobile rows, one visible state chip, hidden row detail/action noise, and full-width in-row bars. |
| Verification pressure | Verifier strings encouraged visible explanatory panels. | Mature apps keep proof available without turning proof into the product canvas. | Preserve DOM/data hooks, but hide or fold explanatory UI in focus modes. |

## Evidence Screenshots

Agent Live before and after:

- Before real-dialogue cleanup: `C:\Users\paul\Projects\vibe-coding-platform\tmp-ui-checks\agent-live-hermes-dialogue-20260607\agent-live-hermes-dialogue-desktop.png`
- After Agent focus cleanup, desktop: `C:\Users\paul\Projects\vibe-coding-platform\tmp-ui-checks\agent-live-focus-nas-20260607-final2\desktop.png`
- After Agent focus cleanup, phone: `C:\Users\paul\Projects\vibe-coding-platform\tmp-ui-checks\agent-live-focus-nas-20260607-final2\phone.png`
- Final Agent Live v2 NAS desktop: `C:\Users\paul\Projects\vibe-coding-platform\tmp-ui-checks\agent-live-v2-final-nas-20260607\desktop.png`
- Final Agent Live v2 NAS phone: `C:\Users\paul\Projects\vibe-coding-platform\tmp-ui-checks\agent-live-v2-final-nas-20260607\phone.png`
- Final authenticated Agent verifier report: `C:\Users\paul\Projects\vibe-coding-platform\tmp-ui-checks\authenticated-live-agent\authenticated-live-agent-check.json`

Builder/Gantt before and after:

- Before Gantt mobile cleanup, desktop: `C:\Users\paul\Projects\vibe-coding-platform\tmp-ui-checks\builder-gantt-before-20260607\desktop.png`
- Before Gantt mobile cleanup, phone: `C:\Users\paul\Projects\vibe-coding-platform\tmp-ui-checks\builder-gantt-before-20260607\phone.png`
- After Gantt mobile cleanup, desktop: `C:\Users\paul\Projects\vibe-coding-platform\tmp-ui-checks\builder-gantt-final-20260607\desktop.png`
- After Gantt mobile cleanup, phone: `C:\Users\paul\Projects\vibe-coding-platform\tmp-ui-checks\builder-gantt-final-20260607\phone.png`

## Applied Rules

Agent Live:

- Real dialogue first.
- Continue, modify, launch, verify, summarize, and composer stay adjacent to the thread.
- Agent Live v2 default order is transcript, compact mission controls, composer. The command band must not sit above the transcript like a dashboard card.
- Phone controls may compress or scroll horizontally; they must not push the composer out of reach.
- Provider admission, quota explanation, notifications, progress, proof brief, selected report, preview, evidence rail, lane board, and plan diagnostics stay out of focus mode unless they are the requested object.
- Hermes dialogue must be a conversational reply, not a lane receipt, dispatch message, proof digest, numbered checklist, file path, or raw runtime output.
- Verifiers that need lane controls, proof readers, notifications, or diagnostics should switch to Details. They should not force those panels back into the Live first viewport.

Builder/Gantt:

- Gantt rows represent missions/projects by default.
- Left lane is readable label/status; right lane is schedule/progress.
- Bars carry timing/progress; prose does not sit over bars.
- Desktop may show richer state chips; phone gets one state chip per row.
- Phone rows prioritize lane, title, state, bar, and compact meta.
- Details and actions remain available, but row-level prose and action pills are hidden on phone to avoid clipping.

## Verification Evidence

Focused checks run during this pass:

- `python -m pytest tests/test_desktop_ui_contract.py -q --tb=short`
- `npm run frontend:build`
- NAS deploy to active release: `/volume1/Saclay/projects/syntelos/releases/20260505-212517`
- NAS `/health` check returned OK after deploys.

Final Builder phone screenshot metrics:

- viewport width: `390`
- document width: `390`
- timeline rows: `5`
- visible state chips: `5` from `15` total
- first row bar inside row: `true`

Final Agent Live screenshot metrics:

- final v2 viewport width: `390` phone, `1440` desktop
- final v2 document width: `390` phone, `1440` desktop
- live NAS mission: `mission_6ade06ff56`
- transcript rows: `1`
- first visible speaker: `Hermes`
- runtime/checkpoint rows in visible transcript: `0`
- proof visible in Live: `false`
- notification rail visible in Live: `false`
- phone mission controls height after compression: `71px`
- composer visible: `true`
- `npm run verify:authenticated-live-agent`: passed after verifier switched diagnostics checks into Details mode

## Remaining Product Gaps

These are not blockers to the current cleanup, but they remain before the broader goal can be called complete:

- Builder Gantt still needs explicit zoom/display controls near the chart: week/month/quarter/year, density, completed visibility, and grouping.
- Builder row dates are represented by phase labels rather than real calendar dates; if mission scheduling data exists, bars should map to actual start/target/proof windows.
- Agent Details mode passed the live Agent verifier for proof/diagnostics/lane controls, but still deserves a human visual review as a separate details surface.
- Full authenticated verifier suite beyond Agent has not been rerun end-to-end after every visual change in this sequence.
- The local skill was updated and validated, but the project should continue using it for future Agent, Builder, Workbench, Phone, and launch surfaces.

## Non-Negotiable Rule Going Forward

Before editing Fluxio UI, write this sentence:

> The current screen fails because ______ dominates, but the human's primary object should be ______.

Then compare against Codex, Linear, Asana/Jira, and progressive disclosure patterns. Only after that should code change.
