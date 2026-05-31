from __future__ import annotations

import argparse
import json
import ssl
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTROL_URL = "https://sysnology.tail602108.ts.net:47880/control"
DEFAULT_HEALTH_URL = "https://sysnology.tail602108.ts.net:47880/health"
LOOPBACK_CONTROL_URL = "https://127.0.0.1:47880/control"
LOOPBACK_HEALTH_URL = "https://127.0.0.1:47880/health"


def _fetch_json(url: str, *, timeout: int) -> tuple[int, dict]:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    request = Request(url, headers={"User-Agent": "fluxio-private-nas-web-verifier/1.0"})
    with urlopen(request, timeout=timeout, context=context) as response:
        status = int(getattr(response, "status", 0) or 0)
        raw = response.read(1_000_000).decode("utf-8", "replace")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {"rawPreview": raw[:500]}
    return status, payload if isinstance(payload, dict) else {"payload": payload}


def _fetch_text_head(url: str, *, timeout: int) -> tuple[int, str]:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    request = Request(url, headers={"User-Agent": "fluxio-private-nas-web-verifier/1.0"})
    with urlopen(request, timeout=timeout, context=context) as response:
        status = int(getattr(response, "status", 0) or 0)
        raw = response.read(500_000).decode("utf-8", "replace")
    return status, raw[:2000]


def verify_private_nas_web_deployment(
    root: Path,
    *,
    control_url: str = DEFAULT_CONTROL_URL,
    health_url: str = DEFAULT_HEALTH_URL,
    output: Path | None = None,
    timeout: int = 12,
    write: bool = False,
) -> dict:
    root = root.resolve()
    checked_at = datetime.now(timezone.utc).isoformat()
    checks: list[dict] = []
    public_control_url = control_url
    public_health_url = health_url
    observed_control_url = control_url
    observed_health_url = health_url
    fallback_used = False
    health_status = 0
    health_payload: dict = {}
    control_status = 0
    control_head = ""
    error = ""
    try:
        health_status, health_payload = _fetch_json(health_url, timeout=timeout)
        control_status, control_head = _fetch_text_head(control_url, timeout=timeout)
    except (OSError, TimeoutError, URLError) as exc:
        error = f"{type(exc).__name__}: {exc}"
        if "sysnology.tail602108.ts.net" in health_url or "sysnology.tail602108.ts.net" in control_url:
            try:
                observed_health_url = LOOPBACK_HEALTH_URL
                observed_control_url = LOOPBACK_CONTROL_URL
                health_status, health_payload = _fetch_json(observed_health_url, timeout=timeout)
                control_status, control_head = _fetch_text_head(observed_control_url, timeout=timeout)
                fallback_used = True
                error = ""
            except (OSError, TimeoutError, URLError) as fallback_exc:
                error = f"{error}; loopback fallback failed: {type(fallback_exc).__name__}: {fallback_exc}"

    checks.append(
        {
            "checkId": "health_endpoint_reachable",
            "passed": health_status == 200 and bool(health_payload.get("ok")),
            "details": f"GET {observed_health_url} returned {health_status}.",
        }
    )
    checks.append(
        {
            "checkId": "control_route_reachable",
            "passed": control_status == 200 and ("Fluxio" in control_head or "<html" in control_head.lower()),
            "details": f"GET {observed_control_url} returned {control_status}.",
        }
    )
    checks.append(
        {
            "checkId": "login_boundary_declared",
            "passed": bool(health_payload.get("loginRequired")),
            "details": "Private NAS web receipt confirms the app is reachable but still protected by login.",
        }
    )
    missing = [item["checkId"] for item in checks if not item["passed"]]
    receipt = {
        "schema": "fluxio.private_nas_web_deployment.v1",
        "checkedAt": checked_at,
        "root": str(root),
        "scope": "private_tailscale_nas",
        "controlUrl": observed_control_url,
        "healthUrl": observed_health_url,
        "publicControlUrl": public_control_url,
        "publicHealthUrl": public_health_url,
        "fallbackUsed": fallback_used,
        "ok": not missing,
        "healthStatus": health_status,
        "controlStatus": control_status,
        "backend": str(health_payload.get("backend") or ""),
        "loginRequired": bool(health_payload.get("loginRequired")),
        "checks": checks,
        "missing": missing,
        "error": error,
        "nextAction": (
            "Private NAS web deployment is reachable; attach this receipt to release proof while public deployment remains separate."
            if not missing
            else "Restore private NAS web reachability, then rerun this verifier."
        ),
    }
    if write:
        target = output or root / ".agent_control" / "deployment_evidence" / "private-nas-web.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        receipt["evidencePath"] = str(target)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the private Tailscale NAS web deployment.")
    parser.add_argument("--root", default=str(ROOT), help="Workspace root.")
    parser.add_argument("--control-url", default=DEFAULT_CONTROL_URL)
    parser.add_argument("--health-url", default=DEFAULT_HEALTH_URL)
    parser.add_argument("--output", default="")
    parser.add_argument("--timeout", type=int, default=12)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    receipt = verify_private_nas_web_deployment(
        Path(args.root),
        control_url=args.control_url,
        health_url=args.health_url,
        output=Path(args.output) if args.output else None,
        timeout=args.timeout,
        write=args.write,
    )
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
