from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_MAX_CHAIN = 5


def _load_pr_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list of pull requests")
    return [item for item in payload if isinstance(item, dict)]


def _fetch_open_pr_rows(limit: int = 200) -> list[dict[str, Any]]:
    if not shutil.which("gh"):
        raise RuntimeError("GitHub CLI `gh` is not available; pass --input with saved PR JSON")
    completed = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "open",
            "--limit",
            str(limit),
            "--json",
            "number,title,headRefName,baseRefName,isDraft,url",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    payload = json.loads(completed.stdout or "[]")
    if not isinstance(payload, list):
        raise RuntimeError("GitHub CLI returned an unexpected PR payload")
    return [item for item in payload if isinstance(item, dict)]


def _pr_number(row: dict[str, Any]) -> int:
    try:
        return int(row.get("number") or 0)
    except (TypeError, ValueError):
        return 0


def _branch_name(row: dict[str, Any], key: str) -> str:
    return str(row.get(key) or "").strip()


def _build_chains(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    by_head = {_branch_name(row, "headRefName"): row for row in rows if _branch_name(row, "headRefName")}
    children = {_branch_name(row, "baseRefName") for row in rows if _branch_name(row, "baseRefName") in by_head}
    roots = [row for row in rows if _branch_name(row, "headRefName") not in children]

    chains: list[list[dict[str, Any]]] = []
    for root in sorted(roots, key=_pr_number, reverse=True):
        chain: list[dict[str, Any]] = []
        seen: set[str] = set()
        current: dict[str, Any] | None = root
        while current is not None:
            head = _branch_name(current, "headRefName")
            if not head or head in seen:
                break
            seen.add(head)
            chain.append(current)
            base = _branch_name(current, "baseRefName")
            current = by_head.get(base)
        chains.append(chain)

    if not chains and rows:
        chains.append(sorted(rows, key=_pr_number, reverse=True))
    return chains


def build_pr_stack_health(rows: list[dict[str, Any]], *, max_chain: int = DEFAULT_MAX_CHAIN) -> dict[str, Any]:
    chains = _build_chains(rows)
    longest = max(chains, key=len, default=[])
    longest_numbers = [_pr_number(row) for row in longest]
    longest_heads = [_branch_name(row, "headRefName") for row in longest]
    stale_stack_detected = len(longest) > max_chain

    return {
        "schema": "fluxio.pr_stack_health.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "ok": not stale_stack_detected,
        "openPrCount": len(rows),
        "maxAllowedChain": max_chain,
        "chainCount": len(chains),
        "longestChainLength": len(longest),
        "longestChainPrs": longest_numbers,
        "longestChainHeads": longest_heads,
        "staleStackDetected": stale_stack_detected,
        "recommendation": (
            "Stop opening stacked PRs; merge or close the current chain before starting new compartments."
            if stale_stack_detected
            else "Open PR stack is within the configured chain limit."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect stale stacked GitHub PR chains before they become unreviewable.")
    parser.add_argument("--input", type=Path, help="Saved `gh pr list --json ...` payload to inspect")
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    parser.add_argument("--max-chain", type=int, default=DEFAULT_MAX_CHAIN, help="Maximum allowed stacked PR chain length")
    parser.add_argument("--limit", type=int, default=200, help="Maximum open PRs to fetch when --input is omitted")
    args = parser.parse_args()

    rows = _load_pr_rows(args.input) if args.input else _fetch_open_pr_rows(limit=args.limit)
    report = build_pr_stack_health(rows, max_chain=args.max_chain)
    report_text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report_text + "\n", encoding="utf-8")
    print(report_text)
    return 1 if report["staleStackDetected"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
