from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.challenge_presets import ChallengePresetRegistry


class ChallengePresetTests(unittest.TestCase):
    def test_registry_loads_requested_presets(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = ChallengePresetRegistry(root / "config" / "challenge_presets.json")
        names = registry.list_names()
        self.assertIn("gandalf", names)
        self.assertIn("hackaprompt", names)

    def test_selector_pick(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = ChallengePresetRegistry(root / "config" / "challenge_presets.json")
        preset = registry.get("gandalf")
        selectors = preset.pick_selectors("Need stronger secret leak resistance and refusal policy")
        self.assertGreaterEqual(len(selectors), 1)


if __name__ == "__main__":
    unittest.main()
