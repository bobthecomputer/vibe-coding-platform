from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.vibe_suggestions import build_vibe_next_steps, collect_repo_signals


class VibeSuggestionTests(unittest.TestCase):
    def test_build_vibe_next_steps(self) -> None:
        actions = build_vibe_next_steps(
            objective="Improve UI preview loop",
            run_state={"next_actions": ["Implement preview check"]},
            memory_hits=["mem_1"],
            repo_signals={"tests_count": 2, "docs_count": 1, "has_pyproject": True, "has_readme": True},
            limit=6,
        )
        self.assertGreaterEqual(len(actions), 3)
        self.assertIn("Finish remaining plan step", actions[0])

    def test_collect_repo_signals(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        signals = collect_repo_signals(root)
        self.assertIn("tests_count", signals)
        self.assertIn("docs_count", signals)


if __name__ == "__main__":
    unittest.main()
