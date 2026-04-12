from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

from .models import GuidanceCard, ImprovementQueueItem, OnboardingProgress, TutorialStep
from .profiles import ProfileRegistry
from .runtimes import runtime_adapter_map

MINIMAX_GLOBAL_OPENCLAW_DOCS = "https://platform.minimax.io/docs/token-plan/openclaw"
MINIMAX_CN_OPENCLAW_DOCS = "https://platform.minimaxi.com/docs/token-plan/openclaw"
MINIMAX_GLOBAL_API_PORTAL = "https://platform.minimax.io/user-center/basic-information/interface-key"
MINIMAX_CN_API_PORTAL = "https://platform.minimaxi.com/user-center/basic-information/interface-key"


def _shell_open_url_command(url: str, platform_name: str) -> str:
    normalized_platform = (platform_name or "").strip().lower()
    if normalized_platform == "windows":
        return f'start "" "{url}"'
    if normalized_platform == "darwin":
        return f'open "{url}"'
    return f'xdg-open "{url}"'


def _primary_workspace_contract(root: Path) -> dict:
    workspaces = _load_control_list(root, "workspaces.json")
    if not workspaces:
        return {}
    return dict(workspaces[0])


def _minimax_auth_label(mode: str) -> str:
    normalized = str(mode or "none").strip().lower()
    if normalized == "minimax-portal-oauth":
        return "OAuth portal"
    if normalized == "minimax-api":
        return "API key"
    return "not configured"


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
    wsl = detect_wsl_status()
    setup_history = _load_setup_history(root)
    launched_mission_count = _launched_mission_count(root)
    phone_ready = _phone_destination_count(root) > 0
    checks = {
        "node": _command_version("node"),
        "python": _command_version("python"),
        "uv": _command_version("uv", ["--version"]),
        "openclaw": _command_version("openclaw"),
        "hermes": _command_version("hermes"),
    }
    profile_registry = ProfileRegistry(root / "config" / "profiles.json")
    next_actions = _recommended_next_actions(root, checks, wsl)
    setup_health = _build_setup_health(
        root,
        checks,
        wsl,
        next_actions,
        setup_history=setup_history,
        launched_mission_count=launched_mission_count,
        phone_ready=phone_ready,
    )
    tutorial = _build_tutorial(root, checks, profile_registry, setup_health)
    return {
        "platform": platform.system(),
        "workspaceRoot": str(root),
        "wsl": wsl,
        "checks": checks,
        "workspaceHints": {
            "hasReadme": readme_exists,
            "hasTauri": (root / "src-tauri").exists(),
            "hasPythonCore": (root / "src" / "grant_agent").exists(),
        },
        "nextActions": next_actions,
        "setupHealth": setup_health,
        "profileChoices": _profile_choices(profile_registry),
        "recommendedProfile": _recommended_profile(root, checks, profile_registry),
        "tutorial": tutorial,
    }


def build_guidance_snapshot(root: Path) -> dict:
    root = root.resolve()
    onboarding = detect_onboarding_status(root)
    profile_registry = ProfileRegistry(root / "config" / "profiles.json")
    checks = onboarding["checks"]
    tutorial = onboarding["tutorial"]
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


def _recommended_next_actions(
    root: Path,
    checks: dict | None = None,
    wsl: dict | None = None,
) -> list[str]:
    status: list[str] = []
    wsl = wsl or detect_wsl_status()
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
    if (root / "src-tauri").exists() and (not shutil.which("cargo") or not shutil.which("rustc")):
        status.append("Install Rust and Cargo before relying on the packaged Tauri desktop path.")
    if not _workspace_count(root):
        status.append("Add your first workspace so Fluxio can recommend skills and approvals.")
    if not _launched_mission_count(root):
        status.append("Launch a first mission to unlock the planner timeline and proof surfaces.")
    if _phone_destination_count(root) == 0:
        status.append("Configure Telegram escalation before long unattended runs.")

    if not status:
        status.append("Setup is complete. Launch or resume a mission.")
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


