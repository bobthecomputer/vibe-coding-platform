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
              FUSION_MIGRATION_LANES,
              FUSION_RISK_LABELS,
              buildFusionWorkbench,
            } from './web/src/fluxio/fusion/fusionFixtures.js';

            const workbench = buildFusionWorkbench();
            console.log(JSON.stringify({
              modes: FUSION_COLLECTION_MODES,
              risks: FUSION_RISK_LABELS,
              summary: workbench.summary,
              rows: FUSION_FIXTURES,
              lanes: FUSION_MIGRATION_LANES,
              rules: workbench.acceptanceRules,
            }));
            """
        )

        self.assertEqual(payload["summary"]["totalRows"], len(payload["rows"]))
        self.assertGreaterEqual(payload["summary"]["readyRows"], 2)
        self.assertEqual(payload["summary"]["migrationLaneCount"], len(payload["lanes"]))
        self.assertIn("Synology monitoring", payload["summary"]["nextMigrationLane"])
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

        lane_required = {
            "id",
            "title",
            "sourcePair",
            "duplicateArea",
            "migrationStatus",
            "targetRuntime",
            "safeSlice",
            "proofAction",
            "ownerRole",
        }
        for lane in payload["lanes"]:
            self.assertTrue(lane_required.issubset(lane), lane["id"])
            self.assertIn("->", lane["sourcePair"])
            self.assertTrue(lane["proofAction"])

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
        self.assertIn("safe slice", joined)
        self.assertTrue(
            any(row["collectionMode"] == "blocked" for row in payload["rows"])
        )

    def test_backend_fusion_rows_merge_with_default_inventory(self) -> None:
        payload = run_node(
            """
            import { buildFusionWorkbench } from './web/src/fluxio/fusion/fusionFixtures.js';
            const workbench = buildFusionWorkbench([
              {
                id: 'mindtower-readonly-sqlite-adapter',
                sourceProject: 'Mind Tower',
                sourcePath: 'C:/Users/paul/projects/mind-tower/data/mindtower.sqlite',
                sourceHashPrefix: '',
                collectionMode: 'read-only-adapter',
                riskLabel: 'no-credential-copy',
                status: 'ready-for-adapter-shape',
                title: 'Mind Tower read-only source and event adapter',
                summary: 'Read-only adapter found 10 records.',
                proofNeed: 'Credential values stay masked and no writes are exposed.',
                nextSlice: 'Promote source health rows into Fluxio bridge cards.',
                lastVerifiedAt: '2026-06-21',
              }
            ]);
            console.log(JSON.stringify({
              ids: workbench.rows.map(item => item.id),
              totalRows: workbench.summary.totalRows,
            }));
            """
        )

        self.assertIn("mindtower-readonly-sqlite-adapter", payload["ids"])
        self.assertIn("solantir-signal-contract", payload["ids"])
        self.assertIn("jbheaven-defensive-harness", payload["ids"])
        self.assertGreaterEqual(payload["totalRows"], 5)


if __name__ == "__main__":
    unittest.main()
