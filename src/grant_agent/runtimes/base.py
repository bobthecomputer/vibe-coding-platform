from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import Mission, RuntimeCapability, RuntimeInstallStatus, WorkspaceProfile


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
