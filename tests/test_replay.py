from __future__ import annotations

import json
import pathlib
import shutil
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.replay import build_lineage_timeline


class ReplayTests(unittest.TestCase):
    def test_build_lineage_timeline(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        base = root / ".agent_runs_replay"
        if base.exists():
            shutil.rmtree(base)
        first = base / "session_aaa"
        second = base / "session_bbb"
        first.mkdir(parents=True, exist_ok=True)
        second.mkdir(parents=True, exist_ok=True)

        (first / "timeline.jsonl").write_text(
            json.dumps({"kind": "preflight", "message": "ok"}) + "\n",
            encoding="utf-8",
        )
        (second / "timeline.jsonl").write_text(
            json.dumps({"kind": "resume", "message": "continued"}) + "\n",
            encoding="utf-8",
        )

        events = build_lineage_timeline(base, ["session_aaa", "session_bbb"])
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["session_id"], "session_aaa")
        self.assertEqual(events[1]["session_id"], "session_bbb")


if __name__ == "__main__":
    unittest.main()
