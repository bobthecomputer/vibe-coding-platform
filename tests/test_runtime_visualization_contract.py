from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "web" / "src" / "fluxio" / "FluxioShell.jsx"
DRAWER = ROOT / "web" / "src" / "fluxio" / "FluxioDrawerPanel.jsx"
WORKSPACE_MODEL = ROOT / "web" / "src" / "fluxio" / "workspaceModel.js"
STYLES = ROOT / "web" / "src" / "fluxio" / "styles.css"
MODEL = ROOT / "desktop-ui" / "missionControlModel.js"


def shell_surface_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (SHELL, DRAWER)
        if path.exists()
    )


def test_workbench_runtime_ops_surface_is_first_class() -> None:
    source = shell_surface_source()

    assert "Runtime bridge" in source
    assert "Open runtime bridge" in source
    assert "Connect model account" in source
    assert "runtimeOps" in source


def test_runtime_ops_actions_execute_through_settings_service_action_path() -> None:
    source = SHELL.read_text(encoding="utf-8")

    assert "handleReferenceQuickAuth" in source
    assert "setActiveDrawer(\"runtime\")" in source


def test_workbench_uses_current_fluxio_shell_not_deleted_reference_shell() -> None:
    source = SHELL.read_text(encoding="utf-8")

    assert "Builder workbench" in source
    assert "builder-workbench-grid" in source
    assert not (ROOT / "web" / "src" / "fluxio" / "FluxioReferenceShell.jsx").exists()
    assert not (ROOT / "web" / "src" / "fluxio" / "RuntimeOperationsPanel.jsx").exists()


def test_workbench_runtime_panel_is_not_trapped_in_top_grid_row() -> None:
    source = STYLES.read_text(encoding="utf-8")

    assert ".builder-workbench-grid" in source
    assert ".agent-live-workbench-grid" in source
    assert ".builder-live-review-panel" in source


def test_workbench_state_exposes_runtime_update_and_auto_verify_counts() -> None:
    source = shell_surface_source()
    model_source = WORKSPACE_MODEL.read_text(encoding="utf-8")

    assert "runtimeOps" in source
    assert "deriveRuntimeOperations(serviceStudio)" in source
    assert "export function deriveRuntimeOperations" in model_source
    assert "autoVerifyCount" in model_source
    assert "updateActionCount" in model_source
    assert "updateServices" in model_source


def test_service_model_preserves_auto_run_verify_for_runtime_actions() -> None:
    source = MODEL.read_text(encoding="utf-8")

    assert "autoRunVerify: Boolean(action.autoRunVerify)" in source
    assert "followUp: action.followUp" in source


