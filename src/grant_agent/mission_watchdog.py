from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import uuid

from .models import Mission, WorkspaceProfile, utc_now_iso

TERMINAL_STATUSES = {"completed", "failed", "stopped", "archived"}
SCOPE_SAFE = "safe"
SCOPE_UNKNOWN = "unknown"
SCOPE_OVERLAP = "overlap"
ARTIFACT_SCAN_LIMIT = 200
ARTIFACT_SAMPLE_LIMIT = 8
ARTIFACT_PREVIEW_SUFFIXES = {
    ".csv",
    ".gif",
    ".html",
    ".htm",
    ".ipynb",
    ".jpeg",
    ".jpg",
    ".json",
    ".md",
    ".mp4",
    ".pdf",
    ".png",
    ".svg",
    ".webp",
}
ARTIFACT_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
}
PROBLEM_REGISTRY_LIMIT = 200


def _parse_time(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_minutes(value: object, now: datetime) -> int | None:
    parsed = _parse_time(value)
    if parsed is None:
        return None
    return max(0, int((now - parsed).total_seconds() // 60))


def _latest_runtime_cycles_by_mission(root: Path) -> dict[str, dict]:
    path = root / ".agent_control" / "mission_events.jsonl"
    if not path.exists():
        return {}
    latest: dict[str, dict] = {}
    try:
        handle = path.open("r", encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    with handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if event.get("kind") != "mission.runtime_cycle":
                continue
            mission_id = str(event.get("mission_id") or event.get("missionId") or "").strip()
            if mission_id:
                latest[mission_id] = event
    return latest


def _route_roles(mission: Mission) -> set[str]:
    roles: set[str] = set()
    for item in mission.route_configs or []:
        if isinstance(item, dict):
            role = item.get("role")
        elif hasattr(item, "role"):
            role = getattr(item, "role")
        else:
            role = ""
        normalized = str(role or "").strip().lower()
        if normalized:
            roles.add(normalized)
    return roles


def _execution_target_preference(workspace: WorkspaceProfile | None) -> str:
    return str(getattr(workspace, "execution_target_preference", "") or "profile_default").strip()


def _normalize_scope_path(value: object) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        return ""
    while text.startswith("./"):
        text = text[2:]
    normalized = "/".join(part for part in text.split("/") if part and part != ".")
    if not normalized or normalized.startswith("-") or "://" in normalized:
        return ""
    return normalized.lower()


def _append_scope_value(paths: set[str], value: object) -> None:
    normalized = _normalize_scope_path(value)
    if normalized:
        paths.add(normalized)


def _append_scope_from_payload(paths: set[str], payload: object) -> None:
    if isinstance(payload, dict):
        for key in (
            "changed_files",
            "changedFiles",
            "files",
            "filePaths",
            "targetPaths",
            "target_path",
            "path",
            "artifactPath",
        ):
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    _append_scope_value(paths, item)
            else:
                _append_scope_value(paths, value)
        for nested_key in ("payload", "data", "result", "metadata"):
            nested = payload.get(nested_key)
            if isinstance(nested, (dict, list)):
                _append_scope_from_payload(paths, nested)
    elif isinstance(payload, list):
        for item in payload:
            _append_scope_from_payload(paths, item)


def _field(value: object, name: str, default: object = "") -> object:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _mission_file_scope(mission: Mission) -> set[str]:
    paths: set[str] = set()
    for value in getattr(mission, "planned_file_scope", []) or []:
        _append_scope_value(paths, value)
    for value in getattr(mission.proof, "changed_files", []) or []:
        _append_scope_value(paths, value)
    for record in getattr(mission, "action_history", []) or []:
        proposal = _field(record, "proposal", {})
        result = _field(record, "result", {})
        _append_scope_value(paths, _field(proposal, "target_path", ""))
        for value in _field(result, "changed_files", []) or []:
            _append_scope_value(paths, value)
        _append_scope_from_payload(paths, _field(result, "payload", {}))
    for session in getattr(mission, "delegated_runtime_sessions", []) or []:
        for value in getattr(session, "changed_files", []) or []:
            _append_scope_value(paths, value)
        for event in getattr(session, "latest_events", []) or []:
            _append_scope_from_payload(paths, event)
    return paths


def _scope_path_candidates(
    value: object,
    *,
    root: Path,
    workspace: WorkspaceProfile | None,
) -> list[Path]:
    text = str(value or "").strip()
    if not text or "://" in text:
        return []
    candidate_texts = [text]
    normalized = text.replace("\\", "/")
    if normalized.lower().startswith("/volume1/saclay/"):
        candidate_texts.append("/volume1/Saclay/" + normalized[len("/volume1/saclay/") :])
    raw = Path(candidate_texts[0]).expanduser()
    if raw.is_absolute():
        candidates = [Path(item).expanduser() for item in candidate_texts]
        unique: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate)
            if key not in seen:
                seen.add(key)
                unique.append(candidate)
        return unique
    candidates: list[Path] = []
    workspace_root = str(getattr(workspace, "root_path", "") or "").strip()
    for candidate_text in candidate_texts:
        if workspace_root:
            candidates.append(Path(workspace_root).expanduser() / candidate_text)
        candidates.append(root / candidate_text)
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _artifact_entry_payload(
    value: object,
    *,
    root: Path,
    workspace: WorkspaceProfile | None,
) -> dict[str, Any]:
    candidates = _scope_path_candidates(value, root=root, workspace=workspace)
    raw = str(value or "").strip()
    path = next((candidate for candidate in candidates if candidate.exists()), candidates[0] if candidates else Path(raw))
    exists = path.exists()
    is_dir = path.is_dir() if exists else False
    file_count = 0
    sample_files: list[str] = []
    readme_path = ""
    index_html_path = ""
    preview_files: list[str] = []
    truncated = False

    if exists and path.is_file():
        file_count = 1
        sample_files.append(path.name)
        suffix = path.suffix.lower()
        if suffix in ARTIFACT_PREVIEW_SUFFIXES:
            preview_files.append(path.name)
        if path.name.lower().startswith("readme") and suffix in {".md", ".txt"}:
            readme_path = str(path)
        if path.name.lower() in {"index.html", "index.htm"}:
            index_html_path = str(path)
    elif exists and path.is_dir():
        for current_text, dirs, files in os.walk(path):
            current = Path(current_text)
            dirs[:] = [
                item
                for item in dirs
                if item not in ARTIFACT_SKIP_DIRS and not item.startswith(".")
            ]
            try:
                depth = len(current.relative_to(path).parts)
            except ValueError:
                depth = 0
            if depth >= 2:
                dirs[:] = []
            for filename in files:
                if filename.startswith("."):
                    continue
                file_path = current / filename
                file_count += 1
                try:
                    relative = file_path.relative_to(path).as_posix()
                except ValueError:
                    relative = filename
                if len(sample_files) < ARTIFACT_SAMPLE_LIMIT:
                    sample_files.append(relative)
                lower = filename.lower()
                suffix = file_path.suffix.lower()
                if not readme_path and lower.startswith("readme") and suffix in {".md", ".txt"}:
                    readme_path = str(file_path)
                if not index_html_path and lower in {"index.html", "index.htm"}:
                    index_html_path = str(file_path)
                if suffix in ARTIFACT_PREVIEW_SUFFIXES and len(preview_files) < ARTIFACT_SAMPLE_LIMIT:
                    preview_files.append(relative)
                if file_count >= ARTIFACT_SCAN_LIMIT:
                    truncated = True
                    break
            if truncated:
                break

    previewable = bool(readme_path or index_html_path or preview_files)
    if not exists:
        status = "missing"
    elif file_count <= 0:
        status = "empty"
    elif previewable:
        status = "ready"
    else:
        status = "partial"
    return {
        "path": raw,
        "resolvedPath": str(path),
        "exists": exists,
        "isDir": is_dir,
        "fileCount": file_count,
        "sampleFiles": sample_files,
        "readmePath": readme_path,
        "indexHtmlPath": index_html_path,
        "previewFiles": preview_files,
        "previewable": previewable,
        "truncated": truncated,
        "status": status,
    }


def _ignored_scope_entry_reason(entry: dict[str, Any]) -> str:
    if entry.get("exists"):
        return ""
    raw = str(entry.get("path") or "").strip().replace("\\", "/").lower()
    resolved = str(entry.get("resolvedPath") or "").strip().replace("\\", "/").lower()
    normalized = raw.strip("/")
    if normalized == "tests/build/smoke" or normalized.endswith("/tests/build/smoke"):
        return "verification_check_path"
    if "/projects/projects/" in raw or "/projects/projects/" in resolved:
        return "malformed_source_path"
    return ""


def _scope_artifact_status(entries: list[dict[str, Any]]) -> tuple[str, str]:
    if not entries:
        return (
            "unplanned",
            "Add a planned file scope so the watchdog can verify mission artifacts.",
        )
    ready_count = sum(1 for item in entries if item["status"] == "ready")
    existing_count = sum(1 for item in entries if item["exists"])
    if ready_count == len(entries):
        return "ready", "Open the README or preview artifact and review the mission output."
    if existing_count > 0:
        return (
            "partial",
            "Add a README or preview artifact for the existing mission output folder.",
        )
    return "missing", "Run or repair the mission so it creates its planned artifact folder."


def build_planned_scope_artifacts(
    *,
    root: Path,
    mission: Mission,
    workspace: WorkspaceProfile | None = None,
) -> dict[str, Any]:
    raw_entries = [
        _artifact_entry_payload(value, root=root, workspace=workspace)
        for value in getattr(mission, "planned_file_scope", []) or []
        if str(value or "").strip()
    ]
    ignored_entries: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for entry in raw_entries:
        ignored_reason = _ignored_scope_entry_reason(entry)
        if ignored_reason:
            ignored_entries.append({**entry, "ignored": True, "ignoredReason": ignored_reason})
        else:
            entries.append(entry)
    if not entries:
        return {
            "status": "unplanned",
            "scopeCount": 0,
            "rawScopeCount": len(raw_entries),
            "ignoredCount": len(ignored_entries),
            "existingCount": 0,
            "readyCount": 0,
            "partialCount": 0,
            "missingCount": 0,
            "readmeCount": 0,
            "previewableCount": 0,
            "entries": [],
            "ignoredEntries": ignored_entries,
            "nextAction": "Add a planned file scope so the watchdog can verify mission artifacts.",
        }
    existing_count = sum(1 for item in entries if item["exists"])
    ready_count = sum(1 for item in entries if item["status"] == "ready")
    partial_count = sum(1 for item in entries if item["status"] in {"partial", "empty"})
    missing_count = sum(1 for item in entries if item["status"] == "missing")
    readme_count = sum(1 for item in entries if item["readmePath"])
    previewable_count = sum(1 for item in entries if item["previewable"])
    status, next_action = _scope_artifact_status(entries)
    return {
        "status": status,
        "scopeCount": len(entries),
        "rawScopeCount": len(raw_entries),
        "ignoredCount": len(ignored_entries),
        "existingCount": existing_count,
        "readyCount": ready_count,
        "partialCount": partial_count,
        "missingCount": missing_count,
        "readmeCount": readme_count,
        "previewableCount": previewable_count,
        "entries": entries,
        "ignoredEntries": ignored_entries,
        "nextAction": next_action,
    }


def _scope_relation(active: Mission, queued: Mission) -> dict[str, Any]:
    active_files = _mission_file_scope(active)
    queued_files = _mission_file_scope(queued)
    overlap = sorted(active_files & queued_files)
    if overlap:
        safety = SCOPE_OVERLAP
    elif active_files and queued_files:
        safety = SCOPE_SAFE
    else:
        safety = SCOPE_UNKNOWN
    return {
        "safety": safety,
        "activeFileCount": len(active_files),
        "queuedFileCount": len(queued_files),
        "overlapFiles": overlap[:8],
        "activeSamples": sorted(active_files)[:8],
        "queuedSamples": sorted(queued_files)[:8],
    }


def parallel_dispatch_scope_evidence(active: Mission, queued: Mission) -> dict[str, Any]:
    """Return the file-scope evidence required before splitting a queued mission."""
    return _scope_relation(active, queued)


def _parallel_lane_first_step(
    root: Path,
    mission: Mission,
    workspace: WorkspaceProfile | None,
    scope_relation: dict[str, Any],
) -> str:
    workspace_label = workspace.workspace_id if workspace else mission.workspace_id
    safety = scope_relation.get("safety")
    if safety == SCOPE_SAFE:
        return (
            "Scope evidence is disjoint, so move the queued mission to a dedicated "
            "`isolated_worktree` lane and launch it asynchronously: run "
            f"`python -m grant_agent.cli mission-action --root {root} --mission-id {mission.mission_id} "
            "--action parallelize-worktree --launch-async`."
            f" Workspace: {workspace_label}."
        )
    if safety == SCOPE_OVERLAP:
        overlap = ", ".join(scope_relation.get("overlapFiles") or []) or "overlap evidence present"
        return (
            "Do not parallelize automatically yet. The queued mission overlaps the active file scope "
            f"({overlap}); keep it queued or split the objective into a non-overlapping lane."
            f" Workspace: {workspace_label}."
        )
    return (
        "Collect file-scope evidence before parallelizing. The watchdog could not prove whether this queued "
        "mission overlaps the active mission, so keep it queued until changed file or target path evidence exists."
        f" Workspace: {workspace_label}."
    )


def _issue(
    *,
    mission: Mission,
    severity: str,
    kind: str,
    title: str,
    detail: str,
    first_step: str,
    evidence: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    issue = {
        "issueId": f"{mission.mission_id}:{kind}",
        "missionId": mission.mission_id,
        "missionTitle": mission.title or mission.objective[:80],
        "workspaceId": mission.workspace_id,
        "severity": severity,
        "kind": kind,
        "title": title,
        "detail": detail,
        "firstStep": first_step,
        "evidence": evidence or [],
    }
    if extra:
        issue.update(extra)
    return issue


def _latest_delegated_session(mission: Mission) -> Any | None:
    sessions = list(getattr(mission, "delegated_runtime_sessions", []) or [])
    if not sessions:
        return None
    return max(
        sessions,
        key=lambda session: (
            str(_field(session, "updated_at", "") or ""),
            str(_field(session, "created_at", "") or ""),
            str(_field(session, "delegated_id", "") or ""),
        ),
    )


def _blocked_or_failed_first_step(root: Path, mission: Mission, stop_reason: str) -> str:
    if stop_reason == "runtime_budget":
        return "Extend the mission run budget for unattended work, then resume it."
    if stop_reason in {"delegated_runtime_failed", "runtime_failed"}:
        return (
            "Inspect the latest delegated runtime log, repair the provider/auth/runtime failure, then run "
            f"`python -m grant_agent.cli mission-action --root {root} "
            f"--mission-id {mission.mission_id} --action resume --launch-async`."
        )
    if stop_reason in {"approval_rejected", "approval_required"}:
        return (
            "Review the approval history and either approve a safe latest action or split the mission into "
            "a smaller non-mutating repair step."
        )
    return (
        "Review the mission proof, failed checks, and latest runtime events, then resume asynchronously once "
        "the blocking cause is repaired."
    )


def build_watchdog_problem_report(report: dict[str, Any]) -> dict[str, Any]:
    checked_at = str(report.get("checkedAt") or utc_now_iso())
    problems = []
    for issue in report.get("issues", []) or []:
        if not isinstance(issue, dict):
            continue
        problem_id = str(issue.get("issueId") or "").strip()
        if not problem_id:
            mission_id = str(issue.get("missionId") or "mission").strip()
            kind = str(issue.get("kind") or "watchdog_issue").strip()
            problem_id = f"{mission_id}:{kind}"
        problems.append(
            {
                "problemId": problem_id,
                "schema": "fluxio.watchdog_problem.v1",
                "detectedAt": checked_at,
                "status": "open",
                "owner": "external_mission_watchdog",
                "severity": str(issue.get("severity") or "info"),
                "kind": str(issue.get("kind") or "watchdog_issue"),
                "missionId": str(issue.get("missionId") or ""),
                "workspaceId": str(issue.get("workspaceId") or ""),
                "title": str(issue.get("title") or "Watchdog issue"),
                "detail": str(issue.get("detail") or ""),
                "firstStep": str(issue.get("firstStep") or report.get("nextAction") or ""),
                "firstRepairStep": str(issue.get("firstStep") or report.get("nextAction") or ""),
                "evidence": list(issue.get("evidence") or []),
                "sourceIssueId": str(issue.get("issueId") or problem_id),
            }
        )
    return {
        "schema": "fluxio.watchdog_problem_report.v1",
        "checkedAt": checked_at,
        "status": "open" if problems else "clear",
        "problemCount": len(problems),
        "openProblems": problems,
        "firstProblem": problems[0] if problems else {},
        "nextAction": (
            problems[0]["firstStep"]
            if problems
            else "No watchdog problems found. Keep the external loop active."
        ),
    }


def build_watchdog_problem_registry(
    *,
    root: Path,
    report: dict[str, Any],
) -> dict[str, Any]:
    checked_at = str(report.get("checkedAt") or utc_now_iso())
    registry_path = root / ".agent_control" / "mission_watchdog_problem_registry.json"
    previous: dict[str, Any] = {}
    if registry_path.exists():
        try:
            loaded = json.loads(registry_path.read_text(encoding="utf-8"))
            previous = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError):
            previous = {}

    previous_by_id = {
        str(item.get("problemId") or ""): item
        for item in previous.get("problems", []) or []
        if isinstance(item, dict) and str(item.get("problemId") or "")
    }
    current_problems = {
        str(item.get("problemId") or ""): item
        for item in report.get("problemReport", {}).get("openProblems", []) or []
        if isinstance(item, dict) and str(item.get("problemId") or "")
    }
    merged: list[dict[str, Any]] = []
    for problem_id, problem in current_problems.items():
        previous_problem = previous_by_id.get(problem_id, {})
        first_detected_at = str(previous_problem.get("firstDetectedAt") or problem.get("detectedAt") or checked_at)
        occurrence_count = int(previous_problem.get("occurrenceCount") or 0) + 1
        merged.append(
            {
                **problem,
                "schema": "fluxio.watchdog_problem_registry_entry.v1",
                "problemId": problem_id,
                "status": "open",
                "firstDetectedAt": first_detected_at,
                "lastDetectedAt": checked_at,
                "lastSeenAt": checked_at,
                "occurrenceCount": occurrence_count,
                "resolvedAt": "",
                "firstRepairStep": str(
                    problem.get("firstRepairStep")
                    or problem.get("firstStep")
                    or report.get("nextAction")
                    or ""
                ),
            }
        )

    for problem_id, previous_problem in previous_by_id.items():
        if problem_id in current_problems:
            continue
        status = str(previous_problem.get("status") or "").lower()
        resolved_at = str(previous_problem.get("resolvedAt") or checked_at)
        merged.append(
            {
                **previous_problem,
                "schema": "fluxio.watchdog_problem_registry_entry.v1",
                "status": "resolved" if status != "open" else "resolved",
                "resolvedAt": resolved_at,
                "lastSeenAt": str(previous_problem.get("lastSeenAt") or previous_problem.get("lastDetectedAt") or ""),
            }
        )

    severity_order = {"bad": 0, "warn": 1, "info": 2}
    merged.sort(
        key=lambda item: (
            0 if item.get("status") == "open" else 1,
            severity_order.get(str(item.get("severity") or "info"), 9),
            str(item.get("lastDetectedAt") or item.get("lastSeenAt") or ""),
        )
    )
    merged = merged[:PROBLEM_REGISTRY_LIMIT]
    open_problems = [item for item in merged if item.get("status") == "open"]
    resolved_problems = [item for item in merged if item.get("status") == "resolved"]
    new_problem_count = sum(
        1 for item in open_problems if int(item.get("occurrenceCount") or 0) <= 1
    )
    return {
        "schema": "fluxio.watchdog_problem_registry.v1",
        "updatedAt": checked_at,
        "status": "open" if open_problems else "clear",
        "root": str(root),
        "registryPath": str(registry_path),
        "problemCount": len(merged),
        "openProblemCount": len(open_problems),
        "resolvedProblemCount": len(resolved_problems),
        "newProblemCount": new_problem_count,
        "firstOpenProblem": open_problems[0] if open_problems else {},
        "nextAction": (
            str(open_problems[0].get("firstRepairStep") or open_problems[0].get("firstStep"))
            if open_problems
            else "No open watchdog problems. Keep the external loop active."
        ),
        "problems": merged,
    }


def build_mission_watchdog_report(
    *,
    root: Path,
    missions: list[Mission],
    workspaces: list[WorkspaceProfile],
    stale_minutes: int = 60,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    workspace_by_id = {item.workspace_id: item for item in workspaces}
    latest_runtime_cycles = _latest_runtime_cycles_by_mission(root)
    issues: list[dict[str, Any]] = []
    artifact_readiness_by_mission = {
        mission.mission_id: build_planned_scope_artifacts(
            root=root,
            mission=mission,
            workspace=workspace_by_id.get(mission.workspace_id),
        )
        for mission in missions
    }

    active_by_workspace: dict[str, list[Mission]] = {}
    for mission in missions:
        status = str(mission.state.status or "").strip().lower()
        if status and status not in TERMINAL_STATUSES and status != "queued":
            active_by_workspace.setdefault(mission.workspace_id, []).append(mission)

    for mission in missions:
        status = str(mission.state.status or "").strip().lower()
        artifact_readiness = artifact_readiness_by_mission.get(mission.mission_id, {})
        artifact_status = str(artifact_readiness.get("status") or "").strip().lower()
        if status == "completed" and artifact_status in {"missing", "partial"}:
            issues.append(
                _issue(
                    mission=mission,
                    severity="bad" if artifact_status == "missing" else "warn",
                    kind="planned_scope_artifacts_not_ready",
                    title="Completed mission artifact scope is not ready",
                    detail=(
                        "The mission is completed, but its planned output folder is not fully inspectable "
                        f"(artifact status: {artifact_status})."
                    ),
                    first_step=str(
                        artifact_readiness.get("nextAction")
                        or "Create or document the planned artifact output."
                    ),
                    evidence=[
                        f"artifactStatus={artifact_status}",
                        f"scopeCount={artifact_readiness.get('scopeCount', 0)}",
                        f"existingCount={artifact_readiness.get('existingCount', 0)}",
                        f"previewableCount={artifact_readiness.get('previewableCount', 0)}",
                    ],
                    extra={"artifactReadiness": artifact_readiness},
                )
            )
        if status == "failed" or (status == "blocked" and mission.state.stop_reason != "runtime_budget"):
            stop_reason = str(mission.state.stop_reason or "").strip()
            latest_session = _latest_delegated_session(mission)
            session_status = str(_field(latest_session, "status", "") or "")
            session_id = str(_field(latest_session, "delegated_id", "") or "")
            session_log = str(_field(latest_session, "log_path", "") or "")
            issues.append(
                _issue(
                    mission=mission,
                    severity="bad",
                    kind="mission_blocked_or_failed",
                    title="Mission is blocked or failed",
                    detail=(
                        mission.proof.summary
                        or f"The mission is {status} and cannot continue without repair."
                    ),
                    first_step=_blocked_or_failed_first_step(root, mission, stop_reason),
                    evidence=[
                        f"status={status}",
                        f"stopReason={stop_reason or 'unknown'}",
                        f"blockedBy={','.join(mission.proof.blocked_by or []) or 'none'}",
                        f"latestDelegatedSession={session_id or 'none'}",
                        f"latestDelegatedStatus={session_status or 'unknown'}",
                        f"latestDelegatedLog={session_log or 'none'}",
                    ],
                )
            )
        if status in TERMINAL_STATUSES:
            continue

        updated_age = _age_minutes(mission.updated_at, current)
        state_age = _age_minutes(
            mission.state.last_runtime_event
            if str(mission.state.last_runtime_event or "").startswith("20")
            else mission.updated_at,
            current,
        )
        age = updated_age if updated_age is not None else state_age
        workspace = workspace_by_id.get(mission.workspace_id)
        latest_runtime_cycle = latest_runtime_cycles.get(mission.mission_id, {})
        latest_runtime_metadata = (
            latest_runtime_cycle.get("metadata")
            if isinstance(latest_runtime_cycle.get("metadata"), dict)
            else {}
        )
        latest_runtime_status = str(latest_runtime_metadata.get("autopilotStatus") or "").strip().lower()
        latest_runtime_pause = str(latest_runtime_metadata.get("pauseReason") or "").strip()
        latest_runtime_age = _age_minutes(latest_runtime_cycle.get("timestamp"), current)
        planner_loop_status = str(
            getattr(mission.state, "planner_loop_status", "")
            or getattr(mission, "planner_loop_status", "")
            or ""
        ).strip().lower()

        if (
            status in {"running", "launching"}
            and latest_runtime_status == "completed"
            and not latest_runtime_pause
        ):
            issues.append(
                _issue(
                    mission=mission,
                    severity="bad",
                    kind="runtime_cycle_state_mismatch",
                    title="Mission row says running but latest runtime cycle completed",
                    detail=(
                        "The event stream recorded a completed runtime cycle, but the mission row still shows "
                        f"{status}."
                    ),
                    first_step=(
                        f"Run a control-room refresh or `python -m grant_agent.cli mission-action --root {root} "
                        f"--mission-id {mission.mission_id} --action complete` after confirming proof."
                    ),
                    evidence=[
                        f"runtimeCycleStatus={latest_runtime_status}",
                        f"runtimeCycleAgeMinutes={latest_runtime_age if latest_runtime_age is not None else 'unknown'}",
                        f"runtimeCycleSessionId={latest_runtime_metadata.get('sessionId') or ''}",
                    ],
                )
            )

        if (
            status in {"running", "launching"}
            and planner_loop_status in {"", "idle", "stopped"}
            and not mission.state.pending_approval_payload
            and mission.state.pending_mutating_actions <= 0
            and (age is None or age < stale_minutes)
        ):
            issues.append(
                _issue(
                    mission=mission,
                    severity="warn",
                    kind="running_planner_loop_idle",
                    title="Mission row is active but planner loop is idle",
                    detail=(
                        "The mission row is active, but the planner loop is not currently dispatching work. "
                        "This can make the UI look healthy while no new slice is actually moving."
                    ),
                    first_step=(
                        f"Extend budget if needed, then run `python -m grant_agent.cli mission-action "
                        f"--root {root} --mission-id {mission.mission_id} --action resume --launch-async`."
                    ),
                    evidence=[
                        f"status={status}",
                        f"plannerLoopStatus={planner_loop_status or 'missing'}",
                        f"ageMinutes={age if age is not None else 'unknown'}",
                    ],
                )
            )

        if status == "needs_approval" or mission.state.pending_mutating_actions > 0:
            issues.append(
                _issue(
                    mission=mission,
                    severity="warn",
                    kind="approval_waiting",
                    title="Mission is waiting on an approval gate",
                    detail=(
                        mission.proof.summary
                        or "A mutating action is pending and the mission cannot advance."
                    ),
                    first_step=(
                        f"Review the latest action, then run `python -m grant_agent.cli "
                        f"mission-action --root {root} --mission-id {mission.mission_id} "
                        "--action approve-latest` if it is a safe artifact/write action."
                    ),
                    evidence=[
                        f"pendingMutatingActions={mission.state.pending_mutating_actions}",
                        f"stopReason={mission.state.stop_reason or ''}",
                    ],
                )
            )

        if status == "queued" and mission.state.queue_position == 0:
            issues.append(
                _issue(
                    mission=mission,
                    severity="info",
                    kind="queue_front_not_running",
                    title="Mission is first in queue but not running",
                    detail=mission.proof.summary or "The mission can be dispatched now.",
                    first_step=(
                        f"Run `python -m grant_agent.cli mission-action --root {root} "
                        f"--mission-id {mission.mission_id} --action resume --launch-async`."
                    ),
                    evidence=[f"workspace={workspace.name if workspace else mission.workspace_id}"],
                )
            )

        if status == "queued" and mission.state.blocking_mission_id:
            blocker = next(
                (item for item in missions if item.mission_id == mission.state.blocking_mission_id),
                None,
            )
            blocker_status = str(blocker.state.status or "").lower() if blocker else "missing"
            if blocker is None or blocker_status in TERMINAL_STATUSES:
                issues.append(
                    _issue(
                        mission=mission,
                        severity="bad",
                        kind="stale_queue_blocker",
                        title="Mission is queued behind a stale blocker",
                        detail=f"Blocking mission is {mission.state.blocking_mission_id}, status {blocker_status}.",
                        first_step="Run the watchdog or control-room refresh to rebalance the workspace queue.",
                        evidence=[f"blockingMissionId={mission.state.blocking_mission_id}"],
                    )
                )
            else:
                blocker_age = _age_minutes(blocker.created_at, current)
                queued_count = sum(
                    1
                    for item in missions
                    if item.workspace_id == mission.workspace_id
                    and str(item.state.status or "").strip().lower() == "queued"
                    and item.state.queue_position > 0
                )
                if (
                    blocker_status in {"running", "launching"}
                    and blocker_age is not None
                    and blocker_age >= stale_minutes
                    and queued_count > 0
                ):
                    relation = _scope_relation(blocker, mission)
                    issues.append(
                        _issue(
                            mission=mission,
                            severity="info",
                            kind="workspace_queue_pressure",
                            title="Queued mission is waiting behind a long-running workspace slot",
                            detail=(
                                f"Blocking mission {blocker.mission_id} has held the active workspace slot "
                                f"for about {blocker_age} minutes while {queued_count} mission(s) wait."
                            ),
                            first_step=_parallel_lane_first_step(root, mission, workspace, relation),
                            evidence=[
                                f"blockingMissionId={mission.state.blocking_mission_id}",
                                f"blockingAgeMinutes={blocker_age}",
                                f"queuedMissionsInWorkspace={queued_count}",
                                f"workspaceExecutionTargetPreference={_execution_target_preference(workspace)}",
                                f"scopeSafety={relation['safety']}",
                                f"activeScopeFiles={relation['activeFileCount']}",
                                f"queuedScopeFiles={relation['queuedFileCount']}",
                            ],
                            extra={
                                "scopeSafety": relation["safety"],
                                "scopeEvidence": {
                                    "activeFileCount": relation["activeFileCount"],
                                    "queuedFileCount": relation["queuedFileCount"],
                                    "overlapFiles": relation["overlapFiles"],
                                    "activeSamples": relation["activeSamples"],
                                    "queuedSamples": relation["queuedSamples"],
                                },
                            },
                        )
                    )

        if status in {"running", "launching"} and age is not None and age >= stale_minutes:
            issues.append(
                _issue(
                    mission=mission,
                    severity="warn",
                    kind="stale_running_mission",
                    title="Running mission has not reported recent movement",
                    detail=f"No mission record update for about {age} minutes.",
                    first_step=(
                        "Inspect the latest async log and session state; if no process is active, "
                        "resume the mission asynchronously from the control room."
                    ),
                    evidence=[f"ageMinutes={age}", f"staleThresholdMinutes={stale_minutes}"],
                )
            )

        budget_status = str(mission.state.time_budget_status or "").strip().lower()
        budget_exhausted = (
            mission.state.stop_reason == "runtime_budget"
            or (
                status in {"running", "needs_approval"}
                and mission.state.remaining_runtime_seconds <= 0
                and budget_status in {"exhausted", "expired", "paused"}
            )
        )
        if budget_exhausted:
            issues.append(
                _issue(
                    mission=mission,
                    severity="bad",
                    kind="runtime_budget_exhausted",
                    title="Mission runtime budget is exhausted",
                    detail="The mission cannot continue until its budget window is extended or the mission is closed.",
                    first_step="Extend the mission run budget for unattended work, then resume it.",
                    evidence=[f"remainingSeconds={mission.state.remaining_runtime_seconds}"],
                )
            )

        roles = _route_roles(mission)
        missing_roles = [role for role in ("planner", "executor", "verifier") if role not in roles]
        if missing_roles and status in {"queued", "running", "needs_approval"}:
            issues.append(
                _issue(
                    mission=mission,
                    severity="info",
                    kind="route_contract_incomplete",
                    title="Mission route contract is incomplete",
                    detail=f"Missing route roles: {', '.join(missing_roles)}.",
                    first_step="Apply the task-aware route contract before the next resume.",
                    evidence=[f"roles={','.join(sorted(roles)) or 'none'}"],
                )
            )

        for session in mission.delegated_runtime_sessions or []:
            status_text = str(getattr(session, "status", "") or "").lower()
            heartbeat_status = str(getattr(session, "heartbeat_status", "") or "").lower()
            heartbeat_age = int(getattr(session, "heartbeat_age_seconds", 0) or 0)
            if status_text not in TERMINAL_STATUSES and (
                heartbeat_status == "stale" or heartbeat_age >= stale_minutes * 60
            ):
                issues.append(
                    _issue(
                        mission=mission,
                        severity="warn",
                        kind="stale_runtime_heartbeat",
                        title="Delegated runtime heartbeat is stale",
                        detail=f"Runtime session {getattr(session, 'delegated_id', '')} heartbeat is stale.",
                        first_step="Refresh the runtime session; if the process is gone, relaunch the mission lane.",
                        evidence=[
                            f"heartbeatStatus={heartbeat_status}",
                            f"heartbeatAgeSeconds={heartbeat_age}",
                        ],
                    )
                )

    severity_order = {"bad": 0, "warn": 1, "info": 2}
    issues.sort(key=lambda item: (severity_order.get(item["severity"], 9), item["missionId"], item["kind"]))
    report = {
        "schema": "fluxio.mission_watchdog.v1",
        "checkedAt": utc_now_iso(),
        "root": str(root),
        "staleMinutes": stale_minutes,
        "summary": {
            "missionCount": len(missions),
            "issueCount": len(issues),
            "bad": sum(1 for item in issues if item["severity"] == "bad"),
            "warn": sum(1 for item in issues if item["severity"] == "warn"),
            "info": sum(1 for item in issues if item["severity"] == "info"),
            "queuePressure": sum(
                1 for item in issues if item["kind"] == "workspace_queue_pressure"
            ),
            "queuePressureSafe": sum(
                1
                for item in issues
                if item["kind"] == "workspace_queue_pressure"
                and item.get("scopeSafety") == SCOPE_SAFE
            ),
            "queuePressureUnknown": sum(
                1
                for item in issues
                if item["kind"] == "workspace_queue_pressure"
                and item.get("scopeSafety") == SCOPE_UNKNOWN
            ),
            "queuePressureOverlap": sum(
                1
                for item in issues
                if item["kind"] == "workspace_queue_pressure"
                and item.get("scopeSafety") == SCOPE_OVERLAP
            ),
            "artifactReady": sum(
                1
                for item in artifact_readiness_by_mission.values()
                if item.get("status") == "ready"
            ),
            "artifactPartial": sum(
                1
                for item in artifact_readiness_by_mission.values()
                if item.get("status") == "partial"
            ),
            "artifactMissing": sum(
                1
                for item in artifact_readiness_by_mission.values()
                if item.get("status") == "missing"
            ),
            "artifactUnplanned": sum(
                1
                for item in artifact_readiness_by_mission.values()
                if item.get("status") == "unplanned"
            ),
            "activeWorkspaceCount": len(active_by_workspace),
        },
        "issues": issues,
        "artifactReadiness": artifact_readiness_by_mission,
        "nextAction": (
            issues[0]["firstStep"]
            if issues
            else "No watchdog issues found. Keep the scheduled watchdog active."
        ),
    }
    report["problemReport"] = build_watchdog_problem_report(report)
    report["problemRegistry"] = build_watchdog_problem_registry(root=root, report=report)
    return report


def write_mission_watchdog_report(root: Path, report: dict[str, Any]) -> Path:
    control_dir = root / ".agent_control"
    control_dir.mkdir(parents=True, exist_ok=True)
    registry = build_watchdog_problem_registry(root=root, report=report)
    report["problemRegistry"] = registry
    report.setdefault("problemReport", build_watchdog_problem_report(report))["registryPath"] = registry[
        "registryPath"
    ]
    path = control_dir / "mission_watchdog.json"
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(report, indent=2), encoding="utf-8")
    tmp.replace(path)
    problems_path = control_dir / "mission_watchdog_problems.json"
    problems_tmp = problems_path.with_name(f"{problems_path.name}.{uuid.uuid4().hex}.tmp")
    problems_tmp.write_text(
        json.dumps(report.get("problemReport", build_watchdog_problem_report(report)), indent=2),
        encoding="utf-8",
    )
    problems_tmp.replace(problems_path)
    registry_path = control_dir / "mission_watchdog_problem_registry.json"
    registry_tmp = registry_path.with_name(f"{registry_path.name}.{uuid.uuid4().hex}.tmp")
    registry_tmp.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    registry_tmp.replace(registry_path)
    return path


def build_watchdog_supervisor_state(
    *,
    root: Path,
    interval_seconds: int,
    stale_minutes: int,
    runs_completed: int,
    report: dict[str, Any],
    started_at: str,
    loop_mode: str,
) -> dict[str, Any]:
    checked_at = str(report.get("checkedAt") or utc_now_iso())
    next_run_at = (
        _parse_time(checked_at) or datetime.now(timezone.utc)
    ) + timedelta(seconds=max(0, interval_seconds))
    problem_report = report.get("problemReport", {})
    return {
        "schema": "fluxio.mission_watchdog_supervisor.v1",
        "root": str(root),
        "processPid": os.getpid(),
        "status": str(problem_report.get("status") or "clear"),
        "loopMode": loop_mode,
        "supervisorActive": loop_mode in {"ongoing", "bounded", "one_shot"},
        "startedAt": started_at,
        "lastRunAt": checked_at,
        "nextRunAt": next_run_at.isoformat(),
        "intervalSeconds": max(0, interval_seconds),
        "cadencePolicy": {
            "schema": "fluxio.mission_watchdog_cadence.v1",
            "activeIntervalSeconds": max(0, interval_seconds),
            "staleMinutes": max(1, stale_minutes),
            "presets": [
                {"label": "1 minute", "intervalSeconds": 60},
                {"label": "5 minutes", "intervalSeconds": 300},
                {"label": "20 minutes", "intervalSeconds": 1200},
                {"label": "1 hour", "intervalSeconds": 3600},
                {"label": "1 day", "intervalSeconds": 86400},
            ],
            "configureCommand": (
                "python -m grant_agent.cli mission-watchdog --loop --max-runs 0 "
                "--interval-seconds <seconds> --advance-self-improvement "
                "--self-improvement-interval-minutes 60"
            ),
        },
        "staleMinutes": max(1, stale_minutes),
        "runsCompleted": max(0, runs_completed),
        "lastProblemCount": int(problem_report.get("problemCount") or 0),
        "lastIssueCount": int(report.get("summary", {}).get("issueCount") or 0),
        "nextAction": str(
            problem_report.get("nextAction")
            or report.get("nextAction")
            or "No watchdog problems found. Keep the external loop active."
        ),
        "problemReportPath": str(root / ".agent_control" / "mission_watchdog_problems.json"),
        "watchdogReportPath": str(root / ".agent_control" / "mission_watchdog.json"),
    }


def _pid_alive(pid: object) -> bool:
    try:
        normalized = int(pid)
    except (TypeError, ValueError):
        return False
    if normalized <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            handle = kernel32.OpenProcess(0x1000, False, normalized)
            if not handle:
                return False
            try:
                exit_code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return False
                return exit_code.value == 259
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(normalized, 0)
    except OSError:
        return False
    return True


def load_watchdog_supervisor_state(
    root: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    path = root / ".agent_control" / "mission_watchdog_supervisor.json"
    if not path.exists():
        return {
            "schema": "fluxio.mission_watchdog_supervisor.v1",
            "root": str(root),
            "status": "missing",
            "loopMode": "none",
            "supervisorActive": False,
            "stale": True,
            "lastRunAt": "",
            "nextRunAt": "",
            "intervalSeconds": 0,
            "cadencePolicy": {
                "schema": "fluxio.mission_watchdog_cadence.v1",
                "activeIntervalSeconds": 0,
                "staleMinutes": 60,
                "presets": [
                    {"label": "1 minute", "intervalSeconds": 60},
                    {"label": "5 minutes", "intervalSeconds": 300},
                    {"label": "20 minutes", "intervalSeconds": 1200},
                    {"label": "1 hour", "intervalSeconds": 3600},
                    {"label": "1 day", "intervalSeconds": 86400},
                ],
                "configureCommand": (
                    "python -m grant_agent.cli mission-watchdog --loop --max-runs 0 "
                    "--interval-seconds <seconds> --advance-self-improvement "
                    "--self-improvement-interval-minutes 60"
                ),
            },
            "staleMinutes": 60,
            "runsCompleted": 0,
            "lastProblemCount": 0,
            "lastIssueCount": 0,
            "nextAction": (
                "Start the external mission watchdog loop with "
                "`python -m grant_agent.cli mission-watchdog --loop --max-runs 0`."
            ),
            "problemReportPath": str(root / ".agent_control" / "mission_watchdog_problems.json"),
            "watchdogReportPath": str(root / ".agent_control" / "mission_watchdog.json"),
        }
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "schema": "fluxio.mission_watchdog_supervisor.v1",
            "root": str(root),
            "status": "unreadable",
            "loopMode": "unknown",
            "supervisorActive": False,
            "stale": True,
            "lastRunAt": "",
            "nextRunAt": "",
            "intervalSeconds": 0,
            "cadencePolicy": {
                "schema": "fluxio.mission_watchdog_cadence.v1",
                "activeIntervalSeconds": 0,
                "staleMinutes": 60,
                "presets": [
                    {"label": "1 minute", "intervalSeconds": 60},
                    {"label": "5 minutes", "intervalSeconds": 300},
                    {"label": "20 minutes", "intervalSeconds": 1200},
                    {"label": "1 hour", "intervalSeconds": 3600},
                    {"label": "1 day", "intervalSeconds": 86400},
                ],
                "configureCommand": (
                    "python -m grant_agent.cli mission-watchdog --loop --max-runs 0 "
                    "--interval-seconds <seconds> --advance-self-improvement "
                    "--self-improvement-interval-minutes 60"
                ),
            },
            "staleMinutes": 60,
            "runsCompleted": 0,
            "lastProblemCount": 0,
            "lastIssueCount": 0,
            "nextAction": "Repair or remove the unreadable mission watchdog supervisor state file.",
            "problemReportPath": str(root / ".agent_control" / "mission_watchdog_problems.json"),
            "watchdogReportPath": str(root / ".agent_control" / "mission_watchdog.json"),
        }
    if not isinstance(state, dict):
        state = {}
    current = now or datetime.now(timezone.utc)
    interval_seconds = max(0, int(state.get("intervalSeconds") or 0))
    cadence_policy = state.get("cadencePolicy") if isinstance(state.get("cadencePolicy"), dict) else {}
    next_run_at = _parse_time(state.get("nextRunAt"))
    stale_grace_seconds = max(90, interval_seconds * 2)
    stale = True
    if next_run_at is not None:
        stale = current > next_run_at + timedelta(seconds=stale_grace_seconds)
    loop_mode = str(state.get("loopMode") or "unknown")
    process_pid = state.get("processPid")
    process_alive = _pid_alive(process_pid)
    ongoing = loop_mode == "ongoing"
    supervisor_active = (process_alive or not ongoing) and not stale and loop_mode not in {"none", "unknown"}
    normalized = {
        "schema": "fluxio.mission_watchdog_supervisor.v1",
        "root": str(state.get("root") or root),
        "status": str(state.get("status") or "clear"),
        "loopMode": loop_mode,
        "processPid": int(process_pid) if str(process_pid or "").isdigit() else 0,
        "processAlive": process_alive,
        "supervisorActive": supervisor_active,
        "stale": stale,
        "startedAt": str(state.get("startedAt") or ""),
        "lastRunAt": str(state.get("lastRunAt") or ""),
        "nextRunAt": str(state.get("nextRunAt") or ""),
        "intervalSeconds": interval_seconds,
        "cadencePolicy": {
            "schema": "fluxio.mission_watchdog_cadence.v1",
            "activeIntervalSeconds": max(0, int(cadence_policy.get("activeIntervalSeconds") or interval_seconds)),
            "staleMinutes": max(1, int(cadence_policy.get("staleMinutes") or state.get("staleMinutes") or 60)),
            "presets": cadence_policy.get("presets")
            if isinstance(cadence_policy.get("presets"), list)
            else [
                {"label": "1 minute", "intervalSeconds": 60},
                {"label": "5 minutes", "intervalSeconds": 300},
                {"label": "20 minutes", "intervalSeconds": 1200},
                {"label": "1 hour", "intervalSeconds": 3600},
                {"label": "1 day", "intervalSeconds": 86400},
            ],
            "configureCommand": str(
                cadence_policy.get("configureCommand")
                or (
                    "python -m grant_agent.cli mission-watchdog --loop --max-runs 0 "
                    "--interval-seconds <seconds> --advance-self-improvement "
                    "--self-improvement-interval-minutes 60"
                )
            ),
        },
        "staleMinutes": max(1, int(state.get("staleMinutes") or 60)),
        "runsCompleted": max(0, int(state.get("runsCompleted") or 0)),
        "lastProblemCount": max(0, int(state.get("lastProblemCount") or 0)),
        "lastIssueCount": max(0, int(state.get("lastIssueCount") or 0)),
        "nextAction": str(
            state.get("nextAction")
            or "No watchdog problems found. Keep the external loop active."
        ),
        "problemReportPath": str(
            state.get("problemReportPath")
            or root / ".agent_control" / "mission_watchdog_problems.json"
        ),
        "watchdogReportPath": str(
            state.get("watchdogReportPath")
            or root / ".agent_control" / "mission_watchdog.json"
        ),
        "notificationStatus": str(state.get("notificationStatus") or ""),
    }
    if ongoing and not process_alive:
        normalized["status"] = "stale"
        normalized["nextAction"] = (
            "Restart the external mission watchdog loop; the previous ongoing supervisor process is gone."
        )
    elif stale:
        normalized["status"] = "stale"
        normalized["nextAction"] = (
            "Restart the external mission watchdog loop; the next scheduled pass is overdue."
        )
    return normalized


def write_watchdog_supervisor_state(root: Path, state: dict[str, Any]) -> Path:
    control_dir = root / ".agent_control"
    control_dir.mkdir(parents=True, exist_ok=True)
    path = control_dir / "mission_watchdog_supervisor.json"
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def ensure_watchdog_supervisor_loop(
    root: Path,
    *,
    stale_minutes: int = 60,
    interval_seconds: int = 1200,
    notify_telegram: bool = True,
) -> dict[str, Any]:
    root = Path(root).resolve()
    current = load_watchdog_supervisor_state(root)
    if current.get("supervisorActive") and current.get("loopMode") == "ongoing":
        return {
            "schema": "fluxio.mission_watchdog_autostart.v1",
            "ok": True,
            "started": False,
            "reason": "already_active",
            "supervisor": current,
        }

    control_dir = root / ".agent_control"
    control_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = control_dir / "mission_watchdog_loop.out.log"
    stderr_path = control_dir / "mission_watchdog_loop.err.log"
    command = [
        sys.executable,
        "-m",
        "grant_agent.cli",
        "mission-watchdog",
        "--root",
        str(root),
        "--stale-minutes",
        str(max(1, stale_minutes)),
        "--loop",
        "--interval-seconds",
        str(max(0, interval_seconds)),
        "--max-runs",
        "0",
        "--advance-self-improvement",
        "--self-improvement-interval-minutes",
        "60",
        "--self-improvement-max-steps",
        "1",
    ]
    if notify_telegram:
        command.append("--notify-telegram")

    stdout_handle = stdout_path.open("a", encoding="utf-8")
    stderr_handle = stderr_path.open("a", encoding="utf-8")
    popen_kwargs: dict[str, Any] = {
        "cwd": str(root),
        "stdout": stdout_handle,
        "stderr": stderr_handle,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        )
    else:
        popen_kwargs["start_new_session"] = True

    try:
        process = subprocess.Popen(command, **popen_kwargs)
    finally:
        stdout_handle.close()
        stderr_handle.close()
    return {
        "schema": "fluxio.mission_watchdog_autostart.v1",
        "ok": True,
        "started": True,
        "reason": "missing_or_stale",
        "pid": process.pid,
        "command": command,
        "stdoutPath": str(stdout_path),
        "stderrPath": str(stderr_path),
        "previousSupervisor": current,
    }
