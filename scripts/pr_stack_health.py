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
            "number,title,headRefName,baseRefName,isDraft,url,mergeStateStatus,statusCheckRollup,reviewDecision,updatedAt",
        ],
        check=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
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


def _check_rollup(row: dict[str, Any]) -> list[dict[str, Any]]:
    rollup = row.get("statusCheckRollup")
    if not isinstance(rollup, list):
        return []
    return [item for item in rollup if isinstance(item, dict)]


def _release_proof_status(row: dict[str, Any]) -> str:
    checks = _check_rollup(row)
    if not checks:
        return "missing"
    release_checks = [
        check
        for check in checks
        if "release-proof" in str(check.get("name") or "").casefold()
        or "release proof" in str(check.get("workflowName") or "").casefold()
    ]
    if not release_checks:
        return "missing"
    if any(str(check.get("status") or "").upper() not in {"", "COMPLETED"} for check in release_checks):
        return "pending"
    if all(str(check.get("conclusion") or "").upper() == "SUCCESS" for check in release_checks):
        return "passed"
    return "failed"


def _landing_row(row: dict[str, Any]) -> dict[str, Any]:
    merge_state = str(row.get("mergeStateStatus") or "UNKNOWN").strip().upper()
    review_decision = str(row.get("reviewDecision") or "").strip().upper()
    release_status = _release_proof_status(row)
    blockers: list[str] = []
    if bool(row.get("isDraft")):
        blockers.append("draft")
    if merge_state != "CLEAN":
        blockers.append(f"merge_state:{merge_state.lower()}")
    if release_status != "passed":
        blockers.append(f"release_proof:{release_status}")
    if review_decision in {"CHANGES_REQUESTED", "REVIEW_REQUIRED"}:
        blockers.append(f"review:{review_decision.lower()}")
    return {
        "number": _pr_number(row),
        "title": str(row.get("title") or "").strip(),
        "url": str(row.get("url") or "").strip(),
        "headRefName": _branch_name(row, "headRefName"),
        "baseRefName": _branch_name(row, "baseRefName"),
        "isDraft": bool(row.get("isDraft")),
        "mergeStateStatus": merge_state,
        "reviewDecision": review_decision,
        "releaseProofStatus": release_status,
        "clean": merge_state == "CLEAN",
        "ready": not blockers,
        "blockers": blockers,
        "updatedAt": str(row.get("updatedAt") or "").strip(),
    }


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


def _continuation_policy(status: str, next_action: str) -> dict[str, Any]:
    if status == "no_open_prs":
        return {
            "state": "completed",
            "shouldContinueStackWork": False,
            "automationDecision": "skip_completed_pr_stack",
            "nextCompartmentAction": (
                "Start a fresh mission from current origin/master; do not reopen completed PR-stack landing work."
            ),
            "detail": "The stack landing compartment has no remaining open PR frontier.",
        }
    if status == "blocked_at_landing_frontier":
        return {
            "state": "continue_stack_repair",
            "shouldContinueStackWork": True,
            "automationDecision": "repair_landing_frontier",
            "nextCompartmentAction": next_action,
            "detail": "Stay on the current stack until the oldest blocked PR is repaired or closed.",
        }
    if status in {"ready_to_land", "ready_to_land_but_stack_exceeds_limit"}:
        return {
            "state": "continue_stack_landing",
            "shouldContinueStackWork": True,
            "automationDecision": "land_oldest_pr",
            "nextCompartmentAction": next_action,
            "detail": "Land one PR, then re-run readiness before touching newer stacked work.",
        }
    return {
        "state": "unknown",
        "shouldContinueStackWork": None,
        "automationDecision": "inspect_manually",
        "nextCompartmentAction": next_action,
        "detail": "The readiness status is not recognized by the continuation policy.",
    }


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


