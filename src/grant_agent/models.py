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


def to_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value
