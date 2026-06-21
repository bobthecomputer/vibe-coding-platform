from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import runtime_lane_proof_harness as harness
from grant_agent.runtimes import runtime_adapter_map


class RuntimeLaneProofHarnessTests(unittest.TestCase):
    def test_builds_hermes_openclaw_fused_proof_without_opencode_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = harness.build_proof(
                output_root=pathlib.Path(temp_dir),
                run_id="test-runtime-lane-proof",
            )

        lanes = {lane["runtimeId"]: lane for lane in payload["lanes"]}
        self.assertEqual(set(lanes), {"openclaw", "hermes"})
        self.assertNotIn("opencode", runtime_adapter_map())
        self.assertNotIn("opencode", payload["fusedRuntime"]["registeredRuntimeAdapters"])
        self.assertEqual(payload["proofType"], "route_contract_proof")
        self.assertFalse(payload["proofTruth"]["liveRuntimeExecution"])
        self.assertIn("route contract construction", payload["proofTruth"]["proves"])
        self.assertIn("a live runtime process completed", payload["proofTruth"]["doesNotProve"])
        self.assertFalse(payload["safetyContract"]["liveRuntimeExecution"])
        self.assertEqual(payload["safetyContract"]["proofType"], "route_contract_proof")

        self.assertIn("openclaw agent", lanes["openclaw"]["launchCommand"])
        self.assertIn("--json", lanes["openclaw"]["launchCommand"])
        self.assertEqual(
            lanes["openclaw"]["readiness"]["status"],
            "contract_ready_live_unverified",
        )
        self.assertTrue(lanes["openclaw"]["readiness"]["promotionBlocked"])
        self.assertGreaterEqual(lanes["openclaw"]["readiness"]["blockingGateCount"], 1)
        self.assertIn(
            "OpenClaw CLI available",
            {gate["label"] for gate in lanes["openclaw"]["readiness"]["gates"]},
        )
        self.assertEqual(
            lanes["openclaw"]["routeContract"]["canonical_model_id"],
            "openai-codex/gpt-5.4-mini",
        )

        self.assertIn("hermes chat", lanes["hermes"]["launchCommand"])
        self.assertIn("--provider minimax", lanes["hermes"]["launchCommand"])
        self.assertEqual(
            lanes["hermes"]["readiness"]["status"],
            "contract_ready_live_unverified",
        )
        self.assertTrue(lanes["hermes"]["readiness"]["promotionBlocked"])
        self.assertGreaterEqual(lanes["hermes"]["readiness"]["blockingGateCount"], 1)
        self.assertIn(
            "Hermes CLI available",
            {gate["label"] for gate in lanes["hermes"]["readiness"]["gates"]},
        )
        self.assertEqual(lanes["hermes"]["routeContract"]["provider"], "minimax")

        self.assertEqual(
            payload["fusedRuntime"]["role"],
            "supervisor_not_runtime_adapter",
        )
        self.assertEqual(
            payload["fusedRuntime"]["readinessSummary"]["overallStatus"],
            "contract_ready_live_unverified",
        )
        self.assertTrue(payload["fusedRuntime"]["readinessSummary"]["promotionBlocked"])
        self.assertGreaterEqual(
            payload["fusedRuntime"]["readinessSummary"]["blockingGateCount"],
            2,
        )
        self.assertFalse(payload["fusedRuntime"]["runtimeAdapterAdded"])
        self.assertTrue(
            all(payload["fusedRuntime"]["delegatedSessionFieldsPresent"].values())
        )
        self.assertTrue(
            payload["skillVisibility"]["requiredSkills"]["jbheaven_godmode_lab"]
        )
        self.assertTrue(
            payload["skillVisibility"]["requiredSkills"]["runtime_loop_supervisor"]
        )
        self.assertEqual(
            payload["routeScorecard"]["schemaVersion"],
            "benchmark-board-route-scorecard/v1",
        )
        candidates = {
            item["runtimeLane"]["laneId"]: item
            for item in payload["routeScorecard"]["candidates"]
        }
        self.assertEqual(set(candidates), {"openclaw", "hermes"})
        self.assertEqual(candidates["openclaw"]["providerRoute"]["provider"], "openai")
        self.assertEqual(candidates["hermes"]["providerRoute"]["provider"], "minimax")
        for runtime_id, candidate in candidates.items():
            self.assertNotEqual(
                candidate["providerRoute"]["provider"],
                candidate["runtimeLane"]["laneId"],
                runtime_id,
            )
            self.assertFalse(candidate["runtimeLane"]["runtimeAdapterAdded"])
            self.assertEqual(candidate["verifierProof"]["proofType"], "route_contract_proof")
            self.assertFalse(candidate["verifierProof"]["liveRuntimeExecution"])
            self.assertGreaterEqual(len(candidate["readinessGates"]), 3)
            self.assertTrue(
                any(gate["blocksPromotion"] for gate in candidate["readinessGates"])
            )

    def test_writes_artifact_index_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = harness.build_proof(
                output_root=pathlib.Path(temp_dir),
                run_id="test-runtime-lane-proof",
            )

            for path in payload["artifactPaths"].values():
                self.assertTrue(pathlib.Path(path).exists(), path)

            markdown = pathlib.Path(payload["artifactPaths"]["markdown"]).read_text(
                encoding="utf-8"
            )
            self.assertIn("Hermes/OpenClaw Runtime Lane Proof", markdown)
            self.assertIn("Runtime adapter added: `False`", markdown)
            self.assertIn("Proof type: `route_contract_proof`", markdown)
            self.assertIn("Readiness And Recovery", markdown)
            self.assertIn("contract_ready_live_unverified", markdown)
            self.assertIn("Promotion blocked: `True`", markdown)

            scorecard = json.loads(
                pathlib.Path(payload["artifactPaths"]["route_scorecard"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                scorecard["schemaVersion"],
                "benchmark-board-route-scorecard/v1",
            )
            self.assertEqual(len(scorecard["candidates"]), 2)


if __name__ == "__main__":
    unittest.main()
