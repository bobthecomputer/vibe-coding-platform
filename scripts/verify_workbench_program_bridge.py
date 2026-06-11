from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from control_route_interaction_smoke import Cdp, DevToolsSocket, free_port, wait_for_devtools
from control_route_visual_smoke import find_browser_or_playwright_managed
from verify_windows_control_ui import process_group_flags, stop_process_tree, wait_for_http


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "tmp-ui-checks" / "workbench-program-bridge"
PASSWORD_FILE = ROOT / ".agent_control" / "grand_agent_admin_password.txt"


class ClickProbeState:
    def __init__(self) -> None:
        self.clicks = 0
        self.lock = threading.Lock()

    def increment(self) -> int:
        with self.lock:
            self.clicks += 1
            return self.clicks

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            return {"ok": True, "clicks": self.clicks}


class QuietThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request: object, client_address: object) -> None:
        return


def npm_command() -> str:
    return "npm.cmd" if sys.platform.startswith("win") else "npm"


def python_command() -> str:
    return sys.executable


def read_local_password(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    username = re.search(r"^Username:\s*(.+?)\s*$", text, re.MULTILINE)
    password = re.search(r"^Password:\s*(.+?)\s*$", text, re.MULTILINE)
    if not username or not password:
        raise RuntimeError(f"Could not read local account credentials from {path}")
    return username.group(1).strip(), password.group(1).strip()


def json_get(url: str, timeout: float = 8.0) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def make_click_probe_handler(state: ClickProbeState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _send_json(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self) -> None:
            html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Fluxio Click Probe</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, Arial, sans-serif; }
    body { margin: 0; background: #0b0f14; color: #f8fafc; }
    main { padding: 32px; }
    h1 { font-size: 28px; margin: 0 0 10px; }
    p { color: #b8c4d4; max-width: 640px; }
    button {
      margin-top: 28px;
      min-width: 210px;
      min-height: 54px;
      border: 1px solid #79ffe1;
      background: #0f2b29;
      color: #ffffff;
      font-size: 17px;
      font-weight: 700;
      cursor: pointer;
    }
    #count { display: inline-block; min-width: 3ch; font-variant-numeric: tabular-nums; }
    .receipt { margin-top: 22px; color: #79ffe1; font-weight: 700; }
  </style>
</head>
<body>
  <main>
    <h1>Fluxio Click Probe</h1>
    <p>This page is a real local program served outside the app. Workbench must render it and pass mouse clicks into it.</p>
    <button id="probe-button" type="button">Send bridge click</button>
    <div class="receipt">Clicks received by program: <span id="count">0</span></div>
  </main>
  <script>
    const count = document.getElementById('count');
    document.getElementById('probe-button').addEventListener('click', async () => {
      const response = await fetch('/click', { method: 'POST' });
      const data = await response.json();
      count.textContent = String(data.clicks);
    });
  </script>
</body>
</html>"""
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = urllib.parse.urlsplit(self.path).path
            if path == "/state":
                self._send_json(200, state.snapshot())
                return
            self._send_html()

        def do_POST(self) -> None:  # noqa: N802
            path = urllib.parse.urlsplit(self.path).path
            if path == "/click":
                self._send_json(200, {"ok": True, "clicks": state.increment()})
                return
            self._send_json(404, {"ok": False, "error": "unknown route"})

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def start_click_probe(port: int) -> tuple[QuietThreadingHTTPServer, ClickProbeState]:
    state = ClickProbeState()
    server = QuietThreadingHTTPServer(("127.0.0.1", port), make_click_probe_handler(state))
    thread = threading.Thread(target=server.serve_forever, name="fluxio-click-probe", daemon=True)
    thread.start()
    return server, state


def start_backend(port: int) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env["FLUXIO_WATCHDOG_AUTOSTART"] = "0"
    return subprocess.Popen(
        [
            python_command(),
            "scripts/run_web_backend.py",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--allow-port-reuse",
        ],
        cwd=ROOT,
        env=env,
        creationflags=process_group_flags(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def start_vite(port: int, backend_url: str) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env["VITE_FLUXIO_BACKEND_URL"] = backend_url
    return subprocess.Popen(
        [
            npm_command(),
            "run",
            "frontend:dev",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--strictPort",
        ],
        cwd=ROOT,
        env=env,
        creationflags=process_group_flags(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def capture(cdp: Cdp, path: Path) -> str:
    result = cdp.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, str):
        raise RuntimeError(f"Screenshot capture failed for {path.name}.")
    path.write_bytes(base64.b64decode(data))
    return str(path)


def eval_json(cdp: Cdp, expression: str, timeout: float = 15.0) -> object:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = cdp.eval(expression)
        if last:
            return last
        time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for expression: {expression}; last={last!r}")


def wait_for_body_text(cdp: Cdp, fragment: str, timeout: float = 20.0) -> str:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        text = str(cdp.eval("document.body ? document.body.innerText : ''") or "")
        last = text
        if fragment.casefold() in text.casefold():
            return text
        time.sleep(0.25)
    state = cdp.eval(
        """(() => ({
  location: location.href,
  readyState: document.readyState,
  title: document.title,
  bodyHtmlLength: document.body ? document.body.innerHTML.length : 0,
  scriptCount: document.scripts ? document.scripts.length : 0
}))()"""
    )
    raise RuntimeError(f"Timed out waiting for {fragment!r}; state={state!r}; visible excerpt={last[:700]!r}")


def wait_for_shell_document(cdp: Cdp, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = cdp.eval(
            """(() => ({
  readyState: document.readyState,
  rootExists: Boolean(document.querySelector('#root')),
  scriptCount: document.scripts ? document.scripts.length : 0
}))()"""
        )
        if (
            isinstance(state, dict)
            and state.get("readyState") == "complete"
            and state.get("rootExists")
            and int(state.get("scriptCount") or 0) > 0
        ):
            return
        time.sleep(0.25)
    raise RuntimeError("Timed out waiting for the app shell document.")


def click_at(cdp: Cdp, x: float, y: float) -> None:
    params = {"x": x, "y": y, "button": "left", "clickCount": 1}
    cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", **params})
    cdp.send("Input.dispatchMouseEvent", {"type": "mousePressed", **params})
    cdp.send("Input.dispatchMouseEvent", {"type": "mouseReleased", **params})


def click_button_by_text(cdp: Cdp, label: str) -> None:
    expression = f"""
(() => {{
  const buttons = Array.from(document.querySelectorAll('button'));
  const button = buttons.find(item => item.innerText.trim().includes({json.dumps(label)}));
  if (!button) return false;
  button.scrollIntoView({{ block: 'center', inline: 'center' }});
  button.click();
  return true;
}})()
"""
    if not cdp.eval(expression):
        raise RuntimeError(f"Button not found: {label}")


def click_selector(cdp: Cdp, selector: str) -> None:
    expression = f"""
(() => {{
  const target = document.querySelector({json.dumps(selector)});
  if (!target) return {{ clicked: false, reason: 'selector not found' }};
  target.scrollIntoView({{ block: 'center', inline: 'center' }});
  target.click();
  return {{ clicked: true, text: target.innerText ? target.innerText.trim() : '' }};
}})()
"""
    result = cdp.eval(expression)
    if not isinstance(result, dict) or not result.get("clicked"):
        raise RuntimeError(f"Could not click selector {selector}: {result}")


def wait_for_selector(cdp: Cdp, selector: str, timeout: float = 30.0) -> dict[str, object]:
    expression = f"""
(() => {{
  const target = document.querySelector({json.dumps(selector)});
  if (!target) return null;
  const rect = target.getBoundingClientRect();
  return {{
    text: target.innerText ? target.innerText.trim() : '',
    disabled: Boolean(target.disabled),
    x: rect.x,
    y: rect.y,
    width: rect.width,
    height: rect.height
  }};
}})()
"""
    result = eval_json(cdp, expression, timeout=timeout)
    if not isinstance(result, dict):
        raise RuntimeError(f"Selector did not resolve to an element: {selector}")
    return result


def login_backend_from_page(cdp: Cdp, backend_url: str, username: str, password: str) -> None:
    expression = f"""
(async () => {{
  const response = await fetch({json.dumps(backend_url + '/api/auth/login')}, {{
    method: 'POST',
    credentials: 'include',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ username: {json.dumps(username)}, password: {json.dumps(password)} }})
  }});
  const data = await response.json().catch(() => ({{}}));
  return {{ ok: response.ok && data.ok !== false, status: response.status, error: data.error || '' }};
}})()
"""
    result = cdp.eval(expression, await_promise=True)
    if not isinstance(result, dict) or not result.get("ok"):
        raise RuntimeError(f"Backend login failed: {result}")


def wait_for_program_clicks(program_url: str, minimum: int, timeout: float = 8.0) -> int:
    deadline = time.time() + timeout
    last = 0
    while time.time() < deadline:
        state = json_get(f"{program_url}/state")
        last = int(state.get("clicks") or 0)
        if last >= minimum:
            return last
        time.sleep(0.2)
    raise RuntimeError(f"Local program did not receive click. clicks={last}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Workbench can render and click a real local program plus browse folders.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--browser", choices=["auto", "chrome", "chromium", "edge", "zen"], default="auto")
    parser.add_argument("--browser-path", default="")
    parser.add_argument("--keep-servers", action="store_true")
    args = parser.parse_args()

    run_dir = Path(args.out_dir) / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    browser_path = find_browser_or_playwright_managed(args.browser, args.browser_path)
    if not browser_path:
        raise RuntimeError("A local Chrome, Chromium, Edge, or Zen browser is required for CDP interaction proof.")

    username, password = read_local_password(PASSWORD_FILE)
    backend_port = free_port()
    vite_port = free_port()
    program_port = free_port()
    cdp_port = free_port()
    backend_url = f"http://127.0.0.1:{backend_port}"
    base_url = f"http://127.0.0.1:{vite_port}"
    program_url = f"http://127.0.0.1:{program_port}"
    backend = start_backend(backend_port)
    vite = start_vite(vite_port, backend_url)
    program_server, _program_state = start_click_probe(program_port)
    profile = tempfile.TemporaryDirectory(prefix="fluxio-workbench-bridge-")
    browser = subprocess.Popen(
        [
            browser_path,
            "--headless=new",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-sandbox",
            f"--remote-debugging-port={cdp_port}",
            f"--user-data-dir={profile.name}",
            "--window-size=1440,960",
            "about:blank",
        ],
        cwd=ROOT,
        creationflags=process_group_flags(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    ws: DevToolsSocket | None = None
    cdp: Cdp | None = None
    report: dict[str, object] = {
        "schema": "fluxio.workbench_program_bridge_verification.v1",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "outDir": str(run_dir),
        "baseUrl": base_url,
        "backendUrl": backend_url,
        "programUrl": program_url,
        "screenshots": {},
        "checks": [],
    }

    def record(check_id: str, passed: bool, detail: str) -> None:
        report["checks"].append({"checkId": check_id, "passed": passed, "detail": detail})

    try:
        wait_for_http(f"{backend_url}/api/health", timeout=45)
        wait_for_http(f"{program_url}/state", timeout=10)
        wait_for_http(f"{base_url}/control?preview-control=1", timeout=60)

        tabs = wait_for_devtools(cdp_port)
        ws = DevToolsSocket(str(tabs[0]["webSocketDebuggerUrl"]))
        ws.socket.settimeout(45)
        cdp = Cdp(ws)
        cdp.send("Page.enable")
        cdp.send("Runtime.enable")
        cdp.send(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1440, "height": 960, "deviceScaleFactor": 1, "mobile": False},
        )

        initial_url = f"{base_url}/control?mode=builder&surface=workbench"
        cdp.send("Page.navigate", {"url": initial_url})
        time.sleep(1.0)
        login_backend_from_page(cdp, backend_url, username, password)

        agent_url = (
            f"{base_url}/control?preview-control=1&mode=agent&surface=agent"
            f"&previewUrl={urllib.parse.quote(program_url + '/', safe='')}"
            f"&previewLabel={urllib.parse.quote('Local program click probe', safe='')}"
        )
        cdp.send("Page.navigate", {"url": agent_url})
        wait_for_selector(cdp, '[data-live-agent-action="preview"]', timeout=90.0)
        report["screenshots"]["agentPreviewButton"] = capture(cdp, run_dir / "agent-preview-button.png")
        click_selector(cdp, '[data-live-agent-action="preview"]')
        agent_iframe_rect = eval_json(
            cdp,
            """(() => {
  const frame = document.querySelector('[data-agent-preview-frame="true"]');
  if (!frame) return null;
  const rect = frame.getBoundingClientRect();
  return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
})()""",
        )
        if not isinstance(agent_iframe_rect, dict) or float(agent_iframe_rect.get("width") or 0) < 320:
            raise RuntimeError(f"Agent preview iframe was not visible: {agent_iframe_rect}")
        report["screenshots"]["agentPreviewWindow"] = capture(cdp, run_dir / "agent-preview-window.png")
        record("agent-preview-button-opens-local-program", True, f"Agent Preview opened a local iframe at {agent_iframe_rect}.")
        click_at(cdp, float(agent_iframe_rect["x"]) + 136, float(agent_iframe_rect["y"]) + 188)
        agent_clicks = wait_for_program_clicks(program_url, 1)
        report["screenshots"]["agentPreviewAfterClick"] = capture(cdp, run_dir / "agent-preview-after-click.png")
        record("agent-preview-mouse-click-reaches-local-program", True, f"The external click probe recorded {agent_clicks} click(s) from Agent preview.")

        workbench_url = (
            f"{base_url}/control?preview-control=1&mode=builder&surface=workbench"
            f"&previewUrl={urllib.parse.quote(program_url + '/', safe='')}"
            f"&previewLabel={urllib.parse.quote('Local program click probe', safe='')}"
        )
        cdp.send("Page.navigate", {"url": workbench_url})
        wait_for_body_text(cdp, "Local program click probe", timeout=75.0)
        iframe_rect = eval_json(
            cdp,
            """(() => {
  const frame = document.querySelector('[data-workbench-preview-frame="true"]');
  if (!frame) return null;
  const rect = frame.getBoundingClientRect();
  return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
})()""",
        )
        if not isinstance(iframe_rect, dict) or float(iframe_rect.get("width") or 0) < 320:
            raise RuntimeError(f"Workbench preview iframe was not visible: {iframe_rect}")
        report["screenshots"]["workbenchBeforeClick"] = capture(cdp, run_dir / "workbench-program-before-click.png")
        record("workbench-renders-local-program", True, f"Workbench rendered a local iframe at {iframe_rect}.")

        click_at(cdp, float(iframe_rect["x"]) + 136, float(iframe_rect["y"]) + 188)
        clicks = wait_for_program_clicks(program_url, int(agent_clicks) + 1)
        report["screenshots"]["workbenchAfterClick"] = capture(cdp, run_dir / "workbench-program-after-click.png")
        record("mouse-click-reaches-local-program", True, f"The external click probe recorded {clicks} click(s).")

        settings_url = f"{base_url}/control?mode=builder&surface=settings&settingsTab=workspace"
        cdp.send("Page.navigate", {"url": settings_url})
        wait_for_body_text(cdp, "Workspace")
        click_button_by_text(cdp, "Pick workspace folder")
        wait_for_body_text(cdp, "Current folder")
        entries = eval_json(
            cdp,
            "Array.from(document.querySelectorAll('.workspace-browser-entry')).map(item => item.innerText.trim())",
        )
        roots = eval_json(
            cdp,
            "Array.from(document.querySelectorAll('.workspace-browser-root-button')).map(item => item.innerText.trim())",
        )
        report["screenshots"]["folderBrowser"] = capture(cdp, run_dir / "folder-browser-open.png")
        record(
            "folder-browser-opens-real-backend",
            isinstance(roots, list) and len(roots) > 0,
            f"Folder browser rendered {len(roots) if isinstance(roots, list) else 0} roots and {len(entries) if isinstance(entries, list) else 0} entries.",
        )

        passed = all(bool(item["passed"]) for item in report["checks"])
        report["passed"] = passed
        report_path = run_dir / "workbench-program-bridge-check.json"
        report["reportPath"] = str(report_path)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0 if passed else 1
    except Exception as exc:
        report["passed"] = False
        report["error"] = str(exc)
        if cdp is not None:
            try:
                report["browserState"] = cdp.eval(
                    """(() => ({
  location: location.href,
  readyState: document.readyState,
  title: document.title,
  bodyText: document.body ? document.body.innerText.slice(0, 500) : '',
  bodyHtmlLength: document.body ? document.body.innerHTML.length : 0,
  rootExists: Boolean(document.querySelector('#root')),
  scriptCount: document.scripts ? document.scripts.length : 0
}))()"""
                )
                report["screenshots"]["failure"] = capture(cdp, run_dir / "failure-state.png")
            except Exception as debug_exc:
                report["browserStateError"] = str(debug_exc)
        report_path = run_dir / "workbench-program-bridge-check.json"
        report["reportPath"] = str(report_path)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1
    finally:
        if ws:
            ws.close()
        stop_process_tree(browser)
        profile.cleanup()
        program_server.shutdown()
        program_server.server_close()
        if not args.keep_servers:
            stop_process_tree(vite)
            stop_process_tree(backend)


if __name__ == "__main__":
    raise SystemExit(main())
