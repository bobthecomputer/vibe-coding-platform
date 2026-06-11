from __future__ import annotations

import json
import os
import time
import urllib.request
import uuid
import base64
import importlib.util
from dataclasses import asdict
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from .models import DeliveryReceipt, MissionEvent, utc_now_iso

RECEIPTS_FILENAME = "delivery_receipts.jsonl"
WEB_PUSH_SUBSCRIPTIONS_FILENAME = "web_push_subscriptions.jsonl"
WEB_PUSH_VAPID_FILENAME = "web_push_vapid.json"
NTFY_SETTINGS_FILENAME = "ntfy_settings.json"


def delivery_receipts_path(root: str | Path) -> Path:
    path = Path(root) / ".agent_control" / RECEIPTS_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def web_push_subscriptions_path(root: str | Path) -> Path:
    path = Path(root) / ".agent_control" / WEB_PUSH_SUBSCRIPTIONS_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def web_push_vapid_path(root: str | Path) -> Path:
    path = Path(root) / ".agent_control" / WEB_PUSH_VAPID_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def ntfy_settings_path(root: str | Path) -> Path:
    path = Path(root) / ".agent_control" / NTFY_SETTINGS_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def ntfy_status(root: str | Path | None = None) -> dict[str, Any]:
    settings = _load_ntfy_settings(root)
    server_url = _ntfy_server_url(settings)
    topic = _ntfy_topic(settings)
    token = _ntfy_token(settings)
    configured = bool(topic)
    return {
        "schema": "fluxio.ntfy_status.v1",
        "configured": configured,
        "senderConfigured": configured,
        "serverUrl": server_url,
        "topic": topic,
        "tokenConfigured": bool(token),
        "channel": "ntfy",
        "setupPath": str(ntfy_settings_path(root)) if root else "",
        "nextAction": (
            "ntfy can send phone/tablet mission notifications."
            if configured
            else "Set FLUXIO_NTFY_TOPIC or .agent_control/ntfy_settings.json before ntfy phone push can send."
        ),
    }


def web_push_status(root: str | Path | None = None) -> dict[str, Any]:
    vapid_config = _load_web_push_vapid_config(root) if root else {}
    public_key = _web_push_public_key(root, vapid_config=vapid_config)
    private_key = _web_push_private_key(root, vapid_config=vapid_config)
    dependency_available = _web_push_dependency_available()
    subscription_count = len(load_web_push_subscriptions(root)) if root else 0
    keys_configured = bool(public_key and private_key)
    sender_configured = bool(keys_configured and dependency_available)
    return {
        "schema": "fluxio.web_push_status.v1",
        "configured": bool(public_key),
        "senderConfigured": sender_configured,
        "dependencyAvailable": dependency_available,
        "privateKeyConfigured": bool(private_key),
        "localKeyConfigured": bool(vapid_config.get("publicKey") and vapid_config.get("privateKeyPem")),
        "configuredSource": _web_push_key_source(root, vapid_config=vapid_config),
        "setupPath": str(web_push_vapid_path(root)) if root else "",
        "publicKey": public_key,
        "subscriptionCount": subscription_count,
        "channel": "web_push",
        "nextAction": (
            "Closed-tab Web Push can send mission notifications."
            if sender_configured and subscription_count > 0
            else "Register this browser from the notification stack before closed-tab push can send."
            if sender_configured
            else "Install pywebpush and set FLUXIO_WEB_PUSH_PUBLIC_KEY plus FLUXIO_WEB_PUSH_PRIVATE_KEY before closed-tab push can send."
            if keys_configured and not dependency_available
            else "Set FLUXIO_WEB_PUSH_PRIVATE_KEY before closed-tab push can send."
            if public_key
            else "Provision VAPID keys from the notification stack or set FLUXIO_WEB_PUSH_PUBLIC_KEY and FLUXIO_WEB_PUSH_PRIVATE_KEY."
        ),
    }


