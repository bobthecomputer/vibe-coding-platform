# Live Agent Runtime Production Update Plus - 2026-06-29

Package time: 2026-06-29 16:15 Europe/Paris

## Purpose

This bundle is a follow-up hardening pass on the Agent Live runtime/chat update. It keeps the original production files and adds fixes for the remaining OpenClaw/backend-chat and OpenCode-chat gaps. It still does not include secrets, `.agent_control`, generated dependency folders, or fake model replies.

## Behavior Covered

- Hermes route aliases for `opencon`, `opencon-pro`, and `openconpro`.
- Hermes OpenRouter model normalization for `glm-5.2` / `openrouter/z-ai/glm-5.2`.
- OpenClaw now also normalizes `opencon`/`opencon-pro` GLM 5.2 routes to `openrouter/z-ai/glm-5.2`.
- Runtime worker parsing for raw JSON assistant/model/tool/command events, including OpenCode `part.updated` text events.
- Native OpenCode runtime registration and bridge code.
- Backend Agent Live chat now accepts `runtime: "opencode"` and extracts real `FLUXIO_EVENT: runtime.model_message` output from the bridge.
- Backend OpenClaw chat now defaults to the same `openclaw agent --session-id --message --json --local` path used by mission execution, with agent/model setup before the turn. The previous `infer model run` path remains available with `openclawMode: "infer"` or `FLUXIO_OPENCLAW_CHAT_MODE=infer`.
- Backend chat failures now create a failed compartment/turn receipt instead of losing the turn completely, so Agent Live can show the real error and route metadata.
- Agent Live UI now displays structured failed-runtime results as failed turns instead of generic empty replies.
- Workspace policy save notifications remain visible during mission launch; the previous success-toast suppression stays removed.
- Tests were updated/added for runtime parsing, Hermes aliases, OpenClaw/OpenCon route normalization, OpenCode chat, backend routing, and workspace model contracts.

## Included Files

- `src/grant_agent/runtime_worker.py`
- `src/grant_agent/runtimes/hermes.py`
- `src/grant_agent/runtimes/openclaw.py`
- `src/grant_agent/runtimes/opencode.py`
- `src/grant_agent/runtimes/__init__.py`
- `src/grant_agent/opencode_bridge.py`
- `src/grant_agent/web_backend.py`
- `src/grant_agent/mission_control.py`
- `web/src/fluxio/workspaceModel.js`
- `web/src/fluxio/FluxioShell.jsx`
- `web/src/fluxio/styles.css`
- `scripts/verify_real_agent_conversation_proof.py`
- `tests/test_runtime_worker_messages.py`
- `tests/test_hermes_route_aliases.py`
- `tests/test_runtimes.py`
- `tests/test_web_backend.py`
- `tests/test_workspace_model_contract.py`
- `handoff/live-agent-runtime-handoff-2026-06-29.md`
- `handoff/live-agent-runtime-production-update-2026-06-29.MANIFEST.md`

## Verification Performed In This Follow-Up

- `python -m py_compile src/grant_agent/runtime_worker.py src/grant_agent/runtimes/hermes.py src/grant_agent/runtimes/openclaw.py src/grant_agent/runtimes/opencode.py src/grant_agent/opencode_bridge.py src/grant_agent/web_backend.py tests/test_runtime_worker_messages.py tests/test_hermes_route_aliases.py tests/test_runtimes.py tests/test_web_backend.py tests/test_workspace_model_contract.py`
- Runtime-worker parser smoke with temporary stubs for the missing base-repo modules.
- Web-backend route/reply smoke with temporary stubs for the missing base-repo modules.
- Agent-chat smoke covering OpenClaw agent-mode execution, OpenCode `FLUXIO_EVENT` reply extraction, and failed-runtime compartment creation.

## Verification To Run After Applying To The Full Repository

- `python -m pytest tests/test_runtime_worker_messages.py tests/test_hermes_route_aliases.py tests/test_runtimes.py tests/test_web_backend.py tests/test_workspace_model_contract.py -q`
- `npm run frontend:build`
- `npm run verify:authenticated-live-agent`
- A real OpenClaw Agent Live smoke with `runtime=openclaw`, then an OpenCode smoke with `runtime=opencode`.

## Remaining Risk

I could not run a real model call from this sandbox. The OpenClaw timeout blocker is mitigated by switching backend chat to the mission-proven `openclaw agent` path and by preserving failed receipts, but the full runtime host still needs the real OpenClaw smoke above to confirm provider/auth behavior.
