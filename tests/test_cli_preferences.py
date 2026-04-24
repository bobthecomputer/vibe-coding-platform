from __future__ import annotations

import argparse
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.cli import (
    _invoke_engine,
    bootstrap_project,
    cmd_mission_action,
    cmd_mission_start,
    cmd_workspace_save,
)
from grant_agent.checkpoints import CheckpointStore
from grant_agent.mission_control import ControlRoomStore
from grant_agent.models import RunState, RuntimeInstallStatus


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

    def test_invoke_engine_honors_legacy_harness_preference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            bootstrap_project(root)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            _init_git_repo(root)

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
            self.assertEqual(result["harness_id"], "legacy_autonomous_engine")
            self.assertEqual(result["effective_harness"], "legacy_autonomous_engine")
            self.assertEqual(
                result["effective_execution_target_preference"],
                "isolated_worktree",
            )
            planner = next(item for item in result["route_configs"] if item["role"] == "planner")
            executor = next(item for item in result["route_configs"] if item["role"] == "executor")
            self.assertEqual(planner["model"], "gpt-5.5")
            self.assertEqual(executor["model"], "gpt-5.5")
            self.assertNotEqual(result["execution_scope"]["execution_root"], str(root))
            self.assertEqual(result["execution_scope"]["execution_target"], "worktree")
            self.assertEqual(
                result["execution_policy"]["profile_name"],
                "hands_free_builder",
            )

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


if __name__ == "__main__":
    unittest.main()

