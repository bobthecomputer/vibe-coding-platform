from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .models import (
    ApprovalEscalation,
    DelegatedRuntimeSession,
    ExecutionPolicy,
    ExecutionScope,
    IntegrationRecommendation,
    Mission,
    MissionCodeExecutionConfig,
    MissionEvent,
    MissionProof,
    MissionRunBudget,
    MissionStateSnapshot,
    MissionVerificationPolicy,
    SkillRecommendation,
    WorkspaceProfile,
    utc_now_iso,
)
from .app_capability_standard import build_connected_apps_snapshot
from .execution_truth import derive_execution_target
from .onboarding import (
    build_guidance_snapshot,
    detect_onboarding_status,
    invalidate_onboarding_status_cache,
)
from .profiles import ProfileRegistry
from .runtimes import detect_runtime_statuses, invalidate_runtime_status_cache
from .runtime_supervisor import DelegatedRuntimeSupervisor
from .skill_library import SkillLibrary
from .skills import SkillRegistry
from .verification import detect_default_verification_commands

TERMINAL_MISSION_STATUSES = {"completed", "failed", "stopped"}
MISSION_TITLE_STOPWORDS = {
    "a",
    "an",
    "the",
    "to",
    "for",
    "of",
    "and",
    "or",
    "in",
    "on",
    "with",
    "from",
    "into",
    "my",
    "your",
    "our",
}
MISSION_TITLE_PREFIXES = [
    r"^(please|pls)\s+",
    r"^(can|could|would)\s+you\s+",
    r"^i\s+(need|want)\s+you\s+to\s+",
    r"^help\s+me\s+(?:to\s+)?",
    r"^(let's|lets)\s+",
]
ROUTE_OVERRIDE_ROLES = {"planner", "executor", "verifier"}
OPENAI_CODEX_AUTH_MODES = {"none", "chatgpt", "api"}
MINIMAX_AUTH_MODES = {"none", "minimax-portal-oauth", "minimax-api"}
MINIMAX_SETUP_ACTION_IDS = {
    "minimax-global-oauth",
    "minimax-cn-oauth",
    "minimax-global-api",
    "minimax-cn-api",
}
HARNESS_RECENT_RUN_LIMIT = max(
    int(os.environ.get("FLUXIO_HARNESS_RECENT_RUN_LIMIT", "20")),
    8,
)
RELEASE_READINESS_WEIGHTS = {
    "required": 80,
    "quality": 20,
}
PROVIDER_ENV_HINTS = {
    "openai": "OPENAI_API_KEY",
    "openai-codex": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "minimax": "MINIMAX_API_KEY",
}


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
        if role not in ROUTE_OVERRIDE_ROLES or not provider or not model:
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
        role = item["role"]
        if role in seen_roles:
            continue
        seen_roles.add(role)
        deduped.append(item)
    return deduped


def normalize_minimax_auth_mode(value: object) -> str:
    normalized = str(value or "none").strip().lower()
    if normalized in {"minimax-portal-oauth", "minimax_api", "minimax-api"}:
        return "minimax-portal-oauth" if "portal" in normalized else "minimax-api"
    return normalized if normalized in MINIMAX_AUTH_MODES else "none"


def normalize_openai_codex_auth_mode(value: object) -> str:
    normalized = str(value or "none").strip().lower()
    if normalized in {"chatgpt", "chatgpt-portal", "portal", "oauth", "chatgpt-oauth"}:
        return "chatgpt"
    if normalized in {"api", "api-key", "api_key"}:
        return "api"
    return normalized if normalized in OPENAI_CODEX_AUTH_MODES else "none"


def openai_codex_auth_label(mode: str) -> str:
    if mode == "chatgpt":
        return "ChatGPT portal"
    if mode == "api":
        return "API key"
    return "not configured"


def minimax_auth_label(mode: str) -> str:
    if mode == "minimax-portal-oauth":
        return "OAuth portal"
    if mode == "minimax-api":
        return "API key"
    return "not configured"


def _latest_minimax_setup_action(setup_history: list[dict]) -> dict:
    latest = {}
    for record in setup_history:
        proposal = record.get("proposal", {})
        args = proposal.get("args", {})
        action_id = args.get("workspaceActionId", "")
        if action_id not in MINIMAX_SETUP_ACTION_IDS:
            continue
        if latest and str(record.get("executed_at", "")) < str(latest.get("executed_at", "")):
            continue
        latest = record
    if not latest:
        return {}
    result = latest.get("result", {})
    return {
        "actionId": latest.get("proposal", {}).get("args", {}).get("workspaceActionId", ""),
        "ok": bool(result.get("ok")),
        "resultSummary": result.get("result_summary", "") or result.get("error", ""),
        "executedAt": latest.get("executed_at", ""),
    }


def _minimax_setup_status_for_workspace(
    workspace: WorkspaceProfile | dict,
    setup_history: list[dict],
) -> dict:
    workspace_payload = (
        asdict(workspace) if hasattr(workspace, "__dataclass_fields__") else dict(workspace)
    )
    mode = normalize_minimax_auth_mode(workspace_payload.get("minimax_auth_mode"))
    latest = _latest_minimax_setup_action(setup_history)
    return {
        "authMode": mode,
        "authPath": minimax_auth_label(mode),
        "configured": mode != "none",
        "lastActionResult": latest,
        "lastCheckedAt": latest.get("executedAt", "") or workspace_payload.get("updated_at", ""),
    }


def _openai_codex_setup_status_for_workspace(
    workspace: WorkspaceProfile | dict,
    *,
    auth_presence: dict[str, bool],
) -> dict:
    workspace_payload = (
        asdict(workspace) if hasattr(workspace, "__dataclass_fields__") else dict(workspace)
    )
    mode = normalize_openai_codex_auth_mode(
        workspace_payload.get("openai_codex_auth_mode")
    )
    api_key_present = bool(
        auth_presence.get("openai", False) or auth_presence.get("openai-codex", False)
    )
    effective_mode = mode
    configured = False
    if mode == "chatgpt":
        configured = True
    elif mode == "api":
        configured = api_key_present
    elif api_key_present:
        effective_mode = "api"
        configured = True
    return {
        "authMode": effective_mode,
        "authPath": openai_codex_auth_label(effective_mode),
        "configured": configured,
        "authPresent": configured,
        "lastCheckedAt": workspace_payload.get("updated_at", ""),
    }


def _latest_autotune_event(activity: list[dict]) -> dict:
    for event in activity:
        if event.get("kind") == "mission.autotune.applied":
            return event
    return {}


def _build_efficiency_autotune_snapshot(
    *,
    harness_lab: dict,
    auto_optimize_enabled: bool,
    activity: list[dict],
) -> dict:
    efficiency = harness_lab.get("efficiency", {})
    session_health = harness_lab.get("sessionHealth", {})
    total_runs = int(efficiency.get("totalRuns", 0) or 0)
    completion_rate = int(efficiency.get("completionRate", 0) or 0)
    approval_pause_rate = int(efficiency.get("approvalPauseRate", 0) or 0)
    stale_heartbeat_count = int(session_health.get("staleHeartbeatCount", 0) or 0)
    eligible = total_runs >= 3
    if not auto_optimize_enabled:
        reason = "Auto-optimize routing is off for this workspace."
    elif not eligible:
        reason = "Not enough local data yet (need at least 3 runs)."
    elif stale_heartbeat_count > 0 or completion_rate < 50:
        reason = "Safety route active because heartbeat is stale or completion is below 50%."
    elif approval_pause_rate > 40:
        reason = "Approval pause rate is high, so Fluxio keeps tiered approvals and reduces delegation."
    elif completion_rate >= 70 and stale_heartbeat_count == 0:
        reason = "Runs look stable, so Fluxio can prefer a more efficient executor route."
    else:
        reason = "Routing is left unchanged until a clearer efficiency signal appears."
    latest_event = _latest_autotune_event(activity)
    return {
        "enabled": bool(auto_optimize_enabled),
        "eligible": eligible,
        "reason": reason,
        "lastAppliedPolicy": (latest_event.get("metadata") or {}).get("policy", ""),
        "lastAppliedAt": latest_event.get("created_at", ""),
    }


class ControlRoomStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.control_dir = self.root / ".agent_control"
        self.control_dir.mkdir(parents=True, exist_ok=True)
        self.workspaces_path = self.control_dir / "workspaces.json"
        self.missions_path = self.control_dir / "missions.json"
        self.events_path = self.control_dir / "mission_events.jsonl"
        self.workspace_actions_path = self.control_dir / "workspace_actions.json"

    def _write_json_if_changed(self, path: Path, payload: object) -> None:
        serialized = json.dumps(payload, indent=2)
        if path.exists():
            try:
                if path.read_text(encoding="utf-8") == serialized:
                    return
            except OSError:
                pass
        path.write_text(serialized, encoding="utf-8")

    def _invalidate_snapshot_caches(self) -> None:
        invalidate_onboarding_status_cache(self.root)
        invalidate_runtime_status_cache(self.root)

    def load_workspaces(self) -> list[WorkspaceProfile]:
        payload = self._load_json(self.workspaces_path, [])
        workspaces = [WorkspaceProfile(**item) for item in payload]
        if not workspaces:
            workspaces = [self._default_workspace_profile()]
            self.save_workspaces(workspaces)
        return workspaces

    def save_workspaces(self, workspaces: list[WorkspaceProfile]) -> None:
        self._invalidate_snapshot_caches()
        self._write_json_if_changed(
            self.workspaces_path,
            [asdict(item) for item in workspaces],
        )

    def load_missions(self) -> list[Mission]:
        payload = self._load_json(self.missions_path, [])
        missions: list[Mission] = []
        for item in payload:
            run_budget = MissionRunBudget(**item.get("run_budget", {}))
            verification_policy = MissionVerificationPolicy(
                **item.get("verification_policy", {})
            )
            escalation_policy = ApprovalEscalation(
                **item.get("escalation_policy", {})
            )
            state = MissionStateSnapshot(**item.get("state", {}))
            proof = MissionProof(**item.get("proof", {}))
            execution_scope = ExecutionScope(**item.get("execution_scope", {}))
            execution_policy = ExecutionPolicy(
                **item.get("execution_policy", {"profile_name": item.get("selected_profile", "builder")})
            )
            code_execution = MissionCodeExecutionConfig(
                **item.get("code_execution", {})
            )
            delegated_runtime_sessions = [
                DelegatedRuntimeSession(**row)
                for row in item.get("delegated_runtime_sessions", [])
            ]
            missions.append(
                Mission(
                    mission_id=item["mission_id"],
                    workspace_id=item["workspace_id"],
                    runtime_id=item["runtime_id"],
                    objective=item["objective"],
                    success_checks=item.get("success_checks", []),
                    created_at=item.get("created_at", utc_now_iso()),
                    updated_at=item.get("updated_at", utc_now_iso()),
                    title=item.get("title", ""),
                    run_budget=run_budget,
                    verification_policy=verification_policy,
                    escalation_policy=escalation_policy,
                    harness_id=item.get("harness_id", "fluxio_hybrid"),
                    selected_profile=item.get("selected_profile", "builder"),
                    execution_scope=execution_scope,
                    execution_policy=execution_policy,
                    code_execution=code_execution,
                    route_configs=item.get("route_configs", []),
                    routing_decisions=item.get("routing_decisions", []),
                    effective_route_contract=item.get("effective_route_contract", {}),
                    current_plan_revision_id=item.get("current_plan_revision_id"),
                    plan_revisions=item.get("plan_revisions", []),
                    derived_tasks=item.get("derived_tasks", []),
                    improvement_queue=item.get("improvement_queue", []),
                    skill_usage=item.get("skill_usage", []),
                    learned_skill_events=item.get("learned_skill_events", []),
                    action_history=item.get("action_history", []),
                    delegated_runtime_sessions=delegated_runtime_sessions,
                    tutorial_context=item.get("tutorial_context", {}),
                    planner_loop_status=item.get("planner_loop_status", "idle"),
                    state=state,
                    proof=proof,
                )
            )
        return missions

    def save_missions(self, missions: list[Mission]) -> None:
        self._write_json_if_changed(
            self.missions_path,
            [asdict(item) for item in missions],
        )

    def upsert_workspace(
        self,
        name: str,
        root_path: str,
        default_runtime: str,
        user_profile: str = "builder",
        preferred_harness: str = "fluxio_hybrid",
        routing_strategy: str = "profile_default",
        route_overrides: list[dict] | None = None,
        auto_optimize_routing: bool | None = None,
        openai_codex_auth_mode: str | None = None,
        minimax_auth_mode: str | None = None,
        commit_message_style: str = "scoped",
        execution_target_preference: str = "profile_default",
        workspace_id: str | None = None,
    ) -> WorkspaceProfile:
        workspaces = self.load_workspaces()
        workspace_root = Path(root_path).resolve()
        now = utc_now_iso()
        normalized_route_overrides = normalize_route_overrides(route_overrides or [])
        normalized_openai_codex_auth_mode = normalize_openai_codex_auth_mode(
            openai_codex_auth_mode
        )
        normalized_minimax_auth_mode = normalize_minimax_auth_mode(minimax_auth_mode)
        for item in workspaces:
            if item.workspace_id == workspace_id or (
                workspace_id is None and Path(item.root_path).resolve() == workspace_root
            ):
                item.name = name
                item.root_path = str(workspace_root)
                item.default_runtime = default_runtime
                item.user_profile = user_profile or item.user_profile
                item.preferred_harness = preferred_harness or item.preferred_harness
                item.routing_strategy = routing_strategy or item.routing_strategy
                item.route_overrides = (
                    normalized_route_overrides
                    if route_overrides is not None
                    else item.route_overrides
                )
                if auto_optimize_routing is not None:
                    item.auto_optimize_routing = bool(auto_optimize_routing)
                if openai_codex_auth_mode is not None:
                    item.openai_codex_auth_mode = normalized_openai_codex_auth_mode
                if minimax_auth_mode is not None:
                    item.minimax_auth_mode = normalized_minimax_auth_mode
                item.commit_message_style = (
                    commit_message_style or item.commit_message_style
                )
                item.execution_target_preference = (
                    execution_target_preference or item.execution_target_preference
                )
                item.workspace_type = detect_workspace_type(workspace_root)
                item.updated_at = now
                self.save_workspaces(workspaces)
                return item

        workspace = WorkspaceProfile(
            workspace_id=workspace_id or f"workspace_{uuid.uuid4().hex[:8]}",
            name=name,
            root_path=str(workspace_root),
            default_runtime=default_runtime,
            workspace_type=detect_workspace_type(workspace_root),
            user_profile=user_profile or "builder",
            preferred_harness=preferred_harness or "fluxio_hybrid",
            routing_strategy=routing_strategy or "profile_default",
            route_overrides=normalized_route_overrides,
            auto_optimize_routing=bool(auto_optimize_routing),
            openai_codex_auth_mode=normalized_openai_codex_auth_mode,
            minimax_auth_mode=normalized_minimax_auth_mode,
            commit_message_style=commit_message_style or "scoped",
            execution_target_preference=execution_target_preference or "profile_default",
            updated_at=now,
        )
        workspaces.append(workspace)
        self.save_workspaces(workspaces)
        return workspace

    def create_mission(
        self,
        workspace_id: str,
        runtime_id: str,
        objective: str,
        success_checks: list[str],
        mode: str,
        verification_commands: list[str],
        max_runtime_seconds: int,
        selected_profile: str = "builder",
        escalation_destination: str = "",
        run_until_behavior: str | None = None,
        deadline_at: str | None = None,
        harness_id: str = "fluxio_hybrid",
        code_execution_enabled: bool = False,
        code_execution_memory: str = "4g",
        code_execution_container_id: str = "",
        code_execution_required: bool = False,
    ) -> Mission:
        missions = self.load_missions()
        self._rebalance_workspace_queue_in_place(missions, workspace_id)
        blocking_mission = self._active_workspace_mission(workspace_id, missions)
        queue_position = 0
        queue_reason = ""
        blocking_mission_id = None
        summary = "Mission created and waiting for first runtime cycle."
        if blocking_mission is not None:
            queue_position = (
                len(
                    [
                        item
                        for item in missions
                        if item.workspace_id == workspace_id
                        and item.state.status not in TERMINAL_MISSION_STATUSES
                        and item.state.queue_position > 0
                    ]
                )
                + 1
            )
            blocking_mission_id = blocking_mission.mission_id
            queue_reason = (
                f"Waiting for mission '{blocking_mission.title or blocking_mission.objective or blocking_mission.mission_id}' "
                "to leave the active slot for this workspace."
            )
            summary = queue_reason
        mission_id = f"mission_{uuid.uuid4().hex[:10]}"
        now = utc_now_iso()
        mission = Mission(
            mission_id=mission_id,
            workspace_id=workspace_id,
            runtime_id=runtime_id,
            objective=objective,
            success_checks=success_checks,
            title=_mission_title(objective),
            created_at=now,
            updated_at=now,
            run_budget=MissionRunBudget(
                mode=mode,
                max_runtime_seconds=max_runtime_seconds,
                focus_window_hours=max(1, round(max_runtime_seconds / 3600)),
                run_until_behavior=run_until_behavior or "pause_on_failure",
                deadline_at=deadline_at or None,
            ),
            verification_policy=MissionVerificationPolicy(
                commands=verification_commands,
                pause_on_failure=(run_until_behavior or "pause_on_failure") != "continue_until_blocked",
            ),
            escalation_policy=ApprovalEscalation(
                channel="telegram",
                enabled=bool(escalation_destination),
                destination=escalation_destination,
                triggers=[
                    "blocked approval",
                    "missing setup step",
                    "verification failure",
                    "completion summary",
                ],
            ),
            harness_id=harness_id or "fluxio_hybrid",
            selected_profile=selected_profile,
            execution_scope=ExecutionScope(
                requested="isolated",
                strategy="direct",
                workspace_root="",
                execution_root="",
                status="pending",
                detail="Execution scope will be resolved during the first harness cycle.",
            ),
            execution_policy=ExecutionPolicy(
                profile_name=selected_profile,
            ),
            code_execution=MissionCodeExecutionConfig(
                enabled=bool(code_execution_enabled),
                memory_limit=code_execution_memory or "4g",
                container_id=str(code_execution_container_id or "").strip(),
                required=bool(code_execution_required),
            ),
            state=MissionStateSnapshot(
                status="queued",
                queue_position=queue_position,
                blocking_mission_id=blocking_mission_id,
                queue_reason=queue_reason,
                code_execution={
                    "enabled": bool(code_execution_enabled),
                    "memory_limit": code_execution_memory or "4g",
                    "container_id": str(code_execution_container_id or "").strip(),
                    "required": bool(code_execution_required),
                    "artifacts": [],
                },
            ),
            tutorial_context={
                "profile": selected_profile,
                "preferredHarness": harness_id or "fluxio_hybrid",
            },
            proof=MissionProof(summary=summary),
        )
        missions.append(mission)
        self._rebalance_workspace_queue_in_place(missions, workspace_id)
        self.save_missions(missions)
        self.append_event(
            MissionEvent(
                mission_id=mission_id,
                kind="mission.queued" if queue_position else "mission.created",
                message=(
                    f"Mission queued behind {blocking_mission_id} for workspace collision avoidance."
                    if queue_position
                    else f"Mission created for runtime {runtime_id}."
                ),
                metadata={
                    "workspaceId": workspace_id,
                    "mode": mode,
                    "queuePosition": queue_position,
                    "blockingMissionId": blocking_mission_id,
                },
            )
        )
        return mission

    def update_mission(self, mission: Mission) -> Mission:
        missions = self.load_missions()
        updated = mission
        updated.updated_at = utc_now_iso()
        for index, item in enumerate(missions):
            if item.mission_id == mission.mission_id:
                missions[index] = updated
                self.save_missions(missions)
                return updated
        missions.append(updated)
        self.save_missions(missions)
        return updated

    def get_workspace(self, workspace_id: str) -> WorkspaceProfile | None:
        for item in self.load_workspaces():
            if item.workspace_id == workspace_id:
                return item
        return None

    def get_mission(self, mission_id: str) -> Mission | None:
        for item in self.load_missions():
            if item.mission_id == mission_id:
                return item
        return None

    def rebalance_mission_queue(
        self,
        workspace_id: str | None = None,
    ) -> list[Mission]:
        missions = self.load_missions()
        self._rebalance_workspace_queue_in_place(missions, workspace_id)
        if missions:
            self.save_missions(missions)
        return missions

    def append_event(self, event: MissionEvent) -> None:
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=True) + "\n")

    def recent_events(self, limit: int = 40) -> list[dict]:
        if not self.events_path.exists():
            return []
        lines = [
            line.strip()
            for line in self.events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return [json.loads(line) for line in lines[-limit:]][::-1]

    def load_workspace_actions(self) -> dict[str, list[dict]]:
        payload = self._load_json(self.workspace_actions_path, {})
        if not isinstance(payload, dict):
            return {}
        histories: dict[str, list[dict]] = {}
        for key, value in payload.items():
            if isinstance(value, list):
                histories[str(key)] = value
        return histories

    def append_workspace_action(
        self,
        history_key: str,
        record: dict,
        limit: int = 24,
    ) -> dict:
        if history_key == "__setup__":
            self._invalidate_snapshot_caches()
        histories = self.load_workspace_actions()
        entries = list(histories.get(history_key, []))
        entries.append(record)
        histories[history_key] = entries[-max(1, limit) :]
        self.workspace_actions_path.write_text(
            json.dumps(histories, indent=2),
            encoding="utf-8",
        )
        return record

    def build_snapshot(self) -> dict:
        workspaces = self.load_workspaces()
        missions = self.load_missions()
        workspace_action_history = self.load_workspace_actions()
        setup_history = workspace_action_history.get("__setup__", [])
        runtime_statuses = detect_runtime_statuses(self.root)
        runtime_lookup = {item.runtime_id: asdict(item) for item in runtime_statuses}
        profiles = ProfileRegistry(self.root / "config" / "profiles.json")
        skill_library = SkillLibrary(
            root=self.root,
            registry=SkillRegistry(self.root / "config" / "skills.json"),
        )
        onboarding = detect_onboarding_status(self.root)
        setup_health = onboarding.get("setupHealth", {})
        setup_health["actionHistory"] = workspace_action_history.get("__setup__", [])
        guidance = build_guidance_snapshot(self.root, onboarding=onboarding)
        runtime_supervisor = DelegatedRuntimeSupervisor(self.root)
        connected_apps_snapshot = build_connected_apps_snapshot(self.root)
        harness_lab_snapshot = build_harness_lab_snapshot(self.root)
        activity = self.recent_events()
        provider_auth_presence = _provider_auth_presence_from_env()
        workspace_lookup = {item.workspace_id: item for item in workspaces}

        workspace_cards = []
        recommended_skill_pack_objects = []
        for workspace in workspaces:
            runtime_id = workspace.default_runtime
            profile = profiles.resolve(workspace.user_profile, Path(workspace.root_path))
            profile_parameters = _profile_parameter_snapshot(
                workspace.user_profile,
                profile,
            )
            git_snapshot = _inspect_workspace_git(
                Path(workspace.root_path),
                commit_message_style=workspace.commit_message_style,
            )
            validation_actions = _build_validation_actions(Path(workspace.root_path))
            verification_commands = detect_default_verification_commands(
                Path(workspace.root_path)
            )
            skill_recommendations = [
                asdict(item)
                for item in recommend_skills(
                    workspace.workspace_type, workspace.default_runtime
                )
            ]
            integration_recommendations = [
                asdict(item)
                for item in recommend_integrations(
                    workspace.workspace_type, workspace.default_runtime
                )
            ]
            recommended_skill_packs = SkillLibrary.recommended_packs_from_skills(
                skill_recommendations
            )
            recommended_skill_pack_objects.extend(recommended_skill_packs)
            workspace_cards.append(
                {
                    **asdict(workspace),
                    "openaiCodexSetupStatus": _openai_codex_setup_status_for_workspace(
                        workspace,
                        auth_presence=provider_auth_presence,
                    ),
                    "minimaxSetupStatus": _minimax_setup_status_for_workspace(
                        workspace,
                        setup_history,
                    ),
                    "runtimeStatus": runtime_lookup.get(runtime_id),
                    "gitSnapshot": git_snapshot,
                    "gitActions": _build_git_actions(git_snapshot, profile_parameters),
                    "validationActions": validation_actions,
                    "verificationCommands": verification_commands,
                    "workspaceActionHistory": workspace_action_history.get(
                        workspace.workspace_id,
                        [],
                    ),
                    "profileParameters": profile_parameters,
                    "skillRecommendations": skill_recommendations,
                    "integrationRecommendations": integration_recommendations,
                    "recommendedSkillPacks": [
                        asdict(item) for item in recommended_skill_packs
                    ],
                    "serviceManagement": _build_workspace_service_management(
                        setup_health=setup_health,
                        runtime_status=runtime_lookup.get(runtime_id),
                        integration_recommendations=integration_recommendations,
                        connected_apps=connected_apps_snapshot.get("connectedSessions", []),
                    ),
                }
            )

        for mission in missions:
            _sync_execution_scope_snapshot(mission)
            refreshed_sessions = []
            for session in mission.delegated_runtime_sessions:
                refreshed = runtime_supervisor.refresh_session(session)
                refreshed_sessions.append(refreshed)
            mission.delegated_runtime_sessions = refreshed_sessions
            mission.action_history = normalize_action_history(mission.action_history)
            mission.state.delegated_runtime_sessions = [asdict(item) for item in refreshed_sessions]
            refresh_mission_runtime_state(mission, refreshed_sessions)
            mission.state.provider_runtime_truth = _provider_truth_for_mission(
                mission,
                auth_presence=provider_auth_presence,
                workspace=workspace_lookup.get(mission.workspace_id),
            )
            sync_mission_state_snapshot(mission)
        self._rebalance_workspace_queue_in_place(missions)
        missions_payload = []
        for item in missions:
            mission_payload = asdict(item)
            mission_payload["missionLoop"] = build_mission_loop_snapshot(item)
            mission_payload["effectiveRouteContract"] = (
                item.effective_route_contract
                if item.effective_route_contract
                else _effective_route_contract_for_mission(item)
            )
            mission_payload["providerTruth"] = dict(item.state.provider_runtime_truth or {})
            missions_payload.append(mission_payload)
        recommended_skill_packs = list(
            {item.pack_id: item for item in recommended_skill_pack_objects}.values()
        )
        skill_catalog = skill_library.build_catalog(
            recommended_packs=recommended_skill_packs,
        )
        workspace_payload = []
        for workspace in workspace_cards:
            active_mission = self._active_workspace_mission(workspace["workspace_id"], missions)
            queued_missions = [
                item
                for item in missions
                if item.workspace_id == workspace["workspace_id"] and item.state.queue_position > 0
            ]
            service_management = workspace.get("serviceManagement", [])
            workspace_payload.append(
                {
                    **workspace,
                    "activeMissionId": active_mission.mission_id if active_mission else "",
                    "activeMissionTitle": active_mission.title if active_mission else "",
                    "queuedMissionIds": [item.mission_id for item in queued_missions],
                    "queuedMissionCount": len(queued_missions),
                    "serviceManagementSummary": _service_management_summary(service_management),
                }
            )
        inbox_items = [
            {
                "missionId": item.mission_id,
                "channel": item.escalation_policy.channel,
                "destination": item.escalation_policy.destination,
                "ready": item.escalation_policy.delivery_ready,
                "pendingCount": item.escalation_policy.pending_count,
                "previewMessage": build_escalation_preview(item),
            }
            for item in missions
            if item.state.status in {"blocked", "needs_approval", "verification_failed", "completed"}
        ]

        active_workspace_payload = workspace_payload[0] if workspace_payload else {}
        active_workspace_id = str(active_workspace_payload.get("workspace_id", "") or "")
        active_mission = self._active_workspace_mission(active_workspace_id, missions)
        active_provider_truth = (
            dict(active_mission.state.provider_runtime_truth or {})
            if active_mission is not None
            else {}
        )
        active_route = (
            dict(active_provider_truth.get("activeRoute", {}))
            if isinstance(active_provider_truth.get("activeRoute"), dict)
            else {}
        )
        provider_status = {}
        for provider_id in ("openai", "anthropic", "openrouter"):
            aliases = (
                {"openai", "openai-codex"}
                if provider_id == "openai"
                else {provider_id}
            )
            last_success = (
                active_provider_truth.get("lastSuccessfulCall", {})
                if isinstance(active_provider_truth.get("lastSuccessfulCall"), dict)
                else {}
            )
            last_failure = (
                active_provider_truth.get("lastFailure", {})
                if isinstance(active_provider_truth.get("lastFailure"), dict)
                else {}
            )
            openai_status = (
                dict(active_workspace_payload.get("openaiCodexSetupStatus", {}))
                if provider_id == "openai"
                and isinstance(active_workspace_payload.get("openaiCodexSetupStatus"), dict)
                else {}
            )
            auth_present = (
                bool(openai_status.get("authPresent", False))
                if provider_id == "openai"
                else bool(provider_auth_presence.get(provider_id, False))
            )
            provider_status[provider_id] = {
                "providerId": provider_id,
                "authPresent": auth_present,
                "configured": auth_present,
                "authMode": (
                    str(openai_status.get("authMode", "")).strip().lower()
                    if provider_id == "openai"
                    else ""
                ),
                "authPath": (
                    str(openai_status.get("authPath", "")).strip()
                    if provider_id == "openai"
                    else ""
                ),
                "activeRoute": active_route
                if str(active_route.get("provider", "")).strip().lower() in aliases
                else {},
                "lastSuccessfulModelCall": (
                    last_success
                    if str(last_success.get("provider", "")).strip().lower() in aliases
                    else {}
                ),
                "lastProviderFailure": (
                    last_failure
                    if str(last_failure.get("provider", "")).strip().lower() in aliases
                    else {}
                ),
                "lastCheckedAt": utc_now_iso(),
            }
        provider_setup_status = {
            **provider_status,
            "minimax": active_workspace_payload.get("minimaxSetupStatus")
            or _minimax_setup_status_for_workspace(
                self._default_workspace_profile(),
                setup_history,
            ),
        }
        efficiency_autotune = _build_efficiency_autotune_snapshot(
            harness_lab=harness_lab_snapshot,
            auto_optimize_enabled=bool(
                active_workspace_payload.get("auto_optimize_routing", False)
            ),
            activity=activity,
        )
        release_readiness = build_release_readiness_snapshot(
            self.root,
            onboarding=onboarding,
            setup_health=setup_health,
            harness_lab=harness_lab_snapshot,
        )

        return {
            "workspaceRoot": str(self.root),
            "ui": {
                "uiMode": "agent",
                "defaultMode": "agent",
                "availableModes": ["agent", "builder"],
                "layout": "t3_workbench",
                "sharedMissionState": True,
            },
            "workspaces": workspace_payload,
            "missions": missions_payload,
            "runtimes": [asdict(item) for item in runtime_statuses],
            "activity": activity,
            "inbox": inbox_items,
            "onboarding": onboarding,
            "setupHealth": setup_health,
            "guidance": guidance,
            "profiles": {
                "defaultProfile": profiles.default_profile,
                "availableProfiles": profiles.list_names(),
                "details": {
                    name: {
                        "description": profile.description,
                        "ui": profile.ui,
                        "agent": asdict(profile.agent),
                        "parameters": _profile_parameter_snapshot(name, profile),
                    }
                    for name, profile in profiles.profiles.items()
                },
            },
            "skillLibrary": skill_catalog,
            "workflowStudio": _build_workflow_studio(
                workspace_payload,
                missions_payload,
                setup_health,
                skill_catalog,
            ),
            "harnessLab": harness_lab_snapshot,
            "providerSetupStatus": provider_setup_status,
            "efficiencyAutotune": efficiency_autotune,
            "bridgeLab": connected_apps_snapshot,
            "releaseReadiness": release_readiness,
        }

    def _default_workspace_profile(self) -> WorkspaceProfile:
        now = utc_now_iso()
        return WorkspaceProfile(
            workspace_id="workspace_primary",
            name=self.root.name.replace("-", " ").title(),
            root_path=str(self.root),
            default_runtime="openclaw",
            workspace_type=detect_workspace_type(self.root),
            user_profile="builder",
            preferred_harness="fluxio_hybrid",
            routing_strategy="profile_default",
            route_overrides=[],
            auto_optimize_routing=False,
            openai_codex_auth_mode="none",
            minimax_auth_mode="none",
            commit_message_style="scoped",
            execution_target_preference="profile_default",
            updated_at=now,
        )

    @staticmethod
    def _load_json(path: Path, default: list | dict) -> list | dict:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def _active_workspace_mission(
        self,
        workspace_id: str,
        missions: list[Mission],
    ) -> Mission | None:
        for mission in missions:
            if mission.workspace_id != workspace_id:
                continue
            if mission.state.status in TERMINAL_MISSION_STATUSES:
                continue
            # A budget-exhausted mission should not keep the active slot forever.
            # It can remain visible in the queue, but newer missions must still advance.
            stop_reason = (mission.state.stop_reason or mission.state.last_error or "").strip().lower()
            if stop_reason == "runtime_budget":
                continue
            if mission.state.queue_position == 0:
                return mission
        return None

    def _rebalance_workspace_queue_in_place(
        self,
        missions: list[Mission],
        workspace_id: str | None = None,
    ) -> None:
        workspace_ids = (
            [workspace_id]
            if workspace_id is not None
            else list(dict.fromkeys(item.workspace_id for item in missions))
        )
        for current_workspace_id in workspace_ids:
            workspace_missions = [
                item for item in missions if item.workspace_id == current_workspace_id
            ]
            active = self._active_workspace_mission(current_workspace_id, workspace_missions)
            candidates = [
                item
                for item in workspace_missions
                if item.state.status not in TERMINAL_MISSION_STATUSES
            ]
            if not candidates:
                continue

            waiting = [
                item for item in candidates if active is None or item.mission_id != active.mission_id
            ]
            waiting.sort(
                key=lambda item: (
                    item.state.queue_position if item.state.queue_position > 0 else 10_000,
                    item.created_at,
                    item.mission_id,
                )
            )

            if active is None:
                active = waiting.pop(0)

            was_waiting = bool(
                active.state.queue_position
                or active.state.blocking_mission_id
                or active.state.queue_reason
            )
            active.state.queue_position = 0
            active.state.blocking_mission_id = None
            active.state.queue_reason = ""
            if was_waiting and active.state.status == "queued":
                active.proof.summary = (
                    "Mission reached the front of the workspace queue. Resume to start."
                )

            active_label = active.title or active.objective or active.mission_id
            for index, queued in enumerate(waiting, start=1):
                queued.state.status = "queued"
                queued.state.queue_position = index
                queued.state.blocking_mission_id = active.mission_id
                queued.state.queue_reason = (
                    f"Waiting for mission '{active_label}' to leave the active slot for this workspace."
                )
                queued.proof.summary = queued.state.queue_reason

            for mission in workspace_missions:
                if mission.state.status in TERMINAL_MISSION_STATUSES:
                    mission.state.queue_position = 0
                    mission.state.blocking_mission_id = None
                    mission.state.queue_reason = ""


def _profile_parameter_snapshot(profile_name: str, profile) -> dict:
    if profile is None:
        return {
            "profileName": profile_name,
            "autonomyLevel": "balanced",
            "approvalStrictness": "tiered",
            "verificationCadence": "each_cycle",
            "explanationLevel": "medium",
            "explorationBreadth": "bounded",
            "autoContinueBehavior": "pause_on_failure",
            "gitActionPolicy": "approval_gated",
            "setupAutomationPolicy": "guided_install",
            "learningAggressiveness": "bounded",
            "uiDensity": "comfortable",
            "visibilityLevel": "balanced",
        }

    approval_mode = profile.agent.approval_mode or "tiered"
    pause_on_failure = (
        True
        if profile.agent.pause_on_verification_failure is None
        else bool(profile.agent.pause_on_verification_failure)
    )
    delegation = profile.agent.delegation_aggressiveness or "balanced"
    mode = profile.agent.mode or "autopilot"
    autonomy_map = {
        "fast": "guided",
        "careful": "guided",
        "autopilot": "balanced",
        "swarms": "high",
        "deep_run": "maximum",
    }
    visibility_map = {
        "beginner": "guided",
        "builder": "balanced",
        "advanced": "detailed",
        "experimental": "expert",
    }
    learning_map = {
        "low": "guarded",
        "balanced": "bounded",
        "high": "aggressive",
    }
    return {
        "profileName": profile.name,
        "autonomyLevel": autonomy_map.get(mode, "balanced"),
        "approvalStrictness": approval_mode,
        "verificationCadence": "each_cycle" if pause_on_failure else "continuous_until_blocked",
        "explanationLevel": profile.agent.explanation_depth or "medium",
        "explorationBreadth": "wide" if (profile.agent.parallel_agents or 1) > 2 else "bounded",
        "autoContinueBehavior": "pause_on_failure" if pause_on_failure else "continue_until_blocked",
        "gitActionPolicy": "profile_resolved" if approval_mode == "hands_free" else "approval_gated",
        "setupAutomationPolicy": "installer_guided" if profile.name == "beginner" else "repair_and_verify",
        "learningAggressiveness": learning_map.get(delegation, "bounded"),
        "uiDensity": profile.ui.get("density", "comfortable"),
        "visibilityLevel": visibility_map.get(profile.name, "balanced"),
    }


def build_mission_loop_snapshot(mission: Mission) -> dict:
    plan_revisions = mission.plan_revisions or []
    latest_revision = plan_revisions[-1] if plan_revisions else None
    delegated = mission.delegated_runtime_sessions or []
    if mission.state.status in {"queued", "draft"}:
        phase = "plan"
    elif mission.state.status == "verification_failed":
        phase = "replan"
    elif mission.proof.failed_checks or mission.state.verification_failures:
        phase = "verify"
    elif any(item.status in {"launching", "running", "waiting_for_approval"} for item in delegated):
        phase = "execute"
    elif mission.state.active_step_id:
        phase = "execute"
    elif plan_revisions:
        phase = "verify"
    else:
        phase = "plan"

    verification_result = "pending"
    if mission.proof.failed_checks or mission.state.verification_failures:
        verification_result = "failed"
    elif mission.proof.passed_checks:
        verification_result = "passed"

    continuity_state, continuity_detail = _continuity_state_for_mission(mission, delegated)
    time_budget = _time_budget_snapshot_for_mission(mission)

    return {
        "currentCyclePhase": phase,
        "cycleCount": len(plan_revisions) or (1 if mission.state.status != "draft" else 0),
        "lastVerificationResult": verification_result,
        "lastVerificationSummary": _verification_summary_for_mission(mission, verification_result),
        "lastReplanReason": _plan_revision_value(latest_revision, "trigger"),
        "lastReplanTrigger": _plan_revision_value(latest_revision, "trigger"),
        "improvementQueue": [
            {"title": item.get("title", ""), "priority": item.get("priority", "medium")}
            if isinstance(item, dict)
            else {"title": getattr(item, "title", ""), "priority": getattr(item, "priority", "medium")}
            for item in mission.improvement_queue
        ],
        "resumeReady": bool(mission.state.latest_session_id),
        "continuityState": continuity_state,
        "continuityDetail": continuity_detail,
        "approvalHistoryCount": len(mission.state.approval_history),
        "pauseReason": time_budget["lastPauseReason"],
        "currentRuntimeLane": _current_runtime_lane_for_mission(mission, delegated),
        "timeBudget": time_budget,
        "contextWindow": {
            "usedTokens": mission.state.context_used_tokens,
            "usageRatio": mission.state.context_usage_ratio,
            "status": mission.state.context_status,
            "handoffCount": mission.state.handoff_count,
            "lastHandoffReason": mission.state.last_handoff_reason,
        },
        "runtimeAutonomy": mission.state.runtime_autonomy,
        "routeChangeCount": mission.state.route_change_count,
        "parallelAgents": mission.state.parallel_agents,
        "mergePolicy": mission.state.merge_policy,
        "blocker": mission.state.blocker_classification,
        "providerTruth": mission.state.provider_runtime_truth,
        "codeExecution": mission.state.code_execution,
    }


def sync_mission_state_snapshot(mission: Mission) -> dict:
    _sync_execution_scope_snapshot(mission)
    mission_loop = build_mission_loop_snapshot(mission)
    mission.state.current_cycle_phase = mission_loop["currentCyclePhase"]
    mission.state.cycle_count = mission_loop["cycleCount"]
    mission.state.last_verification_result = mission_loop["lastVerificationResult"]
    mission.state.last_replan_reason = mission_loop["lastReplanReason"]
    mission.state.last_verification_summary = mission_loop["lastVerificationSummary"]
    mission.state.last_replan_trigger = mission_loop["lastReplanTrigger"]
    mission.state.continuity_state = mission_loop["continuityState"]
    mission.state.continuity_detail = mission_loop["continuityDetail"]
    mission.state.elapsed_runtime_seconds = mission_loop["timeBudget"]["elapsedSeconds"]
    mission.state.remaining_runtime_seconds = mission_loop["timeBudget"]["remainingSeconds"]
    mission.state.time_budget_status = mission_loop["timeBudget"]["status"]
    mission.state.last_budget_pause_reason = mission_loop["timeBudget"]["lastPauseReason"]
    mission.state.current_runtime_lane = mission_loop["currentRuntimeLane"]
    mission.state.blocker_classification = mission_loop.get("blocker", {})
    mission.state.provider_runtime_truth = mission_loop.get("providerTruth", {})
    mission.state.code_execution = mission_loop.get("codeExecution", {})
    return mission_loop


def _sync_execution_scope_snapshot(mission: Mission) -> None:
    truth = derive_execution_target(
        execution_root=mission.execution_scope.execution_root,
        workspace_root=mission.execution_scope.workspace_root,
        strategy=mission.execution_scope.strategy,
    )
    mission.execution_scope.execution_target = truth["execution_target"]
    mission.execution_scope.storage_mode = truth["storage_mode"]
    mission.execution_scope.host_locality = truth["host_locality"]
    mission.execution_scope.execution_target_detail = truth["execution_target_detail"]
    mission.state.execution_scope = asdict(mission.execution_scope)


def _plan_revision_value(revision: object, key: str) -> str:
    if revision is None:
        return ""
    if isinstance(revision, dict):
        return str(revision.get(key, "") or "")
    return str(getattr(revision, key, "") or "")


def _provider_auth_presence_from_env() -> dict[str, bool]:
    presence: dict[str, bool] = {}
    for provider_id, env_name in PROVIDER_ENV_HINTS.items():
        presence[provider_id] = bool(str(os.environ.get(env_name, "")).strip())
    return presence


def _route_role_for_phase(phase: str) -> str:
    normalized = str(phase or "execute").strip().lower()
    if normalized in {"plan", "replan"}:
        return "planner"
    if normalized == "verify":
        return "verifier"
    return "executor"


def _route_rows_for_mission(mission: Mission) -> list[dict]:
    effective_contract = (
        mission.effective_route_contract
        if mission.effective_route_contract
        else _effective_route_contract_for_mission(mission)
    )
    rows = effective_contract.get("roles", [])
    if not isinstance(rows, list):
        return []
    normalized: list[dict] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        if role not in ROUTE_OVERRIDE_ROLES:
            continue
        normalized.append(
            {
                "role": role,
                "provider": str(item.get("provider", "")).strip().lower(),
                "model": str(item.get("model", "")).strip(),
                "effort": str(item.get("effort", "")).strip().lower(),
                "budgetClass": str(
                    item.get("budgetClass", item.get("budget_class", ""))
                ).strip(),
                "source": str(item.get("source", "")).strip(),
                "reason": str(item.get("reason", "")).strip(),
            }
        )
    return normalized


def _route_row_for_phase(
    mission: Mission,
    phase: str,
    *,
    route_rows: list[dict] | None = None,
) -> dict:
    rows = route_rows if route_rows is not None else _route_rows_for_mission(mission)
    role = _route_role_for_phase(phase)
    for item in rows:
        if str(item.get("role", "")).strip().lower() == role:
            return item
    return {
        "role": role,
        "provider": "",
        "model": "",
        "effort": "",
        "budgetClass": "",
        "source": "",
        "reason": "",
    }


def _provider_truth_from_action_history(
    mission: Mission,
    *,
    route_rows: list[dict],
) -> tuple[dict, dict]:
    success: dict = {}
    failure: dict = {}
    for entry in reversed(mission.action_history or []):
        if not isinstance(entry, dict):
            if hasattr(entry, "__dataclass_fields__"):
                entry = asdict(entry)
            else:
                continue
        result = dict(entry.get("result", {}))
        proposal = dict(entry.get("proposal", {}))
        delegation = dict(proposal.get("delegation_metadata", {}))
        phase = str(
            delegation.get("cycle_phase", mission.state.current_cycle_phase or "execute")
        ).strip().lower()
        route = _route_row_for_phase(mission, phase, route_rows=route_rows)
        provider = str(route.get("provider", "")).strip().lower()
        model = str(route.get("model", "")).strip()
        role = str(route.get("role", "")).strip().lower()
        if not provider and not model:
            continue
        summary = str(
            result.get("result_summary")
            or result.get("error")
            or result.get("stderr")
            or result.get("stdout")
            or ""
        ).strip()
        if len(summary) > 220:
            summary = summary[:217].rstrip() + "..."
        row = {
            "provider": provider,
            "model": model,
            "role": role,
            "phase": phase,
            "at": str(entry.get("executed_at", "") or ""),
            "source": "action_history",
            "summary": summary,
        }
        if bool(result.get("ok")):
            if not success:
                success = row
        elif not failure:
            failure = row
        if success and failure:
            break
    return success, failure


def _provider_truth_for_mission(
    mission: Mission,
    *,
    auth_presence: dict[str, bool],
    workspace: WorkspaceProfile | None = None,
) -> dict:
    phase = str(mission.state.current_cycle_phase or "execute").strip().lower()
    route_rows = _route_rows_for_mission(mission)
    active_route = _route_row_for_phase(mission, phase, route_rows=route_rows)
    active_provider = str(active_route.get("provider", "")).strip().lower()
    active_model = str(active_route.get("model", "")).strip()
    openai_auth_mode = normalize_openai_codex_auth_mode(
        getattr(workspace, "openai_codex_auth_mode", "none")
    )
    minimax_auth_mode = normalize_minimax_auth_mode(
        getattr(workspace, "minimax_auth_mode", "none")
    )
    if active_provider in {"openai", "openai-codex"}:
        api_key_present = bool(
            auth_presence.get("openai", False) or auth_presence.get("openai-codex", False)
        )
        auth_present = (
            openai_auth_mode == "chatgpt"
            or (openai_auth_mode == "api" and api_key_present)
            or api_key_present
        )
        auth_mode = (
            openai_auth_mode
            if openai_auth_mode != "none"
            else ("api" if api_key_present else "none")
        )
        auth_path = openai_codex_auth_label(auth_mode)
    elif active_provider in {"minimax", "minimax-portal", "minimax-cn"}:
        api_key_present = bool(
            auth_presence.get("minimax", False)
            or auth_presence.get("minimax-cn", False)
            or auth_presence.get(active_provider, False)
        )
        auth_present = (
            minimax_auth_mode == "minimax-portal-oauth"
            or (minimax_auth_mode == "minimax-api" and api_key_present)
            or api_key_present
        )
        auth_mode = (
            minimax_auth_mode
            if minimax_auth_mode != "none"
            else ("minimax-api" if api_key_present else "none")
        )
        auth_path = minimax_auth_label(auth_mode)
    else:
        auth_present = bool(auth_presence.get(active_provider, False)) if active_provider else False
        auth_mode = ""
        auth_path = ""
    last_success, last_failure = _provider_truth_from_action_history(
        mission,
        route_rows=route_rows,
    )
    if not last_failure:
        for session in reversed(mission.delegated_runtime_sessions or []):
            if hasattr(session, "__dataclass_fields__"):
                row = asdict(session)
            elif isinstance(session, dict):
                row = dict(session)
            else:
                continue
            status = str(row.get("status", "")).strip().lower()
            if status not in {"failed", "stopped"}:
                continue
            provider = str(row.get("target_provider", active_provider)).strip().lower()
            model = str(row.get("target_model", active_model)).strip()
            if not provider and not model:
                continue
            last_failure = {
                "provider": provider,
                "model": model,
                "role": str(row.get("target_role", _route_role_for_phase(phase))).strip().lower(),
                "phase": str(row.get("target_phase", phase)).strip().lower(),
                "at": str(row.get("updated_at", "") or ""),
                "source": "delegated_runtime",
                "summary": str(row.get("last_event") or row.get("detail") or "").strip(),
            }
            break

    updated_at_candidates = [
        str(mission.updated_at or ""),
        str(last_success.get("at", "") or "") if isinstance(last_success, dict) else "",
        str(last_failure.get("at", "") or "") if isinstance(last_failure, dict) else "",
    ]
    truth_updated_at = max(
        (value for value in updated_at_candidates if value),
        default=str(mission.updated_at or ""),
    )

    return {
        "currentPhase": phase or "execute",
        "activeRoute": {
            "role": str(active_route.get("role", "")).strip().lower(),
            "provider": active_provider,
            "model": active_model,
            "effort": str(active_route.get("effort", "")).strip().lower(),
            "budgetClass": str(active_route.get("budgetClass", "")).strip(),
            "source": str(active_route.get("source", "")).strip(),
        },
        "authPresent": auth_present,
        "authKnown": bool(active_provider),
        "authMode": auth_mode,
        "authPath": auth_path,
        "lastSuccessfulCall": last_success,
        "lastFailure": last_failure,
        "updatedAt": truth_updated_at,
    }


def _effective_route_contract_for_mission(mission: Mission) -> dict:
    route_rows = []
    for item in mission.route_configs or []:
        route = dict(item) if isinstance(item, dict) else asdict(item)
        role = str(route.get("role", "")).strip().lower()
        if role not in ROUTE_OVERRIDE_ROLES:
            continue
        explanation = str(route.get("explanation", "") or "")
        source = (
            "override"
            if "override" in explanation.lower()
            else ("strategy" if "strategy" in explanation.lower() else "profile_default")
        )
        route_rows.append(
            {
                "role": role,
                "provider": route.get("provider", ""),
                "model": route.get("model", ""),
                "effort": route.get("effort", "medium"),
                "budgetClass": route.get("budget_class", route.get("budgetClass", "")),
                "fallbackPolicy": route.get("fallback_policy", route.get("fallbackPolicy", "same_provider")),
                "source": source,
                "reason": explanation,
            }
        )
    if route_rows:
        summary = " | ".join(
            [
                f"{row['role']}: {row['provider']}:{row['model']} ({row['source']})"
                for row in route_rows
            ]
        )
    else:
        summary = "No route contract resolved yet."
    return {
        "roles": route_rows,
        "resolutionOrder": "override > strategy > profile_default",
        "whyThisRoute": summary,
        "fallbackPolicy": "same_provider",
    }


def refresh_mission_runtime_state(
    mission: Mission,
    refreshed_sessions: list[DelegatedRuntimeSession],
) -> None:
    prompts = [
        item.pending_approval.get("prompt", "Delegated approval required.")
        for item in refreshed_sessions
        if item.status == "waiting_for_approval"
    ]
    approval_payload = next(
        (dict(item.pending_approval) for item in refreshed_sessions if item.pending_approval),
        {},
    )
    approval_history = [
        entry
        for session in refreshed_sessions
        for entry in session.approval_history
        if isinstance(entry, dict)
    ]

    mission.state.pending_approval_payload = approval_payload
    mission.state.approval_history = approval_history[-8:]
    if not prompts:
        mission.proof.pending_approvals = []
    if refreshed_sessions:
        mission.state.last_runtime_event = (
            refreshed_sessions[-1].last_event or mission.state.last_runtime_event
        )

    if prompts:
        mission.state.status = "needs_approval"
        mission.proof.summary = prompts[0]
        mission.proof.pending_approvals = prompts
    elif any(item.status in {"launching", "running"} for item in refreshed_sessions):
        mission.state.status = "running"
        mission.proof.summary = (
            "Delegated runtime lane is active. Fluxio will continue when it finishes."
        )

    continuity_state, continuity_detail = _continuity_state_for_mission(mission, refreshed_sessions)
    mission.state.continuity_state = continuity_state
    mission.state.continuity_detail = continuity_detail


def normalize_action_history(action_history: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for item in action_history or []:
        record = dict(item)
        proposal = dict(record.get("proposal", {}))
        source_kind = proposal.get("sourceKind") or _infer_action_source_kind(proposal)
        proposal["sourceKind"] = source_kind
        result = dict(record.get("result", {}))
        result.setdefault("sourceKind", source_kind)
        record["proposal"] = proposal
        record["result"] = result
        normalized.append(record)
    return normalized


def _infer_action_source_kind(proposal: dict) -> str:
    if proposal.get("delegation_metadata"):
        return "delegated"
    if proposal.get("kind") in {
        "runtime_delegate",
        "delegated_runtime",
        "delegated_action",
    }:
        return "delegated"
    return "local"


def _continuity_state_for_mission(
    mission: Mission,
    delegated: list[DelegatedRuntimeSession],
) -> tuple[str, str]:
    if any(item.status == "waiting_for_approval" for item in delegated):
        prompt = next(
            (
                item.pending_approval.get("prompt", "Delegated runtime is paused on approval.")
                for item in delegated
                if item.status == "waiting_for_approval"
            ),
            "Delegated runtime is paused on approval.",
        )
        return "approval_waiting", prompt
    if any(item.status in {"launching", "running"} for item in delegated):
        runtime_id = next(
            (item.runtime_id for item in delegated if item.status in {"launching", "running"}),
            mission.runtime_id,
        )
        return "delegated_active", f"{runtime_id} lane is still active and restart-safe."
    if any(item.status in {"completed", "failed"} and not item.acknowledged for item in delegated):
        return (
            "resume_available",
            "A delegated lane finished while Fluxio was away. Resume once to reconcile proof and planning state.",
        )
    if mission.state.latest_session_id and mission.state.status not in TERMINAL_MISSION_STATUSES:
        return "resume_available", "Mission can resume safely from the last recorded session."
    if mission.state.status in TERMINAL_MISSION_STATUSES:
        return "terminal", "Mission is in a terminal state with recorded proof."
    return "fresh_only", "No resumable mission continuity has been recorded yet."


def _verification_summary_for_mission(mission: Mission, verification_result: str) -> str:
    if verification_result == "failed":
        failed = mission.proof.failed_checks or mission.state.verification_failures
        return f"Failed: {', '.join(failed[:2])}" if failed else "Verification failed."
    if verification_result == "passed":
        passed_count = len(mission.proof.passed_checks)
        return f"Passed {passed_count} verification check(s)."
    return "Verification is still pending."


def _parse_iso_datetime(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def mission_time_budget_window(
    mission: Mission,
    now: datetime | None = None,
) -> dict:
    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    started_at = _parse_iso_datetime(mission.created_at) or current_time
    elapsed_seconds = max(0, round((current_time - started_at).total_seconds()))

    deadline_at = _parse_iso_datetime(mission.run_budget.deadline_at)
    max_runtime_seconds = max(0, int(mission.run_budget.max_runtime_seconds or 0))
    if deadline_at is not None:
        max_runtime_seconds = max(
            0,
            round((deadline_at - started_at).total_seconds()),
        )
        remaining_seconds = max(
            0,
            round((deadline_at - current_time).total_seconds()),
        )
    else:
        remaining_seconds = max(0, max_runtime_seconds - elapsed_seconds)

    return {
        "startedAt": started_at.isoformat(),
        "deadlineAt": deadline_at.isoformat() if deadline_at is not None else None,
        "maxRuntimeSeconds": max_runtime_seconds,
        "elapsedSeconds": elapsed_seconds,
        "remainingSeconds": remaining_seconds,
    }


def _time_budget_snapshot_for_mission(mission: Mission) -> dict:
    delegated = mission.delegated_runtime_sessions or []
    budget_window = mission_time_budget_window(mission)
    elapsed_seconds = int(budget_window["elapsedSeconds"])
    max_runtime_seconds = int(budget_window["maxRuntimeSeconds"])
    remaining_seconds = int(budget_window["remainingSeconds"])
    pause_reason = _pause_reason_for_mission(mission, delegated)

    if mission.state.status in TERMINAL_MISSION_STATUSES:
        status = mission.state.status
    elif pause_reason == "runtime_budget":
        status = "budget_exhausted"
    elif mission.state.status == "needs_approval":
        status = "paused_for_approval"
    elif pause_reason in {"verification_failed", "verification_failure"} or mission.state.status == "verification_failed":
        status = "paused_for_verification"
    elif mission.state.status == "blocked":
        status = "paused"
    elif mission.state.status == "queued":
        status = "queued"
    elif any(item.status in {"launching", "running"} for item in delegated):
        status = "delegated_active"
    elif mission.state.status == "running":
        status = "running"
    else:
        status = "pending"

    return {
        "mode": mission.run_budget.mode,
        "runUntilBehavior": mission.run_budget.run_until_behavior,
        "focusWindowHours": mission.run_budget.focus_window_hours,
        "deadlineAt": budget_window["deadlineAt"],
        "maxRuntimeSeconds": max_runtime_seconds,
        "budgetHours": round(max_runtime_seconds / 3600, 2) if max_runtime_seconds else 0,
        "elapsedSeconds": elapsed_seconds,
        "remainingSeconds": remaining_seconds,
        "status": status,
        "lastPauseReason": pause_reason,
    }


def _pause_reason_for_mission(
    mission: Mission,
    delegated: list[DelegatedRuntimeSession],
) -> str:
    waiting_session = next(
        (item for item in delegated if item.status == "waiting_for_approval"),
        None,
    )
    if waiting_session is not None:
        return waiting_session.pending_approval.get(
            "prompt",
            "Delegated runtime is paused on approval.",
        )

    raw_reason = mission.state.stop_reason or mission.state.last_budget_pause_reason or ""
    if raw_reason == "runtime_budget":
        return "Runtime budget exhausted."
    if raw_reason in {"verification_failed", "verification_failure"} or mission.state.status == "verification_failed":
        summary = mission.state.last_verification_summary or _verification_summary_for_mission(mission, "failed")
        return summary or "Verification failed."
    if raw_reason == "approval_required":
        return "Operator approval is required before Fluxio can continue."
    if raw_reason == "delegated_runtime_running":
        return "Delegated runtime lane is still active and restart-safe."
    if raw_reason:
        return raw_reason

    if any(item.status in {"launching", "running"} for item in delegated):
        return "Delegated runtime lane is still active and restart-safe."
    if mission.state.status == "queued":
        return mission.state.queue_reason or "Mission is queued behind another active mission."
    if mission.state.status == "blocked":
        return mission.state.last_error or "Mission is paused and needs operator attention."
    return ""


def _current_runtime_lane_for_mission(
    mission: Mission,
    delegated: list[DelegatedRuntimeSession],
) -> str:
    for item in delegated:
        if item.status in {"waiting_for_approval", "launching", "running"}:
            return f"{item.runtime_id} delegated lane {item.status.replace('_', ' ')}"
    if delegated:
        latest = delegated[-1]
        return f"{latest.runtime_id} delegated lane {latest.status.replace('_', ' ')}"
    return f"{mission.runtime_id} primary lane {mission.state.status.replace('_', ' ')}"


def _inspect_workspace_git(
    workspace_root: Path,
    commit_message_style: str = "scoped",
) -> dict:
    snapshot = {
        "repoDetected": False,
        "branch": "",
        "trackingBranch": "",
        "dirty": False,
        "stagedCount": 0,
        "unstagedCount": 0,
        "untrackedCount": 0,
        "ahead": 0,
        "behind": 0,
        "changedFiles": [],
        "suggestedCommitMessage": "",
        "remotes": [],
        "deployTarget": {
            "provider": "",
            "available": False,
            "configured": False,
            "requiresApproval": True,
            "detail": "No deploy target detected.",
        },
        "detail": "",
    }
    if not workspace_root.exists():
        snapshot["detail"] = "Workspace path does not exist."
        return snapshot

    git_probe = _run_git_command(workspace_root, ["rev-parse", "--is-inside-work-tree"])
    if git_probe["return_code"] != 0 or git_probe["stdout"].strip() != "true":
        snapshot["detail"] = "No Git repository detected for this workspace."
        return snapshot

    snapshot["repoDetected"] = True
    status_output = _run_git_command(workspace_root, ["status", "--porcelain=1", "--branch"])
    lines = [line for line in status_output["stdout"].splitlines() if line.strip()]
    if lines and lines[0].startswith("## "):
        snapshot.update(_parse_branch_status(lines[0][3:]))
        lines = lines[1:]

    for line in lines:
        code = line[:2]
        path_text = _parse_git_status_path(line)
        if path_text and path_text not in snapshot["changedFiles"]:
            snapshot["changedFiles"].append(path_text)
        if code.startswith("??"):
            snapshot["untrackedCount"] += 1
            continue
        if code[:1] not in {" ", "?"}:
            snapshot["stagedCount"] += 1
        if code[1:2] not in {" ", "?"}:
            snapshot["unstagedCount"] += 1
    snapshot["dirty"] = (
        snapshot["stagedCount"] > 0
        or snapshot["unstagedCount"] > 0
        or snapshot["untrackedCount"] > 0
    )

    remotes = []
    remotes_output = _run_git_command(workspace_root, ["remote", "-v"])
    seen = set()
    for line in remotes_output["stdout"].splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        name, url, kind = parts[0], parts[1], parts[2].strip("()")
        key = (name, url)
        if kind != "push" or key in seen:
            continue
        seen.add(key)
        remotes.append({"name": name, "url": url})
    snapshot["remotes"] = remotes
    snapshot["deployTarget"] = _infer_deploy_target(workspace_root, remotes)
    snapshot["detail"] = (
        f"{snapshot['branch'] or 'Detached HEAD'} · "
        f"{'dirty' if snapshot['dirty'] else 'clean'} · "
        f"{len(remotes)} remote(s)"
    )
    snapshot["suggestedCommitMessage"] = _build_generated_commit_message(
        snapshot,
        commit_message_style,
    )
    return snapshot


def _run_git_command(workspace_root: Path, args: list[str]) -> dict:
    try:
        completed = subprocess.run(  # noqa: S603
            ["git", *args],
            cwd=str(workspace_root),
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except OSError:
        return {"return_code": 1, "stdout": "", "stderr": "git unavailable"}
    return {
        "return_code": completed.returncode,
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
    }


def _parse_branch_status(branch_line: str) -> dict:
    branch = branch_line
    tracking = ""
    ahead = 0
    behind = 0
    if "..." in branch_line:
        branch, rest = branch_line.split("...", 1)
        tracking = rest.split(" [", 1)[0].strip()
    match = re.search(r"\[(.*?)\]$", branch_line)
    if match:
        parts = [item.strip() for item in match.group(1).split(",")]
        for part in parts:
            if part.startswith("ahead "):
                ahead = int(part.split(" ", 1)[1])
            elif part.startswith("behind "):
                behind = int(part.split(" ", 1)[1])
    return {
        "branch": branch.strip(),
        "trackingBranch": tracking,
        "ahead": ahead,
        "behind": behind,
    }


def _parse_git_status_path(line: str) -> str:
    payload = line[3:].strip()
    if " -> " in payload:
        payload = payload.split(" -> ", 1)[1].strip()
    return payload


def _normalize_commit_subject_token(value: str) -> str:
    cleaned = re.sub(r"[_\-]+", " ", value)
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def _build_generated_commit_message(
    git_snapshot: dict,
    style: str = "scoped",
) -> str:
    if not git_snapshot.get("dirty"):
        return ""
    changed_files = git_snapshot.get("changedFiles", [])
    labels: list[str] = []
    for path_text in changed_files[:4]:
        path = Path(path_text)
        token = _normalize_commit_subject_token(path.stem or path.name or path_text)
        if token and token not in labels:
            labels.append(token)
    normalized_style = (style or "scoped").strip().lower()
    if normalized_style == "concise":
        if labels:
            return f"Update {labels[0]}"
        return "Update workspace state"
    if normalized_style == "detailed":
        branch = git_snapshot.get("branch") or "workspace"
        if len(labels) == 1:
            return f"Update {labels[0]} on {branch}"
        if len(labels) == 2:
            return f"Update {labels[0]} and {labels[1]} on {branch}"
        if len(labels) >= 3:
            return f"Update {labels[0]}, {labels[1]}, and related files on {branch}"
        return f"Update workspace state on {branch}"
    if len(labels) == 1:
        return f"Update {labels[0]}"
    if len(labels) == 2:
        return f"Update {labels[0]} and {labels[1]}"
    if len(labels) >= 3:
        return f"Update {labels[0]}, {labels[1]}, and related files"
    return "Update workspace state"


def _infer_deploy_target(
    workspace_root: Path,
    remotes: list[dict],
) -> dict:
    remote_urls = [item["url"] for item in remotes]
    github_remote = next((url for url in remote_urls if "github.com" in url.lower()), "")
    pages_workflow = workspace_root / ".github" / "workflows"
    has_pages_workflow = pages_workflow.exists() and any(
        "pages" in child.name.lower() for child in pages_workflow.glob("*.y*ml")
    )
    if github_remote:
        return {
            "provider": "github_pages",
            "available": True,
            "configured": has_pages_workflow,
            "requiresApproval": True,
            "detail": (
                "GitHub remote detected. Offer approval-gated push or Pages deployment actions."
                if has_pages_workflow
                else "GitHub remote detected. Pages can be scaffolded after explicit approval."
            ),
        }
    return {
        "provider": "",
        "available": False,
        "configured": False,
        "requiresApproval": True,
        "detail": "No GitHub remote detected yet.",
    }


def _build_git_actions(git_snapshot: dict, profile_parameters: dict) -> list[dict]:
    if not git_snapshot.get("repoDetected"):
        return []
    approval_required = profile_parameters.get("gitActionPolicy", "approval_gated") != "profile_resolved"
    tracking_branch = str(git_snapshot.get("trackingBranch") or "").strip()
    ahead = int(git_snapshot.get("ahead") or 0)
    behind = int(git_snapshot.get("behind") or 0)
    suggested_commit_message = str(
        git_snapshot.get("suggestedCommitMessage") or "Update workspace state"
    ).replace('"', "")
    actions = [
        {
            "actionId": "inspect_repo_state",
            "label": "Inspect repository state",
            "command": "git status --short --branch",
            "commandSurface": "git.inspect",
            "requiresApproval": False,
            "detail": "Review branch, changes, and ahead/behind before mutating actions.",
        }
    ]
    if tracking_branch:
        detail = f"Fast-forward only pull from {tracking_branch}."
        if behind > 0:
            detail = f"{behind} remote commit(s) are waiting on {tracking_branch}. Pull fast-forward only."
        elif ahead > 0:
            detail = (
                f"Branch is ahead of {tracking_branch}. Pull stays fast-forward only before pushing."
            )
        actions.append(
            {
                "actionId": "pull_branch",
                "label": "Pull tracked branch",
                "command": "git pull --ff-only",
                "commandSurface": "git.pull",
                "requiresApproval": approval_required,
                "detail": detail,
            }
        )
    if git_snapshot.get("dirty"):
        actions.append(
            {
                "actionId": "commit_changes",
                "label": "Commit with generated message",
                "command": f'git add -A && git commit -m "{suggested_commit_message}"',
                "commandSurface": "git.commit",
                "requiresApproval": True,
                "detail": (
                    f'Fluxio stages all current changes and commits them with "{suggested_commit_message}".'
                ),
                "generatedMessage": suggested_commit_message,
            }
        )
    if git_snapshot.get("remotes"):
        actions.append(
            {
                "actionId": "push_branch",
                "label": "Push current branch",
                "command": "git push",
                "commandSurface": "git.push",
                "requiresApproval": approval_required,
                "detail": "Policy-resolved push action. Approval stays on by default.",
            }
        )
    deploy_target = git_snapshot.get("deployTarget", {})
    if deploy_target.get("available"):
        actions.append(
            {
                "actionId": "deploy_pages",
                "label": "Publish deploy target",
                "command": "git push origin HEAD",
                "commandSurface": "deploy.pages",
                "requiresApproval": True,
                "detail": deploy_target.get("detail", "Deploy target is available."),
            }
        )
    return actions


def _build_validation_actions(workspace_root: Path) -> list[dict]:
    verification_commands = detect_default_verification_commands(workspace_root)
    if not verification_commands:
        return []
    joined_command = " && ".join(verification_commands)
    detail = (
        verification_commands[0]
        if len(verification_commands) == 1
        else f"{verification_commands[0]} then {len(verification_commands) - 1} more verification command(s)."
    )
    return [
        {
            "actionId": "validate_workspace",
            "label": "Validate workspace",
            "command": joined_command,
            "commandSurface": "validate.workspace",
            "requiresApproval": False,
            "detail": f"Run detected verification commands: {detail}",
            "commands": verification_commands,
        }
    ]


def _build_workspace_service_management(
    *,
    setup_health: dict,
    runtime_status: dict | None,
    integration_recommendations: list[dict],
    connected_apps: list[dict],
) -> list[dict]:
    services = {
        item["serviceId"]: dict(item)
        for item in setup_health.get("serviceManagement", [])
        if isinstance(item, dict) and item.get("serviceId")
    }

    if runtime_status:
        runtime_id = runtime_status.get("runtime_id", "")
        existing = services.get(runtime_id, {})
        services[runtime_id] = {
            **existing,
            "serviceId": runtime_id,
            "label": runtime_status.get("label", runtime_id),
            "serviceCategory": "runtime",
            "installSource": existing.get("installSource", "system_path"),
            "currentHealthStatus": (
                "update_available"
                if runtime_status.get("update_available")
                else ("healthy" if runtime_status.get("detected") else "missing")
            ),
            "lastVerificationResult": (
                "outdated"
                if runtime_status.get("update_available")
                else ("passed" if runtime_status.get("detected") else "blocked")
            ),
            "lastRepairAction": existing.get("lastRepairAction", {}),
            "managementMode": existing.get("managementMode", "externally_managed"),
            "version": runtime_status.get("version") or existing.get("version", ""),
            "latestVersion": runtime_status.get("latest_version") or existing.get("latestVersion", ""),
            "updateAvailable": runtime_status.get("update_available", existing.get("updateAvailable", False)),
            "details": runtime_status.get("doctor_summary") or existing.get("details", ""),
            "serviceActions": existing.get("serviceActions", []),
            "verifyAction": existing.get("verifyAction", {}),
        }

    for item in integration_recommendations:
        recommendation_id = item.get("recommendation_id", "")
        if not recommendation_id:
            continue
        services[recommendation_id] = {
            "serviceId": recommendation_id,
            "label": item.get("label", recommendation_id),
            "serviceCategory": "mcp_tool_server",
            "installSource": item.get("command", ""),
            "currentHealthStatus": "recommended",
            "lastVerificationResult": "not_run",
            "lastRepairAction": {},
            "managementMode": "fluxio_managed",
            "version": "",
            "details": item.get("reason", ""),
            "serviceActions": [],
            "verifyAction": {},
        }

    for session in connected_apps:
        app_id = session.get("app_id", "")
        if not app_id:
            continue
        services[app_id] = {
            "serviceId": app_id,
            "label": session.get("app_name", app_id),
            "serviceCategory": "connected_app_bridge",
            "installSource": session.get("bridge_transport", "") or "bridge_manifest",
            "currentHealthStatus": session.get("bridge_health", session.get("status", "unknown")),
            "lastVerificationResult": (
                "passed" if session.get("status") == "connected" else session.get("status", "unknown")
            ),
            "lastRepairAction": {},
            "managementMode": "externally_managed",
            "version": "",
            "details": session.get("latest_task_result", {}).get("resultSummary", ""),
            "serviceActions": [],
            "verifyAction": {},
        }

    return list(services.values())


def _service_management_summary(items: list[dict]) -> dict[str, int]:
    healthy_statuses = {"healthy", "connected", "ready"}
    return {
        "totalItems": len(items),
        "healthyCount": sum(
            1 for item in items if item.get("currentHealthStatus") in healthy_statuses
        ),
        "needsAttentionCount": sum(
            1 for item in items if item.get("currentHealthStatus") not in healthy_statuses
        ),
        "runtimeCount": sum(1 for item in items if item.get("serviceCategory") == "runtime"),
        "toolServerCount": sum(
            1 for item in items if item.get("serviceCategory") == "mcp_tool_server"
        ),
        "bridgeCount": sum(
            1 for item in items if item.get("serviceCategory") == "connected_app_bridge"
        ),
    }


def _default_workflow_verification(selected_workspace: dict) -> list[str]:
    workspace_type = selected_workspace.get("workspace_type", "")
    commands: list[str] = []
    if "python" in workspace_type:
        commands.append("python -m pytest tests -q")
    if "node" in workspace_type or "tauri" in workspace_type or "web" in workspace_type:
        commands.append("npm run frontend:build")
    if "tauri" in workspace_type:
        commands.append("npm run tauri build -- --debug")
    return commands


def _build_workflow_studio(
    workspaces: list[dict],
    missions: list[dict],
    setup_health: dict,
    skill_catalog: dict,
) -> dict:
    selected_workspace = workspaces[0] if workspaces else {}
    git_snapshot = selected_workspace.get("gitSnapshot", {})
    verification_defaults = _default_workflow_verification(selected_workspace)
    recommended_skill_ids = [
        item.get("packId") or item.get("pack_id") or item.get("skillId") or item.get("skill_id")
        for item in skill_catalog.get("recommendedPacks", [])
        if item.get("packId") or item.get("pack_id") or item.get("skillId") or item.get("skill_id")
    ]
    managed_service_ids = [
        item.get("serviceId")
        for item in selected_workspace.get("serviceManagement", [])
        if item.get("managementMode") == "fluxio_managed" and item.get("serviceId")
    ]
    setup_blockers = [
        item.get("serviceId")
        for item in setup_health.get("serviceManagement", [])
        if item.get("currentHealthStatus") != "healthy" and item.get("serviceId")
    ]
    recipes = [
        {
            "workflowId": "agent_long_run",
            "label": "Long-Run Agent Session",
            "description": "Leave Fluxio to plan, execute, verify, and replan over many hours with approvals and proof kept visible.",
            "status": "ready" if missions else "available",
            "audience": "all",
            "surface": "agent_view",
            "reviewStatus": "reviewed",
            "runtimeChoice": selected_workspace.get("default_runtime", "openclaw_or_hermes"),
            "skillIds": recommended_skill_ids[:3],
            "serviceIds": managed_service_ids[:4],
            "verificationDefaults": verification_defaults,
        },
        {
            "workflowId": "ui_review_loop",
            "label": "Live UI Review Loop",
            "description": "Use HMR, fixtures, proof, and replay-ready states while refining the desktop workbench.",
            "status": "ready" if selected_workspace else "available",
            "audience": "builder",
            "surface": "builder_view",
            "reviewStatus": "reviewed",
            "runtimeChoice": selected_workspace.get("default_runtime", "openclaw"),
            "skillIds": recommended_skill_ids[:2],
            "serviceIds": [
                item.get("serviceId")
                for item in selected_workspace.get("serviceManagement", [])
                if item.get("serviceCategory") in {"mcp_tool_server", "runtime"}
            ][:4],
            "verificationDefaults": verification_defaults,
        },
        {
            "workflowId": "safe_git_push",
            "label": "Safe Push Or Deploy",
            "description": "Inspect repo truth first, then offer profile-resolved push and GitHub Pages actions with approvals.",
            "status": "ready" if git_snapshot.get("repoDetected") else "blocked",
            "audience": "advanced",
            "surface": "builder_view",
            "reviewStatus": "reviewed",
            "runtimeChoice": selected_workspace.get("default_runtime", "openclaw"),
            "skillIds": recommended_skill_ids[:1],
            "serviceIds": managed_service_ids[:2],
            "verificationDefaults": verification_defaults,
        },
        {
            "workflowId": "skill_authoring",
            "label": "Skill And Workflow Authoring",
            "description": "Create a new skill or workflow recipe, test it locally, and keep it reviewable inside Fluxio.",
            "status": "ready" if selected_workspace else "available",
            "audience": "builder",
            "surface": "skill_studio",
            "reviewStatus": "reviewed",
            "runtimeChoice": selected_workspace.get("default_runtime", "openclaw"),
            "skillIds": [
                skill_id
                for skill_id in [
                    item.get("skillId") or item.get("skill_id") or item.get("packId")
                    for item in (
                        skill_catalog.get("userInstalledSkills", [])[:2]
                        + skill_catalog.get("learnedSkills", [])[:2]
                    )
                ]
                if skill_id
            ],
            "serviceIds": managed_service_ids[:3],
            "verificationDefaults": verification_defaults,
        },
        {
            "workflowId": "setup_repair",
            "label": "Installer-Grade Setup Repair",
            "description": "Detect missing dependencies, explain blockers, and guide repair actions from inside the app.",
            "status": "blocked" if setup_health.get("missingDependencies") else "ready",
            "audience": "beginner",
            "surface": "setup",
            "reviewStatus": "reviewed",
            "runtimeChoice": selected_workspace.get("default_runtime", "openclaw"),
            "skillIds": [],
            "serviceIds": setup_blockers[:4],
            "verificationDefaults": verification_defaults,
        },
    ]
    learning_queue = []
    for mission in missions:
        for item in mission.get("missionLoop", {}).get("improvementQueue", []):
            learning_queue.append(item)
    return {
        "recipes": recipes,
        "learningQueue": learning_queue[:6],
        "recommendedMode": "agent",
        "managementSummary": {
            "recipeCount": len(recipes),
            "reviewedCount": sum(1 for item in recipes if item.get("reviewStatus") == "reviewed"),
            "blockedCount": sum(1 for item in recipes if item.get("status") == "blocked"),
        },
    }


def detect_workspace_type(root: Path) -> str:
    root = root.resolve()
    if (root / "src-tauri").exists() and (root / "pyproject.toml").exists():
        return "tauri-python"
    if (root / "package.json").exists() and (root / "public").exists():
        return "web-node"
    if (root / "pyproject.toml").exists():
        return "python"
    if (root / "package.json").exists():
        return "node"
    return "general"


def recommend_skills(
    workspace_type: str, runtime_id: str
) -> list[SkillRecommendation]:
    recommendations = [
        SkillRecommendation(
            recommendation_id="repo_scan",
            label="Repo Scan",
            reason="Ground each mission in real workspace structure before delegating.",
            runtime_id=runtime_id,
            workspace_type=workspace_type,
            enabled_by_default=True,
        )
    ]
    if "python" in workspace_type:
        recommendations.append(
            SkillRecommendation(
                recommendation_id="python_verification",
                label="Python Verification",
                reason="Keep pytest and packaging checks visible in completion proof.",
                runtime_id=runtime_id,
                workspace_type=workspace_type,
            )
        )
    if "node" in workspace_type or "web" in workspace_type or "tauri" in workspace_type:
        recommendations.append(
            SkillRecommendation(
                recommendation_id="frontend_proof",
                label="Frontend Proof",
                reason="Track UI regressions and live run output for mission proof.",
                runtime_id=runtime_id,
                workspace_type=workspace_type,
            )
        )
    return recommendations


def recommend_integrations(
    workspace_type: str, runtime_id: str
) -> list[IntegrationRecommendation]:
    recommendations = [
        IntegrationRecommendation(
            recommendation_id="filesystem_mcp",
            label="Filesystem MCP",
            reason="Helps the agent inspect and summarize multiple projects safely.",
            command="npx @modelcontextprotocol/server-filesystem .",
            runtime_id=runtime_id,
            workspace_type=workspace_type,
            enabled_by_default=True,
        ),
        IntegrationRecommendation(
            recommendation_id="git_mcp",
            label="Git MCP",
            reason="Exposes repo status and history to the agent without custom glue.",
            command="uvx mcp-server-git",
            runtime_id=runtime_id,
            workspace_type=workspace_type,
        ),
    ]
    if "web" in workspace_type or "tauri" in workspace_type:
        recommendations.append(
            IntegrationRecommendation(
                recommendation_id="playwright_mcp",
                label="Playwright MCP",
                reason="Useful for proof screenshots, smoke tests, and non-technical validation.",
                command="npx @playwright/mcp@latest",
                runtime_id=runtime_id,
                workspace_type=workspace_type,
            )
        )
    return recommendations


def mission_mode_to_engine_mode(mode: str) -> str:
    mapping = {
        "focus": "fast",
        "autopilot": "autopilot",
        "deep run": "deep_run",
        "research": "swarms",
    }
    return mapping.get(mode.strip().lower(), "autopilot")


def default_docs_for_workspace(root: Path) -> list[str]:
    candidates = ["docs/PRD.md", "docs/ROADMAP.md", "README.md"]
    return [path for path in candidates if (root / path).exists()]


def build_escalation_preview(mission: Mission) -> str:
    proof_summary = mission.proof.summary or mission.objective
    if mission.state.status == "completed":
        return f"Mission complete: {proof_summary}"
    if mission.state.status == "verification_failed":
        failures = ", ".join(mission.state.verification_failures) or "verification failed"
        return f"Mission needs input: {failures}"
    if mission.state.status == "blocked":
        blocked = ", ".join(mission.proof.blocked_by) or "setup or approval is blocking progress"
        return f"Mission blocked: {blocked}"
    if mission.state.status == "needs_approval":
        return f"Approval needed: {proof_summary}"
    return f"Mission update: {proof_summary}"


def _mission_title(objective: str) -> str:
    cleaned = re.sub(r"\s+", " ", objective or "").strip()
    if not cleaned:
        return "New Mission"
    cleaned = re.split(r"[\n.!?]", cleaned, maxsplit=1)[0].strip()
    for pattern in MISSION_TITLE_PREFIXES:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9+./_-]*", cleaned)
    if not tokens:
        return "New Mission"
    title_tokens: list[str] = []
    for index, token in enumerate(tokens):
        if index >= 2 and token.lower() in MISSION_TITLE_STOPWORDS:
            continue
        title_tokens.append(token)
        if len(title_tokens) >= 6:
            break
    if not title_tokens:
        title_tokens = tokens[:6]
    first = title_tokens[0]
    if first and not first[:1].isupper():
        title_tokens[0] = f"{first[:1].upper()}{first[1:]}"
    return " ".join(title_tokens)


def _age_seconds(value: str) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(int((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()), 0)


def _percent(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return int(round((numerator / denominator) * 100))


def _load_json_file(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _verify_desktop_script_contract(root: Path) -> tuple[bool, str]:
    package_path = root / "package.json"
    payload = _load_json_file(package_path)
    if not isinstance(payload, dict):
        return False, "package.json is missing or unreadable."
    scripts = payload.get("scripts", {})
    if not isinstance(scripts, dict):
        return False, "package.json has no scripts section."
    command = str(scripts.get("verify:desktop", "")).strip()
    required_snippets = (
        "python -m pytest tests -q",
        "npm run frontend:build",
        "npm run tauri build -- --debug",
    )
    missing = [snippet for snippet in required_snippets if snippet not in command]
    if missing:
        return False, "verify:desktop is missing required stages."
    return True, "verify:desktop includes pytest, frontend build, and Tauri build."


def _verify_frontend_source_alignment(root: Path) -> tuple[bool, str]:
    required_paths = [
        root / "t3code" / "apps" / "web" / "src" / "main.tsx",
        root / "t3code" / "apps" / "web" / "src" / "fluxio" / "FluxioApp.tsx",
        root / "t3code" / "apps" / "web" / "src" / "fluxio" / "fluxioBridge.ts",
    ]
    if any(not path.exists() for path in required_paths):
        return False, "t3code frontend entrypoint files are missing."

    vite_path = root / "vite.config.mjs"
    tauri_path = root / "src-tauri" / "tauri.conf.json"
    if not vite_path.exists() or not tauri_path.exists():
        return False, "Vite or Tauri desktop config is missing."
    vite_text = vite_path.read_text(encoding="utf-8")
    if not _vite_targets_t3_web(vite_text):
        return False, "vite.config.mjs is not aligned with t3code/apps/web."

    tauri_payload = _load_json_file(tauri_path)
    if not isinstance(tauri_payload, dict):
        return False, "src-tauri/tauri.conf.json is unreadable."
    frontend_dist = (
        str(tauri_payload.get("build", {}).get("frontendDist", ""))
        .replace("\\", "/")
        .strip()
    )
    if "t3code/apps/web/dist" not in frontend_dist:
        return False, "src-tauri/tauri.conf.json is not aligned with t3code/apps/web/dist."
    return True, "Frontend source-of-truth is aligned to t3code/apps/web."


def _vite_targets_t3_web(vite_text: str) -> bool:
    normalized = vite_text.replace("\\", "/")
    if "t3code/apps/web" in normalized:
        return True

    for match in re.finditer(
        r"const\s+([A-Za-z_]\w*)\s*=\s*resolve\(([^)]*)\)",
        normalized,
        flags=re.DOTALL,
    ):
        variable_name = match.group(1)
        args = match.group(2)
        if not (
            re.search(r"['\"]t3code['\"]", args)
            and re.search(r"['\"]apps['\"]", args)
            and re.search(r"['\"]web['\"]", args)
        ):
            continue
        root_refs_variable = re.search(
            rf"\broot\s*:\s*{re.escape(variable_name)}\b",
            normalized,
        )
        if root_refs_variable:
            return True
    return False


def _release_quality_score(
    *,
    completion_rate: int,
    delegated_run_rate: int,
    resume_run_rate: int,
    resume_completion_rate: int,
    verification_pause_rate: int,
) -> int:
    resume_component = resume_completion_rate if resume_run_rate > 0 else 50
    values = [
        max(0, min(completion_rate, 100)),
        max(0, min(delegated_run_rate * 2, 100)),
        max(0, min(resume_component, 100)),
        max(0, min(100 - verification_pause_rate, 100)),
    ]
    return int(round(sum(values) / len(values)))


def _build_proving_cycle_readiness(root: Path) -> dict:
    payload = _load_json_file(root / ".agent_control" / "missions.json")
    missions = payload if isinstance(payload, list) else []
    runtime_counts = {
        "openclaw": 0,
        "hermes": 0,
    }
    completed_counts = {
        "openclaw": 0,
        "hermes": 0,
    }
    approval_wait_seen = False
    delegated_active_seen = False

    for mission in missions:
        if not isinstance(mission, dict):
            continue
        runtime_id = str(mission.get("runtime_id", "")).strip().lower()
        state = mission.get("state", {})
        if not isinstance(state, dict):
            state = {}
        status = str(state.get("status", "")).strip().lower()
        continuity_state = str(state.get("continuity_state", "")).strip().lower()
        time_budget_status = str(state.get("time_budget_status", "")).strip().lower()
        stop_reason = str(state.get("stop_reason", "")).strip().lower()
        runtime_lane = str(state.get("current_runtime_lane", "")).strip().lower()
        escalation_policy = mission.get("escalation_policy", {})
        if not isinstance(escalation_policy, dict):
            escalation_policy = {}
        pending_approval_count = int(escalation_policy.get("pending_count", 0) or 0)
        delegated_sessions = state.get("delegated_runtime_sessions")
        if not isinstance(delegated_sessions, list):
            delegated_sessions = mission.get("delegated_runtime_sessions", [])
        delegated_session_statuses = {
            str(item.get("status", "")).strip().lower()
            for item in delegated_sessions
            if isinstance(item, dict)
        }
        if runtime_id in runtime_counts:
            runtime_counts[runtime_id] += 1
            if status == "completed":
                completed_counts[runtime_id] += 1
        if runtime_id == "hermes" and (
            status == "needs_approval"
            or continuity_state == "approval_waiting"
            or pending_approval_count > 0
            or "waiting_for_approval" in delegated_session_statuses
        ):
            approval_wait_seen = True
        if (
            continuity_state == "delegated_active"
            or time_budget_status == "delegated_active"
            or stop_reason == "delegated_runtime_running"
            or any(
                status_name in {"launching", "running", "waiting_for_approval"}
                for status_name in delegated_session_statuses
            )
            or (
                "delegated lane" in runtime_lane
                and any(token in runtime_lane for token in ("launching", "running", "waiting"))
            )
        ):
            delegated_active_seen = True

    proofs = [
        {
            "proofId": "openclaw_proving_mission",
            "label": "OpenClaw proving mission completed",
            "passed": completed_counts["openclaw"] > 0,
            "details": f"Completed OpenClaw missions: {completed_counts['openclaw']}.",
        },
        {
            "proofId": "hermes_delegated_mission",
            "label": "Hermes delegated mission completed",
            "passed": completed_counts["hermes"] > 0,
            "details": f"Completed Hermes missions: {completed_counts['hermes']}.",
        },
        {
            "proofId": "approval_wait_evidence",
            "label": "Hermes approval-wait evidence recorded",
            "passed": approval_wait_seen,
            "details": (
                "At least one Hermes mission recorded `needs_approval` or `approval_waiting`."
                if approval_wait_seen
                else "No Hermes approval-wait state has been recorded yet."
            ),
        },
        {
            "proofId": "delegated_active_evidence",
            "label": "Delegated-active continuity evidence recorded",
            "passed": delegated_active_seen,
            "details": (
                "At least one mission recorded `delegated_active` continuity."
                if delegated_active_seen
                else "No delegated-active continuity state has been recorded yet."
            ),
        },
    ]
    missing = [item["label"] for item in proofs if not item["passed"]]
    next_actions = [f"Capture proof: {label}." for label in missing]
    return {
        "missionCount": len(missions),
        "runtimeMissionCounts": runtime_counts,
        "runtimeCompletionCounts": completed_counts,
        "proofs": proofs,
        "missingProofs": missing,
        "ready": not missing,
        "nextActions": next_actions[:4],
    }


def build_release_readiness_snapshot(
    root: Path,
    *,
    onboarding: dict | None = None,
    setup_health: dict | None = None,
    harness_lab: dict | None = None,
) -> dict:
    root = root.resolve()
    onboarding_payload = onboarding or detect_onboarding_status(root)
    setup_health_payload = setup_health or onboarding_payload.get("setupHealth", {})
    harness_lab_payload = harness_lab or build_harness_lab_snapshot(root)
    proving_cycle = _build_proving_cycle_readiness(root)

    checks = onboarding_payload.get("checks", {})
    service_summary = setup_health_payload.get("serviceManagementSummary", {})
    efficiency = harness_lab_payload.get("efficiency", {})
    session_health = harness_lab_payload.get("sessionHealth", {})

    verify_desktop_ok, verify_desktop_detail = _verify_desktop_script_contract(root)
    frontend_alignment_ok, frontend_alignment_detail = _verify_frontend_source_alignment(root)
    required_total_items = int(service_summary.get("totalItems", 0) or 0)
    required_healthy_count = int(service_summary.get("healthyCount", 0) or 0)
    completion_rate = int(efficiency.get("completionRate", 0) or 0)
    delegated_run_rate = int(efficiency.get("delegatedRunRate", 0) or 0)
    resume_run_rate = int(efficiency.get("resumeRunRate", 0) or 0)
    resume_completion_rate = int(efficiency.get("resumeCompletionRate", 0) or 0)
    verification_pause_rate = int(efficiency.get("verificationPauseRate", 0) or 0)
    stale_heartbeat_count = int(session_health.get("staleHeartbeatCount", 0) or 0)

    required_gates = [
        {
            "gateId": "verify_desktop_contract",
            "label": "verify:desktop contract",
            "required": True,
            "passed": verify_desktop_ok,
            "details": verify_desktop_detail,
        },
        {
            "gateId": "frontend_source_alignment",
            "label": "frontend source alignment",
            "required": True,
            "passed": frontend_alignment_ok,
            "details": frontend_alignment_detail,
        },
        {
            "gateId": "uv_installed",
            "label": "uv installed",
            "required": True,
            "passed": bool(checks.get("uv", {}).get("installed")),
            "details": str(checks.get("uv", {}).get("details", "")),
        },
        {
            "gateId": "openclaw_installed",
            "label": "OpenClaw installed",
            "required": True,
            "passed": bool(checks.get("openclaw", {}).get("installed")),
            "details": str(checks.get("openclaw", {}).get("details", "")),
        },
        {
            "gateId": "hermes_installed",
            "label": "Hermes installed",
            "required": True,
            "passed": bool(checks.get("hermes", {}).get("installed")),
            "details": str(checks.get("hermes", {}).get("details", "")),
        },
        {
            "gateId": "setup_required_services_healthy",
            "label": "required setup services healthy",
            "required": True,
            "passed": required_total_items > 0 and required_healthy_count == required_total_items,
            "details": f"{required_healthy_count}/{required_total_items} required setup services are healthy.",
        },
        {
            "gateId": "runtime_heartbeat_stable",
            "label": "delegated heartbeat stable",
            "required": True,
            "passed": stale_heartbeat_count == 0,
            "details": (
                "No stale delegated runtime heartbeat detected."
                if stale_heartbeat_count == 0
                else f"{stale_heartbeat_count} delegated runtime session(s) have stale heartbeat."
            ),
        },
    ]
    optional_signals = [
        {
            "gateId": "completion_rate",
            "label": "recent completion rate >= 50%",
            "required": False,
            "passed": completion_rate >= 50,
            "details": f"Current completion rate is {completion_rate}%.",
        },
        {
            "gateId": "delegated_run_rate",
            "label": "delegated run rate >= 20%",
            "required": False,
            "passed": delegated_run_rate >= 20,
            "details": f"Current delegated run rate is {delegated_run_rate}%.",
        },
        {
            "gateId": "resume_completion_rate",
            "label": "resume completion rate >= 60%",
            "required": False,
            "passed": resume_run_rate == 0 or resume_completion_rate >= 60,
            "details": (
                "No resumed runs recorded yet."
                if resume_run_rate == 0
                else f"Current resume completion rate is {resume_completion_rate}%."
            ),
        },
        {
            "gateId": "proof_openclaw_completed",
            "label": "OpenClaw proving mission evidence",
            "required": False,
            "passed": bool(
                next(
                    (
                        item.get("passed", False)
                        for item in proving_cycle.get("proofs", [])
                        if item.get("proofId") == "openclaw_proving_mission"
                    ),
                    False,
                )
            ),
            "details": str(
                next(
                    (
                        item.get("details", "")
                        for item in proving_cycle.get("proofs", [])
                        if item.get("proofId") == "openclaw_proving_mission"
                    ),
                    "",
                )
            ),
        },
        {
            "gateId": "proof_hermes_completed",
            "label": "Hermes delegated mission evidence",
            "required": False,
            "passed": bool(
                next(
                    (
                        item.get("passed", False)
                        for item in proving_cycle.get("proofs", [])
                        if item.get("proofId") == "hermes_delegated_mission"
                    ),
                    False,
                )
            ),
            "details": str(
                next(
                    (
                        item.get("details", "")
                        for item in proving_cycle.get("proofs", [])
                        if item.get("proofId") == "hermes_delegated_mission"
                    ),
                    "",
                )
            ),
        },
    ]
    gates = required_gates + optional_signals
    required_passed = sum(1 for gate in required_gates if gate["passed"])
    required_total = len(required_gates)
    required_score = _percent(required_passed, required_total)
    quality_score = _release_quality_score(
        completion_rate=completion_rate,
        delegated_run_rate=delegated_run_rate,
        resume_run_rate=resume_run_rate,
        resume_completion_rate=resume_completion_rate,
        verification_pause_rate=verification_pause_rate,
    )
    overall_score = int(
        round(
            (required_score * RELEASE_READINESS_WEIGHTS["required"] / 100)
            + (quality_score * RELEASE_READINESS_WEIGHTS["quality"] / 100)
        )
    )

    if required_passed == required_total and overall_score >= 85:
        status = "ready_for_1_0_validation"
    elif required_passed == required_total:
        status = "validation_ready_with_quality_gaps"
    elif required_passed >= max(required_total - 1, 1):
        status = "close_but_blocked"
    else:
        status = "blocked"

    failed_required_actions = [
        f"{gate['label']}: {gate['details']}"
        for gate in required_gates
        if not gate["passed"]
    ]
    next_actions = (
        failed_required_actions
        + list(proving_cycle.get("nextActions", []))
        + list(onboarding_payload.get("nextActions", []))
    )
    return {
        "status": status,
        "score": overall_score,
        "requiredGateSummary": {
            "passed": required_passed,
            "total": required_total,
            "score": required_score,
        },
        "qualityScore": quality_score,
        "qualitySignals": {
            "completionRate": completion_rate,
            "delegatedRunRate": delegated_run_rate,
            "resumeRunRate": resume_run_rate,
            "resumeCompletionRate": resume_completion_rate,
            "verificationPauseRate": verification_pause_rate,
        },
        "proofReadiness": proving_cycle,
        "gates": gates,
        "nextActions": next_actions[:8],
        "calculatedAt": utc_now_iso(),
    }


def _build_runtime_session_health(root: Path) -> dict:
    runtime_root = root / ".agent_control" / "runtime_sessions"
    session_paths = sorted(
        runtime_root.glob("delegate_*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ) if runtime_root.exists() else []
    active_count = 0
    waiting_approval_count = 0
    healthy_heartbeat_count = 0
    stale_heartbeat_count = 0
    delegated_healthy_count = 0
    delegated_stale_count = 0
    latest_heartbeat_age_seconds: int | None = None
    latest_status = ""
    for path in session_paths[:16]:
        payload = _load_json_file(path)
        if not isinstance(payload, dict):
            continue
        status = str(payload.get("status", "unknown"))
        heartbeat_status = str(payload.get("heartbeat_status", "unknown"))
        heartbeat_age = payload.get("heartbeat_age_seconds")
        if heartbeat_age is None:
            heartbeat_age = _age_seconds(
                str(payload.get("heartbeat_at") or payload.get("updated_at") or "")
            )
        stale_after = max(int(payload.get("heartbeat_interval_seconds") or 10) * 3, 35)
        effective_heartbeat_status = heartbeat_status
        if status in {"launching", "running", "waiting_for_approval"} and heartbeat_age is not None:
            effective_heartbeat_status = (
                "stale" if heartbeat_age > stale_after else "healthy"
            )
        if heartbeat_age is not None and latest_heartbeat_age_seconds is None:
            latest_heartbeat_age_seconds = heartbeat_age
            latest_status = status
        if status in {"launching", "running", "waiting_for_approval"}:
            active_count += 1
        if status == "waiting_for_approval":
            waiting_approval_count += 1
        if effective_heartbeat_status == "healthy":
            healthy_heartbeat_count += 1
        elif effective_heartbeat_status == "stale":
            stale_heartbeat_count += 1
        if status in {"launching", "running", "waiting_for_approval"}:
            if effective_heartbeat_status == "healthy":
                delegated_healthy_count += 1
            elif effective_heartbeat_status == "stale":
                delegated_stale_count += 1
    delegated_total = delegated_healthy_count + delegated_stale_count
    return {
        "totalSessions": len(session_paths),
        "activeCount": active_count,
        "waitingApprovalCount": waiting_approval_count,
        "healthyHeartbeatCount": healthy_heartbeat_count,
        "staleHeartbeatCount": stale_heartbeat_count,
        "delegatedHealthyCount": delegated_healthy_count,
        "delegatedStaleCount": delegated_stale_count,
        "delegatedHealthyRate": _percent(delegated_healthy_count, delegated_total),
        "latestHeartbeatAgeSeconds": latest_heartbeat_age_seconds,
        "latestStatus": latest_status or "idle",
    }


def _harness_efficiency_recommendation(
    *,
    total_runs: int,
    completion_rate: int,
    delegated_run_rate: int,
    resume_run_rate: int,
    resume_completion_rate: int,
    approval_pause_rate: int,
    verification_pause_rate: int,
    stale_heartbeat_count: int,
) -> str:
    if total_runs == 0:
        return (
            "No local harness runs are recorded yet. Start one real mission to measure "
            "pause friction, delegated session health, and verification efficiency."
        )
    if stale_heartbeat_count > 0:
        return (
            "Delegated runtime heartbeat went stale recently. Verify runtime health "
            "before widening unattended autonomy."
        )
    if delegated_run_rate < 20 and total_runs >= 4:
        return (
            "Delegated runtime usage is still low in recent runs. Run more real delegated "
            "missions before claiming long-run readiness."
        )
    if resume_run_rate >= 20 and resume_completion_rate < 60:
        return (
            "Resume continuity is still weak after restart. Improve resume completion "
            "before expanding unattended missions."
        )
    if completion_rate < 50:
        return (
            "Completion rate is below 50% on recent runs. Stabilize runtime and verification "
            "before widening autonomy."
        )
    if approval_pause_rate >= 35:
        return (
            "Approval waits dominate recent runs. Keep the hybrid harness, but reduce "
            "unnecessary approval pressure before widening delegation."
        )
    if verification_pause_rate >= 25:
        return (
            "Verification failures are the main pause source. Improve verification "
            "defaults before increasing autonomy."
        )
    return (
        "Fluxio hybrid looks stable on recent local runs. Keep it as production and "
        "use the legacy harness only as a benchmark."
    )


def build_harness_lab_snapshot(root: Path) -> dict:
    runs_root = root / ".agent_runs"
    sessions = sorted(
        [path for path in runs_root.glob("session_*") if path.is_dir()],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    recent_runs: list[dict] = []
    harness_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    pause_reason_counts: dict[str, int] = {}
    delegated_run_count = 0
    delegated_failure_run_count = 0
    runtime_budget_pause_count = 0
    delegated_active_pause_count = 0
    resumed_run_count = 0
    resumed_completed_count = 0
    approval_resolved_run_count = 0
    approval_rejected_run_count = 0
    verification_failure_total = 0
    action_count_total = 0
    for session in sessions[:HARNESS_RECENT_RUN_LIMIT]:
        state_path = session / "state.json"
        if not state_path.exists():
            continue
        payload = _load_json_file(state_path)
        if not isinstance(payload, dict):
            continue
        harness_id = payload.get("harness_id", "legacy_autonomous_engine")
        status = str(payload.get("autopilot_status", "unknown"))
        pause_reason = str(payload.get("autopilot_pause_reason", "none") or "none")
        delegated_sessions = payload.get("delegated_runtime_sessions", [])
        if not isinstance(delegated_sessions, list):
            delegated_sessions = []
        delegated_session_count = len(delegated_sessions)
        verification_failures = len(payload.get("verification_failures", []))
        action_count = len(payload.get("action_history", []))
        metadata = _load_json_file(session / "metadata.json")
        parent_session_id = (
            str(metadata.get("parent_session_id", "")).strip()
            if isinstance(metadata, dict)
            else ""
        )
        harness_counts[harness_id] = harness_counts.get(harness_id, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
        pause_reason_counts[pause_reason] = pause_reason_counts.get(pause_reason, 0) + 1
        if delegated_session_count:
            delegated_run_count += 1
            if status == "failed" or any(
                str(item.get("status", "")) in {"failed", "stopped"}
                for item in delegated_sessions
                if isinstance(item, dict)
            ):
                delegated_failure_run_count += 1
            approval_decisions = {
                str(entry.get("status", ""))
                for item in delegated_sessions
                if isinstance(item, dict)
                for entry in item.get("approval_history", [])
                if isinstance(entry, dict)
            }
            if "approved" in approval_decisions:
                approval_resolved_run_count += 1
            if "rejected" in approval_decisions:
                approval_rejected_run_count += 1
        if pause_reason == "runtime_budget":
            runtime_budget_pause_count += 1
        if pause_reason == "delegated_runtime_running":
            delegated_active_pause_count += 1
        if parent_session_id:
            resumed_run_count += 1
            if status == "completed":
                resumed_completed_count += 1
        verification_failure_total += verification_failures
        action_count_total += action_count
        recent_runs.append(
            {
                "sessionId": session.name,
                "harnessId": harness_id,
                "runtimeId": payload.get("runtime_id", "openclaw"),
                "autopilotStatus": status,
                "pauseReason": pause_reason if pause_reason != "none" else "",
                "verificationFailures": verification_failures,
                "delegatedSessionCount": delegated_session_count,
                "resumedFromSessionId": parent_session_id,
                "actionCount": action_count,
            }
        )
    total_runs = len(recent_runs)
    completed_runs = status_counts.get("completed", 0)
    approval_pauses = pause_reason_counts.get("approval_required", 0)
    verification_pauses = pause_reason_counts.get("verification_failed", 0)
    completion_rate = _percent(completed_runs, total_runs)
    delegated_run_rate = _percent(delegated_run_count, total_runs)
    resume_run_rate = _percent(resumed_run_count, total_runs)
    resume_completion_rate = _percent(resumed_completed_count, resumed_run_count)
    approval_decision_total = approval_resolved_run_count + approval_rejected_run_count
    session_health = _build_runtime_session_health(root)
    recommendation = _harness_efficiency_recommendation(
        total_runs=total_runs,
        completion_rate=completion_rate,
        delegated_run_rate=delegated_run_rate,
        resume_run_rate=resume_run_rate,
        resume_completion_rate=resume_completion_rate,
        approval_pause_rate=_percent(approval_pauses, total_runs),
        verification_pause_rate=_percent(verification_pauses, total_runs),
        stale_heartbeat_count=int(session_health["staleHeartbeatCount"]),
    )
    return {
        "productionHarness": "fluxio_hybrid",
        "shadowCandidates": ["legacy_autonomous_engine"],
        "recentRuns": recent_runs,
        "harnessCounts": harness_counts,
        "statusCounts": status_counts,
        "pauseReasonCounts": pause_reason_counts,
        "efficiency": {
            "totalRuns": total_runs,
            "completedRuns": completed_runs,
            "completionRate": completion_rate,
            "approvalPauseRate": _percent(approval_pauses, total_runs),
            "verificationPauseRate": _percent(verification_pauses, total_runs),
            "delegatedRunRate": delegated_run_rate,
            "delegatedFailureRate": _percent(
                delegated_failure_run_count,
                delegated_run_count,
            ),
            "runtimeBudgetPauseRate": _percent(runtime_budget_pause_count, total_runs),
            "delegatedActivePauseRate": _percent(
                delegated_active_pause_count,
                total_runs,
            ),
            "resumeRunRate": resume_run_rate,
            "resumeCompletionRate": resume_completion_rate,
            "approvalRecoveryRate": _percent(
                approval_resolved_run_count,
                approval_decision_total,
            ),
            "averageActionsPerRun": round(action_count_total / total_runs, 1)
            if total_runs
            else 0.0,
            "averageVerificationFailures": round(
                verification_failure_total / total_runs, 1
            )
            if total_runs
            else 0.0,
        },
        "sessionHealth": session_health,
        "recommendation": recommendation,
    }
