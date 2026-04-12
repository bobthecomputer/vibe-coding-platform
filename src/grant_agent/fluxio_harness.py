from __future__ import annotations

import time
import uuid
from dataclasses import asdict
from pathlib import Path

from .action_executor import (
    build_action_proposal,
    build_execution_policy,
    execute_action,
    prepare_execution_scope,
    requested_scope_for_execution_target,
)
from .checkpoints import CheckpointStore
from .doc_ingestion import ingest_docs
from .engine import AutonomousEngine
from .models import (
    ActionExecutionRecord,
    ActionProposal,
    DerivedTask,
    ExecutionPolicy,
    ExecutionScope,
    HarnessExecutionContext,
    ImprovementQueueItem,
    ModelRouteConfig,
    PlanRevision,
    PlannedStep,
    RoutingDecision,
    RunState,
    TimelineEvent,
    VerificationResult,
    utc_now_iso,
)
from .planner import PlanBundle, build_docs_first_plan
from .profiles import PersonalizationProfile
from .reporting import write_run_report
from .runtime_supervisor import DelegatedRuntimeSupervisor
from .session_store import SessionStore
from .skill_library import SkillLibrary
from .verification import VerificationRunner


def guided_profile_defaults(name: str) -> dict:
    normalized = (name or "builder").strip().lower()
    defaults = {
        "beginner": {
            "autonomy_level": "guided",
            "approval_strictness": "high",
            "explanation_level": "high",
            "innovation_scope": "strict",
            "execution_scope": "isolated",
            "approval_mode": "strict",
            "delegation_aggressiveness": "low",
            "repeated_failure_broadening_threshold": 1,
            "learned_skill_aggressiveness": "low",
            "routing_strategy": "planner_premium_executor_efficient",
            "harness_experimentation_visibility": "hidden",
        },
        "builder": {
            "autonomy_level": "balanced",
            "approval_strictness": "medium",
            "explanation_level": "medium",
            "innovation_scope": "bounded",
            "execution_scope": "isolated",
            "approval_mode": "tiered",
            "delegation_aggressiveness": "balanced",
            "repeated_failure_broadening_threshold": 2,
            "learned_skill_aggressiveness": "medium",
            "routing_strategy": "planner_premium_executor_efficient",
            "harness_experimentation_visibility": "visible",
        },
        "advanced": {
            "autonomy_level": "high",
            "approval_strictness": "medium",
            "explanation_level": "low",
            "innovation_scope": "bounded",
            "execution_scope": "isolated",
            "approval_mode": "tiered",
            "delegation_aggressiveness": "balanced",
            "repeated_failure_broadening_threshold": 2,
            "learned_skill_aggressiveness": "medium",
            "routing_strategy": "uniform_quality",
            "harness_experimentation_visibility": "visible",
        },
        "experimental": {
            "autonomy_level": "high",
            "approval_strictness": "low",
            "explanation_level": "low",
            "innovation_scope": "bounded",
            "execution_scope": "isolated",
            "approval_mode": "hands_free",
            "delegation_aggressiveness": "high",
            "repeated_failure_broadening_threshold": 3,
            "learned_skill_aggressiveness": "high",
            "routing_strategy": "budget_first",
            "harness_experimentation_visibility": "wide",
        },
    }
    if normalized in defaults:
        return defaults[normalized]
    legacy_mapping = {
        "hands_free_builder": "builder",
        "minimal_focus": "beginner",
        "research_sprint": "advanced",
        "safety_gate": "beginner",
    }
    return defaults.get(legacy_mapping.get(normalized, "builder"), defaults["builder"])


def normalize_route_overrides(route_overrides: object) -> list[dict]:
    if not isinstance(route_overrides, list):
        return []
    normalized: list[dict] = []
    for item in route_overrides:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        provider = str(item.get("provider", "")).strip().lower()
        model = str(item.get("model", "")).strip()
        if role not in {"planner", "executor", "verifier"} or not provider or not model:
            continue
        row = {
            "role": role,
            "provider": provider,
            "model": model,
        }
        effort = str(item.get("effort", "")).strip().lower()
        if effort:
            row["effort"] = effort
        budget_class = str(item.get("budgetClass", item.get("budget_class", ""))).strip().lower()
        if budget_class:
            row["budgetClass"] = budget_class
        normalized.append(row)
    deduped: list[dict] = []
    seen_roles: set[str] = set()
    for item in normalized:
        if item["role"] in seen_roles:
            continue
        seen_roles.add(item["role"])
        deduped.append(item)
    return deduped


