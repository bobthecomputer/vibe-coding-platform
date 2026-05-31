# Fluxio System Improvement Analysis - 2026-05-30

## Current Evidence

- Live NAS control room: `https://sysnology.tail602108.ts.net:47880/control`.
- Latest authenticated Agent verifier: `tmp-ui-checks/authenticated-live-agent/after-live-summary-project-progress-agent-check-check.json`.
- Latest authenticated Builder verifier: `tmp-ui-checks/authenticated-live-control/after-live-summary-project-progress-control-check-check.json`.
- F1-specific Agent verifier: `tmp-ui-checks/authenticated-live-agent/after-pwa-update-f1-agent-click-check.json`.
- Verifier status: current Agent passed at `2026-05-30T19:50:46.199261+00:00`; live Builder/control passed at `2026-05-30T19:50:30.718423+00:00`; F1/Workbench stale-frame regression remains covered by the Agent verifier's message and Workbench click-switch checks.
- Live mission rows: `52`.
- Active mission rows: `2`, both Hermes, both running; blocked mission rows: `0`.
- Runtime mix: `48` Hermes rows, `4` OpenClaw rows.
- Notifications: `24`, including `17` slice-completion notifications.
- Self-improvement red-team evidence: `40` aggregate-only NAS rows after the latest NAS loop advancement; current source is `live_nas_system_audit_with_local_follow_up`.
- Latest red-team loop state: `38` satisfied escalation targets, `1` pending harder follow-up, next benchmark `hackaprompt` at `L5 pressure 110` with `89` attempts.
- Latest T3 Code release evidence: `.agent_control/t3_code_benchmark_latest.json`, refreshed at `2026-05-30T17:59:39.302658+00:00` from `https://api.github.com/repos/pingdotgg/t3code/releases`.
- T3 Code baseline observed: stable `v0.0.24` published `2026-05-15T06:39:44Z`; nightly `v0.0.25-nightly.20260530.413` published `2026-05-30T01:18:06Z`.
- Deployed full-summary cache evidence: direct authenticated NAS calls returned `miss`, then `hit`, then `hit` with `52` missions and `summaryCache.mode = full`.
- Deployed summary-shaping evidence: full summary payload dropped from about `1,310,005` bytes to about `346,623` bytes by deferring terminal mission context roots, compacting terminal mission index rows, bounding project/red-team/audit rows, and stripping skill audit blobs from the live summary.
- Warm authenticated summary calls now return in about `190ms` from memory cache after the latest summary-speed deployment.
- Restart cold-start proof: after a real backend restart, the first authenticated summary request returned as `summaryCache.status = disk-hit` in about `638ms` with `freshness = control-files-matched`, avoiding a full rebuild when the persisted summary signature still matches.
- True rebuild latency is now mostly solved for the current data size: after clearing the persisted summary cache and refreshing the watchdog, the authenticated full-summary rebuild reported `84.53ms` backend duration (`1.64s` external first HTTP round trip) with `52` missions. This is down from `5.36s` after the previous patch and from the earlier `41.9s+` rebuild measurement.
- Latest slowest summary sections are now `skill_catalog` (`38.77ms`), `project_progress_history` (`13.09ms`), `base_store_load` (`12.81ms`), `mission_rows` (`7.56ms`), and `system_audit_digest` (`4.21ms`).
- The watchdog report is now sourced from `.agent_control/mission_watchdog.json` with explicit `summarySource` freshness. The latest measured summary reports watchdog freshness as `fresh`, age `25s`.
- The live Skills surface is now verified independently from the generic Builder page: `after-live-skills-verifier-check` proves `12` NAS skill rows, `4` repair-state rows, `12` measured feedback rows, no static skill leaks, and no full snapshot calls.
- Local beginner launch proof `tmp-ui-checks/responsive/beginner-launch-hermes-5174-responsive-check.json` now passes on phone, tablet, and desktop. It proves a mobile/frontend objective recommends `Hermes · Frontend/UI/design` with `MiniMax-M2.7` execution instead of defaulting the harness to OpenClaw.
- Live Builder now has an authenticated multi-project queue and beginner-guide proof: `after-live-message-scope-guide-control-check` proves the NAS summary exposes `8` dependency-aware scheduling rows, renders the live multi-project queue, and renders a live-data beginner guide connecting mission state, Agent thread, queue, and notifications.
- Live Agent now has strict message-scope proof: `after-live-message-scope-guide-agent-check` proves every visible live Agent row is scoped to the selected mission, runtime-output report bodies are promoted into selectable message text, message clicks switch the selected proof panel with `0` stale iframes, and Workbench click-switching stays iframe-free.
- Live Agent now has a sub-agent lane-board and lane-control proof: `after-clearall-digest-fix-agent-check` proves the selected running mission exposes visible live `planner`, `executor`, and `verifier` rows plus operable Inspect/Proof/Reroute controls with a visible lane-control receipt.
- Live Builder and Agent now have a compact live operations brief: `after-live-summary-project-progress-control-check` proves it renders from current NAS summary/detail data with `52` missions, `2` running missions, `24` alerts, and the same `8` dependency-aware queue rows as the live summary contract.

