from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


def _safe_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _child_dirs(path: Path, *, limit: int = 12) -> list[str]:
    if not path.exists():
        return []
    try:
        return sorted(item.name for item in path.iterdir() if item.is_dir())[:limit]
    except OSError:
        return []


def _workspace_status(app_root: Path) -> dict:
    package = _safe_json(app_root / "package.json")
    skills = _child_dirs(app_root / "skills")
    services = _child_dirs(app_root / "services")
    apps = _child_dirs(app_root / "apps")
    return {
        "ok": True,
        "status": "ready",
        "runtime": "fluxio-python-mind-tower-bridge",
        "workspaceRoot": str(app_root),
        "packageName": str(package.get("name") or "mind-tower"),
        "packageVersion": str(package.get("version") or "not reported"),
        "skills": skills,
        "services": services,
        "apps": apps,
        "skillCount": len(skills),
        "serviceCount": len(services),
        "appCount": len(apps),
        "message": "Mind Tower workspace files are readable through the Fluxio Python bridge.",
    }


class MindTowerHandler(BaseHTTPRequestHandler):
    app_root: Path

    def _send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path in {"/health", "/api/health", "/api/connections/status"}:
            self._send_json(_workspace_status(self.app_root))
            return
        if path in {"/api/skills", "/api/skill/list"}:
            status = _workspace_status(self.app_root)
            self._send_json(
                {
                    "ok": True,
                    "status": "ready",
                    "workspaceRoot": status["workspaceRoot"],
                    "skills": status["skills"],
                    "services": status["services"],
                    "apps": status["apps"],
                }
            )
            return
        self._send_json({"ok": False, "status": "not_found", "path": path}, status=404)

    def log_message(self, format: str, *args: object) -> None:
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Expose Mind Tower workspace status for Fluxio.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3000)
    args = parser.parse_args(argv)

    app_root = Path(args.root).expanduser().resolve()
    if not app_root.exists():
        raise SystemExit(f"Mind Tower root does not exist: {app_root}")
    MindTowerHandler.app_root = app_root
    server = ThreadingHTTPServer((args.host, args.port), MindTowerHandler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
