from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import uuid
from errno import EBUSY, ETXTBSY
from dataclasses import asdict
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
    RuntimeInstallStatus,
    SkillRecommendation,
    WorkspaceProfile,
    utc_now_iso,
)
from .app_capability_standard import build_connected_apps_snapshot
from .execution_truth import derive_execution_target
from .mindtower_fusion import build_mindtower_fusion_snapshot
from .onboarding import (
    build_guidance_snapshot,
    detect_onboarding_status,
    invalidate_onboarding_status_cache,
)
from .profiles import ProfileRegistry
from .runtimes import detect_runtime_statuses, invalidate_runtime_status_cache
from .runtime_supervisor import DelegatedRuntimeSupervisor
from .skill_library import SkillLibrary
from .skills import SkillRegistry
from .verification import detect_default_verification_commands

TERMINAL_MISSION_STATUSES = {"completed", "failed", "stopped"}
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
BENCHMARK_SCORECARD_SCHEMA_VERSION = "benchmark-board-route-scorecard/v1"
BENCHMARK_SCORECARD_ARTIFACT_LIMIT = 3
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
PROVIDER_ECOSYSTEM_SOURCES = [
    {
        "sourceId": "opencode_models",
        "label": "OpenCode models",
        "url": "https://opencode.ai/docs/models/",
        "verifiedAt": "2026-06-21",
        "signal": "OpenCode uses AI SDK plus Models.dev for broad provider/model discovery.",
    },
    {
        "sourceId": "crush_local_models",
        "label": "Crush local providers",
        "url": "https://github.com/charmbracelet/crush",
        "verifiedAt": "2026-06-21",
        "signal": "Crush auto-discovers Ollama, LM Studio, LiteLLM, and OMLX providers.",
    },
    {
        "sourceId": "openclaw_model_providers",
        "label": "OpenClaw model providers",
        "url": "https://docs.openclaw.ai/concepts/model-providers",
        "verifiedAt": "2026-06-21",
        "signal": "OpenClaw exposes a provider directory and exact-origin network trust rules.",
    },
    {
        "sourceId": "vercel_ai_gateway_models",
        "label": "Vercel AI Gateway models endpoint",
        "url": "https://ai-gateway.vercel.sh/v1/models",
        "verifiedAt": "2026-06-21",
        "signal": "Gateway model metadata can include IDs, pricing, context windows, and capabilities.",
    },
    {
        "sourceId": "litellm_providers",
        "label": "LiteLLM providers",
        "url": "https://docs.litellm.ai/docs/providers",
        "verifiedAt": "2026-06-21",
        "signal": "LiteLLM is a broad adapter/gateway source for remote, local, speech, and image providers.",
    },
]
PROVIDER_ECOSYSTEM_ROWS = [
    {
        "providerId": "openai",
        "label": "OpenAI / Codex",
        "status": "repo_supported",
        "routeRole": "primary_model_route",
        "authPath": "OpenAI API key or OpenAI Codex OAuth",
        "sourceId": "opencode_models",
        "updateSource": "official_docs_and_runtime_status",
        "supports": ["chat", "coding", "image-route-check"],
    },
    {
        "providerId": "minimax",
        "label": "MiniMax",
        "status": "repo_supported",
        "routeRole": "bounded_model_route",
        "authPath": "MiniMax API key or OpenClaw OAuth",
        "sourceId": "openclaw_model_providers",
        "updateSource": "OpenClaw provider directory",
        "supports": ["chat", "coding", "hermes-route"],
    },
    {
        "providerId": "anthropic",
        "label": "Anthropic",
        "status": "credential_ready",
        "routeRole": "external_model_route",
        "authPath": "Anthropic API key",
        "sourceId": "opencode_models",
        "updateSource": "AI SDK provider registry",
        "supports": ["chat", "coding", "verification"],
    },
    {
        "providerId": "openrouter",
        "label": "OpenRouter",
        "status": "credential_ready",
        "routeRole": "gateway_model_route",
        "authPath": "OpenRouter API key",
        "sourceId": "opencode_models",
        "updateSource": "OpenCode/OpenRouter integration",
        "supports": ["multi-provider", "fallback", "benchmarking"],
    },
    {
        "providerId": "google",
        "label": "Google Gemini / Vertex",
        "status": "planned_adapter",
        "routeRole": "future_model_route",
        "authPath": "Google AI Studio or Vertex credentials",
        "sourceId": "opencode_models",
        "updateSource": "AI SDK provider registry",
        "supports": ["chat", "vision", "long-context"],
    },
    {
        "providerId": "local",
        "label": "Local models",
        "status": "planned_adapter",
        "routeRole": "local_model_route",
        "authPath": "Ollama, LM Studio, LiteLLM, vLLM, or OMLX endpoint",
        "sourceId": "crush_local_models",
        "updateSource": "Crush local-provider discovery",
        "supports": ["private-chat", "cheap-probes", "offline-runs"],
    },
    {
        "providerId": "vercel-ai-gateway",
        "label": "Vercel AI Gateway",
        "status": "planned_gateway",
        "routeRole": "provider_catalog_source",
        "authPath": "AI Gateway key",
        "sourceId": "vercel_ai_gateway_models",
        "updateSource": "AI Gateway /v1/models endpoint",
        "supports": ["model-catalog", "pricing", "capability-metadata"],
    },
    {
        "providerId": "litellm",
        "label": "LiteLLM",
        "status": "planned_gateway",
        "routeRole": "adapter_gateway",
        "authPath": "LiteLLM proxy or provider-specific keys",
        "sourceId": "litellm_providers",
        "updateSource": "LiteLLM provider docs",
        "supports": ["many-providers", "speech", "image", "fallback"],
    },
]


def _provider_route_exposure(row: dict, *, can_route_now: bool) -> dict:
    provider_id = str(row.get("providerId", "")).strip().lower()
    status = str(row.get("status", "")).strip().lower()
    if provider_id == "openai":
        level = "first_class_route"
        label = "First-class route"
        summary = "Native Codex/OpenAI route metadata is tracked; live use still depends on account access and a smoke check."
    elif provider_id == "minimax":
        level = "bounded_openclaw_route"
        label = "Bounded OpenClaw route"
        summary = "MiniMax is routed through the OpenClaw/Hermes lane and must keep auth, runtime, and route proof visible."
    elif status == "credential_ready":
        level = "credential_ready_adapter"
        label = "Credential-ready adapter"
        summary = "Credentials can unlock this route, but it should not become default until a health check passes."
    elif status == "planned_gateway":
        level = "catalog_source_only"
        label = "Catalog source only"
        summary = "This is a provider catalog signal until a gateway adapter and route smoke proof exist."
    elif status.startswith("planned"):
        level = "planned_adapter"
        label = "Planned adapter"
        summary = "This provider is tracked for future adapter work and cannot route live work yet."
    else:
        level = "review_required"
        label = "Review required"
        summary = "Provider exposure could not be classified from the current repo metadata."
    return {
        "level": level,
        "label": label,
        "summary": summary,
        "routeReady": can_route_now,
    }


def _provider_source_freshness(sources: list[dict], *, as_of: str = "2026-06-21") -> dict:
    as_of_date = datetime.strptime(as_of, "%Y-%m-%d").date()
    source_rows: list[dict] = []
    fresh_count = 0
    stale_count = 0
    latest_verified_at = ""
    for source in sources:
        verified_at = str(source.get("verifiedAt", "")).strip()
        age_days = None
        status = "review"
        if verified_at:
            try:
                verified_date = datetime.strptime(verified_at, "%Y-%m-%d").date()
                age_days = max(0, (as_of_date - verified_date).days)
                if not latest_verified_at or verified_at > latest_verified_at:
                    latest_verified_at = verified_at
                status = "current" if age_days <= 7 else "stale" if age_days <= 30 else "expired"
            except ValueError:
                status = "review"
        if status == "current":
            fresh_count += 1
        else:
            stale_count += 1
        source_rows.append(
            {
                **source,
                "freshnessStatus": status,
                "ageDays": age_days,
                "reviewOnly": True,
                "refreshAction": "Refresh catalog metadata and review before default route changes.",
            }
        )
    return {
        "asOf": as_of,
        "sourceCount": len(source_rows),
        "freshSourceCount": fresh_count,
        "reviewRequiredCount": stale_count,
        "latestVerifiedAt": latest_verified_at,
        "status": "current" if stale_count == 0 and source_rows else "review_required",
        "reviewOnly": True,
        "sources": source_rows,
        "nextRefreshAction": "Run scripts/provider_catalog_refresh.py, review the artifact, then run provider health checks before default changes.",
    }


def _provider_compatibility_warnings(row: dict, *, auth_present: bool, can_route_now: bool) -> list[str]:
    warnings = [
        "Review refreshed catalog metadata before changing default model IDs.",
        "Keep user-defined models unchanged until a route smoke test passes.",
    ]
    if row.get("status") in {"repo_supported", "credential_ready"} and not auth_present:
        warnings.append("Credentials are missing, so this provider cannot be selected for live routes yet.")
    if not can_route_now and str(row.get("status", "")).startswith("planned"):
        warnings.append("Adapter work is planned; use this row as a catalog signal only.")
    return warnings


def _provider_model_capabilities(row: dict) -> dict:
    supports = {str(item).strip().lower() for item in row.get("supports", [])}
    provider_id = str(row.get("providerId", "")).strip().lower()
    planned = str(row.get("status", "")).startswith("planned")
    return {
        "chat": "chat" in supports or "multi-provider" in supports or "many-providers" in supports,
        "coding": "coding" in supports or "benchmarking" in supports or provider_id in {"openai", "minimax", "anthropic"},
        "toolUse": "supported" if provider_id in {"openai", "anthropic", "minimax"} else "planned" if planned else "unknown",
        "vision": "vision" in supports or "image" in supports,
        "image": "image" in supports or "image-route-check" in supports,
        "localPrivate": provider_id == "local",
        "contextWindowTokens": None,
        "costBand": "low" if provider_id in {"minimax", "local"} else "balanced" if provider_id in {"openai", "anthropic"} else "unknown",
        "speedBand": "fast" if provider_id in {"minimax", "local"} else "balanced" if provider_id in {"openai", "anthropic"} else "unknown",
    }


def _provider_capability_chips(capabilities: dict) -> list[str]:
    chips = [
        "chat" if capabilities.get("chat") else "",
        "coding" if capabilities.get("coding") else "",
        "image" if capabilities.get("image") else "",
        "vision" if capabilities.get("vision") else "",
        "local private" if capabilities.get("localPrivate") else "",
        f"tools {capabilities.get('toolUse')}" if capabilities.get("toolUse") else "",
        f"cost {capabilities.get('costBand')}" if capabilities.get("costBand") else "",
        f"speed {capabilities.get('speedBand')}" if capabilities.get("speedBand") else "",
    ]
    return [chip for chip in chips if chip][:8]


def _provider_health_check(
    row: dict,
    *,
    auth_present: bool,
    can_route_now: bool,
    observed_route_count: int,
    runtime_ids: set[str],
    compatibility_warnings: list[str],
) -> dict:
    provider_id = str(row.get("providerId", "")).strip().lower()
    status = str(row.get("status", "")).strip().lower()
    needs_openclaw = provider_id in {"minimax", "vercel-ai-gateway", "litellm"} or row.get("updateSource") == "OpenClaw provider directory"
    needs_hermes = "hermes-route" in {str(item).strip().lower() for item in row.get("supports", [])}
    missing_runtime = (needs_openclaw and "openclaw" not in runtime_ids) or (needs_hermes and "hermes" not in runtime_ids)
    evidence = []
    if auth_present:
        evidence.append("auth present")
    else:
        evidence.append("auth missing")
    if observed_route_count:
        evidence.append(f"{observed_route_count} observed route{'s' if observed_route_count != 1 else ''}")
    if needs_openclaw:
        evidence.append("OpenClaw detected" if "openclaw" in runtime_ids else "OpenClaw missing")
    if needs_hermes:
        evidence.append("Hermes detected" if "hermes" in runtime_ids else "Hermes missing")
    if can_route_now:
        health_status = "ready"
        summary = "Credentials and route metadata are ready for controlled live work."
        safe_next_step = "Run a provider smoke test before assigning expensive or long-running work."
    elif status.startswith("planned"):
        health_status = "adapter_planned"
        summary = "This provider is tracked as a catalog or future adapter signal only."
        safe_next_step = "Implement the adapter and prove a route smoke test before using it."
    elif missing_runtime:
        health_status = "runtime_missing"
        summary = "Credentials alone are not enough because a required runtime adapter is missing."
        safe_next_step = "Repair the missing runtime, then rerun setup health."
    elif not auth_present:
        health_status = "missing_auth"
        summary = "A supported provider route exists, but credentials are not configured."
        safe_next_step = "Connect credentials, then rerun provider health."
    else:
        health_status = "unverified"
        summary = "Provider metadata is tracked but no recent route proof is available."
        safe_next_step = "Run a route smoke test and keep the previous default until it passes."
    return {
        "status": health_status,
        "summary": summary,
        "evidence": evidence,
        "safeNextStep": safe_next_step,
        "warnings": compatibility_warnings,
    }


