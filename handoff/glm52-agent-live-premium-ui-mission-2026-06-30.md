# GLM-5.2 Agent Live Premium UI Mission - 2026-06-30

This is the handoff packet for the next Agent Live UI improvement mission.

## Route Contract

Use this route unless the operator explicitly changes it:

- Harness/runtime: `Hermes`
- Provider lane: `OpenCode Go`
- Requested model: `opencode-go/glm-5.2`
- Effective model id: `openrouter/z-ai/glm-5.2`
- Effort: `low` for route smoke tests, `medium` or `high` only for deeper design work
- Skill/context: `hermes-opencode`

The model name is `GLM-5.2`, not `GNM`, `GN 5.2`, or `gpt-5.5`.

If asked what model or runtime is active, answer from the route contract above. Do not self-identify as OpenAI Codex or `gpt-5.5` unless the selected route is actually `openai-codex/gpt-5.5`.

## Worktree Rule

Do not edit the deployed release or the operator's active working tree directly.

Create an isolated copy/worktree first:

```powershell
git -C C:/Users/paul/Projects/vibe-coding-platform/tmp-pr-audit/merge-master-agent-live worktree add C:/Users/paul/Projects/vibe-coding-platform/tmp-pr-audit/glm52-agent-live-premium-ui codex/glm52-agent-live-premium-ui
```

If that branch already exists, use a fresh timestamped branch under `codex/`.

Keep the existing NAS deployment working while the mission runs. The operator should be able to keep using `http://127.0.0.1:47980/control?mode=agent&workspace=route_trust_general_coding&runtime=hermes&provider=opencode-go&model=opencode-go%2Fglm-5.2&effort=low&skill=hermes-opencode&channel=browser&runUntil=continue_until_blocked`.

## Primary Objective

Make Agent Live and the adjacent operator surfaces feel like a finished daily-use product rather than an internal runtime verifier.

The first viewport must answer:

1. What is the current thread/mission?
2. What did the agent say?
3. What can the operator do next?
4. Which route is active?
5. Where is proof if the operator wants it?

Proof, runtime trace, provider internals, receipts, and old diagnostics must remain available, but they must not dominate the default view.

## Required Skills And Rules

Before changing UI, read and apply:

- `C:/Users/paul/.codex/skills/finished-operator-ui/SKILL.md`
- `C:/Users/paul/.codex/skills/human-operator-product-ui/SKILL.md`
- `docs/OPERATOR_UI_VISUAL_AUDIT_2026-06-07.md`
- `docs/FLUXIO_1_0_POLISH_PLAN.md`
- `docs/OPERATOR_UI_BAD_VS_BEST_RESEARCH_2026-06-08.md`
- `docs/OPERATOR_UI_GOAL_COMPLETION_AUDIT_2026-06-08.md`

Write this sentence before editing:

> The current screen fails because ______ dominates, but the human's primary object should be ______.

Then inspect the rendered screen and identify duplicate state before coding.

## UI Improvements To Target

Prioritize these in order:

1. Route identity clarity
   - Visible chips should say `Hermes`, `OpenCode Go`, and `GLM-5.2`.
   - Receipts may disclose the effective bridge as `native OpenCode bridge / openrouter/z-ai/glm-5.2`.
   - Do not show `gpt-5.5` in the active Agent Live route unless that route is really selected.

2. Agent Live thread quality
   - Make the transcript the dominant object.
   - Keep the composer and continue/modify controls close to the thread.
   - Keep runtime trace collapsed by default.
   - Show pending, success, error, and retry states as real UI states, not toast-only failures.

3. Premium operator polish
   - Remove card piles and nested bordered boxes.
   - Use a calm black-and-white operator aesthetic with sparse accent color.
   - Keep copy short and action-oriented.
   - Add focused micro-animations only where they communicate state: sending, streaming, completed, retrying, proof available.
   - Respect reduced-motion preferences.

4. Accessibility
   - Keyboard focus must be visible.
   - Buttons and icon controls need labels.
   - Chat messages should preserve readable order for screen readers.
   - Loading and error states should be announced or discoverable.
   - Color must not be the only status signal.

5. Verification and preview workflow
   - Browser and Preview are model-usable workspaces.
   - The agent must be able to inspect rendered HTML, click buttons, send messages, capture screenshots, and attach proof.
   - Every visual patch needs desktop and phone screenshots.

## Open Source References To Borrow From

Use these as product references, not as copy-paste sources:

- Open WebUI: self-hosted AI UI with OpenAI-compatible and OpenRouter-style backends. Borrow provider flexibility and local-control framing.
- LibreChat: unified provider chat, agents, artifacts, code interpreter, MCP, memory, and conversation search. Borrow the idea of provider/model selection that still feels like one conversation.
- Langfuse: LLM tracing and observability. Borrow compact traces, latency/model metadata, and drill-down proof without making trace the chat.
- Plane: open-source project management inspired by Jira/Linear/Monday/ClickUp. Borrow project/queue clarity and visual planning discipline for Builder.

Reference URLs:

- `https://github.com/open-webui/open-webui`
- `https://github.com/danny-avila/LibreChat`
- `https://github.com/langfuse/langfuse`
- `https://github.com/makeplane/plane`

Do not import large dependencies from these projects without a dependency review.

## Dependency And Codex Naming Review

Before removing or renaming anything related to Codex:

1. Search for runtime meaning versus brand/UI meaning.
2. Keep `openai-codex` where it is an actual provider/auth route.
3. Remove or rename only misleading visible UI text.
4. Preserve tests and provider contracts.

The current bug class is route identity leakage: the active UI can show one route while the model says another. Fix that class with explicit route state and prompt identity, not cosmetic text replacement.

## Verification Checklist

Run the smallest effective verification set:

```powershell
python -m unittest tests.test_web_backend.FluxioWebBackendTests.test_hermes_opencode_go_chat_uses_native_opencode_bridge tests.test_web_backend.FluxioWebBackendTests.test_agent_chat_command_runs_native_opencode_runtime tests.test_web_backend.FluxioWebBackendTests.test_chat_route_opencode_go_glm52_normalizes_to_installed_model_id -v
npm run frontend:build
```

Then verify like a user:

1. Open Agent Live through the full route URL.
2. Send: `what model/runtime are you using?`
3. Confirm the visible answer says Hermes + OpenCode Go + GLM-5.2 or `openrouter/z-ai/glm-5.2`.
4. Confirm the active chips do not show `gpt-5.5`.
5. Send a normal work prompt and confirm it produces a real answer.
6. Capture desktop and phone screenshots.
7. Inspect screenshots for one dominant object, visible composer, readable route chips, and no overlapping text.

## Browser Proof Requirement

Use the in-app Browser when possible. If Browser control is unavailable, use a normal browser window only after stating that the embedded browser hook is blocked.

Do not claim UI success from API output alone. API proof only proves the route; the operator judges the UI.

## Done Definition

The mission is done only when all are true:

- A separate worktree contains the changes.
- The Agent Live URL applies the Hermes/OpenCode-Go/GLM-5.2 route.
- The model self-report matches the selected route.
- The visible UI makes the current thread and next action obvious.
- Runtime proof is present but not visually dominant.
- Desktop and phone screenshots pass the visual audit.
- Focused tests and frontend build pass.
- The operator can pull from `master` without losing the deployed stable route.
