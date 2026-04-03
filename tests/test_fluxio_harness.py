from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.fluxio_harness import FluxioHarness, LegacyHarnessAdapter
from grant_agent.session_store import SessionStore
from grant_agent.skill_library import SkillLibrary
from grant_agent.skills import SkillRegistry
from grant_agent.verification import VerificationRunner


class _DummyEngine:
    def run(self, **_: object) -> dict:
        return {"status": "ok"}


class FluxioHarnessTests(unittest.TestCase):
    def _build_harness(self, root: pathlib.Path) -> FluxioHarness:
        config_dir = root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "skills.json").write_text(
            json.dumps(
                [
                    {
                        "name": "repo_scan",
                        "description": "Ground the task in repo evidence",
                        "schema": {"type": "object", "properties": {}},
                        "permissions": ["file_read"],
                    }
                ],
                indent=2,
            ),
            encoding="utf-8",
        )
        return FluxioHarness(
            compatibility_harness=LegacyHarnessAdapter(_DummyEngine()),
            session_store=SessionStore(root / ".agent_runs"),
            verification_runner=VerificationRunner(),
            skill_library=SkillLibrary(root=root, registry=SkillRegistry(config_dir / "skills.json")),
        )

    def test_harness_runs_and_promotes_learned_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text(
                "import unittest\n\nclass Sample(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )

            harness = self._build_harness(root)
            result = harness.run(
                objective="Verify the control room and repo grounding flow",
                docs=["README.md"],
                project_profile="Harness test",
                verify_commands=["python -m unittest discover -s tests"],
                repo_path=root,
                iterations=4,
                max_handoffs=6,
                max_runtime_seconds=300,
                profile_name="builder",
            )

            self.assertEqual(result["harness_id"], "fluxio_hybrid")
            self.assertGreaterEqual(len(result["route_configs"]), 4)
            self.assertTrue(result["plan_revisions"])
            self.assertTrue(result["learned_skill_events"])
            self.assertIn("execution_scope", result)
            self.assertIn("execution_policy", result)

    def test_rejected_action_triggers_replanning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text(
                "import unittest\n\nclass Sample(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )

            harness = self._build_harness(root)
            first = harness.run(
                objective="Verify the repo with approval-gated verification",
                docs=["README.md"],
                project_profile="Approval test",
                verify_commands=["git reset --hard"],
                repo_path=root,
                iterations=4,
                max_handoffs=6,
                max_runtime_seconds=300,
                profile_name="builder",
            )
            self.assertEqual(first["autopilot_pause_reason"], "approval_required")

            session_path = pathlib.Path(first["session_path"])
            state_path = session_path / "state.json"
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            payload["action_history"][-1]["gate"]["status"] = "rejected"
            state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            resumed = harness.run(
                objective="Verify the repo with approval-gated verification",
                docs=["README.md"],
                project_profile="Approval test",
                verify_commands=["git reset --hard"],
                repo_path=root,
                iterations=2,
                max_handoffs=6,
                max_runtime_seconds=300,
                profile_name="builder",
                resume_from_session_id=session_path.name,
            )

            triggers = [item["trigger"] for item in resumed["plan_revisions"]]
            self.assertIn("approval_rejected", triggers)


if __name__ == "__main__":
    unittest.main()
