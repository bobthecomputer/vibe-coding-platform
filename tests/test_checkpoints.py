from __future__ import annotations

import pathlib
import shutil
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.checkpoints import CheckpointStore
from grant_agent.models import RunState


class CheckpointTests(unittest.TestCase):
    def test_checkpoint_save_and_load(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        session = root / ".checkpoint_test" / "session_x"
        if session.parent.exists():
            shutil.rmtree(session.parent)
        session.mkdir(parents=True, exist_ok=True)

        store = CheckpointStore(session)
        state = RunState(
            objective="demo",
            plan_steps=["a", "b"],
            acceptance_checks=["tests"],
            completed_steps=["a"],
            next_actions=["b"],
        )
        path = store.save(
            session_id="session_x",
            iteration=1,
            run_state=state,
            context={"usage_ratio": 0.2, "status": "ok"},
            doc_sources=["README.md"],
        )
        loaded = CheckpointStore.load(path)
        self.assertEqual(loaded["checkpoint_id"], "ckpt_001")
        self.assertEqual(loaded["session_id"], "session_x")
        self.assertEqual(loaded["state"]["objective"], "demo")


if __name__ == "__main__":
    unittest.main()