def _build_tutorial(
    root: Path,
    checks: dict,
    profile_registry: ProfileRegistry,
    setup_health: dict,
) -> dict:
    progress = _load_guidance_progress(root)
    selected_profile = _selected_profile(root) or progress.selected_profile or _recommended_profile(
        root, checks, profile_registry
    )
    missions = _launched_mission_count(root)
    workspaces = _workspace_count(root)
    phone_ready = _phone_destination_count(root) > 0

    steps = [
        TutorialStep(
            step_id="detect_environment",
            title="Check local setup",
            description="Verify WSL2, Node, Python, uv, OpenClaw, and Hermes before launching a mission.",
            status="completed" if setup_health.get("environmentReady") else "pending",
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
    if not tutorial["isComplete"] or not checks["openclaw"]["installed"] or not checks["hermes"]["installed"]:
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


def _latest_setup_record(
    setup_history: list[dict],
    dependency_id: str | None = None,
    command_surface: str | None = None,
) -> dict:
    filtered = []
    for record in setup_history:
        proposal = record.get("proposal", {})
        args = proposal.get("args", {})
        payload = record.get("result", {}).get("payload", {})
        if dependency_id is not None and (
            args.get("dependencyId") != dependency_id
            and payload.get("dependencyId") != dependency_id
        ):
            continue
        if command_surface is not None and args.get("commandSurface") != command_surface:
            continue
        filtered.append(record)
    if not filtered:
        return {}
    filtered.sort(key=lambda item: item.get("executed_at") or "")
    return filtered[-1]


def _dependency_stage(
    dependency: dict,
    *,
    setup_history: list[dict],
    latest_verify: dict,
) -> str:
    latest_action = _latest_setup_record(setup_history, dependency["dependencyId"])
    latest_surface = latest_action.get("proposal", {}).get("args", {}).get("commandSurface", "")
    latest_gate = latest_action.get("gate", {}).get("status", "")
    latest_ok = latest_action.get("result", {}).get("ok")
    latest_action_time = latest_action.get("executed_at") or ""
    latest_verify_time = latest_verify.get("executed_at") or ""
    installed = bool(dependency.get("installed"))

    if latest_gate == "pending":
        return "install_available"
    if latest_surface == "setup.auth" and latest_ok is False:
        return "failed"
    if latest_surface == "setup.auth" and latest_ok:
        return "healthy" if installed else "verify_pending"
    if latest_surface in {"setup.install", "setup.repair"} and latest_ok is False:
        return "failed"
    if latest_surface in {"setup.install", "setup.repair"} and latest_ok:
        if installed and latest_verify_time >= latest_action_time:
            return "healthy"
        return "verify_pending"
    if installed:
        return "healthy"
    if dependency.get("repairActions"):
        return "install_available"
    return "missing"


def _service_category_for_dependency(dependency: dict) -> str:
    dependency_id = dependency.get("dependencyId", "")
    category = dependency.get("category", "")
    if dependency_id == "wsl2":
        return "runtime_substrate"
    if dependency_id == "telegram_ready":
        return "connected_app_bridge"
    if dependency_id == "guided_mission":
        return "workflow_gate"
    if category in {"runtime", "agent_runtime"}:
        return "runtime"
    if category == "tooling":
        return "tooling"
    if category == "desktop":
        return "local_service"
    return category or "local_service"


def _install_source_for_dependency(dependency: dict) -> str:
    dependency_id = dependency.get("dependencyId", "")
    repair_actions = dependency.get("repairActions", [])
    primary_action = repair_actions[0] if repair_actions else {}
    platform = primary_action.get("platform", "")
    command = primary_action.get("command", "")
    if dependency_id == "wsl2":
        return "windows_feature"
    if dependency_id == "guided_mission":
        return "fluxio_desktop"
    if dependency_id == "telegram_ready":
        return "telegram_destination"
    if dependency_id == "minimax_auth":
        return "openclaw_auth"
    if dependency_id == "tauri_prereqs":
        return "rust_toolchain"
    if "winget" in command.lower():
        return "winget"
    if platform == "wsl2":
        return "wsl_script"
    if platform:
        return platform
    return "system_path"


def _verification_result_for_dependency(
    dependency: dict,
    latest_verify: dict,
) -> str:
    stage = dependency.get("stage", "missing")
    verify_ok = latest_verify.get("result", {}).get("ok")
    if stage == "healthy":
        return "passed" if latest_verify else "not_run"
    if stage == "verify_pending":
        return "pending"
    if verify_ok is False and dependency.get("required"):
        return "failed"
    if stage in {"install_available", "missing", "failed"}:
        return "blocked"
    return "not_run"


def _last_action_summary(record: dict) -> dict:
    if not record:
        return {}
    proposal = record.get("proposal", {})
    result = record.get("result", {})
    return {
        "actionId": proposal.get("args", {}).get("workspaceActionId", ""),
        "title": proposal.get("title", record.get("action_id", "")),
        "status": result.get("result_summary", "") or ("ok" if result.get("ok") else "failed"),
        "executedAt": record.get("executed_at", ""),
    }


def _management_mode_for_dependency(dependency: dict) -> str:
    dependency_id = dependency.get("dependencyId", "")
    if dependency_id == "guided_mission":
        return "externally_managed"
    if dependency_id == "telegram_ready":
        return "fluxio_managed"
    if dependency.get("latestAction"):
        return "fluxio_managed"
    if dependency.get("repairActions"):
        return "fluxio_managed"
    if dependency.get("category") in {"runtime", "agent_runtime", "tooling", "desktop", "platform"}:
        return "externally_managed"
    return "externally_managed"


def _service_actions_for_dependency(dependency: dict) -> list[dict]:
    actions = []
    for action in dependency.get("repairActions", []):
        if not action.get("command") and not action.get("followUp"):
            continue
        action_kind = str(action.get("kind", "")).strip().lower()
        command_surface = (
            "setup.install"
            if action_kind == "install"
            else ("setup.auth" if action_kind == "auth" else "setup.repair")
        )
        actions.append(
            {
                **action,
                "surface": "setup",
                "commandSurface": command_surface,
            }
        )
    return actions


def _overall_install_state(dependencies: list[dict], installer_ready: bool) -> str:
    required = [item for item in dependencies if item.get("required")]
    required_stages = [item.get("stage", "missing") for item in required]
    if installer_ready:
        return "healthy"
    if "failed" in required_stages:
        return "failed"
    if "verify_pending" in required_stages:
        return "verify_pending"
    if "install_available" in required_stages:
        return "install_available"
    if all(stage == "healthy" for stage in required_stages):
        return "verify_pending"
    return "missing"


def _build_setup_health(
    root: Path,
    checks: dict[str, dict],
    wsl: dict,
    next_actions: list[str],
    *,
    setup_history: list[dict] | None = None,
    launched_mission_count: int | None = None,
    phone_ready: bool | None = None,
) -> dict:
    setup_history = setup_history or []
    launched_mission_count = (
        _launched_mission_count(root)
        if launched_mission_count is None
        else launched_mission_count
    )
    phone_ready = (
        _phone_destination_count(root) > 0 if phone_ready is None else phone_ready
    )
    adapters = runtime_adapter_map()
    openclaw_install = adapters["openclaw"].install()
    hermes_install = adapters["hermes"].install()
    platform_name = platform.system().lower()
    workspace_contract = _primary_workspace_contract(root)
    minimax_auth_mode = str(
        workspace_contract.get("minimax_auth_mode", "none")
    ).strip().lower()
    minimax_auth_configured = minimax_auth_mode in {
        "minimax-portal-oauth",
        "minimax-api",
    }
    minimax_auth_details = (
        f"MiniMax auth path is configured through {_minimax_auth_label(minimax_auth_mode)}."
        if minimax_auth_configured
        else "Choose one MiniMax auth path so OpenClaw can route MiniMax runs safely."
    )
    tauri_required = (root / "src-tauri").exists()
    cargo_check = (
        _command_version("cargo")
        if tauri_required
        else {
            "installed": True,
            "command": None,
            "version": "",
            "details": "No Tauri desktop shell detected in this workspace.",
        }
    )
    rustc_check = (
        _command_version("rustc")
        if tauri_required
        else {
            "installed": True,
            "command": None,
            "version": "",
            "details": "No Tauri desktop shell detected in this workspace.",
        }
    )
    latest_verify = _latest_setup_record(setup_history, command_surface="setup.verify")

    dependencies = [
        {
            "dependencyId": "wsl2",
            "label": "WSL2",
            "category": "platform",
            "required": bool(wsl.get("required")),
            "installed": bool(wsl.get("installed")),
            "version": f"WSL{wsl.get('default_version')}" if wsl.get("default_version") else "",
            "details": wsl.get("details", ""),
            "repairActions": (
                []
                if (not wsl.get("required")) or (wsl.get("installed") and wsl.get("default_version") in {2, None})
                else [
                    {
                        "actionId": "install_wsl2",
                        "label": "Install WSL2",
                        "description": "Install WSL2 and reboot before runtime setup.",
                        "command": "wsl --install",
                        "kind": "install",
                        "platform": "windows",
                    }
                ]
            ),
        },
        {
            "dependencyId": "node",
            "label": "Node",
            "category": "runtime",
            "required": True,
            "installed": bool(checks["node"]["installed"]),
            "version": checks["node"].get("version") or "",
            "details": checks["node"].get("details", ""),
            "repairActions": []
            if checks["node"]["installed"]
            else [
                {
                    "actionId": "install_node",
                    "label": "Install Node LTS",
                    "description": "Install Node for OpenClaw and desktop tooling.",
                    "command": "winget install OpenJS.NodeJS.LTS" if platform_name == "windows" else "",
                    "kind": "install",
                    "platform": platform_name,
                }
            ],
        },
        {
            "dependencyId": "python",
            "label": "Python",
            "category": "runtime",
            "required": True,
            "installed": bool(checks["python"]["installed"]),
            "version": checks["python"].get("version") or "",
            "details": checks["python"].get("details", ""),
            "repairActions": []
            if checks["python"]["installed"]
            else [
                {
                    "actionId": "install_python",
                    "label": "Install Python",
                    "description": "Install Python for the Grant Agent core.",
                    "command": "winget install Python.Python.3.12" if platform_name == "windows" else "",
                    "kind": "install",
                    "platform": platform_name,
                }
            ],
        },
        {
            "dependencyId": "uv",
            "label": "uv",
            "category": "tooling",
            "required": True,
            "installed": bool(checks["uv"]["installed"]),
            "version": checks["uv"].get("version") or "",
            "details": checks["uv"].get("details", ""),
            "repairActions": []
            if checks["uv"]["installed"]
            else [
                {
                    "actionId": "install_uv",
                    "label": "Install uv",
                    "description": "Install uv for faster Python environment management.",
                    "command": "winget install --id=astral-sh.uv -e" if platform_name == "windows" else "",
                    "kind": "install",
                    "platform": platform_name,
                }
            ],
        },
        {
            "dependencyId": "openclaw",
            "label": "OpenClaw",
            "category": "agent_runtime",
            "required": True,
            "installed": bool(checks["openclaw"]["installed"]),
            "version": checks["openclaw"].get("version") or "",
            "details": checks["openclaw"].get("details", ""),
            "repairActions": []
            if checks["openclaw"]["installed"]
            else [
                {
                    "actionId": "install_openclaw",
                    "label": "Install OpenClaw",
                    "description": "Install the OpenClaw CLI and onboard the daemon.",
                    "command": openclaw_install.get("command", ""),
                    "followUp": openclaw_install.get("follow_up", ""),
                    "kind": "install",
                    "platform": platform_name,
                }
            ],
        },
        {
            "dependencyId": "hermes",
            "label": "Hermes",
            "category": "agent_runtime",
            "required": True,
            "installed": bool(checks["hermes"]["installed"]),
            "version": checks["hermes"].get("version") or "",
            "details": checks["hermes"].get("details", ""),
            "repairActions": []
            if checks["hermes"]["installed"]
            else [
                {
                    "actionId": "install_hermes",
                    "label": "Install Hermes",
                    "description": "Install Hermes in WSL2, then finish setup.",
                    "command": hermes_install.get("command", ""),
                    "followUp": hermes_install.get("follow_up", ""),
                    "kind": "install",
                    "platform": "wsl2",
                }
            ],
        },
        {
            "dependencyId": "minimax_auth",
            "label": "MiniMax auth",
            "category": "agent_runtime",
            "required": False,
            "installed": minimax_auth_configured,
            "version": _minimax_auth_label(minimax_auth_mode),
            "details": minimax_auth_details,
            "repairActions": [
                {
                    "actionId": "minimax-global-oauth",
                    "label": "MiniMax global OAuth",
                    "description": "Open OpenClaw setup docs and choose MiniMax Global OAuth.",
                    "command": _shell_open_url_command(
                        MINIMAX_GLOBAL_OPENCLAW_DOCS,
                        platform_name,
                    ),
                    "followUp": "In OpenClaw setup, select MiniMax Global — OAuth (minimax.io), then authorize OpenClaw.",
                    "kind": "auth",
                    "platform": platform_name,
                },
                {
                    "actionId": "minimax-cn-oauth",
                    "label": "MiniMax CN OAuth",
                    "description": "Open OpenClaw CN docs and choose MiniMax CN OAuth.",
                    "command": _shell_open_url_command(
                        MINIMAX_CN_OPENCLAW_DOCS,
                        platform_name,
                    ),
                    "followUp": "In OpenClaw setup, select the MiniMax CN OAuth auth method, then authorize OpenClaw.",
                    "kind": "auth",
                    "platform": platform_name,
                },
                {
                    "actionId": "minimax-global-api",
                    "label": "MiniMax global API key",
                    "description": "Open the global MiniMax API key portal for OpenClaw API-key auth.",
                    "command": _shell_open_url_command(
                        MINIMAX_GLOBAL_API_PORTAL,
                        platform_name,
                    ),
                    "followUp": "Generate an API key and configure OpenClaw with MiniMax Global API auth.",
                    "kind": "auth",
                    "platform": platform_name,
                },
                {
                    "actionId": "minimax-cn-api",
                    "label": "MiniMax CN API key",
                    "description": "Open the CN MiniMax API key portal for OpenClaw API-key auth.",
                    "command": _shell_open_url_command(
                        MINIMAX_CN_API_PORTAL,
                        platform_name,
                    ),
                    "followUp": "Generate an API key and configure OpenClaw with MiniMax CN API auth.",
                    "kind": "auth",
                    "platform": platform_name,
                },
            ],
        },
        {
            "dependencyId": "tauri_prereqs",
            "label": "Tauri prerequisites",
            "category": "desktop",
            "required": tauri_required,
            "installed": bool(cargo_check["installed"] and rustc_check["installed"]),
            "version": cargo_check.get("version") or rustc_check.get("version") or "",
            "details": (
                "Rust and Cargo are available for Tauri builds."
                if cargo_check["installed"] and rustc_check["installed"]
                else "Install Rust and Cargo before relying on the packaged Tauri desktop path."
            ),
            "repairActions": []
            if (cargo_check["installed"] and rustc_check["installed"])
            else [
                {
                    "actionId": "install_tauri_prereqs",
                    "dependencyId": "tauri_prereqs",
                    "label": "Install Rust toolchain",
                    "description": "Install Rust and Cargo for the Tauri desktop shell.",
                    "command": "winget install Rustlang.Rustup" if platform_name == "windows" else "curl https://sh.rustup.rs -sSf | sh -s -- -y",
                    "followUp": "rustup default stable",
                    "kind": "install",
                    "platform": platform_name,
                }
            ],
        },
        {
            "dependencyId": "telegram_ready",
            "label": "Telegram escalation",
            "category": "readiness",
            "required": False,
            "installed": bool(phone_ready),
            "version": "",
            "details": (
                "A Telegram destination is configured for blocked approvals and completion summaries."
                if phone_ready
                else "Add a Telegram destination so long unattended runs can escalate approvals."
            ),
            "repairActions": [],
        },
        {
            "dependencyId": "guided_mission",
            "label": "First guided mission",
            "category": "readiness",
            "required": True,
            "installed": launched_mission_count > 0,
            "version": "",
            "details": (
                "Fluxio has already launched a guided mission from the desktop path."
                if launched_mission_count > 0
                else "Finish setup by launching one real guided mission from Fluxio."
            ),
            "repairActions": [],
        },
    ]

    for dependency in dependencies:
        for action in dependency.get("repairActions", []):
            action["dependencyId"] = dependency["dependencyId"]
        dependency["latestAction"] = _latest_setup_record(
            setup_history,
            dependency["dependencyId"],
        )
        dependency["stage"] = _dependency_stage(
            dependency,
            setup_history=setup_history,
            latest_verify=latest_verify,
        )
        dependency["blocked"] = bool(
            dependency.get("required") and dependency.get("stage") != "healthy"
        )
        dependency["serviceCategory"] = _service_category_for_dependency(dependency)
        dependency["installSource"] = _install_source_for_dependency(dependency)
        dependency["currentHealthStatus"] = dependency["stage"]
        dependency["lastVerificationResult"] = _verification_result_for_dependency(
            dependency,
            latest_verify,
        )
        dependency["lastRepairAction"] = _last_action_summary(dependency["latestAction"])
        dependency["managementMode"] = _management_mode_for_dependency(dependency)

    repair_actions = [
        action
        for dependency in dependencies
        for action in dependency["repairActions"]
    ]
    missing_dependencies = [
        dependency["label"]
        for dependency in dependencies
        if dependency["required"] and dependency["stage"] != "healthy"
    ]
    filtered_repair_actions = [
        action for action in repair_actions if action.get("command") or action.get("followUp")
    ]
    environment_ready = all(
        dependency["stage"] == "healthy"
        for dependency in dependencies
        if dependency["required"] and dependency["dependencyId"] != "guided_mission"
    )
    installer_ready = all(
        dependency["stage"] == "healthy"
        for dependency in dependencies
        if dependency["required"]
    )
    history_by_dependency = {
        dependency["dependencyId"]: [
            record
            for record in setup_history
            if record.get("proposal", {}).get("args", {}).get("dependencyId")
            == dependency["dependencyId"]
        ][-6:]
        for dependency in dependencies
    }
    verify_action = {
        "actionId": "verify_setup_health",
        "label": "Verify setup health",
        "description": "Re-check local dependencies, runtimes, and blockers after a repair.",
        "commandSurface": "setup.verify",
        "kind": "verify",
        "platform": platform_name,
        "surface": "setup",
    }
    service_management = [
        {
            "serviceId": dependency["dependencyId"],
            "label": dependency["label"],
            "serviceCategory": dependency["serviceCategory"],
            "installSource": dependency["installSource"],
            "currentHealthStatus": dependency["currentHealthStatus"],
            "lastVerificationResult": dependency["lastVerificationResult"],
            "lastRepairAction": dependency["lastRepairAction"],
            "managementMode": dependency["managementMode"],
            "version": dependency.get("version", ""),
            "details": dependency.get("details", ""),
            "required": dependency.get("required", False),
            "serviceActions": _service_actions_for_dependency(dependency),
            "verifyAction": verify_action,
        }
        for dependency in dependencies
        if dependency["serviceCategory"] != "workflow_gate"
    ]
    return {
        "installState": _overall_install_state(dependencies, installer_ready),
        "environmentReady": environment_ready,
        "installerReady": installer_ready,
        "firstMissionLaunched": launched_mission_count > 0,
        "telegramReady": bool(phone_ready),
        "dependencies": dependencies,
        "missingDependencies": missing_dependencies,
        "repairActions": filtered_repair_actions,
        "globalActions": [verify_action],
        "actionHistoryByDependency": history_by_dependency,
        "serviceManagement": service_management,
        "serviceManagementSummary": {
            "totalItems": len(service_management),
            "healthyCount": sum(
                1 for item in service_management if item["currentHealthStatus"] == "healthy"
            ),
            "needsAttentionCount": sum(
                1 for item in service_management if item["currentHealthStatus"] != "healthy"
            ),
            "fluxioManagedCount": sum(
                1 for item in service_management if item["managementMode"] == "fluxio_managed"
            ),
            "externalCount": sum(
                1 for item in service_management if item["managementMode"] == "externally_managed"
            ),
        },
        "blockerExplanations": next_actions,
    }


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


def _launched_mission_count(root: Path) -> int:
    missions = _load_control_list(root, "missions.json")
    return sum(
        1
        for mission in missions
        if mission.get("state", {}).get("latest_session_id")
        or mission.get("state", {}).get("status")
        in {"running", "needs_approval", "verification_failed", "completed", "stopped"}
    )


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


def _load_setup_history(root: Path) -> list[dict]:
    path = root / ".agent_control" / "workspace_actions.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    history = payload.get("__setup__", [])
    return history if isinstance(history, list) else []


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
