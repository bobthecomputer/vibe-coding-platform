from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from ..models import Mission, RuntimeCapability, RuntimeInstallStatus, WorkspaceProfile
from ..subprocess_utils import hidden_windows_subprocess_kwargs
from .base import AgentRuntimeAdapter, mission_phase_route, shell_join

ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
DEFAULT_OPENCODEGO_MODEL = "opencode/deepseek-v4-flash-free"


def _clean_terminal_text(value: str) -> str:
    return ANSI_ESCAPE_PATTERN.sub("", str(value or "")).strip()


def _run_opencode_command(args: list[str], workspace_root: Path, timeout: int = 20) -> str:
    completed = subprocess.run(  # noqa: S603
        args,
        cwd=str(workspace_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        **hidden_windows_subprocess_kwargs(),
    )
    return _clean_terminal_text((completed.stdout or completed.stderr or "").strip())


class OpenCodeRuntimeAdapter(AgentRuntimeAdapter):
    runtime_id = "opencode"
    label = "OpenCodeGo"

    def list_capabilities(self) -> list[RuntimeCapability]:
        return [
            RuntimeCapability(
                key="subscription_models",
                label="OpenCodeGo models",
                available=True,
                detail="Routes Fluxio delegated missions through OpenCode subscription model slugs.",
            ),
            RuntimeCapability(
                key="cli_transcripts",
                label="Visible transcripts",
                available=True,
                detail="OpenCode CLI output is captured in Fluxio runtime session logs and events.",
            ),
            RuntimeCapability(
                key="model_switching",
                label="Per-mission model selection",
                available=True,
                detail="Route overrides can select opencode/* or minimax-coding-plan/* models per role.",
            ),
        ]

    def detect(self, workspace_root: Path) -> RuntimeInstallStatus:
        command = shutil.which("opencode")
        issues: list[str] = []
        version = None
        auth_output = ""
        models_output = ""
        if command:
            try:
                version = _run_opencode_command([command, "--version"], workspace_root, timeout=8)
            except Exception as exc:  # pragma: no cover - defensive
                issues.append(f"Unable to read OpenCode version: {exc}")
            try:
                auth_output = _run_opencode_command([command, "auth", "list"], workspace_root, timeout=12)
            except Exception as exc:  # pragma: no cover - defensive
                issues.append(f"Unable to read OpenCode auth status: {exc}")
            try:
                models_output = _run_opencode_command([command, "models"], workspace_root, timeout=20)
            except Exception as exc:  # pragma: no cover - defensive
                issues.append(f"Unable to read OpenCode models: {exc}")
        else:
            issues.append("OpenCode CLI was not found on PATH.")

        available_models = [
            line.strip()
            for line in models_output.splitlines()
            if line.strip() and "/" in line
        ]
        has_subscription_models = any(
            item.startswith(("opencode/", "minimax-coding-plan/"))
            for item in available_models
        )
        has_credentials = bool(auth_output and "credentials" in auth_output.lower())
        if command and not has_credentials:
            issues.append("OpenCode is installed, but no credential status was visible.")
        if command and not has_subscription_models:
            issues.append("OpenCode did not list OpenCodeGo subscription model slugs.")

        if command and has_subscription_models:
            doctor_summary = (
                "OpenCodeGo is ready for Fluxio mission routing through opencode subscription models."
            )
        elif command:
            doctor_summary = (
                "OpenCode is installed, but Fluxio could not verify OpenCodeGo subscription models."
            )
        else:
            doctor_summary = (
                "Install and authenticate OpenCode before using the OpenCodeGo runtime lane."
            )

        return RuntimeInstallStatus(
            runtime_id=self.runtime_id,
            label=self.label,
            detected=command is not None,
            command=command,
            version=version,
            update_available=False,
            update_command=self.update(workspace_root).get("command", "") if command else "",
            install_hint=(
                "Install OpenCode, run `opencode auth login`, then verify with "
                "`opencode auth list` and `opencode models`."
            ),
            doctor_summary=doctor_summary,
            issues=issues,
            capabilities=self.list_capabilities(),
        )

    def install(self) -> dict[str, str]:
        return {
            "command": "npm install -g opencode-ai@latest",
            "follow_up": "opencode auth login && opencode models",
        }

    def doctor(self, workspace_root: Path) -> RuntimeInstallStatus:
        return self.detect(workspace_root)

    def update(self, workspace_root: Path) -> dict[str, str]:
        return {
            "command": "npm install -g opencode-ai@latest",
            "follow_up": "opencode --version",
        }

    def start_mission(
        self, mission: Mission, workspace: WorkspaceProfile
    ) -> dict[str, object]:
        route_contract = self._route_contract(mission)
        return {
            "launch_command": self._mission_launch_command(
                mission.mission_id,
                mission.objective,
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
                "message": "OpenCodeGo output is captured in the Fluxio delegated session log.",
                "missionId": mission.mission_id,
            }
        ]

    def request_approval(self, mission: Mission, prompt: str) -> dict[str, object]:
        return {
            "channel": "desktop",
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
                route_contract=route_contract,
            ),
            "workspace": workspace.root_path,
            "runtime_id": self.runtime_id,
            "route_contract": route_contract,
            "route_summary": self._route_summary(route_contract),
        }

    def stop_mission(self, mission: Mission) -> dict[str, object]:
        return {
            "message": f"Stop requested for OpenCodeGo mission {mission.mission_id}.",
            "runtime_id": self.runtime_id,
        }

    def _mission_launch_command(
        self,
        mission_id: str,
        objective: str,
        *,
        route_contract: dict[str, str] | None = None,
    ) -> str:
        route_contract = route_contract or {}
        model_id = self._canonical_model_id(route_contract)
        title = re.sub(r"[^A-Za-z0-9_. -]+", " ", f"Fluxio {mission_id}").strip()
        args = [
            self._command(),
            "run",
            "--format",
            "default",
            "--title",
            title[:80] or "Fluxio OpenCodeGo mission",
        ]
        if model_id:
            args.extend(["--model", model_id])
        args.append(objective)
        return shell_join(args)

    def _command(self) -> str:
        command = shutil.which("opencode") or "opencode"
        return command.replace("\\", "/")

    def _route_contract(self, mission: Mission) -> dict[str, str]:
        route = mission_phase_route(mission)
        provider = self._normalize_provider(route.get("provider", ""))
        model = str(route.get("model", "")).strip()
        canonical_model_id = self._canonical_model_id(
            {"provider": provider, "model": model}
        )
        return {
            "phase": str(route.get("phase", "")).strip().lower(),
            "role": str(route.get("role", "")).strip().lower(),
            "provider": provider,
            "model": model,
            "canonical_model_id": canonical_model_id,
            "effort": str(route.get("effort", "")).strip().lower(),
        }

    def _normalize_provider(self, provider: str) -> str:
        normalized = str(provider or "").strip().lower()
        if normalized in {"opencode", "open-code", "opencodego", "opencode-go", "open-code-go"}:
            return "opencode"
        if normalized in {"minimax-coding-plan", "minimax-token-plan", "minimax-plan"}:
            return "minimax-coding-plan"
        if normalized in {"openai", "openai-codex"}:
            return "openai"
        return normalized

    def _canonical_model_id(self, route_contract: dict[str, str]) -> str:
        model = str(route_contract.get("model", "")).strip()
        if "/" in model:
            return model
        provider = str(route_contract.get("provider", "")).strip().lower()
        if provider in {"opencode", "minimax-coding-plan", "openai"} and model:
            return f"{provider}/{model}"
        return model or DEFAULT_OPENCODEGO_MODEL

    def _route_summary(self, route_contract: dict[str, str]) -> str:
        model_id = self._canonical_model_id(route_contract)
        role = str(route_contract.get("role", "")).strip()
        phase = str(route_contract.get("phase", "")).strip()
        prefix = f"{phase or 'execute'}:{role or 'route'} -> " if phase or role else ""
        return f"OpenCodeGo launch route: {prefix}{model_id}"
