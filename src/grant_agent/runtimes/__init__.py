from __future__ import annotations

from pathlib import Path

from ..models import RuntimeInstallStatus
from .base import AgentRuntimeAdapter
from .hermes import HermesRuntimeAdapter
from .openclaw import OpenClawRuntimeAdapter


def runtime_adapters() -> list[AgentRuntimeAdapter]:
    return [OpenClawRuntimeAdapter(), HermesRuntimeAdapter()]


def runtime_adapter_map() -> dict[str, AgentRuntimeAdapter]:
    return {adapter.runtime_id: adapter for adapter in runtime_adapters()}


def detect_runtime_statuses(workspace_root: Path) -> list[RuntimeInstallStatus]:
    return [adapter.doctor(workspace_root) for adapter in runtime_adapters()]
