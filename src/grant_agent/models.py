from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PersonaProfile:
    name: str
    tone: str
    risk_tolerance: str
    creativity_level: str
    coding_style: str
    verbosity: str


@dataclass
class PromptStack:
    base_constitution: str
    project_profile: str
    persona: PersonaProfile
    task_brief: str
    step_policy: str


@dataclass
class VerificationResult:
    command: str
    return_code: int
    stdout: str
    stderr: str
    duration_ms: int
    status: str = "executed"
    risk_level: str = "low"


@dataclass
class TimelineEvent:
    kind: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_now_iso)


@dataclass
class RunState:
    objective: str
    plan_steps: list[str]
    acceptance_checks: list[str]
    completed_steps: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    verification_results: list[VerificationResult] = field(default_factory=list)
    retrieved_skills: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class HandoffPacket:
    schema_version: str
    generated_at: str
    reason: str
    session_id: str
    parent_session_id: str | None
    objective: str
    prompt_stack: dict[str, Any]
    progress: dict[str, Any]
    changed_files: list[str]
    decisions: list[str]
    risks: list[str]
    acceptance_checks: list[str]
    verification: list[dict[str, Any]]
    next_actions: list[str]
    resume_instructions: list[str]


@dataclass
class RuntimeCapability:
    key: str
    label: str
    available: bool
    detail: str = ""


@dataclass
class RuntimeInstallStatus:
    runtime_id: str
    label: str
    detected: bool
    command: str | None = None
    version: str | None = None
    latest_version: str | None = None
    update_available: bool = False
    update_command: str | None = None
    update_source_url: str | None = None
    install_hint: str | None = None
    doctor_summary: str = ""
    issues: list[str] = field(default_factory=list)
    capabilities: list[RuntimeCapability] = field(default_factory=list)


@dataclass
class MissionRunBudget:
    mode: str
    max_runtime_seconds: int
    focus_window_hours: int = 12
    run_until_behavior: str = "pause_on_failure"
    deadline_at: str | None = None


@dataclass
class MissionVerificationPolicy:
    commands: list[str] = field(default_factory=list)
    pause_on_failure: bool = True


@dataclass
class MissionProof:
    summary: str = ""
    changed_files: list[str] = field(default_factory=list)
    passed_checks: list[str] = field(default_factory=list)
    failed_checks: list[str] = field(default_factory=list)
    pending_approvals: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)


@dataclass
class MissionStateSnapshot:
    status: str = "draft"
    latest_session_id: str | None = None
    last_runtime_event: str | None = None
    last_error: str | None = None
    current_cycle_phase: str = "plan"
    cycle_count: int = 0
    last_verification_result: str = ""
    last_replan_reason: str = ""
    queue_position: int = 0
    blocking_mission_id: str | None = None
    queue_reason: str = ""
    remaining_steps: list[str] = field(default_factory=list)
    verification_failures: list[str] = field(default_factory=list)
    active_step_id: str | None = None
    repeated_failure_count: int = 0
    planner_loop_status: str = "idle"
    stop_reason: str | None = None
    last_plan_summary: str = ""
    execution_scope: dict[str, Any] = field(default_factory=dict)
    pending_mutating_actions: int = 0
    delegated_runtime_sessions: list[dict[str, Any]] = field(default_factory=list)
    replay_action_cursor: str = ""
    tutorial_context: dict[str, Any] = field(default_factory=dict)
    continuity_state: str = "fresh_only"
    continuity_detail: str = ""
    last_verification_summary: str = ""
    last_replan_trigger: str = ""
    pending_approval_payload: dict[str, Any] = field(default_factory=dict)
    approval_history: list[dict[str, Any]] = field(default_factory=list)
    elapsed_runtime_seconds: int = 0
    remaining_runtime_seconds: int = 0
    time_budget_status: str = "pending"
    last_budget_pause_reason: str = ""
    current_runtime_lane: str = ""
    context_used_tokens: int = 0
    context_usage_ratio: float = 0.0
    context_status: str = "ok"
    handoff_count: int = 0
    last_handoff_reason: str = ""
    route_change_count: int = 0
    parallel_agents: int = 1
    merge_policy: str = "best_score"
    runtime_autonomy: dict[str, Any] = field(default_factory=dict)
    blocker_classification: dict[str, Any] = field(default_factory=dict)
    blocker_history: list[dict[str, Any]] = field(default_factory=list)
    provider_runtime_truth: dict[str, Any] = field(default_factory=dict)
    code_execution: dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalEscalation:
    channel: str
    enabled: bool
    destination: str
    triggers: list[str] = field(default_factory=list)
    pending_count: int = 0
    delivery_ready: bool = False
    preview_message: str = ""
    last_sent_at: str | None = None
    last_error: str | None = None