## What Is Working

- The live Agent route now shows real Hermes/runtime reports for current NAS missions instead of fixture chat.
- The RF/wireless mission has concrete runtime-output rows for a draft implementation plan and an implemented slice note.
- Message clicks in the live report thread rebuild the selected-message panel and keep iframe count at `0`, so the old stuck preview/F1-frame symptom is verified fixed on the live surface.
- Workbench now defaults to selected live-message evidence instead of a mission preview iframe, and the authenticated verifier clicks Workbench rows to prove the F1/stale-frame path stays fixed.
- Skills now show live NAS skill-library rows with system-loss feedback and repair/reinforce state. The route is no longer only "visually plausible"; it has a Skills-specific authenticated check.
- The PWA shell now registers a build-stamped service worker URL, bumps the cache version to `fluxio-pwa-v7-live-thread-cache-purge-20260530`, purges old Fluxio caches, and checks for shell updates every minute so stale in-memory UI is forced forward after deployments.
- Builder and Agent operate from the NAS web endpoint, with local account auth and live mission switching.
- Hermes is the dominant runtime and is used for the active missions, matching the requested Hermes-first direction.
- The mission launcher is now Hermes-first for frontend/mobile/browser goals while still surfacing MiniMax as the specialist UI execution model. OpenClaw is only selected by the recommendation when the objective explicitly asks for OpenClaw.
- The NAS backend now caches full control-room summaries for a short live window and explicitly labels stale-while-revalidate responses; this improves perceived speed without introducing hidden demo/fallback data.
- The persisted full-summary cache signature now includes watchdog report, problem report, and supervisor files, so watchdog refreshes invalidate old summary snapshots instead of leaving stale status visible.
- The summary harness lab now derives session health from already-loaded mission delegated-session records instead of scanning runtime-session files, so `harness_lab` dropped out of the cold-summary slowest list.
- The skill catalog now builds one operator-value index per `SkillLibrary` instance instead of rereading/parsing `missions.json` once per skill row, reducing `skill_catalog` from seconds to about `39ms` on the current NAS data.
- The NAS summary now only includes rich context roots for active missions; old/completed missions point to mission detail for archived context instead of bloating the main Agent/Builder route.
- The live skill catalog no longer ships learned-skill audit blobs in every refresh; the measured skill-library portion fell to about `21.6KB`.
- The backend now persists the last full live summary with a control-file signature and cache version. It is used only when the current mission/workspace/event signatures match, so it is not an unlabeled demo/fallback path.
- The live summary now recomputes each mission's provider/runtime truth before emitting rows, so stale mission JSON cannot contradict the current Hermes/OpenClaw/OpenAI/MiniMax credential pool.
- Builder now has a first-class `fluxio.provider_capability_contract.v1` per live mission, with planner/executor/verifier lanes, provider readiness, auth path, quota truth, tool families, and normalized failure classes exposed directly in the UI.
- Builder now renders the live dependency-aware multi-project queue from `projectProgressHistory.schedulingQueue`, including rank, state, priority, active/queued/blocked/done counts, related holds, and safe-to-launch versus hold state.
- Builder now includes a live beginner guide sourced only from the NAS summary and selected mission detail: mission count, selected Agent thread row count, queue rank count, and notification/slice-alert count are shown without fixture rows.
- Builder and Agent now show a single live operations brief above the dense panels, combining selected mission, latest runtime/report text, progress, running count, queue count, and alert count from NAS-only data.
- Live Agent messages are now mission-scoped: untagged old transcript rows are not inherited by the selected live mission, so old 5.3/Collect-looking rows cannot appear under the wrong mission.
- Agent now has a first-class live sub-agent lane board. It reads delegated sessions when present, otherwise uses `runtimeLanes` / `providerCapabilities.lanes`, so planner/executor/verifier route ownership, provider, model, effort, auth state, quota state, current lane event, and lane-control receipts are visible from current NAS data.
- The self-improvement red-team loop now consumes the live NAS audit history tail before recording a harder follow-up, then merges the live audit rows with the new local row so the next audit does not lose the target it just satisfied.
- Skill selection now has a hard `fluxio.skill_system_loss_hold.v1` gate: high-loss or low-operator-value skills stay visible in Skill Studio but are not returned to mission execution until clean validation evidence clears the repair/promotion gate.
- Route selection now has `fluxio.route_outcome_quarantine.v1`: provider/model lanes with low operator-value closeouts or weak success rates are held out of automatic task-fit routing and rerouted to Codex `gpt-5.5` high until a clean value-scored route-trust sample clears the lane.
- The fusion mission `mission_f4743514ab` is completed; it should be treated as historical proof, not as the active visual proof mission.

