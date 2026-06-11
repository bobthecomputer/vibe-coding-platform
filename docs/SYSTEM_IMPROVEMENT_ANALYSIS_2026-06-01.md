# Fluxio System Improvement Analysis - 2026-06-01

## Current Verdict

The system is real, but it is not finished and must not call itself complete. Current completion is about `84%`: the NAS, backend, Hermes routing, mission rows, control UI, Telegram watchdog receipts, browser notification capability, Web Push sender keys, watchdog loop, Hermes-first launch defaults, live notification truth, first-screen live summary performance, mission-detail backend performance, first-screen Agent live-thread proof, explicit Web Push subscription proof UI, and durable NAS backend restart path are operational. The remaining gap is not basic reachability anymore; it is product trust. The product still loses operator trust through noisy UI, no fresh phone/Web Push browser-subscription receipt on the operator device, incomplete rendered phone/tablet proof of the Agent thread, and queue-pressure states that need clearer Builder action paths.

Current strongest evidence:
- T3 Code reference refreshed on `2026-06-02` from the official GitHub repository page: latest stable `v0.0.24` dated `2026-05-15`; current README says T3 Code supports Codex, Claude, and OpenCode and can run with `npx t3` or desktop installers.
- NAS SSH is reachable. `/volume1` is `37%` used with about `2.3T` available; `/volume1/Saclay` is about `30G`.
- Active release is `/volume1/Saclay/projects/syntelos/releases/20260505-212517`.
- Backend is serving on TLS port `47880`; `/api/health` and `/control` return successfully after restart through the durable release-local launcher on PID `21113`.
- Deployment durability now reports `durable`: `.agent_control/start_backend_47880.sh` is a real executable release file, not a `/tmp` symlink; `temporarySymlinkCount=0`.
- Workspace defaults are Hermes-first.
- External watchdog loop is active on PID `31324`; latest supervisor state reports `notificationStatus=duplicate_suppressed` because the current watchdog state was already delivered.
- Release readiness still reports `ready_for_1_0_validation` with required gates `8/8`.
- Operator route trust is now `operator_proven`: `6/6` tracked task categories have value-scored samples, including the repaired F1/data analytics route.
- Public launch evidence is present.
- Red-team escalation is adaptive and current: `75` rows, latest resistance `100`, latest pressure `215`, next pressure `220`.
- Live mission rows are Hermes-first and authenticated from the NAS.
- Live API refresh on `2026-06-02T01:11+02:00` returned `53` mission rows, `6` running missions, `4` queued missions, `24` completed missions, and `0` repair blockers.
- Live summary performance after the latest bootstrap compaction and durable restart is within budget: `2/2` authenticated NAS measurements passed, max wall time `108.45 ms`, max backend duration `20.92 ms`, and max payload `299525` bytes against the `350000` byte budget.
- Live mission-detail performance after the latest compaction is within budget: authenticated NAS measurements passed, max wall time `267.24 ms`, max backend generation `132.02 ms`, and the largest measured detail payload was `696489` bytes against the `750000` byte budget.
- The deployed `/control` bundle now contains `agentLiveThreadProof` and renders a first-screen `Live thread proof` band for the selected mission with transcript status, cache status, payload budget, and live message counts.
- Live mission-detail status now proves the checked Hermes rows have real runtime report counts and no transcript-only output warning.
- Live cross-category Hermes outcome validation now passes `4/4`: F1/data analytics (`mission_f023b4633d`), RF/wireless (`mission_e55b280fee`), public-data investigation (`mission_343715c7a1`), and frontend/mobile UI (`mission_89758ab312`).
- Live mission output quality now reports `passed` with `0` repair rows after the audit stopped ignoring real runtime report counts and stopped treating a passed runtime-output gate as a missing-artifact repair.
- MiniMax and OpenAI/Codex auth are both visible to the web backend.
- Web Push sender keys are configured, and the deployed `/control` bundle now has a first-class `Phone push proof` band with `Register this browser` when the sender is ready but this browser is not subscribed. There are still `0` current browser subscriptions, so closed-tab phone/tablet notification delivery is not yet proven on the operator device. Telegram receipts are live and delivered.
- New workspaces, workflow recipes, launch shortcuts, action proposals, and harness calls now default to Hermes unless OpenCLAW is explicitly selected.

Current hard blocker:
- There is no storage, web reachability, or repair blocker right now. The remaining watchdog problems are `info` severity queue-pressure items where queued missions overlap the active file scope, so the safe behavior is to keep them queued or split them into non-overlapping lanes. The latest watchdog pass reports `4` open problems, all queue pressure, and `0` bad repair blockers.
- SSH maintenance is currently usable with bounded commands. The web backend API remains the preferred live-state path for UI data; SSH is for deployment and repair only.

