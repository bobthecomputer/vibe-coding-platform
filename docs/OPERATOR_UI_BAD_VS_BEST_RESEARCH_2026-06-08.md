# Operator UI Bad-vs-Best Research - 2026-06-08

This document records the visual/product comparison requested for Fluxio. It is intentionally practical: each source pattern is translated into a rule that prevents the specific Codex failure mode seen in this repo.

Completion audit:

- `C:\Users\paul\Projects\vibe-coding-platform\docs\OPERATOR_UI_GOAL_COMPLETION_AUDIT_2026-06-08.md`

## Current Sources Checked

| Source | Relevant Pattern | Fluxio Rule |
| --- | --- | --- |
| OpenAI Codex product page, `https://openai.com/codex/` checked 2026-06-08 | Codex is described as a command center for agentic coding with parallel work, worktrees, cloud environments, skills, automations, and review quality. | Fluxio should center the current mission/thread/review object and keep secondary proof/route/setup surfaces subordinate. |
| OpenAI Introducing Codex, `https://openai.com/index/introducing-codex/` checked 2026-06-08 | Codex tasks run independently in isolated environments; users monitor progress, review results, request revisions, open PRs, and inspect terminal/test evidence. | Agent and Builder must preserve proof, but proof should support review rather than masquerade as chat or Gantt content. |
| Linear Timeline docs, `https://linear.app/docs/timeline` checked 2026-06-08 | Timeline is explicitly project-level; individual issues are excluded from timeline and belong in list/board layouts. | Builder/Gantt rows should be mission/project-level; checkpoint logs and runtime receipts become drilldown. |
| Atlassian Gantt guide, `https://www.atlassian.com/agile/project-management/gantt-chart` checked 2026-06-08 | Gantt charts combine task list, timeline, dependencies, milestones, progress tracking, and assignees; common mistakes include overcomplication and missing dependencies. | Fluxio Gantt should use schedule/progress geometry and filtered dependency cues instead of prose-heavy row cards. |
| Jira Advanced Roadmaps dependencies, `https://support.atlassian.com/jira-software-cloud/docs/what-are-dependencies-in-advanced-roadmaps/` checked 2026-06-08 | Dependencies appear as connecting lines or numbered badges; off-track dependencies turn red to show risk. | Fluxio should show selected/current first-order dependencies and conflicts, not every true dependency. |
| NN/g Visual Design Principles PDF, `https://media.nngroup.com/media/articles/attachments/Principles_Visual_Design-Letter.pdf` checked 2026-06-08 | Scale, visual hierarchy, balance, contrast, and Gestalt grouping guide attention. | One primary object must dominate the first viewport; proof and diagnostics cannot share equal scale. |
| NN/g Heuristics summary PDF, `https://media.nngroup.com/media/articles/attachments/Heuristic_Summary1_A4_compressed.pdf` checked 2026-06-08 | Visibility of status and user control matter, but every extra unit of irrelevant information competes with relevant information. | Fluxio should keep live status visible while folding rarely needed proof, setup, and diagnostics. |
| OpenAI Codex product page, `https://openai.com/codex/` | Codex is framed as a command center for agentic coding, parallel work, worktrees, skills, and shipping work end to end. | Fluxio should organize agent work into inspectable missions/threads, not dashboards full of backend facts. |
| OpenAI Codex app announcement, `https://openai.com/index/introducing-the-codex-app/` | Codex is a work delegation and continuation surface, with skills and reusable workflows. | Agent Live must make continuation obvious: what happened, what was said, what proof exists, what to do next. |
| OpenAI Codex Academy getting started, `https://openai.com/academy/codex-how-to-start/` | Codex keeps projects/history in the sidebar while the main workspace shows the current thread and chat. | Fluxio Agent should look like a mission thread first, not a control-room report first. |
| OpenAI Codex working guide, `https://openai.com/academy/working-with-codex/` | The sidebar is navigation; the chat window is where the user tells Codex the task and collaborates while it takes action. | Agent Live should separate thread navigation/activity from the actual conversation lane. |
| OpenAI App Server article, `https://openai.com/index/unlocking-the-codex-harness/` | Thread lifecycle, persistence, tool execution, approvals, and event streams are distinct app-server concepts. | Fluxio must render lifecycle/runtime events as activity/proof, not conversation bubbles. |
| OpenAI Codex mobile, `https://openai.com/index/work-with-codex-from-anywhere/` | Mobile continuation exposes live threads, approvals, outputs, screenshots, terminal output, diffs, tests, and model changes while credentials stay on the trusted machine. | Phone Agent should show current mission, real dialogue/next action, and reachable composer; proof surfaces remain support. |
| Linear Timeline, `https://linear.app/docs/timeline/` | Timeline views are project-level planning surfaces. | Builder/Gantt rows should be missions/projects by default, not checkpoint logs or runtime receipts. |
| Linear Display Options, `https://linear.app/docs/display-options` | Mature views expose grouping, ordering, visible properties, and timeline zoom. | Gantt needs display controls near the chart, but these controls should not become a dashboard. |
| Asana Timeline dependencies, `https://help.asana.com/s/article/managing-tasks-and-dependencies-with-timeline` | Dependencies are drawn between tasks; conflicts can be highlighted; timeline zoom changes the planning scale. | Dependencies should be first-order, readable, and conflict-focused. Do not draw every internal relation. |
| Asana project timeline planning, `https://asana.com/id/inside-asana/asana-timeline-plan-projects` | Timeline turns a task list into a visual plan so teams can see how pieces connect and whether the schedule is doable. | Planning geometry must carry the story: bars, dates, dependencies, blockers, milestones. |
| Asana Gantt template, `https://asana.com/templates/gantt-chart` | Gantt views are high-level visual plans for tasks, roles, dependencies, and deadlines. | Fluxio Gantt should resist day-to-day trace granularity; it needs schedule geometry, not prose cards. |
| Asana community dependency complaint, `https://forum.asana.com/t/messy-representation-of-dependencies-in-timeline-or-gantt-views/852432` | Too many dependency lines can make a Gantt unusable. | Fluxio must filter dependencies and avoid line clutter; one useful dependency is better than ten true but unreadable ones. |
| User research docx, `C:\Users\paul\Downloads\Front-End Research Skillpack for Codex.docx` | Trust comes from hierarchy, cognitive-load reduction, state completeness, accessibility, specific recovery language, and motion restraint. | Fluxio work is incomplete if it only looks good in one populated screenshot; loading/empty/error/success/focus/mobile states must be designed. |
| User research docx, `C:\Users\paul\Downloads\Prompt Addendum for Opus Versus Codex.docx` | Separate model capability from wrapper/product UX and tag user feedback by surface/date/confidence. | Fluxio should import scope discipline, uncertainty reporting, validation, and first-pass completeness without confusing those with a particular model brand. |

