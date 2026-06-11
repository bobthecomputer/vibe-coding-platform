from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from control_route_visual_smoke import browser_launch_diagnostics, find_browser_or_playwright_managed, image_stats
from verify_authenticated_live_control import _api_url, _display_title, _load_login

try:
    from playwright.async_api import async_playwright
except Exception as exc:  # pragma: no cover - environment guard
    async_playwright = None
    PLAYWRIGHT_IMPORT_ERROR = exc
else:
    PLAYWRIGHT_IMPORT_ERROR = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "https://sysnology.tail602108.ts.net:47880/control?mode=builder&surface=phone"


async def _summary_payload(context, url: str, timeout_ms: int) -> tuple[object, dict]:
    response = await context.request.post(
        _api_url(url, "/api/backend"),
        data=json.dumps(
            {
                "command": "get_control_room_summary_command",
                "payload": {"payload": {"root": None, "summaryMode": "bootstrap"}},
            }
        ),
        headers={"Content-Type": "application/json"},
        timeout=timeout_ms,
    )
    payload = await response.json()
    summary = payload.get("data", {}) if isinstance(payload, dict) else {}
    return response, summary if isinstance(summary, dict) else {}


async def _verify_async(args: argparse.Namespace) -> dict:
    if async_playwright is None:
        return {
            "schema": "fluxio.authenticated_phone_progress.v1",
            "ok": False,
            "error": f"Playwright is required: {PLAYWRIGHT_IMPORT_ERROR}",
        }

    username, password = _load_login(Path(args.password_file), args.username, args.password)
    browser_path = find_browser_or_playwright_managed(args.browser, args.browser_path)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = out_dir / f"{args.name}.png"
    dom_path = out_dir / f"{args.name}.html"
    report_path = out_dir / f"{args.name}-check.json"
    checks: list[dict] = []

    def record(check_id: str, passed: bool, detail: str, **extra: object) -> None:
        checks.append({"checkId": check_id, "passed": bool(passed), "detail": detail, **extra})

    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(
                executable_path=browser_path,
                headless=not args.headed,
                args=["--disable-gpu", "--no-sandbox"],
            )
        except Exception as exc:
            diagnostics = browser_launch_diagnostics(exc)
            record(
                "browser-launch",
                False,
                "Chromium could not start for authenticated phone-progress verification.",
                **diagnostics,
            )
            result = {
                "schema": "fluxio.authenticated_phone_progress.v1",
                "checkedAt": datetime.now(timezone.utc).isoformat(),
                "url": args.url,
                "ok": False,
                "checks": checks,
                "summary": {},
                "artifacts": {
                    "screenshotPath": str(screenshot_path),
                    "domPath": str(dom_path),
                    "reportPath": str(report_path),
                },
                "nextAction": str(diagnostics.get("nextAction") or "Fix browser launch before trusting NAS-local phone proof."),
            }
            report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            return result
        context = await browser.new_context(
            ignore_https_errors=True,
            viewport={"width": args.width, "height": args.height},
            is_mobile=True,
        )
        login_response = await context.request.post(
            _api_url(args.url, "/api/auth/login"),
            data=json.dumps({"username": username, "password": password}),
            headers={"Content-Type": "application/json"},
            timeout=args.timeout_ms,
        )
        record("account-login", login_response.ok, f"Login endpoint returned HTTP {login_response.status}.", status=login_response.status)

        summary_response, summary = await _summary_payload(context, args.url, args.timeout_ms)
        missions = summary.get("missions", []) if isinstance(summary.get("missions"), list) else []
        notifications = summary.get("notifications", []) if isinstance(summary.get("notifications"), list) else []
        counts = summary.get("counts", {}) if isinstance(summary.get("counts"), dict) else {}
        web_push_status = summary.get("webPushStatus", {}) if isinstance(summary.get("webPushStatus"), dict) else {}
        ntfy_status = summary.get("ntfyStatus", {}) if isinstance(summary.get("ntfyStatus"), dict) else {}
        running = [item for item in missions if item.get("status") == "running"]
        slice_notifications = [item for item in notifications if item.get("kind") == "mission_slice_completed"]
        running_titles = [_display_title(item.get("title") or "") for item in running if str(item.get("title") or "").strip()]
        record(
            "summary-api-authenticated",
            summary_response.ok and len(missions) > 0,
            "Authenticated browser context can read the NAS live summary for the phone progress view.",
            status=summary_response.status,
            missionCount=len(missions),
            runningMissionCount=len(running),
            notificationCount=len(notifications),
            sliceNotificationCount=len(slice_notifications),
        )
        record(
            "summary-web-push-status-live",
            web_push_status.get("schema") == "fluxio.web_push_status.v1"
            and bool(web_push_status.get("senderConfigured"))
            and bool(web_push_status.get("dependencyAvailable")),
            "Live summary exposes closed-tab Web Push sender status for phone setup.",
            senderConfigured=bool(web_push_status.get("senderConfigured")),
            dependencyAvailable=bool(web_push_status.get("dependencyAvailable")),
            subscriptionCount=int(web_push_status.get("subscriptionCount") or 0),
            nextAction=web_push_status.get("nextAction", ""),
        )
        record(
            "summary-ntfy-status-live",
            ntfy_status.get("schema") == "fluxio.ntfy_status.v1"
            and ntfy_status.get("channel") == "ntfy",
            "Live summary exposes ntfy phone push setup state for the open-source iOS notification path.",
            configured=bool(ntfy_status.get("configured")),
            senderConfigured=bool(ntfy_status.get("senderConfigured")),
            topic=ntfy_status.get("topic", ""),
            nextAction=ntfy_status.get("nextAction", ""),
        )

        parsed_url = urlparse(args.url)
        if args.register_web_push:
            await context.grant_permissions(["notifications"], origin=f"{parsed_url.scheme}://{parsed_url.netloc}")

        page = await context.new_page()
        await page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout_ms)
        await page.wait_for_timeout(args.settle_ms)
        try:
            await page.wait_for_selector('[data-live-phone-progress="true"]', timeout=args.timeout_ms)
        except Exception:
            pass

        registration_result = {}
        if args.register_web_push:
            initial_subscription_count = int(web_push_status.get("subscriptionCount") or 0)
            permission = await page.evaluate("() => (window.Notification && window.Notification.permission) || 'unsupported'")
            push_permission_state = await page.evaluate(
                """async () => {
                    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return 'unsupported';
                    try {
                        const registration = await navigator.serviceWorker.ready;
                        if (!registration.pushManager || !registration.pushManager.permissionState) return 'unavailable';
                        return await registration.pushManager.permissionState({ userVisibleOnly: true });
                    } catch (error) {
                        return `error:${String(error && error.message || error)}`;
                    }
                }"""
            )
            action_locator = page.locator('[data-phone-web-push-action="true"], [data-web-push-action="true"]').first
            action_count = await page.locator('[data-phone-web-push-action="true"], [data-web-push-action="true"]').count()
            if action_count > 0 and initial_subscription_count <= 0:
                try:
                    await action_locator.click(timeout=args.timeout_ms)
                    await page.wait_for_timeout(args.settle_ms)
                except Exception as exc:
                    registration_result["clickError"] = str(exc)
            browser_web_push_state = await page.evaluate(
                """() => {
                    const state = window.__fluxioWebPushState || window.__FLUXIO_WEB_PUSH_STATE || null;
                    if (state && typeof state === 'object') return state;
                    const marker = document.querySelector('[data-web-push-proof-status], [data-phone-web-push-status]');
                    return {
                        status: marker ? (marker.getAttribute('data-web-push-proof-status') || marker.getAttribute('data-phone-web-push-status') || '') : '',
                        text: marker ? marker.textContent : ''
                    };
                }"""
            )
            _, refreshed_summary = await _summary_payload(context, args.url, args.timeout_ms)
            refreshed_web_push_status = (
                refreshed_summary.get("webPushStatus", {})
                if isinstance(refreshed_summary.get("webPushStatus"), dict)
                else {}
            )
            refreshed_subscription_count = int(refreshed_web_push_status.get("subscriptionCount") or 0)
            record(
                "web-push-browser-registration",
                permission == "granted"
                and refreshed_subscription_count > 0
                and (action_count > 0 or initial_subscription_count > 0),
                "Phone verifier registered this authenticated browser with PushManager and the NAS counted the subscription.",
                permission=permission,
                pushPermissionState=push_permission_state,
                actionCount=action_count,
                initialSubscriptionCount=initial_subscription_count,
                subscriptionCount=refreshed_subscription_count,
                webPushStatus=refreshed_web_push_status.get("status", ""),
                browserWebPushState=browser_web_push_state,
                **registration_result,
            )
            if refreshed_web_push_status:
                summary = refreshed_summary
                missions = summary.get("missions", []) if isinstance(summary.get("missions"), list) else missions
                notifications = summary.get("notifications", []) if isinstance(summary.get("notifications"), list) else notifications
                counts = summary.get("counts", {}) if isinstance(summary.get("counts"), dict) else counts
                web_push_status = refreshed_web_push_status
                ntfy_status = (
                    summary.get("ntfyStatus", {})
                    if isinstance(summary.get("ntfyStatus"), dict)
                    else ntfy_status
                )
                running = [item for item in missions if item.get("status") == "running"]
                slice_notifications = [item for item in notifications if item.get("kind") == "mission_slice_completed"]
                running_titles = [_display_title(item.get("title") or "") for item in running if str(item.get("title") or "").strip()]

        body_text = await page.locator("body").inner_text(timeout=args.timeout_ms)
        html = await page.content()
        lowered = body_text.lower()
        dom_path.write_text(html, encoding="utf-8")

        phone_surface_count = await page.locator('[data-live-phone-progress="true"]').count()
        mission_card_count = await page.locator('[data-phone-mission-card="true"]').count()
        notification_card_count = await page.locator('[data-phone-notification-card="true"]').count()
        notification_stack_count = await page.locator('[data-phone-notification-stack="true"]').count()
        phone_web_push_proof_count = await page.locator('[data-phone-web-push-proof="true"]').count()
        phone_ntfy_proof_count = await page.locator('[data-phone-ntfy-proof="true"]').count()
        phone_web_push_status = ""
        phone_web_push_text = ""
        phone_ntfy_status = ""
        phone_ntfy_text = ""
        if phone_web_push_proof_count > 0:
            try:
                phone_web_push_status = await page.locator(
                    '[data-phone-web-push-proof="true"]'
                ).first.get_attribute("data-phone-web-push-status", timeout=args.timeout_ms) or ""
                phone_web_push_text = await page.locator(
                    '[data-phone-web-push-proof="true"]'
                ).first.inner_text(timeout=args.timeout_ms)
            except Exception:
                phone_web_push_status = ""
                phone_web_push_text = ""
        if phone_ntfy_proof_count > 0:
            try:
                phone_ntfy_status = await page.locator(
                    '[data-phone-ntfy-proof="true"]'
                ).first.get_attribute("data-phone-ntfy-status", timeout=args.timeout_ms) or ""
                phone_ntfy_text = await page.locator(
                    '[data-phone-ntfy-proof="true"]'
                ).first.inner_text(timeout=args.timeout_ms)
            except Exception:
                phone_ntfy_status = ""
                phone_ntfy_text = ""
        visible_running_titles = [title for title in running_titles[: args.max_expected_titles] if title.lower() in lowered]
        record(
            "phone-progress-surface-visible",
            phone_surface_count == 1 and "phone progress" in lowered and (mission_card_count > 0 or notification_card_count > 0),
            "Authenticated phone route renders a compact live progress surface backed by NAS mission rows.",
            phoneSurfaceCount=phone_surface_count,
            missionCardCount=mission_card_count,
            notificationCardCount=notification_card_count,
        )
        record(
            "phone-running-missions-visible",
            mission_card_count >= min(args.min_running, max(1, len(running))) and len(visible_running_titles) >= min(1, len(running_titles)),
            "Phone progress view shows live running mission cards from the NAS summary.",
            missionCardCount=mission_card_count,
            expectedTitles=running_titles[: args.max_expected_titles],
            visibleTitles=visible_running_titles,
        )
        record(
            "phone-notifications-visible",
            notification_stack_count == 1 and notification_card_count >= min(args.min_notifications, len(notifications)),
            "Phone progress view shows live notification cards without requiring the full desktop notification stack.",
            notificationStackCount=notification_stack_count,
            notificationCardCount=notification_card_count,
            notificationCount=len(notifications),
            sliceNotificationCount=len(slice_notifications),
        )
        expected_phone_push_status = (
            "ready"
            if int(web_push_status.get("subscriptionCount") or 0) > 0 and web_push_status.get("senderConfigured")
            else "needs_subscription"
            if web_push_status.get("senderConfigured")
            else "needs_sender"
        )
        record(
            "phone-web-push-proof-visible",
            phone_web_push_proof_count == 1
            and phone_web_push_status == expected_phone_push_status
            and "closed-tab push" in phone_web_push_text.lower()
            and (
                "sender ready" in phone_web_push_text.lower()
                or "closed-tab push is registered" in phone_web_push_text.lower()
                or "provision web push sender" in phone_web_push_text.lower()
            ),
            "Phone progress view shows the live closed-tab Web Push setup state and next action.",
            proofCount=phone_web_push_proof_count,
            expectedStatus=expected_phone_push_status,
            domStatus=phone_web_push_status,
            proofText=phone_web_push_text[:520],
            senderConfigured=bool(web_push_status.get("senderConfigured")),
            subscriptionCount=int(web_push_status.get("subscriptionCount") or 0),
        )
        expected_ntfy_status = "ready" if ntfy_status.get("senderConfigured") else "needs_topic"
        record(
            "phone-ntfy-proof-visible",
            phone_ntfy_proof_count == 1
            and phone_ntfy_status == expected_ntfy_status
            and "ntfy phone push" in phone_ntfy_text.lower()
            and (
                "open-source ios channel ready" in phone_ntfy_text.lower()
                or "configure ntfy topic" in phone_ntfy_text.lower()
            ),
            "Phone progress view shows the live ntfy setup state for the open-source iOS push path.",
            proofCount=phone_ntfy_proof_count,
            expectedStatus=expected_ntfy_status,
            domStatus=phone_ntfy_status,
            proofText=phone_ntfy_text[:520],
            senderConfigured=bool(ntfy_status.get("senderConfigured")),
            topicConfigured=bool(ntfy_status.get("configured")),
        )
        record(
            "phone-live-only-copy",
            "no fallback notification cards" in lowered or "live data only" in lowered or "slice" in lowered,
            "Phone progress route exposes live-data-only language and does not silently fall back to fixtures.",
        )
        forbidden = [
            "checkout qa",
            "market research",
            "landing polish",
            "image variants",
            "fixture layout preview",
            "sample mission",
        ]
        leaked = [item for item in forbidden if item in lowered]
        record("no-demo-data-visible", not leaked, "Authenticated phone progress DOM does not expose known demo/fallback labels.", leakedLabels=leaked)

        await page.screenshot(path=str(screenshot_path), full_page=True)
        stats = image_stats(screenshot_path, min_width=args.min_width, min_height=args.min_height)
        record(
            "screenshot-nonblank",
            bool(stats.get("nonBlank")),
            "Authenticated phone progress screenshot is nonblank and meets mobile dimensions.",
            imageStats=stats,
            screenshotPath=str(screenshot_path),
            domPath=str(dom_path),
        )
        await browser.close()

    result = {
        "schema": "fluxio.authenticated_phone_progress.v1",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "url": args.url,
        "ok": all(item["passed"] for item in checks),
        "checks": checks,
        "summary": {
            "generatedAt": summary.get("generatedAt") if isinstance(summary, dict) else "",
            "counts": counts,
            "missionCount": len(missions),
            "runningMissionCount": len(running),
            "notificationCount": len(notifications),
            "sliceNotificationCount": len(slice_notifications),
            "webPushSenderConfigured": bool(web_push_status.get("senderConfigured")),
            "webPushSubscriptionCount": int(web_push_status.get("subscriptionCount") or 0),
            "ntfySenderConfigured": bool(ntfy_status.get("senderConfigured")),
            "ntfyTopicConfigured": bool(ntfy_status.get("configured")),
        },
        "artifacts": {
            "screenshotPath": str(screenshot_path),
            "domPath": str(dom_path),
            "reportPath": str(report_path),
        },
    }
    report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify authenticated Fluxio phone progress route renders live NAS data.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--out-dir", default=str(ROOT / "tmp-ui-checks" / "authenticated-phone-progress"))
    parser.add_argument("--name", default="authenticated-phone-progress")
    parser.add_argument("--username", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--password-file", default=str(ROOT / ".agent_control" / "grand_agent_admin_password.txt"))
    parser.add_argument("--browser", choices=["auto", "chrome", "chromium", "edge", "zen"], default="auto")
    parser.add_argument("--browser-path", default="")
    parser.add_argument("--headed", action="store_true", help="Run Chromium in headed mode for PushManager registration checks that fail in headless browsers.")
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--settle-ms", type=int, default=2200)
    parser.add_argument("--width", type=int, default=390)
    parser.add_argument("--height", type=int, default=844)
    parser.add_argument("--min-width", type=int, default=360)
    parser.add_argument("--min-height", type=int, default=640)
    parser.add_argument("--min-running", type=int, default=1)
    parser.add_argument("--min-notifications", type=int, default=3)
    parser.add_argument("--max-expected-titles", type=int, default=3)
    parser.add_argument(
        "--register-web-push",
        action="store_true",
        help="Grant notification permission, click the phone Web Push registration action, and require the NAS subscription count to increase above zero.",
    )
    args = parser.parse_args(argv)
    result = asyncio.run(_verify_async(args))
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
