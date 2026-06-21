from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DELEGATED_RUNTIME_PROOF_SCHEMA = "delegated-runtime-proof.v1"
TERMINAL_RUNTIME_STATUSES = {"completed", "failed", "stopped"}


def _path_exists(value: str) -> bool:
    raw = str(value or "").strip()
    return bool(raw) and Path(raw).exists()


def _read_event_count(events_path: str) -> int:
    raw = str(events_path or "").strip()
    if not raw:
        return 0
    path = Path(raw)
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            if raw_line.strip():
                count += 1
    return count


def _terminal_status_ok(status: str, exit_code: int | None) -> bool:
    if status == "completed":
        return exit_code == 0
    if status == "failed":
        return exit_code not in {None, 0}
    if status == "stopped":
        return True
    return False


def _intent_alignment_from_session(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get("intent_alignment")
    if not isinstance(raw, dict):
        raw = session.get("intentAlignment") if isinstance(session.get("intentAlignment"), dict) else {}
    if raw:
        return {
            "schemaVersion": str(raw.get("schemaVersion") or "mission-intent-alignment.v1"),
            "status": str(raw.get("status") or "unknown"),
            "source": str(raw.get("source") or "delegated_runtime_session"),
            "objectiveExcerpt": str(raw.get("objectiveExcerpt") or raw.get("originalUserIntent") or ""),
            "routeReason": str(raw.get("routeReason") or raw.get("driftReason") or ""),
            "selectedSkillId": str(raw.get("selectedSkillId") or raw.get("selectedSkill") or ""),
            "checkedAt": str(raw.get("checkedAt") or raw.get("updatedAt") or ""),
        }
    objective = str(session.get("objective") or session.get("mission_objective") or "").strip()
    route_reason = str(session.get("route_reason") or session.get("target_reason") or "").strip()
    selected_skill = str(session.get("selected_skill_id") or session.get("selectedSkillId") or "").strip()
    if not any([objective, route_reason, selected_skill]):
        return {}
    return {
        "schemaVersion": "mission-intent-alignment.v1",
        "status": "unknown",
        "source": "delegated_runtime_session",
        "objectiveExcerpt": objective[:180],
        "routeReason": route_reason,
        "selectedSkillId": selected_skill,
        "checkedAt": str(session.get("updated_at") or session.get("created_at") or ""),
    }


def build_delegated_runtime_proof_receipt(session: dict[str, Any]) -> dict[str, Any]:
    status = str(session.get("status") or "").strip().lower()
    exit_code = session.get("exit_code")
    if exit_code is not None:
        try:
            exit_code = int(exit_code)
        except (TypeError, ValueError):
            exit_code = None
    events_path = str(session.get("events_path") or "")
    log_path = str(session.get("log_path") or "")
    session_path = str(session.get("session_path") or "")
    changed_files = session.get("changed_files")
    if not isinstance(changed_files, list):
        changed_files = []
    event_count = int(session.get("event_cursor") or 0) or _read_event_count(events_path)
    artifact_checks = {
        "session": _path_exists(session_path),
        "events": _path_exists(events_path),
        "log": _path_exists(log_path),
    }
    terminal_ok = _terminal_status_ok(status, exit_code)
    artifact_ok = all(artifact_checks.values())
    intent_alignment = _intent_alignment_from_session(session)
    return {
        "schemaVersion": DELEGATED_RUNTIME_PROOF_SCHEMA,
        "delegatedId": str(session.get("delegated_id") or ""),
        "runtimeId": str(session.get("runtime_id") or ""),
        "status": status,
        "terminal": status in TERMINAL_RUNTIME_STATUSES,
        "exitCode": exit_code,
        "createdAt": str(session.get("created_at") or ""),
        "updatedAt": str(session.get("updated_at") or ""),
        "sourceStepId": str(session.get("source_step_id") or ""),
        "route": {
            "phase": str(session.get("target_phase") or ""),
            "role": str(session.get("target_role") or ""),
            "provider": str(session.get("target_provider") or ""),
            "model": str(session.get("target_model") or ""),
            "effort": str(session.get("target_effort") or ""),
            "budgetClass": str(session.get("target_budget_class") or ""),
        },
        "intentAlignment": intent_alignment,
        "heartbeat": {
            "status": str(session.get("heartbeat_status") or "unknown"),
            "at": str(session.get("heartbeat_at") or ""),
            "ageSeconds": session.get("heartbeat_age_seconds"),
            "intervalSeconds": int(session.get("heartbeat_interval_seconds") or 0),
        },
        "artifacts": {
            "sessionPath": session_path,
            "eventsPath": events_path,
            "logPath": log_path,
            "skillPayloadPath": str(session.get("skill_payload_path") or ""),
        },
        "artifactChecks": artifact_checks,
        "eventCount": event_count,
        "latestEvents": list(session.get("latest_events") or [])[-5:],
        "changedFiles": [str(item) for item in changed_files[:20]],
        "changedFileCount": len(changed_files),
        "approvalCount": len(session.get("approval_history") or []),
        "proofScope": "delegated_runtime_session_lifecycle",
        "safety": {
            "liveRuntimeExecution": status in TERMINAL_RUNTIME_STATUSES and event_count > 0,
            "liveModelCalls": False,
            "runtimeAdapterAdded": False,
            "openCodeGoRuntimeAdded": False,
            "secretsIncluded": False,
            "realTargetsAsserted": False,
        },
        "promotionGate": {
            "promotionBlocked": not (terminal_ok and artifact_ok),
            "terminalStatusVerified": terminal_ok,
            "artifactIntegrityVerified": artifact_ok,
            "eventLogObserved": event_count > 0,
            "intentAlignmentRecorded": bool(intent_alignment),
        },
    }


def verify_delegated_runtime_proof_receipt(
    receipt: dict[str, Any],
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    problems: list[str] = []
    if receipt.get("schemaVersion") != DELEGATED_RUNTIME_PROOF_SCHEMA:
        problems.append("schemaVersion mismatch")
    delegated_id = str(receipt.get("delegatedId") or "")
    runtime_id = str(receipt.get("runtimeId") or "")
    if not delegated_id:
        problems.append("delegatedId missing")
    if not runtime_id:
        problems.append("runtimeId missing")
    if session:
        if delegated_id != str(session.get("delegated_id") or ""):
            problems.append("delegatedId does not match session")
        if runtime_id != str(session.get("runtime_id") or ""):
            problems.append("runtimeId does not match session")
    status = str(receipt.get("status") or "")
    exit_code = receipt.get("exitCode")
    if not _terminal_status_ok(status, exit_code if isinstance(exit_code, int) else None):
        problems.append("terminal status and exit code are inconsistent")
    artifacts = receipt.get("artifacts") if isinstance(receipt.get("artifacts"), dict) else {}
    for key in ("sessionPath", "eventsPath", "logPath"):
        if not _path_exists(str(artifacts.get(key) or "")):
            problems.append(f"{key} missing")
    if int(receipt.get("eventCount") or 0) <= 0:
        problems.append("event log is empty")
    safety = receipt.get("safety") if isinstance(receipt.get("safety"), dict) else {}
    if safety.get("runtimeAdapterAdded"):
        problems.append("receipt must not claim a new runtime adapter")
    if safety.get("secretsIncluded"):
        problems.append("receipt must not include secrets")
    return {
        "schemaVersion": "delegated-runtime-proof-verification.v1",
        "passed": not problems,
        "problems": problems,
    }


def write_delegated_runtime_proof_receipt(
    path: Path,
    session: dict[str, Any],
) -> dict[str, Any]:
    receipt = build_delegated_runtime_proof_receipt(session)
    receipt["verification"] = verify_delegated_runtime_proof_receipt(receipt, session)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return receipt
