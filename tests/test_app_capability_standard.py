from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.app_capability_standard import build_connected_apps_snapshot
from grant_agent.mission_control import ControlRoomStore


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

    def test_build_connected_apps_snapshot_uses_live_reference_app_and_follow_on_solantir(self) -> None:
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

            snapshot = build_connected_apps_snapshot(workspace_root)

            sessions = {item["app_id"]: item for item in snapshot["connectedSessions"]}
            self.assertEqual(sessions["oratio-viva"]["status"], "available")
            self.assertEqual(sessions["oratio-viva"]["bridge_health"], "offline")
            self.assertNotIn("mind-tower", sessions)
            self.assertEqual(sessions["solantir-terminal"]["status"], "follow_on_manifest")
            self.assertEqual(
                sessions["oratio-viva"]["task_history"][0]["sourceKind"],
                "connected_app",
            )
            self.assertEqual(
                sessions["oratio-viva"]["task_history"][0]["status"],
                "blocked",
            )
            self.assertEqual(
                sessions["oratio-viva"]["latest_task_result"]["payload"]["engineCount"],
                2,
            )
            self.assertFalse(
                sessions["oratio-viva"]["latest_task_result"]["payload"]["bridgeOnline"]
            )
            self.assertIn(
                "must not claim a render ran",
                sessions["oratio-viva"]["latest_task_result"]["resultSummary"],
            )
            self.assertIn(
                "availableEngines",
                sessions["oratio-viva"]["latest_task_result"]["payload"],
            )
            self.assertNotIn("Mind Tower", {item["name"] for item in snapshot["discoveredApps"]})

    def test_oratio_reports_connected_only_when_bridge_health_responds(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path != "/health":
                    self.send_response(404)
                    self.end_headers()
                    return
                body = json.dumps({"message": "Oratio bridge ready."}).encode("utf-8")
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
                                    "endpoint": f"http://127.0.0.1:{server.server_port}/fluxio",
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
                oratio_root = workspace_root.parent / "OratioViva"
                (oratio_root / "backend").mkdir(parents=True)
                (oratio_root / "backend" / "dia2_worker.py").write_text("print('ok')\n", encoding="utf-8")

                thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
                thread.start()
                snapshot = build_connected_apps_snapshot(workspace_root)
                session = snapshot["connectedSessions"][0]

                self.assertEqual(session["status"], "connected")
                self.assertEqual(session["bridge_health"], "healthy")
                self.assertEqual(session["latest_task_result"]["status"], "completed")
                self.assertTrue(session["latest_task_result"]["payload"]["bridgeOnline"])
                self.assertIn("Oratio bridge ready", session["notes"][0])
        finally:
            server.shutdown()

    def test_oratio_missing_state_is_honest_and_agent_setup_ready(self) -> None:
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
                            "ui_hints": {
                                "runtimeManager": "voice-and-relax-engine-manager",
                                "skillCandidate": "voice-preview-workflow",
                                "aliases": ["relax engines", "voice engines"],
                            },
                        }
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )

            snapshot = build_connected_apps_snapshot(workspace_root)
            session = snapshot["connectedSessions"][0]

            self.assertEqual(session["app_id"], "oratio-viva")
            self.assertEqual(session["status"], "missing")
            self.assertEqual(session["ui_hints"]["runtimeManager"], "voice-and-relax-engine-manager")
            self.assertIn("relax engines", session["ui_hints"]["aliases"])
            self.assertIn("should not claim a render ran", session["latest_task_result"]["resultSummary"])
            self.assertEqual(
                session["latest_task_result"]["payload"]["bridgeEndpoint"],
                "http://127.0.0.1:47830/fluxio",
            )
            self.assertIn(
                "Bridge endpoint: http://127.0.0.1:47830/fluxio",
                session["context_preview"][0]["items"],
            )

    def test_oratio_previous_receipts_gain_current_engine_inventory(self) -> None:
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
                            "ui_hints": {
                                "runtimeManager": "voice-and-relax-engine-manager",
                                "skillCandidate": "voice-preview-workflow",
                            },
                        }
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )
            oratio_root = workspace_root.parent / "OratioViva"
            (oratio_root / "backend").mkdir(parents=True)
            (oratio_root / "backend" / "dia2_worker.py").write_text("print('ok')\n", encoding="utf-8")
            (oratio_root / "backend" / "qwen_tts_worker.py").write_text("print('ok')\n", encoding="utf-8")
            (workspace_root / ".agent_control" / "connected_apps_state.json").write_text(
                json.dumps(
                    {
                        "oratio-viva": {
                            "session_id": "bridge_oratio-viva",
                            "task_history": [
                                {
                                    "taskId": "render-voice-preview",
                                    "label": "Render voice preview",
                                    "status": "completed",
                                    "payload": {"selectedEngine": "dia2"},
                                }
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )

            snapshot = build_connected_apps_snapshot(workspace_root)
            session = snapshot["connectedSessions"][0]
            payload = session["latest_task_result"]["payload"]

            self.assertEqual(payload["selectedEngine"], "dia2")
            self.assertEqual(payload["engineCount"], 2)
            self.assertEqual(payload["availableEngines"], ["dia2", "qwen_tts"])
            self.assertEqual(payload["runtimeManager"], "voice-and-relax-engine-manager")

    def test_release_root_can_find_project_level_oratio_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = pathlib.Path(temp_dir) / "projects"
            workspace_root = project_root / "syntelos" / "releases" / "20260609-000000"
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
                            "ui_hints": {"runtimeManager": "voice-and-relax-engine-manager"},
                        }
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )
            oratio_root = project_root / "Projects" / "OratioViva"
            (oratio_root / "backend").mkdir(parents=True)
            (oratio_root / "backend" / "chroma_worker.py").write_text("print('ok')\n", encoding="utf-8")

            snapshot = build_connected_apps_snapshot(workspace_root)
            session = snapshot["connectedSessions"][0]

            self.assertEqual(session["status"], "available")
            self.assertEqual(session["bridge_health"], "offline")
            self.assertEqual(session["app_root"], str(oratio_root.resolve()))
            self.assertEqual(session["latest_task_result"]["payload"]["engineCount"], 1)
            self.assertFalse(session["latest_task_result"]["payload"]["bridgeOnline"])

    def test_mind_tower_follow_on_bridge_is_visible_for_time_management_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = pathlib.Path(temp_dir) / "vibe-coding-platform"
            workspace_root.mkdir(parents=True)
            (workspace_root / "config").mkdir()
            (workspace_root / ".agent_control").mkdir()
            (workspace_root / "config" / "connected_apps.json").write_text(
                json.dumps(
                    [
                        {
                            "manifest_id": "manifest_mind_tower",
                            "schema_version": "fluxio.app-capability/v0-draft",
                            "app_id": "mind-tower",
                            "name": "Mind Tower",
                            "description": "Time manager bridge",
                            "bridge": {
                                "transport": "http",
                                "endpoint": "http://127.0.0.1:47842/fluxio",
                                "healthcheck": "/health",
                                "event_stream": "/events",
                            },
                            "auth": {"mode": "local_session", "scopes": ["tower.read"]},
                            "permissions": ["task.run", "context.read", "skill.propose"],
                            "tasks": [
                                {
                                    "task_id": "plan-timebox",
                                    "label": "Plan timebox",
                                    "description": "Plan",
                                }
                            ],
                            "context_surfaces": [
                                {
                                    "surface_id": "tower-focus-board",
                                    "label": "Tower Focus Board",
                                    "description": "Board",
                                    "access": "read",
                                }
                            ],
                            "action_hooks": [
                                {
                                    "hook_id": "propose-skill",
                                    "label": "Propose Skill",
                                    "description": "Draft",
                                    "mutability": "write",
                                }
                            ],
                            "ui_hints": {
                                "bridgeRole": "personal_manager",
                                "runtimeManager": "timebox-and-skill-manager",
                                "skillCandidate": "time-management-workflow",
                                "aliases": ["tower", "time manager", "JBHABCN"],
                            },
                        }
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )

            mind_root = workspace_root.parent / "mind-tower"
            (mind_root / "apps" / "admin").mkdir(parents=True)
            (mind_root / "services" / "monitor-worker").mkdir(parents=True)
            (mind_root / "skills" / "mindtower-signal-ops").mkdir(parents=True)
            (mind_root / "package.json").write_text(
                json.dumps({"name": "mind-tower", "version": "0.1.0"}),
                encoding="utf-8",
            )

            snapshot = build_connected_apps_snapshot(workspace_root)
            session = snapshot["connectedSessions"][0]
            self.assertEqual(session["app_id"], "mind-tower")
            self.assertEqual(session["status"], "available")
            self.assertEqual(session["bridge_health"], "offline")
            self.assertEqual(session["ui_hints"]["runtimeManager"], "timebox-and-skill-manager")
            self.assertIn("pnpm --filter @mindtower/admin dev", session["ui_hints"]["startCommand"])
            self.assertEqual(session["ui_hints"]["healthUrl"], "http://127.0.0.1:3000/api/connections/status")
            self.assertIn("JBHABCN", session["ui_hints"]["aliases"])
            self.assertEqual(
                session["latest_task_result"]["payload"]["skillCandidate"],
                "time-management-workflow",
            )
            self.assertFalse(session["latest_task_result"]["payload"]["bridgeOnline"])
            self.assertIn("skill:mindtower-signal-ops", session["context_preview"][0]["items"])
            self.assertEqual(session["action_hooks"][0]["hookId"], "propose-skill")
            self.assertEqual(session["action_hooks"][0]["label"], "Propose Skill")
            self.assertEqual(session["action_hooks"][0]["riskLevel"], "low")
            self.assertIn("bridge endpoint is offline", session["latest_task_result"]["resultSummary"])

    def test_python_app_runtime_prefers_fluxio_app_venv_when_available(self) -> None:
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
                            "auth": {"mode": "local_token", "scopes": ["speech.manage"]},
                            "permissions": ["task.run", "context.read", "action.invoke"],
                            "tasks": [{"task_id": "render-voice-preview", "label": "Render", "description": "Render"}],
                            "context_surfaces": [
                                {
                                    "surface_id": "voice-catalog",
                                    "label": "Voice Catalog",
                                    "description": "Voices",
                                    "access": "read",
                                }
                            ],
                            "action_hooks": [{"hook_id": "queue-render", "label": "Queue", "description": "Queue", "mutability": "write"}],
                            "ui_hints": {"bridgeRole": "voice_runtime"},
                        }
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )
            app_root = workspace_root.parent / "OratioViva"
            (app_root / "backend").mkdir(parents=True)
            venv_python = app_root / ".venv_fluxio" / ("Scripts" if os.name == "nt" else "bin") / (
                "python.exe" if os.name == "nt" else "python"
            )
            venv_python.parent.mkdir(parents=True)
            venv_python.write_text("", encoding="utf-8")

            snapshot = build_connected_apps_snapshot(workspace_root)
            command = snapshot["connectedSessions"][0]["ui_hints"]["startCommand"]
            self.assertIn(str(venv_python), command)
            self.assertIn("-m uvicorn backend.main:app", command)

    def test_summary_snapshot_includes_bridge_lab_for_agent_drawer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = pathlib.Path(temp_dir) / "vibe-coding-platform"
            workspace_root.mkdir(parents=True)
            (workspace_root / "config").mkdir()
            (workspace_root / ".agent_control").mkdir()
            (workspace_root / "config" / "connected_apps.json").write_text(
                json.dumps(
                    [
                        {
                            "manifest_id": "manifest_mind_tower",
                            "schema_version": "fluxio.app-capability/v0-draft",
                            "app_id": "mind-tower",
                            "name": "Mind Tower",
                            "description": "Time manager bridge",
                            "bridge": {
                                "transport": "http",
                                "endpoint": "http://127.0.0.1:47842/fluxio",
                                "healthcheck": "/health",
                                "event_stream": "/events",
                            },
                            "auth": {"mode": "local_session", "scopes": ["tower.read"]},
                            "permissions": ["task.run", "context.read", "skill.propose"],
                            "tasks": [
                                {
                                    "task_id": "plan-timebox",
                                    "label": "Plan timebox",
                                    "description": "Plan",
                                }
                            ],
                            "context_surfaces": [
                                {
                                    "surface_id": "tower-focus-board",
                                    "label": "Tower Focus Board",
                                    "description": "Board",
                                    "access": "read",
                                }
                            ],
                            "action_hooks": [
                                {
                                    "hook_id": "propose-skill",
                                    "label": "Propose Skill",
                                    "description": "Draft",
                                    "mutability": "write",
                                }
                            ],
                        }
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )

            summary = ControlRoomStore(workspace_root).build_summary_snapshot()
            sessions = summary["bridgeLab"]["connectedSessions"]
            self.assertEqual(sessions[0]["app_id"], "mind-tower")
            self.assertEqual(sessions[0]["status"], "missing")
            bootstrap = ControlRoomStore(workspace_root).build_bootstrap_summary_snapshot()
            bootstrap_sessions = bootstrap["bridgeLab"]["connectedSessions"]
            self.assertEqual(bootstrap_sessions[0]["app_id"], "mind-tower")

    def test_mind_tower_uses_python_bridge_when_pnpm_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = pathlib.Path(temp_dir) / "vibe-coding-platform"
            workspace_root.mkdir(parents=True)
            (workspace_root / "config").mkdir()
            (workspace_root / ".agent_control").mkdir()
            app_root = workspace_root.parent / "mind-tower"
            app_root.mkdir(parents=True)
            (app_root / "package.json").write_text('{"name":"mind-tower"}', encoding="utf-8")
            (workspace_root / "config" / "connected_apps.json").write_text(
                json.dumps(
                    [
                        {
                            "manifest_id": "manifest_mind_tower",
                            "schema_version": "fluxio.app-capability/v0-draft",
                            "app_id": "mind-tower",
                            "name": "Mind Tower",
                            "description": "Time manager bridge",
                            "bridge": {
                                "transport": "http",
                                "endpoint": "http://127.0.0.1:47842/fluxio",
                                "healthcheck": "/health",
                                "event_stream": "/events",
                            },
                            "auth": {"mode": "local_session", "scopes": ["tower.read"]},
                            "permissions": ["task.run", "context.read", "skill.propose"],
                            "tasks": [{"task_id": "plan-timebox", "label": "Plan timebox", "description": "Plan"}],
                            "context_surfaces": [
                                {
                                    "surface_id": "tower-focus-board",
                                    "label": "Tower Focus Board",
                                    "description": "Board",
                                    "access": "read",
                                }
                            ],
                            "action_hooks": [
                                {
                                    "hook_id": "propose-skill",
                                    "label": "Propose Skill",
                                    "description": "Draft",
                                    "mutability": "write",
                                }
                            ],
                        }
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )

            with mock.patch("grant_agent.app_capability_standard.shutil.which", return_value=None):
                snapshot = build_connected_apps_snapshot(workspace_root)

            command = snapshot["connectedSessions"][0]["ui_hints"]["startCommand"]
            self.assertIn("mind_tower_bridge.py", command)
            self.assertIn("--port 3001", command)
            self.assertNotIn("pnpm --filter", command)
            self.assertEqual(
                snapshot["connectedSessions"][0]["ui_hints"]["healthUrl"],
                "http://127.0.0.1:3001/api/connections/status",
            )

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
                self.assertEqual(session["ui_hints"]["bridgeRole"], "nas_storage")
                self.assertEqual(session["ui_hints"]["sourceRoot"], "C:/Users/paul/projects/Cowork")
                self.assertEqual(session["ui_hints"]["targetRoot"], "/volume1/Cowork")
                self.assertEqual(
                    session["latest_task_result"]["payload"]["safeDirections"],
                    ["upload", "download"],
                )
                self.assertTrue(
                    session["latest_task_result"]["payload"]["requiresApprovalForWrite"]
                )
                self.assertEqual(
                    session["latest_task_result"]["payload"]["bridgePlan"]["writePolicy"],
                    "preview_then_approve",
                )
        finally:
            server.shutdown()

    def test_synology_fast_sync_reports_activation_required_when_mapping_is_inactive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = pathlib.Path(temp_dir) / "vibe-coding-platform"
            workspace_root.mkdir(parents=True)
            (workspace_root / "config").mkdir()
            (workspace_root / ".agent_control").mkdir()
            cowork_root = workspace_root.parent / "Cowork"
            cowork_root.mkdir(parents=True)
            target_root = workspace_root.parent / "missing-nas" / "projects"
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
                                "endpoint": "http://127.0.0.1:9",
                                "healthcheck": "/api/status",
                                "event_stream": "/api/job",
                                "workspace_root": str(cowork_root),
                                "source_root": str(workspace_root.parent),
                                "target_root": str(target_root),
                                "nas_host": "100.125.54.118",
                                "control_protocol": "ssh",
                                "ssh_user": "Codex2",
                                "ssh_port": 22,
                                "requested_ssh_port": 22,
                                "ssh_port_status": "verified TCP reachability on SSH/SFTP port 22",
                                "remote_project_root": "/volume1/Saclay/projects",
                                "connection_mode": "tailscale",
                                "activation_project": "Core",
                                "activation_command": str(cowork_root / "map-synology-fast-path.cmd"),
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

            snapshot = build_connected_apps_snapshot(workspace_root)
            session = snapshot["connectedSessions"][0]
            payload = session["latest_task_result"]["payload"]
            self.assertEqual(session["status"], "available")
            self.assertFalse(payload["targetReady"])
            self.assertTrue(payload["activationRequired"])
            self.assertEqual(payload["activationProject"], "Core")
            self.assertIn("Activate the Core project", payload["activationHint"])
            self.assertEqual(payload["controlProtocol"], "ssh")
            self.assertEqual(payload["controlPort"], 22)
            self.assertEqual(payload["requestedSshPort"], 22)
            self.assertEqual(payload["sshPortStatus"], "verified TCP reachability on SSH/SFTP port 22")
            self.assertEqual(payload["sshUser"], "Codex2")
            self.assertEqual(payload["remoteProjectRoot"], "/volume1/Saclay/projects")

    def test_synology_fast_sync_can_enable_automatic_bidirectional_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = pathlib.Path(temp_dir) / "vibe-coding-platform"
            workspace_root.mkdir(parents=True)
            (workspace_root / "config").mkdir()
            (workspace_root / ".agent_control").mkdir()
            cowork_root = workspace_root.parent / "Cowork"
            cowork_root.mkdir(parents=True)
            target_root = workspace_root.parent / "nas-projects"
            target_root.mkdir(parents=True)
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
                                "endpoint": "http://127.0.0.1:9",
                                "healthcheck": "/api/status",
                                "event_stream": "/api/job",
                                "workspace_root": str(cowork_root),
                                "source_root": str(workspace_root.parent),
                                "target_root": str(target_root),
                                "nas_host": "100.125.54.118",
                                "control_protocol": "ssh",
                                "ssh_user": "Codex2",
                                "ssh_port": 22,
                                "requested_ssh_port": 22,
                                "remote_project_root": "/volume1/Saclay/projects",
                                "requires_approval_for_write": False,
                                "auto_sync": True,
                                "write_policy": "automatic_bidirectional",
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

            snapshot = build_connected_apps_snapshot(workspace_root)
            payload = snapshot["connectedSessions"][0]["latest_task_result"]["payload"]
            bridge_plan = payload["bridgePlan"]
            self.assertFalse(payload["requiresApprovalForWrite"])
            self.assertTrue(bridge_plan["autoSyncEnabled"])
            self.assertEqual(bridge_plan["writePolicy"], "automatic_bidirectional")
            self.assertEqual(payload["safeDirections"], ["upload", "download"])

    def test_synology_fast_sync_still_builds_session_when_cowork_root_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = pathlib.Path(temp_dir) / "vibe-coding-platform"
            workspace_root.mkdir(parents=True)
            (workspace_root / "config").mkdir()
            (workspace_root / ".agent_control").mkdir()
            remote_root = workspace_root.parent / "nas-projects"
            remote_root.mkdir(parents=True)
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
                                "endpoint": "http://127.0.0.1:9",
                                "healthcheck": "/api/status",
                                "event_stream": "/api/job",
                                "workspace_root": "C:/Users/paul/Projects/Cowork",
                                "source_root": "C:/Users/paul/Projects",
                                "target_root": "Y:/projects",
                                "remote_project_root": str(remote_root),
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

            snapshot = build_connected_apps_snapshot(workspace_root)
            session = snapshot["connectedSessions"][0]
            payload = session["latest_task_result"]["payload"]
            self.assertEqual(session["app_id"], "synology-fast-sync")
            self.assertNotEqual(session["status"], "missing")
            self.assertEqual(payload["targetRoot"], str(remote_root))
            self.assertTrue(payload["targetReady"])

    def test_cloud_drive_bridge_reports_google_login_and_requires_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = pathlib.Path(temp_dir) / "vibe-coding-platform"
            workspace_root.mkdir(parents=True)
            (workspace_root / "config").mkdir()
            (workspace_root / ".agent_control").mkdir()
            cloud_root = pathlib.Path(temp_dir) / "GoogleDrive" / "My Drive"
            cloud_root.mkdir(parents=True)
            (workspace_root / "config" / "connected_apps.json").write_text(
                json.dumps(
                    [
                        {
                            "manifest_id": "manifest_cloud_drive_sync",
                            "schema_version": "fluxio.app-capability/v0-draft",
                            "app_id": "cloud-drive-sync",
                            "name": "Cloud Drive Bridge",
                            "description": "Cloud storage bridge",
                            "bridge": {
                                "transport": "local_mount_oauth",
                                "endpoint": "local://cloud-drive",
                                "healthcheck": "provider-presence",
                                "event_stream": "local-events",
                                "source_root": str(workspace_root.parent),
                            },
                            "auth": {
                                "mode": "google_oauth_or_local_mount",
                                "scopes": ["drive.status"],
                            },
                            "permissions": ["task.run", "context.read", "cloud.plan"],
                            "tasks": [
                                {
                                    "task_id": "monitor-cloud-drive",
                                    "label": "Monitor Cloud Drive bridge",
                                    "description": "Monitor",
                                }
                            ],
                            "context_surfaces": [
                                {
                                    "surface_id": "cloud-drive-status",
                                    "label": "Cloud Drive Status",
                                    "description": "Status",
                                    "access": "read",
                                }
                            ],
                            "action_hooks": [
                                {
                                    "hook_id": "queue-cloud-drive-transfer",
                                    "label": "Queue Cloud Drive Transfer",
                                    "description": "Queue",
                                    "mutability": "write",
                                }
                            ],
                            "ui_hints": {
                                "category": "storage",
                                "bridgeRole": "cloud_storage",
                                "providers": ["google-drive"],
                                "primaryProvider": "google-drive",
                            },
                        }
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )

            original_root = os.environ.get("FLUXIO_GOOGLE_DRIVE_ROOT")
            original_oauth = os.environ.get("FLUXIO_GOOGLE_DRIVE_OAUTH_PRESENT")
            os.environ["FLUXIO_GOOGLE_DRIVE_ROOT"] = str(cloud_root)
            os.environ["FLUXIO_GOOGLE_DRIVE_OAUTH_PRESENT"] = "1"
            try:
                snapshot = build_connected_apps_snapshot(workspace_root)
            finally:
                if original_root is None:
                    os.environ.pop("FLUXIO_GOOGLE_DRIVE_ROOT", None)
                else:
                    os.environ["FLUXIO_GOOGLE_DRIVE_ROOT"] = original_root
                if original_oauth is None:
                    os.environ.pop("FLUXIO_GOOGLE_DRIVE_OAUTH_PRESENT", None)
                else:
                    os.environ["FLUXIO_GOOGLE_DRIVE_OAUTH_PRESENT"] = original_oauth

            session = snapshot["connectedSessions"][0]
            payload = session["latest_task_result"]["payload"]
            self.assertEqual(session["app_id"], "cloud-drive-sync")
            self.assertEqual(session["status"], "connected")
            self.assertEqual(session["ui_hints"]["bridgeRole"], "cloud_storage")
            self.assertTrue(payload["googleLoginReady"])
            self.assertEqual(payload["safeDirections"], ["upload", "download"])
            self.assertTrue(payload["requiresApprovalForWrite"])
            self.assertEqual(payload["mountedRoots"][0]["provider"], "google-drive")


if __name__ == "__main__":
    unittest.main()
