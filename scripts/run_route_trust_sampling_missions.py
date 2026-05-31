from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from grant_agent.cli import _select_quickstart_workspace, cmd_mission_start
from grant_agent.mission_control import ControlRoomStore, TERMINAL_MISSION_STATUSES


def _parse_json_output(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _mission_id(payload: dict) -> str:
    mission = payload.get("mission") if isinstance(payload.get("mission"), dict) else {}
    return str(mission.get("mission_id") or mission.get("missionId") or mission.get("id") or "")


def _active_mission_objectives(store: ControlRoomStore) -> set[str]:
    active: set[str] = set()
    for mission in store.load_missions():
        if mission.state.status in TERMINAL_MISSION_STATUSES or mission.state.status == "draft":
            continue
        active.add(str(mission.objective or "").strip().lower())
    return active


def _waiting_closeout_task_types(closeout: dict) -> set[str]:
    proposals = closeout.get("proposals", []) if isinstance(closeout.get("proposals"), list) else []
    waiting: set[str] = set()
    for item in proposals:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "") != "waiting_for_terminal_state":
            continue
        task_type = str(item.get("taskType") or "").strip()
        if task_type:
            waiting.add(task_type)
    return waiting


def _task_workspace_slug(task_type: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(task_type or "").strip().lower()).strip("_")
    return slug[:48] or "general"


def _sampling_workspace_for_task(
    store: ControlRoomStore,
    *,
    root: Path,
    task_type: str,
    runtime: str,
):
    base_workspace = _select_quickstart_workspace(store, root=root)
    slug = _task_workspace_slug(task_type)
    selected_runtime = str(runtime or "auto").strip().lower()
    if selected_runtime == "auto":
        selected_runtime = base_workspace.default_runtime
    return store.upsert_workspace(
        workspace_id=f"route_trust_{slug}",
        name=f"Route trust / {slug.replace('_', ' ')}",
        root_path=base_workspace.root_path,
        default_runtime=selected_runtime,
        user_profile=base_workspace.user_profile,
        preferred_harness=base_workspace.preferred_harness,
        routing_strategy=base_workspace.routing_strategy,
        route_overrides=base_workspace.route_overrides,
        auto_optimize_routing=base_workspace.auto_optimize_routing,
        openai_codex_auth_mode=base_workspace.openai_codex_auth_mode,
        minimax_auth_mode=base_workspace.minimax_auth_mode,
        commit_message_style=base_workspace.commit_message_style,
        execution_target_preference="isolated_worktree",
        local_project_path=base_workspace.local_project_path,
        nas_project_path=base_workspace.nas_project_path,
        sync_mode=base_workspace.sync_mode,
        sync_direction=base_workspace.sync_direction,
        sync_conflict_policy=base_workspace.sync_conflict_policy,
        auto_sync_to_nas=base_workspace.auto_sync_to_nas,
    )


def _run_quickstart(
    *,
    root: Path,
    objective: str,
    success_checks: list[str],
    runtime: str,
    mode: str,
    budget_hours: int,
    verification_commands: list[str] | None = None,
    route_contract: list[dict[str, str]] | None = None,
    task_type: str = "",
    dedicated_workspace: bool = False,
) -> tuple[int, dict, str]:
    stdout = io.StringIO()
    store = ControlRoomStore(root)
    try:
        workspace = (
            _sampling_workspace_for_task(
                store,
                root=root,
                task_type=task_type,
                runtime=runtime,
            )
            if dedicated_workspace and task_type
            else _select_quickstart_workspace(store, root=root)
        )
    except ValueError as exc:
        return 1, {"error": str(exc)}, json.dumps({"error": str(exc)}, indent=2)
    if not success_checks:
        success_checks = [
            "Mission produces reviewable proof with no failed checks or pending approvals."
        ]
    selected_runtime = str(runtime or "auto").strip().lower()
    if selected_runtime == "auto":
        selected_runtime = workspace.default_runtime
    args = argparse.Namespace(
        root=str(root),
        workspace_id=workspace.workspace_id,
        runtime=selected_runtime,
        objective=objective,
        success_check=success_checks,
        verification_command=verification_commands or [],
        mode=mode,
        budget_hours=budget_hours,
        relative_stop_minutes=0,
        run_until="continue_until_blocked",
        profile=workspace.user_profile,
        route_overrides_json=json.dumps(route_contract or workspace.route_overrides or []),
        escalation_destination="",
        code_execution=False,
        code_execution_memory="4g",
        code_execution_container_id="",
        code_execution_required=False,
        launch_async=True,
    )
    with contextlib.redirect_stdout(stdout):
        exit_code = cmd_mission_start(args)
    raw = stdout.getvalue()
    return exit_code, _parse_json_output(raw), raw


