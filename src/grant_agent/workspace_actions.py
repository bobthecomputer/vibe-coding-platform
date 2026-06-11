from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
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
from .app_capability_standard import (
    build_connected_apps_snapshot,
    record_connected_app_action_receipt,
)
from .models import (
    ActionApprovalGate,
    ActionExecutionRecord,
    ActionProposal,
    ActionResultEnvelope,
    WorkspaceProfile,
    utc_now_iso,
)
from .onboarding import (
    detect_onboarding_status,
    invalidate_onboarding_status_cache,
    load_telegram_destination,
)
from .profiles import ProfileRegistry
from .runtimes import invalidate_runtime_status_cache
from .safety import risk_level_for_command
from .subprocess_utils import hidden_windows_subprocess_kwargs

SETUP_HISTORY_KEY = "__setup__"
TELEGRAM_ENV_KEYS = (
    "FLUXIO_TELEGRAM_DESTINATION",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_DESTINATION",
)
APP_RUNTIME_BRIDGE_IDS = {"oratio-viva", "mind-tower", "jbheaven"}

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
    history_key = (
        SETUP_HISTORY_KEY
        if surface == "setup"
        else ("__bridge__" if surface == "bridge" or workspace is None else workspace.workspace_id)
    )
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
    if (
        surface == "setup"
        and spec.get("commandSurface") in {"setup.install", "setup.repair", "setup.telegram"}
        and record_dict.get("result", {}).get("ok", False)
        and bool(spec.get("autoRunVerify", False))
    ):
        verify_spec = next(
            (
                item
                for item in build_setup_actions(root)
                if item.get("actionId") == "verify_setup_health"
            ),
            None,
        )
        if verify_spec is not None:
            verify_record = _run_action(
                root=root,
                surface=surface,
                spec=verify_spec,
                workspace=workspace,
                approved=True,
            )
            verify_dict = asdict(verify_record)
            store.append_workspace_action(history_key, verify_dict)
            payload = dict(record_dict.get("result", {}).get("payload", {}))
            verify_payload = verify_dict.get("result", {}).get("payload", {})
            verify_setup = verify_payload.get("setupHealth", {})
            payload["autoVerify"] = {
                "ok": verify_dict.get("result", {}).get("ok", False),
                "resultSummary": verify_dict.get("result", {}).get("result_summary", ""),
                "missingDependencies": verify_setup.get("missingDependencies", []),
            }
            record_dict.setdefault("result", {})["payload"] = payload
    if surface == "setup":
        invalidate_onboarding_status_cache(root)
        invalidate_runtime_status_cache(root)
        record_dict = _refresh_setup_result_payload(
            store=store,
            root=root,
            history_key=history_key,
            spec=spec,
            record=record_dict,
        )
    snapshot = (
        _bridge_app_action_snapshot(root, history_key=history_key, record=record_dict)
        if spec.get("commandSurface") in {"bridge.app_health", "bridge.start_app"}
        else store.build_snapshot()
    )
    return {
        "ok": record_dict.get("result", {}).get("ok", False),
        "surface": surface,
        "workspaceId": workspace.workspace_id if workspace is not None else "",
        "record": record_dict,
        "snapshot": snapshot,
    }


def build_setup_actions(root: Path) -> list[dict]:
    onboarding = detect_onboarding_status(root)
    setup_health = onboarding.get("setupHealth", {})
    actions = []
    for action in setup_health.get("repairActions", []):
        item = dict(action)
        action_kind = str(item.get("kind", "")).strip().lower()
        command_surface = str(item.get("commandSurface", "")).strip()
        if not command_surface:
            command_surface = (
                "setup.install"
                if action_kind == "install"
                else ("setup.auth" if action_kind == "auth" else "setup.repair")
            )
        item["commandSurface"] = command_surface
        if (
            action_kind == "install"
            and item.get("followUp")
            and item.get("dependencyId") in {"openclaw", "hermes", "tauri_prereqs"}
        ):
            item["autoRunFollowUp"] = True
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
        if action.get("commandSurface") not in {"setup.verify", "setup.telegram"}:
            profile_name = workspace.user_profile if workspace is not None else "builder"
            action["requiresApproval"] = _setup_action_requires_approval(profile_name)
        return action, workspace

    if normalized_surface == "bridge":
        workspace = _resolve_workspace_for_setup(store, workspace_id)
        actions = _build_bridge_actions(root)
        action = next((item for item in actions if item.get("actionId") == action_id), None)
        if action is None:
            raise ValueError(f"Unknown bridge action id: {action_id}")
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