## Bad Parts First

The first problem is still live-state trust, but the worst form is fixed. The NAS is reachable and storage is healthy. The watchdog now acknowledges terminal delegates at dispatch time, avoids full-list mission overwrites, refreshes before skip, reconciles again after report generation, discovers cross-workspace delegated sessions when the harness result omits them, and re-reads session JSON before treating a dead recorded PID as a bad delegated-runtime failure.

The latest trust fix is default-route truth. Several implicit defaults still pointed at OpenCLAW even though the product and operator expectation are Hermes-first. Those defaults are now patched and deployed: `workspace-save`, `_default_workspace_profile`, workflow runtime fallbacks, action delegation, and the Fluxio harness runner all default to Hermes. OpenCLAW remains available as an explicit compatibility runtime.

The latest UI problem is not lack of data, it is explanation density. Builder has live queue-pressure evidence, but it still needs to make the safe next action obvious for non-technical users. The code now normalizes `workspace_queue_pressure` watchdog rows into `builderQueuePressureRows` and adds a dedicated queue-pressure section in both the watchdog panel and the multi-project Builder queue. This is verified locally and deployed to the NAS bundle.

The second problem is score fragility. Many category scores are capped by the same release quality score and by the NAS storage gate. This is better than score inflation, but it means Fluxio is not yet better than T3 in every category.

The third problem is Agent readability. This improved in the latest deploy: the Agent page now has a first-screen live-thread proof strip tied to selected mission detail, transcript state, cache state, payload budget, and real message counts. It still needs visual polish, clearer phone/tablet proof, and less competing chrome before it feels like a clean running thread.

The fourth problem was route-trust maturity. Cross-category Hermes runtime evidence now passes, and route trust is now `operator_proven`: `6/6` tracked task categories have useful value-scored proof. The F1/data category was promoted by `mission_f023b4633d`, which now carries an explicit useful operator closeout and `data_f1_analytics` route-trust annotation.

The fifth problem is web notification proof. Browser/PWA and Telegram notification paths exist, and the UI now exposes the live Web Push sender/subscription state instead of burying it in a small channel chip. Fresh phone/tablet push receipts remain required before web distribution can beat T3 cleanly.

The sixth problem is now UI rendering rather than backend detail performance. Summary and mission-detail backend measurements are within budget, and the Agent proof band is deployed, but speed cannot claim `20/20` until the thread view is visually verified across desktop, tablet, and phone with dismissible notifications and no stale preview/frame confusion.

## T3 Code Comparison

Latest observed T3 Code evidence:
- Official GitHub repository page: `https://github.com/pingdotgg/t3code`.
- Current README positioning: minimal web GUI for coding agents, currently Codex, Claude, and OpenCode.
- Current launch paths: `npx t3`, Windows `winget`, macOS Homebrew cask, Arch AUR.
- Latest release shown on GitHub: `T3 Code v0.0.24`, dated `2026-05-15`.
- Repository scale shown on GitHub at refresh: about `12.3k` stars, `2.4k` forks, `1,481` commits.
- Older local evidence still records prerelease `v0.0.25-nightly.20260530.413`; treat the GitHub repository page as the stronger current public source until the releases API is refreshed again.

T3 strengths Fluxio must beat:
- Very low-friction desktop/package launch.
- BYO provider connection story.
- Normal workflow model/provider switching.
- Worktrees, diff review, and PR flow.
- Fast, simple perceived UI.

Current Fluxio scorecard:

| Category | Fluxio | T3 reference | State |
| --- | ---: | ---: | --- |
| Launch friction and beginner experience | 17 | 18 | behind |
| Multi-project Builder operations | 18 | 17 | ahead |
| Harness and sub-agent capability | 16 | 18 | behind |
| Web availability and distribution | 18 | 18 | parity |
| Proof, verification, and trust | 18 | 14 | ahead |
| Speed and long-history performance | 18 | 18 | parity |
| Roadmap clarity and self-improvement | 16 | 14 | ahead |
| Interface clarity and operator ergonomics | 17 | 17 | parity |

The target remains `8/8` categories ahead. Current live audit result is `4/8`: Fluxio is stronger than T3-style tools on durable mission proof, multi-project intent, harness/sub-agent operation, and self-improvement direction, but still has `4` must-beat category gaps. The remaining weak areas are launch friction/beginner experience, interface clarity/operator ergonomics, speed/long-history proof cadence, and web availability/distribution.

