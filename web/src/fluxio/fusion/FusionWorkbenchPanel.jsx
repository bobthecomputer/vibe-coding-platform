function toneClass(tone) {
  return tone ? `tone-${tone}` : "";
}

export function FusionWorkbenchPanel({ fusionWorkbench }) {
  if (!fusionWorkbench) return null;
  return (
    <section className="drawer-block">
      <h3>Fusion contract preview</h3>
      <p>
        Read-only Solantir, Mind Tower, and JBH-EAVEN rows are visible before live adapters so provenance and risk labels stay attached.
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
      </div>
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
