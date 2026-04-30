from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict
from pathlib import Path

from .models import (
    AppActionHook,
    AppBridgeHandshake,
    AppCapabilityManifest,
    AppContextSurface,
    AppTaskDescriptor,
    CapabilityGrant,
    ConnectedAppSession,
    utc_now_iso,
)

SCHEMA_VERSION = "fluxio.app-capability/v0-draft"
BRIDGE_VERSION = "fluxio.bridge/v0-draft"
FOLLOW_ON_APP_IDS = {"solantir-terminal"}
BRIDGE_HTTP_TIMEOUT_SECONDS = 0.35


def manifest_schema() -> dict:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "required": [
            "manifest_id",
            "schema_version",
            "app_id",
            "name",
            "description",
            "bridge",
            "auth",
            "permissions",
            "tasks",
            "context_surfaces",
            "action_hooks",
        ],
        "bridgeFields": ["transport", "endpoint", "healthcheck", "event_stream"],
        "authFields": ["mode", "scopes"],
        "taskFields": ["task_id", "label", "description"],
        "contextSurfaceFields": ["surface_id", "label", "description", "access"],
        "actionHookFields": ["hook_id", "label", "description", "mutability"],
    }


def validate_manifest_payload(payload: dict) -> list[str]:
    errors: list[str] = []
    schema = manifest_schema()
    for key in schema["required"]:
        if key not in payload:
            errors.append(f"Missing manifest field: {key}")

    bridge = payload.get("bridge", {})
    for key in schema["bridgeFields"]:
        if key not in bridge:
            errors.append(f"Missing bridge field: {key}")

    auth = payload.get("auth", {})
    for key in schema["authFields"]:
        if key not in auth:
            errors.append(f"Missing auth field: {key}")

    for collection_name, required_fields in (
        ("tasks", schema["taskFields"]),
        ("context_surfaces", schema["contextSurfaceFields"]),
        ("action_hooks", schema["actionHookFields"]),
    ):
        collection = payload.get(collection_name, [])
        if not isinstance(collection, list) or not collection:
            errors.append(f"{collection_name} must contain at least one entry")
            continue
        for index, item in enumerate(collection):
            for field_name in required_fields:
                if field_name not in item:
                    errors.append(f"{collection_name}[{index}] is missing {field_name}")
    return errors


def validate_handshake_payload(payload: dict) -> list[str]:
    errors: list[str] = []
    for key in ("app_id", "bridge_version", "session_id", "transport"):
        if key not in payload:
            errors.append(f"Missing handshake field: {key}")
    return errors


def load_mock_manifests(root: Path) -> list[AppCapabilityManifest]:
    config_path = root / "config" / "connected_apps.json"
    payload = _load_manifest_payloads(config_path)
    return [_to_manifest(item) for item in payload]


def build_connected_apps_snapshot(root: Path) -> dict:
    manifests = load_mock_manifests(root)
    state = _load_session_state(root)
    connected_sessions: list[ConnectedAppSession] = []
    handshakes: list[dict] = []

    for manifest in manifests:
        if manifest.app_id in FOLLOW_ON_APP_IDS:
            session = _build_follow_on_session(root, manifest)
            connected_sessions.append(session)
            handshakes.append(
                asdict(
                    AppBridgeHandshake(
                        app_id=manifest.app_id,
                        bridge_version=BRIDGE_VERSION,
                        session_id=session.session_id,
                        transport=manifest.bridge.get("transport", "ipc"),
                        capabilities=manifest.permissions,
                        auth_mode=manifest.auth.get("mode", "local_session"),
                        requires_user_present=bool(
                            manifest.ui_hints.get("requiresUserPresent", True)
                        ),
                    )
                )
            )
            continue

        live_session, handshake = _build_live_session(
            root=root,
            manifest=manifest,
            previous_state=state.get(manifest.app_id, {}),
        )
        connected_sessions.append(live_session)
        handshakes.append(handshake)
        state[manifest.app_id] = _persistable_session_state(live_session)

    if state:
        _save_session_state(root, state)

    connected_names = [
        session.app_name for session in connected_sessions if session.status == "connected"
    ]
    recommendation = (
        f"{', '.join(connected_names)} bridge session(s) are live. Solantir remains in manifest-only follow-on review."
        if connected_names
        else "Connected apps are loaded, but live bridge sessions are not healthy yet."
    )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "bridgeVersion": BRIDGE_VERSION,
        "manifestSchema": manifest_schema(),
        "bridgeHandshake": handshakes[0]
        if handshakes
        else asdict(
            AppBridgeHandshake(
                app_id="mock.app",
                bridge_version=BRIDGE_VERSION,
                session_id=f"handshake_{uuid.uuid4().hex[:8]}",
                transport="http",
            )
        ),
        "bridgeHandshakes": handshakes,
        "phases": [
            "Phase A: manifest and policy contract",
            "Phase B: live reference integrations for OratioViva plus storage and cloud bridges",
            "Phase C: Solantir follow-on after the bridge standard is proven",
        ],
        "discoveredApps": [asdict(item) for item in manifests],
        "connectedSessions": [asdict(item) for item in connected_sessions],
        "recommendation": recommendation,
    }


