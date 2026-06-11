from __future__ import annotations

import argparse
import json
import pathlib
import re
import time
from datetime import datetime, timezone
from typing import Any

import requests
import urllib3


DEFAULT_BASE_URL = "https://sysnology.tail602108.ts.net:47880"


def _load_credentials(root: pathlib.Path) -> tuple[str, str]:
    text = (root / ".agent_control" / "grand_agent_admin_password.txt").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    username_match = re.search(r"^\s*Username:\s*(.+)$", text, re.M | re.I)
    password_match = re.search(r"^\s*Password:\s*(.+)$", text, re.M | re.I)
    if not username_match or not password_match:
        raise SystemExit("Missing web admin credentials under .agent_control.")
    return username_match.group(1).strip(), password_match.group(1).strip()


def _backend(session: requests.Session, base_url: str, command: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    response = session.post(
        f"{base_url}/api/backend",
        json={"command": command, "payload": {"payload": payload}},
        timeout=timeout,
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict) or "data" not in body:
        raise RuntimeError(f"Unexpected backend response for {command}: {body!r}")
    return body["data"]


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = pathlib.Path(args.root).resolve()
    if args.insecure:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    username, password = _load_credentials(root)
    session = requests.Session()
    session.verify = not args.insecure
    login = session.post(
        f"{args.base_url}/api/auth/login",
        json={"username": username, "password": password},
        timeout=args.timeout_seconds,
    )
    login.raise_for_status()

    summary = _backend(
        session,
        args.base_url,
        "get_control_room_summary_command",
        {"root": None, "summaryMode": "bootstrap"},
        args.timeout_seconds,
    )
    missions = summary.get("missions", []) if isinstance(summary.get("missions"), list) else []
    running = [
        mission
        for mission in missions
        if isinstance(mission, dict) and mission.get("status") == "running"
    ]
    target_missions = running[: args.mission_limit]
    target_source = "running"
    if not target_missions:
        target_missions = [
            mission
            for mission in missions
            if isinstance(mission, dict)
            and str(mission.get("status") or "").strip().lower() not in {"draft", "stopped"}
        ][: args.mission_limit]
        target_source = "recent_live_non_draft"

    measurements: list[dict[str, Any]] = []
    for pass_index in range(args.passes):
        for mission in target_missions:
            mission_id = str(mission.get("mission_id") or mission.get("missionId") or "").strip()
            if not mission_id:
                continue
            started = time.perf_counter()
            detail = _backend(
                session,
                args.base_url,
                "get_control_room_mission_detail_command",
                {"missionId": mission_id, "root": None, "eventLimit": args.event_limit},
                args.timeout_seconds,
            )
            wall_ms = (time.perf_counter() - started) * 1000
            performance = detail.get("performance", {}) if isinstance(detail.get("performance"), dict) else {}
            budget = performance.get("budget", {}) if isinstance(performance.get("budget"), dict) else {}
            cache = (
                detail.get("detailCache", {})
                if isinstance(detail.get("detailCache"), dict)
                else performance.get("missionDetailCache", {})
                if isinstance(performance.get("missionDetailCache"), dict)
                else {}
            )
            measurements.append(
                {
                    "pass": pass_index + 1,
                    "missionId": mission_id,
                    "title": str(mission.get("title") or ""),
                    "runtime": str(mission.get("runtime_id") or mission.get("runtimeId") or ""),
                    "wallMs": round(wall_ms, 2),
                    "durationMs": performance.get("durationMs"),
                    "payloadBytes": performance.get("payloadBytes"),
                    "budgetStatus": str(budget.get("status") or "unknown"),
                    "cacheStatus": str(cache.get("status") or "unknown"),
                    "cacheFreshness": str(cache.get("freshness") or ""),
                    "generationDurationMs": cache.get("generationDurationMs"),
                    "runtimeTranscriptStatus": (
                        detail.get("runtimeTranscript", {}).get("status")
                        if isinstance(detail.get("runtimeTranscript"), dict)
                        else ""
                    ),
                    "agentMessageCount": len(detail.get("agentMessages", []))
                    if isinstance(detail.get("agentMessages"), list)
                    else 0,
                }
            )

    wall_warn_measurements = [
        item
        for item in measurements
        if float(item.get("wallMs") or 0) > args.wall_budget_ms
    ]
    backend_warn_measurements = [
        item
        for item in measurements
        if item.get("budgetStatus") != "pass"
    ]
    warn_measurements = [*backend_warn_measurements, *wall_warn_measurements]
    seen_warning_keys: set[tuple[int, str, float]] = set()
    deduped_warn_measurements: list[dict[str, Any]] = []
    for item in warn_measurements:
        key = (int(item.get("pass") or 0), str(item.get("missionId") or ""), float(item.get("wallMs") or 0))
        if key in seen_warning_keys:
            continue
        seen_warning_keys.add(key)
        deduped_warn_measurements.append(item)
    warn_measurements = deduped_warn_measurements
    cold_backend_warn_measurements = [
        item
        for item in backend_warn_measurements
        if item.get("pass") == 1 and item.get("cacheStatus") != "hit"
    ]
    warm_backend_warn_measurements = [
        item
        for item in backend_warn_measurements
        if item.get("cacheStatus") == "hit" or item.get("pass", 0) > 1
    ]
    cold_wall_warn_measurements = [
        item
        for item in wall_warn_measurements
        if item.get("pass") == 1 and item.get("cacheStatus") != "hit"
    ]
    warm_wall_warn_measurements = [
        item
        for item in wall_warn_measurements
        if item.get("cacheStatus") == "hit" or item.get("pass", 0) > 1
    ]
    max_wall_ms = max((float(item.get("wallMs") or 0) for item in measurements), default=0.0)
    max_duration_ms = max((float(item.get("durationMs") or 0) for item in measurements), default=0.0)
    ok = (
        len(backend_warn_measurements) == 0
        and len(warm_wall_warn_measurements) == 0
        and len(measurements) > 0
    )
    return {
        "schema": "fluxio.live_mission_detail_performance.v1",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "baseUrl": args.base_url,
        "summaryGeneratedAt": summary.get("generatedAt", ""),
        "missionCount": len(missions),
        "runningMissionCount": len(running),
        "targetMissionCount": len(target_missions),
        "targetMissionSource": target_source,
        "passes": args.passes,
        "eventLimit": args.event_limit,
        "wallBudgetMs": args.wall_budget_ms,
        "measurementCount": len(measurements),
        "warningCount": len(warn_measurements),
        "backendWarningCount": len(backend_warn_measurements),
        "wallWarningCount": len(wall_warn_measurements),
        "coldWarningCount": len(cold_backend_warn_measurements),
        "warmWarningCount": len(warm_backend_warn_measurements),
        "coldTransportWarningCount": len(cold_wall_warn_measurements),
        "warmTransportWarningCount": len(warm_wall_warn_measurements),
        "maxWallMs": round(max_wall_ms, 2),
        "maxDurationMs": round(max_duration_ms, 2),
        "ok": ok,
        "measurements": measurements,
        "warnings": warn_measurements[:10],
        "nextAction": (
            "Keep the current mission-detail cache and bounded transcript readers."
            if ok and not wall_warn_measurements
            else "Backend detail is within budget; investigate transport warm-up if first-click wall time remains high."
            if ok
            else "Reduce cold mission-detail generation time before claiming speed parity."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure authenticated live NAS mission-detail performance.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--mission-limit", type=int, default=2)
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--event-limit", type=int, default=80)
    parser.add_argument("--wall-budget-ms", type=float, default=450.0)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=".agent_control/live_mission_detail_performance_latest.json")
    parser.add_argument("--insecure", action="store_true", default=True)
    args = parser.parse_args()

    report = build_report(args)
    print(json.dumps(report, indent=2))
    if args.write:
        output = pathlib.Path(args.output)
        if not output.is_absolute():
            output = pathlib.Path(args.root).resolve() / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
