from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VISUAL_SMOKE = ROOT / "scripts" / "control_route_visual_smoke.py"
DEFAULT_OUT_DIR = ROOT / "tmp-ui-checks" / "windows-control-ui"


SURFACES = [
    {
        "name": "home-desktop",
        "surface": "home",
        "width": 1440,
        "height": 960,
        "expect": ["Agent", "Builder"],
    },
    {
        "name": "agent-desktop",
        "surface": "agent",
        "mode": "agent",
        "width": 1440,
        "height": 960,
        "expect": ["Agent Live", "Thread"],
    },
    {
        "name": "builder-desktop",
        "surface": "builder",
        "width": 1440,
        "height": 960,
        "expect": ["Builder", "Project readiness", "Preview mode"],
    },
    {
        "name": "workbench-desktop",
        "surface": "workbench",
        "width": 1440,
        "height": 960,
        "expect": ["Live State", "Screenshot", "Local target"],
    },
    {
        "name": "skills-desktop",
        "surface": "skills",
        "width": 1440,
        "height": 960,
        "expect": ["Skill library"],
    },
    {
        "name": "phone-desktop",
        "surface": "phone",
        "width": 1440,
        "height": 960,
        "expect": ["Phone progress"],
    },
    {
        "name": "images-desktop",
        "surface": "images",
        "mode": "agent",
        "width": 1440,
        "height": 960,
        "expect": ["Image Playground", "Prompt", "Generate image"],
    },
    {
        "name": "settings-models-desktop",
        "surface": "settings",
        "settings_tab": "general",
        "width": 1440,
        "height": 960,
        "expect": ["Models & Accounts", "Provider keys"],
    },
    {
        "name": "settings-workspace-desktop",
        "surface": "settings",
        "settings_tab": "workspace",
        "width": 1440,
        "height": 960,
        "expect": ["Workspace", "Local folder"],
    },
    {
        "name": "settings-appearance-desktop",
        "surface": "settings",
        "settings_tab": "appearance",
        "width": 1440,
        "height": 960,
        "expect": ["Appearance", "Fluxio Noir"],
    },
    {
        "name": "settings-rules-desktop",
        "surface": "settings",
        "settings_tab": "rules",
        "width": 1440,
        "height": 960,
        "expect": ["Rules & Routing", "Workspace Access Policy"],
    },
    {
        "name": "settings-runtimes-desktop",
        "surface": "settings",
        "settings_tab": "runtimes",
        "width": 1440,
        "height": 960,
        "expect": ["Runtimes & Rooms", "Hermes", "Bridge sessions"],
    },
    {
        "name": "settings-databases-desktop",
        "surface": "settings",
        "settings_tab": "databases",
        "width": 1440,
        "height": 960,
        "expect": ["Databases", "stores"],
    },
    {
        "name": "settings-team-desktop",
        "surface": "settings",
        "settings_tab": "team",
        "width": 1440,
        "height": 960,
        "expect": ["Team Manager", "Setup"],
    },
    {
        "name": "settings-runtimes-phone",
        "surface": "settings",
        "settings_tab": "runtimes",
        "width": 390,
        "height": 844,
        "min_width": 360,
        "min_height": 720,
        "expect": ["Runtimes & Rooms", "Hermes", "Bridge sessions"],
    },
]


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_http(url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if 200 <= int(response.status) < 500:
                    return
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.35)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def npm_command() -> str:
    return "npm.cmd" if sys.platform.startswith("win") else "npm"


def process_group_flags() -> int:
    return subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform.startswith("win") else 0


def stop_process_tree(process: subprocess.Popen[bytes | str] | None, timeout: float = 8.0) -> None:
    if process is None or process.poll() is not None:
        return
    if sys.platform.startswith("win"):
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()


