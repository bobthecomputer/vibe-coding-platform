from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _copy_file(source: Path, target_dir: Path, *, label: str) -> dict:
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    shutil.copy2(source, target)
    return {
        "label": label,
        "sourcePath": str(source),
        "archivePath": str(target),
        "bytes": target.stat().st_size,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_jsonl(path: Path) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    rows: list[dict] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _capture_live_nas_system_audit_snapshot(root: Path) -> Path:
    try:
        from grant_agent.system_audit import build_system_audit
    except ModuleNotFoundError:  # pragma: no cover - local source-tree execution
        from src.grant_agent.system_audit import build_system_audit

    output = root / ".agent_control" / "live_nas_system_audit_latest.json"
    audit = build_system_audit(root)
    wrapper = {
        "schema": "fluxio.live_nas_system_audit_snapshot.v1",
        "ok": True,
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "sourceHost": "archive_release_proofs",
        "sourceRoot": str(root),
        "maxAgeSeconds": 6 * 60 * 60,
        "syncedEvidenceFiles": [],
        "missingEvidenceFiles": [],
        "audit": audit,
        "stderrPreview": "",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(wrapper, indent=2), encoding="utf-8")
    return output


def _latest_files(root: Path, pattern: str, *, limit: int) -> list[Path]:
    return sorted(
        [path for path in root.glob(pattern) if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[:limit]


def _looks_like_long_history_report(path: Path) -> bool:
    name = path.name.lower()
    if "long-history" in name or "long_history" in name:
        return True
    if path.suffix.lower() not in {".json", ".html", ".txt", ".md"}:
        return False
    return "long_history" in path.read_text(encoding="utf-8", errors="ignore")[:2000].lower()


def _looks_like_authenticated_live_report(path: Path) -> bool:
    name = path.name.lower()
    if "authenticated-live-control" in name:
        return True
    if path.suffix.lower() not in {".json", ".html", ".txt", ".md"}:
        return False
    head = path.read_text(encoding="utf-8", errors="ignore")[:4000].lower()
    return "fluxio.authenticated_live_control.v1" in head or "authenticated live control" in head


def _relative_archive_path(archive_root: Path, path: Path) -> str:
    try:
        return path.relative_to(archive_root).as_posix()
    except ValueError:
        return path.as_posix()


def _write_public_release_publication_packet(
    release_candidate_dir: Path,
    *,
    archive_root: Path,
    candidate_id: str,
    created_at: str,
    workspace_root: Path,
    manifest_path: Path,
    release_candidate_path: Path,
    public_web_deployment_artifacts: list[dict],
    private_nas_web_deployment_artifacts: list[dict],
    launcher_package_artifact: dict,
    public_launch_staging_artifact: dict,
    cross_device_receipt_summary: dict,
    self_improvement_summary: dict,
    self_improvement_artifacts: list[dict],
    live_nas_system_audit_artifact: dict,
    missing: list[str],
) -> list[dict]:
    publication_manifest_path = release_candidate_dir / "publication-manifest.json"
    release_notes_path = release_candidate_dir / "public-release-notes.md"
    latest_public_web = public_web_deployment_artifacts[0] if public_web_deployment_artifacts else {}
    public_web_current = bool(public_web_deployment_artifacts) and all(
        bool(item.get("publicationCurrent", True)) for item in public_web_deployment_artifacts
    )
    required_proof_attached = bool(
        public_web_current
        and launcher_package_artifact
        and cross_device_receipt_summary
    )
    status = (
        "ready_for_publication"
        if not missing and required_proof_attached
        else "publication_packet_ready"
        if not missing
        else "incomplete"
    )
    publication_manifest = {
        "schema": "fluxio.public_release_publication_packet.v1",
        "candidateId": candidate_id,
        "createdAt": created_at,
        "status": status,
        "workspaceRoot": str(workspace_root),
        "releaseProofArchive": str(archive_root),
        "releaseProofManifestPath": str(manifest_path),
        "releaseCandidatePath": str(release_candidate_path),
        "publicReleaseNotesPath": str(release_notes_path),
        "latestPublicWebDeployment": latest_public_web,
        "publicWebDeploymentReceipts": public_web_deployment_artifacts,
        "publicWebDeploymentCurrent": public_web_current,
        "privateNasWebDeploymentReceipts": private_nas_web_deployment_artifacts,
        "launcherPackageReceipt": launcher_package_artifact,
        "publicLaunchStagingReceipt": public_launch_staging_artifact,
        "crossDeviceLaunchReceiptSummary": cross_device_receipt_summary,
        "selfImprovementSummary": self_improvement_summary,
        "selfImprovementArtifacts": self_improvement_artifacts,
        "liveNasSystemAuditReceipt": live_nas_system_audit_artifact,
        "requiredProof": {
            "publicWebDeployment": bool(public_web_deployment_artifacts),
            "publicWebDeploymentCurrent": public_web_current,
            "privateNasWebDeployment": bool(private_nas_web_deployment_artifacts),
            "launcherPackage": bool(launcher_package_artifact),
            "publicLaunchStagingProof": bool(public_launch_staging_artifact),
            "crossDeviceLaunchReceipts": bool(cross_device_receipt_summary),
            "selfImprovementEvidence": bool(self_improvement_artifacts),
            "selfImprovementWatchdogTrend": bool(self_improvement_summary.get("trendProven")),
            "liveNasSystemAudit": bool(live_nas_system_audit_artifact),
            "releaseProofManifest": True,
        },
        "missing": missing,
        "publishChecklist": [
            "Review public-release-notes.md.",
            "Attach publication-manifest.json and manifest.json to the public release candidate.",
            "Publish or tag the candidate only after requiredProof values are true.",
            "Keep the proof archive available beside the public release page.",
        ],
        "nextAction": (
            "Publish or tag this release candidate with the publication packet and proof archive attached."
            if not missing and required_proof_attached
            else "Publish the remaining source changes, redeploy Pages, and record a current public web receipt before final tagging."
            if public_web_deployment_artifacts and not public_web_current
            else "Attach the remaining public release proof receipts, then publish or tag this candidate with the packet."
            if not missing
            else "Resolve missing proof artifacts, then rebuild the publication packet."
        ),
    }
    publication_manifest_path.write_text(json.dumps(publication_manifest, indent=2), encoding="utf-8")

    public_url = str(latest_public_web.get("url") or "not attached")
    private_nas_url = str(
        (private_nas_web_deployment_artifacts[0] if private_nas_web_deployment_artifacts else {}).get("controlUrl")
        or "not attached"
    )
    launcher_entrypoint = str(launcher_package_artifact.get("entrypoint") or "not attached")
    receipt_count = int(cross_device_receipt_summary.get("receiptCount") or 0)
    trend_status = str(cross_device_receipt_summary.get("trendStatus") or "missing")
    watchdog_receipt_count = int(self_improvement_summary.get("watchdogReceiptCount") or 0)
    watchdog_completed_count = int(self_improvement_summary.get("watchdogCompletedReceiptCount") or 0)
    release_notes = "\n".join(
        [
            f"# Fluxio Release Candidate {candidate_id}",
            "",
            f"Status: {status}",
            f"Created: {created_at}",
            "",
            "## Public Entry Points",
            "",
            f"- Public web deployment: {public_url}",
            f"- Private NAS web deployment: {private_nas_url}",
            f"- Launcher entrypoint: {launcher_entrypoint}",
            f"- Release proof archive: {archive_root}",
            f"- Release proof manifest: {manifest_path}",
            "",
            "## Proof Summary",
            "",
            f"- Cross-device launch receipts: {receipt_count}",
            f"- Cross-device receipt trend: {trend_status}",
            f"- Self-improvement watchdog receipts: {watchdog_receipt_count}",
            f"- Self-improvement completed watchdog receipts: {watchdog_completed_count}",
            f"- Self-improvement watchdog trend proven: {bool(self_improvement_summary.get('trendProven'))}",
            f"- Public web receipts attached: {len(public_web_deployment_artifacts)}",
            f"- Public web current source: {public_web_current}",
            f"- Private NAS web receipts attached: {len(private_nas_web_deployment_artifacts)}",
            f"- Launcher package attached: {bool(launcher_package_artifact)}",
            f"- Public launch staging proof attached: {bool(public_launch_staging_artifact)}",
            f"- Live NAS audit attached: {bool(live_nas_system_audit_artifact)}",
            "",
            "## Publish Checklist",
            "",
            "- Attach this notes file, publication-manifest.json, release-candidate.json, and manifest.json to the release page.",
            "- Confirm required proof remains attached before tagging or announcing the candidate.",
            "- Keep the archived proof bundle reachable for review.",
            "",
            "## Missing Proof",
            "",
            *(f"- {item}" for item in missing),
        ]
    )
    if not missing:
        release_notes += "- None.\n"
    release_notes_path.write_text(release_notes, encoding="utf-8")

    artifacts = []
    for path, label, schema in [
        (
            publication_manifest_path,
            "public_release_publication_manifest",
            publication_manifest["schema"],
        ),
        (release_notes_path, "public_release_notes", "fluxio.public_release_notes.v1"),
    ]:
        artifacts.append(
            {
                "label": label,
                "sourcePath": str(path),
                "archivePath": str(path),
                "archiveRelativePath": _relative_archive_path(archive_root, path),
                "bytes": path.stat().st_size,
                "schema": schema,
            }
        )
    return artifacts


def _write_publication_attachment_manifest(
    release_candidate_dir: Path,
    *,
    archive_root: Path,
    candidate_id: str,
    created_at: str,
    manifest_path: Path,
    release_candidate_path: Path,
    publication_packet_artifacts: list[dict],
    public_web_deployment_artifacts: list[dict],
    private_nas_web_deployment_artifacts: list[dict],
    launcher_package_artifact: dict,
    public_launch_readiness_artifact: dict,
    public_launch_staging_artifact: dict,
    self_improvement_artifacts: list[dict],
    live_nas_system_audit_artifact: dict,
    cross_device_receipt_summary: dict,
    missing: list[str],
) -> dict:
    attachment_manifest_path = release_candidate_dir / "publication-attachments.json"
    attachment_sources: list[tuple[str, Path]] = [("release_candidate_manifest", release_candidate_path)]
    for artifact in publication_packet_artifacts:
        path = Path(str(artifact.get("archivePath") or artifact.get("sourcePath") or ""))
        if path.exists():
            attachment_sources.append((str(artifact.get("label") or path.stem), path))
    for artifact in [
        *public_web_deployment_artifacts,
        *private_nas_web_deployment_artifacts,
        launcher_package_artifact,
        public_launch_readiness_artifact,
        public_launch_staging_artifact,
        *self_improvement_artifacts,
        live_nas_system_audit_artifact,
    ]:
        archive_path = str(artifact.get("archivePath") or "").strip()
        if not archive_path:
            continue
        path = Path(archive_path)
        if path.exists():
            attachment_sources.append((str(artifact.get("label") or path.stem), path))
    summary_path = archive_root / "cross_device_launch_rehearsals" / "summary.json"
    if cross_device_receipt_summary and summary_path.exists():
        attachment_sources.append(("cross_device_launch_receipt_summary", summary_path))

    seen: set[Path] = set()
    attachments: list[dict] = []
    for label, path in attachment_sources:
        resolved = path.resolve()
        if resolved in seen or not path.exists():
            continue
        seen.add(resolved)
        attachments.append(
            {
                "label": label,
                "archiveRelativePath": _relative_archive_path(archive_root, path),
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )

    attachment_manifest = {
        "schema": "fluxio.public_release_attachment_manifest.v1",
        "candidateId": candidate_id,
        "createdAt": created_at,
        "status": "ready_to_attach" if not missing else "incomplete",
        "releaseProofArchive": str(archive_root),
        "attachmentCount": len(attachments),
        "attachments": attachments,
        "missing": missing,
        "publishInstructions": [
            "Attach every file listed here to the release page or signed release packet.",
            "Verify each attachment sha256 after upload.",
            "Keep manifest.json and publication-attachments.json together so the proof archive can be reconstructed.",
        ],
        "nextAction": (
            "Attach these checksummed files beside the public/signed release candidate."
            if not missing
            else "Resolve missing required proof artifacts, then rebuild this attachment manifest."
        ),
    }
    attachment_manifest_path.write_text(json.dumps(attachment_manifest, indent=2), encoding="utf-8")
    return {
        "label": "public_release_attachment_manifest",
        "sourcePath": str(attachment_manifest_path),
        "archivePath": str(attachment_manifest_path),
        "archiveRelativePath": _relative_archive_path(archive_root, attachment_manifest_path),
        "bytes": attachment_manifest_path.stat().st_size,
        "schema": attachment_manifest["schema"],
        "attachmentCount": attachment_manifest["attachmentCount"],
    }


def _write_latest_release_artifact_pointer(root: Path, manifest: dict, release_candidate: dict) -> Path:
    latest_path = root / ".agent_control" / "release_artifacts" / "latest.json"
    latest = {
        "schema": "fluxio.latest_release_artifact_pointer.v1",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "archiveRoot": manifest.get("archiveRoot", ""),
        "manifestPath": manifest.get("manifestPath", ""),
        "candidateId": release_candidate.get("candidateId", ""),
        "candidateStatus": release_candidate.get("status", ""),
        "releaseCandidatePath": str(
            Path(str(manifest.get("archiveRoot") or ""))
            / "release_candidate"
            / "release-candidate.json"
        ),
        "publicationManifestPath": release_candidate.get("publicationManifestPath", ""),
        "publicationAttachmentManifestPath": release_candidate.get("publicationAttachmentManifestPath", ""),
        "publicReleaseNotesPath": release_candidate.get("publicReleaseNotesPath", ""),
        "ok": bool(manifest.get("ok")),
        "counts": manifest.get("counts", {}),
        "nextAction": release_candidate.get("nextAction") or manifest.get("nextAction") or "",
    }
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(json.dumps(latest, indent=2), encoding="utf-8")
    return latest_path


def build_release_proof_archive(
    root: Path,
    *,
    output_dir: Path | None = None,
    require_long_history: bool = False,
    require_proof_digest: bool = False,
    require_authenticated_live: bool = False,
    require_parallel_dispatch: bool = False,
    require_cross_device_launch_receipts: bool = False,
    require_public_web_deployment: bool = False,
    require_publication_packet: bool = False,
    capture_live_nas_system_audit: bool = False,
) -> dict:
    root = root.resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_root = output_dir.resolve() if output_dir else root / ".agent_control" / "release_artifacts" / stamp
    manifest_path = archive_root / "manifest.json"
    copied: list[dict] = []
    missing: list[str] = []

    audit_path = root / "docs" / "SYSTEM_GAP_ANALYSIS.current.md"
    if audit_path.exists():
        copied.append(_copy_file(audit_path, archive_root / "audit", label="system_audit_current"))
    else:
        missing.append("docs/SYSTEM_GAP_ANALYSIS.current.md")

    proof_digest_files = _latest_files(root / ".agent_control" / "proof_digests", "*.md", limit=8)
    if proof_digest_files:
        for path in proof_digest_files:
            copied.append(_copy_file(path, archive_root / "proof_digests", label="mission_proof_digest"))
    elif require_proof_digest:
        missing.append(".agent_control/proof_digests/*.md")

    self_improvement_path = root / ".agent_control" / "self_improvement_evidence" / "latest.json"
    self_improvement_watchdog_latest_path = (
        root / ".agent_control" / "self_improvement_evidence" / "watchdog_latest.json"
    )
    self_improvement_watchdog_history_path = (
        root / ".agent_control" / "self_improvement_evidence" / "watchdog_history.jsonl"
    )
    self_improvement_artifacts: list[dict] = []
    if self_improvement_path.exists():
        self_improvement_artifacts.append(
            _copy_file(self_improvement_path, archive_root / "self_improvement", label="self_improvement_evidence")
        )
    if self_improvement_watchdog_latest_path.exists():
        self_improvement_artifacts.append(
            _copy_file(
                self_improvement_watchdog_latest_path,
                archive_root / "self_improvement",
                label="self_improvement_watchdog_latest",
            )
        )
    watchdog_history_rows = [
        row
        for row in _load_jsonl(self_improvement_watchdog_history_path)
        if row.get("schema") == "fluxio.self_improvement_watchdog_cadence.v1"
    ]
    watchdog_completed_rows = [row for row in watchdog_history_rows if row.get("status") == "completed"]
    if self_improvement_watchdog_history_path.exists():
        self_improvement_artifacts.append(
            _copy_file(
                self_improvement_watchdog_history_path,
                archive_root / "self_improvement",
                label="self_improvement_watchdog_history",
            )
        )
    self_improvement_summary = {
        "schema": "fluxio.self_improvement_release_archive_summary.v1",
        "latestEvidenceAttached": self_improvement_path.exists(),
        "watchdogLatestAttached": self_improvement_watchdog_latest_path.exists(),
        "watchdogHistoryAttached": self_improvement_watchdog_history_path.exists(),
        "watchdogReceiptCount": len(watchdog_history_rows),
        "watchdogCompletedReceiptCount": len(watchdog_completed_rows),
        "trendProven": len(watchdog_completed_rows) >= 3,
        "nextAction": (
            "Publish or tag the release candidate with the self-improvement trend proof attached."
            if len(watchdog_completed_rows) >= 3
            else "Let the watchdog collect at least three completed self-improvement receipts before publication."
        ),
    }
    if self_improvement_artifacts:
        summary_path = archive_root / "self_improvement" / "summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(self_improvement_summary, indent=2), encoding="utf-8")
        self_improvement_artifacts.append(
            {
                "label": "self_improvement_release_summary",
                "sourcePath": str(summary_path),
                "archivePath": str(summary_path),
                "archiveRelativePath": _relative_archive_path(archive_root, summary_path),
                "bytes": summary_path.stat().st_size,
                "schema": self_improvement_summary["schema"],
            }
        )
        copied.extend(self_improvement_artifacts)

    live_nas_system_audit_path = root / ".agent_control" / "live_nas_system_audit_latest.json"
    if capture_live_nas_system_audit:
        live_nas_system_audit_path = _capture_live_nas_system_audit_snapshot(root)
    live_nas_system_audit_artifact: dict = {}
    if live_nas_system_audit_path.exists():
        live_nas_system_audit_artifact = _copy_file(
            live_nas_system_audit_path,
            archive_root / "live_nas_system_audit",
            label="live_nas_system_audit",
        )
        payload = _load_json(live_nas_system_audit_path)
        live_nas_system_audit_artifact["schema"] = payload.get("schema", "")
        live_nas_system_audit_artifact["checkedAt"] = payload.get("checkedAt", "")
        live_nas_system_audit_artifact["sourceRoot"] = payload.get("sourceRoot", "")
        live_nas_system_audit_artifact["syncedEvidenceFiles"] = payload.get("syncedEvidenceFiles", [])
        copied.append(live_nas_system_audit_artifact)

    parallel_dispatch_path = root / ".agent_control" / "parallel_dispatch_evidence" / "latest.json"
    if parallel_dispatch_path.exists():
        copied.append(
            _copy_file(
                parallel_dispatch_path,
                archive_root / "parallel_dispatch",
                label="parallel_dispatch_evidence",
            )
        )
    elif require_parallel_dispatch:
        missing.append(".agent_control/parallel_dispatch_evidence/latest.json")

    cross_device_receipts_dir = root / ".agent_control" / "cross_device_launch_rehearsals"
    cross_device_receipts_path = cross_device_receipts_dir / "receipts.jsonl"
    cross_device_latest_path = cross_device_receipts_dir / "latest.json"
    cross_device_receipts = [
        row
        for row in _load_jsonl(cross_device_receipts_path)
        if row.get("schema") == "fluxio.cross_device_launch_rehearsal_receipt.v1"
    ]
    cross_device_launch_artifacts: list[dict] = []
    cross_device_status_counts: dict[str, int] = {}
    cross_device_workspace_ids: set[str] = set()
    cross_device_mission_ids: set[str] = set()
    for receipt in cross_device_receipts:
        status = str(receipt.get("status") or "unknown")
        cross_device_status_counts[status] = cross_device_status_counts.get(status, 0) + 1
        workspace_id = str(receipt.get("workspaceId") or "")
        mission_id = str(receipt.get("missionId") or "")
        if workspace_id:
            cross_device_workspace_ids.add(workspace_id)
        if mission_id:
            cross_device_mission_ids.add(mission_id)
    if cross_device_receipts:
        if cross_device_receipts_path.exists():
            cross_device_launch_artifacts.append(
                _copy_file(
                    cross_device_receipts_path,
                    archive_root / "cross_device_launch_rehearsals",
                    label="cross_device_launch_receipts",
                )
            )
        if cross_device_latest_path.exists():
            cross_device_launch_artifacts.append(
                _copy_file(
                    cross_device_latest_path,
                    archive_root / "cross_device_launch_rehearsals",
                    label="cross_device_launch_latest_receipt",
                )
            )
        receipt_summary = {
            "schema": "fluxio.cross_device_launch_release_proof.v1",
            "receiptCount": len(cross_device_receipts),
            "workspaceCount": len(cross_device_workspace_ids),
            "missionCount": len(cross_device_mission_ids),
            "statusCounts": cross_device_status_counts,
            "trendStatus": "repeated" if len(cross_device_receipts) >= 2 else "single",
            "latestReceiptId": str(
                sorted(cross_device_receipts, key=lambda row: str(row.get("generatedAt") or ""))[-1].get("receiptId")
                or ""
            ),
            "nextAction": (
                "Publish this release candidate with repeated cross-device launch proof attached."
                if len(cross_device_receipts) >= 2
                else "Record one more cross-device launch rehearsal receipt before treating this as a trend."
            ),
        }
        summary_path = archive_root / "cross_device_launch_rehearsals" / "summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(receipt_summary, indent=2), encoding="utf-8")
        cross_device_launch_artifacts.append(
            {
                "label": "cross_device_launch_receipt_summary",
                "sourcePath": str(summary_path),
                "archivePath": str(summary_path),
                "bytes": summary_path.stat().st_size,
                "schema": receipt_summary["schema"],
                "receiptCount": receipt_summary["receiptCount"],
                "trendStatus": receipt_summary["trendStatus"],
            }
        )
        copied.extend(cross_device_launch_artifacts)
    elif require_cross_device_launch_receipts:
        missing.append(".agent_control/cross_device_launch_rehearsals/receipts.jsonl")

    launcher_package_path = root / ".agent_control" / "launcher_package" / "latest.json"
    launcher_package_artifact: dict = {}
    if launcher_package_path.exists():
        launcher_package_artifact = _copy_file(
            launcher_package_path,
            archive_root / "launcher_package",
            label="launcher_package_verification",
        )
        payload = _load_json(launcher_package_path)
        launcher_package_artifact["schema"] = payload.get("schema", "")
        launcher_package_artifact["entrypoint"] = payload.get("entrypoint", "")
        launcher_package_artifact["packedFileCount"] = payload.get("packedFileCount", 0)
        copied.append(launcher_package_artifact)

    public_launch_readiness_path = root / ".agent_control" / "public_launch_readiness" / "latest.json"
    public_launch_readiness_artifact: dict = {}
    if public_launch_readiness_path.exists():
        public_launch_readiness_artifact = _copy_file(
            public_launch_readiness_path,
            archive_root / "public_launch_readiness",
            label="public_launch_readiness",
        )
        payload = _load_json(public_launch_readiness_path)
        public_launch_readiness_artifact["schema"] = payload.get("schema", "")
        public_launch_readiness_artifact["status"] = payload.get("status", "")
        public_launch_readiness_artifact["ok"] = payload.get("ok", False)
        public_launch_readiness_artifact["internalPacketReady"] = payload.get("internalPacketReady", False)
        copied.append(public_launch_readiness_artifact)

    public_launch_staging_path = root / ".agent_control" / "public_launch_readiness" / "staging-plan.json"
    public_launch_staging_artifact: dict = {}
    if public_launch_staging_path.exists():
        public_launch_staging_artifact = _copy_file(
            public_launch_staging_path,
            archive_root / "public_launch_readiness",
            label="public_launch_staging_proof",
        )
        payload = _load_json(public_launch_staging_path)
        public_launch_staging_artifact["schema"] = payload.get("schema", "")
        public_launch_staging_artifact["status"] = payload.get("status", "")
        public_launch_staging_artifact["sourceCoverage"] = payload.get("sourceCoverage", "")
        public_launch_staging_artifact["releaseImpactPathCount"] = payload.get("releaseImpactPathCount", 0)
        public_launch_staging_artifact["privateOrGeneratedPathCount"] = payload.get("privateOrGeneratedPathCount", 0)
        copied.append(public_launch_staging_artifact)

    browser_report_files: list[Path] = []
    checks_root = root / "tmp-ui-checks"
    if checks_root.exists():
        browser_report_files.extend(_latest_files(checks_root, "**/*-check.json", limit=12))
        browser_report_files.extend(_latest_files(checks_root, "**/*phone.html", limit=4))
        browser_report_files.extend(_latest_files(checks_root, "**/*tablet.html", limit=4))
        browser_report_files.extend(_latest_files(checks_root, "**/*desktop.html", limit=4))
        browser_report_files.extend(_latest_files(checks_root, "**/*phone.png", limit=4))
        browser_report_files.extend(_latest_files(checks_root, "**/*tablet.png", limit=4))
        browser_report_files.extend(_latest_files(checks_root, "**/*desktop.png", limit=4))
    long_history_reports = [path for path in browser_report_files if _looks_like_long_history_report(path)]
    authenticated_live_reports = [path for path in browser_report_files if _looks_like_authenticated_live_report(path)]
    if long_history_reports:
        seen: set[Path] = set()
        for path in browser_report_files:
            if path in seen:
                continue
            seen.add(path)
            copied.append(_copy_file(path, archive_root / "browser_reports", label="browser_release_report"))
    elif require_long_history:
        missing.append("tmp-ui-checks/**/*long-history* report")
    if authenticated_live_reports:
        seen: set[Path] = set()
        for path in authenticated_live_reports:
            if path in seen:
                continue
            seen.add(path)
            copied.append(
                _copy_file(
                    path,
                    archive_root / "authenticated_live_control",
                    label="authenticated_live_control",
                )
            )
    elif require_authenticated_live:
        missing.append("tmp-ui-checks/**/*authenticated-live-control* report")

    public_web_deployments = _latest_files(
        root / ".agent_control" / "deployment_evidence",
        "public-web*.json",
        limit=6,
    )
    public_web_deployment_artifacts: list[dict] = []
    if public_web_deployments:
        for path in public_web_deployments:
            artifact = _copy_file(
                path,
                archive_root / "deployment_evidence",
                label="public_web_deployment_receipt",
            )
            payload = _load_json(path)
            artifact["schema"] = payload.get("schema", "")
            artifact["url"] = payload.get("url", "")
            artifact["workflowRun"] = payload.get("workflowRun", "")
            artifact["sha"] = payload.get("sha", "")
            artifact["publicationCurrent"] = payload.get("publicationCurrent", False)
            artifact["sourceState"] = payload.get("sourceState", {})
            public_web_deployment_artifacts.append(artifact)
            copied.append(artifact)
    elif require_public_web_deployment:
        missing.append(".agent_control/deployment_evidence/public-web*.json")

    private_nas_web_deployments = _latest_files(
        root / ".agent_control" / "deployment_evidence",
        "private-nas-web*.json",
        limit=3,
    )
    private_nas_web_deployment_artifacts: list[dict] = []
    if private_nas_web_deployments:
        for path in private_nas_web_deployments:
            artifact = _copy_file(
                path,
                archive_root / "deployment_evidence",
                label="private_nas_web_deployment_receipt",
            )
            payload = _load_json(path)
            artifact["schema"] = payload.get("schema", "")
            artifact["controlUrl"] = payload.get("controlUrl", "")
            artifact["healthUrl"] = payload.get("healthUrl", "")
            artifact["scope"] = payload.get("scope", "")
            artifact["checkedAt"] = payload.get("checkedAt", "")
            artifact["ok"] = payload.get("ok", False)
            private_nas_web_deployment_artifacts.append(artifact)
            copied.append(artifact)

    release_candidate_dir = archive_root / "release_candidate"
    release_candidate_dir.mkdir(parents=True, exist_ok=True)
    release_candidate_path = release_candidate_dir / "release-candidate.json"
    candidate_id = f"release-candidate-{stamp}"
    candidate_created_at = datetime.now(timezone.utc).isoformat()
    cross_device_receipt_summary = (
        _load_json(
            archive_root / "cross_device_launch_rehearsals" / "summary.json",
        )
        if cross_device_launch_artifacts
        else {}
    )
    public_web_deployment_current = bool(public_web_deployment_artifacts) and all(
        bool(item.get("publicationCurrent", True)) for item in public_web_deployment_artifacts
    )
    publication_packet_artifacts = _write_public_release_publication_packet(
        release_candidate_dir,
        archive_root=archive_root,
        candidate_id=candidate_id,
        created_at=candidate_created_at,
        workspace_root=root,
        manifest_path=manifest_path,
        release_candidate_path=release_candidate_path,
        public_web_deployment_artifacts=public_web_deployment_artifacts,
        private_nas_web_deployment_artifacts=private_nas_web_deployment_artifacts,
        launcher_package_artifact=launcher_package_artifact,
        public_launch_staging_artifact=public_launch_staging_artifact,
        cross_device_receipt_summary=cross_device_receipt_summary,
        self_improvement_summary=self_improvement_summary,
        self_improvement_artifacts=self_improvement_artifacts,
        live_nas_system_audit_artifact=live_nas_system_audit_artifact,
        missing=missing,
    )
    if require_publication_packet and len(publication_packet_artifacts) < 2:
        missing.append("release_candidate/publication-manifest.json and public-release-notes.md")

    release_candidate = {
        "schema": "fluxio.release_candidate.v1",
        "candidateId": candidate_id,
        "createdAt": candidate_created_at,
        "workspaceRoot": str(root),
        "releaseProofArchive": str(archive_root),
        "publicReleasePublicationPacketAttached": len(publication_packet_artifacts) >= 2,
        "publicReleaseNotesPath": str(release_candidate_dir / "public-release-notes.md"),
        "publicationManifestPath": str(release_candidate_dir / "publication-manifest.json"),
        "publicationAttachmentManifestPath": str(release_candidate_dir / "publication-attachments.json"),
        "publicReleaseAttachmentManifestAttached": True,
        "publicWebDeploymentAttached": bool(public_web_deployment_artifacts),
        "publicWebDeploymentCurrent": public_web_deployment_current,
        "publicWebDeploymentReceipts": public_web_deployment_artifacts,
        "privateNasWebDeploymentAttached": bool(private_nas_web_deployment_artifacts),
        "privateNasWebDeploymentReceipts": private_nas_web_deployment_artifacts,
        "launcherPackageAttached": bool(launcher_package_artifact),
        "launcherPackageReceipt": launcher_package_artifact,
        "publicLaunchReadinessAttached": bool(public_launch_readiness_artifact),
        "publicLaunchReadinessReceipt": public_launch_readiness_artifact,
        "publicLaunchStagingProofAttached": bool(public_launch_staging_artifact),
        "publicLaunchStagingProofReceipt": public_launch_staging_artifact,
        "selfImprovementAttached": bool(self_improvement_artifacts),
        "selfImprovementSummary": self_improvement_summary,
        "selfImprovementArtifacts": self_improvement_artifacts,
        "liveNasSystemAuditAttached": bool(live_nas_system_audit_artifact),
        "liveNasSystemAuditReceipt": live_nas_system_audit_artifact,
        "crossDeviceLaunchReceiptsAttached": bool(cross_device_launch_artifacts),
        "crossDeviceLaunchReceiptSummary": cross_device_receipt_summary,
        "requiredAttachments": {
            "publicWebDeployment": bool(public_web_deployment_artifacts),
            "publicWebDeploymentCurrent": public_web_deployment_current,
            "privateNasWebDeployment": bool(private_nas_web_deployment_artifacts),
            "launcherPackage": bool(launcher_package_artifact),
            "publicLaunchReadiness": bool(public_launch_readiness_artifact),
            "publicLaunchReady": bool(public_launch_readiness_artifact.get("ok")),
            "publicLaunchStagingProof": bool(public_launch_staging_artifact),
            "crossDeviceLaunchReceipts": bool(cross_device_launch_artifacts),
            "selfImprovementEvidence": bool(self_improvement_artifacts),
            "selfImprovementWatchdogTrend": bool(self_improvement_summary.get("trendProven")),
            "liveNasSystemAudit": bool(live_nas_system_audit_artifact),
            "publicReleasePublicationPacket": len(publication_packet_artifacts) >= 2,
            "releaseProofManifest": str(manifest_path),
        },
        "status": (
            "ready"
            if not missing and public_web_deployment_current
            else "public_web_reachable_but_source_stale"
            if not missing and public_web_deployment_artifacts and not public_web_deployment_current
            else "incomplete"
        ),
        "nextAction": (
            "Publish this candidate with the attached public web deployment receipt and release proof archive."
            if public_web_deployment_artifacts and public_web_deployment_current and not missing
            else "Publish the remaining source changes, redeploy Pages, and record a current public web receipt."
            if public_web_deployment_artifacts and not public_web_deployment_current and not missing
            else "Attach the public web deployment receipt, then rebuild the release candidate manifest."
            if not public_web_deployment_artifacts
            else "Resolve missing required proof artifacts before publishing this candidate."
        ),
    }
    release_candidate_path.write_text(json.dumps(release_candidate, indent=2), encoding="utf-8")
    attachment_manifest_artifact = _write_publication_attachment_manifest(
        release_candidate_dir,
        archive_root=archive_root,
        candidate_id=candidate_id,
        created_at=candidate_created_at,
        manifest_path=manifest_path,
        release_candidate_path=release_candidate_path,
        publication_packet_artifacts=publication_packet_artifacts,
        public_web_deployment_artifacts=public_web_deployment_artifacts,
        private_nas_web_deployment_artifacts=private_nas_web_deployment_artifacts,
        launcher_package_artifact=launcher_package_artifact,
        public_launch_readiness_artifact=public_launch_readiness_artifact,
        public_launch_staging_artifact=public_launch_staging_artifact,
        self_improvement_artifacts=self_improvement_artifacts,
        live_nas_system_audit_artifact=live_nas_system_audit_artifact,
        cross_device_receipt_summary=cross_device_receipt_summary,
        missing=missing,
    )
    copied.extend(publication_packet_artifacts)
    copied.append(attachment_manifest_artifact)
    copied.append(
        {
            "label": "release_candidate_manifest",
            "sourcePath": str(release_candidate_path),
            "archivePath": str(release_candidate_path),
            "bytes": release_candidate_path.stat().st_size,
            "schema": release_candidate["schema"],
        }
    )

    manifest = {
        "schema": "fluxio.release_proof_archive.v1",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "workspaceRoot": str(root),
        "archiveRoot": str(archive_root),
        "counts": {
            "copiedArtifacts": len(copied),
            "proofDigests": len(proof_digest_files),
            "selfImprovementEvidence": 1 if self_improvement_path.exists() else 0,
            "selfImprovementArtifacts": len(self_improvement_artifacts),
            "selfImprovementWatchdogReceipts": len(watchdog_history_rows),
            "selfImprovementWatchdogCompletedReceipts": len(watchdog_completed_rows),
            "liveNasSystemAuditSnapshots": 1 if live_nas_system_audit_artifact else 0,
            "parallelDispatchEvidence": 1 if parallel_dispatch_path.exists() else 0,
            "crossDeviceLaunchReceipts": len(cross_device_receipts),
            "crossDeviceLaunchReceiptArtifacts": len(cross_device_launch_artifacts),
            "launcherPackageReceipts": 1 if launcher_package_artifact else 0,
            "publicLaunchReadinessReceipts": 1 if public_launch_readiness_artifact else 0,
            "publicLaunchStagingProofReceipts": 1 if public_launch_staging_artifact else 0,
            "browserReports": len(browser_report_files),
            "longHistoryReports": len(long_history_reports),
            "authenticatedLiveControlReports": len(authenticated_live_reports),
            "publicWebDeploymentReceipts": len(public_web_deployment_artifacts),
            "privateNasWebDeploymentReceipts": len(private_nas_web_deployment_artifacts),
            "publicReleasePublicationPacketArtifacts": len(publication_packet_artifacts),
            "publicReleaseAttachmentManifestArtifacts": 1,
            "releaseCandidates": 1,
            "missing": len(missing),
        },
        "artifacts": copied,
        "missing": missing,
        "ok": not missing,
        "nextAction": (
            "Release proof archive is complete and a release candidate manifest is attached."
            if not missing and public_web_deployment_artifacts
            else "Release proof archive is complete."
            if not missing
            else "Run the missing proof commands, then re-run this archive step."
        ),
    }
    archive_root.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["manifestPath"] = str(manifest_path)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    latest_path = _write_latest_release_artifact_pointer(root, manifest, release_candidate)
    manifest["latestPointerPath"] = str(latest_path)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archive release proof artifacts for Fluxio validation.")
    parser.add_argument("--root", default=str(ROOT), help="Workspace root")
    parser.add_argument("--output-dir", default="", help="Optional archive directory")
    parser.add_argument("--require-long-history", action="store_true")
    parser.add_argument("--require-proof-digest", action="store_true")
    parser.add_argument("--require-authenticated-live", action="store_true")
    parser.add_argument("--require-parallel-dispatch", action="store_true")
    parser.add_argument("--require-cross-device-launch-receipts", action="store_true")
    parser.add_argument("--require-public-web-deployment", action="store_true")
    parser.add_argument("--require-publication-packet", action="store_true")
    parser.add_argument(
        "--capture-live-nas-system-audit",
        action="store_true",
        help="Write a fresh live_nas_system_audit_latest.json snapshot before archiving.",
    )
    args = parser.parse_args(argv)

    manifest = build_release_proof_archive(
        Path(args.root),
        output_dir=Path(args.output_dir) if args.output_dir else None,
        require_long_history=args.require_long_history,
        require_proof_digest=args.require_proof_digest,
        require_authenticated_live=args.require_authenticated_live,
        require_parallel_dispatch=args.require_parallel_dispatch,
        require_cross_device_launch_receipts=args.require_cross_device_launch_receipts,
        require_public_web_deployment=args.require_public_web_deployment,
        require_publication_packet=args.require_publication_packet,
        capture_live_nas_system_audit=args.capture_live_nas_system_audit,
    )
    print(json.dumps(manifest, indent=2))
    return 0 if manifest["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
