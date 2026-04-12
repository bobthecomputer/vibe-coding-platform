from __future__ import annotations

import json
import subprocess
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from .mission_control import (
    _build_validation_actions,
    ControlRoomStore,
    _build_git_actions,
    _inspect_workspace_git,
    _profile_parameter_snapshot,
)
from .models import (
    ActionApprovalGate,
    ActionExecutionRecord,
    ActionProposal,
    ActionResultEnvelope,
    WorkspaceProfile,
    utc_now_iso,
)
from .onboarding import detect_onboarding_status
from .profiles import ProfileRegistry
from .safety import risk_level_for_command

SETUP_HISTORY_KEY = "__setup__"


def execute_control_room_workspace_action(
    *,
    store: ControlRoomStore,
    root: Path,
    surface: str,
    action_id: str,
    workspace_id: str | None = None,
    approved: bool = False,
) -> dict:
    root = root.resolve()
    spec, workspace = _resolve_action_spec(
        store=store,
        root=root,
        surface=surface,
        action_id=action_id,
        workspace_id=workspace_id,
    )
    history_key = SETUP_HISTORY_KEY if surface == "setup" else workspace.workspace_id
    if (
        surface == "setup"
        and spec.get("commandSurface") in {"setup.install", "setup.repair"}
        and (approved or not spec.get("requiresApproval"))
    ):
        started = _build_started_record(
            root=root,
            surface=surface,
            spec=spec,
            workspace=workspace,
        )
        store.append_workspace_action(history_key, asdict(started))
    record = _run_action(
        root=root,
        surface=surface,
        spec=spec,
        workspace=workspace,
        approved=approved,
    )
    record_dict = asdict(record)
    store.append_workspace_action(history_key, record_dict)
    if surface == "setup":
        record_dict = _refresh_setup_result_payload(
            store=store,
            root=root,
            history_key=history_key,
            spec=spec,
            record=record_dict,
        )
    return {
        "ok": record_dict.get("result", {}).get("ok", False),
        "surface": surface,
        "workspaceId": workspace.workspace_id if workspace is not None else "",
        "record": record_dict,
        "snapshot": store.build_snapshot(),
    }


def build_setup_actions(root: Path) -> list[dict]:
    onboarding = detect_onboarding_status(root)
    setup_health = onboarding.get("setupHealth", {})
    actions = []
    for action in setup_health.get("repairActions", []):
        item = dict(action)
        action_kind = str(item.get("kind", "")).strip().lower()
        item["commandSurface"] = (
            "setup.install"
            if action_kind == "install"
            else ("setup.auth" if action_kind == "auth" else "setup.repair")
        )
        actions.append(item)
    actions.append(
        {
            "actionId": "verify_setup_health",
            "label": "Verify setup health",
            "description": "Re-check local dependencies, runtimes, and setup blockers.",
            "commandSurface": "setup.verify",
            "requiresApproval": False,
            "kind": "verify",
            "platform": "local",
        }
    )
    return actions


def _resolve_action_spec(
    *,
    store: ControlRoomStore,
    root: Path,
    surface: str,
    action_id: str,
    workspace_id: str | None,
) -> tuple[dict, WorkspaceProfile | None]:
    normalized_surface = (surface or "").strip().lower()
    if normalized_surface == "setup":
        workspace = _resolve_workspace_for_setup(store, workspace_id)
        actions = build_setup_actions(root)
        action = next((item for item in actions if item.get("actionId") == action_id), None)
        if action is None:
            raise ValueError(f"Unknown setup action id: {action_id}")
        if action.get("commandSurface") != "setup.verify":
            profile_name = workspace.user_profile if workspace is not None else "builder"
            action["requiresApproval"] = _setup_action_requires_approval(profile_name)
        return action, workspace

    if normalized_surface != "git":
        if normalized_surface != "validate":
            raise ValueError(f"Unknown workspace action surface: {surface}")
        if not workspace_id:
            raise ValueError("workspaceId is required for validation actions.")
        workspace = store.get_workspace(workspace_id)
        if workspace is None:
            raise ValueError(f"Unknown workspace id: {workspace_id}")
        actions = _build_validation_actions(Path(workspace.root_path))
        action = next((item for item in actions if item.get("actionId") == action_id), None)
        if action is None:
            raise ValueError(f"Unknown validation action id: {action_id}")
        return action, workspace
    if not workspace_id:
        raise ValueError("workspaceId is required for git actions.")
    workspace = store.get_workspace(workspace_id)
    if workspace is None:
        raise ValueError(f"Unknown workspace id: {workspace_id}")
    profiles = ProfileRegistry(root / "config" / "profiles.json")
    profile = profiles.resolve(workspace.user_profile, Path(workspace.root_path))
    profile_parameters = _profile_parameter_snapshot(workspace.user_profile, profile)
    git_snapshot = _inspect_workspace_git(Path(workspace.root_path))
    actions = _build_git_actions(git_snapshot, profile_parameters)
    action = next((item for item in actions if item.get("actionId") == action_id), None)
    if action is None:
        raise ValueError(f"Unknown git action id: {action_id}")
    return action, workspace


