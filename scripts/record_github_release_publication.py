from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
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
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        return candidate.resolve()
    except OSError:
        return candidate


def _git_output(root: Path, args: list[str]) -> str:
    if not shutil.which("git"):
        return ""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout.strip()


def _quote_shell_arg(value: str) -> str:
    return json.dumps(str(value))


def _repo_from_remote(remote: str) -> str:
    text = remote.strip()
    patterns = (
        r"github\.com[:/](?P<repo>[^/]+/[^/.]+)(?:\.git)?$",
        r"https?://github\.com/(?P<repo>[^/]+/[^/.]+)(?:\.git)?$",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group("repo")
    return ""


def _default_release_tag(latest_pointer: dict[str, Any]) -> str:
    candidate_id = str(latest_pointer.get("candidateId") or "").strip()
    if candidate_id.startswith("release-candidate-"):
        return "fluxio-" + candidate_id.removeprefix("release-candidate-")
    archive_root = Path(str(latest_pointer.get("archiveRoot") or ""))
    if archive_root.name:
        return "fluxio-" + archive_root.name
    return ""


def _release_asset_summary(assets: object) -> list[dict[str, Any]]:
    rows = assets if isinstance(assets, list) else []
    summary: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        summary.append(
            {
                "name": str(item.get("name") or ""),
                "size": int(item.get("size") or 0),
                "url": str(item.get("url") or item.get("browser_download_url") or ""),
            }
        )
    return summary


def build_github_release_publication_plan(
    root: Path,
    *,
    repo: str = "",
    tag: str = "",
) -> dict[str, Any]:
    root = root.resolve()
    if not repo:
        repo = _repo_from_remote(_git_output(root, ["remote", "get-url", "origin"]))
    latest_pointer = _load_json(root / ".agent_control" / "release_artifacts" / "latest.json")
    if not tag:
        tag = _default_release_tag(latest_pointer)
    release_candidate_path = _resolve_declared_path(root, latest_pointer.get("releaseCandidatePath"))
    publication_manifest_path = _resolve_declared_path(root, latest_pointer.get("publicationManifestPath"))
    attachment_manifest_path = _resolve_declared_path(root, latest_pointer.get("publicationAttachmentManifestPath"))
    public_notes_path = _resolve_declared_path(root, latest_pointer.get("publicReleaseNotesPath"))
    candidate_paths = [
        ("release_candidate", release_candidate_path),
        ("publication_manifest", publication_manifest_path),
        ("publication_attachments", attachment_manifest_path),
        ("public_release_notes", public_notes_path),
    ]
    assets: list[dict[str, Any]] = []
    missing: list[str] = []
    for label, path in candidate_paths:
        if path is None:
            missing.append(label)
            continue
        if not path.exists() or not path.is_file():
            missing.append(str(path))
            continue
        assets.append(
            {
                "label": label,
                "path": str(path),
                "name": path.name,
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    git_head = _git_output(root, ["rev-parse", "HEAD"])
    title = f"Fluxio release candidate {tag}" if tag else "Fluxio release candidate"
    create_parts = [
        "gh",
        "release",
        "create",
        tag or "<tag>",
        "--repo",
        repo or "<owner/repo>",
        "--title",
        title,
    ]
    if git_head:
        create_parts.extend(["--target", git_head])
    if public_notes_path is not None:
        create_parts.extend(["--notes-file", str(public_notes_path)])
    command = " ".join(_quote_shell_arg(part) for part in create_parts)
    if assets:
        command += " " + " ".join(_quote_shell_arg(item["path"]) for item in assets)
    expected_attachment_name = Path(str(attachment_manifest_path or "publication-attachments.json")).name
    has_expected_attachment = any(item["name"] == expected_attachment_name and item["size"] > 0 for item in assets)
    ready = bool(repo and tag and assets and has_expected_attachment and not missing)
    return {
        "schema": "fluxio.github_release_publication_plan.v1",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "repo": repo,
        "tagName": tag,
        "targetCommitish": git_head,
        "expectedAttachmentManifestName": expected_attachment_name,
        "expectedAttachmentManifestReady": has_expected_attachment,
        "assetCount": len(assets),
        "assets": assets,
        "missing": missing,
        "ready": ready,
        "command": command,
        "recordReceiptCommand": (
            f"python scripts/record_github_release_publication.py --tag {tag}"
            + (f" --repo {repo}" if repo else "")
            if tag
            else "python scripts/record_github_release_publication.py --tag <tag>"
        ),
        "nextAction": (
            "Create the GitHub release with the command, then run the receipt command and public launch verifier."
            if ready
            else "Rebuild the release proof archive before creating the GitHub release; required attachment files are missing."
        ),
    }


def build_github_release_publication_receipt(
    root: Path,
    *,
    repo: str,
    tag: str,
    release_payload: dict[str, Any],
) -> dict[str, Any]:
    root = root.resolve()
    assets = _release_asset_summary(release_payload.get("assets"))
    attachment_manifest = _load_json(
        root / ".agent_control" / "release_artifacts" / "latest.json"
    )
    expected_attachment_path = str(attachment_manifest.get("publicationAttachmentManifestPath") or "")
    expected_attachment_name = Path(expected_attachment_path).name if expected_attachment_path else "publication-attachments.json"
    attached_asset = next(
        (
            asset
            for asset in assets
            if str(asset.get("name") or "").strip() == expected_attachment_name
            and int(asset.get("size") or 0) > 0
        ),
        None,
    )
    receipt = {
        "schema": "fluxio.github_release_publication_receipt.v1",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "repo": repo,
        "tagName": str(release_payload.get("tagName") or tag),
        "url": str(release_payload.get("url") or ""),
        "targetCommitish": str(release_payload.get("targetCommitish") or ""),
        "isDraft": bool(release_payload.get("isDraft")),
        "isPrerelease": bool(release_payload.get("isPrerelease")),
        "createdAt": str(release_payload.get("createdAt") or ""),
        "publishedAt": str(release_payload.get("publishedAt") or ""),
        "attachmentCount": len(assets),
        "assets": assets[:40],
        "expectedAttachmentManifestPath": expected_attachment_path,
        "expectedAttachmentManifestName": expected_attachment_name,
        "expectedAttachmentManifestAttached": bool(attached_asset),
        "expectedAttachmentManifestAsset": attached_asset or {},
        "ok": bool(release_payload.get("url"))
        and not bool(release_payload.get("isDraft"))
        and bool(str(release_payload.get("tagName") or tag).strip())
        and bool(attached_asset),
        "nextAction": (
            "Attach this GitHub release publication receipt to public launch readiness evidence."
        ),
    }
    if receipt["isDraft"]:
        receipt["nextAction"] = "Publish the draft GitHub release before using it as public launch proof."
    elif not receipt["expectedAttachmentManifestAttached"]:
        receipt["nextAction"] = (
            f"Attach {expected_attachment_name} from the release-candidate proof packet to the GitHub release."
        )
    return receipt


def record_github_release_publication(
    root: Path,
    *,
    repo: str = "",
    tag: str,
) -> dict[str, Any]:
    root = root.resolve()
    if not tag:
        raise ValueError("--tag is required")
    if not repo:
        repo = _repo_from_remote(_git_output(root, ["remote", "get-url", "origin"]))
    if not repo:
        raise ValueError("--repo is required when origin is not a GitHub remote")
    if not shutil.which("gh"):
        raise RuntimeError("GitHub CLI `gh` is required to record a release publication receipt")
    completed = subprocess.run(
        [
            "gh",
            "release",
            "view",
            tag,
            "--repo",
            repo,
            "--json",
            "tagName,url,targetCommitish,isDraft,isPrerelease,createdAt,publishedAt,assets",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub release response was not a JSON object")
    receipt = build_github_release_publication_receipt(
        root,
        repo=repo,
        tag=tag,
        release_payload=payload,
    )
    path = root / ".agent_control" / "publication" / "github-release.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    receipt["evidencePath"] = str(path)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Record a verified GitHub release/tag publication receipt for Fluxio public launch readiness."
    )
    parser.add_argument("--root", default=str(ROOT), help="Workspace root")
    parser.add_argument("--repo", default="", help="GitHub owner/repo, defaults to origin")
    parser.add_argument("--tag", default="", help="GitHub release tag to verify")
    parser.add_argument("--plan", action="store_true", help="Print the GitHub release publication plan instead of reading a live release.")
    parser.add_argument("--write-plan", action="store_true", help="Write the plan to .agent_control/publication/github-release-plan.json.")
    args = parser.parse_args(argv)
    if args.plan:
        plan = build_github_release_publication_plan(
            Path(args.root),
            repo=args.repo,
            tag=args.tag,
        )
        if args.write_plan:
            path = Path(args.root).resolve() / ".agent_control" / "publication" / "github-release-plan.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
            plan["evidencePath"] = str(path)
        print(json.dumps(plan, indent=2))
        return 0 if plan.get("ready") else 1
    if not args.tag:
        raise SystemExit("--tag is required unless --plan is used")
    receipt = record_github_release_publication(
        Path(args.root),
        repo=args.repo,
        tag=args.tag,
    )
    print(json.dumps(receipt, indent=2))
    return 0 if receipt.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
