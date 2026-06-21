from __future__ import annotations

import base64
import json
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from control_route_interaction_smoke import (
    CHROME,
    ROOT,
    Cdp,
    DevToolsSocket,
    assert_current_control_shell,
    free_port,
    wait_for_control_shell,
    wait_for_devtools,
    wait_for_ready,
)


OUT_DIR = ROOT / "artifacts" / "pr89-fusion-migration-gates"
CHECK_PATH = OUT_DIR / "fusion-migration-browser-proof.json"
URL = "http://127.0.0.1:1420/control?preview-control=1&fixture=live_review&mode=builder&surface=workbench&drawer=runtime"


def capture(cdp: Cdp, path: Path) -> None:
    result = cdp.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, str):
        raise RuntimeError(f"Screenshot capture failed for {path.name}.")
    path.write_bytes(base64.b64decode(data))


def run_viewport(width: int, height: int, screenshot_name: str) -> dict:
    port = free_port()
    profile = tempfile.TemporaryDirectory(prefix="fluxio-fusion-proof-cdp-")
    process = subprocess.Popen(
        [
            str(CHROME),
            "--headless",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-sandbox",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile.name}",
            f"--window-size={width},{height}",
            "about:blank",
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    ws: DevToolsSocket | None = None
    try:
        tabs = wait_for_devtools(port)
        ws = DevToolsSocket(str(tabs[0]["webSocketDebuggerUrl"]))
        cdp = Cdp(ws)
        cdp.send("Page.enable")
        cdp.send("Runtime.enable")
        cdp.send("Page.navigate", {"url": URL})
        time.sleep(1.5)
        wait_for_ready(cdp)
        wait_for_control_shell(cdp)
        deadline = time.time() + 14
        while time.time() < deadline:
            if cdp.eval('Boolean(document.querySelector(".fusion-adapter-panel"))'):
                break
            cdp.eval(
                """
                document.querySelector(".drawer-content")?.scrollBy(0, 520);
                window.scrollBy(0, 420);
                """
            )
            time.sleep(0.35)
        cdp.eval(
            """
            document.querySelector(".fusion-adapter-panel")
              ?.scrollIntoView({ block: "center", inline: "nearest" });
            """
        )
        time.sleep(0.45)
        assert_current_control_shell(cdp)
        visible_text = str(
            cdp.eval('document.querySelector(".drawer-content")?.innerText || document.body.innerText || ""')
        )
        selectors = {
            "fusionWorkbench": bool(cdp.eval('Boolean(document.querySelector(".fusion-adapter-panel"))')),
            "phaseStrip": bool(cdp.eval('Boolean(document.querySelector(".fusion-phase-strip"))')),
            "nextLane": bool(cdp.eval('Boolean(document.querySelector(".fusion-next-lane"))')),
            "gateList": bool(cdp.eval('Boolean(document.querySelector(".fusion-gate-list"))')),
            "migrationCard": bool(cdp.eval('Boolean(document.querySelector(".fusion-migration-card"))')),
            "signalCard": bool(cdp.eval('Boolean(document.querySelector(".fusion-signal-card"))')),
        }
        screenshot_path = OUT_DIR / screenshot_name
        capture(cdp, screenshot_path)
        visible_text_normalized = visible_text.lower()
        expected = [
            "fusion migration workbench",
            "mind tower adapter truth",
            "next safe slice",
            "read-only adapters",
            "passed:",
            "no-trading-execution",
        ]
        return {
            "viewport": {"width": width, "height": height},
            "screenshotPath": str(screenshot_path.resolve()),
            "selectors": selectors,
            "expectedFragments": expected,
            "missingFragments": [
                fragment for fragment in expected if fragment not in visible_text_normalized
            ],
        }
    finally:
        if ws:
            ws.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        profile.cleanup()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    desktop = run_viewport(1440, 1180, "fusion-migration-desktop.png")
    mobile = run_viewport(390, 980, "fusion-migration-mobile.png")
    runs = [desktop, mobile]
    selector_failures = [
        f"{run['viewport']['width']}x{run['viewport']['height']}:{name}"
        for run in runs
        for name, present in run["selectors"].items()
        if not present
    ]
    missing_fragments = {
        f"{run['viewport']['width']}x{run['viewport']['height']}": run["missingFragments"]
        for run in runs
        if run["missingFragments"]
    }
    report = {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "url": URL,
        "browser": str(CHROME),
        "runs": runs,
        "selectorFailures": selector_failures,
        "missingFragmentsByViewport": missing_fragments,
        "passed": not selector_failures and not missing_fragments,
    }
    CHECK_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