def _build_live_session(
    *,
    root: Path,
    manifest: AppCapabilityManifest,
    previous_state: dict,
) -> tuple[ConnectedAppSession, dict]:
    app_root = _resolve_app_root(root, manifest)
    grants = _build_grants(manifest)
    session_id = previous_state.get("session_id") or f"bridge_{manifest.app_id}"
    handshake = AppBridgeHandshake(
        app_id=manifest.app_id,
        bridge_version=BRIDGE_VERSION,
        session_id=session_id,
        transport=manifest.bridge.get("transport", "http"),
        capabilities=manifest.permissions,
        auth_mode=manifest.auth.get("mode", "local_token"),
        requires_user_present=bool(manifest.ui_hints.get("requiresUserPresent", False)),
    )

    if manifest.app_id == "cloud-drive-sync":
        return (
            _build_cloud_drive_session(
                root=root,
                manifest=manifest,
                previous_state=previous_state,
                grants=grants,
            ),
            asdict(handshake),
        )

    if manifest.app_id == "synology-fast-sync":
        return (
            _build_synology_fast_sync_session(
                manifest=manifest,
                app_root=app_root or root,
                previous_state=previous_state,
                grants=grants,
            ),
            asdict(handshake),
        )

    if app_root is None or not app_root.exists():
        session = ConnectedAppSession(
            session_id=session_id,
            app_id=manifest.app_id,
            app_name=manifest.name,
            status="missing",
            bridge_health="missing",
            manifest_id=manifest.manifest_id,
            granted_capabilities=grants,
            handshake_status="bridge_missing",
            bridge_transport=manifest.bridge.get("transport", ""),
            bridge_endpoint=manifest.bridge.get("endpoint", ""),
            notes=[
                "The manifest loaded, but the local sibling app repository was not found.",
                "Keep this integration in review until the app root is available on disk.",
            ],
        )
        return session, asdict(handshake)

    context_preview = _context_preview_for_app(manifest.app_id, app_root, manifest)
    task_history = _task_history_for_app(
        manifest=manifest,
        app_root=app_root,
        previous_task_history=previous_state.get("task_history", []),
    )
    latest_task_result = task_history[-1] if task_history else {}
    approval_callback = _approval_callback_for_app(manifest.app_id, app_root)
    status = "connected"
    bridge_health = "healthy"
    active_tasks = [
        item.get("label", item.get("taskId", "task"))
        for item in task_history
        if item.get("status") in {"queued", "running"}
    ]
    notes = [
        f"Handshake resolved against {app_root}.",
        "Capability grants stay scoped to the app manifest and bridge contract.",
    ]
    if approval_callback.get("available"):
        notes.append(approval_callback.get("detail", "Approval callback is available."))

    session = ConnectedAppSession(
        session_id=session_id,
        app_id=manifest.app_id,
        app_name=manifest.name,
        status=status,
        bridge_health=bridge_health,
        manifest_id=manifest.manifest_id,
        granted_capabilities=grants,
        active_tasks=active_tasks,
        last_seen_at=utc_now_iso(),
        notes=notes,
        handshake_status="connected",
        bridge_transport=manifest.bridge.get("transport", ""),
        bridge_endpoint=manifest.bridge.get("endpoint", ""),
        app_root=str(app_root),
        context_preview=context_preview,
        task_history=task_history[-4:],
        latest_task_result=latest_task_result,
        approval_callback=approval_callback,
    )
    return session, asdict(handshake)


