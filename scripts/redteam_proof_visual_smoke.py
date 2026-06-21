from __future__ import annotations

import base64
import json
import os
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


ARTIFACT_ROOT = ROOT / "artifacts" / "red-team" / "worker-f-jbheaven-safe-scenario-20260621"
CHECK_PATH = ARTIFACT_ROOT / "browser-proof.json"
URL = os.environ.get(
    "FLUXIO_CONTROL_URL",
    "http://127.0.0.1:1420/control?preview-control=1&fixture=live_review&mode=builder&surface=workbench&drawer=runtime",
)


def capture(cdp: Cdp, path: Path) -> None:
    result = cdp.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, str):
        raise RuntimeError(f"Screenshot capture failed for {path.name}.")
    path.write_bytes(base64.b64decode(data))


def run_viewport(width: int, height: int, screenshot_name: str) -> dict:
    port = free_port()
    profile = tempfile.TemporaryDirectory(prefix="fluxio-redteam-proof-cdp-")
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
            if cdp.eval('Boolean(document.querySelector(".redteam-proof-card"))'):
                break
            cdp.eval("window.scrollBy(0, 420)")
            time.sleep(0.35)
        cdp.eval(
            """
            (() => {
              const target = document.querySelector(".redteam-transcript-parity") ||
                document.querySelector(".redteam-proof-card");
              target?.scrollIntoView({ block: "center", inline: "nearest" });
            })();
            """
        )
        time.sleep(0.45)
        assert_current_control_shell(cdp)
        visible_text = str(cdp.eval('document.querySelector(".redteam-proof-card")?.innerText || ""'))
        normalized_visible_text = visible_text.lower()
        selectors = {
            "proofCard": bool(cdp.eval('Boolean(document.querySelector(".redteam-proof-card"))')),
            "promotionGates": bool(cdp.eval('Boolean(document.querySelector(".redteam-promotion-gates"))')),
            "taxonomyMap": bool(cdp.eval('Boolean(document.querySelector(".redteam-taxonomy-map"))')),
            "coverageMatrix": bool(cdp.eval('Boolean(document.querySelector(".redteam-coverage-matrix"))')),
            "probeTranscripts": bool(cdp.eval('Boolean(document.querySelector(".redteam-probe-transcripts"))')),
            "transcriptParity": bool(cdp.eval('Boolean(document.querySelector(".redteam-transcript-parity"))')),
        }
        screenshot_path = ARTIFACT_ROOT / screenshot_name
        capture(cdp, screenshot_path)
        expected = [
            "jbh-eaven controlled safe red-team probe set",
            "llm01:2025 prompt injection",
            "promotion gate summary",
            "transcript parity",
            "4/4 matched",
            "browser-proof.json",
            "sample_transcript.json",
        ]
        return {
            "viewport": {"width": width, "height": height},
            "screenshotPath": str(screenshot_path.resolve()),
            "selectors": selectors,
            "expectedFragments": expected,
            "missingFragments": [fragment for fragment in expected if fragment not in normalized_visible_text],
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
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    desktop = run_viewport(1440, 1180, "redteam-proof-desktop.png")
    mobile = run_viewport(390, 980, "redteam-proof-mobile.png")
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