## Bad Parts First

1. **Speed is improved but not fully solved.**
   The deployed NAS backend now serves warm full-summary requests from an explicit live cache, uses a signature-checked persisted cache after restart, compacts terminal mission rows, removes skill audits from the main route, keeps payload around the `350KB` target, and reduced backend rebuild time to `84.53ms` for the current `52`-mission dataset. The remaining speed work is less about the current summary and more about keeping this true at larger scale: project history, skill feedback, watchdog reports, and release/audit proof need incremental indexes before the mission count grows significantly.

2. **Deployment is still too manual.**
   The current patch was deployed successfully through the Paramiko tar-stream runbook, but that is still an operator-grade path. The system should not depend on ad hoc SSH deploys for emergency UI/backend fixes; it needs a signed release/update path or a resilient NAS-side updater.

3. **The UI is better, but still too dense.**
   Agent now has real, mission-scoped messages, full selected report bodies, and a compact live operations brief. Builder now exposes a real live multi-project queue, beginner guide, and matching live operations brief. The overall surface is still dense; the ideal app shape is: mission list, active live thread, selected message/proof rail, notifications, and a clearer queue-first Builder layout.

4. **System-loss learning exists but is not enforced enough.**
   Mission-slice feedback, red-team history, skill feedback, and repair proposals exist. The red-team loop now advances from live NAS audit state instead of stale local-only history, high-loss skills are held out of mission selection, low-value provider/model lanes are quarantined from automatic task-fit routing, and the Skills page is verified to show live repair/reinforce state. The remaining gap is proving route quarantine over longer live trends and turning repair proposals into one-click validated repair missions.

5. **Sub-agent lanes are visible and have first-pass controls, but still need deeper mutation proof.**
   Planner/executor/verifier routing exists, default route text now prefers high-effort Codex 5.5, and Agent renders a live lane board with role, provider, model, effort, auth, quota state, current event, Inspect/Proof/Reroute buttons, and a lane-control receipt. The remaining gap is proving pause/resume/reroute side effects across longer live missions, not only routing the lane action from the UI.

6. **Harness parity is better, but true live quota reporting still needs provider adapters.**
   Fluxio now emits a single live provider capability contract for each mission and Builder renders readiness, quota truth, tool families, and failure classes. The remaining parity work is to replace `quota.status = unreported` with actual provider quota/rate-window reports when each provider exposes them.

7. **Beginner experience is not good enough yet.**
   A beginner can launch through the web, the launcher now proves the expected Hermes-first/MiniMax-frontend route across phone, tablet, and desktop, and Builder now shows a live beginner guide. The remaining gap is a true guided first-run flow that explains Hermes, proof, route choice, and notifications while the user performs the first mission.

8. **Notifications are useful but incomplete.**
   Browser notification receipts exist, slice notifications are counted, individual dismiss works, and Clear all now removes both live notification rows and the overnight digest. Phone/tablet experience still needs a reliable subscribed device view and probably an out-of-band channel for overnight work.

9. **Web availability exists but distribution is not finished.**
   Private NAS web works. Public launch readiness and package/release receipts exist. The remaining gap is external publication proof: a new user should be able to open a public page, install/launch, connect providers, and reach the private control room without manual file knowledge.

## Current Mission Advancement

| Mission | State | Evidence | Next use |
|---|---|---|---|
| `mission_e55b280fee` RF/wireless mapping | Running | Live row reports Hermes runtime, planner loop running, `22` Agent messages, `2` runtime-output rows, strict mission-scoped Agent rows, `planner/executor/verifier` lane-board proof, and current Agent/Workbench switching proof | Best cross-mission switch, lane-board, and notification proof mission |
| `mission_343715c7a1` public-data investigation suite | Running | 22 Agent messages, 2 runtime-output rows, planner loop running, authenticated provider capability status `ready` across MiniMax/OpenAI/OpenAI-Codex, `30` visible mission-scoped Agent rows, live Hermes report selection, lane-control receipt proof, and quota truth explicitly `unreported` for all three providers | Best current visual proof and multi-project validation mission |
| `mission_f4743514ab` fusion mission | Completed | Completed detail visible; no current runtime-output rows | Historical harness proof, not active UI proof |