def _load_ntfy_settings(root: str | Path | None) -> dict[str, Any]:
    if not root:
        return {}
    try:
        payload = json.loads(ntfy_settings_path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _ntfy_server_url(settings: dict[str, Any] | None = None) -> str:
    value = (
        os.environ.get("FLUXIO_NTFY_SERVER_URL")
        or os.environ.get("NTFY_SERVER_URL")
        or str((settings or {}).get("serverUrl") or (settings or {}).get("server_url") or "")
        or "https://ntfy.sh"
    ).strip()
    return value.rstrip("/")


def _ntfy_topic(settings: dict[str, Any] | None = None) -> str:
    return (
        os.environ.get("FLUXIO_NTFY_TOPIC")
        or os.environ.get("NTFY_TOPIC")
        or str((settings or {}).get("topic") or "")
        or ""
    ).strip().strip("/")


def _ntfy_token(settings: dict[str, Any] | None = None) -> str:
    return (
        os.environ.get("FLUXIO_NTFY_TOKEN")
        or os.environ.get("NTFY_TOKEN")
        or str((settings or {}).get("token") or "")
        or ""
    ).strip()


def record_web_push_subscription(
    root: str | Path,
    *,
    subscription: dict[str, Any],
    user_agent: str = "",
    status: str = "subscribed",
) -> dict[str, Any]:
    endpoint = str(subscription.get("endpoint") or "").strip()
    if not endpoint:
        raise ValueError("Web Push subscription endpoint is required.")
    row = {
        "schema": "fluxio.web_push_subscription.v1",
        "subscriptionId": f"push_{uuid.uuid4().hex[:12]}",
        "endpoint": endpoint,
        "subscription": subscription,
        "userAgent": user_agent,
        "status": status,
        "createdAt": utc_now_iso(),
        "channel": "web_push",
    }
    with web_push_subscriptions_path(root).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")
    return {
        **row,
        "subscription": {
            "endpoint": endpoint,
            "keysPresent": bool((subscription.get("keys") or {}).get("p256dh"))
            and bool((subscription.get("keys") or {}).get("auth")),
        },
    }


def load_web_push_subscriptions(root: str | Path, limit: int = 50) -> list[dict[str, Any]]:
    path = Path(root) / ".agent_control" / WEB_PUSH_SUBSCRIPTIONS_FILENAME
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in _tail_text_lines(path, limit):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("status") == "subscribed":
            rows.append(row)
    return rows


def _web_push_dependency_available() -> bool:
    return importlib.util.find_spec("pywebpush") is not None


def _load_web_push_vapid_config(root: str | Path | None) -> dict[str, Any]:
    if not root:
        return {}
    try:
        payload = json.loads(web_push_vapid_path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _web_push_key_source(root: str | Path | None = None, *, vapid_config: dict[str, Any] | None = None) -> str:
    if os.environ.get("FLUXIO_WEB_PUSH_PUBLIC_KEY") or os.environ.get("VAPID_PUBLIC_KEY"):
        return "environment"
    if root and (vapid_config if vapid_config is not None else _load_web_push_vapid_config(root)).get("publicKey"):
        return "local_agent_control"
    return "missing"


def _web_push_private_key(root: str | Path | None = None, *, vapid_config: dict[str, Any] | None = None) -> str:
    config = vapid_config if vapid_config is not None else _load_web_push_vapid_config(root)
    return (
        os.environ.get("FLUXIO_WEB_PUSH_PRIVATE_KEY")
        or os.environ.get("VAPID_PRIVATE_KEY")
        or str(config.get("privateKeyPem") or config.get("privateKey") or "")
        or ""
    ).strip()


def _web_push_public_key(root: str | Path | None = None, *, vapid_config: dict[str, Any] | None = None) -> str:
    config = vapid_config if vapid_config is not None else _load_web_push_vapid_config(root)
    return (
        os.environ.get("FLUXIO_WEB_PUSH_PUBLIC_KEY")
        or os.environ.get("VAPID_PUBLIC_KEY")
        or str(config.get("publicKey") or "")
        or ""
    ).strip()


def generate_web_push_vapid_config(root: str | Path, *, subject: str = "") -> dict[str, Any]:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Install cryptography before generating Web Push VAPID keys.") from exc

    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    public_key = base64.urlsafe_b64encode(public_bytes).rstrip(b"=").decode("ascii")
    path = web_push_vapid_path(root)
    payload = {
        "schema": "fluxio.web_push_vapid_config.v1",
        "createdAt": utc_now_iso(),
        "channel": "web_push",
        "subject": subject.strip() or os.environ.get("FLUXIO_WEB_PUSH_SUBJECT", "mailto:fluxio@localhost"),
        "publicKey": public_key,
        "privateKeyPem": private_pem,
        "warning": "This file contains a Web Push private key. Keep it under .agent_control and out of Git.",
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    status = web_push_status(root)
    return {
        "schema": "fluxio.web_push_vapid_provisioning.v1",
        "ok": True,
        "path": str(path),
        "publicKey": public_key,
        "privateKeyConfigured": True,
        "senderConfigured": bool(status.get("senderConfigured")),
        "dependencyAvailable": bool(status.get("dependencyAvailable")),
        "nextAction": status.get("nextAction", ""),
    }


def send_web_push_delivery_receipts(
    *,
    root: str | Path,
    mission_id: str,
    title: str,
    body: str,
    target_url: str = "/control?mode=agent&surface=agent",
    event_kind: str = "notification.web_push_test",
    subscriptions: list[dict[str, Any]] | None = None,
    dry_run: bool = False,
) -> list[DeliveryReceipt]:
    rows = subscriptions if subscriptions is not None else load_web_push_subscriptions(root)
    if not rows:
        return [
            _append_receipt(
                root,
                DeliveryReceipt(
                    receipt_id=f"rcpt_{uuid.uuid4().hex[:12]}",
                    mission_id=mission_id,
                    channel="web_push",
                    destination="",
                    event_kind=event_kind,
                    event_message=body,
                    sent_at=utc_now_iso(),
                    status="skipped",
                    error_message="no_web_push_subscriptions",
                ),
            )
        ]

    public_key = _web_push_public_key(root)
    private_key = _web_push_private_key(root)
    dependency_available = _web_push_dependency_available()
    if not public_key or not private_key or not dependency_available:
        reason = (
            "web_push_sender_dependency_missing"
            if public_key and private_key and not dependency_available
            else "web_push_vapid_keys_not_configured"
        )
        return [
            _append_receipt(
                root,
                DeliveryReceipt(
                    receipt_id=f"rcpt_{uuid.uuid4().hex[:12]}",
                    mission_id=mission_id,
                    channel="web_push",
                    destination=str(row.get("endpoint") or ""),
                    event_kind=event_kind,
                    event_message=body,
                    sent_at=utc_now_iso(),
                    status="skipped",
                    error_message=reason,
                ),
            )
            for row in rows
        ]

    payload = json.dumps(
        {
            "title": title,
            "body": body,
            "url": target_url,
            "missionId": mission_id,
            "tag": f"fluxio:{event_kind}:{mission_id}",
        }
    )
    receipts: list[DeliveryReceipt] = []
    for row in rows:
        subscription = row.get("subscription") if isinstance(row.get("subscription"), dict) else {}
        endpoint = str(row.get("endpoint") or subscription.get("endpoint") or "")
        receipt = _append_receipt(
            root,
            DeliveryReceipt(
                receipt_id=f"rcpt_{uuid.uuid4().hex[:12]}",
                mission_id=mission_id,
                channel="web_push",
                destination=endpoint,
                event_kind=event_kind,
                event_message=body,
                sent_at=utc_now_iso(),
                status="pending",
            ),
        )
        if dry_run:
            receipt.status = "delivered"
            receipt.delivery_url = f"dry_run://web_push/{receipt.receipt_id}"
            receipts.append(_update_receipt(root, receipt))
            continue
        try:
            from pywebpush import WebPushException, webpush

            webpush(
                subscription_info=subscription,
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": os.environ.get("FLUXIO_WEB_PUSH_SUBJECT", "mailto:fluxio@localhost")},
            )
            receipt.status = "delivered"
            receipt.delivery_url = "web-push://sent"
        except Exception as exc:  # noqa: BLE001
            receipt.status = "error"
            receipt.error_message = str(exc)
        receipts.append(_update_receipt(root, receipt))
    return receipts


def _read_telegram_token_with_source(root: str | Path | None = None) -> tuple[str, str]:
    token = (
        os.environ.get("SYNTELOS_TELEGRAM_BOT_TOKEN")
        or os.environ.get("FLUXIO_TELEGRAM_BOT_TOKEN")
        or os.environ.get("TELEGRAM_BOT_TOKEN")
    )
    if token:
        return token.strip(), "fluxio_env"
    if root:
        try:
            candidate = Path(root) / ".agent_control" / "telegram_bot_token.txt"
            if candidate.exists():
                token = candidate.read_text(encoding="utf-8").strip()
                if token:
                    return token, "fluxio_agent_control"
        except OSError:
            pass
    for candidate in (
        Path.home() / ".agent_control" / "telegram_bot_token.txt",
        Path.home() / ".syntelos" / "telegram_bot_token.txt",
    ):
        try:
            if candidate.exists():
                token = candidate.read_text(encoding="utf-8").strip()
                if token:
                    return token, "user_agent_control"
        except OSError:
            continue
    token = _read_openclaw_telegram_token()
    return (token, "openclaw_telegram_token") if token else ("", "missing")


def _read_telegram_token(root: str | Path | None = None) -> str:
    token, _source = _read_telegram_token_with_source(root)
    return token


def _read_openclaw_telegram_token() -> str:
    env_path = Path.home() / ".openclaw" / ".env"
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "TELEGRAM_BOT_TOKEN":
            continue
        token = value.strip().strip('"').strip("'")
        if token:
            return token
    return ""


def _read_telegram_destination(root: str | Path) -> str:
    for key in ("FLUXIO_TELEGRAM_DESTINATION", "TELEGRAM_CHAT_ID", "TELEGRAM_DESTINATION"):
        value = str(os.environ.get(key) or "").strip()
        if value:
            return value
    settings_path = Path(root) / ".agent_control" / "telegram_settings.json"
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("destination") or "").strip()


def _append_receipt(root: str | Path, receipt: DeliveryReceipt) -> DeliveryReceipt:
    with delivery_receipts_path(root).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(receipt), ensure_ascii=True) + "\n")
    return receipt


