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
    Cdp,
    DevToolsSocket,
    free_port,
    wait_for_devtools,
    wait_for_ready,
    wait_for_text,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = Path(os.environ.get("FLUXIO_PROOF_OUT_DIR", str(ROOT / "artifacts" / "pr112-image-vision-ui-self-repair")))
BASE_URL = os.environ.get(
    "FLUXIO_CONTROL_URL",
    "http://127.0.0.1:1420/control?preview-control=1&mode=builder&surface=images&sidebar=collapsed&imageRoute=openai-gpt-image-2&diagnostics=1",
)
BACKEND_URL = os.environ.get("VITE_FLUXIO_BACKEND_URL") or os.environ.get("FLUXIO_BACKEND_URL") or "http://127.0.0.1:47880"
VIEWPORT_WIDTH = int(os.environ.get("FLUXIO_VIEWPORT_WIDTH", "1440"))
VIEWPORT_HEIGHT = int(os.environ.get("FLUXIO_VIEWPORT_HEIGHT", "980"))
PROMPT = os.environ.get(
    "FLUXIO_IMAGE_PROMPT",
    (
        "Fresh app-button generation proof for Fluxio: matte black modular camera on basalt stone, "
        "amber rim light, precise glass reflections, premium dark editorial product photo, no text, no logo."
    ),
)


def capture(cdp: Cdp, name: str) -> str:
    path = OUT_DIR / f"app-button-generate-{name}.png"
    result = cdp.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, str):
        raise RuntimeError(f"Screenshot capture failed for {name}.")
    path.write_bytes(base64.b64decode(data))
    return str(path)


def read_state(cdp: Cdp) -> dict[str, object]:
    result = cdp.eval(
        """
(() => {
  const buttonItems = Array.from(document.querySelectorAll('button'))
    .filter(button => button.innerText.includes('Generate image') || button.innerText.includes('Generating'))
    .map(button => ({
      text: button.innerText.trim().replace(/\\s+/g, ' '),
      disabled: Boolean(button.disabled),
      className: button.className || '',
    }));
  const runResult = document.querySelector('.image-studio-run-result');
  const toastText = Array.from(document.querySelectorAll('.toast-host, [role="alert"], [aria-live="polite"]'))
    .map(node => (node.innerText || node.textContent || '').trim())
    .filter(Boolean)
    .join('\\n')
    .slice(0, 2000);
  const canvasLayerStyles = Array.from(document.querySelectorAll('.image-studio-canvas-layer'))
    .map(layer => layer.getAttribute('style') || '');
  const generatedLinks = Array.from(document.querySelectorAll('a, code, span, p, strong'))
    .map(node => (node.innerText || node.textContent || '').trim())
    .filter(text => text.includes('/api/artifact') || text.includes('codex_image_artifacts') || text.includes('gpt-image-2'))
    .slice(0, 20);
  return {
    url: location.href,
    title: document.title,
    bodyText: document.body ? document.body.innerText.slice(0, 6000) : '',
    routeSummary: document.querySelector('.image-studio-route-summary')?.innerText.trim().replace(/\\s+/g, ' ') || '',
    runResultText: runResult?.innerText.trim().replace(/\\s+/g, ' ') || '',
    runResultIsError: Boolean(runResult?.classList.contains('is-error')),
    runResultIsBlocked: Boolean(runResult?.classList.contains('is-blocked')),
    toastText,
    buttonItems,
    promptText: document.querySelector('#image-studio-prompt')?.value || '',
    quickPromptText: document.querySelector('#image-studio-prompt-quick')?.value || '',
    canvasLayerCount: canvasLayerStyles.length,
    canvasLayerStyles,
    generatedLinks,
    artifactBackgrounds: canvasLayerStyles.filter(style => style.includes('/api/artifact')),
  };
})()
""",
    )
    return result if isinstance(result, dict) else {"raw": result}


def read_local_login() -> tuple[str, str]:
    username = os.environ.get("SYNTELOS_ACCOUNT_USER") or os.environ.get("GRAND_AGENT_ADMIN_USER") or ""
    password = os.environ.get("SYNTELOS_ACCOUNT_PASSWORD") or os.environ.get("GRAND_AGENT_ADMIN_PASSWORD") or ""
    if username and password:
        return username, password
    password_note = ROOT / ".agent_control" / "grand_agent_admin_password.txt"
    if not password_note.exists():
        raise RuntimeError(f"Local account password note was not found: {password_note}")
    for line in password_note.read_text(encoding="utf-8").splitlines():
        if line.startswith("Username:"):
            username = line.split(":", 1)[1].strip()
        elif line.startswith("Password:"):
            password = line.split(":", 1)[1].strip()
    if not username or not password:
        raise RuntimeError(f"Local account password note is incomplete: {password_note}")
    return username, password


