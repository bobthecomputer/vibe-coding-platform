# Fluxio System Improvement Analysis - 2026-06-02

## Current Verdict

Fluxio is operational, web-reachable in the latest authenticated browser verification, Hermes-first, and materially stronger than it was yesterday, but it is still not complete. The current authenticated live Builder verifier proves `87% proven · Partial`, not 100%. The remaining blocker is no longer a stale runtime budget: the active Hermes mission has been extended and resumed, and the live runtime transcript is attached. The remaining must-beat blocker is final notification/distribution trust: phone/tablet Web Push still needs a durable browser subscription and delivery receipt from the operator device.

Current strongest evidence:
- Live NAS Builder `/control` verification passed on `2026-06-02T17:55:08.911231Z`.
- Live Agent/Workbench verification passed on `2026-06-02T18:03:54.671630Z`.
- Live phone progress verification passed on `2026-06-02T18:04:18.622750Z`.
- Live Skills/MiniMax-M3 proof verification passed on `2026-06-02T18:21:01.956940Z`.
- Live strict system-loss Builder verification passed on `2026-06-02T18:32:44.559028Z`.
- Live budget-resumed Builder verification passed on `2026-06-02T18:44:12.331618Z`.
- Running mission: `mission_6ade06ff56`, title `Continue the system-loss improvement mission using`, runtime `hermes`, planner loop `running`.
- Live summary counts: `29` missions, `1` active/running, `0` blocked, `26` completed, `24` notifications, `3` slice notifications.
- Runtime counts: all `29` visible mission rows are `hermes`.
- First-viewport objective audit: `87% proven · Partial`.
- First-viewport system gap card: `19.6/20 · gap 0.4/20`, `7/8` T3 categories ahead.
- Storage: writable, `38%` used, no active repair gate.
- Deployment durability: durable release paths, not a `/tmp` recovery.
- Notification controls: dismiss and mark-visible-read are verified.
- Screenshot proof: `.agent_control/screenshots/live-nas-builder-density-20260602.png`.
- Strict score proof screenshot: `.agent_control/screenshots/live-nas-builder-strict-system-loss-20260602.png`.
- Budget-resumed proof screenshot: `.agent_control/screenshots/live-nas-builder-budget-resumed-20260602.png`.
- Agent/Workbench proof screenshot: `.agent_control/screenshots/live-nas-agent-m3-sanitized-live-20260602.png`.
- Phone proof screenshot: `.agent_control/screenshots/live-nas-phone-builder-density-20260602.png`.
- Skills source proof: `.agent_control/screenshots/live-nas-skills-hermes-source-20260602.png`.
- MiniMax provider lane proof: live Builder DOM contains the MiniMax-M3 executor lane and no stale MiniMax-M2.7 frontend routing leakage.
- Hermes/MiniMax-M3 backend proof: authenticated web backend returned a MiniMax-M3 frontend executor review through Hermes; live Builder now shows `Hermes/M3 runtime proof`, Hermes Agent `v0.15.0`, and `MiniMax-M3 verified`.
- Phone/Web Push proof: live summary exposes `fluxio.web_push_status.v1`, `senderConfigured=true`, `dependencyAvailable=true`, `subscriptionCount=0`; phone UI now shows `Sender ready, register this browser` and does not mark closed-tab push ready.
- Phone compactness proof: `.agent_control/screenshots/live-nas-phone-m3-ui-accessible-20260602-check.json` passed with `notificationCardCount=4` and screenshot height `1619`, replacing the earlier 8-card, 2252px-tall phone wall.
- Push registration diagnostic proof: `.agent_control/screenshots/live-nas-phone-webpush-diagnostics-display-20260602-check.json` shows foreground `Notification.permission=granted` and `PushManager.permissionState=granted`, but `PushManager.subscribe` fails with `AbortError: Registration failed - permission denied`; `subscriptionCount=0`, so Fluxio keeps the state as `needs_subscription`.
- Current live audit records active `mission_6ade06ff56` as `running`, `plannerLoopStatus=running`, `remainingRuntimeSeconds=14215`, `maxRuntimeSeconds=43200`, `progressKind=runtime_progress`, `progressLabel=Budget window progress`, and active executor route `minimax / MiniMax-M3`. The latest mission detail sync also shows concrete completed Hermes artifacts for F1 telemetry, RF/wireless mapping, hardware/electrical discovery, and the Builder zero-active-state repair.
- Live notification/Agent text sanitization proof: the latest Builder verifier passed with `staleMiniMaxFrontendModels=[]`; historical follow-up rows that mention an obsolete MiniMax route are now rendered as a legacy route label instead of exposing the stale alias in the operator UI.
- Builder density proof: `.agent_control/screenshots/live-nas-builder-density-20260602.png` passed the authenticated live Builder verifier after the queue-first band was simplified from a squeezed three-column cockpit block into a single-column command strip with two-column metrics and horizontal actions. Screenshot height dropped from `3726` to `3583` pixels while preserving all live data gates.
- Accessible/M3 UI proof: the deployed NAS bundle now marks phone and Agent progress regions with `role=status`/`aria-live=polite`, uses the first meaningful live notification line as the compact phone notification headline, and keeps closed-tab push state at `needs_subscription` until the backend reports a real subscription.
- Builder focus-mode compactness patch is deployed and verified on the NAS. Focus folds lower diagnostics behind `data-builder-focus-disclosure="true"` and the `live-builder-focus-mode-compact` gate passed with screenshot size `1440x3743`.
- Deployed compact Builder bundle: `.agent_control/deploy_bundles/fluxio-builder-focus-20260602-172510.tgz`; manifest: `.agent_control/deploy_bundles/fluxio-builder-focus-20260602-172510.json`.
- NAS reachability recovered after the earlier Tailscale outage: SSH, HTTPS health, deployment, and authenticated live Builder verification succeeded against the active release.
- NAS-local browser proof receipt: `.agent_control/screenshots/nas-local-agent-workbench-proof-diagnostic-20260602-check.json`. Playwright and managed Chromium are now installed under `/volume1/Saclay/projects/syntelos/.playwright-browsers`, but Chromium cannot start on Synology because the host is missing `libatk-1.0.so.0`.
- Latest T3 benchmark refresh passed at `2026-06-02T18:07:24Z`: stable `v0.0.24` published `2026-05-15T06:39:44Z`; nightly `v0.0.25-nightly.20260602.439` published `2026-06-02T08:05:20Z`.
- T3 product page claims verified: open-source control plane, Claude/Codex/OpenCode/Cursor orchestration, BYO subscription, no quota caps, mid-thread model switching, desktop platforms, diff/PR flow.
- MiniMax M3 official page confirms `MiniMax-M3` as an API model with coding/agentic positioning, 1M-token API support, and coding-tool connection guidance.
- Official Codex CLI and MiniMax M3 references were refreshed for routing/design guidance. MiniMax's M3 page positions M3 for coding/agentic work with a 1M context window; the app now exposes MiniMax-M3 as a Hermes frontend executor proof, not as a fake static catalog. The live Skills surface shows whether rows came from the NAS registry, mission-slice feedback, or no live registry.

