from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest
from unittest import mock

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

    def test_timeout_is_reported_instead_of_raising(self) -> None:
        runner = VerificationRunner(default_timeout_seconds=1)
        timeout_error = subprocess.TimeoutExpired(
            cmd="python -m unittest discover -s tests",
            timeout=1,
            output="partial stdout",
            stderr="partial stderr",
        )
        with mock.patch("grant_agent.verification.subprocess.run", side_effect=timeout_error):
            results = runner.run(
                ["python -m unittest discover -s tests"],
                workdir=pathlib.Path.cwd(),
            )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "timeout")
        self.assertEqual(results[0].return_code, 124)
        self.assertIn("timed out", results[0].stderr.lower())


if __name__ == "__main__":
    unittest.main()