## Mission Progress

`mission_7ac4ebd308` - F1 prototype/report:
- Status: completed.
- Runtime: Hermes.
- Agent messages: `40`.
- Runtime outputs: `4`.
- Artifact status: reported.
- Transcript: attached.
- Current read: best completed proof row among the launched discovery missions.

`mission_e55b280fee` - legal defensive RF/wireless mapping:
- Status: completed after Hermes watchdog reconciliation.
- Runtime: Hermes.
- Agent messages: `22`.
- Runtime outputs: `4`.
- Artifact status: reported.
- Transcript: attached.
- Current read: produced a reviewable RF/wireless mapping result; no longer the main stuck worker.

`mission_343715c7a1` - public-data investigation suite:
- Status: running.
- Runtime: Hermes.
- Agent messages: `32`.
- Runtime outputs: `4`.
- Artifact status: reported.
- Transcript: attached.
- Current read: active again. The latest watchdog auto-resume dispatched it cleanly, and the stale dead-delegate warning is gone.

`mission_89758ab312` - polished phone/tablet Builder progress:
- Status: running.
- Runtime: Hermes.
- Agent messages: `30`.
- Runtime outputs: `31`.
- Artifact status: none returned.
- Transcript: missing.
- Current read: still active and relevant to the phone/tablet notification goal. Needs a visible first-screen transcript/progress summary and a real browser subscription receipt before it can be called done.

`mission_dbc6edbc9c` - Fluxio fusion/system-improvement mission Hermes:
- Status: running after budget extension and async resume.
- Runtime: Hermes.
- Remaining runtime: about `5h56m` at the last check.
- Current read: the stale runtime-budget blocker was real, not a false positive. It has been extended and resumed; the watchdog no longer reports it as a repair blocker.

`mission_f023b4633d` - F1/data route-trust repair:
- Status: completed in the visible live Builder flow, but older local/verifier rows may still show it as running until refreshed.
- Runtime: Hermes.
- Agent messages: `40`.
- Runtime outputs: `18`.
- Artifact status: reported with `6` artifact rows, including `f1-telemetry-analytics-repair/index.html`, sample data, analytics JSON, proof digest, and browser preview check.
- Transcript: attached (`session_622e1e78f7`).
- Current read: this is now the strongest F1/data row for cross-category Hermes validation and route trust. It has an explicit `88` useful operator closeout, `trustSignal: promote`, and `routeTrustTaskType: data_f1_analytics`, so it lifts the final route-trust category to `operator_proven`.

## Improvement Order

1. Finish watchdog settle and acknowledgement.
   The latest patches refresh delegated sessions before skip, reconcile again after report generation, acknowledge terminal delegates at dispatch time, avoid full-list mission overwrites, and discover cross-workspace delegates. Keep the watchdog running until the remaining queue-pressure items are either safely split or completed.

2. Make Agent the real thread.
   The first Agent view should show current messages, slice progress, runtime output, artifact links, transcript state, and next repair action.

3. Restore transcript proof for active Hermes missions.
   This is no longer the immediate harness blocker for the checked set: current detail status has attached transcripts and real runtime report counts for the selected Hermes rows. Keep this verifier fresh as missions rotate.

4. Finish notification delivery proof.
   Browser notifications should use the beginning of the agent message, support dismissal, and archive phone/tablet receipts with production VAPID keys. Current state: Telegram delivered, browser notifications available, Web Push sender configured, proof UI deployed, `0` browser subscriptions.

5. Make Builder beat T3 for multi-project operation.
   Builder should rank active, blocked, queued, and completed projects; surface dependency and write-scope status; and expose one clear launch/resume path.

6. Keep the self-improvement loop hard.
   Red-team escalation is now `72` rows and still clean. The next aggregate-only benchmark is `L5 pressure 205` with `153` attempts.

## Implemented In This Pass