def _runtime_update_safety(service: dict) -> dict:
    if not service.get("updateAvailable"):
        return dict(service.get("updateSafety") or {})
    label = str(service.get("label") or service.get("serviceId") or service.get("runtime_id") or "Runtime")
    version = str(service.get("version") or "current installed version")
    latest = str(service.get("latestVersion") or service.get("latest_version") or "latest available version")
    return {
        "label": "Review before updating",
        "summary": f"{label} has an update available. Finish or pause active runs before changing runtime binaries.",
        "impact": f"{label} will move from {version} to {latest}.",
        "safeNextStep": "Run the existing update action, then rerun setup verification before assigning new work.",
        "verifyAfterUpdate": True,
        "requiresActiveRunPause": True,
    }


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
    oauth_present = bool(auth_presence.get("minimax-portal", False))
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


def _build_provider_ecosystem_snapshot(
    *,
    provider_setup_status: dict,
    provider_auth_presence: dict[str, bool],
    runtime_statuses: list[RuntimeInstallStatus],
    harness_lab: dict,
) -> dict:
    runtime_ids = {item.runtime_id for item in runtime_statuses if item.detected}
    source_freshness = _provider_source_freshness(PROVIDER_ECOSYSTEM_SOURCES)
    sources_by_id = {
        str(item.get("sourceId", "")).strip(): item
        for item in source_freshness["sources"]
        if item.get("sourceId")
    }
    fused_runtime = harness_lab.get("fusedRuntime", {})
    observed_routes = {
        str(item.get("provider", "")).strip().lower(): int(item.get("observedCount", 0) or 0)
        for item in fused_runtime.get("modelProviderRoutes", [])
        if isinstance(item, dict)
    }
    rows = []
    for row in PROVIDER_ECOSYSTEM_ROWS:
        provider_id = row["providerId"]
        setup = provider_setup_status.get(provider_id, {})
        auth_present = bool(
            setup.get("authPresent")
            or setup.get("configured")
            or provider_auth_presence.get(provider_id, False)
        )
        can_route_now = row["status"] in {"repo_supported", "credential_ready"} and auth_present
        compatibility_warnings = _provider_compatibility_warnings(
            row,
            auth_present=auth_present,
            can_route_now=can_route_now,
        )
        observed_route_count = observed_routes.get(provider_id, 0)
        model_capabilities = _provider_model_capabilities(row)
        route_exposure = _provider_route_exposure(row, can_route_now=can_route_now)
        row_source = sources_by_id.get(str(row.get("sourceId", "")).strip(), {})
        rows.append(
            {
                **row,
                "authPresent": auth_present,
                "canRouteNow": can_route_now,
                "observedRouteCount": observed_route_count,
                "routeExposure": route_exposure,
                "sourceFreshness": {
                    "sourceId": row_source.get("sourceId") or row.get("sourceId"),
                    "status": row_source.get("freshnessStatus", "review"),
                    "verifiedAt": row_source.get("verifiedAt", ""),
                    "reviewOnly": bool(row_source.get("reviewOnly", True)),
                },
                "setup": setup,
                "compatibilityWarnings": compatibility_warnings,
                "healthCheck": _provider_health_check(
                    row,
                    auth_present=auth_present,
                    can_route_now=can_route_now,
                    observed_route_count=observed_route_count,
                    runtime_ids=runtime_ids,
                    compatibility_warnings=compatibility_warnings,
                ),
                "modelCapabilities": model_capabilities,
                "capabilityChips": _provider_capability_chips(model_capabilities),
                "updateSafety": {
                    "label": "Safe catalog refresh",
                    "summary": "Refresh provider catalogs before changing defaults or routing expensive work.",
                    "safeNextStep": compatibility_warnings[0],
                    "requiresApprovalForDefaultChanges": True,
                    "neverOverwriteUserModels": True,
                },
            }
        )
    implemented = [item for item in rows if item["status"] in {"repo_supported", "credential_ready"}]
    route_ready = [item for item in rows if item["canRouteNow"]]
    missing_auth = [
        item["providerId"]
        for item in rows
        if item["status"] in {"repo_supported", "credential_ready"} and not item["authPresent"]
    ]
    next_actions: list[str] = []
    if "openclaw" not in runtime_ids:
        next_actions.append("Install or repair OpenClaw before widening provider routing.")
    if "hermes" not in runtime_ids:
        next_actions.append("Install or repair Hermes before assigning long-running provider routes.")
    if missing_auth:
        next_actions.append(
            "Connect provider credentials for: " + ", ".join(missing_auth) + "."
        )
    next_actions.append(
        "Use dynamic catalog refresh for Vercel AI Gateway, LiteLLM, OpenClaw, and OpenCode/Models.dev before changing default model IDs."
    )
    readiness_checklist = [
        {
            "checkId": "catalog_refresh_review",
            "label": "Catalog refresh review",
            "status": "ready",
            "summary": "Create a review-only provider catalog artifact before changing model defaults.",
            "safeAction": (
                "Run scripts/provider_catalog_refresh.py and review the JSON artifact "
                "in artifacts/provider-catalog."
            ),
            "proof": "provider-catalog-refresh/v1 report; writesDefaults=false; writesCredentials=false.",
        },
        {
            "checkId": "credential_safety",
            "label": "Credential safety",
            "status": "review" if missing_auth else "ready",
            "summary": (
                "Provider credentials are present for route-ready accounts."
                if not missing_auth
                else "Some supported providers still need credentials before they can route live work."
            ),
            "safeAction": (
                "Keep stored credentials masked and connect missing providers: "
                + ", ".join(missing_auth)
                + "."
                if missing_auth
                else "Keep masked credential status visible; never write raw keys into catalog artifacts."
            ),
            "proof": "providerSetupStatus and provider health checks are included in the snapshot.",
        },
        {
            "checkId": "runtime_compatibility",
            "label": "Runtime compatibility",
            "status": (
                "ready" if {"openclaw", "hermes"}.issubset(runtime_ids) else "review"
            ),
            "summary": "OpenClaw and Hermes runtime presence is checked before widening provider routing.",
            "safeAction": (
                "Runtime lanes detected for OpenClaw and Hermes."
                if {"openclaw", "hermes"}.issubset(runtime_ids)
                else "Repair missing OpenClaw/Hermes lanes before assigning long-running provider routes."
            ),
            "proof": "Runtime install statuses and fused runtime route observations feed this checklist.",
        },
        {
            "checkId": "route_smoke",
            "label": "Route smoke verification",
            "status": "ready" if route_ready else "review",
            "summary": "A route should pass a cheap health check before becoming the default path.",
            "safeAction": (
                "Use the existing provider health check before assigning live work."
                if route_ready
                else "Connect at least one supported provider, then run a provider health check."
            ),
            "proof": "healthCheck.status, safeNextStep, and observed route counts are shown per provider.",
        },
        {
            "checkId": "user_model_preservation",
            "label": "User model preservation",
            "status": "ready",
            "summary": "Catalog refreshes cannot overwrite user-defined model IDs or route defaults.",
            "safeAction": "Promote catalog changes through a PR and require approval before default route changes.",
            "proof": "requiresApprovalForDefaultChanges=true; neverOverwriteUserModels=true.",
        },
    ]
    readiness_ready = [
        item for item in readiness_checklist if item["status"] == "ready"
    ]
    readiness_review = [
        item for item in readiness_checklist if item["status"] != "ready"
    ]
    exposure_counts: dict[str, int] = {}
    for item in rows:
        level = str(item.get("routeExposure", {}).get("level", "review_required"))
        exposure_counts[level] = exposure_counts.get(level, 0) + 1
    return {
        "schemaVersion": "provider-ecosystem.v1",
        "lastVerifiedAt": "2026-06-21",
        "sourceFreshness": {
            key: value
            for key, value in source_freshness.items()
            if key != "sources"
        },
        "summary": {
            "totalProvidersTracked": len(rows),
            "implementedOrCredentialReady": len(implemented),
            "routeReadyCount": len(route_ready),
            "missingAuthCount": len(missing_auth),
            "updateReadinessReadyCount": len(readiness_ready),
            "updateReadinessReviewCount": len(readiness_review),
            "catalogSourceCount": source_freshness["sourceCount"],
            "freshCatalogSourceCount": source_freshness["freshSourceCount"],
            "catalogReviewRequiredCount": source_freshness["reviewRequiredCount"],
            "firstClassRouteCount": exposure_counts.get("first_class_route", 0),
            "boundedRouteCount": exposure_counts.get("bounded_openclaw_route", 0),
            "catalogOnlyCount": exposure_counts.get("catalog_source_only", 0),
            "plannedAdapterCount": exposure_counts.get("planned_adapter", 0),
        },
        "providers": rows,
        "sources": source_freshness["sources"],
        "updatePolicy": {
            "mode": "safe_refresh",
            "cadence": "manual_or_weekly",
            "requiresApprovalForDefaultChanges": True,
            "neverOverwriteUserModels": True,
            "refreshProof": {
                "schemaVersion": "provider-catalog-refresh/v1",
                "command": "python scripts/provider_catalog_refresh.py",
                "artifactRoot": "artifacts/provider-catalog",
                "reviewOnly": True,
                "writesDefaults": False,
                "writesCredentials": False,
                "writesProviderRegistry": False,
                "requiresProviderHealthAfterRefresh": True,
            },
            "compatibilityWarnings": [
                "Review refreshed catalog metadata before changing default model IDs.",
                "Keep user-defined models unchanged until a route smoke test passes.",
                "Run a provider health check after catalog updates and before assigning live work.",
            ],
            "safeWorkflow": [
                "Refresh catalog metadata.",
                "Review default model changes.",
                "Run provider health checks.",
                "Keep prior routes available until verification passes.",
            ],
            "dynamicSources": [
                "https://ai-gateway.vercel.sh/v1/models",
                "OpenClaw provider directory",
                "OpenCode Models.dev-backed provider catalog",
                "LiteLLM provider registry",
            ],
            "readinessChecklist": readiness_checklist,
            "readinessSummary": {
                "readyCount": len(readiness_ready),
                "reviewCount": len(readiness_review),
                "totalCount": len(readiness_checklist),
                "safeToRefresh": len(readiness_review) == 0,
            },
        },
        "nextActions": next_actions,
    }


