# Hermes/OpenClaw Runtime Lane Proof

Run id: `pr109-delegated-runtime-proof`
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

- proof: `artifacts\pr109-runtime-live-proof-receipts\pr109-delegated-runtime-proof\runtime_lane_proof.json`
- markdown: `artifacts\pr109-runtime-live-proof-receipts\pr109-delegated-runtime-proof\RUNTIME_LANE_PROOF.md`
- route_scorecard: `artifacts\pr109-runtime-live-proof-receipts\pr109-delegated-runtime-proof\route_scorecard.json`
- artifact_index: `artifacts\pr109-runtime-live-proof-receipts\pr109-delegated-runtime-proof\artifacts_index.json`
