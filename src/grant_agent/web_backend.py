from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import shutil
import ssl
import subprocess
import sys
import webbrowser
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .subprocess_utils import hidden_windows_subprocess_kwargs

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 47880
DEFAULT_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_NAME = "Syntelos"
ADMIN_CONFIG_RELATIVE_PATH = ".agent_control/grand_agent_web_admin.json"
ADMIN_PASSWORD_RELATIVE_PATH = ".agent_control/grand_agent_admin_password.txt"
SESSION_COOKIE_NAME = "grand_agent_session"
ACCOUNT_ROLES = {"account", "operator", "admin"}
PASSWORD_ITERATIONS = 240_000
PROVIDER_ENV = {
    "openai": ("OPENAI_API_KEY",),
    "openai-codex": ("OPENAI_API_KEY", "FLUXIO_OPENAI_CODEX_OAUTH_PRESENT"),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "minimax": ("MINIMAX_API_KEY",),
    "minimax-cn": ("MINIMAX_API_KEY",),
    "minimax-portal": ("MINIMAX_OAUTH_TOKEN", "FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT"),
}


def _send_cors_headers(handler: BaseHTTPRequestHandler) -> None:
    origin = handler.headers.get("Origin")
    if origin:
        handler.send_header("Access-Control-Allow-Origin", origin)
        handler.send_header("Vary", "Origin")
    handler.send_header("Access-Control-Allow-Credentials", "true")
    handler.send_header("Access-Control-Allow-Headers", "content-type, authorization")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")


def _apply_security_headers(
    handler: BaseHTTPRequestHandler,
    *,
    cache_control: str = "no-store",
) -> None:
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("X-Frame-Options", "DENY")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("Cache-Control", cache_control)


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: object) -> None:
    body = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    _apply_security_headers(handler)
    _send_cors_headers(handler)
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


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _password_hash(password: str, salt: bytes, iterations: int = PASSWORD_ITERATIONS) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return base64.b64encode(digest).decode("ascii")


def _hash_record(password: str) -> dict[str, object]:
    salt = secrets.token_bytes(24)
    return {
        "algorithm": "pbkdf2_sha256",
        "iterations": PASSWORD_ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": _password_hash(password, salt),
    }


def _verify_password(password: str, record: dict[str, object]) -> bool:
    if not password or record.get("algorithm") != "pbkdf2_sha256":
        return False
    try:
        salt = base64.b64decode(str(record.get("salt") or ""))
        iterations = int(record.get("iterations") or PASSWORD_ITERATIONS)
    except (ValueError, TypeError):
        return False
    candidate = _password_hash(password, salt, iterations)
    return hmac.compare_digest(candidate, str(record.get("hash") or ""))


def _write_private_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _clean_username(username: str | None) -> str:
    cleaned = str(username or "").strip()
    if not cleaned:
        raise ValueError("Username is required.")
    if any(char.isspace() for char in cleaned):
        raise ValueError("Username cannot contain spaces.")
    return cleaned


def _default_display_name(username: str) -> str:
    return "Account" if username == "admin" else username


def _normalise_role(value: object) -> str:
    role = str(value or "").strip().lower()
    if role in {"owner", "member", "operator"}:
        return role
    return "account"


def _user_record(
    username: str,
    *,
    display_name: str | None = None,
    password: str,
    source: str,
    created_at: str | None = None,
) -> dict[str, object]:
    return {
        "username": username,
        "displayName": display_name or _default_display_name(username),
        "role": "account",
        "password": _hash_record(password),
        "source": source,
        "createdAt": created_at or _utc_now(),
    }


