from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

from scripts.archive_release_proofs import build_release_proof_archive


class ReleaseProofArchiveTests(unittest.TestCase):
    def test_archive_collects_audit_digest_long_history_and_authenticated_live_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "docs").mkdir()
            (root / "docs" / "SYSTEM_GAP_ANALYSIS.current.md").write_text(
                "# Audit\n",
                encoding="utf-8",
            )
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True, exist_ok=True)
            (control_dir / "live_nas_system_audit_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.live_nas_system_audit_snapshot.v1",
                        "ok": True,
                        "checkedAt": "2026-05-29T14:10:21+00:00",
                        "sourceRoot": "/volume1/Saclay/projects/syntelos/releases/20260505-212517",
                        "syncedEvidenceFiles": [
                            ".agent_control/cross_device_launch_rehearsals/receipts.jsonl"
                        ],
                        "audit": {"summary": "52 current NAS mission rows"},
                    }
                ),
                encoding="utf-8",
            )
            digest_dir = root / ".agent_control" / "proof_digests"
            digest_dir.mkdir(parents=True)
            (digest_dir / "mission_123.md").write_text("# Mission Proof Digest\n", encoding="utf-8")
            report_dir = root / "tmp-ui-checks" / "release-long-history"
            report_dir.mkdir(parents=True)
            (report_dir / "release-long-history-check.json").write_text(
                json.dumps({"url": "/control?fixture=long_history", "passed": True}),
                encoding="utf-8",
            )
            (report_dir / "release-long-history-phone.html").write_text(
                "Long-History Proof Load",
                encoding="utf-8",
            )
            (report_dir / "release-long-history-phone.png").write_bytes(b"\x89PNG\r\n")
            live_dir = root / "tmp-ui-checks" / "authenticated-live-control"
            live_dir.mkdir(parents=True)
            (live_dir / "authenticated-live-control-check.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.authenticated_live_control.v1",
                        "ok": True,
                        "summary": {"counts": {"activeMissions": 2}},
                    }
                ),
                encoding="utf-8",
            )
            (live_dir / "authenticated-live-control.html").write_text(
                "Build a public-data investigation suite concept/prototype",
                encoding="utf-8",
            )
            (live_dir / "authenticated-live-control.png").write_bytes(b"\x89PNG\r\n")
            parallel_dir = root / ".agent_control" / "parallel_dispatch_evidence"
            parallel_dir.mkdir(parents=True)
            (parallel_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.parallel_dispatch_evidence.v1",
                        "ok": True,
                        "safeCandidates": [],
                        "blockedCandidates": [],
                    }
                ),
                encoding="utf-8",
            )
            cross_device_dir = root / ".agent_control" / "cross_device_launch_rehearsals"
            cross_device_dir.mkdir(parents=True)
            receipts = [
                {
                    "schema": "fluxio.cross_device_launch_rehearsal_receipt.v1",
                    "receiptId": "cross_launch_one",
                    "generatedAt": "2026-05-29T10:00:00+00:00",
                    "workspaceId": "workspace_a",
                    "missionId": "mission_a",
                    "status": "launched_with_review_items",
                },
                {
                    "schema": "fluxio.cross_device_launch_rehearsal_receipt.v1",
                    "receiptId": "cross_launch_two",
                    "generatedAt": "2026-05-29T11:00:00+00:00",
                    "workspaceId": "workspace_b",
                    "missionId": "mission_b",
                    "status": "launched_with_review_items",
                },
            ]
            (cross_device_dir / "receipts.jsonl").write_text(
                "\n".join(json.dumps(item) for item in receipts) + "\n",
                encoding="utf-8",
            )
            (cross_device_dir / "latest.json").write_text(
                json.dumps(receipts[-1]),
                encoding="utf-8",
            )
            launcher_dir = root / ".agent_control" / "launcher_package"
            launcher_dir.mkdir(parents=True)
            (launcher_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.launcher_package_verification.v1",
                        "ok": True,
                        "entrypoint": "scripts/fluxio-cli.mjs",
                        "packedFileCount": 42,
                    }
                ),
                encoding="utf-8",
            )
            public_launch_readiness_dir = root / ".agent_control" / "public_launch_readiness"
            public_launch_readiness_dir.mkdir(parents=True)
            (public_launch_readiness_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.public_launch_readiness.v1",
                        "ok": False,
                        "status": "public_packet_ready_missing_current_web_and_publication",
                        "internalPacketReady": True,
                    }
                ),
                encoding="utf-8",
            )
            (public_launch_readiness_dir / "staging-plan.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.public_launch_staging_proof.v1",
                        "status": "public_packet_ready_missing_current_web_and_publication",
                        "sourceCoverage": "full_git_status",
                        "releaseImpactPathCount": 2,
                        "privateOrGeneratedPathCount": 1,
                    }
                ),
                encoding="utf-8",
            )
            deployment_dir = root / ".agent_control" / "deployment_evidence"
            deployment_dir.mkdir(parents=True)
            (deployment_dir / "public-web.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.public_web_deployment.v1",
                        "provider": "github_pages",
                        "url": "https://example.github.io/fluxio/",
                        "workflowRun": "https://github.com/example/repo/actions/runs/42",
                        "sha": "abc123",
                        "publicationCurrent": True,
                        "sourceState": {
                            "deployedShaMatchesLocalHead": True,
                            "sourceWorkingTreeClean": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (deployment_dir / "private-nas-web.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.private_nas_web_deployment.v1",
                        "ok": True,
                        "scope": "private_tailscale_nas",
                        "controlUrl": "https://sysnology.tail602108.ts.net:47880/control",
                        "healthUrl": "https://sysnology.tail602108.ts.net:47880/health",
                        "checkedAt": "2026-05-29T14:18:00+00:00",
                    }
                ),
                encoding="utf-8",
            )
            self_improvement_dir = root / ".agent_control" / "self_improvement_evidence"
            self_improvement_dir.mkdir(parents=True)
            (self_improvement_dir / "latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.self_improvement_evidence.v1",
                        "ok": True,
                        "redTeam": {"historyRows": 31, "nextBenchmarkPlan": {"attemptBudget": 71}},
                    }
                ),
                encoding="utf-8",
            )
            (self_improvement_dir / "watchdog_latest.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.self_improvement_watchdog_cadence.v1",
                        "status": "completed",
                        "latestHistoryRows": 31,
                        "nextAttemptBudget": 71,
                    }
                ),
                encoding="utf-8",
            )
            watchdog_rows = [
                {
                    "schema": "fluxio.self_improvement_watchdog_cadence.v1",
                    "status": "completed",
                    "historyIndex": index,
                }
                for index in range(1, 4)
            ]
            (self_improvement_dir / "watchdog_history.jsonl").write_text(
                "\n".join(json.dumps(item) for item in watchdog_rows) + "\n",
                encoding="utf-8",
            )

            manifest = build_release_proof_archive(
                root,
                require_long_history=True,
                require_proof_digest=True,
                require_authenticated_live=True,
                require_parallel_dispatch=True,
                require_cross_device_launch_receipts=True,
                require_public_web_deployment=True,
                require_publication_packet=True,
            )

            self.assertTrue(manifest["ok"])
            self.assertEqual(manifest["schema"], "fluxio.release_proof_archive.v1")
            self.assertGreaterEqual(manifest["counts"]["copiedArtifacts"], 4)
            self.assertEqual(manifest["counts"]["proofDigests"], 1)
            self.assertEqual(manifest["counts"]["liveNasSystemAuditSnapshots"], 1)
            self.assertGreaterEqual(manifest["counts"]["longHistoryReports"], 1)
            self.assertGreaterEqual(manifest["counts"]["authenticatedLiveControlReports"], 1)
            self.assertEqual(manifest["counts"]["parallelDispatchEvidence"], 1)
            self.assertEqual(manifest["counts"]["crossDeviceLaunchReceipts"], 2)
            self.assertGreaterEqual(manifest["counts"]["crossDeviceLaunchReceiptArtifacts"], 3)
            self.assertEqual(manifest["counts"]["launcherPackageReceipts"], 1)
            self.assertEqual(manifest["counts"]["publicLaunchReadinessReceipts"], 1)
            self.assertEqual(manifest["counts"]["publicLaunchStagingProofReceipts"], 1)
            self.assertEqual(manifest["counts"]["selfImprovementEvidence"], 1)
            self.assertGreaterEqual(manifest["counts"]["selfImprovementArtifacts"], 4)
            self.assertEqual(manifest["counts"]["selfImprovementWatchdogReceipts"], 3)
            self.assertEqual(manifest["counts"]["selfImprovementWatchdogCompletedReceipts"], 3)
            self.assertEqual(manifest["counts"]["publicWebDeploymentReceipts"], 1)
            self.assertEqual(manifest["counts"]["privateNasWebDeploymentReceipts"], 1)
            self.assertEqual(manifest["counts"]["publicReleasePublicationPacketArtifacts"], 2)
            self.assertEqual(manifest["counts"]["publicReleaseAttachmentManifestArtifacts"], 1)
            self.assertEqual(manifest["counts"]["releaseCandidates"], 1)
            manifest_path = pathlib.Path(manifest["manifestPath"])
            self.assertTrue(manifest_path.exists())
            latest_path = pathlib.Path(manifest["latestPointerPath"])
            self.assertTrue(latest_path.exists())
            self.assertIn("browser_reports", manifest_path.read_text(encoding="utf-8"))
            self.assertIn("authenticated_live_control", manifest_path.read_text(encoding="utf-8"))
            self.assertIn("parallel_dispatch", manifest_path.read_text(encoding="utf-8"))
            self.assertIn("live_nas_system_audit", manifest_path.read_text(encoding="utf-8"))
            self.assertIn("cross_device_launch_rehearsals", manifest_path.read_text(encoding="utf-8"))
            self.assertIn("launcher_package", manifest_path.read_text(encoding="utf-8"))
            self.assertIn("self_improvement", manifest_path.read_text(encoding="utf-8"))
            self.assertIn("deployment_evidence", manifest_path.read_text(encoding="utf-8"))
            self.assertIn("release_candidate", manifest_path.read_text(encoding="utf-8"))
            candidate_path = pathlib.Path(manifest["archiveRoot"]) / "release_candidate" / "release-candidate.json"
            candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
            self.assertEqual(candidate["schema"], "fluxio.release_candidate.v1")
            self.assertTrue(candidate["publicReleasePublicationPacketAttached"])
            self.assertTrue(candidate["liveNasSystemAuditAttached"])
            self.assertEqual(
                candidate["liveNasSystemAuditReceipt"]["schema"],
                "fluxio.live_nas_system_audit_snapshot.v1",
            )
            self.assertIn("public-release-notes.md", candidate["publicReleaseNotesPath"])
            self.assertIn("publication-manifest.json", candidate["publicationManifestPath"])
            self.assertIn("publication-attachments.json", candidate["publicationAttachmentManifestPath"])
            self.assertTrue(candidate["publicReleaseAttachmentManifestAttached"])
            self.assertTrue(candidate["publicWebDeploymentAttached"])
            self.assertTrue(candidate["publicWebDeploymentCurrent"])
            self.assertTrue(candidate["privateNasWebDeploymentAttached"])
            self.assertTrue(candidate["launcherPackageAttached"])
            self.assertTrue(candidate["publicLaunchReadinessAttached"])
            self.assertTrue(candidate["publicLaunchStagingProofAttached"])
            self.assertEqual(
                candidate["publicLaunchStagingProofReceipt"]["schema"],
                "fluxio.public_launch_staging_proof.v1",
            )
            self.assertTrue(candidate["selfImprovementAttached"])
            self.assertTrue(candidate["requiredAttachments"]["selfImprovementWatchdogTrend"])
            self.assertEqual(candidate["selfImprovementSummary"]["watchdogReceiptCount"], 3)
            self.assertEqual(candidate["selfImprovementSummary"]["watchdogCompletedReceiptCount"], 3)
            self.assertTrue(candidate["selfImprovementSummary"]["trendProven"])
            self.assertTrue(candidate["crossDeviceLaunchReceiptsAttached"])
            self.assertEqual(candidate["crossDeviceLaunchReceiptSummary"]["receiptCount"], 2)
            self.assertEqual(candidate["crossDeviceLaunchReceiptSummary"]["trendStatus"], "repeated")
            self.assertEqual(candidate["launcherPackageReceipt"]["schema"], "fluxio.launcher_package_verification.v1")
            self.assertEqual(candidate["publicWebDeploymentReceipts"][0]["schema"], "fluxio.public_web_deployment.v1")
            self.assertTrue(candidate["publicWebDeploymentReceipts"][0]["publicationCurrent"])
            self.assertTrue(
                candidate["publicWebDeploymentReceipts"][0]["sourceState"]["deployedShaMatchesLocalHead"]
            )
            self.assertEqual(
                candidate["privateNasWebDeploymentReceipts"][0]["schema"],
                "fluxio.private_nas_web_deployment.v1",
            )
            publication_manifest_path = (
                pathlib.Path(manifest["archiveRoot"]) / "release_candidate" / "publication-manifest.json"
            )
            publication_manifest = json.loads(publication_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(
                publication_manifest["schema"],
                "fluxio.public_release_publication_packet.v1",
            )
            self.assertEqual(publication_manifest["crossDeviceLaunchReceiptSummary"]["receiptCount"], 2)
            self.assertEqual(publication_manifest["crossDeviceLaunchReceiptSummary"]["trendStatus"], "repeated")
            self.assertEqual(publication_manifest["selfImprovementSummary"]["watchdogReceiptCount"], 3)
            self.assertTrue(publication_manifest["requiredProof"]["selfImprovementWatchdogTrend"])
            self.assertTrue(publication_manifest["publicWebDeploymentCurrent"])
            self.assertTrue(publication_manifest["requiredProof"]["publicLaunchStagingProof"])
            self.assertEqual(
                publication_manifest["publicLaunchStagingReceipt"]["schema"],
                "fluxio.public_launch_staging_proof.v1",
            )
            self.assertEqual(
                publication_manifest["privateNasWebDeploymentReceipts"][0]["schema"],
                "fluxio.private_nas_web_deployment.v1",
            )
            self.assertEqual(
                publication_manifest["liveNasSystemAuditReceipt"]["schema"],
                "fluxio.live_nas_system_audit_snapshot.v1",
            )
            notes = (
                pathlib.Path(manifest["archiveRoot"]) / "release_candidate" / "public-release-notes.md"
            ).read_text(encoding="utf-8")
            self.assertIn("Cross-device launch receipts: 2", notes)
            self.assertIn("Cross-device receipt trend: repeated", notes)
            self.assertIn("Self-improvement watchdog receipts: 3", notes)
            self.assertIn("Self-improvement watchdog trend proven: True", notes)
            self.assertIn("Public launch staging proof attached: True", notes)
            self.assertIn("Live NAS audit attached: True", notes)
            self.assertIn("Public web current source: True", notes)
            self.assertIn("Private NAS web receipts attached: 1", notes)
            attachment_manifest = json.loads(
                (pathlib.Path(manifest["archiveRoot"]) / "release_candidate" / "publication-attachments.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                attachment_manifest["schema"],
                "fluxio.public_release_attachment_manifest.v1",
            )
            self.assertEqual(attachment_manifest["status"], "ready_to_attach")
            self.assertGreaterEqual(attachment_manifest["attachmentCount"], 6)
            self.assertTrue(all(item.get("sha256") for item in attachment_manifest["attachments"]))
            self.assertIn(
                "release_candidate/release-candidate.json",
                [item["archiveRelativePath"] for item in attachment_manifest["attachments"]],
            )
            self.assertIn(
                "self_improvement/watchdog_history.jsonl",
                [item["archiveRelativePath"] for item in attachment_manifest["attachments"]],
            )
            self.assertIn(
                "self_improvement/summary.json",
                [item["archiveRelativePath"] for item in attachment_manifest["attachments"]],
            )
            latest = json.loads(latest_path.read_text(encoding="utf-8"))
            self.assertEqual(latest["schema"], "fluxio.latest_release_artifact_pointer.v1")
            self.assertEqual(latest["candidateId"], candidate["candidateId"])
            self.assertEqual(latest["publicationAttachmentManifestPath"], candidate["publicationAttachmentManifestPath"])

    def test_archive_fails_when_required_proof_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = build_release_proof_archive(
                pathlib.Path(temp_dir),
                require_long_history=True,
                require_proof_digest=True,
                require_parallel_dispatch=True,
                require_cross_device_launch_receipts=True,
                require_public_web_deployment=True,
                require_publication_packet=True,
            )

            self.assertFalse(manifest["ok"])
            self.assertGreaterEqual(manifest["counts"]["missing"], 5)


if __name__ == "__main__":
    unittest.main()
