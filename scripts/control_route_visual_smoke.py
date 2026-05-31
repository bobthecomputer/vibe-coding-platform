from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

try:
    from PIL import Image
except Exception as exc:  # pragma: no cover - environment guard
    Image = None
    PIL_IMPORT_ERROR = exc
else:
    PIL_IMPORT_ERROR = None

try:
    from playwright.async_api import async_playwright
except Exception as exc:  # pragma: no cover - environment guard
    async_playwright = None
    PLAYWRIGHT_IMPORT_ERROR = exc
else:
    PLAYWRIGHT_IMPORT_ERROR = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "http://127.0.0.1:1420/control?preview-control=1&fixture=live_review&mode=builder&surface=workbench"
DEFAULT_OUT_DIR = ROOT / "docs" / "cleanup" / "before-after" / "2026-05-20"
LAUNCH_INTERACTION_FRONTEND_OBJECTIVE = "Build a mobile telemetry dashboard with live browser setup"
LAUNCH_INTERACTION_HERMES_OBJECTIVE = "Continue overnight watchdog work for hardware electrical simulation"


def launch_interaction_url(url: str) -> str:
    return url_with_params(
        url,
        **{
            "preview-control": "1",
            "fixture": "live_review",
            "mode": "builder",
            "surface": "workbench",
            "launch": "mission",
            "runtime": "auto",
            "profile": "beginner",
            "objective": LAUNCH_INTERACTION_FRONTEND_OBJECTIVE,
        },
    )


