from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "web" / "src" / "fluxio" / "FluxioShell.jsx"
WORKSPACE_MODEL = ROOT / "web" / "src" / "fluxio" / "workspaceModel.js"
STYLES = ROOT / "web" / "src" / "fluxio" / "styles.css"
MODEL = ROOT / "desktop-ui" / "missionControlModel.js"


def test_workbench_runtime_ops_surface_is_first_class() -> None:
    source = SHELL.read_text(encoding="utf-8")

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
    assert ".syntelos-review-workbench" in source


def test_workbench_state_exposes_runtime_update_and_auto_verify_counts() -> None:
    source = SHELL.read_text(encoding="utf-8")
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
    source = SHELL.read_text(encoding="utf-8")
    fixtures = (ROOT / "desktop-ui" / "fixtures.js").read_text(encoding="utf-8")

    assert "fusedRuntime" in source
    assert "Runtime lane" in source
    assert "Provider route" in source
    assert "modelProviderRoutes" in source
    assert "supervisor_not_runtime_adapter" in fixtures
    assert "provider_model_route" in fixtures


def test_builder_runtime_leaders_show_local_route_decision_rows() -> None:
    source = SHELL.read_text(encoding="utf-8")
    styles = STYLES.read_text(encoding="utf-8")
    fixtures = (ROOT / "desktop-ui" / "fixtures.js").read_text(encoding="utf-8")

    assert "routeDecisionRows" in source
    assert "Local route decision scorecards" in source
    assert "route-decision-card" in source
    assert "route-decision-meta" in source
    assert "route-outcome-scorecard" in source
    assert "outcomeScorecard" in source
    assert "Harness:" in source
    assert ".route-decision-card" in styles
    assert ".route-decision-meta" in styles
    assert ".route-outcome-scorecard" in styles
    assert "harnessId" in fixtures
    assert "High confidence" in fixtures
    assert "Needs proof" in fixtures
    assert "totalTokens" in fixtures
    assert "latestTestResult" in fixtures
    assert "Use for similar work" in fixtures
    assert "Needs local evidence" in fixtures


def test_fusion_migration_lanes_are_visible_in_builder_and_drawer() -> None:
    source = SHELL.read_text(encoding="utf-8")
    styles = STYLES.read_text(encoding="utf-8")
    fixtures = (ROOT / "web" / "src" / "fluxio" / "fusion" / "fusionFixtures.js").read_text(encoding="utf-8")

    assert "migrationLanes" in source
    assert "fusion-migration-card" in source
    assert "fusion-migration-list" in source
    assert ".fusion-migration-card" in styles
    assert "FUSION_MIGRATION_LANES" in fixtures
    assert "Terminal and operator workbench shell" in fixtures
    assert "Synology monitoring and event records" in fixtures
    assert "Synthetic red-team proof lane" in fixtures
