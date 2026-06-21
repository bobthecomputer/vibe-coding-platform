function toneClass(tone) {
  return tone ? `tone-${tone}` : "";
}

function statusTone(status) {
  if (status === "passed" || status === "ready") return "good";
  if (status === "blocked" || status === "error") return "bad";
  if (status === "needed" || status === "gated" || status === "missing") return "warn";
  return "neutral";
}

export function FusionWorkbenchPanel({ fusionWorkbench }) {
  if (!fusionWorkbench) return null;
  const adapter = fusionWorkbench.adapter || {};
  const adapterSummary = fusionWorkbench.adapterSummary || {};
  const nextLane = fusionWorkbench.migrationLanes.find(
    item => item.title === fusionWorkbench.summary.nextMigrationLane,
  ) || fusionWorkbench.migrationLanes[0];
  return (
    <section className="drawer-block">
      <h3>Fusion migration workbench</h3>
      <p>
        Read-only Solantir, Mind Tower, and JBH-EAVEN rows stay gated until source truth, adapter safety, and proof artifacts are visible.
      </p>
      <div className="context-grid compact-metrics">
        <article className="context-item">
          <span>Rows</span>
          <strong>{fusionWorkbench.summary.totalRows}</strong>
        </article>
        <article className="context-item">
          <span>Ready</span>
          <strong>{fusionWorkbench.summary.readyRows}</strong>
        </article>
        <article className="context-item">
          <span>Blocked</span>
          <strong>{fusionWorkbench.summary.blockedRows}</strong>
        </article>
        <article className="context-item">
          <span>Lanes</span>
          <strong>{fusionWorkbench.summary.migrationLaneCount}</strong>
        </article>
        <article className="context-item">
          <span>Signals</span>
          <strong>{fusionWorkbench.summary.signalSnapshotCount || 0}</strong>
        </article>
        <article className="context-item">
          <span>Gates</span>
          <strong>
            {fusionWorkbench.summary.passedGateCount}/{fusionWorkbench.summary.gateCount}
          </strong>
        </article>
      </div>
      <section className="fusion-phase-strip" aria-label="Fusion migration phases">
        {fusionWorkbench.migrationPhases.map(phase => (
          <article className={`fusion-phase-card ${toneClass(statusTone(phase.status))}`} key={phase.id}>
            <span>{phase.status}</span>
            <strong>{phase.label}</strong>
            <p>{phase.summary}</p>
            <em>{phase.evidence}</em>
          </article>
        ))}
      </section>
      <section className="fusion-adapter-panel" aria-label="Mind Tower read-only adapter status">
        <div className="builder-live-review-panel-head compact">
          <div>
            <h4>Mind Tower adapter truth</h4>
            <p>{adapterSummary.detail || "Fixture rows remain visible until a read-only adapter snapshot is attached."}</p>
          </div>
          <span className={`mini-pill ${toneClass(statusTone(adapterSummary.status))}`}>
            {adapterSummary.status || "fixture-only"}
          </span>
        </div>
        <div className="context-grid compact-metrics">
          <article className="context-item">
            <span>Available</span>
            <strong>{adapterSummary.available ? "yes" : "no"}</strong>
          </article>
          <article className="context-item">
            <span>Read-only</span>
            <strong>{adapterSummary.readOnly ? "yes" : "no"}</strong>
          </article>
          <article className="context-item">
            <span>Writes</span>
            <strong>{adapterSummary.writeActions ?? 0}</strong>
          </article>
          <article className="context-item">
            <span>Records</span>
            <strong>{adapterSummary.recordTotal ?? 0}</strong>
          </article>
          <article className="context-item">
            <span>Events</span>
            <strong>{adapterSummary.eventCount ?? 0}</strong>
          </article>
          <article className="context-item">
            <span>Runtime</span>
            <strong>{adapterSummary.runtimeStateCount ?? 0}</strong>
          </article>
        </div>
        <div className="fusion-adapter-preview-grid">
          <article className="fusion-adapter-preview-card">
            <span>Source health</span>
            {(adapter.sourceHealth || []).length ? (
              (adapter.sourceHealth || []).slice(0, 3).map(item => (
                <p key={`source-health-${item.id}`}>
                  <strong>{item.label}</strong> {item.status}
                </p>
              ))
            ) : (
              <p>No source rows attached.</p>
            )}
          </article>
          <article className="fusion-adapter-preview-card">
            <span>Summary jobs</span>
            {(adapter.summaryJobs || []).length ? (
              (adapter.summaryJobs || []).slice(0, 3).map(item => (
                <p key={`summary-job-${item.id}`}>
                  <strong>{item.label}</strong> {item.status}
                </p>
              ))
            ) : (
              <p>No review jobs attached.</p>
            )}
          </article>
          <article className="fusion-adapter-preview-card">
            <span>Recent evidence</span>
            {(adapter.recentEvents || []).length ? (
              (adapter.recentEvents || []).slice(0, 3).map(item => (
                <p key={`recent-event-${item.id}`}>
                  <strong>{item.sourceType}</strong> score {item.priorityScore}
                </p>
              ))
            ) : (
              <p>No recent events attached.</p>
            )}
          </article>
        </div>
        <p className="fusion-source-path">
          {adapterSummary.label || "mindtower-readonly-sqlite"} · {adapterSummary.sourcePath || "adapter path unavailable"}
        </p>
      </section>
      {nextLane ? (
        <section className="fusion-next-lane" aria-label="Next fusion migration lane">
          <div>
            <span>Next safe slice</span>
            <strong>{nextLane.title}</strong>
            <p>{nextLane.safeSlice}</p>
          </div>
          <div className="fusion-gate-list">
            {(nextLane.promotionGates || []).map(gate => (
              <span className={`mini-pill ${toneClass(statusTone(gate.status))}`} key={gate.id}>
                {gate.status}: {gate.label}
              </span>
            ))}
          </div>
        </section>
      ) : null}
      <section className="fusion-signal-panel" aria-label="Explainable Solantir signals">
        <div className="builder-live-review-panel-head compact">
          <div>
            <h4>Explainable Solantir signals</h4>
            <p>Fixture-backed signals only; no broker, no order routing, not investment advice.</p>
          </div>
          <span className="mini-pill muted">no-trading-execution</span>
        </div>
        <div className="fusion-signal-list">
          {fusionWorkbench.signalSnapshots.map(item => (
            <article className="fusion-signal-card" key={item.id}>
              <span>{item.collectionMode} · {item.direction}</span>
              <strong>{item.entity}</strong>
              <div className="pill-row">
                <span className="mini-pill">score {item.score}</span>
                <span className="mini-pill muted">confidence {Math.round(item.confidence * 100)}%</span>
                <span className="mini-pill muted">{item.riskLabel}</span>
              </div>
              <p>{item.topDrivers[0]}</p>
              <div className="fusion-factor-list">
                {item.factors.slice(0, 3).map(factor => (
                  <span key={`${item.id}-${factor.name}`}>{factor.name}: {factor.contribution}</span>
                ))}
              </div>
              <p className="fusion-source-path">{item.timestamp} · {item.sourcePath}</p>
            </article>
          ))}
        </div>
      </section>
      <div className="drawer-list fusion-migration-list">
        {fusionWorkbench.migrationLanes.map(item => (
          <article className="drawer-card fusion-migration-card" key={`fusion-migration-${item.id}`}>
            <span>{item.sourcePair} · {item.migrationStatus}</span>
            <strong>{item.title}</strong>
            <p>{item.duplicateArea}</p>
            <div className="pill-row">
              <span className="mini-pill">{item.targetRuntime}</span>
              <span className="mini-pill muted">{item.ownerRole}</span>
            </div>
            <p>{item.safeSlice}</p>
            <div className="fusion-gate-list">
              {(item.promotionGates || []).map(gate => (
                <span className={`mini-pill ${toneClass(statusTone(gate.status))}`} key={`${item.id}-${gate.id}`}>
                  {gate.status}: {gate.label}
                </span>
              ))}
            </div>
            <p className="fusion-source-path">{item.proofAction}</p>
          </article>
        ))}
      </div>
      <div className="drawer-list">
        {fusionWorkbench.rows.map(item => (
          <article
            className={`drawer-card fusion-contract-card ${toneClass(item.collectionMode === "blocked" ? "warn" : "neutral")}`}
            key={`fusion-contract-${item.id}`}
          >
            <span>{item.sourceProject} · {item.collectionMode}</span>
            <strong>{item.title}</strong>
            <p>{item.summary}</p>
            <div className="pill-row">
              <span className="mini-pill">{item.riskLabel}</span>
              <span className="mini-pill muted">{item.status}</span>
              <span className="mini-pill muted">{item.lastVerifiedAt}</span>
            </div>
            <p>{item.proofNeed}</p>
            <p className="fusion-source-path">{item.sourcePath}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

export default FusionWorkbenchPanel;
