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


OUT_DIR = ROOT / "artifacts" / "pr87-voice-control-checkpoint"
CHECK_PATH = OUT_DIR / "voice-control-checkpoint-check.json"
URL = "http://127.0.0.1:1420/control?preview-control=1&fixture=live_review&mode=agent&surface=agent"


def capture(cdp: Cdp, path: Path) -> None:
    result = cdp.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, str):
        raise RuntimeError("Screenshot capture failed for voice control checkpoint.")
    path.write_bytes(base64.b64decode(data))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    port = free_port()
    profile = tempfile.TemporaryDirectory(prefix="fluxio-voice-checkpoint-cdp-")
    process = subprocess.Popen(
        [
            str(CHROME),
            "--headless",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-sandbox",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile.name}",
            "--window-size=1440,1180",
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
        deadline = time.time() + 12
        while time.time() < deadline:
            if cdp.eval('Boolean(document.querySelector(".voice-control-checkpoint"))'):
                break
            cdp.eval("window.scrollBy(0, 360)")
            time.sleep(0.35)
        cdp.eval(
            """
            document.querySelector(".voice-control-checkpoint")
              ?.scrollIntoView({ block: "center", inline: "nearest" });
            """
        )
        time.sleep(0.45)
        assert_current_control_shell(cdp)
        visible_text = str(cdp.eval('document.querySelector(".voice-control-checkpoint")?.innerText || ""'))
        screenshot_path = OUT_DIR / "voice-control-checkpoint.png"
        capture(cdp, screenshot_path)
        expected = [
            "VOICE CONTROL CHECKPOINT",
            "Open voice review",
            "System dictation",
            "Guard:",
        ]
        report = {
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "url": URL,
            "browser": str(CHROME),
            "screenshotPath": str(screenshot_path.resolve()),
            "expectedFragments": expected,
            "missingFragments": [fragment for fragment in expected if fragment not in visible_text],
        }
        report["passed"] = not report["missingFragments"]
        CHECK_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 1
    finally:
        if ws:
            ws.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        profile.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
