from __future__ import annotations

import hashlib
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

PREVIEW_LIMIT = 4
SOLANTIR_SIGNAL_SOURCE_SPECS = [
    {
        "id": "solantir-backend-signal-legacy-drivers",
        "relativePath": Path("legacy") / "osint-platform" / "backend" / "solantir_api" / "signals.py",
        "entity": "Solantir Legacy Signal Drivers",
        "direction": "upside-watch",
        "baseScore": 64,
    },
    {
        "id": "solantir-backend-signal-contract-provenance",
        "relativePath": Path("packages") / "contracts" / "src" / "solantir.ts",
        "entity": "Solantir Contract Provenance",
        "direction": "neutral",
        "baseScore": 58,
    },
]


def _default_db_path(root: Path) -> Path:
    configured = os.environ.get("MINDTOWER_DB_PATH", "").strip()
    if configured:
        return Path(configured)
    return root.parent / "mind-tower" / "data" / "mindtower.sqlite"


def _default_solantir_root(root: Path) -> Path:
    configured = os.environ.get("SOLANTIR_ROOT_PATH", "").strip()
    if configured:
        return Path(configured)
    return root.parent / "Solantir"


def _hash_prefix(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()[:12]


def _keyword_hits(text: str, keywords: list[str]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword in lowered)


def build_solantir_signal_snapshots(
    root: Path,
    solantir_root: Path | None = None,
) -> list[dict[str, Any]]:
    source_root = solantir_root or _default_solantir_root(root)
    snapshots: list[dict[str, Any]] = []
    for spec in SOLANTIR_SIGNAL_SOURCE_SPECS:
        source_path = source_root / spec["relativePath"]
        if not source_path.exists() or not source_path.is_file():
            continue
        try:
            text = source_path.read_text(encoding="utf-8", errors="ignore")
            source_hash = _hash_prefix(source_path)
        except OSError:
            continue
        provenance_hits = _keyword_hits(text, ["provenance", "source", "confidence", "signal"])
        safety_hits = _keyword_hits(text, ["readonly", "read-only", "risk", "forecast", "observation"])
        size_bonus = min(12, max(0, source_path.stat().st_size // 800))
        score = max(0, min(100, int(spec["baseScore"]) + provenance_hits * 3 + safety_hits * 2 + size_bonus))
        confidence = min(0.92, 0.54 + provenance_hits * 0.045 + safety_hits * 0.035)
        snapshots.append(
            {
                "id": spec["id"],
                "entity": spec["entity"],
                "direction": spec["direction"],
                "score": score,
                "confidence": round(confidence, 2),
                "timestamp": "2026-06-21T00:00:00Z",
                "collectionMode": "read-only-adapter",
                "riskLabel": "no-trading-execution",
                "sourceProject": "Solantir",
                "sourcePath": str(source_path),
                "sourceHashPrefix": source_hash,
                "factors": [
                    {
                        "name": "provenance coverage",
                        "weight": 0.4,
                        "contribution": min(24, provenance_hits * 5),
                    },
                    {
                        "name": "driver explainability",
                        "weight": 0.32,
                        "contribution": min(20, safety_hits * 4),
                    },
                    {
                        "name": "source file presence",
                        "weight": 0.28,
                        "contribution": max(6, size_bonus),
                    },
                ],
                "topDrivers": [
                    f"Read-only backend adapter found {source_path.name} and recorded hash {source_hash}.",
                    "No broker, order routing, credential, or live market execution path is exposed.",
                ],
                "safetyLabels": ["no broker", "no order routing", "not investment advice"],
            }
        )
    return snapshots


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


def _load_record_payloads(
    connection: sqlite3.Connection,
    resource: str,
    *,
    limit: int = PREVIEW_LIMIT,
) -> list[dict[str, Any]]:
    if not _table_exists(connection, "records"):
        return []
    cursor = connection.execute(
        """
        SELECT id, payload, updated_at
        FROM records
        WHERE resource = ?
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (resource, limit),
    )
    records: list[dict[str, Any]] = []
    for record_id, raw_payload, updated_at in cursor.fetchall():
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        masked = _mask_payload(payload)
        records.append(
            {
                "id": str(masked.get("id") or record_id),
                "label": str(masked.get("label") or masked.get("name") or record_id),
                "status": str(masked.get("status") or masked.get("state") or "unknown"),
                "detail": str(
                    masked.get("description")
                    or masked.get("summary")
                    or masked.get("details")
                    or ""
                )[:180],
                "updatedAt": str(masked.get("updated_at") or updated_at or ""),
            }
        )
    return records


def _recent_events(connection: sqlite3.Connection, *, limit: int = PREVIEW_LIMIT) -> list[dict[str, Any]]:
    if not _table_exists(connection, "events"):
        return []
    cursor = connection.execute(
        """
        SELECT id, source_type, source_id, author, published_at, content, url, priority_score
        FROM events
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    events: list[dict[str, Any]] = []
    for row in cursor.fetchall():
        event_id, source_type, source_id, author, published_at, content, url, priority_score = row
        events.append(
            {
                "id": str(event_id),
                "sourceType": str(source_type),
                "sourceId": str(source_id),
                "author": str(author),
                "publishedAt": str(published_at),
                "contentPreview": str(content or "")[:180],
                "url": str(url),
                "priorityScore": int(priority_score or 0),
            }
        )
    return events


def _runtime_state_preview(
    connection: sqlite3.Connection,
    *,
    limit: int = PREVIEW_LIMIT,
) -> list[dict[str, str]]:
    if not _table_exists(connection, "runtime_state"):
        return []
    cursor = connection.execute(
        """
        SELECT namespace, key, value, updated_at
        FROM runtime_state
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    preview: list[dict[str, str]] = []
    for namespace, key, value, updated_at in cursor.fetchall():
        masked = _mask_payload({str(key): value})
        preview.append(
            {
                "namespace": str(namespace),
                "key": str(key),
                "valuePreview": str(masked.get(str(key), ""))[:160],
                "updatedAt": str(updated_at),
            }
        )
    return preview


def build_fusion_evidence_packets(
    adapter: dict[str, Any],
    signal_snapshots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if (
        not adapter.get("available")
        or adapter.get("readOnly") is False
        or int(adapter.get("writeActions") or 0) != 0
        or adapter.get("credentialValuesExposed")
        or not signal_snapshots
    ):
        return []

    source_health = adapter.get("sourceHealth") if isinstance(adapter.get("sourceHealth"), list) else []
    summary_jobs = adapter.get("summaryJobs") if isinstance(adapter.get("summaryJobs"), list) else []
    recent_events = adapter.get("recentEvents") if isinstance(adapter.get("recentEvents"), list) else []
    if not source_health and not summary_jobs and not recent_events:
        return []

    evidence_count = len(source_health) + len(summary_jobs) + len(recent_events)
    packets: list[dict[str, Any]] = []
    for index, signal in enumerate(signal_snapshots[:3]):
        confidence = float(signal.get("confidence") or 0)
        support_score = min(0.18, evidence_count * 0.025)
        packet_confidence = round(min(0.95, confidence * 0.72 + support_score), 2)
        source = source_health[index % len(source_health)] if source_health else {}
        event = recent_events[index % len(recent_events)] if recent_events else {}
        job = summary_jobs[index % len(summary_jobs)] if summary_jobs else {}
        packets.append(
            {
                "id": f"fusion-evidence-{signal.get('id', index)}",
                "status": "review-ready",
                "title": f"{signal.get('entity', 'Solantir signal')} evidence packet",
                "sourceProjects": ["Mind Tower", "Solantir"],
                "collectionMode": "read-only-adapter",
                "riskLabel": "no-trading-execution",
                "confidence": packet_confidence,
                "signalSnapshotId": signal.get("id", ""),
                "signalEntity": signal.get("entity", ""),
                "signalScore": signal.get("score", 0),
                "signalDirection": signal.get("direction", ""),
                "matchedEvidence": [
                    {
                        "kind": "mindtower-source-health",
                        "id": source.get("id", "source-health-unavailable"),
                        "label": source.get("label", "Source health unavailable"),
                        "status": source.get("status", "unavailable"),
                    },
                    {
                        "kind": "mindtower-event",
                        "id": event.get("id", "event-unavailable"),
                        "label": event.get("sourceType", "No recent event"),
                        "status": str(event.get("priorityScore", "unavailable")),
                    },
                    {
                        "kind": "mindtower-summary-job",
                        "id": job.get("id", "summary-job-unavailable"),
                        "label": job.get("label", "Summary job unavailable"),
                        "status": job.get("status", "unavailable"),
                    },
                ],
                "provenance": {
                    "mindTowerSourcePath": adapter.get("sourcePath", ""),
                    "solantirSourcePath": signal.get("sourcePath", ""),
                    "solantirSourceHashPrefix": signal.get("sourceHashPrefix", ""),
                },
                "safetyLabels": [
                    "read-only",
                    "no-trading-execution",
                    "no-credential-copy",
                    "review-only",
                ],
                "acceptanceRule": "Review-only no-trading-execution correlation packet; it cannot place trades, copy credentials, or write back to either project.",
            }
        )
    return packets


def build_mindtower_fusion_snapshot(
    root: Path,
    db_path: Path | None = None,
    solantir_root: Path | None = None,
) -> dict[str, Any]:
    database_path = db_path or _default_db_path(root)
    signal_snapshots = build_solantir_signal_snapshots(root, solantir_root=solantir_root)
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
        "sourceHealth": [],
        "summaryJobs": [],
        "recentEvents": [],
        "runtimeStatePreview": [],
    }
    if not database_path.exists():
        adapter["detail"] = "Mind Tower SQLite database was not found; fixture rows remain the fallback."
        return {"adapter": adapter, "rows": [], "signalSnapshots": signal_snapshots, "fusionEvidencePackets": []}

    try:
        uri = f"file:{database_path.as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        try:
            adapter["recordCounts"] = _record_counts(connection)
            adapter["eventCount"] = _count_rows(connection, "events")
            adapter["runtimeStateCount"] = _count_rows(connection, "runtime_state")
            adapter["credentialSummary"] = _credential_summary(connection)
            adapter["sourceHealth"] = _load_record_payloads(connection, "sources")
            adapter["summaryJobs"] = _load_record_payloads(connection, "summary-jobs")
            adapter["recentEvents"] = _recent_events(connection)
            adapter["runtimeStatePreview"] = _runtime_state_preview(connection)
        finally:
            connection.close()
    except sqlite3.Error as exc:
        adapter["status"] = "error"
        adapter["detail"] = f"Mind Tower SQLite read failed: {exc}"
        return {"adapter": adapter, "rows": [], "signalSnapshots": signal_snapshots, "fusionEvidencePackets": []}

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
    return {
        "adapter": adapter,
        "rows": rows,
        "signalSnapshots": signal_snapshots,
        "fusionEvidencePackets": build_fusion_evidence_packets(adapter, signal_snapshots),
    }
