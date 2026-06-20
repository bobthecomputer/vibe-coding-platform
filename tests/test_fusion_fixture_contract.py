from __future__ import annotations

import json
import pathlib
import subprocess
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def run_node(script: str) -> dict:
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", textwrap.dedent(script)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


class FusionFixtureContractTests(unittest.TestCase):
    def test_fusion_fixtures_keep_provenance_mode_and_risk_visible(self) -> None:
        payload = run_node(
            """
            import {
              FUSION_COLLECTION_MODES,
              FUSION_FIXTURES,
              FUSION_RISK_LABELS,
              buildFusionWorkbench,
            } from './web/src/fluxio/fusion/fusionFixtures.js';

            const workbench = buildFusionWorkbench();
            console.log(JSON.stringify({
              modes: FUSION_COLLECTION_MODES,
              risks: FUSION_RISK_LABELS,
              summary: workbench.summary,
              rows: FUSION_FIXTURES,
              rules: workbench.acceptanceRules,
            }));
            """
        )

        self.assertEqual(payload["summary"]["totalRows"], len(payload["rows"]))
        self.assertGreaterEqual(payload["summary"]["readyRows"], 2)
        self.assertIn("read-only-adapter", payload["modes"])
        self.assertIn("no-trading-execution", payload["risks"])

        required = {
            "id",
            "sourceProject",
            "sourcePath",
            "collectionMode",
            "riskLabel",
            "status",
            "title",
            "summary",
            "proofNeed",
            "nextSlice",
            "lastVerifiedAt",
        }
        for row in payload["rows"]:
            self.assertTrue(required.issubset(row), row["id"])
            self.assertIn(row["collectionMode"], payload["modes"])
            self.assertIn(row["riskLabel"], payload["risks"])
            self.assertEqual(row["lastVerifiedAt"], "2026-06-21")
            self.assertTrue(row["sourcePath"])

    def test_fusion_fixtures_do_not_claim_live_or_write_access(self) -> None:
        payload = run_node(
            """
            import { buildFusionWorkbench } from './web/src/fluxio/fusion/fusionFixtures.js';
            const workbench = buildFusionWorkbench();
            console.log(JSON.stringify(workbench));
            """
        )

        joined = json.dumps(payload).lower()
        self.assertNotIn("order routing enabled", joined)
        self.assertNotIn("credential value", joined)
        self.assertNotIn("live exploit", joined)
        self.assertIn("read-only", joined)
        self.assertIn("synthetic", joined)
        self.assertTrue(
            any(row["collectionMode"] == "blocked" for row in payload["rows"])
        )


if __name__ == "__main__":
    unittest.main()
