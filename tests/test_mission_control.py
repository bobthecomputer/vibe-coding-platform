from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.cli import cmd_mission_follow_up, cmd_workspace_delete
from grant_agent import mission_control as mission_control_module
from grant_agent.mission_control import (
    ControlRoomStore,
    ROUTE_TRUST_SAMPLE_TEMPLATES,
    _build_generated_image_artifacts_snapshot,
    _build_git_actions,
    _build_validation_actions,
    _mission_title,
    _platform_path_for_windows_drive,
    _recover_evidence_path,
    _sync_project_tree,
    build_harness_lab_snapshot,
    build_integration_readiness_snapshot,
    build_summary_harness_lab_snapshot,
    build_red_team_escalation_snapshot,
    build_release_readiness_snapshot,
    build_escalation_preview,
    mission_mode_to_engine_mode,
    mission_time_budget_window,
    record_cross_device_launch_rehearsal_receipt,
    infer_planned_file_scope,
    resolve_workspace_sync_conflict,
    resolve_workspace_sync_conflict_batch,
)
from grant_agent.mission_watchdog import (
    build_mission_watchdog_report,
    prune_stale_generated_agent_runs,
    write_mission_watchdog_report,
    write_watchdog_supervisor_state,
)
from grant_agent.models import DelegatedRuntimeSession, MissionEvent, utc_now_iso
from grant_agent.workspace_actions import execute_control_room_workspace_action


