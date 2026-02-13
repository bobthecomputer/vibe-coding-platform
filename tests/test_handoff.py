from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.context_manager import ContextWindowManager
from grant_agent.handoff import create_handoff_packet
from grant_agent.models import PersonaProfile, PromptStack, RunState


class HandoffTests(unittest.TestCase):
    def test_packet_contains_progress(self) -> None:
        manager = ContextWindowManager(max_tokens=100)
        manager.record("user", "build feature")
        manager.record("assistant", "did something")

        state = RunState(
            objective="Build feature",
            plan_steps=["Read docs", "Implement"],
            acceptance_checks=["Tests pass"],
            completed_steps=["Read docs"],
            next_actions=["Implement"],
        )
        stack = PromptStack(
            base_constitution="rules",
            project_profile="project",
            persona=PersonaProfile(
                name="p",
                tone="t",
                risk_tolerance="medium",
                creativity_level="high",
                coding_style="small changes",
                verbosity="concise",
            ),
            task_brief="task",
            step_policy="policy",
        )
        packet = create_handoff_packet(
            session_id="s1",
            parent_session_id=None,
            reason="context_rollover",
            state=state,
            prompt_stack=stack,
            context_manager=manager,
        )
        self.assertEqual(packet.progress["remaining_steps"], ["Implement"])
        self.assertEqual(packet.session_id, "s1")


if __name__ == "__main__":
    unittest.main()