def start_vite(port: int, *, env: dict[str, str] | None = None) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [
            npm_command(),
            "run",
            "frontend:dev",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--strictPort",
        ],
        cwd=ROOT,
        env=env,
        creationflags=process_group_flags(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def surface_url(base_url: str, surface: dict[str, object]) -> str:
    mode = str(surface.get("mode") or "builder")
    url = f"{base_url}/control?preview-control=1&fixture=live_review&mode={mode}&surface={surface['surface']}"
    settings_tab = surface.get("settings_tab")
    if settings_tab:
        url += f"&settingsTab={settings_tab}"
    return url


def run_surface_check(
    *,
    base_url: str,
    out_dir: Path,
    browser: str,
    browser_path: str,
    surface: dict[str, object],
    timeout: int,
) -> dict[str, object]:
    command = [
        sys.executable,
        str(VISUAL_SMOKE),
        "--url",
        surface_url(base_url, surface),
        "--out-dir",
        str(out_dir),
        "--name",
        str(surface["name"]),
        "--browser",
        browser,
        "--width",
        str(surface["width"]),
        "--height",
        str(surface["height"]),
        "--min-width",
        str(surface.get("min_width", 1000)),
        "--min-height",
        str(surface.get("min_height", 700)),
        "--render-timeout",
        str(timeout),
    ]
    if browser_path:
        command.extend(["--browser-path", browser_path])
    for fragment in surface["expect"]:
        command.extend(["--expect", str(fragment)])
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    report_path = out_dir / f"{surface['name']}-check.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    else:
        report = {
            "passed": False,
            "error": completed.stderr.strip() or completed.stdout.strip() or "visual smoke did not write a report",
        }
    return {
        "name": surface["name"],
        "surface": surface["surface"],
        "exitCode": completed.returncode,
        "elapsedMs": elapsed_ms,
        "passed": completed.returncode == 0 and bool(report.get("passed")),
        "reportPath": str(report_path),
        "screenshotPath": str(report.get("screenshotPath") or ""),
        "missingFragments": report.get("missingFragments") or [],
        "error": "" if completed.returncode == 0 else (completed.stderr.strip() or completed.stdout.strip())[:1600],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the local web UI and capture Windows-ready control screenshots.")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--browser", choices=["auto", "chrome", "chromium", "edge", "zen"], default="auto")
    parser.add_argument("--browser-path", default="")
    parser.add_argument("--keep-server", action="store_true")
    parser.add_argument("--surface-timeout", type=int, default=120)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--only", action="append", default=[], help="Surface check name to run; can be passed more than once.")
    args = parser.parse_args()

    port = args.port or free_port()
    base_url = f"http://127.0.0.1:{port}"
    run_dir = Path(args.out_dir) / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    server = start_vite(port)
    try:
        wait_for_http(f"{base_url}/control?preview-control=1", timeout=45)
        selected_names = {str(name).strip() for name in args.only if str(name).strip()}
        surfaces = [surface for surface in SURFACES if not selected_names or str(surface["name"]) in selected_names]
        results = []
        for surface in surfaces:
            latest = None
            for attempt in range(args.retries + 1):
                latest = run_surface_check(
                    base_url=base_url,
                    out_dir=run_dir,
                    browser=args.browser,
                    browser_path=args.browser_path,
                    surface=surface,
                    timeout=args.surface_timeout,
                )
                latest["attempt"] = attempt + 1
                if latest["passed"]:
                    break
            results.append(latest or {"name": surface["name"], "passed": False, "error": "surface was not checked"})
        passed = all(bool(item["passed"]) for item in results)
        report = {
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "schema": "fluxio.windows_control_ui_verification.v1",
            "baseUrl": base_url,
            "outDir": str(run_dir),
            "passed": passed,
            "surfaces": results,
        }
        report_path = run_dir / "windows-control-ui-check.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0 if passed else 1
    finally:
        if not args.keep_server:
            stop_process_tree(server)


if __name__ == "__main__":
    raise SystemExit(main())
