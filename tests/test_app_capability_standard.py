from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.app_capability_standard import build_connected_apps_snapshot


class AppCapabilityStandardTests(unittest.TestCase):
    def test_build_connected_apps_snapshot_does_not_rewrite_state_when_nothing_changed(self) -> None:
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
                        }
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )

            state_path = workspace_root / ".agent_control" / "connected_apps_state.json"
            build_connected_apps_snapshot(workspace_root)
            original_text = state_path.read_text(encoding="utf-8")
            original_mtime = state_path.stat().st_mtime_ns

            time.sleep(0.05)
            build_connected_apps_snapshot(workspace_root)

            self.assertEqual(state_path.read_text(encoding="utf-8"), original_text)
            self.assertEqual(state_path.stat().st_mtime_ns, original_mtime)
            persisted_state = json.loads(original_text)
            self.assertNotIn("last_seen_at", persisted_state["oratio-viva"])

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

    def test_synology_fast_sync_bridge_uses_http_status_when_available(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/api/status":
                    payload = {
                        "message": "Fast Sync ready on LAN.",
                        "selectedMode": "tailscale",
                        "selectedHost": "synology.local",
                        "targetReady": True,
                        "targetRoot": "/volume1/Cowork",
                        "sourceRoot": "C:/Users/paul/projects/Cowork",
                    }
                elif self.path == "/api/job":
                    payload = {
                        "state": "running",
                        "direction": "upload",
                        "completedFiles": 3,
                        "remainingFiles": 2,
                        "currentPath": "web/index.html",
                    }
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                workspace_root = pathlib.Path(temp_dir) / "vibe-coding-platform"
                workspace_root.mkdir(parents=True)
                (workspace_root / "config").mkdir()
                (workspace_root / ".agent_control").mkdir()
                cowork_root = workspace_root.parent / "Cowork"
                (cowork_root / "synology_fast_ui").mkdir(parents=True)
                (cowork_root / "synology-fast-ui.py").write_text("print('ok')\n", encoding="utf-8")
                (workspace_root / "config" / "connected_apps.json").write_text(
                    json.dumps(
                        [
                            {
                                "manifest_id": "manifest_synology_fast_sync",
                                "schema_version": "fluxio.app-capability/v0-draft",
                                "app_id": "synology-fast-sync",
                                "name": "Synology Fast Sync",
                                "description": "Fast sync bridge",
                                "bridge": {
                                    "transport": "http",
                                    "endpoint": f"http://127.0.0.1:{server.server_port}",
                                    "healthcheck": "/api/status",
                                    "event_stream": "/api/job",
                                },
                                "auth": {"mode": "local_session", "scopes": ["sync.status"]},
                                "permissions": ["task.run", "context.read"],
                                "tasks": [
                                    {
                                        "task_id": "monitor-fast-sync",
                                        "label": "Monitor Fast Sync output",
                                        "description": "Monitor",
                                    }
                                ],
                                "context_surfaces": [
                                    {
                                        "surface_id": "sync-status",
                                        "label": "Sync Status",
                                        "description": "Status",
                                        "access": "read",
                                    }
                                ],
                                "action_hooks": [
                                    {
                                        "hook_id": "start-sync-selection",
                                        "label": "Start Sync Selection",
                                        "description": "Queue selected transfer",
                                        "mutability": "write",
                                    }
                                ],
                            }
                        ],
                        indent=2,
                    ),
                    encoding="utf-8",
                )

                thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
                thread.start()
                snapshot = build_connected_apps_snapshot(workspace_root)
                session = snapshot["connectedSessions"][0]
                self.assertEqual(session["app_id"], "synology-fast-sync")
                self.assertEqual(session["status"], "connected")
                self.assertEqual(session["approval_callback"]["channel"], "mobile_web")
                self.assertIn("Upload output", session["latest_task_result"]["resultSummary"])
                self.assertIn("Fast Sync ready", session["context_preview"][0]["summary"])
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
