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
    Cdp,
    DevToolsSocket,
    assert_current_control_shell,
    free_port,
    wait_for_devtools,
    wait_for_ready,
    wait_for_text,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "fluxio-image-chroma-proof-workflow-20260621"
URL = "http://127.0.0.1:1420/control?preview-control=1&surface=images&fixture=live_review&mode=builder"


def capture(cdp: Cdp, name: str) -> str:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = (OUT_DIR / f"{name}.png").resolve()
    result = cdp.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, str):
        raise RuntimeError("Screenshot capture failed.")
    path.write_bytes(base64.b64decode(data))
    return str(path)


def click_preview_matte(cdp: Cdp) -> object:
    return cdp.eval(
        """
(() => {
  const button = Array.from(document.querySelectorAll('button'))
    .find(item => item.innerText.trim().includes('Preview matte'));
  if (!button) return { clicked: false, reason: 'button not found' };
  button.scrollIntoView({ block: 'center', inline: 'center' });
  if (button.disabled) return { clicked: false, reason: 'button disabled' };
  button.click();
  return { clicked: true, text: button.innerText.trim() };
})()
""",
    )


def select_available_source(cdp: Cdp) -> object:
    return cdp.eval(
        """
(() => {
  const select = document.querySelector('#image-studio-matte-source');
  if (!select) return { selected: false, reason: 'source select not found' };
  const options = Array.from(select.options);
  const target = options.find(item => item.text.includes('Synthetic green-screen sample')) ||
    options.find(item => item.text.includes('Codex generated workbench reference')) ||
    options[0];
  if (!target) return { selected: false, reason: 'no source options' };
  select.value = target.value;
  select.dispatchEvent(new Event('change', { bubbles: true }));
  return { selected: true, label: target.text, value: target.value };
})()
""",
    )


def read_state(cdp: Cdp) -> object:
    return cdp.eval(
        """
(() => ({
  hasShell: Boolean(document.querySelector('.fluxio-shell')),
  hasStudio: Boolean(document.querySelector('.image-studio')),
  hasBreakdown: Boolean(document.querySelector('.image-studio-breakdown')),
  breakdownSteps: document.querySelectorAll('.image-studio-breakdown-step').length,
  hasDiagnostics: Boolean(document.querySelector('.image-studio-chroma-diagnostics')),
  hasLocalProof: Boolean(document.querySelector('.image-studio-local-matte-proof')),
  runButtonText: Array.from(document.querySelectorAll('button')).find(item => item.innerText.includes('Run provider image') || item.innerText.includes('Running provider'))?.innerText.trim() || '',
  runButtonDisabled: Boolean(Array.from(document.querySelectorAll('button')).find(item => item.innerText.includes('Run provider image'))?.disabled),
  proofImages: document.querySelectorAll('.image-studio-local-matte-proof img').length,
  proofSource: document.querySelector('#image-studio-matte-source')?.value || '',
  text: document.body.innerText.slice(0, 2000),
  url: location.href,
}))()
""",
    )


def main() -> int:
    if not CHROME.exists():
        raise RuntimeError(f"Chrome executable not found: {CHROME}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    port = free_port()
    profile = tempfile.TemporaryDirectory(prefix="fluxio-image-chroma-")
    process = subprocess.Popen(
        [
            str(CHROME),
            "--headless",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-sandbox",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile.name}",
            "--window-size=1440,1200",
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
        wait_for_text(cdp, "Provider-ready image playground", timeout=18)
        assert_current_control_shell(cdp)
        wait_for_text(cdp, "Matte QA checklist")
        before = read_state(cdp)
        selected = select_available_source(cdp)
        if not isinstance(selected, dict) or not selected.get("selected"):
            raise RuntimeError(f"Could not select proof source: {selected}")
        clicked = click_preview_matte(cdp)
        if not isinstance(clicked, dict) or not clicked.get("clicked"):
            raise RuntimeError(f"Could not click Preview matte: {clicked}")
        try:
            wait_for_text(cdp, "Transparent preview", timeout=12)
            wait_for_text(cdp, "Matte mask", timeout=12)
        except Exception:
            time.sleep(1.0)
        after = read_state(cdp)
        screenshot = capture(cdp, "image-chroma-proof-interaction")
        report = {
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "url": URL,
            "browser": str(CHROME),
            "clicked": clicked,
            "selected": selected,
            "before": before,
            "after": after,
            "screenshotPath": screenshot,
            "passed": (
                bool(after.get("hasBreakdown"))
                and int(after.get("breakdownSteps") or 0) >= 6
                and bool(after.get("hasLocalProof"))
                and int(after.get("proofImages") or 0) >= 2
                and "Run provider image" in str(after.get("runButtonText") or "")
                and bool(after.get("runButtonDisabled"))
            ),
        }
        report_path = OUT_DIR / "image-chroma-proof-interaction-check.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
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
