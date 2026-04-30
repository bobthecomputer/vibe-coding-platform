from __future__ import annotations

import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "web" / "index.html"
MAIN_TSX = ROOT / "web" / "src" / "main.tsx"
FLUXIO_APP = ROOT / "web" / "src" / "fluxio" / "FluxioApp.tsx"
FLUXIO_BRIDGE = ROOT / "web" / "src" / "fluxio" / "fluxioBridge.ts"
FLUXIO_REFERENCE_SHELL = ROOT / "web" / "src" / "fluxio" / "FluxioReferenceShell.jsx"
FLUXIO_SHELL = ROOT / "web" / "src" / "fluxio" / "FluxioShell.jsx"
FLUXIO_STYLES = ROOT / "web" / "src" / "fluxio" / "styles.css"
HELPERS_JS = ROOT / "desktop-ui" / "fluxioHelpers.js"
TAURI_CONF = ROOT / "src-tauri" / "tauri.conf.json"
PACKAGE_JSON = ROOT / "package.json"


class DesktopUiContractTests(unittest.TestCase):
    def test_index_html_mounts_web_root_and_entrypoint(self) -> None:
        html = INDEX_HTML.read_text(encoding="utf-8")

        self.assertIn('id="root"', html)
        self.assertIn('src="/src/main.tsx"', html)
        self.assertIn("DM+Sans", html)

    def test_main_entry_mounts_fluxio_app_inside_web_source_tree(self) -> None:
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

    def test_bridge_exposes_fluxio_facade_commands(self) -> None:
        bridge = FLUXIO_BRIDGE.read_text(encoding="utf-8")

        self.assertIn("export async function getSnapshot", bridge)
        self.assertIn("export async function dispatchCommand", bridge)
        self.assertIn('"mission.start"', bridge)
        self.assertIn('"approval.resolve"', bridge)
        self.assertIn("export function getTurnDiff", bridge)
        self.assertIn("export function getFullThreadDiff", bridge)
        self.assertIn("export function replayEvents", bridge)

    def test_tauri_frontend_dist_points_at_web_build(self) -> None:
        tauri_conf = json.loads(TAURI_CONF.read_text(encoding="utf-8"))
        self.assertEqual(tauri_conf["build"]["frontendDist"], "../web/dist")

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

    def test_reference_shell_buttons_are_wired_to_actions(self) -> None:
        shell = FLUXIO_REFERENCE_SHELL.read_text(encoding="utf-8")

        self.assertNotIn("onClick={() => {}}", shell)
        self.assertIn('onRequestAction?.("flow:search")', shell)
        self.assertIn('onRequestAction?.("flow:add-project")', shell)
        self.assertIn('onRequestAction?.("builder:new-project")', shell)
        self.assertIn('onRequestAction?.("builder:project-actions"', shell)
        self.assertIn('onRequestAction?.("idle:reset-defaults")', shell)
        self.assertIn('onRequestAction?.("settings:export-data")', shell)

    def test_slash_panel_surfaces_comments_and_skills(self) -> None:
        reference_shell = FLUXIO_REFERENCE_SHELL.read_text(encoding="utf-8")
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")

        self.assertIn('kind === "skill"', reference_shell)
        self.assertIn('return "S"', reference_shell)
        self.assertIn("COMMENT_SLASH_COMMANDS", shell)
        self.assertIn('kind: "comment"', shell)

    def test_settings_is_global_rail_navigation_item(self) -> None:
        reference_shell = FLUXIO_REFERENCE_SHELL.read_text(encoding="utf-8")
        styles = FLUXIO_STYLES.read_text(encoding="utf-8")

        self.assertIn('active={surface === "settings"}', reference_shell)
        self.assertIn('label="Settings"', reference_shell)
        self.assertNotIn("reference-sidebar-settings", styles)
        self.assertNotIn('className="reference-sidebar-settings"', reference_shell)

    def test_packaged_tauri_defaults_to_live_mode_without_fixture(self) -> None:
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")

        self.assertIn("function resolveInitialPreviewMode", shell)
        self.assertIn('const explicitFixture = searchParams.get("fixture")', shell)
        self.assertIn("if (hasTauriBackend())", shell)
        self.assertIn('return "live";', shell)
        self.assertNotIn(
            'searchParams.get("fixture") || localStorage.getItem(STORAGE_KEYS.previewMode) || "live"',
            shell,
        )

    def test_selector_controls_use_polished_drawer_style(self) -> None:
        styles = FLUXIO_STYLES.read_text(encoding="utf-8")

        self.assertIn(".agent-control-grid", styles)
        self.assertIn('content: "Route selector"', styles)
        self.assertIn(".field select,", styles)
        self.assertIn("appearance: none", styles)

    def test_provider_auth_ui_does_not_fake_chatgpt_or_minimax_login(self) -> None:
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")
        reference_shell = FLUXIO_REFERENCE_SHELL.read_text(encoding="utf-8")

        self.assertNotIn("chatgpt.com/auth/login", shell)
        self.assertNotIn("Connect ChatGPT", shell)
        self.assertNotIn("ChatGPT login", shell)
        self.assertNotIn("Connect MiniMax", shell)
        self.assertNotIn("MiniMax portal auth preference saved", shell)
        self.assertIn("Connect Codex OAuth", shell)
        self.assertIn("start_openai_codex_oauth_command", shell)
        self.assertIn("complete_openai_codex_oauth_command", shell)
        self.assertIn("start_minimax_openclaw_auth_command", shell)
        self.assertIn("get_minimax_openclaw_auth_status_command", shell)
        self.assertIn("MiniMax OpenClaw OAuth", shell)
        self.assertIn("Accounts used by OpenClaw", shell)
        self.assertIn("Connect model accounts", shell)
        self.assertIn("Connect model account", shell)
        self.assertIn("ChatGPT connection", reference_shell)
        self.assertIn("ChatGPT-compatible MCP endpoint", reference_shell)

    def test_provider_oauth_actions_require_desktop_credential_service(self) -> None:
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")
        reference_shell = FLUXIO_REFERENCE_SHELL.read_text(encoding="utf-8")

        self.assertIn("providerOAuthActionsAvailable", shell)
        self.assertIn(
            "Model OAuth account setup requires the desktop credential service (Tauri).",
            shell,
        )
        self.assertIn("quickAuth.disabled", reference_shell)
        self.assertIn("disabled={Boolean(provider.quickAuth.disabled)}", reference_shell)

    def test_builder_agent_modes_and_runtimes_remain_distinct(self) -> None:
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")

        self.assertIn("data-mode={uiMode}", shell)
        self.assertIn('setUiMode("agent")', shell)
        self.assertIn('setUiMode("builder")', shell)
        self.assertIn('label="Agent"', shell)
        self.assertIn('label="Builder"', shell)
        self.assertIn('label: "Setup"', shell)
        self.assertIn("OpenClaw live connection", shell)
        self.assertIn("Work engines", shell)
        self.assertIn("Work engines and accounts", shell)
        self.assertIn("primaryRuntimeServices", shell)


if __name__ == "__main__":
    unittest.main()