@dataclass
class SkillSource:
    kind: str
    label: str = ""
    path: str = ""
    runtime_id: str = ""
    trusted: bool = True


@dataclass
class SkillPack:
    pack_id: str
    label: str
    description: str
    source: SkillSource
    recommended: bool = False
    installed: bool = False
    skills: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    audience: str = "all"
    action_kinds: list[str] = field(default_factory=list)
    profile_suitability: list[str] = field(default_factory=list)
    guidance_only: bool = False
    execution_capable: bool = False


@dataclass
class LearnedSkill:
    skill_id: str
    label: str
    description: str
    prompt_hint: str
    source: SkillSource
    confidence: float = 0.0
    status: str = "learned"
    disabled: bool = False
    usage_count: int = 0
    tags: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    audit: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    last_used_at: str | None = None


@dataclass
class SkillPromotionCandidate:
    candidate_id: str
    label: str
    reason: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    status: str = "candidate"
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class SkillUsageRecord:
    skill_id: str
    label: str
    step_id: str
    mission_id: str
    helped: bool
    source_kind: str
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class ModelRouteConfig:
    role: str
    provider: str
    model: str
    effort: str = "medium"
    budget_class: str = "balanced"
    fallback_policy: str = "same_provider"
    explanation: str = ""


@dataclass
class ExecutionScope:
    requested: str = "isolated"
    strategy: str = "direct"
    execution_root: str = ""
    workspace_root: str = ""
    execution_target: str = "unresolved"
    storage_mode: str = "unknown"
    host_locality: str = "unknown"
    execution_target_detail: str = ""
    branch_name: str = ""
    worktree_path: str = ""
    isolated: bool = False
    status: str = "pending"
    detail: str = ""


@dataclass
class ExecutionPolicy:
    profile_name: str
    approval_mode: str = "tiered"
    explanation_depth: str = "medium"
    delegation_aggressiveness: str = "balanced"
    auto_allowed_kinds: list[str] = field(default_factory=list)
    approval_required_kinds: list[str] = field(default_factory=list)
    destructive_requires_approval: bool = True


@dataclass
class MissionCodeExecutionConfig:
    enabled: bool = False
    memory_limit: str = "4g"
    container_id: str = ""
    required: bool = False
    file_ids: list[str] = field(default_factory=list)
    last_started_at: str = ""
    last_result: str = ""
    last_error: str = ""
    artifacts: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DelegatedRuntimeEvent:
    event_id: str
    delegated_id: str
    runtime_id: str
    kind: str
    message: str
    status: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class DelegatedApprovalRequest:
    request_id: str
    delegated_id: str
    runtime_id: str
    prompt: str
    risk_level: str = "medium"
    status: str = "pending"
    created_at: str = field(default_factory=utc_now_iso)
    resolved_at: str | None = None
    resolved_by: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DelegatedSessionSnapshot:
    delegated_id: str
    runtime_id: str
    status: str
    detail: str = ""
    last_event: str = ""
    last_event_kind: str = ""
    latest_events: list[DelegatedRuntimeEvent] = field(default_factory=list)
    pending_approval: DelegatedApprovalRequest | None = None
    event_cursor: int = 0
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    workspace_root: str = ""
    execution_root: str = ""
    execution_target: str = "unresolved"
    storage_mode: str = "unknown"
    host_locality: str = "unknown"
    execution_target_detail: str = ""
    session_path: str = ""
    log_path: str = ""
    source_step_id: str = ""
    pid: int = 0
    supervisor_pid: int = 0
    exit_code: int | None = None
    heartbeat_at: str = ""
    heartbeat_status: str = "unknown"
    heartbeat_age_seconds: int | None = None
    heartbeat_interval_seconds: int = 10
    target_phase: str = ""
    target_role: str = ""
    target_provider: str = ""
    target_model: str = ""
    target_effort: str = ""
    target_budget_class: str = ""
    handoff_count: int = 0
    handoff_reason: str = ""
    source_delegated_id: str = ""


