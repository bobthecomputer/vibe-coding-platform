from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path

from .models import (
    ActionApprovalGate,
    ActionExecutionRecord,
    ActionProposal,
    ActionResultEnvelope,
    DelegatedRuntimeSession,
    ExecutionPolicy,
    ExecutionScope,
    Mission,
    PlannedStep,
    WorkspaceProfile,
    utc_now_iso,
)
from .research import search_workspace
from .runtimes import runtime_adapter_map
from .runtime_supervisor import DelegatedRuntimeSupervisor
from .safety import risk_level_for_command

PROFILE_EXECUTION_DEFAULTS = {
    "beginner": {
        "scope": "isolated",
        "approval_mode": "strict",
        "explanation_depth": "high",
        "delegation": "low",
    },
    "builder": {
        "scope": "isolated",
        "approval_mode": "tiered",
        "explanation_depth": "medium",
        "delegation": "balanced",
    },
    "advanced": {
        "scope": "isolated",
        "approval_mode": "tiered",
        "explanation_depth": "low",
        "delegation": "balanced",
    },
    "experimental": {
        "scope": "isolated",
        "approval_mode": "hands_free",
        "explanation_depth": "low",
        "delegation": "high",
    },
}

WRITE_HINTS = ("implement", "edit", "update", "patch", "fix", "write", "refactor")
CREATE_HINTS = ("create", "new file", "draft", "author")
DELEGATE_HINTS = ("delegate", "runtime lane", "openclaw", "hermes")
STATUS_HINTS = ("status", "ground", "inspect mutable", "workspace state")
DIFF_HINTS = ("rollout", "diff", "next iteration", "changed files")
VERIFY_HINTS = ("verify", "test", "build", "lint", "smoke")


class ExecutionAdapter(ABC):
    @abstractmethod
    def build_policy(self, profile_name: str) -> ExecutionPolicy:
        raise NotImplementedError

    @abstractmethod
    def prepare_scope(
        self,
        workspace_root: Path,
        mission_id: str,
        requested_scope: str = "",
        profile_name: str = "builder",
    ) -> ExecutionScope:
        raise NotImplementedError

    @abstractmethod
    def build_action_proposal(
        self,
        step: PlannedStep,
        objective: str,
        workspace_root: Path,
        verification_commands: list[str],
        runtime_id: str,
        execution_scope: ExecutionScope,
        execution_policy: ExecutionPolicy,
    ) -> ActionProposal:
        raise NotImplementedError

    @abstractmethod
    def execute(
        self,
        proposal: ActionProposal,
        workspace_root: Path,
        execution_scope: ExecutionScope,
        execution_policy: ExecutionPolicy,
        timeout_seconds: int = 90,
        approval_override: bool = False,
    ) -> ActionExecutionRecord:
        raise NotImplementedError


