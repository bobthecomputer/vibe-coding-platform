from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
FLUXIO_SHELL = ROOT / "web" / "src" / "fluxio" / "FluxioShell.jsx"
FLUXIO_APP = ROOT / "web" / "src" / "fluxio" / "FluxioApp.tsx"
MODEL = ROOT / "desktop-ui" / "missionControlModel.js"
STYLES = ROOT / "web" / "src" / "fluxio" / "styles.css"


class LiveReviewPanelFrontendTests(unittest.TestCase):
    def test_live_review_model_includes_required_event_domains(self) -> None:
        model = MODEL.read_text(encoding="utf-8")

        for fragment in [
            'kind: "file_change"',
            'kind: "browser_qa"',
            'kind: "computer_use"',
            'kind: "preview_refresh"',
            'kind: "verification"',
            'kind: "image_playground"',
            'kind: "operator_followup"',
            'kind: "progress_update"',
            'kind: "runtime_activity"',
            'kind: "continuation_supervisor"',
            'kind: "replay_marker"',
            "annotationReadiness",
            "recoveryAction",
            "queueTimeline",
            "providerEvents",
            "generatedImages",
            "layerHandoff",
            "launchedPrograms",
            "runtimeActivity",
            "progressUpdate",
            "cadenceMinutes",
            "cadenceState",
            "cadenceAgeMinutes",
            "deepLink",
            "tests",
            "replayMarkers",
            "acknowledgedBy",
            "operatorMessages",
            "page",
            "screenshotFrames",
            "snapshotPath",
            "thumbnailPath",
            "frameId",
            "proofTarget",
            "threadTarget",
            "selectedSkills",
            "plannerRules",
            "designPrompts",
            "plannerProof",
            "continuationSupervisor",
            "routePreservation",
            "dispatchLagMinutes",
            "reconcileLatencyMs",
            "blockerReason",
            "externalHeartbeatRequired",
            "failureReason",
            "nextIdea",
            "structuredFeedbackReceipt",
            "latestStructuredFeedbackReceipt",
            "live_review_structured_feedback",
            "plannerExecutorHandoffId",
        ]:
            self.assertIn(fragment, model)

    def test_connected_device_bridge_evidence_is_exposed_to_live_review(self) -> None:
        bridge = (ROOT / "web" / "src" / "fluxio" / "fluxioBridge.ts").read_text(encoding="utf-8")
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")
        styles = STYLES.read_text(encoding="utf-8")

        for fragment in [
            "connectedDeviceBridge",
            "dualPathBridge",
            "performedByHost",
            "pendingApprovals",
            "syncStatus",
            "receipts",
            "bridge.permission",
            "set_connected_device_bridge_permission_command",
            "plan_connected_device_bridge_operation_command",
        ]:
            self.assertIn(fragment, bridge)
        for fragment in [
            "Dual-path bridge",
            "builder-live-review-bridge",
            "Performed by",
            "Sync:",
            "Operation receipt",
            "Host status:",
        ]:
            self.assertIn(fragment, shell)
        self.assertIn(".builder-live-review-bridge", styles)

    def test_live_review_planner_proof_shows_decision_influence_and_coworking_status(self) -> None:
        model = MODEL.read_text(encoding="utf-8")
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")
        styles = STYLES.read_text(encoding="utf-8")

        self.assertIn("decisionInfluence", model)
        for fragment in [
            "Skill/ruleset impact",
            "builder-live-proof-impact-grid",
            "Applied to",
            "Co-working status",
            "Side-by-side preview",
            "Feedback bridge",
            "Evidence timeline",
            "Planner \u2192 executor bridge packet",
            "Route context",
            "Task context",
            "Verifier feedback",
            "status updates",
        ]:
            self.assertIn(fragment, shell)
        for fragment in [
            ".builder-cowork-status-grid",
            ".builder-live-proof-impact-grid",
            ".builder-live-bridge-packet",
            ".builder-live-bridge-grid",
            "touch-action: manipulation",
        ]:
            self.assertIn(fragment, styles)

    def test_fluxio_app_live_review_renders_coworking_bridge_and_skill_influence_panels(self) -> None:
        app = FLUXIO_APP.read_text(encoding="utf-8")
        bridge = (ROOT / "web" / "src" / "fluxio" / "fluxioBridge.ts").read_text(encoding="utf-8")
        styles = STYLES.read_text(encoding="utf-8")

        for fragment in [
            "skillInfluence",
            "coworkStatus",
            "plannerBridgePacket",
            "statusUpdates",
            "routeContext",
            "taskContext",
            "verifierFeedback",
        ]:
            self.assertIn(fragment, bridge)
        for fragment in [
            "Side-by-side preview",
            "Feedback bridge",
            "Evidence timeline",
            "Planner \u2192 executor bridge packet",
            "Route/model/task context",
            "Verifier feedback",
            "Skill/ruleset impact",
            "Design prompts + next idea",
            "Status updates",
        ]:
            self.assertIn(fragment, app)
        for fragment in [
            ".syntelos-review-cowork-grid",
            ".syntelos-review-bridge-grid",
            ".syntelos-review-skill-influence",
            ".syntelos-review-status-updates",
            "touch-action: manipulation",
        ]:
            self.assertIn(fragment, styles)

    def test_live_review_side_panel_renders_current_shell_timeline_and_annotations(self) -> None:
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")
        styles = STYLES.read_text(encoding="utf-8")

        for fragment in [
            "Live Review Timeline",
            "builder-live-review-panel",
            "builder-live-review-events",
            "builder-live-review-event",
            "builder-live-review-queue-strip",
            "builder-live-review-event-group",
            "builder-live-review-meta",
            "Browser annotations",
            "builder-live-annotation-item",
            "Page/layer:",
            "Recovery:",
            "builder-live-annotation-map",
            "builder-live-annotation-rect",
            "builder-live-annotation-pin",
            "Design prompts",
            "Next idea handoff",
            "Send structured feedback",
            "Latest structured feedback receipt",
            "Receipt kind: live_review_structured_feedback",
            "Timeline receipt kind: live_review_structured_feedback",
            "Proof eventId",
            "Copy receipt proof handle",
            "builder-live-review-receipt-handles",
            "Copy latest receipt eventId",
            "Copy latest plannerExecutorHandoffId",
            "data-proof-handle",
            "Structured feedback receipt history",
            "Copy receipt history eventId",
            "Copy receipt history plannerExecutorHandoffId",
            "Copy receipt history combined proof handle",
            "Copy all handles",
            "Jump to source event",
            "history-jump-source-event",
            "plannerExecutorHandoffId",
        ]:
            self.assertIn(fragment, shell)
        self.assertIn(".builder-live-review-receipt-handles", styles)
        self.assertIn(".builder-live-review-receipt-history", styles)

    def test_control_room_renders_runtime_compartment_and_visual_generated_artifacts(self) -> None:
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")
        styles = STYLES.read_text(encoding="utf-8")

        for fragment in [
            "agent-compartment-box",
            "Runtime compartment",
            "Tool/action timeline",
            "Files and approvals",
            "builder-live-review-image-grid",
            "artifactUrlForRecord",
            "resolveControlArtifactUrl",
            "Preview not served",
        ]:
            self.assertIn(fragment, shell)
        for fragment in [
            ".agent-compartment-box",
            ".agent-compartment-matrix",
            ".builder-live-review-image-card",
            ".builder-live-review-artifact-list",
        ]:
            self.assertIn(fragment, styles)

    def test_removed_standalone_old_ui_files_stay_deleted(self) -> None:
        self.assertFalse((ROOT / "web" / "src" / "fluxio" / "FluxioReferenceShell.jsx").exists())
        self.assertFalse((ROOT / "web" / "src" / "fluxio" / "ImagePlayground.jsx").exists())
        self.assertFalse((ROOT / "web" / "src" / "fluxio" / "RuntimeOperationsPanel.jsx").exists())
        self.assertFalse((ROOT / "web" / "src" / "fluxio" / "imageProviderAdapters.js").exists())
        styles = STYLES.read_text(encoding="utf-8")
        self.assertNotIn(".reference-shell", styles)
        self.assertNotIn(".image-playground", styles)

    def test_live_review_side_panel_renders_clickthrough_and_replay_controls(self) -> None:
        shell = FLUXIO_SHELL.read_text(encoding="utf-8")
        styles = STYLES.read_text(encoding="utf-8")

        for fragment in [
            "selectedLiveReviewEvent",
            "builder-live-review-focus",
            "builder-live-review-controls",
            "Rewind marker",
            "Previous frame",
            "Next frame",
            "setSelectedLiveReviewEventId",
            "screenshotFrames",
            "Marker-to-frame timeline rail",
            "Autoplay timelapse",
            "Pause timelapse",
            "Jump to review block",
            "Open preview URL",
            "Open {titleizeToken(selectedLiveReviewEvent.deepLink.drawerId)} drawer",
            "Cadence ${titleizeToken(item.cadenceState)}",
            "stepReplayMarker",
            "Runtime activity detail",
            "Internal Continuation Supervisor",
            "Internal supervisor state and failure reason",
            "Failure reason:",
            "Blocker reason:",
            "External heartbeat required:",
            "Preserved route:",
            "continuation_supervisor",
            "Planner proof",
            "Planner skills and prompts",
            "Selected skills: none captured yet",
            "builder-live-proof-chip-row",
            "builder-live-proof-chip",
            "Skill chip opened",
            "Skills drawer filtered to",
            "Design prompt detail",
            "Next idea handoff draft seeded",
            "Follow-up from planner next idea",
            "ArrowRight",
            "ArrowLeft",
            'role="listbox"',
            "onKeyDown={event =>",
        ]:
            self.assertIn(fragment, shell)
        for fragment in [
            ".builder-live-review-layout",
            ".builder-live-review-panel",
            ".builder-live-review-focus",
            ".builder-live-review-controls",
            ".builder-live-review-timeline-rail",
        ]:
            self.assertIn(fragment, styles)


if __name__ == "__main__":
    unittest.main()
