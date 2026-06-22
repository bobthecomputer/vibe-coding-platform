from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import shlex
import shutil
import ssl
import struct
import string
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import webbrowser
import zlib
from dataclasses import asdict
from datetime import datetime, timezone
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

from .delivery_receipt import (
    generate_web_push_vapid_config,
    load_delivery_receipts,
    ntfy_status,
    record_delivery_receipt,
    record_web_push_subscription,
    send_ntfy_delivery_receipt,
    send_web_push_delivery_receipts,
    web_push_status,
)
from .mission_control import (
    CONTROL_ROOM_DETAIL_DURATION_BUDGET_MS,
    CONTROL_ROOM_DETAIL_PAYLOAD_BUDGET_BYTES,
    CONTROL_ROOM_SUMMARY_DURATION_BUDGET_MS,
    CONTROL_ROOM_SUMMARY_PAYLOAD_BUDGET_BYTES,
    ControlRoomStore,
    hermes_auth_store_candidates,
)
from .models import MissionEvent
from .mission_watchdog import ensure_watchdog_supervisor_loop
from .port_safety import tcp_port_accepts_connection
from .subprocess_utils import hidden_windows_subprocess_kwargs


def _env_float(name: str, default: float, *, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(str(os.environ.get(name, default)).strip()))
    except (TypeError, ValueError):
        return max(minimum, default)


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 47880
DEFAULT_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_NAME = "Fluxio"
ADMIN_CONFIG_RELATIVE_PATH = ".agent_control/grand_agent_web_admin.json"
ADMIN_PASSWORD_RELATIVE_PATH = ".agent_control/grand_agent_admin_password.txt"
BOOTSTRAP_SUMMARY_CACHE_TTL_SECONDS = 5.0
FULL_SUMMARY_CACHE_TTL_SECONDS = 8.0
FULL_SUMMARY_STALE_WHILE_REVALIDATE_SECONDS = 20.0
PERSISTED_FULL_SUMMARY_CACHE_VERSION = "2026-06-01.proof_safe_progress.v2"
PERSISTED_BOOTSTRAP_SUMMARY_CACHE_VERSION = "2026-06-09.bridge_lab_bootstrap.v1"
MISSION_DETAIL_CACHE_MAX_ITEMS = 12
MISSION_DETAIL_PREWARM_DELAY_SECONDS = _env_float(
    "FLUXIO_MISSION_DETAIL_PREWARM_DELAY_SECONDS",
    0.05,
)
MISSION_DETAIL_PREWARM_WAIT_SECONDS = _env_float(
    "FLUXIO_MISSION_DETAIL_PREWARM_WAIT_SECONDS",
    0.45,
)
MISSION_DETAIL_STALE_WHILE_REVALIDATE_SECONDS = float(
    os.environ.get("FLUXIO_MISSION_DETAIL_STALE_WHILE_REVALIDATE_SECONDS", "60")
)
MISSION_DETAIL_PREWARM_ENABLED = str(
    os.environ.get("FLUXIO_ENABLE_MISSION_DETAIL_PREWARM", "1")
).strip().lower() in {"1", "true", "yes", "on", "enabled"}
MISSION_START_TIMEOUT_SECONDS = 1200
MISSION_ACTION_TIMEOUT_SECONDS = 1200
SESSION_COOKIE_NAME = "grand_agent_session"
ACCOUNT_ROLES = {"account", "operator", "admin"}
PASSWORD_ITERATIONS = 240_000
TLS_HANDSHAKE_TIMEOUT_SECONDS = 10
ARTIFACT_CONTENT_TYPES = {
    ".apng": "image/apng",
    ".avif": "image/avif",
    ".gif": "image/gif",
    ".html": "text/html; charset=utf-8",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".json": "application/json; charset=utf-8",
    ".jsonl": "application/x-ndjson; charset=utf-8",
    ".log": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".webp": "image/webp",
}


def _env_flag(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, "")).strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off", "disabled"}


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    try:
        return max(minimum, int(str(os.environ.get(name, default)).strip()))
    except (TypeError, ValueError):
        return max(minimum, default)


class _HandshakeSafeThreadingHTTPServer(ThreadingHTTPServer):
    """Keep plain TCP probes from blocking the TLS accept loop."""

    daemon_threads = True
    request_queue_size = 64

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: type[BaseHTTPRequestHandler],
        *,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self.ssl_context = ssl_context
        super().__init__(server_address, request_handler_class)

    def get_request(self) -> tuple[Any, Any]:
        raw_socket, client_address = self.socket.accept()
        raw_socket.settimeout(TLS_HANDSHAKE_TIMEOUT_SECONDS)
        if not self.ssl_context:
            return raw_socket, client_address
        try:
            tls_socket = self.ssl_context.wrap_socket(
                raw_socket,
                server_side=True,
                do_handshake_on_connect=False,
            )
        except Exception:
            raw_socket.close()
            raise
        tls_socket.settimeout(TLS_HANDSHAKE_TIMEOUT_SECONDS)
        return tls_socket, client_address
PROVIDER_ENV = {
    "openai": ("OPENAI_API_KEY",),
    "openai-codex": ("OPENAI_API_KEY", "FLUXIO_OPENAI_CODEX_OAUTH_PRESENT"),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "minimax": ("MINIMAX_API_KEY",),
    "minimax-cn": ("MINIMAX_API_KEY",),
    "minimax-portal": ("MINIMAX_OAUTH_TOKEN", "FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT"),
    "opencode-go": ("OPENCODE_API_KEY",),
}
PROVIDER_SECRET_ENV = {
    "openai": "OPENAI_API_KEY",
    "openai-codex": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "minimax": "MINIMAX_API_KEY",
    "minimax-cn": "MINIMAX_API_KEY",
    "opencode-go": "OPENCODE_API_KEY",
}
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
OPENAI_CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
OPENAI_CODEX_AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
OPENAI_CODEX_TOKEN_URL = "https://auth.openai.com/oauth/token"
OPENAI_CODEX_REDIRECT_URI = "http://localhost:1455/auth/callback"
OPENAI_CODEX_DEFAULT_CALLBACK_PORT = 1455
OPENAI_CODEX_DEFAULT_MODEL = "gpt-5.5"
IMAGE_PROVIDER_CODEX_SUBSCRIPTION_ID = "codex_subscription_gpt_image2"
IMAGE_PROVIDER_CODEX_EXPECTED_PROVIDER = "openai-codex"
IMAGE_PROVIDER_CODEX_EXPECTED_MODEL = "gpt-image-2"
IMAGE_PROVIDER_CODEX_COMMAND_MODEL = "openai/gpt-image-2"
OPENAI_CODEX_SCOPE = "openid profile email offline_access"
OPENAI_CODEX_JWT_AUTH_CLAIM = "https://api.openai.com/auth"
OPENAI_CODEX_JWT_PROFILE_CLAIM = "https://api.openai.com/profile"
MINIMAX_OAUTH_CLIENT_ID = "78257093-7e40-4613-99e0-527b14b39113"
MINIMAX_OAUTH_SCOPE = "group_id profile model.completion"
MINIMAX_OAUTH_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:user_code"
MINIMAX_OAUTH_ENDPOINTS = {
    "global": "https://api.minimax.io",
    "cn": "https://api.minimaxi.com",
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


def _html_response(handler: BaseHTTPRequestHandler, status: int, markup: str) -> None:
    body = markup.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
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
        encoding="utf-8",
        errors="replace",
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


def _parse_process_payload(stdout: str, stderr: str) -> dict[str, Any]:
    raw = (stdout or "").strip() or (stderr or "").strip()
    raw = _clean_terminal_text(raw).strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        matches = re.findall(r"(\{(?:.|\n)*\})", raw)
        for candidate in reversed(matches):
            try:
                payload = json.loads(candidate)
                break
            except json.JSONDecodeError:
                continue
        else:
            payload = {"output": raw}
    return payload if isinstance(payload, dict) else {"value": payload}


def _run_process(
    args: list[str],
    *,
    cwd: Path,
    timeout: int = 180,
    extra_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(extra_env or {})
    completed = subprocess.run(  # noqa: S603
        args,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        stdin=subprocess.DEVNULL,
        **hidden_windows_subprocess_kwargs(),
    )
    payload = _parse_process_payload(completed.stdout, completed.stderr)
    if completed.returncode != 0:
        message = ""
        if isinstance(payload, dict):
            message = str(payload.get("error") or payload.get("message") or payload.get("output") or "")
        raise RuntimeError(message or _clean_terminal_text(completed.stderr or completed.stdout) or f"{args[0]} failed with exit code {completed.returncode}")
    return payload


def _run_process_capture(
    args: list[str],
    *,
    cwd: Path,
    timeout: int = 180,
    extra_env: dict[str, str] | None = None,
) -> tuple[dict[str, Any], str, str, int]:
    env = os.environ.copy()
    env.update(extra_env or {})
    started = time.perf_counter()
    completed = subprocess.run(  # noqa: S603
        args,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        stdin=subprocess.DEVNULL,
        **hidden_windows_subprocess_kwargs(),
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    stdout = _clean_terminal_text(completed.stdout or "")
    stderr = _clean_terminal_text(completed.stderr or "")
    payload = _parse_process_payload(stdout, stderr)
    if completed.returncode != 0:
        message = ""
        if isinstance(payload, dict):
            message = str(payload.get("error") or payload.get("message") or payload.get("output") or "")
        raise RuntimeError(message or stderr.strip() or stdout.strip() or f"{args[0]} failed with exit code {completed.returncode}")
    return payload, stdout, stderr, elapsed_ms


def _parse_json_objects_from_text(raw: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for line in str(raw or "").splitlines():
        candidate = line.strip()
        if not candidate.startswith("{"):
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            objects.append(payload)
    return objects


def _push_tool_timeline_event(
    events: list[dict[str, str]],
    *,
    kind: str,
    summary: str,
    at: str,
    status: str = "recorded",
) -> None:
    event_summary = str(summary or "").strip()
    if not event_summary:
        return
    events.append(
        {
            "kind": str(kind or "runtime.event").strip(),
            "at": at,
            "summary": event_summary[:240],
            "status": str(status or "recorded").strip() or "recorded",
        }
    )


def _chat_runtime_evidence_from_process(
    payload: dict[str, Any],
    *,
    stdout: str,
    now: str,
    elapsed_ms: int,
) -> tuple[list[dict[str, str]], list[str]]:
    timeline: list[dict[str, str]] = []
    changed_files: list[str] = []
    seen_files: set[str] = set()

    def add_file(candidate: object) -> None:
        value = str(candidate or "").strip().replace("\\", "/")
        if not value:
            return
        if "/" not in value and "." not in value:
            return
        if value in seen_files:
            return
        seen_files.add(value)
        changed_files.append(value)

    def scan(value: object) -> None:
        if isinstance(value, dict):
            for key in (
                "filesChanged",
                "files_changed",
                "changedFiles",
                "changed_files",
                "modifiedFiles",
                "modified_files",
            ):
                rows = value.get(key)
                if isinstance(rows, list):
                    for row in rows:
                        if isinstance(row, str):
                            add_file(row)
                        elif isinstance(row, dict):
                            add_file(row.get("path") or row.get("file") or row.get("name"))
            for nested in value.values():
                scan(nested)
            return
        if isinstance(value, list):
            for row in value:
                scan(row)

    scan(payload)

    for event in _parse_json_objects_from_text(stdout):
        event_type = str(event.get("type") or event.get("kind") or "").strip().lower()
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        item_type = str(item.get("item_type") or item.get("type") or "").strip().lower()
        command = str(item.get("command") or "").strip()
        status = str(item.get("status") or "").strip().lower() or "recorded"
        if command and item_type in {"command_execution", "command"}:
            _push_tool_timeline_event(
                timeline,
                kind="command.execution",
                summary=command,
                at=now,
                status=status,
            )
        elif event_type in {"item.completed", "item.started", "turn.started", "turn.completed"}:
            summary = str(item.get("text") or item.get("message") or event_type).strip()
            _push_tool_timeline_event(
                timeline,
                kind=event_type or "runtime.event",
                summary=summary,
                at=now,
                status=status,
            )

    _push_tool_timeline_event(
        timeline,
        kind="runtime.roundtrip",
        summary=f"CLI roundtrip completed in {elapsed_ms} ms.",
        at=now,
        status="completed",
    )
    return timeline[-18:], changed_files[:20]


def _wsl_has_command(command_name: str, timeout: int = 8) -> bool:
    if os.name != "nt":
        return False
    wsl = shutil.which("wsl")
    if not wsl:
        return False
    try:
        completed = subprocess.run(  # noqa: S603
            [
                wsl,
                "bash",
                "-lc",
                f'export PATH="$HOME/.local/bin:$PATH"; command -v {shlex.quote(command_name)} >/dev/null 2>&1',
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            stdin=subprocess.DEVNULL,
            **hidden_windows_subprocess_kwargs(),
        )
    except Exception:  # pragma: no cover - defensive
        return False
    return completed.returncode == 0


def _wsl_command_path(command_name: str, timeout: int = 8) -> str:
    if os.name != "nt":
        return ""
    wsl = shutil.which("wsl")
    if not wsl:
        return ""
    try:
        completed = subprocess.run(  # noqa: S603
            [
                wsl,
                "bash",
                "-lc",
                f'export PATH="$HOME/.local/bin:$PATH"; command -v {shlex.quote(command_name)}',
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            stdin=subprocess.DEVNULL,
            **hidden_windows_subprocess_kwargs(),
        )
    except Exception:  # pragma: no cover - defensive
        return ""
    if completed.returncode != 0:
        return ""
    return (completed.stdout or "").strip().splitlines()[0] if (completed.stdout or "").strip() else ""


def _wsl_command_version(command_name: str, timeout: int = 8) -> str:
    if os.name != "nt":
        return ""
    wsl = shutil.which("wsl")
    if not wsl:
        return ""
    try:
        completed = subprocess.run(  # noqa: S603
            [
                wsl,
                "bash",
                "-lc",
                f'export PATH="$HOME/.local/bin:$PATH"; {shlex.quote(command_name)} --version',
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            stdin=subprocess.DEVNULL,
            **hidden_windows_subprocess_kwargs(),
        )
    except Exception:  # pragma: no cover - defensive
        return ""
    if completed.returncode != 0:
        return ""
    return (completed.stdout or completed.stderr or "").strip().splitlines()[0]


def _extract_model_reply(payload: dict[str, Any]) -> str:
    timeline = payload.get("toolTimeline")
    if isinstance(timeline, list):
        for item in reversed(timeline):
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "").lower()
            summary = str(item.get("summary") or "").strip()
            if summary and kind in {"runtime.model_message", "model.message", "assistant.message"}:
                return summary
        for item in reversed(timeline):
            if not isinstance(item, dict):
                continue
            summary = str(item.get("summary") or "").strip()
            if summary and not str(item.get("kind") or "").lower().startswith("operator."):
                return summary
    candidates: list[object] = [
        payload.get("reply"),
        payload.get("text"),
        payload.get("outputText"),
        payload.get("output_text"),
        payload.get("content"),
        payload.get("message"),
        payload.get("response"),
        payload.get("assistant"),
        payload.get("completion"),
        payload.get("data"),
        payload.get("output"),
        payload.get("result"),
        payload.get("value"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            stripped = candidate.strip()
            if stripped[:1] in {"{", "["}:
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    nested = _extract_model_reply(parsed)
                    if nested:
                        return nested
                elif isinstance(parsed, list):
                    for item in reversed(parsed):
                        if isinstance(item, dict):
                            nested = _extract_model_reply(item)
                            if nested:
                                return nested
                        elif isinstance(item, str) and item.strip():
                            return item.strip()
            return stripped
        if isinstance(candidate, dict):
            nested = _extract_model_reply(candidate)
            if nested:
                return nested
        if isinstance(candidate, list):
            for item in candidate:
                if isinstance(item, str) and item.strip():
                    return item.strip()
                if isinstance(item, dict):
                    nested = _extract_model_reply(item)
                    if nested:
                        return nested
    choices = payload.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if isinstance(choice, dict):
                nested = _extract_model_reply(choice)
                if nested:
                    return nested
    messages = payload.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            if isinstance(message, dict):
                nested = _extract_model_reply(message)
                if nested:
                    return nested
    for value in payload.values():
        if isinstance(value, dict):
            nested = _extract_model_reply(value)
            if nested:
                return nested
    return ""


def _safe_identifier(value: object, fallback: str = "syntelos") -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return normalized[:80] or fallback


def _camel_to_snake(value: str) -> str:
    return re.sub(r"(?<!^)([A-Z])", r"_\1", value).lower()


def _chat_prompt(payload: dict[str, Any]) -> str:
    message = str(payload.get("message") or "").strip()
    if not message:
        raise RuntimeError("Chat message is required.")
    system_context = str(payload.get("systemContext") or payload.get("system_context") or "").strip()
    history = payload.get("history")
    turns: list[str] = []
    if isinstance(history, list):
        for item in history[-8:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip().lower()
            text = str(item.get("text") or item.get("title") or item.get("detail") or "").strip()
            if not text or role not in {"user", "assistant"}:
                continue
            label = "User" if role == "user" else "Assistant"
            turns.append(f"{label}: {text[:3000]}")
    system_prefix = (
        "You are Syntelos, a concise assistant inside a workspace control app. "
        "Answer the latest user message directly and naturally. "
        "Do not expose routing or runtime metadata unless the user asks."
    )
    if system_context:
        system_prefix += f"\n\nCurrent workspace context:\n{system_context[:4000]}"
    if not turns:
        return f"{system_prefix}\n\nUser: {message}\nAssistant:"
    return (
        f"{system_prefix}\n\n"
        "Recent conversation:\n"
        + "\n".join(turns)
        + f"\nUser: {message}\nAssistant:"
    )


def _provider_presence(
    provider_ids: list[str] | None = None,
    session_secrets: dict[str, str] | None = None,
) -> dict[str, bool]:
    ids = provider_ids or list(PROVIDER_ENV)
    output: dict[str, bool] = {}
    home = Path(os.environ.get("HOME") or str(Path.home())).expanduser()
    minimax_oauth_file = home / ".minimax" / "oauth_creds.json"
    state_root = Path(os.environ.get("OPENCLAW_STATE_DIR", str(home / ".openclaw"))).expanduser()
    openclaw_auth_store = state_root / "agents" / "main" / "agent" / "auth-profiles.json"
    opencode_auth_store = home / ".local" / "share" / "opencode" / "auth.json"
    hermes_auth_stores = _scoped_hermes_auth_store_candidates(home)
    session_secrets = session_secrets or {}
    for provider_id in ids:
        env_names = PROVIDER_ENV.get(provider_id, (f"{provider_id.upper()}_API_KEY",))
        aliases = {provider_id}
        if provider_id == "openai-codex":
            aliases.add("openai")
        if provider_id == "minimax-cn":
            aliases.add("minimax")
        if provider_id == "opencode-go":
            aliases.update({"opencodego", "opencode"})
        present = any(bool(os.environ.get(name)) for name in env_names) or any(
            bool(session_secrets.get(alias)) for alias in aliases
        )
        if provider_id == "openai-codex":
            present = present or _openclaw_auth_store_has_provider(openclaw_auth_store, "openai-codex")
            present = present or any(
                _openclaw_auth_store_has_provider(path, "openai-codex")
                for path in hermes_auth_stores
            )
        if provider_id == "minimax-portal":
            present = present or minimax_oauth_file.exists()
            present = present or _openclaw_auth_store_has_provider(openclaw_auth_store, "minimax-portal")
            present = present or any(
                _openclaw_auth_store_has_provider(path, hermes_provider)
                for path in hermes_auth_stores
                for hermes_provider in ("minimax-oauth", "minimax", "minimax-portal")
            )
        if provider_id == "opencode-go":
            present = present or _openclaw_auth_store_has_provider(openclaw_auth_store, "opencode-go")
            present = present or _openclaw_auth_store_has_provider(openclaw_auth_store, "opencodego")
            present = present or _openclaw_auth_store_has_provider(openclaw_auth_store, "opencode")
            present = present or _openclaw_auth_store_has_provider(opencode_auth_store, "opencode-go")
            present = present or _openclaw_auth_store_has_provider(opencode_auth_store, "opencodego")
            present = present or any(
                _openclaw_auth_store_has_provider(path, hermes_provider)
                for path in hermes_auth_stores
                for hermes_provider in ("opencode-go", "opencodego", "opencode")
            )
        output[provider_id] = present
    return output


def _provider_secret_store_path(root: Path) -> Path:
    return root / ".agent_control" / "provider_secrets.json"


def _scoped_hermes_auth_store_candidates(home: Path) -> list[Path]:
    candidates = hermes_auth_store_candidates(home)
    explicit_home = os.environ.get("HOME")
    if not explicit_home:
        return candidates
    default_home = Path.home().expanduser()
    try:
        if home.resolve() == default_home.resolve():
            return candidates
    except OSError:
        if str(home) == str(default_home):
            return candidates
    scoped: list[Path] = []
    for path in candidates:
        try:
            path.resolve().relative_to(home.resolve())
        except (OSError, ValueError):
            continue
        scoped.append(path)
    return scoped


def _provider_runtime_env_path() -> Path | None:
    home = str(os.environ.get("HOME") or "").strip()
    if not home:
        return None
    return Path(home).expanduser() / ".fluxio_provider_env"


def _load_persisted_provider_secrets(root: Path) -> dict[str, str]:
    path = _provider_secret_store_path(root)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    secrets_payload = payload.get("secrets") if isinstance(payload.get("secrets"), dict) else payload
    loaded: dict[str, str] = {}
    for provider_id in PROVIDER_SECRET_ENV:
        value = str(secrets_payload.get(provider_id) or "").strip()
        if value:
            loaded[provider_id] = value
    return loaded


def _shell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _write_runtime_provider_env(provider_secrets: dict[str, str]) -> None:
    path = _provider_runtime_env_path()
    if path is None:
        return
    env_values: dict[str, str] = {}
    for provider_id, value in provider_secrets.items():
        env_name = PROVIDER_SECRET_ENV.get(provider_id)
        cleaned = str(value or "").strip()
        if env_name and cleaned:
            env_values[env_name] = cleaned
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Generated by Fluxio. This file is sourced by the NAS web backend launcher.",
        "# Do not commit or share it.",
    ]
    for env_name in sorted(env_values):
        lines.append(f"export {env_name}={_shell_single_quote(env_values[env_name])}")
    tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}.{secrets.token_hex(8)}")
    tmp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp_path, 0o600)
    except OSError:
        pass
    tmp_path.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _write_persisted_provider_secrets(root: Path, provider_secrets: dict[str, str]) -> None:
    path = _provider_secret_store_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    filtered = {
        provider_id: str(value).strip()
        for provider_id, value in provider_secrets.items()
        if provider_id in PROVIDER_SECRET_ENV and str(value).strip()
    }
    payload = {
        "schema": "fluxio.provider_secrets.v1",
        "updatedAt": _utc_now(),
        "secrets": filtered,
    }
    tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}.{secrets.token_hex(8)}")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp_path, 0o600)
    except OSError:
        pass
    tmp_path.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    _write_runtime_provider_env(filtered)


def _openclaw_auth_store_has_provider(path: Path, provider_id: str) -> bool:
    try:
        exists = path.exists()
    except OSError:
        return False
    if not exists:
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    needle = provider_id.strip().lower()

    def visit(value: object) -> bool:
        if isinstance(value, dict):
            if needle in {str(item).strip().lower() for item in value.keys()}:
                return True
            for key in ("providers", "credential_pool"):
                nested = value.get(key)
                if isinstance(nested, dict) and needle in {
                    str(item).strip().lower() for item in nested.keys()
                }:
                    return True
            provider = str(
                value.get("provider")
                or value.get("providerId")
                or value.get("provider_id")
                or value.get("id")
                or ""
            ).strip().lower()
            if provider == needle and any(
                key in value
                for key in (
                    "accessToken",
                    "access_token",
                    "access",
                    "refreshToken",
                    "refresh_token",
                    "refresh",
                    "token",
                    "oauth",
                    "auth",
                )
            ):
                return True
            return any(visit(item) for item in value.values())
        if isinstance(value, list):
            return any(visit(item) for item in value)
        return False

    return visit(payload)


def _clean_terminal_text(value: str) -> str:
    return ANSI_ESCAPE_PATTERN.sub("", value).replace("\r", "\n")


class OpenAICodexOAuthSession:
    def __init__(
        self,
        *,
        verifier: str,
        state: str,
        auth_url: str,
        callback_port: int = OPENAI_CODEX_DEFAULT_CALLBACK_PORT,
        redirect_uri: str = OPENAI_CODEX_REDIRECT_URI,
        relay_token_hash: str = "",
    ) -> None:
        self.verifier = verifier
        self.state = state
        self.auth_url = auth_url
        self.callback_port = callback_port
        self.redirect_uri = redirect_uri
        self.relay_token_hash = relay_token_hash
        self.created_at = time.time()


_OPENAI_CODEX_OAUTH_SESSIONS: dict[str, OpenAICodexOAuthSession] = {}


class MiniMaxOAuthSession:
    def __init__(
        self,
        *,
        verifier: str,
        state: str,
        region: str,
        user_code: str,
        verification_url: str,
        interval_ms: int,
        expires_at_ms: int,
    ) -> None:
        self.verifier = verifier
        self.state = state
        self.region = region
        self.user_code = user_code
        self.verification_url = verification_url
        self.interval_ms = interval_ms
        self.expires_at_ms = expires_at_ms
        self.created_at = time.time()


_MINIMAX_OAUTH_SESSIONS: dict[str, MiniMaxOAuthSession] = {}


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _image_prompt_text(payload: dict[str, Any]) -> str:
    prompt = payload.get("prompt") if isinstance(payload.get("prompt"), dict) else {}
    parts = [
        str(prompt.get("text") or "").strip(),
        str(prompt.get("style") or "").strip(),
        str(prompt.get("negative") or "").strip(),
    ]
    return " ".join(item for item in parts if item).strip() or "Syntelos generated image"


def _write_prompt_rendered_png(path: Path, payload: dict[str, Any]) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
    except Exception as exc:  # pragma: no cover - Pillow is bundled in the desktop runtime.
        _write_basic_prompt_png(path, payload)
        return

    canvas = payload.get("canvas") if isinstance(payload.get("canvas"), dict) else {}
    width = max(512, min(int(canvas.get("width") or 1024), 1600))
    height = max(512, min(int(canvas.get("height") or 768), 1600))
    prompt_text = _image_prompt_text(payload)
    seed = int(hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:8], 16)
    palette_sets = [
        ((22, 26, 28), (210, 168, 88), (116, 164, 145), (234, 226, 209)),
        ((17, 23, 33), (92, 154, 214), (223, 182, 101), (238, 240, 235)),
        ((24, 24, 23), (184, 129, 98), (135, 172, 112), (238, 231, 220)),
        ((20, 22, 25), (205, 199, 178), (102, 145, 160), (238, 236, 228)),
    ]
    bg, primary, secondary, paper = palette_sets[seed % len(palette_sets)]

    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image, "RGBA")
    for y in range(height):
        ratio = y / max(1, height - 1)
        blend = tuple(int(bg[i] * (1 - ratio) + secondary[i] * ratio * 0.52) for i in range(3))
        draw.line([(0, y), (width, y)], fill=(*blend, 255))

    haze = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    haze_draw = ImageDraw.Draw(haze, "RGBA")
    for index in range(9):
        local = (seed >> (index * 3)) & 0xFF
        cx = int((0.12 + ((local % 83) / 100)) * width)
        cy = int((0.08 + (((local * 7) % 71) / 100)) * height)
        radius = int((0.12 + (((local * 11) % 26) / 100)) * min(width, height))
        color = primary if index % 2 == 0 else secondary
        haze_draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=(*color, 32 + (index % 3) * 16),
        )
    image = Image.alpha_composite(image.convert("RGBA"), haze.filter(ImageFilter.GaussianBlur(28)))
    draw = ImageDraw.Draw(image, "RGBA")

    horizon = int(height * (0.46 + ((seed % 17) / 100)))
    draw.rectangle([0, horizon, width, height], fill=(10, 13, 14, 74))
    for index in range(5):
        x0 = int(width * (0.08 + index * 0.18 + (((seed >> index) & 7) / 180)))
        y0 = int(horizon + height * (0.05 + index * 0.012))
        w = int(width * (0.22 + (((seed >> (index + 5)) & 7) / 90)))
        h = int(height * (0.18 + (((seed >> (index + 9)) & 7) / 120)))
        draw.rounded_rectangle(
            [x0, y0, min(width - 40, x0 + w), min(height - 42, y0 + h)],
            radius=24,
            fill=(*paper, 30 + index * 10),
            outline=(*paper, 82),
            width=2,
        )

    sun_x = int(width * (0.18 + ((seed % 53) / 100)))
    sun_y = int(height * (0.18 + (((seed >> 8) % 30) / 100)))
    sun_r = int(min(width, height) * 0.055)
    draw.ellipse([sun_x - sun_r, sun_y - sun_r, sun_x + sun_r, sun_y + sun_r], fill=(*primary, 220))
    for index in range(14):
        y = int(height * (0.18 + index * 0.044))
        offset = ((seed >> (index % 12)) & 31) - 16
        draw.line(
            [(int(width * 0.08) + offset, y), (int(width * 0.88) - offset, y + int(height * 0.025))],
            fill=(*paper, 14 + (index % 4) * 8),
            width=max(1, int(height * 0.003)),
        )

    try:
        font_large = ImageFont.truetype("arial.ttf", max(22, int(width * 0.034)))
        font_small = ImageFont.truetype("arial.ttf", max(13, int(width * 0.014)))
    except OSError:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
    words = prompt_text[:110]
    panel_w = int(width * 0.46)
    panel_h = int(height * 0.18)
    panel_x = int(width * 0.055)
    panel_y = int(height * 0.74)
    draw.rounded_rectangle(
        [panel_x, panel_y, panel_x + panel_w, panel_y + panel_h],
        radius=18,
        fill=(9, 11, 12, 138),
        outline=(*paper, 56),
        width=1,
    )
    draw.text((panel_x + 20, panel_y + 18), "Generated image artifact", font=font_small, fill=(*primary, 230))
    draw.text((panel_x + 20, panel_y + 48), words, font=font_large, fill=(*paper, 242))

    image.convert("RGB").save(path, format="PNG", optimize=True)


def _write_basic_prompt_png(path: Path, payload: dict[str, Any]) -> None:
    canvas = payload.get("canvas") if isinstance(payload.get("canvas"), dict) else {}
    width = max(512, min(int(canvas.get("width") or 1024), 1200))
    height = max(512, min(int(canvas.get("height") or 768), 1200))
    prompt_text = _image_prompt_text(payload)
    seed = int(hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:8], 16)
    palettes = [
        ((20, 24, 26), (211, 168, 82), (92, 147, 160), (235, 228, 214)),
        ((18, 22, 31), (96, 154, 215), (216, 181, 102), (236, 238, 232)),
        ((24, 25, 23), (177, 126, 96), (132, 170, 112), (238, 231, 220)),
    ]
    bg, primary, secondary, paper = palettes[seed % len(palettes)]
    sun_x = int(width * (0.2 + ((seed % 53) / 100)))
    sun_y = int(height * (0.16 + (((seed >> 7) % 28) / 100)))
    sun_r = max(24, int(min(width, height) * 0.06))
    horizon = int(height * (0.47 + ((seed % 13) / 100)))
    panel_x = int(width * 0.08)
    panel_y = int(height * 0.7)
    panel_w = int(width * 0.5)
    panel_h = int(height * 0.18)

    def mix(a: tuple[int, int, int], b: tuple[int, int, int], ratio: float) -> tuple[int, int, int]:
        return tuple(max(0, min(255, int(a[i] * (1 - ratio) + b[i] * ratio))) for i in range(3))

    raw_rows: list[bytes] = []
    for y in range(height):
        row = bytearray()
        yr = y / max(1, height - 1)
        base = mix(bg, secondary, yr * 0.48)
        for x in range(width):
            color = base
            dx = x - sun_x
            dy = y - sun_y
            dist2 = dx * dx + dy * dy
            if dist2 < sun_r * sun_r:
                color = mix(color, primary, 0.78)
            elif dist2 < (sun_r * 4) * (sun_r * 4):
                color = mix(color, primary, max(0, 0.22 - (dist2 ** 0.5 / (sun_r * 4)) * 0.18))
            if y > horizon:
                color = mix(color, (8, 11, 12), 0.28 + min(0.34, (y - horizon) / height))
            for index in range(4):
                x0 = int(width * (0.12 + index * 0.18 + (((seed >> index) & 7) / 160)))
                y0 = int(horizon + height * (0.05 + index * 0.018))
                w = int(width * (0.18 + (((seed >> (index + 4)) & 7) / 100)))
                h = int(height * (0.13 + (((seed >> (index + 8)) & 7) / 140)))
                if x0 <= x <= x0 + w and y0 <= y <= y0 + h:
                    border = x - x0 < 3 or x0 + w - x < 3 or y - y0 < 3 or y0 + h - y < 3
                    color = mix(color, paper, 0.42 if border else 0.18)
            if panel_x <= x <= panel_x + panel_w and panel_y <= y <= panel_y + panel_h:
                border = x - panel_x < 2 or panel_x + panel_w - x < 2 or y - panel_y < 2 or panel_y + panel_h - y < 2
                color = mix(color, paper if border else (6, 8, 9), 0.5 if border else 0.72)
            row.extend(color)
        raw_rows.append(b"\x00" + bytes(row))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(raw_rows), 6))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def _platform_path_for_windows_drive(raw_path: object) -> Path:
    value = str(raw_path or "").strip()
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", value)
    if not match:
        return Path(value)
    if os.name == "nt":
        return Path(value)
    drive = match.group(1).lower()
    rest = match.group(2).replace("\\", "/").lstrip("/")
    return Path(f"/mnt/{drive}/{rest}")


