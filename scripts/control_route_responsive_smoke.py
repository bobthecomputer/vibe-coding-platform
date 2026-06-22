from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from control_route_visual_smoke import ROOT, main as visual_main


DEVICES = [
    {
        "name": "phone",
        "width": 390,
        "height": 844,
        "min_width": 360,
        "min_height": 720,
    },
    {
        "name": "tablet",
        "width": 820,
        "height": 1180,
        "min_width": 760,
        "min_height": 900,
    },
    {
        "name": "desktop",
        "width": 1440,
        "height": 1100,
        "min_width": 1200,
        "min_height": 900,
    },
]


def run_visual_check(args: argparse.Namespace, device: dict[str, int | str]) -> dict:
    report_path = Path(args.out_dir) / f"{args.name}-{device['name']}-check.json"
    device_name = str(device["name"])
    use_long_history_fixture = bool(args.long_history_fixture and device_name == "desktop")
    expected_fragments = list(args.expect)
    if args.long_history_fixture and not use_long_history_fixture:
        expected_fragments = ["Fixture review surface ready"]
    argv = [
        "control_route_visual_smoke.py",
        "--url",
        args.url,
        "--out-dir",
        args.out_dir,
        "--name",
        f"{args.name}-{device['name']}",
        "--browser",
        args.browser,
        "--width",
        str(device["width"]),
        "--height",
        str(device["height"]),
        "--min-width",
        str(device["min_width"]),
        "--min-height",
        str(device["min_height"]),
    ]
    if args.browser_path:
        argv.extend(["--browser-path", args.browser_path])
    if args.measure_performance and device["name"] == "desktop":
        argv.extend(
            [
                "--measure-performance",
                "--warm-tab-budget-ms",
                str(args.warm_tab_budget_ms),
                "--mission-switch-budget-ms",
                str(args.mission_switch_budget_ms),
                "--proof-pane-budget-ms",
                str(args.proof_pane_budget_ms),
            ]
        )
    if use_long_history_fixture:
        argv.append("--long-history-fixture")
    if args.assert_launch_interactions:
        argv.append("--assert-launch-interactions")
    for expected in expected_fragments:
        argv.extend(["--expect", expected])
    original_argv = sys.argv
    try:
        sys.argv = argv
        exit_code = visual_main()
    finally:
        sys.argv = original_argv
    if report_path.exists():
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    else:
        payload = {"passed": False, "error": "visual smoke did not write a report"}
    payload["device"] = device["name"]
    payload["exitCode"] = exit_code
    if args.long_history_fixture:
        payload["longHistoryFixture"] = "desktop-only" if use_long_history_fixture else "skipped-for-responsive-viewport"
    else:
        payload["longHistoryFixture"] = "not-requested"
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture phone, tablet, and desktop control-route screenshots.")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:5173/control?preview-control=1&fixture=live_review&mode=builder&surface=workbench",
    )
    parser.add_argument("--out-dir", default=str(ROOT / "tmp-ui-checks" / "responsive"))
    parser.add_argument("--name", default="control-responsive")
    parser.add_argument("--browser", choices=["auto", "chrome", "chromium", "edge", "zen"], default="auto")
    parser.add_argument("--browser-path", default="")
    parser.add_argument("--measure-performance", action="store_true")
    parser.add_argument(
        "--long-history-fixture",
        action="store_true",
        help="Use the long_history fixture for desktop browser speed budgets.",
    )
    parser.add_argument("--warm-tab-budget-ms", type=int, default=2500)
    parser.add_argument("--mission-switch-budget-ms", type=int, default=2500)
    parser.add_argument("--proof-pane-budget-ms", type=int, default=2500)
    parser.add_argument(
        "--assert-launch-interactions",
        action="store_true",
        help="Prove beginner launch URL prefill, contextual recommendation, and quickstart behavior on each viewport.",
    )
    parser.add_argument(
        "--expect",
        action="append",
        default=None,
        help="Rendered DOM text that must be present for Chromium DOM dumps.",
    )
    args = parser.parse_args()
    if args.expect is None:
        args.expect = ["Agent", "Builder", "Mission updates"]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = [run_visual_check(args, device) for device in DEVICES]
    passed = all(bool(item.get("passed")) for item in results)
    report = {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "url": args.url,
        "devices": results,
        "passed": passed,
    }
    report_path = out_dir / f"{args.name}-responsive-check.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