def reconcile_provider_secret_presence(
    snapshot: dict,
    provider_secret_presence: dict[str, bool],
) -> dict:
    """Keep masked provider credential truth consistent across setup and ecosystem rows."""
    if not isinstance(snapshot, dict) or not isinstance(provider_secret_presence, dict):
        return snapshot

    def has_any(*provider_ids: str) -> bool:
        return any(bool(provider_secret_presence.get(provider_id)) for provider_id in provider_ids)

    provider_aliases = {
        "openai": ("openai", "openai-codex"),
        "minimax": ("minimax", "minimax-cn", "minimax-portal"),
    }
    setup_status = snapshot.setdefault("providerSetupStatus", {})
    if not isinstance(setup_status, dict):
        setup_status = {}
        snapshot["providerSetupStatus"] = setup_status
    for provider_id, aliases in provider_aliases.items():
        if not has_any(*aliases):
            continue
        setup = setup_status.setdefault(provider_id, {})
        if not isinstance(setup, dict):
            setup = {}
            setup_status[provider_id] = setup
        setup["authPresent"] = True
        setup["configured"] = True
        if provider_id == "openai":
            setup.setdefault(
                "authPath",
                "OpenAI Codex OAuth" if has_any("openai-codex") and not has_any("openai") else "API key",
            )
        if provider_id == "minimax":
            setup.setdefault(
                "authPath",
                "MiniMax OpenClaw OAuth"
                if has_any("minimax-portal") and not has_any("minimax", "minimax-cn")
                else "API key",
            )
    alias_ids = {alias for aliases in provider_aliases.values() for alias in aliases}
    setup_supported_ids = {"anthropic", "openrouter"}
    for provider_id, present in provider_secret_presence.items():
        if not present:
            continue
        provider_id = str(provider_id)
        if provider_id in alias_ids or provider_id not in setup_supported_ids:
            continue
        setup = setup_status.setdefault(str(provider_id), {})
        if not isinstance(setup, dict):
            setup = {}
            setup_status[str(provider_id)] = setup
        setup["authPresent"] = True
        setup["configured"] = True

    ecosystem = snapshot.get("providerEcosystem")
    if not isinstance(ecosystem, dict):
        return snapshot
    rows = ecosystem.get("providers")
    if not isinstance(rows, list):
        return snapshot

    reconciled_rows = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        provider_id = str(item.get("providerId", "")).strip().lower()
        aliases = provider_aliases.get(provider_id, (provider_id,))
        auth_present = bool(item.get("authPresent") or has_any(*aliases))
        status = str(item.get("status") or "").strip().lower()
        existing_health = item.get("healthCheck") if isinstance(item.get("healthCheck"), dict) else {}
        blocked_by_runtime = existing_health.get("status") == "runtime_missing"
        can_route_now = bool(
            status in {"repo_supported", "credential_ready"}
            and auth_present
            and not blocked_by_runtime
        )
        compatibility_warnings = _provider_compatibility_warnings(
            item,
            auth_present=auth_present,
            can_route_now=can_route_now,
        )
        if blocked_by_runtime:
            health_check = {
                **existing_health,
                "evidence": [
                    "auth present" if auth_present else "auth missing",
                    *[
                        str(evidence)
                        for evidence in existing_health.get("evidence", [])
                        if str(evidence) not in {"auth present", "auth missing"}
                    ],
                ],
                "warnings": compatibility_warnings,
            }
        else:
            health_check = _provider_health_check(
                item,
                auth_present=auth_present,
                can_route_now=can_route_now,
                observed_route_count=int(item.get("observedRouteCount", 0) or 0),
                runtime_ids=set(),
                compatibility_warnings=compatibility_warnings,
            )
        reconciled_rows.append(
            {
                **item,
                "authPresent": auth_present,
                "canRouteNow": can_route_now,
                "compatibilityWarnings": compatibility_warnings,
                "healthCheck": health_check,
            }
        )
    ecosystem["providers"] = reconciled_rows

    implemented = [
        item for item in reconciled_rows if item.get("status") in {"repo_supported", "credential_ready"}
    ]
    route_ready = [item for item in reconciled_rows if item.get("canRouteNow")]
    missing_auth = [
        str(item.get("providerId"))
        for item in implemented
        if not item.get("authPresent")
    ]
    summary = ecosystem.setdefault("summary", {})
    if not isinstance(summary, dict):
        summary = {}
        ecosystem["summary"] = summary
    summary["totalProvidersTracked"] = len(reconciled_rows)
    summary["implementedOrCredentialReady"] = len(implemented)
    summary["routeReadyCount"] = len(route_ready)
    summary["missingAuthCount"] = len(missing_auth)

    update_policy = ecosystem.get("updatePolicy")
    if isinstance(update_policy, dict):
        checklist = update_policy.get("readinessChecklist")
        if isinstance(checklist, list):
            for check in checklist:
                if not isinstance(check, dict):
                    continue
                if check.get("checkId") == "credential_safety":
                    check["status"] = "review" if missing_auth else "ready"
                    check["summary"] = (
                        "Provider credentials are present for route-ready accounts."
                        if not missing_auth
                        else "Some supported providers still need credentials before they can route live work."
                    )
                    check["safeAction"] = (
                        "Keep stored credentials masked and connect missing providers: "
                        + ", ".join(missing_auth)
                        + "."
                        if missing_auth
                        else "Keep masked credential status visible; never write raw keys into catalog artifacts."
                    )
                if check.get("checkId") == "route_smoke":
                    check["status"] = "ready" if route_ready else "review"
                    check["safeAction"] = (
                        "Use the existing provider health check before assigning live work."
                        if route_ready
                        else "Connect at least one supported provider, then run a provider health check."
                    )
            ready = [item for item in checklist if isinstance(item, dict) and item.get("status") == "ready"]
            review = [item for item in checklist if isinstance(item, dict) and item.get("status") != "ready"]
            summary["updateReadinessReadyCount"] = len(ready)
            summary["updateReadinessReviewCount"] = len(review)
            update_policy["readinessSummary"] = {
                "readyCount": len(ready),
                "reviewCount": len(review),
                "totalCount": len(checklist),
                "safeToRefresh": len(review) == 0,
            }
    return snapshot


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
        path.write_text(serialized, encoding="utf-8")

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
            run_budget = MissionRunBudget(**item.get("run_budget", {}))
            verification_policy = MissionVerificationPolicy(
                **item.get("verification_policy", {})
            )
            escalation_policy = ApprovalEscalation(
                **item.get("escalation_policy", {})
            )
            state = MissionStateSnapshot(**item.get("state", {}))
            proof = MissionProof(**item.get("proof", {}))
            execution_scope = ExecutionScope(**item.get("execution_scope", {}))
            execution_policy = ExecutionPolicy(
                **item.get("execution_policy", {"profile_name": item.get("selected_profile", "builder")})
            )
            code_execution = MissionCodeExecutionConfig(
                **item.get("code_execution", {})
            )
            delegated_runtime_sessions = [
                DelegatedRuntimeSession(**row)
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
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=True) + "\n")

    def recent_events(self, limit: int = 40) -> list[dict]:
        if not self.events_path.exists():
            return []
        lines = [
            line.strip()
            for line in self.events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return [json.loads(line) for line in lines[-limit:]][::-1]

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

        for mission in missions:
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
            mission.state.provider_runtime_truth = _provider_truth_for_mission(
                mission,
                auth_presence=provider_auth_presence,
                workspace=workspace_lookup.get(mission.workspace_id),
            )
            mission.state.skill_recovery = build_skill_recovery_snapshot(
                mission,
                skill_library=skill_library,
            )
            sync_mission_state_snapshot(mission)
        self._rebalance_workspace_queue_in_place(missions)
        missions_payload = []
        for item in missions:
            mission_payload = asdict(item)
            mission_payload["missionLoop"] = build_mission_loop_snapshot(item)
            mission_payload["effectiveRouteContract"] = (
                item.effective_route_contract
                if item.effective_route_contract
                else _effective_route_contract_for_mission(item)
            )
            mission_payload["providerTruth"] = dict(item.state.provider_runtime_truth or {})
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
        provider_ecosystem = _build_provider_ecosystem_snapshot(
            provider_setup_status=provider_setup_status,
            provider_auth_presence=provider_auth_presence,
            runtime_statuses=runtime_statuses,
            harness_lab=harness_lab_snapshot,
        )
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
        fusion_workbench = build_mindtower_fusion_snapshot(self.root)
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
            "providerEcosystem": provider_ecosystem,
            "efficiencyAutotune": efficiency_autotune,
            "bridgeLab": connected_apps_snapshot,
            "fusionWorkbench": fusion_workbench,
            "storageBridge": storage_bridge,
            "releaseReadiness": release_readiness,
            "runtimeCompartments": runtime_compartments,
            "generatedImageArtifacts": generated_image_artifacts,
            "hermesMissionEvidence": hermes_mission_evidence,
            "nasDeployReadiness": nas_deploy_readiness,
            "autonomousWorkflows": autonomous_workflows,
        }

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
            _sync_execution_scope_snapshot(mission)
            mission.state.skill_recovery = build_skill_recovery_snapshot(mission)
            mission_payload = asdict(mission)
            mission_payload["missionLoop"] = build_mission_loop_snapshot(mission)
            mission_payload["effectiveRouteContract"] = (
                mission.effective_route_contract
                if mission.effective_route_contract
                else _effective_route_contract_for_mission(mission)
            )
            mission_payload["providerTruth"] = dict(mission.state.provider_runtime_truth or {})
            missions_payload.append(mission_payload)
        storage_bridge: dict = {}
        setup_health: dict = {"actionHistory": []}
        autonomous_workflows = self.reconcile_autonomous_workflows(missions)
        provider_setup_status: dict = {}
        provider_ecosystem = _build_provider_ecosystem_snapshot(
            provider_setup_status=provider_setup_status,
            provider_auth_presence=provider_auth_presence,
            runtime_statuses=[],
            harness_lab={},
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
            "providerSetupStatus": provider_setup_status,
            "providerEcosystem": provider_ecosystem,
            "efficiencyAutotune": {},
            "bridgeLab": {"connectedSessions": []},
            "fusionWorkbench": build_mindtower_fusion_snapshot(self.root),
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
        if not path.exists():
            return default
        try:
            raw = path.read_text(encoding="utf-8").strip()
        except OSError:
            return default
        if not raw:
            return default
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return default

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


def _skill_recovery_evidence(values: list[object], limit: int = 4) -> list[str]:
    evidence: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in evidence:
            evidence.append(text)
        if len(evidence) >= limit:
            break
    return evidence


def _recovery_action_for_trigger(kind: str) -> str:
    actions = {
        "mission_blocked": "Inspect the recorded blocker, confirm the missing input or approval, then resume from the latest mission state.",
        "verification_failure": "Run the verification skill against the failed checks, capture the failing command output, and replan only from that evidence.",
        "repeated_failure": "Stop retrying the same step, inspect the last failures, and choose a different skill or route before resuming.",
        "context_missing": "Generate a handoff or repo-grounding packet before continuing so the next runtime has the missing context.",
        "weak_provider_route": "Repair the provider route or auth state before retrying; keep Hermes/OpenClaw as runtime lanes, not provider fallbacks.",
        "runtime_lane_attention": "Inspect the delegated runtime session and restart or resume that lane only after heartbeat and approval state are clear.",
    }
    return actions.get(kind, "Inspect the mission evidence and choose the smallest recovery action before retrying.")


def _recovery_loop_step_for_trigger(kind: str) -> str:
    steps = {
        "mission_blocked": "plan",
        "verification_failure": "verify",
        "repeated_failure": "repair",
        "context_missing": "plan",
        "weak_provider_route": "route",
        "runtime_lane_attention": "observe",
    }
    return steps.get(kind, "repair")


def _recovery_proof_requirement_for_trigger(kind: str) -> dict:
    requirements = {
        "mission_blocked": {
            "artifactKind": "blocker_decision_receipt",
            "label": "Decision receipt",
            "minimumEvidence": [
                "blocker label",
                "operator decision or safe assumption",
                "resume point",
            ],
        },
        "verification_failure": {
            "artifactKind": "verification_failure_receipt",
            "label": "Failing check output",
            "minimumEvidence": [
                "command",
                "exit code",
                "reproduced output",
                "next focused repair",
            ],
        },
        "repeated_failure": {
            "artifactKind": "retry_guard_receipt",
            "label": "Retry guard receipt",
            "minimumEvidence": [
                "last failed attempts",
                "changed skill or route",
                "smallest next test",
            ],
        },
        "context_missing": {
            "artifactKind": "handoff_context_receipt",
            "label": "Context handoff packet",
            "minimumEvidence": [
                "missing context",
                "source files or artifacts",
                "handoff summary",
            ],
        },
        "weak_provider_route": {
            "artifactKind": "provider_route_health_receipt",
            "label": "Provider route health",
            "minimumEvidence": [
                "provider",
                "model",
                "auth status",
                "route reason",
            ],
        },
        "runtime_lane_attention": {
            "artifactKind": "runtime_lane_recovery_receipt",
            "label": "Runtime lane receipt",
            "minimumEvidence": [
                "runtime lane",
                "heartbeat",
                "last event",
                "resume or restart decision",
            ],
        },
    }
    return requirements.get(
        kind,
        {
            "artifactKind": "mission_recovery_receipt",
            "label": "Recovery receipt",
            "minimumEvidence": ["trigger", "selected action", "verification command"],
        },
    )


def _build_skill_recovery_plan(
    *,
    mission: Mission,
    triggers: list[dict],
    recommendations: list[dict],
    runtime_lane: str,
    active_route: dict,
) -> dict:
    primary_trigger = triggers[0] if triggers else {}
    primary_recommendation = recommendations[0] if recommendations else {}
    selected_skill_id = str(
        primary_recommendation.get("skillId")
        or ("stuck_state_recovery" if triggers else "")
    )
    selected_skill_label = str(
        primary_recommendation.get("label")
        or ("Stuck State Recovery" if triggers else "")
    )
    trigger_id = str(primary_trigger.get("triggerId") or "normal_flow")
    proof_requirement = _recovery_proof_requirement_for_trigger(trigger_id)
    provider_route = {
        "role": str(active_route.get("role", "") or "").strip().lower(),
        "provider": str(active_route.get("provider", "") or "").strip().lower(),
        "model": str(active_route.get("model", "") or "").strip(),
    }
    route_bits = [
        selected_skill_label or "No recovery skill",
        f"runtime lane {runtime_lane or mission.runtime_id or 'unresolved'}",
        provider_route["provider"] or "provider unresolved",
        provider_route["model"] or "model unresolved",
    ]
    return {
        "schemaVersion": "mission-skill-recovery-plan.v1",
        "status": "ready" if triggers else "idle",
        "selectedSkill": {
            "skillId": selected_skill_id,
            "label": selected_skill_label,
            "sourceKind": str(primary_recommendation.get("sourceKind") or ""),
            "executionCapable": bool(primary_recommendation.get("executionCapable", False)),
            "guidanceOnly": bool(primary_recommendation.get("guidanceOnly", False)),
        },
        "runtimeLane": runtime_lane or mission.runtime_id or "",
        "providerRoute": provider_route,
        "routeReason": (
            str(primary_trigger.get("reason") or "")
            or "No recovery trigger is active; continue the normal plan-execute-verify loop."
        ),
        "loopStep": _recovery_loop_step_for_trigger(trigger_id),
        "nextAction": str(
            primary_trigger.get("recoveryAction")
            or "Continue the normal plan-execute-verify loop."
        ),
        "retryGuard": {
            "mode": "change_skill_or_route_before_retry" if triggers else "normal_flow",
            "blockSameStepRetry": bool(triggers),
            "reason": (
                "A recovery trigger is active, so the same step should not be retried "
                "without a changed skill, route, handoff, or proof packet."
                if triggers
                else "No retry guard is active."
            ),
        },
        "proofRequirement": proof_requirement,
        "proofArtifactPlan": {
            "artifactKind": proof_requirement["artifactKind"],
            "suggestedPath": (
                f"artifacts/mission-recovery/{mission.mission_id}/"
                f"{trigger_id}-{proof_requirement['artifactKind']}.json"
                if triggers
                else ""
            ),
            "mustAttachBeforeRetry": bool(triggers),
        },
        "visibleRouteSummary": " · ".join(item for item in route_bits if item),
    }


def _mission_skill_recovery_triggers(mission: Mission) -> list[dict]:
    triggers: list[dict] = []
    delegated = mission.delegated_runtime_sessions or []
    provider_truth = (
        dict(mission.state.provider_runtime_truth)
        if isinstance(mission.state.provider_runtime_truth, dict)
        else {}
    )
    active_route = (
        dict(provider_truth.get("activeRoute", {}))
        if isinstance(provider_truth.get("activeRoute"), dict)
        else {}
    )
    runtime_lane = _current_runtime_lane_for_mission(mission, delegated)
    route_contract = (
        mission.effective_route_contract
        if mission.effective_route_contract
        else _effective_route_contract_for_mission(mission)
    )
    route_rows = route_contract.get("roles", []) if isinstance(route_contract, dict) else []
    if not isinstance(route_rows, list):
        route_rows = []

    def add_trigger(kind: str, label: str, reason: str, severity: str, evidence: list[object]) -> None:
        if any(item["triggerId"] == kind for item in triggers):
            return
        triggers.append(
            {
                "triggerId": kind,
                "kind": kind,
                "label": label,
                "severity": severity,
                "reason": reason,
                "evidence": _skill_recovery_evidence(evidence),
                "recoveryAction": _recovery_action_for_trigger(kind),
                "loopStep": _recovery_loop_step_for_trigger(kind),
                "proofRequirement": _recovery_proof_requirement_for_trigger(kind),
            }
        )

    if mission.state.status == "blocked" or mission.proof.blocked_by:
        add_trigger(
            "mission_blocked",
            "Mission blocked",
            "Mission state or proof contains an explicit blocker.",
            "high",
            [*mission.proof.blocked_by, mission.state.last_error, mission.state.stop_reason],
        )

    verification_failures = [
        *list(mission.state.verification_failures or []),
        *list(mission.proof.failed_checks or []),
    ]
    if mission.state.status == "verification_failed" or verification_failures:
        add_trigger(
            "verification_failure",
            "Verification failed",
            "Verification proof has failed checks that need evidence-driven recovery.",
            "high",
            verification_failures,
        )

    if int(mission.state.repeated_failure_count or 0) >= 2:
        add_trigger(
            "repeated_failure",
            "Repeated failures",
            "The same mission has failed repeatedly and should not continue with the same route blindly.",
            "high",
            [
                f"repeated_failure_count={mission.state.repeated_failure_count}",
                mission.state.last_error,
                mission.state.last_replan_reason,
            ],
        )

    context_status = str(mission.state.context_status or "ok").strip().lower()
    if context_status in {"missing", "insufficient", "needs_handoff", "handoff_required", "critical", "exhausted"} or float(mission.state.context_usage_ratio or 0.0) >= 0.85:
        add_trigger(
            "context_missing",
            "Context needs recovery",
            "Mission context is missing, near rollover, or needs a handoff before another runtime continues.",
            "medium",
            [
                f"context_status={context_status}",
                f"context_usage_ratio={mission.state.context_usage_ratio}",
                mission.state.last_handoff_reason,
            ],
        )

    active_provider = str(active_route.get("provider", "") or "").strip().lower()
    active_model = str(active_route.get("model", "") or "").strip()
    last_failure = (
        dict(provider_truth.get("lastFailure", {}))
        if isinstance(provider_truth.get("lastFailure"), dict)
        else {}
    )
    route_is_weak = (
        not route_rows
        or not active_provider
        or not active_model
        or (active_provider and provider_truth.get("authKnown") and not provider_truth.get("authPresent"))
        or bool(last_failure)
        or int(mission.state.route_change_count or 0) >= 2
    )
    if route_is_weak:
        add_trigger(
            "weak_provider_route",
            "Provider route needs attention",
            "The provider/model route is unresolved, unauthenticated, recently failed, or changing too often.",
            "medium" if active_provider else "high",
            [
                f"provider={active_provider or 'unresolved'}",
                f"model={active_model or 'unresolved'}",
                f"route_count={len(route_rows)}",
                f"auth_present={provider_truth.get('authPresent')}",
                last_failure.get("summary", ""),
            ],
        )

    runtime_evidence: list[str] = []
    for session in delegated:
        row = asdict(session) if hasattr(session, "__dataclass_fields__") else dict(session)
        status = str(row.get("status", "") or "").strip().lower()
        heartbeat = str(row.get("heartbeat_status", "") or "").strip().lower()
        if status in {"failed", "stopped"} or heartbeat == "stale":
            runtime_evidence.append(
                " ".join(
                    [
                        str(row.get("runtime_id", "") or "runtime"),
                        str(row.get("delegated_id", "") or ""),
                        status or "unknown",
                        heartbeat or "",
                    ]
                ).strip()
            )
    if runtime_evidence:
        add_trigger(
            "runtime_lane_attention",
            "Runtime lane needs attention",
            "A delegated Hermes/OpenClaw runtime session failed, stopped, or has a stale heartbeat.",
            "high",
            runtime_evidence,
        )

    for trigger in triggers:
        trigger["runtimeLane"] = runtime_lane
        trigger["providerRoute"] = {
            "role": str(active_route.get("role", "") or "").strip().lower(),
            "provider": active_provider,
            "model": active_model,
        }
    return triggers


def build_skill_recovery_snapshot(
    mission: Mission,
    *,
    skill_library: SkillLibrary | None = None,
    recommendation_limit: int = 6,
) -> dict:
    triggers = _mission_skill_recovery_triggers(mission)
    provider_truth = (
        dict(mission.state.provider_runtime_truth)
        if isinstance(mission.state.provider_runtime_truth, dict)
        else {}
    )
    active_route = (
        dict(provider_truth.get("activeRoute", {}))
        if isinstance(provider_truth.get("activeRoute"), dict)
        else {}
    )
    runtime_lane = _current_runtime_lane_for_mission(
        mission,
        mission.delegated_runtime_sessions or [],
    )
    recommendations: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for trigger in triggers:
        if skill_library is None:
            candidates = []
        else:
            query = " ".join(
                [
                    mission.objective,
                    trigger["kind"],
                    trigger["label"],
                    trigger["reason"],
                    " ".join(trigger.get("evidence", [])),
                ]
            )
            candidates = skill_library.retrieve(query, top_k=3)
        for rank, skill in enumerate(candidates):
            skill_id = str(skill.get("skillId", "") or "")
            if not skill_id:
                continue
            key = (trigger["triggerId"], skill_id)
            if key in seen:
                continue
            seen.add(key)
            recommendations.append(
                {
                    "recommendationId": f"{trigger['triggerId']}:{skill_id}",
                    "triggerId": trigger["triggerId"],
                    "skillId": skill_id,
                    "label": skill.get("label", skill_id),
                    "sourceKind": skill.get("sourceKind", "curated"),
                    "reason": f"{skill.get('label', skill_id)} matches {trigger['label'].lower()} recovery.",
                    "routeReason": trigger["reason"],
                    "loopStep": trigger.get("loopStep", _recovery_loop_step_for_trigger(trigger["triggerId"])),
                    "recoveryAction": trigger["recoveryAction"],
                    "proofRequirement": trigger.get(
                        "proofRequirement",
                        _recovery_proof_requirement_for_trigger(trigger["triggerId"]),
                    ),
                    "permissions": skill.get("permissions", []),
                    "actionKinds": skill.get("actionKinds", []),
                    "profileSuitability": skill.get("profileSuitability", []),
                    "guidanceOnly": bool(skill.get("guidanceOnly", False)),
                    "executionCapable": bool(skill.get("executionCapable", False)),
                    "confidence": round(max(0.52, 0.86 - (rank * 0.08)), 2),
                    "evidence": trigger.get("evidence", []),
                    "appliesTo": {
                        "missionStatus": mission.state.status,
                        "currentPhase": mission.state.current_cycle_phase,
                        "runtimeLane": runtime_lane,
                        "providerRoute": {
                            "role": str(active_route.get("role", "") or "").strip().lower(),
                            "provider": str(active_route.get("provider", "") or "").strip().lower(),
                            "model": str(active_route.get("model", "") or "").strip(),
                        },
                    },
                }
            )
            if len(recommendations) >= recommendation_limit:
                break
        if len(recommendations) >= recommendation_limit:
            break

    recovery_actions = []
    for trigger in triggers:
        recovery_actions.append(
            {
                "triggerId": trigger["triggerId"],
                "label": trigger["label"],
                "action": trigger["recoveryAction"],
                "severity": trigger["severity"],
                "loopStep": trigger.get("loopStep", _recovery_loop_step_for_trigger(trigger["triggerId"])),
                "proofRequirement": trigger.get(
                    "proofRequirement",
                    _recovery_proof_requirement_for_trigger(trigger["triggerId"]),
                ),
            }
        )

    recovery_plan = _build_skill_recovery_plan(
        mission=mission,
        triggers=triggers,
        recommendations=recommendations,
        runtime_lane=runtime_lane,
        active_route=active_route,
    )

    return {
        "schemaVersion": "mission-skill-recovery.v1",
        "status": "needs_recovery" if triggers else "idle",
        "generatedFrom": "mission_state_and_skill_registry",
        "triggerCount": len(triggers),
        "triggers": triggers,
        "recommendations": recommendations,
        "recoveryActions": recovery_actions,
        "recoveryPlan": recovery_plan,
        "routeSeparation": {
            "runtimeLane": runtime_lane,
            "providerRoute": {
                "role": str(active_route.get("role", "") or "").strip().lower(),
                "provider": str(active_route.get("provider", "") or "").strip().lower(),
                "model": str(active_route.get("model", "") or "").strip(),
            },
            "rule": "Hermes/OpenClaw are runtime lanes; OpenAI/MiniMax/etc. are provider routes.",
        },
    }


def _build_supervisor_interventions(mission: Mission, skill_recovery: dict) -> list[dict]:
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    interventions: list[dict] = []

    def add(
        intervention_id: str,
        *,
        source: str,
        severity: str,
        label: str,
        reason: str,
        next_action: str,
        target_drawer: str,
        runtime_lane: dict | None = None,
        provider_route: dict | None = None,
        lane_id: str = "",
        proof_required: bool = True,
    ) -> None:
        if any(item["interventionId"] == intervention_id for item in interventions):
            return
        interventions.append(
            {
                "interventionId": intervention_id,
                "source": source,
                "severity": severity,
                "label": label,
                "reason": reason,
                "nextAction": next_action,
                "targetDrawer": target_drawer,
                "runtimeLane": runtime_lane or {},
                "providerRoute": provider_route or {},
                "laneId": lane_id,
                "proofRequired": proof_required,
            }
        )

    for trigger in skill_recovery.get("triggers", []) if isinstance(skill_recovery, dict) else []:
        if not isinstance(trigger, dict):
            continue
        trigger_id = str(trigger.get("triggerId") or trigger.get("kind") or "skill_recovery")
        add(
            f"skill:{trigger_id}",
            source="skill_recovery",
            severity=str(trigger.get("severity") or "medium"),
            label=str(trigger.get("label") or "Skill recovery needed"),
            reason=str(trigger.get("reason") or "Mission recovery trigger is active."),
            next_action=str(trigger.get("recoveryAction") or "Select a relevant skill and rerun the smallest verification step."),
            target_drawer="skills" if trigger_id in {"context_missing", "weak_provider_route"} else "queue",
            runtime_lane=trigger.get("runtimeLane") if isinstance(trigger.get("runtimeLane"), dict) else {},
            provider_route=trigger.get("providerRoute") if isinstance(trigger.get("providerRoute"), dict) else {},
        )

    for index, approval in enumerate(mission.proof.pending_approvals or []):
        add(
            f"approval:{index}",
            source="approval",
            severity="high",
            label="Approval boundary waiting",
            reason=str(approval or "A mission approval must be resolved before continuing this lane."),
            next_action="Open the queue, resolve the approval, then resume the smallest independent task.",
            target_drawer="queue",
            proof_required=False,
        )

    failures = [*list(mission.state.verification_failures or []), *list(mission.proof.failed_checks or [])]
    if failures:
        add(
            "verification:failed-proof",
            source="verification",
            severity="high",
            label="Verification proof failed",
            reason="; ".join(str(item) for item in failures[:3]),
            next_action="Run the smallest failing check, attach output, and repair before expanding scope.",
            target_drawer="proof",
        )

    for session in mission.delegated_runtime_sessions or []:
        row = asdict(session) if hasattr(session, "__dataclass_fields__") else dict(session)
        status = str(row.get("status", "") or "").strip().lower()
        heartbeat = str(row.get("heartbeat_status", "") or "").strip().lower()
        pending_approval = bool(row.get("pending_approval"))
        if status in {"failed", "blocked", "waiting_for_approval", "stopped"} or heartbeat == "stale" or pending_approval:
            lane_id = str(row.get("delegated_id") or row.get("session_id") or row.get("runtime_id") or "runtime-lane")
            add(
                f"runtime:{lane_id}",
                source="delegated_runtime",
                severity="high" if status in {"failed", "blocked"} or heartbeat == "stale" else "medium",
                label="Delegated runtime lane needs review",
                reason=f"{row.get('runtime_id') or 'runtime'} lane {status or 'unknown'}; heartbeat {heartbeat or 'unknown'}",
                next_action="Inspect runtime events, resolve approvals or stale heartbeat, then verify proof before merging.",
                target_drawer="runtime",
                runtime_lane={
                    "runtime": row.get("runtime_id") or "",
                    "status": status,
                    "heartbeatStatus": heartbeat,
                },
                lane_id=lane_id,
            )

    interventions.sort(key=lambda item: (severity_rank.get(item["severity"], 3), item["source"], item["interventionId"]))
    return interventions[:6]


def build_mission_loop_snapshot(mission: Mission) -> dict:
    plan_revisions = mission.plan_revisions or []
    latest_revision = plan_revisions[-1] if plan_revisions else None
    delegated = mission.delegated_runtime_sessions or []
    if mission.state.status in {"queued", "draft"}:
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
    skill_recovery = mission.state.skill_recovery or build_skill_recovery_snapshot(mission)

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
        "runtimeAutonomy": mission.state.runtime_autonomy,
        "routeChangeCount": mission.state.route_change_count,
        "parallelAgents": mission.state.parallel_agents,
        "mergePolicy": mission.state.merge_policy,
        "blocker": mission.state.blocker_classification,
        "providerTruth": mission.state.provider_runtime_truth,
        "codeExecution": mission.state.code_execution,
        "skillRecovery": skill_recovery,
        "supervisorInterventions": _build_supervisor_interventions(mission, skill_recovery),
    }


