from __future__ import annotations

import os
import shlex
import subprocess
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path

from ..models import (
    Mission,
    ModelRouteConfig,
    RuntimeCapability,
    RuntimeInstallStatus,
    WorkspaceProfile,
)

PHASE_ROLE_PREFERENCES: dict[str, tuple[str, ...]] = {
    "plan": ("planner", "executor", "verifier"),
    "replan": ("planner", "verifier", "executor"),
    "execute": ("executor", "planner", "verifier"),
    "verify": ("verifier", "executor", "planner"),
}
PHASE_ALIASES = {
    "planning": "plan",
    "replanning": "replan",
    "execution": "execute",
    "executing": "execute",
    "verification": "verify",
    "verifying": "verify",
}


def shell_join(args: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(args)
    return shlex.join(args)


def _normalized_route_rows(mission: Mission) -> list[dict[str, str]]:
    route_configs = getattr(mission, "route_configs", None) or []
    normalized_rows: list[dict[str, str]] = []
    for item in route_configs:
        if isinstance(item, dict):
            row = dict(item)
        elif isinstance(item, ModelRouteConfig) or hasattr(item, "__dataclass_fields__"):
            row = asdict(item)
        else:
            continue
        role = str(row.get("role", "")).strip().lower()
        if not role:
            continue
        normalized_rows.append(
            {
                "role": role,
                "provider": str(row.get("provider", "")).strip().lower(),
                "model": str(row.get("model", "")).strip(),
                "effort": str(row.get("effort", "")).strip().lower(),
                "budget_class": str(
                    row.get("budget_class", row.get("budgetClass", ""))
                ).strip(),
            }
        )
    return normalized_rows


def mission_cycle_phase(
    mission: Mission,
    fallback_phase: str = "execute",
) -> str:
    state = getattr(mission, "state", None)
    explicit_phase = str(getattr(state, "current_cycle_phase", "") or "").strip().lower()
    normalized_phase = PHASE_ALIASES.get(explicit_phase, explicit_phase)
    if normalized_phase in PHASE_ROLE_PREFERENCES:
        return normalized_phase

    status = str(getattr(state, "status", "") or "").strip().lower()
    if status in {"draft", "queued"}:
        return "plan"
    if status == "verification_failed":
        return "replan"
    if status in {"completed", "verified"}:
        return "verify"
    return PHASE_ALIASES.get(fallback_phase, fallback_phase)


def mission_phase_route(
    mission: Mission,
    *,
    phase: str | None = None,
    preferred_roles: tuple[str, ...] | None = None,
) -> dict[str, str]:
    normalized_rows = _normalized_route_rows(mission)
    raw_phase = str(phase or mission_cycle_phase(mission)).strip().lower()
    phase_key = PHASE_ALIASES.get(raw_phase, raw_phase)
    default_roles = PHASE_ROLE_PREFERENCES.get(
        phase_key,
        PHASE_ROLE_PREFERENCES["execute"],
    )
    selected_roles = preferred_roles or default_roles
    for role in selected_roles:
        match = next(
            (item for item in normalized_rows if item.get("role") == role),
            None,
        )
        if match is not None:
            return {
                **match,
                "phase": phase_key,
                "phase_label": phase_key,
            }
    return {
        "role": "",
        "provider": "",
        "model": "",
        "effort": "",
        "budget_class": "",
        "phase": phase_key,
        "phase_label": phase_key,
    }


def mission_executor_route(
    mission: Mission,
    preferred_roles: tuple[str, ...] = ("executor", "planner", "verifier"),
) -> dict[str, str]:
    return mission_phase_route(
        mission,
        phase="execute",
        preferred_roles=preferred_roles,
    )


class AgentRuntimeAdapter(ABC):
    runtime_id: str
    label: str

    @abstractmethod
    def detect(self, workspace_root: Path) -> RuntimeInstallStatus:
        raise NotImplementedError

    @abstractmethod
    def install(self) -> dict[str, str]:
        raise NotImplementedError

    @abstractmethod
    def doctor(self, workspace_root: Path) -> RuntimeInstallStatus:
        raise NotImplementedError

    @abstractmethod
    def update(self, workspace_root: Path) -> dict[str, str]:
        raise NotImplementedError

    @abstractmethod
    def start_mission(
        self, mission: Mission, workspace: WorkspaceProfile
    ) -> dict[str, object]:
        raise NotImplementedError

    @abstractmethod
    def stream_events(self, mission: Mission) -> list[dict[str, object]]:
        raise NotImplementedError

    @abstractmethod
    def request_approval(self, mission: Mission, prompt: str) -> dict[str, object]:
        raise NotImplementedError

    @abstractmethod
    def resume_mission(self, mission: Mission, workspace: WorkspaceProfile) -> dict[str, object]:
        raise NotImplementedError

    @abstractmethod
    def stop_mission(self, mission: Mission) -> dict[str, object]:
        raise NotImplementedError

    def list_capabilities(self) -> list[RuntimeCapability]:
        return []
