from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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