def _build_bridge_actions(root: Path) -> list[dict]:
    snapshot = build_connected_apps_snapshot(root)
    actions: list[dict] = []
    for session in snapshot.get("connectedSessions", []):
        app_id = str(session.get("app_id", ""))
        ui_hints = session.get("ui_hints", {}) if isinstance(session.get("ui_hints"), dict) else {}
        bridge_role = str(ui_hints.get("bridgeRole") or "")
        if app_id not in {"synology-fast-sync", "cloud-drive-sync"} and bridge_role not in {
            "nas_storage",
            "cloud_storage",
        }:
            if app_id in APP_RUNTIME_BRIDGE_IDS:
                actions.extend(_build_app_runtime_bridge_actions(session))
            continue
        is_cloud = app_id == "cloud-drive-sync" or bridge_role == "cloud_storage"
        latest_task = session.get("latest_task_result", {})
        payload = latest_task.get("payload", {}) if isinstance(latest_task, dict) else {}
        requires_approval_for_write = bool(
            payload.get("requiresApprovalForWrite", True)
        )
        activation_command = str(payload.get("activationCommand") or "").strip()
        if not is_cloud and activation_command:
            actions.append(
                {
                    "actionId": "activate-nas-mapping",
                    "label": "Activate NAS mapping",
                    "description": "Run the Core/Cowork Synology mapper so the NAS project drive is available.",
                    "commandSurface": "bridge.activate",
                    "requiresApproval": True,
                    "kind": "activate",
                    "appId": app_id,
                    "command": _quote_shell_path(activation_command),
                    "platform": "local",
                }
            )
        if not is_cloud:
            host = str(payload.get("selectedHost") or ui_hints.get("selectedHost") or "").strip()
            port = int(payload.get("controlPort") or ui_hints.get("controlPort") or 22)
            user = str(payload.get("sshUser") or ui_hints.get("sshUser") or "").strip()
            remote_root = str(
                payload.get("remoteProjectRoot") or ui_hints.get("remoteProjectRoot") or ""
            ).strip()
            if host and user:
                actions.append(
                    {
                        "actionId": "verify-nas-ssh",
                        "label": "Verify NAS SSH",
                        "description": (
                            "Probe the SSH/SFTP NAS route on the configured port without logging secrets. "
                            "A local guard rate-limits repeated probes so port 22 is not hammered."
                        ),
                        "commandSurface": "bridge.verify",
                        "requiresApproval": False,
                        "kind": "verify",
                        "appId": app_id,
                        "command": (
                            f"python scripts/nas_ssh_probe.py --host {_quote_shell_arg(host)} "
                            f"--port {port} --user {_quote_shell_arg(user)} "
                            f"--remote-root {_quote_shell_arg(remote_root)} --diagnose "
                            "--cooldown-seconds 20 --window-seconds 60 --max-attempts 6"
                        ),
                        "platform": "local",
                        "portSafety": {
                            "guarded": True,
                            "cooldownSeconds": 20,
                            "windowSeconds": 60,
                            "maxAttempts": 6,
                            "ports": [port],
                        },
                    }
                )
                actions.append(
                    {
                        "actionId": "unlock-codex-network",
                        "label": "Unlock local network rule",
                        "description": (
                            "Disable the local Codex outbound firewall block through an elevated "
                            "PowerShell prompt, then retry the NAS SSH route."
                        ),
                        "commandSurface": "bridge.activate",
                        "requiresApproval": True,
                        "kind": "repair",
                        "appId": app_id,
                        "command": 'powershell -NoProfile -ExecutionPolicy Bypass -File "scripts/unblock_codex_network.ps1"',
                        "platform": "local",
                    }
                )
        actions.append(
            {
                "actionId": "monitor-cloud-drive" if is_cloud else "monitor-fast-sync",
                "label": "Monitor bridge",
                "description": (
                    "Read the latest cloud-drive bridge status from the connected app."
                    if is_cloud
                    else "Read the latest computer/NAS bridge status from the connected app."
                ),
                "commandSurface": "bridge.status",
                "requiresApproval": False,
                "kind": "status",
                "appId": app_id,
            }
        )
        actions.append(
            {
                "actionId": "queue-cloud-drive-transfer" if is_cloud else "start-sync-selection",
                "label": "Queue transfer",
                "description": (
                    "Queue an upload or download through the cloud-drive bridge after preview."
                    if is_cloud
                    else (
                        "Queue an upload or download through the NAS bridge after preview."
                        if requires_approval_for_write
                        else "Run an upload or download through the NAS bridge immediately."
                    )
                ),
                "commandSurface": "bridge.sync",
                "requiresApproval": requires_approval_for_write,
                "kind": "sync",
                "appId": app_id,
            }
        )
    return actions


def _build_app_runtime_bridge_actions(session: dict) -> list[dict]:
    app_id = str(session.get("app_id", "")).strip()
    if not app_id:
        return []
    app_name = str(session.get("app_name") or session.get("label") or app_id)
    ui_hints = session.get("ui_hints", {}) if isinstance(session.get("ui_hints"), dict) else {}
    latest_task = (
        session.get("latest_task_result", {})
        if isinstance(session.get("latest_task_result"), dict)
        else {}
    )
    latest_payload = (
        latest_task.get("payload", {}) if isinstance(latest_task.get("payload"), dict) else {}
    )
    start_command = str(ui_hints.get("startCommand") or latest_payload.get("startCommand") or "").strip()
    health_url = str(
        ui_hints.get("healthUrl")
        or latest_payload.get("healthUrl")
        or ui_hints.get("bridgeHealthUrl")
        or ""
    ).strip()
    app_url = str(ui_hints.get("appUrl") or latest_payload.get("appUrl") or "").strip()
    app_root = str(session.get("app_root") or latest_payload.get("workspaceRoot") or "").strip()
    actions: list[dict] = []
    if health_url:
        actions.append(
            {
                "actionId": f"check-{app_id}-health",
                "label": f"Check {app_name} health",
                "description": "Probe the local app health endpoint and save a readable bridge receipt.",
                "commandSurface": "bridge.app_health",
                "requiresApproval": False,
                "kind": "status",
                "appId": app_id,
                "appName": app_name,
                "healthUrl": health_url,
                "appUrl": app_url,
                "appRoot": app_root,
                "platform": "local",
            }
        )
    if start_command:
        actions.append(
            {
                "actionId": f"start-{app_id}",
                "label": f"Start {app_name}",
                "description": (
                    "Start the local app service in the background, then check health and record "
                    "the exact command, PID, log path, and readiness state."
                ),
                "commandSurface": "bridge.start_app",
                "requiresApproval": False,
                "kind": "start",
                "appId": app_id,
                "appName": app_name,
                "command": start_command,
                "healthUrl": health_url,
                "appUrl": app_url,
                "appRoot": app_root,
                "platform": "local",
            }
        )
    return actions


