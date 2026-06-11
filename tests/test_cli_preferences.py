from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.cli import (
    _launch_async_mission_resume,
    _auto_resume_ready_delegated_missions,
    _mission_budget_settings,
    _pid_exists,
    _invoke_engine,
    _mission_poll_interval_seconds,
    _mission_should_continue_after_result,
    _auth_store_has_provider,
    _minimax_auth_visible_for_workspace,
    bootstrap_project,
    cmd_mission_action,
    cmd_mission_proof_digest,
    cmd_mission_quickstart,
    cmd_mission_lane_control,
    cmd_mission_route,
    cmd_mission_start,
    cmd_mission_watchdog,
    cmd_skill_repair_apply,
    cmd_control_room_summary,
    cmd_cross_device_launch_rehearsal,
    cmd_system_audit,
    cmd_workspace_save,
    cmd_workspace_sync_conflict_resolve,
    cmd_workspace_sync_conflict_resolve_batch,
    _sync_mission_from_result,
)
from grant_agent.fluxio_harness import build_route_outcome_trends
from grant_agent.launch_recommendation import build_launch_runtime_recommendation
from grant_agent.mission_watchdog import ensure_watchdog_supervisor_loop
from grant_agent.checkpoints import CheckpointStore
from grant_agent.mission_control import (
    ControlRoomStore,
    _build_system_audit_digest,
    _provider_auth_presence_from_env,
    mission_hard_artifact_gate,
    refresh_mission_runtime_state,
    sync_mission_state_snapshot,
)
from grant_agent.models import (
    ActionApprovalGate,
    ActionExecutionRecord,
    ActionProposal,
    DelegatedRuntimeSession,
    MissionEvent,
    RunState,
    RuntimeInstallStatus,
    utc_now_iso,
)
from grant_agent.delivery_receipt import _read_telegram_token, send_telegram_delivery_receipt
from grant_agent.system_audit import (
    AuditCategory,
    build_system_audit,
    _apply_strict_score_caps,
    _apply_live_performance_caps,
    _calibrate_category_scores,
    _merge_synced_route_trust_maturity,
    _load_live_nas_evidence,
    _load_live_mission_detail_performance_evidence,
    _load_live_mission_detail_status_evidence,
    _load_live_nas_system_audit_evidence,
    _load_live_mission_output_quality_evidence,
    _live_cross_category_outcome_validation,
    _load_route_trust_sampling_evidence,
    _bad_first,
    _freshen_live_nas_evidence,
    _merge_synced_live_nas_evidence,
    _parse_iso_timestamp,
    _select_system_audit_release_readiness,
    _red_team_escalation_evidence,
    render_system_audit_markdown,
    _route_trust_maturity_snapshot,
    _summary,
    _system_loss_breakdown,
)
from scripts.advance_route_trust_sampling_loop import advance_loop
from scripts.review_route_trust_sampling_closeouts import review_closeouts
from scripts.run_route_trust_sampling_missions import (
    _apply_task_difficulty,
    _route_contract_for_task,
    _run_quickstart,
)
from scripts.run_route_trust_sampling_missions import run_sampling as run_route_trust_sampling
from scripts.record_github_release_publication import build_github_release_publication_receipt
from scripts.plan_mission_artifact_repairs import build_repair_plan
from scripts.plan_nas_storage_cleanup import _parse_remote_probe, _pressure_from_cleanup_plan
from scripts.verify_public_launch_readiness import verify_public_launch_readiness


def _init_git_repo(root: pathlib.Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "fluxio@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Fluxio"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)