def _normalise_admin_payload(payload: dict[str, object]) -> dict[str, object]:
    users = payload.get("users")
    if isinstance(users, list) and users:
        clean_users = []
        for user in users:
            if not isinstance(user, dict) or not user.get("password"):
                continue
            next_user = dict(user)
            next_user["role"] = _normalise_role(next_user.get("role"))
            clean_users.append(next_user)
        if clean_users:
            primary = clean_users[0]
            next_payload = dict(payload)
            next_payload["users"] = clean_users
            next_payload["username"] = primary.get("username") or payload.get("username") or "admin"
            primary_username = str(primary.get("username") or payload.get("username") or "admin")
            next_payload["displayName"] = (
                primary.get("displayName") or payload.get("displayName") or _default_display_name(primary_username)
            )
            next_payload["role"] = _normalise_role(primary.get("role") or payload.get("role"))
            next_payload["password"] = primary.get("password")
            return next_payload
    if payload.get("password"):
        username = str(payload.get("username") or "admin")
        user = {
            "username": username,
            "displayName": payload.get("displayName") or _default_display_name(username),
            "role": _normalise_role(payload.get("role")),
            "password": payload.get("password"),
            "source": payload.get("source") or "local_config",
            "createdAt": payload.get("createdAt") or _utc_now(),
        }
        next_payload = dict(payload)
        next_payload["users"] = [user]
        next_payload["username"] = username
        next_payload["displayName"] = user["displayName"]
        next_payload["role"] = user["role"]
        return next_payload
    return payload


def _public_url(host: str, port: int, *, public_url: str | None = None, https: bool = False) -> str:
    configured = str(public_url or "").strip().rstrip("/")
    if configured:
        return configured
    scheme = "https" if https else "http"
    return f"{scheme}://127.0.0.1:{port}" if host in {"0.0.0.0", "::"} else f"{scheme}://{host}:{port}"


def _write_password_note(
    path: Path,
    entries: list[tuple[str, str]],
    *,
    title: str,
    url: str | None = None,
) -> None:
    lines = [
        title,
        f"URL: {url or _public_url(DEFAULT_HOST, DEFAULT_PORT)}",
        "",
    ]
    for username, password in entries:
        lines.extend(
            [
                f"Username: {username}",
                f"Password: {password}",
                "",
            ]
        )
    lines.append("This file is ignored by git. Delete it after storing the password.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def ensure_admin_config(
    root: Path,
    *,
    reset_password: bool = False,
    username: str | None = None,
    display_name: str | None = None,
    public_url: str | None = None,
) -> tuple[dict[str, object], str | None]:
    control_dir = root / ".agent_control"
    config_path = root / ADMIN_CONFIG_RELATIVE_PATH
    password_path = root / ADMIN_PASSWORD_RELATIVE_PATH
    env_password = os.environ.get("SYNTELOS_ACCOUNT_PASSWORD") or os.environ.get("GRAND_AGENT_ADMIN_PASSWORD")
    env_user = _clean_username(
        username
        or os.environ.get("SYNTELOS_ACCOUNT_USER")
        or os.environ.get("GRAND_AGENT_ADMIN_USER", "admin")
    )
    if env_password:
        user = _user_record(
            env_user,
            display_name=(
                display_name
                or os.environ.get("SYNTELOS_ACCOUNT_DISPLAY_NAME")
                or os.environ.get("GRAND_AGENT_ADMIN_DISPLAY_NAME")
                or _default_display_name(env_user)
            ),
            password=env_password,
            source="environment",
        )
        return (
            {
                "username": user["username"],
                "displayName": user["displayName"],
                "role": user["role"],
                "password": user["password"],
                "users": [user],
                "sessionSecret": (
                    os.environ.get("SYNTELOS_SESSION_SECRET")
                    or os.environ.get("GRAND_AGENT_SESSION_SECRET")
                    or secrets.token_urlsafe(48)
                ),
                "source": "environment",
                "createdAt": _utc_now(),
            },
            None,
        )

    if config_path.exists() and not reset_password:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and (payload.get("password") or payload.get("users")):
            normalised = _normalise_admin_payload(payload)
            if normalised != payload:
                _write_private_json(config_path, normalised)
            return normalised, None

    password = secrets.token_urlsafe(18)
    user = _user_record(
        env_user,
        display_name=display_name or os.environ.get("GRAND_AGENT_ADMIN_DISPLAY_NAME"),
        password=password,
        source="local_config",
    )
    payload: dict[str, object] = {
        "username": user["username"],
        "displayName": user["displayName"],
        "role": user["role"],
        "password": user["password"],
        "users": [user],
        "sessionSecret": secrets.token_urlsafe(48),
        "source": "local_config",
        "createdAt": _utc_now(),
    }
    _write_private_json(config_path, payload)
    control_dir.mkdir(parents=True, exist_ok=True)
    _write_password_note(
        password_path,
        [(str(user["username"]), password)],
        title=f"{PRODUCT_NAME} local account login",
        url=public_url,
    )
    return payload, password


