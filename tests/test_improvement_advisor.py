from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.improvement_advisor import recommend_improvements


class ImprovementAdvisorTests(unittest.TestCase):
    def test_recommendations_generated(self) -> None:
        metrics = {
            "total_sessions": 10,
            "sessions_with_handoff": 6,
            "verification_failures": 2,
            "blocked_commands": 1,
            "runs_with_memory_writes": 2,
            "runs_with_doc_evidence": 8,
        }
        bundles = [
            {"resistance_score": 60},
            {"resistance_score": 70},
        ]
        recs = recommend_improvements(metrics, bundles, top_k=5)
        self.assertGreaterEqual(len(recs), 3)
        priorities = [item["priority"] for item in recs]
        self.assertIn("high", priorities)


if __name__ == "__main__":
    unittest.main()
