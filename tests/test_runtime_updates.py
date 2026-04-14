from __future__ import annotations

import json
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent import runtime_updates


class RuntimeUpdatesTests(unittest.TestCase):
    def tearDown(self) -> None:
        runtime_updates._CACHE.clear()
        super().tearDown()

    def test_compare_version_tokens_handles_semver_and_date_versions(self) -> None:
        self.assertLess(
            runtime_updates.compare_version_tokens("2026.2.15", "2026.4.14"),
            0,
        )
        self.assertLess(
            runtime_updates.compare_version_tokens("v0.4.0", "v0.9.0"),
            0,
        )

    @mock.patch("grant_agent.runtime_updates.urllib.request.urlopen")
    def test_latest_openclaw_release_reads_npm_latest_version(
        self, urlopen_mock: mock.Mock
    ) -> None:
        response = mock.Mock()
        response.read.return_value = json.dumps({"version": "2026.4.14"}).encode("utf-8")
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=False)
        urlopen_mock.return_value = response

        payload = runtime_updates.latest_openclaw_release()

        self.assertEqual(payload["version"], "2026.4.14")

    @mock.patch("grant_agent.runtime_updates.urllib.request.urlopen")
    def test_latest_hermes_release_reads_release_files_from_github_contents(
        self, urlopen_mock: mock.Mock
    ) -> None:
        response = mock.Mock()
        response.read.return_value = json.dumps(
            [
                {"name": "README.md"},
                {"name": "RELEASE_v0.8.0.md"},
                {"name": "RELEASE_v0.9.0.md"},
            ]
        ).encode("utf-8")
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=False)
        urlopen_mock.return_value = response

        payload = runtime_updates.latest_hermes_release()

        self.assertEqual(payload["version"], "v0.9.0")
        self.assertIn("RELEASE_v0.9.0.md", payload["sourceUrl"])


if __name__ == "__main__":
    unittest.main()