- Verified NAS storage: `/volume1` is `37%` used with about `2.3T` free; `/volume1/Saclay` is about `30G`.
- Verified the active release and Hermes-first workspace defaults on the NAS.
- Verified live app API state through `/api/backend`: `53` missions, `6` running, `0` review-blocked, `24` notifications, MiniMax authenticated, OpenAI/Codex authenticated, Web Push configured with `0` subscriptions.
- Patched Builder UI locally so live watchdog queue pressure is explicit: queued mission, blocking mission, scope safety, active/queued file counts, overlap files, and first repair step.
- Added desktop UI contract coverage for the live queue-pressure section.
- Verified `python -m pytest tests\test_desktop_ui_contract.py -q`: `38 passed`.
- Verified `npm run frontend:build`: Vite production build passed.
- Added regression coverage for recorded dead delegate PIDs, stale `launching` rows with no worker, post-report watchdog reconciliation, and running delegates that must be refreshed before skip.
- Patched and deployed `src/grant_agent/runtime_supervisor.py` so recorded dead delegate PIDs fail even when a stale heartbeat still says healthy.
- Patched and deployed `src/grant_agent/cli.py` so watchdog auto-resume handles `launching` rows with no active worker, runs a second reconciliation after report generation, and refreshes delegated sessions before deciding to skip a row.
- Patched and deployed `src/grant_agent/cli.py` again so watchdog auto-resume does not overwrite concurrent mission updates, acknowledges terminal delegated sessions immediately when dispatching reconciliation, and discovers cross-workspace delegated sessions when harness results omit the session list.
- Patched and deployed `src/grant_agent/mission_watchdog.py` so watchdog re-reads authoritative delegated session JSON before deciding that a recorded PID is dead. This cleared the two false `delegated_runtime_process_gone` bad issues on the NAS.
- Patched and deployed `src/grant_agent/web_backend.py` so `/api/health` works for the web control shell and unauthenticated `/api/backend` consumes request bodies before returning login-required. This prevents malformed `JSONGET` keep-alive failures and fixes the `/control` runtime-unavailable screen.
- Rebuilt and redeployed `web/dist`; verified `/control` reaches the real Fluxio login/control flow and captured `.agent_control/fluxio-control-ui-screenshot-20260601.png`.
- Restarted the NAS backend and watchdog loop on the patched release.
- Confirmed Hermes missions are being relaunched/reconciled by the watchdog instead of staying silently stale.
- Confirmed latest watchdog status has `0` repair blockers; remaining open problems are `info` queue-pressure items.
- Patched and deployed Hermes-first defaults:
  - `cli.py` workspace save default runtime now uses `hermes`.
  - `mission_control.py` default workspace profiles and workflow runtime fallbacks now use `hermes`.
  - `action_executor.py` delegated action proposals default to `hermes`.
  - `fluxio_harness.py` harness runs default to `hermes`.
  - Live NAS summary confirms first workspace default, first launch shortcut runtime, and first launch recommendation are all `hermes`.
- Patched and deployed overnight digest count truth: safely held queue items are no longer counted as raw `blocked`; the digest now reports `blocked=0`, `heldQueued=4`, `attention=4`, and `actionRequired=0`.
- Patched and deployed notification truth reporting:
  - `mission_watchdog.py` now emits structured `notificationChannels` for in-app stack, browser notification, Web Push, and Telegram.
  - `cli.py` now reports Telegram as `delivered`, `duplicate_suppressed`, or `not_requested` without implying that browser notifications are disabled.
  - `mission_control.py` now includes Web Push sender/subscription state in the overnight digest.
  - `delivery_receipt.py` now reports Web Push sender-ready-without-subscription correctly and includes `acknowledge_delivery_receipt` for the deployed backend.
- Restarted the watchdog loop on PID `25386` and the web backend on PID `30458`; `/api/health` returns `200`.
- Extended and resumed `mission_dbc6edbc9c`; refreshed watchdog summary now reports `4 mission(s) held safely in queue`, `0 repair`, and `6` running missions.
- Patched and deployed live summary performance:
  - `delivery_receipt.py` avoids importing `pywebpush` on every status call and tail-reads receipt ledgers.
  - `mission_control.py` uses a fast live skill summary instead of full skill-library enrichment on first-screen refresh.
  - `mission_control.py` now builds project progress through a bounded live mission/event summary, enriching only visible project rows while keeping the full snapshot/detail path available.
  - Cross-device launch receipt history now tail-reads JSONL instead of loading the full file for each summary refresh.
  - Bootstrap active mission rows now compact `contextRoots` and bound launch shortcuts, leaving full root context to mission detail.
  - Focused verification passed: `python -m py_compile src\grant_agent\mission_control.py` and `python -m pytest tests\test_mission_control.py::MissionControlTests::test_summary_snapshot_is_lightweight_and_notification_ready tests\test_mission_control.py::MissionControlTests::test_summary_bounds_skill_red_team_project_and_audit_sections tests\test_mission_control.py::MissionControlTests::test_store_creates_default_workspace_and_snapshot -q`.
  - Authenticated NAS verification now passes on warm bootstrap refresh: `2/2` measurements, max wall time `102.82 ms`, max backend duration `9.04 ms`, max payload `299523` bytes, and budget status `pass`.
