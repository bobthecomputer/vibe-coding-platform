from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "docs" / "cleanup" / "verification"
SCREENSHOT_DIR = ROOT / "docs" / "cleanup" / "before-after" / "2026-05-20"
CONTROL_URL = "http://127.0.0.1:1420/control?preview-control=1"

VISUAL_ROUTES = [
    {
        "name": "surface-home",
        "url": f"{CONTROL_URL}&fixture=live_review&surface=home",
        "expect": ["Syntelos", "Agent", "Rule Sets"],
    },
    {
        "name": "surface-agent",
        "url": f"{CONTROL_URL}&fixture=live_review&surface=agent",
        "expect": ["Agent Chat", "Workspace", "Model"],
    },
    {
        "name": "surface-builder",
        "url": f"{CONTROL_URL}&fixture=live_review&mode=builder&surface=builder",
        "expect": ["Builder", "Rule Set", "Timeline"],
    },
    {
        "name": "surface-skills",
        "url": f"{CONTROL_URL}&fixture=live_review&surface=skills",
        "expect": ["Skills", "Scope", "Trigger"],
    },
    {
        "name": "surface-rule-sets",
        "url": f"{CONTROL_URL}&fixture=live_review&surface=rule-sets",
        "expect": ["Rule Sets", "Core policy", "Approval"],
    },
    {
        "name": "surface-settings",
        "url": f"{CONTROL_URL}&fixture=live_review&surface=settings",
        "expect": ["Settings", "Manage your workspace", "Routing"],
    },
    {
        "name": "runtime-workbench-visual-proof",
        "url": f"{CONTROL_URL}&fixture=live_review&mode=builder&surface=workbench",
        "expect": ["Runtime operations", "Automatic verify", "OpenClaw", "Hermes"],
    },
]

ZEN_WORKBENCH_ROUTE = {
    "name": "runtime-workbench-zen-proof",
    "url": f"{CONTROL_URL}&fixture=live_review&mode=builder&surface=workbench",
    "expect": ["Runtime operations", "Automatic verify", "OpenClaw", "Hermes"],
    "browser": "zen",
}


def npm_bin() -> str:
    return "npm.cmd" if platform.system().lower().startswith("win") else "npm"


def run_step(name: str, command: list[str], cwd: Path = ROOT, timeout: int = 300) -> dict[str, object]:
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    elapsed = time.perf_counter() - started
    stdout_tail = completed.stdout[-4000:] if completed.stdout else ""
    stderr_tail = completed.stderr[-4000:] if completed.stderr else ""
    return {
        "name": name,
        "command": command,
        "cwd": str(cwd),
        "returnCode": completed.returncode,
        "durationSeconds": round(elapsed, 2),
        "stdoutTail": stdout_tail,
        "stderrTail": stderr_tail,
        "passed": completed.returncode == 0,
    }


def ensure_dev_server() -> dict[str, object]:
    probe = run_step(
        "control route dev-server probe",
        [sys.executable, "-c", f"import urllib.request; urllib.request.urlopen({CONTROL_URL!r}, timeout=5).read(256)"],
        timeout=10,
    )
    if probe["passed"]:
        probe["startedServer"] = False
        return probe

    npm = npm_bin()
    stdout = ROOT / ".tmp-control-frontend.out.log"
    stderr = ROOT / ".tmp-control-frontend.err.log"
    with stdout.open("ab") as out_file, stderr.open("ab") as err_file:
        subprocess.Popen(
            [npm, "run", "frontend:dev"],
            cwd=ROOT,
            stdout=out_file,
            stderr=err_file,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    for _ in range(20):
        time.sleep(1)
        probe = run_step(
            "control route dev-server probe",
            [sys.executable, "-c", f"import urllib.request; urllib.request.urlopen({CONTROL_URL!r}, timeout=5).read(256)"],
            timeout=10,
        )
        if probe["passed"]:
            probe["startedServer"] = True
            return probe
    probe["startedServer"] = True
    return probe


def zen_available() -> bool:
    candidates = [
        Path(r"C:\Program Files\Zen Browser\zen.exe"),
        Path(r"C:\Program Files\Zen\zen.exe"),
        Path.home() / "AppData" / "Local" / "Programs" / "Zen Browser" / "zen.exe",
        Path.home() / "AppData" / "Local" / "zen" / "zen.exe",
    ]
    return any(path.exists() for path in candidates) or shutil.which("zen") is not None


def visual_step(route: dict[str, object]) -> dict[str, object]:
    command = [
        sys.executable,
        "scripts/control_route_visual_smoke.py",
        "--url",
        str(route["url"]),
        "--name",
        str(route["name"]),
    ]
    if route.get("browser"):
        command.extend(["--browser", str(route["browser"])])
    for fragment in route["expect"]:
        command.extend(["--expect", str(fragment)])
    result = run_step(f"visual smoke {route['name']}", command, timeout=120)
    check_path = SCREENSHOT_DIR / f"{route['name']}-check.json"
    if check_path.exists():
        try:
            result["visualReport"] = json.loads(check_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            result["visualReport"] = {"error": "Could not parse visual report JSON."}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full non-void Syntelos control workspace verification loop.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip the full Python test suite.")
    parser.add_argument("--skip-visual", action="store_true", help="Skip screenshot visual smoke checks.")
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    steps: list[dict[str, object]] = []

    steps.append(
        run_step(
            "python library import",
            [sys.executable, "-c", "import grant_agent; print(','.join(grant_agent.__all__))"],
            timeout=30,
        )
    )
    if not args.skip_tests:
        steps.append(run_step("python tests", [sys.executable, "-m", "pytest", "tests", "-q"], timeout=420))
    steps.append(run_step("rust cargo check", ["cargo", "check"], cwd=ROOT / "src-tauri", timeout=240))
    steps.append(run_step("frontend build", [npm_bin(), "run", "frontend:build"], timeout=180))

    server = ensure_dev_server()
    steps.append(server)
    if server["passed"]:
        steps.append(run_step("browser html smoke", [npm_bin(), "run", "verify:browser", "--", CONTROL_URL], timeout=60))
        steps.append(run_step("browser click interaction smoke", [sys.executable, "scripts/control_route_interaction_smoke.py"], timeout=180))
        if not args.skip_visual:
            if not shutil.which("python"):
                steps.append({"name": "visual smoke preflight", "passed": False, "error": "python executable not found"})
            for route in VISUAL_ROUTES:
                steps.append(visual_step(route))
            if zen_available():
                steps.append(visual_step(ZEN_WORKBENCH_ROUTE))
            else:
                steps.append(
                    {
                        "name": "visual smoke runtime-workbench-zen-proof",
                        "passed": True,
                        "skipped": True,
                        "reason": "Zen Browser executable was not found.",
                    }
                )
    else:
        steps.append({"name": "browser html smoke", "passed": False, "error": "Dev server did not respond."})

    passed = all(step.get("passed") for step in steps)
    report = {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "goal": "non-void control workspace verification loop",
        "passed": passed,
        "steps": steps,
    }
    report_path = REPORT_DIR / "control-workspace-verify-2026-05-20.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"passed": passed, "reportPath": str(report_path), "stepCount": len(steps)}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