## T3 Code Comparison

| Category | Fluxio Now | T3 Code Baseline | Required Next Bar |
|---|---|---|---|
| Launch | Strong private NAS launch, weak public publication | Latest observed T3 stable `v0.0.24` ships packaged desktop assets; nightly `v0.0.25-nightly.20260530.413` also ships desktop artifacts | Publish/install proof with beginner flow |
| Multi-project Builder | Live dependency-aware queue is now visible and verified; Builder still visually dense | T3 emphasizes project/worktree flow | Make the queue the primary Builder layout |
| Sub-agents and harness | Strong Hermes-first supervision, route history, proof | T3 focuses on orchestrating known coding agents | Make lanes explicit and interchangeable |
| Speed | Warm summaries are fast and current backend rebuild is `84.53ms`; first authenticated HTTP round trip still has network/auth overhead | T3's bar is perceived responsiveness | Keep incremental indexes so this holds at larger mission counts |
| UI clarity | Powerful but dense; Agent/Workbench and Skills are now live-data verified | T3's bar is simpler first-use flow | Reduce panels and make active thread primary |
| Proof/trust | Stronger than T3 | T3 has diff/PR workflow strength | Keep durable proof while improving diff ergonomics |
| Self-improvement | Strong red-team/skill feedback evidence | T3 is less focused on autonomous system-loss loops | Enforce loss feedback automatically |

## Recommended Next Engineering Order

1. Keep summary performance protected with incremental indexes for project progress, skill feedback, watchdog, and audit proof as mission count grows.
2. Turn Agent into one primary thread with a proof rail; demote trace/bookkeeping further.
3. Promote Builder's verified multi-project queue into the primary layout with owner lane, next action, and problem count always above secondary dashboards.
4. Add a first-run tutorial that launches one Hermes mission and explains proof, messages, route, and notifications.
5. Add provider-specific quota adapters so the provider capability contract can show remaining quota/rate windows instead of `unreported`.
6. Make system-loss enforcement automatic: high-loss skill or route gets held, repair mission launches, validation required before reuse.
7. Replace the manual NAS deploy runbook with an authenticated updater or release channel.
8. Finish phone/tablet notifications and a mobile progress URL.

## Latest Backend Patch

- Added `fluxio.skill_system_loss_hold.v1` to `SkillLibrary`: any skill in `repair`, `operator_value_repair`, `operator_value_deprioritize`, or `selectionPolicy.state = deprioritize` is visible in the catalog but excluded from `retrieve()` until its promotion gate is eligible.
- Updated the system audit so `has_system_loss_skill_routing` only passes when the hard hold contract and `systemLossHold` field exist, avoiding a false pass from soft ranking alone.
- Deployed the skill hold and audit patches to `/volume1/Saclay/projects/syntelos/releases/20260505-212517`, cleared the summary cache, and restarted the NAS backend.
- Added `fluxio.route_outcome_quarantine.v1` to route outcome trends. Low operator-value provider/model lanes, such as a bad MiniMax frontend executor lane, are recorded under `quarantinedRoutes`.
- Updated `recommended_model_routes()` so automatic task-fit/outcome routing skips a quarantined executor/verifier lane and reroutes to `openai-codex/gpt-5.5` with `route_intent = route_outcome_quarantine_reroute`.
- Updated the system audit so `has_outcome_trend_routing` requires both positive outcome-trend routing and route-outcome quarantine/reroute support.
- Added the route-outcome quarantine fields to the live route-trust coverage summary so the authenticated summary hot path returns `harnessLab.routeTrustCoverage` without needing the slow full snapshot command.
- Fixed the self-improvement evidence selector so a local follow-up row recorded from live NAS audit history is merged back with the live audit tail instead of being hidden by the stale live/local source choice.
- Added `historyTail` to `fluxio.self_improvement_evidence.v1` so the bounded red-team loop can seed the next harder benchmark from the live audit rows without exporting raw payload attempts.
- Updated `advance_self_improvement_red_team_loop.py` to report the red-team source and seed-history row count for each bounded step.
- Advanced the NAS red-team loop once after deployment: the runner recorded the aggregate-only `87`-attempt follow-up and left the next harder target at `89` attempts, preserving ongoing operation.
- Extended `fluxio.provider_capability_contract.v1` with `quotaSummary`, `toolSummary`, `failureSummary`, per-provider `quota`, `toolFamilies`, and `failureClasses`.
- Quota is now deliberately labeled `unreported` when auth is present but the runtime has no provider quota report, avoiding false "provider limit" claims.
- Added `fluxio.provider_capability_contract.v1` to full mission payloads, fast snapshots, bounded mission detail, and live summary mission rows.
- Recomputed provider truth during live summary builds so mission rows use current provider auth presence instead of stale persisted mission state.
- Cleared the deployed NAS summary cache after rollout and verified `mission_343715c7a1` reports provider capability status `ready` with MiniMax, OpenAI, and OpenAI-Codex authenticated.
- Added a summary-only harness lab path that derives route-trust and efficiency fields from already-loaded mission/runtime records instead of scanning the full `.agent_runs` tree during every summary rebuild.
- Added a summary runtime-session health path that uses already-loaded mission delegated-session records instead of scanning `.agent_control/runtime_sessions` in the summary path.
- Added a cached operator-value index inside `SkillLibrary`, so the live skill catalog parses `missions.json` once per catalog build instead of once per skill row.
- Added explicit watchdog summary-source metadata and uses the external watchdog report for summary display when present.
- Fixed summary-cache invalidation so watchdog report and supervisor changes are part of the freshness signature.
- Refreshed the NAS watchdog pass and confirmed the summary source is fresh in the latest measurement.
- Deployed to `/volume1/Saclay/projects/syntelos/releases/20260505-212517`.

