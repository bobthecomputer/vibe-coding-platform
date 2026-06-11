from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKING_ROOT = Path.cwd().resolve()
ROOT = (
    WORKING_ROOT
    if (WORKING_ROOT / ".agent_control").exists()
    and (WORKING_ROOT / "src" / "grant_agent").exists()
    else SCRIPT_ROOT
)
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from grant_agent.system_audit import (
    _load_live_mission_detail_status_evidence,
    _load_live_mission_output_quality_evidence,
)


DEFAULT_OUTPUT = ROOT / ".agent_control" / "mission_artifact_repair_plan_latest.json"
NAS_STORAGE_PRESSURE_PATH = Path(".agent_control") / "nas_storage_pressure_latest.json"
MISSION_EVIDENCE_MANIFEST_PATH = Path(".agent_control") / "mission_evidence_manifest_latest.json"


HARD_GATE_CHECKS = [
    "A concrete runtime-output body is visible in the selected Agent thread.",
    "At least one served artifact, artifact path, or preview URL is returned by the mission detail endpoint.",
    "Workbench artifact execution state is not `missing` for the selected mission.",
    "A screenshot or verifier receipt is attached after opening the artifact from Workbench.",
]


def _repair_prompt(row: dict[str, Any]) -> str:
    mission_id = str(row.get("missionId") or "").strip()
    title = str(row.get("title") or mission_id or "mission").strip()
    return (
        f"Resume {mission_id} ({title}) with a hard artifact gate. "
        "Do not mark the mission completed until the selected Agent thread contains a concrete runtime-output body "
        "and the Workbench artifact execution surface has a served artifact, artifact path, or preview URL. "
        "If the original scope cannot produce an interactive artifact, write a reviewable report artifact and attach "
        "a verifier receipt proving it opened from Workbench."
    )


def _repair_reason(row: dict[str, Any]) -> str:
    status = str(row.get("status") or "unknown").strip() or "unknown"
    artifact_gate = row.get("artifactGate") if isinstance(row.get("artifactGate"), dict) else {}
    runtime_transcript = row.get("runtimeTranscript") if isinstance(row.get("runtimeTranscript"), dict) else {}
    artifact_gate_status = str(row.get("artifactGateStatus") or artifact_gate.get("status") or "").strip()
    transcript_status = str(row.get("runtimeTranscriptStatus") or runtime_transcript.get("status") or "").strip()
    runtime_output_count = int(row.get("runtimeOutputCount") or artifact_gate.get("runtimeOutputCount") or 0)
    artifact_count = int(row.get("artifactCount") or artifact_gate.get("artifactCount") or 0)
    artifact_status = str(row.get("artifactStatus") or ("returned" if artifact_count > 0 else "")).strip()
    parts = [f"mission status `{status}`"]
    if artifact_gate_status:
        parts.append(f"artifact gate `{artifact_gate_status}`")
    if transcript_status:
        parts.append(f"runtime transcript `{transcript_status}`")
    if runtime_output_count <= 0:
        parts.append("no concrete runtime-output body")
    if artifact_status == "none_returned":
        parts.append("no served artifact or artifact path")
    return "; ".join(parts)


