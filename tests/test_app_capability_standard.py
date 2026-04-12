from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.app_capability_standard import build_connected_apps_snapshot


class AppCapabilityStandardTests(unittest.TestCase):
    def test_build_connected_apps_snapshot_uses_live_reference_apps_and_follow_on_solantir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = pathlib.Path(temp_dir) / "vibe-coding-platform"
            workspace_root.mkdir(parents=True)
            (workspace_root / "config").mkdir()
            (workspace_root / ".agent_control").mkdir()
            (workspace_root / "config" / "connected_apps.json").write_text(
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
                            },
                            "auth": {"mode": "local_token", "scopes": ["voice.render"]},
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
                                    "description": "Catalog",
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
                        },
                        {
                            "manifest_id": "manifest_mind_tower",
                            "schema_version": "fluxio.app-capability/v0-draft",
                            "app_id": "mind-tower",
                            "name": "Mind Tower",
                            "description": "Monitoring bridge",
                            "bridge": {
                                "transport": "http",
                                "endpoint": "http://127.0.0.1:47831/fluxio",
                                "healthcheck": "/health",
                                "event_stream": "/events",
                            },
                            "auth": {"mode": "local_token", "scopes": ["digest.run"]},
                            "permissions": ["task.run", "context.read", "approval.callback"],
                            "tasks": [
                                {
                                    "task_id": "run-monitor-digest",
                                    "label": "Run monitoring digest",
                                    "description": "Digest",
                                }
                            ],
                            "context_surfaces": [
                                {
                                    "surface_id": "monitoring-dashboard",
                                    "label": "Monitoring Dashboard",
                                    "description": "Dashboard",
                                    "access": "read",
                                }
                            ],
                            "action_hooks": [
                                {
                                    "hook_id": "send-digest",
                                    "label": "Send Digest",
                                    "description": "Digest",
                                    "mutability": "write",
                                }
                            ],
                        },
                        {
                            "manifest_id": "manifest_solantir_terminal",
                            "schema_version": "fluxio.app-capability/v0-draft",
                            "app_id": "solantir-terminal",
                            "name": "Solantir Terminal",
                            "description": "Follow-on bridge",
                            "bridge": {
                                "transport": "ipc",
                                "endpoint": "pipe://fluxio-solantir",
                                "healthcheck": "ping",
                                "event_stream": "events",
                            },
                            "auth": {"mode": "local_session", "scopes": ["watchlist.write"]},
                            "permissions": ["task.run", "context.read", "approval.request"],
                            "tasks": [
                                {
                                    "task_id": "refresh-watchlist",
                                    "label": "Refresh watchlist",
                                    "description": "Watchlist",
                                }
                            ],
                            "context_surfaces": [
                                {
                                    "surface_id": "watchlist",
                                    "label": "Watchlist",
                                    "description": "Watchlist",
                                    "access": "read",
                                }
                            ],
                            "action_hooks": [
                                {
                                    "hook_id": "ack-alert",
                                    "label": "Acknowledge alert",
                                    "description": "Ack",
                                    "mutability": "write",
                                }
                            ],
                        },
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )

            oratio_root = workspace_root.parent / "OratioViva"
            (oratio_root / "backend").mkdir(parents=True)
            (oratio_root / "frontend").mkdir(parents=True)
            (oratio_root / "backend" / "dia2_worker.py").write_text("print('ok')\n", encoding="utf-8")
            (oratio_root / "backend" / "qwen_tts_worker.py").write_text("print('ok')\n", encoding="utf-8")
            (oratio_root / "frontend" / "package.json").write_text(
                json.dumps({"name": "oratio-viva-ui", "version": "0.1.0"}),
                encoding="utf-8",
            )

            mind_root = workspace_root.parent / "mind-tower"
            (mind_root / "apps" / "admin").mkdir(parents=True)
            (mind_root / "apps" / "admin" / "package.json").write_text(
                json.dumps({"name": "mind-tower-admin"}),
                encoding="utf-8",
            )
            (mind_root / "services" / "monitor-worker" / "src" / "mindtower_worker").mkdir(parents=True)
            (mind_root / "services" / "monitor-worker" / "src" / "mindtower_worker" / "telegram_listener.py").write_text(
                "print('ok')\n",
                encoding="utf-8",
            )

            snapshot = build_connected_apps_snapshot(workspace_root)

            sessions = {item["app_id"]: item for item in snapshot["connectedSessions"]}
            self.assertEqual(sessions["oratio-viva"]["status"], "connected")
            self.assertEqual(sessions["mind-tower"]["status"], "connected")
            self.assertEqual(sessions["solantir-terminal"]["status"], "follow_on_manifest")
            self.assertEqual(
                sessions["oratio-viva"]["task_history"][0]["sourceKind"],
                "connected_app",
            )
            self.assertTrue(sessions["mind-tower"]["approval_callback"]["available"])
            self.assertIn("Mind Tower", {item["name"] for item in snapshot["discoveredApps"]})


if __name__ == "__main__":
    unittest.main()
