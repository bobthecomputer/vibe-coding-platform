function asList(value) {
  return Array.isArray(value) ? value : [];
}

function asObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
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

export function RuntimeTruthContract({ fusedRuntime, missionSkillRecovery, missionSkillRecoveryPlan }) {
  const runtime = fusedRuntime || {};
  const recovery = asObject(missionSkillRecovery);
  const recoveryPlan = asObject(missionSkillRecoveryPlan || recovery.recoveryPlan);
  const recoveryTriggers = asList(recovery.triggers);
  const recoveryActions = asList(recovery.recoveryActions);
  const recoveryRecommendations = asList(recovery.recommendations);
  const recoveryRouteSeparation = asObject(recovery.routeSeparation);
  const recoveryProviderRoute = asObject(recoveryPlan.providerRoute || recoveryRouteSeparation.providerRoute);
  const recoverySelectedSkill = asObject(recoveryPlan.selectedSkill || recoveryRecommendations[0]);
  const recoveryProofRequirement = asObject(recoveryPlan.proofRequirement);
  const recoveryProofArtifactPlan = asObject(recoveryPlan.proofArtifactPlan);
  const recoveryRetryGuard = asObject(recoveryPlan.retryGuard);
  const recoveryIsActive =
    Boolean(recoveryPlan.schemaVersion) ||
    String(recovery.status || "").toLowerCase() === "needs_recovery" ||
    recoveryTriggers.length > 0;
  const recoveryRuntimeLane = recoveryPlan.runtimeLane || recoveryRouteSeparation.runtimeLane || runtime.runtimeLanes?.[0]?.runtimeId || "";
  const recoveryNextAction =
    recoveryPlan.nextAction ||
    recoveryActions[0]?.action ||
    recoveryTriggers[0]?.recoveryAction ||
    "No mission recovery action is active right now.";
  const proofSignals = runtime.proofSignals || {};
  const latestProof = runtime.latestLaneProof || {};
  const delegatedProofReceipts = asList(runtime.delegatedProofReceipts);
  const proofGateSummary = runtime.proofGateSummary || latestProof.proofGateSummary || {};
  const lanes = asList(runtime.runtimeLanes)
    .map(item => item.label || runtimeLabel(item.runtimeId))
    .filter(Boolean);
  const fusionPoints = asList(runtime.fusionPoints).slice(0, 4).map(titleizeToken);
  const proofLanes = asList(latestProof.lanes).filter(item => item.runtimeId || item.label);
  const proofArtifactCount = Object.keys(latestProof.artifactPaths || {}).length;
  const readiness = latestProof.fusedRuntime?.readinessSummary || latestProof.readinessSummary || {};
  const readinessRows = asList(readiness.lanes);
  const artifactIntegrity = latestProof.artifactIntegrity || {};
  const artifactIntegrityRows = asList(artifactIntegrity.artifacts);
  const missingGateArtifacts = asList(
    proofGateSummary.missingGateArtifacts || artifactIntegrity.missingGateArtifacts,
  );
  const laneReadinessRows = proofLanes.flatMap(item =>
    asList(item.readiness?.gates).map(gate => ({
      runtimeId: item.runtimeId || item.label,
      ...gate,
    })),
  );
  const proofPromotionBlocked =
    proofGateSummary.promotionBlocked !== undefined
      ? Boolean(proofGateSummary.promotionBlocked)
      : Boolean(readiness.promotionBlocked);
  const nextRecoveryActions = asList(proofGateSummary.nextRecoveryActions);
  const requiredArtifacts = asList(proofGateSummary.requiredArtifacts);

  return (
    <div className="runtime-truth-contract" aria-label="Fused runtime truth contract">
      <span>Fused runtime truth contract</span>
      <strong>Role: {titleizeToken(proofSignals.fusedRuntimeRole || "supervisor_not_runtime_adapter")}</strong>
      <p>Runtime adapter added: {runtime.runtimeAdapterAdded ? "yes" : "no"} · Providers stay model routes, not runtime lanes.</p>
      <p>Executable lanes: {lanes.join(" · ") || "none recorded"}</p>
      <p>
        Delegated proof receipts: {proofSignals.verifiedDelegatedProofReceiptCount || 0}/{proofSignals.delegatedProofReceiptCount || delegatedProofReceipts.length || 0} verified
      </p>
      <small>Normalizes {fusionPoints.join(" · ") || "mission control evidence"} before route promotion.</small>
      {delegatedProofReceipts.length > 0 ? (
        <div className="delegated-runtime-proof-receipts" aria-label="Delegated runtime proof receipts">
          <div className="runtime-proof-flight-head">
            <span>Delegated runtime proof receipts</span>
            <strong>{proofSignals.verifiedDelegatedProofReceiptCount || 0} verified</strong>
          </div>
          <div className="delegated-runtime-proof-list">
            {delegatedProofReceipts.slice(0, 4).map(item => (
              <article
                className="delegated-runtime-proof-card"
                data-verified={Boolean(item.verification?.passed)}
                key={`delegated-runtime-proof-${item.delegatedId || item.path}`}
              >
                <span>{item.schemaVersion || "delegated-runtime-proof.v1"}</span>
                <strong>{runtimeLabel(item.runtimeId)} · {item.delegatedId || "delegated session"}</strong>
                <p>
                  {titleizeToken(item.status || "unknown")} · events {item.eventCount || 0} · changed files {item.changedFileCount || 0}
                </p>
                <small>
                  live runtime execution: {item.safety?.liveRuntimeExecution ? "yes" : "no"} · live model calls: {item.safety?.liveModelCalls ? "yes" : "no"} · runtime adapter added: {item.safety?.runtimeAdapterAdded ? "yes" : "no"}
                </small>
                <code>{item.path || item.artifactUrl || "receipt path pending"}</code>
              </article>
            ))}
          </div>
        </div>
      ) : null}
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
            <div className="runtime-proof-flight-recorder" aria-label="Runtime proof gate flight recorder">
              <div className="runtime-proof-flight-head">
                <span>Runtime proof flight recorder</span>
                <strong>{proofPromotionBlocked ? "Promotion blocked" : "Promotion clear"}</strong>
              </div>
              <div className="runtime-proof-flight-grid">
                <div>
                  <span>Gate status</span>
                  <b>{titleizeToken(proofGateSummary.status || readiness.overallStatus || "contract_ready_live_unverified")}</b>
                </div>
                <div>
                  <span>Blocking gates</span>
                  <b>{proofGateSummary.blockingGateCount || readiness.blockingGateCount || 0}</b>
                </div>
                <div>
                  <span>Live validation</span>
                  <b>{proofGateSummary.liveValidationGateCount || 0} gate(s)</b>
                </div>
                <div>
                  <span>Passed / unchecked</span>
                  <b>{proofGateSummary.passedGateCount || 0} / {proofGateSummary.uncheckedGateCount || 0}</b>
                </div>
              </div>
              <code>{proofGateSummary.proofRunCommand || latestProof.proofRunCommand || "python scripts/runtime_lane_proof_harness.py"}</code>
              {requiredArtifacts.length > 0 ? (
                <small>Artifacts: {requiredArtifacts.slice(0, 4).join(" · ")}</small>
              ) : null}
              <div className="runtime-proof-artifact-integrity" aria-label="Runtime proof artifact integrity">
                <div className="runtime-proof-flight-head">
                  <span>Proof artifact integrity</span>
                  <strong>
                    {artifactIntegrity.missingCount || proofGateSummary.missingArtifactCount
                      ? "Missing evidence"
                      : "Files present"}
                  </strong>
                </div>
                <div className="runtime-proof-flight-grid">
                  <div>
                    <span>Present files</span>
                    <b>{artifactIntegrity.presentCount || proofGateSummary.presentArtifactCount || 0}</b>
                  </div>
                  <div>
                    <span>Missing files</span>
                    <b>{artifactIntegrity.missingCount || proofGateSummary.missingArtifactCount || 0}</b>
                  </div>
                  <div>
                    <span>Gate-required</span>
                    <b>{artifactIntegrity.gateRequiredCount || requiredArtifacts.length || 0}</b>
                  </div>
                  <div>
                    <span>Tracked paths</span>
                    <b>{artifactIntegrityRows.length || proofArtifactCount}</b>
                  </div>
                </div>
                {artifactIntegrityRows.length > 0 ? (
                  <div className="runtime-proof-artifact-list">
                    {artifactIntegrityRows.slice(0, 4).map(item => (
                      <span data-present={item.exists} key={`${item.key}-${item.path}`}>
                        {item.name || item.key}: {item.exists ? "present" : "missing"}
                      </span>
                    ))}
                  </div>
                ) : null}
                {missingGateArtifacts.length > 0 ? (
                  <small>Missing gate proof: {missingGateArtifacts.slice(0, 4).join(" · ")}</small>
                ) : null}
              </div>
              {nextRecoveryActions.length > 0 ? (
                <ul className="runtime-proof-next-actions">
                  {nextRecoveryActions.slice(0, 3).map(action => (
                    <li key={`runtime-proof-next-${action}`}>{action}</li>
                  ))}
                </ul>
              ) : null}
              <div className="runtime-recovery-proof-gate" data-active={recoveryIsActive} aria-label="Runtime recovery proof gate">
                <div className="runtime-proof-flight-head">
                  <span>Recovery proof gate</span>
                  <strong>{recoveryIsActive ? "Recovery required" : "No recovery block"}</strong>
                </div>
                <div className="runtime-recovery-proof-grid">
                  <div>
                    <span>Selected skill</span>
                    <b>{recoverySelectedSkill.label || titleizeToken(recoverySelectedSkill.skillId || "No recovery skill selected")}</b>
                  </div>
                  <div>
                    <span>Loop step</span>
                    <b>{titleizeToken(recoveryPlan.loopStep || recoveryTriggers[0]?.loopStep || "observe")}</b>
                  </div>
                  <div>
                    <span>Runtime lane</span>
                    <b>{runtimeLabel(recoveryRuntimeLane || "none")}</b>
                  </div>
                  <div>
                    <span>Retry guard</span>
                    <b>{recoveryRetryGuard.blockSameStepRetry ? "Blocked until proof" : "Clear"}</b>
                  </div>
                </div>
                <p>{recoveryNextAction}</p>
                <small>
                  Proof before retry: {recoveryProofRequirement.label || recoveryProofArtifactPlan.artifactKind || "not required"}
                  {recoveryProofArtifactPlan.mustAttachBeforeRetry ? " · must attach before retry" : ""}
                </small>
                {recoveryProviderRoute.provider || recoveryProviderRoute.model ? (
                  <small>
                    Route: {recoveryPlan.visibleRouteSummary ||
                      [recoveryRuntimeLane, recoveryProviderRoute.provider, recoveryProviderRoute.model].filter(Boolean).join(" · ")}
                  </small>
                ) : null}
                {recoveryRetryGuard.reason ? <code>{recoveryRetryGuard.reason}</code> : null}
                {recoveryProofArtifactPlan.suggestedPath ? <code>{recoveryProofArtifactPlan.suggestedPath}</code> : null}
                {recoveryActions.length > 0 ? (
                  <ul className="runtime-proof-next-actions">
                    {recoveryActions.slice(0, 3).map((action, index) => (
                      <li key={`runtime-recovery-action-${action.action || action.label || index}`}>
                        {action.action || action.label || action.recoveryAction}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </div>
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
