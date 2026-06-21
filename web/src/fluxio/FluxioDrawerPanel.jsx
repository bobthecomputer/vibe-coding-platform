import { lazy, Suspense } from "react";

import { ActionButton, Field, Modal, StatusPill } from "../../../desktop-ui/MissionControlPrimitives.jsx";

const FusionWorkbenchPanel = lazy(() =>
  import("./fusion/FusionWorkbenchPanel.jsx").then(module => ({
    default: module.FusionWorkbenchPanel,
  })),
);
const ProviderEcosystemPanel = lazy(() =>
  import("./provider/ProviderEcosystemPanel.jsx").then(module => ({
    default: module.ProviderEcosystemPanel,
  })),
);
const RedTeamProofBoard = lazy(() =>
  import("./redteam/RedTeamProofBoard.jsx").then(module => ({
    default: module.RedTeamProofBoard,
  })),
);
const VisualProofReceiptGallery = lazy(() => import("./proof/VisualProofReceiptGallery.jsx"));
const SubagentReadinessPanel = lazy(() => import("./subagents/SubagentReadinessPanel.jsx"));
const RuntimeTruth = lazy(() => import("./runtime/RuntimeTruthContract.jsx"));

function LazySurfaceFallback({ label }) {
  return (
    <div className="lazy-surface-fallback" role="status">
      <span />
      {label}
    </div>
  );
}

