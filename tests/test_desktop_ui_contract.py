from __future__ import annotations

import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "t3code" / "apps" / "web" / "index.html"
MAIN_TSX = ROOT / "t3code" / "apps" / "web" / "src" / "main.tsx"
FLUXIO_APP = ROOT / "t3code" / "apps" / "web" / "src" / "fluxio" / "FluxioApp.tsx"
FLUXIO_BRIDGE = ROOT / "t3code" / "apps" / "web" / "src" / "fluxio" / "fluxioBridge.ts"
HELPERS_JS = ROOT / "desktop-ui" / "fluxioHelpers.js"
TAURI_CONF = ROOT / "src-tauri" / "tauri.conf.json"
PACKAGE_JSON = ROOT / "package.json"


class DesktopUiContractTests(unittest.TestCase):
    def test_index_html_mounts_t3_web_root_and_entrypoint(self) -> None:
        html = INDEX_HTML.read_text(encoding="utf-8")

        self.assertIn('id="root"', html)
        self.assertIn('src="/src/main.tsx"', html)
        self.assertIn("DM+Sans", html)

    def test_main_entry_mounts_fluxio_app_inside_t3_source_tree(self) -> None:
        main_tsx = MAIN_TSX.read_text(encoding="utf-8")
        fluxio_app = FLUXIO_APP.read_text(encoding="utf-8")

        self.assertIn("FluxioApp", main_tsx)
        self.assertIn('from "./fluxio/FluxioApp"', main_tsx)
        self.assertIn("SidebarProvider", fluxio_app)
        self.assertIn("Thread and proof", fluxio_app)
        self.assertIn("Apps, previews, and bridge runs", fluxio_app)
        self.assertIn("Needs approval now", fluxio_app)
        self.assertIn("Decision queue", fluxio_app)
        self.assertIn("Task navigator", fluxio_app)
        self.assertIn("Timeline", fluxio_app)
        self.assertIn("Context, apps, and escalation", fluxio_app)

    def test_bridge_exposes_t3_facing_facade_commands(self) -> None:
        bridge = FLUXIO_BRIDGE.read_text(encoding="utf-8")

        self.assertIn("export async function getSnapshot", bridge)
        self.assertIn("export async function dispatchCommand", bridge)
        self.assertIn('"mission.start"', bridge)
        self.assertIn('"approval.resolve"', bridge)
        self.assertIn("export function getTurnDiff", bridge)
        self.assertIn("export function getFullThreadDiff", bridge)
        self.assertIn("export function replayEvents", bridge)

    def test_tauri_frontend_dist_points_at_t3_web_build(self) -> None:
        tauri_conf = json.loads(TAURI_CONF.read_text(encoding="utf-8"))
        self.assertEqual(tauri_conf["build"]["frontendDist"], "../t3code/apps/web/dist")

    def test_package_json_exposes_desktop_verification_script(self) -> None:
        package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
        scripts = package.get("scripts", {})

        self.assertIn("verify:desktop", scripts)
        self.assertIn("python -m pytest tests -q", scripts["verify:desktop"])
        self.assertIn("npm run frontend:build", scripts["verify:desktop"])
        self.assertIn("npm run tauri build -- --debug", scripts["verify:desktop"])

    def test_pause_reason_and_runtime_lane_still_read_from_shared_mission_loop(self) -> None:
        helpers = HELPERS_JS.read_text(encoding="utf-8")

        self.assertIn("timeBudget?.lastPauseReason", helpers)
        self.assertIn("currentRuntimeLane", helpers)


if __name__ == "__main__":
    unittest.main()