def test_builder_runtime_card_exposes_fused_runtime_without_promoting_provider_to_runtime() -> None:
    source = shell_surface_source()
    runtime_contract = (ROOT / "web" / "src" / "fluxio" / "runtime" / "RuntimeTruthContract.jsx").read_text(encoding="utf-8")
    fixtures = (ROOT / "desktop-ui" / "fixtures.js").read_text(encoding="utf-8")

    assert "fusedRuntime" in source
    assert 'import("./runtime/RuntimeTruthContract.jsx")' in source
    assert "Runtime lane" in source
    assert "Provider route" in source
    assert "modelProviderRoutes" in source
    assert "Fused runtime truth contract" in runtime_contract
    assert "Runtime adapter added" in runtime_contract
    assert "Providers stay model routes, not runtime lanes" in runtime_contract
    assert "Latest runtime lane proof" in runtime_contract
    assert "Runtime readiness and recovery gates" in runtime_contract
    assert "Runtime proof flight recorder" in runtime_contract
    assert "Proof artifact integrity" in runtime_contract
    assert "Runtime recovery proof gate" in runtime_contract
    assert "Recovery proof gate" in runtime_contract
    assert "missionSkillRecovery" in runtime_contract
    assert "missionSkillRecoveryPlan" in runtime_contract
    assert "recoveryRetryGuard" in runtime_contract
    assert "Proof before retry:" in runtime_contract
    assert "must attach before retry" in runtime_contract
    assert "No mission recovery action is active right now." in runtime_contract
    assert "Runtime proof artifact integrity" in runtime_contract
    assert "missingGateArtifacts" in runtime_contract
    assert "Missing gate proof:" in runtime_contract
    assert "proofGateSummary" in runtime_contract
    assert "proofRunCommand" in runtime_contract
    assert "requiredArtifacts" in runtime_contract
    assert "runtime-proof-flight-recorder" in runtime_contract
    assert "runtime-proof-artifact-integrity" in runtime_contract
    assert "runtime-proof-artifact-list" in runtime_contract
    assert "runtime-proof-next-actions" in runtime_contract
    assert "runtime-recovery-proof-gate" in runtime_contract
    assert "runtime-recovery-proof-grid" in runtime_contract
    assert "runtime-readiness-contract" in runtime_contract
    assert "runtime-readiness-summary-list" in runtime_contract
    assert "runtime-readiness-gate-list" in runtime_contract
    assert "Promotion blocked:" in runtime_contract
    assert "blocks promotion:" in runtime_contract
    assert "proofType" in runtime_contract
    assert "live runtime execution:" in runtime_contract
    assert "live model calls:" in runtime_contract
    assert "runtime adapter added:" in runtime_contract
    assert "runtime-truth-contract" in runtime_contract
    assert "runtime-lane-proof-receipt" in runtime_contract
    assert "runtimeProofReceipt" in source
    assert "runtimeProofGateSummary" in source
    assert "missionSkillRecovery={missionSkillRecovery}" in source
    assert "missionSkillRecoveryPlan={missionSkillRecoveryPlan}" in source
    assert "runtimeProofGateCommand" in source
    assert "Runtime proof receipt" in source
    assert "Open proof receipt" in source
    assert "agent-runtime-proof-receipt" in source
    assert "latestFusedRuntimeProof" in source
    assert "runtimeSkillProofRoute" in source
    assert "runtimeSkillProofProvider" in source
    assert "runtimeSkillProofRuntime" in source
    assert "runtimeSkillProofSelectedSkill" in source
    assert "runtimeSkillProofRequirementLabel" in source
    assert "runtimeSkillProofRetryBlocked" in source
    assert "runtime-skill-proof-strip" in source
    assert "Runtime + skill proof" in source
    assert "Runtime and skill proof for current mission" in source
    assert "Proof before retry:" in source
    assert "Promotion gates" in source
    assert "Proof command" in source
    assert "Review recovery" in source
    assert "Inspect runtime" in source
    assert "Live execution" in source
    assert ".runtime-truth-contract" in STYLES.read_text(encoding="utf-8")
    assert ".runtime-lane-proof-receipt" in STYLES.read_text(encoding="utf-8")
    assert ".runtime-readiness-contract" in STYLES.read_text(encoding="utf-8")
    assert ".runtime-readiness-gate-list" in STYLES.read_text(encoding="utf-8")
    assert ".runtime-proof-flight-recorder" in STYLES.read_text(encoding="utf-8")
    assert ".runtime-proof-artifact-integrity" in STYLES.read_text(encoding="utf-8")
    assert ".runtime-proof-artifact-list" in STYLES.read_text(encoding="utf-8")
    assert ".runtime-proof-flight-grid" in STYLES.read_text(encoding="utf-8")
    assert ".runtime-proof-next-actions" in STYLES.read_text(encoding="utf-8")
    assert ".runtime-recovery-proof-gate" in STYLES.read_text(encoding="utf-8")
    assert ".runtime-recovery-proof-grid" in STYLES.read_text(encoding="utf-8")
    assert ".agent-runtime-proof-receipt" in STYLES.read_text(encoding="utf-8")
    assert ".runtime-skill-proof-strip" in STYLES.read_text(encoding="utf-8")
    assert ".runtime-skill-proof-grid" in STYLES.read_text(encoding="utf-8")
    assert "supervisor_not_runtime_adapter" in fixtures
    assert "contract_ready_live_unverified" in fixtures
    assert "OpenClaw CLI available" in fixtures
    assert "Hermes CLI available" in fixtures
    assert "Run one bounded OpenClaw proving mission" in fixtures
    assert "Run a supervised synthetic lab transcript" in fixtures
    assert "provider_model_route" in fixtures
    assert "fixture_runtime_compartment_state" in fixtures
    assert "runtime-compartment-proof.v1" in fixtures
    assert "runtime-proof-gate-summary.v1" in fixtures
    assert "Runtime proof flight recorder" in runtime_contract
    assert "python scripts/runtime_lane_proof_harness.py --run-id lane-proof-fixture" in fixtures
    assert "runtime-proof-flight-recorder" in (ROOT / "scripts" / "runtime_proof_visual_smoke.py").read_text(encoding="utf-8")
    assert "runtime-proof-artifact-integrity" in (ROOT / "scripts" / "runtime_proof_visual_smoke.py").read_text(encoding="utf-8")


