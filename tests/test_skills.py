from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.skills import SkillRegistry


class SkillRegistryTests(unittest.TestCase):
    def test_retrieves_relevant_skill(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = SkillRegistry(root / "config" / "skills.json")
        skills = registry.retrieve("please run tests and build verification")
        names = [skill.name for skill in skills]
        self.assertIn("run_verification_suite", names)

    def test_fallback_returns_defaults_when_no_overlap(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = SkillRegistry(root / "config" / "skills.json")
        skills = registry.retrieve("zzzz unmatched tokens", top_k=2)
        self.assertEqual(len(skills), 2)


if __name__ == "__main__":
    unittest.main()
