from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import ssl
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

try:
    from scripts.verify_github_action_runtimes import verify_github_action_runtimes
except ModuleNotFoundError:  # pragma: no cover - supports direct script execution.
    from verify_github_action_runtimes import verify_github_action_runtimes


ROOT = Path(__file__).resolve().parents[1]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _fetch_text(url: str, *, timeout: int) -> tuple[int, str]:
    context = ssl.create_default_context()
    request = Request(url, headers={"User-Agent": "fluxio-public-web-verifier/1.0"})
    with urlopen(request, timeout=timeout, context=context) as response:
        status = int(getattr(response, "status", 0) or 0)
        text = response.read(500_000).decode("utf-8", "replace")
    return status, text[:2000]


def _gh_api_json(path: str) -> dict:
    if not shutil.which("gh"):
        return {}
    try:
        completed = subprocess.run(
            ["gh", "api", path],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return {}
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


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


def _local_source_state(root: Path, *, deployed_sha: str) -> dict:
    git_head = _git_output(root, ["rev-parse", "HEAD"])
    status_text = _git_output(
        root,
        [
            "status",
            "--short",
            "--",
            ".",
            ":!.agent_control",
            ":!tmp-ui-checks",
            ":!*.tgz",
            ":!*.zip",
        ],
    )
    dirty_paths = [line for line in status_text.splitlines() if line.strip()]
    return {
        "gitHead": git_head,
        "deployedSha": deployed_sha,
        "deployedShaMatchesLocalHead": bool(git_head and deployed_sha and git_head == deployed_sha),
        "sourceWorkingTreeClean": not dirty_paths,
        "sourceDirtyPathCount": len(dirty_paths),
        "sourceDirtyPathSample": dirty_paths[:20],
        "ignoredPrivateControlEvidence": True,
    }


def record_live_pages_deployment_receipt(
    root: Path,
    *,
    repo: str,
    run_id: str = "",
    sha: str = "",
    timeout: int = 20,
) -> dict:
    root = root.resolve()
    pages = _gh_api_json(f"repos/{repo}/pages")
    html_url = str(pages.get("html_url") or "").strip()
    status = 0
    head = ""
    error = ""
    if html_url:
        try:
            status, head = _fetch_text(html_url, timeout=timeout)
        except (OSError, TimeoutError, URLError) as exc:
            error = f"{type(exc).__name__}: {exc}"
    checks = [
        {
            "checkId": "github_pages_enabled",
            "passed": bool(html_url) and pages.get("build_type") == "workflow",
            "details": f"GitHub Pages html_url is {html_url or 'missing'}.",
        },
        {
            "checkId": "public_url_reachable",
            "passed": status == 200 and ("<html" in head.lower() or "Fluxio" in head),
            "details": f"GET {html_url or 'missing'} returned {status}.",
        },
    ]
    source_state = _local_source_state(root, deployed_sha=sha)
    checks.extend(
        [
            {
                "checkId": "deployed_sha_matches_local_head",
                "passed": bool(source_state.get("deployedShaMatchesLocalHead")),
                "details": (
                    f"deployedSha={source_state.get('deployedSha') or 'missing'}; "
                    f"localHead={source_state.get('gitHead') or 'missing'}."
                ),
            },
            {
                "checkId": "source_working_tree_clean",
                "passed": bool(source_state.get("sourceWorkingTreeClean")),
                "details": (
                    "Working tree has no unpublished source changes."
                    if source_state.get("sourceWorkingTreeClean")
                    else f"Working tree has {source_state.get('sourceDirtyPathCount')} unpublished source path(s)."
                ),
                "blockingForReachability": False,
            },
        ]
    )
    missing = [item["checkId"] for item in checks if not item["passed"]]
    blocking_missing = [
        item["checkId"]
        for item in checks
        if not item["passed"] and item.get("blockingForReachability", True)
    ]
    workflow_run = f"https://github.com/{repo}/actions/runs/{run_id}" if run_id else ""
    receipt = {
        "schema": "fluxio.public_web_deployment.v1",
        "provider": "github_pages",
        "url": html_url,
        "workflowRun": workflow_run,
        "sha": sha,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "repo": repo,
        "ok": not blocking_missing,
        "publicationCurrent": not missing,
        "status": status,
        "sourceState": source_state,
        "buildType": pages.get("build_type", ""),
        "public": bool(pages.get("public")),
        "checks": checks,
        "missing": missing,
        "blockingMissing": blocking_missing,
        "error": error,
        "nextAction": (
            "Attach this public web deployment receipt to the release candidate."
            if not missing
            else "Public URL is reachable, but unpublished source changes remain; publish those changes before claiming the public URL is the current release."
            if not blocking_missing
            else "Enable GitHub Pages workflow deployment or rerun the deploy workflow, then record this receipt again."
        ),
    }
    evidence_path = root / ".agent_control" / "deployment_evidence" / "public-web.json"
    candidate_path = root / ".agent_control" / "release_candidates" / "public-web" / "release-candidate.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    candidate = {
        "schema": "fluxio.release_candidate.v1",
        "candidateId": f"public-web-{run_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "createdAt": receipt["createdAt"],
        "publicWebDeploymentAttached": not blocking_missing,
        "publicWebDeploymentCurrent": not missing,
        "publicWebDeploymentReceipt": str(evidence_path),
        "publicWebUrl": html_url,
        "workflowRun": workflow_run,
        "sha": sha,
        "nextAction": (
            "Attach this release candidate receipt to the full release proof archive."
            if not missing
            else "Public URL is live, but source parity is incomplete; publish the remaining source changes before final release."
            if not blocking_missing
            else "Fix public Pages deployment, then rebuild this candidate receipt."
        ),
    }
    candidate_path.write_text(json.dumps(candidate, indent=2), encoding="utf-8")
    receipt["evidencePath"] = str(evidence_path)
    receipt["releaseCandidatePath"] = str(candidate_path)
    return receipt


