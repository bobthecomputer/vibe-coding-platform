from __future__ import annotations

import json
import pathlib
import shutil
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.dashboard import load_proof_bundles, write_proof_dashboard


class DashboardTests(unittest.TestCase):
    def test_load_and_write_dashboard(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        bundle_root = root / ".demo_dashboard_test"
        if bundle_root.exists():
            shutil.rmtree(bundle_root)

        first = bundle_root / "bundle_001_demo"
        second = bundle_root / "bundle_002_demo"
        first.mkdir(parents=True, exist_ok=True)
        second.mkdir(parents=True, exist_ok=True)

        payload1 = {
            "generated_at": "2026-02-09T00:00:00Z",
            "preset": {"name": "gandalf", "description": "d"},
            "training_before": {"completion_score": 50},
            "training_after": {"completion_score": 60},
            "training_comparison": {"score_delta": 10},
            "probe": {"status": "pass", "resistance_score": 90},
            "top_findings": ["A"],
        }
        payload2 = {
            "generated_at": "2026-02-09T01:00:00Z",
            "preset": {"name": "hackaprompt", "description": "d"},
            "training_before": {"completion_score": 45},
            "training_after": {"completion_score": 48},
            "training_comparison": {"score_delta": 3},
            "probe": {"status": "needs_hardening", "resistance_score": 67},
            "top_findings": ["B"],
        }
        (first / "proof_payload.json").write_text(json.dumps(payload1), encoding="utf-8")
        (second / "proof_payload.json").write_text(json.dumps(payload2), encoding="utf-8")

        bundles = load_proof_bundles(bundle_root)
        self.assertEqual(len(bundles), 2)

        output = bundle_root / "proof_dashboard.html"
        written = write_proof_dashboard(bundle_root, output)
        self.assertTrue(written.exists())
        html = written.read_text(encoding="utf-8")
        self.assertIn("Proof Report Dashboard", html)
        self.assertIn("gandalf", html)
        self.assertIn("trendPanel", html)
        self.assertIn("comparatorPanel", html)


if __name__ == "__main__":
    unittest.main()