def login_to_backend(cdp: Cdp) -> dict[str, object]:
    username, password = read_local_login()
    result = cdp.eval(
        f"""
(async () => {{
  const response = await fetch({json.dumps(BACKEND_URL.rstrip('/') + '/api/auth/login')}, {{
    method: 'POST',
    credentials: 'include',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ username: {json.dumps(username)}, password: {json.dumps(password)} }}),
  }});
  const payload = await response.json().catch(() => ({{}}));
  return {{
    ok: response.ok && payload?.ok !== false,
    status: response.status,
    authenticated: Boolean(payload?.data?.authenticated),
    user: payload?.data?.user || null,
    error: payload?.error || '',
  }};
}})()
""",
        await_promise=True,
    )
    if not isinstance(result, dict) or not result.get("ok"):
        raise RuntimeError(f"Could not authenticate browser proof session: {result}")
    return result


def set_prompt(cdp: Cdp) -> None:
    result = cdp.eval(
        f"""
(() => {{
  const prompt = {json.dumps(PROMPT)};
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
  const fields = ['#image-studio-prompt', '#image-studio-prompt-quick']
    .map(selector => document.querySelector(selector))
    .filter(Boolean);
  for (const field of fields) {{
    field.focus();
    if (setter) {{
      setter.call(field, prompt);
    }} else {{
      field.value = prompt;
    }}
    field.dispatchEvent(new Event('input', {{ bubbles: true }}));
    field.dispatchEvent(new Event('change', {{ bubbles: true }}));
  }}
  return {{
    updated: fields.length,
    prompt,
    values: fields.map(field => field.value),
  }};
}})()
""",
    )
    if not isinstance(result, dict) or int(result.get("updated") or 0) == 0:
        raise RuntimeError(f"Could not set prompt in Image Studio: {result}")
    deadline = time.time() + 10
    last_state: dict[str, object] = {}
    while time.time() < deadline:
        last_state = read_state(cdp)
        if PROMPT in str(last_state.get("promptText") or "") or PROMPT in str(last_state.get("quickPromptText") or ""):
            return
        time.sleep(0.25)
    raise RuntimeError(f"Prompt did not update in React state: {last_state}")


def wait_for_image_studio(cdp: Cdp, timeout: float = 45.0) -> None:
    wait_for_ready(cdp, timeout=timeout)
    wait_for_text(cdp, "Image generation playground", timeout=timeout)
    deadline = time.time() + timeout
    last_state: object = None
    while time.time() < deadline:
        last_state = cdp.eval(
            """
(() => ({
  prompt: Boolean(document.querySelector('#image-studio-prompt')),
  quickPrompt: Boolean(document.querySelector('#image-studio-prompt-quick')),
  shell: Boolean(document.querySelector('.fluxio-shell')),
  body: document.body ? document.body.innerText.slice(0, 1000) : '',
}))()
"""
        )
        if isinstance(last_state, dict) and last_state.get("prompt") and last_state.get("quickPrompt"):
            return
        time.sleep(0.5)
    raise RuntimeError(f"Image Studio prompt fields did not render: {last_state}")


def wait_for_generate_enabled(cdp: Cdp, timeout: float = 90.0) -> dict[str, object]:
    deadline = time.time() + timeout
    last_state: dict[str, object] = {}
    while time.time() < deadline:
        state = read_state(cdp)
        last_state = state
        buttons = state.get("buttonItems")
        if isinstance(buttons, list) and any(isinstance(item, dict) and not item.get("disabled") for item in buttons):
            return state
        time.sleep(0.5)
    raise RuntimeError(f"Generate image button did not become enabled: {last_state}")


