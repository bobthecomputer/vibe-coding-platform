from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _snippet_check(check_id: str, text: str, snippets: tuple[str, ...], details: str) -> dict:
    missing = [snippet for snippet in snippets if snippet not in text]
    return {
        "checkId": check_id,
        "passed": not missing,
        "details": details,
        "missingSnippets": missing,
    }


def verify_live_data_contract(root: Path, *, require_built_dist: bool = False) -> dict:
    root = root.resolve()
    shell_text = _read_text(root / "web" / "src" / "fluxio" / "FluxioShell.jsx")
    reference_text = _read_text(root / "web" / "src" / "fluxio" / "FluxioReferenceShell.jsx")
    model_text = _read_text(root / "desktop-ui" / "missionControlModel.js")
    package_text = _read_text(root / "package.json")
    nas_progress_text = _read_text(root / "docs" / "NAS_MISSION_PROGRESS_2026-05-28.md")
    system_gap_text = _read_text(root / "docs" / "SYSTEM_GAP_ANALYSIS.current.md")
    dist_text = "\n".join(
        _read_text(path)
        for path in (root / "web" / "dist" / "assets").glob("*.js")
    )

    checks = [
        _snippet_check(
            "live_mode_does_not_boot_from_cached_snapshot",
            shell_text,
            (
                "const initialPreviewMode = previewModeOptions.some(option => option.id === storedPreviewMode) ? storedPreviewMode : \"live\";",
                "snapshot: initialPreviewMode !== \"live\" && storedControlRoomSnapshot",
                "initialPreviewMode !== \"live\" && storedControlRoomSnapshot && typeof storedControlRoomSnapshot === \"object\"",
            ),
            "Live mode must wait for the backend instead of populating from localStorage snapshots.",
        ),
        _snippet_check(
            "fixtures_are_dev_preview_only",
            shell_text,
            (
                "function fixturesAllowedForSearch(searchParams)",
                "import.meta.env?.DEV && searchParams.get(\"preview-control\") === \"1\"",
                "allowFixtureMode && explicitFixture",
                "if (hasTauriBackend() || !allowFixtureMode)",
                "const allowFixturePreviewModes = fixturesAllowedForSearch(searchParams)",
            ),
            "Fixture mode must be restricted to explicit development preview-control mode.",
        ),
        _snippet_check(
            "summary_missions_feed_builder_rows",
            shell_text,
            (
                "const summaryMissions = Array.isArray(summarySnapshot.missions) ? summarySnapshot.missions : EMPTY_ARRAY;",
                "previewMode === \"live\"",
                "? summaryMissions",
                ": snapshotMissions.length > 0",
                "CONTROL_ROOM_SUMMARY_TIMEOUT_MS",
                "callBackendWithTimeout",
                "liveSummaryAfterSnapshotError",
                "summaryMode: \"bootstrap\"",
                "? \"control-room summary\"",
                "missionCount: Number(summarySnapshot.counts?.missions || missions.length || 0)",
            ),
            "Builder live mode must prefer the authenticated bootstrap control-room summary over older snapshot rows.",
        ),
        _snippet_check(
            "fast_bootstrap_summary_is_backend_supported",
            _read_text(root / "src" / "grant_agent" / "mission_control.py")
            + "\n"
            + _read_text(root / "src" / "grant_agent" / "web_backend.py"),
            (
                "def build_bootstrap_summary_snapshot(self) -> dict:",
                "\"summaryMode\": \"bootstrap\"",
                "\"source\": \"control_room_summary_bootstrap\"",
                "def _build_control_room_bootstrap_summary(self, root: Path) -> dict[str, Any]:",
                "summary_mode = str(payload.get(\"summaryMode\") or \"\").strip().lower()",
                "if bootstrap or summary_mode == \"bootstrap\"",
            ),
            "The web backend must expose a fast live bootstrap summary for first paint instead of waiting on the full audit snapshot.",
        ),
        _snippet_check(
            "live_backend_failures_are_not_silently_masked",
            shell_text,
            (
                "function callBackendWithTimeout(command, payload = undefined, timeoutMs = 4500)",
                "reject(new Error(`${command} timed out after ${timeoutMs}ms`))",
                "callBackend(command, payload, { throwOnError: true })",
                "pushToast(`Refresh failed: ${error}`, \"error\")",
                "summary:",
                ": null,",
                "pushToast(`Mission detail refresh failed: ${error}`, \"error\")",
            ),
            "Live backend reads must fail visibly instead of substituting empty arrays, false values, or cached mission data.",
        ),
        _snippet_check(
            "reference_shell_hides_fixture_rows_in_live_mode",
            reference_text,
            (
                "const isLiveBackend = liveDataStatus?.previewMode === \"live\";",
                "isLiveBackend ? [] : BUILDER_FLOWS",
                "isLiveBackend ? [] : CHANGED_FILES",
                "isLiveBackend ? [] : TOOL_EVENTS",
                "fixture flow cards are hidden in live mode",
                "no cached or sample sessions are shown",
                "The latest Model / OpenRuntime message is shown in the run receipt below",
                "No runtime operation rows loaded",
                "No NAS preview evidence loaded",
            ),
            "Live mode must show real rows or explicit unavailable states, never fixture operational data.",
        ),
        _snippet_check(
            "live_review_copy_is_truthful",
            model_text,
            (
                "No live review targets are available yet; the panel waits for current NAS mission evidence.",
                "previewMode === \"live\"",
                "fixtureOnly.push(\"Fixture-backed snapshot review\")",
            ),
            "Review copy must distinguish unavailable live evidence from fixture review data.",
        ),
        _snippet_check(
            "nas_evidence_docs_are_current",
            nas_progress_text + "\n" + system_gap_text,
            (
                "Source of truth: NAS `control-room-summary`, not local cached snapshots or UI fixture rows.",
                "Running missions: 2.",
                "Queued missions: 0.",
                "Blocked missions: 0.",
                "Runtime split: Hermes 14, OpenClaw 4.",
                "## NAS Live-State Evidence",
                "Treat this section as stronger evidence than stale local workspace rows",
            ),
            "Operator-facing docs must identify NAS live data as the source of truth.",
        ),
        _snippet_check(
            "package_exposes_live_data_verifier",
            package_text,
            (
                "\"verify:live-data\"",
                "python scripts/verify_live_data_contract.py",
                "scripts/verify_live_data_contract.py",
            ),
            "The live-data contract verifier must be available from package scripts and packaged files.",
        ),
    ]

    if require_built_dist:
        checks.append(
            _snippet_check(
                "built_dist_contains_live_only_copy",
                dist_text,
                (
                    "Live NAS mission readiness",
                    "no cached or sample sessions are shown",
                    "No runtime operation rows loaded",
                    "fixture flow cards are hidden in live mode",
                ),
                "The production bundle must contain the live-only UI contract text.",
            )
        )

    missing = [item["checkId"] for item in checks if not item["passed"]]
    return {
        "schema": "fluxio.live_data_contract.v1",
        "root": str(root),
        "ok": not missing,
        "checks": checks,
        "missing": missing,
        "nextAction": (
            "Live mode is protected against cached snapshots and fixture operational data."
            if not missing
            else "Fix the missing live-data contract checks, rebuild, and redeploy."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Fluxio live-mode data truthfulness contract.")
    parser.add_argument("--root", default=str(ROOT), help="Workspace root")
    parser.add_argument("--require-built-dist", action="store_true")
    args = parser.parse_args(argv)

    result = verify_live_data_contract(
        Path(args.root),
        require_built_dist=args.require_built_dist,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
