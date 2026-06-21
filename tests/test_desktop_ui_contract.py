from __future__ import annotations

import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "web" / "index.html"
MAIN_TSX = ROOT / "web" / "src" / "main.tsx"
FLUXIO_APP = ROOT / "web" / "src" / "fluxio" / "FluxioApp.tsx"
FLUXIO_BRIDGE = ROOT / "web" / "src" / "fluxio" / "fluxioBridge.ts"
FLUXIO_SHELL = ROOT / "web" / "src" / "fluxio" / "FluxioShell.jsx"
FLUXIO_STYLES = ROOT / "web" / "src" / "fluxio" / "styles.css"
HELPERS_JS = ROOT / "desktop-ui" / "fluxioHelpers.js"
MISSION_MODEL = ROOT / "desktop-ui" / "missionControlModel.js"
TAURI_CONF = ROOT / "src-tauri" / "tauri.conf.json"
PACKAGE_JSON = ROOT / "package.json"
CONTROL_SMOKE = ROOT / "scripts" / "control_route_smoke.mjs"
CONTROL_VISUAL_SMOKE = ROOT / "scripts" / "control_route_visual_smoke.py"
CONTROL_INTERACTION_SMOKE = ROOT / "scripts" / "control_route_interaction_smoke.py"
VOICE_PANEL = ROOT / "web" / "src" / "fluxio" / "voice" / "VoiceCommandPanel.jsx"
VOICE_CONTROLLER = ROOT / "web" / "src" / "fluxio" / "voice" / "useVoiceInteractionController.js"
VOICE_ADAPTERS = ROOT / "web" / "src" / "fluxio" / "voice" / "voiceCaptureAdapters.js"
VOICE_INDEX = ROOT / "web" / "src" / "fluxio" / "voice" / "index.js"


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
        self.assertIn("React.lazy", fluxio_app)
        self.assertIn('import("./FluxioShell.jsx")', fluxio_app)
        self.assertIn("React.Suspense", fluxio_app)
        self.assertIn("control-shell-loading", fluxio_app)
        self.assertNotIn('import { FluxioShellApp } from "./FluxioShell.jsx"', fluxio_app)
        self.assertNotIn("PublicProductPage", fluxio_app)
        self.assertNotIn("grand-public-page", fluxio_app)
        self.assertNotIn("buildLiveReviewWorkbench", fluxio_app)

    def test_bridge_exposes_fluxio_facade_commands(self) -> None:
        bridge = FLUXIO_BRIDGE.read_text(encoding="utf-8")

        self.assertIn("export async function getSnapshot", bridge)
        self.assertIn("export async function dispatchCommand", bridge)
        self.assertIn('"mission.start"', bridge)
        self.assertIn('"approval.resolve"', bridge)
        self.assertIn("export function getTurnDiff", bridge)
        self.assertIn("export function getFullThreadDiff", bridge)
        self.assertNotIn("export function replayEvents", bridge)

    def test_tauri_frontend_dist_points_at_web_build(self) -> None:
        tauri_conf = json.loads(TAURI_CONF.read_text(encoding="utf-8"))
        self.assertEqual(tauri_conf["build"]["frontendDist"], "../web/dist")

    def test_package_json_exposes_desktop_verification_script(self) -> None:
        package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
        scripts = package.get("scripts", {})

        self.assertIn("verify:desktop", scripts)
        self.assertIn("verify:browser", scripts)
        self.assertIn("node scripts/control_route_smoke.mjs", scripts["verify:browser"])
        self.assertIn("python -m pytest tests -q", scripts["verify:desktop"])
        self.assertIn("npm run frontend:build", scripts["verify:desktop"])
        self.assertIn("npm run tauri build -- --debug", scripts["verify:desktop"])

    def test_pause_reason_and_runtime_lane_still_read_from_shared_mission_loop(self) -> None:
        helpers = HELPERS_JS.read_text(encoding="utf-8")

        self.assertIn("timeBudget?.lastPauseReason", helpers)
        self.assertIn("currentRuntimeLane", helpers)

    def test_private_control_route_renders_current_black_shell_not_old_reference_skin(self) -> None:
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")
        styles = FLUXIO_STYLES.read_text(encoding="utf-8")

        self.assertFalse((ROOT / "web" / "src" / "fluxio" / "FluxioReferenceShell.jsx").exists())
        self.assertFalse((ROOT / "web" / "src" / "fluxio" / "ImagePlayground.jsx").exists())
        self.assertFalse((ROOT / "web" / "src" / "fluxio" / "RuntimeOperationsPanel.jsx").exists())
        self.assertNotIn("FluxioReferenceShell", shell)
        self.assertNotIn("fluxos-", shell)
        self.assertNotIn(".fluxos-", styles)
        self.assertNotIn(".reference-", styles)
        self.assertNotIn(".image-playground", styles)
        self.assertNotIn(".grand-public", styles)
        self.assertNotIn(".grand-console", styles)
        self.assertNotIn(".syntelos-review", styles)
        self.assertNotIn(".syntelos-app-preview", styles)
        self.assertIn('className="fluxio-shell"', shell)
        self.assertIn("data-mode={uiMode}", shell)
        self.assertIn("control-preview-refresh", shell)
        self.assertIn("interactionModeOptions", shell)
        self.assertIn('aria-label="Interaction modes"', shell)
        self.assertIn("interaction:${item.id}", shell)
        self.assertIn('role="button"', shell)
        self.assertIn("onKeyDown={handleKeyDown}", shell)
        self.assertNotIn('<button\n      className={`fluxio-nav-item', shell)
        self.assertNotIn("reference-preview-refresh", shell)
        self.assertNotIn("showBlockingSnapshotLoader", shell)
        self.assertNotIn("Loading live control-room state", shell)

    def test_current_shell_motion_layer_has_accessible_interaction_polish(self) -> None:
        styles = FLUXIO_STYLES.read_text(encoding="utf-8")

        for fragment in [
            ".interaction-mode-rail",
            ".fluxio-mode::before",
            ".fluxio-shell[data-mode=\"builder\"] .fluxio-mode::before",
            ".app-menu::-webkit-scrollbar",
            "grid-template-columns: repeat(3, minmax(0, 1fr))",
            "control-topbar-scan",
            "control-micro-line",
            ".builder-panel:hover::after",
            ".fluxio-nav-item:focus-visible::after",
            "@media (prefers-reduced-motion: reduce)",
        ]:
            self.assertIn(fragment, styles)
        self.assertNotIn("control-micro-line 3.6s", styles)
        self.assertNotIn("control-line-draw 4.8s", styles)

    def test_browser_proof_scripts_reject_wrong_skins(self) -> None:
        smoke = CONTROL_SMOKE.read_text(encoding="utf-8")
        visual = CONTROL_VISUAL_SMOKE.read_text(encoding="utf-8")
        interaction = CONTROL_INTERACTION_SMOKE.read_text(encoding="utf-8")

        for source in (smoke, visual, interaction):
            self.assertIn("preview-control=1", source)
            self.assertIn("fluxio-shell", source)
            self.assertIn("fluxos-shell", source)
            self.assertIn("grand-public-page", source)

    def test_slash_panel_surfaces_comments_skills_and_cleanup_command(self) -> None:
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")

        self.assertIn("COMMENT_SLASH_COMMANDS", shell)
        self.assertIn('kind: "comment"', shell)
        self.assertIn('kind: "skill"', shell)
        self.assertIn("/cleanup-legacy-ui", shell)
        self.assertIn("Legacy UI cleanup", shell)

    def test_skills_hub_surfaces_jbheaven_runtime_loop_and_voice_accessibility_skills(self) -> None:
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")

        self.assertIn("JBHEAVEN Godmode Lab", shell)
        self.assertIn("Hermes Skill Packager", shell)
        self.assertIn("Runtime Loop Supervisor", shell)
        self.assertIn("Voice Accessibility Operator", shell)
        self.assertIn("mergeReferenceStudioState", shell)
        self.assertIn("referenceSkillEffectTrace", shell)
        self.assertIn("private chain-of-thought", shell)

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
        self.assertIn("select,\ninput,\ntextarea", styles)
        self.assertIn("appearance: none", styles)

    def test_provider_auth_ui_does_not_fake_chatgpt_or_minimax_login(self) -> None:
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")

        self.assertNotIn("chatgpt.com/auth/login", shell)
        self.assertNotIn("Connect ChatGPT", shell)
        self.assertNotIn("ChatGPT login", shell)
        self.assertNotIn("Connect MiniMax", shell)
        self.assertNotIn("MiniMax portal auth preference saved", shell)
        self.assertIn("Connect Codex OAuth", shell)
        self.assertIn("start_openai_codex_oauth_command", shell)
        self.assertIn("complete_openai_codex_oauth_command", shell)
        self.assertIn("start_minimax_openclaw_auth_command", shell)
        self.assertIn("complete_minimax_openclaw_auth_command", shell)
        self.assertIn("get_minimax_openclaw_auth_status_command", shell)
        self.assertIn("MiniMax OpenClaw OAuth", shell)
        self.assertIn("Accounts used by OpenClaw", shell)
        self.assertIn("Connect model accounts", shell)
        self.assertIn("Connect model account", shell)

    def test_provider_oauth_actions_offer_web_nas_fallback(self) -> None:
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")

        self.assertIn("providerOAuthActionsAvailable", shell)
        self.assertIn('protocol === "https:"', shell)
        self.assertIn("Complete OpenAI Codex OAuth", shell)
        self.assertIn("callbackPort || 1455", shell)
        self.assertIn("OpenAI redirects Codex OAuth to localhost", shell)
        self.assertIn("desktop app catches that callback directly", shell)
        self.assertIn("Copy fallback relay helper", shell)
        self.assertIn("Connect Codex OAuth", shell)
        self.assertIn("Complete MiniMax OpenClaw OAuth", shell)
        self.assertIn("Verify MiniMax", shell)
        self.assertIn("MiniMax uses a portal user-code grant", shell)
        self.assertNotIn("codex/device", shell)
        self.assertNotIn("device-code", shell)
        self.assertIn("MiniMax OpenClaw auth command copied", shell)

    def test_provider_ecosystem_is_visible_in_runtime_drawer(self) -> None:
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")
        styles = FLUXIO_STYLES.read_text(encoding="utf-8")
        provider_panel = (ROOT / "web" / "src" / "fluxio" / "provider" / "ProviderEcosystemPanel.jsx").read_text(encoding="utf-8")

        self.assertIn("providerEcosystem", shell)
        self.assertIn("ProviderEcosystemPanel", shell)
        self.assertIn('import("./provider/ProviderEcosystemPanel.jsx")', shell)
        self.assertIn("Provider ecosystem", provider_panel)
        self.assertIn("Routes, catalogs, and safe updates", provider_panel)
        self.assertIn("Default route changes require approval", provider_panel)
        self.assertIn("User-defined models are never overwritten", provider_panel)
        self.assertIn("Compatibility warnings", provider_panel)
        self.assertIn("provider health check", provider_panel)
        self.assertIn("model capabilities", provider_panel)
        self.assertIn("provider-capability-chips", provider_panel)
        self.assertIn("provider-health-note", provider_panel)
        self.assertIn("Provider update readiness checklist", provider_panel)
        self.assertIn("Safe refresh checklist", provider_panel)
        self.assertIn("provider-update-readiness", styles)
        self.assertIn("provider-update-readiness-row", styles)
        self.assertIn("Fluxio will re-check setup after the update.", shell)
        self.assertIn("update-safety-note", shell)
        self.assertIn("provider-ecosystem-panel", styles)
        self.assertIn("provider-ecosystem-list", styles)
        self.assertIn(".provider-health-note", styles)
        self.assertIn(".provider-capability-chips", styles)
        self.assertIn(".update-safety-note", styles)

    def test_tauri_registers_live_review_structured_feedback_command(self) -> None:
        tauri = (ROOT / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")

        self.assertIn("record_live_review_structured_feedback_command", tauri)
        self.assertIn("live_review_visual_proof", tauri)
        self.assertIn("proofOnly", tauri)
        self.assertIn("live_review_receipts", tauri)
        self.assertIn("merge_live_review_receipts", tauri)
        self.assertIn("proofOnly", shell)
        self.assertIn("Capture proof", shell)

    def test_skills_drawer_surfaces_stuck_state_recovery_contract(self) -> None:
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")
        styles = FLUXIO_STYLES.read_text(encoding="utf-8")

        self.assertIn("missionSkillRecovery", shell)
        self.assertIn("mission?.missionLoop?.skillRecovery", shell)
        self.assertIn("mission?.state?.skill_recovery", shell)
        self.assertIn("Skill recovery", shell)
        self.assertIn("Recommended recovery skills", shell)
        self.assertIn("Recovery actions and route separation", shell)
        self.assertIn("Hermes/OpenClaw remain runtime lanes", shell)
        self.assertIn("Mission skill recovery", shell)
        self.assertIn("function cx(...values)", shell)
        self.assertIn("skill-recovery-panel", styles)
        self.assertIn("skill-recovery-strip", styles)
        self.assertIn("skill-recovery-list", styles)

    def test_builder_surfaces_external_monitor_loops(self) -> None:
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")
        styles = FLUXIO_STYLES.read_text(encoding="utf-8")
        model = MISSION_MODEL.read_text(encoding="utf-8")

        for fragment in [
            "deriveMonitoringLoopStudio",
            "supervisorInterventions",
            "interventionQueue",
            "topIntervention",
            "criticalCount",
            "blocked-state-sentry",
            "intent-drift-sentry",
            "silence-watchdog",
            "verification-sentinel",
            "milestone-notifier",
            "off_until_enabled_or_blocked",
        ]:
            self.assertIn(fragment, model)
        for fragment in [
            "monitoringLoopStudio",
            "External monitor loops",
            "Review blockers",
            "Review proof",
            "Review context",
            "monitor-loop-strip",
            "Supervisor intervention queue",
            "supervisor-intervention-strip",
            "supervisor-intervention-queue",
            "monitor-loop-panel",
        ]:
            self.assertIn(fragment, shell)
        self.assertIn(".monitor-loop-card", styles)
        self.assertIn(".monitor-loop-strip", styles)
        self.assertIn(".supervisor-intervention-card", styles)
        self.assertIn(".supervisor-intervention-strip", styles)

    def test_builder_surfaces_subagent_command_center(self) -> None:
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")
        styles = FLUXIO_STYLES.read_text(encoding="utf-8")
        model = MISSION_MODEL.read_text(encoding="utf-8")
        readiness = (ROOT / "web" / "src" / "fluxio" / "subagents" / "SubagentReadinessPanel.jsx").read_text(encoding="utf-8")

        for fragment in [
            "deriveSubagentOrchestrationStudio",
            "Subagent command center",
            "delegatedLaneTone",
            "configuredWorkers",
            "mergePolicy",
            "worker_merge_events",
            "supervisorAction",
            "blockReason",
            "Resolve blocked delegated lanes",
        ]:
            self.assertIn(fragment, model)
        for fragment in [
            "subagentOrchestrationStudio",
            "subagent-command-panel",
            "subagent-command-strip",
            "subagent-board-stack",
            "SubagentReadinessPanel",
            "Inspect runtime",
            "Resolve lane blocks",
            "Verify merge proof",
            "Delegated lane roster",
            "subagent-supervisor-note",
        ]:
            self.assertIn(fragment, shell)
        for fragment in [
            "Subagent spawn readiness",
            "Spawn readiness",
            "Handoff packet",
            "Suggested roles",
            "Subagent merge checklist",
            "Ready to spawn another lane",
            "Handoff context bounded",
            "Preserve user work during merge",
        ]:
            self.assertIn(fragment, readiness)
        self.assertIn(".subagent-lane-card", styles)
        self.assertIn(".subagent-readiness-panel", styles)
        self.assertIn(".subagent-handoff-grid", styles)
        self.assertIn(".subagent-merge-checklist", styles)
        self.assertIn(".subagent-supervisor-note", styles)
        self.assertIn(".subagent-command-strip", styles)
        self.assertIn(".subagent-board-card", styles)

    def test_control_room_surfaces_live_agent_artifacts_compartments_and_deploy_readiness(self) -> None:
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")
        styles = FLUXIO_STYLES.read_text(encoding="utf-8")

        self.assertIn("runtimeCompartments", shell)
        self.assertIn("hermesMissionEvidence", shell)
        self.assertIn("nasDeployReadiness", shell)
        self.assertIn("Generated image artifacts", shell)
        self.assertIn("Hermes mission evidence", shell)
        self.assertIn("NAS deploy readiness", shell)
        self.assertIn("Live runtime compartments", shell)
        self.assertIn("artifact.previewUrl", shell)
        self.assertIn("artifact.manifestUrl", shell)
        self.assertIn("emptyState", shell)
        self.assertIn(".agent-live-workbench-grid", styles)
        self.assertIn(".agent-artifact-card", styles)

    def test_current_shell_mounts_image_and_voice_surfaces(self) -> None:
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")
        styles = FLUXIO_STYLES.read_text(encoding="utf-8")

        self.assertIn("ImageStudioPlayground", shell)
        self.assertIn("lazy(() =>", shell)
        self.assertIn("Suspense", shell)
        self.assertIn("LazySurfaceFallback", shell)
        self.assertIn("generatedArtifacts={generatedImageArtifacts}", shell)
        self.assertIn("VoiceCommandPanel", shell)
        self.assertIn('surface === "images"', shell)
        self.assertIn('surface === "voice"', shell)
        self.assertIn("handleImageStudioRequestDraft", shell)
        self.assertIn("handleVoiceCommand", shell)
        self.assertIn('action === "voice.stop"', shell)
        self.assertIn('label="Images"', shell)
        self.assertIn('label="Voice"', shell)
        self.assertIn(".voice-studio-grid", styles)
        self.assertIn(".lazy-surface-fallback", styles)
        image_studio = (ROOT / "web" / "src" / "fluxio" / "image-studio" / "ImageStudioPlayground.jsx").read_text(encoding="utf-8")
        image_css = (ROOT / "web" / "src" / "fluxio" / "image-studio" / "image-studio.css").read_text(encoding="utf-8")
        self.assertIn("Served artifacts", image_studio)
        self.assertIn("GeneratedArtifactCard", image_studio)
        self.assertIn("No served generated image artifacts are available yet.", image_studio)
        self.assertIn("Green screen matte", image_studio)
        self.assertIn("Prepare chroma-key removal", image_studio)
        self.assertIn("Key color", image_studio)
        self.assertIn("Spill cleanup", image_studio)
        self.assertIn("Matte proof ready", image_studio)
        self.assertIn("ChromaMatteDiagnostics", image_studio)
        self.assertIn("Matte QA checklist", image_studio)
        self.assertIn("Proof source", image_studio)
        self.assertIn("Preview matte", image_studio)
        self.assertIn("Local matte proof preview", image_studio)
        self.assertIn("Synthetic green-screen sample", image_studio)
        self.assertIn("ArtifactBackendHealthNote", image_studio)
        self.assertIn("Artifact backend offline", image_studio)
        self.assertIn("scripts/run_web_backend.py", image_studio)
        self.assertIn("renderChromaMattePreview", image_studio)
        self.assertIn(".image-studio-generated-artifact", image_css)
        self.assertIn(".image-studio-chroma-card", image_css)
        self.assertIn(".image-studio-chroma-proof", image_css)
        self.assertIn(".image-studio-chroma-diagnostics", image_css)
        self.assertIn(".image-studio-local-matte-proof", image_css)
        self.assertIn(".image-studio-backend-health", image_css)
        self.assertIn("image-studio-white-line-scan", image_css)
        self.assertIn("route-decision-chip-row", shell)
        self.assertIn("Local proof", shell)
        self.assertIn("Route hardness", shell)
        self.assertIn(".route-decision-chip-row", styles)
        voice_panel = VOICE_PANEL.read_text(encoding="utf-8")
        voice_controller = VOICE_CONTROLLER.read_text(encoding="utf-8")
        voice_adapters = VOICE_ADAPTERS.read_text(encoding="utf-8")
        voice_index = VOICE_INDEX.read_text(encoding="utf-8")
        voice_css = (ROOT / "web" / "src" / "fluxio" / "voice" / "voice.css").read_text(encoding="utf-8")
        self.assertIn("speechAdapter", voice_panel)
        self.assertIn("Pre-send gate", voice_panel)
        self.assertIn("Capture source", voice_panel)
        self.assertIn("Capture state", voice_panel)
        self.assertIn("Capture stopped by", voice_panel)
        self.assertIn("Voice capture diagnostics", voice_panel)
        self.assertIn("Live capture not wired", voice_panel)
        self.assertIn("Last event", voice_panel)
        self.assertIn("Restart attempts", voice_panel)
        self.assertIn("Last error", voice_panel)
        self.assertIn("Dictation repair queue", voice_panel)
        self.assertIn("Repair queue", voice_panel)
        self.assertIn("Next repair", voice_panel)
        self.assertIn("Review console", voice_panel)
        self.assertIn("Correction text", voice_panel)
        self.assertIn("Apply correction", voice_panel)
        self.assertIn("Accidental-send check", voice_panel)
        self.assertIn("manualCorrectionDraft", voice_panel)
        self.assertIn("reviewConsoleStatus", voice_panel)
        self.assertIn("Mark reviewed", voice_panel)
        self.assertIn("correctTranscriptSegment", voice_panel)
        self.assertIn("describeVoiceCaptureStatus", voice_controller)
        self.assertIn("createVoiceCaptureAdapter", voice_controller)
        self.assertIn("onInterim", voice_controller)
        self.assertIn("onFinal", voice_controller)
        self.assertIn("onStop", voice_controller)
        self.assertIn("onLifecycle", voice_controller)
        self.assertIn("capture.stopped", voice_controller)
        self.assertIn("capture.lifecycle", voice_controller)
        self.assertIn("captureLifecycle", voice_controller)
        self.assertIn('state.pendingCommand.action === "voice.clearTranscript"', voice_controller)
        self.assertIn('reason: "voice_command"', voice_controller)
        self.assertIn("replaceTranscriptSegment", voice_controller)
        self.assertIn("createBrowserSpeechAdapter", voice_adapters)
        self.assertIn("maxAutoRestarts", voice_adapters)
        self.assertIn("Browser speech capture ended unexpectedly; reconnecting.", voice_adapters)
        self.assertIn("createBridgeSpeechAdapter", voice_adapters)
        self.assertIn("normalizeSpeechRecognitionResult", voice_adapters)
        self.assertIn("SpeechRecognition", voice_adapters)
        self.assertIn("__FLUXIO_VOICE_BRIDGE__", voice_adapters)
        self.assertIn("createVoiceCaptureAdapter", voice_index)
        self.assertIn(".fluxio-voice-capture-diagnostics", voice_css)
        self.assertIn(".fluxio-voice-capture-facts", voice_css)
        self.assertIn(".fluxio-voice-repair-queue", voice_css)
        self.assertIn(".fluxio-voice-repair-counts", voice_css)
        self.assertIn(".fluxio-voice-review-console", voice_css)
        self.assertIn(".fluxio-voice-manual-repair", voice_css)
        self.assertIn(".fluxio-voice-send-gate", voice_css)
        self.assertIn(".fluxio-voice-correction-actions", voice_css)

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
        self.assertIn("OpenCodeGo", shell)
        self.assertIn('<option value="opencode">OpenCodeGo</option>', shell)

    def test_old_bitmap_assets_are_not_part_of_current_ui(self) -> None:
        obsolete_assets = [
            ROOT / "desktop-ui" / "logo-main.png",
            ROOT / "desktop-ui" / "logo-mark.png",
            ROOT / "web" / "src" / "fluxio" / "assets" / "grand-agent-topology.png",
            ROOT / "web" / "src" / "fluxio" / "assets" / "grand-agent-nas-hero.png",
        ]
        for asset in obsolete_assets:
            self.assertFalse(asset.exists(), f"{asset.name} should stay removed unless current UI imports it")


if __name__ == "__main__":
    unittest.main()
