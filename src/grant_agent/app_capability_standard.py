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
)

SCHEMA_VERSION = "fluxio.app-capability/v0-draft"
BRIDGE_VERSION = "fluxio.bridge/v0-draft"


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
    connected_sessions: list[ConnectedAppSession] = []
    for manifest in manifests:
        grants = [
            CapabilityGrant(
                grant_id=f"grant_{manifest.app_id}_{index}",
                capability_key=permission,
                status="granted" if index < 2 else "review",
                scope="app",
                reason="Mock registry entry for bridge-lab review.",
            )
            for index, permission in enumerate(manifest.permissions)
        ]
        connected_sessions.append(
            ConnectedAppSession(
                session_id=f"bridge_{manifest.app_id}",
                app_id=manifest.app_id,
                app_name=manifest.name,
                status="mock_connected",
                bridge_health="healthy",
                manifest_id=manifest.manifest_id,
                granted_capabilities=grants,
                active_tasks=[item.label for item in manifest.tasks[:1]],
                notes=[
                    "Bridge lab mock entry. Capability-scoped control only.",
                    "This app standard is separate from runtime adapters and mission execution.",
                ],
            )
        )

    handshake = (
        AppBridgeHandshake(
            app_id=manifests[0].app_id,
            bridge_version=BRIDGE_VERSION,
            session_id=f"handshake_{uuid.uuid4().hex[:8]}",
            transport=manifests[0].bridge.get("transport", "http"),
            capabilities=manifests[0].permissions,
            auth_mode=manifests[0].auth.get("mode", "local_token"),
            requires_user_present=bool(manifests[0].ui_hints.get("requiresUserPresent", False)),
        )
        if manifests
        else AppBridgeHandshake(
            app_id="mock.app",
            bridge_version=BRIDGE_VERSION,
            session_id=f"handshake_{uuid.uuid4().hex[:8]}",
            transport="http",
        )
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "bridgeVersion": BRIDGE_VERSION,
        "manifestSchema": manifest_schema(),
        "bridgeHandshake": asdict(handshake),
        "phases": [
            "Phase A: spec and mock registry only",
            "Phase B: one reference integration using the manifest and local bridge",
            "Phase C: developer kit and public docs",
        ],
        "discoveredApps": [asdict(item) for item in manifests],
        "connectedSessions": [asdict(item) for item in connected_sessions],
        "recommendation": (
            "Keep connected apps in Bridge Lab until delegated supervision and approval callbacks are fully stable."
        ),
    }


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
