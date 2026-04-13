from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.runtimes.hermes import HermesRuntimeAdapter
from grant_agent.runtimes.openclaw import OpenClawRuntimeAdapter


class RuntimeAdapterTests(unittest.TestCase):
    @mock.patch("grant_agent.runtimes.openclaw.subprocess.run")
    @mock.patch("grant_agent.runtimes.openclaw.shutil.which")
    def test_openclaw_adapter_detects_runtime(
        self, which_mock: mock.Mock, run_mock: mock.Mock
    ) -> None:
        which_mock.return_value = "openclaw"
        run_mock.return_value = mock.Mock(stdout="2026.2.15\n", stderr="")

        adapter = OpenClawRuntimeAdapter()
        with tempfile.TemporaryDirectory() as temp_dir:
            status = adapter.doctor(pathlib.Path(temp_dir))

        self.assertTrue(status.detected)
        self.assertEqual(status.version, "2026.2.15")
        self.assertGreaterEqual(len(status.capabilities), 1)

    @mock.patch("grant_agent.runtimes.hermes.shutil.which")
    def test_hermes_adapter_reports_missing_runtime(self, which_mock: mock.Mock) -> None:
        which_mock.return_value = None

        adapter = HermesRuntimeAdapter()
        with tempfile.TemporaryDirectory() as temp_dir:
            status = adapter.doctor(pathlib.Path(temp_dir))

        self.assertFalse(status.detected)
        self.assertIn("Install Hermes", status.doctor_summary)

    @mock.patch("grant_agent.runtimes.hermes.subprocess.run")
    @mock.patch("grant_agent.runtimes.hermes.shutil.which")
    @mock.patch("grant_agent.runtimes.hermes.os.name", "nt")
    def test_hermes_adapter_detects_runtime_inside_wsl(
        self,
        which_mock: mock.Mock,
        run_mock: mock.Mock,
    ) -> None:
        def _which(name: str) -> str | None:
            if name == "wsl":
                return "C:/Windows/System32/wsl.exe"
            return None

        which_mock.side_effect = _which
        run_mock.return_value = mock.Mock(
            returncode=0,
            stdout="Hermes Agent v0.4.0\n",
            stderr="",
        )

        adapter = HermesRuntimeAdapter()
        with tempfile.TemporaryDirectory() as temp_dir:
            status = adapter.doctor(pathlib.Path(temp_dir))

        self.assertTrue(status.detected)
        self.assertEqual(status.command, "wsl:hermes")
        self.assertIn("WSL2", status.doctor_summary)

    def test_openclaw_launch_uses_session_id_and_json_output(self) -> None:
        adapter = OpenClawRuntimeAdapter()
        mission = mock.Mock(mission_id="mission_abcd1234", objective='Fix "quote" handling')
        workspace = mock.Mock(root_path=r"C:\repo")

        launch = adapter.start_mission(mission, workspace)

        command = str(launch["launch_command"])
        self.assertIn("--session-id fluxio_mission_abcd1234", command)
        self.assertIn("--thinking high", command)
        self.assertIn("--json", command)
        self.assertIn('Fix \\"quote\\" handling', command)

    def test_hermes_launch_uses_wsl_bash_lc_when_hermes_only_in_wsl(self) -> None:
        adapter = HermesRuntimeAdapter()
        mission = mock.Mock(mission_id="mission_abcd1234", objective="Run from WSL")
        workspace = mock.Mock(root_path=r"C:\repo")

        with mock.patch("grant_agent.runtimes.hermes.shutil.which", return_value=None):
            with mock.patch.object(adapter, "_wsl_hermes_available", return_value=True):
                launch = adapter.start_mission(mission, workspace)

        command = str(launch["launch_command"])
        self.assertTrue(command.startswith("wsl bash -lc "))
        self.assertIn('hermes chat -q \\"Run from WSL\\" -Q', command)


if __name__ == "__main__":
    unittest.main()
