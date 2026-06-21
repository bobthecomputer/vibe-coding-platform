from __future__ import annotations

import json
import pathlib
import sqlite3
import tempfile
import unittest

from src.grant_agent.mindtower_fusion import (
    build_mindtower_fusion_snapshot,
    build_solantir_signal_snapshots,
)


class MindTowerFusionAdapterTests(unittest.TestCase):
    def test_readonly_adapter_counts_resources_and_masks_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            db_path = root / "mindtower.sqlite"
            connection = sqlite3.connect(db_path)
            try:
                connection.executescript(
                    """
                    CREATE TABLE records (
                      resource TEXT NOT NULL,
                      id TEXT NOT NULL,
                      payload TEXT NOT NULL,
                      created_at TEXT NOT NULL,
                      updated_at TEXT NOT NULL,
                      PRIMARY KEY (resource, id)
                    );
                    CREATE TABLE events (
                      id TEXT PRIMARY KEY,
                      source_type TEXT NOT NULL,
                      source_id TEXT NOT NULL,
                      author TEXT NOT NULL,
                      published_at TEXT NOT NULL,
                      content TEXT NOT NULL,
                      url TEXT NOT NULL,
                      tags_json TEXT NOT NULL,
                      priority_score INTEGER NOT NULL,
                      raw_payload_ref TEXT NOT NULL,
                      created_at TEXT NOT NULL
                    );
                    CREATE TABLE runtime_state (
                      namespace TEXT NOT NULL,
                      key TEXT NOT NULL,
                      value TEXT NOT NULL,
                      updated_at TEXT NOT NULL,
                      PRIMARY KEY (namespace, key)
                    );
                    """
                )
                now = "2026-06-21T00:00:00Z"
                connection.execute(
                    "INSERT INTO records VALUES (?, ?, ?, ?, ?)",
                    (
                        "sources",
                        "source_one",
                        json.dumps({"id": "source_one", "label": "Example source", "status": "healthy"}),
                        now,
                        now,
                    ),
                )
                connection.execute(
                    "INSERT INTO records VALUES (?, ?, ?, ?, ?)",
                    (
                        "summary-jobs",
                        "summary_one",
                        json.dumps(
                            {
                                "id": "summary_one",
                                "label": "Morning source review",
                                "status": "ready",
                                "api_token": "job-secret-token",
                            }
                        ),
                        now,
                        now,
                    ),
                )
                connection.execute(
                    "INSERT INTO records VALUES (?, ?, ?, ?, ?)",
                    (
                        "credential-status",
                        "openai",
                        json.dumps(
                            {
                                "id": "openai",
                                "key_name": "openai",
                                "status": "ready",
                                "details": "connected",
                                "ai_api_key": "sk-test-secret-value",
                                "updated_at": now,
                            }
                        ),
                        now,
                        now,
                    ),
                )
                connection.execute(
                    "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        "event_one",
                        "rss",
                        "source_one",
                        "author",
                        now,
                        "content",
                        "https://example.invalid/item",
                        "[]",
                        1,
                        "raw",
                        now,
                    ),
                )
                connection.execute(
                    "INSERT INTO runtime_state VALUES (?, ?, ?, ?)",
                    ("worker", "last_run", "ok", now),
                )
                connection.commit()
            finally:
                connection.close()

            snapshot = build_mindtower_fusion_snapshot(root, db_path=db_path)

            self.assertTrue(snapshot["adapter"]["available"])
            self.assertTrue(snapshot["adapter"]["readOnly"])
            self.assertEqual(snapshot["adapter"]["writeActions"], 0)
            self.assertFalse(snapshot["adapter"]["credentialValuesExposed"])
            self.assertEqual(snapshot["adapter"]["recordCounts"]["sources"], 1)
            self.assertEqual(snapshot["adapter"]["recordCounts"]["summary-jobs"], 1)
            self.assertEqual(snapshot["adapter"]["eventCount"], 1)
            self.assertEqual(snapshot["adapter"]["runtimeStateCount"], 1)
            self.assertEqual(snapshot["adapter"]["credentialSummary"][0]["status"], "ready")
            self.assertEqual(snapshot["adapter"]["sourceHealth"][0]["label"], "Example source")
            self.assertEqual(snapshot["adapter"]["sourceHealth"][0]["status"], "healthy")
            self.assertEqual(snapshot["adapter"]["summaryJobs"][0]["label"], "Morning source review")
            self.assertEqual(snapshot["adapter"]["summaryJobs"][0]["status"], "ready")
            self.assertEqual(snapshot["adapter"]["recentEvents"][0]["sourceType"], "rss")
            self.assertEqual(snapshot["adapter"]["recentEvents"][0]["priorityScore"], 1)
            self.assertEqual(snapshot["adapter"]["runtimeStatePreview"][0]["namespace"], "worker")
            joined = json.dumps(snapshot)
            self.assertNotIn("sk-test-secret-value", joined)
            self.assertNotIn("job-secret-token", joined)
            self.assertEqual(snapshot["rows"][0]["id"], "mindtower-readonly-sqlite-adapter")
            self.assertEqual(snapshot["rows"][0]["collectionMode"], "read-only-adapter")
            self.assertIn("read-only mode", snapshot["rows"][0]["proofNeed"])

    def test_missing_database_reports_fallback_without_fake_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            snapshot = build_mindtower_fusion_snapshot(root, db_path=root / "missing.sqlite")

            self.assertFalse(snapshot["adapter"]["available"])
            self.assertEqual(snapshot["adapter"]["status"], "missing")
            self.assertEqual(snapshot["rows"], [])
            self.assertEqual(snapshot["adapter"]["sourceHealth"], [])
            self.assertEqual(snapshot["adapter"]["recentEvents"], [])
            self.assertEqual(snapshot["signalSnapshots"], [])

    def test_solantir_signal_snapshots_use_readonly_source_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir) / "platform"
            root.mkdir()
            solantir_root = pathlib.Path(temp_dir) / "Solantir"
            legacy_signals = solantir_root / "legacy" / "osint-platform" / "backend" / "solantir_api" / "signals.py"
            contracts = solantir_root / "packages" / "contracts" / "src" / "solantir.ts"
            legacy_signals.parent.mkdir(parents=True)
            contracts.parent.mkdir(parents=True)
            legacy_signals.write_text(
                "signal confidence provenance source forecast observation read-only risk\n",
                encoding="utf-8",
            )
            contracts.write_text(
                "export type SolantirProvenance = { source: string; confidence: number; signal: string }\n",
                encoding="utf-8",
            )

            snapshots = build_solantir_signal_snapshots(root, solantir_root=solantir_root)
            fusion = build_mindtower_fusion_snapshot(
                root,
                db_path=root / "missing.sqlite",
                solantir_root=solantir_root,
            )

            self.assertEqual(len(snapshots), 2)
            self.assertEqual(fusion["signalSnapshots"], snapshots)
            for signal in snapshots:
                self.assertEqual(signal["sourceProject"], "Solantir")
                self.assertEqual(signal["collectionMode"], "read-only-adapter")
                self.assertEqual(signal["riskLabel"], "no-trading-execution")
                self.assertTrue(signal["sourceHashPrefix"])
                self.assertTrue(pathlib.Path(signal["sourcePath"]).exists())
                self.assertGreaterEqual(len(signal["factors"]), 3)
                self.assertIn("no order routing", signal["safetyLabels"])
                self.assertIn("not investment advice", signal["safetyLabels"])


if __name__ == "__main__":
    unittest.main()