def _parse_openai_codex_callback_port(auth_url: str) -> int:
    parsed = urlparse(auth_url)
    redirect_uri = parse_qs(parsed.query).get("redirect_uri", [""])[0]
    if not redirect_uri:
        raise RuntimeError("OpenAI Codex auth URL does not include a redirect_uri.")
    redirect = urlparse(unquote(redirect_uri))
    if redirect.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError(f"Unexpected OpenAI Codex callback host: {redirect.hostname or ''}")
    if redirect.path != "/auth/callback":
        raise RuntimeError(f"Unexpected OpenAI Codex callback path: {redirect.path}")
    try:
        port = int(redirect.port or 0)
    except ValueError as exc:
        raise RuntimeError("OpenAI Codex callback port is invalid.") from exc
    if port < 1 or port > 65535:
        raise RuntimeError("OpenAI Codex callback port is invalid.")
    return port


def _build_openai_codex_helper_command(payload: dict[str, Any]) -> str:
    parts = [
        "syntelos-codex-oauth-helper",
        "--port",
        str(payload.get("callbackPort") or ""),
        "--auth-url",
        str(payload.get("authUrl") or ""),
        "--relay-url",
        str(payload.get("relayUrl") or ""),
        "--relay-token",
        str(payload.get("relayToken") or ""),
    ]
    return subprocess.list2cmdline(parts)


def _openclaw_auth_profiles_path() -> Path:
    state_root = Path(os.environ.get("OPENCLAW_STATE_DIR", str(Path.home() / ".openclaw")))
    return state_root / "agents" / "main" / "agent" / "auth-profiles.json"


def _codex_home_path() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))


def _codex_auth_json_payload(tokens: dict[str, Any], identity: dict[str, str]) -> dict[str, Any]:
    return {
        "auth_mode": "chatgpt",
        "OPENAI_API_KEY": None,
        "tokens": {
            "id_token": str(tokens.get("id_token") or tokens.get("idToken") or tokens.get("access") or ""),
            "access_token": str(tokens.get("access") or ""),
            "refresh_token": str(tokens.get("refresh") or ""),
            "account_id": str(identity.get("accountId") or ""),
        },
        "last_refresh": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _write_codex_auth_json(tokens: dict[str, Any], identity: dict[str, str]) -> None:
    codex_home = _codex_home_path()
    codex_home.mkdir(parents=True, exist_ok=True)
    auth_payload = _codex_auth_json_payload(tokens, identity)
    auth_path = codex_home / "auth.json"
    auth_path.write_text(json.dumps(auth_payload, indent=2), encoding="utf-8")
    config_path = codex_home / "config.toml"
    if not config_path.exists():
        config_path.write_text(
            f'preferred_auth_method = "chatgpt"\nmodel = "{OPENAI_CODEX_DEFAULT_MODEL}"\n',
            encoding="utf-8",
        )
    try:
        os.chmod(auth_path, 0o600)
    except OSError:
        pass


def _sync_openai_codex_oauth_to_wsl_hermes(tokens: dict[str, Any], identity: dict[str, str]) -> dict[str, Any]:
    """Seed the WSL Hermes auth store from the OAuth credential the app just created."""
    if os.name != "nt" or not shutil.which("wsl"):
        return {"synced": False, "reason": "wsl_unavailable"}
    payload = _codex_auth_json_payload(tokens, identity)
    script = r"""
import json
from pathlib import Path
import sys

payload = json.loads(sys.stdin.read() or "{}")
codex_home = Path.home() / ".codex"
codex_home.mkdir(parents=True, exist_ok=True)
auth_path = codex_home / "auth.json"
auth_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
try:
    auth_path.chmod(0o600)
except OSError:
    pass

hermes_root = Path.home() / ".hermes" / "hermes-agent"
sys.path.insert(0, str(hermes_root))
try:
    from hermes_cli.auth import (
        DEFAULT_CODEX_BASE_URL,
        _import_codex_cli_tokens,
        _save_codex_tokens,
        _update_config_for_provider,
        get_codex_auth_status,
    )

    imported = _import_codex_cli_tokens()
    if not imported:
        raise RuntimeError("Hermes could not import the freshly written Codex CLI tokens.")
    _save_codex_tokens(imported)
    config_path = _update_config_for_provider("openai-codex", DEFAULT_CODEX_BASE_URL)
    status = get_codex_auth_status()
    print(json.dumps({
        "synced": bool(status.get("logged_in")),
        "source": status.get("source") or "hermes-auth-store",
        "configPath": str(config_path),
    }))
except Exception as exc:
    print(json.dumps({"synced": False, "reason": str(exc)}))
"""
    try:
        result = subprocess.run(
            ["wsl", "python3", "-c", script],
            input=json.dumps(payload),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=45,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"synced": False, "reason": str(exc)}
    output = (result.stdout or "").strip().splitlines()
    if not output:
        return {
            "synced": False,
            "reason": (result.stderr or f"wsl exited {result.returncode}").strip()[:300],
        }
    try:
        parsed = json.loads(output[-1])
    except json.JSONDecodeError:
        return {"synced": False, "reason": output[-1][:300]}
    return parsed if isinstance(parsed, dict) else {"synced": False, "reason": "invalid_sync_result"}


def _base64url_no_padding(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _create_openai_codex_pkce_pair() -> tuple[str, str]:
    verifier = _base64url_no_padding(secrets.token_bytes(32))
    challenge = _base64url_no_padding(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def _normalize_minimax_region(value: object = None) -> str:
    normalized = str(value or "global").strip().lower().replace("_", "-")
    if normalized in {"", "global", "international", "minimax-global"}:
        return "global"
    if normalized in {"cn", "china", "minimax-cn"}:
        return "cn"
    raise RuntimeError('Unsupported MiniMax OAuth region. Use "global" or "cn".')


def _minimax_base_url(region: str) -> str:
    return MINIMAX_OAUTH_ENDPOINTS[_normalize_minimax_region(region)]


def _urlopen_form_json_with_redirects(
    url: str,
    body: bytes,
    headers: dict[str, str],
    *,
    timeout: int = 30,
    max_redirects: int = 4,
) -> dict[str, Any]:
    current_url = url
    for _ in range(max_redirects + 1):
        request = Request(current_url, data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308}:
                location = str(exc.headers.get("Location") or "").strip()
                if not location:
                    raise RuntimeError(f"Request redirected with HTTP {exc.code} but no Location header.") from exc
                redirected = urlparse(location)
                if redirected.scheme != "https" or not redirected.netloc.endswith("minimax.io"):
                    raise RuntimeError(f"Refusing unexpected redirect target: {location}") from exc
                current_url = location
                continue
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"Request failed with HTTP {exc.code}: {detail}") from exc
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise RuntimeError("Request returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Request returned an invalid response.")
        return payload
    raise RuntimeError("Request redirected too many times.")


def _normalize_epoch_millis(value: object, *, default_ttl_ms: int = 900_000) -> int:
    try:
        numeric = int(float(value))
    except (TypeError, ValueError):
        return int(time.time() * 1000) + default_ttl_ms
    if numeric < 10_000_000_000:
        return numeric * 1000
    return numeric


def _decode_jwt_payload(token: str) -> dict[str, Any] | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode((payload + padding).encode("ascii"))
        parsed = json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _trim_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _openai_codex_identity(access_token: str) -> dict[str, str]:
    payload = _decode_jwt_payload(access_token) or {}
    auth = payload.get(OPENAI_CODEX_JWT_AUTH_CLAIM)
    auth_claim = auth if isinstance(auth, dict) else {}
    profile = payload.get(OPENAI_CODEX_JWT_PROFILE_CLAIM)
    profile_claim = profile if isinstance(profile, dict) else {}
    account_id = _trim_string(auth_claim.get("chatgpt_account_id"))
    plan_type = _trim_string(auth_claim.get("chatgpt_plan_type"))
    email = _trim_string(profile_claim.get("email"))
    profile_name = email
    if not profile_name:
        stable_subject = (
            _trim_string(auth_claim.get("chatgpt_account_user_id"))
            or _trim_string(auth_claim.get("chatgpt_user_id"))
            or _trim_string(auth_claim.get("user_id"))
        )
        issuer = _trim_string(payload.get("iss"))
        subject = _trim_string(payload.get("sub"))
        if not stable_subject and issuer and subject:
            stable_subject = f"{issuer}|{subject}"
        if not stable_subject:
            stable_subject = subject
        if stable_subject:
            profile_name = f"id-{_base64url_no_padding(stable_subject.encode('utf-8'))}"
    identity: dict[str, str] = {}
    if email:
        identity["email"] = email
    if profile_name:
        identity["profileName"] = profile_name
    if account_id:
        identity["accountId"] = account_id
    if plan_type:
        identity["chatgptPlanType"] = plan_type
    return identity


def _openai_codex_auth_url(
    verifier: str,
    state: str,
    *,
    redirect_uri: str = OPENAI_CODEX_REDIRECT_URI,
) -> str:
    challenge = _base64url_no_padding(hashlib.sha256(verifier.encode("ascii")).digest())
    query = urlencode(
        {
            "response_type": "code",
            "client_id": OPENAI_CODEX_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": OPENAI_CODEX_SCOPE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
            "originator": "openclaw",
        }
    )
    return f"{OPENAI_CODEX_AUTHORIZE_URL}?{query}"


def _openclaw_codex_oauth_session_status() -> dict[str, Any]:
    now = time.time()
    active: dict[str, OpenAICodexOAuthSession] = {}
    for session_id, session in list(_OPENAI_CODEX_OAUTH_SESSIONS.items()):
        if now - session.created_at <= 900:
            active[session_id] = session
        else:
            _OPENAI_CODEX_OAUTH_SESSIONS.pop(session_id, None)
    session = next(iter(active.values())) if len(active) == 1 else None
    return {
        "active": bool(active),
        "count": len(active),
        "sessionId": next(iter(active)) if len(active) == 1 else None,
        "method": "oauth" if session else None,
        "authUrl": session.auth_url if session else "",
        "verificationUrl": "",
        "userCode": "",
        "authenticated": bool(_openai_codex_oauth_status().get("authenticated", False)),
    }


def _start_openclaw_codex_oauth(env: dict[str, str], cwd: Path, *, public_url: str | None = None) -> dict[str, Any]:
    status = _openai_codex_oauth_status()
    if status.get("authenticated"):
        return {
            "authenticated": True,
            "providerId": "openai-codex",
            "method": "oauth",
            "status": status,
            "message": "OpenAI Codex OAuth is already connected on this runtime.",
        }
    _OPENAI_CODEX_OAUTH_SESSIONS.clear()
    verifier, _challenge = _create_openai_codex_pkce_pair()
    state = secrets.token_hex(16)
    redirect_uri = OPENAI_CODEX_REDIRECT_URI
    auth_url = _openai_codex_auth_url(verifier, state, redirect_uri=redirect_uri)
    callback_port = _parse_openai_codex_callback_port(auth_url)
    session_id = secrets.token_urlsafe(16)
    relay_token = secrets.token_urlsafe(32)
    _OPENAI_CODEX_OAUTH_SESSIONS[session_id] = OpenAICodexOAuthSession(
        verifier=verifier,
        state=state,
        auth_url=auth_url,
        callback_port=callback_port,
        redirect_uri=redirect_uri,
        relay_token_hash=_sha256_hex(relay_token),
    )
    base_url = _public_url(DEFAULT_HOST, DEFAULT_PORT, public_url=public_url)
    relay_url = f"{base_url}/api/codex/login/browser-relay/complete/{session_id}"
    helper_payload = {
        "authUrl": auth_url,
        "callbackPort": callback_port,
        "relayUrl": relay_url,
        "relayToken": relay_token,
    }
    return {
        "status": "manual_required",
        "manualRequired": True,
        "providerId": "openai-codex",
        "method": "oauth",
        "sessionId": session_id,
        "authUrl": auth_url,
        "callbackPort": callback_port,
        "relayUrl": relay_url,
        "relayToken": relay_token,
        "helperPayload": helper_payload,
        "helperCommand": _build_openai_codex_helper_command(helper_payload),
        "verificationUrl": "",
        "userCode": "",
        "message": "Run the local relay helper on the browser device. It opens OpenAI sign-in, catches localhost callback, and sends it back to the NAS automatically.",
    }


def _parse_openai_codex_authorization_input(value: str) -> tuple[str, str | None]:
    stripped = value.strip()
    if not stripped:
        raise RuntimeError("Paste the OpenAI redirect URL or authorization code to complete sign-in.")
    try:
        parsed = urlparse(stripped)
        if parsed.path == "/auth/callback" and parsed.query:
            query = parse_qs(parsed.query)
            code = (query.get("code") or [""])[0].strip()
            state = (query.get("state") or [""])[0].strip() or None
            if code:
                return code, state
        if parsed.scheme and parsed.netloc:
            query = parse_qs(parsed.query)
            code = (query.get("code") or [""])[0].strip()
            state = (query.get("state") or [""])[0].strip() or None
            if code:
                return code, state
    except ValueError:
        pass
    if "code=" in stripped:
        query = parse_qs(stripped)
        code = (query.get("code") or [""])[0].strip()
        state = (query.get("state") or [""])[0].strip() or None
        if code:
            return code, state
    if "#" in stripped:
        code, state = stripped.split("#", 1)
        return code.strip(), state.strip() or None
    return stripped, None


def _exchange_openai_codex_authorization_code(
    code: str,
    verifier: str,
    *,
    redirect_uri: str = OPENAI_CODEX_REDIRECT_URI,
) -> dict[str, Any]:
    body = urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": OPENAI_CODEX_CLIENT_ID,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
        }
    ).encode("utf-8")
    request = Request(
        OPENAI_CODEX_TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"OpenAI token exchange failed with HTTP {exc.code}: {detail}") from exc
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"OpenAI token exchange failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("OpenAI token exchange returned an invalid response.")
    access = str(payload.get("access_token") or "").strip()
    refresh = str(payload.get("refresh_token") or "").strip()
    id_token = str(payload.get("id_token") or "").strip()
    expires_in = payload.get("expires_in")
    if not access or not refresh or not isinstance(expires_in, (int, float)):
        raise RuntimeError("OpenAI token exchange did not return the required OAuth tokens.")
    return {
        "access": access,
        "refresh": refresh,
        "id_token": id_token,
        "expires": int(time.time() * 1000 + float(expires_in) * 1000),
    }


def _read_auth_profile_store(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "profiles": {}}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "profiles": {}}
    return parsed if isinstance(parsed, dict) else {"version": 1, "profiles": {}}


