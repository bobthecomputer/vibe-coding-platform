from __future__ import annotations

import pathlib
import shutil
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.challenge_presets import ChallengePresetRegistry
from grant_agent.demo_runner import compare_training, export_report_bundle, run_adversarial_probe, summarize_run


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


if __name__ == "__main__":
    unittest.main()