## Bad Parts First

The UI is still too dense in Full mode, but the default Builder Focus mode is now deployed and verified. Builder is clearer because the live control strip puts mission progress, Agent report, notifications, and watchdog state in one place. The queue-first band no longer squeezes metrics into thin vertical columns; it now reads as one command strip with two-column metrics and a single row of actions. Focus folds full audit, queue, public launch, provider truth, diff, flow-board, and review-bundle diagnostics behind a compact proof drawer, while Full mode preserves the diagnostic surface for debugging.

NAS deployment is no longer blocked. The workstation regained Tailscale/TCP reachability, the active release stayed `/volume1/Saclay/projects/syntelos/releases/20260505-212517`, the backend restarted cleanly, and `/health` returned OK after the verifier contract update.

The active mission is still running, but it is no longer stuck at the old runtime-budget gate. The budget was extended to `43200` seconds and a new Hermes/MiniMax-M3 resume worker `delegate_284e44f4` is running. The product must keep the mission alive until a completion or blocker lands with artifact proof.

NAS-local browser proof is still weaker than workstation browser proof, but the blocker is narrower now. Python Playwright and managed Chromium are installed in the NAS runtime. The current blocker is Synology native browser libraries: the NAS-local verifier records `browser-launch=false`, `nativeDependencyBlocked=true`, and missing library `libatk-1.0.so.0`. Workstation authenticated verification still passes and is valid for UI proof, but truly unattended NAS-local Workbench/browser proof now needs native library support or an external browser runner.

