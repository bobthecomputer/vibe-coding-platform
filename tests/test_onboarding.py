from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.onboarding import detect_onboarding_status


class OnboardingTests(unittest.TestCase):
    @mock.patch("grant_agent.onboarding.detect_wsl_status")
    @mock.patch("grant_agent.onboarding._command_version")
    def test_detect_onboarding_status_collects_checks(
        self,
        command_version: mock.Mock,
        detect_wsl_status: mock.Mock,
    ) -> None:
        detect_wsl_status.return_value = {
            "required": True,
            "installed": True,
            "default_version": 2,
            "details": "WSL2 ready",
        }
        command_version.side_effect = [
            {"installed": True, "command": "node", "version": "v22", "details": "ok"},
            {"installed": True, "command": "python", "version": "3.13", "details": "ok"},
            {"installed": True, "command": "uv", "version": "0.9", "details": "ok"},
            {"installed": True, "command": "openclaw", "version": "2026.2.15", "details": "ok"},
            {"installed": False, "command": None, "version": None, "details": "missing"},
            {"installed": True, "command": "node", "version": "v22", "details": "ok"},
            {"installed": True, "command": "python", "version": "3.13", "details": "ok"},
            {"installed": True, "command": "uv", "version": "0.9", "details": "ok"},
            {"installed": True, "command": "openclaw", "version": "2026.2.15", "details": "ok"},
            {"installed": False, "command": None, "version": None, "details": "missing"},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "profiles.json").write_text(
                """
                {
                  "default_profile": "builder",
                  "profiles": {
                    "beginner": {"description": "Beginner", "ui": {"motion": "reduced"}, "agent": {"execution_scope": "isolated", "approval_mode": "strict", "explanation_depth": "high", "delegation_aggressiveness": "low"}},
                    "builder": {"description": "Builder", "ui": {"motion": "standard"}, "agent": {"execution_scope": "isolated", "approval_mode": "tiered", "explanation_depth": "medium", "delegation_aggressiveness": "balanced"}}
                  }
                }
                """,
                encoding="utf-8",
            )
            status = detect_onboarding_status(root)

        self.assertEqual(status["checks"]["node"]["version"], "v22")
        self.assertFalse(status["checks"]["hermes"]["installed"])
        self.assertIn("Install Hermes", status["nextActions"][0])
        self.assertIn("tutorial", status)
        self.assertIn("profileChoices", status)


if __name__ == "__main__":
    unittest.main()
