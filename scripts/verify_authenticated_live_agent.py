from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

from control_route_visual_smoke import browser_launch_diagnostics, find_browser_or_playwright_managed, image_stats

try:
    from playwright.async_api import async_playwright
except Exception as exc:  # pragma: no cover - environment guard
    async_playwright = None
    PLAYWRIGHT_IMPORT_ERROR = exc
else:
    PLAYWRIGHT_IMPORT_ERROR = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "https://sysnology.tail602108.ts.net:47880/control?mode=agent&surface=agent&agentScene=run"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _load_login(password_file: Path, username: str = "", password: str = "") -> tuple[str, str]:
    if username and password:
        return username, password
    text = _read_text(password_file)
    next_username = username
    next_password = password
    for line in text.splitlines():
        if not next_username:
            match = re.match(r"\s*Username:\s*(.+?)\s*$", line, flags=re.IGNORECASE)
            if match:
                next_username = match.group(1).strip()
        if not next_password:
            match = re.match(r"\s*Password:\s*(.+?)\s*$", line, flags=re.IGNORECASE)
            if match:
                next_password = match.group(1).strip()
    if not next_username:
        account = json.loads(_read_text(ROOT / ".agent_control" / "grand_agent_web_admin.json") or "{}")
        next_username = str(account.get("username") or "admin")
    if not next_username or not next_password:
        raise RuntimeError("Missing Fluxio account username or password for authenticated live-Agent verification.")
    return next_username, next_password


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def _api_url(url: str, path: str) -> str:
    return urljoin(_origin(url) + "/", path.lstrip("/"))


