export const FUSION_CONTRACT_VERSION = "fluxio-fusion-fixture/v1";

export const FUSION_COLLECTION_MODES = Object.freeze([
  "seeded",
  "read-only-adapter",
  "live",
  "blocked",
]);

export const FUSION_RISK_LABELS = Object.freeze([
  "no-trading-execution",
  "no-credential-copy",
  "synthetic-red-team-only",
  "stale-mirror",
  "read-only",
]);

export const FUSION_FIXTURES = Object.freeze([
  {
    id: "solantir-signal-contract",
    sourceProject: "Solantir",
    sourcePath: "C:\\Users\\paul\\projects\\Solantir\\packages\\contracts\\src\\solantir.ts",
    sourceHashPrefix: "77FF86081481",
    collectionMode: "read-only-adapter",
    riskLabel: "no-trading-execution",
    status: "ready-for-contract-fixture",
    title: "Explainable market signal snapshot",
    summary:
      "Imports Solantir entity, observation, forecast, provenance, and source-health vocabulary as read-only Fluxio fixture rows.",
    proofNeed:
      "Every score must keep factors, drivers, confidence, timestamp, and no broker/order-routing action.",
    nextSlice: "Build a fixture-backed signal card from Solantir contracts and legacy signal drivers.",
    lastVerifiedAt: "2026-06-21",
  },
  {
    id: "mindtower-source-health",
    sourceProject: "Mind Tower",
    sourcePath: "C:\\Users\\paul\\projects\\mind-tower\\packages\\shared\\src\\models.ts",
    sourceHashPrefix: "DE7D0D085B6E",
    collectionMode: "read-only-adapter",
    riskLabel: "no-credential-copy",
    status: "ready-for-adapter-shape",
    title: "Synology source and review health",
    summary:
      "Maps sources, watch rules, digests, alerts, delivery targets, operators, summary jobs, and normalized events into Fluxio bridge status.",
    proofNeed:
      "Read-only SQLite or fixture import must mask credentials and report unavailable NAS data honestly.",
    nextSlice: "Add a read-only adapter shape for records, events, and runtime_state.",
    lastVerifiedAt: "2026-06-21",
  },
  {
    id: "jbheaven-defensive-harness",
    sourceProject: "JBH-EAVEN",
    sourcePath: "C:\\Users\\paul\\projects\\Jbheaven\\scripts\\red-team-harness.mjs",
    sourceHashPrefix: "0038D908C240",
    collectionMode: "seeded",
    riskLabel: "synthetic-red-team-only",
    status: "fixture-only",
    title: "Deterministic defensive red-team proof lane",
    summary:
      "Keeps JBH-EAVEN red-team proof synthetic, deterministic, scored, and transcript-backed before any live model route is used.",
    proofNeed:
      "Runs must record scenario seed, sampled probes, guardrails, detector coverage, transcript path, and boundary labels.",
    nextSlice: "Emit Fluxio proof artifacts from a deterministic synthetic harness runner.",
    lastVerifiedAt: "2026-06-21",
  },
  {
    id: "nas-mirror-policy",
    sourceProject: "NAS mirrors",
    sourcePath: "Y:\\projects",
    sourceHashPrefix: "",
    collectionMode: "blocked",
    riskLabel: "stale-mirror",
    status: "needs-policy",
    title: "Mirror authority and cleanup policy",
    summary:
      "Marks local git clones as code source of truth and NAS folders as runtime proof, historical artifacts, or recovery mirrors.",
    proofNeed:
      "Mirror cleanup must be report-only until the user explicitly approves deletes or remote production changes.",
    nextSlice: "Add a hash/check report that identifies authoritative, archival, and divergent mirrors without copying files.",
    lastVerifiedAt: "2026-06-21",
  },
]);

export function buildFusionWorkbench(fixtures = FUSION_FIXTURES) {
  const rows = Array.isArray(fixtures) ? fixtures : [];
  const projects = [...new Set(rows.map(item => item.sourceProject).filter(Boolean))];
  const ready = rows.filter(item =>
    ["ready-for-contract-fixture", "ready-for-adapter-shape"].includes(item.status),
  );
  const blocked = rows.filter(item => item.collectionMode === "blocked" || item.status === "needs-policy");
  const proofRequired = rows.filter(item => item.proofNeed);
  return {
    schemaVersion: FUSION_CONTRACT_VERSION,
    collectionModes: FUSION_COLLECTION_MODES,
    riskLabels: FUSION_RISK_LABELS,
    summary: {
      totalRows: rows.length,
      projects: projects.length,
      readyRows: ready.length,
      blockedRows: blocked.length,
      proofRequiredRows: proofRequired.length,
    },
    rows,
    acceptanceRules: [
      "Every row must expose sourceProject, sourcePath, collectionMode, riskLabel, and lastVerifiedAt.",
      "Seeded or read-only rows must not imply live data, trading execution, credential access, or offensive red-team execution.",
      "Blocked rows must describe the missing policy or proof instead of inventing live status.",
    ],
  };
}
