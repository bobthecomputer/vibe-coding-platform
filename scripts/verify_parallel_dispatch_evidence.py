from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from grant_agent.mission_control import ControlRoomStore
from grant_agent.mission_watchdog import (
    SCOPE_SAFE,
    build_mission_watchdog_report,
)


def build_parallel_dispatch_evidence(root: Path, *, require_safe_candidate: bool = False) -> dict:
    root = root.resolve()
    store = ControlRoomStore(root)
    report = build_mission_watchdog_report(
        root=root,
        missions=store.load_missions(),
        workspaces=store.load_workspaces(),
    )
    issues = [
        item
        for item in report.get("issues", [])
        if isinstance(item, dict) and item.get("kind") == "workspace_queue_pressure"
    ]
    failures: list[dict] = []
    safe_candidates: list[dict] = []
    blocked_candidates: list[dict] = []

    for item in issues:
        mission_id = str(item.get("missionId") or "")
        scope_safety = str(item.get("scopeSafety") or "unknown")
        scope_evidence = item.get("scopeEvidence") if isinstance(item.get("scopeEvidence"), dict) else {}
        first_step = str(item.get("firstStep") or "")
        exposes_parallelize = "--action parallelize-worktree" in first_step
        active_count = int(scope_evidence.get("activeFileCount") or 0)
        queued_count = int(scope_evidence.get("queuedFileCount") or 0)
        overlap_files = scope_evidence.get("overlapFiles") or []

        row = {
            "missionId": mission_id,
            "scopeSafety": scope_safety,
            "activeFileCount": active_count,
            "queuedFileCount": queued_count,
            "overlapFiles": overlap_files,
            "exposesParallelizeAction": exposes_parallelize,
        }
        if scope_safety == SCOPE_SAFE:
            safe_candidates.append(row)
            if not exposes_parallelize:
                failures.append({**row, "reason": "safe candidate does not expose parallel dispatch"})
            if active_count <= 0 or queued_count <= 0:
                failures.append({**row, "reason": "safe candidate lacks concrete file-scope counts"})
            if overlap_files:
                failures.append({**row, "reason": "safe candidate contains overlap files"})
        else:
            blocked_candidates.append(row)
            if exposes_parallelize:
                failures.append({**row, "reason": "unsafe candidate exposes parallel dispatch"})

    if require_safe_candidate and not safe_candidates:
        failures.append(
            {
                "missionId": "",
                "scopeSafety": "missing",
                "reason": "no safe queue-pressure candidate exists in the current live watchdog report",
            }
        )

    return {
        "schema": "fluxio.parallel_dispatch_evidence.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "ok": not failures,
        "watchdogReport": {
            "issueCount": len(report.get("issues", [])),
            "queuePressure": report.get("summary", {}).get("queuePressure", 0),
            "queuePressureSafe": report.get("summary", {}).get("queuePressureSafe", 0),
            "queuePressureUnknown": report.get("summary", {}).get("queuePressureUnknown", 0),
            "queuePressureOverlap": report.get("summary", {}).get("queuePressureOverlap", 0),
        },
        "safeCandidates": safe_candidates,
        "blockedCandidates": blocked_candidates,
        "failures": failures,
        "nextAction": (
            "Parallel dispatch evidence is release-safe."
            if not failures
            else "Keep unsafe queued missions serial, collect file-scope evidence, or split objectives before dispatch."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify safe parallel-dispatch evidence.")
    parser.add_argument("--root", default=str(ROOT), help="Workspace root")
    parser.add_argument("--write", action="store_true", help="Write latest evidence artifact")
    parser.add_argument("--require-safe-candidate", action="store_true")
    args = parser.parse_args(argv)

    payload = build_parallel_dispatch_evidence(
        Path(args.root),
        require_safe_candidate=args.require_safe_candidate,
    )
    if args.write:
        output_path = Path(args.root) / ".agent_control" / "parallel_dispatch_evidence" / "latest.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["outputPath"] = str(output_path)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
