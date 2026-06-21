from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grant_agent.mission_control import build_harness_lab_snapshot

SCHEMA_PATH = ROOT / "docs" / "benchmark-board" / "route_scorecard_schema.json"
FIXTURE_PATH = (
    ROOT
    / "docs"
    / "benchmark-board"
    / "fixtures"
    / "jbheaven_route_scorecard.fixture.json"
)


REQUIRED_CANDIDATE_BLOCKS = {
    "providerRoute",
    "runtimeLane",
    "harnessQualities",
    "verifierProof",
    "speedCostContext",
    "safeRedTeam",
    "decision",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_benchmark_board_schema_names_practical_route_decision_blocks() -> None:
    schema = load_json(SCHEMA_PATH)
    candidate_required = set(schema["$defs"]["candidate"]["required"])

    assert schema["properties"]["schemaVersion"]["const"] == "benchmark-board-route-scorecard/v1"
    assert REQUIRED_CANDIDATE_BLOCKS.issubset(candidate_required)

    for block in REQUIRED_CANDIDATE_BLOCKS:
        assert block in schema["$defs"]["candidate"]["properties"]


def test_jbheaven_fixture_keeps_provider_route_separate_from_runtime_lane() -> None:
    fixture = load_json(FIXTURE_PATH)

    assert fixture["schemaVersion"] == "benchmark-board-route-scorecard/v1"
    assert fixture["candidates"]

    for candidate in fixture["candidates"]:
        assert REQUIRED_CANDIDATE_BLOCKS.issubset(candidate)
        assert candidate["providerRoute"]["provider"] != candidate["runtimeLane"]["laneId"]
        assert candidate["runtimeLane"]["supervisorHarness"] == candidate["harnessId"]
        assert candidate["runtimeLane"]["runtimeAdapterAdded"] is False


def test_jbheaven_fixture_requires_verifier_speed_cost_context_and_redteam_rubric() -> None:
    fixture = load_json(FIXTURE_PATH)
    recommended = [item for item in fixture["candidates"] if item["decision"]["recommended"]]
    redteam_candidates = [item for item in fixture["candidates"] if item["safeRedTeam"]["applicable"]]

    assert len(recommended) == 1
    assert redteam_candidates

    for candidate in fixture["candidates"]:
        proof = candidate["verifierProof"]
        speed = candidate["speedCostContext"]
        redteam = candidate["safeRedTeam"]

        assert proof["proofArtifacts"]
        assert proof["acceptanceGate"]
        assert speed["contextWindowTokens"] > 0
        assert speed["expectedWallTimeBand"] in {"sub_10m", "10_60m", "1_4h", "4h_plus", "unknown"}
        assert speed["costBand"] in {"low", "balanced", "high", "unknown"}

        if candidate["decision"]["routeTier"] in {"F6", "F7", "F8"}:
            assert proof["independence"] in {"independent_route", "deterministic", "human_review"}

        if redteam["applicable"]:
            assert redteam["scope"] in {"synthetic_lab", "authorized_private_target"}
            assert redteam["escalationRequired"] is True

        for score_name, score in redteam["scorecard"].items():
            if score_name == "rubricNotes":
                assert isinstance(score, str)
            else:
                assert 0 <= score <= 5


def test_harness_lab_uses_fixture_benchmark_candidates_when_local_runs_are_missing() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        snapshot = build_harness_lab_snapshot(Path(temp_dir))

    rows = snapshot["routeDecisionRows"]
    benchmark_rows = snapshot["benchmarkRouteRows"]

    assert snapshot["routeDecisionSummary"]["localCount"] == 0
    assert snapshot["routeDecisionSummary"]["benchmarkCount"] >= 2
    assert snapshot["routeDecisionSummary"]["candidateCount"] >= 2
    assert snapshot["routeDecisionSummary"]["benchmarkShownCount"] >= 1
    assert snapshot["routeDecisionSummary"]["proofGapCount"] >= 1
    assert snapshot["routeDecisionSummary"]["localProofRequiredCount"] >= 1
    assert snapshot["routeDecisionSummary"]["redTeamCandidateCount"] >= 1
    assert snapshot["routeDecisionSummary"]["highestRouteTier"].startswith("F")
    assert snapshot["routeDecisionSummary"]["highestRouteWorkClass"] in {
        "normal_repo_execution",
        "controlled_red_team_lab",
        "hard_or_frontier_mission",
        "cheap_or_deterministic_work",
        "unclassified_route",
    }
    assert snapshot["routeDecisionSummary"]["highestRouteCostBand"] in {"low", "balanced", "high", "unknown"}
    assert snapshot["routeDecisionSummary"]["needsLocalProof"] is True
    assert snapshot["routeDecisionSummary"]["highestHardnessTier"].startswith("F")
    assert snapshot["routeDecisionSummary"]["highestHardnessIsOnlyPrior"] is True
    assert snapshot["routeDecisionSummary"]["bestPracticalDecision"] in {"needs_evidence", "use", "watch"}
    assert snapshot["routeDecisionSummary"]["bestPracticalEvidenceKind"] in {"none", "local_proof"}
    assert snapshot["routeDecisionSummary"]["bestPracticalPromotionStatus"] in {
        "needs_local_proof",
        "blocked_by_proof_gap",
        "usable_now",
    }
    assert snapshot["routeDecisionGuide"]["schemaVersion"] == "benchmark-route-decision-guide.v1"
    assert snapshot["routeDecisionGuide"]["sourceMode"] in {"benchmark_prior", "local_proof", "no_candidate"}
    assert snapshot["routeDecisionGuide"]["nextAction"]
    assert rows
    assert benchmark_rows
    assert rows[0]["benchmarkCandidate"] is True
    assert rows[0]["evidenceKind"] == "benchmark_prior"
    assert rows[0]["promotionStatus"] in {"blocked_by_proof_gap", "needs_local_proof"}
    assert rows[0]["decisionRecommendation"]["localProofRequired"] is True
    assert rows[0]["sourceLabel"] == "JBHEAVEN benchmark fixture"
    assert rows[0]["provider"] != rows[0]["runtimeId"]
    assert rows[0]["outcomeScorecard"]["latestTestResult"] == "benchmark"
    assert "local proof run" in rows[0]["proofGaps"][0]
    assert rows[0]["routeTier"].startswith("F")
    assert rows[0]["workClass"] in {
        "normal_repo_execution",
        "controlled_red_team_lab",
        "hard_or_frontier_mission",
        "cheap_or_deterministic_work",
        "unclassified_route",
    }
    assert rows[0]["localProofRequired"] is True
    assert rows[0]["expectedWallTimeBand"] in {"sub_10m", "10_60m", "1_4h", "4h_plus", "unknown"}


def test_harness_lab_loads_generated_runtime_lane_scorecard_artifacts() -> None:
    fixture = load_json(FIXTURE_PATH)
    fixture["boardId"] = "runtime-lane-proof-test-artifact"
    fixture["candidates"] = fixture["candidates"][:1]
    fixture["candidates"][0]["candidateId"] = "artifact-openclaw-candidate"

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        artifact_dir = root / "artifacts" / "runtime-lanes" / "artifact-proof"
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "route_scorecard.json").write_text(
            json.dumps(fixture, indent=2),
            encoding="utf-8",
        )

        snapshot = build_harness_lab_snapshot(root)

    artifact_rows = [
        item
        for item in snapshot["benchmarkRouteRows"]
        if item["source"] == "benchmark_artifact"
    ]

    assert artifact_rows
    assert artifact_rows[0]["benchmarkBoardId"] == "runtime-lane-proof-test-artifact"
    assert artifact_rows[0]["candidateId"] == "artifact-openclaw-candidate"
    assert artifact_rows[0]["evidenceKind"] == "generated_contract_proof"
    assert artifact_rows[0]["promotionStatus"] in {"blocked_by_proof_gap", "needs_local_proof"}
    assert artifact_rows[0]["sourceLabel"] == "Generated benchmark artifact"
    assert artifact_rows[0]["useWhen"]
    assert artifact_rows[0]["doNotUseWhen"]
    assert "contextWindowTokens" in artifact_rows[0]