def _resolve_workspace_for_setup(
    store: ControlRoomStore,
    workspace_id: str | None,
) -> WorkspaceProfile | None:
    if workspace_id:
        return store.get_workspace(workspace_id)
    workspaces = store.load_workspaces()
    return workspaces[0] if workspaces else None


def _setup_action_requires_approval(profile_name: str) -> bool:
    return (profile_name or "builder").strip().lower() != "experimental"


def _run_action(
    *,
    root: Path,
    surface: str,
    spec: dict,
    workspace: WorkspaceProfile | None,
    approved: bool,
) -> ActionExecutionRecord:
    proposal = _build_proposal(
        root=root,
        surface=surface,
        spec=spec,
        workspace=workspace,
    )
    gate = ActionApprovalGate(
        required=proposal.requires_approval,
        status=(
            "approved"
            if proposal.requires_approval and approved
            else ("pending" if proposal.requires_approval else "not_required")
        ),
        risk_level=proposal.risk_level,
        reason=proposal.reason,
        approved_by="operator" if proposal.requires_approval and approved else "",
    )
    record = ActionExecutionRecord(
        action_id=proposal.action_id,
        proposal=proposal,
        gate=gate,
        attempts=1,
        event_id=proposal.event_id,
    )
    if proposal.requires_approval and not approved:
        record.result = ActionResultEnvelope(
            ok=False,
            payload={
                "approvalRequired": True,
                "workspaceActionId": spec.get("actionId", ""),
                "surface": surface,
                "commandSurface": spec.get("commandSurface", ""),
            },
            result_summary="Approval required before Fluxio will run this action.",
            target_path=proposal.target_path,
        )
        record.executed_at = utc_now_iso()
        return record

    start = time.monotonic()
    if spec.get("commandSurface") == "setup.verify":
        onboarding = detect_onboarding_status(root)
        setup_health = onboarding.get("setupHealth", {})
        missing = setup_health.get("missingDependencies", [])
        record.result = ActionResultEnvelope(
            ok=not missing,
            stdout=json.dumps(onboarding, indent=2),
            duration_ms=round((time.monotonic() - start) * 1000),
            payload={
                "onboarding": onboarding,
                "setupHealth": setup_health,
                "dependencyId": spec.get("dependencyId", ""),
            },
            result_summary=(
                "Setup health is ready."
                if not missing
                else f"Setup still needs attention: {', '.join(missing)}."
            ),
            target_path=str(root),
        )
        record.executed_at = utc_now_iso()
        return record

    command = str(spec.get("command", "")).strip()
    if not command:
        record.result = ActionResultEnvelope(
            ok=False,
            error="No executable command was configured for this action.",
            duration_ms=round((time.monotonic() - start) * 1000),
            result_summary="Workspace action failed before launch.",
            target_path=proposal.target_path,
        )
        record.executed_at = utc_now_iso()
        return record

    completed = _run_shell_action(
        command=command,
        cwd=Path(workspace.root_path).resolve() if workspace is not None else root,
        platform=str(spec.get("platform", "local")),
        timeout_seconds=_timeout_for_action(spec),
    )
    duration_ms = round((time.monotonic() - start) * 1000)
    post_onboarding = (
        detect_onboarding_status(root)
        if surface == "setup" and spec.get("commandSurface") in {"setup.install", "setup.repair"}
        else {}
    )
    post_setup = post_onboarding.get("setupHealth", {}) if post_onboarding else {}
    dependency_id = spec.get("dependencyId", "")
    dependency_state = next(
        (
            item.get("stage", "")
            for item in post_setup.get("dependencies", [])
            if item.get("dependencyId") == dependency_id
        ),
        "",
    )
    record.result = ActionResultEnvelope(
        ok=completed.returncode == 0,
        exit_code=completed.returncode,
        stdout=(completed.stdout or "").strip(),
        stderr=(completed.stderr or "").strip(),
        duration_ms=duration_ms,
        payload={
            "workspaceActionId": spec.get("actionId", ""),
            "surface": surface,
            "commandSurface": spec.get("commandSurface", ""),
            "followUp": spec.get("followUp", ""),
            "dependencyId": dependency_id,
            "setupHealth": post_setup,
            "onboarding": post_onboarding,
            "dependencyStage": dependency_state,
        },
        target_path=proposal.target_path,
        result_summary=(
            f"{spec.get('label', proposal.title)} completed with exit code {completed.returncode}."
            if not dependency_state
            else f"{spec.get('label', proposal.title)} completed with exit code {completed.returncode}. {dependency_id} is now {dependency_state}."
        ),
    )
    record.executed_at = utc_now_iso()
    return record


