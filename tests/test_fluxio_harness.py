from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.fluxio_harness import (
    FluxioHarness,
    LegacyHarnessAdapter,
    recommended_model_routes,
    resolve_efficiency_autotune_policy,
)
from grant_agent.models import DelegatedRuntimeSession, ExecutionPolicy, ModelRouteConfig, PlannedStep, PlanRevision
from grant_agent.session_store import SessionStore
from grant_agent.skill_library import SkillLibrary
from grant_agent.skills import SkillRegistry
from grant_agent.verification import VerificationRunner


class _DummyEngine:
    def run(self, **_: object) -> dict:
        return {"status": "ok"}


class FluxioHarnessTests(unittest.TestCase):
    def _build_harness(self, root: pathlib.Path) -> FluxioHarness:
        config_dir = root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "skills.json").write_text(
            json.dumps(
                [
                    {
                        "name": "repo_scan",
                        "description": "Ground the task in repo evidence",
                        "schema": {"type": "object", "properties": {}},
                        "permissions": ["file_read"],
                    }
                ],
                indent=2,
            ),
            encoding="utf-8",
        )
        return FluxioHarness(
            compatibility_harness=LegacyHarnessAdapter(_DummyEngine()),
            session_store=SessionStore(root / ".agent_runs"),
            verification_runner=VerificationRunner(),
            skill_library=SkillLibrary(root=root, registry=SkillRegistry(config_dir / "skills.json")),
        )

    def test_skill_library_ignores_empty_control_json_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            config_dir = root / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "skills.json").write_text("[]", encoding="utf-8")
            control_dir = root / ".agent_control"
            control_dir.mkdir()
            (control_dir / "learned_skills.json").write_text("", encoding="utf-8")

            library = SkillLibrary(root=root, registry=SkillRegistry(config_dir / "skills.json"))

            self.assertEqual(library.learned_skills, [])

    def test_openai_codex_provider_does_not_force_repeated_handoff(self) -> None:
        session = type(
            "Session",
            (),
            {
                "target_phase": "execute",
                "target_provider": "openai-codex",
                "target_model": "gpt-5.4-mini",
                "target_effort": "medium",
            },
        )()
        desired = ModelRouteConfig(
            role="executor",
            provider="openai",
            model="gpt-5.4-mini",
            effort="medium",
        )

        self.assertFalse(
            FluxioHarness._delegated_route_mismatch(
                session,
                desired_phase="execute",
                desired_route=desired,
            )
        )

    def test_failed_delegated_runtime_sets_blocking_trigger(self) -> None:
        step = PlannedStep(
            step_id="step_auth",
            title="Run delegated Hermes lane",
            description="Run delegated Hermes lane",
        )
        plan_revisions = [
            PlanRevision(
                revision_id="rev_auth",
                trigger="mission_start",
                summary="Test plan",
                steps=[step],
                active_step_id=step.step_id,
            )
        ]
        session = DelegatedRuntimeSession(
            delegated_id="delegate_auth",
            runtime_id="hermes",
            launch_command="hermes chat -q demo -Q",
            status="failed",
            detail="Delegated runtime process failed.",
            last_event="Codex token refresh failed with status 401.",
            source_step_id=step.step_id,
        )
        supervisor = type(
            "Supervisor",
            (),
            {"refresh_session": staticmethod(lambda _item: session)},
        )()

        refreshed, active_status, replan_trigger = FluxioHarness._reconcile_delegated_sessions(
            delegated_runtime_sessions=[{}],
            plan_revisions=plan_revisions,
            runtime_supervisor=supervisor,
            notes=[],
            risks=[],
            objective="Repair control room",
            route_configs=[],
        )

        self.assertEqual(active_status, "")
        self.assertEqual(replan_trigger, "delegated_runtime_failed")
        self.assertEqual(plan_revisions[-1].steps[0].status, "blocked")
        self.assertEqual(plan_revisions[-1].steps[0].attempts, 1)
        self.assertTrue(refreshed[0]["acknowledged"])

    def test_harness_runs_and_promotes_learned_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text(
                "import unittest\n\nclass Sample(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )

            harness = self._build_harness(root)
            result = harness.run(
                objective="Verify the control room and repo grounding flow",
                docs=["README.md"],
                project_profile="Harness test",
                verify_commands=["python -m unittest discover -s tests"],
                repo_path=root,
                iterations=4,
                max_handoffs=6,
                max_runtime_seconds=300,
                profile_name="builder",
            )

            self.assertEqual(result["harness_id"], "fluxio_hybrid")
            self.assertGreaterEqual(len(result["route_configs"]), 4)
            self.assertTrue(result["plan_revisions"])
            self.assertTrue(result["learned_skill_events"])
            self.assertIn("execution_scope", result)
            self.assertIn("execution_policy", result)

    def test_rejected_action_triggers_replanning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text(
                "import unittest\n\nclass Sample(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )

            harness = self._build_harness(root)
            first = harness.run(
                objective="Verify the repo with approval-gated verification",
                docs=["README.md"],
                project_profile="Approval test",
                verify_commands=["git reset --hard"],
                repo_path=root,
                iterations=4,
                max_handoffs=6,
                max_runtime_seconds=300,
                profile_name="builder",
            )
            self.assertEqual(first["autopilot_pause_reason"], "approval_required")

            session_path = pathlib.Path(first["session_path"])
            state_path = session_path / "state.json"
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            payload["action_history"][-1]["gate"]["status"] = "rejected"
            state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            resumed = harness.run(
                objective="Verify the repo with approval-gated verification",
                docs=["README.md"],
                project_profile="Approval test",
                verify_commands=["git reset --hard"],
                repo_path=root,
                iterations=2,
                max_handoffs=6,
                max_runtime_seconds=300,
                profile_name="builder",
                resume_from_session_id=session_path.name,
            )

            triggers = [item["trigger"] for item in resumed["plan_revisions"]]
            self.assertIn("approval_rejected", triggers)

    def test_resume_recomputes_route_config_from_current_strategy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text(
                "import unittest\n\nclass Sample(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )

            harness = self._build_harness(root)
            first = harness.run(
                objective="Keep route choices stable across resume",
                docs=["README.md"],
                project_profile="Routing continuity test",
                verify_commands=["python -m unittest discover -s tests"],
                repo_path=root,
                iterations=2,
                max_handoffs=4,
                max_runtime_seconds=120,
                profile_name="builder",
                routing_strategy_override="budget_first",
            )
            first_planner = next(
                item for item in first["route_configs"] if item["role"] == "planner"
            )
            first_executor = next(
                item for item in first["route_configs"] if item["role"] == "executor"
            )
            self.assertEqual(first_planner["model"], "gpt-5.4-mini")
            self.assertEqual(first_executor["model"], "gpt-5.4-mini")

            resumed = harness.run(
                objective="Keep route choices stable across resume",
                docs=["README.md"],
                project_profile="Routing continuity test",
                verify_commands=["python -m unittest discover -s tests"],
                repo_path=root,
                iterations=1,
                max_handoffs=4,
                max_runtime_seconds=120,
                profile_name="builder",
                resume_from_session_id=pathlib.Path(first["session_path"]).name,
                routing_strategy_override="uniform_quality",
            )
            resumed_planner = next(
                item for item in resumed["route_configs"] if item["role"] == "planner"
            )
            resumed_executor = next(
                item for item in resumed["route_configs"] if item["role"] == "executor"
            )
            self.assertEqual(resumed_planner["model"], "gpt-5.5")
            self.assertEqual(resumed_executor["model"], "gpt-5.5")

    def test_recommended_routes_apply_role_overrides_first(self) -> None:
        routes = recommended_model_routes(
            "builder",
            routing_strategy_override="uniform_quality",
            route_overrides=[
                {
                    "role": "executor",
                    "provider": "minimax",
                    "model": "MiniMax-M2.7-highspeed",
                    "effort": "medium",
                }
            ],
        )
        planner = next(item for item in routes if item.role == "planner")
        executor = next(item for item in routes if item.role == "executor")
        self.assertEqual(planner.model, "gpt-5.5")
        self.assertEqual(executor.provider, "minimax")
        self.assertEqual(executor.model, "MiniMax-M2.7-highspeed")
        self.assertIn("override", executor.explanation.lower())

    def test_autotune_policy_waits_for_local_sample_size(self) -> None:
        policy = resolve_efficiency_autotune_policy(
            harness_lab_snapshot={
                "efficiency": {"totalRuns": 2, "completionRate": 100, "approvalPauseRate": 0},
                "sessionHealth": {"staleHeartbeatCount": 0},
            },
            auto_optimize_routing=True,
            requested_strategy="profile_default",
        )
        self.assertTrue(policy["enabled"])
        self.assertFalse(policy["eligible"])
        self.assertFalse(policy["appliedPolicy"])
        self.assertIn("Not enough local data", policy["reason"])

    def test_autotune_policy_switches_to_safe_route_when_completion_is_low(self) -> None:
        policy = resolve_efficiency_autotune_policy(
            harness_lab_snapshot={
                "efficiency": {
                    "totalRuns": 5,
                    "completionRate": 40,
                    "approvalPauseRate": 10,
                    "averageVerificationFailures": 1.2,
                },
                "sessionHealth": {"staleHeartbeatCount": 0},
            },
            auto_optimize_routing=True,
            requested_strategy="budget_first",
        )
        self.assertTrue(policy["eligible"])
        self.assertEqual(policy["routingStrategy"], "uniform_quality")
        self.assertEqual(policy["appliedPolicy"]["policy"], "safety_bias")

    def test_harness_compacts_context_and_saves_handoff_packets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text(
                "import unittest\n\nclass Sample(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )

            harness = self._build_harness(root)
            result = harness.run(
                objective="Implement a very long runtime continuity objective with repeated context summaries and proof checkpoints",
                docs=["README.md"],
                project_profile="Runtime rollover test",
                verify_commands=["python -m unittest discover -s tests"],
                repo_path=root,
                iterations=4,
                max_handoffs=3,
                max_runtime_seconds=300,
                profile_name="builder",
                max_tokens=24,
            )

            self.assertTrue(result["handoff_packets"])
            self.assertEqual(result["context"]["status"], "ok")
            self.assertTrue(result["context_seed"])

    def test_harness_shifts_to_uniform_quality_after_verification_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            harness = self._build_harness(root)

            result = harness.run(
                objective="Implement runtime repair notes",
                docs=["README.md"],
                project_profile="Autonomy route test",
                verify_commands=[f"{sys.executable} -c \"import sys; sys.exit(1)\""],
                repo_path=root,
                iterations=2,
                max_handoffs=4,
                max_runtime_seconds=120,
                profile_name="builder",
                routing_strategy_override="budget_first",
            )

            self.assertEqual(result["runtime_autonomy"]["routingStrategy"], "uniform_quality")
            self.assertGreaterEqual(result["route_change_count"], 1)
            self.assertEqual(result["execution_policy"]["delegation_aggressiveness"], "low")

    def test_experimental_guardrail_preserves_hands_free_runtime_delegation(self) -> None:
        routes, policy, _autonomy, changed, _route_change_count = FluxioHarness._apply_runtime_autonomy(
            profile_name="experimental",
            route_configs=recommended_model_routes("experimental", routing_strategy_override="budget_first"),
            route_overrides=[],
            execution_policy=ExecutionPolicy(
                profile_name="experimental",
                approval_mode="hands_free",
                explanation_depth="low",
                delegation_aggressiveness="high",
                auto_allowed_kinds=["runtime_delegate"],
                approval_required_kinds=["git_commit", "shell_command"],
            ),
            repeated_failure_count=2,
            verification_failures=[],
            stable_success_streak=0,
            context_status="ok",
            delegated_status="",
            route_change_count=0,
            parallel_agents=1,
            merge_policy="best_score",
            max_tokens=1024,
        )

        self.assertTrue(changed)
        self.assertEqual(policy.approval_mode, "hands_free")
        self.assertEqual(policy.delegation_aggressiveness, "high")
        self.assertIn("runtime_delegate", policy.auto_allowed_kinds)
        self.assertNotIn("runtime_delegate", policy.approval_required_kinds)
        self.assertEqual(FluxioHarness._routing_strategy_for_routes(routes), "uniform_quality")


if __name__ == "__main__":
    unittest.main()

