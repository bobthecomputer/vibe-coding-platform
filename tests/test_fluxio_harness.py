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
    build_route_outcome_trends,
    recommended_model_routes,
    resolve_efficiency_autotune_policy,
)
from grant_agent.models import DelegatedRuntimeSession, ModelRouteConfig, PlannedStep, PlanRevision
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

    def test_skill_library_records_slice_feedback_loss_and_catalog_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
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
                    ]
                ),
                encoding="utf-8",
            )
            library = SkillLibrary(root=root, registry=SkillRegistry(config_dir / "skills.json"))

            records = library.record_slice_feedback(
                mission_id="mission_demo",
                step_id="step_patch",
                selected_skills=[
                    {"skillId": "repo_scan", "label": "Repo Scan", "sourceKind": "curated"}
                ],
                execution_ok=True,
                verification_failures=[],
                changed_files=["src/app.py"],
            )
            catalog = library.build_catalog()

            self.assertEqual(records[0]["nextAction"], "reinforce")
            self.assertLess(records[0]["systemLoss"], 0.15)
            self.assertEqual(catalog["feedbackLoop"]["cadence"], "mission_slice_end")
            self.assertEqual(catalog["feedbackLoop"]["totalFeedbackSlices"], 1)
            self.assertTrue(catalog["feedbackLoop"]["systemLossRouting"]["enabled"])
            self.assertEqual(
                catalog["curatedPacks"][0]["feedbackSummary"]["selectionPolicy"]["state"],
                "prefer",
            )
            self.assertEqual(
                catalog["curatedPacks"][0]["feedbackSummary"]["trend"],
                "reinforce",
            )
            runtime_contract = catalog["runtimeContract"]
            self.assertEqual(runtime_contract["schema"], "fluxio.skill_runtime_contract.v1")
            self.assertEqual(runtime_contract["primaryRuntimeLane"], "hermes")
            self.assertIn("openclaw", runtime_contract["fallbackRuntimeLanes"])
            self.assertIn("opencode", runtime_contract["fallbackRuntimeLanes"])
            self.assertEqual(runtime_contract["skills"][0]["output"]["schema"], "fluxio.skill_runtime_result.v1")
            self.assertTrue(runtime_contract["skills"][0]["output"]["artifactRequired"])
            self.assertIn("attach_proof_to_mission", runtime_contract["skills"][0]["guardrails"])

    def test_skill_retrieval_uses_slice_loss_to_route_away_from_repair_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            config_dir = root / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "skills.json").write_text(
                json.dumps(
                    [
                        {
                            "name": "repo_scan",
                            "description": "Ground the repo workspace task in evidence",
                            "schema": {"type": "object", "properties": {}},
                            "permissions": ["file_read"],
                        },
                        {
                            "name": "workspace_risky_runner",
                            "description": "Run workspace repo changes quickly",
                            "schema": {"type": "object", "properties": {}},
                            "permissions": ["file_write"],
                        },
                    ]
                ),
                encoding="utf-8",
            )
            library = SkillLibrary(root=root, registry=SkillRegistry(config_dir / "skills.json"))
            library.record_slice_feedback(
                mission_id="mission_bad",
                step_id="step_risky",
                selected_skills=[
                    {
                        "skillId": "workspace_risky_runner",
                        "label": "Workspace Risky Runner",
                        "sourceKind": "curated",
                    }
                ],
                execution_ok=False,
                verification_failures=["python -m pytest"],
                changed_files=[],
            )
            library.record_slice_feedback(
                mission_id="mission_good",
                step_id="step_repo",
                selected_skills=[{"skillId": "repo_scan", "label": "Repo Scan", "sourceKind": "curated"}],
                execution_ok=True,
                verification_failures=[],
                changed_files=["src/app.py"],
            )

            retrieved = library.retrieve("repo workspace changes", top_k=1)

            self.assertEqual(retrieved[0]["skillId"], "repo_scan")
            self.assertEqual(retrieved[0]["selectionPolicy"]["state"], "prefer")

    def test_operator_value_closeouts_change_skill_selection_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            config_dir = root / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "skills.json").write_text(
                json.dumps(
                    [
                        {
                            "name": "useful_workspace_loop",
                            "description": "Handle workspace repo task evidence",
                            "schema": {"type": "object", "properties": {}},
                            "permissions": ["file_read"],
                        },
                        {
                            "name": "low_value_workspace_loop",
                            "description": "Handle workspace repo task evidence",
                            "schema": {"type": "object", "properties": {}},
                            "permissions": ["file_read"],
                        },
                    ]
                ),
                encoding="utf-8",
            )
            control_dir = root / ".agent_control"
            control_dir.mkdir()
            missions = []
            for index, (skill_id, score, outcome, signal) in enumerate(
                [
                    ("useful_workspace_loop", 91, "useful", "promote"),
                    ("useful_workspace_loop", 86, "useful", "promote"),
                    ("low_value_workspace_loop", 32, "not_useful", "deprioritize"),
                ]
            ):
                missions.append(
                    {
                        "mission_id": f"mission_skill_value_{index}",
                        "updated_at": f"2026-05-28T0{index}:00:00+00:00",
                        "skill_usage": [
                            {
                                "skill_id": skill_id,
                                "label": skill_id.replace("_", " ").title(),
                                "helped": signal == "promote",
                            }
                        ],
                        "state": {
                            "status": "completed",
                            "operator_value_feedback": {
                                "schema": "fluxio.mission_operator_value_feedback.v1",
                                "score": score,
                                "outcome": outcome,
                                "trustSignal": signal,
                            },
                        },
                    }
                )
            (control_dir / "missions.json").write_text(json.dumps(missions), encoding="utf-8")
            library = SkillLibrary(root=root, registry=SkillRegistry(config_dir / "skills.json"))

            retrieved = library.retrieve("workspace repo task evidence", top_k=2)
            catalog = library.build_catalog()
            useful = next(item for item in catalog["curatedPacks"] if item["packId"] == "curated:useful_workspace_loop")
            low_value = next(item for item in catalog["curatedPacks"] if item["packId"] == "curated:low_value_workspace_loop")

            self.assertEqual(retrieved[0]["skillId"], "useful_workspace_loop")
            self.assertNotIn("low_value_workspace_loop", [item["skillId"] for item in retrieved])
            self.assertEqual(useful["feedbackSummary"]["operatorValue"]["state"], "prefer")
            self.assertEqual(useful["feedbackSummary"]["promotionGate"]["eligible"], True)
            self.assertEqual(low_value["feedbackSummary"]["selectionPolicy"]["state"], "deprioritize")
            self.assertEqual(low_value["systemLossHold"]["held"], True)
            self.assertEqual(catalog["feedbackLoop"]["operatorValueSkillCount"], 2)
            self.assertIn("operator_value_closeout", catalog["feedbackLoop"]["scoreInputs"])

    def test_high_loss_skill_feedback_creates_repair_proposal_with_validation_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            config_dir = root / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "skills.json").write_text(
                json.dumps(
                    [
                        {
                            "name": "workspace_risky_runner",
                            "description": "Run workspace repo changes quickly",
                            "schema": {"type": "object", "properties": {}},
                            "permissions": ["file_write"],
                        },
                    ]
                ),
                encoding="utf-8",
            )
            library = SkillLibrary(root=root, registry=SkillRegistry(config_dir / "skills.json"))

            library.record_slice_feedback(
                mission_id="mission_bad",
                step_id="step_risky",
                selected_skills=[
                    {
                        "skillId": "workspace_risky_runner",
                        "label": "Workspace Risky Runner",
                        "sourceKind": "curated",
                    }
                ],
                execution_ok=False,
                verification_failures=["python -m pytest"],
                changed_files=[],
            )
            catalog = library.build_catalog()

            proposals = catalog["feedbackLoop"]["repairProposals"]
            self.assertEqual(len(proposals), 1)
            self.assertEqual(proposals[0]["skillId"], "workspace_risky_runner")
            self.assertEqual(proposals[0]["beforeVerification"]["missionId"], "mission_bad")
            self.assertEqual(
                proposals[0]["beforeVerification"]["verificationFailures"],
                ["python -m pytest"],
            )
            self.assertEqual(proposals[0]["afterVerification"]["maxSystemLoss"], 0.15)
            self.assertEqual(
                proposals[0]["repairPatch"]["routePolicy"],
                "deprioritize_until_clean_validation_slice",
            )
            self.assertEqual(
                catalog["curatedPacks"][0]["feedbackSummary"]["repairProposal"]["nextAction"],
                "repair_before_reuse",
            )
            retrieved = library.retrieve("workspace risky runner", top_k=1)
            self.assertEqual(retrieved, [])
            self.assertEqual(catalog["curatedPacks"][0]["systemLossHold"]["held"], True)

    def test_apply_repair_proposal_updates_editable_learned_skill_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            config_dir = root / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "skills.json").write_text("[]", encoding="utf-8")
            control_dir = root / ".agent_control"
            control_dir.mkdir()
            (control_dir / "learned_skills.json").write_text(
                json.dumps(
                    [
                        {
                            "skill_id": "learned_risky_runner",
                            "label": "Risky Runner",
                            "description": "Runs workspace changes quickly.",
                            "prompt_hint": "Move fast.",
                            "source": {"kind": "learned", "label": "Learned"},
                            "confidence": 0.7,
                            "status": "learned",
                            "tags": ["learned"],
                            "permissions": ["file_write"],
                            "audit": [],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            library = SkillLibrary(root=root, registry=SkillRegistry(config_dir / "skills.json"))
            library.record_slice_feedback(
                mission_id="mission_bad",
                step_id="step_risky",
                selected_skills=[
                    {
                        "skillId": "learned_risky_runner",
                        "label": "Risky Runner",
                        "sourceKind": "learned",
                    }
                ],
                execution_ok=False,
                verification_failures=["python -m pytest"],
                changed_files=[],
            )
            proposal = library.build_catalog()["feedbackLoop"]["repairProposals"][0]

            receipt = library.apply_repair_proposal(
                proposal_id=proposal["proposalId"],
                reviewer="operator",
                validation_mission_id="mission_validation",
            )

            self.assertEqual(receipt["schema"], "fluxio.skill_repair_apply_receipt.v1")
            self.assertEqual(receipt["status"], "applied")
            self.assertIn("ground the slice", receipt["afterPromptHint"])
            updated = SkillLibrary(root=root, registry=SkillRegistry(config_dir / "skills.json"))
            self.assertEqual(updated.learned_skills[0].status, "repair_applied")
            self.assertIn("repair-applied", updated.learned_skills[0].tags)
            self.assertTrue((control_dir / "skill_repair_receipts.json").exists())

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
            self.assertTrue(result["skill_feedback_events"])
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
            self.assertEqual(first_planner["provider"], "openai-codex")
            self.assertEqual(first_planner["model"], "gpt-5.5")
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
            self.assertEqual(resumed_planner["provider"], "openai-codex")
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
        self.assertEqual(planner.provider, "openai-codex")
        self.assertEqual(planner.model, "gpt-5.5")
        self.assertEqual(executor.provider, "minimax")
        self.assertEqual(executor.model, "MiniMax-M3")
        self.assertIn("override", executor.explanation.lower())

    def test_recommended_routes_use_task_fit_for_frontend_execution(self) -> None:
        routes = recommended_model_routes(
            "builder",
            routing_strategy_override="profile_default",
            objective="Build a polished React frontend UI with mobile design proof.",
        )
        planner = next(item for item in routes if item.role == "planner")
        executor = next(item for item in routes if item.role == "executor")
        verifier = next(item for item in routes if item.role == "verifier")

        self.assertEqual(planner.provider, "openai-codex")
        self.assertEqual(planner.model, "gpt-5.5")
        self.assertEqual(executor.provider, "minimax")
        self.assertEqual(executor.model, "MiniMax-M3")
        self.assertEqual(executor.task_type, "frontend_design")
        self.assertEqual(executor.route_intent, "visual_interface_execution")
        self.assertGreaterEqual(executor.fit_score, 70)
        self.assertIn("Frontend/UI/design", executor.explanation)
        self.assertEqual(verifier.provider, "openai")
        self.assertEqual(verifier.model, "gpt-5.5")
        self.assertEqual(verifier.task_type, "frontend_design")

    def test_recommended_routes_use_task_fit_for_hardware_and_f1_missions(self) -> None:
        hardware_routes = recommended_model_routes(
            "builder",
            routing_strategy_override="profile_default",
            objective="Build a hardware engineering tool for electrical circuit simulation and sensor analysis.",
        )
        hardware_executor = next(item for item in hardware_routes if item.role == "executor")
        self.assertEqual(hardware_executor.task_type, "hardware_electrical")
        self.assertEqual(hardware_executor.model, "gpt-5.5")
        self.assertEqual(hardware_executor.route_intent, "engineering_simulation_execution")

        f1_routes = recommended_model_routes(
            "builder",
            routing_strategy_override="profile_default",
            objective="Create an F1 telemetry analytics dashboard for lap time visualization.",
        )
        f1_executor = next(item for item in f1_routes if item.role == "executor")
        self.assertEqual(f1_executor.task_type, "data_f1_analytics")
        self.assertEqual(f1_executor.model, "gpt-5.5")
        self.assertEqual(f1_executor.route_intent, "analytics_dashboard_execution")

    def test_recommended_routes_use_outcome_trends_for_similar_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            runs_root = root / ".agent_runs"
            for index in range(2):
                session = runs_root / f"session_f1_success_{index}"
                session.mkdir(parents=True)
                (session / "state.json").write_text(
                    json.dumps(
                        {
                            "objective": "Create an F1 telemetry analytics dashboard for lap visualization.",
                            "autopilot_status": "completed",
                            "route_configs": [
                                {
                                    "role": "executor",
                                    "provider": "minimax",
                                    "model": "MiniMax-M2.7",
                                    "effort": "medium",
                                    "budget_class": "specialist",
                                },
                                {
                                    "role": "verifier",
                                    "provider": "openai",
                                    "model": "gpt-5.5",
                                    "effort": "high",
                                    "budget_class": "premium",
                                },
                            ],
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )

            trends = build_route_outcome_trends(root)
            routes = recommended_model_routes(
                "builder",
                routing_strategy_override="profile_default",
                objective="Build an F1 telemetry analytics dashboard for tire and lap-time comparison.",
                route_outcome_trends=trends,
            )
            executor = next(item for item in routes if item.role == "executor")

            self.assertEqual(executor.provider, "minimax")
            self.assertEqual(executor.model, "MiniMax-M3")
            self.assertEqual(executor.task_type, "data_f1_analytics")
            self.assertEqual(executor.route_intent, "outcome_trend_execution")
            self.assertEqual(executor.outcome_sample_count, 2)
            self.assertEqual(executor.outcome_success_rate, 100)
            self.assertIn("outcome trend", executor.explanation)

    def test_operator_value_closeouts_feed_route_outcome_trends(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True)
            missions = []
            for index, score in enumerate((92, 88)):
                missions.append(
                    {
                        "mission_id": f"mission_operator_value_{index}",
                        "workspace_id": "workspace_default",
                        "runtime_id": "hermes",
                        "objective": "Create an F1 telemetry analytics dashboard for race pace comparison.",
                        "updated_at": f"2026-05-28T0{index}:00:00+00:00",
                        "route_configs": [
                            {
                                "role": "executor",
                                "provider": "minimax",
                                "model": "MiniMax-M2.7",
                                "effort": "medium",
                                "budget_class": "specialist",
                            }
                        ],
                        "state": {
                            "status": "completed",
                            "operator_value_feedback": {
                                "schema": "fluxio.mission_operator_value_feedback.v1",
                                "score": score,
                                "outcome": "useful",
                                "trustSignal": "promote",
                            },
                        },
                    }
                )
            (control_dir / "missions.json").write_text(
                json.dumps(missions, indent=2),
                encoding="utf-8",
            )

            trends = build_route_outcome_trends(root)
            recommendation = trends["recommendations"]["data_f1_analytics"]["executor"]
            routes = recommended_model_routes(
                "builder",
                routing_strategy_override="profile_default",
                objective="Build an F1 telemetry analytics dashboard.",
                route_outcome_trends=trends,
            )
            executor = next(item for item in routes if item.role == "executor")

            self.assertEqual(trends["scannedMissionCloseouts"], 2)
            self.assertEqual(recommendation["operatorValueSampleCount"], 2)
            self.assertEqual(recommendation["operatorValueAverage"], 90)
            self.assertEqual(executor.provider, "minimax")
            self.assertEqual(executor.route_intent, "outcome_trend_execution")
            self.assertIn("operator value 90/100", executor.outcome_trend)

    def test_frontend_specialist_route_keeps_minimax_m3_despite_codex_outcome_trend(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True)
            missions = [
                {
                    "mission_id": "mission_frontend_codex_closeout",
                    "workspace_id": "workspace_default",
                    "runtime_id": "hermes",
                    "objective": "Fix a React frontend UI and mobile Builder surface.",
                    "updated_at": "2026-06-02T10:00:00+00:00",
                    "route_configs": [
                        {
                            "role": "executor",
                            "provider": "openai-codex",
                            "model": "gpt-5.5",
                            "effort": "high",
                            "budget_class": "specialist",
                            "task_type": "frontend_design",
                        }
                    ],
                    "state": {
                        "status": "completed",
                        "operator_value_feedback": {
                            "schema": "fluxio.mission_operator_value_feedback.v1",
                            "score": 86,
                            "outcome": "useful",
                            "trustSignal": "promote",
                            "routeTrustTaskType": "frontend_design",
                        },
                    },
                }
            ]
            (control_dir / "missions.json").write_text(json.dumps(missions, indent=2), encoding="utf-8")

            trends = build_route_outcome_trends(root)
            routes = recommended_model_routes(
                "builder",
                routing_strategy_override="profile_default",
                objective="Fix the React frontend UI with MiniMax M3 inside Hermes.",
                route_outcome_trends=trends,
            )
            executor = next(item for item in routes if item.role == "executor")

            self.assertEqual(executor.provider, "minimax")
            self.assertEqual(executor.model, "MiniMax-M3")
            self.assertEqual(executor.route_intent, "visual_interface_execution")
            self.assertIn("Frontend/UI/design work routes execution to MiniMax", executor.explanation)

    def test_low_value_route_closeouts_quarantine_task_fit_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True)
            missions = []
            for index, score in enumerate((31, 42)):
                missions.append(
                    {
                        "mission_id": f"mission_low_value_frontend_{index}",
                        "workspace_id": "workspace_default",
                        "runtime_id": "hermes",
                        "objective": "Build a polished React frontend UI with mobile design proof.",
                        "updated_at": f"2026-05-28T0{index}:00:00+00:00",
                        "route_configs": [
                            {
                                "role": "executor",
                                "provider": "minimax",
                                "model": "MiniMax-M2.7",
                                "effort": "high",
                                "budget_class": "specialist",
                            }
                        ],
                        "state": {
                            "status": "completed",
                            "operator_value_feedback": {
                                "schema": "fluxio.mission_operator_value_feedback.v1",
                                "score": score,
                                "outcome": "not_useful",
                                "trustSignal": "deprioritize",
                            },
                        },
                    }
                )
            (control_dir / "missions.json").write_text(json.dumps(missions, indent=2), encoding="utf-8")

            trends = build_route_outcome_trends(root)
            quarantined = trends["quarantinedRoutes"]["frontend_design"]["executor"][0]
            routes = recommended_model_routes(
                "builder",
                routing_strategy_override="profile_default",
                objective="Build a polished React frontend UI with mobile design proof.",
                route_outcome_trends=trends,
            )
            executor = next(item for item in routes if item.role == "executor")

            self.assertEqual(quarantined["schema"], "fluxio.route_outcome_quarantine.v1")
            self.assertEqual(quarantined["provider"], "minimax")
            self.assertEqual(quarantined["model"], "MiniMax-M2.7")
            self.assertEqual(quarantined["operatorValueSampleCount"], 2)
            self.assertEqual(quarantined["operatorDeprioritizeCount"], 2)
            self.assertEqual(executor.provider, "minimax")
            self.assertEqual(executor.model, "MiniMax-M3")
            self.assertEqual(executor.route_intent, "visual_interface_execution")

    def test_explicit_executor_override_wins_over_task_fit(self) -> None:
        routes = recommended_model_routes(
            "builder",
            routing_strategy_override="profile_default",
            objective="Build a polished frontend UI.",
            route_overrides=[
                {
                    "role": "executor",
                    "provider": "openai",
                    "model": "gpt-5.4-mini",
                    "effort": "medium",
                }
            ],
        )
        executor = next(item for item in routes if item.role == "executor")

        self.assertEqual(executor.provider, "openai")
        self.assertEqual(executor.model, "gpt-5.4-mini")
        self.assertEqual(executor.task_type, "frontend_design")
        self.assertEqual(executor.route_intent, "manual_workspace_override")
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


if __name__ == "__main__":
    unittest.main()

