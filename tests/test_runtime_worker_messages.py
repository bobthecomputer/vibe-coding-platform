from __future__ import annotations

import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.runtime_worker import _parse_structured_event


class RuntimeWorkerMessageParsingTests(unittest.TestCase):
    def test_preserves_fluxio_event_protocol(self) -> None:
        event = _parse_structured_event(
            "FLUXIO_EVENT:"
            + json.dumps(
                {
                    "kind": "approval.request",
                    "message": "Approve deploy?",
                    "status": "waiting_for_approval",
                    "data": {"surface": "deploy"},
                }
            )
        )

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["kind"], "approval.request")
        self.assertEqual(event["message"], "Approve deploy?")
        self.assertEqual(event["data"]["surface"], "deploy")

    def test_converts_open_runtime_command_json_to_live_tool_event(self) -> None:
        event = _parse_structured_event(
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "item_type": "command_execution",
                        "command": "pytest -q",
                        "status": "completed",
                    },
                }
            )
        )

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["kind"], "runtime.output")
        self.assertIn("pytest -q", event["message"])
        self.assertEqual(event["data"]["semanticKind"], "runtime.tool_result")
        self.assertEqual(event["data"]["command"], "pytest -q")

    def test_converts_assistant_message_json_to_live_model_event(self) -> None:
        event = _parse_structured_event(
            json.dumps(
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "I checked the repository and found the failing import."}
                        ],
                    },
                }
            )
        )

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["kind"], "runtime.model_message")
        self.assertIn("failing import", event["message"])
        self.assertEqual(event["data"]["semanticKind"], "runtime.model_message")

    def test_converts_opencode_part_json_to_live_model_event(self) -> None:
        event = _parse_structured_event(
            json.dumps(
                {
                    "type": "part.updated",
                    "part": {"type": "text", "text": "OpenCode streamed a visible answer."},
                }
            )
        )

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["kind"], "runtime.model_message")
        self.assertIn("visible answer", event["message"])

    def test_strips_ansi_before_parsing_json_event(self) -> None:
        event = _parse_structured_event(
            '\x1b[32m{"kind":"runtime.phase","message":"Lane booted","status":"running"}\x1b[0m'
        )

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["kind"], "runtime.phase")
        self.assertEqual(event["message"], "Lane booted")


if __name__ == "__main__":
    unittest.main()
