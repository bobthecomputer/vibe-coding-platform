from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from control_route_visual_smoke import find_browser, image_stats
from verify_authenticated_live_control import _api_url, _load_login

try:
    from playwright.async_api import async_playwright
except Exception as exc:  # pragma: no cover - environment guard
    async_playwright = None
    PLAYWRIGHT_IMPORT_ERROR = exc
else:
    PLAYWRIGHT_IMPORT_ERROR = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "https://sysnology.tail602108.ts.net:47880/control?mode=builder&surface=phone"


async def _verify_async(args: argparse.Namespace) -> dict:
    if async_playwright is None:
        return {
            "schema": "fluxio.authenticated_phone_progress.v1",
            "ok": False,
            "error": f"Playwright is required: {PLAYWRIGHT_IMPORT_ERROR}",
        }

    username, password = _load_login(Path(args.password_file), args.username, args.password)
    browser_path = find_browser(args.browser, args.browser_path)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = out_dir / f"{args.name}.png"
    dom_path = out_dir / f"{args.name}.html"
    report_path = out_dir / f"{args.name}-check.json"
    checks: list[dict] = []

    def record(check_id: str, passed: bool, detail: str, **extra: object) -> None:
        checks.append({"checkId": check_id, "passed": bool(passed), "detail": detail, **extra})

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=browser_path,
            headless=True,
            args=["--disable-gpu", "--no-sandbox"],
        )
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

        summary_response = await context.request.post(
            _api_url(args.url, "/api/backend"),
            data=json.dumps(
                {
                    "command": "get_control_room_summary_command",
                    "payload": {"payload": {"root": None, "summaryMode": "bootstrap"}},
                }
            ),
            headers={"Content-Type": "application/json"},
            timeout=args.timeout_ms,
        )
        summary_payload = await summary_response.json()
        summary = summary_payload.get("data", {}) if isinstance(summary_payload, dict) else {}
        missions = summary.get("missions", []) if isinstance(summary.get("missions"), list) else []
        notifications = summary.get("notifications", []) if isinstance(summary.get("notifications"), list) else []
        counts = summary.get("counts", {}) if isinstance(summary.get("counts"), dict) else {}
        running = [item for item in missions if item.get("status") == "running"]
        slice_notifications = [item for item in notifications if item.get("kind") == "mission_slice_completed"]
        running_titles = [str(item.get("title") or "") for item in running if str(item.get("title") or "").strip()]
        record(
            "summary-api-authenticated",
            summary_response.ok and summary_payload.get("ok") is not False and len(missions) > 0,
            "Authenticated browser context can read the NAS live summary for the phone progress view.",
            status=summary_response.status,
            missionCount=len(missions),
            runningMissionCount=len(running),
            notificationCount=len(notifications),
            sliceNotificationCount=len(slice_notifications),
        )

        page = await context.new_page()
        await page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout_ms)
        await page.wait_for_timeout(args.settle_ms)
        try:
            await page.wait_for_selector('[data-live-phone-progress="true"]', timeout=args.timeout_ms)
        except Exception:
            pass
        body_text = await page.locator("body").inner_text(timeout=args.timeout_ms)
        html = await page.content()
        lowered = body_text.lower()
        dom_path.write_text(html, encoding="utf-8")

        phone_surface_count = await page.locator('[data-live-phone-progress="true"]').count()
        mission_card_count = await page.locator('[data-phone-mission-card="true"]').count()
        notification_card_count = await page.locator('[data-phone-notification-card="true"]').count()
        notification_stack_count = await page.locator('[data-phone-notification-stack="true"]').count()
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
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--settle-ms", type=int, default=2200)
    parser.add_argument("--width", type=int, default=390)
    parser.add_argument("--height", type=int, default=844)
    parser.add_argument("--min-width", type=int, default=360)
    parser.add_argument("--min-height", type=int, default=640)
    parser.add_argument("--min-running", type=int, default=1)
    parser.add_argument("--min-notifications", type=int, default=3)
    parser.add_argument("--max-expected-titles", type=int, default=3)
    args = parser.parse_args(argv)
    result = asyncio.run(_verify_async(args))
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