@dataclass
class DelegatedRuntimeSession:
    delegated_id: str
    runtime_id: str
    launch_command: str
    status: str = "queued"
    detail: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    last_event: str = ""
    session_path: str = ""
    workspace_root: str = ""
    execution_root: str = ""
    execution_target: str = "unresolved"
    storage_mode: str = "unknown"
    host_locality: str = "unknown"
    execution_target_detail: str = ""
    log_path: str = ""
    events_path: str = ""
    decision_path: str = ""
    source_step_id: str = ""
    pid: int = 0
    supervisor_pid: int = 0
    exit_code: int | None = None
    acknowledged: bool = False
    last_event_kind: str = ""
    latest_events: list[dict[str, Any]] = field(default_factory=list)
    pending_approval: dict[str, Any] = field(default_factory=dict)
    approval_history: list[dict[str, Any]] = field(default_factory=list)
    event_cursor: int = 0
    heartbeat_at: str = ""
    heartbeat_status: str = "unknown"
    heartbeat_age_seconds: int | None = None
    heartbeat_interval_seconds: int = 10
    target_phase: str = ""
    target_role: str = ""
    target_provider: str = ""
    target_model: str = ""
    target_effort: str = ""
    target_budget_class: str = ""
    handoff_count: int = 0
    handoff_reason: str = ""
    source_delegated_id: str = ""


@dataclass
class TutorialStep:
    step_id: str
    title: str
    description: str
    status: str = "pending"
    cta_label: str = ""
    panel: str = ""


@dataclass
class GuidanceCard:
    card_id: str
    title: str
    body: str
    kind: str
    status: str = "active"
    cta_label: str = ""
    panel: str = ""


@dataclass
class OnboardingProgress:
    selected_profile: str = ""
    completed_steps: list[str] = field(default_factory=list)
    dismissed_cards: list[str] = field(default_factory=list)
    current_step_id: str = ""
    is_complete: bool = False


@dataclass
class GuidanceTrigger:
    trigger_id: str
    kind: str
    reason: str
    mission_id: str = ""
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class RoutingDecision:
    role: str
    provider: str
    model: str
    reason: str
    budget_class: str
    timestamp: str = field(default_factory=utc_now_iso)


@dataclass
class AppTaskDescriptor:
    task_id: str
    label: str
    description: str
    requires_approval: bool = False
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class AppContextSurface:
    surface_id: str
    label: str
    description: str
    access: str = "read"
    data_shape: dict[str, Any] = field(default_factory=dict)


@dataclass
class AppActionHook:
    hook_id: str
    label: str
    description: str
    mutability: str = "read"
    risk_level: str = "low"
    requires_approval: bool = False


@dataclass
class CapabilityGrant:
    grant_id: str
    capability_key: str
    status: str
    scope: str = "app"
    reason: str = ""


@dataclass
class AppCapabilityManifest:
    manifest_id: str
    schema_version: str
    app_id: str
    name: str
    description: str
    bridge: dict[str, Any] = field(default_factory=dict)
    auth: dict[str, Any] = field(default_factory=dict)
    permissions: list[str] = field(default_factory=list)
    tasks: list[AppTaskDescriptor] = field(default_factory=list)
    context_surfaces: list[AppContextSurface] = field(default_factory=list)
    action_hooks: list[AppActionHook] = field(default_factory=list)
    ui_hints: dict[str, Any] = field(default_factory=dict)


