from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..models import Mission, RuntimeCapability, RuntimeInstallStatus, WorkspaceProfile
from .base import AgentRuntimeAdapter


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
                version = (completed.stdout or completed.stderr).strip() or None
            except Exception as exc:  # pragma: no cover - defensive
                issues.append(f"Unable to read Hermes version: {exc}")
        else:
            issues.append("Hermes CLI was not found on PATH or inside WSL2.")

        return RuntimeInstallStatus(
            runtime_id=self.runtime_id,
            label=self.label,
            detected=command is not None,
            command=command,
            version=version,
            install_hint="Install in WSL2 with `curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash`.",
            doctor_summary=(
                "Hermes is ready for mission routing."
                if command
                else "Install Hermes in WSL2 before using the runtime."
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

    def start_mission(
        self, mission: Mission, workspace: WorkspaceProfile
    ) -> dict[str, object]:
        return {
            "launch_command": f'hermes -p "{mission.objective}"',
            "workspace": workspace.root_path,
            "runtime_id": self.runtime_id,
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
        return {
            "launch_command": f'hermes -p "Resume mission {mission.mission_id}: {mission.objective}"',
            "workspace": workspace.root_path,
            "runtime_id": self.runtime_id,
        }

    def stop_mission(self, mission: Mission) -> dict[str, object]:
        return {
            "message": f"Stop requested for Hermes mission {mission.mission_id}.",
            "runtime_id": self.runtime_id,
        }