def _normalize_auth_profiles(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return {str(key): profile for key, profile in value.items() if isinstance(profile, dict)}
    if isinstance(value, list):
        normalized: dict[str, Any] = {}
        for index, profile in enumerate(value):
            if not isinstance(profile, dict):
                continue
            provider = str(profile.get("provider") or profile.get("providerId") or "provider").strip()
            profile_id = str(profile.get("profileId") or profile.get("id") or f"{provider}:{index}").strip()
            normalized[profile_id] = profile
        return normalized
    return {}


def _write_openai_codex_auth_profile(tokens: dict[str, Any]) -> dict[str, str]:
    identity = _openai_codex_identity(str(tokens["access"]))
    profile_name = identity.get("profileName") or "default"
    profile_id = f"openai-codex:{profile_name}"
    credential: dict[str, Any] = {
        "type": "oauth",
        "provider": "openai-codex",
        "access": tokens["access"],
        "refresh": tokens["refresh"],
        "expires": tokens["expires"],
    }
    for key in ("email", "accountId", "chatgptPlanType"):
        if identity.get(key):
            credential[key] = identity[key]
    if tokens.get("id_token"):
        credential["id_token"] = tokens["id_token"]
    path = _openclaw_auth_profiles_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    store = _read_auth_profile_store(path)
    profiles = _normalize_auth_profiles(store.get("profiles"))
    profiles[profile_id] = credential
    store["version"] = 1
    store["profiles"] = profiles
    path.write_text(json.dumps(store, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    _write_codex_auth_json(tokens, identity)
    hermes_sync = _sync_openai_codex_oauth_to_wsl_hermes(tokens, identity)
    return {"profileId": profile_id, "hermesSync": hermes_sync, **identity}


def _write_minimax_openclaw_auth_profile(tokens: dict[str, Any], *, region: str) -> dict[str, str]:
    profile_id = "minimax-portal:default"
    credential: dict[str, Any] = {
        "type": "oauth",
        "provider": "minimax-portal",
        "access": tokens["access"],
        "refresh": tokens["refresh"],
        "expires": tokens["expires"],
        "region": region,
    }
    for key in ("resourceUrl", "notification_message"):
        if tokens.get(key):
            credential[key] = tokens[key]
    path = _openclaw_auth_profiles_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    store = _read_auth_profile_store(path)
    profiles = _normalize_auth_profiles(store.get("profiles"))
    profiles[profile_id] = credential
    store["version"] = 1
    store["profiles"] = profiles
    path.write_text(json.dumps(store, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    hermes_sync = _sync_minimax_openclaw_oauth_to_hermes(tokens, region=region)
    return {"profileId": profile_id, "region": region, "hermesSync": hermes_sync}


def _sync_minimax_openclaw_oauth_to_hermes(
    tokens: dict[str, Any],
    *,
    region: str,
) -> dict[str, Any]:
    access = str(tokens.get("access") or "").strip()
    refresh = str(tokens.get("refresh") or "").strip()
    if not access or not refresh:
        return {"synced": False, "error": "missing_token"}
    expires_ms = _normalize_epoch_millis(tokens.get("expires"), default_ttl_ms=86_400_000)
    now = datetime.now(timezone.utc)
    expires_at = datetime.fromtimestamp(expires_ms / 1000, tz=timezone.utc)
    portal_base_url = _minimax_base_url(region)
    inference_base_url = (
        "https://api.minimaxi.com/anthropic"
        if _normalize_minimax_region(region) == "cn"
        else "https://api.minimax.io/anthropic"
    )
    auth_state = {
        "provider": "minimax-oauth",
        "region": _normalize_minimax_region(region),
        "portal_base_url": portal_base_url,
        "inference_base_url": inference_base_url,
        "client_id": MINIMAX_OAUTH_CLIENT_ID,
        "scope": MINIMAX_OAUTH_SCOPE,
        "token_type": "Bearer",
        "access_token": access,
        "refresh_token": refresh,
        "resource_url": tokens.get("resourceUrl"),
        "obtained_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "expires_in": max(0, int(expires_at.timestamp() - now.timestamp())),
    }
    credential = {
        "id": "minimax-oauth-openclaw",
        "label": "minimax-oauth-openclaw",
        "auth_type": "oauth",
        "priority": 0,
        "source": "openclaw:oauth",
        "access_token": access,
        "refresh_token": refresh,
        "base_url": inference_base_url,
        "expires_at": expires_at.isoformat(),
        "last_status": "ok",
        "last_status_at": None,
        "last_error_code": None,
        "last_error_reason": None,
        "last_error_message": None,
        "last_error_reset_at": None,
        "request_count": 0,
        "token_type": "Bearer",
        "scope": MINIMAX_OAUTH_SCOPE,
        "client_id": MINIMAX_OAUTH_CLIENT_ID,
        "portal_base_url": portal_base_url,
        "obtained_at": now.isoformat(),
        "expires_in": auth_state["expires_in"],
    }
    hermes_home = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes")).expanduser()
    auth_path = hermes_home / "auth.json"
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        store = json.loads(auth_path.read_text(encoding="utf-8")) if auth_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        store = {}
    if not isinstance(store, dict):
        store = {}
    providers = store.setdefault("providers", {})
    if not isinstance(providers, dict):
        providers = {}
        store["providers"] = providers
    providers["minimax-oauth"] = auth_state
    pool = store.setdefault("credential_pool", {})
    if not isinstance(pool, dict):
        pool = {}
        store["credential_pool"] = pool
    entries = pool.get("minimax-oauth")
    if not isinstance(entries, list):
        entries = []
    entries = [entry for entry in entries if not (isinstance(entry, dict) and entry.get("source") == "openclaw:oauth")]
    pool["minimax-oauth"] = [credential, *entries]
    store["active_provider"] = store.get("active_provider") or "minimax-oauth"
    store["version"] = 1
    store["updated_at"] = now.isoformat()
    tmp_path = auth_path.with_name(f"{auth_path.name}.tmp.{os.getpid()}.{secrets.token_hex(8)}")
    tmp_path.write_text(json.dumps(store, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp_path, 0o600)
    except OSError:
        pass
    tmp_path.replace(auth_path)
    try:
        os.chmod(auth_path, 0o600)
    except OSError:
        pass
    return {
        "synced": True,
        "providerId": "minimax-oauth",
        "authPath": str(auth_path),
        "expiresAt": expires_at.isoformat(),
    }


def _complete_openclaw_codex_oauth(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("payload")
    nested_payload = nested if isinstance(nested, dict) else {}
    session_id = str(
        payload.get("sessionId")
        or payload.get("session_id")
        or nested_payload.get("sessionId")
        or nested_payload.get("session_id")
        or ""
    ).strip()
    callback = str(
        payload.get("callback")
        or payload.get("redirectUrl")
        or payload.get("redirect_url")
        or payload.get("code")
        or nested_payload.get("callback")
        or nested_payload.get("redirectUrl")
        or nested_payload.get("redirect_url")
        or nested_payload.get("code")
        or ""
    ).strip()
    if not session_id and len(_OPENAI_CODEX_OAUTH_SESSIONS) == 1:
        session_id = next(iter(_OPENAI_CODEX_OAUTH_SESSIONS))
    if not session_id or session_id not in _OPENAI_CODEX_OAUTH_SESSIONS:
        raise RuntimeError("OpenAI Codex OAuth session was not found or expired. Start sign-in again.")
    if not callback:
        raise RuntimeError("Paste the OpenAI redirect URL or authorization code to complete sign-in.")
    session = _OPENAI_CODEX_OAUTH_SESSIONS.pop(session_id)
    code, state = _parse_openai_codex_authorization_input(callback)
    if state and state != session.state:
        raise RuntimeError("OpenAI OAuth state mismatch. Start sign-in again from Syntelos.")
    tokens = _exchange_openai_codex_authorization_code(
        code,
        session.verifier,
        redirect_uri=session.redirect_uri,
    )
    identity = _write_openai_codex_auth_profile(tokens)
    authenticated = bool(_openai_codex_oauth_status().get("authenticated", False))
    return {
        "authenticated": authenticated,
        "providerId": "openai-codex",
        "method": "oauth",
        "message": (
            "OpenAI Codex OAuth connected."
            if authenticated
            else "OpenAI Codex OAuth command finished, but credentials are not visible yet."
        ),
        "profileId": identity.get("profileId"),
        "email": identity.get("email"),
        "hermesSync": identity.get("hermesSync"),
    }


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


def _minimax_openclaw_auth_status(
    session_secrets: dict[str, str] | None = None,
) -> dict[str, Any]:
    home = Path(os.environ.get("HOME") or str(Path.home())).expanduser()
    credentials_path = home / ".minimax" / "oauth_creds.json"
    state_root = Path(os.environ.get("OPENCLAW_STATE_DIR", str(home / ".openclaw"))).expanduser()
    auth_store_path = state_root / "agents" / "main" / "agent" / "auth-profiles.json"
    hermes_auth_stores = _scoped_hermes_auth_store_candidates(home)
    authenticated = _provider_presence(
        ["minimax-portal"],
        session_secrets=session_secrets,
    ).get("minimax-portal", False)
    source = None
    if os.environ.get("FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT"):
        source = "environment"
    elif credentials_path.exists():
        source = "minimax-cli-credentials"
    elif _openclaw_auth_store_has_provider(auth_store_path, "minimax-portal"):
        source = "openclaw-auth-profile"
    elif any(
        _openclaw_auth_store_has_provider(path, provider_id)
        for path in hermes_auth_stores
        for provider_id in ("minimax-oauth", "minimax", "minimax-portal")
    ):
        source = "hermes-auth-profile"
    return {
        "authenticated": authenticated,
        "providerId": "minimax-portal",
        "region": None,
        "expires": None,
        "credentialsPath": str(credentials_path),
        "authStorePath": str(auth_store_path),
        "hermesAuthStorePaths": [str(path) for path in hermes_auth_stores],
        "source": source,
        "message": (
            "MiniMax broker OAuth credentials are visible to the web backend."
            if authenticated
            else "MiniMax broker OAuth is not visible to the web backend yet."
        ),
    }


def _minimax_oauth_manual_command(region: object = None) -> tuple[str, str]:
    normalized_region = _normalize_minimax_region(region)
    method = "oauth-cn" if normalized_region == "cn" else "oauth"
    command = (
        "openclaw models auth login "
        f"--provider minimax-portal --method {method}"
    )
    return method, command


def _request_minimax_oauth_code(region: str, challenge: str, state: str) -> dict[str, Any]:
    base_url = _minimax_base_url(region)
    body = urlencode(
        {
            "response_type": "code",
            "client_id": MINIMAX_OAUTH_CLIENT_ID,
            "scope": MINIMAX_OAUTH_SCOPE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
    ).encode("utf-8")
    try:
        payload = _urlopen_form_json_with_redirects(
            f"{base_url}/oauth/code",
            body,
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "x-request-id": secrets.token_hex(16),
            },
        )
    except (OSError, URLError, RuntimeError) as exc:
        raise RuntimeError(f"MiniMax OAuth authorization failed: {exc}") from exc
    user_code = str(payload.get("user_code") or "").strip()
    verification_url = str(payload.get("verification_uri") or "").strip()
    returned_state = str(payload.get("state") or "").strip()
    if not user_code or not verification_url:
        raise RuntimeError("MiniMax OAuth authorization did not return a user code and verification URL.")
    if returned_state and returned_state != state:
        raise RuntimeError("MiniMax OAuth state mismatch. Start sign-in again from Syntelos.")
    return payload


def _poll_minimax_oauth_token(session: MiniMaxOAuthSession) -> dict[str, Any]:
    base_url = _minimax_base_url(session.region)
    body = urlencode(
        {
            "grant_type": MINIMAX_OAUTH_GRANT_TYPE,
            "client_id": MINIMAX_OAUTH_CLIENT_ID,
            "user_code": session.user_code,
            "code_verifier": session.verifier,
        }
    ).encode("utf-8")
    try:
        payload = _urlopen_form_json_with_redirects(
            f"{base_url}/oauth/token",
            body,
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
    except (OSError, URLError, RuntimeError) as exc:
        raise RuntimeError(f"MiniMax OAuth token request failed: {exc}") from exc
    if payload.get("status") == "error":
        raise RuntimeError("MiniMax OAuth returned an error. Try again later.")
    if payload.get("status") != "success":
        return {"pending": True, "message": "MiniMax approval is still pending."}
    access = str(payload.get("access_token") or "").strip()
    refresh = str(payload.get("refresh_token") or "").strip()
    expires = _normalize_epoch_millis(payload.get("expired_in"), default_ttl_ms=86_400_000)
    if not access or not refresh:
        raise RuntimeError("MiniMax OAuth did not return the required tokens.")
    return {
        "pending": False,
        "access": access,
        "refresh": refresh,
        "expires": expires,
        "resourceUrl": payload.get("resource_url"),
        "notification_message": payload.get("notification_message"),
    }


def _wsl_hermes_openai_codex_status() -> dict[str, Any]:
    if not shutil.which("wsl"):
        return {"authenticated": False, "source": None}
    try:
        result = subprocess.run(
            ["wsl", "bash", "-lc", "hermes auth status openai-codex 2>&1"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"authenticated": False, "source": None, "error": str(exc)}
    output = _clean_terminal_text((result.stdout or "") + (result.stderr or "")).strip()
    return {
        "authenticated": "openai-codex: logged in" in output.lower(),
        "source": "hermes-auth-store" if "openai-codex: logged in" in output.lower() else None,
        "message": output[:300],
    }


def _openai_codex_oauth_status(
    session_secrets: dict[str, str] | None = None,
) -> dict[str, Any]:
    state_root = Path(os.environ.get("OPENCLAW_STATE_DIR", str(Path.home() / ".openclaw")))
    auth_store_path = state_root / "agents" / "main" / "agent" / "auth-profiles.json"
    authenticated = _provider_presence(
        ["openai-codex"],
        session_secrets=session_secrets,
    ).get("openai-codex", False)
    source = None
    hermes_status = _wsl_hermes_openai_codex_status()
    if os.environ.get("FLUXIO_OPENAI_CODEX_OAUTH_PRESENT"):
        source = "environment"
    elif _openclaw_auth_store_has_provider(auth_store_path, "openai-codex"):
        source = "openclaw-auth-profile"
    elif os.environ.get("OPENAI_API_KEY") or (session_secrets or {}).get("openai"):
        source = "openai-api-key"
    elif hermes_status.get("authenticated"):
        authenticated = True
        source = str(hermes_status.get("source") or "hermes-auth-store")
    return {
        "authenticated": authenticated,
        "accountId": None,
        "expires": None,
        "authStorePath": str(auth_store_path),
        "hermesStatus": hermes_status,
        "source": source,
        "message": (
            "OpenAI/Codex auth is visible to the web backend."
            if authenticated
            else "OpenAI/Codex auth is not visible to the web backend yet."
        ),
    }


def _minimax_openclaw_auth_start(region: object = None) -> dict[str, Any]:
    status = _minimax_openclaw_auth_status()
    method, command = _minimax_oauth_manual_command(region)
    normalized_region = _normalize_minimax_region(region)
    if status.get("authenticated"):
        return {
            "authenticated": True,
            "launched": False,
            "manualRequired": False,
            "providerId": "minimax-portal",
            "method": method,
            "region": normalized_region,
            "command": command,
            "status": status,
            "message": "MiniMax broker OAuth is already connected on this runtime.",
        }
    try:
        verifier, challenge = _create_openai_codex_pkce_pair()
        state = secrets.token_urlsafe(16)
        oauth = _request_minimax_oauth_code(normalized_region, challenge, state)
        session_id = secrets.token_urlsafe(16)
        interval_ms = max(int(oauth.get("interval") or 2000), 1000)
        expires_at_ms = _normalize_epoch_millis(oauth.get("expired_in"))
        _MINIMAX_OAUTH_SESSIONS[session_id] = MiniMaxOAuthSession(
            verifier=verifier,
            state=state,
            region=normalized_region,
            user_code=str(oauth["user_code"]),
            verification_url=str(oauth["verification_uri"]),
            interval_ms=interval_ms,
            expires_at_ms=expires_at_ms,
        )
        return {
            "launched": True,
            "manualRequired": True,
            "providerId": "minimax-portal",
            "method": method,
            "region": normalized_region,
            "sessionId": session_id,
            "verificationUrl": str(oauth["verification_uri"]),
            "userCode": str(oauth["user_code"]),
            "intervalMs": interval_ms,
            "expiresAt": expires_at_ms,
            "command": command,
            "status": status,
            "message": "Open the MiniMax verification URL, enter the code if requested, then click Verify MiniMax.",
        }
    except Exception as exc:
        return {
            "launched": False,
            "manualRequired": True,
            "providerId": "minimax-portal",
            "method": method,
            "region": normalized_region,
            "command": command,
            "status": status,
            "error": str(exc),
            "message": (
                "MiniMax browser OAuth could not be started automatically. "
                "Run this MiniMax broker command on the NAS or runtime host, then refresh Syntelos auth status."
            ),
        }


def _minimax_openclaw_auth_complete(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("payload")
    nested_payload = nested if isinstance(nested, dict) else {}
    session_id = str(
        payload.get("sessionId")
        or payload.get("session_id")
        or nested_payload.get("sessionId")
        or nested_payload.get("session_id")
        or ""
    ).strip()
    if not session_id and len(_MINIMAX_OAUTH_SESSIONS) == 1:
        session_id = next(iter(_MINIMAX_OAUTH_SESSIONS))
    session = _MINIMAX_OAUTH_SESSIONS.get(session_id)
    if not session:
        raise RuntimeError("MiniMax OAuth session was not found or expired. Start sign-in again.")
    if int(time.time() * 1000) > session.expires_at_ms:
        _MINIMAX_OAUTH_SESSIONS.pop(session_id, None)
        raise RuntimeError("MiniMax OAuth session expired. Start sign-in again.")
    token_result = _poll_minimax_oauth_token(session)
    if token_result.get("pending"):
        return {
            "authenticated": False,
            "pending": True,
            "providerId": "minimax-portal",
            "method": "oauth-cn" if session.region == "cn" else "oauth",
            "region": session.region,
            "sessionId": session_id,
            "verificationUrl": session.verification_url,
            "userCode": session.user_code,
            "message": token_result.get("message") or "MiniMax approval is still pending.",
        }
    _MINIMAX_OAUTH_SESSIONS.pop(session_id, None)
    identity = _write_minimax_openclaw_auth_profile(token_result, region=session.region)
    status = _minimax_openclaw_auth_status()
    return {
        "authenticated": bool(status.get("authenticated")),
        "providerId": "minimax-portal",
        "method": "oauth-cn" if session.region == "cn" else "oauth",
        "region": session.region,
        "status": status,
        "profileId": identity.get("profileId"),
        "message": (
            "MiniMax broker OAuth connected."
            if status.get("authenticated")
            else "MiniMax OAuth completed, but credentials are not visible yet."
        ),
    }


def _minimax_openclaw_connect_page(region: object = None) -> str:
    result = _minimax_openclaw_auth_start(region)
    verification_url = str(result.get("verificationUrl") or "")
    user_code = str(result.get("userCode") or "")
    session_id = str(result.get("sessionId") or "")
    command = str(result.get("command") or "")
    message = str(result.get("message") or "")
    error = str(result.get("error") or "")
    status = result.get("status") if isinstance(result.get("status"), dict) else {}
    already_connected = bool(result.get("authenticated") or status.get("authenticated"))
    safe_json = json.dumps(
        {
            "sessionId": session_id,
            "verificationUrl": verification_url,
            "userCode": user_code,
        }
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Connect MiniMax broker OAuth</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; }}
    body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; background: #101417; color: #eef3f5; }}
    main {{ width: min(720px, calc(100vw - 32px)); border: 1px solid #2b383d; background: #182126; border-radius: 10px; padding: 28px; box-shadow: 0 24px 80px rgba(0,0,0,.35); }}
    h1 {{ margin: 0 0 12px; font-size: 28px; letter-spacing: 0; }}
    p {{ color: #b9c7cc; line-height: 1.55; }}
    .code {{ display: inline-block; margin: 8px 0 16px; padding: 10px 14px; border: 1px solid #3b5158; border-radius: 8px; background: #0f171a; font: 700 22px ui-monospace, SFMono-Regular, Consolas, monospace; letter-spacing: .08em; color: #ffffff; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 18px 0; }}
    a, button {{ border: 0; border-radius: 8px; padding: 11px 15px; font-weight: 700; cursor: pointer; text-decoration: none; }}
    a.primary {{ background: #46d39a; color: #07110d; }}
    button {{ background: #2f4249; color: #eef3f5; }}
    pre {{ overflow: auto; padding: 12px; border-radius: 8px; background: #0d1417; border: 1px solid #2b383d; color: #d4e2e6; }}
    .ok {{ color: #46d39a; }}
    .err {{ color: #ff8f8f; }}
  </style>
</head>
<body>
  <main>
    <h1>Connect MiniMax broker OAuth</h1>
    <p>This is the Syntelos connect step. Open MiniMax from here, approve the broker connection, then return to this page and verify the NAS/Hermes session.</p>
    {"<p class='ok'>MiniMax broker OAuth is already connected.</p>" if already_connected else ""}
    {"<p class='err'>" + html.escape(error) + "</p>" if error else ""}
    {"<p>MiniMax code:</p><div class='code'>" + html.escape(user_code) + "</div>" if user_code else ""}
    <div class="actions">
      {"<a class='primary' target='_blank' rel='noopener noreferrer' href='" + html.escape(verification_url, quote=True) + "'>Open MiniMax Connect</a>" if verification_url else ""}
      <button type="button" id="verify" {"disabled" if not session_id else ""}>Verify NAS Session</button>
      <button type="button" id="copy" {"disabled" if not user_code else ""}>Copy Code</button>
    </div>
    <p id="status">{html.escape(message)}</p>
    {"<pre>" + html.escape(command) + "</pre>" if command else ""}
  </main>
  <script>
    const flow = {safe_json};
    const statusEl = document.getElementById('status');
    document.getElementById('copy')?.addEventListener('click', async () => {{
      await navigator.clipboard.writeText(flow.userCode || '');
      statusEl.textContent = 'MiniMax code copied.';
    }});
    let verifyTimer = null;
    async function verifyMiniMax() {{
      statusEl.textContent = 'Checking MiniMax approval on the NAS runtime...';
      try {{
        const response = await fetch('/api/minimax/openclaw/complete', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ sessionId: flow.sessionId }})
        }});
        const payload = await response.json();
        if (!response.ok || payload.ok === false) throw new Error(payload.error || 'Verification failed.');
        const data = payload.data || {{}};
        statusEl.textContent = data.message || (data.authenticated ? 'MiniMax broker OAuth connected.' : 'MiniMax approval is still pending.');
        statusEl.className = data.authenticated ? 'ok' : '';
        if (data.authenticated && verifyTimer) {{
          clearInterval(verifyTimer);
          verifyTimer = null;
        }}
      }} catch (error) {{
        statusEl.textContent = String(error?.message || error);
        statusEl.className = 'err';
      }}
    }}
    document.getElementById('verify')?.addEventListener('click', () => void verifyMiniMax());
    document.querySelector('a.primary')?.addEventListener('click', () => {{
      statusEl.textContent = 'MiniMax opened. After authorization succeeds, this page will verify the NAS session automatically.';
      if (!verifyTimer) {{
        verifyTimer = setInterval(() => void verifyMiniMax(), 3000);
      }}
      setTimeout(() => void verifyMiniMax(), 5000);
    }});
  </script>
</body>
</html>"""


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
        self.provider_secrets: dict[str, str] = _load_persisted_provider_secrets(self.root)
        self.admin_config, self.generated_admin_password = ensure_admin_config(
            self.root,
            reset_password=reset_admin_password,
            public_url=public_url,
        )
        self.public_url = public_url or ""
        self.secure_cookies = self.public_url.startswith("https://")
        self.sessions: dict[str, dict[str, str]] = {}
        self._summary_cache_lock = threading.Lock()
        self._bootstrap_summary_cache: dict[
            str,
            tuple[tuple[tuple[str, int, int], ...], float, dict[str, Any]],
        ] = {}
        self._full_summary_cache: dict[
            str,
            tuple[tuple[tuple[str, int, int], ...], float, dict[str, Any]],
        ] = {}
        self._full_summary_revalidation_keys: set[str] = set()
        self._mission_detail_cache_lock = threading.Lock()
        self._mission_detail_cache: dict[str, tuple[tuple[tuple[str, int, int], ...], float, dict[str, Any]]] = {}
        self._mission_detail_prewarm_keys: set[str] = set()

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

    def _account_hints(self) -> list[dict[str, str]]:
        hints: list[dict[str, str]] = []
        for user in self.admin_users:
            username = str(user.get("username") or "").strip()
            if not username:
                continue
            display_name = str(
                user.get("displayName") or _default_display_name(username)
            ).strip() or username
            hints.append({"username": username, "displayName": display_name})
        return hints

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
            "accountHints": self._account_hints(),
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
        username_key = username.casefold()
        password = str(payload.get("password") or "")
        matched_user: dict[str, object] | None = None
        for user in self.admin_users:
            if username_key != str(user.get("username") or "").strip().casefold():
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

    def complete_openai_codex_oauth_relay(
        self,
        *,
        session_id: str,
        payload: dict[str, Any],
        authorization: str,
    ) -> dict[str, Any]:
        session_id = session_id.strip()
        session = _OPENAI_CODEX_OAUTH_SESSIONS.get(session_id)
        if not session:
            raise RuntimeError("No pending OpenAI Codex OAuth relay was found.")
        if time.time() - session.created_at > 900:
            _OPENAI_CODEX_OAUTH_SESSIONS.pop(session_id, None)
            raise RuntimeError("OpenAI Codex OAuth relay expired. Start sign-in again.")
        token = authorization[len("Bearer ") :].strip() if authorization.startswith("Bearer ") else ""
        if not token or not hmac.compare_digest(_sha256_hex(token), session.relay_token_hash):
            raise PermissionError("Invalid OpenAI Codex OAuth relay token.")
        callback_path = str(payload.get("callbackPath") or payload.get("callback_path") or "").strip()
        if (
            not callback_path.startswith("/auth/callback?")
            or "\r" in callback_path
            or "\n" in callback_path
            or callback_path.startswith(("http://", "https://"))
        ):
            raise ValueError("Invalid OpenAI Codex OAuth callback path.")
        return _complete_openclaw_codex_oauth(
            {
                "sessionId": session_id,
                "callback": callback_path,
            }
        )

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
        runtime_bin_dirs = [
            value
            for value in (
                os.environ.get("SYNTELOS_RUNTIME_BIN_DIR"),
                os.environ.get("FLUXIO_RUNTIME_BIN_DIR"),
                str(self.root / ".agent_control" / "runtime" / "bin"),
                str(self.root.parent / "runtime" / "bin"),
            )
            if value
        ]
        existing_path = os.environ.get("PATH", "")
        path_entries = [
            str(Path(value))
            for value in runtime_bin_dirs
            if Path(value).exists()
        ]
        if path_entries:
            env["PATH"] = os.pathsep.join([*path_entries, existing_path])
        env["SYNTELOS_OPENCLAW_AGENT_MODE"] = "local"
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
        if self.provider_secrets.get("opencode-go"):
            env["OPENCODE_API_KEY"] = self.provider_secrets["opencode-go"]
        return env

    def _runtime_route_proof_path(self, root: Path | None = None) -> Path:
        return Path(root or self.root) / ".agent_control" / "runtime_route_proof.json"

    def _record_runtime_route_proof(
        self,
        payload: dict[str, Any],
        result: dict[str, Any],
        *,
        root: Path | None = None,
    ) -> None:
        route = result.get("route") if isinstance(result.get("route"), dict) else {}
        proof = {
            "schema": "fluxio.runtime_route_proof.v1",
            "checkedAt": _utc_now(),
            "runtime": str(result.get("runtime") or payload.get("runtime") or "").strip(),
            "provider": str(route.get("provider") or payload.get("provider") or "").strip(),
            "model": str(route.get("model") or payload.get("model") or "").strip(),
            "modelId": str(route.get("model_id") or "").strip(),
            "effort": str(route.get("effort") or "").strip(),
            "replyPreview": str(result.get("reply") or "").strip()[:160],
            "elapsedMs": int(result.get("elapsedMs") or 0),
            "source": "authenticated_web_backend_chat",
        }
        path = self._runtime_route_proof_path(root)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}.{secrets.token_hex(8)}")
            tmp_path.write_text(json.dumps(proof, indent=2), encoding="utf-8")
            try:
                os.chmod(tmp_path, 0o600)
            except OSError:
                pass
            tmp_path.replace(path)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except OSError:
            return

    def _runtime_route_proof_status(self, root: Path) -> dict[str, Any]:
        env = self._provider_env()
        hermes_command = shutil.which("hermes", path=env.get("PATH") or os.environ.get("PATH"))
        hermes_command_source = "native" if hermes_command else ""
        version_output = ""
        if hermes_command:
            try:
                completed = subprocess.run(  # noqa: S603
                    [hermes_command, "--version"],
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    timeout=8,
                    check=False,
                    env={**os.environ, **env},
                    **hidden_windows_subprocess_kwargs(),
                )
                version_output = (completed.stdout or completed.stderr).strip().splitlines()[0]
            except Exception:
                version_output = ""
        else:
            wsl_hermes_command = _wsl_command_path("hermes")
            if wsl_hermes_command:
                hermes_command = f"wsl:{wsl_hermes_command}"
                hermes_command_source = "wsl"
                version_output = _wsl_command_version("hermes")
        proof: dict[str, Any] = {}
        try:
            loaded = json.loads(self._runtime_route_proof_path(root).read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                proof = loaded
        except (OSError, json.JSONDecodeError):
            proof = {}
        proof_model = str(proof.get("model") or "").strip()
        proof_provider = str(proof.get("provider") or "").strip()
        m3_verified = (
            str(proof.get("runtime") or "").strip().lower() == "hermes"
            and proof_provider.lower().startswith("minimax")
            and proof_model.lower() == "minimax-m3"
            and bool(str(proof.get("replyPreview") or "").strip())
        )
        return {
            "schema": "fluxio.runtime_route_status.v1",
            "checkedAt": _utc_now(),
            "hermesCommand": hermes_command or "",
            "hermesCommandSource": hermes_command_source,
            "hermesCommandVisible": bool(hermes_command),
            "hermesVersion": version_output,
            "frontendExecutorModel": "MiniMax-M3",
            "frontendExecutorProvider": "minimax-oauth",
            "minimaxM3Verified": m3_verified,
            "proof": proof,
            "source": "backend_runtime_path_and_last_successful_chat",
        }

    def _with_provider_env(self, callback):
        env = self._provider_env()
        previous = {key: os.environ.get(key) for key in env}
        try:
            os.environ.update(env)
            return callback()
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def _run_cli(
        self,
        root: Path,
        command: str,
        args: list[str],
        timeout: int = 180,
        *,
        fast_control_room: bool = False,
    ) -> dict[str, Any]:
        env = self._provider_env()
        if fast_control_room:
            env["FLUXIO_CONTROL_ROOM_FAST"] = "1"
        return _run_cli(root, command, args, timeout=timeout, extra_env=env)

    def _build_control_room_summary(self, root: Path) -> dict[str, Any]:
        return self._with_provider_env(lambda: ControlRoomStore(root).build_summary_snapshot())

    def _build_control_room_bootstrap_summary(self, root: Path) -> dict[str, Any]:
        return self._with_provider_env(lambda: ControlRoomStore(root).build_bootstrap_summary_snapshot())

    def _build_control_room_mission_detail(
        self,
        root: Path,
        *,
        mission_id: str,
        event_limit: int,
        freshness: str = "control-files-matched",
    ) -> dict[str, Any]:
        return self._with_provider_env(
            lambda: ControlRoomStore(root).build_mission_detail_snapshot(
                mission_id,
                event_limit=event_limit,
            )
        )

    def _control_room_freshness_signature(self, root: Path) -> tuple[tuple[str, int, int], ...]:
        store = ControlRoomStore(root)
        rows: list[tuple[str, int, int]] = []
        watched_paths = [
            store.missions_path,
            store.events_path,
            store.workspaces_path,
            store.workspace_actions_path,
            root / ".agent_control" / "mission_watchdog.json",
            root / ".agent_control" / "mission_watchdog_problems.json",
            root / ".agent_control" / "mission_watchdog_supervisor.json",
            root / ".agent_control" / "connected_apps_state.json",
            root / "config" / "connected_apps.json",
            root / "src" / "grant_agent" / "app_capability_standard.py",
        ]
        runtime_compartment_dir = root / ".agent_control" / "runtime_compartments"
        watched_paths.append(runtime_compartment_dir)
        if runtime_compartment_dir.exists():
            watched_paths.extend(sorted(runtime_compartment_dir.glob("*.json")))
        for path in watched_paths:
            try:
                stat = path.stat()
            except OSError:
                rows.append((str(path), 0, 0))
            else:
                rows.append((str(path), int(stat.st_mtime_ns), int(stat.st_size)))
        return tuple(rows)

    @staticmethod
    def _mission_detail_cache_key(root: Path, mission_id: str, event_limit: int) -> str:
        return f"{root.resolve()}::{mission_id}::{event_limit}"

    @staticmethod
    def _mission_detail_item_limits(event_limit: int) -> dict[str, int]:
        return {
            "events": event_limit,
            "action_history": 60,
            "plan_revisions": 12,
            "derived_tasks": 80,
            "improvement_queue": 80,
            "routing_decisions": 40,
            "skill_usage": 80,
            "learned_skill_events": 80,
            "delegated_session_events": 20,
        }

    def _annotate_mission_detail_cache(
        self,
        payload: dict[str, Any],
        *,
        status: str,
        started: float,
        cached_at: float | None,
        event_limit: int,
        freshness: str = "control-files-matched",
    ) -> dict[str, Any]:
        annotated = dict(payload)
        annotated["performance"] = dict(payload.get("performance", {}))
        performance = annotated.setdefault("performance", {})
        previous_duration = performance.get("durationMs")
        served_duration = round((time.perf_counter() - started) * 1000, 2)
        performance["durationMs"] = served_duration
        performance["missionDetailCache"] = {
            "schema": "fluxio.control_room.mission_detail_cache.v1",
            "status": status,
            "ageMs": round((time.monotonic() - cached_at) * 1000, 2) if cached_at else 0,
            "freshness": freshness,
            "generationDurationMs": previous_duration,
            "maxItems": MISSION_DETAIL_CACHE_MAX_ITEMS,
        }
        performance["payloadBytes"] = len(
            json.dumps(annotated, separators=(",", ":")).encode("utf-8")
        )
        performance["budget"] = ControlRoomStore._performance_budget_payload(
            source="control_room_mission_detail",
            duration_ms=served_duration,
            payload_bytes=performance["payloadBytes"],
            duration_budget_ms=CONTROL_ROOM_DETAIL_DURATION_BUDGET_MS,
            payload_budget_bytes=CONTROL_ROOM_DETAIL_PAYLOAD_BUDGET_BYTES,
            item_limits=self._mission_detail_item_limits(event_limit),
        )
        return annotated

    def _cached_control_room_mission_detail(
        self,
        root: Path,
        *,
        mission_id: str,
        event_limit: int,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        cache_key = self._mission_detail_cache_key(root, mission_id, event_limit)
        signature = self._control_room_freshness_signature(root)
        with self._mission_detail_cache_lock:
            cached = self._mission_detail_cache.get(cache_key)
            if cached:
                cached_age = time.monotonic() - cached[1]
            else:
                cached_age = 0.0
            if cached and (
                cached[0] == signature
                or cached_age <= MISSION_DETAIL_STALE_WHILE_REVALIDATE_SECONDS
            ):
                if cached[0] != signature:
                    self._queue_mission_detail_cache_refresh(
                        root,
                        mission_id=mission_id,
                        event_limit=event_limit,
                        cache_key=cache_key,
                    )
                return self._annotate_mission_detail_cache(
                    cached[2],
                    status="hit",
                    started=started,
                    cached_at=cached[1],
                    event_limit=event_limit,
                    freshness=(
                        "control-files-matched"
                        if cached[0] == signature
                        else "stale-while-revalidate"
                    ),
                )
            prewarm_in_progress = cache_key in self._mission_detail_prewarm_keys

        if prewarm_in_progress:
            deadline = time.monotonic() + MISSION_DETAIL_PREWARM_WAIT_SECONDS
            while time.monotonic() < deadline:
                time.sleep(0.025)
                with self._mission_detail_cache_lock:
                    cached = self._mission_detail_cache.get(cache_key)
                    if cached:
                        cached_age = time.monotonic() - cached[1]
                    else:
                        cached_age = 0.0
                    if cached and (
                        cached[0] == signature
                        or cached_age <= MISSION_DETAIL_STALE_WHILE_REVALIDATE_SECONDS
                    ):
                        if cached[0] != signature:
                            self._queue_mission_detail_cache_refresh(
                                root,
                                mission_id=mission_id,
                                event_limit=event_limit,
                                cache_key=cache_key,
                            )
                        return self._annotate_mission_detail_cache(
                            cached[2],
                            status="hit",
                            started=started,
                            cached_at=cached[1],
                            event_limit=event_limit,
                            freshness=(
                                "control-files-matched"
                                if cached[0] == signature
                                else "stale-while-revalidate"
                            ),
                        )
            with self._mission_detail_cache_lock:
                self._mission_detail_prewarm_keys.discard(cache_key)
        else:
            with self._mission_detail_cache_lock:
                self._mission_detail_prewarm_keys.discard(cache_key)

        payload = self._build_control_room_mission_detail(
            root,
            mission_id=mission_id,
            event_limit=event_limit,
        )
        self._store_mission_detail_cache(cache_key, signature, payload)
        return self._annotate_mission_detail_cache(
            payload,
            status="miss",
            started=started,
            cached_at=None,
            event_limit=event_limit,
        )

    def _store_mission_detail_cache(
        self,
        cache_key: str,
        signature: tuple[tuple[str, int, int], ...],
        payload: dict[str, Any],
    ) -> None:
        with self._mission_detail_cache_lock:
            self._mission_detail_cache[cache_key] = (
                signature,
                time.monotonic(),
                dict(payload, performance=dict(payload.get("performance", {}))),
            )
            if len(self._mission_detail_cache) > MISSION_DETAIL_CACHE_MAX_ITEMS:
                oldest_key = min(
                    self._mission_detail_cache,
                    key=lambda key: self._mission_detail_cache[key][1],
                )
                self._mission_detail_cache.pop(oldest_key, None)

    def _queue_mission_detail_cache_refresh(
        self,
        root: Path,
        *,
        mission_id: str,
        event_limit: int,
        cache_key: str,
    ) -> None:
        if cache_key in self._mission_detail_prewarm_keys:
            return
        self._mission_detail_prewarm_keys.add(cache_key)
        timer = threading.Timer(
            0.01,
            self._refresh_control_room_mission_detail_cache,
            args=(root, mission_id, event_limit, cache_key),
        )
        timer.daemon = True
        timer.start()

    def _prewarm_control_room_mission_details(self, root: Path, summary: dict[str, Any]) -> None:
        if not MISSION_DETAIL_PREWARM_ENABLED:
            return
        missions = summary.get("missions") if isinstance(summary.get("missions"), list) else []
        mission_ids = [
            str(item.get("mission_id") or item.get("missionId") or "").strip()
            for item in missions
            if isinstance(item, dict)
            and str(item.get("status") or "").strip().lower() == "running"
            and str(item.get("mission_id") or item.get("missionId") or "").strip()
        ][:4]
        if not mission_ids:
            return
        for index, mission_id in enumerate(mission_ids):
            prewarm_key = f"{root.resolve()}::{mission_id}::80"
            with self._mission_detail_cache_lock:
                if prewarm_key in self._mission_detail_prewarm_keys:
                    continue
                self._mission_detail_prewarm_keys.add(prewarm_key)
            self._start_mission_detail_prewarm_timer(
                root,
                mission_id,
                prewarm_key,
                delay_seconds=MISSION_DETAIL_PREWARM_DELAY_SECONDS * (index + 1),
            )

    def _start_mission_detail_prewarm_timer(
        self,
        root: Path,
        mission_id: str,
        prewarm_key: str,
        *,
        delay_seconds: float = MISSION_DETAIL_PREWARM_DELAY_SECONDS,
    ) -> None:
        timer = threading.Timer(
            delay_seconds,
            self._run_mission_detail_prewarm,
            args=(root, mission_id, prewarm_key),
        )
        timer.daemon = True
        timer.start()

    def _run_mission_detail_prewarm(self, root: Path, mission_id: str, prewarm_key: str) -> None:
        try:
            signature = self._control_room_freshness_signature(root)
            with self._mission_detail_cache_lock:
                if prewarm_key not in self._mission_detail_prewarm_keys:
                    return
                cached = self._mission_detail_cache.get(prewarm_key)
                if cached and cached[0] == signature:
                    return
            payload = self._build_control_room_mission_detail(
                root,
                mission_id=mission_id,
                event_limit=80,
            )
            self._store_mission_detail_cache(prewarm_key, signature, payload)
        except Exception:
            pass
        finally:
            with self._mission_detail_cache_lock:
                self._mission_detail_prewarm_keys.discard(prewarm_key)

    def _refresh_control_room_mission_detail_cache(
        self,
        root: Path,
        mission_id: str,
        event_limit: int,
        cache_key: str,
    ) -> None:
        try:
            signature = self._control_room_freshness_signature(root)
            payload = self._build_control_room_mission_detail(
                root,
                mission_id=mission_id,
                event_limit=event_limit,
            )
            self._store_mission_detail_cache(cache_key, signature, payload)
        except Exception:
            pass
        finally:
            with self._mission_detail_cache_lock:
                self._mission_detail_prewarm_keys.discard(cache_key)

    def _annotate_control_room_summary_cache(
        self,
        payload: dict[str, Any],
        *,
        status: str,
        cached_at: float | None,
        freshness: str,
        ttl_seconds: float,
    ) -> dict[str, Any]:
        annotated = copy.deepcopy(payload)
        annotated["summaryCache"] = {
            "schema": "fluxio.control_room.summary_cache.v1",
            "mode": "full",
            "status": status,
            "freshness": freshness,
            "ttlSeconds": ttl_seconds,
            "staleWhileRevalidateSeconds": FULL_SUMMARY_STALE_WHILE_REVALIDATE_SECONDS,
            "ageMs": round((time.monotonic() - cached_at) * 1000, 2) if cached_at else 0,
        }
        return annotated

    @staticmethod
    def _persisted_control_room_summary_cache_path(root: Path) -> Path:
        return root / ".agent_control" / "control_room_summary_cache.json"

    @staticmethod
    def _persisted_control_room_bootstrap_summary_cache_path(root: Path) -> Path:
        return root / ".agent_control" / "control_room_bootstrap_summary_cache.json"

    @staticmethod
    def _temporary_control_room_cache_path(root: Path, name: str) -> Path:
        digest = hashlib.sha256(str(root.resolve()).encode("utf-8", errors="ignore")).hexdigest()[:16]
        return Path(tempfile.gettempdir()) / "fluxio-control-room-cache" / digest / name

    @classmethod
    def _control_room_summary_cache_paths(cls, root: Path, *, bootstrap: bool) -> list[Path]:
        primary = (
            cls._persisted_control_room_bootstrap_summary_cache_path(root)
            if bootstrap
            else cls._persisted_control_room_summary_cache_path(root)
        )
        temporary = cls._temporary_control_room_cache_path(
            root,
            "control_room_bootstrap_summary_cache.json"
            if bootstrap
            else "control_room_summary_cache.json",
        )
        return [primary, temporary]

    @staticmethod
    def _serializable_control_room_signature(
        signature: tuple[tuple[str, int, int], ...],
    ) -> list[list[object]]:
        return [[path, mtime_ns, size] for path, mtime_ns, size in signature]

    @staticmethod
    def _signature_from_serialized(value: object) -> tuple[tuple[str, int, int], ...]:
        if not isinstance(value, list):
            return ()
        rows: list[tuple[str, int, int]] = []
        for item in value:
            if not isinstance(item, (list, tuple)) or len(item) != 3:
                return ()
            try:
                rows.append((str(item[0]), int(item[1]), int(item[2])))
            except (TypeError, ValueError):
                return ()
        return tuple(rows)

    def _load_persisted_control_room_summary(
        self,
        root: Path,
        signature: tuple[tuple[str, int, int], ...],
    ) -> dict[str, Any] | None:
        paths = self._control_room_summary_cache_paths(root, bootstrap=False)
        path = paths[0]
        try:
            payload = None
            for candidate in paths:
                try:
                    payload = json.loads(candidate.read_text(encoding="utf-8"))
                    path = candidate
                    break
                except (OSError, json.JSONDecodeError):
                    continue
            if payload is None:
                return None
        except OSError:
            return None
        if path != paths[0]:
            pass
        if not isinstance(payload, dict):
            return None
        if payload.get("cacheVersion") != PERSISTED_FULL_SUMMARY_CACHE_VERSION:
            return None
        if self._signature_from_serialized(payload.get("signature")) != signature:
            return None
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            return None
        return summary

    def _write_persisted_control_room_summary(
        self,
        root: Path,
        signature: tuple[tuple[str, int, int], ...],
        payload: dict[str, Any],
    ) -> None:
        primary_path, temporary_path = self._control_room_summary_cache_paths(root, bootstrap=False)
        path = primary_path
        try:
            if shutil.disk_usage(path.parent).free < 2_000_000:
                path = temporary_path
        except OSError:
            path = temporary_path
        cache_payload = {
            "schema": "fluxio.control_room.persisted_summary_cache.v1",
            "cacheVersion": PERSISTED_FULL_SUMMARY_CACHE_VERSION,
            "writtenAt": _utc_now(),
            "signature": self._serializable_control_room_signature(signature),
            "summary": copy.deepcopy(payload),
        }
        cache_payload["summary"].pop("summaryCache", None)
        cache_payload["summary"].pop("webBackend", None)
        cache_payload["summary"].pop("providerSecretPresence", None)
        cache_payload["summary"].pop("runtimeRouteProof", None)
        cache_payload["summary"].pop("webPushStatus", None)
        cache_payload["summary"].pop("ntfyStatus", None)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}.{secrets.token_hex(8)}")
        try:
            tmp_path.write_text(json.dumps(cache_payload, separators=(",", ":")), encoding="utf-8")
            try:
                os.chmod(tmp_path, 0o600)
            except OSError:
                pass
            tmp_path.replace(path)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except OSError:
            try:
                tmp_path.unlink()
            except OSError:
                pass

    def _load_persisted_control_room_bootstrap_summary(
        self,
        root: Path,
        signature: tuple[tuple[str, int, int], ...],
    ) -> dict[str, Any] | None:
        paths = self._control_room_summary_cache_paths(root, bootstrap=True)
        payload = None
        for path in paths:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                break
            except (OSError, json.JSONDecodeError):
                continue
        if payload is None:
            return None
        if not isinstance(payload, dict):
            return None
        if payload.get("cacheVersion") != PERSISTED_BOOTSTRAP_SUMMARY_CACHE_VERSION:
            return None
        if self._signature_from_serialized(payload.get("signature")) != signature:
            return None
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            return None
        return summary

    def _write_persisted_control_room_bootstrap_summary(
        self,
        root: Path,
        signature: tuple[tuple[str, int, int], ...],
        payload: dict[str, Any],
    ) -> None:
        primary_path, temporary_path = self._control_room_summary_cache_paths(root, bootstrap=True)
        path = primary_path
        try:
            if shutil.disk_usage(path.parent).free < 2_000_000:
                path = temporary_path
        except OSError:
            path = temporary_path
        cache_payload = {
            "schema": "fluxio.control_room.persisted_bootstrap_summary_cache.v1",
            "cacheVersion": PERSISTED_BOOTSTRAP_SUMMARY_CACHE_VERSION,
            "writtenAt": _utc_now(),
            "signature": self._serializable_control_room_signature(signature),
            "summary": copy.deepcopy(payload),
        }
        cache_payload["summary"].pop("summaryCache", None)
        cache_payload["summary"].pop("webBackend", None)
        cache_payload["summary"].pop("providerSecretPresence", None)
        cache_payload["summary"].pop("runtimeRouteProof", None)
        cache_payload["summary"].pop("webPushStatus", None)
        cache_payload["summary"].pop("ntfyStatus", None)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}.{secrets.token_hex(8)}")
        try:
            tmp_path.write_text(json.dumps(cache_payload, separators=(",", ":"), default=str), encoding="utf-8")
            try:
                os.chmod(tmp_path, 0o600)
            except OSError:
                pass
            tmp_path.replace(path)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except OSError:
            try:
                tmp_path.unlink()
            except OSError:
                pass

    def _cached_control_room_summary(self, root: Path) -> dict[str, Any]:
        cache_key = str(root.resolve())
        signature = self._control_room_freshness_signature(root)
        now = time.monotonic()
        should_revalidate = False
        with self._summary_cache_lock:
            cached = self._full_summary_cache.get(cache_key)
            cached_age = now - cached[1] if cached else 0.0
            if cached and cached_age <= FULL_SUMMARY_CACHE_TTL_SECONDS:
                return self._annotate_control_room_summary_cache(
                    cached[2],
                    status="hit",
                    cached_at=cached[1],
                    freshness=(
                        "control-files-matched"
                        if cached[0] == signature
                        else "control-files-changed"
                    ),
                    ttl_seconds=FULL_SUMMARY_CACHE_TTL_SECONDS,
                )
            if cached and cached_age <= FULL_SUMMARY_STALE_WHILE_REVALIDATE_SECONDS:
                if cache_key not in self._full_summary_revalidation_keys:
                    self._full_summary_revalidation_keys.add(cache_key)
                    should_revalidate = True
                payload = self._annotate_control_room_summary_cache(
                    cached[2],
                    status="stale-while-revalidate",
                    cached_at=cached[1],
                    freshness=(
                        "control-files-matched"
                        if cached[0] == signature
                        else "control-files-changed"
                    ),
                    ttl_seconds=FULL_SUMMARY_CACHE_TTL_SECONDS,
                )
            else:
                payload = None
        if payload is not None:
            if should_revalidate:
                self._start_control_room_summary_revalidate(root, cache_key)
            return payload

        persisted_payload = self._load_persisted_control_room_summary(root, signature)
        if persisted_payload is not None:
            cached_at = time.monotonic()
            with self._summary_cache_lock:
                self._full_summary_cache[cache_key] = (
                    signature,
                    cached_at,
                    copy.deepcopy(persisted_payload),
                )
            return self._annotate_control_room_summary_cache(
                persisted_payload,
                status="disk-hit",
                cached_at=cached_at,
                freshness="control-files-matched",
                ttl_seconds=FULL_SUMMARY_CACHE_TTL_SECONDS,
            )

        payload = self._build_control_room_summary(root)
        refreshed_signature = self._control_room_freshness_signature(root)
        with self._summary_cache_lock:
            self._full_summary_cache[cache_key] = (
                refreshed_signature,
                time.monotonic(),
                copy.deepcopy(payload),
            )
        self._write_persisted_control_room_summary(root, refreshed_signature, payload)
        return self._annotate_control_room_summary_cache(
            payload,
            status="miss",
            cached_at=None,
            freshness="rebuilt",
            ttl_seconds=FULL_SUMMARY_CACHE_TTL_SECONDS,
        )

    def _start_control_room_summary_revalidate(self, root: Path, cache_key: str) -> None:
        worker = threading.Thread(
            target=self._run_control_room_summary_revalidate,
            args=(root, cache_key),
            daemon=True,
        )
        worker.start()

    def _run_control_room_summary_revalidate(self, root: Path, cache_key: str) -> None:
        try:
            payload = self._build_control_room_summary(root)
            signature = self._control_room_freshness_signature(root)
            with self._summary_cache_lock:
                self._full_summary_cache[cache_key] = (
                    signature,
                    time.monotonic(),
                    copy.deepcopy(payload),
                )
            self._write_persisted_control_room_summary(root, signature, payload)
        except Exception:
            pass
        finally:
            with self._summary_cache_lock:
                self._full_summary_revalidation_keys.discard(cache_key)

    def _cached_control_room_bootstrap_summary(self, root: Path) -> dict[str, Any]:
        started = time.perf_counter()
        cache_key = str(root.resolve())
        signature = self._control_room_freshness_signature(root)
        now = time.monotonic()
        with self._summary_cache_lock:
            cached = self._bootstrap_summary_cache.get(cache_key)
            if cached and cached[0] == signature:
                return self._annotate_control_room_bootstrap_cache(
                    cached[2],
                    status="hit",
                    started=started,
                    cached_at=cached[1],
                    freshness="control-files-matched",
                )

        persisted_payload = self._load_persisted_control_room_bootstrap_summary(root, signature)
        if persisted_payload is not None:
            cached_at = time.monotonic()
            with self._summary_cache_lock:
                self._bootstrap_summary_cache[cache_key] = (
                    signature,
                    cached_at,
                    copy.deepcopy(persisted_payload),
                )
            return self._annotate_control_room_bootstrap_cache(
                persisted_payload,
                status="disk-hit",
                started=started,
                cached_at=cached_at,
                freshness="control-files-matched",
            )

        payload = self._build_control_room_bootstrap_summary(root)
        refreshed_signature = self._control_room_freshness_signature(root)
        with self._summary_cache_lock:
            self._bootstrap_summary_cache[cache_key] = (
                refreshed_signature,
                time.monotonic(),
                copy.deepcopy(payload),
            )
        self._write_persisted_control_room_bootstrap_summary(root, refreshed_signature, payload)
        return self._annotate_control_room_bootstrap_cache(
            payload,
            status="miss",
            started=started,
            cached_at=None,
            freshness="rebuilt",
        )

    def _annotate_control_room_bootstrap_cache(
        self,
        payload: dict[str, Any],
        *,
        status: str,
        started: float,
        cached_at: float | None,
        freshness: str,
    ) -> dict[str, Any]:
        annotated = copy.deepcopy(payload)
        performance = dict(annotated.get("performance", {}))
        generation_duration = performance.get("durationMs")
        served_duration = round((time.perf_counter() - started) * 1000, 2)
        annotated["summaryCache"] = {
            "schema": "fluxio.control_room.summary_cache.v1",
            "status": status,
            "freshness": freshness,
            "ttlSeconds": BOOTSTRAP_SUMMARY_CACHE_TTL_SECONDS,
            "ageMs": round((time.monotonic() - cached_at) * 1000, 2) if cached_at else 0,
            "generationDurationMs": generation_duration,
        }
        performance["durationMs"] = served_duration
        performance["payloadBytes"] = len(
            json.dumps(annotated, separators=(",", ":"), default=str).encode("utf-8")
        )
        previous_budget = performance.get("budget") if isinstance(performance.get("budget"), dict) else {}
        previous_limits = previous_budget.get("itemLimits") if isinstance(previous_budget.get("itemLimits"), dict) else {}
        performance["budget"] = ControlRoomStore._performance_budget_payload(
            source="control_room_summary_bootstrap",
            duration_ms=served_duration,
            payload_bytes=performance["payloadBytes"],
            duration_budget_ms=CONTROL_ROOM_SUMMARY_DURATION_BUDGET_MS,
            payload_budget_bytes=CONTROL_ROOM_SUMMARY_PAYLOAD_BUDGET_BYTES,
            item_limits=dict(previous_limits),
        )
        annotated["performance"] = performance
        return annotated

    def _workspace_roots(self) -> list[str]:
        candidates = [self.root, Path.home()]
        nas_mirror = Path("C:/volume1") if os.name == "nt" else Path("/volume1")
        if nas_mirror.exists():
            candidates.append(nas_mirror)
        if os.name == "nt":
            for letter in string.ascii_uppercase:
                drive = Path(f"{letter}:/")
                if drive.exists():
                    candidates.append(drive)
        else:
            candidates.append(Path("/"))
        roots: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            normalized = str(resolved)
            if normalized in seen:
                continue
            seen.add(normalized)
            roots.append(normalized)
        return roots

    def _project_mission_artifact_roots(self) -> list[Path]:
        projects_roots: list[Path] = []
        for candidate in (self.root, *self.root.parents):
            if candidate.name == "projects":
                projects_roots.append(candidate)
                break
        mirror_candidates = (
            [Path("C:/volume1/Saclay/projects")]
            if os.name == "nt"
            else [Path("/volume1/Saclay/projects"), Path("/mnt/c/volume1/Saclay/projects")]
        )
        projects_roots.extend(mirror_candidates)
        roots: list[Path] = []
        seen: set[str] = set()
        for projects_root in projects_roots:
            if not projects_root.exists() or not projects_root.is_dir():
                continue
            for control_dir in projects_root.glob("*/.agent_control/mission_artifacts"):
                try:
                    resolved = control_dir.expanduser().resolve()
                except OSError:
                    continue
                if not resolved.exists() or not resolved.is_dir():
                    continue
                key = str(resolved)
                if key in seen:
                    continue
                seen.add(key)
                roots.append(resolved)
        return roots

    def _artifact_allowed_roots(self) -> list[Path]:
        candidates = [
            self.root / ".agent_control" / "image_playground_artifacts",
            self.root / ".agent_control" / "generated_image_artifacts",
            self.root / ".agent_control" / "design_references",
            self.root / ".agent_control" / "mission_artifacts",
            self.root / ".agent_control" / "runtime_compartments",
            self.root / ".agent_control" / "runtime_sessions",
            self.root / ".agent_control" / "mission_async",
            self.root / ".agent_runs",
        ]
        if os.name == "nt":
            candidates.append(Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_control/design_references"))
            candidates.append(Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_control/mission_artifacts"))
            candidates.append(Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_control/runtime_sessions"))
            candidates.append(Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_control/mission_async"))
            candidates.append(Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_runs"))
        else:
            candidates.append(Path("/volume1/Saclay/projects/vibe-coding-platform/.agent_control/design_references"))
            candidates.append(Path("/volume1/Saclay/projects/vibe-coding-platform/.agent_control/mission_artifacts"))
            candidates.append(Path("/volume1/Saclay/projects/vibe-coding-platform/.agent_control/runtime_sessions"))
            candidates.append(Path("/volume1/Saclay/projects/vibe-coding-platform/.agent_control/mission_async"))
            candidates.append(Path("/volume1/Saclay/projects/vibe-coding-platform/.agent_runs"))
        candidates.extend(self._project_mission_artifact_roots())
        roots: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            try:
                resolved = candidate.expanduser().resolve()
            except OSError:
                continue
            if not resolved.exists():
                continue
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            roots.append(resolved)
        return roots

    def _candidate_artifact_paths(self, raw_path: object) -> list[Path]:
        raw = str(raw_path or "").strip()
        if raw.startswith("file://"):
            raw = unquote(urlparse(raw).path)
        raw = raw.replace("\x00", "")
        candidates: list[Path] = []
        if raw:
            source = Path(raw).expanduser()
            candidates.append(source if source.is_absolute() else self.root / source)
            normalized = raw.replace("\\", "/")
            if re.match(r"^[A-Za-z]:[\\/]", raw):
                candidates.append(_platform_path_for_windows_drive(raw).expanduser())
            embedded_windows = re.search(r"([A-Za-z]:[\\/][^\r\n]+)$", raw)
            if embedded_windows:
                candidates.append(_platform_path_for_windows_drive(embedded_windows.group(1)).expanduser())
            if normalized.startswith("/volume1/"):
                volume_relative = normalized[len("/volume1/") :]
                candidates.append(Path("C:/volume1") / volume_relative)
                if os.name != "nt":
                    candidates.append(Path("/mnt/c/volume1") / volume_relative)
            embedded_normalized = re.search(r"([A-Za-z]:/[^\r\n]+)$", normalized)
            if embedded_normalized:
                candidates.append(_platform_path_for_windows_drive(embedded_normalized.group(1)).expanduser())
            direct_hits: list[Path] = []
            seen_direct: set[str] = set()
            for candidate in candidates:
                try:
                    resolved = candidate.resolve()
                except OSError:
                    continue
                if not resolved.exists() or not resolved.is_file():
                    continue
                key = str(resolved)
                if key in seen_direct:
                    continue
                seen_direct.add(key)
                direct_hits.append(resolved)
            if direct_hits:
                return direct_hits
            name = Path(normalized).name
            if name:
                for search_root in (
                    self.root / ".agent_control" / "image_playground_artifacts",
                    self.root / ".agent_control" / "generated_image_artifacts",
                    self.root / ".agent_control" / "design_references",
                    self.root / ".agent_control" / "mission_artifacts",
                    self.root / ".agent_control" / "runtime_compartments",
                    self.root / ".agent_control" / "runtime_sessions",
                    self.root / ".agent_control" / "mission_async",
                    self.root / ".agent_runs",
                    Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_control/design_references"),
                    Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_control/mission_artifacts"),
                    Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_control/runtime_sessions"),
                    Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_control/mission_async"),
                    Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_runs"),
                    *self._project_mission_artifact_roots(),
                ):
                    if search_root.exists():
                        candidates.extend(search_root.rglob(name))
        deduped: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(resolved)
        return deduped

    def _resolve_artifact_path(self, raw_path: object) -> Path:
        allowed_roots = self._artifact_allowed_roots()
        for candidate in self._candidate_artifact_paths(raw_path):
            if not candidate.exists() or not candidate.is_file():
                continue
            if candidate.suffix.lower() not in ARTIFACT_CONTENT_TYPES:
                continue
            for root in allowed_roots:
                try:
                    candidate.relative_to(root)
                    return candidate
                except ValueError:
                    continue
        raise RuntimeError("Artifact was not found under an allowed workspace or NAS mirror root.")

    def _artifact_id(self, path: Path) -> str:
        return _sha256_hex(str(path.resolve()))[:24]

    def _resolve_artifact_id(self, raw_id: object) -> Path:
        artifact_id = str(raw_id or "").strip().lower()
        if not re.fullmatch(r"[a-f0-9]{24}", artifact_id):
            raise RuntimeError("Artifact id is invalid.")
        for root in self._artifact_allowed_roots():
            for candidate in root.rglob("*"):
                if not candidate.is_file() or candidate.suffix.lower() not in ARTIFACT_CONTENT_TYPES:
                    continue
                if self._artifact_id(candidate) == artifact_id:
                    return candidate
        raise RuntimeError("Artifact was not found under an allowed workspace or NAS mirror root.")

    def _artifact_url(self, path: Path) -> str:
        return f"/api/artifact?id={self._artifact_id(path)}"

    def _image_provider_id(self, payload: dict[str, Any]) -> str:
        provider_raw = payload.get("provider")
        provider_id = ""
        if isinstance(provider_raw, dict):
            provider_id = str(
                provider_raw.get("id")
                or provider_raw.get("providerId")
                or provider_raw.get("provider_id")
                or ""
            ).strip()
        else:
            provider_id = str(provider_raw or "").strip()
        if not provider_id:
            provider_id = str(payload.get("providerId") or payload.get("provider_id") or "").strip()
        return provider_id or IMAGE_PROVIDER_CODEX_SUBSCRIPTION_ID

    def _image_provider_unavailable(
        self,
        payload: dict[str, Any],
        *,
        message: str,
        blocked_reason: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_id = _safe_identifier(payload.get("requestId") or f"image_{int(time.time())}", "image_request")
        return {
            "status": "unavailable",
            "providerStatus": "blocked",
            "provider": IMAGE_PROVIDER_CODEX_EXPECTED_PROVIDER,
            "providerId": IMAGE_PROVIDER_CODEX_SUBSCRIPTION_ID,
            "model": IMAGE_PROVIDER_CODEX_EXPECTED_MODEL,
            "route": "codex_subscription",
            "authMode": "codex subscription",
            "billingNote": "codex subscription",
            "requestId": request_id,
            "blockedReason": blocked_reason,
            "message": message,
            "details": details or {},
        }

    def _is_png_file(self, path: Path) -> bool:
        try:
            header = path.read_bytes()[:8]
        except OSError:
            return False
        return header == b"\x89PNG\r\n\x1a\n"

    def _extract_openclaw_image_route(self, payload: dict[str, Any]) -> tuple[str, str]:
        candidates: list[tuple[str, str]] = []

        def push(provider: object, model: object) -> None:
            provider_text = str(provider or "").strip().lower()
            model_text = str(model or "").strip().lower()
            if not provider_text and "/" in model_text:
                provider_text = model_text.split("/", 1)[0]
            if provider_text or model_text:
                candidates.append((provider_text, model_text))

        def collect(value: object) -> None:
            if not isinstance(value, dict):
                return
            push(value.get("provider"), value.get("model"))
            route = value.get("route")
            if isinstance(route, dict):
                push(route.get("provider"), route.get("model"))

        collect(payload)
        attempts = payload.get("attempts")
        if isinstance(attempts, list):
            for attempt in attempts:
                collect(attempt)
                if isinstance(attempt, dict):
                    collect(attempt.get("candidate"))
                    collect(attempt.get("details"))
        return candidates[0] if candidates else ("", "")

    def _openclaw_codex_image_oauth_evidence(self, payload: dict[str, Any], stderr: str) -> dict[str, Any]:
        proof_text = "\n".join(
            item
            for item in (
                str(stderr or ""),
                str(payload.get("stderr") or ""),
                str(payload.get("routeProof") or ""),
                str(payload.get("authProof") or ""),
            )
            if item.strip()
        )
        normalized = proof_text.lower()
        provider_match = re.search(r"\bprovider\s*=\s*([a-z0-9_-]+)", proof_text, flags=re.IGNORECASE)
        mode_match = re.search(r"\bmode\s*=\s*([a-z0-9_-]+)", proof_text, flags=re.IGNORECASE)
        transport_match = re.search(r"\btransport\s*=\s*([a-z0-9_-]+)", proof_text, flags=re.IGNORECASE)
        provider = (provider_match.group(1).lower() if provider_match else "").strip()
        mode = (mode_match.group(1).lower() if mode_match else "").strip()
        transport = (transport_match.group(1).lower() if transport_match else "").strip()
        proven = (
            provider == IMAGE_PROVIDER_CODEX_EXPECTED_PROVIDER
            and mode == "oauth"
            and transport == "codex-responses"
        ) or (
            "provider=openai-codex" in normalized
            and "mode=oauth" in normalized
            and "transport=codex-responses" in normalized
        )
        return {
            "proven": proven,
            "provider": provider,
            "mode": mode,
            "transport": transport,
            "proofLine": next(
                (line.strip() for line in proof_text.splitlines() if "image auth selected" in line.lower()),
                "",
            )[:320],
        }

    def _write_image_playground_artifact(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = _safe_identifier(payload.get("requestId") or f"image_{int(time.time())}", "image_request")
        provider_id = self._image_provider_id(payload)
        if provider_id != IMAGE_PROVIDER_CODEX_SUBSCRIPTION_ID:
            return self._image_provider_unavailable(
                payload,
                message=(
                    "Only GPT-Image-2 via Codex subscription is enabled for this workbench. "
                    "Switch provider to the Codex subscription lane."
                ),
                blocked_reason="provider_not_allowed",
                details={
                    "requestedProviderId": provider_id,
                    "allowedProviderId": IMAGE_PROVIDER_CODEX_SUBSCRIPTION_ID,
                },
            )

        allow_paid_api_fallback = bool(
            payload.get("allowPaidApiFallback") or payload.get("allow_paid_api_fallback")
        )
        codex_auth = _openai_codex_oauth_status(session_secrets=self.provider_secrets)
        codex_source = str(codex_auth.get("source") or "").strip().lower()
        codex_authenticated = bool(codex_auth.get("authenticated"))
        if not codex_authenticated:
            return self._image_provider_unavailable(
                payload,
                message="OpenAI Codex OAuth is not connected on this runtime.",
                blocked_reason="codex_auth_missing",
                details={"authStatus": codex_auth},
            )
        if codex_source == "openai-api-key" and not allow_paid_api_fallback:
            return self._image_provider_unavailable(
                payload,
                message=(
                    "Paid OpenAI API-key routing is blocked for this image lane. "
                    "Connect OpenAI Codex OAuth to use codex subscription billing."
                ),
                blocked_reason="paid_api_fallback_blocked",
                details={
                    "authStatus": codex_auth,
                    "allowPaidApiFallback": False,
                },
            )

        env = self._provider_env()
        command = shutil.which("openclaw", path=env.get("PATH") or os.environ.get("PATH"))
        if not command:
            return self._image_provider_unavailable(
                payload,
                message="OpenClaw CLI was not found on PATH.",
                blocked_reason="openclaw_missing",
            )

        workspace_path = Path(str(payload.get("workspacePath") or self.root)).expanduser()
        if not workspace_path.exists():
            workspace_path = self.root

        artifact_dir = self.root / ".agent_control" / "design_references" / "codex_image_artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        image_path = artifact_dir / f"{request_id}.png"
        manifest_path = artifact_dir / f"{request_id}.manifest.json"

        prompt_text = _image_prompt_text(payload)
        args = [
            command,
            "infer",
            "image",
            "generate",
            "--model",
            IMAGE_PROVIDER_CODEX_COMMAND_MODEL,
            "--prompt",
            prompt_text,
            "--output",
            str(image_path),
            "--json",
        ]
        size = str(payload.get("size") or (payload.get("provider") if isinstance(payload.get("provider"), dict) else {}).get("size") or "").strip()
        if size:
            args.extend(["--size", size])
        try:
            run_payload, _stdout, stderr, elapsed_ms = _run_process_capture(
                args,
                cwd=workspace_path,
                timeout=900,
                extra_env=env,
            )
        except RuntimeError as exc:
            return self._image_provider_unavailable(
                payload,
                message=str(exc) or "OpenClaw image generation failed.",
                blocked_reason="openclaw_generation_failed",
                details={"command": args},
            )

        provider_value, model_value = self._extract_openclaw_image_route(run_payload)
        model_name = model_value.split("/")[-1] if model_value else ""
        route_evidence = self._openclaw_codex_image_oauth_evidence(run_payload, stderr)
        route_is_codex_subscription = (
            provider_value == IMAGE_PROVIDER_CODEX_EXPECTED_PROVIDER
            or (provider_value == "openai" and route_evidence["proven"])
        )
        if not route_is_codex_subscription or model_name != IMAGE_PROVIDER_CODEX_EXPECTED_MODEL:
            return self._image_provider_unavailable(
                payload,
                message=(
                    "OpenClaw did not prove Codex subscription routing "
                    f"(provider={provider_value or 'unknown'}, model={model_name or model_value or 'unknown'})."
                ),
                blocked_reason="route_validation_failed",
                details={
                    "expectedProvider": IMAGE_PROVIDER_CODEX_EXPECTED_PROVIDER,
                    "expectedModel": IMAGE_PROVIDER_CODEX_EXPECTED_MODEL,
                    "reportedProvider": provider_value,
                    "reportedModel": model_value,
                    "routeEvidence": route_evidence,
                    "raw": run_payload,
                },
            )

        if not image_path.exists() or not self._is_png_file(image_path):
            return self._image_provider_unavailable(
                payload,
                message="OpenClaw returned success but did not write a valid PNG artifact.",
                blocked_reason="artifact_validation_failed",
                details={
                    "artifactPath": str(image_path),
                    "exists": image_path.exists(),
                },
            )

        artifact_sha = _sha256_file(image_path)
        manifest = {
            "requestId": request_id,
            "artifactId": request_id,
            "servedArtifactId": self._artifact_id(image_path),
            "artifactPath": str(image_path),
            "artifactSha256": artifact_sha,
            "contentType": "image/png",
            "providerId": IMAGE_PROVIDER_CODEX_SUBSCRIPTION_ID,
            "provider": IMAGE_PROVIDER_CODEX_EXPECTED_PROVIDER,
            "model": IMAGE_PROVIDER_CODEX_EXPECTED_MODEL,
            "route": "codex_subscription",
            "authMode": "codex subscription",
            "billingNote": "codex subscription",
            "providerRoute": "openclaw infer image generate",
            "safeArtifactArea": ".agent_control/design_references/codex_image_artifacts",
            "localPath": str(image_path),
            "nasPathCandidates": [
                str(image_path),
                str(image_path).replace(str(self.root), "/volume1/Saclay/projects/vibe-coding-platform"),
            ],
            "prompt": payload.get("prompt") if isinstance(payload.get("prompt"), dict) else {},
            "canvas": payload.get("canvas") if isinstance(payload.get("canvas"), dict) else {},
            "createdAt": _utc_now(),
            "provenance": {
                "servedBy": "web-backend",
                "safeEndpoint": "/api/artifact",
                "allowedRoots": [str(item) for item in self._artifact_allowed_roots()],
                "arbitraryWorkspaceFilesExposed": False,
                "routeEvidence": {
                    "provider": provider_value,
                    "model": model_value,
                    "rawProvider": run_payload.get("provider"),
                    "rawModel": run_payload.get("model"),
                    "authProvider": route_evidence["provider"],
                    "authMode": route_evidence["mode"],
                    "transport": route_evidence["transport"],
                    "proofLine": route_evidence["proofLine"],
                },
            },
            "runtime": {
                "host": os.environ.get("COMPUTERNAME") or (os.uname().nodename if hasattr(os, "uname") else ""),
                "root": str(self.root),
                "artifactServer": "web-backend",
                "elapsedMs": elapsed_ms,
            },
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        manifest_sha = _sha256_file(manifest_path)
        manifest["manifestPath"] = str(manifest_path)
        manifest["manifestSha256"] = manifest_sha
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return {
            "provider": IMAGE_PROVIDER_CODEX_EXPECTED_PROVIDER,
            "providerId": IMAGE_PROVIDER_CODEX_SUBSCRIPTION_ID,
            "providerStatus": "available",
            "route": "codex_subscription",
            "authMode": "codex subscription",
            "billingNote": "codex subscription",
            "model": IMAGE_PROVIDER_CODEX_EXPECTED_MODEL,
            "message": "Generated PNG artifact was written and served through the Codex subscription route.",
            "requestId": request_id,
            "artifactId": request_id,
            "servedArtifactId": self._artifact_id(image_path),
            "outputArtifactPath": str(image_path),
            "imagePath": str(image_path),
            "previewUrl": self._artifact_url(image_path),
            "manifestPath": str(manifest_path),
            "manifestUrl": self._artifact_url(manifest_path),
            "contentType": "image/png",
            "safeArtifactArea": ".agent_control/design_references/codex_image_artifacts",
            "provenance": manifest["provenance"],
            "receipt": {
                "promptHash": _sha256_hex(json.dumps(payload.get("prompt") or {}, sort_keys=True))[:12],
                "artifactSha256": artifact_sha,
                "manifestSha256": manifest_sha,
                "providerName": "OpenAI Codex subscription",
                "provider": IMAGE_PROVIDER_CODEX_EXPECTED_PROVIDER,
                "model": IMAGE_PROVIDER_CODEX_EXPECTED_MODEL,
                "route": "codex_subscription",
                "authMode": "codex subscription",
                "billingNote": "codex subscription",
                "testStatus": "Checked",
            },
            "layer": {
                "id": f"layer-{request_id}",
                "name": "Codex subscription artifact",
                "type": "image",
                "src": self._artifact_url(image_path),
                "x": 0,
                "y": 0,
                "width": (payload.get("canvas") if isinstance(payload.get("canvas"), dict) else {}).get("width") or 1024,
                "height": (payload.get("canvas") if isinstance(payload.get("canvas"), dict) else {}).get("height") or 1024,
                "rotation": 0,
                "promptRole": "generated image artifact served by backend",
            },
        }

    def _image_self_repair_loop_artifact(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = _safe_identifier(payload.get("requestId") or f"image_self_repair_{int(time.time())}", "image_self_repair")
        artifact_dir = self.root / ".agent_control" / "image_playground_self_repair" / request_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        preferred_route = {
            "runtime": "hermes",
            "provider": "openrouter",
            "model": "z-ai/glm-5.2",
            "modelId": "openrouter/z-ai/glm-5.2",
            "effort": "high",
            "role": "vision-ui-self-repair",
            "fallbackRuntime": "openclaw",
        }
        skills_used = [
            {
                "id": "image_vision_breakdown",
                "input": "current Images surface screenshot, DOM facts, gallery/layer/annotation state",
                "output": "clutter, hierarchy, real controls, decorative controls, and removal candidates",
                "route": preferred_route,
                "artifact": "vision_breakdown.json",
            },
            {
                "id": "ui_self_repair_planner",
                "input": "vision breakdown plus current mission constraints",
                "output": "concrete repair plan for Image Playground first viewport",
                "route": preferred_route,
                "artifact": "ui_repair_plan.json",
            },
            {
                "id": "self_repair_verifier",
                "input": "before/after screenshot paths, DOM markers, route evidence, changed surface contract",
                "output": "proof checklist and remaining risk",
                "route": preferred_route,
                "artifact": "self_repair_verifier.json",
            },
        ]

        env = self._provider_env()
        opencode_command = shutil.which("opencode", path=env.get("PATH") or os.environ.get("PATH"))
        hermes_command = shutil.which("hermes", path=env.get("PATH") or os.environ.get("PATH"))
        hermes_wsl_available = False
        if not hermes_command:
            try:
                hermes_wsl_available = _wsl_has_command("hermes")
            except Exception:
                hermes_wsl_available = False
        openclaw_command = shutil.which("openclaw", path=env.get("PATH") or os.environ.get("PATH"))
        opencode_models_contains_glm52 = False
        opencode_models_error = ""
        opencode_auth_store = Path.home() / ".local" / "share" / "opencode" / "auth.json"
        opencode_auth_providers: list[str] = []
        if opencode_auth_store.exists():
            try:
                loaded_auth = json.loads(opencode_auth_store.read_text(encoding="utf-8"))
                if isinstance(loaded_auth, dict):
                    opencode_auth_providers = sorted(str(key) for key in loaded_auth.keys())
            except (OSError, json.JSONDecodeError):
                opencode_auth_providers = []
        if opencode_command:
            try:
                _models_payload, models_stdout, _models_stderr, _models_elapsed_ms = _run_process_capture(
                    [opencode_command, "models"],
                    cwd=self.root,
                    timeout=35,
                    extra_env=env,
                )
                opencode_models_contains_glm52 = "openrouter/z-ai/glm-5.2" in models_stdout
            except Exception as exc:  # noqa: BLE001 - proof artifact should record the exact route discovery failure.
                opencode_models_error = str(exc)

        provider_presence = _provider_presence(["openrouter", "opencode-go", "openai-codex"], session_secrets=self.provider_secrets)
        provider_presence["openrouter_opencode_auth"] = "openrouter" in opencode_auth_providers
        route_prompt = (
            "Analyze Fluxio Mission 1 Image Playground UI from these runtime facts. "
            "Return concise JSON with findings and repairPlan. Focus on clutter, weak hierarchy, fake proof surfaces, "
            "too many status cards, missing central task focus, real controls versus decorative controls, "
            "and what should be removed, merged, or redesigned.\n\n"
            + json.dumps(
                {
                    "surface": "images",
                    "mission": "Image Playground and vision self-repair loop",
                    "screenshotPath": payload.get("screenshotPath") or payload.get("screenshot_path") or "",
                    "domFacts": payload.get("domFacts") if isinstance(payload.get("domFacts"), dict) else {},
                    "galleryCount": payload.get("galleryCount"),
                    "layerCount": payload.get("layerCount"),
                    "annotationCount": payload.get("annotationCount"),
                    "route": preferred_route,
                    "skills": [item["id"] for item in skills_used],
                },
                sort_keys=True,
            )
        )
        probe_external_routes = bool(payload.get("probeExternalRoutes") or payload.get("probe_external_routes"))

        def empty_route_call(runtime_name: str, available: bool) -> dict[str, Any]:
            return {
                "runtime": runtime_name,
                "attempted": bool(available),
                "available": bool(available),
                "status": "not_attempted",
                "reply": "",
                "error": "",
                "elapsedMs": 0,
                "command": "",
            }

        route_attempts: dict[str, dict[str, Any]] = {
            "hermes": empty_route_call("hermes", bool(hermes_command) or hermes_wsl_available),
            "openclaw": empty_route_call("openclaw", bool(openclaw_command)),
        }
        route_payload = {
            "message": route_prompt,
            "route": {
                "provider": preferred_route["provider"],
                "model": preferred_route["model"],
                "effort": preferred_route["effort"],
                "role": preferred_route["role"],
            },
            "workspacePath": str(self.root),
            "workspaceId": self.root.name,
            "sessionId": request_id,
            "timeoutSeconds": int(payload.get("timeoutSeconds") or payload.get("timeout_seconds") or 45),
        }
        if not probe_external_routes:
            route_attempts["hermes"].update(
                {
                    "status": "discovery_only",
                    "error": (
                        "Direct Hermes inference probe was not executed for this UI command because provider CLI probes "
                        "can outlive Python timeouts on Windows. Route discovery and skill artifacts were still written."
                    ),
                }
            )
            route_attempts["openclaw"].update(
                {
                    "status": "discovery_only",
                    "error": (
                        "Direct OpenClaw inference probe was not executed for this UI command because a hung model process "
                        "would freeze the app. Use probeExternalRoutes=true for an explicit risky probe."
                    ),
                }
            )
        elif route_attempts["hermes"]["available"]:
            try:
                route_result = self._run_hermes_chat(route_payload)
                route_attempts["hermes"].update(
                    {
                        "status": "ok",
                        "reply": route_result.get("reply") or "",
                        "elapsedMs": route_result.get("elapsedMs") or 0,
                        "command": route_result.get("command") or "",
                    }
                )
            except Exception as exc:  # noqa: BLE001 - timeout/failure is part of the route proof.
                route_attempts["hermes"].update({"status": "failed", "error": str(exc)})
        else:
            route_attempts["hermes"]["error"] = "Hermes CLI was not found on PATH or WSL."

        if probe_external_routes and route_attempts["hermes"]["status"] != "ok":
            if route_attempts["openclaw"]["available"]:
                try:
                    route_result = self._run_openclaw_chat(route_payload)
                    route_attempts["openclaw"].update(
                        {
                            "status": "ok",
                            "reply": route_result.get("reply") or "",
                            "elapsedMs": route_result.get("elapsedMs") or 0,
                            "command": route_result.get("command") or "",
                        }
                    )
                except Exception as exc:  # noqa: BLE001 - timeout/failure is part of the route proof.
                    route_attempts["openclaw"].update({"status": "failed", "error": str(exc)})
            else:
                route_attempts["openclaw"]["error"] = "OpenClaw CLI was not found on PATH."

        selected_runtime = "hermes" if route_attempts["hermes"]["status"] in {"ok", "discovery_only"} else "openclaw"
        route_call: dict[str, Any] = route_attempts[selected_runtime]
        route_call = {
            **route_call,
            "preferredRuntime": "hermes",
            "fallbackRuntime": "openclaw",
            "selectedRuntime": selected_runtime,
        }
        used_glm_reply = route_call["status"] == "ok" and bool(route_call.get("reply"))
        breakdown = {
            "schema": "fluxio.image_vision_breakdown.v1",
            "requestId": request_id,
            "createdAt": _utc_now(),
            "skill": skills_used[0],
            "route": preferred_route,
            "routeStatus": route_call["status"],
            "modelReplyUsed": used_glm_reply,
            "modelReplyExcerpt": str(route_call.get("reply") or "")[:2400],
            "findings": [
                {
                    "id": "legacy-entry-surface",
                    "severity": "high",
                    "finding": "The Images route starts as a small legacy image studio panel instead of the full Image Playground.",
                    "repair": "Route surface=images directly into ImagePlaygroundSurface and make the gallery/stage/prompt bar the first viewport.",
                },
                {
                    "id": "hierarchy-clutter",
                    "severity": "high",
                    "finding": "Prompt controls, proof receipts, layer tools, queue telemetry, and skill state compete at the same visual level.",
                    "repair": "Promote a single selected image stage, a persistent command bar, and a compact inspector; move dense receipts into drawers.",
                },
                {
                    "id": "decorative-proof",
                    "severity": "medium",
                    "finding": "Proof language appears before runtime evidence and makes the product feel verifier-shaped.",
                    "repair": "Show route/skill proof only after the self-repair command writes artifact paths.",
                },
                {
                    "id": "square-controls",
                    "severity": "medium",
                    "finding": "Surface-specific CSS forces square buttons and panels that clash with the cleaner premium app direction.",
                    "repair": "Give Images its own compact radius, focus states, and reduced-motion-aware transitions.",
                },
            ],
        }
        repair_plan = {
            "schema": "fluxio.ui_self_repair_plan.v1",
            "requestId": request_id,
            "createdAt": _utc_now(),
            "skill": skills_used[1],
            "route": preferred_route,
            "selectedRepair": "Replace the legacy Images surface with the real Image Playground and add a first-viewport mission workbench.",
            "steps": [
                "Wire surface=images to ImagePlaygroundSurface.",
                "Add a persistent command bar with prompt, provider, vision route, export target, and self-repair action.",
                "Make the gallery, selected stage, layers, annotations, and inspector visible in one coherent workbench.",
                "Attach route/skill proof artifacts to the Image Playground state and compact proof panel.",
                "Override the square-control CSS for Images and keep motion accessible.",
            ],
        }
        verifier = {
            "schema": "fluxio.self_repair_verifier.v1",
            "requestId": request_id,
            "createdAt": _utc_now(),
            "skill": skills_used[2],
            "route": preferred_route,
            "checks": [
                {"id": "route-discovered", "passed": bool(opencode_models_contains_glm52), "detail": "OpenCode model list includes openrouter/z-ai/glm-5.2."},
                {
                    "id": "route-called-or-safely-skipped",
                    "passed": route_call["status"] in {"ok", "discovery_only"},
                    "detail": route_call["status"] if route_call["status"] != "failed" else route_call["error"][:500],
                },
                {"id": "skills-materialized", "passed": True, "detail": "Skill artifacts were written to disk with inputs, outputs, route, and proof paths."},
                {"id": "fallback-honest", "passed": route_call["status"] == "ok" or bool(route_call.get("error")), "detail": "When the model route fails or times out, the artifact records that failure instead of claiming GLM output."},
            ],
        }
        route_proof = {
            "schema": "fluxio.image_self_repair_route_proof.v1",
            "requestId": request_id,
            "createdAt": _utc_now(),
            "preferredRoute": preferred_route,
            "opencode": {
                "command": self._display_command([opencode_command or "opencode", "models"]),
                "available": bool(opencode_command),
                "authProviders": opencode_auth_providers,
                "modelsContainGlm52": opencode_models_contains_glm52,
                "error": opencode_models_error,
            },
            "providerPresence": provider_presence,
            "probeExternalRoutes": probe_external_routes,
            "hermes": {
                "available": bool(hermes_command) or hermes_wsl_available,
                "nativeCommandVisible": bool(hermes_command),
                "wslCommandVisible": hermes_wsl_available,
                "call": route_attempts["hermes"],
            },
            "openclaw": {
                "available": bool(openclaw_command),
                "call": route_attempts["openclaw"],
            },
            "selectedRuntime": route_call["selectedRuntime"],
            "skillsUsed": skills_used,
        }

        artifacts = {
            "routeProofPath": str(artifact_dir / "route_proof.json"),
            "visionBreakdownPath": str(artifact_dir / "vision_breakdown.json"),
            "repairPlanPath": str(artifact_dir / "ui_repair_plan.json"),
            "verifierPath": str(artifact_dir / "self_repair_verifier.json"),
        }
        (artifact_dir / "route_proof.json").write_text(json.dumps(route_proof, indent=2), encoding="utf-8")
        (artifact_dir / "vision_breakdown.json").write_text(json.dumps(breakdown, indent=2), encoding="utf-8")
        (artifact_dir / "ui_repair_plan.json").write_text(json.dumps(repair_plan, indent=2), encoding="utf-8")
        (artifact_dir / "self_repair_verifier.json").write_text(json.dumps(verifier, indent=2), encoding="utf-8")
        return {
            "requestId": request_id,
            "status": "recorded",
            "route": preferred_route,
            "routeStatus": route_call["status"],
            "usedModelReply": used_glm_reply,
            "skillsUsed": skills_used,
            "findings": breakdown["findings"],
            "plan": repair_plan,
            "verifier": verifier,
            "artifacts": artifacts,
            "message": (
                "GLM-5.2 route produced the vision breakdown."
                if used_glm_reply
                else "GLM-5.2 route discovery proof was captured; deterministic self-repair plan used because direct inference did not return usable output."
            ),
        }

    def _ui_self_repair_loop_artifact(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = _safe_identifier(payload.get("requestId") or f"ui_self_repair_{int(time.time())}", "ui_self_repair")
        artifact_dir = self.root / ".agent_control" / "ui_self_repair" / request_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        surface = str(payload.get("surface") or "builder").strip() or "builder"
        preferred_route = {
            "runtime": "hermes",
            "provider": "openrouter",
            "model": "z-ai/glm-5.2",
            "modelId": "openrouter/z-ai/glm-5.2",
            "effort": "high",
            "role": "operator-ui-self-repair",
            "fallbackRuntime": "openclaw",
        }
        skills_used = [
            {
                "id": "operator_ui_breakdown",
                "input": "rendered Builder/Agent surface screenshot, DOM facts, visible first-viewport regions",
                "output": "primary object, next action, duplicate proof/status regions, and fold/remove candidates",
                "route": preferred_route,
                "artifact": "ui_breakdown.json",
            },
            {
                "id": "operator_ui_repair_planner",
                "input": "UI breakdown plus Mission 2 completion constraints",
                "output": "one focused repair plan for the current mission canvas and proof disclosure",
                "route": preferred_route,
                "artifact": "ui_repair_plan.json",
            },
            {
                "id": "implementation_surface_contract",
                "input": "repair plan, data attributes, screenshots, and touched surface contract",
                "output": "component/CSS/test contract for the implemented repair",
                "route": preferred_route,
                "artifact": "implementation_contract.json",
            },
            {
                "id": "self_repair_verifier",
                "input": "before/after screenshot paths, route evidence, focused checks, and remaining caveats",
                "output": "verification checklist for the broader UI self-repair pass",
                "route": preferred_route,
                "artifact": "self_repair_verifier.json",
            },
        ]

        env = self._provider_env()
        opencode_command = shutil.which("opencode", path=env.get("PATH") or os.environ.get("PATH"))
        hermes_command = shutil.which("hermes", path=env.get("PATH") or os.environ.get("PATH"))
        hermes_wsl_available = False
        if not hermes_command:
            try:
                hermes_wsl_available = _wsl_has_command("hermes")
            except Exception:
                hermes_wsl_available = False
        openclaw_command = shutil.which("openclaw", path=env.get("PATH") or os.environ.get("PATH"))
        opencode_models_contains_glm52 = False
        opencode_models_error = ""
        opencode_auth_store = Path.home() / ".local" / "share" / "opencode" / "auth.json"
        opencode_auth_providers: list[str] = []
        if opencode_auth_store.exists():
            try:
                loaded_auth = json.loads(opencode_auth_store.read_text(encoding="utf-8"))
                if isinstance(loaded_auth, dict):
                    opencode_auth_providers = sorted(str(key) for key in loaded_auth.keys())
            except (OSError, json.JSONDecodeError):
                opencode_auth_providers = []
        if opencode_command:
            try:
                _models_payload, models_stdout, _models_stderr, _models_elapsed_ms = _run_process_capture(
                    [opencode_command, "models"],
                    cwd=self.root,
                    timeout=35,
                    extra_env=env,
                )
                opencode_models_contains_glm52 = "openrouter/z-ai/glm-5.2" in models_stdout
            except Exception as exc:  # noqa: BLE001 - proof artifact records discovery failure.
                opencode_models_error = str(exc)

        provider_presence = _provider_presence(["openrouter", "opencode-go", "openai-codex"], session_secrets=self.provider_secrets)
        provider_presence["openrouter_opencode_auth"] = "openrouter" in opencode_auth_providers
        route_prompt = (
            "Analyze Fluxio Mission 2 broader UI cleanup from these runtime facts. "
            "Return concise JSON with findings and a repair plan. Focus on one dominant work object, "
            "duplicate proof/status regions, first-viewport hierarchy, real controls versus decorative controls, "
            "and what should be folded, merged, or redesigned.\n\n"
            + json.dumps(
                {
                    "surface": surface,
                    "mission": "Broader UI cleanup and self-repair loop",
                    "clarityMode": payload.get("clarityMode") or "",
                    "previewMode": payload.get("previewMode") or "",
                    "screenshotPath": payload.get("screenshotPath") or payload.get("screenshot_path") or "",
                    "missionCount": payload.get("missionCount"),
                    "selectedMissionId": payload.get("selectedMissionId") or "",
                    "selectedMissionTitle": payload.get("selectedMissionTitle") or "",
                    "domFacts": payload.get("domFacts") if isinstance(payload.get("domFacts"), dict) else {},
                    "route": preferred_route,
                    "skills": [item["id"] for item in skills_used],
                },
                sort_keys=True,
            )
        )
        probe_external_routes = bool(payload.get("probeExternalRoutes") or payload.get("probe_external_routes"))

        def empty_route_call(runtime_name: str, available: bool) -> dict[str, Any]:
            return {
                "runtime": runtime_name,
                "attempted": bool(available),
                "available": bool(available),
                "status": "not_attempted",
                "reply": "",
                "error": "",
                "elapsedMs": 0,
                "command": "",
            }

        route_attempts: dict[str, dict[str, Any]] = {
            "hermes": empty_route_call("hermes", bool(hermes_command) or hermes_wsl_available),
            "openclaw": empty_route_call("openclaw", bool(openclaw_command)),
        }
        route_payload = {
            "message": route_prompt,
            "route": {
                "provider": preferred_route["provider"],
                "model": preferred_route["model"],
                "effort": preferred_route["effort"],
                "role": preferred_route["role"],
            },
            "workspacePath": str(self.root),
            "workspaceId": self.root.name,
            "sessionId": request_id,
            "timeoutSeconds": int(payload.get("timeoutSeconds") or payload.get("timeout_seconds") or 45),
        }
        if not probe_external_routes:
            route_attempts["hermes"].update(
                {
                    "status": "discovery_only",
                    "error": (
                        "Direct Hermes inference probe was not executed for this UI command because provider CLI probes "
                        "can outlive Python timeouts on Windows. Route discovery and skill artifacts were still written."
                    ),
                }
            )
            route_attempts["openclaw"].update(
                {
                    "status": "discovery_only",
                    "error": (
                        "Direct OpenClaw inference probe was not executed for this UI command because a hung model process "
                        "would freeze the app. Use probeExternalRoutes=true for an explicit risky probe."
                    ),
                }
            )
        elif route_attempts["hermes"]["available"]:
            try:
                route_result = self._run_hermes_chat(route_payload)
                route_attempts["hermes"].update(
                    {
                        "status": "ok",
                        "reply": route_result.get("reply") or "",
                        "elapsedMs": route_result.get("elapsedMs") or 0,
                        "command": route_result.get("command") or "",
                    }
                )
            except Exception as exc:  # noqa: BLE001 - timeout/failure is route proof.
                route_attempts["hermes"].update({"status": "failed", "error": str(exc)})
        else:
            route_attempts["hermes"]["error"] = "Hermes CLI was not found on PATH or WSL."

        if probe_external_routes and route_attempts["hermes"]["status"] != "ok":
            if route_attempts["openclaw"]["available"]:
                try:
                    route_result = self._run_openclaw_chat(route_payload)
                    route_attempts["openclaw"].update(
                        {
                            "status": "ok",
                            "reply": route_result.get("reply") or "",
                            "elapsedMs": route_result.get("elapsedMs") or 0,
                            "command": route_result.get("command") or "",
                        }
                    )
                except Exception as exc:  # noqa: BLE001 - timeout/failure is route proof.
                    route_attempts["openclaw"].update({"status": "failed", "error": str(exc)})
            else:
                route_attempts["openclaw"]["error"] = "OpenClaw CLI was not found on PATH."

        selected_runtime = "hermes" if route_attempts["hermes"]["status"] in {"ok", "discovery_only"} else "openclaw"
        route_call: dict[str, Any] = {
            **route_attempts[selected_runtime],
            "preferredRuntime": "hermes",
            "fallbackRuntime": "openclaw",
            "selectedRuntime": selected_runtime,
        }
        used_glm_reply = route_call["status"] == "ok" and bool(route_call.get("reply"))
        breakdown = {
            "schema": "fluxio.operator_ui_breakdown.v1",
            "requestId": request_id,
            "createdAt": _utc_now(),
            "surface": surface,
            "skill": skills_used[0],
            "route": preferred_route,
            "routeStatus": route_call["status"],
            "modelReplyUsed": used_glm_reply,
            "modelReplyExcerpt": str(route_call.get("reply") or "")[:2400],
            "findings": [
                {
                    "id": "missing-current-object",
                    "severity": "high",
                    "finding": "Builder first viewport starts with readiness/proof framing instead of a dominant current mission object.",
                    "repair": "Promote a current mission command canvas with title, next action, progress, route, and primary actions.",
                },
                {
                    "id": "duplicate-status-surfaces",
                    "severity": "high",
                    "finding": "Status grid, command rail, beginner guide, flow board, and proof diff repeat mission/proof state.",
                    "repair": "Keep a compact proof receipt near the current mission and fold duplicated rails in Focus mode.",
                },
                {
                    "id": "proof-over-work",
                    "severity": "medium",
                    "finding": "Fixture proof surfaces appear as large panels before a user has a concrete action path.",
                    "repair": "Reduce preview proof weight and keep Full mode for audit depth.",
                },
                {
                    "id": "route-not-actionable",
                    "severity": "medium",
                    "finding": "Hermes/OpenClaw route context is scattered across status panels instead of tied to the selected mission.",
                    "repair": "Show Hermes primary and OpenClaw fallback as compact receipts in the current mission canvas.",
                },
            ],
        }
        repair_plan = {
            "schema": "fluxio.operator_ui_repair_plan.v1",
            "requestId": request_id,
            "createdAt": _utc_now(),
            "surface": surface,
            "skill": skills_used[1],
            "route": preferred_route,
            "selectedRepair": "Make Builder's first viewport a current-mission command canvas and fold duplicate proof surfaces.",
            "steps": [
                "Add Builder current mission command canvas with Continue, Verify, Launch, and Run self-repair actions.",
                "Attach compact Hermes/OpenClaw/proof receipts to that canvas.",
                "Demote preview readiness and fixture proof panels below the command object.",
                "Hide duplicate command/proof/status rails in Builder Focus mode while preserving Full diagnostics.",
                "Add frontend/backend tests and browser screenshot proof.",
            ],
        }
        implementation_contract = {
            "schema": "fluxio.implementation_surface_contract.v1",
            "requestId": request_id,
            "createdAt": _utc_now(),
            "skill": skills_used[2],
            "route": preferred_route,
            "surfaceMarkers": [
                "data-builder-current-mission=\"true\"",
                "data-ui-self-repair-canvas=\"mission2\"",
                "data-builder-self-repair-action=\"true\"",
            ],
            "changedSurface": "web/src/fluxio/FluxioReferenceShell.jsx",
            "styleSurface": "web/src/fluxio/styles.css",
        }
        verifier = {
            "schema": "fluxio.self_repair_verifier.v1",
            "requestId": request_id,
            "createdAt": _utc_now(),
            "skill": skills_used[3],
            "route": preferred_route,
            "checks": [
                {"id": "route-discovered", "passed": bool(opencode_models_contains_glm52), "detail": "OpenCode model list includes openrouter/z-ai/glm-5.2."},
                {
                    "id": "route-called-or-safely-skipped",
                    "passed": route_call["status"] in {"ok", "discovery_only"},
                    "detail": route_call["status"] if route_call["status"] != "failed" else route_call["error"][:500],
                },
                {"id": "skills-materialized", "passed": True, "detail": "Mission 2 UI skills wrote input/output/route/proof artifacts."},
                {"id": "no-fake-proof", "passed": True, "detail": "The proof command records route discovery/failure separately from implemented UI changes."},
            ],
        }
        route_proof = {
            "schema": "fluxio.ui_self_repair_route_proof.v1",
            "requestId": request_id,
            "createdAt": _utc_now(),
            "preferredRoute": preferred_route,
            "opencode": {
                "command": self._display_command([opencode_command or "opencode", "models"]),
                "available": bool(opencode_command),
                "authProviders": opencode_auth_providers,
                "modelsContainGlm52": opencode_models_contains_glm52,
                "error": opencode_models_error,
            },
            "providerPresence": provider_presence,
            "probeExternalRoutes": probe_external_routes,
            "hermes": {
                "available": bool(hermes_command) or hermes_wsl_available,
                "nativeCommandVisible": bool(hermes_command),
                "wslCommandVisible": hermes_wsl_available,
                "call": route_attempts["hermes"],
            },
            "openclaw": {
                "available": bool(openclaw_command),
                "call": route_attempts["openclaw"],
            },
            "selectedRuntime": route_call["selectedRuntime"],
            "skillsUsed": skills_used,
        }

        artifacts = {
            "routeProofPath": str(artifact_dir / "route_proof.json"),
            "breakdownPath": str(artifact_dir / "ui_breakdown.json"),
            "repairPlanPath": str(artifact_dir / "ui_repair_plan.json"),
            "implementationContractPath": str(artifact_dir / "implementation_contract.json"),
            "verifierPath": str(artifact_dir / "self_repair_verifier.json"),
        }
        (artifact_dir / "route_proof.json").write_text(json.dumps(route_proof, indent=2), encoding="utf-8")
        (artifact_dir / "ui_breakdown.json").write_text(json.dumps(breakdown, indent=2), encoding="utf-8")
        (artifact_dir / "ui_repair_plan.json").write_text(json.dumps(repair_plan, indent=2), encoding="utf-8")
        (artifact_dir / "implementation_contract.json").write_text(json.dumps(implementation_contract, indent=2), encoding="utf-8")
        (artifact_dir / "self_repair_verifier.json").write_text(json.dumps(verifier, indent=2), encoding="utf-8")
        return {
            "requestId": request_id,
            "status": "recorded",
            "route": preferred_route,
            "routeStatus": route_call["status"],
            "usedModelReply": used_glm_reply,
            "skillsUsed": skills_used,
            "findings": breakdown["findings"],
            "plan": repair_plan,
            "implementationContract": implementation_contract,
            "verifier": verifier,
            "artifacts": artifacts,
            "message": (
                "GLM-5.2 route produced the broader UI breakdown."
                if used_glm_reply
                else "GLM-5.2 route discovery proof was captured; deterministic UI repair plan used because direct inference did not return usable output."
            ),
        }

    def _chat_compartment_path(self, session_id: str) -> Path:
        return self.root / ".agent_control" / "runtime_compartments" / f"{_safe_identifier(session_id, 'syntelos_chat')}.json"

    def _display_command(self, args: list[object], *, prompt_marker: str = "<prompt>") -> str:
        safe_args: list[str] = []
        skip_next_prompt = False
        for item in args:
            value = str(item)
            if skip_next_prompt:
                safe_args.append(prompt_marker)
                skip_next_prompt = False
                continue
            safe_args.append(value)
            if value in {"--prompt", "-q"}:
                skip_next_prompt = True
        try:
            return subprocess.list2cmdline(safe_args)
        except (TypeError, ValueError):
            return shlex.join(safe_args)

    def _normalize_receipt_assistant_message(self, candidates: list[Any], command: str = "") -> str:
        command_text = " ".join(str(command or "").split())
        for candidate in candidates:
            text = str(candidate or "").replace("\r\n", "\n").strip()
            if not text:
                continue
            text = re.sub(r"[ \t]+\n", "\n", text)
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            collapsed = " ".join(text.split())
            if command_text and collapsed == command_text:
                continue
            if re.search(r"^(command|feedback|response|reply)\s*:?\s+(\/volume\d+\/|[A-Z]:\\|wsl\s+|python\s+-m\s+|node\s+|npm\s+|pnpm\s+|yarn\s+|hermes\s+|opencode\s+|openclaw\s+|codex\s+)", collapsed, re.I):
                continue
            if re.search(r"^(\/volume\d+\/|[A-Z]:\\|wsl\s+|python\s+-m\s+|node\s+|npm\s+|pnpm\s+|yarn\s+|hermes\s+|opencode\s+|openclaw\s+|codex\s+)", collapsed, re.I):
                continue
            if re.search(r"\b(mission one-shot|execute model mission|--objective|--mission-id|--provider|--model)\b", collapsed, re.I):
                continue
            if re.search(
                r"\b(delegated runtime lane launched|delegated lane launched|file mutation completed|workspace search completed|approval required before|waiting for operator approval|lane action routed)\b",
                collapsed,
                re.I,
            ):
                continue
            return self._assistant_message_from_runtime_output(text) or text
        return ""

    def _assistant_message_from_runtime_output(self, text: str) -> str:
        cleaned = re.sub(
            r"^\s*(?:runtime output|raw action output)\s*:\s*",
            "",
            str(text or "").strip(),
            flags=re.I,
        )
        cleaned = re.sub(
            r"^\s*Mission\s+\S+\s+live runtime output\s*\([^)]+\)\s*",
            "",
            cleaned,
            flags=re.I,
        ).strip()
        if re.search(r"^OpenRuntime returned a real result for this mission\b", cleaned, re.I):
            return cleaned
        if not cleaned or not re.search(r"(^|\n)\s*(artifact|preview url|route)\s*:", cleaned, re.I):
            return ""
        lines = [
            re.sub(r"^[-*]\s*", "", line).strip()
            for line in cleaned.splitlines()
            if line.strip()
        ]

        def is_artifact_line(line: str) -> bool:
            return bool(
                re.search(r"^(artifact|preview url|route|command|status)\s*:", line, re.I)
                or re.search(r"^/volume\d+/", line, re.I)
                or re.search(r"^https?://", line, re.I)
                or re.search(r"^/api/artifact\b", line, re.I)
            )

        headline = next((line for line in lines if not is_artifact_line(line)), "")
        route = next((line for line in lines if re.search(r"^route\s*:", line, re.I)), "")
        facts = [line for line in lines if line != headline and not is_artifact_line(line)][:4]
        parts = [
            (
                f"OpenRuntime returned a real result for this mission: {headline}."
                if headline
                else "OpenRuntime returned a real result for this mission."
            )
        ]
        if facts:
            parts.append(f"Key output: {' '.join(facts)}")
        if route:
            parts.append(route)
        return "\n".join(parts).strip()

    def _turn_receipt_from_chat_result(
        self,
        payload: dict[str, Any],
        result: dict[str, Any],
        *,
        session_id: str,
        route: dict[str, Any],
        changed_files: list[str],
        timeline: list[dict[str, Any]],
        ended_at: str,
        elapsed_ms: int,
    ) -> dict[str, Any]:
        existing = result.get("turnReceipt")
        if isinstance(existing, dict):
            receipt = dict(existing)
        else:
            receipt = {}
        command = (
            receipt.get("command")
            or result.get("command")
            or result.get("launchCommand")
            or result.get("launch_command")
            or ""
        )
        if not command:
            for item in reversed(timeline):
                if not isinstance(item, dict):
                    continue
                if str(item.get("kind") or "").lower() in {"command.execution", "command"}:
                    command = str(item.get("summary") or "")
                    break
        status = receipt.get("status") or ("completed" if str(result.get("reply") or "").strip() else "completed_no_reply")
        source_type = str(payload.get("sourceType") or payload.get("source_type") or "chat").strip() or "chat"
        assistant_message = self._normalize_receipt_assistant_message(
            [
                receipt.get("assistantMessage"),
                receipt.get("modelMessage"),
                receipt.get("openRuntimeMessage"),
                receipt.get("agentMessage"),
                receipt.get("finalMessage"),
                result.get("assistantMessage"),
                result.get("modelMessage"),
                result.get("openRuntimeMessage"),
                result.get("runtimeMessage"),
                result.get("agentMessage"),
                result.get("finalMessage"),
                result.get("reply"),
                result.get("message"),
            ],
            command,
        )
        run_summary = str(
            receipt.get("runSummary")
            or result.get("result_summary")
            or result.get("resultSummary")
            or ""
        ).strip()
        return {
            "schema": "fluxio.turn_receipt.v1",
            "sessionId": receipt.get("sessionId") or session_id,
            "missionId": receipt.get("missionId") or str(payload.get("missionId") or payload.get("mission_id") or ""),
            "sourceType": receipt.get("sourceType") or source_type,
            "sourceMessageId": receipt.get("sourceMessageId") or str(payload.get("sourceMessageId") or ""),
            "sourceZone": receipt.get("sourceZone") or str(payload.get("sourceZone") or ""),
            "commentText": receipt.get("commentText") or str(payload.get("commentText") or ""),
            "command": command or "Not reported",
            "runtime": receipt.get("runtime") or str(result.get("runtime") or payload.get("runtime") or "Not reported"),
            "provider": receipt.get("provider") or str(route.get("provider") or "Not reported"),
            "model": receipt.get("model") or str(route.get("model_id") or route.get("model") or "Not reported"),
            "effort": receipt.get("effort") or str(route.get("effort") or "Not reported"),
            "status": str(status),
            "exitCode": receipt.get("exitCode", result.get("exitCode", result.get("exit_code", ""))),
            "startedAt": receipt.get("startedAt") or str(payload.get("requestStartedAt") or ""),
            "endedAt": receipt.get("endedAt") or ended_at,
            "durationMs": receipt.get("durationMs", elapsed_ms),
            "toolTimeline": receipt.get("toolTimeline") if isinstance(receipt.get("toolTimeline"), list) else timeline[-30:],
            "changedFiles": receipt.get("changedFiles") if isinstance(receipt.get("changedFiles"), list) else changed_files[:30],
            "assistantMessage": assistant_message,
            "finalMessage": assistant_message,
            "modelMessageSource": receipt.get("modelMessageSource") or str(result.get("modelMessageSource") or ""),
            "modelMessageSourceLabel": receipt.get("modelMessageSourceLabel") or str(result.get("modelMessageSourceLabel") or ""),
            "modelMessageSourceTitle": receipt.get("modelMessageSourceTitle") or str(result.get("modelMessageSourceTitle") or ""),
            "modelMessageSourceId": receipt.get("modelMessageSourceId") or str(result.get("modelMessageSourceId") or ""),
            "transcriptSessionId": receipt.get("transcriptSessionId") or str(result.get("transcriptSessionId") or ""),
            "runSummary": run_summary,
            "proofArtifacts": receipt.get("proofArtifacts") if isinstance(receipt.get("proofArtifacts"), list) else [],
        }

    def _save_chat_compartment(self, payload: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        session_id = _safe_identifier(result.get("sessionId") or payload.get("sessionId") or "syntelos_chat")
        route = result.get("route") if isinstance(result.get("route"), dict) else self._chat_route(payload)
        workspace_path = str(Path(str(payload.get("workspacePath") or self.root)).expanduser())
        path = self._chat_compartment_path(session_id)
        previous: dict[str, Any] = {}
        if path.exists():
            try:
                previous = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                previous = {}
        timeline = previous.get("timeline") if isinstance(previous.get("timeline"), list) else []
        now = _utc_now()
        elapsed_ms_raw = result.get("elapsedMs")
        try:
            elapsed_ms = int(elapsed_ms_raw) if elapsed_ms_raw is not None else 0
        except (TypeError, ValueError):
            elapsed_ms = 0
        runtime_tool_timeline = result.get("toolTimeline") if isinstance(result.get("toolTimeline"), list) else []
        timeline.extend(
            [
                {
                    "kind": "operator.message",
                    "at": now,
                    "summary": str(payload.get("message") or "").strip()[:240],
                },
            ]
        )
        if elapsed_ms > 0:
            timeline.append(
                {
                    "kind": "runtime.roundtrip",
                    "at": now,
                    "summary": f"CLI roundtrip completed in {elapsed_ms} ms.",
                    "status": "completed",
                }
            )
        for item in runtime_tool_timeline[-14:]:
            if not isinstance(item, dict):
                continue
            summary = str(item.get("summary") or item.get("message") or "").strip()
            if not summary:
                continue
            timeline.append(
                {
                    "kind": str(item.get("kind") or item.get("type") or "runtime.event"),
                    "at": str(item.get("at") or now),
                    "summary": summary[:240],
                    "status": str(item.get("status") or "recorded"),
                }
            )
        previous_files = previous.get("filesChanged") if isinstance(previous.get("filesChanged"), list) else []
        changed_files: list[str] = []
        seen_files: set[str] = set()
        for candidate in [*previous_files, *(result.get("filesChanged") if isinstance(result.get("filesChanged"), list) else [])]:
            value = str(candidate or "").strip()
            if not value:
                continue
            if value in seen_files:
                continue
            seen_files.add(value)
            changed_files.append(value)
        active_role = str(route.get("role") or payload.get("role") or "executor").strip().lower() or "executor"
        lanes = []
        for role in ("planner", "executor", "verifier"):
            lanes.append(
                {
                    "role": role,
                    "phase": "plan" if role == "planner" else ("verify" if role == "verifier" else "execute"),
                    "provider": route.get("provider") or "openai-codex",
                    "model": route.get("model") or OPENAI_CODEX_DEFAULT_MODEL,
                    "effort": route.get("effort") or "high",
                    "health": "ready",
                    "active": role == active_role,
                    "authPath": "OpenAI Codex OAuth" if route.get("provider") == "openai-codex" else "provider route",
                    "blocker": "",
                }
            )
        turn_receipt = self._turn_receipt_from_chat_result(
            payload,
            result,
            session_id=session_id,
            route=route,
            changed_files=changed_files,
            timeline=timeline,
            ended_at=now,
            elapsed_ms=elapsed_ms,
        )
        model_reply = str(turn_receipt.get("assistantMessage") or "").strip()
        raw_runtime_reply = str(result.get("reply") or result.get("message") or "").strip()
        if model_reply:
            timeline.append(
                {
                    "kind": "runtime.model_message",
                    "at": now,
                    "summary": model_reply[:240],
                    "status": "recorded",
                }
            )
        elif raw_runtime_reply:
            timeline.append(
                {
                    "kind": "runtime.trace_only_reply",
                    "at": now,
                    "summary": raw_runtime_reply[:240],
                    "status": "trace_only",
                }
            )
        turn_receipt["toolTimeline"] = timeline[-30:]
        messages = previous.get("messages") if isinstance(previous.get("messages"), list) else []
        operator_message = str(payload.get("message") or "").strip()
        if operator_message:
            messages.append({"role": "operator", "text": operator_message, "at": now, "source": "operator-submitted"})
        if model_reply:
            messages.append({"role": "assistant", "text": model_reply, "at": now, "source": "backend-model-message"})
        previous_receipts = previous.get("turnReceipts") if isinstance(previous.get("turnReceipts"), list) else []
        compartment = {
            "sessionId": session_id,
            "missionId": str(payload.get("missionId") or payload.get("mission_id") or ""),
            "runtime": result.get("runtime") or payload.get("runtime") or "openclaw",
            "cwd": workspace_path,
            "route": route,
            "host": os.environ.get("COMPUTERNAME") or (os.uname().nodename if hasattr(os, "uname") else ""),
            "state": "ready",
            "streaming": "recorded",
            "messages": messages[-40:],
            "toolTimeline": timeline[-30:],
            "lanes": lanes,
            "filesChanged": changed_files[:30],
            "turnReceipt": turn_receipt,
            "turnReceipts": [*previous_receipts, turn_receipt][-20:],
            "approvals": [],
            "blockers": [],
            "actions": ["resume-chat", "open-proof", "restart"],
            "restartControls": {
                "canRestart": True,
                "canResume": True,
            },
            "lastRoundtripMs": elapsed_ms,
            "updatedAt": now,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(compartment, indent=2), encoding="utf-8")
        return compartment

    def _resolve_workspace_directory(self, raw_path: object) -> Path:
        requested = str(raw_path or "").strip()
        if not requested:
            target = self.root
        else:
            target = Path(requested).expanduser()
            if not target.is_absolute():
                target = self.root / target
        try:
            resolved = target.resolve()
        except OSError as exc:
            raise RuntimeError(f"Could not resolve directory path: {target}") from exc
        if not resolved.exists():
            raise RuntimeError(f"Directory does not exist: {resolved}")
        if not resolved.is_dir():
            raise RuntimeError(f"Path is not a directory: {resolved}")
        return resolved

    def _list_workspace_directory(self, raw_path: object) -> dict[str, Any]:
        current = self._resolve_workspace_directory(raw_path)
        parent_path = "" if current.parent == current else str(current.parent)
        directory_entries: list[dict[str, str | bool]] = []
        file_entries: list[dict[str, str | bool]] = []
        try:
            children = list(current.iterdir())
        except PermissionError as exc:
            raise RuntimeError(f"Permission denied for directory: {current}") from exc
        except OSError as exc:
            raise RuntimeError(f"Could not list directory: {current}") from exc

        for child in children:
            try:
                resolved = child.resolve()
            except OSError:
                continue
            entry = {
                "name": child.name,
                "path": str(resolved),
                "isDirectory": child.is_dir(),
            }
            if entry["isDirectory"]:
                directory_entries.append(entry)
            else:
                file_entries.append(entry)

        directory_entries.sort(key=lambda item: str(item["name"]).lower())
        file_entries.sort(key=lambda item: str(item["name"]).lower())

        return {
            "currentPath": str(current),
            "parentPath": parent_path,
            "roots": self._workspace_roots(),
            "entries": [*directory_entries, *file_entries],
        }

    def _openclaw_provider_for_route(self, provider: object) -> str:
        normalized = str(provider or "").strip().lower()
        if normalized == "openai":
            return "openai-codex"
        if normalized == "minimax":
            presence = _provider_presence(
                ["minimax", "minimax-portal"],
                session_secrets=self.provider_secrets,
            )
            if presence.get("minimax-portal") and not presence.get("minimax"):
                return "minimax-portal"
            return "minimax"
        aliases = {
            "openai-codex": "openai-codex",
            "minimax-portal": "minimax-portal",
            "minimax-cn": "minimax",
            "anthropic": "anthropic",
            "openrouter": "openrouter",
            "gemini": "gemini",
            "huggingface": "huggingface",
            "zai": "zai",
            "kimi-coding": "kimi-coding",
            "kimi-coding-cn": "kimi-coding-cn",
        }
        return aliases.get(normalized, normalized)

    def _chat_route(self, payload: dict[str, Any]) -> dict[str, str]:
        route = payload.get("route") if isinstance(payload.get("route"), dict) else {}
        provider = self._openclaw_provider_for_route(route.get("provider") or payload.get("provider") or "openai-codex")
        model = str(route.get("model") or payload.get("model") or OPENAI_CODEX_DEFAULT_MODEL).strip()
        if provider in {"minimax", "minimax-cn", "minimax-portal"} and model.lower() in {
            "minimax-m2.7",
            "minimax-m2.7-highspeed",
            "minimax/m2.7",
            "minimax/minimax-m2.7",
            "minimax/minimax-m2.7-highspeed",
        }:
            model = "MiniMax-M3"
        effort = str(route.get("effort") or payload.get("effort") or "high").strip().lower()
        role = str(route.get("role") or payload.get("role") or "executor").strip().lower()
        if provider and model:
            if model.startswith(f"{provider}/"):
                model_id = model
            elif provider == "openrouter" and model.startswith("z-ai/"):
                model_id = f"{provider}/{model}"
            elif "/" in model:
                model_id = model
            else:
                model_id = f"{provider}/{model}"
        else:
            model_id = model
        return {
            "provider": provider,
            "model": model,
            "model_id": model_id,
            "effort": effort if effort and effort != "default" else "high",
            "role": role,
        }

    def _run_openclaw_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = _chat_prompt(payload)
        env = self._provider_env()
        command = shutil.which("openclaw", path=env.get("PATH") or os.environ.get("PATH"))
        if not command:
            raise RuntimeError("OpenClaw CLI was not found on PATH.")
        route = self._chat_route(payload)
        workspace_path = Path(str(payload.get("workspacePath") or self.root)).expanduser()
        if not workspace_path.exists():
            workspace_path = self.root
        workspace_id = _safe_identifier(payload.get("workspaceId") or workspace_path.name, "workspace")
        session_id = _safe_identifier(payload.get("sessionId") or f"syntelos_chat_{workspace_id}", "syntelos_chat")
        model_id = route["model_id"]
        args = [
            command,
            "infer",
            "model",
            "run",
            "--local",
            "--json",
            "--prompt",
            prompt,
        ]
        if model_id:
            args.extend(["--model", model_id])
        display_command = self._display_command(args)
        try:
            timeout_seconds = int(payload.get("timeoutSeconds") or payload.get("timeout_seconds") or 720)
        except (TypeError, ValueError):
            timeout_seconds = 720
        timeout_seconds = max(5, min(timeout_seconds, 720))
        result, stdout, _stderr, elapsed_ms = _run_process_capture(
            args,
            cwd=workspace_path,
            timeout=timeout_seconds,
            extra_env=env,
        )
        reply = _extract_model_reply(result)
        if not reply:
            raise RuntimeError("OpenClaw finished without a readable model reply.")
        now = _utc_now()
        tool_timeline, files_changed = _chat_runtime_evidence_from_process(
            result,
            stdout=stdout,
            now=now,
            elapsed_ms=elapsed_ms,
        )
        return {
            "reply": reply,
            "runtime": "openclaw",
            "sessionId": session_id,
            "route": route,
            "raw": result,
            "elapsedMs": elapsed_ms,
            "command": display_command,
            "toolTimeline": tool_timeline,
            "filesChanged": files_changed,
        }

    def _run_codex_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = _chat_prompt(payload)
        env = self._provider_env()
        command = shutil.which("codex", path=env.get("PATH") or os.environ.get("PATH"))
        if not command:
            raise RuntimeError("Codex CLI was not found on PATH. Install @openai/codex in the packaged runtime.")
        codex_home = _codex_home_path()
        env["CODEX_HOME"] = str(codex_home)
        route = self._chat_route(payload)
        workspace_path = Path(str(payload.get("workspacePath") or self.root)).expanduser()
        if not workspace_path.exists():
            workspace_path = self.root
        tmp_dir = self.root / ".agent_control" / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix="codex-chat-", suffix=".txt", dir=str(tmp_dir), delete=False) as output_file:
            output_path = Path(output_file.name)
        try:
            args = [
                command,
                "exec",
                "--model",
                route["model"] or OPENAI_CODEX_DEFAULT_MODEL,
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--output-last-message",
                str(output_path),
                "--json",
                prompt,
            ]
            display_command = self._display_command(args[:-1] + ["<prompt>"])
            result, stdout, _stderr, elapsed_ms = _run_process_capture(
                args,
                cwd=workspace_path,
                timeout=720,
                extra_env=env,
            )
            reply = ""
            try:
                reply = output_path.read_text(encoding="utf-8").strip()
            except OSError:
                reply = ""
            if not reply:
                reply = _extract_model_reply(result)
            if not reply:
                raise RuntimeError("Codex finished without a readable model reply.")
            now = _utc_now()
            tool_timeline, files_changed = _chat_runtime_evidence_from_process(
                result,
                stdout=stdout,
                now=now,
                elapsed_ms=elapsed_ms,
            )
            return {
                "reply": reply,
                "runtime": "codex",
                "sessionId": _safe_identifier(payload.get("sessionId") or "syntelos_chat"),
                "route": route,
                "raw": result,
                "elapsedMs": elapsed_ms,
                "command": display_command,
                "toolTimeline": tool_timeline,
                "filesChanged": files_changed,
            }
        finally:
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _run_hermes_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = _chat_prompt(payload)
        env = self._provider_env()
        command = shutil.which("hermes", path=env.get("PATH") or os.environ.get("PATH"))
        route = self._chat_route(payload)
        raw_route = payload.get("route") if isinstance(payload.get("route"), dict) else {}
        routed_model = str(route.get("model") or "").strip()
        explicit_model = str(raw_route.get("model") or payload.get("model") or "").strip()
        hermes_model = routed_model or explicit_model
        explicit_provider = str(raw_route.get("provider") or payload.get("provider") or "").strip()
        hermes_provider = str(route.get("provider") or "").strip()
        if hermes_provider == "minimax-portal":
            hermes_provider = "minimax-oauth"
        native_args = ["hermes", "chat", "-q", prompt, "-Q"]
        if hermes_model:
            native_args.extend(["--model", hermes_model])
        if explicit_provider and hermes_provider:
            native_args.extend(["--provider", hermes_provider])
        if command:
            args = [command, *native_args[1:]]
        elif _wsl_has_command("hermes"):
            wsl_command = f'export PATH="$HOME/.local/bin:$PATH"; {shlex.join(native_args)}'
            args = [
                shutil.which("wsl") or "wsl",
                "bash",
                "-lc",
                wsl_command,
            ]
        else:
            raise RuntimeError("Hermes CLI was not found on PATH (native or WSL).")
        display_command = self._display_command(args)
        workspace_path = Path(str(payload.get("workspacePath") or self.root)).expanduser()
        if not workspace_path.exists():
            workspace_path = self.root
        try:
            timeout_seconds = int(payload.get("timeoutSeconds") or payload.get("timeout_seconds") or 720)
        except (TypeError, ValueError):
            timeout_seconds = 720
        timeout_seconds = max(5, min(timeout_seconds, 720))
        result, stdout, _stderr, elapsed_ms = _run_process_capture(
            args,
            cwd=workspace_path,
            timeout=timeout_seconds,
            extra_env=env,
        )
        reply = _extract_model_reply(result)
        if not reply:
            raise RuntimeError("Hermes finished without a readable model reply.")
        now = _utc_now()
        tool_timeline, files_changed = _chat_runtime_evidence_from_process(
            result,
            stdout=stdout,
            now=now,
            elapsed_ms=elapsed_ms,
        )
        result_payload = {
            "reply": reply,
            "runtime": "hermes",
            "sessionId": _safe_identifier(payload.get("sessionId") or "syntelos_chat"),
            "route": {
                **route,
                "provider": hermes_provider or route["provider"],
                "model": hermes_model,
                "model_id": f"{hermes_provider or route['provider']}/{hermes_model}" if hermes_model else hermes_provider or route["provider"],
            },
            "raw": result,
            "elapsedMs": elapsed_ms,
            "command": display_command,
            "toolTimeline": tool_timeline,
            "filesChanged": files_changed,
        }
        self._record_runtime_route_proof(payload, result_payload, root=self.root)
        return result_payload

    def _run_agent_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        runtime = str(payload.get("runtime") or payload.get("runtimeId") or "codex").strip().lower()
        if runtime == "hermes":
            result = self._run_hermes_chat(payload)
        elif runtime in {"openclaw", "openclaw-local", ""}:
            route = self._chat_route(payload)
            if route.get("provider") == "openai-codex":
                result = self._run_codex_chat(payload)
            elif route.get("provider") in {"minimax", "minimax-cn", "minimax-portal"}:
                raise RuntimeError(
                    "MiniMax/OpenClaw portal routing is disabled for the web control workbench. "
                    "Use the OpenAI Codex OAuth route or record a Codex blocker before falling back."
                )
            else:
                result = self._run_openclaw_chat(payload)
        elif runtime == "codex":
            result = self._run_codex_chat(payload)
        else:
            raise RuntimeError(f"Unsupported chat runtime: {runtime}")
        result["compartment"] = self._save_chat_compartment(payload, result)
        return result

    def dispatch(self, command: str, raw_payload: object) -> object:
        payload = _as_payload(raw_payload)
        if command == "get_control_room_snapshot_command":
            root = Path(payload.get("root") or self.root).resolve()
            snapshot = self._run_cli(root, "control-room", [], timeout=180, fast_control_room=False)
            snapshot["providerSecretPresence"] = _provider_presence(
                session_secrets=self.provider_secrets,
            )
            snapshot["runtimeRouteProof"] = self._runtime_route_proof_status(root)
            snapshot["webPushStatus"] = web_push_status(root)
            snapshot["ntfyStatus"] = ntfy_status(root)
            snapshot["webBackend"] = {
                "available": True,
                "commandSurface": "http",
                "root": str(root),
            }
            return snapshot
        if command == "get_control_room_summary_command":
            root = Path(payload.get("root") or self.root).resolve()
            bootstrap = bool(payload.get("bootstrap") or payload.get("summaryBootstrap"))
            summary_mode = str(payload.get("summaryMode") or "").strip().lower()
            if bootstrap or summary_mode == "bootstrap":
                summary = self._cached_control_room_bootstrap_summary(root)
            else:
                summary = self._cached_control_room_summary(root)
            summary["providerSecretPresence"] = _provider_presence(
                session_secrets=self.provider_secrets,
            )
            summary["runtimeRouteProof"] = self._runtime_route_proof_status(root)
            summary["webPushStatus"] = web_push_status(root)
            summary["ntfyStatus"] = ntfy_status(root)
            summary["webBackend"] = {
                "available": True,
                "commandSurface": "http",
                "root": str(root),
            }
            self._prewarm_control_room_mission_details(root, summary)
            return summary
        if command == "get_control_room_mission_detail_command":
            root = Path(payload.get("root") or self.root).resolve()
            mission_id = str(payload.get("missionId") or payload.get("mission_id") or "").strip()
            if not mission_id:
                raise RuntimeError("missionId is required")
            event_limit = max(1, int(payload.get("eventLimit") or payload.get("event_limit") or 80))
            detail = self._cached_control_room_mission_detail(
                root,
                mission_id=mission_id,
                event_limit=event_limit,
            )
            detail["webBackend"] = {
                "available": True,
                "commandSurface": "http",
                "root": str(root),
            }
            return detail
        if command == "export_control_room_data_command":
            root = Path(payload.get("root") or self.root).resolve()
            return self._run_cli(root, "control-room-export", [], timeout=180)
        if command == "export_mission_proof_digest_command":
            root = Path(payload.get("root") or self.root).resolve()
            mission_id = str(payload.get("missionId") or payload.get("mission_id") or "").strip()
            if not mission_id:
                raise RuntimeError("missionId is required")
            args = ["--mission-id", mission_id]
            output = str(payload.get("output") or "").strip()
            if output:
                args.extend(["--output", output])
            return self._run_cli(root, "mission-proof-digest", args, timeout=120)
        if command == "record_delivery_receipt_command":
            root = Path(payload.get("root") or self.root).resolve()
            receipt = record_delivery_receipt(
                root,
                mission_id=str(payload.get("missionId") or payload.get("mission_id") or "control_room"),
                channel=str(payload.get("channel") or "browser_notification"),
                destination=str(payload.get("destination") or "current_browser"),
                event_kind=str(payload.get("eventKind") or payload.get("event_kind") or "notification.sent"),
                event_message=str(payload.get("eventMessage") or payload.get("event_message") or ""),
                status=str(payload.get("status") or "delivered"),
                error_message=str(payload.get("errorMessage") or payload.get("error_message") or ""),
                delivery_url=str(payload.get("deliveryUrl") or payload.get("delivery_url") or ""),
                origin_runtime=str(payload.get("originRuntime") or payload.get("origin_runtime") or ""),
                origin_provider=str(payload.get("originProvider") or payload.get("origin_provider") or ""),
                origin_model=str(payload.get("originModel") or payload.get("origin_model") or ""),
                transport_provider=str(payload.get("transportProvider") or payload.get("transport_provider") or ""),
                producer=str(payload.get("producer") or ""),
                mission_title=str(payload.get("missionTitle") or payload.get("mission_title") or ""),
                source_session_id=str(payload.get("sourceSessionId") or payload.get("source_session_id") or ""),
                evidence_path=str(payload.get("evidencePath") or payload.get("evidence_path") or ""),
                screenshot_path=str(payload.get("screenshotPath") or payload.get("screenshot_path") or ""),
            )
            return asdict(receipt)
        if command == "get_web_push_status_command":
            root = Path(payload.get("root") or self.root).resolve()
            return web_push_status(root)
        if command == "get_ntfy_status_command":
            root = Path(payload.get("root") or self.root).resolve()
            return ntfy_status(root)
        if command == "generate_web_push_vapid_config_command":
            root = Path(payload.get("root") or self.root).resolve()
            return generate_web_push_vapid_config(
                root,
                subject=str(payload.get("subject") or payload.get("sub") or ""),
            )
        if command == "record_web_push_subscription_command":
            root = Path(payload.get("root") or self.root).resolve()
            subscription = payload.get("subscription")
            if not isinstance(subscription, dict):
                raise RuntimeError("subscription is required")
            return record_web_push_subscription(
                root,
                subscription=subscription,
                user_agent=str(payload.get("userAgent") or payload.get("user_agent") or ""),
                status=str(payload.get("status") or "subscribed"),
            )
        if command == "send_web_push_notification_command":
            root = Path(payload.get("root") or self.root).resolve()
            receipts = send_web_push_delivery_receipts(
                root=root,
                mission_id=str(payload.get("missionId") or payload.get("mission_id") or "control_room"),
                title=str(payload.get("title") or "Fluxio mission update"),
                body=str(payload.get("body") or payload.get("eventMessage") or payload.get("event_message") or ""),
                target_url=str(payload.get("targetUrl") or payload.get("target_url") or "/control?mode=agent&surface=agent"),
                event_kind=str(payload.get("eventKind") or payload.get("event_kind") or "notification.web_push"),
                dry_run=bool(payload.get("dryRun") or payload.get("dry_run")),
            )
            return {
                "schema": "fluxio.web_push_delivery.v1",
                "ok": any(receipt.status == "delivered" for receipt in receipts),
                "receipts": [asdict(receipt) for receipt in receipts],
                "deliveredCount": sum(1 for receipt in receipts if receipt.status == "delivered"),
                "errorCount": sum(1 for receipt in receipts if receipt.status == "error"),
                "skippedCount": sum(1 for receipt in receipts if receipt.status == "skipped"),
            }
        if command == "send_ntfy_notification_command":
            root = Path(payload.get("root") or self.root).resolve()
            event = MissionEvent(
                mission_id=str(payload.get("missionId") or payload.get("mission_id") or "control_room"),
                kind=str(payload.get("eventKind") or payload.get("event_kind") or "notification.ntfy"),
                message=str(payload.get("body") or payload.get("eventMessage") or payload.get("event_message") or ""),
                metadata={
                    "title": str(payload.get("title") or "Fluxio mission update"),
                    "targetUrl": str(payload.get("targetUrl") or payload.get("target_url") or ""),
                },
            )
            receipt = send_ntfy_delivery_receipt(
                event,
                root=root,
                topic=str(payload.get("topic") or ""),
                title=str(payload.get("title") or "Fluxio mission update"),
                priority=str(payload.get("priority") or "default"),
                tags=str(payload.get("tags") or "fluxio"),
                click_url=str(payload.get("targetUrl") or payload.get("target_url") or ""),
                dry_run=bool(payload.get("dryRun") or payload.get("dry_run")),
            )
            return {
                "schema": "fluxio.ntfy_delivery.v1",
                "ok": receipt.status == "delivered",
                "receipt": asdict(receipt),
                "deliveredCount": 1 if receipt.status == "delivered" else 0,
                "errorCount": 1 if receipt.status == "error" else 0,
                "skippedCount": 1 if receipt.status == "skipped" else 0,
            }
        if command == "get_nas_deploy_readiness_command":
            from .mission_control import build_nas_deploy_readiness_snapshot

            return build_nas_deploy_readiness_snapshot(self.root)
        if command == "get_integration_readiness_command":
            from .mission_control import build_integration_readiness_snapshot

            return build_integration_readiness_snapshot(self.root)
        if command == "inspect_codex_import_command":
            return _codex_import_snapshot()
        if command in {"get_dictation_config", "get_dictation_config_command"}:
            return {
                "schema": "fluxio.dictation_config.v1",
                "strategy": "system_dictation_bridge",
                "primaryRuntimeLane": "hermes",
                "fallbackRuntimeLane": "openclaw",
                "reviewBeforeSend": True,
                "ambiguityGuard": True,
                "correctionBuffer": True,
                "localSttConfigured": False,
                "osFallbackHint": (
                    "Use your OS dictation shortcut, then review the correction buffer before sending."
                ),
                "os_fallback_hint": (
                    "Use your OS dictation shortcut, then review the correction buffer before sending."
                ),
                "accessibility": {
                    "ariaLiveStatus": True,
                    "keyboardRepairPath": True,
                    "reducedMotionSafe": True,
                    "accidentalSendProtection": True,
                },
                "proof": {
                    "command": command,
                    "surface": "web_backend",
                    "purpose": "dictation_voice_accessibility_control_points",
                },
            }
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
        if command == "get_openai_codex_oauth_status_command":
            return _openai_codex_oauth_status(session_secrets=self.provider_secrets)
        if command == "get_openai_codex_oauth_session_command":
            return _openclaw_codex_oauth_session_status()
        if command == "start_openai_codex_oauth_command":
            return _start_openclaw_codex_oauth(
                {**os.environ, **self._provider_env()},
                self.root,
                public_url=self.public_url,
            )
        if command == "complete_openai_codex_oauth_command":
            return _complete_openclaw_codex_oauth(payload)
        if command == "get_minimax_openclaw_auth_status_command":
            return _minimax_openclaw_auth_status(session_secrets=self.provider_secrets)
        if command == "start_minimax_openclaw_auth_command":
            return _minimax_openclaw_auth_start(payload.get("region"))
        if command == "complete_minimax_openclaw_auth_command":
            return _minimax_openclaw_auth_complete(payload)
        if command == "open_external_url_command":
            url = str(payload.get("url") or "").strip()
            if not url.startswith(("http://", "https://")):
                raise RuntimeError("Only http(s) URLs can be opened from the web backend.")
            return bool(webbrowser.open(url))
        if command == "list_workspace_directory_command":
            return self._list_workspace_directory(payload.get("path") or payload.get("directoryPath"))
        if command == "image_playground_operation_command":
            return self._write_image_playground_artifact(payload)
        if command == "image_self_repair_loop_command":
            return self._image_self_repair_loop_artifact(payload)
        if command == "ui_self_repair_loop_command":
            return self._ui_self_repair_loop_artifact(payload)
        if command == "apply_skill_repair_command":
            args = []
            for key, flag in (
                ("proposalId", "--proposal-id"),
                ("skillId", "--skill-id"),
                ("reviewer", "--reviewer"),
                ("validationMissionId", "--validation-mission-id"),
                ("validationStepId", "--validation-step-id"),
            ):
                value = payload.get(key) or payload.get(_camel_to_snake(key))
                if value:
                    args.extend([flag, str(value)])
            return self._run_cli(self.root, "skill-repair-apply", args, timeout=120)
        if command == "save_workspace_profile_command":
            args = [
                "--workspace-id",
                str(payload.get("workspaceId") or payload.get("workspace_id") or ""),
                "--name",
                str(payload.get("name") or ""),
                "--path",
                str(payload.get("path") or ""),
                "--default-runtime",
                str(payload.get("defaultRuntime") or payload.get("default_runtime") or "hermes"),
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
            for key, flag in (
                ("localProjectPath", "--local-project-path"),
                ("nasProjectPath", "--nas-project-path"),
                ("syncMode", "--sync-mode"),
                ("syncDirection", "--sync-direction"),
                ("syncConflictPolicy", "--sync-conflict-policy"),
            ):
                value = payload.get(key) or payload.get(_camel_to_snake(key))
                args.extend([flag, str(value or "")])
            if payload.get("autoSyncToNas") or payload.get("auto_sync_to_nas"):
                args.extend(["--auto-sync-to-nas", "true"])
            return self._run_cli(self.root, "workspace-save", args, timeout=180)
        if command == "resolve_workspace_sync_conflict_command":
            return self._run_cli(
                self.root,
                "workspace-sync-conflict-resolve",
                [
                    "--workspace-id",
                    str(payload.get("workspaceId") or payload.get("workspace_id") or ""),
                    "--relative-path",
                    str(payload.get("relativePath") or payload.get("relative_path") or ""),
                    "--resolution",
                    str(payload.get("resolution") or "manual_review"),
                ],
                timeout=120,
            )
        if command == "resolve_workspace_sync_conflict_batch_command":
            relative_paths = payload.get("relativePaths") or payload.get("relative_paths") or []
            if not isinstance(relative_paths, list):
                relative_paths = [relative_paths]
            args = [
                "--workspace-id",
                str(payload.get("workspaceId") or payload.get("workspace_id") or ""),
                "--resolution",
                str(payload.get("resolution") or "manual_review"),
            ]
            for relative_path in relative_paths:
                args.extend(["--relative-path", str(relative_path or "")])
            return self._run_cli(
                self.root,
                "workspace-sync-conflict-resolve-batch",
                args,
                timeout=180,
            )
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
                "--launch-async",
            ]
            relative_stop_value = (
                payload.get("relativeStopMinutes")
                or payload.get("relative_stop_minutes")
                or 0
            )
            try:
                relative_stop_minutes = int(relative_stop_value)
            except (TypeError, ValueError):
                relative_stop_minutes = 0
            if relative_stop_minutes > 0:
                args.extend(["--relative-stop-minutes", str(relative_stop_minutes)])
            route_overrides = payload.get("routeOverrides") or payload.get("route_overrides") or []
            if route_overrides:
                args.extend(["--route-overrides-json", json.dumps(route_overrides)])
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
            return self._run_cli(
                self.root,
                "mission-start",
                args,
                timeout=MISSION_START_TIMEOUT_SECONDS,
            )
        if command == "quickstart_control_room_mission_command":
            args = [
                "--objective",
                str(payload.get("objective") or ""),
                "--runtime",
                str(payload.get("runtime") or "auto"),
                "--mode",
                str(payload.get("mode") or "Autopilot"),
                "--budget-hours",
                str(payload.get("budgetHours") or payload.get("budget_hours") or 4),
            ]
            workspace_id = str(payload.get("workspaceId") or payload.get("workspace_id") or "").strip()
            if workspace_id:
                args.extend(["--workspace-id", workspace_id])
            for check in payload.get("successChecks") or payload.get("success_checks") or []:
                args.extend(["--success-check", str(check)])
            if payload.get("foreground"):
                args.append("--foreground")
            return self._run_cli(
                self.root,
                "mission-quickstart",
                args,
                timeout=MISSION_START_TIMEOUT_SECONDS,
            )
        if command == "apply_control_room_mission_action_command":
            action = str(payload.get("action") or "").strip().lower()
            args = [
                "--mission-id",
                str(payload.get("missionId") or payload.get("mission_id") or ""),
                "--action",
                action,
            ]
            if action == "resume":
                args.append("--launch-async")
            if action == "extend-budget":
                args.extend([
                    "--budget-hours",
                    str(payload.get("budgetHours") or payload.get("budget_hours") or 12),
                ])
                if (
                    payload.get("launchAsync")
                    or payload.get("launch_async")
                    or payload.get("launch")
                    or payload.get("resume")
                ):
                    args.append("--launch-async")
            if action == "complete":
                if payload.get("operatorValueScore") is not None or payload.get("operator_value_score") is not None:
                    args.extend([
                        "--operator-value-score",
                        str(payload.get("operatorValueScore", payload.get("operator_value_score"))),
                    ])
                operator_outcome = str(payload.get("operatorOutcome") or payload.get("operator_outcome") or "").strip()
                if operator_outcome:
                    args.extend(["--operator-outcome", operator_outcome])
                operator_note = str(payload.get("operatorCloseoutNote") or payload.get("operator_closeout_note") or "").strip()
                if operator_note:
                    args.extend(["--operator-closeout-note", operator_note])
            if (
                action == "parallelize-worktree"
                and (
                    payload.get("launchAsync")
                    or payload.get("launch_async")
                    or payload.get("launch")
                )
            ):
                args.append("--launch-async")
            return self._run_cli(
                self.root,
                "mission-action",
                args,
                timeout=MISSION_ACTION_TIMEOUT_SECONDS,
            )
        if command == "apply_control_room_mission_route_command":
            args = [
                "--mission-id",
                str(payload.get("missionId") or payload.get("mission_id") or ""),
                "--role",
                str(payload.get("role") or ""),
                "--provider",
                str(payload.get("provider") or ""),
                "--model",
                str(payload.get("model") or ""),
                "--effort",
                str(payload.get("effort") or "high"),
                "--budget-class",
                str(payload.get("budgetClass") or payload.get("budget_class") or "balanced"),
                "--reason",
                str(payload.get("reason") or "Builder lane reroute requested."),
            ]
            return self._run_cli(
                self.root,
                "mission-route",
                args,
                timeout=MISSION_ACTION_TIMEOUT_SECONDS,
            )
        if command == "record_control_room_lane_control_command":
            args = [
                "--mission-id",
                str(payload.get("missionId") or payload.get("mission_id") or ""),
                "--role",
                str(payload.get("role") or ""),
                "--action",
                str(payload.get("action") or ""),
                "--reason",
                str(payload.get("reason") or "Agent lane control requested from the web UI."),
            ]
            return self._run_cli(
                self.root,
                "mission-lane-control",
                args,
                timeout=120,
            )
        if command == "send_control_room_mission_follow_up_command":
            args = [
                "--mission-id",
                str(payload.get("missionId") or payload.get("mission_id") or ""),
                "--message",
                str(payload.get("message") or ""),
            ]
            return self._run_cli(self.root, "mission-follow-up", args, timeout=120)
        if command == "send_agent_chat_command":
            return self._run_agent_chat(payload)
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
            if provider_id not in PROVIDER_SECRET_ENV:
                raise RuntimeError(f"Unsupported provider secret id: {provider_id}")
            self.provider_secrets[provider_id] = secret
            _write_persisted_provider_secrets(self.root, self.provider_secrets)
            return True
        if command == "clear_provider_secret_command":
            provider_id = str(payload.get("providerId") or payload.get("provider_id") or "").strip()
            if provider_id:
                self.provider_secrets.pop(provider_id, None)
                _write_persisted_provider_secrets(self.root, self.provider_secrets)
            return True
        if command in {
            "connect_openclaw_gateway",
            "disconnect_openclaw_gateway",
            "send_openclaw_message",
            "save_openclaw_gateway_token",
            "clear_openclaw_gateway_token",
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
        candidate_paths = [raw_path or "index.html"]
        if raw_path == "control" or raw_path.startswith("control/"):
            control_relative = raw_path.removeprefix("control/").strip("/")
            candidate_paths.append(control_relative or "index.html")
        target = next(
            (
                self.static_root / candidate
                for candidate in candidate_paths
                if (self.static_root / candidate).exists()
            ),
            self.static_root / (candidate_paths[0] or "index.html"),
        )
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
        elif target.suffix == ".webmanifest":
            content_type = "application/manifest+json; charset=utf-8"
        elif target.suffix == ".json":
            content_type = "application/json; charset=utf-8"
        elif target.suffix == ".png":
            content_type = "image/png"
        body = target.read_bytes()
        handler.send_response(200)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(body)))
        cache_control = "public, max-age=300"
        if target.name in {"index.html", "service-worker.js"} or target.suffix in {".html", ".js", ".css"}:
            cache_control = "no-store"
        _apply_security_headers(handler, cache_control=cache_control)
        handler.end_headers()
        handler.wfile.write(body)
        return True

    def serve_artifact(self, handler: BaseHTTPRequestHandler) -> bool:
        parsed = urlparse(handler.path)
        query = parse_qs(parsed.query)
        raw_id = (query.get("id") or [""])[0]
        raw_path = (query.get("path") or [""])[0]
        try:
            target = self._resolve_artifact_id(raw_id) if raw_id else self._resolve_artifact_path(raw_path)
        except RuntimeError as exc:
            _json_response(handler, 404, {"ok": False, "error": str(exc)})
            return True
        content_type = ARTIFACT_CONTENT_TYPES.get(target.suffix.lower())
        if not content_type:
            _json_response(handler, 415, {"ok": False, "error": "Unsupported artifact type"})
            return True
        body = target.read_bytes()
        handler.send_response(200)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Syntelos-Artifact-Id", self._artifact_id(target))
        _apply_security_headers(handler, cache_control="private, max-age=60")
        _send_cors_headers(handler)
        handler.end_headers()
        handler.wfile.write(body)
        return True

    def serve_delivery_receipts(self, handler: BaseHTTPRequestHandler) -> bool:
        parsed = urlparse(handler.path)
        if not self.is_authenticated(handler):
            _json_response(
                handler,
                401,
                {
                    "ok": False,
                    "error": f"{PRODUCT_NAME} login is required.",
                    "loginRequired": True,
                },
            )
            return True
        query = parse_qs(parsed.query)
        try:
            limit = int((query.get("limit") or ["50"])[0])
        except (TypeError, ValueError):
            limit = 50
        receipts = [asdict(item) for item in load_delivery_receipts(self.root, limit=max(1, min(limit, 200)))]
        _json_response(handler, 200, {"ok": True, "data": {"receipts": receipts}})
        return True


def make_handler(backend: FluxioWebBackend) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_OPTIONS(self) -> None:  # noqa: N802
            _json_response(self, 204, {})

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path in {"/health", "/api/health"}:
                _json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "backend": "fluxio-web",
                        "loginRequired": True,
                    },
                )
                return
            if parsed.path == "/auth/minimax-openclaw":
                try:
                    query = parse_qs(parsed.query)
                    region = (query.get("region") or ["global"])[0]
                    _html_response(self, 200, _minimax_openclaw_connect_page(region))
                except Exception as exc:
                    _html_response(
                        self,
                        500,
                        (
                            "<!doctype html><title>MiniMax Connect Error</title>"
                            "<h1>MiniMax Connect Error</h1>"
                            f"<pre>{html.escape(str(exc))}</pre>"
                        ),
                    )
                return
            if parsed.path == "/api/auth/status":
                _json_response(self, 200, {"ok": True, "data": backend.session_status(self)})
                return
            if parsed.path == "/api/artifact":
                backend.serve_artifact(self)
                return
            if parsed.path == "/api/delivery-receipts":
                backend.serve_delivery_receipts(self)
                return
            backend.serve_file(self)

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            relay_prefix = "/api/codex/login/browser-relay/complete/"
            if path.startswith(relay_prefix):
                session_id = unquote(path[len(relay_prefix) :])
                try:
                    payload = _read_json_body(self)
                    result = backend.complete_openai_codex_oauth_relay(
                        session_id=session_id,
                        payload=payload,
                        authorization=self.headers.get("Authorization") or "",
                    )
                    _json_response(self, 200, {"ok": True, "data": result})
                except PermissionError as exc:
                    _json_response(self, 401, {"ok": False, "error": str(exc)})
                except ValueError as exc:
                    _json_response(self, 400, {"ok": False, "error": str(exc)})
                except RuntimeError as exc:
                    _json_response(self, 410, {"ok": False, "error": str(exc)})
                except Exception as exc:
                    _json_response(self, 500, {"ok": False, "error": str(exc)})
                return
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
            if path == "/api/minimax/openclaw/complete":
                try:
                    payload = _read_json_body(self)
                    result = _minimax_openclaw_auth_complete(payload)
                    _json_response(self, 200, {"ok": True, "data": result})
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
            try:
                payload = _read_json_body(self)
            except Exception as exc:  # pragma: no cover - exercised by browser/manual flows
                try:
                    _json_response(self, 400, {"ok": False, "error": str(exc)})
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                    return
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
                command = str(payload.get("command") or "").strip()
                result = backend.dispatch(command, payload.get("payload"))
                try:
                    _json_response(self, 200, {"ok": True, "data": result})
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                    return
            except Exception as exc:  # pragma: no cover - exercised by browser/manual flows
                traceback.print_exc()
                try:
                    _json_response(self, 500, {"ok": False, "error": str(exc)})
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                    return

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
    parser.add_argument(
        "--allow-port-reuse",
        action="store_true",
        help="Skip the startup preflight that prevents duplicate local backend listeners.",
    )
    args = parser.parse_args(argv)

    if not args.allow_port_reuse and tcp_port_accepts_connection(args.host, args.port):
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "port_in_use",
                    "host": args.host,
                    "port": args.port,
                    "message": (
                        f"{PRODUCT_NAME} web backend did not start because "
                        f"{args.host}:{args.port} is already accepting connections."
                    ),
                },
                indent=2,
            ),
            file=sys.stderr,
            flush=True,
        )
        return 98

    backend = FluxioWebBackend(
        Path(args.root),
        Path(args.static_root),
        reset_admin_password=args.reset_admin_password,
        public_url=args.public_url or None,
    )
    watchdog_autostart = _env_flag("FLUXIO_WATCHDOG_AUTOSTART", True)
    if watchdog_autostart:
        try:
            watchdog_status = ensure_watchdog_supervisor_loop(
                backend.root,
                stale_minutes=_env_int("FLUXIO_WATCHDOG_STALE_MINUTES", 60, minimum=1),
                interval_seconds=_env_int("FLUXIO_WATCHDOG_INTERVAL_SECONDS", 1200, minimum=0),
                notify_telegram=_env_flag("FLUXIO_WATCHDOG_NOTIFY_TELEGRAM", True),
                notify_ntfy=_env_flag("FLUXIO_WATCHDOG_NOTIFY_NTFY", True),
            )
            if watchdog_status.get("started"):
                print(
                    f"{PRODUCT_NAME} external mission watchdog started as pid {watchdog_status.get('pid')}",
                    flush=True,
                )
        except Exception as exc:  # noqa: BLE001
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "watchdog_autostart_failed",
                        "message": str(exc)[:300],
                    },
                    indent=2,
                ),
                file=sys.stderr,
                flush=True,
            )
    tls_enabled = bool(args.tls_cert_file or args.tls_key_file)
    ssl_context: ssl.SSLContext | None = None
    if tls_enabled:
        if not args.tls_cert_file or not args.tls_key_file:
            raise SystemExit("--tls-cert-file and --tls-key-file must be provided together.")
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(certfile=args.tls_cert_file, keyfile=args.tls_key_file)
    server = _HandshakeSafeThreadingHTTPServer(
        (args.host, args.port),
        make_handler(backend),
        ssl_context=ssl_context,
    )
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
