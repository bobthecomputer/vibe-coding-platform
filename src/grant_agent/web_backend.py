from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
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
import time
import webbrowser
import zlib
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

from .mission_control import reconcile_provider_secret_presence
from .port_safety import tcp_port_accepts_connection
from .subprocess_utils import hidden_windows_subprocess_kwargs

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 47880
DEFAULT_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_NAME = "Fluxio"
ADMIN_CONFIG_RELATIVE_PATH = ".agent_control/grand_agent_web_admin.json"
ADMIN_PASSWORD_RELATIVE_PATH = ".agent_control/grand_agent_admin_password.txt"
MISSION_START_TIMEOUT_SECONDS = 1200
MISSION_ACTION_TIMEOUT_SECONDS = 1200
SESSION_COOKIE_NAME = "grand_agent_session"
ACCOUNT_ROLES = {"account", "operator", "admin"}
PASSWORD_ITERATIONS = 240_000
ARTIFACT_CONTENT_TYPES = {
    ".apng": "image/apng",
    ".avif": "image/avif",
    ".gif": "image/gif",
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
SYNTHETIC_LIVE_REVIEW_FRAME_PATHS = {
    "screenshots/latest.png",
    "screenshots/previous.png",
}
PROVIDER_ENV = {
    "openai": ("OPENAI_API_KEY",),
    "openai-codex": ("OPENAI_API_KEY", "FLUXIO_OPENAI_CODEX_OAUTH_PRESENT"),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "minimax": ("MINIMAX_API_KEY",),
    "minimax-cn": ("MINIMAX_API_KEY",),
    "minimax-portal": ("MINIMAX_OAUTH_TOKEN", "FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT"),
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


def _tail_text(value: str, limit: int = 800) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return _redact_process_text(text)
    return _redact_process_text(text[-limit:])


def _redact_process_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(
        r"(?i)(api[_-]?key|token|secret|password|authorization|bearer)(\s*[:=]\s*)([^\s\"']+)",
        r"\1\2[redacted]",
        text,
    )
    text = re.sub(r"(?i)\b(sk-[a-z0-9_-]{12,})\b", "[redacted-api-key]", text)
    text = re.sub(r"(?i)\b([a-z0-9_-]{20,}\.[a-z0-9_-]{20,}\.[a-z0-9_-]{20,})\b", "[redacted-token]", text)
    return text


def _process_evidence_from_capture(
    *,
    args: list[str],
    cwd: Path,
    payload: dict[str, Any],
    stdout: str,
    stderr: str,
    elapsed_ms: int,
    accepted_output_field: str,
) -> dict[str, Any]:
    return {
        "schemaVersion": "runtime-process-evidence.v1",
        "commandArgv": [str(item) for item in args],
        "resolvedRuntimeBinary": str(args[0] if args else ""),
        "cwd": str(cwd),
        "exitCode": 0,
        "elapsedMs": int(elapsed_ms or 0),
        "stdoutSha256": hashlib.sha256(str(stdout or "").encode("utf-8")).hexdigest(),
        "stderrSha256": hashlib.sha256(str(stderr or "").encode("utf-8")).hexdigest(),
        "stdoutTail": _tail_text(stdout),
        "stderrTail": _tail_text(stderr),
        "parsedJson": isinstance(payload, dict),
        "acceptedOutputField": accepted_output_field,
    }


def _valid_process_evidence(evidence: object) -> bool:
    if not isinstance(evidence, dict):
        return False
    command_argv = evidence.get("commandArgv")
    return (
        evidence.get("exitCode") == 0
        and isinstance(command_argv, list)
        and len(command_argv) > 0
        and bool(str(evidence.get("resolvedRuntimeBinary") or "").strip())
        and bool(str(evidence.get("acceptedOutputField") or "").strip())
    )


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
            [wsl, "bash", "-lc", f"command -v {shlex.quote(command_name)} >/dev/null 2>&1"],
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


def _extract_model_reply_with_source(payload: dict[str, Any]) -> tuple[str, str]:
    candidate_fields = [
        "reply",
        "text",
        "outputText",
        "output_text",
        "content",
        "message",
        "response",
        "assistant",
        "completion",
        "data",
        "output",
        "result",
        "value",
    ]

    def scan(value: object, source: str) -> tuple[str, str]:
        if isinstance(value, str) and value.strip():
            return value.strip(), source
        if isinstance(value, dict):
            nested = _extract_model_reply_with_source(value)
            if nested[0]:
                return nested[0], f"{source}.{nested[1]}" if source else nested[1]
        if isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, str) and item.strip():
                    return item.strip(), f"{source}[{index}]"
                if isinstance(item, dict):
                    nested = _extract_model_reply_with_source(item)
                    if nested[0]:
                        nested_source = f"{source}[{index}]"
                        return nested[0], f"{nested_source}.{nested[1]}" if nested[1] else nested_source
        return "", ""

    for field in candidate_fields:
        if field not in payload:
            continue
        reply, source = scan(payload.get(field), field)
        if reply:
            return reply, source
    choices = payload.get("choices")
    if isinstance(choices, list):
        for index, choice in enumerate(choices):
            if isinstance(choice, dict):
                reply, source = _extract_model_reply_with_source(choice)
                if reply:
                    return reply, f"choices[{index}].{source}" if source else f"choices[{index}]"
    messages = payload.get("messages")
    if isinstance(messages, list):
        for index, message in reversed(list(enumerate(messages))):
            if isinstance(message, dict):
                reply, source = _extract_model_reply_with_source(message)
                if reply:
                    return reply, f"messages[{index}].{source}" if source else f"messages[{index}]"
    for field, value in payload.items():
        if field in candidate_fields or field in {"choices", "messages"}:
            continue
        if isinstance(value, dict):
            reply, source = _extract_model_reply_with_source(value)
            if reply:
                return reply, f"{field}.{source}" if source else field
    return "", ""


def _extract_model_reply(payload: dict[str, Any]) -> str:
    return _extract_model_reply_with_source(payload)[0]


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
    minimax_oauth_file = Path.home() / ".minimax" / "oauth_creds.json"
    state_root = Path(os.environ.get("OPENCLAW_STATE_DIR", str(Path.home() / ".openclaw")))
    openclaw_auth_store = state_root / "agents" / "main" / "agent" / "auth-profiles.json"
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
        if provider_id == "openai-codex":
            present = present or _openclaw_auth_store_has_provider(openclaw_auth_store, "openai-codex")
        if provider_id == "minimax-portal":
            present = present or minimax_oauth_file.exists()
            present = present or _openclaw_auth_store_has_provider(openclaw_auth_store, "minimax-portal")
        output[provider_id] = present
    return output


def _openclaw_auth_store_has_provider(path: Path, provider_id: str) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    needle = provider_id.strip().lower()

    def visit(value: object) -> bool:
        if isinstance(value, dict):
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
    return {"profileId": profile_id, "region": region}


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
    credentials_path = Path.home() / ".minimax" / "oauth_creds.json"
    state_root = Path(os.environ.get("OPENCLAW_STATE_DIR", str(Path.home() / ".openclaw")))
    auth_store_path = state_root / "agents" / "main" / "agent" / "auth-profiles.json"
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
    return {
        "authenticated": authenticated,
        "providerId": "minimax-portal",
        "region": None,
        "expires": None,
        "credentialsPath": str(credentials_path),
        "authStorePath": str(auth_store_path),
        "source": source,
        "message": (
            "MiniMax OpenClaw OAuth credentials are visible to the web backend."
            if authenticated
            else "MiniMax OpenClaw OAuth is not visible to the web backend yet."
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
            "message": "MiniMax OpenClaw OAuth is already connected on this runtime.",
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
                "Run this OpenClaw command on the NAS or runtime host, then refresh Syntelos auth status."
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
            "MiniMax OpenClaw OAuth connected."
            if status.get("authenticated")
            else "MiniMax OAuth completed, but credentials are not visible yet."
        ),
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
        token = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else ""
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
        if self.provider_secrets.get("minimax-portal"):
            env["MINIMAX_OAUTH_TOKEN"] = self.provider_secrets["minimax-portal"]
        if _provider_presence(["minimax-portal"], session_secrets=self.provider_secrets).get("minimax-portal"):
            env["FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT"] = "1"
        return env

    def _live_review_receipt_dir(self) -> Path:
        return self.root / ".agent_control" / "live_review_receipts"

    def _load_live_review_receipts(self, limit: int = 25) -> list[dict[str, Any]]:
        receipt_dir = self._live_review_receipt_dir()
        if not receipt_dir.exists():
            return []
        receipts: list[dict[str, Any]] = []
        for path in sorted(receipt_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                receipts.append(payload)
            if len(receipts) >= limit:
                break
        return list(reversed(receipts))

    def _resolve_live_review_frame_path(self, raw_path: object) -> str:
        candidate = str(raw_path or "").strip()
        if not candidate:
            return ""
        normalized = candidate.replace("\\", "/")
        if normalized in SYNTHETIC_LIVE_REVIEW_FRAME_PATHS:
            return ""
        try:
            resolved = self._resolve_artifact_path(candidate)
        except RuntimeError:
            return ""
        content_type = ARTIFACT_CONTENT_TYPES.get(resolved.suffix.lower(), "")
        return str(resolved) if content_type.startswith("image/") else ""

    def _sanitize_live_review_visual_proof(
        self,
        visual_proof: dict[str, Any],
        screenshots: list[str],
        annotations: list[dict[str, Any]],
        task_context: dict[str, Any],
        route_context: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        proof = dict(visual_proof) if visual_proof else {}
        frame_path = self._resolve_live_review_frame_path(proof.get("framePath")) or (screenshots[0] if screenshots else "")
        has_real_frame = bool(frame_path)
        if not proof:
            proof = {
                "previewUrl": payload.get("previewUrl") or "",
                "annotationCount": len(annotations),
                "annotationIds": [
                    str(item.get("id") or "").strip()
                    for item in annotations
                    if str(item.get("id") or "").strip()
                ],
                "annotationSeverities": [
                    str(item.get("severity") or "").strip()
                    for item in annotations
                    if str(item.get("severity") or "").strip()
                ],
                "proofTarget": task_context.get("reviewTargetId") or "",
                "threadTarget": route_context.get("missionId") or "",
            }
        proof["framePath"] = frame_path
        proof["hasRealFrame"] = has_real_frame
        proof["frameStatus"] = "captured" if has_real_frame else "missing"
        if has_real_frame:
            proof.pop("frameMissingReason", None)
        else:
            proof["frameMissingReason"] = (
                str(proof.get("frameMissingReason") or "").strip()
                or "No real screenshot artifact could be resolved for this Live Review receipt."
            )
        return proof

    def _record_live_review_structured_feedback(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not payload:
            raise ValueError("Structured Live Review feedback payload is required.")
        event_id = _safe_identifier(
            payload.get("eventId")
            or payload.get("sourceEventId")
            or payload.get("selectedEventId")
            or f"live_review_{int(time.time())}",
            "live_review",
        )
        handoff_id = str(
            payload.get("plannerExecutorHandoffId")
            or f"live-review:{event_id}:{secrets.token_hex(4)}"
        ).strip()
        if not handoff_id:
            handoff_id = f"live-review:{event_id}:{secrets.token_hex(4)}"
        task_context = payload.get("taskContext") if isinstance(payload.get("taskContext"), dict) else {}
        route_context = payload.get("routeContext") if isinstance(payload.get("routeContext"), dict) else {}
        visual_proof = payload.get("visualProofPacket") if isinstance(payload.get("visualProofPacket"), dict) else {}
        proof_only = bool(payload.get("proofOnly"))
        screenshots = [
            resolved
            for resolved in (
                self._resolve_live_review_frame_path(item)
                for item in task_context.get("screenshots", [])
            )
            if resolved
        ] if isinstance(task_context.get("screenshots"), list) else []
        annotations = [
            item
            for item in task_context.get("annotations", [])
            if isinstance(item, dict)
        ] if isinstance(task_context.get("annotations"), list) else []
        visual_proof = self._sanitize_live_review_visual_proof(
            visual_proof,
            screenshots,
            annotations,
            task_context,
            route_context,
            payload,
        )
        proof_warnings = [] if visual_proof.get("hasRealFrame") else ["frame_evidence_missing"]
        now = _utc_now()
        receipt = {
            "receiptKind": "live_review_visual_proof" if proof_only else "live_review_structured_feedback",
            "proofOnly": proof_only,
            "eventId": event_id,
            "sourceEventId": _safe_identifier(payload.get("sourceEventId") or event_id, "live_review"),
            "plannerExecutorHandoffId": handoff_id,
            "status": "missing_frame" if proof_only and proof_warnings else "received",
            "timestamp": now,
            "source": str(payload.get("source") or "builder-live-review"),
            "proofWarnings": proof_warnings,
            "routeContext": route_context,
            "taskContext": {
                **task_context,
                "screenshots": screenshots,
                "annotations": annotations,
            },
            "visualProofPacket": visual_proof,
            "verifierFeedback": payload.get("verifierFeedback") if isinstance(payload.get("verifierFeedback"), dict) else {},
            "nextIdea": str(payload.get("nextIdea") or "").strip(),
        }
        receipt_dir = self._live_review_receipt_dir()
        receipt_dir.mkdir(parents=True, exist_ok=True)
        path = receipt_dir / f"{event_id}-{_safe_identifier(handoff_id, 'handoff')}.json"
        receipt["artifactPath"] = str(path)
        path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        return receipt

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

    def _artifact_allowed_roots(self) -> list[Path]:
        candidates = [
            self.root / ".agent_control" / "image_playground_artifacts",
            self.root / ".agent_control" / "generated_image_artifacts",
            self.root / ".agent_control" / "design_references",
            self.root / ".agent_control" / "runtime_compartments",
            self.root / ".agent_control" / "runtime_sessions",
            self.root / ".agent_control" / "live_review_receipts",
            self.root / ".agent_control" / "mission_async",
            self.root / ".agent_runs",
            self.root / "artifacts",
        ]
        if os.name == "nt":
            candidates.append(Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_control/design_references"))
            candidates.append(Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_control/runtime_sessions"))
            candidates.append(Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_control/live_review_receipts"))
            candidates.append(Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_control/mission_async"))
            candidates.append(Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_runs"))
            candidates.append(Path("C:/volume1/Saclay/projects/vibe-coding-platform/artifacts"))
        else:
            candidates.append(Path("/volume1/Saclay/projects/vibe-coding-platform/.agent_control/design_references"))
            candidates.append(Path("/volume1/Saclay/projects/vibe-coding-platform/.agent_control/runtime_sessions"))
            candidates.append(Path("/volume1/Saclay/projects/vibe-coding-platform/.agent_control/live_review_receipts"))
            candidates.append(Path("/volume1/Saclay/projects/vibe-coding-platform/.agent_control/mission_async"))
            candidates.append(Path("/volume1/Saclay/projects/vibe-coding-platform/.agent_runs"))
            candidates.append(Path("/volume1/Saclay/projects/vibe-coding-platform/artifacts"))
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
                candidates.append(Path("C:/volume1") / normalized.removeprefix("/volume1/"))
                if os.name != "nt":
                    candidates.append(Path("/mnt/c/volume1") / normalized.removeprefix("/volume1/"))
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
                    self.root / ".agent_control" / "runtime_compartments",
                    self.root / ".agent_control" / "runtime_sessions",
                    self.root / ".agent_control" / "live_review_receipts",
                    self.root / ".agent_control" / "mission_async",
                    self.root / ".agent_runs",
                    self.root / "artifacts",
                    Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_control/design_references"),
                    Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_control/runtime_sessions"),
                    Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_control/live_review_receipts"),
                    Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_control/mission_async"),
                    Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_runs"),
                    Path("C:/volume1/Saclay/projects/vibe-coding-platform/artifacts"),
                    Path("/volume1/Saclay/projects/vibe-coding-platform/artifacts"),
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

    def _image_generation_capability(self, payload: dict[str, Any]) -> dict[str, Any]:
        provider_id = self._image_provider_id(payload)
        artifact_dir = self.root / ".agent_control" / "design_references" / "codex_image_artifacts"
        checks: list[dict[str, Any]] = []

        def add_check(check_id: str, label: str, passed: bool, detail: str) -> None:
            checks.append(
                {
                    "checkId": check_id,
                    "label": label,
                    "passed": passed,
                    "detail": detail,
                }
            )

        provider_allowed = provider_id == IMAGE_PROVIDER_CODEX_SUBSCRIPTION_ID
        add_check(
            "provider_allowed",
            "Codex subscription image route",
            provider_allowed,
            (
                "Provider is the allowed Codex subscription GPT-Image-2 lane."
                if provider_allowed
                else f"Provider {provider_id or 'unknown'} is not enabled for real image runs."
            ),
        )

        allow_paid_api_fallback = bool(
            payload.get("allowPaidApiFallback") or payload.get("allow_paid_api_fallback")
        )
        codex_auth = _openai_codex_oauth_status(session_secrets=self.provider_secrets)
        codex_source = str(codex_auth.get("source") or "").strip().lower()
        codex_authenticated = bool(codex_auth.get("authenticated"))
        add_check(
            "codex_oauth",
            "OpenAI Codex OAuth",
            codex_authenticated,
            (
                f"Authenticated through {codex_source or 'configured Codex source'}."
                if codex_authenticated
                else "OpenAI Codex OAuth is not connected on this runtime."
            ),
        )
        paid_api_allowed = codex_source != "openai-api-key" or allow_paid_api_fallback
        add_check(
            "paid_api_fallback_policy",
            "Paid API fallback policy",
            paid_api_allowed,
            (
                "Codex subscription routing is not using a paid API-key fallback."
                if paid_api_allowed
                else "Paid OpenAI API-key routing is blocked for this image lane."
            ),
        )

        env = self._provider_env()
        openclaw_command = shutil.which("openclaw", path=env.get("PATH") or os.environ.get("PATH"))
        add_check(
            "openclaw_cli",
            "OpenClaw CLI",
            bool(openclaw_command),
            (
                f"OpenClaw CLI found at {openclaw_command}."
                if openclaw_command
                else "OpenClaw CLI was not found on PATH."
            ),
        )

        try:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            artifact_root_ready = artifact_dir.exists() and os.access(str(artifact_dir), os.W_OK)
            artifact_root_detail = f"Artifact root is writable: {artifact_dir}."
        except OSError as exc:
            artifact_root_ready = False
            artifact_root_detail = f"Artifact root is not writable: {artifact_dir}. {exc}"
        add_check(
            "artifact_root",
            "Safe artifact root",
            artifact_root_ready,
            artifact_root_detail,
        )

        blocked_reason = ""
        message = "Codex image generation capability is available."
        if not provider_allowed:
            blocked_reason = "provider_not_allowed"
            message = "Only GPT-Image-2 via Codex subscription is enabled for this workbench."
        elif not codex_authenticated:
            blocked_reason = "codex_auth_missing"
            message = "OpenAI Codex OAuth is not connected on this runtime."
        elif not paid_api_allowed:
            blocked_reason = "paid_api_fallback_blocked"
            message = "Paid OpenAI API-key routing is blocked for this image lane."
        elif not openclaw_command:
            blocked_reason = "openclaw_missing"
            message = "OpenClaw CLI was not found on PATH."
        elif not artifact_root_ready:
            blocked_reason = "artifact_root_unavailable"
            message = "The safe generated image artifact root is not writable."

        available = not blocked_reason
        return {
            "schemaVersion": "image-generation-capability.v1",
            "status": "available" if available else "unavailable",
            "providerStatus": "available" if available else "blocked",
            "provider": IMAGE_PROVIDER_CODEX_EXPECTED_PROVIDER,
            "providerId": IMAGE_PROVIDER_CODEX_SUBSCRIPTION_ID,
            "model": IMAGE_PROVIDER_CODEX_EXPECTED_MODEL,
            "route": "codex_subscription",
            "authMode": "codex subscription",
            "billingNote": "codex subscription",
            "runActionAvailable": available,
            "readyForRealRun": available,
            "blockedReason": blocked_reason,
            "message": message,
            "checks": checks,
            "artifactRoot": str(artifact_dir),
            "openclawCommand": str(openclaw_command or ""),
            "authStatus": codex_auth,
            "doesNotWriteImageFiles": True,
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

    def _chat_compartment_path(self, session_id: str) -> Path:
        return self.root / ".agent_control" / "runtime_compartments" / f"{_safe_identifier(session_id, 'syntelos_chat')}.json"

    def _chat_compartment_proof_path(self, session_id: str) -> Path:
        return (
            self.root
            / ".agent_control"
            / "runtime_compartment_proofs"
            / f"{_safe_identifier(session_id, 'syntelos_chat')}.proof.json"
        )

    def _build_chat_compartment_proof_receipt(
        self,
        *,
        session_id: str,
        compartment: dict[str, Any],
        proof_path: Path,
        elapsed_ms: int,
    ) -> dict[str, Any]:
        route = compartment.get("route") if isinstance(compartment.get("route"), dict) else {}
        timeline = compartment.get("toolTimeline") if isinstance(compartment.get("toolTimeline"), list) else []
        files_changed = (
            compartment.get("filesChanged") if isinstance(compartment.get("filesChanged"), list) else []
        )
        messages = compartment.get("messages") if isinstance(compartment.get("messages"), list) else []
        process_evidence = (
            compartment.get("processEvidence")
            if isinstance(compartment.get("processEvidence"), dict)
            else {}
        )
        intent_alignment = (
            compartment.get("intentAlignment")
            if isinstance(compartment.get("intentAlignment"), dict)
            else {}
        )
        live_model_call_recorded = (
            _valid_process_evidence(process_evidence)
            and any(item.get("role") == "assistant" for item in messages if isinstance(item, dict))
        )
        receipt = {
            "schemaVersion": "runtime-compartment-proof.v1",
            "receiptKind": "runtime_compartment_proof",
            "sessionId": session_id,
            "runtime": str(compartment.get("runtime") or ""),
            "cwd": str(compartment.get("cwd") or ""),
            "route": {
                "role": str(route.get("role") or ""),
                "provider": str(route.get("provider") or ""),
                "model": str(route.get("model") or ""),
                "effort": str(route.get("effort") or ""),
            },
            "summary": {
                "messageCount": len(messages),
                "timelineEventCount": len(timeline),
                "filesChangedCount": len(files_changed),
                "elapsedMs": elapsed_ms,
            },
            "proofSignals": {
                "hasRuntimeReply": any(item.get("role") == "assistant" for item in messages if isinstance(item, dict)),
                "hasRoute": bool(route.get("provider") and route.get("model")),
                "hasToolTimeline": len(timeline) > 0,
                "hasChangedFiles": len(files_changed) > 0,
                "hasProcessEvidence": _valid_process_evidence(process_evidence),
                "hasIntentAlignment": bool(intent_alignment),
            },
            "intentAlignment": intent_alignment,
            "processEvidence": process_evidence,
            "safety": {
                "liveModelCallRecorded": live_model_call_recorded,
                "runtimeAdapterAdded": False,
                "fusedRuntimeRole": "evidence_layer_not_runtime_adapter",
                "secretsIncluded": False,
            },
            "artifacts": {
                "compartmentPath": str(self._chat_compartment_path(session_id)),
                "proofPath": str(proof_path),
                "proofUrl": self._artifact_url(proof_path),
            },
            "createdAt": str(compartment.get("updatedAt") or _utc_now()),
        }
        return receipt

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
                {
                    "kind": "runtime.reply",
                    "at": now,
                    "summary": str(result.get("reply") or "").strip()[:240],
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
        messages = previous.get("messages") if isinstance(previous.get("messages"), list) else []
        operator_message = str(payload.get("message") or "").strip()
        runtime_reply = str(result.get("reply") or "").strip()
        if operator_message:
            messages.append({"role": "operator", "text": operator_message, "at": now})
        if runtime_reply:
            messages.append({"role": "assistant", "text": runtime_reply, "at": now})
        process_evidence = (
            result.get("processEvidence") if isinstance(result.get("processEvidence"), dict) else {}
        )
        process_backed_reply = bool(runtime_reply and _valid_process_evidence(process_evidence))
        raw_intent_alignment = (
            result.get("intentAlignment")
            if isinstance(result.get("intentAlignment"), dict)
            else payload.get("intentAlignment")
            if isinstance(payload.get("intentAlignment"), dict)
            else {}
        )
        if raw_intent_alignment:
            intent_alignment = {
                "schemaVersion": str(raw_intent_alignment.get("schemaVersion") or "mission-intent-alignment.v1"),
                "status": str(raw_intent_alignment.get("status") or "unknown"),
                "source": str(raw_intent_alignment.get("source") or "runtime_compartment"),
                "objectiveExcerpt": str(raw_intent_alignment.get("objectiveExcerpt") or raw_intent_alignment.get("originalUserIntent") or "")[:180],
                "routeReason": str(raw_intent_alignment.get("routeReason") or raw_intent_alignment.get("driftReason") or ""),
                "selectedSkillId": str(raw_intent_alignment.get("selectedSkillId") or raw_intent_alignment.get("selectedSkill") or ""),
                "checkedAt": str(raw_intent_alignment.get("checkedAt") or now),
            }
        else:
            intent_alignment = {
                "schemaVersion": "mission-intent-alignment.v1",
                "status": "unknown",
                "source": "operator_message",
                "objectiveExcerpt": operator_message[:180],
                "routeReason": str(route.get("reason") or payload.get("routeReason") or ""),
                "selectedSkillId": str(payload.get("selectedSkillId") or result.get("selectedSkillId") or ""),
                "checkedAt": now,
            } if operator_message or route.get("reason") or payload.get("selectedSkillId") else {}
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
                    "effort": route.get("effort") or "medium",
                    "health": "ready" if process_backed_reply else "proof-only",
                    "active": role == active_role,
                    "authPath": "OpenAI Codex OAuth" if route.get("provider") == "openai-codex" else "provider route",
                    "blocker": "" if process_backed_reply else "No process-backed model evidence recorded.",
                }
            )
        compartment = {
            "sessionId": session_id,
            "runtime": result.get("runtime") or payload.get("runtime") or "openclaw",
            "cwd": workspace_path,
            "route": route,
            "host": os.environ.get("COMPUTERNAME") or (os.uname().nodename if hasattr(os, "uname") else ""),
            "state": "ready",
            "streaming": "recorded",
            "messages": messages[-40:],
            "toolTimeline": timeline[-30:],
            "lanes": lanes,
            "processEvidence": process_evidence,
            "intentAlignment": intent_alignment,
            "filesChanged": changed_files[:30],
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
        proof_path = self._chat_compartment_proof_path(session_id)
        proof_path.parent.mkdir(parents=True, exist_ok=True)
        proof_receipt = self._build_chat_compartment_proof_receipt(
            session_id=session_id,
            compartment=compartment,
            proof_path=proof_path,
            elapsed_ms=elapsed_ms,
        )
        proof_path.write_text(json.dumps(proof_receipt, indent=2), encoding="utf-8")
        compartment["runtimeProofReceipt"] = proof_receipt
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
        effort = str(route.get("effort") or payload.get("effort") or "medium").strip().lower()
        role = str(route.get("role") or payload.get("role") or "executor").strip().lower()
        model_id = model if "/" in model else f"{provider}/{model}" if provider and model else model
        return {
            "provider": provider,
            "model": model,
            "model_id": model_id,
            "effort": effort if effort and effort != "default" else "medium",
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
        result, stdout, _stderr, elapsed_ms = _run_process_capture(
            args,
            cwd=workspace_path,
            timeout=720,
            extra_env=env,
        )
        reply, reply_source = _extract_model_reply_with_source(result)
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
            "processEvidence": _process_evidence_from_capture(
                args=args,
                cwd=workspace_path,
                payload=result,
                stdout=stdout,
                stderr=_stderr,
                elapsed_ms=elapsed_ms,
                accepted_output_field=reply_source,
            ),
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
            reply_source = "output-last-message"
            if not reply:
                reply, reply_source = _extract_model_reply_with_source(result)
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
                "processEvidence": _process_evidence_from_capture(
                    args=args,
                    cwd=workspace_path,
                    payload=result,
                    stdout=stdout,
                    stderr=_stderr,
                    elapsed_ms=elapsed_ms,
                    accepted_output_field=reply_source,
                ),
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
        explicit_model = str(raw_route.get("model") or payload.get("model") or "").strip()
        explicit_provider = str(raw_route.get("provider") or payload.get("provider") or "").strip()
        native_args = ["hermes", "chat", "-q", prompt, "-Q"]
        if explicit_model:
            native_args.extend(["--model", explicit_model])
        if explicit_provider and route["provider"]:
            native_args.extend(["--provider", route["provider"]])
        if command:
            args = [command, *native_args[1:]]
        elif _wsl_has_command("hermes"):
            args = [
                shutil.which("wsl") or "wsl",
                "bash",
                "-lc",
                shlex.join(native_args),
            ]
        else:
            raise RuntimeError("Hermes CLI was not found on PATH (native or WSL).")
        workspace_path = Path(str(payload.get("workspacePath") or self.root)).expanduser()
        if not workspace_path.exists():
            workspace_path = self.root
        result, stdout, _stderr, elapsed_ms = _run_process_capture(
            args,
            cwd=workspace_path,
            timeout=720,
            extra_env=env,
        )
        reply, reply_source = _extract_model_reply_with_source(result)
        if not reply:
            raise RuntimeError("Hermes finished without a readable model reply.")
        now = _utc_now()
        tool_timeline, files_changed = _chat_runtime_evidence_from_process(
            result,
            stdout=stdout,
            now=now,
            elapsed_ms=elapsed_ms,
        )
        return {
            "reply": reply,
            "runtime": "hermes",
            "sessionId": _safe_identifier(payload.get("sessionId") or "syntelos_chat"),
            "route": {
                **route,
                "model": explicit_model,
                "model_id": f"{route['provider']}/{explicit_model}" if explicit_model else route["provider"],
            },
            "raw": result,
            "elapsedMs": elapsed_ms,
            "processEvidence": _process_evidence_from_capture(
                args=args,
                cwd=workspace_path,
                payload=result,
                stdout=stdout,
                stderr=_stderr,
                elapsed_ms=elapsed_ms,
                accepted_output_field=reply_source,
            ),
            "toolTimeline": tool_timeline,
            "filesChanged": files_changed,
        }

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
            snapshot = self._run_cli(root, "control-room", [], timeout=180, fast_control_room=True)
            provider_presence = _provider_presence(
                session_secrets=self.provider_secrets,
            )
            snapshot["providerSecretPresence"] = provider_presence
            reconcile_provider_secret_presence(snapshot, provider_presence)
            snapshot["webBackend"] = {
                "available": True,
                "commandSurface": "http",
                "root": str(root),
            }
            connected_bridge = snapshot.get("connectedDeviceBridge")
            if not isinstance(connected_bridge, dict):
                connected_bridge = {}
            existing_receipts = connected_bridge.get("receipts")
            receipts = [
                *([item for item in existing_receipts if isinstance(item, dict)] if isinstance(existing_receipts, list) else []),
                *self._load_live_review_receipts(),
            ]
            if receipts:
                connected_bridge["receipts"] = receipts[-25:]
                connected_bridge.setdefault("status", "local_receipts")
                snapshot["connectedDeviceBridge"] = connected_bridge
            return snapshot
        if command == "get_nas_deploy_readiness_command":
            from .mission_control import build_nas_deploy_readiness_snapshot

            return build_nas_deploy_readiness_snapshot(self.root)
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
        if command == "image_generation_capability_command":
            return self._image_generation_capability(payload)
        if command == "image_playground_operation_command":
            return self._write_image_playground_artifact(payload)
        if command == "record_live_review_structured_feedback_command":
            return self._record_live_review_structured_feedback(payload)
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
        if command == "apply_control_room_mission_action_command":
            args = [
                "--mission-id",
                str(payload.get("missionId") or payload.get("mission_id") or ""),
                "--action",
                str(payload.get("action") or ""),
            ]
            if str(payload.get("action") or "").strip().lower() == "resume":
                args.append("--launch-async")
            return self._run_cli(
                self.root,
                "mission-action",
                args,
                timeout=MISSION_ACTION_TIMEOUT_SECONDS,
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
                        "backend": "fluxio-web",
                        "loginRequired": True,
                    },
                )
                return
            if parsed.path == "/api/auth/status":
                _json_response(self, 200, {"ok": True, "data": backend.session_status(self)})
                return
            if parsed.path == "/api/artifact":
                backend.serve_artifact(self)
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
                try:
                    _json_response(self, 200, {"ok": True, "data": result})
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                    return
            except Exception as exc:  # pragma: no cover - exercised by browser/manual flows
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
