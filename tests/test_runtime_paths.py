from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.models import Mission, WorkspaceProfile
from grant_agent.runtime_worker import _popen_command
from grant_agent.runtimes.base import runtime_lookup_path
from grant_agent.runtimes.hermes import HermesRuntimeAdapter
from grant_agent.runtimes.openclaw import OpenClawRuntimeAdapter


class RuntimePathTests(unittest.TestCase):
    def test_release_adjacent_runtime_bin_is_prepended_to_lookup_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            release = pathlib.Path(temp_dir) / "syntelos" / "releases" / "20260505-212517"
            runtime_bin = pathlib.Path(temp_dir) / "syntelos" / "runtime" / "bin"
            release.mkdir(parents=True)
            runtime_bin.mkdir(parents=True)

            lookup = runtime_lookup_path(release)

            self.assertTrue(lookup.startswith(str(runtime_bin)))

    def test_launch_commands_carry_release_adjacent_runtime_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            release = pathlib.Path(temp_dir) / "syntelos" / "releases" / "20260505-212517"
            runtime_bin = pathlib.Path(temp_dir) / "syntelos" / "runtime" / "bin"
            release.mkdir(parents=True)
            runtime_bin.mkdir(parents=True)
            for name in ("openclaw", "hermes"):
                executable = runtime_bin / (f"{name}.cmd" if os.name == "nt" else name)
                executable.write_text("@echo off\n" if os.name == "nt" else "#!/bin/sh\n", encoding="utf-8")
                if os.name != "nt":
                    executable.chmod(0o755)
            mission = Mission(
                mission_id="mission_runtime_path",
                workspace_id="workspace_primary",
                runtime_id="openclaw",
                objective="prove runtime path",
                success_checks=[],
            )
            workspace = WorkspaceProfile(
                workspace_id="workspace_primary",
                name="Primary",
                root_path=str(release),
                default_runtime="openclaw",
                workspace_type="python",
            )

            openclaw_command = OpenClawRuntimeAdapter().start_mission(
                mission, workspace
            )["launch_command"]
            hermes_command = HermesRuntimeAdapter()._mission_launch_command(
                "prove runtime path",
                workspace_root=str(release),
            )

            self.assertIn(str(runtime_bin), openclaw_command)
            self.assertIn(str(runtime_bin), hermes_command)
            self.assertNotIn("export PATH;", openclaw_command)
            self.assertNotIn("export PATH;", hermes_command)
            if os.name != "nt":
                self.assertTrue(_popen_command(str(openclaw_command))[0].startswith(str(runtime_bin)))
                self.assertTrue(_popen_command(str(hermes_command))[0].startswith(str(runtime_bin)))

    def test_openclaw_model_setup_command_is_worker_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            release = pathlib.Path(temp_dir) / "syntelos" / "releases" / "20260505-212517"
            runtime_bin = pathlib.Path(temp_dir) / "syntelos" / "runtime" / "bin"
            release.mkdir(parents=True)
            runtime_bin.mkdir(parents=True)
            executable = runtime_bin / (f"openclaw.cmd" if os.name == "nt" else "openclaw")
            executable.write_text("@echo off\n" if os.name == "nt" else "#!/bin/sh\n", encoding="utf-8")
            if os.name != "nt":
                executable.chmod(0o755)
            mission = Mission(
                mission_id="mission_runtime_path",
                workspace_id="workspace_primary",
                runtime_id="openclaw",
                objective="prove runtime path",
                success_checks=[],
                route_configs=[
                    {
                        "role": "executor",
                        "provider": "openai",
                        "model": "gpt-5-mini",
                        "effort": "medium",
                    }
                ],
            )
            workspace = WorkspaceProfile(
                workspace_id="workspace_primary",
                name="Primary",
                root_path=str(release),
                default_runtime="openclaw",
                workspace_type="python",
            )

            command = str(OpenClawRuntimeAdapter().start_mission(mission, workspace)["launch_command"])
            args = _popen_command(command)

            if os.name == "nt":
                self.assertEqual(args[:4], ["cmd", "/d", "/s", "/c"])
            else:
                self.assertEqual(args[:2], ["sh", "-lc"])
                self.assertIn(str(executable), args[2])
                self.assertIn("export PATH;", args[2])
                self.assertIn("&&", args[2])


if __name__ == "__main__":
    unittest.main()
