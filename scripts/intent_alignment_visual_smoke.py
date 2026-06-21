from __future__ import annotations

import argparse
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
    free_port,
    wait_for_control_shell,
    wait_for_devtools,
    wait_for_ready,
    wait_for_text,
)
from control_route_visual_smoke import git_head, image_stats


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "http://127.0.0.1:1420/control?preview-control=1&fixture=verification_failure&mode=builder&surface=workbench"
DEFAULT_OUT_DIR = ROOT / "artifacts" / "pr111-intent-drift-recovery"


def capture(cdp: Cdp, path: Path) -> None:
    result = cdp.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, str):
        raise RuntimeError("CDP screenshot capture did not return image data.")
    path.write_bytes(base64.b64decode(data))


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture the visible Fluxio intent-alignment recovery proof.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--name", default="intent-alignment-proof-focused")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=1200)
    args = parser.parse_args()

    if not CHROME.exists():
        raise RuntimeError(f"Chrome executable not found: {CHROME}")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = (out_dir / f"{args.name}.png").resolve()
    report_path = (out_dir / f"{args.name}-check.json").resolve()
    port = free_port()
    profile = tempfile.TemporaryDirectory(prefix="fluxio-intent-cdp-")
    process = subprocess.Popen(
        [
            str(CHROME),
            "--headless",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-sandbox",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile.name}",
            f"--window-size={args.width},{args.height}",
            args.url,
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        tabs = wait_for_devtools(port)
        page = tabs[0]
        ws = DevToolsSocket(str(page["webSocketDebuggerUrl"]))
        cdp = Cdp(ws)
        try:
            cdp.send("Page.enable")
            cdp.send("Runtime.enable")
            wait_for_ready(cdp)
            wait_for_control_shell(cdp)
            wait_for_text(cdp, "Intent alignment", timeout=12)
            proof = cdp.eval(
                """
(() => {
  const target = document.querySelector('.intent-alignment-proof');
  if (!target) return { found: false };
  target.scrollIntoView({ block: 'center', inline: 'nearest' });
  const text = target.innerText || '';
  const rect = target.getBoundingClientRect();
  return {
    found: true,
    text,
    top: Math.round(rect.top),
    bottom: Math.round(rect.bottom),
    visible: rect.top >= 0 && rect.bottom <= window.innerHeight,
  };
})()
"""
            )
            time.sleep(0.3)
            capture(cdp, screenshot_path)
        finally:
            ws.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        profile.cleanup()

    stats = image_stats(screenshot_path)
    proof_text = str(proof.get("text") if isinstance(proof, dict) else "")
    expected = ["Intent alignment", "Original intent", "Current focus", "Recovery action", "Intent alignment receipt"]
    lowered_proof_text = proof_text.lower()
    missing = [fragment for fragment in expected if fragment.lower() not in lowered_proof_text]
    report = {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "url": args.url,
        "gitHead": git_head(),
        "viewport": {"width": args.width, "height": args.height},
        "screenshotPath": str(screenshot_path),
        "proofElement": proof,
        "expectedFragments": expected,
        "missingFragments": missing,
        "image": stats,
        "passed": bool(isinstance(proof, dict) and proof.get("found") and proof.get("visible") and not missing and stats["nonBlank"]),
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
