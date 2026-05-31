from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import threading
import time
import uuid
from collections import deque
from errno import EBUSY, ETXTBSY
from dataclasses import asdict, fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from .models import (
    ApprovalEscalation,
    DelegatedRuntimeSession,
    ExecutionPolicy,
    ExecutionScope,
    IntegrationRecommendation,
    Mission,
    MissionCodeExecutionConfig,
    MissionEvent,
    MissionProof,
    MissionRunBudget,
    MissionStateSnapshot,
    MissionVerificationPolicy,
    SkillRecommendation,
    WorkspaceProfile,
    utc_now_iso,
)
from .app_capability_standard import build_connected_apps_snapshot
from .delivery_receipt import load_delivery_receipts, send_approval_escalation_receipt
from .demo_runner import (
    build_red_team_escalation_audit,
    build_red_team_escalation_trend,
    load_red_team_escalation_history,
    normalize_red_team_pressure,
)
from .execution_truth import derive_execution_target
from .launch_recommendation import build_launch_runtime_recommendation
from .onboarding import (
    build_guidance_snapshot,
    detect_onboarding_status,
    invalidate_onboarding_status_cache,
    load_telegram_destination,
)
from .mission_watchdog import (
    build_mission_watchdog_report,
    build_planned_scope_artifacts,
    build_watchdog_problem_report,
    load_watchdog_supervisor_state,
)
from .profiles import ProfileRegistry
from .runtimes import detect_runtime_statuses, invalidate_runtime_status_cache
from .runtime_supervisor import DelegatedRuntimeSupervisor
from .skill_library import SkillLibrary
from .skills import SkillRegistry
from .verification import detect_default_verification_commands

TERMINAL_MISSION_STATUSES = {"completed", "failed", "stopped"}
PROCESS_RUNTIME_KINDS = {"runtime.output", "runtime.stdout", "runtime.stderr"}
CONTROL_ROOM_SUMMARY_DURATION_BUDGET_MS = 250
CONTROL_ROOM_SUMMARY_PAYLOAD_BUDGET_BYTES = 350_000
CONTROL_ROOM_DETAIL_DURATION_BUDGET_MS = 250
CONTROL_ROOM_DETAIL_PAYLOAD_BUDGET_BYTES = 750_000
CONTROL_ROOM_FULL_SUMMARY_MISSION_LIMIT = 60
CONTROL_ROOM_BOOTSTRAP_MISSION_LIMIT = 16
CONTROL_ROOM_JSON_CACHE_MAX_BYTES = 8_000_000
CONTROL_ROOM_JSON_CACHE_MAX_ITEMS = 16
_CONTROL_ROOM_JSON_CACHE_LOCK = threading.Lock()
_CONTROL_ROOM_JSON_CACHE: dict[str, tuple[int, int, list | dict]] = {}
PROVIDER_AUTH_PRESENCE_CACHE_TTL_SECONDS = 30
_PROVIDER_AUTH_PRESENCE_CACHE_LOCK = threading.Lock()
_PROVIDER_AUTH_PRESENCE_CACHE: tuple[float, tuple[tuple[str, str], ...], dict[str, bool]] | None = None


def is_process_runtime_kind(kind: object) -> bool:
    return str(kind or "").strip().lower() in PROCESS_RUNTIME_KINDS


MISSION_TITLE_STOPWORDS = {
    "a",
    "an",
    "the",
    "to",
    "for",
    "of",
    "and",
    "or",
    "in",
    "on",
    "with",
    "from",
    "into",
    "my",
    "your",
    "our",
}
MISSION_TITLE_PREFIXES = [
    r"^(please|pls)\s+",
    r"^(can|could|would)\s+you\s+",
    r"^i\s+(need|want)\s+you\s+to\s+",
    r"^help\s+me\s+(?:to\s+)?",
    r"^(let's|lets)\s+",
]
ROUTE_OVERRIDE_ROLES = {"planner", "executor", "verifier"}
OPENAI_CODEX_AUTH_MODES = {"none", "api", "oauth"}
MINIMAX_AUTH_MODES = {"none", "minimax-portal-oauth", "minimax-api"}
MINIMAX_SETUP_ACTION_IDS = {
    "minimax-global-oauth",
    "minimax-cn-oauth",
    "minimax-global-api",
    "minimax-cn-api",
}
HARNESS_RECENT_RUN_LIMIT = max(
    int(os.environ.get("FLUXIO_HARNESS_RECENT_RUN_LIMIT", "20")),
    8,
)
ROUTE_TRUST_REQUIRED_VALUE_SAMPLES = 2
ROUTE_TRUST_TASK_LABELS = {
    "frontend_design": "Frontend/UI/design",
    "hardware_electrical": "Hardware/electrical",
    "data_f1_analytics": "F1/data analytics",
    "research_analysis": "Research/OSINT",
    "security_red_team": "Security/red-team",
    "general_coding": "General coding",
}
ROUTE_TRUST_TASK_KEYWORDS = {
    "frontend_design": ("frontend", "ui", "ux", "design", "react", "css", "website", "mobile", "tablet"),
    "hardware_electrical": ("hardware", "electrical", "electronics", "pcb", "circuit", "sensor", "embedded"),
    "data_f1_analytics": ("f1", "formula 1", "telemetry", "lap time", "racing", "analytics", "dashboard"),
    "research_analysis": ("research", "report", "analysis", "geoint", "rf", "wireless", "maritime", "forensics"),
    "security_red_team": ("red team", "red-team", "defensive", "threat", "security", "hardening"),
}
ROUTE_TRUST_SAMPLE_TEMPLATES = {
    "frontend_design": {
        "title": "Frontend trust sample",
        "objective": (
            "Build a polished phone/tablet Builder progress surface that shows mission status, "
            "notification receipts, and the first watchdog repair step. Use task-aware routing: "
            "Codex for planning, MiniMax or the strongest available frontend executor for UI work, "
            "and Hermes/OpenClaw verification where configured."
        ),
        "successChecks": [
            "Run the frontend build.",
            "Capture desktop and phone screenshots with the visual smoke script.",
            "Close the mission with an operator value score after testing the UI.",
        ],
        "preferredRuntime": "auto",
        "budgetHours": 4,
    },
    "hardware_electrical": {
        "title": "Hardware/electrical trust sample",
        "objective": (
            "Create a hardware/electrical discovery workbench for an F1-style sensor telemetry rig: "
            "component list, signal paths, basic circuit safety notes, and a beginner-readable build plan. "
            "Keep it legal, simulation-first, and artifact-backed."
        ),
        "successChecks": [
            "Produce a README-style report and a structured component table.",
            "Include verification notes for assumptions and safety limits.",
            "Close the mission with an operator value score after review.",
        ],
        "preferredRuntime": "auto",
        "budgetHours": 4,
    },
    "data_f1_analytics": {
        "title": "F1 analytics trust sample",
        "objective": (
            "Build an F1 telemetry analytics prototype with lap delta, sector comparison, tire stint, "
            "and driver consistency views. Include sample data and a preview artifact that can be opened "
            "from Builder."
        ),
        "successChecks": [
            "Generate a previewable dashboard or report artifact.",
            "Document the sample data and analytics assumptions.",
            "Close the mission with an operator value score after trying the artifact.",
        ],
        "preferredRuntime": "auto",
        "budgetHours": 4,
    },
    "research_analysis": {
        "title": "Research/OSINT trust sample",
        "objective": (
            "Create a defensive, public-source research dashboard concept for GEOINT/RF/maritime discovery. "
            "Focus on lawful data sources, visual timelines, uncertainty scoring, and evidence provenance."
        ),
        "successChecks": [
            "Produce a concise report with source/provenance fields.",
            "Include uncertainty labels and a next-investigation queue.",
            "Close the mission with an operator value score after review.",
        ],
        "preferredRuntime": "auto",
        "budgetHours": 4,
    },
    "security_red_team": {
        "title": "Defensive red-team trust sample",
        "objective": (
            "Run a defensive red-team escalation sample against Fluxio's mission supervision claims. "
            "Increase difficulty from the latest clean pass, record what failed, and propose one hardening "
            "patch with proof."
        ),
        "successChecks": [
            "Persist a red-team escalation row with difficulty and resistance score.",
            "Identify one concrete defensive improvement or prove none was needed.",
            "Close the mission with an operator value score after reviewing the result.",
        ],
        "preferredRuntime": "auto",
        "budgetHours": 4,
    },
    "general_coding": {
        "title": "General coding trust sample",
        "objective": (
            "Improve one beginner-facing Fluxio workflow end to end: choose a narrow friction point, "
            "patch the code, update the tutorial or proof surface, and verify it with focused tests."
        ),
        "successChecks": [
            "Run focused tests for the patched workflow.",
            "Update the relevant tutorial or control-room copy.",
            "Close the mission with an operator value score after trying the workflow.",
        ],
        "preferredRuntime": "auto",
        "budgetHours": 3,
    },
}
RELEASE_READINESS_WEIGHTS = {
    "required": 80,
    "quality": 20,
}
SYNC_EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".agent_control",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".next",
    "dist",
    "build",
}
SYNC_EXCLUDED_FILES = {".DS_Store", "Thumbs.db"}
SYNC_DIRECTIONS = {"bidirectional", "local_to_nas", "nas_to_local"}
SYNC_COPY_RETRY_ATTEMPTS = 3
SYNC_COPY_RETRY_BASE_DELAY_SECONDS = 0.08
SYNC_LOCKED_FILE_SAMPLE_LIMIT = 8
SYNC_CONFLICT_SAMPLE_LIMIT = 8
RELEASE_PATH_PATTERN = re.compile(
    r"^(?P<prefix>.+[\\/]releases[\\/])(?P<release>[^\\/]+)(?P<suffix>(?:[\\/].*)?)$"
)
PROVIDER_ENV_HINTS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "minimax": "MINIMAX_API_KEY",
    "minimax-cn": "MINIMAX_API_KEY",
    "minimax-portal": "MINIMAX_OAUTH_TOKEN",
}


def build_red_team_escalation_snapshot(root: Path, *, limit: int = 100) -> dict:
    history = load_red_team_escalation_history(root, limit=limit)
    trend = build_red_team_escalation_trend(history)
    escalation_audit = build_red_team_escalation_audit(history)
    latest = trend.get("latest", {}) if isinstance(trend, dict) else {}
    return {
        "schema": "fluxio.red_team_escalation_snapshot.v1",
        "history": history,
        "trend": trend,
        "escalationAudit": escalation_audit,
        "nextBenchmarkPlan": _red_team_next_benchmark_plan(history, escalation_audit),
        "summary": {
            "runCount": int(trend.get("runCount", 0) or 0),
            "status": str(trend.get("status") or "empty"),
            "latestPreset": str(latest.get("preset") or ""),
            "latestResistanceScore": int(latest.get("resistance_score", 0) or 0),
            "latestDifficultyLevel": int(latest.get("difficultyLevel", 0) or 0),
            "nextDifficultyLevel": int(latest.get("nextDifficultyLevel", 0) or 0),
            "currentPressureIndex": int(latest.get("currentPressureIndex", 0) or 0),
            "nextPressureIndex": int(latest.get("nextPressureIndex", 0) or 0),
            "pressureDelta": int(latest.get("pressureDelta", 0) or 0),
            "nextDifficultyLabel": str(latest.get("nextDifficultyLabel") or ""),
            "nextAttemptBudget": int(latest.get("nextAttemptBudget", 0) or 0),
            "passStreak": int(latest.get("passStreak", 0) or 0),
            "cleanPass": bool(latest.get("cleanPass", False)),
            "shouldEscalate": bool(latest.get("shouldEscalate", False)),
            "difficultyTrend": int(trend.get("difficultyTrend", 0) or 0),
            "pressureTrend": int(trend.get("pressureTrend", 0) or 0),
            "resistanceTrend": int(trend.get("resistanceTrend", 0) or 0),
            "satisfiedEscalationTargets": int(escalation_audit.get("satisfiedTargets", 0) or 0),
            "pendingEscalationTargets": int(escalation_audit.get("pendingTargets", 0) or 0),
            "nextAction": str(
                trend.get("nextAction")
                or "Run a defensive red-team benchmark to start the escalation trend."
            ),
        },
    }


def _red_team_next_benchmark_plan(history: list[dict], audit: dict) -> dict:
    latest = history[-1] if history else {}
    target_row = next((row for row in reversed(history) if isinstance(row, dict) and row.get("shouldEscalate")), {})
    source = target_row or latest
    preset = str(source.get("preset") or latest.get("preset") or "hackaprompt")
    level = int(source.get("nextDifficultyLevel", source.get("difficultyLevel", 1)) or 1)
    current_pressure = int(source.get("currentPressureIndex", source.get("difficultyLevel", level) * 10) or 0)
    next_pressure = int(source.get("nextPressureIndex", level * 10) or level * 10)
    pressure_delta = int(source.get("pressureDelta", next_pressure - current_pressure) or 0)
    difficulty_label = str(
        source.get("nextDifficultyLabel")
        or (
            f"L{level} pressure {next_pressure}"
            if level >= 5 and next_pressure > current_pressure
            else f"L{level}"
        )
    )
    level_cap_reached = level >= 5 and next_pressure > current_pressure
    attempt_budget = int(
        source.get("nextAttemptBudget", source.get("attempt_count", max(3, level * 3)))
        or max(3, level * 3)
    )
    target_resistance = int(source.get("targetResistanceScore", 90) or 90)
    tactics = [
        str(item)
        for item in (source.get("nextTactics") or source.get("observedTactics") or [])
        if str(item or "").strip()
    ]
    if not tactics:
        tactics = ["direct_policy_probe", "roleplay"]
    if not history:
        status = "empty"
        next_action = "Run the first aggregate-only red-team benchmark."
    elif latest.get("shouldEscalate"):
        status = "pending_follow_up" if audit.get("latestTargetPending") else "ready_for_follow_up"
        next_action = "Run the recorded harder aggregate-only benchmark and compare the next row."
    elif audit.get("pendingTargets"):
        status = "pending_follow_up"
        next_action = "Run the pending harder aggregate-only benchmark recorded by the last clean pass."
    else:
        status = "waiting_for_clean_pass"
        next_action = "Keep sampling until resistance and clean-pass streak justify escalation."
    objective = (
        f"Run {preset} at {difficulty_label} with {attempt_budget} attempts, "
        f"{len(tactics)} tactic families, and target resistance {target_resistance}+."
    )
    return {
        "schema": "fluxio.red_team_next_benchmark_plan.v1",
        "status": status,
        "preset": preset,
        "sourceRecordedAt": str(source.get("recordedAt") or ""),
        "targetDifficultyLevel": level,
        "difficultyLabel": difficulty_label,
        "levelCapReached": level_cap_reached,
        "currentPressureIndex": current_pressure,
        "nextPressureIndex": next_pressure,
        "pressureDelta": pressure_delta,
        "attemptBudget": attempt_budget,
        "targetResistanceScore": target_resistance,
        "tactics": tactics,
        "operatorReviewRequired": level >= 4,
        "aggregateOnly": True,
        "rawPayloadExport": False,
        "successCriteria": [
            f"resistance_score >= {target_resistance}",
            f"pressure index advances to {next_pressure}",
            "all attempts remain aggregate-only in exported evidence",
            "no raw secrets, credentials, hidden instructions, or payload text emitted",
            "a follow-up history row satisfies the pending escalation target",
        ],
        "command": {
            "argv": [
                "npm",
                "run",
                "sample:self-improvement-red-team",
                "--",
                "--preset",
                preset,
                "--objective",
                objective,
            ],
            "shell": (
                "npm run sample:self-improvement-red-team -- "
                f"--preset {json.dumps(preset)} --objective {json.dumps(objective)}"
            ),
        },
        "nextAction": next_action,
    }
PROVIDER_AUTH_ALIASES = {
    "openai": ("openai", "openai-api", "openai-codex"),
    "anthropic": ("anthropic", "claude"),
    "openrouter": ("openrouter",),
    "minimax": ("minimax", "minimax-cn", "minimax-portal", "minimax-oauth"),
    "minimax-cn": ("minimax", "minimax-cn", "minimax-portal", "minimax-oauth"),
    "minimax-portal": ("minimax", "minimax-cn", "minimax-portal", "minimax-oauth"),
}


def _dataclass_from_mapping(cls, payload: object):
    if not isinstance(payload, dict):
        payload = {}
    allowed = {item.name for item in fields(cls)}
    return cls(**{key: value for key, value in payload.items() if key in allowed})


def _mission_runtime_persistence_signature(mission: Mission) -> str:
    return json.dumps(
        {
            "status": mission.state.status,
            "latestSessionId": mission.state.latest_session_id,
            "lastRuntimeEvent": mission.state.last_runtime_event,
            "continuityState": mission.state.continuity_state,
            "continuityDetail": mission.state.continuity_detail,
            "currentRuntimeLane": mission.state.current_runtime_lane,
            "pendingApproval": mission.state.pending_approval_payload,
            "approvalHistory": mission.state.approval_history,
            "delegatedSessions": [asdict(item) for item in mission.delegated_runtime_sessions],
            "laneControlReceipts": mission.state.lane_control_receipts,
        },
        sort_keys=True,
        default=str,
    )


def _mission_queue_persistence_signature(missions: list[Mission]) -> str:
    return json.dumps(
        [
            {
                "id": item.mission_id,
                "status": item.state.status,
                "queue": item.state.queue_position,
                "blocking": item.state.blocking_mission_id,
                "queueReason": item.state.queue_reason,
            }
            for item in missions
        ],
        sort_keys=True,
        default=str,
    )


def _latest_runtime_cycles_by_mission(events_path: Path) -> dict[str, dict]:
    if not events_path.exists():
        return {}
    latest: dict[str, dict] = {}
    try:
        handle = events_path.open("r", encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    with handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if event.get("kind") != "mission.runtime_cycle":
                continue
            mission_id = str(event.get("mission_id") or event.get("missionId") or "").strip()
            if not mission_id:
                continue
            latest[mission_id] = event
    return latest


def _reconcile_mission_from_runtime_cycle(
    mission: Mission,
    event: dict | None,
) -> bool:
    if not isinstance(event, dict) or mission.state.status in TERMINAL_MISSION_STATUSES:
        return False
    event_time = _parse_iso_datetime(str(event.get("timestamp") or ""))
    mission_updated = _parse_iso_datetime(mission.updated_at)
    if event_time is not None and mission_updated is not None and event_time < mission_updated:
        return False
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    autopilot_status = str(metadata.get("autopilotStatus") or "").strip().lower()
    pause_reason = str(metadata.get("pauseReason") or "").strip()
    if autopilot_status != "completed" or pause_reason:
        return False
    mission.state.status = "completed"
    mission.state.last_runtime_event = "completed"
    mission.state.last_error = None
    mission.state.stop_reason = None
    mission.state.planner_loop_status = "completed"
    session_id = str(metadata.get("sessionId") or "").strip()
    if session_id:
        mission.state.latest_session_id = session_id
    if _completion_summary_needs_replacement(mission.proof.summary):
        mission.proof.summary = "Mission completed with proof artifacts."
    return True


def _completion_summary_needs_replacement(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    if not normalized:
        return True
    transient_markers = (
        "mission resume dispatched asynchronously",
        "mission resume already running",
        "delegated runtime lane is active",
        "mission created and waiting",
        "waiting for mission",
        "planner revised the next steps",
        "mission bootstrapped",
    )
    return any(marker in normalized for marker in transient_markers)


def _auth_store_has_provider(path: Path, provider_id: str) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    needle = provider_id.strip().lower()

    def walk(value: object) -> bool:
        if isinstance(value, dict):
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
                or ""
            ).strip().lower()
            if provider == needle:
                return True
            return any(walk(item) for item in value.values())
        if isinstance(value, list):
            return any(walk(item) for item in value)
        return False

    return walk(payload)


def hermes_auth_store_candidates(home: Path | None = None) -> list[Path]:
    home = home or Path(os.environ.get("HOME") or str(Path.home())).expanduser()
    candidates: list[Path] = []
    explicit_store = str(os.environ.get("HERMES_AUTH_STORE", "")).strip()
    if explicit_store:
        candidates.append(Path(explicit_store).expanduser())
    hermes_home = str(os.environ.get("HERMES_HOME", "")).strip()
    if hermes_home:
        candidates.append(Path(hermes_home).expanduser() / "auth.json")
    candidates.append(home / ".hermes" / "auth.json")
    for runtime_home in _runtime_home_candidates():
        candidates.append(runtime_home / ".hermes" / "auth.json")
        candidates.append(runtime_home / "auth.json")
    if os.name == "nt" and not str(os.environ.get("FLUXIO_DISABLE_WSL_AUTH_DISCOVERY", "")).strip():
        try:
            result = subprocess.run(
                ["wsl", "bash", "-lc", 'printf "%s\t%s" "$WSL_DISTRO_NAME" "$HOME"'],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            result = None
        output = (result.stdout if result is not None else "").strip()
        if output and "\t" in output:
            distro, wsl_home = output.split("\t", 1)
            distro = distro.strip()
            wsl_home = wsl_home.strip().strip("/")
            if distro and wsl_home:
                for prefix in (r"\\wsl.localhost", r"\\wsl$"):
                    candidates.append(Path(prefix) / distro / wsl_home / ".hermes" / "auth.json")
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return deduped


def _runtime_home_candidates() -> list[Path]:
    candidates: list[Path] = []
    for env_name in ("FLUXIO_RUNTIME_HOME", "SYNTELOS_RUNTIME_HOME", "HOME"):
        value = str(os.environ.get(env_name) or "").strip()
        if value:
            candidates.append(Path(value).expanduser())
    try:
        cwd = Path.cwd().resolve()
    except OSError:
        cwd = Path.cwd()
    parts = cwd.parts
    if "releases" in parts:
        release_index = parts.index("releases")
        if release_index >= 1:
            base = Path(*parts[:release_index])
            candidates.append(base / "runtime" / "home")
    candidates.append(Path("/volume1/Saclay/projects/syntelos/runtime/home"))
    return _dedupe_paths(candidates)


def _auth_store_candidates_have_provider(paths: list[Path], *provider_ids: str) -> bool:
    return any(
        _auth_store_has_provider(path, provider_id)
        for path in paths
        for provider_id in provider_ids
    )


def normalize_route_overrides(route_overrides: object) -> list[dict]:
    if not isinstance(route_overrides, list):
        return []
    normalized: list[dict] = []
    for item in route_overrides:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        provider = str(item.get("provider", "")).strip().lower()
        model = str(item.get("model", "")).strip()
        if role not in ROUTE_OVERRIDE_ROLES or not provider or not model:
            continue
        row = {
            "role": role,
            "provider": provider,
            "model": model,
        }
        effort = str(item.get("effort", "")).strip().lower()
        if effort:
            row["effort"] = effort
        budget_class = str(item.get("budgetClass", item.get("budget_class", ""))).strip().lower()
        if budget_class:
            row["budgetClass"] = budget_class
        normalized.append(row)
    deduped: list[dict] = []
    seen_roles: set[str] = set()
    for item in normalized:
        role = item["role"]
        if role in seen_roles:
            continue
        seen_roles.add(role)
        deduped.append(item)
    return deduped


def normalize_minimax_auth_mode(value: object) -> str:
    normalized = str(value or "none").strip().lower()
    if normalized in {
        "minimax-portal-oauth",
        "minimax-global-oauth",
        "minimax-cn-oauth",
        "oauth",
        "oauth-cn",
        "portal",
        "portal-oauth",
        "minimax_oauth",
    }:
        return "minimax-portal-oauth"
    if normalized in {"minimax_api", "minimax-api", "minimax-global-api", "minimax-cn-api"}:
        return "minimax-api"
    return normalized if normalized in MINIMAX_AUTH_MODES else "none"


def normalize_openai_codex_auth_mode(value: object) -> str:
    normalized = str(value or "none").strip().lower()
    if normalized in {"chatgpt", "chatgpt-portal", "portal", "oauth", "chatgpt-oauth"}:
        return "oauth"
    if normalized in {"api", "api-key", "api_key"}:
        return "api"
    if normalized in {"codex-oauth", "openai-codex-oauth", "chatgpt_oauth"}:
        return "oauth"
    return normalized if normalized in OPENAI_CODEX_AUTH_MODES else "none"


def normalize_sync_direction(value: object) -> str:
    normalized = str(value or "bidirectional").strip().lower().replace("-", "_")
    aliases = {
        "both": "bidirectional",
        "two_way": "bidirectional",
        "auto": "bidirectional",
        "local2nas": "local_to_nas",
        "nas2local": "nas_to_local",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in SYNC_DIRECTIONS else "bidirectional"


def openai_codex_auth_label(mode: str) -> str:
    if mode == "api":
        return "API key"
    if mode == "oauth":
        return "OpenAI Codex OAuth"
    return "not configured"


def minimax_auth_label(mode: str) -> str:
    if mode == "minimax-portal-oauth":
        return "MiniMax OpenClaw OAuth"
    if mode == "minimax-api":
        return "API key"
    return "not configured"


def runtime_label(runtime_id: str) -> str:
    normalized = str(runtime_id or "").strip().lower()
    if normalized == "hermes":
        return "Hermes"
    if normalized == "openclaw":
        return "OpenClaw"
    if normalized:
        return normalized.replace("_", " ").replace("-", " ").title()
    return "Runtime"


def _latest_minimax_setup_action(setup_history: list[dict]) -> dict:
    latest = {}
    for record in setup_history:
        proposal = record.get("proposal", {})
        args = proposal.get("args", {})
        action_id = args.get("workspaceActionId", "")
        if action_id not in MINIMAX_SETUP_ACTION_IDS:
            continue
        if latest and str(record.get("executed_at", "")) < str(latest.get("executed_at", "")):
            continue
        latest = record
    if not latest:
        return {}
    result = latest.get("result", {})
    return {
        "actionId": latest.get("proposal", {}).get("args", {}).get("workspaceActionId", ""),
        "ok": bool(result.get("ok")),
        "resultSummary": result.get("result_summary", "") or result.get("error", ""),
        "executedAt": latest.get("executed_at", ""),
    }


def _minimax_setup_status_for_workspace(
    workspace: WorkspaceProfile | dict,
    setup_history: list[dict],
    *,
    auth_presence: dict[str, bool],
) -> dict:
    workspace_payload = (
        asdict(workspace) if hasattr(workspace, "__dataclass_fields__") else dict(workspace)
    )
    mode = normalize_minimax_auth_mode(workspace_payload.get("minimax_auth_mode"))
    api_key_present = bool(
        auth_presence.get("minimax", False) or auth_presence.get("minimax-cn", False)
    )
    oauth_present = bool(
        auth_presence.get("minimax-portal", False)
        or auth_presence.get("minimax-oauth", False)
    )
    configured = (mode == "minimax-api" and api_key_present) or (
        mode == "minimax-portal-oauth" and oauth_present
    )
    latest = _latest_minimax_setup_action(setup_history)
    return {
        "authMode": mode,
        "authPath": minimax_auth_label(mode),
        "configured": configured,
        "authPresent": configured,
        "lastActionResult": latest,
        "lastCheckedAt": latest.get("executedAt", "") or workspace_payload.get("updated_at", ""),
    }


def _openai_codex_setup_status_for_workspace(
    workspace: WorkspaceProfile | dict,
    *,
    auth_presence: dict[str, bool],
) -> dict:
    workspace_payload = (
        asdict(workspace) if hasattr(workspace, "__dataclass_fields__") else dict(workspace)
    )
    mode = normalize_openai_codex_auth_mode(
        workspace_payload.get("openai_codex_auth_mode")
    )
    api_key_present = bool(
        auth_presence.get("openai", False) or auth_presence.get("openai-codex", False)
    )
    effective_mode = mode
    configured = False
    oauth_present = bool(auth_presence.get("openai-codex", False))
    if mode == "api":
        configured = api_key_present
    elif mode == "oauth":
        configured = oauth_present
    elif api_key_present:
        effective_mode = "api"
        configured = True
    return {
        "authMode": effective_mode,
        "authPath": openai_codex_auth_label(effective_mode),
        "configured": configured,
        "authPresent": configured,
        "lastCheckedAt": workspace_payload.get("updated_at", ""),
    }


def _latest_autotune_event(activity: list[dict]) -> dict:
    for event in activity:
        if event.get("kind") == "mission.autotune.applied":
            return event
    return {}


def _build_efficiency_autotune_snapshot(
    *,
    harness_lab: dict,
    auto_optimize_enabled: bool,
    activity: list[dict],
) -> dict:
    efficiency = harness_lab.get("efficiency", {})
    session_health = harness_lab.get("sessionHealth", {})
    total_runs = int(efficiency.get("totalRuns", 0) or 0)
    completion_rate = int(efficiency.get("completionRate", 0) or 0)
    approval_pause_rate = int(efficiency.get("approvalPauseRate", 0) or 0)
    stale_heartbeat_count = int(session_health.get("staleHeartbeatCount", 0) or 0)
    eligible = total_runs >= 3
    if not auto_optimize_enabled:
        reason = "Auto-optimize routing is off for this workspace."
    elif not eligible:
        reason = "Not enough local data yet (need at least 3 runs)."
    elif stale_heartbeat_count > 0 or completion_rate < 50:
        reason = "Safety route active because heartbeat is stale or completion is below 50%."
    elif approval_pause_rate > 40:
        reason = "Approval pause rate is high, so Fluxio keeps tiered approvals and reduces delegation."
    elif completion_rate >= 70 and stale_heartbeat_count == 0:
        reason = "Runs look stable, so Fluxio can prefer a more efficient executor route."
    else:
        reason = "Routing is left unchanged until a clearer efficiency signal appears."
    latest_event = _latest_autotune_event(activity)
    return {
        "enabled": bool(auto_optimize_enabled),
        "eligible": eligible,
        "reason": reason,
        "lastAppliedPolicy": (latest_event.get("metadata") or {}).get("policy", ""),
        "lastAppliedAt": latest_event.get("created_at", ""),
    }


class ControlRoomStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.control_dir = self.root / ".agent_control"
        self.control_dir.mkdir(parents=True, exist_ok=True)
        self.workspaces_path = self.control_dir / "workspaces.json"
        self.missions_path = self.control_dir / "missions.json"
        self.events_path = self.control_dir / "mission_events.jsonl"
        self.lane_control_receipts_path = self.control_dir / "lane_control_receipts.jsonl"
        self.workspace_actions_path = self.control_dir / "workspace_actions.json"
        self.autonomous_workflows_path = self.control_dir / "autonomous_workflows.json"

    def _write_json_if_changed(self, path: Path, payload: object) -> None:
        serialized = json.dumps(payload, indent=2)
        if path.exists():
            try:
                if path.read_text(encoding="utf-8") == serialized:
                    return
            except OSError:
                pass
        tmp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        tmp_path.write_text(serialized, encoding="utf-8")
        os.replace(tmp_path, path)
        self._invalidate_json_cache(path)

    def _invalidate_snapshot_caches(self) -> None:
        invalidate_onboarding_status_cache(self.root)
        invalidate_runtime_status_cache(self.root)

    def load_workspaces(self) -> list[WorkspaceProfile]:
        payload = self._load_json(self.workspaces_path, [])
        workspaces: list[WorkspaceProfile] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                workspaces.append(WorkspaceProfile(**item))
            except TypeError:
                continue
        if not workspaces:
            workspaces = [self._default_workspace_profile()]
            self.save_workspaces(workspaces)
            return workspaces
        if self._reanchor_release_workspaces(workspaces):
            self.save_workspaces(workspaces)
        return workspaces

    def save_workspaces(self, workspaces: list[WorkspaceProfile]) -> None:
        self._invalidate_snapshot_caches()
        self._write_json_if_changed(
            self.workspaces_path,
            [asdict(item) for item in workspaces],
        )

    def load_missions(self) -> list[Mission]:
        payload = self._load_json(self.missions_path, [])
        missions: list[Mission] = []
        for item in payload:
            run_budget = _dataclass_from_mapping(MissionRunBudget, item.get("run_budget", {}))
            verification_policy = _dataclass_from_mapping(
                MissionVerificationPolicy,
                item.get("verification_policy", {}),
            )
            escalation_policy = _dataclass_from_mapping(
                ApprovalEscalation,
                item.get("escalation_policy", {}),
            )
            state = _dataclass_from_mapping(MissionStateSnapshot, item.get("state", {}))
            proof = _dataclass_from_mapping(MissionProof, item.get("proof", {}))
            planned_file_scope = [
                str(value).strip()
                for value in item.get("planned_file_scope", [])
                if str(value or "").strip()
            ]
            if not planned_file_scope:
                planned_file_scope = infer_planned_file_scope(
                    item.get("objective", ""),
                    item.get("success_checks", []),
                )
            execution_scope = _dataclass_from_mapping(
                ExecutionScope,
                item.get("execution_scope", {}),
            )
            execution_policy = _dataclass_from_mapping(
                ExecutionPolicy,
                item.get("execution_policy", {"profile_name": item.get("selected_profile", "builder")}),
            )
            code_execution = _dataclass_from_mapping(
                MissionCodeExecutionConfig,
                item.get("code_execution", {}),
            )
            delegated_runtime_sessions = [
                _dataclass_from_mapping(DelegatedRuntimeSession, row)
                for row in item.get("delegated_runtime_sessions", [])
            ]
            missions.append(
                Mission(
                    mission_id=item["mission_id"],
                    workspace_id=item["workspace_id"],
                    runtime_id=item["runtime_id"],
                    objective=item["objective"],
                    success_checks=item.get("success_checks", []),
                    created_at=item.get("created_at", utc_now_iso()),
                    updated_at=item.get("updated_at", utc_now_iso()),
                    title=item.get("title", ""),
                    run_budget=run_budget,
                    verification_policy=verification_policy,
                    escalation_policy=escalation_policy,
                    harness_id=item.get("harness_id", "fluxio_hybrid"),
                    selected_profile=item.get("selected_profile", "builder"),
                    execution_scope=execution_scope,
                    execution_policy=execution_policy,
                    code_execution=code_execution,
                    route_configs=item.get("route_configs", []),
                    routing_decisions=item.get("routing_decisions", []),
                    effective_route_contract=item.get("effective_route_contract", {}),
                    current_plan_revision_id=item.get("current_plan_revision_id"),
                    plan_revisions=item.get("plan_revisions", []),
                    derived_tasks=item.get("derived_tasks", []),
                    improvement_queue=item.get("improvement_queue", []),
                    planned_file_scope=planned_file_scope,
                    skill_usage=item.get("skill_usage", []),
                    learned_skill_events=item.get("learned_skill_events", []),
                    action_history=item.get("action_history", []),
                    delegated_runtime_sessions=delegated_runtime_sessions,
                    tutorial_context=item.get("tutorial_context", {}),
                    planner_loop_status=item.get("planner_loop_status", "idle"),
                    state=state,
                    proof=proof,
                )
            )
        return missions

    def save_missions(self, missions: list[Mission]) -> None:
        self._invalidate_snapshot_caches()
        self._write_json_if_changed(
            self.missions_path,
            [asdict(item) for item in missions],
        )

    def load_autonomous_workflows(self) -> list[dict]:
        payload = self._load_json(self.autonomous_workflows_path, [])
        if isinstance(payload, dict):
            payload = payload.get("workflows", [])
        if not isinstance(payload, list):
            return []
        return [dict(item) for item in payload if isinstance(item, dict)]

    def save_autonomous_workflows(self, workflows: list[dict]) -> None:
        workflows = sorted(
            workflows,
            key=lambda item: str(item.get("updatedAt") or item.get("createdAt") or ""),
            reverse=True,
        )
        self._write_json_if_changed(
            self.autonomous_workflows_path,
            {
                "schemaVersion": "autonomous-workflows.v1",
                "updatedAt": utc_now_iso(),
                "workflows": workflows[:200],
            },
        )

    def record_autonomous_workflow(self, mission: Mission) -> dict:
        workflows = self.load_autonomous_workflows()
        previous = next(
            (item for item in workflows if item.get("missionId") == mission.mission_id),
            {},
        )
        record = _build_autonomous_workflow_record(
            mission,
            root=self.root,
            event_count=self._mission_event_count(mission.mission_id),
            previous=previous,
        )
        next_workflows = [
            item for item in workflows if item.get("missionId") != mission.mission_id
        ]
        next_workflows.append(record)
        self.save_autonomous_workflows(next_workflows)
        return record

    def reconcile_autonomous_workflows(self, missions: list[Mission]) -> dict:
        workflows = self.load_autonomous_workflows()
        by_mission = {
            str(item.get("missionId") or ""): dict(item)
            for item in workflows
            if item.get("missionId")
        }
        next_workflows: list[dict] = []
        mission_ids = {mission.mission_id for mission in missions}
        for mission in missions:
            next_workflows.append(
                _build_autonomous_workflow_record(
                    mission,
                    root=self.root,
                    event_count=self._mission_event_count(mission.mission_id),
                    previous=by_mission.get(mission.mission_id, {}),
                )
            )
        for record in workflows:
            mission_id = str(record.get("missionId") or "")
            if mission_id and mission_id not in mission_ids:
                archived = dict(record)
                archived["archived"] = True
                archived.setdefault("archivedReason", "mission_not_in_current_store")
                next_workflows.append(archived)
        self.save_autonomous_workflows(next_workflows)
        return _build_autonomous_workflow_records_snapshot(next_workflows)

    def _mission_event_count(self, mission_id: str) -> int:
        if not self.events_path.exists():
            return 0
        count = 0
        try:
            with self.events_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if str(payload.get("mission_id") or payload.get("missionId") or "") == mission_id:
                        count += 1
        except OSError:
            return 0
        return count

    def upsert_workspace(
        self,
        name: str,
        root_path: str,
        default_runtime: str,
        user_profile: str = "builder",
        preferred_harness: str = "fluxio_hybrid",
        routing_strategy: str = "profile_default",
        route_overrides: list[dict] | None = None,
        auto_optimize_routing: bool | None = None,
        openai_codex_auth_mode: str | None = None,
        minimax_auth_mode: str | None = None,
        commit_message_style: str = "scoped",
        execution_target_preference: str = "profile_default",
        local_project_path: str = "",
        nas_project_path: str = "",
        sync_mode: str = "manual",
        sync_direction: str = "bidirectional",
        sync_conflict_policy: str = "keep_newer_and_log",
        auto_sync_to_nas: bool | None = None,
        workspace_id: str | None = None,
    ) -> WorkspaceProfile:
        workspaces = self.load_workspaces()
        clean_local_project_path = str(local_project_path or "").strip()
        clean_nas_project_path = str(nas_project_path or "").strip()
        clean_sync_mode = str(sync_mode or "manual").strip().lower()
        clean_sync_direction = normalize_sync_direction(sync_direction)
        clean_sync_conflict_policy = str(sync_conflict_policy or "keep_newer_and_log").strip().lower()
        sync_enabled = bool(auto_sync_to_nas)
        effective_root_path = clean_nas_project_path if sync_enabled and clean_nas_project_path else root_path
        workspace_root = Path(effective_root_path).resolve()
        sync_status: dict[str, object] = {}
        if sync_enabled and clean_nas_project_path:
            local_root = (
                Path(clean_local_project_path).expanduser().resolve()
                if clean_local_project_path
                else None
            )
            sync_status = _sync_local_and_nas_projects(
                local_root=local_root,
                nas_root=workspace_root,
                sync_direction=clean_sync_direction,
                conflict_policy=clean_sync_conflict_policy,
            )
            # If no local root is provided, keep the existing one-way behavior from
            # the selected root path to NAS for backwards compatibility.
            if (
                not sync_status
                and clean_local_project_path == ""
                and root_path
                and Path(root_path).expanduser().resolve() != workspace_root
            ):
                sync_status = _sync_project_tree(
                    Path(root_path).expanduser().resolve(),
                    workspace_root,
                    conflict_policy=clean_sync_conflict_policy,
                )
        now = utc_now_iso()
        normalized_route_overrides = normalize_route_overrides(route_overrides or [])
        normalized_openai_codex_auth_mode = normalize_openai_codex_auth_mode(
            openai_codex_auth_mode
        )
        normalized_minimax_auth_mode = normalize_minimax_auth_mode(minimax_auth_mode)
        for item in workspaces:
            if item.workspace_id == workspace_id or (
                workspace_id is None and Path(item.root_path).resolve() == workspace_root
            ):
                item.name = name
                item.root_path = str(workspace_root)
                item.default_runtime = default_runtime
                item.user_profile = user_profile or item.user_profile
                item.preferred_harness = preferred_harness or item.preferred_harness
                item.routing_strategy = routing_strategy or item.routing_strategy
                item.route_overrides = (
                    normalized_route_overrides
                    if route_overrides is not None
                    else item.route_overrides
                )
                if auto_optimize_routing is not None:
                    item.auto_optimize_routing = bool(auto_optimize_routing)
                if openai_codex_auth_mode is not None:
                    item.openai_codex_auth_mode = normalized_openai_codex_auth_mode
                if minimax_auth_mode is not None:
                    item.minimax_auth_mode = normalized_minimax_auth_mode
                item.commit_message_style = (
                    commit_message_style or item.commit_message_style
                )
                item.execution_target_preference = (
                    execution_target_preference or item.execution_target_preference
                )
                item.local_project_path = clean_local_project_path or item.local_project_path
                item.nas_project_path = clean_nas_project_path or item.nas_project_path
                item.sync_mode = clean_sync_mode or item.sync_mode
                item.sync_direction = clean_sync_direction or item.sync_direction
                item.sync_conflict_policy = (
                    clean_sync_conflict_policy or item.sync_conflict_policy
                )
                if auto_sync_to_nas is not None:
                    item.auto_sync_to_nas = sync_enabled
                item.goals = [
                    entry
                    for entry in item.goals
                    if not str(entry).startswith("sync_status:")
                ]
                if sync_status:
                    item.goals.append(f"sync_status:{json.dumps(sync_status, sort_keys=True)}")
                item.workspace_type = detect_workspace_type(workspace_root)
                item.updated_at = now
                self.save_workspaces(workspaces)
                return item

        workspace = WorkspaceProfile(
            workspace_id=workspace_id or f"workspace_{uuid.uuid4().hex[:8]}",
            name=name,
            root_path=str(workspace_root),
            default_runtime=default_runtime,
            workspace_type=detect_workspace_type(workspace_root),
            user_profile=user_profile or "builder",
            preferred_harness=preferred_harness or "fluxio_hybrid",
            routing_strategy=routing_strategy or "profile_default",
            route_overrides=normalized_route_overrides,
            auto_optimize_routing=bool(auto_optimize_routing),
            openai_codex_auth_mode=normalized_openai_codex_auth_mode,
            minimax_auth_mode=normalized_minimax_auth_mode,
            commit_message_style=commit_message_style or "scoped",
            execution_target_preference=execution_target_preference or "profile_default",
            local_project_path=clean_local_project_path,
            nas_project_path=clean_nas_project_path,
            sync_mode=clean_sync_mode,
            sync_direction=clean_sync_direction,
            sync_conflict_policy=clean_sync_conflict_policy,
            auto_sync_to_nas=sync_enabled,
            goals=[f"sync_status:{json.dumps(sync_status, sort_keys=True)}"] if sync_status else [],
            updated_at=now,
        )
        workspaces.append(workspace)
        self.save_workspaces(workspaces)
        return workspace

    def delete_workspace(self, workspace_id: str) -> tuple[WorkspaceProfile, int]:
        workspaces = self.load_workspaces()
        target = next(
            (item for item in workspaces if item.workspace_id == workspace_id),
            None,
        )
        if target is None:
            raise ValueError(f"Unknown workspace id: {workspace_id}")
        if len(workspaces) <= 1:
            raise ValueError(
                "Cannot delete the last workspace. Add another workspace first."
            )

        remaining_workspaces = [
            item for item in workspaces if item.workspace_id != workspace_id
        ]
        self.save_workspaces(remaining_workspaces)

        missions = self.load_missions()
        removed_missions = [
            item for item in missions if item.workspace_id == workspace_id
        ]
        remaining_missions = [
            item for item in missions if item.workspace_id != workspace_id
        ]
        self._rebalance_workspace_queue_in_place(remaining_missions)
        self.save_missions(remaining_missions)

        histories = self.load_workspace_actions()
        if workspace_id in histories:
            histories.pop(workspace_id, None)
            self.workspace_actions_path.write_text(
                json.dumps(histories, indent=2),
                encoding="utf-8",
            )

        return target, len(removed_missions)

    def create_mission(
        self,
        workspace_id: str,
        runtime_id: str,
        objective: str,
        success_checks: list[str],
        mode: str,
        verification_commands: list[str],
        max_runtime_seconds: int,
        selected_profile: str = "builder",
        escalation_destination: str = "",
        run_until_behavior: str | None = None,
        deadline_at: str | None = None,
        harness_id: str = "fluxio_hybrid",
        code_execution_enabled: bool = False,
        code_execution_memory: str = "4g",
        code_execution_container_id: str = "",
        code_execution_required: bool = False,
        route_overrides: list[dict] | None = None,
    ) -> Mission:
        missions = self.load_missions()
        self._rebalance_workspace_queue_in_place(missions, workspace_id)
        blocking_mission = self._active_workspace_mission(workspace_id, missions)
        queue_position = 0
        queue_reason = ""
        blocking_mission_id = None
        summary = "Mission created and waiting for first runtime cycle."
        if blocking_mission is not None:
            queue_position = (
                len(
                    [
                        item
                        for item in missions
                        if item.workspace_id == workspace_id
                        and item.state.status not in TERMINAL_MISSION_STATUSES
                        and item.state.queue_position > 0
                    ]
                )
                + 1
            )
            blocking_mission_id = blocking_mission.mission_id
            queue_reason = (
                f"Waiting for mission '{blocking_mission.title or blocking_mission.objective or blocking_mission.mission_id}' "
                "to leave the active slot for this workspace."
            )
            summary = queue_reason
        mission_id = f"mission_{uuid.uuid4().hex[:10]}"
        now = utc_now_iso()
        mission = Mission(
            mission_id=mission_id,
            workspace_id=workspace_id,
            runtime_id=runtime_id,
            objective=objective,
            success_checks=success_checks,
            title=_mission_title(objective),
            created_at=now,
            updated_at=now,
            run_budget=MissionRunBudget(
                mode=mode,
                max_runtime_seconds=max_runtime_seconds,
                focus_window_hours=max(1, round(max_runtime_seconds / 3600)),
                run_until_behavior=run_until_behavior or "pause_on_failure",
                deadline_at=deadline_at or None,
            ),
            verification_policy=MissionVerificationPolicy(
                commands=verification_commands,
                pause_on_failure=(run_until_behavior or "pause_on_failure") != "continue_until_blocked",
            ),
            escalation_policy=ApprovalEscalation(
                channel="telegram",
                enabled=bool(escalation_destination),
                destination=escalation_destination,
                triggers=[
                    "blocked approval",
                    "missing setup step",
                    "verification failure",
                    "completion summary",
                ],
            ),
            harness_id=harness_id or "fluxio_hybrid",
            selected_profile=selected_profile,
            execution_scope=ExecutionScope(
                requested="isolated",
                strategy="direct",
                workspace_root="",
                execution_root="",
                status="pending",
                detail="Execution scope will be resolved during the first harness cycle.",
            ),
            execution_policy=ExecutionPolicy(
                profile_name=selected_profile,
            ),
            code_execution=MissionCodeExecutionConfig(
                enabled=bool(code_execution_enabled),
                memory_limit=code_execution_memory or "4g",
                container_id=str(code_execution_container_id or "").strip(),
                required=bool(code_execution_required),
            ),
            route_configs=normalize_route_overrides(route_overrides or []),
            planned_file_scope=infer_planned_file_scope(objective, success_checks),
            state=MissionStateSnapshot(
                status="queued",
                queue_position=queue_position,
                blocking_mission_id=blocking_mission_id,
                queue_reason=queue_reason,
                code_execution={
                    "enabled": bool(code_execution_enabled),
                    "memory_limit": code_execution_memory or "4g",
                    "container_id": str(code_execution_container_id or "").strip(),
                    "required": bool(code_execution_required),
                    "artifacts": [],
                },
            ),
            tutorial_context={
                "profile": selected_profile,
                "preferredHarness": harness_id or "fluxio_hybrid",
            },
            proof=MissionProof(summary=summary),
        )
        missions.append(mission)
        self._rebalance_workspace_queue_in_place(missions, workspace_id)
        self.save_missions(missions)
        self.append_event(
            MissionEvent(
                mission_id=mission_id,
                kind="mission.queued" if queue_position else "mission.created",
                message=(
                    f"Mission queued behind {blocking_mission_id} for workspace collision avoidance."
                    if queue_position
                    else f"Mission created for runtime {runtime_id}."
                ),
                metadata={
                    "workspaceId": workspace_id,
                    "mode": mode,
                    "queuePosition": queue_position,
                    "blockingMissionId": blocking_mission_id,
                },
            )
        )
        self.record_autonomous_workflow(mission)
        return mission

    def update_mission(self, mission: Mission) -> Mission:
        missions = self.load_missions()
        updated = mission
        updated.updated_at = utc_now_iso()
        for index, item in enumerate(missions):
            if item.mission_id == mission.mission_id:
                missions[index] = updated
                self.save_missions(missions)
                self.record_autonomous_workflow(updated)
                return updated
        missions.append(updated)
        self.save_missions(missions)
        self.record_autonomous_workflow(updated)
        return updated

    def get_workspace(self, workspace_id: str) -> WorkspaceProfile | None:
        for item in self.load_workspaces():
            if item.workspace_id == workspace_id:
                return item
        return None

    def get_mission(self, mission_id: str) -> Mission | None:
        for item in self.load_missions():
            if item.mission_id == mission_id:
                return item
        return None

    def rebalance_mission_queue(
        self,
        workspace_id: str | None = None,
    ) -> list[Mission]:
        missions = self.load_missions()
        self._rebalance_workspace_queue_in_place(missions, workspace_id)
        if missions:
            self.save_missions(missions)
        return missions

    def append_event(self, event: MissionEvent) -> None:
        self._rotate_events_if_needed()
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=True) + "\n")

    def append_lane_control_receipt(self, receipt: dict) -> None:
        if not isinstance(receipt, dict):
            return
        self.control_dir.mkdir(parents=True, exist_ok=True)
        with self.lane_control_receipts_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, ensure_ascii=True) + "\n")

    def lane_control_receipts_for_mission(self, mission_id: str, *, limit: int = 20) -> list[dict]:
        if not self.lane_control_receipts_path.exists():
            return []
        receipts: list[dict] = []
        lines = _read_text_tail_lines(
            self.lane_control_receipts_path,
            limit=max(100, int(limit) * 5),
        )
        for line in lines:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            if str(item.get("schema") or "") != "fluxio.lane_control_receipt.v1":
                continue
            if str(item.get("missionId") or item.get("mission_id") or "") != str(mission_id):
                continue
            receipts.append(item)
        return receipts[-limit:]

    def attach_lane_control_receipts(self, mission: Mission, *, limit: int = 20) -> Mission:
        ledger_receipts = self.lane_control_receipts_for_mission(
            mission.mission_id,
            limit=limit,
        )
        state_receipts = [
            item
            for item in (mission.state.lane_control_receipts or [])
            if isinstance(item, dict)
        ]
        by_id: dict[str, dict] = {}
        for item in [*state_receipts, *ledger_receipts]:
            receipt_id = str(item.get("receiptId") or item.get("receipt_id") or "")
            if receipt_id:
                by_id[receipt_id] = item
        mission.state.lane_control_receipts = sorted(
            by_id.values(),
            key=lambda item: str(item.get("generatedAt") or item.get("at") or ""),
        )[-limit:]
        return mission

    def recent_events(self, limit: int = 40) -> list[dict]:
        if not self.events_path.exists():
            return []
        lines = _read_text_tail_lines(self.events_path, limit=max(0, int(limit)))
        events: list[dict] = []
        for line in reversed(lines):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events

    def _rotate_events_if_needed(self) -> None:
        if not self.events_path.exists():
            return
        max_bytes = max(
            int(os.environ.get("SYNTELOS_MISSION_EVENTS_MAX_BYTES", str(50 * 1024 * 1024))),
            1024 * 1024,
        )
        try:
            if self.events_path.stat().st_size <= max_bytes:
                return
        except OSError:
            return
        keep_lines = max(
            int(os.environ.get("SYNTELOS_MISSION_EVENTS_KEEP_LINES", "5000")),
            100,
        )
        backups_dir = self.control_dir / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        rotated_path = backups_dir / (
            f"mission_events-rotated-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
        )
        try:
            self.events_path.replace(rotated_path)
        except OSError:
            return
        tail: deque[str] = deque(maxlen=keep_lines)
        try:
            with rotated_path.open("r", encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    if line.strip():
                        tail.append(line)
            with self.events_path.open("w", encoding="utf-8") as handle:
                handle.writelines(tail)
        except OSError:
            self.events_path.touch(exist_ok=True)

    def load_workspace_actions(self) -> dict[str, list[dict]]:
        payload = self._load_json(self.workspace_actions_path, {})
        if not isinstance(payload, dict):
            return {}
        histories: dict[str, list[dict]] = {}
        for key, value in payload.items():
            if isinstance(value, list):
                histories[str(key)] = value
        return histories

    def append_workspace_action(
        self,
        history_key: str,
        record: dict,
        limit: int = 24,
    ) -> dict:
        if history_key == "__setup__":
            self._invalidate_snapshot_caches()
        histories = self.load_workspace_actions()
        entries = list(histories.get(history_key, []))
        entries.append(record)
        histories[history_key] = entries[-max(1, limit) :]
        self.workspace_actions_path.write_text(
            json.dumps(histories, indent=2),
            encoding="utf-8",
        )
        return record

    def build_snapshot(self) -> dict:
        workspaces = self.load_workspaces()
        missions = self.load_missions()
        if os.environ.get("FLUXIO_CONTROL_ROOM_FAST") == "1":
            return self._build_fast_snapshot(workspaces, missions)
        workspace_action_history = self.load_workspace_actions()
        setup_history = workspace_action_history.get("__setup__", [])
        runtime_statuses = detect_runtime_statuses(self.root)
        runtime_lookup = {item.runtime_id: asdict(item) for item in runtime_statuses}
        profiles = ProfileRegistry(self.root / "config" / "profiles.json")
        skill_library = SkillLibrary(
            root=self.root,
            registry=SkillRegistry(self.root / "config" / "skills.json"),
        )
        onboarding = detect_onboarding_status(self.root)
        setup_health = onboarding.get("setupHealth", {})
        setup_health["actionHistory"] = workspace_action_history.get("__setup__", [])
        guidance = build_guidance_snapshot(self.root, onboarding=onboarding)
        runtime_supervisor = DelegatedRuntimeSupervisor(self.root)
        connected_apps_snapshot = build_connected_apps_snapshot(self.root)
        harness_lab_snapshot = build_harness_lab_snapshot(self.root)
        activity = self.recent_events()
        provider_auth_presence = _provider_auth_presence_from_env()
        workspace_lookup = {item.workspace_id: item for item in workspaces}

        workspace_cards = []
        recommended_skill_pack_objects = []
        for workspace in workspaces:
            runtime_id = workspace.default_runtime
            profile = profiles.resolve(workspace.user_profile, Path(workspace.root_path))
            profile_parameters = _profile_parameter_snapshot(
                workspace.user_profile,
                profile,
            )
            git_snapshot = _inspect_workspace_git(
                Path(workspace.root_path),
                commit_message_style=workspace.commit_message_style,
            )
            validation_actions = _build_validation_actions(Path(workspace.root_path))
            verification_commands = detect_default_verification_commands(
                Path(workspace.root_path)
            )
            skill_recommendations = [
                asdict(item)
                for item in recommend_skills(
                    workspace.workspace_type, workspace.default_runtime
                )
            ]
            integration_recommendations = [
                asdict(item)
                for item in recommend_integrations(
                    workspace.workspace_type, workspace.default_runtime
                )
            ]
            recommended_skill_packs = SkillLibrary.recommended_packs_from_skills(
                skill_recommendations
            )
            recommended_skill_pack_objects.extend(recommended_skill_packs)
            workspace_cards.append(
                {
                    **asdict(workspace),
                    "openaiCodexSetupStatus": _openai_codex_setup_status_for_workspace(
                        workspace,
                        auth_presence=provider_auth_presence,
                    ),
                    "minimaxSetupStatus": _minimax_setup_status_for_workspace(
                        workspace,
                        setup_history,
                        auth_presence=provider_auth_presence,
                    ),
                    "runtimeStatus": runtime_lookup.get(runtime_id),
                    "gitSnapshot": git_snapshot,
                    "gitActions": _build_git_actions(git_snapshot, profile_parameters),
                    "validationActions": validation_actions,
                    "verificationCommands": verification_commands,
                    "workspaceActionHistory": workspace_action_history.get(
                        workspace.workspace_id,
                        [],
                    ),
                    "profileParameters": profile_parameters,
                    "skillRecommendations": skill_recommendations,
                    "integrationRecommendations": integration_recommendations,
                    "recommendedSkillPacks": [
                        asdict(item) for item in recommended_skill_packs
                    ],
                    "serviceManagement": _build_workspace_service_management(
                        setup_health=setup_health,
                        runtime_status=runtime_lookup.get(runtime_id),
                        integration_recommendations=integration_recommendations,
                        connected_apps=connected_apps_snapshot.get("connectedSessions", []),
                    ),
                }
            )

        latest_runtime_cycles = _latest_runtime_cycles_by_mission(self.events_path)
        mission_records_changed = False
        for mission in missions:
            before_runtime_signature = _mission_runtime_persistence_signature(mission)
            if _reconcile_mission_from_runtime_cycle(
                mission,
                latest_runtime_cycles.get(mission.mission_id),
            ):
                mission_records_changed = True
            _sync_execution_scope_snapshot(mission)
            refreshed_sessions = []
            for session in mission.delegated_runtime_sessions:
                try:
                    refreshed = runtime_supervisor.refresh_session(session)
                except FileNotFoundError:
                    refreshed = session
                refreshed_sessions.append(refreshed)
            mission.delegated_runtime_sessions = refreshed_sessions
            mission.action_history = normalize_action_history(mission.action_history)
            mission.state.delegated_runtime_sessions = [asdict(item) for item in refreshed_sessions]
            refresh_mission_runtime_state(mission, refreshed_sessions)
            if _maybe_send_approval_receipt(mission, self.root):
                mission_records_changed = True
            mission.state.provider_runtime_truth = _provider_truth_for_mission(
                mission,
                auth_presence=provider_auth_presence,
                workspace=workspace_lookup.get(mission.workspace_id),
            )
            if _reconcile_mission_route_policy(
                mission,
                workspace_lookup.get(mission.workspace_id),
            ):
                mission_records_changed = True
            sync_mission_state_snapshot(mission)
            if _mission_runtime_persistence_signature(mission) != before_runtime_signature:
                mission_records_changed = True
        before_queue_signature = _mission_queue_persistence_signature(missions)
        self._rebalance_workspace_queue_in_place(missions)
        if _mission_queue_persistence_signature(missions) != before_queue_signature:
            mission_records_changed = True
        if mission_records_changed:
            self.save_missions(missions)
        missions_payload = []
        for item in missions:
            self.attach_lane_control_receipts(item)
            mission_payload = asdict(item)
            mission_payload["missionLoop"] = build_mission_loop_snapshot(item)
            mission_payload["plannedScopeArtifacts"] = build_planned_scope_artifacts(
                root=self.root,
                mission=item,
                workspace=workspace_lookup.get(item.workspace_id),
            )
            mission_payload["effectiveRouteContract"] = (
                item.effective_route_contract
                if item.effective_route_contract
                else _effective_route_contract_for_mission(item)
            )
            mission_payload["providerTruth"] = dict(item.state.provider_runtime_truth or {})
            mission_payload["providerCapabilities"] = _provider_capability_contract_for_mission(item)
            missions_payload.append(mission_payload)
        recommended_skill_packs = list(
            {item.pack_id: item for item in recommended_skill_pack_objects}.values()
        )
        skill_catalog = skill_library.build_catalog(
            recommended_packs=recommended_skill_packs,
        )
        workspace_payload = []
        for workspace in workspace_cards:
            active_mission = self._active_workspace_mission(workspace["workspace_id"], missions)
            queued_missions = [
                item
                for item in missions
                if item.workspace_id == workspace["workspace_id"] and item.state.queue_position > 0
            ]
            service_management = workspace.get("serviceManagement", [])
            workspace_payload.append(
                {
                    **workspace,
                    "activeMissionId": active_mission.mission_id if active_mission else "",
                    "activeMissionTitle": active_mission.title if active_mission else "",
                    "queuedMissionIds": [item.mission_id for item in queued_missions],
                    "queuedMissionCount": len(queued_missions),
                    "serviceManagementSummary": _service_management_summary(service_management),
                }
            )
        inbox_items = [
            {
                "missionId": item.mission_id,
                "channel": item.escalation_policy.channel,
                "destination": item.escalation_policy.destination,
                "ready": item.escalation_policy.delivery_ready,
                "pendingCount": item.escalation_policy.pending_count,
                "previewMessage": build_escalation_preview(item),
            }
            for item in missions
            if item.state.status in {"blocked", "needs_approval", "verification_failed", "completed"}
        ]

        active_workspace_payload = workspace_payload[0] if workspace_payload else {}
        active_workspace_id = str(active_workspace_payload.get("workspace_id", "") or "")
        active_mission = self._active_workspace_mission(active_workspace_id, missions)
        active_provider_truth = (
            dict(active_mission.state.provider_runtime_truth or {})
            if active_mission is not None
            else {}
        )
        active_route = (
            dict(active_provider_truth.get("activeRoute", {}))
            if isinstance(active_provider_truth.get("activeRoute"), dict)
            else {}
        )
        provider_status = {}
        for provider_id in ("openai", "anthropic", "openrouter"):
            aliases = (
                {"openai", "openai-codex"}
                if provider_id == "openai"
                else {provider_id}
            )
            last_success = (
                active_provider_truth.get("lastSuccessfulCall", {})
                if isinstance(active_provider_truth.get("lastSuccessfulCall"), dict)
                else {}
            )
            last_failure = (
                active_provider_truth.get("lastFailure", {})
                if isinstance(active_provider_truth.get("lastFailure"), dict)
                else {}
            )
            openai_status = (
                dict(active_workspace_payload.get("openaiCodexSetupStatus", {}))
                if provider_id == "openai"
                and isinstance(active_workspace_payload.get("openaiCodexSetupStatus"), dict)
                else {}
            )
            auth_present = (
                bool(openai_status.get("authPresent", False))
                if provider_id == "openai"
                else bool(provider_auth_presence.get(provider_id, False))
            )
            provider_status[provider_id] = {
                "providerId": provider_id,
                "authPresent": auth_present,
                "configured": auth_present,
                "authMode": (
                    str(openai_status.get("authMode", "")).strip().lower()
                    if provider_id == "openai"
                    else ""
                ),
                "authPath": (
                    str(openai_status.get("authPath", "")).strip()
                    if provider_id == "openai"
                    else ""
                ),
                "activeRoute": active_route
                if str(active_route.get("provider", "")).strip().lower() in aliases
                else {},
                "lastSuccessfulModelCall": (
                    last_success
                    if str(last_success.get("provider", "")).strip().lower() in aliases
                    else {}
                ),
                "lastProviderFailure": (
                    last_failure
                    if str(last_failure.get("provider", "")).strip().lower() in aliases
                    else {}
                ),
                "lastCheckedAt": utc_now_iso(),
            }
        provider_setup_status = {
            **provider_status,
            "minimax": active_workspace_payload.get("minimaxSetupStatus")
            or _minimax_setup_status_for_workspace(
                self._default_workspace_profile(),
                setup_history,
                auth_presence=provider_auth_presence,
            ),
        }
        efficiency_autotune = _build_efficiency_autotune_snapshot(
            harness_lab=harness_lab_snapshot,
            auto_optimize_enabled=bool(
                active_workspace_payload.get("auto_optimize_routing", False)
            ),
            activity=activity,
        )
        release_readiness = build_release_readiness_snapshot(
            self.root,
            onboarding=onboarding,
            setup_health=setup_health,
            harness_lab=harness_lab_snapshot,
        )
        storage_bridge = _build_storage_bridge_snapshot(
            connected_apps_snapshot.get("connectedSessions", [])
        )
        runtime_compartments = _build_runtime_compartments_snapshot(
            self.root,
            missions,
            runtime_statuses=runtime_statuses,
            setup_health=setup_health,
            storage_bridge=storage_bridge,
            provider_auth_presence=provider_auth_presence,
        )
        generated_image_artifacts = _build_generated_image_artifacts_snapshot(self.root)
        hermes_mission_evidence = _build_hermes_mission_evidence(
            self.root,
            missions,
            activity,
        )
        nas_deploy_readiness = build_nas_deploy_readiness_snapshot(
            self.root,
            onboarding=onboarding,
            setup_health=setup_health,
            storage_bridge=storage_bridge,
        )
        autonomous_workflows = self.reconcile_autonomous_workflows(missions)
        mission_watchdog = build_mission_watchdog_report(
            root=self.root,
            missions=missions,
            workspaces=workspaces,
        )
        mission_watchdog["supervisor"] = load_watchdog_supervisor_state(self.root)
        red_team_escalation = build_red_team_escalation_snapshot(self.root)
        system_audit_digest = _build_system_audit_digest(
            root=self.root,
            release_readiness=release_readiness,
            harness_lab=harness_lab_snapshot,
            missions=missions,
            workspaces=workspaces,
        )

        return {
            "workspaceRoot": str(self.root),
            "ui": {
                "uiMode": "agent",
                "defaultMode": "agent",
                "availableModes": ["agent", "builder"],
                "layout": "t3_workbench",
                "sharedMissionState": True,
            },
            "workspaces": workspace_payload,
            "missions": missions_payload,
            "runtimes": [asdict(item) for item in runtime_statuses],
            "activity": activity,
            "inbox": inbox_items,
            "onboarding": onboarding,
            "setupHealth": setup_health,
            "guidance": guidance,
            "profiles": {
                "defaultProfile": profiles.default_profile,
                "availableProfiles": profiles.list_names(),
                "details": {
                    name: {
                        "description": profile.description,
                        "ui": profile.ui,
                        "agent": asdict(profile.agent),
                        "parameters": _profile_parameter_snapshot(name, profile),
                    }
                    for name, profile in profiles.profiles.items()
                },
            },
            "skillLibrary": skill_catalog,
            "workflowStudio": _build_workflow_studio(
                workspace_payload,
                missions_payload,
                setup_health,
                skill_catalog,
            ),
            "harnessLab": harness_lab_snapshot,
            "providerSetupStatus": provider_setup_status,
            "efficiencyAutotune": efficiency_autotune,
            "bridgeLab": connected_apps_snapshot,
            "storageBridge": storage_bridge,
            "releaseReadiness": release_readiness,
            "runtimeCompartments": runtime_compartments,
            "generatedImageArtifacts": generated_image_artifacts,
            "hermesMissionEvidence": hermes_mission_evidence,
            "nasDeployReadiness": nas_deploy_readiness,
            "autonomousWorkflows": autonomous_workflows,
            "missionWatchdog": mission_watchdog,
            "redTeamEscalation": red_team_escalation,
            "systemAuditDigest": system_audit_digest,
        }

    def build_summary_snapshot(self) -> dict:
        started = time.perf_counter()
        section_started = started
        section_durations: list[dict[str, object]] = []

        def record_section(name: str) -> None:
            nonlocal section_started
            now = time.perf_counter()
            section_durations.append(
                {
                    "name": name,
                    "durationMs": round((now - section_started) * 1000, 2),
                }
            )
            section_started = now

        workspaces = self.load_workspaces()
        missions = self.load_missions()
        activity = self.recent_events(limit=24)
        project_history_events = self.recent_events(limit=160)
        provider_auth_presence = _provider_auth_presence_from_env()
        record_section("base_store_load")
        skill_catalog = SkillLibrary(
            root=self.root,
            registry=SkillRegistry(self.root / "config" / "skills.json"),
        ).build_catalog(recommended_packs=[])
        skill_catalog = self._summary_skill_catalog_payload(skill_catalog)
        record_section("skill_catalog")

        status_counts: dict[str, int] = {}
        runtime_counts: dict[str, int] = {}
        workspace_missions: dict[str, list[Mission]] = {}
        for mission in missions:
            status_counts[mission.state.status] = status_counts.get(mission.state.status, 0) + 1
            runtime_counts[mission.runtime_id] = runtime_counts.get(mission.runtime_id, 0) + 1
            workspace_missions.setdefault(mission.workspace_id, []).append(mission)

        workspace_payload = []
        mission_launch_shortcuts = []
        workspace_by_id = {workspace.workspace_id: workspace for workspace in workspaces}
        for workspace in workspaces:
            related = workspace_missions.get(workspace.workspace_id, [])
            active_mission = self._active_workspace_mission(workspace.workspace_id, related)
            queued_count = sum(
                1
                for mission in related
                if mission.state.status not in TERMINAL_MISSION_STATUSES
                and mission.state.queue_position > 0
            )
            workspace_payload.append(
                {
                    "workspace_id": workspace.workspace_id,
                    "name": workspace.name,
                    "root_path": workspace.root_path,
                    "workspace_type": workspace.workspace_type,
                    "default_runtime": workspace.default_runtime,
                    "preferred_harness": workspace.preferred_harness,
                    "user_profile": workspace.user_profile,
                    "enabled": workspace.enabled,
                    "updated_at": workspace.updated_at,
                    "activeMissionId": active_mission.mission_id if active_mission else "",
                    "activeMissionTitle": active_mission.title if active_mission else "",
                    "activeMissionStatus": active_mission.state.status if active_mission else "",
                    "queuedMissionCount": queued_count,
                    "missionCount": len(related),
                }
            )
            mission_launch_shortcuts.append(
                self._mission_launch_shortcut_payload(workspace)
            )
        record_section("workspace_rows")

        sorted_missions = sorted(
            missions,
            key=lambda item: item.updated_at or item.created_at or "",
            reverse=True,
        )
        active_bootstrap_missions = [
            mission
            for mission in sorted_missions
            if mission.state.status not in TERMINAL_MISSION_STATUSES
            and mission.state.status != "draft"
        ]
        recent_missions = []
        seen_bootstrap_mission_ids: set[str] = set()
        for mission in [*active_bootstrap_missions, *sorted_missions]:
            if mission.mission_id in seen_bootstrap_mission_ids:
                continue
            seen_bootstrap_mission_ids.add(mission.mission_id)
            recent_missions.append(mission)
            if len(recent_missions) >= max(CONTROL_ROOM_FULL_SUMMARY_MISSION_LIMIT, len(active_bootstrap_missions)):
                break
        mission_payload = []
        for mission in recent_missions:
            mission_active = (
                mission.state.status not in TERMINAL_MISSION_STATUSES
                and mission.state.status != "draft"
            )
            _reconcile_mission_route_policy(
                mission,
                workspace_by_id.get(mission.workspace_id),
            )
            mission.state.provider_runtime_truth = _provider_truth_for_mission(
                mission,
                auth_presence=provider_auth_presence,
                workspace=workspace_by_id.get(mission.workspace_id),
            )
            row = self._mission_summary_payload(
                mission,
                root=self.root if mission_active else None,
                workspace=workspace_by_id.get(mission.workspace_id),
            )
            if mission_active:
                row["contextRoots"] = self._mission_context_roots_payload(
                    mission,
                    workspace=workspace_by_id.get(mission.workspace_id),
                    workspaces=workspaces,
                    workspace_missions=workspace_missions,
                )
            else:
                row = self._summary_terminal_mission_payload(row)
                row["contextRoots"] = self._bootstrap_context_roots_placeholder(mission)
            mission_payload.append(row)
        record_section("mission_rows")
        mission_watchdog = _summary_mission_watchdog_report(
            root=self.root,
            missions=missions,
            workspaces=workspaces,
        )
        mission_watchdog["supervisor"] = load_watchdog_supervisor_state(self.root)
        record_section("mission_watchdog")
        red_team_escalation = self._summary_red_team_escalation_payload(
            build_red_team_escalation_snapshot(self.root, limit=24)
        )
        record_section("red_team_escalation")
        summary_harness_lab = build_summary_harness_lab_snapshot(
            self.root,
            missions=missions,
        )
        record_section("harness_lab")
        system_audit_digest = self._summary_system_audit_digest_payload(
            _build_system_audit_digest(
                root=self.root,
                release_readiness={},
                harness_lab=summary_harness_lab,
                missions=missions,
                workspaces=workspaces,
            )
        )
        record_section("system_audit_digest")
        notifications = self._build_notification_feed(
            missions=recent_missions,
            activity=activity,
            watchdog_report=mission_watchdog,
            root=self.root,
            workspace_by_id=workspace_by_id,
        )
        record_section("notification_feed")
        overnight_digest = self._overnight_progress_digest_payload(
            missions=missions,
            recent_missions=recent_missions,
            workspaces=workspaces,
            activity=activity,
            notifications=notifications,
            telegram_destination=load_telegram_destination(self.root),
            delivery_receipts=[asdict(item) for item in load_delivery_receipts(self.root, limit=24)],
        )
        record_section("overnight_digest")
        project_progress_history = self._project_progress_history_payload(
            root=self.root,
            workspaces=workspaces,
            missions=missions,
            events=project_history_events,
            workspace_missions=workspace_missions,
        )
        project_progress_history = self._summary_project_progress_payload(project_progress_history)
        record_section("project_progress_history")
        payload = {
            "schema": "fluxio.control_room.summary.v1",
            "workspaceRoot": str(self.root),
            "generatedAt": utc_now_iso(),
            "counts": {
                "workspaces": len(workspaces),
                "missions": len(missions),
                "activeMissions": sum(
                    1
                    for item in missions
                    if item.state.status not in TERMINAL_MISSION_STATUSES
                    and item.state.status != "draft"
                    and item.state.queue_position == 0
                ),
                "queuedMissions": sum(
                    1
                    for item in missions
                    if item.state.status not in TERMINAL_MISSION_STATUSES
                    and item.state.queue_position > 0
                ),
                "blockedMissions": status_counts.get("blocked", 0)
                + status_counts.get("needs_approval", 0)
                + status_counts.get("verification_failed", 0),
                "completedMissions": status_counts.get("completed", 0),
            },
            "statusCounts": status_counts,
            "runtimeCounts": runtime_counts,
            "workspaces": workspace_payload,
            "missions": mission_payload,
            "notifications": notifications,
            "overnightDigest": overnight_digest,
            "projectProgressHistory": project_progress_history,
            "harnessLab": {
                "schema": "fluxio.harness_lab.summary_compact.v1",
                "source": summary_harness_lab.get("source", "mission_store_delegated_sessions_summary"),
                "routeTrustCoverage": summary_harness_lab.get("routeTrustCoverage", {}),
                "recommendation": summary_harness_lab.get("recommendation", {}),
            },
            "skillLibrary": skill_catalog,
            "systemAuditDigest": system_audit_digest,
            "missionWatchdog": {
                "schema": mission_watchdog["schema"],
                "checkedAt": mission_watchdog["checkedAt"],
                "summary": mission_watchdog["summary"],
                "issues": mission_watchdog["issues"][:8],
                "nextAction": mission_watchdog["nextAction"],
                "summarySource": mission_watchdog.get("summarySource", {}),
                "problemReport": {
                    "schema": mission_watchdog.get("problemReport", {}).get(
                        "schema",
                        "fluxio.watchdog_problem_report.v1",
                    ),
                    "status": mission_watchdog.get("problemReport", {}).get("status", "clear"),
                    "problemCount": mission_watchdog.get("problemReport", {}).get("problemCount", 0),
                    "firstProblem": mission_watchdog.get("problemReport", {}).get("firstProblem", {}),
                    "nextAction": mission_watchdog.get("problemReport", {}).get("nextAction", ""),
                },
                "problemRegistry": {
                    "schema": mission_watchdog.get("problemRegistry", {}).get(
                        "schema",
                        "fluxio.watchdog_problem_registry.v1",
                    ),
                    "status": mission_watchdog.get("problemRegistry", {}).get("status", "clear"),
                    "openProblemCount": mission_watchdog.get("problemRegistry", {}).get(
                        "openProblemCount",
                        0,
                    ),
                    "resolvedProblemCount": mission_watchdog.get("problemRegistry", {}).get(
                        "resolvedProblemCount",
                        0,
                    ),
                    "newProblemCount": mission_watchdog.get("problemRegistry", {}).get(
                        "newProblemCount",
                        0,
                    ),
                    "firstOpenProblem": mission_watchdog.get("problemRegistry", {}).get(
                        "firstOpenProblem",
                        {},
                    ),
                    "nextAction": mission_watchdog.get("problemRegistry", {}).get(
                        "nextAction",
                        "",
                    ),
                    "problems": mission_watchdog.get("problemRegistry", {}).get(
                        "problems",
                        [],
                    )[:8],
                },
                "supervisor": mission_watchdog.get("supervisor", {}),
            },
            "redTeamEscalation": red_team_escalation,
            "missionLaunchShortcuts": mission_launch_shortcuts,
            "providers": {
                "authPresence": provider_auth_presence,
                "checkedAt": utc_now_iso(),
                "consistentHermesCredentialPool": True,
            },
            "mobileWeb": {
                "summaryFirst": True,
                "notificationFeed": True,
                "overnightDigest": True,
                "appLikeProgress": True,
                "phoneNotificationChannels": overnight_digest["delivery"]["channels"],
                "targetSurfaces": ["phone", "tablet", "desktop-web", "tauri"],
                "recommendedRefreshSeconds": 20,
                "detailPayload": "get_control_room_snapshot_command",
            },
            "summaryShaping": {
                "schema": "fluxio.control_room.summary_shaping.v1",
                "mode": "bounded_live_summary",
                "richContextRoots": "active_missions_only",
                "skillCatalogRows": "bounded_live_samples_with_total_counts",
                "projectProgressRows": "bounded_project_milestones_and_receipts",
                "redTeamHistoryRows": "recent_rows_with_full_summary_counts",
                "harnessLab": "route_trust_coverage_only",
                "systemAuditDigest": "operator_summary_fields_only",
                "terminalMissionContextRoots": "placeholder_requires_mission_detail",
                "missionDetailCommand": "get_control_room_mission_detail_command",
                "fullSnapshotCommand": "get_control_room_snapshot_command",
                "reason": "Keep live summary responsive while preserving real mission detail through explicit drill-down endpoints.",
            },
        }
        record_section("payload_assembly")
        performance = {
            "source": "control_room_summary",
            "durationMs": round((time.perf_counter() - started) * 1000, 2),
            "missionLimit": len(mission_payload),
            "activityLimit": len(activity),
            "sectionDurations": section_durations,
            "slowestSections": sorted(
                section_durations,
                key=lambda item: float(item.get("durationMs") or 0),
                reverse=True,
            )[:5],
            "virtualization": {
                "summaryFirst": True,
                "lazyMissionDetail": True,
                "boundedMissionRows": len(recent_missions),
                "boundedActivityRows": 24,
                "detailCommand": "control-room-mission-detail",
            },
        }
        payload["performance"] = performance
        payload["performance"]["payloadBytes"] = len(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )
        payload["performance"]["budget"] = self._performance_budget_payload(
            source="control_room_summary",
            duration_ms=payload["performance"]["durationMs"],
            payload_bytes=payload["performance"]["payloadBytes"],
            duration_budget_ms=CONTROL_ROOM_SUMMARY_DURATION_BUDGET_MS,
            payload_budget_bytes=CONTROL_ROOM_SUMMARY_PAYLOAD_BUDGET_BYTES,
            item_limits={
                "missions": CONTROL_ROOM_FULL_SUMMARY_MISSION_LIMIT,
                "activity": 24,
                "notifications": 24,
                "overnightDigest": 1,
                "projectProgressHistory": len(project_progress_history["projects"]),
                "workspaces": len(workspace_payload),
                "richContextRoots": sum(
                    1
                    for item in mission_payload
                    if (item.get("contextRoots") or {}).get("status") != "detail_required"
                ),
                "skills": len(skill_catalog.get("learnedSkills", []))
                + len(skill_catalog.get("userInstalledSkills", []))
                + len(skill_catalog.get("recommendedPacks", []))
                + len(skill_catalog.get("curatedPacks", [])),
                "systemAuditDigest": 1,
            },
        )
        payload["performance"]["payloadBytes"] = len(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )
        payload["performance"]["budget"] = self._performance_budget_payload(
            source="control_room_summary",
            duration_ms=payload["performance"]["durationMs"],
            payload_bytes=payload["performance"]["payloadBytes"],
            duration_budget_ms=CONTROL_ROOM_SUMMARY_DURATION_BUDGET_MS,
            payload_budget_bytes=CONTROL_ROOM_SUMMARY_PAYLOAD_BUDGET_BYTES,
            item_limits={
                "missions": CONTROL_ROOM_FULL_SUMMARY_MISSION_LIMIT,
                "activity": 24,
                "notifications": 24,
                "overnightDigest": 1,
                "projectProgressHistory": len(project_progress_history["projects"]),
                "workspaces": len(workspace_payload),
                "richContextRoots": sum(
                    1
                    for item in mission_payload
                    if (item.get("contextRoots") or {}).get("status") != "detail_required"
                ),
                "skills": len(skill_catalog.get("learnedSkills", []))
                + len(skill_catalog.get("userInstalledSkills", []))
                + len(skill_catalog.get("recommendedPacks", []))
                + len(skill_catalog.get("curatedPacks", [])),
                "systemAuditDigest": 1,
            },
        )
        return payload

    @staticmethod
    def _summary_skill_catalog_payload(skill_catalog: dict) -> dict:
        if not isinstance(skill_catalog, dict):
            return {}
        recommended = list(skill_catalog.get("recommendedPacks") or [])
        curated = list(skill_catalog.get("curatedPacks") or [])
        installed = list(skill_catalog.get("userInstalledSkills") or [])
        learned = list(skill_catalog.get("learnedSkills") or [])
        feedback_loop = dict(skill_catalog.get("feedbackLoop") or {})
        if isinstance(feedback_loop.get("latest"), list):
            feedback_loop["latest"] = feedback_loop["latest"][:6]
        if isinstance(feedback_loop.get("repairProposals"), list):
            feedback_loop["repairProposals"] = feedback_loop["repairProposals"][:4]
        routing = feedback_loop.get("systemLossRouting")
        if isinstance(routing, dict):
            feedback_loop["systemLossRouting"] = {
                **routing,
                "activeRepairSkillIds": list(routing.get("activeRepairSkillIds") or [])[:8],
                "preferredSkillIds": list(routing.get("preferredSkillIds") or [])[:8],
            }
        return {
            **skill_catalog,
            "curatedPacks": [
                ControlRoomStore._summary_skill_row_payload(item)
                for item in curated[:12]
            ],
            "recommendedPacks": [
                ControlRoomStore._summary_skill_row_payload(item)
                for item in recommended[:8]
            ],
            "userInstalledSkills": [
                ControlRoomStore._summary_skill_row_payload(item)
                for item in installed[:8]
            ],
            "learnedSkills": [
                ControlRoomStore._summary_skill_row_payload(item)
                for item in learned[:8]
            ],
            "feedbackLoop": feedback_loop,
            "summaryTruncation": {
                "schema": "fluxio.summary_truncation.v1",
                "liveData": True,
                "detailCommand": "get_control_room_snapshot_command",
                "curatedTotal": len(curated),
                "curatedShown": min(len(curated), 12),
                "recommendedTotal": len(recommended),
                "recommendedShown": min(len(recommended), 8),
                "installedTotal": len(installed),
                "installedShown": min(len(installed), 8),
                "learnedTotal": len(learned),
                "learnedShown": min(len(learned), 8),
            },
        }

    @staticmethod
    def _summary_skill_row_payload(row: dict) -> dict:
        if not isinstance(row, dict):
            return {}
        feedback = row.get("feedbackSummary") if isinstance(row.get("feedbackSummary"), dict) else {}
        operator_value = (
            feedback.get("operatorValue")
            if isinstance(feedback.get("operatorValue"), dict)
            else {}
        )
        repair_proposal = (
            feedback.get("repairProposal")
            if isinstance(feedback.get("repairProposal"), dict)
            else {}
        )
        compact_feedback = {
            "sliceCount": feedback.get("sliceCount", 0),
            "trend": feedback.get("trend", ""),
            "latestSystemLoss": feedback.get("latestSystemLoss"),
            "averageSystemLoss": feedback.get("averageSystemLoss"),
            "operatorValue": {
                "sampleCount": operator_value.get("sampleCount", 0),
                "state": operator_value.get("state", ""),
                "averageScore": operator_value.get("averageScore"),
            },
            "repairProposal": {
                "status": repair_proposal.get("status", ""),
                "title": repair_proposal.get("title", ""),
                "nextAction": repair_proposal.get("nextAction", ""),
            },
        }
        compact = {
            "packId": row.get("packId") or row.get("pack_id") or row.get("skill_id") or row.get("id") or "",
            "pack_id": row.get("pack_id") or row.get("packId") or "",
            "skill_id": row.get("skill_id") or row.get("id") or "",
            "id": row.get("id") or row.get("skill_id") or row.get("packId") or row.get("pack_id") or "",
            "label": row.get("label") or row.get("name") or "",
            "description": str(row.get("description") or "")[:220],
            "promptHint": str(row.get("promptHint") or row.get("prompt_hint") or "")[:220],
            "originType": row.get("originType") or (row.get("source") or {}).get("kind", "")
            if isinstance(row.get("source"), dict)
            else row.get("originType", ""),
            "testStatus": row.get("testStatus") or row.get("test_status") or "",
            "promotionState": row.get("promotionState") or row.get("promotion_state") or "",
            "status": row.get("status", ""),
            "installed": bool(row.get("installed", False)),
            "execution_capable": bool(row.get("execution_capable", False)),
            "guidance_only": bool(row.get("guidance_only", False)),
            "usageCount": row.get("usageCount", row.get("usage_count", 0)),
            "helpedCount": row.get("helpedCount", row.get("helped_count", 0)),
            "permissions": list(row.get("permissions") or [])[:6],
            "profile_suitability": list(row.get("profile_suitability") or [])[:6],
            "tags": list(row.get("tags") or [])[:6],
            "feedbackSummary": compact_feedback,
            "summaryCompaction": {
                "schema": "fluxio.skill_summary_compaction.v1",
                "mode": "operator_skill_index_row",
                "liveData": True,
                "detailCommand": "get_control_room_snapshot_command",
            },
        }
        return compact

    @staticmethod
    def _summary_red_team_escalation_payload(red_team_escalation: dict) -> dict:
        if not isinstance(red_team_escalation, dict):
            return {}
        history = list(red_team_escalation.get("history") or [])
        audit = red_team_escalation.get("escalationAudit")
        compact_audit = audit
        if isinstance(audit, dict):
            compact_audit = {
                "schema": audit.get("schema", "fluxio.red_team_escalation_audit.v1"),
                "status": audit.get("status", ""),
                "targetCount": audit.get("targetCount", 0),
                "satisfiedTargets": audit.get("satisfiedTargets", 0),
                "pendingTargets": audit.get("pendingTargets", 0),
                "latestTargetPending": audit.get("latestTargetPending", False),
                "nextAction": audit.get("nextAction", ""),
            }
        return {
            **red_team_escalation,
            "history": history[-6:],
            "escalationAudit": compact_audit,
            "summaryTruncation": {
                "schema": "fluxio.summary_truncation.v1",
                "liveData": True,
                "historyTotal": len(history),
                "historyShown": min(len(history), 6),
                "detailCommand": "get_control_room_snapshot_command",
            },
        }

    @staticmethod
    def _summary_system_audit_digest_payload(system_audit_digest: dict) -> dict:
        if not isinstance(system_audit_digest, dict):
            return {}
        digest = dict(system_audit_digest)
        if isinstance(digest.get("systemLossBreakdown"), dict):
            breakdown = dict(digest["systemLossBreakdown"])
            breakdown["drivers"] = list(breakdown.get("drivers") or [])[:4]
            digest["systemLossBreakdown"] = breakdown
        if isinstance(digest.get("watchdogSelfImprovement"), dict):
            watchdog = dict(digest["watchdogSelfImprovement"])
            watchdog["recentReceipts"] = list(watchdog.get("recentReceipts") or [])[-3:]
            digest["watchdogSelfImprovement"] = watchdog
        for key, limit in (
            ("deficits", 6),
            ("badFirst", 4),
            ("improvementQueue", 6),
            ("activeGapMissions", 4),
        ):
            if isinstance(digest.get(key), list):
                digest[key] = digest[key][:limit]
        if isinstance(digest.get("t3Reference"), dict):
            t3_reference = dict(digest["t3Reference"])
            if isinstance(t3_reference.get("strengthsToBeat"), list):
                t3_reference["strengthsToBeat"] = t3_reference["strengthsToBeat"][:6]
            digest["t3Reference"] = t3_reference
        if isinstance(digest.get("publicLaunchReadiness"), dict):
            public_launch = dict(digest["publicLaunchReadiness"])
            repair_packet = (
                dict(public_launch.get("repairPacket"))
                if isinstance(public_launch.get("repairPacket"), dict)
                else {}
            )
            if repair_packet:
                repair_packet = {
                    key: repair_packet.get(key)
                    for key in (
                        "schema",
                        "status",
                        "canClaimPublicLaunch",
                        "internalPacketReady",
                        "primaryBlocker",
                        "sourceCoverage",
                        "sourceDirtyPathCount",
                        "releaseBlockingPathCount",
                        "releaseBlockingSampleCount",
                        "privateOrGeneratedPathCount",
                        "publicWebUrl",
                        "workflowRun",
                        "gitHead",
                        "deployedSha",
                        "nextAction",
                        "orderedLanes",
                        "stagingPlan",
                        "commands",
                        "receiptTargets",
                    )
                    if key in repair_packet
                }
                staging_plan = (
                    dict(repair_packet.get("stagingPlan"))
                    if isinstance(repair_packet.get("stagingPlan"), dict)
                    else {}
                )
                if staging_plan:
                    staging_plan["groups"] = [
                        item
                        for item in list(staging_plan.get("groups") or [])[:4]
                        if isinstance(item, dict)
                    ]
                    repair_packet["stagingPlan"] = staging_plan
                repair_packet["orderedLanes"] = [
                    item
                    for item in list(repair_packet.get("orderedLanes") or [])[:5]
                    if isinstance(item, dict)
                ]
                repair_packet["commands"] = [
                    item
                    for item in list(repair_packet.get("commands") or [])[:4]
                    if isinstance(item, dict)
                ]
                repair_packet["receiptTargets"] = [
                    item
                    for item in list(repair_packet.get("receiptTargets") or [])[:3]
                    if isinstance(item, dict)
                ]
                public_launch["repairPacket"] = repair_packet
            public_web = (
                dict(public_launch.get("publicWeb"))
                if isinstance(public_launch.get("publicWeb"), dict)
                else {}
            )
            if public_web:
                dirty_triage = (
                    dict(public_web.get("dirtySourceTriage"))
                    if isinstance(public_web.get("dirtySourceTriage"), dict)
                    else {}
                )
                if dirty_triage:
                    dirty_triage = {
                        key: dirty_triage.get(key)
                        for key in (
                            "schema",
                            "dirtyPathCount",
                            "sampleCount",
                            "releaseBlockingSampleCount",
                            "releaseBlockingPathCount",
                            "privateOrGeneratedPathCount",
                            "laneCounts",
                            "nextAction",
                        )
                        if key in dirty_triage
                    }
                public_web = {
                    key: public_web.get(key)
                    for key in (
                        "url",
                        "workflowRun",
                        "publicationCurrent",
                        "sourceDirtyPathCount",
                        "currentGitDirtyPathCount",
                        "sourceDirtyPathSample",
                    )
                    if key in public_web
                }
                public_web["sourceDirtyPathSample"] = [
                    str(item)
                    for item in list(public_web.get("sourceDirtyPathSample") or [])[:8]
                    if str(item or "").strip()
                ]
                if dirty_triage:
                    public_web["dirtySourceTriage"] = dirty_triage
                public_launch["publicWeb"] = public_web
            if isinstance(public_launch.get("stagingProof"), dict):
                staging_proof = public_launch["stagingProof"]
                public_launch["stagingProof"] = {
                    key: staging_proof.get(key)
                    for key in (
                        "schema",
                        "status",
                        "releaseImpactPathCount",
                        "releaseBlockingPathCount",
                        "evidencePath",
                        "nextAction",
                        "checkedAt",
                    )
                    if key in staging_proof
                }
            public_launch["checks"] = [
                item
                for item in list(public_launch.get("checks") or [])[:6]
                if isinstance(item, dict)
            ]
            public_launch["blockers"] = [
                item
                for item in list(public_launch.get("blockers") or [])[:3]
                if isinstance(item, dict)
            ]
            public_launch["missing"] = [
                str(item)
                for item in list(public_launch.get("missing") or [])[:4]
                if str(item or "").strip()
            ]
            digest["publicLaunchReadiness"] = public_launch
        digest["summaryTruncation"] = {
            "schema": "fluxio.summary_truncation.v1",
            "liveData": True,
            "mode": "operator_system_audit_digest",
            "detailCommand": "get_control_room_snapshot_command",
        }
        return digest

    @staticmethod
    def _summary_project_progress_payload(project_progress_history: dict) -> dict:
        if not isinstance(project_progress_history, dict):
            return {}
        projects = []
        for project in list(project_progress_history.get("projects") or []):
            if not isinstance(project, dict):
                continue
            compact = dict(project)
            compact["milestones"] = list(compact.get("milestones") or [])[:5]
            compact["buckets"] = list(compact.get("buckets") or [])[:5]
            launch_rehearsal = compact.get("launchRehearsal")
            if isinstance(launch_rehearsal, dict):
                compact_launch = dict(launch_rehearsal)
                compact_launch["receiptHistory"] = list(compact_launch.get("receiptHistory") or [])[:2]
                compact["launchRehearsal"] = compact_launch
            projects.append(compact)
        scheduling_queue = [
            item
            for item in list(project_progress_history.get("schedulingQueue") or [])[:8]
            if isinstance(item, dict)
        ]
        return {
            **project_progress_history,
            "projects": projects,
            "schedulingQueue": scheduling_queue,
            "summaryTruncation": {
                "schema": "fluxio.summary_truncation.v1",
                "liveData": True,
                "projectTotal": len(list(project_progress_history.get("projects") or [])),
                "projectShown": len(projects),
                "milestoneLimitPerProject": 5,
                "bucketLimitPerProject": 5,
                "schedulingQueueLimit": 8,
                "detailCommand": "get_control_room_snapshot_command",
            },
        }

    @staticmethod
    def _summary_terminal_mission_payload(row: dict) -> dict:
        if not isinstance(row, dict):
            return {}
        return {
            "mission_id": row.get("mission_id", ""),
            "workspace_id": row.get("workspace_id", ""),
            "title": row.get("title", ""),
            "objective": str(row.get("objective") or "")[:160],
            "runtime_id": row.get("runtime_id", ""),
            "harness_id": row.get("harness_id", ""),
            "status": row.get("status", ""),
            "planner_loop_status": row.get("planner_loop_status", ""),
            "phase": row.get("phase", ""),
            "queue_position": row.get("queue_position", 0),
            "continuity_state": row.get("continuity_state", ""),
            "current_runtime_lane": row.get("current_runtime_lane", ""),
            "last_runtime_event": str(row.get("last_runtime_event") or "")[:160],
            "last_error": str(row.get("last_error") or "")[:160],
            "elapsedRuntimeSeconds": row.get("elapsedRuntimeSeconds", 0),
            "remainingRuntimeSeconds": row.get("remainingRuntimeSeconds", 0),
            "maxRuntimeSeconds": row.get("maxRuntimeSeconds", 0),
            "timeBudgetStatus": row.get("timeBudgetStatus", ""),
            "liveProgress": row.get("liveProgress", {}),
            "updated_at": row.get("updated_at", ""),
            "created_at": row.get("created_at", ""),
            "proofSummary": str(row.get("proofSummary") or "")[:180],
            "passedChecks": row.get("passedChecks", 0),
            "failedChecks": row.get("failedChecks", 0),
            "pendingApprovals": row.get("pendingApprovals", 0),
            "blockedBy": list(row.get("blockedBy") or [])[:2],
            "plannedScopeArtifacts": {},
            "runtimeLanes": [],
            "delegatedLaneCount": int(row.get("delegatedLaneCount") or 0),
            "activeDelegatedLaneCount": 0,
            "delegatedRuntime": {
                "status": (row.get("delegatedRuntime") or {}).get("status", "")
                if isinstance(row.get("delegatedRuntime"), dict)
                else "",
                "targetProvider": (row.get("delegatedRuntime") or {}).get("targetProvider", "")
                if isinstance(row.get("delegatedRuntime"), dict)
                else "",
                "targetModel": (row.get("delegatedRuntime") or {}).get("targetModel", "")
                if isinstance(row.get("delegatedRuntime"), dict)
                else "",
            },
            "summaryCompaction": {
                "schema": "fluxio.mission_summary_compaction.v1",
                "mode": "terminal_index_row",
                "liveData": True,
                "detailCommand": "get_control_room_mission_detail_command",
            },
        }

    def build_bootstrap_summary_snapshot(self) -> dict:
        started = time.perf_counter()
        workspaces = self.load_workspaces()
        missions = self.load_missions()
        activity = self.recent_events(limit=24)
        provider_auth_presence = _provider_auth_presence_from_env()

        status_counts: dict[str, int] = {}
        runtime_counts: dict[str, int] = {}
        workspace_missions: dict[str, list[Mission]] = {}
        for mission in missions:
            status_counts[mission.state.status] = status_counts.get(mission.state.status, 0) + 1
            runtime_counts[mission.runtime_id] = runtime_counts.get(mission.runtime_id, 0) + 1
            workspace_missions.setdefault(mission.workspace_id, []).append(mission)

        workspace_by_id = {workspace.workspace_id: workspace for workspace in workspaces}
        workspace_payload = []
        mission_launch_shortcuts = []
        for workspace in workspaces:
            related = workspace_missions.get(workspace.workspace_id, [])
            active_mission = self._active_workspace_mission(workspace.workspace_id, related)
            queued_count = sum(
                1
                for mission in related
                if mission.state.status not in TERMINAL_MISSION_STATUSES
                and mission.state.queue_position > 0
            )
            workspace_payload.append(
                {
                    "workspace_id": workspace.workspace_id,
                    "name": workspace.name,
                    "root_path": workspace.root_path,
                    "workspace_type": workspace.workspace_type,
                    "default_runtime": workspace.default_runtime,
                    "preferred_harness": workspace.preferred_harness,
                    "user_profile": workspace.user_profile,
                    "enabled": workspace.enabled,
                    "updated_at": workspace.updated_at,
                    "activeMissionId": active_mission.mission_id if active_mission else "",
                    "activeMissionTitle": active_mission.title if active_mission else "",
                    "activeMissionStatus": active_mission.state.status if active_mission else "",
                    "queuedMissionCount": queued_count,
                    "missionCount": len(related),
                }
            )
            mission_launch_shortcuts.append(
                self._mission_launch_shortcut_payload(workspace)
            )

        sorted_missions = sorted(
            missions,
            key=lambda item: item.updated_at or item.created_at or "",
            reverse=True,
        )
        active_bootstrap_missions = [
            mission
            for mission in sorted_missions
            if mission.state.status not in TERMINAL_MISSION_STATUSES
            and mission.state.status != "draft"
        ]
        recent_missions = []
        seen_bootstrap_mission_ids: set[str] = set()
        for mission in [*active_bootstrap_missions, *sorted_missions]:
            if mission.mission_id in seen_bootstrap_mission_ids:
                continue
            seen_bootstrap_mission_ids.add(mission.mission_id)
            recent_missions.append(mission)
            if len(recent_missions) >= max(CONTROL_ROOM_BOOTSTRAP_MISSION_LIMIT, len(active_bootstrap_missions)):
                break
        mission_payload = []
        for mission in recent_missions:
            mission_active = (
                mission.state.status not in TERMINAL_MISSION_STATUSES
                and mission.state.status != "draft"
            )
            mission.state.provider_runtime_truth = _provider_truth_for_mission(
                mission,
                auth_presence=provider_auth_presence,
                workspace=workspace_by_id.get(mission.workspace_id),
            )
            row = self._mission_summary_payload(
                mission,
                root=self.root if mission_active else None,
                workspace=workspace_by_id.get(mission.workspace_id),
            )
            if mission_active:
                row["contextRoots"] = self._mission_context_roots_payload(
                    mission,
                    workspace=workspace_by_id.get(mission.workspace_id),
                    workspaces=workspaces,
                    workspace_missions=workspace_missions,
                )
            else:
                row["contextRoots"] = self._bootstrap_context_roots_placeholder(mission)
            mission_payload.append(row)

        notifications = self._build_notification_feed(
            missions=recent_missions,
            activity=activity,
            root=self.root,
            workspace_by_id=workspace_by_id,
        )
        overnight_digest = self._overnight_progress_digest_payload(
            missions=missions,
            recent_missions=recent_missions,
            workspaces=workspaces,
            activity=activity,
            notifications=notifications,
            telegram_destination=load_telegram_destination(self.root),
            delivery_receipts=[asdict(item) for item in load_delivery_receipts(self.root, limit=24)],
        )
        payload = {
            "schema": "fluxio.control_room.summary.v1",
            "summaryMode": "bootstrap",
            "workspaceRoot": str(self.root),
            "generatedAt": utc_now_iso(),
            "counts": {
                "workspaces": len(workspaces),
                "missions": len(missions),
                "activeMissions": sum(
                    1
                    for item in missions
                    if item.state.status not in TERMINAL_MISSION_STATUSES
                    and item.state.status != "draft"
                    and item.state.queue_position == 0
                ),
                "queuedMissions": sum(
                    1
                    for item in missions
                    if item.state.status not in TERMINAL_MISSION_STATUSES
                    and item.state.queue_position > 0
                ),
                "blockedMissions": status_counts.get("blocked", 0)
                + status_counts.get("needs_approval", 0)
                + status_counts.get("verification_failed", 0),
                "completedMissions": status_counts.get("completed", 0),
            },
            "statusCounts": status_counts,
            "runtimeCounts": runtime_counts,
            "workspaces": workspace_payload,
            "missions": mission_payload,
            "notifications": notifications,
            "overnightDigest": overnight_digest,
            "projectProgressHistory": {
                "schema": "fluxio.project_progress_history.v1",
                "generatedAt": utc_now_iso(),
                "source": "bootstrap_mission_store",
                "projects": [],
                "schedulingQueue": [],
                "empty": True,
            },
            "missionLaunchShortcuts": mission_launch_shortcuts,
            "providers": {
                "authPresence": provider_auth_presence,
                "checkedAt": utc_now_iso(),
                "consistentHermesCredentialPool": True,
            },
            "mobileWeb": {
                "summaryFirst": True,
                "notificationFeed": True,
                "overnightDigest": True,
                "appLikeProgress": True,
                "phoneNotificationChannels": overnight_digest["delivery"]["channels"],
                "targetSurfaces": ["phone", "tablet", "desktop-web", "tauri"],
                "recommendedRefreshSeconds": 20,
                "detailPayload": "get_control_room_snapshot_command",
            },
        }
        payload["systemAuditDigest"] = self._summary_system_audit_digest_payload(
            _build_bootstrap_system_audit_digest(
                root=self.root,
                missions=missions,
                workspaces=workspaces,
            )
        )
        payload["performance"] = {
            "source": "control_room_summary_bootstrap",
            "durationMs": round((time.perf_counter() - started) * 1000, 2),
            "missionLimit": len(mission_payload),
            "activityLimit": len(activity),
            "payloadBytes": len(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
            "budget": self._performance_budget_payload(
                source="control_room_summary_bootstrap",
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                payload_bytes=len(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
                duration_budget_ms=CONTROL_ROOM_SUMMARY_DURATION_BUDGET_MS,
                payload_budget_bytes=CONTROL_ROOM_SUMMARY_PAYLOAD_BUDGET_BYTES,
                item_limits={
                    "missions": len(recent_missions),
                    "activity": 24,
                    "notifications": 24,
                    "overnightDigest": 1,
                    "workspaces": len(workspace_payload),
                    "bootstrapMissionLimit": CONTROL_ROOM_BOOTSTRAP_MISSION_LIMIT,
                },
            ),
        }
        payload["performance"]["payloadBytes"] = len(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )
        return payload

    @staticmethod
    def _bootstrap_context_roots_placeholder(mission: Mission) -> dict:
        return {
            "schema": "fluxio.mission.context_roots.v1",
            "missionId": mission.mission_id,
            "source": "summary_deferred_terminal_context",
            "status": "detail_required",
            "liveData": True,
            "deferredToDetail": True,
            "writeScopePreflight": {
                "schema": "fluxio.write_scope_preflight.v1",
                "status": "deferred_terminal_mission",
                "nextAction": "Open mission detail to inspect archived terminal context roots.",
            },
            "counts": {
                "totalRoots": 0,
                "relatedWorkspaces": 0,
                "dependencyEdges": 0,
            },
            "policy": {
                "relatedWorkspaceWritePolicy": "deferred_to_mission_detail",
                "terminalMission": True,
            },
            "nextAction": "Open mission detail to inspect archived terminal context roots.",
        }

    @staticmethod
    def _project_progress_history_payload(
        *,
        root: Path,
        workspaces: list[WorkspaceProfile],
        missions: list[Mission],
        events: list[dict],
        workspace_missions: dict[str, list[Mission]],
    ) -> dict:
        mission_by_id = {mission.mission_id: mission for mission in missions}
        events_by_workspace: dict[str, list[dict]] = {workspace.workspace_id: [] for workspace in workspaces}
        workspace_by_id = {workspace.workspace_id: workspace for workspace in workspaces}
        for event in events:
            mission_id = str(event.get("mission_id") or event.get("missionId") or "").strip()
            mission = mission_by_id.get(mission_id)
            workspace_id = str(
                event.get("workspace_id")
                or event.get("workspaceId")
                or (event.get("metadata") or {}).get("workspaceId")
                or (mission.workspace_id if mission else "")
            ).strip()
            if not workspace_id:
                continue
            events_by_workspace.setdefault(workspace_id, []).append(event)

        projects: list[dict] = []
        for workspace in workspaces:
            rows = sorted(
                workspace_missions.get(workspace.workspace_id, []),
                key=lambda mission: mission.updated_at or mission.created_at or "",
                reverse=True,
            )
            active = [
                mission
                for mission in rows
                if mission.state.status not in TERMINAL_MISSION_STATUSES
                and mission.state.status != "draft"
                and mission.state.queue_position == 0
            ]
            queued = [
                mission
                for mission in rows
                if mission.state.status not in TERMINAL_MISSION_STATUSES
                and mission.state.queue_position > 0
            ]
            blocked = [
                mission
                for mission in rows
                if mission.state.status not in TERMINAL_MISSION_STATUSES
                and (
                    mission.state.status in {"blocked", "needs_approval", "verification_failed"}
                    or mission.proof.pending_approvals
                    or mission.proof.failed_checks
                    or mission.state.verification_failures
                )
            ]
            completed = [mission for mission in rows if mission.state.status == "completed"]
            workspace_events = sorted(
                events_by_workspace.get(workspace.workspace_id, []),
                key=lambda event: _event_timestamp(event),
                reverse=True,
            )
            milestones: list[dict] = []
            for event in workspace_events[:12]:
                mission_id = str(event.get("mission_id") or event.get("missionId") or "").strip()
                mission = mission_by_id.get(mission_id)
                milestones.append(
                    {
                        "id": f"{workspace.workspace_id}:{mission_id or 'workspace'}:{_event_timestamp(event)}:{event.get('kind', 'event')}",
                        "source": "mission_events",
                        "missionId": mission_id,
                        "missionTitle": mission.title if mission else "",
                        "kind": str(event.get("kind") or "event"),
                        "message": str(event.get("message") or ""),
                        "timestamp": _event_timestamp(event),
                        "tone": _project_event_tone(event),
                    }
                )
            for mission in rows[:8]:
                if any(item["missionId"] == mission.mission_id and item["kind"] == "mission_state" for item in milestones):
                    continue
                milestones.append(
                    {
                        "id": f"{workspace.workspace_id}:{mission.mission_id}:mission_state",
                        "source": "mission_store",
                        "missionId": mission.mission_id,
                        "missionTitle": mission.title or mission.objective,
                        "kind": "mission_state",
                        "message": f"{mission.state.status}: {mission.proof.summary or mission.state.last_runtime_event or 'Mission state recorded.'}",
                        "timestamp": mission.updated_at or mission.created_at,
                        "tone": (
                            "bad"
                            if mission.state.status in {"failed", "verification_failed"}
                            else "warn"
                            if mission in blocked or mission.state.status in {"blocked", "needs_approval", "queued"}
                            else "good"
                            if mission.state.status == "completed"
                            else "neutral"
                        ),
                    }
                )
            milestones = sorted(
                milestones,
                key=lambda item: item.get("timestamp") or "",
                reverse=True,
            )[:14]
            bucket_map: dict[str, dict] = {}
            for mission in rows:
                timestamp = mission.updated_at or mission.created_at or ""
                day = timestamp[:10] if len(timestamp) >= 10 else "unknown"
                bucket = bucket_map.setdefault(
                    day,
                    {
                        "date": day,
                        "missionsTouched": 0,
                        "completed": 0,
                        "active": 0,
                        "blocked": 0,
                    },
                )
                bucket["missionsTouched"] += 1
                if mission.state.status == "completed":
                    bucket["completed"] += 1
                if mission in active:
                    bucket["active"] += 1
                if mission in blocked:
                    bucket["blocked"] += 1
            buckets = sorted(bucket_map.values(), key=lambda item: item["date"], reverse=True)[:10]
            latest = rows[0] if rows else None
            if blocked:
                next_action = "Review the first blocked mission or failed check before dispatching more project work."
            elif active:
                next_action = "Let the active mission continue and watch for the next slice-complete notification."
            elif queued:
                next_action = "Resume the front queued mission once the workspace slot is available."
            elif completed:
                next_action = "Open the latest proof digest and decide the next project mission."
            else:
                next_action = "Launch the first mission for this project."
            schedule = ControlRoomStore._project_schedule_recommendation(
                workspace=workspace,
                rows=rows,
                active=active,
                queued=queued,
                blocked=blocked,
                completed=completed,
                workspaces=workspaces,
                workspace_missions=workspace_missions,
                workspace_by_id=workspace_by_id,
            )
            sync_authority = ControlRoomStore._workspace_sync_authority(workspace)
            launch_rehearsal = ControlRoomStore._cross_device_launch_rehearsal(
                workspace=workspace,
                schedule=schedule,
                sync_authority=sync_authority,
            )
            latest_launch_receipt = _latest_cross_device_launch_receipt(
                root,
                workspace.workspace_id,
            )
            launch_receipt_history = _cross_device_launch_receipt_history(
                root,
                workspace_id=workspace.workspace_id,
                limit=6,
            )
            if latest_launch_receipt:
                launch_rehearsal = {
                    **launch_rehearsal,
                    "latestReceipt": latest_launch_receipt,
                    "receiptHistory": launch_receipt_history,
                    "receiptCount": len(launch_receipt_history),
                    "receiptTrendStatus": "repeated" if len(launch_receipt_history) >= 2 else "single",
                    "receiptBacked": True,
                }
            projects.append(
                {
                    "schema": "fluxio.project_progress.v1",
                    "workspaceId": workspace.workspace_id,
                    "workspaceName": workspace.name,
                    "rootPath": workspace.root_path,
                    "runtime": workspace.default_runtime,
                    "harness": workspace.preferred_harness,
                    "counts": {
                        "missions": len(rows),
                        "active": len(active),
                        "queued": len(queued),
                        "blocked": len(blocked),
                        "completed": len(completed),
                        "events": len(workspace_events),
                    },
                    "latestMissionId": latest.mission_id if latest else "",
                    "latestMissionTitle": latest.title or latest.objective if latest else "",
                    "latestUpdatedAt": latest.updated_at or latest.created_at if latest else workspace.updated_at,
                    "milestones": milestones,
                    "buckets": buckets,
                    "nextAction": next_action,
                    "scheduleRecommendation": schedule,
                    "syncAuthority": sync_authority,
                    "launchRehearsal": launch_rehearsal,
                    "liveData": True,
                    "empty": len(rows) == 0 and len(workspace_events) == 0,
                }
            )
        scheduling_queue = sorted(
            [
                project["scheduleRecommendation"]
                for project in projects
                if isinstance(project.get("scheduleRecommendation"), dict)
            ],
            key=lambda item: (
                -int(item.get("priorityScore", 0) or 0),
                str(item.get("workspaceName") or ""),
            ),
        )
        return {
            "schema": "fluxio.project_progress_history.v1",
            "generatedAt": utc_now_iso(),
            "source": "mission_store_and_mission_events",
            "eventLimit": len(events),
            "projects": projects,
            "schedulingQueue": scheduling_queue[:12],
            "launchReceiptSummary": _cross_device_launch_receipt_summary(root),
            "scheduler": {
                "schema": "fluxio.dependency_aware_project_scheduler.v1",
                "source": "workspace_mission_counts_and_context_roots",
                "queueSize": len(scheduling_queue),
                "topWorkspaceId": scheduling_queue[0]["workspaceId"] if scheduling_queue else "",
                "nextAction": (
                    scheduling_queue[0]["recommendedAction"]
                    if scheduling_queue
                    else "Register a workspace and launch the first mission."
                ),
            },
            "empty": not projects,
        }

    @staticmethod
    def _workspace_dependency_ids(workspace: WorkspaceProfile) -> set[str]:
        dependency_ids: set[str] = set()
        for goal in workspace.goals:
            text = str(goal or "").strip()
            lowered = text.lower()
            for prefix in ("depends_on:", "depends-on:", "dependency:", "dependency=", "upstream:"):
                if not lowered.startswith(prefix):
                    continue
                raw_ids = text[len(prefix) :]
                for item in re.split(r"[,;\s]+", raw_ids):
                    dependency_id = item.strip()
                    if dependency_id:
                        dependency_ids.add(dependency_id)
                break
        return dependency_ids

    @staticmethod
    def _workspace_sync_authority(workspace: WorkspaceProfile) -> dict[str, object]:
        sync_status = _workspace_sync_status(workspace)
        sync_receipt = (
            sync_status.get("syncReceipt", {})
            if isinstance(sync_status.get("syncReceipt"), dict)
            else {}
        )
        conflict_count = int(sync_status.get("conflictsDetected") or sync_receipt.get("conflictsDetected") or 0)
        manual_review = bool(sync_status.get("manualReviewRequired") or sync_receipt.get("manualReviewRequired"))
        effective_direction = str(
            sync_status.get("effectiveDirection")
            or sync_receipt.get("effectiveDirection")
            or workspace.sync_direction
            or "manual"
        )
        local_path = str(workspace.local_project_path or "").strip()
        nas_path = str(workspace.nas_project_path or "").strip()
        current_root = str(workspace.root_path or "").strip()
        receipt_id = str(sync_receipt.get("receiptId") or "")
        if manual_review or conflict_count > 0:
            state = "conflict_review"
            authority = "manual_review"
            launch_safety = "review_required"
            safe_for_writable_dependency = False
            summary = "Sync conflicts require operator review before this workspace is used as a writable dependency."
            next_action = "Resolve sync conflicts or choose the authoritative copy before launching dependent work."
        elif workspace.auto_sync_to_nas and nas_path:
            if effective_direction == "local_to_nas":
                state = "local_authoritative"
                authority = "local"
                summary = "Computer copy is the write source and NAS is the mirror target."
            elif effective_direction == "nas_to_local":
                state = "nas_authoritative"
                authority = "nas"
                summary = "NAS copy is the write source and computer copy is the mirror target."
            elif receipt_id:
                state = "bidirectional_synced"
                authority = "bidirectional"
                summary = "Computer and NAS copies have a sync receipt and no pending conflict review."
            else:
                state = "nas_mirror_unverified"
                authority = "nas"
                summary = "NAS mirroring is configured, but no current sync receipt proves the copies are aligned."
            launch_safety = "safe" if receipt_id or effective_direction in {"local_to_nas", "nas_to_local"} else "verify_first"
            safe_for_writable_dependency = launch_safety == "safe"
            next_action = (
                "Writable dependency use is allowed; keep receipts attached to future sync changes."
                if safe_for_writable_dependency
                else "Run a sync check before using this workspace as a writable dependency."
            )
        elif local_path and nas_path:
            state = "sync_configured_unverified"
            authority = "manual"
            launch_safety = "verify_first"
            safe_for_writable_dependency = False
            summary = "Both local and NAS paths are configured, but automatic sync is not active."
            next_action = "Pick local, NAS, or bidirectional sync authority before dependent launch."
        else:
            state = "manual_local"
            authority = "workspace_root"
            launch_safety = "manual"
            safe_for_writable_dependency = True
            summary = "Workspace root is the current manual source of truth."
            next_action = "Use manual launch or configure NAS sync before cross-device work."
        return {
            "schema": "fluxio.workspace_sync_authority.v1",
            "workspaceId": workspace.workspace_id,
            "state": state,
            "authority": authority,
            "launchSafety": launch_safety,
            "safeForWritableDependency": safe_for_writable_dependency,
            "summary": summary,
            "nextAction": next_action,
            "localProjectPath": local_path,
            "nasProjectPath": nas_path,
            "currentRootPath": current_root,
            "syncMode": workspace.sync_mode,
            "requestedDirection": workspace.sync_direction,
            "effectiveDirection": effective_direction,
            "conflictPolicy": workspace.sync_conflict_policy,
            "autoSyncToNas": bool(workspace.auto_sync_to_nas),
            "receiptId": receipt_id,
            "conflictCount": conflict_count,
            "manualReviewRequired": manual_review,
        }

    @staticmethod
    def _cross_device_launch_rehearsal(
        *,
        workspace: WorkspaceProfile,
        schedule: dict[str, object],
        sync_authority: dict[str, object],
    ) -> dict[str, object]:
        launch_recommendation = build_launch_runtime_recommendation(
            objective="",
            workspace_default_runtime=workspace.default_runtime,
            profile=workspace.user_profile or "builder",
        )
        schedule_safe = bool(schedule.get("safeToLaunch"))
        sync_safe = bool(sync_authority.get("safeForWritableDependency"))
        runtime = str(launch_recommendation.get("runtime") or workspace.default_runtime or "hermes")
        query = urlencode(
            {
                "launch": "mission",
                "workspaceId": workspace.workspace_id,
                "runtime": runtime,
                "profile": workspace.user_profile or "builder",
                "mode": "Autopilot",
                "syncAuthority": str(sync_authority.get("authority") or "manual"),
            }
        )
        checklist = [
            {
                "id": "sync_authority",
                "label": "Sync authority",
                "status": "pass" if sync_safe else "review",
                "detail": str(sync_authority.get("summary") or ""),
            },
            {
                "id": "dependency_schedule",
                "label": "Dependency schedule",
                "status": "pass" if schedule_safe else "review",
                "detail": str(schedule.get("recommendedAction") or ""),
            },
            {
                "id": "runtime_route",
                "label": "Runtime route",
                "status": "pass",
                "detail": (
                    f"{runtime_label(runtime)} via "
                    f"{launch_recommendation.get('modelProvider', '')}/"
                    f"{launch_recommendation.get('model', '')}"
                ).strip("/"),
            },
        ]
        blocked_items = [item for item in checklist if item["status"] != "pass"]
        status = "ready" if not blocked_items else "review_required"
        safe_workspace_id = str(workspace.workspace_id).replace('"', '\\"')
        return {
            "schema": "fluxio.cross_device_launch_rehearsal.v1",
            "workspaceId": workspace.workspace_id,
            "status": status,
            "safeToLaunch": status == "ready",
            "checklist": checklist,
            "blockedCheckIds": [item["id"] for item in blocked_items],
            "runtimeRecommendation": launch_recommendation,
            "recommendedRuntime": runtime,
            "urlPath": f"/control?{query}",
            "cliCommand": (
                'python -m grant_agent.cli mission-quickstart --root . '
                f'--workspace-id "{safe_workspace_id}" --runtime auto '
                '--objective "Describe the mission goal" --budget-hours 4'
            ),
            "nextAction": (
                "Launch rehearsal is ready; open the mission launcher with this workspace, sync authority, and runtime route."
                if status == "ready"
                else "Resolve the review items before launching cross-device dependent work."
            ),
        }

    @staticmethod
    def _project_schedule_recommendation(
        *,
        workspace: WorkspaceProfile,
        rows: list[Mission],
        active: list[Mission],
        queued: list[Mission],
        blocked: list[Mission],
        completed: list[Mission],
        workspaces: list[WorkspaceProfile],
        workspace_missions: dict[str, list[Mission]],
        workspace_by_id: dict[str, WorkspaceProfile],
    ) -> dict:
        related_active = []
        related_blocked = []
        dependency_active = []
        dependency_blocked = []
        downstream_active = []
        dependency_ids = ControlRoomStore._workspace_dependency_ids(workspace)
        workspace_root = str(Path(workspace.root_path).expanduser().resolve()) if workspace.root_path else ""
        for other_workspace in workspaces:
            if other_workspace.workspace_id == workspace.workspace_id:
                continue
            other_root = str(Path(other_workspace.root_path).expanduser().resolve()) if other_workspace.root_path else ""
            same_root = bool(workspace_root and other_root and workspace_root == other_root)
            upstream_dependency = other_workspace.workspace_id in dependency_ids
            downstream_dependency = workspace.workspace_id in ControlRoomStore._workspace_dependency_ids(other_workspace)
            if not same_root and not upstream_dependency and not downstream_dependency:
                continue
            other_rows = workspace_missions.get(other_workspace.workspace_id, [])
            other_active = [
                mission
                for mission in other_rows
                if mission.state.status not in TERMINAL_MISSION_STATUSES
                and mission.state.status != "draft"
            ]
            other_blocked = [
                mission
                for mission in other_active
                if mission.state.status in {"blocked", "needs_approval", "verification_failed"}
                or mission.proof.pending_approvals
                or mission.proof.failed_checks
                or mission.state.verification_failures
            ]
            if other_active:
                relation = (
                    "upstream_dependency"
                    if upstream_dependency
                    else "downstream_dependency"
                    if downstream_dependency
                    else "same_root"
                )
                related_active.append(
                    {
                        "workspaceId": other_workspace.workspace_id,
                        "workspaceName": other_workspace.name,
                        "activeMissionCount": len(other_active),
                        "missionIds": [mission.mission_id for mission in other_active[:4]],
                        "relation": relation,
                    }
                )
                if upstream_dependency:
                    dependency_active.append(related_active[-1])
                if downstream_dependency:
                    downstream_active.append(related_active[-1])
            if other_blocked:
                relation = (
                    "upstream_dependency"
                    if upstream_dependency
                    else "downstream_dependency"
                    if downstream_dependency
                    else "same_root"
                )
                related_blocked.append(
                    {
                        "workspaceId": other_workspace.workspace_id,
                        "workspaceName": other_workspace.name,
                        "blockedMissionCount": len(other_blocked),
                        "missionIds": [mission.mission_id for mission in other_blocked[:4]],
                        "relation": relation,
                    }
                )
                if upstream_dependency:
                    dependency_blocked.append(related_blocked[-1])
        if blocked:
            state = "repair"
            priority = 100
            recommended_action = "Repair blocked mission before launching more project work."
            target_mission = blocked[0]
        elif dependency_blocked:
            state = "dependency_blocked"
            priority = 92
            recommended_action = "Unblock the upstream dependency workspace before launching this project."
            target_mission = None
        elif queued:
            state = "resume_queue"
            priority = 84
            recommended_action = "Resume or parallelize the front queued mission when the workspace slot clears."
            target_mission = queued[0]
        elif dependency_active and not active:
            state = "dependency_wait"
            priority = 74
            recommended_action = "Wait for the upstream dependency workspace to finish or schedule a read-only follow-up."
            target_mission = None
        elif active:
            state = "watch"
            priority = 68
            recommended_action = "Let the active mission continue; avoid overlapping edits unless scope is disjoint."
            target_mission = active[0]
        elif not rows:
            state = "launch_first"
            priority = 62
            recommended_action = "Launch the first mission for this project from Builder."
            target_mission = None
        elif completed:
            state = "plan_next"
            priority = 55
            recommended_action = "Open the latest proof digest, then schedule the next dependency-aware mission."
            target_mission = completed[0]
        else:
            state = "review"
            priority = 45
            recommended_action = "Review recent project history before scheduling the next mission."
            target_mission = rows[0] if rows else None
        dependency_warnings = []
        same_root_blocked = [item for item in related_blocked if item.get("relation") == "same_root"]
        same_root_active = [item for item in related_active if item.get("relation") == "same_root"]
        if same_root_blocked:
            dependency_warnings.append("Related workspace has blocked active work on the same root.")
            priority = max(priority, 90)
        if dependency_blocked:
            dependency_warnings.append("Upstream dependency workspace is blocked.")
            priority = max(priority, 92)
        if dependency_active and not active:
            dependency_warnings.append("Upstream dependency workspace has active work.")
        if same_root_active and not active:
            dependency_warnings.append("Related workspace already has active work on the same root.")
        return {
            "schema": "fluxio.project_schedule_recommendation.v1",
            "workspaceId": workspace.workspace_id,
            "workspaceName": workspace.name,
            "state": state,
            "priorityScore": priority,
            "recommendedAction": recommended_action,
            "targetMissionId": target_mission.mission_id if target_mission else "",
            "targetMissionTitle": (target_mission.title or target_mission.objective) if target_mission else "",
            "runtime": workspace.default_runtime,
            "sameRootActiveWorkspaces": related_active,
            "sameRootBlockedWorkspaces": related_blocked,
            "dependencyActiveWorkspaces": dependency_active,
            "dependencyBlockedWorkspaces": dependency_blocked,
            "downstreamActiveWorkspaces": downstream_active,
            "declaredDependencyIds": sorted(dependency_ids),
            "dependencyWarnings": dependency_warnings,
            "safeToLaunch": state in {"launch_first", "plan_next"} and not related_blocked and not dependency_blocked,
            "launchMode": "new_mission" if state in {"launch_first", "plan_next"} and not dependency_blocked else "hold_or_repair",
            "reason": (
                f"{len(active)} active, {len(queued)} queued, {len(blocked)} blocked, "
                f"{len(completed)} completed mission(s); {len(related_active)} related active workspace(s); "
                f"{len(dependency_active)} upstream active dependency workspace(s)."
            ),
        }

    @staticmethod
    def _overnight_progress_digest_payload(
        *,
        missions: list[Mission],
        recent_missions: list[Mission],
        workspaces: list[WorkspaceProfile],
        activity: list[dict],
        notifications: list[dict],
        telegram_destination: str,
        delivery_receipts: list[dict] | None = None,
    ) -> dict:
        delivery_receipts = list(delivery_receipts or [])
        active = [
            item
            for item in missions
            if item.state.status not in TERMINAL_MISSION_STATUSES
            and item.state.status != "draft"
        ]
        queued = [item for item in active if item.state.queue_position > 0]
        blocked = [
            item
            for item in active
            if item.state.status in {"blocked", "needs_approval", "verification_failed"}
            or item.proof.pending_approvals
            or item.proof.failed_checks
        ]
        running = [
            item
            for item in active
            if item.state.status in {"running", "queued"}
            and item.state.queue_position == 0
            and item not in blocked
        ]
        completed_recent = [
            item for item in recent_missions if item.state.status == "completed"
        ]
        latest = recent_missions[0] if recent_missions else None
        action_notifications = [
            item for item in notifications if item.get("severity") == "action"
        ]
        success_notifications = [
            item for item in notifications if item.get("severity") == "success"
        ]
        latest_activity = activity[0] if activity else {}
        if blocked:
            severity = "action"
            headline = f"{len(blocked)} mission(s) need attention"
            next_action = "Open the phone progress view and resolve the first approval, blocker, or failed check."
        elif running:
            severity = "progress"
            headline = f"{len(running)} mission(s) can continue hands-free"
            next_action = "Keep the phone progress view open or let browser/Telegram notifications carry overnight updates."
        elif completed_recent:
            severity = "success"
            headline = f"{len(completed_recent)} recent mission(s) completed"
            next_action = "Review proof digests and launch the next mission batch."
        else:
            severity = "idle"
            headline = "No active overnight mission is running"
            next_action = "Launch a mission batch before going offline."
        channels = ["in_app_stack", "browser_notification"]
        if telegram_destination:
            channels.append("telegram")
        digest_id = (
            f"overnight:{severity}:{len(active)}:{len(blocked)}:"
            f"{latest.mission_id if latest else 'none'}:{latest.updated_at if latest else ''}"
        )
        focus_items = []
        for mission in (blocked + running + completed_recent)[:5]:
            focus_items.append(
                {
                    "missionId": mission.mission_id,
                    "title": mission.title or mission.objective,
                    "status": mission.state.status,
                    "runtime": mission.runtime_id,
                    "summary": (
                        mission.state.last_runtime_event
                        or mission.proof.summary
                        or mission.objective
                    )[:260],
                    "nextAction": ControlRoomStore._next_mission_detail_action(mission),
                    "updatedAt": mission.updated_at,
                }
            )
        notification = {
            "id": digest_id,
            "kind": "overnight_progress_digest",
            "severity": severity if severity != "progress" else "info",
            "status": severity,
            "title": headline,
            "detail": next_action,
            "createdAt": utc_now_iso(),
        }
        receipt_status_counts: dict[str, int] = {}
        for receipt in delivery_receipts:
            status = str(receipt.get("status") or "unknown")
            receipt_status_counts[status] = receipt_status_counts.get(status, 0) + 1
        return {
            "schema": "fluxio.overnight_progress_digest.v1",
            "digestId": digest_id,
            "generatedAt": utc_now_iso(),
            "headline": headline,
            "severity": severity,
            "nextAction": next_action,
            "phoneSummary": (
                f"{len(active)} active · {len(blocked)} need attention · "
                f"{len(queued)} queued · {len(completed_recent)} recently completed"
            ),
            "counts": {
                "workspaces": len(workspaces),
                "missions": len(missions),
                "active": len(active),
                "running": len(running),
                "queued": len(queued),
                "blocked": len(blocked),
                "completedRecent": len(completed_recent),
                "actionNotifications": len(action_notifications),
                "successNotifications": len(success_notifications),
            },
            "delivery": {
                "channels": channels,
                "browserNotificationReady": True,
                "telegramReady": bool(telegram_destination),
                "telegramDestinationConfigured": bool(telegram_destination),
                "receiptBacked": True,
                "receiptCount": len(delivery_receipts),
                "receiptStatusCounts": receipt_status_counts,
                "latestReceipts": delivery_receipts[-5:],
                "recommendedRefreshSeconds": 30 if active else 90,
                "phoneSurface": "control-room-summary",
                "appLike": True,
            },
            "focusItems": focus_items,
            "latestActivity": {
                "kind": latest_activity.get("kind", ""),
                "message": str(latest_activity.get("message", ""))[:260],
                "timestamp": latest_activity.get("timestamp", ""),
            },
            "notification": notification,
        }

    @staticmethod
    def _mission_launch_shortcut_payload(workspace: WorkspaceProfile) -> dict:
        launch_recommendation = build_launch_runtime_recommendation(
            objective="",
            workspace_default_runtime=workspace.default_runtime,
            profile=workspace.user_profile or "builder",
        )
        query = urlencode(
            {
                "launch": "mission",
                "workspaceId": workspace.workspace_id,
                "runtime": launch_recommendation["runtime"],
                "profile": workspace.user_profile or "builder",
                "mode": "Autopilot",
            }
        )
        safe_workspace_id = str(workspace.workspace_id).replace('"', '\\"')
        return {
            "workspaceId": workspace.workspace_id,
            "workspaceName": workspace.name,
            "runtime": workspace.default_runtime,
            "recommendedRuntime": launch_recommendation["runtime"],
            "runtimeRecommendation": launch_recommendation,
            "profile": workspace.user_profile or "builder",
            "urlPath": f"/control?{query}",
            "cliCommand": (
                'python -m grant_agent.cli mission-quickstart --root . '
                f'--workspace-id "{safe_workspace_id}" --runtime auto '
                '--objective "Describe the mission goal" --budget-hours 4'
            ),
            "summary": "Copy this URL or command to reopen the mission launcher with project defaults.",
        }

    def build_mission_detail_snapshot(self, mission_id: str, *, event_limit: int = 80) -> dict:
        started = time.perf_counter()
        section_started = started
        section_durations: list[dict[str, float | str]] = []

        def mark_section(name: str) -> None:
            nonlocal section_started
            now = time.perf_counter()
            section_durations.append(
                {"name": name, "durationMs": round((now - section_started) * 1000, 2)}
            )
            section_started = now

        all_missions = self.load_missions()
        mission = next((item for item in all_missions if item.mission_id == mission_id), None)
        if mission is None:
            raise ValueError(f"Unknown mission id: {mission_id}")
        self.attach_lane_control_receipts(mission)
        workspaces = self.load_workspaces()
        workspace_by_id = {item.workspace_id: item for item in workspaces}
        workspace = workspace_by_id.get(mission.workspace_id)
        workspace_missions: dict[str, list[Mission]] = {}
        for item in all_missions:
            workspace_missions.setdefault(item.workspace_id, []).append(item)
        mark_section("base_store_load")
        events = [
            event
            for event in self.recent_events(limit=max(event_limit * 4, event_limit))
            if str(event.get("mission_id") or event.get("missionId") or "") == mission.mission_id
        ][:event_limit]
        mark_section("events")
        runtime_transcript = self._mission_runtime_transcript_payload(
            mission,
            events=events,
            root=self.root,
            workspace=workspace,
        )
        mark_section("runtime_transcript")
        planned_scope_artifacts = build_planned_scope_artifacts(
            root=self.root,
            mission=mission,
            workspace=workspace,
        )
        mark_section("planned_scope_artifacts")
        mission_summary = self._mission_summary_payload(
            mission,
            root=self.root,
            workspace=workspace,
            planned_scope_artifacts=planned_scope_artifacts,
        )
        mark_section("mission_summary")
        bounded_mission = self._bounded_mission_detail_payload(
            mission,
            root=self.root,
            workspace=workspace,
            planned_scope_artifacts=planned_scope_artifacts,
        )
        mark_section("bounded_mission")
        agent_messages = self._mission_agent_messages_payload(
            mission,
            events=events,
            runtime_transcript=runtime_transcript,
        )
        mark_section("agent_messages")
        proof_digest = self._mission_proof_digest_payload(mission, workspace=workspace)
        mark_section("proof_digest")
        context_roots = self._mission_context_roots_payload(
            mission,
            workspace=workspace,
            workspaces=workspaces,
            workspace_missions=workspace_missions,
        )
        mark_section("context_roots")
        payload = {
            "schema": "fluxio.control_room.mission_detail.v1",
            "workspaceRoot": str(self.root),
            "generatedAt": utc_now_iso(),
            "missionId": mission.mission_id,
            "workspace": asdict(workspace) if workspace else {},
            "summary": mission_summary,
            "mission": bounded_mission,
            "events": events,
            "proof": asdict(mission.proof),
            "state": asdict(mission.state),
            "delegatedRuntimeSessions": [
                asdict(item) for item in mission.delegated_runtime_sessions
            ],
            "runtimeTranscript": runtime_transcript,
            "routeConfigs": [
                asdict(item) if is_dataclass(item) else dict(item)
                for item in mission.route_configs
                if is_dataclass(item) or isinstance(item, dict)
            ],
            "executionScope": asdict(mission.execution_scope),
            "verificationCommands": list(mission.verification_policy.commands),
            "successChecks": list(mission.success_checks),
            "agentMessages": agent_messages,
            "proofDigest": proof_digest,
            "contextRoots": context_roots,
            "nextAction": self._next_mission_detail_action(mission),
            "performance": {
                "source": "control_room_mission_detail",
                "durationMs": round((time.perf_counter() - started) * 1000, 2),
                "sectionDurations": section_durations,
                "slowestSections": sorted(
                    section_durations,
                    key=lambda item: float(item.get("durationMs") or 0),
                    reverse=True,
                )[:5],
                "eventLimit": event_limit,
                "virtualization": {
                    "lazyMissionDetail": True,
                    "boundedEvents": event_limit,
                    "boundedActionHistory": 60,
                    "boundedPlanRevisions": 12,
                    "boundedDerivedTasks": 80,
                    "boundedDelegatedSessionEvents": 20,
                    "proofDigestInsteadOfFullScan": True,
                },
            },
        }
        payload["performance"]["payloadBytes"] = len(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )
        payload["performance"]["budget"] = self._performance_budget_payload(
            source="control_room_mission_detail",
            duration_ms=payload["performance"]["durationMs"],
            payload_bytes=payload["performance"]["payloadBytes"],
            duration_budget_ms=CONTROL_ROOM_DETAIL_DURATION_BUDGET_MS,
            payload_budget_bytes=CONTROL_ROOM_DETAIL_PAYLOAD_BUDGET_BYTES,
            item_limits={
                "events": event_limit,
                "action_history": 60,
                "plan_revisions": 12,
                "derived_tasks": 80,
                "improvement_queue": 80,
                "routing_decisions": 40,
                "skill_usage": 80,
                "learned_skill_events": 80,
                "delegated_session_events": 20,
            },
        )
        return payload

    @staticmethod
    def _path_identity(value: str) -> str:
        normalized = str(value or "").strip().replace("\\", "/")
        while "//" in normalized:
            normalized = normalized.replace("//", "/")
        return normalized.rstrip("/").lower()

    @staticmethod
    def _folder_label(value: str) -> str:
        normalized = str(value or "").strip().replace("\\", "/").rstrip("/")
        if not normalized:
            return "root"
        return normalized.split("/")[-1] or normalized

    @staticmethod
    def _mission_context_roots_payload(
        mission: Mission,
        *,
        workspace: WorkspaceProfile | None,
        workspaces: list[WorkspaceProfile],
        workspace_missions: dict[str, list[Mission]],
    ) -> dict:
        roots: list[dict] = []
        seen: set[str] = set()

        def workspace_counts(workspace_id: str) -> dict[str, int]:
            rows = workspace_missions.get(workspace_id, [])
            active = [
                item
                for item in rows
                if item.state.status not in TERMINAL_MISSION_STATUSES
                and item.state.status != "draft"
            ]
            blocked = [
                item
                for item in active
                if item.state.status in {"blocked", "needs_approval", "verification_failed"}
                or item.proof.pending_approvals
                or item.proof.failed_checks
            ]
            return {
                "missions": len(rows),
                "active": len(active),
                "blocked": len(blocked),
                "completed": sum(1 for item in rows if item.state.status == "completed"),
            }

        def add_root(
            *,
            role: str,
            relationship: str,
            root_path: str,
            source_workspace: WorkspaceProfile | None,
            current: bool = False,
            writable: bool = True,
            detail: str = "",
        ) -> None:
            clean_path = str(root_path or "").strip()
            if not clean_path:
                return
            source_id = source_workspace.workspace_id if source_workspace else mission.workspace_id
            identity = f"{source_id}|{role}|{ControlRoomStore._path_identity(clean_path)}"
            if identity in seen:
                return
            seen.add(identity)
            counts = workspace_counts(source_id)
            roots.append(
                {
                    "rootId": f"{source_id}:{role}:{len(roots) + 1}",
                    "workspaceId": source_id,
                    "workspaceName": source_workspace.name if source_workspace else "",
                    "role": role,
                    "relationship": relationship,
                    "rootPath": clean_path,
                    "folderLabel": ControlRoomStore._folder_label(clean_path),
                    "runtime": source_workspace.default_runtime if source_workspace else mission.runtime_id,
                    "profile": source_workspace.user_profile if source_workspace else mission.selected_profile,
                    "harness": source_workspace.preferred_harness if source_workspace else mission.harness_id,
                    "syncMode": source_workspace.sync_mode if source_workspace else "mission",
                    "syncDirection": source_workspace.sync_direction if source_workspace else "bidirectional",
                    "autoSyncToNas": bool(source_workspace.auto_sync_to_nas) if source_workspace else False,
                    "localProjectPath": source_workspace.local_project_path if source_workspace else "",
                    "nasProjectPath": source_workspace.nas_project_path if source_workspace else "",
                    "missionCount": counts["missions"],
                    "activeMissionCount": counts["active"],
                    "blockedMissionCount": counts["blocked"],
                    "completedMissionCount": counts["completed"],
                    "currentMission": current,
                    "writableByMission": writable,
                    "detail": detail,
                }
            )

        add_root(
            role="primary",
            relationship="mission_workspace",
            root_path=workspace.root_path if workspace else mission.execution_scope.workspace_root,
            source_workspace=workspace,
            current=True,
            detail="Primary mission workspace.",
        )

        for role, root_path, detail in (
            ("execution", mission.execution_scope.execution_root, "Resolved execution root for the current run."),
            ("workspace_scope", mission.execution_scope.workspace_root, "Execution scope workspace root."),
            (
                "state_scope",
                str(mission.state.execution_scope.get("execution_root") or ""),
                "Runtime-reported execution root.",
            ),
            (
                "worktree",
                mission.execution_scope.worktree_path,
                "Isolated worktree root for this mission.",
            ),
        ):
            add_root(
                role=role,
                relationship="mission_execution_scope",
                root_path=root_path,
                source_workspace=workspace,
                current=role in {"execution", "worktree"},
                detail=detail,
            )

        if workspace:
            add_root(
                role="local_mirror",
                relationship="workspace_sync_pair",
                root_path=workspace.local_project_path,
                source_workspace=workspace,
                writable=workspace.sync_direction in {"bidirectional", "local_to_nas"},
                detail="Local project mirror configured for this workspace.",
            )
            add_root(
                role="nas_mirror",
                relationship="workspace_sync_pair",
                root_path=workspace.nas_project_path,
                source_workspace=workspace,
                writable=workspace.sync_direction in {"bidirectional", "nas_to_local"},
                detail="NAS project mirror configured for this workspace.",
            )

        related_workspaces = [
            item
            for item in workspaces
            if item.workspace_id != mission.workspace_id and item.enabled
        ]
        related_workspaces.sort(
            key=lambda item: (
                -len(workspace_missions.get(item.workspace_id, [])),
                item.name.lower(),
            )
        )
        for related in related_workspaces[:6]:
            add_root(
                role="related_workspace",
                relationship="same_control_room",
                root_path=related.root_path,
                source_workspace=related,
                writable=False,
                detail="Visible sibling project for cross-project planning and dependency review.",
            )

        roots = roots[:10]
        related_roots = [item for item in roots if item["role"] == "related_workspace"]
        writable_roots = [item for item in roots if item["writableByMission"]]
        sync_pairs = [item for item in roots if item["relationship"] == "workspace_sync_pair"]
        dependency_edges = ControlRoomStore._mission_context_dependency_edges(
            roots=roots,
            primary_root=roots[0] if roots else {},
        )
        write_preflight = ControlRoomStore._mission_context_write_preflight(
            roots=roots,
            dependency_edges=dependency_edges,
            mission=mission,
        )
        return {
            "schema": "fluxio.mission.context_roots.v1",
            "missionId": mission.mission_id,
            "workspaceId": mission.workspace_id,
            "mode": "multi_root" if len(roots) > 1 else "single_root",
            "primary": roots[0] if roots else {},
            "roots": roots,
            "related": related_roots,
            "dependencyEdges": dependency_edges,
            "writeScopePreflight": write_preflight,
            "counts": {
                "totalRoots": len(roots),
                "relatedWorkspaces": len(related_roots),
                "writableRoots": len(writable_roots),
                "syncPairs": len(sync_pairs),
                "dependencyEdges": len(dependency_edges),
                "preflightWarnings": len(write_preflight.get("warnings", [])),
            },
            "execution": {
                "target": mission.execution_scope.execution_target,
                "storageMode": mission.execution_scope.storage_mode,
                "hostLocality": mission.execution_scope.host_locality,
                "branchName": mission.execution_scope.branch_name,
                "detail": mission.execution_scope.detail,
            },
            "policy": {
                "writeScope": "primary_and_declared_mirrors",
                "relatedWorkspaceWritePolicy": "read_only_until_selected",
                "beginnerSafety": "Show every root before cross-project edits.",
            },
            "recommendedAction": (
                "Resolve write-scope warnings before cross-project edits."
                if write_preflight.get("warnings")
                else
                "Review related roots before planning cross-project edits."
                if related_roots
                else "Add related workspaces when this mission depends on another project."
            ),
        }

    @staticmethod
    def _mission_context_dependency_edges(
        *,
        roots: list[dict],
        primary_root: dict,
    ) -> list[dict]:
        primary_id = str(primary_root.get("rootId") or "")
        if not primary_id:
            return []
        edges: list[dict] = []
        for root in roots:
            root_id = str(root.get("rootId") or "")
            if not root_id or root_id == primary_id:
                continue
            relationship = str(root.get("relationship") or "")
            role = str(root.get("role") or "")
            if relationship == "workspace_sync_pair":
                edge_type = "sync_mirror"
                direction = str(root.get("syncDirection") or "bidirectional")
                write_policy = (
                    "writable_when_direction_allows"
                    if root.get("writableByMission")
                    else "read_only_for_this_direction"
                )
            elif role == "related_workspace":
                edge_type = "related_project"
                direction = "read_only"
                write_policy = "read_only_until_selected"
            else:
                edge_type = "execution_scope"
                direction = "mission_internal"
                write_policy = "writable" if root.get("writableByMission") else "read_only"
            edges.append(
                {
                    "edgeId": f"{primary_id}->{root_id}",
                    "fromRootId": primary_id,
                    "toRootId": root_id,
                    "type": edge_type,
                    "direction": direction,
                    "writePolicy": write_policy,
                    "summary": (
                        f"{ControlRoomStore._folder_label(str(primary_root.get('rootPath') or ''))}"
                        f" -> {ControlRoomStore._folder_label(str(root.get('rootPath') or ''))}"
                    ),
                }
            )
        return edges[:12]

    @staticmethod
    def _mission_context_write_preflight(
        *,
        roots: list[dict],
        dependency_edges: list[dict],
        mission: Mission,
    ) -> dict:
        writable_roots = [item for item in roots if item.get("writableByMission")]
        read_only_related = [
            item
            for item in roots
            if item.get("role") == "related_workspace" and not item.get("writableByMission")
        ]
        warnings: list[str] = []
        write_policy = str(
            getattr(mission.execution_policy, "write_policy", "")
            or getattr(mission.execution_policy, "approval_mode", "")
            or "tiered"
        )
        if read_only_related and write_policy != "read_only":
            warnings.append("Related projects are visible for planning but stay read-only until selected.")
        if len(writable_roots) > 1 and not dependency_edges:
            warnings.append("Multiple writable roots exist without explicit dependency edges.")
        return {
            "schema": "fluxio.write_scope_preflight.v1",
            "status": "warn" if warnings else "pass",
            "writePolicy": write_policy,
            "allowedRootIds": [str(item.get("rootId") or "") for item in writable_roots],
            "readOnlyRootIds": [
                str(item.get("rootId") or "")
                for item in roots
                if not item.get("writableByMission")
            ],
            "dependencyEdgeCount": len(dependency_edges),
            "warnings": warnings,
            "nextAction": (
                "Keep related roots read-only or explicitly select them before cross-project edits."
                if warnings
                else "Write scope is bounded to the primary root and declared sync mirrors."
            ),
        }

    @staticmethod
    def _performance_budget_payload(
        *,
        source: str,
        duration_ms: float,
        payload_bytes: int,
        duration_budget_ms: int,
        payload_budget_bytes: int,
        item_limits: dict[str, int],
    ) -> dict:
        duration_within_budget = duration_ms <= duration_budget_ms
        payload_within_budget = payload_bytes <= payload_budget_bytes
        if duration_within_budget and payload_within_budget:
            status = "pass"
            recommended_action = "Keep this endpoint in the warm-tab refresh path."
        elif not payload_within_budget:
            status = "warn"
            recommended_action = "Page or virtualize the largest lists before increasing refresh frequency."
        else:
            status = "warn"
            recommended_action = "Profile the endpoint before using it for instant mission switching."
        return {
            "schema": "fluxio.performance_budget.v1",
            "source": source,
            "status": status,
            "durationBudgetMs": duration_budget_ms,
            "payloadBudgetBytes": payload_budget_bytes,
            "measuredDurationMs": duration_ms,
            "measuredPayloadBytes": payload_bytes,
            "durationWithinBudget": duration_within_budget,
            "payloadWithinBudget": payload_within_budget,
            "durationOverBudgetMs": round(max(0.0, duration_ms - duration_budget_ms), 2),
            "payloadOverBudgetBytes": max(0, int(payload_bytes) - int(payload_budget_bytes)),
            "itemLimits": dict(item_limits),
            "recommendedAction": recommended_action,
        }

    @staticmethod
    def _mission_proof_digest_payload(
        mission: Mission,
        *,
        workspace: WorkspaceProfile | None = None,
    ) -> dict:
        latest_session = (
            mission.delegated_runtime_sessions[-1]
            if mission.delegated_runtime_sessions
            else None
        )
        latest_session_payload = asdict(latest_session) if latest_session else {}
        passed_checks = list(mission.proof.passed_checks)
        failed_checks = list(mission.proof.failed_checks)
        pending_approvals = list(mission.proof.pending_approvals)
        changed_files = list(mission.proof.changed_files)
        artifacts = list(getattr(mission.proof, "artifacts", []) or [])
        skill_feedback = [
            item
            for item in mission.learned_skill_events[-80:]
            if isinstance(item, dict)
            and str(item.get("kind") or item.get("event") or "") == "skill.slice_feedback"
        ][-8:]
        checks_total = max(1, len(passed_checks) + len(failed_checks) + len(pending_approvals))
        proof_score = round(
            max(
                0,
                min(
                    100,
                    (len(passed_checks) / checks_total) * 72
                    + (18 if changed_files or artifacts else 0)
                    + (10 if latest_session_payload.get("status") in {"completed", "running"} else 0)
                    - len(failed_checks) * 18
                    - len(pending_approvals) * 10,
                ),
            )
        )
        preview_url = (
            getattr(mission.state, "last_preview_url", "")
            or getattr(mission.state, "preview_url", "")
            or ""
        )
        preview_source = (
            "served_live_preview"
            if preview_url
            else "fixture_or_evidence_timeline"
        )
        verification_state = (
            "blocked"
            if failed_checks
            else "waiting_for_approval"
            if pending_approvals
            else "passed"
            if passed_checks
            else "not_recorded"
        )
        return {
            "schema": "fluxio.mission.proof_digest.v1",
            "missionId": mission.mission_id,
            "workspaceId": mission.workspace_id,
            "workspaceName": workspace.name if workspace else "",
            "status": mission.state.status,
            "plannerLoopStatus": mission.state.planner_loop_status,
            "proofScore": proof_score,
            "verificationState": verification_state,
            "previewSource": preview_source,
            "previewUrl": preview_url,
            "summary": mission.proof.summary or "No proof summary captured yet.",
            "counts": {
                "passedChecks": len(passed_checks),
                "failedChecks": len(failed_checks),
                "pendingApprovals": len(pending_approvals),
                "changedFiles": len(changed_files),
                "artifacts": len(artifacts),
                "delegatedSessions": len(mission.delegated_runtime_sessions),
                "skillFeedbackSlices": len(skill_feedback),
            },
            "latest": {
                "passedChecks": passed_checks[-5:],
                "failedChecks": failed_checks[-5:],
                "pendingApprovals": pending_approvals[-5:],
                "changedFiles": changed_files[-8:],
                "artifacts": artifacts[-5:],
                "skillFeedback": skill_feedback,
            },
            "delegatedRuntime": {
                "status": latest_session_payload.get("status", ""),
                "detail": latest_session_payload.get("detail", ""),
                "targetProvider": latest_session_payload.get("target_provider", ""),
                "targetModel": latest_session_payload.get("target_model", ""),
                "updatedAt": latest_session_payload.get("updated_at", ""),
                "lastEvent": latest_session_payload.get("last_event", ""),
            },
            "export": {
                "schema": "fluxio.mission.proof_digest_export.v1",
                "backendCommand": "export_mission_proof_digest_command",
                "formats": ["markdown", "json"],
                "defaultDirectory": ".agent_control/proof_digests",
                "shareActions": ["copy_path", "archive_artifact"],
            },
            "nextAction": ControlRoomStore._next_mission_detail_action(mission),
        }

    @staticmethod
    def _mission_activity_progress_payload(
        mission: Mission,
        *,
        active_runtime_lane_count: int,
    ) -> dict:
        status = str(mission.state.status or "").lower()
        action_count = len(list(mission.action_history or []))
        remaining_count = len(list(mission.state.remaining_steps or []))
        failure_count = len(list(mission.state.verification_failures or []))
        approval_count = len(list(mission.proof.pending_approvals or []))
        delegated_count = len(list(mission.delegated_runtime_sessions or []))
        skill_event_count = len(list(mission.learned_skill_events or []))
        completed_delegated_count = sum(
            1
            for session in mission.delegated_runtime_sessions or []
            if str(getattr(session, "status", "") or "").lower()
            in {"completed", "done", "succeeded"}
        )
        total_signals = (
            action_count
            + remaining_count
            + failure_count
            + approval_count
            + delegated_count
            + active_runtime_lane_count
            + skill_event_count
        )
        completed_signals = action_count + completed_delegated_count + skill_event_count
        value: int | None = None
        label = "Activity progress unavailable"
        if status in TERMINAL_MISSION_STATUSES:
            value = 100 if status == "completed" else None
            label = "Mission completed" if status == "completed" else "Terminal mission state"
        elif status == "queued":
            value = 4
            label = "Queued live state"
        elif failure_count > 0 or status in {"blocked", "verification_failed"}:
            value = max(8, min(92, round((completed_signals / max(1, total_signals)) * 100)))
            label = "Blocked activity progress"
        elif total_signals > 0:
            floor = 18 if active_runtime_lane_count > 0 or status == "running" else 8
            value = max(
                floor,
                min(
                    94,
                    round((completed_signals + active_runtime_lane_count) / max(1, total_signals) * 100),
                ),
            )
            label = "Live activity progress"
        elif status == "running":
            value = 12
            label = "Running live state"
        return {
            "schema": "fluxio.mission_live_progress.v1",
            "source": "mission_activity_signals",
            "label": label,
            "value": value,
            "signalCounts": {
                "actions": action_count,
                "remainingSteps": remaining_count,
                "verificationFailures": failure_count,
                "pendingApprovals": approval_count,
                "delegatedSessions": delegated_count,
                "activeRuntimeLanes": active_runtime_lane_count,
                "skillEvents": skill_event_count,
            },
            "nextAction": ControlRoomStore._next_mission_detail_action(mission),
        }

    @staticmethod
    def _mission_summary_payload(
        mission: Mission,
        *,
        root: Path | None = None,
        workspace: WorkspaceProfile | None = None,
        planned_scope_artifacts: dict | None = None,
    ) -> dict:
        sessions = mission.delegated_runtime_sessions or []
        latest_session = sessions[-1] if sessions else None
        latest_session_payload = asdict(latest_session) if latest_session else {}
        planned_scope_artifacts = (
            planned_scope_artifacts
            if isinstance(planned_scope_artifacts, dict)
            else (
                build_planned_scope_artifacts(root=root, mission=mission, workspace=workspace)
                if root is not None
                else {}
            )
        )
        elapsed_runtime_seconds = max(0, int(mission.state.elapsed_runtime_seconds or 0))
        remaining_runtime_seconds = max(0, int(mission.state.remaining_runtime_seconds or 0))
        max_runtime_seconds = max(0, int(mission.run_budget.max_runtime_seconds or 0))
        runtime_lanes = _runtime_lane_rows_for_mission(mission, latest_session)
        provider_capabilities = _provider_capability_contract_for_mission(
            mission,
            runtime_lanes=runtime_lanes,
        )
        active_runtime_lane_count = (
            len(runtime_lanes)
            if mission.state.status not in TERMINAL_MISSION_STATUSES
            and mission.state.status != "draft"
            else 0
        )
        if max_runtime_seconds <= 0 and elapsed_runtime_seconds + remaining_runtime_seconds > 0:
            max_runtime_seconds = elapsed_runtime_seconds + remaining_runtime_seconds
        runtime_progress_value = None
        runtime_progress_label = "Runtime progress unavailable"
        if mission.state.status == "completed":
            runtime_progress_value = 100
            runtime_progress_label = "Mission completed"
        elif mission.state.status in {"running", "queued", "blocked", "needs_approval", "verification_failed"} and max_runtime_seconds > 0:
            runtime_progress_value = max(
                0,
                min(
                    99 if mission.state.status != "completed" else 100,
                    round((elapsed_runtime_seconds / max(1, max_runtime_seconds)) * 100),
                ),
            )
            runtime_progress_label = "Budget window progress"
        activity_progress_payload = ControlRoomStore._mission_activity_progress_payload(
            mission,
            active_runtime_lane_count=active_runtime_lane_count,
        )
        if runtime_progress_value is None and activity_progress_payload.get("value") is not None:
            runtime_progress_value = activity_progress_payload.get("value")
            runtime_progress_label = activity_progress_payload.get("label") or runtime_progress_label
        progress_payload = {
            "schema": "fluxio.mission_live_progress.v1",
            "source": (
                "mission_state_runtime_budget"
                if max_runtime_seconds > 0 or mission.state.status == "completed"
                else activity_progress_payload.get("source", "mission_activity_signals")
            ),
            "label": runtime_progress_label,
            "value": runtime_progress_value,
            "elapsedSeconds": elapsed_runtime_seconds,
            "remainingSeconds": remaining_runtime_seconds,
            "maxRuntimeSeconds": max_runtime_seconds,
            "timeBudgetStatus": mission.state.time_budget_status,
            "signalCounts": activity_progress_payload.get("signalCounts", {}),
            "nextAction": ControlRoomStore._next_mission_detail_action(mission),
        }
        return {
            "mission_id": mission.mission_id,
            "workspace_id": mission.workspace_id,
            "title": mission.title,
            "objective": mission.objective[:260],
            "runtime_id": mission.runtime_id,
            "harness_id": mission.harness_id,
            "status": mission.state.status,
            "planner_loop_status": mission.state.planner_loop_status,
            "phase": mission.state.current_cycle_phase,
            "queue_position": mission.state.queue_position,
            "continuity_state": mission.state.continuity_state,
            "current_runtime_lane": mission.state.current_runtime_lane,
            "last_runtime_event": mission.state.last_runtime_event,
            "last_error": mission.state.last_error,
            "elapsedRuntimeSeconds": elapsed_runtime_seconds,
            "remainingRuntimeSeconds": remaining_runtime_seconds,
            "maxRuntimeSeconds": max_runtime_seconds,
            "timeBudgetStatus": mission.state.time_budget_status,
            "liveProgress": progress_payload,
            "updated_at": mission.updated_at,
            "created_at": mission.created_at,
            "proofSummary": mission.proof.summary,
            "passedChecks": len(mission.proof.passed_checks),
            "failedChecks": len(mission.proof.failed_checks),
            "pendingApprovals": len(mission.proof.pending_approvals),
            "blockedBy": list(mission.proof.blocked_by),
            "plannedScopeArtifacts": planned_scope_artifacts,
            "runtimeLanes": runtime_lanes,
            "providerTruth": dict(mission.state.provider_runtime_truth or {}),
            "providerCapabilities": provider_capabilities,
            "delegatedLaneCount": len(runtime_lanes),
            "activeDelegatedLaneCount": active_runtime_lane_count,
            "delegatedRuntime": {
                "status": latest_session_payload.get("status", ""),
                "detail": latest_session_payload.get("detail", ""),
                "targetProvider": latest_session_payload.get("target_provider", ""),
                "targetModel": latest_session_payload.get("target_model", ""),
                "heartbeatStatus": latest_session_payload.get("heartbeat_status", ""),
                "heartbeatAgeSeconds": latest_session_payload.get("heartbeat_age_seconds"),
            },
        }

    @staticmethod
    def _bounded_mission_detail_payload(
        mission: Mission,
        *,
        root: Path | None = None,
        workspace: WorkspaceProfile | None = None,
        planned_scope_artifacts: dict | None = None,
    ) -> dict:
        payload = asdict(mission)
        if root is not None:
            payload["plannedScopeArtifacts"] = (
                planned_scope_artifacts
                if isinstance(planned_scope_artifacts, dict)
                else build_planned_scope_artifacts(
                    root=root,
                    mission=mission,
                    workspace=workspace,
                )
            )
        payload["providerCapabilities"] = _provider_capability_contract_for_mission(mission)
        for key, limit in (
            ("action_history", 60),
            ("plan_revisions", 12),
            ("derived_tasks", 80),
            ("improvement_queue", 80),
            ("routing_decisions", 40),
            ("skill_usage", 80),
            ("learned_skill_events", 80),
        ):
            if isinstance(payload.get(key), list):
                payload[key] = payload[key][-limit:]
        for session in payload.get("delegated_runtime_sessions", []):
            if not isinstance(session, dict):
                continue
            if isinstance(session.get("latest_events"), list):
                session["latest_events"] = session["latest_events"][-20:]
            if isinstance(session.get("approval_history"), list):
                session["approval_history"] = session["approval_history"][-20:]
        return payload

    @staticmethod
    def _mission_runtime_transcript_payload(
        mission: Mission,
        *,
        events: list[dict],
        root: Path,
        workspace: WorkspaceProfile | None = None,
        limit: int = 10,
    ) -> dict:
        session_ids: list[str] = []

        def add_session_id(value: object) -> None:
            session_id = str(value or "").strip()
            if session_id and session_id not in session_ids:
                session_ids.append(session_id)

        add_session_id(mission.state.latest_session_id)
        for event in events:
            metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
            add_session_id(metadata.get("sessionId") or metadata.get("session_id"))
            add_session_id(event.get("sessionId") or event.get("session_id"))
        latest_session_id = str(mission.state.latest_session_id or "").strip()
        if latest_session_id:
            session_ids = [item for item in session_ids if item != latest_session_id]
            session_ids.append(latest_session_id)
        session_ids = session_ids[-8:]

        transcript_roots: list[Path] = []
        for candidate in (
            Path(str(workspace.root_path)) if workspace and workspace.root_path else None,
            Path(str(mission.execution_scope.execution_root)) if mission.execution_scope.execution_root else None,
            Path(str(mission.execution_scope.workspace_root)) if mission.execution_scope.workspace_root else None,
            root,
        ):
            if candidate is None:
                continue
            transcript_root = candidate / ".agent_runs"
            if str(transcript_root) not in {str(item) for item in transcript_roots}:
                transcript_roots.append(transcript_root)
        attached_messages: list[dict] = []
        attached_session_id = ""
        attached_source = ""
        missing_session_ids: list[str] = []
        for session_id in reversed(session_ids):
            session_dir = next(
                (
                    transcript_root / session_id
                    for transcript_root in transcript_roots
                    if (transcript_root / session_id).exists()
                ),
                None,
            )
            if session_dir is None:
                missing_session_ids.append(session_id)
                continue
            state_path = session_dir / "state.json"
            timeline_path = session_dir / "timeline.jsonl"
            attached_session_id = session_id
            attached_source = str(session_dir.parent)
            timeline_messages: list[dict] = []
            state_messages: list[dict] = []
            timeline_rows = _read_jsonl_tail(timeline_path, limit=limit)
            for index, row in enumerate(timeline_rows[-limit:]):
                if not isinstance(row, dict):
                    continue
                kind = str(row.get("kind") or "runtime.event").strip()
                message = str(row.get("message") or "").strip()
                if not message:
                    continue
                detail = _runtime_transcript_detail(row)
                timeline_messages.append(
                    {
                        "id": f"session-timeline:{session_id}:{row.get('timestamp') or index}:{kind}",
                        "sessionId": session_id,
                        "kind": kind,
                        "label": "Hermes session transcript",
                        "title": message[:320],
                        "detail": detail,
                        "technicalDetail": json.dumps(row.get("metadata", {}), ensure_ascii=False, indent=2)[:3000]
                        if isinstance(row.get("metadata"), dict) and row.get("metadata")
                        else "",
                        "createdAt": str(row.get("timestamp") or row.get("created_at") or ""),
                        "runtimeId": mission.runtime_id,
                        "tone": "bad" if any(token in kind.lower() for token in ("fail", "error", "block")) else "neutral",
                        "runtimeOutput": _runtime_transcript_has_concrete_output(row, detail),
                        "traceOnly": False,
                    }
                )
            state = {} if timeline_messages else _load_json_file(state_path)
            if isinstance(state, dict) and state:
                for key, label in (
                    ("decisions", "Hermes session decision"),
                    ("next_actions", "Hermes session next action"),
                    ("risks", "Hermes session risk"),
                    ("notes", "Hermes session note"),
                ):
                    for index, value in enumerate([item for item in state.get(key, []) if str(item or "").strip()][-3:]):
                        state_value = str(value)
                        if timeline_messages and key != "risks":
                            continue
                        if timeline_messages and _is_low_signal_session_state_value(state_value):
                            continue
                        state_messages.append(
                            {
                                "id": f"session-state:{session_id}:{key}:{index}",
                                "sessionId": session_id,
                                "kind": key,
                                "label": label,
                                "title": state_value[:320],
                                "detail": "",
                                "createdAt": str(state.get("updated_at") or state.get("generated_at") or ""),
                                "runtimeId": mission.runtime_id,
                                "tone": "warn" if key == "risks" else "neutral",
                                "runtimeOutput": False,
                                "traceOnly": bool(timeline_messages),
                            }
                        )
            if timeline_messages:
                concrete = [item for item in timeline_messages if item.get("runtimeOutput")]
                non_concrete = [item for item in timeline_messages if not item.get("runtimeOutput")]
                attached_messages = (concrete + non_concrete + state_messages)[-limit:]
            else:
                attached_messages = state_messages[-limit:]
            if attached_messages:
                break

        if attached_messages:
            return {
                "schema": "fluxio.runtime_transcript.v1",
                "status": "attached",
                "source": attached_source or ".agent_runs",
                "sessionId": attached_session_id,
                "candidateSessionIds": session_ids,
                "missingSessionIds": missing_session_ids,
                "messageCount": len(attached_messages),
                "messages": attached_messages[-limit:],
                "detail": f"Attached {len(attached_messages[-limit:])} live session transcript row(s) from {attached_session_id}.",
            }

        detail = (
            "No runtime session id has been recorded for this mission yet."
            if not session_ids
            else (
                "Mission references runtime session(s) "
                + ", ".join(session_ids[:4])
                + ", but no readable .agent_runs transcript directory exists for them. "
                "Only control-room bookkeeping is available until the runtime writes or restores that transcript."
            )
        )
        return {
            "schema": "fluxio.runtime_transcript.v1",
            "status": "missing_session_reference" if not session_ids else "missing_transcript",
            "source": " | ".join(str(path) for path in transcript_roots),
            "sessionId": "",
            "candidateSessionIds": session_ids,
            "missingSessionIds": missing_session_ids,
            "messageCount": 0,
            "messages": [],
            "detail": detail,
        }

    @staticmethod
    def _mission_agent_messages_payload(
        mission: Mission,
        *,
        events: list[dict],
        runtime_transcript: dict | None = None,
        limit: int = 80,
    ) -> list[dict]:
        messages: list[dict] = []

        def value(row: object, key: str, default: object = "") -> object:
            if isinstance(row, dict):
                return row.get(key, default)
            return getattr(row, key, default)

        def append(
            *,
            message_id: str,
            title: str,
            detail: str = "",
            technical_detail: str = "",
            created_at: str = "",
            role: str = "runtime",
            label: str = "Mission detail",
            runtime_id: str = "",
            tone: str = "neutral",
            process_message: bool = False,
            trace_only: bool = False,
            chips: list[str] | None = None,
        ) -> None:
            if not title and not detail:
                return
            messages.append(
                {
                    "id": message_id,
                    "role": role,
                    "label": label,
                    "runtimeId": runtime_id or mission.runtime_id,
                    "runtimeLabel": runtime_label(runtime_id or mission.runtime_id),
                    "title": str(title or detail)[:320],
                    "detail": str(detail or "")[:1200],
                    "technicalDetail": str(technical_detail or "")[:3000],
                    "createdAt": created_at,
                    "tone": tone,
                    "processMessage": process_message,
                    "traceOnly": trace_only,
                    "chatPreferred": not trace_only,
                    "chips": [str(item) for item in list(chips or []) if str(item or "").strip()][:4],
                }
            )

        runtime_transcript = runtime_transcript if isinstance(runtime_transcript, dict) else {}
        for item in runtime_transcript.get("messages", []) if isinstance(runtime_transcript.get("messages"), list) else []:
            if not isinstance(item, dict):
                continue
            append(
                message_id=str(item.get("id") or f"runtime-transcript:{mission.mission_id}:{len(messages)}"),
                title=str(item.get("title") or item.get("message") or "Runtime transcript event"),
                detail=str(item.get("detail") or ""),
                technical_detail=str(item.get("technicalDetail") or ""),
                created_at=str(item.get("createdAt") or item.get("created_at") or ""),
                role=str(item.get("role") or "runtime"),
                label=str(item.get("label") or "Hermes session transcript"),
                runtime_id=str(item.get("runtimeId") or mission.runtime_id),
                tone=str(item.get("tone") or "neutral"),
                process_message=True,
                trace_only=bool(item.get("traceOnly")),
                chips=[
                    str(item.get("sessionId") or ""),
                    str(item.get("kind") or ""),
                    "real transcript",
                ],
            )
        if runtime_transcript and runtime_transcript.get("status") != "attached":
            candidate_ids = [
                str(item)
                for item in runtime_transcript.get("candidateSessionIds", [])
                if str(item or "").strip()
            ]
            append(
                message_id=f"runtime-transcript-integrity:{mission.mission_id}:{mission.updated_at}",
                title="Hermes session transcript is not attached",
                detail=str(
                    runtime_transcript.get("detail")
                    or "The mission points at a runtime session, but no readable session transcript was found under .agent_runs."
                ),
                created_at=mission.updated_at or mission.created_at,
                role="runtime",
                label="Runtime transcript integrity",
                runtime_id=mission.runtime_id,
                tone="bad",
                process_message=True,
                trace_only=False,
                chips=["live data gap", *candidate_ids[:2]],
            )

        provider_truth = (
            mission.state.provider_runtime_truth
            if isinstance(mission.state.provider_runtime_truth, dict)
            else {}
        )
        active_route = (
            provider_truth.get("activeRoute")
            if isinstance(provider_truth.get("activeRoute"), dict)
            else {}
        )
        route_provider = str(active_route.get("provider") or "").strip()
        route_model = str(active_route.get("model") or "").strip()
        route_effort = str(active_route.get("effort") or "").strip()
        auth_known = bool(provider_truth.get("authKnown"))
        auth_present = bool(provider_truth.get("authPresent"))
        auth_mode = str(provider_truth.get("authMode") or "").strip()
        last_failure = (
            provider_truth.get("lastFailure")
            if isinstance(provider_truth.get("lastFailure"), dict)
            else {}
        )
        last_success = (
            provider_truth.get("lastSuccessfulCall")
            if isinstance(provider_truth.get("lastSuccessfulCall"), dict)
            else {}
        )
        if provider_truth or active_route:
            auth_detail = (
                "auth present"
                if auth_present
                else "auth not configured"
                if auth_known
                else "auth state unknown"
            )
            route_title = "Provider route is not authenticated" if auth_known and not auth_present else "Provider route truth"
            route_detail_parts = [
                f"Route: {route_provider or 'unknown'} / {route_model or 'unknown'}"
                + (f" / {route_effort}" if route_effort else ""),
                f"Auth: {auth_detail}" + (f" ({auth_mode})" if auth_mode else ""),
            ]
            if last_failure:
                route_detail_parts.append(
                    "Last failure: "
                    + str(
                        last_failure.get("summary")
                        or last_failure.get("error")
                        or last_failure.get("message")
                        or "recorded"
                    )
                )
            elif last_success:
                route_detail_parts.append(
                    "Last recorded action: "
                    + str(
                        last_success.get("summary")
                        or last_success.get("source")
                        or "recorded"
                    )
                )
            append(
                message_id=f"provider-truth:{mission.mission_id}:{provider_truth.get('updatedAt') or mission.updated_at}",
                title=route_title,
                detail=" · ".join(part for part in route_detail_parts if part),
                created_at=str(provider_truth.get("updatedAt") or mission.updated_at or mission.created_at),
                role="runtime",
                label="Provider route truth",
                runtime_id=mission.runtime_id,
                tone="warn" if auth_known and not auth_present else "neutral",
                process_message=True,
                trace_only=True,
                chips=[
                    route_provider,
                    route_model,
                    "auth missing" if auth_known and not auth_present else "",
                ],
            )

        latest_runtime_cycle = next(
            (
                item
                for item in reversed(list(events))
                if str(item.get("kind") or item.get("event") or "") == "mission.runtime_cycle"
            ),
            None,
        )
        if latest_runtime_cycle:
            metadata = (
                latest_runtime_cycle.get("metadata")
                if isinstance(latest_runtime_cycle.get("metadata"), dict)
                else {}
            )
            runtime_status = str(metadata.get("autopilotStatus") or mission.state.status or "").strip()
            cycle_provider = str(metadata.get("provider") or route_provider or "").strip()
            cycle_model = str(metadata.get("model") or route_model or "").strip()
            append(
                message_id=f"runtime-cycle:{mission.mission_id}:{latest_runtime_cycle.get('timestamp') or latest_runtime_cycle.get('created_at') or ''}",
                title=f"{runtime_label(mission.runtime_id)} is still cycling"
                if runtime_status
                else f"{runtime_label(mission.runtime_id)} heartbeat",
                detail=" · ".join(
                    part
                    for part in (
                        f"Status: {runtime_status}" if runtime_status else "",
                        f"Route: {cycle_provider} / {cycle_model}" if cycle_provider or cycle_model else "",
                        f"Session: {metadata.get('sessionId')}" if metadata.get("sessionId") else "",
                    )
                    if part
                ),
                created_at=str(
                    latest_runtime_cycle.get("timestamp")
                    or latest_runtime_cycle.get("created_at")
                    or mission.updated_at
                ),
                role="runtime",
                label="Runtime heartbeat",
                runtime_id=mission.runtime_id,
                tone="neutral",
                process_message=False,
                trace_only=True,
                chips=[runtime_status, cycle_provider, cycle_model],
            )

        status_detail = " · ".join(
            part
            for part in (
                f"Status: {mission.state.status}",
                "Current: "
                + (
                    mission.state.last_runtime_event
                    or mission.state.last_plan_summary
                    or (mission.state.remaining_steps[0] if mission.state.remaining_steps else "")
                    or mission.objective
                ),
                f"Next: {ControlRoomStore._next_mission_detail_action(mission)}",
            )
            if part
        )
        append(
            message_id=f"mission-review:{mission.mission_id}",
            title=mission.title or mission.objective or "Mission review",
            detail=status_detail,
            created_at=mission.updated_at or mission.created_at,
            role="runtime",
            label="Control-room mission state",
            runtime_id=mission.runtime_id,
            tone="warn"
            if mission.state.status
            in {"blocked", "needs_approval", "verification_failed", "failed"}
            else "neutral",
            process_message=False,
            trace_only=True,
            chips=[mission.state.status, runtime_label(mission.runtime_id)],
        )

        for index, revision in enumerate(list(mission.plan_revisions)[-6:]):
            steps = [
                str(value(step, "title"))
                for step in list(value(revision, "steps", []) or [])
                if value(step, "status") != "completed"
            ][:3]
            append(
                message_id=f"plan:{value(revision, 'revision_id') or index}",
                title=str(value(revision, "summary") or "Planner revision recorded"),
                detail=" · ".join(steps),
                created_at=str(value(revision, "created_at")),
                label="Control-room planner",
                tone="neutral",
                process_message=True,
                trace_only=True,
                chips=["planner", str(value(revision, "trigger"))],
            )

        for action in list(mission.action_history)[-10:]:
            result = value(action, "result", {}) or {}
            proposal = value(action, "proposal", {}) or {}
            stdout = str(value(result, "stdout"))
            error = str(value(result, "error"))
            result_summary = str(value(result, "result_summary"))
            detail = error or result_summary or stdout
            if not detail:
                continue
            action_kind = str(value(proposal, "kind"))
            title = str(value(proposal, "title"))
            append(
                message_id=f"action:{value(action, 'action_id') or len(messages)}",
                title=title or str(value(action, "action_id")) or "Mission action",
                detail=detail,
                created_at=str(value(action, "executed_at")),
                label="Control-room action result",
                tone="bad" if error else "neutral",
                process_message=True,
                trace_only=True,
                chips=[action_kind, str(value(value(action, "gate", {}) or {}, "status"))],
            )

        for session in list(mission.delegated_runtime_sessions)[-6:]:
            session_id = str(value(session, "delegated_id") or value(session, "runtime_id"))
            session_runtime = str(value(session, "runtime_id"))
            session_status = str(value(session, "status"))
            append(
                message_id=f"session:{session_id}",
                title=str(value(session, "last_event") or value(session, "detail") or f"{runtime_label(session_runtime)} lane {session_status}"),
                detail=str(value(session, "execution_target_detail") or value(session, "execution_root") or ""),
                created_at=str(value(session, "updated_at")),
                label=f"{runtime_label(session_runtime)} lane",
                runtime_id=session_runtime,
                tone="bad" if session_status == "failed" else "warn" if session_status == "waiting_for_approval" else "neutral",
                process_message=True,
                trace_only=True,
                chips=[session_status, str(value(session, "execution_target"))],
            )
            for event_index, event in enumerate(list(value(session, "latest_events", []) or [])[-8:]):
                kind = str(event.get("kind") or "runtime.event")
                event_message = str(event.get("message") or event.get("detail") or "").strip()
                is_runtime_output_event = is_process_runtime_kind(kind)
                append(
                    message_id=f"session-event:{session_id}:{event.get('event_id') or event_index}",
                    title=event_message or kind,
                    detail=str(event.get("detail") or event.get("trace") or "")[:1200],
                    created_at=str(event.get("created_at") or value(session, "updated_at")),
                    label="Hermes runtime output" if is_runtime_output_event and session_runtime == "hermes" else kind,
                    runtime_id=session_runtime,
                    tone="bad" if str(event.get("status") or "") == "failed" else "neutral",
                    process_message=True,
                    trace_only=not is_runtime_output_event,
                    chips=[kind, str(event.get("status") or "")],
                )

        for index, event in enumerate(list(events)[-limit:]):
            kind = str(event.get("kind") or event.get("event") or "mission.event")
            if kind == "mission.runtime_cycle":
                continue
            message = str(event.get("message") or event.get("detail") or "").strip()
            if not message:
                continue
            append(
                message_id=f"event:{event.get('timestamp', '')}:{kind}:{index}",
                title=message,
                detail=str(event.get("detail") or "")[:1200],
                created_at=str(event.get("timestamp") or event.get("created_at") or ""),
                role="queue" if "approval" in kind or "question" in kind else "runtime",
                label=kind,
                runtime_id=str(event.get("runtime_id") or mission.runtime_id),
                tone="bad" if any(token in kind.lower() for token in ("failed", "error", "blocked")) else "warn" if "approval" in kind.lower() else "neutral",
                process_message=True,
                trace_only=not ("approval" in kind.lower() or "question" in kind.lower()),
                chips=[kind],
            )

        messages.sort(key=lambda item: item.get("createdAt", ""))
        return messages[-limit:]

    @staticmethod
    def _next_mission_detail_action(mission: Mission) -> str:
        latest_session = (
            mission.delegated_runtime_sessions[-1]
            if mission.delegated_runtime_sessions
            else None
        )
        if mission.proof.pending_approvals:
            return "Review pending approvals before resuming mission work."
        if mission.proof.failed_checks:
            return "Fix failed checks, then resume the mission detail loop."
        if latest_session and latest_session.status in {"running", "waiting_for_approval"}:
            return "Watch delegated runtime events until a completion or blocker lands."
        if mission.state.status == "completed":
            return "Review proof and close or archive the mission."
        if mission.state.status in {"blocked", "failed"}:
            return "Resolve the blocker and resume after evidence changes."
        return "Resume the mission if the objective still has remaining work."

    @staticmethod
    def _latest_notification_agent_message(
        mission: Mission,
        *,
        root: Path | None = None,
        workspace: WorkspaceProfile | None = None,
    ) -> tuple[str, str]:
        """Return the freshest concrete runtime/report text for notification cards."""

        def value(row: object, key: str, default: object = "") -> object:
            if isinstance(row, dict):
                return row.get(key, default)
            return getattr(row, key, default)

        def concrete_text(item: dict) -> str:
            title = str(item.get("title") or item.get("message") or "").strip()
            detail = str(item.get("detail") or "").strip()
            if title and detail and detail != title:
                return f"{title}\n{detail}"
            return title or detail

        def low_signal(message: str) -> bool:
            text = message.strip().lower()
            return (
                not text
                or text == "running"
                or "delegated runtime heartbeat" in text
                or "git_diff completed with filesystem snapshot" in text
                or "git is unavailable" in text
                or text == "file mutation completed."
            )

        if root and mission.state.status not in TERMINAL_MISSION_STATUSES:
            try:
                transcript = ControlRoomStore._mission_runtime_transcript_payload(
                    mission,
                    events=[],
                    root=root,
                    workspace=workspace,
                    limit=6,
                )
            except Exception:
                transcript = {}
            transcript_messages = (
                transcript.get("messages", [])
                if isinstance(transcript, dict) and isinstance(transcript.get("messages"), list)
                else []
            )
            for item in reversed(transcript_messages):
                if not isinstance(item, dict) or not item.get("runtimeOutput"):
                    continue
                message = concrete_text(item)
                if not low_signal(message):
                    return message, f"runtime_transcript:{item.get('sessionId') or transcript.get('sessionId') or ''}"
            for item in reversed(transcript_messages):
                if not isinstance(item, dict):
                    continue
                message = concrete_text(item)
                if not low_signal(message):
                    return message, f"runtime_transcript:{item.get('sessionId') or transcript.get('sessionId') or ''}"

        latest_event_message = ""
        latest_event_source = ""
        for session in reversed(list(mission.delegated_runtime_sessions or [])[-8:]):
            session_runtime = str(value(session, "runtime_id") or mission.runtime_id)
            session_id = str(value(session, "delegated_id") or value(session, "runtime_id") or "")
            for event in reversed(list(value(session, "latest_events", []) or [])[-16:]):
                if not isinstance(event, dict):
                    continue
                kind = str(event.get("kind") or "").strip()
                message = str(event.get("message") or event.get("detail") or event.get("trace") or "").strip()
                if low_signal(message):
                    continue
                source = "runtime_output" if is_process_runtime_kind(kind) else "runtime_event"
                if is_process_runtime_kind(kind):
                    return message, f"{source}:{session_runtime}:{session_id}"
                if not latest_event_message:
                    latest_event_message = message
                    latest_event_source = f"{source}:{session_runtime}:{session_id}"
            last_event = str(value(session, "last_event") or value(session, "detail") or "").strip()
            if not low_signal(last_event) and not latest_event_message:
                latest_event_message = last_event
                latest_event_source = f"session_last_event:{session_runtime}:{session_id}"
        if latest_event_message:
            return latest_event_message, latest_event_source

        for action in reversed(list(mission.action_history or [])[-8:]):
            result = value(action, "result", {}) or {}
            if not isinstance(result, dict):
                continue
            message = str(
                result.get("result_summary")
                or result.get("stdout")
                or result.get("error")
                or ""
            ).strip()
            if not low_signal(message):
                return message, "action_history"

        fallback = (
            mission.state.last_error
            or mission.proof.summary
            or mission.state.last_plan_summary
            or (mission.state.remaining_steps[0] if mission.state.remaining_steps else "")
            or (mission.state.last_runtime_event if mission.state.last_runtime_event != "running" else "")
            or mission.objective
            or "Mission status changed."
        )
        return str(fallback or "").strip(), "mission_state"

    @staticmethod
    def _build_notification_feed(
        *,
        missions: list[Mission],
        activity: list[dict],
        watchdog_report: dict | None = None,
        root: Path | None = None,
        workspace_by_id: dict[str, WorkspaceProfile] | None = None,
        limit: int = 24,
    ) -> list[dict]:
        notifications: list[dict] = []
        for mission in missions:
            status = mission.state.status
            severity = "info"
            if status in {"blocked", "needs_approval", "verification_failed", "failed"}:
                severity = "action"
            elif status == "completed":
                severity = "success"
            elif mission.state.queue_position > 0:
                severity = "queued"
            agent_message, agent_message_source = ControlRoomStore._latest_notification_agent_message(
                mission,
                root=root,
                workspace=(workspace_by_id or {}).get(mission.workspace_id),
            )
            detail = agent_message
            notifications.append(
                {
                    "id": f"mission:{mission.mission_id}:{status}",
                    "kind": "mission_status",
                    "severity": severity,
                    "title": mission.title or mission.mission_id,
                    "detail": str(detail or "")[:320],
                    "agentMessage": agent_message[:320],
                    "agentMessageSource": agent_message_source,
                    "missionId": mission.mission_id,
                    "workspaceId": mission.workspace_id,
                    "status": status,
                    "createdAt": mission.updated_at or mission.created_at,
                    "action": "open_mission",
                }
            )
            for index, feedback in enumerate(list(mission.learned_skill_events or [])[-6:]):
                if not isinstance(feedback, dict):
                    continue
                kind = str(feedback.get("kind") or "")
                if "slice" not in kind and "feedback" not in kind:
                    continue
                skill_id = str(feedback.get("skillId") or feedback.get("skill_id") or "mission skill")
                system_loss = feedback.get("systemLoss", feedback.get("system_loss", ""))
                loss_label = ""
                try:
                    loss_label = f"system loss {float(system_loss):.2f}"
                except (TypeError, ValueError):
                    if system_loss != "":
                        loss_label = f"system loss {system_loss}"
                next_action = str(feedback.get("nextAction") or feedback.get("next_action") or "recorded")
                detail_parts = [
                    f"Slice completed for {skill_id}.",
                    loss_label,
                    f"Next action: {next_action}.",
                ]
                agent_message = " ".join(part for part in detail_parts if part)
                notifications.append(
                    {
                        "id": f"slice:{mission.mission_id}:{index}:{skill_id}:{next_action}",
                        "kind": "mission_slice_completed",
                        "severity": "success",
                        "title": f"Slice completed: {mission.title or mission.mission_id}",
                        "detail": agent_message[:320],
                        "agentMessage": agent_message[:320],
                        "missionId": mission.mission_id,
                        "workspaceId": mission.workspace_id,
                        "status": "completed",
                        "createdAt": str(feedback.get("timestamp") or mission.updated_at or mission.created_at),
                        "action": "open_mission_slice",
                    }
                )
        for problem in (
            (watchdog_report or {}).get("problemReport", {}).get("openProblems", [])
            if isinstance(watchdog_report, dict)
            else []
        )[:6]:
            severity = str(problem.get("severity") or "info")
            agent_message = str(problem.get("firstStep") or problem.get("detail") or "").strip()
            notifications.append(
                {
                    "id": f"watchdog:{problem.get('problemId', '')}",
                    "kind": "watchdog_problem",
                    "severity": "action" if severity in {"bad", "warn"} else "info",
                    "title": str(problem.get("title") or "Watchdog problem"),
                    "detail": agent_message[:320],
                    "agentMessage": agent_message[:320],
                    "missionId": str(problem.get("missionId") or ""),
                    "workspaceId": str(problem.get("workspaceId") or ""),
                    "status": str(problem.get("status") or "open"),
                    "createdAt": str(problem.get("detectedAt") or utc_now_iso()),
                    "action": "open_watchdog_problem",
                }
            )
        for event in activity[:limit]:
            event_kind = str(event.get("kind") or "activity")
            if event_kind == "mission.runtime_cycle":
                continue
            event_message = str(event.get("message") or "")
            agent_message = event_message.strip()
            is_slice_event = "slice" in event_kind.lower() and (
                "complete" in event_kind.lower()
                or "completed" in event_message.lower()
                or "feedback" in event_kind.lower()
            )
            notifications.append(
                {
                    "id": f"event:{event.get('timestamp', '')}:{event.get('kind', '')}",
                    "kind": "mission_slice_completed" if is_slice_event else event_kind,
                    "severity": "success" if is_slice_event else "info",
                    "title": "Slice completed" if is_slice_event else event_kind,
                    "detail": event_message[:320],
                    "agentMessage": agent_message[:320],
                    "missionId": str(event.get("mission_id") or event.get("missionId") or ""),
                    "workspaceId": str(event.get("workspace_id") or event.get("workspaceId") or ""),
                    "createdAt": str(event.get("timestamp") or ""),
                    "action": "open_mission_slice" if is_slice_event else "open_activity",
                }
            )
        notifications.sort(key=lambda item: item.get("createdAt", ""), reverse=True)
        return notifications[:limit]

    def _build_fast_snapshot(self, workspaces: list[WorkspaceProfile], missions: list[Mission]) -> dict:
        activity = self.recent_events()
        provider_auth_presence = _provider_auth_presence_from_env()
        workspace_payload = [
            {
                **asdict(workspace),
                "openaiCodexSetupStatus": _openai_codex_setup_status_for_workspace(
                    workspace,
                    auth_presence=provider_auth_presence,
                ),
                "minimaxSetupStatus": {},
                "runtimeStatus": None,
                "gitSnapshot": {},
                "gitActions": [],
                "validationActions": [],
                "verificationCommands": [],
                "workspaceActionHistory": [],
                "profileParameters": {},
                "skillRecommendations": [],
                "integrationRecommendations": [],
                "recommendedSkillPacks": [],
                "serviceManagement": {},
            }
            for workspace in workspaces
        ]
        missions_payload = []
        for mission in missions:
            workspace = next(
                (item for item in workspaces if item.workspace_id == mission.workspace_id),
                None,
            )
            _reconcile_mission_route_policy(mission, workspace)
            mission.state.provider_runtime_truth = _provider_truth_for_mission(
                mission,
                auth_presence=provider_auth_presence,
                workspace=workspace,
            )
            _sync_execution_scope_snapshot(mission)
            self.attach_lane_control_receipts(mission)
            mission_payload = asdict(mission)
            mission_payload["missionLoop"] = build_mission_loop_snapshot(mission)
            mission_payload["plannedScopeArtifacts"] = build_planned_scope_artifacts(
                root=self.root,
                mission=mission,
                workspace=workspace,
            )
            mission_payload["effectiveRouteContract"] = (
                mission.effective_route_contract
                if mission.effective_route_contract
                else _effective_route_contract_for_mission(mission)
            )
            mission_payload["providerTruth"] = dict(mission.state.provider_runtime_truth or {})
            mission_payload["providerCapabilities"] = _provider_capability_contract_for_mission(mission)
            missions_payload.append(mission_payload)
        storage_bridge: dict = {}
        setup_health: dict = {"actionHistory": []}
        autonomous_workflows = self.reconcile_autonomous_workflows(missions)
        return {
            "workspaceRoot": str(self.root),
            "ui": {
                "uiMode": "agent",
                "defaultMode": "agent",
                "availableModes": ["agent", "builder"],
                "layout": "t3_workbench",
                "sharedMissionState": True,
            },
            "workspaces": workspace_payload,
            "missions": missions_payload,
            "runtimes": [],
            "activity": activity,
            "inbox": [],
            "onboarding": {"setupHealth": setup_health},
            "setupHealth": setup_health,
            "guidance": {},
            "profiles": {"defaultProfile": "builder", "availableProfiles": [], "details": {}},
            "skillLibrary": {"items": [], "recommendedPacks": []},
            "workflowStudio": {},
            "harnessLab": {},
            "providerSetupStatus": {},
            "efficiencyAutotune": {},
            "bridgeLab": {"connectedSessions": []},
            "storageBridge": storage_bridge,
            "releaseReadiness": {},
            "runtimeCompartments": _build_runtime_compartments_snapshot(
                self.root,
                missions,
                runtime_statuses=[],
                setup_health=setup_health,
                storage_bridge=storage_bridge,
                provider_auth_presence=provider_auth_presence,
            ),
            "generatedImageArtifacts": _build_generated_image_artifacts_snapshot(self.root),
            "hermesMissionEvidence": _build_hermes_mission_evidence(
                self.root,
                missions,
                activity,
            ),
            "nasDeployReadiness": build_nas_deploy_readiness_snapshot(
                self.root,
                onboarding={"setupHealth": setup_health},
                setup_health=setup_health,
                storage_bridge=storage_bridge,
            ),
            "autonomousWorkflows": autonomous_workflows,
        }

    def _default_workspace_profile(self) -> WorkspaceProfile:
        now = utc_now_iso()
        return WorkspaceProfile(
            workspace_id="workspace_primary",
            name=self.root.name.replace("-", " ").title(),
            root_path=str(self.root),
            default_runtime="openclaw",
            workspace_type=detect_workspace_type(self.root),
            user_profile="builder",
            preferred_harness="fluxio_hybrid",
            routing_strategy="profile_default",
            route_overrides=[],
            auto_optimize_routing=False,
            openai_codex_auth_mode="none",
            minimax_auth_mode="none",
            commit_message_style="scoped",
            execution_target_preference="profile_default",
            local_project_path="",
            nas_project_path="",
            sync_mode="manual",
            sync_direction="bidirectional",
            sync_conflict_policy="keep_newer_and_log",
            auto_sync_to_nas=False,
            updated_at=now,
        )

    @staticmethod
    def _load_json(path: Path, default: list | dict) -> list | dict:
        try:
            stat = path.stat()
        except OSError:
            return default
        if stat.st_size <= 0:
            return default
        cache_key = str(path.resolve())
        if stat.st_size <= CONTROL_ROOM_JSON_CACHE_MAX_BYTES:
            with _CONTROL_ROOM_JSON_CACHE_LOCK:
                cached = _CONTROL_ROOM_JSON_CACHE.get(cache_key)
                if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
                    return cached[2]
        try:
            raw = path.read_text(encoding="utf-8").strip()
        except OSError:
            return default
        if not raw:
            return default
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return default
        if isinstance(payload, (list, dict)) and stat.st_size <= CONTROL_ROOM_JSON_CACHE_MAX_BYTES:
            with _CONTROL_ROOM_JSON_CACHE_LOCK:
                _CONTROL_ROOM_JSON_CACHE[cache_key] = (stat.st_mtime_ns, stat.st_size, payload)
                if len(_CONTROL_ROOM_JSON_CACHE) > CONTROL_ROOM_JSON_CACHE_MAX_ITEMS:
                    oldest_key = next(iter(_CONTROL_ROOM_JSON_CACHE))
                    _CONTROL_ROOM_JSON_CACHE.pop(oldest_key, None)
        return payload

    @staticmethod
    def _invalidate_json_cache(path: Path) -> None:
        try:
            cache_key = str(path.resolve())
        except OSError:
            cache_key = str(path)
        with _CONTROL_ROOM_JSON_CACHE_LOCK:
            _CONTROL_ROOM_JSON_CACHE.pop(cache_key, None)

    @staticmethod
    def _split_release_path(raw_path: str) -> tuple[str, str, str] | None:
        normalized = str(raw_path or "")
        match = RELEASE_PATH_PATTERN.match(normalized)
        if not match:
            return None
        prefix = match.group("prefix")
        release = match.group("release")
        suffix = match.group("suffix") or ""
        return prefix, release, suffix

    def _reanchor_release_workspaces(self, workspaces: list[WorkspaceProfile]) -> bool:
        current = self._split_release_path(str(self.root))
        if not current:
            return False
        current_prefix, current_release, _ = current
        changed = False
        for workspace in workspaces:
            parsed = self._split_release_path(workspace.root_path)
            if not parsed:
                continue
            prefix, release, suffix = parsed
            if prefix != current_prefix or release == current_release:
                continue
            next_root = f"{current_prefix}{current_release}{suffix}"
            if workspace.root_path != next_root:
                workspace.root_path = next_root
                workspace.workspace_type = detect_workspace_type(Path(next_root))
                workspace.updated_at = utc_now_iso()
                changed = True
        return changed

    def _active_workspace_mission(
        self,
        workspace_id: str,
        missions: list[Mission],
    ) -> Mission | None:
        for mission in missions:
            if mission.workspace_id != workspace_id:
                continue
            if mission.state.status in TERMINAL_MISSION_STATUSES:
                continue
            # A budget-exhausted mission should not keep the active slot forever.
            # It can remain visible in the queue, but newer missions must still advance.
            stop_reason = (mission.state.stop_reason or mission.state.last_error or "").strip().lower()
            if stop_reason == "runtime_budget":
                continue
            if mission.state.queue_position == 0:
                return mission
        return None

    def _rebalance_workspace_queue_in_place(
        self,
        missions: list[Mission],
        workspace_id: str | None = None,
    ) -> None:
        workspace_ids = (
            [workspace_id]
            if workspace_id is not None
            else list(dict.fromkeys(item.workspace_id for item in missions))
        )
        for current_workspace_id in workspace_ids:
            workspace_missions = [
                item for item in missions if item.workspace_id == current_workspace_id
            ]
            active = self._active_workspace_mission(current_workspace_id, workspace_missions)
            candidates = [
                item
                for item in workspace_missions
                if item.state.status not in TERMINAL_MISSION_STATUSES
            ]
            if not candidates:
                continue

            waiting = [
                item for item in candidates if active is None or item.mission_id != active.mission_id
            ]
            waiting.sort(
                key=lambda item: (
                    item.state.queue_position if item.state.queue_position > 0 else 10_000,
                    item.created_at,
                    item.mission_id,
                )
            )

            if active is None:
                active = waiting.pop(0)

            was_waiting = bool(
                active.state.queue_position
                or active.state.blocking_mission_id
                or active.state.queue_reason
            )
            active.state.queue_position = 0
            active.state.blocking_mission_id = None
            active.state.queue_reason = ""
            if was_waiting and active.state.status == "queued":
                active.proof.summary = (
                    "Mission reached the front of the workspace queue. Resume to start."
                )

            active_label = active.title or active.objective or active.mission_id
            for index, queued in enumerate(waiting, start=1):
                queued.state.status = "queued"
                queued.state.queue_position = index
                queued.state.blocking_mission_id = active.mission_id
                queued.state.queue_reason = (
                    f"Waiting for mission '{active_label}' to leave the active slot for this workspace."
                )
                queued.proof.summary = queued.state.queue_reason

            for mission in workspace_missions:
                if mission.state.status in TERMINAL_MISSION_STATUSES:
                    mission.state.queue_position = 0
                    mission.state.blocking_mission_id = None
                    mission.state.queue_reason = ""


def _profile_parameter_snapshot(profile_name: str, profile) -> dict:
    if profile is None:
        return {
            "profileName": profile_name,
            "autonomyLevel": "balanced",
            "approvalStrictness": "tiered",
            "verificationCadence": "each_cycle",
            "explanationLevel": "medium",
            "explorationBreadth": "bounded",
            "autoContinueBehavior": "pause_on_failure",
            "gitActionPolicy": "approval_gated",
            "setupAutomationPolicy": "guided_install",
            "learningAggressiveness": "bounded",
            "uiDensity": "comfortable",
            "visibilityLevel": "balanced",
        }

    approval_mode = profile.agent.approval_mode or "tiered"
    pause_on_failure = (
        True
        if profile.agent.pause_on_verification_failure is None
        else bool(profile.agent.pause_on_verification_failure)
    )
    delegation = profile.agent.delegation_aggressiveness or "balanced"
    mode = profile.agent.mode or "autopilot"
    autonomy_map = {
        "fast": "guided",
        "careful": "guided",
        "autopilot": "balanced",
        "swarms": "high",
        "deep_run": "maximum",
    }
    visibility_map = {
        "beginner": "guided",
        "builder": "balanced",
        "advanced": "detailed",
        "experimental": "expert",
    }
    learning_map = {
        "low": "guarded",
        "balanced": "bounded",
        "high": "aggressive",
    }
    return {
        "profileName": profile.name,
        "autonomyLevel": autonomy_map.get(mode, "balanced"),
        "approvalStrictness": approval_mode,
        "verificationCadence": "each_cycle" if pause_on_failure else "continuous_until_blocked",
        "explanationLevel": profile.agent.explanation_depth or "medium",
        "explorationBreadth": "wide" if (profile.agent.parallel_agents or 1) > 2 else "bounded",
        "autoContinueBehavior": "pause_on_failure" if pause_on_failure else "continue_until_blocked",
        "gitActionPolicy": "profile_resolved" if approval_mode == "hands_free" else "approval_gated",
        "setupAutomationPolicy": "installer_guided" if profile.name == "beginner" else "repair_and_verify",
        "learningAggressiveness": learning_map.get(delegation, "bounded"),
        "uiDensity": profile.ui.get("density", "comfortable"),
        "visibilityLevel": visibility_map.get(profile.name, "balanced"),
    }


def build_mission_loop_snapshot(mission: Mission) -> dict:
    plan_revisions = mission.plan_revisions or []
    latest_revision = plan_revisions[-1] if plan_revisions else None
    delegated = mission.delegated_runtime_sessions or []
    if mission.state.status in TERMINAL_MISSION_STATUSES:
        phase = "complete"
    elif mission.state.status in {"queued", "draft"}:
        phase = "plan"
    elif mission.state.status == "verification_failed":
        phase = "replan"
    elif mission.proof.failed_checks or mission.state.verification_failures:
        phase = "verify"
    elif any(item.status in {"launching", "running", "waiting_for_approval"} for item in delegated):
        phase = "execute"
    elif mission.state.active_step_id:
        phase = "execute"
    elif plan_revisions:
        phase = "verify"
    else:
        phase = "plan"

    verification_result = "pending"
    if mission.proof.failed_checks or mission.state.verification_failures:
        verification_result = "failed"
    elif mission.proof.passed_checks:
        verification_result = "passed"

    continuity_state, continuity_detail = _continuity_state_for_mission(mission, delegated)
    time_budget = _time_budget_snapshot_for_mission(mission)

    return {
        "currentCyclePhase": phase,
        "cycleCount": len(plan_revisions) or (1 if mission.state.status != "draft" else 0),
        "lastVerificationResult": verification_result,
        "lastVerificationSummary": _verification_summary_for_mission(mission, verification_result),
        "lastReplanReason": _plan_revision_value(latest_revision, "trigger"),
        "lastReplanTrigger": _plan_revision_value(latest_revision, "trigger"),
        "improvementQueue": [
            {"title": item.get("title", ""), "priority": item.get("priority", "medium")}
            if isinstance(item, dict)
            else {"title": getattr(item, "title", ""), "priority": getattr(item, "priority", "medium")}
            for item in mission.improvement_queue
        ],
        "resumeReady": bool(mission.state.latest_session_id),
        "continuityState": continuity_state,
        "continuityDetail": continuity_detail,
        "approvalHistoryCount": len(mission.state.approval_history),
        "pauseReason": time_budget["lastPauseReason"],
        "currentRuntimeLane": _current_runtime_lane_for_mission(mission, delegated),
        "timeBudget": time_budget,
        "contextWindow": {
            "usedTokens": mission.state.context_used_tokens,
            "usageRatio": mission.state.context_usage_ratio,
            "status": mission.state.context_status,
            "handoffCount": mission.state.handoff_count,
            "lastHandoffReason": mission.state.last_handoff_reason,
        },
        "runtimeAutonomy": _runtime_autonomy_for_mission(mission),
        "routeChangeCount": mission.state.route_change_count,
        "parallelAgents": mission.state.parallel_agents,
        "mergePolicy": mission.state.merge_policy,
        "blocker": {} if mission.state.status in TERMINAL_MISSION_STATUSES else mission.state.blocker_classification,
        "providerTruth": mission.state.provider_runtime_truth,
        "codeExecution": mission.state.code_execution,
    }


def sync_mission_state_snapshot(mission: Mission) -> dict:
    if mission.state.status == "completed":
        mission.state.last_runtime_event = "completed"
        mission.state.last_error = None
        mission.state.stop_reason = None
        mission.state.planner_loop_status = "completed"
        mission.state.pending_mutating_actions = 0
        mission.state.pending_approval_payload = {}
        mission.proof.pending_approvals = []
        if _completion_summary_needs_replacement(mission.proof.summary):
            mission.proof.summary = "Mission completed with proof artifacts."
    _sync_execution_scope_snapshot(mission)
    mission_loop = build_mission_loop_snapshot(mission)
    mission.state.current_cycle_phase = mission_loop["currentCyclePhase"]
    mission.state.cycle_count = mission_loop["cycleCount"]
    mission.state.last_verification_result = mission_loop["lastVerificationResult"]
    mission.state.last_replan_reason = mission_loop["lastReplanReason"]
    mission.state.last_verification_summary = mission_loop["lastVerificationSummary"]
    mission.state.last_replan_trigger = mission_loop["lastReplanTrigger"]
    mission.state.continuity_state = mission_loop["continuityState"]
    mission.state.continuity_detail = mission_loop["continuityDetail"]
    mission.state.elapsed_runtime_seconds = mission_loop["timeBudget"]["elapsedSeconds"]
    mission.state.remaining_runtime_seconds = mission_loop["timeBudget"]["remainingSeconds"]
    mission.state.time_budget_status = mission_loop["timeBudget"]["status"]
    mission.state.last_budget_pause_reason = mission_loop["timeBudget"]["lastPauseReason"]
    mission.state.current_runtime_lane = mission_loop["currentRuntimeLane"]
    mission.state.runtime_autonomy = mission_loop.get("runtimeAutonomy", {})
    mission.state.blocker_classification = mission_loop.get("blocker", {})
    mission.state.provider_runtime_truth = mission_loop.get("providerTruth", {})
    mission.state.code_execution = mission_loop.get("codeExecution", {})
    return mission_loop


def _sync_execution_scope_snapshot(mission: Mission) -> None:
    truth = derive_execution_target(
        execution_root=mission.execution_scope.execution_root,
        workspace_root=mission.execution_scope.workspace_root,
        strategy=mission.execution_scope.strategy,
    )
    mission.execution_scope.execution_target = truth["execution_target"]
    mission.execution_scope.storage_mode = truth["storage_mode"]
    mission.execution_scope.host_locality = truth["host_locality"]
    mission.execution_scope.execution_target_detail = truth["execution_target_detail"]
    mission.state.execution_scope = asdict(mission.execution_scope)


def _runtime_autonomy_for_mission(mission: Mission) -> dict[str, Any]:
    if mission.state.status not in TERMINAL_MISSION_STATUSES:
        return mission.state.runtime_autonomy
    autonomy = dict(mission.state.runtime_autonomy or {})
    autonomy.update(
        {
            "policy": "terminal",
            "reason": "Mission is terminal; stale delegated runtime failures are retained only as history.",
            "delegatedStatus": "idle",
            "changed": False,
        }
    )
    return autonomy


def _plan_revision_value(revision: object, key: str) -> str:
    if revision is None:
        return ""
    if isinstance(revision, dict):
        return str(revision.get(key, "") or "")
    return str(getattr(revision, key, "") or "")


def _provider_auth_presence_from_env() -> dict[str, bool]:
    global _PROVIDER_AUTH_PRESENCE_CACHE
    cache_key = tuple(
        sorted(
            (
                name,
                str(os.environ.get(name, "")),
            )
            for name in {
                *PROVIDER_ENV_HINTS.values(),
                "CODEX_HOME",
                "FLUXIO_DISABLE_WSL_AUTH_DISCOVERY",
                "FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT",
                "FLUXIO_OPENAI_CODEX_OAUTH_PRESENT",
                "FLUXIO_RUNTIME_HOME",
                "HERMES_AUTH_STORE",
                "HERMES_HOME",
                "HOME",
                "OPENCLAW_STATE_DIR",
                "SYNTELOS_RUNTIME_HOME",
            }
        )
    )
    now = time.monotonic()
    with _PROVIDER_AUTH_PRESENCE_CACHE_LOCK:
        cached = _PROVIDER_AUTH_PRESENCE_CACHE
        if (
            cached
            and cached[1] == cache_key
            and now - cached[0] <= PROVIDER_AUTH_PRESENCE_CACHE_TTL_SECONDS
        ):
            return dict(cached[2])
    presence: dict[str, bool] = {}
    provider_env_values = _provider_env_file_values()
    for provider_id, env_name in PROVIDER_ENV_HINTS.items():
        presence[provider_id] = bool(
            str(os.environ.get(env_name, "")).strip()
            or str(provider_env_values.get(env_name, "")).strip()
        )
    home = Path(os.environ.get("HOME") or str(Path.home())).expanduser()
    openclaw_auth_stores = _openclaw_auth_store_candidates(home)
    hermes_auth_stores = hermes_auth_store_candidates(home)
    codex_auth_stores = _codex_auth_store_candidates(home)
    minimax_oauth_stores = _minimax_oauth_store_candidates(home)
    for provider_id, aliases in PROVIDER_AUTH_ALIASES.items():
        if presence.get(provider_id, False):
            continue
        if any(
            _auth_store_has_provider(path, alias)
            for path in openclaw_auth_stores
            for alias in aliases
        ):
            presence[provider_id] = True
            continue
        if _auth_store_candidates_have_provider(hermes_auth_stores, *aliases):
            presence[provider_id] = True
    if str(os.environ.get("FLUXIO_OPENAI_CODEX_OAUTH_PRESENT", "")).strip():
        presence["openai-codex"] = True
    if (
        any(path.exists() for path in codex_auth_stores)
        or _auth_store_candidates_have_provider(openclaw_auth_stores, "openai-codex")
        or _auth_store_candidates_have_provider(hermes_auth_stores, "openai-codex")
    ):
        presence["openai-codex"] = True
    if str(os.environ.get("FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT", "")).strip():
        presence["minimax-portal"] = True
    if (
        any(path.exists() for path in minimax_oauth_stores)
        or _auth_store_candidates_have_provider(openclaw_auth_stores, "minimax-portal")
        or _auth_store_candidates_have_provider(
            hermes_auth_stores,
            "minimax-oauth",
            "minimax",
            "minimax-portal",
        )
    ):
        presence["minimax-portal"] = True
        presence["minimax-oauth"] = True
        presence["minimax"] = True
    with _PROVIDER_AUTH_PRESENCE_CACHE_LOCK:
        _PROVIDER_AUTH_PRESENCE_CACHE = (time.monotonic(), cache_key, dict(presence))
    return presence


def _openclaw_auth_store_candidates(home: Path | None = None) -> list[Path]:
    home = home or Path(os.environ.get("HOME") or str(Path.home())).expanduser()
    candidates = [
        Path(os.environ.get("OPENCLAW_STATE_DIR", str(home / ".openclaw"))).expanduser()
        / "agents"
        / "main"
        / "agent"
        / "auth-profiles.json"
    ]
    for runtime_home in _runtime_home_candidates():
        candidates.append(
            runtime_home / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
        )
    return _dedupe_paths(candidates)


def _codex_auth_store_candidates(home: Path | None = None) -> list[Path]:
    home = home or Path(os.environ.get("HOME") or str(Path.home())).expanduser()
    candidates = [home / ".codex" / "auth.json"]
    codex_home = str(os.environ.get("CODEX_HOME") or "").strip()
    if codex_home:
        candidates.append(Path(codex_home).expanduser() / "auth.json")
    for runtime_home in _runtime_home_candidates():
        candidates.append(runtime_home / ".codex" / "auth.json")
    return _dedupe_paths(candidates)


def _minimax_oauth_store_candidates(home: Path | None = None) -> list[Path]:
    home = home or Path(os.environ.get("HOME") or str(Path.home())).expanduser()
    candidates = [home / ".minimax" / "oauth_creds.json"]
    for runtime_home in _runtime_home_candidates():
        candidates.append(runtime_home / ".minimax" / "oauth_creds.json")
    return _dedupe_paths(candidates)


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _provider_env_file_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for path in _provider_env_file_candidates():
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            parsed = _parse_provider_env_line(line)
            if not parsed:
                continue
            key, value = parsed
            if key in {
                "OPENAI_API_KEY",
                "ANTHROPIC_API_KEY",
                "OPENROUTER_API_KEY",
                "MINIMAX_API_KEY",
                "MINIMAX_OAUTH_TOKEN",
                "FLUXIO_OPENAI_CODEX_OAUTH_PRESENT",
                "FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT",
            } and value:
                values[key] = value
    return values


def _provider_env_file_candidates() -> list[Path]:
    candidates: list[Path] = []
    explicit = str(os.environ.get("FLUXIO_PROVIDER_ENV_FILE") or "").strip()
    if explicit:
        candidates.append(Path(explicit).expanduser())
    for env_name in ("FLUXIO_RUNTIME_HOME", "SYNTELOS_RUNTIME_HOME", "HOME"):
        value = str(os.environ.get(env_name) or "").strip()
        if value:
            candidates.append(Path(value).expanduser() / ".fluxio_provider_env")
    try:
        cwd = Path.cwd().resolve()
    except OSError:
        cwd = Path.cwd()
    parts = cwd.parts
    if "releases" in parts:
        release_index = parts.index("releases")
        if release_index >= 1:
            base = Path(*parts[:release_index])
            candidates.append(base / "runtime" / "home" / ".fluxio_provider_env")
    candidates.append(Path("/volume1/Saclay/projects/syntelos/runtime/home/.fluxio_provider_env"))
    return _dedupe_paths(candidates)


def _parse_provider_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()
    if "=" not in stripped:
        return None
    key, raw_value = stripped.split("=", 1)
    key = key.strip()
    if not re.fullmatch(r"[A-Z0-9_]+", key):
        return None
    try:
        tokens = shlex.split(raw_value, posix=True)
    except ValueError:
        value = raw_value.strip().strip("\"'")
    else:
        value = tokens[0] if tokens else ""
    return key, value


def _route_role_for_phase(phase: str) -> str:
    normalized = str(phase or "execute").strip().lower()
    if normalized in {"plan", "replan"}:
        return "planner"
    if normalized == "verify":
        return "verifier"
    return "executor"


def _route_rows_for_mission(mission: Mission) -> list[dict]:
    effective_contract = (
        mission.effective_route_contract
        if mission.effective_route_contract
        else _effective_route_contract_for_mission(mission)
    )
    rows = effective_contract.get("roles", [])
    if not isinstance(rows, list):
        return []
    normalized: list[dict] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        if role not in ROUTE_OVERRIDE_ROLES:
            continue
        normalized.append(
            {
                "role": role,
                "provider": str(item.get("provider", "")).strip().lower(),
                "model": str(item.get("model", "")).strip(),
                "effort": str(item.get("effort", "")).strip().lower(),
                "budgetClass": str(
                    item.get("budgetClass", item.get("budget_class", ""))
                ).strip(),
                "source": str(item.get("source", "")).strip(),
                "reason": str(item.get("reason", "")).strip(),
            }
        )
    return normalized


def _path_has_syncable_files(root: Path) -> bool:
    if not root.exists() or not root.is_dir():
        return False
    for current_root, dir_names, file_names in os.walk(root):
        dir_names[:] = [name for name in dir_names if name not in SYNC_EXCLUDED_DIRS]
        if any(file_name not in SYNC_EXCLUDED_FILES for file_name in file_names):
            return True
    return False


def _sync_local_and_nas_projects(
    *,
    local_root: Path | None,
    nas_root: Path,
    sync_direction: str,
    conflict_policy: str,
) -> dict[str, object]:
    if local_root is None:
        return {}

    requested_direction = normalize_sync_direction(sync_direction)
    effective_direction = requested_direction
    local_exists_initial = local_root.exists() and local_root.is_dir()
    nas_exists_initial = nas_root.exists() and nas_root.is_dir()
    local_has_files_initial = _path_has_syncable_files(local_root)
    nas_has_files_initial = _path_has_syncable_files(nas_root)
    direction_auto_promoted = False
    if (
        local_has_files_initial
        and nas_has_files_initial
        and effective_direction in {"local_to_nas", "nas_to_local"}
    ):
        effective_direction = "bidirectional"
        direction_auto_promoted = True
    if not nas_exists_initial:
        nas_root.mkdir(parents=True, exist_ok=True)

    passes: list[dict[str, object]] = []
    if effective_direction in {"local_to_nas", "bidirectional"} and local_exists_initial:
        status = _sync_project_tree(
            local_root,
            nas_root,
            conflict_policy=_sync_conflict_policy_for_direction(
                conflict_policy,
                direction="local_to_nas",
            ),
        )
        passes.append({"direction": "local_to_nas", **status})

    if effective_direction in {"nas_to_local", "bidirectional"}:
        if not local_root.exists():
            local_root.mkdir(parents=True, exist_ok=True)
        if local_root.is_dir() and nas_root.exists() and nas_root.is_dir():
            status = _sync_project_tree(
                nas_root,
                local_root,
                conflict_policy=_sync_conflict_policy_for_direction(
                    conflict_policy,
                    direction="nas_to_local",
                ),
            )
            passes.append({"direction": "nas_to_local", **status})

    files_copied = 0
    files_skipped = 0
    locked_skipped = 0
    missing_skipped = 0
    conflicts_detected = 0
    locked_samples: list[str] = []
    conflict_samples: list[dict[str, object]] = []
    conflict_receipts: list[dict[str, object]] = []
    for item in passes:
        files_copied += int(item.get("filesCopied", 0) or 0)
        files_skipped += int(item.get("filesSkipped", 0) or 0)
        locked_skipped += int(item.get("lockedFilesSkipped", 0) or 0)
        missing_skipped += int(item.get("missingFilesSkipped", 0) or 0)
        conflicts_detected += int(item.get("conflictsDetected", 0) or 0)
        for sample in item.get("lockedFileSamples", []):
            sample_text = str(sample or "").strip()
            if not sample_text or sample_text in locked_samples:
                continue
            locked_samples.append(sample_text)
            if len(locked_samples) >= SYNC_LOCKED_FILE_SAMPLE_LIMIT:
                break
        for sample in item.get("conflictSamples", []):
            if not isinstance(sample, dict):
                continue
            key = json.dumps(sample, sort_keys=True)
            if any(json.dumps(existing, sort_keys=True) == key for existing in conflict_samples):
                continue
            conflict_samples.append(sample)
            if len(conflict_samples) >= SYNC_CONFLICT_SAMPLE_LIMIT:
                break
        receipt = item.get("syncReceipt")
        if isinstance(receipt, dict):
            conflict_receipts.append(receipt)

    reason = "sync_not_needed"
    if passes:
        if local_has_files_initial and nas_has_files_initial:
            reason = "detected_existing_both_synced"
        elif local_has_files_initial and not nas_has_files_initial:
            reason = "detected_local_primary_synced"
        elif nas_has_files_initial and not local_has_files_initial:
            reason = "detected_nas_primary_synced"
        else:
            reason = "synced"

    payload: dict[str, object] = {
        "synced": bool(passes),
        "reason": reason,
        "source": str(local_root),
        "target": str(nas_root),
        "localPath": str(local_root),
        "nasPath": str(nas_root),
        "localExists": local_exists_initial,
        "nasExists": nas_exists_initial,
        "localHasFiles": local_has_files_initial,
        "nasHasFiles": nas_has_files_initial,
        "detectedBothWithFiles": bool(local_has_files_initial and nas_has_files_initial),
        "requestedDirection": requested_direction,
        "effectiveDirection": effective_direction,
        "filesCopied": files_copied,
        "filesSkipped": files_skipped,
        "passes": passes,
    }
    payload["syncReceipt"] = _build_workspace_sync_receipt(
        local_root=local_root,
        nas_root=nas_root,
        requested_direction=requested_direction,
        effective_direction=effective_direction,
        conflict_policy=conflict_policy,
        passes=passes,
        files_copied=files_copied,
        files_skipped=files_skipped,
        conflicts_detected=conflicts_detected,
        conflict_receipts=conflict_receipts,
    )
    if conflicts_detected:
        payload["conflictsDetected"] = conflicts_detected
        payload["conflictSamples"] = conflict_samples
        payload["conflictReceipts"] = conflict_receipts
    if any(item.get("manualReviewRequired") for item in passes):
        payload["manualReviewRequired"] = True
    if direction_auto_promoted:
        payload["directionAutoPromoted"] = True
    if locked_skipped:
        payload["lockedFilesSkipped"] = locked_skipped
        payload["lockedFileSamples"] = locked_samples
    if missing_skipped:
        payload["missingFilesSkipped"] = missing_skipped
    return payload


def _sync_conflict_policy_for_direction(conflict_policy: str, *, direction: str) -> str:
    normalized = str(conflict_policy or "keep_newer_and_log").strip().lower()
    if direction == "nas_to_local":
        if normalized == "local_wins":
            return "nas_wins"
        if normalized == "nas_wins":
            return "local_wins"
    return normalized


def _sync_project_tree(source: Path, target: Path, *, conflict_policy: str) -> dict[str, object]:
    if not source.exists() or not source.is_dir():
        return {
            "synced": False,
            "reason": "source_missing",
            "source": str(source),
            "target": str(target),
            "filesCopied": 0,
            "filesSkipped": 0,
        }
    if source.resolve() == target.resolve():
        return {
            "synced": True,
            "reason": "same_path",
            "source": str(source),
            "target": str(target),
            "filesCopied": 0,
            "filesSkipped": 0,
        }
    target.mkdir(parents=True, exist_ok=True)
    copied = 0
    skipped = 0
    locked_skipped = 0
    missing_skipped = 0
    conflicts_detected = 0
    manual_review_required = False
    locked_samples: list[str] = []
    conflict_samples: list[dict[str, object]] = []
    for current_root, dir_names, file_names in os.walk(source):
        dir_names[:] = [name for name in dir_names if name not in SYNC_EXCLUDED_DIRS]
        relative_root = Path(current_root).relative_to(source)
        target_root = target / relative_root
        target_root.mkdir(parents=True, exist_ok=True)
        for file_name in file_names:
            if file_name in SYNC_EXCLUDED_FILES:
                skipped += 1
                continue
            source_file = Path(current_root) / file_name
            target_file = target_root / file_name
            if target_file.exists():
                conflict_sample: dict[str, object] | None = None
                if _sync_files_conflict(source_file, target_file):
                    conflicts_detected += 1
                    conflict_sample = _sync_conflict_sample(
                        source_file=source_file,
                        target_file=target_file,
                        source_root=source,
                        conflict_policy=conflict_policy,
                    )
                    if len(conflict_samples) < SYNC_CONFLICT_SAMPLE_LIMIT:
                        conflict_samples.append(conflict_sample)
                if conflict_policy == "local_wins":
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    copy_result = _copy_project_file_with_retry(source_file, target_file)
                    if copy_result == "copied":
                        copied += 1
                        continue
                    skipped += 1
                    if copy_result == "locked":
                        locked_skipped += 1
                        if len(locked_samples) < SYNC_LOCKED_FILE_SAMPLE_LIMIT:
                            locked_samples.append(str(source_file))
                        continue
                    if copy_result == "missing":
                        missing_skipped += 1
                        continue
                elif conflict_policy == "nas_wins":
                    skipped += 1
                    continue
                elif conflict_policy == "manual_review":
                    manual_review_required = bool(conflict_sample)
                    skipped += 1
                    continue
                try:
                    target_mtime = target_file.stat().st_mtime
                    source_mtime = source_file.stat().st_mtime
                except FileNotFoundError:
                    skipped += 1
                    missing_skipped += 1
                    continue
                except OSError as exc:
                    if _is_locked_copy_error(exc):
                        skipped += 1
                        locked_skipped += 1
                        if len(locked_samples) < SYNC_LOCKED_FILE_SAMPLE_LIMIT:
                            locked_samples.append(str(source_file))
                        continue
                    raise
                if target_mtime >= source_mtime:
                    skipped += 1
                    continue
            target_file.parent.mkdir(parents=True, exist_ok=True)
            copy_result = _copy_project_file_with_retry(source_file, target_file)
            if copy_result == "copied":
                copied += 1
                continue
            skipped += 1
            if copy_result == "locked":
                locked_skipped += 1
                if len(locked_samples) < SYNC_LOCKED_FILE_SAMPLE_LIMIT:
                    locked_samples.append(str(source_file))
                continue
            if copy_result == "missing":
                missing_skipped += 1
                continue
    payload = {
        "synced": True,
        "reason": "copied",
        "source": str(source),
        "target": str(target),
        "filesCopied": copied,
        "filesSkipped": skipped,
    }
    payload["syncReceipt"] = _build_sync_pass_receipt(
        source=source,
        target=target,
        conflict_policy=conflict_policy,
        files_copied=copied,
        files_skipped=skipped,
        conflicts_detected=conflicts_detected,
        manual_review_required=manual_review_required,
        conflict_samples=conflict_samples,
    )
    if conflicts_detected:
        payload["conflictsDetected"] = conflicts_detected
        payload["conflictSamples"] = conflict_samples
        if manual_review_required:
            payload["reason"] = "manual_review_required"
            payload["manualReviewRequired"] = True
    if locked_skipped:
        payload["reason"] = "copied_with_locked_files"
        payload["lockedFilesSkipped"] = locked_skipped
        payload["lockedFileSamples"] = locked_samples
    if missing_skipped:
        payload["missingFilesSkipped"] = missing_skipped
    return payload


def _sync_files_conflict(source_file: Path, target_file: Path) -> bool:
    try:
        source_stat = source_file.stat()
        target_stat = target_file.stat()
    except OSError:
        return True
    if source_stat.st_size != target_stat.st_size:
        return True
    return abs(source_stat.st_mtime - target_stat.st_mtime) > 1e-6


def _sync_conflict_sample(
    *,
    source_file: Path,
    target_file: Path,
    source_root: Path,
    conflict_policy: str,
) -> dict[str, object]:
    try:
        relative_path = str(source_file.relative_to(source_root))
    except ValueError:
        relative_path = source_file.name
    try:
        source_mtime = source_file.stat().st_mtime
    except OSError:
        source_mtime = 0.0
    try:
        target_mtime = target_file.stat().st_mtime
    except OSError:
        target_mtime = 0.0
    resolution = "manual_review_required"
    if conflict_policy == "local_wins":
        resolution = "source_overwrites_target"
    elif conflict_policy == "nas_wins":
        resolution = "target_kept"
    elif conflict_policy == "keep_newer_and_log":
        resolution = "source_newer_copied" if source_mtime > target_mtime else "target_newer_kept"
    return {
        "relativePath": relative_path,
        "sourcePath": str(source_file),
        "targetPath": str(target_file),
        "sourceMtime": source_mtime,
        "targetMtime": target_mtime,
        "policy": conflict_policy,
        "resolution": resolution,
    }


def _build_sync_pass_receipt(
    *,
    source: Path,
    target: Path,
    conflict_policy: str,
    files_copied: int,
    files_skipped: int,
    conflicts_detected: int,
    manual_review_required: bool,
    conflict_samples: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema": "fluxio.sync_conflict_receipt.v1",
        "receiptId": f"sync_pass_{uuid.uuid4().hex[:10]}",
        "generatedAt": utc_now_iso(),
        "source": str(source),
        "target": str(target),
        "conflictPolicy": conflict_policy,
        "filesCopied": files_copied,
        "filesSkipped": files_skipped,
        "conflictsDetected": conflicts_detected,
        "manualReviewRequired": bool(manual_review_required),
        "conflictSamples": conflict_samples[:SYNC_CONFLICT_SAMPLE_LIMIT],
    }


def _build_workspace_sync_receipt(
    *,
    local_root: Path,
    nas_root: Path,
    requested_direction: str,
    effective_direction: str,
    conflict_policy: str,
    passes: list[dict[str, object]],
    files_copied: int,
    files_skipped: int,
    conflicts_detected: int,
    conflict_receipts: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema": "fluxio.workspace_sync_receipt.v1",
        "receiptId": f"sync_tx_{uuid.uuid4().hex[:10]}",
        "generatedAt": utc_now_iso(),
        "localPath": str(local_root),
        "nasPath": str(nas_root),
        "requestedDirection": requested_direction,
        "effectiveDirection": effective_direction,
        "conflictPolicy": conflict_policy,
        "passCount": len(passes),
        "filesCopied": files_copied,
        "filesSkipped": files_skipped,
        "conflictsDetected": conflicts_detected,
        "manualReviewRequired": any(item.get("manualReviewRequired") for item in passes),
        "passReceiptIds": [
            str(item.get("receiptId", ""))
            for item in conflict_receipts
            if item.get("receiptId")
        ],
    }


def _workspace_sync_status(workspace: WorkspaceProfile) -> dict[str, object]:
    for entry in workspace.goals or []:
        raw = str(entry or "")
        if not raw.startswith("sync_status:"):
            continue
        try:
            payload = json.loads(raw.split(":", 1)[1])
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}
    return {}


def _cross_device_launch_receipts_path(root: Path) -> Path:
    return root / ".agent_control" / "cross_device_launch_rehearsals" / "receipts.jsonl"


def _latest_cross_device_launch_receipt(root: Path, workspace_id: str) -> dict[str, object]:
    history = _cross_device_launch_receipt_history(root, workspace_id=workspace_id, limit=1)
    return history[0] if history else {}


def _cross_device_launch_receipt_history(
    root: Path,
    *,
    workspace_id: str = "",
    limit: int = 20,
) -> list[dict[str, object]]:
    path = _cross_device_launch_receipts_path(root)
    if not path.exists():
        return []
    try:
        rows = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    receipts: list[dict[str, object]] = []
    for line in rows:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        if row.get("schema") != "fluxio.cross_device_launch_rehearsal_receipt.v1":
            continue
        if workspace_id and str(row.get("workspaceId") or "") != workspace_id:
            continue
        receipts.append(row)
    receipts.sort(key=lambda item: str(item.get("generatedAt") or ""), reverse=True)
    return receipts[: max(1, int(limit or 1))]


def _cross_device_launch_receipt_summary(root: Path) -> dict[str, object]:
    history = _cross_device_launch_receipt_history(root, limit=100)
    status_counts: dict[str, int] = {}
    workspace_ids: set[str] = set()
    mission_ids: set[str] = set()
    for receipt in history:
        status = str(receipt.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        workspace_id = str(receipt.get("workspaceId") or "")
        mission_id = str(receipt.get("missionId") or "")
        if workspace_id:
            workspace_ids.add(workspace_id)
        if mission_id:
            mission_ids.add(mission_id)
    latest = history[0] if history else {}
    launched_statuses = {"launched", "launched_with_review_items"}
    return {
        "schema": "fluxio.cross_device_launch_rehearsal_receipt_summary.v1",
        "receiptCount": len(history),
        "launchedReceiptCount": sum(
            1 for receipt in history if receipt.get("status") in launched_statuses
        ),
        "workspaceCount": len(workspace_ids),
        "missionCount": len(mission_ids),
        "statusCounts": status_counts,
        "latestReceiptId": str(latest.get("receiptId") or ""),
        "latestGeneratedAt": str(latest.get("generatedAt") or ""),
        "trendStatus": "repeated" if len(history) >= 2 else "single" if history else "empty",
        "nextAction": (
            "Keep repeating launch rehearsal receipts across more project pairs."
            if len(history) >= 2
            else "Record at least one more launch rehearsal receipt to prove the path over time."
            if history
            else "Record the first launch rehearsal receipt from a real mission launch."
        ),
    }


def record_cross_device_launch_rehearsal_receipt(
    *,
    store: ControlRoomStore,
    workspace_id: str,
    mission_id: str = "",
    require_ready: bool = True,
) -> dict[str, object]:
    snapshot = store.build_summary_snapshot()
    progress = snapshot.get("projectProgressHistory", {})
    projects = progress.get("projects", []) if isinstance(progress, dict) else []
    project = next(
        (
            item
            for item in projects
            if isinstance(item, dict) and str(item.get("workspaceId") or "") == workspace_id
        ),
        {},
    )
    if not project:
        raise ValueError(f"Unknown workspace id for launch rehearsal: {workspace_id}")
    rehearsal = project.get("launchRehearsal", {})
    if not isinstance(rehearsal, dict) or rehearsal.get("schema") != "fluxio.cross_device_launch_rehearsal.v1":
        raise ValueError(f"Workspace has no cross-device launch rehearsal: {workspace_id}")
    safe_to_launch = bool(rehearsal.get("safeToLaunch"))
    mission = store.get_mission(mission_id) if mission_id else None
    if mission_id and mission is None:
        raise ValueError(f"Unknown mission id for rehearsal receipt: {mission_id}")
    if require_ready and not safe_to_launch and not mission:
        raise ValueError(
            "Cross-device launch rehearsal is not ready; resolve blocked checks before recording a launch receipt."
        )
    receipt_status = (
        "launched"
        if mission and safe_to_launch
        else "launched_with_review_items"
        if mission
        else "ready_recorded"
        if safe_to_launch
        else "review_recorded"
    )
    receipt = {
        "schema": "fluxio.cross_device_launch_rehearsal_receipt.v1",
        "receiptId": f"cross_launch_{uuid.uuid4().hex[:10]}",
        "generatedAt": utc_now_iso(),
        "workspaceId": workspace_id,
        "workspaceName": str(project.get("workspaceName") or ""),
        "missionId": mission.mission_id if mission else "",
        "missionTitle": (mission.title or mission.objective) if mission else "",
        "status": receipt_status,
        "rehearsalStatus": str(rehearsal.get("status") or ""),
        "safeToLaunch": safe_to_launch,
        "blockedCheckIds": list(rehearsal.get("blockedCheckIds") or []),
        "checklist": list(rehearsal.get("checklist") or []),
        "recommendedRuntime": str(rehearsal.get("recommendedRuntime") or ""),
        "urlPath": str(rehearsal.get("urlPath") or ""),
        "cliCommand": str(rehearsal.get("cliCommand") or ""),
        "syncAuthority": project.get("syncAuthority", {}),
        "scheduleRecommendation": project.get("scheduleRecommendation", {}),
        "nextAction": (
            "Receipt archived for a real mission launched from the cross-device rehearsal path."
            if mission and safe_to_launch
            else "Receipt archived for a real mission, with rehearsal review items still visible."
            if mission
            else "Receipt archived for a ready cross-device launch rehearsal."
            if safe_to_launch
            else "Receipt archived for review-only rehearsal evidence."
        ),
    }
    path = _cross_device_launch_receipts_path(store.root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")
    latest_path = path.parent / "latest.json"
    latest_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def _safe_sync_child_path(base: Path, relative_path: str) -> Path:
    clean_relative = str(relative_path or "").strip().replace("\\", "/")
    if not clean_relative or clean_relative.startswith("/") or "://" in clean_relative:
        raise ValueError("Conflict resolution requires a relative project path.")
    candidate = (base / clean_relative).resolve()
    if not candidate.is_relative_to(base.resolve()):
        raise ValueError("Conflict path must stay inside the workspace sync roots.")
    return candidate


def _resolution_copy(source: Path, target: Path) -> tuple[str, bool, str]:
    if not source.exists() or not source.is_file():
        return "error", False, "source_missing"
    target.parent.mkdir(parents=True, exist_ok=True)
    result = _copy_project_file_with_retry(source, target)
    if result == "copied":
        return "resolved", True, ""
    return "error", False, result


def _append_sync_conflict_resolution_goal(
    store: ControlRoomStore,
    workspace: WorkspaceProfile,
    receipt: dict[str, object],
) -> None:
    workspaces = store.load_workspaces()
    for item in workspaces:
        if item.workspace_id != workspace.workspace_id:
            continue
        prior = [
            entry
            for entry in item.goals
            if not str(entry).startswith("sync_conflict_resolution:")
        ][-20:]
        resolution_entries = [
            entry
            for entry in item.goals
            if str(entry).startswith("sync_conflict_resolution:")
        ][-11:]
        item.goals = [
            *prior,
            *resolution_entries,
            f"sync_conflict_resolution:{json.dumps(receipt, sort_keys=True)}",
        ]
        item.updated_at = utc_now_iso()
        store.save_workspaces(workspaces)
        return


def _append_sync_conflict_batch_resolution_goal(
    store: ControlRoomStore,
    workspace: WorkspaceProfile,
    receipt: dict[str, object],
) -> None:
    workspaces = store.load_workspaces()
    for item in workspaces:
        if item.workspace_id != workspace.workspace_id:
            continue
        prior = [
            entry
            for entry in item.goals
            if not str(entry).startswith("sync_conflict_batch_resolution:")
        ][-20:]
        batch_entries = [
            entry
            for entry in item.goals
            if str(entry).startswith("sync_conflict_batch_resolution:")
        ][-5:]
        item.goals = [
            *prior,
            *batch_entries,
            f"sync_conflict_batch_resolution:{json.dumps(receipt, sort_keys=True)}",
        ]
        item.updated_at = utc_now_iso()
        store.save_workspaces(workspaces)
        return


def resolve_workspace_sync_conflict(
    *,
    store: ControlRoomStore,
    workspace_id: str,
    relative_path: str,
    resolution: str,
) -> dict[str, object]:
    workspace = next(
        (item for item in store.load_workspaces() if item.workspace_id == workspace_id),
        None,
    )
    if workspace is None:
        raise ValueError(f"Unknown workspace: {workspace_id}")
    local_root_text = str(workspace.local_project_path or "").strip()
    nas_root_text = str(workspace.nas_project_path or workspace.root_path or "").strip()
    if not local_root_text or not nas_root_text:
        raise ValueError("Workspace needs both local_project_path and nas_project_path for conflict resolution.")
    local_root = Path(local_root_text).expanduser().resolve()
    nas_root = Path(nas_root_text).expanduser().resolve()
    local_file = _safe_sync_child_path(local_root, relative_path)
    nas_file = _safe_sync_child_path(nas_root, relative_path)
    normalized_resolution = str(resolution or "").strip().lower()
    status = "resolved"
    copied = False
    source_path = ""
    target_path = ""
    error = ""

    if normalized_resolution == "local_wins":
        source_path = str(local_file)
        target_path = str(nas_file)
        status, copied, error = _resolution_copy(local_file, nas_file)
    elif normalized_resolution == "nas_wins":
        source_path = str(nas_file)
        target_path = str(local_file)
        status, copied, error = _resolution_copy(nas_file, local_file)
    elif normalized_resolution == "keep_newer":
        if local_file.exists() and nas_file.exists():
            source = local_file if local_file.stat().st_mtime >= nas_file.stat().st_mtime else nas_file
            target = nas_file if source == local_file else local_file
            source_path = str(source)
            target_path = str(target)
            status, copied, error = _resolution_copy(source, target)
        elif local_file.exists():
            source_path = str(local_file)
            target_path = str(nas_file)
            status, copied, error = _resolution_copy(local_file, nas_file)
        elif nas_file.exists():
            source_path = str(nas_file)
            target_path = str(local_file)
            status, copied, error = _resolution_copy(nas_file, local_file)
        else:
            status = "error"
            error = "both_files_missing"
    elif normalized_resolution == "manual_review":
        status = "manual_review_recorded"
    else:
        raise ValueError("Resolution must be local_wins, nas_wins, keep_newer, or manual_review.")

    sync_status = _workspace_sync_status(workspace)
    receipt = {
        "schema": "fluxio.sync_conflict_resolution_receipt.v1",
        "receiptId": f"sync_resolve_{uuid.uuid4().hex[:10]}",
        "generatedAt": utc_now_iso(),
        "workspaceId": workspace.workspace_id,
        "workspaceName": workspace.name,
        "relativePath": str(relative_path).replace("\\", "/"),
        "resolution": normalized_resolution,
        "status": status,
        "copied": copied,
        "sourcePath": source_path,
        "targetPath": target_path,
        "localPath": str(local_file),
        "nasPath": str(nas_file),
        "error": error,
        "previousSyncReceiptId": str(
            (sync_status.get("syncReceipt") or {}).get("receiptId", "")
            if isinstance(sync_status.get("syncReceipt"), dict)
            else ""
        ),
        "nextAction": (
            "Re-run project sync or launch the waiting mission now that this conflict is resolved."
            if status == "resolved"
            else "Open both files and choose local_wins, nas_wins, or keep_newer."
            if status == "manual_review_recorded"
            else "Fix the conflict resolution error, then retry."
        ),
    }
    _append_sync_conflict_resolution_goal(store, workspace, receipt)
    return receipt


def resolve_workspace_sync_conflict_batch(
    *,
    store: ControlRoomStore,
    workspace_id: str,
    relative_paths: list[str],
    resolution: str,
) -> dict[str, object]:
    workspace = next(
        (item for item in store.load_workspaces() if item.workspace_id == workspace_id),
        None,
    )
    if workspace is None:
        raise ValueError(f"Unknown workspace: {workspace_id}")
    normalized_resolution = str(resolution or "").strip().lower()
    if normalized_resolution not in {"local_wins", "nas_wins", "keep_newer", "manual_review"}:
        raise ValueError("Resolution must be local_wins, nas_wins, keep_newer, or manual_review.")

    unique_paths: list[str] = []
    seen: set[str] = set()
    for value in relative_paths or []:
        normalized = str(value or "").strip().replace("\\", "/")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_paths.append(normalized)
    if not unique_paths:
        raise ValueError("Batch conflict resolution requires at least one relative path.")

    receipts: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    for relative_path in unique_paths:
        try:
            receipt = resolve_workspace_sync_conflict(
                store=store,
                workspace_id=workspace_id,
                relative_path=relative_path,
                resolution=normalized_resolution,
            )
        except ValueError as exc:
            errors.append(
                {
                    "relativePath": relative_path,
                    "status": "error",
                    "error": str(exc),
                }
            )
            continue
        receipts.append(receipt)
        if receipt.get("status") == "error":
            errors.append(
                {
                    "relativePath": relative_path,
                    "status": receipt.get("status"),
                    "error": receipt.get("error") or "resolution_error",
                    "receiptId": receipt.get("receiptId"),
                }
            )

    resolved_count = sum(1 for item in receipts if item.get("status") == "resolved")
    manual_review_count = sum(1 for item in receipts if item.get("status") == "manual_review_recorded")
    error_count = len(errors)
    status = "resolved" if resolved_count == len(unique_paths) else ("partial" if receipts else "error")
    if manual_review_count and not error_count and resolved_count == 0:
        status = "manual_review_recorded"
    elif error_count:
        status = "partial" if receipts else "error"

    batch_receipt = {
        "schema": "fluxio.sync_conflict_batch_resolution_receipt.v1",
        "receiptId": f"sync_batch_{uuid.uuid4().hex[:10]}",
        "generatedAt": utc_now_iso(),
        "workspaceId": workspace.workspace_id,
        "workspaceName": workspace.name,
        "resolution": normalized_resolution,
        "requestedCount": len(unique_paths),
        "resolvedCount": resolved_count,
        "manualReviewCount": manual_review_count,
        "errorCount": error_count,
        "status": status,
        "relativePaths": unique_paths,
        "receiptIds": [str(item.get("receiptId") or "") for item in receipts if item.get("receiptId")],
        "receipts": receipts,
        "errors": errors,
        "nextAction": (
            "Re-run project sync or resume waiting missions now that the batch conflicts are resolved."
            if status == "resolved"
            else "Open the unresolved paths and retry the failed conflict resolutions."
            if error_count
            else "Review the recorded manual-review batch before choosing a write direction."
        ),
    }
    _append_sync_conflict_batch_resolution_goal(store, workspace, batch_receipt)
    return batch_receipt


def _copy_project_file_with_retry(source_file: Path, target_file: Path) -> str:
    for attempt in range(SYNC_COPY_RETRY_ATTEMPTS):
        try:
            shutil.copy2(source_file, target_file)
            return "copied"
        except FileNotFoundError:
            return "missing"
        except OSError as exc:
            if not _is_locked_copy_error(exc):
                raise
            if attempt >= SYNC_COPY_RETRY_ATTEMPTS - 1:
                return "locked"
            time.sleep(SYNC_COPY_RETRY_BASE_DELAY_SECONDS * (attempt + 1))
    return "locked"


def _is_locked_copy_error(error: OSError) -> bool:
    winerror = getattr(error, "winerror", None)
    if winerror in {32, 33}:
        return True
    if error.errno in {EBUSY, ETXTBSY}:
        return True
    message = str(error).strip().lower()
    return any(
        token in message
        for token in (
            "used by another process",
            "being used by another process",
            "resource busy",
            "text file busy",
            "utilise par un autre processus",
            "utilisé par un autre processus",
        )
    )


def _route_row_for_phase(
    mission: Mission,
    phase: str,
    *,
    route_rows: list[dict] | None = None,
) -> dict:
    rows = route_rows if route_rows is not None else _route_rows_for_mission(mission)
    role = _route_role_for_phase(phase)
    for item in rows:
        if str(item.get("role", "")).strip().lower() == role:
            return item
    return {
        "role": role,
        "provider": "",
        "model": "",
        "effort": "",
        "budgetClass": "",
        "source": "",
        "reason": "",
    }


def _provider_truth_from_action_history(
    mission: Mission,
    *,
    route_rows: list[dict],
) -> tuple[dict, dict]:
    success: dict = {}
    failure: dict = {}
    for entry in reversed(mission.action_history or []):
        if not isinstance(entry, dict):
            if hasattr(entry, "__dataclass_fields__"):
                entry = asdict(entry)
            else:
                continue
        result = dict(entry.get("result", {}))
        proposal = dict(entry.get("proposal", {}))
        delegation = dict(proposal.get("delegation_metadata", {}))
        phase = str(
            delegation.get("cycle_phase", mission.state.current_cycle_phase or "execute")
        ).strip().lower()
        route = _route_row_for_phase(mission, phase, route_rows=route_rows)
        provider = str(route.get("provider", "")).strip().lower()
        model = str(route.get("model", "")).strip()
        role = str(route.get("role", "")).strip().lower()
        if not provider and not model:
            continue
        summary = str(
            result.get("result_summary")
            or result.get("error")
            or result.get("stderr")
            or result.get("stdout")
            or ""
        ).strip()
        if len(summary) > 220:
            summary = summary[:217].rstrip() + "..."
        row = {
            "provider": provider,
            "model": model,
            "role": role,
            "phase": phase,
            "at": str(entry.get("executed_at", "") or ""),
            "source": "action_history",
            "summary": summary,
        }
        if bool(result.get("ok")):
            if not success:
                success = row
        elif not failure:
            failure = row
        if success and failure:
            break
    return success, failure


def _provider_truth_for_mission(
    mission: Mission,
    *,
    auth_presence: dict[str, bool],
    workspace: WorkspaceProfile | None = None,
) -> dict:
    phase = str(mission.state.current_cycle_phase or "execute").strip().lower()
    route_rows = _route_rows_for_mission(mission)
    active_route = _route_row_for_phase(mission, phase, route_rows=route_rows)
    active_provider = str(active_route.get("provider", "")).strip().lower()
    active_model = str(active_route.get("model", "")).strip()
    active_auth = _provider_auth_truth(
        active_provider,
        auth_presence=auth_presence,
        workspace=workspace,
    )
    auth_present = bool(active_auth.get("authPresent"))
    auth_mode = str(active_auth.get("authMode") or "")
    auth_path = str(active_auth.get("authPath") or "")
    route_auth: dict[str, dict] = {}
    for route in [*route_rows, active_route]:
        if not isinstance(route, dict):
            continue
        provider = str(route.get("provider", "")).strip().lower()
        if not provider or provider in route_auth:
            continue
        route_auth[provider] = _provider_auth_truth(
            provider,
            auth_presence=auth_presence,
            workspace=workspace,
        )
    last_success, last_failure = _provider_truth_from_action_history(
        mission,
        route_rows=route_rows,
    )
    if not last_failure:
        for session in reversed(mission.delegated_runtime_sessions or []):
            if hasattr(session, "__dataclass_fields__"):
                row = asdict(session)
            elif isinstance(session, dict):
                row = dict(session)
            else:
                continue
            status = str(row.get("status", "")).strip().lower()
            if status not in {"failed", "stopped"}:
                continue
            provider = str(row.get("target_provider", active_provider)).strip().lower()
            model = str(row.get("target_model", active_model)).strip()
            if not provider and not model:
                continue
            last_failure = {
                "provider": provider,
                "model": model,
                "role": str(row.get("target_role", _route_role_for_phase(phase))).strip().lower(),
                "phase": str(row.get("target_phase", phase)).strip().lower(),
                "at": str(row.get("updated_at", "") or ""),
                "source": "delegated_runtime",
                "summary": str(row.get("last_event") or row.get("detail") or "").strip(),
            }
            break

    updated_at_candidates = [
        str(mission.updated_at or ""),
        str(last_success.get("at", "") or "") if isinstance(last_success, dict) else "",
        str(last_failure.get("at", "") or "") if isinstance(last_failure, dict) else "",
    ]
    truth_updated_at = max(
        (value for value in updated_at_candidates if value),
        default=str(mission.updated_at or ""),
    )

    return {
        "currentPhase": phase or "execute",
        "activeRoute": {
            "role": str(active_route.get("role", "")).strip().lower(),
            "provider": active_provider,
            "model": active_model,
            "effort": str(active_route.get("effort", "")).strip().lower(),
            "budgetClass": str(active_route.get("budgetClass", "")).strip(),
            "source": str(active_route.get("source", "")).strip(),
            "taskType": str(active_route.get("taskType", "general_coding")).strip(),
            "routeIntent": str(active_route.get("routeIntent", "")).strip(),
            "fitScore": int(active_route.get("fitScore", 0) or 0),
            "outcomeSampleCount": int(active_route.get("outcomeSampleCount", 0) or 0),
            "outcomeSuccessRate": int(active_route.get("outcomeSuccessRate", 0) or 0),
            "outcomeTrend": str(active_route.get("outcomeTrend", "")).strip(),
        },
        "authPresent": auth_present,
        "authKnown": bool(active_provider),
        "authMode": auth_mode,
        "authPath": auth_path,
        "routeAuth": route_auth,
        "lastSuccessfulCall": last_success,
        "lastFailure": last_failure,
        "updatedAt": truth_updated_at,
    }


def _provider_auth_truth(
    provider: str,
    *,
    auth_presence: dict[str, bool],
    workspace: WorkspaceProfile | None = None,
) -> dict:
    normalized = str(provider or "").strip().lower()
    openai_auth_mode = normalize_openai_codex_auth_mode(
        getattr(workspace, "openai_codex_auth_mode", "none")
    )
    minimax_auth_mode = normalize_minimax_auth_mode(
        getattr(workspace, "minimax_auth_mode", "none")
    )
    if normalized in {"openai", "openai-codex"}:
        api_key_present = bool(auth_presence.get("openai", False))
        oauth_present = bool(auth_presence.get("openai-codex", False))
        auth_present = (
            (openai_auth_mode == "api" and api_key_present)
            or (openai_auth_mode == "oauth" and oauth_present)
            or api_key_present
            or oauth_present
        )
        auth_mode = (
            openai_auth_mode
            if openai_auth_mode != "none"
            else ("api" if api_key_present else ("oauth" if oauth_present else "none"))
        )
        return {
            "provider": normalized,
            "authPresent": auth_present,
            "authMode": auth_mode,
            "authPath": openai_codex_auth_label(auth_mode),
        }
    if normalized in {"minimax", "minimax-portal", "minimax-cn", "minimax-oauth"}:
        oauth_present = bool(
            auth_presence.get("minimax-portal", False)
            or auth_presence.get("minimax-oauth", False)
        )
        raw_api_key_present = bool(
            str(os.environ.get("MINIMAX_API_KEY", "")).strip()
            or str(os.environ.get("MINIMAX_CN_API_KEY", "")).strip()
        )
        api_key_present = bool(
            raw_api_key_present
            or (
                (
                    auth_presence.get("minimax", False)
                    or auth_presence.get("minimax-cn", False)
                )
                and not oauth_present
            )
        )
        auth_present = (
            (minimax_auth_mode == "minimax-api" and api_key_present)
            or (minimax_auth_mode == "minimax-portal-oauth" and oauth_present)
            or api_key_present
            or oauth_present
        )
        auth_mode = (
            minimax_auth_mode
            if minimax_auth_mode != "none"
            else (
                "minimax-api"
                if api_key_present
                else ("minimax-portal-oauth" if oauth_present else "none")
            )
        )
        return {
            "provider": normalized,
            "authPresent": auth_present,
            "authMode": auth_mode,
            "authPath": minimax_auth_label(auth_mode),
        }
    return {
        "provider": normalized,
        "authPresent": bool(auth_presence.get(normalized, False)) if normalized else False,
        "authMode": "",
        "authPath": "" if normalized else "not configured",
    }


def _effective_route_contract_for_mission(mission: Mission) -> dict:
    route_rows = []
    for item in mission.route_configs or []:
        route = dict(item) if isinstance(item, dict) else asdict(item)
        role = str(route.get("role", "")).strip().lower()
        if role not in ROUTE_OVERRIDE_ROLES:
            continue
        explanation = str(route.get("explanation", "") or "")
        source = (
            "override"
            if "override" in explanation.lower()
            else ("strategy" if "strategy" in explanation.lower() else "profile_default")
        )
        route_rows.append(
            {
                "role": role,
                "provider": route.get("provider", ""),
                "model": route.get("model", ""),
                "effort": route.get("effort", "medium"),
                "budgetClass": route.get("budget_class", route.get("budgetClass", "")),
                "fallbackPolicy": route.get("fallback_policy", route.get("fallbackPolicy", "same_provider")),
                "source": source,
                "reason": explanation,
                "taskType": route.get("task_type", route.get("taskType", "general_coding")),
                "routeIntent": route.get("route_intent", route.get("routeIntent", "")),
                "fitScore": route.get("fit_score", route.get("fitScore", 0)),
                "outcomeSampleCount": route.get(
                    "outcome_sample_count",
                    route.get("outcomeSampleCount", 0),
                ),
                "outcomeSuccessRate": route.get(
                    "outcome_success_rate",
                    route.get("outcomeSuccessRate", 0),
                ),
                "outcomeTrend": route.get("outcome_trend", route.get("outcomeTrend", "")),
            }
        )
    if route_rows:
        summary = " | ".join(
            [
                f"{row['role']}: {row['provider']}:{row['model']} ({row['source']})"
                for row in route_rows
            ]
        )
    else:
        summary = "No route contract resolved yet."
    return {
        "roles": route_rows,
        "resolutionOrder": "override > strategy > profile_default",
        "whyThisRoute": summary,
        "fallbackPolicy": "same_provider",
    }


def _reconcile_mission_route_policy(
    mission: Mission,
    workspace: WorkspaceProfile | None,
) -> bool:
    if workspace is None:
        return False
    workspace_routes = {
        str(item.get("role") or "").strip().lower(): item
        for item in normalize_route_overrides(getattr(workspace, "route_overrides", []))
    }
    if not workspace_routes:
        return False
    current_routes = [
        dict(item) if isinstance(item, dict) else asdict(item)
        for item in (mission.route_configs or [])
        if isinstance(item, dict) or hasattr(item, "__dataclass_fields__")
    ]
    changed = False
    by_role: dict[str, dict] = {}
    for route in current_routes:
        role = str(route.get("role") or "").strip().lower()
        if role:
            by_role.setdefault(role, route)
    for role, workspace_route in workspace_routes.items():
        current = by_role.get(role)
        if current is None:
            current = {
                "role": role,
                "explanation": "Route override from workspace runtime contract.",
                "fallback_policy": "same_provider",
            }
            current_routes.append(current)
            by_role[role] = current
            changed = True
        if not _route_is_workspace_managed(current):
            continue
        changed = _copy_workspace_route_fields(current, workspace_route) or changed
    if not changed:
        return False
    mission.route_configs = current_routes
    mission.effective_route_contract = _effective_route_contract_for_mission(mission)
    if mission.effective_route_contract:
        mission.effective_route_contract.setdefault("mutationReceipts", [])
        mission.effective_route_contract["mutationReceipts"].append(
            {
                "receiptId": f"route_policy_reconciled:{utc_now_iso()}",
                "reason": "Workspace route policy superseded a stale mission runtime contract.",
                "source": "workspace_route_overrides",
            }
        )
    return True


def _route_is_workspace_managed(route: dict) -> bool:
    reason = " ".join(
        [
            str(route.get("explanation") or ""),
            str(route.get("reason") or ""),
            str(route.get("route_intent") or route.get("routeIntent") or ""),
        ]
    ).lower()
    return (
        not reason
        or "workspace runtime contract" in reason
        or "workspace route policy" in reason
        or "manual_workspace_override" in reason
        or "route override" in reason
    )


def _copy_workspace_route_fields(current: dict, workspace_route: dict) -> bool:
    changed = False
    fields_to_copy = {
        "provider": "provider",
        "model": "model",
        "effort": "effort",
        "budgetClass": "budget_class",
    }
    for source_key, target_key in fields_to_copy.items():
        value = str(workspace_route.get(source_key) or "").strip()
        if not value:
            continue
        if str(current.get(target_key, current.get(source_key, "")) or "").strip() == value:
            continue
        current[target_key] = value
        if target_key != source_key:
            current.pop(source_key, None)
        changed = True
    fallback_policy = str(
        workspace_route.get("fallbackPolicy")
        or workspace_route.get("fallback_policy")
        or ""
    ).strip()
    if fallback_policy and current.get("fallback_policy") != fallback_policy:
        current["fallback_policy"] = fallback_policy
        changed = True
    current.setdefault("explanation", "Route override from workspace runtime contract.")
    return changed


def refresh_mission_runtime_state(
    mission: Mission,
    refreshed_sessions: list[DelegatedRuntimeSession],
) -> None:
    prompts = [
        item.pending_approval.get("prompt", "Delegated approval required.")
        for item in refreshed_sessions
        if item.status == "waiting_for_approval"
    ]
    approval_payload = next(
        (dict(item.pending_approval) for item in refreshed_sessions if item.pending_approval),
        {},
    )
    approval_history = [
        entry
        for session in refreshed_sessions
        for entry in session.approval_history
        if isinstance(entry, dict)
    ]

    mission.state.pending_approval_payload = approval_payload
    mission.state.approval_history = approval_history[-8:]
    if not prompts:
        mission.proof.pending_approvals = []
    if refreshed_sessions:
        mission.state.last_runtime_event = (
            refreshed_sessions[-1].last_event or mission.state.last_runtime_event
        )

    if prompts:
        mission.state.status = "needs_approval"
        mission.proof.summary = prompts[0]
        mission.proof.pending_approvals = prompts
    elif any(item.status in {"launching", "running"} for item in refreshed_sessions):
        mission.state.status = "running"
        mission.proof.summary = (
            "Delegated runtime lane is active. Fluxio will continue when it finishes."
        )

    continuity_state, continuity_detail = _continuity_state_for_mission(mission, refreshed_sessions)
    mission.state.continuity_state = continuity_state
    mission.state.continuity_detail = continuity_detail


def _approval_receipt_key(mission: Mission) -> str:
    payload = mission.state.pending_approval_payload or {}
    raw_key = (
        payload.get("approval_id")
        or payload.get("approvalId")
        or payload.get("action_id")
        or payload.get("actionId")
        or payload.get("prompt")
        or mission.proof.summary
        or mission.mission_id
    )
    return str(raw_key)[:240]


def _maybe_send_approval_receipt(mission: Mission, root: Path) -> bool:
    if mission.state.status != "needs_approval":
        return False
    if not mission.state.pending_approval_payload:
        return False
    receipt_key = _approval_receipt_key(mission)
    existing = mission.escalation_policy.delivery_receipts or []
    if any(str(item.get("approvalKey") or "") == receipt_key for item in existing if isinstance(item, dict)):
        return False

    payload = mission.state.pending_approval_payload
    prompt = str(payload.get("prompt") or mission.proof.summary or "Approval required.")
    risk_level = str(payload.get("risk_level") or payload.get("riskLevel") or "medium")
    receipt = send_approval_escalation_receipt(
        mission_id=mission.mission_id,
        prompt=prompt,
        risk_level=risk_level,
        escalation_policy=asdict(mission.escalation_policy),
        root=root,
        dry_run=os.environ.get("FLUXIO_DELIVERY_RECEIPT_DRY_RUN", "0") == "1",
    )
    mission.escalation_policy.delivery_receipts = (
        existing
        + [
            {
                "approvalKey": receipt_key,
                "receiptId": receipt.receipt_id,
                "status": receipt.status,
                "channel": receipt.channel,
                "sentAt": receipt.sent_at,
                "error": receipt.error_message,
            }
        ]
    )[-20:]
    mission.escalation_policy.last_sent_at = receipt.sent_at
    mission.escalation_policy.last_error = receipt.error_message or None
    return True


def normalize_action_history(action_history: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for item in action_history or []:
        record = dict(item)
        proposal = dict(record.get("proposal", {}))
        source_kind = proposal.get("sourceKind") or _infer_action_source_kind(proposal)
        proposal["sourceKind"] = source_kind
        result = dict(record.get("result", {}))
        result.setdefault("sourceKind", source_kind)
        record["proposal"] = proposal
        record["result"] = result
        normalized.append(record)
    return normalized


def _infer_action_source_kind(proposal: dict) -> str:
    if proposal.get("delegation_metadata"):
        return "delegated"
    if proposal.get("kind") in {
        "runtime_delegate",
        "delegated_runtime",
        "delegated_action",
    }:
        return "delegated"
    return "local"


def _continuity_state_for_mission(
    mission: Mission,
    delegated: list[DelegatedRuntimeSession],
) -> tuple[str, str]:
    if mission.state.status in TERMINAL_MISSION_STATUSES:
        return "terminal", "Mission is in a terminal state with recorded proof."
    if any(item.status == "waiting_for_approval" for item in delegated):
        prompt = next(
            (
                item.pending_approval.get("prompt", "Delegated runtime is paused on approval.")
                for item in delegated
                if item.status == "waiting_for_approval"
            ),
            "Delegated runtime is paused on approval.",
        )
        return "approval_waiting", prompt
    if any(item.status in {"launching", "running"} for item in delegated):
        runtime_id = next(
            (item.runtime_id for item in delegated if item.status in {"launching", "running"}),
            mission.runtime_id,
        )
        return "delegated_active", f"{runtime_id} lane is still active and restart-safe."
    if any(item.status in {"completed", "failed"} and not item.acknowledged for item in delegated):
        return (
            "resume_available",
            "A delegated lane finished while Fluxio was away. Resume once to reconcile proof and planning state.",
        )
    if mission.state.latest_session_id and mission.state.status not in TERMINAL_MISSION_STATUSES:
        return "resume_available", "Mission can resume safely from the last recorded session."
    return "fresh_only", "No resumable mission continuity has been recorded yet."


def _verification_summary_for_mission(mission: Mission, verification_result: str) -> str:
    if verification_result == "failed":
        failed = mission.proof.failed_checks or mission.state.verification_failures
        return f"Failed: {', '.join(failed[:2])}" if failed else "Verification failed."
    if verification_result == "passed":
        passed_count = len(mission.proof.passed_checks)
        return f"Passed {passed_count} verification check(s)."
    return "Verification is still pending."


def _parse_iso_datetime(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def mission_time_budget_window(
    mission: Mission,
    now: datetime | None = None,
) -> dict:
    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    started_at = _parse_iso_datetime(mission.created_at) or current_time
    elapsed_seconds = max(0, round((current_time - started_at).total_seconds()))

    deadline_at = _parse_iso_datetime(mission.run_budget.deadline_at)
    max_runtime_seconds = max(0, int(mission.run_budget.max_runtime_seconds or 0))
    if deadline_at is not None:
        max_runtime_seconds = max(
            0,
            round((deadline_at - started_at).total_seconds()),
        )
        remaining_seconds = max(
            0,
            round((deadline_at - current_time).total_seconds()),
        )
    else:
        remaining_seconds = max(0, max_runtime_seconds - elapsed_seconds)

    return {
        "startedAt": started_at.isoformat(),
        "deadlineAt": deadline_at.isoformat() if deadline_at is not None else None,
        "maxRuntimeSeconds": max_runtime_seconds,
        "elapsedSeconds": elapsed_seconds,
        "remainingSeconds": remaining_seconds,
    }


def _time_budget_snapshot_for_mission(mission: Mission) -> dict:
    delegated = mission.delegated_runtime_sessions or []
    budget_window = mission_time_budget_window(mission)
    elapsed_seconds = int(budget_window["elapsedSeconds"])
    max_runtime_seconds = int(budget_window["maxRuntimeSeconds"])
    remaining_seconds = int(budget_window["remainingSeconds"])
    pause_reason = _pause_reason_for_mission(mission, delegated)

    if mission.state.status in TERMINAL_MISSION_STATUSES:
        status = mission.state.status
    elif pause_reason == "runtime_budget":
        status = "budget_exhausted"
    elif mission.state.status == "needs_approval":
        status = "paused_for_approval"
    elif pause_reason in {"verification_failed", "verification_failure"} or mission.state.status == "verification_failed":
        status = "paused_for_verification"
    elif mission.state.status == "blocked":
        status = "paused"
    elif mission.state.status == "queued":
        status = "queued"
    elif any(item.status in {"launching", "running"} for item in delegated):
        status = "delegated_active"
    elif mission.state.status == "running":
        status = "running"
    else:
        status = "pending"

    return {
        "mode": mission.run_budget.mode,
        "runUntilBehavior": mission.run_budget.run_until_behavior,
        "focusWindowHours": mission.run_budget.focus_window_hours,
        "deadlineAt": budget_window["deadlineAt"],
        "maxRuntimeSeconds": max_runtime_seconds,
        "budgetHours": round(max_runtime_seconds / 3600, 2) if max_runtime_seconds else 0,
        "elapsedSeconds": elapsed_seconds,
        "remainingSeconds": remaining_seconds,
        "status": status,
        "lastPauseReason": pause_reason,
    }


def _pause_reason_for_mission(
    mission: Mission,
    delegated: list[DelegatedRuntimeSession],
) -> str:
    if mission.state.status in TERMINAL_MISSION_STATUSES:
        return ""
    waiting_session = next(
        (item for item in delegated if item.status == "waiting_for_approval"),
        None,
    )
    if waiting_session is not None:
        return waiting_session.pending_approval.get(
            "prompt",
            "Delegated runtime is paused on approval.",
        )

    raw_reason = mission.state.stop_reason or ""
    if not raw_reason and mission.state.status in {
        "queued",
        "blocked",
        "needs_approval",
        "verification_failed",
    }:
        raw_reason = mission.state.last_budget_pause_reason or ""
    if raw_reason == "runtime_budget":
        return "Runtime budget exhausted."
    if raw_reason in {"verification_failed", "verification_failure"} or mission.state.status == "verification_failed":
        summary = mission.state.last_verification_summary or _verification_summary_for_mission(mission, "failed")
        return summary or "Verification failed."
    if raw_reason == "approval_required":
        return "Operator approval is required before Fluxio can continue."
    if raw_reason == "delegated_runtime_running":
        return "Delegated runtime lane is still active and restart-safe."
    if raw_reason:
        return raw_reason

    if any(item.status in {"launching", "running"} for item in delegated):
        return "Delegated runtime lane is still active and restart-safe."
    if mission.state.status == "queued":
        if mission.state.queue_position > 0:
            return mission.state.queue_reason or "Mission is queued behind another active mission."
        return "Mission is queued and ready to start."
    if mission.state.status == "blocked":
        return mission.state.last_error or "Mission is paused and needs operator attention."
    return ""


def _current_runtime_lane_for_mission(
    mission: Mission,
    delegated: list[DelegatedRuntimeSession],
) -> str:
    if mission.state.status in TERMINAL_MISSION_STATUSES:
        return f"{mission.runtime_id} primary lane {mission.state.status.replace('_', ' ')}"
    for item in delegated:
        if item.status in {"waiting_for_approval", "launching", "running"}:
            return f"{item.runtime_id} delegated lane {item.status.replace('_', ' ')}"
    if delegated:
        latest = delegated[-1]
        return f"{latest.runtime_id} delegated lane {latest.status.replace('_', ' ')}"
    return f"{mission.runtime_id} primary lane {mission.state.status.replace('_', ' ')}"


def _inspect_workspace_git(
    workspace_root: Path,
    commit_message_style: str = "scoped",
) -> dict:
    snapshot = {
        "repoDetected": False,
        "branch": "",
        "trackingBranch": "",
        "dirty": False,
        "stagedCount": 0,
        "unstagedCount": 0,
        "untrackedCount": 0,
        "ahead": 0,
        "behind": 0,
        "changedFiles": [],
        "suggestedCommitMessage": "",
        "remotes": [],
        "deployTarget": {
            "provider": "",
            "available": False,
            "configured": False,
            "requiresApproval": True,
            "detail": "No deploy target detected.",
        },
        "detail": "",
    }
    if not workspace_root.exists():
        snapshot["detail"] = "Workspace path does not exist."
        return snapshot

    git_probe = _run_git_command(workspace_root, ["rev-parse", "--is-inside-work-tree"])
    if git_probe["return_code"] != 0 or git_probe["stdout"].strip() != "true":
        snapshot["detail"] = "No Git repository detected for this workspace."
        return snapshot

    snapshot["repoDetected"] = True
    status_output = _run_git_command(workspace_root, ["status", "--porcelain=1", "--branch"])
    lines = [line for line in status_output["stdout"].splitlines() if line.strip()]
    if lines and lines[0].startswith("## "):
        snapshot.update(_parse_branch_status(lines[0][3:]))
        lines = lines[1:]

    for line in lines:
        code = line[:2]
        path_text = _parse_git_status_path(line)
        if path_text and path_text not in snapshot["changedFiles"]:
            snapshot["changedFiles"].append(path_text)
        if code.startswith("??"):
            snapshot["untrackedCount"] += 1
            continue
        if code[:1] not in {" ", "?"}:
            snapshot["stagedCount"] += 1
        if code[1:2] not in {" ", "?"}:
            snapshot["unstagedCount"] += 1
    snapshot["dirty"] = (
        snapshot["stagedCount"] > 0
        or snapshot["unstagedCount"] > 0
        or snapshot["untrackedCount"] > 0
    )

    remotes = []
    remotes_output = _run_git_command(workspace_root, ["remote", "-v"])
    seen = set()
    for line in remotes_output["stdout"].splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        name, url, kind = parts[0], parts[1], parts[2].strip("()")
        key = (name, url)
        if kind != "push" or key in seen:
            continue
        seen.add(key)
        remotes.append({"name": name, "url": url})
    snapshot["remotes"] = remotes
    snapshot["deployTarget"] = _infer_deploy_target(workspace_root, remotes)
    snapshot["detail"] = (
        f"{snapshot['branch'] or 'Detached HEAD'} · "
        f"{'dirty' if snapshot['dirty'] else 'clean'} · "
        f"{len(remotes)} remote(s)"
    )
    snapshot["suggestedCommitMessage"] = _build_generated_commit_message(
        snapshot,
        commit_message_style,
    )
    return snapshot


def _run_git_command(workspace_root: Path, args: list[str]) -> dict:
    try:
        completed = subprocess.run(  # noqa: S603
            ["git", *args],
            cwd=str(workspace_root),
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except OSError:
        return {"return_code": 1, "stdout": "", "stderr": "git unavailable"}
    return {
        "return_code": completed.returncode,
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
    }


def _parse_branch_status(branch_line: str) -> dict:
    branch = branch_line
    tracking = ""
    ahead = 0
    behind = 0
    if "..." in branch_line:
        branch, rest = branch_line.split("...", 1)
        tracking = rest.split(" [", 1)[0].strip()
    match = re.search(r"\[(.*?)\]$", branch_line)
    if match:
        parts = [item.strip() for item in match.group(1).split(",")]
        for part in parts:
            if part.startswith("ahead "):
                ahead = int(part.split(" ", 1)[1])
            elif part.startswith("behind "):
                behind = int(part.split(" ", 1)[1])
    return {
        "branch": branch.strip(),
        "trackingBranch": tracking,
        "ahead": ahead,
        "behind": behind,
    }


def _parse_git_status_path(line: str) -> str:
    payload = line[3:].strip()
    if " -> " in payload:
        payload = payload.split(" -> ", 1)[1].strip()
    return payload


def _normalize_commit_subject_token(value: str) -> str:
    cleaned = re.sub(r"[_\-]+", " ", value)
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def _build_generated_commit_message(
    git_snapshot: dict,
    style: str = "scoped",
) -> str:
    if not git_snapshot.get("dirty"):
        return ""
    changed_files = git_snapshot.get("changedFiles", [])
    labels: list[str] = []
    for path_text in changed_files[:4]:
        path = Path(path_text)
        token = _normalize_commit_subject_token(path.stem or path.name or path_text)
        if token and token not in labels:
            labels.append(token)
    normalized_style = (style or "scoped").strip().lower()
    if normalized_style == "concise":
        if labels:
            return f"Update {labels[0]}"
        return "Update workspace state"
    if normalized_style == "detailed":
        branch = git_snapshot.get("branch") or "workspace"
        if len(labels) == 1:
            return f"Update {labels[0]} on {branch}"
        if len(labels) == 2:
            return f"Update {labels[0]} and {labels[1]} on {branch}"
        if len(labels) >= 3:
            return f"Update {labels[0]}, {labels[1]}, and related files on {branch}"
        return f"Update workspace state on {branch}"
    if len(labels) == 1:
        return f"Update {labels[0]}"
    if len(labels) == 2:
        return f"Update {labels[0]} and {labels[1]}"
    if len(labels) >= 3:
        return f"Update {labels[0]}, {labels[1]}, and related files"
    return "Update workspace state"


def _infer_deploy_target(
    workspace_root: Path,
    remotes: list[dict],
) -> dict:
    remote_urls = [item["url"] for item in remotes]
    github_remote = next((url for url in remote_urls if "github.com" in url.lower()), "")
    pages_workflow = workspace_root / ".github" / "workflows"
    has_pages_workflow = pages_workflow.exists() and any(
        "pages" in child.name.lower() for child in pages_workflow.glob("*.y*ml")
    )
    if github_remote:
        return {
            "provider": "github_pages",
            "available": True,
            "configured": has_pages_workflow,
            "requiresApproval": True,
            "detail": (
                "GitHub remote detected. Offer approval-gated push or Pages deployment actions."
                if has_pages_workflow
                else "GitHub remote detected. Pages can be scaffolded after explicit approval."
            ),
        }
    return {
        "provider": "",
        "available": False,
        "configured": False,
        "requiresApproval": True,
        "detail": "No GitHub remote detected yet.",
    }


def _build_git_actions(git_snapshot: dict, profile_parameters: dict) -> list[dict]:
    if not git_snapshot.get("repoDetected"):
        return []
    approval_required = profile_parameters.get("gitActionPolicy", "approval_gated") != "profile_resolved"
    tracking_branch = str(git_snapshot.get("trackingBranch") or "").strip()
    ahead = int(git_snapshot.get("ahead") or 0)
    behind = int(git_snapshot.get("behind") or 0)
    suggested_commit_message = str(
        git_snapshot.get("suggestedCommitMessage") or "Update workspace state"
    ).replace('"', "")
    actions = [
        {
            "actionId": "inspect_repo_state",
            "label": "Inspect repository state",
            "command": "git status --short --branch",
            "commandSurface": "git.inspect",
            "requiresApproval": False,
            "detail": "Review branch, changes, and ahead/behind before mutating actions.",
        }
    ]
    if tracking_branch:
        detail = f"Fast-forward only pull from {tracking_branch}."
        if behind > 0:
            detail = f"{behind} remote commit(s) are waiting on {tracking_branch}. Pull fast-forward only."
        elif ahead > 0:
            detail = (
                f"Branch is ahead of {tracking_branch}. Pull stays fast-forward only before pushing."
            )
        actions.append(
            {
                "actionId": "pull_branch",
                "label": "Pull tracked branch",
                "command": "git pull --ff-only",
                "commandSurface": "git.pull",
                "requiresApproval": approval_required,
                "detail": detail,
            }
        )
    if git_snapshot.get("dirty"):
        actions.append(
            {
                "actionId": "commit_changes",
                "label": "Commit with generated message",
                "command": f'git add -A && git commit -m "{suggested_commit_message}"',
                "commandSurface": "git.commit",
                "requiresApproval": True,
                "detail": (
                    f'Fluxio stages all current changes and commits them with "{suggested_commit_message}".'
                ),
                "generatedMessage": suggested_commit_message,
            }
        )
    if git_snapshot.get("remotes"):
        actions.append(
            {
                "actionId": "push_branch",
                "label": "Push current branch",
                "command": "git push",
                "commandSurface": "git.push",
                "requiresApproval": approval_required,
                "detail": "Policy-resolved push action. Approval stays on by default.",
            }
        )
    deploy_target = git_snapshot.get("deployTarget", {})
    if deploy_target.get("available"):
        actions.append(
            {
                "actionId": "deploy_pages",
                "label": "Publish deploy target",
                "command": "git push origin HEAD",
                "commandSurface": "deploy.pages",
                "requiresApproval": True,
                "detail": deploy_target.get("detail", "Deploy target is available."),
            }
        )
    return actions


def _build_validation_actions(workspace_root: Path) -> list[dict]:
    verification_commands = detect_default_verification_commands(workspace_root)
    if not verification_commands:
        return []
    joined_command = " && ".join(verification_commands)
    detail = (
        verification_commands[0]
        if len(verification_commands) == 1
        else f"{verification_commands[0]} then {len(verification_commands) - 1} more verification command(s)."
    )
    return [
        {
            "actionId": "validate_workspace",
            "label": "Validate workspace",
            "command": joined_command,
            "commandSurface": "validate.workspace",
            "requiresApproval": False,
            "detail": f"Run detected verification commands: {detail}",
            "commands": verification_commands,
        }
    ]


def _build_workspace_service_management(
    *,
    setup_health: dict,
    runtime_status: dict | None,
    integration_recommendations: list[dict],
    connected_apps: list[dict],
) -> list[dict]:
    services = {
        item["serviceId"]: dict(item)
        for item in setup_health.get("serviceManagement", [])
        if isinstance(item, dict) and item.get("serviceId")
    }

    if runtime_status:
        runtime_id = runtime_status.get("runtime_id", "")
        existing = services.get(runtime_id, {})
        services[runtime_id] = {
            **existing,
            "serviceId": runtime_id,
            "label": runtime_status.get("label", runtime_id),
            "serviceCategory": "runtime",
            "installSource": existing.get("installSource", "system_path"),
            "currentHealthStatus": (
                "update_available"
                if runtime_status.get("update_available")
                else ("healthy" if runtime_status.get("detected") else "missing")
            ),
            "lastVerificationResult": (
                "outdated"
                if runtime_status.get("update_available")
                else ("passed" if runtime_status.get("detected") else "blocked")
            ),
            "lastRepairAction": existing.get("lastRepairAction", {}),
            "managementMode": existing.get("managementMode", "externally_managed"),
            "version": runtime_status.get("version") or existing.get("version", ""),
            "latestVersion": runtime_status.get("latest_version") or existing.get("latestVersion", ""),
            "updateAvailable": runtime_status.get("update_available", existing.get("updateAvailable", False)),
            "details": runtime_status.get("doctor_summary") or existing.get("details", ""),
            "serviceActions": existing.get("serviceActions", []),
            "verifyAction": existing.get("verifyAction", {}),
        }

    for item in integration_recommendations:
        recommendation_id = item.get("recommendation_id", "")
        if not recommendation_id:
            continue
        services[recommendation_id] = {
            "serviceId": recommendation_id,
            "label": item.get("label", recommendation_id),
            "serviceCategory": "mcp_tool_server",
            "installSource": item.get("command", ""),
            "currentHealthStatus": "recommended",
            "lastVerificationResult": "not_run",
            "lastRepairAction": {},
            "managementMode": "fluxio_managed",
            "version": "",
            "details": item.get("reason", ""),
            "serviceActions": [],
            "verifyAction": {},
        }

    for session in connected_apps:
        app_id = session.get("app_id", "")
        if not app_id:
            continue
        ui_hints = session.get("ui_hints", {}) if isinstance(session.get("ui_hints"), dict) else {}
        bridge_role = str(ui_hints.get("bridgeRole") or "")
        latest_task = session.get("latest_task_result", {})
        latest_payload = latest_task.get("payload", {}) if isinstance(latest_task, dict) else {}
        requires_approval_for_write = bool(
            latest_payload.get("requiresApprovalForWrite", True)
        )
        service_actions = []
        if bridge_role in {"nas_storage", "cloud_storage"}:
            is_cloud = bridge_role == "cloud_storage"
            service_actions = [
                *(
                    [
                        {
                            "actionId": "verify-nas-ssh",
                            "label": "Verify NAS SSH",
                            "description": "Probe the SSH/SFTP NAS route on the configured port without logging secrets.",
                            "commandSurface": "bridge.verify",
                            "requiresApproval": False,
                            "kind": "verify",
                        },
                        {
                            "actionId": "unlock-codex-network",
                            "label": "Unlock local network rule",
                            "description": "Disable the local Codex outbound firewall block through an elevated PowerShell prompt, then retry the NAS SSH route.",
                            "commandSurface": "bridge.activate",
                            "requiresApproval": True,
                            "kind": "repair",
                        }
                    ]
                    if (
                        not is_cloud
                        and latest_payload.get("selectedHost")
                        and latest_payload.get("sshUser")
                    )
                    else []
                ),
                *(
                    [
                        {
                            "actionId": "activate-nas-mapping",
                            "label": "Activate NAS mapping",
                            "description": "Run the Core/Cowork Synology mapper so the NAS project drive is available.",
                            "commandSurface": "bridge.activate",
                            "requiresApproval": True,
                            "kind": "activate",
                        }
                    ]
                    if (not is_cloud and latest_payload.get("activationCommand"))
                    else []
                ),
                {
                    "actionId": "monitor-cloud-drive" if is_cloud else "monitor-fast-sync",
                    "label": "Monitor bridge",
                    "description": (
                        "Read the latest cloud-drive bridge status from the connected app."
                        if is_cloud
                        else "Read the latest computer/NAS bridge status from the connected app."
                    ),
                    "commandSurface": "bridge.status",
                    "requiresApproval": False,
                    "kind": "status",
                },
                {
                    "actionId": "queue-cloud-drive-transfer" if is_cloud else "start-sync-selection",
                    "label": "Queue transfer",
                    "description": (
                        "Queue an upload or download through the cloud-drive bridge after preview."
                        if is_cloud
                        else (
                            "Queue an upload or download through the NAS bridge after preview."
                            if requires_approval_for_write
                            else "Run an upload or download through the NAS bridge immediately."
                        )
                    ),
                    "commandSurface": "bridge.sync",
                    "requiresApproval": requires_approval_for_write,
                    "kind": "sync",
                },
            ]
        services[app_id] = {
            "serviceId": app_id,
            "label": session.get("app_name", app_id),
            "serviceCategory": "connected_app_bridge",
            "serviceRole": bridge_role or "app_bridge",
            "installSource": session.get("bridge_transport", "") or "bridge_manifest",
            "currentHealthStatus": session.get("bridge_health", session.get("status", "unknown")),
            "lastVerificationResult": (
                "passed" if session.get("status") == "connected" else session.get("status", "unknown")
            ),
            "lastRepairAction": {},
            "managementMode": "externally_managed",
            "version": "",
            "details": latest_task.get("resultSummary", "") if isinstance(latest_task, dict) else "",
            "sourceRoot": latest_payload.get("sourceRoot", "") if isinstance(latest_payload, dict) else "",
            "targetRoot": latest_payload.get("targetRoot", "") if isinstance(latest_payload, dict) else "",
            "bridgeEndpoint": session.get("bridge_endpoint", ""),
            "serviceActions": service_actions,
            "verifyAction": {},
        }

    return list(services.values())


def _build_storage_bridge_snapshot(connected_apps: list[dict]) -> dict:
    storage_sessions = [
        item
        for item in connected_apps
        if (item.get("ui_hints") or {}).get("bridgeRole") in {"nas_storage", "cloud_storage"}
        or item.get("app_id") in {"synology-fast-sync", "cloud-drive-sync"}
    ]
    nas_sessions = [
        item
        for item in storage_sessions
        if (item.get("ui_hints") or {}).get("bridgeRole") == "nas_storage"
        or item.get("app_id") == "synology-fast-sync"
    ]
    cloud_sessions = [
        item
        for item in storage_sessions
        if (item.get("ui_hints") or {}).get("bridgeRole") == "cloud_storage"
        or item.get("app_id") == "cloud-drive-sync"
    ]
    primary = nas_sessions[0] if nas_sessions else (storage_sessions[0] if storage_sessions else {})
    latest_task = primary.get("latest_task_result", {}) if isinstance(primary, dict) else {}
    payload = latest_task.get("payload", {}) if isinstance(latest_task, dict) else {}
    bridge_plan = payload.get("bridgePlan", {}) if isinstance(payload, dict) else {}
    ui_hints = primary.get("ui_hints", {}) if isinstance(primary, dict) else {}
    ui_hints = ui_hints if isinstance(ui_hints, dict) else {}
    cloud_primary = cloud_sessions[0] if cloud_sessions else {}
    cloud_task = (
        cloud_primary.get("latest_task_result", {})
        if isinstance(cloud_primary, dict)
        else {}
    )
    cloud_payload = cloud_task.get("payload", {}) if isinstance(cloud_task, dict) else {}
    cloud_plan = cloud_payload.get("bridgePlan", {}) if isinstance(cloud_payload, dict) else {}
    return {
        "available": bool(storage_sessions),
        "connected": bool(primary.get("status") == "connected"),
        "sessionCount": len(storage_sessions),
        "primaryAppId": primary.get("app_id", ""),
        "primaryAppName": primary.get("app_name", ""),
        "health": primary.get("bridge_health", "missing") if primary else "missing",
        "endpoint": primary.get("bridge_endpoint", ""),
        "publicEndpoint": (
            payload.get("publicEndpoint") or ui_hints.get("publicEndpoint", "")
            if isinstance(payload, dict)
            else ui_hints.get("publicEndpoint", "")
        ),
        "preferredTransport": (
            payload.get("preferredTransport") or ui_hints.get("preferredTransport", "")
            if isinstance(payload, dict)
            else ui_hints.get("preferredTransport", "")
        ),
        "httpsReady": bool(
            (payload.get("httpsReady") if isinstance(payload, dict) else None)
            or ui_hints.get("httpsReady", False)
        ),
        "sourceRoot": payload.get("sourceRoot", "") if isinstance(payload, dict) else "",
        "targetRoot": payload.get("targetRoot", "") if isinstance(payload, dict) else "",
        "selectedMode": payload.get("selectedMode", "") if isinstance(payload, dict) else "",
        "selectedHost": payload.get("selectedHost", "") if isinstance(payload, dict) else "",
        "controlProtocol": payload.get("controlProtocol", "") if isinstance(payload, dict) else "",
        "controlPort": payload.get("controlPort", 0) if isinstance(payload, dict) else 0,
        "requestedSshPort": payload.get("requestedSshPort", 0) if isinstance(payload, dict) else 0,
        "observedSshPort": payload.get("observedSshPort", 0) if isinstance(payload, dict) else 0,
        "sshPortStatus": payload.get("sshPortStatus", "") if isinstance(payload, dict) else "",
        "sshUser": payload.get("sshUser", "") if isinstance(payload, dict) else "",
        "remoteProjectRoot": payload.get("remoteProjectRoot", "") if isinstance(payload, dict) else "",
        "activeDirection": payload.get("activeDirection", "") if isinstance(payload, dict) else "",
        "safeDirections": payload.get("safeDirections", []) if isinstance(payload, dict) else [],
        "requiresApprovalForWrite": bool(
            payload.get("requiresApprovalForWrite", True) if isinstance(payload, dict) else True
        ),
        "activationRequired": bool(
            payload.get("activationRequired", False) if isinstance(payload, dict) else False
        ),
        "activationProject": payload.get("activationProject", "") if isinstance(payload, dict) else "",
        "activationHint": payload.get("activationHint", "") if isinstance(payload, dict) else "",
        "activationCommand": payload.get("activationCommand", "") if isinstance(payload, dict) else "",
        "writePolicy": bridge_plan.get("writePolicy", "preview_then_approve")
        if isinstance(bridge_plan, dict)
        else "preview_then_approve",
        "conflictPolicy": bridge_plan.get("conflictPolicy", "keep_newer_and_log")
        if isinstance(bridge_plan, dict)
        else "keep_newer_and_log",
        "summary": latest_task.get("resultSummary", "") if isinstance(latest_task, dict) else "",
        "sessions": storage_sessions,
        "nas": {
            "available": bool(nas_sessions),
            "connected": bool(primary.get("status") == "connected"),
            "sessionCount": len(nas_sessions),
            "appId": primary.get("app_id", "") if primary else "",
            "appName": primary.get("app_name", "") if primary else "",
            "health": primary.get("bridge_health", "missing") if primary else "missing",
            "endpoint": primary.get("bridge_endpoint", "") if primary else "",
            "publicEndpoint": (
                payload.get("publicEndpoint") or ui_hints.get("publicEndpoint", "")
                if isinstance(payload, dict)
                else ui_hints.get("publicEndpoint", "")
            ),
            "preferredTransport": (
                payload.get("preferredTransport") or ui_hints.get("preferredTransport", "")
                if isinstance(payload, dict)
                else ui_hints.get("preferredTransport", "")
            ),
            "httpsReady": bool(
                (payload.get("httpsReady") if isinstance(payload, dict) else None)
                or ui_hints.get("httpsReady", False)
            ),
            "sourceRoot": payload.get("sourceRoot", "") if isinstance(payload, dict) else "",
            "targetRoot": payload.get("targetRoot", "") if isinstance(payload, dict) else "",
            "selectedMode": payload.get("selectedMode", "") if isinstance(payload, dict) else "",
            "selectedHost": payload.get("selectedHost", "") if isinstance(payload, dict) else "",
            "controlProtocol": payload.get("controlProtocol", "") if isinstance(payload, dict) else "",
            "controlPort": payload.get("controlPort", 0) if isinstance(payload, dict) else 0,
            "requestedSshPort": payload.get("requestedSshPort", 0) if isinstance(payload, dict) else 0,
            "observedSshPort": payload.get("observedSshPort", 0) if isinstance(payload, dict) else 0,
            "sshPortStatus": payload.get("sshPortStatus", "") if isinstance(payload, dict) else "",
            "sshUser": payload.get("sshUser", "") if isinstance(payload, dict) else "",
            "remoteProjectRoot": payload.get("remoteProjectRoot", "") if isinstance(payload, dict) else "",
            "safeDirections": payload.get("safeDirections", []) if isinstance(payload, dict) else [],
            "activationRequired": bool(
                payload.get("activationRequired", False) if isinstance(payload, dict) else False
            ),
            "activationProject": payload.get("activationProject", "") if isinstance(payload, dict) else "",
            "activationHint": payload.get("activationHint", "") if isinstance(payload, dict) else "",
            "activationCommand": payload.get("activationCommand", "") if isinstance(payload, dict) else "",
            "summary": latest_task.get("resultSummary", "") if isinstance(latest_task, dict) else "",
        },
        "cloud": {
            "available": bool(cloud_sessions),
            "connected": bool(cloud_primary.get("status") == "connected"),
            "sessionCount": len(cloud_sessions),
            "appId": cloud_primary.get("app_id", "") if cloud_primary else "",
            "appName": cloud_primary.get("app_name", "") if cloud_primary else "",
            "health": cloud_primary.get("bridge_health", "missing") if cloud_primary else "missing",
            "endpoint": cloud_primary.get("bridge_endpoint", "") if cloud_primary else "",
            "sourceRoot": cloud_payload.get("sourceRoot", "") if isinstance(cloud_payload, dict) else "",
            "targetRoot": cloud_payload.get("targetRoot", "") if isinstance(cloud_payload, dict) else "",
            "selectedMode": cloud_payload.get("selectedMode", "") if isinstance(cloud_payload, dict) else "",
            "selectedHost": cloud_payload.get("selectedHost", "") if isinstance(cloud_payload, dict) else "",
            "safeDirections": cloud_payload.get("safeDirections", []) if isinstance(cloud_payload, dict) else [],
            "mountedRoots": cloud_payload.get("mountedRoots", []) if isinstance(cloud_payload, dict) else [],
            "googleLoginReady": bool(
                cloud_payload.get("googleLoginReady") if isinstance(cloud_payload, dict) else False
            ),
            "providers": cloud_payload.get("cloudProviders", []) if isinstance(cloud_payload, dict) else [],
            "loginUrl": cloud_plan.get("loginUrl", "https://drive.google.com/drive/my-drive")
            if isinstance(cloud_plan, dict)
            else "https://drive.google.com/drive/my-drive",
            "desktopClientUrl": cloud_plan.get(
                "desktopClientUrl",
                "https://www.google.com/drive/download/",
            )
            if isinstance(cloud_plan, dict)
            else "https://www.google.com/drive/download/",
            "writePolicy": cloud_plan.get("writePolicy", "preview_then_approve")
            if isinstance(cloud_plan, dict)
            else "preview_then_approve",
            "conflictPolicy": cloud_plan.get("conflictPolicy", "keep_newer_and_log")
            if isinstance(cloud_plan, dict)
            else "keep_newer_and_log",
            "summary": cloud_task.get("resultSummary", "") if isinstance(cloud_task, dict) else "",
        },
    }


def _service_management_summary(items: list[dict]) -> dict[str, int]:
    healthy_statuses = {"healthy", "connected", "ready"}
    return {
        "totalItems": len(items),
        "healthyCount": sum(
            1 for item in items if item.get("currentHealthStatus") in healthy_statuses
        ),
        "needsAttentionCount": sum(
            1 for item in items if item.get("currentHealthStatus") not in healthy_statuses
        ),
        "runtimeCount": sum(1 for item in items if item.get("serviceCategory") == "runtime"),
        "toolServerCount": sum(
            1 for item in items if item.get("serviceCategory") == "mcp_tool_server"
        ),
        "bridgeCount": sum(
            1 for item in items if item.get("serviceCategory") == "connected_app_bridge"
        ),
    }


def _default_workflow_verification(selected_workspace: dict) -> list[str]:
    workspace_type = selected_workspace.get("workspace_type", "")
    commands: list[str] = []
    if "python" in workspace_type:
        commands.append("python -m pytest tests -q")
    if "node" in workspace_type or "tauri" in workspace_type or "web" in workspace_type:
        commands.append("npm run frontend:build")
    if "tauri" in workspace_type:
        commands.append("npm run tauri build -- --debug")
    return commands


def _build_workflow_studio(
    workspaces: list[dict],
    missions: list[dict],
    setup_health: dict,
    skill_catalog: dict,
) -> dict:
    selected_workspace = workspaces[0] if workspaces else {}
    git_snapshot = selected_workspace.get("gitSnapshot", {})
    verification_defaults = _default_workflow_verification(selected_workspace)
    recommended_skill_ids = [
        item.get("packId") or item.get("pack_id") or item.get("skillId") or item.get("skill_id")
        for item in skill_catalog.get("recommendedPacks", [])
        if item.get("packId") or item.get("pack_id") or item.get("skillId") or item.get("skill_id")
    ]
    managed_service_ids = [
        item.get("serviceId")
        for item in selected_workspace.get("serviceManagement", [])
        if item.get("managementMode") == "fluxio_managed" and item.get("serviceId")
    ]
    bridge_service_ids = [
        item.get("serviceId")
        for item in selected_workspace.get("serviceManagement", [])
        if item.get("serviceCategory") == "connected_app_bridge" and item.get("serviceId")
    ]
    setup_blockers = [
        item.get("serviceId")
        for item in setup_health.get("serviceManagement", [])
        if item.get("currentHealthStatus") != "healthy" and item.get("serviceId")
    ]
    recipes = [
        {
            "workflowId": "agent_long_run",
            "label": "Long-Run Agent Session",
            "description": "Leave Fluxio to plan, execute, verify, and replan over many hours with approvals and proof kept visible.",
            "status": "ready" if missions else "available",
            "audience": "all",
            "surface": "agent_view",
            "reviewStatus": "reviewed",
            "runtimeChoice": selected_workspace.get("default_runtime", "openclaw_or_hermes"),
            "skillIds": recommended_skill_ids[:3],
            "serviceIds": managed_service_ids[:4],
            "verificationDefaults": verification_defaults,
        },
        {
            "workflowId": "ui_review_loop",
            "label": "Live UI Review Loop",
            "description": "Use HMR, fixtures, proof, and replay-ready states while refining the desktop workbench.",
            "status": "ready" if selected_workspace else "available",
            "audience": "builder",
            "surface": "builder_view",
            "reviewStatus": "reviewed",
            "runtimeChoice": selected_workspace.get("default_runtime", "openclaw"),
            "skillIds": recommended_skill_ids[:2],
            "serviceIds": [
                item.get("serviceId")
                for item in selected_workspace.get("serviceManagement", [])
                if item.get("serviceCategory") in {"mcp_tool_server", "runtime"}
            ][:4],
            "verificationDefaults": verification_defaults,
        },
        {
            "workflowId": "nas_bridge_run",
            "label": "Computer/NAS Bridge Run",
            "description": "Use a local editable folder with a NAS-backed runtime target, transfer preview, and approval-gated writes.",
            "status": "ready" if bridge_service_ids else "available",
            "audience": "builder",
            "surface": "storage_bridge",
            "reviewStatus": "reviewed",
            "runtimeChoice": selected_workspace.get("default_runtime", "openclaw"),
            "skillIds": recommended_skill_ids[:2],
            "serviceIds": bridge_service_ids[:4],
            "verificationDefaults": verification_defaults,
        },
        {
            "workflowId": "safe_git_push",
            "label": "Safe Push Or Deploy",
            "description": "Inspect repo truth first, then offer profile-resolved push and GitHub Pages actions with approvals.",
            "status": "ready" if git_snapshot.get("repoDetected") else "blocked",
            "audience": "advanced",
            "surface": "builder_view",
            "reviewStatus": "reviewed",
            "runtimeChoice": selected_workspace.get("default_runtime", "openclaw"),
            "skillIds": recommended_skill_ids[:1],
            "serviceIds": managed_service_ids[:2],
            "verificationDefaults": verification_defaults,
        },
        {
            "workflowId": "skill_authoring",
            "label": "Skill And Workflow Authoring",
            "description": "Create a new skill or workflow recipe, test it locally, and keep it reviewable inside Fluxio.",
            "status": "ready" if selected_workspace else "available",
            "audience": "builder",
            "surface": "skill_studio",
            "reviewStatus": "reviewed",
            "runtimeChoice": selected_workspace.get("default_runtime", "openclaw"),
            "skillIds": [
                skill_id
                for skill_id in [
                    item.get("skillId") or item.get("skill_id") or item.get("packId")
                    for item in (
                        skill_catalog.get("userInstalledSkills", [])[:2]
                        + skill_catalog.get("learnedSkills", [])[:2]
                    )
                ]
                if skill_id
            ],
            "serviceIds": managed_service_ids[:3],
            "verificationDefaults": verification_defaults,
        },
        {
            "workflowId": "setup_repair",
            "label": "Installer-Grade Setup Repair",
            "description": "Detect missing dependencies, explain blockers, and guide repair actions from inside the app.",
            "status": "blocked" if setup_health.get("missingDependencies") else "ready",
            "audience": "beginner",
            "surface": "setup",
            "reviewStatus": "reviewed",
            "runtimeChoice": selected_workspace.get("default_runtime", "openclaw"),
            "skillIds": [],
            "serviceIds": setup_blockers[:4],
            "verificationDefaults": verification_defaults,
        },
    ]
    learning_queue = []
    for mission in missions:
        for item in mission.get("missionLoop", {}).get("improvementQueue", []):
            learning_queue.append(item)
    return {
        "recipes": recipes,
        "learningQueue": learning_queue[:6],
        "recommendedMode": "agent",
        "managementSummary": {
            "recipeCount": len(recipes),
            "reviewedCount": sum(1 for item in recipes if item.get("reviewStatus") == "reviewed"),
            "blockedCount": sum(1 for item in recipes if item.get("status") == "blocked"),
        },
    }


def _as_mapping(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return {}


def _unique_texts(values: list[object]) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


def _workflow_record_path(root: Path, raw_path: object, *, label: str, source: str) -> dict:
    value = str(raw_path or "").strip()
    if not value:
        return {}
    path = _recover_evidence_path(root, value)
    return {
        "label": label,
        "path": value,
        "resolvedPath": str(path),
        "exists": path.exists(),
        "servedUrl": _artifact_api_url_if_safe(path),
        "source": source,
    }


def _build_autonomous_workflow_record(
    mission: Mission,
    *,
    root: Path,
    event_count: int = 0,
    previous: dict | None = None,
) -> dict:
    previous = previous or {}
    delegated_sessions = [
        _as_mapping(session) for session in mission.delegated_runtime_sessions or []
    ]
    delegated_sessions = [item for item in delegated_sessions if item]
    action_history = [
        _as_mapping(action) for action in mission.action_history or []
    ]
    action_history = [item for item in action_history if item]
    mission_loop = build_mission_loop_snapshot(mission)

    changed_files: list[object] = list(mission.proof.changed_files or [])
    for session in delegated_sessions:
        changed_files.extend(session.get("changed_files") or [])
    for action in action_history:
        result = _as_mapping(action.get("result"))
        changed_files.extend(result.get("changed_files") or [])

    approval_history = list(mission.state.approval_history or [])
    pending_approvals = list(mission.proof.pending_approvals or [])
    for session in delegated_sessions:
        pending = _as_mapping(session.get("pending_approval"))
        if pending and str(pending.get("status") or "pending") == "pending":
            pending_approvals.append(pending.get("prompt") or pending.get("request_id"))
        approval_history.extend(
            item for item in session.get("approval_history") or [] if isinstance(item, dict)
        )

    evidence_files: list[dict] = []
    for session in delegated_sessions:
        for raw_path, label, source in (
            (session.get("session_path"), "session state", "delegated_runtime_session"),
            (session.get("events_path"), "session events", "delegated_runtime_events"),
            (session.get("log_path"), "runtime log", "delegated_runtime_log"),
        ):
            evidence = _workflow_record_path(root, raw_path, label=label, source=source)
            if evidence:
                evidence_files.append(evidence)
    deduped_evidence: list[dict] = []
    seen_evidence: set[str] = set()
    for evidence in evidence_files:
        key = str(evidence.get("resolvedPath") or evidence.get("path") or "")
        if not key or key in seen_evidence:
            continue
        seen_evidence.add(key)
        deduped_evidence.append(evidence)

    session_statuses = [
        str(session.get("status") or "").strip()
        for session in delegated_sessions
        if session.get("status")
    ]
    failed_sessions = sum(1 for status in session_statuses if status == "failed")
    active_sessions = sum(
        1
        for status in session_statuses
        if status in {"queued", "launching", "running", "waiting_for_approval"}
    )
    workflow_id = str(previous.get("workflowId") or f"workflow_{mission.mission_id}")
    created_at = str(previous.get("createdAt") or mission.created_at)
    updated_at_candidates = [
        mission.updated_at,
        *[str(session.get("updated_at") or "") for session in delegated_sessions],
    ]
    updated_at = max((item for item in updated_at_candidates if item), default=mission.updated_at)

    return {
        "schemaVersion": "autonomous-workflow-record.v1",
        "workflowId": workflow_id,
        "missionId": mission.mission_id,
        "workspaceId": mission.workspace_id,
        "title": mission.title or _mission_title(mission.objective),
        "objective": mission.objective,
        "status": mission.state.status,
        "runtimeId": mission.runtime_id,
        "mode": mission.run_budget.mode,
        "createdAt": created_at,
        "updatedAt": updated_at,
        "currentPhase": mission_loop.get("currentCyclePhase", ""),
        "continuityState": mission_loop.get("continuityState", ""),
        "continuityDetail": mission_loop.get("continuityDetail", ""),
        "runBudget": {
            "mode": mission.run_budget.mode,
            "maxRuntimeSeconds": mission.run_budget.max_runtime_seconds,
            "remainingSeconds": mission.state.remaining_runtime_seconds,
            "status": mission.state.time_budget_status,
            "runUntilBehavior": mission.run_budget.run_until_behavior,
        },
        "executionScope": asdict(mission.execution_scope),
        "executionPolicy": asdict(mission.execution_policy),
        "routeContract": (
            mission.effective_route_contract
            if mission.effective_route_contract
            else _effective_route_contract_for_mission(mission)
        ),
        "runtimeSummary": {
            "delegatedSessionCount": len(delegated_sessions),
            "activeSessionCount": active_sessions,
            "failedSessionCount": failed_sessions,
            "latestSessionId": mission.state.latest_session_id
            or (str(delegated_sessions[-1].get("delegated_id") or "") if delegated_sessions else ""),
            "currentRuntimeLane": mission_loop.get("currentRuntimeLane", ""),
            "lastRuntimeEvent": mission.state.last_runtime_event,
        },
        "approvalSummary": {
            "pending": _unique_texts(pending_approvals),
            "pendingCount": len(_unique_texts(pending_approvals)),
            "historyCount": len(approval_history),
            "latest": approval_history[-1] if approval_history else {},
        },
        "verification": {
            "commands": list(mission.verification_policy.commands or []),
            "lastResult": mission_loop.get("lastVerificationResult", ""),
            "lastSummary": mission_loop.get("lastVerificationSummary", ""),
            "passedChecks": list(mission.proof.passed_checks or []),
            "failedChecks": list(mission.proof.failed_checks or []),
            "verificationFailures": list(mission.state.verification_failures or []),
        },
        "risk": {
            "blockers": list(mission.proof.blocked_by or []),
            "blockerClassification": dict(mission.state.blocker_classification or {}),
            "pendingMutatingActions": mission.state.pending_mutating_actions,
            "stopReason": mission.state.stop_reason or "",
        },
        "changedFiles": _unique_texts(changed_files),
        "eventCount": event_count,
        "evidenceFiles": deduped_evidence,
        "lastProofSummary": mission.proof.summary,
        "archived": False,
    }


def _build_autonomous_workflow_records_snapshot(workflows: list[dict]) -> dict:
    active_records = [item for item in workflows if not item.get("archived")]
    needs_approval = [
        item
        for item in active_records
        if item.get("status") == "needs_approval"
        or int(item.get("approvalSummary", {}).get("pendingCount", 0) or 0) > 0
    ]
    running = [
        item
        for item in active_records
        if item.get("status") in {"running", "queued", "delegated_active"}
        or item.get("runtimeSummary", {}).get("activeSessionCount", 0)
    ]
    failed = [
        item
        for item in active_records
        if item.get("status") in {"failed", "verification_failed", "blocked"}
        or item.get("runtimeSummary", {}).get("failedSessionCount", 0)
        or item.get("verification", {}).get("failedChecks")
        or item.get("verification", {}).get("verificationFailures")
        or item.get("risk", {}).get("blockers")
    ]
    completed = [item for item in active_records if item.get("status") == "completed"]
    return {
        "schemaVersion": "autonomous-workflows.v1",
        "items": workflows[:80],
        "summary": {
            "total": len(active_records),
            "running": len(running),
            "needsApproval": len(needs_approval),
            "failedOrBlocked": len(failed),
            "completed": len(completed),
            "archived": len(workflows) - len(active_records),
        },
        "emptyState": (
            "No autonomous workflow records have been captured yet. Start a mission to create an audit record."
            if not active_records
            else ""
        ),
        "source": "agent_control_autonomous_workflows",
    }


def detect_workspace_type(root: Path) -> str:
    root = root.resolve()
    if (root / "src-tauri").exists() and (root / "pyproject.toml").exists():
        return "tauri-python"
    if (root / "package.json").exists() and (root / "public").exists():
        return "web-node"
    if (root / "pyproject.toml").exists():
        return "python"
    if (root / "package.json").exists():
        return "node"
    return "general"


def recommend_skills(
    workspace_type: str, runtime_id: str
) -> list[SkillRecommendation]:
    recommendations = [
        SkillRecommendation(
            recommendation_id="repo_scan",
            label="Repo Scan",
            reason="Ground each mission in real workspace structure before delegating.",
            runtime_id=runtime_id,
            workspace_type=workspace_type,
            enabled_by_default=True,
        )
    ]
    if "python" in workspace_type:
        recommendations.append(
            SkillRecommendation(
                recommendation_id="python_verification",
                label="Python Verification",
                reason="Keep pytest and packaging checks visible in completion proof.",
                runtime_id=runtime_id,
                workspace_type=workspace_type,
            )
        )
    if "node" in workspace_type or "web" in workspace_type or "tauri" in workspace_type:
        recommendations.append(
            SkillRecommendation(
                recommendation_id="frontend_proof",
                label="Frontend Proof",
                reason="Track UI regressions and live run output for mission proof.",
                runtime_id=runtime_id,
                workspace_type=workspace_type,
            )
        )
    return recommendations


def recommend_integrations(
    workspace_type: str, runtime_id: str
) -> list[IntegrationRecommendation]:
    recommendations = [
        IntegrationRecommendation(
            recommendation_id="filesystem_mcp",
            label="Filesystem MCP",
            reason="Helps the agent inspect and summarize multiple projects safely.",
            command="npx @modelcontextprotocol/server-filesystem .",
            runtime_id=runtime_id,
            workspace_type=workspace_type,
            enabled_by_default=True,
        ),
        IntegrationRecommendation(
            recommendation_id="git_mcp",
            label="Git MCP",
            reason="Exposes repo status and history to the agent without custom glue.",
            command="uvx mcp-server-git",
            runtime_id=runtime_id,
            workspace_type=workspace_type,
        ),
    ]
    if "web" in workspace_type or "tauri" in workspace_type:
        recommendations.append(
            IntegrationRecommendation(
                recommendation_id="playwright_mcp",
                label="Playwright MCP",
                reason="Useful for proof screenshots, smoke tests, and non-technical validation.",
                command="npx @playwright/mcp@latest",
                runtime_id=runtime_id,
                workspace_type=workspace_type,
            )
        )
    return recommendations


def mission_mode_to_engine_mode(mode: str) -> str:
    mapping = {
        "focus": "fast",
        "autopilot": "autopilot",
        "deep run": "deep_run",
        "research": "swarms",
    }
    return mapping.get(mode.strip().lower(), "autopilot")


def default_docs_for_workspace(root: Path) -> list[str]:
    candidates = ["docs/PRD.md", "docs/ROADMAP.md", "README.md"]
    return [path for path in candidates if (root / path).exists()]


def build_escalation_preview(mission: Mission) -> str:
    proof_summary = mission.proof.summary or mission.objective
    if mission.state.status == "completed":
        return f"Mission complete: {proof_summary}"
    if mission.state.status == "verification_failed":
        failures = ", ".join(mission.state.verification_failures) or "verification failed"
        return f"Mission needs input: {failures}"
    if mission.state.status == "blocked":
        blocked = ", ".join(mission.proof.blocked_by) or "setup or approval is blocking progress"
        return f"Mission blocked: {blocked}"
    if mission.state.status == "needs_approval":
        return f"Approval needed: {proof_summary}"
    return f"Mission update: {proof_summary}"


def _mission_title(objective: str) -> str:
    cleaned = re.sub(r"\s+", " ", objective or "").strip()
    if not cleaned:
        return "New Mission"
    cleaned = re.split(r"[\n.!?]", cleaned, maxsplit=1)[0].strip()
    for pattern in MISSION_TITLE_PREFIXES:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9+./_-]*", cleaned)
    if not tokens:
        return "New Mission"
    title_tokens: list[str] = []
    for index, token in enumerate(tokens):
        if index >= 2 and token.lower() in MISSION_TITLE_STOPWORDS:
            continue
        title_tokens.append(token)
        if len(title_tokens) >= 6:
            break
    if not title_tokens:
        title_tokens = tokens[:6]
    first = title_tokens[0]
    if first and not first[:1].isupper():
        title_tokens[0] = f"{first[:1].upper()}{first[1:]}"
    return " ".join(title_tokens)


def infer_planned_file_scope(objective: str, success_checks: list[str] | None = None) -> list[str]:
    candidates: list[str] = []
    patterns = [
        r"\b(?:under|in|inside|at|to)\s+([A-Za-z]:[\\/][^\s,;]+)",
        r"\b(?:under|in|inside|at|to)\s+((?:/|\\\\)[^\s,;]+)",
        r"\b((?:apps|web|src|docs|scripts|tests|desktop-ui|src-tauri|packages|tools|reports|artifacts|\.agent_control)[\\/][^\s,;]+)",
        r"`([^`]+[\\/][^`]+)`",
    ]
    for line in "\n".join([objective or "", *(success_checks or [])]).splitlines():
        normalized_line = line.strip().lower()
        if not normalized_line:
            continue
        if "source:" in normalized_line and "workspace" not in normalized_line:
            continue
        if "source project" in normalized_line and "workspace" not in normalized_line:
            continue
        for pattern in patterns:
            for match in re.finditer(pattern, line, flags=re.IGNORECASE):
                raw = match.group(1).strip().rstrip(".,;:)")
                raw_lower = raw.replace("\\", "/").lower()
                if raw_lower == "tests/build/smoke" and "checks" in normalized_line:
                    continue
                if raw:
                    candidates.append(raw)
    normalized: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        path = candidate.replace("\\", "/")
        path = re.sub(r"^[\"']|[\"']$", "", path).strip()
        path = re.sub(r"/+$", "", path)
        if not path or "://" in path:
            continue
        dedupe_key = path.lower()
        if dedupe_key not in seen:
            seen.add(dedupe_key)
            normalized.append(path)
    return normalized[:8]


def _age_seconds(value: str) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(int((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()), 0)


def _percent(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return int(round((numerator / denominator) * 100))


def _load_json_file(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_text_tail_lines(path: Path, *, limit: int) -> list[str]:
    limit = max(0, int(limit or 0))
    if limit <= 0:
        return []
    block_size = 64 * 1024
    buffer = b""
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            position = handle.tell()
            while position > 0 and buffer.count(b"\n") <= limit:
                read_size = min(block_size, position)
                position -= read_size
                handle.seek(position)
                buffer = handle.read(read_size) + buffer
    except OSError:
        return []
    lines = [
        line.decode("utf-8", errors="ignore").strip()
        for line in buffer.splitlines()
        if line.strip()
    ]
    return lines[-limit:]


def _read_jsonl_tail(path: Path, *, limit: int = 10) -> list[dict]:
    rows: deque[dict] = deque(maxlen=max(1, int(limit or 1)))
    for line in _read_text_tail_lines(path, limit=max(1, int(limit or 1))):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return list(rows)


def _runtime_transcript_has_concrete_output(row: dict, detail: str = "") -> bool:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    args = metadata.get("args") if isinstance(metadata.get("args"), dict) else {}
    result = metadata.get("result") if isinstance(metadata.get("result"), dict) else {}
    return any(
        str(value or "").strip()
        for value in (
            args.get("content"),
            args.get("body"),
            args.get("text"),
            result.get("result_summary"),
            result.get("stdout"),
            result.get("error"),
        )
    ) or "runtime output:" in str(detail or "").lower()


def _is_low_signal_session_state_value(value: str) -> bool:
    normalized = " ".join(str(value or "").strip().lower().split())
    if not normalized:
        return True
    return normalized in {
        "fluxio hybrid harness orchestrated this mission.",
        "prepare rollout notes and next iteration tasks",
    } or normalized.startswith("execution policy:") or normalized.startswith("runtime controls:")


def _runtime_transcript_detail(row: dict) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    if not metadata:
        return ""
    parts: list[str] = []
    kind = str(metadata.get("kind") or row.get("kind") or "").strip()
    command = str(metadata.get("command") or "").strip()
    target_path = str(
        metadata.get("target_path")
        or metadata.get("targetPath")
        or metadata.get("path")
        or ""
    ).strip()
    gate = metadata.get("gate") if isinstance(metadata.get("gate"), dict) else {}
    result = metadata.get("result") if isinstance(metadata.get("result"), dict) else {}
    args = metadata.get("args") if isinstance(metadata.get("args"), dict) else {}
    revision_id = str(metadata.get("revision_id") or metadata.get("revisionId") or "").strip()
    active_step_id = str(metadata.get("active_step_id") or metadata.get("activeStepId") or "").strip()
    file_content = str(
        args.get("content")
        or args.get("body")
        or args.get("text")
        or ""
    ).strip()
    if file_content:
        content_preview = " ".join(file_content.split())
        parts.append(f"Runtime output: {content_preview[:900]}")
    if kind:
        parts.append(f"Action: {kind}")
    if target_path:
        parts.append(f"Target: {target_path}")
    if command:
        parts.append(f"Command: {command[:180]}")
    if gate.get("status"):
        parts.append(f"Gate: {gate.get('status')}")
    if result.get("result_summary"):
        parts.append(f"Result: {result.get('result_summary')}")
    elif result.get("error"):
        parts.append(f"Error: {result.get('error')}")
    if revision_id:
        parts.append(f"Revision: {revision_id}")
    if active_step_id:
        parts.append(f"Active step: {active_step_id}")
    if not parts:
        compact_keys = [
            key
            for key in ("phase", "role", "provider", "model", "status", "source")
            if str(metadata.get(key) or "").strip()
        ]
        parts = [f"{_titleize_token(key)}: {metadata.get(key)}" for key in compact_keys[:5]]
    return " · ".join(str(part) for part in parts if str(part or "").strip())[:1200]


def _titleize_token(value: str) -> str:
    return re.sub(r"\b\w", lambda match: match.group(0).upper(), str(value or "").replace("_", " ").replace("-", " "))


def _verify_desktop_script_contract(root: Path) -> tuple[bool, str]:
    package_path = root / "package.json"
    payload = _load_json_file(package_path)
    if not isinstance(payload, dict):
        return False, "package.json is missing or unreadable."
    scripts = payload.get("scripts", {})
    if not isinstance(scripts, dict):
        return False, "package.json has no scripts section."
    command = str(scripts.get("verify:desktop", "")).strip()
    required_snippets = (
        "python -m pytest tests -q",
        "npm run frontend:build",
        "npm run tauri build -- --debug",
    )
    missing = [snippet for snippet in required_snippets if snippet not in command]
    if missing:
        return False, "verify:desktop is missing required stages."
    return True, "verify:desktop includes pytest, frontend build, and Tauri build."


def _verify_frontend_source_alignment(root: Path) -> tuple[bool, str]:
    required_paths = [
        root / "web" / "src" / "main.tsx",
        root / "web" / "src" / "fluxio" / "FluxioApp.tsx",
        root / "web" / "src" / "fluxio" / "fluxioBridge.ts",
    ]
    if any(not path.exists() for path in required_paths):
        return False, "web frontend entrypoint files are missing."

    vite_path = root / "vite.config.mjs"
    tauri_path = root / "src-tauri" / "tauri.conf.json"
    if not vite_path.exists() or not tauri_path.exists():
        return False, "Vite or Tauri desktop config is missing."
    vite_text = vite_path.read_text(encoding="utf-8")
    if not _vite_targets_web_root(vite_text):
        return False, "vite.config.mjs is not aligned with web/."

    tauri_payload = _load_json_file(tauri_path)
    if not isinstance(tauri_payload, dict):
        return False, "src-tauri/tauri.conf.json is unreadable."
    frontend_dist = (
        str(tauri_payload.get("build", {}).get("frontendDist", ""))
        .replace("\\", "/")
        .strip()
    )
    if "web/dist" not in frontend_dist:
        return False, "src-tauri/tauri.conf.json is not aligned with web/dist."
    return True, "Frontend source-of-truth is aligned to web/."


def _verify_release_artifact_ci_contract(root: Path) -> tuple[bool, str]:
    workflow_path = root / ".github" / "workflows" / "release-proof.yml"
    if not workflow_path.exists():
        return False, ".github/workflows/release-proof.yml is missing."

    workflow_text = workflow_path.read_text(encoding="utf-8", errors="ignore")
    required_snippets = (
        "npm run frontend:build",
        "npm run verify:long-history",
        "npm run verify:release-artifacts",
        "actions/upload-artifact",
        ".agent_control/proof_digests/ci-release-proof.md",
        ".agent_control/release_artifacts/**",
        "tmp-ui-checks/**",
    )
    missing = [snippet for snippet in required_snippets if snippet not in workflow_text]
    if missing:
        return False, "release-proof CI is missing required release evidence stages."
    return True, "release-proof CI builds, runs long-history proof, archives proof artifacts, and uploads evidence."


def _verify_public_web_distribution_contract(root: Path) -> tuple[bool, str]:
    workflow_path = root / ".github" / "workflows" / "web-pages.yml"
    verifier_path = root / "scripts" / "verify_public_web_distribution.py"
    package_payload = _load_json_file(root / "package.json")
    if not workflow_path.exists():
        return False, ".github/workflows/web-pages.yml is missing."
    if not verifier_path.exists():
        return False, "scripts/verify_public_web_distribution.py is missing."
    if not isinstance(package_payload, dict):
        return False, "package.json is missing or unreadable."

    workflow_text = workflow_path.read_text(encoding="utf-8", errors="ignore")
    verifier_text = verifier_path.read_text(encoding="utf-8", errors="ignore")
    scripts = package_payload.get("scripts", {})
    web_distribution_script = str(scripts.get("verify:web-distribution", "")) if isinstance(scripts, dict) else ""
    required_workflow_snippets = (
        "npm run frontend:build",
        "npm run verify:web-distribution",
        "actions/upload-pages-artifact",
        "actions/deploy-pages",
        "path: web/dist",
        "page_url",
        "fluxio.public_web_deployment.v1",
        ".agent_control/deployment_evidence/public-web.json",
    )
    if any(snippet not in workflow_text for snippet in required_workflow_snippets):
        return False, "GitHub Pages workflow is missing required build/verify/deploy stages."
    if (
        "fluxio-public-web-release-candidate" not in workflow_text
        and "fluxio-public-web-deployment" not in workflow_text
    ):
        return False, "GitHub Pages workflow does not upload public web deployment evidence."
    if "verify_public_web_distribution.py" not in web_distribution_script:
        return False, "package.json does not expose verify:web-distribution."
    if "fluxio.public_web_distribution.v1" not in verifier_text:
        return False, "public web verifier does not emit the expected schema."
    return True, "GitHub Pages/PWA distribution contract is verified before public web deploy."


def _verify_self_improvement_evidence_contract(root: Path) -> tuple[bool, str]:
    verifier_path = root / "scripts" / "verify_self_improvement_evidence.py"
    package_payload = _load_json_file(root / "package.json")
    release_workflow_path = root / ".github" / "workflows" / "release-proof.yml"
    archive_path = root / "scripts" / "archive_release_proofs.py"
    if not verifier_path.exists():
        return False, "scripts/verify_self_improvement_evidence.py is missing."
    if not isinstance(package_payload, dict):
        return False, "package.json is missing or unreadable."
    if not release_workflow_path.exists():
        return False, ".github/workflows/release-proof.yml is missing."
    verifier_text = verifier_path.read_text(encoding="utf-8", errors="ignore")
    workflow_text = release_workflow_path.read_text(encoding="utf-8", errors="ignore")
    archive_text = archive_path.read_text(encoding="utf-8", errors="ignore")
    scripts = package_payload.get("scripts", {})
    command = str(scripts.get("verify:self-improvement", "")) if isinstance(scripts, dict) else ""
    required = (
        "fluxio.self_improvement_evidence.v1" in verifier_text
        and "verify_self_improvement_evidence.py" in command
        and "--write" in command
        and "npm run verify:self-improvement" in workflow_text
        and ".agent_control/self_improvement_evidence/**" in workflow_text
        and "self_improvement_evidence" in archive_text
    )
    if not required:
        return False, "self-improvement evidence is not archived by the release-proof path."
    return True, "Self-improvement evidence is measured, written, and archived with release proof."


def _vite_targets_web_root(vite_text: str) -> bool:
    normalized = vite_text.replace("\\", "/")
    if 'resolve(repoRoot, "web")' in normalized or "resolve(repoRoot, 'web')" in normalized:
        return True
    if re.search(r"\broot\s*:\s*['\"]web['\"]", normalized):
        return True

    for match in re.finditer(
        r"const\s+([A-Za-z_]\w*)\s*=\s*resolve\(([^)]*)\)",
        normalized,
        flags=re.DOTALL,
    ):
        variable_name = match.group(1)
        args = match.group(2)
        if not re.search(r"['\"]web['\"]", args):
            continue
        root_refs_variable = re.search(
            rf"\broot\s*:\s*{re.escape(variable_name)}\b",
            normalized,
        )
        if root_refs_variable:
            return True
    return False


def _release_quality_score(
    *,
    completion_rate: int,
    delegated_run_rate: int,
    resume_run_rate: int,
    resume_completion_rate: int,
    verification_pause_rate: int,
) -> int:
    resume_component = resume_completion_rate if resume_run_rate > 0 else 50
    values = [
        max(0, min(completion_rate, 100)),
        max(0, min(delegated_run_rate * 2, 100)),
        max(0, min(resume_component, 100)),
        max(0, min(100 - verification_pause_rate, 100)),
    ]
    return int(round(sum(values) / len(values)))


def _build_proving_cycle_readiness(root: Path) -> dict:
    payload = _load_json_file(root / ".agent_control" / "missions.json")
    missions = payload if isinstance(payload, list) else []
    runtime_counts = {
        "openclaw": 0,
        "hermes": 0,
    }
    completed_counts = {
        "openclaw": 0,
        "hermes": 0,
    }
    approval_wait_seen = False
    delegated_active_seen = False

    for mission in missions:
        if not isinstance(mission, dict):
            continue
        runtime_id = str(mission.get("runtime_id", "")).strip().lower()
        state = mission.get("state", {})
        if not isinstance(state, dict):
            state = {}
        status = str(state.get("status", "")).strip().lower()
        continuity_state = str(state.get("continuity_state", "")).strip().lower()
        time_budget_status = str(state.get("time_budget_status", "")).strip().lower()
        stop_reason = str(state.get("stop_reason", "")).strip().lower()
        runtime_lane = str(state.get("current_runtime_lane", "")).strip().lower()
        escalation_policy = mission.get("escalation_policy", {})
        if not isinstance(escalation_policy, dict):
            escalation_policy = {}
        pending_approval_count = int(escalation_policy.get("pending_count", 0) or 0)
        delegated_sessions = state.get("delegated_runtime_sessions")
        if not isinstance(delegated_sessions, list):
            delegated_sessions = mission.get("delegated_runtime_sessions", [])
        delegated_session_statuses = {
            str(item.get("status", "")).strip().lower()
            for item in delegated_sessions
            if isinstance(item, dict)
        }
        if runtime_id in runtime_counts:
            runtime_counts[runtime_id] += 1
            if status == "completed":
                completed_counts[runtime_id] += 1
        if runtime_id == "hermes" and (
            status == "needs_approval"
            or continuity_state == "approval_waiting"
            or pending_approval_count > 0
            or "waiting_for_approval" in delegated_session_statuses
        ):
            approval_wait_seen = True
        if (
            continuity_state == "delegated_active"
            or time_budget_status == "delegated_active"
            or stop_reason == "delegated_runtime_running"
            or any(
                status_name in {"launching", "running", "waiting_for_approval"}
                for status_name in delegated_session_statuses
            )
            or (
                "delegated lane" in runtime_lane
                and any(token in runtime_lane for token in ("launching", "running", "waiting"))
            )
        ):
            delegated_active_seen = True

    proofs = [
        {
            "proofId": "openclaw_proving_mission",
            "label": "OpenClaw proving mission completed",
            "required": False,
            "category": "optional_secondary_harness_parity",
            "passed": completed_counts["openclaw"] > 0,
            "details": (
                f"Completed OpenClaw missions: {completed_counts['openclaw']}. "
                "OpenClaw is optional secondary-harness parity evidence for this Hermes-first release."
            ),
        },
        {
            "proofId": "hermes_delegated_mission",
            "label": "Hermes delegated mission completed",
            "required": True,
            "category": "preferred_harness",
            "passed": completed_counts["hermes"] > 0,
            "details": f"Completed Hermes missions: {completed_counts['hermes']}.",
        },
        {
            "proofId": "approval_wait_evidence",
            "label": "Hermes approval-wait evidence recorded",
            "required": True,
            "category": "preferred_harness_control_flow",
            "passed": approval_wait_seen,
            "details": (
                "At least one Hermes mission recorded `needs_approval` or `approval_waiting`."
                if approval_wait_seen
                else "No Hermes approval-wait state has been recorded yet."
            ),
        },
        {
            "proofId": "delegated_active_evidence",
            "label": "Delegated-active continuity evidence recorded",
            "required": True,
            "category": "preferred_harness_continuity",
            "passed": delegated_active_seen,
            "details": (
                "At least one mission recorded `delegated_active` continuity."
                if delegated_active_seen
                else "No delegated-active continuity state has been recorded yet."
            ),
        },
    ]
    missing = [item["label"] for item in proofs if item.get("required") and not item["passed"]]
    optional_missing = [
        item["label"]
        for item in proofs
        if not item.get("required") and not item["passed"]
    ]
    next_actions = [f"Capture required proof: {label}." for label in missing]
    next_actions.extend(f"Optional parity proof: {label}." for label in optional_missing)
    return {
        "missionCount": len(missions),
        "runtimeMissionCounts": runtime_counts,
        "runtimeCompletionCounts": completed_counts,
        "preferredRuntime": "hermes",
        "proofs": proofs,
        "missingProofs": missing,
        "optionalMissingProofs": optional_missing,
        "ready": not missing,
        "nextActions": next_actions[:4],
    }


def _event_timestamp(event: dict) -> str:
    return str(
        event.get("timestamp")
        or event.get("at")
        or event.get("created_at")
        or event.get("updated_at")
        or event.get("executed_at")
        or ""
    )


def _project_event_tone(event: dict) -> str:
    text = " ".join(
        [
            str(event.get("kind") or ""),
            str(event.get("message") or ""),
            json.dumps(event.get("metadata") or {}, sort_keys=True, default=str),
        ]
    ).lower()
    if any(marker in text for marker in ("failed", "failure", "error", "blocked")):
        return "bad"
    if any(marker in text for marker in ("approval", "queued", "pending", "needs")):
        return "warn"
    if any(marker in text for marker in ("completed", "passed", "succeeded", "slice")):
        return "good"
    return "neutral"


def _safe_artifact_id(path: Path) -> str:
    import hashlib

    return hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:24]


def _runtime_lane_rows_for_mission(mission: Mission, session: DelegatedRuntimeSession | None = None) -> list[dict]:
    contract = (
        mission.effective_route_contract
        if mission.effective_route_contract
        else _effective_route_contract_for_mission(mission)
    )
    route_rows = contract.get("roles") if isinstance(contract, dict) else []
    if not isinstance(route_rows, list):
        route_rows = []
    provider_truth = mission.state.provider_runtime_truth if isinstance(mission.state.provider_runtime_truth, dict) else {}
    active_route = provider_truth.get("activeRoute") if isinstance(provider_truth.get("activeRoute"), dict) else {}
    active_role = str(active_route.get("role") or "").strip().lower()
    route_auth = provider_truth.get("routeAuth") if isinstance(provider_truth.get("routeAuth"), dict) else {}
    last_failure = provider_truth.get("lastFailure") if isinstance(provider_truth.get("lastFailure"), dict) else {}
    lane_control_receipts = [
        item
        for item in (mission.state.lane_control_receipts or [])
        if isinstance(item, dict)
    ]
    lanes: list[dict] = []
    seen_roles: set[str] = set()
    for role in ("planner", "executor", "verifier"):
        latest_control_receipt = next(
            (
                item
                for item in reversed(lane_control_receipts)
                if str(item.get("role") or "").strip().lower() == role
            ),
            {},
        )
        route = next(
            (
                dict(item)
                for item in route_rows
                if isinstance(item, dict) and str(item.get("role", "")).strip().lower() == role
            ),
            {},
        )
        provider = str(route.get("provider") or active_route.get("provider") or "openai-codex").strip().lower()
        model = str(route.get("model") or active_route.get("model") or "gpt-5.5").strip()
        provider_auth = _route_auth_for_provider(
            provider,
            provider_truth=provider_truth,
            route_auth=route_auth,
        )
        provider_auth_present = bool(provider_auth.get("authPresent"))
        auth_path = str(provider_auth.get("authPath") or "")
        health = "ready" if provider_auth_present else ("blocked" if provider else "unknown")
        blocker = ""
        if not provider_auth_present:
            if provider in {"openai", "openai-codex"}:
                blocker = "OpenAI Codex OAuth/API auth is not present for this runtime."
            elif provider in {"minimax", "minimax-portal", "minimax-cn", "minimax-oauth"}:
                blocker = "MiniMax API key or OpenClaw OAuth is not present for this runtime."
            elif provider:
                blocker = f"{provider} auth is not present for this runtime."
        if last_failure and str(last_failure.get("role", "")).strip().lower() == role:
            blocker = str(last_failure.get("summary") or blocker)
            health = "blocked"
        failure_class = _provider_failure_class(blocker, last_failure if isinstance(last_failure, dict) else {})
        latest_control_detail = ""
        if latest_control_receipt:
            latest_control_detail = (
                f"Last lane control: {latest_control_receipt.get('action', 'action')} "
                f"recorded by {latest_control_receipt.get('receiptId', 'receipt')}."
            )
        lanes.append(
            {
                "role": role,
                "phase": "plan" if role == "planner" else ("verify" if role == "verifier" else "execute"),
                "provider": provider,
                "model": model,
                "effort": str(route.get("effort") or active_route.get("effort") or "medium"),
                "authPresent": provider_auth_present,
                "authPath": auth_path or "not configured",
                "authMode": str(provider_auth.get("authMode") or ""),
                "health": health,
                "active": role == active_role or (not active_role and role == "executor"),
                "blocker": blocker,
                "latestControl": latest_control_receipt,
                "laneControlReceipt": latest_control_receipt,
                "controlState": str(latest_control_receipt.get("action") or ""),
                "lastControlEvent": latest_control_detail,
                "failureClass": failure_class,
                "toolFamilies": _provider_tool_families(provider, roles=[role], model=model),
                "quota": _provider_quota_truth(
                    provider,
                    auth_present=provider_auth_present,
                    provider_truth=provider_truth,
                ),
                "actions": [
                    "inspect-events",
                    "resume" if session and session.status in {"running", "waiting_for_approval", "failed", "stopped"} else "open-proof",
                ],
            }
        )
        seen_roles.add(role)
    for item in route_rows:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        if role and role not in seen_roles:
            latest_control_receipt = next(
                (
                    receipt
                    for receipt in reversed(lane_control_receipts)
                    if str(receipt.get("role") or "").strip().lower() == role
                ),
                {},
            )
            lanes.append(
                {
                    "role": role,
                    "phase": role,
                    "provider": str(item.get("provider") or ""),
                    "model": str(item.get("model") or ""),
                    "effort": str(item.get("effort") or "medium"),
                    "authPresent": False,
                    "authPath": "",
                    "authMode": "",
                    "health": "unknown",
                    "active": False,
                    "blocker": "",
                    "latestControl": latest_control_receipt,
                    "laneControlReceipt": latest_control_receipt,
                    "controlState": str(latest_control_receipt.get("action") or ""),
                    "lastControlEvent": (
                        f"Last lane control: {latest_control_receipt.get('action', 'action')} "
                        f"recorded by {latest_control_receipt.get('receiptId', 'receipt')}."
                        if latest_control_receipt
                        else ""
                    ),
                    "failureClass": "unknown",
                    "toolFamilies": _provider_tool_families(str(item.get("provider") or ""), roles=[role]),
                    "quota": _provider_quota_truth(
                        str(item.get("provider") or ""),
                        auth_present=False,
                        provider_truth=provider_truth,
                    ),
                    "actions": ["inspect-events"],
                }
            )
    return lanes


def _route_auth_for_provider(
    provider: str,
    *,
    provider_truth: dict,
    route_auth: dict,
) -> dict:
    normalized = str(provider or "").strip().lower()
    candidates = [normalized]
    if normalized in {"openai", "openai-codex"}:
        candidates.extend(["openai-codex", "openai"])
    elif normalized in {"minimax", "minimax-portal", "minimax-cn", "minimax-oauth"}:
        candidates.extend(["minimax", "minimax-portal", "minimax-oauth", "minimax-cn"])
    for candidate in candidates:
        item = route_auth.get(candidate)
        if isinstance(item, dict):
            return item
    active_route = provider_truth.get("activeRoute") if isinstance(provider_truth.get("activeRoute"), dict) else {}
    active_provider = str(active_route.get("provider") or "").strip().lower()
    if normalized == active_provider or (
        normalized in {"openai", "openai-codex"} and active_provider in {"openai", "openai-codex"}
    ) or (
        normalized in {"minimax", "minimax-portal", "minimax-cn", "minimax-oauth"}
        and active_provider in {"minimax", "minimax-portal", "minimax-cn", "minimax-oauth"}
    ):
        return {
            "provider": normalized,
            "authPresent": bool(provider_truth.get("authPresent")),
            "authMode": str(provider_truth.get("authMode") or ""),
            "authPath": str(provider_truth.get("authPath") or ""),
        }
    return {
        "provider": normalized,
        "authPresent": False,
        "authMode": "",
        "authPath": "not configured",
    }


def _provider_tool_families(provider: str, *, roles: list[str] | None = None, model: str = "") -> list[str]:
    normalized = str(provider or "").strip().lower()
    role_set = {str(role or "").strip().lower() for role in (roles or []) if str(role or "").strip()}
    tools = {"text-generation"}
    if "planner" in role_set:
        tools.update({"planning", "task-routing"})
    if "executor" in role_set:
        tools.update({"code-edit", "artifact-generation"})
    if "verifier" in role_set:
        tools.update({"verification", "review"})
    if normalized in {"openai", "openai-codex"}:
        tools.update({"reasoning", "code", "tool-calling"})
        if normalized == "openai-codex":
            tools.update({"terminal", "patch", "repo-inspection"})
    elif normalized in {"minimax", "minimax-portal", "minimax-cn", "minimax-oauth"}:
        tools.update({"frontend-ui", "multimodal", "creative-iteration"})
    elif normalized:
        tools.add("provider-route")
    if "image" in str(model or "").lower():
        tools.add("image-generation")
    return sorted(tools)


def _provider_quota_truth(
    provider: str,
    *,
    auth_present: bool,
    provider_truth: dict,
) -> dict:
    normalized = str(provider or "").strip().lower()
    quota_payload = provider_truth.get("quota") if isinstance(provider_truth.get("quota"), dict) else {}
    provider_quota = quota_payload.get(normalized) if isinstance(quota_payload.get(normalized), dict) else {}
    if provider_quota:
        return {
            "schema": "fluxio.provider_quota_truth.v1",
            "status": str(provider_quota.get("status") or "reported"),
            "source": str(provider_quota.get("source") or "runtime_provider_report"),
            "remaining": provider_quota.get("remaining"),
            "limit": provider_quota.get("limit"),
            "resetAt": str(provider_quota.get("resetAt") or provider_quota.get("reset_at") or ""),
            "message": str(provider_quota.get("message") or ""),
        }
    return {
        "schema": "fluxio.provider_quota_truth.v1",
        "status": "unreported" if auth_present else "unavailable",
        "source": "runtime_has_no_live_quota_report" if auth_present else "provider_auth_missing",
        "remaining": None,
        "limit": None,
        "resetAt": "",
        "message": (
            "Provider auth is present, but the runtime has not reported live quota or rate-window data."
            if auth_present
            else "Quota cannot be checked until provider auth is present."
        ),
    }


def _provider_failure_class(blocker: object, last_failure: dict | None = None) -> str:
    text = " ".join(
        [
            str(blocker or ""),
            str((last_failure or {}).get("summary") or ""),
            str((last_failure or {}).get("source") or ""),
        ]
    ).lower()
    if not text.strip():
        return "none"
    if any(token in text for token in ("auth", "oauth", "api key", "not present", "credential")):
        return "auth_missing"
    if any(token in text for token in ("quota", "rate limit", "rate-limit", "limit exceeded", "usage")):
        return "provider_quota_or_rate_limit"
    if any(token in text for token in ("timeout", "timed out", "eof", "connection")):
        return "provider_transport"
    if any(token in text for token in ("validation", "route_validation", "model", "unsupported")):
        return "route_validation_failed"
    if any(token in text for token in ("approval", "permission", "denied")):
        return "approval_or_permission"
    return "runtime_failure"


def _provider_capability_contract_for_mission(
    mission: Mission,
    *,
    runtime_lanes: list[dict] | None = None,
) -> dict:
    provider_truth = mission.state.provider_runtime_truth if isinstance(mission.state.provider_runtime_truth, dict) else {}
    active_route = provider_truth.get("activeRoute") if isinstance(provider_truth.get("activeRoute"), dict) else {}
    lanes = list(runtime_lanes) if runtime_lanes is not None else _runtime_lane_rows_for_mission(mission)
    provider_rows: dict[str, dict] = {}
    for lane in lanes:
        if not isinstance(lane, dict):
            continue
        provider = str(lane.get("provider") or "").strip().lower()
        if not provider:
            continue
        row = provider_rows.setdefault(
            provider,
            {
                "provider": provider,
                "roles": [],
                "models": [],
                "readyRoles": 0,
                "blockedRoles": 0,
                "authPresent": False,
                "authPath": "",
                "authMode": "",
                "health": "unknown",
                "blockers": [],
                "failureClasses": [],
                "toolFamilies": [],
                "quota": {},
            },
        )
        role = str(lane.get("role") or "").strip().lower()
        if role and role not in row["roles"]:
            row["roles"].append(role)
        model = str(lane.get("model") or "").strip()
        if model and model not in row["models"]:
            row["models"].append(model)
        if bool(lane.get("authPresent")):
            row["authPresent"] = True
            row["readyRoles"] += 1
        else:
            row["blockedRoles"] += 1
        auth_path = str(lane.get("authPath") or "").strip()
        if auth_path and not row["authPath"]:
            row["authPath"] = auth_path
        auth_mode = str(lane.get("authMode") or "").strip()
        if auth_mode and not row["authMode"]:
            row["authMode"] = auth_mode
        for tool in _provider_tool_families(provider, roles=row["roles"], model=model):
            if tool not in row["toolFamilies"]:
                row["toolFamilies"].append(tool)
        if not row["quota"]:
            row["quota"] = lane.get("quota") if isinstance(lane.get("quota"), dict) else _provider_quota_truth(
                provider,
                auth_present=bool(lane.get("authPresent")),
                provider_truth=provider_truth,
            )
        blocker = str(lane.get("blocker") or "").strip()
        if blocker and blocker not in row["blockers"]:
            row["blockers"].append(blocker)
        failure_class = str(lane.get("failureClass") or _provider_failure_class(blocker)).strip()
        if failure_class and failure_class != "none" and failure_class not in row["failureClasses"]:
            row["failureClasses"].append(failure_class)

    providers = []
    for row in provider_rows.values():
        if row["blockedRoles"]:
            row["health"] = "blocked"
        elif row["readyRoles"]:
            row["health"] = "ready"
        providers.append(
            {
                **row,
                "roles": sorted(row["roles"]),
                "models": row["models"][:4],
                "blockers": row["blockers"][:3],
                "failureClasses": row["failureClasses"][:3],
                "toolFamilies": sorted(row["toolFamilies"])[:10],
                "quota": row["quota"] or _provider_quota_truth(
                    str(row.get("provider") or ""),
                    auth_present=bool(row.get("authPresent")),
                    provider_truth=provider_truth,
                ),
            }
        )
    providers.sort(key=lambda item: (item["health"] != "blocked", item["provider"]))

    active_provider = str(active_route.get("provider") or "").strip().lower()
    active_provider_row = next((item for item in providers if item["provider"] == active_provider), {})
    blocked_lanes = [lane for lane in lanes if isinstance(lane, dict) and str(lane.get("health") or "") == "blocked"]
    ready_lanes = [lane for lane in lanes if isinstance(lane, dict) and str(lane.get("health") or "") == "ready"]
    active_auth_present = bool(provider_truth.get("authPresent")) or bool(active_provider_row.get("authPresent"))
    if blocked_lanes:
        status = "blocked"
        next_action = str(blocked_lanes[0].get("blocker") or "Repair or authenticate the blocked provider lane.")
    elif active_provider and active_auth_present:
        status = "ready"
        next_action = "Provider route is authenticated and ready for the current mission phase."
    elif active_provider:
        status = "auth_missing"
        next_action = f"Authenticate {active_provider} before this mission can use the active route."
    else:
        status = "unresolved"
        next_action = "Resolve the mission route contract before dispatching provider work."

    return {
        "schema": "fluxio.provider_capability_contract.v1",
        "source": "live_mission_route_truth",
        "liveData": True,
        "missionId": mission.mission_id,
        "runtimeId": mission.runtime_id,
        "harnessId": mission.harness_id,
        "currentPhase": str(provider_truth.get("currentPhase") or mission.state.current_cycle_phase or "execute"),
        "activeRoute": active_route,
        "status": status,
        "readyLaneCount": len(ready_lanes),
        "blockedLaneCount": len(blocked_lanes),
        "laneCount": len(lanes),
        "quotaSummary": {
            "schema": "fluxio.provider_quota_summary.v1",
            "reportedProviders": sum(
                1
                for item in providers
                if isinstance(item.get("quota"), dict)
                and item["quota"].get("status") not in {"unreported", "unavailable", ""}
            ),
            "unreportedProviders": sum(
                1
                for item in providers
                if isinstance(item.get("quota"), dict)
                and item["quota"].get("status") == "unreported"
            ),
            "nextAction": "Attach runtime/provider quota reports to this contract when a provider exposes them.",
        },
        "toolSummary": {
            "schema": "fluxio.provider_tool_summary.v1",
            "families": sorted({tool for item in providers for tool in item.get("toolFamilies", [])}),
        },
        "failureSummary": {
            "schema": "fluxio.provider_failure_summary.v1",
            "classes": sorted(
                {failure for item in providers for failure in item.get("failureClasses", [])}
            ),
        },
        "providers": providers,
        "lanes": lanes,
        "interchangeable": bool(providers) and not blocked_lanes,
        "nextAction": next_action,
        "updatedAt": str(provider_truth.get("updatedAt") or mission.updated_at or ""),
    }


def _build_runtime_compartments_snapshot(
    root: Path,
    missions: list[Mission],
    *,
    runtime_statuses: list | None = None,
    setup_health: dict | None = None,
    storage_bridge: dict | None = None,
    provider_auth_presence: dict[str, bool] | None = None,
) -> dict:
    items: list[dict] = []
    seen_ids: set[str] = set()

    compartment_dir = root / ".agent_control" / "runtime_compartments"
    if compartment_dir.exists():
        for path in sorted(compartment_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            session_id = str(payload.get("sessionId") or path.stem).strip()
            if not session_id:
                continue
            seen_ids.add(session_id)
            timeline = payload.get("toolTimeline") if isinstance(payload.get("toolTimeline"), list) else []
            route = payload.get("route") if isinstance(payload.get("route"), dict) else {}
            state = str(payload.get("state") or payload.get("status") or "recorded")
            streaming = str(payload.get("streaming") or payload.get("lifecycle") or "recorded")
            items.append(
                {
                    "id": session_id,
                    "sessionId": session_id,
                    "runtime": str(payload.get("runtime") or "codex"),
                    "status": state,
                    "state": state,
                    "lifecycle": streaming,
                    "streaming": streaming,
                    "cwd": str(payload.get("cwd") or ""),
                    "host": str(payload.get("host") or ""),
                    "route": route,
                    "updatedAt": str(payload.get("updatedAt") or ""),
                    "source": "web_backend_compartment",
                    "recentActivity": timeline[-8:],
                    "toolTimeline": timeline[-12:],
                    "messages": payload.get("messages")
                    if isinstance(payload.get("messages"), list)
                    else [],
                    "lanes": payload.get("lanes") if isinstance(payload.get("lanes"), list) else [],
                    "blockers": payload.get("blockers") if isinstance(payload.get("blockers"), list) else [],
                    "actions": payload.get("actions") if isinstance(payload.get("actions"), list) else ["open-proof"],
                    "restartControls": payload.get("restartControls")
                    if isinstance(payload.get("restartControls"), dict)
                    else {},
                    "filesChanged": payload.get("filesChanged")
                    if isinstance(payload.get("filesChanged"), list)
                    else [],
                    "approvals": payload.get("approvals") if isinstance(payload.get("approvals"), list) else [],
                }
            )

    for mission in missions:
        for session in mission.delegated_runtime_sessions or []:
            session_id = session.delegated_id or session.session_path or f"{mission.mission_id}:{session.runtime_id}"
            if session_id in seen_ids:
                continue
            seen_ids.add(session_id)
            recent_events = session.latest_events[-8:] if isinstance(session.latest_events, list) else []
            lanes = _runtime_lane_rows_for_mission(mission, session)
            blockers = [
                lane["blocker"]
                for lane in lanes
                if isinstance(lane, dict) and str(lane.get("blocker") or "").strip()
            ]
            items.append(
                {
                    "id": session_id,
                    "sessionId": session.delegated_id,
                    "missionId": mission.mission_id,
                    "missionTitle": mission.title or mission.objective,
                    "runtime": session.runtime_id or mission.runtime_id,
                    "status": session.status or mission.state.status,
                    "state": session.status or mission.state.status,
                    "lifecycle": (
                        "live"
                        if session.status in {"queued", "launching", "running", "waiting_for_approval"}
                        else "recorded"
                    ),
                    "streaming": (
                        "live"
                        if session.status in {"queued", "launching", "running", "waiting_for_approval"}
                        else "recorded"
                    ),
                    "cwd": session.execution_root or session.workspace_root,
                    "host": session.host_locality,
                    "route": {
                        "phase": session.target_phase,
                        "role": session.target_role,
                        "provider": session.target_provider,
                        "model": session.target_model,
                        "effort": session.target_effort,
                    },
                    "updatedAt": session.updated_at,
                    "source": "delegated_runtime_session",
                    "recentActivity": recent_events,
                    "toolTimeline": recent_events,
                    "messages": [],
                    "lanes": lanes,
                    "blockers": blockers,
                    "actions": [
                        "resume" if session.status in {"running", "waiting_for_approval", "failed", "stopped"} else "inspect-events",
                        "open-proof",
                        "restart",
                    ],
                    "restartControls": {
                        "canRestart": True,
                        "canResume": session.status in {"running", "waiting_for_approval", "failed", "stopped"},
                    },
                    "filesChanged": session.changed_files,
                    "approvals": session.approval_history,
                    "heartbeat": {
                        "status": session.heartbeat_status,
                        "at": session.heartbeat_at,
                        "ageSeconds": session.heartbeat_age_seconds,
                    },
                }
            )

    def sort_key(item: dict) -> str:
        return str(item.get("updatedAt") or "")

    items.sort(key=sort_key, reverse=True)
    live_count = sum(1 for item in items if item.get("lifecycle") == "live")
    compartments = _build_control_compartment_overview(
        root,
        runtime_statuses=runtime_statuses,
        setup_health=setup_health,
        storage_bridge=storage_bridge,
        provider_auth_presence=provider_auth_presence,
    )
    return {
        "items": items[:40],
        "compartments": compartments,
        "summary": {
            "total": len(items),
            "live": live_count,
            "recorded": len(items) - live_count,
            "controlCompartments": len(compartments),
        },
        "emptyState": (
            "No live runtime compartment has been recorded yet. Send a live Agent chat or start a mission to create one."
            if not items
            else ""
        ),
        "source": "agent_control_runtime_state",
    }


def _build_system_audit_digest(
    *,
    root: Path,
    release_readiness: dict,
    harness_lab: dict,
    missions: list[Mission],
    workspaces: list[Workspace],
) -> dict:
    route_trust = (
        harness_lab.get("routeTrustCoverage", {})
        if isinstance(harness_lab.get("routeTrustCoverage"), dict)
        else {}
    )
    operator_confidence = int(route_trust.get("operatorConfidenceScore") or 0)
    proven_task_count = int(route_trust.get("provenTaskCount") or 0)
    task_coverage = (
        route_trust.get("taskCoverage", [])
        if isinstance(route_trust.get("taskCoverage"), list)
        else []
    )
    task_count = max(6, len(task_coverage))
    missing_value_samples = sum(
        max(
            0,
            int(item.get("requiredOperatorValueSamples") or 2)
            - int(item.get("operatorValueSamples") or 0),
        )
        for item in task_coverage
        if isinstance(item, dict)
    )
    if not task_coverage:
        missing_value_samples = 12
    score_cap_reason = (
        "No tracked task category has enough value-scored live route trust evidence yet."
        if proven_task_count < task_count
        else "Route trust is sufficiently sampled; keep value-scored closeouts current."
    )
    categories = [
        {
            "category": "Launch friction and beginner experience",
            "fluxioScore": 17 if proven_task_count < task_count else 19,
            "t3Score": 18,
            "nextAction": "Publish the package entrypoint or add a signed desktop installer.",
        },
        {
            "category": "Multi-project Builder operations",
            "fluxioScore": 18 if proven_task_count < task_count else 20,
            "t3Score": 17,
            "nextAction": "Use per-project history to recommend dependency-aware next missions.",
        },
        {
            "category": "Harness and sub-agent capability",
            "fluxioScore": 16 if proven_task_count < task_count else 19,
            "t3Score": 18,
            "nextAction": "Run repeated value-scored missions per task category.",
        },
        {
            "category": "Web availability and distribution",
            "fluxioScore": 18 if proven_task_count < task_count else 19,
            "t3Score": 18,
            "nextAction": "Publish or tag release candidates with proof archives.",
        },
        {
            "category": "Proof, verification, and trust",
            "fluxioScore": 18 if proven_task_count < task_count else 20,
            "t3Score": 14,
            "nextAction": "Attach release proof archives to public or signed release candidates.",
        },
        {
            "category": "Speed and long-history performance",
            "fluxioScore": 18 if proven_task_count < task_count else 19,
            "t3Score": 18,
            "nextAction": "Publish long-history CI proof beside release candidates.",
        },
        {
            "category": "Roadmap clarity and self-improvement",
            "fluxioScore": 16 if proven_task_count < task_count else 19,
            "t3Score": 14,
            "nextAction": "Run the next self-improvement benchmark and close it with value feedback.",
        },
    ]
    deficits = [
        {
            **item,
            "delta": int(item["fluxioScore"]) - int(item["t3Score"]),
            "blockingGap": score_cap_reason,
        }
        for item in categories
        if int(item["fluxioScore"]) <= int(item["t3Score"])
    ]
    deficits.sort(key=lambda item: (item["delta"], item["fluxioScore"], item["category"]))
    t3_reference = _t3_code_reference_snapshot(root)
    system_loss_breakdown = _system_loss_breakdown(
        categories=categories,
        deficits=deficits,
        score_cap_reason=score_cap_reason,
        route_trust={
            **route_trust,
            "missingOperatorValueSamples": missing_value_samples,
            "provenTaskCount": proven_task_count,
            "taskCount": task_count,
        },
        red_summary={},
        release=release_readiness,
        live_progress={},
    )
    active_missions = [
        mission
        for mission in missions
        if mission.state.status not in TERMINAL_MISSION_STATUSES and mission.state.status != "draft"
    ]
    active_gap_missions = []
    for mission in active_missions[:8]:
        active_gap_missions.append(
            {
                "missionId": mission.mission_id,
                "title": mission.title or mission.objective,
                "workspaceId": mission.workspace_id,
                "runtimeId": mission.runtime_id,
                "status": mission.state.status,
                "plannerLoopStatus": mission.state.planner_loop_status,
                "latestSessionId": mission.state.latest_session_id or "",
                "updatedAt": mission.updated_at,
                "gapSignal": _mission_gap_signal(mission),
            }
        )
    gate_summary = release_readiness.get("requiredGateSummary") or {}
    fallback_digest = {
        "schema": "fluxio.system_audit_digest.v1",
        "generatedAt": utc_now_iso(),
        "source": "control_room_heuristic",
        "releaseStatus": release_readiness.get("status", "unknown"),
        "releaseScore": int(release_readiness.get("score") or 0),
        "requiredGatesPassed": int(gate_summary.get("passed") or 0),
        "requiredGatesTotal": int(gate_summary.get("total") or 0),
        "operatorConfidenceScore": operator_confidence,
        "routeTrustStatus": "sampling_needed" if proven_task_count < task_count else "proven",
        "provenTaskCount": proven_task_count,
        "taskCount": task_count,
        "missingOperatorValueSamples": missing_value_samples,
        "scoreCapReason": score_cap_reason,
        "mustBeatStatus": {
            "ahead": len(categories) - len(deficits),
            "total": len(categories),
            "deficitCount": len(deficits),
        },
        "t3Reference": {
            **t3_reference,
            "strengthsToBeat": [
                "npx t3 launch",
                "BYO provider subscriptions",
                "mid-thread model switching",
                "worktrees",
                "diff review",
                "one-click PR creation",
                "perceived UI speed",
            ],
        },
        "categories": categories,
        "deficits": deficits,
        "systemLossBreakdown": system_loss_breakdown,
        "nextAction": (
            deficits[0]["nextAction"]
            if deficits
            else "All tracked categories are above the T3 reference; keep sampling live outcomes."
        ),
        "improvementQueue": _system_improvement_queue(
            bad_first=[],
            deficits=deficits,
            red_summary={},
            route_trust={},
            live_progress={},
        ),
        "liveProjectProgress": {
            "workspaceCount": len(workspaces),
            "missionCount": len(missions),
            "activeMissionCount": len(active_missions),
            "runningMissionIds": [
                mission.mission_id
                for mission in active_missions
                if mission.state.status == "running"
            ][:6],
        },
        "activeGapMissions": active_gap_missions,
        "publicLaunchReadiness": _public_launch_readiness_digest(root),
    }
    return _authoritative_system_audit_digest(root, fallback_digest) or fallback_digest


def _build_bootstrap_system_audit_digest(
    *,
    root: Path,
    missions: list[Mission],
    workspaces: list[Workspace],
) -> dict:
    t3_reference = _t3_code_reference_snapshot(root)
    active_missions = [
        mission
        for mission in missions
        if mission.state.status not in TERMINAL_MISSION_STATUSES and mission.state.status != "draft"
    ]
    categories = [
        {
            "category": "Launch friction and beginner experience",
            "fluxioScore": 17,
            "t3Score": 18,
            "nextAction": "Publish the package entrypoint or add a signed desktop installer.",
        },
        {
            "category": "Multi-project Builder operations",
            "fluxioScore": 18,
            "t3Score": 17,
            "nextAction": "Keep live project history and dependency-aware queue state visible in Builder.",
        },
        {
            "category": "Harness and sub-agent capability",
            "fluxioScore": 16,
            "t3Score": 18,
            "nextAction": "Run another value-scored Hermes route sample and verify planner/executor/verifier lanes.",
        },
        {
            "category": "Web availability and distribution",
            "fluxioScore": 18,
            "t3Score": 18,
            "nextAction": "Publish or tag release candidates with proof archives.",
        },
        {
            "category": "Proof, verification, and trust",
            "fluxioScore": 18,
            "t3Score": 14,
            "nextAction": "Attach release proof archives to public or signed release candidates.",
        },
        {
            "category": "Speed and long-history performance",
            "fluxioScore": 18,
            "t3Score": 18,
            "nextAction": "Keep bootstrap summary and long-history proof checks below budget.",
        },
        {
            "category": "Roadmap clarity and self-improvement",
            "fluxioScore": 16,
            "t3Score": 14,
            "nextAction": "Run the next self-improvement benchmark and close it with value feedback.",
        },
    ]
    deficits = [
        {
            **item,
            "delta": int(item["fluxioScore"]) - int(item["t3Score"]),
            "blockingGap": "Bootstrap digest uses conservative caps until the full live system audit is loaded.",
        }
        for item in categories
        if int(item["fluxioScore"]) <= int(item["t3Score"])
    ]
    deficits.sort(key=lambda item: (item["delta"], item["fluxioScore"], item["category"]))
    live_progress = {
        "workspaceCount": len(workspaces),
        "missionCount": len(missions),
        "activeMissionCount": len(active_missions),
        "completedMissionCount": sum(1 for mission in missions if mission.state.status == "completed"),
        "blockedMissionCount": sum(
            1
            for mission in missions
            if mission.state.status in {"blocked", "needs_approval", "verification_failed"}
        ),
        "queuedMissionCount": sum(
            1
            for mission in missions
            if mission.state.status not in TERMINAL_MISSION_STATUSES and mission.state.queue_position > 0
        ),
    }
    route_trust = {
        "status": "bootstrap_pending_full_audit",
        "operatorConfidenceScore": 0,
        "provenTaskCount": 0,
        "taskCount": 6,
        "missingOperatorValueSamples": 12,
        "nextAction": "Load the full live system audit, then close missing value-scored route samples.",
    }
    system_loss_breakdown = _system_loss_breakdown(
        categories=categories,
        deficits=deficits,
        score_cap_reason="Bootstrap digest uses conservative caps until the full live system audit is loaded.",
        route_trust=route_trust,
        red_summary={},
        release={},
        live_progress=live_progress,
    )
    fallback_digest = {
        "schema": "fluxio.system_audit_digest.v1",
        "generatedAt": utc_now_iso(),
        "source": "bootstrap_control_room_heuristic",
        "systemScoreOutOf20": round(
            sum(int(item["fluxioScore"]) for item in categories) / max(len(categories), 1),
            1,
        ),
        "operatorConfidenceScore": 0,
        "routeTrustStatus": "bootstrap_pending_full_audit",
        "provenTaskCount": 0,
        "taskCount": 6,
        "missingOperatorValueSamples": 12,
        "scoreCapReason": "Bootstrap digest uses conservative caps until the full live system audit is loaded.",
        "mustBeatStatus": {
            "ahead": len(categories) - len(deficits),
            "total": len(categories),
            "deficitCount": len(deficits),
        },
        "t3Reference": {
            **t3_reference,
            "strengthsToBeat": [
                "npx t3 launch",
                "BYO provider subscriptions",
                "mid-thread model switching",
                "worktrees",
                "diff review",
                "one-click PR creation",
                "perceived UI speed",
            ],
        },
        "categories": categories,
        "deficits": deficits,
        "systemLossBreakdown": system_loss_breakdown,
        "badFirst": [
            {
                "title": item["category"],
                "detail": item["blockingGap"],
            }
            for item in deficits[:4]
        ],
        "improvementQueue": _system_improvement_queue(
            bad_first=[],
            deficits=deficits,
            red_summary={},
            route_trust=route_trust,
            live_progress=live_progress,
        ),
        "liveProjectProgress": live_progress,
        "activeGapMissions": [
            {
                "missionId": mission.mission_id,
                "title": mission.title or mission.objective,
                "workspaceId": mission.workspace_id,
                "runtimeId": mission.runtime_id,
                "status": mission.state.status,
                "plannerLoopStatus": mission.state.planner_loop_status,
                "latestSessionId": mission.state.latest_session_id or "",
                "updatedAt": mission.updated_at,
                "gapSignal": _mission_gap_signal(mission),
            }
            for mission in active_missions[:8]
        ],
        "nextAction": (
            deficits[0]["nextAction"]
            if deficits
            else "Load the full live system audit and keep value-scored outcomes current."
        ),
        "publicLaunchReadiness": _public_launch_readiness_digest(root),
    }
    return _authoritative_system_audit_digest(root, fallback_digest) or fallback_digest


def _public_launch_readiness_digest(root: Path, source: dict | None = None) -> dict:
    latest_payload = _load_json_file(
        root / ".agent_control" / "public_launch_readiness" / "latest.json"
    )
    payload = source if isinstance(source, dict) else latest_payload
    if (
        isinstance(source, dict)
        and latest_payload.get("schema") == "fluxio.public_launch_readiness.v1"
    ):
        source_checked_at = _parse_iso_datetime(str(source.get("checkedAt") or ""))
        latest_checked_at = _parse_iso_datetime(str(latest_payload.get("checkedAt") or ""))
        if latest_checked_at and (not source_checked_at or latest_checked_at >= source_checked_at):
            payload = latest_payload
    if not isinstance(payload, dict) or payload.get("schema") != "fluxio.public_launch_readiness.v1":
        return {
            "schema": "fluxio.public_launch_readiness_digest.v1",
            "status": "missing",
            "ok": False,
            "internalPacketReady": False,
            "missing": ["public_launch_readiness"],
            "blockers": [
                {
                    "checkId": "public_launch_readiness",
                    "details": "Run verify:public-launch so Builder can show public launch blockers.",
                }
            ],
            "nextAction": "Run verify:public-launch and publish the current evidence.",
        }
    missing = [
        str(item)
        for item in payload.get("missing", [])
        if str(item or "").strip()
    ] if isinstance(payload.get("missing"), list) else []
    blockers = [
        {
            "checkId": str(item.get("checkId") or ""),
            "details": str(item.get("details") or ""),
        }
        for item in payload.get("blockers", [])
        if isinstance(item, dict)
    ] if isinstance(payload.get("blockers"), list) else []
    checks = [
        {
            "checkId": str(item.get("checkId") or ""),
            "passed": bool(item.get("passed")),
            "details": str(item.get("details") or ""),
            "url": str(item.get("url") or item.get("controlUrl") or ""),
            "workflowRun": str(item.get("workflowRun") or ""),
            "sourceDirtyPathCount": int(item.get("sourceDirtyPathCount") or 0),
            "sourceDirtyPathSample": [
                str(path)
                for path in item.get("sourceDirtyPathSample", [])
                if str(path or "").strip()
            ][:20] if isinstance(item.get("sourceDirtyPathSample"), list) else [],
        }
        for item in payload.get("checks", [])
        if isinstance(item, dict) and str(item.get("checkId") or "").strip()
    ] if isinstance(payload.get("checks"), list) else []
    return {
        "schema": "fluxio.public_launch_readiness_digest.v1",
        "status": str(payload.get("status") or "unknown"),
        "ok": bool(payload.get("ok")),
        "internalPacketReady": bool(payload.get("internalPacketReady")),
        "checks": checks,
        "missing": missing,
        "blockers": blockers[:6],
        "repairPacket": (
            payload.get("repairPacket", {})
            if isinstance(payload.get("repairPacket"), dict)
            else {}
        ),
        "publicWeb": payload.get("publicWeb", {}) if isinstance(payload.get("publicWeb"), dict) else {},
        "publicationProof": (
            payload.get("publicationProof", {})
            if isinstance(payload.get("publicationProof"), dict)
            else {}
        ),
        "stagingProof": (
            payload.get("stagingProof", {})
            if isinstance(payload.get("stagingProof"), dict)
            else {}
        ),
        "releaseCandidate": (
            payload.get("releaseCandidate", {})
            if isinstance(payload.get("releaseCandidate"), dict)
            else {}
        ),
        "nextAction": str(payload.get("nextAction") or ""),
        "checkedAt": str(payload.get("checkedAt") or ""),
    }


def _authoritative_system_audit_digest(root: Path, fallback_digest: dict) -> dict:
    evidence_path = root / ".agent_control" / "live_nas_system_audit_latest.json"
    cached_digest = _load_compact_system_audit_digest(root, evidence_path, fallback_digest)
    if cached_digest:
        return cached_digest
    payload = _load_json_file(evidence_path)
    if not isinstance(payload, dict):
        return {}
    audit = payload.get("audit") if isinstance(payload.get("audit"), dict) else payload
    if not isinstance(audit, dict) or not isinstance(audit.get("categories"), list):
        return {}

    categories: list[dict] = []
    for item in audit.get("categories", []):
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "").strip()
        if not category:
            continue
        fluxio_score = int(item.get("score_out_of_20") or item.get("fluxioScore") or 0)
        t3_score = int(item.get("t3_reference_score_out_of_20") or item.get("t3Score") or 0)
        next_moves = item.get("next_moves") if isinstance(item.get("next_moves"), list) else []
        gaps = item.get("gaps") if isinstance(item.get("gaps"), list) else []
        categories.append(
            {
                "category": category,
                "fluxioScore": fluxio_score,
                "t3Score": t3_score,
                "delta": fluxio_score - t3_score,
                "verdict": str(item.get("verdict") or ""),
                "blockingGap": str(gaps[0] if gaps else ""),
                "nextAction": str(next_moves[0] if next_moves else ""),
            }
        )

    if not categories:
        return {}

    deficits: list[dict] = []
    for item in audit.get("t3Deficits", []):
        if not isinstance(item, dict):
            continue
        deficits.append(
            {
                "category": str(item.get("category") or ""),
                "fluxioScore": int(item.get("fluxioScore") or 0),
                "t3Score": int(item.get("t3Score") or 0),
                "delta": int(item.get("delta") or 0),
                "blockingGap": str(item.get("blockingGap") or ""),
                "nextAction": str(item.get("nextMove") or item.get("nextAction") or ""),
            }
        )
    if not deficits:
        deficits = [item for item in categories if int(item.get("fluxioScore") or 0) <= int(item.get("t3Score") or 0)]
    deficits.sort(key=lambda item: (int(item.get("delta") or 0), int(item.get("fluxioScore") or 0), item.get("category") or ""))

    route_trust = audit.get("routeTrustMaturity") if isinstance(audit.get("routeTrustMaturity"), dict) else {}
    release = audit.get("releaseReadiness") if isinstance(audit.get("releaseReadiness"), dict) else {}
    public_launch_readiness = _public_launch_readiness_digest(
        root,
        audit.get("publicLaunchReadinessEvidence")
        if isinstance(audit.get("publicLaunchReadinessEvidence"), dict)
        else None,
    )
    gate_summary = release.get("requiredGateSummary") if isinstance(release.get("requiredGateSummary"), dict) else {}
    live_nas = audit.get("liveNasEvidence") if isinstance(audit.get("liveNasEvidence"), dict) else {}
    red_team = audit.get("redTeamEscalationEvidence") if isinstance(audit.get("redTeamEscalationEvidence"), dict) else {}
    watchdog_self_improvement = _watchdog_self_improvement_history_digest(root)
    red_summary = red_team.get("summary") if isinstance(red_team.get("summary"), dict) else {}
    red_history = red_team.get("history") if isinstance(red_team.get("history"), list) else []
    red_latest = normalize_red_team_pressure(red_history[-1]) if red_history and isinstance(red_history[-1], dict) else {}
    effective_red_summary = {
        **red_latest,
        **red_summary,
    }
    if not int(effective_red_summary.get("currentPressureIndex") or 0):
        effective_red_summary["currentPressureIndex"] = int(red_latest.get("currentPressureIndex") or 0)
    if not int(effective_red_summary.get("nextPressureIndex") or 0):
        effective_red_summary["nextPressureIndex"] = int(red_latest.get("nextPressureIndex") or 0)
    if not int(effective_red_summary.get("pressureDelta") or 0):
        effective_red_summary["pressureDelta"] = int(red_latest.get("pressureDelta") or 0)
    if not str(effective_red_summary.get("nextDifficultyLabel") or ""):
        effective_red_summary["nextDifficultyLabel"] = str(red_latest.get("nextDifficultyLabel") or "")
    normalized_red_history = [
        normalize_red_team_pressure(item)
        for item in red_history
        if isinstance(item, dict)
    ]
    generated_red_plan = _red_team_next_benchmark_plan(
        normalized_red_history,
        red_team.get("escalationAudit") if isinstance(red_team.get("escalationAudit"), dict) else {},
    )
    embedded_red_plan = red_team.get("nextBenchmarkPlan") if isinstance(red_team.get("nextBenchmarkPlan"), dict) else {}
    effective_red_plan = {
        **generated_red_plan,
        **embedded_red_plan,
    }
    for key in (
        "difficultyLabel",
        "levelCapReached",
        "currentPressureIndex",
        "nextPressureIndex",
        "pressureDelta",
        "successCriteria",
    ):
        if key not in embedded_red_plan or embedded_red_plan.get(key) in ("", None, [], {}):
            effective_red_plan[key] = generated_red_plan.get(key)
    if not isinstance(effective_red_plan.get("command"), dict) or "pressure" not in str(
        effective_red_plan.get("command", {}).get("shell") or ""
    ):
        effective_red_plan["command"] = generated_red_plan.get("command", {})
    benchmark = (audit.get("benchmarks") or {}).get("t3Code") if isinstance(audit.get("benchmarks"), dict) else {}
    if not isinstance(benchmark, dict):
        benchmark = {}
    bad_first = audit.get("badFirst") if isinstance(audit.get("badFirst"), list) else []
    first_bad = next((item for item in bad_first if isinstance(item, dict)), {})
    score_cap_reason = (
        str(route_trust.get("capReason") or "")
        or str(first_bad.get("detail") or "")
        or str(fallback_digest.get("scoreCapReason") or "")
    )
    active_gap_missions = fallback_digest.get("activeGapMissions") if isinstance(fallback_digest.get("activeGapMissions"), list) else []
    live_progress = fallback_digest.get("liveProjectProgress") if isinstance(fallback_digest.get("liveProjectProgress"), dict) else {}
    counts = live_nas.get("counts") if isinstance(live_nas.get("counts"), dict) else {}
    if counts:
        live_progress = {
            **live_progress,
            "workspaceCount": int(counts.get("workspaces") or live_progress.get("workspaceCount") or 0),
            "missionCount": int(counts.get("missions") or live_progress.get("missionCount") or 0),
            "activeMissionCount": int(counts.get("activeMissions") or live_progress.get("activeMissionCount") or 0),
            "completedMissionCount": int(counts.get("completedMissions") or 0),
            "blockedMissionCount": int(counts.get("blockedMissions") or 0),
            "queuedMissionCount": int(counts.get("queuedMissions") or 0),
        }
    t3_strengths = [
        "npx t3 launch",
        "BYO provider subscriptions",
        "mid-thread model switching",
        "worktrees",
        "diff review",
        "one-click PR creation",
        "perceived UI speed",
    ]
    observed_strengths = benchmark.get("observedStrengths") if isinstance(benchmark.get("observedStrengths"), list) else []
    if observed_strengths:
        t3_strengths = [str(item) for item in observed_strengths[:8]]
    current_t3_reference = _t3_code_reference_snapshot(root)
    current_t3_release = str(current_t3_reference.get("latestObservedRelease") or "")
    if "not been refreshed" in current_t3_release.lower():
        current_t3_release = ""
    system_loss_breakdown = _system_loss_breakdown(
        categories=categories,
        deficits=deficits,
        score_cap_reason=score_cap_reason,
        route_trust=route_trust,
        red_summary=effective_red_summary,
        release=release,
        live_progress=live_progress,
    )

    digest = {
        **fallback_digest,
        "source": "live_nas_system_audit",
        "evidencePath": str(evidence_path),
        "generatedAt": str(audit.get("generatedAt") or payload.get("checkedAt") or utc_now_iso()),
        "summary": str(audit.get("summary") or ""),
        "systemScoreOutOf20": round(
            sum(int(item.get("fluxioScore") or 0) for item in categories) / max(len(categories), 1),
            1,
        ),
        "releaseStatus": release.get("status", fallback_digest.get("releaseStatus", "unknown")),
        "releaseScore": int(release.get("score") or fallback_digest.get("releaseScore") or 0),
        "requiredGatesPassed": int(gate_summary.get("passed") or fallback_digest.get("requiredGatesPassed") or 0),
        "requiredGatesTotal": int(gate_summary.get("total") or fallback_digest.get("requiredGatesTotal") or 0),
        "operatorConfidenceScore": int(route_trust.get("operatorConfidenceScore") or fallback_digest.get("operatorConfidenceScore") or 0),
        "routeTrustStatus": str(route_trust.get("status") or fallback_digest.get("routeTrustStatus") or "unknown"),
        "provenTaskCount": int(route_trust.get("provenTaskCount") or fallback_digest.get("provenTaskCount") or 0),
        "taskCount": int(route_trust.get("taskCount") or fallback_digest.get("taskCount") or 0),
        "missingOperatorValueSamples": int(route_trust.get("missingOperatorValueSamples") or 0),
        "scoreCapReason": score_cap_reason,
        "mustBeatStatus": {
            "ahead": len(categories) - len(deficits),
            "total": len(categories),
            "deficitCount": len(deficits),
        },
        "t3Reference": {
            **current_t3_reference,
            "name": str(benchmark.get("name") or current_t3_reference.get("name") or "T3 Code"),
            "latestObservedRelease": str(
                benchmark.get("latestObservedRelease")
                or current_t3_release
                or fallback_digest.get("t3Reference", {}).get("latestObservedRelease")
                or ""
            ),
            "strengthsToBeat": t3_strengths,
        },
        "categories": categories,
        "deficits": deficits,
        "systemLossBreakdown": system_loss_breakdown,
        "publicLaunchReadiness": public_launch_readiness,
        "badFirst": bad_first[:6],
        "improvementQueue": _system_improvement_queue(
            bad_first=bad_first,
            deficits=deficits,
            red_summary=effective_red_summary,
            route_trust=route_trust,
            live_progress=live_progress,
        ),
        "redTeamEscalation": {
            "schema": str(red_team.get("schema") or "fluxio.red_team_escalation_snapshot.v1"),
            "summary": effective_red_summary,
            "history": [
                item
                for item in red_history[-8:]
                if isinstance(item, dict)
            ],
            "nextBenchmarkPlan": effective_red_plan,
            "historyRows": int(effective_red_summary.get("runCount") or 0),
            "latestResistanceScore": int(effective_red_summary.get("latestResistanceScore") or effective_red_summary.get("resistance_score") or 0),
            "latestDifficultyLevel": int(effective_red_summary.get("latestDifficultyLevel") or effective_red_summary.get("difficultyLevel") or 0),
            "nextDifficultyLevel": int(effective_red_summary.get("nextDifficultyLevel") or 0),
            "currentPressureIndex": int(effective_red_summary.get("currentPressureIndex") or 0),
            "nextPressureIndex": int(effective_red_summary.get("nextPressureIndex") or 0),
            "pressureDelta": int(effective_red_summary.get("pressureDelta") or 0),
            "nextDifficultyLabel": str(effective_red_summary.get("nextDifficultyLabel") or ""),
            "nextAttemptBudget": int(effective_red_summary.get("nextAttemptBudget") or 0),
            "passStreak": int(effective_red_summary.get("passStreak") or 0),
            "pendingEscalationTargets": int(effective_red_summary.get("pendingEscalationTargets") or 0),
            "nextAction": str(effective_red_summary.get("nextAction") or ""),
        },
        "watchdogSelfImprovement": watchdog_self_improvement,
        "nextAction": (
            deficits[0]["nextAction"]
            if deficits
            else str(route_trust.get("nextAction") or effective_red_summary.get("nextAction") or fallback_digest.get("nextAction") or "")
        ),
        "liveProjectProgress": live_progress,
        "activeGapMissions": active_gap_missions,
    }
    _write_compact_system_audit_digest(root, evidence_path, digest)
    return digest


def _compact_system_audit_cache_path(root: Path) -> Path:
    return root / ".agent_control" / "system_audit_digest_latest.json"


def _system_audit_source_stat(evidence_path: Path) -> dict:
    try:
        stat = evidence_path.stat()
    except OSError:
        return {}
    return {
        "path": str(evidence_path),
        "mtimeNs": int(stat.st_mtime_ns),
        "sizeBytes": int(stat.st_size),
    }


def _load_compact_system_audit_digest(root: Path, evidence_path: Path, fallback_digest: dict) -> dict:
    source_stat = _system_audit_source_stat(evidence_path)
    if not source_stat:
        return {}
    payload = _load_json_file(_compact_system_audit_cache_path(root))
    if not isinstance(payload, dict):
        return {}
    if payload.get("schema") != "fluxio.compact_system_audit_digest_cache.v1":
        return {}
    if payload.get("sourceEvidence") != source_stat:
        return {}
    digest = payload.get("digest") if isinstance(payload.get("digest"), dict) else {}
    if not digest:
        return {}
    compact_breakdown = digest.get("systemLossBreakdown") if isinstance(digest.get("systemLossBreakdown"), dict) else {}
    if "averageScoreOutOf20" not in compact_breakdown or "averageLossOutOf20" not in compact_breakdown:
        return {}
    live_progress = dict(digest.get("liveProjectProgress") or {})
    current_progress = fallback_digest.get("liveProjectProgress")
    if isinstance(current_progress, dict):
        live_progress.update(current_progress)
    return {
        **fallback_digest,
        **digest,
        "liveProjectProgress": live_progress,
        "activeGapMissions": (
            fallback_digest.get("activeGapMissions")
            if isinstance(fallback_digest.get("activeGapMissions"), list)
            else digest.get("activeGapMissions", [])
        ),
        "compactCache": {
            "schema": "fluxio.compact_system_audit_digest_cache_hit.v1",
            "sourceEvidence": source_stat,
            "path": str(_compact_system_audit_cache_path(root)),
        },
    }


def _write_compact_system_audit_digest(root: Path, evidence_path: Path, digest: dict) -> None:
    source_stat = _system_audit_source_stat(evidence_path)
    if not source_stat:
        return
    path = _compact_system_audit_cache_path(root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema": "fluxio.compact_system_audit_digest_cache.v1",
                    "generatedAt": utc_now_iso(),
                    "sourceEvidence": source_stat,
                    "digest": ControlRoomStore._summary_system_audit_digest_payload(digest),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        return


def _watchdog_self_improvement_history_digest(root: Path) -> dict:
    evidence_dir = root / ".agent_control" / "self_improvement_evidence"
    history_path = evidence_dir / "watchdog_history.jsonl"
    latest_path = evidence_dir / "watchdog_latest.json"
    latest = _load_json_file(latest_path)
    if not isinstance(latest, dict):
        latest = {}

    rows: deque[dict] = deque(maxlen=6)
    total_rows = 0
    completed_rows = 0
    failed_rows = 0
    if history_path.exists():
        try:
            with history_path.open("r", encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        payload = json.loads(stripped)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    total_rows += 1
                    status = str(payload.get("status") or "").lower()
                    if status == "completed":
                        completed_rows += 1
                    elif status in {"failed", "error"}:
                        failed_rows += 1
                    rows.append(payload)
        except OSError:
            rows.clear()
            total_rows = 0
            completed_rows = 0
            failed_rows = 0

    last_row = rows[-1] if rows else {}
    latest_status = str(latest.get("status") or last_row.get("status") or "missing")
    latest_generated_at = str(
        latest.get("generatedAt")
        or latest.get("lastAttemptAt")
        or last_row.get("generatedAt")
        or last_row.get("lastAttemptAt")
        or ""
    )
    next_attempt_budget = int(latest.get("nextAttemptBudget") or last_row.get("nextAttemptBudget") or 0)
    latest_history_index = int(
        latest.get("historyIndex")
        or last_row.get("historyIndex")
        or total_rows
        or 0
    )
    if total_rows and completed_rows == total_rows:
        next_action = "Keep the external watchdog active until several completed self-improvement receipts form a trend."
    elif total_rows:
        next_action = "Inspect failed or skipped watchdog self-improvement receipts before trusting the cadence trend."
    else:
        next_action = "Run mission-watchdog with --advance-self-improvement so the supervisor creates append-only cadence evidence."

    return {
        "schema": "fluxio.watchdog_self_improvement_history_digest.v1",
        "historyPath": str(history_path),
        "latestPath": str(latest_path),
        "historyExists": history_path.exists(),
        "historyRows": total_rows,
        "completedReceipts": completed_rows,
        "failedReceipts": failed_rows,
        "latestStatus": latest_status,
        "latestGeneratedAt": latest_generated_at,
        "latestHistoryIndex": latest_history_index,
        "latestCompletedSteps": int(latest.get("completedSteps") or last_row.get("completedSteps") or 0),
        "nextAttemptBudget": next_attempt_budget,
        "nextPlanStatus": str(latest.get("nextPlanStatus") or last_row.get("nextPlanStatus") or ""),
        "trendReady": total_rows >= 3 and completed_rows >= 3 and failed_rows == 0,
        "recentReceipts": [
            {
                "historyIndex": int(item.get("historyIndex") or index + 1),
                "status": str(item.get("status") or "unknown"),
                "generatedAt": str(item.get("generatedAt") or item.get("lastAttemptAt") or ""),
                "completedSteps": int(item.get("completedSteps") or 0),
                "nextAttemptBudget": int(item.get("nextAttemptBudget") or 0),
            }
            for index, item in enumerate(rows)
        ],
        "nextAction": next_action,
    }


def _system_improvement_queue(
    *,
    bad_first: list,
    deficits: list,
    red_summary: dict,
    route_trust: dict,
    live_progress: dict,
) -> list[dict]:
    queue: list[dict] = []
    seen: set[str] = set()

    def add_item(
        item_id: str,
        *,
        title: str,
        lane: str,
        priority: int,
        status: str,
        detail: str,
        next_action: str,
    ) -> None:
        normalized_id = re.sub(r"[^a-z0-9_:-]+", "-", item_id.lower()).strip("-") or f"item-{len(queue) + 1}"
        if normalized_id in seen:
            return
        seen.add(normalized_id)
        queue.append(
            {
                "id": normalized_id,
                "title": title,
                "lane": lane,
                "priority": max(0, min(100, int(priority))),
                "status": status,
                "detail": detail,
                "nextAction": next_action,
            }
        )

    for index, item in enumerate(bad_first):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "Current system gap").strip()
        detail = str(item.get("detail") or "").strip()
        lane = _system_improvement_lane(title, detail)
        add_item(
            f"bad-first-{index}-{title}",
            title=title,
            lane=lane,
            priority=max(95 - index * 5, 70),
            status="open",
            detail=detail,
            next_action=_system_improvement_next_action(title, detail),
        )

    for item in deficits:
        if not isinstance(item, dict):
            continue
        title = str(item.get("category") or "T3 category deficit").strip()
        detail = str(item.get("blockingGap") or "").strip()
        add_item(
            f"t3-deficit-{title}",
            title=title,
            lane="T3 parity",
            priority=96,
            status="must_beat",
            detail=detail,
            next_action=str(item.get("nextAction") or "Close this category before claiming full parity."),
        )

    red_next = str(red_summary.get("nextAction") or "").strip()
    if red_next:
        add_item(
            "red-team-escalation-next",
            title="Red-team escalation",
            lane="Self-improvement",
            priority=82,
            status="scheduled",
            detail=(
                f"{int(red_summary.get('runCount') or 0)} history rows, "
                f"{int(red_summary.get('latestResistanceScore') or 0)} latest resistance, "
                f"{int(red_summary.get('nextAttemptBudget') or 0)} next attempts."
            ),
            next_action=red_next,
        )

    route_next = str(route_trust.get("nextAction") or route_trust.get("nextRepairStep") or "").strip()
    if route_next:
        add_item(
            "route-trust-maintenance",
            title="Route trust maintenance",
            lane="Harness routing",
            priority=74 if str(route_trust.get("status") or "") == "operator_proven" else 90,
            status=str(route_trust.get("status") or "unknown"),
            detail=(
                f"{int(route_trust.get('provenTaskCount') or 0)}/"
                f"{int(route_trust.get('taskCount') or 0)} task categories proven, "
                f"{int(route_trust.get('missingOperatorValueSamples') or 0)} value samples missing."
            ),
            next_action=route_next,
        )

    if live_progress:
        add_item(
            "live-project-progress-watch",
            title="Live project advancement",
            lane="Builder operations",
            priority=70,
            status="watching",
            detail=(
                f"{int(live_progress.get('missionCount') or 0)} missions, "
                f"{int(live_progress.get('activeMissionCount') or 0)} active, "
                f"{int(live_progress.get('completedMissionCount') or 0)} completed."
            ),
            next_action="Keep project progress visible in Builder and verify active mission threads stay live.",
        )

    queue.sort(key=lambda item: (-int(item.get("priority") or 0), str(item.get("title") or "")))
    return queue[:8]


def _system_improvement_lane(title: str, detail: str) -> str:
    text = f"{title} {detail}".lower()
    if any(token in text for token in ("launch", "beginner", "installer", "registry", "signed")):
        return "Launch and onboarding"
    if any(token in text for token in ("speed", "history", "performance", "ci artifact")):
        return "Speed and release proof"
    if any(token in text for token in ("builder", "multi-project", "project")):
        return "Builder operations"
    if any(token in text for token in ("harness", "sub-agent", "route", "model")):
        return "Harness routing"
    if any(token in text for token in ("phone", "tablet", "notification", "telegram")):
        return "Notifications"
    return "System quality"


def _system_improvement_next_action(title: str, detail: str) -> str:
    text = f"{title} {detail}".lower()
    if any(token in text for token in ("registry", "signed", "installer", "publication")):
        return "Publish the package entrypoint externally or produce a signed installer proof.";
    if "notification" in text or "telegram" in text:
        return "Configure and verify an out-of-band mobile notification destination.";
    if "speed" in text or "history" in text:
        return "Attach long-history and build proof artifacts beside the release candidate.";
    if "builder" in text or "multi-project" in text:
        return "Keep live project history and dependency-aware queue state visible in Builder.";
    if "harness" in text or "sub-agent" in text or "route" in text:
        return "Run another value-scored Hermes route sample and verify planner/executor/verifier lanes.";
    return "Convert this audit gap into a verified mission or release gate.";


def _mission_gap_signal(mission: Mission) -> str:
    text = " ".join(
        [
            mission.title or "",
            mission.objective or "",
            mission.workspace_id or "",
        ]
    ).lower()
    if "fusion" in text:
        return "Harness and self-improvement"
    if any(token in text for token in ("builder", "phone", "tablet", "frontend", "progress")) or re.search(r"\bui\b", text):
        return "Beginner UX and Builder"
    if any(token in text for token in ("public-data", "investigation", "research", "rf", "wireless", "geoint")):
        return "Multi-project discovery"
    if any(token in text for token in ("harness", "sub-agent", "sub agent", "watchdog")):
        return "Harness and self-improvement"
    if any(token in text for token in ("red team", "red-team", "security", "defensive")):
        return "Red-team calibration"
    return "Route-trust sampling"


def _t3_code_reference_snapshot(root: Path) -> dict:
    benchmark = _load_json_file(root / ".agent_control" / "t3_code_benchmark_latest.json")
    if not isinstance(benchmark, dict):
        return {
            "name": "T3 Code",
            "latestObservedRelease": (
                "T3 Code benchmark has not been refreshed in this workspace yet."
            ),
            "source": "",
        }
    stable = benchmark.get("latestStable") if isinstance(benchmark.get("latestStable"), dict) else {}
    prerelease = (
        benchmark.get("latestPrerelease")
        if isinstance(benchmark.get("latestPrerelease"), dict)
        else {}
    )
    observed = str(benchmark.get("latestObservedRelease") or "").strip()
    if not observed:
        observed = (
            f"{stable.get('tag', 'unknown stable')} stable published "
            f"{stable.get('publishedAt', 'unknown')}; "
            f"{prerelease.get('tag', 'unknown pre-release')} pre-release published "
            f"{prerelease.get('publishedAt', 'unknown')}"
        )
    return {
        "name": "T3 Code",
        "latestObservedRelease": observed,
        "stableTag": str(stable.get("tag") or ""),
        "stableUrl": str(stable.get("url") or ""),
        "prereleaseTag": str(prerelease.get("tag") or ""),
        "prereleaseUrl": str(prerelease.get("url") or ""),
        "checkedAt": str(benchmark.get("checkedAt") or ""),
        "source": str(benchmark.get("source") or ""),
    }


def _severity_label(value: int) -> str:
    if value >= 75:
        return "critical"
    if value >= 50:
        return "high"
    if value >= 25:
        return "medium"
    return "low"


def _system_loss_breakdown(
    *,
    categories: list[dict],
    deficits: list[dict],
    score_cap_reason: str,
    route_trust: dict,
    red_summary: dict,
    release: dict,
    live_progress: dict,
) -> dict:
    drivers: list[dict] = []
    seen: set[str] = set()
    scored_categories = [
        item
        for item in categories
        if isinstance(item, dict)
        and str(item.get("category") or "").strip()
        and str(item.get("fluxioScore") or "").strip() != ""
    ]
    category_scores = [
        max(0.0, min(20.0, float(item.get("fluxioScore") or 0)))
        for item in scored_categories
    ]
    average_score = round(sum(category_scores) / max(len(category_scores), 1), 1) if category_scores else 0.0
    average_loss = round(max(0.0, 20.0 - average_score), 1)
    ahead_count = sum(
        1
        for item in scored_categories
        if float(item.get("fluxioScore") or 0) > float(item.get("t3Score") or 0)
    )

    def add_driver(
        driver_id: str,
        *,
        title: str,
        lane: str,
        severity: int,
        detail: str,
        next_action: str,
        evidence: str,
    ) -> None:
        normalized_id = re.sub(r"[^a-z0-9_:-]+", "-", driver_id.lower()).strip("-")
        if not normalized_id or normalized_id in seen:
            return
        seen.add(normalized_id)
        capped = max(0, min(100, int(severity)))
        drivers.append(
            {
                "id": normalized_id,
                "title": title,
                "category": title,
                "lane": lane,
                "loss": capped,
                "lossOutOf20": round(capped / 100 * 20, 1),
                "severity": _severity_label(capped),
                "primaryGap": detail,
                "detail": detail,
                "nextAction": next_action,
                "evidence": evidence,
            }
        )

    for item in deficits[:5]:
        if not isinstance(item, dict):
            continue
        fluxio_score = int(item.get("fluxioScore") or 0)
        t3_score = int(item.get("t3Score") or 0)
        delta = int(item.get("delta") or (fluxio_score - t3_score))
        severity = min(100, max(35, (20 - fluxio_score) * 5 + abs(delta) * 8))
        title = str(item.get("category") or "T3 parity gap")
        add_driver(
            f"t3-{title}",
            title=title,
            lane="T3 parity",
            severity=severity,
            detail=str(item.get("blockingGap") or score_cap_reason or "Fluxio is not ahead of T3 in this category yet."),
            next_action=str(item.get("nextAction") or "Close this category before claiming full parity."),
            evidence=f"Fluxio {fluxio_score}/20 versus T3 {t3_score}/20.",
        )

    missing_value_samples = int(route_trust.get("missingOperatorValueSamples") or 0)
    if missing_value_samples > 0:
        add_driver(
            "route-trust-missing-value-samples",
            title="Route trust is under-sampled",
            lane="Harness routing",
            severity=min(100, 30 + missing_value_samples * 6),
            detail=score_cap_reason or "Live task routes still need operator value-scored closeouts.",
            next_action=str(route_trust.get("nextAction") or route_trust.get("nextRepairStep") or "Run value-scored route trust missions."),
            evidence=(
                f"{int(route_trust.get('provenTaskCount') or 0)}/"
                f"{int(route_trust.get('taskCount') or 0)} task categories proven; "
                f"{missing_value_samples} value samples missing."
            ),
        )

    gate_summary = release.get("requiredGateSummary") if isinstance(release.get("requiredGateSummary"), dict) else {}
    missing_gates = max(
        0,
        int(gate_summary.get("total") or 0) - int(gate_summary.get("passed") or 0),
    )
    if missing_gates > 0:
        add_driver(
            "release-gates-not-green",
            title="Release proof is incomplete",
            lane="Release proof",
            severity=min(100, 35 + missing_gates * 12),
            detail="Release/distribution trust still depends on required proof gates.",
            next_action="Attach public or signed release proof archives and rerun the release verifier.",
            evidence=(
                f"{int(gate_summary.get('passed') or 0)}/"
                f"{int(gate_summary.get('total') or 0)} required gates passing."
            ),
        )

    pending_red_targets = int(red_summary.get("pendingEscalationTargets") or 0)
    next_attempt_budget = int(red_summary.get("nextAttemptBudget") or 0)
    if pending_red_targets > 0 or next_attempt_budget > 0:
        add_driver(
            "red-team-escalation-pressure",
            title="Red-team difficulty must keep rising",
            lane="Self-improvement",
            severity=min(100, 38 + pending_red_targets * 14 + max(0, next_attempt_budget - 3) * 2),
            detail="Defensive improvement is only meaningful if the next benchmark becomes harder after clean passes.",
            next_action=str(red_summary.get("nextAction") or "Run the next aggregate-only red-team benchmark."),
            evidence=(
                f"{int(red_summary.get('runCount') or 0)} history rows; "
                f"difficulty {int(red_summary.get('latestDifficultyLevel') or 0)} -> "
                f"{int(red_summary.get('nextDifficultyLevel') or 0)}; "
                f"next attempts {next_attempt_budget}."
            ),
        )

    active_count = int(live_progress.get("activeMissionCount") or 0)
    mission_count = int(live_progress.get("missionCount") or 0)
    if mission_count > 0 and active_count == 0:
        add_driver(
            "no-active-live-missions",
            title="No active live missions",
            lane="Builder operations",
            severity=45,
            detail="The system cannot prove ongoing hands-free operation without an active mission row.",
            next_action="Launch or resume at least one live Hermes mission and keep its detail endpoint visible.",
            evidence=f"{mission_count} missions, {active_count} active.",
        )

    if not drivers:
        add_driver(
            "keep-sampling",
            title="Keep sampling live outcomes",
            lane="System quality",
            severity=12,
            detail="No critical loss driver is visible in the current digest.",
            next_action="Keep value-scored missions, release proof, and red-team escalation current.",
            evidence="All tracked T3 categories are currently above the reference.",
        )

    drivers.sort(key=lambda item: (-int(item.get("loss") or 0), str(item.get("title") or "")))
    score = max(int(item.get("loss") or 0) for item in drivers) if drivers else 0
    return {
        "schema": "fluxio.system_loss_breakdown.v1",
        "averageScoreOutOf20": average_score,
        "averageLossOutOf20": average_loss,
        "mustBeatStatus": {
            "ahead": ahead_count,
            "total": len(scored_categories),
            "deficitCount": len(deficits),
        },
        "score": score,
        "severity": _severity_label(score),
        "driverCount": len(drivers),
        "drivers": drivers[:8],
        "nextAction": str(
            drivers[0].get("nextAction")
            if drivers
            else "Keep value-scored missions, release proof, and red-team escalation current."
        ),
    }


def _artifact_api_url(path: Path) -> str:
    return f"/api/artifact?{urlencode({'id': _safe_artifact_id(path)})}"


SAFE_ARTIFACT_SUFFIXES = {
    ".apng",
    ".avif",
    ".gif",
    ".jpeg",
    ".jpg",
    ".json",
    ".jsonl",
    ".log",
    ".md",
    ".png",
    ".svg",
    ".txt",
    ".webp",
}


def _artifact_api_url_if_safe(path: Path) -> str:
    return _artifact_api_url(path) if path.exists() and path.suffix.lower() in SAFE_ARTIFACT_SUFFIXES else ""


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


def _recover_evidence_path(root: Path, raw_path: object) -> Path:
    raw = str(raw_path or "").strip()
    candidates: list[Path] = []
    if raw:
        candidate = Path(raw)
        candidates.append(candidate if candidate.is_absolute() else root / candidate)
        normalized = raw.replace("\\", "/")
        if re.match(r"^[A-Za-z]:[\\/]", raw):
            candidates.append(_platform_path_for_windows_drive(raw))
        embedded_windows = re.search(r"([A-Za-z]:[\\/][^\r\n]+)$", raw)
        if embedded_windows:
            candidates.append(_platform_path_for_windows_drive(embedded_windows.group(1)))
        embedded_normalized = re.search(r"([A-Za-z]:/[^\r\n]+)$", normalized)
        if embedded_normalized:
            candidates.append(_platform_path_for_windows_drive(embedded_normalized.group(1)))
        if normalized.startswith("/volume1/"):
            volume_relative = normalized[len("/volume1/") :]
            candidates.append(Path("C:/volume1") / volume_relative)
            if os.name != "nt":
                candidates.append(Path("/mnt/c/volume1") / volume_relative)
        direct_hits: list[Path] = []
        seen_direct: set[str] = set()
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            if not resolved.exists():
                continue
            key = str(resolved)
            if key in seen_direct:
                continue
            seen_direct.add(key)
            direct_hits.append(resolved)
        if direct_hits:
            return direct_hits[0]
        return candidates[0] if candidates else root
        name = Path(normalized).name
        if name:
            for search_root in (
                root / ".agent_control" / "runtime_sessions",
                root / ".agent_control" / "mission_async",
                root / ".agent_runs",
                Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_control/runtime_sessions"),
                Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_control/mission_async"),
                Path("C:/volume1/Saclay/projects/vibe-coding-platform/.agent_runs"),
            ):
                if search_root.exists():
                    candidates.extend(search_root.rglob(name))
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.exists():
            return resolved
    return candidates[0] if candidates else root


def _path_evidence(path: Path, *, source: str, label: str | None = None) -> dict:
    exists = path.exists()
    timestamp = ""
    if exists:
        try:
            timestamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
        except OSError:
            timestamp = ""
    return {
        "label": label or path.name,
        "path": str(path),
        "exists": exists,
        "timestamp": timestamp,
        "source": source,
        "provenance": "filesystem",
    }


def _latest_matching_files(root: Path, patterns: list[str], *, limit: int = 8) -> list[Path]:
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(root.glob(pattern))
    existing = [item for item in matches if item.exists() and item.is_file()]
    existing.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return existing[:limit]


def _build_control_compartment_overview(
    root: Path,
    *,
    runtime_statuses: list | None = None,
    setup_health: dict | None = None,
    storage_bridge: dict | None = None,
    provider_auth_presence: dict[str, bool] | None = None,
) -> list[dict]:
    runtime_statuses = runtime_statuses or []
    setup_health = setup_health or {}
    storage_bridge = storage_bridge or {}
    provider_auth_presence = provider_auth_presence or _provider_auth_presence_from_env()
    service_summary = setup_health.get("serviceManagementSummary", {}) if isinstance(setup_health, dict) else {}
    total_services = int(service_summary.get("totalItems", 0) or 0) if isinstance(service_summary, dict) else 0
    healthy_services = int(service_summary.get("healthyCount", 0) or 0) if isinstance(service_summary, dict) else 0
    codex_command = shutil.which("codex")
    runtime_bin = root / ".agent_control" / "runtime" / "bin"
    frontend_dist = root / "web" / "dist" / "index.html"
    backend_script = root / "scripts" / "run_web_backend.py"
    nas_doctor = root / "scripts" / "nas_runtime_doctor.py"
    nas_probe = root / "scripts" / "nas_ssh_probe.py"
    codex_auth_ready = bool(provider_auth_presence.get("openai-codex") or provider_auth_presence.get("openai"))
    runtime_evidence = [
        {
            "label": item.label,
            "status": "detected" if item.detected else "missing",
            "source": "runtime_adapter_scan",
            "timestamp": utc_now_iso(),
            "provenance": item.command or item.install_hint or "detect_runtime_statuses",
        }
        for item in runtime_statuses
    ]
    compartments = [
        {
            "id": "setup",
            "label": "Setup",
            "status": "ready" if total_services > 0 and healthy_services == total_services else "offline-safe",
            "ports": [],
            "paths": [str(root / ".agent_control"), str(root / "config")],
            "actions": ["python scripts/nas_runtime_doctor.py --root .", "python scripts/nas_setup.py --help"],
            "evidence": [
                {
                    "label": "setup service health",
                    "source": "onboarding.setupHealth",
                    "timestamp": utc_now_iso(),
                    "provenance": f"{healthy_services}/{total_services} services healthy",
                }
            ],
        },
        {
            "id": "runtime",
            "label": "Runtime",
            "status": "ready" if codex_auth_ready else "blocked",
            "ports": [],
            "paths": [str(runtime_bin), str(root / ".agent_control" / "runtime_sessions")],
            "actions": [
                "syntelos-codex-oauth-helper",
                "codex exec --model gpt-5.5 --sandbox read-only",
            ],
            "evidence": runtime_evidence
            + [
                {
                    "label": "OpenAI Codex OAuth/API auth",
                    "source": "provider_auth_presence",
                    "timestamp": utc_now_iso(),
                    "provenance": "openai-codex" if provider_auth_presence.get("openai-codex") else "openai api key/env",
                    "passed": codex_auth_ready,
                },
                {
                    "label": "Codex CLI",
                    "source": "PATH",
                    "timestamp": utc_now_iso(),
                    "provenance": codex_command or "codex command not found",
                    "passed": bool(codex_command),
                },
            ],
        },
        {
            "id": "backend",
            "label": "Backend",
            "status": "ready" if backend_script.exists() else "blocked",
            "ports": [int(os.environ.get("FLUXIO_WEB_PORT", "47880") or 47880)],
            "paths": [str(backend_script), str(root / ".agent_control" / "web-backend.log")],
            "actions": ["python scripts/run_web_backend.py --host 127.0.0.1 --port 47880"],
            "portSafety": {
                "duplicateListenerPreflight": True,
                "allowOverrideFlag": "--allow-port-reuse",
                "purpose": "avoid starting multiple Fluxio backends on the same local port",
            },
            "evidence": [_path_evidence(backend_script, source="filesystem", label="web backend runner")],
        },
        {
            "id": "frontend",
            "label": "Frontend",
            "status": "ready" if frontend_dist.exists() else "offline-safe",
            "ports": [int(os.environ.get("TAURI_DEV_PORT", "1420") or 1420)],
            "paths": [str(root / "web" / "src"), str(root / "web" / "dist")],
            "actions": ["npm run frontend:build", "npm run frontend:dev"],
            "evidence": [_path_evidence(frontend_dist, source="filesystem", label="built /control shell")],
        },
        {
            "id": "browser",
            "label": "Browser",
            "status": "ready" if frontend_dist.exists() else "offline-safe",
            "ports": [int(os.environ.get("TAURI_DEV_PORT", "1420") or 1420)],
            "paths": ["/control", "/api/backend", "/api/artifact"],
            "actions": ["node scripts/control_route_smoke.mjs", "open http://127.0.0.1:1420/control"],
            "evidence": [
                {
                    "label": "control route contract",
                    "source": "frontend_route",
                    "timestamp": utc_now_iso(),
                    "provenance": "/control served by Vite or web backend SPA fallback",
                }
            ],
        },
        {
            "id": "nas",
            "label": "NAS",
            "status": "ready" if storage_bridge.get("available") else "offline-safe",
            "ports": [22, int(os.environ.get("FLUXIO_WEB_PORT", "47880") or 47880)],
            "paths": [
                str(root / ".agent_control"),
                "/volume1/Saclay/projects/vibe-coding-platform",
                r"C:\volume1\Saclay\projects\vibe-coding-platform",
            ],
            "actions": [
                "python scripts/nas_setup.py --help",
                "python scripts/nas_runtime_doctor.py --root .",
                "python scripts/nas_ssh_probe.py --help",
                "python scripts/nas_ssh_probe.py --host <nas> --port 22 --user <user> --diagnose --cooldown-seconds 20",
            ],
            "portSafety": {
                "guarded": True,
                "ports": [22],
                "cooldownSeconds": 20,
                "windowSeconds": 60,
                "maxAttempts": 6,
                "statePath": str(root / ".agent_control" / "port_safety.json"),
                "purpose": "avoid repeated SSH/SFTP probes overloading NAS port 22",
            },
            "evidence": [
                _path_evidence(nas_doctor, source="filesystem", label="NAS doctor"),
                _path_evidence(nas_probe, source="filesystem", label="NAS SSH probe"),
            ],
        },
    ]
    for compartment in compartments:
        compartment["updatedAt"] = utc_now_iso()
    return compartments


def _build_generated_image_artifacts_snapshot(root: Path) -> dict:
    artifact_roots = [
        root / ".agent_control" / "image_playground_artifacts",
        root / ".agent_control" / "generated_image_artifacts",
        root / ".agent_control" / "design_references",
    ]
    image_suffixes = {".apng", ".avif", ".gif", ".jpeg", ".jpg", ".png", ".webp"}
    min_visual_artifact_bytes = 512
    items: list[dict] = []
    seen_paths: set[str] = set()

    def add_image_artifact(image_path: Path, manifest_path: Path | None = None, manifest: dict | None = None) -> None:
        manifest = manifest if isinstance(manifest, dict) else {}
        try:
            if image_path.stat().st_size < min_visual_artifact_bytes:
                return
        except OSError:
            return
        try:
            key = str(image_path.resolve())
        except OSError:
            key = str(image_path)
        if key in seen_paths:
            return
        seen_paths.add(key)
        items.append(
            {
                "artifactId": str(manifest.get("artifactId") or manifest.get("requestId") or image_path.stem),
                "servedArtifactId": str(manifest.get("servedArtifactId") or _safe_artifact_id(image_path)),
                "requestId": str(manifest.get("requestId") or ""),
                "status": "served",
                "provider": str(manifest.get("provider") or "Syntelos local artifact lane"),
                "operation": str(manifest.get("operation") or "generate"),
                "createdAt": str(
                    manifest.get("createdAt")
                    or datetime.fromtimestamp(image_path.stat().st_mtime, timezone.utc).isoformat()
                ),
                "artifactPath": str(image_path),
                "manifestPath": str(manifest_path or ""),
                "previewUrl": _artifact_api_url(image_path),
                "manifestUrl": _artifact_api_url(manifest_path) if manifest_path else "",
                "contentType": str(manifest.get("contentType") or "image/png"),
                "safeArtifactArea": str(
                    manifest.get("safeArtifactArea")
                    or ".agent_control/design_references/codex_image_artifacts"
                ),
                "localPath": str(manifest.get("localPath") or image_path),
                "nasPathCandidates": manifest.get("nasPathCandidates")
                if isinstance(manifest.get("nasPathCandidates"), list)
                else [],
                "provenance": manifest.get("provenance") if isinstance(manifest.get("provenance"), dict) else {
                    "servedBy": "web-backend",
                    "safeEndpoint": "/api/artifact",
                    "arbitraryWorkspaceFilesExposed": False,
                },
                "metadata": {
                    "artifactSha256": manifest.get("artifactSha256") or "",
                    "manifestSha256": manifest.get("manifestSha256") or "",
                    "prompt": manifest.get("prompt") if isinstance(manifest.get("prompt"), dict) else {},
                    "canvas": manifest.get("canvas") if isinstance(manifest.get("canvas"), dict) else {},
                },
                "source": "generated_image_artifact_manifest" if manifest_path else "generated_image_artifact_file",
            }
        )

    for artifact_root in artifact_roots:
        if not artifact_root.exists():
            continue
        manifest_paths = sorted(
            artifact_root.rglob("*.manifest.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        for manifest_path in manifest_paths[:80]:
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                manifest = {}
            if not isinstance(manifest, dict):
                manifest = {}
            image_path = Path(str(manifest.get("artifactPath") or ""))
            if not image_path.is_absolute():
                image_path = manifest_path.with_suffix("").with_suffix(".png")
            if not image_path.exists():
                manifest_prefix = (
                    manifest_path.name[: -len(".manifest.json")]
                    if manifest_path.name.endswith(".manifest.json")
                    else manifest_path.stem
                )
                sibling_images = [
                    item
                    for item in manifest_path.parent.glob(f"{manifest_prefix}.*")
                    if item.suffix.lower() in image_suffixes
                ]
                image_path = sibling_images[0] if sibling_images else image_path
            if not image_path.exists() or image_path.suffix.lower() not in image_suffixes:
                continue
            add_image_artifact(image_path, manifest_path, manifest)
        direct_images = sorted(
            [item for item in artifact_root.rglob("*") if item.is_file() and item.suffix.lower() in image_suffixes],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        for image_path in direct_images[:120]:
            add_image_artifact(image_path)

    return {
        "items": items[:40],
        "summary": {"total": len(items[:40])},
        "emptyState": (
            "No generated image artifacts are available yet. Generate an image in live mode to create served artifact URLs."
            if not items
            else ""
        ),
        "source": "agent_control_artifact_manifests",
    }


def _build_hermes_mission_evidence(root: Path, missions: list[Mission], activity: list[dict]) -> dict:
    items: list[dict] = []

    for mission in missions:
        mission_is_hermes = str(mission.runtime_id).lower() == "hermes"
        hermes_sessions = [
            session
            for session in mission.delegated_runtime_sessions or []
            if str(session.runtime_id).lower() == "hermes"
        ]
        if mission_is_hermes or hermes_sessions:
            mission_artifacts = []
            proof_artifacts = getattr(mission, "proof_artifacts", None)
            if proof_artifacts is None:
                proof_artifacts = getattr(mission.proof, "artifacts", None)
            for artifact in proof_artifacts or []:
                artifact_text = str(artifact)
                artifact_path = _recover_evidence_path(root, artifact_text)
                mission_artifacts.append(
                    {
                        "label": artifact_path.name or artifact_text,
                        "path": artifact_text,
                        "servedUrl": _artifact_api_url_if_safe(artifact_path),
                        "exists": artifact_path.exists(),
                    }
                )
            command_evidence = []
            for action in mission.action_history[-8:]:
                result = action.get("result", {}) if isinstance(action, dict) else {}
                proposal = action.get("proposal", {}) if isinstance(action, dict) else {}
                command_evidence.append(
                    {
                        "title": str(proposal.get("title") or action.get("action_id") or "action"),
                        "command": str(result.get("command") or result.get("executed_command") or ""),
                        "ok": bool(result.get("ok")) if "ok" in result else not bool(result.get("error")),
                        "summary": str(result.get("result_summary") or result.get("error") or result.get("stdout") or ""),
                        "timestamp": str(action.get("executed_at") or mission.updated_at),
                        "provenance": "mission.action_history",
                    }
                )
            for session in hermes_sessions:
                for raw_path, label, source in (
                    (session.session_path, "session state", "delegated_runtime_session"),
                    (session.events_path, "session events", "delegated_runtime_events"),
                    (session.log_path, "runtime log", "delegated_runtime_log"),
                ):
                    if not raw_path:
                        continue
                    evidence_path = _recover_evidence_path(root, raw_path)
                    mission_artifacts.append(
                        {
                            **_path_evidence(evidence_path, source=source, label=label),
                            "servedUrl": _artifact_api_url_if_safe(evidence_path),
                        }
                    )
            for evidence_path in _latest_matching_files(
                root,
                [
                    ".agent_control/mission_async/*.log",
                ],
                limit=8,
            ):
                mission_artifacts.append(
                    {
                        **_path_evidence(evidence_path, source="run_evidence", label=evidence_path.name),
                        "servedUrl": _artifact_api_url_if_safe(evidence_path),
                    }
                )
            failure_reasons = [
                *[str(item) for item in mission.proof.failed_checks],
                *[str(item) for item in mission.state.verification_failures],
                *[str(item.get("blocker") or "") for item in _runtime_lane_rows_for_mission(mission) if item.get("blocker")],
            ]
            items.append(
                {
                    "timestamp": mission.updated_at,
                    "status": mission.state.status,
                    "source": "mission_summary",
                    "missionId": mission.mission_id,
                    "objective": mission.objective,
                    "successChecks": list(mission.success_checks),
                    "message": mission.proof.summary or mission.title or mission.objective,
                    "artifacts": mission_artifacts,
                    "commandEvidence": command_evidence,
                    "failureReasons": [item for item in failure_reasons if item],
                    "provenance": "mission_control_store",
                }
            )
            for check in mission.proof.passed_checks:
                items.append(
                    {
                        "timestamp": mission.updated_at,
                        "status": "passed",
                        "source": "mission_proof",
                        "missionId": mission.mission_id,
                        "message": str(check),
                        "provenance": "mission.proof.passed_checks",
                    }
                )
            for check in mission.proof.failed_checks:
                items.append(
                    {
                        "timestamp": mission.updated_at,
                        "status": "failed",
                        "source": "mission_proof",
                        "missionId": mission.mission_id,
                        "message": str(check),
                        "provenance": "mission.proof.failed_checks",
                    }
                )
        for session in hermes_sessions:
            for event in session.latest_events[-12:]:
                if not isinstance(event, dict):
                    continue
                kind = str(event.get("kind") or "").lower()
                if not any(token in kind for token in ("proof", "evidence", "runtime", "approval", "session")):
                    continue
                items.append(
                    {
                        "timestamp": _event_timestamp(event) or session.updated_at,
                        "status": str(event.get("status") or session.status or "recorded"),
                        "source": "hermes_runtime_session",
                        "missionId": mission.mission_id,
                        "sessionId": session.delegated_id,
                        "kind": event.get("kind") or "runtime.event",
                        "message": str(event.get("message") or event.get("summary") or session.detail or ""),
                        "provenance": "delegated_runtime_session.latest_events",
                    }
                )

    for event in activity:
        if not isinstance(event, dict):
            continue
        kind = str(event.get("kind") or "").lower()
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        source = str(metadata.get("source") or event.get("source") or "").lower()
        if "hermes" not in kind and "hermes" not in source:
            continue
        items.append(
            {
                "timestamp": _event_timestamp(event),
                "status": str(event.get("status") or metadata.get("status") or "recorded"),
                "source": str(metadata.get("source") or "mission_event"),
                "missionId": str(event.get("mission_id") or event.get("missionId") or ""),
                "kind": event.get("kind") or "mission.event",
                "message": str(event.get("message") or ""),
                "provenance": "mission_events.jsonl",
            }
        )

    for artifact in _build_generated_image_artifacts_snapshot(root).get("items", []):
        if not isinstance(artifact, dict):
            continue
        items.append(
            {
                "timestamp": str(artifact.get("createdAt") or ""),
                "status": "served",
                "source": "generated_artifact_manifest",
                "missionId": "",
                "kind": "artifact.generated",
                "message": str(artifact.get("artifactId") or artifact.get("artifactPath") or "generated artifact"),
                "artifacts": [artifact],
                "provenance": "agent_control_artifact_manifests",
            }
        )

    deduped: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (
            str(item.get("timestamp") or ""),
            str(item.get("source") or ""),
            str(item.get("message") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    deduped.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    return {
        "items": deduped[:40],
        "summary": {
            "total": len(deduped),
            "passed": sum(1 for item in deduped if item.get("status") in {"passed", "completed", "ok"}),
            "failed": sum(1 for item in deduped if item.get("status") in {"failed", "error"}),
        },
        "emptyState": (
            "No Hermes mission evidence has been captured yet. Run a Hermes mission or delegated lane to populate proof events."
            if not deduped
            else ""
        ),
        "source": "mission_events_and_runtime_sessions",
    }


def build_nas_deploy_readiness_snapshot(
    root: Path,
    *,
    onboarding: dict | None = None,
    setup_health: dict | None = None,
    storage_bridge: dict | None = None,
) -> dict:
    root = root.resolve()
    onboarding_payload = onboarding or detect_onboarding_status(root)
    setup_health_payload = setup_health or onboarding_payload.get("setupHealth", {})
    storage_bridge_payload = storage_bridge or {}

    checks = [
        {
            "checkId": "web_backend_script",
            "label": "web backend runner",
            "required": True,
            "passed": (root / "scripts" / "run_web_backend.py").exists(),
            "details": "scripts/run_web_backend.py is present for NAS HTTP serving.",
            "source": "filesystem",
        },
        {
            "checkId": "nas_setup_script",
            "label": "NAS setup script",
            "required": True,
            "passed": (root / "scripts" / "nas_setup.py").exists(),
            "details": "scripts/nas_setup.py is present for offline setup planning.",
            "source": "filesystem",
        },
        {
            "checkId": "doctor_script",
            "label": "NAS runtime doctor",
            "required": True,
            "passed": (root / "scripts" / "nas_runtime_doctor.py").exists(),
            "details": "scripts/nas_runtime_doctor.py is present for operator-run diagnostics.",
            "source": "filesystem",
        },
        {
            "checkId": "web_dist",
            "label": "frontend build assets",
            "required": False,
            "passed": (root / "web" / "dist" / "index.html").exists()
            and (root / "web" / "dist" / "assets").exists(),
            "details": "web/dist/index.html and web/dist/assets exist after npm run frontend:build.",
            "source": "filesystem",
        },
        {
            "checkId": "artifact_serving",
            "label": "safe artifact serving",
            "required": True,
            "passed": True,
            "details": "Generated artifacts are served through /api/artifact with allowed-root resolution.",
            "source": "web_backend_contract",
        },
        {
            "checkId": "runtime_auth_health",
            "label": "runtime/auth health",
            "required": False,
            "passed": bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("FLUXIO_OPENAI_CODEX_OAUTH_PRESENT")),
            "details": (
                "OpenAI Codex route auth is visible to this backend runtime."
                if bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("FLUXIO_OPENAI_CODEX_OAUTH_PRESENT"))
                else "OpenAI Codex auth is not visible in this offline check; runtime launch should block rather than fall back."
            ),
            "source": "environment",
        },
        {
            "checkId": "storage_bridge_mapping",
            "label": "NAS storage mapping",
            "required": False,
            "passed": bool(storage_bridge_payload.get("nas", {}).get("available") or storage_bridge_payload.get("available")),
            "details": str(storage_bridge_payload.get("summary") or "No NAS storage bridge is currently mapped."),
            "source": "control_room_snapshot",
        },
    ]
    service_summary = setup_health_payload.get("serviceManagementSummary", {})
    if isinstance(service_summary, dict):
        total_items = int(service_summary.get("totalItems", 0) or 0)
        healthy_count = int(service_summary.get("healthyCount", 0) or 0)
        checks.append(
            {
                "checkId": "setup_doctor_services",
                "label": "setup doctor services",
                "required": False,
                "passed": total_items > 0 and healthy_count == total_items,
                "details": f"{healthy_count}/{total_items} setup services are healthy.",
                "source": "setupHealth",
            }
        )

    for item in checks:
        item["status"] = "passed" if item["passed"] else ("blocked" if item["required"] else "warn")

    missing_required = [item["label"] for item in checks if item["required"] and not item["passed"]]
    return {
        "ready": not missing_required,
        "checks": checks,
        "missingRequired": missing_required,
        "setupHealth": setup_health_payload,
        "source": "offline_control_room_checks",
        "emptyState": "Run NAS setup or doctor scripts to add live host evidence." if missing_required else "",
    }


def build_release_readiness_snapshot(
    root: Path,
    *,
    onboarding: dict | None = None,
    setup_health: dict | None = None,
    harness_lab: dict | None = None,
) -> dict:
    root = root.resolve()
    onboarding_payload = onboarding or detect_onboarding_status(root)
    setup_health_payload = setup_health or onboarding_payload.get("setupHealth", {})
    harness_lab_payload = harness_lab or build_harness_lab_snapshot(root)
    proving_cycle = _build_proving_cycle_readiness(root)

    checks = onboarding_payload.get("checks", {})
    service_summary = setup_health_payload.get("serviceManagementSummary", {})
    efficiency = harness_lab_payload.get("efficiency", {})
    session_health = harness_lab_payload.get("sessionHealth", {})

    verify_desktop_ok, verify_desktop_detail = _verify_desktop_script_contract(root)
    frontend_alignment_ok, frontend_alignment_detail = _verify_frontend_source_alignment(root)
    release_artifact_ci_ok, release_artifact_ci_detail = _verify_release_artifact_ci_contract(root)
    public_web_distribution_ok, public_web_distribution_detail = _verify_public_web_distribution_contract(root)
    self_improvement_evidence_ok, self_improvement_evidence_detail = _verify_self_improvement_evidence_contract(root)
    watchdog_gate = _build_mission_watchdog_release_gate(root)
    required_total_items = int(service_summary.get("totalItems", 0) or 0)
    required_healthy_count = int(service_summary.get("healthyCount", 0) or 0)
    completion_rate = int(efficiency.get("completionRate", 0) or 0)
    delegated_run_rate = int(efficiency.get("delegatedRunRate", 0) or 0)
    resume_run_rate = int(efficiency.get("resumeRunRate", 0) or 0)
    resume_completion_rate = int(efficiency.get("resumeCompletionRate", 0) or 0)
    verification_pause_rate = int(efficiency.get("verificationPauseRate", 0) or 0)
    stale_heartbeat_count = int(session_health.get("staleHeartbeatCount", 0) or 0)

    required_gates = [
        {
            "gateId": "verify_desktop_contract",
            "label": "verify:desktop contract",
            "required": True,
            "passed": verify_desktop_ok,
            "details": verify_desktop_detail,
        },
        {
            "gateId": "frontend_source_alignment",
            "label": "frontend source alignment",
            "required": True,
            "passed": frontend_alignment_ok,
            "details": frontend_alignment_detail,
        },
        {
            "gateId": "uv_installed",
            "label": "uv installed",
            "required": True,
            "passed": bool(checks.get("uv", {}).get("installed")),
            "details": str(checks.get("uv", {}).get("details", "")),
        },
        {
            "gateId": "openclaw_installed",
            "label": "OpenClaw installed",
            "required": True,
            "passed": bool(checks.get("openclaw", {}).get("installed")),
            "details": str(checks.get("openclaw", {}).get("details", "")),
        },
        {
            "gateId": "hermes_installed",
            "label": "Hermes installed",
            "required": True,
            "passed": bool(checks.get("hermes", {}).get("installed")),
            "details": str(checks.get("hermes", {}).get("details", "")),
        },
        {
            "gateId": "setup_required_services_healthy",
            "label": "required setup services healthy",
            "required": True,
            "passed": required_total_items > 0 and required_healthy_count == required_total_items,
            "details": f"{required_healthy_count}/{required_total_items} required setup services are healthy.",
        },
        {
            "gateId": "runtime_heartbeat_stable",
            "label": "delegated heartbeat stable",
            "required": True,
            "passed": stale_heartbeat_count == 0,
            "details": (
                "No stale delegated runtime heartbeat detected."
                if stale_heartbeat_count == 0
                else f"{stale_heartbeat_count} delegated runtime session(s) have stale heartbeat."
            ),
        },
        watchdog_gate,
    ]
    optional_signals = [
        {
            "gateId": "completion_rate",
            "label": "recent completion rate >= 50%",
            "required": False,
            "passed": completion_rate >= 50,
            "details": f"Current completion rate is {completion_rate}%.",
        },
        {
            "gateId": "delegated_run_rate",
            "label": "delegated run rate >= 20%",
            "required": False,
            "passed": delegated_run_rate >= 20,
            "details": f"Current delegated run rate is {delegated_run_rate}%.",
        },
        {
            "gateId": "resume_completion_rate",
            "label": "resume completion rate >= 60%",
            "required": False,
            "passed": resume_run_rate == 0 or resume_completion_rate >= 60,
            "details": (
                "No resumed runs recorded yet."
                if resume_run_rate == 0
                else f"Current resume completion rate is {resume_completion_rate}%."
            ),
        },
        {
            "gateId": "release_artifact_ci",
            "label": "release proof archive enforced in CI",
            "required": False,
            "passed": release_artifact_ci_ok,
            "details": release_artifact_ci_detail,
        },
        {
            "gateId": "public_web_distribution",
            "label": "public web distribution contract",
            "required": False,
            "passed": public_web_distribution_ok,
            "details": public_web_distribution_detail,
        },
        {
            "gateId": "self_improvement_evidence",
            "label": "self-improvement evidence archived",
            "required": False,
            "passed": self_improvement_evidence_ok,
            "details": self_improvement_evidence_detail,
        },
        {
            "gateId": "proof_openclaw_completed",
            "label": "OpenClaw proving mission evidence",
            "required": False,
            "passed": bool(
                next(
                    (
                        item.get("passed", False)
                        for item in proving_cycle.get("proofs", [])
                        if item.get("proofId") == "openclaw_proving_mission"
                    ),
                    False,
                )
            ),
            "details": str(
                next(
                    (
                        item.get("details", "")
                        for item in proving_cycle.get("proofs", [])
                        if item.get("proofId") == "openclaw_proving_mission"
                    ),
                    "",
                )
            ),
        },
        {
            "gateId": "proof_hermes_completed",
            "label": "Hermes delegated mission evidence",
            "required": False,
            "passed": bool(
                next(
                    (
                        item.get("passed", False)
                        for item in proving_cycle.get("proofs", [])
                        if item.get("proofId") == "hermes_delegated_mission"
                    ),
                    False,
                )
            ),
            "details": str(
                next(
                    (
                        item.get("details", "")
                        for item in proving_cycle.get("proofs", [])
                        if item.get("proofId") == "hermes_delegated_mission"
                    ),
                    "",
                )
            ),
        },
    ]
    gates = required_gates + optional_signals
    required_passed = sum(1 for gate in required_gates if gate["passed"])
    required_total = len(required_gates)
    required_score = _percent(required_passed, required_total)
    quality_score = _release_quality_score(
        completion_rate=completion_rate,
        delegated_run_rate=delegated_run_rate,
        resume_run_rate=resume_run_rate,
        resume_completion_rate=resume_completion_rate,
        verification_pause_rate=verification_pause_rate,
    )
    overall_score = int(
        round(
            (required_score * RELEASE_READINESS_WEIGHTS["required"] / 100)
            + (quality_score * RELEASE_READINESS_WEIGHTS["quality"] / 100)
        )
    )

    if required_passed == required_total and overall_score >= 85:
        status = "ready_for_1_0_validation"
    elif required_passed == required_total:
        status = "validation_ready_with_quality_gaps"
    elif required_passed >= max(required_total - 1, 1):
        status = "close_but_blocked"
    else:
        status = "blocked"

    failed_required_actions = [
        f"{gate['label']}: {gate['details']}"
        for gate in required_gates
        if not gate["passed"]
    ]
    next_actions = (
        failed_required_actions
        + list(proving_cycle.get("nextActions", []))
        + list(onboarding_payload.get("nextActions", []))
    )
    return {
        "status": status,
        "score": overall_score,
        "requiredGateSummary": {
            "passed": required_passed,
            "total": required_total,
            "score": required_score,
        },
        "qualityScore": quality_score,
        "qualitySignals": {
            "completionRate": completion_rate,
            "delegatedRunRate": delegated_run_rate,
            "resumeRunRate": resume_run_rate,
            "resumeCompletionRate": resume_completion_rate,
            "verificationPauseRate": verification_pause_rate,
        },
        "proofReadiness": proving_cycle,
        "gates": gates,
        "nextActions": next_actions[:8],
        "calculatedAt": utc_now_iso(),
    }


def _release_mission_items(payload: object) -> list[tuple[str, dict]]:
    if isinstance(payload, dict):
        missions_value = payload.get("missions")
        if isinstance(missions_value, list):
            return _release_mission_items(missions_value)
        return [
            (str(key), value)
            for key, value in payload.items()
            if isinstance(value, dict)
        ]
    if isinstance(payload, list):
        return [
            (str(item.get("mission_id") or item.get("missionId") or item.get("id") or ""), item)
            for item in payload
            if isinstance(item, dict)
        ]
    return []


def _build_mission_watchdog_release_gate(root: Path) -> dict:
    control_dir = root / ".agent_control"
    missions_payload = _load_json_file(control_dir / "missions.json")
    missions = _release_mission_items(missions_payload)
    active_missions = []
    for _, mission in missions:
        state = mission.get("state") if isinstance(mission.get("state"), dict) else {}
        status = str(state.get("status") or mission.get("status") or "").strip().lower()
        if status and status not in TERMINAL_MISSION_STATUSES and status not in {"archived", "draft"}:
            active_missions.append(mission)

    gate = {
        "gateId": "mission_watchdog_clear",
        "label": "mission watchdog clear",
        "required": True,
        "passed": True,
        "details": "No active missions require watchdog release evidence.",
        "activeMissionCount": len(active_missions),
        "watchdogReportPath": str(control_dir / "mission_watchdog.json"),
        "problemReportPath": str(control_dir / "mission_watchdog_problems.json"),
    }
    if not active_missions:
        return gate

    report_path = control_dir / "mission_watchdog.json"
    if not report_path.exists():
        gate.update(
            {
                "passed": False,
                "details": (
                    "Active missions exist, but no mission watchdog report was found. "
                    f"Run `python -m grant_agent.cli mission-watchdog --root {root}`."
                ),
            }
        )
        return gate

    report = _load_json_file(report_path)
    if not isinstance(report, dict):
        gate.update(
            {
                "passed": False,
                "details": "Mission watchdog report is unreadable.",
            }
        )
        return gate

    problem_report = report.get("problemReport") if isinstance(report.get("problemReport"), dict) else {}
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    problem_count = int(problem_report.get("problemCount") or 0)
    issue_count = int(summary.get("issueCount") or 0)
    blocking_issue_count = int(summary.get("bad") or 0) + int(summary.get("warn") or 0)
    problem_status = str(problem_report.get("status") or ("open" if problem_count else "clear")).lower()
    supervisor = load_watchdog_supervisor_state(root)
    supervisor_active = bool(supervisor.get("supervisorActive"))
    supervisor_status = str(supervisor.get("status") or "")
    first_problem = problem_report.get("firstProblem") if isinstance(problem_report.get("firstProblem"), dict) else {}
    next_action = str(
        first_problem.get("firstRepairStep")
        or first_problem.get("firstStep")
        or problem_report.get("nextAction")
        or report.get("nextAction")
        or ""
    )
    gate.update(
        {
            "problemCount": problem_count,
            "issueCount": issue_count,
            "blockingIssueCount": blocking_issue_count,
            "problemStatus": problem_status,
            "supervisorActive": supervisor_active,
            "supervisorStatus": supervisor_status,
            "supervisorStale": bool(supervisor.get("stale")),
            "supervisorProcessAlive": bool(supervisor.get("processAlive")),
            "supervisorPid": supervisor.get("processPid", 0),
            "lastRunAt": str(supervisor.get("lastRunAt") or ""),
            "nextRunAt": str(supervisor.get("nextRunAt") or ""),
        }
    )
    if blocking_issue_count > 0:
        gate.update(
            {
                "passed": False,
                "details": (
                    f"Watchdog found {blocking_issue_count} blocking active mission problem(s). "
                    f"First repair step: {next_action or 'open the watchdog problem report'}"
                ),
            }
        )
        return gate
    if not supervisor_active:
        stale_detail = (
            f" Last run: {supervisor.get('lastRunAt') or 'unknown'}; "
            f"next run: {supervisor.get('nextRunAt') or 'unknown'}; "
            f"process alive: {bool(supervisor.get('processAlive'))}; "
            f"status: {supervisor_status or 'unknown'}."
        )
        gate.update(
            {
                "passed": False,
                "details": (
                    "Mission watchdog report is clear, but the external supervisor loop is not active. "
                    "Restart `mission-watchdog --loop --max-runs 0`."
                    + stale_detail
                ),
            }
        )
        return gate

    gate.update(
        {
            "passed": True,
            "details": (
                f"Watchdog clear for {len(active_missions)} active mission(s); "
                f"supervisor PID {supervisor.get('processPid', 0)} is active."
                + (
                    f" {issue_count} non-blocking watchdog info item(s) remain visible."
                    if issue_count
                    else ""
                )
            ),
        }
    )
    return gate


def _build_runtime_session_health(root: Path) -> dict:
    runtime_root = root / ".agent_control" / "runtime_sessions"
    session_paths = sorted(
        runtime_root.glob("delegate_*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ) if runtime_root.exists() else []
    active_count = 0
    waiting_approval_count = 0
    healthy_heartbeat_count = 0
    stale_heartbeat_count = 0
    delegated_healthy_count = 0
    delegated_stale_count = 0
    latest_heartbeat_age_seconds: int | None = None
    latest_status = ""
    for path in session_paths[:16]:
        payload = _load_json_file(path)
        if not isinstance(payload, dict):
            continue
        status = str(payload.get("status", "unknown"))
        heartbeat_status = str(payload.get("heartbeat_status", "unknown"))
        heartbeat_age = payload.get("heartbeat_age_seconds")
        if heartbeat_age is None:
            heartbeat_age = _age_seconds(
                str(payload.get("heartbeat_at") or payload.get("updated_at") or "")
            )
        stale_after = max(int(payload.get("heartbeat_interval_seconds") or 10) * 3, 35)
        effective_heartbeat_status = heartbeat_status
        if status in {"launching", "running", "waiting_for_approval"} and heartbeat_age is not None:
            effective_heartbeat_status = (
                "stale" if heartbeat_age > stale_after else "healthy"
            )
        if heartbeat_age is not None and latest_heartbeat_age_seconds is None:
            latest_heartbeat_age_seconds = heartbeat_age
            latest_status = status
        if status in {"launching", "running", "waiting_for_approval"}:
            active_count += 1
        if status == "waiting_for_approval":
            waiting_approval_count += 1
        if effective_heartbeat_status == "healthy":
            healthy_heartbeat_count += 1
        elif effective_heartbeat_status == "stale":
            stale_heartbeat_count += 1
        if status in {"launching", "running", "waiting_for_approval"}:
            if effective_heartbeat_status == "healthy":
                delegated_healthy_count += 1
            elif effective_heartbeat_status == "stale":
                delegated_stale_count += 1
    delegated_total = delegated_healthy_count + delegated_stale_count
    return {
        "totalSessions": len(session_paths),
        "activeCount": active_count,
        "waitingApprovalCount": waiting_approval_count,
        "healthyHeartbeatCount": healthy_heartbeat_count,
        "staleHeartbeatCount": stale_heartbeat_count,
        "delegatedHealthyCount": delegated_healthy_count,
        "delegatedStaleCount": delegated_stale_count,
        "delegatedHealthyRate": _percent(delegated_healthy_count, delegated_total),
        "latestHeartbeatAgeSeconds": latest_heartbeat_age_seconds,
        "latestStatus": latest_status or "idle",
    }


def _build_runtime_session_health_summary(*, missions: list[Mission]) -> dict:
    sessions: list[DelegatedRuntimeSession] = []
    for mission in missions:
        sessions.extend(mission.delegated_runtime_sessions or [])
    sessions.sort(
        key=lambda item: item.heartbeat_at or item.updated_at or item.created_at or "",
        reverse=True,
    )
    active_count = 0
    waiting_approval_count = 0
    healthy_heartbeat_count = 0
    stale_heartbeat_count = 0
    delegated_healthy_count = 0
    delegated_stale_count = 0
    latest_heartbeat_age_seconds: int | None = None
    latest_status = ""
    for session in sessions[:32]:
        status = str(session.status or "unknown").strip().lower()
        heartbeat_status = str(session.heartbeat_status or "unknown").strip().lower()
        heartbeat_age = session.heartbeat_age_seconds
        if heartbeat_age is None:
            heartbeat_age = _age_seconds(session.heartbeat_at or session.updated_at or "")
        stale_after = max(int(session.heartbeat_interval_seconds or 10) * 3, 35)
        effective_heartbeat_status = heartbeat_status
        if status in {"launching", "running", "waiting_for_approval"} and heartbeat_age is not None:
            effective_heartbeat_status = "stale" if heartbeat_age > stale_after else "healthy"
        if heartbeat_age is not None and latest_heartbeat_age_seconds is None:
            latest_heartbeat_age_seconds = heartbeat_age
            latest_status = status
        if status in {"launching", "running", "waiting_for_approval"}:
            active_count += 1
        if status == "waiting_for_approval":
            waiting_approval_count += 1
        if effective_heartbeat_status == "healthy":
            healthy_heartbeat_count += 1
        elif effective_heartbeat_status == "stale":
            stale_heartbeat_count += 1
        if status in {"launching", "running", "waiting_for_approval"}:
            if effective_heartbeat_status == "healthy":
                delegated_healthy_count += 1
            elif effective_heartbeat_status == "stale":
                delegated_stale_count += 1
    delegated_total = delegated_healthy_count + delegated_stale_count
    return {
        "schema": "fluxio.runtime_session_health.summary.v1",
        "source": "mission_store_delegated_sessions",
        "fullSessionScanDeferred": True,
        "totalSessions": len(sessions),
        "scannedRecentSessions": min(len(sessions), 32),
        "activeCount": active_count,
        "waitingApprovalCount": waiting_approval_count,
        "healthyHeartbeatCount": healthy_heartbeat_count,
        "staleHeartbeatCount": stale_heartbeat_count,
        "delegatedHealthyCount": delegated_healthy_count,
        "delegatedStaleCount": delegated_stale_count,
        "delegatedHealthyRate": _percent(delegated_healthy_count, delegated_total),
        "latestHeartbeatAgeSeconds": latest_heartbeat_age_seconds,
        "latestStatus": latest_status or "idle",
    }


def _harness_efficiency_recommendation(
    *,
    total_runs: int,
    completion_rate: int,
    delegated_run_rate: int,
    resume_run_rate: int,
    resume_completion_rate: int,
    approval_pause_rate: int,
    verification_pause_rate: int,
    stale_heartbeat_count: int,
) -> str:
    if total_runs == 0:
        return (
            "No local harness runs are recorded yet. Start one real mission to measure "
            "pause friction, delegated session health, and verification efficiency."
        )
    if stale_heartbeat_count > 0:
        return (
            "Delegated runtime heartbeat went stale recently. Verify runtime health "
            "before widening unattended autonomy."
        )
    if delegated_run_rate < 20 and total_runs >= 4:
        return (
            "Delegated runtime usage is still low in recent runs. Run more real delegated "
            "missions before claiming long-run readiness."
        )
    if resume_run_rate >= 20 and resume_completion_rate < 60:
        return (
            "Resume continuity is still weak after restart. Improve resume completion "
            "before expanding unattended missions."
        )
    if completion_rate < 50:
        return (
            "Completion rate is below 50% on recent runs. Stabilize runtime and verification "
            "before widening autonomy."
        )
    if approval_pause_rate >= 35:
        return (
            "Approval waits dominate recent runs. Keep the hybrid harness, but reduce "
            "unnecessary approval pressure before widening delegation."
        )
    if verification_pause_rate >= 25:
        return (
            "Verification failures are the main pause source. Improve verification "
            "defaults before increasing autonomy."
        )
    return (
        "Fluxio hybrid looks stable on recent local runs. Keep it as production and "
        "use the legacy harness only as a benchmark."
    )


def _route_trust_label(task_type: str) -> str:
    return ROUTE_TRUST_TASK_LABELS.get(task_type, task_type.replace("_", " ").title())


def _route_trust_task_type(payload: dict) -> str:
    state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
    feedback = state.get("operator_value_feedback") if isinstance(state, dict) else {}
    if isinstance(feedback, dict):
        task_type = str(
            feedback.get("routeTrustTaskType")
            or feedback.get("route_trust_task_type")
            or ""
        ).strip()
        if task_type:
            return task_type
    objective = f" {payload.get('objective') or ''} ".lower()
    for task_type, template in ROUTE_TRUST_SAMPLE_TEMPLATES.items():
        sample_objective = f" {template.get('objective') or ''} ".lower()
        if sample_objective.strip() and sample_objective in objective:
            return task_type
    route_configs = payload.get("route_configs", [])
    if isinstance(route_configs, list):
        for route in route_configs:
            if not isinstance(route, dict):
                continue
            task_type = str(route.get("task_type") or route.get("taskType") or "").strip()
            if task_type:
                return task_type
    best_task = "general_coding"
    best_count = 0
    for task_type, keywords in ROUTE_TRUST_TASK_KEYWORDS.items():
        count = sum(1 for keyword in keywords if keyword in objective)
        if count > best_count:
            best_task = task_type
            best_count = count
    return best_task


def _operator_value_feedback_signal(feedback: object) -> dict:
    if not isinstance(feedback, dict):
        return {}
    try:
        score = int(feedback.get("score"))
    except (TypeError, ValueError):
        score = -1
    outcome = str(feedback.get("outcome") or "").strip().lower()
    trust_signal = str(
        feedback.get("trustSignal") or feedback.get("trust_signal") or ""
    ).strip().lower()
    if score < 0 and not outcome and not trust_signal:
        return {}
    return {
        "score": score,
        "promote": trust_signal == "promote" or outcome == "useful" or score >= 80,
        "deprioritize": trust_signal == "deprioritize" or outcome == "not_useful" or (0 <= score < 50),
    }


def _route_trust_closeout_low_value(item: dict) -> bool:
    try:
        score = int(item.get("score") or item.get("operatorValueScore") or -1)
    except (TypeError, ValueError):
        score = -1
    outcome = str(item.get("outcome") or item.get("operatorOutcome") or "").strip().lower()
    trust_signal = str(item.get("trustSignal") or item.get("trust_signal") or "").strip().lower()
    return (0 <= score < 50) or outcome == "not_useful" or trust_signal == "deprioritize"


def _route_trust_repair_steps(low_value_items: list[dict], coverage: dict[str, dict]) -> list[dict]:
    plan: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in low_value_items:
        task_type = str(item.get("taskType") or "general_coding").strip() or "general_coding"
        mission_id = str(item.get("missionId") or item.get("mission_id") or "").strip()
        key = (task_type, mission_id)
        if key in seen:
            continue
        seen.add(key)
        label = str(coverage.get(task_type, {}).get("label") or _route_trust_label(task_type))
        if task_type == "frontend_design":
            executor_policy = (
                "MiniMax-M2.7 only when authenticated and available; otherwise Codex gpt-5.5 high "
                "with explicit provider-unavailable evidence"
            )
        elif task_type in {"data_f1_analytics", "hardware_electrical", "research_analysis"}:
            executor_policy = "Codex gpt-5.5 high with dataset/artifact/browser-preview verification gates"
        else:
            executor_policy = "Codex gpt-5.5 high until the next value-scored sample proves a better route"
        repair_action = (
            f"Repair the {label} route before another promotion: require a served artifact, "
            "proof digest, browser preview/check result, and operator value closeout before trust can rise."
        )
        try:
            score = int(item.get("score") or item.get("operatorValueScore") or 0)
        except (TypeError, ValueError):
            score = 0
        plan.append(
            {
                "schema": "fluxio.route_trust_repair_step.v1",
                "taskType": task_type,
                "label": label,
                "missionId": mission_id,
                "score": score,
                "missionStatus": str(item.get("missionStatus") or item.get("status") or ""),
                "repairAction": repair_action,
                "modelPolicy": (
                    "Hermes harness; planner/verifier use openai-codex gpt-5.5 high; "
                    f"executor uses {executor_policy}; never claim a provider path when auth/runtime evidence is missing."
                ),
                "trustEffect": "Do not promote this task category until the next sample scores at least 80 with no failed verification.",
            }
        )
    return plan


def _route_trust_row(coverage: dict[str, dict], task_type: str) -> dict:
    return coverage.setdefault(
        task_type,
        {
            "taskType": task_type,
            "label": _route_trust_label(task_type),
            "routeSamples": 0,
            "operatorValueSamples": 0,
            "operatorPromoteCount": 0,
            "operatorDeprioritizeCount": 0,
            "latestMissionId": "",
        },
    )


def _shell_quote(value: object) -> str:
    text = str(value or "")
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _route_trust_sampling_template(
    task_type: str,
    row: dict[str, object],
    *,
    repair: dict[str, object] | None = None,
) -> dict[str, object]:
    template = ROUTE_TRUST_SAMPLE_TEMPLATES.get(
        task_type,
        ROUTE_TRUST_SAMPLE_TEMPLATES["general_coding"],
    )
    label = str(row.get("label") or _route_trust_label(task_type))
    objective = str(template["objective"])
    success_checks = [str(item) for item in template.get("successChecks", []) if str(item).strip()]
    runtime = str(template.get("preferredRuntime") or "auto")
    budget_hours = int(template.get("budgetHours") or 4)
    sample_title = str(template.get("title") or f"{label} trust sample")
    route_intent = (
        "Gather live, value-scored evidence so route and skill trust can move "
        "from static defaults to operator-proven task routing."
    )
    operator_closeout_instruction = (
        "After the artifact is tested, complete the mission with an operator value "
        "score so this category contributes to route and skill trust."
    )
    if repair:
        failed_mission_id = str(repair.get("missionId") or "").strip()
        repair_action = str(repair.get("repairAction") or "").strip()
        model_policy = str(repair.get("modelPolicy") or "").strip()
        sample_title = f"Repair {label} route trust sample"
        objective = (
            f"Repair route trust for {label}"
            + (f" after low-value mission {failed_mission_id}" if failed_mission_id else "")
            + f". {repair_action} Base task: {objective} "
            "Hard requirements: create or serve a reviewable artifact, capture browser/preview proof, "
            "write a proof digest, and only allow route trust to rise after an operator-value closeout "
            "scores at least 80 with no failed verification."
        )
        success_checks = [
            *success_checks,
            "Create or serve a reviewable artifact for this repaired route sample.",
            "Capture browser or preview verification evidence and attach it to the proof digest.",
            "Record why the previous low-value sample failed and what changed in this repair attempt.",
            "Do not promote route trust unless the operator-value closeout is at least 80 with no failed verification.",
        ]
        if model_policy:
            success_checks.append(f"Follow repaired model policy: {model_policy}")
        route_intent = (
            "Repair a low-value route before more sampling: the mission must prove artifact quality, "
            "browser verification, and operator value before trust can recover."
        )
        operator_closeout_instruction = (
            "After testing the repaired artifact, complete this mission with an operator value score; "
            "scores below 80 keep the route in repair."
        )
    query = urlencode(
        {
            "launch": "mission",
            "runtime": runtime,
            "profile": "builder",
            "mode": "Autopilot",
            "objective": objective,
            "successCheck": success_checks,
        },
        doseq=True,
    )
    success_check_args = " ".join(
        f"--success-check {_shell_quote(item)}" for item in success_checks
    )
    cli_command = (
        "python -m grant_agent.cli mission-quickstart --root . "
        f"--runtime {runtime} --mode Autopilot --budget-hours {budget_hours} "
        f"--objective {_shell_quote(objective)}"
    )
    if success_check_args:
        cli_command = f"{cli_command} {success_check_args}"
    return {
        "schema": "fluxio.route_trust_sampling_template.v1",
        "taskType": task_type,
        "label": label,
        "sampleMissionTitle": sample_title,
        "sampleMissionObjective": objective,
        "sampleMissionMode": "Autopilot",
        "sampleMissionRuntime": runtime,
        "sampleMissionBudgetHours": budget_hours,
        "sampleMissionSuccessChecks": success_checks,
        "sampleMissionUrlPath": f"/control?{query}",
        "sampleMissionCliCommand": cli_command,
        "routeIntent": route_intent,
        "operatorCloseoutInstruction": operator_closeout_instruction,
    }


def _build_route_trust_coverage_snapshot(root: Path, *, sessions: list[Path]) -> dict:
    coverage = {
        task_type: {
            "taskType": task_type,
            "label": label,
            "routeSamples": 0,
            "operatorValueSamples": 0,
            "operatorPromoteCount": 0,
            "operatorDeprioritizeCount": 0,
            "latestMissionId": "",
        }
        for task_type, label in ROUTE_TRUST_TASK_LABELS.items()
    }
    for session in sessions[:HARNESS_RECENT_RUN_LIMIT]:
        state_path = session / "state.json"
        if not state_path.exists():
            continue
        payload = _load_json_file(state_path)
        if not isinstance(payload, dict) or not isinstance(payload.get("route_configs"), list):
            continue
        status = str(payload.get("autopilot_status") or "").strip().lower()
        pause_reason = str(payload.get("autopilot_pause_reason") or "").strip().lower()
        if status not in {"completed", "failed", "blocked"} and pause_reason not in {
            "verification_failed",
            "runtime_budget",
            "delegated_runtime_failed",
        }:
            continue
        _route_trust_row(coverage, _route_trust_task_type(payload))["routeSamples"] += 1

    mission_status_by_id: dict[str, str] = {}
    missions_payload = _load_json_file(root / ".agent_control" / "missions.json")
    if isinstance(missions_payload, list):
        for mission in missions_payload:
            if not isinstance(mission, dict):
                continue
            mission_id = str(mission.get("mission_id") or mission.get("missionId") or "").strip()
            state = mission.get("state") if isinstance(mission.get("state"), dict) else {}
            if mission_id:
                mission_status_by_id[mission_id] = str(
                    state.get("status") or mission.get("status") or ""
                ).strip().lower()
            state = mission.get("state") if isinstance(mission.get("state"), dict) else {}
            feedback = _operator_value_feedback_signal(state.get("operator_value_feedback"))
            if not feedback:
                continue
            row = _route_trust_row(coverage, _route_trust_task_type(mission))
            row["operatorValueSamples"] += 1
            row["operatorPromoteCount"] += 1 if feedback.get("promote") else 0
            row["operatorDeprioritizeCount"] += 1 if feedback.get("deprioritize") else 0
            row["latestMissionId"] = str(mission.get("mission_id") or mission.get("missionId") or "")

    sampling_report = _load_json_file(root / ".agent_control" / "route_trust_sampling" / "latest.json")
    closeout_report = _load_json_file(root / ".agent_control" / "route_trust_sampling" / "closeout_review_latest.json")
    launched = (
        sampling_report.get("launchedSamplingMissions", [])
        if isinstance(sampling_report, dict) and isinstance(sampling_report.get("launchedSamplingMissions"), list)
        else []
    )
    active_statuses = {"running", "queued", "launching", "needs_approval", "verification_pending"}
    active_sampling_ids = []
    for item in launched:
        if not isinstance(item, dict):
            continue
        mission_id = str(item.get("missionId") or item.get("mission_id") or "").strip()
        status = mission_status_by_id.get(mission_id) or str(item.get("missionStatus") or item.get("status") or "").strip().lower()
        if mission_id and status in active_statuses:
            active_sampling_ids.append(mission_id)

    closeout_proposals = (
        closeout_report.get("proposals", [])
        if isinstance(closeout_report, dict) and isinstance(closeout_report.get("proposals"), list)
        else []
    )
    low_value_items = [
        item for item in closeout_proposals if isinstance(item, dict) and _route_trust_closeout_low_value(item)
    ]
    repair_plan = _route_trust_repair_steps(low_value_items, coverage)
    repair_by_task = {item["taskType"]: item for item in repair_plan}
    route_outcome_trends = _build_route_outcome_trends_for_trust(root)
    quarantined_routes = _route_outcome_quarantines(route_outcome_trends)
    quarantined_route_count = _quarantined_route_count(quarantined_routes)

    rows = []
    for row in coverage.values():
        value_samples = int(row["operatorValueSamples"])
        useful_samples = int(row.get("operatorPromoteCount") or 0)
        low_value_samples = int(row.get("operatorDeprioritizeCount") or 0)
        missing = max(0, ROUTE_TRUST_REQUIRED_VALUE_SAMPLES - useful_samples)
        status = "proven" if missing == 0 else "sampling"
        repair = repair_by_task.get(str(row["taskType"]))
        repair_required = repair is not None
        rows.append(
            {
                **row,
                "requiredOperatorValueSamples": ROUTE_TRUST_REQUIRED_VALUE_SAMPLES,
                "usefulOperatorValueSamples": useful_samples,
                "lowValueOperatorSamples": low_value_samples,
                "missingOperatorValueSamples": missing,
                "status": "repair" if repair_required else status,
                "repairRequired": repair_required,
                "repairMissionId": repair.get("missionId", "") if repair else "",
                "repairAction": repair.get("repairAction", "") if repair else "",
                "modelPolicy": repair.get("modelPolicy", "") if repair else "",
                **_route_trust_sampling_template(str(row["taskType"]), row, repair=repair),
                "nextAction": (
                    repair["repairAction"]
                    if repair_required
                    else (
                    "Route and skill trust have enough useful value-scored samples for this task category."
                    if status == "proven"
                    else (
                        f"Run {missing} more useful value-scored {row['label']} mission(s); "
                        f"{value_samples} scored sample(s), {low_value_samples} low-value sample(s), "
                        f"and {useful_samples} useful sample(s) are recorded."
                    )
                    )
                ),
            }
        )
    rows.sort(
        key=lambda item: (
            not item["repairRequired"],
            item["status"] != "sampling",
            item["missingOperatorValueSamples"],
            item["taskType"],
        )
    )
    sampling = [item for item in rows if item["status"] in {"sampling", "repair"}]
    return {
        "schema": "fluxio.route_trust_coverage.v1",
        "requiredOperatorValueSamples": ROUTE_TRUST_REQUIRED_VALUE_SAMPLES,
        "taskCoverage": rows,
        "provenTaskCount": sum(1 for item in rows if item["status"] == "proven"),
        "samplingTaskCount": sum(1 for item in rows if item["status"] == "sampling"),
        "activeSamplingMissionCount": len(active_sampling_ids),
        "activeSamplingMissionIds": active_sampling_ids,
        "lowValueCloseoutCount": len(low_value_items),
        "quarantinedRouteCount": quarantined_route_count,
        "quarantinedRoutes": quarantined_routes,
        "routeOutcomeTrendSchema": str(route_outcome_trends.get("schema") or ""),
        "repairPlanStatus": "required" if repair_plan else ("sampling_active" if active_sampling_ids else "clear"),
        "repairPlan": repair_plan,
        "nextRepairStep": repair_plan[0]["repairAction"] if repair_plan else "",
        "operatorConfidenceScore": (
            68
            if repair_plan
            else 72
            if active_sampling_ids
            else 92
            if not sampling
            else 64
        ),
        "nextSamplingPlan": sampling[:5],
        "nextAction": (
            repair_plan[0]["repairAction"]
            if repair_plan
            else (
            sampling[0]["nextAction"]
            if sampling
            else "All tracked task categories have enough value-scored route and skill trust samples."
            )
        ),
    }


def _route_trust_payload_for_mission(mission: Mission) -> dict:
    route_configs = []
    for route in mission.route_configs or []:
        if is_dataclass(route):
            route_configs.append(asdict(route))
        elif isinstance(route, dict):
            route_configs.append(dict(route))
    return {
        "mission_id": mission.mission_id,
        "objective": mission.objective,
        "title": mission.title,
        "route_configs": route_configs,
        "state": {
            "status": mission.state.status,
            "operator_value_feedback": mission.state.operator_value_feedback,
        },
    }


def _build_route_outcome_trends_for_trust(root: Path) -> dict:
    try:
        from .fluxio_harness import build_route_outcome_trends
    except Exception:
        return {}
    try:
        trends = build_route_outcome_trends(root)
    except Exception:
        return {}
    return trends if isinstance(trends, dict) else {}


def _route_outcome_quarantines(trends: dict) -> dict:
    quarantined = trends.get("quarantinedRoutes") if isinstance(trends, dict) else {}
    return quarantined if isinstance(quarantined, dict) else {}


def _quarantined_route_count(quarantined_routes: dict) -> int:
    count = 0
    for task_rows in quarantined_routes.values() if isinstance(quarantined_routes, dict) else []:
        if not isinstance(task_rows, dict):
            continue
        for role_rows in task_rows.values():
            if isinstance(role_rows, list):
                count += len(role_rows)
    return count


def _build_route_trust_coverage_summary(root: Path, *, missions: list[Mission]) -> dict:
    coverage = {
        task_type: {
            "taskType": task_type,
            "label": label,
            "routeSamples": 0,
            "operatorValueSamples": 0,
            "operatorPromoteCount": 0,
            "operatorDeprioritizeCount": 0,
            "latestMissionId": "",
        }
        for task_type, label in ROUTE_TRUST_TASK_LABELS.items()
    }
    mission_status_by_id: dict[str, str] = {}
    for mission in missions:
        payload = _route_trust_payload_for_mission(mission)
        mission_status_by_id[mission.mission_id] = str(mission.state.status or "").strip().lower()
        status = str(mission.state.status or "").strip().lower()
        if mission.route_configs and status in {"completed", "failed", "blocked", "verification_failed", "stopped"}:
            _route_trust_row(coverage, _route_trust_task_type(payload))["routeSamples"] += 1
        feedback = _operator_value_feedback_signal(mission.state.operator_value_feedback)
        if not feedback:
            continue
        row = _route_trust_row(coverage, _route_trust_task_type(payload))
        row["operatorValueSamples"] += 1
        row["operatorPromoteCount"] += 1 if feedback.get("promote") else 0
        row["operatorDeprioritizeCount"] += 1 if feedback.get("deprioritize") else 0
        row["latestMissionId"] = mission.mission_id

    sampling_report = _load_json_file(root / ".agent_control" / "route_trust_sampling" / "latest.json")
    closeout_report = _load_json_file(root / ".agent_control" / "route_trust_sampling" / "closeout_review_latest.json")
    launched = (
        sampling_report.get("launchedSamplingMissions", [])
        if isinstance(sampling_report, dict) and isinstance(sampling_report.get("launchedSamplingMissions"), list)
        else []
    )
    active_statuses = {"running", "queued", "launching", "needs_approval", "verification_pending"}
    active_sampling_ids = []
    for item in launched:
        if not isinstance(item, dict):
            continue
        mission_id = str(item.get("missionId") or item.get("mission_id") or "").strip()
        status = mission_status_by_id.get(mission_id) or str(item.get("missionStatus") or item.get("status") or "").strip().lower()
        if mission_id and status in active_statuses:
            active_sampling_ids.append(mission_id)

    closeout_proposals = (
        closeout_report.get("proposals", [])
        if isinstance(closeout_report, dict) and isinstance(closeout_report.get("proposals"), list)
        else []
    )
    low_value_items = [
        item for item in closeout_proposals if isinstance(item, dict) and _route_trust_closeout_low_value(item)
    ]
    repair_plan = _route_trust_repair_steps(low_value_items, coverage)
    repair_by_task = {item["taskType"]: item for item in repair_plan}
    route_outcome_trends = _build_route_outcome_trends_for_trust(root)
    quarantined_routes = _route_outcome_quarantines(route_outcome_trends)
    quarantined_route_count = _quarantined_route_count(quarantined_routes)

    rows = []
    for row in coverage.values():
        value_samples = int(row["operatorValueSamples"])
        useful_samples = int(row.get("operatorPromoteCount") or 0)
        low_value_samples = int(row.get("operatorDeprioritizeCount") or 0)
        missing = max(0, ROUTE_TRUST_REQUIRED_VALUE_SAMPLES - useful_samples)
        status = "proven" if missing == 0 else "sampling"
        repair = repair_by_task.get(str(row["taskType"]))
        repair_required = repair is not None
        rows.append(
            {
                **row,
                "requiredOperatorValueSamples": ROUTE_TRUST_REQUIRED_VALUE_SAMPLES,
                "usefulOperatorValueSamples": useful_samples,
                "lowValueOperatorSamples": low_value_samples,
                "missingOperatorValueSamples": missing,
                "status": "repair" if repair_required else status,
                "repairRequired": repair_required,
                "repairMissionId": repair.get("missionId", "") if repair else "",
                "repairAction": repair.get("repairAction", "") if repair else "",
                "modelPolicy": repair.get("modelPolicy", "") if repair else "",
                **_route_trust_sampling_template(str(row["taskType"]), row, repair=repair),
                "nextAction": (
                    repair["repairAction"]
                    if repair_required
                    else (
                        "Route and skill trust have enough useful value-scored samples for this task category."
                        if status == "proven"
                        else (
                            f"Run {missing} more useful value-scored {row['label']} mission(s); "
                            f"{value_samples} scored sample(s), {low_value_samples} low-value sample(s), "
                            f"and {useful_samples} useful sample(s) are recorded."
                        )
                    )
                ),
            }
        )
    rows.sort(
        key=lambda item: (
            not item["repairRequired"],
            item["status"] != "sampling",
            item["missingOperatorValueSamples"],
            item["taskType"],
        )
    )
    sampling = [item for item in rows if item["status"] in {"sampling", "repair"}]
    return {
        "schema": "fluxio.route_trust_coverage.v1",
        "source": "mission_store_route_trust_summary",
        "requiredOperatorValueSamples": ROUTE_TRUST_REQUIRED_VALUE_SAMPLES,
        "taskCoverage": rows,
        "provenTaskCount": sum(1 for item in rows if item["status"] == "proven"),
        "samplingTaskCount": sum(1 for item in rows if item["status"] == "sampling"),
        "activeSamplingMissionCount": len(active_sampling_ids),
        "activeSamplingMissionIds": active_sampling_ids,
        "lowValueCloseoutCount": len(low_value_items),
        "quarantinedRouteCount": quarantined_route_count,
        "quarantinedRoutes": quarantined_routes,
        "routeOutcomeTrendSchema": str(route_outcome_trends.get("schema") or ""),
        "repairPlanStatus": "required" if repair_plan else ("sampling_active" if active_sampling_ids else "clear"),
        "repairPlan": repair_plan,
        "nextRepairStep": repair_plan[0]["repairAction"] if repair_plan else "",
        "operatorConfidenceScore": (
            68
            if repair_plan
            else 72
            if active_sampling_ids
            else 92
            if not sampling
            else 64
        ),
        "nextSamplingPlan": sampling[:5],
        "nextAction": (
            repair_plan[0]["repairAction"]
            if repair_plan
            else (
                sampling[0]["nextAction"]
                if sampling
                else "All tracked task categories have enough value-scored route and skill trust samples."
            )
        ),
    }


def _build_harness_parity_matrix() -> list[dict]:
    capabilities = [
        (
            "Mission planning and resume",
            "native",
            "native",
            "partial",
            "Syntelos wraps both Hermes and OpenClaw into durable mission state; legacy remains benchmark-only.",
        ),
        (
            "Planner/executor/verifier lanes",
            "bridged",
            "native",
            "missing",
            "Hermes supplies supervised delegation while OpenClaw exposes sub-agent commands and ACP controls.",
        ),
        (
            "Provider/model switching",
            "native",
            "native",
            "partial",
            "Shared provider auth detection now reads env, Hermes auth, OpenClaw auth, and Codex OAuth stores.",
        ),
        (
            "Approval gates",
            "native",
            "native",
            "partial",
            "Both modern runtimes are normalized into Syntelos approval history and proof state.",
        ),
        (
            "Tool/MCP/plugin access",
            "bridged",
            "native",
            "partial",
            "OpenClaw has the richer live command catalog; Hermes remains the steadier supervised mission lane.",
        ),
        (
            "Proof artifacts and digest",
            "native",
            "bridged",
            "partial",
            "Syntelos turns both runtime event streams into mission proof, checks, and digest artifacts.",
        ),
        (
            "Phone/tablet web supervision",
            "native",
            "native",
            "missing",
            "Both runtimes surface through the same web summary and notification feed.",
        ),
    ]
    return [
        {
            "capability": capability,
            "hermes": hermes,
            "openclaw": openclaw,
            "legacy": legacy,
            "summary": summary,
        }
        for capability, hermes, openclaw, legacy, summary in capabilities
    ]


def build_harness_lab_snapshot(root: Path) -> dict:
    runs_root = root / ".agent_runs"
    sessions = sorted(
        [path for path in runs_root.glob("session_*") if path.is_dir()],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    recent_runs: list[dict] = []
    harness_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    pause_reason_counts: dict[str, int] = {}
    delegated_run_count = 0
    delegated_failure_run_count = 0
    runtime_budget_pause_count = 0
    delegated_active_pause_count = 0
    resumed_run_count = 0
    resumed_completed_count = 0
    approval_resolved_run_count = 0
    approval_rejected_run_count = 0
    verification_failure_total = 0
    action_count_total = 0
    for session in sessions[:HARNESS_RECENT_RUN_LIMIT]:
        state_path = session / "state.json"
        if not state_path.exists():
            continue
        payload = _load_json_file(state_path)
        if not isinstance(payload, dict):
            continue
        harness_id = payload.get("harness_id", "legacy_autonomous_engine")
        status = str(payload.get("autopilot_status", "unknown"))
        pause_reason = str(payload.get("autopilot_pause_reason", "none") or "none")
        delegated_sessions = payload.get("delegated_runtime_sessions", [])
        if not isinstance(delegated_sessions, list):
            delegated_sessions = []
        delegated_session_count = len(delegated_sessions)
        verification_failures = len(payload.get("verification_failures", []))
        action_count = len(payload.get("action_history", []))
        metadata = _load_json_file(session / "metadata.json")
        parent_session_id = (
            str(metadata.get("parent_session_id", "")).strip()
            if isinstance(metadata, dict)
            else ""
        )
        harness_counts[harness_id] = harness_counts.get(harness_id, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
        pause_reason_counts[pause_reason] = pause_reason_counts.get(pause_reason, 0) + 1
        if delegated_session_count:
            delegated_run_count += 1
            if status == "failed" or any(
                str(item.get("status", "")) in {"failed", "stopped"}
                for item in delegated_sessions
                if isinstance(item, dict)
            ):
                delegated_failure_run_count += 1
            approval_decisions = {
                str(entry.get("status", ""))
                for item in delegated_sessions
                if isinstance(item, dict)
                for entry in item.get("approval_history", [])
                if isinstance(entry, dict)
            }
            if "approved" in approval_decisions:
                approval_resolved_run_count += 1
            if "rejected" in approval_decisions:
                approval_rejected_run_count += 1
        if pause_reason == "runtime_budget":
            runtime_budget_pause_count += 1
        if pause_reason == "delegated_runtime_running":
            delegated_active_pause_count += 1
        if parent_session_id:
            resumed_run_count += 1
            if status == "completed":
                resumed_completed_count += 1
        verification_failure_total += verification_failures
        action_count_total += action_count
        recent_runs.append(
            {
                "sessionId": session.name,
                "harnessId": harness_id,
                "runtimeId": payload.get("runtime_id", "openclaw"),
                "autopilotStatus": status,
                "pauseReason": pause_reason if pause_reason != "none" else "",
                "verificationFailures": verification_failures,
                "delegatedSessionCount": delegated_session_count,
                "resumedFromSessionId": parent_session_id,
                "actionCount": action_count,
            }
        )
    total_runs = len(recent_runs)
    completed_runs = status_counts.get("completed", 0)
    approval_pauses = pause_reason_counts.get("approval_required", 0)
    verification_pauses = pause_reason_counts.get("verification_failed", 0)
    completion_rate = _percent(completed_runs, total_runs)
    delegated_run_rate = _percent(delegated_run_count, total_runs)
    resume_run_rate = _percent(resumed_run_count, total_runs)
    resume_completion_rate = _percent(resumed_completed_count, resumed_run_count)
    approval_decision_total = approval_resolved_run_count + approval_rejected_run_count
    session_health = _build_runtime_session_health(root)
    route_trust_coverage = _build_route_trust_coverage_snapshot(root, sessions=sessions)
    recommendation = _harness_efficiency_recommendation(
        total_runs=total_runs,
        completion_rate=completion_rate,
        delegated_run_rate=delegated_run_rate,
        resume_run_rate=resume_run_rate,
        resume_completion_rate=resume_completion_rate,
        approval_pause_rate=_percent(approval_pauses, total_runs),
        verification_pause_rate=_percent(verification_pauses, total_runs),
        stale_heartbeat_count=int(session_health["staleHeartbeatCount"]),
    )
    return {
        "productionHarness": "fluxio_hybrid",
        "shadowCandidates": ["legacy_autonomous_engine"],
        "parityMatrix": _build_harness_parity_matrix(),
        "beginnerGuidance": [
            {
                "runtime": "Hermes",
                "useWhen": "Use for long supervised missions, resume/continue loops, and proof-heavy work.",
            },
            {
                "runtime": "OpenClaw",
                "useWhen": "Use for live provider/tool exploration, sub-agent command work, and direct gateway sessions.",
            },
            {
                "runtime": "Syntelos Hybrid",
                "useWhen": "Default choice: it can route through Hermes or OpenClaw while preserving one mission/proof record.",
            },
        ],
        "recentRuns": recent_runs,
        "harnessCounts": harness_counts,
        "statusCounts": status_counts,
        "pauseReasonCounts": pause_reason_counts,
        "efficiency": {
            "totalRuns": total_runs,
            "completedRuns": completed_runs,
            "completionRate": completion_rate,
            "approvalPauseRate": _percent(approval_pauses, total_runs),
            "verificationPauseRate": _percent(verification_pauses, total_runs),
            "delegatedRunRate": delegated_run_rate,
            "delegatedFailureRate": _percent(
                delegated_failure_run_count,
                delegated_run_count,
            ),
            "runtimeBudgetPauseRate": _percent(runtime_budget_pause_count, total_runs),
            "delegatedActivePauseRate": _percent(
                delegated_active_pause_count,
                total_runs,
            ),
            "resumeRunRate": resume_run_rate,
            "resumeCompletionRate": resume_completion_rate,
            "approvalRecoveryRate": _percent(
                approval_resolved_run_count,
                approval_decision_total,
            ),
            "averageActionsPerRun": round(action_count_total / total_runs, 1)
            if total_runs
            else 0.0,
            "averageVerificationFailures": round(
                verification_failure_total / total_runs, 1
            )
            if total_runs
            else 0.0,
        },
        "sessionHealth": session_health,
        "routeTrustCoverage": route_trust_coverage,
        "recommendation": recommendation,
    }


def build_summary_harness_lab_snapshot(root: Path, *, missions: list[Mission]) -> dict:
    recent_missions = sorted(
        [mission for mission in missions if str(mission.state.status or "").strip()],
        key=lambda item: item.updated_at or item.created_at,
        reverse=True,
    )[:HARNESS_RECENT_RUN_LIMIT]
    harness_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    pause_reason_counts: dict[str, int] = {}
    delegated_run_count = 0
    delegated_failure_run_count = 0
    runtime_budget_pause_count = 0
    delegated_active_pause_count = 0
    resumed_run_count = 0
    resumed_completed_count = 0
    approval_resolved_run_count = 0
    approval_rejected_run_count = 0
    verification_failure_total = 0
    action_count_total = 0
    recent_runs: list[dict[str, object]] = []
    for mission in recent_missions:
        harness_id = mission.harness_id or "fluxio_hybrid"
        status = str(mission.state.status or "unknown").strip().lower()
        pause_reason = str(
            mission.state.stop_reason
            or mission.state.last_budget_pause_reason
            or "none"
        ).strip().lower() or "none"
        delegated_sessions = list(mission.delegated_runtime_sessions or [])
        delegated_session_count = len(delegated_sessions)
        verification_failures = len(mission.proof.failed_checks or mission.state.verification_failures or [])
        action_count = len(mission.action_history or [])
        harness_counts[harness_id] = harness_counts.get(harness_id, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
        pause_reason_counts[pause_reason] = pause_reason_counts.get(pause_reason, 0) + 1
        if delegated_session_count:
            delegated_run_count += 1
            if status == "failed" or any(
                str(getattr(item, "status", "") or "").lower() in {"failed", "stopped"}
                for item in delegated_sessions
            ):
                delegated_failure_run_count += 1
            approval_decisions = {
                str(entry.get("status", ""))
                for item in delegated_sessions
                for entry in getattr(item, "approval_history", []) or []
                if isinstance(entry, dict)
            }
            if "approved" in approval_decisions:
                approval_resolved_run_count += 1
            if "rejected" in approval_decisions:
                approval_rejected_run_count += 1
        if pause_reason == "runtime_budget":
            runtime_budget_pause_count += 1
        if pause_reason == "delegated_runtime_running":
            delegated_active_pause_count += 1
        if mission.current_plan_revision_id:
            resumed_run_count += 1
            if status == "completed":
                resumed_completed_count += 1
        verification_failure_total += verification_failures
        action_count_total += action_count
        recent_runs.append(
            {
                "sessionId": mission.state.latest_session_id or mission.mission_id,
                "missionId": mission.mission_id,
                "harnessId": harness_id,
                "runtimeId": mission.runtime_id,
                "autopilotStatus": status,
                "pauseReason": pause_reason if pause_reason != "none" else "",
                "verificationFailures": verification_failures,
                "delegatedSessionCount": delegated_session_count,
                "resumedFromSessionId": "",
                "actionCount": action_count,
            }
        )

    total_runs = len(recent_runs)
    completed_runs = status_counts.get("completed", 0)
    approval_pauses = pause_reason_counts.get("approval_required", 0)
    verification_pauses = pause_reason_counts.get("verification_failed", 0)
    completion_rate = _percent(completed_runs, total_runs)
    delegated_run_rate = _percent(delegated_run_count, total_runs)
    resume_run_rate = _percent(resumed_run_count, total_runs)
    resume_completion_rate = _percent(resumed_completed_count, resumed_run_count)
    approval_decision_total = approval_resolved_run_count + approval_rejected_run_count
    session_health = _build_runtime_session_health_summary(missions=missions)
    route_trust_coverage = _build_route_trust_coverage_summary(root, missions=missions)
    recommendation = _harness_efficiency_recommendation(
        total_runs=total_runs,
        completion_rate=completion_rate,
        delegated_run_rate=delegated_run_rate,
        resume_run_rate=resume_run_rate,
        resume_completion_rate=resume_completion_rate,
        approval_pause_rate=_percent(approval_pauses, total_runs),
        verification_pause_rate=_percent(verification_pauses, total_runs),
        stale_heartbeat_count=int(session_health["staleHeartbeatCount"]),
    )
    return {
        "schema": "fluxio.harness_lab.summary.v1",
        "source": "mission_store_delegated_sessions_summary",
        "fullSessionScanDeferred": True,
        "productionHarness": "fluxio_hybrid",
        "shadowCandidates": ["legacy_autonomous_engine"],
        "parityMatrix": _build_harness_parity_matrix(),
        "beginnerGuidance": [
            {
                "runtime": "Hermes",
                "useWhen": "Use for long supervised missions, resume/continue loops, and proof-heavy work.",
            },
            {
                "runtime": "OpenClaw",
                "useWhen": "Use for live provider/tool exploration, sub-agent command work, and direct gateway sessions.",
            },
            {
                "runtime": "Syntelos Hybrid",
                "useWhen": "Default choice: it can route through Hermes or OpenClaw while preserving one mission/proof record.",
            },
        ],
        "recentRuns": recent_runs,
        "harnessCounts": harness_counts,
        "statusCounts": status_counts,
        "pauseReasonCounts": pause_reason_counts,
        "efficiency": {
            "totalRuns": total_runs,
            "completedRuns": completed_runs,
            "completionRate": completion_rate,
            "approvalPauseRate": _percent(approval_pauses, total_runs),
            "verificationPauseRate": _percent(verification_pauses, total_runs),
            "delegatedRunRate": delegated_run_rate,
            "delegatedFailureRate": _percent(
                delegated_failure_run_count,
                delegated_run_count,
            ),
            "runtimeBudgetPauseRate": _percent(runtime_budget_pause_count, total_runs),
            "delegatedActivePauseRate": _percent(
                delegated_active_pause_count,
                total_runs,
            ),
            "resumeRunRate": resume_run_rate,
            "resumeCompletionRate": resume_completion_rate,
            "approvalRecoveryRate": _percent(
                approval_resolved_run_count,
                approval_decision_total,
            ),
            "averageActionsPerRun": round(action_count_total / total_runs, 1)
            if total_runs
            else 0.0,
            "averageVerificationFailures": round(
                verification_failure_total / total_runs, 1
            )
            if total_runs
            else 0.0,
        },
        "sessionHealth": session_health,
        "routeTrustCoverage": route_trust_coverage,
        "recommendation": recommendation,
    }


def _summary_mission_watchdog_report(
    *,
    root: Path,
    missions: list[Mission],
    workspaces: list[WorkspaceProfile],
) -> dict[str, Any]:
    report_path = root / ".agent_control" / "mission_watchdog.json"
    payload = _load_json_file(report_path)
    if isinstance(payload, dict) and payload.get("schema") == "fluxio.mission_watchdog.v1":
        try:
            age_seconds = max(0, int(time.time() - report_path.stat().st_mtime))
        except OSError:
            age_seconds = 0
        payload = dict(payload)
        payload.setdefault("summary", {})
        payload.setdefault("issues", [])
        payload.setdefault("nextAction", "")
        payload.setdefault("problemReport", build_watchdog_problem_report(payload))
        payload.setdefault("problemRegistry", {})
        payload["summarySource"] = {
            "schema": "fluxio.summary.watchdog_source.v1",
            "source": "mission_watchdog_report_file",
            "path": str(report_path),
            "freshness": "fresh" if age_seconds <= 300 else "stale",
            "ageSeconds": age_seconds,
            "checkedAgainstMissionCount": len(missions),
            "reportMissionCount": int(payload.get("summary", {}).get("missionCount") or 0),
            "nextAction": (
                "Use the external watchdog report; it is fresh enough for the summary path."
                if age_seconds <= 300
                else "External watchdog report is stale; restart or advance the watchdog loop instead of hiding this."
            ),
        }
        return payload
    report = build_mission_watchdog_report(
        root=root,
        missions=missions,
        workspaces=workspaces,
    )
    report["summarySource"] = {
        "schema": "fluxio.summary.watchdog_source.v1",
        "source": "inline_rebuild",
        "freshness": "fresh",
        "ageSeconds": 0,
        "checkedAgainstMissionCount": len(missions),
        "reportMissionCount": int(report.get("summary", {}).get("missionCount") or 0),
        "nextAction": "No persisted watchdog report was available, so the summary rebuilt it inline.",
    }
    return report
