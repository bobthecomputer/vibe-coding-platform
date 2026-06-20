from __future__ import annotations

import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = (
    ROOT
    / "artifacts"
    / "red-team"
    / "worker-f-jbheaven-safe-scenario-20260621"
)


class WorkerFRedTeamArtifactTests(unittest.TestCase):
    def test_artifact_set_has_required_files_and_cross_references(self) -> None:
        expected_files = {
            "README.md",
            "scenario.json",
            "probes.jsonl",
            "rubric.json",
            "transcript_schema.json",
            "sample_transcript.json",
            "artifacts_index.json",
        }

        for filename in expected_files:
            self.assertTrue((ARTIFACT_ROOT / filename).exists(), filename)

        scenario = json.loads((ARTIFACT_ROOT / "scenario.json").read_text())
        probes = [
            json.loads(line)
            for line in (ARTIFACT_ROOT / "probes.jsonl").read_text().splitlines()
            if line.strip()
        ]
        rubric = json.loads((ARTIFACT_ROOT / "rubric.json").read_text())

        self.assertEqual(
            scenario["scenario_id"], "worker-f-jbheaven-safe-scenario-20260621"
        )
        self.assertFalse(scenario["model_route"]["live_model_calls"])
        self.assertFalse(scenario["safety_contract"]["real_targets"])
        self.assertFalse(scenario["safety_contract"]["harmful_instructions"])
        self.assertEqual(set(scenario["probe_inventory"]), {p["probe_id"] for p in probes})
        self.assertEqual(rubric["thresholds"]["pass"], 85)

    def test_probes_stay_fictional_and_safe_for_artifact_use(self) -> None:
        probes = [
            json.loads(line)
            for line in (ARTIFACT_ROOT / "probes.jsonl").read_text().splitlines()
            if line.strip()
        ]

        required_families = {
            "refusal_quality",
            "false_data_robustness",
            "prompt_injection_resistance",
            "harmless_dual_use_boundary",
            "transcript_integrity",
        }
        self.assertTrue(required_families.issubset({p["family"] for p in probes}))

        for probe in probes:
            self.assertIn(
                probe["authorization_label"],
                {
                    "authorized_lab_only",
                    "synthetic_data_only",
                    "visible_transcript_only",
                    "fictional_targets_only",
                    "human_review_required",
                },
            )
            self.assertNotIn("http://", probe["fake_target"])
            self.assertNotIn("https://", probe["fake_target"])
            self.assertNotRegex(probe["fake_target"], r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
            self.assertGreaterEqual(len(probe["expected_safe_behavior"]), 3)
            self.assertIn("visible_response", probe["transcript_requirements"])

            safe_expectations = " ".join(probe["expected_safe_behavior"]).lower()
            self.assertNotIn("step-by-step", safe_expectations)
            self.assertNotIn("payload", safe_expectations)
            self.assertTrue(
                any(
                    signal in safe_expectations
                    for signal in (
                        "refuse",
                        "avoid",
                        "unverified",
                        "untrusted",
                        "authorized",
                        "omitted",
                    )
                ),
                probe["probe_id"],
            )

    def test_sample_transcript_matches_required_proof_contract(self) -> None:
        schema = json.loads((ARTIFACT_ROOT / "transcript_schema.json").read_text())
        sample = json.loads((ARTIFACT_ROOT / "sample_transcript.json").read_text())

        for field in schema["required"]:
            self.assertIn(field, sample)

        self.assertEqual(sample["scenario_id"], schema["properties"]["scenario_id"]["const"])
        self.assertFalse(sample["target_boundary"]["real_targets_used"])
        self.assertFalse(sample["target_boundary"]["network_activity"])
        self.assertFalse(sample["proof_summary"]["live_model_calls"])
        self.assertFalse(sample["proof_summary"]["harmful_instructions_included"])
        self.assertTrue(
            all(result["hidden_reasoning_omitted"] for result in sample["probe_results"])
        )


if __name__ == "__main__":
    unittest.main()
