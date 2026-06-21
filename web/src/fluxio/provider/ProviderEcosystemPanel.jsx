import { StatusPill } from "../../../../desktop-ui/MissionControlPrimitives.jsx";
import { titleizeToken } from "../../../../desktop-ui/fluxioHelpers.js";

function asList(value) {
  return Array.isArray(value) ? value : [];
}

function asRecord(value) {
  return value && typeof value === "object" ? value : {};
}

function toneClass(tone) {
  return tone ? `tone-${tone}` : "";
}

export function ProviderEcosystemPanel({
  providerEcosystem = {},
  providers = [],
  sources = [],
  summary = {},
  updatePolicy = {},
}) {
  return (
    <section className="provider-ecosystem-panel" aria-label="Provider ecosystem and model catalog status">
      <div className="section-header">
        <div className="section-title-block">
          <p className="eyebrow">Provider ecosystem</p>
          <h3>Routes, catalogs, and safe updates</h3>
        </div>
        <StatusPill tone={Number(summary.routeReadyCount || 0) > 0 ? "good" : "warn"}>
          {summary.routeReadyCount || 0} route ready
        </StatusPill>
      </div>
      <div className="context-grid compact-metrics">
        <article className="context-item">
          <span>Tracked</span>
          <strong>{summary.totalProvidersTracked || providers.length}</strong>
          <p>{providerEcosystem.schemaVersion || "provider-ecosystem.v1"}</p>
        </article>
        <article className="context-item">
          <span>Implemented</span>
          <strong>{summary.implementedOrCredentialReady || 0}</strong>
          <p>Repo-supported or credential-ready routes.</p>
        </article>
        <article className="context-item">
          <span>Missing auth</span>
          <strong>{summary.missingAuthCount || 0}</strong>
          <p>{providerEcosystem.lastVerifiedAt ? `Verified ${providerEcosystem.lastVerifiedAt}` : "Waiting for live snapshot."}</p>
        </article>
      </div>
      <div className="drawer-list compact provider-ecosystem-list">
        {providers.length > 0 ? (
          providers.map(item => {
            const healthCheck = asRecord(item.healthCheck);
            const capabilityChips = asList(item.capabilityChips);
            return (
              <article
                className={`drawer-card ${toneClass(item.canRouteNow ? "good" : item.authPresent ? "neutral" : "warn")}`}
                key={`provider-ecosystem-${item.providerId}`}
              >
                <span>{item.routeRole || "provider route"}</span>
                <strong>{item.label || item.providerId}</strong>
                <p>
                  {titleizeToken(item.status || "unknown")} · {item.canRouteNow ? "route ready" : item.authPresent ? "auth present" : "auth or adapter needed"}
                </p>
                <div className="pill-row">
                  <span className="mini-pill">{item.providerId}</span>
                  <span className="mini-pill muted">{item.updateSource || "manual"}</span>
                  <span className="mini-pill muted">{item.observedRouteCount || 0} observed</span>
                </div>
                {healthCheck.status ? (
                  <div className="provider-health-note" aria-label={`${item.label || item.providerId} provider health check`}>
                    <strong>{titleizeToken(healthCheck.status)}</strong>
                    <p>{healthCheck.summary}</p>
                    <span>{healthCheck.safeNextStep}</span>
                    <div className="pill-row">
                      {asList(healthCheck.evidence).slice(0, 4).map(evidence => (
                        <span className="mini-pill muted" key={`${item.providerId}-evidence-${evidence}`}>{evidence}</span>
                      ))}
                    </div>
                  </div>
                ) : null}
                {capabilityChips.length > 0 ? (
                  <div className="pill-row provider-capability-chips" aria-label={`${item.label || item.providerId} model capabilities`}>
                    {capabilityChips.map(chip => (
                      <span className="mini-pill" key={`${item.providerId}-capability-${chip}`}>{chip}</span>
                    ))}
                  </div>
                ) : null}
                {item.updateSafety?.summary || asList(item.compatibilityWarnings).length > 0 ? (
                  <div className="update-safety-note" aria-label={`${item.label || item.providerId} compatibility warnings`}>
                    <strong>{item.updateSafety?.label || "Compatibility warning"}</strong>
                    <p>{item.updateSafety?.summary || asList(item.compatibilityWarnings)[0]}</p>
                    {asList(item.compatibilityWarnings).slice(0, 2).map(warning => (
                      <span key={`${item.providerId}-${warning}`}>{warning}</span>
                    ))}
                  </div>
                ) : null}
              </article>
            );
          })
        ) : (
          <article className="drawer-card">
            <strong>Provider ecosystem snapshot not loaded yet.</strong>
            <p>Run a live setup snapshot to show OpenAI, MiniMax, local, gateway, and future provider route status.</p>
          </article>
        )}
      </div>
      <div className="bridge-context-list">
        <div className="bridge-context-item">
          <span>Safe refresh policy</span>
          <p>
            {updatePolicy.requiresApprovalForDefaultChanges
              ? "Default route changes require approval."
              : "Default route approval policy is not loaded yet."}{" "}
            {updatePolicy.neverOverwriteUserModels
              ? "User-defined models are never overwritten."
              : "User-defined model overwrite policy is pending."}
          </p>
        </div>
        <div className="bridge-context-item">
          <span>Catalog sources</span>
          <p>
            {sources.length > 0
              ? sources.slice(0, 4).map(item => item.label || item.sourceId).join(", ")
              : "OpenCode, OpenClaw, LiteLLM, AI Gateway, and local model catalogs appear after a live snapshot."}
          </p>
        </div>
        {asList(updatePolicy.compatibilityWarnings).length > 0 ? (
          <div className="bridge-context-item update-policy-warnings">
            <span>Compatibility warnings</span>
            <p>{updatePolicy.compatibilityWarnings.slice(0, 3).join(" ")}</p>
          </div>
        ) : null}
      </div>
    </section>
  );
}

export default ProviderEcosystemPanel;