def _row_needs_repair(row: dict[str, Any]) -> bool:
    status = str(row.get("status") or "").lower()
    artifact_gate = row.get("artifactGate") if isinstance(row.get("artifactGate"), dict) else {}
    runtime_transcript = row.get("runtimeTranscript") if isinstance(row.get("runtimeTranscript"), dict) else {}
    artifact_gate_status = str(row.get("artifactGateStatus") or artifact_gate.get("status") or "").lower()
    transcript_status = str(row.get("runtimeTranscriptStatus") or runtime_transcript.get("status") or "").lower()
    runtime_output_count = int(row.get("runtimeOutputCount") or artifact_gate.get("runtimeOutputCount") or 0)
    artifact_count = int(row.get("artifactCount") or artifact_gate.get("artifactCount") or 0)
    artifact_status = str(row.get("artifactStatus") or ("returned" if artifact_count > 0 else "")).lower()
    missing_runtime_output = runtime_output_count <= 0
    missing_artifact = artifact_status in {"none_returned", "missing", ""}
    transcript_missing_runtime_output = transcript_status in {
        "missing_runtime_output",
        "missing_required_output",
        "missing_transcript",
        "missing",
        "",
    }
    passed_with_runtime_output = (
        artifact_gate_status in {"passed", "ok", "clear"}
        and runtime_output_count > 0
        and not transcript_missing_runtime_output
    )
    return bool(
        row.get("weakOutput")
        or artifact_gate_status in {"missing_required_output", "failed", "blocked"}
        or (
            status == "completed"
            and not passed_with_runtime_output
            and (
                missing_runtime_output
                or missing_artifact
                or transcript_status in {"missing_transcript", "missing"}
            )
        )
        or (
            status in {"running", "delegated", "active"}
            and transcript_missing_runtime_output
            and missing_artifact
        )
        or (
            status in {"verification_failed", "failed", "blocked", "paused"}
            and (
                missing_runtime_output
                or missing_artifact
                or transcript_missing_runtime_output
            )
        )
    )


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_nas_storage_pressure(root: Path) -> dict[str, Any]:
    path = root / NAS_STORAGE_PRESSURE_PATH
    payload = _load_json_file(path)
    if payload.get("schema") != "fluxio.nas_storage_pressure.v1":
        return {}
    checked_at = str(payload.get("checkedAt") or "")
    try:
        checked_ts = datetime.fromisoformat(checked_at.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return {}
    max_age_seconds = int(payload.get("maxAgeSeconds") or 48 * 60 * 60)
    if datetime.now(timezone.utc).timestamp() - checked_ts > max_age_seconds:
        return {}
    payload["sourcePath"] = str(path.resolve())
    return payload


def _load_mission_evidence_screenshot_manifest(root: Path) -> dict[str, Any]:
    path = root / MISSION_EVIDENCE_MANIFEST_PATH
    payload = _load_json_file(path)
    if payload.get("schema") != "fluxio.mission_evidence_screenshot_manifest.v1":
        return {}
    source_checked_at = str(payload.get("sourceCheckedAt") or payload.get("generatedAt") or "")
    try:
        checked_ts = datetime.fromisoformat(source_checked_at.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return {}
    max_age_seconds = int(payload.get("maxAgeSeconds") or 7 * 24 * 60 * 60)
    if datetime.now(timezone.utc).timestamp() - checked_ts > max_age_seconds:
        return {}
    payload["sourcePath"] = str(path.resolve())
    return payload


def _mission_evidence_screenshot_path(root: Path, mission_id: str) -> str:
    manifest = _load_mission_evidence_screenshot_manifest(root)
    for row in manifest.get("screenshots", []) if isinstance(manifest.get("screenshots"), list) else []:
        if not isinstance(row, dict):
            continue
        if str(row.get("missionId") or "") != mission_id:
            continue
        path = Path(str(row.get("screenshotPath") or ""))
        if path.exists():
            return str(path.resolve())
    screenshot_dir = root / ".agent_control" / "mission_result_screenshots"
    candidates = sorted(
        screenshot_dir.glob(f"*{mission_id}*.png"),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    for path in candidates:
        return str(path.resolve())
    return ""


def _nas_storage_preflight(root: Path) -> dict[str, Any]:
    pressure = _load_nas_storage_pressure(root)
    if not pressure:
        return {
            "schema": "fluxio.mission_artifact_repair_storage_preflight.v1",
            "status": "unknown",
            "canResume": True,
            "nextAction": "No fresh NAS storage pressure evidence was found for mission artifact repair.",
        }
    status = str(pressure.get("status") or "").strip().lower()
    critical = (
        status in {"critical", "full"}
        or bool(pressure.get("probeTimedOut"))
        or bool(pressure.get("probeConnectFailed"))
        or ("availableBytes" in pressure and int(pressure.get("availableBytes") or 0) <= 0)
        or ("usedPercent" in pressure and int(pressure.get("usedPercent") or 0) >= 99)
    )
    return {
        "schema": "fluxio.mission_artifact_repair_storage_preflight.v1",
        "status": "blocked" if critical else "passed",
        "canResume": not critical,
        "storage": {
            "host": pressure.get("host", ""),
            "mount": pressure.get("mount", "/volume1/Saclay"),
            "status": pressure.get("status", "critical" if critical else "unknown"),
            "probeTimedOut": bool(pressure.get("probeTimedOut")),
            "probeConnectFailed": bool(pressure.get("probeConnectFailed")),
            "measuredUsageAvailable": bool(pressure.get("measuredUsageAvailable", True)),
            "usedPercent": int(pressure.get("usedPercent") or 0),
            "availableBytes": int(pressure.get("availableBytes") or 0),
            "source": pressure.get("source", ""),
            "sourcePath": pressure.get("sourcePath", ""),
            "cleanupPlanPath": pressure.get("cleanupPlanPath", ""),
        },
        "nextAction": (
            "Do not resume hard artifact repair missions until NAS storage/I/O pressure clears."
            if critical
            else "NAS storage preflight passed for mission artifact repair."
        ),
    }


def build_repair_plan(root: Path) -> dict[str, Any]:
    root = root.resolve()
    quality = _load_live_mission_output_quality_evidence(root)
    weak_rows = quality.get("weakMissionRows", []) if isinstance(quality.get("weakMissionRows"), list) else []
    repair_rows = quality.get("repairMissionRows", []) if isinstance(quality.get("repairMissionRows"), list) else []
    detail_status = _load_live_mission_detail_status_evidence(root)
    detail_rows = (
        detail_status.get("missionRows", [])
        if isinstance(detail_status.get("missionRows"), list)
        else []
    )
    candidate_rows: dict[str, dict[str, Any]] = {}
    for row in [*repair_rows, *weak_rows, *detail_rows]:
        if not isinstance(row, dict):
            continue
        mission_id = str(row.get("missionId") or "").strip()
        if mission_id and _row_needs_repair(row):
            candidate_rows[mission_id] = row
    storage_preflight = _nas_storage_preflight(root)
    can_resume = bool(storage_preflight.get("canResume", True))
    screenshot_manifest = _load_mission_evidence_screenshot_manifest(root)
    repairs: list[dict[str, Any]] = []
    for index, row in enumerate(candidate_rows.values(), start=1):
        if not isinstance(row, dict):
            continue
        mission_id = str(row.get("missionId") or "").strip()
        if not mission_id:
            continue
        screenshot_path = str(row.get("screenshotPath") or "") or _mission_evidence_screenshot_path(root, mission_id)
        repairs.append(
            {
                "missionId": mission_id,
                "title": str(row.get("title") or mission_id),
                "runtime": str(row.get("runtime") or "hermes"),
                "status": str(row.get("status") or "unknown"),
                "priority": index,
                "sourceReportPath": str(row.get("reportPath") or ""),
                "sourceScreenshotPath": screenshot_path,
                "observedAgentMessageCount": int(row.get("agentMessageCount") or 0),
                "observedRuntimeOutputCount": int(
                    row.get("runtimeOutputCount")
                    or (row.get("artifactGate") if isinstance(row.get("artifactGate"), dict) else {}).get("runtimeOutputCount")
                    or 0
                ),
                "observedArtifactStatus": str(
                    row.get("artifactStatus")
                    or (
                        "returned"
                        if int(
                            row.get("artifactCount")
                            or (row.get("artifactGate") if isinstance(row.get("artifactGate"), dict) else {}).get("artifactCount")
                            or 0
                        )
                        > 0
                        else "unknown"
                    )
                ),
                "artifactGateStatus": str(
                    row.get("artifactGateStatus")
                    or (row.get("artifactGate") if isinstance(row.get("artifactGate"), dict) else {}).get("status")
                    or ""
                ),
                "runtimeTranscriptStatus": str(
                    row.get("runtimeTranscriptStatus")
                    or (row.get("runtimeTranscript") if isinstance(row.get("runtimeTranscript"), dict) else {}).get("status")
                    or ""
                ),
                "repairReason": _repair_reason(row),
                "action": "resume_with_hard_artifact_gate",
                "canResumeNow": can_resume,
                "resumeBlockedBy": [] if can_resume else ["nas_storage_pressure"],
                "hardGateChecks": HARD_GATE_CHECKS,
                "resumePrompt": _repair_prompt(row),
                "verificationCommand": (
                    "python scripts/verify_authenticated_live_agent.py "
                    f"--mission-id {mission_id}"
                ),
            }
        )
    return {
        "schema": "fluxio.mission_artifact_repair_plan.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "live_mission_output_quality",
        "sourceCheckedAt": str(quality.get("checkedAt") or ""),
        "liveDetailCheckedAt": str(detail_status.get("checkedAt") or ""),
        "missionEvidenceScreenshotManifest": {
            "sourcePath": str(screenshot_manifest.get("sourcePath") or ""),
            "sourceCheckedAt": str(screenshot_manifest.get("sourceCheckedAt") or ""),
            "screenshotCount": int(screenshot_manifest.get("screenshotCount") or 0),
        } if screenshot_manifest else {},
        "status": (
            "repairs_blocked_by_nas_storage"
            if repairs and not can_resume
            else "repairs_ready"
            if repairs
            else "passed"
        ),
        "weakMissionCount": len(repairs),
        "repairMissionCount": len(repairs),
        "repairs": repairs,
        "storagePreflight": storage_preflight,
        "hardGateChecks": HARD_GATE_CHECKS,
        "nextAction": (
            storage_preflight.get("nextAction", "Free NAS storage before resuming mission artifact repairs.")
            if repairs and not can_resume
            else (
            "Resume the listed missions with the hard artifact gate before counting them as useful completed work."
            if repairs
            else "No transcript-only completed missions are present in current authenticated verifier evidence."
            )
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a hard artifact-gate repair plan for transcript-only missions.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    payload = build_repair_plan(root)
    if args.write:
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        payload["outputPath"] = str(output.resolve())
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
