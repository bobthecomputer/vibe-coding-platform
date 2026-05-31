from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 47880


def _port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _health_ok(base_url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False
    return bool(payload.get("ok"))


def _run_build(skip_build: bool) -> None:
    dist_index = ROOT / "web" / "dist" / "index.html"
    if skip_build or dist_index.exists():
        return
    subprocess.run(
        ["npm", "run", "frontend:build"],
        cwd=ROOT,
        check=True,
    )


def _start_backend(host: str, port: int) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_web_backend.py"),
            "--host",
            host,
            "--port",
            str(port),
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _wait_for_backend(base_url: str, process: subprocess.Popen | None) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if _health_ok(base_url):
            return
        if process is not None and process.poll() is not None:
            output = ""
            if process.stdout is not None:
                output = process.stdout.read()
            raise RuntimeError(f"Fluxio backend exited early.\n{output}")
        time.sleep(0.35)
    raise TimeoutError(f"Fluxio backend did not become healthy at {base_url}/health")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Start Fluxio's local web console and open Builder."
    )
    parser.add_argument("--host", default=os.environ.get("FLUXIO_WEB_HOST", DEFAULT_HOST))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("FLUXIO_WEB_PORT", DEFAULT_PORT)),
    )
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser tab.")
    parser.add_argument("--skip-build", action="store_true", help="Do not build missing web assets.")
    args = parser.parse_args(argv)

    _run_build(skip_build=args.skip_build)
    base_url = f"http://{args.host}:{args.port}"
    process: subprocess.Popen | None = None
    reused = _port_open(args.host, args.port)
    if not reused:
        process = _start_backend(args.host, args.port)
    _wait_for_backend(base_url, process)

    control_url = f"{base_url}/control"
    print(
        json.dumps(
            {
                "ok": True,
                "url": control_url,
                "backend": "reused" if reused else "started",
                "pid": process.pid if process is not None else None,
            },
            indent=2,
        ),
        flush=True,
    )
    if not args.no_open:
        webbrowser.open(control_url)
    if process is not None:
        try:
            process.wait()
        except KeyboardInterrupt:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