def _build_started_record(
    *,
    root: Path,
    surface: str,
    spec: dict,
    workspace: WorkspaceProfile | None,
) -> ActionExecutionRecord:
    proposal = _build_proposal(
        root=root,
        surface=surface,
        spec=spec,
        workspace=workspace,
    )
    proposal.status = "running"
    record = ActionExecutionRecord(
        action_id=f"{proposal.action_id}_started",
        proposal=proposal,
        gate=ActionApprovalGate(
            required=proposal.requires_approval,
            status="approved" if proposal.requires_approval else "not_required",
            risk_level=proposal.risk_level,
            reason=proposal.reason,
            approved_by="operator" if proposal.requires_approval else "",
        ),
        attempts=1,
        event_id=proposal.event_id,
        executed_at=utc_now_iso(),
    )
    record.result = ActionResultEnvelope(
        ok=False,
        payload={
            "workspaceActionId": spec.get("actionId", ""),
            "surface": surface,
            "commandSurface": spec.get("commandSurface", ""),
            "dependencyId": spec.get("dependencyId", ""),
            "dependencyStage": "installing",
        },
        target_path=proposal.target_path,
        result_summary=f"{spec.get('label', proposal.title)} started.",
    )
    return record


def _build_proposal(
    *,
    root: Path,
    surface: str,
    spec: dict,
    workspace: WorkspaceProfile | None,
) -> ActionProposal:
    command = str(spec.get("command", "")).strip()
    command_surface = str(spec.get("commandSurface", ""))
    command_kind = "setup_verify" if command_surface == "setup.verify" else (
        "git_status"
        if command_surface == "git.inspect"
        else (
            "git_commit"
            if command_surface == "git.commit"
            else ("test_run" if command_surface == "validate.workspace" else "shell_command")
        )
    )
    mutability_class = (
        "read"
        if command_surface in {"git.inspect", "setup.verify"}
        else ("execute" if command_surface == "validate.workspace" else "write")
    )
    action_uuid = uuid.uuid4().hex[:10]
    proposal = ActionProposal(
        action_id=f"workspace_action_{action_uuid}",
        kind=command_kind,
        title=str(spec.get("label", command_surface or "Workspace action")),
        command=command,
        args={
            "workspaceActionId": spec.get("actionId", ""),
            "surface": surface,
            "commandSurface": command_surface,
            "followUp": spec.get("followUp", ""),
            "dependencyId": spec.get("dependencyId", ""),
        },
        risk_level="low" if not command else risk_level_for_command(command),
        requires_approval=bool(spec.get("requiresApproval")),
        reason=str(spec.get("detail") or spec.get("description") or ""),
        status="proposed",
        event_id=f"evt_{uuid.uuid4().hex[:10]}",
        target_path=str(Path(workspace.root_path).resolve() if workspace is not None else root),
        target_scope="workspace" if workspace is not None else "setup",
        mutability_class=mutability_class,
        policy_decision="requires_approval" if spec.get("requiresApproval") else "auto_run",
    )
    return proposal


def _run_shell_action(
    *,
    command: str,
    cwd: Path,
    platform: str,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    if platform == "wsl2":
        return subprocess.run(  # noqa: S603
            ["wsl", "bash", "-lc", command],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    return subprocess.run(  # noqa: S603
        command,
        shell=True,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


def _timeout_for_action(spec: dict) -> int:
    command_surface = str(spec.get("commandSurface", ""))
    if command_surface in {"setup.install", "setup.repair"}:
        return 600
    if command_surface == "setup.auth":
        return 180
    if command_surface == "validate.workspace":
        return 600
    if command_surface in {"git.pull", "git.push", "deploy.pages"}:
        return 180
    return 60


def _refresh_setup_result_payload(
    *,
    store: ControlRoomStore,
    root: Path,
    history_key: str,
    spec: dict,
    record: dict,
) -> dict:
    onboarding = detect_onboarding_status(root)
    setup_health = onboarding.get("setupHealth", {})
    dependency_id = spec.get("dependencyId", "")
    missing = setup_health.get("missingDependencies", [])
    dependency_stage = next(
        (
            item.get("stage", "")
            for item in setup_health.get("dependencies", [])
            if item.get("dependencyId") == dependency_id
        ),
        "",
    )
    payload = dict(record.get("result", {}).get("payload", {}))
    payload["setupHealth"] = setup_health
    payload["onboarding"] = onboarding
    payload["dependencyStage"] = dependency_stage
    record["result"]["payload"] = payload
    if spec.get("commandSurface") == "setup.verify":
        record["result"]["ok"] = not missing
        record["result"]["stdout"] = json.dumps(onboarding, indent=2)
        record["result"]["result_summary"] = (
            "Setup health is ready."
            if not missing
            else f"Setup still needs attention: {', '.join(missing)}."
        )
    else:
        record["result"]["result_summary"] = (
            f"{spec.get('label', 'Setup action')} completed with exit code {record['result'].get('exit_code', 0)}."
            if not dependency_stage
            else (
                f"{spec.get('label', 'Setup action')} completed with exit code {record['result'].get('exit_code', 0)}. "
                f"{dependency_id} is now {dependency_stage}."
            )
        )
    histories = store.load_workspace_actions()
    entries = list(histories.get(history_key, []))
    if entries:
        entries[-1] = record
        histories[history_key] = entries
        store.workspace_actions_path.write_text(
            json.dumps(histories, indent=2),
            encoding="utf-8",
        )
    return record
