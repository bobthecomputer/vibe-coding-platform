from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from PIL import Image
except Exception as exc:  # pragma: no cover - environment guard
    Image = None
    PIL_IMPORT_ERROR = exc
else:
    PIL_IMPORT_ERROR = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "http://127.0.0.1:1420/control?preview-control=1&fixture=live_review&mode=builder&surface=workbench"
DEFAULT_OUT_DIR = ROOT / "docs" / "cleanup" / "before-after" / "2026-05-20"


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


def run_browser(browser: str, args: list[str], timeout: int = 45) -> subprocess.CompletedProcess[bytes]:
    headless_arg = "--headless=new" if browser_family(browser) == "chromium" else "--headless"
    return subprocess.run(
        [browser, headless_arg, "--disable-gpu", "--no-sandbox", *args],
        check=False,
        cwd=ROOT,
        capture_output=True,
        timeout=timeout,
    )


def decode_output(value: bytes | None) -> str:
    return (value or b"").decode("utf-8", errors="replace")


def image_stats(path: Path) -> dict[str, object]:
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
            "nonBlank": unique >= 24 and width >= 320 and height >= 600,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture and verify the rendered control route.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--name", default="runtime-workbench-visual-proof")
    parser.add_argument("--browser", choices=["auto", "chrome", "chromium", "edge", "zen"], default="auto")
    parser.add_argument("--browser-path", default="")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=1200)
    parser.add_argument(
        "--expect",
        action="append",
        default=None,
        help="Rendered DOM text that must be present. May be passed multiple times.",
    )
    args = parser.parse_args()

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

    expected = args.expect or ["Syntelos", "Agent", "Builder", "OpenClaw"]
    missing = [] if not dom_supported else [fragment for fragment in expected if fragment not in dom_text]
    skin_errors = []
    if dom_supported:
        if 'class="fluxio-shell' not in dom_text:
            skin_errors.append("missing .fluxio-shell current app root")
        if 'class="fluxos-shell' in dom_text:
            skin_errors.append("rendered removed .fluxos-shell reference skin")
        if 'class="grand-public-page' in dom_text:
            skin_errors.append("rendered public landing page instead of /control app")
    stats = image_stats(screenshot_path)
    passed = not missing and not skin_errors and bool(stats["nonBlank"])
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
        "skinErrors": skin_errors,
        "image": stats,
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
