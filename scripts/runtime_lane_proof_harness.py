from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import asdict, fields
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from grant_agent.models import (  # noqa: E402
    DelegatedRuntimeSession,
    Mission,
    ModelRouteConfig,
    WorkspaceProfile,
)
from grant_agent.runtimes import runtime_adapter_map  # noqa: E402
from grant_agent.skills import SkillRegistry  # noqa: E402

DEFAULT_OUTPUT_ROOT = ROOT / "artifacts" / "runtime-lanes"


LANE_ROUTES = {
    "openclaw": ModelRouteConfig(
        role="executor",
        provider="openai",
        model="gpt-5.4-mini",
        effort="medium",
        explanation="OpenClaw owns gateway-style execution, remote approvals, and JSON session output.",
    ),
    "hermes": ModelRouteConfig(
        role="executor",
        provider="minimax",
        model="MiniMax-M3",
        effort="high",
        explanation="Hermes owns long-running agent loops, scheduling, memory, and skill reuse.",
    ),
}

LANE_SKILLS = {
    "openclaw": "jbheaven_godmode_lab",
    "hermes": "jbheaven_godmode_lab",
}

LANE_SCORECARD_CONTEXT = {
    "openclaw": {
        "budgetClass": "balanced",
        "contextWindowTokens": 400000,
        "expectedWallTimeBand": "10_60m",
        "tokenBudgetBand": "balanced",
        "costBand": "balanced",
        "retryBudget": 1,
        "routeTier": "F5",
        "recommended": True,
        "executionTarget": "wsl2",
        "handoffMode": "delegated",
        "strengths": [
            "Structured launch contract",
            "Approval-aware handoff",
            "JSON session output",
        ],
        "risks": [
            "Provider auth must be healthy",
            "Not a red-team scorer by itself",
        ],
        "prerequisites": [
            "OpenClaw installed",
            "OpenAI provider route configured",
            "Fluxio proof artifact path writable",
        ],
        "scaffoldingSensitivity": "medium",
        "recoverySupport": "restart_safe",
        "safeRedTeamApplicable": False,
    },
    "hermes": {
        "budgetClass": "premium",
        "contextWindowTokens": 1000000,
        "expectedWallTimeBand": "1_4h",
        "tokenBudgetBand": "high",
        "costBand": "high",
        "retryBudget": 2,
        "routeTier": "F7",
        "recommended": False,
        "executionTarget": "nas",
        "handoffMode": "delegated",
        "strengths": [
            "Long-running loop supervision",
            "Skill reuse",
            "Transcript-oriented proof",
        ],
        "risks": [
            "Requires strict target boundaries",
            "Higher setup and provider cost",
        ],
        "prerequisites": [
            "Hermes installed",
            "MiniMax provider route configured",
            "Synthetic or authorized target scope recorded",
        ],
        "scaffoldingSensitivity": "high",
        "recoverySupport": "checkpointed",
        "safeRedTeamApplicable": True,
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _mission_for_lane(runtime_id: str, route: ModelRouteConfig) -> Mission:
    return Mission(
        mission_id=f"mission_{runtime_id}_lane_proof",
        workspace_id="workspace_runtime_lane_proof",
        runtime_id=runtime_id,
        objective=(
            "Prove runtime route metadata and skill visibility only. "
            "Do not call a model, edit files, or perform live red-team actions."
        ),
        success_checks=["route contract recorded", "skill visible", "no live model call"],
        route_configs=[route],
    )


def _workspace(runtime_id: str) -> WorkspaceProfile:
    return WorkspaceProfile(
        workspace_id="workspace_runtime_lane_proof",
        name="Runtime Lane Proof",
        root_path=str(ROOT),
        default_runtime=runtime_id,
        workspace_type="python",
    )


def _lane_payload(runtime_id: str) -> dict:
    adapters = runtime_adapter_map()
    if runtime_id not in adapters:
        raise ValueError(f"Runtime adapter {runtime_id!r} is not registered.")
    adapter = adapters[runtime_id]
    route = LANE_ROUTES[runtime_id]
    mission = _mission_for_lane(runtime_id, route)
    workspace = _workspace(runtime_id)
    with mock.patch("grant_agent.runtimes.hermes.shutil.which", return_value="hermes"):
        launch = adapter.start_mission(mission, workspace)
    capabilities = [asdict(item) for item in adapter.list_capabilities()]
    return {
        "runtimeId": runtime_id,
        "label": adapter.label,
        "skill": LANE_SKILLS[runtime_id],
        "capabilities": capabilities,
        "launchCommand": launch["launch_command"],
        "routeContract": launch["route_contract"],
        "routeSummary": launch["route_summary"],
        "proofMeaning": route.explanation,
    }


def _skill_visibility() -> dict:
    registry = SkillRegistry(ROOT / "config" / "skills.json")
    catalog_names = {skill.name for skill in registry.skills}
    retrieved = registry.retrieve(
        "JBHEAVEN Hermes OpenClaw runtime lane proof skill execution visibility",
        top_k=6,
    )
    required = ["jbheaven_godmode_lab", "hermes_skill_packager", "runtime_loop_supervisor"]
    return {
        "requiredSkills": {
            name: name in catalog_names
            for name in required
        },
        "retrievedSkills": [skill.name for skill in retrieved],
        "catalogSize": len(registry.skills),
    }


def _fused_runtime_payload(lanes: list[dict]) -> dict:
    session_fields = {field.name for field in fields(DelegatedRuntimeSession)}
    required_fields = [
        "runtime_id",
        "launch_command",
        "events_path",
        "log_path",
        "decision_path",
        "latest_events",
        "pending_approval",
        "heartbeat_status",
        "target_phase",
        "target_role",
        "target_provider",
        "target_model",
        "changed_files",
    ]
    return {
        "runtimeId": "fluxio-fused-supervisor",
        "role": "supervisor_not_runtime_adapter",
        "runtimeAdapterAdded": False,
        "registeredRuntimeAdapters": [lane["runtimeId"] for lane in lanes],
        "normalizes": [
            "route_contracts",
            "structured_events",
            "approval_state",
            "logs",
            "heartbeats",
            "changed_files",
        ],
        "delegatedSessionFieldsPresent": {
            name: name in session_fields
            for name in required_fields
        },
    }


def _provider_family(provider: str) -> str:
    if provider in {"openai-codex", "openai_codex"}:
        return "openai"
    return provider


def _scorecard_candidate(lane: dict, artifact_paths: dict) -> dict:
    runtime_id = lane["runtimeId"]
    route = lane["routeContract"]
    context = LANE_SCORECARD_CONTEXT[runtime_id]
    safe_red_team_applicable = bool(context["safeRedTeamApplicable"])
    raw_provider = route.get("provider", "")
    provider = _provider_family(raw_provider)
    model = route.get("model", "")
    canonical_model_id = route.get("canonical_model_id") or f"{raw_provider or provider}/{model}"
    return {
        "candidateId": f"fluxio-{runtime_id}-{provider}-runtime-lane-proof",
        "label": f"Fluxio supervisor with {lane['label']} {provider.title()} route",
        "modelId": canonical_model_id,
        "harnessId": "fluxio_hybrid",
        "providerRoute": {
            "provider": provider,
            "model": model,
            "role": route.get("role", "executor"),
            "effort": route.get("effort", "medium"),
            "budgetClass": context["budgetClass"],
            "authStatus": "unknown",
            "routeReason": lane["proofMeaning"],
        },
        "runtimeLane": {
            "laneId": runtime_id,
            "supervisorHarness": "fluxio_hybrid",
            "executionTarget": context["executionTarget"],
            "runtimeAdapterAdded": False,
            "handoffMode": context["handoffMode"],
        },
        "harnessQualities": {
            "strengths": context["strengths"],
            "risks": context["risks"],
            "prerequisites": context["prerequisites"],
            "scaffoldingSensitivity": context["scaffoldingSensitivity"],
            "recoverySupport": context["recoverySupport"],
        },
        "verifierProof": {
            "verifierType": "deterministic_test",
            "independence": "deterministic",
            "requiredCommands": [
                "python -m pytest tests/test_runtime_lane_proof_harness.py",
            ],
            "proofArtifacts": [
                artifact_paths["proof"],
                artifact_paths["markdown"],
                artifact_paths["route_scorecard"],
            ],
            "acceptanceGate": "Route metadata, runtime lane, and deterministic proof artifacts must exist before recommending this route.",
        },
        "speedCostContext": {
            "contextWindowTokens": context["contextWindowTokens"],
            "expectedWallTimeBand": context["expectedWallTimeBand"],
            "tokenBudgetBand": context["tokenBudgetBand"],
            "costBand": context["costBand"],
            "retryBudget": context["retryBudget"],
        },
        "safeRedTeam": {
            "applicable": safe_red_team_applicable,
            "scope": "synthetic_lab" if safe_red_team_applicable else "not_applicable",
            "scorecard": {
                "containment": 5 if safe_red_team_applicable else 0,
                "harmfulInstructionAvoidance": 5 if safe_red_team_applicable else 0,
                "transcriptProof": 3 if safe_red_team_applicable else 0,
                "boundaryRespect": 5 if safe_red_team_applicable else 0,
                "rubricNotes": (
                    "Only synthetic lab prompts or explicitly authorized private targets qualify for this lane."
                    if safe_red_team_applicable
                    else "Not selected for red-team scoring; use this lane for bounded execution proof."
                ),
            },
            "escalationRequired": safe_red_team_applicable,
        },
        "decision": {
            "recommended": context["recommended"],
            "routeTier": context["routeTier"],
            "useWhen": [
                "The mission needs runtime lane visibility and deterministic proof artifacts.",
                lane["proofMeaning"],
            ],
            "doNotUseWhen": [
                "Provider auth is missing or the route contract cannot be written.",
                "The task can be completed by a deterministic local script without a model.",
            ],
            "downgradeTriggers": [
                "The work is read-only summarization.",
                "The verifier can complete the proof without a delegated runtime lane.",
            ],
            "upgradeTriggers": [
                "Independent verifier rejects proof quality.",
                "The task crosses into long-horizon or boundary-sensitive work.",
            ],
        },
    }


def _route_scorecard_payload(
    *,
    run_id: str,
    created_at: str,
    lanes: list[dict],
    artifact_paths: dict,
) -> dict:
    board_id = run_id if run_id.startswith("runtime-lane-proof") else f"runtime-lane-proof-{run_id}"
    return {
        "schemaVersion": "benchmark-board-route-scorecard/v1",
        "boardId": board_id,
        "decisionQuestion": "Which provider route plus runtime lane should own this Fluxio mission?",
        "updatedAt": created_at,
        "candidates": [
            _scorecard_candidate(lane, artifact_paths)
            for lane in lanes
        ],
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _markdown(payload: dict) -> str:
    lines = [
        "# Hermes/OpenClaw Runtime Lane Proof",
        "",
        f"Run id: `{payload['runId']}`",
        f"Mode: `{payload['mode']}`",
        "",
        "This proof records route contracts, launch commands, skill visibility, and fused supervision fields. It does not call live models and does not add a runtime adapter.",
        "",
        "## Runtime Lanes",
        "",
        "| Lane | Route | Skill | Differentiator |",
        "| --- | --- | --- | --- |",
    ]
    for lane in payload["lanes"]:
        lines.append(
            f"| `{lane['runtimeId']}` | `{lane['routeSummary']}` | `{lane['skill']}` | {lane['proofMeaning']} |"
        )
    lines.extend(
        [
            "",
            "## Fused Supervision",
            "",
            f"- Role: `{payload['fusedRuntime']['role']}`",
            f"- Runtime adapter added: `{payload['fusedRuntime']['runtimeAdapterAdded']}`",
            f"- Registered adapters: `{', '.join(payload['fusedRuntime']['registeredRuntimeAdapters'])}`",
            "",
            "## Artifacts",
            "",
        ]
    )
    for label, path in payload["artifactPaths"].items():
        lines.append(f"- {label}: `{path}`")
    lines.append("")
    return "\n".join(lines)


def build_proof(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    run_id: str | None = None,
) -> dict:
    stable_run_id = run_id or f"runtime-lane-proof-{slug_timestamp()}-{uuid.uuid4().hex[:6]}"
    run_dir = output_root / stable_run_id
    artifact_paths = {
        "proof": str(run_dir / "runtime_lane_proof.json"),
        "markdown": str(run_dir / "RUNTIME_LANE_PROOF.md"),
        "route_scorecard": str(run_dir / "route_scorecard.json"),
        "artifact_index": str(run_dir / "artifacts_index.json"),
    }
    lanes = [_lane_payload("openclaw"), _lane_payload("hermes")]
    created_at = utc_now()
    payload = {
        "runId": stable_run_id,
        "mode": "deterministic-no-live-runtime-call",
        "createdAt": created_at,
        "lanes": lanes,
        "fusedRuntime": _fused_runtime_payload(lanes),
        "skillVisibility": _skill_visibility(),
        "safetyContract": {
            "liveModelCalls": False,
            "realTargets": False,
            "harmfulInstructions": False,
            "runtimeAdapterAdded": False,
            "openCodeGoRuntimeAdded": False,
        },
        "artifactPaths": artifact_paths,
    }
    route_scorecard = _route_scorecard_payload(
        run_id=stable_run_id,
        created_at=created_at,
        lanes=lanes,
        artifact_paths=artifact_paths,
    )
    artifact_index = {
        "runId": stable_run_id,
        "root": str(run_dir),
        "paths": artifact_paths,
    }
    _write_json(Path(artifact_paths["proof"]), payload)
    _write_json(Path(artifact_paths["route_scorecard"]), route_scorecard)
    Path(artifact_paths["markdown"]).write_text(_markdown(payload), encoding="utf-8")
    _write_json(Path(artifact_paths["artifact_index"]), artifact_index)
    payload["routeScorecard"] = route_scorecard
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create deterministic Hermes/OpenClaw runtime lane proof artifacts."
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args(argv)

    payload = build_proof(
        output_root=args.output_root,
        run_id=args.run_id or None,
    )
    print(json.dumps({"runId": payload["runId"], "artifactPaths": payload["artifactPaths"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
