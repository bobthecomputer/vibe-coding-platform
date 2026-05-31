from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from grant_agent import t3_benchmark


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


class T3BenchmarkTests(unittest.TestCase):
    def test_release_benchmark_includes_product_page_claim_evidence(self) -> None:
        releases = [
            {
                "tag_name": "v0.0.24",
                "name": "v0.0.24",
                "html_url": "https://github.com/pingdotgg/t3code/releases/tag/v0.0.24",
                "published_at": "2026-05-15T06:39:44Z",
                "prerelease": False,
                "assets": [{"name": "T3-Code-Windows.exe"}],
            },
            {
                "tag_name": "v0.0.25-nightly.20260530.413",
                "name": "nightly",
                "html_url": "https://github.com/pingdotgg/t3code/releases/tag/v0.0.25-nightly.20260530.413",
                "published_at": "2026-05-30T01:18:06Z",
                "prerelease": True,
                "assets": [{"name": "T3-Code-macOS.dmg"}],
            },
        ]
        product_html = """
        <html><title>T3 Code</title><body>
        The open-source control plane for coding agents.
        Orchestrate Claude Code, Codex, OpenCode and Cursor from one surface.
        Bring your own subscription.
        No keys resold. No quota caps. Switch models mid-thread.
        Windows macOS Linux. View diff. Pull Request.
        </body></html>
        """

        def fake_urlopen(request: object, timeout: int) -> _FakeResponse:
            url = str(getattr(request, "full_url", request))
            if url == t3_benchmark.T3_CODE_RELEASES_API:
                return _FakeResponse(json.dumps(releases).encode("utf-8"))
            if url == t3_benchmark.T3_CODE_PRODUCT_PAGE:
                return _FakeResponse(product_html.encode("utf-8"))
            raise AssertionError(url)

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            payload = t3_benchmark.fetch_t3_code_release_benchmark(timeout_seconds=3)

        self.assertEqual(payload["latestStable"]["tag"], "v0.0.24")
        self.assertEqual(payload["latestPrerelease"]["tag"], "v0.0.25-nightly.20260530.413")
        product = payload["productPageEvidence"]
        self.assertTrue(product["ok"])
        self.assertEqual(product["source"], t3_benchmark.T3_CODE_PRODUCT_PAGE)
        self.assertEqual(product["verifiedClaimCount"], 7)
        self.assertTrue(all(product["claims"].values()))
        self.assertIn("open-source control plane", product["excerpt"])


if __name__ == "__main__":
    unittest.main()
