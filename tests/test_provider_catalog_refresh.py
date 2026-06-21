from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import provider_catalog_refresh as refresh


class ProviderCatalogRefreshTests(unittest.TestCase):
    def test_builds_review_only_provider_catalog_report(self) -> None:
        report = refresh.build_catalog_refresh_report(
            fetch_ai_gateway=False,
            run_id="test-provider-catalog-refresh",
        )

        self.assertEqual(report["schemaVersion"], "provider-catalog-refresh/v1")
        self.assertEqual(report["mode"], "review_artifact_only")
        self.assertFalse(report["liveFetch"]["aiGateway"])
        self.assertTrue(report["approvalPolicy"]["requiresApprovalForDefaultChanges"])
        self.assertTrue(report["approvalPolicy"]["neverOverwriteUserModels"])
        self.assertFalse(report["approvalPolicy"]["writesDefaults"])
        self.assertFalse(report["approvalPolicy"]["writesCredentials"])
        self.assertFalse(report["approvalPolicy"]["writesProviderRegistry"])
        self.assertEqual(
            report["sourceVerificationGate"]["schemaVersion"],
            "provider-source-verification-gate.v1",
        )
        self.assertEqual(
            report["sourceVerificationGate"]["status"],
            "review_only_current",
        )
        self.assertFalse(report["sourceVerificationGate"]["defaultChangeAllowed"])
        self.assertTrue(report["sourceVerificationGate"]["defaultChangeBlocked"])
        self.assertGreaterEqual(
            report["sourceVerificationGate"]["primarySourceCount"],
            5,
        )
        source_urls = {
            item["url"]
            for item in report["sourceVerificationGate"]["primarySources"]
        }
        self.assertIn("https://opencode.ai/docs/models/", source_urls)
        self.assertIn("https://docs.openclaw.ai/concepts/model-providers", source_urls)
        self.assertIn("https://ai-gateway.vercel.sh/v1/models", source_urls)
        self.assertIn("https://docs.litellm.ai/docs/providers", source_urls)

        source_snapshot = report["sourceSnapshots"][0]
        self.assertEqual(source_snapshot["status"], "metadata_only")
        self.assertFalse(source_snapshot["liveFetchPerformed"])
        self.assertEqual(source_snapshot["runId"], "test-provider-catalog-refresh")
        self.assertIsNone(source_snapshot["modelCount"])
        self.assertEqual(source_snapshot["error"], "")

        provider_ids = {item["providerId"] for item in report["trackedProviders"]}
        self.assertIn("openai", provider_ids)
        self.assertIn("minimax", provider_ids)
        self.assertIn("local", provider_ids)
        self.assertTrue(all(item["defaultChangeAllowed"] is False for item in report["trackedProviders"]))

        dynamic = report["dynamicSourceSnapshots"][0]
        self.assertEqual(dynamic["sourceId"], "vercel_ai_gateway_models")
        self.assertEqual(dynamic["status"], "not_fetched")
        self.assertFalse(dynamic["liveFetchPerformed"])
        self.assertIsNone(dynamic["modelCount"])
        self.assertEqual(dynamic["error"], "")

    def test_writes_report_without_mutating_defaults(self) -> None:
        report = refresh.build_catalog_refresh_report(
            fetch_ai_gateway=False,
            run_id="test-provider-catalog-refresh",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = refresh.write_report(report, output_root=pathlib.Path(temp_dir))

            self.assertTrue(path.exists())
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["runId"], "test-provider-catalog-refresh")
        self.assertFalse(payload["approvalPolicy"]["writesDefaults"])
        self.assertTrue(payload["sourceVerificationGate"]["defaultChangeBlocked"])
        self.assertIn("Promote changes through a separate PR", " ".join(payload["reviewActions"]))

    def test_source_freshness_expires_with_real_age(self) -> None:
        freshness = refresh._provider_source_freshness(
            [
                {
                    "sourceId": "old_source",
                    "label": "Old source",
                    "url": "https://example.invalid/provider",
                    "verifiedAt": "2026-01-01",
                }
            ],
            as_of="2026-06-21",
        )
        gate = refresh._provider_source_verification_gate(freshness)

        self.assertEqual(freshness["status"], "review_required")
        self.assertEqual(freshness["sources"][0]["freshnessStatus"], "expired")
        self.assertEqual(gate["status"], "source_review_required")
        self.assertEqual(gate["reviewRequiredCount"], 1)
        self.assertTrue(gate["defaultChangeBlocked"])

    def test_report_does_not_leak_secret_values(self) -> None:
        report = refresh.build_catalog_refresh_report(
            fetch_ai_gateway=False,
            run_id="test-provider-catalog-refresh",
        )
        serialized = json.dumps(report)

        self.assertNotIn("sk-test-DO-NOT-LEAK", serialized)
        self.assertNotIn("test-openai-key", serialized)


if __name__ == "__main__":
    unittest.main()
