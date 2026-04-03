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


if __name__ == "__main__":
    unittest.main()
