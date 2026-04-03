from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from dataclasses import asdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.app_capability_standard import (
    build_connected_apps_snapshot,
    load_mock_manifests,
    validate_handshake_payload,
    validate_manifest_payload,
)


class AppCapabilityStandardTests(unittest.TestCase):
    def test_mock_manifests_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "config").mkdir()
            source = pathlib.Path(__file__).resolve().parents[1] / "config" / "connected_apps.json"
            (root / "config" / "connected_apps.json").write_text(
                source.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            manifests = load_mock_manifests(root)

        self.assertGreaterEqual(len(manifests), 2)
        for manifest in manifests:
            self.assertEqual(validate_manifest_payload(asdict(manifest)), [])

    def test_bridge_snapshot_contains_handshake_and_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "config").mkdir()
            source = pathlib.Path(__file__).resolve().parents[1] / "config" / "connected_apps.json"
            (root / "config" / "connected_apps.json").write_text(
                source.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            snapshot = build_connected_apps_snapshot(root)

        self.assertIn("discoveredApps", snapshot)
        self.assertIn("connectedSessions", snapshot)
        self.assertEqual(validate_handshake_payload(snapshot["bridgeHandshake"]), [])
        self.assertTrue(snapshot["connectedSessions"])


if __name__ == "__main__":
    unittest.main()