def _update_receipt(root: str | Path, receipt: DeliveryReceipt) -> DeliveryReceipt:
    path = delivery_receipts_path(root)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    encoded = json.dumps(asdict(receipt), ensure_ascii=True)
    if lines:
        lines[-1] = encoded
    else:
        lines.append(encoded)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return receipt


def load_delivery_receipts(root: str | Path, limit: int = 50) -> list[DeliveryReceipt]:
    path = Path(root) / ".agent_control" / RECEIPTS_FILENAME
    if not path.exists():
        return []
    rows: list[DeliveryReceipt] = []
    for line in _tail_text_lines(path, limit):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            if not isinstance(payload, dict):
                continue
            allowed = DeliveryReceipt.__dataclass_fields__.keys()
            rows.append(DeliveryReceipt(**{key: value for key, value in payload.items() if key in allowed}))
        except (TypeError, json.JSONDecodeError):
            continue
    return rows


def _tail_text_lines(path: Path, limit: int, *, chunk_size: int = 8192) -> list[str]:
    if limit <= 0:
        return []
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            offset = size
            chunks: list[bytes] = []
            line_count = 0
            while offset > 0 and line_count <= limit:
                read_size = min(chunk_size, offset)
                offset -= read_size
                handle.seek(offset)
                chunk = handle.read(read_size)
                chunks.append(chunk)
                line_count += chunk.count(b"\n")
    except OSError:
        return []
    data = b"".join(reversed(chunks))
    return data.decode("utf-8", errors="replace").splitlines()[-limit:]


