from __future__ import annotations

import json
import pathlib
import shutil
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.eval import summarize_runs


class EvalTests(unittest.TestCase):
    def test_summarize_runs(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        base = root / ".agent_runs_eval"
        if base.exists():
            shutil.rmtree(base)
        session = base / "session_test123"
        session.mkdir(parents=True, exist_ok=True)

        (session / "handoff_packet_001.json").write_text("{}", encoding="utf-8")
        (session / "state.json").write_text(
            json.dumps(
                {
                    "context": {"usage_ratio": 0.8},
                    "verification_results": [
                        {"command": "ok", "return_code": 0},
                        {"command": "fail", "return_code": 1},
                    ],
                }
            ),
            encoding="utf-8",
        )
        metrics = summarize_runs(base)
        self.assertEqual(metrics["total_sessions"], 1)
        self.assertEqual(metrics["sessions_with_handoff"], 1)
        self.assertEqual(metrics["verification_failures"], 1)
        self.assertIn("blocked_commands", metrics)
        self.assertIn("runs_with_checkpoints", metrics)


if __name__ == "__main__":
    unittest.main()