def _build_synology_fast_sync_session(
    *,
    manifest: AppCapabilityManifest,
    app_root: Path,
    previous_state: dict,
    grants: list[CapabilityGrant],
) -> ConnectedAppSession:
    bridge_endpoint = manifest.bridge.get("endpoint", "http://127.0.0.1:8765")
    public_endpoint = str(manifest.bridge.get("public_endpoint") or bridge_endpoint).rstrip("/")
    status_payload = _read_bridge_json(bridge_endpoint, "/api/status")
    job_payload = _read_bridge_json(bridge_endpoint, "/api/job") if status_payload else {}
    bridge_online = bool(status_payload)
    bridge_plan = _synology_bridge_plan(manifest, status_payload, job_payload)

    context_preview = _synology_context_preview(
        manifest=manifest,
        app_root=app_root,
        status_payload=status_payload,
        job_payload=job_payload,
        bridge_plan=bridge_plan,
    )
    task_history = _synology_task_history(
        manifest=manifest,
        status_payload=status_payload,
        job_payload=job_payload,
        bridge_plan=bridge_plan,
        previous_task_history=previous_state.get("task_history", []),
    )
    latest_task_result = task_history[-1] if task_history else {}
    app_root_exists = bool(app_root.exists())
    notes = [
        (
            "Cowork Synology Fast Sync files are present and registered as a local app bridge."
            if app_root_exists
            else "Synology bridge metadata is loaded even though the mapped app root is not available on this host."
        ),
        "Use the Fast Sync web surface for large project upload/download output.",
    ]
    if bridge_online:
        notes.insert(0, str(status_payload.get("message") or "Synology Fast Sync bridge is online."))
    else:
        notes.insert(
            0,
            "Synology Fast Sync UI is not responding on the configured local endpoint.",
        )

    return ConnectedAppSession(
        session_id=previous_state.get("session_id") or f"bridge_{manifest.app_id}",
        app_id=manifest.app_id,
        app_name=manifest.name,
        status="connected" if bridge_online else "available",
        bridge_health="healthy" if bridge_online else "offline",
        manifest_id=manifest.manifest_id,
        granted_capabilities=grants,
        active_tasks=[
            "Fast Sync copy"
            for state in [job_payload.get("state")]
            if state in {"preparing", "running"}
        ],
        last_seen_at=utc_now_iso(),
        notes=notes,
        handshake_status="connected" if bridge_online else "endpoint_offline",
        bridge_transport=manifest.bridge.get("transport", "http"),
        bridge_endpoint=bridge_endpoint,
        app_root=str(app_root),
        context_preview=context_preview,
        task_history=task_history[-4:],
        latest_task_result=latest_task_result,
        approval_callback={
            "available": True,
            "channel": "mobile_web",
            "detail": (
                "Fast Sync output is browser-readable; bind the service to a LAN or Tailscale "
                "address when you want the phone to operate the same bridge."
            ),
        },
        ui_hints={
            **manifest.ui_hints,
            "bridgeRole": "nas_storage",
            "sourceRoot": bridge_plan.get("sourceRoot", ""),
            "targetRoot": bridge_plan.get("targetRoot", ""),
            "selectedMode": bridge_plan.get("selectedMode", ""),
            "selectedHost": bridge_plan.get("selectedHost", ""),
            "controlProtocol": bridge_plan.get("controlProtocol", ""),
            "controlPort": bridge_plan.get("controlPort", 0),
            "requestedSshPort": bridge_plan.get("requestedSshPort", 0),
            "observedSshPort": bridge_plan.get("observedSshPort", 0),
            "sshPortStatus": bridge_plan.get("sshPortStatus", ""),
            "sshUser": bridge_plan.get("sshUser", ""),
            "remoteProjectRoot": bridge_plan.get("remoteProjectRoot", ""),
            "safeDirections": bridge_plan.get("safeDirections", []),
            "activeDirection": bridge_plan.get("activeDirection", ""),
            "targetReady": bridge_plan.get("targetReady", False),
            "activationRequired": bridge_plan.get("activationRequired", False),
            "activationProject": bridge_plan.get("activationProject", ""),
            "activationHint": bridge_plan.get("activationHint", ""),
            "publicEndpoint": public_endpoint,
            "preferredTransport": manifest.bridge.get("preferred_transport", ""),
            "httpsReady": public_endpoint.startswith("https://"),
            "requiresApprovalForWrite": bool(
                bridge_plan.get("requiresApprovalForWrite", True)
            ),
        },
    )


def _build_cloud_drive_session(
    *,
    root: Path,
    manifest: AppCapabilityManifest,
    previous_state: dict,
    grants: list[CapabilityGrant],
) -> ConnectedAppSession:
    bridge_plan = _cloud_drive_bridge_plan(root, manifest)
    context_preview = _cloud_drive_context_preview(manifest, bridge_plan)
    task_history = _cloud_drive_task_history(
        manifest=manifest,
        bridge_plan=bridge_plan,
        previous_task_history=previous_state.get("task_history", []),
    )
    latest_task_result = task_history[-1] if task_history else {}
    connected = bool(bridge_plan.get("mountedRoots") or bridge_plan.get("googleLoginReady"))
    notes = [
        "Cloud Drive Bridge is registered as a storage bridge for Google Drive and mounted folders.",
        "Writes stay approval-gated so cloud and NAS copies cannot be changed silently.",
    ]
    if bridge_plan.get("googleLoginReady"):
        notes.insert(0, "Google Drive login state is present on this machine.")
    elif bridge_plan.get("mountedRoots"):
        notes.insert(0, "Mounted cloud-drive folders were detected on this machine.")
    else:
        notes.insert(0, "Cloud storage is ready to configure, but no Google login or mounted folder is detected yet.")

    return ConnectedAppSession(
        session_id=previous_state.get("session_id") or f"bridge_{manifest.app_id}",
        app_id=manifest.app_id,
        app_name=manifest.name,
        status="connected" if connected else "available",
        bridge_health="healthy" if connected else "configure",
        manifest_id=manifest.manifest_id,
        granted_capabilities=grants,
        active_tasks=[],
        last_seen_at=utc_now_iso(),
        notes=notes,
        handshake_status="connected" if connected else "configuration_pending",
        bridge_transport=manifest.bridge.get("transport", "local_mount_oauth"),
        bridge_endpoint=manifest.bridge.get("endpoint", "local://cloud-drive"),
        app_root=str(root),
        context_preview=context_preview,
        task_history=task_history[-4:],
        latest_task_result=latest_task_result,
        approval_callback={
            "available": True,
            "channel": "desktop_oauth",
            "detail": (
                "Google login should be launched by the desktop credential service; mounted "
                "folders can be used without sending raw cloud tokens to the browser."
            ),
        },
        ui_hints={
            **manifest.ui_hints,
            "bridgeRole": "cloud_storage",
            "sourceRoot": bridge_plan.get("sourceRoot", ""),
            "targetRoot": bridge_plan.get("primaryRoot", ""),
            "selectedMode": bridge_plan.get("selectedMode", ""),
            "selectedHost": bridge_plan.get("selectedProvider", ""),
            "safeDirections": bridge_plan.get("safeDirections", []),
            "activeDirection": bridge_plan.get("activeDirection", ""),
            "targetReady": bool(bridge_plan.get("targetReady")),
            "requiresApprovalForWrite": True,
            "mountedRoots": bridge_plan.get("mountedRoots", []),
            "googleLoginReady": bool(bridge_plan.get("googleLoginReady")),
        },
    )


