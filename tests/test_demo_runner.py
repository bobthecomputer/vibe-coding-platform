from __future__ import annotations

import pathlib
import json
import shutil
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.challenge_presets import ChallengePresetRegistry
from grant_agent.demo_runner import (
    append_red_team_escalation_history,
    build_difficulty_escalation,
    build_red_team_escalation_trend,
    compare_training,
    export_report_bundle,
    load_red_team_escalation_history,
    run_adversarial_probe,
    summarize_run,
)
from scripts.verify_self_improvement_evidence import (
    build_self_improvement_evidence,
    record_red_team_sample,
)
from scripts.advance_self_improvement_red_team_loop import (
    WATCHDOG_CADENCE_SCHEMA,
    advance_red_team_loop,
    record_watchdog_cadence_receipt,
)


class DemoRunnerTests(unittest.TestCase):
    def test_compare_training(self) -> None:
        before = {"completion_score": 40, "remaining_steps": ["a", "b"], "verification_failures": ["x"]}
        after = {"completion_score": 70, "remaining_steps": ["a"], "verification_failures": []}
        comparison = compare_training(before, after)
        self.assertGreater(comparison["score_delta"], 0)
        self.assertTrue(comparison["improved"])

    def test_probe_and_bundle_export(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = ChallengePresetRegistry(root / "config" / "challenge_presets.json")
        preset = registry.get("hackaprompt")

        probe = run_adversarial_probe(preset, "Evaluate injection resilience")
        self.assertGreaterEqual(probe["attempt_count"], 1)
        self.assertIn("difficultyEscalation", probe)
        self.assertIn("escalationTrend", probe)
        self.assertGreaterEqual(
            probe["difficultyEscalation"]["nextAttemptBudget"],
            probe["attempt_count"],
        )

        bundle_root = root / ".demo_bundle_test"
        if bundle_root.exists():
            shutil.rmtree(bundle_root)

        navigator = summarize_run("navigator", "balanced", {"session_path": "s", "remaining_steps": []})
        before = summarize_run(
            "before",
            "fast",
            {"session_path": "b", "remaining_steps": ["x"], "verification_failures": ["f"]},
        )
        after = summarize_run("after", "careful", {"session_path": "a", "remaining_steps": []})
        comparison = compare_training(before, after)

        exported = export_report_bundle(
            bundle_root=bundle_root,
            preset=preset,
            navigator=navigator,
            before=before,
            after=after,
            comparison=comparison,
            probe=probe,
            findings=["A", "B"],
            export_zip=False,
        )
        self.assertTrue(pathlib.Path(exported["proof_panel_path"]).exists())
        self.assertTrue(pathlib.Path(exported["proof_report_path"]).exists())
        self.assertTrue(
            (pathlib.Path(exported["bundle_path"]) / "red_team_escalation_trend.json").exists()
        )
        report = pathlib.Path(exported["proof_report_path"]).read_text(encoding="utf-8")
        self.assertIn("Next difficulty", report)
        exported_probe = json.loads(
            (pathlib.Path(exported["bundle_path"]) / "adversarial_probe.json").read_text(encoding="utf-8")
        )
        exported_payload = json.loads(
            (pathlib.Path(exported["bundle_path"]) / "proof_payload.json").read_text(encoding="utf-8")
        )
        self.assertFalse(exported_probe["rawPayloadExported"])
        self.assertEqual(exported_probe["payloadHandling"], "aggregate_only_redacted")
        self.assertEqual(exported_payload["probe"]["payloadHandling"], "aggregate_only_redacted")
        for attempt in exported_probe["attempts"]:
            self.assertEqual(attempt["prompt"], "[redacted: aggregate-only defensive red-team payload]")
            self.assertRegex(attempt["prompt_sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(attempt["prompt_length"], 0)

    def test_clean_red_team_pass_escalates_next_benchmark(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = ChallengePresetRegistry(root / "config" / "challenge_presets.json")
        preset = registry.get("hackaprompt")
        probe = {
            "attempt_count": 7,
            "blocked_attempt_count": 7,
            "resistance_score": 100,
            "attempts": [
                {"tactic": "format_smuggling"},
                {"tactic": "obfuscation"},
                {"tactic": "tool_confusion"},
            ],
        }

        escalation = build_difficulty_escalation(
            preset,
            probe,
            comparison={"score_delta": 12},
        )

        self.assertTrue(escalation["shouldEscalate"])
        self.assertTrue(escalation["cleanPass"])
        self.assertGreater(escalation["nextDifficultyLevel"], escalation["currentDifficultyLevel"])
        self.assertGreater(escalation["nextAttemptBudget"], probe["attempt_count"])
        self.assertFalse(escalation["safetyPolicy"]["rawPayloadExport"])

    def test_max_level_red_team_pass_escalates_pressure(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = ChallengePresetRegistry(root / "config" / "challenge_presets.json")
        preset = registry.get("hackaprompt")
        history = [
            {
                "schema": "fluxio.red_team_escalation_history.v1",
                "recordedAt": "2026-05-29T00:00:00+00:00",
                "preset": "hackaprompt",
                "status": "pass",
                "resistance_score": 100,
                "attempt_count": 27,
                "blocked_attempt_count": 27,
                "difficultyLevel": 5,
                "nextDifficultyLevel": 5,
                "passStreak": 8,
                "cleanPass": True,
                "shouldEscalate": True,
                "nextAttemptBudget": 29,
                "currentPressureIndex": 44,
                "nextPressureIndex": 50,
            }
        ]
        probe = {
            "attempt_count": 29,
            "blocked_attempt_count": 29,
            "resistance_score": 100,
            "status": "pass",
            "attempts": [
                {"tactic": "format_smuggling"},
                {"tactic": "obfuscation"},
                {"tactic": "tool_confusion"},
                {"tactic": "multi_turn"},
            ],
        }

        escalation = build_difficulty_escalation(preset, probe, history=history)

        self.assertEqual(escalation["currentDifficultyLevel"], 5)
        self.assertEqual(escalation["nextDifficultyLevel"], 5)
        self.assertGreater(escalation["nextPressureIndex"], escalation["currentPressureIndex"])
        self.assertGreater(escalation["pressureDelta"], 0)
        self.assertIn("pressure", escalation["nextDifficultyLabel"])
        self.assertIn("pressure", escalation["nextBenchmark"]["objective"])

    def test_max_level_red_team_pressure_never_regresses_from_short_history_tail(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = ChallengePresetRegistry(root / "config" / "challenge_presets.json")
        preset = registry.get("hackaprompt")
        history = [
            {
                "schema": "fluxio.red_team_escalation_history.v1",
                "recordedAt": "2026-05-31T23:50:20+00:00",
                "preset": "hackaprompt",
                "status": "pass",
                "resistance_score": 100,
                "attempt_count": 137,
                "blocked_attempt_count": 137,
                "difficultyLevel": 5,
                "nextDifficultyLevel": 5,
                "passStreak": 21,
                "cleanPass": True,
                "shouldEscalate": True,
                "currentPressureIndex": 170,
                "nextPressureIndex": 175,
                "nextAttemptBudget": 139,
            },
            {
                "schema": "fluxio.red_team_escalation_history.v1",
                "recordedAt": "2026-06-01T02:48:57+00:00",
                "preset": "hackaprompt",
                "status": "pass",
                "resistance_score": 100,
                "attempt_count": 139,
                "blocked_attempt_count": 139,
                "difficultyLevel": 5,
                "nextDifficultyLevel": 5,
                "passStreak": 6,
                "cleanPass": True,
                "shouldEscalate": True,
                "currentPressureIndex": 157,
                "nextPressureIndex": 162,
                "nextAttemptBudget": 141,
            },
        ]
        probe = {
            "attempt_count": 141,
            "blocked_attempt_count": 141,
            "resistance_score": 100,
            "status": "pass",
            "attempts": [
                {"tactic": "direct_policy_probe"},
                {"tactic": "roleplay"},
                {"tactic": "authority"},
            ],
        }

        escalation = build_difficulty_escalation(preset, probe, history=history)

        self.assertGreaterEqual(escalation["currentPressureIndex"], 175)
        self.assertGreater(escalation["nextPressureIndex"], escalation["currentPressureIndex"])
        self.assertIn("pressure", escalation["nextDifficultyLabel"])

    def test_probe_detects_simple_encoded_secret_request(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = ChallengePresetRegistry(root / "config" / "challenge_presets.json")
        preset = registry.get("hackaprompt")

        probe = run_adversarial_probe(preset, "Evaluate encoded injection resilience")

        self.assertEqual(probe["blocked_attempt_count"], probe["attempt_count"])
        encoded_attempt = next(
            item for item in probe["attempts"] if item["strategy"] == "encoding_obfuscation"
        )
        self.assertTrue(
            any(str(pattern).startswith("decoded:") for pattern in encoded_attempt["triggered_patterns"])
        )

    def test_red_team_escalation_history_is_aggregate_and_drives_streak(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = ChallengePresetRegistry(root / "config" / "challenge_presets.json")
        preset = registry.get("hackaprompt")
        temp_root = (root / ".demo_history_test").absolute()
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir()
        try:
            probe = {
                "attempt_count": 7,
                "blocked_attempt_count": 7,
                "resistance_score": 100,
                "status": "pass",
                "attempts": [{"tactic": "format_smuggling"}],
            }
            probe["difficultyEscalation"] = build_difficulty_escalation(preset, probe)
            first = append_red_team_escalation_history(
                root=temp_root,
                preset=preset,
                probe=probe,
                comparison={"score_delta": 8},
                bundle_path="bundle_1",
            )
            history = load_red_team_escalation_history(temp_root, preset.name)
            next_probe = {
                "attempt_count": 9,
                "blocked_attempt_count": 9,
                "resistance_score": 100,
                "status": "pass",
                "attempts": [{"tactic": "obfuscation"}],
            }
            next_probe["difficultyEscalation"] = build_difficulty_escalation(
                preset,
                next_probe,
                history=history,
            )
            second = append_red_team_escalation_history(
                root=temp_root,
                preset=preset,
                probe=next_probe,
                comparison={"score_delta": 3},
                bundle_path="bundle_2",
            )
            trend = build_red_team_escalation_trend([first, second])

            self.assertEqual(len(load_red_team_escalation_history(temp_root, preset.name)), 2)
            self.assertFalse(first["rawPayloadExported"])
            self.assertNotIn("attempts", first)
            self.assertGreaterEqual(next_probe["difficultyEscalation"]["passStreak"], 2)
            self.assertEqual(trend["schema"], "fluxio.red_team_escalation_trend.v1")
            self.assertEqual(trend["runCount"], 2)
            self.assertIn(trend["status"], {"tracking", "escalating"})
        finally:
            shutil.rmtree(temp_root)

    def test_red_team_probe_consumes_escalation_target_from_history(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = ChallengePresetRegistry(root / "config" / "challenge_presets.json")
        preset = registry.get("hackaprompt")
        history = [
            {
                "schema": "fluxio.red_team_escalation_history.v1",
                "recordedAt": "2026-05-28T00:00:00+00:00",
                "preset": "hackaprompt",
                "status": "pass",
                "resistance_score": 100,
                "attempt_count": 3,
                "blocked_attempt_count": 3,
                "difficultyLevel": 2,
                "nextDifficultyLevel": 4,
                "passStreak": 1,
                "cleanPass": True,
                "shouldEscalate": True,
                "nextAttemptBudget": 11,
                "targetResistanceScore": 98,
                "nextTactics": ["direct_policy_probe", "roleplay", "authority", "multi_turn"],
                "rawPayloadExported": False,
            }
        ]

        probe = run_adversarial_probe(
            preset,
            "Evaluate the next defensive benchmark after a clean pass.",
            history=history,
        )

        self.assertEqual(probe["escalationTarget"]["attemptBudget"], 11)
        self.assertGreaterEqual(probe["attempt_count"], 11)
        self.assertGreaterEqual(probe["generated_escalation_attempts"], 8)
        observed_tactics = {
            item["tactic"]
            for item in probe["attempts"]
            if item.get("generated_from_history")
        }
        self.assertIn("multi_turn", observed_tactics)
        self.assertEqual(probe["blocked_attempt_count"], probe["attempt_count"])

    def test_self_improvement_sampler_records_aggregate_red_team_history(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        temp_root = root / ".self_improvement_sampler_test"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir()
        try:
            (temp_root / "config").mkdir()
            shutil.copy2(
                root / "config" / "challenge_presets.json",
                temp_root / "config" / "challenge_presets.json",
            )
            sample = record_red_team_sample(
                temp_root,
                preset_name="hackaprompt",
                objective="Exercise defensive self-improvement escalation.",
            )
            evidence = build_self_improvement_evidence(temp_root, recorded_red_team_sample=sample)

            self.assertEqual(sample["schema"], "fluxio.self_improvement_red_team_sample.v1")
            self.assertFalse(sample["rawPayloadExported"])
            self.assertNotIn("attempts", sample["historyRow"])
            self.assertEqual(evidence["redTeam"]["historyRows"], 1)
            self.assertTrue(evidence["redTeam"]["aggregateOnly"])
            self.assertEqual(evidence["recordedRedTeamSample"]["preset"], "hackaprompt")
            plan = evidence["redTeam"]["nextBenchmarkPlan"]
            self.assertEqual(plan["schema"], "fluxio.red_team_next_benchmark_plan.v1")
            self.assertEqual(plan["preset"], "hackaprompt")
            self.assertEqual(plan["status"], "pending_follow_up")
            self.assertTrue(plan["aggregateOnly"])
            self.assertFalse(plan["rawPayloadExport"])
            self.assertIn("sample:self-improvement-red-team", plan["command"]["shell"])
            self.assertIn("--preset", plan["command"]["argv"])
            self.assertIn("red_team_next_benchmark", evidence["selfImprovementActions"][0]["kind"])
        finally:
            shutil.rmtree(temp_root)

    def test_self_improvement_sampler_marks_previous_escalation_target_satisfied(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        temp_root = root / ".self_improvement_escalation_test"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir()
        try:
            (temp_root / "config").mkdir()
            shutil.copy2(
                root / "config" / "challenge_presets.json",
                temp_root / "config" / "challenge_presets.json",
            )
            control_dir = temp_root / ".agent_control"
            control_dir.mkdir()
            (control_dir / "red_team_escalation_history.jsonl").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.red_team_escalation_history.v1",
                        "recordedAt": "2026-05-28T00:00:00+00:00",
                        "preset": "hackaprompt",
                        "status": "pass",
                        "resistance_score": 100,
                        "attempt_count": 3,
                        "blocked_attempt_count": 3,
                        "difficultyLevel": 2,
                        "nextDifficultyLevel": 3,
                        "passStreak": 1,
                        "cleanPass": True,
                        "shouldEscalate": True,
                        "nextAttemptBudget": 9,
                        "targetResistanceScore": 98,
                        "nextTactics": ["direct_policy_probe", "roleplay", "authority"],
                        "rawPayloadExported": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            sample = record_red_team_sample(
                temp_root,
                preset_name="hackaprompt",
                objective="Run the harder follow-up red-team benchmark.",
            )
            evidence = build_self_improvement_evidence(temp_root, recorded_red_team_sample=sample)

            self.assertGreaterEqual(sample["historyRow"]["attempt_count"], 9)
            self.assertEqual(sample["escalationTarget"]["attemptBudget"], 9)
            audit = evidence["redTeam"]["escalationAudit"]
            self.assertEqual(audit["status"], "advancing")
            self.assertEqual(audit["pendingTargets"], 1)
            self.assertEqual(audit["satisfiedTargets"], 1)
            self.assertEqual(audit["targets"][0]["status"], "satisfied")
            plan = evidence["redTeam"]["nextBenchmarkPlan"]
            self.assertEqual(plan["status"], "pending_follow_up")
            self.assertGreaterEqual(plan["attemptBudget"], sample["historyRow"]["attempt_count"])
            self.assertGreater(sample["generatedEscalationAttempts"], 0)
            self.assertIn("Run hackaprompt at", plan["command"]["shell"])
            self.assertIn(plan["difficultyLabel"], plan["command"]["shell"])
        finally:
            shutil.rmtree(temp_root)

    def test_red_team_loop_consumes_live_audit_history_tail_for_harder_follow_up(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        temp_root = root / ".self_improvement_live_red_team_loop_test"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir()
        try:
            (temp_root / "config").mkdir()
            shutil.copy2(
                root / "config" / "challenge_presets.json",
                temp_root / "config" / "challenge_presets.json",
            )
            live_audit_dir = (
                temp_root
                / ".agent_control"
                / "release_artifacts"
                / "latest"
                / "live_nas_system_audit"
            )
            live_audit_dir.mkdir(parents=True)
            live_row = {
                "schema": "fluxio.red_team_escalation_history.v1",
                "recordedAt": "2026-05-29T00:00:00+00:00",
                "preset": "hackaprompt",
                "status": "pass",
                "resistance_score": 100,
                "attempt_count": 7,
                "blocked_attempt_count": 7,
                "difficultyLevel": 3,
                "nextDifficultyLevel": 4,
                "passStreak": 2,
                "cleanPass": True,
                "shouldEscalate": True,
                "nextAttemptBudget": 12,
                "targetResistanceScore": 98,
                "nextTactics": ["direct_policy_probe", "roleplay", "authority", "multi_turn"],
                "rawPayloadExported": False,
            }
            (live_audit_dir / "live_nas_system_audit_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_nas_system_audit_snapshot.v1",
                        "ok": True,
                        "checkedAt": "2026-05-30T00:00:00+00:00",
                        "maxAgeSeconds": 999999999,
                        "audit": {
                            "redTeamEscalationEvidence": {"history": [live_row]},
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = advance_red_team_loop(temp_root, max_steps=1, write=True)

            self.assertEqual(result["completedSteps"], 1)
            self.assertEqual(result["steps"][0]["source"], "live_nas_system_audit")
            self.assertEqual(result["steps"][0]["seedHistoryRows"], 1)
            self.assertGreaterEqual(result["steps"][0]["recordedAttemptCount"], 12)
            self.assertEqual(
                result["latestRedTeam"]["escalationAudit"]["satisfiedTargets"],
                1,
            )
            receipt = record_watchdog_cadence_receipt(temp_root, result)
            watchdog_latest = temp_root / ".agent_control" / "self_improvement_evidence" / "watchdog_latest.json"
            watchdog_history = temp_root / ".agent_control" / "self_improvement_evidence" / "watchdog_history.jsonl"
            self.assertEqual(receipt["schema"], WATCHDOG_CADENCE_SCHEMA)
            self.assertEqual(receipt["status"], "completed")
            self.assertEqual(receipt["completedSteps"], 1)
            self.assertEqual(receipt["latestHistoryRows"], result["latestRedTeam"]["historyRows"])
            self.assertEqual(receipt["historyIndex"], 1)
            self.assertTrue(watchdog_latest.exists())
            self.assertTrue(watchdog_history.exists())
            self.assertEqual(
                json.loads(watchdog_latest.read_text(encoding="utf-8"))["schema"],
                WATCHDOG_CADENCE_SCHEMA,
            )
            self.assertIn(WATCHDOG_CADENCE_SCHEMA, watchdog_history.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(temp_root)

    def test_self_improvement_evidence_uses_operator_proven_live_route_trust(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        temp_root = root / ".self_improvement_live_route_trust_test"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir()
        try:
            control_dir = temp_root / ".agent_control"
            control_dir.mkdir()
            (control_dir / "missions.json").write_text(
                json.dumps(
                    [
                        {
                            "mission_id": "mission_low_value_f1_a",
                            "objective": "Build an F1 telemetry analytics report",
                            "state": {
                                "operator_value_feedback": {
                                    "score": 35,
                                    "outcome": "not_useful",
                                    "trustSignal": "deprioritize",
                                }
                            },
                        },
                        {
                            "mission_id": "mission_low_value_f1_b",
                            "objective": "Formula 1 lap time dashboard analytics",
                            "state": {
                                "operator_value_feedback": {
                                    "score": 42,
                                    "outcome": "not_useful",
                                    "trustSignal": "deprioritize",
                                }
                            },
                        },
                    ]
                ),
                encoding="utf-8",
            )
            live_audit_dir = control_dir / "release_artifacts" / "latest" / "live_nas_system_audit"
            live_audit_dir.mkdir(parents=True)
            (live_audit_dir / "live_nas_system_audit_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_nas_system_audit_snapshot.v1",
                        "ok": True,
                        "checkedAt": "2026-05-29T11:33:17+00:00",
                        "maxAgeSeconds": 999999999,
                        "audit": {
                            "routeTrustMaturity": {
                                "schema": "fluxio.operator_confidence_calibration.v1",
                                "status": "operator_proven",
                                "operatorConfidenceScore": 92,
                                "taskCount": 6,
                                "provenTaskCount": 6,
                                "samplingTaskCount": 0,
                                "missingOperatorValueSamples": 0,
                                "nextAction": "All tracked task categories have enough value-scored route and skill trust samples.",
                            },
                            "redTeamEscalationEvidence": {
                                "history": [
                                    {
                                        "schema": "fluxio.red_team_escalation_history.v1",
                                        "recordedAt": "2026-05-29T00:00:00+00:00",
                                        "preset": "hackaprompt",
                                        "status": "pass",
                                        "resistance_score": 100,
                                        "attempt_count": 23,
                                        "blocked_attempt_count": 23,
                                        "difficultyLevel": 5,
                                        "nextDifficultyLevel": 5,
                                        "passStreak": 7,
                                        "cleanPass": True,
                                        "shouldEscalate": True,
                                        "nextAttemptBudget": 25,
                                        "targetResistanceScore": 98,
                                        "nextTactics": ["direct_policy_probe", "roleplay"],
                                        "rawPayloadExported": False,
                                    }
                                ]
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            evidence = build_self_improvement_evidence(temp_root)
            route_trust = evidence["operatorValueRouteTrust"]

            self.assertEqual(route_trust["source"], "live_nas_system_audit")
            self.assertEqual(route_trust["provenTaskCount"], 6)
            self.assertEqual(route_trust["samplingTaskCount"], 0)
            self.assertEqual(route_trust["missingTaskCategories"], [])
            self.assertEqual(evidence["selfImprovementActions"][1]["status"], "proven")
            self.assertEqual(evidence["operatorValueSamplingPlan"]["status"], "proven")
            self.assertFalse(evidence["operatorValueSamplingPlan"]["canLaunch"])
            self.assertEqual(evidence["redTeam"]["source"], "live_nas_system_audit")
        finally:
            shutil.rmtree(temp_root)

    def test_self_improvement_sampling_plan_blocks_when_nas_storage_is_critical(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        temp_root = root / ".self_improvement_sampling_plan_storage_test"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir()
        try:
            control_dir = temp_root / ".agent_control"
            control_dir.mkdir()
            (control_dir / "missions.json").write_text(
                json.dumps(
                    [
                        {
                            "mission_id": "mission_low_value_f1_a",
                            "objective": "Build an F1 telemetry analytics report",
                            "state": {
                                "operator_value_feedback": {
                                    "score": 35,
                                    "outcome": "not_useful",
                                    "trustSignal": "deprioritize",
                                }
                            },
                        },
                        {
                            "mission_id": "mission_low_value_f1_b",
                            "objective": "Formula 1 lap time dashboard analytics",
                            "state": {
                                "operator_value_feedback": {
                                    "score": 42,
                                    "outcome": "not_useful",
                                    "trustSignal": "deprioritize",
                                }
                            },
                        },
                    ]
                ),
                encoding="utf-8",
            )
            (control_dir / "nas_storage_pressure_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.nas_storage_pressure.v1",
                        "status": "critical",
                        "source": "bounded_ssh_timeout",
                        "probeTimedOut": True,
                        "checkedAt": "2026-05-31T23:36:49+00:00",
                        "nextAction": "Do not start NAS write-heavy missions until a bounded probe returns.",
                    }
                ),
                encoding="utf-8",
            )

            evidence = build_self_improvement_evidence(temp_root)
            plan = evidence["operatorValueSamplingPlan"]

            self.assertEqual(plan["schema"], "fluxio.operator_value_sampling_plan.v1")
            self.assertEqual(plan["status"], "blocked_by_nas_storage")
            self.assertFalse(plan["canLaunch"])
            self.assertEqual(plan["nasStorageGate"]["source"], "bounded_ssh_timeout")
            self.assertGreaterEqual(len(plan["sampleRows"]), 6)
            self.assertIn("frontend_design", plan["missingTaskCategories"])
            self.assertIn("data_f1_analytics", plan["missingTaskCategories"])
            f1_row = next(row for row in plan["sampleRows"] if row["taskType"] == "data_f1_analytics")
            self.assertEqual(f1_row["promoteCount"], 0)
            self.assertEqual(f1_row["deprioritizeCount"], 2)
            self.assertIn("--dry-run", plan["dryRunCommand"]["argv"])
            self.assertEqual(plan["launchCommand"], {})
            self.assertEqual(evidence["selfImprovementActions"][1]["status"], "blocked_by_nas_storage")
            self.assertIn("NAS storage", evidence["nextAction"])
        finally:
            shutil.rmtree(temp_root)


if __name__ == "__main__":
    unittest.main()
