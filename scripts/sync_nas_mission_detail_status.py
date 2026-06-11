from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.sync_nas_system_audit import (  # noqa: E402
    DEFAULT_REMOTE_PYTHON,
    DEFAULT_REMOTE_ROOT,
    _connect_nas_client,
    _load_nas_credentials,
    _paramiko,
    _run_remote_bash_script,
)


DEFAULT_OUTPUT = ROOT / ".agent_control" / "live_mission_detail_status_latest.json"
DEFAULT_SELECTED_MISSION_LIMIT = 12
TASK_TYPE_TO_FAMILY = {
    "data_f1_analytics": "f1_data_analytics",
    "frontend_design": "frontend_mobile_ui",
    "hardware_electrical": "hardware_electrical",
    "research_analysis": "public_data_investigation",
    "security_red_team": "security_red_team",
}


def _real_runtime_report_count(messages: list[Any]) -> int:
    count = 0
    for item in messages:
        if not isinstance(item, dict):
            continue
        if bool(item.get("traceOnly")):
            continue
        label = str(item.get("label") or item.get("roleLabel") or "").lower()
        role = str(item.get("role") or "").lower()
        detail = "\n".join(
            str(item.get(key) or "").strip()
            for key in ("detail", "message", "content", "technicalDetail")
            if str(item.get(key) or "").strip()
        )
        if not detail:
            continue
        if (
            "hermes session transcript" in label
            or "hermes runtime output" in label
            or "hermes runtime evidence" in label
            or "runtime output:" in detail.lower()
            or (bool(item.get("processMessage")) and role in {"runtime", "assistant"})
        ):
            count += 1
    return count


def _trace_only_message_count(messages: list[Any]) -> int:
    return sum(1 for item in messages if isinstance(item, dict) and bool(item.get("traceOnly")))


def _state_dict(mission: Any) -> dict[str, Any]:
    state = getattr(mission, "state", None)
    if is_dataclass(state):
        return asdict(state)
    return state if isinstance(state, dict) else {}


def _route_task_types(mission: Any) -> list[str]:
    values: list[str] = []
    for route in getattr(mission, "route_configs", None) or []:
        item = asdict(route) if is_dataclass(route) else (route if isinstance(route, dict) else {})
        task_type = str(item.get("task_type") or item.get("taskType") or "").strip()
        if task_type:
            values.append(task_type)
    state = _state_dict(mission)
    feedback = state.get("operator_value_feedback") if isinstance(state.get("operator_value_feedback"), dict) else {}
    feedback_task_type = str(feedback.get("routeTrustTaskType") or "").strip()
    if feedback_task_type:
        values.append(feedback_task_type)
    return sorted(set(values))


def _mission_task_family(mission: Any) -> str:
    route_types = _route_task_types(mission)
    title = str(getattr(mission, "title", "") or "")
    objective = str(getattr(mission, "objective", "") or "")
    workspace = str(getattr(mission, "workspace_id", "") or "")
    text = " ".join([title, objective, workspace]).lower()
    if re.search(r"\brf\b|\bwi-?fi\b|\bwireless\b|\bbluetooth\b|\bsdr\b|\bads-b\b|\bais\b", text):
        return "rf_wireless"
    if re.search(r"\bhardware\b|\belectrical\b|\bworkbench\b|\bbench\b|\bsensor\b|\bpcb\b|\bcircuit\b", text):
        return "hardware_electrical"
    if any(token in text for token in ("f1", "telemetry", "lap", "sector", "tire", "tyre")):
        return "f1_data_analytics"
    if any(token in text for token in ("public-data", "public data", "investigation", "geoint", "osint", "maritime", "supply-chain")):
        return "public_data_investigation"
    if any(token in text for token in ("red-team", "red team", "security", "defensive hardening")):
        return "security_red_team"
    for task_type in route_types:
        family = TASK_TYPE_TO_FAMILY.get(task_type)
        if family:
            return family
    if any(token in text for token in ("phone", "tablet", "builder progress", "frontend", "ui", "workbench")):
        return "frontend_mobile_ui"
    return ""


