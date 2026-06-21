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
- whether credentials are ready separately from route-smoke proof;
- whether the provider can be routed now after observed route proof;
- observed local route count from fused-runtime proof;
- provider catalog sources and update policy;
- source verification gate state, primary source URLs, and default-change block reason;
- next actions for missing runtime/auth/catalog refresh.

This is intentionally not a live catalog fetch. Live refresh should be a separate approval-aware workflow because it may change available model IDs, pricing, and default routes.

## Routing Rules

- `openai` and `minimax` are repo-supported when auth/config is present, but they are not route-ready until a route smoke proof has been observed.
- `anthropic` and `openrouter` are credential-ready external routes, not fully proven runtime defaults.
- `google`, `local`, `vercel-ai-gateway`, and `litellm` are planned adapter/gateway tracks until tested in Fluxio.
- Dynamic provider catalogs must never overwrite user-defined model IDs without approval.
- Provider source freshness ages from the current run date. Stale or expired sources keep the source verification gate in review-required mode.
- Catalog refresh reports are review-only proof artifacts. They must keep `writesDefaults=false`, `writesCredentials=false`, `writesProviderRegistry=false`, and `defaultChangeAllowed=false`.

## Implemented PR100 Slice

1. Provider drawer shows a visible source verification gate with primary source URLs, schema version, review counts, and the exact verification command.
2. Builder provider-flight card shows the source gate state alongside route exposure, freshness, missing auth, and review-only refresh proof.
3. `scripts/provider_catalog_refresh.py` writes the same source verification gate into the review artifact.
4. Mission/web reconciliation keeps `credentialReady` separate from `canRouteNow` and requires observed route-smoke proof before route promotion.

## Next PRs

1. Load the latest reviewed provider catalog artifact back into the runtime snapshot after human approval.
2. Add provider capability metadata refresh for context window, price band, speed band, tool support, vision, image, and local/private mode.
3. Fold provider/harness success data into the benchmark board so route choices are practical, not leaderboard-only.
4. Add live AI Gateway fetch proof in a separate PR when network variability is acceptable for that proof run.
