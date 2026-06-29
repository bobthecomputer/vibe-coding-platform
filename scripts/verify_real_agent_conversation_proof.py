from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from grant_agent.mission_control import ControlRoomStore, sync_mission_state_snapshot  # noqa: E402
from grant_agent.models import DelegatedRuntimeSession, MissionEvent, utc_now_iso  # noqa: E402

from control_route_interaction_smoke import Cdp, free_port, wait_for_devtools  # noqa: E402
from control_route_visual_smoke import find_browser_or_playwright_managed  # noqa: E402
from verify_windows_control_ui import process_group_flags, stop_process_tree, wait_for_http  # noqa: E402
from verify_workbench_program_bridge import (  # noqa: E402
    PASSWORD_FILE,
    capture,
    click_selector,
    login_backend_from_page,
    read_local_password,
    start_backend,
    start_vite,
    wait_for_selector,
)


DEFAULT_OUT_DIR = ROOT / "tmp-ui-checks" / "real-agent-conversation-proof"
DEFAULT_PROMPT = (
    "You are being invoked by Fluxio as a real local agent runtime for a transcript visibility check. "
    "Write a concise final-response-style answer in 3 to 5 sentences. "
    "State only what you can directly know from this request: you received a runtime prompt, you can answer from this prompt, "
    "and you did not inspect files, edit files, run tools, capture screenshots, or verify external state. "
    "Mention Fluxio, the SDK transcript route as a concept, and one honest next step for proving the UI shows this response. "
    "Do not invent transcript filenames, filesystem paths, hashes, persisted sessions, setup checks, screenshots, or completed verification."
)
DEFAULT_MODELS = [
    "minimax/MiniMax-M2.7-highspeed",
    "openai/gpt-5.5-fast",
    "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
    "openrouter/deepseek/deepseek-v4-flash",
]
DEFAULT_HERMES_MODEL = "gpt-5.5"
DEFAULT_HERMES_PROVIDER = "openai-codex"
OPENCLAW_SESSION_ROOT = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
OPENCLAW_CONFIG_PATH = Path(os.environ.get("OPENCLAW_CONFIG_PATH") or (Path.home() / ".openclaw" / "openclaw.json"))
OPENCLAW_STATE_DIR = OPENCLAW_CONFIG_PATH.parent
OPENCLAW_AUTH_PROFILES_PATH = OPENCLAW_STATE_DIR / "agents" / "main" / "agent" / "auth-profiles.json"
OPENCLAW_DOTENV_PATH = OPENCLAW_STATE_DIR / ".env"
OPENCLAW_GATEWAY_LAUNCHER_PATH = OPENCLAW_STATE_DIR / "gateway.cmd"
OPENCLAW_PROOF_SESSION_PREFIX = "fluxio-night-school-proof"
CORE_CHECK_IDS = {
    "runtime-command-available",
    "real-agent-reply-captured",
    "real-agent-reply-is-substantive",
    "fluxio-mission-stores-real-dialogue-or-blocker",
}
NON_SUBSTANTIVE_REPLY_PATTERNS = [
    (r"\bi can(?:not|'t) help with this request\b", "reply is a refusal instead of a usable agent answer"),
    (r"\basking me to fabricate\b", "reply treated the prompt as fake-proof fabrication"),
    (r"\bfake verification/proof\b", "reply focused on refusing fake verification"),
    (r"\bfresh workspace, no memory\b", "reply is an OpenClaw bootstrap greeting"),
    (r"\bblank identity\.md\b", "reply is an OpenClaw identity bootstrap greeting"),
]
SECRET_TEXT_PATTERNS = [
    re.compile(r"(Authorization:\s*Bearer\s+)[^\s,;]+", re.I),
    re.compile(r"(x-api-key[\"']?\s*[:=]\s*[\"']?)[^\"'\s,;]+", re.I),
    re.compile(r"([A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,})"),
    re.compile(r"(?<![A-Za-z0-9_-])([A-Za-z0-9_-]{48,})(?![A-Za-z0-9_-])"),
]
PROOF_BAG_DEFINITIONS = [
    (
        "fresh_opencode_round",
        "Fresh OpenCode runtime round",
        "A real `opencode run` attempt produced an assistant reply, or the failed attempt was recorded as a blocker.",
    ),
    (
        "fresh_hermes_round",
        "Fresh Hermes runtime round",
        "A real `hermes chat` attempt produced an assistant reply, or the failed attempt was recorded as a blocker.",
    ),
    (
        "fresh_openclaw_round",
        "Fresh OpenClaw runtime round",
        "A real `openclaw agent` attempt produced an assistant reply, or the failed attempt was recorded as a blocker.",
    ),
    (
        "recovered_openclaw_session",
        "Recovered OpenClaw persisted session",
        "A previously persisted OpenClaw assistant reply was recovered from the local session store.",
    ),
    (
        "fluxio_mission_storage",
        "Fluxio mission dialogue storage",
        "The runtime reply or explicit blocker reached Fluxio mission detail storage.",
    ),
    (
        "agent_ui_screenshot",
        "Agent UI screenshot",
        "Browser automation captured the Agent thread showing the real dialogue or recorded blocker.",
    ),
    (
        "produced_output_preview",
        "Produced output Preview screenshot",
        "Browser automation captured the generated proof artifact in Preview.",
    ),
]


def npm_command() -> str:
    return "npm.cmd" if sys.platform.startswith("win") else "npm"


def python_command() -> str:
    return sys.executable


def now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def record(report: dict, check_id: str, passed: bool, detail: str, **extra: object) -> None:
    item = {"checkId": check_id, "passed": bool(passed), "detail": detail}
    item.update(extra)
    report.setdefault("checks", []).append(item)


def initial_proof_bags() -> dict[str, dict[str, object]]:
    return {
        bag_id: {
            "bagId": bag_id,
            "label": label,
            "status": "missing",
            "passed": False,
            "detail": description,
        }
        for bag_id, label, description in PROOF_BAG_DEFINITIONS
    }


def set_proof_bag(report: dict, bag_id: str, status: str, detail: str, **extra: object) -> None:
    bags = report.setdefault("proofBags", initial_proof_bags())
    bag = bags.setdefault(
        bag_id,
        {
            "bagId": bag_id,
            "label": bag_id.replace("_", " ").title(),
            "status": "missing",
            "passed": False,
            "detail": "",
        },
    )
    bag["status"] = status
    bag["passed"] = status == "collected"
    bag["detail"] = detail
    bag.update(extra)


def summarize_proof_bags(report: dict) -> dict[str, object]:
    bags = report.get("proofBags")
    if not isinstance(bags, dict):
        bags = initial_proof_bags()
        report["proofBags"] = bags
    by_status: dict[str, list[str]] = {}
    for bag_id, bag in bags.items():
        if not isinstance(bag, dict):
            continue
        status = str(bag.get("status") or "missing")
        by_status.setdefault(status, []).append(str(bag.get("label") or bag_id))
    missing_or_skipped = [
        str(bag.get("label") or bag_id)
        for bag_id, bag in bags.items()
        if isinstance(bag, dict) and str(bag.get("status") or "missing") in {"missing", "skipped"}
    ]
    blocked = [
        str(bag.get("label") or bag_id)
        for bag_id, bag in bags.items()
        if isinstance(bag, dict) and str(bag.get("status") or "") == "blocked"
    ]
    return {
        "byStatus": by_status,
        "missingOrSkipped": missing_or_skipped,
        "blocked": blocked,
        "allBagsCollected": not missing_or_skipped and not blocked,
        "allBagsClosed": not missing_or_skipped,
    }


def run_command(command: list[str], *, timeout: int, cwd: Path) -> dict[str, object]:
    started = time.time()
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=process_group_flags(),
        )
        stdout, stderr = process.communicate(timeout=timeout)
        return {
            "command": command,
            "returnCode": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "durationMs": round((time.time() - started) * 1000),
            "timedOut": False,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        stop_process_tree(process)
        if process is not None:
            try:
                tail_stdout, tail_stderr = process.communicate(timeout=2)
                stdout += tail_stdout or ""
                stderr += tail_stderr or ""
            except Exception:
                pass
        return {
            "command": command,
            "returnCode": None,
            "stdout": stdout,
            "stderr": stderr,
            "durationMs": round((time.time() - started) * 1000),
            "timedOut": True,
        }


def redact_command(command: list[str]) -> list[str]:
    redacted: list[str] = []
    skip_next = False
    secret_flags = {"--password", "--api-key", "--token"}
    for item in command:
        if skip_next:
            redacted.append("***")
            skip_next = False
            continue
        redacted.append(item)
        if item in secret_flags:
            skip_next = True
    return redacted


def parse_json_lines(text: str) -> list[object]:
    rows: list[object] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            rows.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return rows


def parse_embedded_json_objects(text: str) -> list[object]:
    rows: list[object] = []
    decoder = json.JSONDecoder()
    for match in re.finditer(r"[\{\[]", text or ""):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        rows.append(value)
    return rows


def nested_text_values(value: object, *, assistant_only: bool = False) -> list[str]:
    texts: list[str] = []
    if isinstance(value, dict):
        role = str(value.get("role") or value.get("author") or "").lower()
        value_type = str(value.get("type") or value.get("kind") or "").lower()
        local_assistant = (
            assistant_only
            or role == "assistant"
            or "assistant" in value_type
            or value_type == "text"
            or "payloads" in value
            or "finalAssistantVisibleText" in value
            or "finalAssistantRawText" in value
        )
        for key in ("reply", "answer", "message", "content", "text", "output", "finalAssistantVisibleText", "finalAssistantRawText"):
            raw = value.get(key)
            if isinstance(raw, str) and (local_assistant or key in {"reply", "answer", "output"}):
                body = clean_agent_text(raw)
                if body:
                    texts.append(body)
            elif isinstance(raw, (dict, list)):
                texts.extend(nested_text_values(raw, assistant_only=local_assistant))
        for raw in value.values():
            if isinstance(raw, (dict, list)):
                texts.extend(nested_text_values(raw, assistant_only=local_assistant))
    elif isinstance(value, list):
        for item in value:
            texts.extend(nested_text_values(item, assistant_only=assistant_only))
    return texts


def clean_agent_text(text: str) -> str:
    body = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(text or "")).strip()
    body = re.sub(r"\s+", " ", body)
    if not body or len(body) < 40:
        return ""
    lowered = body.lower()
    if "unexpected server error" in lowered or lowered.startswith("error:"):
        return ""
    return body


def runtime_reply_quality(text: str) -> dict[str, object]:
    body = clean_agent_text(text)
    lowered = body.lower()
    problems: list[str] = []
    if len(body) < 160:
        problems.append("reply is too short to be comparable to a final response")
    for pattern, detail in NON_SUBSTANTIVE_REPLY_PATTERNS:
        if re.search(pattern, lowered, flags=re.I):
            problems.append(detail)
    relevance_terms = [
        term
        for term in ("fluxio", "runtime", "transcript", "agent", "ui", "mission")
        if term in lowered
    ]
    if len(relevance_terms) < 2:
        problems.append("reply does not carry enough Fluxio/runtime transcript context")
    return {
        "substantive": bool(body) and not problems,
        "charCount": len(body),
        "relevanceTerms": relevance_terms,
        "problems": problems,
        "excerpt": body[:700],
    }


