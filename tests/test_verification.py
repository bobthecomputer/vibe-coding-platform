from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.verification import VerificationRunner, detect_default_verification_commands


class VerificationTests(unittest.TestCase):
    def test_blocks_high_risk_command(self) -> None:
        runner = VerificationRunner()
        results = runner.run(["rm -rf /tmp/demo"], workdir=pathlib.Path.cwd())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "blocked")
        self.assertNotEqual(results[0].return_code, 0)

    def test_detect_default_commands(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        commands = detect_default_verification_commands(root)
        self.assertIn("python -m unittest discover -s tests", commands)


if __name__ == "__main__":
    unittest.main()