def _focused_verification_commands(task_type: str) -> list[str]:
    commands = [
        "python -m compileall -q src",
        (
            "python -m pytest "
            "tests/test_action_executor.py::ActionExecutorTests::test_generated_write_without_explicit_path_uses_mission_artifact "
            "tests/test_runtimes.py::RuntimeAdapterTests::test_hermes_launch_normalizes_minimax_model_for_cli "
            "tests/test_cli_preferences.py::CliPreferenceTests::test_route_trust_sampler_applies_route_contract_before_async_launch "
            "-q"
        ),
    ]
    if task_type == "frontend_design":
        commands.append("npm run frontend:build")
    return commands


def _load_latest_closeout(root: Path) -> dict:
    path = root / ".agent_control" / "route_trust_sampling" / "closeout_review_latest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_live_audit_route_repair_plan(root: Path) -> list[dict]:
    path = root / ".agent_control" / "live_nas_system_audit_latest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    audit = payload.get("audit") if isinstance(payload, dict) else {}
    maturity = audit.get("routeTrustMaturity") if isinstance(audit, dict) else {}
    if not isinstance(maturity, dict) or str(maturity.get("status") or "") != "needs_route_repair":
        return []
    repair_plan = maturity.get("repairPlan", [])
    return [item for item in repair_plan if isinstance(item, dict) and item.get("taskType")]


def _repair_plan_sample_item(item: dict) -> dict:
    task_type = str(item.get("taskType") or "").strip()
    label = str(item.get("label") or task_type.replace("_", " ")).strip() or "route trust"
    failed_mission = str(item.get("missionId") or "").strip()
    repair_action = str(item.get("repairAction") or "").strip()
    model_policy = str(item.get("modelPolicy") or "").strip()
    trust_effect = str(item.get("trustEffect") or "").strip()
    if task_type == "data_f1_analytics":
        base_objective = (
            "Repair route trust for F1/data analytics by building an F1 telemetry analytics "
            "prototype with lap delta, sector comparison, tire stint, driver consistency, "
            "sample data, and a reviewable dashboard/report artifact."
        )
    else:
        base_objective = f"Repair route trust for {label} with a high-value reviewable mission artifact."
    context = [
        f"Previous low-value mission: {failed_mission}." if failed_mission else "",
        repair_action,
        model_policy,
        trust_effect,
    ]
    objective = " ".join([base_objective, *[value for value in context if value]]).strip()
    checks = [
        "Generate a served or file-backed artifact that can be opened from Builder.",
        "Capture browser/preview verification evidence and attach it to the proof digest.",
        "Document the dataset, assumptions, and why the previous low-value route failed.",
        "Do not promote route trust unless operator value is at least 80 with no failed verification.",
    ]
    if repair_action:
        checks.append(repair_action)
    if model_policy:
        checks.append(f"Apply repaired model policy: {model_policy}")
    return {
        "taskType": task_type,
        "sampleMissionObjective": objective,
        "sampleMissionSuccessChecks": checks,
        "sampleMissionMode": "Autopilot",
        "sampleMissionBudgetHours": 4,
        "source": "live_nas_system_audit_repair_plan",
        "repairPlan": item,
    }


