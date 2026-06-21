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
  const lanes = asList(runtime.runtimeLanes)
    .map(item => item.label || runtimeLabel(item.runtimeId))
    .filter(Boolean);
  const fusionPoints = asList(runtime.fusionPoints).slice(0, 4).map(titleizeToken);

  return (
    <div className="runtime-truth-contract" aria-label="Fused runtime truth contract">
      <span>Fused runtime truth contract</span>
      <strong>Role: {titleizeToken(proofSignals.fusedRuntimeRole || "supervisor_not_runtime_adapter")}</strong>
      <p>Runtime adapter added: {runtime.runtimeAdapterAdded ? "yes" : "no"} · Providers stay model routes, not runtime lanes.</p>
      <p>Executable lanes: {lanes.join(" · ") || "none recorded"}</p>
      <small>Normalizes {fusionPoints.join(" · ") || "mission control evidence"} before route promotion.</small>
    </div>
  );
}

export default RuntimeTruthContract;