def resolve_efficiency_autotune_policy(
    *,
    harness_lab_snapshot: dict,
    auto_optimize_routing: bool,
    requested_strategy: str,
) -> dict:
    efficiency = harness_lab_snapshot.get("efficiency", {})
    session_health = harness_lab_snapshot.get("sessionHealth", {})
    total_runs = int(efficiency.get("totalRuns", 0) or 0)
    completion_rate = int(efficiency.get("completionRate", 0) or 0)
    approval_pause_rate = int(efficiency.get("approvalPauseRate", 0) or 0)
    average_verification_failures = float(
        efficiency.get("averageVerificationFailures", 0.0) or 0.0
    )
    stale_heartbeat_count = int(session_health.get("staleHeartbeatCount", 0) or 0)
    normalized_requested = (requested_strategy or "profile_default").strip().lower()
    eligible = total_runs >= 3
    if not auto_optimize_routing:
        return {
            "enabled": False,
            "eligible": eligible,
            "reason": "Auto-optimize routing is disabled for this workspace.",
            "requestedStrategy": normalized_requested,
            "routingStrategy": normalized_requested,
            "appliedPolicy": {},
            "forcePauseOnFailure": False,
        }
    if not eligible:
        return {
            "enabled": True,
            "eligible": False,
            "reason": "Not enough local data yet (need at least 3 runs).",
            "requestedStrategy": normalized_requested,
            "routingStrategy": normalized_requested,
            "appliedPolicy": {},
            "forcePauseOnFailure": False,
        }
    if stale_heartbeat_count > 0 or completion_rate < 50:
        return {
            "enabled": True,
            "eligible": True,
            "reason": (
                "Stale runtime heartbeat or low completion rate triggered a safer routing policy."
            ),
            "requestedStrategy": normalized_requested,
            "routingStrategy": "uniform_quality",
            "appliedPolicy": {
                "policy": "safety_bias",
                "routingStrategy": "uniform_quality",
                "approvalMode": "tiered",
                "delegationAggressiveness": "low",
                "pauseOnVerificationFailure": True,
            },
            "forcePauseOnFailure": True,
        }
    if approval_pause_rate > 40:
        return {
            "enabled": True,
            "eligible": True,
            "reason": "Approval pauses are high, so delegation is reduced while keeping tiered approvals.",
            "requestedStrategy": normalized_requested,
            "routingStrategy": normalized_requested,
            "appliedPolicy": {
                "policy": "approval_pressure",
                "routingStrategy": normalized_requested,
                "approvalMode": "tiered",
                "delegationAggressiveness": "low",
                "pauseOnVerificationFailure": True,
            },
            "forcePauseOnFailure": True,
        }
    if (
        completion_rate >= 70
        and stale_heartbeat_count == 0
        and average_verification_failures <= 1.0
    ):
        return {
            "enabled": True,
            "eligible": True,
            "reason": "Local runs are stable, so Fluxio can use a more efficient executor profile.",
            "requestedStrategy": normalized_requested,
            "routingStrategy": "planner_premium_executor_efficient",
            "appliedPolicy": {
                "policy": "stable_efficiency",
                "routingStrategy": "planner_premium_executor_efficient",
                "approvalMode": "tiered",
                "delegationAggressiveness": "balanced",
                "pauseOnVerificationFailure": True,
            },
            "forcePauseOnFailure": True,
        }
    return {
        "enabled": True,
        "eligible": True,
        "reason": "No stronger local signal yet; Fluxio keeps the requested routing strategy.",
        "requestedStrategy": normalized_requested,
        "routingStrategy": normalized_requested,
        "appliedPolicy": {},
        "forcePauseOnFailure": False,
    }


def _budget_class_for_model(model: str, override_value: str = "") -> str:
    normalized_override = (override_value or "").strip().lower()
    if normalized_override:
        return normalized_override
    normalized_model = (model or "").strip().lower()
    if "mini" in normalized_model or "highspeed" in normalized_model:
        return "efficient"
    return "premium"


def recommended_model_routes(
    profile_name: str,
    routing_strategy_override: str | None = None,
    route_overrides: list[dict] | None = None,
) -> list[ModelRouteConfig]:
    defaults = guided_profile_defaults(profile_name)
    strategy = (routing_strategy_override or "profile_default").strip().lower()
    strategy_source = "strategy"
    if not strategy or strategy == "profile_default":
        strategy = defaults["routing_strategy"]
        strategy_source = "profile_default"
    override_map = {
        item["role"]: item for item in normalize_route_overrides(route_overrides or [])
    }
    if strategy == "uniform_quality":
        planner = ("openai", "gpt-5.4")
        executor = ("openai", "gpt-5.4")
    elif strategy == "budget_first":
        planner = ("openai", "gpt-5.4-mini")
        executor = ("openai", "gpt-5.4-mini")
    else:
        planner = ("openai", "gpt-5.4")
        executor = ("openai", "gpt-5.4-mini")
    routes = [
        ModelRouteConfig(
            role="planner",
            provider=planner[0],
            model=planner[1],
            effort="high",
            budget_class="premium" if planner[1] == "gpt-5.4" else "efficient",
            explanation=(
                "Planner route resolved from workspace strategy."
                if strategy_source == "strategy"
                else "Planner route resolved from profile default strategy."
            ),
        ),
        ModelRouteConfig(
            role="executor",
            provider=executor[0],
            model=executor[1],
            effort="medium",
            budget_class="efficient" if executor[1] != "gpt-5.4" else "premium",
            explanation=(
                "Executor route resolved from workspace strategy."
                if strategy_source == "strategy"
                else "Executor route resolved from profile default strategy."
            ),
        ),
        ModelRouteConfig(
            role="verifier",
            provider="openai",
            model="gpt-5.4",
            effort="high",
            budget_class="premium",
            explanation="Verifier route resolved from profile confidence defaults.",
        ),
        ModelRouteConfig(
            role="summarizer",
            provider="openai",
            model="gpt-5.4-mini",
            effort="medium",
            budget_class="efficient",
            explanation="Summaries stay efficient unless overridden.",
        ),
        ModelRouteConfig(
            role="skill_curator",
            provider="openai",
            model="gpt-5.4-mini",
            effort="medium",
            budget_class="efficient",
            explanation="Skill curation is efficient and reviewable by default.",
        ),
        ModelRouteConfig(
            role="guide_author",
            provider="openai",
            model="gpt-5.4-mini",
            effort="medium",
            budget_class="efficient",
            explanation="Guidance and onboarding copy stay concise and adaptive to the selected profile.",
        ),
    ]
    for index, route in enumerate(routes):
        override = override_map.get(route.role)
        if not override:
            continue
        routes[index] = ModelRouteConfig(
            role=route.role,
            provider=override.get("provider", route.provider),
            model=override.get("model", route.model),
            effort=override.get("effort", route.effort),
            budget_class=_budget_class_for_model(
                override.get("model", route.model),
                override.get("budgetClass", ""),
            ),
            fallback_policy="same_provider",
            explanation="Route override from workspace runtime contract.",
        )
    return routes


