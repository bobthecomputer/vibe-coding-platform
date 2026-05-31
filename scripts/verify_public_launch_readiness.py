from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_declared_path(root: Path, value: object) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("\\", "/")
    anchor = "/.agent_control/"
    if re.match(r"^[A-Za-z]:/", normalized) and anchor in normalized:
        normalized = ".agent_control/" + normalized.split(anchor, 1)[1]
        text = normalized
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        return candidate.resolve()
    except OSError:
        return candidate


def _check(checks: list[dict[str, Any]], check_id: str, passed: bool, details: str, **extra: Any) -> None:
    checks.append({"checkId": check_id, "passed": bool(passed), "details": details, **extra})


def _dirty_path_label(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    if text[:2] in {"M ", "A ", "D ", "R ", "C ", "U "}:
        text = text[2:].strip()
    elif text.startswith("??"):
        text = text[2:].strip()
    return text.replace("\\", "/")


def _dirty_path_lane(path: str) -> str:
    normalized = _dirty_path_label(path)
    if not normalized:
        return "unknown"
    if normalized.startswith(".agent_control/") or "/.agent_control/" in normalized:
        return "private_evidence"
    if normalized.startswith("tmp-") or normalized.endswith(".tgz"):
        return "temporary_artifact"
    if normalized.startswith(".github/"):
        return "ci_release"
    if normalized == "package.json" or normalized.startswith(("src/", "scripts/", "web/", "desktop-ui/", "src-tauri/")):
        return "product_source"
    if normalized.startswith("tests/"):
        return "verification"
    if normalized.startswith("docs/") or normalized == "README.md":
        return "docs"
    if normalized.startswith("C") and "volume1" in normalized:
        return "accidental_path_artifact"
    return "other"


def _current_git_dirty_rows(root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    return [line.rstrip() for line in result.stdout.splitlines() if line.strip()]


def _publication_dirty_source_triage(source_state: dict[str, Any], sample: list[str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    lane_counts: dict[str, int] = {}
    for raw in sample:
        normalized = _dirty_path_label(raw)
        if not normalized:
            continue
        lane = _dirty_path_lane(normalized)
        lane_counts[lane] = lane_counts.get(lane, 0) + 1
        rows.append(
            {
                "raw": raw,
                "path": normalized,
                "lane": lane,
                "releaseImpact": lane
                in {"product_source", "verification", "ci_release", "docs"},
                "recommendedAction": (
                    "Commit, push, and redeploy this source change before claiming public launch."
                    if lane in {"product_source", "verification", "ci_release", "docs"}
                    else "Keep this private evidence out of public release source, or archive it as an attachment."
                    if lane == "private_evidence"
                    else "Delete or move this accidental path artifact before public release."
                    if lane == "accidental_path_artifact"
                    else "Remove this temporary artifact before public release."
                    if lane == "temporary_artifact"
                    else "Review before publication."
                ),
            }
        )
    release_blocking_sample_count = sum(1 for item in rows if item["releaseImpact"])
    dirty_count = int(source_state.get("sourceDirtyPathCount") or len(rows) or 0)
    release_blocking_paths = [item["path"] for item in rows if item["releaseImpact"]]
    private_or_generated_paths = [
        item["path"]
        for item in rows
        if item["lane"] in {"private_evidence", "temporary_artifact", "accidental_path_artifact"}
    ]
    return {
        "schema": "fluxio.public_launch_dirty_source_triage.v1",
        "dirtyPathCount": dirty_count,
        "sampleCount": len(rows),
        "releaseBlockingSampleCount": release_blocking_sample_count,
        "releaseBlockingPathCount": len(release_blocking_paths),
        "privateOrGeneratedPathCount": len(private_or_generated_paths),
        "laneCounts": lane_counts,
        "rows": rows[:20],
        "releaseBlockingPaths": release_blocking_paths,
        "privateOrGeneratedPaths": private_or_generated_paths,
        "sourceCoverage": "full_git_status" if len(rows) >= dirty_count or dirty_count == len(rows) else "receipt_sample",
        "hasPrivateEvidenceSample": any(item["lane"] == "private_evidence" for item in rows),
        "hasAccidentalPathArtifacts": any(item["lane"] == "accidental_path_artifact" for item in rows),
        "safeToClaimCurrentPublicWeb": bool(
            source_state.get("sourceWorkingTreeClean")
            and source_state.get("deployedShaMatchesLocalHead")
            and dirty_count == 0
        ),
        "nextAction": (
            "Commit/push/deploy release-impacting source changes, then rerun public web and public launch verifiers."
            if release_blocking_sample_count
            else "Clean private/generated artifacts from the working tree or explicitly exclude them from publication proof."
            if rows
            else "No dirty source sample was reported; rerun public web verification with current source-state capture."
        ),
    }


def _public_launch_repair_packet(
    *,
    status: str,
    ok: bool,
    internal_packet_ready: bool,
    missing: list[str],
    next_action: str,
    dirty_source_triage: dict[str, Any],
    public_web: dict[str, Any],
    source_state: dict[str, Any],
) -> dict[str, Any]:
    lane_priority = [
        "product_source",
        "verification",
        "ci_release",
        "docs",
        "private_evidence",
        "temporary_artifact",
        "accidental_path_artifact",
        "other",
    ]
    lane_counts = (
        dirty_source_triage.get("laneCounts", {})
        if isinstance(dirty_source_triage.get("laneCounts"), dict)
        else {}
    )
    release_blocking_paths = [
        str(item)
        for item in dirty_source_triage.get("releaseBlockingPaths", [])
        if str(item or "").strip()
    ] if isinstance(dirty_source_triage.get("releaseBlockingPaths"), list) else []
    private_or_generated_paths = [
        str(item)
        for item in dirty_source_triage.get("privateOrGeneratedPaths", [])
        if str(item or "").strip()
    ] if isinstance(dirty_source_triage.get("privateOrGeneratedPaths"), list) else []
    ordered_lanes = [
        {
            "lane": lane,
            "count": int(lane_counts.get(lane) or 0),
            "releaseBlocking": lane in {"product_source", "verification", "ci_release", "docs"},
            "nextAction": (
                "Review, test, commit, push, and redeploy before claiming current public web."
                if lane in {"product_source", "verification", "ci_release", "docs"}
                else "Keep private/generated evidence out of the public release proof."
                if lane == "private_evidence"
                else "Remove the temporary archive from the release source tree."
                if lane == "temporary_artifact"
                else "Delete or move the accidental path artifact before release."
                if lane == "accidental_path_artifact"
                else "Review before publication."
            ),
        }
        for lane in lane_priority
        if int(lane_counts.get(lane) or 0) > 0
    ]
    primary_blocker = (
        "public_web_current"
        if "public_web_current" in missing
        else "external_publication_proven"
        if "external_publication_proven" in missing
        else missing[0]
        if missing
        else ""
    )
    receipt_targets = [
        {
            "label": "GitHub release/tag receipt",
            "path": ".agent_control/publication/github-release.json",
            "schema": "fluxio.github_release_publication_receipt.v1",
        },
        {
            "label": "npm registry receipt",
            "path": ".agent_control/publication/npm-registry.json",
            "schema": "fluxio.npm_publication_receipt.v1",
        },
        {
            "label": "Signed installer receipt",
            "path": ".agent_control/publication/signed-installer.json",
            "schema": "fluxio.signed_installer_receipt.v1",
        },
    ]
    staging_groups = []
    for lane in lane_priority:
        lane_paths = [
            str(item.get("path") or "")
            for item in dirty_source_triage.get("rows", [])
            if isinstance(item, dict)
            and str(item.get("lane") or "") == lane
            and item.get("releaseImpact")
            and str(item.get("path") or "").strip()
        ]
        full_lane_paths = [
            path for path in release_blocking_paths if _dirty_path_lane(path) == lane
        ]
        if full_lane_paths:
            lane_paths = full_lane_paths
        if not lane_paths:
            continue
        staging_groups.append(
            {
                "lane": lane,
                "pathCount": len(lane_paths),
                "paths": lane_paths[:30],
                "command": "git add -- " + " ".join(json.dumps(path) for path in lane_paths[:30]),
                "truncated": len(lane_paths) > 30,
            }
        )
    staging_plan = {
        "schema": "fluxio.public_launch_staging_plan.v1",
        "status": "needs_staging" if release_blocking_paths else "no_release_source_to_stage",
        "releaseImpactPathCount": len(release_blocking_paths),
        "privateOrGeneratedPathCount": len(private_or_generated_paths),
        "groups": staging_groups,
        "cleanupCommands": [
            {
                "label": "Review generated/private paths before release",
                "command": "git status --short -- " + " ".join(json.dumps(path) for path in private_or_generated_paths[:20]),
                "pathCount": len(private_or_generated_paths),
            }
        ] if private_or_generated_paths else [],
        "commitCommand": "git commit -m \"Prepare Fluxio public launch proof\"",
        "verifyCommand": "npm run frontend:build && python scripts/verify_public_web_distribution.py --write && python scripts/verify_public_launch_readiness.py --write",
        "nextAction": (
            "Stage the release-impacting groups, clean or exclude generated/private artifacts, run verifiers, then publish."
            if release_blocking_paths
            else "No release-impacting source paths were detected; attach external publication proof."
        ),
    }
    commands = [
        {
            "label": "Inspect release-impacting source lanes",
            "command": "git status --short",
            "requiresOperator": False,
            "proves": "Which source, docs, test, workflow, evidence, and temporary paths are still unpublished.",
        },
        {
            "label": "Rebuild and rerun public launch verifiers",
            "command": "npm run frontend:build && python scripts/verify_public_web_distribution.py --write && python scripts/verify_public_launch_readiness.py --write",
            "requiresOperator": False,
            "proves": "The web bundle, public-web receipt, and public-launch readiness JSON are current after local changes.",
        },
        {
            "label": "Publish current web source",
            "command": "git add <release-impacting paths> && git commit -m \"Prepare Fluxio public launch proof\" && git push",
            "requiresOperator": True,
            "proves": "GitHub Pages can deploy the same source state that the readiness verifier inspected.",
        },
        {
            "label": "Record external publication receipt",
            "command": "python scripts/record_github_release_publication.py --plan --write-plan && python scripts/record_github_release_publication.py --tag <tag>",
            "requiresOperator": True,
            "proves": "The GitHub release candidate attachment plan is complete, then a non-draft external release exists with publication-attachments.json.",
        },
        {
            "label": "Final public launch readiness check",
            "command": "python scripts/verify_public_launch_readiness.py --write --require-ready",
            "requiresOperator": False,
            "proves": "All required public launch checks pass before the UI can claim launch-ready.",
        },
    ]
    publish_order = [
        "Review dirty source lanes and separate release-impacting source from private evidence.",
        "Run build and verifier commands until the readiness JSON reflects the current source state.",
        "Commit and push release-impacting source changes, then wait for the GitHub Pages workflow.",
        "Refresh public-web distribution proof so deployedSha matches local head and the source tree is clean.",
        "Attach one accepted external publication receipt: GitHub release, npm registry, or signed installer.",
        "Rerun public launch readiness with --require-ready before claiming the release is public.",
    ]
    return {
        "schema": "fluxio.public_launch_repair_packet.v1",
        "status": status,
        "canClaimPublicLaunch": bool(ok),
        "internalPacketReady": bool(internal_packet_ready),
        "primaryBlocker": primary_blocker,
        "publicWebUrl": str(public_web.get("url") or ""),
        "workflowRun": str(public_web.get("workflowRun") or ""),
        "gitHead": str(source_state.get("gitHead") or ""),
        "deployedSha": str(source_state.get("deployedSha") or ""),
        "sourceWorkingTreeClean": bool(source_state.get("sourceWorkingTreeClean")),
        "sourceDirtyPathCount": int(dirty_source_triage.get("dirtyPathCount") or source_state.get("sourceDirtyPathCount") or 0),
        "sourceCoverage": str(dirty_source_triage.get("sourceCoverage") or ""),
        "releaseBlockingSampleCount": int(dirty_source_triage.get("releaseBlockingSampleCount") or 0),
        "releaseBlockingPathCount": int(dirty_source_triage.get("releaseBlockingPathCount") or 0),
        "privateOrGeneratedPathCount": int(dirty_source_triage.get("privateOrGeneratedPathCount") or 0),
        "releaseBlockingPaths": [
            str(item)
            for item in dirty_source_triage.get("releaseBlockingPaths", [])
            if str(item or "").strip()
        ][:40] if isinstance(dirty_source_triage.get("releaseBlockingPaths"), list) else [],
        "stagingPlan": staging_plan,
        "orderedLanes": ordered_lanes,
        "publishOrder": publish_order,
        "commands": commands,
        "receiptTargets": receipt_targets,
        "nextAction": next_action,
    }


def _public_launch_staging_proof(payload: dict[str, Any], proof_path: Path) -> dict[str, Any]:
    repair_packet = payload.get("repairPacket", {}) if isinstance(payload.get("repairPacket"), dict) else {}
    staging_plan = (
        repair_packet.get("stagingPlan", {})
        if isinstance(repair_packet.get("stagingPlan"), dict)
        else {}
    )
    return {
        "schema": "fluxio.public_launch_staging_proof.v1",
        "checkedAt": str(payload.get("checkedAt") or ""),
        "status": str(payload.get("status") or "unknown"),
        "canClaimPublicLaunch": bool(repair_packet.get("canClaimPublicLaunch")),
        "internalPacketReady": bool(payload.get("internalPacketReady")),
        "sourceCoverage": str(repair_packet.get("sourceCoverage") or ""),
        "primaryBlocker": str(repair_packet.get("primaryBlocker") or ""),
        "releaseImpactPathCount": int(staging_plan.get("releaseImpactPathCount") or 0),
        "privateOrGeneratedPathCount": int(staging_plan.get("privateOrGeneratedPathCount") or 0),
        "groups": staging_plan.get("groups", []) if isinstance(staging_plan.get("groups"), list) else [],
        "cleanupCommands": (
            staging_plan.get("cleanupCommands", [])
            if isinstance(staging_plan.get("cleanupCommands"), list)
            else []
        ),
        "verifyCommand": str(staging_plan.get("verifyCommand") or ""),
        "commitCommand": str(staging_plan.get("commitCommand") or ""),
        "nextAction": str(staging_plan.get("nextAction") or payload.get("nextAction") or ""),
        "readinessPath": str(proof_path.with_name("latest.json").resolve()),
        "evidencePath": str(proof_path.resolve()),
    }


def _attachment_integrity(root: Path, attachment_manifest: dict[str, Any], archive_root: Path | None) -> dict[str, Any]:
    attachments = (
        attachment_manifest.get("attachments", [])
        if isinstance(attachment_manifest.get("attachments"), list)
        else []
    )
    verified = 0
    failed: list[dict[str, str]] = []
    for item in attachments:
        if not isinstance(item, dict):
            continue
        relative_path = str(item.get("archiveRelativePath") or "").strip()
        expected_sha = str(item.get("sha256") or "").strip()
        if not relative_path or not expected_sha or archive_root is None:
            failed.append({"path": relative_path, "reason": "missing path, archive root, or checksum"})
            continue
        path = archive_root / relative_path
        if not path.exists() or not path.is_file():
            failed.append({"path": str(path), "reason": "missing"})
            continue
        actual_sha = _sha256_file(path)
        if actual_sha != expected_sha:
            failed.append({"path": str(path), "reason": "checksum mismatch"})
            continue
        verified += 1
    return {
        "attachmentCount": len(attachments),
        "verifiedCount": verified,
        "failed": failed,
        "ok": bool(attachments) and not failed and verified == len(attachments),
    }


def verify_public_launch_readiness(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    package = _load_json(root / "package.json")
    scripts = package.get("scripts", {}) if isinstance(package.get("scripts"), dict) else {}
    files = package.get("files", []) if isinstance(package.get("files"), list) else []
    launcher = _load_json(root / ".agent_control" / "launcher_package" / "latest.json")
    public_web = _load_json(root / ".agent_control" / "deployment_evidence" / "public-web.json")
    private_nas = _load_json(root / ".agent_control" / "deployment_evidence" / "private-nas-web.json")
    latest_pointer = _load_json(root / ".agent_control" / "release_artifacts" / "latest.json")

    release_candidate_path = _resolve_declared_path(root, latest_pointer.get("releaseCandidatePath"))
    publication_manifest_path = _resolve_declared_path(root, latest_pointer.get("publicationManifestPath"))
    attachment_manifest_path = _resolve_declared_path(root, latest_pointer.get("publicationAttachmentManifestPath"))
    archive_root = _resolve_declared_path(root, latest_pointer.get("archiveRoot"))

    release_candidate = _load_json(release_candidate_path) if release_candidate_path else {}
    publication_manifest = _load_json(publication_manifest_path) if publication_manifest_path else {}
    attachment_manifest = _load_json(attachment_manifest_path) if attachment_manifest_path else {}
    npm_registry = _load_json(root / ".agent_control" / "publication" / "npm-registry.json")
    signed_installer = _load_json(root / ".agent_control" / "publication" / "signed-installer.json")
    github_release = _load_json(root / ".agent_control" / "publication" / "github-release.json")
    github_release_plan = _load_json(root / ".agent_control" / "publication" / "github-release-plan.json")
    attachment_integrity = _attachment_integrity(root, attachment_manifest, archive_root)
    expected_attachment_name = Path(str(attachment_manifest_path or "publication-attachments.json")).name
    github_assets = github_release.get("assets", []) if isinstance(github_release.get("assets"), list) else []
    github_release_has_expected_attachment = any(
        isinstance(item, dict)
        and str(item.get("name") or "") == expected_attachment_name
        and int(item.get("size") or 0) > 0
        for item in github_assets
    )

    source_state = public_web.get("sourceState", {}) if isinstance(public_web.get("sourceState"), dict) else {}
    source_dirty_sample = [
        str(item)
        for item in source_state.get("sourceDirtyPathSample", [])
        if str(item or "").strip()
    ] if isinstance(source_state.get("sourceDirtyPathSample"), list) else []
    current_git_dirty_rows = _current_git_dirty_rows(root)
    dirty_source_rows = current_git_dirty_rows or source_dirty_sample
    source_state_for_triage = dict(source_state)
    if current_git_dirty_rows:
        source_state_for_triage["sourceDirtyPathCount"] = len(current_git_dirty_rows)
    dirty_source_triage = _publication_dirty_source_triage(source_state_for_triage, dirty_source_rows)
    public_web_current = bool(
        public_web.get("publicationCurrent")
        and source_state.get("deployedShaMatchesLocalHead")
        and source_state.get("sourceWorkingTreeClean")
    )
    public_publication_proven = bool(
        (
            npm_registry.get("schema") == "fluxio.npm_publication_receipt.v1"
            and npm_registry.get("ok") is True
            and npm_registry.get("package")
        )
        or (
            signed_installer.get("schema") == "fluxio.signed_installer_receipt.v1"
            and signed_installer.get("ok") is True
            and signed_installer.get("artifactPath")
        )
        or (
            github_release.get("schema") == "fluxio.github_release_publication_receipt.v1"
            and github_release.get("ok") is True
            and github_release.get("tagName")
            and github_release.get("url")
            and github_release_has_expected_attachment
        )
    )

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        "launcher_package_current",
        launcher.get("schema") == "fluxio.launcher_package_verification.v1"
        and launcher.get("ok") is True
        and launcher.get("entrypoint") == "scripts/fluxio-cli.mjs"
        and int(launcher.get("packedFileCount") or 0) > 0,
        "Launcher receipt proves the npx-style package entrypoint and packed web assets.",
        checkedAt=launcher.get("checkedAt", ""),
        packedFileCount=launcher.get("packedFileCount", 0),
    )
    _check(
        checks,
        "package_public_entrypoint_declared",
        package.get("bin", {}).get("fluxio") == "scripts/fluxio-cli.mjs"
        and "scripts/fluxio-cli.mjs" in files
        and "web/dist" in files
        and "verify:launcher-package" in scripts,
        "package.json exposes the Fluxio command and includes the built web app in package files.",
    )
    _check(
        checks,
        "public_web_reachable",
        public_web.get("schema") == "fluxio.public_web_deployment.v1"
        and public_web.get("ok") is True
        and int(public_web.get("status") or 0) == 200
        and bool(public_web.get("url")),
        "GitHub Pages/public web receipt is reachable.",
        url=public_web.get("url", ""),
        workflowRun=public_web.get("workflowRun", ""),
    )
    _check(
        checks,
        "public_web_current",
        public_web_current,
        "Public web receipt must point at the current source state before public launch can be claimed.",
        publicationCurrent=public_web.get("publicationCurrent", False),
        sourceWorkingTreeClean=source_state.get("sourceWorkingTreeClean", False),
        deployedShaMatchesLocalHead=source_state.get("deployedShaMatchesLocalHead", False),
        sourceDirtyPathCount=source_state.get("sourceDirtyPathCount", 0),
        sourceDirtyPathSample=source_dirty_sample[:20],
        currentGitDirtyPathCount=len(current_git_dirty_rows),
        currentGitDirtyPathSample=current_git_dirty_rows[:20],
        dirtySourceTriage=dirty_source_triage,
    )
    _check(
        checks,
        "private_nas_live_reachable",
        private_nas.get("schema") == "fluxio.private_nas_web_deployment.v1"
        and private_nas.get("ok") is True
        and int(private_nas.get("healthStatus") or 0) == 200
        and int(private_nas.get("controlStatus") or 0) == 200,
        "Private Tailscale NAS web receipt is reachable and login-protected.",
        controlUrl=private_nas.get("controlUrl", ""),
    )
    _check(
        checks,
        "release_packet_attached",
        latest_pointer.get("schema") == "fluxio.latest_release_artifact_pointer.v1"
        and bool(release_candidate)
        and bool(publication_manifest)
        and bool(attachment_manifest),
        "Latest release pointer resolves to release candidate, publication manifest, and attachment manifest.",
        candidateStatus=latest_pointer.get("candidateStatus", ""),
        releaseCandidatePath=str(release_candidate_path or ""),
    )
    _check(
        checks,
        "publication_manifest_ready",
        publication_manifest.get("schema") == "fluxio.public_release_publication_packet.v1"
        and not publication_manifest.get("missing")
        and publication_manifest.get("requiredProof", {}).get("launcherPackage") is True
        and publication_manifest.get("requiredProof", {}).get("privateNasWebDeployment") is True,
        "Publication manifest has required internal proof attached.",
        status=publication_manifest.get("status", ""),
    )
    _check(
        checks,
        "attachment_manifest_integrity",
        attachment_manifest.get("schema") == "fluxio.public_release_attachment_manifest.v1"
        and attachment_manifest.get("status") == "ready_to_attach"
        and attachment_integrity.get("ok") is True,
        "Every declared release attachment exists and matches its sha256.",
        attachmentCount=attachment_integrity.get("attachmentCount", 0),
        verifiedCount=attachment_integrity.get("verifiedCount", 0),
        failed=attachment_integrity.get("failed", []),
    )
    _check(
        checks,
        "external_publication_proven",
        public_publication_proven,
        "A public npm publication receipt, signed installer receipt, or GitHub release/tag receipt is required before claiming full public launch.",
        npmReceiptPresent=bool(npm_registry),
        signedInstallerReceiptPresent=bool(signed_installer),
        githubReleaseReceiptPresent=bool(github_release),
        githubReleasePlanReady=bool(github_release_plan.get("ready")),
        githubReleasePlanTag=github_release_plan.get("tagName", ""),
        githubReleasePlanAssetCount=github_release_plan.get("assetCount", 0),
        githubReleaseHasExpectedAttachment=github_release_has_expected_attachment,
        expectedGitHubReleaseAttachment=expected_attachment_name,
        expectedReceipts=[
            ".agent_control/publication/npm-registry.json",
            ".agent_control/publication/signed-installer.json",
            ".agent_control/publication/github-release.json",
        ],
    )

    missing = [item["checkId"] for item in checks if not item["passed"]]
    packet_ready_missing = [
        item
        for item in missing
        if item
        not in {
            "public_web_current",
            "external_publication_proven",
        }
    ]
    internal_packet_ready = not packet_ready_missing
    ok = not missing
    public_distribution_missing = {
        "public_web_current",
        "external_publication_proven",
    }.issubset(set(missing))
    status = (
        "ready_for_public_launch"
        if ok
        else "public_packet_ready_missing_current_web_and_publication"
        if internal_packet_ready and public_distribution_missing
        else "public_packet_ready_but_source_stale"
        if internal_packet_ready and "public_web_current" in missing
        else "public_packet_ready_missing_external_publication"
        if internal_packet_ready and missing == ["external_publication_proven"]
        else "public_launch_not_ready"
    )
    blockers = [
        {
            "checkId": item["checkId"],
            "details": item["details"],
        }
        for item in checks
        if not item["passed"]
    ]
    next_action = (
        "Public launch is proven; keep the public web, release packet, and publication receipts current."
        if ok
        else "Publish the current source to GitHub Pages, refresh the public-web receipt, then add npm, signed-installer, or GitHub release/tag publication proof."
        if "public_web_current" in missing and "external_publication_proven" in missing
        else "Publish the current source to GitHub Pages and refresh the public-web receipt."
        if "public_web_current" in missing
        else "Add npm registry publication proof, a signed installer receipt, or a GitHub release/tag receipt."
        if "external_publication_proven" in missing
        else "Fix the missing release packet checks, then rerun public launch readiness."
    )
    repair_packet = _public_launch_repair_packet(
        status=status,
        ok=ok,
        internal_packet_ready=internal_packet_ready,
        missing=missing,
        next_action=next_action,
        dirty_source_triage=dirty_source_triage,
        public_web=public_web,
        source_state=source_state,
    )
    payload = {
        "schema": "fluxio.public_launch_readiness.v1",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "ok": ok,
        "status": status,
        "internalPacketReady": internal_packet_ready,
        "checks": checks,
        "missing": missing,
        "blockers": blockers,
        "repairPacket": repair_packet,
        "publicWeb": {
            "url": public_web.get("url", ""),
            "workflowRun": public_web.get("workflowRun", ""),
            "publicationCurrent": public_web.get("publicationCurrent", False),
            "sourceDirtyPathCount": source_state.get("sourceDirtyPathCount", 0),
            "sourceDirtyPathSample": source_dirty_sample[:20],
            "currentGitDirtyPathCount": len(current_git_dirty_rows),
            "currentGitDirtyPathSample": current_git_dirty_rows[:20],
            "dirtySourceTriage": dirty_source_triage,
            "gitHead": source_state.get("gitHead", ""),
            "deployedSha": source_state.get("deployedSha", ""),
            "deployedShaMatchesLocalHead": source_state.get("deployedShaMatchesLocalHead", False),
            "sourceWorkingTreeClean": source_state.get("sourceWorkingTreeClean", False),
        },
        "publicationProof": {
            "npmReceiptPath": str(root / ".agent_control" / "publication" / "npm-registry.json"),
            "signedInstallerReceiptPath": str(root / ".agent_control" / "publication" / "signed-installer.json"),
            "githubReleaseReceiptPath": str(root / ".agent_control" / "publication" / "github-release.json"),
            "githubReleasePlanPath": str(root / ".agent_control" / "publication" / "github-release-plan.json"),
            "npmReceiptPresent": bool(npm_registry),
            "signedInstallerReceiptPresent": bool(signed_installer),
            "githubReleaseReceiptPresent": bool(github_release),
            "githubReleasePlanReady": bool(github_release_plan.get("ready")),
            "githubReleasePlanTag": github_release_plan.get("tagName", ""),
            "githubReleasePlanAssetCount": github_release_plan.get("assetCount", 0),
            "githubReleasePlanCommand": github_release_plan.get("command", ""),
            "githubReleasePlanRecordReceiptCommand": github_release_plan.get("recordReceiptCommand", ""),
            "githubReleaseHasExpectedAttachment": github_release_has_expected_attachment,
            "expectedGitHubReleaseAttachment": expected_attachment_name,
            "acceptedSchemas": [
                "fluxio.npm_publication_receipt.v1",
                "fluxio.signed_installer_receipt.v1",
                "fluxio.github_release_publication_receipt.v1",
            ],
            "nextAction": "Attach a verified npm registry, signed installer, or GitHub release/tag receipt after publishing.",
        },
        "releaseCandidate": {
            "candidateId": release_candidate.get("candidateId", latest_pointer.get("candidateId", "")),
            "status": release_candidate.get("status", latest_pointer.get("candidateStatus", "")),
            "archiveRoot": str(archive_root or ""),
            "releaseCandidatePath": str(release_candidate_path or ""),
            "publicationManifestPath": str(publication_manifest_path or ""),
            "publicationAttachmentManifestPath": str(attachment_manifest_path or ""),
        },
        "nextAction": next_action,
    }
    staging_proof_path = root / ".agent_control" / "public_launch_readiness" / "staging-plan.json"
    payload["repairPacket"]["stagingPlan"]["proofPath"] = str(staging_proof_path.resolve())
    payload["stagingProof"] = _public_launch_staging_proof(payload, staging_proof_path)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Fluxio public launch readiness without overstating internal release packets.")
    parser.add_argument("--root", default=str(ROOT), help="Workspace root")
    parser.add_argument("--write", action="store_true", help="Write .agent_control/public_launch_readiness/latest.json")
    parser.add_argument("--require-ready", action="store_true", help="Exit nonzero unless full public launch readiness is proven")
    args = parser.parse_args(argv)

    payload = verify_public_launch_readiness(Path(args.root))
    if args.write:
        out_dir = Path(args.root) / ".agent_control" / "public_launch_readiness"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "latest.json"
        staging_path = out_dir / "staging-plan.json"
        payload["evidencePath"] = str(out_path.resolve())
        payload["repairPacket"]["stagingPlan"]["proofPath"] = str(staging_path.resolve())
        payload["stagingProof"] = _public_launch_staging_proof(payload, staging_path)
        staging_path.write_text(json.dumps(payload["stagingProof"], indent=2), encoding="utf-8")
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] or not args.require_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