def sync_mission_state_snapshot(mission: Mission) -> dict:
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
    mission.state.blocker_classification = mission_loop.get("blocker", {})
    mission.state.provider_runtime_truth = mission_loop.get("providerTruth", {})
    mission.state.code_execution = mission_loop.get("codeExecution", {})
    mission.state.skill_recovery = mission_loop.get("skillRecovery", {})
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


def _plan_revision_value(revision: object, key: str) -> str:
    if revision is None:
        return ""
    if isinstance(revision, dict):
        return str(revision.get(key, "") or "")
    return str(getattr(revision, key, "") or "")


def _provider_auth_presence_from_env() -> dict[str, bool]:
    presence: dict[str, bool] = {}
    for provider_id, env_name in PROVIDER_ENV_HINTS.items():
        presence[provider_id] = bool(str(os.environ.get(env_name, "")).strip())
    if str(os.environ.get("FLUXIO_OPENAI_CODEX_OAUTH_PRESENT", "")).strip():
        presence["openai-codex"] = True
    if str(os.environ.get("FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT", "")).strip():
        presence["minimax-portal"] = True
    return presence


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
    locked_samples: list[str] = []
    for item in passes:
        files_copied += int(item.get("filesCopied", 0) or 0)
        files_skipped += int(item.get("filesSkipped", 0) or 0)
        locked_skipped += int(item.get("lockedFilesSkipped", 0) or 0)
        missing_skipped += int(item.get("missingFilesSkipped", 0) or 0)
        for sample in item.get("lockedFileSamples", []):
            sample_text = str(sample or "").strip()
            if not sample_text or sample_text in locked_samples:
                continue
            locked_samples.append(sample_text)
            if len(locked_samples) >= SYNC_LOCKED_FILE_SAMPLE_LIMIT:
                break

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
    locked_samples: list[str] = []
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
    if locked_skipped:
        payload["reason"] = "copied_with_locked_files"
        payload["lockedFilesSkipped"] = locked_skipped
        payload["lockedFileSamples"] = locked_samples
    if missing_skipped:
        payload["missingFilesSkipped"] = missing_skipped
    return payload


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
    openai_auth_mode = normalize_openai_codex_auth_mode(
        getattr(workspace, "openai_codex_auth_mode", "none")
    )
    minimax_auth_mode = normalize_minimax_auth_mode(
        getattr(workspace, "minimax_auth_mode", "none")
    )
    if active_provider in {"openai", "openai-codex"}:
        api_key_present = bool(
            auth_presence.get("openai", False)
        )
        oauth_present = bool(auth_presence.get("openai-codex", False))
        auth_present = (
            (openai_auth_mode == "api" and api_key_present)
            or (openai_auth_mode == "oauth" and oauth_present)
            or api_key_present
        )
        auth_mode = (
            openai_auth_mode
            if openai_auth_mode != "none"
            else ("api" if api_key_present else ("oauth" if oauth_present else "none"))
        )
        auth_path = openai_codex_auth_label(auth_mode)
    elif active_provider in {"minimax", "minimax-portal", "minimax-cn"}:
        api_key_present = bool(
            auth_presence.get("minimax", False)
            or auth_presence.get("minimax-cn", False)
        )
        oauth_present = bool(auth_presence.get("minimax-portal", False))
        auth_present = (
            (minimax_auth_mode == "minimax-api" and api_key_present)
            or (minimax_auth_mode == "minimax-portal-oauth" and oauth_present)
            or api_key_present
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
        auth_path = minimax_auth_label(auth_mode)
    else:
        auth_present = bool(auth_presence.get(active_provider, False)) if active_provider else False
        auth_mode = ""
        auth_path = ""
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
        },
        "authPresent": auth_present,
        "authKnown": bool(active_provider),
        "authMode": auth_mode,
        "authPath": auth_path,
        "lastSuccessfulCall": last_success,
        "lastFailure": last_failure,
        "updatedAt": truth_updated_at,
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
    if mission.state.status in TERMINAL_MISSION_STATUSES:
        return "terminal", "Mission is in a terminal state with recorded proof."
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
    waiting_session = next(
        (item for item in delegated if item.status == "waiting_for_approval"),
        None,
    )
    if waiting_session is not None:
        return waiting_session.pending_approval.get(
            "prompt",
            "Delegated runtime is paused on approval.",
        )

    raw_reason = mission.state.stop_reason or mission.state.last_budget_pause_reason or ""
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
        return mission.state.queue_reason or "Mission is queued behind another active mission."
    if mission.state.status == "blocked":
        return mission.state.last_error or "Mission is paused and needs operator attention."
    return ""