def _mission_sort_key(mission: Any) -> tuple[int, int, int, int, int, str]:
    state = _state_dict(mission)
    feedback = state.get("operator_value_feedback") if isinstance(state.get("operator_value_feedback"), dict) else {}
    score = int(feedback.get("score") or 0)
    status = str(state.get("status") or "").lower()
    proof = getattr(mission, "proof", None)
    changed_files = getattr(proof, "changed_files", None) if proof is not None else []
    artifacts = getattr(proof, "artifacts", None) if proof is not None else []
    created_at = str(getattr(mission, "created_at", "") or "")
    return (
        1 if status == "running" else 0,
        1 if status == "completed" else 0,
        1 if score >= 80 else 0,
        1 if changed_files or artifacts else 0,
        score,
        created_at,
    )


def _select_live_mission_ids_from_store(store: Any, *, limit: int = DEFAULT_SELECTED_MISSION_LIMIT) -> list[str]:
    by_family: dict[str, Any] = {}
    extras: list[Any] = []
    for mission in store.load_missions():
        runtime_id = str(getattr(mission, "runtime_id", "") or "").lower()
        if runtime_id != "hermes":
            continue
        state = _state_dict(mission)
        status = str(state.get("status") or "").lower()
        if status not in {"running", "delegated", "active", "completed"}:
            continue
        family = _mission_task_family(mission)
        if not family:
            continue
        current = by_family.get(family)
        if current is None or _mission_sort_key(mission) > _mission_sort_key(current):
            by_family[family] = mission
        extras.append(mission)
    selected: list[str] = []
    seen: set[str] = set()
    for family in (
        "frontend_mobile_ui",
        "f1_data_analytics",
        "rf_wireless",
        "public_data_investigation",
        "hardware_electrical",
        "security_red_team",
    ):
        mission = by_family.get(family)
        mission_id = str(getattr(mission, "mission_id", "") or "") if mission is not None else ""
        if mission_id and mission_id not in seen:
            selected.append(mission_id)
            seen.add(mission_id)
    for mission in sorted(extras, key=_mission_sort_key, reverse=True):
        mission_id = str(getattr(mission, "mission_id", "") or "")
        if mission_id and mission_id not in seen:
            selected.append(mission_id)
            seen.add(mission_id)
        if len(selected) >= limit:
            break
    return selected


def _detail_row_from_store(store: Any, mission_id: str, missions_by_id: dict[str, Any]) -> dict[str, Any]:
    detail = store.build_mission_detail_snapshot(mission_id, event_limit=20)
    mission = detail.get("mission") if isinstance(detail.get("mission"), dict) else {}
    state = detail.get("state") if isinstance(detail.get("state"), dict) else {}
    stored_mission = missions_by_id.get(mission_id)
    route_task_types = _route_task_types(stored_mission) if stored_mission is not None else []
    task_family = _mission_task_family(stored_mission) if stored_mission is not None else ""
    feedback = state.get("operator_value_feedback") if isinstance(state.get("operator_value_feedback"), dict) else {}
    agent_messages = detail.get("agentMessages") or []
    messages = agent_messages if isinstance(agent_messages, list) else []
    artifact_gate = detail.get("artifactGate") if isinstance(detail.get("artifactGate"), dict) else {}
    runtime_transcript = (
        detail.get("runtimeTranscript")
        if isinstance(detail.get("runtimeTranscript"), dict)
        else {}
    )
    artifact_count = int(artifact_gate.get("artifactCount") or 0)
    return {
        "missionId": mission_id,
        "title": mission.get("title") or mission_id,
        "runtime": mission.get("runtime_id") or mission.get("runtimeId") or "",
        "status": state.get("status") or "",
        "objective": mission.get("objective") or "",
        "workspaceId": mission.get("workspace_id") or mission.get("workspaceId") or "",
        "routeTaskTypes": route_task_types,
        "routeTrustTaskType": str(feedback.get("routeTrustTaskType") or (route_task_types[0] if route_task_types else "")),
        "taskFamily": task_family,
        "plannerLoopStatus": state.get("planner_loop_status") or "",
        "latestSessionId": state.get("latest_session_id") or "",
        "agentMessages": len(messages),
        "checkedAt": detail.get("generatedAt") or "",
        "realRuntimeReportCount": _real_runtime_report_count(messages),
        "realRuntimeReportCountKnown": True,
        "traceOnlyMessageCount": _trace_only_message_count(messages),
        "runtimeTranscript": runtime_transcript,
        "artifactGate": artifact_gate,
        "runtimeTranscriptStatus": runtime_transcript.get("status") or "",
        "artifactGateStatus": artifact_gate.get("status") or "",
        "runtimeOutputCount": int(artifact_gate.get("runtimeOutputCount") or 0),
        "artifactCount": artifact_count,
        "artifactStatus": "returned" if artifact_count > 0 else "none_returned",
        "weakOutput": not bool(artifact_gate.get("passed")),
        "nextAction": detail.get("nextAction") or "",
    }