def _merge_live_repair_closeout(closeout: dict, root: Path) -> dict:
    repair_rows = _load_live_audit_route_repair_plan(root)
    if not repair_rows:
        return closeout
    merged = dict(closeout or {})
    proposals = list(merged.get("proposals", []) if isinstance(merged.get("proposals"), list) else [])
    known = {
        (
            str(item.get("taskType") or ""),
            str(item.get("missionId") or item.get("mission_id") or ""),
        )
        for item in proposals
        if isinstance(item, dict)
    }
    for repair in repair_rows:
        key = (str(repair.get("taskType") or ""), str(repair.get("missionId") or ""))
        if key in known:
            continue
        proposals.append(
            {
                "missionId": repair.get("missionId", ""),
                "taskType": repair.get("taskType", ""),
                "score": repair.get("score", 30),
                "outcome": "not_useful",
                "trustSignal": "deprioritize",
                "source": "live_nas_system_audit_repair_plan",
                "repairAction": repair.get("repairAction", ""),
            }
        )
    merged["proposals"] = proposals
    return merged


def _latest_low_value_task(closeout: dict, task_type: str) -> dict:
    proposals = closeout.get("proposals", []) if isinstance(closeout.get("proposals"), list) else []
    applied = closeout.get("appliedCloseouts", []) if isinstance(closeout.get("appliedCloseouts"), list) else []
    for item in reversed([*proposals, *applied]):
        if not isinstance(item, dict):
            continue
        if str(item.get("taskType") or "") != task_type:
            continue
        try:
            score = int(item.get("score") or 0)
        except (TypeError, ValueError):
            score = 0
        signal = str(item.get("trustSignal") or item.get("trust_signal") or "").lower()
        outcome = str(item.get("outcome") or "").lower()
        if score < 50 or signal == "deprioritize" or outcome == "not_useful":
            return item
    return {}


def _task_value_rows(closeout: dict, task_type: str) -> list[dict]:
    rows: list[dict] = []
    for collection in (
        closeout.get("proposals", []),
        closeout.get("appliedCloseouts", []),
    ):
        if not isinstance(collection, list):
            continue
        for item in collection:
            if not isinstance(item, dict):
                continue
            if str(item.get("taskType") or "") != task_type:
                continue
            try:
                score = int(item.get("score") or item.get("operatorValueScore") or 0)
            except (TypeError, ValueError):
                score = 0
            rows.append(
                {
                    **item,
                    "score": score,
                    "outcome": str(item.get("outcome") or item.get("operatorOutcome") or ""),
                    "trustSignal": str(item.get("trustSignal") or item.get("trust_signal") or ""),
                }
            )
    return rows


def _security_red_team_difficulty_profile(closeout: dict) -> dict:
    rows = _task_value_rows(closeout, "security_red_team")
    clean_promotions = [
        item
        for item in rows
        if int(item.get("score") or 0) >= 80
        and str(item.get("outcome") or "").lower() != "not_useful"
        and str(item.get("trustSignal") or "").lower() != "deprioritize"
    ]
    best_score = max([int(item.get("score") or 0) for item in rows] or [0])
    next_level = min(5, 1 + len(clean_promotions))
    return {
        "schema": "fluxio.route_trust_red_team_difficulty.v1",
        "taskType": "security_red_team",
        "cleanPromotionCount": len(clean_promotions),
        "bestScore": best_score,
        "difficultyLevel": next_level,
        "shouldEscalate": len(clean_promotions) > 0,
        "attemptBudget": 7 + (next_level * 3),
        "safetyPolicy": {
            "defensiveOnly": True,
            "noThirdPartyTargets": True,
            "noCredentialAttackPayloads": True,
            "rawPayloadExport": False,
        },
        "nextBenchmarkFocus": [
            "multi-step defensive threat model",
            "harder false-positive/false-negative analysis",
            "control bypass reasoning without exploit payloads",
            "operator-facing remediation playbook",
        ],
    }


