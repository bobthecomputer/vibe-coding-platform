from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.research import search_workspace


class ResearchTests(unittest.TestCase):
    def test_search_workspace_returns_matches(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        matches = search_workspace(root=root, query="AutonomousEngine", include_glob="src/**/*.py", max_results=10)
        self.assertGreaterEqual(len(matches), 1)


if __name__ == "__main__":
    unittest.main()