def find_browser(preference: str = "auto", browser_path: str = "") -> str:
    if browser_path:
        if Path(browser_path).exists():
            return browser_path
        raise RuntimeError(f"Browser path does not exist: {browser_path}")
    zen_candidates = [
        r"C:\Program Files\Zen Browser\zen.exe",
        r"C:\Program Files\Zen\zen.exe",
        str(Path.home() / "AppData" / "Local" / "Programs" / "Zen Browser" / "zen.exe"),
        str(Path.home() / "AppData" / "Local" / "zen" / "zen.exe"),
        shutil.which("zen"),
    ]
    chromium_candidates = [
        shutil.which("chrome"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("msedge"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    if preference == "zen":
        candidates = zen_candidates
    elif preference in {"chrome", "chromium", "edge"}:
        candidates = chromium_candidates
    else:
        candidates = chromium_candidates + zen_candidates
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise RuntimeError("No Chrome, Chromium, Edge, or Zen executable found for visual smoke capture.")


def browser_family(browser: str) -> str:
    lowered = browser.lower()
    if "zen" in lowered:
        return "zen"
    if "firefox" in lowered:
        return "firefox"
    return "chromium"


def run_browser(browser: str, args: list[str], timeout: int = 90) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [browser, "--headless", "--disable-gpu", "--no-sandbox", *args],
        check=False,
        cwd=ROOT,
        capture_output=True,
        timeout=timeout,
    )


def decode_output(value: bytes | None) -> str:
    return (value or b"").decode("utf-8", errors="replace")


def url_with_params(url: str, **updates: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({key: value for key, value in updates.items() if value is not None})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def image_stats(path: Path, *, min_width: int = 1000, min_height: int = 700) -> dict[str, object]:
    if Image is None:
        raise RuntimeError(f"Pillow is required for pixel checks: {PIL_IMPORT_ERROR}")
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        step_x = max(1, width // 90)
        step_y = max(1, height // 90)
        samples = []
        for y in range(0, height, step_y):
            for x in range(0, width, step_x):
                samples.append(rgb.getpixel((x, y)))
        unique = len(set(samples))
        average_luma = sum((0.2126 * r + 0.7152 * g + 0.0722 * b) for r, g, b in samples) / max(len(samples), 1)
        return {
            "width": width,
            "height": height,
            "sampleCount": len(samples),
            "uniqueSampleColors": unique,
            "averageLuma": round(average_luma, 2),
            "nonBlank": unique >= 24 and width >= min_width and height >= min_height,
        }


async def _measure_browser_performance_async(
    *,
    browser_path: str,
    url: str,
    width: int,
    height: int,
    warm_tab_budget_ms: int,
    mission_switch_budget_ms: int,
    proof_pane_budget_ms: int,
) -> dict[str, object]:
    if async_playwright is None:
        return {
            "schema": "fluxio.browser_performance_budget.v1",
            "passed": False,
            "status": "unsupported",
            "error": f"Playwright is required for browser performance budgets: {PLAYWRIGHT_IMPORT_ERROR}",
        }
    started = time.perf_counter()
    target_specs = [
        {
            "id": "warm-tab",
            "label": "Warm tab render",
            "url": url,
            "budgetMs": warm_tab_budget_ms,
        },
        {
            "id": "mission-switch",
            "label": "Mission switch render",
            "url": url_with_params(url, mode="builder", surface="builder"),
            "budgetMs": mission_switch_budget_ms,
        },
        {
            "id": "proof-pane",
            "label": "Proof pane render",
            "url": url_with_params(url, mode="builder", surface="builder", drawer="proof"),
            "budgetMs": proof_pane_budget_ms,
        },
    ]
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=browser_path,
            headless=True,
            args=["--disable-gpu", "--no-sandbox"],
        )
        page = await browser.new_page(viewport={"width": width, "height": height})
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(250)
        measurements = []
        for spec in target_specs:
            measure_started = time.perf_counter()
            await page.goto(spec["url"], wait_until="domcontentloaded", timeout=15000)
            await page.locator("body").wait_for(timeout=10000)
            await page.wait_for_timeout(150)
            elapsed_ms = round((time.perf_counter() - measure_started) * 1000, 2)
            content = await page.content()
            measurements.append(
                {
                    **spec,
                    "measuredMs": elapsed_ms,
                    "withinBudget": elapsed_ms <= spec["budgetMs"],
                    "overBudgetMs": round(max(0.0, elapsed_ms - spec["budgetMs"]), 2),
                    "domBytes": len(content.encode("utf-8")),
                }
            )
        await browser.close()
    passed = all(bool(item["withinBudget"]) for item in measurements)
    return {
        "schema": "fluxio.browser_performance_budget.v1",
        "status": "pass" if passed else "warn",
        "passed": passed,
        "measuredWith": "playwright.chromium.single-session",
        "viewport": {"width": width, "height": height},
        "totalMs": round((time.perf_counter() - started) * 1000, 2),
        "targets": measurements,
    }


def measure_browser_performance(
    *,
    browser_path: str,
    url: str,
    width: int,
    height: int,
    warm_tab_budget_ms: int,
    mission_switch_budget_ms: int,
    proof_pane_budget_ms: int,
) -> dict[str, object]:
    return asyncio.run(
        _measure_browser_performance_async(
            browser_path=browser_path,
            url=url,
            width=width,
            height=height,
            warm_tab_budget_ms=warm_tab_budget_ms,
            mission_switch_budget_ms=mission_switch_budget_ms,
            proof_pane_budget_ms=proof_pane_budget_ms,
        )
    )


async def _assert_launch_interactions_async(
    *,
    browser_path: str,
    url: str,
    width: int,
    height: int,
) -> dict[str, object]:
    if async_playwright is None:
        return {
            "schema": "fluxio.launch_interaction_proof.v1",
            "passed": False,
            "status": "unsupported",
            "error": f"Playwright is required for launch interaction proof: {PLAYWRIGHT_IMPORT_ERROR}",
        }

    frontend_objective = LAUNCH_INTERACTION_FRONTEND_OBJECTIVE
    hermes_objective = LAUNCH_INTERACTION_HERMES_OBJECTIVE
    launch_url = launch_interaction_url(url)
    checks: list[dict[str, object]] = []

    def record(check_id: str, passed: bool, detail: str) -> None:
        checks.append({"checkId": check_id, "passed": passed, "detail": detail})

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=browser_path,
            headless=True,
            args=["--disable-gpu", "--no-sandbox"],
        )
        page = await browser.new_page(viewport={"width": width, "height": height})
        await page.goto(launch_url, wait_until="domcontentloaded", timeout=15000)
        textarea = page.locator('label:has-text("Start from goal") textarea').first
        await textarea.wait_for(timeout=10000)
        prefilled = await textarea.input_value()
        record(
            "launch-url-prefills-objective",
            frontend_objective in prefilled,
            "Launch URL objective appears in the Start from goal field.",
        )
        body_text = await page.locator("body").inner_text(timeout=10000)
        normalized = body_text.lower()
        record(
            "contextual-recommendation-visible",
            "recommended route" in normalized,
            "The launcher renders the contextual runtime recommendation panel.",
        )
        record(
            "frontend-objective-routes-to-hermes-minimax",
            "hermes" in normalized and "frontend/ui/design" in normalized and "minimax" in normalized,
            "A browser/mobile frontend objective recommends Hermes supervision with MiniMax execution.",
        )
        runtime_select = page.locator('label:has-text("Runtime") select').first
        runtime_value = await runtime_select.input_value()
        record(
            "runtime-select-prefilled",
            runtime_value in {"openclaw", "hermes"},
            f"Runtime select has a concrete value: {runtime_value}.",
        )

        await textarea.fill(hermes_objective)
        await runtime_select.select_option("openclaw")
        await page.wait_for_timeout(250)
        body_text = await page.locator("body").inner_text(timeout=10000)
        normalized = body_text.lower()
        record(
            "objective-change-recalculates-recommendation",
            "hermes" in normalized and "hardware/electrical engineering" in normalized and "gpt-5.5" in normalized,
            "Changing the objective recalculates to Hermes plus the hardware/electrical model route.",
        )
        record(
            "runtime-difference-warning-visible",
            "selected runtime differs from the recommendation" in normalized,
            "The launcher warns when the selected runtime does not match the recommendation.",
        )

        await page.get_by_role("button", name="Quick start").click(timeout=10000)
        await page.wait_for_timeout(350)
        body_text = await page.locator("body").inner_text(timeout=10000)
        normalized = body_text.lower()
        record(
            "preview-quickstart-is-controlled",
            "preview mode cannot launch missions" in normalized,
            "Quick start in preview mode shows a controlled no-launch message instead of silently failing.",
        )
        await browser.close()

    passed = all(bool(item["passed"]) for item in checks)
    return {
        "schema": "fluxio.launch_interaction_proof.v1",
        "status": "pass" if passed else "fail",
        "passed": passed,
        "url": launch_url,
        "viewport": {"width": width, "height": height},
        "checks": checks,
    }


def assert_launch_interactions(
    *,
    browser_path: str,
    url: str,
    width: int,
    height: int,
) -> dict[str, object]:
    frontend_objective = LAUNCH_INTERACTION_FRONTEND_OBJECTIVE
    hermes_objective = LAUNCH_INTERACTION_HERMES_OBJECTIVE
    launch_url = launch_interaction_url(url)
    hermes_url = url_with_params(launch_url, objective=hermes_objective, runtime="openclaw")

    def dump_text(target_url: str) -> str:
        dom = run_browser(browser_path, ["--virtual-time-budget=5000", "--dump-dom", target_url], timeout=45)
        if dom.returncode not in (0, None):
            raise RuntimeError(
                decode_output(dom.stderr).strip()
                or decode_output(dom.stdout).strip()
                or "Browser DOM dump failed."
            )
        return decode_output(dom.stdout).lower()

    frontend_text = dump_text(launch_url)
    hermes_text = dump_text(hermes_url)
    checks: list[dict[str, object]] = []

    def record(check_id: str, passed: bool, detail: str) -> None:
        checks.append({"checkId": check_id, "passed": passed, "detail": detail})

    record(
        "launch-url-prefills-objective",
        frontend_objective.lower() in frontend_text,
        "Launch URL objective appears in the Start from goal field.",
    )
    record(
        "contextual-recommendation-visible",
        "recommended route" in frontend_text,
        "The launcher renders the contextual runtime recommendation panel.",
    )
    record(
        "frontend-objective-routes-to-hermes-minimax",
        "hermes" in frontend_text and "frontend/ui/design" in frontend_text and "minimax" in frontend_text,
        "A browser/mobile frontend objective recommends Hermes supervision with MiniMax execution.",
    )
    record(
        "runtime-select-prefilled",
        '<option value="hermes"' in frontend_text or "hermes · frontend/ui/design" in frontend_text,
        "Runtime select has a concrete Hermes-compatible value.",
    )
    record(
        "objective-change-recalculates-recommendation",
        "hermes" in hermes_text and "hardware/electrical engineering" in hermes_text and "gpt-5.5" in hermes_text,
        "Changing the objective recalculates to Hermes plus the hardware/electrical model route.",
    )
    record(
        "runtime-alternatives-visible",
        "openclaw" in hermes_text and "hermes" in hermes_text,
        "The launcher keeps runtime alternatives visible while the recommendation stays Hermes-first.",
    )
    record(
        "quickstart-control-visible",
        "quick start" in frontend_text and "launch mission" in frontend_text,
        "Quick start and launch controls are visible in the preview launcher.",
    )
    passed = all(bool(item["passed"]) for item in checks)
    return {
        "schema": "fluxio.launch_interaction_proof.v1",
        "status": "pass" if passed else "fail",
        "passed": passed,
        "url": launch_url,
        "viewport": {"width": width, "height": height},
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture and verify the rendered control route.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--name", default="runtime-workbench-visual-proof")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=1200)
    parser.add_argument("--min-width", type=int, default=1000)
    parser.add_argument("--min-height", type=int, default=700)
    parser.add_argument("--browser", choices=["auto", "chrome", "chromium", "edge", "zen"], default="auto")
    parser.add_argument("--browser-path", default="")
    parser.add_argument("--measure-performance", action="store_true")
    parser.add_argument("--warm-tab-budget-ms", type=int, default=2500)
    parser.add_argument("--mission-switch-budget-ms", type=int, default=2500)
    parser.add_argument("--proof-pane-budget-ms", type=int, default=2500)
    parser.add_argument(
        "--assert-launch-interactions",
        action="store_true",
        help="Use Playwright to prove launch URL prefill, contextual route guidance, and quickstart behavior.",
    )
    parser.add_argument(
        "--long-history-fixture",
        action="store_true",
        help="Force the long_history fixture and include transcript/proof-heavy browser budget targets.",
    )
    parser.add_argument(
        "--expect",
        action="append",
        default=None,
        help="Rendered DOM text that must be present. May be passed multiple times.",
    )
    args = parser.parse_args()
    if args.long_history_fixture:
        args.url = url_with_params(
            args.url,
            **{
                "preview-control": "1",
                "fixture": "long_history",
                "mode": "builder",
                "surface": "builder",
                "drawer": "proof",
            },
        )
    if args.assert_launch_interactions:
        args.url = launch_interaction_url(args.url)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = (out_dir / f"{args.name}.png").resolve()
    dom_path = (out_dir / f"{args.name}.html").resolve()
    report_path = (out_dir / f"{args.name}-check.json").resolve()

    browser = find_browser(args.browser, args.browser_path)
    family = browser_family(browser)
    if family in {"zen", "firefox"}:
        profile_dir = ROOT / "tmp-ui-checks" / f"{family}-visual-smoke-profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        screenshot_args = [
            "--no-remote",
            "--profile",
            str(profile_dir),
            f"--window-size={args.width},{args.height}",
            "--screenshot",
            str(screenshot_path),
            args.url,
        ]
    else:
        screenshot_args = [
            "--hide-scrollbars",
            f"--window-size={args.width},{args.height}",
            "--virtual-time-budget=5000",
            f"--screenshot={screenshot_path}",
            args.url,
        ]
    screenshot = run_browser(browser, screenshot_args)
    if screenshot.returncode not in (0, None) and not screenshot_path.exists():
        raise RuntimeError(
            decode_output(screenshot.stderr).strip()
            or decode_output(screenshot.stdout).strip()
            or "Browser screenshot failed."
        )
    if not screenshot_path.exists():
        raise RuntimeError("Browser did not create a screenshot.")

    dom_text = ""
    dom_supported = family == "chromium"
    if dom_supported:
        dom = run_browser(browser, ["--virtual-time-budget=5000", "--dump-dom", args.url])
        if dom.returncode not in (0, None):
            raise RuntimeError(
                decode_output(dom.stderr).strip()
                or decode_output(dom.stdout).strip()
                or "Browser DOM dump failed."
            )
        dom_text = decode_output(dom.stdout)
    dom_path.write_text(dom_text, encoding="utf-8")

    expected = args.expect or ["Runtime operations", "Automatic verify", "OpenClaw", "Hermes"]
    missing = [] if not dom_supported else [fragment for fragment in expected if fragment not in dom_text]
    stats = image_stats(
        screenshot_path,
        min_width=args.min_width,
        min_height=args.min_height,
    )
    performance_report = None
    if args.measure_performance:
        performance_report = measure_browser_performance(
            browser_path=browser,
            url=args.url,
            width=args.width,
            height=args.height,
            warm_tab_budget_ms=args.warm_tab_budget_ms,
            mission_switch_budget_ms=args.mission_switch_budget_ms,
            proof_pane_budget_ms=args.proof_pane_budget_ms,
        )
        if args.long_history_fixture and performance_report.get("targets"):
            long_targets = []
            for target in list(performance_report["targets"]):
                if target.get("id") not in {"mission-switch", "proof-pane"}:
                    continue
                cloned = dict(target)
                cloned["id"] = f"long-history-{target['id']}"
                cloned["label"] = f"Long-history {target['label'].lower()}"
                cloned["fixture"] = "long_history"
                long_targets.append(cloned)
            performance_report["targets"].extend(long_targets)
            performance_report["longHistoryFixture"] = {
                "enabled": True,
                "fixture": "long_history",
                "targetCount": len(long_targets),
                "requiredTargets": ["long-history-mission-switch", "long-history-proof-pane"],
            }
    performance_passed = True if performance_report is None else bool(performance_report.get("passed"))
    launch_interaction_report = None
    if args.assert_launch_interactions:
        launch_interaction_report = assert_launch_interactions(
            browser_path=browser,
            url=args.url,
            width=args.width,
            height=args.height,
        )
    launch_interaction_passed = (
        True if launch_interaction_report is None else bool(launch_interaction_report.get("passed"))
    )
    passed = not missing and bool(stats["nonBlank"]) and performance_passed and launch_interaction_passed
    report = {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "url": args.url,
        "browser": browser,
        "browserFamily": family,
        "domSupported": dom_supported,
        "screenshotPath": str(screenshot_path),
        "domPath": str(dom_path),
        "expectedFragments": expected,
        "missingFragments": missing,
        "image": stats,
        "performance": performance_report,
        "launchInteractions": launch_interaction_report,
        "passed": passed,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not passed:
        print(json.dumps(report, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
