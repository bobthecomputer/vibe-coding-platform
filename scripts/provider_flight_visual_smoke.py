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
    wait_for_text,
)


OUT_DIR = ROOT / "artifacts" / "pr85-provider-update-health"
CHECK_PATH = OUT_DIR / "provider-flight-focused-check.json"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    port = free_port()
    profile = tempfile.TemporaryDirectory(prefix="fluxio-provider-flight-cdp-")
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
            found = cdp.eval('Boolean(document.querySelector(".provider-flight-check"))')
            if found:
                break
            cdp.eval("window.scrollBy(0, 420)")
            time.sleep(0.35)
        else:
            wait_for_text(cdp, "Provider update flight check", timeout=0.5)
        cdp.eval(
            """
            document.querySelector(".provider-flight-check")
              ?.scrollIntoView({ block: "center", inline: "nearest" });
            """
        )
        time.sleep(0.4)
        assert_current_control_shell(cdp)
        wait_for_text(cdp, "Open provider ecosystem")
        screenshot_path = Path(capture(cdp, "provider-flight-focused")).resolve()
        final_path = OUT_DIR / "provider-flight-focused.png"
        if screenshot_path != final_path:
            screenshot_path.replace(final_path)
        visible_text = str(cdp.eval('document.querySelector(".provider-flight-check")?.innerText || ""'))
        report = {
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "url": BASE_URL,
            "browser": str(CHROME),
            "screenshotPath": str(final_path.resolve()),
            "expectedFragments": [
                "PROVIDER UPDATE FLIGHT CHECK",
                "Open provider ecosystem",
                "Review-only artifact",
            ],
            "missingFragments": [
                fragment
                for fragment in [
                    "PROVIDER UPDATE FLIGHT CHECK",
                    "Open provider ecosystem",
                    "Review-only artifact",
                ]
                if fragment not in visible_text
            ],
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
