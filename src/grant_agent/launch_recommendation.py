from __future__ import annotations

from typing import Any

TASK_RECOMMENDATIONS: list[dict[str, Any]] = [
    {
        "taskType": "frontend_design",
        "taskLabel": "Frontend/UI/design",
        "keywords": (
            "frontend",
            "front-end",
            "ui",
            "ux",
            "interface",
            "design",
            "react",
            "css",
            "website",
            "mobile",
            "tablet",
        ),
        "provider": "minimax",
        "model": "MiniMax-M3",
        "effort": "high",
        "reason": "UI and frontend work benefits from MiniMax as the execution model while Hermes keeps the mission durable.",
    },
    {
        "taskType": "hardware_electrical",
        "taskLabel": "Hardware/electrical engineering",
        "keywords": (
            "hardware",
            "electrical",
            "electronics",
            "pcb",
            "circuit",
            "sensor",
            "embedded",
            "microcontroller",
            "firmware",
            "simulation",
        ),
        "provider": "openai-codex",
        "model": "gpt-5.5",
        "effort": "high",
        "reason": "Hardware and electrical work needs stronger reasoning for constraints, units, and simulation artifacts.",
    },
    {
        "taskType": "data_f1_analytics",
        "taskLabel": "F1/data analytics",
        "keywords": (
            "f1",
            "formula 1",
            "formula one",
            "telemetry",
            "lap time",
            "racing",
            "analytics",
            "dashboard",
            "visualization",
        ),
        "provider": "openai-codex",
        "model": "gpt-5.5",
        "effort": "high",
        "reason": "F1 and analytics work stays on high-effort Codex until value-scored route trust proves an efficient route.",
    },
    {
        "taskType": "security_red_team",
        "taskLabel": "Security/red-team",
        "keywords": (
            "red team",
            "red-team",
            "defensive",
            "threat",
            "security",
            "vulnerability",
            "hardening",
            "attack surface",
        ),
        "provider": "openai-codex",
        "model": "gpt-5.5",
        "effort": "high",
        "reason": "Security and red-team work should use a premium model so difficulty can escalate with proof quality.",
    },
]

OPENCLAW_RUNTIME_KEYWORDS = (
    "openclaw",
    "openclaw proof",
    "openclaw parity",
    "compare openclaw",
    "test openclaw",
    "debug openclaw",
    "openclaw setup",
    "openclaw auth",
)
OPENCLAW_NEGATION_KEYWORDS = (
    "do not use openclaw",
    "do not relaunch through openclaw",
    "do not launch through openclaw",
    "don't use openclaw",
    "dont use openclaw",
    "avoid openclaw",
    "not openclaw",
    "no openclaw",
    "without openclaw",
 )
HERMES_RUNTIME_KEYWORDS = (
    "browser automation",
    "interactive",
    "oauth",
    "provider setup",
    "broker authentication",
    "terminal",
    "tool exploration",
    "mcp",
    "overnight",
    "hands-free",
    "hands free",
    "continue",
    "resume",
    "watchdog",
    "proof",
    "long",
    "mission",
    "hermes",
)


def _explicit_openclaw_requested(normalized_objective: str) -> bool:
    if any(keyword in normalized_objective for keyword in OPENCLAW_NEGATION_KEYWORDS):
        return False
    return any(keyword in normalized_objective for keyword in OPENCLAW_RUNTIME_KEYWORDS)


def infer_launch_task(objective: str) -> dict[str, Any]:
    normalized = f" {objective or ''} ".lower()
    best: dict[str, Any] | None = None
    best_matches: list[str] = []
    for item in TASK_RECOMMENDATIONS:
        matches = [keyword for keyword in item["keywords"] if keyword in normalized]
        if len(matches) > len(best_matches):
            best = item
            best_matches = matches
    if best is None:
        return {
            "taskType": "general_coding",
            "taskLabel": "General coding",
            "matchedKeywords": [],
            "provider": "openai-codex",
            "model": "gpt-5.5",
            "effort": "high",
            "reason": "No specialist task type was detected; keep planning, execution, and verification on high-effort Codex.",
        }
    return {
        "taskType": best["taskType"],
        "taskLabel": best["taskLabel"],
        "matchedKeywords": best_matches[:6],
        "provider": best["provider"],
        "model": best["model"],
        "effort": best.get("effort", "high"),
        "reason": best["reason"],
    }


def build_task_route_decision(task: dict[str, Any], runtime: str) -> list[dict[str, str]]:
    executor_provider = str(task.get("provider") or "openai-codex")
    executor_model = str(task.get("model") or "gpt-5.5")
    executor_effort = str(task.get("effort") or "high")
    return [
        {
            "role": "planner",
            "provider": "openai-codex",
            "model": "gpt-5.5",
            "effort": "high",
            "reason": "Codex 5.5 high decomposes the objective and chooses the route before dispatch.",
        },
        {
            "role": "executor",
            "provider": executor_provider,
            "model": executor_model,
            "effort": executor_effort,
            "reason": str(task.get("reason") or "Executor follows the task-fit route."),
        },
        {
            "role": "verifier",
            "provider": "openai-codex",
            "model": "gpt-5.5",
            "effort": "high",
            "reason": "Codex 5.5 high checks proof, diffs, browser output, and route receipts.",
        },
        {
            "role": "supervisor",
            "provider": runtime if runtime in {"hermes", "openclaw"} else "hermes",
            "model": "durable harness",
            "effort": "resume",
            "reason": "The harness owns mission continuity, approvals, watchdogs, and resumability.",
        },
    ]


def build_launch_runtime_recommendation(
    *,
    objective: str = "",
    workspace_default_runtime: str = "hermes",
    profile: str = "builder",
) -> dict[str, Any]:
    normalized = f" {objective or ''} ".lower()
    task = infer_launch_task(objective)
    runtime = (workspace_default_runtime or "hermes").strip().lower() or "hermes"
    runtime_reason = "Hermes is the default durable harness for supervised Fluxio missions."
    confidence = 55
    if any(keyword in normalized for keyword in HERMES_RUNTIME_KEYWORDS):
        runtime = "hermes"
        runtime_reason = "Hermes is better for durable supervised missions, provider setup, resume loops, and proof-heavy work."
        confidence = max(confidence, 78)
    explicit_openclaw = _explicit_openclaw_requested(normalized)
    if explicit_openclaw:
        runtime = "openclaw"
        runtime_reason = "OpenClaw was explicitly requested for this launch."
        confidence = max(confidence, 82)
    if not objective:
        confidence = 50
    guidance = [
        runtime_reason,
        task["reason"],
        "Leave runtime/model on Auto unless you need a specific provider for the mission.",
    ]
    return {
        "schema": "fluxio.launch_runtime_recommendation.v1",
        "runtime": runtime if runtime in {"hermes", "openclaw"} else "hermes",
        "confidence": confidence,
        "profile": profile or "builder",
        "taskType": task["taskType"],
        "taskLabel": task["taskLabel"],
        "matchedKeywords": task["matchedKeywords"],
        "modelProvider": task["provider"],
        "model": task["model"],
        "modelEffort": task.get("effort", "high"),
        "reason": runtime_reason,
        "modelReason": task["reason"],
        "routeDecisionRows": build_task_route_decision(task, runtime),
        "beginnerSummary": (
            f"Use {runtime.title() if runtime in {'hermes', 'openclaw'} else 'Hermes'} for this launch. "
            f"Planner and verifier stay on openai-codex / gpt-5.5 / high. "
            f"Recommended executor model: {task['provider']} / {task['model']} / {task.get('effort', 'high')}."
        ),
        "guidance": guidance,
    }