class MissionControlTests(unittest.TestCase):
    def test_verification_summary_handles_structured_failed_check_rows(self) -> None:
        mission = mission_control_module.Mission(
            mission_id="mission_structured_failure",
            workspace_id="workspace",
            runtime_id="hermes",
            objective="Keep lane receipts durable.",
            success_checks=[],
        )
        mission.proof.failed_checks = [
            {"checkId": "lane_control_receipt", "detail": "Receipt command returned proof."},
            {"title": "Artifact gate", "status": "failed"},
        ]

        summary = mission_control_module._verification_summary_for_mission(mission, "failed")

        self.assertEqual(summary, "Failed: lane_control_receipt, Artifact gate")

    def test_runtime_compartment_snapshot_derives_mission_chat_mission_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            compartment_dir = root / ".agent_control" / "runtime_compartments"
            compartment_dir.mkdir(parents=True)
            mission = mission_control_module.Mission(
                mission_id="mission_live",
                workspace_id="workspace",
                runtime_id="hermes",
                objective="Keep Agent Live attached to real dialogue.",
                title="Agent Live thread",
                success_checks=[],
            )
            (compartment_dir / "mission-chat-mission_live.json").write_text(
                json.dumps(
                    {
                        "sessionId": "mission-chat-mission_live",
                        "runtime": "hermes",
                        "messages": [
                            {"role": "operator", "text": "Continue this mission."},
                            {
                                "role": "assistant",
                                "text": "I can continue from the persisted thread.",
                                "source": "backend-model-message",
                            },
                        ],
                        "turnReceipt": {
                            "schema": "fluxio.turn_receipt.v1",
                            "assistantMessage": "I can continue from the persisted thread.",
                            "command": "hermes chat -q <prompt>",
                        },
                    }
                ),
                encoding="utf-8",
            )

            snapshot = mission_control_module._build_runtime_compartments_snapshot(root, [mission])
            item = next(row for row in snapshot["items"] if row["sessionId"] == "mission-chat-mission_live")

            self.assertEqual(item["missionId"], "mission_live")
            self.assertEqual(item["missionTitle"], "Agent Live thread")
            self.assertEqual(len(item["messages"]), 2)
            self.assertEqual(item["turnReceipt"]["assistantMessage"], "I can continue from the persisted thread.")
            self.assertEqual(item["turnReceipts"][0]["command"], "hermes chat -q <prompt>")

    def test_bootstrap_summary_includes_runtime_compartments_for_agent_live_dialogue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            control_dir = root / ".agent_control"
            compartment_dir = control_dir / "runtime_compartments"
            compartment_dir.mkdir(parents=True)
            store = ControlRoomStore(root)
            (compartment_dir / "mission-chat-mission_live.json").write_text(
                json.dumps(
                    {
                        "sessionId": "mission-chat-mission_live",
                        "runtime": "hermes",
                        "messages": [
                            {"role": "operator", "text": "Show the persisted conversation."},
                            {"role": "assistant", "text": "This is real persisted dialogue."},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            summary = store.build_bootstrap_summary_snapshot()
            sessions = [
                item.get("sessionId")
                for item in summary["runtimeCompartments"]["items"]
                if isinstance(item, dict)
            ]

            self.assertIn("mission-chat-mission_live", sessions)
            self.assertEqual(summary["runtimeCompartments"]["source"], "agent_control_runtime_state")

    def test_control_room_json_loader_reuses_unchanged_file_parse(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            store = ControlRoomStore(root)
            path = root / ".agent_control" / "sample.json"
            path.write_text(json.dumps([{"value": 1}]), encoding="utf-8")
            mission_control_module._CONTROL_ROOM_JSON_CACHE.clear()

            with mock.patch.object(
                mission_control_module.json,
                "loads",
                wraps=mission_control_module.json.loads,
            ) as loads:
                first = store._load_json(path, [])
                second = store._load_json(path, [])

            self.assertEqual(first, [{"value": 1}])
            self.assertIs(first, second)
            self.assertEqual(loads.call_count, 1)

    def test_control_room_json_loader_invalidates_after_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            store = ControlRoomStore(root)
            path = root / ".agent_control" / "sample.json"
            store._write_json_if_changed(path, [{"value": 1}])
            self.assertEqual(store._load_json(path, []), [{"value": 1}])
            store._write_json_if_changed(path, [{"value": 2}])

            self.assertEqual(store._load_json(path, []), [{"value": 2}])

    def test_missing_mission_row_recovers_from_live_autonomous_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True, exist_ok=True)
            store.save_missions([])
            session_path = control_dir / "runtime_sessions" / "delegate_live.json"
            session_path.parent.mkdir(parents=True, exist_ok=True)
            session_path.write_text(
                json.dumps(
                    {
                        "delegated_id": "delegate_live",
                        "runtime_id": "hermes",
                        "launch_command": (
                            "hermes chat -q 'Resume mission mission_recovered with "
                            ".agent_control/mission_artifacts hard artifact gate'"
                        ),
                        "status": "running",
                        "session_path": str(session_path),
                    }
                ),
                encoding="utf-8",
            )
            (control_dir / "autonomous_workflows.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": "autonomous-workflows.v1",
                        "workflows": [
                            {
                                "schemaVersion": "autonomous-workflow-record.v1",
                                "workflowId": "workflow_mission_recovered",
                                "missionId": "mission_recovered",
                                "workspaceId": workspace.workspace_id,
                                "title": "Build a recovered live mission",
                                "objective": "Build a recovered live mission with real artifacts.",
                                "status": "running",
                                "runtimeId": "hermes",
                                "mode": "Autopilot",
                                "createdAt": "2026-06-02T00:00:00+00:00",
                                "updatedAt": "2026-06-02T01:00:00+00:00",
                                "currentPhase": "execute",
                                "continuityState": "delegated_active",
                                "continuityDetail": "hermes lane is still active and restart-safe.",
                                "runBudget": {
                                    "mode": "Autopilot",
                                    "maxRuntimeSeconds": 7200,
                                    "remainingSeconds": 3600,
                                    "status": "delegated_active",
                                    "runUntilBehavior": "continue_until_blocked",
                                },
                                "executionScope": {"workspace_root": str(root), "execution_root": str(root)},
                                "executionPolicy": {"profile_name": "builder"},
                                "runtimeSummary": {
                                    "latestSessionId": "session_live",
                                    "currentRuntimeLane": "hermes",
                                    "lastRuntimeEvent": "hard artifact repair running",
                                },
                                "verification": {
                                    "commands": ["python -m pytest"],
                                    "lastResult": "pending",
                                    "passedChecks": [],
                                    "failedChecks": [],
                                    "verificationFailures": [],
                                },
                                "risk": {"blockers": [], "stopReason": ""},
                                "changedFiles": [],
                                "evidenceFiles": [],
                                "lastProofSummary": "Recovered workflow proof summary.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            recovered = store.get_mission("mission_recovered")

            self.assertIsNotNone(recovered)
            assert recovered is not None
            self.assertEqual(recovered.mission_id, "mission_recovered")
            self.assertEqual(recovered.runtime_id, "hermes")
            self.assertEqual(recovered.state.status, "running")
            self.assertEqual(recovered.state.continuity_state, "delegated_active")
            self.assertEqual(len(recovered.delegated_runtime_sessions), 1)
            self.assertEqual(recovered.delegated_runtime_sessions[0].delegated_id, "delegate_live")
            detail = store.build_mission_detail_snapshot("mission_recovered", event_limit=5)
            self.assertIn("mission_recovered", json.dumps(detail))
            self.assertIn("Build a recovered live mission", json.dumps(detail))

    def test_red_team_escalation_snapshot_counts_more_than_default_visible_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True)
            rows = []
            for index in range(15):
                rows.append(
                    {
                        "schema": "fluxio.red_team_escalation_history.v1",
                        "recordedAt": f"2026-05-29T10:{index:02d}:00+00:00",
                        "preset": "hackaprompt",
                        "status": "pass",
                        "resistance_score": 100,
                        "attempt_count": 20 + index,
                        "blocked_attempt_count": 20 + index,
                        "difficultyLevel": 5,
                        "nextDifficultyLevel": 5,
                        "nextAttemptBudget": 21 + index,
                        "passStreak": index + 1,
                        "cleanPass": True,
                        "shouldEscalate": True,
                        "targetResistanceScore": 98,
                    }
                )
            (control_dir / "red_team_escalation_history.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )

            snapshot = build_red_team_escalation_snapshot(root)

            self.assertEqual(snapshot["summary"]["runCount"], 15)
            self.assertEqual(len(snapshot["history"]), 15)
            self.assertEqual(snapshot["summary"]["nextAttemptBudget"], 35)
            self.assertEqual(snapshot["summary"]["passStreak"], 15)

    @staticmethod
    def _write_clear_watchdog_release_evidence(root: pathlib.Path) -> None:
        control_dir = root / ".agent_control"
        control_dir.mkdir(parents=True, exist_ok=True)
        report = {
            "schema": "fluxio.mission_watchdog.v1",
            "checkedAt": utc_now_iso(),
            "root": str(root),
            "staleMinutes": 60,
            "summary": {
                "missionCount": 1,
                "issueCount": 0,
                "bad": 0,
                "warn": 0,
                "info": 0,
            },
            "issues": [],
            "nextAction": "No watchdog issues found. Keep the scheduled watchdog active.",
            "problemReport": {
                "schema": "fluxio.watchdog_problem_report.v1",
                "checkedAt": utc_now_iso(),
                "status": "clear",
                "problemCount": 0,
                "openProblems": [],
                "firstProblem": {},
                "nextAction": "No watchdog problems found. Keep the external loop active.",
            },
        }
        write_mission_watchdog_report(root, report)
        write_watchdog_supervisor_state(
            root,
            {
                "schema": "fluxio.mission_watchdog_supervisor.v1",
                "root": str(root),
                "processPid": os.getpid(),
                "status": "clear",
                "loopMode": "ongoing",
                "supervisorActive": True,
                "startedAt": utc_now_iso(),
                "lastRunAt": utc_now_iso(),
                "nextRunAt": (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat(),
                "intervalSeconds": 1200,
                "staleMinutes": 60,
                "runsCompleted": 1,
                "lastProblemCount": 0,
                "lastIssueCount": 0,
                "nextAction": "No watchdog problems found. Keep the external loop active.",
            },
        )

    def test_mission_watchdog_flags_queue_front_and_repair_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build a mobile progress watchdog",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "queued"
            mission.state.queue_position = 0
            mission.state.remaining_runtime_seconds = 3600
            store.update_mission(mission)

            report = build_mission_watchdog_report(
                root=root,
                missions=store.load_missions(),
                workspaces=store.load_workspaces(),
                stale_minutes=60,
            )

            kinds = {item["kind"] for item in report["issues"]}
            self.assertIn("queue_front_not_running", kinds)
            self.assertIn("mission-action", report["nextAction"])
            self.assertEqual(report["summary"]["missionCount"], 1)
            self.assertEqual(report["problemReport"]["status"], "open")
            self.assertGreaterEqual(report["problemReport"]["problemCount"], 1)
            self.assertIn("mission-action", report["problemReport"]["firstProblem"]["firstStep"])
            self.assertEqual(report["problemRegistry"]["schema"], "fluxio.watchdog_problem_registry.v1")
            self.assertEqual(report["problemRegistry"]["status"], "open")
            self.assertGreaterEqual(report["problemRegistry"]["openProblemCount"], 1)
            self.assertIn(
                "mission-action",
                report["problemRegistry"]["firstOpenProblem"]["firstRepairStep"],
            )

    def test_watchdog_prunes_only_stale_generated_agent_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            runs_root = root / ".agent_runs"
            stale_session = runs_root / "session_stale"
            current_session = runs_root / "session_current"
            protected_session = runs_root / "session_protected"
            for session in (stale_session, current_session, protected_session):
                session.mkdir(parents=True)
                (session / "timeline.jsonl").write_text("x" * 32, encoding="utf-8")
            old_timestamp = (datetime.now(timezone.utc) - timedelta(hours=3)).timestamp()
            os.utime(stale_session, (old_timestamp, old_timestamp))
            os.utime(protected_session, (old_timestamp, old_timestamp))
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep latest session evidence",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.latest_session_id = "session_protected"

            retention = prune_stale_generated_agent_runs(
                root=root,
                missions=[mission],
                workspaces=store.load_workspaces(),
                retention_minutes=60,
                min_bytes=1,
                max_delete_per_pass=20,
            )

            self.assertEqual(retention["status"], "pruned")
            self.assertEqual(retention["deletedCount"], 1)
            self.assertFalse(stale_session.exists())
            self.assertTrue(current_session.exists())
            self.assertTrue(protected_session.exists())

    def test_mission_watchdog_ignores_stale_historical_delegated_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep only current delegated heartbeat actionable",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "running"
            mission.state.remaining_runtime_seconds = 1800
            stale = DelegatedRuntimeSession(
                delegated_id="delegate_old",
                runtime_id="hermes",
                launch_command="old",
                status="running",
                updated_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                heartbeat_status="stale",
                heartbeat_age_seconds=7200,
            )
            current = DelegatedRuntimeSession(
                delegated_id="delegate_current",
                runtime_id="hermes",
                launch_command="current",
                status="running",
                updated_at=datetime.now(timezone.utc).isoformat(),
                heartbeat_status="healthy",
                heartbeat_age_seconds=5,
            )
            mission.delegated_runtime_sessions = [stale, current]
            store.save_missions([mission])

            report = build_mission_watchdog_report(
                root=root,
                missions=store.load_missions(),
                workspaces=store.load_workspaces(),
                stale_minutes=60,
            )

            self.assertNotIn(
                "stale_runtime_heartbeat",
                {item["kind"] for item in report["issues"]},
            )

    def test_mission_watchdog_flags_stale_running_mission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep ongoing work alive",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "running"
            mission.state.remaining_runtime_seconds = 1200
            old = datetime.now(timezone.utc) - timedelta(minutes=75)
            mission.updated_at = old.isoformat()
            store.save_missions([mission])

            report = build_mission_watchdog_report(
                root=root,
                missions=store.load_missions(),
                workspaces=store.load_workspaces(),
                stale_minutes=30,
                now=datetime.now(timezone.utc),
            )

            self.assertIn(
                "stale_running_mission",
                {item["kind"] for item in report["issues"]},
            )
            self.assertEqual(report["summary"]["warn"], 1)

    def test_mission_watchdog_flags_dead_active_delegated_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep a live delegated lane honest",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "running"
            mission.state.remaining_runtime_seconds = 1200
            mission.delegated_runtime_sessions = [
                DelegatedRuntimeSession(
                    delegated_id="delegate_dead",
                    runtime_id="hermes",
                    launch_command="hermes chat",
                    status="running",
                    pid=99999999,
                    heartbeat_status="healthy",
                    heartbeat_age_seconds=5,
                )
            ]
            store.save_missions([mission])

            report = build_mission_watchdog_report(
                root=root,
                missions=store.load_missions(),
                workspaces=store.load_workspaces(),
                stale_minutes=60,
            )

            issue = next(
                item
                for item in report["issues"]
                if item["kind"] == "delegated_runtime_process_gone"
            )
            self.assertEqual(issue["severity"], "bad")
            self.assertIn("delegate_dead", issue["evidence"][0])
            self.assertIn("--action resume", issue["firstStep"])

    def test_mission_watchdog_uses_terminal_session_file_before_dead_pid_alarm(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Do not relaunch a delegate that already completed",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "running"
            mission.state.remaining_runtime_seconds = 1200
            session_path = root / ".agent_control" / "runtime_sessions" / "delegate_completed.json"
            session_path.parent.mkdir(parents=True)
            stale_embedded = DelegatedRuntimeSession(
                delegated_id="delegate_completed",
                runtime_id="hermes",
                launch_command="hermes chat",
                status="running",
                session_path=str(session_path),
                pid=99999999,
                heartbeat_status="healthy",
                heartbeat_age_seconds=5,
            )
            completed_file = DelegatedRuntimeSession(
                delegated_id="delegate_completed",
                runtime_id="hermes",
                launch_command="hermes chat",
                status="completed",
                detail="Delegated runtime process completed.",
                session_path=str(session_path),
                pid=99999999,
                exit_code=0,
                acknowledged=True,
            )
            session_path.write_text(json.dumps(asdict(completed_file), indent=2), encoding="utf-8")
            mission.delegated_runtime_sessions = [stale_embedded]
            store.save_missions([mission])

            report = build_mission_watchdog_report(
                root=root,
                missions=store.load_missions(),
                workspaces=store.load_workspaces(),
                stale_minutes=60,
            )

            kinds = {item["kind"] for item in report["issues"]}
            self.assertNotIn("delegated_runtime_process_gone", kinds)
            self.assertNotIn("delegated_runtime_completed_unreconciled", kinds)

    def test_mission_watchdog_ignores_dead_historical_delegate_when_newer_lane_is_live(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep only the latest active delegated lane actionable",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "running"
            mission.state.remaining_runtime_seconds = 1200
            old = datetime.now(timezone.utc) - timedelta(minutes=5)
            mission.delegated_runtime_sessions = [
                DelegatedRuntimeSession(
                    delegated_id="delegate_old_dead",
                    runtime_id="hermes",
                    launch_command="hermes chat",
                    status="running",
                    pid=99999999,
                    updated_at=old.isoformat(),
                    heartbeat_status="stale",
                    heartbeat_age_seconds=300,
                ),
                DelegatedRuntimeSession(
                    delegated_id="delegate_current_live",
                    runtime_id="hermes",
                    launch_command="hermes chat",
                    status="running",
                    pid=os.getpid(),
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    heartbeat_status="healthy",
                    heartbeat_age_seconds=2,
                ),
            ]
            store.save_missions([mission])

            report = build_mission_watchdog_report(
                root=root,
                missions=store.load_missions(),
                workspaces=store.load_workspaces(),
                stale_minutes=60,
            )

            self.assertNotIn(
                "delegated_runtime_process_gone",
                {item["kind"] for item in report["issues"]},
            )

    def test_mission_watchdog_flags_unreconciled_completed_delegate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Move completed delegated output into verification",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "running"
            mission.state.remaining_runtime_seconds = 1200
            mission.delegated_runtime_sessions = [
                DelegatedRuntimeSession(
                    delegated_id="delegate_done",
                    runtime_id="hermes",
                    launch_command="hermes chat",
                    status="completed",
                    exit_code=0,
                    acknowledged=False,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
            ]
            store.save_missions([mission])

            report = build_mission_watchdog_report(
                root=root,
                missions=store.load_missions(),
                workspaces=store.load_workspaces(),
                stale_minutes=60,
            )

            issue = next(
                item
                for item in report["issues"]
                if item["kind"] == "delegated_runtime_completed_unreconciled"
            )
            self.assertEqual(issue["severity"], "bad")
            self.assertIn("delegate_done", issue["evidence"][0])
            self.assertIn("--action resume", issue["firstStep"])

    def test_mission_watchdog_flags_runtime_cycle_state_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Catch completed event mismatch",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "running"
            mission.state.remaining_runtime_seconds = 1200
            store.update_mission(mission)
            store.append_event(
                MissionEvent(
                    mission_id=mission.mission_id,
                    kind="mission.runtime_cycle",
                    message="hermes control cycle finished with status completed.",
                    metadata={
                        "sessionId": "session_done",
                        "autopilotStatus": "completed",
                        "pauseReason": "",
                    },
                )
            )

            report = build_mission_watchdog_report(
                root=root,
                missions=store.load_missions(),
                workspaces=store.load_workspaces(),
                stale_minutes=60,
            )

            issue = next(
                item
                for item in report["issues"]
                if item["kind"] == "runtime_cycle_state_mismatch"
            )
            self.assertEqual(issue["severity"], "bad")
            self.assertIn("--action complete", issue["firstStep"])

    def test_mission_watchdog_flags_active_row_with_idle_planner_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Continue a route-trust sample that stopped dispatching",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "running"
            mission.state.planner_loop_status = "idle"
            mission.planner_loop_status = "idle"
            mission.state.remaining_runtime_seconds = 1200
            store.update_mission(mission)

            report = build_mission_watchdog_report(
                root=root,
                missions=store.load_missions(),
                workspaces=store.load_workspaces(),
                stale_minutes=60,
            )

            issue = next(
                item
                for item in report["issues"]
                if item["kind"] == "running_planner_loop_idle"
            )
            self.assertEqual(issue["severity"], "warn")
            self.assertIn("--action resume", issue["firstStep"])
            self.assertIn("plannerLoopStatus=idle", issue["evidence"])

    def test_mission_watchdog_flags_long_running_workspace_queue_pressure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            active = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build a large investigation suite",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )
            active.state.status = "running"
            active.state.remaining_runtime_seconds = 36000
            stale_at = (datetime.now(timezone.utc) - timedelta(minutes=130)).isoformat()
            active.created_at = stale_at
            store.update_mission(active)
            missions = store.load_missions()
            for item in missions:
                if item.mission_id == active.mission_id:
                    item.updated_at = stale_at
            store.save_missions(missions)
            queued = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build an F1 analytics prototype",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )

            report = build_mission_watchdog_report(
                root=root,
                missions=store.load_missions(),
                workspaces=store.load_workspaces(),
                stale_minutes=60,
                now=datetime.now(timezone.utc),
            )

            issue = next(
                item
                for item in report["issues"]
                if item["kind"] == "workspace_queue_pressure"
            )
            self.assertEqual(issue["missionId"], queued.mission_id)
            self.assertEqual(issue["scopeSafety"], "unknown")
            self.assertIn("Collect file-scope evidence", issue["firstStep"])
            self.assertNotIn("--action parallelize-worktree", issue["firstStep"])
            self.assertEqual(report["summary"]["queuePressure"], 1)
            self.assertEqual(report["summary"]["queuePressureUnknown"], 1)

    def test_mission_watchdog_does_not_report_queue_pressure_after_recent_blocker_movement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            active = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Resume a long-running Hermes proof",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )
            active.state.status = "running"
            active.state.remaining_runtime_seconds = 36000
            active.created_at = (
                datetime.now(timezone.utc) - timedelta(minutes=130)
            ).isoformat()
            store.update_mission(active)
            store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Queued follow-up behind fresh active work",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )

            report = build_mission_watchdog_report(
                root=root,
                missions=store.load_missions(),
                workspaces=store.load_workspaces(),
                stale_minutes=60,
                now=datetime.now(timezone.utc),
            )

            self.assertNotIn(
                "workspace_queue_pressure",
                {item["kind"] for item in report["issues"]},
            )
            self.assertEqual(report["summary"]["queuePressure"], 0)

    def test_mission_watchdog_allows_parallel_worktree_when_file_scopes_are_disjoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            active = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Improve mobile notifications",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )
            active.state.status = "running"
            active.state.remaining_runtime_seconds = 36000
            stale_at = (datetime.now(timezone.utc) - timedelta(minutes=130)).isoformat()
            active.created_at = stale_at
            active.proof.changed_files = ["web/src/notifications/NotificationStack.jsx"]
            store.update_mission(active)
            missions = store.load_missions()
            for item in missions:
                if item.mission_id == active.mission_id:
                    item.updated_at = stale_at
            store.save_missions(missions)
            queued = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build an F1 analytics prototype",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )
            queued.proof.changed_files = ["apps/f1-analytics/dashboard.tsx"]
            store.update_mission(queued)

            report = build_mission_watchdog_report(
                root=root,
                missions=store.load_missions(),
                workspaces=store.load_workspaces(),
                stale_minutes=60,
                now=datetime.now(timezone.utc),
            )

            issue = next(
                item
                for item in report["issues"]
                if item["kind"] == "workspace_queue_pressure"
            )
            self.assertEqual(issue["missionId"], queued.mission_id)
            self.assertEqual(issue["scopeSafety"], "safe")
            self.assertEqual(issue["scopeEvidence"]["activeFileCount"], 1)
            self.assertEqual(issue["scopeEvidence"]["queuedFileCount"], 1)
            self.assertEqual(issue["scopeEvidence"]["overlapFiles"], [])
            self.assertIn("isolated_worktree", issue["firstStep"])
            self.assertIn("--action parallelize-worktree", issue["firstStep"])
            self.assertEqual(report["summary"]["queuePressureSafe"], 1)

    def test_mission_watchdog_uses_planned_file_scope_from_objective(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            active = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build the GEOINT prototype under /projects/lab/geoint-maritime-suite.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )
            active.state.status = "running"
            active.state.remaining_runtime_seconds = 36000
            stale_at = (datetime.now(timezone.utc) - timedelta(minutes=130)).isoformat()
            active.created_at = stale_at
            store.update_mission(active)
            missions = store.load_missions()
            for item in missions:
                if item.mission_id == active.mission_id:
                    item.updated_at = stale_at
            store.save_missions(missions)
            queued = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build the F1 workbench under /projects/lab/f1-telemetry-workbench.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )

            report = build_mission_watchdog_report(
                root=root,
                missions=store.load_missions(),
                workspaces=store.load_workspaces(),
                stale_minutes=60,
                now=datetime.now(timezone.utc),
            )

            issue = next(
                item
                for item in report["issues"]
                if item["kind"] == "workspace_queue_pressure"
            )
            self.assertEqual(issue["missionId"], queued.mission_id)
            self.assertEqual(issue["scopeSafety"], "safe")
            self.assertIn("projects/lab/geoint-maritime-suite", issue["scopeEvidence"]["activeSamples"])
            self.assertIn("projects/lab/f1-telemetry-workbench", issue["scopeEvidence"]["queuedSamples"])
            self.assertIn("--action parallelize-worktree", issue["firstStep"])

    def test_mission_summary_includes_planned_scope_artifact_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            artifact_dir = root / "overnight-discovery-lab" / "f1-telemetry-workbench"
            artifact_dir.mkdir(parents=True)
            (artifact_dir / "README.md").write_text("# F1 telemetry workbench\n", encoding="utf-8")
            (artifact_dir / "index.html").write_text("<main>ready</main>\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build the F1 workbench.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )
            mission.planned_file_scope = [str(artifact_dir)]
            mission.state.status = "completed"
            store.update_mission(mission)

            snapshot = store.build_summary_snapshot()
            row = next(item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id)
            artifacts = row["plannedScopeArtifacts"]

            self.assertEqual(artifacts["status"], "ready")
            self.assertEqual(artifacts["scopeCount"], 1)
            self.assertEqual(artifacts["readyCount"], 1)
            self.assertEqual(artifacts["readmeCount"], 1)
            self.assertEqual(artifacts["previewableCount"], 1)
            self.assertEqual(artifacts["entries"][0]["fileCount"], 2)

    def test_summary_digest_exposes_public_launch_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            evidence_dir = root / ".agent_control" / "public_launch_readiness"
            evidence_dir.mkdir(parents=True)
            (evidence_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.public_launch_readiness.v1",
                        "ok": False,
                        "status": "public_packet_ready_missing_current_web_and_publication",
                        "internalPacketReady": True,
                        "missing": ["public_web_current", "external_publication_proven"],
                        "blockers": [
                            {
                                "checkId": "public_web_current",
                                "details": "Public web receipt must point at the current source state.",
                            },
                            {
                                "checkId": "external_publication_proven",
                                "details": "Publication proof is required.",
                            },
                        ],
                        "publicWeb": {
                            "sourceDirtyPathCount": 3,
                            "sourceDirtyPathSample": [" M README.md"],
                            "dirtySourceTriage": {
                                "schema": "fluxio.public_launch_dirty_source_triage.v1",
                                "releaseBlockingSampleCount": 1,
                                "laneCounts": {"docs": 1},
                                "nextAction": "Commit/push/deploy release-impacting source changes.",
                            },
                        },
                        "publicationProof": {
                            "nextAction": "Attach publication proof.",
                        },
                        "nextAction": "Publish current source and add publication proof.",
                    }
                ),
                encoding="utf-8",
            )
            store = ControlRoomStore(root)

            summary = store.build_summary_snapshot()
            public_launch = summary["systemAuditDigest"]["publicLaunchReadiness"]

            self.assertEqual(
                public_launch["status"],
                "public_packet_ready_missing_current_web_and_publication",
            )
            self.assertTrue(public_launch["internalPacketReady"])
            self.assertEqual(
                public_launch["missing"],
                ["public_web_current", "external_publication_proven"],
            )
            self.assertEqual(public_launch["blockers"][0]["checkId"], "public_web_current")
            self.assertEqual(public_launch["publicWeb"]["sourceDirtyPathSample"], [" M README.md"])
            self.assertEqual(
                public_launch["publicWeb"]["dirtySourceTriage"]["releaseBlockingSampleCount"],
                1,
            )
            self.assertEqual(public_launch["publicationProof"]["nextAction"], "Attach publication proof.")

    def test_summary_digest_preserves_public_launch_repair_packet_operator_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            evidence_dir = root / ".agent_control" / "public_launch_readiness"
            evidence_dir.mkdir(parents=True)
            (evidence_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.public_launch_readiness.v1",
                        "ok": True,
                        "status": "ready_for_public_launch",
                        "internalPacketReady": True,
                        "missing": [],
                        "blockers": [],
                        "repairPacket": {
                            "schema": "fluxio.public_launch_repair_packet.v1",
                            "status": "ready_for_public_launch",
                            "canClaimPublicLaunch": True,
                            "sourceCoverage": "full_git_status",
                            "releaseBlockingPathCount": 0,
                            "nextAction": "Keep public launch receipts current.",
                            "orderedLanes": [
                                {
                                    "lane": "verifier",
                                    "count": 2,
                                    "nextAction": "Rerun public launch verifiers.",
                                }
                            ],
                            "commands": [
                                {
                                    "label": "Final public launch readiness check",
                                    "command": "npm run verify:public-launch",
                                }
                            ],
                            "receiptTargets": [
                                {
                                    "label": "Public launch receipt",
                                    "path": ".agent_control/public_launch_readiness/latest.json",
                                }
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )
            store = ControlRoomStore(root)

            summary = store.build_summary_snapshot()
            repair_packet = summary["systemAuditDigest"]["publicLaunchReadiness"]["repairPacket"]

            self.assertEqual(repair_packet["orderedLanes"][0]["lane"], "verifier")
            self.assertEqual(
                repair_packet["commands"][0]["command"],
                "npm run verify:public-launch",
            )
            self.assertEqual(
                repair_packet["receiptTargets"][0]["path"],
                ".agent_control/public_launch_readiness/latest.json",
            )

    def test_public_launch_digest_prefers_fresher_readiness_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            evidence_dir = root / ".agent_control" / "public_launch_readiness"
            evidence_dir.mkdir(parents=True)
            (evidence_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.public_launch_readiness.v1",
                        "checkedAt": "2026-05-30T10:20:00+00:00",
                        "ok": False,
                        "status": "public_packet_ready_missing_current_web_and_publication",
                        "internalPacketReady": True,
                        "missing": ["public_web_current"],
                        "blockers": [],
                        "publicWeb": {
                            "sourceDirtyPathSample": [" M fresh.py"],
                        },
                    }
                ),
                encoding="utf-8",
            )

            digest = mission_control_module._public_launch_readiness_digest(
                root,
                {
                    "schema": "fluxio.public_launch_readiness.v1",
                    "checkedAt": "2026-05-30T09:00:00+00:00",
                    "ok": False,
                    "status": "stale",
                    "internalPacketReady": True,
                    "missing": ["external_publication_proven"],
                    "blockers": [],
                    "publicWeb": {
                        "sourceDirtyPathSample": [" M stale.py"],
                    },
                },
            )

            self.assertEqual(digest["status"], "public_packet_ready_missing_current_web_and_publication")
            self.assertEqual(digest["publicWeb"]["sourceDirtyPathSample"], [" M fresh.py"])

    def test_mission_watchdog_flags_completed_missing_planned_scope_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build the RF hidden-world explorer.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )
            mission.planned_file_scope = [str(root / "missing-rf-explorer")]
            mission.state.status = "completed"
            store.update_mission(mission)

            report = build_mission_watchdog_report(
                root=root,
                missions=store.load_missions(),
                workspaces=store.load_workspaces(),
                stale_minutes=60,
                now=datetime.now(timezone.utc),
            )

            issue = next(
                item
                for item in report["issues"]
                if item["kind"] == "planned_scope_artifacts_not_ready"
            )
            self.assertEqual(issue["severity"], "bad")
            self.assertEqual(issue["artifactReadiness"]["status"], "missing")
            self.assertEqual(report["summary"]["artifactMissing"], 1)

    def test_mission_watchdog_ignores_stale_non_artifact_scope_when_output_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            artifact_dir = root / "solantir-mindtower-fusion"
            artifact_dir.mkdir()
            (artifact_dir / "README.md").write_text("# Fusion output\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build the fusion workspace.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )
            mission.planned_file_scope = [
                str(artifact_dir),
                "tests/build/smoke",
                "/volume1/Saclay/projects/Projects/Solantir",
            ]
            mission.state.status = "completed"
            store.update_mission(mission)

            report = build_mission_watchdog_report(
                root=root,
                missions=store.load_missions(),
                workspaces=store.load_workspaces(),
                stale_minutes=60,
                now=datetime.now(timezone.utc),
            )
            readiness = report["artifactReadiness"][mission.mission_id]

            self.assertEqual(readiness["status"], "ready")
            self.assertEqual(readiness["scopeCount"], 1)
            self.assertEqual(readiness["rawScopeCount"], 3)
            self.assertEqual(readiness["ignoredCount"], 2)
            self.assertEqual(report["summary"]["artifactReady"], 1)
            self.assertNotIn(
                "planned_scope_artifacts_not_ready",
                {item["kind"] for item in report["issues"]},
            )

    def test_mission_watchdog_blocks_parallel_worktree_when_file_scopes_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            active = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Improve the Builder watchdog panel",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )
            active.state.status = "running"
            active.state.remaining_runtime_seconds = 36000
            stale_at = (datetime.now(timezone.utc) - timedelta(minutes=130)).isoformat()
            active.created_at = stale_at
            active.proof.changed_files = ["web/src/fluxio/FluxioShell.jsx"]
            store.update_mission(active)
            missions = store.load_missions()
            for item in missions:
                if item.mission_id == active.mission_id:
                    item.updated_at = stale_at
            store.save_missions(missions)
            queued = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Tune the same Builder watchdog panel",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=43200,
            )
            queued.proof.changed_files = ["web/src/fluxio/FluxioShell.jsx"]
            queued.state.stop_reason = "artifact_gate_failed"
            queued.proof.blocked_by = [
                "Hard artifact gate failed: no concrete runtime-output body or served artifact was recorded."
            ]
            store.update_mission(queued)

            report = build_mission_watchdog_report(
                root=root,
                missions=store.load_missions(),
                workspaces=store.load_workspaces(),
                stale_minutes=60,
                now=datetime.now(timezone.utc),
            )

            issue = next(
                item
                for item in report["issues"]
                if item["kind"] == "workspace_queue_pressure"
            )
            self.assertEqual(issue["scopeSafety"], "overlap")
            self.assertEqual(issue["scopeEvidence"]["overlapFiles"], ["web/src/fluxio/fluxioshell.jsx"])
            self.assertIn("Do not parallelize automatically", issue["firstStep"])
            self.assertIn("plan_mission_artifact_repairs.py", issue["firstStep"])
            self.assertIn("--action resume --launch-async", issue["firstStep"])
            self.assertNotIn("--action parallelize-worktree", issue["firstStep"])
            self.assertEqual(report["summary"]["queuePressureOverlap"], 1)

    def test_infer_planned_file_scope_extracts_artifact_directory(self) -> None:
        self.assertEqual(
            infer_planned_file_scope(
                "Put all artifacts under /volume1/Saclay/projects/overnight-discovery-lab/f1-telemetry-workbench.",
                [],
            ),
            ["/volume1/Saclay/projects/overnight-discovery-lab/f1-telemetry-workbench"],
        )

    def test_infer_planned_file_scope_prefers_fusion_workspace_over_sources(self) -> None:
        objective = """Source projects:
- Solantir source: `/volume1/Saclay/projects/Projects/Solantír`
- Mind Tower source: `/volume1/Saclay/projects/mind-tower`
- Fusion workspace: `/volume1/Saclay/projects/solantir-mindtower-fusion`

Run available tests/build/smoke checks and record proof artifacts.
"""

        self.assertEqual(
            infer_planned_file_scope(objective, []),
            ["/volume1/Saclay/projects/solantir-mindtower-fusion"],
        )

    def test_empty_workspace_store_falls_back_to_default_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True)
            (control_dir / "workspaces.json").write_text("", encoding="utf-8")

            workspaces = ControlRoomStore(root).load_workspaces()

            self.assertEqual(len(workspaces), 1)
            saved = json.loads((control_dir / "workspaces.json").read_text(encoding="utf-8"))
            self.assertEqual(saved[0]["workspace_id"], workspaces[0].workspace_id)

    def test_invalid_workspace_store_falls_back_to_default_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True)
            (control_dir / "workspaces.json").write_text("{", encoding="utf-8")

            workspaces = ControlRoomStore(root).load_workspaces()

            self.assertEqual(len(workspaces), 1)
            saved = json.loads((control_dir / "workspaces.json").read_text(encoding="utf-8"))
            self.assertEqual(saved[0]["workspace_id"], workspaces[0].workspace_id)

    def test_workspace_store_reanchors_old_release_root_to_current_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            releases_root = pathlib.Path(temp_dir) / "syntelos" / "releases"
            old_release = releases_root / "20260430-165341"
            new_release = releases_root / "20260505-212517"
            old_release.mkdir(parents=True, exist_ok=True)
            new_release.mkdir(parents=True, exist_ok=True)
            (old_release / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            (new_release / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

            store = ControlRoomStore(new_release)
            control_dir = new_release / ".agent_control"
            workspace = asdict(store._default_workspace_profile())  # noqa: SLF001 - test fixture
            workspace["root_path"] = str(old_release)
            (control_dir / "workspaces.json").write_text(json.dumps([workspace], indent=2), encoding="utf-8")

            loaded = store.load_workspaces()

            self.assertEqual(loaded[0].root_path, str(new_release))
            saved = json.loads((control_dir / "workspaces.json").read_text(encoding="utf-8"))
            self.assertEqual(saved[0]["root_path"], str(new_release))

    def test_workspace_store_keeps_non_release_roots_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir) / "syntelos"
            root.mkdir(parents=True, exist_ok=True)
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            external_root = pathlib.Path(temp_dir) / "other_project"
            external_root.mkdir(parents=True, exist_ok=True)

            store = ControlRoomStore(root)
            control_dir = root / ".agent_control"
            workspace = asdict(store._default_workspace_profile())  # noqa: SLF001 - test fixture
            workspace["root_path"] = str(external_root)
            (control_dir / "workspaces.json").write_text(json.dumps([workspace], indent=2), encoding="utf-8")

            loaded = store.load_workspaces()

            self.assertEqual(loaded[0].root_path, str(external_root))

    def test_generated_image_artifact_snapshot_includes_direct_images_without_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            artifact_dir = root / ".agent_control" / "generated_image_artifacts"
            artifact_dir.mkdir(parents=True)
            image = artifact_dir / "direct-output.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n" + (b"0" * 1024))

            snapshot = _build_generated_image_artifacts_snapshot(root)

            self.assertEqual(snapshot["summary"]["total"], 1)
            item = snapshot["items"][0]
            self.assertEqual(item["artifactId"], "direct-output")
            self.assertIn("/api/artifact?id=", item["previewUrl"])
            self.assertEqual(item["source"], "generated_image_artifact_file")

    def test_recover_evidence_path_extracts_embedded_windows_runtime_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            runtime_dir = root / ".agent_control" / "runtime_sessions"
            runtime_dir.mkdir(parents=True)
            evidence = runtime_dir / "delegate.events.jsonl"
            evidence.write_text('{"kind":"runtime.output"}\n', encoding="utf-8")
            if not evidence.drive:
                self.skipTest("Embedded Windows-path recovery is Windows-specific.")
            malformed = f"/mnt/c/Users/paul/Projects/demo/{evidence}"

            self.assertEqual(_recover_evidence_path(root, malformed), evidence.resolve())

    def test_mission_evidence_windows_path_translates_for_wsl(self) -> None:
        with mock.patch("grant_agent.mission_control.os.name", "posix"):
            self.assertEqual(
                str(_platform_path_for_windows_drive(r"C:\volume1\Saclay\evidence.log")),
                "/mnt/c/volume1/Saclay/evidence.log",
            )

    def test_delete_workspace_removes_scoped_missions_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            secondary_root = root / "secondary"
            secondary_root.mkdir(parents=True, exist_ok=True)

            store = ControlRoomStore(root)
            primary = store.load_workspaces()[0]
            secondary = store.upsert_workspace(
                name="Secondary",
                root_path=str(secondary_root),
                default_runtime="openclaw",
                user_profile="builder",
            )
            mission = store.create_mission(
                workspace_id=secondary.workspace_id,
                runtime_id="openclaw",
                objective="Secondary workspace mission",
                success_checks=[],
                mode="Autopilot",
                verification_commands=["python -m unittest"],
                max_runtime_seconds=1800,
            )
            store.append_workspace_action(
                secondary.workspace_id,
                {
                    "actionId": "validate_workspace",
                    "result": {"ok": True},
                    "workspaceId": secondary.workspace_id,
                },
            )

            removed_workspace, removed_mission_count = store.delete_workspace(
                secondary.workspace_id
            )

            self.assertEqual(removed_workspace.workspace_id, secondary.workspace_id)
            self.assertEqual(removed_mission_count, 1)
            remaining_workspace_ids = {
                item.workspace_id for item in store.load_workspaces()
            }
            self.assertIn(primary.workspace_id, remaining_workspace_ids)
            self.assertNotIn(secondary.workspace_id, remaining_workspace_ids)
            remaining_mission_ids = {item.mission_id for item in store.load_missions()}
            self.assertNotIn(mission.mission_id, remaining_mission_ids)
            self.assertNotIn(secondary.workspace_id, store.load_workspace_actions())

    def test_workspace_delete_command_rejects_last_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            exit_code = cmd_workspace_delete(
                argparse.Namespace(root=str(root), workspace_id=workspace.workspace_id)
            )
            self.assertEqual(exit_code, 1)

    def test_sync_project_tree_skips_locked_files_instead_of_raising(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            source = root / "source"
            target = root / "target"
            source.mkdir(parents=True, exist_ok=True)
            target.mkdir(parents=True, exist_ok=True)
            (source / "ready.txt").write_text("ready\n", encoding="utf-8")
            (source / "locked.txt").write_text("locked\n", encoding="utf-8")
            real_copy2 = shutil.copy2

            class LockedByProcessError(PermissionError):
                def __init__(self) -> None:
                    super().__init__(13, "used by another process")
                    self.winerror = 32

            def fake_copy2(src: str | pathlib.Path, dst: str | pathlib.Path) -> str:
                if pathlib.Path(src).name == "locked.txt":
                    raise LockedByProcessError()
                return real_copy2(src, dst)

            with (
                mock.patch("grant_agent.mission_control.shutil.copy2", side_effect=fake_copy2),
                mock.patch("grant_agent.mission_control.time.sleep", return_value=None),
            ):
                status = _sync_project_tree(
                    source,
                    target,
                    conflict_policy="keep_newer_and_log",
                )

            self.assertTrue(status["synced"])
            self.assertEqual(status["reason"], "copied_with_locked_files")
            self.assertEqual(status["filesCopied"], 1)
            self.assertEqual(status["filesSkipped"], 1)
            self.assertEqual(status["lockedFilesSkipped"], 1)
            self.assertIn(str(source / "locked.txt"), status["lockedFileSamples"])
            self.assertEqual((target / "ready.txt").read_text(encoding="utf-8"), "ready\n")
            self.assertFalse((target / "locked.txt").exists())

    def test_sync_project_tree_raises_non_lock_permission_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            source = root / "source"
            target = root / "target"
            source.mkdir(parents=True, exist_ok=True)
            target.mkdir(parents=True, exist_ok=True)
            (source / "blocked.txt").write_text("blocked\n", encoding="utf-8")

            class AccessDeniedError(PermissionError):
                def __init__(self) -> None:
                    super().__init__(13, "permission denied")
                    self.winerror = 5

            with mock.patch(
                "grant_agent.mission_control.shutil.copy2",
                side_effect=AccessDeniedError(),
            ):
                with self.assertRaises(PermissionError):
                    _sync_project_tree(
                        source,
                        target,
                        conflict_policy="local_wins",
                    )

    def test_workspace_save_reconciles_local_and_nas_when_both_already_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            local_root = root / "local-project"
            nas_root = root / "nas-project"
            local_root.mkdir(parents=True, exist_ok=True)
            nas_root.mkdir(parents=True, exist_ok=True)
            (local_root / "local_only.txt").write_text("local\n", encoding="utf-8")
            (nas_root / "nas_only.txt").write_text("nas\n", encoding="utf-8")
            local_shared = local_root / "shared.txt"
            nas_shared = nas_root / "shared.txt"
            local_shared.write_text("local-old\n", encoding="utf-8")
            nas_shared.write_text("nas-new\n", encoding="utf-8")
            os.utime(local_shared, (1_700_000_000, 1_700_000_000))
            os.utime(nas_shared, (1_700_000_100, 1_700_000_100))

            store = ControlRoomStore(root)
            workspace = store.upsert_workspace(
                name="NAS Sync Workspace",
                root_path=str(local_root),
                default_runtime="openclaw",
                user_profile="builder",
                local_project_path=str(local_root),
                nas_project_path=str(nas_root),
                sync_mode="auto_nas_mirror",
                sync_direction="bidirectional",
                sync_conflict_policy="keep_newer_and_log",
                auto_sync_to_nas=True,
            )

            self.assertEqual(workspace.root_path, str(nas_root.resolve()))
            self.assertEqual((nas_root / "local_only.txt").read_text(encoding="utf-8"), "local\n")
            self.assertEqual((local_root / "nas_only.txt").read_text(encoding="utf-8"), "nas\n")
            self.assertEqual(local_shared.read_text(encoding="utf-8"), "nas-new\n")
            self.assertEqual(nas_shared.read_text(encoding="utf-8"), "nas-new\n")

            sync_goal = next(
                item for item in workspace.goals if str(item).startswith("sync_status:")
            )
            sync_status = json.loads(str(sync_goal).split(":", 1)[1])
            self.assertEqual(sync_status["effectiveDirection"], "bidirectional")
            self.assertTrue(sync_status["detectedBothWithFiles"])
            self.assertGreaterEqual(sync_status["filesCopied"], 3)
            self.assertGreaterEqual(len(sync_status["passes"]), 2)
            self.assertEqual(
                sync_status["syncReceipt"]["schema"],
                "fluxio.workspace_sync_receipt.v1",
            )
            self.assertGreaterEqual(sync_status["syncReceipt"]["conflictsDetected"], 1)
            self.assertGreaterEqual(sync_status["conflictsDetected"], 1)
            self.assertEqual(
                sync_status["conflictReceipts"][0]["schema"],
                "fluxio.sync_conflict_receipt.v1",
            )

    def test_workspace_save_bidirectional_nas_wins_updates_local_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            local_root = root / "local-project"
            nas_root = root / "nas-project"
            local_root.mkdir(parents=True, exist_ok=True)
            nas_root.mkdir(parents=True, exist_ok=True)
            shared_local = local_root / "shared.txt"
            shared_nas = nas_root / "shared.txt"
            shared_local.write_text("local-version\n", encoding="utf-8")
            shared_nas.write_text("nas-version\n", encoding="utf-8")

            store = ControlRoomStore(root)
            store.upsert_workspace(
                name="NAS Wins Workspace",
                root_path=str(local_root),
                default_runtime="openclaw",
                user_profile="builder",
                local_project_path=str(local_root),
                nas_project_path=str(nas_root),
                sync_mode="auto_nas_mirror",
                sync_direction="bidirectional",
                sync_conflict_policy="nas_wins",
                auto_sync_to_nas=True,
            )

            self.assertEqual(shared_nas.read_text(encoding="utf-8"), "nas-version\n")
            self.assertEqual(shared_local.read_text(encoding="utf-8"), "nas-version\n")

    def test_workspace_save_auto_promotes_to_bidirectional_when_both_roots_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            local_root = root / "local-project"
            nas_root = root / "nas-project"
            local_root.mkdir(parents=True, exist_ok=True)
            nas_root.mkdir(parents=True, exist_ok=True)
            (local_root / "local_only.txt").write_text("local\n", encoding="utf-8")
            (nas_root / "nas_only.txt").write_text("nas\n", encoding="utf-8")

            store = ControlRoomStore(root)
            workspace = store.upsert_workspace(
                name="Auto Promote Sync Workspace",
                root_path=str(local_root),
                default_runtime="openclaw",
                user_profile="builder",
                local_project_path=str(local_root),
                nas_project_path=str(nas_root),
                sync_mode="auto_nas_mirror",
                sync_direction="local_to_nas",
                sync_conflict_policy="keep_newer_and_log",
                auto_sync_to_nas=True,
            )

            self.assertEqual((nas_root / "local_only.txt").read_text(encoding="utf-8"), "local\n")
            self.assertEqual((local_root / "nas_only.txt").read_text(encoding="utf-8"), "nas\n")

            sync_goal = next(
                item for item in workspace.goals if str(item).startswith("sync_status:")
            )
            sync_status = json.loads(str(sync_goal).split(":", 1)[1])
            self.assertEqual(sync_status["requestedDirection"], "local_to_nas")
            self.assertEqual(sync_status["effectiveDirection"], "bidirectional")
            self.assertTrue(sync_status["directionAutoPromoted"])

    def test_sync_project_tree_records_manual_review_conflict_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            source = root / "source"
            target = root / "target"
            source.mkdir(parents=True, exist_ok=True)
            target.mkdir(parents=True, exist_ok=True)
            (source / "shared.txt").write_text("source-version-longer\n", encoding="utf-8")
            (target / "shared.txt").write_text("target-version\n", encoding="utf-8")

            status = _sync_project_tree(
                source,
                target,
                conflict_policy="manual_review",
            )

            self.assertTrue(status["synced"])
            self.assertEqual(status["reason"], "manual_review_required")
            self.assertTrue(status["manualReviewRequired"])
            self.assertEqual(status["conflictsDetected"], 1)
            self.assertEqual(
                status["syncReceipt"]["schema"],
                "fluxio.sync_conflict_receipt.v1",
            )
            self.assertTrue(status["syncReceipt"]["manualReviewRequired"])
            self.assertEqual(
                status["syncReceipt"]["conflictSamples"][0]["resolution"],
                "manual_review_required",
            )
            self.assertEqual(
                (target / "shared.txt").read_text(encoding="utf-8"),
                "target-version\n",
            )

    def test_resolve_workspace_sync_conflict_records_resolution_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            local_root = root / "local-project"
            nas_root = root / "nas-project"
            local_root.mkdir(parents=True, exist_ok=True)
            nas_root.mkdir(parents=True, exist_ok=True)
            (local_root / "shared.txt").write_text("local-version\n", encoding="utf-8")
            (nas_root / "shared.txt").write_text("nas-version\n", encoding="utf-8")

            store = ControlRoomStore(root)
            workspace = store.upsert_workspace(
                name="Manual Review Workspace",
                root_path=str(local_root),
                default_runtime="openclaw",
                user_profile="builder",
                local_project_path=str(local_root),
                nas_project_path=str(nas_root),
                sync_mode="auto_nas_mirror",
                sync_direction="local_to_nas",
                sync_conflict_policy="manual_review",
                auto_sync_to_nas=True,
            )
            self.assertEqual((nas_root / "shared.txt").read_text(encoding="utf-8"), "nas-version\n")

            receipt = resolve_workspace_sync_conflict(
                store=store,
                workspace_id=workspace.workspace_id,
                relative_path="shared.txt",
                resolution="local_wins",
            )

            self.assertEqual(receipt["schema"], "fluxio.sync_conflict_resolution_receipt.v1")
            self.assertEqual(receipt["status"], "resolved")
            self.assertTrue(receipt["copied"])
            self.assertEqual((nas_root / "shared.txt").read_text(encoding="utf-8"), "local-version\n")
            refreshed = store.get_workspace(workspace.workspace_id)
            self.assertTrue(
                any(
                    str(item).startswith("sync_conflict_resolution:")
                    for item in (refreshed.goals if refreshed else [])
                )
            )

    def test_resolve_workspace_sync_conflict_batch_records_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            local_root = root / "local-project"
            nas_root = root / "nas-project"
            local_root.mkdir(parents=True, exist_ok=True)
            nas_root.mkdir(parents=True, exist_ok=True)
            for name in ("alpha.txt", "beta.txt"):
                (local_root / name).write_text(f"local-{name}\n", encoding="utf-8")
                (nas_root / name).write_text(f"nas-{name}\n", encoding="utf-8")

            store = ControlRoomStore(root)
            workspace = store.upsert_workspace(
                name="Batch Manual Review Workspace",
                root_path=str(local_root),
                default_runtime="openclaw",
                user_profile="builder",
                local_project_path=str(local_root),
                nas_project_path=str(nas_root),
                sync_mode="auto_nas_mirror",
                sync_direction="local_to_nas",
                sync_conflict_policy="manual_review",
                auto_sync_to_nas=True,
            )

            receipt = resolve_workspace_sync_conflict_batch(
                store=store,
                workspace_id=workspace.workspace_id,
                relative_paths=["alpha.txt", "beta.txt"],
                resolution="local_wins",
            )

            self.assertEqual(receipt["schema"], "fluxio.sync_conflict_batch_resolution_receipt.v1")
            self.assertEqual(receipt["status"], "resolved")
            self.assertEqual(receipt["requestedCount"], 2)
            self.assertEqual(receipt["resolvedCount"], 2)
            self.assertEqual(len(receipt["receiptIds"]), 2)
            self.assertEqual((nas_root / "alpha.txt").read_text(encoding="utf-8"), "local-alpha.txt\n")
            self.assertEqual((nas_root / "beta.txt").read_text(encoding="utf-8"), "local-beta.txt\n")
            refreshed = store.get_workspace(workspace.workspace_id)
            goals = refreshed.goals if refreshed else []
            self.assertTrue(any(str(item).startswith("sync_conflict_resolution:") for item in goals))
            self.assertTrue(any(str(item).startswith("sync_conflict_batch_resolution:") for item in goals))

    def test_cli_mission_follow_up_records_thread_and_runtime_lane(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep operator follow-ups inside the mission conversation",
                success_checks=[],
                mode="Autopilot",
                verification_commands=["python -m unittest"],
                max_runtime_seconds=3600,
            )
            runtime_dir = root / ".agent_control" / "runtime_sessions"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            session_path = runtime_dir / "delegate_follow_up.json"
            session = DelegatedRuntimeSession(
                delegated_id="delegate_follow_up",
                runtime_id="hermes",
                launch_command="hermes chat -q demo -Q",
                status="running",
                detail="Delegated runtime is active.",
                session_path=str(session_path),
                events_path=str(runtime_dir / "delegate_follow_up.events.jsonl"),
                decision_path=str(runtime_dir / "delegate_follow_up.approval.json"),
                updated_at=utc_now_iso(),
            )
            session_path.write_text(json.dumps(asdict(session), indent=2), encoding="utf-8")
            mission.delegated_runtime_sessions = [session]
            mission.state.delegated_runtime_sessions = [asdict(session)]
            store.update_mission(mission)

            with mock.patch("grant_agent.runtime_supervisor._pid_alive", return_value=True):
                exit_code = cmd_mission_follow_up(
                    argparse.Namespace(
                        root=str(root),
                        mission_id=mission.mission_id,
                        message="Please keep me updated on the next runtime checkpoint.",
                    )
                )
            self.assertEqual(exit_code, 0)

            snapshot = store.build_snapshot()
            mission_payload = next(
                item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id
            )
            self.assertEqual(
                mission_payload["state"]["last_runtime_event"],
                "Please keep me updated on the next runtime checkpoint.",
            )
            self.assertEqual(
                mission_payload["delegated_runtime_sessions"][0]["latest_events"][-1]["kind"],
                "operator.followup",
            )
            recent_event = store.recent_events(limit=1)[0]
            self.assertEqual(recent_event["kind"], "mission.follow_up")
            self.assertEqual(
                recent_event["message"],
                "Please keep me updated on the next runtime checkpoint.",
            )

    def test_recent_events_reads_only_tail_rows_in_newest_first_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            store = ControlRoomStore(root)
            store.events_path.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "mission_id": f"mission_{index % 3}",
                            "kind": f"event.{index}",
                            "message": f"message {index}",
                            "timestamp": f"2026-05-30T00:{index % 60:02d}:00Z",
                        }
                    )
                    for index in range(250)
                )
                + "\n",
                encoding="utf-8",
            )

            events = store.recent_events(limit=5)

            self.assertEqual([item["kind"] for item in events], [f"event.{index}" for index in range(249, 244, -1)])

    def test_store_creates_default_workspace_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            (root / "src-tauri").mkdir()

            store = ControlRoomStore(root)
            snapshot = store.build_snapshot()

            self.assertEqual(len(snapshot["workspaces"]), 1)
            self.assertEqual(snapshot["workspaces"][0]["default_runtime"], "hermes")
            self.assertEqual(snapshot["workspaces"][0]["workspace_type"], "tauri-python")
            self.assertEqual(snapshot["workspaces"][0]["preferred_harness"], "fluxio_hybrid")
            self.assertEqual(snapshot["workspaces"][0]["routing_strategy"], "profile_default")
            self.assertEqual(snapshot["workspaces"][0]["route_overrides"], [])
            self.assertFalse(snapshot["workspaces"][0]["auto_optimize_routing"])
            self.assertEqual(snapshot["workspaces"][0]["minimax_auth_mode"], "none")
            self.assertEqual(snapshot["workspaces"][0]["commit_message_style"], "scoped")
            self.assertEqual(
                snapshot["workspaces"][0]["execution_target_preference"],
                "profile_default",
            )
            self.assertIn("profiles", snapshot)
            self.assertIn("skillLibrary", snapshot)
            self.assertIn("harnessLab", snapshot)
            self.assertIn("parityMatrix", snapshot["harnessLab"])
            self.assertEqual(
                snapshot["harnessLab"]["routeTrustCoverage"]["schema"],
                "fluxio.route_trust_coverage.v1",
            )
            self.assertIn("nextSamplingPlan", snapshot["harnessLab"]["routeTrustCoverage"])
            sampling_plan = snapshot["harnessLab"]["routeTrustCoverage"]["nextSamplingPlan"]
            self.assertGreaterEqual(len(sampling_plan), 1)
            self.assertEqual(
                sampling_plan[0]["schema"],
                "fluxio.route_trust_sampling_template.v1",
            )
            self.assertIn("sampleMissionObjective", sampling_plan[0])
            self.assertIn("sampleMissionSuccessChecks", sampling_plan[0])
            self.assertIn("sampleMissionUrlPath", sampling_plan[0])
            self.assertIn("sampleMissionCliCommand", sampling_plan[0])
            self.assertIn("successCheck=", sampling_plan[0]["sampleMissionUrlPath"])
            self.assertIn("mission-quickstart", sampling_plan[0]["sampleMissionCliCommand"])
            self.assertIn("operatorConfidenceScore", snapshot["harnessLab"]["routeTrustCoverage"])
            self.assertIn("repairPlanStatus", snapshot["harnessLab"]["routeTrustCoverage"])
            self.assertIn("activeSamplingMissionCount", snapshot["harnessLab"]["routeTrustCoverage"])
            self.assertIn("beginnerGuidance", snapshot["harnessLab"])
            self.assertGreaterEqual(len(snapshot["harnessLab"]["parityMatrix"]), 6)
            self.assertIn("bridgeLab", snapshot)
            self.assertIn("storageBridge", snapshot)
            self.assertIn("guidance", snapshot)
            self.assertIn("onboarding", snapshot)
            self.assertIn("ui", snapshot)
            self.assertIn("setupHealth", snapshot)
            self.assertIn("workflowStudio", snapshot)
            self.assertIn("providerSetupStatus", snapshot)
            self.assertIn("efficiencyAutotune", snapshot)
            self.assertIn("releaseReadiness", snapshot)
            self.assertIn("runtimeCompartments", snapshot)
            self.assertIn("hermesMissionEvidence", snapshot)
            self.assertIn("nasDeployReadiness", snapshot)
            self.assertIn("gitSnapshot", snapshot["workspaces"][0])
            self.assertFalse(snapshot["workspaces"][0]["gitSnapshot"]["repoDetected"])
            self.assertIn("serviceManagement", snapshot["workspaces"][0])
            self.assertIn("serviceManagementSummary", snapshot["workspaces"][0])
            self.assertGreater(len(snapshot["workspaces"][0]["serviceManagement"]), 0)
            self.assertIn(
                "serviceActions",
                snapshot["workspaces"][0]["serviceManagement"][0],
            )
            self.assertIn(
                "verifyAction",
                snapshot["workspaces"][0]["serviceManagement"][0],
            )
            self.assertIn("managementSummary", snapshot["skillLibrary"])
            self.assertIn("feedbackLoop", snapshot["skillLibrary"])
            self.assertEqual(
                snapshot["skillLibrary"]["feedbackLoop"]["cadence"],
                "mission_slice_end",
            )
            self.assertIn("serviceManagement", snapshot["setupHealth"])
            self.assertIn("minimax", snapshot["providerSetupStatus"])
            self.assertEqual(
                snapshot["providerSetupStatus"]["minimax"]["authPath"],
                "not configured",
            )
            self.assertFalse(snapshot["efficiencyAutotune"]["eligible"])
            workflow = snapshot["workflowStudio"]["recipes"][0]
            self.assertIn("reviewStatus", workflow)
            self.assertEqual(workflow["runtimeChoice"], "hermes")
            self.assertIn("serviceIds", workflow)
            self.assertIn("verificationDefaults", workflow)

    def test_route_trust_coverage_surfaces_low_value_repair_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            active = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Build a polished phone/tablet Builder progress surface",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            active.state.status = "running"
            store.update_mission(active)
            route_dir = root / ".agent_control" / "route_trust_sampling"
            route_dir.mkdir(parents=True)
            (route_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.route_trust_live_sampling_run.v1",
                        "launchedSamplingMissions": [
                            {
                                "missionId": active.mission_id,
                                "taskType": "frontend_design",
                                "runtime": "hermes",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (route_dir / "closeout_review_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.route_trust_sampling_closeout_review.v1",
                        "proposals": [
                            {
                                "missionId": "mission_failed_f1",
                                "taskType": "data_f1_analytics",
                                "missionStatus": "completed",
                                "score": 30,
                                "outcome": "not_useful",
                                "trustSignal": "deprioritize",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            coverage = store.build_snapshot()["harnessLab"]["routeTrustCoverage"]

            self.assertEqual(coverage["repairPlanStatus"], "required")
            self.assertEqual(coverage["lowValueCloseoutCount"], 1)
            self.assertEqual(coverage["activeSamplingMissionCount"], 1)
            self.assertEqual(coverage["activeSamplingMissionIds"], [active.mission_id])
            self.assertEqual(coverage["repairPlan"][0]["taskType"], "data_f1_analytics")
            self.assertIn("Codex gpt-5.5 high", coverage["repairPlan"][0]["modelPolicy"])
            self.assertTrue(coverage["nextSamplingPlan"][0]["repairRequired"])
            repair_sample = coverage["nextSamplingPlan"][0]
            self.assertEqual(repair_sample["sampleMissionTitle"], "Repair F1/data analytics route trust sample")
            self.assertIn("mission_failed_f1", repair_sample["sampleMissionObjective"])
            self.assertIn("proof digest", repair_sample["sampleMissionObjective"])
            self.assertIn("operator-value closeout", repair_sample["sampleMissionObjective"])
            self.assertTrue(
                any("previous low-value sample failed" in check for check in repair_sample["sampleMissionSuccessChecks"])
            )

    def test_route_trust_proven_requires_useful_operator_value_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            for index in range(2):
                mission = store.create_mission(
                    workspace_id=workspace.workspace_id,
                    runtime_id="hermes",
                    objective=f"Build F1 telemetry analytics prototype {index}",
                    success_checks=[],
                    mode="Autopilot",
                    verification_commands=[],
                    max_runtime_seconds=3600,
                )
                mission.state.status = "completed"
                mission.state.operator_value_feedback = {
                    "schema": "fluxio.mission_operator_value_feedback.v1",
                    "score": 30,
                    "outcome": "not_useful",
                    "trustSignal": "deprioritize",
                }
                store.update_mission(mission)

            coverage = store.build_snapshot()["harnessLab"]["routeTrustCoverage"]
            f1_row = next(
                item
                for item in coverage["taskCoverage"]
                if item["taskType"] == "data_f1_analytics"
            )

            self.assertEqual(f1_row["operatorValueSamples"], 2)
            self.assertEqual(f1_row["operatorPromoteCount"], 0)
            self.assertEqual(f1_row["operatorDeprioritizeCount"], 2)
            self.assertEqual(f1_row["usefulOperatorValueSamples"], 0)
            self.assertEqual(f1_row["lowValueOperatorSamples"], 2)
            self.assertEqual(f1_row["missingOperatorValueSamples"], 2)
            self.assertEqual(f1_row["status"], "sampling")
            self.assertNotEqual(f1_row["status"], "proven")
            self.assertIn("useful value-scored", f1_row["nextAction"])

    def test_route_trust_coverage_uses_sampling_objective_before_workspace_route_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective=ROUTE_TRUST_SAMPLE_TEMPLATES["general_coding"]["objective"],
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
                route_overrides=[
                    {
                        "role": "planner",
                        "provider": "openai-codex",
                        "model": "gpt-5.5",
                        "task_type": "frontend_design",
                    }
                ],
            )
            mission.state.status = "completed"
            mission.state.operator_value_feedback = {
                "schema": "fluxio.mission_operator_value_feedback.v1",
                "score": 92,
                "outcome": "useful",
                "trustSignal": "promote",
            }
            store.update_mission(mission)

            coverage = store.build_snapshot()["harnessLab"]["routeTrustCoverage"]
            rows = {item["taskType"]: item for item in coverage["taskCoverage"]}

            self.assertEqual(rows["general_coding"]["operatorValueSamples"], 1)
            self.assertEqual(rows["general_coding"]["usefulOperatorValueSamples"], 1)
            self.assertEqual(rows["frontend_design"]["operatorValueSamples"], 0)

    def test_summary_running_mission_progress_falls_back_to_live_activity_signals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep a Hermes mission progressing without a runtime budget denominator.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=0,
            )
            mission.state.status = "running"
            mission.state.planner_loop_status = "running"
            mission.action_history = [
                {
                    "action_id": "action_patch",
                    "proposal": {"kind": "file_patch", "title": "Patch target file"},
                    "result": {"result_summary": "File mutation completed."},
                }
            ]
            mission.delegated_runtime_sessions.append(
                DelegatedRuntimeSession(
                    delegated_id="delegate_no_budget",
                    runtime_id="hermes",
                    launch_command="python -m grant_agent.runtime_worker",
                    status="running",
                )
            )
            store.update_mission(mission)

            summary = store.build_summary_snapshot()
            row = next(item for item in summary["missions"] if item["mission_id"] == mission.mission_id)
            progress = row["liveProgress"]

            self.assertEqual(progress["schema"], "fluxio.mission_live_progress.v1")
            self.assertEqual(progress["source"], "mission_activity_signals")
            self.assertEqual(progress["label"], "Live activity progress")
            self.assertIsInstance(progress["value"], int)
            self.assertGreater(progress["value"], 0)
            self.assertEqual(progress["signalCounts"]["actions"], 1)
            self.assertEqual(progress["signalCounts"]["activeRuntimeLanes"], 3)

    def test_web_backend_summary_cache_version_tracks_live_progress_semantics(self) -> None:
        self.assertIn(
            "2026-06-01.proof_safe_progress.v2",
            (
                pathlib.Path(__file__).resolve().parents[1]
                / "src"
                / "grant_agent"
                / "web_backend.py"
            ).read_text(encoding="utf-8"),
        )

    def test_summary_failed_mission_progress_uses_proof_repair_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Do not display failed mission runtime budget as completion.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=100,
            )
            mission.state.status = "verification_failed"
            mission.state.elapsed_runtime_seconds = 99
            mission.state.remaining_runtime_seconds = 1
            mission.state.verification_failures = ["hard_artifact_gate"]
            mission.proof.failed_checks = ["Hard artifact gate failed"]
            mission.action_history = [
                {
                    "action_id": "action_patch",
                    "proposal": {"kind": "file_patch", "title": "Patch target file"},
                    "result": {"result_summary": "File mutation completed."},
                }
            ]
            store.update_mission(mission)

            summary = store.build_summary_snapshot()
            row = next(item for item in summary["missions"] if item["mission_id"] == mission.mission_id)
            progress = row["liveProgress"]

            self.assertEqual(progress["schema"], "fluxio.mission_live_progress.v1")
            self.assertEqual(progress["source"], "mission_proof_repair_readiness")
            self.assertEqual(progress["label"], "Proof repair readiness")
            self.assertEqual(progress["progressKind"], "proof_repair")
            self.assertFalse(progress["displayAsCompletion"])
            self.assertLess(progress["value"], 99)
            self.assertLessEqual(progress["value"], 64)

    def test_summary_queued_mission_progress_does_not_use_stale_runtime_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Do not display queued work as nearly complete.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=100,
            )
            mission.state.status = "queued"
            mission.state.queue_position = 4
            mission.state.elapsed_runtime_seconds = 99
            mission.state.remaining_runtime_seconds = 1
            store.update_mission(mission)

            summary = store.build_summary_snapshot()
            row = next(item for item in summary["missions"] if item["mission_id"] == mission.mission_id)
            progress = row["liveProgress"]

            self.assertEqual(progress["schema"], "fluxio.mission_live_progress.v1")
            self.assertEqual(progress["source"], "mission_activity_signals")
            self.assertEqual(progress["label"], "Queued live state")
            self.assertEqual(progress["value"], 4)
            self.assertEqual(progress["progressKind"], "runtime_progress")
            self.assertTrue(progress["displayAsCompletion"])

    def test_summary_over_budget_running_mission_is_not_completion_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Do not display exhausted runtime budget as normal completion progress.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=100,
            )
            mission.state.status = "running"
            mission.state.planner_loop_status = "running"
            mission.state.elapsed_runtime_seconds = 125
            mission.state.remaining_runtime_seconds = 0
            mission.state.time_budget_status = "running"
            store.update_mission(mission)

            summary = store.build_summary_snapshot()
            row = next(item for item in summary["missions"] if item["mission_id"] == mission.mission_id)
            progress = row["liveProgress"]

            self.assertEqual(summary["counts"]["activeMissions"], 0)
            self.assertEqual(summary["counts"]["blockedMissions"], 1)
            self.assertEqual(summary["liveControlState"]["activeMissionCount"], 0)
            self.assertEqual(summary["liveControlState"]["blockedMissionCount"], 1)
            self.assertEqual(progress["schema"], "fluxio.mission_live_progress.v1")
            self.assertEqual(progress["source"], "mission_runtime_budget_exhausted")
            self.assertEqual(progress["label"], "Runtime budget exhausted")
            self.assertEqual(progress["progressKind"], "runtime_budget_exhausted")
            self.assertFalse(progress["displayAsCompletion"])
            self.assertEqual(progress["value"], 99)
            self.assertIn("Extend the runtime budget", progress["nextAction"])

    def test_summary_over_budget_running_mission_does_not_block_next_active_slot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            exhausted = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="This stale run should not keep the active slot.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=100,
            )
            exhausted.state.status = "running"
            exhausted.state.planner_loop_status = "running"
            exhausted.state.elapsed_runtime_seconds = 360
            exhausted.state.remaining_runtime_seconds = 0
            exhausted.state.time_budget_status = "running"
            store.update_mission(exhausted)

            fresh = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="This mission should get the active workspace slot.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=600,
            )

            summary = store.build_summary_snapshot()
            workspace_row = next(
                item for item in summary["workspaces"] if item["workspace_id"] == workspace.workspace_id
            )
            exhausted_row = next(
                item for item in summary["missions"] if item["mission_id"] == exhausted.mission_id
            )
            fresh_row = next(
                item for item in summary["missions"] if item["mission_id"] == fresh.mission_id
            )

            self.assertEqual(workspace_row["activeMissionId"], fresh.mission_id)
            self.assertEqual(summary["counts"]["activeMissions"], 0)
            self.assertEqual(summary["counts"]["blockedMissions"], 1)
            self.assertEqual(exhausted_row["liveProgress"]["progressKind"], "runtime_budget_exhausted")
            self.assertNotEqual(fresh_row["liveProgress"]["progressKind"], "runtime_budget_exhausted")

    def test_summary_running_mission_with_extended_remaining_budget_is_not_exhausted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Show renewed active budget as live progress, not a stale exhaustion warning.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=100,
            )
            mission.state.status = "running"
            mission.state.planner_loop_status = "running"
            mission.state.elapsed_runtime_seconds = 125
            mission.state.remaining_runtime_seconds = 25
            mission.state.time_budget_status = "delegated_active"
            mission.delegated_runtime_sessions.append(
                DelegatedRuntimeSession(
                    delegated_id="delegate_extended_budget",
                    runtime_id="hermes",
                    launch_command="python -m grant_agent.runtime_worker",
                    status="running",
                )
            )
            store.update_mission(mission)

            summary = store.build_summary_snapshot()
            row = next(item for item in summary["missions"] if item["mission_id"] == mission.mission_id)
            progress = row["liveProgress"]

            self.assertEqual(progress["schema"], "fluxio.mission_live_progress.v1")
            self.assertEqual(progress["source"], "mission_activity_signals")
            self.assertEqual(progress["label"], "Live activity progress")
            self.assertEqual(progress["progressKind"], "runtime_progress")
            self.assertTrue(progress["displayAsCompletion"])
            self.assertEqual(progress["maxRuntimeSeconds"], 150)
            self.assertEqual(progress["remainingSeconds"], 25)
            self.assertLess(progress["value"], 99)
            self.assertNotIn("Extend the runtime budget", progress["nextAction"])

    def test_summary_fresh_running_delegated_mission_uses_activity_progress_floor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Show a newly launched runtime lane as started, not dead.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "running"
            mission.state.planner_loop_status = "running"
            mission.state.elapsed_runtime_seconds = 0
            mission.state.remaining_runtime_seconds = 3600
            mission.state.time_budget_status = "delegated_active"
            mission.delegated_runtime_sessions.append(
                DelegatedRuntimeSession(
                    delegated_id="delegate_fresh",
                    runtime_id="hermes",
                    launch_command="hermes chat -q demo",
                    status="running",
                )
            )
            store.update_mission(mission)

            summary = store.build_summary_snapshot()
            row = next(item for item in summary["missions"] if item["mission_id"] == mission.mission_id)
            progress = row["liveProgress"]

            self.assertEqual(progress["schema"], "fluxio.mission_live_progress.v1")
            self.assertEqual(progress["source"], "mission_activity_signals")
            self.assertEqual(progress["label"], "Live activity progress")
            self.assertEqual(progress["progressKind"], "runtime_progress")
            self.assertTrue(progress["displayAsCompletion"])
            self.assertGreater(progress["value"], 0)

    def test_summary_reconcile_pending_over_budget_mission_is_not_completion_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Do not show reconcile-pending over-budget rows as completion.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=100,
            )
            mission.state.status = "running"
            mission.state.planner_loop_status = "running"
            mission.state.elapsed_runtime_seconds = 125
            mission.state.remaining_runtime_seconds = 25
            mission.state.time_budget_status = "reconcile_pending"
            store.update_mission(mission)

            summary = store.build_summary_snapshot()
            row = next(item for item in summary["missions"] if item["mission_id"] == mission.mission_id)
            progress = row["liveProgress"]

            self.assertEqual(progress["source"], "mission_runtime_budget_exhausted")
            self.assertEqual(progress["label"], "Runtime budget exhausted")
            self.assertEqual(progress["progressKind"], "runtime_budget_exhausted")
            self.assertFalse(progress["displayAsCompletion"])
            self.assertEqual(progress["remainingSeconds"], 25)
            self.assertIn("Extend the runtime budget", progress["nextAction"])

    def test_summary_snapshot_is_lightweight_and_notification_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            sibling_root = root / "api-service"
            sibling_root.mkdir()
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            sibling = store.upsert_workspace(
                name="API Service",
                root_path=str(sibling_root),
                default_runtime="openclaw",
                workspace_id="workspace_api_service",
            )
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep the web operator informed while work continues.",
                success_checks=["Notification feed updates"],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=1800,
            )
            mission.state.status = "running"
            mission.state.latest_session_id = "runtime_report_session"
            mission.state.last_runtime_event = "Delegated worker picked up the next step."
            mission.delegated_runtime_sessions.append(
                DelegatedRuntimeSession(
                    delegated_id="delegate_summary_fastpath",
                    runtime_id="hermes",
                    launch_command="python -m grant_agent.runtime_worker",
                    status="running",
                    last_event="Fallback session event that should not outrank runtime output.",
                    latest_events=[
                        {
                            "kind": "runtime.output",
                            "message": "## Fluxio Mission Note - Step: Implement smallest vertical slice\nHermes report body starts here.",
                            "created_at": utc_now_iso(),
                            "status": "running",
                        }
                    ],
                    heartbeat_status="healthy",
                    heartbeat_at=utc_now_iso(),
                    heartbeat_interval_seconds=10,
                )
            )
            mission.execution_scope.workspace_root = workspace.root_path
            mission.execution_scope.execution_root = str(root / ".agent_control" / "worktrees" / mission.mission_id)
            mission.execution_scope.branch_name = "mission/context-roots"
            mission.proof.summary = "Mission is producing progress events."
            mission.proof.passed_checks.append("Notification feed updates")
            mission.proof.changed_files.append("web/src/fluxio/FluxioShell.jsx")
            mission.learned_skill_events.append(
                {
                    "kind": "skill.slice_feedback",
                    "skillId": "design-taste-frontend",
                    "systemLoss": 0.18,
                    "nextAction": "reinforce",
                }
            )
            session_dir = root / ".agent_runs" / "runtime_report_session"
            session_dir.mkdir(parents=True)
            (session_dir / "timeline.jsonl").write_text(
                json.dumps(
                    {
                        "kind": "runtime.output",
                        "message": "## Fluxio Mission Note - Step: Implement smallest vertical slice",
                        "timestamp": utc_now_iso(),
                        "metadata": {
                            "args": {
                                "content": "Hermes report body starts here with the actual operator-facing progress note."
                            }
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            store.update_mission(mission)
            store.append_event(
                MissionEvent(
                    mission_id=mission.mission_id,
                    kind="mission.progress",
                    message="Worker advanced one step.",
                )
            )
            store.append_event(
                MissionEvent(
                    mission_id=mission.mission_id,
                    kind="mission.runtime_cycle",
                    message="hermes control cycle finished with status running.",
                )
            )
            control_dir = root / ".agent_control"
            control_dir.mkdir(exist_ok=True)
            (control_dir / "red_team_escalation_history.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "schema": "fluxio.red_team_escalation_history.v1",
                                "recordedAt": "2026-05-28T00:00:00+00:00",
                                "preset": "hackaprompt",
                                "status": "pass",
                                "resistance_score": 92,
                                "difficultyLevel": 2,
                                "nextDifficultyLevel": 3,
                                "passStreak": 1,
                                "cleanPass": True,
                                "shouldEscalate": True,
                                "nextAttemptBudget": 9,
                            }
                        ),
                        json.dumps(
                            {
                                "schema": "fluxio.red_team_escalation_history.v1",
                                "recordedAt": "2026-05-28T01:00:00+00:00",
                                "preset": "hackaprompt",
                                "status": "pass",
                                "resistance_score": 100,
                                "attempt_count": 9,
                                "blocked_attempt_count": 9,
                                "difficultyLevel": 3,
                                "nextDifficultyLevel": 4,
                                "passStreak": 2,
                                "cleanPass": True,
                                "shouldEscalate": True,
                                "nextAttemptBudget": 11,
                                "observedTactics": [
                                    "direct_policy_probe",
                                    "roleplay",
                                    "authority",
                                ],
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = store.build_summary_snapshot()

            self.assertEqual(summary["schema"], "fluxio.control_room.summary.v1")
            self.assertEqual(summary["counts"]["missions"], 1)
            self.assertEqual(summary["counts"]["activeMissions"], 1)
            self.assertEqual(summary["missions"][0]["mission_id"], mission.mission_id)
            self.assertEqual(
                summary["missions"][0]["contextRoots"]["schema"],
                "fluxio.mission.context_roots.v1",
            )
            self.assertGreaterEqual(summary["missions"][0]["contextRoots"]["counts"]["totalRoots"], 2)
            self.assertGreaterEqual(
                summary["missions"][0]["contextRoots"]["counts"]["dependencyEdges"],
                1,
            )
            self.assertEqual(
                summary["missions"][0]["contextRoots"]["writeScopePreflight"]["schema"],
                "fluxio.write_scope_preflight.v1",
            )
            self.assertIn(
                summary["missions"][0]["contextRoots"]["writeScopePreflight"]["status"],
                {"pass", "warn"},
            )
            self.assertGreaterEqual(
                len(summary["missions"][0]["contextRoots"]["dependencyEdges"]),
                1,
            )
            self.assertEqual(
                summary["missions"][0]["contextRoots"]["primary"]["workspaceId"],
                workspace.workspace_id,
            )
            self.assertEqual(
                summary["missions"][0]["contextRoots"]["related"][0]["workspaceId"],
                sibling.workspace_id,
            )
            self.assertIn("notifications", summary)
            self.assertGreaterEqual(len(summary["notifications"]), 1)
            self.assertFalse(
                any(item.get("kind") == "mission.runtime_cycle" for item in summary["notifications"])
            )
            mission_notifications = [
                item for item in summary["notifications"] if item.get("kind") == "mission_status"
            ]
            self.assertTrue(mission_notifications)
            self.assertTrue(
                mission_notifications[0]["agentMessage"].startswith(
                    "## Fluxio Mission Note - Step: Implement smallest vertical slice"
                )
            )
            self.assertEqual(
                mission_notifications[0]["agentMessageSource"],
                "runtime_transcript:runtime_report_session",
            )
            slice_notifications = [
                item for item in summary["notifications"]
                if item.get("kind") == "mission_slice_completed"
            ]
            self.assertGreaterEqual(len(slice_notifications), 1)
            self.assertEqual(slice_notifications[0]["severity"], "success")
            self.assertIn("Slice completed", slice_notifications[0]["title"])
            self.assertIn("system gap 0.18", slice_notifications[0]["detail"])
            self.assertIn("system gap 0.18", slice_notifications[0]["agentMessage"])
            self.assertEqual(
                summary["missionWatchdog"]["supervisor"]["schema"],
                "fluxio.mission_watchdog_supervisor.v1",
            )
            self.assertEqual(summary["missionWatchdog"]["supervisor"]["loopMode"], "none")
            self.assertFalse(summary["missionWatchdog"]["supervisor"]["supervisorActive"])
            self.assertIn("mission-watchdog --loop", summary["missionWatchdog"]["supervisor"]["nextAction"])
            self.assertEqual(
                summary["redTeamEscalation"]["schema"],
                "fluxio.red_team_escalation_snapshot.v1",
            )
            self.assertEqual(summary["redTeamEscalation"]["summary"]["runCount"], 2)
            self.assertEqual(summary["redTeamEscalation"]["summary"]["latestResistanceScore"], 100)
            self.assertEqual(summary["redTeamEscalation"]["summary"]["nextDifficultyLevel"], 4)
            self.assertEqual(
                summary["redTeamEscalation"]["escalationAudit"]["schema"],
                "fluxio.red_team_escalation_audit.v1",
            )
            self.assertEqual(
                summary["redTeamEscalation"]["nextBenchmarkPlan"]["schema"],
                "fluxio.red_team_next_benchmark_plan.v1",
            )
            self.assertEqual(
                summary["redTeamEscalation"]["summaryTruncation"]["schema"],
                "fluxio.summary_truncation.v1",
            )
            self.assertEqual(summary["redTeamEscalation"]["nextBenchmarkPlan"]["difficultyLabel"], "L4")
            self.assertEqual(
                summary["redTeamEscalation"]["nextBenchmarkPlan"]["nextPressureIndex"],
                summary["redTeamEscalation"]["summary"]["nextPressureIndex"],
            )
            self.assertIn(
                f"pressure index advances to {summary['redTeamEscalation']['summary']['nextPressureIndex']}",
                summary["redTeamEscalation"]["nextBenchmarkPlan"]["successCriteria"],
            )
            self.assertIn(
                "sample:self-improvement-red-team",
                summary["redTeamEscalation"]["nextBenchmarkPlan"]["command"]["shell"],
            )
            self.assertEqual(summary["redTeamEscalation"]["summary"]["satisfiedEscalationTargets"], 1)
            self.assertEqual(summary["redTeamEscalation"]["summary"]["pendingEscalationTargets"], 1)
            self.assertEqual(summary["overnightDigest"]["schema"], "fluxio.overnight_progress_digest.v1")
            self.assertTrue(summary["overnightDigest"]["delivery"]["appLike"])
            self.assertTrue(summary["overnightDigest"]["delivery"]["receiptBacked"])
            self.assertIn("browser_notification", summary["overnightDigest"]["delivery"]["channels"])
            self.assertIn("webPushReady", summary["overnightDigest"]["delivery"])
            self.assertIn("webPushSenderConfigured", summary["overnightDigest"]["delivery"])
            self.assertIn("webPushSubscriptionCount", summary["overnightDigest"]["delivery"])
            self.assertIn("webPushNextAction", summary["overnightDigest"]["delivery"])
            self.assertEqual(summary["overnightDigest"]["counts"]["active"], 1)
            self.assertEqual(
                summary["projectProgressHistory"]["schema"],
                "fluxio.project_progress_history.v1",
            )
            self.assertEqual(
                summary["projectProgressHistory"]["summaryTruncation"]["schema"],
                "fluxio.summary_truncation.v1",
            )
            self.assertEqual(summary["projectProgressHistory"]["source"], "mission_store_and_mission_events")
            project_history = {
                item["workspaceId"]: item
                for item in summary["projectProgressHistory"]["projects"]
            }
            self.assertIn(workspace.workspace_id, project_history)
            self.assertTrue(project_history[workspace.workspace_id]["liveData"])
            self.assertGreaterEqual(project_history[workspace.workspace_id]["counts"]["events"], 1)
            self.assertGreaterEqual(
                len(project_history[workspace.workspace_id]["milestones"]),
                1,
            )
            self.assertEqual(
                project_history[workspace.workspace_id]["milestones"][0]["source"],
                "mission_events",
            )
            self.assertGreaterEqual(
                len(project_history[workspace.workspace_id]["buckets"]),
                1,
            )
            self.assertEqual(
                project_history[workspace.workspace_id]["scheduleRecommendation"]["schema"],
                "fluxio.project_schedule_recommendation.v1",
            )
            self.assertEqual(
                project_history[workspace.workspace_id]["syncAuthority"]["schema"],
                "fluxio.workspace_sync_authority.v1",
            )
            self.assertEqual(
                project_history[workspace.workspace_id]["launchRehearsal"]["schema"],
                "fluxio.cross_device_launch_rehearsal.v1",
            )
            self.assertFalse(project_history[workspace.workspace_id]["launchRehearsal"]["safeToLaunch"])
            self.assertIn(
                "dependency_schedule",
                project_history[workspace.workspace_id]["launchRehearsal"]["blockedCheckIds"],
            )
            self.assertEqual(
                project_history[workspace.workspace_id]["syncAuthority"]["state"],
                "manual_local",
            )
            self.assertTrue(
                project_history[workspace.workspace_id]["syncAuthority"]["safeForWritableDependency"],
            )
            self.assertEqual(
                project_history[workspace.workspace_id]["scheduleRecommendation"]["state"],
                "watch",
            )
            self.assertFalse(
                project_history[workspace.workspace_id]["scheduleRecommendation"]["safeToLaunch"],
            )
            self.assertEqual(
                summary["projectProgressHistory"]["scheduler"]["schema"],
                "fluxio.dependency_aware_project_scheduler.v1",
            )
            self.assertGreaterEqual(
                len(summary["projectProgressHistory"]["schedulingQueue"]),
                1,
            )
            self.assertEqual(
                summary["projectProgressHistory"]["scheduler"]["topWorkspaceId"],
                summary["projectProgressHistory"]["schedulingQueue"][0]["workspaceId"],
            )
            self.assertIn(
                project_history[workspace.workspace_id]["scheduleRecommendation"],
                summary["projectProgressHistory"]["schedulingQueue"],
            )
            self.assertIn("phoneSummary", summary["overnightDigest"])
            self.assertEqual(
                summary["missionWatchdog"]["summarySource"]["schema"],
                "fluxio.summary.watchdog_source.v1",
            )
            self.assertIn("missionLaunchShortcuts", summary)
            self.assertIn("harnessLab", summary)
            self.assertEqual(
                summary["harnessLab"]["routeTrustCoverage"]["schema"],
                "fluxio.route_trust_coverage.v1",
            )
            self.assertIn("quarantinedRouteCount", summary["harnessLab"]["routeTrustCoverage"])
            self.assertEqual(summary["summaryShaping"]["harnessLab"], "route_trust_coverage_only")
            self.assertEqual(
                summary["missionLaunchShortcuts"][0]["workspaceId"],
                workspace.workspace_id,
            )
            self.assertEqual(
                summary["missionLaunchShortcuts"][0]["runtimeRecommendation"]["schema"],
                "fluxio.launch_runtime_recommendation.v1",
            )
            self.assertIn(
                summary["missionLaunchShortcuts"][0]["recommendedRuntime"],
                {"hermes", "openclaw"},
            )
            self.assertEqual(summary["missionLaunchShortcuts"][0]["runtime"], "hermes")
            self.assertIn("launch=mission", summary["missionLaunchShortcuts"][0]["urlPath"])
            self.assertIn("mission-quickstart", summary["missionLaunchShortcuts"][0]["cliCommand"])
            self.assertTrue(summary["mobileWeb"]["summaryFirst"])
            self.assertTrue(summary["mobileWeb"]["overnightDigest"])
            self.assertTrue(summary["mobileWeb"]["appLikeProgress"])
            self.assertIn("browser_notification", summary["mobileWeb"]["phoneNotificationChannels"])
            self.assertEqual(summary["performance"]["source"], "control_room_summary")
            self.assertGreater(summary["performance"]["payloadBytes"], 0)
            self.assertEqual(
                summary["performance"]["budget"]["schema"],
                "fluxio.performance_budget.v1",
            )
            self.assertIn(summary["performance"]["budget"]["status"], {"pass", "warn"})
            self.assertTrue(summary["performance"]["virtualization"]["summaryFirst"])
            self.assertEqual(summary["performance"]["budget"]["itemLimits"]["missions"], 60)
            self.assertTrue(summary["performance"]["sectionDurations"])
            self.assertTrue(summary["performance"]["slowestSections"])
            self.assertIn(
                "system_audit_digest",
                {item["name"] for item in summary["performance"]["sectionDurations"]},
            )
            self.assertEqual(summary["performance"]["budget"]["itemLimits"]["richContextRoots"], 1)
            self.assertEqual(
                summary["summaryShaping"]["schema"],
                "fluxio.control_room.summary_shaping.v1",
            )
            self.assertEqual(summary["summaryShaping"]["richContextRoots"], "active_missions_only")
            self.assertEqual(summary["summaryShaping"]["skillCatalogRows"], "bounded_live_samples_with_total_counts")
            self.assertEqual(summary["summaryShaping"]["projectProgressRows"], "bounded_project_milestones_and_receipts")
            self.assertEqual(summary["summaryShaping"]["systemAuditDigest"], "operator_summary_fields_only")

            detail = store.build_mission_detail_snapshot(mission.mission_id, event_limit=12)

            self.assertEqual(detail["schema"], "fluxio.control_room.mission_detail.v1")
            self.assertEqual(detail["missionId"], mission.mission_id)
            self.assertEqual(detail["summary"]["mission_id"], mission.mission_id)
            self.assertEqual(detail["contextRoots"]["schema"], "fluxio.mission.context_roots.v1")
            self.assertEqual(detail["contextRoots"]["execution"]["branchName"], "mission/context-roots")
            self.assertGreaterEqual(detail["contextRoots"]["counts"]["relatedWorkspaces"], 1)
            self.assertGreaterEqual(detail["contextRoots"]["counts"]["dependencyEdges"], 1)
            self.assertEqual(
                detail["contextRoots"]["writeScopePreflight"]["schema"],
                "fluxio.write_scope_preflight.v1",
            )
            self.assertEqual(detail["performance"]["source"], "control_room_mission_detail")
            self.assertEqual(detail["performance"]["eventLimit"], 12)
            self.assertGreater(detail["performance"]["payloadBytes"], 0)
            self.assertEqual(
                detail["performance"]["budget"]["schema"],
                "fluxio.performance_budget.v1",
            )
            self.assertTrue(detail["performance"]["virtualization"]["lazyMissionDetail"])
            self.assertEqual(detail["performance"]["budget"]["itemLimits"]["events"], 12)
            self.assertIn("mission.progress", [item["kind"] for item in detail["events"]])
            self.assertGreaterEqual(len(detail["agentMessages"]), 1)
            self.assertTrue(
                any("Progress" in item["title"] or "progress" in item["label"].lower() for item in detail["agentMessages"])
            )
            self.assertEqual(detail["proofDigest"]["schema"], "fluxio.mission.proof_digest.v1")
            self.assertEqual(detail["proofDigest"]["missionId"], mission.mission_id)
            self.assertEqual(detail["proofDigest"]["counts"]["passedChecks"], 1)
            self.assertEqual(detail["proofDigest"]["counts"]["changedFiles"], 1)
            self.assertEqual(detail["proofDigest"]["counts"]["skillFeedbackSlices"], 1)
            self.assertEqual(
                detail["proofDigest"]["export"]["schema"],
                "fluxio.mission.proof_digest_export.v1",
            )
            self.assertEqual(
                detail["proofDigest"]["export"]["backendCommand"],
                "export_mission_proof_digest_command",
            )
            self.assertEqual(
                detail["proofDigest"]["latest"]["skillFeedback"][0]["skillId"],
                "design-taste-frontend",
            )

    def test_bootstrap_summary_keeps_slice_notifications_outside_visible_mission_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            old_slice = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep slice feedback visible in bootstrap notifications.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            old_slice.title = "Older slice mission"
            old_slice.state.status = "completed"
            old_slice.created_at = "2026-05-01T00:00:00+00:00"
            old_slice.updated_at = "2026-05-01T00:00:00+00:00"
            old_slice.learned_skill_events = [
                {
                    "kind": "skill.slice_feedback",
                    "skillId": "agent-thread-reader",
                    "systemLoss": 0.12,
                    "nextAction": "Keep report-first Agent visible.",
                    "timestamp": "2026-06-02T01:00:00+00:00",
                }
            ]
            store.update_mission(old_slice)
            for index in range(mission_control_module.CONTROL_ROOM_BOOTSTRAP_MISSION_LIMIT + 3):
                mission = store.create_mission(
                    workspace_id=workspace.workspace_id,
                    runtime_id="hermes",
                    objective=f"Recent running mission {index}",
                    success_checks=[],
                    mode="Autopilot",
                    verification_commands=[],
                    max_runtime_seconds=3600,
                )
                mission.state.status = "running"
                mission.created_at = f"2026-06-01T00:{index:02d}:00+00:00"
                mission.updated_at = f"2026-06-01T00:{index:02d}:00+00:00"
                store.update_mission(mission)

            summary = store.build_bootstrap_summary_snapshot()

            visible_ids = {item["mission_id"] for item in summary["missions"]}
            self.assertNotIn(old_slice.mission_id, visible_ids)
            self.assertTrue(
                any(
                    item["kind"] == "mission_slice_completed"
                    and item["missionId"] == old_slice.mission_id
                    and "agent-thread-reader" in item["detail"]
                    for item in summary["notifications"]
                )
            )

    def test_running_notification_hydrates_missing_workflow_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep running Hermes output visible in notifications.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "running"
            mission.delegated_runtime_sessions = []
            mission.state.last_runtime_event = "running"
            mission.action_history = []
            store.update_mission(mission)
            runtime_sessions_root = root / ".agent_control" / "runtime_sessions"
            runtime_sessions_root.mkdir(parents=True, exist_ok=True)
            (runtime_sessions_root / "delegate_live.json").write_text(
                json.dumps(
                    {
                        "missionId": mission.mission_id,
                        "delegated_id": "delegate_live",
                        "runtime_id": "hermes",
                        "launch_command": "hermes resume mission",
                        "status": "running",
                        "latest_events": [
                            {
                                "kind": "runtime.output",
                                "message": "Hermes produced live slice output for the active mission.",
                                "created_at": "2026-06-02T04:20:00+00:00",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            summary = store.build_bootstrap_summary_snapshot()

            mission_notifications = [
                item
                for item in summary["notifications"]
                if item.get("kind") == "mission_status"
                and item.get("missionId") == mission.mission_id
            ]
            self.assertTrue(mission_notifications)
            self.assertIn("Hermes produced live slice output", mission_notifications[0]["agentMessage"])
            self.assertEqual(
                mission_notifications[0]["agentMessageSource"],
                "runtime_output:hermes:delegate_live",
            )

    def test_completed_runtime_status_emits_slice_notification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Notify when a runtime-backed slice completes.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.title = "Runtime backed slice"
            mission.state.status = "completed"
            mission.delegated_runtime_sessions = [
                DelegatedRuntimeSession(
                    delegated_id="delegate_done",
                    runtime_id="hermes",
                    launch_command="hermes run",
                    status="completed",
                    latest_events=[
                        {
                            "kind": "runtime.output",
                            "message": "Hermes completed the report body.",
                        }
                    ],
                )
            ]
            store.update_mission(mission)

            summary = store.build_bootstrap_summary_snapshot()

            slice_notifications = [
                item
                for item in summary["notifications"]
                if item.get("kind") == "mission_slice_completed"
                and item.get("missionId") == mission.mission_id
            ]
            self.assertTrue(slice_notifications)
            self.assertIn("Slice completed: Runtime backed slice", slice_notifications[0]["title"])
            self.assertIn("Hermes completed the report body", slice_notifications[0]["agentMessage"])
            self.assertEqual(
                slice_notifications[0]["agentMessageSource"],
                "runtime_output:hermes:delegate_done",
            )

    def test_overnight_digest_separates_repair_from_safely_held_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            blocker = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Active mission owns the shared file scope.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=1800,
            )
            blocker.state.status = "running"
            blocker.state.queue_position = 0
            store.update_mission(blocker)

            held = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Queued mission should wait instead of overlapping the active writes.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=1800,
            )
            held.state.status = "queued"
            held.state.queue_position = 1
            held.state.blocking_mission_id = blocker.mission_id
            held.proof.failed_checks = ["Artifact gate waits for the active scope."]
            store.update_mission(held)

            failed = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Failed mission needs a real repair action.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=1800,
            )
            failed.state.status = "verification_failed"
            failed.proof.failed_checks = ["Verifier failed."]
            failed.proof.summary = "Verifier failed."
            store.update_mission(failed)

            summary = store.build_summary_snapshot()
            digest = summary["overnightDigest"]

            self.assertEqual(digest["headline"], "1 mission(s) need repair · 1 held safely")
            self.assertIn("1 repair · 1 held", digest["phoneSummary"])
            self.assertEqual(digest["counts"]["actionRequired"], 1)
            self.assertEqual(digest["counts"]["heldQueued"], 1)
            self.assertEqual(digest["counts"]["blocked"], 1)
            self.assertEqual(digest["counts"]["attention"], 2)
            self.assertIn("split their file scope", digest["nextAction"])
            focus_by_id = {item["missionId"]: item for item in digest["focusItems"]}
            self.assertEqual(focus_by_id[failed.mission_id]["attentionKind"], "repair")
            self.assertEqual(focus_by_id[held.mission_id]["attentionKind"], "held_queue")
            self.assertEqual(focus_by_id[held.mission_id]["blockingMissionId"], blocker.mission_id)
            self.assertIn("Held behind active mission", focus_by_id[held.mission_id]["summary"])
            self.assertIn("Keep queued", focus_by_id[held.mission_id]["nextAction"])

    def test_summary_defers_terminal_context_roots_to_mission_detail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            running = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep live mission context available in the summary.",
                success_checks=["Live context shown"],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=1800,
            )
            running.state.status = "running"
            running.execution_scope.workspace_root = workspace.root_path
            running.execution_scope.execution_root = str(
                root / ".agent_control" / "worktrees" / running.mission_id
            )
            store.update_mission(running)

            completed = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Completed mission should not bulk-load context in the list.",
                success_checks=["Proof archived"],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=1800,
            )
            completed.state.status = "completed"
            completed.execution_scope.workspace_root = workspace.root_path
            completed.execution_scope.execution_root = str(
                root / ".agent_control" / "worktrees" / completed.mission_id
            )
            completed.proof.summary = "Proof archived."
            store.update_mission(completed)

            summary = store.build_summary_snapshot()
            rows = {item["mission_id"]: item for item in summary["missions"]}

            self.assertEqual(
                rows[running.mission_id]["contextRoots"]["schema"],
                "fluxio.mission.context_roots.v1",
            )
            self.assertNotEqual(rows[running.mission_id]["contextRoots"].get("status"), "detail_required")
            self.assertEqual(rows[completed.mission_id]["contextRoots"]["status"], "detail_required")
            self.assertEqual(
                rows[completed.mission_id]["contextRoots"]["source"],
                "summary_deferred_terminal_context",
            )
            self.assertEqual(rows[completed.mission_id]["plannedScopeArtifacts"], {})
            self.assertEqual(rows[completed.mission_id]["runtimeLanes"], [])
            self.assertEqual(
                rows[completed.mission_id]["summaryCompaction"]["schema"],
                "fluxio.mission_summary_compaction.v1",
            )
            self.assertEqual(summary["summaryShaping"]["richContextRoots"], "active_missions_only")
            self.assertEqual(summary["performance"]["budget"]["itemLimits"]["richContextRoots"], 1)

    def test_summary_bounds_skill_red_team_project_and_audit_sections(self) -> None:
        skill_catalog = {
            "curatedPacks": [{"packId": f"curated_{index}"} for index in range(20)],
            "recommendedPacks": [{"packId": f"recommended_{index}"} for index in range(12)],
            "userInstalledSkills": [{"id": f"installed_{index}"} for index in range(12)],
            "learnedSkills": [
                {
                    "skill_id": f"learned_{index}",
                    "label": f"Learned {index}",
                    "audit": [{"large": item} for item in range(200)],
                    "feedbackSummary": {
                        "sliceCount": 3,
                        "trend": "repair",
                        "history": [{"large": item} for item in range(100)],
                    },
                }
                for index in range(12)
            ],
            "managementSummary": {"totalSkills": 56},
            "feedbackLoop": {
                "latest": [{"id": index} for index in range(12)],
                "repairProposals": [{"id": index} for index in range(8)],
                "systemLossRouting": {
                    "activeRepairSkillIds": [f"repair_{index}" for index in range(12)],
                    "preferredSkillIds": [f"preferred_{index}" for index in range(12)],
                },
            },
        }
        red_team = {
            "schema": "fluxio.red_team_escalation_snapshot.v1",
            "history": [{"recordedAt": f"2026-05-29T00:{index:02d}:00+00:00"} for index in range(10)],
            "summary": {"runCount": 10},
            "escalationAudit": {
                "schema": "fluxio.red_team_escalation_audit.v1",
                "status": "pending",
                "satisfiedTargets": 3,
                "pendingTargets": 1,
                "rawRows": [{"large": index} for index in range(20)],
            },
        }
        project_progress = {
            "schema": "fluxio.project_progress_history.v1",
            "projects": [
                {
                    "workspaceId": "workspace_demo",
                    "milestones": [{"id": f"m{index}"} for index in range(12)],
                    "buckets": [{"date": f"2026-05-{index:02d}"} for index in range(12)],
                    "launchRehearsal": {
                        "receiptHistory": [{"id": f"receipt_{index}"} for index in range(6)],
                    },
                }
            ],
            "schedulingQueue": [{"workspaceId": f"workspace_{index}"} for index in range(12)],
        }
        audit = {
            "schema": "fluxio.system_audit_digest.v1",
            "deficits": [{"id": index} for index in range(12)],
            "badFirst": [{"id": index} for index in range(12)],
            "improvementQueue": [{"id": index} for index in range(12)],
            "activeGapMissions": [{"id": index} for index in range(12)],
            "systemLossBreakdown": {"drivers": [{"id": index} for index in range(12)]},
            "watchdogSelfImprovement": {"recentReceipts": [{"id": index} for index in range(12)]},
            "t3Reference": {"strengthsToBeat": [f"strength_{index}" for index in range(12)]},
        }

        compact_skills = ControlRoomStore._summary_skill_catalog_payload(skill_catalog)
        compact_red_team = ControlRoomStore._summary_red_team_escalation_payload(red_team)
        compact_projects = ControlRoomStore._summary_project_progress_payload(project_progress)
        compact_audit = ControlRoomStore._summary_system_audit_digest_payload(audit)

        self.assertEqual(len(compact_skills["curatedPacks"]), 12)
        self.assertEqual(len(compact_skills["recommendedPacks"]), 8)
        self.assertEqual(len(compact_skills["userInstalledSkills"]), 8)
        self.assertEqual(len(compact_skills["learnedSkills"]), 8)
        self.assertEqual(compact_skills["summaryTruncation"]["curatedTotal"], 20)
        self.assertNotIn("audit", compact_skills["learnedSkills"][0])
        self.assertNotIn("history", compact_skills["learnedSkills"][0]["feedbackSummary"])
        self.assertEqual(
            compact_skills["learnedSkills"][0]["summaryCompaction"]["schema"],
            "fluxio.skill_summary_compaction.v1",
        )
        self.assertEqual(len(compact_skills["feedbackLoop"]["latest"]), 6)
        self.assertEqual(len(compact_skills["feedbackLoop"]["repairProposals"]), 4)
        self.assertEqual(
            len(compact_skills["feedbackLoop"]["systemLossRouting"]["activeRepairSkillIds"]),
            8,
        )
        self.assertEqual(len(compact_red_team["history"]), 6)
        self.assertEqual(compact_red_team["summaryTruncation"]["historyTotal"], 10)
        self.assertNotIn("rawRows", compact_red_team["escalationAudit"])
        self.assertEqual(len(compact_projects["projects"][0]["milestones"]), 5)
        self.assertEqual(len(compact_projects["projects"][0]["buckets"]), 5)
        self.assertEqual(len(compact_projects["projects"][0]["launchRehearsal"]["receiptHistory"]), 2)
        self.assertEqual(len(compact_projects["schedulingQueue"]), 8)
        self.assertEqual(len(compact_audit["deficits"]), 6)
        self.assertEqual(len(compact_audit["badFirst"]), 4)
        self.assertEqual(len(compact_audit["systemLossBreakdown"]["drivers"]), 4)
        self.assertEqual(len(compact_audit["watchdogSelfImprovement"]["recentReceipts"]), 3)

    def test_project_scheduler_respects_declared_workspace_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            app_root = root / "app"
            api_root = root / "api"
            app_root.mkdir()
            api_root.mkdir()
            store = ControlRoomStore(root)
            app = store.upsert_workspace(
                name="App",
                root_path=str(app_root),
                default_runtime="hermes",
                workspace_id="workspace_app",
            )
            api = store.upsert_workspace(
                name="API",
                root_path=str(api_root),
                default_runtime="hermes",
                workspace_id="workspace_api",
            )
            app.goals.append(f"depends_on:{api.workspace_id}")
            store.save_workspaces([app, api])

            blocker = store.create_mission(
                workspace_id=api.workspace_id,
                runtime_id="hermes",
                objective="Fix the API contract before UI work continues.",
                success_checks=["API contract verified"],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=1800,
            )
            blocker.state.status = "blocked"
            blocker.proof.blocked_by.append("contract review")
            store.update_mission(blocker)

            summary = store.build_summary_snapshot()
            project_history = {
                item["workspaceId"]: item
                for item in summary["projectProgressHistory"]["projects"]
            }
            app_schedule = project_history[app.workspace_id]["scheduleRecommendation"]

            self.assertEqual(app_schedule["state"], "dependency_blocked")
            self.assertFalse(app_schedule["safeToLaunch"])
            self.assertEqual(app_schedule["declaredDependencyIds"], [api.workspace_id])
            self.assertEqual(
                app_schedule["dependencyBlockedWorkspaces"][0]["workspaceId"],
                api.workspace_id,
            )
            self.assertEqual(
                app_schedule["dependencyBlockedWorkspaces"][0]["relation"],
                "upstream_dependency",
            )
            self.assertIn("Upstream dependency workspace is blocked.", app_schedule["dependencyWarnings"])
            self.assertIn(app_schedule, summary["projectProgressHistory"]["schedulingQueue"])
            self.assertIn(
                "dependency_schedule",
                project_history[app.workspace_id]["launchRehearsal"]["blockedCheckIds"],
            )

    def test_project_progress_exposes_sync_authority_review_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            local_root = root / "local"
            nas_root = root / "nas"
            local_root.mkdir()
            nas_root.mkdir()
            store = ControlRoomStore(root)
            workspace = store.upsert_workspace(
                name="Synced project",
                root_path=str(local_root),
                default_runtime="hermes",
                local_project_path=str(local_root),
                nas_project_path=str(nas_root),
                sync_mode="auto_nas_mirror",
                sync_direction="bidirectional",
                auto_sync_to_nas=True,
                workspace_id="workspace_synced",
            )
            sync_payload = {
                "schema": "fluxio.workspace_sync_status.v1",
                "effectiveDirection": "bidirectional",
                "conflictsDetected": 1,
                "manualReviewRequired": True,
                "syncReceipt": {
                    "schema": "fluxio.workspace_sync_receipt.v1",
                    "receiptId": "sync_123",
                    "effectiveDirection": "bidirectional",
                    "conflictsDetected": 1,
                    "manualReviewRequired": True,
                },
            }
            workspace.goals = [
                entry for entry in workspace.goals if not str(entry).startswith("sync_status:")
            ]
            workspace.goals.append(f"sync_status:{json.dumps(sync_payload, sort_keys=True)}")
            store.save_workspaces([workspace])

            summary = store.build_summary_snapshot()
            project = summary["projectProgressHistory"]["projects"][0]
            authority = project["syncAuthority"]

            self.assertEqual(authority["schema"], "fluxio.workspace_sync_authority.v1")
            self.assertEqual(authority["state"], "conflict_review")
            self.assertEqual(authority["authority"], "manual_review")
            self.assertEqual(authority["receiptId"], "sync_123")
            self.assertEqual(authority["conflictCount"], 1)
            self.assertTrue(authority["manualReviewRequired"])
            self.assertFalse(authority["safeForWritableDependency"])
            self.assertIn("Resolve sync conflicts", authority["nextAction"])
            rehearsal = project["launchRehearsal"]
            self.assertEqual(rehearsal["schema"], "fluxio.cross_device_launch_rehearsal.v1")
            self.assertFalse(rehearsal["safeToLaunch"])
            self.assertIn("sync_authority", rehearsal["blockedCheckIds"])
            self.assertIn("launch=mission", rehearsal["urlPath"])
            self.assertIn("mission-quickstart", rehearsal["cliCommand"])

    def test_project_progress_exposes_ready_cross_device_launch_rehearsal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            project_root = root / "project"
            project_root.mkdir()
            store = ControlRoomStore(root)
            workspace = store.upsert_workspace(
                name="Ready project",
                root_path=str(project_root),
                default_runtime="hermes",
                workspace_id="workspace_ready",
            )

            summary = store.build_summary_snapshot()
            project = next(
                item
                for item in summary["projectProgressHistory"]["projects"]
                if item["workspaceId"] == workspace.workspace_id
            )
            rehearsal = project["launchRehearsal"]

            self.assertEqual(rehearsal["schema"], "fluxio.cross_device_launch_rehearsal.v1")
            self.assertTrue(rehearsal["safeToLaunch"])
            self.assertEqual(rehearsal["status"], "ready")
            self.assertEqual(rehearsal["blockedCheckIds"], [])
            self.assertEqual(len(rehearsal["checklist"]), 3)
            self.assertEqual(
                {item["id"] for item in rehearsal["checklist"]},
                {"sync_authority", "dependency_schedule", "runtime_route"},
            )
            self.assertIn("launch=mission", rehearsal["urlPath"])
            self.assertIn("mission-quickstart", rehearsal["cliCommand"])

    def test_cross_device_launch_rehearsal_receipt_is_archived_and_attached(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            project_root = root / "project"
            project_root.mkdir()
            store = ControlRoomStore(root)
            workspace = store.upsert_workspace(
                name="Receipt project",
                root_path=str(project_root),
                default_runtime="hermes",
                workspace_id="workspace_receipt",
            )
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Launch from the cross-device rehearsal path.",
                success_checks=["Receipt archived"],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=1800,
            )

            receipt = record_cross_device_launch_rehearsal_receipt(
                store=store,
                workspace_id=workspace.workspace_id,
                mission_id=mission.mission_id,
            )
            second_receipt = record_cross_device_launch_rehearsal_receipt(
                store=store,
                workspace_id=workspace.workspace_id,
                mission_id=mission.mission_id,
            )
            summary = store.build_summary_snapshot()
            project = next(
                item
                for item in summary["projectProgressHistory"]["projects"]
                if item["workspaceId"] == workspace.workspace_id
            )

            self.assertEqual(receipt["schema"], "fluxio.cross_device_launch_rehearsal_receipt.v1")
            self.assertIn(receipt["status"], {"launched", "launched_with_review_items"})
            self.assertEqual(receipt["missionId"], mission.mission_id)
            self.assertTrue((root / ".agent_control" / "cross_device_launch_rehearsals" / "latest.json").exists())
            self.assertEqual(
                project["launchRehearsal"]["latestReceipt"]["receiptId"],
                second_receipt["receiptId"],
            )
            self.assertEqual(project["launchRehearsal"]["receiptCount"], 2)
            self.assertEqual(project["launchRehearsal"]["receiptTrendStatus"], "repeated")
            self.assertEqual(len(project["launchRehearsal"]["receiptHistory"]), 2)
            self.assertTrue(project["launchRehearsal"]["receiptBacked"])
            self.assertEqual(
                summary["projectProgressHistory"]["launchReceiptSummary"]["receiptCount"],
                2,
            )
            self.assertEqual(
                summary["projectProgressHistory"]["launchReceiptSummary"]["trendStatus"],
                "repeated",
            )

    def test_snapshot_performance_budget_stays_bounded_with_long_histories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Exercise long history snapshot budgets.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=1800,
            )
            for index in range(120):
                store.append_event(
                    MissionEvent(
                        mission_id=mission.mission_id,
                        kind="mission.progress",
                        message=f"Long-history event {index}",
                    )
                )

            summary = store.build_summary_snapshot()
            detail = store.build_mission_detail_snapshot(mission.mission_id, event_limit=17)

            self.assertLessEqual(len(summary["notifications"]), 24)
            self.assertEqual(summary["performance"]["budget"]["itemLimits"]["activity"], 24)
            self.assertLessEqual(len(detail["events"]), 17)
            self.assertEqual(detail["performance"]["budget"]["itemLimits"]["events"], 17)
            self.assertLessEqual(
                detail["performance"]["payloadBytes"],
                detail["performance"]["budget"]["payloadBudgetBytes"],
            )

    def test_snapshot_includes_runtime_compartments_and_hermes_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Collect Hermes mission evidence.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=1800,
            )
            session = DelegatedRuntimeSession(
                delegated_id="delegate_test",
                runtime_id="hermes",
                launch_command="hermes chat -q test",
                status="running",
                detail="Hermes delegated lane is running.",
                session_path=str(root / ".agent_control" / "runtime_sessions" / "delegate_test.json"),
                workspace_root=str(root),
                execution_root=str(root),
                latest_events=[
                    {
                        "kind": "runtime.proof",
                        "message": "Hermes produced proof event.",
                        "status": "running",
                        "timestamp": "2026-05-12T10:00:00+00:00",
                    }
                ],
            )
            session_file = pathlib.Path(session.session_path)
            session_file.parent.mkdir(parents=True)
            session_file.write_text(json.dumps(asdict(session), indent=2), encoding="utf-8")
            mission.delegated_runtime_sessions = [session]
            mission.state.delegated_runtime_sessions = [asdict(session)]
            mission.proof.passed_checks = ["Hermes proof captured"]
            store.save_missions([mission])
            store.append_event(
                MissionEvent(
                    mission_id=mission.mission_id,
                    kind="hermes.proof",
                    message="Hermes proof event persisted.",
                    timestamp="2026-05-12T10:01:00+00:00",
                    metadata={"source": "hermes"},
                )
            )

            snapshot = ControlRoomStore(root).build_snapshot()

            compartments = snapshot["runtimeCompartments"]
            self.assertGreaterEqual(compartments["summary"]["total"], 1)
            self.assertEqual(compartments["items"][0]["runtime"], "hermes")
            self.assertEqual(compartments["items"][0]["status"], "running")
            self.assertIn("recentActivity", compartments["items"][0])

            evidence = snapshot["hermesMissionEvidence"]
            self.assertTrue(evidence["items"])
            self.assertTrue(
                all(
                    {"timestamp", "status", "source", "message"}.issubset(item)
                    for item in evidence["items"]
                )
            )

    def test_empty_snapshot_reports_honest_runtime_and_hermes_empty_states(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)

            snapshot = ControlRoomStore(root).build_snapshot()

            self.assertEqual(snapshot["runtimeCompartments"]["items"], [])
            self.assertIn("emptyState", snapshot["runtimeCompartments"])
            self.assertEqual(snapshot["hermesMissionEvidence"]["items"], [])
            self.assertIn("emptyState", snapshot["hermesMissionEvidence"])
            self.assertIn("checks", snapshot["nasDeployReadiness"])

    def test_create_mission_persists_and_builds_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="openclaw",
                objective="Ship a safer control room",
                success_checks=["Proof summary written"],
                mode="Autopilot",
                verification_commands=["python -m unittest"],
                max_runtime_seconds=3600,
                escalation_destination="123456",
            )
            mission.state.status = "needs_approval"
            mission.proof.summary = "Approval needed for deploy step."
            preview = build_escalation_preview(mission)
            snapshot = store.build_snapshot()

            self.assertIn("Approval needed", preview)
            self.assertEqual(store.get_mission(mission.mission_id).mission_id, mission.mission_id)
            mission_payload = next(item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id)
            self.assertIn("missionLoop", mission_payload)
            self.assertIn("effectiveRouteContract", mission_payload)
            self.assertIn("currentCyclePhase", mission_payload["missionLoop"])
            self.assertIn("timeBudget", mission_payload["missionLoop"])
            self.assertIn("autonomousWorkflows", snapshot)
            workflow_record = next(
                item
                for item in snapshot["autonomousWorkflows"]["items"]
                if item["missionId"] == mission.mission_id
            )
            self.assertEqual(workflow_record["objective"], mission.objective)
            self.assertEqual(workflow_record["mode"], "Autopilot")
            self.assertEqual(workflow_record["verification"]["commands"], ["python -m unittest"])
            self.assertGreaterEqual(workflow_record["eventCount"], 1)

    def test_autonomous_workflow_records_runtime_evidence_and_approvals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Record autonomous runtime evidence.",
                success_checks=["Runtime evidence captured"],
                mode="Deep Run",
                verification_commands=["python -m pytest tests -q"],
                max_runtime_seconds=7200,
            )
            sessions_dir = root / ".agent_control" / "runtime_sessions"
            sessions_dir.mkdir(parents=True)
            session = DelegatedRuntimeSession(
                delegated_id="delegate_recording",
                runtime_id="hermes",
                launch_command="hermes chat -q test",
                status="waiting_for_approval",
                detail="Approval required.",
                session_path=str(sessions_dir / "delegate_recording.json"),
                workspace_root=str(root),
                execution_root=str(root),
                log_path=str(sessions_dir / "delegate_recording.log"),
                events_path=str(sessions_dir / "delegate_recording.events.jsonl"),
                decision_path=str(sessions_dir / "delegate_recording.approval.json"),
                pending_approval={
                    "request_id": "approval_1",
                    "delegated_id": "delegate_recording",
                    "runtime_id": "hermes",
                    "prompt": "Approve file write?",
                    "risk_level": "medium",
                    "status": "pending",
                    "created_at": "2026-05-20T12:00:00+00:00",
                    "metadata": {},
                },
                changed_files=["src/demo.py"],
            )
            pathlib.Path(session.log_path).write_text("runtime log\n", encoding="utf-8")
            pathlib.Path(session.events_path).write_text(
                json.dumps(
                    {
                        "event_id": "evt_1",
                        "delegated_id": "delegate_recording",
                        "runtime_id": "hermes",
                        "kind": "approval.request",
                        "message": "Approve file write?",
                        "status": "waiting_for_approval",
                        "created_at": "2026-05-20T12:00:00+00:00",
                        "data": {},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            pathlib.Path(session.session_path).write_text(
                json.dumps(asdict(session), indent=2),
                encoding="utf-8",
            )
            mission.state.status = "needs_approval"
            mission.state.latest_session_id = session.delegated_id
            mission.delegated_runtime_sessions = [session]
            mission.proof.pending_approvals = ["Approve file write?"]
            mission.proof.failed_checks = ["verification blocked until approval"]
            store.update_mission(mission)

            records = store.load_autonomous_workflows()
            record = next(item for item in records if item["missionId"] == mission.mission_id)

            self.assertEqual(record["runtimeSummary"]["delegatedSessionCount"], 1)
            self.assertEqual(record["approvalSummary"]["pendingCount"], 1)
            self.assertIn("src/demo.py", record["changedFiles"])
            self.assertTrue(
                any(
                    item["label"] == "session events" and item["exists"]
                    for item in record["evidenceFiles"]
                )
            )
            self.assertEqual(
                record["verification"]["failedChecks"],
                ["verification blocked until approval"],
            )

            snapshot = ControlRoomStore(root).build_snapshot()
            workflows = snapshot["autonomousWorkflows"]
            self.assertEqual(workflows["summary"]["needsApproval"], 1)
            self.assertGreaterEqual(workflows["summary"]["failedOrBlocked"], 1)

    def test_minimax_portal_auth_does_not_mark_provider_truth_ready_without_openclaw_oauth(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "MINIMAX_API_KEY": "",
                "MINIMAX_CN_API_KEY": "",
                "OPENAI_API_KEY": "",
                "MINIMAX_OAUTH_TOKEN": "",
                "FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT": "",
                "FLUXIO_DISABLE_WSL_AUTH_DISCOVERY": "1",
                "HERMES_AUTH_STORE": "",
                "HERMES_HOME": "",
            },
            clear=False,
        ), tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            os.environ["HOME"] = str(root)
            os.environ["OPENCLAW_STATE_DIR"] = str(root / ".openclaw")
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspaces = store.load_workspaces()
            workspace = workspaces[0]
            workspace.minimax_auth_mode = "minimax-portal-oauth"
            workspace.route_overrides = [
                {
                    "role": "executor",
                    "provider": "minimax",
                    "model": "MiniMax-M2.7",
                    "effort": "medium",
                }
            ]
            store.save_workspaces(workspaces)

            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="openclaw",
                objective="Route execution through MiniMax",
                success_checks=[],
                mode="Autopilot",
                verification_commands=["python -m unittest"],
                max_runtime_seconds=3600,
            )
            mission.state.current_cycle_phase = "execute"
            mission.effective_route_contract = {
                "roles": [
                    {
                        "role": "executor",
                        "provider": "minimax",
                        "model": "MiniMax-M2.7",
                        "effort": "medium",
                    }
                ]
            }
            store.update_mission(mission)

            snapshot = store.build_snapshot()
            mission_payload = next(
                item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id
            )
            self.assertFalse(mission_payload["providerTruth"]["authPresent"])
            self.assertEqual(
                mission_payload["providerTruth"]["authPath"],
                "MiniMax broker OAuth",
            )
            mission.state.provider_runtime_truth = mission_payload["providerTruth"]
            executor_lane = next(
                item
                for item in mission_control_module._runtime_lane_rows_for_mission(mission)
                if item["role"] == "executor"
            )
            self.assertFalse(executor_lane["authPresent"])
            self.assertEqual(executor_lane["health"], "blocked")
            self.assertIn("MiniMax", executor_lane["blocker"])
            self.assertNotIn("OpenAI Codex coding path", executor_lane["blocker"])

    def test_hermes_auth_store_wsl_probe_ignores_login_banner_noise(self) -> None:
        noisy_stdout = (
            "\x1b[1;31mMessage from Kali developers\x1b[00m\n"
            "This is a minimal installation of Kali Linux.\n"
            "kali-linux\t/home/kali"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            with mock.patch.dict(
                os.environ,
                {
                    "HOME": str(root),
                    "HERMES_AUTH_STORE": "",
                    "HERMES_HOME": "",
                    "FLUXIO_RUNTIME_HOME": "",
                    "SYNTELOS_RUNTIME_HOME": "",
                    "FLUXIO_DISABLE_WSL_AUTH_DISCOVERY": "",
                },
                clear=False,
            ), mock.patch("grant_agent.mission_control.os.name", "nt"), mock.patch(
                "grant_agent.mission_control.subprocess.run",
                return_value=mock.Mock(stdout=noisy_stdout),
            ):
                candidates = mission_control_module.hermes_auth_store_candidates(root)

            candidate_text = "\n".join(str(candidate) for candidate in candidates)
            self.assertIn("kali-linux", candidate_text)
            self.assertIn("home", candidate_text)
            self.assertNotIn("Message from Kali developers", candidate_text)

            with mock.patch.dict(
                os.environ,
                {"HOME": str(root), "FLUXIO_DISABLE_WSL_AUTH_DISCOVERY": ""},
                clear=False,
            ), mock.patch("grant_agent.mission_control.os.name", "nt"), mock.patch(
                "grant_agent.mission_control.subprocess.run",
                return_value=mock.Mock(stdout=None),
            ):
                candidates = mission_control_module.hermes_auth_store_candidates(root)
            self.assertTrue(candidates)

    def test_minimax_portal_auth_marks_provider_truth_ready_with_openclaw_oauth(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "MINIMAX_API_KEY": "",
                "MINIMAX_CN_API_KEY": "",
                "OPENAI_API_KEY": "",
                "FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT": "1",
            },
            clear=False,
        ), tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspaces = store.load_workspaces()
            workspace = workspaces[0]
            workspace.minimax_auth_mode = "minimax-portal-oauth"
            workspace.route_overrides = [
                {
                    "role": "executor",
                    "provider": "minimax",
                    "model": "MiniMax-M2.7",
                    "effort": "medium",
                }
            ]
            store.save_workspaces(workspaces)

            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="openclaw",
                objective="Route execution through MiniMax",
                success_checks=[],
                mode="Autopilot",
                verification_commands=["python -m unittest"],
                max_runtime_seconds=3600,
            )
            mission.state.current_cycle_phase = "execute"
            mission.effective_route_contract = {
                "roles": [
                    {
                        "role": "executor",
                        "provider": "minimax",
                        "model": "MiniMax-M2.7",
                        "effort": "medium",
                    }
                ]
            }
            store.update_mission(mission)

            snapshot = store.build_snapshot()
            mission_payload = next(
                item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id
            )
            self.assertTrue(mission_payload["providerTruth"]["authPresent"])
            self.assertEqual(
                mission_payload["providerTruth"]["authPath"],
                "MiniMax broker OAuth",
            )
            mission.state.provider_runtime_truth = mission_payload["providerTruth"]
            executor_lane = next(
                item
                for item in mission_control_module._runtime_lane_rows_for_mission(mission)
                if item["role"] == "executor"
            )
            self.assertTrue(executor_lane["authPresent"])
            self.assertEqual(executor_lane["authPath"], "MiniMax broker OAuth")
            self.assertEqual(executor_lane["health"], "ready")
            self.assertEqual(executor_lane["blocker"], "")

    def test_minimax_oauth_presence_marks_runtime_lane_ready_even_before_profile_mode_saved(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "MINIMAX_API_KEY": "",
                "MINIMAX_CN_API_KEY": "",
                "OPENAI_API_KEY": "",
                "FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT": "1",
            },
            clear=False,
        ), tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspaces = store.load_workspaces()
            workspace = workspaces[0]
            workspace.minimax_auth_mode = "none"
            workspace.route_overrides = [
                {
                    "role": "executor",
                    "provider": "minimax",
                    "model": "MiniMax-M2.7",
                    "effort": "medium",
                }
            ]
            store.save_workspaces(workspaces)

            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Route execution through Hermes and MiniMax",
                success_checks=[],
                mode="Autopilot",
                verification_commands=["python -m unittest"],
                max_runtime_seconds=3600,
            )
            mission.state.current_cycle_phase = "execute"
            mission.effective_route_contract = {
                "roles": [
                    {
                        "role": "executor",
                        "provider": "minimax",
                        "model": "MiniMax-M2.7",
                        "effort": "medium",
                    }
                ]
            }
            store.update_mission(mission)

            snapshot = store.build_snapshot()
            mission_payload = next(
                item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id
            )
            self.assertTrue(mission_payload["providerTruth"]["authPresent"])
            self.assertEqual(
                mission_payload["providerTruth"]["authPath"],
                "MiniMax broker OAuth",
            )
            mission.state.provider_runtime_truth = mission_payload["providerTruth"]
            executor_lane = next(
                item
                for item in mission_control_module._runtime_lane_rows_for_mission(mission)
                if item["role"] == "executor"
            )
            self.assertTrue(executor_lane["authPresent"])
            self.assertEqual(executor_lane["health"], "ready")
            self.assertEqual(executor_lane["model"], "MiniMax-M3")

    def test_runtime_provider_env_file_marks_minimax_ready_for_cli_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            provider_env = root / ".fluxio_provider_env"
            provider_env.write_text(
                "# private\nexport MINIMAX_API_KEY='test-minimax-key'\n",
                encoding="utf-8",
            )
            with mock.patch.dict(
                os.environ,
                {
                    "MINIMAX_API_KEY": "",
                    "MINIMAX_CN_API_KEY": "",
                    "MINIMAX_OAUTH_TOKEN": "",
                    "FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT": "",
                    "FLUXIO_PROVIDER_ENV_FILE": str(provider_env),
                    "HOME": str(root / "empty-home"),
                    "OPENCLAW_STATE_DIR": str(root / "empty-openclaw"),
                },
                clear=False,
            ):
                (root / "README.md").write_text("# Demo\n", encoding="utf-8")
                store = ControlRoomStore(root)
                workspace = store.load_workspaces()[0]
                workspace.minimax_auth_mode = "minimax-api"
                store.save_workspaces([workspace])
                mission = store.create_mission(
                    workspace_id=workspace.workspace_id,
                    runtime_id="hermes",
                    objective="Route execution through MiniMax",
                    success_checks=[],
                    mode="Autopilot",
                    verification_commands=[],
                    max_runtime_seconds=3600,
                )
                mission.state.current_cycle_phase = "execute"
                mission.effective_route_contract = {
                    "roles": [
                        {
                            "role": "executor",
                            "provider": "minimax",
                            "model": "MiniMax-M2.7",
                            "effort": "medium",
                        }
                    ]
                }
                store.update_mission(mission)

                snapshot = store.build_snapshot()
                mission_payload = next(
                    item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id
                )
                self.assertTrue(mission_payload["providerTruth"]["authPresent"])
                self.assertEqual(mission_payload["providerTruth"]["authPath"], "API key")

                summary = store.build_summary_snapshot()
                summary_row = next(
                    item for item in summary["missions"] if item["mission_id"] == mission.mission_id
                )
                provider_capabilities = summary_row["providerCapabilities"]
                self.assertEqual(
                    provider_capabilities["schema"],
                    "fluxio.provider_capability_contract.v1",
                )
                self.assertEqual(provider_capabilities["laneCount"], 3)
                providers_by_id = {
                    item["provider"]: item for item in provider_capabilities["providers"]
                }
                self.assertTrue(providers_by_id["minimax"]["authPresent"])
                self.assertEqual(providers_by_id["minimax"]["health"], "ready")
                self.assertEqual(providers_by_id["minimax"]["models"], ["MiniMax-M3"])
                self.assertEqual(providers_by_id["minimax"]["readyRoles"], 1)
                self.assertEqual(
                    providers_by_id["minimax"]["quota"]["status"],
                    "unreported",
                )
                self.assertIn("frontend-ui", providers_by_id["minimax"]["toolFamilies"])
                self.assertEqual(providers_by_id["openai-codex"]["health"], "blocked")
                self.assertIn(
                    "auth_missing",
                    providers_by_id["openai-codex"]["failureClasses"],
                )
                self.assertEqual(provider_capabilities["quotaSummary"]["unreportedProviders"], 1)
                self.assertIn("code-edit", provider_capabilities["toolSummary"]["families"])
                executor_lane = next(
                    item for item in summary_row["runtimeLanes"] if item["role"] == "executor"
                )
                self.assertTrue(executor_lane["authPresent"])
                self.assertEqual(executor_lane["authPath"], "API key")
                self.assertEqual(executor_lane["health"], "ready")
                self.assertEqual(executor_lane["quota"]["schema"], "fluxio.provider_quota_truth.v1")

    def test_release_adjacent_runtime_codex_auth_marks_planner_ready_for_cli_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            release_root = (
                pathlib.Path(temp_dir)
                / "syntelos"
                / "releases"
                / "20260505-212517"
            )
            runtime_home = pathlib.Path(temp_dir) / "syntelos" / "runtime" / "home"
            codex_home = runtime_home / ".codex"
            codex_home.mkdir(parents=True)
            (codex_home / "auth.json").write_text(
                json.dumps(
                    {
                        "OPENAI_API_KEY": None,
                        "auth_mode": "chatgpt",
                        "tokens": {"access_token": "token"},
                    }
                ),
                encoding="utf-8",
            )
            release_root.mkdir(parents=True)
            (release_root / "README.md").write_text("# Demo\n", encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "",
                    "FLUXIO_OPENAI_CODEX_OAUTH_PRESENT": "",
                    "HOME": str(pathlib.Path(temp_dir) / "missing-home"),
                    "OPENCLAW_STATE_DIR": str(pathlib.Path(temp_dir) / "missing-openclaw"),
                },
                clear=False,
            ), mock.patch.object(mission_control_module.Path, "cwd", return_value=release_root):
                store = ControlRoomStore(release_root)
                workspace = store.load_workspaces()[0]
                workspace.openai_codex_auth_mode = "oauth"
                store.save_workspaces([workspace])
                mission = store.create_mission(
                    workspace_id=workspace.workspace_id,
                    runtime_id="hermes",
                    objective="Route planning through Codex",
                    success_checks=[],
                    mode="Autopilot",
                    verification_commands=[],
                    max_runtime_seconds=3600,
                )
                mission.state.current_cycle_phase = "plan"
                mission.effective_route_contract = {
                    "roles": [
                        {
                            "role": "planner",
                            "provider": "openai-codex",
                            "model": "gpt-5.5",
                            "effort": "high",
                        }
                    ]
                }
                store.update_mission(mission)

                summary = store.build_summary_snapshot()
                row = next(item for item in summary["missions"] if item["mission_id"] == mission.mission_id)
                planner_lane = next(item for item in row["runtimeLanes"] if item["role"] == "planner")
                self.assertTrue(planner_lane["authPresent"])
                self.assertEqual(planner_lane["authPath"], "OpenAI Codex OAuth")
                self.assertEqual(planner_lane["health"], "ready")

    def test_summary_reconciles_stale_mission_route_contract_from_workspace_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            workspace.route_overrides = [
                {
                    "role": "planner",
                    "provider": "openai-codex",
                    "model": "gpt-5.5",
                    "effort": "high",
                    "budgetClass": "premium",
                },
                {
                    "role": "executor",
                    "provider": "minimax",
                    "model": "MiniMax-M2.7",
                    "effort": "high",
                    "budgetClass": "specialist",
                },
                {
                    "role": "verifier",
                    "provider": "openai-codex",
                    "model": "gpt-5.5",
                    "effort": "high",
                    "budgetClass": "premium",
                },
            ]
            store.save_workspaces([workspace])
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Use stale launch-time route then upgrade it",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.route_configs = [
                {
                    "role": "planner",
                    "provider": "openai-codex",
                    "model": "gpt-5.3-codex",
                    "effort": "high",
                    "budget_class": "specialist",
                    "explanation": "Route override from workspace runtime contract.",
                    "route_intent": "manual_workspace_override",
                },
                {
                    "role": "executor",
                    "provider": "minimax",
                    "model": "MiniMax-M2.7",
                    "effort": "medium",
                    "budget_class": "specialist",
                    "explanation": "Route override from workspace runtime contract.",
                    "route_intent": "manual_workspace_override",
                },
                {
                    "role": "verifier",
                    "provider": "openai",
                    "model": "gpt-5.5",
                    "effort": "high",
                    "budget_class": "premium",
                    "explanation": "Route override from workspace runtime contract.",
                    "route_intent": "manual_workspace_override",
                },
            ]
            mission.effective_route_contract = {}
            store.update_mission(mission)

            summary = store.build_summary_snapshot()
            row = next(item for item in summary["missions"] if item["mission_id"] == mission.mission_id)
            lanes = {item["role"]: item for item in row["runtimeLanes"]}

            self.assertEqual(lanes["planner"]["model"], "gpt-5.5")
            self.assertEqual(lanes["planner"]["provider"], "openai-codex")
            self.assertEqual(lanes["executor"]["effort"], "high")
            self.assertEqual(lanes["verifier"]["provider"], "openai-codex")

            store.build_snapshot()
            refreshed = next(item for item in store.load_missions() if item.mission_id == mission.mission_id)
            refreshed_routes = {item["role"]: item for item in refreshed.route_configs}
            self.assertEqual(refreshed_routes["planner"]["model"], "gpt-5.5")
            self.assertEqual(refreshed_routes["executor"]["effort"], "high")
            self.assertEqual(refreshed_routes["verifier"]["provider"], "openai-codex")

    def test_second_mission_is_queued_behind_active_workspace_mission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            first = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="openclaw",
                objective="First mission owns the workspace",
                success_checks=[],
                mode="Autopilot",
                verification_commands=["python -m unittest"],
                max_runtime_seconds=3600,
            )
            second = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Second mission should queue",
                success_checks=[],
                mode="Autopilot",
                verification_commands=["python -m unittest"],
                max_runtime_seconds=3600,
            )

            self.assertEqual(first.state.queue_position, 0)
            self.assertEqual(second.state.queue_position, 1)
            self.assertEqual(second.state.blocking_mission_id, first.mission_id)
            self.assertIn("active slot", second.state.queue_reason)

            snapshot = store.build_snapshot()
            self.assertEqual(snapshot["workspaces"][0]["activeMissionId"], first.mission_id)
            self.assertEqual(snapshot["workspaces"][0]["queuedMissionCount"], 1)

    def test_completed_active_mission_promotes_next_queued_mission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            first = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="openclaw",
                objective="First mission owns the workspace",
                success_checks=[],
                mode="Autopilot",
                verification_commands=["python -m unittest"],
                max_runtime_seconds=3600,
            )
            second = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Second mission should queue",
                success_checks=[],
                mode="Autopilot",
                verification_commands=["python -m unittest"],
                max_runtime_seconds=3600,
            )

            first.state.status = "completed"
            store.update_mission(first)
            store.rebalance_mission_queue(workspace.workspace_id)

            promoted = store.get_mission(second.mission_id)
            self.assertEqual(promoted.state.queue_position, 0)
            self.assertIsNone(promoted.state.blocking_mission_id)
            self.assertEqual(promoted.state.queue_reason, "")
            self.assertIn("front of the workspace queue", promoted.proof.summary)

    def test_mode_mapping_matches_desktop_vocabulary(self) -> None:
        self.assertEqual(mission_mode_to_engine_mode("Focus"), "fast")
        self.assertEqual(mission_mode_to_engine_mode("Autopilot"), "autopilot")
        self.assertEqual(mission_mode_to_engine_mode("Deep Run"), "deep_run")
        self.assertEqual(mission_mode_to_engine_mode("Research"), "swarms")

    def test_mission_title_strips_prompt_filler_and_keeps_codex_style_name(self) -> None:
        self.assertEqual(
            _mission_title("Please tighten Fluxio trust story and import Codex sessions."),
            "Tighten Fluxio trust story import Codex",
        )
        self.assertEqual(
            _mission_title("Can you repair restart continuity for delegated approvals?"),
            "Repair restart continuity delegated approvals",
        )

    def test_setup_verify_action_persists_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)

            payload = execute_control_room_workspace_action(
                store=store,
                root=root,
                surface="setup",
                action_id="verify_setup_health",
            )

            self.assertIn("snapshot", payload)
            self.assertIn("actionHistory", payload["snapshot"]["setupHealth"])
            self.assertEqual(
                payload["snapshot"]["setupHealth"]["actionHistory"][-1]["proposal"]["args"]["workspaceActionId"],
                "verify_setup_health",
            )

    def test_setup_telegram_action_persists_destination_and_updates_health(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            with mock.patch.dict(
                os.environ,
                {"FLUXIO_TELEGRAM_DESTINATION": "@fluxio_test"},
                clear=False,
            ):
                payload = execute_control_room_workspace_action(
                    store=store,
                    root=root,
                    surface="setup",
                    action_id="configure_telegram_destination",
                    workspace_id=workspace.workspace_id,
                    approved=False,
                )

            self.assertTrue(payload["ok"])
            telegram_settings_path = root / ".agent_control" / "telegram_settings.json"
            self.assertTrue(telegram_settings_path.exists())
            telegram_settings = json.loads(telegram_settings_path.read_text(encoding="utf-8"))
            self.assertEqual(telegram_settings["destination"], "@fluxio_test")
            self.assertTrue(payload["snapshot"]["setupHealth"]["telegramReady"])
            self.assertEqual(
                payload["record"]["result"]["payload"]["dependencyId"],
                "telegram_ready",
            )

    def test_setup_telegram_action_detects_openclaw_telegram_allow_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            fake_home = root / "fake-home"
            openclaw_dir = fake_home / ".openclaw"
            openclaw_dir.mkdir(parents=True, exist_ok=True)
            (openclaw_dir / "openclaw.json").write_text(
                json.dumps(
                    {
                        "tools": {
                            "elevated": {
                                "allowFrom": {
                                    "telegram": [6528735547],
                                }
                            }
                        }
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            with mock.patch("grant_agent.workspace_actions.Path.home", return_value=fake_home):
                with mock.patch.dict(
                    os.environ,
                    {
                        "FLUXIO_TELEGRAM_DESTINATION": "",
                        "TELEGRAM_CHAT_ID": "",
                        "TELEGRAM_DESTINATION": "",
                    },
                    clear=False,
                ):
                    payload = execute_control_room_workspace_action(
                        store=store,
                        root=root,
                        surface="setup",
                        action_id="configure_telegram_destination",
                        workspace_id=workspace.workspace_id,
                        approved=False,
                    )

            self.assertTrue(payload["ok"])
            self.assertEqual(
                payload["record"]["result"]["payload"]["telegramDestination"],
                "6528735547",
            )
            self.assertTrue(payload["snapshot"]["setupHealth"]["telegramReady"])

    def test_snapshot_surfaces_continuity_and_action_source_kind(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="openclaw",
                objective="Recover a delegated approval after restart",
                success_checks=[],
                mode="Autopilot",
                verification_commands=["python -m unittest"],
                max_runtime_seconds=3600,
            )
            runtime_dir = root / ".agent_control" / "runtime_sessions"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            session_path = runtime_dir / "delegate_demo.json"
            session = DelegatedRuntimeSession(
                delegated_id="delegate_demo",
                runtime_id="openclaw",
                launch_command="python -V",
                status="waiting_for_approval",
                detail="Delegated runtime is waiting for approval.",
                session_path=str(session_path),
                events_path=str(runtime_dir / "delegate_demo.events.jsonl"),
                decision_path=str(runtime_dir / "delegate_demo.approval.json"),
                pending_approval={
                    "request_id": "approval_demo",
                    "prompt": "Approve delegated deploy simulation?",
                    "status": "pending",
                },
                approval_history=[
                    {
                        "request_id": "approval_previous",
                        "status": "approved",
                        "resolved_by": "operator",
                    }
                ],
            )
            session_path.write_text(json.dumps(asdict(session), indent=2), encoding="utf-8")
            mission.delegated_runtime_sessions = [session]
            mission.action_history = [
                {
                    "action_id": "action_delegate",
                    "proposal": {
                        "kind": "runtime_delegate",
                        "title": "Delegate work to OpenClaw",
                    },
                    "gate": {"status": "not_required"},
                    "result": {"result_summary": "Delegated lane launched."},
                },
                {
                    "action_id": "action_local",
                    "proposal": {
                        "kind": "file_patch",
                        "title": "Patch a local file",
                    },
                    "gate": {"status": "not_required"},
                    "result": {"result_summary": "Patched app.js."},
                },
            ]
            store.update_mission(mission)

            snapshot = store.build_snapshot()
            mission_payload = next(
                item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id
            )

            self.assertEqual(mission_payload["missionLoop"]["continuityState"], "approval_waiting")
            self.assertEqual(
                mission_payload["state"]["pending_approval_payload"]["prompt"],
                "Approve delegated deploy simulation?",
            )
            self.assertEqual(
                mission_payload["missionLoop"]["pauseReason"],
                "Approve delegated deploy simulation?",
            )
            self.assertEqual(
                mission_payload["state"]["last_budget_pause_reason"],
                "Approve delegated deploy simulation?",
            )
            self.assertEqual(
                mission_payload["missionLoop"]["currentRuntimeLane"],
                "openclaw delegated lane waiting for approval",
            )
            self.assertEqual(
                mission_payload["state"]["current_runtime_lane"],
                "openclaw delegated lane waiting for approval",
            )
            self.assertEqual(
                mission_payload["action_history"][0]["proposal"]["sourceKind"],
                "delegated",
            )
            self.assertEqual(
                mission_payload["action_history"][1]["proposal"]["sourceKind"],
                "local",
            )
            receipts_path = root / ".agent_control" / "delivery_receipts.jsonl"
            self.assertTrue(receipts_path.exists())
            receipt_lines = receipts_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(receipt_lines), 1)
            receipt = json.loads(receipt_lines[0])
            self.assertEqual(receipt["mission_id"], mission.mission_id)
            self.assertEqual(receipt["event_kind"], "approval.required")
            self.assertIn(receipt["status"], {"skipped", "delivered", "error"})

            snapshot = store.build_snapshot()
            receipt_lines_after_refresh = receipts_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(receipt_lines_after_refresh), 1)
            mission_payload_after_refresh = next(
                item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id
            )
            self.assertEqual(
                len(mission_payload_after_refresh["escalation_policy"]["delivery_receipts"]),
                1,
            )

    def test_snapshot_surfaces_time_budget_and_run_until_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep running until the budget or a hard blocker stops the mission",
                success_checks=[],
                mode="Deep Run",
                verification_commands=["python -m unittest"],
                max_runtime_seconds=7200,
                run_until_behavior="continue_until_blocked",
            )
            store.update_mission(mission)

            snapshot = store.build_snapshot()
            mission_payload = next(
                item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id
            )

            self.assertEqual(
                mission_payload["run_budget"]["run_until_behavior"],
                "continue_until_blocked",
            )
            self.assertEqual(
                mission_payload["missionLoop"]["timeBudget"]["runUntilBehavior"],
                "continue_until_blocked",
            )
            self.assertGreater(
                mission_payload["missionLoop"]["timeBudget"]["remainingSeconds"],
                0,
            )
            self.assertEqual(
                mission_payload["missionLoop"]["currentRuntimeLane"],
                "hermes primary lane queued",
            )

    def test_mission_time_budget_window_prefers_explicit_deadline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Work through the night until 8 a.m.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=["python -m unittest"],
                max_runtime_seconds=3600,
                run_until_behavior="continue_until_blocked",
                deadline_at="2026-04-17T08:00:00+00:00",
            )
            mission.created_at = "2026-04-16T22:00:00+00:00"

            budget_window = mission_time_budget_window(
                mission,
                now=datetime(2026, 4, 17, 1, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(budget_window["maxRuntimeSeconds"], 36000)
            self.assertEqual(budget_window["elapsedSeconds"], 10800)
            self.assertEqual(budget_window["remainingSeconds"], 25200)
            self.assertEqual(
                budget_window["deadlineAt"],
                "2026-04-17T08:00:00+00:00",
            )

    def test_snapshot_workflows_and_services_reflect_setup_and_runtime_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            (root / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")
            (root / "src-tauri").mkdir()
            store = ControlRoomStore(root)

            snapshot = store.build_snapshot()
            workflow_map = {
                item["workflowId"]: item for item in snapshot["workflowStudio"]["recipes"]
            }
            workspace = snapshot["workspaces"][0]
            service_summary = workspace["serviceManagementSummary"]

            self.assertIn("setup_repair", workflow_map)
            self.assertIn("agent_long_run", workflow_map)
            self.assertIn("nas_bridge_run", workflow_map)
            self.assertEqual(workspace["default_runtime"], "hermes")
            self.assertEqual(workflow_map["agent_long_run"]["runtimeChoice"], "hermes")
            self.assertEqual(workflow_map["nas_bridge_run"]["runtimeChoice"], "hermes")
            self.assertEqual(workflow_map["nas_bridge_run"]["reviewStatus"], "reviewed")
            self.assertEqual(workflow_map["setup_repair"]["status"], "blocked")
            self.assertEqual(workflow_map["setup_repair"]["reviewStatus"], "reviewed")
            self.assertGreaterEqual(len(workflow_map["setup_repair"]["serviceIds"]), 1)
            self.assertEqual(
                workflow_map["agent_long_run"]["verificationDefaults"],
                [
                    "python -m pytest tests -q",
                    "npm run frontend:build",
                    "npm run tauri build -- --debug",
                ],
            )
            self.assertGreaterEqual(service_summary["runtimeCount"], 2)
            self.assertGreaterEqual(service_summary["toolServerCount"], 1)
            self.assertIn("serviceManagement", workspace)
            self.assertIn(
                "runtime",
                {
                    item["serviceCategory"]
                    for item in workspace["serviceManagement"]
                },
            )

    def test_harness_lab_snapshot_reports_efficiency_and_session_health(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            runs_root = root / ".agent_runs"
            session_one = runs_root / "session_one"
            session_two = runs_root / "session_two"
            session_one.mkdir(parents=True)
            session_two.mkdir(parents=True)
            (session_one / "state.json").write_text(
                json.dumps(
                    {
                        "harness_id": "fluxio_hybrid",
                        "runtime_id": "hermes",
                        "autopilot_status": "completed",
                        "autopilot_pause_reason": "",
                        "verification_failures": [],
                        "delegated_runtime_sessions": [{"delegated_id": "delegate_one"}],
                        "action_history": [{}, {}, {}],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            (session_two / "state.json").write_text(
                json.dumps(
                    {
                        "harness_id": "fluxio_hybrid",
                        "runtime_id": "openclaw",
                        "autopilot_status": "paused",
                        "autopilot_pause_reason": "approval_required",
                        "verification_failures": ["npm run frontend:build"],
                        "delegated_runtime_sessions": [],
                        "action_history": [{}],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            runtime_root = root / ".agent_control" / "runtime_sessions"
            runtime_root.mkdir(parents=True)
            (runtime_root / "delegate_one.json").write_text(
                json.dumps(
                    {
                        "delegated_id": "delegate_one",
                        "runtime_id": "hermes",
                        "launch_command": "python -V",
                        "status": "running",
                        "heartbeat_status": "healthy",
                        "heartbeat_at": utc_now_iso(),
                        "heartbeat_interval_seconds": 10,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            snapshot = build_harness_lab_snapshot(root)

            self.assertEqual(snapshot["efficiency"]["totalRuns"], 2)
            self.assertEqual(snapshot["efficiency"]["completionRate"], 50)
            self.assertEqual(snapshot["efficiency"]["approvalPauseRate"], 50)
            self.assertEqual(snapshot["efficiency"]["delegatedRunRate"], 50)
            self.assertEqual(snapshot["efficiency"]["resumeRunRate"], 0)
            self.assertEqual(snapshot["efficiency"]["resumeCompletionRate"], 0)
            self.assertEqual(snapshot["efficiency"]["runtimeBudgetPauseRate"], 0)
            self.assertEqual(snapshot["efficiency"]["delegatedActivePauseRate"], 0)
            self.assertEqual(snapshot["sessionHealth"]["activeCount"], 1)
            self.assertEqual(snapshot["sessionHealth"]["healthyHeartbeatCount"], 1)
            self.assertEqual(snapshot["sessionHealth"]["delegatedHealthyCount"], 1)
            self.assertEqual(snapshot["sessionHealth"]["delegatedStaleCount"], 0)
            self.assertIn("Approval waits dominate", snapshot["recommendation"])

    def test_harness_lab_session_health_does_not_count_orphaned_runtime_pid_as_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            runtime_root = root / ".agent_control" / "runtime_sessions"
            runtime_root.mkdir(parents=True)
            (runtime_root / "delegate_orphaned.json").write_text(
                json.dumps(
                    {
                        "delegated_id": "delegate_orphaned",
                        "runtime_id": "hermes",
                        "status": "running",
                        "heartbeat_status": "healthy",
                        "heartbeat_at": "2026-01-01T00:00:00+00:00",
                        "heartbeat_interval_seconds": 10,
                        "pid": 99999999,
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch("grant_agent.mission_control._runtime_pid_alive", return_value=False):
                snapshot = build_harness_lab_snapshot(root)

            self.assertEqual(snapshot["sessionHealth"]["activeCount"], 0)
            self.assertEqual(snapshot["sessionHealth"]["staleHeartbeatCount"], 0)
            self.assertEqual(snapshot["sessionHealth"]["delegatedStaleCount"], 0)
            self.assertEqual(snapshot["sessionHealth"]["orphanedActiveCount"], 1)

    def test_summary_harness_lab_uses_mission_session_index_without_full_runtime_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep the delegated runtime loop observable.",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=1800,
            )
            mission.state.status = "running"
            mission.delegated_runtime_sessions.append(
                DelegatedRuntimeSession(
                    delegated_id="delegate_summary",
                    runtime_id="hermes",
                    launch_command="python -m grant_agent.runtime_worker",
                    status="running",
                    heartbeat_status="healthy",
                    heartbeat_at=utc_now_iso(),
                    heartbeat_interval_seconds=10,
                )
            )
            store.update_mission(mission)
            runtime_root = root / ".agent_control" / "runtime_sessions"
            runtime_root.mkdir(parents=True)
            for index in range(120):
                (runtime_root / f"delegate_old_{index}.json").write_text(
                    json.dumps(
                        {
                            "delegated_id": f"delegate_old_{index}",
                            "status": "running",
                            "heartbeat_status": "stale",
                        }
                    ),
                    encoding="utf-8",
                )

            summary = build_summary_harness_lab_snapshot(root, missions=store.load_missions())

            self.assertEqual(summary["source"], "mission_store_delegated_sessions_summary")
            self.assertTrue(summary["fullSessionScanDeferred"])
            self.assertEqual(
                summary["sessionHealth"]["schema"],
                "fluxio.runtime_session_health.summary.v1",
            )
            self.assertEqual(
                summary["sessionHealth"]["source"],
                "mission_store_delegated_sessions",
            )
            self.assertEqual(summary["sessionHealth"]["totalSessions"], 1)
            self.assertEqual(summary["sessionHealth"]["activeCount"], 1)
            self.assertEqual(summary["sessionHealth"]["delegatedHealthyCount"], 1)
            self.assertEqual(summary["sessionHealth"]["delegatedStaleCount"], 0)

    def test_release_readiness_snapshot_scores_required_gates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "web" / "src" / "fluxio").mkdir(parents=True)
            (root / "src-tauri").mkdir(parents=True)
            (root / "web" / "src" / "main.tsx").write_text(
                "export {};\n",
                encoding="utf-8",
            )
            (root / "web" / "src" / "fluxio" / "FluxioApp.tsx").write_text(
                "export function FluxioApp() { return null; }\n",
                encoding="utf-8",
            )
            (root / "web" / "src" / "fluxio" / "fluxioBridge.ts").write_text(
                "export const bridge = {};\n",
                encoding="utf-8",
            )
            (root / "vite.config.mjs").write_text(
                'export default { root: "web" };\n',
                encoding="utf-8",
            )
            (root / "src-tauri" / "tauri.conf.json").write_text(
                '{"build":{"frontendDist":"../web/dist"}}\n',
                encoding="utf-8",
            )
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {
                            "verify:desktop": (
                                "python -m pytest tests -q && "
                                "npm run frontend:build && "
                                "npm run tauri build -- --debug"
                            )
                        }
                    }
                ),
                encoding="utf-8",
            )
            onboarding = {
                "checks": {
                    "uv": {"installed": True, "details": "ok"},
                    "openclaw": {"installed": True, "details": "ok"},
                    "hermes": {"installed": True, "details": "ok"},
                },
                "nextActions": [],
            }
            setup_health = {
                "serviceManagementSummary": {
                    "totalItems": 4,
                    "healthyCount": 4,
                }
            }
            harness_lab = {
                "efficiency": {
                    "completionRate": 75,
                    "delegatedRunRate": 40,
                    "resumeRunRate": 25,
                    "resumeCompletionRate": 70,
                    "verificationPauseRate": 10,
                },
                "sessionHealth": {"staleHeartbeatCount": 0},
            }

            readiness = build_release_readiness_snapshot(
                root,
                onboarding=onboarding,
                setup_health=setup_health,
                harness_lab=harness_lab,
            )

            self.assertEqual(readiness["status"], "ready_for_1_0_validation")
            self.assertEqual(
                readiness["requiredGateSummary"]["passed"],
                readiness["requiredGateSummary"]["total"],
            )
            self.assertGreaterEqual(readiness["score"], 90)
            self.assertIn("proofReadiness", readiness)
            self.assertFalse(readiness["proofReadiness"]["ready"])

    def test_release_quality_counts_live_continuity_without_erasing_terminal_completion(self) -> None:
        quality = mission_control_module._release_quality_score(
            completion_rate=45,
            completed_or_continuing_rate=75,
            delegated_run_rate=40,
            resume_run_rate=95,
            resume_completion_rate=47,
            resume_completed_or_continuing_rate=79,
            verification_pause_rate=0,
        )

        self.assertEqual(quality, 84)

    def test_summary_harness_lab_reports_completed_or_continuing_live_missions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            completed = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Completed Hermes proof",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            completed.state.status = "completed"
            completed.current_plan_revision_id = "plan_completed"
            completed.delegated_runtime_sessions = [
                DelegatedRuntimeSession(
                    delegated_id="delegate_completed",
                    runtime_id="hermes",
                    launch_command="hermes",
                    status="completed",
                )
            ]
            store.update_mission(completed)
            running = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Ongoing Hermes proof",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            running.state.status = "running"
            running.state.planner_loop_status = "running"
            running.current_plan_revision_id = "plan_running"
            running.delegated_runtime_sessions = [
                DelegatedRuntimeSession(
                    delegated_id="delegate_running",
                    runtime_id="hermes",
                    launch_command="hermes",
                    status="running",
                )
            ]
            store.update_mission(running)

            summary = build_summary_harness_lab_snapshot(root, missions=store.load_missions())
            efficiency = summary["efficiency"]

            self.assertEqual(efficiency["completionRate"], 50)
            self.assertEqual(efficiency["completedOrContinuingRate"], 100)
            self.assertEqual(efficiency["resumeCompletionRate"], 50)
            self.assertEqual(efficiency["resumeCompletedOrContinuingRate"], 100)

    def test_release_readiness_reports_release_proof_ci_signal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "web" / "src" / "fluxio").mkdir(parents=True)
            (root / "src-tauri").mkdir(parents=True)
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / "scripts").mkdir(parents=True)
            (root / "web" / "src" / "main.tsx").write_text("export {};\n", encoding="utf-8")
            (root / "web" / "src" / "fluxio" / "FluxioApp.tsx").write_text(
                "export function FluxioApp() { return null; }\n",
                encoding="utf-8",
            )
            (root / "web" / "src" / "fluxio" / "fluxioBridge.ts").write_text(
                "export const bridge = {};\n",
                encoding="utf-8",
            )
            (root / "vite.config.mjs").write_text('export default { root: "web" };\n', encoding="utf-8")
            (root / "src-tauri" / "tauri.conf.json").write_text(
                '{"build":{"frontendDist":"../web/dist"}}\n',
                encoding="utf-8",
            )
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {
                            "verify:desktop": (
                                "python -m pytest tests -q && "
                                "npm run frontend:build && "
                                "npm run tauri build -- --debug"
                            ),
                            "verify:web-distribution": "python scripts/verify_public_web_distribution.py",
                            "verify:self-improvement": "python scripts/verify_self_improvement_evidence.py --write",
                        }
                    }
                ),
                encoding="utf-8",
            )
            (root / "scripts" / "verify_public_web_distribution.py").write_text(
                'print("fluxio.public_web_distribution.v1")\n',
                encoding="utf-8",
            )
            (root / "scripts" / "verify_self_improvement_evidence.py").write_text(
                'print("fluxio.self_improvement_evidence.v1")\n',
                encoding="utf-8",
            )
            (root / "scripts" / "archive_release_proofs.py").write_text(
                'LABEL = "self_improvement_evidence"\n',
                encoding="utf-8",
            )
            (root / ".github" / "workflows" / "web-pages.yml").write_text(
                "\n".join(
                    [
                        "steps:",
                        "  - run: npm run frontend:build",
                        "  - run: npm run verify:web-distribution -- --require-built-dist",
                        "  - uses: actions/upload-pages-artifact@v3",
                        "    with:",
                        "      path: web/dist",
                        "  - id: deployment",
                        "    uses: actions/deploy-pages@v4",
                        "environment:",
                        "  url: ${{ steps.deployment.outputs.page_url }}",
                        "  - run: echo fluxio.public_web_deployment.v1 > .agent_control/deployment_evidence/public-web.json",
                        "  - uses: actions/upload-artifact@v4",
                        "    with:",
                        "      name: fluxio-public-web-deployment",
                        "      path: .agent_control/deployment_evidence/public-web.json",
                    ]
                ),
                encoding="utf-8",
            )
            (root / ".github" / "workflows" / "release-proof.yml").write_text(
                "\n".join(
                    [
                        "steps:",
                        "  - run: npm run frontend:build",
                        "  - run: npm run verify:long-history",
                        "  - run: npm run verify:self-improvement",
                        "  - run: python -c \"from pathlib import Path; Path('.agent_control/proof_digests/ci-release-proof.md').write_text('ok')\"",
                        "  - run: npm run verify:release-artifacts",
                        "  - uses: actions/upload-artifact@v4",
                        "    with:",
                        "      path: |",
                        "        .agent_control/release_artifacts/**",
                        "        .agent_control/self_improvement_evidence/**",
                        "        tmp-ui-checks/**",
                    ]
                ),
                encoding="utf-8",
            )
            readiness = build_release_readiness_snapshot(
                root,
                onboarding={
                    "checks": {
                        "uv": {"installed": True, "details": "ok"},
                        "openclaw": {"installed": True, "details": "ok"},
                        "hermes": {"installed": True, "details": "ok"},
                    }
                },
                setup_health={"serviceManagementSummary": {"totalItems": 1, "healthyCount": 1}},
                harness_lab={
                    "efficiency": {
                        "completionRate": 0,
                        "delegatedRunRate": 0,
                        "resumeRunRate": 0,
                        "resumeCompletionRate": 0,
                        "verificationPauseRate": 0,
                    },
                    "sessionHealth": {"staleHeartbeatCount": 0},
                },
            )

            ci_gate = next(item for item in readiness["gates"] if item["gateId"] == "release_artifact_ci")
            self.assertFalse(ci_gate["required"])
            self.assertTrue(ci_gate["passed"])
            self.assertIn("uploads evidence", ci_gate["details"])
            public_web_gate = next(
                item for item in readiness["gates"] if item["gateId"] == "public_web_distribution"
            )
            self.assertFalse(public_web_gate["required"])
            self.assertTrue(public_web_gate["passed"])
            self.assertIn("public web deploy", public_web_gate["details"])
            self_improvement_gate = next(
                item for item in readiness["gates"] if item["gateId"] == "self_improvement_evidence"
            )
            self.assertFalse(self_improvement_gate["required"])
            self.assertTrue(self_improvement_gate["passed"])
            self.assertIn("archived with release proof", self_improvement_gate["details"])

    def test_release_readiness_accepts_dynamic_vite_web_root_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "web" / "src" / "fluxio").mkdir(parents=True)
            (root / "src-tauri").mkdir()
            (root / "web" / "src" / "main.tsx").write_text(
                "export {};\n",
                encoding="utf-8",
            )
            (root / "web" / "src" / "fluxio" / "FluxioApp.tsx").write_text(
                "export function FluxioApp() { return null; }\n",
                encoding="utf-8",
            )
            (root / "web" / "src" / "fluxio" / "fluxioBridge.ts").write_text(
                "export const bridge = {};\n",
                encoding="utf-8",
            )
            (root / "vite.config.mjs").write_text(
                (
                    'import { resolve } from "node:path";\n'
                    'const repoRoot = process.cwd();\n'
                    'const webRoot = resolve(repoRoot, "web");\n'
                    "export default {\n"
                    "  root: webRoot,\n"
                    "};\n"
                ),
                encoding="utf-8",
            )
            (root / "src-tauri" / "tauri.conf.json").write_text(
                '{"build":{"frontendDist":"../web/dist"}}\n',
                encoding="utf-8",
            )
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {
                            "verify:desktop": (
                                "python -m pytest tests -q && "
                                "npm run frontend:build && "
                                "npm run tauri build -- --debug"
                            )
                        }
                    }
                ),
                encoding="utf-8",
            )
            onboarding = {
                "checks": {
                    "uv": {"installed": True, "details": "ok"},
                    "openclaw": {"installed": True, "details": "ok"},
                    "hermes": {"installed": True, "details": "ok"},
                },
                "nextActions": [],
            }
            setup_health = {
                "serviceManagementSummary": {
                    "totalItems": 4,
                    "healthyCount": 4,
                }
            }
            harness_lab = {
                "efficiency": {
                    "completionRate": 75,
                    "delegatedRunRate": 40,
                    "resumeRunRate": 25,
                    "resumeCompletionRate": 70,
                    "verificationPauseRate": 10,
                },
                "sessionHealth": {"staleHeartbeatCount": 0},
            }

            readiness = build_release_readiness_snapshot(
                root,
                onboarding=onboarding,
                setup_health=setup_health,
                harness_lab=harness_lab,
            )

            alignment_gate = next(
                item
                for item in readiness["gates"]
                if item["gateId"] == "frontend_source_alignment"
            )
            self.assertTrue(alignment_gate["passed"])

    def test_release_readiness_reports_proof_readiness_when_missions_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "web" / "src" / "fluxio").mkdir(parents=True)
            (root / "src-tauri").mkdir(parents=True)
            (root / "web" / "src" / "main.tsx").write_text(
                "export {};\n",
                encoding="utf-8",
            )
            (root / "web" / "src" / "fluxio" / "FluxioApp.tsx").write_text(
                "export function FluxioApp() { return null; }\n",
                encoding="utf-8",
            )
            (root / "web" / "src" / "fluxio" / "fluxioBridge.ts").write_text(
                "export const bridge = {};\n",
                encoding="utf-8",
            )
            (root / "vite.config.mjs").write_text(
                'export default { root: "web" };\n',
                encoding="utf-8",
            )
            (root / "src-tauri" / "tauri.conf.json").write_text(
                '{"build":{"frontendDist":"../web/dist"}}\n',
                encoding="utf-8",
            )
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {
                            "verify:desktop": (
                                "python -m pytest tests -q && "
                                "npm run frontend:build && "
                                "npm run tauri build -- --debug"
                            )
                        }
                    }
                ),
                encoding="utf-8",
            )
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True, exist_ok=True)
            (control_dir / "missions.json").write_text(
                json.dumps(
                    [
                        {
                            "runtime_id": "openclaw",
                            "state": {
                                "status": "completed",
                                "continuity_state": "terminal",
                            },
                        },
                        {
                            "runtime_id": "hermes",
                            "state": {
                                "status": "completed",
                                "continuity_state": "terminal",
                            },
                        },
                        {
                            "runtime_id": "hermes",
                            "state": {
                                "status": "needs_approval",
                                "continuity_state": "approval_waiting",
                            },
                        },
                        {
                            "runtime_id": "hermes",
                            "state": {
                                "status": "running",
                                "continuity_state": "delegated_active",
                                "time_budget_status": "delegated_active",
                            },
                        },
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )
            self._write_clear_watchdog_release_evidence(root)
            onboarding = {
                "checks": {
                    "uv": {"installed": True, "details": "ok"},
                    "openclaw": {"installed": True, "details": "ok"},
                    "hermes": {"installed": True, "details": "ok"},
                },
                "nextActions": [],
            }
            setup_health = {
                "serviceManagementSummary": {
                    "totalItems": 4,
                    "healthyCount": 4,
                }
            }
            harness_lab = {
                "efficiency": {
                    "completionRate": 75,
                    "delegatedRunRate": 40,
                    "resumeRunRate": 25,
                    "resumeCompletionRate": 70,
                    "verificationPauseRate": 10,
                },
                "sessionHealth": {"staleHeartbeatCount": 0},
            }

            readiness = build_release_readiness_snapshot(
                root,
                onboarding=onboarding,
                setup_health=setup_health,
                harness_lab=harness_lab,
            )

            self.assertTrue(readiness["proofReadiness"]["ready"])
            proof_gate_ids = {item["gateId"] for item in readiness["gates"]}
            self.assertIn("proof_openclaw_completed", proof_gate_ids)
            self.assertIn("proof_hermes_completed", proof_gate_ids)

    def test_release_readiness_requires_clear_watchdog_for_active_missions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "web" / "src" / "fluxio").mkdir(parents=True)
            (root / "src-tauri").mkdir(parents=True)
            (root / "web" / "src" / "main.tsx").write_text("export {};\n", encoding="utf-8")
            (root / "web" / "src" / "fluxio" / "FluxioApp.tsx").write_text(
                "export function FluxioApp() { return null; }\n",
                encoding="utf-8",
            )
            (root / "web" / "src" / "fluxio" / "fluxioBridge.ts").write_text(
                "export const bridge = {};\n",
                encoding="utf-8",
            )
            (root / "vite.config.mjs").write_text('export default { root: "web" };\n', encoding="utf-8")
            (root / "src-tauri" / "tauri.conf.json").write_text(
                '{"build":{"frontendDist":"../web/dist"}}\n',
                encoding="utf-8",
            )
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {
                            "verify:desktop": (
                                "python -m pytest tests -q && "
                                "npm run frontend:build && "
                                "npm run tauri build -- --debug"
                            )
                        }
                    }
                ),
                encoding="utf-8",
            )
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True, exist_ok=True)
            (control_dir / "missions.json").write_text(
                json.dumps(
                    [
                        {
                            "runtime_id": "hermes",
                            "state": {"status": "running", "continuity_state": "delegated_active"},
                        }
                    ]
                ),
                encoding="utf-8",
            )
            onboarding = {
                "checks": {
                    "uv": {"installed": True, "details": "ok"},
                    "openclaw": {"installed": True, "details": "ok"},
                    "hermes": {"installed": True, "details": "ok"},
                },
                "nextActions": [],
            }
            setup_health = {"serviceManagementSummary": {"totalItems": 4, "healthyCount": 4}}
            harness_lab = {
                "efficiency": {
                    "completionRate": 75,
                    "delegatedRunRate": 40,
                    "resumeRunRate": 25,
                    "resumeCompletionRate": 70,
                    "verificationPauseRate": 10,
                },
                "sessionHealth": {"staleHeartbeatCount": 0},
            }

            readiness = build_release_readiness_snapshot(
                root,
                onboarding=onboarding,
                setup_health=setup_health,
                harness_lab=harness_lab,
            )
            watchdog_gate = next(
                item for item in readiness["gates"] if item["gateId"] == "mission_watchdog_clear"
            )
            self.assertFalse(watchdog_gate["passed"])
            self.assertEqual(readiness["status"], "close_but_blocked")

            self._write_clear_watchdog_release_evidence(root)
            readiness = build_release_readiness_snapshot(
                root,
                onboarding=onboarding,
                setup_health=setup_health,
                harness_lab=harness_lab,
            )
            watchdog_gate = next(
                item for item in readiness["gates"] if item["gateId"] == "mission_watchdog_clear"
            )
            self.assertTrue(watchdog_gate["passed"])
            self.assertEqual(readiness["status"], "ready_for_1_0_validation")

            info_only_report = {
                "schema": "fluxio.mission_watchdog.v1",
                "checkedAt": utc_now_iso(),
                "root": str(root),
                "staleMinutes": 60,
                "summary": {
                    "missionCount": 1,
                    "issueCount": 1,
                    "bad": 0,
                    "warn": 0,
                    "info": 1,
                },
                "issues": [
                    {
                        "severity": "info",
                        "kind": "workspace_queue_pressure",
                        "firstStep": "Keep queued until scope is known.",
                    }
                ],
                "problemReport": {
                    "schema": "fluxio.watchdog_problem_report.v1",
                    "checkedAt": utc_now_iso(),
                    "status": "open",
                    "problemCount": 1,
                    "firstProblem": {
                        "firstRepairStep": "Keep queued until scope is known.",
                    },
                },
            }
            write_mission_watchdog_report(root, info_only_report)
            readiness = build_release_readiness_snapshot(
                root,
                onboarding=onboarding,
                setup_health=setup_health,
                harness_lab=harness_lab,
            )
            watchdog_gate = next(
                item for item in readiness["gates"] if item["gateId"] == "mission_watchdog_clear"
            )
            self.assertTrue(watchdog_gate["passed"])
            self.assertEqual(watchdog_gate["blockingIssueCount"], 0)

    def test_release_readiness_blocks_stale_watchdog_supervisor_even_when_pid_is_alive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "web" / "src" / "fluxio").mkdir(parents=True)
            (root / "src-tauri").mkdir(parents=True)
            (root / "web" / "src" / "main.tsx").write_text("export {};\n", encoding="utf-8")
            (root / "web" / "src" / "fluxio" / "FluxioApp.tsx").write_text(
                "export function FluxioApp() { return null; }\n",
                encoding="utf-8",
            )
            (root / "web" / "src" / "fluxio" / "fluxioBridge.ts").write_text(
                "export const bridge = {};\n",
                encoding="utf-8",
            )
            (root / "src" / "grant_agent").mkdir(parents=True)
            (root / "src" / "grant_agent" / "web_backend.py").write_text(
                "def serve_control_room(): pass\n",
                encoding="utf-8",
            )
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep the watchdog honest",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=1800,
            )
            mission.state.status = "running"
            store.update_mission(mission)
            self._write_clear_watchdog_release_evidence(root)
            stale_next_run = datetime.now(timezone.utc) - timedelta(hours=4)
            write_watchdog_supervisor_state(
                root,
                {
                    "schema": "fluxio.mission_watchdog_supervisor.v1",
                    "root": str(root),
                    "processPid": os.getpid(),
                    "status": "clear",
                    "loopMode": "ongoing",
                    "supervisorActive": True,
                    "startedAt": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                    "lastRunAt": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
                    "nextRunAt": stale_next_run.isoformat(),
                    "intervalSeconds": 1200,
                    "staleMinutes": 60,
                    "runsCompleted": 10,
                    "lastProblemCount": 0,
                    "lastIssueCount": 0,
                    "nextAction": "No watchdog problems found. Keep the external loop active.",
                },
            )
            onboarding = {
                "checks": {
                    "uv": {"installed": True},
                    "openclaw": {"installed": True},
                    "hermes": {"installed": True},
                }
            }
            setup_health = {"serviceManagementSummary": {"totalItems": 1, "healthyCount": 1}}
            harness_lab = {
                "efficiency": {
                    "completionRate": 75,
                    "delegatedRunRate": 40,
                    "resumeRunRate": 25,
                    "resumeCompletionRate": 70,
                    "verificationPauseRate": 0,
                },
                "sessionHealth": {"staleHeartbeatCount": 0},
            }

            readiness = build_release_readiness_snapshot(
                root,
                onboarding=onboarding,
                setup_health=setup_health,
                harness_lab=harness_lab,
            )
            watchdog_gate = next(
                item for item in readiness["gates"] if item["gateId"] == "mission_watchdog_clear"
            )

            self.assertFalse(watchdog_gate["passed"])
            self.assertTrue(watchdog_gate["supervisorStale"])
            self.assertTrue(watchdog_gate["supervisorProcessAlive"])
            self.assertIn("next run", watchdog_gate["details"])
            self.assertIn(readiness["status"], {"blocked", "close_but_blocked"})

    def test_release_readiness_treats_openclaw_proof_as_optional_for_hermes_first(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "web" / "src" / "fluxio").mkdir(parents=True)
            (root / "src-tauri").mkdir(parents=True)
            (root / "web" / "src" / "main.tsx").write_text("export {};\n", encoding="utf-8")
            (root / "web" / "src" / "fluxio" / "FluxioApp.tsx").write_text(
                "export function FluxioApp() { return null; }\n",
                encoding="utf-8",
            )
            (root / "web" / "src" / "fluxio" / "fluxioBridge.ts").write_text(
                "export const bridge = {};\n",
                encoding="utf-8",
            )
            (root / "vite.config.mjs").write_text('export default { root: "web" };\n', encoding="utf-8")
            (root / "src-tauri" / "tauri.conf.json").write_text(
                '{"build":{"frontendDist":"../web/dist"}}\n',
                encoding="utf-8",
            )
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {
                            "verify:desktop": (
                                "python -m pytest tests -q && "
                                "npm run frontend:build && "
                                "npm run tauri build -- --debug"
                            )
                        }
                    }
                ),
                encoding="utf-8",
            )
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True, exist_ok=True)
            (control_dir / "missions.json").write_text(
                json.dumps(
                    [
                        {
                            "runtime_id": "hermes",
                            "state": {
                                "status": "completed",
                                "continuity_state": "terminal",
                            },
                        },
                        {
                            "runtime_id": "hermes",
                            "state": {
                                "status": "needs_approval",
                                "continuity_state": "approval_waiting",
                            },
                        },
                        {
                            "runtime_id": "hermes",
                            "state": {
                                "status": "running",
                                "continuity_state": "delegated_active",
                                "time_budget_status": "delegated_active",
                            },
                        },
                    ]
                ),
                encoding="utf-8",
            )
            self._write_clear_watchdog_release_evidence(root)
            onboarding = {
                "checks": {
                    "uv": {"installed": True, "details": "ok"},
                    "openclaw": {"installed": True, "details": "ok"},
                    "hermes": {"installed": True, "details": "ok"},
                },
                "nextActions": [],
            }
            setup_health = {"serviceManagementSummary": {"totalItems": 4, "healthyCount": 4}}
            harness_lab = {
                "efficiency": {
                    "completionRate": 75,
                    "delegatedRunRate": 40,
                    "resumeRunRate": 25,
                    "resumeCompletionRate": 70,
                    "verificationPauseRate": 10,
                },
                "sessionHealth": {"staleHeartbeatCount": 0},
            }

            readiness = build_release_readiness_snapshot(
                root,
                onboarding=onboarding,
                setup_health=setup_health,
                harness_lab=harness_lab,
            )

            self.assertTrue(readiness["proofReadiness"]["ready"])
            self.assertEqual(readiness["proofReadiness"]["missingProofs"], [])
            self.assertEqual(
                readiness["proofReadiness"]["optionalMissingProofs"],
                ["OpenClaw proving mission completed"],
            )
            self.assertEqual(readiness["status"], "ready_for_1_0_validation")

    def test_release_readiness_uses_pending_and_delegated_session_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / "src-tauri").mkdir(parents=True, exist_ok=True)
            (root / "web" / "src" / "fluxio").mkdir(
                parents=True, exist_ok=True
            )
            (root / "web" / "src" / "fluxio" / "FluxioApp.tsx").write_text(
                "export default function FluxioApp() { return null; }\n",
                encoding="utf-8",
            )
            (root / "web" / "src" / "fluxio" / "fluxioBridge.ts").write_text(
                "export const bridge = {};\n",
                encoding="utf-8",
            )
            (root / "vite.config.mjs").write_text(
                'export default { root: "web" };\n',
                encoding="utf-8",
            )
            (root / "src-tauri" / "tauri.conf.json").write_text(
                '{"build":{"frontendDist":"../web/dist"}}\n',
                encoding="utf-8",
            )
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {
                            "verify:desktop": (
                                "python -m pytest tests -q && "
                                "npm run frontend:build && "
                                "npm run tauri build -- --debug"
                            )
                        }
                    }
                ),
                encoding="utf-8",
            )
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True, exist_ok=True)
            (control_dir / "missions.json").write_text(
                json.dumps(
                    [
                        {
                            "runtime_id": "openclaw",
                            "state": {"status": "completed", "continuity_state": "terminal"},
                        },
                        {
                            "runtime_id": "hermes",
                            "state": {"status": "completed", "continuity_state": "terminal"},
                        },
                        {
                            "runtime_id": "hermes",
                            "escalation_policy": {"pending_count": 1},
                            "state": {
                                "status": "queued",
                                "continuity_state": "fresh_only",
                                "delegated_runtime_sessions": [
                                    {"status": "running"},
                                ],
                            },
                        },
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )
            self._write_clear_watchdog_release_evidence(root)
            onboarding = {
                "checks": {
                    "uv": {"installed": True, "details": "ok"},
                    "openclaw": {"installed": True, "details": "ok"},
                    "hermes": {"installed": True, "details": "ok"},
                },
                "nextActions": [],
            }
            setup_health = {"serviceManagementSummary": {"totalItems": 4, "healthyCount": 4}}
            harness_lab = {
                "efficiency": {
                    "completionRate": 75,
                    "delegatedRunRate": 40,
                    "resumeRunRate": 25,
                    "resumeCompletionRate": 70,
                    "verificationPauseRate": 10,
                },
                "sessionHealth": {"staleHeartbeatCount": 0},
            }

            readiness = build_release_readiness_snapshot(
                root,
                onboarding=onboarding,
                setup_health=setup_health,
                harness_lab=harness_lab,
            )
            proofs = {
                item["proofId"]: item.get("passed", False)
                for item in readiness["proofReadiness"]["proofs"]
            }
            self.assertTrue(proofs["approval_wait_evidence"])
            self.assertTrue(proofs["delegated_active_evidence"])

    @mock.patch("grant_agent.mission_control._runtime_pid_alive", side_effect=lambda pid: pid == 43210)
    def test_release_readiness_uses_runtime_session_file_for_delegated_active_evidence(
        self,
        _pid_alive: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / "src-tauri").mkdir(parents=True, exist_ok=True)
            (root / "web" / "src" / "fluxio").mkdir(parents=True, exist_ok=True)
            (root / "web" / "src" / "fluxio" / "FluxioApp.tsx").write_text(
                "export default function FluxioApp() { return null; }\n",
                encoding="utf-8",
            )
            (root / "web" / "src" / "fluxio" / "fluxioBridge.ts").write_text(
                "export const bridge = {};\n",
                encoding="utf-8",
            )
            (root / "vite.config.mjs").write_text(
                'export default { root: "web" };\n',
                encoding="utf-8",
            )
            (root / "src-tauri" / "tauri.conf.json").write_text(
                '{"build":{"frontendDist":"../web/dist"}}\n',
                encoding="utf-8",
            )
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {
                            "verify:desktop": (
                                "python -m pytest tests -q && "
                                "npm run frontend:build && "
                                "npm run tauri build -- --debug"
                            )
                        }
                    }
                ),
                encoding="utf-8",
            )
            control_dir = root / ".agent_control"
            runtime_dir = control_dir / "runtime_sessions"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (control_dir / "missions.json").write_text(
                json.dumps(
                    [
                        {
                            "runtime_id": "hermes",
                            "state": {"status": "completed", "continuity_state": "terminal"},
                        },
                        {
                            "runtime_id": "hermes",
                            "escalation_policy": {"pending_count": 1},
                            "state": {"status": "running", "continuity_state": "fresh_only"},
                        },
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )
            (runtime_dir / "delegate_live.json").write_text(
                json.dumps(
                    {
                        "delegated_id": "delegate_live",
                        "runtime_id": "hermes",
                        "status": "running",
                        "pid": 43210,
                        "heartbeat_status": "healthy",
                        "heartbeat_interval_seconds": 10,
                        "updated_at": utc_now_iso(),
                    }
                ),
                encoding="utf-8",
            )
            self._write_clear_watchdog_release_evidence(root)
            onboarding = {
                "checks": {
                    "uv": {"installed": True, "details": "ok"},
                    "openclaw": {"installed": True, "details": "ok"},
                    "hermes": {"installed": True, "details": "ok"},
                },
                "nextActions": [],
            }
            setup_health = {"serviceManagementSummary": {"totalItems": 4, "healthyCount": 4}}
            harness_lab = {
                "efficiency": {
                    "completionRate": 75,
                    "delegatedRunRate": 40,
                    "resumeRunRate": 25,
                    "resumeCompletionRate": 70,
                    "verificationPauseRate": 10,
                },
                "sessionHealth": {"staleHeartbeatCount": 0},
            }

            readiness = build_release_readiness_snapshot(
                root,
                onboarding=onboarding,
                setup_health=setup_health,
                harness_lab=harness_lab,
            )

            proofs = {
                item["proofId"]: item.get("passed", False)
                for item in readiness["proofReadiness"]["proofs"]
            }
            self.assertTrue(proofs["delegated_active_evidence"])
            self.assertEqual(readiness["proofReadiness"]["missingProofs"], [])

    def test_release_readiness_uses_running_hermes_planner_loop_as_continuity(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / "src-tauri").mkdir(parents=True, exist_ok=True)
            (root / "web" / "src" / "fluxio").mkdir(parents=True, exist_ok=True)
            (root / "web" / "src" / "fluxio" / "FluxioApp.tsx").write_text(
                "export default function FluxioApp() { return null; }\n",
                encoding="utf-8",
            )
            (root / "web" / "src" / "fluxio" / "fluxioBridge.ts").write_text(
                "export const bridge = {};\n",
                encoding="utf-8",
            )
            (root / "vite.config.mjs").write_text(
                'export default { root: "web" };\n',
                encoding="utf-8",
            )
            (root / "src-tauri" / "tauri.conf.json").write_text(
                '{"build":{"frontendDist":"../web/dist"}}\n',
                encoding="utf-8",
            )
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {
                            "verify:desktop": (
                                "python -m pytest tests -q && "
                                "npm run frontend:build && "
                                "npm run tauri build -- --debug"
                            )
                        }
                    }
                ),
                encoding="utf-8",
            )
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True, exist_ok=True)
            (control_dir / "missions.json").write_text(
                json.dumps(
                    [
                        {
                            "runtime_id": "hermes",
                            "state": {"status": "completed", "continuity_state": "terminal"},
                        },
                        {
                            "runtime_id": "hermes",
                            "escalation_policy": {"pending_count": 1},
                            "state": {
                                "status": "running",
                                "continuity_state": "resume_available",
                                "planner_loop_status": "running",
                                "current_runtime_lane": "hermes delegated lane completed",
                                "delegated_runtime_sessions": [
                                    {
                                        "runtime_id": "hermes",
                                        "status": "completed",
                                        "target_provider": "minimax",
                                        "target_model": "MiniMax-M3",
                                    }
                                ],
                            },
                        },
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )
            self._write_clear_watchdog_release_evidence(root)
            onboarding = {
                "checks": {
                    "uv": {"installed": True, "details": "ok"},
                    "openclaw": {"installed": True, "details": "ok"},
                    "hermes": {"installed": True, "details": "ok"},
                },
                "nextActions": [],
            }
            setup_health = {"serviceManagementSummary": {"totalItems": 4, "healthyCount": 4}}
            harness_lab = {
                "efficiency": {
                    "completionRate": 75,
                    "delegatedRunRate": 40,
                    "resumeRunRate": 25,
                    "resumeCompletionRate": 70,
                    "verificationPauseRate": 10,
                },
                "sessionHealth": {"staleHeartbeatCount": 0},
            }

            readiness = build_release_readiness_snapshot(
                root,
                onboarding=onboarding,
                setup_health=setup_health,
                harness_lab=harness_lab,
            )

            proofs = {
                item["proofId"]: item.get("passed", False)
                for item in readiness["proofReadiness"]["proofs"]
            }
            self.assertTrue(proofs["delegated_active_evidence"])
            self.assertEqual(readiness["proofReadiness"]["missingProofs"], [])

    @mock.patch("grant_agent.runtime_supervisor._pid_alive", side_effect=lambda pid: pid == 43210)
    def test_snapshot_surfaces_delegated_runtime_activity_across_restart(
        self,
        _pid_alive: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep delegated runtime truth visible across restart",
                success_checks=[],
                mode="Autopilot",
                verification_commands=["python -m unittest"],
                max_runtime_seconds=7200,
                run_until_behavior="continue_until_blocked",
            )
            runtime_dir = root / ".agent_control" / "runtime_sessions"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            session_path = runtime_dir / "delegate_running.json"
            session = DelegatedRuntimeSession(
                delegated_id="delegate_running",
                runtime_id="hermes",
                launch_command="hermes --mission delegated",
                status="running",
                detail="Delegated runtime is still active.",
                session_path=str(session_path),
                events_path=str(runtime_dir / "delegate_running.events.jsonl"),
                decision_path=str(runtime_dir / "delegate_running.approval.json"),
                pid=43210,
                supervisor_pid=43210,
            )
            session_path.write_text(json.dumps(asdict(session), indent=2), encoding="utf-8")
            mission.delegated_runtime_sessions = [session]
            mission.state.status = "running"
            mission.state.stop_reason = "delegated_runtime_running"
            store.update_mission(mission)

            snapshot = store.build_snapshot()
            mission_payload = next(
                item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id
            )

            self.assertEqual(mission_payload["missionLoop"]["continuityState"], "delegated_active")
            self.assertEqual(
                mission_payload["missionLoop"]["pauseReason"],
                "Delegated runtime lane is still active and restart-safe.",
            )
            self.assertEqual(
                mission_payload["missionLoop"]["timeBudget"]["status"],
                "delegated_active",
            )
            self.assertEqual(
                mission_payload["missionLoop"]["currentRuntimeLane"],
                "hermes delegated lane running",
            )
            self.assertEqual(
                mission_payload["state"]["current_runtime_lane"],
                "hermes delegated lane running",
            )

    def test_snapshot_does_not_report_completed_delegated_lane_as_active(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Reconcile delegated completion truth",
                success_checks=[],
                mode="Autopilot",
                verification_commands=["python -m unittest"],
                max_runtime_seconds=7200,
                run_until_behavior="continue_until_blocked",
            )
            runtime_dir = root / ".agent_control" / "runtime_sessions"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            session_path = runtime_dir / "delegate_completed.json"
            session = DelegatedRuntimeSession(
                delegated_id="delegate_completed",
                runtime_id="hermes",
                launch_command="hermes --mission delegated",
                status="completed",
                detail="Delegated runtime completed on NAS-backed storage.",
                session_path=str(session_path),
                events_path=str(runtime_dir / "delegate_completed.events.jsonl"),
                decision_path=str(runtime_dir / "delegate_completed.approval.json"),
                acknowledged=False,
            )
            session_path.write_text(json.dumps(asdict(session), indent=2), encoding="utf-8")
            mission.delegated_runtime_sessions = [session]
            mission.state.status = "running"
            mission.state.stop_reason = "delegated_runtime_running"
            mission.proof.summary = (
                "Delegated runtime lane is active. Fluxio will continue when it finishes."
            )
            store.update_mission(mission)

            snapshot = store.build_snapshot()
            mission_payload = next(
                item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id
            )

            self.assertEqual(mission_payload["missionLoop"]["continuityState"], "resume_available")
            self.assertEqual(
                mission_payload["missionLoop"]["pauseReason"],
                "Delegated runtime lane completed and needs one reconciliation resume.",
            )
            self.assertEqual(
                mission_payload["missionLoop"]["timeBudget"]["status"],
                "reconcile_pending",
            )
            self.assertEqual(
                mission_payload["missionLoop"]["currentRuntimeLane"],
                "hermes delegated lane completed",
            )
            self.assertEqual(
                mission_payload["proof"]["summary"],
                "Delegated runtime lane completed. Resume once to reconcile proof and planning state.",
            )
            self.assertNotIn("active", mission_payload["proof"]["summary"].lower())

    @mock.patch("grant_agent.runtime_supervisor._pid_alive", return_value=True)
    def test_snapshot_sorts_delegated_sessions_before_selecting_current_lane(
        self,
        _pid_alive: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Prefer the newest recovery delegate over stale failed delegates",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=7200,
            )
            runtime_dir = root / ".agent_control" / "runtime_sessions"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            old_path = runtime_dir / "delegate_old_failed.json"
            new_path = runtime_dir / "delegate_new_running.json"
            old_failed = DelegatedRuntimeSession(
                delegated_id="delegate_old_failed",
                runtime_id="hermes",
                launch_command="hermes chat old",
                status="failed",
                detail="Old failed delegate.",
                created_at="2026-06-01T10:00:00+00:00",
                updated_at="2026-06-01T18:33:00+00:00",
                session_path=str(old_path),
                exit_code=-1,
            )
            new_running = DelegatedRuntimeSession(
                delegated_id="delegate_new_running",
                runtime_id="hermes",
                launch_command="hermes chat recovery",
                status="running",
                detail="Fresh recovery delegate.",
                created_at="2026-06-01T18:42:00+00:00",
                updated_at="2026-06-01T18:42:00+00:00",
                session_path=str(new_path),
                pid=24680,
                heartbeat_status="healthy",
                heartbeat_at="2026-06-01T18:42:00+00:00",
            )
            old_path.write_text(json.dumps(asdict(old_failed), indent=2), encoding="utf-8")
            new_path.write_text(json.dumps(asdict(new_running), indent=2), encoding="utf-8")
            mission.delegated_runtime_sessions = [new_running, old_failed]
            mission.state.delegated_runtime_sessions = [asdict(new_running), asdict(old_failed)]
            mission.state.status = "running"
            store.update_mission(mission)

            snapshot = store.build_snapshot()
            mission_payload = next(
                item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id
            )

            self.assertEqual(
                [item["delegated_id"] for item in mission_payload["delegated_runtime_sessions"]],
                ["delegate_old_failed", "delegate_new_running"],
            )
            self.assertEqual(
                mission_payload["missionLoop"]["currentRuntimeLane"],
                "hermes delegated lane running",
            )
            self.assertEqual(
                mission_payload["missionLoop"]["continuityState"],
                "delegated_active",
            )

    @mock.patch("grant_agent.runtime_supervisor._pid_alive", return_value=True)
    def test_snapshot_discovers_unlisted_runtime_session_by_plan_step(
        self,
        _pid_alive: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Keep live runtime sessions attached to mission rows",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=7200,
            )
            mission.plan_revisions = [
                {
                    "revision_id": "rev_live",
                    "trigger": "mission_start",
                    "summary": "Plan",
                    "active_step_id": "step_live",
                    "steps": [
                        {
                            "step_id": "step_live",
                            "title": "Implement vertical slice",
                            "status": "in_progress",
                        }
                    ],
                }
            ]
            mission.state.active_step_id = "step_live"
            mission.state.status = "running"
            store.update_mission(mission)

            runtime_dir = root / ".agent_control" / "runtime_sessions"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            stopped_path = runtime_dir / "delegate_stopped.json"
            stopped_session = DelegatedRuntimeSession(
                delegated_id="delegate_stopped",
                runtime_id="hermes",
                launch_command="hermes chat",
                status="stopped",
                detail="Delegated runtime session was stopped by Fluxio.",
                session_path=str(stopped_path),
                source_step_id="step_live",
                pid=13579,
                supervisor_pid=13579,
            )
            stopped_path.write_text(
                json.dumps(asdict(stopped_session), indent=2),
                encoding="utf-8",
            )
            session_path = runtime_dir / "delegate_live.json"
            session = DelegatedRuntimeSession(
                delegated_id="delegate_live",
                runtime_id="hermes",
                launch_command="hermes chat",
                status="running",
                detail="Delegated runtime process is running.",
                session_path=str(session_path),
                source_step_id="step_live",
                source_delegated_id="delegate_stopped",
                pid=24680,
                supervisor_pid=24680,
            )
            session_path.write_text(json.dumps(asdict(session), indent=2), encoding="utf-8")

            snapshot = store.build_snapshot()
            mission_payload = next(
                item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id
            )

            self.assertEqual(
                mission_payload["missionLoop"]["currentRuntimeLane"],
                "hermes delegated lane running",
            )
            self.assertEqual(mission_payload["missionLoop"]["continuityState"], "delegated_active")
            self.assertEqual(
                [item["delegated_id"] for item in mission_payload["delegated_runtime_sessions"]],
                ["delegate_live"],
            )
            persisted = ControlRoomStore(root).get_mission(mission.mission_id)
            self.assertEqual(
                [item.delegated_id for item in persisted.delegated_runtime_sessions],
                ["delegate_live"],
            )

    def test_snapshot_normalizes_execution_target_truth_for_network_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="openclaw",
                objective="Keep execution target truth explicit for NAS-backed work",
                success_checks=[],
                mode="Autopilot",
                verification_commands=["python -m unittest"],
                max_runtime_seconds=3600,
            )
            mission.execution_scope.execution_root = r"\\nas\fluxio\workspace"
            mission.execution_scope.workspace_root = r"\\nas\fluxio\workspace"

            runtime_dir = root / ".agent_control" / "runtime_sessions"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            session_path = runtime_dir / "delegate_network.json"
            session = DelegatedRuntimeSession(
                delegated_id="delegate_network",
                runtime_id="openclaw",
                launch_command="openclaw agent --message test",
                status="completed",
                detail="Delegated runtime completed on NAS-backed storage.",
                session_path=str(session_path),
                events_path=str(runtime_dir / "delegate_network.events.jsonl"),
                decision_path=str(runtime_dir / "delegate_network.approval.json"),
                workspace_root=r"\\nas\fluxio\workspace",
                execution_root=r"\\nas\fluxio\workspace",
            )
            session_path.write_text(json.dumps(asdict(session), indent=2), encoding="utf-8")
            mission.delegated_runtime_sessions = [session]
            store.update_mission(mission)

            snapshot = store.build_snapshot()
            mission_payload = next(
                item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id
            )

            self.assertEqual(
                mission_payload["execution_scope"]["execution_target"],
                "nas",
            )
            self.assertEqual(
                mission_payload["state"]["execution_scope"]["execution_target"],
                "nas",
            )
            self.assertEqual(
                mission_payload["delegated_runtime_sessions"][0]["execution_target"],
                "nas",
            )
            self.assertIn(
                "NAS or network storage",
                mission_payload["delegated_runtime_sessions"][0]["execution_target_detail"],
            )

    def test_completed_mission_terminal_state_overrides_failed_delegated_tail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Close mission after verified proof",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            session = DelegatedRuntimeSession(
                delegated_id="delegate_failed_tail",
                runtime_id="hermes",
                launch_command="hermes chat",
                status="failed",
                detail="A later delegated retry failed after proof was captured.",
                acknowledged=False,
            )
            mission.delegated_runtime_sessions = [session]
            mission.state.status = "completed"
            mission.state.last_runtime_event = "Error: later delegated retry failed"
            mission.state.runtime_autonomy = {"delegatedStatus": "delegated_runtime_failed"}
            mission.state.blocker_classification = {
                "kind": "delegated_runtime_failed",
                "summary": "Stale delegated failure.",
            }
            mission.proof.summary = "Proof verified."
            store.update_mission(mission)

            snapshot = store.build_snapshot()
            payload = next(
                item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id
            )

            self.assertEqual(payload["missionLoop"]["continuityState"], "terminal")
            self.assertEqual(payload["missionLoop"]["currentRuntimeLane"], "hermes primary lane completed")
            self.assertEqual(payload["missionLoop"]["currentCyclePhase"], "complete")
            self.assertEqual(payload["missionLoop"]["blocker"], {})
            self.assertEqual(payload["missionLoop"]["runtimeAutonomy"]["policy"], "terminal")
            self.assertEqual(payload["missionLoop"]["runtimeAutonomy"]["delegatedStatus"], "idle")
            self.assertEqual(payload["state"]["continuity_state"], "terminal")
            self.assertEqual(payload["state"]["current_runtime_lane"], "hermes primary lane completed")
            self.assertEqual(payload["state"]["last_runtime_event"], "completed")
            self.assertEqual(payload["state"]["blocker_classification"], {})
            self.assertEqual(payload["state"]["runtime_autonomy"]["delegatedStatus"], "idle")

    def test_snapshot_reconciles_running_mission_from_completed_runtime_cycle_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Reconcile runtime cycle completion",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "running"
            mission.state.last_runtime_event = "running"
            mission.proof.summary = "Mission resume dispatched asynchronously."
            store.update_mission(mission)
            store.append_event(
                MissionEvent(
                    mission_id=mission.mission_id,
                    kind="mission.runtime_cycle",
                    message="hermes control cycle finished with status completed.",
                    metadata={
                        "sessionId": "session_done",
                        "autopilotStatus": "completed",
                        "pauseReason": "",
                    },
                )
            )

            snapshot = store.build_snapshot()
            payload = next(
                item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id
            )

            self.assertEqual(payload["state"]["status"], "completed")
            self.assertEqual(payload["state"]["latest_session_id"], "session_done")
            self.assertEqual(payload["state"]["last_runtime_event"], "completed")
            self.assertEqual(payload["proof"]["summary"], "Mission completed with proof artifacts.")
            self.assertEqual(payload["missionLoop"]["continuityState"], "terminal")

    def test_mission_detail_agent_messages_hide_runtime_cycle_spam(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Show real Hermes action reports",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.action_history = [
                {
                    "action_id": "action_patch",
                    "proposal": {
                        "kind": "file_patch",
                        "title": "Patch target file",
                    },
                    "gate": {"status": "not_required"},
                    "result": {"result_summary": "File mutation completed."},
                    "executed_at": "2026-05-29T08:21:28Z",
                }
            ]
            store.update_mission(mission)
            store.append_event(
                MissionEvent(
                    mission_id=mission.mission_id,
                    kind="mission.runtime_cycle",
                    message="hermes control cycle finished with status running.",
                )
            )

            detail = store.build_mission_detail_snapshot(mission.mission_id, event_limit=12)
            labels = [item["label"] for item in detail["agentMessages"]]

            self.assertIn("mission.runtime_cycle", [item["kind"] for item in detail["events"]])
            self.assertNotIn("mission.runtime_cycle", labels)
            self.assertTrue(
                any(
                    item["label"] == "Control-room action result"
                    and item["title"] == "Patch target file"
                    and "File mutation completed." in item["detail"]
                    and item["traceOnly"] is True
                    and item["chatPreferred"] is False
                    for item in detail["agentMessages"]
                )
            )

    def test_mission_detail_reports_missing_runtime_transcript_without_pretending_bookkeeping_is_chat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Show transcript integrity",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "running"
            mission.state.latest_session_id = "session_missing"
            mission.plan_revisions = [
                {
                    "revision_id": "rev1",
                    "summary": "Planner revised the next steps after a successful action.",
                    "created_at": "2026-05-29T08:21:28Z",
                    "steps": [],
                }
            ]
            store.update_mission(mission)

            detail = store.build_mission_detail_snapshot(mission.mission_id, event_limit=12)

            self.assertEqual(detail["runtimeTranscript"]["status"], "missing_transcript")
            self.assertIn("session_missing", detail["runtimeTranscript"]["candidateSessionIds"])
            labels = [item["label"] for item in detail["agentMessages"]]
            self.assertIn("Runtime transcript integrity", labels)
            self.assertIn("Control-room planner", labels)
            self.assertNotIn("Planner review", labels)
            self.assertTrue(
                any(
                    item["label"] == "Runtime transcript integrity"
                    and item["traceOnly"] is True
                    and item["chatPreferred"] is False
                    for item in detail["agentMessages"]
                )
            )
            self.assertTrue(
                any(
                    item["label"] == "Control-room planner"
                    and item["traceOnly"] is True
                    and item["chatPreferred"] is False
                    for item in detail["agentMessages"]
                )
            )

    def test_mission_detail_surfaces_real_runtime_evidence_when_transcript_directory_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Show real mission evidence even if .agent_runs was not copied",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            artifact_path = root / ".agent_control" / "mission_artifacts" / "builder-progress.md"
            artifact_path.parent.mkdir(parents=True)
            artifact_path.write_text("# Builder progress\nLive tablet progress view proof.", encoding="utf-8")
            mission.state.status = "running"
            mission.state.latest_session_id = "session_missing"
            mission.proof.artifacts.append(str(artifact_path))
            mission.action_history = [
                {
                    "action_id": "action_runtime_report",
                    "proposal": {
                        "kind": "file_write",
                        "title": "Write Builder progress proof",
                        "target_path": str(artifact_path),
                    },
                    "gate": {"status": "not_required"},
                    "result": {
                        "result_summary": "Built a tablet progress screen with live mission slice summaries.",
                    },
                    "executed_at": "2026-06-01T08:21:28Z",
                }
            ]
            store.update_mission(mission)

            detail = store.build_mission_detail_snapshot(mission.mission_id, event_limit=12)

            self.assertEqual(detail["runtimeTranscript"]["status"], "missing_transcript")
            self.assertTrue(detail["artifactGate"]["passed"])
            self.assertTrue(
                any(
                    item["label"] == "Hermes runtime evidence"
                    and item["traceOnly"] is False
                    and item["chatPreferred"] is True
                    and (
                        "Built a tablet progress screen" in item["detail"]
                        or "builder-progress.md" in item["detail"]
                    )
                    for item in detail["agentMessages"]
                )
            )

    def test_mission_detail_attaches_real_session_timeline_before_bookkeeping(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Show real Hermes report",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            session_dir = root / ".agent_runs" / "session_live"
            session_dir.mkdir(parents=True)
            (session_dir / "timeline.jsonl").write_text(
                json.dumps(
                    {
                        "kind": "runtime.report",
                        "message": "Hermes produced a concrete slice report.",
                        "timestamp": "2026-05-29T08:21:28Z",
                        "metadata": {
                            "kind": "file_patch",
                            "target_path": "docs/demo.md",
                            "args": {
                                "content": "## Slice report\nHermes wrote the actual operator-facing report body.",
                            },
                            "result": {"result_summary": "File mutation completed."},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (session_dir / "state.json").write_text(
                json.dumps(
                    {
                        "decisions": [
                            "Fluxio hybrid harness orchestrated this mission.",
                            "Keep the RF map scope defensive.",
                        ],
                        "next_actions": ["Prepare rollout notes and next iteration tasks"],
                        "notes": [
                            "Execution policy: hands_free approvals with high delegation.",
                            "Runtime controls: context=2400 tokens, parallel_agents=1.",
                        ],
                    }
                ),
                encoding="utf-8",
            )
            mission.state.latest_session_id = "session_live"
            store.update_mission(mission)

            detail = store.build_mission_detail_snapshot(mission.mission_id, event_limit=12)

            self.assertEqual(detail["runtimeTranscript"]["status"], "attached")
            self.assertTrue(
                any(
                    item["label"] == "Hermes session transcript"
                    and item["title"] == "Hermes produced a concrete slice report."
                    and item["detail"].startswith("Runtime output: ## Slice report")
                    and "Action: file_patch" in item["detail"]
                    and "docs/demo.md" in item["detail"]
                    and "Hermes wrote the actual operator-facing report body" in item["detail"]
                    and "result_summary" in item["technicalDetail"]
                    and item["traceOnly"] is False
                    and item["chatPreferred"] is True
                    for item in detail["agentMessages"]
                )
            )
            self.assertFalse(
                any(
                    item["label"].startswith("Hermes session decision")
                    or item["label"].startswith("Hermes session note")
                    or item["label"].startswith("Hermes session next action")
                    for item in detail["agentMessages"]
                )
            )

    def test_mission_detail_rejects_read_only_transcript_as_live_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Do not show read-only planning rows as current output",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            session_dir = root / ".agent_runs" / "session_read_only"
            session_dir.mkdir(parents=True)
            (session_dir / "timeline.jsonl").write_text(
                json.dumps(
                    {
                        "kind": "action.proposed",
                        "message": "Read context for Draft implementation plan with milestones",
                        "timestamp": "2026-06-01T08:05:00Z",
                        "metadata": {
                            "kind": "file_read",
                            "target_path": str(root / "MISSION_NOTES.md"),
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            mission.state.latest_session_id = "session_read_only"
            store.update_mission(mission)

            detail = store.build_mission_detail_snapshot(mission.mission_id, event_limit=12)

            self.assertEqual(detail["runtimeTranscript"]["status"], "missing_runtime_output")
            self.assertEqual(detail["runtimeTranscript"]["messageCount"], 0)
            self.assertIn("session_read_only", detail["runtimeTranscript"]["nonConcreteSessionIds"])
            self.assertFalse(
                any(item["label"] == "Hermes session transcript" for item in detail["agentMessages"])
            )
            self.assertTrue(
                any(
                    item["label"] == "Runtime transcript integrity"
                    and item["traceOnly"] is True
                    and "no runtime output body" in item["detail"]
                    for item in detail["agentMessages"]
                )
            )

    def test_mission_detail_attaches_runtime_output_artifact_when_sessions_are_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Show concrete runtime artifact proof",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            session_dir = root / ".agent_runs" / "session_read_only"
            session_dir.mkdir(parents=True)
            (session_dir / "timeline.jsonl").write_text(
                json.dumps(
                    {
                        "kind": "action.proposed",
                        "message": "Read context for Draft implementation plan with milestones",
                        "timestamp": "2026-06-01T08:05:00Z",
                        "metadata": {
                            "kind": "file_read",
                            "target_path": str(root / "MISSION_NOTES.md"),
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            artifact_root = (
                root
                / ".agent_control"
                / "mission_artifacts"
                / mission.mission_id
            )
            proof_root = artifact_root / "proof"
            proof_root.mkdir(parents=True)
            (artifact_root / "index.html").write_text(
                "<main>Mission proof artifact</main>",
                encoding="utf-8",
            )
            (proof_root / "runtime_output.txt").write_text(
                "Mission live runtime output\n\n"
                "What changed:\n"
                "- Hermes produced an operator-facing report body.\n"
                "- Builder proof rows are backed by mission artifacts.\n",
                encoding="utf-8",
            )
            mission.state.latest_session_id = "session_read_only"
            store.update_mission(mission)

            detail = store.build_mission_detail_snapshot(mission.mission_id, event_limit=12)

            self.assertEqual(detail["runtimeTranscript"]["status"], "attached")
            self.assertEqual(detail["runtimeTranscript"]["sessionId"], "runtime_artifact")
            self.assertGreaterEqual(detail["runtimeTranscript"]["messageCount"], 2)
            self.assertIn("session_read_only", detail["runtimeTranscript"]["nonConcreteSessionIds"])
            self.assertTrue(detail["artifactGate"]["passed"])
            self.assertGreaterEqual(detail["artifactGate"]["runtimeOutputCount"], 1)
            self.assertTrue(
                any(
                    item["label"] == "Runtime output artifact"
                    and item["processMessage"] is True
                    and item["traceOnly"] is False
                    and "Runtime output:" in item["detail"]
                    and "Hermes produced an operator-facing report body" in item["detail"]
                    for item in detail["agentMessages"]
                )
            )

    def test_mission_detail_keeps_latest_session_ahead_of_stale_event_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Show current Hermes report",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.latest_session_id = "session_current"
            store.update_mission(mission)
            current_dir = root / ".agent_runs" / "session_current"
            current_dir.mkdir(parents=True)
            (current_dir / "timeline.jsonl").write_text(
                json.dumps(
                    {
                        "kind": "runtime.report",
                        "message": "Current Hermes report is the selected transcript.",
                        "timestamp": "2026-05-29T08:30:00Z",
                        "metadata": {
                            "kind": "file_write",
                            "args": {"content": "Current report body"},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            for index in range(10):
                stale_id = f"session_stale_{index}"
                stale_dir = root / ".agent_runs" / stale_id
                stale_dir.mkdir(parents=True)
                (stale_dir / "timeline.jsonl").write_text(
                    json.dumps(
                        {
                            "kind": "runtime.report",
                            "message": f"Stale report {index}",
                            "timestamp": f"2026-05-29T08:2{index}:00Z",
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                store.append_event(
                    MissionEvent(
                        mission_id=mission.mission_id,
                        kind="mission.runtime_cycle",
                        message=f"Stale cycle {index}",
                        metadata={"sessionId": stale_id},
                    )
                )

            detail = store.build_mission_detail_snapshot(mission.mission_id, event_limit=20)

            self.assertEqual(detail["runtimeTranscript"]["status"], "attached")
            self.assertEqual(detail["runtimeTranscript"]["sessionId"], "session_current")
            self.assertTrue(
                any(
                    item["label"] == "Hermes session transcript"
                    and item["title"] == "Current Hermes report is the selected transcript."
                    for item in detail["agentMessages"]
                )
            )

    def test_mission_detail_prefers_concrete_artifact_session_over_latest_read_only_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Show the real F1 deliverable instead of read-only bookkeeping",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.latest_session_id = "session_read_only"
            store.update_mission(mission)
            concrete_dir = root / ".agent_runs" / "session_concrete"
            concrete_dir.mkdir(parents=True)
            artifact_path = root / ".agent_control" / "mission_artifacts" / "f1-report.md"
            (concrete_dir / "timeline.jsonl").write_text(
                json.dumps(
                    {
                        "kind": "action.proposed",
                        "message": "Hermes wrote the F1 telemetry report.",
                        "timestamp": "2026-06-01T08:00:00Z",
                        "metadata": {
                            "kind": "file_write",
                            "target_path": str(artifact_path),
                            "args": {"content": "# F1 report\nTelemetry analytics prototype."},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            read_only_dir = root / ".agent_runs" / "session_read_only"
            read_only_dir.mkdir(parents=True)
            (read_only_dir / "timeline.jsonl").write_text(
                json.dumps(
                    {
                        "kind": "action.proposed",
                        "message": "Read context for Draft implementation plan with milestones",
                        "timestamp": "2026-06-01T08:05:00Z",
                        "metadata": {
                            "kind": "file_read",
                            "target_path": str(root / "MISSION_NOTES.md"),
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            store.append_event(
                MissionEvent(
                    mission_id=mission.mission_id,
                    kind="mission.runtime_cycle",
                    message="Concrete Hermes cycle completed.",
                    metadata={"sessionId": "session_concrete"},
                )
            )

            detail = store.build_mission_detail_snapshot(mission.mission_id, event_limit=12)

            self.assertEqual(detail["runtimeTranscript"]["status"], "attached")
            self.assertEqual(detail["runtimeTranscript"]["sessionId"], "session_concrete")
            self.assertTrue(detail["artifactGate"]["passed"])
            self.assertTrue(
                any(
                    item["label"] == "Hermes session transcript"
                    and item["title"] == "Hermes wrote the F1 telemetry report."
                    and "Telemetry analytics prototype" in item["detail"]
                    for item in detail["agentMessages"]
                )
            )

    def test_running_mission_ignores_stale_queue_pause_reason_after_parallel_split(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Run after parallel split",
                success_checks=[],
                mode="Autopilot",
                verification_commands=[],
                max_runtime_seconds=3600,
            )
            mission.state.status = "running"
            mission.state.queue_position = 0
            mission.state.queue_reason = ""
            mission.state.last_budget_pause_reason = "Waiting for mission 'old blocker' to leave the active slot."
            store.update_mission(mission)

            snapshot = store.build_snapshot()
            payload = next(
                item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id
            )

            self.assertEqual(payload["missionLoop"]["timeBudget"]["status"], "running")
            self.assertEqual(payload["missionLoop"]["pauseReason"], "")
            self.assertEqual(payload["state"]["last_budget_pause_reason"], "")

    @unittest.skipUnless(shutil.which("git"), "git is required for workspace git action tests")
    def test_git_inspect_action_persists_workspace_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=str(root), check=False, capture_output=True, text=True)
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            payload = execute_control_room_workspace_action(
                store=store,
                root=root,
                surface="git",
                action_id="inspect_repo_state",
                workspace_id=workspace.workspace_id,
            )

            self.assertTrue(payload["ok"])
            workspace_history = payload["snapshot"]["workspaces"][0]["workspaceActionHistory"]
            self.assertEqual(
                workspace_history[-1]["proposal"]["args"]["workspaceActionId"],
                "inspect_repo_state",
            )

    def test_build_git_actions_includes_pull_for_tracked_branch(self) -> None:
        actions = _build_git_actions(
            {
                "repoDetected": True,
                "remotes": [{"name": "origin", "url": "https://github.com/example/demo.git"}],
                "trackingBranch": "origin/main",
                "ahead": 0,
                "behind": 2,
                "dirty": True,
                "suggestedCommitMessage": "Update mission control and related files",
                "deployTarget": {"available": False},
            },
            {"gitActionPolicy": "approval_gated"},
        )

        action_ids = [item["actionId"] for item in actions]
        self.assertEqual(
            action_ids[:4],
            ["inspect_repo_state", "pull_branch", "commit_changes", "push_branch"],
        )
        pull_action = next(item for item in actions if item["actionId"] == "pull_branch")
        self.assertEqual(pull_action["commandSurface"], "git.pull")
        self.assertEqual(pull_action["command"], "git pull --ff-only")
        self.assertTrue(pull_action["requiresApproval"])
        commit_action = next(item for item in actions if item["actionId"] == "commit_changes")
        self.assertEqual(commit_action["commandSurface"], "git.commit")
        self.assertIn("Update mission control and related files", commit_action["command"])

    def test_build_validation_actions_uses_detected_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "package.json").write_text(
                json.dumps({"scripts": {"frontend:build": "vite build"}}),
                encoding="utf-8",
            )

            actions = _build_validation_actions(root)

            self.assertEqual(len(actions), 1)
            self.assertEqual(actions[0]["actionId"], "validate_workspace")
            self.assertEqual(actions[0]["commandSurface"], "validate.workspace")
            self.assertIn("python -m unittest discover -s tests", actions[0]["command"])
            self.assertIn("npm run frontend:build", actions[0]["command"])

    @unittest.skipUnless(shutil.which("git"), "git is required for workspace git action tests")
    def test_git_pull_action_persists_workspace_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir) / "workspace"
            root.mkdir(parents=True)
            remote = pathlib.Path(temp_dir) / "remote.git"

            subprocess.run(["git", "init", "--bare", str(remote)], check=False, capture_output=True, text=True)
            subprocess.run(["git", "init"], cwd=str(root), check=False, capture_output=True, text=True)
            subprocess.run(["git", "config", "user.email", "fluxio@example.com"], cwd=str(root), check=False, capture_output=True, text=True)
            subprocess.run(["git", "config", "user.name", "Fluxio Test"], cwd=str(root), check=False, capture_output=True, text=True)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=str(root), check=False, capture_output=True, text=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=str(root), check=False, capture_output=True, text=True)
            subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=str(root), check=False, capture_output=True, text=True)
            subprocess.run(["git", "push", "-u", "origin", "HEAD"], cwd=str(root), check=False, capture_output=True, text=True)

            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            snapshot = store.build_snapshot()
            action_ids = [item["actionId"] for item in snapshot["workspaces"][0]["gitActions"]]
            self.assertIn("pull_branch", action_ids)

            with mock.patch(
                "grant_agent.workspace_actions._run_shell_action",
                return_value=subprocess.CompletedProcess(
                    args=["git", "pull", "--ff-only"],
                    returncode=0,
                    stdout="Already up to date.\n",
                    stderr="",
                ),
            ):
                payload = execute_control_room_workspace_action(
                    store=store,
                    root=root,
                    surface="git",
                    action_id="pull_branch",
                    workspace_id=workspace.workspace_id,
                    approved=True,
                )

            self.assertTrue(payload["ok"])
            workspace_history = payload["snapshot"]["workspaces"][0]["workspaceActionHistory"]
            self.assertEqual(
                workspace_history[-1]["proposal"]["args"]["workspaceActionId"],
                "pull_branch",
            )

    def test_validate_action_persists_workspace_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_demo.py").write_text("def test_demo():\n    assert True\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            with mock.patch(
                "grant_agent.workspace_actions._run_shell_action",
                return_value=subprocess.CompletedProcess(
                    args=["python", "-m", "unittest", "discover", "-s", "tests"],
                    returncode=0,
                    stdout="ok\n",
                    stderr="",
                ),
            ):
                payload = execute_control_room_workspace_action(
                    store=store,
                    root=root,
                    surface="validate",
                    action_id="validate_workspace",
                    workspace_id=workspace.workspace_id,
                    approved=False,
                )

            self.assertTrue(payload["ok"])
            workspace_history = payload["snapshot"]["workspaces"][0]["workspaceActionHistory"]
            self.assertEqual(
                workspace_history[-1]["proposal"]["args"]["workspaceActionId"],
                "validate_workspace",
            )

    def test_integration_readiness_scores_live_evidence_without_fake_100(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            connected_apps = {
                "connectedSessions": [
                    {
                        "app_id": "oratio-viva",
                        "status": "connected",
                        "bridge_health": "healthy",
                        "latest_task_result": {
                            "status": "completed",
                            "resultSummary": "Oratio bridge action receipt completed.",
                            "payload": {"bridgeOnline": True, "healthUrl": "http://127.0.0.1:8000/health"},
                        },
                        "ui_hints": {"startCommand": "python -m uvicorn backend.main:app"},
                    },
                    {
                        "app_id": "jbheaven",
                        "status": "connected",
                        "bridge_health": "healthy",
                        "latest_task_result": {
                            "status": "completed",
                            "resultSummary": "JBHABCN skill inspection receipt completed.",
                            "payload": {"bridgeOnline": True, "apiOnline": True},
                        },
                        "ui_hints": {"startCommand": "python api_server.py"},
                    },
                    {
                        "app_id": "mind-tower",
                        "status": "available",
                        "bridge_health": "offline",
                        "latest_task_result": {
                            "status": "blocked",
                            "resultSummary": "Mind Tower bridge endpoint is offline.",
                            "payload": {"bridgeOnline": False},
                        },
                        "ui_hints": {"startCommand": "pnpm --filter @mindtower/admin dev"},
                    },
                ]
            }
            runtime_compartments = {
                "items": [
                    {
                        "sessionId": "mission-chat-real-openruntime",
                        "runtime": "hermes",
                        "turnReceipt": {
                            "runtime": "hermes",
                            "provider": "minimax",
                            "model": "MiniMax-M3",
                            "assistantMessage": "OpenRuntime returned a real result for this mission.",
                        },
                    }
                ]
            }

            snapshot = build_integration_readiness_snapshot(
                root,
                connected_apps_snapshot=connected_apps,
                runtime_compartments=runtime_compartments,
                provider_auth_presence={
                    "opencode-go": True,
                    "minimax": True,
                    "openai-codex": True,
                },
                nas_deploy_readiness={"ready": True},
                hermes_mission_evidence={"items": []},
            )

            self.assertEqual(snapshot["schema"], "fluxio.integration_readiness.v1")
            self.assertEqual(snapshot["score"], 75)
            self.assertEqual(snapshot["maxScore"], 100)
            self.assertEqual(snapshot["percent"], 75)
            self.assertNotEqual(snapshot["status"], "ready")
            states = {item["id"]: item["state"] for item in snapshot["categories"]}
            self.assertEqual(states["nas_live_data"], "ready")
            self.assertEqual(states["hermes_openruntime_turn"], "ready")
            self.assertEqual(states["oratio_viva_action"], "ready")
            self.assertEqual(states["jbheaven_action"], "ready")
            self.assertEqual(states["mind_tower_action"], "blocked")
            self.assertEqual(states["provider_routes"], "ready")
            self.assertIn("authenticated_phone_agent", states)
            self.assertGreater(len(snapshot["blockers"]), 0)


if __name__ == "__main__":
    unittest.main()
