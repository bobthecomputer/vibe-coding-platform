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


OUT_DIR = ROOT / "artifacts" / "pr91-voice-dictation-repair-flow"
CHECK_PATH = OUT_DIR / "voice-control-checkpoint-check.json"
URL = "http://127.0.0.1:1420/control?preview-control=1&fixture=live_review&mode=agent&surface=agent"


def capture(cdp: Cdp, path: Path) -> None:
    result = cdp.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, str):
        raise RuntimeError("Screenshot capture failed for voice control checkpoint.")
    path.write_bytes(base64.b64decode(data))


def click_button(cdp: Cdp, label: str) -> bool:
    return bool(
        cdp.eval(
            f"""
            (() => {{
              const button = Array.from(document.querySelectorAll("button"))
                .find(item => (item.textContent || "").trim() === {json.dumps(label)});
              if (!button || button.disabled) return false;
              button.click();
              return true;
            }})()
            """
        )
    )


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
        checkpoint_text = str(cdp.eval('document.querySelector(".voice-control-checkpoint")?.innerText || ""'))
        opened_review = click_button(cdp, "Open voice review")
        time.sleep(0.8)
        wait_for_control_shell(cdp)
        cdp.eval(
            """
            (() => {
              const field = document.querySelector("#fluxio-voice-manual-dictation");
              if (!field) return false;
              const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
              if (setter) setter.call(field, "send message");
              else field.value = "send message";
              field.dispatchEvent(new Event("input", { bubbles: true }));
              return true;
            })()
            """
        )
        time.sleep(0.25)
        added_dictation = click_button(cdp, "Add to review")
        time.sleep(0.8)
        cdp.eval(
            """
            document.querySelector(".fluxio-voice-mode-checkpoint")
              ?.scrollIntoView({ block: "center", inline: "nearest" });
            """
        )
        time.sleep(0.45)
        visible_text = f"{checkpoint_text}\n{str(cdp.eval('document.body.innerText || \"\"'))}"
        run_disabled = bool(
            cdp.eval(
                """
                (() => {
                  const run = Array.from(document.querySelectorAll("button"))
                    .find(item => (item.textContent || "").trim() === "Run");
                  return Boolean(run?.disabled);
                })()
                """
            )
        )
        mode_switch_found = bool(cdp.eval('Boolean(document.querySelector(".fluxio-voice-mode-switch"))'))
        mode_checkpoint_found = bool(cdp.eval('Boolean(document.querySelector(".fluxio-voice-mode-checkpoint"))'))
        screenshot_path = OUT_DIR / "voice-control-checkpoint.png"
        capture(cdp, screenshot_path)
        expected = [
            "VOICE CONTROL CHECKPOINT",
            "Open voice review",
            "Mode:",
            "Unknown confidence:",
            "System dictation",
            "MODE CHECKPOINT",
            "Dictation mode",
            "hold_for_mode_review",
        ]
        report = {
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "url": URL,
            "browser": str(CHROME),
            "screenshotPath": str(screenshot_path.resolve()),
            "openedReview": opened_review,
            "addedDictation": added_dictation,
            "runDisabledAfterRiskyDictation": run_disabled,
            "modeSwitchFound": mode_switch_found,
            "modeCheckpointFound": mode_checkpoint_found,
            "checkpointText": checkpoint_text,
            "expectedFragments": expected,
            "missingFragments": [fragment for fragment in expected if fragment not in visible_text],
        }
        report["passed"] = (
            not report["missingFragments"]
            and opened_review
            and added_dictation
            and run_disabled
            and mode_switch_found
            and mode_checkpoint_found
        )
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
