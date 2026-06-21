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
            <span>{latestProof.runId} · {latestProof.mode || "proof recorded"}</span>
            <ul>
              {proofLanes.slice(0, 3).map(item => (
                <li key={`${item.runtimeId}-${item.provider}-${item.model}`}>
                  {runtimeLabel(item.runtimeId || item.label)} · {item.skill || "skill recorded"} · {item.provider || "provider"} / {item.model || "model"}
                </li>
              ))}
            </ul>
            <small>
              {proofArtifactCount} artifact{proofArtifactCount === 1 ? "" : "s"} · live model calls: {latestProof.safetyContract?.liveModelCalls ? "yes" : "no"} · runtime adapter added: {latestProof.safetyContract?.runtimeAdapterAdded ? "yes" : "no"}
            </small>
          </>
        ) : (
          <span>No runtime lane proof receipt found yet. Run the deterministic lane proof harness to attach one.</span>
        )}
      </div>
    </div>
  );
}

export default RuntimeTruthContract;