def build_pr_stack_landing_readiness(rows: list[dict[str, Any]], *, max_chain: int = DEFAULT_MAX_CHAIN) -> dict[str, Any]:
    health = build_pr_stack_health(rows, max_chain=max_chain)
    chains = _build_chains(rows)
    longest = max(chains, key=len, default=[])
    landing_sequence = [_landing_row(row) for row in reversed(longest)]
    blocked = [row for row in landing_sequence if row["blockers"]]
    ready_to_land = [row for row in landing_sequence if row["ready"]]
    landing_frontier = blocked[0] if blocked else (landing_sequence[0] if landing_sequence else None)
    if not landing_sequence:
        status = "no_open_prs"
        next_action = "No open stacked PRs were found."
    elif blocked:
        frontier = landing_frontier or {}
        reason = ", ".join(frontier.get("blockers") or ["unknown"])
        status = "blocked_at_landing_frontier"
        next_action = f"Fix PR{frontier.get('number')} before landing newer stacked PRs: {reason}."
    elif health["staleStackDetected"]:
        status = "ready_to_land_but_stack_exceeds_limit"
        next_action = "Land the oldest PR first, then re-run readiness before advancing the stack."
    else:
        status = "ready_to_land"
        next_action = "Land the oldest PR first, then re-run readiness after GitHub updates the next base."

    release_passed_count = sum(1 for row in landing_sequence if row["releaseProofStatus"] == "passed")
    clean_count = sum(1 for row in landing_sequence if row["clean"])
    draft_count = sum(1 for row in landing_sequence if row["isDraft"])
    blocked_count = len(blocked)
    return {
        "schema": "fluxio.pr_stack_landing_readiness.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "ok": status in {"ready_to_land", "ready_to_land_but_stack_exceeds_limit", "no_open_prs"},
        "status": status,
        "primaryRuntimeLane": "hermes",
        "fallbackRuntimeLanes": ["openclaw", "opencode"],
        "source": "github_pr_rows",
        "stack": {
            "openPrCount": health["openPrCount"],
            "chainCount": health["chainCount"],
            "longestChainLength": health["longestChainLength"],
            "longestChainPrs": health["longestChainPrs"],
            "longestChainHeads": health["longestChainHeads"],
            "maxAllowedChain": max_chain,
            "staleStackDetected": health["staleStackDetected"],
        },
        "summary": {
            "readyToLandCount": len(ready_to_land),
            "blockedCount": blocked_count,
            "draftCount": draft_count,
            "cleanCount": clean_count,
            "releaseProofPassedCount": release_passed_count,
        },
        "landingFrontier": landing_frontier,
        "landingSequence": landing_sequence,
        "blockers": landing_frontier.get("blockers", []) if landing_frontier else [],
        "nextAction": next_action,
        "continuationPolicy": _continuation_policy(status, next_action),
        "routeProof": {
            "primary": "hermes",
            "fallback": ["openclaw", "opencode"],
            "purpose": "pr_stack_landing_order_readiness",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect stale stacked GitHub PR chains before they become unreviewable.")
    parser.add_argument("--input", type=Path, help="Saved `gh pr list --json ...` payload to inspect")
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    parser.add_argument("--max-chain", type=int, default=DEFAULT_MAX_CHAIN, help="Maximum allowed stacked PR chain length")
    parser.add_argument("--limit", type=int, default=200, help="Maximum open PRs to fetch when --input is omitted")
    parser.add_argument("--landing-readiness", action="store_true", help="Report ordered landing readiness instead of only chain length")
    args = parser.parse_args()

    rows = _load_pr_rows(args.input) if args.input else _fetch_open_pr_rows(limit=args.limit)
    report = (
        build_pr_stack_landing_readiness(rows, max_chain=args.max_chain)
        if args.landing_readiness
        else build_pr_stack_health(rows, max_chain=args.max_chain)
    )
    report_text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report_text + "\n", encoding="utf-8")
    print(report_text)
    if args.landing_readiness:
        return 0 if report["ok"] else 1
    return 1 if report["staleStackDetected"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
