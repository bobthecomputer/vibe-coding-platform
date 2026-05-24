from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "web" / "src" / "fluxio" / "FluxioShell.jsx"
REFERENCE_SHELL = ROOT / "web" / "src" / "fluxio" / "FluxioReferenceShell.jsx"
RUNTIME_PANEL = ROOT / "web" / "src" / "fluxio" / "RuntimeOperationsPanel.jsx"
WORKSPACE_MODEL = ROOT / "web" / "src" / "fluxio" / "workspaceModel.js"
STYLES = ROOT / "web" / "src" / "fluxio" / "styles.css"
MODEL = ROOT / "desktop-ui" / "missionControlModel.js"


def test_workbench_runtime_ops_surface_is_first_class() -> None:
    source = RUNTIME_PANEL.read_text(encoding="utf-8")

    assert "Runtime operations" in source
    assert "Automatic verify" in source
    assert "Update actions" in source
    assert "reference-runtime-service-grid" in source


def test_runtime_ops_actions_execute_through_settings_service_action_path() -> None:
    source = RUNTIME_PANEL.read_text(encoding="utf-8")

    assert 'onRequestAction?.("settings:run-action", { action })' in source


def test_workbench_uses_extracted_runtime_operations_panel() -> None:
    source = REFERENCE_SHELL.read_text(encoding="utf-8")

    assert 'import { RuntimeOperationsPanel } from "./RuntimeOperationsPanel.jsx";' in source
    assert "<RuntimeOperationsPanel" in source


def test_workbench_runtime_panel_is_not_trapped_in_top_grid_row() -> None:
    source = STYLES.read_text(encoding="utf-8")

    assert ".reference-main:not(.with-flow-sidebar)" in source
    assert ".reference-main:not(.with-flow-sidebar) > .reference-main-body" in source
    assert ".reference-shell.surface-workbench .reference-main" in source
    assert "grid-template-rows: minmax(0, 1fr);" in source
    assert ".reference-shell.surface-workbench .reference-runtime-service-grid" in source


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