def _bridge_app_action_snapshot(root: Path, *, history_key: str, record: dict) -> dict:
    payload = record.get("result", {}).get("payload", {}) if isinstance(record, dict) else {}
    return {
        "summaryMode": "workspace_action_receipt",
        "source": "bridge_app_action",
        "workspaceActionHistoryKey": history_key,
        "latestWorkspaceAction": record,
        "connectedApp": _compact_connected_app_from_action_payload(payload),
    }


def _compact_connected_app_from_action_payload(payload: dict) -> dict:
    return {
        "appId": payload.get("appId", ""),
        "appName": payload.get("appName", ""),
        "status": "ready" if payload.get("healthOnline") else "offline",
        "bridgeHealth": "healthy" if payload.get("healthOnline") else "offline",
        "appRoot": payload.get("appRoot", ""),
        "startCommand": payload.get("startCommand") or payload.get("command", ""),
        "healthUrl": payload.get("healthUrl", ""),
        "appUrl": payload.get("appUrl", ""),
        "pid": payload.get("pid"),
        "logPath": payload.get("logPath", ""),
        "alreadyRunning": bool(payload.get("alreadyRunning")),
    }


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

    if spec.get("commandSurface") == "setup.telegram":
        setup = _configure_telegram_destination(root)
        onboarding = detect_onboarding_status(root)
        setup_health = onboarding.get("setupHealth", {})
        record.result = ActionResultEnvelope(
            ok=bool(setup.get("ok")),
            exit_code=0 if setup.get("ok") else 1,
            error="" if setup.get("ok") else str(setup.get("error", "")),
            duration_ms=round((time.monotonic() - start) * 1000),
            payload={
                "workspaceActionId": spec.get("actionId", ""),
                "surface": surface,
                "commandSurface": spec.get("commandSurface", ""),
                "dependencyId": "telegram_ready",
                "telegramDestination": setup.get("destination", ""),
                "destinationSource": setup.get("source", ""),
                "onboarding": onboarding,
                "setupHealth": setup_health,
                "baseExitCode": 0 if setup.get("ok") else 1,
                "followUpRan": False,
                "followUpExitCode": None,
            },
            result_summary=str(setup.get("summary", "")),
            target_path=proposal.target_path,
        )
        record.executed_at = utc_now_iso()
        return record

    if spec.get("commandSurface") == "bridge.app_health":
        health_url = str(spec.get("healthUrl") or "").strip()
        health_payload = _probe_health_url(health_url)
        app_name = str(spec.get("appName") or spec.get("appId") or "Connected app")
        result_payload = {
            "workspaceActionId": spec.get("actionId", ""),
            "surface": surface,
            "commandSurface": spec.get("commandSurface", ""),
            "appId": spec.get("appId", ""),
            "appName": app_name,
            "healthUrl": health_url,
            "appUrl": spec.get("appUrl", ""),
            "appRoot": spec.get("appRoot", ""),
            "healthOnline": bool(health_payload),
            "healthPayload": health_payload,
        }
        result_summary = (
            f"{app_name} health responded at {health_url}."
            if health_payload
            else f"{app_name} health did not respond at {health_url}."
        )
        record_connected_app_action_receipt(
            root,
            app_id=str(spec.get("appId") or ""),
            app_name=app_name,
            command_surface=str(spec.get("commandSurface") or ""),
            result_summary=result_summary,
            ok=bool(health_payload),
            health_online=bool(health_payload),
            payload=result_payload,
        )
        record.result = ActionResultEnvelope(
            ok=bool(health_payload),
            exit_code=0 if health_payload else 1,
            duration_ms=round((time.monotonic() - start) * 1000),
            payload=result_payload,
            result_summary=result_summary,
            target_path=proposal.target_path,
        )
        record.executed_at = utc_now_iso()
        return record

    if spec.get("commandSurface") == "bridge.start_app":
        app_name = str(spec.get("appName") or spec.get("appId") or "Connected app")
        start_command = str(spec.get("command") or "").strip()
        health_url = str(spec.get("healthUrl") or "").strip()
        health_before = _probe_health_url(health_url)
        launch_receipt: dict[str, object] = {}
        launch_ok = bool(health_before)
        launch_error = ""
        process_running = False
        if not health_before:
            launch_receipt = _launch_background_app_command(
                root=root,
                app_id=str(spec.get("appId") or "connected-app"),
                command=start_command,
                app_root=str(spec.get("appRoot") or ""),
            )
            launch_ok = bool(launch_receipt.get("ok"))
            launch_error = str(launch_receipt.get("error") or "")
            time.sleep(1.25)
        health_after = _probe_health_url(health_url)
        ready = bool(health_before or health_after)
        if launch_receipt.get("pid"):
            process_running = _process_is_running(int(launch_receipt.get("pid") or 0))
        if launch_ok and not ready and launch_receipt.get("pid") and not process_running:
            launch_ok = False
            log_tail = _tail_text(Path(str(launch_receipt.get("logPath") or "")), limit=900)
            launch_error = (
                "Process exited during startup."
                + (f" Latest log: {log_tail}" if log_tail else "")
            )
        result_payload = {
            "workspaceActionId": spec.get("actionId", ""),
            "surface": surface,
            "commandSurface": spec.get("commandSurface", ""),
            "appId": spec.get("appId", ""),
            "appName": app_name,
            "command": start_command,
            "startCommand": start_command,
            "healthUrl": health_url,
            "appUrl": spec.get("appUrl", ""),
            "appRoot": spec.get("appRoot", ""),
            "pid": launch_receipt.get("pid"),
            "logPath": launch_receipt.get("logPath", ""),
            "alreadyRunning": bool(health_before),
            "processRunning": process_running,
            "healthOnline": ready,
            "healthPayload": health_after or health_before,
        }
        result_summary = (
            f"{app_name} was already running and health responded at {health_url}."
            if health_before
            else (
                f"{app_name} start command launched; health responded at {health_url}."
                if ready
                else (
                    f"{app_name} start command launched, but health is still warming up at {health_url}. "
                    "Use Check health again in a moment."
                )
                if launch_ok
                else f"{app_name} could not be started: {launch_error or 'no launch receipt was produced'}."
            )
        )
        record_connected_app_action_receipt(
            root,
            app_id=str(spec.get("appId") or ""),
            app_name=app_name,
            command_surface=str(spec.get("commandSurface") or ""),
            result_summary=result_summary,
            ok=bool(launch_ok or ready),
            health_online=ready,
            payload=result_payload,
        )
        record.result = ActionResultEnvelope(
            ok=bool(launch_ok or ready),
            exit_code=0 if (launch_ok or ready) else 1,
            error=launch_error,
            duration_ms=round((time.monotonic() - start) * 1000),
            payload=result_payload,
            result_summary=result_summary,
            target_path=proposal.target_path,
        )
        record.executed_at = utc_now_iso()
        return record

    if spec.get("commandSurface") in {"bridge.status", "bridge.sync"}:
        snapshot = build_connected_apps_snapshot(root)
        requested_app_id = str(spec.get("appId") or "synology-fast-sync")
        storage_session = next(
            (
                item
                for item in snapshot.get("connectedSessions", [])
                if item.get("app_id") == requested_app_id
            ),
            {},
        )
        latest_task = storage_session.get("latest_task_result", {})
        payload = latest_task.get("payload", {}) if isinstance(latest_task, dict) else {}
        is_sync_request = spec.get("commandSurface") == "bridge.sync"
        bridge_name = "Cloud-drive" if requested_app_id == "cloud-drive-sync" else "NAS"
        record.result = ActionResultEnvelope(
            ok=bool(storage_session),
            exit_code=0 if storage_session else 1,
            duration_ms=round((time.monotonic() - start) * 1000),
            payload={
                "workspaceActionId": spec.get("actionId", ""),
                "surface": surface,
                "commandSurface": spec.get("commandSurface", ""),
                "bridgeSession": storage_session,
                "sourceRoot": payload.get("sourceRoot", "") if isinstance(payload, dict) else "",
                "targetRoot": payload.get("targetRoot", "") if isinstance(payload, dict) else "",
                "queuedTransfer": bool(is_sync_request and storage_session),
            },
            result_summary=(
                f"{bridge_name} bridge transfer request is recorded for the connected app."
                if is_sync_request and storage_session
                else (
                    latest_task.get("resultSummary", "")
                    if isinstance(latest_task, dict) and latest_task.get("resultSummary")
                    else f"{bridge_name} bridge status was refreshed."
                )
            ),
            target_path=proposal.target_path,
        )
        record.executed_at = utc_now_iso()
        return record

    execution_root = Path(workspace.root_path).resolve() if workspace is not None else root
    timeout_seconds = _timeout_for_action(spec)
    batch_commands = list(spec.get("batchCommands", []))
    command = str(spec.get("command", "")).strip()
    if not command and not batch_commands:
        record.result = ActionResultEnvelope(
            ok=False,
            error="No executable command was configured for this action.",
            duration_ms=round((time.monotonic() - start) * 1000),
            result_summary="Workspace action failed before launch.",
            target_path=proposal.target_path,
        )
        record.executed_at = utc_now_iso()
        return record

    completed: subprocess.CompletedProcess[str] | None = None
    follow_up_completed: subprocess.CompletedProcess[str] | None = None
    follow_up_ran = False
    effective_result: subprocess.CompletedProcess[str] | None = None
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    batch_results: list[dict] = []
    dependency_ids: list[str] = []
    if batch_commands:
        for batch_item in batch_commands:
            item = dict(batch_item)
            item_command = str(item.get("command", "")).strip()
            if not item_command:
                continue
            item_label = str(item.get("label", "Setup step"))
            item_platform = str(item.get("platform") or spec.get("platform", "local"))
            item_completed = _run_shell_action(
                command=item_command,
                cwd=execution_root,
                platform=item_platform,
                timeout_seconds=timeout_seconds,
            )
            item_follow_up_command = str(item.get("followUp", "")).strip()
            item_follow_up_completed: subprocess.CompletedProcess[str] | None = None
            item_follow_up_ran = False
            if (
                item_completed.returncode == 0
                and item_follow_up_command
                and bool(item.get("autoRunFollowUp", spec.get("autoRunFollowUp", False)))
            ):
                item_follow_up_completed = _run_shell_action(
                    command=item_follow_up_command,
                    cwd=execution_root,
                    platform=item_platform,
                    timeout_seconds=timeout_seconds,
                )
                item_follow_up_ran = True
            item_effective = item_follow_up_completed or item_completed
            item_stdout = "\n".join(
                text
                for text in [
                    (item_completed.stdout or "").strip(),
                    (
                        (item_follow_up_completed.stdout or "").strip()
                        if item_follow_up_completed is not None
                        else ""
                    ),
                ]
                if text
            )
            item_stderr = "\n".join(
                text
                for text in [
                    (item_completed.stderr or "").strip(),
                    (
                        (item_follow_up_completed.stderr or "").strip()
                        if item_follow_up_completed is not None
                        else ""
                    ),
                ]
                if text
            )
            if item_stdout:
                stdout_parts.append(item_stdout)
            if item_stderr:
                stderr_parts.append(item_stderr)
            item_dependency_id = str(item.get("dependencyId", "")).strip()
            if item_dependency_id and item_dependency_id not in dependency_ids:
                dependency_ids.append(item_dependency_id)
            batch_results.append(
                {
                    "label": item_label,
                    "dependencyId": item_dependency_id,
                    "platform": item_platform,
                    "command": item_command,
                    "followUp": item_follow_up_command,
                    "baseExitCode": item_completed.returncode,
                    "followUpRan": item_follow_up_ran,
                    "followUpExitCode": (
                        item_follow_up_completed.returncode
                        if item_follow_up_completed is not None
                        else None
                    ),
                    "effectiveExitCode": item_effective.returncode,
                }
            )
            completed = item_completed
            follow_up_completed = item_follow_up_completed
            follow_up_ran = item_follow_up_ran
            effective_result = item_effective
            if item_effective.returncode != 0:
                break
    else:
        completed = _run_shell_action(
            command=command,
            cwd=execution_root,
            platform=str(spec.get("platform", "local")),
            timeout_seconds=timeout_seconds,
        )
        follow_up_command = str(spec.get("followUp", "")).strip()
        if (
            completed.returncode == 0
            and follow_up_command
            and bool(spec.get("autoRunFollowUp", False))
        ):
            follow_up_completed = _run_shell_action(
                command=follow_up_command,
                cwd=execution_root,
                platform=str(spec.get("platform", "local")),
                timeout_seconds=timeout_seconds,
            )
            follow_up_ran = True
        effective_result = follow_up_completed or completed
        single_stdout = "\n".join(
            text
            for text in [
                (completed.stdout or "").strip(),
                ((follow_up_completed.stdout or "").strip() if follow_up_completed else ""),
            ]
            if text
        )
        single_stderr = "\n".join(
            text
            for text in [
                (completed.stderr or "").strip(),
                ((follow_up_completed.stderr or "").strip() if follow_up_completed else ""),
            ]
            if text
        )
        if single_stdout:
            stdout_parts.append(single_stdout)
        if single_stderr:
            stderr_parts.append(single_stderr)

    if completed is None or effective_result is None:
        record.result = ActionResultEnvelope(
            ok=False,
            error="No executable setup command was configured for this action.",
            duration_ms=round((time.monotonic() - start) * 1000),
            result_summary="Workspace action failed before launch.",
            target_path=proposal.target_path,
        )
        record.executed_at = utc_now_iso()
        return record

    duration_ms = round((time.monotonic() - start) * 1000)
    stdout = "\n".join(part for part in stdout_parts if part)
    stderr = "\n".join(part for part in stderr_parts if part)
    post_onboarding = (
        detect_onboarding_status(root)
        if surface == "setup" and spec.get("commandSurface") in {"setup.install", "setup.repair"}
        else {}
    )
    post_setup = post_onboarding.get("setupHealth", {}) if post_onboarding else {}
    dependency_id = str(spec.get("dependencyId", "")).strip()
    if dependency_id and dependency_id not in dependency_ids:
        dependency_ids.insert(0, dependency_id)
    dependency_state = next(
        (
            item.get("stage", "")
            for item in post_setup.get("dependencies", [])
            if item.get("dependencyId") == dependency_id
        ),
        "",
    )
    dependency_stages = {
        item_dependency_id: next(
            (
                item.get("stage", "")
                for item in post_setup.get("dependencies", [])
                if item.get("dependencyId") == item_dependency_id
            ),
            "",
        )
        for item_dependency_id in dependency_ids
    }
    if dependency_state and dependency_id:
        dependency_stages[dependency_id] = dependency_state
    record.result = ActionResultEnvelope(
        ok=effective_result.returncode == 0,
        exit_code=effective_result.returncode,
        stdout=stdout,
        stderr=stderr,
        duration_ms=duration_ms,
        payload={
            "workspaceActionId": spec.get("actionId", ""),
            "surface": surface,
            "commandSurface": spec.get("commandSurface", ""),
            "followUp": spec.get("followUp", ""),
            "batchCommands": batch_commands,
            "batchResults": batch_results,
            "baseExitCode": completed.returncode,
            "followUpRan": follow_up_ran,
            "followUpExitCode": (
                follow_up_completed.returncode if follow_up_completed is not None else None
            ),
            "dependencyId": dependency_id,
            "dependencyIds": dependency_ids,
            "dependencyStages": dependency_stages,
            "setupHealth": post_setup,
            "onboarding": post_onboarding,
            "dependencyStage": dependency_state,
        },
        target_path=proposal.target_path,
        result_summary=(
            _setup_batch_result_summary(
                label=str(spec.get("label", proposal.title)),
                batch_results=batch_results,
                dependency_stages=dependency_stages,
                effective_exit_code=effective_result.returncode,
            )
            if batch_results
            else _setup_result_summary(
                label=str(spec.get("label", proposal.title)),
                dependency_id=dependency_id,
                dependency_state=dependency_state,
                base_exit_code=completed.returncode,
                follow_up_ran=follow_up_ran,
                follow_up_exit_code=(
                    follow_up_completed.returncode if follow_up_completed is not None else None
                ),
                effective_exit_code=effective_result.returncode,
            )
        ),
    )
    record.executed_at = utc_now_iso()
    return record