def _build_follow_on_session(root: Path, manifest: AppCapabilityManifest) -> ConnectedAppSession:
    app_root = _resolve_app_root(root, manifest)
    return ConnectedAppSession(
        session_id=f"bridge_{manifest.app_id}",
        app_id=manifest.app_id,
        app_name=manifest.name,
        status="follow_on_manifest",
        bridge_health="manifest_only",
        manifest_id=manifest.manifest_id,
        granted_capabilities=_build_grants(manifest),
        last_seen_at=utc_now_iso(),
        notes=[
            "Kept in the Bridge Lab design set for 1.0 review.",
            "Full handshake and task execution are intentionally deferred until after the reference bridge path is proven.",
        ],
        handshake_status="manifest_loaded",
        bridge_transport=manifest.bridge.get("transport", ""),
        bridge_endpoint=manifest.bridge.get("endpoint", ""),
        app_root=str(app_root) if app_root else "",
        context_preview=[],
        task_history=[],
        latest_task_result={
            "taskId": manifest.tasks[0].task_id if manifest.tasks else "",
            "label": manifest.tasks[0].label if manifest.tasks else "Follow-on task",
            "status": "deferred",
            "sourceKind": "connected_app",
            "resultSummary": "Solantir stays in follow-on review for the first post-1.0 bridge activation.",
            "createdAt": utc_now_iso(),
            "completedAt": utc_now_iso(),
            "approvalStatus": "deferred",
            "payload": {
                "followOnSlice": "watchlist read plus approval-aware terminal action",
            },
        },
        approval_callback={
            "available": True,
            "channel": "terminal",
            "detail": "Approval-aware terminal callback is part of the follow-on slice definition.",
        },
    )


def _context_preview_for_app(
    app_id: str,
    app_root: Path,
    manifest: AppCapabilityManifest,
) -> list[dict]:
    if app_id == "oratio-viva":
        worker_files = sorted(
            path.stem.replace("_worker", "")
            for path in (app_root / "backend").glob("*worker.py")
        )
        package_name, package_version = _read_package_name_version(
            app_root / "frontend" / "package.json"
        )
        return [
            {
                "surfaceId": "voice-catalog",
                "label": "Voice Catalog",
                "summary": (
                    f"{len(worker_files)} voice engines detected"
                    + (f" in {package_name} {package_version}" if package_name else "")
                ),
                "items": worker_files[:6],
                "access": manifest.context_surfaces[0].access if manifest.context_surfaces else "read",
            }
        ]
    return []


def _task_history_for_app(
    *,
    manifest: AppCapabilityManifest,
    app_root: Path,
    previous_task_history: list[dict],
) -> list[dict]:
    if previous_task_history:
        return list(previous_task_history)

    if manifest.app_id == "oratio-viva":
        workers = sorted(
            path.stem.replace("_worker", "")
            for path in (app_root / "backend").glob("*worker.py")
        )
        selected = workers[0] if workers else "default"
        return [
            {
                "taskId": manifest.tasks[0].task_id,
                "label": manifest.tasks[0].label,
                "status": "completed",
                "sourceKind": "connected_app",
                "resultSummary": f"Queued and completed a local preview bridge task for the {selected} voice engine.",
                "createdAt": utc_now_iso(),
                "completedAt": utc_now_iso(),
                "approvalStatus": "not_required",
                "payload": {
                    "selectedEngine": selected,
                    "workspaceRoot": str(app_root),
                    "surfaceRead": "voice-catalog",
                    "previewPrompt": "Fluxio bridge preview",
                },
            }
        ]

    return []


def _synology_context_preview(
    *,
    manifest: AppCapabilityManifest,
    app_root: Path,
    status_payload: dict,
    job_payload: dict,
    bridge_plan: dict,
) -> list[dict]:
    surface = manifest.context_surfaces[0] if manifest.context_surfaces else None
    selected_mode = str(bridge_plan.get("selectedMode") or "offline")
    selected_host = str(bridge_plan.get("selectedHost") or "")
    status_items = [
        f"Mode: {selected_mode}",
        f"Host: {selected_host or 'not selected'}",
        f"Control: {bridge_plan.get('controlProtocol') or 'not configured'}:{bridge_plan.get('controlPort') or '-'}",
        f"Port note: {bridge_plan.get('sshPortStatus') or 'operator configured'}",
        f"Remote user: {bridge_plan.get('sshUser') or 'not configured'}",
        f"Computer: {bridge_plan.get('sourceRoot') or 'not mapped'}",
        f"NAS: {bridge_plan.get('targetRoot') or 'not mapped'}",
        f"Remote root: {bridge_plan.get('remoteProjectRoot') or 'not configured'}",
        f"Active transfer: {bridge_plan.get('activeDirection') or 'none'}",
        f"Queued writes need approval: {'yes' if bridge_plan.get('requiresApprovalForWrite') else 'no'}",
    ]
    if job_payload.get("currentPath"):
        status_items.append(f"Current file: {job_payload.get('currentPath')}")
    if bridge_plan.get("activationRequired"):
        status_items.append(str(bridge_plan.get("activationHint") or "Activate the storage project before mapping."))

    return [
        {
            "surfaceId": surface.surface_id if surface else "sync-status",
            "label": surface.label if surface else "Sync Status",
            "summary": (
                str(status_payload.get("message"))
                if status_payload
                else "Cowork Fast Sync backend is installed but the local web bridge is offline."
            ),
            "items": status_items
            or [
                str(app_root / "synology-fast-ui.py"),
                str(app_root / "synology_fast_ui"),
            ],
            "access": surface.access if surface else "read",
        }
    ]


