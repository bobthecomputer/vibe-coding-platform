from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.record_github_release_publication import build_github_release_publication_plan  # noqa: E402
from scripts.verify_public_launch_readiness import verify_public_launch_readiness  # noqa: E402


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_readiness(root: Path, readiness: dict[str, Any]) -> Path:
    out_dir = root / ".agent_control" / "public_launch_readiness"
    out_path = out_dir / "latest.json"
    staging_path = out_dir / "staging-plan.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    repair = readiness.get("repairPacket", {}) if isinstance(readiness.get("repairPacket"), dict) else {}
    staging = repair.get("stagingPlan", {}) if isinstance(repair.get("stagingPlan"), dict) else {}
    staging["proofPath"] = str(staging_path.resolve())
    if "stagingProof" in readiness:
        readiness["stagingProof"]["evidencePath"] = str(staging_path.resolve())
        readiness["stagingProof"]["readinessPath"] = str(out_path.resolve())
        _write_json(staging_path, readiness["stagingProof"])
    readiness["evidencePath"] = str(out_path.resolve())
    _write_json(out_path, readiness)
    return out_path


def build_public_launch_doctor(
    root: Path,
    *,
    repo: str = "",
    tag: str = "",
    write: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    release_plan = build_github_release_publication_plan(root, repo=repo, tag=tag)
    if write:
        plan_path = root / ".agent_control" / "publication" / "github-release-plan.json"
        _write_json(plan_path, release_plan)
        release_plan["evidencePath"] = str(plan_path.resolve())
    readiness = verify_public_launch_readiness(root)
    if write:
        _write_readiness(root, readiness)
    missing = readiness.get("missing", []) if isinstance(readiness.get("missing"), list) else []
    source_dirty_count = int(readiness.get("publicWeb", {}).get("currentGitDirtyPathCount") or 0)
    if readiness.get("ok"):
        status = "ready_for_public_launch"
        next_action = "Public launch can be claimed from the current readiness receipt."
    elif "public_web_current" in missing:
        status = "needs_current_public_source"
        next_action = "Commit, push, and redeploy the release-impacting source changes, then rerun this doctor."
    elif "external_publication_proven" in missing and release_plan.get("ready"):
        status = "ready_for_external_release_creation"
        next_action = str(release_plan.get("nextAction") or "")
    elif "external_publication_proven" in missing:
        status = "needs_release_candidate_plan"
        next_action = "Rebuild the release proof archive, then rerun this doctor."
    else:
        status = "public_launch_not_ready"
        next_action = str(readiness.get("nextAction") or "Fix failing readiness checks and rerun this doctor.")
    payload = {
        "schema": "fluxio.public_launch_doctor.v1",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "ok": bool(readiness.get("ok")),
        "status": status,
        "readinessStatus": readiness.get("status", ""),
        "missing": missing,
        "sourceDirtyPathCount": source_dirty_count,
        "releaseBlockingPathCount": int(
            readiness.get("repairPacket", {}).get("releaseBlockingPathCount") or 0
        ),
        "privateOrGeneratedPathCount": int(
            readiness.get("repairPacket", {}).get("privateOrGeneratedPathCount") or 0
        ),
        "githubReleasePlanReady": bool(release_plan.get("ready")),
        "githubReleasePlanTag": release_plan.get("tagName", ""),
        "githubReleasePlanAssetCount": int(release_plan.get("assetCount") or 0),
        "githubReleaseCreateCommand": release_plan.get("command", ""),
        "githubReleaseReceiptCommand": release_plan.get("recordReceiptCommand", ""),
        "readinessEvidencePath": readiness.get("evidencePath", ""),
        "githubReleasePlanEvidencePath": release_plan.get("evidencePath", ""),
        "nextAction": next_action,
    }
    if write:
        doctor_path = root / ".agent_control" / "public_launch_readiness" / "doctor.json"
        _write_json(doctor_path, payload)
        payload["evidencePath"] = str(doctor_path.resolve())
        _write_json(doctor_path, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the public-launch doctor: release plan plus readiness blockers in one receipt."
    )
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--repo", default="")
    parser.add_argument("--tag", default="")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)
    payload = build_public_launch_doctor(
        Path(args.root),
        repo=args.repo,
        tag=args.tag,
        write=args.write,
    )
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("ok") or not args.require_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