Phone/Web Push proof is clearer but not finished. Telegram, in-app/browser foreground notifications, Web Push sender keys, and the `pywebpush` dependency are now proven. The phone view shows the real setup state and next action, and the compact phone surface now defaults to 4 alert rows instead of a long notification wall. The remaining missing proof is a real browser subscription from the operator's phone/tablet and a delivered Web Push receipt. Until `subscriptionCount > 0` and a real `web_push` delivery receipt exists, web distribution should stay below a perfect score.

The T3 comparison is stronger but must stay honest. The live UI now says `7/8` categories ahead from the automated system audit because Web availability/distribution is capped at parity until a real phone/tablet Web Push subscription receipt exists. The user-facing product still needs cleaner launch, simpler provider setup, and a less bulky interface before it is obviously better than T3 to a beginner.

Some OpenCLAW vocabulary remains in compatibility docs and older historical artifacts. Runtime defaults, visible Beginner launch paths, Builder copy, and live provider/admission surfaces are now Hermes-first. Remaining OpenCLAW mentions should stay limited to explicit compatibility or migration contexts.

## T3 Code Comparison

Latest observed T3 Code evidence:
- Official product page: `https://t3.codes/`.
- Official releases feed source: `https://api.github.com/repos/pingdotgg/t3code/releases?per_page=50`.
- Latest stable: `v0.0.24`, published `2026-05-15T06:39:44Z`.
- Latest nightly: `v0.0.25-nightly.20260602.439`, published `2026-06-02T08:05:20Z`.

| Category | Fluxio /20 | T3 Code /20 | Current state |
| --- | ---: | ---: | --- |
| Launch friction and beginner experience | 20 | 18 | Ahead. Hermes defaults, launcher/package proof, beginner launch proof, and public release proof beat the current T3-style launch benchmark, though install polish still matters. |
| Multi-project Builder operations | 20 | 17 | Ahead. Live dependency-aware queue, queue-first command band, project health, and watchdog pressure rows beat T3's simpler project/worktree view. |
| Harness and sub-agent capability | 20 | 18 | Ahead. Hermes-first supervision, route trust sampling, planner/executor/verifier lanes, and watchdog loops are deeper than T3's current public positioning. |
| Web availability and distribution | 18 | 18 | Parity. NAS web app is live and public-launch evidence exists, but phone/Web Push subscription proof is still incomplete. |
| Proof, verification, and trust | 20 | 14 | Ahead. Mission proof digests, live verifiers, receipt-backed notifications, screenshots, and artifact gates are a major advantage. |
| Speed and long-history performance | 20 | 18 | Ahead. Summary/detail hot paths, long-history gates, lazy proof paging, and release proof are now covered by live performance evidence. |
| Roadmap and self-improvement | 20 | 14 | Ahead. Red-team escalation, system-loss routing, watchdog self-improvement, and route-trust sampling are real differentiators. |
| Interface clarity and operator ergonomics | 20 | 17 | Ahead by the audit, but still the most fragile subjective area. Focus mode, live thread proof, and notification dismissal are proven; Full mode remains bulky. |

Strict target: `8/8` categories above T3. Latest authenticated Builder proof shows `7/8` ahead, with Fluxio `19.6/20` against a T3-style reference average of `16.8/20`; the post-detail audit reports `19.8/20` but keeps the same `7/8` must-beat status. Operator-facing completion should stay below 100% until the active mission completes and Web Push has a real subscribed-device receipt.

## Mission Progress

