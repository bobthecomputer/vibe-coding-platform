from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_MODEL = ROOT / "web" / "src" / "fluxio" / "workspaceModel.js"


def test_workspace_model_promotes_rule_sets_as_core_surface() -> None:
    source = WORKSPACE_MODEL.read_text(encoding="utf-8")

    assert '{ id: "rule-sets", label: "Rule Sets", section: "workspace" }' in source
    assert '{ id: "voice", label: "Voice", section: "workspace" }' in source
    assert '{ id: "settings", label: "Settings", section: "global" }' in source


def test_workspace_model_keeps_permission_modes_explicit() -> None:
    source = WORKSPACE_MODEL.read_text(encoding="utf-8")

    for mode in [
        "always_ask",
        "workspace_safe",
        "review_only",
        "autonomous_scoped",
    ]:
        assert f'value: "{mode}"' in source


def test_workspace_model_defines_shared_route_model_controls() -> None:
    source = WORKSPACE_MODEL.read_text(encoding="utf-8")

    for token in [
        "MODEL_PROVIDER_OPTIONS",
        "MODEL_EFFORT_OPTIONS",
        "EXECUTION_TARGET_OPTIONS",
        "ROUTE_ROLE_OPTIONS",
    ]:
        assert f"export const {token}" in source

    assert '{ value: "opencode", label: "OpenCodeGo" }' in source

