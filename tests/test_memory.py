from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.memory import MemoryStore, ingest_state_into_memory


class MemoryTests(unittest.TestCase):
    def test_add_and_search_memory(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        path = root / ".agent_memory_test.json"
        if path.exists():
            path.unlink()

        store = MemoryStore(path)
        store.add(
            source_session_id="session_x",
            objective="Build verification loop",
            content="Decision: always run tests after edits",
            tags=["decision", "verify"],
            kind="decision",
        )
        matches = store.search("verification tests", limit=5)
        self.assertGreaterEqual(len(matches), 1)

    def test_ingest_state(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        path = root / ".agent_memory_test.json"
        if path.exists():
            path.unlink()

        store = MemoryStore(path)
        state = {
            "objective": "Improve safety",
            "decisions": ["Use budget caps", "Block risky commands"],
            "risks": ["Potential context overflow"],
            "next_actions": ["Add replay command"],
        }
        inserted = ingest_state_into_memory(store, "session_y", state)
        self.assertGreaterEqual(len(inserted), 3)


if __name__ == "__main__":
    unittest.main()
