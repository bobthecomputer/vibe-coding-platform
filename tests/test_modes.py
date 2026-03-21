from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.modes import ModeRegistry


class ModeTests(unittest.TestCase):
    def test_load_balanced_mode(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = ModeRegistry(root / "config" / "modes.json")
        mode = registry.get("balanced")
        self.assertEqual(mode.persona, "balanced_builder")
        self.assertGreater(mode.max_tokens, 1000)
        self.assertEqual(mode.merge_policy, "best_score")

    def test_load_swarms_mode_parallel_workers(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = ModeRegistry(root / "config" / "modes.json")
        mode = registry.get("swarms")
        self.assertEqual(mode.parallel_agents, 3)
        self.assertIn("parallel", mode.description.lower())
        self.assertEqual(mode.merge_policy, "consensus")


if __name__ == "__main__":
    unittest.main()
