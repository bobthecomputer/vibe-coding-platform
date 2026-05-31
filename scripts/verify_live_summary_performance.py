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
    data = body["data"]
    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected data response for {command}: {data!r}")
    return data


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

    measurements: list[dict[str, Any]] = []
    for pass_index in range(args.passes):
        started = time.perf_counter()
        summary = _backend(
            session,
            args.base_url,
            "get_control_room_summary_command",
            {"root": None, "summaryMode": "bootstrap"},
            args.timeout_seconds,
        )
        wall_ms = (time.perf_counter() - started) * 1000
        performance = summary.get("performance", {}) if isinstance(summary.get("performance"), dict) else {}
        budget = performance.get("budget", {}) if isinstance(performance.get("budget"), dict) else {}
        cache = summary.get("summaryCache", {}) if isinstance(summary.get("summaryCache"), dict) else {}
        measurements.append(
            {
                "pass": pass_index + 1,
                "wallMs": round(wall_ms, 2),
                "durationMs": performance.get("durationMs"),
                "payloadBytes": performance.get("payloadBytes"),
                "budgetStatus": str(budget.get("status") or "unknown"),
                "cacheStatus": str(cache.get("status") or "unknown"),
                "missionRows": len(summary.get("missions", [])) if isinstance(summary.get("missions"), list) else 0,
                "missionCount": int((summary.get("counts") or {}).get("missions") or 0)
                if isinstance(summary.get("counts"), dict)
                else 0,
                "notificationCount": len(summary.get("notifications", [])) if isinstance(summary.get("notifications"), list) else 0,
                "summaryMode": str(summary.get("summaryMode") or ""),
            }
        )

    wall_warn_measurements = [
        item
        for item in measurements
        if float(item.get("wallMs") or 0) > args.wall_budget_ms
    ]
    payload_warn_measurements = [
        item
        for item in measurements
        if int(item.get("payloadBytes") or 0) > args.payload_budget_bytes
    ]
    backend_warn_measurements = [
        item
        for item in measurements
        if item.get("budgetStatus") not in {"pass", "unknown"}
    ]
    max_wall_ms = max((float(item.get("wallMs") or 0) for item in measurements), default=0.0)
    max_payload_bytes = max((int(item.get("payloadBytes") or 0) for item in measurements), default=0)
    ok = bool(measurements) and not wall_warn_measurements and not payload_warn_measurements and not backend_warn_measurements
    return {
        "schema": "fluxio.live_summary_performance.v1",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "baseUrl": args.base_url,
        "passes": args.passes,
        "wallBudgetMs": args.wall_budget_ms,
        "payloadBudgetBytes": args.payload_budget_bytes,
        "measurementCount": len(measurements),
        "warningCount": len(wall_warn_measurements) + len(payload_warn_measurements) + len(backend_warn_measurements),
        "wallWarningCount": len(wall_warn_measurements),
        "payloadWarningCount": len(payload_warn_measurements),
        "backendWarningCount": len(backend_warn_measurements),
        "maxWallMs": round(max_wall_ms, 2),
        "maxPayloadBytes": max_payload_bytes,
        "ok": ok,
        "measurements": measurements,
        "warnings": [*wall_warn_measurements, *payload_warn_measurements, *backend_warn_measurements][:10],
        "nextAction": (
            "Keep the bootstrap summary bounded and cached."
            if ok
            else "Reduce bootstrap summary payload size or first-paint wall time before claiming speed parity."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure authenticated live NAS bootstrap-summary performance.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--passes", type=int, default=5)
    parser.add_argument("--wall-budget-ms", type=float, default=450.0)
    parser.add_argument("--payload-budget-bytes", type=int, default=350000)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=".agent_control/live_summary_performance_latest.json")
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