def _synology_task_history(
    *,
    manifest: AppCapabilityManifest,
    status_payload: dict,
    job_payload: dict,
    bridge_plan: dict,
    previous_task_history: list[dict],
) -> list[dict]:
    task = manifest.tasks[0] if manifest.tasks else None
    previous_created_at = ""
    if previous_task_history:
        previous_created_at = str(previous_task_history[-1].get("createdAt", ""))
    job_state = str(job_payload.get("state") or "offline")
    direction = str(job_payload.get("direction") or "")
    completed_files = _safe_int(job_payload.get("completedFiles"))
    remaining_files = _safe_int(job_payload.get("remainingFiles"))
    result_summary = (
        f"Fast Sync job is {job_state}."
        if not status_payload
        else (
            f"{bridge_plan.get('selectedMode') or 'offline'} path selected; "
            f"{completed_files} file(s) completed and {remaining_files} remaining."
        )
    )
    if direction:
        result_summary = f"{direction.title()} output: {result_summary}"

    return [
        {
            "taskId": task.task_id if task else "monitor-fast-sync",
            "label": task.label if task else "Monitor Fast Sync output",
            "status": "running" if job_state in {"preparing", "running"} else "completed",
            "sourceKind": "connected_app",
            "resultSummary": result_summary,
            "createdAt": previous_created_at or utc_now_iso(),
            "completedAt": "" if job_state in {"preparing", "running"} else utc_now_iso(),
            "approvalStatus": "not_required",
            "payload": {
                "targetReady": bool(bridge_plan.get("targetReady")),
                "targetRoot": str(bridge_plan.get("targetRoot") or ""),
                "sourceRoot": str(bridge_plan.get("sourceRoot") or ""),
                "selectedMode": str(bridge_plan.get("selectedMode") or ""),
                "selectedHost": str(bridge_plan.get("selectedHost") or ""),
                "controlProtocol": str(bridge_plan.get("controlProtocol") or ""),
                "controlPort": _safe_int(bridge_plan.get("controlPort")),
                "requestedSshPort": _safe_int(bridge_plan.get("requestedSshPort")),
                "observedSshPort": _safe_int(bridge_plan.get("observedSshPort")),
                "sshPortStatus": str(bridge_plan.get("sshPortStatus") or ""),
                "sshUser": str(bridge_plan.get("sshUser") or ""),
                "remoteProjectRoot": str(bridge_plan.get("remoteProjectRoot") or ""),
                "safeDirections": list(bridge_plan.get("safeDirections", [])),
                "activeDirection": str(bridge_plan.get("activeDirection") or ""),
                "requiresApprovalForWrite": bool(bridge_plan.get("requiresApprovalForWrite")),
                "activationRequired": bool(bridge_plan.get("activationRequired")),
                "activationProject": str(bridge_plan.get("activationProject") or ""),
                "activationHint": str(bridge_plan.get("activationHint") or ""),
                "activationCommand": str(bridge_plan.get("activationCommand") or ""),
                "bridgePlan": bridge_plan,
                "currentPath": str(job_payload.get("currentPath") or ""),
            },
        }
    ]


def _cloud_drive_context_preview(manifest: AppCapabilityManifest, bridge_plan: dict) -> list[dict]:
    surface = manifest.context_surfaces[0] if manifest.context_surfaces else None
    mounted_roots = list(bridge_plan.get("mountedRoots", []))
    items = [
        f"Provider: {bridge_plan.get('selectedProvider') or 'not selected'}",
        f"Computer: {bridge_plan.get('sourceRoot') or 'not mapped'}",
        f"Primary cloud folder: {bridge_plan.get('primaryRoot') or 'not mounted'}",
        f"Google login: {'ready' if bridge_plan.get('googleLoginReady') else 'not configured'}",
        f"Queued writes need approval: {'yes' if bridge_plan.get('requiresApprovalForWrite') else 'no'}",
    ]
    items.extend(str(item.get("root", "")) for item in mounted_roots[:4] if item.get("root"))
    return [
        {
            "surfaceId": surface.surface_id if surface else "cloud-drive-status",
            "label": surface.label if surface else "Cloud Drive Status",
            "summary": bridge_plan.get("summary", ""),
            "items": items,
            "access": surface.access if surface else "read",
        }
    ]