def acknowledge_delivery_receipt(root: str | Path, receipt_id: str) -> DeliveryReceipt | None:
    target = str(receipt_id or "").strip()
    if not target:
        return None
    path = delivery_receipts_path(root)
    if not path.exists():
        return None
    try:
        raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    rows: list[dict[str, Any]] = []
    matched: DeliveryReceipt | None = None
    for raw_line in raw_lines:
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        if str(row.get("receipt_id") or "") == target:
            row["status"] = "acknowledged"
            row["acknowledged_at"] = utc_now_iso()
            try:
                allowed = DeliveryReceipt.__dataclass_fields__.keys()
                matched = DeliveryReceipt(**{key: value for key, value in row.items() if key in allowed})
            except (TypeError, ValueError):
                matched = None
        rows.append(row)
    if matched is None:
        return None
    tmp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=True, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)
    return matched


def delivery_receipt_from_event(
    event: MissionEvent,
    *,
    channel: str,
    destination: str,
    transport_provider: str = "",
    producer: str = "",
) -> DeliveryReceipt:
    return DeliveryReceipt(
        receipt_id=f"rcpt_{uuid.uuid4().hex[:12]}",
        mission_id=event.mission_id,
        channel=channel,
        destination=destination,
        event_kind=event.kind,
        event_message=event.message,
        sent_at=utc_now_iso(),
        status="pending",
        origin_runtime=str(
            event.metadata.get("originRuntime")
            or event.metadata.get("runtimeId")
            or event.metadata.get("runtime")
            or ""
        ),
        origin_provider=str(
            event.metadata.get("originProvider")
            or event.metadata.get("provider")
            or event.metadata.get("modelProvider")
            or ""
        ),
        origin_model=str(event.metadata.get("originModel") or event.metadata.get("model") or ""),
        transport_provider=transport_provider,
        producer=producer or str(event.metadata.get("producer") or event.kind.split(".", 1)[0] or ""),
        mission_title=str(event.metadata.get("missionTitle") or event.metadata.get("title") or ""),
        source_session_id=str(event.metadata.get("sourceSessionId") or event.metadata.get("sessionId") or ""),
        evidence_path=str(event.metadata.get("evidencePath") or ""),
        screenshot_path=str(event.metadata.get("screenshotPath") or ""),
    )


