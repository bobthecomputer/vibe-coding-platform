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

    def test_packaged_catalog_includes_curated_design_and_browser_skills(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = SkillRegistry(root / "config" / "skills.json")
        names = {skill.name for skill in registry.skills}

        self.assertIn("browser_use_local_inspection", names)
        self.assertIn("leon_lin_design_taste", names)
        self.assertIn("high_end_visual_design", names)
        self.assertIn("gpt_taste_frontend_motion", names)
        self.assertIn("frontend_image_direction", names)
        self.assertIn("ui_refactor_expert", names)
        self.assertIn("frontend_taste_director", names)
        self.assertIn("jbheaven_godmode_lab", names)
        self.assertIn("hermes_skill_packager", names)
        self.assertIn("runtime_loop_supervisor", names)
        self.assertIn("voice_accessibility_operator", names)

    def test_retrieves_jbheaven_godmode_skill_for_red_team_objectives(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = SkillRegistry(root / "config" / "skills.json")
        skills = registry.retrieve(
            "run a JBHEAVEN Godmode G0DM0D3 red-team proof with OpenCode transcript",
            top_k=4,
        )
        names = [skill.name for skill in skills]

        self.assertIn("jbheaven_godmode_lab", names)

    def test_retrieves_voice_accessibility_skill_for_low_typing_objectives(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = SkillRegistry(root / "config" / "skills.json")
        skills = registry.retrieve(
            "improve voice dictation accessibility keyboard screen reader low typing composer",
            top_k=4,
        )
        names = [skill.name for skill in skills]

        self.assertIn("voice_accessibility_operator", names)


if __name__ == "__main__":
    unittest.main()