def test_builder_runtime_leaders_show_local_route_decision_rows() -> None:
    source = SHELL.read_text(encoding="utf-8")
    styles = STYLES.read_text(encoding="utf-8")
    fixtures = (ROOT / "desktop-ui" / "fixtures.js").read_text(encoding="utf-8")

    assert "routeDecisionRows" in source
    assert "benchmarkRouteRows" in (ROOT / "src" / "grant_agent" / "mission_control.py").read_text(encoding="utf-8")
    assert "_route_decision_summary" in (ROOT / "src" / "grant_agent" / "mission_control.py").read_text(encoding="utf-8")
    assert "Model and harness route decision scorecards" in source
    assert "routeDecisionGuide" in source
    assert "routeDecisionDisplayRows" in source
    assert "Benchmark route decision guide" in source
    assert "Decision guide" in source
    assert "Harness benchmark board" in source
    assert "benchmark-route-board" in source
    assert "Provider update flight check" in source
    assert "provider-flight-check" in source
    assert "Open provider ecosystem" in source
    assert "Source gate" in source
    assert "Default changes blocked" in source
    assert "provider-flight-check" in (ROOT / "scripts" / "provider_flight_visual_smoke.py").read_text(encoding="utf-8")
    benchmark_smoke = (ROOT / "scripts" / "benchmark_board_visual_smoke.py").read_text(encoding="utf-8")
    assert "benchmark-route-board" in benchmark_smoke
    assert "DECISION GUIDE" in benchmark_smoke
    assert "FLUXIO_BENCHMARK_BOARD_OUT_DIR" in benchmark_smoke
    assert "routeDecisionSummary" in source
    assert "highestRouteTier" in source
    assert "highestHardnessTier" in (ROOT / "src" / "grant_agent" / "mission_control.py").read_text(encoding="utf-8")
    assert "bestPracticalRouteId" in (ROOT / "src" / "grant_agent" / "mission_control.py").read_text(encoding="utf-8")
    assert "highestRouteWorkClass" in source
    assert "localProofRequiredCount" in source
    assert "needsLocalProof" in source
    assert "route-decision-card" in source
    assert "route-decision-meta" in source
    assert "route-decision-rules" in source
    assert "Source:" in source
    assert "Use:" in source
    assert "Do not:" in source
    assert "promotionStatus" in source
    assert "evidenceKind" in source
    assert "route-outcome-scorecard" in source
    assert "outcomeScorecard" in source
    assert "Harness:" in source
    assert ".route-decision-card" in styles
    assert ".route-decision-meta" in styles
    assert ".route-outcome-scorecard" in styles
    assert ".benchmark-route-board" in styles
    assert ".benchmark-route-grid" in styles
    assert ".benchmark-decision-guide" in styles
    assert ".route-decision-rules" in styles
    assert ".provider-flight-check" in styles
    assert ".provider-flight-grid" in styles
    assert ".provider-source-verification-gate" in styles
    assert ".provider-source-gate-grid" in styles
    assert "harnessId" in fixtures
    assert "routeDecisionSummary" in fixtures
    assert "routeDecisionGuide" in fixtures
    assert "benchmark-route-decision-guide.v1" in fixtures
    assert "benchmark_prior" in fixtures
    assert "usable_now" in fixtures
    assert "bestPracticalRouteId" in fixtures
    assert "sourceFreshness" in fixtures
    assert "sourceVerificationGate" in fixtures
    assert "provider-source-verification-gate.v1" in fixtures
    assert "https://ai-gateway.vercel.sh/v1/models" in fixtures
    assert "routeExposure" in fixtures
    assert "routeSmokeStatus" in fixtures
    assert "provider-catalog-refresh/v1" in fixtures
    assert "Benchmark F7" in fixtures
    assert "MiniMax-M3" in fixtures
    assert "JBHEAVEN benchmark fixture" in fixtures
    assert "High confidence" in fixtures
    assert "Needs proof" in fixtures
    assert "totalTokens" in fixtures
    assert "latestTestResult" in fixtures
    assert "Use for similar work" in fixtures
    assert "Needs local evidence" in fixtures