def _setup_result_summary(
    *,
    label: str,
    dependency_id: str,
    dependency_state: str,
    base_exit_code: int,
    follow_up_ran: bool,
    follow_up_exit_code: int | None,
    effective_exit_code: int,
) -> str:
    if follow_up_ran and follow_up_exit_code is not None:
        if follow_up_exit_code == 0:
            suffix = " Follow-up setup command succeeded."
        else:
            suffix = (
                f" Follow-up setup command failed with exit code {follow_up_exit_code}."
            )
    else:
        suffix = ""
    if not dependency_state:
        return (
            f"{label} completed with exit code {effective_exit_code}."
            f"{suffix}"
        )
    return (
        f"{label} completed with base exit code {base_exit_code}"
        f"{' and follow-up exit code ' + str(follow_up_exit_code) if follow_up_ran else ''}. "
        f"{dependency_id} is now {dependency_state}.{suffix}"
    )


def _setup_batch_result_summary(
    *,
    label: str,
    batch_results: list[dict],
    dependency_stages: dict[str, str],
    effective_exit_code: int,
) -> str:
    if effective_exit_code != 0:
        failed = next(
            (
                item
                for item in batch_results
                if int(item.get("effectiveExitCode", 0) or 0) != 0
            ),
            (batch_results[-1] if batch_results else {}),
        )
        failed_label = str(failed.get("label", "a setup step")) if failed else "a setup step"
        failed_code = int(failed.get("effectiveExitCode", effective_exit_code) or effective_exit_code)
        return f"{label} stopped during {failed_label} (exit code {failed_code})."
    if dependency_stages:
        pending = [
            dependency_id
            for dependency_id, stage in dependency_stages.items()
            if stage != "healthy"
        ]
        if pending:
            return (
                f"{label} finished, but these services still need attention: "
                f"{', '.join(pending)}."
            )
        return f"{label} finished and all targeted services are healthy."
    return f"{label} completed."


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
        "bridge_status"
        if command_surface in {"bridge.status", "bridge.app_health"}
        else (
            "bridge_verify"
            if command_surface == "bridge.verify"
            else (
                "bridge_activate"
                if command_surface in {"bridge.activate", "bridge.start_app"}
                else (
                    "bridge_sync"
                    if command_surface == "bridge.sync"
                    else (
                        "git_status"
                        if command_surface == "git.inspect"
                        else (
                            "git_commit"
                            if command_surface == "git.commit"
                            else ("test_run" if command_surface == "validate.workspace" else "shell_command")
                        )
                    )
                )
            )
        )
    )
    mutability_class = (
        "read"
        if command_surface in {
            "git.inspect",
            "setup.verify",
            "bridge.status",
            "bridge.verify",
            "bridge.app_health",
        }
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


def _configure_telegram_destination(root: Path) -> dict[str, object]:
    destination, source = _discover_telegram_destination(root)
    if not destination:
        return {
            "ok": False,
            "destination": "",
            "source": "",
            "summary": "Telegram setup needs a destination before escalation can be enabled.",
            "error": (
                "No Telegram destination found. Set FLUXIO_TELEGRAM_DESTINATION or TELEGRAM_CHAT_ID, "
                "then rerun One-click Telegram setup."
            ),
        }
    _persist_telegram_destination(root, destination=destination, source=source)
    updated_missions = _backfill_mission_telegram_destinations(root, destination)
    return {
        "ok": True,
        "destination": destination,
        "source": source,
        "summary": (
            "Telegram escalation destination is configured."
            if updated_missions == 0
            else f"Telegram escalation destination is configured and applied to {updated_missions} mission(s)."
        ),
        "error": "",
    }


def _discover_telegram_destination(root: Path) -> tuple[str, str]:
    existing = load_telegram_destination(root)
    if existing:
        return existing, "settings"
    for key in TELEGRAM_ENV_KEYS:
        value = _normalize_telegram_destination(os.environ.get(key))
        if value:
            return value, f"env:{key}"
    openclaw_destination, openclaw_source = _discover_openclaw_telegram_destination()
    if openclaw_destination:
        return openclaw_destination, openclaw_source
    missions_path = root / ".agent_control" / "missions.json"
    missions_payload = _load_json_list(missions_path)
    for mission in missions_payload:
        destination = _normalize_telegram_destination(
            mission.get("escalation_policy", {}).get("destination")
        )
        if destination:
            return destination, "missions"
    return "", ""


def _discover_openclaw_telegram_destination() -> tuple[str, str]:
    config_candidates: list[Path] = []
    seen_paths: set[str] = set()

    explicit_config = str(os.environ.get("OPENCLAW_CONFIG_PATH", "")).strip()
    if explicit_config:
        candidate = Path(explicit_config).expanduser()
        config_candidates.append(candidate)
        seen_paths.add(str(candidate.resolve(strict=False)))

    state_dirs: list[Path] = []
    explicit_state = str(os.environ.get("OPENCLAW_STATE_DIR", "")).strip()
    if explicit_state:
        state_dirs.append(Path(explicit_state).expanduser())
    state_dirs.append(Path.home() / ".openclaw")

    for state_dir in state_dirs:
        env_destination = _read_env_destination(state_dir / ".env")
        if env_destination:
            return env_destination, f"openclaw-env:{state_dir}"
        candidate = state_dir / "openclaw.json"
        resolved = str(candidate.resolve(strict=False))
        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)
        config_candidates.append(candidate)

    for config_path in config_candidates:
        destination = _read_openclaw_destination(config_path)
        if destination:
            return destination, f"openclaw-config:{config_path}"
    return "", ""


