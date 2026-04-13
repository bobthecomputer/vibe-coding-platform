# Grant Agent Harness

Grant Agent Harness is a docs-first, safety-aware orchestration layer for long-running coding sessions.

It is built around one core promise: the agent can keep moving when context gets full, but users stay in control through explicit plans, checks, and handoff artifacts.

Current product stop point:

- [Fluxio 1.0 Release Definition](docs/FLUXIO_1_0_RELEASE.md)
- [Live UI Development](docs/LIVE_UI_DEVELOPMENT.md)

## What this MVP includes

- Prompt stack assembly with persona profiles.
- Personalization profile registry (`config/profiles.json`) for UI + agent defaults.
- Skill registry with top-k retrieval per objective.
- Docs-first preflight policy enforcement.
- Doc evidence ingestion (local files and URLs).
- Context window tracking with rollover thresholds.
- Parallel worker branches with merge scoring (`--parallel-agents` / swarm modes).
- Explicit worker merge policy selection (`best_score`, `consensus`, `risk_averse`).
- Structured handoff packet generation for new sessions.
- Runtime and handoff budget controls.
- Timeline and state artifacts for replay/debugging.
- Persistent memory store for cross-session continuity and auto-resume.
- Vibe loop command with checkpointing and autopilot pause signals.
- Soak command for multi-cycle autonomous reliability validation.
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
python -m grant_agent.cli run --mode profile --profile hands_free_builder --objective "Build a login flow" --doc "docs/api.md"
python -m grant_agent.cli profiles
python -m grant_agent.cli soak --objective "Stress test autonomous loop" --cycles 2 --iterations 2
python -m grant_agent.cli run --mode swarms --objective "Parallelize API + tests + docs" --doc "README.md"
python -m grant_agent.cli run --mode balanced --parallel-agents 4 --objective "Split implementation by subsystem" --doc "README.md"
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
python -m grant_agent.cli release-readiness
```

## Desktop (Tauri)

The desktop app now runs a single canonical frontend shell from the `t3code` tree:

- `src-tauri/` for tray/overlay/runtime logic
- `t3code/apps/web/` for the live React workbench UI
- `desktop-ui/` for shared view-model and shell components imported by the T3 web entrypoint

Run:

```bash
npm install
npm run tauri:dev
```

Implemented backend features:

- Hold-to-open overlay (`Space`, fallback `Ctrl+Space`), tray controls, persisted settings.
- Performance telemetry: cold start, hotkey latency, idle RAM.
- Dictation service (push-to-talk session model, local-first command-based STT, OS fallback path).
- Mode system v1 (`coding`, `youtube`, `writing`) with per-mode context recipe + tool allowlists.
- Question bubbles and approval gate for uncertain/high-risk actions.
- Typed agent command protocol + localhost automation API (optional bearer-token auth).
- OpenClaw-style localhost gateway integration path (WebSocket client + events).
- OpenClaw reconnect/backoff hardening with rejected-event audit logging.
- OpenClaw action/clarify roundtrip continuity (`ui.answer` + `action.result` relay back to gateway).
- Autonomous-mode gateway activation: OpenClaw routing is enabled in autonomous agent modes and disabled outside them.
- OpenClaw offline queue + replay for outbound payload continuity after reconnect.
- OpenClaw duplicate-event suppression via recent gateway event id tracking.
- OpenClaw nonce/integrity envelope + ack tracking for safer replay semantics.
- Night mode scheduler for safe maintenance tasks only.
- Append-only audit log and keychain-backed gateway credential storage.
- Key-first provider setup: provider secrets are stored in OS keychain (not local storage).
- Desktop autonomous dashboard with one-click `vibe-status`, `vibe-continue`, and `soak` actions.
- Task-level model routing in desktop settings (frontend/backend/verification/research/general), with automatic prompt classification and provider/model switching.
- Codex and MiniMax provider defaults hardened (Codex API-key flow, MiniMax bearer-token flow) with credential status surfaced in routing UI.

Reference docs:

- `docs/AGENT_CONTROL_PROTOCOL.md`
- `docs/AUTOMATION_LOCALHOST_API.md`
- `docs/DICTATION_SETUP.md`
- `docs/NIGHT_MODE.md`
- `docs/THREAT_MODEL.md`
- `docs/DESKTOP_PERFORMANCE_REPORT.md`
- `docs/LIVE_UI_DEVELOPMENT.md`

Generated artifacts are written under `.agent_runs/`.

## Profiles And Merge Policies

- `python -m grant_agent.cli profiles` lists available personalization profiles and workspace defaults.
- `python -m grant_agent.cli profiles --name hands_free_builder` prints resolved UI/agent settings for one profile.
- Use `--mode profile --profile <name>` to resolve execution defaults from `config/profiles.json`.
- Use `--merge-policy <best_score|consensus|risk_averse>` to override per-mode/per-profile merge behavior.
- `python -m grant_agent.cli soak ...` runs repeated autonomous cycles and reports checkpoint/session health.

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
- `config/modes.json`: fast/balanced/careful/creative plus swarms/autopilot/deep_run/swarm_mega presets.
- `config/challenge_presets.json`: Gandalf/HackAPrompt demo presets.
- `docs/`: constitution, roadmap, handoff schema, PRD, CLI reference.
- `tests/`: unit tests for rollover and handoff behavior.