def record_delivery_receipt(
    root: str | Path,
    *,
    mission_id: str,
    channel: str,
    destination: str,
    event_kind: str,
    event_message: str,
    status: str,
    error_message: str = "",
    delivery_url: str = "",
    origin_runtime: str = "",
    origin_provider: str = "",
    origin_model: str = "",
    transport_provider: str = "",
    producer: str = "",
    mission_title: str = "",
    source_session_id: str = "",
    evidence_path: str = "",
    screenshot_path: str = "",
) -> DeliveryReceipt:
    return _append_receipt(
        root,
        DeliveryReceipt(
            receipt_id=f"rcpt_{uuid.uuid4().hex[:12]}",
            mission_id=mission_id,
            channel=channel,
            destination=destination,
            event_kind=event_kind,
            event_message=event_message,
            sent_at=utc_now_iso(),
            status=status,
            error_message=error_message,
            delivery_url=delivery_url,
            origin_runtime=origin_runtime,
            origin_provider=origin_provider,
            origin_model=origin_model,
            transport_provider=transport_provider or channel,
            producer=producer,
            mission_title=mission_title,
            source_session_id=source_session_id,
            evidence_path=evidence_path,
            screenshot_path=screenshot_path,
        ),
    )


def _format_telegram_message(event: MissionEvent) -> str:
    lines = [
        "<b>Fluxio mission event</b>",
        f"<b>Mission:</b> {escape(event.mission_id)}",
        f"<b>Event:</b> {escape(event.kind)}",
        f"<b>Message:</b> {escape(event.message)}",
    ]
    for key, value in list(event.metadata.items())[:5]:
        if key.lower() in {"destination", "token"}:
            continue
        lines.append(f"<b>{escape(key)}:</b> {escape(str(value)[:160])}")
    runtime = str(event.metadata.get("originRuntime") or event.metadata.get("runtimeId") or "").strip()
    provider = str(event.metadata.get("originProvider") or event.metadata.get("provider") or "").strip()
    model = str(event.metadata.get("originModel") or event.metadata.get("model") or "").strip()
    transport = str(event.metadata.get("transportProvider") or "").strip()
    if runtime:
        lines.append(f"<b>Runtime:</b> {escape(runtime)}")
    if provider or model:
        lines.append(f"<b>Provider/model:</b> {escape(' / '.join(part for part in (provider, model) if part))}")
    if transport:
        lines.append(f"<b>Transport:</b> {escape(transport)}")
    return "\n".join(lines)