def add_or_reset_admin_user(
    root: Path,
    *,
    username: str,
    display_name: str | None = None,
    public_url: str | None = None,
) -> tuple[dict[str, object], str, Path]:
    if os.environ.get("SYNTELOS_ACCOUNT_PASSWORD") or os.environ.get("GRAND_AGENT_ADMIN_PASSWORD"):
        raise RuntimeError("Cannot add local accounts while environment-controlled auth is active.")
    clean_username = _clean_username(username)
    config_path = root / ADMIN_CONFIG_RELATIVE_PATH
    payload, _ = ensure_admin_config(root)
    payload = _normalise_admin_payload(payload)
    users = [dict(user) for user in payload.get("users", []) if isinstance(user, dict)]
    password = secrets.token_urlsafe(18)
    next_user = _user_record(
        clean_username,
        display_name=display_name,
        password=password,
        source="local_config",
    )
    users = [user for user in users if user.get("username") != clean_username]
    users.append(next_user)
    payload["users"] = users
    payload = _normalise_admin_payload(payload)
    _write_private_json(config_path, payload)
    safe_username = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in clean_username)
    password_path = root / ".agent_control" / f"syntelos_{safe_username}_password.txt"
    _write_password_note(
        password_path,
        [(clean_username, password)],
        title=f"{PRODUCT_NAME} local account login",
        url=public_url,
    )
    return payload, password, password_path


