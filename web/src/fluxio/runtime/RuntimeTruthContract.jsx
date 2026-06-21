function asList(value) {
  return Array.isArray(value) ? value : [];
}

function titleizeToken(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, letter => letter.toUpperCase());
}

function runtimeLabel(runtimeId) {
  const value = String(runtimeId || "").toLowerCase();
  if (value === "openclaw") return "OpenClaw";
  if (value === "hermes") return "Hermes";
  return titleizeToken(runtimeId || "Runtime");
}

export function RuntimeTruthContract({ fusedRuntime }) {
  const runtime = fusedRuntime || {};
  const proofSignals = runtime.proofSignals || {};
  const latestProof = runtime.latestLaneProof || {};
  const lanes = asList(runtime.runtimeLanes)
    .map(item => item.label || runtimeLabel(item.runtimeId))
    .filter(Boolean);
  const fusionPoints = asList(runtime.fusionPoints).slice(0, 4).map(titleizeToken);
  const proofLanes = asList(latestProof.lanes).filter(item => item.runtimeId || item.label);
  const proofArtifactCount = Object.keys(latestProof.artifactPaths || {}).length;
  const readiness = latestProof.fusedRuntime?.readinessSummary || latestProof.readinessSummary || {};
  const readinessRows = asList(readiness.lanes);
  const laneReadinessRows = proofLanes.flatMap(item =>
    asList(item.readiness?.gates).map(gate => ({
      runtimeId: item.runtimeId || item.label,
      ...gate,
    })),
  );

  return (
    <div className="runtime-truth-contract" aria-label="Fused runtime truth contract">
      <span>Fused runtime truth contract</span>
      <strong>Role: {titleizeToken(proofSignals.fusedRuntimeRole || "supervisor_not_runtime_adapter")}</strong>
      <p>Runtime adapter added: {runtime.runtimeAdapterAdded ? "yes" : "no"} · Providers stay model routes, not runtime lanes.</p>
      <p>Executable lanes: {lanes.join(" · ") || "none recorded"}</p>
      <small>Normalizes {fusionPoints.join(" · ") || "mission control evidence"} before route promotion.</small>
      <div className="runtime-lane-proof-receipt">
        <b>Latest runtime lane proof</b>
        {latestProof.runId ? (
          <>
            <span>
              {latestProof.runId} · {latestProof.proofType || latestProof.mode || "proof recorded"}
            </span>
            <ul>
              {proofLanes.slice(0, 3).map(item => (
                <li key={`${item.runtimeId}-${item.provider}-${item.model}`}>
                  {runtimeLabel(item.runtimeId || item.label)} · {item.skill || "skill recorded"} · {item.provider || "provider"} / {item.model || "model"}
                </li>
              ))}
            </ul>
            <small>
              {proofArtifactCount} artifact{proofArtifactCount === 1 ? "" : "s"} · live runtime execution: {latestProof.safetyContract?.liveRuntimeExecution ? "yes" : "no"} · live model calls: {latestProof.safetyContract?.liveModelCalls ? "yes" : "no"} · runtime adapter added: {latestProof.safetyContract?.runtimeAdapterAdded ? "yes" : "no"}
            </small>
            <div className="runtime-readiness-contract" aria-label="Runtime readiness and recovery gates">
              <strong>Readiness: {titleizeToken(readiness.overallStatus || "contract_ready_live_unverified")}</strong>
              <p>
                Promotion blocked: {readiness.promotionBlocked ? "yes" : "no"} · Blocking gates {readiness.blockingGateCount || 0}
              </p>
              {readinessRows.length > 0 ? (
                <div className="runtime-readiness-summary-list">
                  {readinessRows.map(item => (
                    <article key={`runtime-readiness-summary-${item.runtimeId}`}>
                      <span>{runtimeLabel(item.runtimeId)}</span>
                      <b>{titleizeToken(item.status)}</b>
                      <small>{item.nextRecoveryAction || "No recovery action recorded."}</small>
                    </article>
                  ))}
                </div>
              ) : null}
              {laneReadinessRows.length > 0 ? (
                <div className="runtime-readiness-gate-list">
                  {laneReadinessRows.slice(0, 6).map(item => (
                    <article key={`${item.runtimeId}-${item.gateId}`}>
                      <span>{runtimeLabel(item.runtimeId)} · {titleizeToken(item.status)}</span>
                      <b>{item.label}</b>
                      <p>{item.recoveryAction}</p>
                      <small>{item.proofArtifact} · blocks promotion: {item.blocksPromotion ? "yes" : "no"}</small>
                    </article>
                  ))}
                </div>
              ) : null}
            </div>
          </>
        ) : (
          <span>No runtime lane proof receipt found yet. Run the deterministic lane proof harness to attach one.</span>
        )}
      </div>
    </div>
  );
}

export default RuntimeTruthContract;