## Latest Frontend/PWA Patch

- Builder's provider capability truth panel now shows quota status, tool families, and failure classes per provider.
- Builder route trust now exposes a held-lane count and a `Held route lanes` panel when `quarantinedRoutes` contains provider/model lanes held by outcome-trend quarantine.
- Workbench live message rows are selectable and pin the preview panel to the selected message; a selected row with no served preview artifact now shows selected-message evidence instead of reusing an older mission iframe.
- Workbench now auto-selects a real runtime report row in live mode, so an already-captured mission preview/F1 iframe cannot remain the default selected evidence.
- Agent message cards now promote the Hermes `Runtime output` body as the visible message title/detail instead of using the control-room action title as the primary text.
- Skills live rows now include stable `data-live-skill-row`, `data-skill-id`, and `data-skill-feedback-state` markers so authenticated tests can prove the page is using NAS skill data.
- The authenticated live control verifier now has Skills-specific checks for NAS skill rows and system-loss repair/reinforce feedback.
- Added a Builder provider capability truth panel for live missions, showing planner/executor/verifier provider readiness, auth path, model, and blocker text from the live provider contract.
- Filtered the Agent live report list to prefer real Hermes/runtime report rows and avoid selecting synthetic control-room overview/bookkeeping rows as the main report message.
- Added PWA cache purging for old `fluxio-pwa-*` caches and one-time reload per build marker.
- Added a build-stamped PWA registration (`20260530-live-thread-cache-purge-v7`) so browsers do not silently keep an older service-worker script URL.
- Added periodic service-worker update checks every `60s`; when a new shell takes control, the page reloads through the existing `controllerchange` path.
- Bumped the served service-worker cache marker to `fluxio-pwa-v7-live-thread-cache-purge-20260530`.
- Deployed rebuilt `web/dist` to `/volume1/Saclay/projects/syntelos/releases/20260505-212517`.
- Agent lane cards now expose Inspect, Proof, pause/resume, and Reroute controls from live NAS lane data, and clicking Inspect produces a visible lane-control receipt instead of a no-op.
- Notification Clear all now dismisses the exact visible notification rows plus the overnight digest identity, fixing the case where the digest card stayed visible after clearing.
- Added a shared live operations brief to Builder and Agent. It surfaces mission progress, active running count, dependency-aware queue count, alert count, and latest Hermes/runtime report text from NAS summary/detail state.
- Fixed the reference shell project-progress source so Builder prefers `summarySnapshot.projectProgressHistory` when the live `fluxio.project_progress_history.v1` contract is present; the compact brief now shows the same `8` queue rows proven by the API and detailed queue.
- Deployed rebuilt `web/dist` and the updated source/verifier files to `/volume1/Saclay/projects/syntelos/releases/20260505-212517`.

## Latest Verification