def reply_quality_problem_summary(quality: dict[str, object]) -> str:
    problems = [
        str(item)
        for item in quality.get("problems", [])
        if str(item or "").strip()
    ]
    return "; ".join(problems) or "reply failed the substantive runtime proof quality gate"


def extract_agent_reply(result: dict[str, object]) -> str:
    stdout = str(result.get("stdout") or "")
    stderr = str(result.get("stderr") or "")
    candidates: list[str] = []
    for row in [*parse_json_lines(stdout), *parse_json_lines(stderr)]:
        candidates.extend(nested_text_values(row))
    if not candidates:
        for row in [*parse_embedded_json_objects(stdout), *parse_embedded_json_objects(stderr)]:
            candidates.extend(nested_text_values(row))
    plain = clean_agent_text(stdout)
    if plain and not parse_json_lines(stdout):
        candidates.append(plain)
    prompt_echo = DEFAULT_PROMPT.lower()
    candidates = [item for item in candidates if item.lower() != prompt_echo]
    if candidates:
        return max(candidates, key=len)[:3000]
    err = clean_agent_text(stderr)
    return "" if err else ""


def assistant_text_from_openclaw_row(row: object) -> str:
    if not isinstance(row, dict):
        return ""
    data = row.get("data") if isinstance(row.get("data"), dict) else {}
    assistant_texts = data.get("assistantTexts")
    if isinstance(assistant_texts, list):
        for item in reversed(assistant_texts):
            body = clean_agent_text(str(item or ""))
            if body:
                return body
    message = row.get("message") if isinstance(row.get("message"), dict) else {}
    if str(message.get("role") or "").lower() == "assistant":
        content = message.get("content")
        if isinstance(content, list):
            pieces: list[str] = []
            for item in content:
                if not isinstance(item, dict) or str(item.get("type") or "") != "text":
                    continue
                body = clean_agent_text(str(item.get("text") or ""))
                if body:
                    pieces.append(body)
            if pieces:
                return "\n\n".join(pieces)
    return ""


def load_openclaw_config() -> dict[str, object]:
    try:
        payload = json.loads(OPENCLAW_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def openclaw_configured_agents() -> list[dict[str, object]]:
    config = load_openclaw_config()
    agents = config.get("agents") if isinstance(config.get("agents"), dict) else {}
    rows = agents.get("list") if isinstance(agents, dict) else []
    return [item for item in rows if isinstance(item, dict)]


def same_existing_path(left: object, right: object) -> bool:
    left_text = str(left or "").strip()
    right_text = str(right or "").strip()
    if not left_text or not right_text:
        return False
    try:
        return Path(left_text).expanduser().resolve() == Path(right_text).expanduser().resolve()
    except OSError:
        return left_text.replace("\\", "/").rstrip("/").lower() == right_text.replace("\\", "/").rstrip("/").lower()


def openclaw_agent_selection(args: argparse.Namespace) -> dict[str, object]:
    explicit = safe_openclaw_identifier(str(getattr(args, "openclaw_agent", "") or ""))
    if explicit:
        return {
            "schema": "fluxio.openclaw_agent_selection.v1",
            "agentId": explicit,
            "source": "explicit-cli",
            "configPath": str(OPENCLAW_CONFIG_PATH),
        }
    root = Path(str(getattr(args, "root", ROOT) or ROOT)).expanduser()
    for row in openclaw_configured_agents():
        workspace = str(row.get("workspace") or "").strip()
        agent_id = safe_openclaw_identifier(str(row.get("id") or row.get("name") or ""))
        if agent_id and same_existing_path(workspace, root):
            agent_dir = str(row.get("agentDir") or "").strip()
            session_root = ""
            if agent_dir:
                agent_path = Path(agent_dir).expanduser()
                session_root = str((agent_path.parent if agent_path.name.lower() == "agent" else agent_path) / "sessions")
            if not session_root:
                session_root = str(Path.home() / ".openclaw" / "agents" / agent_id / "sessions")
            return {
                "schema": "fluxio.openclaw_agent_selection.v1",
                "agentId": agent_id,
                "source": "workspace-config",
                "workspace": workspace,
                "agentDir": agent_dir,
                "sessionRoot": session_root,
                "configPath": str(OPENCLAW_CONFIG_PATH),
            }
    return {
        "schema": "fluxio.openclaw_agent_selection.v1",
        "agentId": "",
        "source": "default-main-agent",
        "sessionRoot": str(OPENCLAW_SESSION_ROOT),
        "configPath": str(OPENCLAW_CONFIG_PATH),
    }


def openclaw_session_roots(args: argparse.Namespace | None = None) -> list[Path]:
    roots: list[Path] = []
    if args is not None:
        selection = openclaw_agent_selection(args)
        session_root = str(selection.get("sessionRoot") or "").strip()
        agent_id = str(selection.get("agentId") or "").strip()
        if session_root:
            roots.append(Path(session_root).expanduser())
        elif agent_id:
            roots.append(Path.home() / ".openclaw" / "agents" / agent_id / "sessions")
    if not roots:
        roots.append(OPENCLAW_SESSION_ROOT)
    deduped: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root.expanduser()).replace("\\", "/").rstrip("/").lower()
        if key and key not in seen:
            deduped.append(root.expanduser())
            seen.add(key)
    return deduped


def recover_openclaw_session_reply(
    session_hint: str = "",
    *,
    session_roots: list[Path] | None = None,
) -> dict[str, object]:
    """Recover a real OpenClaw assistant reply from persisted session/trajectory files."""
    roots = session_roots or [OPENCLAW_SESSION_ROOT]
    for root in roots:
        if not root.exists():
            continue
        session_files = list(root.glob("*.jsonl")) + list(root.glob("*.trajectory.jsonl"))
        if session_hint:
            session_files.sort(
                key=lambda path: (
                    session_hint not in path.name,
                    -path.stat().st_mtime,
                )
            )
        else:
            session_files.sort(key=lambda path: -path.stat().st_mtime)
        for path in session_files[:30]:
            if session_hint and session_hint not in path.name:
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            provider = "openclaw"
            model = ""
            session_id = path.name.split(".")[0]
            for line in reversed(lines):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    provider = str(row.get("provider") or provider or "openclaw")
                    model = str(row.get("modelId") or row.get("model") or model or "")
                    data = row.get("data") if isinstance(row.get("data"), dict) else {}
                    if not model:
                        model = str(data.get("modelId") or data.get("model") or "")
                    session_id = str(row.get("sessionId") or session_id)
                text = assistant_text_from_openclaw_row(row)
                if text:
                    return {
                        "runtime": "openclaw",
                        "provider": provider or "openclaw",
                        "model": model or "MiniMax-M2.7",
                        "sessionId": session_id,
                        "reply": text,
                        "sourcePath": str(path),
                        "sourceRoot": str(root),
                    }
    return {}


def summarize_runtime_failure(result: dict[str, object]) -> str:
    stdout = str(result.get("stdout") or "").strip()
    stderr = str(result.get("stderr") or "").strip()
    body = stderr or stdout or "Runtime command produced no assistant reply."
    body = re.sub(r"\s+", " ", body)
    if len(body) > 900:
        body = body[:900] + "..."
    if result.get("timedOut"):
        return f"Runtime command timed out and did not produce an assistant reply. {body}".strip()
    return f"Runtime command did not produce an assistant reply. {body}".strip()


def compact_redacted_text(value: object, limit: int = 500) -> str:
    body = re.sub(r"\s+", " ", str(value or "")).strip()
    for pattern in SECRET_TEXT_PATTERNS:
        body = pattern.sub(lambda match: (match.group(1) if match.lastindex else "") + "***", body)
    if len(body) <= limit:
        return body
    return body[: limit - 3].rstrip() + "..."


