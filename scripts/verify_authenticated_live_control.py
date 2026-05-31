from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

from control_route_visual_smoke import find_browser, image_stats

try:
    from playwright.async_api import async_playwright
except Exception as exc:  # pragma: no cover - environment guard
    async_playwright = None
    PLAYWRIGHT_IMPORT_ERROR = exc
else:
    PLAYWRIGHT_IMPORT_ERROR = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "https://sysnology.tail602108.ts.net:47880/control?mode=builder&surface=builder"


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
        raise RuntimeError("Missing Fluxio account username or password for authenticated live-control verification.")
    return next_username, next_password


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def _api_url(url: str, path: str) -> str:
    return urljoin(_origin(url) + "/", path.lstrip("/"))


def _backend_command_from_request(request: object) -> str:
    try:
        method = str(getattr(request, "method", "") or "").upper()
        request_url = str(getattr(request, "url", "") or "")
    except Exception:
        return ""
    if method != "POST" or not urlsplit(request_url).path.endswith("/api/backend"):
        return ""
    try:
        raw = getattr(request, "post_data", "") or ""
        payload = json.loads(raw) if raw else {}
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("command") or "").strip()


def _requested_surface(url: str) -> str:
    parts = urlsplit(url)
    values = parse_qs(parts.query).get("surface", [])
    return str(values[0] if values else "").strip().lower()


