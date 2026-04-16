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


def shell_join(args: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(args)
    return shlex.join(args)


def mission_executor_route(
    mission: Mission,
    preferred_roles: tuple[str, ...] = ("executor", "planner", "verifier"),
) -> dict[str, str]:
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
    for role in preferred_roles:
        match = next(
            (item for item in normalized_rows if item.get("role") == role),
            None,
        )
        if match is not None:
            return match
    return {
        "role": "",
        "provider": "",
        "model": "",
        "effort": "",
        "budget_class": "",
    }


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
