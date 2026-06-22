from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_public_web_distribution import verify_public_web_distribution


ROOT = Path(__file__).resolve().parents[1]


def _write_minimal_public_web_contract(root: Path, *, upload_pages_ref: str = "v5") -> None:
    workflow_root = root / ".github" / "workflows"
    workflow_root.mkdir(parents=True)
    (workflow_root / "web-pages.yml").write_text(
        "\n".join(
            [
                "name: Deploy Fluxio Web",
                "on:",
                "  workflow_dispatch:",
                "permissions:",
                "  contents: read",
                "  pages: write",
                "  id-token: write",
                "jobs:",
                "  build:",
                "    steps:",
                "      - uses: actions/checkout@v5",
                "      - uses: actions/setup-node@v5",
                "      - run: npm run frontend:build",
                "      - run: npm run verify:web-distribution -- --require-built-dist",
                f"      - uses: actions/upload-pages-artifact@{upload_pages_ref}",
                "        with:",
                "          path: web/dist",
                "  deploy:",
                "    environment:",
                "      name: github-pages",
                "      url: ${{ steps.deployment.outputs.page_url }}",
                "    steps:",
                "      - id: deployment",
                "        uses: actions/deploy-pages@v5",
                "      - run: |",
                "          echo fluxio.public_web_deployment.v1",
                "          echo ${{ steps.deployment.outputs.page_url }}",
                "          echo ${{ github.sha }}",
                "          echo ${{ github.run_id }}",
                "          echo fluxio.release_candidate.v1",
                "          echo .agent_control/deployment_evidence/public-web.json",
                "          echo .agent_control/release_candidates/public-web/release-candidate.json",
                "      - uses: actions/upload-artifact@v6",
                "        with:",
                "          name: fluxio-public-web-release-candidate",
            ]
        ),
        encoding="utf-8",
    )
    (root / "package.json").write_text(
        json.dumps(
            {
                "scripts": {
                    "frontend:build": "vite build",
                    "web:backend": "python scripts/run_web_backend.py",
                    "web:serve": "npm run frontend:build && python scripts/run_web_backend.py",
                    "verify:pwa": "python scripts/verify_pwa_shell.py",
                    "verify:web-distribution": "python scripts/verify_public_web_distribution.py",
                }
            }
        ),
        encoding="utf-8",
    )
    public_root = root / "web" / "public"
    public_root.mkdir(parents=True)
    (public_root / "manifest.webmanifest").write_text(
        json.dumps({"name": "Fluxio", "start_url": "/", "display": "standalone"}),
        encoding="utf-8",
    )
    (public_root / "service-worker.js").write_text("const offline = true;\n", encoding="utf-8")
    (public_root / "offline.html").write_text("<html>Offline</html>\n", encoding="utf-8")


class PublicWebDistributionRuntimeGuardTest(unittest.TestCase):
    def test_current_public_web_distribution_reports_action_runtime_guard(self) -> None:
        result = verify_public_web_distribution(ROOT)

        self.assertTrue(result["ok"], result["missing"])
        guard = next(item for item in result["checks"] if item["checkId"] == "github_action_runtime_guard")
        self.assertTrue(guard["passed"], guard)
        self.assertEqual(guard["runtimeGuard"]["schema"], "fluxio.github_action_runtime_guard.v1")
        self.assertGreaterEqual(guard["runtimeGuard"]["checkedActionRefCount"], 1)

    def test_stale_pages_action_fails_distribution_even_when_workflow_shape_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_public_web_contract(root, upload_pages_ref="v3")

            result = verify_public_web_distribution(root)

        self.assertFalse(result["ok"])
        self.assertIn("github_action_runtime_guard", result["missing"])
        guard = next(item for item in result["checks"] if item["checkId"] == "github_action_runtime_guard")
        self.assertFalse(guard["passed"])
        self.assertEqual(
            guard["runtimeGuard"]["violations"][0]["action"],
            "actions/upload-pages-artifact",
        )


if __name__ == "__main__":
    unittest.main()
