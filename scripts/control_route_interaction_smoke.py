from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = Path(os.environ.get("FLUXIO_PROOF_OUT_DIR", str(ROOT / "docs" / "cleanup" / "before-after" / "2026-05-20")))
CHECK_PATH = OUT_DIR / "interaction-smoke-check.json"
BASE_URL = os.environ.get(
    "FLUXIO_CONTROL_URL",
    "http://127.0.0.1:1420/control?preview-control=1&fixture=live_review&mode=builder",
)
VIEWPORT_WIDTH = int(os.environ.get("FLUXIO_VIEWPORT_WIDTH", "1440"))
VIEWPORT_HEIGHT = int(os.environ.get("FLUXIO_VIEWPORT_HEIGHT", "1200"))
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def json_get(url: str) -> object:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


class DevToolsSocket:
    def __init__(self, websocket_url: str) -> None:
        parsed = urllib.parse.urlparse(websocket_url)
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 80
        self.path = parsed.path
        if parsed.query:
            self.path += f"?{parsed.query}"
        self.socket = socket.create_connection((self.host, self.port), timeout=10)
        self._handshake()

    def _handshake(self) -> None:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        self.socket.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.socket.recv(4096)
            if not chunk:
                break
            response += chunk
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError(f"WebSocket handshake failed: {response[:200]!r}")
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest())
        if accept not in response:
            raise RuntimeError("WebSocket handshake did not return the expected accept key.")

    def send_text(self, text: str) -> None:
        payload = text.encode("utf-8")
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.socket.sendall(bytes(header) + masked)

    def recv_text(self) -> str:
        while True:
            first = self.socket.recv(2)
            if len(first) < 2:
                raise RuntimeError("WebSocket closed.")
            opcode = first[0] & 0x0F
            masked = bool(first[1] & 0x80)
            length = first[1] & 0x7F
            if length == 126:
                length = struct.unpack("!H", self.socket.recv(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self.socket.recv(8))[0]
            mask = self.socket.recv(4) if masked else b""
            payload = b""
            while len(payload) < length:
                payload += self.socket.recv(length - len(payload))
            if masked:
                payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
            if opcode == 0x8:
                raise RuntimeError("WebSocket close frame received.")
            if opcode == 0x9:
                continue
            if opcode in (0x1, 0x0):
                return payload.decode("utf-8", errors="replace")

    def close(self) -> None:
        self.socket.close()


class Cdp:
    def __init__(self, ws: DevToolsSocket) -> None:
        self.ws = ws
        self.next_id = 0

    def send(self, method: str, params: dict[str, object] | None = None) -> object:
        self.next_id += 1
        message_id = self.next_id
        self.ws.send_text(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.ws.recv_text())
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(f"CDP {method} failed: {message['error']}")
                return message.get("result", {})

    def eval(self, expression: str, await_promise: bool = False) -> object:
        result = self.send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": await_promise,
                "returnByValue": True,
            },
        )
        remote = result.get("result", {}) if isinstance(result, dict) else {}
        if isinstance(remote, dict) and "value" in remote:
            return remote["value"]
        return remote


def wait_for_devtools(port: int) -> list[dict[str, object]]:
    for _ in range(40):
        try:
            tabs = json_get(f"http://127.0.0.1:{port}/json/list")
            if isinstance(tabs, list) and tabs:
                page_tabs = [
                    tab
                    for tab in tabs
                    if tab.get("type") == "page" and not str(tab.get("url", "")).startswith("chrome-extension:")
                ]
                if page_tabs:
                    return page_tabs
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("Chrome DevTools endpoint did not start.")