def _local_status_rows(root: Path, mission_ids: list[str]) -> list[dict[str, Any]]:
    from grant_agent.mission_control import ControlRoomStore

    store = ControlRoomStore(root)
    all_missions = list(store.load_missions())
    missions_by_id = {
        str(getattr(mission, "mission_id", "") or ""): mission
        for mission in all_missions
        if str(getattr(mission, "mission_id", "") or "")
    }
    selected_ids = mission_ids or _select_live_mission_ids_from_store(store)
    rows: list[dict[str, Any]] = []
    for mission_id in selected_ids:
        try:
            rows.append(_detail_row_from_store(store, mission_id, missions_by_id))
        except Exception as exc:  # pragma: no cover - reported in sync payload.
            rows.append({"missionId": mission_id, "error": str(exc)})
    return rows


def _remote_status_script(remote_root: str, remote_python: str, mission_ids: list[str]) -> str:
    ids_json = json.dumps(mission_ids)
    return f"""set -e
ROOT={json.dumps(remote_root)}
PY={json.dumps(remote_python)}
cd "$ROOT"
export PYTHONPATH="$ROOT/src:${{PYTHONPATH:-}}"
"$PY" - <<'PY'
import json
import re
from pathlib import Path
from dataclasses import asdict, is_dataclass
from grant_agent.mission_control import ControlRoomStore

root = Path({remote_root!r})
store = ControlRoomStore(root)
mission_ids = json.loads({ids_json!r})
all_missions = list(store.load_missions())
missions_by_id = {{
    str(getattr(mission, "mission_id", "") or ""): mission
    for mission in all_missions
    if str(getattr(mission, "mission_id", "") or "")
}}

TASK_TYPE_TO_FAMILY = {{
    "data_f1_analytics": "f1_data_analytics",
    "frontend_design": "frontend_mobile_ui",
    "hardware_electrical": "hardware_electrical",
    "research_analysis": "public_data_investigation",
    "security_red_team": "security_red_team",
}}


def _state_dict(mission):
    state = getattr(mission, "state", None)
    return asdict(state) if is_dataclass(state) else (state if isinstance(state, dict) else {{}})


def _route_task_types(mission):
    values = []
    for route in (getattr(mission, "route_configs", None) or []):
        item = asdict(route) if is_dataclass(route) else (route if isinstance(route, dict) else {{}})
        task_type = str(item.get("task_type") or item.get("taskType") or "").strip()
        if task_type:
            values.append(task_type)
    state = _state_dict(mission)
    feedback = state.get("operator_value_feedback") if isinstance(state.get("operator_value_feedback"), dict) else {{}}
    feedback_task_type = str(feedback.get("routeTrustTaskType") or "").strip()
    if feedback_task_type:
        values.append(feedback_task_type)
    return sorted(set(values))


def _mission_task_family(mission):
    route_types = _route_task_types(mission)
    title = str(getattr(mission, "title", "") or "")
    objective = str(getattr(mission, "objective", "") or "")
    workspace = str(getattr(mission, "workspace_id", "") or "")
    text = " ".join([title, objective, workspace]).lower()
    if re.search(r"\\brf\\b|\\bwi-?fi\\b|\\bwireless\\b|\\bbluetooth\\b|\\bsdr\\b|\\bads-b\\b|\\bais\\b", text):
        return "rf_wireless"
    if re.search(r"\\bhardware\\b|\\belectrical\\b|\\bworkbench\\b|\\bbench\\b|\\bsensor\\b|\\bpcb\\b|\\bcircuit\\b", text):
        return "hardware_electrical"
    if any(token in text for token in ("f1", "telemetry", "lap", "sector", "tire", "tyre")):
        return "f1_data_analytics"
    if any(token in text for token in ("public-data", "public data", "investigation", "geoint", "osint", "maritime", "supply-chain")):
        return "public_data_investigation"
    if any(token in text for token in ("red-team", "red team", "security", "defensive hardening")):
        return "security_red_team"
    for task_type in route_types:
        family = TASK_TYPE_TO_FAMILY.get(task_type)
        if family:
            return family
    if any(token in text for token in ("phone", "tablet", "builder progress", "frontend", "ui", "workbench")):
        return "frontend_mobile_ui"
    return ""


def _mission_sort_key(mission):
    state = _state_dict(mission)
    feedback = state.get("operator_value_feedback") if isinstance(state.get("operator_value_feedback"), dict) else {{}}
    score = int(feedback.get("score") or 0)
    status = str(state.get("status") or "").lower()
    proof = getattr(mission, "proof", None)
    changed_files = getattr(proof, "changed_files", None) if proof is not None else []
    artifacts = getattr(proof, "artifacts", None) if proof is not None else []
    created_at = str(getattr(mission, "created_at", "") or "")
    return (
        1 if status == "running" else 0,
        1 if status == "completed" else 0,
        1 if score >= 80 else 0,
        1 if changed_files or artifacts else 0,
        score,
        created_at,
    )


def _select_live_mission_ids(limit={DEFAULT_SELECTED_MISSION_LIMIT}):
    by_family = {{}}
    extras = []
    for mission in all_missions:
        runtime_id = str(getattr(mission, "runtime_id", "") or "").lower()
        if runtime_id != "hermes":
            continue
        state = _state_dict(mission)
        status = str(state.get("status") or "").lower()
        if status not in {{"running", "delegated", "active", "completed"}}:
            continue
        family = _mission_task_family(mission)
        if not family:
            continue
        current = by_family.get(family)
        if current is None or _mission_sort_key(mission) > _mission_sort_key(current):
            by_family[family] = mission
        extras.append(mission)
    selected = []
    seen = set()
    for family in (
        "frontend_mobile_ui",
        "f1_data_analytics",
        "rf_wireless",
        "public_data_investigation",
        "hardware_electrical",
        "security_red_team",
    ):
        mission = by_family.get(family)
        mission_id = str(getattr(mission, "mission_id", "") or "") if mission is not None else ""
        if mission_id and mission_id not in seen:
            selected.append(mission_id)
            seen.add(mission_id)
    for mission in sorted(extras, key=_mission_sort_key, reverse=True):
        mission_id = str(getattr(mission, "mission_id", "") or "")
        if mission_id and mission_id not in seen:
            selected.append(mission_id)
            seen.add(mission_id)
        if len(selected) >= limit:
            break
    return selected


if not mission_ids:
    mission_ids = _select_live_mission_ids()

rows = []
for mission_id in mission_ids:
    try:
        detail = store.build_mission_detail_snapshot(mission_id, event_limit=20)
    except Exception as exc:
        rows.append({{"missionId": mission_id, "error": str(exc)}})
        continue
    mission = detail.get("mission") if isinstance(detail.get("mission"), dict) else {{}}
    state = detail.get("state") if isinstance(detail.get("state"), dict) else {{}}
    stored_mission = missions_by_id.get(mission_id)
    route_task_types = _route_task_types(stored_mission) if stored_mission is not None else []
    task_family = _mission_task_family(stored_mission) if stored_mission is not None else ""
    feedback = state.get("operator_value_feedback") if isinstance(state.get("operator_value_feedback"), dict) else {{}}
    agent_messages = detail.get("agentMessages") or []
    real_runtime_report_count = 0
    trace_only_message_count = 0
    for item in (agent_messages if isinstance(agent_messages, list) else []):
        if not isinstance(item, dict):
            continue
        if bool(item.get("traceOnly")):
            trace_only_message_count += 1
            continue
        label = str(item.get("label") or item.get("roleLabel") or "").lower()
        role = str(item.get("role") or "").lower()
        detail_text = "\\n".join(
            str(item.get(key) or "").strip()
            for key in ("detail", "message", "content", "technicalDetail")
            if str(item.get(key) or "").strip()
        )
        if not detail_text:
            continue
        lowered_detail = detail_text.lower()
        if (
            "hermes session transcript" in label
            or "hermes runtime output" in label
            or "hermes runtime evidence" in label
            or "runtime output:" in lowered_detail
            or (bool(item.get("processMessage")) and role in {"runtime", "assistant"})
        ):
            real_runtime_report_count += 1
    rows.append({{
        "missionId": mission_id,
        "title": mission.get("title") or mission_id,
        "runtime": mission.get("runtime_id") or mission.get("runtimeId") or "",
        "status": state.get("status") or "",
        "objective": mission.get("objective") or "",
        "workspaceId": mission.get("workspace_id") or mission.get("workspaceId") or "",
        "routeTaskTypes": route_task_types,
        "routeTrustTaskType": str(feedback.get("routeTrustTaskType") or (route_task_types[0] if route_task_types else "")),
        "taskFamily": task_family,
        "plannerLoopStatus": state.get("planner_loop_status") or "",
        "latestSessionId": state.get("latest_session_id") or "",
        "agentMessages": len(agent_messages) if isinstance(agent_messages, list) else 0,
        "checkedAt": detail.get("generatedAt") or "",
        "realRuntimeReportCount": real_runtime_report_count,
        "realRuntimeReportCountKnown": True,
        "traceOnlyMessageCount": trace_only_message_count,
        "runtimeTranscript": detail.get("runtimeTranscript") or {{}},
        "artifactGate": detail.get("artifactGate") or {{}},
        "runtimeTranscriptStatus": (detail.get("runtimeTranscript") or {{}}).get("status") or "",
        "artifactGateStatus": (detail.get("artifactGate") or {{}}).get("status") or "",
        "runtimeOutputCount": int((detail.get("artifactGate") or {{}}).get("runtimeOutputCount") or 0),
        "artifactCount": int((detail.get("artifactGate") or {{}}).get("artifactCount") or 0),
        "artifactStatus": (
            "returned"
            if int((detail.get("artifactGate") or {{}}).get("artifactCount") or 0) > 0
            else "none_returned"
        ),
        "weakOutput": not bool((detail.get("artifactGate") or {{}}).get("passed")),
        "nextAction": detail.get("nextAction") or "",
    }})
print(json.dumps({{"missionRows": rows}}, indent=2))
PY
"""