def _format_ntfy_body(event: MissionEvent) -> str:
    lines = [
        event.message.strip() or "Fluxio mission update.",
        "",
        f"Mission: {event.mission_id}",
        f"Event: {event.kind}",
    ]
    for key, value in list(event.metadata.items())[:5]:
        if key.lower() in {"destination", "token", "authorization"}:
            continue
        lines.append(f"{key}: {str(value)[:160]}")
    return "\n".join(line for line in lines if line is not None)


def send_ntfy_delivery_receipt(
    event: MissionEvent,
    *,
    root: str | Path,
    topic: str = "",
    title: str = "",
    priority: str = "default",
    tags: str = "fluxio",
    click_url: str = "",
    dry_run: bool = False,
) -> DeliveryReceipt:
    settings = _load_ntfy_settings(root)
    server_url = _ntfy_server_url(settings)
    resolved_topic = str(topic or _ntfy_topic(settings)).strip().strip("/")
    destination = f"{server_url}/{resolved_topic}" if resolved_topic else server_url
    receipt = _append_receipt(
        root,
        delivery_receipt_from_event(event, channel="ntfy", destination=destination),
    )
    if not resolved_topic:
        receipt.status = "skipped"
        receipt.error_message = "ntfy_topic_not_configured"
        return _update_receipt(root, receipt)
    if not urlparse(server_url).scheme:
        receipt.status = "error"
        receipt.error_message = "ntfy_server_url_invalid"
        return _update_receipt(root, receipt)
    if dry_run:
        receipt.status = "delivered"
        receipt.delivery_url = f"dry_run://ntfy/{resolved_topic}"
        return _update_receipt(root, receipt)

    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "X-Title": title.strip() or "Fluxio mission update",
        "X-Priority": priority.strip() or "default",
        "X-Tags": tags.strip() or "fluxio",
    }
    if click_url.strip():
        headers["X-Click"] = click_url.strip()
    token = _ntfy_token(settings)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{server_url}/{quote(resolved_topic, safe='')}",
        data=_format_ntfy_body(event).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    last_error = ""
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response.read()
            last_error = ""
            break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            receipt.retry_count = attempt + 1
            if attempt < 2:
                time.sleep(2**attempt)
    if last_error:
        receipt.status = "error"
        receipt.error_message = last_error
    else:
        receipt.status = "delivered"
        receipt.delivery_url = f"{server_url}/***/json"
    return _update_receipt(root, receipt)


