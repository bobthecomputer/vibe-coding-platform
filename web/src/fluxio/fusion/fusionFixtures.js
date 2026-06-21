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

export const FUSION_MIGRATION_PHASES = Object.freeze([
  {
    id: "inventory",
    label: "Inventory",
    status: "passed",
    summary: "Source-of-truth paths, stale mirrors, and high-risk duplicates are mapped.",
    evidence: "docs/SOLANTIR_MINDTOWER_JBHEAVEN_FUSION_INVENTORY.md",
  },
  {
    id: "read-only-adapters",
    label: "Read-only adapters",
    status: "active",
    summary: "Solantir signals and Mind Tower health can be inspected without write actions.",
    evidence: "web/src/fluxio/fusion/fusionFixtures.js",
  },
  {
    id: "promotion-proof",
    label: "Promotion proof",
    status: "gated",
    summary: "Each lane needs proof gates before any live adapter or cleanup action is enabled.",
    evidence: "tests/test_fusion_fixture_contract.py",
  },
  {
    id: "cleanup",
    label: "Mirror cleanup",
    status: "blocked",
    summary: "NAS mirror cleanup remains report-only until explicit destructive approval exists.",
    evidence: "docs/SOLANTIR_MINDTOWER_JBHEAVEN_FUSION_INVENTORY_DATA.json",
  },
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

export const FUSION_MIGRATION_LANES = Object.freeze([
  {
    id: "terminal-workbench-shell",
    phaseId: "promotion-proof",
    title: "Terminal and operator workbench shell",
    sourcePair: "Solantir Terminal -> Fluxio Builder",
    duplicateArea: "Terminal navigation, workspace switching, command review, and proof surfaces.",
    migrationStatus: "ready-for-ui-adapter",
    targetRuntime: "Fluxio supervision shell",
    safeSlice:
      "Port only read-only terminal/workspace metadata into Builder cards; leave command execution inside Fluxio approvals.",
    proofAction: "Show Solantir source path, Fluxio drawer card, and no direct shell execution controls.",
    ownerRole: "UI reviewer",
    promotionGates: [
      {
        id: "source-hash",
        status: "passed",
        label: "Authoritative source hash recorded",
        evidence: "docs/SOLANTIR_MINDTOWER_JBHEAVEN_FUSION_INVENTORY_DATA.json",
      },
      {
        id: "no-shell-execution",
        status: "passed",
        label: "No direct shell execution controls",
        evidence: "web/src/fluxio/fusion/fusionFixtures.js",
      },
      {
        id: "browser-proof",
        status: "needed",
        label: "Browser proof after UI adapter",
        evidence: "artifacts/pr89-fusion-migration-gates/",
      },
    ],
  },
  {
    id: "synology-monitoring-events",
    phaseId: "read-only-adapters",
    title: "Synology monitoring and event records",
    sourcePair: "Mind Tower SQLite/runtime_state -> Fluxio bridge health",
    duplicateArea: "Source health, watch rules, normalized events, digests, alerts, and review jobs.",
    migrationStatus: "adapter-contract-next",
    targetRuntime: "Read-only storage bridge",
    safeSlice:
      "Define a read-only adapter payload for sources, events, and jobs with credentials masked before UI import.",
    proofAction: "Fixture must include masked credentials, unavailable NAS state, and zero write actions.",
    ownerRole: "Runtime engineer",
    promotionGates: [
      {
        id: "readonly-open",
        status: "passed",
        label: "SQLite opens in read-only mode",
        evidence: "src/grant_agent/mindtower_fusion.py",
      },
      {
        id: "credential-mask",
        status: "passed",
        label: "Credential-like fields are masked",
        evidence: "tests/test_mindtower_fusion_adapter.py",
      },
      {
        id: "nas-policy",
        status: "needed",
        label: "NAS authority policy before cleanup",
        evidence: "docs/SOLANTIR_MINDTOWER_JBHEAVEN_FUSION_INVENTORY.md",
      },
    ],
  },
  {
    id: "signal-provenance-board",
    phaseId: "read-only-adapters",
    title: "Explainable signal provenance board",
    sourcePair: "Solantir contracts/signals -> Fluxio fusion rows",
    duplicateArea: "Entity, observation, forecast, factor, driver, confidence, timestamp, and source health models.",
    migrationStatus: "fixture-import-next",
    targetRuntime: "Read-only signal importer",
    safeSlice:
      "Import fixture-backed signal snapshots with factor attribution and explicit no-broker/no-order-routing labels.",
    proofAction: "Every signal row must show factors, source path, timestamp, confidence, and no-trading-execution risk.",
    ownerRole: "Researcher",
    promotionGates: [
      {
        id: "factor-attribution",
        status: "passed",
        label: "Factors, drivers, and confidence visible",
        evidence: "web/src/fluxio/fusion/fusionFixtures.js",
      },
      {
        id: "execution-block",
        status: "passed",
        label: "No broker or order-routing action",
        evidence: "tests/test_fusion_fixture_contract.py",
      },
      {
        id: "live-importer",
        status: "blocked",
        label: "Live importer blocked until source-health proof",
        evidence: "docs/SOLANTIR_MINDTOWER_JBHEAVEN_FUSION_INVENTORY.md",
      },
    ],
  },
  {
    id: "synthetic-redteam-proof",
    phaseId: "promotion-proof",
    title: "Synthetic red-team proof lane",
    sourcePair: "JBH-EAVEN harness -> Fluxio proof artifacts",
    duplicateArea: "Scenario metadata, safe probe transcripts, detector coverage, refusal scoring, and proof links.",
    migrationStatus: "proof-runner-next",
    targetRuntime: "Controlled synthetic verifier",
    safeSlice:
      "Emit deterministic, fictional red-team proof packets without live targets, secrets, evasion, malware, or exfiltration.",
    proofAction: "Attach scenario seed, boundary labels, prompt, model response, score, transcript, and artifact path.",
    ownerRole: "Red-team evaluator",
    promotionGates: [
      {
        id: "synthetic-scope",
        status: "passed",
        label: "Synthetic and authorized scope labels",
        evidence: "artifacts/red-team/worker-f-jbheaven-safe-scenario-20260621/scenario.json",
      },
      {
        id: "taxonomy-coverage",
        status: "passed",
        label: "Taxonomy coverage and refusal scoring",
        evidence: "tests/test_redteam_proof_board.py",
      },
      {
        id: "live-route",
        status: "needed",
        label: "OpenCodeGo route transcript before live model claims",
        evidence: "artifacts/red-team/worker-f-jbheaven-safe-scenario-20260621/",
      },
    ],
  },
]);

export const SOLANTIR_SIGNAL_SNAPSHOTS = Object.freeze([
  {
    id: "solantir-signal-energy-resilience",
    entity: "Fictional Energy Grid Supplier",
    direction: "upside-watch",
    score: 72,
    confidence: 0.68,
    timestamp: "2026-06-21T00:00:00+02:00",
    collectionMode: "seeded",
    riskLabel: "no-trading-execution",
    sourcePath: "C:\\Users\\paul\\projects\\Solantir\\legacy\\osint-platform\\backend\\solantir_api\\signals.py",
    factors: [
      { name: "supply-chain resilience", weight: 0.34, contribution: 18 },
      { name: "defensive infrastructure demand", weight: 0.28, contribution: 15 },
      { name: "source freshness", weight: 0.18, contribution: 8 },
    ],
    topDrivers: [
      "Synthetic demand signal improved after maintenance-window reporting.",
      "Source health remains sufficient for explainability, not live execution.",
    ],
    safetyLabels: ["no broker", "no order routing", "not investment advice"],
  },
  {
    id: "solantir-signal-logistics-pressure",
    entity: "Fictional Logistics Corridor Index",
    direction: "risk-watch",
    score: 41,
    confidence: 0.61,
    timestamp: "2026-06-21T00:00:00+02:00",
    collectionMode: "seeded",
    riskLabel: "no-trading-execution",
    sourcePath: "C:\\Users\\paul\\projects\\Solantir\\packages\\contracts\\src\\solantir.ts",
    factors: [
      { name: "event pressure", weight: 0.36, contribution: -14 },
      { name: "forecast dispersion", weight: 0.24, contribution: -9 },
      { name: "confidence floor", weight: 0.2, contribution: 6 },
    ],
    topDrivers: [
      "Synthetic observation volatility increased relative to the seeded baseline.",
      "Forecast confidence remains above the fixture cutoff but below action quality.",
    ],
    safetyLabels: ["no broker", "no order routing", "not investment advice"],
  },
  {
    id: "solantir-signal-source-health",
    entity: "Solantir Source Health Composite",
    direction: "neutral",
    score: 55,
    confidence: 0.74,
    timestamp: "2026-06-21T00:00:00+02:00",
    collectionMode: "read-only-adapter",
    riskLabel: "no-trading-execution",
    sourcePath: "C:\\Users\\paul\\projects\\Solantir\\packages\\contracts\\src\\solantir.ts",
    factors: [
      { name: "provenance coverage", weight: 0.4, contribution: 16 },
      { name: "staleness penalty", weight: 0.22, contribution: -5 },
      { name: "driver explainability", weight: 0.24, contribution: 11 },
    ],
    topDrivers: [
      "Canonical contract fields cover observation, forecast, source, and provenance.",
      "No live market feed or execution bridge is attached to this fixture.",
    ],
    safetyLabels: ["no broker", "no order routing", "not investment advice"],
  },
]);

function normalizeAdapter(adapter, rows) {
  if (adapter && typeof adapter === "object") {
    return adapter;
  }
  const rowAdapter = rows.find(item => item?.adapter && typeof item.adapter === "object")?.adapter;
  return rowAdapter || null;
}

function summarizeAdapter(adapter) {
  if (!adapter) {
    return {
      label: "Fixture-only",
      available: false,
      status: "fixture-only",
      detail: "No live Mind Tower adapter snapshot was attached; Fluxio is showing safe fixture rows only.",
      readOnly: true,
      writeActions: 0,
      recordTotal: 0,
      eventCount: 0,
      runtimeStateCount: 0,
      credentialCount: 0,
      sourceHealthCount: 0,
      summaryJobCount: 0,
      recentEventCount: 0,
      runtimePreviewCount: 0,
    };
  }
  const recordCounts = adapter.recordCounts && typeof adapter.recordCounts === "object"
    ? adapter.recordCounts
    : {};
  const recordTotal = Object.values(recordCounts).reduce(
    (total, value) => total + Number(value || 0),
    0,
  );
  return {
    label: adapter.adapterId || "mindtower-readonly-sqlite",
    available: Boolean(adapter.available),
    status: adapter.status || "unknown",
    detail: adapter.detail || "",
    sourcePath: adapter.sourcePath || "",
    readOnly: adapter.readOnly !== false,
    writeActions: Number(adapter.writeActions || 0),
    credentialValuesExposed: Boolean(adapter.credentialValuesExposed),
    recordTotal,
    eventCount: Number(adapter.eventCount || 0),
    runtimeStateCount: Number(adapter.runtimeStateCount || 0),
    credentialCount: Array.isArray(adapter.credentialSummary) ? adapter.credentialSummary.length : 0,
    sourceHealthCount: Array.isArray(adapter.sourceHealth) ? adapter.sourceHealth.length : 0,
    summaryJobCount: Array.isArray(adapter.summaryJobs) ? adapter.summaryJobs.length : 0,
    recentEventCount: Array.isArray(adapter.recentEvents) ? adapter.recentEvents.length : 0,
    runtimePreviewCount: Array.isArray(adapter.runtimeStatePreview) ? adapter.runtimeStatePreview.length : 0,
  };
}

export function buildFusionWorkbench(fixtures = FUSION_FIXTURES) {
  const snapshot = fixtures && typeof fixtures === "object" && !Array.isArray(fixtures) ? fixtures : null;
  const providedRows = Array.isArray(fixtures)
    ? fixtures
    : Array.isArray(snapshot?.rows)
      ? snapshot.rows
      : [];
  const rowMap = new Map(FUSION_FIXTURES.map(item => [item.id, item]));
  for (const row of providedRows) {
    if (row?.id) {
      rowMap.set(row.id, row);
    }
  }
  const rows = [...rowMap.values()];
  const adapter = normalizeAdapter(snapshot?.adapter, rows);
  const adapterSummary = summarizeAdapter(adapter);
  const migrationLanes = FUSION_MIGRATION_LANES;
  const phaseOrder = new Map(FUSION_MIGRATION_PHASES.map((phase, index) => [phase.id, index]));
  const sortedLanes = [...migrationLanes].sort(
    (left, right) => (phaseOrder.get(left.phaseId) ?? 99) - (phaseOrder.get(right.phaseId) ?? 99),
  );
  const gateRows = migrationLanes.flatMap(lane =>
    (lane.promotionGates || []).map(gate => ({
      ...gate,
      laneId: lane.id,
      laneTitle: lane.title,
      phaseId: lane.phaseId,
    })),
  );
  const projects = [...new Set(rows.map(item => item.sourceProject).filter(Boolean))];
  const ready = rows.filter(item =>
    ["ready-for-contract-fixture", "ready-for-adapter-shape"].includes(item.status),
  );
  const blocked = rows.filter(item => item.collectionMode === "blocked" || item.status === "needs-policy");
  const proofRequired = rows.filter(item => item.proofNeed);
  const nextLane =
    sortedLanes.find(item => item.migrationStatus.includes("next")) || sortedLanes[0];
  const activePhase =
    FUSION_MIGRATION_PHASES.find(phase => phase.status === "active") ||
    FUSION_MIGRATION_PHASES[0];
  const passedGates = gateRows.filter(gate => gate.status === "passed");
  const blockedGates = gateRows.filter(gate => gate.status === "blocked");
  const neededGates = gateRows.filter(gate => gate.status === "needed");
  const promotionReadyLanes = migrationLanes.filter(lane =>
    (lane.promotionGates || []).every(gate => gate.status === "passed"),
  );
  const signalSnapshots = Array.isArray(snapshot?.signalSnapshots) && snapshot.signalSnapshots.length > 0
    ? snapshot.signalSnapshots
    : SOLANTIR_SIGNAL_SNAPSHOTS;
  return {
    schemaVersion: FUSION_CONTRACT_VERSION,
    collectionModes: FUSION_COLLECTION_MODES,
    riskLabels: FUSION_RISK_LABELS,
    migrationPhases: FUSION_MIGRATION_PHASES,
    summary: {
      totalRows: rows.length,
      projects: projects.length,
      readyRows: ready.length,
      blockedRows: blocked.length,
      proofRequiredRows: proofRequired.length,
      migrationLaneCount: migrationLanes.length,
      nextMigrationLane: nextLane?.title || "",
      signalSnapshotCount: signalSnapshots.length,
      phaseCount: FUSION_MIGRATION_PHASES.length,
      activePhase: activePhase?.label || "",
      gateCount: gateRows.length,
      passedGateCount: passedGates.length,
      neededGateCount: neededGates.length,
      blockedGateCount: blockedGates.length,
      promotionReadyLaneCount: promotionReadyLanes.length,
      adapterAvailable: adapterSummary.available,
      adapterStatus: adapterSummary.status,
      adapterRecordTotal: adapterSummary.recordTotal,
      adapterWriteActions: adapterSummary.writeActions,
    },
    rows,
    migrationLanes: sortedLanes,
    gateRows,
    adapter,
    adapterSummary,
    signalSnapshots,
    acceptanceRules: [
      "Every row must expose sourceProject, sourcePath, collectionMode, riskLabel, and lastVerifiedAt.",
      "Seeded or read-only rows must not imply live data, trading execution, credential access, or offensive red-team execution.",
      "Blocked rows must describe the missing policy or proof instead of inventing live status.",
      "Migration lanes must name duplicate areas, safe slices, target runtime, proof action, and owner role before code is copied.",
      "Solantir signal snapshots must show factors, drivers, confidence, timestamp, source path, and no-trading-execution labels.",
      "Promotion gates must show passed, needed, or blocked status before a lane can move beyond read-only fixture work.",
    ],
  };
}