def _cloud_drive_task_history(
    *,
    manifest: AppCapabilityManifest,
    bridge_plan: dict,
    previous_task_history: list[dict],
) -> list[dict]:
    task = manifest.tasks[0] if manifest.tasks else None
    previous_created_at = ""
    if previous_task_history:
        previous_created_at = str(previous_task_history[-1].get("createdAt", ""))
    return [
        {
            "taskId": task.task_id if task else "monitor-cloud-drive",
            "label": task.label if task else "Monitor Cloud Drive bridge",
            "status": "completed",
            "sourceKind": "connected_app",
            "resultSummary": bridge_plan.get("summary", "Cloud-drive bridge state was refreshed."),
            "createdAt": previous_created_at or utc_now_iso(),
            "completedAt": utc_now_iso(),
            "approvalStatus": "not_required",
            "payload": {
                "targetReady": bool(bridge_plan.get("targetReady")),
                "targetRoot": str(bridge_plan.get("primaryRoot") or ""),
                "sourceRoot": str(bridge_plan.get("sourceRoot") or ""),
                "selectedMode": str(bridge_plan.get("selectedMode") or ""),
                "selectedHost": str(bridge_plan.get("selectedProvider") or ""),
                "safeDirections": list(bridge_plan.get("safeDirections", [])),
                "activeDirection": str(bridge_plan.get("activeDirection") or ""),
                "requiresApprovalForWrite": bool(bridge_plan.get("requiresApprovalForWrite")),
                "bridgePlan": bridge_plan,
                "cloudProviders": list(bridge_plan.get("providers", [])),
                "mountedRoots": list(bridge_plan.get("mountedRoots", [])),
                "googleLoginReady": bool(bridge_plan.get("googleLoginReady")),
            },
        }
    ]


def _cloud_drive_bridge_plan(root: Path, manifest: AppCapabilityManifest) -> dict:
    source_root = str(
        manifest.bridge.get("source_root")
        or manifest.bridge.get("workspace_root")
        or root.resolve()
    )
    mounted_roots = _discover_cloud_drive_roots()
    google_login_ready = _google_drive_oauth_present(root)
    primary = mounted_roots[0] if mounted_roots else {}
    selected_provider = str(primary.get("provider") or manifest.ui_hints.get("primaryProvider") or "google-drive")
    primary_root = str(primary.get("root") or "")
    target_ready = bool(primary_root or google_login_ready)
    safe_directions = ["upload", "download"] if target_ready else []
    summary = (
        f"{selected_provider} bridge ready at {primary_root}."
        if primary_root
        else (
            "Google Drive OAuth is ready; select a cloud folder before queuing transfers."
            if google_login_ready
            else "Cloud Drive bridge is waiting for Google login or a mounted cloud folder."
        )
    )
    return {
        "mode": "cloud_drive_bridge",
        "selectedMode": "google_oauth" if google_login_ready else ("mounted_folder" if primary_root else "configure"),
        "selectedProvider": selected_provider,
        "sourceRoot": source_root,
        "primaryRoot": primary_root,
        "targetRoot": primary_root,
        "mountedRoots": mounted_roots,
        "providers": list(manifest.ui_hints.get("providers", [])),
        "googleLoginReady": google_login_ready,
        "activeDirection": "",
        "safeDirections": safe_directions,
        "targetReady": target_ready,
        "requiresApprovalForWrite": True,
        "writePolicy": "preview_then_approve",
        "conflictPolicy": "keep_newer_and_log",
        "loginUrl": "https://drive.google.com/drive/my-drive",
        "desktopClientUrl": "https://www.google.com/drive/download/",
        "summary": summary,
    }


def _discover_cloud_drive_roots() -> list[dict]:
    candidates: list[tuple[str, Path]] = []
    for env_name, provider in (
        ("FLUXIO_CLOUD_DRIVE_ROOT", "local-mounted-drive"),
        ("FLUXIO_GOOGLE_DRIVE_ROOT", "google-drive"),
        ("GOOGLE_DRIVE_ROOT", "google-drive"),
        ("OneDrive", "onedrive"),
        ("OneDriveConsumer", "onedrive"),
        ("OneDriveCommercial", "onedrive"),
        ("DROPBOX", "dropbox"),
    ):
        value = str(os.environ.get(env_name, "")).strip()
        if value:
            candidates.append((provider, Path(value)))

    home = Path.home()
    candidates.extend(
        [
            ("google-drive", Path("G:/My Drive")),
            ("google-drive", Path("G:/Shared drives")),
            ("google-drive", home / "Google Drive"),
            ("google-drive", home / "My Drive"),
            ("onedrive", home / "OneDrive"),
            ("dropbox", home / "Dropbox"),
        ]
    )

    seen: set[str] = set()
    roots: list[dict] = []
    for provider, path in candidates:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            resolved = path.expanduser()
        key = str(resolved).lower()
        if key in seen or not resolved.exists():
            continue
        seen.add(key)
        roots.append({"provider": provider, "root": str(resolved)})
    return roots


def _google_drive_oauth_present(root: Path) -> bool:
    if str(os.environ.get("FLUXIO_GOOGLE_DRIVE_OAUTH_PRESENT", "")).strip():
        return True
    for env_name in ("GOOGLE_DRIVE_OAUTH_TOKEN", "GOOGLE_APPLICATION_CREDENTIALS"):
        if str(os.environ.get(env_name, "")).strip():
            return True
    for candidate in (
        root / ".agent_control" / "google_drive_token.json",
        Path.home() / ".config" / "syntelos" / "google_drive_token.json",
        Path.home() / ".config" / "fluxio" / "google_drive_token.json",
    ):
        if candidate.exists():
            return True
    return False


