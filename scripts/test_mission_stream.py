#!/usr/bin/env python3
"""
Test mission event generator for proving SSE stream.

Writes sample mission events to .agent_control/mission_events.jsonl
and creates corresponding mission state files under .agent_control/mission_XXX/.

Run from the project root:
    python scripts/test_mission_stream.py [--root /path/to/project]

Each run appends a fresh set of 3-5 events per test mission.
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_event(mission_id: str, kind: str, message: str, metadata: dict | None = None) -> dict:
    return {
        "mission_id": mission_id,
        "kind": kind,
        "message": message,
        "timestamp": utc_now_iso(),
        "metadata": metadata or {},
    }


def write_events(events_path: Path, events: list[dict]) -> None:
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")


def write_mission_state(mission_id: str, control_dir: Path, state: dict) -> None:
    mission_dir = control_dir / f"mission_{mission_id}"
    mission_dir.mkdir(parents=True, exist_ok=True)
    state_path = mission_dir / "mission_state.json"
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def generate_test_missions(root: Path) -> list[tuple[str, str]]:
    """Return list of (mission_id, workspace_id) pairs for test missions."""
    return [
        (f"test_mission_{uuid.uuid4().hex[:8]}", "workspace_primary"),
        (f"test_mission_{uuid.uuid4().hex[:8]}", "workspace_primary"),
    ]


def build_mission_state(mission_id: str, workspace_id: str, status: str) -> dict:
    return {
        "mission_id": mission_id,
        "workspace_id": workspace_id,
        "status": status,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "state": {
            "status": status,
            "cycle_count": 0,
            "current_cycle_phase": "plan",
            "queue_position": 0,
        },
        "proof": {
            "summary": "",
            "changed_files": [],
            "passed_checks": [],
            "failed_checks": [],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate test mission events for SSE stream")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).parent.parent,
        help="Project root (default: parent of scripts/)",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    control_dir = root / ".agent_control"
    events_path = control_dir / "mission_events.jsonl"

    print(f"Project root : {root}")
    print(f"Control dir  : {control_dir}")
    print(f"Events file  : {events_path}")
    print()

    missions = generate_test_missions(root)

    for mission_id, workspace_id in missions:
        print(f"--- Mission: {mission_id} ---")

        # Build 3-5 events per mission
        events = [
            make_event(
                mission_id,
                "mission.created",
                f"Mission {mission_id} created for workspace {workspace_id}.",
                metadata={"workspaceId": workspace_id, "mode": "test"},
            ),
            make_event(
                mission_id,
                "mission.started",
                "Mission started — entering planning phase.",
                metadata={"workspaceId": workspace_id, "phase": "plan"},
            ),
            make_event(
                mission_id,
                "mission.planning",
                "Planner is drafting the execution plan.",
                metadata={"workspaceId": workspace_id, "step": "draft_plan"},
            ),
            make_event(
                mission_id,
                "mission.running",
                "Plan approved — executing steps.",
                metadata={
                    "workspaceId": workspace_id,
                    "approved_steps": ["step_1", "step_2", "step_3"],
                },
            ),
            make_event(
                mission_id,
                "mission.completed",
                "All steps completed successfully.",
                metadata={
                    "workspaceId": workspace_id,
                    "changed_files": ["src/main.py", "tests/test_main.py"],
                    "passed_checks": ["lint", "test"],
                },
            ),
        ]

        write_events(events_path, events)
        print(f"  Wrote {len(events)} events")

        for ev in events:
            print(f"    [{ev['kind']}] {ev['message'][:60]}")

        # Write the mission state file
        final_state = build_mission_state(mission_id, workspace_id, status="completed")
        write_mission_state(mission_id, control_dir, final_state)
        state_path = control_dir / f"mission_{mission_id}" / "mission_state.json"
        print(f"  Wrote state: {state_path}")

    print()
    print("Done. To verify the SSE stream, run the control-room SSE endpoint and observe events.")


if __name__ == "__main__":
    main()