def _agent_url(url: str, mission_id: str) -> str:
    parts = urlsplit(url)
    query = urlencode(
        {
            "mode": "agent",
            "surface": "agent",
            "agentScene": "run",
            "missionId": mission_id,
        }
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/control", query, ""))


def _workbench_url(url: str, mission_id: str) -> str:
    parts = urlsplit(url)
    query = urlencode(
        {
            "mode": "agent",
            "surface": "workbench",
            "agentScene": "run",
            "missionId": mission_id,
        }
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/control", query, ""))


def _mission_id(item: dict) -> str:
    return str(item.get("mission_id") or item.get("missionId") or item.get("id") or "")


def _mission_title(item: dict) -> str:
    return str(item.get("title") or item.get("objective") or item.get("mission_id") or "")


async def _fetch_mission_detail(context, base_url: str, mission_id: str, timeout_ms: int) -> dict:
    if not mission_id:
        return {}
    last_error: Exception | None = None
    response = None
    for attempt in range(3):
        try:
            response = await context.request.post(
                _api_url(base_url, "/api/backend"),
                data=json.dumps(
                    {
                        "command": "get_control_room_mission_detail_command",
                        "payload": {
                            "payload": {
                                "root": None,
                                "missionId": mission_id,
                                "eventLimit": 80,
                            }
                        },
                    }
                ),
                headers={"Content-Type": "application/json"},
                timeout=timeout_ms,
            )
            break
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(0.8 * (attempt + 1))
    if response is None:
        raise last_error or RuntimeError("Mission detail request failed.")
    payload = await response.json()
    detail = payload.get("data", {}) if isinstance(payload, dict) else {}
    if not isinstance(detail, dict):
        detail = {}
    detail["_httpStatus"] = response.status
    detail["_httpOk"] = response.ok and payload.get("ok") is not False if isinstance(payload, dict) else response.ok
    return detail


def _mission_detail_needles(detail: dict, fallback_title: str) -> list[str]:
    needles: list[str] = []
    for value in (
        fallback_title,
        detail.get("summary", {}).get("title") if isinstance(detail.get("summary"), dict) else "",
        detail.get("mission", {}).get("title") if isinstance(detail.get("mission"), dict) else "",
    ):
        text = str(value or "").strip()
        if len(text) >= 8 and text not in needles:
            needles.append(text)
    for message in detail.get("agentMessages", []) if isinstance(detail.get("agentMessages"), list) else []:
        if not isinstance(message, dict):
            continue
        for key in ("title", "detail"):
            text = str(message.get(key) or "").strip()
            if len(text) >= 12 and text not in needles:
                needles.append(text)
                break
    for event in detail.get("events", []) if isinstance(detail.get("events"), list) else []:
        if not isinstance(event, dict):
            continue
        text = str(event.get("message") or event.get("detail") or "").strip()
        if len(text) >= 12 and text not in needles:
            needles.append(text)
        if len(needles) >= 8:
            break
    return needles[:8]


def _collapse_text(value: object) -> str:
    return " ".join(str(value or "").lower().split())


def _display_text(value: object) -> str:
    return (
        str(value or "")
        .replace("system-loss improvement mission", "system improvement mission")
        .replace("system loss improvement mission", "system improvement mission")
        .replace("System-loss improvement mission", "System improvement mission")
        .replace("System loss improvement mission", "System improvement mission")
        .replace("system-loss", "system improvement")
        .replace("system loss", "system improvement")
        .replace("System-loss", "System improvement")
        .replace("System loss", "System improvement")
    )


async def _main_agent_text(page, timeout_ms: int) -> str:
    selectors = [
        ".fluxos-agent-main",
        ".agent-chat-stage",
        ".reference-agent-run",
        "main",
        "body",
    ]
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if await locator.count() > 0:
                return await locator.inner_text(timeout=timeout_ms)
        except Exception:
            continue
    return await page.locator("body").inner_text(timeout=timeout_ms)


def _requested_mission_id(url: str, explicit: str) -> str:
    explicit = str(explicit or "").strip()
    if explicit:
        return explicit
    query = parse_qs(urlsplit(url).query)
    values = query.get("missionId") or query.get("mission_id") or []
    return str(values[0] if values else "").strip()


def _pick_mission(missions: list[dict], requested_mission_id: str) -> dict:
    if requested_mission_id:
        for item in missions:
            if _mission_id(item) == requested_mission_id:
                return item
        return {
            "mission_id": requested_mission_id,
            "title": requested_mission_id,
            "status": "requested_missing",
            "requestedMissing": True,
        }
    running = [
        item
        for item in missions
        if item.get("status") == "running" or item.get("planner_loop_status") == "running"
    ]
    active = [
        item
        for item in missions
        if str(item.get("status") or "").lower() not in {"completed", "failed", "cancelled"}
    ]
    return (running or active or missions or [{}])[0]


async def _verify_async(args: argparse.Namespace) -> dict:
    if async_playwright is None:
        return {
            "schema": "fluxio.authenticated_live_agent.v1",
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
                headless=True,
                args=["--disable-gpu", "--no-sandbox"],
            )
        except Exception as exc:
            diagnostics = browser_launch_diagnostics(exc)
            record(
                "browser-launch",
                False,
                "Chromium could not start for authenticated live-Agent verification.",
                **diagnostics,
            )
            result = {
                "schema": "fluxio.authenticated_live_agent.v1",
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
                "nextAction": str(diagnostics.get("nextAction") or "Fix browser launch before trusting NAS-local Agent proof."),
            }
            report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            return result
        context = await browser.new_context(
            ignore_https_errors=True,
            viewport={"width": args.width, "height": args.height},
        )
        login_response = await context.request.post(
            _api_url(args.url, "/api/auth/login"),
            data=json.dumps({"username": username, "password": password}),
            headers={"Content-Type": "application/json"},
            timeout=args.timeout_ms,
        )
        record(
            "account-login",
            login_response.ok,
            f"Login endpoint returned HTTP {login_response.status}.",
            status=login_response.status,
        )

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
        summary_response_payload = await summary_response.json()
        summary_payload = {
            "status": summary_response.status,
            "ok": summary_response.ok and summary_response_payload.get("ok") is not False,
            "payload": summary_response_payload,
        }
        summary = summary_payload.get("payload", {}).get("data", {}) if isinstance(summary_payload, dict) else {}
        counts = summary.get("counts", {}) if isinstance(summary, dict) else {}
        missions = summary.get("missions", []) if isinstance(summary, dict) and isinstance(summary.get("missions"), list) else []
        notifications = summary.get("notifications", []) if isinstance(summary, dict) and isinstance(summary.get("notifications"), list) else []
        running = [item for item in missions if item.get("status") == "running"]
        active = [
            item
            for item in missions
            if str(item.get("status") or "").lower() not in {"completed", "failed", "cancelled"}
        ]
        slice_notifications = [item for item in notifications if item.get("kind") == "mission_slice_completed"]
        requested_mission_id = _requested_mission_id(args.url, args.mission_id)
        selected = _pick_mission(missions, requested_mission_id)
        selected_mission_id = _mission_id(selected)
        selected_detail = await _fetch_mission_detail(
            context,
            args.url,
            selected_mission_id,
            args.timeout_ms,
        )
        detail_mission = selected_detail.get("mission", {}) if isinstance(selected_detail.get("mission"), dict) else {}
        detail_state = selected_detail.get("state", {}) if isinstance(selected_detail.get("state"), dict) else {}
        detail_summary = selected_detail.get("summary", {}) if isinstance(selected_detail.get("summary"), dict) else {}
        detail_title = str(detail_mission.get("title") or detail_summary.get("title") or "").strip()
        detail_status = str(detail_state.get("status") or detail_mission.get("status") or "").strip()
        detail_runtime = str(detail_mission.get("runtime_id") or detail_mission.get("runtimeId") or "").strip()
        detail_confirms_requested = (
            bool(selected_detail.get("_httpOk"))
            and selected_detail.get("missionId") == selected_mission_id
            and bool(detail_title or selected_detail.get("agentMessages") or selected_detail.get("events"))
        )
        if selected.get("requestedMissing") and detail_confirms_requested:
            selected = {
                **selected,
                "title": detail_title or selected_mission_id,
                "status": detail_status or selected.get("status"),
                "runtime_id": detail_runtime or selected.get("runtime_id"),
                "planner_loop_status": detail_state.get("planner_loop_status") or selected.get("planner_loop_status"),
                "requestedMissing": False,
                "resolvedFromDetail": True,
            }
        selected_title = _mission_title(selected)
        record(
            "summary-api-authenticated",
            bool(summary_payload.get("ok")) and len(missions) > 0,
            "Authenticated browser context can read the NAS control-room summary before opening Agent.",
            status=summary_payload.get("status"),
            missionCount=len(missions),
        )
        record(
            "selected-live-mission",
            bool(selected_mission_id) and not selected.get("requestedMissing"),
            "Verifier selected a current NAS mission for the Agent detail route, using the live detail endpoint when the compact summary omits a completed requested mission.",
            requestedMissionId=requested_mission_id,
            missionId=selected_mission_id,
            title=selected_title,
            status=selected.get("status"),
            plannerLoopStatus=selected.get("planner_loop_status"),
            resolvedFromDetail=bool(selected.get("resolvedFromDetail")),
        )
        selected_needles = _mission_detail_needles(selected_detail, selected_title)
        record(
            "selected-mission-detail-api",
            bool(selected_detail.get("_httpOk")) and selected_detail.get("missionId") == selected_mission_id,
            "Authenticated verifier can fetch the selected mission's live detail endpoint.",
            status=selected_detail.get("_httpStatus"),
            missionId=selected_detail.get("missionId"),
            agentMessageCount=len(selected_detail.get("agentMessages", []) if isinstance(selected_detail.get("agentMessages"), list) else []),
            eventCount=len(selected_detail.get("events", []) if isinstance(selected_detail.get("events"), list) else []),
        )

        page = await context.new_page()
        if selected_mission_id:
            await page.goto(_agent_url(args.url, selected_mission_id), wait_until="commit", timeout=args.timeout_ms)
            await page.wait_for_timeout(args.settle_ms)
            try:
                await page.wait_for_function(
                    """
                    missionId => {
                      const bodyText = document.body?.innerText || "";
                      const taggedRows = document.querySelectorAll(`[data-mission-id="${missionId}"]`).length;
                      return taggedRows >= 2 && !bodyText.toLowerCase().includes("sign in to fluxio");
                    }
                    """,
                    selected_mission_id,
                    timeout=max(args.settle_ms, 10000),
                )
            except Exception:
                # Keep recording the concrete failure below; this wait only prevents
                # false negatives while the live mission detail request is hydrating.
                pass
        else:
            await page.goto(args.url, wait_until="commit", timeout=args.timeout_ms)
            await page.wait_for_timeout(args.settle_ms)

        body_text = await page.locator("body").inner_text(timeout=args.timeout_ms)
        main_text = await _main_agent_text(page, args.timeout_ms)
        dom_text = await page.content()
        lowered = body_text.lower()
        dom_lowered = dom_text.lower()
        title_visible = bool(
            selected_title
            and _display_text(selected_title).lower() in _display_text(body_text).lower()
        )
        selected_message_count = await page.locator(f'[data-mission-id="{selected_mission_id}"]').count() if selected_mission_id else 0
        if selected_mission_id and (selected_message_count == 0 or not title_visible):
            try:
                await page.wait_for_selector(
                    f'.fluxos-thread .fluxos-message[data-mission-id="{selected_mission_id}"]',
                    timeout=max(args.timeout_ms, args.settle_ms),
                )
                body_text = await page.locator("body").inner_text(timeout=args.timeout_ms)
                main_text = await _main_agent_text(page, args.timeout_ms)
                dom_text = await page.content()
                lowered = body_text.lower()
                dom_lowered = dom_text.lower()
                title_visible = bool(
                    selected_title
                    and _display_text(selected_title).lower() in _display_text(body_text).lower()
                )
                selected_message_count = await page.locator(f'[data-mission-id="{selected_mission_id}"]').count()
            except Exception:
                # The concrete checks below will preserve the failure details.
                pass
        normalized_main_text = _display_text(main_text).lower()
        selected_needles_visible = [
            item for item in selected_needles if item and _display_text(item).lower() in normalized_main_text
        ]
        selected_empty_dialogue_state = (
            "no real hermes dialogue yet" in lowered
            or "no real hermes dialogue is attached to this mission yet" in lowered
            or "no hermes chat reply yet" in lowered
            or "no hermes chat transcript is attached for this mission" in lowered
        )
        record(
            "not-login-screen",
            "sign in to fluxio" not in lowered,
            "Authenticated Agent route rendered beyond the login screen.",
        )
        record(
            "selected-mission-visible-in-agent",
            title_visible or bool(selected_mission_id and selected_mission_id.lower() in lowered),
            "The selected live mission is visible in the Agent surface.",
            missionId=selected_mission_id,
            title=selected_title,
        )
        record(
            "selected-mission-specific-thread",
            (selected_message_count > 0 and bool(selected_needles_visible))
            or (selected_empty_dialogue_state and title_visible),
            "Agent shows selected mission-scoped dialogue rows, or the selected mission with an honest empty dialogue state.",
            missionId=selected_mission_id,
            taggedMessageCount=selected_message_count,
            emptyDialogueState=selected_empty_dialogue_state,
            matchedNeedles=selected_needles_visible[:3],
            candidateNeedles=selected_needles[:5],
        )
        visible_turn_rows = page.locator('.fluxos-agent-main [data-message-zone="thread"][data-turn-id][role="button"]')
        visible_turn_count = await visible_turn_rows.count()
        unscoped_visible_turn_count = await page.locator(
            f'.fluxos-agent-main [data-message-zone="thread"][data-turn-id][role="button"]:not([data-mission-id="{selected_mission_id}"])'
        ).count() if selected_mission_id else 0
        record(
            "live-agent-thread-is-mission-scoped",
            not selected_mission_id or unscoped_visible_turn_count == 0,
            "Every selectable live Agent report row is scoped to the selected mission instead of inheriting old untagged transcript rows.",
            missionId=selected_mission_id,
            visibleTurnRows=visible_turn_count,
            unscopedVisibleTurnRows=unscoped_visible_turn_count,
        )
        operations_brief_count = await page.locator('[data-live-operations-brief="true"]').count()
        operations_brief_text = ""
        if operations_brief_count > 0:
            try:
                operations_brief_text = await page.locator('[data-live-operations-brief="true"]').first.inner_text(timeout=args.timeout_ms)
            except Exception:
                operations_brief_text = ""
        record(
            "live-agent-operations-brief-visible",
            operations_brief_count > 0
            and _display_text(selected_title).lower() in _display_text(operations_brief_text).lower()
            and "alerts" in operations_brief_text.lower()
            and "queue" in operations_brief_text.lower(),
            "Agent shows a compact live operations brief with selected mission, queue, and notification state from live NAS data.",
            missionId=selected_mission_id,
            operationsBriefCount=operations_brief_count,
            operationsBriefText=operations_brief_text[:280],
        )
        if not args.expanded_interactions:
            await page.screenshot(path=str(screenshot_path), full_page=False, timeout=args.timeout_ms)
            dom_path.write_text(dom_text, encoding="utf-8")
            stats = image_stats(screenshot_path, min_width=args.min_width, min_height=args.min_height)
            record(
                "screenshot-nonblank",
                bool(stats.get("nonBlank")),
                "Authenticated live Agent screenshot is nonblank and meets minimum dimensions.",
                imageStats=stats,
                screenshotPath=str(screenshot_path),
                domPath=str(dom_path),
            )
            await browser.close()
            redacted_summary = {
                "generatedAt": summary.get("generatedAt") if isinstance(summary, dict) else "",
                "counts": counts,
                "runtimeCounts": summary.get("runtimeCounts", {}) if isinstance(summary, dict) else {},
                "statusCounts": summary.get("statusCounts", {}) if isinstance(summary, dict) else {},
                "notificationCount": len(notifications),
                "sliceNotificationCount": len(slice_notifications),
                "selectedMission": {
                    "mission_id": selected_mission_id,
                    "title": selected_title,
                    "runtime_id": selected.get("runtime_id"),
                    "status": selected.get("status"),
                    "planner_loop_status": selected.get("planner_loop_status"),
                },
                "runningMissions": [
                    {
                        "mission_id": item.get("mission_id"),
                        "title": item.get("title"),
                        "runtime_id": item.get("runtime_id"),
                        "status": item.get("status"),
                        "planner_loop_status": item.get("planner_loop_status"),
                    }
                    for item in running
                ],
                "mode": "bounded_core_proof",
            }
            ok = all(item["passed"] for item in checks)
            result = {
                "schema": "fluxio.authenticated_live_agent.v1",
                "checkedAt": datetime.now(timezone.utc).isoformat(),
                "url": _agent_url(args.url, selected_mission_id) if selected_mission_id else args.url,
                "ok": ok,
                "checks": checks,
                "summary": redacted_summary,
                "artifacts": {
                    "screenshotPath": str(screenshot_path),
                    "domPath": str(dom_path),
                    "reportPath": str(report_path),
                },
                "nextAction": (
                    "Authenticated live Agent route renders current NAS mission detail and messages."
                    if ok
                    else "Fix failed authenticated live-Agent core checks before trusting Builder-to-Agent mission drill-down."
                ),
            }
            report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            return result
        try:
            details_button = page.locator('[data-agent-clarity-switch="true"] button', has_text="Details").first
            if await details_button.count() > 0:
                await details_button.click(timeout=args.timeout_ms)
                await page.wait_for_selector(
                    '.fluxos-agent-grid[data-agent-clarity-mode="full"]',
                    timeout=max(args.settle_ms, 12000),
                )
        except Exception:
            pass
        notification_card_count = await page.locator('[data-notification-card="true"]').count()
        inline_dismiss_count = await page.locator('[data-notification-dismiss-inline="true"]').count()
        clear_all_count = await page.locator('[data-notification-clear-all="true"]').count()
        restore_count = await page.locator('[data-notification-restore-dismissed="true"]').count()
        record(
            "live-agent-notification-dismiss-control",
            notification_card_count > 0 and inline_dismiss_count > 0 and clear_all_count == 1 and restore_count == 1,
            "Agent notification stack exposes per-update dismiss, mark-visible-read, and restore controls.",
            notificationCardCount=notification_card_count,
            inlineDismissButtonCount=inline_dismiss_count,
            clearAllControlCount=clear_all_count,
            restoreControlCount=restore_count,
        )
        dismiss_after_count = notification_card_count
        restore_after_count = notification_card_count
        restore_was_enabled = False
        if inline_dismiss_count > 0:
            try:
                await page.locator('[data-notification-dismiss-inline="true"]').first.click(timeout=args.timeout_ms)
                await page.wait_for_timeout(400)
                dismiss_after_count = await page.locator('[data-notification-card="true"]').count()
                restore_button = page.locator('[data-notification-restore-dismissed="true"]').first
                restore_was_enabled = restore_count > 0 and not await restore_button.is_disabled(timeout=args.timeout_ms)
                if restore_was_enabled:
                    await restore_button.click(timeout=args.timeout_ms)
                    await page.wait_for_timeout(400)
                    restore_after_count = await page.locator('[data-notification-card="true"]').count()
            except Exception:
                restore_was_enabled = False
        record(
            "live-agent-notification-dismiss-and-restore",
            notification_card_count > 0
            and dismiss_after_count < notification_card_count
            and restore_was_enabled
            and restore_after_count >= notification_card_count,
            "Clicking a live Agent notification dismisses it from the stack and Restore brings dismissed updates back.",
            beforeCount=notification_card_count,
            afterDismissCount=dismiss_after_count,
            restoreWasEnabled=restore_was_enabled,
            afterRestoreCount=restore_after_count,
        )
        try:
            live_button = page.locator('[data-agent-clarity-switch="true"] button', has_text="Live").first
            if await live_button.count() > 0:
                await live_button.click(timeout=args.timeout_ms)
                await page.wait_for_selector(
                    '.fluxos-agent-grid[data-agent-clarity-mode="focus"]',
                    timeout=max(args.settle_ms, 12000),
                )
        except Exception:
            pass
        thread_first_band = page.locator('[data-live-agent-thread-first-band="true"]').first
        thread_first_band_count = await page.locator('[data-live-agent-thread-first-band="true"]').count()
        thread_first_text = ""
        thread_first_order = {}
        if thread_first_band_count > 0:
            try:
                thread_first_text = await thread_first_band.inner_text(timeout=args.timeout_ms)
            except Exception:
                thread_first_text = ""
            try:
                thread_first_order = await page.evaluate(
                    """
                    () => {
                      const orderFor = selector => {
                        const node = document.querySelector(selector);
                        if (!node) return null;
                        const raw = window.getComputedStyle(node).order;
                        const parsed = Number.parseInt(raw, 10);
                        return Number.isFinite(parsed) ? parsed : 0;
                      };
                        return {
                        band: orderFor('[data-live-agent-thread-first-band="true"]'),
                        proofBrief: orderFor('[data-live-agent-proof-brief="true"]'),
                        selectedReport: orderFor('[data-live-selected-report-reader="true"]'),
                        thread: orderFor('.fluxos-thread'),
                        composer: orderFor('.fluxos-agent-main > .fluxos-composer'),
                        diagnostics: orderFor('[data-agent-advanced-drawer-kind="runtime"]'),
                        lane: orderFor('[data-agent-advanced-drawer-kind="runtime"]'),
                        thinking: orderFor('[data-agent-advanced-drawer-kind="runtime"]'),
                        plan: orderFor('[data-agent-advanced-drawer-kind="plan"]'),
                      };
                    }
                    """
                )
            except Exception:
                thread_first_order = {}
        thread_first_order_safe = {
            key: value if isinstance(value, (int, float)) else 99
            for key, value in (thread_first_order or {}).items()
        }
        record(
            "live-agent-thread-first-band-visible",
            thread_first_band_count == 1
            and "mission controls" in thread_first_text.lower()
            and all(token in thread_first_text.lower() for token in ["continue", "modify", "launch", "verify", "summarize"])
            and (
                not thread_first_order_safe
                or (
                    thread_first_order_safe.get("thread", 99) < thread_first_order_safe.get("band", 99)
                    < thread_first_order_safe.get("composer", 99)
                    < thread_first_order_safe.get("proofBrief", 99)
                    < thread_first_order_safe.get("selectedReport", 99)
                    < thread_first_order_safe.get("diagnostics", 99)
                    <= thread_first_order_safe.get("lane", 99)
                    <= thread_first_order_safe.get("thinking", 99)
                    < thread_first_order_safe.get("plan", 99)
                )
            ),
            "Agent renders the cleaned Agent Live flow: mission dialogue, compact mission controls, composer, then detail evidence and diagnostics.",
            commandBandCount=thread_first_band_count,
            commandBandText=thread_first_text[:280],
            visualOrder=thread_first_order,
            visualOrderSafe=thread_first_order_safe,
        )
        agent_launch_action_count = await page.locator('[data-live-agent-launch-action="true"]').count()
        record(
            "live-agent-launch-action-visible",
            agent_launch_action_count == 1,
            "Agent Live exposes direct mission launch from the Agent Live command band.",
            launchActionCount=agent_launch_action_count,
        )
        agent_workflow_actions = ["continue", "modify", "launch", "verify", "summarize", "preview"]
        agent_workflow_action_counts = {}
        for action_id in agent_workflow_actions:
            agent_workflow_action_counts[action_id] = await page.locator(
                f'[data-live-agent-action="{action_id}"]'
            ).count()
        record(
            "live-agent-workflow-actions-visible",
            all(agent_workflow_action_counts.get(action_id) == 1 for action_id in agent_workflow_actions),
            "Agent Live exposes Continue, Modify, Launch, Verify, Summarize, and in-Agent Preview controls in the Agent Live command band.",
            actionCounts=agent_workflow_action_counts,
        )

        async def verify_agent_draft_action(
            action_id: str,
            check_id: str,
            expected_fragments: list[str],
        ) -> None:
            action_page = await context.new_page()
            try:
                await action_page.goto(_agent_url(args.url, selected_mission_id), wait_until="commit", timeout=args.timeout_ms)
                await action_page.wait_for_timeout(max(900, min(args.settle_ms, 2200)))
                selector = f'[data-live-agent-action="{action_id}"]'
                action_button = action_page.locator(selector).first
                button_count = await action_page.locator(selector).count()
                if button_count != 1:
                    record(
                        check_id,
                        False,
                        f"Agent Live {action_id} action must be present exactly once before draft verification.",
                        buttonCount=button_count,
                    )
                    return
                await action_button.click(timeout=args.timeout_ms)
                composer = action_page.locator('[data-agent-composer-draft="true"]').first
                await composer.wait_for(state="visible", timeout=args.timeout_ms)
                draft_value = await composer.input_value(timeout=args.timeout_ms)
                draft_lower = draft_value.lower()
                record(
                    check_id,
                    all(fragment.lower() in draft_lower for fragment in expected_fragments),
                    f"Clicking Agent Live {action_id} opens an actionable draft in the Agent composer.",
                    buttonCount=button_count,
                    draftPreview=draft_value[:220],
                )
            except Exception as exc:
                record(
                    check_id,
                    False,
                    f"Agent Live {action_id} action could not be verified as a composer draft.",
                    error=type(exc).__name__,
                )
            finally:
                await action_page.close()

        async def verify_agent_proof_action() -> None:
            proof_page = await context.new_page()
            try:
                await proof_page.goto(_agent_url(args.url, selected_mission_id), wait_until="commit", timeout=args.timeout_ms)
                await proof_page.wait_for_timeout(max(900, min(args.settle_ms, 2200)))
                selector = '[data-live-agent-action="verify"]'
                action_button = proof_page.locator(selector).first
                button_count = await proof_page.locator(selector).count()
                if button_count != 1:
                    record(
                        "live-agent-verify-opens-proof",
                        False,
                        "Agent Live Verify action must be present exactly once before proof verification.",
                        buttonCount=button_count,
                    )
                    return
                await action_button.click(timeout=args.timeout_ms)
                await proof_page.wait_for_timeout(600)
                proof_text = await proof_page.locator("body").inner_text(timeout=min(args.timeout_ms, 12000))
                proof_lower = proof_text.lower()
                record(
                    "live-agent-verify-opens-proof",
                    "live thread proof" in proof_lower or "proof source" in proof_lower or "verifier" in proof_lower,
                    "Clicking Agent Live Verify opens proof context without leaving the Agent surface.",
                    buttonCount=button_count,
                    proofVisible=(
                        "live thread proof" in proof_lower
                        or "proof source" in proof_lower
                        or "verifier" in proof_lower
                    ),
                )
            except Exception as exc:
                record(
                    "live-agent-verify-opens-proof",
                    False,
                    "Agent Live Verify action could not be verified from the live UI.",
                    error=type(exc).__name__,
                )
            finally:
                await proof_page.close()

        if selected_mission_id:
            await verify_agent_draft_action(
                "continue",
                "live-agent-continue-opens-agent-draft",
                ["continue", "current thread context", "proof"],
            )
            await verify_agent_draft_action(
                "modify",
                "live-agent-modify-opens-agent-draft",
                ["modify", "change this part", "proof"],
            )
            await verify_agent_draft_action(
                "summarize",
                "live-agent-summarize-opens-agent-draft",
                ["summarize", "what happened", "proof"],
            )
            await verify_agent_proof_action()
        agent_launch_modal = {
            "opened": False,
            "starterTemplateCount": 0,
            "readinessVisible": False,
            "routeDecisionVisible": False,
            "launcherText": "",
        }
        if agent_launch_action_count == 1 and selected_mission_id:
            launch_page = await context.new_page()
            try:
                await launch_page.goto(_agent_url(args.url, selected_mission_id), wait_until="commit", timeout=args.timeout_ms)
                await launch_page.wait_for_timeout(max(1200, min(args.settle_ms, 3000)))
                await launch_page.locator('[data-live-agent-launch-action="true"]').first.click(timeout=args.timeout_ms)
                await launch_page.wait_for_timeout(900)
                launcher_text = await launch_page.locator("body").inner_text(timeout=args.timeout_ms)
                launcher_lower = launcher_text.lower()
                objective_value = ""
                try:
                    objective_value = await launch_page.locator('[data-mission-launch-objective="quickstart"]').first.input_value(timeout=args.timeout_ms)
                except Exception:
                    objective_value = ""
                objective_lower = objective_value.lower()
                launcher_layout = {}
                try:
                    launcher_layout = await launch_page.evaluate(
                        """
                        () => {
                          const objective = document.querySelector('[data-mission-launch-objective="quickstart"]');
                          const route = document.querySelector('[data-task-fit-route-decision="true"]');
                          const readiness = document.querySelector('[data-live-launch-readiness="true"]');
                          const starters = document.querySelector('[data-mission-starter-templates="true"]');
                          const action = document.querySelector('.mission-quickstart-actions');
                          const topFor = node => node ? Math.round(node.getBoundingClientRect().top) : null;
                          const heightFor = node => node ? Math.round(node.getBoundingClientRect().height) : null;
                          return {
                            objectiveTop: topFor(objective),
                            objectiveHeight: heightFor(objective),
                            actionTop: topFor(action),
                            routeTop: topFor(route),
                            readinessTop: topFor(readiness),
                            startersTop: topFor(starters),
                          };
                        }
                        """
                    )
                except Exception:
                    launcher_layout = {}
                agent_launch_modal = {
                    "opened": "start mission" in launcher_lower or "launch mission" in launcher_lower,
                    "starterTemplateCount": await launch_page.locator('[data-mission-starter-templates="true"] [data-mission-template-id]').count(),
                    "readinessVisible": "provider auth" in launcher_lower,
                    "routeDecisionVisible": "task-fit route decision" in launcher_lower,
                    "builderCopyLeaked": "from builder" in launcher_lower or "from builder" in objective_lower,
                    "objectivePreview": objective_value[:220],
                    **launcher_layout,
                    "launcherText": launcher_text[:420],
                }
            except Exception as exc:
                agent_launch_modal = {**agent_launch_modal, "error": str(exc)[:240]}
            finally:
                await launch_page.close()
        record(
            "live-agent-launch-opens-mission-launcher",
            bool(agent_launch_modal.get("opened"))
            and int(agent_launch_modal.get("starterTemplateCount") or 0) > 0
            and agent_launch_modal.get("readinessVisible") is True
            and agent_launch_modal.get("routeDecisionVisible") is True
            and agent_launch_modal.get("builderCopyLeaked") is not True,
            "Clicking Agent Live Launch opens the real mission launcher with starter templates, provider readiness, and task-fit route decision.",
            **agent_launch_modal,
        )
        record(
            "live-agent-launch-objective-first",
            isinstance(agent_launch_modal.get("objectiveTop"), int)
            and isinstance(agent_launch_modal.get("actionTop"), int)
            and isinstance(agent_launch_modal.get("routeTop"), int)
            and isinstance(agent_launch_modal.get("readinessTop"), int)
            and agent_launch_modal.get("objectiveTop") < agent_launch_modal.get("actionTop")
            < agent_launch_modal.get("routeTop")
            < agent_launch_modal.get("readinessTop")
            and int(agent_launch_modal.get("objectiveHeight") or 0) >= 100,
            "Agent-launched mission dialog puts the objective and quick-start action before route/readiness diagnostics.",
            **agent_launch_modal,
        )
        try:
            await page.evaluate("() => window.scrollTo(0, 0)")
            await page.wait_for_timeout(250)
        except Exception:
            pass
        focus_layout = {}
        try:
            focus_layout = await page.evaluate(
                """
                () => {
                  const agentGrid = document.querySelector('.fluxos-agent-grid[data-agent-clarity-mode="focus"]');
                  const preview = document.querySelector('.fluxos-agent-grid[data-agent-clarity-mode="focus"] .fluxos-preview-panel');
                  const evidence = document.querySelector('.fluxos-agent-grid[data-agent-clarity-mode="focus"] .fluxos-evidence-rail');
                  const composer = document.querySelector('.fluxos-agent-grid[data-agent-clarity-mode="focus"] .fluxos-composer');
                  const thread = document.querySelector('.fluxos-agent-grid[data-agent-clarity-mode="focus"] .fluxos-thread');
                  const styleFor = node => node ? window.getComputedStyle(node) : null;
                  const isHidden = node => {
                    const style = styleFor(node);
                    if (!node || !style) return true;
                    const rect = node.getBoundingClientRect();
                    return style.display === 'none' || style.visibility === 'hidden' || rect.width === 0 || rect.height === 0;
                  };
                  return {
                    gridColumns: agentGrid ? styleFor(agentGrid).gridTemplateColumns : '',
                    previewHidden: isHidden(preview),
                    evidenceHidden: isHidden(evidence),
                    previewExists: Boolean(preview),
                    evidenceExists: Boolean(evidence),
                    composerTop: composer ? Math.round(composer.getBoundingClientRect().top) : null,
                    composerBottom: composer ? Math.round(composer.getBoundingClientRect().bottom) : null,
                    composerInFirstViewport: composer
                      ? composer.getBoundingClientRect().bottom > 0 && composer.getBoundingClientRect().top < window.innerHeight
                      : false,
                    threadMaxHeight: thread ? styleFor(thread).maxHeight : '',
                    viewportHeight: window.innerHeight,
                  };
                }
                """
            )
        except Exception:
            focus_layout = {}
        record(
            "live-agent-focus-single-reading-lane",
            bool(focus_layout)
            and focus_layout.get("previewHidden") is True
            and focus_layout.get("evidenceHidden") is True,
            "Agent Thread mode hides side preview/evidence rails so the live mission thread keeps the full reading lane.",
            **focus_layout,
        )
        record(
            "live-agent-composer-visible-after-thread",
            bool(focus_layout)
            and focus_layout.get("composerInFirstViewport") is True
            and isinstance(thread_first_order_safe.get("composer"), (int, float))
            and thread_first_order_safe.get("thread", 99) < thread_first_order_safe.get("composer", 99),
            "Agent Thread mode keeps the continue/modify/run composer immediately after the mission dialogue in the first viewport.",
            **focus_layout,
        )
        proof_brief = page.locator('[data-live-agent-proof-brief="true"]').first
        proof_brief_count = await page.locator('[data-live-agent-proof-brief="true"]').count()
        proof_source_count = await page.locator('[data-live-agent-proof-source="true"]').count()
        proof_next_count = await page.locator('[data-live-agent-next-repair="true"]').count()
        proof_no_fallback_count = await page.locator('[data-live-agent-no-fallback="true"]').count()
        proof_brief_text = ""
        if proof_brief_count > 0:
            try:
                proof_brief_text = await proof_brief.text_content(timeout=args.timeout_ms) or ""
            except Exception:
                proof_brief_text = ""
        proof_brief_lower = proof_brief_text.lower()
        proof_brief_hidden = True
        if proof_brief_count > 0:
            try:
                proof_brief_hidden = bool(await proof_brief.evaluate(
                    """node => {
                      const style = window.getComputedStyle(node);
                      const rect = node.getBoundingClientRect();
                      return style.display === 'none' || style.visibility === 'hidden' || rect.width === 0 || rect.height === 0;
                    }"""
                ))
            except Exception:
                proof_brief_hidden = True
        record(
            "live-agent-proof-brief-available-as-detail",
            proof_brief_count == 1
            and proof_source_count >= 1
            and proof_next_count >= 1
            and proof_no_fallback_count >= 1
            and "mission" in proof_brief_lower
            and "proof" in proof_brief_lower,
            "Agent keeps selected mission proof source and next action available as detail content without forcing it into the first reading lane.",
            proofBriefCount=proof_brief_count,
            proofSourceCount=proof_source_count,
            proofNextCount=proof_next_count,
            noFallbackCount=proof_no_fallback_count,
            proofBriefHiddenInFocus=proof_brief_hidden,
            proofBriefText=proof_brief_text[:320],
        )
        runtime_drawer = page.locator('[data-agent-advanced-drawer-kind="runtime"]')
        plan_drawer = page.locator('[data-agent-advanced-drawer-kind="plan"]')
        runtime_drawer_count = await runtime_drawer.count()
        plan_drawer_count = await plan_drawer.count()
        runtime_drawer_open_initial = False
        plan_drawer_open_initial = False
        runtime_drawer_text = ""
        try:
            if runtime_drawer_count:
                runtime_drawer_open_initial = bool(await runtime_drawer.first.evaluate("(node) => node.open"))
                runtime_drawer_text = await runtime_drawer.first.inner_text(timeout=args.timeout_ms)
            if plan_drawer_count:
                plan_drawer_open_initial = bool(await plan_drawer.first.evaluate("(node) => node.open"))
        except Exception:
            pass
        record(
            "live-agent-advanced-drawers-collapsed",
            runtime_drawer_count == 1
            and plan_drawer_count == 1
            and not runtime_drawer_open_initial
            and not plan_drawer_open_initial
            and all(token in runtime_drawer_text.lower() for token in ["advanced runtime controls", "lanes", "trace"]),
            "Agent keeps secondary diagnostics, lane controls, trace, and plan steps in collapsed advanced drawers by default.",
            runtimeDrawerCount=runtime_drawer_count,
            planDrawerCount=plan_drawer_count,
            runtimeDrawerOpenInitial=runtime_drawer_open_initial,
            planDrawerOpenInitial=plan_drawer_open_initial,
            runtimeDrawerText=runtime_drawer_text[:180],
        )
        detail_switch_result = {"clicked": False, "mode": ""}
        try:
            details_button = page.locator('[data-agent-clarity-switch="true"] button', has_text="Details").first
            if await details_button.count() > 0:
                await details_button.click(timeout=args.timeout_ms)
                await page.wait_for_selector(
                    '.fluxos-agent-grid[data-agent-clarity-mode="full"]',
                    timeout=max(args.settle_ms, 12000),
                )
                detail_switch_result["clicked"] = True
                detail_switch_result["mode"] = "full"
        except Exception as exc:
            detail_switch_result["error"] = str(exc)[:240]
        record(
            "live-agent-details-mode-opens-diagnostics",
            detail_switch_result.get("mode") == "full",
            "Verifier switches from Agent Live focus into Details before testing diagnostics and lane controls.",
            **detail_switch_result,
        )
        runtime_drawer = page.locator('[data-agent-advanced-drawer-kind="runtime"]')
        plan_drawer = page.locator('[data-agent-advanced-drawer-kind="plan"]')
        runtime_drawer_count = await runtime_drawer.count()
        plan_drawer_count = await plan_drawer.count()
        if runtime_drawer_count:
            try:
                await runtime_drawer.first.evaluate("(node) => { node.open = true; }")
            except Exception:
                pass
        if plan_drawer_count:
            try:
                await plan_drawer.first.evaluate("(node) => { node.open = true; }")
            except Exception:
                pass
        diagnostics_shelf = page.locator('[data-agent-diagnostics-shelf="true"]')
        diagnostics_shelf_count = await diagnostics_shelf.count()
        diagnostics_shelf_text = ""
        try:
            if diagnostics_shelf_count:
                diagnostics_shelf_text = await diagnostics_shelf.first.inner_text(timeout=args.timeout_ms)
        except Exception:
            diagnostics_shelf_text = ""
        record(
            "live-agent-diagnostics-shelf-visible",
            diagnostics_shelf_count == 1
            and "diagnostics" in diagnostics_shelf_text.lower()
            and all(token in diagnostics_shelf_text.lower() for token in ["trace", "lanes", "plan"]),
            "Agent groups trace, lane, and plan counters below the report thread so live reports stay readable first.",
            shelfCount=diagnostics_shelf_count,
            shelfText=diagnostics_shelf_text[:220],
        )
        runtime_output_needles = [
            str(message.get("detail") or "")
            for message in selected_detail.get("agentMessages", [])
            if isinstance(message, dict) and "Runtime output:" in str(message.get("detail") or "")
        ]
        runtime_report_body_needles = [
            match.group(1).strip()[:48]
            for needle in runtime_output_needles
            for match in [re.search(r"Runtime output:\s*(.+?)(?:\s+[·]\s+Action:|\s+[·]\s+Target:|\s*$)", needle)]
            if match and len(match.group(1).strip()) >= 24
        ]
        def visible_runtime_outputs() -> tuple[list[str], list[str]]:
            normalized_lowered = _collapse_text(_display_text(lowered))
            output_visible = [
                needle[:80]
                for needle in runtime_output_needles
                if _collapse_text(_display_text(needle[:80])) in normalized_lowered
            ]
            report_visible = [
                needle
                for needle in runtime_report_body_needles
                if _collapse_text(_display_text(needle)) in normalized_lowered
            ]
            return output_visible, report_visible

        runtime_output_visible, runtime_report_body_visible = visible_runtime_outputs()
        if runtime_output_needles:
            try:
                await page.wait_for_selector(
                    '[data-runtime-report="true"][data-message-zone="thread"]',
                    timeout=max(args.settle_ms, 12000),
                )
                body_text = await page.locator("body").inner_text(timeout=args.timeout_ms)
                dom_text = await page.content()
                lowered = body_text.lower()
                dom_lowered = dom_text.lower()
                runtime_output_visible, runtime_report_body_visible = visible_runtime_outputs()
            except Exception:
                pass
        else:
            try:
                await page.wait_for_selector(
                    '[data-hermes-transcript="true"][data-message-zone="thread"]',
                    timeout=max(args.settle_ms, 12000),
                )
                body_text = await page.locator("body").inner_text(timeout=args.timeout_ms)
                dom_text = await page.content()
                lowered = body_text.lower()
                dom_lowered = dom_text.lower()
            except Exception:
                pass
        selected_report_empty_indicator_count = await page.locator('[data-live-report-empty-state="true"]').count()
        selected_report_empty_indicator_text = ""
        if selected_report_empty_indicator_count:
            try:
                selected_report_empty_indicator_text = await page.locator(
                    '[data-live-report-empty-state="true"]'
                ).first.inner_text(timeout=args.timeout_ms)
            except Exception:
                selected_report_empty_indicator_text = ""
        selected_report_empty_indicator_lower = selected_report_empty_indicator_text.lower()
        selected_report_explicit_empty = (
            selected_report_empty_indicator_count >= 1
            and "live data only" in selected_report_empty_indicator_lower
            and (
                "no selected evidence body returned yet" in selected_report_empty_indicator_lower
                or "no evidence body selected" in selected_report_empty_indicator_lower
            )
        )
        record(
            "runtime-output-visible-in-evidence-not-dialogue",
            not runtime_output_needles
            or bool(runtime_report_body_visible or runtime_output_visible)
            or (
                await page.locator('[data-live-selected-report-body="true"]').count() >= 1
                and await page.locator('[data-runtime-report="true"][data-message-zone="thread"]').count() == 0
            )
            or (
                selected_report_explicit_empty
                and await page.locator('[data-runtime-report="true"][data-message-zone="thread"]').count() == 0
            ),
            "Agent Live keeps concrete Hermes/runtime slice bodies in evidence/detail surfaces instead of promoting them as dialogue messages.",
            missionId=selected_mission_id,
            runtimeOutputCount=len(runtime_output_needles),
            matchedRuntimeOutputs=runtime_output_visible[:3],
            matchedRuntimeReportBodies=runtime_report_body_visible[:3],
            explicitEmptyReportState=selected_report_explicit_empty,
            skipped=len(runtime_output_needles) == 0,
        )
        runtime_report_row_count = await page.locator('[data-runtime-report="true"][data-message-zone="thread"]').count()
        hermes_transcript_row_count = await page.locator('[data-hermes-transcript="true"][data-message-zone="thread"]').count()
        live_thread_row_count = await page.locator('.fluxos-agent-main [data-message-zone="thread"][data-turn-id]').count()
        non_report_thread_row_count = await page.locator(
            '.fluxos-agent-main [data-message-zone="thread"][data-turn-id]:not([data-runtime-report="true"])'
        ).count()
        record(
            "runtime-report-rows-not-promoted",
            runtime_report_row_count == 0,
            "Runtime output/proof rows are not promoted into the Agent Live dialogue thread.",
            runtimeReportRows=runtime_report_row_count,
            runtimeOutputCount=len(runtime_output_needles),
            skipped=len(runtime_output_needles) == 0,
        )
        record(
            "live-agent-thread-is-dialogue-only",
            runtime_report_row_count == 0
            and hermes_transcript_row_count == 0
            and live_thread_row_count == non_report_thread_row_count,
            "The live Agent message list is reserved for real dialogue rows; Hermes transcripts, proof artifacts, and runtime reports stay in evidence/diagnostics.",
            runtimeOutputCount=len(runtime_output_needles),
            liveThreadRows=live_thread_row_count,
            runtimeReportRows=runtime_report_row_count,
            hermesTranscriptRows=hermes_transcript_row_count,
            nonReportThreadRows=non_report_thread_row_count,
        )
        selected_mission_summary = next(
            (item for item in missions if _mission_id(item) == selected_mission_id),
            {},
        )
        expected_lane_roles = [
            str(item.get("role") or "").strip().lower()
            for item in (
                selected_mission_summary.get("runtimeLanes")
                or selected_mission_summary.get("providerCapabilities", {}).get("lanes")
                or selected_mission_summary.get("provider_capabilities", {}).get("lanes")
                or []
            )
            if isinstance(item, dict) and str(item.get("role") or "").strip()
        ]
        visible_lane_rows = page.locator('[data-live-agent-lane="true"]')
        visible_lane_count = await visible_lane_rows.count()
        visible_lane_roles = []
        for index in range(visible_lane_count):
            role = await visible_lane_rows.nth(index).get_attribute("data-lane-role") or ""
            if role:
                visible_lane_roles.append(role.lower())
        lane_board_text = ""
        try:
            lane_board_text = await page.locator('[data-live-agent-lane-board="true"]').first.inner_text(timeout=args.timeout_ms)
        except Exception:
            lane_board_text = ""
        expected_role_set = sorted(set(expected_lane_roles))
        visible_role_set = sorted(set(visible_lane_roles))
        record(
            "live-agent-subagent-lane-board-visible",
            (
                len(expected_role_set) == 0
                or (
                    visible_lane_count >= len(expected_role_set)
                    and all(role in visible_role_set for role in expected_role_set)
                    and "sub-agent lane board" in lane_board_text.lower()
                )
            ),
            "Agent renders live planner/executor/verifier lanes from the NAS provider capability contract, not only delegated session rows.",
            missionId=selected_mission_id,
            expectedLaneRoles=expected_role_set,
            visibleLaneRoles=visible_role_set,
            visibleLaneCount=visible_lane_count,
            laneBoardText=lane_board_text[:220],
            skipped=len(expected_role_set) == 0,
        )
        lane_control_buttons = page.locator('[data-live-agent-lane-control="true"]')
        lane_control_count = await lane_control_buttons.count()
        lane_control_actions = []
        for index in range(lane_control_count):
            action = await lane_control_buttons.nth(index).get_attribute("data-lane-control-action") or ""
            if action:
                lane_control_actions.append(action)
        inspect_control = page.locator(
            '[data-live-agent-lane-control="true"][data-lane-control-action="runtime"]'
        ).first
        receipt_text = ""
        if await inspect_control.count() > 0:
            await inspect_control.click(timeout=args.timeout_ms)
            try:
                await page.wait_for_selector(
                    '[data-live-agent-lane-mutation-proof="true"]',
                    timeout=max(args.settle_ms, 12000),
                )
            except Exception:
                await page.wait_for_timeout(500)
            try:
                receipt_text = await page.locator('[data-live-agent-lane-control-receipt="true"]').first.inner_text(timeout=args.timeout_ms)
            except Exception:
                receipt_text = ""
        mutation_proof_text = ""
        mutation_proof_count = await page.locator('[data-live-agent-lane-mutation-proof="true"]').count()
        if mutation_proof_count:
            try:
                mutation_proof_text = await page.locator('[data-live-agent-lane-mutation-proof="true"]').first.inner_text(timeout=args.timeout_ms)
            except Exception:
                mutation_proof_text = ""
        record(
            "live-agent-lane-controls-operable",
            lane_control_count >= max(1, len(expected_role_set))
            and {"runtime", "proof", "reroute"}.issubset(set(lane_control_actions))
            and "lane control receipt" in receipt_text.lower(),
            "Agent lane board exposes operable Inspect/Proof/Reroute controls and clicking Inspect produces a visible lane-control receipt.",
            missionId=selected_mission_id,
            laneControlCount=lane_control_count,
            laneControlActions=sorted(set(lane_control_actions)),
            receiptText=receipt_text[:240],
            skipped=len(expected_role_set) == 0,
        )
        record(
            "live-agent-lane-mutation-proof-visible",
            mutation_proof_count > 0
            and "mission.state.current_runtime_lane" in mutation_proof_text
            and "observed after write" in mutation_proof_text.lower(),
            "Clicking a lane control exposes the durable before/after state proof for the live mission lane mutation.",
            missionId=selected_mission_id,
            mutationProofCount=mutation_proof_count,
            mutationProofText=mutation_proof_text[:240],
            skipped=len(expected_role_set) == 0,
        )

        dialogue_thread_rows = await page.locator(
            '[data-message-zone="thread"][data-agent-dialogue-turn="true"]'
        ).count()
        proof_thread_rows = await page.locator(
            '[data-message-zone="thread"][data-agent-proof-artifact="true"]'
        ).count()
        runtime_activity_thread_rows = await page.locator(
            '[data-message-zone="thread"][data-agent-runtime-activity="true"]'
        ).count()
        all_thread_rows = await page.locator('[data-message-zone="thread"]').count()
        empty_dialogue_state = (
            "no real hermes dialogue yet" in lowered
            or "no real hermes dialogue is attached to this mission yet" in lowered
        )
        forbidden_thread_fragments = [
            "runtime output artifact",
            "runtime_output.txt",
            "nas audit fluxio.live_nas_system_audit_snapshot",
            "planner selected step",
            "action: file_read",
        ]
        visible_forbidden_thread_fragments = []
        try:
            thread_text = await page.locator(".fluxos-thread").first.inner_text(timeout=args.timeout_ms)
            thread_lower = thread_text.lower()
            visible_forbidden_thread_fragments = [
                marker for marker in forbidden_thread_fragments if marker in thread_lower
            ]
        except Exception:
            thread_text = ""
        record(
            "agent-dialogue-thread-real-or-empty",
            (
                dialogue_thread_rows > 0
                or (all_thread_rows == 0 and empty_dialogue_state)
            )
            and proof_thread_rows == 0
            and runtime_activity_thread_rows == 0
            and not visible_forbidden_thread_fragments,
            "Agent mission detail shows real operator/Hermes dialogue, or an explicit empty dialogue state, without promoting proof artifacts or checkpoint fragments as chat.",
            dialogueThreadRows=dialogue_thread_rows,
            allThreadRows=all_thread_rows,
            emptyDialogueState=empty_dialogue_state,
            proofThreadRows=proof_thread_rows,
            runtimeActivityThreadRows=runtime_activity_thread_rows,
            forbiddenFragments=visible_forbidden_thread_fragments,
        )
        record(
            "live-runtime-activity-stays-diagnostic",
            proof_thread_rows == 0 and runtime_activity_thread_rows == 0,
            "Agent keeps runtime/tool-event evidence out of the dialogue thread so activity stays in diagnostic/proof surfaces.",
            proofThreadRows=proof_thread_rows,
            runtimeActivityThreadRows=runtime_activity_thread_rows,
        )
        record(
            "codex-high-route-visible",
            "gpt-5.5" in lowered and "high" in lowered,
            "Agent route defaults visible route text to high-effort Codex 5.5 instead of medium legacy Codex.",
        )
        default_selected_text = ""
        try:
            default_selected_text = await page.locator(".fluxos-selected-message-proof").first.inner_text(timeout=args.timeout_ms)
        except Exception:
            default_selected_text = ""
        default_selected_lower = default_selected_text.lower()
        bookkeeping_default_markers = [
            "low-signal runtime heartbeat",
            "provider route truth",
            "provider route is not authenticated",
            "control-room planner",
            "control-room mission state",
            "runtime heartbeat",
        ]
        runtime_output_count = len(runtime_output_needles)
        has_hermes_transcript_fallback = runtime_output_count == 0 and hermes_transcript_row_count > 0
        no_report_default_empty = (
            not has_hermes_transcript_fallback
            and (
                runtime_output_count == 0
                or (live_thread_row_count == 0 and selected_report_explicit_empty)
            )
        )
        meaningful_default = (
            (
                bool(default_selected_text)
                and (runtime_output_count > 0 or has_hermes_transcript_fallback)
                and not any(marker in default_selected_lower for marker in bookkeeping_default_markers)
            )
            or no_report_default_empty
        )
        record(
            "default-selected-message-is-meaningful",
            meaningful_default,
            "Agent opens on a meaningful live Hermes/runtime report row, or an explicit empty live-report state when the mission has no Runtime output body.",
            selectedText=default_selected_text[:240],
            runtimeOutputCount=runtime_output_count,
            hermesTranscriptRows=hermes_transcript_row_count,
            forbiddenMarkers=[marker for marker in bookkeeping_default_markers if marker in default_selected_lower],
        )
        selected_report_reader = page.locator('[data-live-selected-report-reader="true"]')
        selected_report_reader_count = await selected_report_reader.count()
        selected_report_reader_text = ""
        selected_report_body_text = ""
        selected_report_body_count = 0
        try:
            if selected_report_reader_count:
                selected_report_reader_text = await selected_report_reader.first.inner_text(timeout=args.timeout_ms)
                selected_report_body_count = await selected_report_reader.locator('[data-live-selected-report-body="true"]').count()
                if selected_report_body_count:
                    selected_report_body_text = (
                        await selected_report_reader.locator('[data-live-selected-report-body="true"]').first.inner_text(timeout=args.timeout_ms)
                    )
        except Exception:
            selected_report_reader_text = ""
            selected_report_body_text = ""
            selected_report_body_count = 0
        selected_report_reader_lower = selected_report_reader_text.lower()
        selected_report_has_body = selected_report_body_count >= 1 and (
            runtime_output_count > 0 or has_hermes_transcript_fallback
        )
        selected_report_has_dialogue_body = (
            selected_report_body_count >= 1
            and runtime_output_count == 0
            and not has_hermes_transcript_fallback
            and dialogue_thread_rows > 0
            and bool(selected_report_body_text.strip())
            and "live data only" not in selected_report_reader_lower
        )
        selected_report_empty_state = (
            not has_hermes_transcript_fallback
            and selected_report_body_count == 0
            and (
                "no selected evidence body returned yet" in selected_report_reader_lower
                or "no evidence body selected" in selected_report_reader_lower
            )
            and "live data only" in selected_report_reader_lower
        )
        record(
            "live-selected-report-reader-visible",
            selected_report_reader_count == 1
            and (selected_report_has_body or selected_report_has_dialogue_body or selected_report_empty_state)
            and ("selected live report" in selected_report_reader_lower or "evidence reader" in selected_report_reader_lower)
            and not any(marker in selected_report_reader_lower for marker in bookkeeping_default_markers),
            "Agent main column shows the selected Hermes/runtime report reader, selected dialogue body, or an explicit no-report live state when NAS returned no report body.",
            readerCount=selected_report_reader_count,
            bodyCount=selected_report_body_count,
            runtimeOutputCount=runtime_output_count,
            hermesTranscriptRows=hermes_transcript_row_count,
            dialogueThreadRows=dialogue_thread_rows,
            dialogueBody=selected_report_has_dialogue_body,
            emptyState=selected_report_empty_state,
            readerText=selected_report_reader_text[:260],
            forbiddenMarkers=[marker for marker in bookkeeping_default_markers if marker in selected_report_reader_lower],
        )
        selection_version_count = await page.locator('[data-live-message-selection-version="v29"]').count()
        record(
            "live-message-selection-version-current",
            selection_version_count == 1,
            "Agent is running the v29 message-selection bundle that forces the installed app shell forward, rejects unscoped live rows, collapses secondary diagnostics into advanced drawers, keeps the live operations brief compact, preserves manual live-message selection across feed refreshes, resets stale preview caches, and never embeds live preview frames.",
            selectionVersionCount=selection_version_count,
        )
        raw_action_json_markers = [
            '"action_id"',
            '"target_path"',
            '"risk_level"',
            '"requires_approval"',
            "source_step_id",
        ]
        selected_report_body_lower = selected_report_body_text.lower()
        record(
            "live-selected-report-body-excludes-action-json",
            selected_report_empty_state
            or runtime_output_count == 0
            or (
                bool(selected_report_body_text.strip())
                and not any(marker in selected_report_body_lower for marker in raw_action_json_markers)
            ),
            "Selected Hermes/runtime report body shows the operator-facing report text without raw action proposal JSON.",
            runtimeOutputCount=runtime_output_count,
            bodyPreview=selected_report_body_text[:300],
            leakedMarkers=[marker for marker in raw_action_json_markers if marker in selected_report_body_lower],
        )
        message_rows = page.locator('.fluxos-agent-main [data-message-zone="thread"][data-turn-id][role="button"]')
        message_row_count = await message_rows.count()
        message_zone_counts = {}
        for zone in ("thinking", "thread", "plan"):
            message_zone_counts[zone] = await page.locator(f'[data-message-zone="{zone}"]').count()
        if message_row_count < 2:
            preview_frame_count = await page.locator(".fluxos-preview-panel iframe").count()
            preview_state = ""
            try:
                preview_state = await page.locator(".fluxos-preview-panel").first.get_attribute("data-preview-state", timeout=args.timeout_ms) or ""
            except Exception:
                preview_state = ""
            empty_report_state = (
                not has_hermes_transcript_fallback
                and message_row_count == 0
                and preview_frame_count == 0
                and preview_state == "empty"
                and selected_report_empty_state
            )
            record(
                "live-message-click-switch",
                empty_report_state or message_row_count == 1,
                "Live Agent keeps the primary thread runtime-report-only; missions with no report body show an explicit empty state instead of falling back to stale frames.",
                visibleMessageRows=message_row_count,
                messageZoneCounts=message_zone_counts,
                previewFrameCount=preview_frame_count,
                previewState=preview_state,
                runtimeOutputCount=runtime_output_count,
                emptyReportState=empty_report_state,
                skipped=True,
            )
        else:
            first_message = message_rows.nth(0)
            last_message = message_rows.nth(message_row_count - 1)
            first_title = ""
            last_title = ""
            try:
                first_title = (await first_message.locator("strong").nth(0).inner_text(timeout=args.timeout_ms)).strip()
            except Exception:
                first_title = ""
            try:
                last_title = (await last_message.locator("strong").nth(0).inner_text(timeout=args.timeout_ms)).strip()
            except Exception:
                last_title = ""
            try:
                await first_message.scroll_into_view_if_needed(timeout=args.timeout_ms)
            except Exception:
                pass
            await first_message.click(timeout=args.timeout_ms)
            if first_title:
                try:
                    await page.wait_for_function(
                        """
                        title => {
                          const proof = document.querySelector(".fluxos-selected-message-proof")?.innerText || "";
                          const reader = document.querySelector('[data-live-selected-report-reader="true"]')?.innerText || "";
                          return `${proof}\n${reader}`.toLowerCase().includes(String(title || "").toLowerCase());
                        }
                        """,
                        first_title,
                        timeout=max(args.settle_ms, 3000),
                    )
                except Exception:
                    await page.wait_for_timeout(700)
            else:
                await page.wait_for_timeout(700)
            first_selected_text = ""
            try:
                first_selected_text = await page.locator(".fluxos-selected-message-proof").first.inner_text(timeout=args.timeout_ms)
            except Exception:
                first_selected_text = await page.locator(".fluxos-preview-panel").first.inner_text(timeout=args.timeout_ms)
            first_reader_text = ""
            try:
                first_reader_text = await page.locator('[data-live-selected-report-reader="true"]').first.inner_text(timeout=args.timeout_ms)
            except Exception:
                first_reader_text = ""
            try:
                await last_message.scroll_into_view_if_needed(timeout=args.timeout_ms)
            except Exception:
                pass
            await last_message.click(timeout=args.timeout_ms)
            if last_title:
                try:
                    await page.wait_for_function(
                        """
                        title => {
                          const proof = document.querySelector(".fluxos-selected-message-proof")?.innerText || "";
                          const reader = document.querySelector('[data-live-selected-report-reader="true"]')?.innerText || "";
                          return `${proof}\n${reader}`.toLowerCase().includes(String(title || "").toLowerCase());
                        }
                        """,
                        last_title,
                        timeout=max(args.settle_ms, 3000),
                    )
                except Exception:
                    await page.wait_for_timeout(700)
            else:
                await page.wait_for_timeout(700)
            last_selected_text = ""
            try:
                last_selected_text = await page.locator(".fluxos-selected-message-proof").first.inner_text(timeout=args.timeout_ms)
            except Exception:
                last_selected_text = await page.locator(".fluxos-preview-panel").first.inner_text(timeout=args.timeout_ms)
            last_reader_text = ""
            try:
                last_reader_text = await page.locator('[data-live-selected-report-reader="true"]').first.inner_text(timeout=args.timeout_ms)
            except Exception:
                last_reader_text = ""
            preview_frame_count_after_click = await page.locator(".fluxos-preview-panel iframe").count()
            selected_message_proof_count = await page.locator(".fluxos-selected-message-proof").count()
            preview_state_after_click = ""
            try:
                preview_state_after_click = await page.locator(".fluxos-preview-panel").first.get_attribute("data-preview-state", timeout=args.timeout_ms) or ""
            except Exception:
                preview_state_after_click = ""
            first_match = bool(first_title and first_title.lower() in first_selected_text.lower())
            last_match = bool(last_title and last_title.lower() in last_selected_text.lower())
            reader_first_match = bool(first_title and first_title.lower() in first_reader_text.lower())
            reader_last_match = bool(last_title and last_title.lower() in last_reader_text.lower())
            reader_switch_ok = (
                reader_first_match and reader_last_match
            ) or (
                runtime_output_count == 0
                and not has_hermes_transcript_fallback
                and "no evidence body selected" in first_reader_text.lower()
                and "no evidence body selected" in last_reader_text.lower()
            )
            record(
                "live-message-click-switch",
                first_selected_text != last_selected_text
                and first_match
                and last_match
                and reader_switch_ok
                and preview_frame_count_after_click == 0
                and selected_message_proof_count > 0
                and preview_state_after_click == "selected-message",
                "Clicking different live Agent messages rebuilds the selected-message preview instead of leaving an older mission frame stuck.",
                visibleMessageRows=message_row_count,
                firstTitle=first_title,
                lastTitle=last_title,
                firstMatched=first_match,
                lastMatched=last_match,
                readerFirstMatched=reader_first_match,
                readerLastMatched=reader_last_match,
                readerStayedEmptyBecauseNoRuntimeReport=runtime_output_count == 0
                and not has_hermes_transcript_fallback
                and "no evidence body selected" in first_reader_text.lower()
                and "no evidence body selected" in last_reader_text.lower(),
                previewFrameCountAfterClick=preview_frame_count_after_click,
                selectedMessageProofCount=selected_message_proof_count,
                previewStateAfterClick=preview_state_after_click,
                messageZoneCounts=message_zone_counts,
            )
        diagnostic_rows = page.locator(
            '.fluxos-agent-main [data-message-zone="thinking"][role="button"], '
            '.fluxos-agent-main [data-message-zone="plan"][role="button"]'
        )
        diagnostic_row_count = await diagnostic_rows.count()
        if diagnostic_row_count == 0:
            record(
                "live-diagnostic-rows-do-not-hijack-report-reader",
                True,
                "No selectable diagnostic rows were returned for this selected mission; primary runtime-report selection was checked separately.",
                diagnosticRows=0,
                skipped=True,
            )
        else:
            diagnostic_row = diagnostic_rows.first
            diagnostic_title = ""
            try:
                diagnostic_title = (await diagnostic_row.locator("strong").nth(0).inner_text(timeout=args.timeout_ms)).strip()
            except Exception:
                diagnostic_title = ""
            report_reader_before_diagnostic = ""
            selected_proof_before_diagnostic = ""
            try:
                report_reader_before_diagnostic = await page.locator('[data-live-selected-report-reader="true"]').first.inner_text(timeout=args.timeout_ms)
            except Exception:
                report_reader_before_diagnostic = ""
            try:
                selected_proof_before_diagnostic = await page.locator(".fluxos-selected-message-proof").first.inner_text(timeout=args.timeout_ms)
            except Exception:
                selected_proof_before_diagnostic = ""
            await diagnostic_row.click(timeout=args.timeout_ms)
            await page.wait_for_timeout(700)
            diagnostic_selected_text = ""
            try:
                diagnostic_selected_text = await page.locator(".fluxos-selected-message-proof").first.inner_text(timeout=args.timeout_ms)
            except Exception:
                diagnostic_selected_text = await page.locator(".fluxos-preview-panel").first.inner_text(timeout=args.timeout_ms)
            diagnostic_reader_text = ""
            try:
                diagnostic_reader_text = await page.locator('[data-live-selected-report-reader="true"]').first.inner_text(timeout=args.timeout_ms)
            except Exception:
                diagnostic_reader_text = ""
            diagnostic_frame_count = await page.locator(".fluxos-preview-panel iframe").count()
            diagnostic_preview_state = ""
            try:
                diagnostic_preview_state = await page.locator(".fluxos-preview-panel").first.get_attribute("data-preview-state", timeout=args.timeout_ms) or ""
            except Exception:
                diagnostic_preview_state = ""
            selected_diagnostic_count = await page.locator(
                '[data-selected-diagnostic-message="true"]'
            ).count()
            diagnostic_hijacked_report = bool(
                diagnostic_title
                and diagnostic_title.lower() in (diagnostic_selected_text + "\n" + diagnostic_reader_text).lower()
            )
            report_reader_unchanged = (
                bool(report_reader_before_diagnostic)
                and diagnostic_reader_text == report_reader_before_diagnostic
                and diagnostic_selected_text == selected_proof_before_diagnostic
            )
            expected_diagnostic_preview_state = (
                "selected-message" if runtime_output_count > 0 or has_hermes_transcript_fallback else "empty"
            )
            record(
                "live-diagnostic-rows-do-not-hijack-report-reader",
                report_reader_unchanged
                and not diagnostic_hijacked_report
                and selected_diagnostic_count > 0
                and diagnostic_frame_count == 0
                and diagnostic_preview_state == expected_diagnostic_preview_state,
                "Clicking live trace/plan rows marks the diagnostic row without replacing the selected Hermes/runtime report reader or reviving an older preview frame.",
                diagnosticRows=diagnostic_row_count,
                diagnosticTitle=diagnostic_title,
                diagnosticHijackedReport=diagnostic_hijacked_report,
                reportReaderUnchanged=report_reader_unchanged,
                selectedDiagnosticRows=selected_diagnostic_count,
                previewFrameCountAfterClick=diagnostic_frame_count,
                previewStateAfterClick=diagnostic_preview_state,
                expectedPreviewState=expected_diagnostic_preview_state,
            )
        if selected_mission_id:
            workbench_page = await context.new_page()
            await workbench_page.goto(_workbench_url(args.url, selected_mission_id), wait_until="commit", timeout=args.timeout_ms)
            await workbench_page.wait_for_timeout(args.settle_ms)
            try:
                await workbench_page.wait_for_selector(".fluxos-workbench-thread [data-agent-message-key]", timeout=max(args.timeout_ms, args.settle_ms))
            except Exception:
                pass
            workbench_proof_band = workbench_page.locator('[data-live-workbench-proof-band="true"]')
            workbench_proof_band_count = await workbench_proof_band.count()
            workbench_proof_band_text = ""
            if workbench_proof_band_count:
                try:
                    workbench_proof_band_text = (await workbench_proof_band.first.inner_text(timeout=args.timeout_ms)).strip()
                except Exception:
                    workbench_proof_band_text = ""
            workbench_proof_band_lower = workbench_proof_band_text.lower()
            record(
                "live-workbench-proof-band-visible",
                workbench_proof_band_count == 1
                and "live workbench proof" in workbench_proof_band_lower
                and "messages" in workbench_proof_band_lower
                and "artifacts" in workbench_proof_band_lower
                and "operations" in workbench_proof_band_lower
                and "fixture" not in workbench_proof_band_lower
                and "demo" not in workbench_proof_band_lower,
                "Workbench exposes a live-only proof/control band before preview content, with counts coming from the NAS mission detail.",
                proofBandCount=workbench_proof_band_count,
                proofBandText=workbench_proof_band_text[:700],
            )
            workbench_rows = workbench_page.locator(".fluxos-workbench-thread [data-agent-message-key][role='button']")
            workbench_row_count = await workbench_rows.count()
            workbench_default_state = ""
            try:
                workbench_default_state = await workbench_page.locator(".fluxos-live-preview.workbench").first.get_attribute("data-preview-state", timeout=args.timeout_ms) or ""
            except Exception:
                workbench_default_state = ""
            workbench_initial_frame_count = await workbench_page.locator(".fluxos-live-preview.workbench iframe").count()
            record(
                "live-workbench-never-renders-live-iframe",
                workbench_initial_frame_count == 0,
                "Live Workbench renders selected report evidence or an explicit empty state; it must not embed a stale mission iframe.",
                missionId=selected_mission_id,
                defaultPreviewState=workbench_default_state,
                initialFrameCount=workbench_initial_frame_count,
            )
            if workbench_row_count < 2:
                workbench_empty_live_state = workbench_row_count == 0 and workbench_default_state == "empty" and workbench_initial_frame_count == 0
                record(
                    "live-workbench-message-click-switch",
                    workbench_empty_live_state
                    or (workbench_row_count > 0 and workbench_default_state == "selected-message" and workbench_initial_frame_count == 0),
                    "Workbench has too few live report rows for a full switch test, but it must show either selected-message evidence or an explicit empty live-report state without a stale iframe.",
                    visibleMessageRows=workbench_row_count,
                    defaultPreviewState=workbench_default_state,
                    initialFrameCount=workbench_initial_frame_count,
                    emptyLiveState=workbench_empty_live_state,
                    skipped=True,
                )
            else:
                first_workbench_row = workbench_rows.nth(0)
                last_workbench_row = workbench_rows.nth(workbench_row_count - 1)
                first_workbench_title = ""
                last_workbench_title = ""
                try:
                    first_workbench_title = (await first_workbench_row.locator("strong").nth(0).inner_text(timeout=args.timeout_ms)).strip()
                except Exception:
                    first_workbench_title = ""
                try:
                    last_workbench_title = (await last_workbench_row.locator("strong").nth(0).inner_text(timeout=args.timeout_ms)).strip()
                except Exception:
                    last_workbench_title = ""
                await first_workbench_row.click(timeout=args.timeout_ms)
                await workbench_page.wait_for_timeout(500)
                first_workbench_selected = await workbench_page.locator(".fluxos-live-preview.workbench .fluxos-selected-message-proof").first.inner_text(timeout=args.timeout_ms)
                await last_workbench_row.click(timeout=args.timeout_ms)
                await workbench_page.wait_for_timeout(500)
                last_workbench_selected = await workbench_page.locator(".fluxos-live-preview.workbench .fluxos-selected-message-proof").first.inner_text(timeout=args.timeout_ms)
                workbench_frame_count_after_click = await workbench_page.locator(".fluxos-live-preview.workbench iframe").count()
                workbench_preview_state = await workbench_page.locator(".fluxos-live-preview.workbench").first.get_attribute("data-preview-state", timeout=args.timeout_ms) or ""
                record(
                    "live-workbench-message-click-switch",
                    workbench_default_state == "selected-message"
                    and workbench_initial_frame_count == 0
                    and first_workbench_selected != last_workbench_selected
                    and bool(first_workbench_title and first_workbench_title.lower() in first_workbench_selected.lower())
                    and bool(last_workbench_title and last_workbench_title.lower() in last_workbench_selected.lower())
                    and workbench_frame_count_after_click == 0
                    and workbench_preview_state == "selected-message",
                    "Workbench defaults to live message evidence and clicking another message does not leave an old preview frame stuck.",
                    visibleMessageRows=workbench_row_count,
                    defaultPreviewState=workbench_default_state,
                    initialFrameCount=workbench_initial_frame_count,
                    firstTitle=first_workbench_title,
                    lastTitle=last_workbench_title,
                    frameCountAfterClick=workbench_frame_count_after_click,
                    previewStateAfterClick=workbench_preview_state,
                )
            await workbench_page.close()
        switch_pool = [
            item
            for item in active
            if _mission_id(item) and _mission_id(item) != selected_mission_id
        ] or [
            item
            for item in missions
            if _mission_id(item) and _mission_id(item) != selected_mission_id
        ]
        switch_candidates = switch_pool
        if len(switch_candidates) == 0:
            record(
                "live-mission-click-switch",
                True,
                "Only one running mission was available, so mission switching was not applicable.",
                skipped=True,
            )
        else:
            switch_target = switch_candidates[0]
            switch_mission_id = _mission_id(switch_target)
            switch_title = _mission_title(switch_target)
            switch_detail = await _fetch_mission_detail(
                context,
                args.url,
                switch_mission_id,
                args.timeout_ms,
            )
            switch_needles = _mission_detail_needles(switch_detail, switch_title)
            switch_button = page.locator(".fluxos-recent-sidebar button").filter(has_text=switch_title).nth(0)
            switch_button_count = await page.locator(".fluxos-recent-sidebar button").filter(has_text=switch_title).count()
            switch_click_used = False
            if switch_button_count > 0:
                try:
                    await switch_button.click(timeout=args.timeout_ms, force=True)
                    switch_click_used = True
                except Exception:
                    await page.goto(_agent_url(args.url, switch_mission_id), wait_until="commit", timeout=args.timeout_ms)
            else:
                await page.goto(_agent_url(args.url, switch_mission_id), wait_until="commit", timeout=args.timeout_ms)
            await page.wait_for_function(
                "(missionId) => new URL(window.location.href).searchParams.get('missionId') === missionId",
                arg=switch_mission_id,
                timeout=args.timeout_ms,
            )
            await page.wait_for_timeout(args.switch_settle_ms)
            expected_switch_messages = len(
                switch_detail.get("agentMessages", [])
                if isinstance(switch_detail.get("agentMessages"), list)
                else []
            )
            expected_switch_tagged = min(3, expected_switch_messages) if expected_switch_messages > 1 else 1
            if expected_switch_tagged > 1:
                try:
                    await page.wait_for_function(
                        """([missionId, expectedCount]) =>
                          document.querySelectorAll(`[data-mission-id="${missionId}"]`).length >= expectedCount
                        """,
                        arg=[switch_mission_id, expected_switch_tagged],
                        timeout=args.timeout_ms,
                    )
                except Exception:
                    pass
            switched_body = await page.locator("body").inner_text(timeout=args.timeout_ms)
            switched_main_text = await _main_agent_text(page, args.timeout_ms)
            switched_tagged_count = await page.locator(f'[data-mission-id="{switch_mission_id}"]').count()
            switched_needles_visible = [
                item
                for item in switch_needles
                if item and _display_text(item).lower() in _display_text(switched_main_text).lower()
            ]
            switched_empty_dialogue_state = "no real hermes dialogue yet" in switched_body.lower()
            active_heading = ""
            try:
                active_heading = await page.locator(".fluxos-agent-main .fluxos-section-head strong").nth(0).inner_text(timeout=args.timeout_ms)
            except Exception:
                active_heading = ""
            record(
                "live-mission-click-switch",
                _display_text(switch_title).lower() in _display_text(switched_body).lower()
                and switch_mission_id in page.url
                and (
                    not active_heading
                    or _display_text(switch_title).lower() in _display_text(active_heading).lower()
                ),
                "Clicking another live NAS mission switches the Agent route and active run instead of leaving the old frame/thread stuck.",
                fromMissionId=selected_mission_id,
                toMissionId=switch_mission_id,
                toTitle=switch_title,
                pageUrl=page.url,
                activeHeading=active_heading,
                sidebarButtonCount=switch_button_count,
                buttonClickUsed=switch_click_used,
            )
            record(
                "switched-mission-specific-thread",
                bool(switch_detail.get("_httpOk"))
                and switch_detail.get("missionId") == switch_mission_id
                and (switched_tagged_count >= expected_switch_tagged or switched_empty_dialogue_state)
                and bool(switched_needles_visible),
                "After clicking another mission, Agent shows that mission's real dialogue rows or an honest empty dialogue state instead of promoting detail logs as chat.",
                missionId=switch_mission_id,
                status=switch_detail.get("_httpStatus"),
                taggedMessageCount=switched_tagged_count,
                expectedTaggedCount=expected_switch_tagged,
                emptyDialogueState=switched_empty_dialogue_state,
                matchedNeedles=switched_needles_visible[:3],
                candidateNeedles=switch_needles[:5],
                agentMessageCount=expected_switch_messages,
                eventCount=len(switch_detail.get("events", []) if isinstance(switch_detail.get("events"), list) else []),
            )
            await page.goto(_agent_url(args.url, selected_mission_id), wait_until="commit", timeout=args.timeout_ms)
            await page.wait_for_function(
                "(missionId) => new URL(window.location.href).searchParams.get('missionId') === missionId",
                arg=selected_mission_id,
                timeout=args.timeout_ms,
            )
            await page.wait_for_timeout(args.switch_settle_ms)
            body_text = await page.locator("body").inner_text(timeout=args.timeout_ms)
            dom_text = await page.content()
            lowered = body_text.lower()
            dom_lowered = dom_text.lower()
        forbidden = [
            "checkout qa",
            "market research",
            "landing polish",
            "image variants",
            "stripe integration",
            "dashboard redesign",
            "fixture layout preview",
        ]
        if "f1 telemetry" not in selected_title.lower():
            forbidden.extend(["f1 telemetry analytics", "build f1 telemetry analytics"])
        leaked = [item for item in forbidden if item in lowered]
        record(
            "no-demo-data-visible",
            not leaked,
            "Authenticated live Agent DOM does not expose known demo/fallback labels.",
            leakedLabels=leaked,
        )

        screenshot_focus = {"mode": "", "threadVisible": False, "selectedReportVisible": None, "composerVisible": False}
        try:
            live_button = page.locator('[data-agent-clarity-switch="true"] button', has_text="Live").first
            if await live_button.count() > 0:
                await live_button.click(timeout=args.timeout_ms)
            await page.wait_for_selector(
                '.fluxos-agent-grid[data-agent-clarity-mode="focus"]',
                timeout=max(args.settle_ms, 12000),
            )
            await page.wait_for_timeout(500)
            screenshot_focus = await page.evaluate(
                """
                () => {
                  const visible = selector => {
                    const node = document.querySelector(selector);
                    if (!node) return null;
                    const style = window.getComputedStyle(node);
                    const rect = node.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 1 && rect.height > 1;
                  };
                  return {
                    mode: document.querySelector('.fluxos-agent-grid')?.getAttribute('data-agent-clarity-mode') || '',
                    threadVisible: Boolean(visible('.fluxos-thread')),
                    selectedReportVisible: visible('.fluxos-agent-selected-report'),
                    composerVisible: Boolean(visible('.fluxos-composer')),
                  };
                }
                """
            )
            body_text = await page.locator("body").inner_text(timeout=args.timeout_ms)
            dom_text = await page.content()
        except Exception as exc:
            screenshot_focus["error"] = str(exc)[:240]
        record(
            "screenshot-captures-agent-live-dialogue",
            screenshot_focus.get("mode") == "focus"
            and screenshot_focus.get("threadVisible") is True
            and screenshot_focus.get("composerVisible") is True
            and screenshot_focus.get("selectedReportVisible") is False,
            "Final authenticated proof screenshot is captured from the Agent Live dialogue-first view, not the Details/proof reader mode.",
            **screenshot_focus,
        )

        await page.screenshot(path=str(screenshot_path), full_page=False, timeout=args.timeout_ms)
        dom_path.write_text(dom_text, encoding="utf-8")
        stats = image_stats(screenshot_path, min_width=args.min_width, min_height=args.min_height)
        record(
            "screenshot-nonblank",
            bool(stats.get("nonBlank")),
            "Authenticated live Agent screenshot is nonblank and meets minimum dimensions.",
            imageStats=stats,
            screenshotPath=str(screenshot_path),
            domPath=str(dom_path),
        )
        await browser.close()

    redacted_summary = {
        "generatedAt": summary.get("generatedAt") if isinstance(summary, dict) else "",
        "counts": counts,
        "runtimeCounts": summary.get("runtimeCounts", {}) if isinstance(summary, dict) else {},
        "statusCounts": summary.get("statusCounts", {}) if isinstance(summary, dict) else {},
        "notificationCount": len(notifications),
        "sliceNotificationCount": len(slice_notifications),
        "selectedMission": {
            "mission_id": selected_mission_id,
            "title": selected_title,
            "runtime_id": selected.get("runtime_id"),
            "status": selected.get("status"),
            "planner_loop_status": selected.get("planner_loop_status"),
        },
        "runningMissions": [
            {
                "mission_id": item.get("mission_id"),
                "title": item.get("title"),
                "runtime_id": item.get("runtime_id"),
                "status": item.get("status"),
                "planner_loop_status": item.get("planner_loop_status"),
            }
            for item in running
        ],
    }
    ok = all(item["passed"] for item in checks)
    result = {
        "schema": "fluxio.authenticated_live_agent.v1",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "url": _agent_url(args.url, selected_mission_id) if selected_mission_id else args.url,
        "ok": ok,
        "checks": checks,
        "summary": redacted_summary,
        "artifacts": {
            "screenshotPath": str(screenshot_path),
            "domPath": str(dom_path),
            "reportPath": str(report_path),
        },
        "nextAction": (
            "Authenticated live Agent route renders current NAS mission detail and messages."
            if ok
            else "Fix failed authenticated live-Agent checks before trusting Builder-to-Agent mission drill-down."
        ),
    }
    report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify authenticated Fluxio Agent renders live NAS mission detail.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--mission-id", default="")
    parser.add_argument("--out-dir", default=str(ROOT / "tmp-ui-checks" / "authenticated-live-agent"))
    parser.add_argument("--name", default="authenticated-live-agent")
    parser.add_argument("--username", default="")
    parser.add_argument("--password", default="")
    parser.add_argument(
        "--password-file",
        default=str(ROOT / ".agent_control" / "grand_agent_admin_password.txt"),
        help="Ignored local account password file. The verifier never prints the secret.",
    )
    parser.add_argument("--browser", choices=["auto", "chrome", "chromium", "edge", "zen"], default="auto")
    parser.add_argument("--browser-path", default="")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=1100)
    parser.add_argument("--min-width", type=int, default=1200)
    parser.add_argument("--min-height", type=int, default=900)
    parser.add_argument("--timeout-ms", type=int, default=60000)
    parser.add_argument("--settle-ms", type=int, default=9000)
    parser.add_argument("--switch-settle-ms", type=int, default=4500)
    parser.add_argument(
        "--expanded-interactions",
        action="store_true",
        help="Run the long optional click-through verifier after the core Agent proof.",
    )
    parser.add_argument(
        "--global-timeout-ms",
        type=int,
        default=120000,
        help="Hard cap for the full verifier; writes a failure receipt instead of hanging.",
    )
    args = parser.parse_args(argv)

    async def run_with_global_timeout() -> dict:
        try:
            return await asyncio.wait_for(
                _verify_async(args),
                timeout=max(1, int(args.global_timeout_ms or 120000)) / 1000,
            )
        except asyncio.TimeoutError:
            out_dir = Path(args.out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            report_path = out_dir / f"{args.name}-check.json"
            screenshot_path = out_dir / f"{args.name}.png"
            dom_path = out_dir / f"{args.name}.html"
            result = {
                "schema": "fluxio.authenticated_live_agent.v1",
                "checkedAt": datetime.now(timezone.utc).isoformat(),
                "url": args.url,
                "ok": False,
                "checks": [
                    {
                        "checkId": "global-timeout",
                        "passed": False,
                        "detail": (
                            "Authenticated live-Agent verifier exceeded the global timeout; "
                            "this is recorded as an explicit failed receipt instead of hanging."
                        ),
                        "timeoutMs": int(args.global_timeout_ms or 120000),
                    }
                ],
                "summary": {},
                "artifacts": {
                    "screenshotPath": str(screenshot_path),
                    "domPath": str(dom_path),
                    "reportPath": str(report_path),
                },
                "nextAction": "Reduce slow waits or fix the failing live-Agent route before trusting this proof.",
            }
            report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            return result

    result = asyncio.run(run_with_global_timeout())
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
