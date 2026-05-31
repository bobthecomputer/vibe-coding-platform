from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

from control_route_visual_smoke import find_browser, image_stats

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
            "Verifier selected a current NAS mission for the Agent detail route.",
            requestedMissionId=requested_mission_id,
            missionId=selected_mission_id,
            title=selected_title,
            status=selected.get("status"),
            plannerLoopStatus=selected.get("planner_loop_status"),
        )
        selected_detail = await _fetch_mission_detail(
            context,
            args.url,
            selected_mission_id,
            args.timeout_ms,
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
            await page.goto(_agent_url(args.url, selected_mission_id), wait_until="domcontentloaded", timeout=args.timeout_ms)
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
            await page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout_ms)
            await page.wait_for_timeout(args.settle_ms)

        body_text = await page.locator("body").inner_text(timeout=args.timeout_ms)
        main_text = await _main_agent_text(page, args.timeout_ms)
        dom_text = await page.content()
        lowered = body_text.lower()
        dom_lowered = dom_text.lower()
        title_visible = bool(selected_title and selected_title.lower() in lowered)
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
                title_visible = bool(selected_title and selected_title.lower() in lowered)
                selected_message_count = await page.locator(f'[data-mission-id="{selected_mission_id}"]').count()
            except Exception:
                # The concrete checks below will preserve the failure details.
                pass
        selected_needles_visible = [
            item for item in selected_needles if item and item.lower() in main_text.lower()
        ]
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
            selected_message_count > 0 and bool(selected_needles_visible),
            "Visible Agent messages are tagged with the selected mission id and contain selected mission-detail text.",
            missionId=selected_mission_id,
            taggedMessageCount=selected_message_count,
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
            and selected_title.lower() in operations_brief_text.lower()
            and "alerts" in operations_brief_text.lower()
            and "queue" in operations_brief_text.lower(),
            "Agent shows a compact live operations brief with selected mission, queue, and notification state from live NAS data.",
            missionId=selected_mission_id,
            operationsBriefCount=operations_brief_count,
            operationsBriefText=operations_brief_text[:280],
        )
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
                        selectedReport: orderFor('[data-live-selected-report-reader="true"]'),
                        thread: orderFor('.fluxos-thread'),
                        diagnostics: orderFor('[data-agent-diagnostics-shelf="true"]'),
                        lane: orderFor('[data-live-agent-lane-board="true"]'),
                        thinking: orderFor('.fluxos-thinking-panel'),
                        plan: orderFor('.fluxos-plan-list'),
                      };
                    }
                    """
                )
            except Exception:
                thread_first_order = {}
        record(
            "live-agent-thread-first-band-visible",
            thread_first_band_count == 1
            and "thread-first agent" in thread_first_text.lower()
            and all(token in thread_first_text.lower() for token in ["messages", "selected", "lanes", "alerts"])
            and (
                not thread_first_order
                or (
                    thread_first_order.get("band", 99) < thread_first_order.get("thread", 99)
                    and thread_first_order.get("band", 99) < thread_first_order.get("selectedReport", 99)
                    < thread_first_order.get("thread", 99)
                    < thread_first_order.get("diagnostics", 99)
                    < thread_first_order.get("lane", 99)
                    < thread_first_order.get("thinking", 99)
                    < thread_first_order.get("plan", 99)
                )
            ),
            "Agent renders a report-first command flow: band, selected report, live report thread, then diagnostics.",
            commandBandCount=thread_first_band_count,
            commandBandText=thread_first_text[:280],
            visualOrder=thread_first_order,
        )
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
            match.group(1).strip()[:80]
            for needle in runtime_output_needles
            for match in [re.search(r"Runtime output:\s*(.+?)(?:\s+[·]\s+Action:|\s+[·]\s+Target:|\s*$)", needle)]
            if match and len(match.group(1).strip()) >= 24
        ]
        runtime_output_visible = [
            needle[:80]
            for needle in runtime_output_needles
            if needle[:80].lower() in lowered
        ]
        runtime_report_body_visible = [
            needle
            for needle in runtime_report_body_needles
            if needle.lower() in lowered
        ]
        if runtime_output_needles:
            try:
                await page.wait_for_selector(
                    '[data-runtime-report="true"][data-message-zone="thread"]',
                    timeout=max(args.settle_ms, 12000),
                )
            except Exception:
                pass
        else:
            try:
                await page.wait_for_selector(
                    '[data-hermes-transcript="true"][data-message-zone="thread"]',
                    timeout=max(args.settle_ms, 12000),
                )
            except Exception:
                pass
        record(
            "runtime-output-visible-in-thread",
            not runtime_output_needles or bool(runtime_report_body_visible),
            "Agent thread surfaces the concrete Hermes/runtime slice body as the message text instead of requiring the raw Runtime output prefix.",
            missionId=selected_mission_id,
            runtimeOutputCount=len(runtime_output_needles),
            matchedRuntimeOutputs=runtime_output_visible[:3],
            matchedRuntimeReportBodies=runtime_report_body_visible[:3],
            skipped=len(runtime_output_needles) == 0,
        )
        runtime_report_row_count = await page.locator('[data-runtime-report="true"][data-message-zone="thread"]').count()
        hermes_transcript_row_count = await page.locator('[data-hermes-transcript="true"][data-message-zone="thread"]').count()
        live_thread_row_count = await page.locator('.fluxos-agent-main [data-message-zone="thread"][data-turn-id]').count()
        non_report_thread_row_count = await page.locator(
            '.fluxos-agent-main [data-message-zone="thread"][data-turn-id]:not([data-runtime-report="true"])'
        ).count()
        record(
            "runtime-report-rows-promoted",
            len(runtime_output_needles) == 0 or runtime_report_row_count > 0,
            "Runtime output rows are promoted as first-class selectable Agent messages instead of only appearing under action bookkeeping.",
            runtimeReportRows=runtime_report_row_count,
            runtimeOutputCount=len(runtime_output_needles),
            skipped=len(runtime_output_needles) == 0,
        )
        record(
            "live-agent-thread-is-runtime-report-only",
            (
                len(runtime_output_needles) > 0
                and live_thread_row_count == runtime_report_row_count
                and non_report_thread_row_count == 0
            )
            or (
                len(runtime_output_needles) == 0
                and live_thread_row_count == hermes_transcript_row_count
                and hermes_transcript_row_count > 0
            ),
            "The live Agent message list prefers concrete Runtime output rows and falls back to real Hermes transcript rows for completed missions with no Runtime output body.",
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
        expected_role_set = sorted(set(expected_lane_roles))
        visible_role_set = sorted(set(visible_lane_roles))
        record(
            "live-agent-subagent-lane-board-visible",
            (
                len(expected_role_set) == 0
                or (
                    visible_lane_count >= len(expected_role_set)
                    and all(role in visible_role_set for role in expected_role_set)
                    and "sub-agent lane board" in lowered
                )
            ),
            "Agent renders live planner/executor/verifier lanes from the NAS provider capability contract, not only delegated session rows.",
            missionId=selected_mission_id,
            expectedLaneRoles=expected_role_set,
            visibleLaneRoles=visible_role_set,
            visibleLaneCount=visible_lane_count,
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

        empty_transcript = "no live transcript loaded" in lowered or "the agent thread will stay empty" in lowered
        live_message_markers = [
            "mission-review-",
            "detail-message",
            "agent-chat-message",
            "fluxos-message role-assistant",
            "fluxos-tool-event",
            "agent-compartment-event",
            "live tool event",
            "runtime event",
        ]
        visible_message_markers = [marker for marker in live_message_markers if marker in dom_lowered or marker in lowered]
        record(
            "agent-thread-not-empty",
            bool(visible_message_markers),
            "Agent mission detail contains live/reconstructed mission messages instead of the empty-thread placeholder.",
            visibleMarkers=visible_message_markers,
            emptyPlaceholderVisible=empty_transcript,
        )
        record(
            "live-tool-event-visible",
            any(marker in visible_message_markers for marker in ["fluxos-tool-event", "agent-compartment-event", "live tool event", "runtime event"]),
            "Agent detail exposes live runtime/tool-event evidence for the selected mission.",
            visibleMarkers=visible_message_markers,
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
            runtime_output_count == 0
            and not has_hermes_transcript_fallback
            and not default_selected_text
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
        selected_report_empty_state = (
            runtime_output_count == 0
            and not has_hermes_transcript_fallback
            and selected_report_body_count == 0
            and "no selected report body returned yet" in selected_report_reader_lower
            and "live data only" in selected_report_reader_lower
        )
        record(
            "live-selected-report-reader-visible",
            selected_report_reader_count == 1
            and (selected_report_has_body or selected_report_empty_state)
            and "selected live report" in selected_report_reader_lower
            and not any(marker in selected_report_reader_lower for marker in bookkeeping_default_markers),
            "Agent main column shows the selected Hermes/runtime report reader, or an explicit no-report live state when NAS returned no report body.",
            readerCount=selected_report_reader_count,
            bodyCount=selected_report_body_count,
            runtimeOutputCount=runtime_output_count,
            hermesTranscriptRows=hermes_transcript_row_count,
            emptyState=selected_report_empty_state,
            readerText=selected_report_reader_text[:260],
            forbiddenMarkers=[marker for marker in bookkeeping_default_markers if marker in selected_report_reader_lower],
        )
        selection_version_count = await page.locator('[data-live-message-selection-version="v25"]').count()
        record(
            "live-message-selection-version-current",
            selection_version_count == 1,
            "Agent is running the v25 message-selection bundle that preserves manual live-message selection across feed refreshes, resets stale preview caches, and never embeds live preview frames.",
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
            runtime_output_count == 0
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
            empty_report_state = runtime_output_count == 0 and message_row_count == 0 and preview_frame_count == 0 and preview_state == "empty"
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
            await first_message.click(timeout=args.timeout_ms)
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
            await last_message.click(timeout=args.timeout_ms)
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
            record(
                "live-message-click-switch",
                first_selected_text != last_selected_text
                and first_reader_text != last_reader_text
                and first_match
                and last_match
                and reader_first_match
                and reader_last_match
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
            await workbench_page.goto(_workbench_url(args.url, selected_mission_id), wait_until="domcontentloaded", timeout=args.timeout_ms)
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
                    await page.goto(_agent_url(args.url, switch_mission_id), wait_until="domcontentloaded", timeout=args.timeout_ms)
            else:
                await page.goto(_agent_url(args.url, switch_mission_id), wait_until="domcontentloaded", timeout=args.timeout_ms)
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
                item for item in switch_needles if item and item.lower() in switched_main_text.lower()
            ]
            active_heading = ""
            try:
                active_heading = await page.locator(".fluxos-agent-main .fluxos-section-head strong").nth(0).inner_text(timeout=args.timeout_ms)
            except Exception:
                active_heading = ""
            record(
                "live-mission-click-switch",
                switch_title.lower() in switched_body.lower()
                and switch_mission_id in page.url
                and (not active_heading or switch_title.lower() in active_heading.lower()),
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
                and switched_tagged_count >= expected_switch_tagged
                and bool(switched_needles_visible),
                "After clicking another mission, the visible Agent thread is rebuilt from that mission's live detail endpoint.",
                missionId=switch_mission_id,
                status=switch_detail.get("_httpStatus"),
                taggedMessageCount=switched_tagged_count,
                expectedTaggedCount=expected_switch_tagged,
                matchedNeedles=switched_needles_visible[:3],
                candidateNeedles=switch_needles[:5],
                agentMessageCount=expected_switch_messages,
                eventCount=len(switch_detail.get("events", []) if isinstance(switch_detail.get("events"), list) else []),
            )
            body_text = switched_body
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
        leaked = [item for item in forbidden if item in lowered]
        record(
            "no-demo-data-visible",
            not leaked,
            "Authenticated live Agent DOM does not expose known demo/fallback labels.",
            leakedLabels=leaked,
        )

        await page.screenshot(path=str(screenshot_path), full_page=True)
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
    args = parser.parse_args(argv)

    result = asyncio.run(_verify_async(args))
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