def _read_env_destination(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() not in TELEGRAM_ENV_KEYS:
            continue
        normalized = _normalize_telegram_destination(value)
        if normalized:
            return normalized
    return ""


def _read_openclaw_destination(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""

    tools = payload.get("tools", {})
    allow_from = tools.get("elevated", {}).get("allowFrom", {}) if isinstance(tools, dict) else {}
    telegram_allow = allow_from.get("telegram") if isinstance(allow_from, dict) else None
    if isinstance(telegram_allow, list):
        for entry in telegram_allow:
            normalized = _normalize_telegram_destination(entry)
            if normalized:
                return normalized

    telegram_config = payload.get("telegram", {})
    if isinstance(telegram_config, dict):
        for key in ("destination", "chatId", "chat_id", "target", "userId", "user_id"):
            normalized = _normalize_telegram_destination(telegram_config.get(key))
            if normalized:
                return normalized

    channels = payload.get("channels", {})
    if isinstance(channels, dict):
        telegram_channel = channels.get("telegram", {})
        if isinstance(telegram_channel, dict):
            for key in ("destination", "chatId", "chat_id", "target"):
                normalized = _normalize_telegram_destination(telegram_channel.get(key))
                if normalized:
                    return normalized

    return ""


def _normalize_telegram_destination(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        text = str(int(value))
    else:
        text = str(value).strip()
    if not text:
        return ""
    if text.startswith(("'", '"')) and text.endswith(("'", '"')) and len(text) >= 2:
        text = text[1:-1].strip()
    return text


def _persist_telegram_destination(root: Path, *, destination: str, source: str) -> None:
    control_dir = root / ".agent_control"
    control_dir.mkdir(parents=True, exist_ok=True)
    settings_path = control_dir / "telegram_settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "destination": destination,
                "source": source,
                "updated_at": utc_now_iso(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _backfill_mission_telegram_destinations(root: Path, destination: str) -> int:
    missions_path = root / ".agent_control" / "missions.json"
    missions = _load_json_list(missions_path)
    if not missions:
        return 0
    updated_count = 0
    changed = False
    for mission in missions:
        policy = mission.get("escalation_policy", {})
        if not isinstance(policy, dict):
            policy = {}
        current_destination = str(policy.get("destination", "")).strip()
        if current_destination:
            continue
        policy["channel"] = str(policy.get("channel", "telegram") or "telegram")
        policy["enabled"] = True
        policy["destination"] = destination
        if not policy.get("triggers"):
            policy["triggers"] = [
                "blocked approval",
                "missing setup step",
                "verification failure",
                "completion summary",
            ]
        mission["escalation_policy"] = policy
        updated_count += 1
        changed = True
    if changed:
        missions_path.parent.mkdir(parents=True, exist_ok=True)
        missions_path.write_text(json.dumps(missions, indent=2), encoding="utf-8")
    return updated_count


def _load_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _probe_health_url(url: str) -> dict:
    if not url:
        return {}
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            body = response.read().decode("utf-8", errors="replace")
    except (OSError, urllib.error.URLError, TimeoutError):
        return {}
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return {"status": "responded", "body": body[:500]}
    return payload if isinstance(payload, dict) else {"status": "responded", "body": body[:500]}


def _launch_background_app_command(
    *,
    root: Path,
    app_id: str,
    command: str,
    app_root: str,
) -> dict[str, object]:
    if not command:
        return {"ok": False, "error": "No start command was configured."}
    cwd = Path(app_root).resolve() if app_root else root
    if app_root and not cwd.exists():
        return {"ok": False, "error": f"App root does not exist: {cwd}"}
    log_dir = root / ".agent_control" / "bridge_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    safe_app_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in app_id)
    log_path = log_dir / f"{safe_app_id}-{int(time.time())}.log"
    stdout_handle = log_path.open("a", encoding="utf-8")
    stderr_handle = stdout_handle
    try:
        process = subprocess.Popen(  # noqa: S603
            command,
            shell=True,
            cwd=str(cwd),
            stdout=stdout_handle,
            stderr=stderr_handle,
            stdin=subprocess.DEVNULL,
            text=True,
            **hidden_windows_subprocess_kwargs(),
        )
    except OSError as exc:
        stdout_handle.close()
        return {"ok": False, "error": str(exc), "logPath": str(log_path)}
    stdout_handle.close()
    return {"ok": True, "pid": process.pid, "logPath": str(log_path)}


def _process_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    proc_stat = Path(f"/proc/{pid}/stat")
    if proc_stat.exists():
        try:
            stat_text = proc_stat.read_text(encoding="utf-8", errors="replace")
        except OSError:
            stat_text = ""
        parts = stat_text.split()
        if len(parts) >= 3 and parts[2] == "Z":
            return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _tail_text(path: Path, *, limit: int = 900) -> str:
    if not path or not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[-limit:].strip()


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
            **hidden_windows_subprocess_kwargs(),
        )
    return subprocess.run(  # noqa: S603
        command,
        shell=True,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
        **hidden_windows_subprocess_kwargs(),
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
    if command_surface in {"bridge.activate", "bridge.verify", "bridge.start_app"}:
        return 120
    if command_surface.startswith("bridge."):
        return 15
    return 60


def _quote_shell_path(path: str) -> str:
    return f'"{path.replace(chr(34), chr(34) + chr(34))}"'


def _quote_shell_arg(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) + chr(34))}"'


def _refresh_setup_result_payload(
    *,
    store: ControlRoomStore,
    root: Path,
    history_key: str,
    spec: dict,
    record: dict,
) -> dict:
    onboarding = detect_onboarding_status(root, force=True)
    setup_health = onboarding.get("setupHealth", {})
    dependency_id = spec.get("dependencyId", "")
    missing = setup_health.get("missingDependencies", [])
    payload = dict(record.get("result", {}).get("payload", {}))
    dependency_ids = [
        str(item)
        for item in payload.get("dependencyIds", [])
        if str(item).strip()
    ]
    if dependency_id and dependency_id not in dependency_ids:
        dependency_ids.insert(0, dependency_id)
    dependency_stages = {
        item_dependency_id: next(
            (
                item.get("stage", "")
                for item in setup_health.get("dependencies", [])
                if item.get("dependencyId") == item_dependency_id
            ),
            "",
        )
        for item_dependency_id in dependency_ids
    }
    dependency_stage = dependency_stages.get(str(dependency_id), "")
    if not dependency_stage and len(dependency_stages) == 1:
        dependency_stage = next(iter(dependency_stages.values()))
    payload["setupHealth"] = setup_health
    payload["onboarding"] = onboarding
    payload["dependencyStage"] = dependency_stage
    payload["dependencyIds"] = dependency_ids
    payload["dependencyStages"] = dependency_stages
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
        result_payload = record.get("result", {}).get("payload", {})
        if result_payload.get("batchResults"):
            record["result"]["result_summary"] = _setup_batch_result_summary(
                label=str(spec.get("label", "Setup action")),
                batch_results=list(result_payload.get("batchResults", [])),
                dependency_stages=dependency_stages,
                effective_exit_code=int(record["result"].get("exit_code", 0) or 0),
            )
        else:
            record["result"]["result_summary"] = _setup_result_summary(
                label=str(spec.get("label", "Setup action")),
                dependency_id=str(dependency_id),
                dependency_state=str(dependency_stage),
                base_exit_code=int(result_payload.get("baseExitCode", record["result"].get("exit_code", 0)) or 0),
                follow_up_ran=bool(result_payload.get("followUpRan", False)),
                follow_up_exit_code=(
                    int(result_payload["followUpExitCode"])
                    if result_payload.get("followUpExitCode") is not None
                    else None
                ),
                effective_exit_code=int(record["result"].get("exit_code", 0) or 0),
            )
    histories = store.load_workspace_actions()
    entries = list(histories.get(history_key, []))
    if entries:
        record_action_id = str(record.get("action_id", "")).strip()
        replaced = False
        if record_action_id:
            for index in range(len(entries) - 1, -1, -1):
                if str(entries[index].get("action_id", "")).strip() == record_action_id:
                    entries[index] = record
                    replaced = True
                    break
        if not replaced:
            entries[-1] = record
        histories[history_key] = entries
        store.workspace_actions_path.write_text(
            json.dumps(histories, indent=2),
            encoding="utf-8",
        )
    return record