class LegacyHarnessAdapter:
    harness_id = "legacy_autonomous_engine"

    def __init__(self, engine: AutonomousEngine) -> None:
        self.engine = engine

    def run(self, **kwargs: object) -> dict:
        return self.engine.run(**kwargs)


class FluxioHarness:
    harness_id = "fluxio_hybrid"

    def __init__(
        self,
        compatibility_harness: LegacyHarnessAdapter,
        session_store: SessionStore,
        verification_runner: VerificationRunner,
        skill_library: SkillLibrary,
    ) -> None:
        self.compatibility_harness = compatibility_harness
        self.session_store = session_store
        self.verification_runner = verification_runner
        self.skill_library = skill_library

    def run(
        self,
        objective: str,
        docs: list[str],
        project_profile: str,
        verify_commands: list[str],
        repo_path: Path,
        iterations: int,
        max_handoffs: int,
        max_runtime_seconds: int,
        mission_id: str | None = None,
        runtime_id: str = "openclaw",
        profile_name: str = "builder",
        selected_profile: PersonalizationProfile | None = None,
        resume_from_session_id: str | None = None,
        resume_from_checkpoint_path: str | None = None,
        checkpoint_every: int = 1,
        autopilot_guardrails: dict | None = None,
        routing_strategy_override: str | None = None,
        route_overrides: list[dict] | None = None,
        execution_target_preference: str | None = None,
    ) -> dict:
        del max_handoffs
        guardrails = autopilot_guardrails or {
            "pause_on_handoff": True,
            "pause_on_verification_failure": True,
        }
        started_at = time.monotonic()
        resolved_mission_id = mission_id or f"mission_{uuid.uuid4().hex[:8]}"
        profile_defaults = guided_profile_defaults(profile_name)
        route_configs = recommended_model_routes(
            profile_name,
            routing_strategy_override=routing_strategy_override,
            route_overrides=route_overrides,
        )
        execution_policy = build_execution_policy(profile_name)
        execution_scope = prepare_execution_scope(
            workspace_root=repo_path,
            mission_id=resolved_mission_id,
            requested_scope=(
                requested_scope_for_execution_target(execution_target_preference)
                or profile_defaults.get("execution_scope", "")
            ),
            profile_name=profile_name,
        )
        execution_context = HarnessExecutionContext(
            mission_id=resolved_mission_id,
            workspace_root=str(repo_path),
            runtime_id=runtime_id,
            profile_name=profile_name,
            execution_scope=execution_scope,
            execution_policy=execution_policy,
            route_configs=route_configs,
            broadening_threshold=int(
                profile_defaults["repeated_failure_broadening_threshold"]
            ),
            innovation_scope=str(profile_defaults["innovation_scope"]),
            harness_id=self.harness_id,
        )

        resumed_state: dict | None = None
        if resume_from_session_id:
            previous_path = self.session_store.get_session_path(resume_from_session_id)
            if previous_path and (previous_path / "state.json").exists():
                resumed_state = self.session_store.read_state(previous_path)
                if not docs:
                    docs = [
                        item.get("source", "")
                        for item in resumed_state.get("doc_evidence", [])
                        if item.get("source")
                    ]
        if resume_from_checkpoint_path:
            checkpoint_payload = CheckpointStore.load(Path(resume_from_checkpoint_path))
            resumed_state = checkpoint_payload.get("state", resumed_state)
            if not docs:
                docs = checkpoint_payload.get("doc_sources", docs)
        if resumed_state:
            loaded_scope = self._load_execution_scope(resumed_state)
            loaded_policy = self._load_execution_policy(resumed_state)
            loaded_routes = self._load_route_configs(resumed_state)
            if loaded_scope is not None:
                execution_scope = loaded_scope
            if loaded_policy is not None:
                execution_policy = loaded_policy
            keep_loaded_routes = bool(
                loaded_routes
                and not normalize_route_overrides(route_overrides or [])
                and (
                    not routing_strategy_override
                    or routing_strategy_override == "profile_default"
                )
            )
            if keep_loaded_routes:
                route_configs = loaded_routes
            execution_context.execution_scope = execution_scope
            execution_context.execution_policy = execution_policy
            execution_context.route_configs = route_configs

        session_path = self.session_store.create_session(
            objective=objective,
            parent_session_id=resume_from_session_id,
        )
        metadata = self.session_store.read_metadata(session_path)
        session_id = metadata["session_id"]
        lineage = []
        if resumed_state:
            lineage.extend(resumed_state.get("session_lineage", []))
        lineage.append(session_id)
        checkpoint_store = CheckpointStore(session_path)
        docs_evidence = ingest_docs(docs=docs, repo_path=repo_path, session_path=session_path)
        plan_bundle = build_docs_first_plan(objective=objective, docs=docs)

        plan_revisions = self._load_plan_revisions(resumed_state, plan_bundle)
        derived_tasks = self._load_derived_tasks(resumed_state)
        improvement_queue = self._load_improvement_queue(resumed_state)
        action_history = self._load_action_history(resumed_state)
        routing_decisions = self._load_routing_decisions(resumed_state)
        verification_failures = (
            list(resumed_state.get("verification_failures", []))
            if resumed_state
            else []
        )
        selected_skills = self.skill_library.retrieve(task_brief=objective, top_k=4)
        skill_usage = list(resumed_state.get("skill_usage", [])) if resumed_state else []
        learned_skill_events = (
            list(resumed_state.get("learned_skill_events", [])) if resumed_state else []
        )
        delegated_runtime_sessions = (
            list(resumed_state.get("delegated_runtime_sessions", []))
            if resumed_state
            else []
        )
        changed_files = list(resumed_state.get("changed_files", [])) if resumed_state else []
        decisions = list(resumed_state.get("decisions", [])) if resumed_state else []
        risks = list(resumed_state.get("risks", [])) if resumed_state else []
        completed_steps = (
            list(resumed_state.get("completed_steps", [])) if resumed_state else []
        )
        notes = list(resumed_state.get("notes", [])) if resumed_state else []
        autopilot_status = "running"
        autopilot_pause_reason = ""
        last_verification_results: list[VerificationResult] = []
        repeated_failure_count = (
            int(resumed_state.get("repeated_failure_count", 0)) if resumed_state else 0
        )

        decisions.append("Fluxio hybrid harness orchestrated this mission.")
        if selected_profile:
            decisions.append(f"Resolved profile: {selected_profile.name}")
        notes.append(
            f"Role-based routing: {', '.join([item.role + '=' + item.model for item in route_configs])}"
        )
        notes.append(
            f"Selected skills: {', '.join([item['label'] for item in selected_skills]) or 'none'}"
        )
        notes.append(
            f"Execution scope: {execution_scope.strategy} at {execution_scope.execution_root or repo_path}"
        )
        notes.append(
            f"Execution policy: {execution_policy.approval_mode} approvals with {execution_policy.delegation_aggressiveness} delegation."
        )
        execution_root = Path(execution_scope.execution_root or repo_path)
        runtime_supervisor = DelegatedRuntimeSupervisor(repo_path)

        self.session_store.append_timeline(
            session_path,
            TimelineEvent(
                kind="harness.started",
                message="Fluxio harness started mission execution.",
                metadata={
                    "mission_id": execution_context.mission_id,
                    "runtime_id": runtime_id,
                    "profile_name": profile_name,
                },
            ),
        )

        for role in (
            "planner",
            "executor",
            "verifier",
            "summarizer",
            "skill_curator",
            "guide_author",
        ):
            route = next((item for item in route_configs if item.role == role), None)
            if route:
                routing_decisions.append(
                    asdict(
                        RoutingDecision(
                            role=route.role,
                            provider=route.provider,
                            model=route.model,
                            reason=route.explanation,
                            budget_class=route.budget_class,
                        )
                    )
                )

        for iteration in range(1, iterations + 1):
            (
                delegated_runtime_sessions,
                delegated_status,
                delegated_replan_trigger,
            ) = self._reconcile_delegated_sessions(
                delegated_runtime_sessions=delegated_runtime_sessions,
                plan_revisions=plan_revisions,
                runtime_supervisor=runtime_supervisor,
                notes=notes,
                risks=risks,
            )
            if delegated_status == "waiting_for_approval":
                autopilot_status = "paused"
                autopilot_pause_reason = "approval_required"
                break
            if delegated_replan_trigger == "approval_rejected":
                repeated_failure_count += 1
                self._append_revised_plan(
                    plan_revisions=plan_revisions,
                    base_revision=plan_revisions[-1],
                    trigger="approval_rejected",
                    summary="Planner revised the mission after a delegated approval was rejected.",
                    extra_steps=[
                        PlannedStep(
                            step_id=f"step_{uuid.uuid4().hex[:8]}",
                            title="Replan after delegated approval rejection",
                            description="Find a safer path after the delegated lane was rejected.",
                            kind="derived",
                        )
                    ],
                )
                continue
            if delegated_status == "running":
                autopilot_status = "paused"
                autopilot_pause_reason = "delegated_runtime_running"
                break

            if time.monotonic() - started_at >= max_runtime_seconds:
                autopilot_status = "paused"
                autopilot_pause_reason = "runtime_budget"
                decisions.append("Mission paused because runtime budget was exhausted.")
                break

            latest_revision = plan_revisions[-1]
            next_step = self._next_pending_step(latest_revision)
            if next_step is None:
                autopilot_status = "completed"
                break

            self.session_store.append_timeline(
                session_path,
                TimelineEvent(
                    kind="plan.revision",
                    message=f"Planner selected step: {next_step.title}",
                    metadata={
                        "revision_id": latest_revision.revision_id,
                        "active_step_id": next_step.step_id,
                    },
                ),
            )

            execution_record = None
            pending_approval = self._resolve_pending_action_if_any(
                action_history=action_history,
                workspace_root=execution_root,
                execution_scope=execution_scope,
                execution_policy=execution_policy,
            )
            if pending_approval is not None:
                if pending_approval.gate.status == "pending":
                    autopilot_status = "paused"
                    autopilot_pause_reason = "approval_required"
                    notes.append("Harness detected a pending approval gate and paused safely.")
                    break
                if pending_approval.gate.status == "rejected":
                    repeated_failure_count += 1
                    risks.append("Operator rejected a high-risk action; replanning required.")
                    self._append_revised_plan(
                        plan_revisions=plan_revisions,
                        base_revision=latest_revision,
                        trigger="approval_rejected",
                        summary="Planner revised the mission after a rejected high-risk action.",
                        extra_steps=[
                            PlannedStep(
                                step_id=f"step_{uuid.uuid4().hex[:8]}",
                                title="Inspect environment and dependency assumptions",
                                description="Broaden the search after the rejected action.",
                                kind="derived",
                            )
                        ],
                    )
                    action_history[-1] = asdict(pending_approval)
                    continue
                execution_record = pending_approval
                action_history[-1] = asdict(execution_record)

            if execution_record is None:
                proposal = build_action_proposal(
                    step=next_step,
                    objective=objective,
                    workspace_root=repo_path,
                    verification_commands=verify_commands,
                    runtime_id=runtime_id,
                    execution_scope=execution_scope,
                    execution_policy=execution_policy,
                )
                self.session_store.append_timeline(
                    session_path,
                    TimelineEvent(
                        kind="action.proposed",
                        message=proposal.title,
                        metadata=asdict(proposal),
                    ),
                )

                execution_record = execute_action(
                    proposal,
                    repo_path,
                    execution_scope=execution_scope,
                    execution_policy=execution_policy,
                )
                action_history.append(asdict(execution_record))

            if execution_record.gate.status == "pending":
                autopilot_status = "paused"
                autopilot_pause_reason = "approval_required"
                risks.append("A high-risk action was proposed and is waiting for operator approval.")
                next_step.notes.append("Pending approval before execution.")
                latest_revision.active_step_id = next_step.step_id
                break

            delegated_payload = execution_record.result.payload.get("delegatedSession", {})
            if execution_record.proposal.kind == "runtime_delegate" and delegated_payload:
                next_step.status = "in_progress"
                latest_revision.active_step_id = next_step.step_id
                delegated_runtime_sessions = [
                    item
                    for item in delegated_runtime_sessions
                    if item.get("delegated_id") != delegated_payload.get("delegated_id")
                ]
                delegated_runtime_sessions.append(delegated_payload)
                notes.append("Delegated runtime lane launched; Fluxio will resume once it completes.")
                autopilot_status = "paused"
                autopilot_pause_reason = "delegated_runtime_running"
                break

            if execution_record.result.ok:
                next_step.status = "completed"
                completed_steps.append(next_step.title)
                changed_files = list(
                    dict.fromkeys(changed_files + execution_record.result.changed_files)
                )
                repeated_failure_count = 0
                skill_record = self.skill_library.record_usage(
                    skill_id=selected_skills[0]["skillId"] if selected_skills else "curated:repo_scan",
                    label=selected_skills[0]["label"] if selected_skills else "Repo Scan",
                    step_id=next_step.step_id,
                    mission_id=execution_context.mission_id,
                    helped=True,
                    source_kind=selected_skills[0]["sourceKind"] if selected_skills else "curated",
                )
                skill_usage.append(asdict(skill_record))
            else:
                next_step.attempts += 1
                next_step.status = "blocked"
                repeated_failure_count += 1
                risks.append(
                    execution_record.result.error
                    or execution_record.result.stderr
                    or "Action execution failed."
                )

            last_verification_results = self.verification_runner.run(
                verify_commands, execution_root
            )
            verification_failures = [
                item.command
                for item in last_verification_results
                if item.return_code != 0 or item.status != "executed"
            ]
            if verification_failures:
                improvement_queue.extend(
                    [
                        ImprovementQueueItem(
                            item_id=f"improve_{uuid.uuid4().hex[:8]}",
                            title=f"Verification follow-up: {command}",
                            reason="Verification failed and needs explicit follow-up.",
                            priority="high",
                            in_mission_scope=True,
                            category="verification",
                            source_step_id=next_step.step_id,
                        )
                        for command in verification_failures
                    ]
                )
                if guardrails.get("pause_on_verification_failure", True):
                    autopilot_status = "paused"
                    autopilot_pause_reason = "verification_failed"

            if repeated_failure_count >= execution_context.broadening_threshold:
                derived = DerivedTask(
                    task_id=f"derived_{uuid.uuid4().hex[:8]}",
                    title="Inspect dependencies, environment, and configuration",
                    reason="Repeated failures triggered Hermes-style problem broadening.",
                    source_step_id=next_step.step_id,
                    status="pending",
                    priority="high",
                    attempt_count=repeated_failure_count,
                )
                if not any(item.title == derived.title for item in derived_tasks):
                    derived_tasks.append(derived)
                self._append_revised_plan(
                    plan_revisions=plan_revisions,
                    base_revision=latest_revision,
                    trigger="repeated_failure_broadening",
                    summary="Planner broadened the search after repeated failures.",
                    extra_steps=[
                        PlannedStep(
                            step_id=f"step_{uuid.uuid4().hex[:8]}",
                            title=derived.title,
                            description=derived.reason,
                            kind="derived",
                        )
                    ],
                )
            else:
                self._append_revised_plan(
                    plan_revisions=plan_revisions,
                    base_revision=latest_revision,
                    trigger="action_completed" if execution_record.result.ok else "action_failed",
                    summary=(
                        "Planner revised the next steps after a successful action."
                        if execution_record.result.ok
                        else "Planner revised the next steps after an action failure."
                    ),
                    extra_steps=[],
                )

            promotion_candidates = self.skill_library.suggest_promotions(
                mission_id=execution_context.mission_id,
                objective=objective,
                selected_skills=selected_skills,
                verification_failures=verification_failures,
            )
            promoted = self.skill_library.promote_candidates(promotion_candidates)
            for item in promoted:
                learned_skill_events.append(
                    {
                        "kind": "skill.promoted",
                        "label": item.label,
                        "confidence": item.confidence,
                        "timestamp": utc_now_iso(),
                    }
                )

            if checkpoint_every and iteration % checkpoint_every == 0:
                checkpoint_store.save(
                    session_id=session_id,
                    iteration=iteration,
                    run_state=self._build_run_state(
                        objective=objective,
                        plan_revisions=plan_revisions,
                        completed_steps=completed_steps,
                        decisions=decisions,
                        changed_files=changed_files,
                        risks=risks,
                        verification_results=last_verification_results,
                        selected_skills=selected_skills,
                        notes=notes,
                    ),
                    context={
                        "used_tokens": 0,
                        "usage_ratio": 0.0,
                        "status": "nominal",
                    },
                    doc_sources=docs,
                )

            if autopilot_pause_reason:
                break

        final_steps = [
            step.title for step in plan_revisions[-1].steps if step.status != "completed"
        ]
        if not final_steps and not autopilot_pause_reason:
            autopilot_status = "completed"

        persisted_state = {
            "objective": objective,
            "doc_evidence": [asdict(item) for item in docs_evidence],
            "plan_steps": [item.title for item in plan_revisions[-1].steps],
            "acceptance_checks": plan_bundle.acceptance_checks,
            "completed_steps": completed_steps,
            "decisions": decisions,
            "changed_files": changed_files,
            "risks": risks,
            "next_actions": final_steps[:6],
            "verification_results": [asdict(item) for item in last_verification_results],
            "verification_failures": verification_failures,
            "retrieved_skills": [item["label"] for item in selected_skills],
            "notes": notes,
            "autopilot_status": autopilot_status,
            "autopilot_pause_reason": autopilot_pause_reason,
            "session_lineage": lineage,
            "profile": profile_name,
            "profile_defaults": profile_defaults,
            "execution_scope": asdict(execution_scope),
            "execution_policy": asdict(execution_policy),
            "route_configs": [asdict(item) for item in route_configs],
            "routing_decisions": routing_decisions,
            "plan_revisions": [asdict(item) for item in plan_revisions],
            "current_plan_revision_id": plan_revisions[-1].revision_id,
            "derived_tasks": [asdict(item) for item in derived_tasks],
            "improvement_queue": [asdict(item) for item in improvement_queue],
            "skill_usage": skill_usage,
            "learned_skill_events": learned_skill_events,
            "action_history": action_history,
            "delegated_runtime_sessions": delegated_runtime_sessions,
            "repeated_failure_count": repeated_failure_count,
            "planner_loop_status": "paused" if autopilot_pause_reason else autopilot_status,
            "harness_id": self.harness_id,
            "runtime_id": runtime_id,
            "mission_id": execution_context.mission_id,
            "compatibility_harness_id": self.compatibility_harness.harness_id,
            "project_profile": project_profile,
            "context": {
                "used_tokens": 0,
                "usage_ratio": 0.0,
                "status": "nominal",
            },
            "memory_item_ids": [],
            "handoff_packets": [],
            "handoff_budget_used": 0,
            "parallel_agents": 1,
            "merge_policy": (
                "risk_averse"
                if profile_defaults["approval_strictness"] == "high"
                else "best_score"
            ),
            "vibe_next_steps": [item.title for item in improvement_queue[:3]],
            "pending_mutating_actions": sum(
                1
                for item in action_history
                if item.get("proposal", {}).get("mutability_class") == "write"
                and item.get("gate", {}).get("status") == "pending"
            ),
            "replay_action_cursor": action_history[-1]["proposal"].get("replay_cursor", "")
            if action_history
            else "",
            "tutorial_context": {
                "profile": profile_name,
                "explanationDepth": execution_policy.explanation_depth,
                "scope": execution_scope.strategy,
            },
        }
        self.session_store.save_state(session_path, persisted_state)

        write_run_report(
            session_path=session_path,
            objective=objective,
            session_lineage=lineage,
            handoff_paths=[],
            state=persisted_state,
        )

        return {
            "status": "ok",
            "session_path": str(session_path),
            "autopilot_status": autopilot_status,
            "autopilot_pause_reason": autopilot_pause_reason,
            "remaining_steps": final_steps,
            "verification_failures": verification_failures,
            "changed_files": changed_files,
            "route_configs": [asdict(item) for item in route_configs],
            "routing_decisions": routing_decisions,
            "execution_scope": asdict(execution_scope),
            "execution_policy": asdict(execution_policy),
            "plan_revisions": [asdict(item) for item in plan_revisions],
            "current_plan_revision_id": plan_revisions[-1].revision_id,
            "derived_tasks": [asdict(item) for item in derived_tasks],
            "improvement_queue": [asdict(item) for item in improvement_queue],
            "skill_usage": skill_usage,
            "learned_skill_events": learned_skill_events,
            "action_history": action_history,
            "delegated_runtime_sessions": delegated_runtime_sessions,
            "harness_id": self.harness_id,
            "profile_defaults": profile_defaults,
            "repeated_failure_count": repeated_failure_count,
        }

    @staticmethod
    def _build_run_state(
        objective: str,
        plan_revisions: list[PlanRevision],
        completed_steps: list[str],
        decisions: list[str],
        changed_files: list[str],
        risks: list[str],
        verification_results: list[VerificationResult],
        selected_skills: list[dict],
        notes: list[str],
    ) -> RunState:
        return RunState(
            objective=objective,
            plan_steps=[item.title for item in plan_revisions[-1].steps],
            acceptance_checks=[],
            completed_steps=completed_steps,
            decisions=decisions,
            changed_files=changed_files,
            risks=risks,
            next_actions=[
                item.title for item in plan_revisions[-1].steps if item.status != "completed"
            ],
            verification_results=verification_results,
            retrieved_skills=[item["label"] for item in selected_skills],
            notes=notes,
        )

    @staticmethod
    def _reconcile_delegated_sessions(
        delegated_runtime_sessions: list[dict],
        plan_revisions: list[PlanRevision],
        runtime_supervisor: DelegatedRuntimeSupervisor,
        notes: list[str],
        risks: list[str],
    ) -> tuple[list[dict], str, str]:
        if not delegated_runtime_sessions:
            return delegated_runtime_sessions, "", ""

        refreshed: list[dict] = []
        active_status = ""
        replan_trigger = ""
        latest_revision = plan_revisions[-1]
        step_lookup = {step.step_id: step for revision in plan_revisions for step in revision.steps}
        for item in delegated_runtime_sessions:
            session = runtime_supervisor.refresh_session(item)
            step = step_lookup.get(session.source_step_id)
            if session.status in {"running", "launching"}:
                active_status = "running"
                if step is not None:
                    step.status = "in_progress"
                    latest_revision.active_step_id = step.step_id
            elif session.status == "waiting_for_approval":
                active_status = "waiting_for_approval"
                if step is not None:
                    step.status = "in_progress"
                    latest_revision.active_step_id = step.step_id
                prompt = session.pending_approval.get("prompt", "Delegated runtime requested approval.")
                if prompt not in notes:
                    notes.append(f"Delegated approval required: {prompt}")
            elif not session.acknowledged and step is not None:
                if session.status == "completed":
                    step.status = "completed"
                    notes.append(
                        f"Delegated runtime {session.runtime_id} completed for step {step.title}: "
                        f"{session.last_event or session.detail}"
                    )
                else:
                    step.status = "blocked"
                    step.attempts += 1
                    if any(
                        entry.get("status") == "rejected"
                        for entry in session.approval_history
                        if isinstance(entry, dict)
                    ):
                        replan_trigger = "approval_rejected"
                    risks.append(
                        f"Delegated runtime {session.runtime_id} stopped with status {session.status}: "
                        f"{session.last_event or session.detail}"
                    )
                session.acknowledged = True
            refreshed.append(asdict(session))
        return refreshed, active_status, replan_trigger

    @staticmethod
    def _load_plan_revisions(
        resumed_state: dict | None,
        plan_bundle: PlanBundle,
    ) -> list[PlanRevision]:
        if resumed_state and resumed_state.get("plan_revisions"):
            revisions: list[PlanRevision] = []
            for revision in resumed_state.get("plan_revisions", []):
                steps = [PlannedStep(**item) for item in revision.get("steps", [])]
                revisions.append(
                    PlanRevision(
                        revision_id=revision["revision_id"],
                        trigger=revision.get("trigger", "resume"),
                        summary=revision.get("summary", ""),
                        steps=steps,
                        active_step_id=revision.get("active_step_id"),
                        created_at=revision.get("created_at", utc_now_iso()),
                    )
                )
            return revisions

        return [
            PlanRevision(
                revision_id=f"rev_{uuid.uuid4().hex[:8]}",
                trigger="mission_start",
                summary="Initial Fluxio plan built from docs-first planning.",
                steps=[
                    PlannedStep(
                        step_id=f"step_{uuid.uuid4().hex[:8]}",
                        title=step,
                        description=step,
                        kind="primary",
                    )
                    for step in plan_bundle.plan_steps
                ],
            )
        ]

    @staticmethod
    def _load_derived_tasks(resumed_state: dict | None) -> list[DerivedTask]:
        if not resumed_state:
            return []
        return [DerivedTask(**item) for item in resumed_state.get("derived_tasks", [])]

    @staticmethod
    def _load_improvement_queue(
        resumed_state: dict | None,
    ) -> list[ImprovementQueueItem]:
        if not resumed_state:
            return []
        return [
            ImprovementQueueItem(**item)
            for item in resumed_state.get("improvement_queue", [])
        ]

    @staticmethod
    def _load_action_history(resumed_state: dict | None) -> list[dict]:
        if not resumed_state:
            return []
        return list(resumed_state.get("action_history", []))

    @staticmethod
    def _load_routing_decisions(resumed_state: dict | None) -> list[dict]:
        if not resumed_state:
            return []
        return list(resumed_state.get("routing_decisions", []))

    @staticmethod
    def _load_execution_scope(resumed_state: dict | None) -> ExecutionScope | None:
        if not resumed_state or not resumed_state.get("execution_scope"):
            return None
        return ExecutionScope(**resumed_state["execution_scope"])

    @staticmethod
    def _load_execution_policy(resumed_state: dict | None) -> ExecutionPolicy | None:
        if not resumed_state or not resumed_state.get("execution_policy"):
            return None
        return ExecutionPolicy(**resumed_state["execution_policy"])

    @staticmethod
    def _load_route_configs(
        resumed_state: dict | None,
    ) -> list[ModelRouteConfig]:
        if not resumed_state:
            return []
        return [
            ModelRouteConfig(**item)
            for item in resumed_state.get("route_configs", [])
            if isinstance(item, dict) and item.get("role")
        ]

    @staticmethod
    def _next_pending_step(revision: PlanRevision) -> PlannedStep | None:
        for step in revision.steps:
            if step.status == "pending":
                revision.active_step_id = step.step_id
                return step
        for step in revision.steps:
            if step.status != "completed":
                revision.active_step_id = step.step_id
                return step
        revision.active_step_id = None
        return None

    @staticmethod
    def _append_revised_plan(
        plan_revisions: list[PlanRevision],
        base_revision: PlanRevision,
        trigger: str,
        summary: str,
        extra_steps: list[PlannedStep],
    ) -> None:
        pending_existing = [
            PlannedStep(
                step_id=item.step_id,
                title=item.title,
                description=item.description,
                status=item.status,
                kind=item.kind,
                attempts=item.attempts,
                notes=list(item.notes),
            )
            for item in base_revision.steps
            if item.status != "completed"
        ]
        merged_steps = pending_existing + extra_steps
        if not merged_steps:
            return
        plan_revisions.append(
            PlanRevision(
                revision_id=f"rev_{uuid.uuid4().hex[:8]}",
                trigger=trigger,
                summary=summary,
                steps=merged_steps,
                active_step_id=merged_steps[0].step_id,
            )
        )

    @staticmethod
    def _resolve_pending_action_if_any(
        action_history: list[dict],
        workspace_root: Path,
        execution_scope: ExecutionScope,
        execution_policy: ExecutionPolicy,
    ) -> ActionExecutionRecord | None:
        if not action_history:
            return None
        last = action_history[-1]
        gate = last.get("gate", {})
        proposal = last.get("proposal", {})
        result = last.get("result", {})
        if gate.get("status") not in {"pending", "approved", "rejected"}:
            return None

        record = ActionExecutionRecord(
            action_id=last["action_id"],
            proposal=ActionProposal(**proposal),
        )
        record.gate.required = gate.get("required", False)
        record.gate.status = gate.get("status", "not_required")
        record.gate.risk_level = gate.get("risk_level", "low")
        record.gate.reason = gate.get("reason", "")
        record.gate.approved_by = gate.get("approved_by", "")
        record.gate.resolved_at = gate.get("resolved_at")
        record.result.ok = result.get("ok", False)
        record.result.exit_code = result.get("exit_code", 0)
        record.result.stdout = result.get("stdout", "")
        record.result.stderr = result.get("stderr", "")
        record.result.duration_ms = result.get("duration_ms", 0)
        record.result.error = result.get("error", "")
        record.result.changed_files = result.get("changed_files", [])
        record.result.payload = result.get("payload", {})
        record.attempts = int(last.get("attempts", 0))
        record.event_id = last.get("event_id", "")
        record.acked = bool(last.get("acked", False))
        record.replayed = bool(last.get("replayed", False))
        record.executed_at = last.get("executed_at")

        if record.gate.status == "approved" and record.result.ok:
            return None
        if record.gate.status == "approved" and not record.result.ok:
            rerun = execute_action(
                record.proposal,
                workspace_root,
                execution_scope=execution_scope,
                execution_policy=execution_policy,
                approval_override=True,
            )
            rerun.gate.approved_by = "operator"
            rerun.gate.resolved_at = utc_now_iso()
            return rerun
        return record
