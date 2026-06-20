# Provider Ecosystem Update Plan

Date: 2026-06-21

## Goal

Fluxio should treat providers as an updateable ecosystem, not as a small hardcoded picker. The app should show what is supported now, what is credential-ready, what is planned, and which provider catalogs should be refreshed before changing defaults.

## Verified Sources

- OpenCode models docs: https://opencode.ai/docs/models/
  - OpenCode says it uses AI SDK and Models.dev to support 75+ providers and local models.
- Crush repository: https://github.com/charmbracelet/crush
  - Crush documents local provider auto-discovery for Ollama, LM Studio, LiteLLM, and OMLX.
- OpenClaw model providers: https://docs.openclaw.ai/concepts/model-providers
  - OpenClaw exposes a provider directory and guarded network rules for configured provider origins.
- Vercel AI Gateway models: https://ai-gateway.vercel.sh/v1/models
  - Vercel documents this endpoint as a dynamic model source for IDs, pricing, context windows, and capabilities.
- LiteLLM providers: https://docs.litellm.ai/docs/providers
  - LiteLLM remains a broad provider/gateway reference for remote, local, speech, and image routes.

## Implemented Contract

`ControlRoomStore.build_snapshot()` now includes `providerEcosystem`:

- tracked providers and their current Fluxio support level;
- whether auth/config is present;
- whether the provider can be routed now;
- observed local route count from fused-runtime proof;
- provider catalog sources and update policy;
- next actions for missing runtime/auth/catalog refresh.

This is intentionally not a live catalog fetch. Live refresh should be a separate approval-aware workflow because it may change available model IDs, pricing, and default routes.

## Routing Rules

- `openai` and `minimax` are repo-supported only when auth/config is present.
- `anthropic` and `openrouter` are credential-ready external routes, not fully proven runtime defaults.
- `google`, `local`, `vercel-ai-gateway`, and `litellm` are planned adapter/gateway tracks until tested in Fluxio.
- Dynamic provider catalogs must never overwrite user-defined model IDs without approval.

## Next PRs

1. Display `providerEcosystem` in the Settings/Runtime surfaces with clear update actions.
2. Add a safe catalog refresh command that writes a reviewable artifact before updating defaults.
3. Add provider capability metadata for context window, price band, speed band, tool support, vision, image, and local/private mode.
4. Fold provider/harness success data into the benchmark board so route choices are practical, not leaderboard-only.