## Bad Fluxio vs Best-App Comparison

| Area | Bad Fluxio Symptom | Best-App Pattern | Required Fluxio Rule |
| --- | --- | --- | --- |
| Primary object | Screens showed many equal panels: proof, route, notifications, progress, selected reports, lanes, and the actual thread. | Codex-like products keep the thread/task/review object central; supporting proof is available but secondary. | First viewport gets one dominant object: Agent transcript, Gantt, launcher, queue, Workbench proof, or settings. |
| Agent messages | Runtime output, lane receipts, dispatch rows, and checkpoint fragments could read like chat. | Agent products use threads for human/agent dialogue; logs and artifacts are inspection surfaces. | Agent Live transcript contains only real operator/Hermes dialogue or an honest empty state. |
| Agent lifecycle events | The live Agent DOM showed rows such as runtime budget exhausted, resume dispatched, runtime evidence, and lane migration under `Hermes dialogue`. | Codex/App Server separates event streams from thread dialogue; lifecycle events are proof/activity. | `Mission.*`, resume dispatches, runtime-budget notices, exit-code evidence, and lane migrations are explicitly rejected from the Agent dialogue list. |
| Agent controls | Continue/modify/launch/verify/summarize were initially above the conversation as a large control card. | Commands belong beside or immediately after the object they affect. | Agent Live order: mission identity, transcript, compact controls, composer. Details stay behind Details. |
| Proof | Proof walls and verifier text competed with the actual work object. | Mature tools give compact trust markers and drilldown evidence. | Proof is compact in Live and expanded in Details/Workbench/Verify. Verifiers must switch modes instead of forcing proof into Live. |
| Gantt granularity | The UI risked turning checkpoints, proof, and provider state into rows or prose panels around the chart. | Linear/Asana/Jira-style timelines use project/task bars, dates, milestones, and dependencies. | Builder/Gantt rows are mission/project level; logs become row detail or Agent thread. |
| Dependencies | Every true relation can become visible line noise. | Timeline products show dependencies to explain sequence and conflicts, not as decoration. | Show selected/current first-order dependencies and conflicts by default; hide full graph behind display controls. |
| Mobile | Phone views became narrow desktop dashboards, with controls and cards pushing the composer/detail below reach. | Mobile continuation is current item, state, next action, latest update, approval/proof. | Phone first viewport keeps current object and next action; diagnostics collapse or scroll horizontally. |
| Verification | Passing tests encouraged visible explanatory panels. | Good products separate human hierarchy from machine-readable proof. | Preserve `data-*` hooks and testable details, but keep visible copy minimal. |

## 2026-06-08 Gantt Re-Audit

The current Builder/Gantt screenshot is materially better than the previous card pile, but it still risks reading like a framed status table instead of a finished planning canvas.

Current evidence:

- Authenticated NAS Builder screenshot: `C:\Users\paul\Projects\vibe-coding-platform\tmp-ui-checks\authenticated-live-control\authenticated-live-control.png`
- Source surface: `web/src/fluxio/FluxioReferenceShell.jsx`
- Timeline CSS: `web/src/fluxio/styles.css`