def wait_for_text(cdp: Cdp, text: str, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = cdp.eval("document.body ? document.body.innerText : ''")
        if text in str(body):
            return
        time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for visible text: {text}")


def wait_for_ready(cdp: Cdp, timeout: float = 12.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        ready = cdp.eval("document.readyState")
        has_root = cdp.eval("Boolean(document.querySelector('#root'))")
        body_length = cdp.eval("document.body ? document.body.innerText.length : 0")
        if ready == "complete" and has_root and int(body_length or 0) > 20:
            return
        time.sleep(0.25)
    location = cdp.eval("location.href")
    ready = cdp.eval("document.readyState")
    text = cdp.eval("document.body ? document.body.innerText.slice(0, 500) : ''")
    raise RuntimeError(f"Timed out waiting for React route to render. location={location!r} ready={ready!r} text={text!r}")


def assert_current_control_shell(cdp: Cdp) -> None:
    result = cdp.eval(
        """
(() => ({
  hasFluxioShell: Boolean(document.querySelector('.fluxio-shell')),
  hasErrorScreen: Boolean(document.querySelector('.fluxio-error-screen')),
  errorText: document.querySelector('.fluxio-error-screen')?.innerText?.slice(0, 500) || '',
  hasFluxosShell: Boolean(document.querySelector('.fluxos-shell')),
  hasPublicPage: Boolean(document.querySelector('.grand-public-page')),
  url: location.href,
}))()
"""
    )
    if isinstance(result, dict) and result.get("hasErrorScreen"):
        raise RuntimeError(f"Fluxio render error screen appeared during control proof: {result}")
    if not isinstance(result, dict) or not result.get("hasFluxioShell"):
        raise RuntimeError(f"Current .fluxio-shell did not render: {result}")
    if result.get("hasFluxosShell") or result.get("hasPublicPage"):
        raise RuntimeError(f"Wrong skin rendered for control proof: {result}")


def wait_for_control_shell(cdp: Cdp, timeout: float = 12.0) -> None:
    deadline = time.time() + timeout
    last_result: object = None
    while time.time() < deadline:
        try:
            assert_current_control_shell(cdp)
            return
        except RuntimeError as error:
            last_result = str(error)
            if "render error screen" in str(error):
                raise
        time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for current .fluxio-shell: {last_result}")


def assert_no_horizontal_overflow(cdp: Cdp) -> dict[str, object]:
    result = cdp.eval(
        """
(() => {
  const viewportWidth = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
  const documentScrollWidth = document.documentElement.scrollWidth || 0;
  const bodyScrollWidth = document.body ? document.body.scrollWidth || 0 : 0;
  const overflowPx = Math.max(documentScrollWidth, bodyScrollWidth) - viewportWidth;
  const offenders = Array.from(document.querySelectorAll("body *"))
    .map(element => {
      const rect = element.getBoundingClientRect();
      return {
        tag: element.tagName,
        className: typeof element.className === "string" ? element.className : "",
        text: (element.textContent || "").trim().replace(/\\s+/g, " ").slice(0, 120),
        left: Math.round(rect.left),
        right: Math.round(rect.right),
        width: Math.round(rect.width),
      };
    })
    .filter(item => item.right > viewportWidth + 4)
    .slice(0, 12);
  return { viewportWidth, documentScrollWidth, bodyScrollWidth, overflowPx, offenders };
})()
"""
    )
    if not isinstance(result, dict):
        raise RuntimeError(f"Could not inspect layout overflow: {result}")
    if int(result.get("overflowPx") or 0) > 4 or result.get("offenders"):
        raise RuntimeError(f"Horizontal overflow detected: {result}")
    return result


def click_button(cdp: Cdp, label: str) -> None:
    expression = f"""
(() => {{
  const normalize = value => (value || '').trim().replace(/\\s+/g, ' ');
  const railButtons = Array.from(document.querySelectorAll('.global-rail-button'));
  const railTarget = railButtons.find(button => normalize(button.innerText) === {json.dumps(label)});
  if (railTarget) {{
    railTarget.scrollIntoView({{ block: 'center', inline: 'center' }});
    railTarget.click();
    return {{ clicked: true, text: railTarget.innerText.trim(), selector: '.global-rail-button' }};
  }}
  const buttons = Array.from(document.querySelectorAll('button'));
  const target = buttons.find(button => normalize(button.innerText).includes({json.dumps(label)}));
  if (!target) return {{ clicked: false, reason: 'button not found' }};
  target.scrollIntoView({{ block: 'center', inline: 'center' }});
  target.click();
  return {{ clicked: true, text: target.innerText.trim(), selector: 'button' }};
}})()
"""
    result = cdp.eval(expression)
    if not isinstance(result, dict) or not result.get("clicked"):
        raise RuntimeError(f"Could not click button {label}: {result}")


def capture(cdp: Cdp, name: str) -> str:
    path = OUT_DIR / f"interaction-{name}.png"
    result = cdp.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, str):
        raise RuntimeError(f"Screenshot capture failed for {name}.")
    path.write_bytes(base64.b64decode(data))
    return str(path)


def main() -> int:
    if not CHROME.exists():
        raise RuntimeError(f"Chrome executable not found: {CHROME}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    port = free_port()
    profile = tempfile.TemporaryDirectory(prefix="syntelos-cdp-")
    process = subprocess.Popen(
        [
            str(CHROME),
            "--headless",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-sandbox",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile.name}",
            f"--window-size={VIEWPORT_WIDTH},{VIEWPORT_HEIGHT}",
            "about:blank",
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    ws: DevToolsSocket | None = None
    try:
        tabs = wait_for_devtools(port)
        ws_url = str(tabs[0]["webSocketDebuggerUrl"])
        ws = DevToolsSocket(ws_url)
        cdp = Cdp(ws)
        cdp.send("Page.enable")
        cdp.send("Runtime.enable")
        cdp.send("Page.navigate", {"url": BASE_URL})
        time.sleep(1.5)
        wait_for_ready(cdp)
        wait_for_control_shell(cdp)
        initial_layout = assert_no_horizontal_overflow(cdp)

        steps = []
        for label, expected in [
            ("Builder", ["CONVERSATION COMMAND BOARD", "Launch mission"]),
            (
                "Skills",
                [
                    "Skills",
                    "Skill recovery",
                    "RECOMMENDED SKILLS",
                    "RUNTIME LANE",
                    "Recovery actions and route separation",
                ],
            ),
            ("Runtime", ["Runtime", "OpenClaw", "Work engines"]),
            ("Settings", ["Settings", "Workspace"]),
            ("Agent", ["Agent", "Syntelos"]),
        ]:
            click_button(cdp, label)
            assert_current_control_shell(cdp)
            layout = assert_no_horizontal_overflow(cdp)
            for fragment in expected:
                wait_for_text(cdp, fragment)
            visible = str(cdp.eval("document.body.innerText")).replace("\r\n", "\n")
            screenshot = capture(cdp, label.lower().replace(" ", "-"))
            steps.append(
                {
                    "click": label,
                    "expected": expected,
                    "visibleTextMatched": all(fragment in visible for fragment in expected),
                    "layout": layout,
                    "screenshotPath": screenshot,
                    "excerpt": visible[:900],
                    "passed": True,
                }
            )

        report = {
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "browser": str(CHROME),
            "type": "live CDP click interaction",
            "viewport": {"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            "initialLayout": initial_layout,
            "passed": all(step["passed"] for step in steps),
            "steps": steps,
        }
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