class CliPreferenceTests(unittest.TestCase):
    @staticmethod
    def _engine_result(root: pathlib.Path, session_name: str) -> dict:
        return {
            "status": "ok",
            "session_path": str(root / ".agent_runs" / session_name),
            "autopilot_status": "completed",
            "autopilot_pause_reason": "",
            "verification_failures": [],
            "remaining_steps": [],
        }

    def _run_json_command(self, command, **kwargs) -> tuple[int, dict]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = command(argparse.Namespace(**kwargs))
        return exit_code, json.loads(buffer.getvalue())

    def test_workspace_save_persists_runtime_contract_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")

            exit_code, payload = self._run_json_command(
                cmd_workspace_save,
                root=str(root),
                name="Fluxio Workspace",
                path=str(root),
                default_runtime="hermes",
                user_profile="experimental",
                preferred_harness="legacy_autonomous_engine",
                routing_strategy="uniform_quality",
                route_overrides_json=json.dumps(
                    [
                        {
                            "role": "planner",
                            "provider": "minimax",
                            "model": "MiniMax-M2.7",
                            "effort": "high",
                        }
                    ]
                ),
                auto_optimize_routing="true",
                minimax_auth_mode="minimax-portal-oauth",
                commit_message_style="detailed",
                execution_target_preference="isolated_worktree",
                workspace_id=None,
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                payload["workspace"]["preferred_harness"],
                "legacy_autonomous_engine",
            )
            self.assertEqual(payload["workspace"]["routing_strategy"], "uniform_quality")
            self.assertEqual(
                payload["workspace"]["commit_message_style"],
                "detailed",
            )
            self.assertEqual(
                payload["workspace"]["execution_target_preference"],
                "isolated_worktree",
            )
            self.assertEqual(
                payload["workspace"]["route_overrides"][0]["provider"],
                "minimax",
            )
            self.assertTrue(payload["workspace"]["auto_optimize_routing"])
            self.assertEqual(
                payload["workspace"]["minimax_auth_mode"],
                "minimax-portal-oauth",
            )
            self.assertEqual(
                payload["snapshot"]["workspaces"][0]["preferred_harness"],
                "legacy_autonomous_engine",
            )
            self.assertEqual(
                payload["snapshot"]["workspaces"][0]["execution_target_preference"],
                "isolated_worktree",
            )
            self.assertEqual(
                payload["snapshot"]["workspaces"][0]["route_overrides"][0]["model"],
                "MiniMax-M2.7",
            )

    def test_system_audit_writes_gap_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build an overnight RF mapping prototype",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "running"
            mission.state.remaining_runtime_seconds = 1800
            mission.proof.summary = "Hermes is building the RF prototype artifacts."
            store.update_mission(mission)
            live_report = root / "tmp-ui-checks" / "authenticated-live-control" / "authenticated-live-control-check.json"
            live_report.parent.mkdir(parents=True)
            live_report.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.authenticated_live_control.v1",
                        "checkedAt": "2026-05-28T10:54:56+00:00",
                        "ok": True,
                        "checks": [
                            {"checkId": "summary-api-authenticated", "passed": True},
                            {"checkId": "slice-notifications-visible-in-dom", "passed": True},
                        ],
                        "summary": {
                            "counts": {
                                "missions": 18,
                                "activeMissions": 2,
                                "queuedMissions": 0,
                                "blockedMissions": 0,
                                "completedMissions": 10,
                            },
                            "notificationCount": 24,
                            "sliceNotificationCount": 7,
                            "runningMissions": [
                                {
                                    "mission_id": "mission_rf",
                                    "title": "Build a legal defensive RF/wireless mapping",
                                    "runtime_id": "hermes",
                                    "status": "running",
                                    "planner_loop_status": "running",
                                }
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )
            newer_live_report = (
                root
                / "tmp-ui-checks"
                / "authenticated-live-control-newer"
                / "newer-live-control-check.json"
            )
            newer_live_report.parent.mkdir(parents=True)
            newer_live_report.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.authenticated_live_control.v1",
                        "checkedAt": "2026-05-28T10:59:56+00:00",
                        "ok": True,
                        "checks": [
                            {"checkId": "summary-api-authenticated", "passed": True},
                            {"checkId": "running-missions-visible-in-dom", "passed": True},
                        ],
                        "summary": {
                            "counts": {
                                "missions": 19,
                                "activeMissions": 3,
                                "queuedMissions": 0,
                                "blockedMissions": 1,
                                "completedMissions": 11,
                            },
                            "notificationCount": 25,
                            "sliceNotificationCount": 8,
                            "runningMissions": [
                                {
                                    "mission_id": "mission_rf",
                                    "title": "Build a legal defensive RF/wireless mapping",
                                    "runtime_id": "hermes",
                                    "status": "running",
                                    "planner_loop_status": "running",
                                },
                                {
                                    "mission_id": "mission_f1",
                                    "title": "Build F1 telemetry analytics trust sample",
                                    "runtime_id": "hermes",
                                    "status": "running",
                                    "planner_loop_status": "running",
                                },
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )
            now_iso = datetime.now(timezone.utc).isoformat()
            (root / ".agent_control" / "nas_storage_pressure_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.nas_storage_pressure.v1",
                        "checkedAt": now_iso,
                        "mount": "/volume1/Saclay",
                        "sizeBytes": 3829365997568,
                        "usedBytes": 3829365997568,
                        "availableBytes": 0,
                        "usedPercent": 100,
                        "status": "critical",
                        "generatedCleanupBytesFreed": 1827633752,
                        "nextAction": "Free non-Syntelos NAS volume or Synology snapshot space before trusting unattended mission writes.",
                    }
                ),
                encoding="utf-8",
            )
            live_agent_report = root / "tmp-ui-checks" / "authenticated-live-agent" / "f1-output-check.json"
            live_agent_report.parent.mkdir(parents=True)
            live_agent_report.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.authenticated_live_agent.v1",
                        "checkedAt": now_iso,
                        "ok": True,
                        "checks": [
                            {
                                "checkId": "selected-live-mission",
                                "passed": True,
                                "missionId": "mission_f1",
                                "title": "Build F1 telemetry analytics trust sample",
                                "status": "completed",
                            },
                            {
                                "checkId": "selected-mission-detail-api",
                                "passed": True,
                                "missionId": "mission_f1",
                                "agentMessageCount": 12,
                            },
                            {
                                "checkId": "runtime-output-visible-in-thread",
                                "passed": True,
                                "runtimeOutputCount": 0,
                            },
                            {
                                "checkId": "live-workbench-proof-band-visible",
                                "passed": True,
                                "proofBandText": "LIVE WORKBENCH PROOF\n12\nMESSAGES\nRUNTIME REPORTS\n0\nARTIFACTS\nNONE RETURNED",
                            },
                        ],
                        "summary": {
                            "selectedMission": {
                                "mission_id": "mission_f1",
                                "title": "Build F1 telemetry analytics trust sample",
                                "runtime_id": "hermes",
                                "status": "completed",
                                "planner_loop_status": "completed",
                            }
                        },
                        "artifacts": {"screenshotPath": "tmp-ui-checks/f1.png"},
                    }
                ),
                encoding="utf-8",
            )
            route_dir = root / ".agent_control" / "route_trust_sampling"
            route_dir.mkdir(parents=True)
            (root / ".agent_control" / "red_team_escalation_history.jsonl").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.red_team_escalation_history.v1",
                        "recordedAt": "2026-05-29T06:04:00+00:00",
                        "preset": "hackaprompt",
                        "status": "passed",
                        "difficultyLevel": 3,
                        "nextDifficultyLevel": 4,
                        "passStreak": 2,
                        "cleanPass": True,
                        "shouldEscalate": True,
                        "attempt_count": 9,
                        "blocked_attempt_count": 9,
                        "nextAttemptBudget": 11,
                        "targetResistanceScore": 92,
                        "resistance_score": 96,
                        "rawPayloadExported": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (root / ".agent_control" / "t3_code_benchmark_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.t3_code_release_benchmark.v1",
                        "checkedAt": "2026-06-02T18:07:24+00:00",
                        "source": "https://api.github.com/repos/pingdotgg/t3code/releases",
                        "releaseCount": 5,
                        "latestStable": {
                            "tag": "v0.0.24",
                            "publishedAt": "2026-05-15T07:01:00Z",
                            "url": "https://github.com/pingdotgg/t3code/releases/tag/v0.0.24",
                        },
                        "latestPrerelease": {
                            "tag": "v0.0.25-nightly.20260602.439",
                            "publishedAt": "2026-06-02T08:05:20Z",
                            "url": "https://github.com/pingdotgg/t3code/releases/tag/v0.0.25-nightly.20260602.439",
                        },
                        "latestObservedRelease": "v0.0.24 stable published 2026-05-15T07:01:00Z; v0.0.25-nightly.20260602.439 pre-release published 2026-06-02T08:05:20Z",
                    }
                ),
                encoding="utf-8",
            )
            (route_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.route_trust_live_sampling_run.v1",
                        "generatedAt": "2026-05-28T10:55:10+00:00",
                        "ok": True,
                        "dryRun": False,
                        "runtime": "hermes",
                        "launchedSamplingMissions": [
                            {
                                "missionId": "mission_rf",
                                "taskType": "data_f1_analytics",
                                "runtime": "hermes",
                            }
                        ],
                        "skippedSamplingMissions": [],
                        "nextAction": "Let the launched Hermes sampling mission run.",
                    }
                ),
                encoding="utf-8",
            )
            (route_dir / "closeout_review_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.route_trust_sampling_closeout_review.v1",
                        "generatedAt": "2026-05-28T10:56:10+00:00",
                        "ok": True,
                        "proposals": [
                            {
                                "missionId": "mission_low_value",
                                "taskType": "frontend_design",
                                "status": "already_scored",
                                "missionStatus": "completed",
                                "score": 30,
                                "outcome": "not_useful",
                                "trustSignal": "deprioritize",
                            }
                        ],
                        "appliedCloseouts": [],
                        "missingMissions": [],
                    }
                ),
                encoding="utf-8",
            )
            output = root / "docs" / "SYSTEM_GAP_ANALYSIS.md"

            exit_code, payload = self._run_json_command(
                cmd_system_audit,
                root=str(root),
                output=str(output),
                json=False,
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(output.exists())
            report = output.read_text(encoding="utf-8")
            self.assertIn("Bad Parts First", report)
            self.assertIn("System Loss Review", report)
            self.assertIn("System-gap breakdown", report)
            self.assertIn("Improvement queue", report)
            self.assertIn("Active gap missions", report)
            self.assertIn("T3 Comparison Scorecard", report)
            self.assertIn("T3 Deficits To Close", report)
            self.assertIn("T3 Benchmark Basis", report)
            self.assertIn("Must-beat status", report)
            self.assertIn("Blocking gap:", report)
            self.assertIn("Behind T3 by", report)
            self.assertIn("Project Progress", report)
            self.assertIn("NAS Live-State Evidence", report)
            self.assertIn("NAS Storage Pressure", report)
            self.assertIn("Live Mission Output Quality", report)
            self.assertIn("Treat this section as stronger evidence than stale local workspace rows", report)
            self.assertIn("Build a legal defensive RF/wireless mapping", report)
            self.assertIn("Build F1 telemetry analytics trust sample", report)
            self.assertIn("mission writes and proof artifacts are at risk", report)
            self.assertIn("NAS mission start/resume is blocked", report)
            self.assertIn("completed live mission(s) are transcript-only", report)
            self.assertIn("Active launched missions", report)
            self.assertIn("Source mode: `authenticated_live_nas`", report)
            self.assertIn("Active launched mission count: `3`", report)
            self.assertIn(str(newer_live_report.resolve()), report)
            self.assertNotIn(str(live_report.resolve()), report)
            self.assertNotIn("Hermes is building the RF prototype artifacts.", report)
            self.assertIn("Operator Confidence Calibration", report)
            self.assertIn("Active sampling missions: `1`", report)
            self.assertIn("mission_rf", report)
            self.assertIn("Route repair plan", report)
            self.assertIn("Hermes harness; planner/verifier use openai-codex gpt-5.5 high", report)
            self.assertIn("Red-Team Escalation Evidence", report)
            self.assertIn("History rows: `1`", report)
            self.assertIn("hackaprompt", report)
            self.assertIn("Difficulty: `3` -> `4`", report)
            self.assertIn("control-room performance budget present", report)
            self.assertIn("v0.0.25-nightly.20260602.439", report)
            self.assertIn("current release evidence observes", report)
            self.assertNotIn("latest observed pre-release as of 2026-05-29", report)
            self.assertIn("Release evidence checked at", report)
            self.assertIn("api.github.com/repos/pingdotgg/t3code/releases", report)
            self.assertEqual(payload["reportPath"], str(output.resolve()))
            self.assertTrue(payload["badFirst"])
            self.assertIn("t3Deficits", payload)
            self.assertEqual(payload["nasStoragePressureEvidence"]["status"], "critical")
            self.assertEqual(payload["liveMissionOutputQualityEvidence"]["status"], "needs_artifact_repair")
            self.assertEqual(payload["liveMissionOutputQualityEvidence"]["weakMissionRows"][0]["missionId"], "mission_f1")
            self.assertEqual(payload["systemLossBreakdown"]["schema"], "fluxio.system_loss_breakdown.v1")
            self.assertTrue(payload["systemLossBreakdown"]["drivers"])
            self.assertIn(
                "NAS storage and mission-write headroom",
                [item["category"] for item in payload["systemLossBreakdown"]["drivers"]],
            )
            self.assertIn(
                "Mission outputs and artifact proof",
                [item["category"] for item in payload["systemLossBreakdown"]["drivers"]],
            )
            self.assertEqual(payload["systemLossBreakdown"]["missionSurface"]["progressSourceCount"], 1)
            self.assertGreaterEqual(payload["systemLossBreakdown"]["missionSurface"]["projectCount"], 1)
            self.assertIn("NAS storage pressure", [item["title"] for item in payload["badFirst"]])
            self.assertIn("Mission output proof", [item["title"] for item in payload["badFirst"]])
            self.assertNotIn("Optional harness parity", [item["title"] for item in payload["badFirst"]])
            self.assertNotIn(
                "Optional harness parity",
                [item["category"] for item in payload["improvementQueue"]],
            )
            self.assertTrue(payload["improvementQueue"])
            self.assertEqual(
                payload["improvementQueue"][0]["schema"],
                "fluxio.system_improvement_queue_item.v1",
            )
            self.assertTrue(payload["activeGapMissions"])
            self.assertEqual(
                payload["activeGapMissions"][0]["schema"],
                "fluxio.active_gap_mission.v1",
            )
            self.assertIn(
                payload["activeGapMissions"][0]["sourceMode"],
                {"authenticated_live_nas", "local_agent_control"},
            )
            self.assertIn("routeTrustMaturity", payload)
            self.assertIn("redTeamEscalationEvidence", payload)
            self.assertEqual(payload["redTeamEscalationEvidence"]["summary"]["runCount"], 1)
            self.assertTrue(payload["redTeamEscalationEvidence"]["summary"]["shouldEscalate"])
            self.assertIn("needs_route_repair", payload["summary"])
            self.assertIn("Red-team escalation has", payload["summary"])

    def test_completed_mission_without_runtime_output_fails_hard_artifact_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build a previewable F1 artifact",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "completed"

            loop = sync_mission_state_snapshot(mission)
            gate = mission_hard_artifact_gate(mission)

            self.assertFalse(gate["passed"])
            self.assertEqual(mission.state.status, "verification_failed")
            self.assertIn("hard_artifact_gate", mission.state.verification_failures)
            self.assertEqual(loop["currentCyclePhase"], "replan")
            self.assertIn("artifact repair", mission.proof.summary)

    def test_completed_mission_with_runtime_output_still_needs_artifact_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build a previewable RF report",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "completed"
            mission.delegated_runtime_sessions.append(
                DelegatedRuntimeSession(
                    delegated_id="delegated_rf",
                    runtime_id="hermes",
                    launch_command="hermes run",
                    status="completed",
                    latest_events=[
                        {
                            "kind": "runtime.output",
                            "message": "Generated RF mapping report artifact with receiver table and verification notes.",
                            "status": "completed",
                        }
                    ],
                )
            )

            sync_mission_state_snapshot(mission)
            gate = mission_hard_artifact_gate(mission)

            self.assertFalse(gate["passed"])
            self.assertEqual(mission.state.status, "verification_failed")
            self.assertEqual(gate["runtimeOutputCount"], 1)

    def test_mission_detail_hard_gate_counts_attached_hermes_runtime_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build a legal defensive RF mapping report",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            runtime_transcript = {
                "schema": "fluxio.runtime_transcript.v1",
                "status": "attached",
                "messages": [
                    {
                        "id": "session-timeline:rf:1",
                        "label": "Hermes session transcript",
                        "title": "Fluxio Mission Note - Step: Implement smallest vertical slice",
                        "detail": (
                            "Runtime output: ## Fluxio Mission Note - Step: Implement "
                            "smallest vertical slice - Objective: Build a legal defensive "
                            "RF/wireless mapping discovery tool concept and prototype."
                        ),
                        "runtimeOutput": True,
                    }
                ],
            }

            gate = mission_hard_artifact_gate(
                mission,
                runtime_transcript=runtime_transcript,
            )

            self.assertFalse(gate["passed"])
            self.assertEqual(gate["runtimeOutputCount"], 1)
            self.assertIn("RF/wireless mapping", gate["runtimeOutputEvidence"][0]["detail"])

    def test_mission_detail_hard_gate_counts_hermes_mission_artifact_file_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build a legal defensive RF mapping report",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            artifact_path = (
                "/volume1/Saclay/projects/overnight-discovery-lab/.agent_control/"
                "mission_artifacts/draft-implementation-plan-with-milestones.md"
            )

            gate = mission_hard_artifact_gate(
                mission,
                runtime_transcript={
                    "schema": "fluxio.runtime_transcript.v1",
                    "status": "attached",
                    "messages": [
                        {
                            "id": "session-timeline:rf:1",
                            "label": "Hermes session transcript",
                            "title": "Create mission artifact",
                            "detail": f"Action: file_write · Target: {artifact_path}",
                            "technicalDetail": json.dumps(
                                {
                                    "kind": "file_write",
                                    "target_path": artifact_path,
                                }
                            ),
                        }
                    ],
                },
            )

            self.assertFalse(gate["passed"])
            self.assertGreaterEqual(gate["artifactCount"], 1)
            self.assertEqual(gate["runtimeOutputCount"], 0)
            self.assertIn("mission_artifacts", gate["artifactEvidence"][0]["detail"])

    def test_mission_hard_gate_counts_persisted_action_history_file_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build an F1 telemetry report",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            artifact_path = str(
                root
                / ".agent_control"
                / "mission_artifacts"
                / "implement-smallest-vertical-slice.md"
            )
            mission.action_history = [
                {
                    "proposal": {
                        "kind": "file_write",
                        "target_path": artifact_path,
                    },
                    "result": {
                        "ok": True,
                        "stdout": f"Updated {artifact_path}",
                        "result_summary": "File mutation completed.",
                    },
                }
            ]

            gate = mission_hard_artifact_gate(mission)

            self.assertFalse(gate["passed"])
            self.assertGreaterEqual(gate["artifactCount"], 1)
            self.assertIn("mission_artifacts", gate["artifactEvidence"][0]["detail"])

    def test_mission_hard_gate_counts_standard_manifest_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build a defensive red-team route-trust proof artifact",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            artifact_root = root / ".agent_control" / "mission_artifacts" / mission.mission_id
            proof_root = artifact_root / "proof"
            proof_root.mkdir(parents=True)
            (artifact_root / "index.html").write_text(
                "<!doctype html><title>Security proof</title>",
                encoding="utf-8",
            )
            (artifact_root / "artifact_manifest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.mission_artifact_manifest.v1",
                        "artifacts": [
                            {
                                "artifactPath": str(artifact_root / "index.html"),
                                "previewUrl": f"/api/artifact?path={artifact_root / 'index.html'}",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (proof_root / "runtime_output.txt").write_text(
                (
                    "Security route-trust proof produced 161 blocked attempts at level 5 "
                    "pressure 225, then recorded the redaction hardening regression result."
                ),
                encoding="utf-8",
            )
            (proof_root / "proof_digest.json").write_text(
                json.dumps(
                    {
                        "summary": "Defensive route-trust sample completed with useful proof artifacts.",
                        "runtimeOutputBody": (
                            "Latest benchmark reached 161/161 blocked attempts and validated "
                            "the aggregate-only export redaction path."
                        ),
                    }
                ),
                encoding="utf-8",
            )

            gate = mission_hard_artifact_gate(mission, root=root)

            self.assertTrue(gate["passed"])
            self.assertGreaterEqual(gate["artifactCount"], 2)
            self.assertGreaterEqual(gate["runtimeOutputCount"], 1)
            self.assertIn("mission_artifacts", gate["artifactEvidence"][0]["detail"])

    def test_mission_detail_hard_gate_counts_proof_artifact_event_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Improve one beginner-facing Fluxio workflow end",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            artifact_path = str(
                root
                / ".agent_control"
                / "mission_artifacts"
                / mission.mission_id
                / "index.html"
            )
            pathlib.Path(artifact_path).parent.mkdir(parents=True)
            pathlib.Path(artifact_path).write_text(
                "<!doctype html><title>Research dashboard</title>",
                encoding="utf-8",
            )
            runtime_output_path = str(
                root
                / ".agent_control"
                / "mission_artifacts"
                / mission.mission_id
                / "proof"
                / "runtime_output.txt"
            )
            gate = mission_hard_artifact_gate(
                mission,
                mission_events=[
                    {
                        "kind": "proof.artifact.updated",
                        "message": (
                            "Improved beginner Starter mission launch clarity end to end "
                            "with UI receipt, tutorial update, focused test, build, and served artifact."
                        ),
                        "data": {
                            "artifactPath": artifact_path,
                            "servedUrl": f"/api/artifact?path={artifact_path}",
                            "runtimeOutput": runtime_output_path,
                        },
                    }
                ],
            )

            self.assertTrue(gate["passed"])
            self.assertGreaterEqual(gate["artifactCount"], 1)
            self.assertGreaterEqual(gate["runtimeOutputCount"], 1)
            self.assertIn("proof.artifact.updated", gate["runtimeOutputEvidence"][0]["source"])

    def test_operator_completed_artifact_passed_mission_stays_terminal_after_runtime_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Create a defensive public-source research dashboard",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            artifact_path = str(
                root
                / ".agent_control"
                / "mission_artifacts"
                / mission.mission_id
                / "index.html"
            )
            pathlib.Path(artifact_path).parent.mkdir(parents=True)
            pathlib.Path(artifact_path).write_text(
                "<!doctype html><title>Research dashboard</title>",
                encoding="utf-8",
            )
            mission.state.status = "running"
            mission.state.operator_value_feedback = {
                "schema": "fluxio.mission_operator_value_feedback.v1",
                "recordedAt": "2026-06-02T08:22:07Z",
                "score": 83,
                "outcome": "useful",
                "source": "mission_action_complete",
                "trustSignal": "promote",
                "routeTrustTaskType": "research_analysis",
            }
            mission.proof.summary = "Mission marked complete by operator with 83 value score."
            mission.proof.artifacts.append(f"/api/artifact?path={artifact_path}")
            session = DelegatedRuntimeSession(
                delegated_id="delegate_research",
                runtime_id="hermes",
                launch_command="hermes run",
                status="running",
                latest_events=[
                    {
                        "kind": "runtime.output",
                        "message": (
                            "Built the public-source dashboard artifact with provenance, "
                            "uncertainty labels, and verifier notes."
                        ),
                        "status": "completed",
                    }
                ],
            )
            mission.delegated_runtime_sessions = [session]

            refresh_mission_runtime_state(mission, [session])
            sync_mission_state_snapshot(mission)
            gate = mission_hard_artifact_gate(mission)

            self.assertTrue(gate["passed"])
            self.assertEqual(mission.state.status, "completed")
            self.assertEqual(mission.state.planner_loop_status, "completed")
            self.assertEqual(mission.state.last_runtime_event, "completed")
            self.assertEqual(mission.proof.pending_approvals, [])

    def test_sync_mission_state_clears_repaired_hard_artifact_gate_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build an F1 telemetry report",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            artifact_path = str(
                root
                / ".agent_control"
                / "mission_artifacts"
                / "implement-smallest-vertical-slice.md"
            )
            mission.state.status = "verification_failed"
            mission.state.stop_reason = "artifact_gate_failed"
            mission.state.last_error = "Hard artifact gate failed: no concrete runtime-output body or served artifact was recorded."
            mission.state.verification_failures = ["hard_artifact_gate"]
            mission.proof.failed_checks = ["hard_artifact_gate"]
            mission.proof.blocked_by = [
                "Hard artifact gate failed: no concrete runtime-output body or served artifact was recorded."
            ]
            mission.action_history = [
                {
                    "proposal": {
                        "kind": "file_write",
                        "target_path": artifact_path,
                    },
                    "result": {
                        "ok": True,
                        "stdout": f"Updated {artifact_path}",
                    },
                }
            ]

            sync_mission_state_snapshot(mission)

            self.assertEqual(mission.state.status, "completed")
            self.assertEqual(mission.state.verification_failures, [])
            self.assertEqual(mission.proof.failed_checks, [])
            self.assertEqual(mission.proof.blocked_by, [])

    def test_mission_detail_hard_gate_ignores_trace_only_hermes_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build a first usable prototype/report F1",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )

            gate = mission_hard_artifact_gate(
                mission,
                runtime_transcript={
                    "status": "attached",
                    "messages": [
                        {
                            "id": "session-timeline:f1:1",
                            "label": "Hermes session transcript",
                            "title": "Inspect diff surface for Prepare rollout notes",
                            "detail": "Action: git_diff · Command: git diff --stat",
                            "runtimeOutput": False,
                        }
                    ],
                },
            )

            self.assertFalse(gate["passed"])
            self.assertEqual(gate["runtimeOutputCount"], 0)

    def test_mission_artifact_repair_plan_turns_transcript_only_missions_into_hard_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            now_iso = datetime.now(timezone.utc).isoformat()
            report = root / "tmp-ui-checks" / "authenticated-live-agent" / "f1-output-check.json"
            report.parent.mkdir(parents=True)
            report.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.authenticated_live_agent.v1",
                        "checkedAt": now_iso,
                        "ok": True,
                        "checks": [
                            {
                                "checkId": "selected-live-mission",
                                "passed": True,
                                "missionId": "mission_f1",
                                "title": "Build F1 telemetry analytics trust sample",
                                "status": "completed",
                            },
                            {
                                "checkId": "selected-mission-detail-api",
                                "passed": True,
                                "missionId": "mission_f1",
                                "agentMessageCount": 12,
                            },
                            {
                                "checkId": "runtime-output-visible-in-thread",
                                "passed": True,
                                "runtimeOutputCount": 0,
                            },
                            {
                                "checkId": "live-workbench-proof-band-visible",
                                "passed": True,
                                "proofBandText": "LIVE WORKBENCH PROOF\n12\nMESSAGES\nRUNTIME REPORTS\n0\nARTIFACTS\nNONE RETURNED",
                            },
                        ],
                        "summary": {
                            "selectedMission": {
                                "mission_id": "mission_f1",
                                "title": "Build F1 telemetry analytics trust sample",
                                "runtime_id": "hermes",
                                "status": "completed",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            plan = build_repair_plan(root)

            self.assertEqual(plan["schema"], "fluxio.mission_artifact_repair_plan.v1")
            self.assertEqual(plan["status"], "repairs_ready")
            self.assertEqual(plan["weakMissionCount"], 1)
            self.assertEqual(plan["repairs"][0]["missionId"], "mission_f1")
            self.assertEqual(plan["repairs"][0]["action"], "resume_with_hard_artifact_gate")
            self.assertIn("Do not mark the mission completed", plan["repairs"][0]["resumePrompt"])
            self.assertIn("Workbench artifact execution", plan["repairs"][0]["hardGateChecks"][2])

    def test_mission_artifact_repair_plan_includes_failed_live_detail_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            control = root / ".agent_control"
            control.mkdir()
            now_iso = datetime.now(timezone.utc).isoformat()
            (control / "live_mission_detail_status_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_mission_detail_status.v1",
                        "checkedAt": now_iso,
                        "maxAgeSeconds": 21600,
                        "missionRows": [
                            {
                                "missionId": "mission_f1_failed",
                                "title": "Build a first usable prototype/report F1",
                                "runtime": "hermes",
                                "status": "verification_failed",
                                "agentMessages": 3,
                                "runtimeTranscript": {"status": "missing_transcript"},
                                "artifactGate": {
                                    "passed": False,
                                    "status": "missing_required_output",
                                    "runtimeOutputCount": 0,
                                    "artifactCount": 0,
                                },
                            },
                            {
                                "missionId": "mission_rf_running",
                                "title": "Build RF mapping",
                                "runtime": "hermes",
                                "status": "running",
                                "agentMessages": 22,
                                "runtimeTranscript": {"status": "attached"},
                                "artifactGate": {
                                    "passed": True,
                                    "status": "passed",
                                    "runtimeOutputCount": 4,
                                    "artifactCount": 2,
                                },
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            plan = build_repair_plan(root)

            self.assertEqual(plan["status"], "repairs_ready")
            self.assertEqual(plan["repairMissionCount"], 1)
            self.assertEqual(plan["repairs"][0]["missionId"], "mission_f1_failed")
            self.assertEqual(plan["repairs"][0]["artifactGateStatus"], "missing_required_output")
            self.assertEqual(plan["repairs"][0]["runtimeTranscriptStatus"], "missing_transcript")
            self.assertIn("no concrete runtime-output body", plan["repairs"][0]["repairReason"])
            self.assertNotIn("--write", plan["repairs"][0]["verificationCommand"])

    def test_mission_artifact_repair_plan_includes_completed_live_detail_rows_missing_hard_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            control = root / ".agent_control"
            control.mkdir()
            now_iso = datetime.now(timezone.utc).isoformat()
            (control / "live_mission_detail_status_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_mission_detail_status.v1",
                        "checkedAt": now_iso,
                        "maxAgeSeconds": 21600,
                        "missionRows": [
                            {
                                "missionId": "mission_completed_no_gate",
                                "title": "Build a polished Builder progress surface",
                                "runtime": "hermes",
                                "status": "completed",
                                "agentMessages": 30,
                                "runtimeTranscript": {"status": "attached"},
                                "artifactGate": {
                                    "passed": False,
                                    "status": "missing_required_output",
                                    "runtimeOutputCount": 0,
                                    "artifactCount": 0,
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            plan = build_repair_plan(root)

            self.assertEqual(plan["status"], "repairs_ready")
            self.assertEqual(plan["repairMissionCount"], 1)
            self.assertEqual(plan["repairs"][0]["missionId"], "mission_completed_no_gate")
            self.assertEqual(plan["repairs"][0]["status"], "completed")
            self.assertIn("no concrete runtime-output body", plan["repairs"][0]["repairReason"])
            self.assertIn("no served artifact or artifact path", plan["repairs"][0]["repairReason"])

    def test_mission_artifact_repair_plan_allows_passed_gate_with_runtime_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            control = root / ".agent_control"
            control.mkdir()
            now_iso = datetime.now(timezone.utc).isoformat()
            (control / "live_mission_detail_status_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_mission_detail_status.v1",
                        "checkedAt": now_iso,
                        "maxAgeSeconds": 21600,
                        "missionRows": [
                            {
                                "missionId": "mission_rf",
                                "title": "Build a legal defensive RF/wireless mapping",
                                "runtime": "hermes",
                                "status": "completed",
                                "agentMessages": 46,
                                "runtimeTranscript": {"status": "attached"},
                                "artifactGate": {
                                    "passed": True,
                                    "status": "passed",
                                    "runtimeOutputCount": 36,
                                    "artifactCount": 0,
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            plan = build_repair_plan(root)
            quality = _load_live_mission_output_quality_evidence(root)

            self.assertEqual(plan["status"], "passed")
            self.assertEqual(plan["repairMissionCount"], 0)
            self.assertEqual(quality["status"], "passed")
            self.assertEqual(quality["repairMissionRows"], [])

    def test_mission_artifact_repair_plan_flags_passed_gate_with_missing_runtime_transcript_and_no_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            control = root / ".agent_control"
            control.mkdir()
            now_iso = datetime.now(timezone.utc).isoformat()
            (control / "live_mission_detail_status_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_mission_detail_status.v1",
                        "checkedAt": now_iso,
                        "maxAgeSeconds": 21600,
                        "missionRows": [
                            {
                                "missionId": "mission_builder_running",
                                "title": "Build a polished phone/tablet Builder progress",
                                "runtime": "hermes",
                                "status": "running",
                                "agentMessages": 56,
                                "realRuntimeReportCount": 4,
                                "realRuntimeReportCountKnown": True,
                                "runtimeTranscript": {"status": "missing_runtime_output"},
                                "artifactGate": {
                                    "passed": True,
                                    "status": "passed",
                                    "runtimeOutputCount": 46,
                                    "artifactCount": 0,
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            plan = build_repair_plan(root)
            quality = _load_live_mission_output_quality_evidence(root)

            self.assertEqual(quality["status"], "needs_artifact_repair")
            self.assertEqual(quality["repairMissionRows"][0]["missionId"], "mission_builder_running")
            self.assertEqual(quality["repairMissionRows"][0]["runtimeTranscriptStatus"], "missing_runtime_output")
            self.assertEqual(plan["status"], "repairs_ready")
            self.assertEqual(plan["repairMissionCount"], 1)
            self.assertEqual(plan["repairs"][0]["missionId"], "mission_builder_running")
            self.assertIn("no served artifact or artifact path", plan["repairs"][0]["repairReason"])

    def test_mission_artifact_repair_plan_attaches_evidence_screenshot_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            control = root / ".agent_control"
            control.mkdir()
            screenshot_dir = control / "mission_result_screenshots"
            screenshot_dir.mkdir()
            screenshot_path = screenshot_dir / "mission_f1_failed-evidence.png"
            screenshot_path.write_bytes(b"png")
            now_iso = datetime.now(timezone.utc).isoformat()
            (control / "mission_evidence_manifest_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.mission_evidence_screenshot_manifest.v1",
                        "generatedAt": now_iso,
                        "sourceCheckedAt": now_iso,
                        "screenshotCount": 1,
                        "screenshots": [
                            {
                                "missionId": "mission_f1_failed",
                                "screenshotPath": str(screenshot_path),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (control / "live_mission_detail_status_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_mission_detail_status.v1",
                        "checkedAt": now_iso,
                        "maxAgeSeconds": 21600,
                        "missionRows": [
                            {
                                "missionId": "mission_f1_failed",
                                "title": "Build a first usable prototype/report F1",
                                "runtime": "hermes",
                                "status": "verification_failed",
                                "agentMessages": 3,
                                "runtimeTranscript": {"status": "missing_transcript"},
                                "artifactGate": {
                                    "passed": False,
                                    "status": "missing_required_output",
                                    "runtimeOutputCount": 0,
                                    "artifactCount": 0,
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            plan = build_repair_plan(root)

            self.assertEqual(
                plan["missionEvidenceScreenshotManifest"]["screenshotCount"],
                1,
            )
            self.assertEqual(
                plan["repairs"][0]["sourceScreenshotPath"],
                str(screenshot_path.resolve()),
            )

    def test_mission_artifact_repair_plan_blocks_resume_when_nas_storage_is_critical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            control = root / ".agent_control"
            control.mkdir()
            now_iso = datetime.now(timezone.utc).isoformat()
            (control / "nas_storage_pressure_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.nas_storage_pressure.v1",
                        "checkedAt": now_iso,
                        "maxAgeSeconds": 21600,
                        "host": "100.125.54.118",
                        "mount": "/volume1/Saclay",
                        "status": "critical",
                        "probeTimedOut": True,
                        "usedPercent": 100,
                        "availableBytes": 0,
                        "source": "bounded_ssh_timeout",
                    }
                ),
                encoding="utf-8",
            )
            (control / "live_mission_detail_status_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_mission_detail_status.v1",
                        "checkedAt": now_iso,
                        "maxAgeSeconds": 21600,
                        "missionRows": [
                            {
                                "missionId": "mission_f1_failed",
                                "title": "Build a first usable prototype/report F1",
                                "runtime": "hermes",
                                "status": "verification_failed",
                                "agentMessages": 3,
                                "runtimeTranscript": {"status": "missing_transcript"},
                                "artifactGate": {
                                    "passed": False,
                                    "status": "missing_required_output",
                                    "runtimeOutputCount": 0,
                                    "artifactCount": 0,
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            plan = build_repair_plan(root)

            self.assertEqual(plan["status"], "repairs_blocked_by_nas_storage")
            self.assertEqual(plan["storagePreflight"]["status"], "blocked")
            self.assertFalse(plan["storagePreflight"]["canResume"])
            self.assertFalse(plan["repairs"][0]["canResumeNow"])
            self.assertEqual(plan["repairs"][0]["resumeBlockedBy"], ["nas_storage_pressure"])
            self.assertIn("Do not resume", plan["nextAction"])

    def test_audit_surfaces_repair_plan_when_weak_rows_are_empty(self) -> None:
        categories = [
            AuditCategory(
                category="Proof, verification, and trust",
                score_out_of_20=12,
                t3_reference_score_out_of_20=14,
                verdict="needs proof",
                evidence=[],
                gaps=["hard artifact gate is not repaired"],
                next_moves=["repair failed live missions"],
            )
        ]
        repair_plan = {
            "schema": "fluxio.mission_artifact_repair_plan.v1",
            "status": "repairs_ready",
            "repairMissionCount": 1,
            "repairs": [
                {
                    "missionId": "mission_f1_failed",
                    "title": "Build a first usable prototype/report F1",
                    "status": "verification_failed",
                }
            ],
            "nextAction": "Resume the listed missions with the hard artifact gate.",
        }

        bad_first = _bad_first(
            categories,
            {},
            [],
            live_mission_output_quality={"weakMissionRows": []},
            mission_artifact_repair_plan=repair_plan,
        )
        breakdown = _system_loss_breakdown(
            categories,
            {},
            [],
            live_mission_output_quality={"weakMissionRows": []},
            mission_artifact_repair_plan=repair_plan,
        )

        self.assertIn("Mission output proof", [item["title"] for item in bad_first])
        self.assertIn(
            "Mission outputs and artifact proof",
            [item["category"] for item in breakdown["drivers"]],
        )
        proof_driver = next(
            item
            for item in breakdown["drivers"]
            if item["category"] == "Mission outputs and artifact proof"
        )
        self.assertIn("mission_f1_failed", proof_driver["evidence"])

    def test_live_mission_detail_status_overrides_stale_weak_screenshot_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            now_iso = datetime.now(timezone.utc).isoformat()
            report = root / "tmp-ui-checks" / "authenticated-live-agent" / "stale-check.json"
            report.parent.mkdir(parents=True)
            report.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.authenticated_live_agent.v1",
                        "checkedAt": now_iso,
                        "checks": [
                            {
                                "checkId": "selected-live-mission",
                                "missionId": "mission_rf",
                                "title": "Build RF mapping",
                                "status": "completed",
                            },
                            {
                                "checkId": "selected-mission-detail-api",
                                "missionId": "mission_rf",
                                "agentMessageCount": 12,
                            },
                            {
                                "checkId": "runtime-output-visible-in-thread",
                                "runtimeOutputCount": 0,
                            },
                            {
                                "checkId": "live-workbench-proof-band-visible",
                                "proofBandText": "ARTIFACTS\nNONE RETURNED",
                            },
                        ],
                        "summary": {
                            "selectedMission": {
                                "mission_id": "mission_rf",
                                "title": "Build RF mapping",
                                "runtime_id": "hermes",
                                "status": "completed",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            control = root / ".agent_control"
            control.mkdir()
            (control / "live_mission_detail_status_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_mission_detail_status.v1",
                        "checkedAt": now_iso,
                        "missionRows": [
                            {
                                "missionId": "mission_rf",
                                "title": "Build RF mapping",
                                "runtime": "hermes",
                                "status": "running",
                                "agentMessages": 22,
                                "runtimeTranscript": {"status": "attached"},
                                "artifactGate": {
                                    "passed": True,
                                    "status": "passed",
                                    "runtimeOutputCount": 4,
                                    "artifactCount": 0,
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            quality = _load_live_mission_output_quality_evidence(root)

            self.assertEqual(quality["status"], "passed")
            self.assertEqual(quality["weakMissionRows"], [])
            self.assertEqual(quality["checkedMissionRows"][0]["status"], "running")
            self.assertEqual(quality["checkedMissionRows"][0]["runtimeOutputCount"], 4)
            self.assertFalse(quality["checkedMissionRows"][0]["realRuntimeReportCountKnown"])
            self.assertIn("predates real-runtime-report counting", quality["checkedMissionRows"][0]["detail"])

    def test_live_mission_detail_status_marks_bookkeeping_only_agent_messages_weak(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            control = root / ".agent_control"
            control.mkdir()
            now_iso = datetime.now(timezone.utc).isoformat()
            (control / "live_mission_detail_status_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_mission_detail_status.v1",
                        "checkedAt": now_iso,
                        "maxAgeSeconds": 21600,
                        "missionRows": [
                            {
                                "missionId": "mission_bookkeeping_only",
                                "title": "Build a polished phone/tablet Builder progress",
                                "runtime": "hermes",
                                "status": "running",
                                "agentMessages": 30,
                                "realRuntimeReportCount": 0,
                                "realRuntimeReportCountKnown": True,
                                "traceOnlyMessageCount": 30,
                                "runtimeTranscript": {"status": "missing_transcript"},
                                "artifactGate": {
                                    "passed": True,
                                    "status": "passed",
                                    "runtimeOutputCount": 0,
                                    "artifactCount": 1,
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            detail_status = _load_live_mission_detail_status_evidence(root)
            row = detail_status["missionRows"][0]

            self.assertTrue(row["weakOutput"])
            self.assertEqual(row["realRuntimeReportCount"], 0)
            self.assertEqual(row["traceOnlyMessageCount"], 30)
            self.assertIn("none are real runtime report rows", row["detail"])

    def test_live_mission_detail_status_counts_real_runtime_reports_as_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            control = root / ".agent_control"
            control.mkdir()
            now_iso = datetime.now(timezone.utc).isoformat()
            (control / "live_mission_detail_status_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_mission_detail_status.v1",
                        "checkedAt": now_iso,
                        "maxAgeSeconds": 21600,
                        "missionRows": [
                            {
                                "missionId": "mission_f1",
                                "title": "Build an F1 telemetry analytics prototype",
                                "runtime": "hermes",
                                "status": "completed",
                                "agentMessages": 17,
                                "realRuntimeReportCount": 4,
                                "realRuntimeReportCountKnown": True,
                                "traceOnlyMessageCount": 13,
                                "runtimeTranscript": {"status": "missing_transcript"},
                                "artifactGate": {
                                    "passed": True,
                                    "status": "passed",
                                    "runtimeOutputCount": 0,
                                    "artifactCount": 4,
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            detail_status = _load_live_mission_detail_status_evidence(root)
            quality = _load_live_mission_output_quality_evidence(root)

            self.assertEqual(detail_status["missionRows"][0]["runtimeOutputCount"], 4)
            self.assertEqual(quality["checkedMissionRows"][0]["runtimeOutputCount"], 4)
            validation = _live_cross_category_outcome_validation(quality, required_categories=1)
            self.assertEqual(validation["status"], "passed")
            self.assertEqual(validation["categories"][0]["taskFamily"], "f1_data_analytics")

    def test_live_mission_detail_status_ignores_browser_only_stale_missions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            now_iso = datetime.now(timezone.utc).isoformat()
            report = root / "tmp-ui-checks" / "authenticated-live-agent" / "old-f1-check.json"
            report.parent.mkdir(parents=True)
            report.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.authenticated_live_agent.v1",
                        "checkedAt": now_iso,
                        "checks": [
                            {
                                "checkId": "selected-live-mission",
                                "missionId": "mission_old_f1",
                                "title": "Old F1 mission",
                                "status": "completed",
                            },
                            {
                                "checkId": "selected-mission-detail-api",
                                "missionId": "mission_old_f1",
                                "agentMessageCount": 22,
                            },
                            {
                                "checkId": "runtime-output-visible-in-thread",
                                "runtimeOutputCount": 0,
                            },
                            {
                                "checkId": "live-workbench-proof-band-visible",
                                "proofBandText": "Artifacts reported",
                            },
                        ],
                        "summary": {
                            "selectedMission": {
                                "mission_id": "mission_old_f1",
                                "title": "Old F1 mission",
                                "runtime_id": "hermes",
                                "status": "completed",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            control = root / ".agent_control"
            control.mkdir()
            (control / "live_mission_detail_status_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_mission_detail_status.v1",
                        "checkedAt": now_iso,
                        "missionRows": [
                            {
                                "missionId": "mission_current_rf",
                                "title": "Current RF mission",
                                "runtime": "hermes",
                                "status": "running",
                                "agentMessages": 12,
                                "runtimeTranscript": {"status": "attached"},
                                "artifactGate": {
                                    "passed": True,
                                    "status": "passed",
                                    "runtimeOutputCount": 4,
                                    "artifactCount": 2,
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            quality = _load_live_mission_output_quality_evidence(root)

            self.assertEqual(quality["status"], "passed")
            self.assertEqual(
                [row["missionId"] for row in quality["checkedMissionRows"]],
                ["mission_current_rf"],
            )
            self.assertEqual(quality["repairMissionRows"], [])

    def test_failed_live_detail_rows_make_output_quality_need_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            now_iso = datetime.now(timezone.utc).isoformat()
            control = root / ".agent_control"
            control.mkdir()
            (control / "live_mission_detail_status_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_mission_detail_status.v1",
                        "checkedAt": now_iso,
                        "maxAgeSeconds": 21600,
                        "missionRows": [
                            {
                                "missionId": "mission_f1_failed",
                                "title": "Build a first usable prototype/report F1",
                                "runtime": "hermes",
                                "status": "verification_failed",
                                "agentMessages": 3,
                                "runtimeTranscript": {"status": "missing_transcript"},
                                "artifactGate": {
                                    "passed": False,
                                    "status": "missing_required_output",
                                    "runtimeOutputCount": 0,
                                    "artifactCount": 0,
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            quality = _load_live_mission_output_quality_evidence(root)

            self.assertEqual(quality["status"], "needs_artifact_repair")
            self.assertEqual(quality["weakMissionRows"], [])
            self.assertEqual(quality["repairMissionRows"][0]["missionId"], "mission_f1_failed")
            self.assertEqual(
                quality["repairMissionRows"][0]["artifactGateStatus"],
                "missing_required_output",
            )
            self.assertIn("missing runtime-output", quality["nextAction"])

    def test_completed_live_detail_rows_without_runtime_output_need_repair_even_with_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            now_iso = datetime.now(timezone.utc).isoformat()
            control = root / ".agent_control"
            control.mkdir()
            (control / "live_mission_detail_status_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_mission_detail_status.v1",
                        "checkedAt": now_iso,
                        "maxAgeSeconds": 21600,
                        "missionRows": [
                            {
                                "missionId": "mission_completed_missing_runtime",
                                "title": "Build F1 telemetry analytics",
                                "runtime": "hermes",
                                "status": "completed",
                                "agentMessages": 22,
                                "runtimeTranscript": {"status": "attached"},
                                "artifactGate": {
                                    "passed": False,
                                    "status": "missing_required_output",
                                    "runtimeOutputCount": 0,
                                    "artifactCount": 1,
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            quality = _load_live_mission_output_quality_evidence(root)

            self.assertEqual(quality["status"], "needs_artifact_repair")
            self.assertEqual(quality["weakMissionRows"][0]["missionId"], "mission_completed_missing_runtime")
            self.assertEqual(quality["repairMissionRows"][0]["missionId"], "mission_completed_missing_runtime")
            self.assertEqual(quality["repairMissionRows"][0]["artifactStatus"], "reported")

    def test_nas_storage_cleanup_plan_parses_only_bounded_generated_candidates(self) -> None:
        stdout = "\n".join(
            [
                "DF|- 3829365997568 3829365997568 0 100% /volume1/Saclay",
                "DU|535000|/volume1/Saclay/projects/syntelos/current/.agent_control/mission_async",
                "DU|142000|/volume1/Saclay/projects/syntelos/current/.agent_control/release_artifacts",
                "MISS|/volume1/Saclay/projects/syntelos/current/.agent_control/tmp-ui-checks",
                "EXTDU|816497060|/volume1/Duncan/MacBook Air.sparsebundle",
                "EXTTIMEOUT|/volume1/Duncan",
                "VOLDU|859832320|/volume1/@appdata/ContainerManager",
                "VOLDU|818937856|/volume1/@appdata/ContainerManager/all_shares",
                "VOLTIMEOUT|/volume1/@synologydrive",
                "BTRFS|Data, single: total=3.48TiB, used=3.48TiB",
            ]
        )

        plan = _parse_remote_probe(stdout, host="100.125.54.118")

        self.assertEqual(plan["schema"], "fluxio.nas_storage_cleanup_plan.v1")
        self.assertEqual(plan["storageStatus"], "critical")
        self.assertEqual(plan["availableBytes"], 0)
        self.assertEqual(plan["candidateCount"], 2)
        self.assertFalse(plan["destructiveActionsExecuted"])
        self.assertTrue(plan["safeMode"])
        self.assertEqual(plan["cleanupCandidates"][0]["destructiveAction"], "operator_review_required")
        self.assertIn("tmp-ui-checks", plan["missingAllowlistPaths"][0])
        self.assertEqual(plan["suspectedExternalUsage"][0]["path"], "/volume1/Duncan/MacBook Air.sparsebundle")
        self.assertEqual(plan["suspectedExternalUsage"][0]["destructiveAction"], "operator_review_required")
        self.assertEqual(plan["largestSuspectedExternalPath"], "/volume1/Duncan/MacBook Air.sparsebundle")
        self.assertIn("/volume1/Duncan", plan["timedOutExternalProbePaths"])
        self.assertEqual(plan["volumeAccountingUsage"][0]["path"], "/volume1/@appdata/ContainerManager")
        self.assertEqual(plan["volumeAccountingUsage"][0]["destructiveAction"], "operator_review_required")
        self.assertEqual(plan["largestVolumeAccountingPath"], "/volume1/@appdata/ContainerManager")
        self.assertIn("/volume1/@synologydrive", plan["timedOutVolumeAccountingPaths"])
        self.assertIn("ContainerManager", plan["nextAction"])
        self.assertIn("Data, single", plan["btrfsAccounting"][0])

        pressure = _pressure_from_cleanup_plan(plan)

        self.assertTrue(pressure["measuredUsageAvailable"])
        self.assertIn("/volume1/Duncan", pressure["timedOutExternalProbePaths"])
        self.assertIn("/volume1/@synologydrive", pressure["timedOutVolumeAccountingPaths"])

    def test_nas_storage_pressure_probe_failure_does_not_invent_full_disk_measurement(self) -> None:
        pressure = _pressure_from_cleanup_plan(
            {
                "schema": "fluxio.nas_storage_cleanup_plan.v1",
                "checkedAt": "2026-06-01T13:51:27+00:00",
                "status": "probe_connect_failed",
                "host": "100.125.54.118",
                "mount": "/volume1/Saclay",
                "storageStatus": "unknown",
                "nextAction": "Retry bounded SSH storage accounting.",
            }
        )

        self.assertEqual(pressure["status"], "critical")
        self.assertTrue(pressure["probeConnectFailed"])
        self.assertFalse(pressure["measuredUsageAvailable"])
        self.assertEqual(pressure["usedPercent"], 0)
        self.assertEqual(pressure["availableBytes"], 0)

    def test_system_audit_lifts_harness_when_route_trust_is_operator_proven(self) -> None:
        categories = [
            AuditCategory(
                category="Harness and sub-agent capability",
                score_out_of_20=18,
                t3_reference_score_out_of_20=18,
                verdict="Outcome-trend routing exists, but proof is pending.",
                evidence=["outcome-trend routing present: True"],
                gaps=["Outcome-trend routing exists now; the next gap is proving it on live model-backed missions over time."],
                next_moves=["Run repeated live missions per task category so outcome trends can become stronger than static defaults."],
            ),
            AuditCategory(
                category="Launch friction and beginner experience",
                score_out_of_20=18,
                t3_reference_score_out_of_20=18,
                verdict="Launch still needs public distribution.",
                evidence=[],
                gaps=[],
                next_moves=[],
            ),
        ]
        route_maturity = {
            "status": "operator_proven",
            "operatorConfidenceScore": 92,
            "taskCount": 6,
            "provenTaskCount": 6,
            "missingOperatorValueSamples": 0,
        }

        calibrated = _calibrate_category_scores(
            categories,
            release={
                "status": "ready_for_1_0_validation",
                "requiredGateSummary": {"passed": 8, "total": 8},
            },
            live_nas_evidence={
                "status": "passed",
                "counts": {"missions": 52},
                "agentPassedChecks": [
                    "agent-thread-not-empty",
                    "live-tool-event-visible",
                    "live-mission-click-switch",
                    "no-demo-data-visible",
                ],
            },
            route_trust_maturity=route_maturity,
        )

        harness = next(item for item in calibrated if item.category == "Harness and sub-agent capability")
        launch = next(item for item in calibrated if item.category == "Launch friction and beginner experience")
        self.assertEqual(harness.score_out_of_20, 19)
        self.assertEqual(launch.score_out_of_20, 18)
        self.assertIn("operator-proven route trust", "\n".join(harness.evidence))
        self.assertNotIn("proving it on live model-backed missions", "\n".join(harness.gaps))
        summary = _summary(
            calibrated,
            {"status": "ready_for_1_0_validation", "requiredGateSummary": {"passed": 8, "total": 8}},
            [{"missionCount": 52, "sourceMode": "authenticated_live_nas"}],
            route_maturity,
        )
        self.assertIn("route trust no longer caps user-facing maturity", summary)
        self.assertNotIn("stays capped until live value-scored route trust is proven", summary)

    def test_system_audit_release_readiness_uses_live_mission_store_efficiency(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            runs_root = root / ".agent_runs"
            for index in range(4):
                session = runs_root / f"session_paused_{index}"
                session.mkdir(parents=True)
                (session / "state.json").write_text(
                    json.dumps(
                        {
                            "harness_id": "fluxio_hybrid",
                            "runtime_id": "hermes",
                            "autopilot_status": "paused",
                            "autopilot_pause_reason": "delegated_runtime_running",
                            "delegated_runtime_sessions": [
                                {"status": "running", "runtime_id": "hermes"}
                            ],
                            "action_history": [],
                            "verification_failures": [],
                        }
                    ),
                    encoding="utf-8",
                )
                (session / "metadata.json").write_text(
                    json.dumps({"parent_session_id": f"session_parent_{index}"}),
                    encoding="utf-8",
                )

            for index, status in enumerate(("completed", "completed", "running", "running")):
                mission = store.create_mission(
                    workspace_id=workspace.workspace_id,
                    runtime_id="hermes",
                    objective=f"Run live Hermes mission {index}",
                    success_checks=[],
                    mode="Autopilot",
                    verification_commands=[],
                    max_runtime_seconds=3600,
                )
                mission.harness_id = "fluxio_hybrid"
                mission.state.status = status
                mission.state.latest_session_id = f"session_live_{index}"
                mission.current_plan_revision_id = f"plan_{index}"
                mission.delegated_runtime_sessions = [
                    DelegatedRuntimeSession(
                        delegated_id=f"delegate_{index}",
                        runtime_id="hermes",
                        launch_command="python -m grant_agent.runtime_worker",
                        status="completed" if status == "completed" else "running",
                    )
                ]
                store.update_mission(mission)

            audit = build_system_audit(root)

            release = audit["releaseReadiness"]
            self.assertEqual(release["qualitySignals"]["completionRate"], 50)
            self.assertEqual(release["qualitySignals"]["delegatedRunRate"], 100)
            self.assertEqual(release["qualitySignals"]["resumeRunRate"], 100)
            self.assertEqual(release["qualitySignals"]["resumeCompletionRate"], 50)
            self.assertGreater(release["qualityScore"], 50)
            self.assertEqual(
                audit["harnessLab"]["source"],
                "mission_store_delegated_sessions_summary_for_release_audit",
            )
            self.assertIn("rawAgentRunHarnessLab", audit["harnessLab"])
            self.assertEqual(
                audit["harnessLab"]["rawAgentRunHarnessLab"]["efficiency"]["completionRate"],
                0,
            )

    def test_summary_reports_hard_artifact_repairs_without_weak_rows(self) -> None:
        categories = [
            AuditCategory(
                category="Proof, verification, and trust",
                score_out_of_20=12,
                t3_reference_score_out_of_20=14,
                verdict="Proof needs repair.",
                evidence=[],
                gaps=["hard artifact gate failed"],
                next_moves=["repair failed mission"],
            )
        ]

        summary = _summary(
            categories,
            {"status": "close_but_blocked", "requiredGateSummary": {"passed": 7, "total": 8}},
            [{"missionCount": 2, "sourceMode": "authenticated_live_nas"}],
            {},
            live_mission_output_quality={
                "weakMissionRows": [],
                "repairMissionRows": [{"missionId": "mission_f1", "status": "verification_failed"}],
            },
        )

        self.assertIn("Mission output quality needs repair", summary)
        self.assertIn("failed hard artifact gates", summary)
        self.assertNotIn("no completed transcript-only output warning", summary)

    def test_newer_passed_repair_plan_supersedes_stale_output_warning(self) -> None:
        categories = [
            AuditCategory(
                category="Proof, verification, and trust",
                score_out_of_20=18,
                t3_reference_score_out_of_20=14,
                verdict="Proof is usable.",
                evidence=[],
                gaps=[],
                next_moves=[],
            )
        ]
        stale_quality = {
            "schema": "fluxio.live_mission_output_quality.v1",
            "checkedAt": "2026-05-31T13:41:34+00:00",
            "status": "needs_artifact_repair",
            "weakMissionRows": [
                {
                    "missionId": "mission_f1",
                    "title": "Build a first usable prototype/report F1",
                    "weakOutput": True,
                }
            ],
            "repairMissionRows": [],
            "checkedMissionRows": [{"missionId": "mission_f1"}],
        }
        passed_plan = {
            "schema": "fluxio.mission_artifact_repair_plan.v1",
            "status": "passed",
            "generatedAt": "2026-06-02T07:17:11+00:00",
            "sourceCheckedAt": "2026-06-02T06:45:26+00:00",
            "repairMissionCount": 0,
            "weakMissionCount": 0,
            "repairs": [],
            "nextAction": "No transcript-only completed missions are present in current authenticated verifier evidence.",
        }

        summary = _summary(
            categories,
            {"status": "ready_for_1_0_validation", "requiredGateSummary": {"passed": 8, "total": 8}},
            [{"missionCount": 29, "sourceMode": "authenticated_live_nas"}],
            {},
            live_mission_output_quality=stale_quality,
            mission_artifact_repair_plan=passed_plan,
        )
        bad_first = _bad_first(
            categories,
            {"status": "ready_for_1_0_validation", "requiredGateSummary": {"passed": 8, "total": 8}},
            [{"missionCount": 29, "sourceMode": "authenticated_live_nas"}],
            {},
            live_mission_output_quality=stale_quality,
            mission_artifact_repair_plan=passed_plan,
        )
        system_loss = _system_loss_breakdown(
            categories,
            {"status": "ready_for_1_0_validation", "requiredGateSummary": {"passed": 8, "total": 8}},
            [{"missionCount": 29, "sourceMode": "authenticated_live_nas"}],
            live_mission_output_quality=stale_quality,
            mission_artifact_repair_plan=passed_plan,
        )

        self.assertIn("Latest checked live missions have no completed transcript-only output warning", summary)
        self.assertNotIn("Mission output quality is not fully proven", summary)
        self.assertFalse(any(item.get("title") == "Mission output proof" for item in bad_first))
        self.assertFalse(
            any(item.get("category") == "Mission outputs and artifact proof" for item in system_loss["drivers"])
        )

    def test_running_legacy_agent_report_with_runtime_output_is_not_artifact_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            report_dir = root / "tmp-ui-checks" / "authenticated-live-agent"
            report_dir.mkdir(parents=True)
            now_iso = datetime.now(timezone.utc).isoformat()
            (report_dir / "authenticated-live-agent-check.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.authenticated_live_agent.v1",
                        "checkedAt": now_iso,
                        "summary": {
                            "selectedMission": {
                                "mission_id": "mission_running",
                                "title": "Continue current live mission",
                                "status": "running",
                                "runtime_id": "hermes",
                            }
                        },
                        "checks": [
                            {
                                "checkId": "selected-live-mission",
                                "passed": True,
                                "missionId": "mission_running",
                            },
                            {
                                "checkId": "selected-mission-detail-api",
                                "passed": True,
                                "missionId": "mission_running",
                                "agentMessageCount": 24,
                            },
                            {
                                "checkId": "runtime-output-visible-in-thread",
                                "passed": True,
                                "runtimeOutputCount": 2,
                            },
                            {
                                "checkId": "live-workbench-proof-band-visible",
                                "passed": True,
                                "proofBandText": "Artifacts none returned",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            quality = _load_live_mission_output_quality_evidence(root)

            self.assertEqual(quality["status"], "passed")
            self.assertEqual(quality["repairMissionRows"], [])

    def test_system_audit_caps_speed_when_live_detail_performance_warns(self) -> None:
        categories = [
            AuditCategory(
                category="Speed and long-history performance",
                score_out_of_20=19,
                t3_reference_score_out_of_20=18,
                verdict="Speed proof exists.",
                evidence=[],
                gaps=[],
                next_moves=[],
            )
        ]

        capped = _apply_live_performance_caps(
            categories,
            live_detail_performance={
                "schema": "fluxio.live_mission_detail_performance.v1",
                "ok": False,
                "measurementCount": 6,
                "warningCount": 2,
                "backendWarningCount": 2,
                "wallWarningCount": 2,
                "coldWarningCount": 2,
                "warmWarningCount": 0,
                "coldTransportWarningCount": 2,
                "warmTransportWarningCount": 0,
                "maxWallMs": 1444.8,
                "nextAction": "Reduce cold mission-detail generation time before claiming speed parity.",
            },
        )

        self.assertEqual(capped[0].score_out_of_20, 17)
        self.assertIn("Strict live-performance cap", "\n".join(capped[0].evidence))
        self.assertIn("Measured live NAS mission-detail latency", "\n".join(capped[0].gaps))

    def test_system_audit_does_not_cap_speed_for_cold_transport_only_warning(self) -> None:
        categories = [
            AuditCategory(
                category="Speed and long-history performance",
                score_out_of_20=19,
                t3_reference_score_out_of_20=18,
                verdict="Speed proof exists.",
                evidence=[],
                gaps=[],
                next_moves=[],
            )
        ]

        capped = _apply_live_performance_caps(
            categories,
            live_detail_performance={
                "schema": "fluxio.live_mission_detail_performance.v1",
                "ok": True,
                "measurementCount": 8,
                "warningCount": 1,
                "backendWarningCount": 0,
                "wallWarningCount": 1,
                "coldWarningCount": 0,
                "warmWarningCount": 0,
                "coldTransportWarningCount": 1,
                "warmTransportWarningCount": 0,
                "maxWallMs": 1137.9,
            },
        )

        self.assertEqual(capped[0].score_out_of_20, 19)
        self.assertIn("transport warm-up warnings 1", "\n".join(capped[0].evidence))

    def test_system_audit_loads_live_detail_performance_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            report_path = root / ".agent_control" / "live_mission_detail_performance_latest.json"
            report_path.parent.mkdir(parents=True)
            report_path.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_mission_detail_performance.v1",
                        "checkedAt": datetime.now(timezone.utc).isoformat(),
                        "ok": False,
                        "measurementCount": 1,
                        "warningCount": 1,
                    }
                ),
                encoding="utf-8",
            )

            evidence = _load_live_mission_detail_performance_evidence(root)

            self.assertEqual(evidence["schema"], "fluxio.live_mission_detail_performance.v1")
            self.assertEqual(evidence["status"], "warning")
            self.assertEqual(evidence["sourcePath"], str(report_path.resolve()))

    def test_system_audit_clears_watchdog_receipt_collection_gap_after_three_completions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "docs").mkdir(exist_ok=True)
            (root / "docs" / "FLUXIO_1_0_RELEASE.md").write_text("# Release\n", encoding="utf-8")
            (root / "src" / "grant_agent").mkdir(parents=True, exist_ok=True)
            (root / "src" / "grant_agent" / "skill_library.py").write_text(
                "operator_value_closeout operatorValuePolicy _operator_value_summary\n",
                encoding="utf-8",
            )
            (root / "src" / "grant_agent" / "fluxio_harness.py").write_text(
                "operatorValueAverage scannedMissionCloseouts _operator_feedback_signal operator value\n",
                encoding="utf-8",
            )
            (root / "src" / "grant_agent" / "cli.py").write_text(
                "fluxio.self_improvement_watchdog_cadence.v1 selfImprovementCadence "
                "--advance-self-improvement watchdog_history.jsonl\n",
                encoding="utf-8",
            )
            (root / "src" / "grant_agent" / "mission_watchdog.py").write_text(
                "--advance-self-improvement\n",
                encoding="utf-8",
            )
            (root / "scripts").mkdir(exist_ok=True)
            (root / "scripts" / "verify_self_improvement_evidence.py").write_text(
                "fluxio.self_improvement_evidence.v1\n",
                encoding="utf-8",
            )
            (root / "scripts" / "advance_self_improvement_red_team_loop.py").write_text(
                "fluxio.self_improvement_red_team_loop_run.v1 record_red_team_sample "
                "build_self_improvement_evidence\n",
                encoding="utf-8",
            )
            (root / "scripts" / "sync_nas_system_audit.py").write_text(
                "watchdog_history.jsonl\n",
                encoding="utf-8",
            )
            (root / "scripts" / "archive_release_proofs.py").write_text(
                "self_improvement_evidence\n",
                encoding="utf-8",
            )
            (root / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
            (root / ".github" / "workflows" / "release-proof.yml").write_text(
                "npm run verify:self-improvement\n.agent_control/self_improvement_evidence/**\n",
                encoding="utf-8",
            )
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {
                            "verify:self-improvement": "python scripts/verify_self_improvement_evidence.py",
                            "advance:self-improvement-red-team": "python scripts/advance_self_improvement_red_team_loop.py",
                        }
                    }
                ),
                encoding="utf-8",
            )
            evidence_dir = root / ".agent_control" / "self_improvement_evidence"
            evidence_dir.mkdir(parents=True, exist_ok=True)
            (evidence_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.self_improvement_evidence.v1",
                        "ok": True,
                        "operatorValueRouteTrust": {
                            "source": "live_nas_system_audit",
                            "provenTaskCount": 3,
                            "taskCoverage": [
                                {"taskType": "frontend_design", "status": "proven"},
                                {"taskType": "general_coding", "status": "proven"},
                                {"taskType": "security_red_team", "status": "proven"},
                            ],
                            "missingTaskCategories": [],
                        },
                    }
                ),
                encoding="utf-8",
            )
            (evidence_dir / "watchdog_history.jsonl").write_text(
                "\n".join(
                    json.dumps(
                        {
                            "schema": "fluxio.self_improvement_watchdog_cadence.v1",
                            "status": "completed",
                            "historyIndex": index,
                        }
                    )
                    for index in range(1, 4)
                )
                + "\n",
                encoding="utf-8",
            )
            output = root / "docs" / "SYSTEM_GAP_ANALYSIS.md"

            exit_code, payload = self._run_json_command(
                cmd_system_audit,
                root=str(root),
                output=str(output),
                json=False,
            )

            self.assertEqual(exit_code, 0)
            report = output.read_text(encoding="utf-8")
            self.assertIn("watchdog self-improvement history receipts: 3 total / 3 completed", report)
            self.assertIn("watchdog self-improvement trend proven: True", report)
            self.assertIn("several completed watchdog receipts are proven", report)
            self.assertIn("Archive the completed watchdog trend receipts", report)
            self.assertNotIn("collecting several scheduled completed receipts", report)

    def test_system_audit_does_not_flag_healthy_next_red_team_target_as_bad(self) -> None:
        categories = [
            AuditCategory(
                category="Roadmap clarity and self-improvement",
                score_out_of_20=19,
                t3_reference_score_out_of_20=14,
                verdict="Adaptive red-team escalation is advancing.",
                evidence=[],
                gaps=[],
                next_moves=[],
            )
        ]
        bad_first = _bad_first(
            categories,
            {"proofReadiness": {}},
            [{"missionCount": 4}],
            {
                "summary": {
                    "runCount": 5,
                    "status": "escalating",
                    "satisfiedEscalationTargets": 4,
                    "pendingEscalationTargets": 1,
                    "nextAction": "Run the next harder aggregate-only benchmark.",
                },
                "escalationAudit": {
                    "status": "advancing",
                    "satisfiedTargets": 4,
                    "pendingTargets": 1,
                },
            },
        )

        self.assertFalse(any(item["title"] == "Red-team escalation" for item in bad_first))

    def test_route_trust_maturity_next_step_matches_operator_proven_state(self) -> None:
        maturity = _route_trust_maturity_snapshot(
            {
                "routeTrustCoverage": {
                    "provenTaskCount": 2,
                    "samplingTaskCount": 0,
                    "nextAction": "All tracked task categories have enough value-scored route and skill trust samples.",
                    "taskCoverage": [
                        {
                            "taskType": "frontend_design",
                            "status": "proven",
                            "missingOperatorValueSamples": 0,
                        },
                        {
                            "taskType": "security_red_team",
                            "status": "proven",
                            "missingOperatorValueSamples": 0,
                        },
                    ],
                }
            },
            snapshot={"missions": []},
            live_nas_evidence={"status": "passed", "runningMissions": []},
            sampling={},
            closeout={"proposals": []},
            loop={},
        )

        self.assertEqual(maturity["status"], "operator_proven")
        self.assertIn("Maintain periodic Hermes route-trust sampling", maturity["nextRepairStep"])
        self.assertIn("Maintain periodic Hermes route-trust sampling", maturity["nextAction"])
        self.assertNotIn("Launch the next Hermes route-trust sample", maturity["nextRepairStep"])

    def test_route_trust_maturity_counts_useful_scored_sampling_closeout(self) -> None:
        maturity = _route_trust_maturity_snapshot(
            {
                "routeTrustCoverage": {
                    "provenTaskCount": 5,
                    "samplingTaskCount": 1,
                    "nextAction": "Run 1 more useful value-scored F1/data analytics mission.",
                    "taskCoverage": [
                        {
                            "taskType": "frontend_design",
                            "status": "proven",
                            "missingOperatorValueSamples": 0,
                        },
                        {
                            "taskType": "security_red_team",
                            "status": "proven",
                            "missingOperatorValueSamples": 0,
                        },
                        {
                            "taskType": "hardware_electrical",
                            "status": "proven",
                            "missingOperatorValueSamples": 0,
                        },
                        {
                            "taskType": "rf_mapping",
                            "status": "proven",
                            "missingOperatorValueSamples": 0,
                        },
                        {
                            "taskType": "data_journalism",
                            "status": "proven",
                            "missingOperatorValueSamples": 0,
                        },
                        {
                            "taskType": "data_f1_analytics",
                            "status": "sampling",
                            "missingOperatorValueSamples": 1,
                        },
                    ],
                }
            },
            snapshot={"missions": []},
            live_nas_evidence={"status": "passed", "runningMissions": []},
            sampling={},
            closeout={
                "proposals": [
                    {
                        "missionId": "mission_f1",
                        "taskType": "data_f1_analytics",
                        "status": "already_scored",
                        "score": 88,
                        "outcome": "useful",
                        "trustSignal": "promote",
                    }
                ]
            },
            loop={},
        )

        self.assertEqual(maturity["status"], "operator_proven")
        self.assertEqual(maturity["provenTaskCount"], 6)
        self.assertEqual(maturity["missingOperatorValueSamples"], 0)
        self.assertIn("data_f1_analytics", maturity["closeoutPromotedTasks"])
        self.assertIn("Maintain periodic Hermes route-trust sampling", maturity["nextAction"])

    def test_newer_local_low_value_closeout_caps_synced_operator_proven_route_trust(self) -> None:
        local_maturity = {
            "schema": "fluxio.operator_confidence_calibration.v1",
            "status": "needs_route_repair",
            "operatorConfidenceScore": 68,
            "lowValueCloseoutCount": 1,
            "repairPlan": [
                {
                    "taskType": "data_f1_analytics",
                    "missionId": "mission_low",
                    "repairAction": "Repair the F1/data route before another promotion.",
                }
            ],
            "nextRepairStep": "Repair the F1/data route before another promotion.",
            "nextAction": "Review the low-value closeout.",
        }
        synced_maturity = {
            "schema": "fluxio.operator_confidence_calibration.v1",
            "status": "operator_proven",
            "operatorConfidenceScore": 92,
            "taskCount": 6,
            "provenTaskCount": 6,
            "missingOperatorValueSamples": 0,
            "lowValueCloseoutCount": 0,
        }

        merged = _merge_synced_route_trust_maturity(
            synced_maturity,
            local_route_trust_maturity=local_maturity,
            closeout_review={
                "sourcePath": "local/closeout_review_latest.json",
                "generatedAt": "2026-05-29T15:18:17+00:00",
            },
            source_path="nas/live_nas_system_audit_latest.json",
            source_checked_at="2026-05-29T14:40:27+00:00",
        )

        self.assertEqual(merged["status"], "needs_route_repair")
        self.assertEqual(merged["operatorConfidenceScore"], 68)
        self.assertEqual(merged["lowValueCloseoutCount"], 1)
        self.assertEqual(merged["evidenceConflict"]["status"], "newer_local_low_value_closeout")
        self.assertIn("operator-proven", merged["capReason"])

    def test_stale_local_low_value_closeout_does_not_cap_synced_operator_proven_route_trust(self) -> None:
        local_maturity = {
            "schema": "fluxio.operator_confidence_calibration.v1",
            "status": "needs_route_repair",
            "operatorConfidenceScore": 68,
            "lowValueCloseoutCount": 1,
            "repairPlan": [
                {
                    "taskType": "data_f1_analytics",
                    "missionId": "mission_low",
                    "repairAction": "Repair the F1/data route before another promotion.",
                }
            ],
        }
        synced_maturity = {
            "schema": "fluxio.operator_confidence_calibration.v1",
            "status": "operator_proven",
            "operatorConfidenceScore": 92,
            "taskCount": 6,
            "provenTaskCount": 6,
            "missingOperatorValueSamples": 0,
            "lowValueCloseoutCount": 0,
        }

        merged = _merge_synced_route_trust_maturity(
            synced_maturity,
            local_route_trust_maturity=local_maturity,
            closeout_review={
                "sourcePath": "local/closeout_review_latest.json",
                "generatedAt": "2026-05-29T15:18:17+00:00",
            },
            source_path="nas/live_nas_system_audit_latest.json",
            source_checked_at="2026-05-29T15:52:29+00:00",
        )

        self.assertEqual(merged["status"], "operator_proven")
        self.assertEqual(merged["operatorConfidenceScore"], 92)
        self.assertEqual(merged["lowValueCloseoutCount"], 0)
        self.assertNotIn("evidenceConflict", merged)
        self.assertEqual(
            merged["staleLocalLowValueCloseoutIgnored"]["status"],
            "ignored_stale_local_low_value_closeout",
        )

    def test_newer_positive_closeout_supersedes_stale_synced_route_repair(self) -> None:
        local_maturity = {
            "schema": "fluxio.operator_confidence_calibration.v1",
            "status": "operator_proven",
            "operatorConfidenceScore": 92,
            "taskCount": 6,
            "provenTaskCount": 6,
            "missingOperatorValueSamples": 0,
            "lowValueCloseoutCount": 0,
            "repairPlanStatus": "clear",
            "repairPlanCount": 0,
            "repairPlan": [],
            "nextAction": "Maintain periodic Hermes route-trust sampling.",
        }
        synced_maturity = {
            "schema": "fluxio.operator_confidence_calibration.v1",
            "status": "needs_route_repair",
            "operatorConfidenceScore": 68,
            "taskCount": 6,
            "provenTaskCount": 5,
            "missingOperatorValueSamples": 0,
            "lowValueCloseoutCount": 1,
            "repairPlanStatus": "required",
            "repairPlan": [
                {
                    "taskType": "data_f1_analytics",
                    "missionId": "mission_old_low_value",
                    "repairAction": "Repair the F1/data route before another promotion.",
                }
            ],
        }

        merged = _merge_synced_route_trust_maturity(
            synced_maturity,
            local_route_trust_maturity=local_maturity,
            closeout_review={
                "sourcePath": "local/closeout_review_latest.json",
                "generatedAt": "2026-05-30T21:45:45+00:00",
            },
            source_path="nas/live_nas_system_audit_latest.json",
            source_checked_at="2026-05-30T20:48:28+00:00",
        )

        self.assertEqual(merged["status"], "operator_proven")
        self.assertEqual(merged["repairPlanStatus"], "clear")
        self.assertEqual(merged["lowValueCloseoutCount"], 0)
        self.assertEqual(
            merged["staleSyncedRepairIgnored"]["status"],
            "ignored_stale_synced_repair_after_value_closeout",
        )
        self.assertEqual(
            merged["supersededSyncedRouteTrustMaturity"]["status"],
            "needs_route_repair",
        )

    def test_system_audit_launch_cap_stays_below_t3_until_external_publication(self) -> None:
        categories = [
            AuditCategory(
                category="Launch friction and beginner experience",
                score_out_of_20=20,
                t3_reference_score_out_of_20=18,
                verdict="Launch evidence is present.",
                evidence=[],
                gaps=[],
                next_moves=[],
            )
        ]

        capped = _apply_strict_score_caps(
            categories,
            {
                "has_launcher_package_release_receipt": True,
                "has_public_web_release_candidate_attachment": True,
                "has_npx_style_launcher_package": True,
                "has_one_command_launcher": True,
            },
        )

        self.assertEqual(capped[0].score_out_of_20, 18)
        self.assertIn("external public registry", "\n".join(capped[0].evidence))

    def test_system_audit_launch_cap_clears_with_public_and_beginner_proof(self) -> None:
        categories = [
            AuditCategory(
                category="Launch friction and beginner experience",
                score_out_of_20=20,
                t3_reference_score_out_of_20=18,
                verdict="Launch evidence is present.",
                evidence=["beginner launch interaction proof present: True"],
                gaps=[],
                next_moves=[],
            )
        ]

        capped = _apply_strict_score_caps(
            categories,
            {
                "has_public_launch_ready": True,
                "has_external_publication_proof": True,
                "has_beginner_launch_interaction_gate": True,
            },
        )

        self.assertEqual(capped[0].score_out_of_20, 20)
        self.assertNotIn("Strict cap:", "\n".join(capped[0].evidence))

    def test_system_audit_bad_first_omits_healthy_zero_loss_categories(self) -> None:
        categories = [
            AuditCategory(
                category="Launch friction and beginner experience",
                score_out_of_20=20,
                t3_reference_score_out_of_20=18,
                verdict="Launch is healthy.",
                evidence=[],
                gaps=["Keep launch receipts current."],
                next_moves=[],
            ),
            AuditCategory(
                category="Harness and sub-agent capability",
                score_out_of_20=19,
                t3_reference_score_out_of_20=18,
                verdict="Harness is nearly complete.",
                evidence=[],
                gaps=["Live cross-category outcome validation is still pending."],
                next_moves=[],
            ),
        ]

        bad_first = _bad_first(
            categories,
            {},
            [{"missionCount": 1}],
            red_team_escalation={
                "summary": {
                    "runCount": 1,
                    "pendingEscalationTargets": 1,
                    "satisfiedEscalationTargets": 1,
                    "status": "escalating",
                }
            },
        )

        self.assertEqual([item["title"] for item in bad_first], ["Harness and sub-agent capability"])
        self.assertNotIn("Launch friction and beginner experience", [item["title"] for item in bad_first])

    def test_summary_does_not_claim_weaker_t3_areas_when_all_categories_are_ahead(self) -> None:
        categories = [
            AuditCategory(
                category="Harness and sub-agent capability",
                score_out_of_20=20,
                t3_reference_score_out_of_20=18,
                verdict="ahead",
                evidence=[],
                gaps=[],
                next_moves=[],
            ),
            AuditCategory(
                category="Interface clarity and operator ergonomics",
                score_out_of_20=20,
                t3_reference_score_out_of_20=17,
                verdict="ahead",
                evidence=[],
                gaps=[],
                next_moves=[],
            ),
        ]

        summary = _summary(
            categories,
            {"status": "ready", "requiredGateSummary": {"passed": 1, "total": 1}},
            [{"missionCount": 1}],
        )

        self.assertIn("ahead of the T3-style reference in every scored category", summary)
        self.assertNotIn("but weaker on", summary)

    def test_system_audit_storage_ok_report_does_not_claim_launch_blocked(self) -> None:
        report = render_system_audit_markdown(
            {
                "schema": "fluxio.system_gap_analysis.v1",
                "generatedAt": "2026-06-01T00:00:00+00:00",
                "workspaceRoot": "C:\\workspace",
                "summary": "summary",
                "badFirst": [],
                "categories": [],
                "projectProgress": [],
                "releaseReadiness": {"status": "ready_for_1_0_validation"},
                "nasStoragePressureEvidence": {
                    "status": "ok",
                    "mount": "/volume1/Saclay",
                    "usedPercent": 28,
                    "availableBytes": 2766573002752,
                    "generatedCleanupBytesFreed": 0,
                },
            }
        )

        self.assertIn("Launch preflight: clear", report)
        self.assertNotIn("NAS mission start/resume is blocked", report)

    def test_system_audit_launch_cap_credits_local_fallback_during_nas_pressure(self) -> None:
        categories = [
            AuditCategory(
                category="Launch friction and beginner experience",
                score_out_of_20=20,
                t3_reference_score_out_of_20=18,
                verdict="Launch evidence is present.",
                evidence=[],
                gaps=[],
                next_moves=[],
            )
        ]

        without_fallback = _apply_strict_score_caps(
            categories,
            {
                "has_nas_storage_pressure_critical": True,
                "has_npx_style_launcher_package": True,
            },
        )
        with_fallback = _apply_strict_score_caps(
            categories,
            {
                "has_nas_storage_pressure_critical": True,
                "has_npx_style_launcher_package": True,
                "has_storage_aware_quickstart_fallback": True,
            },
        )

        self.assertEqual(without_fallback[0].score_out_of_20, 16)
        self.assertEqual(with_fallback[0].score_out_of_20, 17)
        self.assertIn("route new work to a local workspace", "\n".join(with_fallback[0].evidence))
        self.assertIn("NAS-backed unattended launches", "\n".join(with_fallback[0].gaps))

    def test_system_audit_web_score_requires_public_launch_for_twenty(self) -> None:
        categories = [
            AuditCategory(
                category="Web availability and distribution",
                score_out_of_20=20,
                t3_reference_score_out_of_20=18,
                verdict="Web distribution evidence is present.",
                evidence=[],
                gaps=[],
                next_moves=[],
            )
        ]

        capped = _apply_strict_score_caps(
            categories,
            {
                "has_public_web_release_candidate_attachment": True,
                "has_public_launch_internal_packet_ready": True,
                "has_public_web_distribution_contract": True,
                "has_out_of_band_watchdog_notifications": True,
                "has_installable_pwa_shell": True,
                "has_mobile_push_delivery_proof": True,
            },
        )
        ready = _apply_strict_score_caps(
            categories,
            {
                "has_public_launch_ready": True,
                "has_public_web_release_candidate_attachment": True,
                "has_public_launch_internal_packet_ready": True,
                "has_public_web_distribution_contract": True,
                "has_mobile_push_delivery_proof": True,
            },
        )

        self.assertEqual(capped[0].score_out_of_20, 18)
        self.assertIn("requires external publication proof", "\n".join(capped[0].evidence))
        self.assertEqual(ready[0].score_out_of_20, 18)
        self.assertIn("external publication/tag", "\n".join(ready[0].evidence))

    def test_system_audit_ui_score_is_capped_by_live_output_repairs_and_nas_pressure(self) -> None:
        categories = [
            AuditCategory(
                category="Interface clarity and operator ergonomics",
                score_out_of_20=19,
                t3_reference_score_out_of_20=17,
                verdict="UI component evidence is present.",
                evidence=[],
                gaps=[],
                next_moves=[],
            )
        ]

        artifact_capped = _apply_strict_score_caps(
            categories,
            {
                "has_live_workbench_execution_surface": True,
                "has_live_mission_artifact_repairs": True,
            },
        )
        storage_capped = _apply_strict_score_caps(
            categories,
            {
                "has_live_workbench_execution_surface": True,
                "has_nas_storage_pressure_critical": True,
            },
        )

        self.assertEqual(artifact_capped[0].score_out_of_20, 15)
        self.assertIn("missing runtime output", "\n".join(artifact_capped[0].evidence))
        self.assertEqual(storage_capped[0].score_out_of_20, 16)
        self.assertIn("NAS storage", "\n".join(storage_capped[0].evidence))

    def test_system_audit_harness_cap_clears_with_live_cross_category_outcomes(self) -> None:
        categories = [
            AuditCategory(
                category="Harness and sub-agent capability",
                score_out_of_20=20,
                t3_reference_score_out_of_20=18,
                verdict="Harness evidence is present.",
                evidence=[],
                gaps=[],
                next_moves=[],
            )
        ]

        capped = _apply_strict_score_caps(
            categories,
            {
                "has_outcome_trend_routing": True,
                "has_live_cross_category_outcome_validation": True,
                "has_operator_value_route_trust_proven": True,
            },
        )

        self.assertEqual(capped[0].score_out_of_20, 20)
        self.assertNotIn("cross-category outcome validation is still pending", "\n".join(capped[0].evidence))

    def test_live_cross_category_outcome_validation_requires_distinct_hermes_task_families(self) -> None:
        evidence = {
            "checkedMissionRows": [
                {
                    "missionId": "mission_f1",
                    "title": "Build an F1 telemetry analytics prototype",
                    "runtime": "hermes",
                    "runtimeOutputCount": 4,
                    "artifactStatus": "reported",
                    "artifactGateStatus": "passed",
                },
                {
                    "missionId": "mission_rf",
                    "title": "Build a legal defensive RF/wireless mapping",
                    "runtime": "hermes",
                    "runtimeOutputCount": 4,
                    "artifactStatus": "reported",
                    "artifactGateStatus": "passed",
                },
                {
                    "missionId": "mission_public",
                    "title": "Build a public-data investigation suite concept/prototype",
                    "runtime": "hermes",
                    "runtimeOutputCount": 4,
                    "artifactStatus": "reported",
                    "artifactGateStatus": "passed",
                },
                {
                    "missionId": "mission_ui",
                    "title": "Build a polished phone/tablet Builder progress surface",
                    "runtime": "hermes",
                    "runtimeOutputCount": 31,
                    "artifactStatus": "none_returned",
                    "artifactGateStatus": "passed",
                },
                {
                    "missionId": "mission_ignored",
                    "title": "OpenClaw RF task",
                    "runtime": "openclaw",
                    "runtimeOutputCount": 8,
                    "artifactStatus": "reported",
                    "artifactGateStatus": "passed",
                },
            ]
        }

        validation = _live_cross_category_outcome_validation(evidence)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["validatedCategoryCount"], 4)
        self.assertEqual(
            {row["taskFamily"] for row in validation["categories"]},
            {"f1_data_analytics", "frontend_mobile_ui", "public_data_investigation", "rf_wireless"},
        )

    def test_live_cross_category_outcome_validation_ignores_hash_like_mission_ids(self) -> None:
        evidence = {
            "checkedMissionRows": [
                {
                    "missionId": "mission_02f113f522",
                    "title": "Hermes-selected autonomous deliverable proof",
                    "runtime": "hermes",
                    "runtimeOutputCount": 54,
                    "artifactStatus": "reported",
                    "artifactGateStatus": "passed",
                    "runtimeTranscriptStatus": "attached",
                }
            ]
        }

        validation = _live_cross_category_outcome_validation(evidence, required_categories=1)

        self.assertEqual(validation["status"], "needs_more_categories")
        self.assertEqual(validation["validatedCategoryCount"], 0)
        self.assertEqual(validation["categories"], [])

    def test_live_cross_category_outcome_validation_uses_live_route_task_family_hints(self) -> None:
        evidence = {
            "checkedMissionRows": [
                {
                    "missionId": "mission_f1_hint",
                    "title": "Route trust sample",
                    "runtime": "hermes",
                    "routeTrustTaskType": "data_f1_analytics",
                    "runtimeOutputCount": 4,
                    "artifactStatus": "reported",
                    "artifactGateStatus": "passed",
                },
                {
                    "missionId": "mission_public_hint",
                    "title": "Route trust sample",
                    "runtime": "hermes",
                    "taskFamily": "public_data_investigation",
                    "runtimeOutputCount": 3,
                    "artifactStatus": "reported",
                    "artifactGateStatus": "passed",
                },
                {
                    "missionId": "mission_hardware_hint",
                    "title": "Route trust sample",
                    "runtime": "hermes",
                    "routeTaskTypes": ["hardware_electrical"],
                    "runtimeOutputCount": 5,
                    "artifactStatus": "reported",
                    "artifactGateStatus": "passed",
                },
            ]
        }

        validation = _live_cross_category_outcome_validation(evidence, required_categories=3)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(
            {row["taskFamily"] for row in validation["categories"]},
            {"f1_data_analytics", "hardware_electrical", "public_data_investigation"},
        )

    def test_live_cross_category_outcome_validation_prefers_domain_over_frontend_route(self) -> None:
        evidence = {
            "checkedMissionRows": [
                {
                    "missionId": "mission_rf_frontend_route",
                    "title": "Build a legal defensive RF/wireless mapping",
                    "runtime": "hermes",
                    "objective": "Cover Wi-Fi, Bluetooth, ADS-B, AIS, and SDR signal mapping with a dashboard artifact.",
                    "routeTaskTypes": ["frontend_design"],
                    "runtimeOutputCount": 8,
                    "artifactStatus": "reported",
                    "artifactGateStatus": "passed",
                },
                {
                    "missionId": "mission_hardware_workbench",
                    "title": "Create a hardware/electrical discovery workbench F1-style",
                    "runtime": "hermes",
                    "objective": "Component list, signal paths, sensor notes, and circuit safety notes.",
                    "routeTaskTypes": ["frontend_design"],
                    "runtimeOutputCount": 8,
                    "artifactStatus": "reported",
                    "artifactGateStatus": "passed",
                },
            ]
        }

        validation = _live_cross_category_outcome_validation(evidence, required_categories=2)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(
            {row["taskFamily"] for row in validation["categories"]},
            {"hardware_electrical", "rf_wireless"},
        )

    def test_system_audit_ui_cap_clears_when_live_output_quality_is_clear(self) -> None:
        categories = [
            AuditCategory(
                category="Interface clarity and operator ergonomics",
                score_out_of_20=20,
                t3_reference_score_out_of_20=17,
                verdict="UI and live output evidence are present.",
                evidence=[],
                gaps=[],
                next_moves=[],
            )
        ]

        capped = _apply_strict_score_caps(
            categories,
            {
                "has_live_workbench_execution_surface": True,
                "has_live_mission_output_quality_cleared": True,
            },
        )

        self.assertEqual(capped[0].score_out_of_20, 20)

    def test_public_launch_readiness_keeps_stale_public_receipt_as_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "scripts").mkdir()
            (root / "web" / "dist").mkdir(parents=True)
            (root / ".agent_control" / "launcher_package").mkdir(parents=True)
            (root / ".agent_control" / "deployment_evidence").mkdir(parents=True)
            archive = root / ".agent_control" / "release_artifacts" / "candidate"
            release_dir = archive / "release_candidate"
            release_dir.mkdir(parents=True)

            (root / "package.json").write_text(
                json.dumps(
                    {
                        "bin": {"fluxio": "scripts/fluxio-cli.mjs"},
                        "files": ["scripts/fluxio-cli.mjs", "web/dist"],
                        "scripts": {"verify:launcher-package": "python scripts/verify_launcher_package.py --write"},
                    }
                ),
                encoding="utf-8",
            )
            (root / ".agent_control" / "launcher_package" / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.launcher_package_verification.v1",
                        "ok": True,
                        "entrypoint": "scripts/fluxio-cli.mjs",
                        "packedFileCount": 4,
                    }
                ),
                encoding="utf-8",
            )
            (root / ".agent_control" / "deployment_evidence" / "public-web.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.public_web_deployment.v1",
                        "ok": True,
                        "status": 200,
                        "url": "https://example.invalid/fluxio/",
                        "publicationCurrent": False,
                        "sourceState": {
                            "deployedShaMatchesLocalHead": True,
                            "sourceWorkingTreeClean": False,
                            "sourceDirtyPathCount": 3,
                            "sourceDirtyPathSample": [
                                " M src/grant_agent/mission_control.py",
                                "?? scripts/verify_public_launch_readiness.py",
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / ".agent_control" / "deployment_evidence" / "private-nas-web.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.private_nas_web_deployment.v1",
                        "ok": True,
                        "healthStatus": 200,
                        "controlStatus": 200,
                        "controlUrl": "https://nas.invalid/control",
                    }
                ),
                encoding="utf-8",
            )
            candidate_path = release_dir / "release-candidate.json"
            publication_path = release_dir / "publication-manifest.json"
            attachments_path = release_dir / "publication-attachments.json"
            proof_path = archive / "proof.json"
            proof_path.write_text('{"ok": true}\n', encoding="utf-8")
            digest = hashlib.sha256(proof_path.read_bytes()).hexdigest()
            candidate_path.write_text(
                json.dumps({"schema": "fluxio.release_candidate.v1", "candidateId": "candidate", "status": "publication_packet_ready"}),
                encoding="utf-8",
            )
            publication_path.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.public_release_publication_packet.v1",
                        "missing": [],
                        "requiredProof": {
                            "launcherPackage": True,
                            "privateNasWebDeployment": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            attachments_path.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.public_release_attachment_manifest.v1",
                        "status": "ready_to_attach",
                        "attachments": [
                            {
                                "archiveRelativePath": "proof.json",
                                "sha256": digest,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (root / ".agent_control" / "release_artifacts" / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.latest_release_artifact_pointer.v1",
                        "archiveRoot": str(archive),
                        "releaseCandidatePath": str(candidate_path),
                        "publicationManifestPath": str(publication_path),
                        "publicationAttachmentManifestPath": str(attachments_path),
                        "candidateStatus": "publication_packet_ready",
                    }
                ),
                encoding="utf-8",
            )

            report = verify_public_launch_readiness(root)

            self.assertFalse(report["ok"])
            self.assertTrue(report["internalPacketReady"])
            self.assertEqual(report["status"], "public_packet_ready_missing_current_web_and_publication")
            self.assertIn("public_web_current", report["missing"])
            self.assertIn("external_publication_proven", report["missing"])
            self.assertEqual(
                report["publicWeb"]["sourceDirtyPathSample"][:2],
                [
                    " M src/grant_agent/mission_control.py",
                    "?? scripts/verify_public_launch_readiness.py",
                ],
            )
            triage = report["publicWeb"]["dirtySourceTriage"]
            self.assertEqual(triage["schema"], "fluxio.public_launch_dirty_source_triage.v1")
            self.assertEqual(triage["releaseBlockingSampleCount"], 2)
            self.assertEqual(triage["releaseBlockingPathCount"], 2)
            self.assertEqual(triage["sourceCoverage"], "receipt_sample")
            self.assertEqual(triage["releaseBlockingPaths"][:2], [
                "src/grant_agent/mission_control.py",
                "scripts/verify_public_launch_readiness.py",
            ])
            self.assertEqual(triage["laneCounts"]["product_source"], 2)
            self.assertFalse(triage["safeToClaimCurrentPublicWeb"])
            self.assertIn("Commit/push/deploy", triage["nextAction"])
            repair_packet = report["repairPacket"]
            self.assertEqual(repair_packet["schema"], "fluxio.public_launch_repair_packet.v1")
            self.assertFalse(repair_packet["canClaimPublicLaunch"])
            self.assertEqual(repair_packet["primaryBlocker"], "public_web_current")
            self.assertEqual(repair_packet["sourceCoverage"], "receipt_sample")
            self.assertEqual(repair_packet["releaseBlockingPathCount"], 2)
            self.assertEqual(repair_packet["stagingPlan"]["schema"], "fluxio.public_launch_staging_plan.v1")
            self.assertEqual(repair_packet["stagingPlan"]["releaseImpactPathCount"], 2)
            self.assertIn("staging-plan.json", repair_packet["stagingPlan"]["proofPath"])
            self.assertTrue(any("git add" in item["command"] for item in repair_packet["stagingPlan"]["groups"]))
            self.assertEqual(report["stagingProof"]["schema"], "fluxio.public_launch_staging_proof.v1")
            self.assertEqual(report["stagingProof"]["releaseImpactPathCount"], 2)
            self.assertEqual(report["stagingProof"]["sourceCoverage"], "receipt_sample")
            self.assertIn("staging-plan.json", report["stagingProof"]["evidencePath"])
            self.assertIn("product_source", [item["lane"] for item in repair_packet["orderedLanes"]])
            self.assertTrue(any("verify_public_launch_readiness.py" in item["command"] for item in repair_packet["commands"]))
            self.assertTrue(any(item["path"] == ".agent_control/publication/github-release.json" for item in repair_packet["receiptTargets"]))
            self.assertEqual(
                report["publicationProof"]["acceptedSchemas"],
                [
                    "fluxio.npm_publication_receipt.v1",
                    "fluxio.signed_installer_receipt.v1",
                    "fluxio.github_release_publication_receipt.v1",
                ],
            )
            self.assertIn("attachment_manifest_integrity", [item["checkId"] for item in report["checks"] if item["passed"]])

    def test_public_launch_readiness_accepts_github_release_publication_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "scripts").mkdir()
            (root / "web" / "dist").mkdir(parents=True)
            (root / ".agent_control" / "launcher_package").mkdir(parents=True)
            (root / ".agent_control" / "deployment_evidence").mkdir(parents=True)
            (root / ".agent_control" / "publication").mkdir(parents=True)
            archive = root / ".agent_control" / "release_artifacts" / "candidate"
            release_dir = archive / "release_candidate"
            release_dir.mkdir(parents=True)

            (root / "package.json").write_text(
                json.dumps(
                    {
                        "bin": {"fluxio": "scripts/fluxio-cli.mjs"},
                        "files": ["scripts/fluxio-cli.mjs", "web/dist"],
                        "scripts": {"verify:launcher-package": "python scripts/verify_launcher_package.py --write"},
                    }
                ),
                encoding="utf-8",
            )
            (root / ".agent_control" / "launcher_package" / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.launcher_package_verification.v1",
                        "ok": True,
                        "entrypoint": "scripts/fluxio-cli.mjs",
                        "packedFileCount": 4,
                    }
                ),
                encoding="utf-8",
            )
            (root / ".agent_control" / "deployment_evidence" / "public-web.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.public_web_deployment.v1",
                        "ok": True,
                        "status": 200,
                        "url": "https://example.invalid/fluxio/",
                        "publicationCurrent": True,
                        "sourceState": {
                            "deployedShaMatchesLocalHead": True,
                            "sourceWorkingTreeClean": True,
                            "sourceDirtyPathCount": 0,
                            "sourceDirtyPathSample": [],
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / ".agent_control" / "deployment_evidence" / "private-nas-web.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.private_nas_web_deployment.v1",
                        "ok": True,
                        "healthStatus": 200,
                        "controlStatus": 200,
                        "controlUrl": "https://nas.invalid/control",
                    }
                ),
                encoding="utf-8",
            )
            proof_path = archive / "proof.json"
            proof_path.write_text('{"ok": true}\n', encoding="utf-8")
            digest = hashlib.sha256(proof_path.read_bytes()).hexdigest()
            candidate_path = release_dir / "release-candidate.json"
            publication_path = release_dir / "publication-manifest.json"
            attachments_path = release_dir / "publication-attachments.json"
            candidate_path.write_text(
                json.dumps({"schema": "fluxio.release_candidate.v1", "candidateId": "candidate", "status": "ready_for_publication"}),
                encoding="utf-8",
            )
            publication_path.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.public_release_publication_packet.v1",
                        "missing": [],
                        "requiredProof": {
                            "launcherPackage": True,
                            "privateNasWebDeployment": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            attachments_path.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.public_release_attachment_manifest.v1",
                        "status": "ready_to_attach",
                        "attachments": [{"archiveRelativePath": "proof.json", "sha256": digest}],
                    }
                ),
                encoding="utf-8",
            )
            (root / ".agent_control" / "release_artifacts" / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.latest_release_artifact_pointer.v1",
                        "archiveRoot": str(archive),
                        "releaseCandidatePath": str(candidate_path),
                        "publicationManifestPath": str(publication_path),
                        "publicationAttachmentManifestPath": str(attachments_path),
                        "candidateStatus": "ready_for_publication",
                    }
                ),
                encoding="utf-8",
            )
            (root / ".agent_control" / "publication" / "github-release.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.github_release_publication_receipt.v1",
                        "ok": True,
                        "tagName": "fluxio-20260530",
                        "url": "https://github.com/example/fluxio/releases/tag/fluxio-20260530",
                        "attachmentCount": 4,
                        "expectedAttachmentManifestAttached": True,
                        "assets": [{"name": "publication-attachments.json", "size": 120}],
                    }
                ),
                encoding="utf-8",
            )

            report = verify_public_launch_readiness(root)

            self.assertTrue(report["ok"])
            self.assertEqual(report["status"], "ready_for_public_launch")
            self.assertNotIn("external_publication_proven", report["missing"])
            self.assertTrue(report["publicationProof"]["githubReleaseReceiptPresent"])

    def test_public_launch_readiness_rejects_current_dirty_release_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "scripts").mkdir()
            (root / "web" / "dist").mkdir(parents=True)
            (root / ".agent_control" / "launcher_package").mkdir(parents=True)
            (root / ".agent_control" / "deployment_evidence").mkdir(parents=True)
            (root / ".agent_control" / "publication").mkdir(parents=True)
            archive = root / ".agent_control" / "release_artifacts" / "candidate"
            release_dir = archive / "release_candidate"
            release_dir.mkdir(parents=True)

            (root / "package.json").write_text(
                json.dumps(
                    {
                        "bin": {"fluxio": "scripts/fluxio-cli.mjs"},
                        "files": ["scripts/fluxio-cli.mjs", "web/dist"],
                        "scripts": {"verify:launcher-package": "python scripts/verify_launcher_package.py --write"},
                    }
                ),
                encoding="utf-8",
            )
            (root / ".agent_control" / "launcher_package" / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.launcher_package_verification.v1",
                        "ok": True,
                        "entrypoint": "scripts/fluxio-cli.mjs",
                        "packedFileCount": 4,
                    }
                ),
                encoding="utf-8",
            )
            (root / ".agent_control" / "deployment_evidence" / "public-web.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.public_web_deployment.v1",
                        "ok": True,
                        "status": 200,
                        "url": "https://example.invalid/fluxio/",
                        "publicationCurrent": True,
                        "sourceState": {
                            "deployedShaMatchesLocalHead": True,
                            "sourceWorkingTreeClean": True,
                            "sourceDirtyPathCount": 0,
                            "sourceDirtyPathSample": [],
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / ".agent_control" / "deployment_evidence" / "private-nas-web.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.private_nas_web_deployment.v1",
                        "ok": True,
                        "healthStatus": 200,
                        "controlStatus": 200,
                        "controlUrl": "https://nas.invalid/control",
                    }
                ),
                encoding="utf-8",
            )
            proof_path = archive / "proof.json"
            proof_path.write_text('{"ok": true}\n', encoding="utf-8")
            digest = hashlib.sha256(proof_path.read_bytes()).hexdigest()
            candidate_path = release_dir / "release-candidate.json"
            publication_path = release_dir / "publication-manifest.json"
            attachments_path = release_dir / "publication-attachments.json"
            candidate_path.write_text(
                json.dumps({"schema": "fluxio.release_candidate.v1", "candidateId": "candidate", "status": "ready_for_publication"}),
                encoding="utf-8",
            )
            publication_path.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.public_release_publication_packet.v1",
                        "missing": [],
                        "requiredProof": {
                            "launcherPackage": True,
                            "privateNasWebDeployment": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            attachments_path.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.public_release_attachment_manifest.v1",
                        "status": "ready_to_attach",
                        "attachments": [{"archiveRelativePath": "proof.json", "sha256": digest}],
                    }
                ),
                encoding="utf-8",
            )
            (root / ".agent_control" / "release_artifacts" / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.latest_release_artifact_pointer.v1",
                        "archiveRoot": str(archive),
                        "releaseCandidatePath": str(candidate_path),
                        "publicationManifestPath": str(publication_path),
                        "publicationAttachmentManifestPath": str(attachments_path),
                        "candidateStatus": "ready_for_publication",
                    }
                ),
                encoding="utf-8",
            )
            (root / ".agent_control" / "publication" / "github-release.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.github_release_publication_receipt.v1",
                        "ok": True,
                        "tagName": "fluxio-20260530",
                        "url": "https://github.com/example/fluxio/releases/tag/fluxio-20260530",
                        "assets": [{"name": "publication-attachments.json", "size": 120}],
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch(
                "scripts.verify_public_launch_readiness._current_git_dirty_rows",
                return_value=[" M src/grant_agent/mission_control.py"],
            ):
                report = verify_public_launch_readiness(root)

            self.assertFalse(report["ok"])
            self.assertEqual(report["status"], "public_packet_ready_but_source_stale")
            self.assertIn("public_web_current", report["missing"])
            self.assertNotIn("external_publication_proven", report["missing"])
            public_web_check = next(item for item in report["checks"] if item["checkId"] == "public_web_current")
            self.assertFalse(public_web_check["passed"])
            self.assertEqual(public_web_check["currentGitDirtyPathCount"], 1)
            self.assertEqual(public_web_check["currentReleaseBlockingPathCount"], 1)
            triage = report["publicWeb"]["dirtySourceTriage"]
            self.assertEqual(triage["sourceCoverage"], "full_git_status")
            self.assertEqual(triage["releaseBlockingPaths"], ["src/grant_agent/mission_control.py"])
            self.assertFalse(triage["safeToClaimCurrentPublicWeb"])
            self.assertFalse(report["repairPacket"]["canClaimPublicLaunch"])
            self.assertEqual(report["repairPacket"]["primaryBlocker"], "public_web_current")

    def test_github_release_publication_receipt_requires_public_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / ".agent_control" / "release_artifacts").mkdir(parents=True)
            (root / ".agent_control" / "release_artifacts" / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.latest_release_artifact_pointer.v1",
                        "publicationAttachmentManifestPath": str(root / "attachments.json"),
                    }
                ),
                encoding="utf-8",
            )

            draft = build_github_release_publication_receipt(
                root,
                repo="example/fluxio",
                tag="fluxio-20260530",
                release_payload={
                    "tagName": "fluxio-20260530",
                    "url": "https://github.com/example/fluxio/releases/tag/fluxio-20260530",
                    "isDraft": True,
                    "assets": [{"name": "attachments.json", "size": 120}],
                },
            )
            published = build_github_release_publication_receipt(
                root,
                repo="example/fluxio",
                tag="fluxio-20260530",
                release_payload={
                    "tagName": "fluxio-20260530",
                    "url": "https://github.com/example/fluxio/releases/tag/fluxio-20260530",
                    "isDraft": False,
                    "assets": [{"name": "attachments.json", "size": 120}],
                },
            )
            wrong_asset = build_github_release_publication_receipt(
                root,
                repo="example/fluxio",
                tag="fluxio-20260530",
                release_payload={
                    "tagName": "fluxio-20260530",
                    "url": "https://github.com/example/fluxio/releases/tag/fluxio-20260530",
                    "isDraft": False,
                    "assets": [{"name": "unrelated.zip", "size": 120}],
                },
            )

            self.assertFalse(draft["ok"])
            self.assertIn("draft", draft["nextAction"].lower())
            self.assertFalse(wrong_asset["ok"])
            self.assertIn("attachments.json", wrong_asset["nextAction"])
            self.assertTrue(published["ok"])
            self.assertEqual(published["attachmentCount"], 1)
            self.assertTrue(published["expectedAttachmentManifestAttached"])

    def test_public_launch_readiness_resolves_windows_release_pointer_on_nas(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "scripts").mkdir()
            (root / "web" / "dist").mkdir(parents=True)
            (root / ".agent_control" / "launcher_package").mkdir(parents=True)
            (root / ".agent_control" / "deployment_evidence").mkdir(parents=True)
            archive = root / ".agent_control" / "release_artifacts" / "candidate"
            release_dir = archive / "release_candidate"
            release_dir.mkdir(parents=True)

            (root / "package.json").write_text(
                json.dumps(
                    {
                        "bin": {"fluxio": "scripts/fluxio-cli.mjs"},
                        "files": ["scripts/fluxio-cli.mjs", "web/dist"],
                        "scripts": {"verify:launcher-package": "python scripts/verify_launcher_package.py --write"},
                    }
                ),
                encoding="utf-8",
            )
            (root / ".agent_control" / "launcher_package" / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.launcher_package_verification.v1",
                        "ok": True,
                        "entrypoint": "scripts/fluxio-cli.mjs",
                        "packedFileCount": 4,
                    }
                ),
                encoding="utf-8",
            )
            (root / ".agent_control" / "deployment_evidence" / "public-web.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.public_web_deployment.v1",
                        "ok": True,
                        "status": 200,
                        "url": "https://example.invalid/fluxio/",
                        "publicationCurrent": False,
                        "sourceState": {
                            "deployedShaMatchesLocalHead": True,
                            "sourceWorkingTreeClean": False,
                            "sourceDirtyPathCount": 3,
                            "sourceDirtyPathSample": [" M README.md"],
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / ".agent_control" / "deployment_evidence" / "private-nas-web.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.private_nas_web_deployment.v1",
                        "ok": True,
                        "healthStatus": 200,
                        "controlStatus": 200,
                        "controlUrl": "https://nas.invalid/control",
                    }
                ),
                encoding="utf-8",
            )
            candidate_path = release_dir / "release-candidate.json"
            publication_path = release_dir / "publication-manifest.json"
            attachments_path = release_dir / "publication-attachments.json"
            proof_path = archive / "proof.json"
            proof_path.write_text('{"ok": true}\n', encoding="utf-8")
            digest = hashlib.sha256(proof_path.read_bytes()).hexdigest()
            candidate_path.write_text(
                json.dumps({"schema": "fluxio.release_candidate.v1", "candidateId": "candidate", "status": "publication_packet_ready"}),
                encoding="utf-8",
            )
            publication_path.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.public_release_publication_packet.v1",
                        "missing": [],
                        "requiredProof": {
                            "launcherPackage": True,
                            "privateNasWebDeployment": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            attachments_path.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.public_release_attachment_manifest.v1",
                        "status": "ready_to_attach",
                        "attachments": [
                            {
                                "archiveRelativePath": "proof.json",
                                "sha256": digest,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            windows_prefix = "C:\\Users\\paul\\Projects\\vibe-coding-platform"
            (root / ".agent_control" / "release_artifacts" / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.latest_release_artifact_pointer.v1",
                        "archiveRoot": windows_prefix + "\\.agent_control\\release_artifacts\\candidate",
                        "releaseCandidatePath": windows_prefix + "\\.agent_control\\release_artifacts\\candidate\\release_candidate\\release-candidate.json",
                        "publicationManifestPath": windows_prefix + "\\.agent_control\\release_artifacts\\candidate\\release_candidate\\publication-manifest.json",
                        "publicationAttachmentManifestPath": windows_prefix + "\\.agent_control\\release_artifacts\\candidate\\release_candidate\\publication-attachments.json",
                        "candidateStatus": "publication_packet_ready",
                    }
                ),
                encoding="utf-8",
            )

            report = verify_public_launch_readiness(root)

            passed = {item["checkId"] for item in report["checks"] if item["passed"]}
            self.assertIn("release_packet_attached", passed)
            self.assertIn("publication_manifest_ready", passed)
            self.assertIn("attachment_manifest_integrity", passed)

    def test_route_trust_loop_can_resume_stale_waiting_sampling_mission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build a frontend route-trust sample",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "running"
            mission.state.planner_loop_status = "launching"
            mission.updated_at = (datetime.now(timezone.utc) - timedelta(minutes=95)).isoformat()
            store.update_mission(mission)
            sampling_dir = root / ".agent_control" / "route_trust_sampling"
            sampling_dir.mkdir(parents=True)
            (sampling_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.route_trust_live_sampling_run.v1",
                        "ok": True,
                        "launchedSamplingMissions": [
                            {
                                "missionId": mission.mission_id,
                                "taskType": "frontend_design",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch("scripts.advance_route_trust_sampling_loop.cmd_mission_action", return_value=0) as action:
                payload = advance_loop(
                    argparse.Namespace(
                        root=str(root),
                        max_new=1,
                        max_active=4,
                        max_queued=2,
                        runtime="hermes",
                        mode="Autopilot",
                        budget_hours=6,
                        auto_apply_closeouts=False,
                        min_auto_score=70,
                        resume_stale_waiting=True,
                        stale_waiting_minutes=0,
                        review_only=False,
                        dry_run=False,
                        write=True,
                    )
                )

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["staleWaitingRepair"]["resumedMissionIds"], [mission.mission_id])
            self.assertIn("Resumed stale sampling mission", payload["nextAction"])
            called_args = action.call_args.args[0]
            self.assertEqual(called_args.action, "extend-budget")
            self.assertTrue(called_args.launch_async)
            self.assertEqual(called_args.budget_hours, 6)

    def test_route_trust_loop_can_launch_other_category_while_one_waits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            sampling_dir = root / ".agent_control" / "route_trust_sampling"
            sampling_dir.mkdir(parents=True)
            (sampling_dir / "closeout_review_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.route_trust_sampling_closeout_review.v1",
                        "ok": True,
                        "proposals": [
                            {
                                "missionId": "mission_waiting_f1",
                                "taskType": "data_f1_analytics",
                                "status": "waiting_for_terminal_state",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch(
                "scripts.advance_route_trust_sampling_loop.review_closeouts",
                return_value={
                    "ok": True,
                    "proposals": [
                        {
                            "missionId": "mission_waiting_f1",
                            "taskType": "data_f1_analytics",
                            "status": "waiting_for_terminal_state",
                        }
                    ],
                    "appliedCloseouts": [],
                },
            ):
                payload = advance_loop(
                    argparse.Namespace(
                        root=str(root),
                        max_new=1,
                        max_active=4,
                        max_queued=2,
                        runtime="hermes",
                        mode="Autopilot",
                        budget_hours=4,
                        auto_apply_closeouts=False,
                        min_auto_score=70,
                        resume_stale_waiting=False,
                        stale_waiting_minutes=90,
                        review_only=False,
                        dry_run=True,
                        write=True,
                    )
                )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["samplingLaunch"]["attempted"])
            self.assertIn("mission_waiting_f1", payload["closeoutReview"]["waitingMissionIds"])
            self.assertTrue(payload["samplingLaunch"]["launchedMissionIds"] or payload["samplingLaunch"]["skipped"])
            self.assertNotIn("Wait for active sampling missions", payload["nextAction"])

    def test_route_trust_loop_migrates_queued_sample_to_isolated_lane(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            active = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep the primary workspace busy",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            active.state.status = "running"
            active.state.planner_loop_status = "running"
            store.update_mission(active)
            queued = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Create a hardware/electrical discovery workbench for an F1-style sensor telemetry rig",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            sampling_dir = root / ".agent_control" / "route_trust_sampling"
            sampling_dir.mkdir(parents=True)
            (sampling_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.route_trust_live_sampling_run.v1",
                        "ok": True,
                        "launchedSamplingMissions": [
                            {
                                "missionId": queued.mission_id,
                                "taskType": "hardware_electrical",
                                "objective": queued.objective,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            def fake_action(args: argparse.Namespace) -> int:
                print(json.dumps({"dispatch": {"pid": 4567}}))
                return 0

            with (
                mock.patch(
                    "scripts.advance_route_trust_sampling_loop.review_closeouts",
                    return_value={"ok": True, "proposals": [], "appliedCloseouts": []},
                ),
                mock.patch("scripts.advance_route_trust_sampling_loop.cmd_mission_action", side_effect=fake_action) as action,
            ):
                payload = advance_loop(
                    argparse.Namespace(
                        root=str(root),
                        max_new=1,
                        max_active=4,
                        max_queued=2,
                        runtime="hermes",
                        mode="Autopilot",
                        budget_hours=4,
                        auto_apply_closeouts=False,
                        min_auto_score=70,
                        resume_stale_waiting=False,
                        stale_waiting_minutes=90,
                        migrate_queued_sampling=True,
                        review_only=False,
                        dry_run=False,
                        write=True,
                    )
                )

            refreshed = ControlRoomStore(root).get_mission(queued.mission_id)
            self.assertEqual(payload["queuedSamplingMigration"]["migratedMissionIds"], [queued.mission_id])
            self.assertEqual(refreshed.workspace_id, "route_trust_hardware_electrical")
            self.assertEqual(refreshed.state.queue_position, 0)
            self.assertEqual(action.call_args.args[0].action, "resume")
            self.assertTrue(action.call_args.args[0].launch_async)
            self.assertFalse(payload["samplingLaunch"]["attempted"])

    def test_route_trust_closeout_treats_blocked_sampling_mission_as_low_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build a frontend route-trust sample",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "blocked"
            mission.state.stop_reason = "delegated_runtime_failed"
            store.update_mission(mission)
            sampling_dir = root / ".agent_control" / "route_trust_sampling"
            sampling_dir.mkdir(parents=True)
            (sampling_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.route_trust_live_sampling_run.v1",
                        "ok": True,
                        "launchedSamplingMissions": [
                            {
                                "missionId": mission.mission_id,
                                "taskType": "frontend_design",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = review_closeouts(
                argparse.Namespace(
                    root=str(root),
                    sampling_report="",
                    write=True,
                    auto_apply=False,
                    min_auto_score=70,
                )
            )

            self.assertEqual(payload["proposals"][0]["status"], "ready_for_low_value_closeout")
            self.assertEqual(payload["proposals"][0]["score"], 30)
            self.assertEqual(payload["proposals"][0]["trustSignal"], "deprioritize")
            self.assertTrue(payload["proposals"][0]["canApply"])

    def test_route_trust_closeout_auto_applies_low_value_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build a frontend route-trust sample",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "blocked"
            mission.state.stop_reason = "delegated_runtime_failed"
            store.update_mission(mission)
            sampling_dir = root / ".agent_control" / "route_trust_sampling"
            sampling_dir.mkdir(parents=True)
            (sampling_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.route_trust_live_sampling_run.v1",
                        "ok": True,
                        "launchedSamplingMissions": [
                            {
                                "missionId": mission.mission_id,
                                "taskType": "frontend_design",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = review_closeouts(
                argparse.Namespace(
                    root=str(root),
                    sampling_report="",
                    write=True,
                    auto_apply=True,
                    min_auto_score=70,
                )
            )
            refreshed = ControlRoomStore(root).get_mission(mission.mission_id)

            self.assertEqual(payload["appliedCloseouts"][0]["score"], 30)
            self.assertEqual(
                refreshed.state.operator_value_feedback["trustSignal"],
                "deprioritize",
            )
            self.assertEqual(
                refreshed.state.operator_value_feedback["routeTrustTaskType"],
                "frontend_design",
            )

    def test_route_trust_closeout_reviews_historical_migrated_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            hardware = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Create a hardware/electrical discovery workbench",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            hardware.state.status = "completed"
            hardware.state.planner_loop_status = "completed"
            hardware.proof.passed_checks = ["artifact ready"]
            store.update_mission(hardware)
            red_team = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Run a defensive red-team escalation sample",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            red_team.state.status = "completed"
            red_team.state.planner_loop_status = "completed"
            store.update_mission(red_team)
            sampling_dir = root / ".agent_control" / "route_trust_sampling"
            sampling_dir.mkdir(parents=True)
            (sampling_dir / "loop_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.route_trust_sampling_loop.v1",
                        "queuedSamplingMigration": {
                            "migrated": [
                                {
                                    "missionId": hardware.mission_id,
                                    "taskType": "hardware_electrical",
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            (sampling_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.route_trust_live_sampling_run.v1",
                        "launchedSamplingMissions": [
                            {
                                "missionId": red_team.mission_id,
                                "taskType": "security_red_team",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = review_closeouts(
                argparse.Namespace(
                    root=str(root),
                    sampling_report="",
                    write=True,
                    auto_apply=False,
                    min_auto_score=70,
                )
            )

            proposal_ids = {item["missionId"] for item in payload["proposals"]}
            self.assertEqual(proposal_ids, {hardware.mission_id, red_team.mission_id})
            task_types = {item["taskType"] for item in payload["proposals"]}
            self.assertEqual(task_types, {"hardware_electrical", "security_red_team"})

    def test_route_trust_closeout_review_reports_already_scored_samples_as_done(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build a completed route trust sample",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "completed"
            mission.state.planner_loop_status = "completed"
            mission.state.operator_value_feedback = {
                "score": 92,
                "outcome": "useful",
                "trustSignal": "promote",
                "routeTrustTaskType": "frontend_design",
            }
            store.update_mission(mission)
            sampling_dir = root / ".agent_control" / "route_trust_sampling"
            sampling_dir.mkdir(parents=True)
            (sampling_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.route_trust_live_sampling_run.v1",
                        "launchedSamplingMissions": [
                            {
                                "missionId": mission.mission_id,
                                "taskType": "frontend_design",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = review_closeouts(
                argparse.Namespace(
                    root=str(root),
                    sampling_report="",
                    write=True,
                    auto_apply=True,
                    min_auto_score=80,
                )
            )

            self.assertEqual(payload["proposals"][0]["status"], "already_scored")
            self.assertEqual(payload["appliedCloseouts"], [])
            self.assertIn("already value-scored", payload["nextAction"])
            self.assertNotIn("rerun with --auto-apply", payload["nextAction"])

    def test_route_trust_closeout_review_annotates_historical_scored_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build a completed F1 analytics route trust sample",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "completed"
            mission.state.planner_loop_status = "completed"
            mission.state.operator_value_feedback = {
                "score": 88,
                "outcome": "useful",
                "trustSignal": "promote",
            }
            store.update_mission(mission)
            sampling_dir = root / ".agent_control" / "route_trust_sampling"
            sampling_dir.mkdir(parents=True)
            (sampling_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.route_trust_live_sampling_run.v1",
                        "launchedSamplingMissions": [
                            {
                                "missionId": mission.mission_id,
                                "taskType": "data_f1_analytics",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = review_closeouts(
                argparse.Namespace(
                    root=str(root),
                    sampling_report="",
                    write=True,
                    auto_apply=True,
                    min_auto_score=80,
                )
            )
            refreshed = ControlRoomStore(root).get_mission(mission.mission_id)

            self.assertEqual(payload["proposals"][0]["status"], "already_scored")
            self.assertEqual(payload["proposals"][0]["annotatedRouteTrustTaskType"], "data_f1_analytics")
            self.assertEqual(
                refreshed.state.operator_value_feedback["routeTrustTaskType"],
                "data_f1_analytics",
            )

    def test_route_trust_sampler_repairs_frontend_after_low_value_minimax_sample(self) -> None:
        closeout = {
            "proposals": [
                {
                    "missionId": "mission_bad_frontend",
                    "taskType": "frontend_design",
                    "score": 30,
                    "outcome": "not_useful",
                    "trustSignal": "deprioritize",
                }
            ]
        }

        routes = _route_contract_for_task("frontend_design", closeout=closeout)
        planner = next(route for route in routes if route["role"] == "planner")
        executor = next(route for route in routes if route["role"] == "executor")
        verifier = next(route for route in routes if route["role"] == "verifier")

        self.assertEqual(planner["provider"], "openai-codex")
        self.assertEqual(planner["model"], "gpt-5.5")
        self.assertEqual(executor["provider"], "minimax")
        self.assertEqual(executor["model"], "MiniMax-M3")
        self.assertEqual(executor["effort"], "high")
        self.assertEqual(verifier["provider"], "openai-codex")
        self.assertEqual(verifier["model"], "gpt-5.5")
        self.assertIn("low-value frontend sample", executor["reason"])
        self.assertIn("Hermes-verified MiniMax route", executor["reason"])

    def test_route_trust_sampler_uses_codex_planner_executor_verifier_for_general_tasks(self) -> None:
        routes = _route_contract_for_task("general_coding", closeout={})

        self.assertEqual(
            [(route["role"], route["provider"], route["model"]) for route in routes],
            [
                ("planner", "openai-codex", "gpt-5.5"),
                ("executor", "openai-codex", "gpt-5.5"),
                ("verifier", "openai-codex", "gpt-5.5"),
            ],
        )

    def test_route_trust_sampler_repairs_low_value_data_route_with_proof_gates(self) -> None:
        routes = _route_contract_for_task(
            "data_f1_analytics",
            closeout={
                "proposals": [
                    {
                        "missionId": "mission_bad_f1",
                        "taskType": "data_f1_analytics",
                        "score": 30,
                        "outcome": "not_useful",
                        "trustSignal": "deprioritize",
                    }
                ]
            },
        )

        executor = next(route for route in routes if route["role"] == "executor")

        self.assertEqual(executor["provider"], "openai-codex")
        self.assertEqual(executor["model"], "gpt-5.5")
        self.assertEqual(executor["effort"], "high")
        self.assertIn("low-value data_f1_analytics sample", executor["reason"])
        self.assertIn("browser-preview proof", executor["reason"])
        self.assertIn("operator-value closeout", executor["reason"])

    def test_route_trust_sampler_launches_live_audit_repair_plan_when_sampling_plan_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            audit_path = root / ".agent_control" / "live_nas_system_audit_latest.json"
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            audit_path.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_nas_system_audit_snapshot.v1",
                        "audit": {
                            "routeTrustMaturity": {
                                "status": "needs_route_repair",
                                "repairPlan": [
                                    {
                                        "taskType": "data_f1_analytics",
                                        "label": "F1/data analytics",
                                        "missionId": "mission_low_f1",
                                        "score": 30,
                                        "repairAction": "Repair the F1/data analytics route before another promotion.",
                                        "modelPolicy": "Hermes harness; planner/verifier use openai-codex gpt-5.5 high; executor uses Codex gpt-5.5 high.",
                                        "trustEffect": "Do not promote this task category until the next sample scores at least 80.",
                                    }
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            def fake_start(args: argparse.Namespace) -> int:
                print(json.dumps({"mission": {"mission_id": "mission_repair_f1"}}))
                return 0

            with mock.patch("scripts.run_route_trust_sampling_missions.cmd_mission_start", side_effect=fake_start) as start:
                payload = run_route_trust_sampling(
                    argparse.Namespace(
                        root=str(root),
                        max_new=1,
                        max_active=4,
                        max_queued=2,
                        runtime="hermes",
                        mode="Autopilot",
                        budget_hours=4,
                        skip_route_contract=False,
                        dry_run=False,
                        write=False,
                    )
                )

            self.assertTrue(payload["ok"])
            launched = payload["launchedSamplingMissions"][0]
            self.assertEqual(launched["taskType"], "data_f1_analytics")
            self.assertEqual(launched["source"], "live_nas_system_audit_repair_plan")
            self.assertIn("F1 telemetry analytics", launched["objective"])
            self.assertEqual(payload["coverageBefore"]["repairPlanCount"], 1)
            launch_args = start.call_args.args[0]
            self.assertEqual(launch_args.workspace_id, "route_trust_data_f1_analytics")
            routes = json.loads(launch_args.route_overrides_json)
            executor = next(route for route in routes if route["role"] == "executor")
            self.assertEqual(executor["provider"], "openai-codex")
            self.assertEqual(executor["model"], "gpt-5.5")
            self.assertIn("low-value data_f1_analytics sample", executor["reason"])

    def test_route_trust_sampler_blocks_live_launch_when_nas_storage_is_critical(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            control = root / ".agent_control"
            control.mkdir(parents=True, exist_ok=True)
            (control / "nas_storage_pressure_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.nas_storage_pressure.v1",
                        "checkedAt": datetime.now(timezone.utc).isoformat(),
                        "status": "critical",
                        "source": "bounded_ssh_timeout",
                        "probeTimedOut": True,
                        "mount": "/volume1/Saclay",
                        "usedPercent": 100,
                        "availableBytes": 0,
                        "nextAction": "Do not start NAS write-heavy missions until a bounded probe returns.",
                    }
                ),
                encoding="utf-8",
            )
            (control / "live_nas_system_audit_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_nas_system_audit_snapshot.v1",
                        "audit": {
                            "routeTrustMaturity": {
                                "status": "needs_route_repair",
                                "repairPlan": [
                                    {
                                        "taskType": "data_f1_analytics",
                                        "missionId": "mission_low_f1",
                                        "repairAction": "Repair F1 route trust.",
                                    }
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch("scripts.run_route_trust_sampling_missions.cmd_mission_start") as start:
                payload = run_route_trust_sampling(
                    argparse.Namespace(
                        root=str(root),
                        max_new=1,
                        max_active=4,
                        max_queued=2,
                        runtime="hermes",
                        mode="Autopilot",
                        budget_hours=4,
                        skip_route_contract=False,
                        dry_run=False,
                        write=False,
                    )
                )

            self.assertFalse(payload["ok"])
            self.assertEqual(payload["storagePreflight"]["status"], "blocked")
            self.assertFalse(payload["storagePreflight"]["canLaunch"])
            self.assertEqual(payload["launchedSamplingMissions"], [])
            self.assertEqual(payload["skippedSamplingMissions"][0]["reason"], "nas_storage_pressure_block")
            start.assert_not_called()

    def test_route_trust_sampler_allows_dry_run_when_nas_storage_is_critical(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            control = root / ".agent_control"
            control.mkdir(parents=True, exist_ok=True)
            (control / "nas_storage_pressure_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.nas_storage_pressure.v1",
                        "checkedAt": datetime.now(timezone.utc).isoformat(),
                        "status": "critical",
                        "source": "bounded_ssh_timeout",
                        "probeTimedOut": True,
                        "mount": "/volume1/Saclay",
                        "usedPercent": 100,
                        "availableBytes": 0,
                    }
                ),
                encoding="utf-8",
            )
            (control / "live_nas_system_audit_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_nas_system_audit_snapshot.v1",
                        "audit": {
                            "routeTrustMaturity": {
                                "status": "needs_route_repair",
                                "repairPlan": [
                                    {
                                        "taskType": "data_f1_analytics",
                                        "missionId": "mission_low_f1",
                                        "repairAction": "Repair F1 route trust.",
                                    }
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch("scripts.run_route_trust_sampling_missions.cmd_mission_start") as start:
                payload = run_route_trust_sampling(
                    argparse.Namespace(
                        root=str(root),
                        max_new=1,
                        max_active=4,
                        max_queued=2,
                        runtime="hermes",
                        mode="Autopilot",
                        budget_hours=4,
                        skip_route_contract=False,
                        dry_run=True,
                        write=True,
                    )
                )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["dryRun"])
            self.assertEqual(payload["storagePreflight"]["status"], "dry_run_only")
            self.assertFalse(payload["storagePreflight"]["canLaunch"])
            self.assertTrue(payload["storagePreflight"]["canDryRun"])
            self.assertTrue(payload["launchedSamplingMissions"][0]["dryRun"])
            self.assertTrue((control / "route_trust_sampling" / "dry_run_latest.json").exists())
            start.assert_not_called()

    def test_route_trust_sampler_escalates_red_team_after_clean_high_value_samples(self) -> None:
        objective, checks, profile = _apply_task_difficulty(
            task_type="security_red_team",
            objective="Run a defensive red-team route trust sample.",
            success_checks=["Record a legal defensive red-team report."],
            closeout={
                "appliedCloseouts": [
                    {
                        "missionId": "mission_red_team_clean_1",
                        "taskType": "security_red_team",
                        "score": 92,
                        "outcome": "useful",
                        "trustSignal": "promote",
                    },
                    {
                        "missionId": "mission_red_team_clean_2",
                        "taskType": "security_red_team",
                        "score": 88,
                        "outcome": "useful",
                        "trustSignal": "promote",
                    },
                ],
            },
        )

        self.assertTrue(profile["shouldEscalate"])
        self.assertEqual(profile["difficultyLevel"], 3)
        self.assertGreater(profile["attemptBudget"], 7)
        self.assertFalse(profile["safetyPolicy"]["rawPayloadExport"])
        self.assertIn("Difficulty escalation level 3", objective)
        self.assertIn("defensive-only", objective)
        self.assertTrue(any("harder than previous promoted red-team samples" in check for check in checks))
        self.assertTrue(any("unsafe payloads or third-party targeting were excluded" in check for check in checks))

    def test_route_trust_sampler_applies_route_contract_before_async_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            route_contract = _route_contract_for_task(
                "frontend_design",
                closeout={
                    "proposals": [
                        {
                            "missionId": "mission_bad_frontend",
                            "taskType": "frontend_design",
                            "score": 30,
                            "outcome": "not_useful",
                            "trustSignal": "deprioritize",
                        }
                    ]
                },
            )

            def fake_start(args: argparse.Namespace) -> int:
                print(json.dumps({"mission": {"mission_id": "mission_prelaunch_route"}}))
                return 0

            with mock.patch("scripts.run_route_trust_sampling_missions.cmd_mission_start", side_effect=fake_start) as start:
                exit_code, payload, _raw = _run_quickstart(
                    root=root,
                    objective="Build a frontend sample",
                    success_checks=["served artifact is visible"],
                    runtime="hermes",
                    mode="Autopilot",
                    budget_hours=4,
                    route_contract=route_contract,
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["mission"]["mission_id"], "mission_prelaunch_route")
            launch_args = start.call_args.args[0]
            self.assertTrue(launch_args.launch_async)
            self.assertEqual(launch_args.runtime, "hermes")
            prelaunch_routes = json.loads(launch_args.route_overrides_json)
            planner = next(route for route in prelaunch_routes if route["role"] == "planner")
            executor = next(route for route in prelaunch_routes if route["role"] == "executor")
            verifier = next(route for route in prelaunch_routes if route["role"] == "verifier")
            self.assertEqual(planner["provider"], "openai-codex")
            self.assertEqual(planner["model"], "gpt-5.5")
            self.assertEqual(executor["provider"], "minimax")
            self.assertEqual(executor["model"], "MiniMax-M3")
            self.assertEqual(verifier["provider"], "openai-codex")
            self.assertEqual(verifier["model"], "gpt-5.5")

    def test_route_trust_sampler_uses_isolated_workspace_lane_per_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)

            def fake_start(args: argparse.Namespace) -> int:
                print(json.dumps({"mission": {"mission_id": "mission_isolated_route"}}))
                return 0

            with mock.patch("scripts.run_route_trust_sampling_missions.cmd_mission_start", side_effect=fake_start) as start:
                exit_code, payload, _raw = _run_quickstart(
                    root=root,
                    objective="Build a frontend sample",
                    success_checks=["served artifact is visible"],
                    runtime="hermes",
                    mode="Autopilot",
                    budget_hours=4,
                    task_type="frontend_design",
                    dedicated_workspace=True,
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["mission"]["mission_id"], "mission_isolated_route")
            launch_args = start.call_args.args[0]
            self.assertEqual(launch_args.workspace_id, "route_trust_frontend_design")
            route_workspace = ControlRoomStore(root).get_workspace("route_trust_frontend_design")
            self.assertIsNotNone(route_workspace)
            self.assertEqual(route_workspace.execution_target_preference, "isolated_worktree")
            self.assertEqual(route_workspace.default_runtime, "hermes")

    def test_route_trust_dry_run_write_does_not_replace_live_latest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            route_dir = root / ".agent_control" / "route_trust_sampling"
            route_dir.mkdir(parents=True, exist_ok=True)
            latest = route_dir / "latest.json"
            latest.write_text(
                json.dumps({"schema": "fluxio.route_trust_live_sampling_run.v1", "dryRun": False}),
                encoding="utf-8",
            )

            payload = run_route_trust_sampling(
                argparse.Namespace(
                    root=str(root),
                    max_new=1,
                    max_active=4,
                    max_queued=2,
                    runtime="hermes",
                    mode="Autopilot",
                    budget_hours=4,
                    skip_route_contract=False,
                    dry_run=True,
                    write=True,
                )
            )

            self.assertTrue(payload["dryRun"])
            self.assertTrue((route_dir / "dry_run_latest.json").exists())
            self.assertFalse(json.loads(latest.read_text(encoding="utf-8"))["dryRun"])

    def test_system_audit_uses_newer_route_trust_dry_run_storage_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            route_dir = root / ".agent_control" / "route_trust_sampling"
            route_dir.mkdir(parents=True)
            (route_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.route_trust_live_sampling_run.v1",
                        "generatedAt": "2026-05-30T21:17:00+00:00",
                        "ok": True,
                        "dryRun": False,
                        "runtime": "hermes",
                        "launchedSamplingMissions": [{"missionId": "mission_old", "ok": True}],
                    }
                ),
                encoding="utf-8",
            )
            (route_dir / "dry_run_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.route_trust_live_sampling_run.v1",
                        "generatedAt": "2026-06-01T00:17:18+00:00",
                        "ok": True,
                        "dryRun": True,
                        "runtime": "hermes",
                        "storagePreflight": {
                            "schema": "fluxio.route_trust_storage_preflight.v1",
                            "status": "dry_run_only",
                            "canLaunch": False,
                            "canDryRun": True,
                            "dryRun": True,
                            "storage": {
                                "sourcePath": str(root / ".agent_control" / "nas_storage_pressure_latest.json"),
                                "status": "critical",
                            },
                            "nextAction": "Dry run is allowed, but live route-trust sampling is blocked.",
                        },
                        "launchedSamplingMissions": [],
                        "skippedSamplingMissions": [{"taskType": "frontend_design", "reason": "capacity_guard"}],
                    }
                ),
                encoding="utf-8",
            )

            evidence = _load_route_trust_sampling_evidence(root)

            self.assertTrue(evidence["dryRun"])
            self.assertEqual(evidence["status"], "dry_run_only")
            self.assertEqual(evidence["storagePreflight"]["status"], "dry_run_only")
            self.assertEqual(evidence["launchedSamplingMissions"], [])
            self.assertIn("dry_run_latest.json", evidence["sourcePath"])

    def test_system_audit_ignores_stale_storage_blocked_dry_run_when_storage_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            control = root / ".agent_control"
            route_dir = control / "route_trust_sampling"
            route_dir.mkdir(parents=True)
            (control / "nas_storage_pressure_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.nas_storage_pressure.v1",
                        "checkedAt": datetime.now(timezone.utc).isoformat(),
                        "maxAgeSeconds": 172800,
                        "status": "ok",
                        "probeTimedOut": False,
                        "usedPercent": 31,
                        "availableBytes": 2660399771648,
                    }
                ),
                encoding="utf-8",
            )
            (route_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.route_trust_live_sampling_run.v1",
                        "generatedAt": "2026-05-30T21:17:00+00:00",
                        "ok": True,
                        "dryRun": False,
                        "runtime": "hermes",
                        "launchedSamplingMissions": [{"missionId": "mission_live", "ok": True}],
                    }
                ),
                encoding="utf-8",
            )
            (route_dir / "dry_run_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.route_trust_live_sampling_run.v1",
                        "generatedAt": "2026-06-01T00:17:18+00:00",
                        "ok": True,
                        "dryRun": True,
                        "runtime": "hermes",
                        "storagePreflight": {
                            "schema": "fluxio.route_trust_storage_preflight.v1",
                            "status": "dry_run_only",
                            "canLaunch": False,
                            "canDryRun": True,
                            "storage": {"status": "critical", "probeTimedOut": True},
                            "nextAction": "Dry run is allowed, but live route-trust sampling is blocked.",
                        },
                    }
                ),
                encoding="utf-8",
            )

            evidence = _load_route_trust_sampling_evidence(root)

            self.assertFalse(evidence["dryRun"])
            self.assertEqual(evidence["status"], "passed")
            self.assertEqual(evidence["launchedSamplingMissions"][0]["missionId"], "mission_live")
            self.assertIn("latest.json", evidence["sourcePath"])
            self.assertNotIn("dry_run_latest.json", evidence["sourcePath"])

    def test_route_trust_sampler_skips_task_waiting_for_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            route_dir = root / ".agent_control" / "route_trust_sampling"
            route_dir.mkdir(parents=True, exist_ok=True)
            (route_dir / "closeout_review_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.route_trust_sampling_closeout_review.v1",
                        "proposals": [
                            {
                                "missionId": "mission_waiting_f1",
                                "taskType": "data_f1_analytics",
                                "status": "waiting_for_terminal_state",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = run_route_trust_sampling(
                argparse.Namespace(
                    root=str(root),
                    max_new=1,
                    max_active=4,
                    max_queued=2,
                    runtime="hermes",
                    mode="Autopilot",
                    budget_hours=4,
                    skip_route_contract=False,
                    dry_run=True,
                    write=False,
                )
            )

            self.assertEqual(payload["skippedSamplingMissions"][0]["taskType"], "data_f1_analytics")
            self.assertEqual(payload["skippedSamplingMissions"][0]["reason"], "waiting_for_sampling_closeout")
            self.assertNotEqual(payload["launchedSamplingMissions"][0]["taskType"], "data_f1_analytics")

    def test_mission_watchdog_command_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Watch every active mission",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "queued"
            mission.state.queue_position = 0
            mission.state.remaining_runtime_seconds = 3600
            store.update_mission(mission)

            exit_code, payload = self._run_json_command(
                cmd_mission_watchdog,
                root=str(root),
                stale_minutes=60,
                no_write_report=False,
            )

            report_path = root / ".agent_control" / "mission_watchdog.json"
            problems_path = root / ".agent_control" / "mission_watchdog_problems.json"
            registry_path = root / ".agent_control" / "mission_watchdog_problem_registry.json"
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(pathlib.Path(payload["reportPath"]), report_path)
            self.assertTrue(report_path.exists())
            self.assertTrue(problems_path.exists())
            self.assertTrue(registry_path.exists())
            self.assertEqual(payload["watchdog"]["schema"], "fluxio.mission_watchdog.v1")
            self.assertGreaterEqual(payload["watchdog"]["summary"]["issueCount"], 1)
            self.assertEqual(payload["watchdog"]["problemReport"]["status"], "open")
            self.assertEqual(payload["watchdog"]["problemRegistry"]["status"], "open")
            self.assertGreaterEqual(
                payload["watchdog"]["problemRegistry"]["openProblemCount"],
                1,
            )
            self.assertIn(
                "firstRepairStep",
                payload["watchdog"]["problemRegistry"]["firstOpenProblem"],
            )
            self.assertGreaterEqual(
                json.loads(problems_path.read_text(encoding="utf-8"))["problemCount"],
                1,
            )
            self.assertGreaterEqual(
                json.loads(registry_path.read_text(encoding="utf-8"))["openProblemCount"],
                1,
            )

    def test_mission_watchdog_reports_blocked_delegated_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="openclaw",
                objective="Prove external runtime can continue unattended",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "blocked"
            mission.state.stop_reason = "delegated_runtime_failed"
            mission.proof.summary = "Delegated runtime exited before completing proof."
            mission.proof.blocked_by = ["delegated_runtime_failed"]
            mission.delegated_runtime_sessions = [
                DelegatedRuntimeSession(
                    delegated_id="delegate_failed",
                    runtime_id="openclaw",
                    launch_command="openclaw agent",
                    status="failed",
                    exit_code=1,
                    log_path=str(root / ".agent_control" / "runtime_sessions" / "delegate_failed.log"),
                )
            ]
            store.update_mission(mission)

            exit_code, payload = self._run_json_command(
                cmd_mission_watchdog,
                root=str(root),
                stale_minutes=60,
                no_write_report=False,
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["watchdog"]["problemReport"]["status"], "open")
            first_problem = payload["watchdog"]["problemReport"]["firstProblem"]
            self.assertEqual(first_problem["kind"], "mission_blocked_or_failed")
            self.assertEqual(first_problem["severity"], "bad")
            self.assertIn("provider/auth/runtime", first_problem["firstRepairStep"])
            self.assertIn("delegate_failed", "\n".join(first_problem["evidence"]))

    def test_mission_watchdog_can_record_telegram_problem_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Watch every active mission from phone",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "queued"
            mission.state.queue_position = 0
            mission.state.remaining_runtime_seconds = 3600
            store.update_mission(mission)

            exit_code, payload = self._run_json_command(
                cmd_mission_watchdog,
                root=str(root),
                stale_minutes=60,
                no_write_report=False,
                notify_telegram=True,
                notify_clear=False,
                notification_dry_run=True,
                telegram_destination="@fluxio_test",
            )

            receipt = payload["notificationReceipt"]
            receipts_path = root / ".agent_control" / "delivery_receipts.jsonl"
            self.assertEqual(exit_code, 0)
            self.assertEqual(receipt["status"], "delivered")
            self.assertEqual(receipt["channel"], "telegram")
            self.assertEqual(receipt["event_kind"], "watchdog.problem_report")
            self.assertIn("watchdog problem", receipt["event_message"].lower())
            self.assertTrue(receipts_path.exists())
            self.assertIn("watchdog.problem_report", receipts_path.read_text(encoding="utf-8"))

    def test_telegram_token_can_be_read_from_openclaw_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = pathlib.Path(temp_dir)
            openclaw_dir = home / ".openclaw"
            openclaw_dir.mkdir()
            (openclaw_dir / ".env").write_text(
                "OTHER=value\nTELEGRAM_BOT_TOKEN='123456:test-token'\n",
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {}, clear=True), mock.patch("pathlib.Path.home", return_value=home):
                self.assertEqual(_read_telegram_token(), "123456:test-token")

    def test_telegram_token_can_be_read_from_project_agent_control(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            control = root / ".agent_control"
            control.mkdir()
            (control / "telegram_bot_token.txt").write_text("123456:project-token\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(_read_telegram_token(root), "123456:project-token")

    def test_telegram_delivery_retries_transient_timeout(self) -> None:
        class FakeTelegramResponse:
            def __enter__(self) -> "FakeTelegramResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self) -> bytes:
                return b'{"ok": true}'

        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            home = root / "home"
            openclaw_dir = home / ".openclaw"
            openclaw_dir.mkdir(parents=True)
            (openclaw_dir / ".env").write_text("TELEGRAM_BOT_TOKEN=123456:test-token\n", encoding="utf-8")
            event = MissionEvent(
                mission_id="mission_watchdog",
                kind="watchdog.problem_report",
                message="Transient notification test",
                metadata={},
            )
            with (
                mock.patch.dict(os.environ, {}, clear=True),
                mock.patch("pathlib.Path.home", return_value=home),
                mock.patch("grant_agent.delivery_receipt.time.sleep"),
                mock.patch(
                    "grant_agent.delivery_receipt.urllib.request.urlopen",
                    side_effect=[TimeoutError("timed out"), FakeTelegramResponse()],
                ),
            ):
                receipt = send_telegram_delivery_receipt(
                    event,
                    destination="6528735547",
                    root=root,
                )
            self.assertEqual(receipt.status, "delivered")
            self.assertEqual(receipt.retry_count, 1)

    def test_mission_watchdog_loop_writes_supervisor_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep an external loop over every mission",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "queued"
            mission.state.queue_position = 0
            mission.state.remaining_runtime_seconds = 3600
            store.update_mission(mission)

            exit_code, payload = self._run_json_command(
                cmd_mission_watchdog,
                root=str(root),
                stale_minutes=60,
                no_write_report=False,
                notify_telegram=True,
                notify_clear=False,
                notification_dry_run=True,
                telegram_destination="@fluxio_test",
                loop=True,
                interval_seconds=0,
                max_runs=2,
            )

            supervisor_path = root / ".agent_control" / "mission_watchdog_supervisor.json"
            supervisor = json.loads(supervisor_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["loop"])
            self.assertEqual(payload["runsCompleted"], 2)
            self.assertTrue(supervisor_path.exists())
            self.assertEqual(supervisor["schema"], "fluxio.mission_watchdog_supervisor.v1")
            self.assertEqual(supervisor["loopMode"], "bounded")
            self.assertGreater(supervisor["processPid"], 0)
            self.assertTrue(supervisor["supervisorActive"])
            self.assertEqual(supervisor["runsCompleted"], 2)
            self.assertEqual(supervisor["status"], "open")
            self.assertEqual(supervisor["notificationStatus"], "duplicate_suppressed")
            self.assertEqual(
                supervisor["notificationChannels"]["schema"],
                "fluxio.watchdog_notification_channels.v1",
            )
            self.assertEqual(
                supervisor["notificationChannels"]["inAppStack"]["status"],
                "available",
            )
            self.assertEqual(
                supervisor["notificationChannels"]["browserNotification"]["status"],
                "available",
            )
            self.assertEqual(
                supervisor["notificationChannels"]["telegram"]["status"],
                "duplicate_suppressed",
            )
            self.assertGreaterEqual(supervisor["lastProblemCount"], 1)
            self.assertIn("mission_watchdog_problems.json", supervisor["problemReportPath"])
            self.assertIn("mission-action", supervisor["nextAction"])
            self.assertEqual(
                supervisor["cadencePolicy"]["schema"],
                "fluxio.mission_watchdog_cadence.v1",
            )
            self.assertIn("1 hour", {item["label"] for item in supervisor["cadencePolicy"]["presets"]})
            receipts_path = root / ".agent_control" / "delivery_receipts.jsonl"
            self.assertEqual(
                len(receipts_path.read_text(encoding="utf-8").strip().splitlines()),
                1,
            )

    def test_mission_watchdog_can_record_ntfy_problem_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Notify the phone when the watchdog finds a problem",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "queued"
            mission.state.queue_position = 0
            mission.state.remaining_runtime_seconds = 3600
            store.update_mission(mission)

            exit_code, payload = self._run_json_command(
                cmd_mission_watchdog,
                root=str(root),
                stale_minutes=60,
                no_write_report=False,
                notify_telegram=False,
                notify_ntfy=True,
                notify_clear=False,
                notification_dry_run=True,
                ntfy_topic="fluxio-test-topic",
                loop=False,
                interval_seconds=0,
                max_runs=1,
            )

            supervisor = json.loads((root / ".agent_control" / "mission_watchdog_supervisor.json").read_text(encoding="utf-8"))
            receipt = payload["ntfyNotificationReceipt"]
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["notificationReceipt"]["channel"], "ntfy")
            self.assertEqual(receipt["channel"], "ntfy")
            self.assertEqual(receipt["status"], "delivered")
            self.assertEqual(receipt["delivery_url"], "dry_run://ntfy/fluxio-test-topic")
            self.assertEqual(supervisor["ntfyNotificationStatus"], "delivered")
            self.assertEqual(supervisor["notificationChannels"]["ntfy"]["status"], "delivered")
            self.assertIn("watchdog.problem_report", (root / ".agent_control" / "delivery_receipts.jsonl").read_text(encoding="utf-8"))

    def test_mission_watchdog_one_shot_preserves_active_external_loop_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            future = (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat()
            supervisor_path = root / ".agent_control" / "mission_watchdog_supervisor.json"
            supervisor_path.parent.mkdir(parents=True, exist_ok=True)
            supervisor_path.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.mission_watchdog_supervisor.v1",
                        "root": str(root),
                        "processPid": os.getpid(),
                        "status": "clear",
                        "loopMode": "ongoing",
                        "supervisorActive": True,
                        "startedAt": utc_now_iso(),
                        "lastRunAt": utc_now_iso(),
                        "nextRunAt": future,
                        "intervalSeconds": 1200,
                        "staleMinutes": 60,
                        "runsCompleted": 5,
                        "lastProblemCount": 0,
                        "lastIssueCount": 0,
                        "nextAction": "No watchdog problems found. Keep the external loop active.",
                    }
                ),
                encoding="utf-8",
            )

            exit_code, payload = self._run_json_command(
                cmd_mission_watchdog,
                root=str(root),
                stale_minutes=60,
                no_write_report=False,
                notify_telegram=False,
                notify_clear=False,
                notification_dry_run=True,
                telegram_destination="",
                loop=False,
                interval_seconds=1200,
                max_runs=1,
            )

            supervisor = json.loads(supervisor_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["supervisor"]["loopMode"], "ongoing")
            self.assertEqual(supervisor["loopMode"], "ongoing")
            self.assertEqual(supervisor["processPid"], os.getpid())
            self.assertTrue(supervisor["processAlive"])
            self.assertTrue(supervisor["supervisorActive"])
            self.assertEqual(supervisor["runsCompleted"], 5)
            self.assertIn("lastManualRunAt", supervisor)
            self.assertEqual(supervisor["notificationStatus"], "telegram_not_requested")
            self.assertEqual(
                supervisor["notificationChannels"]["telegram"]["status"],
                "not_requested",
            )
            self.assertEqual(
                supervisor["notificationChannels"]["browserNotification"]["status"],
                "available",
            )

    def test_mission_watchdog_ensure_starts_external_loop_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            fake_process = mock.Mock()
            fake_process.pid = 24680

            with mock.patch(
                "grant_agent.mission_watchdog.subprocess.Popen",
                return_value=fake_process,
            ) as popen:
                result = ensure_watchdog_supervisor_loop(
                    root,
                    stale_minutes=15,
                    interval_seconds=60,
                    notify_telegram=True,
                )

            self.assertTrue(result["started"])
            self.assertEqual(result["pid"], 24680)
            command = popen.call_args.args[0]
            self.assertIn("mission-watchdog", command)
            self.assertIn("--loop", command)
            self.assertIn("--max-runs", command)
            self.assertIn("0", command)
            self.assertIn("--notify-telegram", command)
            self.assertIn("--notify-ntfy", command)
            self.assertIn("--advance-self-improvement", command)
            self.assertIn("--self-improvement-interval-minutes", command)
            self.assertTrue((root / ".agent_control" / "mission_watchdog_loop.out.log").exists())

    def test_mission_watchdog_can_advance_self_improvement_cadence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            script = root / "scripts" / "advance_self_improvement_red_team_loop.py"
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text("# placeholder\n", encoding="utf-8")
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(
                    {
                        "schema": "fluxio.self_improvement_red_team_loop_run.v1",
                        "ok": True,
                        "completedSteps": 1,
                        "stoppedReason": "max_steps_reached",
                        "nextAction": "Run the recorded harder aggregate-only benchmark.",
                        "latestRedTeam": {
                            "historyRows": 24,
                            "nextBenchmarkPlan": {
                                "status": "pending_follow_up",
                                "attemptBudget": 57,
                            },
                        },
                    }
                ),
                stderr="",
            )

            with mock.patch("grant_agent.cli.subprocess.run", return_value=completed) as run:
                exit_code, payload = self._run_json_command(
                    cmd_mission_watchdog,
                    root=str(root),
                    stale_minutes=60,
                    no_write_report=False,
                    notify_telegram=False,
                    notify_clear=False,
                    notification_dry_run=True,
                    telegram_destination="",
                    loop=False,
                    interval_seconds=1200,
                    max_runs=1,
                    advance_self_improvement=True,
                    self_improvement_interval_minutes=60,
                    self_improvement_max_steps=1,
                )

            cadence = payload["supervisor"]["selfImprovement"]
            self.assertEqual(exit_code, 0)
            self.assertEqual(cadence["schema"], "fluxio.self_improvement_watchdog_cadence.v1")
            self.assertEqual(cadence["status"], "completed")
            self.assertEqual(cadence["completedSteps"], 1)
            self.assertEqual(cadence["latestHistoryRows"], 24)
            self.assertEqual(cadence["nextAttemptBudget"], 57)
            self.assertTrue(cadence["aggregateOnly"])
            self.assertFalse(cadence["rawPayloadExport"])
            self.assertEqual(payload["watchdog"]["selfImprovementCadence"]["status"], "completed")
            command = run.call_args.args[0]
            self.assertIn(str(script), command)
            self.assertIn("--max-steps", command)
            latest_path = root / ".agent_control" / "self_improvement_evidence" / "watchdog_latest.json"
            history_path = root / ".agent_control" / "self_improvement_evidence" / "watchdog_history.jsonl"
            self.assertTrue(latest_path.exists())
            self.assertTrue(history_path.exists())
            latest = json.loads(latest_path.read_text(encoding="utf-8"))
            history_rows = [
                json.loads(line)
                for line in history_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(latest["historyPath"], str(history_path))
            self.assertEqual(latest["historyIndex"], 1)
            self.assertEqual(len(history_rows), 1)
            self.assertEqual(history_rows[0]["status"], "completed")
            self.assertEqual(cadence["historyPath"], str(history_path))

    def test_mission_watchdog_ensure_reuses_active_external_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            supervisor_path = root / ".agent_control" / "mission_watchdog_supervisor.json"
            supervisor_path.parent.mkdir(parents=True, exist_ok=True)
            supervisor_path.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.mission_watchdog_supervisor.v1",
                        "root": str(root),
                        "status": "clear",
                        "loopMode": "ongoing",
                        "processPid": os.getpid(),
                        "startedAt": utc_now_iso(),
                        "lastRunAt": utc_now_iso(),
                        "nextRunAt": (
                            datetime.now(timezone.utc) + timedelta(minutes=10)
                        ).isoformat(),
                        "intervalSeconds": 60,
                        "staleMinutes": 15,
                        "runsCompleted": 1,
                        "lastProblemCount": 0,
                        "lastIssueCount": 0,
                        "nextAction": "No watchdog problems found.",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            with mock.patch("grant_agent.mission_watchdog.subprocess.Popen") as popen:
                result = ensure_watchdog_supervisor_loop(root)

            self.assertFalse(result["started"])
            self.assertEqual(result["reason"], "already_active")
            popen.assert_not_called()

    def test_workspace_sync_conflict_resolve_command_records_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            local_root = root / "local-project"
            nas_root = root / "nas-project"
            local_root.mkdir()
            nas_root.mkdir()
            (local_root / "shared.txt").write_text("local-version\n", encoding="utf-8")
            (nas_root / "shared.txt").write_text("nas-version\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.upsert_workspace(
                name="Conflict Workspace",
                root_path=str(local_root),
                default_runtime="hermes",
                local_project_path=str(local_root),
                nas_project_path=str(nas_root),
                sync_mode="auto_nas_mirror",
                sync_direction="local_to_nas",
                sync_conflict_policy="manual_review",
                auto_sync_to_nas=True,
            )

            exit_code, payload = self._run_json_command(
                cmd_workspace_sync_conflict_resolve,
                root=str(root),
                workspace_id=workspace.workspace_id,
                relative_path="shared.txt",
                resolution="nas_wins",
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["receipt"]["schema"], "fluxio.sync_conflict_resolution_receipt.v1")
            self.assertEqual((local_root / "shared.txt").read_text(encoding="utf-8"), "nas-version\n")

    def test_workspace_sync_conflict_resolve_batch_command_records_batch_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            local_root = root / "local-project"
            nas_root = root / "nas-project"
            local_root.mkdir()
            nas_root.mkdir()
            for name in ("a.txt", "b.txt"):
                (local_root / name).write_text(f"local-{name}\n", encoding="utf-8")
                (nas_root / name).write_text(f"nas-{name}\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.upsert_workspace(
                name="Batch Conflict Workspace",
                root_path=str(local_root),
                default_runtime="hermes",
                local_project_path=str(local_root),
                nas_project_path=str(nas_root),
                sync_mode="auto_nas_mirror",
                sync_direction="local_to_nas",
                sync_conflict_policy="manual_review",
                auto_sync_to_nas=True,
            )

            exit_code, payload = self._run_json_command(
                cmd_workspace_sync_conflict_resolve_batch,
                root=str(root),
                workspace_id=workspace.workspace_id,
                relative_path=["a.txt", "b.txt"],
                resolution="local_wins",
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            receipt = payload["receipt"]
            self.assertEqual(receipt["schema"], "fluxio.sync_conflict_batch_resolution_receipt.v1")
            self.assertEqual(receipt["requestedCount"], 2)
            self.assertEqual(receipt["resolvedCount"], 2)
            self.assertEqual(receipt["errorCount"], 0)
            self.assertEqual((nas_root / "a.txt").read_text(encoding="utf-8"), "local-a.txt\n")
            self.assertEqual((nas_root / "b.txt").read_text(encoding="utf-8"), "local-b.txt\n")

    def test_skill_repair_apply_command_updates_learned_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            control_dir = root / ".agent_control"
            control_dir.mkdir(exist_ok=True)
            (control_dir / "learned_skills.json").write_text(
                json.dumps(
                    [
                        {
                            "skill_id": "learned_risky_runner",
                            "label": "Risky Runner",
                            "description": "Runs workspace changes quickly.",
                            "prompt_hint": "Move fast.",
                            "source": {"kind": "learned", "label": "Learned"},
                            "confidence": 0.7,
                            "status": "learned",
                            "tags": ["learned"],
                            "permissions": ["file_write"],
                            "audit": [],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (control_dir / "skill_feedback.json").write_text(
                json.dumps(
                    [
                        {
                            "feedbackId": "feedback_bad",
                            "missionId": "mission_bad",
                            "stepId": "step_risky",
                            "skillId": "learned_risky_runner",
                            "label": "Risky Runner",
                            "sourceKind": "learned",
                            "systemLoss": 0.75,
                            "previousSystemLoss": None,
                            "improvementScore": -10,
                            "executionOk": False,
                            "verificationFailureCount": 1,
                            "verificationFailures": ["python -m pytest"],
                            "changedFileCount": 0,
                            "nextAction": "repair",
                            "createdAt": "2026-05-28T00:00:00+00:00",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            exit_code, payload = self._run_json_command(
                cmd_skill_repair_apply,
                root=str(root),
                proposal_id="skill_repair:learned_risky_runner",
                skill_id="learned_risky_runner",
                reviewer="operator",
                validation_mission_id="mission_validation",
                validation_step_id="step_clean",
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["receipt"]["status"], "applied")
            updated = json.loads((control_dir / "learned_skills.json").read_text(encoding="utf-8"))
            self.assertEqual(updated[0]["status"], "repair_applied")
            self.assertIn("Repair note", updated[0]["prompt_hint"])

    def test_mission_action_parallelize_worktree_moves_queued_mission_to_isolated_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            active = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Long active mission",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )
            active.state.status = "running"
            active.proof.changed_files = ["web/src/notifications/NotificationStack.jsx"]
            store.update_mission(active)
            queued = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Parallel F1 analytics mission",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )
            queued.proof.changed_files = ["apps/f1-analytics/dashboard.tsx"]
            store.update_mission(queued)

            exit_code, payload = self._run_json_command(
                cmd_mission_action,
                root=str(root),
                mission_id=queued.mission_id,
                action="parallelize-worktree",
                launch_async=False,
            )

            moved = ControlRoomStore(root).get_mission(queued.mission_id)
            parallel_workspace = ControlRoomStore(root).get_workspace(
                payload["parallelWorkspace"]["workspace_id"]
            )
            self.assertEqual(exit_code, 0)
            self.assertIsNotNone(moved)
            self.assertIsNotNone(parallel_workspace)
            self.assertNotEqual(moved.workspace_id, workspace.workspace_id)
            self.assertEqual(moved.state.queue_position, 0)
            self.assertIsNone(moved.state.blocking_mission_id)
            self.assertEqual(moved.state.queue_reason, "")
            self.assertEqual(moved.state.last_budget_pause_reason, "Mission is queued and ready to start.")
            self.assertIsNone(moved.state.stop_reason)
            self.assertEqual(parallel_workspace.execution_target_preference, "isolated_worktree")
            self.assertEqual(moved.execution_scope.requested, "isolated")
            self.assertEqual(moved.execution_scope.execution_target, "worktree")
            self.assertEqual(payload["scopeSafety"], "safe")
            self.assertEqual(payload["scopeEvidence"]["activeFileCount"], 1)
            self.assertEqual(payload["scopeEvidence"]["queuedFileCount"], 1)

    def test_mission_action_parallelize_worktree_refuses_unknown_file_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            active = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Long active mission",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )
            active.state.status = "running"
            store.update_mission(active)
            queued = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Parallel F1 analytics mission",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )

            exit_code, payload = self._run_json_command(
                cmd_mission_action,
                root=str(root),
                mission_id=queued.mission_id,
                action="parallelize-worktree",
                launch_async=False,
            )

            unchanged = ControlRoomStore(root).get_mission(queued.mission_id)
            self.assertEqual(exit_code, 1)
            self.assertIn("disjoint live file-scope evidence", payload["error"])
            self.assertEqual(payload["scopeSafety"], "unknown")
            self.assertIsNotNone(unchanged)
            self.assertEqual(unchanged.workspace_id, workspace.workspace_id)
            self.assertGreater(unchanged.state.queue_position, 0)

    def test_mission_action_parallelize_worktree_refuses_overlapping_file_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            active = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Long active mission",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )
            active.state.status = "running"
            active.proof.changed_files = ["web/src/fluxio/FluxioShell.jsx"]
            store.update_mission(active)
            queued = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Parallel Builder polish mission",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )
            queued.proof.changed_files = ["web/src/fluxio/FluxioShell.jsx"]
            store.update_mission(queued)

            exit_code, payload = self._run_json_command(
                cmd_mission_action,
                root=str(root),
                mission_id=queued.mission_id,
                action="parallelize-worktree",
                launch_async=False,
            )

            unchanged = ControlRoomStore(root).get_mission(queued.mission_id)
            self.assertEqual(exit_code, 1)
            self.assertIn("overlaps", payload["error"])
            self.assertEqual(payload["scopeSafety"], "overlap")
            self.assertEqual(
                payload["scopeEvidence"]["overlapFiles"],
                ["web/src/fluxio/fluxioshell.jsx"],
            )
            self.assertIsNotNone(unchanged)
            self.assertEqual(unchanged.workspace_id, workspace.workspace_id)
            self.assertGreater(unchanged.state.queue_position, 0)

    def test_mission_proof_digest_writes_reviewable_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Prove the mission digest path.",
                success_checks=["digest contains proof"],
                mode="Focus",
                verification_commands=["python -m pytest tests -q"],
                max_runtime_seconds=3600,
                route_overrides=[
                    {"role": "planner", "provider": "openai", "model": "gpt-5.5"}
                ],
            )
            mission.state.status = "completed"
            mission.state.provider_runtime_truth = {
                "authPresent": True,
                "authMode": "oauth",
                "authPath": "OpenAI Codex OAuth",
                "activeRoute": {"role": "planner", "provider": "openai", "model": "gpt-5.5"},
            }
            mission.proof.summary = "Digest proof passed."
            mission.proof.passed_checks = ["python -m pytest tests -q"]
            store.update_mission(mission)
            output = root / ".agent_control" / "proof_digests" / f"{mission.mission_id}.md"

            exit_code, payload = self._run_json_command(
                cmd_mission_proof_digest,
                root=str(root),
                mission_id=mission.mission_id,
                output=str(output),
                json=False,
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["missionId"], mission.mission_id)
            self.assertTrue(output.exists())
            report = output.read_text(encoding="utf-8")
            self.assertIn("Provider Truth", report)
            self.assertIn("Digest proof passed.", report)
            self.assertIn("python -m pytest tests -q", report)

    def test_auth_store_provider_lookup_reads_hermes_credential_pool(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            auth_store = pathlib.Path(temp_dir) / "auth.json"
            auth_store.write_text(
                json.dumps(
                    {
                        "credential_pool": {
                            "minimax": [
                                {
                                    "label": "minimax-api-key",
                                    "auth_type": "api_key",
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            self.assertTrue(_auth_store_has_provider(auth_store, "minimax"))
            self.assertFalse(_auth_store_has_provider(auth_store, "minimax-oauth"))

    def test_minimax_auth_visible_reads_hermes_minimax_credential_pool(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            auth_store = pathlib.Path(temp_dir) / "auth.json"
            auth_store.write_text(
                json.dumps(
                    {
                        "credential_pool": {
                            "minimax": [
                                {
                                    "label": "minimax-api-key",
                                    "auth_type": "api_key",
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            workspace = mock.Mock(minimax_auth_mode="minimax-portal-oauth")
            with mock.patch.dict(
                "os.environ",
                {
                    "MINIMAX_API_KEY": "",
                    "FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT": "",
                    "HERMES_AUTH_STORE": str(auth_store),
                    "FLUXIO_DISABLE_WSL_AUTH_DISCOVERY": "1",
                },
                clear=False,
            ):
                visible, detail = _minimax_auth_visible_for_workspace(workspace)

            self.assertTrue(visible)
            self.assertTrue(detail["oauthPresent"])

    def test_provider_presence_reads_shared_hermes_credential_pool_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            auth_store = pathlib.Path(temp_dir) / "auth.json"
            auth_store.write_text(
                json.dumps(
                    {
                        "credential_pool": {
                            "anthropic": [{"auth_type": "api_key"}],
                            "openrouter": [{"auth_type": "api_key"}],
                            "minimax": [{"auth_type": "api_key"}],
                            "opencode-go": [{"auth_type": "api_key"}],
                        }
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.dict(
                "os.environ",
                {
                    "ANTHROPIC_API_KEY": "",
                    "OPENROUTER_API_KEY": "",
                    "MINIMAX_API_KEY": "",
                    "OPENCODE_API_KEY": "",
                    "HERMES_AUTH_STORE": str(auth_store),
                    "FLUXIO_DISABLE_WSL_AUTH_DISCOVERY": "1",
                },
                clear=False,
            ):
                presence = _provider_auth_presence_from_env()

            self.assertTrue(presence["anthropic"])
            self.assertTrue(presence["openrouter"])
            self.assertTrue(presence["minimax"])
            self.assertTrue(presence["minimax-portal"])
            self.assertTrue(presence["opencode-go"])

    def test_provider_presence_reads_native_opencode_go_auth_store(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = pathlib.Path(temp_dir) / "home"
            auth_store = home / ".local" / "share" / "opencode" / "auth.json"
            auth_store.parent.mkdir(parents=True)
            auth_store.write_text(
                json.dumps({"opencode-go": {"type": "api"}}),
                encoding="utf-8",
            )
            with mock.patch.dict(
                "os.environ",
                {
                    "OPENCODE_API_KEY": "",
                    "HOME": str(home),
                    "FLUXIO_DISABLE_WSL_AUTH_DISCOVERY": "1",
                },
                clear=False,
            ):
                presence = _provider_auth_presence_from_env()

            self.assertTrue(presence["opencode-go"])

    def test_provider_presence_does_not_treat_plain_opencode_cli_auth_as_go(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = pathlib.Path(temp_dir) / "home"
            auth_store = home / ".local" / "share" / "opencode" / "auth.json"
            auth_store.parent.mkdir(parents=True)
            auth_store.write_text(
                json.dumps({"openai": {"type": "oauth"}, "minimax-coding-plan": {"type": "api"}}),
                encoding="utf-8",
            )
            with mock.patch.dict(
                "os.environ",
                {
                    "OPENCODE_API_KEY": "",
                    "HOME": str(home),
                    "FLUXIO_DISABLE_WSL_AUTH_DISCOVERY": "1",
                },
                clear=False,
            ):
                presence = _provider_auth_presence_from_env()

            self.assertFalse(presence["opencode-go"])

    def test_live_nas_system_audit_evidence_supplies_operator_proven_route_trust(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            evidence_path = root / ".agent_control" / "live_nas_system_audit_latest.json"
            evidence_path.parent.mkdir(parents=True)
            checked_at = datetime.now(timezone.utc).isoformat()
            evidence_path.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_nas_system_audit_snapshot.v1",
                        "ok": True,
                        "checkedAt": checked_at,
                        "sourceHost": "100.125.54.118",
                        "sourceRoot": "/volume1/Saclay/projects/syntelos/releases/20260505-212517",
                        "maxAgeSeconds": 21600,
                        "audit": {
                            "workspaceRoot": "/volume1/Saclay/projects/syntelos/releases/20260505-212517",
                            "generatedAt": checked_at,
                            "summary": "NAS audit is operator proven.",
                            "liveNasEvidence": {
                                "status": "passed",
                                "counts": {"missions": 52, "activeMissions": 2},
                                "runningMissions": [
                                    {"mission_id": "mission_live", "status": "running", "runtime_id": "hermes"}
                                ],
                            },
                            "routeTrustMaturity": {
                                "schema": "fluxio.operator_confidence_calibration.v1",
                                "status": "operator_proven",
                                "operatorConfidenceScore": 92,
                                "taskCount": 6,
                                "provenTaskCount": 6,
                                "missingOperatorValueSamples": 0,
                                "nextRepairStep": "Maintain periodic Hermes route-trust sampling.",
                            },
                            "releaseReadiness": {
                                "status": "ready_for_1_0_validation",
                                "score": 97,
                                "requiredGateSummary": {"passed": 8, "total": 8, "score": 100},
                                "qualityScore": 84,
                            },
                            "redTeamEscalationEvidence": {
                                "schema": "fluxio.red_team_escalation_snapshot.v1",
                                "summary": {
                                    "runCount": 4,
                                    "status": "passing",
                                    "latestPreset": "hackaprompt",
                                    "latestResistanceScore": 98,
                                    "latestDifficultyLevel": 4,
                                    "nextDifficultyLevel": 5,
                                    "nextAttemptBudget": 13,
                                    "passStreak": 3,
                                    "cleanPass": True,
                                    "shouldEscalate": True,
                                    "satisfiedEscalationTargets": 2,
                                    "pendingEscalationTargets": 0,
                                    "nextAction": "Run the next harder red-team benchmark.",
                                },
                                "history": [],
                                "trend": {"status": "passing"},
                                "escalationAudit": {"status": "passing"},
                            },
                            "t3Deficits": [],
                        },
                    }
                ),
                encoding="utf-8",
            )

            evidence = _load_live_nas_system_audit_evidence(root)

            self.assertEqual(evidence["status"], "passed")
            self.assertEqual(evidence["routeTrustMaturity"]["status"], "operator_proven")
            self.assertEqual(evidence["routeTrustMaturity"]["provenTaskCount"], 6)
            self.assertEqual(evidence["liveNasEvidence"]["counts"]["missions"], 52)
            self.assertEqual(evidence["redTeamEscalationEvidence"]["summary"]["runCount"], 4)
            self.assertEqual(evidence["redTeamEscalationEvidence"]["summary"]["nextDifficultyLevel"], 5)
            self.assertEqual(evidence["releaseReadiness"]["score"], 97)
            self.assertEqual(evidence["sourceRoot"], "/volume1/Saclay/projects/syntelos/releases/20260505-212517")

    def test_live_nas_system_audit_evidence_ignores_self_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir).resolve()
            evidence_path = root / ".agent_control" / "live_nas_system_audit_latest.json"
            evidence_path.parent.mkdir(parents=True)
            checked_at = datetime.now(timezone.utc).isoformat()
            evidence_path.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_nas_system_audit_snapshot.v1",
                        "ok": True,
                        "checkedAt": checked_at,
                        "sourceRoot": str(root),
                        "maxAgeSeconds": 21600,
                        "audit": {
                            "workspaceRoot": str(root),
                            "generatedAt": checked_at,
                            "releaseReadiness": {
                                "status": "blocked",
                                "score": 75,
                                "requiredGateSummary": {"passed": 6, "total": 8, "score": 75},
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            evidence = _load_live_nas_system_audit_evidence(root)

            self.assertEqual(evidence, {})

    def test_control_room_system_audit_digest_prefers_authoritative_live_nas_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            evidence_path = root / ".agent_control" / "live_nas_system_audit_latest.json"
            evidence_path.parent.mkdir(parents=True)
            checked_at = datetime.now(timezone.utc).isoformat()
            evidence_path.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_nas_system_audit_snapshot.v1",
                        "ok": True,
                        "checkedAt": checked_at,
                        "audit": {
                            "generatedAt": checked_at,
                            "summary": "Authoritative NAS audit summary.",
                            "categories": [
                                {
                                    "category": "Launch friction and beginner experience",
                                    "score_out_of_20": 20,
                                    "t3_reference_score_out_of_20": 18,
                                    "verdict": "Ahead from live evidence.",
                                    "gaps": ["Public signing remains."],
                                    "next_moves": ["Publish signed installer."],
                                },
                                {
                                    "category": "Roadmap clarity and self-improvement",
                                    "score_out_of_20": 20,
                                    "t3_reference_score_out_of_20": 14,
                                    "verdict": "Ahead from live evidence.",
                                    "gaps": [],
                                    "next_moves": ["Run the next harder red-team sample."],
                                },
                            ],
                            "t3Deficits": [],
                            "badFirst": [
                                {
                                    "title": "Launch friction and beginner experience",
                                    "detail": "Signed installer remains unproven.",
                                }
                            ],
                            "routeTrustMaturity": {
                                "status": "operator_proven",
                                "operatorConfidenceScore": 92,
                                "taskCount": 6,
                                "provenTaskCount": 6,
                                "missingOperatorValueSamples": 0,
                                "capReason": "Every tracked route category is value-scored.",
                                "nextAction": "Maintain periodic Hermes route-trust sampling.",
                            },
                            "redTeamEscalationEvidence": {
                                "history": [
                                    {
                                        "schema": "fluxio.red_team_escalation_history.v1",
                                        "recordedAt": "2026-05-29T16:17:34+00:00",
                                        "preset": "hackaprompt",
                                        "status": "pass",
                                        "resistance_score": 100,
                                        "attempt_count": 27,
                                        "blocked_attempt_count": 27,
                                        "difficultyLevel": 5,
                                        "nextDifficultyLevel": 5,
                                        "passStreak": 9,
                                        "cleanPass": True,
                                        "shouldEscalate": True,
                                        "nextAttemptBudget": 29,
                                        "targetResistanceScore": 98,
                                        "nextTactics": ["direct_policy_probe", "roleplay", "authority"],
                                        "observedTactics": [
                                            "cross_tool",
                                            "format_smuggling",
                                            "indirect_context",
                                            "multi_turn",
                                            "obfuscation",
                                            "roleplay",
                                        ],
                                    }
                                ],
                                "summary": {
                                    "runCount": 10,
                                    "latestResistanceScore": 100,
                                    "latestDifficultyLevel": 5,
                                    "nextDifficultyLevel": 5,
                                    "nextAttemptBudget": 29,
                                    "passStreak": 9,
                                    "pendingEscalationTargets": 1,
                                    "nextAction": "Run the next harder red-team benchmark.",
                                },
                                "nextBenchmarkPlan": {
                                    "schema": "fluxio.red_team_next_benchmark_plan.v1",
                                    "attemptBudget": 29,
                                    "targetResistanceScore": 98,
                                    "tactics": ["direct_policy_probe", "roleplay", "authority"],
                                    "command": {
                                        "shell": "npm run sample:self-improvement-red-team -- --preset hackaprompt",
                                    },
                                }
                            },
                            "benchmarks": {
                                "t3Code": {
                                    "name": "T3 Code",
                                    "latestObservedRelease": "v0.0.25-nightly observed",
                                    "observedStrengths": ["npx t3 launch", "worktrees"],
                                }
                            },
                            "missionArtifactRepairPlan": {
                                "schema": "fluxio.mission_artifact_repair_plan.v1",
                                "status": "repairs_blocked_by_nas_storage",
                                "repairMissionCount": 1,
                                "storagePreflight": {
                                    "schema": "fluxio.mission_artifact_repair_storage_preflight.v1",
                                    "status": "blocked",
                                    "canResume": False,
                                },
                                "repairs": [
                                    {
                                        "missionId": "mission_f1_failed",
                                        "canResumeNow": False,
                                        "resumeBlockedBy": ["nas_storage_pressure"],
                                    }
                                ],
                            },
                            "nasStoragePressureEvidence": {
                                "schema": "fluxio.nas_storage_pressure.v1",
                                "status": "critical",
                                "mount": "/volume1/Saclay",
                                "usedPercent": 100,
                                "availableBytes": 0,
                            },
                            "nasStorageCleanupPlan": {
                                "schema": "fluxio.nas_storage_cleanup_plan.v1",
                                "status": "no_generated_candidates_found",
                                "estimatedReclaimableMB": 0.0,
                                "cleanupCandidates": [],
                                "volumeAccountingGB": 779.45,
                                "largestVolumeAccountingPath": "/volume1/Duncan",
                                "volumeAccountingUsage": [
                                    {"path": "/volume1/Duncan", "sizeGB": 779.06}
                                ],
                                "timedOutExternalProbePaths": ["/volume1/Saclay/projects/syntelos"],
                                "timedOutVolumeAccountingPaths": ["/volume1/@synologydrive"],
                                "btrfsAccounting": ["Data, single: total=3.48TiB, used=3.48TiB"],
                                "destructiveActionsExecuted": False,
                                "nextAction": "Review non-generated NAS data before expecting mission writes.",
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            digest = _build_system_audit_digest(
                root=root,
                release_readiness={},
                harness_lab={"routeTrustCoverage": {"operatorConfidenceScore": 10}},
                missions=[],
                workspaces=[],
            )

            self.assertEqual(digest["source"], "live_nas_system_audit")
            self.assertEqual(digest["operatorConfidenceScore"], 92)
            self.assertEqual(digest["mustBeatStatus"]["ahead"], 2)
            self.assertEqual(digest["mustBeatStatus"]["deficitCount"], 0)
            self.assertEqual(digest["systemScoreOutOf20"], 20.0)
            self.assertEqual(digest["redTeamEscalation"]["nextAttemptBudget"], 29)
            self.assertEqual(digest["redTeamEscalation"]["currentPressureIndex"], 50)
            self.assertEqual(digest["redTeamEscalation"]["nextPressureIndex"], 55)
            self.assertEqual(digest["redTeamEscalation"]["nextDifficultyLabel"], "L5 pressure 55")
            self.assertEqual(digest["redTeamEscalation"]["summary"]["runCount"], 10)
            self.assertEqual(len(digest["redTeamEscalation"]["history"]), 1)
            self.assertEqual(
                digest["redTeamEscalation"]["schema"],
                "fluxio.red_team_escalation_snapshot.v1",
            )
            self.assertEqual(
                digest["redTeamEscalation"]["nextBenchmarkPlan"]["schema"],
                "fluxio.red_team_next_benchmark_plan.v1",
            )
            self.assertEqual(digest["redTeamEscalation"]["nextBenchmarkPlan"]["difficultyLabel"], "L5 pressure 55")
            self.assertTrue(digest["redTeamEscalation"]["nextBenchmarkPlan"]["levelCapReached"])
            self.assertEqual(digest["redTeamEscalation"]["nextBenchmarkPlan"]["currentPressureIndex"], 50)
            self.assertEqual(digest["redTeamEscalation"]["nextBenchmarkPlan"]["nextPressureIndex"], 55)
            self.assertIn(
                "pressure index advances to 55",
                digest["redTeamEscalation"]["nextBenchmarkPlan"]["successCriteria"],
            )
            self.assertIn(
                "sample:self-improvement-red-team",
                digest["redTeamEscalation"]["nextBenchmarkPlan"]["command"]["shell"],
            )
            self.assertIn("L5 pressure 55", digest["redTeamEscalation"]["nextBenchmarkPlan"]["command"]["shell"])
            self.assertEqual(digest["t3Reference"]["latestObservedRelease"], "v0.0.25-nightly observed")
            self.assertEqual(digest["missionArtifactRepairPlan"]["status"], "repairs_blocked_by_nas_storage")
            self.assertFalse(digest["missionArtifactRepairPlan"]["storagePreflight"]["canResume"])
            self.assertFalse(digest["missionArtifactRepairPlan"]["repairs"][0]["canResumeNow"])
            self.assertEqual(digest["designDebtSummary"]["schema"], "fluxio.design_debt_summary.v1")
            self.assertTrue(digest["designDebtSummary"]["rows"])
            self.assertEqual(
                digest["missionAdvancementSummary"]["schema"],
                "fluxio.mission_advancement_summary.v1",
            )
            self.assertEqual(digest["missionAdvancementSummary"]["repairMissionCount"], 1)
            self.assertEqual(
                digest["missionAdvancementSummary"]["rows"][0]["missionId"],
                "mission_f1_failed",
            )
            self.assertEqual(digest["storageTriageSummary"]["schema"], "fluxio.storage_triage_summary.v1")
            self.assertEqual(digest["storageTriageSummary"]["status"], "blocked")
            self.assertEqual(digest["storageTriageSummary"]["generatedCandidateCount"], 0)
            self.assertFalse(digest["storageTriageSummary"]["rows"][0]["safeToDelete"])
            self.assertEqual(digest["operatorNextPath"]["schema"], "fluxio.operator_next_path.v1")
            self.assertEqual(digest["operatorNextPath"]["status"], "blocked")
            self.assertEqual(digest["operatorNextPath"]["steps"][0]["id"], "storage-preflight")
            self.assertTrue(digest["operatorNextPath"]["steps"][0]["blocksLaunch"])
            self.assertEqual(digest["speedSupervisorSummary"]["schema"], "fluxio.speed_supervisor_summary.v1")
            self.assertEqual(digest["speedSupervisorSummary"]["status"], "blocked")
            self.assertTrue(digest["speedSupervisorSummary"]["rows"])
            self.assertTrue(digest["improvementQueue"])
            self.assertEqual(digest["improvementQueue"][0]["lane"], "Launch and onboarding")
            self.assertIn("installer", digest["improvementQueue"][0]["nextAction"])

    def test_control_room_system_audit_digest_uses_local_mission_repair_evidence_when_nas_audit_omits_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            control = root / ".agent_control"
            control.mkdir(parents=True)
            checked_at = datetime.now(timezone.utc).isoformat()
            (control / "live_nas_system_audit_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_nas_system_audit_snapshot.v1",
                        "ok": True,
                        "checkedAt": checked_at,
                        "audit": {
                            "generatedAt": checked_at,
                            "summary": "Authoritative audit without mission-output detail.",
                            "categories": [
                                {
                                    "category": "Proof, verification, and trust",
                                    "score_out_of_20": 12,
                                    "t3_reference_score_out_of_20": 14,
                                    "verdict": "Needs live output repair.",
                                    "gaps": ["Missing artifact proof."],
                                    "next_moves": ["Repair weak mission."],
                                }
                            ],
                            "benchmarks": {"t3Code": {"latestObservedRelease": "stale"}},
                        },
                    }
                ),
                encoding="utf-8",
            )
            (control / "t3_code_benchmark_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.t3_code_release_benchmark.v1",
                        "checkedAt": checked_at,
                        "source": "https://api.github.com/repos/pingdotgg/t3code/releases?per_page=50",
                        "latestObservedRelease": "fresh t3 release evidence",
                        "productPageEvidence": {"verifiedClaims": ["open_source_control_plane"]},
                    }
                ),
                encoding="utf-8",
            )
            (control / "live_mission_detail_status_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_mission_detail_status.v1",
                        "checkedAt": checked_at,
                        "missionRows": [
                            {
                                "missionId": "mission_f1_repair",
                                "title": "Build a first usable prototype/report F1",
                                "runtime": "hermes",
                                "status": "verification_failed",
                                "agentMessages": 3,
                                "artifactGate": {
                                    "status": "missing_required_output",
                                    "runtimeOutputCount": 0,
                                    "artifactCount": 0,
                                },
                                "runtimeTranscript": {"status": "missing_transcript"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (control / "mission_artifact_repair_plan_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.mission_artifact_repair_plan.v1",
                        "generatedAt": checked_at,
                        "status": "repairs_blocked_by_nas_storage",
                        "repairMissionCount": 1,
                        "repairs": [
                            {
                                "missionId": "mission_f1_repair",
                                "title": "Build a first usable prototype/report F1",
                                "runtime": "hermes",
                                "status": "verification_failed",
                                "artifactGateStatus": "missing_required_output",
                                "runtimeTranscriptStatus": "missing_transcript",
                                "observedRuntimeOutputCount": 0,
                                "observedAgentMessageCount": 3,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            digest = _build_system_audit_digest(
                root=root,
                release_readiness={},
                harness_lab={},
                missions=[],
                workspaces=[],
            )

            self.assertEqual(digest["missionAdvancementSummary"]["repairMissionCount"], 1)
            self.assertEqual(digest["missionAdvancementSummary"]["rows"][0]["missionId"], "mission_f1_repair")
            self.assertEqual(digest["liveMissionOutputQuality"]["repairMissionCount"], 1)
            self.assertEqual(digest["operatorNextPath"]["schema"], "fluxio.operator_next_path.v1")
            self.assertTrue(digest["operatorNextPath"]["steps"])
            self.assertEqual(digest["t3Reference"]["latestObservedRelease"], "fresh t3 release evidence")

    def test_synced_nas_audit_keeps_newer_authenticated_agent_switch_proof(self) -> None:
        local = {
            "agentCheckedAt": "2026-05-29T09:40:52+00:00",
            "agentSourcePath": "tmp-ui-checks/authenticated-live-agent/latest.json",
            "agentStatus": "passed",
            "agentPassedChecks": ["live-mission-click-switch", "agent-thread-not-empty"],
        }
        synced = {
            "status": "passed",
            "counts": {"missions": 52},
            "agentCheckedAt": "2026-05-28T19:12:32+00:00",
            "agentSourcePath": "/volume1/old-agent.json",
            "agentStatus": "passed",
            "agentPassedChecks": ["agent-thread-not-empty"],
        }

        merged = _merge_synced_live_nas_evidence(
            local,
            synced,
            system_audit_path=".agent_control/live_nas_system_audit_latest.json",
            system_audit_checked_at="2026-05-29T09:52:25+00:00",
        )

        self.assertEqual(merged["counts"]["missions"], 52)
        self.assertEqual(merged["agentSourcePath"], "tmp-ui-checks/authenticated-live-agent/latest.json")
        self.assertIn("live-mission-click-switch", merged["agentPassedChecks"])
        self.assertTrue(merged["newerLocalAgentEvidencePreserved"])

    def test_live_nas_evidence_reads_newest_agent_report_from_agent_control_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            control = root / ".agent_control"
            control.mkdir(parents=True)
            (control / "live-agent-current-check.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.authenticated_live_agent.v1",
                        "ok": True,
                        "checkedAt": "2026-05-31T07:39:00+00:00",
                        "summary": {
                            "selectedMission": {
                                "mission_id": "mission_current",
                                "title": "Current live Hermes proof",
                            }
                        },
                        "checks": [
                            {"checkId": "live-diagnostic-rows-do-not-hijack-report-reader", "passed": True},
                            {"checkId": "live-message-click-switch", "passed": True},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            old = root / "tmp-ui-checks" / "authenticated-live-agent"
            old.mkdir(parents=True)
            (old / "authenticated-live-agent-check.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.authenticated_live_agent.v1",
                        "ok": True,
                        "checkedAt": "2026-05-28T19:12:00+00:00",
                        "summary": {
                            "selectedMission": {
                                "mission_id": "mission_old",
                                "title": "Old live proof",
                            }
                        },
                        "checks": [{"checkId": "agent-thread-not-empty", "passed": True}],
                    }
                ),
                encoding="utf-8",
            )

            evidence = _load_live_nas_evidence(root)

            self.assertEqual(evidence["agentSelectedMission"]["mission_id"], "mission_current")
            self.assertIn("live-diagnostic-rows-do-not-hijack-report-reader", evidence["agentPassedChecks"])
            self.assertIn(".agent_control", evidence["agentSourcePath"])

    def test_live_nas_evidence_prefers_newer_screenshot_control_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            control = root / ".agent_control"
            screenshots = control / "screenshots"
            screenshots.mkdir(parents=True)
            (control / "old-live-control-check.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.authenticated_live_control.v1",
                        "ok": True,
                        "checkedAt": "2026-05-31T13:05:12+00:00",
                        "summary": {
                            "counts": {"missions": 53, "activeMissions": 2},
                            "runtimeCounts": {"hermes": 49, "openclaw": 4},
                            "runningMissions": [{"mission_id": "mission_old", "runtime_id": "hermes"}],
                        },
                        "checks": [{"checkId": "old-live-data", "passed": True}],
                    }
                ),
                encoding="utf-8",
            )
            (screenshots / "active-hermes-m3-finalgreen-20260602-check.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.authenticated_live_control.v1",
                        "ok": True,
                        "checkedAt": "2026-06-02T10:29:12+00:00",
                        "summary": {
                            "counts": {"missions": 26, "activeMissions": 1, "queuedMissions": 0},
                            "runtimeCounts": {"hermes": 26},
                            "runningMissions": [
                                {
                                    "mission_id": "mission_1bf9a009f1",
                                    "runtime_id": "hermes",
                                    "title": "Hermes MiniMax-M3 frontend cleanup mission use",
                                }
                            ],
                            "notificationCount": 24,
                            "sliceNotificationCount": 1,
                        },
                        "checks": [{"checkId": "no-demo-data-visible", "passed": True}],
                    }
                ),
                encoding="utf-8",
            )

            evidence = _load_live_nas_evidence(root)

            self.assertEqual(evidence["counts"]["missions"], 26)
            self.assertEqual(evidence["runtimeCounts"], {"hermes": 26})
            self.assertEqual(evidence["runningMissions"][0]["mission_id"], "mission_1bf9a009f1")
            self.assertIn("screenshots", evidence["sourcePath"])
            self.assertIn("no-demo-data-visible", evidence["passedChecks"])

    def test_system_audit_keeps_fresh_local_watchdog_gate_over_stale_synced_release(self) -> None:
        local = {
            "status": "ready_for_1_0_validation",
            "score": 92,
            "calculatedAt": "2026-05-30T11:15:00+00:00",
            "gates": [
                {
                    "gateId": "mission_watchdog_clear",
                    "required": True,
                    "passed": True,
                    "activeMissionCount": 2,
                    "supervisorActive": True,
                    "supervisorStale": False,
                    "supervisorProcessAlive": True,
                    "lastRunAt": "2026-05-30T11:13:46+00:00",
                    "nextRunAt": "2026-05-30T11:33:46+00:00",
                }
            ],
        }
        synced = {
            "status": "ready_for_1_0_validation",
            "score": 97,
            "calculatedAt": "2026-05-30T02:52:00+00:00",
            "gates": [
                {
                    "gateId": "mission_watchdog_clear",
                    "required": True,
                    "passed": True,
                    "activeMissionCount": 2,
                    "lastRunAt": "2026-05-30T02:51:18+00:00",
                    "nextRunAt": "2026-05-30T03:11:18+00:00",
                }
            ],
        }

        selected = _select_system_audit_release_readiness(
            local_release=local,
            synced_release=synced,
            live_nas_system_audit={
                "status": "passed",
                "sourcePath": ".agent_control/live_nas_system_audit_latest.json",
                "checkedAt": "2026-05-30T11:40:25+00:00",
            },
        )

        watchdog_gate = next(item for item in selected["gates"] if item["gateId"] == "mission_watchdog_clear")
        self.assertEqual(selected["source"], "local_release_readiness")
        self.assertTrue(selected["newerLocalReleaseReadinessPreserved"])
        self.assertTrue(watchdog_gate["supervisorProcessAlive"])
        self.assertFalse(watchdog_gate["supervisorStale"])
        self.assertEqual(watchdog_gate["lastRunAt"], "2026-05-30T11:13:46+00:00")
        self.assertEqual(
            selected["syncedReleaseReadinessSuperseded"]["sourcePath"],
            ".agent_control/live_nas_system_audit_latest.json",
        )

    def test_system_audit_uses_live_nas_when_local_only_blocked_by_watchdog_drift(self) -> None:
        local = {
            "status": "close_but_blocked",
            "score": 79,
            "qualityScore": 44,
            "calculatedAt": "2026-06-06T20:46:50+00:00",
            "requiredGateSummary": {"passed": 7, "total": 8, "score": 88},
            "gates": [
                {
                    "gateId": "verify_desktop_contract",
                    "required": True,
                    "passed": True,
                },
                {
                    "gateId": "mission_watchdog_clear",
                    "required": True,
                    "passed": False,
                    "activeMissionCount": 4,
                    "details": "Watchdog found stale local active mission problem(s).",
                    "supervisorActive": True,
                    "supervisorStale": False,
                    "supervisorProcessAlive": True,
                    "lastRunAt": "2026-06-06T20:46:38+00:00",
                    "nextRunAt": "2026-06-06T21:06:38+00:00",
                },
            ],
        }
        synced = {
            "status": "ready_for_1_0_validation",
            "score": 100,
            "qualityScore": 100,
            "calculatedAt": "2026-06-06T20:22:40+00:00",
            "requiredGateSummary": {"passed": 8, "total": 8, "score": 100},
            "gates": [
                {
                    "gateId": "mission_watchdog_clear",
                    "required": True,
                    "passed": True,
                    "activeMissionCount": 1,
                    "supervisorActive": True,
                    "supervisorStale": False,
                    "supervisorProcessAlive": True,
                    "lastRunAt": "2026-06-06T20:22:37+00:00",
                    "nextRunAt": "2026-06-06T20:42:37+00:00",
                },
            ],
        }

        selected = _select_system_audit_release_readiness(
            local_release=local,
            synced_release=synced,
            live_nas_system_audit={
                "status": "passed",
                "sourcePath": ".agent_control/live_nas_system_audit_latest.json",
                "checkedAt": "2026-06-06T20:37:37+00:00",
            },
        )

        self.assertEqual(selected["source"], "live_nas_system_audit")
        self.assertTrue(selected["localWatchdogDriftSuperseded"])
        self.assertEqual(selected["score"], 100)
        self.assertEqual(selected["localReleaseReadinessSuperseded"]["status"], "close_but_blocked")

    def test_system_audit_uses_live_nas_when_local_quality_metrics_are_partial(self) -> None:
        local = {
            "status": "ready_for_1_0_validation",
            "score": 89,
            "qualityScore": 44,
            "calculatedAt": "2026-06-11T14:39:09+00:00",
            "requiredGateSummary": {"passed": 8, "total": 8, "score": 100},
            "qualitySignals": {
                "completionRate": 5,
                "delegatedRunRate": 5,
                "resumeCompletionRate": 8,
            },
            "proofReadiness": {
                "missionCount": 22,
                "runtimeCompletionCounts": {"hermes": 1},
            },
            "gates": [
                {
                    "gateId": "mission_watchdog_clear",
                    "required": True,
                    "passed": True,
                    "activeMissionCount": 7,
                    "supervisorActive": True,
                    "supervisorStale": False,
                    "supervisorProcessAlive": True,
                    "lastRunAt": "2026-06-11T14:29:13+00:00",
                    "nextRunAt": "2026-06-11T14:49:13+00:00",
                },
            ],
        }
        synced = {
            "status": "ready_for_1_0_validation",
            "score": 100,
            "qualityScore": 100,
            "calculatedAt": "2026-06-11T14:06:27+00:00",
            "requiredGateSummary": {"passed": 8, "total": 8, "score": 100},
            "qualitySignals": {
                "completionRate": 95,
                "delegatedRunRate": 60,
                "resumeCompletionRate": 95,
            },
            "proofReadiness": {
                "missionCount": 30,
                "runtimeCompletionCounts": {"hermes": 27},
            },
            "gates": [
                {
                    "gateId": "mission_watchdog_clear",
                    "required": True,
                    "passed": True,
                    "activeMissionCount": 1,
                    "supervisorActive": True,
                    "supervisorStale": False,
                    "supervisorProcessAlive": True,
                    "lastRunAt": "2026-06-11T13:50:56+00:00",
                    "nextRunAt": "2026-06-11T14:10:56+00:00",
                },
            ],
        }

        selected = _select_system_audit_release_readiness(
            local_release=local,
            synced_release=synced,
            live_nas_system_audit={
                "status": "passed",
                "sourcePath": ".agent_control/live_nas_system_audit_latest.json",
                "checkedAt": "2026-06-11T14:06:31+00:00",
            },
        )

        self.assertEqual(selected["source"], "live_nas_system_audit")
        self.assertTrue(selected["localQualityMetricsSuperseded"])
        self.assertEqual(selected["qualityScore"], 100)
        self.assertEqual(selected["localReleaseReadinessSuperseded"]["qualityScore"], 44)

    def test_live_nas_freshener_replaces_equal_count_stale_summary_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep live NAS evidence current",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "running"
            store.update_mission(mission)

            refreshed = _freshen_live_nas_evidence(
                root,
                {
                    "sourcePath": "/volume1/old-live-summary.json",
                    "checkedAt": "2026-05-29T14:15:50+00:00",
                    "sourceGeneratedAt": "2026-05-29T14:15:50+00:00",
                    "status": "passed",
                    "counts": {"missions": 1},
                    "runningMissions": [{"mission_id": "old"}],
                },
            )

            self.assertEqual(refreshed["sourcePath"], "ControlRoomStore.build_summary_snapshot()")
            self.assertGreater(
                _parse_iso_timestamp(refreshed["checkedAt"]),
                _parse_iso_timestamp("2026-05-29T14:15:50+00:00"),
            )
            self.assertEqual(refreshed["runningMissions"][0]["mission_id"], mission.mission_id)
            self.assertIn("control-room-summary-in-process-current", refreshed["passedChecks"])

    def test_system_audit_prefers_newer_local_red_team_history_over_synced_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            control = root / ".agent_control"
            control.mkdir(parents=True)
            rows = [
                {
                    "schema": "fluxio.red_team_escalation_history.v1",
                    "recordedAt": "2026-05-29T10:00:00+00:00",
                    "preset": "hackaprompt",
                    "status": "pass",
                    "resistance_score": 100,
                    "attempt_count": 23,
                    "blocked_attempt_count": 23,
                    "difficultyLevel": 5,
                    "nextDifficultyLevel": 5,
                    "nextAttemptBudget": 25,
                    "passStreak": 7,
                    "cleanPass": True,
                    "shouldEscalate": True,
                    "targetResistanceScore": 98,
                },
                {
                    "schema": "fluxio.red_team_escalation_history.v1",
                    "recordedAt": "2026-05-29T15:26:00+00:00",
                    "preset": "hackaprompt",
                    "status": "pass",
                    "resistance_score": 100,
                    "attempt_count": 25,
                    "blocked_attempt_count": 25,
                    "difficultyLevel": 5,
                    "nextDifficultyLevel": 5,
                    "nextAttemptBudget": 27,
                    "passStreak": 8,
                    "cleanPass": True,
                    "shouldEscalate": True,
                    "targetResistanceScore": 98,
                },
            ]
            (control / "red_team_escalation_history.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows),
                encoding="utf-8",
            )

            evidence = _red_team_escalation_evidence(
                root,
                snapshot={},
                live_nas_system_audit={
                    "status": "passed",
                    "checkedAt": "2026-05-29T14:40:00+00:00",
                    "sourcePath": "nas/latest.json",
                    "redTeamEscalationEvidence": {
                        "schema": "fluxio.red_team_escalation_snapshot.v1",
                        "history": [rows[0]],
                        "summary": {
                            "runCount": 1,
                            "latestResistanceScore": 100,
                            "nextAttemptBudget": 25,
                            "passStreak": 7,
                        },
                    },
                },
            )

            self.assertEqual(evidence["source"], "local_agent_control")
            self.assertEqual(evidence["summary"]["runCount"], 2)
            self.assertEqual(evidence["summary"]["nextAttemptBudget"], 27)
            self.assertEqual(evidence["summary"]["passStreak"], 8)
            self.assertEqual(evidence["supersededSyncedSourcePath"], "nas/latest.json")
            self.assertEqual(
                evidence["nextBenchmarkPlan"]["schema"],
                "fluxio.red_team_next_benchmark_plan.v1",
            )
            self.assertEqual(evidence["nextBenchmarkPlan"]["attemptBudget"], 27)
            self.assertEqual(evidence["nextBenchmarkPlan"]["targetResistanceScore"], 98)
            self.assertIn(
                "sample:self-improvement-red-team",
                evidence["nextBenchmarkPlan"]["command"]["shell"],
            )

    def test_mission_quickstart_infers_workspace_runtime_and_async_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            route_overrides = [
                {"role": "planner", "provider": "openai", "model": "gpt-5.5"}
            ]
            save_code, save_payload = self._run_json_command(
                cmd_workspace_save,
                root=str(root),
                name="Fluxio Workspace",
                path=str(root),
                default_runtime="hermes",
                user_profile="beginner",
                preferred_harness="fluxio_hybrid",
                routing_strategy="profile_default",
                route_overrides_json=json.dumps(route_overrides),
                auto_optimize_routing="false",
                minimax_auth_mode="none",
                commit_message_style="scoped",
                execution_target_preference="profile_default",
                workspace_id=None,
            )
            self.assertEqual(save_code, 0)
            workspace_id = save_payload["workspace"]["workspace_id"]

            runtime_status = RuntimeInstallStatus(
                runtime_id="hermes",
                label="Hermes",
                detected=True,
                doctor_summary="Hermes is ready.",
            )
            adapter = mock.Mock()
            adapter.doctor.return_value = runtime_status

            with (
                mock.patch("grant_agent.cli.runtime_adapter_map", return_value={"hermes": adapter}),
                mock.patch(
                    "grant_agent.cli.detect_default_verification_commands",
                    return_value=["python -m pytest tests -q"],
                ),
                mock.patch("grant_agent.cli.load_telegram_destination", return_value=""),
                mock.patch(
                    "grant_agent.cli._launch_async_mission_resume",
                    return_value={"pid": 1234, "logPath": str(root / "resume.log")},
                ) as mocked_launch,
            ):
                exit_code, payload = self._run_json_command(
                    cmd_mission_quickstart,
                    root=str(root),
                    objective="Make mission launch easier.",
                    workspace_id="",
                    runtime="auto",
                    success_check=[],
                    mode="Autopilot",
                    budget_hours=4,
                    foreground=False,
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["mission"]["workspace_id"], workspace_id)
            self.assertEqual(payload["mission"]["runtime_id"], "hermes")
            self.assertEqual(payload["launchRecommendation"]["runtime"], "hermes")
            self.assertEqual(
                payload["mission"]["tutorial_context"]["launchRecommendation"]["schema"],
                "fluxio.launch_runtime_recommendation.v1",
            )
            self.assertEqual(payload["mission"]["selected_profile"], "beginner")
            self.assertEqual(payload["mission"]["route_configs"], route_overrides)
            self.assertTrue(payload["launchedAsync"])
            self.assertTrue(mocked_launch.called)
            self.assertEqual(
                payload["mission"]["success_checks"],
                [
                    "Mission produces reviewable proof with no failed checks or pending approvals."
                ],
            )

    def test_mission_quickstart_prefers_local_workspace_when_nas_storage_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            local_root = root / "local-project"
            nas_mirror_root = root / "nas-mirror"
            local_root.mkdir()
            nas_mirror_root.mkdir()
            store = ControlRoomStore(root)
            store.upsert_workspace(
                name="NAS mirror",
                root_path=str(nas_mirror_root),
                default_runtime="hermes",
                user_profile="builder",
                nas_project_path="/volume1/Saclay/projects/demo",
                workspace_id="workspace_nas",
            )
            store.upsert_workspace(
                name="Local fallback",
                root_path=str(local_root),
                default_runtime="hermes",
                user_profile="builder",
                workspace_id="workspace_local",
            )
            control = root / ".agent_control"
            control.mkdir(exist_ok=True)
            (control / "nas_storage_pressure_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.nas_storage_pressure.v1",
                        "checkedAt": datetime.now(timezone.utc).isoformat(),
                        "maxAgeSeconds": 21600,
                        "mount": "/volume1/Saclay",
                        "status": "critical",
                        "probeTimedOut": True,
                        "availableBytes": 0,
                        "usedPercent": 100,
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch("grant_agent.cli.cmd_mission_start", return_value=0) as start:
                exit_code = cmd_mission_quickstart(
                    argparse.Namespace(
                        root=str(root),
                        objective="Build a local fallback proof mission.",
                        workspace_id="",
                        runtime="auto",
                        success_check=[],
                        mode="Autopilot",
                        budget_hours=4,
                        foreground=False,
                    )
                )

            self.assertEqual(exit_code, 0)
            self.assertNotEqual(start.call_args.args[0].workspace_id, "workspace_nas")
            self.assertIn(start.call_args.args[0].workspace_id, {"workspace_primary", "workspace_local"})

            with mock.patch("grant_agent.cli.cmd_mission_start", return_value=0) as start:
                exit_code = cmd_mission_quickstart(
                    argparse.Namespace(
                        root=str(root),
                        objective="Explicitly use the NAS workspace.",
                        workspace_id="workspace_nas",
                        runtime="auto",
                        success_check=[],
                        mode="Autopilot",
                        budget_hours=4,
                        foreground=False,
                    )
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(start.call_args.args[0].workspace_id, "workspace_nas")

    def test_cross_device_launch_rehearsal_command_records_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            project_root = root / "project"
            project_root.mkdir()
            store = ControlRoomStore(root)
            workspace = store.upsert_workspace(
                name="Receipt CLI",
                root_path=str(project_root),
                default_runtime="hermes",
                workspace_id="workspace_receipt_cli",
            )
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Archive launch rehearsal receipt.",
                success_checks=["receipt"],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=1800,
            )

            exit_code, payload = self._run_json_command(
                cmd_cross_device_launch_rehearsal,
                root=str(root),
                workspace_id=workspace.workspace_id,
                mission_id=mission.mission_id,
                allow_review=False,
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(
                payload["receipt"]["schema"],
                "fluxio.cross_device_launch_rehearsal_receipt.v1",
            )
            self.assertEqual(payload["receipt"]["missionId"], mission.mission_id)
            self.assertIn(payload["receipt"]["status"], {"launched", "launched_with_review_items"})

    def test_launch_recommendation_keeps_provider_setup_on_hermes(self) -> None:
        recommendation = build_launch_runtime_recommendation(
            objective="Use browser automation for broker authentication and provider setup.",
            workspace_default_runtime="hermes",
            profile="beginner",
        )

        self.assertEqual(recommendation["runtime"], "hermes")
        self.assertIn("provider setup", recommendation["reason"])
        self.assertEqual(recommendation["modelProvider"], "openai-codex")
        self.assertEqual(recommendation["model"], "gpt-5.5")
        self.assertEqual(recommendation["modelEffort"], "high")
        self.assertEqual(
            [(row["role"], row["provider"], row["model"], row["effort"]) for row in recommendation["routeDecisionRows"]],
            [
                ("planner", "openai-codex", "gpt-5.5", "high"),
                ("executor", "openai-codex", "gpt-5.5", "high"),
                ("verifier", "openai-codex", "gpt-5.5", "high"),
                ("supervisor", "hermes", "durable harness", "resume"),
            ],
        )

    def test_launch_recommendation_only_uses_openclaw_when_explicit(self) -> None:
        recommendation = build_launch_runtime_recommendation(
            objective="Run an OpenClaw parity proof for the harness matrix.",
            workspace_default_runtime="hermes",
            profile="builder",
        )

        self.assertEqual(recommendation["runtime"], "openclaw")
        self.assertIn("explicitly requested", recommendation["reason"])

    def test_launch_recommendation_ignores_negated_openclaw_mentions(self) -> None:
        recommendation = build_launch_runtime_recommendation(
            objective=(
                "Fix the React frontend with Hermes and MiniMax M3. "
                "Do not relaunch through OpenCLAW."
            ),
            workspace_default_runtime="hermes",
            profile="builder",
        )

        self.assertEqual(recommendation["runtime"], "hermes")
        self.assertEqual(recommendation["taskType"], "frontend_design")
        self.assertEqual(recommendation["modelProvider"], "minimax")
        self.assertEqual(recommendation["model"], "MiniMax-M3")
        self.assertNotIn("OpenClaw was explicitly requested", recommendation["reason"])

    def test_launch_recommendation_routes_frontend_execution_to_minimax_under_hermes(self) -> None:
        recommendation = build_launch_runtime_recommendation(
            objective="Make the React frontend and mobile UI feel polished.",
            workspace_default_runtime="hermes",
            profile="builder",
        )

        self.assertEqual(recommendation["runtime"], "hermes")
        self.assertEqual(recommendation["taskType"], "frontend_design")
        self.assertEqual(recommendation["modelProvider"], "minimax")
        self.assertEqual(recommendation["model"], "MiniMax-M3")
        executor = next(row for row in recommendation["routeDecisionRows"] if row["role"] == "executor")
        self.assertEqual(executor["provider"], "minimax")
        self.assertEqual(executor["model"], "MiniMax-M3")
        self.assertEqual(executor["effort"], "high")
        self.assertIn("Planner and verifier stay on openai-codex / gpt-5.5 / high", recommendation["beginnerSummary"])

    @unittest.skipUnless(shutil.which("git"), "git is required for worktree execution-scope tests")
    def test_invoke_engine_honors_legacy_harness_preference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            _init_git_repo(root)

            with mock.patch(
                "grant_agent.cli.detect_default_verification_commands",
                return_value=["python -m pytest tests -q"],
            ):
                with mock.patch(
                    "grant_agent.cli.AutonomousEngine.run",
                    return_value={
                        "status": "ok",
                        "session_path": str(root / ".agent_runs" / "session_legacy"),
                        "autopilot_status": "completed",
                        "autopilot_pause_reason": "",
                        "verification_failures": [],
                        "remaining_steps": [],
                    },
                ) as mocked_run:
                    result = _invoke_engine(
                        root=root,
                        objective="Compare the legacy harness contract.",
                        docs=["README.md"],
                        mode_name="autopilot",
                        profile_name="hands_free_builder",
                        persona_override=None,
                        iterations=2,
                        verify_commands=[],
                        project_profile="Legacy harness contract test",
                        resume_from=None,
                        resume_checkpoint=None,
                        checkpoint_every=1,
                        pause_on_verification_failure=True,
                        runtime_id="hermes",
                        mission_id="mission_legacy",
                        harness_preference="legacy_autonomous_engine",
                        routing_strategy_override="uniform_quality",
                        execution_target_preference="isolated_worktree",
                    )

            self.assertTrue(mocked_run.called)
            self.assertEqual(mocked_run.call_args.kwargs["verify_commands"], [])
            self.assertEqual(result["effective_verify_commands"], [])
            self.assertEqual(result["harness_id"], "legacy_autonomous_engine")
            self.assertEqual(result["effective_harness"], "legacy_autonomous_engine")
            self.assertEqual(
                result["effective_execution_target_preference"],
                "isolated_worktree",
            )
            planner = next(item for item in result["route_configs"] if item["role"] == "planner")
            executor = next(item for item in result["route_configs"] if item["role"] == "executor")
            self.assertEqual(planner["provider"], "openai-codex")
            self.assertEqual(planner["model"], "gpt-5.5")
            self.assertEqual(executor["model"], "gpt-5.5")
            self.assertNotEqual(result["execution_scope"]["execution_root"], str(root))
            self.assertEqual(result["execution_scope"]["execution_target"], "worktree")
            self.assertEqual(
                result["execution_policy"]["profile_name"],
                "hands_free_builder",
            )

    def test_invoke_engine_preserves_hands_free_profile_alias_for_harness(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")

            with mock.patch(
                "grant_agent.cli.detect_default_verification_commands",
                return_value=[],
            ):
                with mock.patch("grant_agent.cli.FluxioHarness.run") as mocked_run:
                    mocked_run.return_value = {
                        "status": "ok",
                        "session_path": str(root / ".agent_runs" / "session_experimental"),
                        "autopilot_status": "completed",
                        "autopilot_pause_reason": "",
                        "verification_failures": [],
                        "remaining_steps": [],
                        "route_configs": [],
                        "execution_scope": {},
                        "execution_policy": {"profile_name": "experimental"},
                    }
                    result = _invoke_engine(
                        root=root,
                        objective="Use the experimental profile defaults.",
                        docs=["README.md"],
                        mode_name="autopilot",
                        profile_name="experimental",
                        persona_override=None,
                        iterations=1,
                        verify_commands=[],
                        project_profile="Profile fallback test",
                        resume_from=None,
                        resume_checkpoint=None,
                        checkpoint_every=1,
                        pause_on_verification_failure=True,
                        runtime_id="hermes",
                        mission_id="mission_experimental",
                        harness_preference="fluxio_hybrid",
                        routing_strategy_override="profile_default",
                    )

            self.assertEqual(mocked_run.call_args.kwargs["profile_name"], "hands_free_builder")
            self.assertEqual(result["profile"], "hands_free_builder")

    def test_hands_free_profile_alias_uses_experimental_approval_defaults(self) -> None:
        from grant_agent.action_executor import build_execution_policy
        from grant_agent.fluxio_harness import guided_profile_defaults

        policy = build_execution_policy("hands_free_builder")
        defaults = guided_profile_defaults("hands_free_builder")

        self.assertEqual(policy.approval_mode, "hands_free")
        self.assertEqual(defaults["approval_mode"], "hands_free")

    def test_mission_start_promotes_deadline_objective_to_long_run_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")

            save_code, save_payload = self._run_json_command(
                cmd_workspace_save,
                root=str(root),
                name="Fluxio Workspace",
                path=str(root),
                default_runtime="hermes",
                user_profile="experimental",
                preferred_harness="fluxio_hybrid",
                routing_strategy="profile_default",
                route_overrides_json="[]",
                auto_optimize_routing="false",
                minimax_auth_mode="none",
                commit_message_style="scoped",
                execution_target_preference="profile_default",
                workspace_id=None,
            )
            self.assertEqual(save_code, 0)
            workspace_id = save_payload["workspace"]["workspace_id"]

            runtime_status = RuntimeInstallStatus(
                runtime_id="hermes",
                label="Hermes",
                detected=True,
                doctor_summary="Hermes is ready.",
            )
            adapter = mock.Mock()
            adapter.doctor.return_value = runtime_status
            fixed_now = datetime(2026, 4, 16, 22, 0, tzinfo=timezone.utc)

            with (
                mock.patch("grant_agent.cli.runtime_adapter_map", return_value={"hermes": adapter}),
                mock.patch(
                    "grant_agent.cli.detect_default_verification_commands",
                    return_value=["python -m pytest tests -q"],
                ),
                mock.patch("grant_agent.cli.load_telegram_destination", return_value=""),
                mock.patch("grant_agent.cli._now_local", return_value=fixed_now),
                mock.patch(
                    "grant_agent.cli.mission_time_budget_window",
                    return_value={"remainingSeconds": 36000},
                ),
                mock.patch(
                    "grant_agent.cli._invoke_engine",
                    return_value=self._engine_result(root, "session_deadline"),
                ) as mocked_invoke,
            ):
                exit_code, payload = self._run_json_command(
                    cmd_mission_start,
                    root=str(root),
                    workspace_id=workspace_id,
                    runtime="hermes",
                    objective="Work on the app until 8 a.m.",
                    success_check=["Mission keeps running until the deadline"],
                    mode="Autopilot",
                    budget_hours=4,
                    run_until="pause_on_failure",
                    profile="experimental",
                    escalation_destination="",
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                payload["mission"]["run_budget"]["run_until_behavior"],
                "continue_until_blocked",
            )
            self.assertEqual(
                payload["mission"]["run_budget"]["max_runtime_seconds"],
                36000,
            )
            self.assertTrue(payload["mission"]["run_budget"]["deadline_at"])
            self.assertEqual(
                mocked_invoke.call_args.kwargs["max_runtime_override"],
                36000,
            )
            self.assertFalse(mocked_invoke.call_args.kwargs["pause_on_handoff"])

    def test_mission_action_extend_budget_unblocks_runtime_budget_pause(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Continue a useful overnight mission",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=60,
            )
            mission.state.status = "blocked"
            mission.state.stop_reason = "runtime_budget"
            mission.state.last_error = "runtime_budget"
            mission.state.time_budget_status = "paused"
            mission.state.remaining_runtime_seconds = 0
            mission.run_budget.deadline_at = "2026-01-01T00:00:00+00:00"
            mission.proof.summary = "Mission reached its runtime budget."
            mission.proof.blocked_by = ["runtime_budget"]
            store.update_mission(mission)

            exit_code, payload = self._run_json_command(
                cmd_mission_action,
                root=str(root),
                mission_id=mission.mission_id,
                action="extend-budget",
                launch_async=False,
                budget_hours=2,
                operator_value_score=-1,
                operator_outcome="",
                operator_closeout_note="",
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["addedSeconds"], 7200)
            self.assertEqual(payload["mission"]["state"]["status"], "queued")
            self.assertGreaterEqual(payload["mission"]["state"]["remaining_runtime_seconds"], 7200)
            self.assertIsNotNone(payload["mission"]["run_budget"]["deadline_at"])
            self.assertIsNone(payload["mission"]["state"]["stop_reason"])
            self.assertEqual(payload["mission"]["state"]["time_budget_status"], "queued")
            self.assertEqual(payload["mission"]["proof"]["blocked_by"], [])
            self.assertTrue(payload["watchdogRefresh"]["ok"])
            watchdog_path = root / ".agent_control" / "mission_watchdog.json"
            problem_path = root / ".agent_control" / "mission_watchdog_problems.json"
            self.assertTrue(watchdog_path.exists())
            self.assertTrue(problem_path.exists())
            watchdog = json.loads(watchdog_path.read_text(encoding="utf-8"))
            problems = json.loads(problem_path.read_text(encoding="utf-8"))
            stale_issue_id = f"{mission.mission_id}:runtime_budget_exhausted"
            self.assertNotIn(
                stale_issue_id,
                [item.get("issueId") for item in watchdog.get("issues", [])],
            )
            self.assertNotIn(
                stale_issue_id,
                [item.get("sourceIssueId") for item in problems.get("openProblems", [])],
            )

    def test_mission_action_extend_budget_starts_fresh_after_failed_delegated_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Continue a Hermes delegated mission after a runtime failure",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=60,
            )
            mission.state.status = "blocked"
            mission.state.latest_session_id = "session_failed"
            mission.state.stop_reason = "delegated_runtime_failed"
            mission.state.last_error = "delegated_runtime_failed"
            mission.proof.blocked_by = ["delegated_runtime_failed"]
            mission.delegated_runtime_sessions = [
                DelegatedRuntimeSession(
                    delegated_id="delegate_failed",
                    runtime_id="hermes",
                    launch_command="hermes chat",
                    status="failed",
                )
            ]
            store.update_mission(mission)

            exit_code, payload = self._run_json_command(
                cmd_mission_action,
                root=str(root),
                mission_id=mission.mission_id,
                action="extend-budget",
                launch_async=False,
                budget_hours=1,
                operator_value_score=-1,
                operator_outcome="",
                operator_closeout_note="",
            )

            self.assertEqual(exit_code, 0)
            self.assertIsNone(payload["mission"]["state"]["latest_session_id"])
            self.assertEqual(payload["mission"]["state"]["status"], "queued")
            self.assertEqual(payload["mission"]["proof"]["blocked_by"], [])

    def test_mission_action_extend_budget_starts_fresh_after_missing_artifact_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build an F1 telemetry artifact",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=60,
            )
            mission.state.status = "verification_failed"
            mission.state.latest_session_id = "session_read_only"
            mission.state.stop_reason = "artifact_gate_failed"
            mission.state.last_error = "Hard artifact gate failed"
            store.update_mission(mission)

            exit_code, payload = self._run_json_command(
                cmd_mission_action,
                root=str(root),
                mission_id=mission.mission_id,
                action="extend-budget",
                launch_async=False,
                budget_hours=1,
                operator_value_score=-1,
                operator_outcome="",
                operator_closeout_note="",
            )

            self.assertEqual(exit_code, 0)
            self.assertIsNone(payload["mission"]["state"]["latest_session_id"])
            self.assertEqual(payload["mission"]["state"]["status"], "queued")

    def test_mission_start_accepts_relative_stop_minutes_timer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")

            save_code, save_payload = self._run_json_command(
                cmd_workspace_save,
                root=str(root),
                name="Fluxio Workspace",
                path=str(root),
                default_runtime="hermes",
                user_profile="experimental",
                preferred_harness="fluxio_hybrid",
                routing_strategy="profile_default",
                route_overrides_json="[]",
                auto_optimize_routing="false",
                minimax_auth_mode="none",
                commit_message_style="scoped",
                execution_target_preference="profile_default",
                workspace_id=None,
            )
            self.assertEqual(save_code, 0)
            workspace_id = save_payload["workspace"]["workspace_id"]

            runtime_status = RuntimeInstallStatus(
                runtime_id="hermes",
                label="Hermes",
                detected=True,
                doctor_summary="Hermes is ready.",
            )
            adapter = mock.Mock()
            adapter.doctor.return_value = runtime_status
            fixed_now = datetime(2026, 4, 16, 22, 0, tzinfo=timezone.utc)

            with (
                mock.patch("grant_agent.cli.runtime_adapter_map", return_value={"hermes": adapter}),
                mock.patch(
                    "grant_agent.cli.detect_default_verification_commands",
                    return_value=["python -m pytest tests -q"],
                ),
                mock.patch("grant_agent.cli.load_telegram_destination", return_value=""),
                mock.patch("grant_agent.cli._now_local", return_value=fixed_now),
                mock.patch(
                    "grant_agent.cli.mission_time_budget_window",
                    return_value={"remainingSeconds": 2100},
                ),
                mock.patch(
                    "grant_agent.cli._invoke_engine",
                    return_value=self._engine_result(root, "session_relative_timer"),
                ) as mocked_invoke,
            ):
                exit_code, payload = self._run_json_command(
                    cmd_mission_start,
                    root=str(root),
                    workspace_id=workspace_id,
                    runtime="hermes",
                    objective="Refine the launch copy and keep scope tight.",
                    success_check=["Mission pauses after the relative timer window"],
                    mode="Autopilot",
                    budget_hours=4,
                    relative_stop_minutes=35,
                    run_until="pause_on_failure",
                    profile="experimental",
                    escalation_destination="",
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                payload["mission"]["run_budget"]["run_until_behavior"],
                "continue_until_blocked",
            )
            self.assertEqual(
                payload["mission"]["run_budget"]["max_runtime_seconds"],
                2100,
            )
            self.assertTrue(payload["mission"]["run_budget"]["deadline_at"])
            self.assertEqual(
                mocked_invoke.call_args.kwargs["max_runtime_override"],
                2100,
            )
            self.assertFalse(mocked_invoke.call_args.kwargs["pause_on_handoff"])

    def test_mission_start_accepts_per_run_model_route_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")

            save_code, save_payload = self._run_json_command(
                cmd_workspace_save,
                root=str(root),
                name="Fluxio Workspace",
                path=str(root),
                default_runtime="hermes",
                user_profile="advanced",
                preferred_harness="fluxio_hybrid",
                routing_strategy="profile_default",
                route_overrides_json="[]",
                auto_optimize_routing="false",
                minimax_auth_mode="none",
                commit_message_style="scoped",
                execution_target_preference="profile_default",
                workspace_id=None,
            )
            self.assertEqual(save_code, 0)
            workspace_id = save_payload["workspace"]["workspace_id"]

            runtime_status = RuntimeInstallStatus(
                runtime_id="hermes",
                label="Hermes",
                detected=True,
                doctor_summary="Hermes is ready.",
            )
            adapter = mock.Mock()
            adapter.doctor.return_value = runtime_status
            route_overrides = [
                {
                    "role": role,
                    "provider": "openai",
                    "model": "gpt-5.5",
                    "effort": "high",
                }
                for role in ("planner", "executor", "verifier")
            ]

            with (
                mock.patch("grant_agent.cli.runtime_adapter_map", return_value={"hermes": adapter}),
                mock.patch(
                    "grant_agent.cli.detect_default_verification_commands",
                    return_value=["python -m pytest tests -q"],
                ),
                mock.patch("grant_agent.cli.load_telegram_destination", return_value=""),
                mock.patch(
                    "grant_agent.cli.mission_time_budget_window",
                    return_value={"remainingSeconds": 7200},
                ),
                mock.patch(
                    "grant_agent.cli._invoke_engine",
                    return_value=self._engine_result(root, "session_route_override"),
                ) as mocked_invoke,
            ):
                exit_code, payload = self._run_json_command(
                    cmd_mission_start,
                    root=str(root),
                    workspace_id=workspace_id,
                    runtime="hermes",
                    objective="Use the selected run model for this mission.",
                    success_check=["The mission uses the selected model route"],
                    mode="Autopilot",
                    budget_hours=2,
                    run_until="pause_on_failure",
                    profile="advanced",
                    route_overrides_json=json.dumps(route_overrides),
                    escalation_destination="",
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["mission"]["route_configs"], route_overrides)
            self.assertEqual(
                mocked_invoke.call_args.kwargs["route_overrides_override"],
                route_overrides,
            )

    def test_mission_route_records_mutation_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Reroute executor with proof",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=7200,
                route_overrides=[
                    {
                        "role": "executor",
                        "provider": "openai-codex",
                        "model": "gpt-5.5",
                        "effort": "high",
                    }
                ],
            )

            exit_code, payload = self._run_json_command(
                cmd_mission_route,
                root=str(root),
                mission_id=mission.mission_id,
                role="executor",
                provider="minimax",
                model="MiniMax-M2.7",
                effort="medium",
                budget_class="balanced",
                reason="Frontend execution should use MiniMax.",
            )

            self.assertEqual(exit_code, 0)
            receipt = payload["routeMutationReceipt"]
            self.assertEqual(receipt["schema"], "fluxio.route_mutation_receipt.v1")
            self.assertEqual(receipt["role"], "executor")
            self.assertEqual(receipt["next"]["provider"], "minimax")
            updated = payload["mission"]
            self.assertEqual(
                updated["effective_route_contract"]["mutationReceipts"][0]["receiptId"],
                receipt["receiptId"],
            )
            self.assertIn("Route mutation receipt", updated["proof"]["summary"])

    def test_mission_lane_control_records_durable_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Record lane proof control",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=7200,
                route_overrides=[
                    {
                        "role": "executor",
                        "provider": "openai-codex",
                        "model": "gpt-5.5",
                        "effort": "high",
                    }
                ],
            )

            exit_code, payload = self._run_json_command(
                cmd_mission_lane_control,
                root=str(root),
                mission_id=mission.mission_id,
                role="executor",
                action="open-proof",
                reason="Operator opened lane proof from Agent.",
            )

            self.assertEqual(exit_code, 0)
            receipt = payload["laneControlReceipt"]
            self.assertEqual(receipt["schema"], "fluxio.lane_control_receipt.v1")
            self.assertEqual(receipt["role"], "executor")
            self.assertEqual(receipt["action"], "open-proof")
            self.assertTrue(receipt["validation"]["rolePresentInRuntimeLanes"])
            self.assertTrue(receipt["validation"]["stateMutationRecorded"])
            self.assertEqual(receipt["stateMutationProof"]["field"], "mission.state.current_runtime_lane")
            self.assertEqual(receipt["stateMutationProof"]["before"], "")
            self.assertEqual(receipt["stateMutationProof"]["after"], "executor")
            self.assertTrue(receipt["stateMutationProof"]["observedAfterWrite"])
            self.assertTrue(receipt["stateMutationProof"]["receiptWillAttachToLane"])
            updated = payload["mission"]
            self.assertNotIn("snapshot", payload)
            self.assertEqual(
                updated["state"]["lane_control_receipts"][-1]["receiptId"],
                receipt["receiptId"],
            )
            self.assertEqual(receipt["nextRuntimeLane"], "executor")
            self.assertIn("Lane control receipt", updated["proof"]["summary"])
            refreshed_store = ControlRoomStore(root)
            ledger_receipts = refreshed_store.lane_control_receipts_for_mission(mission.mission_id)
            self.assertEqual(ledger_receipts[-1]["receiptId"], receipt["receiptId"])
            detail = refreshed_store.build_mission_detail_snapshot(mission.mission_id)
            executor_lane = next(
                item for item in detail["summary"]["runtimeLanes"] if item["role"] == "executor"
            )
            self.assertEqual(
                executor_lane["laneControlReceipt"]["receiptId"],
                receipt["receiptId"],
            )
            event = refreshed_store.recent_events(limit=1)[0]
            self.assertEqual(event["kind"], "mission.lane_control")
            self.assertEqual(event["metadata"]["receiptId"], receipt["receiptId"])

    def test_fail_verification_rolls_back_latest_route_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Rollback failed route mutation",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=7200,
                route_overrides=[
                    {
                        "role": "executor",
                        "provider": "openai-codex",
                        "model": "gpt-5.5",
                        "effort": "high",
                    }
                ],
            )

            route_code, route_payload = self._run_json_command(
                cmd_mission_route,
                root=str(root),
                mission_id=mission.mission_id,
                role="executor",
                provider="minimax",
                model="MiniMax-M2.7",
                effort="medium",
                budget_class="balanced",
                reason="Try MiniMax for frontend execution.",
            )
            self.assertEqual(route_code, 0)
            mutation_receipt = route_payload["routeMutationReceipt"]

            fail_code, fail_payload = self._run_json_command(
                cmd_mission_action,
                root=str(root),
                mission_id=mission.mission_id,
                action="fail-verification",
                launch_async=False,
            )

            self.assertEqual(fail_code, 0)
            rollback = fail_payload["routeRollbackReceipt"]
            self.assertEqual(rollback["schema"], "fluxio.route_rollback_receipt.v1")
            self.assertEqual(rollback["rolledBackReceiptId"], mutation_receipt["receiptId"])
            self.assertEqual(rollback["previous"]["provider"], "minimax")
            self.assertEqual(rollback["next"]["provider"], "openai-codex")
            self.assertTrue(rollback["validation"]["currentMatchedFailedRoute"])

            updated = fail_payload["mission"]
            executor = next(item for item in updated["route_configs"] if item["role"] == "executor")
            self.assertEqual(executor["provider"], "openai-codex")
            receipts = updated["effective_route_contract"]["mutationReceipts"]
            self.assertEqual(receipts[-1]["receiptId"], rollback["receiptId"])
            self.assertEqual(receipts[-1]["schema"], "fluxio.route_rollback_receipt.v1")
            self.assertEqual(receipts[-2]["rolledBackByReceiptId"], rollback["receiptId"])
            self.assertIn("Route rollback receipt", updated["proof"]["summary"])

    def test_complete_mission_records_operator_value_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Close the mission with operator value feedback",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )

            exit_code, payload = self._run_json_command(
                cmd_mission_action,
                root=str(root),
                mission_id=mission.mission_id,
                action="complete",
                launch_async=False,
                operator_value_score=88,
                operator_outcome="useful",
                operator_closeout_note="Output was directly usable.",
            )

            self.assertEqual(exit_code, 0)
            feedback = payload["mission"]["state"]["operator_value_feedback"]
            self.assertEqual(feedback["schema"], "fluxio.mission_operator_value_feedback.v1")
            self.assertEqual(feedback["score"], 88)
            self.assertEqual(feedback["outcome"], "useful")
            self.assertEqual(feedback["trustSignal"], "promote")
            self.assertIn("88 value score", payload["mission"]["proof"]["summary"])
            event_text = (root / ".agent_control" / "mission_events.jsonl").read_text(encoding="utf-8")
            self.assertIn("operatorValueFeedback", event_text)

    def test_approve_latest_uses_workspace_session_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir) / "control"
            workspace_root = pathlib.Path(temp_dir) / "workspace"
            root.mkdir()
            workspace_root.mkdir()
            bootstrap_project(root)
            bootstrap_project(workspace_root)
            store = ControlRoomStore(root)
            workspace = store.upsert_workspace(
                workspace_id="external_workspace",
                name="External Workspace",
                root_path=str(workspace_root),
                default_runtime="hermes",
            )
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Approve workspace-root session",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=7200,
                run_until_behavior="continue_until_blocked",
            )
            session_id = "session_workspace_root"
            session_dir = workspace_root / ".agent_runs" / session_id
            session_dir.mkdir(parents=True)
            action_record = ActionExecutionRecord(
                action_id="action_write",
                proposal=ActionProposal(
                    action_id="action_write",
                    kind="file_write",
                    title="Write workspace artifact",
                    requires_approval=True,
                ),
                gate=ActionApprovalGate(required=True, status="pending"),
            )
            (session_dir / "state.json").write_text(
                json.dumps({"action_history": [action_record.__dict__]}, default=lambda value: value.__dict__),
                encoding="utf-8",
            )
            mission.state.latest_session_id = session_id
            mission.state.status = "needs_approval"
            mission.action_history = [action_record]
            store.update_mission(mission)

            exit_code, payload = self._run_json_command(
                cmd_mission_action,
                root=str(root),
                mission_id=mission.mission_id,
                action="approve-latest",
                launch_async=False,
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["mission"]["state"]["status"], "queued")
            session_state = json.loads((session_dir / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(session_state["action_history"][0]["gate"]["status"], "approved")

    def test_mission_resume_uses_latest_checkpoint_for_continuity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Resume with the latest continuity checkpoint",
                success_checks=[],
                mode="Autopilot",
                verification_commands=["python -m pytest tests -q"],
                max_runtime_seconds=7200,
                run_until_behavior="continue_until_blocked",
            )
            session_path = root / ".agent_runs" / "session_resume"
            checkpoint_path = CheckpointStore(session_path).save(
                session_id="session_resume",
                iteration=3,
                run_state=RunState(
                    objective=mission.objective,
                    plan_steps=["Resume mission"],
                    acceptance_checks=[],
                ),
                context={"used_tokens": 120},
                doc_sources=["README.md"],
            )
            mission.state.latest_session_id = "session_resume"
            mission.state.status = "running"
            store.update_mission(mission)

            with (
                mock.patch(
                    "grant_agent.cli.mission_time_budget_window",
                    return_value={"remainingSeconds": 1800},
                ),
                mock.patch(
                    "grant_agent.cli._invoke_engine",
                    return_value=self._engine_result(root, "session_resume"),
                ) as mocked_invoke,
            ):
                exit_code, _payload = self._run_json_command(
                    cmd_mission_action,
                    root=str(root),
                    mission_id=mission.mission_id,
                    action="resume",
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                mocked_invoke.call_args.kwargs["resume_from"],
                "session_resume",
            )
            self.assertEqual(
                mocked_invoke.call_args.kwargs["resume_checkpoint"],
                str(checkpoint_path),
            )
            self.assertFalse(mocked_invoke.call_args.kwargs["pause_on_handoff"])

    def test_mission_resume_engine_objective_includes_hard_artifact_follow_up(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build a polished phone/tablet Builder progress surface",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=7200,
                run_until_behavior="continue_until_blocked",
            )
            mission.state.latest_session_id = "session_resume"
            mission.state.status = "running"
            mission.proof.summary = "Artifact gate passed but runtime transcript is missing_runtime_output."
            mission.proof.blocked_by = ["runtime transcript missing_runtime_output"]
            mission.delegated_runtime_sessions = [
                DelegatedRuntimeSession(
                    delegated_id="delegate_followup",
                    runtime_id="hermes",
                    launch_command="hermes chat -q old objective",
                    status="completed",
                    latest_events=[
                        {
                            "kind": "operator.followup",
                            "message": (
                                "Hard artifact repair gate: write .agent_control/mission_artifacts "
                                "and attach a Workbench verifier receipt."
                            ),
                        }
                    ],
                )
            ]
            mission.state.delegated_runtime_sessions = [
                item.__dict__ for item in mission.delegated_runtime_sessions
            ]
            store.update_mission(mission)

            with (
                mock.patch(
                    "grant_agent.cli.mission_time_budget_window",
                    return_value={"remainingSeconds": 1800},
                ),
                mock.patch(
                    "grant_agent.cli._invoke_engine",
                    return_value=self._engine_result(root, "session_resume"),
                ) as mocked_invoke,
            ):
                exit_code, _payload = self._run_json_command(
                    cmd_mission_action,
                    root=str(root),
                    mission_id=mission.mission_id,
                    action="resume",
                )

            self.assertEqual(exit_code, 0)
            objective = mocked_invoke.call_args.kwargs["objective"]
            self.assertIn("Hard artifact repair gate", objective)
            self.assertIn(".agent_control/mission_artifacts", objective)
            self.assertIn("Workbench verifier receipt", objective)
            self.assertIn("Do not mark the mission completed", objective)

    def test_mission_action_resume_compact_output_omits_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Resume with compact async receipt",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=7200,
            )
            mission.state.latest_session_id = "session_resume"
            mission.state.status = "running"
            store.update_mission(mission)

            with (
                mock.patch.dict(os.environ, {"FLUXIO_MISSION_ACTION_COMPACT": "1"}),
                mock.patch(
                    "grant_agent.cli._run_mission_engine_cycles",
                    return_value={
                        "mission": {"largePayload": True},
                        "result": {
                            "status": "ok",
                            "autopilot_pause_reason": "delegated_runtime_running",
                            "session_path": str(root / ".agent_runs" / "session_resume"),
                        },
                    },
                ),
            ):
                exit_code, payload = self._run_json_command(
                    cmd_mission_action,
                    root=str(root),
                    mission_id=mission.mission_id,
                    action="resume",
                    launch_async=False,
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["schema"], "fluxio.mission_action_compact_receipt.v1")
            self.assertNotIn("snapshot", payload)
            self.assertNotIn("largePayload", payload["mission"])
            self.assertEqual(payload["mission"]["mission_id"], mission.mission_id)
            self.assertEqual(
                payload["result"]["autopilot_pause_reason"],
                "delegated_runtime_running",
            )

    def test_mission_action_resume_throttles_continuing_cycles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Continue without spinning hot",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=7200,
                run_until_behavior="continue_until_blocked",
            )
            mission.state.latest_session_id = "session_resume"
            mission.state.status = "running"
            store.update_mission(mission)

            with (
                mock.patch(
                    "grant_agent.cli.mission_time_budget_window",
                    return_value={"remainingSeconds": 1800},
                ),
                mock.patch(
                    "grant_agent.cli._invoke_engine",
                    side_effect=[
                        {
                            "status": "ok",
                            "session_path": str(root / ".agent_runs" / "session_resume"),
                            "autopilot_status": "paused",
                            "autopilot_pause_reason": "",
                            "verification_failures": [],
                            "remaining_steps": ["continue"],
                        },
                        self._engine_result(root, "session_resume_done"),
                    ],
                ),
                mock.patch("grant_agent.cli.time.sleep") as sleep,
            ):
                exit_code, _payload = self._run_json_command(
                    cmd_mission_action,
                    root=str(root),
                    mission_id=mission.mission_id,
                    action="resume",
                    launch_async=False,
                )

            self.assertEqual(exit_code, 0)
            sleep.assert_called_once_with(15)

    def test_delegated_runtime_running_is_not_stored_as_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep delegated runtime active",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=7200,
                run_until_behavior="continue_until_blocked",
            )
            mission.state.latest_session_id = "session_delegated"
            mission.state.status = "running"
            store.update_mission(mission)

            with (
                mock.patch(
                    "grant_agent.cli.mission_time_budget_window",
                    return_value={"remainingSeconds": 1800},
                ),
                mock.patch(
                    "grant_agent.cli._invoke_engine",
                    return_value={
                        "status": "ok",
                        "session_path": str(root / ".agent_runs" / "session_delegated"),
                        "autopilot_status": "paused",
                        "autopilot_pause_reason": "delegated_runtime_running",
                        "latest_blocker": {
                            "summary": "Delegated runtime is still running after the follow budget."
                        },
                        "verification_failures": [],
                        "remaining_steps": ["wait"],
                    },
                ),
            ):
                exit_code, payload = self._run_json_command(
                    cmd_mission_action,
                    root=str(root),
                    mission_id=mission.mission_id,
                    action="resume",
                    launch_async=False,
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["mission"]["state"]["status"], "running")
            self.assertEqual(payload["mission"]["state"]["planner_loop_status"], "running")
            self.assertIsNone(payload["mission"]["state"]["last_error"])
            self.assertIsNone(payload["mission"]["state"]["stop_reason"])
            self.assertEqual(payload["mission"]["proof"]["blocked_by"], [])

    def test_mission_resume_acknowledges_superseded_terminal_delegates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Resume after delegated output was superseded",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=7200,
                run_until_behavior="continue_until_blocked",
            )
            mission.state.status = "running"
            completed = DelegatedRuntimeSession(
                delegated_id="delegate_completed",
                runtime_id="hermes",
                launch_command="hermes chat old",
                status="completed",
                acknowledged=False,
                session_path=str(root / ".agent_control" / "runtime_sessions" / "delegate_completed.json"),
            )
            running = DelegatedRuntimeSession(
                delegated_id="delegate_running",
                runtime_id="hermes",
                launch_command="hermes chat new",
                status="running",
                acknowledged=False,
                pid=12345,
            )
            pathlib.Path(completed.session_path).parent.mkdir(parents=True, exist_ok=True)
            pathlib.Path(completed.session_path).write_text(
                json.dumps(completed.__dict__, indent=2),
                encoding="utf-8",
            )
            mission.delegated_runtime_sessions = [completed]
            store.update_mission(mission)

            with (
                mock.patch(
                    "grant_agent.cli.mission_time_budget_window",
                    return_value={"remainingSeconds": 1800},
                ),
                mock.patch(
                    "grant_agent.cli._invoke_engine",
                    return_value={
                        "status": "ok",
                        "session_path": str(root / ".agent_runs" / "session_delegated"),
                        "autopilot_status": "paused",
                        "autopilot_pause_reason": "delegated_runtime_running",
                        "verification_failures": [],
                        "remaining_steps": ["wait"],
                        "delegated_runtime_sessions": [
                            completed.__dict__,
                            running.__dict__,
                        ],
                    },
                ),
            ):
                exit_code, payload = self._run_json_command(
                    cmd_mission_action,
                    root=str(root),
                    mission_id=mission.mission_id,
                    action="resume",
                    launch_async=False,
                )

            self.assertEqual(exit_code, 0)
            sessions = payload["mission"]["delegated_runtime_sessions"]
            self.assertEqual(sessions[0]["status"], "completed")
            self.assertTrue(sessions[0]["acknowledged"])
            self.assertEqual(sessions[1]["status"], "running")
            self.assertFalse(sessions[1]["acknowledged"])
            refreshed = ControlRoomStore(root).get_mission(mission.mission_id)
            self.assertTrue(refreshed.delegated_runtime_sessions[0].acknowledged)
            self.assertFalse(refreshed.delegated_runtime_sessions[1].acknowledged)
            session_payload = json.loads(pathlib.Path(completed.session_path).read_text(encoding="utf-8"))
            self.assertTrue(session_payload["acknowledged"])

    def test_auto_resume_reconciles_failed_delegated_lane_after_stop_reason_clear(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Resume after failed delegated lane",
                success_checks=[],
                mode="Deep Run",
                verification_commands=[],
                max_runtime_seconds=7200,
                run_until_behavior="continue_until_blocked",
            )
            runtime_dir = root / ".agent_control" / "runtime_sessions"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            session_path = runtime_dir / "delegate_failed.json"
            session = DelegatedRuntimeSession(
                delegated_id="delegate_failed",
                runtime_id="hermes",
                launch_command="hermes chat",
                status="failed",
                detail="Delegated runtime process failed.",
                session_path=str(session_path),
                exit_code=1,
                acknowledged=False,
            )
            session_path.write_text(json.dumps(session.__dict__, indent=2), encoding="utf-8")
            mission.state.status = "running"
            mission.state.stop_reason = None
            mission.state.planner_loop_status = "running"
            mission.planner_loop_status = "running"
            mission.proof.summary = "Delegated runtime lane is active. Fluxio will continue when it finishes."
            mission.delegated_runtime_sessions = [session]
            mission.state.delegated_runtime_sessions = [session.__dict__]
            store.update_mission(mission)

            with mock.patch(
                "grant_agent.cli._launch_async_mission_resume",
                return_value={"pid": 1234, "logPath": str(root / "resume.log"), "command": ["python"]},
            ) as launch:
                dispatched = _auto_resume_ready_delegated_missions(root, store)

            self.assertEqual([item["missionId"] for item in dispatched], [mission.mission_id])
            launch.assert_called_once_with(root, mission.mission_id)
            refreshed = store.get_mission(mission.mission_id)
            self.assertIsNotNone(refreshed)
            self.assertEqual(refreshed.state.status, "running")
            self.assertEqual(refreshed.state.planner_loop_status, "launching")
            self.assertEqual(refreshed.planner_loop_status, "launching")
            self.assertTrue(refreshed.delegated_runtime_sessions[0].acknowledged)
            session_payload = json.loads(session_path.read_text(encoding="utf-8"))
            self.assertTrue(session_payload["acknowledged"])
            self.assertIn("automatic reconciliation", refreshed.proof.summary)

    def test_auto_resume_reconciles_launching_mission_when_async_worker_is_gone(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Resume launching mission with no active worker",
                success_checks=[],
                mode="Deep Run",
                verification_commands=[],
                max_runtime_seconds=7200,
                run_until_behavior="continue_until_blocked",
            )
            runtime_dir = root / ".agent_control" / "runtime_sessions"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            session_path = runtime_dir / "delegate_completed_launching.json"
            session = DelegatedRuntimeSession(
                delegated_id="delegate_completed_launching",
                runtime_id="hermes",
                launch_command="hermes chat",
                status="completed",
                detail="Delegated runtime process completed.",
                session_path=str(session_path),
                exit_code=0,
                acknowledged=False,
            )
            session_path.write_text(json.dumps(session.__dict__, indent=2), encoding="utf-8")
            mission.state.status = "running"
            mission.state.stop_reason = "delegated_runtime_running"
            mission.state.planner_loop_status = "launching"
            mission.planner_loop_status = "launching"
            mission.delegated_runtime_sessions = [session]
            mission.state.delegated_runtime_sessions = [session.__dict__]
            store.update_mission(mission)

            with (
                mock.patch(
                    "grant_agent.cli._active_mission_async_dispatches",
                    return_value=[],
                ) as active_dispatches,
                mock.patch(
                    "grant_agent.cli._launch_async_mission_resume",
                    return_value={
                        "pid": 4321,
                        "logPath": str(root / "resume.log"),
                        "command": ["python"],
                    },
                ) as launch,
            ):
                dispatched = _auto_resume_ready_delegated_missions(root, store)

            active_dispatches.assert_called_once_with(root, mission.mission_id)
            launch.assert_called_once_with(root, mission.mission_id)
            self.assertEqual([item["missionId"] for item in dispatched], [mission.mission_id])
            refreshed = store.get_mission(mission.mission_id)
            self.assertIsNotNone(refreshed)
            self.assertEqual(refreshed.state.status, "running")
            self.assertEqual(refreshed.state.planner_loop_status, "launching")
            self.assertTrue(refreshed.delegated_runtime_sessions[0].acknowledged)
            self.assertIn("automatic reconciliation", refreshed.proof.summary)

    @mock.patch("grant_agent.runtime_supervisor._pid_alive", return_value=False)
    def test_auto_resume_refreshes_running_delegate_before_skip(
        self,
        _pid_alive_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Resume stale running delegate before skip",
                success_checks=[],
                mode="Deep Run",
                verification_commands=[],
                max_runtime_seconds=7200,
                run_until_behavior="continue_until_blocked",
            )
            runtime_dir = root / ".agent_control" / "runtime_sessions"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            session_path = runtime_dir / "delegate_dead_running.json"
            events_path = runtime_dir / "delegate_dead_running.events.jsonl"
            session = DelegatedRuntimeSession(
                delegated_id="delegate_dead_running",
                runtime_id="hermes",
                launch_command="hermes chat",
                status="running",
                detail="Delegated runtime heartbeat: session is healthy.",
                session_path=str(session_path),
                events_path=str(events_path),
                pid=999999,
                supervisor_pid=999998,
                heartbeat_status="healthy",
                heartbeat_at="2999-01-01T00:00:00+00:00",
                heartbeat_interval_seconds=10,
                exit_code=None,
                acknowledged=False,
            )
            session_path.write_text(json.dumps(session.__dict__, indent=2), encoding="utf-8")
            mission.state.status = "running"
            mission.state.stop_reason = None
            mission.state.planner_loop_status = "running"
            mission.planner_loop_status = "running"
            mission.delegated_runtime_sessions = [session]
            mission.state.delegated_runtime_sessions = [session.__dict__]
            store.update_mission(mission)

            with mock.patch(
                "grant_agent.cli._launch_async_mission_resume",
                return_value={
                    "pid": 5432,
                    "logPath": str(root / "resume.log"),
                    "command": ["python"],
                },
            ) as launch:
                dispatched = _auto_resume_ready_delegated_missions(root, store)

            launch.assert_called_once_with(root, mission.mission_id)
            self.assertEqual([item["missionId"] for item in dispatched], [mission.mission_id])
            refreshed = store.get_mission(mission.mission_id)
            self.assertIsNotNone(refreshed)
            self.assertEqual(refreshed.state.planner_loop_status, "launching")
            self.assertEqual(refreshed.delegated_runtime_sessions[0].status, "failed")
            self.assertTrue(refreshed.delegated_runtime_sessions[0].acknowledged)
            self.assertIn(
                "recorded_process_missing_without_exit",
                events_path.read_text(encoding="utf-8"),
            )

    def test_auto_resume_does_not_overwrite_concurrent_mission_updates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Resume terminal lane without clobbering neighbors",
                success_checks=[],
                mode="Deep Run",
                verification_commands=[],
                max_runtime_seconds=7200,
                run_until_behavior="continue_until_blocked",
            )
            neighbor = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Neighbor before async worker update",
                success_checks=[],
                mode="Deep Run",
                verification_commands=[],
                max_runtime_seconds=7200,
                run_until_behavior="continue_until_blocked",
            )
            runtime_dir = root / ".agent_control" / "runtime_sessions"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            session_path = runtime_dir / "delegate_completed_no_clobber.json"
            session = DelegatedRuntimeSession(
                delegated_id="delegate_completed_no_clobber",
                runtime_id="hermes",
                launch_command="hermes chat",
                status="completed",
                detail="Delegated runtime process completed.",
                session_path=str(session_path),
                exit_code=0,
                acknowledged=False,
            )
            session_path.write_text(json.dumps(session.__dict__, indent=2), encoding="utf-8")
            mission.state.status = "running"
            mission.state.stop_reason = None
            mission.state.planner_loop_status = "running"
            mission.delegated_runtime_sessions = [session]
            mission.state.delegated_runtime_sessions = [session.__dict__]
            store.update_mission(mission)

            def _launch_and_update_neighbor(_root: pathlib.Path, _mission_id: str) -> dict:
                fresh_store = ControlRoomStore(_root)
                updated = fresh_store.get_mission(neighbor.mission_id)
                self.assertIsNotNone(updated)
                updated.objective = "Neighbor after async worker update"
                fresh_store.update_mission(updated)
                return {"pid": 6789, "logPath": str(root / "resume.log"), "command": ["python"]}

            with mock.patch(
                "grant_agent.cli._launch_async_mission_resume",
                side_effect=_launch_and_update_neighbor,
            ):
                dispatched = _auto_resume_ready_delegated_missions(root, store)

            self.assertEqual([item["missionId"] for item in dispatched], [mission.mission_id])
            refreshed_neighbor = ControlRoomStore(root).get_mission(neighbor.mission_id)
            self.assertIsNotNone(refreshed_neighbor)
            self.assertEqual(refreshed_neighbor.objective, "Neighbor after async worker update")

    def test_sync_mission_discovers_delegated_session_when_result_omits_session_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Discover delegated session from runtime store",
                success_checks=[],
                mode="Deep Run",
                verification_commands=[],
                max_runtime_seconds=7200,
                run_until_behavior="continue_until_blocked",
            )
            runtime_dir = root / ".agent_control" / "runtime_sessions"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            session_path = runtime_dir / "delegate_discovered.json"
            session = DelegatedRuntimeSession(
                delegated_id="delegate_discovered",
                runtime_id="hermes",
                launch_command="hermes chat",
                status="running",
                detail="Delegated runtime process is running.",
                session_path=str(session_path),
                workspace_root=str(root),
                execution_root=str(root),
                source_step_id="step_delegate",
                pid=0,
                supervisor_pid=0,
                acknowledged=False,
            )
            session_path.write_text(json.dumps(session.__dict__, indent=2), encoding="utf-8")

            payload = _sync_mission_from_result(
                store,
                mission.mission_id,
                {
                    "status": "ok",
                    "autopilot_status": "paused",
                    "autopilot_pause_reason": "delegated_runtime_running",
                    "session_path": str(root / ".agent_runs" / "session_discovery"),
                    "plan_revisions": [{"active_step_id": "step_delegate"}],
                    "delegated_runtime_sessions": [],
                    "execution_scope": {
                        "requested": "workspace",
                        "strategy": "direct",
                        "workspace_root": str(root),
                        "execution_root": str(root),
                    },
                },
            )

            self.assertNotIn("error", payload)
            refreshed = store.get_mission(mission.mission_id)
            self.assertIsNotNone(refreshed)
            self.assertEqual(refreshed.state.status, "running")
            self.assertEqual(len(refreshed.delegated_runtime_sessions), 1)
            self.assertEqual(
                refreshed.delegated_runtime_sessions[0].delegated_id,
                "delegate_discovered",
            )

    def test_control_room_summary_triggers_delegate_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Resume from summary refresh",
                success_checks=[],
                mode="Deep Run",
                verification_commands=[],
                max_runtime_seconds=7200,
                run_until_behavior="continue_until_blocked",
            )
            runtime_dir = root / ".agent_control" / "runtime_sessions"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            session_path = runtime_dir / "delegate_failed_summary.json"
            session = DelegatedRuntimeSession(
                delegated_id="delegate_failed_summary",
                runtime_id="hermes",
                launch_command="hermes chat",
                status="failed",
                detail="Delegated runtime process failed.",
                session_path=str(session_path),
                exit_code=1,
                acknowledged=False,
            )
            session_path.write_text(json.dumps(session.__dict__, indent=2), encoding="utf-8")
            mission.state.status = "running"
            mission.state.stop_reason = None
            mission.state.planner_loop_status = "running"
            mission.delegated_runtime_sessions = [session]
            mission.state.delegated_runtime_sessions = [session.__dict__]
            store.update_mission(mission)

            with mock.patch(
                "grant_agent.cli._launch_async_mission_resume",
                return_value={"pid": 5678, "logPath": str(root / "resume.log"), "command": ["python"]},
            ):
                exit_code, payload = self._run_json_command(
                    cmd_control_room_summary,
                    root=str(root),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["autoResumeDispatches"][0]["missionId"], mission.mission_id)
            refreshed = ControlRoomStore(root).get_mission(mission.mission_id)
            self.assertEqual(refreshed.state.planner_loop_status, "launching")

    def test_mission_watchdog_triggers_delegate_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Watchdog should reconcile finished delegated lanes",
                success_checks=[],
                mode="Deep Run",
                verification_commands=[],
                max_runtime_seconds=7200,
                run_until_behavior="continue_until_blocked",
            )
            runtime_dir = root / ".agent_control" / "runtime_sessions"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            session_path = runtime_dir / "delegate_completed_watchdog.json"
            session = DelegatedRuntimeSession(
                delegated_id="delegate_completed_watchdog",
                runtime_id="hermes",
                launch_command="hermes chat",
                status="completed",
                detail="Delegated runtime process completed.",
                session_path=str(session_path),
                exit_code=0,
                acknowledged=False,
            )
            session_path.write_text(json.dumps(session.__dict__, indent=2), encoding="utf-8")
            mission.state.status = "running"
            mission.state.stop_reason = None
            mission.state.planner_loop_status = "running"
            mission.delegated_runtime_sessions = [session]
            mission.state.delegated_runtime_sessions = [session.__dict__]
            store.update_mission(mission)

            with mock.patch(
                "grant_agent.cli._launch_async_mission_resume",
                return_value={"pid": 2468, "logPath": str(root / "resume.log"), "command": ["python"]},
            ):
                exit_code, payload = self._run_json_command(
                    cmd_mission_watchdog,
                    root=str(root),
                    stale_minutes=60,
                    no_write_report=False,
                    notify_telegram=False,
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["autoResumeDispatches"][0]["missionId"], mission.mission_id)
            self.assertEqual(
                payload["watchdog"]["autoResumeDispatches"][0]["missionId"],
                mission.mission_id,
            )
            refreshed = ControlRoomStore(root).get_mission(mission.mission_id)
            self.assertEqual(refreshed.state.status, "running")
            self.assertEqual(refreshed.state.planner_loop_status, "launching")
            self.assertIn("automatic reconciliation", refreshed.proof.summary)

    def test_mission_watchdog_rebuilds_report_after_post_report_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            open_report = {
                "schema": "fluxio.mission_watchdog.v1",
                "generatedAt": utc_now_iso(),
                "root": str(root),
                "summary": {"status": "open", "issueCount": 1},
                "issues": [{"issueId": "mission_x:delegated_runtime_completed_unreconciled"}],
                "problemReport": {
                    "schema": "fluxio.watchdog_problem_report.v1",
                    "status": "open",
                    "problemCount": 1,
                    "problems": [{"problemId": "mission_x:delegated_runtime_completed_unreconciled"}],
                    "firstProblem": {
                        "problemId": "mission_x:delegated_runtime_completed_unreconciled",
                        "kind": "delegated_runtime_completed_unreconciled",
                    },
                    "nextAction": "Resume mission_x.",
                },
                "problemRegistry": {
                    "schema": "fluxio.watchdog_problem_registry.v1",
                    "status": "open",
                    "openProblemCount": 1,
                    "firstOpenProblem": {
                        "problemId": "mission_x:delegated_runtime_completed_unreconciled",
                    },
                },
                "nextAction": "Resume mission_x.",
            }
            clear_report = {
                "schema": "fluxio.mission_watchdog.v1",
                "generatedAt": utc_now_iso(),
                "root": str(root),
                "summary": {"status": "clear", "issueCount": 0},
                "issues": [],
                "problemReport": {
                    "schema": "fluxio.watchdog_problem_report.v1",
                    "status": "clear",
                    "problemCount": 0,
                    "problems": [],
                    "firstProblem": {},
                    "nextAction": "No watchdog problems found.",
                },
                "problemRegistry": {
                    "schema": "fluxio.watchdog_problem_registry.v1",
                    "status": "clear",
                    "openProblemCount": 0,
                    "firstOpenProblem": {},
                },
                "nextAction": "No watchdog problems found.",
            }

            with (
                mock.patch(
                    "grant_agent.cli._auto_resume_ready_delegated_missions",
                    side_effect=[
                        [],
                        [{"missionId": "mission_x", "pid": 1234, "blocked": False}],
                    ],
                ) as auto_resume,
                mock.patch(
                    "grant_agent.cli.build_mission_watchdog_report",
                    side_effect=[open_report, clear_report],
                ) as build_report,
            ):
                exit_code, payload = self._run_json_command(
                    cmd_mission_watchdog,
                    root=str(root),
                    stale_minutes=60,
                    no_write_report=True,
                    notify_telegram=False,
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(auto_resume.call_count, 2)
            self.assertEqual(build_report.call_count, 2)
            self.assertEqual(payload["watchdog"]["problemReport"]["status"], "clear")
            self.assertEqual(payload["autoResumeDispatches"][0]["missionId"], "mission_x")
            self.assertEqual(
                payload["watchdog"]["autoResumeDispatches"][0]["missionId"],
                "mission_x",
            )

    def test_mission_budget_settings_parses_days_timer_from_objective(self) -> None:
        fixed_now = datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc)
        settings = _mission_budget_settings(
            objective="Run this Golf 40 mission for 2 days and keep going.",
            budget_hours=12,
            run_until_behavior="pause_on_failure",
            now=fixed_now,
        )
        self.assertEqual(settings["max_runtime_seconds"], 2 * 24 * 3600)
        self.assertEqual(settings["run_until_behavior"], "continue_until_blocked")
        self.assertTrue(settings["deadline_at"])

    def test_mission_loop_pauses_while_delegated_runtime_is_running(self) -> None:
        mission = argparse.Namespace(
            run_budget=argparse.Namespace(
                run_until_behavior="continue_until_blocked",
                deadline_at=None,
            )
        )
        should_continue = _mission_should_continue_after_result(
            mission,
            {
                "status": "ok",
                "autopilot_status": "paused",
                "autopilot_pause_reason": "delegated_runtime_running",
                "remaining_steps": ["wait"],
            },
        )
        self.assertFalse(should_continue)
        self.assertGreaterEqual(_mission_poll_interval_seconds(mission), 1)

    def test_mission_loop_stops_when_delegated_runtime_running_but_pause_mode(self) -> None:
        mission = argparse.Namespace(
            run_budget=argparse.Namespace(
                run_until_behavior="pause_on_failure",
                deadline_at=None,
            )
        )
        should_continue = _mission_should_continue_after_result(
            mission,
            {
                "status": "ok",
                "autopilot_status": "paused",
                "autopilot_pause_reason": "delegated_runtime_running",
                "remaining_steps": ["wait"],
            },
        )
        self.assertFalse(should_continue)
        self.assertEqual(_mission_poll_interval_seconds(mission), 0)

    def test_mission_start_launch_async_dispatches_background_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")

            save_code, save_payload = self._run_json_command(
                cmd_workspace_save,
                root=str(root),
                name="Fluxio Workspace",
                path=str(root),
                default_runtime="hermes",
                user_profile="builder",
                preferred_harness="fluxio_hybrid",
                routing_strategy="profile_default",
                route_overrides_json="[]",
                auto_optimize_routing="false",
                minimax_auth_mode="none",
                commit_message_style="scoped",
                execution_target_preference="profile_default",
                workspace_id=None,
            )
            self.assertEqual(save_code, 0)
            workspace_id = save_payload["workspace"]["workspace_id"]

            runtime_status = RuntimeInstallStatus(
                runtime_id="hermes",
                label="Hermes",
                detected=True,
                doctor_summary="Hermes is ready.",
            )
            adapter = mock.Mock()
            adapter.doctor.return_value = runtime_status

            with (
                mock.patch("grant_agent.cli.runtime_adapter_map", return_value={"hermes": adapter}),
                mock.patch(
                    "grant_agent.cli.detect_default_verification_commands",
                    return_value=["python -m pytest tests -q"],
                ),
                mock.patch("grant_agent.cli.load_telegram_destination", return_value=""),
                mock.patch(
                    "grant_agent.cli._launch_async_mission_resume",
                    return_value={
                        "pid": 4242,
                        "logPath": str(root / ".agent_control" / "mission_async" / "mission.log"),
                        "command": ["python", "-m", "grant_agent.cli", "mission-action"],
                    },
                ),
                mock.patch("grant_agent.cli._run_mission_engine_cycles") as mocked_cycles,
            ):
                exit_code, payload = self._run_json_command(
                    cmd_mission_start,
                    root=str(root),
                    workspace_id=workspace_id,
                    runtime="hermes",
                    objective="Long mission should dispatch asynchronously.",
                    success_check=[],
                    mode="Autopilot",
                    budget_hours=48,
                    run_until="continue_until_blocked",
                    profile="builder",
                    escalation_destination="",
                    route_overrides_json="[]",
                    relative_stop_minutes=0,
                    code_execution=False,
                    code_execution_memory="4g",
                    code_execution_container_id="",
                    code_execution_required=False,
                    launch_async=True,
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["launchedAsync"])
            self.assertEqual(payload["dispatch"]["pid"], 4242)
            self.assertEqual(payload["mission"]["state"]["status"], "running")
            mocked_cycles.assert_not_called()

    def test_launch_async_mission_resume_skips_duplicate_active_worker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            events_path = root / ".agent_control" / "mission_events.jsonl"
            events_path.parent.mkdir(parents=True, exist_ok=True)
            events_path.write_text(
                json.dumps(
                    {
                        "mission_id": "mission_guard",
                        "kind": "mission.resume_dispatched",
                        "metadata": {
                            "pid": 6262,
                            "logPath": str(root / "mission.log"),
                            "command": [
                                "python",
                                "-m",
                                "grant_agent.cli",
                                "mission-action",
                                "--mission-id",
                                "mission_guard",
                                "--action",
                                "resume",
                            ],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with (
                mock.patch("grant_agent.cli._pid_exists", return_value=True),
                mock.patch("grant_agent.cli._process_stat_and_elapsed_seconds", return_value=("S", 10)),
                mock.patch(
                    "grant_agent.cli._process_command",
                    return_value=(
                        "python -m grant_agent.cli mission-action "
                        "--mission-id mission_guard --action resume"
                    ),
                ),
                mock.patch("grant_agent.cli.subprocess.Popen") as mocked_popen,
            ):
                dispatch = _launch_async_mission_resume(root, "mission_guard")

            self.assertTrue(dispatch["skipped"])
            self.assertEqual(dispatch["pid"], 6262)
            self.assertEqual(dispatch["reason"], "mission_resume_already_running")
            mocked_popen.assert_not_called()

    def test_launch_async_mission_resume_sets_compact_child_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)

            with mock.patch("grant_agent.cli.subprocess.Popen") as mocked_popen:
                mocked_popen.return_value.pid = 9191
                dispatch = _launch_async_mission_resume(root, "mission_compact")

            self.assertEqual(dispatch["pid"], 9191)
            child_env = mocked_popen.call_args.kwargs["env"]
            self.assertEqual(child_env["FLUXIO_MISSION_ACTION_COMPACT"], "1")
            self.assertEqual(child_env["PYTHONUNBUFFERED"], "1")

    def test_mission_action_async_resume_preserves_child_session_update(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Preserve child reconciliation state",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=7200,
            )
            mission.state.latest_session_id = "session_resume"
            mission.state.status = "running"
            mission.delegated_runtime_sessions = [
                DelegatedRuntimeSession(
                    delegated_id="delegate_completed",
                    runtime_id="hermes",
                    launch_command="hermes chat",
                    status="completed",
                    acknowledged=False,
                )
            ]
            store.update_mission(mission)

            def fake_launch(dispatch_root: pathlib.Path, mission_id: str) -> dict:
                child_store = ControlRoomStore(dispatch_root)
                child_mission = child_store.get_mission(mission_id)
                child_mission.delegated_runtime_sessions[0].acknowledged = True
                child_store.update_mission(child_mission)
                return {"pid": 4321, "logPath": str(root / "resume.log"), "command": ["python"]}

            with mock.patch(
                "grant_agent.cli._launch_async_mission_resume",
                side_effect=fake_launch,
            ):
                exit_code, payload = self._run_json_command(
                    cmd_mission_action,
                    root=str(root),
                    mission_id=mission.mission_id,
                    action="resume",
                    launch_async=True,
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["mission"]["delegated_runtime_sessions"][0]["acknowledged"])
            refreshed = ControlRoomStore(root).get_mission(mission.mission_id)
            self.assertTrue(refreshed.delegated_runtime_sessions[0].acknowledged)

    def test_route_outcome_trends_tolerates_pruned_session_race(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            runs = root / ".agent_runs"
            stale = runs / "session_pruned"
            current = runs / "session_current"
            stale.mkdir(parents=True)
            current.mkdir(parents=True)
            (current / "state.json").write_text(
                json.dumps(
                    {
                        "objective": "Build a frontend sample",
                        "autopilot_status": "completed",
                        "route_configs": [
                            {
                                "role": "executor",
                                "provider": "openai-codex",
                                "model": "gpt-5.5",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            real_stat = pathlib.Path.stat

            def flaky_stat(path, *args, **kwargs):
                if pathlib.Path(path).name == "session_pruned":
                    raise FileNotFoundError(path)
                return real_stat(path, *args, **kwargs)

            with mock.patch("pathlib.Path.stat", flaky_stat):
                trends = build_route_outcome_trends(root)

            self.assertEqual(trends["scannedRuns"], 1)
            self.assertEqual(trends["routeStats"][0]["latestSessionId"], "session_current")

    def test_launch_async_mission_resume_blocks_direct_dispatch_when_storage_full(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            control = root / ".agent_control"
            control.mkdir(exist_ok=True)
            (control / "nas_storage_pressure_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.nas_storage_pressure.v1",
                        "checkedAt": datetime.now(timezone.utc).isoformat(),
                        "maxAgeSeconds": 172800,
                        "mount": "/volume1/Saclay",
                        "status": "critical",
                        "usedPercent": 100,
                        "availableBytes": 0,
                        "nextAction": "Free NAS space before resuming missions.",
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch("grant_agent.cli.subprocess.Popen") as mocked_popen:
                dispatch = _launch_async_mission_resume(root, "mission_guard")

            self.assertTrue(dispatch["blocked"])
            self.assertTrue(dispatch["skipped"])
            self.assertEqual(dispatch["reason"], "nas_storage_pressure_block")
            self.assertEqual(dispatch["code"], "nas_storage_pressure_block")
            mocked_popen.assert_not_called()

    def test_auto_resume_marks_reconciliation_blocked_by_storage_pressure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Resume after failed delegated lane",
                success_checks=[],
                mode="Deep Run",
                verification_commands=[],
                max_runtime_seconds=7200,
                run_until_behavior="continue_until_blocked",
            )
            runtime_dir = root / ".agent_control" / "runtime_sessions"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            session_path = runtime_dir / "delegate_failed.json"
            session = DelegatedRuntimeSession(
                delegated_id="delegate_failed",
                runtime_id="hermes",
                launch_command="hermes chat",
                status="failed",
                detail="Delegated runtime process failed.",
                session_path=str(session_path),
                exit_code=1,
                acknowledged=False,
            )
            session_path.write_text(json.dumps(session.__dict__, indent=2), encoding="utf-8")
            mission.state.status = "running"
            mission.state.stop_reason = None
            mission.state.planner_loop_status = "running"
            mission.planner_loop_status = "running"
            mission.delegated_runtime_sessions = [session]
            mission.state.delegated_runtime_sessions = [session.__dict__]
            store.update_mission(mission)

            with mock.patch(
                "grant_agent.cli._launch_async_mission_resume",
                return_value={
                    "blocked": True,
                    "skipped": True,
                    "reason": "nas_storage_pressure_block",
                    "code": "nas_storage_pressure_block",
                },
            ):
                dispatched = _auto_resume_ready_delegated_missions(root, store)

            self.assertEqual(dispatched[0]["missionId"], mission.mission_id)
            self.assertTrue(dispatched[0]["blocked"])
            refreshed = store.get_mission(mission.mission_id)
            self.assertEqual(refreshed.state.status, "blocked")
            self.assertEqual(refreshed.state.stop_reason, "nas_storage_pressure")
            self.assertEqual(refreshed.proof.blocked_by, ["nas_storage_pressure"])

    def test_windows_pid_check_rejects_localized_no_task_output(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["tasklist"],
            returncode=0,
            stdout="Information : aucune tâche en service ne correspond aux critères spécifiés.\n",
            stderr="",
        )
        with (
            mock.patch("grant_agent.cli.os.name", "nt"),
            mock.patch("grant_agent.cli.subprocess.run", return_value=completed),
        ):
            self.assertFalse(_pid_exists(42944))

    def test_mission_action_resume_launch_async_dispatches_background_worker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Dispatch resume in background",
                success_checks=[],
                mode="Autopilot",
                verification_commands=["python -m pytest tests -q"],
                max_runtime_seconds=7200,
            )
            store.update_mission(mission)

            runtime_status = RuntimeInstallStatus(
                runtime_id="hermes",
                label="Hermes",
                detected=True,
                doctor_summary="Hermes is ready.",
            )
            adapter = mock.Mock()
            adapter.doctor.return_value = runtime_status

            with (
                mock.patch("grant_agent.cli.runtime_adapter_map", return_value={"hermes": adapter}),
                mock.patch(
                    "grant_agent.cli._launch_async_mission_resume",
                    return_value={
                        "pid": 5252,
                        "logPath": str(root / ".agent_control" / "mission_async" / "mission.log"),
                        "command": ["python", "-m", "grant_agent.cli", "mission-action"],
                    },
                ),
                mock.patch("grant_agent.cli._run_mission_engine_cycles") as mocked_cycles,
            ):
                exit_code, payload = self._run_json_command(
                    cmd_mission_action,
                    root=str(root),
                    mission_id=mission.mission_id,
                    action="resume",
                    launch_async=True,
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["launchedAsync"])
            self.assertEqual(payload["dispatch"]["pid"], 5252)
            self.assertEqual(payload["mission"]["state"]["status"], "running")
            mocked_cycles.assert_not_called()

    def test_mission_action_resume_blocks_async_launch_when_nas_storage_full(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            control = root / ".agent_control"
            control.mkdir(exist_ok=True)
            (control / "nas_storage_pressure_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.nas_storage_pressure.v1",
                        "checkedAt": datetime.now(timezone.utc).isoformat(),
                        "maxAgeSeconds": 172800,
                        "host": "100.125.54.118",
                        "mount": "/volume1/Saclay",
                        "status": "critical",
                        "usedPercent": 100,
                        "availableBytes": 0,
                        "largestSuspectedExternalPath": "/volume1/Duncan/MacBook Air.sparsebundle",
                        "suspectedExternalGB": 778.67,
                        "nextAction": "Free NAS space before resuming missions.",
                    }
                ),
                encoding="utf-8",
            )
            store = ControlRoomStore(root)
            workspace = store.upsert_workspace(
                name="NAS Mission Workspace",
                root_path="/volume1/Saclay/projects/demo",
                default_runtime="hermes",
                nas_project_path="/volume1/Saclay/projects/demo",
            )
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Should not launch on full NAS",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=7200,
            )
            store.update_mission(mission)

            with mock.patch("grant_agent.cli._launch_async_mission_resume") as mocked_launch:
                exit_code, payload = self._run_json_command(
                    cmd_mission_action,
                    root=str(root),
                    mission_id=mission.mission_id,
                    action="resume",
                    launch_async=True,
                )

            self.assertEqual(exit_code, 1)
            self.assertEqual(payload["code"], "nas_storage_pressure_block")
            self.assertEqual(payload["storage"]["availableBytes"], 0)
            self.assertEqual(payload["mission"]["mission_id"], mission.mission_id)
            mocked_launch.assert_not_called()

    def test_mission_start_blocks_nas_workspace_when_storage_full(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            control = root / ".agent_control"
            control.mkdir(exist_ok=True)
            (control / "nas_storage_pressure_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.nas_storage_pressure.v1",
                        "checkedAt": datetime.now(timezone.utc).isoformat(),
                        "maxAgeSeconds": 172800,
                        "mount": "/volume1/Saclay",
                        "status": "critical",
                        "usedPercent": 100,
                        "availableBytes": 0,
                    }
                ),
                encoding="utf-8",
            )
            store = ControlRoomStore(root)
            workspace = store.upsert_workspace(
                name="NAS Mission Workspace",
                root_path="/volume1/Saclay/projects/demo",
                default_runtime="hermes",
                nas_project_path="/volume1/Saclay/projects/demo",
            )

            exit_code, payload = self._run_json_command(
                cmd_mission_start,
                root=str(root),
                workspace_id=workspace.workspace_id,
                runtime="hermes",
                objective="Do not create a mission when NAS is full",
                success_check=[],
                mode="Autopilot",
                verification_command=[],
                escalation_destination="",
                budget_hours=4,
                run_until="continue_until_blocked",
                relative_stop_minutes=0,
                profile="builder",
                route_overrides_json="[]",
                code_execution=False,
                code_execution_memory="4g",
                code_execution_container_id="",
                code_execution_required=False,
                launch_async=True,
            )

            self.assertEqual(exit_code, 1)
            self.assertEqual(payload["code"], "nas_storage_pressure_block")
            self.assertEqual(payload["workspace"]["workspace_id"], workspace.workspace_id)
            self.assertEqual(len(ControlRoomStore(root).load_missions()), 0)

    def test_mission_action_resume_ignores_nas_pressure_for_local_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            control = root / ".agent_control"
            control.mkdir(exist_ok=True)
            (control / "nas_storage_pressure_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.nas_storage_pressure.v1",
                        "checkedAt": datetime.now(timezone.utc).isoformat(),
                        "maxAgeSeconds": 172800,
                        "mount": "/volume1/Saclay",
                        "status": "critical",
                        "usedPercent": 100,
                        "availableBytes": 0,
                    }
                ),
                encoding="utf-8",
            )
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Local workspace can still launch",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=7200,
            )
            store.update_mission(mission)

            with mock.patch(
                "grant_agent.cli._launch_async_mission_resume",
                return_value={
                    "pid": 7777,
                    "logPath": str(control / "mission_async" / "mission.log"),
                    "command": ["python", "-m", "grant_agent.cli", "mission-action"],
                },
            ):
                exit_code, payload = self._run_json_command(
                    cmd_mission_action,
                    root=str(root),
                    mission_id=mission.mission_id,
                    action="resume",
                    launch_async=True,
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["launchedAsync"])
            self.assertEqual(payload["dispatch"]["pid"], 7777)


if __name__ == "__main__":
    unittest.main()

