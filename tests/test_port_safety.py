from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from grant_agent.port_safety import reserve_port_probe


class PortSafetyTests(unittest.TestCase):
    def test_reserve_port_probe_blocks_immediate_repeat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = reserve_port_probe(
                host="100.125.54.118",
                port=22,
                purpose="nas-ssh",
                identity="test-agent",
                root=root,
                cooldown_seconds=30,
            )
            second = reserve_port_probe(
                host="100.125.54.118",
                port=22,
                purpose="nas-ssh",
                identity="test-agent",
                root=root,
                cooldown_seconds=30,
            )

            self.assertTrue(first["allowed"])
            self.assertFalse(second["allowed"])
            self.assertEqual(second["reason"], "cooldown")
            self.assertGreaterEqual(second["retryAfterSeconds"], 1)

    def test_reserve_port_probe_rate_limits_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for _ in range(2):
                result = reserve_port_probe(
                    host="nas.local",
                    port=22,
                    purpose="nas-ssh",
                    identity="test-agent",
                    root=root,
                    cooldown_seconds=0,
                    window_seconds=60,
                    max_attempts=2,
                )
                self.assertTrue(result["allowed"])

            blocked = reserve_port_probe(
                host="nas.local",
                port=22,
                purpose="nas-ssh",
                identity="test-agent",
                root=root,
                cooldown_seconds=0,
                window_seconds=60,
                max_attempts=2,
            )

            self.assertFalse(blocked["allowed"])
            self.assertEqual(blocked["reason"], "rate_limited")

    def test_force_bypasses_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reserve_port_probe(
                host="nas.local",
                port=22,
                purpose="nas-ssh",
                identity="test-agent",
                root=root,
                cooldown_seconds=30,
            )
            forced = reserve_port_probe(
                host="nas.local",
                port=22,
                purpose="nas-ssh",
                identity="test-agent",
                root=root,
                cooldown_seconds=30,
                force=True,
            )

            self.assertTrue(forced["allowed"])


if __name__ == "__main__":
    unittest.main()
