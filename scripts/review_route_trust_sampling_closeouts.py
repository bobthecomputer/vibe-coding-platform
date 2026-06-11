from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from grant_agent.cli import cmd_mission_action
from grant_agent.mission_control import ControlRoomStore, TERMINAL_MISSION_STATUSES


def _load_json(path: Path, fallback):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback
    return payload if isinstance(payload, type(fallback)) else fallback


def _mission_id(item: dict) -> str:
    return str(item.get("missionId") or item.get("mission_id") or item.get("id") or "").strip()


def _sampling_items_from_payload(payload: dict) -> list[dict]:
    rows: list[dict] = []
    if not isinstance(payload, dict):
        return rows
    for key in ("launchedSamplingMissions", "proposals", "appliedCloseouts"):
        values = payload.get(key, []) if isinstance(payload.get(key), list) else []
        rows.extend(item for item in values if isinstance(item, dict))
    migration = payload.get("queuedSamplingMigration")
    if isinstance(migration, dict):
        values = migration.get("migrated", []) if isinstance(migration.get("migrated"), list) else []
        rows.extend(item for item in values if isinstance(item, dict))
    closeout = payload.get("closeoutReview")
    if isinstance(closeout, dict):
        values = closeout.get("proposals", []) if isinstance(closeout.get("proposals"), list) else []
        rows.extend(item for item in values if isinstance(item, dict))
    return rows


def _collect_sampling_items(root: Path, sampling_path: Path, *, explicit_report: bool) -> list[dict]:
    if explicit_report:
        payload = _load_json(sampling_path, {})
        return _sampling_items_from_payload(payload)
    candidates = sorted(
        (root / ".agent_control" / "route_trust_sampling").glob("*.json"),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
    )
    by_mission: dict[str, dict] = {}
    for path in candidates:
        payload = _load_json(path, {})
        for item in _sampling_items_from_payload(payload):
            mission_id = _mission_id(item)
            task_type = str(item.get("taskType") or "").strip()
            if not mission_id or not task_type:
                continue
            by_mission[mission_id] = {
                "missionId": mission_id,
                "taskType": task_type,
                "objective": item.get("objective") or item.get("sampleMissionObjective") or "",
                "sourcePath": str(path),
            }
    return list(by_mission.values())


def _feedback_signal(mission) -> dict:
    state = getattr(mission, "state", None)
    feedback = getattr(state, "operator_value_feedback", {}) if state is not None else {}
    return feedback if isinstance(feedback, dict) else {}


def _proposal_for_mission(mission, sampling_item: dict) -> dict:
    status = str(mission.state.status or "")
    stop_reason = str(getattr(mission.state, "stop_reason", "") or "")
    failed = list(mission.proof.failed_checks or []) + list(mission.state.verification_failures or [])
    passed = list(mission.proof.passed_checks or [])
    existing = _feedback_signal(mission)
    if existing:
        score = int(existing.get("score") or 0)
        return {
            "missionId": mission.mission_id,
            "taskType": sampling_item.get("taskType", ""),
            "status": "already_scored",
            "missionStatus": status,
            "score": score,
            "outcome": str(existing.get("outcome") or "recorded"),
            "trustSignal": str(existing.get("trustSignal") or existing.get("trust_signal") or "recorded"),
            "reason": "Mission already has operator value feedback.",
            "canApply": False,
        }
    if status == "completed" and not failed:
        score = 92 if passed else 84
        return {
            "missionId": mission.mission_id,
            "taskType": sampling_item.get("taskType", ""),
            "status": "ready_for_value_closeout",
            "missionStatus": status,
            "score": score,
            "outcome": "useful",
            "trustSignal": "promote",
            "reason": (
                f"Mission completed with {len(passed)} passed check(s), no failed checks, "
                "and was launched from the route-trust sampling plan."
            ),
            "canApply": True,
        }
    if status in {"blocked", "failed", "verification_failed"} or stop_reason or failed:
        return {
            "missionId": mission.mission_id,
            "taskType": sampling_item.get("taskType", ""),
            "status": "ready_for_low_value_closeout",
            "missionStatus": status,
            "score": 30,
            "outcome": "not_useful",
            "trustSignal": "deprioritize",
            "reason": "Sampling mission ended with a blocker, failed verification, or failure state.",
            "canApply": True,
        }
    if status not in TERMINAL_MISSION_STATUSES and status not in {"failed", "verification_failed"}:
        return {
            "missionId": mission.mission_id,
            "taskType": sampling_item.get("taskType", ""),
            "status": "waiting_for_terminal_state",
            "missionStatus": status,
            "score": 0,
            "outcome": "pending",
            "trustSignal": "review",
            "reason": "Sampling mission is still running; value closeout waits for finished proof.",
            "canApply": False,
        }
    return {
        "missionId": mission.mission_id,
        "taskType": sampling_item.get("taskType", ""),
        "status": "manual_review_required",
        "missionStatus": status,
        "score": 55,
        "outcome": "mixed",
        "trustSignal": "review",
        "reason": f"Sampling mission ended as {status}; review proof before promoting route trust.",
        "canApply": False,
    }