class HybridExecutionAdapter(ExecutionAdapter):
    def build_policy(self, profile_name: str) -> ExecutionPolicy:
        defaults = PROFILE_EXECUTION_DEFAULTS.get(
            (profile_name or "builder").strip().lower(),
            PROFILE_EXECUTION_DEFAULTS["builder"],
        )
        approval_mode = defaults["approval_mode"]
        auto_allowed = [
            "workspace_search",
            "file_read",
            "git_status",
            "git_diff",
            "test_run",
            "runtime_delegate",
        ]
        approval_required = ["git_commit", "shell_command"]
        if approval_mode == "strict":
            approval_required.extend(["file_patch", "file_write"])
        elif approval_mode == "tiered":
            approval_required.extend(["file_patch", "file_write"])
        return ExecutionPolicy(
            profile_name=(profile_name or "builder"),
            approval_mode=approval_mode,
            explanation_depth=defaults["explanation_depth"],
            delegation_aggressiveness=defaults["delegation"],
            auto_allowed_kinds=auto_allowed,
            approval_required_kinds=approval_required,
            destructive_requires_approval=True,
        )

    def prepare_scope(
        self,
        workspace_root: Path,
        mission_id: str,
        requested_scope: str = "",
        profile_name: str = "builder",
    ) -> ExecutionScope:
        workspace_root = workspace_root.resolve()
        requested = requested_scope or PROFILE_EXECUTION_DEFAULTS.get(
            (profile_name or "builder").strip().lower(),
            PROFILE_EXECUTION_DEFAULTS["builder"],
        )["scope"]
        direct_scope = ExecutionScope(
            requested=requested,
            strategy="direct",
            execution_root=str(workspace_root),
            workspace_root=str(workspace_root),
            isolated=False,
            status="ready",
            detail="Mission is executing in the primary workspace.",
        )
        if requested == "direct" or not _is_git_workspace(workspace_root):
            if requested != "direct" and not _is_git_workspace(workspace_root):
                direct_scope.status = "fallback"
                direct_scope.detail = "Git isolation is unavailable, so Fluxio is using the primary workspace."
            return direct_scope

        branch_name = f"fluxio/{mission_id}"
        worktree_path = workspace_root.parent / f".fluxio-worktrees-{workspace_root.name}" / mission_id
        if worktree_path.exists():
            return ExecutionScope(
                requested=requested,
                strategy="git_worktree",
                execution_root=str(worktree_path),
                workspace_root=str(workspace_root),
                branch_name=branch_name,
                worktree_path=str(worktree_path),
                isolated=True,
                status="ready",
                detail="Mission is isolated in a dedicated git worktree.",
            )

        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        add_attempts = [
            ["git", "worktree", "add", "-b", branch_name, str(worktree_path), "HEAD"],
            ["git", "worktree", "add", "--force", str(worktree_path), "HEAD"],
        ]
        last_error = ""
        for command in add_attempts:
            try:
                completed = subprocess.run(  # noqa: S603
                    command,
                    cwd=str(workspace_root),
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
            except OSError as exc:
                last_error = str(exc)
                continue
            if completed.returncode == 0:
                return ExecutionScope(
                    requested=requested,
                    strategy="git_worktree",
                    execution_root=str(worktree_path),
                    workspace_root=str(workspace_root),
                    branch_name=branch_name,
                    worktree_path=str(worktree_path),
                    isolated=True,
                    status="ready",
                    detail="Mission is isolated in a dedicated git worktree.",
                )
            last_error = (completed.stderr or completed.stdout).strip()

        direct_scope.status = "fallback"
        direct_scope.detail = (
            "Git worktree setup failed, so Fluxio fell back to the primary workspace. "
            f"{last_error}".strip()
        )
        return direct_scope

    def build_action_proposal(
        self,
        step: PlannedStep,
        objective: str,
        workspace_root: Path,
        verification_commands: list[str],
        runtime_id: str,
        execution_scope: ExecutionScope,
        execution_policy: ExecutionPolicy,
    ) -> ActionProposal:
        lowered = f"{step.title} {step.description} {objective}".lower()
        action_id = f"action_{uuid.uuid4().hex[:10]}"
        event_id = f"evt_{uuid.uuid4().hex[:10]}"
        scope_root = Path(execution_scope.execution_root or workspace_root)
        target_path = _infer_target_path(objective, scope_root)

        if _matches(lowered, VERIFY_HINTS):
            command = verification_commands[0] if verification_commands else "git diff --stat"
            return self._proposal(
                action_id=action_id,
                event_id=event_id,
                kind="test_run",
                title=f"Run verification for {step.title}",
                command=command,
                step=step,
                reason="Verification uses the real execution surface so proof reflects actual outcomes.",
                execution_scope=execution_scope,
                execution_policy=execution_policy,
                mutability_class="verify",
            )

        if _matches(lowered, DELEGATE_HINTS):
            return self._proposal(
                action_id=action_id,
                event_id=event_id,
                kind="runtime_delegate",
                title=f"Delegate {step.title} to {runtime_id}",
                step=step,
                reason="Fluxio can hand this step to the selected runtime lane and normalize the returned trace.",
                execution_scope=execution_scope,
                execution_policy=execution_policy,
                mutability_class="delegate",
                delegation_metadata={"runtime_id": runtime_id, "objective": objective},
            )

        if _matches(lowered, DIFF_HINTS):
            return self._proposal(
                action_id=action_id,
                event_id=event_id,
                kind="git_diff",
                title=f"Inspect diff surface for {step.title}",
                command="git diff --stat",
                step=step,
                reason="Diff summaries keep proof grounded in actual repo changes.",
                execution_scope=execution_scope,
                execution_policy=execution_policy,
                mutability_class="read",
            )

        if _matches(lowered, STATUS_HINTS):
            return self._proposal(
                action_id=action_id,
                event_id=event_id,
                kind="git_status",
                title=f"Inspect workspace state for {step.title}",
                command="git status --short",
                step=step,
                reason="The planner should inspect actual repo state before branching into more work.",
                execution_scope=execution_scope,
                execution_policy=execution_policy,
                mutability_class="read",
            )

        if "doc" in lowered or "constraint" in lowered or "review" in lowered:
            if target_path.exists():
                return self._proposal(
                    action_id=action_id,
                    event_id=event_id,
                    kind="file_read",
                    title=f"Read context for {step.title}",
                    step=step,
                    reason="Fluxio reads the actual file before it edits or delegates follow-up work.",
                    execution_scope=execution_scope,
                    execution_policy=execution_policy,
                    target_path=str(target_path),
                    mutability_class="read",
                )
            return self._proposal(
                action_id=action_id,
                event_id=event_id,
                kind="workspace_search",
                title=f"Search workspace context for {step.title}",
                step=step,
                reason="Ground the plan in repo evidence before execution.",
                execution_scope=execution_scope,
                execution_policy=execution_policy,
                query=r"TODO|FIXME|README|roadmap|plan|mission",
                args={"include_glob": "**/*", "max_results": 12},
                mutability_class="read",
            )

        if _matches(lowered, WRITE_HINTS) or _matches(lowered, CREATE_HINTS):
            create_mode = _matches(lowered, CREATE_HINTS) or not target_path.exists()
            patch_kind = "file_write" if create_mode else "file_patch"
            content = (
                _generated_file_content(step, objective, target_path)
                if create_mode
                else _generated_patch_content(step, objective, target_path)
            )
            title = (
                f"Create mission artifact for {step.title}"
                if create_mode
                else f"Patch target file for {step.title}"
            )
            return self._proposal(
                action_id=action_id,
                event_id=event_id,
                kind=patch_kind,
                title=title,
                step=step,
                reason="This step requires a real file mutation instead of a placeholder summary.",
                execution_scope=execution_scope,
                execution_policy=execution_policy,
                target_path=str(target_path),
                args={"content": content},
                mutability_class="write",
            )

        return self._proposal(
            action_id=action_id,
            event_id=event_id,
            kind="workspace_search",
            title=f"Explore workspace for {step.title}",
            step=step,
            reason="Fallback to real repo exploration when no sharper action is available yet.",
            execution_scope=execution_scope,
            execution_policy=execution_policy,
            query=_fallback_query(objective),
            args={"include_glob": "**/*", "max_results": 10},
            mutability_class="read",
        )

    def execute(
        self,
        proposal: ActionProposal,
        workspace_root: Path,
        execution_scope: ExecutionScope,
        execution_policy: ExecutionPolicy,
        timeout_seconds: int = 90,
        approval_override: bool = False,
    ) -> ActionExecutionRecord:
        gate = ActionApprovalGate(
            required=proposal.requires_approval,
            status=(
                "approved"
                if proposal.requires_approval and approval_override
                else ("pending" if proposal.requires_approval else "not_required")
            ),
            risk_level=proposal.risk_level,
            reason=proposal.reason,
        )
        record = ActionExecutionRecord(
            action_id=proposal.action_id,
            proposal=proposal,
            gate=gate,
            attempts=1,
            event_id=proposal.event_id,
        )
        if proposal.requires_approval and not approval_override:
            record.result = ActionResultEnvelope(
                ok=False,
                error="Approval required before action execution.",
                payload={"approvalRequired": True, "policyDecision": proposal.policy_decision},
                target_path=proposal.target_path,
                result_summary="Waiting for operator approval.",
            )
            return record

        execution_root = Path(execution_scope.execution_root or workspace_root).resolve()
        start = time.monotonic()

        if proposal.kind == "workspace_search":
            results = search_workspace(
                execution_root,
                proposal.query or "mission",
                include_glob=str(proposal.args.get("include_glob", "**/*")),
                max_results=int(proposal.args.get("max_results", 12)),
            )
            return _completed_record(
                record,
                start,
                ok=True,
                stdout=json.dumps(results, indent=2),
                payload={"matches": results},
                target_path=proposal.target_path,
                result_summary="Workspace search completed.",
            )

        if proposal.kind == "file_read":
            target = _resolve_target(proposal.target_path, execution_root)
            try:
                content = target.read_text(encoding="utf-8")
            except OSError as exc:
                return _completed_record(
                    record,
                    start,
                    ok=False,
                    error=str(exc),
                    target_path=str(target),
                    result_summary="File read failed.",
                )
            return _completed_record(
                record,
                start,
                ok=True,
                stdout=content,
                payload={"targetPath": str(target)},
                target_path=str(target),
                result_summary="File read completed.",
            )

        if proposal.kind in {"file_write", "file_patch"}:
            target = _resolve_target(proposal.target_path, execution_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            content = str(proposal.args.get("content", ""))
            try:
                if proposal.kind == "file_write":
                    target.write_text(content, encoding="utf-8")
                else:
                    existing = target.read_text(encoding="utf-8") if target.exists() else ""
                    target.write_text(existing + content, encoding="utf-8")
            except OSError as exc:
                return _completed_record(
                    record,
                    start,
                    ok=False,
                    error=str(exc),
                    target_path=str(target),
                    result_summary="File mutation failed.",
                )
            return _completed_record(
                record,
                start,
                ok=True,
                stdout=f"Updated {target}",
                changed_files=_git_changed_files(execution_root),
                payload={"targetPath": str(target), "mutated": True},
                target_path=str(target),
                result_summary="File mutation completed.",
            )

        if proposal.kind == "runtime_delegate":
            runtime_id = str(proposal.delegation_metadata.get("runtime_id", "openclaw"))
            adapters = runtime_adapter_map()
            adapter = adapters.get(runtime_id)
            if adapter is None:
                return _completed_record(
                    record,
                    start,
                    ok=False,
                    error=f"Unknown runtime delegate: {runtime_id}",
                    result_summary="Delegation failed before launch.",
                )
            status = adapter.detect(execution_root)
            if not status.detected:
                return _completed_record(
                    record,
                    start,
                    ok=False,
                    error=status.doctor_summary or "Runtime is unavailable.",
                    payload={"runtimeStatus": status.doctor_summary},
                    result_summary="Delegation blocked because the runtime is missing.",
                )
            delegated_mission = Mission(
                mission_id=f"delegated_{uuid.uuid4().hex[:8]}",
                workspace_id="delegated",
                runtime_id=runtime_id,
                objective=str(proposal.delegation_metadata.get("objective", proposal.title)),
                success_checks=[],
            )
            delegated_workspace = WorkspaceProfile(
                workspace_id="delegated",
                name=execution_root.name,
                root_path=str(execution_root),
                default_runtime=runtime_id,
                workspace_type="general",
            )
            supervisor = DelegatedRuntimeSupervisor(workspace_root)
            session = supervisor.start_session(
                runtime_id=runtime_id,
                mission=delegated_mission,
                workspace=delegated_workspace,
                source_step_id=proposal.source_step_id,
            )
            snapshot = supervisor.build_session_snapshot(session)
            events = adapter.stream_events(delegated_mission) + supervisor.read_events(session)
            return _completed_record(
                record,
                start,
                ok=True,
                stdout=session.launch_command,
                payload={
                    "delegatedSession": session.__dict__,
                    "delegatedSnapshot": asdict(snapshot),
                    "events": events,
                },
                result_summary="Delegated runtime lane launched under Fluxio supervision.",
            )

        command = proposal.command.strip()
        completed = subprocess.run(  # noqa: S603
            command,
            shell=True,
            cwd=str(execution_root),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return _completed_record(
            record,
            start,
            ok=completed.returncode == 0,
            exit_code=completed.returncode,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
            changed_files=_git_changed_files(execution_root),
            target_path=proposal.target_path,
            result_summary=f"{proposal.kind} completed with exit code {completed.returncode}.",
        )

    def _proposal(
        self,
        *,
        action_id: str,
        event_id: str,
        kind: str,
        title: str,
        step: PlannedStep,
        reason: str,
        execution_scope: ExecutionScope,
        execution_policy: ExecutionPolicy,
        command: str = "",
        query: str = "",
        args: dict | None = None,
        target_path: str = "",
        mutability_class: str = "read",
        delegation_metadata: dict | None = None,
    ) -> ActionProposal:
        proposal = ActionProposal(
            action_id=action_id,
            kind=kind,
            title=title,
            command=command,
            query=query,
            args=args or {},
            source_step_id=step.step_id,
            reason=reason,
            event_id=event_id,
            target_path=target_path,
            target_scope=("worktree" if execution_scope.isolated else "workspace"),
            mutability_class=mutability_class,
            branch_name=execution_scope.branch_name,
            worktree_path=execution_scope.worktree_path,
            delegation_metadata=delegation_metadata or {},
            replay_cursor=event_id,
        )
        proposal.risk_level = _risk_for_proposal(proposal)
        proposal.policy_decision = _policy_decision(proposal, execution_policy)
        proposal.requires_approval = proposal.policy_decision == "requires_approval"
        return proposal


DEFAULT_EXECUTION_ADAPTER = HybridExecutionAdapter()


def build_execution_policy(profile_name: str) -> ExecutionPolicy:
    return DEFAULT_EXECUTION_ADAPTER.build_policy(profile_name)


def prepare_execution_scope(
    workspace_root: Path,
    mission_id: str,
    requested_scope: str = "",
    profile_name: str = "builder",
) -> ExecutionScope:
    return DEFAULT_EXECUTION_ADAPTER.prepare_scope(
        workspace_root=workspace_root,
        mission_id=mission_id,
        requested_scope=requested_scope,
        profile_name=profile_name,
    )


def build_action_proposal(
    step: PlannedStep,
    objective: str,
    workspace_root: Path,
    verification_commands: list[str],
    runtime_id: str = "openclaw",
    execution_scope: ExecutionScope | None = None,
    execution_policy: ExecutionPolicy | None = None,
) -> ActionProposal:
    execution_scope = execution_scope or ExecutionScope(
        execution_root=str(workspace_root),
        workspace_root=str(workspace_root),
        status="ready",
    )
    execution_policy = execution_policy or build_execution_policy("builder")
    return DEFAULT_EXECUTION_ADAPTER.build_action_proposal(
        step=step,
        objective=objective,
        workspace_root=workspace_root,
        verification_commands=verification_commands,
        runtime_id=runtime_id,
        execution_scope=execution_scope,
        execution_policy=execution_policy,
    )


def execute_action(
    proposal: ActionProposal,
    workspace_root: Path,
    execution_scope: ExecutionScope | None = None,
    execution_policy: ExecutionPolicy | None = None,
    timeout_seconds: int = 90,
    approval_override: bool = False,
) -> ActionExecutionRecord:
    execution_scope = execution_scope or ExecutionScope(
        execution_root=str(workspace_root),
        workspace_root=str(workspace_root),
        status="ready",
    )
    execution_policy = execution_policy or build_execution_policy("builder")
    return DEFAULT_EXECUTION_ADAPTER.execute(
        proposal=proposal,
        workspace_root=workspace_root,
        execution_scope=execution_scope,
        execution_policy=execution_policy,
        timeout_seconds=timeout_seconds,
        approval_override=approval_override,
    )


def cleanup_execution_scope(execution_scope: ExecutionScope | None) -> dict[str, object]:
    if execution_scope is None:
        return {"cleaned": False, "reason": "missing_scope"}
    if not execution_scope.isolated or execution_scope.strategy != "git_worktree":
        return {"cleaned": False, "reason": "not_isolated"}

    workspace_root = Path(execution_scope.workspace_root).resolve() if execution_scope.workspace_root else None
    worktree_path = Path(execution_scope.worktree_path or execution_scope.execution_root).resolve()
    if not worktree_path.exists():
        return {"cleaned": False, "reason": "missing_worktree", "path": str(worktree_path)}

    details: list[str] = []
    if workspace_root and workspace_root.exists():
        try:
            completed = subprocess.run(  # noqa: S603
                ["git", "worktree", "remove", "--force", str(worktree_path)],
                cwd=str(workspace_root),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if completed.returncode == 0:
                details.append("git_worktree_removed")
            else:
                details.append((completed.stderr or completed.stdout).strip() or "git_worktree_remove_failed")
        except OSError as exc:
            details.append(str(exc))

        try:
            subprocess.run(  # noqa: S603
                ["git", "worktree", "prune"],
                cwd=str(workspace_root),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except OSError:
            pass

        branch_name = (execution_scope.branch_name or "").strip()
        if branch_name.startswith("fluxio/"):
            try:
                subprocess.run(  # noqa: S603
                    ["git", "branch", "-D", branch_name],
                    cwd=str(workspace_root),
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
            except OSError:
                pass

    if worktree_path.exists():
        worktree_parent = worktree_path.parent
        shutil.rmtree(worktree_path, ignore_errors=True)
        if not worktree_path.exists():
            details.append("worktree_directory_removed")
        if worktree_parent.exists():
            try:
                next(worktree_parent.iterdir())
            except StopIteration:
                worktree_parent.rmdir()

    return {
        "cleaned": not worktree_path.exists(),
        "path": str(worktree_path),
        "details": details,
    }


def _is_git_workspace(workspace_root: Path) -> bool:
    return (workspace_root / ".git").exists()


def _git_changed_files(root: Path) -> list[str]:
    if not _is_git_workspace(root) and not (root / ".git").exists():
        return []
    try:
        completed = subprocess.run(  # noqa: S603
            ["git", "status", "--short"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError:
        return []
    changed: list[str] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        changed.append(line[3:].strip())
    return changed


def _policy_decision(proposal: ActionProposal, policy: ExecutionPolicy) -> str:
    if proposal.risk_level == "high" or proposal.mutability_class == "destructive":
        return "requires_approval"
    if proposal.kind in policy.approval_required_kinds:
        return "requires_approval"
    if proposal.kind in policy.auto_allowed_kinds:
        return "auto_run"
    if policy.approval_mode == "hands_free":
        return "auto_run"
    return "requires_approval"


def _risk_for_proposal(proposal: ActionProposal) -> str:
    if proposal.kind in {"file_write", "file_patch"}:
        lowered = proposal.target_path.lower()
        if ".env" in lowered or "\\.git" in lowered or "/.git" in lowered:
            return "high"
        return "medium"
    if proposal.kind == "runtime_delegate":
        return "medium"
    if proposal.command:
        return risk_level_for_command(proposal.command)
    return "low"


def _fallback_query(objective: str) -> str:
    words = re.findall(r"[A-Za-z0-9_]+", objective)
    return "|".join(words[:4]) or "mission"


def _matches(text: str, hints: tuple[str, ...]) -> bool:
    return any(hint in text for hint in hints)


def _infer_target_path(objective: str, workspace_root: Path) -> Path:
    explicit_matches = re.findall(r"[\w./\\-]+\.[A-Za-z0-9]+", objective)
    for match in explicit_matches:
        candidate = (workspace_root / match).resolve()
        if str(candidate).startswith(str(workspace_root.resolve())):
            return candidate
    preferred = [
        workspace_root / "README.md",
        workspace_root / "docs" / "ROADMAP.md",
        workspace_root / "docs" / "PRD.md",
        workspace_root / "MISSION_NOTES.md",
    ]
    for candidate in preferred:
        if candidate.exists():
            return candidate
    return workspace_root / "MISSION_NOTES.md"


def _generated_file_content(step: PlannedStep, objective: str, target_path: Path) -> str:
    if target_path.suffix.lower() in {".md", ".txt", ".rst"}:
        return (
            f"# {step.title}\n\n"
            f"- Objective: {objective}\n"
            f"- Triggered by step: {step.description or step.title}\n"
            f"- Generated by Fluxio hybrid execution engine at {utc_now_iso()}\n"
        )
    return _comment_block(
        target_path,
        [
            f"Fluxio created this artifact for step: {step.title}",
            f"Objective: {objective}",
        ],
    )


def _generated_patch_content(step: PlannedStep, objective: str, target_path: Path) -> str:
    if target_path.suffix.lower() in {".md", ".txt", ".rst"}:
        return (
            f"\n\n## Fluxio Mission Note\n"
            f"- Step: {step.title}\n"
            f"- Objective: {objective}\n"
            f"- Updated: {utc_now_iso()}\n"
        )
    return "\n" + _comment_block(
        target_path,
        [
            f"Fluxio mission note: {step.title}",
            f"Objective: {objective}",
        ],
    )


def _comment_block(target_path: Path, lines: list[str]) -> str:
    suffix = target_path.suffix.lower()
    if suffix == ".html":
        return "\n".join([f"<!-- {line} -->" for line in lines]) + "\n"
    if suffix in {".py", ".sh", ".yml", ".yaml", ".toml"}:
        return "\n".join([f"# {line}" for line in lines]) + "\n"
    if suffix in {".css", ".xml"}:
        return "\n".join([f"/* {line} */" for line in lines]) + "\n"
    return "\n".join([f"// {line}" for line in lines]) + "\n"


def _resolve_target(target_path: str, execution_root: Path) -> Path:
    candidate = Path(target_path)
    if candidate.is_absolute():
        return candidate
    return (execution_root / candidate).resolve()


def _completed_record(
    record: ActionExecutionRecord,
    started_at: float,
    *,
    ok: bool,
    exit_code: int = 0,
    stdout: str = "",
    stderr: str = "",
    error: str = "",
    changed_files: list[str] | None = None,
    payload: dict | None = None,
    target_path: str = "",
    result_summary: str = "",
) -> ActionExecutionRecord:
    record.result = ActionResultEnvelope(
        ok=ok,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_ms=int((time.monotonic() - started_at) * 1000),
        error=error,
        changed_files=changed_files or [],
        payload=payload or {},
        target_path=target_path,
        result_summary=result_summary,
    )
    record.acked = True
    record.executed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return record
