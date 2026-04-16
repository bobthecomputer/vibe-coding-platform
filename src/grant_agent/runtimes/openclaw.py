from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import re
import shlex
from pathlib import Path

from ..models import Mission, RuntimeCapability, RuntimeInstallStatus, WorkspaceProfile
from ..runtime_updates import (
    compare_version_tokens,
    latest_openclaw_release,
    normalize_openclaw_version,
)
from .base import AgentRuntimeAdapter, mission_phase_route, shell_join

OPENCLAW_PROVIDER_MAP = {
    "openai": "openai-codex",
    "openai-codex": "openai-codex",
    "openrouter": "openrouter",
    "anthropic": "anthropic",
    "gemini": "gemini",
    "minimax": "minimax",
    "minimax-portal": "minimax-portal",
    "minimax-cn": "minimax",
    "huggingface": "huggingface",
    "zai": "zai",
    "kimi-coding": "kimi-coding",
    "kimi-coding-cn": "kimi-coding-cn",
    "xiaomi": "xiaomi",
    "arcee": "arcee",
}


class OpenClawRuntimeAdapter(AgentRuntimeAdapter):
    runtime_id = "openclaw"
    label = "OpenClaw"

    def list_capabilities(self) -> list[RuntimeCapability]:
        return [
            RuntimeCapability(
                key="remote_approvals",
                label="Remote approvals",
                available=True,
                detail="Messaging-first control plane with phone-friendly inbox patterns.",
            ),
            RuntimeCapability(
                key="skills",
                label="Managed skills",
                available=True,
                detail="Bundled, managed, and workspace skills are supported.",
            ),
            RuntimeCapability(
                key="multi_channel",
                label="Multi-channel routing",
                available=True,
                detail="Routes messages and approvals across Telegram and other channels.",
            ),
        ]

    def detect(self, workspace_root: Path) -> RuntimeInstallStatus:
        command = shutil.which("openclaw")
        version = None
        issues: list[str] = []
        if command:
            try:
                completed = subprocess.run(  # noqa: S603
                    [command, "--version"],
                    cwd=str(workspace_root),
                    capture_output=True,
                    text=True,
                    timeout=8,
                    check=False,
                )
                version = normalize_openclaw_version(
                    (completed.stdout or completed.stderr).strip() or None
                )
            except Exception as exc:  # pragma: no cover - defensive
                issues.append(f"Unable to read OpenClaw version: {exc}")
        else:
            issues.append("OpenClaw CLI was not found on PATH.")

        latest_release = latest_openclaw_release()
        latest_version = latest_release.get("version") or None
        update_available = bool(
            command and version and latest_version and compare_version_tokens(version, latest_version) < 0
        )
        if update_available and latest_version:
            issues.append(f"OpenClaw is behind the latest npm release ({latest_version}).")

        return RuntimeInstallStatus(
            runtime_id=self.runtime_id,
            label=self.label,
            detected=command is not None,
            command=command,
            version=version,
            latest_version=latest_version,
            update_available=update_available,
            update_command=self.update(workspace_root).get("command", "") if command else "",
            update_source_url=latest_release.get("sourceUrl") or None,
            install_hint=(
                "Use Fluxio Setup -> Install OpenClaw for one-click install + onboarding, "
                "or run `npm install -g openclaw@latest` then `openclaw onboard --install-daemon`."
            ),
            doctor_summary=(
                (
                    f"OpenClaw is installed, but the latest npm release is {latest_version}."
                    if update_available and latest_version
                    else "OpenClaw is ready for mission routing."
                )
                if command
                else "Install OpenClaw with the setup one-click action before running phone-escalated missions."
            ),
            issues=issues,
            capabilities=self.list_capabilities(),
        )

    def install(self) -> dict[str, str]:
        return {
            "command": "npm install -g openclaw@latest",
            "follow_up": "openclaw onboard --install-daemon",
        }

    def doctor(self, workspace_root: Path) -> RuntimeInstallStatus:
        status = self.detect(workspace_root)
        if status.detected and not status.version:
            status.issues.append("OpenClaw responded, but version output was empty.")
        return status

    def update(self, workspace_root: Path) -> dict[str, str]:
        return {
            "command": "npm install -g openclaw@latest",
            "follow_up": "openclaw onboard --install-daemon",
        }

    def start_mission(
        self, mission: Mission, workspace: WorkspaceProfile
    ) -> dict[str, object]:
        route_contract = self._route_contract(mission)
        return {
            "launch_command": self._mission_launch_command(
                mission.mission_id,
                mission.objective,
                workspace.root_path,
                route_contract=route_contract,
            ),
            "workspace": workspace.root_path,
            "runtime_id": self.runtime_id,
            "route_contract": route_contract,
            "route_summary": self._route_summary(route_contract),
        }

    def stream_events(self, mission: Mission) -> list[dict[str, object]]:
        return [
            {
                "kind": "runtime.stream",
                "message": "OpenClaw mission stream is available through the gateway.",
                "missionId": mission.mission_id,
            }
        ]

    def request_approval(self, mission: Mission, prompt: str) -> dict[str, object]:
        return {
            "channel": "telegram",
            "message": prompt,
            "missionId": mission.mission_id,
        }

    def resume_mission(
        self, mission: Mission, workspace: WorkspaceProfile
    ) -> dict[str, object]:
        route_contract = self._route_contract(mission)
        return {
            "launch_command": self._mission_launch_command(
                mission.mission_id,
                f"Resume mission {mission.mission_id}: {mission.objective}",
                workspace.root_path,
                route_contract=route_contract,
            ),
            "workspace": workspace.root_path,
            "runtime_id": self.runtime_id,
            "route_contract": route_contract,
            "route_summary": self._route_summary(route_contract),
        }

    def stop_mission(self, mission: Mission) -> dict[str, object]:
        return {
            "message": f"Stop requested for OpenClaw mission {mission.mission_id}.",
            "runtime_id": self.runtime_id,
        }

    def _mission_launch_command(
        self,
        mission_id: str,
        objective: str,
        workspace_root: str,
        *,
        route_contract: dict[str, str] | None = None,
    ) -> str:
        session_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"fluxio_{mission_id}") or "fluxio"
        route_contract = route_contract or {}
        thinking = self._thinking_level(route_contract.get("effort", ""))
        model_id = self._canonical_model_id(route_contract)
        run_args = [
            "openclaw",
            "agent",
            "--session-id",
            session_id,
            "--message",
            objective,
            "--thinking",
            thinking,
            "--json",
        ]
        if not model_id:
            return shell_join(run_args)

        agent_id = self._agent_id(mission_id, model_id)
        run_args[2:2] = ["--agent", agent_id]
        add_args = [
            "openclaw",
            "agents",
            "add",
            agent_id,
            "--workspace",
            workspace_root,
            "--model",
            model_id,
            "--non-interactive",
            "--json",
        ]
        set_args = [
            "openclaw",
            "models",
            "--agent",
            agent_id,
            "set",
            model_id,
        ]
        add_cmd = shell_join(add_args)
        set_cmd = shell_join(set_args)
        run_cmd = shell_join(run_args)
        if os.name == "nt":
            return f"({add_cmd} >nul 2>nul || {set_cmd} >nul 2>nul) && {run_cmd}"
        return f"({add_cmd} >/dev/null 2>&1 || {set_cmd} >/dev/null 2>&1) && {run_cmd}"

    def _route_contract(self, mission: Mission) -> dict[str, str]:
        route = mission_phase_route(mission)
        provider = self._normalize_provider(route.get("provider", ""))
        model = str(route.get("model", "")).strip()
        return {
            "phase": str(route.get("phase", "")).strip().lower(),
            "role": str(route.get("role", "")).strip().lower(),
            "provider": provider,
            "model": model,
            "canonical_model_id": (
                f"{provider}/{model}" if provider and model and "/" not in model else model
            ),
            "effort": str(route.get("effort", "")).strip().lower(),
        }

    def _normalize_provider(self, provider: str) -> str:
        return OPENCLAW_PROVIDER_MAP.get(str(provider or "").strip().lower(), "")

    def _canonical_model_id(self, route_contract: dict[str, str]) -> str:
        model = str(route_contract.get("model", "")).strip()
        if "/" in model:
            return model
        provider = str(route_contract.get("provider", "")).strip()
        return f"{provider}/{model}" if provider and model else model

    def _thinking_level(self, effort: str) -> str:
        normalized = str(effort or "").strip().lower()
        if normalized in {"off", "minimal", "low", "medium", "high", "xhigh"}:
            return normalized
        return "high"

    def _agent_id(self, mission_id: str, model_id: str) -> str:
        digest = hashlib.sha1(model_id.encode("utf-8")).hexdigest()[:8]
        base = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"fluxio_{mission_id}_{digest}")
        return base[:64] or "fluxio_agent"

    def _route_summary(self, route_contract: dict[str, str]) -> str:
        model_id = self._canonical_model_id(route_contract)
        effort = str(route_contract.get("effort", "")).strip().lower()
        role = str(route_contract.get("role", "")).strip()
        phase = str(route_contract.get("phase", "")).strip()
        if not model_id:
            return "OpenClaw launch route is using the runtime default model configuration."
        route_prefix = ""
        if phase or role:
            route_prefix = f"{phase or 'execute'}:{role or 'route'} -> "
        summary = f"OpenClaw launch route: {route_prefix}{model_id}"
        if effort:
            summary += f" ({self._thinking_level(effort)} thinking)"
        return summary
