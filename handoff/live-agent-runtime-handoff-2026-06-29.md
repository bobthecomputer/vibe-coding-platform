# Live Agent Runtime Handoff - 2026-06-29

## Project

`C:\Users\paul\Projects\vibe-coding-platform`

## Objective

Make Fluxio/vibe-coding-platform actually usable for Agent Live model work, not just proof and evidence screens. The user needs to log in, select a runtime/model route, send a normal prompt, and see a real assistant answer in Agent messages.

## Current Usable Routes

- Hermes: usable through WSL. Backend smoke returned `HERMES_BACKEND_ROUTE_OK`.
- OpenCode: usable natively. OpenRouter/DeepSeek output was proven visible in Agent Live.
- OpenClaw: installed natively, but model reply calls timed out in backend smoke. The app now reports a clean timeout instead of hanging, but OpenClaw is not yet proven usable for model replies.

## Important Warning

Do not apply `C:\Users\paul\Downloads\vibe-coding-platform-live-agent-fix.zip` wholesale.

The ZIP contains a stale `web/src/fluxio/FluxioShell.jsx` that would replace the current large app shell with a much smaller older file and delete current UI work. Only selected backend/runtime ideas from that ZIP were integrated.

## Integrated From The ZIP

- Hermes route aliases:
  - `opencon`, `opencon-pro`, `openconpro` route to `openrouter`.
  - `glm-5.2` and `openrouter/z-ai/glm-5.2` normalize to `z-ai/glm-5.2` for Hermes CLI calls.
- Runtime worker parsing:
  - Preserves `FLUXIO_EVENT:` structured events.
  - Converts raw JSON CLI assistant/model messages into runtime events.
  - Converts raw JSON command/tool events into runtime output events.
  - Strips ANSI escape sequences before parsing JSON.

## Relevant Files Changed

- `src/grant_agent/runtime_worker.py`
- `src/grant_agent/runtimes/hermes.py`
- `src/grant_agent/runtimes/openclaw.py`
- `src/grant_agent/web_backend.py`
- `src/grant_agent/runtimes/opencode.py`
- `src/grant_agent/opencode_bridge.py`
- `web/src/fluxio/workspaceModel.js`
- `web/src/fluxio/FluxioShell.jsx`
- `tests/test_runtime_worker_messages.py`
- `tests/test_hermes_route_aliases.py`
- `tests/test_runtimes.py`
- `tests/test_web_backend.py`
- `tests/test_workspace_model_contract.py`

## Tests Already Run

- `python -m pytest tests/test_hermes_route_aliases.py tests/test_runtime_worker_messages.py -q` -> passed.
- `python -m pytest tests/test_runtimes.py -q` -> passed.
- Focused runtime/backend/workspace tests -> passed.
- `npm run frontend:build` -> passed.
- `npm run verify:authenticated-settings` -> passed.

## Current Runtime Status

- Hermes:
  - Detected as `wsl:hermes`.
  - Version observed: `v0.14.0`.
  - Ready for WSL mission routing.
- OpenCode:
  - Detected natively.
  - Version observed: `1.15.13`.
  - Ready for native OpenRouter/DeepSeek routing.
- OpenClaw:
  - Detected natively.
  - Version observed: `2026.4.22`.
  - Latest npm observed: `2026.6.10`.
  - Installed but behind latest.
  - Backend model smoke timed out with a readable error.

## Next Best Work

1. Fix or update OpenClaw so this command returns a real model reply:

   ```powershell
   openclaw infer model run --local --json --model openai-codex/gpt-5.5 --prompt "Reply exactly: OPENCLAW_BACKEND_ROUTE_OK"
   ```

2. Verify the app login and Agent Live flow end-to-end:
   - Log in.
   - Select Hermes, OpenCode, and OpenClaw routes.
   - Send a normal prompt.
   - Confirm the assistant answer appears in the Agent message thread.

3. Make runtime readiness obvious in the UI:
   - Hermes: ready through WSL.
   - OpenCode: ready native.
   - OpenClaw: installed but model replies timeout until fixed.

4. Do not accept proof-only success. The acceptance condition is:

   The user sends a normal prompt and sees a real model answer in Agent messages.

## Practical Recommendation

Use Hermes or OpenCode for immediate work. Treat OpenClaw as installed but blocked until the model-call timeout is fixed.

---

## Follow-Up Hardening Added In Production Update Plus

- Backend Agent Live chat now supports `runtime: "opencode"` directly through `grant_agent.opencode_bridge`.
- Backend OpenCode chat extracts real `FLUXIO_EVENT: runtime.model_message` output instead of displaying raw bridge logs.
- Runtime-worker parsing now recognizes OpenCode-style `part.updated` text events as visible model messages.
- Backend OpenClaw chat now defaults to `openclaw agent --session-id --message --json --local`, with `agents add` / `models set` setup before the turn. The older `infer model run` command remains available through `openclawMode: "infer"` or `FLUXIO_OPENCLAW_CHAT_MODE=infer`.
- OpenClaw and backend chat route normalization now support `opencon`, `opencon-pro`, and `openconpro` aliases for GLM 5.2 through OpenRouter.
- Failed backend chat turns now write a failed runtime compartment and turn receipt, so Agent Live can show the real failure reason instead of dropping the turn or showing an empty fake reply.
- The Agent Live UI now marks failed structured chat results as failed turns with the real runtime error detail.

## Updated OpenClaw Validation Command

Use the Agent Live backend path first, because that is now the production path:

```powershell
# From the app: runtime=openclaw, provider=openai-codex, model=gpt-5.5
# Or directly against the CLI path now used by the backend:
openclaw agent --local --json --session-id fluxio_smoke_openclaw --message "Reply exactly: OPENCLAW_BACKEND_ROUTE_OK" --thinking medium
```

The legacy one-shot model path can still be checked separately:

```powershell
openclaw infer model run --local --json --model openai-codex/gpt-5.5 --prompt "Reply exactly: OPENCLAW_INFER_ROUTE_OK"
```

If the legacy command still times out but the `agent` command replies, Agent Live should be considered unblocked for OpenClaw chat.