def _watchdog_event_from_report(report: dict[str, Any]) -> MissionEvent:
    problem_report = report.get("problemReport") if isinstance(report.get("problemReport"), dict) else {}
    first_problem = (
        problem_report.get("firstProblem")
        if isinstance(problem_report.get("firstProblem"), dict)
        else {}
    )
    problem_count = int(problem_report.get("problemCount") or 0)
    status = str(problem_report.get("status") or ("open" if problem_count else "clear"))
    mission_id = str(first_problem.get("missionId") or "mission_watchdog")
    if problem_count:
        title = str(first_problem.get("title") or "Watchdog problem")
        first_step = str(first_problem.get("firstStep") or problem_report.get("nextAction") or "")
        message = f"{problem_count} watchdog problem(s): {title}. First step: {first_step}"
    else:
        message = str(
            problem_report.get("nextAction")
            or report.get("nextAction")
            or "No watchdog problems found. Keep the external loop active."
        )
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return MissionEvent(
        mission_id=mission_id,
        kind="watchdog.problem_report",
        message=message[:900],
        metadata={
            "watchdogStatus": status,
            "problemCount": problem_count,
            "bad": summary.get("bad", 0),
            "warn": summary.get("warn", 0),
            "firstStep": str(first_problem.get("firstStep") or problem_report.get("nextAction") or "")[:240],
        },
    )


