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


def runtime_bin_candidates(workspace_root: Path) -> list[Path]:
    root = Path(workspace_root).expanduser()
    candidates = [
        root / "runtime" / "bin",
        root.parent / "runtime" / "bin",
        root.parent.parent / "runtime" / "bin",
    ]
    for parent in [root, *root.parents]:
        candidates.append(parent / "syntelos" / "runtime" / "bin")
    env_runtime_root = (
        os.environ.get("FLUXIO_RUNTIME_ROOT")
        or os.environ.get("SYNTELOS_RUNTIME_ROOT")
        or os.environ.get("SYNTHELOS_RUNTIME_ROOT")
    )
    if env_runtime_root:
        candidates.insert(0, Path(env_runtime_root).expanduser() / "bin")

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen or not candidate.exists():
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def runtime_lookup_path(workspace_root: Path) -> str:
    current_path = os.environ.get("PATH", "")
    prefixes = [str(item) for item in runtime_bin_candidates(workspace_root)]
    if not prefixes:
        return current_path
    return os.pathsep.join(prefixes + ([current_path] if current_path else []))


def runtime_subprocess_env(workspace_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    lookup_path = runtime_lookup_path(workspace_root)
    if lookup_path:
        env["PATH"] = lookup_path
    _apply_runtime_home_env(env, workspace_root)
    return env


def _apply_runtime_home_env(env: dict[str, str], workspace_root: Path) -> None:
    for runtime_bin in runtime_bin_candidates(workspace_root):
        runtime_root = runtime_bin.parent
        runtime_home = runtime_root / "home"
        if not runtime_home.exists():
            continue
        current_home = str(env.get("HOME", "") or "").strip()
        if not current_home or not Path(current_home).expanduser().exists():
            env["HOME"] = str(runtime_home)
        hermes_home = runtime_home / ".hermes"
        if hermes_home.exists():
            current_hermes_home = str(env.get("HERMES_HOME", "") or "").strip()
            if not current_hermes_home or not Path(current_hermes_home).expanduser().exists():
                env["HERMES_HOME"] = str(hermes_home)
        provider_env = runtime_home / ".fluxio_provider_env"
        if provider_env.exists():
            for raw_line in provider_env.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                if key:
                    env[key] = value.strip().strip("\"'")
        return


def runtime_which(command_name: str, workspace_root: Path) -> str | None:
    runtime_candidates = runtime_bin_candidates(workspace_root)
    direct = _direct_runtime_command(command_name, runtime_candidates)
    if direct:
        return direct
    runtime_bins = [str(item) for item in runtime_candidates]
    if runtime_bins:
        current_path = os.environ.get("PATH", "")
        lookup_path = os.pathsep.join(runtime_bins + ([current_path] if current_path else []))
        return shutil_which(command_name, lookup_path)
    return shutil_which(command_name, None)


def _direct_runtime_command(command_name: str, runtime_bins: list[Path]) -> str | None:
    suffixes = ["", ".cmd", ".bat", ".exe"] if os.name == "nt" else [""]
    for runtime_bin in runtime_bins:
        for suffix in suffixes:
            candidate = runtime_bin / f"{command_name}{suffix}"
            if candidate.exists() and candidate.is_file():
                return str(candidate)
    return None


def shutil_which(command_name: str, lookup_path: str | None) -> str | None:
    import shutil

    if lookup_path:
        return shutil.which(command_name, path=lookup_path)
    return shutil.which(command_name)


def shell_with_runtime_path(command: str, workspace_root: Path) -> str:
    if not runtime_bin_candidates(workspace_root):
        return command
    lookup_path = runtime_lookup_path(workspace_root)
    if not lookup_path:
        return command
    if os.name == "nt":
        return f'set "PATH={lookup_path}" && {command}'
    return f"PATH={shlex.quote(lookup_path)}; export PATH; {command}"


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


def route_role_for_phase(phase: str) -> str:
    normalized = PHASE_ALIASES.get(str(phase or "execute").strip().lower(), "execute")
    if normalized in {"plan", "replan"}:
        return "planner"
    if normalized == "verify":
        return "verifier"
    return "executor"


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