def sync_status(
    root: Path,
    *,
    mission_ids: list[str],
    remote_root: str = DEFAULT_REMOTE_ROOT,
    remote_python: str = DEFAULT_REMOTE_PYTHON,
    runbook_path: Path | None = None,
    timeout: int = 90,
) -> dict[str, Any]:
    root = root.resolve()
    runbook_path = runbook_path or root / ".agent_control" / "NAS_ACCESS_RUNBOOK.md"
    if not runbook_path.exists() and (root / ".agent_control" / "missions.json").exists():
        rows = _local_status_rows(root, mission_ids)
        return {
            "schema": "fluxio.live_mission_detail_status.v1",
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "maxAgeSeconds": 6 * 60 * 60,
            "source": "local_control_room_mission_detail",
            "host": "localhost",
            "remoteRoot": str(root),
            "missionCount": len(rows),
            "missionRows": rows,
            "sshExitCode": 0,
            "stderrPreview": "",
        }
    credentials = _load_nas_credentials(root=root, runbook_path=runbook_path)
    client = _connect_nas_client(_paramiko(), credentials)
    try:
        stdout, stderr, exit_code = _run_remote_bash_script(
            client,
            _remote_status_script(remote_root, remote_python, mission_ids),
            timeout=timeout,
        )
    finally:
        client.close()
    start = stdout.find("{")
    end = stdout.rfind("}")
    payload = json.loads(stdout[start : end + 1]) if start >= 0 and end >= start else {}
    rows = payload.get("missionRows", []) if isinstance(payload.get("missionRows"), list) else []
    return {
        "schema": "fluxio.live_mission_detail_status.v1",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "maxAgeSeconds": 6 * 60 * 60,
        "source": "bounded_ssh_control_room_mission_detail",
        "host": str(credentials.get("host") or ""),
        "remoteRoot": remote_root,
        "missionCount": len(rows),
        "missionRows": rows,
        "sshExitCode": exit_code,
        "stderrPreview": stderr.strip()[:1000],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync selected live NAS mission detail status rows.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--runbook", default="")
    parser.add_argument("--remote-root", default=DEFAULT_REMOTE_ROOT)
    parser.add_argument("--remote-python", default=DEFAULT_REMOTE_PYTHON)
    parser.add_argument("--mission-id", action="append", default=[])
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    runbook = Path(args.runbook).resolve() if args.runbook else None
    mission_ids = [str(item).strip() for item in args.mission_id if str(item).strip()]
    payload = sync_status(
        root,
        mission_ids=mission_ids,
        remote_root=args.remote_root,
        remote_python=args.remote_python,
        runbook_path=runbook,
        timeout=args.timeout,
    )
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