def click_generate(cdp: Cdp) -> dict[str, object]:
    result = cdp.eval(
        """
(() => {
  const buttons = Array.from(document.querySelectorAll('button'))
    .filter(button => button.innerText.includes('Generate image') && !button.disabled);
  const button = buttons[0];
  if (!button) {
    return {
      clicked: false,
      reason: 'enabled generate button not found',
      buttons: Array.from(document.querySelectorAll('button'))
        .filter(item => item.innerText.includes('Generate image') || item.innerText.includes('Generating'))
        .map(item => ({ text: item.innerText.trim(), disabled: Boolean(item.disabled), title: item.title || '' })),
    };
  }
  button.scrollIntoView({ block: 'center', inline: 'center' });
  button.click();
  return { clicked: true, text: button.innerText.trim().replace(/\\s+/g, ' '), className: button.className || '' };
})()
""",
    )
    if not isinstance(result, dict) or not result.get("clicked"):
        raise RuntimeError(f"Could not click Generate image: {result}")
    return result


def wait_for_generation_result(cdp: Cdp, timeout: float = 930.0) -> dict[str, object]:
    deadline = time.time() + timeout
    last_state: dict[str, object] = {}
    while time.time() < deadline:
        state = read_state(cdp)
        last_state = state
        run_text = str(state.get("runResultText") or "")
        body_text = str(state.get("bodyText") or "")
        artifact_backgrounds = state.get("artifactBackgrounds")
        has_artifact = isinstance(artifact_backgrounds, list) and len(artifact_backgrounds) > 0
        if "Generated PNG artifact was written" in run_text and has_artifact:
            return state
        if state.get("runResultIsError") or state.get("runResultIsBlocked"):
            raise RuntimeError(f"Image generation failed in app: {state}")
        if "Provider image artifact recorded" in body_text and has_artifact:
            return state
        time.sleep(2.0)
    raise RuntimeError(f"Timed out waiting for app-generated image artifact: {last_state}")


def main() -> int:
    if not CHROME.exists():
        raise RuntimeError(f"Chrome executable not found: {CHROME}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    port = free_port()
    profile = tempfile.TemporaryDirectory(prefix="fluxio-image-click-")
    process = subprocess.Popen(
        [
            str(CHROME),
            "--headless=new",
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
    report: dict[str, object] = {
        "schemaVersion": "image-studio-app-button-generate-proof.v1",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "url": BASE_URL,
        "backendUrl": BACKEND_URL,
        "prompt": PROMPT,
        "proofKind": "browser_click_to_runtime_image_generation",
    }
    try:
        tabs = wait_for_devtools(port)
        ws = DevToolsSocket(str(tabs[0]["webSocketDebuggerUrl"]))
        cdp = Cdp(ws)
        cdp.send("Page.enable")
        cdp.send("Runtime.enable")
        cdp.send(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": (
                    "window.__FLUXIO_BACKEND_URL__ = "
                    f"{json.dumps(BACKEND_URL.rstrip('/'))};"
                )
            },
        )
        cdp.send("Page.navigate", {"url": BASE_URL})
        wait_for_image_studio(cdp, timeout=60)
        cdp.eval(
            """
(() => {
  localStorage.removeItem('fluxio.image_playground.project.v1');
  localStorage.removeItem('fluxio.image_studio.session.v1');
  localStorage.setItem('fluxio.preview.mode', 'live');
  localStorage.setItem('fluxio.ui.surface', 'images');
  localStorage.setItem('fluxio.ui.mode', 'builder');
  return true;
})()
"""
        )
        auth_state = login_to_backend(cdp)
        cdp.send("Page.reload", {"ignoreCache": True})
        wait_for_image_studio(cdp, timeout=60)
        set_prompt(cdp)
        ready_state = wait_for_generate_enabled(cdp)
        before_path = capture(cdp, "before")
        click_result = click_generate(cdp)
        completed_state = wait_for_generation_result(cdp)
        after_path = capture(cdp, "after")
        report.update(
            {
                "status": "passed",
                "beforeScreenshot": before_path,
                "afterScreenshot": after_path,
                "authState": auth_state,
                "readyState": ready_state,
                "clickResult": click_result,
                "completedState": completed_state,
                "route": {
                    "provider": "openai-codex",
                    "providerId": "codex_subscription_gpt_image2",
                    "model": "gpt-image-2",
                    "command": "image_playground_operation_command -> openclaw infer image generate --model openai/gpt-image-2",
                },
            }
        )
        print(json.dumps(report, indent=2))
        return 0
    except Exception as error:
        try:
            failure_path = capture(cdp, "failure") if ws else ""
        except Exception:
            failure_path = ""
        report.update(
            {
                "status": "failed",
                "error": str(error),
                "failureScreenshot": failure_path,
            }
        )
        print(json.dumps(report, indent=2))
        return 1
    finally:
        (OUT_DIR / "app-button-generate-proof.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
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