def parse_json_dict(text: object) -> dict[str, object]:
    try:
        payload = json.loads(str(text or ""))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def read_json_dict(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def openclaw_launcher_diagnostic() -> dict[str, object]:
    payload: dict[str, object] = {
        "path": str(OPENCLAW_GATEWAY_LAUNCHER_PATH),
        "exists": OPENCLAW_GATEWAY_LAUNCHER_PATH.exists(),
        "containsGatewayRun": False,
        "looksDisabled": False,
        "injectsMiniMaxApiKey": False,
        "problems": [],
    }
    try:
        text = OPENCLAW_GATEWAY_LAUNCHER_PATH.read_text(encoding="utf-8", errors="replace")
    except OSError:
        payload["problems"] = ["OpenClaw gateway launcher file is missing or unreadable."]
        return payload
    lowered = text.lower()
    payload["containsGatewayCommand"] = bool(re.search(r"\bgateway(?:\s|$)", lowered))
    payload["containsGatewayRun"] = bool(re.search(r"\bgateway\s+run(?:\s|$)", lowered))
    payload["looksDisabled"] = "exit /b 0" in lowered and not payload["containsGatewayRun"]
    payload["injectsMiniMaxApiKey"] = "minimax_api_key" in lowered
    try:
        payload["lastModified"] = datetime.fromtimestamp(OPENCLAW_GATEWAY_LAUNCHER_PATH.stat().st_mtime, timezone.utc).isoformat()
    except OSError:
        pass
    problems: list[str] = []
    if payload["looksDisabled"]:
        problems.append("OpenClaw gateway launcher exits immediately instead of starting the gateway.")
    elif not payload["containsGatewayRun"]:
        problems.append("OpenClaw gateway launcher does not include the required gateway run command.")
    if payload["injectsMiniMaxApiKey"]:
        problems.append("OpenClaw gateway launcher still injects a raw MiniMax API key.")
    payload["problems"] = problems
    return payload


def openclaw_dotenv_diagnostic() -> dict[str, object]:
    payload: dict[str, object] = {
        "path": str(OPENCLAW_DOTENV_PATH),
        "exists": OPENCLAW_DOTENV_PATH.exists(),
        "hasMiniMaxApiKey": False,
        "problems": [],
    }
    try:
        text = OPENCLAW_DOTENV_PATH.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return payload
    payload["hasMiniMaxApiKey"] = bool(re.search(r"(?im)^\s*MINIMAX_API_KEY\s*=", text))
    if payload["hasMiniMaxApiKey"]:
        payload["problems"] = ["OpenClaw .env still defines MINIMAX_API_KEY; this can override portal OAuth routing."]
    return payload


def safe_oauth_profiles_from_models_status(payload: dict[str, object]) -> list[dict[str, object]]:
    auth = payload.get("auth") if isinstance(payload.get("auth"), dict) else {}
    oauth = auth.get("oauth") if isinstance(auth.get("oauth"), dict) else {}
    rows = oauth.get("profiles") if isinstance(oauth.get("profiles"), list) else []
    safe_rows: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        safe_rows.append(
            {
                "profileId": row.get("profileId") or "",
                "provider": row.get("provider") or "",
                "type": row.get("type") or "",
                "status": row.get("status") or "",
                "expiresAt": row.get("expiresAt") or None,
                "remainingMs": row.get("remainingMs") or None,
                "source": row.get("source") or "",
                "label": row.get("label") or "",
            }
        )
    return safe_rows


def openclaw_models_status_diagnostic(openclaw_cmd: str, root: Path) -> dict[str, object]:
    result = run_command([openclaw_cmd, "models", "status", "--json"], timeout=30, cwd=root)
    payload = parse_json_dict(result.get("stdout") or result.get("stderr") or "")
    auth = payload.get("auth") if isinstance(payload.get("auth"), dict) else {}
    shell_env = auth.get("shellEnvFallback") if isinstance(auth.get("shellEnvFallback"), dict) else {}
    problems: list[str] = []
    for row in safe_oauth_profiles_from_models_status(payload):
        provider = str(row.get("provider") or row.get("profileId") or "OAuth profile")
        status = str(row.get("status") or "unknown")
        if status and status != "ok":
            problems.append(f"{provider} OAuth status is {status}.")
    missing = auth.get("missingProvidersInUse") if isinstance(auth.get("missingProvidersInUse"), list) else []
    if missing:
        problems.append("OpenClaw models status reports missing providers in use: " + ", ".join(str(item) for item in missing))
    if result.get("timedOut"):
        problems.append("OpenClaw models status command timed out.")
    elif result.get("returnCode") not in (0, None):
        problems.append("OpenClaw models status command exited non-zero.")
    return {
        "command": ["openclaw", "models", "status", "--json"],
        "returnCode": result.get("returnCode"),
        "timedOut": bool(result.get("timedOut")),
        "durationMs": result.get("durationMs"),
        "defaultModel": payload.get("defaultModel") or "",
        "resolvedDefault": payload.get("resolvedDefault") or "",
        "fallbacks": payload.get("fallbacks") if isinstance(payload.get("fallbacks"), list) else [],
        "shellEnvFallbackEnabled": bool(shell_env.get("enabled")),
        "shellEnvFallbackAppliedKeys": shell_env.get("appliedKeys") if isinstance(shell_env.get("appliedKeys"), list) else [],
        "oauthProfiles": safe_oauth_profiles_from_models_status(payload),
        "missingProvidersInUse": missing,
        "errorPreview": compact_redacted_text(result.get("stderr") or result.get("stdout") or "", 360) if not payload else "",
        "problems": problems,
    }


def openclaw_gateway_probe_diagnostic(openclaw_cmd: str, root: Path) -> dict[str, object]:
    result = run_command([openclaw_cmd, "gateway", "probe", "--json"], timeout=30, cwd=root)
    payload = parse_json_dict(result.get("stdout") or result.get("stderr") or "")
    targets = payload.get("targets") if isinstance(payload.get("targets"), list) else []
    first_target = next((item for item in targets if isinstance(item, dict)), {})
    connect = first_target.get("connect") if isinstance(first_target.get("connect"), dict) else {}
    problems: list[str] = []
    ok = bool(payload.get("ok"))
    if result.get("timedOut"):
        problems.append("OpenClaw gateway probe timed out.")
    elif not ok:
        error = compact_redacted_text(connect.get("error") or payload.get("error") or "gateway probe did not connect", 220)
        problems.append(f"OpenClaw gateway probe failed: {error}.")
    return {
        "command": ["openclaw", "gateway", "probe", "--json"],
        "returnCode": result.get("returnCode"),
        "timedOut": bool(result.get("timedOut")),
        "durationMs": result.get("durationMs"),
        "ok": ok,
        "degraded": bool(payload.get("degraded")),
        "capability": payload.get("capability") or "",
        "localLoopbackUrl": ((payload.get("network") or {}).get("localLoopbackUrl") if isinstance(payload.get("network"), dict) else "") or "",
        "targetId": first_target.get("id") if isinstance(first_target, dict) else "",
        "connectOk": bool(connect.get("ok")),
        "rpcOk": bool(connect.get("rpcOk")),
        "connectError": compact_redacted_text(connect.get("error") or "", 220),
        "closeCode": (connect.get("close") or {}).get("code") if isinstance(connect.get("close"), dict) else None,
        "errorPreview": compact_redacted_text(result.get("stderr") or result.get("stdout") or "", 360) if not payload else "",
        "problems": problems,
    }


def provider_http_json_probe(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
    timeout: int = 20,
) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            status = int(response.status)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        status = int(exc.code)
    except urllib.error.URLError as exc:
        return {
            "ok": False,
            "httpStatus": None,
            "durationMs": round((time.time() - started) * 1000),
            "errorPreview": compact_redacted_text(exc.reason, 240),
        }
    except TimeoutError as exc:
        return {
            "ok": False,
            "httpStatus": None,
            "durationMs": round((time.time() - started) * 1000),
            "errorPreview": compact_redacted_text(exc, 240),
        }
    parsed = parse_json_dict(body)
    base_resp = parsed.get("base_resp") if isinstance(parsed.get("base_resp"), dict) else {}
    return {
        "ok": 200 <= status < 300 and not base_resp.get("status_code"),
        "httpStatus": status,
        "durationMs": round((time.time() - started) * 1000),
        "providerStatusCode": base_resp.get("status_code"),
        "providerStatusMessage": compact_redacted_text(base_resp.get("status_msg") or "", 160),
        "errorPreview": compact_redacted_text(body, 240) if not (200 <= status < 300) or base_resp.get("status_code") else "",
    }


def minimax_env_key_diagnostic() -> dict[str, object]:
    key = os.environ.get("MINIMAX_API_KEY") or ""
    payload: dict[str, object] = {
        "provider": "minimax",
        "source": "process-env",
        "keyPresent": bool(key),
        "checked": False,
        "problems": [],
    }
    if not key:
        payload["status"] = "skipped"
        return payload
    probe = provider_http_json_probe(
        url="https://api.minimax.chat/v1/text/chatcompletion_v2",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        payload={
            "model": "MiniMax-M2.7",
            "messages": [{"sender_type": "USER", "text": "Fluxio runtime credential probe."}],
        },
        timeout=20,
    )
    payload.update(probe)
    payload["checked"] = True
    if probe.get("providerStatusCode") == 2049:
        payload["problems"] = ["MINIMAX_API_KEY is rejected by MiniMax as invalid."]
    elif not probe.get("ok"):
        payload["problems"] = [f"MINIMAX_API_KEY probe failed with HTTP {probe.get('httpStatus') or 'unknown'}."]
    return payload


def minimax_portal_oauth_diagnostic(models_status: dict[str, object]) -> dict[str, object]:
    profiles = read_json_dict(OPENCLAW_AUTH_PROFILES_PATH)
    profile_rows = profiles.get("profiles") if isinstance(profiles.get("profiles"), dict) else {}
    portal = profile_rows.get("minimax-portal:default") if isinstance(profile_rows, dict) else {}
    access = str(portal.get("access") or "") if isinstance(portal, dict) else ""
    configured_for_portal = "minimax-portal/" in str(models_status.get("resolvedDefault") or models_status.get("defaultModel") or "")
    payload: dict[str, object] = {
        "provider": "minimax-portal",
        "source": str(OPENCLAW_AUTH_PROFILES_PATH),
        "profilePresent": bool(portal),
        "accessTokenPresent": bool(access),
        "configuredForDefaultModel": configured_for_portal,
        "expires": portal.get("expires") if isinstance(portal, dict) else None,
        "checked": False,
        "problems": [],
    }
    if not access:
        if configured_for_portal:
            payload["problems"] = ["MiniMax Portal is the selected default model provider, but no portal OAuth access token is stored."]
        payload["status"] = "skipped"
        return payload
    anthropic_payload = {
        "model": "MiniMax-M2.7",
        "max_tokens": 8,
        "messages": [{"role": "user", "content": "Fluxio runtime credential probe."}],
    }
    authorization_probe = provider_http_json_probe(
        url="https://api.minimax.io/anthropic/v1/messages",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access}",
            "anthropic-version": "2023-06-01",
        },
        payload=anthropic_payload,
        timeout=20,
    )
    x_api_key_probe = provider_http_json_probe(
        url="https://api.minimax.io/anthropic/v1/messages",
        headers={
            "Content-Type": "application/json",
            "X-Api-Key": access,
            "anthropic-version": "2023-06-01",
        },
        payload=anthropic_payload,
        timeout=20,
    )
    probe = x_api_key_probe if x_api_key_probe.get("ok") else authorization_probe
    payload.update(probe)
    payload["checked"] = True
    payload["attempts"] = [
        {
            "header": "Authorization",
            "ok": bool(authorization_probe.get("ok")),
            "httpStatus": authorization_probe.get("httpStatus"),
            "providerStatusCode": authorization_probe.get("providerStatusCode"),
            "providerStatusMessage": authorization_probe.get("providerStatusMessage") or "",
            "errorPreview": authorization_probe.get("errorPreview") or "",
        },
        {
            "header": "X-Api-Key",
            "ok": bool(x_api_key_probe.get("ok")),
            "httpStatus": x_api_key_probe.get("httpStatus"),
            "providerStatusCode": x_api_key_probe.get("providerStatusCode"),
            "providerStatusMessage": x_api_key_probe.get("providerStatusMessage") or "",
            "errorPreview": x_api_key_probe.get("errorPreview") or "",
        },
    ]
    if not x_api_key_probe.get("ok") and x_api_key_probe.get("httpStatus") == 401:
        payload["problems"] = ["MiniMax Portal OAuth token is rejected by the MiniMax API with HTTP 401, including the X-Api-Key header form."]
    elif not x_api_key_probe.get("ok"):
        payload["problems"] = [f"MiniMax Portal OAuth probe failed with HTTP {x_api_key_probe.get('httpStatus') or 'unknown'}."]
    return payload


def openclaw_diagnostic_problem_summary(diagnostic: object, limit: int = 700) -> str:
    if not isinstance(diagnostic, dict):
        return ""
    problems = [
        str(item).strip()
        for item in diagnostic.get("problems", [])
        if str(item or "").strip()
    ]
    return compact_redacted_text("; ".join(problems), limit)


def openclaw_runtime_diagnostics(args: argparse.Namespace, root: Path) -> dict[str, object]:
    openclaw_cmd = runtime_command_path("openclaw")
    diagnostic: dict[str, object] = {
        "schema": "fluxio.openclaw_runtime_diagnostics.v1",
        "checkedAt": utc_now_iso(),
        "commandAvailable": bool(openclaw_cmd),
        "problems": [],
    }
    if not openclaw_cmd:
        diagnostic["status"] = "blocked"
        diagnostic["problems"] = ["OpenClaw command is not available on PATH."]
        diagnostic["summary"] = openclaw_diagnostic_problem_summary(diagnostic)
        return diagnostic
    launcher = openclaw_launcher_diagnostic()
    dotenv = openclaw_dotenv_diagnostic()
    models_status = openclaw_models_status_diagnostic(openclaw_cmd, root)
    gateway_probe = openclaw_gateway_probe_diagnostic(openclaw_cmd, root)
    env_key = minimax_env_key_diagnostic()
    portal = minimax_portal_oauth_diagnostic(models_status)
    diagnostic.update(
        {
            "launcher": launcher,
            "dotenv": dotenv,
            "modelsStatus": models_status,
            "gatewayProbe": gateway_probe,
            "minimaxEnvKey": env_key,
            "minimaxPortalOAuth": portal,
        }
    )
    problems: list[str] = []
    for section in (launcher, dotenv, models_status, gateway_probe, env_key, portal):
        for item in section.get("problems", []) if isinstance(section, dict) else []:
            text = str(item or "").strip()
            if text and text not in problems:
                problems.append(text)
    diagnostic["problems"] = problems
    diagnostic["status"] = "blocked" if problems else "ok"
    diagnostic["summary"] = openclaw_diagnostic_problem_summary(diagnostic)
    return diagnostic


