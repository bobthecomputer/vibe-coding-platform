from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    manifest_path = WEB_ROOT / "public" / "manifest.webmanifest"
    service_worker_path = WEB_ROOT / "public" / "service-worker.js"
    offline_path = WEB_ROOT / "public" / "offline.html"
    index_path = WEB_ROOT / "index.html"
    main_path = WEB_ROOT / "src" / "main.tsx"
    pwa_path = WEB_ROOT / "src" / "pwa.ts"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    service_worker = service_worker_path.read_text(encoding="utf-8")
    index = index_path.read_text(encoding="utf-8")
    main = main_path.read_text(encoding="utf-8")
    pwa = pwa_path.read_text(encoding="utf-8")

    require(manifest.get("display") == "standalone", "manifest must use standalone display")
    require(manifest.get("start_url") == "/control", "manifest must start at /control")
    require(any(item.get("purpose") == "maskable" for item in manifest.get("icons", [])), "manifest must include a maskable icon")
    require('rel="manifest"' in index or "rel=\"manifest\"" in index, "index must link manifest")
    require('name="theme-color"' in index, "index must set theme color")
    require("navigator.serviceWorker.register" in pwa, "PWA registration must call serviceWorker.register")
    require("registration.update()" in pwa, "PWA registration must proactively check for shell updates")
    require("controllerchange" in pwa, "PWA registration must reload after a controller update")
    require("SKIP_WAITING" in pwa, "PWA registration must activate waiting service workers")
    require("registerFluxioPwa" in main, "main entry must register Fluxio PWA shell")
    require("/offline.html" in service_worker, "service worker must cache offline fallback")
    require('"/control",' not in service_worker, "service worker must not precache the live /control route")
    require("fetch(request)" in service_worker, "service worker must refresh static assets from the network before cache fallback")
    require('event.data.type === "SKIP_WAITING"' in service_worker, "service worker must accept immediate activation messages")
    require('url.pathname.startsWith("/api")' in service_worker, "service worker must bypass API requests")
    require('url.pathname === "/health"' in service_worker, "service worker must bypass health requests")
    require("Fluxio is waiting for the NAS connection" in offline_path.read_text(encoding="utf-8"), "offline page must explain NAS reconnection")

    dist = WEB_ROOT / "dist"
    if dist.exists():
        require((dist / "manifest.webmanifest").exists(), "built dist must include manifest.webmanifest")
        require((dist / "service-worker.js").exists(), "built dist must include service-worker.js")
        require((dist / "offline.html").exists(), "built dist must include offline.html")

    print(json.dumps({"ok": True, "schema": "fluxio.pwa_shell_verification.v1"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
