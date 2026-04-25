from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .subprocess_utils import hidden_windows_subprocess_kwargs

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 47880
DEFAULT_ROOT = Path(__file__).resolve().parents[2]
PROVIDER_ENV = {
    "openai": ("OPENAI_API_KEY",),
    "openai-codex": ("OPENAI_API_KEY", "FLUXIO_OPENAI_CODEX_OAUTH_PRESENT"),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "minimax": ("MINIMAX_API_KEY",),
    "minimax-cn": ("MINIMAX_API_KEY",),
    "minimax-portal": ("MINIMAX_OAUTH_TOKEN", "FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT"),
}


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: object) -> None:
    body = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "content-type, authorization")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("content-length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    payload = json.loads(raw)
    return payload if isinstance(payload, dict) else {}


def _as_payload(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    nested = value.get("payload")
    if isinstance(nested, dict):
        return nested
    return value


def _run_cli(
    root: Path,
    command: str,
    args: list[str],
    timeout: int = 180,
    extra_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    cmd = [sys.executable, "-m", "grant_agent.cli", command, "--root", str(root), *args]
    env = os.environ.copy()
    env.update(extra_env or {})
    completed = subprocess.run(  # noqa: S603
        cmd,
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        **hidden_windows_subprocess_kwargs(),
    )
    raw = (completed.stdout or completed.stderr or "").strip()
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        payload = {"output": raw}
    if completed.returncode != 0:
        message = payload.get("error") if isinstance(payload, dict) else ""
        raise RuntimeError(message or raw or f"{command} failed with exit code {completed.returncode}")
    return payload if isinstance(payload, dict) else {"value": payload}


def _provider_presence(
    provider_ids: list[str] | None = None,
    session_secrets: dict[str, str] | None = None,
) -> dict[str, bool]:
    ids = provider_ids or list(PROVIDER_ENV)
    output: dict[str, bool] = {}
    minimax_oauth_file = Path.home() / ".minimax" / "oauth_creds.json"
    session_secrets = session_secrets or {}
    for provider_id in ids:
        env_names = PROVIDER_ENV.get(provider_id, (f"{provider_id.upper()}_API_KEY",))
        aliases = {provider_id}
        if provider_id == "openai-codex":
            aliases.add("openai")
        if provider_id == "minimax-cn":
            aliases.add("minimax")
        present = any(bool(os.environ.get(name)) for name in env_names) or any(
            bool(session_secrets.get(alias)) for alias in aliases
        )
        if provider_id == "minimax-portal":
            present = present or minimax_oauth_file.exists()
        output[provider_id] = present
    return output


def _openclaw_status() -> dict[str, Any]:
    command = shutil.which("openclaw")
    return {
        "connected": False,
        "gatewayUrl": os.environ.get("OPENCLAW_GATEWAY_URL", "ws://127.0.0.1:8765"),
        "lastError": None if command else "OpenClaw CLI was not found on PATH.",
        "lastEventAt": None,
        "lastConnectedAt": None,
        "reconnectAttempt": 0,
        "queuedOutbound": 0,
        "pendingAckCount": 0,
        "lastAckedMessageId": None,
    }


def _codex_import_snapshot() -> dict[str, Any]:
    candidates = [
        Path.home() / ".codex",
        Path(os.environ.get("CODEX_HOME", "")) if os.environ.get("CODEX_HOME") else None,
    ]
    existing = [str(path) for path in candidates if path and path.exists()]
    return {
        "available": bool(existing),
        "isRefreshing": False,
        "sources": existing,
        "sessions": [],
        "notes": (
            ["Codex local data was found for web backend inspection."]
            if existing
            else ["Codex local data is not visible to the web backend process."]
        ),
    }


class FluxioWebBackend:
    def __init__(self, root: Path, static_root: Path) -> None:
        self.root = root.resolve()
        self.static_root = static_root.resolve()
        self.provider_secrets: dict[str, str] = {}

    def _provider_env(self) -> dict[str, str]:
        env: dict[str, str] = {}
        if self.provider_secrets.get("openai"):
            env["OPENAI_API_KEY"] = self.provider_secrets["openai"]
        if self.provider_secrets.get("openai-codex"):
            env["OPENAI_API_KEY"] = self.provider_secrets["openai-codex"]
        if self.provider_secrets.get("anthropic"):
            env["ANTHROPIC_API_KEY"] = self.provider_secrets["anthropic"]
        if self.provider_secrets.get("openrouter"):
            env["OPENROUTER_API_KEY"] = self.provider_secrets["openrouter"]
        if self.provider_secrets.get("minimax"):
            env["MINIMAX_API_KEY"] = self.provider_secrets["minimax"]
        if self.provider_secrets.get("minimax-cn"):
            env["MINIMAX_API_KEY"] = self.provider_secrets["minimax-cn"]
        return env

    def _run_cli(self, root: Path, command: str, args: list[str], timeout: int = 180) -> dict[str, Any]:
        return _run_cli(root, command, args, timeout=timeout, extra_env=self._provider_env())

    def dispatch(self, command: str, raw_payload: object) -> object:
        payload = _as_payload(raw_payload)
        if command == "get_control_room_snapshot_command":
            root = Path(payload.get("root") or self.root).resolve()
            snapshot = self._run_cli(root, "control-room", [], timeout=180)
            snapshot["providerSecretPresence"] = _provider_presence(
                session_secrets=self.provider_secrets,
            )
            snapshot["webBackend"] = {
                "available": True,
                "commandSurface": "http",
                "root": str(root),
            }
            return snapshot
        if command == "inspect_codex_import_command":
            return _codex_import_snapshot()
        if command == "get_provider_secret_presence_command":
            ids = payload.get("providerIds") or payload.get("provider_ids")
            return _provider_presence(
                [str(item) for item in ids] if isinstance(ids, list) else None,
                session_secrets=self.provider_secrets,
            )
        if command in {"list_pending_approvals", "list_pending_questions"}:
            return []
        if command == "has_telegram_bot_token_command":
            return bool(os.environ.get("TELEGRAM_BOT_TOKEN"))
        if command == "get_openclaw_status":
            return _openclaw_status()
        if command == "has_openclaw_gateway_token":
            return bool(os.environ.get("OPENCLAW_GATEWAY_TOKEN"))
        if command == "open_external_url_command":
            url = str(payload.get("url") or "").strip()
            if not url.startswith(("http://", "https://")):
                raise RuntimeError("Only http(s) URLs can be opened from the web backend.")
            return bool(webbrowser.open(url))
        if command == "save_workspace_profile_command":
            args = [
                "--workspace-id",
                str(payload.get("workspaceId") or payload.get("workspace_id") or ""),
                "--name",
                str(payload.get("name") or ""),
                "--path",
                str(payload.get("path") or ""),
                "--default-runtime",
                str(payload.get("defaultRuntime") or payload.get("default_runtime") or "openclaw"),
                "--user-profile",
                str(payload.get("userProfile") or payload.get("user_profile") or "builder"),
                "--preferred-harness",
                str(payload.get("preferredHarness") or payload.get("preferred_harness") or "fluxio_hybrid"),
                "--routing-strategy",
                str(payload.get("routingStrategy") or payload.get("routing_strategy") or "profile_default"),
                "--route-overrides-json",
                json.dumps(payload.get("routeOverrides") or payload.get("route_overrides") or []),
                "--auto-optimize-routing",
                "true" if payload.get("autoOptimizeRouting") or payload.get("auto_optimize_routing") else "false",
                "--openai-codex-auth-mode",
                str(payload.get("openaiCodexAuthMode") or payload.get("openai_codex_auth_mode") or "none"),
                "--minimax-auth-mode",
                str(payload.get("minimaxAuthMode") or payload.get("minimax_auth_mode") or "none"),
                "--commit-message-style",
                str(payload.get("commitMessageStyle") or payload.get("commit_message_style") or "scoped"),
                "--execution-target-preference",
                str(payload.get("executionTargetPreference") or payload.get("execution_target_preference") or "profile_default"),
            ]
            return self._run_cli(self.root, "workspace-save", args, timeout=180)
        if command == "start_control_room_mission_command":
            args = [
                "--workspace-id",
                str(payload.get("workspaceId") or payload.get("workspace_id") or ""),
                "--runtime",
                str(payload.get("runtime") or "openclaw"),
                "--objective",
                str(payload.get("objective") or ""),
                "--mode",
                str(payload.get("mode") or "Autopilot"),
                "--budget-hours",
                str(payload.get("budgetHours") or payload.get("budget_hours") or 12),
            ]
            for check in payload.get("successChecks") or payload.get("success_checks") or []:
                args.extend(["--success-check", str(check)])
            for key, flag in (
                ("runUntil", "--run-until"),
                ("profile", "--profile"),
                ("escalationDestination", "--escalation-destination"),
                ("codeExecutionMemory", "--code-execution-memory"),
                ("codeExecutionContainerId", "--code-execution-container-id"),
            ):
                if payload.get(key):
                    args.extend([flag, str(payload[key])])
            if payload.get("codeExecution") or payload.get("code_execution"):
                args.append("--code-execution")
            if payload.get("codeExecutionRequired") or payload.get("code_execution_required"):
                args.append("--code-execution-required")
            return self._run_cli(self.root, "mission-start", args, timeout=300)
        if command == "apply_control_room_mission_action_command":
            args = [
                "--mission-id",
                str(payload.get("missionId") or payload.get("mission_id") or ""),
                "--action",
                str(payload.get("action") or ""),
            ]
            return self._run_cli(self.root, "mission-action", args, timeout=240)
        if command == "send_control_room_mission_follow_up_command":
            args = [
                "--mission-id",
                str(payload.get("missionId") or payload.get("mission_id") or ""),
                "--message",
                str(payload.get("message") or ""),
            ]
            return self._run_cli(self.root, "mission-follow-up", args, timeout=120)
        if command == "apply_control_room_workspace_action_command":
            args = [
                "--surface",
                str(payload.get("surface") or "setup"),
                "--action-id",
                str(payload.get("actionId") or payload.get("action_id") or ""),
            ]
            workspace_id = str(payload.get("workspaceId") or payload.get("workspace_id") or "").strip()
            if workspace_id:
                args.extend(["--workspace-id", workspace_id])
            if payload.get("approved"):
                args.append("--approved")
            return self._run_cli(self.root, "workspace-action", args, timeout=900)
        if command == "save_provider_secret_command":
            provider_id = str(payload.get("providerId") or payload.get("provider_id") or "").strip()
            secret = str(payload.get("secret") or "").strip()
            if not provider_id or not secret:
                raise RuntimeError("Provider id and secret are required.")
            self.provider_secrets[provider_id] = secret
            return True
        if command == "clear_provider_secret_command":
            provider_id = str(payload.get("providerId") or payload.get("provider_id") or "").strip()
            if provider_id:
                self.provider_secrets.pop(provider_id, None)
            return True
        if command in {
            "connect_openclaw_gateway",
            "disconnect_openclaw_gateway",
            "send_openclaw_message",
            "save_openclaw_gateway_token",
            "clear_openclaw_gateway_token",
            "start_openai_codex_oauth_command",
            "complete_openai_codex_oauth_command",
            "start_minimax_openclaw_auth_command",
            "save_telegram_bot_token_command",
            "clear_telegram_bot_token_command",
            "send_telegram_message_command",
        }:
            raise RuntimeError(
                f"{command} requires the desktop credential/gateway service. "
                "The web backend can read environment-backed auth state and run mission commands."
            )
        raise RuntimeError(f"Unsupported web backend command: {command}")

    def serve_file(self, handler: BaseHTTPRequestHandler) -> bool:
        parsed = urlparse(handler.path)
        raw_path = unquote(parsed.path.lstrip("/"))
        target = self.static_root / (raw_path or "index.html")
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            target = self.static_root / "index.html"
        try:
            target.resolve().relative_to(self.static_root)
        except ValueError:
            _json_response(handler, 403, {"error": "Forbidden"})
            return True
        if not target.exists():
            _json_response(handler, 404, {"error": "Build web/dist first or run Vite dev."})
            return True
        content_type = "text/html; charset=utf-8"
        if target.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"
        elif target.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif target.suffix == ".svg":
            content_type = "image/svg+xml"
        elif target.suffix == ".png":
            content_type = "image/png"
        body = target.read_bytes()
        handler.send_response(200)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        return True


def make_handler(backend: FluxioWebBackend) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_OPTIONS(self) -> None:  # noqa: N802
            _json_response(self, 204, {})

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                _json_response(self, 200, {"ok": True, "backend": "fluxio-web", "root": str(backend.root)})
                return
            backend.serve_file(self)

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/api/backend":
                _json_response(self, 404, {"ok": False, "error": "Unknown API route"})
                return
            try:
                payload = _read_json_body(self)
                command = str(payload.get("command") or "").strip()
                result = backend.dispatch(command, payload.get("payload"))
                _json_response(self, 200, {"ok": True, "data": result})
            except Exception as exc:  # pragma: no cover - exercised by browser/manual flows
                _json_response(self, 500, {"ok": False, "error": str(exc)})

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Fluxio web backend.")
    parser.add_argument("--host", default=os.environ.get("FLUXIO_WEB_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.environ.get("FLUXIO_WEB_PORT", DEFAULT_PORT)))
    parser.add_argument("--root", default=os.environ.get("FLUXIO_WORKSPACE_ROOT", str(DEFAULT_ROOT)))
    parser.add_argument("--static-root", default=os.environ.get("FLUXIO_STATIC_ROOT", str(DEFAULT_ROOT / "web" / "dist")))
    args = parser.parse_args(argv)

    backend = FluxioWebBackend(Path(args.root), Path(args.static_root))
    server = ThreadingHTTPServer((args.host, args.port), make_handler(backend))
    print(f"Fluxio web backend listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
