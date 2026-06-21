from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any


MINDTOWER_RESOURCE_KEYS = [
    "sources",
    "watch-rules",
    "digest-schedules",
    "alert-policies",
    "delivery-targets",
    "credential-status",
    "operator-profiles",
    "x-discovery-jobs",
    "setup-state",
    "summary-jobs",
]

SECRETISH_FIELDS = {
    "api_api_key",
    "ai_api_key",
    "ai_api_base_url",
    "telegram_api_hash",
    "telegram_session_string",
    "x_password",
    "chat_id",
    "telegram_chat_id",
    "telegram_user_id",
}


def _default_db_path(root: Path) -> Path:
    configured = os.environ.get("MINDTOWER_DB_PATH", "").strip()
    if configured:
        return Path(configured)
    return root.parent / "mind-tower" / "data" / "mindtower.sqlite"


def _mask_value(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= 4:
        return "***"
    return f"{text[:2]}***{text[-2:]}"


def _mask_payload(payload: dict[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for key, value in payload.items():
        if key in SECRETISH_FIELDS or "password" in key or "token" in key or key.endswith("_key"):
            masked[key] = _mask_value(value)
        elif isinstance(value, dict):
            masked[key] = _mask_payload(value)
        else:
            masked[key] = value
    return masked


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    cursor = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    )
    return cursor.fetchone() is not None


def _count_rows(connection: sqlite3.Connection, table: str) -> int:
    if not _table_exists(connection, table):
        return 0
    cursor = connection.execute(f"SELECT COUNT(*) FROM {table}")
    row = cursor.fetchone()
    return int(row[0] if row else 0)


def _record_counts(connection: sqlite3.Connection) -> dict[str, int]:
    if not _table_exists(connection, "records"):
        return {}
    counts = {key: 0 for key in MINDTOWER_RESOURCE_KEYS}
    cursor = connection.execute("SELECT resource, COUNT(*) FROM records GROUP BY resource")
    for resource, count in cursor.fetchall():
        counts[str(resource)] = int(count)
    return counts


def _credential_summary(connection: sqlite3.Connection) -> list[dict[str, str]]:
    if not _table_exists(connection, "records"):
        return []
    cursor = connection.execute(
        "SELECT payload FROM records WHERE resource = ? ORDER BY updated_at DESC LIMIT 6",
        ("credential-status",),
    )
    summary = []
    for (raw_payload,) in cursor.fetchall():
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            continue
        masked = _mask_payload(payload if isinstance(payload, dict) else {})
        summary.append(
            {
                "keyName": str(masked.get("key_name", masked.get("id", "credential"))),
                "status": str(masked.get("status", "unknown")),
                "details": str(masked.get("details", ""))[:160],
                "updatedAt": str(masked.get("updated_at", "")),
            }
        )
    return summary


def build_mindtower_fusion_snapshot(root: Path, db_path: Path | None = None) -> dict[str, Any]:
    database_path = db_path or _default_db_path(root)
    adapter: dict[str, Any] = {
        "adapterId": "mindtower-readonly-sqlite",
        "sourceProject": "Mind Tower",
        "sourcePath": str(database_path),
        "available": database_path.exists(),
        "readOnly": True,
        "writeActions": 0,
        "credentialValuesExposed": False,
        "status": "missing",
        "recordCounts": {},
        "eventCount": 0,
        "runtimeStateCount": 0,
        "credentialSummary": [],
    }
    if not database_path.exists():
        adapter["detail"] = "Mind Tower SQLite database was not found; fixture rows remain the fallback."
        return {"adapter": adapter, "rows": []}

    try:
        uri = f"file:{database_path.as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        try:
            adapter["recordCounts"] = _record_counts(connection)
            adapter["eventCount"] = _count_rows(connection, "events")
            adapter["runtimeStateCount"] = _count_rows(connection, "runtime_state")
            adapter["credentialSummary"] = _credential_summary(connection)
        finally:
            connection.close()
    except sqlite3.Error as exc:
        adapter["status"] = "error"
        adapter["detail"] = f"Mind Tower SQLite read failed: {exc}"
        return {"adapter": adapter, "rows": []}

    resource_count = sum(int(value or 0) for value in adapter["recordCounts"].values())
    adapter["status"] = "ready" if resource_count else "empty"
    adapter["detail"] = (
        f"Read-only adapter found {resource_count} records, "
        f"{adapter['eventCount']} events, and {adapter['runtimeStateCount']} runtime-state rows."
    )
    rows = [
        {
            "id": "mindtower-readonly-sqlite-adapter",
            "sourceProject": "Mind Tower",
            "sourcePath": str(database_path),
            "sourceHashPrefix": "",
            "collectionMode": "read-only-adapter",
            "riskLabel": "no-credential-copy",
            "status": "ready-for-adapter-shape" if resource_count else "needs-data",
            "title": "Mind Tower read-only source and event adapter",
            "summary": adapter["detail"],
            "proofNeed": "Counts and credential status are read from SQLite in read-only mode; credential values stay masked and no writes are exposed.",
            "nextSlice": "Promote selected Mind Tower source health and summary job rows into Fluxio bridge health cards.",
            "lastVerifiedAt": "2026-06-21",
            "adapter": adapter,
        }
    ]
    return {"adapter": adapter, "rows": rows}