def _current_runtime_lane_for_mission(
    mission: Mission,
    delegated: list[DelegatedRuntimeSession],
) -> str:
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
            "updateSafety": _runtime_update_safety(
                {
                    **existing,
                    "serviceId": runtime_id,
                    "label": runtime_status.get("label", runtime_id),
                    "version": runtime_status.get("version") or existing.get("version", ""),
                    "latestVersion": runtime_status.get("latest_version") or existing.get("latestVersion", ""),
                    "updateAvailable": runtime_status.get("update_available", existing.get("updateAvailable", False)),
                }
            ),
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
            "passed": completed_counts["openclaw"] > 0,
            "details": f"Completed OpenClaw missions: {completed_counts['openclaw']}.",
        },
        {
            "proofId": "hermes_delegated_mission",
            "label": "Hermes delegated mission completed",
            "passed": completed_counts["hermes"] > 0,
            "details": f"Completed Hermes missions: {completed_counts['hermes']}.",
        },
        {
            "proofId": "approval_wait_evidence",
            "label": "Hermes approval-wait evidence recorded",
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
            "passed": delegated_active_seen,
            "details": (
                "At least one mission recorded `delegated_active` continuity."
                if delegated_active_seen
                else "No delegated-active continuity state has been recorded yet."
            ),
        },
    ]
    missing = [item["label"] for item in proofs if not item["passed"]]
    next_actions = [f"Capture proof: {label}." for label in missing]
    return {
        "missionCount": len(missions),
        "runtimeMissionCounts": runtime_counts,
        "runtimeCompletionCounts": completed_counts,
        "proofs": proofs,
        "missingProofs": missing,
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
    auth_present = bool(provider_truth.get("authPresent"))
    last_failure = provider_truth.get("lastFailure") if isinstance(provider_truth.get("lastFailure"), dict) else {}
    lanes: list[dict] = []
    seen_roles: set[str] = set()
    for role in ("planner", "executor", "verifier"):
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
        health = "ready" if auth_present and provider in {"openai", "openai-codex"} else ("blocked" if provider else "unknown")
        blocker = ""
        if provider not in {"openai", "openai-codex"}:
            blocker = "Route is not using the OpenAI Codex coding path."
            health = "blocked"
        elif not auth_present:
            blocker = "OpenAI Codex OAuth/API auth is not present for this runtime."
        if last_failure and str(last_failure.get("role", "")).strip().lower() == role:
            blocker = str(last_failure.get("summary") or blocker)
            health = "blocked"
        lanes.append(
            {
                "role": role,
                "phase": "plan" if role == "planner" else ("verify" if role == "verifier" else "execute"),
                "provider": provider,
                "model": model,
                "effort": str(route.get("effort") or active_route.get("effort") or "medium"),
                "authPresent": auth_present if provider in {"openai", "openai-codex"} else False,
                "authPath": str(provider_truth.get("authPath") or "OpenAI Codex OAuth"),
                "health": health,
                "active": role == active_role or (not active_role and role == "executor"),
                "blocker": blocker,
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
            lanes.append(
                {
                    "role": role,
                    "phase": role,
                    "provider": str(item.get("provider") or ""),
                    "model": str(item.get("model") or ""),
                    "effort": str(item.get("effort") or "medium"),
                    "authPresent": False,
                    "authPath": "",
                    "health": "unknown",
                    "active": False,
                    "blocker": "",
                    "actions": ["inspect-events"],
                }
            )
    return lanes


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
            runtime_proof_receipt = (
                payload.get("runtimeProofReceipt")
                if isinstance(payload.get("runtimeProofReceipt"), dict)
                else {}
            )
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
                    "runtimeProofReceipt": runtime_proof_receipt,
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
            candidates.append(Path("C:/volume1") / normalized.removeprefix("/volume1/"))
            if os.name != "nt":
                candidates.append(Path("/mnt/c/volume1") / normalized.removeprefix("/volume1/"))
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
                sibling_images = [
                    item
                    for item in manifest_path.parent.glob(f"{manifest_path.name.removesuffix('.manifest.json')}.*")
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


def _route_contract_present(payload: dict) -> bool:
    effective_contract = payload.get("effective_route_contract", {})
    if isinstance(effective_contract, dict) and effective_contract.get("roles"):
        return True
    route_configs = payload.get("route_configs", [])
    if isinstance(route_configs, list) and any(isinstance(item, dict) for item in route_configs):
        return True
    delegated_sessions = payload.get("delegated_runtime_sessions", [])
    if not isinstance(delegated_sessions, list):
        return False
    return any(
        isinstance(item, dict)
        and (
            str(item.get("target_model", "")).strip()
            or str(item.get("target_provider", "")).strip()
            or str(item.get("target_phase", "")).strip()
        )
        for item in delegated_sessions
    )


def _route_provider_from_payload(payload: dict) -> str:
    effective_contract = payload.get("effective_route_contract", {})
    if isinstance(effective_contract, dict):
        roles = effective_contract.get("roles", [])
        if isinstance(roles, list):
            for item in roles:
                if isinstance(item, dict) and str(item.get("provider", "")).strip():
                    return str(item.get("provider", "")).strip().lower()
    route_configs = payload.get("route_configs", [])
    if isinstance(route_configs, list):
        for item in route_configs:
            if isinstance(item, dict) and str(item.get("provider", "")).strip():
                return str(item.get("provider", "")).strip().lower()
    delegated_sessions = payload.get("delegated_runtime_sessions", [])
    if isinstance(delegated_sessions, list):
        for item in delegated_sessions:
            if isinstance(item, dict) and str(item.get("target_provider", "")).strip():
                return str(item.get("target_provider", "")).strip().lower()
    return ""


def _observed_runtime_lane_counts(root: Path, recent_runs: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for run in recent_runs:
        runtime_id = str(run.get("runtimeId", "") or "").strip()
        if runtime_id:
            counts[runtime_id] = counts.get(runtime_id, 0) + 1

    runtime_root = root / ".agent_control" / "runtime_sessions"
    if runtime_root.exists():
        for path in runtime_root.glob("delegate_*.json"):
            payload = _load_json_file(path)
            if not isinstance(payload, dict):
                continue
            runtime_id = str(payload.get("runtime_id", "") or "").strip()
            if runtime_id:
                counts[runtime_id] = counts.get(runtime_id, 0) + 1
    return counts


def _observed_route_provider_counts(root: Path, recent_runs: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for run in recent_runs:
        provider = str(run.get("routeProvider", "") or "").strip().lower()
        if provider:
            counts[provider] = counts.get(provider, 0) + 1

    runtime_root = root / ".agent_control" / "runtime_sessions"
    if runtime_root.exists():
        for path in runtime_root.glob("delegate_*.json"):
            payload = _load_json_file(path)
            if not isinstance(payload, dict):
                continue
            provider = str(payload.get("target_provider", "") or "").strip().lower()
            if provider:
                counts[provider] = counts.get(provider, 0) + 1
    return counts


def _route_model_from_payload(payload: dict) -> str:
    effective_contract = payload.get("effective_route_contract", {})
    if isinstance(effective_contract, dict):
        roles = effective_contract.get("roles", [])
        if isinstance(roles, list):
            for item in roles:
                if isinstance(item, dict) and str(item.get("model", "")).strip():
                    return str(item.get("model", "")).strip()
    route_configs = payload.get("route_configs", [])
    if isinstance(route_configs, list):
        for item in route_configs:
            if isinstance(item, dict) and str(item.get("model", "")).strip():
                return str(item.get("model", "")).strip()
    delegated_sessions = payload.get("delegated_runtime_sessions", [])
    if isinstance(delegated_sessions, list):
        for item in delegated_sessions:
            if isinstance(item, dict) and str(item.get("target_model", "")).strip():
                return str(item.get("target_model", "")).strip()
    return ""


def _route_role_from_payload(payload: dict) -> str:
    effective_contract = payload.get("effective_route_contract", {})
    if isinstance(effective_contract, dict):
        roles = effective_contract.get("roles", [])
        if isinstance(roles, list):
            for item in roles:
                if isinstance(item, dict) and str(item.get("role", "")).strip():
                    return str(item.get("role", "")).strip()
    route_configs = payload.get("route_configs", [])
    if isinstance(route_configs, list):
        for item in route_configs:
            if isinstance(item, dict) and str(item.get("role", "")).strip():
                return str(item.get("role", "")).strip()
    delegated_sessions = payload.get("delegated_runtime_sessions", [])
    if isinstance(delegated_sessions, list):
        for item in delegated_sessions:
            if isinstance(item, dict) and str(item.get("target_phase", "")).strip():
                return str(item.get("target_phase", "")).strip()
    return "mission"


def _route_decision_recommendation(row: dict) -> tuple[str, str, str]:
    observed = int(row.get("observedRuns", 0) or 0)
    completed = int(row.get("completedRuns", 0) or 0)
    blocked = int(row.get("blockedRuns", 0) or 0)
    verification_failures = int(row.get("verificationFailures", 0) or 0)
    delegated_lanes = int(row.get("delegatedLaneCount", 0) or 0)
    route_contracts = int(row.get("routeContractProofCount", 0) or 0)
    if observed == 0 and delegated_lanes == 0:
        return (
            "needs_evidence",
            "Needs local evidence",
            "Run this route once before treating it as a recommended choice.",
        )
    if verification_failures > completed or blocked > completed + delegated_lanes:
        return (
            "avoid_for_now",
            "Avoid until cleared",
            "Recent local evidence is dominated by verification, approval, or blocked-state friction.",
        )
    if completed > 0 and route_contracts > 0:
        return (
            "use",
            "Use for similar work",
            "Local runs completed and proved provider/model route-contract resolution.",
        )
    if delegated_lanes > 0:
        return (
            "watch",
            "Watch live lane",
            "A delegated runtime lane is active; wait for proof before promoting this route.",
        )
    return (
        "needs_evidence",
        "Needs more proof",
        "The route has local traces, but not enough completion and route-contract proof yet.",
    )


def _route_decision_fit(row: dict) -> tuple[str, str]:
    decision = str(row.get("decision", "needs_evidence"))
    harness_id = str(row.get("harnessId", "unknown_harness"))
    if decision == "use":
        return (
            "High confidence",
            f"{harness_id} has local completion and route-contract proof for this lane.",
        )
    if decision == "watch":
        return (
            "Live proof pending",
            f"{harness_id} is running this lane now; wait for verifier output before promoting it.",
        )
    if decision == "avoid_for_now":
        return (
            "Avoid for now",
            f"{harness_id} has more blocked or failed evidence than useful proof for this lane.",
        )
    return (
        "Needs proof",
        f"{harness_id} needs a completed local proof run before this route becomes a default.",
    )


def _benchmark_work_class(route_tier: str, safe_redteam: dict) -> str:
    tier = str(route_tier or "").strip().upper()
    if safe_redteam.get("applicable"):
        return "controlled_red_team_lab"
    if tier in {"F6", "F7", "F8"}:
        return "hard_or_frontier_mission"
    if tier in {"F4", "F5"}:
        return "normal_repo_execution"
    if tier in {"F0", "F1", "F2", "F3"}:
        return "cheap_or_deterministic_work"
    return "unclassified_route"


def _route_tier_value(route_tier: str) -> int:
    tier = str(route_tier or "").strip().upper()
    if tier.startswith("F"):
        tier = tier[1:]
    try:
        return int(tier)
    except ValueError:
        return -1


def _route_decision_summary(
    *,
    local_route_decision_rows: list[dict],
    benchmark_route_rows: list[dict],
    route_decision_rows: list[dict],
) -> dict:
    local_count = len(local_route_decision_rows)
    benchmark_count = len(benchmark_route_rows)
    all_rows = [*local_route_decision_rows, *benchmark_route_rows]
    shown_rows = list(route_decision_rows)
    highest_tier_row = max(
        all_rows or shown_rows,
        key=lambda item: _route_tier_value(str(item.get("routeTier", "") or "")),
        default={},
    )
    recommended_rows = [
        item
        for item in all_rows
        if item.get("decision") == "use" or "recommended" in str(item.get("label", "")).lower()
    ]
    return {
        "localCount": local_count,
        "benchmarkCount": benchmark_count,
        "totalShown": len(shown_rows),
        "candidateCount": len(all_rows),
        "benchmarkShownCount": sum(1 for item in shown_rows if item.get("benchmarkCandidate")),
        "recommendedCount": len(recommended_rows),
        "proofGapCount": sum(1 for item in all_rows if item.get("proofGaps")),
        "localProofRequiredCount": sum(1 for item in all_rows if item.get("localProofRequired")),
        "redTeamCandidateCount": sum(1 for item in all_rows if item.get("redTeamApplicable")),
        "highestRouteTier": str(highest_tier_row.get("routeTier", "") or "F0"),
        "highestRouteLabel": str(
            highest_tier_row.get("fitLabel")
            or highest_tier_row.get("label")
            or "No benchmark route"
        ),
        "highestRouteWorkClass": str(highest_tier_row.get("workClass", "") or "unclassified_route"),
        "highestRouteCostBand": str(highest_tier_row.get("costBand", "") or "unknown"),
        "highestRouteWallTimeBand": str(highest_tier_row.get("expectedWallTimeBand", "") or "unknown"),
        "highestRouteProvider": str(highest_tier_row.get("provider", "") or ""),
        "highestRouteModel": str(highest_tier_row.get("model", "") or ""),
        "needsLocalProof": any(item.get("localProofRequired") for item in all_rows),
    }


def _latest_runtime_lane_proof(root: Path) -> dict | None:
    artifact_root = root / "artifacts" / "runtime-lanes"
    if not artifact_root.exists():
        return None
    proof_paths = sorted(
        artifact_root.glob("*/runtime_lane_proof.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not proof_paths:
        return None
    proof_path = proof_paths[0]
    payload = _load_json_file(proof_path)
    if not isinstance(payload, dict):
        return None
    lanes = []
    for lane in payload.get("lanes", []):
        if not isinstance(lane, dict):
            continue
        route = lane.get("routeContract", {})
        if not isinstance(route, dict):
            route = {}
        readiness = lane.get("readiness", {})
        if not isinstance(readiness, dict):
            readiness = {}
        lanes.append(
            {
                "runtimeId": str(lane.get("runtimeId") or ""),
                "label": str(lane.get("label") or lane.get("runtimeId") or ""),
                "skill": str(lane.get("skill") or ""),
                "provider": str(route.get("provider") or ""),
                "model": str(route.get("model") or ""),
                "routeSummary": str(lane.get("routeSummary") or ""),
                "launchCommand": str(lane.get("launchCommand") or ""),
                "proofMeaning": str(lane.get("proofMeaning") or ""),
                "readiness": readiness,
            }
        )
    artifact_paths = payload.get("artifactPaths", {})
    if not isinstance(artifact_paths, dict):
        artifact_paths = {}
    artifact_statuses = []
    present_artifact_names: set[str] = set()
    tracked_artifact_names: set[str] = set()
    for key, value in artifact_paths.items():
        if not isinstance(key, str) or not isinstance(value, str) or not value.strip():
            continue
        artifact_path = Path(value)
        exists = artifact_path.exists()
        tracked_artifact_names.add(artifact_path.name)
        if exists:
            present_artifact_names.add(artifact_path.name)
        artifact_statuses.append(
            {
                "key": key,
                "path": str(value),
                "name": artifact_path.name,
                "exists": exists,
                "requiredByGate": False,
            }
        )
    safety_contract = payload.get("safetyContract", {})
    if not isinstance(safety_contract, dict):
        safety_contract = {}
    fused_runtime = payload.get("fusedRuntime", {})
    if not isinstance(fused_runtime, dict):
        fused_runtime = {}
    readiness_summary = fused_runtime.get("readinessSummary", payload.get("readinessSummary", {}))
    if not isinstance(readiness_summary, dict):
        readiness_summary = {}
    gate_required_artifacts: set[str] = set()
    for lane in payload.get("lanes", []):
        if not isinstance(lane, dict):
            continue
        readiness = lane.get("readiness", {})
        if not isinstance(readiness, dict):
            continue
        for gate in readiness.get("gates", []):
            if not isinstance(gate, dict):
                continue
            artifact_name = str(gate.get("proofArtifact") or "").strip()
            if artifact_name:
                gate_required_artifacts.add(artifact_name)
    for item in artifact_statuses:
        item["requiredByGate"] = item["name"] in gate_required_artifacts
    missing_artifacts = sorted((tracked_artifact_names | gate_required_artifacts) - present_artifact_names)
    missing_gate_artifacts = sorted(gate_required_artifacts - present_artifact_names)
    run_id = str(payload.get("runId") or proof_path.parent.name)
    return {
        "runId": run_id,
        "mode": str(payload.get("mode") or ""),
        "proofType": str(payload.get("proofType") or safety_contract.get("proofType") or ""),
        "proofTruth": payload.get("proofTruth") if isinstance(payload.get("proofTruth"), dict) else {},
        "createdAt": str(payload.get("createdAt") or ""),
        "path": str(proof_path),
        "proofRunCommand": f"python scripts/runtime_lane_proof_harness.py --run-id {run_id}",
        "readinessSummary": readiness_summary,
        "lanes": lanes[:4],
        "artifactPaths": {
            key: str(value)
            for key, value in artifact_paths.items()
            if isinstance(key, str) and isinstance(value, str)
        },
        "artifactIntegrity": {
            "schemaVersion": "runtime-proof-artifact-integrity.v1",
            "presentCount": sum(1 for item in artifact_statuses if item["exists"]),
            "missingCount": len(missing_artifacts),
            "artifactComplete": len(missing_artifacts) == 0,
            "gateRequiredCount": len(gate_required_artifacts),
            "missingArtifacts": missing_artifacts,
            "missingGateArtifacts": missing_gate_artifacts,
            "artifacts": artifact_statuses,
        },
        "safetyContract": {
            "liveModelCalls": bool(safety_contract.get("liveModelCalls")),
            "realTargets": bool(safety_contract.get("realTargets")),
            "harmfulInstructions": bool(safety_contract.get("harmfulInstructions")),
            "runtimeAdapterAdded": bool(safety_contract.get("runtimeAdapterAdded")),
            "openCodeGoRuntimeAdded": bool(safety_contract.get("openCodeGoRuntimeAdded")),
            "liveRuntimeExecution": bool(safety_contract.get("liveRuntimeExecution")),
            "proofType": str(safety_contract.get("proofType") or payload.get("proofType") or ""),
        },
    }


def _runtime_proof_gate_summary(latest_proof: dict | None) -> dict:
    if not isinstance(latest_proof, dict) or not latest_proof:
        return {
            "schemaVersion": "runtime-proof-gate-summary.v1",
            "status": "missing",
            "promotionBlocked": True,
            "blockingGateCount": 0,
            "passedGateCount": 0,
            "liveValidationGateCount": 0,
            "uncheckedGateCount": 0,
            "proofRunCommand": "python scripts/runtime_lane_proof_harness.py",
            "requiredArtifacts": [
                "runtime_lane_proof.json",
                "RUNTIME_LANE_PROOF.md",
                "route_scorecard.json",
            ],
            "nextRecoveryActions": [
                "Run the deterministic runtime lane proof harness before promoting Hermes or OpenClaw lanes.",
            ],
        }
    readiness = latest_proof.get("readinessSummary", {})
    if not isinstance(readiness, dict):
        readiness = {}
    artifact_integrity = latest_proof.get("artifactIntegrity", {})
    if not isinstance(artifact_integrity, dict):
        artifact_integrity = {}
    missing_artifact_count = int(artifact_integrity.get("missingCount") or 0)
    readiness_promotion_blocked = bool(readiness.get("promotionBlocked", True))
    promotion_blocked = readiness_promotion_blocked or missing_artifact_count > 0
    readiness_status = str(readiness.get("overallStatus") or "contract_ready_live_unverified")
    status = (
        "artifact_incomplete"
        if missing_artifact_count > 0 and not readiness_promotion_blocked
        else readiness_status
    )
    gates: list[dict] = []
    next_actions: list[str] = []
    for lane in latest_proof.get("lanes", []):
        if not isinstance(lane, dict):
            continue
        lane_readiness = lane.get("readiness", {})
        if not isinstance(lane_readiness, dict):
            continue
        action = str(lane_readiness.get("nextRecoveryAction") or "").strip()
        if action:
            next_actions.append(action)
        for gate in lane_readiness.get("gates", []):
            if isinstance(gate, dict):
                gates.append(gate)
                gate_action = str(gate.get("recoveryAction") or "").strip()
                if gate_action and gate.get("blocksPromotion"):
                    next_actions.append(gate_action)
    required_artifacts = sorted(
        {
            Path(str(value)).name
            for value in latest_proof.get("artifactPaths", {}).values()
            if str(value).strip()
        }
        | {
            str(gate.get("proofArtifact") or "").strip()
            for gate in gates
            if str(gate.get("proofArtifact") or "").strip()
        }
    )
    if not next_actions:
        next_actions.append("Review the latest runtime lane proof before assigning live work.")
    if missing_artifact_count > 0:
        next_actions.insert(
            0,
            "Rerun the deterministic runtime lane proof harness or restore missing proof artifacts before promotion.",
        )
    return {
        "schemaVersion": "runtime-proof-gate-summary.v1",
        "status": status,
        "promotionBlocked": promotion_blocked,
        "blockingGateCount": int(
            readiness.get("blockingGateCount", 0)
            or sum(1 for gate in gates if gate.get("blocksPromotion"))
        )
        + (1 if missing_artifact_count > 0 else 0),
        "passedGateCount": sum(1 for gate in gates if str(gate.get("status")) == "passed"),
        "liveValidationGateCount": sum(
            1 for gate in gates if str(gate.get("status")) == "needs_live_validation"
        ),
        "uncheckedGateCount": sum(1 for gate in gates if str(gate.get("status")) == "unchecked"),
        "presentArtifactCount": int(artifact_integrity.get("presentCount") or 0),
        "missingArtifactCount": missing_artifact_count,
        "artifactComplete": missing_artifact_count == 0,
        "missingArtifacts": [
            str(item)
            for item in artifact_integrity.get("missingArtifacts", [])
            if str(item).strip()
        ],
        "missingGateArtifacts": [
            str(item)
            for item in artifact_integrity.get("missingGateArtifacts", [])
            if str(item).strip()
        ],
        "proofRunCommand": str(
            latest_proof.get("proofRunCommand")
            or f"python scripts/runtime_lane_proof_harness.py --run-id {latest_proof.get('runId', 'runtime-lane-proof')}"
        ),
        "proofPath": str(latest_proof.get("path") or ""),
        "requiredArtifacts": required_artifacts,
        "nextRecoveryActions": list(dict.fromkeys(next_actions))[:4],
    }


def _benchmark_scorecard_fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "benchmark-board"
        / "fixtures"
        / "jbheaven_route_scorecard.fixture.json"
    )


def _benchmark_scorecard_paths(root: Path) -> list[tuple[Path, str]]:
    paths: list[tuple[Path, str]] = []
    fixture_path = _benchmark_scorecard_fixture_path()
    if fixture_path.exists():
        paths.append((fixture_path, "benchmark_fixture"))
    redteam_artifact_root = root / "artifacts" / "red-team"
    if redteam_artifact_root.exists():
        redteam_artifact_paths = sorted(
            redteam_artifact_root.glob("*/route_scorecard.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        paths.extend(
            (path, "redteam_artifact")
            for path in redteam_artifact_paths[:BENCHMARK_SCORECARD_ARTIFACT_LIMIT]
        )
    artifact_root = root / "artifacts" / "runtime-lanes"
    if artifact_root.exists():
        artifact_paths = sorted(
            artifact_root.glob("*/route_scorecard.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        paths.extend(
            (path, "benchmark_artifact")
            for path in artifact_paths[:BENCHMARK_SCORECARD_ARTIFACT_LIMIT]
        )
    return paths


def _benchmark_route_row_from_candidate(
    *,
    board: dict,
    candidate: dict,
    source: str,
    path: Path,
) -> dict | None:
    provider_route = candidate.get("providerRoute", {})
    runtime_lane = candidate.get("runtimeLane", {})
    decision = candidate.get("decision", {})
    verifier_proof = candidate.get("verifierProof", {})
    speed_cost = candidate.get("speedCostContext", {})
    safe_redteam = candidate.get("safeRedTeam", {})
    if not all(
        isinstance(item, dict)
        for item in (provider_route, runtime_lane, decision, verifier_proof)
    ):
        return None
    candidate_id = str(candidate.get("candidateId", "") or "").strip()
    if not candidate_id:
        return None
    provider = str(provider_route.get("provider", "") or "").strip().lower()
    runtime_id = str(runtime_lane.get("laneId", "") or "").strip()
    if not provider or not runtime_id:
        return None
    route_tier = str(decision.get("routeTier", "") or "F0")
    recommended = bool(decision.get("recommended"))
    use_when = decision.get("useWhen", [])
    do_not_use_when = decision.get("doNotUseWhen", [])
    if not isinstance(use_when, list):
        use_when = []
    if not isinstance(do_not_use_when, list):
        do_not_use_when = []
    proof_artifacts = verifier_proof.get("proofArtifacts", [])
    if not isinstance(proof_artifacts, list):
        proof_artifacts = []
    if source == "benchmark_artifact":
        source_label = "Generated benchmark artifact"
    elif source == "redteam_artifact":
        source_label = "JBH-EAVEN safe red-team artifact"
    else:
        source_label = "JBHEAVEN benchmark fixture"
    redteam_applicable = bool(safe_redteam.get("applicable"))
    benchmark_decision = (
        "use" if recommended else "watch" if redteam_applicable else "needs_evidence"
    )
    recommendation = str(provider_route.get("routeReason", "") or "").strip()
    if not recommendation:
        use_when = decision.get("useWhen", [])
        recommendation = str(use_when[0]) if isinstance(use_when, list) and use_when else (
            "Benchmark candidate loaded from route scorecard metadata."
        )
    return {
        "id": f"benchmark::{board.get('boardId', 'scorecard')}::{candidate_id}",
        "source": source,
        "sourceLabel": source_label,
        "sourcePath": str(path),
        "benchmarkCandidate": True,
        "benchmarkBoardId": board.get("boardId", ""),
        "benchmarkUpdatedAt": board.get("updatedAt", ""),
        "candidateId": candidate_id,
        "harnessId": str(candidate.get("harnessId", "") or "fluxio_hybrid"),
        "runtimeId": runtime_id,
        "provider": provider,
        "model": str(provider_route.get("model", "") or candidate.get("modelId", "") or "profile default"),
        "role": str(provider_route.get("role", "") or "mission"),
        "observedRuns": 0,
        "completedRuns": 0,
        "blockedRuns": 0,
        "delegatedLaneCount": 1 if runtime_lane.get("handoffMode") == "delegated" else 0,
        "routeContractProofCount": 0,
        "verificationFailures": 0,
        "completionRate": 0,
        "decision": benchmark_decision,
        "label": "Benchmark recommended" if recommended else "Benchmark candidate",
        "recommendation": recommendation,
        "fitLabel": f"Benchmark {route_tier}",
        "fitReason": str(
            verifier_proof.get("acceptanceGate", "")
            or "Run local proof before promoting this route."
        ),
        "outcomeScorecard": {
            "successRate": 0,
            "humanInterventionCount": 1 if verifier_proof.get("independence") == "human_review" else 0,
            "totalTokens": 0,
            "wallTimeSeconds": 0,
            "retryCount": int(speed_cost.get("retryBudget", 0) or 0),
            "latestTestResult": "benchmark",
            "proofArtifactCompleteness": 0,
            "proofArtifactCount": 0,
            "proofArtifactRequiredCount": len(proof_artifacts),
        },
        "speedCostContext": speed_cost if isinstance(speed_cost, dict) else {},
        "safeRedTeam": safe_redteam if isinstance(safe_redteam, dict) else {},
        "routeTier": route_tier,
        "workClass": _benchmark_work_class(route_tier, safe_redteam if isinstance(safe_redteam, dict) else {}),
        "useWhen": [str(item) for item in use_when[:3]],
        "doNotUseWhen": [str(item) for item in do_not_use_when[:3]],
        "redTeamApplicable": redteam_applicable,
        "redTeamScope": str(safe_redteam.get("scope", "not_applicable") or "not_applicable"),
        "escalationRequired": bool(safe_redteam.get("escalationRequired")),
        "expectedWallTimeBand": str(speed_cost.get("expectedWallTimeBand", "unknown") or "unknown"),
        "costBand": str(speed_cost.get("costBand", "unknown") or "unknown"),
        "contextWindowTokens": int(speed_cost.get("contextWindowTokens", 0) or 0),
        "localProofRequired": True,
        "proofGaps": ["Benchmark candidate needs a local proof run before default promotion."],
    }


def _load_benchmark_route_decision_rows(root: Path) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for path, source in _benchmark_scorecard_paths(root):
        board = _load_json_file(path)
        if not isinstance(board, dict):
            continue
        if board.get("schemaVersion") != BENCHMARK_SCORECARD_SCHEMA_VERSION:
            continue
        candidates = board.get("candidates", [])
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            row = _benchmark_route_row_from_candidate(
                board=board,
                candidate=candidate,
                source=source,
                path=path,
            )
            if not row or row["id"] in seen:
                continue
            rows.append(row)
            seen.add(row["id"])
    return rows[:6]


def _latest_test_result(verification_results: list[dict]) -> str:
    if not verification_results:
        return "missing"
    statuses = {
        str(item.get("status", "") or "").lower()
        for item in verification_results
        if isinstance(item, dict)
    }
    return_codes = [
        int(item.get("return_code", 1) or 0)
        for item in verification_results
        if isinstance(item, dict)
    ]
    if "timeout" in statuses or 124 in return_codes:
        return "timed_out"
    if any(return_code != 0 for return_code in return_codes):
        return "failed"
    return "passed"


def _proof_artifact_score(run: dict) -> tuple[int, int]:
    artifact_count = 0
    if run.get("routeContractResolved"):
        artifact_count += 1
    if int(run.get("verificationResultCount", 0) or 0) > 0:
        artifact_count += 1
    if int(run.get("artifactCount", 0) or 0) + int(run.get("handoffCount", 0) or 0) > 0:
        artifact_count += 1
    return artifact_count, 3


def _local_route_tier(row: dict) -> str:
    role = str(row.get("role", "") or "").lower()
    runtime_id = str(row.get("runtimeId", "") or "").lower()
    if "red" in role or "redteam" in role:
        return "F7"
    if row.get("decision") == "use":
        return "F5" if int(row.get("delegatedLaneCount", 0) or 0) > 0 else "F4"
    if row.get("decision") == "watch":
        return "F5"
    if runtime_id in {"hermes", "openclaw"}:
        return "F4"
    return "F3"


def _build_run_outcome_scorecard(payload: dict, metadata: dict | None) -> dict:
    state = payload.get("state", {}) if isinstance(payload.get("state"), dict) else {}
    context = payload.get("context", {}) if isinstance(payload.get("context"), dict) else {}
    verification_results = payload.get("verification_results", [])
    if not isinstance(verification_results, list):
        verification_results = []
    code_execution = payload.get("code_execution", {})
    if not isinstance(code_execution, dict):
        code_execution = payload.get("code_execution_state", {})
    if not isinstance(code_execution, dict):
        code_execution = {}
    artifacts = code_execution.get("artifacts", [])
    if not isinstance(artifacts, list):
        artifacts = []
    handoff_packets = payload.get("handoff_packets", [])
    if not isinstance(handoff_packets, list):
        handoff_packets = []
    blocker_retry_counts = payload.get("blocker_retry_counts", {})
    if not isinstance(blocker_retry_counts, dict):
        blocker_retry_counts = {}

    verification_duration_ms = sum(
        int(item.get("duration_ms", 0) or 0)
        for item in verification_results
        if isinstance(item, dict)
    )
    metadata_payload = metadata if isinstance(metadata, dict) else {}
    created_at = (
        _parse_iso_datetime(str(metadata_payload.get("created_at", "") or ""))
        or _parse_iso_datetime(str(payload.get("created_at", "") or ""))
    )
    updated_at = _parse_iso_datetime(str(payload.get("updated_at", "") or ""))
    wall_time_seconds = int(state.get("elapsed_runtime_seconds", 0) or 0)
    if wall_time_seconds <= 0 and created_at and updated_at:
        wall_time_seconds = max(0, int((updated_at - created_at).total_seconds()))
    if wall_time_seconds <= 0:
        wall_time_seconds = int(round(verification_duration_ms / 1000))

    return {
        "totalTokens": int(
            context.get("used_tokens", 0)
            or state.get("context_used_tokens", 0)
            or 0
        ),
        "wallTimeSeconds": wall_time_seconds,
        "retryCount": sum(int(value or 0) for value in blocker_retry_counts.values()),
        "latestTestResult": _latest_test_result(verification_results),
        "verificationResultCount": len(verification_results),
        "artifactCount": len(artifacts),
        "handoffCount": len(handoff_packets),
        "humanInterventionCount": len(
            state.get("approval_history", [])
            if isinstance(state.get("approval_history"), list)
            else []
        )
        + (
            1
            if str(payload.get("autopilot_pause_reason", "")) == "approval_required"
            else 0
        ),
    }


def _build_route_decision_rows(root: Path, recent_runs: list[dict]) -> list[dict]:
    rows: dict[str, dict] = {}

    def ensure_row(harness_id: str, runtime_id: str, provider: str, model: str, role: str) -> dict:
        clean_harness = harness_id or "unknown_harness"
        clean_runtime = runtime_id or "runtime"
        clean_provider = provider or "unresolved"
        clean_model = model or "profile default"
        clean_role = role or "mission"
        key = f"{clean_harness}::{clean_runtime}::{clean_provider}::{clean_model}::{clean_role}"
        return rows.setdefault(
            key,
            {
                "id": key,
                "sourceKind": "local",
                "sourceLabel": "Local Fluxio runs",
                "benchmarkCandidate": False,
                "harnessId": clean_harness,
                "runtimeId": clean_runtime,
                "provider": clean_provider,
                "model": clean_model,
                "role": clean_role,
                "observedRuns": 0,
                "completedRuns": 0,
                "blockedRuns": 0,
                "delegatedLaneCount": 0,
                "routeContractProofCount": 0,
                "verificationFailures": 0,
                "totalTokens": 0,
                "wallTimeSeconds": 0,
                "retryCount": 0,
                "humanInterventionCount": 0,
                "proofArtifactCount": 0,
                "proofArtifactRequiredCount": 0,
                "latestTestResult": "missing",
                "proofGaps": [],
            },
        )

    for run in recent_runs:
        row = ensure_row(
            str(run.get("harnessId", "") or "").strip(),
            str(run.get("runtimeId", "") or "").strip(),
            str(run.get("routeProvider", "") or "").strip().lower(),
            str(run.get("routeModel", "") or "").strip(),
            str(run.get("routeRole", "") or "").strip(),
        )
        row["observedRuns"] += 1
        if str(run.get("autopilotStatus", "")) == "completed":
            row["completedRuns"] += 1
        if str(run.get("pauseReason", "")) in {
            "approval_required",
            "verification_failed",
            "delegated_runtime_running",
            "runtime_budget",
        } or str(run.get("autopilotStatus", "")) in {"failed", "blocked"}:
            row["blockedRuns"] += 1
        row["delegatedLaneCount"] += int(run.get("delegatedSessionCount", 0) or 0)
        row["routeContractProofCount"] += 1 if run.get("routeContractResolved") else 0
        row["verificationFailures"] += int(run.get("verificationFailures", 0) or 0)
        scorecard = run.get("outcomeScorecard", {}) if isinstance(run.get("outcomeScorecard"), dict) else {}
        row["totalTokens"] += int(scorecard.get("totalTokens", 0) or 0)
        row["wallTimeSeconds"] += int(scorecard.get("wallTimeSeconds", 0) or 0)
        row["retryCount"] += int(scorecard.get("retryCount", 0) or 0)
        row["humanInterventionCount"] += int(scorecard.get("humanInterventionCount", 0) or 0)
        proof_count, proof_required = _proof_artifact_score(
            {
                **run,
                "verificationResultCount": scorecard.get("verificationResultCount", 0),
                "artifactCount": scorecard.get("artifactCount", 0),
                "handoffCount": scorecard.get("handoffCount", 0),
            }
        )
        row["proofArtifactCount"] += proof_count
        row["proofArtifactRequiredCount"] += proof_required
        if row["latestTestResult"] == "missing":
            row["latestTestResult"] = str(scorecard.get("latestTestResult", "missing") or "missing")

    runtime_root = root / ".agent_control" / "runtime_sessions"
    if runtime_root.exists():
        for path in runtime_root.glob("delegate_*.json"):
            payload = _load_json_file(path)
            if not isinstance(payload, dict):
                continue
            row = ensure_row(
                str(payload.get("harness_id", "") or "delegated_runtime_lane").strip(),
                str(payload.get("runtime_id", "") or "").strip(),
                str(payload.get("target_provider", "") or "").strip().lower(),
                str(payload.get("target_model", "") or "").strip(),
                str(payload.get("target_phase", "") or "").strip(),
            )
            row["delegatedLaneCount"] += 1
            if str(payload.get("status", "")).lower() in {"waiting_for_approval", "blocked", "failed"}:
                row["blockedRuns"] += 1
            if not str(payload.get("target_provider", "") or "").strip():
                row["proofGaps"].append("Provider route missing from delegated session.")
            if not str(payload.get("target_model", "") or "").strip():
                row["proofGaps"].append("Model route missing from delegated session.")

    decision_rows = []
    for row in rows.values():
        if int(row["routeContractProofCount"]) == 0:
            row["proofGaps"].append("No route-contract proof recorded.")
        if int(row["completedRuns"]) == 0:
            row["proofGaps"].append("No completed local run recorded.")
        decision, label, recommendation = _route_decision_recommendation(row)
        row["decision"] = decision
        row["label"] = label
        row["recommendation"] = recommendation
        fit_label, fit_reason = _route_decision_fit(row)
        row["fitLabel"] = fit_label
        row["fitReason"] = fit_reason
        row["completionRate"] = _percent(int(row["completedRuns"]), int(row["observedRuns"]))
        row["outcomeScorecard"] = {
            "successRate": _percent(int(row["completedRuns"]), int(row["observedRuns"])),
            "humanInterventionCount": int(row.pop("humanInterventionCount", 0) or 0),
            "totalTokens": int(row.pop("totalTokens", 0) or 0),
            "wallTimeSeconds": int(row.pop("wallTimeSeconds", 0) or 0),
            "retryCount": int(row.pop("retryCount", 0) or 0),
            "latestTestResult": str(row.pop("latestTestResult", "missing") or "missing"),
            "proofArtifactCompleteness": _percent(
                int(row.get("proofArtifactCount", 0) or 0),
                int(row.get("proofArtifactRequiredCount", 0) or 0),
            ),
            "proofArtifactCount": int(row.pop("proofArtifactCount", 0) or 0),
            "proofArtifactRequiredCount": int(row.pop("proofArtifactRequiredCount", 0) or 0),
        }
        row["routeTier"] = _local_route_tier(row)
        row["workClass"] = (
            "controlled_red_team_lab"
            if "red" in str(row.get("role", "") or "").lower()
            else "normal_repo_execution"
            if row["decision"] == "use"
            else "local_route_needs_evidence"
        )
        row["expectedWallTimeBand"] = (
            "sub_10m"
            if int(row["outcomeScorecard"]["wallTimeSeconds"] or 0) and int(row["outcomeScorecard"]["wallTimeSeconds"] or 0) < 600
            else "10_60m"
            if int(row["outcomeScorecard"]["wallTimeSeconds"] or 0) < 3600
            else "unknown"
        )
        row["costBand"] = "observed"
        row["localProofRequired"] = row["decision"] != "use"
        row["redTeamApplicable"] = False
        row["redTeamScope"] = "not_applicable"
        row["proofGaps"] = sorted(set(row["proofGaps"]))[:3]
        decision_rows.append(row)

    return sorted(
        decision_rows,
        key=lambda item: (
            {"use": 0, "watch": 1, "needs_evidence": 2, "avoid_for_now": 3}.get(
                item["decision"],
                4,
            ),
            -int(item["observedRuns"]),
            -int(item["delegatedLaneCount"]),
            item["harnessId"],
            item["runtimeId"],
        ),
    )[:6]


def _fused_runtime_status(
    *,
    root: Path,
    recent_runs: list[dict],
    harness_counts: dict[str, int],
    route_contract_run_count: int,
    delegated_run_count: int,
    session_health: dict,
) -> dict:
    total_runs = len(recent_runs)
    fluxio_run_count = int(harness_counts.get("fluxio_hybrid", 0) or 0)
    stale_heartbeat_count = int(session_health.get("staleHeartbeatCount", 0) or 0)
    active_count = int(session_health.get("activeCount", 0) or 0)
    waiting_approval_count = int(session_health.get("waitingApprovalCount", 0) or 0)

    if total_runs == 0:
        status = "unproven"
        summary = "No local Fluxio harness runs are recorded yet."
    elif stale_heartbeat_count > 0:
        status = "attention_needed"
        summary = "Fused runtime has recent evidence, but delegated heartbeat health needs attention."
    elif fluxio_run_count == 0:
        status = "legacy_only"
        summary = "Recent runs only prove the legacy compatibility harness, not Fluxio hybrid."
    elif delegated_run_count == 0 or route_contract_run_count == 0:
        status = "partial"
        summary = "Fluxio hybrid has local runs, but delegated lane or route-contract proof is incomplete."
    else:
        status = "operational"
        summary = "Fluxio hybrid has local proof across mission loop, route contracts, and delegated lanes."

    lane_counts = _observed_runtime_lane_counts(root, recent_runs)
    lane_labels = {
        "openclaw": "OpenClaw",
        "hermes": "Hermes",
    }
    runtime_lanes = []
    executable_runtime_ids = {
        runtime_id for runtime_id in lane_counts if runtime_id != "opencode"
    }
    for runtime_id in sorted({*lane_labels.keys(), *executable_runtime_ids}):
        runtime_lanes.append(
            {
                "runtimeId": runtime_id,
                "label": lane_labels.get(runtime_id, runtime_id),
                "role": "executable_runtime_lane",
                "observedCount": lane_counts.get(runtime_id, 0),
                "active": lane_counts.get(runtime_id, 0) > 0,
            }
        )
    provider_counts = _observed_route_provider_counts(root, recent_runs)
    model_provider_routes = [
        {
            "provider": "openai",
            "label": "OpenAI",
            "role": "provider_model_route",
            "suggestedModel": "",
            "observedCount": provider_counts.get("openai", 0),
            "active": provider_counts.get("openai", 0) > 0,
        },
        {
            "provider": "minimax",
            "label": "MiniMax",
            "role": "provider_model_route",
            "suggestedModel": "",
            "observedCount": provider_counts.get("minimax", 0),
            "active": provider_counts.get("minimax", 0) > 0,
        },
    ]

    gaps: list[str] = []
    if total_runs == 0:
        gaps.append("Run one Fluxio hybrid mission to create local fused-runtime evidence.")
    if fluxio_run_count == 0 and total_runs > 0:
        gaps.append("Recent runs do not include the production fluxio_hybrid harness.")
    if delegated_run_count == 0:
        gaps.append("No recent delegated runtime lane is recorded.")
    if route_contract_run_count == 0:
        gaps.append("No recent run proves role/provider/model route-contract resolution.")
    if stale_heartbeat_count > 0:
        gaps.append(f"{stale_heartbeat_count} delegated runtime heartbeat(s) are stale.")

    latest_lane_proof = _latest_runtime_lane_proof(root)
    return {
        "schemaVersion": "fused-runtime-status.v1",
        "status": status,
        "summary": summary,
        "productionHarness": "fluxio_hybrid",
        "compatibilityHarnesses": ["legacy_autonomous_engine"],
        "supervisor": {
            "id": "delegated_runtime_supervisor",
            "activeSessionCount": active_count,
            "waitingApprovalCount": waiting_approval_count,
            "healthyHeartbeatCount": int(session_health.get("healthyHeartbeatCount", 0) or 0),
            "staleHeartbeatCount": stale_heartbeat_count,
            "latestHeartbeatAgeSeconds": session_health.get("latestHeartbeatAgeSeconds"),
        },
        "fusionPoints": [
            "mission_control_loop",
            "fluxio_hybrid_harness",
            "delegated_runtime_supervisor",
            "route_contracts",
            "approval_gate",
            "verification_results",
            "continuity_checkpoints",
        ],
        "runtimeLanes": runtime_lanes,
        "modelProviderRoutes": model_provider_routes,
        "proofSignals": {
            "recentRunCount": total_runs,
            "fluxioHybridRunCount": fluxio_run_count,
            "legacyCompatibilityRunCount": int(
                harness_counts.get("legacy_autonomous_engine", 0) or 0
            ),
            "delegatedRunCount": delegated_run_count,
            "routeContractRunCount": route_contract_run_count,
            "supervisorSessionCount": int(session_health.get("totalSessions", 0) or 0),
            "fusedRuntimeRole": "supervisor_not_runtime_adapter",
            "openCodeGoRole": "route_lane_only",
        },
        "latestLaneProof": latest_lane_proof,
        "proofGateSummary": _runtime_proof_gate_summary(latest_lane_proof),
        "gaps": gaps,
    }


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
    route_contract_run_count = 0
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
        has_route_contract = _route_contract_present(payload)
        route_provider = _route_provider_from_payload(payload)
        route_model = _route_model_from_payload(payload)
        route_role = _route_role_from_payload(payload)
        outcome_scorecard = _build_run_outcome_scorecard(
            payload,
            metadata if isinstance(metadata, dict) else {},
        )
        if has_route_contract:
            route_contract_run_count += 1
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
                "routeContractResolved": has_route_contract,
                "routeProvider": route_provider,
                "routeModel": route_model,
                "routeRole": route_role,
                "outcomeScorecard": outcome_scorecard,
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
    fused_runtime = _fused_runtime_status(
        root=root,
        recent_runs=recent_runs,
        harness_counts=harness_counts,
        route_contract_run_count=route_contract_run_count,
        delegated_run_count=delegated_run_count,
        session_health=session_health,
    )
    local_route_decision_rows = _build_route_decision_rows(root, recent_runs)
    benchmark_route_rows = _load_benchmark_route_decision_rows(root)
    route_row_ids = {item.get("id") for item in local_route_decision_rows}
    route_decision_rows = [
        *local_route_decision_rows,
        *[
            item
            for item in benchmark_route_rows
            if item.get("id") not in route_row_ids
        ],
    ][:6]
    return {
        "productionHarness": "fluxio_hybrid",
        "shadowCandidates": ["legacy_autonomous_engine"],
        "fusedRuntime": fused_runtime,
        "routeDecisionRows": route_decision_rows,
        "benchmarkRouteRows": benchmark_route_rows,
        "routeDecisionSummary": _route_decision_summary(
            local_route_decision_rows=local_route_decision_rows,
            benchmark_route_rows=benchmark_route_rows,
            route_decision_rows=route_decision_rows,
        ),
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
        "recommendation": recommendation,
    }