def _run_cli(
    root: Path,
    command: str,
    args: list[str],
    timeout: int = 180,
    extra_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    cmd = [sys.executable, "-m", "grant_agent.cli", command, "--root", str(root), *args]
    env = os.environ.copy()
    src_path = root / "src"
    if src_path.exists():
        existing_pythonpath = str(env.get("PYTHONPATH", "")).strip()
        env["PYTHONPATH"] = (
            f"{src_path}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else str(src_path)
        )
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
    def __init__(
        self,
        root: Path,
        static_root: Path,
        *,
        reset_admin_password: bool = False,
        public_url: str | None = None,
    ) -> None:
        self.root = root.resolve()
        self.static_root = static_root.resolve()
        self.provider_secrets: dict[str, str] = {}
        self.admin_config, self.generated_admin_password = ensure_admin_config(
            self.root,
            reset_password=reset_admin_password,
            public_url=public_url,
        )
        self.public_url = public_url or ""
        self.secure_cookies = self.public_url.startswith("https://")
        self.sessions: dict[str, dict[str, str]] = {}

    @property
    def username(self) -> str:
        user = self.admin_users[0] if self.admin_users else {}
        return str(user.get("username") or self.admin_config.get("username") or "admin")

    @property
    def admin_users(self) -> list[dict[str, object]]:
        normalised = _normalise_admin_payload(self.admin_config)
        users = normalised.get("users")
        if isinstance(users, list):
            return [user for user in users if isinstance(user, dict) and user.get("password")]
        return []

    @property
    def role(self) -> str:
        return _normalise_role(self.admin_config.get("role"))

    def session_status(self, handler: BaseHTTPRequestHandler) -> dict[str, object]:
        session = self.authenticated_session(handler)
        authenticated = bool(session)
        return {
            "authenticated": authenticated,
            "user": (
                {
                    "username": session.get("username") or self.username,
                    "displayName": session.get("displayName") or self.admin_config.get("displayName") or "Account",
                    "role": session.get("role") or self.role,
                }
                if authenticated
                else None
            ),
            "loginRequired": True,
            "productName": PRODUCT_NAME,
        }

    def authenticated_session(self, handler: BaseHTTPRequestHandler) -> dict[str, str] | None:
        header = handler.headers.get("Cookie") or ""
        parsed = cookies.SimpleCookie()
        try:
            parsed.load(header)
        except cookies.CookieError:
            return None
        morsel = parsed.get(SESSION_COOKIE_NAME)
        if not morsel:
            return None
        token = morsel.value
        session = self.sessions.get(token)
        return session if session and session.get("role") in ACCOUNT_ROLES else None

    def is_authenticated(self, handler: BaseHTTPRequestHandler) -> bool:
        return bool(self.authenticated_session(handler))

    def login(self, payload: dict[str, Any]) -> str | None:
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")
        matched_user: dict[str, object] | None = None
        for user in self.admin_users:
            if username != str(user.get("username") or ""):
                continue
            record = user.get("password")
            if isinstance(record, dict) and _verify_password(password, record):
                matched_user = user
                break
        if not matched_user:
            return None
        token = secrets.token_urlsafe(32)
        self.sessions[token] = {
            "username": str(matched_user.get("username") or username),
            "displayName": str(matched_user.get("displayName") or username),
            "role": _normalise_role(matched_user.get("role")),
            "createdAt": _utc_now(),
        }
        return token

    def logout(self, handler: BaseHTTPRequestHandler) -> None:
        header = handler.headers.get("Cookie") or ""
        parsed = cookies.SimpleCookie()
        try:
            parsed.load(header)
        except cookies.CookieError:
            parsed = cookies.SimpleCookie()
        morsel = parsed.get(SESSION_COOKIE_NAME)
        if morsel:
            self.sessions.pop(morsel.value, None)
        self._clear_session_cookie(handler)

    def _set_session_cookie(self, handler: BaseHTTPRequestHandler, token: str) -> None:
        cookie = cookies.SimpleCookie()
        cookie[SESSION_COOKIE_NAME] = token
        cookie[SESSION_COOKIE_NAME]["path"] = "/"
        cookie[SESSION_COOKIE_NAME]["httponly"] = True
        cookie[SESSION_COOKIE_NAME]["samesite"] = "Lax"
        if self.secure_cookies or os.environ.get("GRAND_AGENT_COOKIE_SECURE") == "1":
            cookie[SESSION_COOKIE_NAME]["secure"] = True
        for value in cookie.values():
            handler.send_header("Set-Cookie", value.OutputString())

    def _clear_session_cookie(self, handler: BaseHTTPRequestHandler) -> None:
        handler.send_header(
            "Set-Cookie",
            f"{SESSION_COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"
            f"{'; Secure' if self.secure_cookies or os.environ.get('GRAND_AGENT_COOKIE_SECURE') == '1' else ''}",
        )

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
        _apply_security_headers(handler, cache_control="public, max-age=300")
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
                _json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "backend": "syntelos-web",
                        "loginRequired": True,
                    },
                )
                return
            if parsed.path == "/api/auth/status":
                _json_response(self, 200, {"ok": True, "data": backend.session_status(self)})
                return
            backend.serve_file(self)

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/api/auth/login":
                try:
                    payload = _read_json_body(self)
                    token = backend.login(payload)
                    if not token:
                        _json_response(
                            self,
                            401,
                            {
                                "ok": False,
                                "error": f"Invalid {PRODUCT_NAME} account username or password.",
                            },
                        )
                        return
                    session = backend.sessions.get(token, {})
                    self.send_response(200)
                    backend._set_session_cookie(self, token)
                    response_payload = {
                        "ok": True,
                        "data": {
                            "authenticated": True,
                            "user": {
                                "username": session.get("username") or backend.username,
                                "displayName": session.get("displayName") or backend.admin_config.get("displayName") or "Account",
                                "role": session.get("role") or backend.role,
                            },
                            "loginRequired": True,
                            "productName": PRODUCT_NAME,
                        },
                    }
                    body = json.dumps(response_payload, indent=2).encode("utf-8")
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    _apply_security_headers(self)
                    _send_cors_headers(self)
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as exc:
                    _json_response(self, 500, {"ok": False, "error": str(exc)})
                return
            if path == "/api/auth/logout":
                self.send_response(200)
                backend.logout(self)
                body = json.dumps({"ok": True, "data": {"authenticated": False}}).encode("utf-8")
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                _apply_security_headers(self)
                _send_cors_headers(self)
                self.end_headers()
                self.wfile.write(body)
                return
            if path != "/api/backend":
                _json_response(self, 404, {"ok": False, "error": "Unknown API route"})
                return
            if not backend.is_authenticated(self):
                _json_response(
                    self,
                    401,
                    {
                        "ok": False,
                        "error": f"{PRODUCT_NAME} login is required.",
                        "loginRequired": True,
                    },
                )
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
    parser = argparse.ArgumentParser(description=f"Run the {PRODUCT_NAME} web backend.")
    parser.add_argument("--host", default=os.environ.get("FLUXIO_WEB_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.environ.get("FLUXIO_WEB_PORT", DEFAULT_PORT)))
    parser.add_argument("--root", default=os.environ.get("FLUXIO_WORKSPACE_ROOT", str(DEFAULT_ROOT)))
    parser.add_argument("--static-root", default=os.environ.get("FLUXIO_STATIC_ROOT", str(DEFAULT_ROOT / "web" / "dist")))
    parser.add_argument(
        "--public-url",
        default=os.environ.get("FLUXIO_PUBLIC_URL", ""),
        help="Browser-facing URL to write into local account notes, usually the DSM HTTPS reverse-proxy URL.",
    )
    parser.add_argument(
        "--tls-cert-file",
        default=os.environ.get("FLUXIO_TLS_CERT_FILE", ""),
        help="Optional TLS certificate file for direct HTTPS serving.",
    )
    parser.add_argument(
        "--tls-key-file",
        default=os.environ.get("FLUXIO_TLS_KEY_FILE", ""),
        help="Optional TLS private key file for direct HTTPS serving.",
    )
    parser.add_argument(
        "--reset-admin-password",
        "--reset-account-password",
        action="store_true",
        dest="reset_admin_password",
        help="Generate a fresh local account password file under .agent_control.",
    )
    args = parser.parse_args(argv)

    backend = FluxioWebBackend(
        Path(args.root),
        Path(args.static_root),
        reset_admin_password=args.reset_admin_password,
        public_url=args.public_url or None,
    )
    server = ThreadingHTTPServer((args.host, args.port), make_handler(backend))
    tls_enabled = bool(args.tls_cert_file or args.tls_key_file)
    if tls_enabled:
        if not args.tls_cert_file or not args.tls_key_file:
            raise SystemExit("--tls-cert-file and --tls-key-file must be provided together.")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=args.tls_cert_file, keyfile=args.tls_key_file)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    password_path = backend.root / ADMIN_PASSWORD_RELATIVE_PATH
    if backend.generated_admin_password:
        print(
            f"{PRODUCT_NAME} account password generated at {password_path}",
            flush=True,
        )
    scheme = "https" if tls_enabled else "http"
    print(
        f"{PRODUCT_NAME} web backend listening on {scheme}://{args.host}:{args.port}",
        flush=True,
    )
    if args.public_url:
        print(f"{PRODUCT_NAME} public URL: {args.public_url.rstrip('/')}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
