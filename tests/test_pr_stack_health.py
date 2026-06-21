from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.pr_stack_health import build_pr_stack_health


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


if __name__ == "__main__":
    unittest.main()
