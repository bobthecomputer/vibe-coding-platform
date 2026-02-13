from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.feature_suggester import suggest_features_from_text


class FeatureSuggestionTests(unittest.TestCase):
    def test_returns_ranked_suggestions(self) -> None:
        text = "We need better memory, context continuity, and budget control for model routing."
        suggestions = suggest_features_from_text(text, top_k=4)
        self.assertGreaterEqual(len(suggestions), 2)
        ids = [item["id"] for item in suggestions]
        self.assertIn("memory_long_horizon", ids)


if __name__ == "__main__":
    unittest.main()