- `python -m py_compile src\grant_agent\web_backend.py src\grant_agent\mission_control.py`
- `python -m pytest tests\test_web_backend.py::FluxioWebBackendTests::test_control_room_summary_command_loads_matching_persisted_full_snapshot_after_restart tests\test_web_backend.py::FluxioWebBackendTests::test_control_room_summary_cache_signature_includes_watchdog_reports tests\test_mission_control.py::MissionControlTests::test_summary_snapshot_is_lightweight_and_notification_ready -q`
- NAS health/control receipt: `.agent_control/deployment_evidence/private-nas-web.json`, checked `2026-05-30T15:01:20.794864+00:00`.
- Summary fast-path receipt: `.agent_control/deployment_evidence/summary-fastpath-measurement-20260530-v2.json`.
- Authenticated live Agent receipt: `tmp-ui-checks/authenticated-live-agent/after-summary-fastpath-watchdog-signature-check.json`.
- PWA/update contract: `python -m pytest tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_web_shell_is_installable_pwa_with_offline_fallback tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_authenticated_live_agent_verifier_proves_real_mission_detail -q`.
- Frontend build: `npm run frontend:build`.
- NAS health/control receipt after PWA deploy: `.agent_control/deployment_evidence/private-nas-web.json`, checked `2026-05-30T15:12:22.963414+00:00`.
- Authenticated F1 Agent receipt: `tmp-ui-checks/authenticated-live-agent/after-pwa-update-f1-agent-click-check.json`.
- Authenticated current Agent receipt: `tmp-ui-checks/authenticated-live-agent/after-pwa-update-current-agent-click-check.json`.
- Summary harness fast-path tests: `python -m pytest tests\test_mission_control.py::MissionControlTests::test_summary_harness_lab_uses_mission_session_index_without_full_runtime_scan tests\test_mission_control.py::MissionControlTests::test_harness_lab_snapshot_reports_efficiency_and_session_health tests\test_mission_control.py::MissionControlTests::test_summary_snapshot_is_lightweight_and_notification_ready -q`.
- Skill catalog index tests: `python -m pytest tests\test_fluxio_harness.py::FluxioHarnessTests::test_skill_library_records_slice_feedback_loss_and_catalog_loop tests\test_fluxio_harness.py::FluxioHarnessTests::test_operator_value_closeouts_change_skill_selection_policy tests\test_mission_control.py::MissionControlTests::test_summary_snapshot_is_lightweight_and_notification_ready -q`.
- Latest summary speed receipt: `.agent_control/deployment_evidence/summary-fastpath-measurement-20260530-v5.json`.
- Latest authenticated live Agent receipt: `tmp-ui-checks/authenticated-live-agent/after-summary-speed-index-agent-check.json`.
- Provider contract focused tests: `python -m pytest tests\test_mission_control.py::MissionControlTests::test_runtime_provider_env_file_marks_minimax_ready_for_cli_snapshots tests\test_mission_control.py::MissionControlTests::test_release_adjacent_runtime_codex_auth_marks_planner_ready_for_cli_snapshots tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_builder_surfaces_project_health_and_subagent_lanes -q`.
- Latest NAS health/control receipt after provider-truth rollout: `.agent_control/deployment_evidence/private-nas-web.json`, checked `2026-05-30T16:19:40.317471+00:00`.
- Latest authenticated live Agent receipt after provider-truth rollout: `tmp-ui-checks/authenticated-live-agent/after-provider-truth-refresh-check.json`.
- Provider semantics focused tests: `python -m pytest tests\test_mission_control.py::MissionControlTests::test_runtime_provider_env_file_marks_minimax_ready_for_cli_snapshots tests\test_mission_control.py::MissionControlTests::test_release_adjacent_runtime_codex_auth_marks_planner_ready_for_cli_snapshots tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_builder_surfaces_project_health_and_subagent_lanes -q`.
- Frontend build after provider semantics: `npm run frontend:build`.
- Latest NAS health/control receipt after provider-semantics rollout: `.agent_control/deployment_evidence/private-nas-web.json`, checked `2026-05-30T16:28:34.374512+00:00`.
- Authenticated provider-semantics summary check: `mission_343715c7a1` reports `quotaSummary.schema = fluxio.provider_quota_summary.v1`, `toolSummary.schema = fluxio.provider_tool_summary.v1`, and `failureSummary.schema = fluxio.provider_failure_summary.v1`.
- Latest authenticated live Agent receipt after provider-semantics rollout: `tmp-ui-checks/authenticated-live-agent/after-provider-semantics-contract-check.json`.
- Self-improvement focused tests: `python -m pytest tests\test_demo_runner.py::DemoRunnerTests::test_red_team_loop_consumes_live_audit_history_tail_for_harder_follow_up tests\test_demo_runner.py::DemoRunnerTests::test_self_improvement_sampler_marks_previous_escalation_target_satisfied tests\test_demo_runner.py::DemoRunnerTests::test_self_improvement_sampler_records_aggregate_red_team_history tests\test_demo_runner.py::DemoRunnerTests::test_self_improvement_evidence_uses_operator_proven_live_route_trust -q`.
- Local self-improvement verifier: `python scripts\verify_self_improvement_evidence.py --write`.
- Local bounded loop advancement: `python scripts\advance_self_improvement_red_team_loop.py --max-steps 1 --write` recorded an aggregate-only `89`-attempt follow-up and advanced the next local target to `91` attempts.
- NAS focused tests after deploy: `/volume1/Saclay/projects/syntelos/.venv/bin/python -m pytest tests/test_demo_runner.py::DemoRunnerTests::test_red_team_loop_consumes_live_audit_history_tail_for_harder_follow_up tests/test_demo_runner.py::DemoRunnerTests::test_self_improvement_sampler_marks_previous_escalation_target_satisfied -q`.
- NAS self-improvement verifier: `/volume1/Saclay/projects/syntelos/.venv/bin/python scripts/verify_self_improvement_evidence.py --write`.
- NAS bounded loop advancement: `/volume1/Saclay/projects/syntelos/.venv/bin/python scripts/advance_self_improvement_red_team_loop.py --max-steps 1 --write`.
- NAS backend restart after cache clear: `bash /volume1/Saclay/projects/syntelos/current/.agent_control/start_backend_47880.sh`; `/health` returned `ok: true`, backend `fluxio-web`.
- Latest authenticated live Builder receipt after self-improvement live-merge rollout: `tmp-ui-checks/authenticated-live-control/after-self-improvement-live-merge-check.json`.
- Latest authenticated live Agent receipt after self-improvement live-merge rollout: `tmp-ui-checks/authenticated-live-agent/after-self-improvement-live-merge-agent-check.json`.
- Skill hold focused tests: `python -m pytest tests\test_fluxio_harness.py::FluxioHarnessTests::test_operator_value_closeouts_change_skill_selection_policy tests\test_fluxio_harness.py::FluxioHarnessTests::test_high_loss_skill_feedback_creates_repair_proposal_with_validation_gate -q`.
- Broader route/skill trust tests: `python -m pytest tests\test_fluxio_harness.py::FluxioHarnessTests::test_skill_library_records_slice_feedback_loss_and_catalog_loop tests\test_fluxio_harness.py::FluxioHarnessTests::test_operator_value_closeouts_feed_route_outcome_trends tests\test_cli_preferences.py::CliPreferenceTests::test_route_trust_closeout_auto_applies_low_value_samples tests\test_cli_preferences.py::CliPreferenceTests::test_route_trust_sampler_repairs_frontend_after_low_value_minimax_sample -q`.
- System-loss UI/audit contract: `python -m pytest tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_skill_studio_surfaces_mission_slice_feedback_loop -q`.
- NAS skill hold tests after deploy: `/volume1/Saclay/projects/syntelos/.venv/bin/python -m pytest tests/test_fluxio_harness.py::FluxioHarnessTests::test_operator_value_closeouts_change_skill_selection_policy tests/test_fluxio_harness.py::FluxioHarnessTests::test_high_loss_skill_feedback_creates_repair_proposal_with_validation_gate tests/test_fluxio_harness.py::FluxioHarnessTests::test_skill_library_records_slice_feedback_loss_and_catalog_loop -q`.
- NAS system-loss UI/audit contract after deploy: `/volume1/Saclay/projects/syntelos/.venv/bin/python -m pytest tests/test_desktop_ui_contract.py::DesktopUiContractTests::test_skill_studio_surfaces_mission_slice_feedback_loop -q`.
- Latest `/health` after final audit deploy returned `ok: true`, backend `fluxio-web`.
- Latest authenticated live Builder receipt after system-loss hold rollout: `tmp-ui-checks/authenticated-live-control/after-system-loss-hold-audit-check.json`.
- Route quarantine focused tests: `python -m pytest tests\test_fluxio_harness.py::FluxioHarnessTests::test_low_value_route_closeouts_quarantine_task_fit_route tests\test_fluxio_harness.py::FluxioHarnessTests::test_operator_value_closeouts_feed_route_outcome_trends tests\test_fluxio_harness.py::FluxioHarnessTests::test_recommended_routes_use_task_fit_for_frontend_execution tests\test_fluxio_harness.py::FluxioHarnessTests::test_recommended_routes_use_outcome_trends_for_similar_tasks -q`.
- Route quarantine audit contract: `python -m pytest tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_route_trust_live_sampler_launches_hermes_sampling_missions_safely -q`.
- NAS route quarantine tests after deploy: `/volume1/Saclay/projects/syntelos/.venv/bin/python -m pytest tests/test_fluxio_harness.py::FluxioHarnessTests::test_low_value_route_closeouts_quarantine_task_fit_route tests/test_fluxio_harness.py::FluxioHarnessTests::test_operator_value_closeouts_feed_route_outcome_trends tests/test_fluxio_harness.py::FluxioHarnessTests::test_recommended_routes_use_task_fit_for_frontend_execution tests/test_fluxio_harness.py::FluxioHarnessTests::test_recommended_routes_use_outcome_trends_for_similar_tasks tests/test_desktop_ui_contract.py::DesktopUiContractTests::test_route_trust_live_sampler_launches_hermes_sampling_missions_safely -q`.
- Latest authenticated live Builder receipt after route-outcome quarantine rollout: `tmp-ui-checks/authenticated-live-control/after-route-outcome-quarantine-check.json`.
- Workbench/route-trust visible UI tests: `python -m pytest tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_agent_review_keeps_runtime_messages_visible_and_defaults_to_high_effort tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_skill_studio_surfaces_mission_slice_feedback_loop tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_workbench_message_selection_does_not_reuse_stale_preview_frame -q`.
- Summary harness live route-trust tests: `python -m pytest tests\test_mission_control.py::MissionControlTests::test_summary_snapshot_is_lightweight_and_notification_ready tests\test_mission_control.py::MissionControlTests::test_summary_harness_lab_uses_mission_session_index_without_full_runtime_scan tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_skill_studio_surfaces_mission_slice_feedback_loop -q`.
- NAS summary harness route-trust deploy test: `/volume1/Saclay/projects/syntelos/.venv/bin/python -m pytest tests/test_mission_control.py::MissionControlTests::test_summary_snapshot_is_lightweight_and_notification_ready -q`.
- NAS summary query after deploy: `harnessLab.schema = fluxio.harness_lab.summary_compact.v1`, `routeTrustCoverage.schema = fluxio.route_trust_coverage.v1`, `routeOutcomeTrendSchema = fluxio.route_outcome_trends.v1`, `quarantinedRouteCount = 0`, `missions = 52`, `activeMissions = 2`.
- Latest authenticated live Builder receipt after summary harness route-trust rollout: `tmp-ui-checks/authenticated-live-control/after-summary-harnesslab-route-trust-check.json`.
- Latest authenticated live Agent receipt after summary harness route-trust rollout: `tmp-ui-checks/authenticated-live-agent/after-summary-harnesslab-agent-regression-check.json`.
- Runtime-message/Workbench focused tests: `python -m pytest tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_workbench_message_selection_does_not_reuse_stale_preview_frame tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_agent_promotes_runtime_output_reports_over_action_titles -q`.
- Latest authenticated live Agent receipt after runtime-message/Workbench rollout: `tmp-ui-checks/authenticated-live-agent/after-live-workbench-runtime-v8-fixed-verifier-check.json`.
- Skills live verifier test: `python -m pytest tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_skill_studio_surfaces_mission_slice_feedback_loop -q`.
- Latest authenticated live Skills/Builder receipt: `tmp-ui-checks/authenticated-live-control/after-live-skills-verifier-check.json`.
- Latest authenticated live Agent regression receipt after Skills rollout: `tmp-ui-checks/authenticated-live-agent/after-live-skills-agent-regression-check.json`.
- Lane-control and notification-clear local contract tests: `python -m pytest tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_web_shell_has_mobile_notification_summary_path tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_authenticated_live_control_verifier_proves_real_nas_rows tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_authenticated_live_agent_verifier_proves_real_mission_detail -q`.
- Frontend build after lane-control/clear-all patch: `npm run frontend:build`.
- Latest authenticated live Builder receipt after clear-all digest fix: `tmp-ui-checks/authenticated-live-control/after-clearall-digest-fix-control-check-check.json`.
- Latest authenticated live Agent receipt after lane-control and F1/message-switch regression: `tmp-ui-checks/authenticated-live-agent/after-clearall-digest-fix-agent-check-check.json`.
- Live operations brief local contract: `python -m pytest tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_builder_surfaces_project_health_and_subagent_lanes tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_authenticated_live_control_verifier_proves_real_nas_rows tests\test_desktop_ui_contract.py::DesktopUiContractTests::test_authenticated_live_agent_verifier_proves_real_mission_detail -q`.
- Frontend build after live operations brief: `npm run frontend:build`.
- Latest authenticated live Builder receipt after summary project-progress source fix: `tmp-ui-checks/authenticated-live-control/after-live-summary-project-progress-control-check-check.json`.
- Latest authenticated live Agent receipt after live operations brief: `tmp-ui-checks/authenticated-live-agent/after-live-summary-project-progress-agent-check-check.json`.
