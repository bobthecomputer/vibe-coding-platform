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
import string
import subprocess
import sys
import tempfile
import time
import webbrowser
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

from .subprocess_utils import hidden_windows_subprocess_kwargs

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 47880
DEFAULT_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_NAME = "Syntelos"
ADMIN_CONFIG_RELATIVE_PATH = ".agent_control/grand_agent_web_admin.json"
ADMIN_PASSWORD_RELATIVE_PATH = ".agent_control/grand_agent_admin_password.txt"
MISSION_START_TIMEOUT_SECONDS = 1200
MISSION_ACTION_TIMEOUT_SECONDS = 1200
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
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
OPENAI_CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
OPENAI_CODEX_AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
OPENAI_CODEX_TOKEN_URL = "https://auth.openai.com/oauth/token"
OPENAI_CODEX_REDIRECT_URI = "http://localhost:1455/auth/callback"
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
            timeout=timeout,
            check=False,
            stdin=subprocess.DEVNULL,
            **hidden_windows_subprocess_kwargs(),
        )
    except Exception:  # pragma: no cover - defensive
        return False
    return completed.returncode == 0


def _extract_model_reply(payload: dict[str, Any]) -> str:
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
            return candidate.strip()
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
        callback_port: int = 1455,
        relay_token_hash: str = "",
    ) -> None:
        self.verifier = verifier
        self.state = state
        self.auth_url = auth_url
        self.callback_port = callback_port
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


def _write_codex_auth_json(tokens: dict[str, Any], identity: dict[str, str]) -> None:
    codex_home = _codex_home_path()
    codex_home.mkdir(parents=True, exist_ok=True)
    auth_payload = {
        "OPENAI_API_KEY": None,
        "tokens": {
            "id_token": str(tokens.get("id_token") or tokens.get("idToken") or tokens.get("access") or ""),
            "access_token": str(tokens.get("access") or ""),
            "refresh_token": str(tokens.get("refresh") or ""),
            "account_id": str(identity.get("accountId") or ""),
        },
        "last_refresh": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    auth_path = codex_home / "auth.json"
    auth_path.write_text(json.dumps(auth_payload, indent=2), encoding="utf-8")
    config_path = codex_home / "config.toml"
    if not config_path.exists():
        config_path.write_text('preferred_auth_method = "chatgpt"\nmodel = "gpt-5.3-codex"\n', encoding="utf-8")
    try:
        os.chmod(auth_path, 0o600)
    except OSError:
        pass


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


def _openai_codex_auth_url(verifier: str, state: str) -> str:
    challenge = _base64url_no_padding(hashlib.sha256(verifier.encode("ascii")).digest())
    query = urlencode(
        {
            "response_type": "code",
            "client_id": OPENAI_CODEX_CLIENT_ID,
            "redirect_uri": OPENAI_CODEX_REDIRECT_URI,
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
    auth_url = _openai_codex_auth_url(verifier, state)
    callback_port = _parse_openai_codex_callback_port(auth_url)
    session_id = secrets.token_urlsafe(16)
    relay_token = secrets.token_urlsafe(32)
    _OPENAI_CODEX_OAUTH_SESSIONS[session_id] = OpenAICodexOAuthSession(
        verifier=verifier,
        state=state,
        auth_url=auth_url,
        callback_port=callback_port,
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


def _exchange_openai_codex_authorization_code(code: str, verifier: str) -> dict[str, Any]:
    body = urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": OPENAI_CODEX_CLIENT_ID,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": OPENAI_CODEX_REDIRECT_URI,
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
    return {"profileId": profile_id, **identity}


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
    tokens = _exchange_openai_codex_authorization_code(code, session.verifier)
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
    if os.environ.get("FLUXIO_OPENAI_CODEX_OAUTH_PRESENT"):
        source = "environment"
    elif _openclaw_auth_store_has_provider(auth_store_path, "openai-codex"):
        source = "openclaw-auth-profile"
    elif os.environ.get("OPENAI_API_KEY") or (session_secrets or {}).get("openai"):
        source = "openai-api-key"
    return {
        "authenticated": authenticated,
        "accountId": None,
        "expires": None,
        "authStorePath": str(auth_store_path),
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
        return env

    def _run_cli(self, root: Path, command: str, args: list[str], timeout: int = 180) -> dict[str, Any]:
        return _run_cli(root, command, args, timeout=timeout, extra_env=self._provider_env())

    def _workspace_roots(self) -> list[str]:
        candidates = [self.root, Path.home()]
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
        provider = self._openclaw_provider_for_route(route.get("provider") or payload.get("provider") or "openai")
        model = str(route.get("model") or payload.get("model") or "").strip()
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
        result = _run_process(args, cwd=workspace_path, timeout=720, extra_env=env)
        reply = _extract_model_reply(result)
        if not reply:
            raise RuntimeError("OpenClaw finished without a readable model reply.")
        return {
            "reply": reply,
            "runtime": "openclaw",
            "sessionId": session_id,
            "route": route,
            "raw": result,
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
                route["model"] or "gpt-5.3-codex",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--output-last-message",
                str(output_path),
                "--json",
                prompt,
            ]
            result = _run_process(args, cwd=workspace_path, timeout=720, extra_env=env)
            reply = ""
            try:
                reply = output_path.read_text(encoding="utf-8").strip()
            except OSError:
                reply = ""
            if not reply:
                reply = _extract_model_reply(result)
            if not reply:
                raise RuntimeError("Codex finished without a readable model reply.")
            return {
                "reply": reply,
                "runtime": "codex",
                "sessionId": _safe_identifier(payload.get("sessionId") or "syntelos_chat"),
                "route": route,
                "raw": result,
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
        native_args = ["hermes", "chat", "-q", prompt, "-Q"]
        if route["model"]:
            native_args.extend(["--model", route["model"]])
        if route["provider"]:
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
        result = _run_process(args, cwd=workspace_path, timeout=720, extra_env=env)
        reply = _extract_model_reply(result)
        if not reply:
            raise RuntimeError("Hermes finished without a readable model reply.")
        return {
            "reply": reply,
            "runtime": "hermes",
            "sessionId": _safe_identifier(payload.get("sessionId") or "syntelos_chat"),
            "route": route,
            "raw": result,
        }

    def _run_agent_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        runtime = str(payload.get("runtime") or payload.get("runtimeId") or "openclaw").strip().lower()
        if runtime == "hermes":
            return self._run_hermes_chat(payload)
        if runtime in {"openclaw", "openclaw-local", ""}:
            route = self._chat_route(payload)
            if route.get("provider") == "openai-codex":
                return self._run_codex_chat(payload)
            return self._run_openclaw_chat(payload)
        if runtime == "codex":
            return self._run_codex_chat(payload)
        raise RuntimeError(f"Unsupported chat runtime: {runtime}")

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