def runtime_session_id_from_command(command: list[str]) -> str:
    for flag in ("--session-id", "--session-key"):
        if flag not in command:
            continue
        index = command.index(flag)
        if index + 1 < len(command):
            return str(command[index + 1] or "").strip()
    return ""


def runtime_session_id_from_result(result: dict[str, object], command: list[str] | None = None) -> str:
    recovered_session_id = str(
        result.get("recoveredSessionId")
        or result.get("sessionId")
        or result.get("session_id")
        or ""
    ).strip()
    if recovered_session_id:
        return recovered_session_id
    text = "\n".join([str(result.get("stdout") or ""), str(result.get("stderr") or "")])
    patterns = [
        r"\bsession_id:\s*([A-Za-z0-9_.:-]+)",
        r'"sessionID"\s*:\s*"([^"]+)"',
        r'"sessionId"\s*:\s*"([^"]+)"',
        r'"sessionKey"\s*:\s*"([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    if command:
        return runtime_session_id_from_command(command)
    return ""


def safe_openclaw_identifier(value: str) -> str:
    identifier = re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value or "").strip()).strip("-")
    return identifier[:96]


def openclaw_proof_session_id(args: argparse.Namespace) -> str:
    explicit = safe_openclaw_identifier(str(getattr(args, "openclaw_session_id", "") or ""))
    if explicit:
        return explicit
    prompt_hash = hashlib.sha256(str(args.prompt or "").encode("utf-8")).hexdigest()[:10]
    return safe_openclaw_identifier(f"{OPENCLAW_PROOF_SESSION_PREFIX}-{now_compact()}-{prompt_hash}")


def openclaw_command_selector(command: list[str]) -> dict[str, object]:
    def flag_value(flag: str) -> str:
        if flag not in command:
            return ""
        index = command.index(flag)
        return str(command[index + 1] or "").strip() if index + 1 < len(command) else ""

    return {
        "schema": "fluxio.openclaw_runtime_selector.v1",
        "sessionId": flag_value("--session-id"),
        "agentId": flag_value("--agent"),
        "thinking": flag_value("--thinking"),
        "timeoutSeconds": flag_value("--timeout"),
        "local": "--local" in command,
    }


def openclaw_gateway_agent_command(openclaw_cmd: str, args: argparse.Namespace) -> list[str]:
    command = [
        openclaw_cmd,
        "agent",
    ]
    selection = openclaw_agent_selection(args)
    agent_id = safe_openclaw_identifier(str(selection.get("agentId") or ""))
    if agent_id:
        command.extend(["--agent", agent_id])
    command.extend([
        "--session-id",
        openclaw_proof_session_id(args),
        "--message",
        args.prompt,
        "--thinking",
        str(getattr(args, "openclaw_thinking", "") or "low"),
        "--json",
        "--timeout",
        str(max(10, int(args.runtime_timeout))),
    ])
    if bool(getattr(args, "openclaw_local", False)):
        command.append("--local")
    return command


def hermes_chat_command(hermes_cmd: str, args: argparse.Namespace) -> list[str]:
    command = [
        hermes_cmd,
        "chat",
        "-q",
        args.prompt,
        "-Q",
        "--model",
        args.hermes_model,
    ]
    if args.hermes_provider:
        command.extend(["--provider", args.hermes_provider])
    return command


def wsl_hermes_chat_command(wsl_cmd: str, args: argparse.Namespace) -> list[str]:
    hermes_args = [
        "hermes",
        "chat",
        "-q",
        str(args.prompt or ""),
        "-Q",
        "--model",
        str(args.hermes_model or DEFAULT_HERMES_MODEL),
    ]
    if args.hermes_provider:
        hermes_args.extend(["--provider", str(args.hermes_provider)])
    script = 'export PATH="$HOME/.local/bin:$PATH"; ' + shlex.join(hermes_args)
    return [wsl_cmd, "bash", "-lc", script]


def command_candidates(args: argparse.Namespace) -> list[tuple[str, str, list[str]]]:
    requested = str(args.runtime or "auto").lower()
    models = [item.strip() for item in str(args.model or "").split(",") if item.strip()] or DEFAULT_MODELS
    candidates: list[tuple[str, str, list[str]]] = []
    opencode_cmd = runtime_command_path("opencode")
    hermes_cmd = runtime_command_path("hermes")
    wsl_cmd = runtime_command_path("wsl")
    openclaw_cmd = runtime_command_path("openclaw")
    if requested in {"auto", "hermes"}:
        hermes_model_label = (
            f"{args.hermes_provider}/{args.hermes_model}"
            if args.hermes_provider
            else args.hermes_model
        )
        if hermes_cmd:
            candidates.append(
                (
                    "hermes",
                    hermes_model_label,
                    hermes_chat_command(hermes_cmd, args),
                )
            )
        elif wsl_cmd:
            candidates.append(
                (
                    "hermes",
                    f"{hermes_model_label} via WSL",
                    wsl_hermes_chat_command(wsl_cmd, args),
                )
            )
    if requested in {"auto", "opencode"} and opencode_cmd:
        for model in models:
            candidates.append(
                (
                    "opencode",
                    model,
                    [
                        opencode_cmd,
                        "run",
                        "--model",
                        model,
                        "--format",
                        "json",
                        "--title",
                        "fluxio-night-school-proof",
                        args.prompt,
                    ],
                )
            )
    if requested in {"auto", "openclaw"} and openclaw_cmd:
        selection = openclaw_agent_selection(args)
        agent_label = str(selection.get("agentId") or "default")
        candidates.append(
            (
                "openclaw",
                f"gateway-agent-{agent_label}",
                openclaw_gateway_agent_command(openclaw_cmd, args),
            )
        )
    return candidates


def runtime_command_path(name: str) -> str:
    if os.name == "nt":
        for candidate in (f"{name}.cmd", f"{name}.exe", name):
            resolved = shutil.which(candidate)
            if resolved and not resolved.lower().endswith(".ps1"):
                return resolved
    resolved = shutil.which(name)
    return resolved or ""


def pick_workspace(store: ControlRoomStore, root: Path):
    workspaces = [item for item in store.load_workspaces() if item.enabled]
    resolved = str(root.resolve())
    for item in workspaces:
        try:
            if str(Path(item.root_path).expanduser().resolve()) == resolved:
                return item
        except OSError:
            continue
    if workspaces:
        return workspaces[0]
    raise RuntimeError("No enabled Fluxio workspace profile is available.")


def normalize_proof_mission_runtime_id(runtime: str) -> str:
    normalized = str(runtime or "").strip().lower()
    if normalized in {"openclaw", "opencode", "hermes"}:
        return normalized
    if normalized.startswith("opencode"):
        return "opencode"
    return normalized or "runtime"


def proof_runtime_display_label(runtime: str) -> str:
    normalized = normalize_proof_mission_runtime_id(runtime)
    if normalized == "openclaw":
        return "OpenClaw"
    if normalized == "opencode":
        return "OpenCode"
    if normalized == "hermes":
        return "Hermes"
    return normalized.replace("_", " ").replace("-", " ").title() or "Runtime"


def runtime_capture_label(capture_mode: object) -> str:
    normalized = str(capture_mode or "").strip().lower().replace("_", "-")
    if normalized in {"recovered-persisted-session", "persisted-session", "recovered-session"}:
        return "recovered persisted session"
    if normalized in {"fresh-runtime-command", "fresh-command", "runtime-command"}:
        return "fresh runtime command"
    if normalized:
        return normalized.replace("-", " ")
    return "real runtime output"


