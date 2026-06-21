from __future__ import annotations

import json
import pathlib
import sqlite3
import tempfile
import unittest

from src.grant_agent.mindtower_fusion import build_mindtower_fusion_snapshot


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
                        json.dumps({"id": "source_one", "label": "Example source"}),
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
            self.assertEqual(snapshot["adapter"]["eventCount"], 1)
            self.assertEqual(snapshot["adapter"]["runtimeStateCount"], 1)
            self.assertEqual(snapshot["adapter"]["credentialSummary"][0]["status"], "ready")
            joined = json.dumps(snapshot)
            self.assertNotIn("sk-test-secret-value", joined)
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


if __name__ == "__main__":
    unittest.main()
