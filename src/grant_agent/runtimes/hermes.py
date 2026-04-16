from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

from ..models import Mission, RuntimeCapability, RuntimeInstallStatus, WorkspaceProfile
from ..subprocess_utils import hidden_windows_subprocess_kwargs
from ..runtime_updates import compare_version_tokens, latest_hermes_release, normalize_hermes_version
from .base import AgentRuntimeAdapter, mission_phase_route, shell_join

HERMES_PROVIDER_MAP = {
    "openai": "openai-codex",
    "openai-codex": "openai-codex",
    "openrouter": "openrouter",
    "nous": "nous",
    "copilot-acp": "copilot-acp",
    "copilot": "copilot",
    "anthropic": "anthropic",
    "gemini": "gemini",
    "huggingface": "huggingface",
    "zai": "zai",
    "kimi-coding": "kimi-coding",
    "kimi-coding-cn": "kimi-coding-cn",
    "minimax": "minimax",
    "minimax-cn": "minimax-cn",
    "kilocode": "kilocode",
    "xiaomi": "xiaomi",
    "arcee": "arcee",
}


class HermesRuntimeAdapter(AgentRuntimeAdapter):
    runtime_id = "hermes"
    label = "Hermes"

    def list_capabilities(self) -> list[RuntimeCapability]:
        return [
            RuntimeCapability(
                key="scheduled_automations",
                label="Scheduled automations",
                available=True,
                detail="Hermes has built-in scheduling and long-running agent loops.",
            ),
            RuntimeCapability(
                key="skills_memory",
                label="Skills and memory",
                available=True,
                detail="Hermes learns and recalls skills across sessions.",
            ),
            RuntimeCapability(
                key="delegation",
                label="Delegation",
                available=True,
                detail="Hermes can spawn isolated subagents for parallel workstreams.",
            ),
        ]

    def detect(self, workspace_root: Path) -> RuntimeInstallStatus:
        command = shutil.which("hermes")
        version_output = None
        detected_in_wsl = False
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
                    **hidden_windows_subprocess_kwargs(),
                )
                version_output = (completed.stdout or completed.stderr).strip() or None
            except Exception as exc:  # pragma: no cover - defensive
                issues.append(f"Unable to read Hermes version: {exc}")
        else:
            version_output = self._wsl_hermes_version()
            if version_output is not None:
                command = "wsl:hermes"
                detected_in_wsl = True
            else:
                issues.append("Hermes CLI was not found on PATH or inside WSL2.")

        version = normalize_hermes_version(version_output)
        latest_release = latest_hermes_release()
        latest_version = latest_release.get("version") or None
        release_comparison_available = bool(command and version and latest_version)
        update_available = False
        if (
            command
            and version
            and latest_version
            and compare_version_tokens(version, latest_version) < 0
        ):
            update_available = True
        elif command and version_output and not release_comparison_available:
            update_available = "update available" in version_output.lower()
        if update_available and latest_version:
            issues.append(f"Hermes is behind the latest upstream release ({latest_version}).")

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
                "Use Fluxio Setup -> Install Hermes for one-click WSL2 install + setup, "
                "or run `curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash` "
                "then `hermes setup`."
            ),
            doctor_summary=(
                (
                    (
                        f"Hermes is installed in WSL2, but the latest upstream release is {latest_version}."
                        if update_available and latest_version and detected_in_wsl
                        else (
                            f"Hermes is installed, but the latest upstream release is {latest_version}."
                            if update_available and latest_version
                            else (
                                "Hermes is ready for mission routing through WSL2."
                                if detected_in_wsl
                                else "Hermes is ready for mission routing."
                            )
                        )
                    )
                )
                if command
                else "Install Hermes from setup (one-click WSL2 flow) before using the runtime."
            ),
            issues=issues,
            capabilities=self.list_capabilities(),
        )

    def install(self) -> dict[str, str]:
        return {
            "command": "curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash",
            "follow_up": "hermes setup",
        }

    def doctor(self, workspace_root: Path) -> RuntimeInstallStatus:
        status = self.detect(workspace_root)
        if status.detected and not status.version:
            status.issues.append("Hermes responded, but version output was empty.")
        return status

    def update(self, workspace_root: Path) -> dict[str, str]:
        if shutil.which("hermes"):
            return {
                "command": "hermes update",
                "follow_up": "hermes --version",
            }
        if self._wsl_hermes_available():
            return {
                "command": 'wsl bash -lc "hermes update"',
                "follow_up": 'wsl bash -lc "hermes --version"',
            }
        return {
            "command": "hermes update",
            "follow_up": "hermes --version",
        }

    def start_mission(
        self, mission: Mission, workspace: WorkspaceProfile
    ) -> dict[str, object]:
        route_contract = self._route_contract(mission)
        launch_command = self._mission_launch_command(
            mission.objective,
            route_contract=route_contract,
        )
        return {
            "launch_command": launch_command,
            "workspace": workspace.root_path,
            "runtime_id": self.runtime_id,
            "route_contract": route_contract,
            "route_summary": self._route_summary(route_contract),
        }

    def stream_events(self, mission: Mission) -> list[dict[str, object]]:
        return [
            {
                "kind": "runtime.stream",
                "message": "Hermes mission stream is available through CLI or messaging gateway.",
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
        objective = f"Resume mission {mission.mission_id}: {mission.objective}"
        route_contract = self._route_contract(mission)
        return {
            "launch_command": self._mission_launch_command(
                objective,
                route_contract=route_contract,
            ),
            "workspace": workspace.root_path,
            "runtime_id": self.runtime_id,
            "route_contract": route_contract,
            "route_summary": self._route_summary(route_contract),
        }

    def stop_mission(self, mission: Mission) -> dict[str, object]:
        return {
            "message": f"Stop requested for Hermes mission {mission.mission_id}.",
            "runtime_id": self.runtime_id,
        }

    def _mission_launch_command(
        self,
        objective: str,
        *,
        route_contract: dict[str, str] | None = None,
    ) -> str:
        route_contract = route_contract or {}
        provider = self._normalize_provider(route_contract.get("provider", ""))
        model = str(route_contract.get("model", "")).strip()
        native_args = ["hermes", "chat", "-q", objective, "-Q"]
        if model:
            native_args.extend(["--model", model])
        if provider:
            native_args.extend(["--provider", provider])
        hermes_chat_cmd = shell_join(native_args)
        if shutil.which("hermes"):
            return hermes_chat_cmd
        if self._wsl_hermes_available():
            return f"wsl bash -lc {shlex.quote(hermes_chat_cmd)}"
        return hermes_chat_cmd

    def _route_contract(self, mission: Mission) -> dict[str, str]:
        route = mission_phase_route(mission)
        return {
            "phase": str(route.get("phase", "")).strip().lower(),
            "role": str(route.get("role", "")).strip().lower(),
            "provider": self._normalize_provider(route.get("provider", "")),
            "model": str(route.get("model", "")).strip(),
            "effort": str(route.get("effort", "")).strip().lower(),
        }

    def _normalize_provider(self, provider: str) -> str:
        return HERMES_PROVIDER_MAP.get(str(provider or "").strip().lower(), "")

    def _route_summary(self, route_contract: dict[str, str]) -> str:
        model = str(route_contract.get("model", "")).strip()
        provider = str(route_contract.get("provider", "")).strip()
        effort = str(route_contract.get("effort", "")).strip()
        role = str(route_contract.get("role", "")).strip()
        phase = str(route_contract.get("phase", "")).strip()
        if not model and not provider:
            return "Hermes launch route is using the runtime default model configuration."
        route_prefix = ""
        if phase or role:
            route_prefix = f"{phase or 'execute'}:{role or 'route'} -> "
        summary = f"Hermes launch route: {route_prefix}{provider or 'auto'}/{model or 'default'}"
        if effort:
            summary += f" ({effort})"
        return summary

    def _wsl_hermes_available(self) -> bool:
        if os.name != "nt":
            return False
        wsl = shutil.which("wsl")
        if not wsl:
            return False
        try:
            completed = subprocess.run(  # noqa: S603
                [wsl, "bash", "-lc", "command -v hermes >/dev/null 2>&1"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
                **hidden_windows_subprocess_kwargs(),
            )
        except Exception:  # pragma: no cover - defensive
            return False
        return completed.returncode == 0

    def _wsl_hermes_version(self) -> str | None:
        if os.name != "nt":
            return None
        wsl = shutil.which("wsl")
        if not wsl:
            return None
        try:
            completed = subprocess.run(  # noqa: S603
                [
                    wsl,
                    "bash",
                    "-lc",
                    f"command -v hermes >/dev/null 2>&1 && hermes {shlex.quote('--version')}",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                **hidden_windows_subprocess_kwargs(),
            )
        except Exception:  # pragma: no cover - defensive
            return None
        if completed.returncode != 0:
            return None
        return (completed.stdout or completed.stderr).strip() or ""