@dataclass
class AppBridgeHandshake:
    app_id: str
    bridge_version: str
    session_id: str
    transport: str
    capabilities: list[str] = field(default_factory=list)
    auth_mode: str = "local_token"
    requires_user_present: bool = False


@dataclass
class ConnectedAppSession:
    session_id: str
    app_id: str
    app_name: str
    status: str
    bridge_health: str
    manifest_id: str = ""
    granted_capabilities: list[CapabilityGrant] = field(default_factory=list)
    active_tasks: list[str] = field(default_factory=list)
    last_seen_at: str = field(default_factory=utc_now_iso)
    notes: list[str] = field(default_factory=list)
    handshake_status: str = ""
    bridge_transport: str = ""
    bridge_endpoint: str = ""
    source_kind: str = "connected_app"
    app_root: str = ""
    context_preview: list[dict[str, Any]] = field(default_factory=list)
    task_history: list[dict[str, Any]] = field(default_factory=list)
    latest_task_result: dict[str, Any] = field(default_factory=dict)
    approval_callback: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlannedStep:
    step_id: str
    title: str
    description: str = ""
    status: str = "pending"
    kind: str = "primary"
    attempts: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass
class PlanRevision:
    revision_id: str
    trigger: str
    summary: str
    steps: list[PlannedStep] = field(default_factory=list)
    active_step_id: str | None = None
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class DerivedTask:
    task_id: str
    title: str
    reason: str
    source_step_id: str = ""
    status: str = "pending"
    priority: str = "normal"
    attempt_count: int = 0


@dataclass
class ImprovementQueueItem:
    item_id: str
    title: str
    reason: str
    priority: str = "medium"
    in_mission_scope: bool = False
    status: str = "queued"
    category: str = "product"
    source_step_id: str = ""
    notes: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class ActionApprovalGate:
    required: bool
    status: str = "not_required"
    risk_level: str = "low"
    reason: str = ""
    approved_by: str = ""
    resolved_at: str | None = None


@dataclass
class ActionProposal:
    action_id: str
    kind: str
    title: str
    command: str = ""
    query: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "low"
    requires_approval: bool = False
    source_step_id: str = ""
    reason: str = ""
    status: str = "proposed"
    event_id: str = ""
    target_path: str = ""
    target_scope: str = "workspace"
    mutability_class: str = "read"
    policy_decision: str = "auto_run"
    branch_name: str = ""
    worktree_path: str = ""
    delegation_metadata: dict[str, Any] = field(default_factory=dict)
    replay_cursor: str = ""


@dataclass
class ActionResultEnvelope:
    ok: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    error: str = ""
    changed_files: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    target_path: str = ""
    result_summary: str = ""


@dataclass
class ActionExecutionRecord:
    action_id: str
    proposal: ActionProposal
    gate: ActionApprovalGate = field(
        default_factory=lambda: ActionApprovalGate(required=False)
    )
    result: ActionResultEnvelope = field(
        default_factory=lambda: ActionResultEnvelope(ok=False)
    )
    attempts: int = 0
    event_id: str = ""
    acked: bool = False
    replayed: bool = False
    executed_at: str | None = None
    retry_outcome: str = ""


@dataclass
class HarnessExecutionContext:
    mission_id: str
    workspace_root: str
    runtime_id: str
    profile_name: str
    execution_scope: ExecutionScope = field(default_factory=ExecutionScope)
    execution_policy: ExecutionPolicy = field(
        default_factory=lambda: ExecutionPolicy(profile_name="builder")
    )
    code_execution: MissionCodeExecutionConfig = field(
        default_factory=MissionCodeExecutionConfig
    )
    route_configs: list[ModelRouteConfig] = field(default_factory=list)
    broadening_threshold: int = 2
    innovation_scope: str = "bounded"
    harness_id: str = "fluxio_hybrid"


