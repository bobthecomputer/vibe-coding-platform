from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlanBundle:
    plan_steps: list[str]
    creative_alternatives: list[str]
    acceptance_checks: list[str]


def build_docs_first_plan(objective: str, docs: list[str]) -> PlanBundle:
    doc_step = (
        "Review referenced docs and extract constraints"
        if docs
        else "Collect missing docs/spec links before implementation"
    )
    steps = [
        doc_step,
        "Draft implementation plan with milestones",
        "Implement smallest vertical slice",
        "Run verification checks and inspect diffs",
        "Prepare rollout notes and next iteration tasks",
    ]
    alternatives = [
        "Use a strict deterministic mode for lower cost and higher reproducibility",
        "Use a creative exploration mode for ideation, then switch to strict mode for execution",
    ]
    checks = [
        "All changed files compile or parse cleanly",
        "Relevant test command completes successfully",
        "Handoff packet includes unresolved risks and next actions",
    ]
    if "ui" in objective.lower() or "preview" in objective.lower():
        checks.append("Preview reflects expected UI behavior on desktop and mobile")
    return PlanBundle(plan_steps=steps, creative_alternatives=alternatives, acceptance_checks=checks)
