# Hermes/OpenClaw Runtime Lane Proof

Run id: `pr99-runtime-truth`
Mode: `deterministic-no-live-runtime-call`
Proof type: `route_contract_proof`

This proof records route contracts, launch command shape, skill visibility, and fused supervision fields. It does not launch a live runtime process, call live models, or add a runtime adapter.

## Runtime Lanes

| Lane | Route | Skill | Differentiator |
| --- | --- | --- | --- |
| `openclaw` | `OpenClaw launch route: plan:executor -> openai-codex/gpt-5.4-mini (medium thinking)` | `jbheaven_godmode_lab` | OpenClaw owns gateway-style execution, remote approvals, and JSON session output. |
| `hermes` | `Hermes launch route: plan:executor -> minimax/MiniMax-M3 (high)` | `jbheaven_godmode_lab` | Hermes owns long-running agent loops, scheduling, memory, and skill reuse. |

## Readiness And Recovery

- Overall status: `contract_ready_live_unverified`
- Promotion blocked: `True`
- Blocking gates: `6`

| Lane | Status | Blocking Gates | Next Recovery |
| --- | --- | --- | --- |
| `openclaw` | `contract_ready_live_unverified` | `3` | Run setup doctor or install OpenClaw before promoting this lane to live execution. |
| `hermes` | `contract_ready_live_unverified` | `3` | Repair Hermes from setup or NAS runtime doctor before long-running delegated work. |

## Fused Supervision

- Role: `supervisor_not_runtime_adapter`
- Runtime adapter added: `False`
- Registered adapters: `openclaw, hermes`

## Artifacts

- proof: `C:\Users\paul\projects\vibe-coding-platform\artifacts\runtime-lanes\pr99-runtime-truth\runtime_lane_proof.json`
- markdown: `C:\Users\paul\projects\vibe-coding-platform\artifacts\runtime-lanes\pr99-runtime-truth\RUNTIME_LANE_PROOF.md`
- route_scorecard: `C:\Users\paul\projects\vibe-coding-platform\artifacts\runtime-lanes\pr99-runtime-truth\route_scorecard.json`
- artifact_index: `C:\Users\paul\projects\vibe-coding-platform\artifacts\runtime-lanes\pr99-runtime-truth\artifacts_index.json`