def test_harness_lab_loads_safe_redteam_route_scorecard_artifacts() -> None:
    artifact = (
        ROOT
        / "artifacts"
        / "red-team"
        / "worker-f-jbheaven-safe-scenario-20260621"
        / "route_scorecard.json"
    )
    scorecard = load_json(artifact)

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        redteam_dir = root / "artifacts" / "red-team" / "worker-f-jbheaven-safe-scenario-20260621"
        redteam_dir.mkdir(parents=True)
        (redteam_dir / "route_scorecard.json").write_text(
            json.dumps(scorecard, indent=2),
            encoding="utf-8",
        )
        runtime_fixture = load_json(FIXTURE_PATH)
        runtime_fixture["candidates"] = runtime_fixture["candidates"][:1]
        for index in range(8):
            runtime_fixture["boardId"] = f"runtime-crowd-{index}"
            runtime_fixture["candidates"][0]["candidateId"] = f"runtime-crowd-candidate-{index}"
            runtime_dir = root / "artifacts" / "runtime-lanes" / f"crowd-{index}"
            runtime_dir.mkdir(parents=True)
            (runtime_dir / "route_scorecard.json").write_text(
                json.dumps(runtime_fixture, indent=2),
                encoding="utf-8",
            )

        snapshot = build_harness_lab_snapshot(root)

    redteam_rows = [
        item
        for item in snapshot["benchmarkRouteRows"]
        if item["source"] == "redteam_artifact"
    ]

    assert redteam_rows
    row = redteam_rows[0]
    assert row["sourceLabel"] == "JBH-EAVEN safe red-team artifact"
    assert row["benchmarkBoardId"] == "worker-f-jbheaven-safe-scenario-20260621"
    assert row["candidateId"] == "jbh-eaven-hermes-opencodego-safe-lab-artifact"
    assert row["runtimeId"] == "hermes"
    assert row["provider"] == "opencodego-compatible-lab-route"
    assert row["redTeamApplicable"] is True
    assert row["redTeamScope"] == "synthetic_lab"
    assert row["localProofRequired"] is True
    assert "dry-run artifact" in " ".join(row["doNotUseWhen"]).lower()
    assert snapshot["routeDecisionSummary"]["redTeamCandidateCount"] >= 1
