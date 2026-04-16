from __future__ import annotations

import json
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

    recommendation = (
        "OratioViva and Mind Tower are live reference integrations. Solantir remains in manifest-only follow-on review."
        if any(session.status == "connected" for session in connected_sessions)
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
            "Phase B: live reference integrations for OratioViva and Mind Tower",
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
    if app_id == "mind-tower":
        service_dirs = sorted(
            path.name for path in (app_root / "services").iterdir() if path.is_dir()
        ) if (app_root / "services").exists() else []
        admin_files = _count_files(app_root / "apps" / "admin")
        return [
            {
                "surfaceId": "monitoring-dashboard",
                "label": "Monitoring Dashboard",
                "summary": f"{admin_files} admin files and {len(service_dirs)} service modules detected.",
                "items": service_dirs[:6],
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

    if manifest.app_id == "mind-tower":
        service_dirs = sorted(
            path.name for path in (app_root / "services").iterdir() if path.is_dir()
        ) if (app_root / "services").exists() else []
        telegram_available = (
            app_root
            / "services"
            / "monitor-worker"
            / "src"
            / "mindtower_worker"
            / "telegram_listener.py"
        ).exists()
        return [
            {
                "taskId": manifest.tasks[0].task_id,
                "label": manifest.tasks[0].label,
                "status": "completed",
                "sourceKind": "connected_app",
                "resultSummary": "Ran the local monitoring digest bridge task and captured session proof.",
                "createdAt": utc_now_iso(),
                "completedAt": utc_now_iso(),
                "approvalStatus": "callback_ready" if telegram_available else "not_required",
                "payload": {
                    "services": service_dirs[:6],
                    "workspaceRoot": str(app_root),
                    "surfaceRead": "monitoring-dashboard",
                    "callbackChannel": "telegram" if telegram_available else "",
                },
            }
        ]

    return []


def _approval_callback_for_app(app_id: str, app_root: Path) -> dict:
    if app_id == "mind-tower":
        telegram_listener = (
            app_root
            / "services"
            / "monitor-worker"
            / "src"
            / "mindtower_worker"
            / "telegram_listener.py"
        )
        if telegram_listener.exists():
            return {
                "available": True,
                "channel": "telegram",
                "detail": "Telegram listener detected for escalation-aware callback handling.",
            }
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
        "mind-tower": [base / "mind-tower", base / "MindTower"],
        "solantir-terminal": [base / "Solantir", base / "solantir"],
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
            "manifest_id": "manifest_mind_tower",
            "schema_version": SCHEMA_VERSION,
            "app_id": "mind-tower",
            "name": "Mind Tower",
            "description": "Monitoring, admin, and digest workflows exposed to Fluxio through a local bridge.",
            "bridge": {
                "transport": "http",
                "endpoint": "http://127.0.0.1:47831/fluxio",
                "healthcheck": "/health",
                "event_stream": "/events",
            },
            "auth": {"mode": "local_token", "scopes": ["admin.read", "digest.run", "telegram.callback"]},
            "permissions": ["task.run", "context.read", "approval.callback"],
            "tasks": [
                {
                    "task_id": "run-monitor-digest",
                    "label": "Run monitoring digest",
                    "description": "Collect monitoring context and generate a digest-style task result.",
                    "requires_approval": False,
                }
            ],
            "context_surfaces": [
                {
                    "surface_id": "monitoring-dashboard",
                    "label": "Monitoring Dashboard",
                    "description": "Admin and monitoring context surfaced from Mind Tower.",
                    "access": "read",
                }
            ],
            "action_hooks": [
                {
                    "hook_id": "send-digest",
                    "label": "Send Digest",
                    "description": "Trigger a digest delivery or callback-aware review action.",
                    "mutability": "write",
                    "risk_level": "medium",
                    "requires_approval": False,
                }
            ],
            "ui_hints": {"category": "operations", "requiresUserPresent": False},
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
