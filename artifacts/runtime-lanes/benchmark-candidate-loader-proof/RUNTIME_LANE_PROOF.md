# Hermes/OpenClaw Runtime Lane Proof

Run id: `benchmark-candidate-loader-proof`
Mode: `deterministic-no-live-runtime-call`

This proof records route contracts, launch commands, skill visibility, and fused supervision fields. It does not call live models and does not add a runtime adapter.

## Runtime Lanes

| Lane | Route | Skill | Differentiator |
| --- | --- | --- | --- |
| `openclaw` | `OpenClaw launch route: plan:executor -> openai-codex/gpt-5.4-mini (medium thinking)` | `jbheaven_godmode_lab` | OpenClaw owns gateway-style execution, remote approvals, and JSON session output. |
| `hermes` | `Hermes launch route: plan:executor -> minimax/MiniMax-M3 (high)` | `jbheaven_godmode_lab` | Hermes owns long-running agent loops, scheduling, memory, and skill reuse. |

## Fused Supervision

- Role: `supervisor_not_runtime_adapter`
- Runtime adapter added: `False`
- Registered adapters: `openclaw, hermes`

## Artifacts

- proof: `artifacts\runtime-lanes\benchmark-candidate-loader-proof\runtime_lane_proof.json`
- markdown: `artifacts\runtime-lanes\benchmark-candidate-loader-proof\RUNTIME_LANE_PROOF.md`
- route_scorecard: `artifacts\runtime-lanes\benchmark-candidate-loader-proof\route_scorecard.json`
- artifact_index: `artifacts\runtime-lanes\benchmark-candidate-loader-proof\artifacts_index.json`
