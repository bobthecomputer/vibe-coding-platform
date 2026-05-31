from __future__ import annotations

import json
import os
import urllib.request
import uuid
import base64
from dataclasses import asdict
from html import escape
from pathlib import Path
from typing import Any

from .models import DeliveryReceipt, MissionEvent, utc_now_iso

RECEIPTS_FILENAME = "delivery_receipts.jsonl"
WEB_PUSH_SUBSCRIPTIONS_FILENAME = "web_push_subscriptions.jsonl"
WEB_PUSH_VAPID_FILENAME = "web_push_vapid.json"


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


def web_push_status(root: str | Path | None = None) -> dict[str, Any]:
    vapid_config = _load_web_push_vapid_config(root) if root else {}
    public_key = _web_push_public_key(root)
    private_key = _web_push_private_key(root)
    dependency_available = _web_push_dependency_available()
    subscription_count = len(load_web_push_subscriptions(root)) if root else 0
    keys_configured = bool(public_key and private_key)
    return {
        "schema": "fluxio.web_push_status.v1",
        "configured": bool(public_key),
        "senderConfigured": bool(keys_configured and dependency_available),
        "dependencyAvailable": dependency_available,
        "privateKeyConfigured": bool(private_key),
        "localKeyConfigured": bool(vapid_config.get("publicKey") and vapid_config.get("privateKeyPem")),
        "configuredSource": _web_push_key_source(root),
        "setupPath": str(web_push_vapid_path(root)) if root else "",
        "publicKey": public_key,
        "subscriptionCount": subscription_count,
        "channel": "web_push",
        "nextAction": (
            "Closed-tab Web Push can send mission notifications."
            if keys_configured and dependency_available
            else "Install pywebpush and set FLUXIO_WEB_PUSH_PUBLIC_KEY plus FLUXIO_WEB_PUSH_PRIVATE_KEY before closed-tab push can send."
            if keys_configured and not dependency_available
            else "Set FLUXIO_WEB_PUSH_PRIVATE_KEY before closed-tab push can send."
            if public_key
            else "Provision VAPID keys from the notification stack or set FLUXIO_WEB_PUSH_PUBLIC_KEY and FLUXIO_WEB_PUSH_PRIVATE_KEY."
        ),
    }


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
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
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
    try:
        import pywebpush  # noqa: F401
    except Exception:
        return False
    return True


def _load_web_push_vapid_config(root: str | Path | None) -> dict[str, Any]:
    if not root:
        return {}
    try:
        payload = json.loads(web_push_vapid_path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _web_push_key_source(root: str | Path | None = None) -> str:
    if os.environ.get("FLUXIO_WEB_PUSH_PUBLIC_KEY") or os.environ.get("VAPID_PUBLIC_KEY"):
        return "environment"
    if root and _load_web_push_vapid_config(root).get("publicKey"):
        return "local_agent_control"
    return "missing"


def _web_push_private_key(root: str | Path | None = None) -> str:
    vapid_config = _load_web_push_vapid_config(root)
    return (
        os.environ.get("FLUXIO_WEB_PUSH_PRIVATE_KEY")
        or os.environ.get("VAPID_PRIVATE_KEY")
        or str(vapid_config.get("privateKeyPem") or vapid_config.get("privateKey") or "")
        or ""
    ).strip()


def _web_push_public_key(root: str | Path | None = None) -> str:
    vapid_config = _load_web_push_vapid_config(root)
    return (
        os.environ.get("FLUXIO_WEB_PUSH_PUBLIC_KEY")
        or os.environ.get("VAPID_PUBLIC_KEY")
        or str(vapid_config.get("publicKey") or "")
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


def _read_telegram_token() -> str:
    token = os.environ.get("SYNTELOS_TELEGRAM_BOT_TOKEN") or os.environ.get(
        "FLUXIO_TELEGRAM_BOT_TOKEN"
    )
    if token:
        return token.strip()
    for candidate in (
        Path.home() / ".agent_control" / "telegram_bot_token.txt",
        Path.home() / ".syntelos" / "telegram_bot_token.txt",
    ):
        try:
            if candidate.exists():
                return candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
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
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            rows.append(DeliveryReceipt(**json.loads(line)))
        except (TypeError, json.JSONDecodeError):
            continue
    return rows


def delivery_receipt_from_event(
    event: MissionEvent,
    *,
    channel: str,
    destination: str,
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
    return "\n".join(lines)


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
    receipt = _append_receipt(
        root,
        delivery_receipt_from_event(event, channel="telegram", destination=destination),
    )
    if dry_run:
        receipt.status = "delivered"
        receipt.delivery_url = f"dry_run://telegram/{destination}"
        return _update_receipt(root, receipt)

    token = _read_telegram_token()
    if not token:
        receipt.status = "error"
        receipt.error_message = "telegram_bot_token_not_configured"
        return _update_receipt(root, receipt)

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
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        receipt.status = "error"
        receipt.error_message = str(exc)
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
