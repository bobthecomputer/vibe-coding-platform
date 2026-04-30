from __future__ import annotations

import argparse
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.cli import (
    bootstrap_project,
    cmd_control_room,
    cmd_release_readiness,
    cmd_mission_action,
    cmd_mission_start,
    cmd_workspace_action,
    cmd_workspace_save,
)
from grant_agent.models import RuntimeCapability, RuntimeInstallStatus


class ReleaseAcceptanceTests(unittest.TestCase):
    def _run_json_command(self, command, **kwargs) -> tuple[int, dict]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = command(argparse.Namespace(**kwargs))
        return exit_code, json.loads(buffer.getvalue())

    def test_cli_release_readiness_returns_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            exit_code, payload = self._run_json_command(
                cmd_release_readiness,
                root=str(root),
            )
            self.assertEqual(exit_code, 0)
            self.assertIn("releaseReadiness", payload)
            self.assertIn("score", payload["releaseReadiness"])

    def test_cli_mission_start_uses_saved_telegram_destination_when_flag_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir) / "vibe-coding-platform"
            root.mkdir(parents=True)
            bootstrap_project(root)
            (root / "pyproject.toml").write_text("[project]\nname='fluxio-demo'\n", encoding="utf-8")
            (root / "package.json").write_text('{"name":"fluxio-demo"}\n', encoding="utf-8")
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True, exist_ok=True)
            (control_dir / "telegram_settings.json").write_text(
                json.dumps({"destination": "@fluxio_default"}, indent=2),
                encoding="utf-8",
            )
            self._set_marker(root, "uv")
            self._set_marker(root, "openclaw")
            self._set_marker(root, "hermes")

            with self._patch_acceptance_environment(root):
                save_code, save_payload = self._run_json_command(
                    cmd_workspace_save,
                    root=str(root),
                    name="Fluxio Workspace",
                    path=str(root),
                    default_runtime="openclaw",
                    user_profile="experimental",
                    workspace_id=None,
                )
                self.assertEqual(save_code, 0)
                workspace_id = save_payload["workspace"]["workspace_id"]

                start_code, start_payload = self._run_json_command(
                    cmd_mission_start,
                    root=str(root),
                    workspace_id=workspace_id,
                    runtime="openclaw",
                    objective="Run with default telegram destination.",
                    success_check=["Mission completes"],
                    mode="autopilot",
                    budget_hours=4,
                    profile="experimental",
                    escalation_destination="",
                    run_until="pause_on_failure",
                )
                self.assertEqual(start_code, 0)
                self.assertEqual(
                    start_payload["mission"]["escalation_policy"]["destination"],
                    "@fluxio_default",
                )

    def test_cli_acceptance_runtime_stack_action_installs_missing_runtimes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir) / "vibe-coding-platform"
            root.mkdir(parents=True)
            bootstrap_project(root)
            (root / "pyproject.toml").write_text("[project]\nname='fluxio-demo'\n", encoding="utf-8")
            (root / "package.json").write_text('{"name":"fluxio-demo"}\n', encoding="utf-8")
            self._set_marker(root, "uv")
            self._clear_marker(root, "openclaw")
            self._clear_marker(root, "hermes")

            with self._patch_acceptance_environment(root):
                save_code, save_payload = self._run_json_command(
                    cmd_workspace_save,
                    root=str(root),
                    name="Fluxio Workspace",
                    path=str(root),
                    default_runtime="openclaw",
                    user_profile="experimental",
                    workspace_id=None,
                )
                self.assertEqual(save_code, 0)
                workspace_id = save_payload["workspace"]["workspace_id"]

                control_code, control_payload = self._run_json_command(
                    cmd_control_room,
                    root=str(root),
                )
                self.assertEqual(control_code, 0)
                action_ids = {
                    item["actionId"]
                    for item in control_payload["onboarding"]["setupHealth"]["repairActions"]
                }
                self.assertIn("install_runtime_stack", action_ids)

                install_code, install_payload = self._run_json_command(
                    cmd_workspace_action,
                    root=str(root),
                    surface="setup",
                    action_id="install_runtime_stack",
                    workspace_id=workspace_id,
                    approved=False,
                )
                self.assertEqual(install_code, 0)
                dependency_stages = install_payload["record"]["result"]["payload"]["dependencyStages"]
                self.assertEqual(dependency_stages["openclaw"], "healthy")
                self.assertEqual(dependency_stages["hermes"], "healthy")
                auto_verify = install_payload["record"]["result"]["payload"]["autoVerify"]
                self.assertFalse(auto_verify["ok"])
                self.assertIn("First guided mission", auto_verify["missingDependencies"])

    def _write_connected_apps_config(self, root: pathlib.Path) -> None:
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

        oratio_root = root.parent / "OratioViva"
        (oratio_root / "backend").mkdir(parents=True)
        (oratio_root / "frontend").mkdir(parents=True)
        (oratio_root / "backend" / "dia2_worker.py").write_text("print('ok')\n", encoding="utf-8")
        (oratio_root / "backend" / "qwen_tts_worker.py").write_text("print('ok')\n", encoding="utf-8")
        (oratio_root / "frontend" / "package.json").write_text(
            json.dumps({"name": "oratio-viva-ui", "version": "0.1.0"}),
            encoding="utf-8",
        )

    def _marker(self, root: pathlib.Path, dependency_id: str) -> pathlib.Path:
        return root / f".fake_{dependency_id}_installed"

    def _set_marker(self, root: pathlib.Path, dependency_id: str) -> None:
        self._marker(root, dependency_id).write_text("installed\n", encoding="utf-8")

    def _clear_marker(self, root: pathlib.Path, dependency_id: str) -> None:
        marker = self._marker(root, dependency_id)
        if marker.exists():
            marker.unlink()

    def _command_version_factory(self, root: pathlib.Path):
        def _command_version(command: str, args: list[str] | None = None) -> dict:
            installed = {
                "node": True,
                "python": True,
                "uv": self._marker(root, "uv").exists(),
                "openclaw": self._marker(root, "openclaw").exists(),
                "hermes": self._marker(root, "hermes").exists(),
                "cargo": True,
                "rustc": True,
            }.get(command, False)
            return {
                "installed": installed,
                "version": "1.0.0" if installed else None,
                "details": "" if installed else f"{command} is missing",
            }

        return _command_version

    def _runtime_adapter_map_factory(self, root: pathlib.Path):
        owner = self

        class _FakeRuntimeAdapter:
            def __init__(self, runtime_id: str, label: str) -> None:
                self.runtime_id = runtime_id
                self.label = label

            def install(self) -> dict[str, str]:
                return {
                    "command": f"install-{self.runtime_id}",
                    "follow_up": f"{self.runtime_id} setup",
                }

            def update(self, _workspace_root: pathlib.Path) -> dict[str, str]:
                return {
                    "command": f"update-{self.runtime_id}",
                    "follow_up": f"{self.runtime_id} update",
                }

            def doctor(self, workspace_root: pathlib.Path) -> RuntimeInstallStatus:
                detected = self.runtime_id == "openclaw"
                if self.runtime_id in {"openclaw", "hermes"}:
                    detected = owner._marker(root, self.runtime_id).exists()
                return RuntimeInstallStatus(
                    runtime_id=self.runtime_id,
                    label=self.label,
                    detected=detected,
                    command=self.runtime_id if detected else None,
                    version="1.0.0" if detected else None,
                    install_hint=f"Install {self.label}",
                    doctor_summary=(
                        f"{self.label} is ready for mission routing."
                        if detected
                        else f"Install {self.label} before mission routing."
                    ),
                    issues=[] if detected else [f"{self.label} is missing."],
                    capabilities=[
                        RuntimeCapability(
                            key="delegated_approval",
                            label="Delegated approval",
                            available=True,
                        )
                    ],
                )

        return {
            "openclaw": _FakeRuntimeAdapter("openclaw", "OpenClaw"),
            "hermes": _FakeRuntimeAdapter("hermes", "Hermes"),
        }

    def _fake_runtime_statuses(self, root: pathlib.Path) -> list[RuntimeInstallStatus]:
        adapters = self._runtime_adapter_map_factory(root)
        return [adapters["openclaw"].doctor(root), adapters["hermes"].doctor(root)]

    def _fake_shell_action(
        self,
        root: pathlib.Path,
        *,
        command: str,
        cwd: pathlib.Path,
        platform: str,
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        if command == "install-uv" or "astral-sh.uv" in command:
            self._set_marker(root, "uv")
        elif command == "install-hermes" or "hermes" in command:
            self._set_marker(root, "hermes")
        elif command == "install-openclaw" or "openclaw" in command:
            self._set_marker(root, "openclaw")
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=f"executed {command}",
            stderr="",
        )

    def _delegated_session_payload(
        self,
        root: pathlib.Path,
        *,
        status: str = "waiting_for_approval",
        approval_status: str = "pending",
        pid: int = 0,
        supervisor_pid: int = 0,
        event_kind: str = "approval.request",
        event_message: str = "Approve delegated Hermes lane?",
        detail: str | None = None,
    ) -> dict:
        sessions_dir = root / ".agent_control" / "runtime_sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        delegated_id = "delegated_hermes_lane"
        session_path = sessions_dir / f"{delegated_id}.json"
        log_path = sessions_dir / f"{delegated_id}.log"
        events_path = sessions_dir / f"{delegated_id}.events.jsonl"
        decision_path = sessions_dir / f"{delegated_id}.approval.json"
        log_path.write_text("delegated lane waiting\n", encoding="utf-8")
        events_path.write_text(
            json.dumps(
                {
                    "event_id": "evt_wait",
                    "delegated_id": delegated_id,
                    "runtime_id": "hermes",
                    "kind": event_kind,
                    "message": event_message,
                    "status": status,
                    "created_at": "2026-04-07T10:00:00+00:00",
                    "data": {"surface": "builder"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        payload = {
            "delegated_id": delegated_id,
            "runtime_id": "hermes",
            "launch_command": "hermes --mission delegated",
            "status": status,
            "detail": detail or event_message,
            "created_at": "2026-04-07T10:00:00+00:00",
            "updated_at": "2026-04-07T10:00:00+00:00",
            "last_event": event_message,
            "session_path": str(session_path),
            "workspace_root": str(root),
            "execution_root": str(root),
            "log_path": str(log_path),
            "events_path": str(events_path),
            "decision_path": str(decision_path),
            "source_step_id": "step_delegate",
            "pid": pid,
            "supervisor_pid": supervisor_pid,
            "exit_code": None,
            "acknowledged": False,
            "last_event_kind": event_kind,
            "latest_events": [
                {
                    "event_id": "evt_wait",
                    "delegated_id": delegated_id,
                    "runtime_id": "hermes",
                    "kind": event_kind,
                    "message": event_message,
                    "status": status,
                    "created_at": "2026-04-07T10:00:00+00:00",
                    "data": {"surface": "builder"},
                }
            ],
            "pending_approval": {
                "request_id": "apr_hermes_lane",
                "delegated_id": delegated_id,
                "runtime_id": "hermes",
                "prompt": "Approve delegated Hermes lane?",
                "risk_level": "high",
                "status": approval_status,
                "created_at": "2026-04-07T10:00:00+00:00",
                "resolved_at": None,
                "resolved_by": "",
                "metadata": {"surface": "builder"},
            }
            if approval_status
            else {},
            "approval_history": [],
            "event_cursor": 1,
        }
        session_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def _engine_result_factory(self, root: pathlib.Path):
        def _invoke_engine(**kwargs) -> dict:
            runtime_id = kwargs["runtime_id"]
            mission_id = kwargs["mission_id"]
            resume_from = kwargs.get("resume_from")
            objective = str(kwargs.get("objective", "")).lower()
            session_dir = root / ".agent_runs" / (resume_from or f"{mission_id}_{runtime_id}")
            session_dir.mkdir(parents=True, exist_ok=True)

            if runtime_id == "openclaw":
                return {
                    "status": "ok",
                    "harness_id": "fluxio_hybrid",
                    "session_path": str(session_dir),
                    "autopilot_status": "completed",
                    "autopilot_pause_reason": None,
                    "effective_verify_commands": ["python -m pytest tests -q"],
                    "execution_scope": {"strategy": "isolated", "status": "ready"},
                    "execution_policy": {"profile_name": "experimental", "explanation_depth": "medium"},
                    "plan_revisions": [
                        {
                            "revision_id": "rev_openclaw",
                            "trigger": "guided_first_mission",
                            "summary": "OpenClaw mission completed from the control room.",
                            "active_step_id": "step_verify_openclaw",
                        }
                    ],
                    "changed_files": ["README.md"],
                    "action_history": [
                        {
                            "proposal": {
                                "title": "Inspect workspace",
                                "mutability_class": "read",
                                "sourceKind": "local",
                            },
                            "result": {"ok": True, "sourceKind": "local"},
                            "gate": {"required": False, "status": "completed"},
                        }
                    ],
                    "delegated_runtime_sessions": [],
                    "verification_failures": [],
                    "remaining_steps": [],
                }

            delegated_path = root / ".agent_control" / "runtime_sessions" / "delegated_hermes_lane.json"
            if not resume_from:
                if "delegated runtime activity" in objective or "activity truthful across restart" in objective:
                    delegated = self._delegated_session_payload(
                        root,
                        status="running",
                        approval_status="",
                        pid=43210,
                        supervisor_pid=54321,
                        event_kind="runtime.phase",
                        event_message="Hermes delegated lane is still running.",
                        detail="Delegated runtime is still active.",
                    )
                    return {
                        "status": "ok",
                        "harness_id": "fluxio_hybrid",
                        "session_path": str(session_dir),
                        "autopilot_status": "paused",
                        "autopilot_pause_reason": "delegated_runtime_running",
                        "effective_verify_commands": ["python -m pytest tests -q"],
                        "execution_scope": {"strategy": "isolated", "status": "ready"},
                        "execution_policy": {"profile_name": "experimental", "explanation_depth": "medium"},
                        "plan_revisions": [
                            {
                                "revision_id": "rev_hermes_running",
                                "trigger": "delegated_launch",
                                "summary": "Delegated Hermes lane launched and is still active.",
                                "active_step_id": "step_delegate_hermes",
                            }
                        ],
                        "changed_files": [],
                        "action_history": [
                            {
                                "proposal": {
                                    "title": "Delegated Hermes lane",
                                    "mutability_class": "write",
                                    "kind": "delegated_runtime",
                                    "sourceKind": "delegated",
                                },
                                "result": {"ok": True, "sourceKind": "delegated"},
                                "gate": {"required": False, "status": "completed"},
                            }
                        ],
                        "delegated_runtime_sessions": [delegated],
                        "verification_failures": [],
                        "remaining_steps": ["Wait for delegated runtime lane"],
                    }
                delegated = self._delegated_session_payload(root)
                return {
                    "status": "ok",
                    "harness_id": "fluxio_hybrid",
                    "session_path": str(session_dir),
                    "autopilot_status": "paused",
                    "autopilot_pause_reason": "approval_required",
                    "effective_verify_commands": ["python -m pytest tests -q"],
                    "execution_scope": {"strategy": "isolated", "status": "ready"},
                    "execution_policy": {"profile_name": "experimental", "explanation_depth": "medium"},
                    "plan_revisions": [
                        {
                            "revision_id": "rev_hermes_waiting",
                            "trigger": "delegated_launch",
                            "summary": "Delegated Hermes lane launched and is waiting for approval.",
                            "active_step_id": "step_delegate_hermes",
                        }
                    ],
                    "changed_files": [],
                    "action_history": [
                        {
                            "proposal": {
                                "title": "Delegated Hermes lane",
                                "mutability_class": "write",
                                "kind": "delegated_runtime",
                                "sourceKind": "delegated",
                            },
                            "result": {"ok": True, "sourceKind": "delegated"},
                            "gate": {"required": False, "status": "completed"},
                        }
                    ],
                    "delegated_runtime_sessions": [delegated],
                    "verification_failures": [],
                    "remaining_steps": ["Await approval"],
                }

            delegated = json.loads(delegated_path.read_text(encoding="utf-8"))
            latest_decision = next(
                (
                    item.get("status")
                    for item in reversed(delegated.get("approval_history", []))
                    if item.get("status") in {"approved", "rejected"}
                ),
                "",
            )
            if latest_decision == "rejected":
                delegated["status"] = "failed"
                delegated["detail"] = "Approval rejected. Replan required."
                delegated["pending_approval"] = {}
                delegated_path.write_text(json.dumps(delegated, indent=2), encoding="utf-8")
                return {
                    "status": "ok",
                    "harness_id": "fluxio_hybrid",
                    "session_path": str(session_dir),
                    "autopilot_status": "paused",
                    "autopilot_pause_reason": "verification_failed",
                    "effective_verify_commands": ["python -m pytest tests -q"],
                    "execution_scope": {"strategy": "isolated", "status": "ready"},
                    "execution_policy": {"profile_name": "experimental", "explanation_depth": "medium"},
                    "plan_revisions": [
                        {
                            "revision_id": "rev_hermes_replan",
                            "trigger": "approval_rejected",
                            "summary": "Approval was rejected. Replan context recorded for the operator.",
                            "active_step_id": "step_replan_hermes",
                        }
                    ],
                    "changed_files": [],
                    "action_history": [
                        {
                            "proposal": {
                                "title": "Delegated Hermes lane",
                                "mutability_class": "write",
                                "kind": "delegated_runtime",
                                "sourceKind": "delegated",
                            },
                            "result": {"ok": False, "sourceKind": "delegated"},
                            "gate": {"required": False, "status": "completed"},
                        }
                    ],
                    "delegated_runtime_sessions": [delegated],
                    "verification_failures": ["Approval rejected; replan required."],
                    "remaining_steps": ["Review replan context"],
                }

            delegated["status"] = "completed"
            delegated["detail"] = "Delegated lane completed after approval."
            delegated["pending_approval"] = {}
            delegated_path.write_text(json.dumps(delegated, indent=2), encoding="utf-8")
            return {
                "status": "ok",
                "harness_id": "fluxio_hybrid",
                "session_path": str(session_dir),
                "autopilot_status": "completed",
                "autopilot_pause_reason": None,
                "effective_verify_commands": ["python -m pytest tests -q"],
                "execution_scope": {"strategy": "isolated", "status": "ready"},
                "execution_policy": {"profile_name": "experimental", "explanation_depth": "medium"},
                "plan_revisions": [
                    {
                        "revision_id": "rev_hermes_resumed",
                        "trigger": "approval_resumed",
                        "summary": "Delegated lane resumed after approval and finished verification.",
                        "active_step_id": "step_verify_hermes",
                    }
                ],
                "changed_files": ["docs/FLUXIO_1_0_RELEASE.md"],
                "action_history": [
                    {
                        "proposal": {
                            "title": "Delegated Hermes lane",
                            "mutability_class": "write",
                            "kind": "delegated_runtime",
                            "sourceKind": "delegated",
                        },
                        "result": {"ok": True, "sourceKind": "delegated"},
                        "gate": {"required": False, "status": "completed"},
                    }
                ],
                "delegated_runtime_sessions": [delegated],
                "verification_failures": [],
                "remaining_steps": [],
            }

        return _invoke_engine

    def _patch_acceptance_environment(self, root: pathlib.Path) -> ExitStack:
        stack = ExitStack()
        command_version = self._command_version_factory(root)
        adapters = self._runtime_adapter_map_factory(root)
        stack.enter_context(mock.patch("grant_agent.onboarding._command_version", side_effect=command_version))
        stack.enter_context(
            mock.patch(
                "grant_agent.onboarding.detect_wsl_status",
                return_value={
                    "required": True,
                    "installed": True,
                    "default_version": 2,
                    "details": "WSL2 is installed.",
                },
            )
        )
        stack.enter_context(
            mock.patch(
                "grant_agent.onboarding.latest_openclaw_release",
                return_value={
                    "version": "1.0.0",
                    "sourceUrl": "https://example.test/openclaw",
                },
            )
        )
        stack.enter_context(
            mock.patch(
                "grant_agent.onboarding.latest_hermes_release",
                return_value={
                    "version": "1.0.0",
                    "sourceUrl": "https://example.test/hermes",
                },
            )
        )
        stack.enter_context(mock.patch("grant_agent.onboarding._phone_destination_count", return_value=1))
        stack.enter_context(mock.patch("grant_agent.onboarding.runtime_adapter_map", return_value=adapters))
        stack.enter_context(mock.patch("grant_agent.cli.runtime_adapter_map", return_value=adapters))
        stack.enter_context(
            mock.patch(
                "grant_agent.mission_control.detect_runtime_statuses",
                side_effect=lambda _root: self._fake_runtime_statuses(root),
            )
        )
        stack.enter_context(
            mock.patch(
                "grant_agent.workspace_actions._run_shell_action",
                side_effect=lambda **kwargs: self._fake_shell_action(root, **kwargs),
            )
        )
        stack.enter_context(
            mock.patch(
                "grant_agent.cli.detect_default_verification_commands",
                return_value=["python -m pytest tests -q"],
            )
        )
        stack.enter_context(
            mock.patch(
                "grant_agent.cli._invoke_engine",
                side_effect=self._engine_result_factory(root),
            )
        )
        stack.enter_context(
            mock.patch(
                "grant_agent.runtime_supervisor._pid_alive",
                side_effect=lambda pid: pid in {43210, 54321},
            )
        )
        return stack

    def test_cli_acceptance_repairs_setup_runs_openclaw_then_hermes_and_restores_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir) / "vibe-coding-platform"
            root.mkdir(parents=True)
            bootstrap_project(root)
            (root / "pyproject.toml").write_text("[project]\nname='fluxio-demo'\n", encoding="utf-8")
            (root / "package.json").write_text('{"name":"fluxio-demo"}\n', encoding="utf-8")
            (root / "src-tauri").mkdir(exist_ok=True)
            self._write_connected_apps_config(root)
            self._set_marker(root, "openclaw")
            self._clear_marker(root, "uv")
            self._clear_marker(root, "hermes")

            with self._patch_acceptance_environment(root):
                save_code, save_payload = self._run_json_command(
                    cmd_workspace_save,
                    root=str(root),
                    name="Fluxio Workspace",
                    path=str(root),
                    default_runtime="openclaw",
                    user_profile="experimental",
                    workspace_id=None,
                )
                self.assertEqual(save_code, 0)
                workspace_id = save_payload["workspace"]["workspace_id"]

                control_code, control_payload = self._run_json_command(
                    cmd_control_room,
                    root=str(root),
                )
                self.assertEqual(control_code, 0)
                self.assertEqual(
                    control_payload["onboarding"]["tutorial"]["currentStepId"],
                    "detect_environment",
                )
                setup_dependencies = {
                    item["dependencyId"]: item for item in control_payload["onboarding"]["setupHealth"]["dependencies"]
                }
                self.assertEqual(setup_dependencies["uv"]["stage"], "install_available")
                self.assertEqual(setup_dependencies["hermes"]["stage"], "install_available")
                initial_workflows = {
                    item["workflowId"]: item
                    for item in control_payload["workflowStudio"]["recipes"]
                }
                self.assertEqual(initial_workflows["setup_repair"]["status"], "blocked")
                self.assertIn("uv", initial_workflows["setup_repair"]["serviceIds"])
                self.assertIn("hermes", initial_workflows["setup_repair"]["serviceIds"])

                uv_code, uv_payload = self._run_json_command(
                    cmd_workspace_action,
                    root=str(root),
                    surface="setup",
                    action_id="install_uv",
                    workspace_id=workspace_id,
                    approved=False,
                )
                self.assertEqual(uv_code, 0)
                self.assertEqual(
                    uv_payload["record"]["result"]["payload"]["dependencyStage"],
                    "verify_pending",
                )

                verify_uv_code, verify_uv_payload = self._run_json_command(
                    cmd_workspace_action,
                    root=str(root),
                    surface="setup",
                    action_id="verify_setup_health",
                    workspace_id=workspace_id,
                    approved=False,
                )
                self.assertEqual(verify_uv_code, 2)
                verify_uv_dependencies = {
                    item["dependencyId"]: item
                    for item in verify_uv_payload["record"]["result"]["payload"]["setupHealth"]["dependencies"]
                }
                self.assertEqual(verify_uv_dependencies["uv"]["stage"], "healthy")
                self.assertEqual(verify_uv_dependencies["hermes"]["stage"], "install_available")

                hermes_code, hermes_payload = self._run_json_command(
                    cmd_workspace_action,
                    root=str(root),
                    surface="setup",
                    action_id="install_hermes",
                    workspace_id=workspace_id,
                    approved=False,
                )
                self.assertEqual(hermes_code, 0)
                self.assertEqual(
                    hermes_payload["record"]["result"]["payload"]["dependencyStage"],
                    "verify_pending",
                )

                verify_ready_code, verify_ready_payload = self._run_json_command(
                    cmd_workspace_action,
                    root=str(root),
                    surface="setup",
                    action_id="verify_setup_health",
                    workspace_id=workspace_id,
                    approved=False,
                )
                self.assertEqual(verify_ready_code, 2)
                ready_setup = verify_ready_payload["record"]["result"]["payload"]["setupHealth"]
                ready_dependencies = {
                    item["dependencyId"]: item for item in ready_setup["dependencies"]
                }
                self.assertTrue(ready_setup["environmentReady"])
                self.assertFalse(ready_setup["installerReady"])
                self.assertEqual(ready_dependencies["hermes"]["stage"], "healthy")
                self.assertEqual(
                    ready_setup["serviceManagementSummary"]["healthyCount"],
                    ready_setup["serviceManagementSummary"]["totalItems"],
                )

                openclaw_code, openclaw_payload = self._run_json_command(
                    cmd_mission_start,
                    root=str(root),
                    workspace_id=workspace_id,
                    runtime="openclaw",
                    objective="Run the guided first mission through OpenClaw.",
                    success_check=["Mission completes"],
                    mode="autopilot",
                    budget_hours=6,
                    profile="experimental",
                    escalation_destination="@fluxio",
                    run_until="pause_on_failure",
                )
                self.assertEqual(openclaw_code, 0)
                self.assertEqual(openclaw_payload["mission"]["state"]["status"], "completed")
                self.assertEqual(
                    openclaw_payload["mission"]["run_budget"]["run_until_behavior"],
                    "pause_on_failure",
                )

                after_first_code, after_first_payload = self._run_json_command(
                    cmd_control_room,
                    root=str(root),
                )
                self.assertEqual(after_first_code, 0)
                self.assertTrue(after_first_payload["onboarding"]["setupHealth"]["firstMissionLaunched"])
                self.assertTrue(after_first_payload["onboarding"]["setupHealth"]["installerReady"])
                self.assertEqual(
                    after_first_payload["onboarding"]["tutorial"]["currentStepId"],
                    "",
                )
                self.assertTrue(after_first_payload["onboarding"]["tutorial"]["isComplete"])
                workflow_map = {
                    item["workflowId"]: item
                    for item in after_first_payload["workflowStudio"]["recipes"]
                }
                self.assertEqual(workflow_map["setup_repair"]["status"], "ready")
                self.assertEqual(workflow_map["agent_long_run"]["status"], "ready")
                self.assertEqual(
                    workflow_map["agent_long_run"]["verificationDefaults"],
                    [
                        "python -m pytest tests -q",
                        "npm run frontend:build",
                        "npm run tauri build -- --debug",
                    ],
                )
                workspace_services = {
                    item["serviceId"]: item
                    for item in after_first_payload["workspaces"][0]["serviceManagement"]
                }
                self.assertEqual(workspace_services["hermes"]["currentHealthStatus"], "healthy")
                self.assertEqual(workspace_services["hermes"]["lastVerificationResult"], "passed")

                hermes_start_code, hermes_start_payload = self._run_json_command(
                    cmd_mission_start,
                    root=str(root),
                    workspace_id=workspace_id,
                    runtime="hermes",
                    objective="Run the Hermes delegated mission from Fluxio.",
                    success_check=["Mission completes after approval"],
                    mode="autopilot",
                    budget_hours=12,
                    profile="experimental",
                    escalation_destination="@fluxio",
                    run_until="continue_until_blocked",
                )
                self.assertEqual(hermes_start_code, 0)
                hermes_mission = hermes_start_payload["mission"]
                self.assertEqual(hermes_mission["state"]["status"], "needs_approval")
                self.assertEqual(hermes_mission["state"]["continuity_state"], "approval_waiting")
                self.assertEqual(
                    hermes_mission["run_budget"]["run_until_behavior"],
                    "continue_until_blocked",
                )
                self.assertEqual(
                    hermes_mission["action_history"][0]["proposal"]["sourceKind"],
                    "delegated",
                )

                restart_code, restart_payload = self._run_json_command(
                    cmd_control_room,
                    root=str(root),
                )
                self.assertEqual(restart_code, 0)
                restart_sessions = {
                    item["app_id"]: item for item in restart_payload["bridgeLab"]["connectedSessions"]
                }
                self.assertEqual(restart_sessions["oratio-viva"]["status"], "connected")
                self.assertNotIn("mind-tower", restart_sessions)
                self.assertEqual(restart_sessions["solantir-terminal"]["status"], "follow_on_manifest")
                latest_restart_mission = restart_payload["missions"][-1]
                self.assertEqual(
                    latest_restart_mission["missionLoop"]["continuityState"],
                    "approval_waiting",
                )
                self.assertEqual(
                    restart_payload["ui"]["availableModes"],
                    ["agent", "builder"],
                )

                approve_code, approve_payload = self._run_json_command(
                    cmd_mission_action,
                    root=str(root),
                    mission_id=hermes_mission["mission_id"],
                    action="approve-latest",
                )
                self.assertEqual(approve_code, 0)
                self.assertEqual(approve_payload["mission"]["state"]["status"], "queued")

                resume_code, resume_payload = self._run_json_command(
                    cmd_mission_action,
                    root=str(root),
                    mission_id=hermes_mission["mission_id"],
                    action="resume",
                )
                self.assertEqual(resume_code, 0)
                resumed_mission = resume_payload["mission"]
                self.assertEqual(resumed_mission["state"]["status"], "completed")
                self.assertEqual(resumed_mission["state"]["continuity_state"], "terminal")
                self.assertTrue(resumed_mission["state"]["approval_history"])
                self.assertEqual(
                    resumed_mission["state"]["approval_history"][-1]["status"],
                    "approved",
                )
                self.assertEqual(
                    resumed_mission["state"]["last_replan_trigger"],
                    "approval_resumed",
                )

                final_code, final_payload = self._run_json_command(
                    cmd_control_room,
                    root=str(root),
                )
                self.assertEqual(final_code, 0)
                final_mission = final_payload["missions"][-1]
                self.assertEqual(final_mission["state"]["status"], "completed")
                self.assertEqual(
                    final_mission["missionLoop"]["timeBudget"]["runUntilBehavior"],
                    "continue_until_blocked",
                )
                self.assertEqual(
                    final_mission["state"]["approval_history"][-1]["status"],
                    "approved",
                )
                self.assertTrue(final_mission["delegated_runtime_sessions"][0]["approval_history"])

    def test_cli_acceptance_records_replan_after_rejected_delegated_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir) / "vibe-coding-platform"
            root.mkdir(parents=True)
            bootstrap_project(root)
            (root / "pyproject.toml").write_text("[project]\nname='fluxio-demo'\n", encoding="utf-8")
            (root / "package.json").write_text('{"name":"fluxio-demo"}\n', encoding="utf-8")
            (root / "src-tauri").mkdir(exist_ok=True)
            self._write_connected_apps_config(root)
            self._set_marker(root, "openclaw")
            self._set_marker(root, "uv")
            self._set_marker(root, "hermes")

            with self._patch_acceptance_environment(root):
                save_code, save_payload = self._run_json_command(
                    cmd_workspace_save,
                    root=str(root),
                    name="Fluxio Workspace",
                    path=str(root),
                    default_runtime="hermes",
                    user_profile="experimental",
                    workspace_id=None,
                )
                self.assertEqual(save_code, 0)
                workspace_id = save_payload["workspace"]["workspace_id"]

                start_code, start_payload = self._run_json_command(
                    cmd_mission_start,
                    root=str(root),
                    workspace_id=workspace_id,
                    runtime="hermes",
                    objective="Run the Hermes delegated mission from Fluxio.",
                    success_check=["Mission records rejection replan"],
                    mode="autopilot",
                    budget_hours=12,
                    profile="experimental",
                    escalation_destination="@fluxio",
                    run_until="continue_until_blocked",
                )
                self.assertEqual(start_code, 0)
                mission_id = start_payload["mission"]["mission_id"]
                self.assertEqual(start_payload["mission"]["state"]["status"], "needs_approval")

                reject_code, reject_payload = self._run_json_command(
                    cmd_mission_action,
                    root=str(root),
                    mission_id=mission_id,
                    action="reject-latest",
                )
                self.assertEqual(reject_code, 0)
                self.assertEqual(reject_payload["mission"]["state"]["status"], "blocked")

                resume_code, resume_payload = self._run_json_command(
                    cmd_mission_action,
                    root=str(root),
                    mission_id=mission_id,
                    action="resume",
                )
                self.assertEqual(resume_code, 0)
                self.assertEqual(resume_payload["mission"]["state"]["status"], "verification_failed")
                self.assertEqual(
                    resume_payload["mission"]["state"]["last_replan_trigger"],
                    "approval_rejected",
                )
                self.assertIn(
                    "Approval rejected",
                    resume_payload["mission"]["state"]["last_verification_summary"],
                )
                self.assertEqual(
                    resume_payload["mission"]["state"]["approval_history"][-1]["status"],
                    "rejected",
                )

                control_code, control_payload = self._run_json_command(
                    cmd_control_room,
                    root=str(root),
                )
                self.assertEqual(control_code, 0)
                latest_mission = control_payload["missions"][-1]
                self.assertEqual(latest_mission["state"]["status"], "verification_failed")
                self.assertEqual(
                    latest_mission["state"]["last_replan_trigger"],
                    "approval_rejected",
                )
                self.assertEqual(
                    latest_mission["state"]["approval_history"][-1]["status"],
                    "rejected",
                )

    def test_cli_acceptance_preserves_delegated_runtime_activity_and_budget_truth_across_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir) / "vibe-coding-platform"
            root.mkdir(parents=True)
            bootstrap_project(root)
            (root / "pyproject.toml").write_text("[project]\nname='fluxio-demo'\n", encoding="utf-8")
            (root / "package.json").write_text('{"name":"fluxio-demo"}\n', encoding="utf-8")
            (root / "src-tauri").mkdir(exist_ok=True)
            self._write_connected_apps_config(root)
            self._set_marker(root, "openclaw")
            self._set_marker(root, "uv")
            self._set_marker(root, "hermes")

            with self._patch_acceptance_environment(root):
                save_code, save_payload = self._run_json_command(
                    cmd_workspace_save,
                    root=str(root),
                    name="Fluxio Workspace",
                    path=str(root),
                    default_runtime="hermes",
                    user_profile="experimental",
                    workspace_id=None,
                )
                self.assertEqual(save_code, 0)
                workspace_id = save_payload["workspace"]["workspace_id"]

                start_code, start_payload = self._run_json_command(
                    cmd_mission_start,
                    root=str(root),
                    workspace_id=workspace_id,
                    runtime="hermes",
                    objective="Keep delegated runtime activity truthful across restart.",
                    success_check=["Mission stays restart-safe while delegated work is still running"],
                    mode="autopilot",
                    budget_hours=12,
                    profile="experimental",
                    escalation_destination="@fluxio",
                    run_until="continue_until_blocked",
                )
                self.assertEqual(start_code, 0)
                mission = start_payload["mission"]
                self.assertEqual(mission["state"]["status"], "running")
                self.assertEqual(mission["state"]["continuity_state"], "delegated_active")
                self.assertEqual(mission["state"]["time_budget_status"], "delegated_active")
                self.assertEqual(
                    mission["state"]["last_budget_pause_reason"],
                    "Delegated runtime lane is still active and restart-safe.",
                )
                self.assertEqual(
                    mission["state"]["current_runtime_lane"],
                    "hermes delegated lane running",
                )

                restart_code, restart_payload = self._run_json_command(
                    cmd_control_room,
                    root=str(root),
                )
                self.assertEqual(restart_code, 0)
                latest_mission = restart_payload["missions"][-1]
                self.assertEqual(latest_mission["missionLoop"]["continuityState"], "delegated_active")
                self.assertEqual(
                    latest_mission["missionLoop"]["timeBudget"]["status"],
                    "delegated_active",
                )
                self.assertEqual(
                    latest_mission["missionLoop"]["pauseReason"],
                    "Delegated runtime lane is still active and restart-safe.",
                )
                self.assertEqual(
                    latest_mission["missionLoop"]["timeBudget"]["lastPauseReason"],
                    "Delegated runtime lane is still active and restart-safe.",
                )
                self.assertEqual(
                    latest_mission["missionLoop"]["currentRuntimeLane"],
                    "hermes delegated lane running",
                )
                self.assertEqual(
                    restart_payload["ui"]["availableModes"],
                    ["agent", "builder"],
                )


if __name__ == "__main__":
    unittest.main()
