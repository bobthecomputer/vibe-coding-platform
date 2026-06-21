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

from grant_agent.cli import cmd_mission_follow_up, cmd_workspace_delete
from grant_agent.mission_control import (
    ControlRoomStore,
    _build_generated_image_artifacts_snapshot,
    _build_runtime_compartments_snapshot,
    _build_git_actions,
    _build_validation_actions,
    _mission_title,
    _platform_path_for_windows_drive,
    _recover_evidence_path,
    _runtime_proof_gate_summary,
    _sync_project_tree,
    build_harness_lab_snapshot,
    build_release_readiness_snapshot,
    build_escalation_preview,
    mission_mode_to_engine_mode,
    mission_time_budget_window,
    reconcile_provider_secret_presence,
)
from grant_agent.models import DelegatedRuntimeSession, Mission, MissionEvent, utc_now_iso
from grant_agent.workspace_actions import execute_control_room_workspace_action


class MissionControlTests(unittest.TestCase):
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

    def test_runtime_proof_gate_summary_blocks_missing_artifacts_without_double_counting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            proof_path = root / "runtime_lane_proof.json"
            scorecard_path = root / "route_scorecard.json"
            proof_path.write_text("{}", encoding="utf-8")
            latest_proof = {
                "runId": "artifact-gap",
                "proofRunCommand": "python scripts/runtime_lane_proof_harness.py --run-id artifact-gap",
                "readinessSummary": {
                    "overallStatus": "ready_for_supervised_live_run",
                    "promotionBlocked": False,
                    "blockingGateCount": 0,
                },
                "lanes": [
                    {
                        "runtimeId": "openclaw",
                        "readiness": {
                            "nextRecoveryAction": "",
                            "gates": [
                                {
                                    "gateId": "route_scorecard_written",
                                    "label": "Route scorecard written",
                                    "status": "passed",
                                    "proofArtifact": "route_scorecard.json",
                                    "recoveryAction": "Restore route scorecard.",
                                    "blocksPromotion": False,
                                }
                            ],
                        },
                    }
                ],
                "artifactPaths": {
                    "proof": str(proof_path),
                    "route_scorecard": str(scorecard_path),
                },
                "artifactIntegrity": {
                    "schemaVersion": "runtime-proof-artifact-integrity.v1",
                    "presentCount": 1,
                    "missingCount": 1,
                    "artifactComplete": False,
                    "gateRequiredCount": 1,
                    "missingArtifacts": ["route_scorecard.json"],
                    "missingGateArtifacts": ["route_scorecard.json"],
                    "artifacts": [
                        {
                            "key": "proof",
                            "name": "runtime_lane_proof.json",
                            "path": str(proof_path),
                            "exists": True,
                            "requiredByGate": False,
                        },
                        {
                            "key": "route_scorecard",
                            "name": "route_scorecard.json",
                            "path": str(scorecard_path),
                            "exists": False,
                            "requiredByGate": True,
                        },
                    ],
                },
            }

            summary = _runtime_proof_gate_summary(latest_proof)

        self.assertEqual(summary["status"], "artifact_incomplete")
        self.assertTrue(summary["promotionBlocked"])
        self.assertEqual(summary["blockingGateCount"], 1)
        self.assertEqual(summary["missingArtifactCount"], 1)
        self.assertEqual(summary["missingArtifacts"], ["route_scorecard.json"])
        self.assertEqual(summary["missingGateArtifacts"], ["route_scorecard.json"])
        self.assertFalse(summary["artifactComplete"])
        self.assertIn(
            "Rerun the deterministic runtime lane proof harness",
            summary["nextRecoveryActions"][0],
        )

    def test_delegated_runtime_proof_receipts_surface_in_fused_runtime_and_compartments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            sessions_dir = root / ".agent_control" / "runtime_sessions"
            sessions_dir.mkdir(parents=True)
            session_path = sessions_dir / "delegate_live.json"
            events_path = sessions_dir / "delegate_live.events.jsonl"
            log_path = sessions_dir / "delegate_live.log"
            receipt_path = sessions_dir / "delegate_live.proof.json"
            session_path.write_text("{}", encoding="utf-8")
            log_path.write_text("runtime completed\n", encoding="utf-8")
            events_path.write_text(
                json.dumps(
                    {
                        "event_id": "evt_1",
                        "delegated_id": "delegate_live",
                        "runtime_id": "hermes",
                        "kind": "session.completed",
                        "message": "runtime completed",
                        "status": "completed",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            receipt_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": "delegated-runtime-proof.v1",
                        "delegatedId": "delegate_live",
                        "runtimeId": "hermes",
                        "status": "completed",
                        "terminal": True,
                        "exitCode": 0,
                        "updatedAt": "2026-06-21T08:00:00+00:00",
                        "route": {
                            "phase": "execute",
                            "role": "executor",
                            "provider": "minimax",
                            "model": "MiniMax-M3",
                        },
                        "heartbeat": {"status": "inactive"},
                        "artifacts": {
                            "sessionPath": str(session_path),
                            "eventsPath": str(events_path),
                            "logPath": str(log_path),
                        },
                        "eventCount": 1,
                        "changedFiles": ["proof.txt"],
                        "changedFileCount": 1,
                        "safety": {
                            "liveRuntimeExecution": True,
                            "liveModelCalls": False,
                            "runtimeAdapterAdded": False,
                            "openCodeGoRuntimeAdded": False,
                            "secretsIncluded": False,
                            "realTargetsAsserted": False,
                        },
                        "promotionGate": {
                            "promotionBlocked": False,
                            "terminalStatusVerified": True,
                            "artifactIntegrityVerified": True,
                            "eventLogObserved": True,
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            harness = build_harness_lab_snapshot(root)

            receipts = harness["fusedRuntime"]["delegatedProofReceipts"]
            self.assertEqual(receipts[0]["schemaVersion"], "delegated-runtime-proof.v1")
            self.assertEqual(receipts[0]["delegatedId"], "delegate_live")
            self.assertTrue(receipts[0]["verification"]["passed"])
            self.assertTrue(receipts[0]["safety"]["liveRuntimeExecution"])
            self.assertFalse(receipts[0]["safety"]["liveModelCalls"])
            self.assertEqual(
                harness["fusedRuntime"]["proofSignals"]["delegatedProofReceiptCount"],
                1,
            )

            mission = Mission(
                mission_id="mission_runtime_receipt",
                workspace_id="workspace_runtime_receipt",
                runtime_id="hermes",
                objective="Show delegated receipt",
                success_checks=[],
            )
            mission.delegated_runtime_sessions = [
                DelegatedRuntimeSession(
                    delegated_id="delegate_live",
                    runtime_id="hermes",
                    launch_command="hermes chat -q test",
                    status="completed",
                    session_path=str(session_path),
                    workspace_root=str(root),
                    execution_root=str(root),
                    log_path=str(log_path),
                    events_path=str(events_path),
                    proof_receipt_path=str(receipt_path),
                    exit_code=0,
                )
            ]

            compartments = _build_runtime_compartments_snapshot(root, [mission])

            receipt = compartments["items"][0]["runtimeProofReceipt"]
            self.assertEqual(receipt["delegatedId"], "delegate_live")
            self.assertTrue(receipt["verification"]["passed"])

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
            self.assertIn("fusionWorkbench", snapshot)
            self.assertIn("storageBridge", snapshot)
            self.assertIn("guidance", snapshot)
            self.assertIn("onboarding", snapshot)
            self.assertIn("ui", snapshot)
            self.assertIn("setupHealth", snapshot)
            self.assertIn("workflowStudio", snapshot)
            self.assertIn("providerSetupStatus", snapshot)
            self.assertIn("providerEcosystem", snapshot)
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
            self.assertIn("serviceManagement", snapshot["setupHealth"])
            self.assertIn("minimax", snapshot["providerSetupStatus"])
            self.assertEqual(
                snapshot["providerSetupStatus"]["minimax"]["authPath"],
                "not configured",
            )
            self.assertEqual(
                snapshot["providerEcosystem"]["schemaVersion"],
                "provider-ecosystem.v1",
            )
            provider_ids = {
                item["providerId"]
                for item in snapshot["providerEcosystem"]["providers"]
            }
            self.assertIn("openai", provider_ids)
            self.assertIn("minimax", provider_ids)
            self.assertIn("local", provider_ids)
            self.assertFalse(snapshot["fusionWorkbench"]["adapter"]["available"])
            self.assertTrue(snapshot["fusionWorkbench"]["adapter"]["readOnly"])
            self.assertEqual(snapshot["fusionWorkbench"]["adapter"]["writeActions"], 0)
            self.assertTrue(
                snapshot["providerEcosystem"]["updatePolicy"][
                    "requiresApprovalForDefaultChanges"
                ]
            )
            self.assertIn(
                "compatibilityWarnings",
                snapshot["providerEcosystem"]["updatePolicy"],
            )
            readiness = snapshot["providerEcosystem"]["updatePolicy"][
                "readinessChecklist"
            ]
            self.assertGreaterEqual(len(readiness), 6)
            readiness_ids = {item["checkId"] for item in readiness}
            self.assertIn("source_verification_gate", readiness_ids)
            self.assertIn("catalog_refresh_review", readiness_ids)
            self.assertIn("credential_safety", readiness_ids)
            self.assertIn("runtime_compatibility", readiness_ids)
            self.assertIn("route_smoke", readiness_ids)
            self.assertIn("user_model_preservation", readiness_ids)
            self.assertFalse(
                snapshot["providerEcosystem"]["updatePolicy"]["readinessSummary"][
                    "safeToRefresh"
                ]
            )
            self.assertIn(
                "updateReadinessReadyCount",
                snapshot["providerEcosystem"]["summary"],
            )
            self.assertIn(
                "routeDecisionAuthRequiredCount",
                snapshot["providerEcosystem"]["summary"],
            )
            self.assertIn(
                "routeDecisionCatalogOnlyCount",
                snapshot["providerEcosystem"]["summary"],
            )
            self.assertIn(
                "routeDecisionPlannedCount",
                snapshot["providerEcosystem"]["summary"],
            )
            self.assertIn(
                "modelCatalogCount",
                snapshot["providerEcosystem"]["summary"],
            )
            self.assertIn("modelCatalog", snapshot["providerEcosystem"])
            self.assertGreaterEqual(
                snapshot["providerEcosystem"]["summary"]["modelCatalogCount"],
                4,
            )
            model_ids = {
                item["modelId"]
                for item in snapshot["providerEcosystem"]["modelCatalog"]
            }
            self.assertIn("gpt-5.5", model_ids)
            self.assertIn("gpt-5.4", model_ids)
            self.assertIn("gpt-5.4-mini", model_ids)
            self.assertIn("gpt-5.3-codex", model_ids)
            self.assertIn("deepseek/deepseek-v4-flash", model_ids)
            self.assertIn("MiniMax-M3", model_ids)
            for model_row in snapshot["providerEcosystem"]["modelCatalog"]:
                self.assertEqual(model_row["metadataUse"], "review_only")
                self.assertFalse(model_row["defaultChangeAllowed"])
                self.assertTrue(model_row["requiresApproval"])
                self.assertIn("sourceFreshness", model_row)
                self.assertIn(model_row["reviewStatus"], {
                    "current_frontier",
                    "current_reviewed",
                    "current_efficient",
                    "codex_api_route",
                    "low_cost_redteam_candidate",
                    "bounded_route",
                    "adapter_planned",
                    "catalog_only",
                })
            self.assertIn("sourceFreshness", snapshot["providerEcosystem"])
            self.assertEqual(
                snapshot["providerEcosystem"]["sourceFreshness"]["status"],
                "current",
            )
            self.assertTrue(
                snapshot["providerEcosystem"]["sourceFreshness"]["reviewOnly"]
            )
            self.assertEqual(
                snapshot["providerEcosystem"]["summary"]["catalogSourceCount"],
                len(snapshot["providerEcosystem"]["sources"]),
            )
            refresh_proof = snapshot["providerEcosystem"]["updatePolicy"][
                "refreshProof"
            ]
            source_gate = snapshot["providerEcosystem"]["updatePolicy"][
                "sourceVerificationGate"
            ]
            self.assertEqual(
                source_gate["schemaVersion"],
                "provider-source-verification-gate.v1",
            )
            self.assertEqual(source_gate["status"], "review_only_current")
            self.assertFalse(source_gate["defaultChangeAllowed"])
            self.assertTrue(source_gate["defaultChangeBlocked"])
            self.assertEqual(
                source_gate["primarySourceCount"],
                snapshot["providerEcosystem"]["summary"]["catalogSourceCount"],
            )
            self.assertIn(
                "sourceVerificationStatus",
                snapshot["providerEcosystem"]["summary"],
            )
            self.assertEqual(
                refresh_proof["schemaVersion"],
                "provider-catalog-refresh/v1",
            )
            self.assertTrue(refresh_proof["reviewOnly"])
            self.assertFalse(refresh_proof["writesDefaults"])
            self.assertFalse(refresh_proof["writesCredentials"])
            self.assertFalse(refresh_proof["writesProviderRegistry"])
            openai_provider = next(
                item
                for item in snapshot["providerEcosystem"]["providers"]
                if item["providerId"] == "openai"
            )
            self.assertEqual(
                openai_provider["routeExposure"]["level"],
                "first_class_route",
            )
            self.assertEqual(openai_provider["sourceFreshness"]["status"], "current")
            self.assertIn("updateSafety", openai_provider)
            self.assertIn("compatibilityWarnings", openai_provider)
            self.assertIn("healthCheck", openai_provider)
            self.assertIn("routeDecision", openai_provider)
            self.assertIn("modelCapabilities", openai_provider)
            self.assertEqual(
                openai_provider["routeDecision"]["schemaVersion"],
                "provider-route-decision.v1",
            )
            self.assertIn(
                openai_provider["routeDecision"]["decision"],
                {
                    "ready_controlled_route",
                    "route_smoke_required",
                    "auth_required",
                    "runtime_required",
                    "review_required",
                },
            )
            self.assertFalse(openai_provider["routeDecision"]["defaultChangeAllowed"])
            self.assertTrue(openai_provider["routeDecision"]["requiresApproval"])
            self.assertGreaterEqual(len(openai_provider["routeDecision"]["capabilitySummary"]), 2)
            self.assertIn("safeNextStep", openai_provider["routeDecision"])
            self.assertIn(
                openai_provider["healthCheck"]["status"],
                {"ready", "missing_auth", "runtime_missing", "unverified"},
            )
            self.assertIn("safeNextStep", openai_provider["healthCheck"])
            self.assertTrue(openai_provider["modelCapabilities"]["chat"])
            self.assertTrue(openai_provider["modelCapabilities"]["coding"])
            self.assertIn(
                openai_provider["modelCapabilities"]["toolUse"],
                {"supported", "planned", "unknown"},
            )
            self.assertIn(
                "Review refreshed catalog metadata",
                openai_provider["compatibilityWarnings"][0],
            )
            self.assertFalse(snapshot["efficiencyAutotune"]["eligible"])
            workflow = snapshot["workflowStudio"]["recipes"][0]
            self.assertIn("reviewStatus", workflow)
            self.assertIn("serviceIds", workflow)
            self.assertIn("verificationDefaults", workflow)

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
            compartment_dir = root / ".agent_control" / "runtime_compartments"
            compartment_dir.mkdir(parents=True)
            proof_path = root / ".agent_control" / "runtime_compartment_proofs" / "chat-live.proof.json"
            proof_path.parent.mkdir(parents=True)
            proof_receipt = {
                "schemaVersion": "runtime-compartment-proof.v1",
                "receiptKind": "runtime_compartment_proof",
                "sessionId": "chat-live",
                "runtime": "codex",
                "route": {"role": "executor", "provider": "openai-codex", "model": "gpt-5.5"},
                "summary": {"messageCount": 2, "timelineEventCount": 3, "filesChangedCount": 1},
                "proofSignals": {"hasRuntimeReply": True, "hasRoute": True, "hasToolTimeline": True},
                "safety": {"runtimeAdapterAdded": False, "fusedRuntimeRole": "evidence_layer_not_runtime_adapter"},
                "artifacts": {"proofPath": str(proof_path), "proofUrl": "/api/artifact?id=test"},
            }
            proof_path.write_text(json.dumps(proof_receipt, indent=2), encoding="utf-8")
            (compartment_dir / "chat-live.json").write_text(
                json.dumps(
                    {
                        "sessionId": "chat-live",
                        "runtime": "codex",
                        "state": "ready",
                        "streaming": "recorded",
                        "route": {"role": "executor", "provider": "openai-codex", "model": "gpt-5.5"},
                        "toolTimeline": [{"kind": "runtime.roundtrip", "summary": "completed"}],
                        "messages": [{"role": "assistant", "text": "done"}],
                        "filesChanged": ["web/src/fluxio/FluxioShell.jsx"],
                        "runtimeProofReceipt": proof_receipt,
                        "updatedAt": "2026-05-12T10:02:00+00:00",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
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
            proof_item = next(item for item in compartments["items"] if item["sessionId"] == "chat-live")
            self.assertEqual(proof_item["runtimeProofReceipt"]["schemaVersion"], "runtime-compartment-proof.v1")
            self.assertFalse(proof_item["runtimeProofReceipt"]["safety"]["runtimeAdapterAdded"])
            hermes_item = next(item for item in compartments["items"] if item["runtime"] == "hermes")
            self.assertEqual(hermes_item["status"], "running")
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
            self.assertEqual(snapshot["harnessLab"]["fusedRuntime"]["status"], "unproven")
            self.assertEqual(
                snapshot["harnessLab"]["fusedRuntime"]["proofSignals"]["fusedRuntimeRole"],
                "supervisor_not_runtime_adapter",
            )
            provider_routes = {
                item["provider"]: item
                for item in snapshot["harnessLab"]["fusedRuntime"]["modelProviderRoutes"]
            }
            self.assertNotIn("opencode", provider_routes)
            self.assertEqual(provider_routes["openai"]["role"], "provider_model_route")
            self.assertEqual(provider_routes["minimax"]["role"], "provider_model_route")
            self.assertEqual(snapshot["hermesMissionEvidence"]["items"], [])
            self.assertIn("emptyState", snapshot["hermesMissionEvidence"])
            self.assertIn("checks", snapshot["nasDeployReadiness"])

    def test_provider_ecosystem_tracks_update_sources_without_claiming_full_support(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "test-openai-key",
                    "ANTHROPIC_API_KEY": "",
                    "OPENROUTER_API_KEY": "",
                    "MINIMAX_API_KEY": "",
                    "FLUXIO_OPENAI_CODEX_OAUTH_PRESENT": "",
                    "FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT": "",
                },
                clear=False,
            ):
                snapshot = ControlRoomStore(root).build_snapshot()

            ecosystem = snapshot["providerEcosystem"]
            providers = {item["providerId"]: item for item in ecosystem["providers"]}
            self.assertEqual(ecosystem["lastVerifiedAt"], "2026-06-21")
            self.assertEqual(providers["openai"]["status"], "repo_supported")
            self.assertTrue(providers["openai"]["authPresent"])
            self.assertTrue(providers["openai"]["credentialReady"])
            self.assertFalse(providers["openai"]["canRouteNow"])
            self.assertEqual(providers["openai"]["routeSmokeStatus"], "missing")
            self.assertEqual(
                providers["openai"]["healthCheck"]["status"],
                "route_smoke_missing",
            )
            self.assertEqual(providers["local"]["status"], "planned_adapter")
            self.assertFalse(providers["local"]["canRouteNow"])
            self.assertIn("https://ai-gateway.vercel.sh/v1/models", ecosystem["updatePolicy"]["dynamicSources"])
            self.assertTrue(
                ecosystem["updatePolicy"]["sourceVerificationGate"][
                    "defaultChangeBlocked"
                ]
            )
            checklist = ecosystem["updatePolicy"]["readinessChecklist"]
            self.assertIn(
                "scripts/provider_catalog_refresh.py",
                next(
                    item
                    for item in checklist
                    if item["checkId"] == "catalog_refresh_review"
                )["safeAction"],
            )
            self.assertTrue(
                next(
                    item
                    for item in checklist
                    if item["checkId"] == "user_model_preservation"
                )["proof"].endswith("neverOverwriteUserModels=true.")
            )
            source_ids = {item["sourceId"] for item in ecosystem["sources"]}
            self.assertIn("opencode_models", source_ids)
            self.assertIn("crush_local_models", source_ids)
            self.assertIn("openclaw_model_providers", source_ids)

    def test_provider_secret_reconciliation_keeps_aliases_and_runtime_blocks_honest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "",
                    "ANTHROPIC_API_KEY": "",
                    "OPENROUTER_API_KEY": "",
                    "MINIMAX_API_KEY": "",
                    "FLUXIO_OPENAI_CODEX_OAUTH_PRESENT": "",
                    "FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT": "",
                },
                clear=False,
            ):
                snapshot = ControlRoomStore(root).build_snapshot()

            reconcile_provider_secret_presence(
                snapshot,
                {"openai-codex": True, "minimax-portal": True},
            )

            providers = {
                item["providerId"]: item
                for item in snapshot["providerEcosystem"]["providers"]
            }
            self.assertTrue(snapshot["providerSetupStatus"]["openai"]["authPresent"])
            self.assertTrue(providers["openai"]["authPresent"])
            self.assertTrue(providers["openai"]["credentialReady"])
            self.assertFalse(providers["openai"]["canRouteNow"])
            self.assertEqual(providers["openai"]["healthCheck"]["status"], "route_smoke_missing")
            self.assertTrue(snapshot["providerSetupStatus"]["minimax"]["authPresent"])
            self.assertTrue(providers["minimax"]["authPresent"])
            if providers["minimax"]["healthCheck"]["status"] == "runtime_missing":
                self.assertFalse(providers["minimax"]["canRouteNow"])
                self.assertIn("auth present", providers["minimax"]["healthCheck"]["evidence"])
            self.assertEqual(
                snapshot["providerEcosystem"]["summary"]["routeReadyCount"],
                0,
            )
            self.assertEqual(
                snapshot["providerEcosystem"]["summary"]["missingAuthCount"],
                3,
            )
            self.assertFalse(providers["deepseek"]["authPresent"])
            self.assertFalse(providers["deepseek"]["canRouteNow"])
            self.assertEqual(
                providers["deepseek"]["routeDecision"]["decision"],
                "auth_required",
            )

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
            self.assertFalse(mission_payload["providerTruth"]["authPresent"])
            self.assertEqual(
                mission_payload["providerTruth"]["authPath"],
                "MiniMax OpenClaw OAuth",
            )

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
                "MiniMax OpenClaw OAuth",
            )

    def test_snapshot_recommends_skills_for_blocked_runtime_recovery(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "",
                "FLUXIO_OPENAI_CODEX_OAUTH_PRESENT": "",
            },
            clear=False,
        ), tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            config_dir = root / "config"
            config_dir.mkdir()
            source_config = pathlib.Path(__file__).resolve().parents[1] / "config" / "skills.json"
            shutil.copy2(source_config, config_dir / "skills.json")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]
            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="hermes",
                objective="Recover a blocked mission with repeated verification failures",
                success_checks=[],
                mode="Autopilot",
                verification_commands=["python -m unittest"],
                max_runtime_seconds=3600,
            )
            mission.state.status = "blocked"
            mission.state.current_cycle_phase = "execute"
            mission.state.repeated_failure_count = 3
            mission.state.context_status = "missing"
            mission.state.context_usage_ratio = 0.91
            mission.state.verification_failures = ["python -m unittest"]
            mission.state.route_change_count = 2
            mission.proof.blocked_by = ["missing operator decision"]
            mission.effective_route_contract = {
                "roles": [
                    {
                        "role": "executor",
                        "provider": "openai",
                        "model": "gpt-5.5",
                        "effort": "medium",
                    }
                ]
            }
            mission.delegated_runtime_sessions = [
                DelegatedRuntimeSession(
                    delegated_id="delegate_stale",
                    runtime_id="hermes",
                    launch_command="hermes chat -q recover",
                    status="running",
                    heartbeat_status="stale",
                    detail="Heartbeat is stale.",
                    target_phase="execute",
                    target_role="executor",
                    target_provider="openai",
                    target_model="gpt-5.5",
                )
            ]
            store.update_mission(mission)

            snapshot = store.build_snapshot()
            mission_payload = next(
                item for item in snapshot["missions"] if item["mission_id"] == mission.mission_id
            )
            recovery = mission_payload["missionLoop"]["skillRecovery"]

            self.assertEqual(recovery["schemaVersion"], "mission-skill-recovery.v1")
            self.assertEqual(recovery["status"], "needs_recovery")
            trigger_ids = {item["triggerId"] for item in recovery["triggers"]}
            self.assertTrue(
                {
                    "mission_blocked",
                    "verification_failure",
                    "repeated_failure",
                    "context_missing",
                    "weak_provider_route",
                    "runtime_lane_attention",
                }.issubset(trigger_ids)
            )
            skill_ids = {item["skillId"] for item in recovery["recommendations"]}
            self.assertIn("stuck_state_recovery", skill_ids)
            self.assertEqual(
                recovery["routeSeparation"]["providerRoute"]["provider"],
                "openai",
            )
            self.assertIn("hermes", recovery["routeSeparation"]["runtimeLane"])
            recovery_plan = recovery["recoveryPlan"]
            self.assertEqual(
                recovery_plan["schemaVersion"],
                "mission-skill-recovery-plan.v1",
            )
            self.assertEqual(recovery_plan["status"], "ready")
            self.assertEqual(
                recovery_plan["selectedSkill"]["skillId"],
                "stuck_state_recovery",
            )
            self.assertIn("hermes", recovery_plan["runtimeLane"])
            self.assertEqual(recovery_plan["providerRoute"]["provider"], "openai")
            self.assertIn(
                recovery_plan["loopStep"],
                {"plan", "verify", "repair", "route", "observe"},
            )
            self.assertTrue(recovery_plan["retryGuard"]["blockSameStepRetry"])
            self.assertTrue(
                recovery_plan["proofArtifactPlan"]["mustAttachBeforeRetry"]
            )
            self.assertIn(
                "artifacts/mission-recovery/",
                recovery_plan["proofArtifactPlan"]["suggestedPath"],
            )
            self.assertIn(
                "minimumEvidence",
                recovery_plan["proofRequirement"],
            )
            self.assertIn("visibleRouteSummary", recovery_plan)
            self.assertEqual(
                recovery_plan["intentAlignment"]["schemaVersion"],
                "mission-intent-alignment.v1",
            )
            self.assertIn(
                recovery_plan["intentAlignment"]["status"],
                {"aligned", "drift_risk"},
            )
            self.assertIn("objectiveExcerpt", recovery_plan["intentAlignment"])
            self.assertIn("routeReason", recovery_plan["intentAlignment"])
            self.assertEqual(
                recovery_plan["intentAlignment"]["proofRequirement"]["artifactKind"],
                "intent_alignment_receipt",
            )
            self.assertEqual(
                mission_payload["state"]["skill_recovery"]["schemaVersion"],
                "mission-skill-recovery.v1",
            )
            interventions = mission_payload["missionLoop"]["supervisorInterventions"]
            self.assertGreaterEqual(len(interventions), 3)
            intervention_sources = {item["source"] for item in interventions}
            self.assertIn("skill_recovery", intervention_sources)
            self.assertIn("verification", intervention_sources)
            self.assertIn("delegated_runtime", intervention_sources)
            self.assertEqual(interventions[0]["severity"], "high")
            self.assertIn("nextAction", interventions[0])
            self.assertTrue(interventions[0]["proofRequired"])

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
            self.assertIn("nas_bridge_run", workflow_map)
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
                        "verification_results": [
                            {
                                "command": "npm run frontend:build",
                                "return_code": 0,
                                "duration_ms": 143000,
                                "status": "executed",
                            }
                        ],
                        "context": {"used_tokens": 449},
                        "blocker_retry_counts": {"verification_failed": 1},
                        "code_execution": {
                            "artifacts": [
                                {"artifact_id": "proof_one", "created_at": "2026-05-20T12:01:00+00:00"}
                            ]
                        },
                        "handoff_packets": ["handoff_one.md"],
                        "route_configs": [
                            {
                                "role": "executor",
                                "provider": "openai",
                                "model": "gpt-5.4-mini",
                                "effort": "medium",
                                "budget_class": "efficient",
                            }
                        ],
                        "delegated_runtime_sessions": [
                            {
                                "delegated_id": "delegate_one",
                                "runtime_id": "hermes",
                                "target_phase": "execute",
                                "target_provider": "openai",
                                "target_model": "gpt-5.4-mini",
                            }
                        ],
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
                        "target_phase": "execute",
                        "target_provider": "openai",
                        "target_model": "gpt-5.4-mini",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            proof_dir = root / "artifacts" / "runtime-lanes" / "runtime-lane-proof-test"
            proof_dir.mkdir(parents=True)
            (proof_dir / "runtime_lane_proof.json").write_text(
                json.dumps(
                    {
                        "runId": "runtime-lane-proof-test",
                        "mode": "deterministic-no-live-runtime-call",
                        "proofType": "route_contract_proof",
                        "proofTruth": {
                            "classification": "route_contract_proof",
                            "liveRuntimeExecution": False,
                            "proves": ["route contract construction"],
                            "doesNotProve": ["a live runtime process completed"],
                        },
                        "createdAt": "2026-06-21T00:00:00Z",
                        "lanes": [
                            {
                                "runtimeId": "openclaw",
                                "label": "OpenClaw",
                                "skill": "jbheaven_godmode_lab",
                                "launchCommand": "openclaw agent run --json",
                                "proofMeaning": "OpenClaw route contract proof only.",
                                "routeSummary": "OpenClaw / OpenAI Codex",
                                "routeContract": {
                                    "provider": "openai-codex",
                                    "model": "gpt-5.4-mini",
                                },
                                "readiness": {
                                    "status": "contract_ready_live_unverified",
                                    "promotionBlocked": True,
                                    "blockingGateCount": 2,
                                    "nextRecoveryAction": "Run one bounded OpenClaw proving mission and attach the runtime session events.",
                                    "gates": [
                                        {
                                            "gateId": "openclaw_cli_available",
                                            "label": "OpenClaw CLI available",
                                            "status": "unchecked",
                                            "proofArtifact": "runtime_lane_proof.json",
                                            "recoveryAction": "Run setup doctor or install OpenClaw before promoting this lane to live execution.",
                                            "blocksPromotion": True,
                                        },
                                        {
                                            "gateId": "openclaw_json_session_output",
                                            "label": "JSON session output observed",
                                            "status": "needs_live_validation",
                                            "proofArtifact": "runtime_session.events.jsonl",
                                            "recoveryAction": "Run one bounded OpenClaw proving mission and attach the runtime session events.",
                                            "blocksPromotion": True,
                                        },
                                    ],
                                },
                            },
                            {
                                "runtimeId": "hermes",
                                "label": "Hermes",
                                "skill": "jbheaven_godmode_lab",
                                "launchCommand": "hermes chat --provider minimax",
                                "proofMeaning": "Hermes skill payload proof only.",
                                "routeSummary": "Hermes / MiniMax",
                                "routeContract": {
                                    "provider": "minimax",
                                    "model": "MiniMax-M3",
                                },
                                "readiness": {
                                    "status": "contract_ready_live_unverified",
                                    "promotionBlocked": True,
                                    "blockingGateCount": 2,
                                    "nextRecoveryAction": "Run a supervised synthetic lab transcript and attach visible prompts, responses, scores, and reviewer notes.",
                                    "gates": [
                                        {
                                            "gateId": "hermes_cli_available",
                                            "label": "Hermes CLI available",
                                            "status": "unchecked",
                                            "proofArtifact": "runtime_lane_proof.json",
                                            "recoveryAction": "Repair Hermes from setup or NAS runtime doctor before long-running delegated work.",
                                            "blocksPromotion": True,
                                        },
                                        {
                                            "gateId": "hermes_transcript_proof_observed",
                                            "label": "Transcript proof observed",
                                            "status": "needs_live_validation",
                                            "proofArtifact": "red_team_transcript.md",
                                            "recoveryAction": "Run a supervised synthetic lab transcript and attach visible prompts, responses, scores, and reviewer notes.",
                                            "blocksPromotion": True,
                                        },
                                    ],
                                },
                            },
                        ],
                        "fusedRuntime": {
                            "readinessSummary": {
                                "overallStatus": "contract_ready_live_unverified",
                                "promotionBlocked": True,
                                "blockingGateCount": 4,
                                "lanes": [
                                    {
                                        "runtimeId": "openclaw",
                                        "status": "contract_ready_live_unverified",
                                        "blockingGateCount": 2,
                                        "nextRecoveryAction": "Run one bounded OpenClaw proving mission and attach the runtime session events.",
                                    },
                                    {
                                        "runtimeId": "hermes",
                                        "status": "contract_ready_live_unverified",
                                        "blockingGateCount": 2,
                                        "nextRecoveryAction": "Run a supervised synthetic lab transcript and attach visible prompts, responses, scores, and reviewer notes.",
                                    },
                                ],
                            },
                        },
                        "artifactPaths": {
                            "proof": str(proof_dir / "runtime_lane_proof.json"),
                            "markdown": str(proof_dir / "RUNTIME_LANE_PROOF.md"),
                            "route_scorecard": str(proof_dir / "route_scorecard.json"),
                        },
                        "safetyContract": {
                            "liveModelCalls": False,
                            "realTargets": False,
                            "harmfulInstructions": False,
                            "runtimeAdapterAdded": False,
                            "openCodeGoRuntimeAdded": False,
                            "liveRuntimeExecution": False,
                            "proofType": "route_contract_proof",
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            (proof_dir / "RUNTIME_LANE_PROOF.md").write_text(
                "# Runtime lane proof\n",
                encoding="utf-8",
            )
            (proof_dir / "route_scorecard.json").write_text(
                json.dumps({"schemaVersion": "benchmark-board-route-scorecard/v1"}),
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
            self.assertTrue(
                any(item["routeContractResolved"] for item in snapshot["recentRuns"])
            )
            self.assertTrue(
                any(item["routeProvider"] == "openai" for item in snapshot["recentRuns"])
            )
            fused_runtime = snapshot["fusedRuntime"]
            self.assertEqual(fused_runtime["status"], "operational")
            self.assertEqual(fused_runtime["productionHarness"], "fluxio_hybrid")
            self.assertEqual(
                fused_runtime["compatibilityHarnesses"],
                ["legacy_autonomous_engine"],
            )
            self.assertIn("route_contracts", fused_runtime["fusionPoints"])
            self.assertEqual(fused_runtime["proofSignals"]["delegatedRunCount"], 1)
            self.assertEqual(fused_runtime["proofSignals"]["routeContractRunCount"], 1)
            self.assertEqual(
                fused_runtime["proofSignals"]["fusedRuntimeRole"],
                "supervisor_not_runtime_adapter",
            )
            self.assertEqual(
                fused_runtime["latestLaneProof"]["runId"],
                "runtime-lane-proof-test",
            )
            self.assertEqual(
                fused_runtime["latestLaneProof"]["proofType"],
                "route_contract_proof",
            )
            self.assertFalse(
                fused_runtime["latestLaneProof"]["proofTruth"]["liveRuntimeExecution"]
            )
            self.assertEqual(
                fused_runtime["latestLaneProof"]["lanes"][0]["skill"],
                "jbheaven_godmode_lab",
            )
            self.assertIn(
                "readiness",
                fused_runtime["latestLaneProof"]["lanes"][0],
            )
            self.assertEqual(
                fused_runtime["latestLaneProof"]["lanes"][0]["launchCommand"],
                "openclaw agent run --json",
            )
            self.assertEqual(
                fused_runtime["latestLaneProof"]["readinessSummary"]["blockingGateCount"],
                4,
            )
            self.assertEqual(
                fused_runtime["proofGateSummary"]["schemaVersion"],
                "runtime-proof-gate-summary.v1",
            )
            self.assertTrue(fused_runtime["proofGateSummary"]["promotionBlocked"])
            self.assertEqual(fused_runtime["proofGateSummary"]["blockingGateCount"], 5)
            self.assertEqual(fused_runtime["proofGateSummary"]["liveValidationGateCount"], 2)
            self.assertEqual(fused_runtime["proofGateSummary"]["uncheckedGateCount"], 2)
            self.assertEqual(fused_runtime["proofGateSummary"]["presentArtifactCount"], 3)
            self.assertEqual(fused_runtime["proofGateSummary"]["missingArtifactCount"], 2)
            self.assertFalse(fused_runtime["proofGateSummary"]["artifactComplete"])
            self.assertIn(
                "Rerun the deterministic runtime lane proof harness",
                fused_runtime["proofGateSummary"]["nextRecoveryActions"][0],
            )
            self.assertIn(
                "red_team_transcript.md",
                fused_runtime["proofGateSummary"]["missingGateArtifacts"],
            )
            self.assertIn(
                "python scripts/runtime_lane_proof_harness.py --run-id runtime-lane-proof-test",
                fused_runtime["proofGateSummary"]["proofRunCommand"],
            )
            self.assertIn(
                "runtime_session.events.jsonl",
                fused_runtime["proofGateSummary"]["requiredArtifacts"],
            )
            self.assertIn(
                "Run one bounded OpenClaw proving mission",
                " ".join(fused_runtime["proofGateSummary"]["nextRecoveryActions"]),
            )
            self.assertFalse(
                fused_runtime["latestLaneProof"]["safetyContract"]["liveModelCalls"]
            )
            self.assertFalse(
                fused_runtime["latestLaneProof"]["safetyContract"]["runtimeAdapterAdded"]
            )
            self.assertFalse(
                fused_runtime["latestLaneProof"]["safetyContract"]["liveRuntimeExecution"]
            )
            artifact_integrity = fused_runtime["latestLaneProof"]["artifactIntegrity"]
            self.assertEqual(
                artifact_integrity["schemaVersion"],
                "runtime-proof-artifact-integrity.v1",
            )
            self.assertEqual(artifact_integrity["presentCount"], 3)
            self.assertEqual(artifact_integrity["missingCount"], 2)
            self.assertFalse(artifact_integrity["artifactComplete"])
            self.assertIn("runtime_session.events.jsonl", artifact_integrity["missingGateArtifacts"])
            self.assertTrue(
                all(item["exists"] for item in artifact_integrity["artifacts"])
            )
            lane_roles = {
                item["runtimeId"]: item["role"]
                for item in fused_runtime["runtimeLanes"]
            }
            self.assertNotIn("opencode", lane_roles)
            self.assertEqual(lane_roles["hermes"], "executable_runtime_lane")
            provider_routes = {
                item["provider"]: item
                for item in fused_runtime["modelProviderRoutes"]
            }
            self.assertNotIn("opencode", provider_routes)
            self.assertGreaterEqual(provider_routes["openai"]["observedCount"], 1)
            route_decisions = snapshot["routeDecisionRows"]
            self.assertTrue(route_decisions)
            self.assertTrue(
                any(item["provider"] == "openai" for item in route_decisions)
            )
            self.assertTrue(
                any(item["runtimeId"] == "hermes" for item in route_decisions)
            )
            self.assertTrue(
                any(item["model"] == "gpt-5.4-mini" for item in route_decisions)
            )
            self.assertTrue(
                all("decision" in item and "recommendation" in item for item in route_decisions)
            )
            self.assertTrue(
                all("harnessId" in item and "fitLabel" in item and "fitReason" in item for item in route_decisions)
            )
            self.assertTrue(
                any(item["harnessId"] == "fluxio_hybrid" for item in route_decisions)
            )
            self.assertTrue(
                any(item["fitLabel"] == "High confidence" for item in route_decisions)
            )
            openai_route = next(item for item in route_decisions if item["provider"] == "openai")
            self.assertFalse(openai_route["benchmarkCandidate"])
            self.assertEqual(openai_route["sourceKind"], "local")
            self.assertTrue(openai_route["routeTier"].startswith("F"))
            self.assertIn(openai_route["costBand"], {"observed", "unknown"})
            self.assertEqual(openai_route["evidenceKind"], "local_proof")
            self.assertEqual(openai_route["promotionStatus"], "usable_now")
            self.assertFalse(openai_route["decisionRecommendation"]["localProofRequired"])
            self.assertIn("outcomeScorecard", openai_route)
            self.assertEqual(openai_route["outcomeScorecard"]["totalTokens"], 449)
            self.assertEqual(openai_route["outcomeScorecard"]["wallTimeSeconds"], 143)
            self.assertEqual(openai_route["outcomeScorecard"]["retryCount"], 1)
            self.assertEqual(openai_route["outcomeScorecard"]["latestTestResult"], "passed")
            self.assertEqual(openai_route["outcomeScorecard"]["proofArtifactCount"], 3)
            guide = snapshot["routeDecisionGuide"]
            self.assertEqual(guide["schemaVersion"], "benchmark-route-decision-guide.v1")
            self.assertEqual(guide["sourceMode"], "local_proof")
            self.assertEqual(guide["primaryRouteId"], openai_route["id"])
            self.assertIn("Approval waits dominate", snapshot["recommendation"])

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