export default function FluxioDrawerPanel(props) {
  const {
    activeDrawer,
    activeRoadmapItemId,
    agentCyclePhase,
    allowFixturePreviewModes,
    asList,
    bridgeSessions,
    clearAllMemory,
    clearDebugEvents,
    clearMissionMemory,
    clearWorkspaceMemory,
    CODE_EXECUTION_MEMORY_OPTIONS,
    codeExecutionArtifacts,
    codeExecutionEnabled,
    codeExecutionMemory,
    COMMIT_STYLE_OPTIONS,
    copyContextValue,
    createLocalTask,
    cx,
    data,
    debugEvents,
    DEFAULT_OPENCLAW_GATEWAY_URL,
    delegatedSessions,
    effectiveRouteRows,
    executeTask,
    EXECUTION_TARGET_OPTIONS,
    focusedRuntimeServices,
    fusionWorkbench,
    handleBuilderFeatureAction,
    handleOpenClawClearToken,
    handleOpenClawConnect,
    handleOpenClawDisconnect,
    handleOpenClawSaveToken,
    handlePrimaryAction,
    handleProviderSecretClear,
    handleProviderSecretSave,
    handleQualityRoadmapAction,
    handleReferenceQuickAuth,
    handleSendTestPing,
    lastPushReason,
    listLabel,
    LIVE_SYNC_OPTIONS,
    liveSyncSeconds,
    localTasks,
    memoryPolicy,
    memoryStore,
    MINIMAX_AUTH_OPTIONS,
    minimaxAuthPath,
    minimaxAuthReady,
    mission,
    missionActionAvailable,
    missionCodeExecutionState,
    missionProviderTruth,
    missionRuntimeContract,
    missionSkillRecovery,
    missionSkillRecoveryActions,
    missionSkillRecoveryNeedsAction,
    missionSkillRecoveryPlan,
    missionSkillRecoveryProofArtifactPlan,
    missionSkillRecoveryProofRequirement,
    missionSkillRecoveryProviderRoute,
    missionSkillRecoveryRecommendations,
    missionSkillRecoveryRoute,
    missionSkillRecoverySelectedSkill,
    missionSkillRecoveryTriggers,
    MODEL_EFFORT_OPTIONS,
    MODEL_PROVIDER_OPTIONS,
    modelAuthReady,
    monitoringLoops,
    monitoringLoopStudio,
    OPENAI_CODEX_AUTH_OPTIONS,
    openAICodexAuthPath,
    openAICodexAuthReady,
    openBridgeEndpoint,
    openClawGatewayToken,
    openClawGatewayUrl,
    openClawStatus,
    openProviderAuthUrl,
    PREFERRED_HARNESS_OPTIONS,
    previewLabel,
    previewMode,
    previewModeOptions,
    proofWrapEnabled,
    PROVIDER_AUTH_URLS,
    PROVIDER_SECRET_OPTIONS,
    providerEcosystem,
    providerEcosystemProviders,
    providerEcosystemSources,
    providerEcosystemSummary,
    providerEcosystemUpdatePolicy,
    providerOAuthActionsAvailable,
    providerOAuthUnavailableReason,
    providerSecretDrafts,
    providerSecretPresence,
    providerSecretSaving,
    providerSetupStatus,
    removeTask,
    ROUTE_MODEL_OPTIONS,
    routeEffortLabel,
    ROUTING_STRATEGY_OPTIONS,
    runMissionAction,
    runtimeLabel,
    runWorkspaceActionSpec,
    saveWorkspacePolicy,
    setActiveDrawer,
    setActiveRoadmapItemId,
    setCodeExecutionEnabled,
    setCodeExecutionMemory,
    setLiveSyncSeconds,
    setMemoryPolicy,
    setOpenClawGatewayToken,
    setOpenClawGatewayUrl,
    setPreviewMode,
    setProofWrapEnabled,
    setProviderSecretDrafts,
    setReferenceSettingsTab,
    setShowEscalationDialog,
    setSkillStudioFilter,
    setSkillStudioQuery,
    setSurface,
    setTaskTriggerToken,
    setWorkspaceProfileForm,
    skillStudioFilter,
    skillStudioQuery,
    snapshot,
    subagentLanes,
    subagentOrchestrationStudio,
    subagentScoreboard,
    supervisorInterventionQueue,
    taskForm,
    taskTriggerToken,
    timestampLabel,
    titleizeToken,
    toggleTaskActive,
    toneClass,
    triggerTaskByToken,
    uiMode,
    uniq,
    updateTaskFormField,
    verifyMiniMaxOpenClawAuth,
    viewModel,
    visualProofPacket,
    WindowedList,
    workspace,
    workspaceProfileForm,
  } = props;
      if (activeDrawer === "queue") {  
        return (  
          <section className="drawer-panel">  
            <header>  
              <p className="eyebrow">Urgency</p>  
              <h2>{viewModel.drawers.queue.label}</h2>  
              <p>{viewModel.drawers.queue.recommendation.reason}</p>  
            </header>  
            <div className="drawer-list">  
              {viewModel.drawers.queue.items.map(item => (  
                <article className={`drawer-card ${toneClass(item.tone)}`} key={`${item.type}-${item.title}`}>  
                  <span>{item.type}</span>  
                  <strong>{item.title}</strong>  
                  <p>{item.reason}</p>  
                </article>  
              ))}  
            </div>  
            <div className="drawer-actions">  
              <ActionButton onClick={handlePrimaryAction} variant="primary">  
                {viewModel.topBar.primaryAction.label}  
              </ActionButton>  
              <ActionButton  
                disabled={!missionActionAvailable(mission, "resume")}  
                onClick={() => void runMissionAction("resume", "Mission resume requested.")}  
              >  
                Resume mission  
              </ActionButton>  
            </div>  
          </section>  
        );  
      }  
    
      if (activeDrawer === "proof") {  
        return (  
          <section className="drawer-panel">  
            <header>  
              <p className="eyebrow">Proof review</p>  
              <h2>{viewModel.drawers.proof.headline}</h2>  
              <p>{viewModel.drawers.proof.diffSummary}</p>  
            </header>  
            <div className="drawer-actions">  
              <ActionButton onClick={() => setProofWrapEnabled(current => !current)} type="button">  
                {proofWrapEnabled ? "Disable wrap" : "Enable wrap"}  
              </ActionButton>  
            </div>  
            <section className="proof-compare-grid">  
              {viewModel.drawers.proof.sections.map(section => (  
                <section className="drawer-block" key={section.title}>  
                  <h3>{section.title}</h3>  
                  <div className={`proof-item-list ${proofWrapEnabled ? "wrap" : "no-wrap"}`.trim()}>  
                    {section.items.length > 0 ? (  
                      section.items.map(item => (  
                        <article className="proof-item-row" key={`${section.title}-${item}`}>  
                          <code>{listLabel(item)}</code>  
                          <ActionButton  
                            onClick={() => copyContextValue(listLabel(item))}  
                            type="button"  
                          >  
                            Copy  
                          </ActionButton>  
                        </article>  
                      ))  
                    ) : (  
                      <article className="proof-item-row">  
                        <code>Nothing captured yet.</code>  
                      </article>  
                    )}  
                  </div>  
                </section>  
              ))}  
            </section>  
          </section>  
        );  
      }  
    
      if (activeDrawer === "skills") {  
        const filteredRecommendedSkills = viewModel.drawers.builder.skillStudio.recommended.filter(  
          item => item.label.toLowerCase().includes(skillStudioQuery.trim().toLowerCase()) || item.description.toLowerCase().includes(skillStudioQuery.trim().toLowerCase()),  
        );  
        const filteredCuratedSkills = viewModel.drawers.builder.skillStudio.curated.filter(item => {  
          const query = skillStudioQuery.trim().toLowerCase();  
          const matchesQuery =  
            !query ||  
            item.label.toLowerCase().includes(query) ||  
            (item.description || "").toLowerCase().includes(query);  
          if (!matchesQuery) {  
            return false;  
          }  
          if (skillStudioFilter === "recommended") {  
            return item.installed;  
          }  
          if (skillStudioFilter === "needs_attention") {  
            return !item.installed || item.testStatus !== "Reviewed";  
          }  
          return true;  
        });  
    
        return (  
          <section className="drawer-panel">  
            <header>  
              <h2>Skills</h2>  
              <p>Install, review, and route the packs that actually support operator work.</p>  
            </header>  
    
            <section className="drawer-block">  
              <div className="skill-toolbar">  
                <Field label="Filter">  
                  <select onChange={event => setSkillStudioFilter(event.target.value)} value={skillStudioFilter}>  
                    <option value="all">All packs</option>  
                    <option value="recommended">Installed</option>  
                    <option value="needs_attention">Needs attention</option>  
                  </select>  
                </Field>  
                <Field label="Find skill pack">  
                  <input  
                    onChange={event => setSkillStudioQuery(event.target.value)}  
                    placeholder="Search by label or note"  
                    value={skillStudioQuery}  
                  />  
                </Field>  
              </div>  
              <div className="context-grid compact-metrics">  
                <article className="context-item">  
                  <span>Reviewed reusable</span>  
                  <strong>  
                    {viewModel.drawers.builder.skillStudio.summary.reviewedReusableCount}/  
                    {viewModel.drawers.builder.skillStudio.summary.totalSkills}  
                  </strong>  
                </article>  
                <article className="context-item">  
                  <span>Execution ready</span>  
                  <strong>{viewModel.drawers.builder.skillStudio.summary.executionReadyCount}</strong>  
                </article>  
                <article className="context-item">  
                  <span>Need tests</span>  
                  <strong>{viewModel.drawers.builder.skillStudio.summary.needsTestCount}</strong>  
                </article>  
              </div>
            </section>
  
            <section className={`drawer-block skill-recovery-panel ${toneClass(missionSkillRecoveryNeedsAction ? "warn" : "good")}`}>
              <div className="skill-recovery-head">
                <div>
                  <h3>Skill recovery</h3>
                  <p>
                    {missionSkillRecoveryNeedsAction
                      ? "The current mission has recovery signals. Pick a different skill, route, or handoff before retrying the same step."
                      : "No blocked-state skill recovery is active for the current mission."}
                  </p>
                </div>
                <span>{titleizeToken(missionSkillRecovery.status || "idle")}</span>
              </div>
              <div className="context-grid compact-metrics">
                <article className="context-item">
                  <span>Triggers</span>
                  <strong>{missionSkillRecoveryTriggers.length}</strong>
                </article>
                <article className="context-item">
                  <span>Recommended skills</span>
                  <strong>{missionSkillRecoveryRecommendations.length}</strong>
                </article>
                <article className="context-item">
                  <span>Runtime lane</span>
                  <strong>{titleizeToken(missionSkillRecoveryRoute.runtimeLane || mission?.runtime_id || "none")}</strong>
                </article>
              </div>
              {missionSkillRecoveryPlan.schemaVersion ? (
                <div className="skill-recovery-plan-grid">
                  <article className="drawer-card tone-neutral">
                    <span>Selected skill</span>
                    <strong>
                      {missionSkillRecoverySelectedSkill.label ||
                        titleizeToken(missionSkillRecoverySelectedSkill.skillId || "Normal flow")}
                    </strong>
                    <p>{missionSkillRecoveryPlan.routeReason || "Route reason has not been recorded yet."}</p>
                    <div className="pill-row">
                      <span className="mini-pill">{`Loop: ${titleizeToken(missionSkillRecoveryPlan.loopStep || "repair")}`}</span>
                      <span className="mini-pill muted">
                        {missionSkillRecoverySelectedSkill.executionCapable ? "Can execute" : "Guidance first"}
                      </span>
                    </div>
                  </article>
                  <article className="drawer-card tone-neutral">
                    <span>Runtime and model route</span>
                    <strong>{missionSkillRecoveryPlan.visibleRouteSummary || "Route summary pending"}</strong>
                    <p>
                      {`Runtime: ${titleizeToken(missionSkillRecoveryPlan.runtimeLane || mission?.runtime_id || "none")} · Provider: ${
                        missionSkillRecoveryProviderRoute.provider ||
                        missionSkillRecoveryPlan.providerRoute?.provider ||
                        "unresolved"
                      } ${missionSkillRecoveryProviderRoute.model || missionSkillRecoveryPlan.providerRoute?.model || ""}`.trim()}
                    </p>
                  </article>
                  <article className="drawer-card tone-warn">
                    <span>Proof before retry</span>
                    <strong>{missionSkillRecoveryProofRequirement.label || "Recovery proof"}</strong>
                    <p>
                      {missionSkillRecoveryProofArtifactPlan.mustAttachBeforeRetry
                        ? "Attach this proof packet before retrying the same step."
                        : "No recovery proof packet is required right now."}
                    </p>
                    {missionSkillRecoveryProofArtifactPlan.suggestedPath ? (
                      <small>{missionSkillRecoveryProofArtifactPlan.suggestedPath}</small>
                    ) : null}
                  </article>
                </div>
              ) : null}
              {missionSkillRecoveryPlan.schemaVersion ? (
                <div className="skill-recovery-action-row">
                  <ActionButton
                    disabled={!missionSkillRecoveryNeedsAction}
                    onClick={() =>
                      void handleBuilderFeatureAction("apply_recovery_plan", {
                        recoveryPlan: missionSkillRecoveryPlan,
                      })
                    }
                    type="button"
                    variant="primary"
                  >
                    Use recovery plan
                  </ActionButton>
                  <span>
                    {missionSkillRecoveryProofArtifactPlan.mustAttachBeforeRetry
                      ? "Proof-gated retry"
                      : "Normal flow"}
                  </span>
                </div>
              ) : null}
              {missionSkillRecoveryTriggers.length > 0 ? (
                <div className="drawer-list compact skill-recovery-list">
                  {missionSkillRecoveryTriggers.slice(0, 4).map(item => (
                    <article
                      className={`drawer-card ${toneClass(item.severity === "high" ? "bad" : "warn")}`}
                      key={`skill-recovery-trigger-${item.triggerId || item.label}`}
                    >
                      <span>{titleizeToken(item.severity || "signal")}</span>
                      <strong>{item.label || titleizeToken(item.triggerId || "Recovery signal")}</strong>
                      <p>{item.reason || "Recovery signal captured from mission state."}</p>
                      {asList(item.evidence).length > 0 ? (
                        <p>{`Evidence: ${asList(item.evidence).slice(0, 2).map(listLabel).join(" | ")}`}</p>
                      ) : null}
                    </article>
                  ))}
                </div>
              ) : null}
              {missionSkillRecoveryRecommendations.length > 0 ? (
                <details open>
                  <summary>Recommended recovery skills</summary>
                  <div className="drawer-list compact skill-recovery-list">
                    {missionSkillRecoveryRecommendations.slice(0, 4).map(item => (
                      <article className="drawer-card tone-neutral" key={`skill-recovery-rec-${item.recommendationId || item.skillId}`}>
                        <span>{titleizeToken(item.sourceKind || "skill")}</span>
                        <strong>{item.label || titleizeToken(item.skillId || "Recovery skill")}</strong>
                        <p>{item.reason || item.recoveryAction || "Recommended by the mission recovery contract."}</p>
                        <div className="pill-row">
                          <span className="mini-pill">{item.executionCapable ? "Execution-capable" : "Guidance"}</span>
                          <span className="mini-pill muted">{item.guidanceOnly ? "Review first" : "Can route"}</span>
                        </div>
                      </article>
                    ))}
                  </div>
                </details>
              ) : null}
              <details>
                <summary>Recovery actions and route separation</summary>
                <ul>
                  {missionSkillRecoveryActions.length > 0 ? (
                    missionSkillRecoveryActions.slice(0, 5).map(item => (
                      <li key={`skill-recovery-action-${item.triggerId || item.label}`}>
                        {item.action || item.label}
                      </li>
                    ))
                  ) : (
                    <li>Continue normal plan-execute-verify flow; no recovery action is currently required.</li>
                  )}
                </ul>
                <p className="drawer-footnote">
                  {missionSkillRecoveryRoute.rule ||
                    "Hermes/OpenClaw remain runtime lanes; model providers remain provider routes."}
                  {missionSkillRecoveryProviderRoute.provider
                    ? ` Provider: ${missionSkillRecoveryProviderRoute.provider} ${missionSkillRecoveryProviderRoute.model || ""}`.trim()
                    : ""}
                </p>
              </details>
            </section>
  
            <section className="drawer-block">
              <h3>Recommended packs</h3>
              <div className="drawer-list">
                {filteredRecommendedSkills.length > 0 ? (  
                  filteredRecommendedSkills.map(item => (  
                    <article className={`drawer-card ${toneClass(item.tone)}`} key={`recommended-${item.id}`}>  
                      <span>{item.originType}</span>  
                      <strong>{item.label}</strong>  
                      <p>{item.description}</p>  
                      <div className="pill-row">  
                        <span className="mini-pill">{item.status}</span>  
                        <span className="mini-pill muted">{item.installed ? "Installed" : "Not installed"}</span>  
                        <span className="mini-pill muted">  
                          {item.executionCapable ? "Execution" : "Guidance only"}  
                        </span>  
                      </div>  
                    </article>  
                  ))  
                ) : (  
                  <article className="drawer-card">  
                    <strong>No recommended pack matches this filter.</strong>  
                  </article>  
                )}  
              </div>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Curated library</h3>  
              <div className="drawer-list">  
                {filteredCuratedSkills.length > 0 ? (  
                  filteredCuratedSkills.map(item => (  
                    <article className={`drawer-card ${toneClass(item.tone)}`} key={`curated-${item.id}`}>  
                      <span>{item.originType}</span>  
                      <strong>{item.label}</strong>  
                      <p>{item.status}</p>  
                      <div className="pill-row">  
                        <span className="mini-pill">{item.testStatus}</span>  
                        <span className="mini-pill muted">{item.usageCount} uses</span>  
                        <span className="mini-pill muted">{item.helpedCount} helped</span>  
                      </div>  
                    </article>  
                  ))  
                ) : (  
                  <article className="drawer-card">  
                    <strong>No curated pack matches this filter.</strong>  
                  </article>  
                )}  
              </div>  
              <p className="drawer-footnote">{viewModel.drawers.builder.skillStudio.capabilitiesNote}</p>  
            </section>  
          </section>  
        );  
      }  
    
      if (activeDrawer === "runtime") {  
        const primaryRuntimeServices = [  
          ...focusedRuntimeServices.hermes,  
          ...focusedRuntimeServices.openClaw.filter(  
            item => !focusedRuntimeServices.hermes.some(existing => existing.serviceId === item.serviceId),  
          ),  
        ];  
        const bridgeServices = focusedRuntimeServices.bridges.filter(  
          item => !primaryRuntimeServices.some(existing => existing.serviceId === item.serviceId),  
        );  
    
        return (  
          <section className="drawer-panel">  
            <header>  
              <h2>Tools and accounts</h2>  
              <p>Keep Hermes, OpenClaw, OpenCodeGo, image tools, and phone alerts healthy from one simple setup panel.</p>
            </header>  
    
            <section className="drawer-block" id="provider-auth-panel">  
              <h3>AI accounts and model tools</h3>  
              <div className="context-grid compact-metrics">  
                <article className="context-item">  
                  <span>OpenAI / Codex auth</span>  
                  <strong>{`${openAICodexAuthPath} · ${openAICodexAuthReady ? "Ready" : "Missing"}`}</strong>  
                  <p>  
                    Connect your OpenAI account for Codex/OpenClaw, or save an API key for direct model calls.  
                  </p>  
                </article>  
                <article className="context-item">  
                  <span>MiniMax auth</span>  
                  <strong>{`${minimaxAuthPath} · ${minimaxAuthReady ? "Ready" : "Missing"}`}</strong>  
                  <p>  
                    {minimaxAuthPath.toLowerCase().includes("oauth")  
                      ? "Syntelos checks the MiniMax login file before marking MiniMax ready."  
                      : "Save a MiniMax API key when you want MiniMax model runs."}  
                  </p>  
                </article>  
                <article className="context-item">
                  <span>Active provider route</span>
                  <strong>
                    {missionProviderTruth?.activeRoute?.provider
                      ? `${titleizeToken(missionProviderTruth.activeRoute.provider)} · ${missionProviderTruth.activeRoute.model || "default"}`
                      : "Not resolved"}  
                  </strong>  
                  <p>  
                    {missionProviderTruth?.activeRoute?.role  
                      ? `${titleizeToken(missionProviderTruth.activeRoute.role)} in ${titleizeToken(missionProviderTruth.currentPhase || agentCyclePhase)}`  
                      : "The active AI account appears here after the first model-backed step."}
                  </p>
                </article>
                <article className="context-item">
                  <span>Provider ecosystem</span>
                  <strong>{providerEcosystemSummary.totalProvidersTracked || providerEcosystemProviders.length} tracked</strong>
                  <p>
                    {providerEcosystemSummary.routeReadyCount || 0} route ready · safe catalog refresh keeps user-defined models.
                  </p>
                </article>
                <article className="context-item">
                  <span>Last successful model call</span>
                  <strong>
                    {missionProviderTruth?.lastSuccessfulCall?.provider  
                      ? `${titleizeToken(missionProviderTruth.lastSuccessfulCall.provider)} · ${missionProviderTruth.lastSuccessfulCall.model || "default"}`  
                      : "None yet"}  
                  </strong>  
                  <p>  
                    {missionProviderTruth?.lastSuccessfulCall?.at  
                      ? timestampLabel(missionProviderTruth.lastSuccessfulCall.at)  
                      : "Success timestamps appear after the first grounded action result."}  
                  </p>  
                </article>  
                <article className="context-item">  
                  <span>Last provider failure</span>  
                  <strong>  
                    {missionProviderTruth?.lastFailure?.provider  
                      ? `${titleizeToken(missionProviderTruth.lastFailure.provider)} · ${missionProviderTruth.lastFailure.model || "default"}`  
                      : "No provider failure"}  
                  </strong>  
                  <p>  
                    {missionProviderTruth?.lastFailure?.summary ||  
                      "Connection or model errors appear here when something needs attention."}  
                  </p>  
                </article>  
              </div>  
    
              <div className="drawer-list">
                {PROVIDER_SECRET_OPTIONS.map(item => {
                  const hasSecret = Boolean(providerSecretPresence[item.id]);  
                  const providerAuthReady =  
                    item.id === "openai"  
                      ? openAICodexAuthReady  
                      : item.id === "minimax"  
                        ? minimaxAuthReady  
                        : hasSecret;  
                  const providerTruthRow =  
                    (providerSetupStatus && typeof providerSetupStatus === "object"  
                      ? providerSetupStatus[item.id]  
                      : null) || {};  
                  return (  
                    <article className={`drawer-card ${toneClass(providerAuthReady ? "good" : "warn")}`} key={`provider-${item.id}`}>  
                      <span>{item.env}</span>  
                      <strong>{item.label}</strong>  
                      <p>{item.note}</p>  
                      <p>  
                        {providerTruthRow?.lastSuccessfulModelCall?.provider  
                          ? `Last success: ${titleizeToken(providerTruthRow.lastSuccessfulModelCall.provider)} · ${providerTruthRow.lastSuccessfulModelCall.model || "default"}`  
                          : "No successful call recorded yet."}  
                      </p>  
                      <p>  
                        {providerTruthRow?.lastProviderFailure?.summary  
                          ? `Last failure: ${providerTruthRow.lastProviderFailure.summary}`  
                          : "No provider failure recorded."}  
                      </p>  
                      {item.id === "openai" ? (  
                        <div className="drawer-actions">  
                          <ActionButton  
                            disabled={!providerOAuthActionsAvailable}  
                            onClick={() => void handleReferenceQuickAuth("openai")}  
                            title={!providerOAuthActionsAvailable ? providerOAuthUnavailableReason : ""}  
                          >  
                            Connect Codex OAuth  
                          </ActionButton>  
                          <ActionButton onClick={() => void openProviderAuthUrl(PROVIDER_AUTH_URLS.openaiApiKeys, "OpenAI API keys")}>  
                            Open API keys  
                          </ActionButton>  
                        </div>  
                      ) : null}  
                      {item.id === "minimax" ? (  
                        <div className="drawer-actions">  
                          <ActionButton  
                            disabled={!providerOAuthActionsAvailable}  
                            onClick={() => void handleReferenceQuickAuth("minimax")}  
                            title={!providerOAuthActionsAvailable ? providerOAuthUnavailableReason : ""}  
                          >  
                            MiniMax OpenClaw OAuth  
                          </ActionButton>  
                          <ActionButton onClick={() => void openProviderAuthUrl(PROVIDER_AUTH_URLS.minimaxApiKeys, "MiniMax API keys")}>  
                            Open API keys  
                          </ActionButton>  
                        </div>  
                      ) : null}  
                      <Field label={`${item.label} API key`}>  
                        <input  
                          autoComplete="off"  
                          onChange={event =>  
                            setProviderSecretDrafts(current => ({  
                              ...current,  
                              [item.id]: event.target.value,  
                            }))  
                          }  
                          placeholder={hasSecret ? "Stored in secure keyring" : "Paste API key"}  
                          type="password"  
                          value={providerSecretDrafts[item.id] || ""}  
                        />  
                      </Field>  
                      <div className="drawer-actions">  
                        <ActionButton  
                          disabled={providerSecretSaving[item.id] === "saving"}  
                          onClick={() => void handleProviderSecretSave(item.id)}  
                        >  
                          {providerSecretSaving[item.id] === "saving" ? "Saving..." : "Save key"}  
                        </ActionButton>  
                        <ActionButton  
                          disabled={providerSecretSaving[item.id] === "clearing"}  
                          onClick={() => void handleProviderSecretClear(item.id)}  
                        >  
                          {providerSecretSaving[item.id] === "clearing" ? "Clearing..." : "Clear"}  
                        </ActionButton>  
                      </div>  
                    </article>  
                  );
                })}
              </div>
  
              <Suspense fallback={<LazySurfaceFallback label="Provider ecosystem" />}>
                <ProviderEcosystemPanel
                  providerEcosystem={providerEcosystem}
                  providers={providerEcosystemProviders}
                  sources={providerEcosystemSources}
                  summary={providerEcosystemSummary}
                  updatePolicy={providerEcosystemUpdatePolicy}
                />
              </Suspense>
  
              <div className="field-row">
                <Field label="Code execution">
                  <select  
                    onChange={event => setCodeExecutionEnabled(event.target.value === "enabled")}  
                    value={codeExecutionEnabled ? "enabled" : "disabled"}  
                  >  
                    <option value="disabled">Disabled</option>  
                    <option value="enabled">Enabled</option>  
                  </select>  
                </Field>  
                <Field label="Container memory">  
                  <select  
                    onChange={event => setCodeExecutionMemory(event.target.value)}  
                    value={codeExecutionMemory}  
                  >  
                    {CODE_EXECUTION_MEMORY_OPTIONS.map(option => (  
                      <option key={`code-exec-memory-${option.value}`} value={option.value}>  
                        {option.label}  
                      </option>  
                    ))}  
                  </select>  
                </Field>  
              </div>  
              {mission ? (  
                <div className="drawer-list compact runtime-event-mini-list">  
                  <article className="drawer-card">  
                    <span>Mission container</span>  
                    <strong>  
                      {missionCodeExecutionState?.enabled  
                        ? missionCodeExecutionState?.container_id || "auto container"  
                        : "disabled"}  
                    </strong>  
                    <p>  
                      {missionCodeExecutionState?.last_result ||  
                        "Code execution results and errors are persisted per mission turn."}  
                    </p>  
                    {missionCodeExecutionState?.last_error ? (  
                      <p>{missionCodeExecutionState.last_error}</p>  
                    ) : null}  
                  </article>  
                  {codeExecutionArtifacts.map(item => (  
                    <article className="drawer-card" key={`code-artifact-${item.artifact_id || item.created_at || item.action_id}`}>  
                      <span>{titleizeToken(item.kind || "artifact")}</span>  
                      <strong>{item.title || item.action_id || "Code execution artifact"}</strong>  
                      <p>{item.summary || "No summary captured."}</p>  
                      <p>{item.created_at ? timestampLabel(item.created_at) : ""}</p>  
                    </article>  
                  ))}  
                </div>  
              ) : null}  
              <p className="drawer-footnote">  
                Mission-level code execution state now persists container identity, failures, and artifacts so the runtime can reuse the same container across turns.  
              </p>  
            </section>  
    
            <section className="drawer-block">  
              <h3>OpenClaw live connection</h3>  
              <div className="context-grid compact-metrics">  
                <article className="context-item">  
                  <span>Connection</span>  
                  <strong>{openClawStatus?.connected ? "Connected" : "Disconnected"}</strong>  
                  <p>{openClawStatus?.gatewayUrl || openClawGatewayUrl || DEFAULT_OPENCLAW_GATEWAY_URL}</p>  
                </article>  
                <article className="context-item">  
                  <span>Messages waiting</span>  
                  <strong>{openClawStatus?.queuedOutbound ?? 0}</strong>  
                  <p>{openClawStatus?.reconnectAttempt ? `Reconnect ${openClawStatus.reconnectAttempt}` : "No reconnect pressure"}</p>  
                </article>  
                <article className="context-item">  
                  <span>Connection token</span>  
                  <strong>{data.openClawHasToken ? "Stored" : "Missing"}</strong>  
                  <p>{openClawStatus?.lastError || "No gateway error reported."}</p>  
                </article>  
                <article className="context-item">  
                  <span>Model accounts</span>  
                  <strong>{modelAuthReady ? "Connected" : "Missing"}</strong>  
                  <p>  
                    {modelAuthReady  
                      ? `${openAICodexAuthReady ? openAICodexAuthPath : minimaxAuthPath} is ready for model routing.`  
                      : "Connect OpenAI, MiniMax, or an API key before starting model work."}  
                  </p>  
                </article>  
              </div>  
    
              <div className="drawer-card runtime-account-card">  
                <div className="runtime-account-head">  
                  <div>  
                    <span>Accounts used by OpenClaw</span>  
                    <strong>Connect model accounts</strong>  
                  </div>  
                  <p className={modelAuthReady ? "runtime-auth-dot good" : "runtime-auth-dot warn"}>  
                    {modelAuthReady ? "ready" : "missing"}  
                  </p>  
                </div>  
                <div className="runtime-auth-ledger">  
                  <div>  
                    <span>Codex</span>  
                    <strong>{openAICodexAuthReady ? "OAuth ready" : "Needs OAuth"}</strong>  
                    <p>{openAICodexAuthPath}</p>  
                  </div>  
                  <div>  
                    <span>MiniMax</span>  
                    <strong>{minimaxAuthReady ? "Portal ready" : "Needs portal"}</strong>  
                    <p>{minimaxAuthPath}</p>  
                  </div>  
                </div>  
                <p>  
                  The connection token moves messages. Your model account decides which AI service OpenClaw can use.  
                </p>  
                <div className="drawer-actions">  
                  <ActionButton  
                    disabled={!providerOAuthActionsAvailable}  
                    onClick={() => void handleReferenceQuickAuth("openai")}  
                    title={!providerOAuthActionsAvailable ? providerOAuthUnavailableReason : ""}  
                    variant={openAICodexAuthReady ? "secondary" : "primary"}  
                  >  
                    {openAICodexAuthReady ? "Codex OAuth connected" : "Connect Codex OAuth"}  
                  </ActionButton>  
                  <ActionButton  
                    disabled={!providerOAuthActionsAvailable}  
                    onClick={() => void handleReferenceQuickAuth("minimax")}  
                    title={!providerOAuthActionsAvailable ? providerOAuthUnavailableReason : ""}  
                    variant={minimaxAuthReady ? "secondary" : "primary"}  
                  >  
                    {minimaxAuthReady ? "MiniMax OAuth connected" : "Start MiniMax OAuth"}  
                  </ActionButton>  
                  <ActionButton onClick={() => void verifyMiniMaxOpenClawAuth()}>  
                    Verify MiniMax  
                  </ActionButton>  
                  <ActionButton onClick={() => {  
                    setReferenceSettingsTab("providers");  
                    setSurface("settings");  
                    setActiveDrawer(null);  
                  }}>  
                    Open account settings  
                  </ActionButton>  
                </div>  
                <p className="drawer-footnote">  
                  Syntelos verifies the saved MiniMax login before it marks MiniMax ready.  
                </p>  
              </div>  
    
              <Field label="Connection URL">  
                <input  
                  onChange={event => setOpenClawGatewayUrl(event.target.value)}  
                  placeholder={DEFAULT_OPENCLAW_GATEWAY_URL}  
                  value={openClawGatewayUrl}  
                />  
              </Field>  
              <Field label="Connection token">  
                <input  
                  onChange={event => setOpenClawGatewayToken(event.target.value)}  
                  placeholder={data.openClawHasToken ? "Token stored in keyring" : "Paste a gateway token"}  
                  type="password"  
                  value={openClawGatewayToken}  
                />  
              </Field>  
              <div className="drawer-actions">  
                <ActionButton onClick={() => void handleOpenClawConnect()} variant="primary">  
                  Connect  
                </ActionButton>  
                <ActionButton onClick={() => void handleOpenClawDisconnect()}>  
                  Disconnect  
                </ActionButton>  
                <ActionButton onClick={() => void handleOpenClawSaveToken()}>  
                  Save token  
                </ActionButton>  
                <ActionButton onClick={() => void handleOpenClawClearToken()}>  
                  Clear token  
                </ActionButton>  
              </div>  
              <p className="drawer-footnote">  
                Syntelos can install, repair, update, and re-check Hermes, OpenClaw, and OpenCodeGo from here.
              </p>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Work engines</h3>  
              <div className="drawer-list">  
                {primaryRuntimeServices.length > 0 ? (  
                  primaryRuntimeServices.map(service => (  
                    <article className={`drawer-card ${toneClass(service.tone)}`} key={`runtime-${service.serviceId}`}>  
                      <span>{service.category}</span>  
                      <strong>{service.label}</strong>  
                      <p>  
                        {service.status}  
                        {service.version ? ` · ${service.version}` : ""}  
                        {service.latestVersion ? ` → ${service.latestVersion}` : ""}  
                      </p>
                      <p>{service.details || service.managementMode}</p>
                      {service.updateSafety?.summary ? (
                        <div className="update-safety-note" aria-label={`${service.label} update safety`}>
                          <strong>{service.updateSafety.label || "Review before updating"}</strong>
                          <p>{service.updateSafety.summary}</p>
                          <span>{service.updateSafety.safeNextStep}</span>
                          {service.updateSafety.verifyAfterUpdate ? <span>Fluxio will re-check setup after the update.</span> : null}
                        </div>
                      ) : null}
                      {service.actions.length > 0 ? (
                        <div className="drawer-actions">
                          {service.actions.slice(0, 3).map(action => (
                            <ActionButton  
                              key={`${service.serviceId}-${action.actionId}`}  
                              onClick={() => void runWorkspaceActionSpec(action)}  
                            >  
                              {action.label}  
                            </ActionButton>  
                          ))}  
                        </div>  
                      ) : null}  
                    </article>  
                  ))  
                ) : (  
                  <article className="drawer-card">  
                    <strong>Hermes, OpenClaw, and OpenCodeGo are not visible yet.</strong>
                    <p>After setup checks run, Syntelos shows them here with install and repair buttons.</p>  
                  </article>  
                )}  
              </div>  
            </section>  
    
            {mission ? (  
              <section className="drawer-block">  
                <h3>Mission settings used for this run</h3>  
                <div className="context-grid compact-metrics">  
                  {missionRuntimeContract.map(item => (  
                    <article className="context-item" key={`runtime-contract-${item.label}`}>  
                      <span>{item.label}</span>  
                      <strong>{item.value}</strong>  
                    </article>  
                  ))}  
                </div>  
                <div className="drawer-list">  
                  {effectiveRouteRows.length > 0 ? (  
                    effectiveRouteRows.map(item => (  
                      <article className="drawer-card" key={`route-contract-${item.role}`}>  
                        <span>{titleizeToken(item.role)}</span>  
                        <strong>  
                          {titleizeToken(item.provider)} · {item.model}  
                        </strong>  
                        <p>  
                          {titleizeToken(item.source || "profile_default")}  
                          {item.effort ? ` · ${routeEffortLabel(item.effort, "medium")} effort` : ""}  
                          {item.budgetClass ? ` · ${titleizeToken(item.budgetClass)}` : ""}  
                        </p>  
                        {item.reason ? <p>{item.reason}</p> : null}  
                      </article>  
                    ))  
                  ) : (  
                    <article className="drawer-card">  
                      <strong>No effective route contract reported yet.</strong>  
                      <p>Once the mission resolves planner, executor, and verifier routes, they will appear here.</p>  
                    </article>  
                  )}  
                </div>  
              </section>  
            ) : null}  
    
            <section className="drawer-block">  
              <h3>Background work</h3>  
              <div className="drawer-list">  
                {delegatedSessions.length > 0 ? (  
                  delegatedSessions.map(session => (  
                    <article  
                      className={`drawer-card ${toneClass(session.heartbeat_status === "stale" ? "warn" : session.status === "failed" ? "bad" : "neutral")}`}  
                      key={`delegated-session-${session.delegated_id}`}  
                    >  
                      <span>{runtimeLabel(session.runtime_id)}</span>  
                      <strong>{titleizeToken(session.status || "unknown")}</strong>  
                      <p>{session.detail || session.last_event || "A background run is active."}</p>  
                      <div className="pill-row">  
                        <span className="mini-pill">{session.heartbeat_status ? `Heartbeat ${titleizeToken(session.heartbeat_status)}` : "No heartbeat"}</span>  
                        {session.execution_target ? (  
                          <span className="mini-pill muted">{titleizeToken(session.execution_target)}</span>  
                        ) : null}  
                        {typeof session.heartbeat_age_seconds === "number" ? (  
                          <span className="mini-pill muted">{session.heartbeat_age_seconds}s ago</span>  
                        ) : null}  
                      </div>  
                      <p>{session.execution_target_detail || session.execution_root || session.workspace_root || "Execution root not reported."}</p>  
                      {Array.isArray(session.latest_events) && session.latest_events.length > 0 ? (  
                        <div className="drawer-list compact runtime-event-mini-list">  
                          {session.latest_events.slice(-3).reverse().map(event => (  
                            <article className="drawer-card" key={`runtime-event-${session.delegated_id}-${event.event_id || event.message}`}>  
                              <span>{titleizeToken(event.kind || "runtime")}</span>  
                              <strong>{event.message || "Runtime event"}</strong>  
                              {event.status ? <p>{titleizeToken(event.status)}</p> : null}  
                            </article>  
                          ))}  
                        </div>  
                      ) : null}  
                    </article>  
                  ))  
                ) : (  
                  <article className="drawer-card">  
                    <strong>No background run is active.</strong>  
                    <p>When Hermes or OpenClaw is working, Syntelos shows progress and the latest update here.</p>  
                  </article>  
                )}  
              </div>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Messaging and bridge surfaces</h3>  
              <div className="drawer-list">  
                {bridgeServices.length > 0 ? (  
                  bridgeServices.map(service => (  
                    <article className={`drawer-card ${toneClass(service.tone)}`} key={`bridge-${service.serviceId}`}>  
                      <span>{service.category}</span>  
                      <strong>{service.label}</strong>  
                      <p>{service.status}</p>  
                      <p>{service.details || "Bridge surface available."}</p>  
                    </article>  
                  ))  
                ) : (  
                  <article className="drawer-card">  
                    <strong>Message bridge visibility is still partial.</strong>  
                    <p>Telegram state is exposed today. iMessage and deeper mobile bridge specifics still need backend support before this shell can manage them honestly.</p>  
                  </article>  
                )}  
              </div>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Connected apps and mobile bridges</h3>  
              <div className="drawer-list">  
                {bridgeSessions.length > 0 ? (  
                  bridgeSessions.map(session => (  
                    <article className={`drawer-card ${toneClass(session.bridge_health === "healthy" ? "good" : "warn")}`} key={`bridge-session-${session.session_id}`}>  
                      <span>{session.app_name || session.app_id}</span>  
                      <strong>  
                        {titleizeToken(session.status || "unknown")}  
                        {session.bridge_transport ? ` · ${titleizeToken(session.bridge_transport)}` : ""}  
                      </strong>  
                      <p>{titleizeToken(session.bridge_health || "unknown")} bridge health</p>  
                      {Array.isArray(session.notes) && session.notes.length > 0 ? <p>{session.notes[0]}</p> : null}  
                      {session.latest_task_result?.resultSummary ? (  
                        <div className="bridge-output-summary">  
                          <span>{session.latest_task_result.label || "Latest output"}</span>  
                          <strong>{session.latest_task_result.resultSummary}</strong>  
                        </div>  
                      ) : null}  
                      {asList(session.context_preview).length > 0 ? (  
                        <div className="bridge-context-list">  
                          {asList(session.context_preview).slice(0, 2).map(surface => (  
                            <div className="bridge-context-item" key={`${session.session_id}-${surface.surfaceId || surface.label}`}>  
                              <span>{surface.label || "Context"}</span>  
                              <p>{surface.summary || "No summary reported."}</p>  
                            </div>  
                          ))}  
                        </div>  
                      ) : null}  
                      {Array.isArray(session.active_tasks) && session.active_tasks.length > 0 ? (  
                        <div className="pill-row">  
                          {session.active_tasks.slice(0, 3).map(item => (  
                            <span className="mini-pill muted" key={`bridge-task-${session.session_id}-${item}`}>  
                              {item}  
                            </span>  
                          ))}  
                        </div>  
                      ) : null}  
                      <div className="drawer-actions bridge-card-actions">  
                        {session.bridge_endpoint ? (  
                          <ActionButton  
                            onClick={() => void openBridgeEndpoint(session.bridge_endpoint, session.app_name || session.app_id)}  
                            type="button"  
                          >  
                            Open bridge  
                          </ActionButton>  
                        ) : null}  
                        {session.approval_callback?.available ? (  
                          <span className="mini-pill">  
                            {titleizeToken(session.approval_callback.channel || "callback")} ready  
                          </span>  
                        ) : null}  
                      </div>  
                    </article>  
                  ))  
                ) : (  
                  <article className="drawer-card">  
                    <strong>No connected app bridge is reporting yet.</strong>  
                    <p>Bridge Lab data will appear here when connected apps expose live session or follow-on bridge state.</p>  
                  </article>  
                )}  
              </div>  
              <p className="drawer-footnote">
                OpenClaw still has the direct gateway, but Hermes supervision now lands in the same Agent conversation through control-room runtime events and delegated lane snapshots.
              </p>
            </section>
  
            <Suspense fallback={<LazySurfaceFallback label="Fusion contract" />}>
              <FusionWorkbenchPanel fusionWorkbench={fusionWorkbench} />
            </Suspense>
  
            <Suspense fallback={<LazySurfaceFallback label="Loading red-team proof" />}>
              <RedTeamProofBoard />
            </Suspense>
  
            <section className="drawer-block">
              <h3>Setup controls</h3>
              <div className="drawer-actions">  
                {viewModel.drawers.builder.serviceStudio.services.flatMap(service =>  
                  service.actions.slice(0, 1).map(action => (  
                    <ActionButton  
                      key={`${service.serviceId}-${action.actionId}-setup`}  
                      onClick={() => void runWorkspaceActionSpec(action)}  
                    >  
                      {action.label}  
                    </ActionButton>  
                  )),  
                ).slice(0, 4)}  
              </div>  
            </section>  
          </section>  
        );  
      }  
    
      if (activeDrawer === "profiles") {  
        return (  
          <section className="drawer-panel">  
            <header>  
              <h2>Profiles and routing</h2>  
              <p>Shape workspace behavior, routing, and execution defaults from one profile surface.</p>  
            </header>  
    
            <section className="drawer-block">  
              <div className="field-row">  
                <Field label="Workspace profile">  
                  <select  
                    onChange={event =>  
                      setWorkspaceProfileForm(current => ({  
                        ...current,  
                        userProfile: event.target.value,  
                      }))  
                    }  
                    value={workspaceProfileForm.userProfile}  
                  >  
                    {(snapshot.profiles?.availableProfiles || ["beginner", "builder", "advanced"]).map(  
                      option => (  
                        <option key={option} value={option}>  
                          {titleizeToken(option)}  
                        </option>  
                      ),  
                    )}  
                  </select>  
                </Field>  
                <Field label="Preferred work engine">  
                  <select  
                    onChange={event =>  
                      setWorkspaceProfileForm(current => ({  
                        ...current,  
                        preferredHarness: event.target.value,  
                      }))  
                    }  
                    value={workspaceProfileForm.preferredHarness}  
                  >  
                    {PREFERRED_HARNESS_OPTIONS.map(option => (  
                      <option key={option.value} value={option.value}>  
                        {option.label}  
                      </option>  
                    ))}  
                  </select>  
                </Field>  
              </div>  
    
              <div className="field-row">  
                <Field label="Routing strategy">  
                  <select  
                    onChange={event =>  
                      setWorkspaceProfileForm(current => ({  
                        ...current,  
                        routingStrategy: event.target.value,  
                      }))  
                    }  
                    value={workspaceProfileForm.routingStrategy}  
                  >  
                    {ROUTING_STRATEGY_OPTIONS.map(option => (  
                      <option key={option.value} value={option.value}>  
                        {option.label}  
                      </option>  
                    ))}  
                  </select>  
                </Field>  
                <Field label="Execution target">  
                  <select  
                    onChange={event =>  
                      setWorkspaceProfileForm(current => ({  
                        ...current,  
                        executionTargetPreference: event.target.value,  
                      }))  
                    }  
                    value={workspaceProfileForm.executionTargetPreference}  
                  >  
                    {EXECUTION_TARGET_OPTIONS.map(option => (  
                      <option key={option.value} value={option.value}>  
                        {option.label}  
                      </option>  
                    ))}  
                  </select>  
                </Field>  
              </div>  
    
              <label className="check-field">  
                <input  
                  checked={workspaceProfileForm.autoOptimizeRouting}  
                  onChange={event =>  
                    setWorkspaceProfileForm(current => ({  
                      ...current,  
                      autoOptimizeRouting: event.target.checked,  
                    }))  
                  }  
                  type="checkbox"  
                />  
                <span>Enable deterministic routing auto-optimize when enough local runs exist.</span>  
              </label>  
    
              <div className="drawer-actions">  
                <ActionButton onClick={() => void saveWorkspacePolicy()} variant="primary">  
                  Save profile policy  
                </ActionButton>  
              </div>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Current behavior</h3>  
              <div className="drawer-list compact">  
                {viewModel.drawers.builder.profileStudio.behavior.map(item => (  
                  <article className="drawer-card" key={`profile-surface-${item.label}`}>  
                    <span>{item.label}</span>  
                    <strong>{item.value}</strong>  
                  </article>  
                ))}  
              </div>  
              <p className="drawer-footnote">  
                Routing strategy is real and saved at workspace level. Builder now exposes per-role overrides for planner, executor, and verifier when you need to pin specific models.  
              </p>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Per-role model routes</h3>  
              <div className="route-override-grid">  
                {workspaceProfileForm.routeOverrides.map(item => (  
                  <article className="drawer-card route-override-card" key={`route-override-${item.role}`}>  
                    <span>{titleizeToken(item.role)}</span>  
                    <div className="field-row">  
                      <Field label="Provider">  
                        <select  
                          onChange={event =>  
                            setWorkspaceProfileForm(current => ({  
                              ...current,  
                              routeOverrides: current.routeOverrides.map(entry =>  
                                entry.role === item.role  
                                  ? { ...entry, provider: event.target.value }  
                                  : entry,  
                              ),  
                            }))  
                          }  
                          value={item.provider}  
                        >  
                          {MODEL_PROVIDER_OPTIONS.map(option => (  
                            <option key={`${item.role}-${option.value}`} value={option.value}>  
                              {option.label}  
                            </option>  
                          ))}  
                        </select>  
                      </Field>  
                      <Field label="Effort">  
                        <select  
                          onChange={event =>  
                            setWorkspaceProfileForm(current => ({  
                              ...current,  
                              routeOverrides: current.routeOverrides.map(entry =>  
                                entry.role === item.role  
                                  ? { ...entry, effort: event.target.value }  
                                  : entry,  
                              ),  
                            }))  
                          }  
                          value={item.effort}  
                        >  
                          {MODEL_EFFORT_OPTIONS.map(option => (  
                            <option key={`${item.role}-${option.value}`} value={option.value}>  
                              {option.label}  
                            </option>  
                          ))}  
                        </select>  
                      </Field>  
                    </div>  
                    <Field label="Model">  
                      <select  
                        onChange={event =>  
                          setWorkspaceProfileForm(current => ({  
                            ...current,  
                            routeOverrides: current.routeOverrides.map(entry =>  
                              entry.role === item.role  
                                ? { ...entry, model: event.target.value }  
                                : entry,  
                            ),  
                          }))  
                        }  
                        value={item.model}  
                      >  
                        <option value="">Profile default</option>  
                        {uniq([item.model, ...ROUTE_MODEL_OPTIONS].filter(Boolean)).map(option => (  
                          <option key={`${item.role}-${option}`} value={option}>  
                            {option}  
                          </option>  
                        ))}  
                      </select>  
                    </Field>  
                  </article>  
                ))}  
              </div>  
              <p className="drawer-footnote">  
                Leave a role blank to keep using the routing strategy default. Planner, executor, and verifier overrides are saved into workspace policy and forwarded to the runtime.  
              </p>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Available contracts</h3>  
              <div className="drawer-list">  
                {viewModel.drawers.builder.profileStudio.profileRows.map(item => (  
                  <article className={`drawer-card ${toneClass(item.tone)}`} key={`profile-contract-${item.id}`}>  
                    <span>{item.label}</span>  
                    <strong>{item.description}</strong>  
                    <p>  
                      {item.approval} approvals · {item.autonomy} autonomy · {item.visibility} visibility  
                    </p>  
                    <p>{item.density} density</p>  
                  </article>  
                ))}  
              </div>  
            </section>  
          </section>  
        );  
      }  
    
      if (activeDrawer === "settings") {  
        return (  
          <section className="drawer-panel">  
            <header>  
              <p className="eyebrow">Settings</p>  
              <h2>Workspace and app controls</h2>  
              <p>Put operational settings here instead of scattering them across the shell.</p>  
            </header>  
    
            <section className="drawer-block">  
              <h3>App view</h3>  
              <Field label="Preview">  
                <select onChange={event => setPreviewMode(event.target.value)} value={previewMode}>  
                  {previewModeOptions.map(option => (  
                    <option key={option.id} value={option.id}>  
                      {option.name}  
                    </option>  
                  ))}  
                </select>  
              </Field>  
              {!allowFixturePreviewModes ? (  
                <p className="drawer-footnote">Web control mode is live-backend only.</p>  
              ) : null}  
              <Field label="Live sync">  
                <select onChange={event => setLiveSyncSeconds(event.target.value)} value={liveSyncSeconds}>  
                  {LIVE_SYNC_OPTIONS.map(option => (  
                    <option key={option.value} value={option.value}>  
                      {option.label}  
                    </option>  
                  ))}  
                </select>  
              </Field>  
              <p className="drawer-footnote">  
                {previewLabel(previewMode, data.previewMeta)}  
                {lastPushReason ? ` · Last push ${lastPushReason}` : ""}  
              </p>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Workspace defaults</h3>  
              <div className="context-grid">  
                {viewModel.drawers.builder.profileStudio.workspacePolicy.map(item => (  
                  <article className="context-item" key={`settings-${item.label}`}>  
                    <span>{item.label}</span>  
                    <strong>{item.value}</strong>  
                  </article>  
                ))}  
              </div>  
              <div className="drawer-actions">  
                <ActionButton onClick={() => setActiveDrawer("builder")} variant="primary">  
                  Open builder controls  
                </ActionButton>  
              </div>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Escalation</h3>  
              <p>{data.telegramReady ? "Telegram ready" : "Telegram not configured"}</p>  
              <div className="drawer-actions">  
                <ActionButton onClick={() => setShowEscalationDialog(true)} variant="primary">  
                  Configure  
                </ActionButton>  
                <ActionButton onClick={() => void handleSendTestPing()}>Send test ping</ActionButton>  
              </div>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Memory</h3>  
              <label className="check-field">  
                <input  
                  checked={memoryPolicy.includeInFollowUps}  
                  onChange={event =>  
                    setMemoryPolicy(current => ({  
                      ...current,  
                      includeInFollowUps: event.target.checked,  
                    }))  
                  }  
                  type="checkbox"  
                />  
                <span>Include memory snippets in follow-up messages.</span>  
              </label>  
              <label className="check-field">  
                <input  
                  checked={memoryPolicy.projectScoped}  
                  onChange={event =>  
                    setMemoryPolicy(current => ({  
                      ...current,  
                      projectScoped: event.target.checked,  
                    }))  
                  }  
                  type="checkbox"  
                />  
                <span>Keep workspace memory.</span>  
              </label>  
              <label className="check-field">  
                <input  
                  checked={memoryPolicy.missionScoped}  
                  onChange={event =>  
                    setMemoryPolicy(current => ({  
                      ...current,  
                      missionScoped: event.target.checked,  
                    }))  
                  }  
                  type="checkbox"  
                />  
                <span>Keep mission memory.</span>  
              </label>  
              <div className="drawer-list compact">  
                <article className="drawer-card">  
                  <span>Workspace memory</span>  
                  <strong>  
                    {workspace?.workspace_id  
                      ? String(memoryStore?.workspace?.[workspace.workspace_id] || "").trim() || "No workspace memory"  
                      : "No workspace selected"}  
                  </strong>  
                </article>  
                <article className="drawer-card">  
                  <span>Mission memory</span>  
                  <strong>  
                    {mission?.mission_id  
                      ? String(memoryStore?.mission?.[mission.mission_id] || "").trim() || "No mission memory"  
                      : "No mission selected"}  
                  </strong>  
                </article>  
              </div>  
              <div className="drawer-actions">  
                <ActionButton onClick={clearWorkspaceMemory} type="button">  
                  Clear workspace memory  
                </ActionButton>  
                <ActionButton onClick={clearMissionMemory} type="button">  
                  Clear mission memory  
                </ActionButton>  
                <ActionButton onClick={clearAllMemory} type="button">  
                  Clear all memory  
                </ActionButton>  
              </div>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Tasks</h3>  
              <div className="field-row">  
                <Field label="Task name">  
                  <input  
                    onChange={event => updateTaskFormField("name", event.target.value)}  
                    placeholder="Regression sweep"  
                    value={taskForm.name}  
                  />  
                </Field>  
                <Field label="Trigger">  
                  <select  
                    onChange={event => updateTaskFormField("trigger", event.target.value)}  
                    value={taskForm.trigger}  
                  >  
                    <option value="schedule">Scheduled</option>  
                    <option value="api">API</option>  
                    <option value="webhook">Webhook</option>  
                  </select>  
                </Field>  
              </div>  
              <Field label="Task prompt">  
                <textarea  
                  onChange={event => updateTaskFormField("prompt", event.target.value)}  
                  placeholder="Run full mission smoke checks and summarize blockers."  
                  value={taskForm.prompt}  
                />  
              </Field>  
              <div className="field-row">  
                <Field label="Every minutes">  
                  <input  
                    min="1"  
                    onChange={event => updateTaskFormField("everyMinutes", Number(event.target.value || 1))}  
                    type="number"  
                    value={taskForm.everyMinutes}  
                  />  
                </Field>  
                <Field label="Webhook/API token">  
                  <input  
                    onChange={event => updateTaskFormField("webhookToken", event.target.value)}  
                    placeholder="task-token-123"  
                    value={taskForm.webhookToken}  
                  />  
                </Field>  
              </div>  
              <label className="check-field">  
                <input  
                  checked={taskForm.active}  
                  onChange={event => updateTaskFormField("active", event.target.checked)}  
                  type="checkbox"  
                />  
                <span>Task active on create.</span>  
              </label>  
              <div className="drawer-actions">  
                <ActionButton onClick={createLocalTask} type="button" variant="primary">  
                  Create task  
                </ActionButton>  
              </div>  
              <Field label="Trigger token now">  
                <input  
                  onChange={event => setTaskTriggerToken(event.target.value)}  
                  placeholder="Paste token to simulate webhook/API trigger"  
                  value={taskTriggerToken}  
                />  
              </Field>  
              <div className="drawer-actions">  
                <ActionButton onClick={triggerTaskByToken} type="button">  
                  Trigger by token  
                </ActionButton>  
              </div>  
              <div className="drawer-list">  
                {localTasks.length > 0 ? (  
                  localTasks.map(item => (  
                    <article className={`drawer-card ${toneClass(item.lastStatus === "failed" ? "bad" : item.active ? "good" : "neutral")}`} key={item.id}>  
                      <span>{titleizeToken(item.trigger)}</span>  
                      <strong>{item.name}</strong>  
                      <p>{item.prompt}</p>  
                      <p>  
                        Every {Math.max(1, Number(item.everyMinutes) || 1)}m · Last run{" "}  
                        {item.lastRunAt ? timestampLabel(item.lastRunAt) : "never"} · {item.totalRuns || 0} run(s)  
                      </p>  
                      <div className="drawer-actions">  
                        <ActionButton onClick={() => toggleTaskActive(item.id)} type="button">  
                          {item.active ? "Pause" : "Resume"}  
                        </ActionButton>  
                        <ActionButton onClick={() => void executeTask(item, "manual")} type="button">  
                          Run now  
                        </ActionButton>  
                        <ActionButton onClick={() => removeTask(item.id)} type="button">  
                          Delete  
                        </ActionButton>  
                      </div>  
                    </article>  
                  ))  
                ) : (  
                  <article className="drawer-card">  
                    <strong>No task yet.</strong>  
                  </article>  
                )}  
              </div>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Debug stream</h3>  
              <p>  
                Backend invoke events, browser errors, and rejected promises are captured here.  
              </p>  
              <div className="drawer-actions">  
                <ActionButton onClick={clearDebugEvents} type="button">  
                  Clear logs  
                </ActionButton>  
              </div>  
              <WindowedList  
                className="drawer-list drawer-debug-list"  
                estimatedItemHeight={84}  
                items={debugEvents}  
                overscan={6}  
                renderItem={item => (  
                  <article className={`drawer-card ${toneClass(String(item.kind || "").includes("error") ? "bad" : "neutral")}`} key={item.id}>  
                    <span>{item.kind || "event"}</span>  
                    <strong>{item.command || item.message || "debug event"}</strong>  
                    <p>  
                      {timestampLabel(item.at)}  
                      {Number.isFinite(item.durationMs) ? ` · ${item.durationMs}ms` : ""}  
                    </p>  
                    {item.error ? <p>{String(item.error)}</p> : null}  
                  </article>  
                )}  
              />  
            </section>  
          </section>  
        );  
      }  
    
      if (activeDrawer === "builder" && uiMode === "builder") {  
        const skillQuery = skillStudioQuery.trim().toLowerCase();  
        const skillMatchesQuery = item =>  
          !skillQuery ||  
          String(item?.label || "")  
            .toLowerCase()  
            .includes(skillQuery) ||  
          String(item?.description || "")  
            .toLowerCase()  
            .includes(skillQuery) ||  
          (item?.profileSuitability || []).some(entry =>  
            String(entry).toLowerCase().includes(skillQuery),  
          );  
        const matchesSkillFilter = item => {  
          if (skillStudioFilter === "recommended") {  
            return !item?.installed;  
          }  
          if (skillStudioFilter === "installed") {  
            return Boolean(item?.installed);  
          }  
          if (skillStudioFilter === "needs_attention") {  
            return item?.testStatus !== "Reviewed" || !item?.installed;  
          }  
          return true;  
        };  
        const filteredRecommendedSkills = viewModel.drawers.builder.skillStudio.recommended.filter(  
          item => matchesSkillFilter(item) && skillMatchesQuery(item),  
        );  
        const filteredCuratedSkills = viewModel.drawers.builder.skillStudio.curated.filter(  
          item => matchesSkillFilter(item) && skillMatchesQuery(item),  
        );  
        const designFrontendRecommended = filteredRecommendedSkills.filter(item =>  
          /design|frontend|ui|ux|tailwind|react/i.test(  
            `${item?.label || ""} ${item?.description || ""} ${(item?.profileSuitability || []).join(" ")}`,  
          ),  
        );  
        const skillLifecycleCounts = filteredCuratedSkills.reduce(  
          (acc, item) => {  
            const statusText = `${item?.status || ""} ${item?.testStatus || ""}`.toLowerCase();  
            if (statusText.includes("proposed") || statusText.includes("draft")) {  
              acc.draft += 1;  
            }  
            if (statusText.includes("review")) {  
              acc.review += 1;  
            }  
            if (statusText.includes("test") || statusText.includes("validation")) {  
              acc.verify += 1;  
            }  
            if ((item?.installed && item?.executionCapable) || statusText.includes("execution-ready")) {  
              acc.publish += 1;  
            }  
            return acc;  
          },  
          { draft: 0, review: 0, verify: 0, publish: 0 },  
        );  
        return (  
          <section className="drawer-panel">
            <header>
              <h2>Confidence and operations</h2>
              <p>{viewModel.drawers.builder.liveSurface.note}</p>
            </header>
  
            <div className={`skill-recovery-strip ${toneClass(missionSkillRecoveryNeedsAction ? "warn" : "good")}`}>
              <div>
                <span>Mission skill recovery</span>
                <strong>
                  {missionSkillRecoveryNeedsAction
                    ? `${missionSkillRecoveryTriggers.length} trigger(s), ${missionSkillRecoveryRecommendations.length} skill lead(s)`
                    : "Clear"}
                </strong>
              </div>
              <p>
                {missionSkillRecoveryNeedsAction
                  ? `${
                      missionSkillRecoverySelectedSkill.label ||
                      titleizeToken(missionSkillRecoverySelectedSkill.skillId || "Recovery skill")
                    }: ${
                      missionSkillRecoveryPlan.nextAction ||
                      missionSkillRecoveryActions[0]?.action ||
                      missionSkillRecoveryTriggers[0]?.recoveryAction ||
                      "Choose a recovery skill or route before retrying the same step."
                    } Proof: ${
                      missionSkillRecoveryProofRequirement.label ||
                      missionSkillRecoveryProofArtifactPlan.artifactKind ||
                      "recovery receipt"
                    }.`
                  : "The agent can continue the normal plan, execute, verify, repair loop."}
              </p>
            </div>
  
            <div className="builder-visual-proof-packet compact">
              <div className="builder-live-review-panel-head compact">
                <strong>Visual proof packet</strong>
                <span className="mini-pill muted">{visualProofPacket.annotationCount} annotation mark(s)</span>
              </div>
              <div className="builder-visual-proof-grid">
                <article>
                  <span>Frame</span>
                  <strong>{visualProofPacket.frameLabel}</strong>
                  <small>{visualProofPacket.framePath || "Path pending"}</small>
                </article>
                <article>
                  <span>Target</span>
                  <strong>{visualProofPacket.proofTarget || "Target pending"}</strong>
                  <small>{visualProofPacket.threadTarget || "Thread pending"}</small>
                </article>
                <article>
                  <span>Receipt</span>
                  <strong>{visualProofPacket.receiptHandle || "No receipt yet"}</strong>
                  <small>{visualProofPacket.receiptKind}</small>
                </article>
              </div>
            </div>
  
            <section className="drawer-block monitor-loop-panel">
              <div className="builder-live-review-panel-head compact">
                <div>
                  <h3>{monitoringLoopStudio.headline || "External monitor loops"}</h3>
                  <p>{monitoringLoopStudio.summary || "Monitor loops are waiting for mission state."}</p>
                </div>
                <span className="mini-pill muted">
                  {titleizeToken(monitoringLoopStudio.activationMode || "important_only")}
                </span>
              </div>
              <div className="context-grid compact-metrics">
                <article className="context-item">
                  <span>Active monitors</span>
                  <strong>{monitoringLoopStudio.activeCount || 0}</strong>
                </article>
                <article className="context-item">
                  <span>Warnings</span>
                  <strong>{monitoringLoopStudio.warningCount || 0}</strong>
                </article>
                <article className="context-item">
                  <span>Default</span>
                  <strong>{titleizeToken(monitoringLoopStudio.defaultState || "off_until_enabled_or_blocked")}</strong>
                </article>
              </div>
              <div className="monitor-loop-list">
                {monitoringLoops.map(item => (
                  <article className={`monitor-loop-card ${toneClass(item.tone)}`} key={item.id}>
                    <span>{titleizeToken(item.status)}</span>
                    <strong>{item.label}</strong>
                    <p>{item.trigger}</p>
                    <small>{item.nextAction}</small>
                    <em>{titleizeToken(item.cadence)} · {titleizeToken(item.activation)}</em>
                  </article>
                ))}
              </div>
              <div className="supervisor-intervention-queue" aria-label="Supervisor intervention queue">
                <div className="builder-live-review-panel-head compact">
                  <div>
                    <h4>Supervisor intervention queue</h4>
                    <p>
                      {supervisorInterventionQueue.length > 0
                        ? `${supervisorInterventionQueue.length} ranked before next step.`
                        : "No intervention queued."}
                    </p>
                  </div>
                  <span className={`mini-pill ${toneClass((monitoringLoopStudio.criticalCount || 0) > 0 ? "warn" : "good")}`}>
                    {monitoringLoopStudio.criticalCount || 0} high
                  </span>
                </div>
                {supervisorInterventionQueue.length > 0 ? (
                  supervisorInterventionQueue.map(item => (
                    <article className={`supervisor-intervention-card ${toneClass(item.severity === "high" ? "warn" : "neutral")}`} key={item.interventionId}>
                      <span>{titleizeToken(item.source)} · {titleizeToken(item.severity)}</span>
                      <strong>{item.label}</strong>
                      <p>{item.reason}</p>
                      <small>{item.nextAction}</small>
                    </article>
                  ))
                ) : (
                  <article className="supervisor-intervention-card">
                    <strong>Continue verification</strong>
                    <p>Queue appears when blocked, drifting, or missing proof.</p>
                  </article>
                )}
              </div>
              <div className="drawer-actions">
                <ActionButton onClick={() => setActiveDrawer("queue")} type="button">
                  Review blockers
                </ActionButton>
                <ActionButton onClick={() => setActiveDrawer("proof")} type="button">
                  Review proof
                </ActionButton>
                <ActionButton onClick={() => setActiveDrawer("context")} type="button">
                  Review context
                </ActionButton>
              </div>
            </section>
  
            <section className="drawer-block subagent-command-panel">
              <div className="builder-live-review-panel-head compact">
                <div>
                  <h3>{subagentOrchestrationStudio.headline || "Subagent command center"}</h3>
                  <p>{subagentOrchestrationStudio.summary || "Delegated lanes appear here."}</p>
                </div>
                <span className="mini-pill muted">
                  {titleizeToken(subagentOrchestrationStudio.mergePolicy || "best_score")}
                </span>
              </div>
              <div className="context-grid compact-metrics">
                <article className="context-item">
                  <span>Configured workers</span>
                  <strong>{subagentOrchestrationStudio.configuredWorkers || 1}</strong>
                </article>
                <article className="context-item">
                  <span>Active lanes</span>
                  <strong>{subagentOrchestrationStudio.activeCount || 0}</strong>
                </article>
                <article className="context-item">
                  <span>Blocked lanes</span>
                  <strong>{subagentOrchestrationStudio.blockedCount || 0}</strong>
                </article>
              </div>
              <Suspense fallback={null}>
                <SubagentReadinessPanel
                  studio={subagentOrchestrationStudio}
                />
              </Suspense>
              <div className="subagent-lane-list">
                {subagentLanes.length > 0 ? (
                  subagentLanes.map(item => (
                    <article className={`subagent-lane-card ${toneClass(item.tone)}`} key={item.id}>
                      <div>
                        <span>{titleizeToken(item.role)}</span>
                        <strong>{item.label}</strong>
                      </div>
                      <p>{item.latestEvent}</p>
                      <dl>
                        <div>
                          <dt>Route</dt>
                          <dd>{item.runtime} / {item.provider} / {item.model}</dd>
                        </div>
                        <div>
                          <dt>Status</dt>
                          <dd>{titleizeToken(item.status)} · {item.heartbeat}</dd>
                        </div>
                        <div>
                          <dt>Proof</dt>
                          <dd>{item.proof}</dd>
                        </div>
                      </dl>
                      {item.blockReason || item.supervisorAction ? (
                        <div className="subagent-supervisor-note">
                          <span>Why</span>
                          <p>{item.blockReason || "Supervisor has no lane-specific blocker."}</p>
                          <span>Next</span>
                          <p>{item.supervisorAction || item.nextAction}</p>
                        </div>
                      ) : null}
                      <small>{item.nextAction}</small>
                    </article>
                  ))
                ) : (
                  <article className="subagent-lane-empty">
                    <strong>No lane active</strong>
                    <p>{subagentOrchestrationStudio.recommendedAction}</p>
                  </article>
                )}
              </div>
              {subagentScoreboard.length > 0 ? (
                <div className="subagent-scoreboard">
                  {subagentScoreboard.map(item => (
                    <article key={item.id}>
                      <span>{item.label}</span>
                      <strong>{item.score}</strong>
                      <p>{item.detail}</p>
                    </article>
                  ))}
                </div>
              ) : null}
              <p className="drawer-note">
                Handoffs: {subagentOrchestrationStudio.handoffCount || 0} · {subagentOrchestrationStudio.lastHandoffReason}
              </p>
              <div className="drawer-actions">
                <ActionButton onClick={() => setActiveDrawer("runtime")} type="button">
                  Inspect runtime
                </ActionButton>
                <ActionButton onClick={() => setActiveDrawer("queue")} type="button">
                  Resolve lane blocks
                </ActionButton>
                <ActionButton onClick={() => setActiveDrawer("proof")} type="button">
                  Verify merge proof
                </ActionButton>
              </div>
            </section>
  
            <section className="drawer-block">
              <h3>Confidence engine</h3>
              <div className="confidence-headline">
                <strong className={toneClass(viewModel.drawers.builder.confidence.tone)}>
                  {viewModel.drawers.builder.confidence.label}
                </strong>  
                <span>{viewModel.drawers.builder.confidence.phase}</span>  
              </div>  
              <div className="confidence-meter" role="presentation">  
                <span style={{ width: `${viewModel.drawers.builder.confidence.score}%` }} />  
              </div>  
              <p>  
                {viewModel.drawers.builder.confidence.requiredGateSummary.label}  
                {` · Quality ${viewModel.drawers.builder.confidence.qualityScore}%`}  
                {` · Release ${viewModel.drawers.builder.confidence.releaseStatus}`}  
              </p>  
              <div className="audit-list">  
                {viewModel.drawers.builder.confidence.milestones.map(item => (  
                  <article className="audit-item" key={item.id}>  
                    <strong>{item.label}</strong>  
                    <p>  
                      {item.percent}% · {item.detail}  
                    </p>  
                  </article>  
                ))}  
              </div>  
              <ul>  
                {viewModel.drawers.builder.confidence.nextActions.length > 0 ? (  
                  viewModel.drawers.builder.confidence.nextActions.map(item => (  
                    <li key={`confidence-action-${item}`}>{item}</li>  
                  ))  
                ) : (  
                  <li>No blocking action reported.</li>  
                )}  
              </ul>  
            </section>  
    
            <section className="drawer-block roadmap-event-block">  
              <div className="roadmap-event-head">  
                <div>  
                  <h3>Road to 100%</h3>  
                  <p>  
                    {viewModel.drawers.builder.qualityRoadmap.headline}  
                    {` · Gap ${viewModel.drawers.builder.qualityRoadmap.gap}%`}  
                  </p>  
                </div>  
                <span>  
                  {viewModel.drawers.builder.qualityRoadmap.doneCount} done ·{" "}  
                  {viewModel.drawers.builder.qualityRoadmap.nextCount} next ·{" "}  
                  {viewModel.drawers.builder.qualityRoadmap.blockedCount} blocked  
                </span>  
              </div>  
              {(() => {  
                const tracks = viewModel.drawers.builder.qualityRoadmap.tracks;  
                const activeItem =  
                  tracks.find(item => item.id === activeRoadmapItemId) ||  
                  tracks.find(item => item.state !== "done") ||  
                  tracks[0];  
                return (  
                  <div className="roadmap-event-layout">  
                    <div className="roadmap-event-line" aria-label="Quality roadmap events">  
                      {tracks.map((item, index) => (  
                        <button  
                          className={cx(  
                            "roadmap-event",  
                            toneClass(item.tone),  
                            activeItem?.id === item.id && "active",  
                          )}  
                          key={item.id}  
                          onClick={() => setActiveRoadmapItemId(item.id)}  
                          style={{ "--roadmap-index": index }}  
                          type="button"  
                        >  
                          <span>{titleizeToken(item.state)}</span>  
                          <strong>{item.label}</strong>  
                          <em>{item.detail}</em>  
                        </button>  
                      ))}  
                    </div>  
                    {activeItem ? (  
                      <aside className={`roadmap-popover ${toneClass(activeItem.tone)}`} key={activeItem.id}>  
                        <span>{titleizeToken(activeItem.state)}</span>  
                        <strong>{activeItem.label}</strong>  
                        <p>{activeItem.detail}</p>  
                        <p>{activeItem.hint}</p>  
                        <div className="drawer-actions">  
                          <ActionButton  
                            onClick={() => void handleQualityRoadmapAction(activeItem)}  
                            type="button"  
                          >  
                            {activeItem.suggestedAction || "Open"}  
                          </ActionButton>  
                        </div>  
                      </aside>  
                    ) : null}  
                  </div>  
                );  
              })()}  
            </section>  
    
            <section className="drawer-block">  
              <h3>Live surface</h3>  
              <Field label="Preview">  
                <select onChange={event => setPreviewMode(event.target.value)} value={previewMode}>  
                  {previewModeOptions.map(option => (  
                    <option key={option.id} value={option.id}>  
                      {option.name}  
                    </option>  
                  ))}  
                </select>  
              </Field>  
              {!allowFixturePreviewModes ? (  
                <p className="drawer-footnote">Web control mode is live-backend only.</p>  
              ) : null}  
              <Field label="Live sync">  
                <select  
                  onChange={event => setLiveSyncSeconds(event.target.value)}  
                  value={liveSyncSeconds}  
                >  
                  {LIVE_SYNC_OPTIONS.map(option => (  
                    <option key={option.value} value={option.value}>  
                      {option.label}  
                    </option>  
                  ))}  
                </select>  
              </Field>  
              <p className="drawer-footnote">  
                {previewLabel(previewMode, data.previewMeta)}  
                {lastPushReason ? ` · Last push ${lastPushReason}` : ""}  
              </p>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Profile studio</h3>  
              <div className="field-row">  
                <Field label="Workspace profile">  
                  <select  
                    onChange={event =>  
                      setWorkspaceProfileForm(current => ({  
                        ...current,  
                        userProfile: event.target.value,  
                      }))  
                    }  
                    value={workspaceProfileForm.userProfile}  
                  >  
                    {(snapshot.profiles?.availableProfiles || ["beginner", "builder", "advanced"]).map(  
                      option => (  
                        <option key={option} value={option}>  
                          {titleizeToken(option)}  
                        </option>  
                      ),  
                    )}  
                  </select>  
                </Field>  
                <Field label="Preferred work engine">  
                  <select  
                    onChange={event =>  
                      setWorkspaceProfileForm(current => ({  
                        ...current,  
                        preferredHarness: event.target.value,  
                      }))  
                    }  
                    value={workspaceProfileForm.preferredHarness}  
                  >  
                    {PREFERRED_HARNESS_OPTIONS.map(option => (  
                      <option key={option.value} value={option.value}>  
                        {option.label}  
                      </option>  
                    ))}  
                  </select>  
                </Field>  
              </div>  
    
              <div className="field-row">  
                <Field label="Routing strategy">  
                  <select  
                    onChange={event =>  
                      setWorkspaceProfileForm(current => ({  
                        ...current,  
                        routingStrategy: event.target.value,  
                      }))  
                    }  
                    value={workspaceProfileForm.routingStrategy}  
                  >  
                    {ROUTING_STRATEGY_OPTIONS.map(option => (  
                      <option key={option.value} value={option.value}>  
                        {option.label}  
                      </option>  
                    ))}  
                  </select>  
                </Field>  
                <Field label="Execution target">  
                  <select  
                    onChange={event =>  
                      setWorkspaceProfileForm(current => ({  
                        ...current,  
                        executionTargetPreference: event.target.value,  
                      }))  
                    }  
                    value={workspaceProfileForm.executionTargetPreference}  
                  >  
                    {EXECUTION_TARGET_OPTIONS.map(option => (  
                      <option key={option.value} value={option.value}>  
                        {option.label}  
                      </option>  
                    ))}  
                  </select>  
                </Field>  
              </div>  
    
              <div className="field-row">  
                <Field label="OpenAI / Codex auth path">  
                  <select  
                    onChange={event =>  
                      setWorkspaceProfileForm(current => ({  
                        ...current,  
                        openaiCodexAuthMode: event.target.value,  
                      }))  
                    }  
                    value={workspaceProfileForm.openaiCodexAuthMode}  
                  >  
                    {OPENAI_CODEX_AUTH_OPTIONS.map(option => (  
                      <option key={option.value} value={option.value}>  
                        {option.label}  
                      </option>  
                    ))}  
                  </select>  
                </Field>  
                <Field label="MiniMax auth path">  
                  <select  
                    onChange={event =>  
                      setWorkspaceProfileForm(current => ({  
                        ...current,  
                        minimaxAuthMode: event.target.value,  
                      }))  
                    }  
                    value={workspaceProfileForm.minimaxAuthMode}  
                  >  
                    {MINIMAX_AUTH_OPTIONS.map(option => (  
                      <option key={option.value} value={option.value}>  
                        {option.label}  
                      </option>  
                    ))}  
                  </select>  
                </Field>  
              </div>  
    
              <div className="field-row">  
                <Field label="Commit message style">  
                  <select  
                    onChange={event =>  
                      setWorkspaceProfileForm(current => ({  
                        ...current,  
                        commitMessageStyle: event.target.value,  
                      }))  
                    }  
                    value={workspaceProfileForm.commitMessageStyle}  
                  >  
                    {COMMIT_STYLE_OPTIONS.map(option => (  
                      <option key={option.value} value={option.value}>  
                        {option.label}  
                      </option>  
                    ))}  
                  </select>  
                </Field>  
              </div>  
    
              <label className="check-field">  
                <input  
                  checked={workspaceProfileForm.autoOptimizeRouting}  
                  onChange={event =>  
                    setWorkspaceProfileForm(current => ({  
                      ...current,  
                      autoOptimizeRouting: event.target.checked,  
                    }))  
                  }  
                  type="checkbox"  
                />  
                <span>Enable deterministic routing auto-optimize when enough local runs exist.</span>  
              </label>  
    
              <div className="drawer-actions">  
                <ActionButton onClick={() => void saveWorkspacePolicy()} variant="primary">  
                  Save workspace policy  
                </ActionButton>  
              </div>  
    
              <div className="drawer-list">  
                {viewModel.drawers.builder.profileStudio.behavior.map(item => (  
                  <article className="drawer-card" key={`profile-behavior-${item.label}`}>  
                    <span>{item.label}</span>  
                    <strong>{item.value}</strong>  
                  </article>  
                ))}  
              </div>  
              <details>  
                <summary>Available profile contracts</summary>  
                <div className="drawer-list">  
                  {viewModel.drawers.builder.profileStudio.profileRows.map(item => (  
                    <article className={`drawer-card ${toneClass(item.tone)}`} key={item.id}>  
                      <span>{item.label}</span>  
                      <strong>{item.description}</strong>  
                      <p>  
                        {item.approval} approvals · {item.autonomy} autonomy · {item.visibility} visibility  
                      </p>  
                      <p>{item.density} density</p>  
                    </article>  
                  ))}  
                </div>  
              </details>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Service management</h3>  
              <p>  
                {`${viewModel.drawers.builder.serviceStudio.summary.healthyCount}/${viewModel.drawers.builder.serviceStudio.summary.totalItems} healthy`}  
                {` · ${viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount} need attention`}  
                {` · ${viewModel.drawers.builder.serviceStudio.availableActionCount} executable actions`}  
              </p>  
              <div className="drawer-list">  
                {viewModel.drawers.builder.serviceStudio.services.map(service => (  
                  <article className={`drawer-card ${toneClass(service.tone)}`} key={service.serviceId}>  
                    <span>{service.category}</span>  
                    <strong>{service.label}</strong>  
                    <p>  
                      {service.status}  
                      {service.version ? ` · ${service.version}` : ""}  
                    </p>  
                    <p>  
                      {service.managementMode}  
                      {service.required ? " · required" : " · optional"}  
                    </p>
                    {service.details ? <p>{service.details}</p> : null}
                    {service.updateSafety?.summary ? (
                      <div className="update-safety-note" aria-label={`${service.label} update safety`}>
                        <strong>{service.updateSafety.label || "Review before updating"}</strong>
                        <p>{service.updateSafety.summary}</p>
                        <span>{service.updateSafety.safeNextStep}</span>
                        {service.updateSafety.verifyAfterUpdate ? <span>Fluxio will re-check setup after the update.</span> : null}
                      </div>
                    ) : null}
                    {service.actions.length > 0 ? (
                      <div className="drawer-actions">
                        {service.actions.slice(0, 3).map(action => (  
                          <ActionButton  
                            key={`${service.serviceId}-${action.actionId}`}  
                            onClick={() => void runWorkspaceActionSpec(action)}  
                          >  
                            {action.label}  
                          </ActionButton>  
                        ))}  
                      </div>  
                    ) : null}  
                  </article>  
                ))}  
              </div>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Skill studio</h3>  
              <p>  
                {`${viewModel.drawers.builder.skillStudio.summary.reviewedReusableCount}/${viewModel.drawers.builder.skillStudio.summary.totalSkills} reviewed reusable`}  
                {` · ${viewModel.drawers.builder.skillStudio.summary.needsTestCount} need tests`}  
                {` · ${viewModel.drawers.builder.skillStudio.summary.learnedCount} learned`}  
              </p>  
              <p>  
                {`${viewModel.drawers.builder.skillStudio.summary.executionReadyCount} execution-ready`}  
                {` · ${viewModel.drawers.builder.skillStudio.summary.installedCount} installed`}  
                {` · ${viewModel.drawers.builder.skillStudio.summary.uniquePackCount} unique packs`}  
              </p>  
              <div className="skill-toolbar">  
                <Field label="Filter">  
                  <select  
                    onChange={event => setSkillStudioFilter(event.target.value)}  
                    value={skillStudioFilter}  
                  >  
                    <option value="all">All packs</option>  
                    <option value="recommended">Recommended only</option>  
                    <option value="installed">Installed only</option>  
                    <option value="needs_attention">Needs attention</option>  
                  </select>  
                </Field>  
                <Field label="Search">  
                  <input  
                    onChange={event => setSkillStudioQuery(event.target.value)}  
                    placeholder="Search by pack or profile"  
                    value={skillStudioQuery}  
                  />  
                </Field>  
              </div>  
              <p className="drawer-footnote">{viewModel.drawers.builder.skillStudio.capabilitiesNote}</p>  
              <div className="context-grid compact-metrics">
                <article className="context-item">
                  <span>Agent-proposed drafts</span>
                  <strong>{skillLifecycleCounts.draft}</strong>
                </article>
                <article className="context-item">  
                  <span>Human review</span>  
                  <strong>{skillLifecycleCounts.review}</strong>  
                </article>  
                <article className="context-item">  
                  <span>Validation and tests</span>  
                  <strong>{skillLifecycleCounts.verify}</strong>  
                </article>  
                <article className="context-item">  
                  <span>Publish-ready</span>
                  <strong>{skillLifecycleCounts.publish}</strong>
                </article>
              </div>
              <details open>
                <summary>Design and frontend recommendations</summary>
                <div className="drawer-list compact">
                  {designFrontendRecommended.length > 0 ? (  
                    designFrontendRecommended.slice(0, 6).map(item => (  
                      <article className={`drawer-card ${toneClass(item.tone)}`} key={`design-${item.id}`}>  
                        <span>{item.originType}</span>  
                        <strong>{item.label}</strong>  
                        <p>{item.description}</p>  
                        <p>{item.installed ? "Installed" : "Recommended"} · {item.executionCapable ? "Execution-capable" : "Guidance only"}</p>  
                      </article>  
                    ))  
                  ) : (  
                    <article className="drawer-card">  
                      <strong>No design/front-end recommendation matches the current filter.</strong>  
                    </article>  
                  )}  
                </div>  
              </details>  
              <details open>  
                <summary>Recommended packs</summary>  
                <div className="drawer-list">  
                  {filteredRecommendedSkills.length > 0 ? (  
                    filteredRecommendedSkills.map(item => (  
                      <article className={`drawer-card ${toneClass(item.tone)}`} key={item.id}>  
                        <span>{item.originType}</span>  
                        <strong>{item.label}</strong>  
                        <p>{item.description}</p>  
                        <p>  
                          {item.status}  
                          {item.installed ? " · installed" : " · not installed"}  
                          {item.executionCapable ? " · execution-capable" : " · guidance-only"}  
                        </p>  
                        {item.profileSuitability?.length > 0 ? (  
                          <div className="pill-row">  
                            {item.profileSuitability.map(entry => (  
                              <span className="mini-pill" key={`${item.id}-${entry}`}>  
                                {entry}  
                              </span>  
                            ))}  
                          </div>  
                        ) : null}  
                        {item.permissions?.length > 0 ? (  
                          <div className="pill-row">  
                            {item.permissions.map(permission => (  
                              <span className="mini-pill muted" key={`${item.id}-perm-${permission}`}>  
                                {permission}  
                              </span>  
                            ))}  
                          </div>  
                        ) : null}  
                      </article>  
                    ))  
                  ) : (  
                    <article className="drawer-card">  
                      <strong>No recommended pack matches this filter.</strong>  
                    </article>  
                  )}  
                </div>  
              </details>  
              <details>  
                <summary>Curated inventory</summary>  
                <div className="drawer-list">  
                  {filteredCuratedSkills.length > 0 ? (  
                    filteredCuratedSkills.map(item => (  
                      <article className={`drawer-card ${toneClass(item.tone)}`} key={item.id}>  
                        <span>{item.originType}</span>  
                        <strong>{item.label}</strong>  
                        <p>  
                          {item.status}  
                          {item.installed ? " · installed" : " · not installed"}  
                          {item.executionCapable ? " · execution-capable" : " · guidance-only"}  
                        </p>  
                        <p>  
                          Used {item.usageCount} time(s) · Helped {item.helpedCount} run(s)  
                        </p>  
                        {item.profileSuitability?.length > 0 ? (  
                          <div className="pill-row">  
                            {item.profileSuitability.map(entry => (  
                              <span className="mini-pill" key={`${item.id}-${entry}`}>  
                                {entry}  
                              </span>  
                            ))}  
                          </div>  
                        ) : null}  
                      </article>  
                    ))  
                  ) : (  
                    <article className="drawer-card">  
                      <strong>No curated pack matches this filter.</strong>  
                    </article>  
                  )}  
                </div>  
              </details>  
              <details>  
                <summary>Quality actions</summary>  
                <ul>  
                  {viewModel.drawers.builder.skillStudio.nextQualityActions.length > 0 ? (  
                    viewModel.drawers.builder.skillStudio.nextQualityActions.map(item => (  
                      <li key={`skill-next-${item}`}>{item}</li>  
                    ))  
                  ) : (  
                    <li>Skill quality checklist is currently clear.</li>  
                  )}  
                </ul>  
              </details>  
              <details>  
                <summary>Profile coverage</summary>  
                <div className="drawer-list compact">  
                  {Object.entries(viewModel.drawers.builder.skillStudio.coverageByProfile).map(  
                    ([profile, count]) => (  
                      <article className="drawer-card" key={`coverage-${profile}`}>  
                        <span>{profile}</span>  
                        <strong>{count} suitable pack(s)</strong>  
                      </article>  
                    ),  
                  )}  
                </div>  
              </details>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Workflow studio</h3>  
              <p>  
                {`${viewModel.drawers.builder.workflowStudio.summary.reviewedCount}/${viewModel.drawers.builder.workflowStudio.summary.recipeCount} reviewed`}  
                {` · ${viewModel.drawers.builder.workflowStudio.summary.blockedCount} blocked`}  
                {` · Recommended mode ${viewModel.drawers.builder.workflowStudio.summary.recommendedMode}`}  
              </p>  
              <div className="drawer-list">  
                {viewModel.drawers.builder.workflowStudio.recipes.map(item => (  
                  <article className={`drawer-card ${toneClass(item.tone)}`} key={item.workflowId}>  
                    <span>{item.surface}</span>  
                    <strong>{item.label}</strong>  
                    <p>{item.description}</p>  
                    <p>  
                      {item.status} · {item.audience} · {item.runtimeChoice}  
                    </p>  
                    {item.verificationDefaults.length > 0 ? (  
                      <p>{`Default verification: ${item.verificationDefaults.join(" | ")}`}</p>  
                    ) : null}  
                  </article>  
                ))}  
              </div>  
              <details>  
                <summary>Learning queue</summary>  
                <ul>  
                  {viewModel.drawers.builder.workflowStudio.learningQueue.length > 0 ? (  
                    viewModel.drawers.builder.workflowStudio.learningQueue.map(item => (  
                      <li key={`learning-${item}`}>{listLabel(item)}</li>  
                    ))  
                  ) : (  
                    <li>No pending workflow learning item.</li>  
                  )}  
                </ul>  
              </details>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Repo operations</h3>  
              <div className="drawer-list">  
                {[...viewModel.drawers.builder.gitActions, ...viewModel.drawers.builder.validationActions].map(  
                  action => (  
                    <article className={`drawer-card ${toneClass(action.tone)}`} key={`${action.surface}-${action.actionId}`}>  
                      <span>{titleizeToken(action.surface)}</span>  
                      <strong>{action.label}</strong>  
                      <p>{action.detail}</p>  
                      <div className="drawer-actions">  
                        <ActionButton onClick={() => void runWorkspaceActionSpec(action)}>  
                          {action.requiresApproval ? "Approve and run" : "Run action"}  
                        </ActionButton>  
                      </div>  
                    </article>  
                  ),  
                )}  
              </div>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Release gates</h3>  
              <div className="drawer-list">  
                {viewModel.drawers.builder.confidence.gates.length > 0 ? (  
                  viewModel.drawers.builder.confidence.gates.map(gate => (  
                    <article className={`drawer-card ${toneClass(gate.tone)}`} key={gate.gateId}>  
                      <span>{gate.required ? "Required" : "Quality"}</span>  
                      <strong>{gate.label}</strong>  
                      <p>{gate.details}</p>  
                    </article>  
                  ))  
                ) : (  
                  <article className="drawer-card">  
                    <strong>Release gates are not available yet.</strong>  
                  </article>  
                )}  
              </div>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Feature truth</h3>  
              <details open>  
                <summary>Real and ready</summary>  
                <ul>  
                  {viewModel.drawers.builder.featureTruth.realReady.map(item => (  
                    <li key={`ready-${item}`}>{item}</li>  
                  ))}  
                </ul>  
              </details>  
              <details>  
                <summary>Real but secondary</summary>  
                <ul>  
                  {viewModel.drawers.builder.featureTruth.realSecondary.map(item => (  
                    <li key={`secondary-${item}`}>{item}</li>  
                  ))}  
                </ul>  
              </details>  
              <details>  
                <summary>Fixture and review only</summary>  
                <ul>  
                  {viewModel.drawers.builder.featureTruth.fixtureOnly.map(item => (  
                    <li key={`fixture-${item}`}>{item}</li>  
                  ))}  
                </ul>  
              </details>  
              <details>  
                <summary>Not ready yet</summary>  
                <ul>  
                  {viewModel.drawers.builder.featureTruth.notReady.map(item => (  
                    <li key={`not-ready-${item}`}>{item}</li>  
                  ))}  
                </ul>  
              </details>  
            </section>  
    
            <section className="drawer-block">  
              <h3>Core state audit</h3>  
              <div className="audit-list">  
                {viewModel.drawers.builder.stateAudit.map(item => (  
                  <article className={`audit-item state-${item.state}`} key={item.id}>  
                    <strong>{item.label}</strong>  
                    <p>{item.nextAction}</p>  
                  </article>  
                ))}  
              </div>  
            </section>  
          </section>  
        );  
      }  
    
      return (  
        <section className="drawer-panel">  
          <header>  
            <p className="eyebrow">Context</p>  
            <h2>Operational context</h2>  
            <p>Open only when you need runtime truth, guardrails, or escalation details.</p>  
          </header>  
          {viewModel.drawers.context.groups.map(group => (  
            <section className="drawer-block" key={group.title}>  
              <h3>{group.title}</h3>  
              <div className="context-grid">  
                {group.items.map(item => (  
                  <article className="context-item" key={`${group.title}-${item.label}-${item.value}`}>  
                    <span>{item.label}</span>  
                    <strong>{item.value}</strong>  
                    {item.note ? <p>{item.note}</p> : null}  
                  </article>  
                ))}  
              </div>  
            </section>  
          ))}  
          <section className="drawer-block">  
            <h3>Escalation</h3>  
            <p>{data.telegramReady ? "Telegram ready" : "Telegram not configured"}</p>  
            <div className="drawer-actions">  
              <ActionButton onClick={() => setShowEscalationDialog(true)} variant="primary">  
                Configure  
              </ActionButton>  
              <ActionButton onClick={() => void handleSendTestPing()}>Send test ping</ActionButton>  
            </div>  
          </section>  
        </section>  
      );
  
}
