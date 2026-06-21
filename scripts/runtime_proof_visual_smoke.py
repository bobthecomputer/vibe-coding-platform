from __future__ import annotations

import json
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from control_route_interaction_smoke import (
    BASE_URL,
    CHROME,
    ROOT,
    Cdp,
    DevToolsSocket,
    assert_current_control_shell,
    capture,
    free_port,
    wait_for_control_shell,
    wait_for_devtools,
    wait_for_ready,
)


OUT_DIR = ROOT / "artifacts" / "pr86-fused-runtime-proof-gates"
CHECK_PATH = OUT_DIR / "runtime-proof-focused-check.json"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    port = free_port()
    profile = tempfile.TemporaryDirectory(prefix="fluxio-runtime-proof-cdp-")
    process = subprocess.Popen(
        [
            str(CHROME),
            "--headless",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-sandbox",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile.name}",
            "--window-size=1440,1100",
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
        cdp.send("Page.navigate", {"url": BASE_URL})
        time.sleep(1.5)
        wait_for_ready(cdp)
        wait_for_control_shell(cdp)
        deadline = time.time() + 12
        while time.time() < deadline:
            if cdp.eval('Boolean(document.querySelector(".runtime-proof-flight-recorder"))'):
                break
            cdp.eval("window.scrollBy(0, 420)")
            time.sleep(0.35)
        cdp.eval(
            """
            document.querySelector(".runtime-proof-flight-recorder")
              ?.scrollIntoView({ block: "center", inline: "nearest" });
            """
        )
        time.sleep(0.4)
        assert_current_control_shell(cdp)
        screenshot_path = Path(capture(cdp, "runtime-proof-focused")).resolve()
        final_path = OUT_DIR / "runtime-proof-focused.png"
        if screenshot_path != final_path:
            screenshot_path.replace(final_path)
        visible_text = str(cdp.eval('document.querySelector(".runtime-proof-flight-recorder")?.innerText || ""'))
        expected = [
            "RUNTIME PROOF FLIGHT RECORDER",
            "Promotion blocked",
            "python scripts/runtime_lane_proof_harness.py",
        ]
        report = {
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "url": BASE_URL,
            "browser": str(CHROME),
            "screenshotPath": str(final_path.resolve()),
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
