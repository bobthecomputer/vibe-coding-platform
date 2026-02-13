from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path

from .checkpoints import CheckpointStore
from .constitution import AgentConstitution
from .context_manager import ContextWindowManager
from .doc_ingestion import ingest_docs
from .handoff import create_handoff_packet, save_handoff_packet
from .memory import MemoryStore, ingest_state_into_memory
from .models import RunState, TimelineEvent
from .persona import PersonaRegistry
from .planner import build_docs_first_plan
from .prompts import build_prompt_stack
from .reporting import write_run_report
from .session_store import SessionStore
from .skills import SkillRegistry
from .verification import VerificationRunner
from .vibe_suggestions import build_vibe_next_steps, collect_repo_signals


class AutonomousEngine:
    def __init__(
        self,
        constitution: AgentConstitution,
        persona_registry: PersonaRegistry,
        context_manager: ContextWindowManager,
        session_store: SessionStore,
        verification_runner: VerificationRunner,
        skill_registry: SkillRegistry,
        memory_store: MemoryStore,
    ) -> None:
        self.constitution = constitution
        self.persona_registry = persona_registry
        self.context_manager = context_manager
        self.session_store = session_store
        self.verification_runner = verification_runner
        self.skill_registry = skill_registry
        self.memory_store = memory_store

    def run(
        self,
        objective: str,
        docs: list[str],
        persona: str,
        iterations: int,
        repo_path: Path,
        verify_commands: list[str],
        project_profile: str,
        max_handoffs: int,
        max_runtime_seconds: int,
        resume_from_session_id: str | None = None,
        checkpoint_every: int = 1,
        resume_from_checkpoint_path: str | None = None,
        autopilot_guardrails: dict | None = None,
        suggest_vibe_next_steps: bool = True,
    ) -> dict:
        started_at = time.monotonic()
        guardrails = autopilot_guardrails or {
            "pause_on_handoff": True,
            "pause_on_verification_failure": True,
        }
        autopilot_status = "running"

        resumed_state: dict | None = None
        resumed_lineage: list[str] = []
        if resume_from_session_id:
            previous_path = self.session_store.get_session_path(resume_from_session_id)
            if previous_path and (previous_path / "state.json").exists():
                resumed_state = self.session_store.read_state(previous_path)
                resumed_lineage = resumed_state.get("session_lineage", [resume_from_session_id])
                if not docs:
                    docs = [
                        record.get("source", "")
                        for record in resumed_state.get("doc_evidence", [])
                        if record.get("source")
                    ]
        if resume_from_checkpoint_path:
            checkpoint_payload = CheckpointStore.load(Path(resume_from_checkpoint_path))
            resumed_state = checkpoint_payload.get("state", resumed_state)
            resumed_lineage = resumed_state.get("session_lineage", resumed_lineage)
            if not docs:
                docs = checkpoint_payload.get("doc_sources", docs)

        plan_bundle = build_docs_first_plan(objective=objective, docs=docs)

        session_path = self.session_store.create_session(
            objective=objective,
            parent_session_id=resume_from_session_id,
        )
        metadata = self.session_store.read_metadata(session_path)
        session_id = metadata["session_id"]
        parent_session_id: str | None = metadata.get("parent_session_id")
        session_lineage: list[str] = resumed_lineage[:] if resumed_lineage else []
        session_lineage.append(session_id)
        checkpoint_store = CheckpointStore(session_path)

        docs_evidence = ingest_docs(docs=docs, repo_path=repo_path, session_path=session_path)
        readable_docs = len([item for item in docs_evidence if item.status == "ok"])

        failures = self.constitution.policy.validate(
            docs=docs,
            readable_docs=readable_docs,
            plan_steps=plan_bundle.plan_steps,
            alternatives=plan_bundle.creative_alternatives,
            acceptance_checks=plan_bundle.acceptance_checks,
        )
        if failures:
            self.session_store.append_timeline(
                session_path,
                TimelineEvent(
                    kind="preflight_failed",
                    message="Preflight checks failed.",
                    metadata={"failures": failures},
                ),
            )
            return {
                "status": "blocked",
                "preflight_failures": failures,
                "session_path": str(session_path),
            }

        persona_profile = self.persona_registry.get(persona)
        prompt_stack = build_prompt_stack(
            constitution_text=self.constitution.text,
            project_profile=project_profile,
            persona=persona_profile,
            task_brief=objective,
        )
        retrieved_skills = self.skill_registry.retrieve(task_brief=objective, top_k=3)
        memory_hits = self.memory_store.search(objective, limit=6)

        state = RunState(
            objective=objective,
            plan_steps=plan_bundle.plan_steps,
            acceptance_checks=plan_bundle.acceptance_checks,
            completed_steps=resumed_state.get("completed_steps", []) if resumed_state else [],
            decisions=(resumed_state.get("decisions", []) if resumed_state else [])
            + ["Applied docs-first planning policy before implementation."],
            changed_files=resumed_state.get("changed_files", []) if resumed_state else [],
            risks=resumed_state.get("risks", []) if resumed_state else [],
            next_actions=(resumed_state.get("next_actions", []) if resumed_state else [])
            or ["Execute the first remaining plan step."],
            retrieved_skills=[skill.name for skill in retrieved_skills],
            notes=[
                f"Creative alternatives: {', '.join(plan_bundle.creative_alternatives)}",
                f"Readable docs: {readable_docs}/{len(docs)}",
                (
                    "Memory hints: "
                    + " | ".join([item.content for item in memory_hits[:3]])
                    if memory_hits
                    else "Memory hints: none"
                ),
            ],
        )
        if resumed_state:
            state.decisions.append(f"Resumed from session '{resume_from_session_id}'.")
            state.acceptance_checks = list(
                dict.fromkeys(state.acceptance_checks + resumed_state.get("acceptance_checks", []))
            )
        if resume_from_checkpoint_path:
            state.decisions.append(f"Resumed from checkpoint '{resume_from_checkpoint_path}'.")

        self.session_store.append_timeline(
            session_path,
            TimelineEvent(kind="preflight", message="Preflight checks passed.", metadata={"docs": docs}),
        )
        if retrieved_skills:
            self.session_store.append_timeline(
                session_path,
                TimelineEvent(
                    kind="skills",
                    message="Retrieved top skills for this objective.",
                    metadata={"skills": [skill.name for skill in retrieved_skills]},
                ),
            )
        if memory_hits:
            self.session_store.append_timeline(
                session_path,
                TimelineEvent(
                    kind="memory",
                    message="Loaded relevant memory hints.",
                    metadata={"memory_count": len(memory_hits), "memory_ids": [item.id for item in memory_hits]},
                ),
            )
        self.context_manager.record("user", objective)
        self.context_manager.record("system", self.constitution.text)

        handoff_paths: list[str] = []
        checkpoint_paths: list[str] = []
        handoff_count = 0
        autopilot_pause_reason = ""

        for index in range(iterations):
            elapsed = time.monotonic() - started_at
            if elapsed >= max_runtime_seconds:
                state.risks.append(
                    f"Stopped early because max runtime budget ({max_runtime_seconds}s) was reached."
                )
                autopilot_status = "paused"
                autopilot_pause_reason = "runtime_budget"
                self.session_store.append_timeline(
                    session_path,
                    TimelineEvent(
                        kind="budget_stop",
                        message="Stopped due to runtime budget.",
                        metadata={"elapsed_seconds": int(elapsed), "max_runtime_seconds": max_runtime_seconds},
                    ),
                )
                break

            remaining_now = [step for step in state.plan_steps if step not in state.completed_steps]
            step = remaining_now[0] if remaining_now else state.plan_steps[index % len(state.plan_steps)]
            if step not in state.completed_steps:
                state.completed_steps.append(step)
            state.decisions.append(f"Iteration {index + 1}: advanced step '{step}'.")
            state.next_actions = [
                next_step
                for next_step in state.plan_steps
                if next_step not in state.completed_steps
            ]
            status = self.context_manager.record(
                "assistant",
                f"Iteration {index + 1}: {step}. Objective: {objective}",
            )
            self.session_store.append_timeline(
                session_path,
                TimelineEvent(kind="iteration", message=f"Completed iteration {index + 1}", metadata={"step": step}),
            )

            if checkpoint_every > 0 and (index + 1) % checkpoint_every == 0:
                context_snapshot = {
                    "used_tokens": self.context_manager.used_tokens,
                    "usage_ratio": round(self.context_manager.usage_ratio, 3),
                    "status": self.context_manager.status(),
                }
                checkpoint_path = checkpoint_store.save(
                    session_id=session_id,
                    iteration=index + 1,
                    run_state=state,
                    context=context_snapshot,
                    doc_sources=docs,
                )
                checkpoint_paths.append(str(checkpoint_path))
                self.session_store.append_timeline(
                    session_path,
                    TimelineEvent(
                        kind="checkpoint",
                        message=f"Created checkpoint at iteration {index + 1}",
                        metadata={"checkpoint_path": str(checkpoint_path)},
                    ),
                )

            if status in {"rollover", "hard_stop"}:
                if handoff_count >= max_handoffs:
                    state.risks.append(
                        f"Rollover requested but max handoffs budget ({max_handoffs}) was reached."
                    )
                    autopilot_status = "paused"
                    autopilot_pause_reason = "handoff_budget"
                    self.session_store.append_timeline(
                        session_path,
                        TimelineEvent(
                            kind="budget_stop",
                            message="Stopped due to handoff budget.",
                            metadata={"handoff_count": handoff_count, "max_handoffs": max_handoffs},
                        ),
                    )
                    break

                handoff_count += 1
                packet = create_handoff_packet(
                    session_id=session_id,
                    parent_session_id=parent_session_id,
                    reason=f"context_{status}",
                    state=state,
                    prompt_stack=prompt_stack,
                    context_manager=self.context_manager,
                )
                handoff_path = save_handoff_packet(
                    packet=packet,
                    session_path=session_path,
                    sequence=handoff_count,
                )
                handoff_paths.append(str(handoff_path))

                self.session_store.append_timeline(
                    session_path,
                    TimelineEvent(
                        kind="handoff",
                        message="Created rollover handoff packet.",
                        metadata={"path": str(handoff_path), "status": status},
                    ),
                )
                compacted = self.context_manager.compact_window()
                self.context_manager.reset_with_seed(compacted)

                if guardrails.get("pause_on_handoff", True):
                    autopilot_pause_reason = f"context_{status}"
                    autopilot_status = "paused"
                    self.session_store.append_timeline(
                        session_path,
                        TimelineEvent(
                            kind="autopilot_pause",
                            message="Paused after handoff per guardrail policy.",
                            metadata={"reason": autopilot_pause_reason},
                        ),
                    )
                    break

                next_session_path = self.session_store.create_session(
                    objective=objective,
                    parent_session_id=session_id,
                )
                next_metadata = self.session_store.read_metadata(next_session_path)
                parent_session_id = session_id
                session_id = next_metadata["session_id"]
                session_path = next_session_path
                session_lineage.append(session_id)
                self.session_store.append_timeline(
                    session_path,
                    TimelineEvent(
                        kind="resume",
                        message="Started from rollover handoff.",
                        metadata={"source_handoff": str(handoff_path)},
                    ),
                )

                if handoff_count >= max_handoffs:
                    state.next_actions.append("Increase handoff budget to continue autonomous progression.")
                    break

        if verify_commands:
            verification_results = self.verification_runner.run(commands=verify_commands, workdir=repo_path)
            state.verification_results.extend(verification_results)
            if guardrails.get("pause_on_verification_failure", True):
                if any(item.return_code != 0 for item in verification_results):
                    autopilot_pause_reason = "verification_failure"
                    autopilot_status = "paused"
            self.session_store.append_timeline(
                session_path,
                TimelineEvent(
                    kind="verification",
                    message="Verification commands completed.",
                    metadata={
                        "commands": verify_commands,
                        "failures": [r.command for r in verification_results if r.return_code != 0],
                    },
                ),
            )

        persisted_state = asdict(state)
        persisted_state["session_lineage"] = session_lineage
        persisted_state["prompt_stack"] = asdict(prompt_stack)
        persisted_state["doc_evidence"] = [asdict(item) for item in docs_evidence]
        persisted_state["context"] = {
            "used_tokens": self.context_manager.used_tokens,
            "usage_ratio": round(self.context_manager.usage_ratio, 3),
            "status": self.context_manager.status(),
        }
        if not autopilot_pause_reason and not state.next_actions:
            autopilot_status = "completed"
        elif not autopilot_pause_reason and state.next_actions:
            autopilot_status = "incomplete"

        persisted_state["autopilot_status"] = autopilot_status
        persisted_state["autopilot_pause_reason"] = autopilot_pause_reason
        self.session_store.save_state(session_path=session_path, state=persisted_state)
        memory_ids = ingest_state_into_memory(
            memory=self.memory_store,
            session_id=session_id,
            state=persisted_state,
        )
        persisted_state["memory_item_ids"] = memory_ids

        vibe_next_steps: list[str] = []
        if suggest_vibe_next_steps:
            repo_signals = collect_repo_signals(repo_path)
            vibe_next_steps = build_vibe_next_steps(
                objective=objective,
                run_state=persisted_state,
                memory_hits=[item.id for item in memory_hits],
                repo_signals=repo_signals,
            )
            persisted_state["vibe_next_steps"] = vibe_next_steps

        self.session_store.save_state(session_path=session_path, state=persisted_state)

        report_paths = write_run_report(
            session_path=session_path,
            objective=objective,
            session_lineage=session_lineage,
            handoff_paths=handoff_paths,
            state=persisted_state,
        )

        return {
            "status": "ok",
            "session_path": str(session_path),
            "session_lineage": session_lineage,
            "handoff_packets": handoff_paths,
            "checkpoints": checkpoint_paths,
            "handoff_budget_used": handoff_count,
            "runtime_seconds": int(time.monotonic() - started_at),
            "readable_docs": readable_docs,
            "memory_hits": [item.id for item in memory_hits],
            "memory_items_written": memory_ids,
            "autopilot_status": autopilot_status,
            "autopilot_pause_reason": autopilot_pause_reason,
            "vibe_next_steps": vibe_next_steps,
            **report_paths,
            "verification_failures": [
                result.command for result in state.verification_results if result.return_code != 0
            ],
            "remaining_steps": state.next_actions,
        }