def _synology_bridge_plan(
    manifest: AppCapabilityManifest,
    status_payload: dict,
    job_payload: dict,
) -> dict:
    selected_mode = str(
        status_payload.get("selectedMode")
        or manifest.bridge.get("connection_mode")
        or "offline"
    ) if status_payload or manifest.bridge else "offline"
    selected_host = str(
        status_payload.get("selectedHost")
        or manifest.bridge.get("nas_host")
        or ""
    ) if status_payload or manifest.bridge else ""
    source_root = str(
        status_payload.get("sourceRoot")
        or manifest.bridge.get("source_root")
        or manifest.bridge.get("workspace_root")
        or ""
    ) if status_payload or manifest.bridge else ""
    target_root = str(
        status_payload.get("targetRoot")
        or manifest.bridge.get("target_root")
        or ""
    ) if status_payload or manifest.bridge else ""
    remote_project_root = str(
        manifest.bridge.get("remote_project_root")
        or manifest.bridge.get("remote_root")
        or ""
    ).strip()
    if remote_project_root:
        if not target_root:
            target_root = remote_project_root
        elif _looks_windows_drive_path(target_root):
            if not Path(target_root).expanduser().exists():
                target_root = remote_project_root
    active_direction = str(job_payload.get("direction") or "").strip().lower()
    target_path_exists = bool(target_root and Path(target_root).expanduser().exists())
    target_ready = bool(status_payload.get("targetReady")) if status_payload else target_path_exists
    activation_project = str(manifest.bridge.get("activation_project") or "Core")
    activation_command = str(
        manifest.bridge.get("activation_command")
        or manifest.bridge.get("map_command")
        or ""
    )
    control_protocol = str(manifest.bridge.get("control_protocol") or "ssh").strip().lower()
    requested_ssh_port = _safe_int(manifest.bridge.get("requested_ssh_port"))
    observed_ssh_port = _safe_int(manifest.bridge.get("ssh_port"))
    control_port = _safe_int(
        manifest.bridge.get("control_port")
        or requested_ssh_port
        or observed_ssh_port
        or 22
    )
    ssh_port_status = str(manifest.bridge.get("ssh_port_status") or "").strip()
    ssh_user = str(manifest.bridge.get("ssh_user") or "").strip()
    activation_required = bool(
        source_root
        and target_root
        and not target_ready
        and (selected_mode in {"tailscale", "lan"} or selected_host)
    )
    activation_hint = (
        f"Activate the {activation_project} project or run the Synology mapper before using {target_root}."
        if activation_required
        else ""
    )
    requires_approval_for_write = _as_bool(
        manifest.bridge.get("requires_approval_for_write"),
        default=True,
    )
    auto_sync_enabled = _as_bool(manifest.bridge.get("auto_sync"), default=False)
    configured_write_policy = str(manifest.bridge.get("write_policy") or "").strip()
    write_policy = (
        configured_write_policy
        or (
            "preview_then_approve"
            if requires_approval_for_write
            else "automatic_bidirectional"
        )
    )
    safe_directions = []
    if source_root and target_ready:
        safe_directions = ["upload", "download"]
    return {
        "mode": "bidirectional_bridge",
        "selectedMode": selected_mode,
        "selectedHost": selected_host,
        "controlProtocol": control_protocol,
        "controlPort": control_port,
        "requestedSshPort": requested_ssh_port or control_port,
        "observedSshPort": observed_ssh_port,
        "sshPortStatus": ssh_port_status,
        "sshUser": ssh_user,
        "remoteProjectRoot": remote_project_root,
        "sourceRoot": source_root,
        "targetRoot": target_root,
        "activeDirection": active_direction,
        "safeDirections": safe_directions,
        "targetReady": target_ready,
        "activationRequired": activation_required,
        "activationProject": activation_project,
        "activationHint": activation_hint,
        "activationCommand": activation_command,
        "requiresApprovalForWrite": requires_approval_for_write,
        "autoSyncEnabled": auto_sync_enabled and not requires_approval_for_write,
        "writePolicy": write_policy,
        "conflictPolicy": str(status_payload.get("conflictPolicy") or "keep_newer_and_log"),
        "continuousRunRole": (
            "NAS keeps the service online while the desktop keeps local working files editable."
        ),
    }


