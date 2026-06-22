from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.pr_stack_health import build_pr_stack_health, build_pr_stack_landing_readiness


ROOT = Path(__file__).resolve().parents[1]


def pr(number: int, head: str, base: str) -> dict[str, object]:
    return {
        "number": number,
        "title": f"PR {number}",
        "headRefName": head,
        "baseRefName": base,
        "isDraft": number % 2 == 0,
        "url": f"https://example.test/pull/{number}",
    }


def pr_with_checks(
    number: int,
    head: str,
    base: str,
    *,
    draft: bool = False,
    merge_state: str = "CLEAN",
    release_conclusion: str = "SUCCESS",
) -> dict[str, object]:
    row = pr(number, head, base)
    row.update(
        {
            "isDraft": draft,
            "mergeStateStatus": merge_state,
            "reviewDecision": "",
            "statusCheckRollup": [
                {
                    "__typename": "CheckRun",
                    "name": "release-proof",
                    "workflowName": "Fluxio Release Proof",
                    "status": "COMPLETED",
                    "conclusion": release_conclusion,
                }
            ],
        }
    )
    return row


class PrStackHealthTests(unittest.TestCase):
    def test_detects_long_stacked_pr_chain(self) -> None:
        rows = [
            pr(6, "codex/feature-6", "codex/feature-5"),
            pr(5, "codex/feature-5", "codex/feature-4"),
            pr(4, "codex/feature-4", "codex/feature-3"),
            pr(3, "codex/feature-3", "codex/feature-2"),
            pr(2, "codex/feature-2", "codex/feature-1"),
            pr(1, "codex/feature-1", "master"),
        ]

        report = build_pr_stack_health(rows, max_chain=3)

        self.assertFalse(report["ok"])
        self.assertTrue(report["staleStackDetected"])
        self.assertEqual(report["openPrCount"], 6)
        self.assertEqual(report["longestChainLength"], 6)
        self.assertEqual(report["longestChainPrs"], [6, 5, 4, 3, 2, 1])
        self.assertIn("Stop opening stacked PRs", report["recommendation"])

    def test_allows_flat_reviewable_prs(self) -> None:
        rows = [
            pr(12, "codex/ui-polish", "master"),
            pr(11, "codex/runtime-proof", "master"),
            pr(10, "codex/skills-contract", "master"),
        ]

        report = build_pr_stack_health(rows, max_chain=3)

        self.assertTrue(report["ok"])
        self.assertFalse(report["staleStackDetected"])
        self.assertEqual(report["openPrCount"], 3)
        self.assertEqual(report["longestChainLength"], 1)
        self.assertEqual(report["chainCount"], 3)

    def test_landing_readiness_blocks_at_oldest_failed_pr(self) -> None:
        rows = [
            pr_with_checks(131, "codex/131-automation-overlap-status", "codex/130-in-app-update-cue"),
            pr_with_checks(130, "codex/130-in-app-update-cue", "codex/119-image-playground-mission1"),
            pr_with_checks(
                119,
                "codex/119-image-playground-mission1",
                "master",
                merge_state="UNSTABLE",
                release_conclusion="FAILURE",
            ),
        ]

        report = build_pr_stack_landing_readiness(rows, max_chain=10)

        self.assertFalse(report["ok"])
        self.assertEqual(report["schema"], "fluxio.pr_stack_landing_readiness.v1")
        self.assertEqual(report["status"], "blocked_at_landing_frontier")
        self.assertEqual(report["landingFrontier"]["number"], 119)
        self.assertEqual(report["landingSequence"][0]["number"], 119)
        self.assertIn("merge_state:unstable", report["landingFrontier"]["blockers"])
        self.assertIn("release_proof:failed", report["landingFrontier"]["blockers"])
        self.assertIn("Fix PR119", report["nextAction"])
        self.assertEqual(report["primaryRuntimeLane"], "hermes")
        self.assertIn("openclaw", report["fallbackRuntimeLanes"])

    def test_landing_readiness_counts_drafts_and_green_checks(self) -> None:
        rows = [
            pr_with_checks(3, "codex/feature-3", "codex/feature-2"),
            pr_with_checks(2, "codex/feature-2", "codex/feature-1", draft=True),
            pr_with_checks(1, "codex/feature-1", "master"),
        ]

        report = build_pr_stack_landing_readiness(rows, max_chain=5)

        self.assertFalse(report["ok"])
        self.assertEqual(report["landingFrontier"]["number"], 2)
        self.assertIn("draft", report["landingFrontier"]["blockers"])
        self.assertEqual(report["summary"]["draftCount"], 1)
        self.assertEqual(report["summary"]["releaseProofPassedCount"], 3)

    def test_landing_readiness_no_open_prs_returns_completion_handoff(self) -> None:
        report = build_pr_stack_landing_readiness([], max_chain=5)

        self.assertTrue(report["ok"])
        self.assertEqual(report["status"], "no_open_prs")
        self.assertEqual(report["stack"]["openPrCount"], 0)
        self.assertEqual(report["landingSequence"], [])
        self.assertEqual(report["continuationPolicy"]["state"], "completed")
        self.assertFalse(report["continuationPolicy"]["shouldContinueStackWork"])
        self.assertEqual(report["continuationPolicy"]["automationDecision"], "skip_completed_pr_stack")
        self.assertIn("Start a fresh mission", report["continuationPolicy"]["nextCompartmentAction"])

    def test_operator_doc_matches_scripts_and_workflow(self) -> None:
        doc = (ROOT / "docs" / "PR_STACK_HEALTH.md").read_text(encoding="utf-8")
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        workflow = (ROOT / ".github" / "workflows" / "pr-stack-health.yml").read_text(encoding="utf-8")

        self.assertIn("verify:pr-stack", package["scripts"])
        self.assertIn("proof:pr-stack", package["scripts"])
        self.assertIn("scripts/pr_stack_health.py", workflow)
        self.assertIn("tests.test_pr_stack_health", workflow)
        self.assertIn("docs/PR_STACK_HEALTH.md", workflow)
        self.assertIn("artifacts/pr-stack-health/pr-stack-health.json", workflow)
        self.assertIn("npm run verify:pr-stack", doc)
        self.assertIn("npm run proof:pr-stack", doc)
        self.assertIn("artifacts/pr-stack-health-local/pr-stack-health.json", doc)
        self.assertIn(".github/workflows/pr-stack-health.yml", doc)
        self.assertIn("artifacts/pr-stack-health/pr-stack-health.json", doc)
        self.assertIn("Stop opening new broad PRs", doc)
        self.assertIn("skip_completed_pr_stack", doc)


if __name__ == "__main__":
    unittest.main()
