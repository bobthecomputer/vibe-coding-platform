from __future__ import annotations

import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts import sync_nas_system_audit as sync


class SyncNasSystemAuditTests(unittest.TestCase):
    def test_nas_client_disables_key_and_agent_auth_probe(self) -> None:
        class FakePolicy:
            pass

        class FakeClient:
            def __init__(self) -> None:
                self.kwargs = {}
                self.policy = None

            def set_missing_host_key_policy(self, policy: object) -> None:
                self.policy = policy

            def connect(self, *args: object, **kwargs: object) -> None:
                self.kwargs = kwargs

        class FakeParamiko:
            def __init__(self) -> None:
                self.client = FakeClient()

            def SSHClient(self) -> FakeClient:
                return self.client

            def AutoAddPolicy(self) -> FakePolicy:
                return FakePolicy()

        fake = FakeParamiko()
        client = sync._connect_nas_client(
            fake,
            {"host": "100.125.54.118", "port": 22, "user": "Codex2", "password": "secret"},
        )

        self.assertIs(client, fake.client)
        self.assertFalse(client.kwargs["look_for_keys"])
        self.assertFalse(client.kwargs["allow_agent"])
        self.assertEqual(client.kwargs["auth_timeout"], 30)

    def test_non_secret_evidence_upload_list_includes_runtime_inputs(self) -> None:
        evidence_files = "\n".join(sync.NON_SECRET_EVIDENCE_FILES)

        self.assertIn(".agent_control/red_team_escalation_history.jsonl", evidence_files)
        self.assertIn(".agent_control/release_artifacts/latest.json", evidence_files)
        self.assertIn(".agent_control/t3_code_benchmark_latest.json", evidence_files)
        self.assertIn(".agent_control/live_mission_detail_performance_latest.json", evidence_files)
        self.assertIn(".agent_control/public_launch_readiness/doctor.json", evidence_files)
        self.assertIn(".agent_control/publication/github-release-plan.json", evidence_files)
        self.assertIn(".agent_control/publication/github-release.json", evidence_files)
        self.assertIn(".agent_control/self_improvement_evidence/latest.json", evidence_files)
        self.assertIn(".agent_control/self_improvement_evidence/watchdog_latest.json", evidence_files)
        self.assertIn(".agent_control/self_improvement_evidence/watchdog_history.jsonl", evidence_files)
        self.assertNotIn("grand_agent_admin_password", evidence_files)
        self.assertNotIn(".dpapi", evidence_files)
        self.assertNotIn("nas_codex2", evidence_files)

    def test_local_evidence_archive_contains_only_existing_safe_agent_control_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            red_team = root / ".agent_control" / "red_team_escalation_history.jsonl"
            benchmark = root / ".agent_control" / "t3_code_benchmark_latest.json"
            red_team.parent.mkdir(parents=True)
            red_team.write_text('{"schema":"fluxio.red_team_escalation_history.v1"}\n', encoding="utf-8")
            benchmark.write_text('{"schema":"fluxio.t3_code_benchmark.v1"}\n', encoding="utf-8")

            payload, pushed, missing = sync._build_local_evidence_archive(root)

        self.assertIn(".agent_control/red_team_escalation_history.jsonl", pushed)
        self.assertIn(".agent_control/t3_code_benchmark_latest.json", pushed)
        self.assertIn(".agent_control/self_improvement_evidence/latest.json", missing)
        self.assertIn(".agent_control/self_improvement_evidence/watchdog_history.jsonl", missing)
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
            names = archive.getnames()
        self.assertEqual(sorted(names), sorted(pushed))
        self.assertTrue(all(name.startswith(".agent_control/") for name in names))
        self.assertFalse(any(".." in Path(name).parts for name in names))

    def test_local_evidence_archive_includes_latest_release_artifact_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive_root = root / ".agent_control" / "release_artifacts" / "20260530T034331Z"
            release_candidate = archive_root / "release_candidate" / "publication-attachments.json"
            watchdog_history = archive_root / "self_improvement" / "watchdog_history.jsonl"
            release_candidate.parent.mkdir(parents=True)
            watchdog_history.parent.mkdir(parents=True)
            release_candidate.write_text('{"schema":"fluxio.public_release_attachment_manifest.v1"}\n', encoding="utf-8")
            watchdog_history.write_text('{"schema":"fluxio.self_improvement_watchdog_cadence.v1"}\n', encoding="utf-8")
            latest = root / ".agent_control" / "release_artifacts" / "latest.json"
            latest.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.latest_release_artifact_pointer.v1",
                        "archiveRoot": str(archive_root),
                    }
                ),
                encoding="utf-8",
            )

            payload, pushed, missing = sync._build_local_evidence_archive(root)

        self.assertIn(".agent_control/release_artifacts/latest.json", pushed)
        self.assertIn(
            ".agent_control/release_artifacts/20260530T034331Z/release_candidate/publication-attachments.json",
            pushed,
        )
        self.assertIn(
            ".agent_control/release_artifacts/20260530T034331Z/self_improvement/watchdog_history.jsonl",
            pushed,
        )
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
            names = archive.getnames()
        self.assertEqual(sorted(names), sorted(pushed))
        self.assertFalse(any(".." in Path(name).parts for name in names))

    def test_local_evidence_archive_includes_latest_root_live_agent_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            control = root / ".agent_control"
            control.mkdir(parents=True)
            older = control / "live-agent-old-check.json"
            newer = control / "live-agent-current-check.json"
            older.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.authenticated_live_agent.v1",
                        "checkedAt": "2026-05-30T10:00:00+00:00",
                        "ok": True,
                    }
                ),
                encoding="utf-8",
            )
            newer.write_text(
                json.dumps(
                    {
                        "schema": "fluxio.authenticated_live_agent.v1",
                        "checkedAt": "2026-05-31T08:02:17+00:00",
                        "ok": True,
                    }
                ),
                encoding="utf-8",
            )
            (control / "live-agent-secret-shaped-check.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.unsupported_debug_dump.v1",
                        "checkedAt": "2026-05-31T09:00:00+00:00",
                        "secret": "do-not-sync",
                    }
                ),
                encoding="utf-8",
            )

            payload, pushed, missing = sync._build_local_evidence_archive(root)

        self.assertIn(".agent_control/live-agent-current-check.json", pushed)
        self.assertNotIn(".agent_control/live-agent-old-check.json", pushed)
        self.assertNotIn(".agent_control/live-agent-secret-shaped-check.json", pushed)
        self.assertIn(".agent_control/red_team_escalation_history.jsonl", missing)
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
            names = archive.getnames()
        self.assertIn(".agent_control/live-agent-current-check.json", names)
        self.assertNotIn(".agent_control/live-agent-secret-shaped-check.json", names)

    def test_unsafe_evidence_paths_are_rejected_before_tar_creation(self) -> None:
        for relative_path in (
            "/tmp/secret.json",
            "../.agent_control/secret.json",
            ".agent_control/../secret.json",
            "agent_control/not-hidden.json",
        ):
            with self.subTest(relative_path=relative_path):
                with self.assertRaises(ValueError):
                    sync._safe_evidence_relative_path(relative_path)

    def test_sync_keeps_newer_local_timestamped_evidence(self) -> None:
        local = json.dumps(
            {
                "schema": "fluxio.live_mission_detail_performance.v1",
                "checkedAt": "2026-05-31T05:54:23+00:00",
                "ok": True,
            }
        )
        remote = json.dumps(
            {
                "schema": "fluxio.live_mission_detail_performance.v1",
                "checkedAt": "2026-05-30T20:43:51+00:00",
                "ok": False,
            }
        )

        self.assertTrue(sync._should_keep_local_evidence(local, remote))
        self.assertFalse(sync._should_keep_local_evidence(remote, local))


if __name__ == "__main__":
    unittest.main()
