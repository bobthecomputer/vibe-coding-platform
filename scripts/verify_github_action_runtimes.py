from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA = "fluxio.github_action_runtime_guard.v1"

MINIMUM_ACTION_MAJORS: dict[str, int] = {
    "actions/checkout": 5,
    "actions/setup-node": 5,
    "actions/setup-python": 6,
    "actions/upload-artifact": 6,
    "actions/upload-pages-artifact": 5,
    "actions/deploy-pages": 5,
}

USES_RE = re.compile(r"\buses:\s*['\"]?([^@\s'\"]+)@([^#\s'\"]+)")
MAJOR_RE = re.compile(r"^v(\d+)(?:$|[.\-])")


def _workflow_paths(root: Path) -> list[Path]:
    workflow_root = root / ".github" / "workflows"
    if not workflow_root.exists():
        return []
    return sorted([*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml")])


def _major(ref: str) -> int | None:
    match = MAJOR_RE.match(ref.strip())
    if not match:
        return None
    return int(match.group(1))


def verify_github_action_runtimes(root: Path) -> dict[str, Any]:
    root = root.resolve()
    checked_refs: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []

    for workflow in _workflow_paths(root):
        try:
            lines = workflow.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = workflow.read_text().splitlines()

        for index, line in enumerate(lines, start=1):
            match = USES_RE.search(line)
            if not match:
                continue

            action = match.group(1).strip().lower()
            ref = match.group(2).strip().rstrip(",")
            checked_refs.append(
                {
                    "path": str(workflow.relative_to(root)).replace("\\", "/"),
                    "line": index,
                    "action": action,
                    "ref": ref,
                }
            )

            required_major = MINIMUM_ACTION_MAJORS.get(action)
            if required_major is None:
                continue

            actual_major = _major(ref)
            if actual_major is None:
                violations.append(
                    {
                        "path": str(workflow.relative_to(root)).replace("\\", "/"),
                        "line": index,
                        "action": action,
                        "ref": ref,
                        "requiredMajor": required_major,
                        "reason": "protected_action_must_use_v_major_ref",
                    }
                )
                continue

            if actual_major < required_major:
                violations.append(
                    {
                        "path": str(workflow.relative_to(root)).replace("\\", "/"),
                        "line": index,
                        "action": action,
                        "ref": ref,
                        "actualMajor": actual_major,
                        "requiredMajor": required_major,
                        "reason": "protected_action_major_below_node24_floor",
                    }
                )

    return {
        "schema": SCHEMA,
        "ok": not violations,
        "workflowCount": len(_workflow_paths(root)),
        "checkedActionRefCount": len(checked_refs),
        "minimumActionMajors": MINIMUM_ACTION_MAJORS,
        "checkedActionRefs": checked_refs,
        "violations": violations,
    }


def _write_output(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify protected GitHub Actions use Node 24-compatible major versions."
    )
    parser.add_argument("--root", default=".", help="Repository root to scan.")
    parser.add_argument("--output", help="Optional JSON artifact path.")
    args = parser.parse_args(argv)

    payload = verify_github_action_runtimes(Path(args.root))
    if args.output:
        _write_output(Path(args.output), payload)

    if payload["ok"]:
        print(
            "github_action_runtime_guard.ok=true "
            f"workflow_count={payload['workflowCount']} "
            f"checked_refs={payload['checkedActionRefCount']}"
        )
        return 0

    print("github_action_runtime_guard.ok=false", file=sys.stderr)
    for violation in payload["violations"]:
        print(
            "{path}:{line}: {action}@{ref} requires v{requiredMajor}+ ({reason})".format(
                **violation
            ),
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
