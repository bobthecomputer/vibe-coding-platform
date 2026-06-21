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
              FUSION_MIGRATION_PHASES,
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
              phases: FUSION_MIGRATION_PHASES,
              gates: workbench.gateRows,
              rules: workbench.acceptanceRules,
            }));
            """
        )

        self.assertEqual(payload["summary"]["totalRows"], len(payload["rows"]))
        self.assertGreaterEqual(payload["summary"]["readyRows"], 2)
        self.assertEqual(payload["summary"]["migrationLaneCount"], len(payload["lanes"]))
        self.assertEqual(payload["summary"]["phaseCount"], len(payload["phases"]))
        self.assertGreaterEqual(payload["summary"]["gateCount"], 10)
        self.assertGreaterEqual(payload["summary"]["passedGateCount"], 6)
        self.assertIn("Read-only adapters", payload["summary"]["activePhase"])
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
            "phaseId",
            "promotionGates",
        }
        for lane in payload["lanes"]:
            self.assertTrue(lane_required.issubset(lane), lane["id"])
            self.assertIn("->", lane["sourcePair"])
            self.assertTrue(lane["proofAction"])
            self.assertGreaterEqual(len(lane["promotionGates"]), 3)

        for gate in payload["gates"]:
            self.assertIn(gate["status"], {"passed", "needed", "blocked"})
            self.assertTrue(gate["evidence"])

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

    def test_backend_adapter_truth_survives_into_fusion_workbench(self) -> None:
        payload = run_node(
            """
            import { buildFusionWorkbench } from './web/src/fluxio/fusion/fusionFixtures.js';
            const workbench = buildFusionWorkbench({
              adapter: {
                adapterId: 'mindtower-readonly-sqlite',
                sourceProject: 'Mind Tower',
                sourcePath: 'C:/Users/paul/projects/mind-tower/data/mindtower.sqlite',
                available: true,
                readOnly: true,
                writeActions: 0,
                credentialValuesExposed: false,
                status: 'ready',
                detail: 'Read-only adapter found 4 records, 1 events, and 1 runtime-state rows.',
                recordCounts: { sources: 2, 'summary-jobs': 2 },
                eventCount: 1,
                runtimeStateCount: 1,
                credentialSummary: [{ keyName: 'openai', status: 'ready' }],
                sourceHealth: [{ id: 'source-one', label: 'Example source', status: 'healthy' }],
                summaryJobs: [{ id: 'summary-one', label: 'Morning review', status: 'ready' }],
                recentEvents: [{ id: 'event-one', sourceType: 'rss', priorityScore: 3 }],
                runtimeStatePreview: [{ namespace: 'worker', key: 'last_run', valuePreview: 'ok' }],
              },
              rows: [
                {
                  id: 'mindtower-readonly-sqlite-adapter',
                  sourceProject: 'Mind Tower',
                  sourcePath: 'C:/Users/paul/projects/mind-tower/data/mindtower.sqlite',
                  sourceHashPrefix: '',
                  collectionMode: 'read-only-adapter',
                  riskLabel: 'no-credential-copy',
                  status: 'ready-for-adapter-shape',
                  title: 'Mind Tower read-only source and event adapter',
                  summary: 'Read-only adapter found 4 records.',
                  proofNeed: 'Credential values stay masked and no writes are exposed.',
                  nextSlice: 'Promote source health rows into Fluxio bridge cards.',
                  lastVerifiedAt: '2026-06-21',
                }
              ],
            });
            console.log(JSON.stringify({
              adapter: workbench.adapter,
              adapterSummary: workbench.adapterSummary,
              summary: workbench.summary,
            }));
            """
        )

        self.assertTrue(payload["adapterSummary"]["available"])
        self.assertEqual(payload["adapterSummary"]["status"], "ready")
        self.assertEqual(payload["adapterSummary"]["recordTotal"], 4)
        self.assertEqual(payload["adapterSummary"]["writeActions"], 0)
        self.assertEqual(payload["adapterSummary"]["sourceHealthCount"], 1)
        self.assertEqual(payload["adapterSummary"]["summaryJobCount"], 1)
        self.assertEqual(payload["summary"]["adapterStatus"], "ready")
        self.assertEqual(payload["summary"]["adapterRecordTotal"], 4)

    def test_backend_signal_snapshots_replace_seeded_solantir_signals(self) -> None:
        payload = run_node(
            """
            import { buildFusionWorkbench } from './web/src/fluxio/fusion/fusionFixtures.js';
            const workbench = buildFusionWorkbench({
              signalSnapshots: [
                {
                  id: 'solantir-backend-signal-contract-provenance',
                  entity: 'Backend Solantir Contract Provenance',
                  direction: 'neutral',
                  score: 67,
                  confidence: 0.82,
                  timestamp: '2026-06-21T00:00:00Z',
                  collectionMode: 'read-only-adapter',
                  riskLabel: 'no-trading-execution',
                  sourceProject: 'Solantir',
                  sourcePath: 'C:/Users/paul/projects/Solantir/packages/contracts/src/solantir.ts',
                  sourceHashPrefix: 'abc123def456',
                  factors: [
                    { name: 'provenance coverage', weight: 0.4, contribution: 16 },
                    { name: 'driver explainability', weight: 0.32, contribution: 12 },
                    { name: 'source file presence', weight: 0.28, contribution: 8 },
                  ],
                  topDrivers: [
                    'Read-only backend adapter found solantir.ts and recorded hash abc123def456.',
                    'No broker, order routing, credential, or live market execution path is exposed.',
                  ],
                  safetyLabels: ['no broker', 'no order routing', 'not investment advice'],
                },
              ],
            });
            console.log(JSON.stringify({
              summary: workbench.summary,
              signals: workbench.signalSnapshots,
            }));
            """
        )

        self.assertEqual(payload["summary"]["signalSnapshotCount"], 1)
        self.assertEqual(payload["signals"][0]["id"], "solantir-backend-signal-contract-provenance")
        self.assertEqual(payload["signals"][0]["collectionMode"], "read-only-adapter")
        self.assertEqual(payload["signals"][0]["sourceProject"], "Solantir")
        self.assertEqual(payload["signals"][0]["sourceHashPrefix"], "abc123def456")
        self.assertEqual(payload["signals"][0]["riskLabel"], "no-trading-execution")

    def test_solantir_signal_snapshots_are_explainable_and_non_executing(self) -> None:
        payload = run_node(
            """
            import { buildFusionWorkbench } from './web/src/fluxio/fusion/fusionFixtures.js';
            const workbench = buildFusionWorkbench();
            console.log(JSON.stringify({
              summary: workbench.summary,
              signals: workbench.signalSnapshots,
              rules: workbench.acceptanceRules,
            }));
            """
        )

        self.assertEqual(payload["summary"]["signalSnapshotCount"], len(payload["signals"]))
        self.assertGreaterEqual(len(payload["signals"]), 3)
        for signal in payload["signals"]:
            self.assertIn(signal["collectionMode"], {"seeded", "read-only-adapter"})
            self.assertEqual(signal["riskLabel"], "no-trading-execution")
            self.assertTrue(signal["sourcePath"])
            self.assertTrue(signal["timestamp"])
            self.assertGreaterEqual(signal["confidence"], 0)
            self.assertLessEqual(signal["confidence"], 1)
            self.assertGreaterEqual(len(signal["factors"]), 3)
            self.assertGreaterEqual(len(signal["topDrivers"]), 2)
            self.assertIn("no order routing", signal["safetyLabels"])
            self.assertIn("not investment advice", signal["safetyLabels"])
        joined = json.dumps(payload).lower()
        self.assertNotIn("broker enabled", joined)
        self.assertNotIn("order routing enabled", joined)
        self.assertIn("solantir signal snapshots", joined)


if __name__ == "__main__":
    unittest.main()