Failure sentence:

> Builder/Gantt is no longer a proof wall, but it still feels slightly table-like because row borders, cramped proof microtext, and equal button weight compete with the timeline bars.

Required correction from research:

- Make the chart canvas feel like the primary product object, not a status card.
- Keep row labels outside bars and let bars carry planning state.
- Preserve actions, but reduce equal visual weight among secondary actions.
- Make the selected/running row clearly active without adding another panel.
- Replace cramped proof residue with a quiet operator dock that is readable at normal zoom.

## Fluxio Screenshot Audit

### Agent Live v2 Final

Evidence:

- Desktop: `C:\Users\paul\Projects\vibe-coding-platform\tmp-ui-checks\agent-live-v2-final-nas-20260607\desktop.png`
- Phone: `C:\Users\paul\Projects\vibe-coding-platform\tmp-ui-checks\agent-live-v2-final-nas-20260607\phone.png`
- Authenticated verifier report: `C:\Users\paul\Projects\vibe-coding-platform\tmp-ui-checks\authenticated-live-agent\authenticated-live-agent-check.json`

What the screenshot now communicates:

> I can read the real Hermes reply and continue this exact mission.

What is proven:

- The visible transcript is a real NAS/Hermes mission row, not fixture text.
- Runtime/checkpoint rows are not promoted into chat.
- Proof and notifications are hidden in Live mode.
- Details mode still exposes proof, notifications, lane controls, and diagnostics for verification.
- Phone keeps transcript, controls, and composer reachable.

Remaining visual risk:

- The desktop transcript can feel visually hollow when there is only one real turn. This is acceptable only if the empty space serves reading focus. If it feels like a blank frame, improve row rhythm, transcript anchoring, or live empty-state guidance before adding cards.

### Agent Live v3 Event-Filter Correction

Evidence from authenticated local DOM after logging in through `http://127.0.0.1:5173/control/?surface=agent`:

- The Agent surface showed `Hermes dialogue`.
- Before the v3 correction, lifecycle rows such as `Mission reached its runtime budget`, `Mission resume was dispatched asynchronously`, `Recorded Hermes runtime evidence`, and route-lane migration notices appeared as selectable dialogue rows.
- After the v3 correction, the DOM showed `No dialogue yet` for the selected mission and the same lifecycle phrases were absent from the visible Agent dialogue snapshot.

What this proves:

- The earlier "real messages only" rule was too permissive because it still allowed `Mission.*` events through when they looked sentence-like.
- The correct product behavior is emptiness over fake conversation. A blank honest thread is better than a polished list of receipts masquerading as Hermes chat.

Screenshot limitation:

- Browser CDP screenshot capture timed out on the Fluxio route, and OS-level capture was blocked by a foreground video window. Because the problem is visual, do not treat the failed screenshots as proof. The DOM evidence is useful for the event-filter contract, but a clean desktop/phone screenshot is still required before claiming visual completion.

### Builder/Gantt

Evidence:

- Desktop final: `C:\Users\paul\Projects\vibe-coding-platform\tmp-ui-checks\builder-gantt-final-20260607\desktop.png`
- Phone final: `C:\Users\paul\Projects\vibe-coding-platform\tmp-ui-checks\builder-gantt-final-20260607\phone.png`

What the screenshot should communicate:

> I can see the active mission, queue pressure, timing/progress, and selected next action on a readable timeline.

Current rule from references:

- Add display controls only if they make the chart clearer: week/month/quarter/year, grouping, completed visibility, density.
- Do not add more summary cards.
- Dependency visualization must be filtered and readable.

## Self-Correction Protocol For Future Codex Work

Before any Fluxio UI edit:

1. Write: `The current screen fails because ____ dominates, but the human's primary object should be ____.`
2. Capture or inspect clean desktop and phone screenshots.
3. Classify visible regions into primary object, immediate controls, compact proof, secondary state, diagnostics.
4. Compare against at least three references from this document or `C:\Users\paul\.codex\skills\codex-operator-ui-research\references\research-baseline.md`.
5. Delete/fold before adding.
6. Preserve verifier evidence with semantic hooks, not visible prose.
7. Capture clean default screenshots separately from action/Details screenshots.

## Hard Rules Extracted

- Agent Live is not a dashboard.
- Builder/Gantt is not a proof wall.
- Workbench is not a fallback iframe.
- Phone is not a narrow desktop.
- Proof is required, but proof is not the primary canvas unless the user opened proof.
- A true detail can still be a bad visible detail.
- A test can prove a contract and still be wrong about hierarchy.
- An event stream is not a conversation. Lifecycle events, runtime receipts, and proof rows must stay out of chat even when they are real and sentence-like.
- A UI is not finished from one good populated state. Loading, empty, error, success, disabled, focus, keyboard, mobile, and reduced-motion states are part of product quality.