async def _verify_async(args: argparse.Namespace) -> dict:
    if async_playwright is None:
        return {
            "schema": "fluxio.authenticated_live_control.v1",
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
                    "payload": {"payload": {"root": None}},
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
        system_audit_digest = (
            summary.get("systemAuditDigest", {})
            if isinstance(summary, dict) and isinstance(summary.get("systemAuditDigest"), dict)
            else {}
        )
        system_loss_breakdown = (
            system_audit_digest.get("systemLossBreakdown", {})
            if isinstance(system_audit_digest.get("systemLossBreakdown"), dict)
            else {}
        )
        skill_library = summary.get("skillLibrary", {}) if isinstance(summary, dict) and isinstance(summary.get("skillLibrary"), dict) else {}
        skill_feedback_loop = skill_library.get("feedbackLoop", {}) if isinstance(skill_library.get("feedbackLoop"), dict) else {}
        project_progress_history = (
            summary.get("projectProgressHistory", {})
            if isinstance(summary, dict) and isinstance(summary.get("projectProgressHistory"), dict)
            else {}
        )
        scheduling_queue = (
            project_progress_history.get("schedulingQueue", [])
            if isinstance(project_progress_history.get("schedulingQueue"), list)
            else []
        )
        running = [item for item in missions if item.get("status") == "running"]
        slice_notifications = [item for item in notifications if item.get("kind") == "mission_slice_completed"]
        running_mission_ids = {
            str(item.get("mission_id") or item.get("missionId") or "")
            for item in running
            if str(item.get("mission_id") or item.get("missionId") or "").strip()
        }
        running_status_notifications = [
            item
            for item in notifications
            if item.get("kind") == "mission_status"
            and str(item.get("missionId") or item.get("mission_id") or "") in running_mission_ids
        ]
        low_signal_notification_phrases = [
            "git_diff completed with filesystem snapshot",
            "git is unavailable",
            "delegated runtime heartbeat",
            "file mutation completed",
            "mission status changed",
        ]
        low_signal_running_notifications = [
            {
                "missionId": item.get("missionId") or item.get("mission_id"),
                "source": item.get("agentMessageSource"),
                "message": str(item.get("agentMessage") or item.get("detail") or "")[:240],
            }
            for item in running_status_notifications
            if any(
                phrase in str(item.get("agentMessage") or item.get("detail") or "").lower()
                for phrase in low_signal_notification_phrases
            )
        ]
        non_runtime_running_notifications = [
            {
                "missionId": item.get("missionId") or item.get("mission_id"),
                "source": item.get("agentMessageSource"),
                "message": str(item.get("agentMessage") or item.get("detail") or "")[:240],
            }
            for item in running_status_notifications
            if not str(item.get("agentMessageSource") or "").startswith(
                ("runtime_transcript:", "runtime_output:")
            )
        ]
        requested_surface = _requested_surface(args.url)
        requested_query = parse_qs(urlsplit(args.url).query)
        is_launch_route = str((requested_query.get("launch") or [""])[0]).strip().lower() == "mission"
        is_builder_surface = requested_surface in {"", "builder"}
        record(
            "summary-api-authenticated",
            bool(summary_payload.get("ok")) and len(missions) > 0,
            "Authenticated browser context can read the NAS control-room summary.",
            status=summary_payload.get("status"),
            missionCount=len(missions),
        )
        record(
            "summary-has-live-running-missions",
            int(counts.get("activeMissions") or 0) >= args.min_running and len(running) >= args.min_running,
            "Live summary reports active running missions.",
            activeMissions=counts.get("activeMissions"),
            runningMissionIds=[item.get("mission_id") for item in running],
        )
        record(
            "summary-has-slice-notifications",
            len(slice_notifications) >= args.min_slice_notifications,
            "Live summary includes mission-slice completion notifications.",
            sliceNotificationCount=len(slice_notifications),
        )
        record(
            "running-notifications-use-runtime-transcripts",
            len(running_status_notifications) >= min(args.min_running, len(running_mission_ids))
            and not non_runtime_running_notifications
            and not low_signal_running_notifications,
            "Running mission status notifications start from live Hermes/runtime transcript output instead of stale bookkeeping.",
            runningMissionIds=sorted(running_mission_ids),
            runningNotificationCount=len(running_status_notifications),
            nonRuntimeNotifications=non_runtime_running_notifications,
            lowSignalNotifications=low_signal_running_notifications,
            notificationSources=[
                {
                    "missionId": item.get("missionId") or item.get("mission_id"),
                    "source": item.get("agentMessageSource"),
                    "messageStart": str(item.get("agentMessage") or item.get("detail") or "")[:120],
                }
                for item in running_status_notifications[: args.max_expected_titles]
            ],
        )
        record(
            "summary-has-live-project-scheduling-queue",
            project_progress_history.get("schema") == "fluxio.project_progress_history.v1" and len(scheduling_queue) > 0,
            "Live summary includes the dependency-aware multi-project scheduling queue.",
            schema=project_progress_history.get("schema"),
            schedulingQueueCount=len(scheduling_queue),
            schedulerSchema=(project_progress_history.get("scheduler") or {}).get("schema")
            if isinstance(project_progress_history.get("scheduler"), dict)
            else None,
        )

        expected_titles = [
            str(item.get("title") or "")
            for item in running
            if str(item.get("title") or "").strip()
        ][: args.max_expected_titles]

        page = await context.new_page()
        page_backend_commands: list[str] = []

        def capture_backend_command(request: object) -> None:
            command = _backend_command_from_request(request)
            if command:
                page_backend_commands.append(command)

        page.on("request", capture_backend_command)
        await page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout_ms)
        await page.wait_for_timeout(args.settle_ms)
        if expected_titles:
            try:
                await page.wait_for_function(
                    """
                    titles => {
                      const text = (document.body?.innerText || "").toLowerCase();
                      if (text.includes("sign in to fluxio") || text.includes("checking fluxio session")) {
                        return false;
                      }
                      return titles.some(title => text.includes(String(title || "").toLowerCase()));
                    }
                    """,
                    arg=expected_titles,
                    timeout=max(args.timeout_ms, args.settle_ms),
                )
            except Exception:
                # Keep the detailed assertions below as the source of truth.
                pass
        body_text = await page.locator("body").inner_text(timeout=args.timeout_ms)
        page_html = await page.content()
        lowered = body_text.lower()
        if is_launch_route:
            starter_cards = page.locator('[data-mission-starter-templates="true"] [data-mission-template-id]')
            starter_card_count = await starter_cards.count()
            starter_text = ""
            selected_template_value = ""
            selected_template_recommendation = ""
            try:
                starter_text = await page.locator('[data-mission-starter-templates="true"]').first.inner_text(timeout=args.timeout_ms)
            except Exception:
                starter_text = ""
            f1_template = page.locator('[data-mission-template-id="f1-telemetry-analytics"]')
            if await f1_template.count():
                await f1_template.first.click(timeout=args.timeout_ms)
                await page.wait_for_timeout(350)
                try:
                    selected_template_value = await page.locator(".mission-quickstart-panel textarea").first.input_value(timeout=args.timeout_ms)
                except Exception:
                    selected_template_value = ""
                try:
                    selected_template_recommendation = await page.locator('[data-beginner-guided-launch="true"]').first.inner_text(timeout=args.timeout_ms)
                except Exception:
                    selected_template_recommendation = ""
            starter_text_lower = starter_text.lower()
            record(
                "mission-launch-starter-templates-visible",
                starter_card_count >= 4
                and "f1 telemetry analytics" in starter_text_lower
                and "rf/wireless mapping" in starter_text_lower
                and "hardware/electrical lab" in starter_text_lower
                and "frontend polish pass" in starter_text_lower,
                "Mission launcher exposes beginner starter templates for the requested project categories.",
                starterCardCount=starter_card_count,
                starterText=starter_text[:500],
            )
            selected_template_lower = selected_template_value.lower()
            recommendation_lower = selected_template_recommendation.lower()
            record(
                "mission-launch-template-applies-route-defaults",
                "f1 telemetry analytics workbench" in selected_template_lower
                and "lap comparison" in selected_template_lower
                and "f1/data analytics" in recommendation_lower
                and "gpt-5.5" in recommendation_lower,
                "Clicking a starter template fills the objective/checks and recalculates task-fit route/model guidance.",
                selectedObjective=selected_template_value[:500],
                recommendationText=selected_template_recommendation[:500],
            )
        record(
            "not-login-screen",
            "sign in to fluxio" not in lowered,
            "Authenticated page rendered beyond the login screen.",
        )
        record(
            "live-data-banner-visible",
            "live nas mission readiness" in lowered or "live nas missions" in lowered,
            "Builder shell exposes live NAS data labeling.",
        )
        full_snapshot_calls = page_backend_commands.count("get_control_room_snapshot_command")
        summary_calls = page_backend_commands.count("get_control_room_summary_command")
        record(
            "live-shell-summary-hotpath",
            full_snapshot_calls == 0 and summary_calls > 0,
            "Live browser load uses the authenticated summary/detail hot path instead of the slow full snapshot command.",
            backendCommands=page_backend_commands,
            summaryCommandCount=summary_calls,
            fullSnapshotCommandCount=full_snapshot_calls,
        )
        record(
            "no-refresh-failed-toast",
            "refresh failed:" not in lowered,
            "Live control shell did not show a refresh failure while rendering current NAS data.",
        )
        provider_admission_marker_count = page_html.count('data-provider-admission-truth="true"')
        record(
            "provider-admission-truth-visible",
            provider_admission_marker_count > 0
            and "admission vs quota" in lowered
            and "not a provider-limit" in lowered,
            "Live control shell separates provider runtime admission from quota/usage reporting so unreported quota is not shown as a provider limit.",
            markerCount=provider_admission_marker_count,
        )
        title_hits = [title for title in expected_titles if title and title.lower() in lowered]
        required_visible_titles = (
            len(expected_titles)
            if args.min_visible_titles <= 0
            else min(args.min_visible_titles, len(expected_titles))
        )
        record(
            "running-missions-visible-in-dom",
            len(title_hits) >= required_visible_titles,
            "Running mission titles from the live summary are visible in the authenticated DOM.",
            expectedTitles=expected_titles,
            visibleTitles=title_hits,
            requiredVisibleTitles=required_visible_titles,
        )
        expected_queue_labels = [
            str(item.get("workspaceName") or item.get("workspaceId") or "")
            for item in scheduling_queue
            if str(item.get("workspaceName") or item.get("workspaceId") or "").strip()
        ][:3]
        visible_queue_labels = [
            label for label in expected_queue_labels if label and label.lower() in lowered
        ]
        record(
            "live-builder-multi-project-queue-visible",
            (not is_builder_surface)
            or (
                "multi-project queue" in lowered
                and "data-live-builder-queue=\"true\"" in page_html
                and len(visible_queue_labels) >= min(1, len(expected_queue_labels))
            ),
            "Builder renders the live NAS dependency-aware multi-project queue instead of only a scheduler sentence.",
            expectedQueueLabels=expected_queue_labels,
            visibleQueueLabels=visible_queue_labels,
            schedulingQueueCount=len(scheduling_queue),
            skipped=not is_builder_surface,
        )
        command_band_count = await page.locator('[data-live-builder-command-band="true"]').count()
        command_band_text = ""
        if command_band_count > 0:
            try:
                command_band_text = await page.locator('[data-live-builder-command-band="true"]').first.inner_text(timeout=args.timeout_ms)
            except Exception:
                command_band_text = ""
        command_band_lower = command_band_text.lower()
        record(
            "live-builder-command-band-queue-first",
            (not is_builder_surface)
            or (
                command_band_count > 0
                and "queue-first builder" in command_band_lower
                and "projects" in command_band_lower
                and "missions" in command_band_lower
                and "queue" in command_band_lower
                and "alerts" in command_band_lower
                and "open top project" in command_band_lower
            ),
            "Builder renders a queue-first command band before lower diagnostic panels.",
            commandBandCount=command_band_count,
            commandBandText=command_band_text[:360],
            skipped=not is_builder_surface,
        )
        record(
            "live-builder-beginner-guide-visible",
            (not is_builder_surface)
            or (
                "beginner guide" in lowered
                and "data-live-beginner-guide=\"true\"" in page_html
                and "agent thread" in lowered
                and "notifications" in lowered
            ),
            "Builder renders a live-data beginner guide that connects the selected mission, Agent thread, queue, and notification state.",
            missionCount=len(missions),
            schedulingQueueCount=len(scheduling_queue),
            notificationCount=len(notifications),
            sliceNotificationCount=len(slice_notifications),
            skipped=not is_builder_surface,
        )
        advancement_digest = page.locator('[data-live-advancement-digest="true"]').first
        advancement_digest_count = await page.locator('[data-live-advancement-digest="true"]').count()
        advancement_mission_count = await page.locator('[data-live-advancement-mission="true"]').count()
        advancement_digest_text = ""
        advancement_row_texts: list[str] = []
        if advancement_digest_count > 0:
            try:
                advancement_digest_text = await advancement_digest.inner_text(timeout=args.timeout_ms)
            except Exception:
                advancement_digest_text = ""
        if advancement_mission_count > 0:
            try:
                advancement_row_texts = await page.locator('[data-live-advancement-mission="true"]').all_inner_texts()
            except Exception:
                advancement_row_texts = []
        advancement_digest_lower = advancement_digest_text.lower()
        visible_advancement_titles = [
            title for title in expected_titles if title and title.lower() in advancement_digest_lower
        ]
        record(
            "live-builder-advancement-digest-visible",
            (not is_builder_surface)
            or (
                advancement_digest_count == 1
                and advancement_mission_count >= min(1, len(missions))
                and "mission advancement digest" in advancement_digest_lower
                and "live nas only" in advancement_digest_lower
                and ("red-team" in advancement_digest_lower or "t3 comparison" in advancement_digest_lower)
                and len(visible_advancement_titles) >= min(1, len(expected_titles))
            ),
            "Builder groups live mission advancement and system self-improvement state in one NAS-only digest.",
            digestCount=advancement_digest_count,
            missionRows=advancement_mission_count,
            visibleAdvancementTitles=visible_advancement_titles,
            digestText=advancement_digest_text[:520],
            skipped=not is_builder_surface,
        )
        operations_brief_count = await page.locator('[data-live-operations-brief="true"]').count()
        operations_brief_text = ""
        if operations_brief_count > 0:
            try:
                operations_brief_text = await page.locator('[data-live-operations-brief="true"]').first.inner_text(timeout=args.timeout_ms)
            except Exception:
                operations_brief_text = ""
        record(
            "live-operations-brief-visible",
            (not is_builder_surface)
            or (
                operations_brief_count > 0
                and "running" in operations_brief_text.lower()
                and "queue" in operations_brief_text.lower()
                and "alerts" in operations_brief_text.lower()
            ),
            "Builder shows a compact live operations brief sourced from the NAS summary/detail; multi-project queue row count is verified separately.",
            operationsBriefCount=operations_brief_count,
            expectedQueueCount=len(scheduling_queue),
            operationsBriefText=operations_brief_text[:280],
            skipped=not is_builder_surface,
        )
        percent_pattern = r"\b(?:[1-9]\d?|100)%"
        operations_progress_visible = bool(re.search(percent_pattern, operations_brief_text))
        operations_title_candidates = [
            title for title in expected_titles if title and title.lower() in operations_brief_text.lower()
        ]
        selected_advancement_rows = [
            text
            for text in advancement_row_texts
            if any(title.lower() in text.lower() for title in operations_title_candidates)
        ]
        advancement_rows_to_check = selected_advancement_rows or advancement_row_texts
        selected_advancement_progress_visible = any(
            re.search(percent_pattern, text)
            for text in advancement_rows_to_check
        )
        selected_advancement_missing_progress = any(
            "no numeric progress" in text.lower()
            for text in selected_advancement_rows
        )
        record(
            "live-builder-advancement-progress-from-detail",
            (not is_builder_surface)
            or (not operations_progress_visible)
            or (
                selected_advancement_progress_visible
                and not selected_advancement_missing_progress
            ),
            "Builder advancement rows preserve the selected mission's live detail progress instead of downgrading it to missing summary progress.",
            operationsProgressVisible=operations_progress_visible,
            operationsTitleCandidates=operations_title_candidates,
            selectedAdvancementRows=[text[:320] for text in selected_advancement_rows],
            advancementRows=[text[:220] for text in advancement_row_texts[:5]],
            skipped=not is_builder_surface,
        )
        running_advancement_rows = [
            text
            for text in advancement_row_texts
            if any(title.lower() in text.lower() for title in expected_titles)
            and "running" in text.lower()
        ]
        running_advancement_rows_with_progress = [
            text
            for text in running_advancement_rows
            if re.search(percent_pattern, text) and "no numeric progress" not in text.lower()
        ]
        record(
            "live-builder-running-rows-have-progress",
            (not is_builder_surface)
            or len(running_advancement_rows_with_progress) >= min(len(expected_titles), len(running_advancement_rows)),
            "Every visible running mission in the Builder advancement digest has numeric live progress instead of a missing-progress placeholder.",
            runningAdvancementRows=[text[:260] for text in running_advancement_rows],
            runningRowsWithProgress=len(running_advancement_rows_with_progress),
            expectedRunningTitles=expected_titles,
            skipped=not is_builder_surface,
        )
        system_loss_count = await page.locator('[data-system-loss-current="true"]').count()
        system_loss_text = ""
        if system_loss_count > 0:
            try:
                system_loss_text = await page.locator('[data-system-loss-current="true"]').first.inner_text(timeout=args.timeout_ms)
            except Exception:
                system_loss_text = ""
        system_loss_lower = system_loss_text.lower()
        expected_system_score = ""
        expected_system_loss = ""
        if system_loss_breakdown.get("averageScoreOutOf20") is not None:
            try:
                expected_system_score = f"{float(system_loss_breakdown.get('averageScoreOutOf20')):g}/20"
            except Exception:
                expected_system_score = ""
        if system_loss_breakdown.get("averageLossOutOf20") is not None:
            try:
                expected_system_loss = f"loss {float(system_loss_breakdown.get('averageLossOutOf20')):g}/20"
            except Exception:
                expected_system_loss = ""
        system_loss_driver_titles = [
            str(item.get("category") or item.get("title") or "").strip()
            for item in (
                system_loss_breakdown.get("drivers", [])
                if isinstance(system_loss_breakdown.get("drivers"), list)
                else []
            )
            if isinstance(item, dict) and str(item.get("category") or item.get("title") or "").strip()
        ][:2]
        visible_system_loss_driver_titles = [
            title for title in system_loss_driver_titles if title.lower() in system_loss_lower
        ]
        record(
            "live-builder-system-loss-truth-visible",
            (not is_builder_surface)
            or (
                system_loss_count >= 1
                and "system loss" in system_loss_lower
                and (
                    not expected_system_score
                    or expected_system_score.lower() in system_loss_lower
                )
                and (
                    not expected_system_loss
                    or expected_system_loss.lower() in system_loss_lower
                )
                and len(visible_system_loss_driver_titles) >= min(1, len(system_loss_driver_titles))
            ),
            "Builder renders the current system-loss audit values and top remaining drivers from the live NAS digest.",
            systemLossCardCount=system_loss_count,
            expectedSystemScore=expected_system_score,
            expectedSystemLoss=expected_system_loss,
            expectedDriverTitles=system_loss_driver_titles,
            visibleDriverTitles=visible_system_loss_driver_titles,
            systemLossText=system_loss_text[:520],
            skipped=not is_builder_surface,
        )
        guided_steps = page.locator('[data-live-guided-next-steps="true"] [data-guided-step]')
        guided_step_count = await guided_steps.count()
        guided_text = ""
        if guided_step_count > 0:
            try:
                guided_text = await page.locator('[data-live-guided-next-steps="true"]').first.inner_text(timeout=args.timeout_ms)
            except Exception:
                guided_text = ""
        record(
            "live-guided-next-steps-visible",
            (not is_builder_surface)
            or (
                guided_step_count >= 4
                and "agent report" in guided_text.lower()
                and "multi-project queue" in guided_text.lower()
                and "notifications" in guided_text.lower()
                and "proof" in guided_text.lower()
            ),
            "Builder exposes an actionable live beginner path for Agent report, queue, notifications, and proof using current NAS state.",
            guidedStepCount=guided_step_count,
            guidedText=guided_text[:360],
            skipped=not is_builder_surface,
        )
        public_launch_steps = page.locator('[data-public-launch-proof-path="true"] [data-public-launch-proof-step]')
        public_launch_step_count = await public_launch_steps.count()
        public_launch_text = ""
        if public_launch_step_count > 0:
            try:
                public_launch_text = await page.locator('[data-public-launch-proof-path="true"]').first.inner_text(timeout=args.timeout_ms)
            except Exception:
                public_launch_text = ""
        public_launch_lower = public_launch_text.lower()
        public_launch_ready = "data-public-launch-ready=\"true\"" in page_html
        record(
            "live-public-launch-proof-path-visible",
            (not is_builder_surface)
            or (
                public_launch_step_count >= 5
                and "launcher package" in public_launch_lower
                and "public web" in public_launch_lower
                and "private nas" in public_launch_lower
                and "release packet" in public_launch_lower
                and "external publication" in public_launch_lower
            ),
            "Builder renders the live public launch proof path as ordered verifier-backed steps instead of only a blocker paragraph.",
            publicLaunchStepCount=public_launch_step_count,
            publicLaunchText=public_launch_text[:520],
            publicLaunchReady=public_launch_ready,
            skipped=not is_builder_surface,
        )
        public_launch_triage_count = await page.locator('[data-public-launch-dirty-source-triage="true"]').count()
        public_launch_triage_text = ""
        if public_launch_triage_count > 0:
            try:
                public_launch_triage_text = await page.locator('[data-public-launch-dirty-source-triage="true"]').first.inner_text(timeout=args.timeout_ms)
            except Exception:
                public_launch_triage_text = ""
        public_launch_triage_lower = public_launch_triage_text.lower()
        record(
            "live-public-launch-dirty-source-triage-visible",
            (not is_builder_surface)
            or (
                public_launch_triage_count >= 1
                and "release-impacting" in public_launch_triage_lower
                and (
                    "commit" in public_launch_triage_lower
                    or "clean" in public_launch_triage_lower
                    or "exclude" in public_launch_triage_lower
                    or "no dirty source sample" in public_launch_triage_lower
                    or "rerun public web verification" in public_launch_triage_lower
                )
            ),
            "Builder shows publication dirty-source triage so current-public-web blockers are actionable instead of a raw dirty-file count.",
            publicLaunchTriageCount=public_launch_triage_count,
            publicLaunchTriageText=public_launch_triage_text[:420],
            skipped=not is_builder_surface,
        )
        public_launch_repair_count = await page.locator('[data-public-launch-repair-packet="true"]').count()
        public_launch_repair_text = ""
        if public_launch_repair_count > 0:
            try:
                public_launch_repair_text = await page.locator('[data-public-launch-repair-packet="true"]').first.inner_text(timeout=args.timeout_ms)
            except Exception:
                public_launch_repair_text = ""
        public_launch_repair_lower = public_launch_repair_text.lower()
        record(
            "live-public-launch-repair-packet-visible",
            (not is_builder_surface)
            or (
                public_launch_repair_count >= 1
                and (
                    "launch repair packet" in public_launch_repair_lower
                    or "launch proof packet" in public_launch_repair_lower
                )
                and (
                    "cannot claim public launch" in public_launch_repair_lower
                    or "public launch proven" in public_launch_repair_lower
                    or "public launch claim enabled" in public_launch_repair_lower
                )
                and "full_git_status" in public_launch_repair_lower
                and "release-impacting path" in public_launch_repair_lower
                and (
                    "verifier command" in public_launch_repair_lower
                    or "rerun public launch verifiers" in public_launch_repair_lower
                    or "final public launch readiness check" in public_launch_repair_lower
                )
                and "receipt" in public_launch_repair_lower
            ),
            "Builder shows a concrete launch proof/repair packet with claim state, verifier commands, lanes, and receipt targets.",
            publicLaunchRepairCount=public_launch_repair_count,
            publicLaunchRepairText=public_launch_repair_text[:520],
            skipped=not is_builder_surface,
        )
        public_launch_staging_count = await page.locator('[data-public-launch-staging-plan="true"]').count()
        public_launch_staging_text = ""
        if public_launch_staging_count > 0:
            try:
                public_launch_staging_text = await page.locator('[data-public-launch-staging-plan="true"]').first.inner_text(timeout=args.timeout_ms)
            except Exception:
                public_launch_staging_text = ""
        public_launch_staging_lower = public_launch_staging_text.lower()
        record(
            "live-public-launch-staging-plan-visible",
            (not is_builder_surface)
            or (
                public_launch_staging_count >= 1
                and "release staging plan" in public_launch_staging_lower
                and "release paths" in public_launch_staging_lower
            ),
            "Builder shows a staging plan for release-impacting paths so the public-launch repair packet is executable.",
            publicLaunchStagingCount=public_launch_staging_count,
            publicLaunchStagingText=public_launch_staging_text[:420],
            skipped=not is_builder_surface,
        )
        public_launch_staging_proof_count = await page.locator('[data-public-launch-staging-proof="true"]').count()
        public_launch_staging_proof_text = ""
        if public_launch_staging_proof_count > 0:
            try:
                public_launch_staging_proof_text = await page.locator('[data-public-launch-staging-proof="true"]').first.inner_text(timeout=args.timeout_ms)
            except Exception:
                public_launch_staging_proof_text = ""
        public_launch_staging_proof_lower = public_launch_staging_proof_text.lower()
        record(
            "live-public-launch-staging-proof-visible",
            (not is_builder_surface)
            or (
                public_launch_staging_proof_count >= 1
                and "staging proof archived" in public_launch_staging_proof_lower
                and "release paths" in public_launch_staging_proof_lower
            ),
            "Builder shows the archived public-launch staging proof receipt beside the executable staging plan.",
            publicLaunchStagingProofCount=public_launch_staging_proof_count,
            publicLaunchStagingProofText=public_launch_staging_proof_text[:420],
            skipped=not is_builder_surface,
        )
        tutorial_steps = page.locator('[data-live-tutorial-path="true"] [data-live-tutorial-step]')
        tutorial_step_count = await tutorial_steps.count()
        tutorial_text = ""
        if tutorial_step_count > 0:
            try:
                tutorial_text = await page.locator('[data-live-tutorial-path="true"]').first.inner_text(timeout=args.timeout_ms)
            except Exception:
                tutorial_text = ""
        tutorial_lower = tutorial_text.lower()
        record(
            "live-builder-tutorial-path-visible",
            (not is_builder_surface)
            or (
                tutorial_step_count >= 5
                and "live operator tutorial" in tutorial_lower
                and "mission" in tutorial_lower
                and "queue" in tutorial_lower
                and "agent" in tutorial_lower
                and "notifications" in tutorial_lower
                and "proof" in tutorial_lower
                and "sample tutorial" in tutorial_lower
            ),
            "Builder exposes a live-data tutorial path for mission, queue, Agent, notifications, and proof.",
            tutorialStepCount=tutorial_step_count,
            tutorialText=tutorial_text[:420],
            skipped=not is_builder_surface,
        )
        visible_slice_labels = [
            str(item.get("title") or item.get("message") or item.get("detail") or "")
            for item in slice_notifications
            if str(item.get("title") or item.get("message") or item.get("detail") or "").strip()
        ][: args.max_expected_titles]
        slice_hits = [
            label
            for label in visible_slice_labels
            if label.lower() in lowered or "slice completed" in lowered or "mission updates" in lowered
        ]
        record(
            "slice-notifications-visible-in-dom",
            len(slice_hits) >= min(args.min_slice_notifications, len(visible_slice_labels) or args.min_slice_notifications),
            "Mission-slice completion notifications from the live summary are visible in the authenticated DOM.",
            expectedSliceLabels=visible_slice_labels,
            visibleSliceLabels=slice_hits,
        )
        notification_cards = page.locator(".notification-card")
        notification_dismiss_buttons = page.locator(".notification-card-dismiss")
        notification_inline_dismiss_buttons = page.locator('[data-notification-dismiss-inline="true"]')
        notification_card_count = await notification_cards.count()
        notification_dismiss_count = await notification_dismiss_buttons.count()
        notification_inline_dismiss_count = await notification_inline_dismiss_buttons.count()
        dismissed_card_count = notification_card_count
        if is_launch_route:
            record(
                "notification-dismiss-control",
                True,
                "Skipped on launch modal routes because the modal intentionally blocks background notification clicks; normal Builder routes enforce this control.",
                notificationCardCountBefore=notification_card_count,
                dismissButtonCount=notification_dismiss_count,
                inlineDismissButtonCount=notification_inline_dismiss_count,
                notificationCardCountAfter=dismissed_card_count,
                skipped=True,
            )
        elif notification_inline_dismiss_count > 0:
            await notification_inline_dismiss_buttons.first.click(timeout=args.timeout_ms)
            await page.wait_for_timeout(350)
            dismissed_card_count = await page.locator(".notification-card").count()
        elif notification_dismiss_count > 0:
            await notification_dismiss_buttons.first.click(timeout=args.timeout_ms)
            await page.wait_for_timeout(350)
            dismissed_card_count = await page.locator(".notification-card").count()
        if not is_launch_route:
            record(
                "notification-dismiss-control",
                notification_inline_dismiss_count > 0 and dismissed_card_count < notification_card_count,
                "Clicking an explicit live notification dismiss action removes that card from the authenticated UI.",
                notificationCardCountBefore=notification_card_count,
                dismissButtonCount=notification_dismiss_count,
                inlineDismissButtonCount=notification_inline_dismiss_count,
                notificationCardCountAfter=dismissed_card_count,
            )
        clear_button = page.locator('[data-notification-clear-all="true"]')
        clear_button_count = await clear_button.count()
        cleared_card_count = dismissed_card_count
        if is_launch_route:
            record(
                "notification-clear-all-control",
                True,
                "Skipped on launch modal routes because the modal intentionally blocks background notification clicks; normal Builder routes enforce this control.",
                clearButtonCount=clear_button_count,
                notificationCardCountAfterClear=cleared_card_count,
                skipped=True,
            )
        elif clear_button_count > 0:
            await clear_button.first.click(timeout=args.timeout_ms)
            await page.wait_for_timeout(350)
            cleared_card_count = await page.locator(".notification-card").count()
        if not is_launch_route:
            record(
                "notification-clear-all-control",
                clear_button_count > 0 and cleared_card_count == 0,
                "The Mark visible read control removes all visible live notification cards in the authenticated UI.",
                clearButtonCount=clear_button_count,
                notificationCardCountAfterClear=cleared_card_count,
            )
        forbidden = [
            "checkout qa",
            "market research",
            "landing polish",
            "image variants",
            "changed-file",
            "stripe integration",
            "dashboard redesign",
            "fixture layout preview",
        ]
        leaked = [item for item in forbidden if item in lowered]
        record(
            "no-demo-data-visible",
            not leaked,
            "Authenticated live Builder DOM does not expose known demo/fallback labels.",
            leakedLabels=leaked,
        )
        if requested_surface == "skills":
            live_skill_rows = page.locator('[data-live-skill-row="true"]')
            live_skill_row_count = await live_skill_rows.count()
            repair_skill_count = await page.locator('[data-live-skill-row="true"][data-skill-feedback-state*="repair"]').count()
            skill_command_band_count = await page.locator('[data-live-skills-command-band="true"]').count()
            skill_command_band_text = ""
            if skill_command_band_count > 0:
                try:
                    skill_command_band_text = await page.locator('[data-live-skills-command-band="true"]').first.inner_text(timeout=args.timeout_ms)
                except Exception:
                    skill_command_band_text = ""
            live_skill_summary_visible = "live measured capabilities" in lowered and "real skill rows" in lowered
            static_skill_leaks = [
                item
                for item in [
                    "ui refactor expert",
                    "api integration helper",
                    "data schema designer",
                    "security auditor",
                ]
                if item in lowered
            ]
            record(
                "live-skills-surface-uses-nas-skill-library",
                live_skill_summary_visible and live_skill_row_count > 0 and not static_skill_leaks,
                "Skills surface renders live NAS skill rows with stable DOM markers, not the bundled static skill catalog.",
                liveSkillRows=live_skill_row_count,
                expectedSkillRows=skill_library.get("totalSkills") or skill_library.get("managementSummary", {}).get("totalSkills"),
                staticSkillLeaks=static_skill_leaks,
                liveSource="control-room summary" if skill_library else "",
            )
            record(
                "live-skills-command-band-system-loss-first",
                skill_command_band_count == 1
                and "system-loss routing" in skill_command_band_text.lower()
                and "repair" in skill_command_band_text.lower()
                and "reinforce" in skill_command_band_text.lower(),
                "Skills surface starts with a live system-loss command band instead of burying repair state below the skill rows.",
                commandBandCount=skill_command_band_count,
                commandBandText=skill_command_band_text[:360],
            )
            record(
                "live-skills-surface-shows-system-loss-feedback",
                repair_skill_count > 0
                and "system loss routing" in lowered
                and int(skill_feedback_loop.get("measuredSkillCount") or 0) > 0,
                "Skills surface exposes measured system-loss feedback and repair-state skills from the live summary.",
                repairSkillRows=repair_skill_count,
                measuredSkillCount=skill_feedback_loop.get("measuredSkillCount"),
                repairCount=skill_feedback_loop.get("repairCount"),
                reinforceCount=skill_feedback_loop.get("reinforceCount"),
            )

        await page.screenshot(path=str(screenshot_path), full_page=True)
        dom_path.write_text(await page.content(), encoding="utf-8")
        stats = image_stats(screenshot_path, min_width=args.min_width, min_height=args.min_height)
        record(
            "screenshot-nonblank",
            bool(stats.get("nonBlank")),
            "Authenticated live control screenshot is nonblank and meets minimum dimensions.",
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
        "schema": "fluxio.authenticated_live_control.v1",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "url": args.url,
        "ok": ok,
        "checks": checks,
        "summary": redacted_summary,
        "artifacts": {
            "screenshotPath": str(screenshot_path),
            "domPath": str(dom_path),
            "reportPath": str(report_path),
        },
        "nextAction": (
            "Authenticated live control room renders current NAS mission data."
            if ok
            else "Fix failed authenticated live-control checks before trusting the web UI."
        ),
    }
    report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify authenticated Fluxio /control renders live NAS data.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--out-dir", default=str(ROOT / "tmp-ui-checks" / "authenticated-live-control"))
    parser.add_argument("--name", default="authenticated-live-control")
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
    parser.add_argument("--settle-ms", type=int, default=8000)
    parser.add_argument("--min-running", type=int, default=1)
    parser.add_argument("--min-slice-notifications", type=int, default=1)
    parser.add_argument(
        "--min-visible-titles",
        type=int,
        default=0,
        help="Minimum running titles that must appear. 0 means every expected running title must be visible.",
    )
    parser.add_argument("--max-expected-titles", type=int, default=3)
    args = parser.parse_args(argv)

    result = asyncio.run(_verify_async(args))
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
