from __future__ import annotations

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
    capture,
    click_button,
    free_port,
    wait_for_control_shell,
    wait_for_devtools,
    wait_for_ready,
    wait_for_text,
)


OUT_DIR = Path(os.environ.get("FLUXIO_PROVIDER_FLIGHT_OUT_DIR", "")).resolve() if os.environ.get("FLUXIO_PROVIDER_FLIGHT_OUT_DIR") else ROOT / "artifacts" / "pr100-provider-source-verification-gate"
CHECK_PATH = OUT_DIR / "provider-flight-focused-check.json"
PROVIDER_FLIGHT_URL = os.environ.get(
    "FLUXIO_PROVIDER_FLIGHT_URL",
    os.environ.get(
        "FLUXIO_CONTROL_URL",
        "http://127.0.0.1:1420/control?preview-control=1&fixture=live_review&mode=builder&surface=workbench",
    ),
)


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
        cdp.send("Page.navigate", {"url": PROVIDER_FLIGHT_URL})
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
        click_button(cdp, "Open provider ecosystem")
        wait_for_text(cdp, "Provider route decision matrix")
        wait_for_text(cdp, "Source-backed model capability catalog")
        wait_for_text(cdp, "DeepSeek V4 Flash")
        cdp.eval(
            """
            document.querySelector(".provider-route-decision-matrix")
              ?.scrollIntoView({ block: "start", inline: "nearest" });
            """
        )
        deadline = time.time() + 8
        while time.time() < deadline:
            drawer_ready = cdp.eval(
                """
(() => Boolean(
  document.querySelector(".provider-ecosystem-panel")
  && document.querySelector(".provider-route-decision-matrix")
  && document.querySelector(".provider-model-catalog")
))()
"""
            )
            if drawer_ready:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("Provider ecosystem drawer did not expose route matrix and model catalog.")
        route_screenshot_path = Path(capture(cdp, "provider-ecosystem-route-matrix")).resolve()
        route_final_path = OUT_DIR / "provider-ecosystem-route-matrix.png"
        if route_screenshot_path != route_final_path:
            route_screenshot_path.replace(route_final_path)
        cdp.eval(
            """
            document.querySelector(".provider-model-catalog")
              ?.scrollIntoView({ block: "start", inline: "nearest" });
            """
        )
        time.sleep(0.35)
        model_screenshot_path = Path(capture(cdp, "provider-ecosystem-model-catalog")).resolve()
        model_final_path = OUT_DIR / "provider-ecosystem-model-catalog.png"
        if model_screenshot_path != model_final_path:
            model_screenshot_path.replace(model_final_path)
        visible_text = str(cdp.eval('document.querySelector(".provider-ecosystem-panel")?.innerText || ""'))
        report = {
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "url": PROVIDER_FLIGHT_URL,
            "browser": str(CHROME),
            "screenshotPath": str(model_final_path.resolve()),
            "screenshotPaths": {
                "routeMatrix": str(route_final_path.resolve()),
                "modelCatalog": str(model_final_path.resolve()),
            },
            "expectedFragments": [
                "Provider route decision matrix",
                "Source-backed model capability catalog",
                "GPT-5.5",
                "DeepSeek V4 Flash",
                "defaultChangeAllowed=false",
            ],
            "missingFragments": [
                fragment
                for fragment in [
                    "Provider route decision matrix",
                    "Source-backed model capability catalog",
                    "GPT-5.5",
                    "DeepSeek V4 Flash",
                    "defaultChangeAllowed=false",
                ]
                if fragment not in visible_text
            ],
        }
        report["selectors"] = {
            "providerEcosystemPanel": bool(cdp.eval('Boolean(document.querySelector(".provider-ecosystem-panel"))')),
            "routeDecisionMatrix": bool(cdp.eval('Boolean(document.querySelector(".provider-route-decision-matrix"))')),
            "modelCatalog": bool(cdp.eval('Boolean(document.querySelector(".provider-model-catalog"))')),
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
