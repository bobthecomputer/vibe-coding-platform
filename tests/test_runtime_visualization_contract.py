from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "web" / "src" / "fluxio" / "FluxioShell.jsx"
WORKSPACE_MODEL = ROOT / "web" / "src" / "fluxio" / "workspaceModel.js"
STYLES = ROOT / "web" / "src" / "fluxio" / "styles.css"
MODEL = ROOT / "desktop-ui" / "missionControlModel.js"


def test_removed_reference_runtime_panel_stays_deleted() -> None:
    assert not (ROOT / "web" / "src" / "fluxio" / "RuntimeOperationsPanel.jsx").exists()
    assert not (ROOT / "web" / "src" / "fluxio" / "FluxioReferenceShell.jsx").exists()


def test_current_shell_keeps_runtime_state_first_class() -> None:
    source = SHELL.read_text(encoding="utf-8")
    model_source = WORKSPACE_MODEL.read_text(encoding="utf-8")

    assert "runtimeOps" in source
    assert "deriveRuntimeOperations(serviceStudio)" in source
    assert "export function deriveRuntimeOperations" in model_source
    assert "autoVerifyCount" in model_source
    assert "updateActionCount" in model_source
    assert "updateServices" in model_source
    assert "primaryRuntimeServices" in source
    assert "OpenClaw live connection" in source
    assert "OpenCodeGo" in source


def test_current_styles_do_not_keep_removed_reference_runtime_grid() -> None:
    source = STYLES.read_text(encoding="utf-8")

    assert ".reference-runtime-service-grid" not in source
    assert ".reference-shell" not in source
    assert ".fluxio-shell" in source
    assert ".agent-control-grid" in source


def test_service_model_preserves_auto_run_verify_for_runtime_actions() -> None:
    source = MODEL.read_text(encoding="utf-8")

    assert "autoRunVerify: Boolean(action.autoRunVerify)" in source
    assert "followUp: action.followUp" in source
