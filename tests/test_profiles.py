from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.profiles import ProfileRegistry


class ProfileTests(unittest.TestCase):
    def test_load_default_profile(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = ProfileRegistry(root / "config" / "profiles.json")
        resolved = registry.resolve(None, root)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.name, registry.default_profile)
        self.assertGreaterEqual(resolved.agent.parallel_agents or 0, 1)

    def test_resolve_named_profile(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = ProfileRegistry(root / "config" / "profiles.json")
        profile = registry.resolve("minimal_focus", root)
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.name, "minimal_focus")
        self.assertEqual(profile.agent.merge_policy, "risk_averse")


if __name__ == "__main__":
    unittest.main()
