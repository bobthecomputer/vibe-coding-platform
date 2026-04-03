from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.mission_control import (
    ControlRoomStore,
    build_escalation_preview,
    mission_mode_to_engine_mode,
)


class MissionControlTests(unittest.TestCase):
    def test_store_creates_default_workspace_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            (root / "src-tauri").mkdir()

            store = ControlRoomStore(root)
            snapshot = store.build_snapshot()

            self.assertEqual(len(snapshot["workspaces"]), 1)
            self.assertEqual(snapshot["workspaces"][0]["workspace_type"], "tauri-python")
            self.assertIn("profiles", snapshot)
            self.assertIn("skillLibrary", snapshot)
            self.assertIn("harnessLab", snapshot)
            self.assertIn("bridgeLab", snapshot)
            self.assertIn("guidance", snapshot)
            self.assertIn("onboarding", snapshot)

    def test_create_mission_persists_and_builds_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            store = ControlRoomStore(root)
            workspace = store.load_workspaces()[0]

            mission = store.create_mission(
                workspace_id=workspace.workspace_id,
                runtime_id="openclaw",
                objective="Ship a safer control room",
                success_checks=["Proof summary written"],
                mode="Autopilot",
                verification_commands=["python -m unittest"],
                max_runtime_seconds=3600,
                escalation_destination="123456",
            )
            mission.state.status = "needs_approval"
            mission.proof.summary = "Approval needed for deploy step."
            preview = build_escalation_preview(mission)

            self.assertIn("Approval needed", preview)
            self.assertEqual(store.get_mission(mission.mission_id).mission_id, mission.mission_id)

    def test_mode_mapping_matches_desktop_vocabulary(self) -> None:
        self.assertEqual(mission_mode_to_engine_mode("Focus"), "fast")
        self.assertEqual(mission_mode_to_engine_mode("Autopilot"), "autopilot")
        self.assertEqual(mission_mode_to_engine_mode("Deep Run"), "deep_run")
        self.assertEqual(mission_mode_to_engine_mode("Research"), "swarms")


if __name__ == "__main__":
    unittest.main()
