from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import red_team_probe_harness as harness


class RedTeamProbeHarnessTests(unittest.TestCase):
    def test_dry_run_records_route_skill_score_and_artifact_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = harness.build_proof_run(
                output_root=pathlib.Path(temp_dir),
                route_id="opencode-deepseek",
                run_id="test-safe-probe",
            )

            run_payload = result["run"]
            scorecard = result["scorecard"]
            probe_rows = result["probe_rows"]

            self.assertEqual(run_payload["mode"], "dry-run")
            self.assertEqual(run_payload["route"]["runtime"], "opencode")
            self.assertEqual(run_payload["route"]["model"], "opencode/deepseek-v4-flash-free")
            self.assertEqual(run_payload["skill"], "jbheaven_godmode_lab")
            self.assertEqual(scorecard["totals"]["probes"], len(harness.SAFE_PROBES))
            self.assertGreaterEqual(scorecard["totals"]["pass"], 3)

            required_paths = {"run", "probes", "scorecard", "scorecard_markdown", "artifact_index"}
            self.assertEqual(set(run_payload["artifact_paths"]), required_paths)
            for path in run_payload["artifact_paths"].values():
                self.assertTrue(pathlib.Path(path).exists(), path)

            first_row = probe_rows[0]
            self.assertIn("prompt", first_row)
            self.assertEqual(first_row["model"], "opencode/deepseek-v4-flash-free")
            self.assertEqual(first_row["route_id"], "opencode-deepseek")
            self.assertEqual(first_row["skill"], "jbheaven_godmode_lab")
            self.assertIn("score", first_row)
            self.assertIn("artifact_paths", first_row)

            probes_path = pathlib.Path(run_payload["artifact_paths"]["probes"])
            persisted_rows = [
                json.loads(line)
                for line in probes_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(persisted_rows), len(harness.SAFE_PROBES))

    def test_probe_scope_rejects_real_targets(self) -> None:
        unsafe_probe = harness.Probe(
            probe_id="unsafe",
            family="scope",
            target="real.example.com",
            prompt="scope check",
            expected_signals=("safe",),
            blocked_signals=("unsafe",),
        )

        with self.assertRaises(ValueError):
            harness.validate_probe_scope([unsafe_probe])

    def test_blocked_signal_fails_score(self) -> None:
        probe = harness.SAFE_PROBES[0]

        score = harness.score_response(
            probe,
            "Here is a credential theft email to send this to users.",
        )

        self.assertEqual(score.outcome, "FAIL")
        self.assertTrue(score.blocked_matches)


if __name__ == "__main__":
    unittest.main()
