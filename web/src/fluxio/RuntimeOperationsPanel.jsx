function cx(...values) {
  return values.filter(Boolean).join(" ");
}

function asList(value) {
  return Array.isArray(value) ? value : [];
}

function RuntimeStatusBadge({ tone, label }) {
  const statusTone = tone === "good" ? "completed" : tone === "bad" ? "failed" : "paused";
  return <span className={cx("reference-status-badge", statusTone)}>{label}</span>;
}

export function RuntimeOperationsPanel({ runtimeOps = {}, onRequestAction, onSetSurface }) {
  const runtimeServices = asList(runtimeOps.services);
  const runtimeUpdates = asList(runtimeOps.updates);
  const runtimeSummary = runtimeOps.summary || {};

  return (
    <section className="reference-runtime-ops-panel">
      <div className="reference-builder-section-head">
        <div>
          <strong>Runtime operations</strong>
          <span>Install, update, verify, and lane health</span>
        </div>
        <div className="reference-inline-actions">
          <button className="reference-outline-button" onClick={() => onSetSurface?.("settings")} type="button">
            Runtime settings
          </button>
          <button className="reference-outline-button" onClick={() => onRequestAction?.("live:refresh-preview")} type="button">
            Refresh status
          </button>
        </div>
      </div>
      <div className="reference-settings-summary-grid runtime-summary">
        <article>
          <span>Managed services</span>
          <strong>{runtimeSummary.totalItems ?? runtimeServices.length}</strong>
          <p>{runtimeSummary.healthyCount ?? 0} healthy</p>
        </article>
        <article>
          <span>Needs attention</span>
          <strong>{runtimeSummary.needsAttentionCount ?? runtimeUpdates.length}</strong>
          <p>{runtimeUpdates.length} update candidate(s)</p>
        </article>
        <article>
          <span>Automatic verify</span>
          <strong>{runtimeOps.autoVerifyCount || 0}</strong>
          <p>Action(s) re-check setup after completion</p>
        </article>
        <article>
          <span>Update actions</span>
          <strong>{runtimeOps.updateActionCount || 0}</strong>
          <p>OpenClaw, Hermes, and supporting tools</p>
        </article>
      </div>
      <div className="reference-runtime-service-grid">
        {runtimeServices.length ? (
          runtimeServices.map(service => (
            <article className={cx("reference-runtime-service-card", `tone-${service.tone || "neutral"}`)} key={service.serviceId}>
              <div className="reference-builder-section-head">
                <div>
                  <strong>{service.label}</strong>
                  <span>{service.category}</span>
                </div>
                <RuntimeStatusBadge label={service.status} tone={service.tone} />
              </div>
              <div className="reference-runtime-version-row">
                <span>Current</span>
                <strong>{service.version || "not detected"}</strong>
                <span>Latest</span>
                <strong>{service.latestVersion || "unknown"}</strong>
              </div>
              <p>{service.details || "No runtime detail reported."}</p>
              {asList(service.actions).length ? (
                <div className="reference-runtime-action-list">
                  {asList(service.actions).slice(0, 3).map(action => (
                    <button
                      className="reference-outline-button"
                      key={`${service.serviceId}-${action.actionId}`}
                      onClick={() => onRequestAction?.("settings:run-action", { action })}
                      type="button"
                    >
                      <span>{action.label}</span>
                      {action.autoRunVerify ? <small>auto-verify</small> : null}
                    </button>
                  ))}
                </div>
              ) : null}
            </article>
          ))
        ) : (
          <article className="reference-runtime-service-card">
            <strong>No runtime services reported</strong>
            <p>Run setup verification to populate OpenClaw, Hermes, WSL, uv, and visual tooling status.</p>
          </article>
        )}
      </div>
    </section>
  );
}
