from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.record_github_release_publication import build_github_release_publication_plan


class GitHubReleasePublicationTests(unittest.TestCase):
    def test_publication_plan_points_to_checksummed_release_candidate_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            release_dir = root / ".agent_control" / "release_artifacts" / "20260531T113504Z" / "release_candidate"
            release_dir.mkdir(parents=True)
            release_candidate = release_dir / "release-candidate.json"
            publication_manifest = release_dir / "publication-manifest.json"
            publication_attachments = release_dir / "publication-attachments.json"
            release_notes = release_dir / "public-release-notes.md"
            release_candidate.write_text('{"schema":"fluxio.release_candidate.v1"}', encoding="utf-8")
            publication_manifest.write_text('{"schema":"fluxio.public_release_publication_packet.v1"}', encoding="utf-8")
            publication_attachments.write_text('{"schema":"fluxio.public_release_attachment_manifest.v1"}', encoding="utf-8")
            release_notes.write_text("# Fluxio release candidate\n", encoding="utf-8")
            latest = root / ".agent_control" / "release_artifacts" / "latest.json"
            latest.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.latest_release_artifact_pointer.v1",
                        "candidateId": "release-candidate-20260531T113504Z",
                        "releaseCandidatePath": str(release_candidate),
                        "publicationManifestPath": str(publication_manifest),
                        "publicationAttachmentManifestPath": str(publication_attachments),
                        "publicReleaseNotesPath": str(release_notes),
                    }
                ),
                encoding="utf-8",
            )

            with patch("scripts.record_github_release_publication._git_output", return_value="abc123"):
                plan = build_github_release_publication_plan(root, repo="example/fluxio")

        self.assertTrue(plan["ready"])
        self.assertEqual(plan["schema"], "fluxio.github_release_publication_plan.v1")
        self.assertEqual(plan["repo"], "example/fluxio")
        self.assertEqual(plan["tagName"], "fluxio-20260531T113504Z")
        self.assertEqual(plan["targetCommitish"], "abc123")
        self.assertEqual(plan["assetCount"], 4)
        self.assertTrue(plan["expectedAttachmentManifestReady"])
        self.assertIn("publication-attachments.json", plan["command"])
        self.assertIn("gh", plan["command"])
        self.assertTrue(all(item["sha256"] for item in plan["assets"]))


if __name__ == "__main__":
    unittest.main()
