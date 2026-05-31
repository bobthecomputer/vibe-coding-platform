from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from review_route_trust_sampling_closeouts import review_closeouts
from run_route_trust_sampling_missions import (
    _sampling_workspace_for_task,
    _task_workspace_slug,
    run_sampling,
)
from grant_agent.cli import cmd_mission_action
from grant_agent.mission_control import ControlRoomStore, MissionEvent, TERMINAL_MISSION_STATUSES


def _waiting_sampling_missions(closeout: dict) -> list[dict]:
    proposals = closeout.get("proposals", []) if isinstance(closeout.get("proposals"), list) else []
    return [
        item
        for item in proposals
        if isinstance(item, dict) and item.get("status") == "waiting_for_terminal_state"
    ]


def _ready_closeouts(closeout: dict) -> list[dict]:
    proposals = closeout.get("proposals", []) if isinstance(closeout.get("proposals"), list) else []
    return [
        item
        for item in proposals
        if isinstance(item, dict) and item.get("canApply")
    ]


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _mission_age_minutes(updated_at: str) -> int | None:
    parsed = _parse_iso(updated_at)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(max(0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() // 60))


def _run_stale_resume(root: Path, mission_id: str, *, budget_hours: int) -> tuple[int, dict, str]:
    stdout = io.StringIO()
    args = argparse.Namespace(
        root=str(root),
        mission_id=mission_id,
        action="extend-budget",
        launch_async=True,
        budget_hours=budget_hours,
        operator_value_score=None,
        operator_outcome="",
        operator_closeout_note="",
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
    return exit_code, parsed if isinstance(parsed, dict) else {}, raw


def _run_async_resume(root: Path, mission_id: str) -> tuple[int, dict, str]:
    stdout = io.StringIO()
    args = argparse.Namespace(
        root=str(root),
        mission_id=mission_id,
        action="resume",
        launch_async=True,
        budget_hours=4,
        operator_value_score=None,
        operator_outcome="",
        operator_closeout_note="",
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
    return exit_code, parsed if isinstance(parsed, dict) else {}, raw


def _load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _route_trust_task_maps(root: Path, store: ControlRoomStore) -> tuple[dict[str, str], dict[str, str]]:
    mission_tasks: dict[str, str] = {}
    objective_tasks: dict[str, str] = {}

    def remember(row: dict) -> None:
        task_type = str(row.get("taskType") or "").strip()
        if not task_type:
            return
        mission_id = str(row.get("missionId") or row.get("mission_id") or "").strip()
        objective = str(row.get("objective") or row.get("sampleMissionObjective") or "").strip()
        if mission_id:
            mission_tasks[mission_id] = task_type
        if objective:
            objective_tasks[objective.lower()] = task_type

    route_dir = root / ".agent_control" / "route_trust_sampling"
    for path in route_dir.glob("*.json"):
        payload = _load_json(path)
        for key in ("launchedSamplingMissions", "proposals", "appliedCloseouts"):
            rows = payload.get(key, []) if isinstance(payload.get(key), list) else []
            for row in rows:
                if isinstance(row, dict):
                    remember(row)
        closeout = payload.get("closeoutReview") if isinstance(payload.get("closeoutReview"), dict) else {}
        rows = closeout.get("proposals", []) if isinstance(closeout.get("proposals"), list) else []
        for row in rows:
            if isinstance(row, dict):
                remember(row)

    try:
        snapshot = store.build_snapshot()
    except Exception:
        snapshot = {}
    route_trust = (
        snapshot.get("harnessLab", {}).get("routeTrustCoverage", {})
        if isinstance(snapshot.get("harnessLab"), dict)
        else {}
    )
    plan = route_trust.get("nextSamplingPlan", []) if isinstance(route_trust.get("nextSamplingPlan"), list) else []
    for row in plan:
        if isinstance(row, dict):
            remember(row)
    return mission_tasks, objective_tasks


def _migrate_queued_sampling_missions(root: Path, *, enabled: bool) -> dict:
    if not enabled:
        return {
            "enabled": False,
            "attempted": False,
            "migratedMissionIds": [],
            "migrated": [],
            "skipped": [],
        }
    store = ControlRoomStore(root)
    store.rebalance_mission_queue()
    mission_tasks, objective_tasks = _route_trust_task_maps(root, store)
    migrated: list[dict] = []
    skipped: list[dict] = []
    for mission in store.load_missions():
        if mission.state.status in TERMINAL_MISSION_STATUSES or mission.state.status == "draft":
            continue
        if mission.state.queue_position <= 0 and mission.state.status != "queued":
            continue
        task_type = (
            mission_tasks.get(mission.mission_id)
            or objective_tasks.get(str(mission.objective or "").strip().lower())
        )
        if not task_type:
            skipped.append({"missionId": mission.mission_id, "reason": "not_route_trust_sampling"})
            continue
        target_workspace_id = f"route_trust_{_task_workspace_slug(task_type)}"
        if mission.workspace_id == target_workspace_id:
            skipped.append(
                {
                    "missionId": mission.mission_id,
                    "reason": "already_in_route_trust_workspace",
                    "taskType": task_type,
                }
            )
            continue
        old_workspace_id = mission.workspace_id
        target_workspace = _sampling_workspace_for_task(
            store,
            root=root,
            task_type=task_type,
            runtime=mission.runtime_id or "hermes",
        )
        mission.workspace_id = target_workspace.workspace_id
        mission.state.queue_position = 0
        mission.state.blocking_mission_id = None
        mission.state.queue_reason = ""
        mission.state.status = "queued"
        mission.state.planner_loop_status = "idle"
        mission.proof.summary = (
            "Queued route-trust sampling mission moved to a dedicated isolated task lane."
        )
        store.update_mission(mission)
        store.rebalance_mission_queue(old_workspace_id)
        store.rebalance_mission_queue(target_workspace.workspace_id)
        store.append_event(
            MissionEvent(
                mission_id=mission.mission_id,
                kind="mission.route_trust_isolated_lane_migrated",
                message=mission.proof.summary,
                metadata={
                    "taskType": task_type,
                    "oldWorkspaceId": old_workspace_id,
                    "newWorkspaceId": target_workspace.workspace_id,
                    "executionTargetPreference": target_workspace.execution_target_preference,
                },
            )
        )
        exit_code, payload, raw = _run_async_resume(root, mission.mission_id)
        dispatch = payload.get("dispatch") if isinstance(payload.get("dispatch"), dict) else {}
        migrated.append(
            {
                "missionId": mission.mission_id,
                "taskType": task_type,
                "oldWorkspaceId": old_workspace_id,
                "newWorkspaceId": target_workspace.workspace_id,
                "ok": exit_code == 0,
                "exitCode": exit_code,
                "dispatchPid": dispatch.get("pid"),
                "rawOutputPreview": raw[:600],
            }
        )
    return {
        "enabled": True,
        "attempted": bool(migrated),
        "migratedMissionIds": [item["missionId"] for item in migrated if item.get("ok")],
        "migrated": migrated,
        "skipped": skipped[:12],
    }


def _resume_stale_waiting_missions(
    root: Path,
    waiting: list[dict],
    *,
    enabled: bool,
    stale_minutes: int,
    budget_hours: int,
) -> dict:
    if not waiting:
        return {
            "enabled": bool(enabled),
            "attempted": False,
            "resumedMissionIds": [],
            "skipped": [],
        }
    store = ControlRoomStore(root)
    resumed: list[dict] = []
    skipped: list[dict] = []
    for item in waiting:
        mission_id = str(item.get("missionId") or "").strip()
        mission = store.get_mission(mission_id) if mission_id else None
        if mission is None:
            skipped.append({"missionId": mission_id, "reason": "mission_not_found"})
            continue
        status = str(mission.state.status or "")
        age = _mission_age_minutes(str(mission.updated_at or mission.created_at or ""))
        if status in TERMINAL_MISSION_STATUSES:
            skipped.append({"missionId": mission_id, "reason": "terminal", "status": status})
            continue
        if age is not None and age < stale_minutes:
            skipped.append(
                {
                    "missionId": mission_id,
                    "reason": "not_stale",
                    "ageMinutes": age,
                    "staleMinutes": stale_minutes,
                }
            )
            continue
        if not enabled:
            skipped.append(
                {
                    "missionId": mission_id,
                    "reason": "stale_resume_disabled",
                    "ageMinutes": age,
                    "staleMinutes": stale_minutes,
                }
            )
            continue
        exit_code, payload, raw = _run_stale_resume(
            root,
            mission_id,
            budget_hours=budget_hours,
        )
        resumed.append(
            {
                "missionId": mission_id,
                "ok": exit_code == 0,
                "exitCode": exit_code,
                "ageMinutes": age,
                "staleMinutes": stale_minutes,
                "rawOutputPreview": raw[:600],
                "dispatchPid": (
                    payload.get("dispatch", {}).get("pid")
                    if isinstance(payload.get("dispatch"), dict)
                    else None
                ),
            }
        )
    return {
        "enabled": bool(enabled),
        "attempted": bool(resumed),
        "resumedMissionIds": [item["missionId"] for item in resumed if item.get("ok")],
        "resumed": resumed,
        "skipped": skipped,
    }


def advance_loop(args: argparse.Namespace) -> dict:
    root = Path(args.root).resolve()
    closeout_args = argparse.Namespace(
        root=str(root),
        sampling_report="",
        write=True,
        auto_apply=bool(args.auto_apply_closeouts),
        min_auto_score=int(args.min_auto_score),
    )
    closeout = review_closeouts(closeout_args)
    waiting = _waiting_sampling_missions(closeout)
    ready = _ready_closeouts(closeout)
    stale_repair = _resume_stale_waiting_missions(
        root,
        waiting,
        enabled=bool(getattr(args, "resume_stale_waiting", False)),
        stale_minutes=int(getattr(args, "stale_waiting_minutes", 90)),
        budget_hours=int(args.budget_hours),
    )
    queued_migration = _migrate_queued_sampling_missions(
        root,
        enabled=bool(getattr(args, "migrate_queued_sampling", True)),
    )
    launched = {}
    should_attempt_sampling = (
        not args.review_only
        and not (ready and not args.auto_apply_closeouts)
        and not stale_repair.get("resumedMissionIds")
        and not queued_migration.get("migratedMissionIds")
    )
    if should_attempt_sampling:
        sampling_args = argparse.Namespace(
            root=str(root),
            max_new=int(args.max_new),
            max_active=int(args.max_active),
            max_queued=int(args.max_queued),
            runtime=str(args.runtime),
            mode=str(args.mode),
            budget_hours=int(args.budget_hours),
            skip_route_contract=False,
            shared_workspace=False,
            dry_run=bool(args.dry_run),
            write=True,
        )
        launched = run_sampling(sampling_args)
    payload = {
        "schema": "fluxio.route_trust_sampling_loop.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "ok": bool(closeout.get("ok")) and (not launched or bool(launched.get("ok"))),
        "reviewOnly": bool(args.review_only),
        "dryRun": bool(args.dry_run),
        "closeoutReview": {
            "status": "passed" if closeout.get("ok") else "failed",
            "proposalCount": len(closeout.get("proposals", [])) if isinstance(closeout.get("proposals"), list) else 0,
            "waitingMissionIds": [item.get("missionId", "") for item in waiting],
            "readyMissionIds": [item.get("missionId", "") for item in ready],
            "appliedCount": len(closeout.get("appliedCloseouts", [])) if isinstance(closeout.get("appliedCloseouts"), list) else 0,
            "nextAction": closeout.get("nextAction", ""),
        },
        "samplingLaunch": {
            "attempted": bool(launched),
            "status": "passed" if launched.get("ok") else "failed" if launched else "not_attempted",
            "launchedMissionIds": [
                item.get("missionId", "")
                for item in launched.get("launchedSamplingMissions", [])
                if isinstance(item, dict)
            ] if isinstance(launched.get("launchedSamplingMissions"), list) else [],
            "skipped": launched.get("skippedSamplingMissions", []) if isinstance(launched.get("skippedSamplingMissions"), list) else [],
            "nextAction": launched.get("nextAction", ""),
        },
        "staleWaitingRepair": stale_repair,
        "queuedSamplingMigration": queued_migration,
        "nextAction": (
            "Resumed stale sampling mission(s); wait for terminal state before closeout."
            if stale_repair.get("resumedMissionIds")
            else "Migrated queued sampling mission(s) into isolated route-trust lanes and dispatched resume."
            if queued_migration.get("migratedMissionIds")
            else "Review ready closeout proposals or rerun with --auto-apply-closeouts."
            if ready and not args.auto_apply_closeouts
            else "Route-trust loop advanced and launched a new sampling mission."
            if launched and launched.get("launchedSamplingMissions")
            else "Waiting sampling mission(s) remain; sampler skipped those task categories and found no other launchable sample."
            if waiting and launched and launched.get("skippedSamplingMissions")
            else "Wait for active sampling missions to reach a terminal state before scoring or launching another."
            if waiting
            else "No sampling launch needed in this pass."
        ),
    }
    if args.write:
        out_path = root / ".agent_control" / "route_trust_sampling" / "loop_latest.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["evidencePath"] = str(out_path)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Advance the route-trust sampling loop safely.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--max-new", type=int, default=1)
    parser.add_argument("--max-active", type=int, default=4)
    parser.add_argument("--max-queued", type=int, default=2)
    parser.add_argument("--runtime", choices=["hermes", "openclaw", "auto"], default="hermes")
    parser.add_argument("--mode", default="Autopilot")
    parser.add_argument("--budget-hours", type=int, default=4)
    parser.add_argument("--auto-apply-closeouts", action="store_true")
    parser.add_argument("--min-auto-score", type=int, default=70)
    parser.add_argument("--resume-stale-waiting", action="store_true")
    parser.add_argument("--stale-waiting-minutes", type=int, default=90)
    parser.add_argument("--no-migrate-queued-sampling", dest="migrate_queued_sampling", action="store_false")
    parser.set_defaults(migrate_queued_sampling=True)
    parser.add_argument("--review-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    payload = advance_loop(args)
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
