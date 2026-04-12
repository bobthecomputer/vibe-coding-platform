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
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.cli import _invoke_engine, bootstrap_project, cmd_workspace_save


def _init_git_repo(root: pathlib.Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "fluxio@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Fluxio"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)


class CliPreferenceTests(unittest.TestCase):
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
            self.assertEqual(planner["model"], "gpt-5.4")
            self.assertEqual(executor["model"], "gpt-5.4")
            self.assertNotEqual(result["execution_scope"]["execution_root"], str(root))
            self.assertEqual(result["execution_scope"]["execution_target"], "worktree")
            self.assertEqual(
                result["execution_policy"]["profile_name"],
                "hands_free_builder",
            )


if __name__ == "__main__":
    unittest.main()
