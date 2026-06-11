from __future__ import annotations

import json
import pathlib
import tempfile
import unittest
from unittest import mock

from grant_agent.mission_control import ControlRoomStore
from grant_agent.workspace_actions import execute_control_room_workspace_action


class WorkspaceBridgeActionTests(unittest.TestCase):
    def _write_oratio_manifest(self, root: pathlib.Path, app_root: pathlib.Path) -> None:
        (root / "config").mkdir(parents=True, exist_ok=True)
        (root / ".agent_control").mkdir(parents=True, exist_ok=True)
        (root / "config" / "connected_apps.json").write_text(
            json.dumps(
                [
                    {
                        "manifest_id": "manifest_oratio_viva",
                        "schema_version": "fluxio.app-capability/v0-draft",
                        "app_id": "oratio-viva",
                        "name": "Oratio Viva",
                        "description": "Speech bridge",
                        "bridge": {
                            "transport": "http",
                            "endpoint": "http://127.0.0.1:47830/fluxio",
                            "healthcheck": "/health",
                            "event_stream": "/events",
                            "workspace_root": str(app_root),
                        },
                        "auth": {"mode": "local_token", "scopes": ["speech.manage"]},
                        "permissions": ["task.run", "context.read", "action.invoke"],
                        "tasks": [
                            {
                                "task_id": "render-voice-preview",
                                "label": "Render voice preview",
                                "description": "Preview",
                            }
                        ],
                        "context_surfaces": [
                            {
                                "surface_id": "voice-catalog",
                                "label": "Voice Catalog",
                                "description": "Voices",
                                "access": "read",
                            }
                        ],
                        "action_hooks": [
                            {
                                "hook_id": "queue-render",
                                "label": "Queue Render",
                                "description": "Queue",
                                "mutability": "write",
                            }
                        ],
                        "ui_hints": {
                            "bridgeRole": "voice_runtime",
                            "runtimeManager": "voice-and-relax-engine-manager",
                            "skillCandidate": "voice-preview-workflow",
                            "aliases": ["relax engines"],
                        },
                    }
                ],
                indent=2,
            ),
            encoding="utf-8",
        )

    def test_app_runtime_start_action_records_command_pid_health_and_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir) / "vibe-coding-platform"
            app_root = pathlib.Path(temp_dir) / "OratioViva"
            (app_root / "backend").mkdir(parents=True)
            (app_root / "backend" / "relax_worker.py").write_text("print('ok')\n", encoding="utf-8")
            root.mkdir(parents=True)
            self._write_oratio_manifest(root, app_root)
            store = ControlRoomStore(root)

            with mock.patch(
                "grant_agent.workspace_actions._probe_health_url",
                side_effect=[{}, {"status": "ok"}],
            ), mock.patch(
                "grant_agent.workspace_actions._launch_background_app_command",
                return_value={"ok": True, "pid": 4321, "logPath": str(root / ".agent_control" / "bridge_logs" / "oratio.log")},
            ) as launch:
                payload = execute_control_room_workspace_action(
                    store=store,
                    root=root,
                    surface="bridge",
                    action_id="start-oratio-viva",
                )

            self.assertTrue(payload["ok"])
            result = payload["record"]["result"]
            self.assertEqual(result["payload"]["commandSurface"], "bridge.start_app")
            self.assertIn("python -m uvicorn backend.main:app", result["payload"]["startCommand"])
            self.assertEqual(result["payload"]["pid"], 4321)
            self.assertTrue(result["payload"]["healthOnline"])
            self.assertTrue(result["payload"]["logPath"].endswith(".log"))
            self.assertIn("start command launched", result["result_summary"])
            launch.assert_called_once()

    def test_app_runtime_health_action_records_honest_offline_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir) / "vibe-coding-platform"
            app_root = pathlib.Path(temp_dir) / "OratioViva"
            (app_root / "backend").mkdir(parents=True)
            root.mkdir(parents=True)
            self._write_oratio_manifest(root, app_root)
            store = ControlRoomStore(root)

            with mock.patch("grant_agent.workspace_actions._probe_health_url", return_value={}):
                payload = execute_control_room_workspace_action(
                    store=store,
                    root=root,
                    surface="bridge",
                    action_id="check-oratio-viva-health",
                )

            self.assertFalse(payload["ok"])
            result = payload["record"]["result"]
            self.assertEqual(result["payload"]["commandSurface"], "bridge.app_health")
            self.assertFalse(result["payload"]["healthOnline"])
            self.assertIn("health did not respond", result["result_summary"])

    def test_app_runtime_health_action_persists_connected_app_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir) / "vibe-coding-platform"
            app_root = pathlib.Path(temp_dir) / "OratioViva"
            (app_root / "backend").mkdir(parents=True)
            root.mkdir(parents=True)
            self._write_oratio_manifest(root, app_root)
            store = ControlRoomStore(root)

            with mock.patch(
                "grant_agent.workspace_actions._probe_health_url",
                return_value={"status": "ok"},
            ):
                payload = execute_control_room_workspace_action(
                    store=store,
                    root=root,
                    surface="bridge",
                    action_id="check-oratio-viva-health",
                )

            self.assertTrue(payload["ok"])
            state = json.loads(
                (root / ".agent_control" / "connected_apps_state.json").read_text(
                    encoding="utf-8"
                )
            )
            latest = state["oratio-viva"]["latest_task_result"]
            self.assertEqual(latest["sourceKind"], "workspace_action")
            self.assertEqual(latest["payload"]["commandSurface"], "bridge.app_health")
            self.assertTrue(latest["payload"]["bridgeOnline"])
            self.assertIn("health responded", latest["resultSummary"])

    def test_app_runtime_health_action_uses_lightweight_receipt_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir) / "vibe-coding-platform"
            app_root = pathlib.Path(temp_dir) / "OratioViva"
            (app_root / "backend").mkdir(parents=True)
            root.mkdir(parents=True)
            self._write_oratio_manifest(root, app_root)
            store = ControlRoomStore(root)

            with mock.patch("grant_agent.workspace_actions._probe_health_url", return_value={}):
                with mock.patch.object(store, "build_snapshot", side_effect=AssertionError("full snapshot should not run")):
                    payload = execute_control_room_workspace_action(
                        store=store,
                        root=root,
                        surface="bridge",
                        action_id="check-oratio-viva-health",
                    )

            self.assertEqual(payload["snapshot"]["summaryMode"], "workspace_action_receipt")
            self.assertEqual(payload["snapshot"]["source"], "bridge_app_action")
            self.assertEqual(
                payload["snapshot"]["latestWorkspaceAction"]["result"]["payload"]["commandSurface"],
                "bridge.app_health",
            )
            self.assertEqual(payload["snapshot"]["connectedApp"]["appId"], "oratio-viva")
            self.assertEqual(payload["snapshot"]["connectedApp"]["healthUrl"], "http://127.0.0.1:8000/health")
            self.assertNotIn("bridgeLab", payload["snapshot"])

    def test_app_runtime_start_action_reports_immediate_process_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir) / "vibe-coding-platform"
            app_root = pathlib.Path(temp_dir) / "OratioViva"
            log_path = root / ".agent_control" / "bridge_logs" / "oratio.log"
            (app_root / "backend").mkdir(parents=True)
            log_path.parent.mkdir(parents=True)
            log_path.write_text("/usr/bin/python: No module named uvicorn\n", encoding="utf-8")
            root.mkdir(parents=True, exist_ok=True)
            self._write_oratio_manifest(root, app_root)
            store = ControlRoomStore(root)

            with mock.patch(
                "grant_agent.workspace_actions._probe_health_url",
                side_effect=[{}, {}],
            ), mock.patch(
                "grant_agent.workspace_actions._launch_background_app_command",
                return_value={"ok": True, "pid": 4321, "logPath": str(log_path)},
            ), mock.patch("grant_agent.workspace_actions._process_is_running", return_value=False):
                payload = execute_control_room_workspace_action(
                    store=store,
                    root=root,
                    surface="bridge",
                    action_id="start-oratio-viva",
                )

            self.assertFalse(payload["ok"])
            result = payload["record"]["result"]
            self.assertEqual(result["exit_code"], 1)
            self.assertFalse(result["payload"]["processRunning"])
            self.assertIn("Process exited during startup", result["error"])
            self.assertIn("No module named uvicorn", result["error"])


if __name__ == "__main__":
    unittest.main()