def test_fusion_migration_lanes_are_visible_in_builder_and_drawer() -> None:
    source = shell_surface_source()
    styles = STYLES.read_text(encoding="utf-8")
    fixtures = (ROOT / "web" / "src" / "fluxio" / "fusion" / "fusionFixtures.js").read_text(encoding="utf-8")
    fusion_panel = (ROOT / "web" / "src" / "fluxio" / "fusion" / "FusionWorkbenchPanel.jsx").read_text(encoding="utf-8")
    desktop_fixtures = (ROOT / "desktop-ui" / "fixtures.js").read_text(encoding="utf-8")

    assert "migrationLanes" in source
    assert "FusionWorkbenchPanel" in source
    assert 'import("./fusion/FusionWorkbenchPanel.jsx")' in source
    assert "Explainable Solantir signals" in fusion_panel
    assert "Fusion migration workbench" in fusion_panel
    assert "Mind Tower adapter truth" in fusion_panel
    assert "Next safe slice" in fusion_panel
    assert "fusion-phase-strip" in fusion_panel
    assert "fusion-adapter-panel" in fusion_panel
    assert "fusion-next-lane" in fusion_panel
    assert "promotionGates" in fusion_panel
    assert "adapterSummary" in fusion_panel
    assert "no order routing" in fusion_panel
    assert "fusion-migration-card" in fusion_panel
    assert "fusion-migration-list" in fusion_panel
    assert "fusion-signal-card" in fusion_panel
    assert ".fusion-phase-strip" in styles
    assert ".fusion-adapter-panel" in styles
    assert ".fusion-next-lane" in styles
    assert ".fusion-gate-list" in styles
    assert ".fusion-migration-card" in styles
    assert ".fusion-signal-card" in styles
    assert "FUSION_MIGRATION_LANES" in fixtures
    assert "FUSION_MIGRATION_PHASES" in fixtures
    assert "Promotion gates must show passed, needed, or blocked status" in fixtures
    assert "SOLANTIR_SIGNAL_SNAPSHOTS" in fixtures
    assert "no-trading-execution" in fixtures
    assert "Terminal and operator workbench shell" in fixtures
    assert "Synology monitoring and event records" in fixtures
    assert "Synthetic red-team proof lane" in fixtures
    assert "mindtower-readonly-sqlite-adapter" in desktop_fixtures
    assert "credentialValuesExposed: false" in desktop_fixtures
    assert "writeActions: 0" in desktop_fixtures


def test_redteam_proof_board_is_visible_and_synthetic_only() -> None:
    source = SHELL.read_text(encoding="utf-8")
    styles = STYLES.read_text(encoding="utf-8")
    component = (ROOT / "web" / "src" / "fluxio" / "redteam" / "RedTeamProofBoard.jsx").read_text(encoding="utf-8")
    fixtures = (ROOT / "web" / "src" / "fluxio" / "redteam" / "redTeamProofFixtures.js").read_text(encoding="utf-8")

    assert "RedTeamProofBoard" in source
    assert 'import("./redteam/RedTeamProofBoard.jsx")' in source
    assert "buildRedTeamProofBoard" in component
    assert "Controlled red-team proof" in component
    assert "redteam-proof-card" in component
    assert "Boundary score" in component
    assert "redteam-boundary-score" in component
    assert "redteam-promotion-gates" in component
    assert "redteam-taxonomy-map" in component
    assert "redteam-coverage-matrix" in component
    assert "redteam-probe-transcripts" in component
    assert "safe probe transcripts" in component
    assert "Promotion gate summary" in component
    assert "taxonomyRisk" in component
    assert "transcriptArtifactPath" in component
    assert "safe checks" in component
    assert ".redteam-proof-card" in styles
    assert ".redteam-boundary-score" in styles
    assert ".redteam-promotion-gates" in styles
    assert ".redteam-taxonomy-map" in styles
    assert ".redteam-coverage-row" in styles
    assert ".redteam-probe-row" in styles
    assert "RED_TEAM_PROOF_PACKETS" in fixtures
    assert "coverageMatrix" in fixtures
    assert "probeTranscripts" in fixtures
    assert "probe-prompt-injection-scope" in fixtures
    assert "safeProbeTaxonomy" in fixtures
    assert "promotionGateSummary" in fixtures
    assert "LLM01:2025 Prompt Injection" in fixtures
    assert "browserProof" in fixtures
    assert "fictional-targets-only" in fixtures
    assert "liveModelCalls: false" in fixtures
    assert "networkActivity: false" in fixtures
    assert "sample_transcript.json" in fixtures


def test_autonomy_guardrails_are_visible_in_builder() -> None:
    source = SHELL.read_text(encoding="utf-8")
    styles = STYLES.read_text(encoding="utf-8")

    assert "autonomyGuardrails" in source
    assert "Autonomy guardrails" in source
    assert "Continue until a real boundary" in source
    assert "Inspect before stopping" in source
    assert "Preserve user work" in source
    assert "Continue independent work" in source
    assert "Split reviewable PRs" in source
    assert "Attach real proof" in source
    assert "autonomy-guardrail-board" in source
    assert ".autonomy-guardrail-board" in styles