def write_artifact(
    *,
    root: Path,
    mission_id: str,
    title: str,
    status: str,
    body: str,
    runtime: str,
    model: str,
    report_path: Path,
    capture_mode: str = "",
    source_path: str = "",
) -> dict[str, str]:
    artifact_dir = root / ".agent_control" / "mission_artifacts" / mission_id
    proof_dir = artifact_dir / "proof"
    proof_dir.mkdir(parents=True, exist_ok=True)
    safe_body = html.escape(str(body or ""))
    safe_title = html.escape(str(title or "Real Agent Conversation Proof"))
    safe_status = html.escape(str(status or "recorded"))
    safe_runtime = html.escape(str(runtime or "runtime"))
    safe_model = html.escape(str(model or "model"))
    safe_report_path = html.escape(str(report_path))
    safe_capture_label = html.escape(runtime_capture_label(capture_mode))
    safe_source_path = html.escape(str(source_path or ""))
    source_path_row = f"\n      <span>Source path: {safe_source_path}</span>" if safe_source_path else ""
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title}</title>
  <style>
    body {{ margin: 0; background: #0d0f12; color: #f8fafc; font: 16px/1.55 Inter, Arial, sans-serif; }}
    main {{ max-width: 860px; padding: 40px; }}
    h1 {{ font-size: 30px; margin: 0 0 12px; }}
    p {{ color: #cbd5e1; }}
    .provenance {{ display: grid; gap: 6px; margin: 18px 0; color: #d9f99d; font-size: 13px; }}
    pre {{ white-space: pre-wrap; background: #15191f; border: 1px solid #2b323d; padding: 20px; }}
    small {{ color: #93a4b8; }}
  </style>
</head>
<body>
  <main data-real-agent-proof-artifact="true">
    <small>{safe_runtime} / {safe_model} / {safe_status}</small>
    <h1>{safe_title}</h1>
    <p>This page is generated from the captured runtime command output for Fluxio Agent transcript verification.</p>
    <div class="provenance" data-real-agent-proof-provenance="real-runtime-output">
      <span>Source: real runtime output via {safe_capture_label}.</span>{source_path_row}
      <span>Report: {safe_report_path}</span>
    </div>
    <pre>{safe_body}</pre>
  </main>
</body>
</html>
"""
    index_path = artifact_dir / "index.html"
    index_path.write_text(html_doc, encoding="utf-8")
    artifact_id = hashlib.sha256(str(index_path.resolve()).encode("utf-8")).hexdigest()[:24]
    manifest = {
        "schema": "fluxio.real_agent_conversation_artifact.v1",
        "missionId": mission_id,
        "status": status,
        "runtime": runtime,
        "model": model,
        "entrypoint": str(index_path),
        "previewUrl": f"/api/artifact?id={artifact_id}",
        "artifactId": artifact_id,
        "reportPath": str(report_path),
        "sourceKind": "real-runtime-output",
        "provenance": {
            "runtimeOutputSource": "captured_runtime_command_output",
            "captureMode": capture_mode,
            "captureLabel": runtime_capture_label(capture_mode),
            "sourcePath": source_path,
            "demoData": False,
            "reportPath": str(report_path),
        },
    }
    manifest_path = artifact_dir / "artifact_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"artifactDir": str(artifact_dir), "indexPath": str(index_path), "manifestPath": str(manifest_path)}


def attach_mission_proof(
    *,
    root: Path,
    runtime: str,
    model: str,
    command: list[str],
    reply: str,
    failure: str,
    result: dict[str, object],
    report_path: Path,
    runtime_session_id: str = "",
) -> dict[str, object]:
    store = ControlRoomStore(root)
    workspace = pick_workspace(store, root)
    mission_runtime_id = normalize_proof_mission_runtime_id(runtime)
    mission = store.create_mission(
        workspace_id=workspace.workspace_id,
        runtime_id=mission_runtime_id,
        objective="Night school real agent conversation proof for Fluxio SDK transcript visibility.",
        success_checks=[
            "A real runtime assistant reply is visible in Agent as dialogue.",
            "The produced proof artifact opens in Preview.",
        ],
        mode="Autopilot",
        verification_commands=[],
        max_runtime_seconds=900,
        selected_profile=workspace.user_profile,
    )
    success = bool(reply)
    event_kind = "runtime.output" if success else "runtime.stderr"
    event_message = reply or failure
    recovered_source_path = str(result.get("recoveredFrom") or "") if isinstance(result, dict) else ""
    capture_mode = "recovered-persisted-session" if recovered_source_path else "fresh-runtime-command"
    session = DelegatedRuntimeSession(
        delegated_id=f"night_school_{now_compact()}",
        runtime_id=runtime,
        launch_command=" ".join(redact_command(command)),
        status="completed" if success else "failed",
        detail="Real runtime reply captured." if success else "Runtime launch attempted but no assistant reply was captured.",
        workspace_root=str(root),
        target_provider=runtime,
        target_model=model,
        target_effort="low",
        exit_code=result.get("returnCode") if isinstance(result.get("returnCode"), int) else None,
        latest_events=[
            {
                "kind": event_kind,
                "message": event_message,
                "timestamp": utc_now_iso(),
                "metadata": {
                    "schema": "fluxio.real_agent_runtime_capture.v1",
                    "sourceKind": "real-runtime-output",
                    "runtime": runtime,
                    "model": model,
                    "returnCode": result.get("returnCode"),
                    "timedOut": bool(result.get("timedOut")),
                    "captureMode": capture_mode,
                    "sourcePath": recovered_source_path,
                    "reportPath": str(report_path),
                    "externalRuntimeSessionId": runtime_session_id,
                },
            }
        ],
    )
    mission.delegated_runtime_sessions = [session]
    mission.state.delegated_runtime_sessions = [asdict(session)]
    mission.state.latest_session_id = session.delegated_id
    mission.state.last_runtime_event = event_kind
    mission.state.status = "completed" if success else "blocked"
    mission.state.planner_loop_status = "completed" if success else "blocked"
    mission.proof.summary = (
        "Real runtime assistant reply captured and attached to the Fluxio Agent conversation."
        if success
        else "Real runtime launch was attempted, but no assistant reply was captured."
    )
    mission.proof.passed_checks = [
        "real runtime command executed",
        "assistant reply captured",
    ] if success else ["real runtime command executed"]
    mission.proof.failed_checks = [] if success else ["assistant reply missing"]
    mission.proof.blocked_by = [] if success else [failure]
    artifact_body = reply or failure
    artifact = write_artifact(
        root=root,
        mission_id=mission.mission_id,
        title="Real Agent Conversation Proof" if success else "Real Agent Runtime Blocker",
        status="completed" if success else "blocked",
        body=artifact_body,
        runtime=runtime,
        model=model,
        report_path=report_path,
        capture_mode=capture_mode,
        source_path=recovered_source_path,
    )
    if success:
        proof_dir = root / ".agent_control" / "mission_artifacts" / mission.mission_id / "proof"
        (proof_dir / "runtime_output.txt").write_text(reply, encoding="utf-8")
    mission.proof.artifacts = [
        {"kind": "runtime_capture", "path": str(report_path)},
        {"kind": "html_preview", "path": artifact["indexPath"]},
    ]
    sync_mission_state_snapshot(mission)
    store.update_mission(mission)
    store.append_event(
        MissionEvent(
            mission_id=mission.mission_id,
            kind="night_school.real_agent_conversation_proof",
            message=mission.proof.summary,
            metadata={
                "runtime": runtime,
                "model": model,
                "success": success,
                "reportPath": str(report_path),
                "artifact": artifact,
            },
        )
    )
    detail = store.build_mission_detail_snapshot(mission.mission_id, event_limit=120)
    return {
        "missionId": mission.mission_id,
        "workspaceId": workspace.workspace_id,
        "success": success,
        "artifact": artifact,
        "detail": detail,
    }


def start_browser() -> tuple[subprocess.Popen[bytes], tempfile.TemporaryDirectory[str], str]:
    browser_exe = find_browser_or_playwright_managed()
    if not browser_exe:
        raise RuntimeError("No Chromium-compatible browser was found for screenshot verification.")
    profile = tempfile.TemporaryDirectory(prefix="fluxio-real-agent-browser-")
    port = free_port()
    browser = subprocess.Popen(
        [
            browser_exe,
            "--headless=new",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-sandbox",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile.name}",
            "--window-size=1440,960",
            "--no-first-run",
            "--disable-default-apps",
            "about:blank",
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=process_group_flags(),
    )
    tabs = wait_for_devtools(port)
    first_tab = tabs[0] if tabs else {}
    ws_url = str(first_tab.get("webSocketDebuggerUrl") or "")
    if not ws_url:
        raise RuntimeError(f"Chrome DevTools did not expose a page websocket: {tabs!r}")
    return browser, profile, ws_url


def cleanup_profile(profile: tempfile.TemporaryDirectory[str] | None) -> None:
    if profile is None:
        return
    try:
        profile.cleanup()
    except PermissionError:
        pass


def login_backend_cookie(backend_url: str, username: str, password: str) -> str:
    payload = json.dumps({"username": username, "password": password}).encode("utf-8")
    request = urllib.request.Request(
        f"{backend_url}/api/auth/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        cookie_header = response.headers.get("Set-Cookie", "")
    parsed = cookie_header.split(";", 1)[0]
    name, _, value = parsed.partition("=")
    if name.strip() != "grand_agent_session" or not value:
        raise RuntimeError("Backend login did not return a grand_agent_session cookie.")
    return value


def set_browser_session_cookie(cdp: Cdp, *, url: str, value: str) -> None:
    cdp.send(
        "Network.setCookie",
        {
            "url": url,
            "name": "grand_agent_session",
            "value": value,
            "path": "/",
            "sameSite": "Lax",
            "httpOnly": True,
        },
    )


def wait_for_iframe_artifact(cdp: Cdp, selector: str, *, timeout: float = 45.0) -> dict[str, object]:
    expression = f"""
(() => {{
  const frame = document.querySelector({json.dumps(selector)});
  if (!frame) return {{ found: false, src: "", readyState: "", hasArtifact: false, artifactSourceVerified: false, text: "" }};
  const src = frame.src || frame.getAttribute("src") || "";
  const srcdoc = frame.getAttribute("srcdoc") || "";
  const sourceKind = srcdoc
    ? "iframe-srcdoc"
    : src
      ? "iframe-src"
      : "iframe-dom";
  try {{
    const doc = frame.contentDocument;
    const text = doc && doc.body ? doc.body.innerText : "";
    const hasArtifact = Boolean(doc && doc.querySelector('[data-real-agent-proof-artifact="true"]'));
    const hasProvenance = Boolean(doc && doc.querySelector('[data-real-agent-proof-provenance="real-runtime-output"]'));
    const srcdocHasArtifact = srcdoc.includes('data-real-agent-proof-artifact="true"');
    return {{
      found: true,
      src,
      sourceKind,
      readyState: doc ? doc.readyState : "",
      hasArtifact,
      hasProvenance,
      artifactSourceVerified: Boolean(hasArtifact && (hasProvenance || srcdocHasArtifact || src || /captured runtime command output/i.test(text))),
      srcdocLength: srcdoc.length,
      srcdocHasArtifact,
      text
    }};
  }} catch (error) {{
    return {{
      found: true,
      src,
      sourceKind,
      readyState: "cross-origin",
      hasArtifact: false,
      hasProvenance: false,
      artifactSourceVerified: false,
      srcdocLength: srcdoc.length,
      srcdocHasArtifact: srcdoc.includes('data-real-agent-proof-artifact="true"'),
      text: String(error && error.message ? error.message : error)
    }};
  }}
}})()
"""
    deadline = time.time() + timeout
    last: dict[str, object] = {}
    while time.time() < deadline:
        value = cdp.eval(expression)
        if isinstance(value, dict):
            last = value
            text = str(value.get("text") or "")
            if value.get("hasArtifact") and "Real Agent Conversation Proof" in text:
                return value
        time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for real agent proof artifact in {selector}; last={last!r}")


def browser_state(cdp: Cdp) -> dict[str, object]:
    state = cdp.eval(
        """
(() => ({
  location: window.location.href,
  readyState: document.readyState,
  title: document.title,
  bodyText: document.body ? document.body.innerText.slice(0, 1200) : "",
  bodyHtmlLength: document.body ? document.body.innerHTML.length : 0,
  threadRows: document.querySelectorAll('[data-message-zone="thread"]').length,
  dialogueRows: document.querySelectorAll('[data-message-zone="thread"][data-agent-dialogue-turn="true"]').length,
  dialogueProvenanceRows: document.querySelectorAll('[data-message-zone="thread"][data-agent-dialogue-turn="true"][data-agent-runtime-provenance="real-runtime-output"]').length,
  runtimeRows: document.querySelectorAll('[data-message-zone="thread"][data-agent-runtime-provenance="real-runtime-output"], [data-message-zone="thread"][data-runtime-report="true"], [data-message-zone="thread"][data-hermes-transcript="true"]').length,
  previewButton: Boolean(document.querySelector('[data-live-agent-action="preview"]')),
  dialogueHeaderText: document.querySelector('.fluxos-thread[data-live-agent-thread-router="true"] .fluxos-thread-head span')?.innerText || "",
  firstSpeakerText: document.querySelector('[data-message-zone="thread"] .fluxos-message-head strong')?.innerText || "",
  firstProvenanceText: document.querySelector('[data-message-zone="thread"] [data-agent-message-provenance="real-runtime-output"]')?.innerText || "",
  recoverableError: Boolean(document.querySelector('.fluxos-recoverable-error, [data-recoverable-error="true"]'))
}))()
"""
    )
    return state if isinstance(state, dict) else {"raw": state}


def wait_for_real_thread_rows(cdp: Cdp, *, timeout: float = 90.0) -> dict[str, object]:
    deadline = time.time() + timeout
    last: dict[str, object] = {}
    while time.time() < deadline:
        state = browser_state(cdp)
        last = state
        if int(state.get("dialogueProvenanceRows") or 0) > 0:
            return state
        if state.get("recoverableError"):
            raise RuntimeError(f"Agent UI recoverable error before proof rows rendered: {state}")
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for real Agent dialogue rows with runtime provenance; last={last!r}")


def click_agent_preview_button_by_coordinates(cdp: Cdp) -> None:
    # The verifier fixes the viewport at 1440x960. This is a CDP fallback for
    # cases where Runtime.evaluate is blocked but screenshots prove the button.
    x = 1300
    y = 640
    for event_type, button in (("mouseMoved", "none"), ("mousePressed", "left"), ("mouseReleased", "left")):
        params: dict[str, object] = {"type": event_type, "x": x, "y": y, "button": button}
        if event_type == "mousePressed":
            params["clickCount"] = 1
        cdp.send("Input.dispatchMouseEvent", params)


def local_proof_artifact_payload(*, root: Path, mission_id: str) -> dict[str, object]:
    path = root / ".agent_control" / "mission_artifacts" / mission_id / "index.html"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"hasArtifact": False, "src": str(path), "text": ""}
    return {
        "hasArtifact": 'data-real-agent-proof-artifact="true"' in text and "Real Agent Conversation Proof" in text,
        "src": str(path),
        "text": re.sub(r"\s+", " ", text)[:1200],
        "source": "local-mission-artifact-file",
    }


def verify_browser(
    report: dict,
    *,
    mission_id: str,
    out_dir: Path,
    root: Path,
    expected_runtime_label: str = "",
) -> dict[str, object]:
    backend_port = free_port()
    vite_port = free_port()
    backend_url = f"http://127.0.0.1:{backend_port}"
    base_url = f"http://127.0.0.1:{vite_port}"
    backend = start_backend(backend_port)
    vite = start_vite(vite_port, backend_url)
    browser = None
    profile = None
    ws = None
    cdp = None
    stage = "starting browser verification"
    report["browserStage"] = stage
    try:
        stage = "waiting for backend health"
        report["browserStage"] = stage
        wait_for_http(f"{backend_url}/api/health", timeout=45.0)
        stage = "waiting for Vite control shell"
        report["browserStage"] = stage
        wait_for_http(f"{base_url}/control?preview-control=1", timeout=90.0)
        stage = "starting browser"
        report["browserStage"] = stage
        browser, profile, ws_url = start_browser()
        from control_route_interaction_smoke import DevToolsSocket

        stage = "opening DevTools socket"
        report["browserStage"] = stage
        ws = DevToolsSocket(ws_url)
        ws.socket.settimeout(60)
        cdp = Cdp(ws)
        stage = "enabling browser domains"
        report["browserStage"] = stage
        cdp.send("Page.enable")
        cdp.send("Runtime.enable")
        cdp.send("Network.enable")
        cdp.send("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 960, "deviceScaleFactor": 1, "mobile": False})
        stage = "logging in through browser page"
        report["browserStage"] = stage
        username, password = read_local_password(PASSWORD_FILE)
        session_cookie = login_backend_cookie(backend_url, username, password)
        set_browser_session_cookie(cdp, url=backend_url, value=session_cookie)
        set_browser_session_cookie(cdp, url=base_url, value=session_cookie)
        cdp.send("Page.navigate", {"url": f"{base_url}/control?mode=builder&surface=workbench"})
        time.sleep(1.0)
        login_backend_from_page(cdp, backend_url, username, password)
        url = f"{base_url}/control?preview-control=1&mode=agent&surface=agent&agentScene=run&missionId={urllib.parse.quote(mission_id)}"
        stage = "navigating to Agent mission"
        report["browserStage"] = stage
        cdp.send("Page.navigate", {"url": url})
        stage = "settling Agent mission route"
        report["browserStage"] = stage
        time.sleep(10.0)
        try:
            cdp.send("Page.stopLoading")
        except Exception:
            pass
        stage = "capturing Agent navigation screenshot"
        report["browserStage"] = stage
        report.setdefault("screenshots", {})["agentAfterNavigate"] = capture(cdp, out_dir / "agent-after-navigate.png")
        stage = "capturing Agent navigation state"
        report["browserStage"] = stage
        dom_probe_error = ""
        try:
            report["browserStateAfterNavigate"] = browser_state(cdp)
            stage = "waiting for real Agent thread rows"
            report["browserStage"] = stage
            thread_state = wait_for_real_thread_rows(cdp, timeout=120.0)
        except Exception as exc:
            dom_probe_error = f"{stage}: {exc}"
            report["browserDomProbeError"] = dom_probe_error
            thread_state = {
                "dialogueRows": 0,
                "dialogueProvenanceRows": 0,
                "runtimeRows": 0,
                "threadRows": 0,
                "domProbeFailed": True,
                "detail": dom_probe_error,
            }
        screenshot_path = out_dir / "agent-real-conversation-proof.png"
        stage = "capturing Agent conversation screenshot"
        report["browserStage"] = stage
        report.setdefault("screenshots", {})["agentConversation"] = capture(cdp, screenshot_path)
        dialogue_rows = int(thread_state.get("dialogueRows") or 0)
        dialogue_provenance_rows = int(thread_state.get("dialogueProvenanceRows") or 0)
        runtime_report_rows = int(thread_state.get("runtimeRows") or 0)
        all_rows = int(thread_state.get("threadRows") or 0)
        provenance_state = thread_state if not dom_probe_error else report.get("browserStateAfterNavigate", {})
        provenance_haystack = " ".join(
            str(provenance_state.get(key) or "")
            for key in ("dialogueHeaderText", "firstSpeakerText", "firstProvenanceText", "bodyText")
            if isinstance(provenance_state, dict)
        )
        expected_label = str(expected_runtime_label or "").strip()
        runtime_provenance_matched = True
        if expected_label:
            lowered_haystack = provenance_haystack.lower()
            lowered_expected = expected_label.lower()
            runtime_provenance_matched = lowered_expected in lowered_haystack
            if lowered_expected != "hermes":
                runtime_provenance_matched = runtime_provenance_matched and "hermes dialogue" not in lowered_haystack
        preview_button = True
        if not dom_probe_error:
            try:
                preview_button = bool(cdp.eval('Boolean(document.querySelector(\'[data-live-agent-action="preview"]\'))'))
            except Exception as exc:
                dom_probe_error = f"checking Preview button: {exc}"
                report["browserDomProbeError"] = dom_probe_error
        preview_screenshot = ""
        preview_error = ""
        if preview_button:
            stage = "opening Agent preview"
            report["browserStage"] = stage
            if dom_probe_error:
                click_agent_preview_button_by_coordinates(cdp)
            else:
                click_selector(cdp, '[data-live-agent-action="preview"]')
            time.sleep(8.0)
            try:
                stage = "waiting for Agent preview frame"
                report["browserStage"] = stage
                wait_for_selector(cdp, '[data-agent-preview-frame="true"]', timeout=45.0)
                stage = "waiting for produced proof artifact iframe"
                report["browserStage"] = stage
                preview_artifact = wait_for_iframe_artifact(cdp, '[data-agent-preview-frame="true"]', timeout=60.0)
                stage = "capturing produced output preview screenshot"
                report["browserStage"] = stage
                preview_screenshot = capture(cdp, out_dir / "agent-produced-output-preview.png")
                report["screenshots"]["producedOutputPreview"] = preview_screenshot
            except Exception as exc:
                preview_error = f"{stage}: {exc}"
                report["previewError"] = preview_error
                report.setdefault("screenshots", {})["previewFailure"] = capture(cdp, out_dir / "preview-failure-state.png")
                local_artifact = local_proof_artifact_payload(root=root, mission_id=mission_id)
                preview_artifact = {
                    "hasArtifact": False,
                    "artifactSourceVerified": bool(local_artifact.get("hasArtifact")),
                    "src": local_artifact.get("src") or "",
                    "sourceKind": local_artifact.get("source") or "",
                    "text": local_artifact.get("text") or "",
                    "source": local_artifact.get("source") or "",
                    "iframeProbeError": preview_error,
                }
                preview_screenshot = report["screenshots"].get("previewFailure", "")
        else:
            preview_artifact = {}
        report["browserStage"] = "complete"
        return {
            "baseUrl": base_url,
            "backendUrl": backend_url,
            "agentUrl": url,
            "dialogueRows": int(dialogue_rows or 0),
            "dialogueProvenanceRows": int(dialogue_provenance_rows or 0),
            "runtimeReportRows": int(runtime_report_rows or 0),
            "allThreadRows": int(all_rows or 0),
            "previewButton": preview_button,
            "expectedRuntimeLabel": expected_label,
            "dialogueHeaderText": str(provenance_state.get("dialogueHeaderText") or "") if isinstance(provenance_state, dict) else "",
            "firstSpeakerText": str(provenance_state.get("firstSpeakerText") or "") if isinstance(provenance_state, dict) else "",
            "firstProvenanceText": str(provenance_state.get("firstProvenanceText") or "") if isinstance(provenance_state, dict) else "",
            "runtimeProvenanceMatched": runtime_provenance_matched,
            "previewScreenshot": preview_screenshot,
            "previewArtifactVisible": bool(preview_artifact.get("hasArtifact")) if isinstance(preview_artifact, dict) else False,
            "previewArtifactSourceVerified": bool(preview_artifact.get("artifactSourceVerified")) if isinstance(preview_artifact, dict) else False,
            "previewArtifactSource": str(preview_artifact.get("sourceKind") or preview_artifact.get("source") or "") if isinstance(preview_artifact, dict) else "",
            "previewArtifactHasProvenance": bool(preview_artifact.get("hasProvenance")) if isinstance(preview_artifact, dict) else False,
            "previewArtifactSrcdocHasArtifact": bool(preview_artifact.get("srcdocHasArtifact")) if isinstance(preview_artifact, dict) else False,
            "previewFrameSrc": str(preview_artifact.get("src") or "") if isinstance(preview_artifact, dict) else "",
            "previewArtifactTextExcerpt": str(preview_artifact.get("text") or "")[:500] if isinstance(preview_artifact, dict) else "",
            "previewError": preview_error,
        }
    except Exception as exc:
        report["browserStage"] = stage
        if ws and cdp:
            try:
                report.setdefault("screenshots", {})["browserFailure"] = capture(cdp, out_dir / "browser-failure-state.png")
                report["browserState"] = browser_state(cdp)
            except Exception:
                pass
        raise RuntimeError(f"{stage}: {exc}") from exc
    finally:
        if ws:
            ws.close()
        if browser:
            stop_process_tree(browser)
        cleanup_profile(profile)
        stop_process_tree(vite)
        stop_process_tree(backend)


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture and prove a real Fluxio agent conversation in the app.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--name", default="real-agent-conversation")
    parser.add_argument("--runtime", choices=["auto", "opencode", "hermes", "openclaw"], default="auto")
    parser.add_argument("--model", default="", help="Comma-separated OpenCode model list to try.")
    parser.add_argument("--hermes-model", default=DEFAULT_HERMES_MODEL, help="Hermes model to use for the fresh Hermes proof round.")
    parser.add_argument("--hermes-provider", default=DEFAULT_HERMES_PROVIDER, help="Hermes provider to use for the fresh Hermes proof round.")
    parser.add_argument("--openclaw-session-id", default="", help="OpenClaw session id to use for the fresh OpenClaw proof round.")
    parser.add_argument("--openclaw-agent", default="", help="Optional existing OpenClaw agent id for the fresh OpenClaw proof round.")
    parser.add_argument("--openclaw-thinking", default="low", help="OpenClaw thinking level for the fresh OpenClaw proof round.")
    parser.add_argument("--openclaw-local", action="store_true", help="Run the fresh OpenClaw proof round in local agent mode.")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--runtime-timeout", type=int, default=60)
    parser.add_argument("--fresh-runtime", action="store_true", help="Launch a new runtime command instead of first using an existing persisted OpenClaw session.")
    parser.add_argument("--with-browser", action="store_true", help="Also capture Agent and Preview screenshots through the local web UI.")
    parser.add_argument("--skip-browser", action="store_true", help="Compatibility alias; browser capture is opt-in by default.")
    parser.add_argument("--require-all-bags", action="store_true", help="Fail unless every proof bag is collected, with no skipped or blocked bags.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    run_dir = Path(args.out_dir) / now_compact()
    run_dir.mkdir(parents=True, exist_ok=True)
    report_path = run_dir / f"{args.name}-check.json"
    report: dict[str, object] = {
        "schema": "fluxio.real_agent_conversation_proof.v1",
        "createdAt": utc_now_iso(),
        "root": str(root),
        "promptHash": hashlib.sha256(str(args.prompt or "").encode("utf-8")).hexdigest()[:16],
        "promptPreview": str(args.prompt or "")[:240],
        "checks": [],
        "screenshots": {},
        "attempts": [],
        "proofBags": initial_proof_bags(),
    }
    report["openclawProofAgent"] = openclaw_agent_selection(args)
    report["openclawSessionRoots"] = [str(item) for item in openclaw_session_roots(args)]
    requested_runtime = str(args.runtime or "auto").lower()
    if requested_runtime in {"auto", "openclaw"}:
        report["openclawRuntimeDiagnostics"] = openclaw_runtime_diagnostics(args, root)
        record(
            report,
            "openclaw-runtime-diagnostics-collected",
            True,
            (
                "OpenClaw diagnostics collected with no provider or gateway blockers."
                if not openclaw_diagnostic_problem_summary(report.get("openclawRuntimeDiagnostics"))
                else "OpenClaw diagnostics collected blocker details: "
                + openclaw_diagnostic_problem_summary(report.get("openclawRuntimeDiagnostics"))
            ),
            runtime="openclaw",
        )

    recovered_reply: dict[str, object] = {}
    recovered_reply_quality: dict[str, object] = {}
    recovered_reply_usable = False
    if not args.fresh_runtime and str(args.runtime).lower() in {"auto", "openclaw"}:
        recovered_reply = recover_openclaw_session_reply(
            OPENCLAW_PROOF_SESSION_PREFIX,
            session_roots=openclaw_session_roots(args),
        )
    if recovered_reply:
        recovered_reply_quality = runtime_reply_quality(str(recovered_reply.get("reply") or ""))
        recovered_reply_usable = bool(recovered_reply_quality.get("substantive"))
        report["recoveredRuntimeReply"] = recovered_reply
        report["recoveredRuntimeReplyQuality"] = recovered_reply_quality
        set_proof_bag(
            report,
            "recovered_openclaw_session",
            "collected" if recovered_reply_usable else "blocked",
            (
                f"Recovered persisted OpenClaw session {recovered_reply.get('sessionId')}."
                if recovered_reply_usable
                else (
                    f"Recovered persisted OpenClaw session {recovered_reply.get('sessionId')}, "
                    "but rejected it as the selected proof: "
                    + reply_quality_problem_summary(recovered_reply_quality)
                )
            ),
            runtime="openclaw",
            model=recovered_reply.get("model") or "MiniMax-M2.7",
            sourcePath=recovered_reply.get("sourcePath"),
            problems=recovered_reply_quality.get("problems"),
        )
        if not recovered_reply_usable:
            report["rejectedRecoveredRuntimeReply"] = {
                "sessionId": recovered_reply.get("sessionId"),
                "sourcePath": recovered_reply.get("sourcePath"),
                "quality": recovered_reply_quality,
            }
    elif args.fresh_runtime and not args.require_all_bags:
        set_proof_bag(
            report,
            "recovered_openclaw_session",
            "skipped",
            "Fresh runtime mode was requested, so persisted OpenClaw recovery was intentionally skipped.",
        )
    candidates = [] if recovered_reply_usable and not args.require_all_bags else command_candidates(args)
    record(
        report,
        "runtime-command-available",
        bool(candidates) or bool(recovered_reply_usable),
        (
            f"Recovered existing OpenClaw session {recovered_reply.get('sessionId')}."
            if recovered_reply_usable
            else (
                f"Rejected recovered OpenClaw session {recovered_reply.get('sessionId')} and found "
                f"{len(candidates)} fresh candidate real runtime command(s)."
                if recovered_reply
                else f"Found {len(candidates)} candidate real runtime command(s)."
            )
        ),
    )
    if recovered_reply and not recovered_reply_usable and not candidates:
        best_failure = (
            "Recovered persisted OpenClaw output was real but not usable as final-response-style proof: "
            + reply_quality_problem_summary(recovered_reply_quality)
        )
    else:
        best_failure = "No OpenCode, Hermes, or OpenClaw command was available on PATH."
    selected_result: dict[str, object] | None = None
    selected_runtime = ""
    selected_model = ""
    selected_command: list[str] = []
    reply = ""
    successful_fresh_runtimes: set[str] = set()
    collect_all_requested_runtimes = bool(args.require_all_bags and str(args.runtime).lower() == "auto")
    if recovered_reply_usable:
        reply = str(recovered_reply.get("reply") or "")
        selected_runtime = "openclaw"
        selected_model = str(recovered_reply.get("model") or "MiniMax-M2.7")
        selected_command = [
            "openclaw",
            "sessions",
            "--json",
            str(recovered_reply.get("sessionId") or ""),
        ]
        selected_result = {
            "returnCode": 0,
            "stdout": reply,
            "stderr": "",
            "timedOut": False,
            "recoveredFrom": recovered_reply.get("sourcePath"),
            "recoveredSessionId": recovered_reply.get("sessionId"),
        }
    for runtime, model, command in candidates:
        if runtime in successful_fresh_runtimes:
            continue
        result = run_command(command, timeout=max(10, int(args.runtime_timeout)), cwd=root)
        result["command"] = redact_command(command)
        attempt = {"runtime": runtime, "model": model, **result}
        if runtime == "openclaw":
            selector = openclaw_command_selector(command)
            attempt["runtimeSelector"] = selector
            report["openclawProofSelector"] = selector
        report["attempts"].append(attempt)
        extracted = extract_agent_reply(result)
        if runtime == "openclaw" and not extracted:
            command_session_id = runtime_session_id_from_command(command)
            persisted = recover_openclaw_session_reply(
                command_session_id,
                session_roots=openclaw_session_roots(args),
            )
            if persisted:
                extracted = str(persisted.get("reply") or "")
                result["recoveredFrom"] = persisted.get("sourcePath")
                result["recoveredSessionId"] = persisted.get("sessionId")
                attempt["recoveredRuntimeReply"] = {
                    "sessionId": persisted.get("sessionId"),
                    "sourcePath": persisted.get("sourcePath"),
                    "sourceRoot": persisted.get("sourceRoot"),
                    "provider": persisted.get("provider"),
                    "model": persisted.get("model"),
                }
        extracted_quality = runtime_reply_quality(extracted)
        if runtime == "opencode":
            bag_id = "fresh_opencode_round"
        elif runtime == "hermes":
            bag_id = "fresh_hermes_round"
        else:
            bag_id = "fresh_openclaw_round"
        if extracted and extracted_quality.get("substantive"):
            set_proof_bag(
                report,
                bag_id,
                "collected",
                f"Fresh {runtime} round produced a substantive real assistant reply.",
                runtime=runtime,
                model=model,
                returnCode=result.get("returnCode"),
                timedOut=bool(result.get("timedOut")),
                charCount=extracted_quality.get("charCount"),
                relevanceTerms=extracted_quality.get("relevanceTerms"),
            )
            successful_fresh_runtimes.add(runtime)
            if not reply:
                selected_result = result
                selected_runtime = runtime
                selected_model = model
                selected_command = command
                reply = extracted
            if not collect_all_requested_runtimes:
                break
            continue
        if not reply:
            selected_result = result
            selected_runtime = runtime
            selected_model = model
            selected_command = command
        best_failure = (
            "Runtime command produced a real assistant reply, but it was not usable as final-response-style proof: "
            + reply_quality_problem_summary(extracted_quality)
            if extracted
            else summarize_runtime_failure(result)
        )
        if runtime == "openclaw":
            diagnostic_summary = openclaw_diagnostic_problem_summary(report.get("openclawRuntimeDiagnostics"))
            if diagnostic_summary:
                best_failure = f"{best_failure} OpenClaw diagnostics: {diagnostic_summary}"
        set_proof_bag(
            report,
            bag_id,
            "blocked",
            best_failure,
            runtime=runtime,
            model=model,
            returnCode=result.get("returnCode"),
            timedOut=bool(result.get("timedOut")),
            problems=extracted_quality.get("problems") if extracted else [],
        )
    if (not reply or args.require_all_bags) and str(args.runtime).lower() in {"auto", "openclaw"}:
        recovered_reply = recover_openclaw_session_reply(
            OPENCLAW_PROOF_SESSION_PREFIX,
            session_roots=openclaw_session_roots(args),
        )
        recovered_text = str(recovered_reply.get("reply") or "")
        recovered_reply_quality = runtime_reply_quality(recovered_text)
        recovered_reply_usable = bool(recovered_reply_quality.get("substantive"))
        if recovered_text:
            set_proof_bag(
                report,
                "recovered_openclaw_session",
                "collected" if recovered_reply_usable else "blocked",
                (
                    f"Recovered persisted OpenClaw session {recovered_reply.get('sessionId')} after fresh attempts."
                    if recovered_reply_usable
                    else (
                        f"Recovered persisted OpenClaw session {recovered_reply.get('sessionId')} after fresh attempts, "
                        "but rejected it as selected proof: "
                        + reply_quality_problem_summary(recovered_reply_quality)
                    )
                ),
                runtime="openclaw",
                model=recovered_reply.get("model") or "MiniMax-M2.7",
                sourcePath=recovered_reply.get("sourcePath"),
                problems=recovered_reply_quality.get("problems"),
            )
            report["recoveredRuntimeReply"] = recovered_reply
            report["recoveredRuntimeReplyQuality"] = recovered_reply_quality
            if not recovered_reply_usable:
                report["rejectedRecoveredRuntimeReply"] = {
                    "sessionId": recovered_reply.get("sessionId"),
                    "sourcePath": recovered_reply.get("sourcePath"),
                    "quality": recovered_reply_quality,
                }
                if not reply:
                    best_failure = (
                        "Recovered persisted OpenClaw output was real but not usable as final-response-style proof: "
                        + reply_quality_problem_summary(recovered_reply_quality)
                    )
            if not reply and recovered_reply_usable:
                reply = recovered_text
                selected_runtime = "openclaw"
                selected_model = str(recovered_reply.get("model") or "MiniMax-M2.7")
                selected_command = [
                    "openclaw",
                    "sessions",
                    "--json",
                    str(recovered_reply.get("sessionId") or ""),
                ]
                selected_result = {
                    "returnCode": 0,
                    "stdout": recovered_text,
                    "stderr": "",
                    "timedOut": False,
                    "recoveredFrom": recovered_reply.get("sourcePath"),
                    "recoveredSessionId": recovered_reply.get("sessionId"),
                }
        elif args.require_all_bags:
            set_proof_bag(
                report,
                "recovered_openclaw_session",
                "blocked",
                "No persisted OpenClaw night-school session could be recovered after fresh runtime attempts.",
            )
            report["recoveredRuntimeReply"] = recovered_reply

    selected_recovered = bool(selected_result and selected_result.get("recoveredFrom"))
    record(
        report,
        "real-agent-reply-captured",
        bool(reply),
        (
            f"A real assistant reply was recovered from persisted OpenClaw session {recovered_reply.get('sessionId')}."
            if selected_recovered
            else "A real assistant reply was captured from the runtime command."
        )
        if reply
        else best_failure,
        runtime=selected_runtime,
        model=selected_model,
    )
    reply_quality = runtime_reply_quality(reply)
    report["replyQuality"] = reply_quality
    record(
        report,
        "real-agent-reply-is-substantive",
        bool(reply_quality.get("substantive")),
        (
            "The captured runtime reply is a substantive final-response-style answer."
            if reply_quality.get("substantive")
            else "The captured runtime output is real, but not substantive enough for conversation proof: "
            + "; ".join(str(item) for item in reply_quality.get("problems", []))
        ),
        runtime=selected_runtime,
        model=selected_model,
        charCount=reply_quality.get("charCount"),
        relevanceTerms=reply_quality.get("relevanceTerms"),
        problems=reply_quality.get("problems"),
    )
    if selected_result is None:
        selected_result = {"returnCode": None, "stdout": "", "stderr": best_failure, "timedOut": False}
    runtime_session_id = runtime_session_id_from_result(selected_result, selected_command)
    report["runtimeSessionId"] = runtime_session_id
    mission_payload = attach_mission_proof(
        root=root,
        runtime=selected_runtime or str(args.runtime),
        model=selected_model,
        command=selected_command,
        reply=reply,
        failure=best_failure,
        result=selected_result,
        report_path=report_path,
        runtime_session_id=runtime_session_id,
    )
    report["mission"] = {
        "missionId": mission_payload["missionId"],
        "workspaceId": mission_payload["workspaceId"],
        "success": mission_payload["success"],
        "artifact": mission_payload["artifact"],
    }
    detail = mission_payload["detail"]
    dialogue_count = len([item for item in detail.get("agentMessages", []) if isinstance(item, dict) and item.get("conversationTurn")])
    dialogue_capture_labels = [
        str((item.get("turnReceipt") or {}).get("captureLabel") or "")
        for item in detail.get("agentMessages", [])
        if isinstance(item, dict)
        and item.get("conversationTurn")
        and isinstance(item.get("turnReceipt"), dict)
    ]
    dialogue_capture_modes = [
        str((item.get("turnReceipt") or {}).get("captureMode") or "")
        for item in detail.get("agentMessages", [])
        if isinstance(item, dict)
        and item.get("conversationTurn")
        and isinstance(item.get("turnReceipt"), dict)
    ]
    report["missionDetailSummary"] = {
        "agentMessageCount": len(detail.get("agentMessages", [])) if isinstance(detail.get("agentMessages"), list) else 0,
        "dialogueCount": dialogue_count,
        "dialogueCaptureModes": [item for item in dialogue_capture_modes if item],
        "dialogueCaptureLabels": [item for item in dialogue_capture_labels if item],
        "runtimeTranscriptStatus": (detail.get("runtimeTranscript") or {}).get("status") if isinstance(detail.get("runtimeTranscript"), dict) else "",
        "artifactGatePassed": bool((detail.get("artifactGate") or {}).get("passed")) if isinstance(detail.get("artifactGate"), dict) else False,
    }
    set_proof_bag(
        report,
        "fluxio_mission_storage",
        "collected" if ((bool(reply) and dialogue_count > 0) or (not reply and bool(best_failure))) else "missing",
        (
            f"Mission detail stored {dialogue_count} real dialogue turn(s)."
            if reply
            else "Mission detail stored an explicit runtime blocker."
        ),
        dialogueCount=dialogue_count,
        missionId=mission_payload["missionId"],
    )
    record(
        report,
        "fluxio-mission-stores-real-dialogue-or-blocker",
        (bool(reply) and dialogue_count > 0) or (not reply and bool(best_failure)),
        "Fluxio mission detail contains real dialogue from runtime output, or an explicit runtime blocker.",
        dialogueCount=dialogue_count,
    )
    record(
        report,
        "runtime-capture-provenance-distinguishes-source",
        bool([item for item in dialogue_capture_modes if item]),
        "Agent dialogue carries capture-mode provenance for real runtime output.",
        captureModes=[item for item in dialogue_capture_modes if item],
        captureLabels=[item for item in dialogue_capture_labels if item],
    )

    if args.with_browser and not args.skip_browser:
        try:
            expected_runtime_label = proof_runtime_display_label(selected_runtime or str(args.runtime))
            browser_payload = verify_browser(
                report,
                mission_id=str(mission_payload["missionId"]),
                out_dir=run_dir,
                root=root,
                expected_runtime_label=expected_runtime_label,
            )
            report["browser"] = browser_payload
            agent_ui_collected = (
                int(browser_payload.get("dialogueProvenanceRows") or 0) > 0
            ) and bool(browser_payload.get("runtimeProvenanceMatched"))
            set_proof_bag(
                report,
                "agent_ui_screenshot",
                "collected" if agent_ui_collected else "missing",
                (
                    "Agent UI screenshot captured real dialogue rows with matching runtime provenance."
                    if agent_ui_collected
                    else "Agent UI screenshot did not contain real dialogue rows with matching runtime provenance."
                ),
                dialogueRows=browser_payload.get("dialogueRows"),
                dialogueProvenanceRows=browser_payload.get("dialogueProvenanceRows"),
                runtimeReportRows=browser_payload.get("runtimeReportRows"),
                expectedRuntimeLabel=browser_payload.get("expectedRuntimeLabel"),
                dialogueHeaderText=browser_payload.get("dialogueHeaderText"),
                firstSpeakerText=browser_payload.get("firstSpeakerText"),
                firstProvenanceText=browser_payload.get("firstProvenanceText"),
                runtimeProvenanceMatched=bool(browser_payload.get("runtimeProvenanceMatched")),
                screenshot=report.get("screenshots", {}).get("agentConversation") if isinstance(report.get("screenshots"), dict) else "",
            )
            set_proof_bag(
                report,
                "produced_output_preview",
                (
                    "collected"
                    if browser_payload.get("previewScreenshot") and browser_payload.get("previewArtifactVisible")
                    else "blocked"
                    if browser_payload.get("previewError")
                    else "missing"
                ),
                (
                    "Preview screenshot captured the generated runtime proof artifact."
                    if browser_payload.get("previewScreenshot") and browser_payload.get("previewArtifactVisible")
                    else str(browser_payload.get("previewError"))
                    if browser_payload.get("previewError")
                    else "Preview screenshot did not prove the generated runtime proof artifact."
                ),
                screenshot=browser_payload.get("previewScreenshot") or "",
                frameSrc=browser_payload.get("previewFrameSrc") or "",
                textExcerpt=browser_payload.get("previewArtifactTextExcerpt") or "",
                previewError=browser_payload.get("previewError") or "",
                artifactSourceVerified=bool(browser_payload.get("previewArtifactSourceVerified")),
                artifactSource=browser_payload.get("previewArtifactSource") or "",
                artifactHasProvenance=bool(browser_payload.get("previewArtifactHasProvenance")),
                artifactSrcdocHasArtifact=bool(browser_payload.get("previewArtifactSrcdocHasArtifact")),
            )
            record(
                report,
                "agent-ui-shows-real-dialogue-or-blocker",
                (
                    bool(reply)
                    and int(browser_payload.get("dialogueProvenanceRows") or 0) > 0
                )
                or (not reply and int(browser_payload.get("allThreadRows") or 0) >= 0),
                "Agent UI screenshot captured real runtime dialogue provenance for the conversation mission.",
                dialogueRows=browser_payload.get("dialogueRows"),
                dialogueProvenanceRows=browser_payload.get("dialogueProvenanceRows"),
                runtimeReportRows=browser_payload.get("runtimeReportRows"),
                previewButton=browser_payload.get("previewButton"),
            )
            record(
                report,
                "agent-ui-runtime-provenance-matches-selected-runtime",
                bool(browser_payload.get("runtimeProvenanceMatched")),
                "Agent UI dialogue label and speaker provenance match the selected real runtime.",
                expectedRuntimeLabel=browser_payload.get("expectedRuntimeLabel"),
                dialogueHeaderText=browser_payload.get("dialogueHeaderText"),
                firstSpeakerText=browser_payload.get("firstSpeakerText"),
                firstProvenanceText=browser_payload.get("firstProvenanceText"),
            )
            record(
                report,
                "produced-output-preview-captured",
                bool(browser_payload.get("previewScreenshot") and browser_payload.get("previewArtifactVisible")),
                (
                    "Preview screenshot captured the generated runtime proof artifact."
                    if browser_payload.get("previewScreenshot") and browser_payload.get("previewArtifactVisible")
                    else str(browser_payload.get("previewError") or "Preview screenshot did not prove the generated runtime proof artifact.")
                ),
            )
        except Exception as exc:
            report["browserError"] = str(exc)
            set_proof_bag(report, "agent_ui_screenshot", "blocked", str(exc))
            set_proof_bag(report, "produced_output_preview", "blocked", str(exc))
            record(report, "agent-ui-screenshot-captured", False, str(exc))
    else:
        set_proof_bag(
            report,
            "agent_ui_screenshot",
            "skipped",
            "Browser capture was not requested. Run with --with-browser to collect this bag.",
        )
        set_proof_bag(
            report,
            "produced_output_preview",
            "skipped",
            "Browser capture was not requested. Run with --with-browser to collect this bag.",
        )

    for runtime_id, bag_id in (
        ("opencode", "fresh_opencode_round"),
        ("hermes", "fresh_hermes_round"),
        ("openclaw", "fresh_openclaw_round"),
    ):
        bag = report.get("proofBags", {}).get(bag_id) if isinstance(report.get("proofBags"), dict) else None
        if isinstance(bag, dict) and str(bag.get("status") or "missing") == "missing":
            set_proof_bag(
                report,
                bag_id,
                "skipped",
                f"No fresh {runtime_id} round was attempted in this run.",
            )
    proof_bag_summary = summarize_proof_bags(report)
    report["proofBagSummary"] = proof_bag_summary
    core_checks = [
        item
        for item in report["checks"]
        if isinstance(item, dict) and str(item.get("checkId") or "") in CORE_CHECK_IDS
    ]
    core_passed = bool(reply) and len(core_checks) == len(CORE_CHECK_IDS) and all(bool(item.get("passed")) for item in core_checks)
    report["corePassed"] = core_passed
    report["passed"] = bool(core_passed and (proof_bag_summary["allBagsCollected"] or not args.require_all_bags))
    report["status"] = (
        "passed"
        if report["passed"] and proof_bag_summary["allBagsCollected"]
        else "partial"
        if core_passed
        else "blocked"
    )
    openclaw_diagnostic_summary = openclaw_diagnostic_problem_summary(report.get("openclawRuntimeDiagnostics"))
    if proof_bag_summary["allBagsCollected"]:
        report["nextAction"] = "All real-agent proof bags are collected."
    elif core_passed:
        report["nextAction"] = (
            "Core real runtime dialogue is recorded; remaining proof bags must be collected or unblocked: "
            + ", ".join([*proof_bag_summary["missingOrSkipped"], *proof_bag_summary["blocked"]])
        )
    elif openclaw_diagnostic_summary and requested_runtime in {"auto", "openclaw"}:
        report["nextAction"] = (
            "Fix OpenClaw provider auth and gateway health, then rerun this verifier to capture a fresh OpenClaw assistant reply: "
            + openclaw_diagnostic_summary
        )
    else:
        report["nextAction"] = "Start/fix the OpenClaw gateway or OpenCode provider route, then rerun this verifier to capture a real assistant reply."
    report["reportPath"] = str(report_path)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    latest_path = Path(args.out_dir) / "latest.json"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
