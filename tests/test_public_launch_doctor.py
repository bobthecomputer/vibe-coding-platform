from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.public_launch_doctor import build_public_launch_doctor


class PublicLaunchDoctorTests(unittest.TestCase):
    def test_doctor_combines_public_readiness_and_release_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            release_plan = {
                "ready": True,
                "tagName": "fluxio-20260531T113504Z",
                "assetCount": 4,
                "command": "gh release create fluxio-20260531T113504Z",
                "recordReceiptCommand": "python scripts/record_github_release_publication.py --tag fluxio-20260531T113504Z",
                "nextAction": "Create the GitHub release.",
            }
            readiness = {
                "ok": False,
                "status": "public_packet_ready_missing_current_web_and_publication",
                "missing": ["public_web_current", "external_publication_proven"],
                "publicWeb": {"currentGitDirtyPathCount": 3},
                "repairPacket": {
                    "releaseBlockingPathCount": 3,
                    "privateOrGeneratedPathCount": 0,
                },
                "stagingProof": {"schema": "fluxio.public_launch_staging_proof.v1"},
            }
            with patch(
                "scripts.public_launch_doctor.build_github_release_publication_plan",
                return_value=release_plan,
            ), patch(
                "scripts.public_launch_doctor.verify_public_launch_readiness",
                return_value=readiness,
            ):
                payload = build_public_launch_doctor(root, write=True)
            self.assertEqual(payload["schema"], "fluxio.public_launch_doctor.v1")
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["status"], "needs_current_public_source")
            self.assertEqual(payload["githubReleasePlanTag"], "fluxio-20260531T113504Z")
            self.assertEqual(payload["githubReleasePlanAssetCount"], 4)
            self.assertEqual(payload["releaseBlockingPathCount"], 3)
            self.assertTrue((root / ".agent_control" / "public_launch_readiness" / "doctor.json").exists())
            self.assertTrue((root / ".agent_control" / "publication" / "github-release-plan.json").exists())


if __name__ == "__main__":
    unittest.main()
