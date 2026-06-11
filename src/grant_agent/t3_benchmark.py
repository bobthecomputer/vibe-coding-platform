from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any


T3_CODE_RELEASES_API = "https://api.github.com/repos/pingdotgg/t3code/releases?per_page=50"
T3_CODE_PRODUCT_PAGE = "https://t3.codes/"

T3_CODE_PRODUCT_CLAIMS = {
    "open_source_control_plane": ("open-source", "control plane", "coding agents"),
    "claude_codex_opencode_cursor": ("Claude Code", "Codex", "OpenCode", "Cursor"),
    "bring_your_own_subscription": ("Bring your own subscription",),
    "no_quota_caps": ("No keys resold", "No quota caps"),
    "mid_thread_model_switching": ("Switch models mid-thread",),
    "desktop_platforms": ("Windows", "macOS", "Linux"),
    "diff_and_pr_flow": ("View diff", "Pull Request"),
}


def _release_summary(release: dict[str, Any]) -> dict[str, Any]:
    assets = release.get("assets", []) if isinstance(release.get("assets"), list) else []
    asset_names = [str(item.get("name") or "") for item in assets if isinstance(item, dict)]
    return {
        "tag": str(release.get("tag_name") or ""),
        "name": str(release.get("name") or ""),
        "url": str(release.get("html_url") or ""),
        "publishedAt": str(release.get("published_at") or release.get("created_at") or ""),
        "prerelease": bool(release.get("prerelease")),
        "assetCount": len(asset_names),
        "assetNames": asset_names[:24],
    }


def _fetch_url_text(url: str, *, timeout_seconds: int) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/json",
            "User-Agent": "fluxio-system-audit",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8", errors="replace")


def _visible_text_from_html(html_text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", html_text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _product_claims_from_text(text: str) -> dict[str, bool]:
    return {
        claim_id: all(needle.lower() in text.lower() for needle in needles)
        for claim_id, needles in T3_CODE_PRODUCT_CLAIMS.items()
    }


def fetch_t3_code_product_page_evidence(*, timeout_seconds: int = 20) -> dict[str, Any]:
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        html_text = _fetch_url_text(T3_CODE_PRODUCT_PAGE, timeout_seconds=timeout_seconds)
    except Exception as exc:  # pragma: no cover - exercised by live network conditions
        return {
            "schema": "fluxio.t3_code_product_page_evidence.v1",
            "checkedAt": checked_at,
            "source": T3_CODE_PRODUCT_PAGE,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "claims": {},
            "verifiedClaimCount": 0,
        }
    text = _visible_text_from_html(html_text)
    claims = _product_claims_from_text(text)
    verified_claims = [claim_id for claim_id, present in claims.items() if present]
    return {
        "schema": "fluxio.t3_code_product_page_evidence.v1",
        "checkedAt": checked_at,
        "source": T3_CODE_PRODUCT_PAGE,
        "ok": True,
        "title": "T3 Code",
        "claims": claims,
        "verifiedClaimCount": len(verified_claims),
        "verifiedClaims": verified_claims,
        "excerpt": text[:700],
    }


def fetch_t3_code_release_benchmark(*, timeout_seconds: int = 20) -> dict[str, Any]:
    request = urllib.request.Request(
        T3_CODE_RELEASES_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "fluxio-system-audit",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        releases = json.loads(response.read().decode("utf-8"))
    if not isinstance(releases, list):
        releases = []
    stable = next(
        (item for item in releases if isinstance(item, dict) and not item.get("prerelease")),
        {},
    )
    prerelease = next(
        (item for item in releases if isinstance(item, dict) and item.get("prerelease")),
        {},
    )
    stable_summary = _release_summary(stable) if stable else {}
    prerelease_summary = _release_summary(prerelease) if prerelease else {}
    observed_parts = []
    if stable_summary:
        observed_parts.append(
            f"{stable_summary['tag']} stable"
            + (f" published {stable_summary['publishedAt']}" if stable_summary.get("publishedAt") else "")
        )
    if prerelease_summary:
        observed_parts.append(
            f"{prerelease_summary['tag']} pre-release"
            + (f" published {prerelease_summary['publishedAt']}" if prerelease_summary.get("publishedAt") else "")
        )
    return {
        "schema": "fluxio.t3_code_release_benchmark.v1",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "source": T3_CODE_RELEASES_API,
        "releaseCount": len(releases),
        "latestStable": stable_summary,
        "latestPrerelease": prerelease_summary,
        "latestObservedRelease": "; ".join(observed_parts),
        "productPageEvidence": fetch_t3_code_product_page_evidence(timeout_seconds=timeout_seconds),
        "notes": [
            "GitHub's latest-release endpoint reports the newest stable release; Fluxio also tracks the newest prerelease/nightly from the releases feed.",
        ],
    }


def write_t3_code_release_benchmark(root: Path, payload: dict[str, Any]) -> Path:
    path = root.resolve() / ".agent_control" / "t3_code_benchmark_latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