`mission_6ade06ff56` - continue system-loss improvement mission:
- Status: running.
- Runtime: Hermes.
- Current proof: first-viewport Builder audit sees it as the only active running mission.
- Progress label: `43% · Budget window progress`; the over-budget state was cleared by extending the budget and dispatching a new Hermes/MiniMax-M3 resume worker.
- Current proof payload: hard artifact gate passed with `15` runtime-output evidence items and `19` artifact evidence items.
- Runtime transcript: attached from `/volume1/Saclay/projects/syntelos/releases/20260505-212517/.agent_control/mission_artifacts/mission_6ade06ff56/proof/runtime_output.txt`.
- Current blocker: the mission is actively running and intentionally not marked completed until the new resume worker produces completion or a concrete blocker with artifact proof.

`delegate_7cb24bde` - Hermes delegate for the current mission:
- Status: completed, exit code `0`.
- It recorded live-only NAS audit, T3 benchmark, red-team evidence, and notification receipt evidence.
- It deliberately did not mark the mission completed because NAS-local browser/Workbench dependencies were missing.

F1/data, RF/wireless, public-data, frontend/mobile, and route-trust missions:
- The current audit/Builder proof treats these as completed or represented in the mission history rather than the active blocker.
- The important current product behavior is that completed rows no longer fake progress; the single active row is the system-loss continuation mission.

Red-team/self-improvement:
- Latest live evidence records `status=pass`, resistance `100`, history rows `84`.
- The current visible system-gap driver is still "Red-team difficulty must keep rising." The latest pressure moved `263 -> 269` with the next aggregate plan at `21` attempts.

## Improvement Order

1. Register a real phone/tablet browser Web Push subscription, send a real closed-tab Web Push notification, and archive the delivery receipt.
2. Keep `mission_6ade06ff56` running under Hermes until `delegate_284e44f4` produces completion or a concrete blocker with artifact proof.
3. Fix the remaining NAS-local native browser dependency (`libatk-1.0.so.0` and any follow-on Chromium libraries) or route NAS-local proof through a supported external browser runner.
4. Reduce UI density: first screen should show mission, Agent report, notifications, watchdog, and one next action; lower diagnostics should be drawers/tabs.
5. Make Agent the real thread by default: selected live runtime output first, artifact links second, advanced traces behind disclosure.
6. Keep T3 benchmark refresh and strict user-facing scorecard current.
7. Keep red-team pressure increasing after clean defensive passes.

## Implemented In This Pass

