from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_self_improvement_evidence import (
    build_self_improvement_evidence,
    record_red_team_sample,
)


RUN_SCHEMA = "fluxio.self_improvement_red_team_loop_run.v1"
WATCHDOG_CADENCE_SCHEMA = "fluxio.self_improvement_watchdog_cadence.v1"
RUNNABLE_PLAN_STATUSES = {"empty", "pending_follow_up", "ready_for_follow_up"}


def _int_value(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _objective_from_plan(plan: dict, *, fallback_preset: str) -> str:
    preset = str(plan.get("preset") or fallback_preset or "hackaprompt")
    level = _int_value(plan.get("targetDifficultyLevel"), 1)
    difficulty_label = str(plan.get("difficultyLabel") or f"level {level}").strip()
    attempts = _int_value(plan.get("attemptBudget"), max(3, level * 3))
    target = _int_value(plan.get("targetResistanceScore"), 90)
    tactics = [str(item) for item in plan.get("tactics") or [] if str(item or "").strip()]
    tactic_count = max(1, len(tactics))
    return (
        f"Run {preset} at {difficulty_label} with {attempts} attempts, "
        f"{tactic_count} tactic families, and target resistance {target}+."
    )


def _watchdog_self_improvement_path(root: Path) -> Path:
    return root / ".agent_control" / "self_improvement_evidence" / "watchdog_latest.json"


def _watchdog_self_improvement_history_path(root: Path) -> Path:
    return root / ".agent_control" / "self_improvement_evidence" / "watchdog_history.jsonl"


def _history_line_count(path: Path) -> int:
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def record_watchdog_cadence_receipt(
    root: Path,
    run_payload: dict,
    *,
    interval_minutes: int = 0,
) -> dict:
    root = root.resolve()
    latest_path = _watchdog_self_improvement_path(root)
    history_path = _watchdog_self_improvement_history_path(root)
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.parent.mkdir(parents=True, exist_ok=True)

    generated_at = str(run_payload.get("generatedAt") or datetime.now(timezone.utc).isoformat())
    latest_red_team = (
        run_payload.get("latestRedTeam", {})
        if isinstance(run_payload.get("latestRedTeam"), dict)
        else {}
    )
    next_plan = (
        latest_red_team.get("nextBenchmarkPlan", {})
        if isinstance(latest_red_team.get("nextBenchmarkPlan"), dict)
        else {}
    )
    history_index = _history_line_count(history_path) + 1
    ok = bool(run_payload.get("ok", False))
    receipt = {
        "schema": WATCHDOG_CADENCE_SCHEMA,
        "enabled": True,
        "root": str(root),
        "generatedAt": generated_at,
        "intervalMinutes": max(0, int(interval_minutes or 0)),
        "maxSteps": _int_value(run_payload.get("maxSteps"), 0),
        "previousRunAt": "",
        "nextDueAt": generated_at,
        "aggregateOnly": True,
        "rawPayloadExport": False,
        "receiptPath": str(latest_path),
        "historyPath": str(history_path),
        "historyIndex": history_index,
        "status": "completed" if ok else "failed",
        "ok": ok,
        "lastAttemptAt": generated_at,
        "command": "direct:advance_self_improvement_red_team_loop",
        "exitCode": 0 if ok else 1,
        "completedSteps": _int_value(run_payload.get("completedSteps"), 0),
        "stoppedReason": str(run_payload.get("stoppedReason") or ""),
        "latestHistoryRows": _int_value(latest_red_team.get("historyRows"), 0),
        "nextAttemptBudget": _int_value(next_plan.get("attemptBudget"), 0),
        "nextPlanStatus": str(next_plan.get("status") or ""),
        "nextAction": str(run_payload.get("nextAction") or ""),
    }

    tmp = latest_path.with_name(f"{latest_path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    tmp.replace(latest_path)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, separators=(",", ":")) + "\n")
    return receipt


def advance_red_team_loop(
    root: Path,
    *,
    max_steps: int,
    write: bool,
    preset_override: str = "",
    objective_override: str = "",
) -> dict:
    root = root.resolve()
    completed_steps = 0
    steps: list[dict] = []
    stopped_reason = "max_steps_reached"
    latest_evidence = build_self_improvement_evidence(root, write=write)

    for index in range(max(0, max_steps)):
        red_team = latest_evidence.get("redTeam", {}) if isinstance(latest_evidence, dict) else {}
        plan = red_team.get("nextBenchmarkPlan", {}) if isinstance(red_team, dict) else {}
        status = str(plan.get("status") or "").strip()
        before_rows = _int_value(red_team.get("historyRows"), 0)
        seed_history = [
            row
            for row in red_team.get("historyTail", [])
            if isinstance(row, dict)
        ] if isinstance(red_team.get("historyTail"), list) else []
        if status not in RUNNABLE_PLAN_STATUSES:
            stopped_reason = f"plan_not_runnable:{status or 'unknown'}"
            break

        preset = str(preset_override or plan.get("preset") or "hackaprompt")
        objective = objective_override or _objective_from_plan(plan, fallback_preset=preset)
        sample = record_red_team_sample(
            root,
            preset_name=preset,
            objective=objective,
            history_override=seed_history or None,
        )
        latest_evidence = build_self_improvement_evidence(
            root,
            write=write,
            recorded_red_team_sample=sample,
        )
        next_red_team = latest_evidence.get("redTeam", {}) if isinstance(latest_evidence, dict) else {}
        steps.append(
            {
                "index": index + 1,
                "status": "recorded",
                "beforeHistoryRows": before_rows,
                "afterHistoryRows": _int_value(next_red_team.get("historyRows"), before_rows),
                "preset": preset,
                "objective": objective,
                "planStatus": status,
                "source": str(red_team.get("source") or "local_red_team_history"),
                "seedHistoryRows": len(seed_history),
                "attemptBudget": _int_value(plan.get("attemptBudget"), 0),
                "targetDifficultyLevel": _int_value(plan.get("targetDifficultyLevel"), 0),
                "recordedHistoryPath": sample.get("historyPath", ""),
                "recordedAttemptCount": _int_value(sample.get("historyRow", {}).get("attempt_count"), 0),
                "nextPlanStatus": str(
                    (next_red_team.get("nextBenchmarkPlan", {}) or {}).get("status") or ""
                ),
                "nextAttemptBudget": _int_value(
                    (next_red_team.get("nextBenchmarkPlan", {}) or {}).get("attemptBudget"),
                    0,
                ),
                "aggregateOnly": True,
                "rawPayloadExport": False,
            }
        )
        completed_steps += 1

    if completed_steps == 0 and stopped_reason == "max_steps_reached":
        stopped_reason = "no_steps_requested"

    return {
        "schema": RUN_SCHEMA,
        "ok": True,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "maxSteps": max_steps,
        "completedSteps": completed_steps,
        "stoppedReason": stopped_reason,
        "steps": steps,
        "latestEvidencePath": str(
            root / ".agent_control" / "self_improvement_evidence" / "latest.json"
        ),
        "nextAction": latest_evidence.get("nextAction", ""),
        "latestRedTeam": latest_evidence.get("redTeam", {}),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Advance the aggregate-only self-improvement red-team loop for a bounded number of steps."
    )
    parser.add_argument("--root", default=str(ROOT), help="Workspace root")
    parser.add_argument("--max-steps", type=int, default=1, help="Maximum red-team follow-up samples to record")
    parser.add_argument("--write", action="store_true", help="Write the latest self-improvement evidence file")
    parser.add_argument(
        "--record-cadence-receipt",
        action="store_true",
        help="Also write the watchdog-compatible cadence receipt for UI/audit freshness.",
    )
    parser.add_argument(
        "--cadence-interval-minutes",
        type=int,
        default=0,
        help="Interval metadata to store in the optional watchdog-compatible receipt.",
    )
    parser.add_argument("--preset", default="", help="Optional challenge preset override")
    parser.add_argument("--objective", default="", help="Optional objective override for every recorded sample")
    args = parser.parse_args(argv)

    payload = advance_red_team_loop(
        Path(args.root),
        max_steps=args.max_steps,
        write=args.write,
        preset_override=args.preset,
        objective_override=args.objective,
    )
    if args.record_cadence_receipt:
        payload["watchdogReceipt"] = record_watchdog_cadence_receipt(
            Path(args.root),
            payload,
            interval_minutes=args.cadence_interval_minutes,
        )
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
