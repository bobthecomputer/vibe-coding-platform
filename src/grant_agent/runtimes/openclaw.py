from __future__ import annotations

import shutil
import subprocess
import re
from pathlib import Path

from ..models import Mission, RuntimeCapability, RuntimeInstallStatus, WorkspaceProfile
from ..runtime_updates import (
    compare_version_tokens,
    latest_openclaw_release,
    normalize_openclaw_version,
)
from .base import AgentRuntimeAdapter


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
        return {
            "launch_command": self._mission_launch_command(
                mission.mission_id,
                mission.objective,
            ),
            "workspace": workspace.root_path,
            "runtime_id": self.runtime_id,
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
        return {
            "launch_command": self._mission_launch_command(
                mission.mission_id,
                f"Resume mission {mission.mission_id}: {mission.objective}",
            ),
            "workspace": workspace.root_path,
            "runtime_id": self.runtime_id,
        }

    def stop_mission(self, mission: Mission) -> dict[str, object]:
        return {
            "message": f"Stop requested for OpenClaw mission {mission.mission_id}.",
            "runtime_id": self.runtime_id,
        }

    def _mission_launch_command(self, mission_id: str, objective: str) -> str:
        session_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"fluxio_{mission_id}") or "fluxio"
        escaped_objective = objective.replace('"', r"\"")
        return (
            f'openclaw agent --session-id {session_id} '
            f'--message "{escaped_objective}" --thinking high --json'
        )
