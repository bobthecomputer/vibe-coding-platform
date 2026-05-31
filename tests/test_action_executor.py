from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.action_executor import (
    build_action_proposal,
    build_execution_policy,
    cleanup_execution_scope,
    delegated_cycle_phase_for_step,
    execute_action,
    prepare_execution_scope,
)
from grant_agent.models import ActionProposal, PlannedStep


def _init_git_repo(root: pathlib.Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "fluxio@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Fluxio"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)


class ActionExecutorTests(unittest.TestCase):
    def test_prepare_execution_scope_direct_marks_local_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")

            scope = prepare_execution_scope(
                root,
                "mission_direct_scope_test",
                requested_scope="direct",
                profile_name="builder",
            )

            self.assertFalse(scope.isolated)
            self.assertEqual(scope.strategy, "direct")
            self.assertEqual(scope.execution_target, "workspace")
            self.assertEqual(scope.storage_mode, "local_disk")
            self.assertEqual(scope.host_locality, "local_machine")

    def test_prepare_execution_scope_creates_isolated_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            _init_git_repo(root)

            scope = prepare_execution_scope(root, "mission_scope_test", profile_name="builder")

            self.assertTrue(scope.isolated)
            self.assertEqual(scope.strategy, "git_worktree")
            self.assertTrue(pathlib.Path(scope.execution_root).exists())
            self.assertNotEqual(pathlib.Path(scope.execution_root), root)
            self.assertEqual(scope.execution_target, "worktree")
            self.assertEqual(scope.storage_mode, "local_disk")
            self.assertEqual(scope.host_locality, "local_machine")

    def test_cleanup_execution_scope_removes_isolated_worktree_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            _init_git_repo(root)

            scope = prepare_execution_scope(root, "mission_cleanup_test", profile_name="builder")
            worktree_path = pathlib.Path(scope.execution_root)

            self.assertTrue(scope.isolated)
            self.assertTrue(worktree_path.exists())

            cleanup = cleanup_execution_scope(scope)

            self.assertTrue(cleanup["cleaned"])
            self.assertFalse(worktree_path.exists())
            self.assertEqual(scope.strategy, "git_worktree")

    def test_file_patch_executes_under_hands_free_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            readme = root / "README.md"
            readme.write_text("# Demo\n", encoding="utf-8")
            policy = build_execution_policy("experimental")
            scope = prepare_execution_scope(root, "mission_patch_test", requested_scope="direct", profile_name="experimental")
            step = PlannedStep(step_id="step_patch", title="Implement smallest vertical slice")

            proposal = build_action_proposal(
                step=step,
                objective="Implement and update README.md with mission notes",
                workspace_root=root,
                verification_commands=["python -m unittest discover -s tests"],
                runtime_id="openclaw",
                execution_scope=scope,
                execution_policy=policy,
            )
            record = execute_action(
                proposal,
                root,
                execution_scope=scope,
                execution_policy=policy,
            )

            self.assertEqual(proposal.kind, "file_patch")
            self.assertFalse(proposal.requires_approval)
            self.assertTrue(record.result.ok)
            self.assertIn("Fluxio Mission Note", readme.read_text(encoding="utf-8"))

    def test_generated_write_without_explicit_path_uses_mission_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            readme = root / "README.md"
            readme.write_text("# Demo\n", encoding="utf-8")
            policy = build_execution_policy("builder")
            scope = prepare_execution_scope(
                root,
                "mission_artifact_target_test",
                requested_scope="direct",
                profile_name="builder",
            )
            step = PlannedStep(
                step_id="step_plan",
                title="Draft implementation plan with milestones",
            )

            proposal = build_action_proposal(
                step=step,
                objective="Improve one beginner-facing Fluxio workflow end to end.",
                workspace_root=root,
                verification_commands=[],
                runtime_id="hermes",
                execution_scope=scope,
                execution_policy=policy,
            )

            self.assertEqual(proposal.kind, "file_write")
            self.assertIn(".agent_control", proposal.target_path)
            self.assertIn("mission_artifacts", proposal.target_path)
            self.assertNotEqual(pathlib.Path(proposal.target_path), readme)
            self.assertFalse(proposal.requires_approval)

    def test_verify_words_in_objective_do_not_turn_non_verify_step_into_test_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            policy = build_execution_policy("builder")
            scope = prepare_execution_scope(
                root,
                "mission_objective_verify_text",
                requested_scope="direct",
                profile_name="builder",
            )
            step = PlannedStep(
                step_id="step_docs",
                title="Review referenced docs and extract constraints",
            )

            proposal = build_action_proposal(
                step=step,
                objective=(
                    "Implement product files first. After product files change, "
                    "run only focused verification."
                ),
                workspace_root=root,
                verification_commands=[],
                runtime_id="hermes",
                execution_scope=scope,
                execution_policy=policy,
            )

            self.assertNotEqual(proposal.kind, "test_run")

    def test_verify_words_in_objective_do_not_route_execute_step_to_verifier(self) -> None:
        step = PlannedStep(
            step_id="step_execute",
            title="Implement smallest vertical slice in product files",
            description="Patch the Live Review model and UI before focused verification.",
            kind="primary",
        )

        phase = delegated_cycle_phase_for_step(
            step,
            objective=(
                "EXECUTE FIRST, NO PREFLIGHT TESTS. After product files change, "
                "run only focused verification relevant to touched files."
            ),
            route_configs=[
                {"role": "planner"},
                {"role": "executor"},
                {"role": "verifier"},
            ],
        )

        self.assertEqual(phase, "execute")

    def test_execute_action_timeout_returns_failed_record_not_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            policy = build_execution_policy("builder")
            scope = prepare_execution_scope(
                root,
                "mission_timeout_test",
                requested_scope="direct",
                profile_name="builder",
            )
            proposal = ActionProposal(
                action_id="action_timeout",
                kind="test_run",
                title="Run verification",
                command="python -m unittest discover -s tests",
                target_path=str(root),
                mutability_class="execute",
                policy_decision="auto_run",
                requires_approval=False,
            )
            timeout_error = subprocess.TimeoutExpired(
                cmd=proposal.command,
                timeout=1,
                output="partial stdout",
                stderr="partial stderr",
            )
            with mock.patch(
                "grant_agent.action_executor.subprocess.run",
                side_effect=timeout_error,
            ):
                record = execute_action(
                    proposal,
                    root,
                    execution_scope=scope,
                    execution_policy=policy,
                    timeout_seconds=1,
                )

            self.assertFalse(record.result.ok)
            self.assertEqual(record.result.exit_code, 124)
            self.assertIn("timed out", record.result.error.lower())
            self.assertIn("timed out", record.result.stderr.lower())

    @mock.patch("grant_agent.runtime_supervisor.runtime_adapter_map")
    @mock.patch("grant_agent.action_executor.runtime_adapter_map")
    def test_runtime_delegate_returns_normalized_session(
        self,
        runtime_supervisor_map: mock.Mock,
        runtime_map: mock.Mock,
    ) -> None:
        class _FakeAdapter:
            runtime_id = "hermes"

            def detect(self, _: pathlib.Path):
                return type("Status", (), {"detected": True, "doctor_summary": "ready"})()

            def start_mission(self, mission, workspace):
                assert mission.route_configs[0].model == "gpt-5.4"
                return {
                    "launch_command": f'"{sys.executable}" -c "print(\'delegate lane ready\')"',
                    "workspace": workspace.root_path,
                }

            def stream_events(self, mission):
                return [{"kind": "runtime.stream", "missionId": mission.mission_id}]

            def resume_mission(self, mission, workspace):
                return self.start_mission(mission, workspace)

        adapter_map = {"hermes": _FakeAdapter()}
        runtime_map.return_value = adapter_map
        runtime_supervisor_map.return_value = adapter_map

        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            policy = build_execution_policy("builder")
            scope = prepare_execution_scope(root, "mission_delegate_test", requested_scope="direct", profile_name="builder")
            step = PlannedStep(step_id="step_delegate", title="Delegate execution to Hermes")
            proposal = build_action_proposal(
                step=step,
                objective="Delegate this mission to Hermes for a runtime lane check",
                workspace_root=root,
                verification_commands=[],
                runtime_id="hermes",
                execution_scope=scope,
                execution_policy=policy,
                route_configs=[
                    {
                        "role": "executor",
                        "provider": "openai",
                        "model": "gpt-5.4",
                        "effort": "high",
                    }
                ],
            )

            record = execute_action(
                proposal,
                root,
                execution_scope=scope,
                execution_policy=policy,
            )

            self.assertEqual(proposal.kind, "runtime_delegate")
            self.assertTrue(record.result.ok)
            self.assertIn("delegatedSession", record.result.payload)
            self.assertEqual(record.result.payload["delegatedSession"]["execution_target"], "workspace")
            self.assertEqual(record.result.payload["delegatedSnapshot"]["execution_target"], "workspace")
            self.assertEqual(
                proposal.delegation_metadata["route_configs"][0]["model"],
                "gpt-5.4",
            )

    def test_balanced_delegation_does_not_hide_approval_gated_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            policy = build_execution_policy("builder")
            scope = prepare_execution_scope(root, "mission_approval_gate_test", requested_scope="direct", profile_name="builder")
            step = PlannedStep(
                step_id="step_review",
                title="Review referenced docs and extract constraints",
                description="Review referenced docs and extract constraints",
            )

            proposal = build_action_proposal(
                step=step,
                objective="Verify the repo with approval-gated verification",
                workspace_root=root,
                verification_commands=["git reset --hard"],
                runtime_id="hermes",
                execution_scope=scope,
                execution_policy=policy,
                route_configs=[],
            )

            self.assertNotEqual(proposal.kind, "runtime_delegate")

    @mock.patch("grant_agent.runtime_supervisor.runtime_adapter_map")
    @mock.patch("grant_agent.action_executor.runtime_adapter_map")
    def test_runtime_delegate_preserves_worktree_execution_truth(
        self,
        runtime_supervisor_map: mock.Mock,
        runtime_map: mock.Mock,
    ) -> None:
        class _FakeAdapter:
            runtime_id = "hermes"

            def detect(self, _: pathlib.Path):
                return type("Status", (), {"detected": True, "doctor_summary": "ready"})()

            def start_mission(self, mission, workspace):
                assert mission.route_configs[0].model == "gpt-5.4-mini"
                return {
                    "launch_command": f'"{sys.executable}" -c "print(\'delegate lane ready\')"',
                    "workspace": workspace.root_path,
                }

            def stream_events(self, mission):
                return [{"kind": "runtime.stream", "missionId": mission.mission_id}]

            def resume_mission(self, mission, workspace):
                return self.start_mission(mission, workspace)

        adapter_map = {"hermes": _FakeAdapter()}
        runtime_map.return_value = adapter_map
        runtime_supervisor_map.return_value = adapter_map

        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            _init_git_repo(root)
            policy = build_execution_policy("builder")
            scope = prepare_execution_scope(root, "mission_delegate_worktree", profile_name="builder")
            step = PlannedStep(step_id="step_delegate", title="Delegate execution to Hermes")
            proposal = build_action_proposal(
                step=step,
                objective="Delegate this mission to Hermes for a runtime lane check",
                workspace_root=root,
                verification_commands=[],
                runtime_id="hermes",
                execution_scope=scope,
                execution_policy=policy,
                route_configs=[
                    {
                        "role": "executor",
                        "provider": "openai",
                        "model": "gpt-5.4-mini",
                        "effort": "medium",
                    }
                ],
            )

            record = execute_action(
                proposal,
                root,
                execution_scope=scope,
                execution_policy=policy,
            )

            self.assertTrue(record.result.ok)
            self.assertEqual(record.result.payload["delegatedSession"]["execution_target"], "worktree")
            self.assertEqual(record.result.payload["delegatedSnapshot"]["execution_target"], "worktree")

    @mock.patch("grant_agent.runtime_supervisor.runtime_adapter_map")
    @mock.patch("grant_agent.action_executor.runtime_adapter_map")
    def test_runtime_delegate_preserves_planner_phase_for_delegated_launch(
        self,
        runtime_supervisor_map: mock.Mock,
        runtime_map: mock.Mock,
    ) -> None:
        class _FakeAdapter:
            runtime_id = "hermes"

            def detect(self, _: pathlib.Path):
                return type("Status", (), {"detected": True, "doctor_summary": "ready"})()

            def start_mission(self, mission, workspace):
                assert mission.state.current_cycle_phase == "plan"
                assert mission.route_configs[0].role == "planner"
                return {
                    "launch_command": f'"{sys.executable}" -c "print(\'delegate planner lane ready\')"',
                    "workspace": workspace.root_path,
                    "route_contract": {
                        "phase": mission.state.current_cycle_phase,
                        "role": "planner",
                    },
                }

            def stream_events(self, mission):
                return [{"kind": "runtime.stream", "missionId": mission.mission_id}]

            def resume_mission(self, mission, workspace):
                return self.start_mission(mission, workspace)

        adapter_map = {"hermes": _FakeAdapter()}
        runtime_map.return_value = adapter_map
        runtime_supervisor_map.return_value = adapter_map

        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            policy = build_execution_policy("builder")
            scope = prepare_execution_scope(root, "mission_delegate_plan", requested_scope="direct", profile_name="builder")
            step = PlannedStep(step_id="step_delegate", title="Delegate approval investigation to Hermes")
            proposal = build_action_proposal(
                step=step,
                objective="Delegate approval investigation to Hermes for a runtime lane check",
                workspace_root=root,
                verification_commands=[],
                runtime_id="hermes",
                execution_scope=scope,
                execution_policy=policy,
                route_configs=[
                    {
                        "role": "planner",
                        "provider": "openai",
                        "model": "gpt-5.4",
                        "effort": "high",
                    }
                ],
            )

            record = execute_action(
                proposal,
                root,
                execution_scope=scope,
                execution_policy=policy,
            )

            self.assertEqual(proposal.delegation_metadata["cycle_phase"], "plan")
            self.assertTrue(record.result.ok)


if __name__ == "__main__":
    unittest.main()
