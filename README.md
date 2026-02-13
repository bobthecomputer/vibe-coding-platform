# Grant Agent Harness

Grant Agent Harness is a docs-first, safety-aware orchestration layer for long-running coding sessions.

It is built around one core promise: the agent can keep moving when context gets full, but users stay in control through explicit plans, checks, and handoff artifacts.

## What this MVP includes

- Prompt stack assembly with persona profiles.
- Skill registry with top-k retrieval per objective.
- Docs-first preflight policy enforcement.
- Doc evidence ingestion (local files and URLs).
- Context window tracking with rollover thresholds.
- Structured handoff packet generation for new sessions.
- Runtime and handoff budget controls.
- Timeline and state artifacts for replay/debugging.
- Persistent memory store for cross-session continuity and auto-resume.
- Vibe loop command with checkpointing and autopilot pause signals.
- Verification runner with high-risk command blocking.
- Public run reporting (`run_report.md`, `tweet_thread.txt`, `public_summary.json`).
- Feature suggestion engine from pasted paper text.
- One-click demo workflow: navigator + training comparison + adversarial probe.
- Stakeholder proof report panel (`proof_report_panel.html`) in exported bundles.
- Challenge presets: `gandalf` and `hackaprompt` with tuned selectors and attempts.

## Quickstart

```bash
python -m pip install -e .
python -m grant_agent.cli bootstrap
python -m grant_agent.cli vibe --objective "Build onboarding flow with polished UX" --doc "docs/PRD.md"
python -m grant_agent.cli vibe-status
python -m grant_agent.cli vibe-continue --cycles 2 --iterations 4
python -m grant_agent.cli checkpoints
python -m grant_agent.cli resume-checkpoint --iterations 4
python -m grant_agent.cli run --mode balanced --objective "Build a login flow" --doc "docs/api.md"
python -m grant_agent.cli resume --mode balanced
python -m grant_agent.cli memory --query "verification"
python -m grant_agent.cli suggest-features --paper-file "docs/PRD.md"
python -m grant_agent.cli list-presets
python -m grant_agent.cli demo-run --preset gandalf --objective "Show autonomous hardening loop" --export-zip
python -m grant_agent.cli demo-suite --objective "Evaluate autonomy hardening" --export-zip
python -m grant_agent.cli demo-button --preset gandalf --objective "Show autonomous hardening loop"
python -m grant_agent.cli proof-dashboard --open
python -m grant_agent.cli next-features
python -m grant_agent.cli search --query "handoff" --include "src/**/*.py"
python -m grant_agent.cli replay
python -m grant_agent.cli story
python -m grant_agent.cli export-openai-request --objective "Build auth" --output "openai_request.json"
python -m grant_agent.cli evaluate
```

Generated artifacts are written under `.agent_runs/`.

Each completed session writes:

- `state.json` and `timeline.jsonl`
- `checkpoints/ckpt_*.json`
- `docs_evidence.json`
- `run_report.md`
- `tweet_thread.txt`
- `public_summary.json`
- global `.agent_memory.json`
- demo bundles in `.demo_bundles/` with `proof_report.md` and `proof_report_panel.html`

## Why this is useful

- It keeps long tasks coherent by emitting a machine-readable handoff packet before context overflow.
- It forces a plan and acceptance checks before edits.
- It gives users visibility into what happened and what to do next.
- It generates post-run artifacts ready to reuse in public progress updates.
- It can generate presentation-grade proof bundles for stakeholders in one command.

## Layout

- `src/grant_agent/`: engine, policies, planning, context manager.
- `config/personas.json`: persona presets.
- `config/skills.json`: typed skill registry for retrieval.
- `config/modes.json`: fast/balanced/careful/creative presets.
- `config/challenge_presets.json`: Gandalf/HackAPrompt demo presets.
- `docs/`: constitution, roadmap, handoff schema, PRD, CLI reference.
- `tests/`: unit tests for rollover and handoff behavior.