def _apply_task_difficulty(
    *,
    task_type: str,
    objective: str,
    success_checks: list[str],
    closeout: dict,
) -> tuple[str, list[str], dict]:
    if task_type != "security_red_team":
        return objective, success_checks, {}
    profile = _security_red_team_difficulty_profile(closeout)
    if not profile.get("shouldEscalate"):
        return objective, success_checks, profile
    level = int(profile.get("difficultyLevel") or 1)
    budget = int(profile.get("attemptBudget") or 10)
    escalated_objective = (
        f"{objective} Difficulty escalation level {level}: build a harder defensive-only "
        f"red-team benchmark with at least {budget} benign attack-simulation attempts, "
        "multi-step threat-chain reasoning, false-positive/false-negative analysis, "
        "and concrete defensive remediation. Keep all work scoped to local/synthetic "
        "systems; do not target third-party services or emit credential-attack payloads."
    )
    escalated_checks = [
        *success_checks,
        f"Document difficulty level {level}, attempt budget {budget}, and why this sample is harder than previous promoted red-team samples.",
        "Include a defensive remediation playbook and prove unsafe payloads or third-party targeting were excluded.",
        "Close with operator-value evidence so the next red-team benchmark can escalate again if it passes cleanly.",
    ]
    return escalated_objective, escalated_checks, profile


def _route_contract_for_task(
    task_type: str,
    *,
    root: Path | None = None,
    closeout: dict | None = None,
) -> list[dict[str, str]]:
    closeout = closeout if closeout is not None else _load_latest_closeout(root) if root else {}
    if root is not None:
        closeout = _merge_live_repair_closeout(closeout or {}, root)
    low_value = _latest_low_value_task(closeout or {}, task_type)
    executor = {
        "provider": "openai-codex",
        "model": "gpt-5.5",
        "effort": "high",
        "budget_class": "premium",
    }
    if task_type == "frontend_design":
        executor = {
            "provider": "minimax",
            "model": "minimax-m2.7",
            "effort": "high",
            "budget_class": "premium",
        }
        if low_value:
            executor["repair_reason"] = (
                "Repair route-trust fallback after low-value frontend sample "
                f"{low_value.get('missionId') or low_value.get('mission_id') or ''}: "
                "use the Hermes-verified MiniMax route with normalized model id."
            )
    elif low_value:
        executor["repair_reason"] = (
            f"Repair route-trust fallback after low-value {task_type} sample "
            f"{low_value.get('missionId') or low_value.get('mission_id') or ''}: "
            "use Codex gpt-5.5 high and require dataset/artifact, browser-preview proof, "
            "proof digest, and operator-value closeout before trust can rise."
        )
    executor_reason = (
        str(executor.pop("repair_reason"))
        if executor.get("repair_reason")
        else f"Route-trust sampler: task-aware executor for {task_type}."
    )
    return [
        {
            "role": "planner",
            "provider": "openai-codex",
            "model": "gpt-5.5",
            "effort": "high",
            "budget_class": "balanced",
            "reason": f"Route-trust sampler: high-effort planner via Codex for {task_type}.",
        },
        {
            "role": "executor",
            "reason": executor_reason,
            **executor,
        },
        {
            "role": "verifier",
            "provider": "openai-codex",
            "model": "gpt-5.5",
            "effort": "high",
            "budget_class": "balanced",
            "reason": f"Route-trust sampler: high-effort verifier via Codex for {task_type}.",
        },
    ]


def _prelaunch_route_receipts(route_contract: list[dict[str, str]]) -> list[dict]:
    return [
        {
            "role": route["role"],
            "provider": route["provider"],
            "model": route["model"],
            "ok": True,
            "appliedBeforeLaunch": True,
            "reason": route.get("reason", ""),
        }
        for route in route_contract
    ]


