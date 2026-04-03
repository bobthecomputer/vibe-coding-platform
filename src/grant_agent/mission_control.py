from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from pathlib import Path

from .models import (
    ApprovalEscalation,
    DelegatedRuntimeSession,
    ExecutionPolicy,
    ExecutionScope,
    IntegrationRecommendation,
    Mission,
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
from .onboarding import build_guidance_snapshot, detect_onboarding_status
from .profiles import ProfileRegistry
from .runtimes import detect_runtime_statuses
from .runtime_supervisor import DelegatedRuntimeSupervisor
from .skill_library import SkillLibrary
from .skills import SkillRegistry


class ControlRoomStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.control_dir = self.root / ".agent_control"
        self.control_dir.mkdir(parents=True, exist_ok=True)
        self.workspaces_path = self.control_dir / "workspaces.json"
        self.missions_path = self.control_dir / "missions.json"
        self.events_path = self.control_dir / "mission_events.jsonl"

    def load_workspaces(self) -> list[WorkspaceProfile]:
        payload = self._load_json(self.workspaces_path, [])
        workspaces = [WorkspaceProfile(**item) for item in payload]
        if not workspaces:
            workspaces = [self._default_workspace_profile()]
            self.save_workspaces(workspaces)
        return workspaces

    def save_workspaces(self, workspaces: list[WorkspaceProfile]) -> None:
        self.workspaces_path.write_text(
            json.dumps([asdict(item) for item in workspaces], indent=2),
            encoding="utf-8",
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
                    route_configs=item.get("route_configs", []),
                    routing_decisions=item.get("routing_decisions", []),
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
        self.missions_path.write_text(
            json.dumps([asdict(item) for item in missions], indent=2),
            encoding="utf-8",
        )

    def upsert_workspace(
        self,
        name: str,
        root_path: str,
        default_runtime: str,
        user_profile: str = "builder",
        workspace_id: str | None = None,
    ) -> WorkspaceProfile:
        workspaces = self.load_workspaces()
        workspace_root = Path(root_path).resolve()
        now = utc_now_iso()
        for item in workspaces:
            if item.workspace_id == workspace_id or (
                workspace_id is None and Path(item.root_path).resolve() == workspace_root
            ):
                item.name = name
                item.root_path = str(workspace_root)
                item.default_runtime = default_runtime
                item.user_profile = user_profile or item.user_profile
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
    ) -> Mission:
        missions = self.load_missions()
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
            ),
            verification_policy=MissionVerificationPolicy(
                commands=verification_commands,
                pause_on_failure=True,
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
            state=MissionStateSnapshot(status="queued"),
            tutorial_context={"profile": selected_profile},
            proof=MissionProof(summary="Mission created and waiting for first runtime cycle."),
        )
        missions.append(mission)
        self.save_missions(missions)
        self.append_event(
            MissionEvent(
                mission_id=mission_id,
                kind="mission.created",
                message=f"Mission created for runtime {runtime_id}.",
                metadata={"workspaceId": workspace_id, "mode": mode},
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

    def build_snapshot(self) -> dict:
        workspaces = self.load_workspaces()
        missions = self.load_missions()
        runtime_statuses = detect_runtime_statuses(self.root)
        runtime_lookup = {item.runtime_id: asdict(item) for item in runtime_statuses}
        profiles = ProfileRegistry(self.root / "config" / "profiles.json")
        skill_library = SkillLibrary(
            root=self.root,
            registry=SkillRegistry(self.root / "config" / "skills.json"),
        )
        onboarding = detect_onboarding_status(self.root)
        guidance = build_guidance_snapshot(self.root)
        runtime_supervisor = DelegatedRuntimeSupervisor(self.root)

        workspace_cards = []
        for workspace in workspaces:
            runtime_id = workspace.default_runtime
            skill_recommendations = [
                asdict(item)
                for item in recommend_skills(
                    workspace.workspace_type, workspace.default_runtime
                )
            ]
            workspace_cards.append(
                {
                    **asdict(workspace),
                    "runtimeStatus": runtime_lookup.get(runtime_id),
                    "skillRecommendations": skill_recommendations,
                    "integrationRecommendations": [
                        asdict(item)
                        for item in recommend_integrations(
                            workspace.workspace_type, workspace.default_runtime
                        )
                    ],
                    "recommendedSkillPacks": [
                        asdict(item)
                        for item in SkillLibrary.recommended_packs_from_skills(
                            skill_recommendations
                        )
                    ],
                }
            )

        for mission in missions:
            refreshed_sessions = []
            for session in mission.delegated_runtime_sessions:
                refreshed = runtime_supervisor.refresh_session(session)
                refreshed_sessions.append(refreshed)
            mission.delegated_runtime_sessions = refreshed_sessions
            mission.state.delegated_runtime_sessions = [asdict(item) for item in refreshed_sessions]
            if any(item.status == "waiting_for_approval" for item in refreshed_sessions):
                mission.state.status = "needs_approval"
                prompts = [
                    item.pending_approval.get("prompt", "Delegated approval required.")
                    for item in refreshed_sessions
                    if item.status == "waiting_for_approval"
                ]
                mission.proof.summary = prompts[0] if prompts else "Delegated runtime is waiting for approval."
                mission.proof.pending_approvals = prompts
            elif any(item.status in {"launching", "running"} for item in refreshed_sessions):
                mission.state.status = "running"
                mission.proof.summary = "Delegated runtime lane is active. Fluxio will continue when it finishes."
            if refreshed_sessions:
                mission.state.last_runtime_event = refreshed_sessions[-1].last_event or mission.state.last_runtime_event
        if missions:
            self.save_missions(missions)
        missions_payload = [asdict(item) for item in missions]
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

        return {
            "workspaceRoot": str(self.root),
            "workspaces": workspace_cards,
            "missions": missions_payload,
            "runtimes": [asdict(item) for item in runtime_statuses],
            "activity": self.recent_events(),
            "inbox": inbox_items,
            "onboarding": onboarding,
            "guidance": guidance,
            "profiles": {
                "defaultProfile": profiles.default_profile,
                "availableProfiles": profiles.list_names(),
                "details": {
                    name: {
                        "description": profile.description,
                        "ui": profile.ui,
                        "agent": asdict(profile.agent),
                    }
                    for name, profile in profiles.profiles.items()
                },
            },
            "skillLibrary": skill_library.build_catalog(),
            "harnessLab": build_harness_lab_snapshot(self.root),
            "bridgeLab": build_connected_apps_snapshot(self.root),
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
            updated_at=now,
        )

    @staticmethod
    def _load_json(path: Path, default: list | dict) -> list | dict:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))


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
    words = objective.strip().split()
    return " ".join(words[:6]) if words else "New Mission"


def build_harness_lab_snapshot(root: Path) -> dict:
    runs_root = root / ".agent_runs"
    sessions = sorted(
        [path for path in runs_root.glob("session_*") if path.is_dir()],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    recent_runs: list[dict] = []
    harness_counts: dict[str, int] = {}
    for session in sessions[:8]:
        state_path = session / "state.json"
        if not state_path.exists():
            continue
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        harness_id = payload.get("harness_id", "legacy_autonomous_engine")
        harness_counts[harness_id] = harness_counts.get(harness_id, 0) + 1
        recent_runs.append(
            {
                "sessionId": session.name,
                "harnessId": harness_id,
                "runtimeId": payload.get("runtime_id", "openclaw"),
                "autopilotStatus": payload.get("autopilot_status", "unknown"),
                "pauseReason": payload.get("autopilot_pause_reason", ""),
                "verificationFailures": len(payload.get("verification_failures", [])),
            }
        )
    return {
        "productionHarness": "fluxio_hybrid",
        "shadowCandidates": ["legacy_autonomous_engine"],
        "recentRuns": recent_runs,
        "harnessCounts": harness_counts,
        "recommendation": (
            "Fluxio hybrid harness is active; keep the legacy harness as a benchmark reference."
        ),
    }