- Patched and deployed mission-detail payload compaction:
  - Top-level `proof`, `state`, `delegatedRuntimeSessions`, and nested `mission` duplicates now use compact bounded payloads.
  - Agent-facing data remains available through `agentMessages`, `runtimeTranscript`, `proofDigest`, `artifactGate`, and `contextRoots`.
  - Focused verification passed: `python -m py_compile src\grant_agent\mission_control.py` and `8` mission-detail/summary tests.
  - Authenticated NAS verification passed: live mission-detail measurements have `0` backend warnings and `0` wall-time warnings, max wall time `267.24 ms`, max backend generation `132.02 ms`, and largest payload `696489` bytes.
  - Synced `.agent_control/live_mission_detail_performance_latest.json` and `.agent_control/live_mission_detail_status_latest.json` to the active NAS release.
- Patched and deployed Agent live-thread proof:
  - `FluxioShell.jsx` now derives `agentLiveThreadProof` from selected mission detail, runtime transcript state, payload budget, cache state, and real message counts.
  - `FluxioReferenceShell.jsx` renders a first-screen `Live thread proof` band with transcript, cache, budget, and message metrics.
  - `styles.css` adds responsive desktop/tablet layout for the proof band.
  - UI contract verification passed: `python -m pytest tests\test_desktop_ui_contract.py -q` (`38` tests).
  - Frontend build passed and the NAS `/control` bundle now serves `assets/index-DRmtMp5Y.js` and `assets/FluxioReferenceShell-BkvugY2R.js`.
- Patched and deployed durable backend restart:
  - Added tracked `scripts/start_backend_47880.sh` and copied it into the active release `.agent_control/start_backend_47880.sh`.
  - Replaced the previous `/tmp/start_backend_47880_no_bytecode.sh` symlink with a real executable release file.
  - Added `backend_restart_launcher` to NAS deploy readiness so deploy readiness cannot pass without the durable restart launcher.
  - Restarted the backend through the new script; `/api/health` returned `200` and backend PID is `21113`.
  - Refreshed and published the NAS system audit; UI-facing `deploymentDurabilitySummary` now reports `status=durable`, `durable=true`, and `temporarySymlinkCount=0`.
  - Post-restart authenticated summary performance passed: `2/2`, max wall time `108.45 ms`, max backend duration `20.92 ms`, max payload `299525` bytes, and budget status `pass`.
- Patched and deployed Web Push subscription proof UI:
  - `FluxioShell.jsx` now derives `webPushSenderConfigured`, `webPushSubscriptionCount`, `webPushReady`, and `webPushProofStatus` from live digest/channel state and local browser subscription checks.
  - The notification stack now renders a `Phone push proof` band with `data-web-push-proof="true"` and a direct `Register this browser` action when the sender is ready but the current browser is not subscribed.
  - `styles.css` adds stable phone/tablet-friendly proof-band styling.
  - UI contract verification passed: `python -m pytest tests\test_desktop_ui_contract.py -q` (`38` tests).
  - Frontend build passed: `npm run frontend:build`.
  - Deployed package `fluxio-webpush-proof-20260602.tgz` to active release `/volume1/Saclay/projects/syntelos/releases/20260505-212517`.
  - Verified served `/control` references the new `assets/index-Cf9k5Al6.js` and `assets/index-D6emOrnH.css`, and the NAS bundle contains both `data-web-push-proof` and `Register this browser`.
- Patched and deployed cross-category Hermes validation repair:
  - Refreshed NAS mission-detail status with F1/data, RF/wireless, public-data investigation, frontend/mobile UI, fusion, phone watcher, and security proof rows.
  - `system_audit.py` now counts `realRuntimeReportCount` as concrete runtime-output evidence when legacy artifact-gate `runtimeOutputCount` is zero.
  - `system_audit.py` no longer classifies opaque mission IDs such as `mission_02f113...` as F1 just because the hash contains `f1`.
  - `system_audit.py` and `plan_mission_artifact_repairs.py` no longer flag a completed mission for hard-artifact repair when the hard gate passed and real runtime output exists.
  - Focused verification passed: `5` targeted `tests/test_cli_preferences.py` tests and `python -m py_compile src\grant_agent\system_audit.py scripts\plan_mission_artifact_repairs.py scripts\sync_nas_mission_detail_status.py`.
  - Published fresh NAS audit snapshot: cross-category Hermes validation is `passed` (`4/4`), live mission output quality is `passed`, and repair rows are `0`.
