from __future__ import annotations

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

        self.assertIn("openclaw agent", lanes["openclaw"]["launchCommand"])
        self.assertIn("--json", lanes["openclaw"]["launchCommand"])
        self.assertEqual(
            lanes["openclaw"]["routeContract"]["canonical_model_id"],
            "openai-codex/gpt-5.4-mini",
        )

        self.assertIn("hermes chat", lanes["hermes"]["launchCommand"])
        self.assertIn("--provider minimax", lanes["hermes"]["launchCommand"])
        self.assertEqual(lanes["hermes"]["routeContract"]["provider"], "minimax")

        self.assertEqual(
            payload["fusedRuntime"]["role"],
            "supervisor_not_runtime_adapter",
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


if __name__ == "__main__":
    unittest.main()