def verify_public_web_distribution(root: Path, *, require_built_dist: bool = False) -> dict:
    root = root.resolve()
    workflow_text = _read_text(root / ".github" / "workflows" / "web-pages.yml")
    package_payload = _load_json(root / "package.json")
    scripts = package_payload.get("scripts", {}) if isinstance(package_payload.get("scripts"), dict) else {}
    manifest_payload = _load_json(root / "web" / "public" / "manifest.webmanifest")
    service_worker_text = _read_text(root / "web" / "public" / "service-worker.js")
    offline_text = _read_text(root / "web" / "public" / "offline.html")
    action_runtime_guard = verify_github_action_runtimes(root)

    checks = [
        {
            "checkId": "github_pages_workflow",
            "passed": all(
                snippet in workflow_text
                for snippet in (
                    "workflow_dispatch",
                    "permissions:",
                    "pages: write",
                    "id-token: write",
                    "npm run frontend:build",
                    "npm run verify:web-distribution",
                    "actions/upload-pages-artifact",
                    "actions/deploy-pages",
                    "path: web/dist",
                    "github-pages",
                    "page_url",
                )
            ),
            "details": "GitHub Pages workflow builds, verifies, uploads, and deploys web/dist.",
        },
        {
            "checkId": "public_deployment_evidence",
            "passed": all(
                snippet in workflow_text
                for snippet in (
                    "fluxio.public_web_deployment.v1",
                    "steps.deployment.outputs.page_url",
                    "github.sha",
                    "github.run_id",
                    "actions/upload-artifact",
                    "fluxio-public-web-release-candidate",
                    ".agent_control/deployment_evidence/public-web.json",
                    "fluxio.release_candidate.v1",
                    ".agent_control/release_candidates/public-web/release-candidate.json",
                )
            ),
            "details": "Pages deployment records the deployed URL, commit, workflow run, and release-candidate attachment as an artifact.",
        },
        {
            "checkId": "github_action_runtime_guard",
            "passed": bool(action_runtime_guard.get("ok")),
            "details": (
                "Workflow actions satisfy the Node 24-compatible runtime guard "
                f"({action_runtime_guard.get('checkedActionRefCount', 0)} refs checked)."
                if action_runtime_guard.get("ok")
                else "Workflow actions include stale majors that can reintroduce Node 20 runner warnings."
            ),
            "runtimeGuard": {
                "schema": action_runtime_guard.get("schema"),
                "workflowCount": action_runtime_guard.get("workflowCount", 0),
                "checkedActionRefCount": action_runtime_guard.get("checkedActionRefCount", 0),
                "violations": action_runtime_guard.get("violations", []),
            },
        },
        {
            "checkId": "package_scripts",
            "passed": all(
                name in scripts
                for name in (
                    "frontend:build",
                    "web:backend",
                    "web:serve",
                    "verify:pwa",
                    "verify:web-distribution",
                )
            ),
            "details": "Package scripts expose local serving plus PWA and web distribution verification.",
        },
        {
            "checkId": "installable_pwa",
            "passed": bool(
                manifest_payload.get("name")
                and manifest_payload.get("start_url")
                and manifest_payload.get("display") in {"standalone", "fullscreen", "minimal-ui"}
                and "offline" in service_worker_text.lower()
                and "<html" in offline_text.lower()
            ),
            "details": "PWA manifest, service worker, and offline fallback are present.",
        },
        {
            "checkId": "built_dist",
            "passed": (root / "web" / "dist" / "index.html").exists() or not require_built_dist,
            "details": "web/dist/index.html exists after the frontend build.",
        },
    ]
    missing = [item["checkId"] for item in checks if not item["passed"]]
    return {
        "schema": "fluxio.public_web_distribution.v1",
        "root": str(root),
        "ok": not missing,
        "checks": checks,
        "missing": missing,
        "nextAction": (
            "Public web distribution contract is ready for GitHub Pages deployment with URL evidence capture."
            if not missing
            else "Fix the missing public web distribution checks, then rerun this verifier."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Fluxio public web distribution contract.")
    parser.add_argument("--root", default=str(ROOT), help="Workspace root")
    parser.add_argument("--require-built-dist", action="store_true")
    parser.add_argument("--record-live-pages", action="store_true")
    parser.add_argument("--repo", default="bobthecomputer/vibe-coding-platform")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--sha", default="")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args(argv)

    if args.record_live_pages:
        result = record_live_pages_deployment_receipt(
            Path(args.root),
            repo=args.repo,
            run_id=args.run_id,
            sha=args.sha,
            timeout=args.timeout,
        )
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1

    result = verify_public_web_distribution(
        Path(args.root),
        require_built_dist=args.require_built_dist,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