- Refreshed the official T3 Code benchmark evidence.
- Verified NAS backend health and live `/control` state.
- Deployed the MiniMax-M3/Hermes Builder live control strip.
- Patched the backend provider-lane contract so authenticated MiniMax frontend executor lanes normalize legacy `MiniMax-M2.7` aliases to `MiniMax-M3`.
- Added and verified the live Hermes Skills Hub source panel: live NAS registry first, mission-slice feedback second, no static fake catalog in live mode.
- Verified authenticated live Builder with a nonblank screenshot, live mission rows, no demo labels, notification dismiss, and mark-visible-read controls.
- Added a verifier contract for the new `data-live-builder-command-rail` strip so future checks prove the improvement.
- Added a verifier contract for the Hermes Skills source panel.
- Added a verifier contract for the MiniMax-M3 provider lane so stale M2.7 frontend routing fails the live Builder proof.
- Added backend `runtimeRouteProof` and live Builder `Hermes/M3 runtime proof` so MiniMax-M3 is proven by a real authenticated Hermes call, not only a provider badge.
- Added backend `webPushStatus` to the authenticated live summary.
- Added a phone-first closed-tab push proof panel that shows sender state, dependency state, live subscription count, and the exact next action.
- Added phone verifier checks for `summary-web-push-status-live` and `phone-web-push-proof-visible`.
- Compacted the phone/tablet route: default live phone view now shows one status strip, at most 3 mission rows, and 4 notification rows, while retaining full live notification stack access.
- Added Push API permission diagnostics so the UI and verifier separate foreground notification permission from a real backend Web Push subscription.
- Exercised Hermes with `MiniMax-M3` for a frontend executor review; its highest-priority guidance was to gate closed-tab push readiness only on backend `subscriptionCount > 0`, which is now the live behavior.
- Added desktop UI contract coverage for the new Builder live control strip.
- Deployed the compact Builder Focus mode to the NAS active release and verified the authenticated live Builder screenshot is nonblank, live-only, and compact.
- Updated the live verifier so compact queue mode proves the live queue section marker plus the top actionable or held row instead of requiring every queued project label in the first viewport.
- Verified MiniMax-M3 through both current public MiniMax M3 information and the authenticated Hermes runtime proof shown in Builder.
- Installed Python Playwright and managed Chromium on the NAS under project storage, patched authenticated verifiers to use Playwright-managed Chromium when no system browser exists, and deployed the diagnostic verifier update.
- Recorded a clean NAS-local Workbench/browser blocker receipt instead of a traceback: missing native library `libatk-1.0.so.0` prevents Chromium launch on Synology.
- Promoted stale MiniMax-M2.7 route inputs to MiniMax-M3 across the launcher, Hermes normalization, web chat routing, mission route mutation, and route outcome recommendations.
- Preserved explicit resume route choices so a requested `uniform_quality` route is not silently lowered by stable-progress autonomy.
- Deployed the M3 route patch and rebuilt `web/dist` to `/volume1/Saclay/projects/syntelos/releases/20260505-212517`; backend health returned `{"ok": true, "backend": "fluxio-web", "loginRequired": true}`.
- Verified authenticated live Builder, Agent/Workbench, and phone routes after deployment with nonblank screenshots and no stale MiniMax-M2.7 frontend routing leakage.
- Deployed the accessible MiniMax-M3 UI polish pass: live Agent and phone progress now expose polite status regions, phone notifications lead with the first meaningful live update line, and the compact phone screenshot now verifies at `390x1619`.
- Reverified the active NAS release after that deploy: Builder `ok=true` at `2026-06-02T16:51:35Z`, Agent `ok=true` at `2026-06-02T16:52:17Z`, phone `ok=true` at `2026-06-02T16:51:33Z`.
- Deployed the live notification/Agent visible-text sanitization patch, removing stale legacy MiniMax aliases from the rendered operator UI while keeping live record sources and timestamps intact.
- Reverified the active NAS release after that deploy: Builder `ok=true` at `2026-06-02T17:22:46Z`, Agent `ok=true` at `2026-06-02T17:24:20Z`, phone `ok=true` at `2026-06-02T17:23:37Z`.
- Deployed the Builder density pass: queue-first Builder and ReferenceShell bands now use one command column, two-column metrics, wrapped copy, and horizontal actions instead of a three-column layout that collapsed inside the main Builder column.
- Reverified the active NAS release after that deploy: Builder `ok=true` at `2026-06-02T17:33:30Z`, phone `ok=true` at `2026-06-02T17:34:14Z`, backend health `ok=true`.
- Deployed the MiniMax-M3 Skills proof strip: the live Skills surface now shows Hermes as the harness, MiniMax-M3 as the frontend executor model, `SKILL.md` as the skill format, and live NAS registry rows as the source.
- Reverified the active NAS release after that deploy: Skills `ok=true` at `2026-06-02T18:21:01Z`, backend health `ok=true`, screenshot `.agent_control/screenshots/live-nas-skills-m3-proof-20260602.png`.
- Deployed stricter system-loss scoring to the NAS active release: Web availability/distribution is capped at T3 parity while Web Push `subscriptionCount=0`, and live Builder now shows `19.6/20`, `gap 0.4/20`, and `7/8` categories ahead instead of the earlier over-optimistic `20/20`.
- Reverified the active NAS release after that deploy: Builder `ok=true` at `2026-06-02T18:32:44Z`, backend health `ok=true`, screenshot `.agent_control/screenshots/live-nas-builder-strict-system-loss-20260602.png`.
- Extended `mission_6ade06ff56` budget to `43200` seconds and dispatched a new Hermes/MiniMax-M3 resume worker `delegate_284e44f4`.
- Reverified the active NAS release after the mission resume: Builder `ok=true` at `2026-06-02T18:44:12Z`; the active mission now shows `43% · Budget window progress`, `plannerLoopStatus=running`, no runtime-budget-exhausted row, and screenshot `.agent_control/screenshots/live-nas-builder-budget-resumed-20260602.png`.
