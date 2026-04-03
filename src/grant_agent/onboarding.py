from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

from .models import GuidanceCard, ImprovementQueueItem, OnboardingProgress, TutorialStep
from .profiles import ProfileRegistry


def _command_version(command_name: str, version_args: list[str] | None = None) -> dict:
    command = shutil.which(command_name)
    if not command:
        return {
            "installed": False,
            "command": None,
            "version": None,
            "details": f"{command_name} was not found on PATH.",
        }

    args = [command, *(version_args or ["--version"])]
    try:
        completed = subprocess.run(  # noqa: S603
            args,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        version_text = (completed.stdout or completed.stderr).strip() or None
    except Exception as exc:  # pragma: no cover - defensive
        version_text = None
        return {
            "installed": True,
            "command": command,
            "version": None,
            "details": f"Installed, but version lookup failed: {exc}",
        }

    return {
        "installed": True,
        "command": command,
        "version": version_text,
        "details": "Installed and reachable.",
    }


def detect_wsl_status() -> dict:
    if os.name != "nt":
        return {
            "required": False,
            "installed": True,
            "default_version": None,
            "details": "WSL2 is only required for the Windows-first install path.",
        }

    wsl = shutil.which("wsl")
    if not wsl:
        return {
            "required": True,
            "installed": False,
            "default_version": None,
            "details": "WSL is not installed. Install WSL2 to support OpenClaw and Hermes cleanly.",
        }

    try:
        completed = subprocess.run(  # noqa: S603
            [wsl, "--status"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        stdout = _decode_command_output(completed.stdout, completed.stderr)
        lowered = stdout.lower()
        default_version = 2 if "default version: 2" in lowered else None
        if "default version: 1" in lowered:
            default_version = 1
        return {
            "required": True,
            "installed": True,
            "default_version": default_version,
            "details": stdout or "WSL is installed.",
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "required": True,
            "installed": True,
            "default_version": None,
            "details": f"WSL is present, but status lookup failed: {exc}",
        }


def _decode_command_output(stdout: bytes | str, stderr: bytes | str) -> str:
    for value in (stdout, stderr):
        if not value:
            continue
        if isinstance(value, str):
            text = value
        else:
            for encoding in ("utf-8", "utf-16-le", "cp1252"):
                try:
                    text = value.decode(encoding).strip()
                    break
                except UnicodeDecodeError:
                    text = value.decode("utf-8", errors="ignore").strip()
        if text:
            return text.replace("\x00", "")
    return ""


def detect_onboarding_status(root: Path) -> dict:
    root = root.resolve()
    readme_exists = (root / "README.md").exists()
    checks = {
        "node": _command_version("node"),
        "python": _command_version("python"),
        "uv": _command_version("uv", ["--version"]),
        "openclaw": _command_version("openclaw"),
        "hermes": _command_version("hermes"),
    }
    profile_registry = ProfileRegistry(root / "config" / "profiles.json")
    tutorial = _build_tutorial(root, checks, profile_registry)
    return {
        "platform": platform.system(),
        "workspaceRoot": str(root),
        "wsl": detect_wsl_status(),
        "checks": checks,
        "workspaceHints": {
            "hasReadme": readme_exists,
            "hasTauri": (root / "src-tauri").exists(),
            "hasPythonCore": (root / "src" / "grant_agent").exists(),
        },
        "nextActions": _recommended_next_actions(root, checks),
        "profileChoices": _profile_choices(profile_registry),
        "recommendedProfile": _recommended_profile(root, checks, profile_registry),
        "tutorial": tutorial,
    }


def build_guidance_snapshot(root: Path) -> dict:
    root = root.resolve()
    profile_registry = ProfileRegistry(root / "config" / "profiles.json")
    checks = {
        "node": _command_version("node"),
        "python": _command_version("python"),
        "uv": _command_version("uv", ["--version"]),
        "openclaw": _command_version("openclaw"),
        "hermes": _command_version("hermes"),
    }
    tutorial = _build_tutorial(root, checks, profile_registry)
    progress = _load_guidance_progress(root)
    progress.selected_profile = tutorial["selectedProfile"]
    progress.completed_steps = tutorial["completedSteps"]
    progress.current_step_id = tutorial["currentStepId"]
    progress.is_complete = tutorial["isComplete"]
    _save_guidance_progress(root, progress)

    cards = _build_guidance_cards(root, tutorial, checks)
    product_improvements = _build_product_improvements(root, tutorial, checks)
    return {
        "onboardingProgress": progress.__dict__,
        "tutorialSteps": tutorial["steps"],
        "guidanceCards": [card.__dict__ for card in cards],
        "productImprovements": [item.__dict__ for item in product_improvements],
        "profileChoices": _profile_choices(profile_registry),
    }


def _recommended_next_actions(root: Path, checks: dict | None = None) -> list[str]:
    status: list[str] = []
    wsl = detect_wsl_status()
    checks = checks or {
        "node": _command_version("node"),
        "python": _command_version("python"),
        "uv": _command_version("uv", ["--version"]),
        "openclaw": _command_version("openclaw"),
        "hermes": _command_version("hermes"),
    }
    if wsl["required"] and not wsl["installed"]:
        status.append("Install WSL2 and reboot before backend setup.")
    if not checks["node"]["installed"]:
        status.append("Install Node 22.16+ or Node 24 for OpenClaw.")
    if not checks["python"]["installed"]:
        status.append("Install Python 3.11+ for the Grant Agent core.")
    if not checks["uv"]["installed"]:
        status.append("Install uv for faster Python environment management.")
    if not checks["openclaw"]["installed"]:
        status.append("Install OpenClaw and complete onboarding.")
    if not checks["hermes"]["installed"]:
        status.append("Install Hermes inside WSL2 and run `hermes setup`.")
    if not _workspace_count(root):
        status.append("Add your first workspace so Fluxio can recommend skills and approvals.")
    if not _mission_count(root):
        status.append("Launch a first mission to unlock the planner timeline and proof surfaces.")

    if not status:
        status.append("Setup looks healthy. Configure Telegram escalation and add workspaces.")
    return status


def _profile_choices(profile_registry: ProfileRegistry) -> list[dict]:
    choices: list[dict] = []
    for name in profile_registry.list_names():
        profile = profile_registry.get(name)
        if not profile:
            continue
        choices.append(
            {
                "name": name,
                "description": profile.description,
                "motion": profile.ui.get("motion", "standard"),
                "executionScope": profile.agent.execution_scope or "isolated",
                "approvalMode": profile.agent.approval_mode or "tiered",
                "explanationDepth": profile.agent.explanation_depth or "medium",
                "delegationAggressiveness": profile.agent.delegation_aggressiveness or "balanced",
            }
        )
    return choices


def _recommended_profile(
    root: Path,
    checks: dict,
    profile_registry: ProfileRegistry,
) -> str:
    if not checks["openclaw"]["installed"] or not checks["hermes"]["installed"]:
        return "beginner" if profile_registry.get("beginner") else profile_registry.default_profile
    if _mission_count(root) > 2 and profile_registry.get("advanced"):
        return "advanced"
    return "builder" if profile_registry.get("builder") else profile_registry.default_profile


def _build_tutorial(root: Path, checks: dict, profile_registry: ProfileRegistry) -> dict:
    progress = _load_guidance_progress(root)
    selected_profile = _selected_profile(root) or progress.selected_profile or _recommended_profile(
        root, checks, profile_registry
    )
    missions = _mission_count(root)
    workspaces = _workspace_count(root)
    phone_ready = _phone_destination_count(root) > 0

    steps = [
        TutorialStep(
            step_id="detect_environment",
            title="Check local setup",
            description="Verify WSL2, Node, Python, uv, OpenClaw, and Hermes before launching a mission.",
            status="completed",
            cta_label="View setup",
            panel="Setup",
        ),
        TutorialStep(
            step_id="choose_profile",
            title="Choose a guided profile",
            description="Pick Beginner, Builder, Advanced, or Experimental to set safe defaults for approvals and motion.",
            status="completed" if selected_profile else "pending",
            cta_label="Open guidance",
            panel="Guidance",
        ),
        TutorialStep(
            step_id="add_workspace",
            title="Add a workspace",
            description="Register a project so Fluxio can recommend skills, runtimes, and verification.",
            status="completed" if workspaces else "pending",
            cta_label="Add workspace",
            panel="Projects",
        ),
        TutorialStep(
            step_id="launch_mission",
            title="Launch a mission",
            description="Start a guided mission to see the planner, approvals, proof, and action timeline in context.",
            status="completed" if missions else "pending",
            cta_label="Start mission",
            panel="Missions",
        ),
        TutorialStep(
            step_id="enable_phone",
            title="Enable phone escalation",
            description="Add a Telegram destination so blocked approvals and completion summaries reach your phone.",
            status="completed" if phone_ready else "pending",
            cta_label="Configure Telegram",
            panel="Integrations",
        ),
    ]
    completed = [item.step_id for item in steps if item.status == "completed"]
    current = next((item.step_id for item in steps if item.status != "completed"), "")
    return {
        "selectedProfile": selected_profile,
        "completedSteps": completed,
        "currentStepId": current,
        "isComplete": not current,
        "steps": [item.__dict__ for item in steps],
    }


def _build_guidance_cards(
    root: Path,
    tutorial: dict,
    checks: dict,
) -> list[GuidanceCard]:
    cards: list[GuidanceCard] = []
    if tutorial["currentStepId"]:
        cards.append(
            GuidanceCard(
                card_id="tutorial.current",
                title="Continue guided setup",
                body="Fluxio keeps the next setup step visible so non-technical users can recover context quickly.",
                kind="tutorial",
                cta_label="Open tutorial",
                panel="Guidance",
            )
        )
    if not checks["openclaw"]["installed"] or not checks["hermes"]["installed"]:
        cards.append(
            GuidanceCard(
                card_id="runtime.install",
                title="Finish runtime setup",
                body="At least one runtime is still missing. Finish setup before expecting deep autonomous loops.",
                kind="setup",
                cta_label="Open setup",
                panel="Setup",
            )
        )
    if not _mission_count(root):
        cards.append(
            GuidanceCard(
                card_id="mission.first",
                title="Run a first mission",
                body="The planner, proof feed, and approvals become easier to understand after one real mission cycle.",
                kind="mission",
                cta_label="Start mission",
                panel="Missions",
            )
        )
    if _phone_destination_count(root) == 0:
        cards.append(
            GuidanceCard(
                card_id="phone.setup",
                title="Set up phone escalation",
                body="Remote approvals are part of the product promise. Configure Telegram before long unattended runs.",
                kind="integration",
                cta_label="Configure Telegram",
                panel="Integrations",
            )
        )
    return cards


def _build_product_improvements(
    root: Path,
    tutorial: dict,
    checks: dict,
) -> list[ImprovementQueueItem]:
    items: list[ImprovementQueueItem] = []
    if not tutorial["isComplete"]:
        items.append(
            ImprovementQueueItem(
                item_id="product_tutorial_completion",
                title="Improve tutorial completion rate",
                reason="The current onboarding path is still incomplete and should surface clearer next actions.",
                priority="high",
                category="tutorial",
            )
        )
    if _phone_destination_count(root) == 0:
        items.append(
            ImprovementQueueItem(
                item_id="product_phone_escalation",
                title="Promote remote approval setup earlier",
                reason="Phone escalation is still unconfigured, which weakens unattended long-run reliability.",
                priority="medium",
                category="automation",
            )
        )
    if not checks["hermes"]["installed"]:
        items.append(
            ImprovementQueueItem(
                item_id="product_runtime_guidance",
                title="Add clearer Hermes setup guidance",
                reason="Hermes is missing, so the setup flow should make the dual-runtime story easier to complete.",
                priority="medium",
                category="setup",
            )
        )
    return items


def _selected_profile(root: Path) -> str:
    workspaces_path = root / ".agent_control" / "workspaces.json"
    if not workspaces_path.exists():
        return ""
    try:
        payload = json.loads(workspaces_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    if not payload:
        return ""
    return str(payload[0].get("user_profile", ""))


def _workspace_count(root: Path) -> int:
    return len(_load_control_list(root, "workspaces.json"))


def _mission_count(root: Path) -> int:
    return len(_load_control_list(root, "missions.json"))


def _phone_destination_count(root: Path) -> int:
    missions = _load_control_list(root, "missions.json")
    return sum(
        1
        for mission in missions
        if mission.get("escalation_policy", {}).get("destination")
    )


def _load_control_list(root: Path, filename: str) -> list[dict]:
    path = root / ".agent_control" / filename
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _load_guidance_progress(root: Path) -> OnboardingProgress:
    path = root / ".agent_control" / "guidance_state.json"
    if not path.exists():
        return OnboardingProgress()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return OnboardingProgress()
    return OnboardingProgress(**payload)


def _save_guidance_progress(root: Path, progress: OnboardingProgress) -> None:
    control_dir = root / ".agent_control"
    control_dir.mkdir(parents=True, exist_ok=True)
    path = control_dir / "guidance_state.json"
    path.write_text(json.dumps(progress.__dict__, indent=2), encoding="utf-8")
