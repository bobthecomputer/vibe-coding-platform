from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.context_manager import ContextWindowManager


class ContextManagerTests(unittest.TestCase):
    def test_status_transitions(self) -> None:
        manager = ContextWindowManager(max_tokens=100)
        manager.record("user", "a" * 120)  # ~30 tokens
        self.assertEqual(manager.status(), "ok")
        manager.record("assistant", "b" * 220)  # +55 => 85
        self.assertEqual(manager.status(), "rollover")

    def test_compaction_keeps_user_messages(self) -> None:
        manager = ContextWindowManager(max_tokens=100)
        manager.record("user", "Need feature X")
        manager.record("assistant", "I propose step one")
        compacted = manager.compact_window()
        self.assertEqual(compacted[0]["role"], "user")
        self.assertIn("compacted_context", compacted[-1]["content"])


if __name__ == "__main__":
    unittest.main()
