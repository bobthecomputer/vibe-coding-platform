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
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.cli import cmd_mission_follow_up
from grant_agent.mission_control import (
    ControlRoomStore,
    _build_git_actions,
    _build_validation_actions,
    _mission_title,
    build_harness_lab_snapshot,
    build_release_readiness_snapshot,
    build_escalation_preview,
    mission_mode_to_engine_mode,
    mission_time_budget_window,
)
from grant_agent.models import DelegatedRuntimeSession, utc_now_iso
from grant_agent.workspace_actions import execute_control_room_workspace_action


class MissionControlTests(unittest.TestCase):
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

    def test_store_creates_default_workspace_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            (root / "src-tauri").mkdir()

            store = ControlRoomStore(root)
            snapshot = store.build_snapshot()

            self.assertEqual(len(snapshot["workspaces"]), 1)
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
            self.assertIn("bridgeLab", snapshot)
            self.assertIn("guidance", snapshot)
            self.assertIn("onboarding", snapshot)
            self.assertIn("ui", snapshot)
            self.assertIn("setupHealth", snapshot)
            self.assertIn("workflowStudio", snapshot)
            self.assertIn("providerSetupStatus", snapshot)
            self.assertIn("efficiencyAutotune", snapshot)
            self.assertIn("releaseReadiness", snapshot)
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
            self.assertIn("serviceManagement", snapshot["setupHealth"])
            self.assertIn("minimax", snapshot["providerSetupStatus"])
            self.assertEqual(
                snapshot["providerSetupStatus"]["minimax"]["authPath"],
                "not configured",
            )
            self.assertFalse(snapshot["efficiencyAutotune"]["eligible"])
            workflow = snapshot["workflowStudio"]["recipes"][0]
            self.assertIn("reviewStatus", workflow)
            self.assertIn("serviceIds", workflow)
            self.assertIn("verificationDefaults", workflow)

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

    def test_minimax_portal_auth_marks_provider_truth_ready_without_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
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
                "OAuth portal",
            )

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

    def test_release_readiness_snapshot_scores_required_gates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "t3code" / "apps" / "web" / "src" / "fluxio").mkdir(parents=True)
            (root / "src-tauri").mkdir(parents=True)
            (root / "t3code" / "apps" / "web" / "src" / "main.tsx").write_text(
                "export {};\n",
                encoding="utf-8",
            )
            (root / "t3code" / "apps" / "web" / "src" / "fluxio" / "FluxioApp.tsx").write_text(
                "export function FluxioApp() { return null; }\n",
                encoding="utf-8",
            )
            (root / "t3code" / "apps" / "web" / "src" / "fluxio" / "fluxioBridge.ts").write_text(
                "export const bridge = {};\n",
                encoding="utf-8",
            )
            (root / "vite.config.mjs").write_text(
                'export default { root: "t3code/apps/web" };\n',
                encoding="utf-8",
            )
            (root / "src-tauri" / "tauri.conf.json").write_text(
                '{"build":{"frontendDist":"../t3code/apps/web/dist"}}\n',
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

    def test_release_readiness_accepts_dynamic_vite_web_root_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "t3code" / "apps" / "web" / "src" / "fluxio").mkdir(parents=True)
            (root / "src-tauri").mkdir()
            (root / "t3code" / "apps" / "web" / "src" / "main.tsx").write_text(
                "export {};\n",
                encoding="utf-8",
            )
            (root / "t3code" / "apps" / "web" / "src" / "fluxio" / "FluxioApp.tsx").write_text(
                "export function FluxioApp() { return null; }\n",
                encoding="utf-8",
            )
            (root / "t3code" / "apps" / "web" / "src" / "fluxio" / "fluxioBridge.ts").write_text(
                "export const bridge = {};\n",
                encoding="utf-8",
            )
            (root / "vite.config.mjs").write_text(
                (
                    'import { resolve } from "node:path";\n'
                    'const repoRoot = process.cwd();\n'
                    'const webRoot = resolve(repoRoot, "t3code", "apps", "web");\n'
                    "export default {\n"
                    "  root: webRoot,\n"
                    "};\n"
                ),
                encoding="utf-8",
            )
            (root / "src-tauri" / "tauri.conf.json").write_text(
                '{"build":{"frontendDist":"../t3code/apps/web/dist"}}\n',
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
            (root / "t3code" / "apps" / "web" / "src" / "fluxio").mkdir(parents=True)
            (root / "src-tauri").mkdir(parents=True)
            (root / "t3code" / "apps" / "web" / "src" / "main.tsx").write_text(
                "export {};\n",
                encoding="utf-8",
            )
            (root / "t3code" / "apps" / "web" / "src" / "fluxio" / "FluxioApp.tsx").write_text(
                "export function FluxioApp() { return null; }\n",
                encoding="utf-8",
            )
            (root / "t3code" / "apps" / "web" / "src" / "fluxio" / "fluxioBridge.ts").write_text(
                "export const bridge = {};\n",
                encoding="utf-8",
            )
            (root / "vite.config.mjs").write_text(
                'export default { root: "t3code/apps/web" };\n',
                encoding="utf-8",
            )
            (root / "src-tauri" / "tauri.conf.json").write_text(
                '{"build":{"frontendDist":"../t3code/apps/web/dist"}}\n',
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

    def test_release_readiness_uses_pending_and_delegated_session_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / "src-tauri").mkdir(parents=True, exist_ok=True)
            (root / "t3code" / "apps" / "web" / "src" / "fluxio").mkdir(
                parents=True, exist_ok=True
            )
            (root / "t3code" / "apps" / "web" / "src" / "fluxio" / "FluxioApp.tsx").write_text(
                "export default function FluxioApp() { return null; }\n",
                encoding="utf-8",
            )
            (root / "t3code" / "apps" / "web" / "src" / "fluxio" / "fluxioBridge.ts").write_text(
                "export const bridge = {};\n",
                encoding="utf-8",
            )
            (root / "vite.config.mjs").write_text(
                'export default { root: "t3code/apps/web" };\n',
                encoding="utf-8",
            )
            (root / "src-tauri" / "tauri.conf.json").write_text(
                '{"build":{"frontendDist":"../t3code/apps/web/dist"}}\n',
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


if __name__ == "__main__":
    unittest.main()