def send_telegram_delivery_receipt(
    event: MissionEvent,
    *,
    destination: str,
    root: str | Path,
    dry_run: bool = False,
) -> DeliveryReceipt:
    token, token_source = _read_telegram_token_with_source(root)
    transport_provider = (
        "telegram_via_openclaw_token"
        if token_source == "openclaw_telegram_token"
        else f"telegram_via_{token_source}"
        if token_source and token_source != "missing"
        else "telegram"
    )
    event.metadata.setdefault("transportProvider", transport_provider)
    receipt = _append_receipt(
        root,
        delivery_receipt_from_event(
            event,
            channel="telegram",
            destination=destination,
            transport_provider=transport_provider,
            producer=str(event.metadata.get("producer") or "mission_runtime"),
        ),
    )
    if dry_run:
        receipt.status = "delivered"
        receipt.delivery_url = f"dry_run://telegram/{destination}"
        return _update_receipt(root, receipt)

    if not token:
        receipt.status = "error"
        receipt.error_message = "telegram_bot_token_not_configured"
        return _update_receipt(root, receipt)

    payload: dict[str, Any] = {}
    last_error = ""
    for attempt in range(3):
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=json.dumps(
                {
                    "chat_id": destination,
                    "text": _format_telegram_message(event),
                    "parse_mode": "HTML",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            last_error = ""
            break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            receipt.retry_count = attempt + 1
            if attempt < 2:
                time.sleep(2**attempt)
    if last_error:
        receipt.status = "error"
        receipt.error_message = last_error
        return _update_receipt(root, receipt)

    if payload.get("ok"):
        receipt.status = "delivered"
        receipt.delivery_url = "https://api.telegram.org/bot***/sendMessage"
    else:
        receipt.status = "error"
        receipt.error_message = str(payload.get("description") or "unknown_telegram_error")
    return _update_receipt(root, receipt)


def send_watchdog_delivery_receipt(
    *,
    root: str | Path,
    report: dict[str, Any],
    destination: str = "",
    dry_run: bool = False,
    include_clear: bool = False,
) -> DeliveryReceipt:
    problem_report = report.get("problemReport") if isinstance(report.get("problemReport"), dict) else {}
    problem_count = int(problem_report.get("problemCount") or 0)
    if problem_count <= 0 and not include_clear:
        return _append_receipt(
            root,
            DeliveryReceipt(
                receipt_id=f"rcpt_{uuid.uuid4().hex[:12]}",
                mission_id="mission_watchdog",
                channel="telegram",
                destination=destination or _read_telegram_destination(root),
                event_kind="watchdog.problem_report",
                event_message="Watchdog clear notification skipped.",
                sent_at=utc_now_iso(),
                status="skipped",
                error_message="watchdog_clear_notification_disabled",
            ),
        )
    resolved_destination = str(destination or _read_telegram_destination(root)).strip()
    if not resolved_destination:
        return _append_receipt(
            root,
            DeliveryReceipt(
                receipt_id=f"rcpt_{uuid.uuid4().hex[:12]}",
                mission_id=str(
                    (problem_report.get("firstProblem") or {}).get("missionId")
                    if isinstance(problem_report.get("firstProblem"), dict)
                    else "mission_watchdog"
                )
                or "mission_watchdog",
                channel="telegram",
                destination="",
                event_kind="watchdog.problem_report",
                event_message="Watchdog notification could not be sent; no Telegram destination is configured.",
                sent_at=utc_now_iso(),
                status="skipped",
                error_message="telegram_destination_not_configured",
            ),
        )
    return send_telegram_delivery_receipt(
        _watchdog_event_from_report(report),
        destination=resolved_destination,
        root=root,
        dry_run=dry_run,
    )


def send_watchdog_ntfy_delivery_receipt(
    *,
    root: str | Path,
    report: dict[str, Any],
    topic: str = "",
    dry_run: bool = False,
    include_clear: bool = False,
) -> DeliveryReceipt:
    problem_report = report.get("problemReport") if isinstance(report.get("problemReport"), dict) else {}
    problem_count = int(problem_report.get("problemCount") or 0)
    if problem_count <= 0 and not include_clear:
        status = ntfy_status(root)
        return _append_receipt(
            root,
            DeliveryReceipt(
                receipt_id=f"rcpt_{uuid.uuid4().hex[:12]}",
                mission_id="mission_watchdog",
                channel="ntfy",
                destination=str(status.get("serverUrl") or ""),
                event_kind="watchdog.problem_report",
                event_message="Watchdog clear notification skipped.",
                sent_at=utc_now_iso(),
                status="skipped",
                error_message="watchdog_clear_notification_disabled",
            ),
        )
    event = _watchdog_event_from_report(report)
    return send_ntfy_delivery_receipt(
        event,
        root=root,
        topic=topic,
        title="Fluxio watchdog",
        priority="high" if problem_count else "default",
        tags="fluxio,watchdog",
        click_url="/control?mode=builder&surface=builder",
        dry_run=dry_run,
    )


def send_approval_escalation_receipt(
    *,
    mission_id: str,
    prompt: str,
    risk_level: str,
    escalation_policy: dict,
    root: str | Path,
    dry_run: bool = False,
) -> DeliveryReceipt:
    if not isinstance(escalation_policy, dict):
        escalation_policy = {}
    channel = str(escalation_policy.get("channel") or "").lower()
    destination = str(escalation_policy.get("destination") or "").strip()
    enabled = bool(escalation_policy.get("enabled"))
    if enabled and channel == "telegram" and destination:
        event = MissionEvent(
            mission_id=mission_id,
            kind="approval.required",
            message=prompt,
            metadata={"risk_level": risk_level, "channel": channel},
        )
        return send_telegram_delivery_receipt(
            event,
            destination=destination,
            root=root,
            dry_run=dry_run,
        )

    reason = "escalation_disabled" if not enabled else "no_telegram_destination"
    return _append_receipt(
        root,
        DeliveryReceipt(
            receipt_id=f"rcpt_{uuid.uuid4().hex[:12]}",
            mission_id=mission_id,
            channel=channel or "none",
            destination=destination,
            event_kind="approval.required",
            event_message=prompt,
            sent_at=utc_now_iso(),
            status="skipped",
            error_message=reason,
        ),
    )