def _read_bridge_json(endpoint: str, path: str) -> dict:
    base = str(endpoint or "").rstrip("/")
    if not base:
        return {}
    if base.endswith("/fluxio"):
        base = base[: -len("/fluxio")]
    url = f"{base}{path}"
    try:
        with urllib.request.urlopen(url, timeout=BRIDGE_HTTP_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _looks_windows_drive_path(value: str) -> bool:
    return len(value) >= 3 and value[1] == ":" and value[2] in {"/", "\\"}


def _as_bool(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _approval_callback_for_app(app_id: str, app_root: Path) -> dict:
    return {"available": False, "channel": "", "detail": ""}


def _persistable_session_state(session: ConnectedAppSession) -> dict:
    return {
        "session_id": session.session_id,
        "task_history": session.task_history,
        "latest_task_result": session.latest_task_result,
    }


def _load_session_state(root: Path) -> dict:
    state_path = root / ".agent_control" / "connected_apps_state.json"
    if not state_path.exists():
        return {}
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_session_state(root: Path, state: dict) -> None:
    state_path = root / ".agent_control" / "connected_apps_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(state, indent=2)
    if state_path.exists():
        try:
            if state_path.read_text(encoding="utf-8") == serialized:
                return
        except OSError:
            pass
    state_path.write_text(serialized, encoding="utf-8")


def _build_grants(manifest: AppCapabilityManifest) -> list[CapabilityGrant]:
    return [
        CapabilityGrant(
            grant_id=f"grant_{manifest.app_id}_{index}",
            capability_key=permission,
            status="granted" if index < 2 else "review",
            scope="app",
            reason="Loaded from the local bridge manifest and kept inside capability scope.",
        )
        for index, permission in enumerate(manifest.permissions)
    ]


def _resolve_app_root(root: Path, manifest: AppCapabilityManifest) -> Path | None:
    configured_root = manifest.bridge.get("workspace_root") or manifest.ui_hints.get(
        "workspaceRoot"
    )
    if configured_root:
        path = Path(str(configured_root)).expanduser().resolve()
        return path

    for candidate in _candidate_app_roots(root, manifest.app_id):
        if candidate.exists():
            return candidate.resolve()
    return _candidate_app_roots(root, manifest.app_id)[0]


def _candidate_app_roots(root: Path, app_id: str) -> list[Path]:
    base = root.resolve().parent
    lookup = {
        "oratio-viva": [base / "OratioViva", base / "oratio-viva"],
        "solantir-terminal": [base / "Solantir", base / "solantir"],
        "synology-fast-sync": [base / "Cowork"],
    }
    return lookup.get(app_id, [base / app_id])


def _read_package_name_version(path: Path) -> tuple[str, str]:
    if not path.exists():
        return "", ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "", ""
    return str(payload.get("name", "")), str(payload.get("version", ""))


def _count_files(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("*") if path.is_file())


def _load_manifest_payloads(config_path: Path) -> list[dict]:
    if config_path.exists():
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = []
        if isinstance(payload, list) and payload:
            return payload
    return [
        {
            "manifest_id": "manifest_oratio_viva",
            "schema_version": SCHEMA_VERSION,
            "app_id": "oratio-viva",
            "name": "Oratio Viva",
            "description": "Speech and voice workflows exposed through a local bridge for guided agent execution.",
            "bridge": {
                "transport": "http",
                "endpoint": "http://127.0.0.1:47830/fluxio",
                "healthcheck": "/health",
                "event_stream": "/events",
            },
            "auth": {"mode": "local_token", "scopes": ["speech.manage", "voice.render"]},
            "permissions": ["task.run", "context.read", "action.invoke"],
            "tasks": [
                {
                    "task_id": "render-voice-preview",
                    "label": "Render voice preview",
                    "description": "Create a short preview from app-managed voices and prompts.",
                    "requires_approval": False,
                }
            ],
            "context_surfaces": [
                {
                    "surface_id": "voice-catalog",
                    "label": "Voice Catalog",
                    "description": "App-managed voice inventory and metadata.",
                    "access": "read",
                }
            ],
            "action_hooks": [
                {
                    "hook_id": "queue-render",
                    "label": "Queue Render",
                    "description": "Send a render request into the app job queue.",
                    "mutability": "write",
                    "risk_level": "medium",
                    "requires_approval": False,
                }
            ],
            "ui_hints": {"category": "speech", "requiresUserPresent": False},
        },
        {
            "manifest_id": "manifest_solantir_terminal",
            "schema_version": SCHEMA_VERSION,
            "app_id": "solantir-terminal",
            "name": "Solantir Terminal",
            "description": "Operator dashboard surfaces exposed to Fluxio through a capability-scoped bridge.",
            "bridge": {
                "transport": "ipc",
                "endpoint": "pipe://fluxio-solantir",
                "healthcheck": "ping",
                "event_stream": "events",
            },
            "auth": {"mode": "local_session", "scopes": ["dashboard.read", "watchlist.write"]},
            "permissions": ["task.run", "context.read", "approval.request"],
            "tasks": [
                {
                    "task_id": "refresh-watchlist",
                    "label": "Refresh watchlist",
                    "description": "Run the app-native watchlist refresh workflow.",
                    "requires_approval": True,
                }
            ],
            "context_surfaces": [
                {
                    "surface_id": "watchlist",
                    "label": "Watchlist",
                    "description": "Current analyst watchlist state.",
                    "access": "read",
                }
            ],
            "action_hooks": [
                {
                    "hook_id": "ack-alert",
                    "label": "Acknowledge alert",
                    "description": "Mark a surfaced alert as acknowledged inside the app.",
                    "mutability": "write",
                    "risk_level": "medium",
                    "requires_approval": True,
                }
            ],
            "ui_hints": {"category": "operations", "requiresUserPresent": True},
        },
    ]


def _to_manifest(payload: dict) -> AppCapabilityManifest:
    errors = validate_manifest_payload(payload)
    if errors:
        raise ValueError("; ".join(errors))
    return AppCapabilityManifest(
        manifest_id=str(payload["manifest_id"]),
        schema_version=str(payload["schema_version"]),
        app_id=str(payload["app_id"]),
        name=str(payload["name"]),
        description=str(payload["description"]),
        bridge=dict(payload.get("bridge", {})),
        auth=dict(payload.get("auth", {})),
        permissions=list(payload.get("permissions", [])),
        tasks=[AppTaskDescriptor(**item) for item in payload.get("tasks", [])],
        context_surfaces=[AppContextSurface(**item) for item in payload.get("context_surfaces", [])],
        action_hooks=[AppActionHook(**item) for item in payload.get("action_hooks", [])],
        ui_hints=dict(payload.get("ui_hints", {})),
    )