def _apply_closeout(root: Path, proposal: dict) -> tuple[int, dict, str]:
    stdout = io.StringIO()
    args = argparse.Namespace(
        root=str(root),
        mission_id=proposal["missionId"],
        action="complete",
        launch_async=False,
        budget_hours=4,
        operator_value_score=int(proposal["score"]),
        operator_outcome=str(proposal["outcome"]),
        operator_closeout_note=(
            "Automated route-trust sampling closeout. "
            + str(proposal.get("reason") or "")
        ),
    )
    with contextlib.redirect_stdout(stdout):
        exit_code = cmd_mission_action(args)
    raw = stdout.getvalue()
    parsed = {}
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end >= start:
        try:
            parsed = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            parsed = {}
    parsed = parsed if isinstance(parsed, dict) else {}
    if exit_code == 0:
        task_type = str(proposal.get("taskType") or "").strip()
        mission_id = str(proposal.get("missionId") or "").strip()
        if task_type and mission_id:
            _annotate_feedback_task_type(root, mission_id, task_type)
            mission_payload = parsed.get("mission") if isinstance(parsed.get("mission"), dict) else {}
            state_payload = mission_payload.get("state") if isinstance(mission_payload.get("state"), dict) else {}
            feedback_payload = (
                state_payload.get("operator_value_feedback")
                if isinstance(state_payload.get("operator_value_feedback"), dict)
                else {}
            )
            feedback_payload["routeTrustTaskType"] = task_type
    return exit_code, parsed, raw


def _should_auto_apply_closeout(proposal: dict, *, min_auto_score: int) -> bool:
    if not proposal.get("canApply"):
        return False
    if str(proposal.get("status") or "") == "ready_for_low_value_closeout":
        return True
    try:
        score = int(proposal.get("score") or 0)
    except (TypeError, ValueError):
        score = 0
    return score >= int(min_auto_score)


def _annotate_feedback_task_type(root: Path, mission_id: str, task_type: str) -> None:
    store = ControlRoomStore(root)
    mission = store.get_mission(mission_id)
    if mission is None:
        return
    feedback = mission.state.operator_value_feedback
    if not isinstance(feedback, dict) or not feedback:
        return
    feedback["routeTrustTaskType"] = task_type
    mission.state.operator_value_feedback = feedback
    store.update_mission(mission)


def review_closeouts(args: argparse.Namespace) -> dict:
    root = Path(args.root).resolve()
    sampling_path = Path(args.sampling_report) if args.sampling_report else root / ".agent_control" / "route_trust_sampling" / "latest.json"
    explicit_report = bool(str(args.sampling_report or "").strip())
    launched = _collect_sampling_items(root, sampling_path, explicit_report=explicit_report)
    store = ControlRoomStore(root)
    proposals: list[dict] = []
    applied: list[dict] = []
    missing: list[dict] = []
    for item in launched:
        if not isinstance(item, dict):
            continue
        mission_id = _mission_id(item)
        if not mission_id:
            continue
        mission = store.get_mission(mission_id)
        if mission is None:
            missing.append({"missionId": mission_id, "taskType": item.get("taskType", ""), "reason": "mission_not_found"})
            continue
        proposal = _proposal_for_mission(mission, item)
        if str(proposal.get("status") or "") == "already_scored":
            task_type = str(proposal.get("taskType") or item.get("taskType") or "").strip()
            if task_type:
                _annotate_feedback_task_type(root, mission_id, task_type)
                proposal["annotatedRouteTrustTaskType"] = task_type
        proposals.append(proposal)
        if (
            args.auto_apply
            and _should_auto_apply_closeout(
                proposal,
                min_auto_score=int(args.min_auto_score),
            )
        ):
            exit_code, payload, raw = _apply_closeout(root, proposal)
            applied.append(
                {
                    "missionId": mission_id,
                    "ok": exit_code == 0,
                    "exitCode": exit_code,
                    "score": proposal.get("score"),
                    "outcome": proposal.get("outcome"),
                    "rawOutputPreview": raw[:600],
                    "operatorValueFeedback": (
                        payload.get("mission", {}).get("state", {}).get("operator_value_feedback", {})
                        if isinstance(payload.get("mission"), dict)
                        else {}
                    ),
                }
            )
    payload = {
        "schema": "fluxio.route_trust_sampling_closeout_review.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "samplingReportPath": str(sampling_path),
        "ok": not any(item.get("ok") is False for item in applied),
        "autoApply": bool(args.auto_apply),
        "minAutoScore": int(args.min_auto_score),
        "proposals": proposals,
        "appliedCloseouts": applied,
        "missingMissions": missing,
        "nextAction": (
            "Applied ready sampling closeouts; refresh route-trust coverage."
            if applied
            else "All discovered route-trust sampling missions are already value-scored; refresh route-trust coverage."
            if proposals and all(item.get("status") == "already_scored" for item in proposals)
            else "Run this review on the same control root that launched the sampling missions."
            if missing and not proposals
            else "Wait for sampling missions to complete, then rerun with --auto-apply."
            if any(item.get("status") == "waiting_for_terminal_state" for item in proposals)
            else "Review proposals and rerun with --auto-apply if the generated value signal is acceptable."
            if proposals
            else "Launch a route-trust sampling mission first."
        ),
    }
    if args.write:
        out_path = root / ".agent_control" / "route_trust_sampling" / "closeout_review_latest.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["evidencePath"] = str(out_path)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review route-trust sampling missions and prepare value closeouts.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--sampling-report", default="")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--auto-apply", action="store_true")
    parser.add_argument("--min-auto-score", type=int, default=70)
    args = parser.parse_args(argv)
    payload = review_closeouts(args)
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
