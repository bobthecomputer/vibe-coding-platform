from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from grant_agent.mission_control import (  # noqa: E402
    PROVIDER_ECOSYSTEM_ROWS,
    PROVIDER_ECOSYSTEM_SOURCES,
    _provider_source_freshness,
    _provider_source_verification_gate,
)


DEFAULT_OUTPUT_ROOT = ROOT / "artifacts" / "provider-catalog"
AI_GATEWAY_MODELS_URL = "https://ai-gateway.vercel.sh/v1/models"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _fetch_json(url: str, *, timeout_seconds: int = 10) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "fluxio-provider-catalog-refresh/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        data = response.read()
    return json.loads(data.decode("utf-8"))


def _dynamic_source_snapshot(fetch_ai_gateway: bool) -> list[dict]:
    if not fetch_ai_gateway:
        return [
            {
                "sourceId": "vercel_ai_gateway_models",
                "url": AI_GATEWAY_MODELS_URL,
                "status": "not_fetched",
                "liveFetchPerformed": False,
                "modelCount": None,
                "error": "",
                "reason": "Live fetch disabled. Run with --fetch-ai-gateway to collect a review artifact.",
            }
        ]
    try:
        payload = _fetch_json(AI_GATEWAY_MODELS_URL)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return [
            {
                "sourceId": "vercel_ai_gateway_models",
                "url": AI_GATEWAY_MODELS_URL,
                "status": "fetch_failed",
                "liveFetchPerformed": True,
                "modelCount": None,
                "error": str(exc),
            }
        ]

    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        models = payload if isinstance(payload, list) else []
    sample = []
    for item in models[:12]:
        if isinstance(item, dict):
            sample.append(
                {
                    "id": item.get("id") or item.get("model") or "",
                    "provider": item.get("provider") or item.get("owned_by") or "",
                    "contextWindow": item.get("contextWindow") or item.get("context_window"),
                    "capabilities": item.get("capabilities") or item.get("modalities") or [],
                }
            )
    return [
        {
            "sourceId": "vercel_ai_gateway_models",
            "url": AI_GATEWAY_MODELS_URL,
            "status": "fetched",
            "liveFetchPerformed": True,
            "modelCount": len(models),
            "error": "",
            "sample": sample,
        }
    ]


def build_catalog_refresh_report(
    *,
    fetch_ai_gateway: bool = False,
    run_id: str | None = None,
) -> dict:
    stable_run_id = run_id or f"provider-catalog-refresh-{slug_now()}"
    source_freshness = _provider_source_freshness(PROVIDER_ECOSYSTEM_SOURCES)
    source_verification_gate = _provider_source_verification_gate(source_freshness)
    tracked_providers = []
    for row in PROVIDER_ECOSYSTEM_ROWS:
        tracked_providers.append(
            {
                "providerId": row["providerId"],
                "label": row["label"],
                "supportStatus": row["status"],
                "routeRole": row["routeRole"],
                "authPath": row["authPath"],
                "updateSource": row["updateSource"],
                "supports": row["supports"],
                "defaultChangeAllowed": False,
            }
        )
    return {
        "schemaVersion": "provider-catalog-refresh/v1",
        "runId": stable_run_id,
        "createdAt": utc_now(),
        "mode": "review_artifact_only",
        "liveFetch": {
            "aiGateway": fetch_ai_gateway,
        },
        "sourceFreshness": {
            key: value
            for key, value in source_freshness.items()
            if key != "sources"
        },
        "sourceVerificationGate": source_verification_gate,
        "trackedProviders": tracked_providers,
        "sourceSnapshots": [
            {
                **source,
                "status": "metadata_only",
                "liveFetchPerformed": False,
                "runId": stable_run_id,
                "modelCount": None,
                "error": "",
            }
            for source in PROVIDER_ECOSYSTEM_SOURCES
        ],
        "dynamicSourceSnapshots": _dynamic_source_snapshot(fetch_ai_gateway),
        "approvalPolicy": {
            "requiresApprovalForDefaultChanges": True,
            "neverOverwriteUserModels": True,
            "writesDefaults": False,
            "writesCredentials": False,
            "writesProviderRegistry": False,
        },
        "reviewActions": [
            "Inspect provider counts, capability samples, auth paths, and source freshness.",
            "Promote changes through a separate PR; do not mutate defaults from this report.",
            "Keep local/user-defined model IDs unless a reviewer explicitly approves replacements.",
        ],
    }


def write_report(report: dict, *, output_root: Path = DEFAULT_OUTPUT_ROOT) -> Path:
    out_dir = output_root / report["runId"]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "provider_catalog_refresh.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a review-only provider catalog refresh artifact."
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--fetch-ai-gateway", action="store_true")
    args = parser.parse_args(argv)

    report = build_catalog_refresh_report(
        fetch_ai_gateway=args.fetch_ai_gateway,
        run_id=args.run_id or None,
    )
    path = write_report(report, output_root=args.output_root)
    print(json.dumps({"runId": report["runId"], "path": str(path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
