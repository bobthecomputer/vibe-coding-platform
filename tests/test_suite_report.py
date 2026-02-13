from __future__ import annotations

import pathlib
import shutil
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.suite_report import build_suite_summary, write_suite_artifacts


class SuiteReportTests(unittest.TestCase):
    def test_build_and_write_suite_artifacts(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        out = root / ".suite_report_test"
        if out.exists():
            shutil.rmtree(out)

        results = [
            {"preset": "gandalf", "training_comparison": {"score_delta": 3}, "probe": {"status": "pass", "resistance_score": 90}},
            {
                "preset": "hackaprompt",
                "training_comparison": {"score_delta": 1},
                "probe": {"status": "needs_hardening", "resistance_score": 67},
            },
        ]
        summary = build_suite_summary(results)
        self.assertEqual(summary["preset_count"], 2)
        artifacts = write_suite_artifacts(out, "suite_x", results, summary)
        self.assertTrue(pathlib.Path(artifacts["suite_json_path"]).exists())
        self.assertTrue(pathlib.Path(artifacts["suite_report_path"]).exists())


if __name__ == "__main__":
    unittest.main()