@dataclass
class HarnessStopReason:
    kind: str
    detail: str = ""


@dataclass
class HarnessStepResult:
    status: str
    plan_revision: PlanRevision | None = None
    action_record: ActionExecutionRecord | None = None
    verification_results: list[VerificationResult] = field(default_factory=list)
    derived_tasks: list[DerivedTask] = field(default_factory=list)
    improvement_items: list[ImprovementQueueItem] = field(default_factory=list)
    routing_decisions: list[RoutingDecision] = field(default_factory=list)
    stop_reason: HarnessStopReason | None = None


@dataclass
class MissionEvent:
    mission_id: str
    kind: str
    message: str
    timestamp: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Mission:
    mission_id: str
    workspace_id: str
    runtime_id: str
    objective: str
    success_checks: list[str]
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    title: str = ""
    run_budget: MissionRunBudget = field(
        default_factory=lambda: MissionRunBudget(mode="Autopilot", max_runtime_seconds=43200)
    )
    verification_policy: MissionVerificationPolicy = field(
        default_factory=MissionVerificationPolicy
    )
    escalation_policy: ApprovalEscalation = field(
        default_factory=lambda: ApprovalEscalation(
            channel="telegram",
            enabled=False,
            destination="",
            triggers=[],
        )
    )
    harness_id: str = "fluxio_hybrid"
    selected_profile: str = "builder"
    execution_scope: ExecutionScope = field(default_factory=ExecutionScope)
    execution_policy: ExecutionPolicy = field(
        default_factory=lambda: ExecutionPolicy(profile_name="builder")
    )
    code_execution: MissionCodeExecutionConfig = field(
        default_factory=MissionCodeExecutionConfig
    )
    route_configs: list[ModelRouteConfig] = field(default_factory=list)
    routing_decisions: list[RoutingDecision] = field(default_factory=list)
    effective_route_contract: dict[str, Any] = field(default_factory=dict)
    current_plan_revision_id: str | None = None
    plan_revisions: list[PlanRevision] = field(default_factory=list)
    derived_tasks: list[DerivedTask] = field(default_factory=list)
    improvement_queue: list[ImprovementQueueItem] = field(default_factory=list)
    skill_usage: list[SkillUsageRecord] = field(default_factory=list)
    learned_skill_events: list[dict[str, Any]] = field(default_factory=list)
    action_history: list[ActionExecutionRecord] = field(default_factory=list)
    delegated_runtime_sessions: list[DelegatedRuntimeSession] = field(default_factory=list)
    tutorial_context: dict[str, Any] = field(default_factory=dict)
    planner_loop_status: str = "idle"
    state: MissionStateSnapshot = field(default_factory=MissionStateSnapshot)
    proof: MissionProof = field(default_factory=MissionProof)


@dataclass
class WorkspaceProfile:
    workspace_id: str
    name: str
    root_path: str
    default_runtime: str
    workspace_type: str
    user_profile: str = "builder"
    preferred_harness: str = "fluxio_hybrid"
    routing_strategy: str = "profile_default"
    route_overrides: list[dict[str, Any]] = field(default_factory=list)
    auto_optimize_routing: bool = False
    openai_codex_auth_mode: str = "none"
    minimax_auth_mode: str = "none"
    commit_message_style: str = "scoped"
    execution_target_preference: str = "profile_default"
    goals: list[str] = field(default_factory=list)
    enabled: bool = True
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)


@dataclass
class SkillRecommendation:
    recommendation_id: str
    label: str
    reason: str
    runtime_id: str
    workspace_type: str
    enabled_by_default: bool = False


@dataclass
class IntegrationRecommendation:
    recommendation_id: str
    label: str
    reason: str
    command: str
    runtime_id: str
    workspace_type: str
    enabled_by_default: bool = False


def to_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value
