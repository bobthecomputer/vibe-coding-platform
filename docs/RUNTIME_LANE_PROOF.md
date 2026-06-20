# Hermes/OpenClaw Runtime Lane Proof

Date: 2026-06-20

## Purpose

This proof path demonstrates the corrected Fluxio/JBHEAVEN runtime goal:

- Hermes and OpenClaw are the registered delegated runtime adapters.
- The fused runtime view is the Fluxio supervisor/session evidence layer, not a third adapter.
- Skill visibility comes from the persisted Fluxio skill catalog in `config/skills.json`.
- No OpenCodeGo runtime adapter is required or added for this proof.

## Lane Differentiation

| Lane | Registered Adapter | Route Shape | Proof Meaning |
| --- | --- | --- | --- |
| OpenClaw | `openclaw` | `openclaw agent ... --json`, optional per-agent model setup, `--thinking` effort | Gateway-style route for phone-visible approvals, managed skills, and JSON session output. |
| Hermes | `hermes` | `hermes chat -q ... -Q --model ... --provider ...`, native or WSL command selection | Long-running agent loop route with scheduling, memory, skill reuse, and subagent-oriented execution. |
| Fused supervisor | none | `DelegatedRuntimeSupervisor` session JSON/events/logs around either lane | Shared proof layer for route contracts, events, approvals, heartbeats, logs, and changed-file evidence. |

## Repeatable Proof Command

```powershell
python scripts/runtime_lane_proof_harness.py --run-id runtime-lane-proof-20260620
```

The harness is deterministic. It calls the real route builders and skill registry, but it does not call live models, run harmful probes, edit files, or add a runtime adapter.

Expected artifacts:

- `artifacts/runtime-lanes/<run-id>/runtime_lane_proof.json`
- `artifacts/runtime-lanes/<run-id>/RUNTIME_LANE_PROOF.md`
- `artifacts/runtime-lanes/<run-id>/artifacts_index.json`

## Verification Commands

```powershell
python -m unittest tests.test_runtime_lane_proof_harness tests.test_runtimes
python scripts/runtime_lane_proof_harness.py --run-id runtime-lane-proof-20260620
```

These prove:

- `runtime_adapter_map()` exposes Hermes and OpenClaw and does not expose `opencode`.
- OpenClaw route contracts canonicalize `openai` to `openai-codex/<model>` and include JSON gateway output.
- Hermes route contracts preserve the Hermes provider/model command shape, including MiniMax routes.
- `jbheaven_godmode_lab`, `hermes_skill_packager`, and `runtime_loop_supervisor` are visible in the skill catalog.
- The fused view uses `DelegatedRuntimeSession` fields instead of adding another runtime adapter.
