from __future__ import annotations

import pathlib
import shutil
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.checkpoints import CheckpointStore
from grant_agent.constitution import AgentConstitution
from grant_agent.context_manager import ContextWindowManager
from grant_agent.engine import AutonomousEngine
from grant_agent.memory import MemoryStore
from grant_agent.persona import PersonaRegistry
from grant_agent.session_store import SessionStore
from grant_agent.skills import SkillRegistry
from grant_agent.verification import VerificationRunner


class EngineTests(unittest.TestCase):
    def test_engine_generates_handoff_on_rollover(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        runs = root / ".agent_runs_test"
        if runs.exists():
            shutil.rmtree(runs)

        engine = AutonomousEngine(
            constitution=AgentConstitution.load(root / "config" / "constitution.json"),
            persona_registry=PersonaRegistry(root / "config" / "personas.json"),
            context_manager=ContextWindowManager(max_tokens=60),
            session_store=SessionStore(runs),
            verification_runner=VerificationRunner(),
            skill_registry=SkillRegistry(root / "config" / "skills.json"),
            memory_store=MemoryStore(root / ".agent_memory_test.json"),
        )
        result = engine.run(
            objective="Build preview and verification loop",
            docs=["docs/ROADMAP.md"],
            persona="balanced_builder",
            iterations=10,
            repo_path=root,
            verify_commands=[],
            project_profile="test profile",
            max_handoffs=4,
            max_runtime_seconds=60,
        )
        self.assertEqual(result["status"], "ok")
        self.assertGreaterEqual(len(result["handoff_packets"]), 1)
        self.assertIn("report_path", result)
        self.assertGreaterEqual(len(result.get("checkpoints", [])), 1)
        self.assertGreaterEqual(len(result.get("vibe_next_steps", [])), 1)

    def test_engine_blocks_when_docs_unreadable(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        runs = root / ".agent_runs_test"
        if runs.exists():
            shutil.rmtree(runs)

        engine = AutonomousEngine(
            constitution=AgentConstitution.load(root / "config" / "constitution.json"),
            persona_registry=PersonaRegistry(root / "config" / "personas.json"),
            context_manager=ContextWindowManager(max_tokens=400),
            session_store=SessionStore(runs),
            verification_runner=VerificationRunner(),
            skill_registry=SkillRegistry(root / "config" / "skills.json"),
            memory_store=MemoryStore(root / ".agent_memory_test.json"),
        )
        result = engine.run(
            objective="Feature with bad docs",
            docs=["docs/does_not_exist.md"],
            persona="balanced_builder",
            iterations=2,
            repo_path=root,
            verify_commands=[],
            project_profile="test profile",
            max_handoffs=1,
            max_runtime_seconds=60,
        )
        self.assertEqual(result["status"], "blocked")

    def test_engine_resume_uses_previous_state(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        runs = root / ".agent_runs_test"
        if runs.exists():
            shutil.rmtree(runs)

        engine = AutonomousEngine(
            constitution=AgentConstitution.load(root / "config" / "constitution.json"),
            persona_registry=PersonaRegistry(root / "config" / "personas.json"),
            context_manager=ContextWindowManager(max_tokens=200),
            session_store=SessionStore(runs),
            verification_runner=VerificationRunner(),
            skill_registry=SkillRegistry(root / "config" / "skills.json"),
            memory_store=MemoryStore(root / ".agent_memory_test.json"),
        )
        first = engine.run(
            objective="Resume flow objective",
            docs=["docs/ROADMAP.md"],
            persona="balanced_builder",
            iterations=1,
            repo_path=root,
            verify_commands=[],
            project_profile="test profile",
            max_handoffs=2,
            max_runtime_seconds=60,
        )
        first_session_id = pathlib.Path(first["session_path"]).name
        second = engine.run(
            objective="Resume flow objective",
            docs=[],
            persona="balanced_builder",
            iterations=1,
            repo_path=root,
            verify_commands=[],
            project_profile="test profile",
            max_handoffs=2,
            max_runtime_seconds=60,
            resume_from_session_id=first_session_id,
        )
        self.assertEqual(second["status"], "ok")
        self.assertIn(first_session_id, second["session_lineage"])

    def test_engine_resume_from_checkpoint(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        runs = root / ".agent_runs_test"
        if runs.exists():
            shutil.rmtree(runs)

        engine = AutonomousEngine(
            constitution=AgentConstitution.load(root / "config" / "constitution.json"),
            persona_registry=PersonaRegistry(root / "config" / "personas.json"),
            context_manager=ContextWindowManager(max_tokens=300),
            session_store=SessionStore(runs),
            verification_runner=VerificationRunner(),
            skill_registry=SkillRegistry(root / "config" / "skills.json"),
            memory_store=MemoryStore(root / ".agent_memory_test.json"),
        )
        first = engine.run(
            objective="Checkpoint resume objective",
            docs=["docs/ROADMAP.md"],
            persona="balanced_builder",
            iterations=2,
            repo_path=root,
            verify_commands=[],
            project_profile="test profile",
            max_handoffs=2,
            max_runtime_seconds=60,
            checkpoint_every=1,
        )
        first_session_path = pathlib.Path(first["session_path"])
        latest_ckpt = CheckpointStore.latest(first_session_path)
        self.assertIsNotNone(latest_ckpt)

        second = engine.run(
            objective="Checkpoint resume objective",
            docs=[],
            persona="balanced_builder",
            iterations=1,
            repo_path=root,
            verify_commands=[],
            project_profile="test profile",
            max_handoffs=2,
            max_runtime_seconds=60,
            resume_from_session_id=first_session_path.name,
            resume_from_checkpoint_path=str(latest_ckpt),
        )
        self.assertEqual(second["status"], "ok")
        self.assertIn("checkpoints", second)

    def test_engine_pauses_on_handoff_guardrail(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        runs = root / ".agent_runs_test"
        if runs.exists():
            shutil.rmtree(runs)

        engine = AutonomousEngine(
            constitution=AgentConstitution.load(root / "config" / "constitution.json"),
            persona_registry=PersonaRegistry(root / "config" / "personas.json"),
            context_manager=ContextWindowManager(max_tokens=50),
            session_store=SessionStore(runs),
            verification_runner=VerificationRunner(),
            skill_registry=SkillRegistry(root / "config" / "skills.json"),
            memory_store=MemoryStore(root / ".agent_memory_test.json"),
        )
        result = engine.run(
            objective="Trigger rollover quickly",
            docs=["docs/ROADMAP.md"],
            persona="balanced_builder",
            iterations=8,
            repo_path=root,
            verify_commands=[],
            project_profile="test profile",
            max_handoffs=3,
            max_runtime_seconds=60,
        )
        self.assertEqual(result["status"], "ok")
        self.assertIn(result.get("autopilot_pause_reason", ""), {"context_rollover", "context_hard_stop"})


if __name__ == "__main__":
    unittest.main()