def run_sampling(args: argparse.Namespace) -> dict:
    root = Path(args.root).resolve()
    store = ControlRoomStore(root)
    store.rebalance_mission_queue()
    before_summary = store.build_summary_snapshot()
    before_counts = before_summary.get("counts", {}) if isinstance(before_summary.get("counts"), dict) else {}
    snapshot = store.build_snapshot()
    closeout = _merge_live_repair_closeout(_load_latest_closeout(root), root)
    waiting_closeout_tasks = _waiting_closeout_task_types(closeout)
    route_trust = (
        snapshot.get("harnessLab", {}).get("routeTrustCoverage", {})
        if isinstance(snapshot.get("harnessLab"), dict)
        else {}
    )
    plan = route_trust.get("nextSamplingPlan", []) if isinstance(route_trust.get("nextSamplingPlan"), list) else []
    repair_plan = [_repair_plan_sample_item(item) for item in _load_live_audit_route_repair_plan(root)]
    if repair_plan:
        seen_repair_tasks = {str(item.get("taskType") or "") for item in repair_plan}
        plan = [
            *repair_plan,
            *[
                item
                for item in plan
                if not isinstance(item, dict) or str(item.get("taskType") or "") not in seen_repair_tasks
            ],
        ]
    active_count = int(before_counts.get("activeMissions") or 0)
    queued_count = int(before_counts.get("queuedMissions") or 0)
    active_objectives = _active_mission_objectives(store)
    launched: list[dict] = []
    skipped: list[dict] = []

    capacity_available = active_count < int(args.max_active) and queued_count <= int(args.max_queued)
    for item in plan:
        if len(launched) >= int(args.max_new):
            break
        if not isinstance(item, dict):
            continue
        task_type = str(item.get("taskType") or "").strip()
        if task_type in waiting_closeout_tasks:
            skipped.append(
                {
                    "taskType": task_type,
                    "reason": "waiting_for_sampling_closeout",
                    "nextAction": "Run the closeout review before launching another sample for this task category.",
                }
            )
            continue
        objective = str(item.get("sampleMissionObjective") or "").strip()
        success_checks = [
            str(check).strip()
            for check in item.get("sampleMissionSuccessChecks", [])
            if str(check).strip()
        ]
        if not objective:
            skipped.append({"taskType": task_type, "reason": "missing_objective"})
            continue
        if objective.lower() in active_objectives:
            skipped.append({"taskType": task_type, "reason": "already_active", "objective": objective})
            continue
        if not capacity_available:
            skipped.append(
                {
                    "taskType": task_type,
                    "reason": "capacity_guard",
                    "activeMissions": active_count,
                    "queuedMissions": queued_count,
                    "maxActive": int(args.max_active),
                    "maxQueued": int(args.max_queued),
                }
            )
            break
        objective_for_launch, success_checks_for_launch, difficulty_profile = _apply_task_difficulty(
            task_type=task_type,
            objective=objective,
            success_checks=success_checks,
            closeout=closeout,
        )
        if args.dry_run:
            launched.append(
                {
                    "taskType": task_type,
                    "dryRun": True,
                    "objective": objective_for_launch,
                    "runtime": args.runtime,
                    "successChecks": success_checks_for_launch,
                    "difficultyProfile": difficulty_profile,
                    "source": item.get("source", "route_trust_next_sampling_plan"),
                }
            )
            active_objectives.add(objective.lower())
            continue
        route_contract = (
            _route_contract_for_task(task_type, root=root, closeout=closeout)
            if not args.skip_route_contract
            else []
        )
        exit_code, payload, raw = _run_quickstart(
            root=root,
            objective=objective_for_launch,
            success_checks=success_checks_for_launch,
            verification_commands=_focused_verification_commands(task_type),
            runtime=args.runtime,
            mode=str(item.get("sampleMissionMode") or args.mode),
            budget_hours=int(item.get("sampleMissionBudgetHours") or args.budget_hours),
            route_contract=route_contract,
            task_type=task_type,
            dedicated_workspace=not bool(getattr(args, "shared_workspace", False)),
        )
        mission_id = _mission_id(payload)
        route_receipts = _prelaunch_route_receipts(route_contract) if mission_id else []
        launched.append(
            {
                "taskType": task_type,
                "dryRun": False,
                "ok": exit_code == 0 and bool(mission_id) and all(item.get("ok") for item in route_receipts),
                "missionId": mission_id,
                "objective": objective_for_launch,
                "runtime": args.runtime,
                "successChecks": success_checks_for_launch,
                "difficultyProfile": difficulty_profile,
                "workspaceId": (
                    f"route_trust_{_task_workspace_slug(task_type)}"
                    if not bool(getattr(args, "shared_workspace", False))
                    else ""
                ),
                "routeReceipts": route_receipts,
                "source": item.get("source", "route_trust_next_sampling_plan"),
                "exitCode": exit_code,
                "rawOutputPreview": raw[:600],
            }
        )
        active_objectives.add(objective.lower())

    after_summary = ControlRoomStore(root).build_summary_snapshot()
    after_counts = after_summary.get("counts", {}) if isinstance(after_summary.get("counts"), dict) else {}
    payload = {
        "schema": "fluxio.route_trust_live_sampling_run.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "ok": all(item.get("ok", True) for item in launched),
        "dryRun": bool(args.dry_run),
        "runtime": args.runtime,
        "capacity": {
            "maxActive": int(args.max_active),
            "maxQueued": int(args.max_queued),
            "before": before_counts,
            "after": after_counts,
        },
        "coverageBefore": {
            "provenTaskCount": route_trust.get("provenTaskCount", 0),
            "samplingTaskCount": route_trust.get("samplingTaskCount", 0),
            "nextAction": route_trust.get("nextAction", ""),
            "repairPlanCount": len(repair_plan),
        },
        "launchedSamplingMissions": launched,
        "skippedSamplingMissions": skipped,
        "nextAction": (
            "Let the launched Hermes sampling mission run, then close it with operator value feedback."
            if launched and not args.dry_run
            else "Capacity guard prevented launch; retry after active missions complete."
            if skipped and skipped[-1].get("reason") == "capacity_guard"
            else "Run this without --dry-run to launch the next Hermes value-scored sampling mission."
            if args.dry_run
            else "No new sampling mission was needed or launchable."
        ),
    }
    if args.write:
        out_path = root / ".agent_control" / "route_trust_sampling" / (
            "dry_run_latest.json" if args.dry_run else "latest.json"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["evidencePath"] = str(out_path)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch safe Hermes route-trust sampling missions from the current coverage plan.")
    parser.add_argument("--root", default=str(ROOT), help="Workspace/control root.")
    parser.add_argument("--max-new", type=int, default=1, help="Maximum sampling missions to launch in one run.")
    parser.add_argument("--max-active", type=int, default=4, help="Do not launch if active missions are already at this count.")
    parser.add_argument("--max-queued", type=int, default=2, help="Do not launch if queued missions exceed this count.")
    parser.add_argument("--runtime", choices=["hermes", "openclaw", "auto"], default="hermes")
    parser.add_argument("--mode", default="Autopilot")
    parser.add_argument("--budget-hours", type=int, default=4)
    parser.add_argument("--skip-route-contract", action="store_true")
    parser.add_argument(
        "--shared-workspace",
        action="store_true",
        help="Use the primary workspace slot instead of a per-task isolated route-trust workspace.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write", action="store_true", help="Write .agent_control/route_trust_sampling/latest.json")
    args = parser.parse_args(argv)

    payload = run_sampling(args)
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
