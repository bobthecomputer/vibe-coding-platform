export function titleizeToken(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, char => char.toUpperCase());
}

export function runtimeLabel(runtimeId) {
  if (runtimeId === "openclaw") return "OpenClaw";
  if (runtimeId === "hermes") return "Hermes";
  return runtimeId || "Runtime";
}

export function missionStatusTone(status) {
  switch (status) {
    case "completed":
    case "healthy":
    case "passed":
      return "good";
    case "blocked":
    case "verification_failed":
    case "failed":
    case "missing":
      return "bad";
    case "needs_approval":
    case "waiting_for_approval":
    case "verify_pending":
    case "install_available":
    case "installing":
    case "detected":
    case "running":
      return "warn";
    default:
      return "neutral";
  }
}

export function formatDurationCompact(totalSeconds) {
  const seconds = Math.max(0, Number(totalSeconds || 0));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
}

export function describeMissionLocus(mission) {
  const delegated = mission?.delegated_runtime_sessions || [];
  if (delegated.some(item => item.status === "waiting_for_approval")) {
    return "Delegated / approval-blocked";
  }
  if (delegated.some(item => ["launching", "running"].includes(item.status))) {
    return "Delegated / active";
  }
  if ((mission?.proof?.pending_approvals || []).length) {
    return "Local / approval-blocked";
  }
  return "Local / direct";
}

export function selectedWorkspace(snapshot, selectedWorkspaceId) {
  const workspaces = snapshot?.workspaces || [];
  return (
    workspaces.find(item => item.workspace_id === selectedWorkspaceId) ||
    workspaces[0] ||
    null
  );
}

export function selectedMission(snapshot, selectedMissionId) {
  const missions = snapshot?.missions || [];
  return (
    missions.find(item => item.mission_id === selectedMissionId) ||
    missions[missions.length - 1] ||
    null
  );
}

export function activeProfileId(snapshot, onboarding, workspace, mission) {
  const tutorial = onboarding?.tutorial || snapshot?.onboarding?.tutorial || {};
  return (
    workspace?.user_profile ||
    mission?.selected_profile ||
    tutorial.selectedProfile ||
    snapshot?.profiles?.defaultProfile ||
    "builder"
  );
}

export function profileDetails(snapshot, profileId) {
  return snapshot?.profiles?.details?.[profileId] || {};
}

export function currentProfileParameters(snapshot, profileId, workspace) {
  return (
    profileDetails(snapshot, profileId)?.parameters ||
    workspace?.profileParameters ||
    {}
  );
}

export function visibilityProfileState(profileParams) {
  const level = profileParams?.visibilityLevel || "balanced";
  return {
    level,
    guided: level === "guided",
    detailed: level === "detailed" || level === "expert",
    expert: level === "expert",
  };
}

export function describeApprovalBehavior(level) {
  switch (level) {
    case "strict":
      return "Fluxio asks before risky work, explains more, and keeps the loop safer.";
    case "hands_free":
      return "Fluxio keeps moving unless proof, safety, or environment boundaries force an interruption.";
    default:
      return "Fluxio keeps moving on bounded work, but still stops at meaningful risk and trust boundaries.";
  }
}

export function describeExplanationBehavior(level) {
  switch (level) {
    case "high":
      return "Expect more plain-language explanation and slower, safer framing.";
    case "low":
      return "Expect denser system truth and less narration.";
    default:
      return "Expect concise, practical explanation without hiding the real state.";
  }
}

export function describeVisibilityBehavior(level) {
  switch (level) {
    case "guided":
      return "The UI foregrounds the next action and hides less-important detail until needed.";
    case "expert":
      return "The UI keeps more raw state visible so advanced operators can inspect without extra clicks.";
    case "detailed":
      return "The UI keeps routing, proof, and runtime detail visible during the mission.";
    default:
      return "The UI balances clarity with enough system truth to stay trustworthy.";
  }
}

export function describeAskBoundary(profileParams, runUntilBehavior) {
  const approvalDetail = {
    strict: "before most mutating actions",
    tiered: "before higher-risk Git, service, or runtime changes",
    hands_free: "only when safety, proof, or environment boundaries require it",
  }[profileParams?.approvalStrictness || "tiered"];
  const runUntilDetail =
    runUntilBehavior === "continue_until_blocked"
      ? "continue until something blocks execution"
      : "pause as soon as a failure needs judgment";
  return `Fluxio will ask ${approvalDetail}, and it will ${runUntilDetail}.`;
}

export function describeProfileFit(profileId) {
  switch (profileId) {
    case "beginner":
      return "Best when you want more help, more explanation, and lower-risk autonomy.";
    case "advanced":
      return "Best when you already know the shape of the work and want faster iteration.";
    case "experimental":
      return "Best when you accept broader autonomy and more aggressive exploration.";
    default:
      return "Best when you want a reliable default that still feels free to build.";
  }
}

export function missionObjectivePlaceholder(profileId) {
  switch (profileId) {
    case "beginner":
      return "Describe the outcome in plain language, what good looks like, and what Fluxio should avoid. Optional timer: 'for 45m'.";
    case "advanced":
      return "State the target change, proof bar, and constraints Fluxio must keep. Optional timer: 'for 45m'.";
    case "experimental":
      return "State the target, proof bar, and allowed exploration. Optional timer: 'for 45m'.";
    default:
      return "Describe the outcome, proof expectations, and success criteria. Optional timer: 'for 45m'.";
  }
}

export function missionChecksPlaceholder(profileId) {
  switch (profileId) {
    case "beginner":
      return "One per line: app still opens, tests pass, summary is easy to review";
    case "advanced":
      return "One per line: targeted tests pass, patch is coherent, proof is captured";
    case "experimental":
      return "One per line: baseline verified, new branch explored, best path justified";
    default:
      return "One per line: tests pass, run report written, proof summary ready";
  }
}

export function describeMissionPhase(mission) {
  const missionLoop = mission?.missionLoop || {};
  const phase = missionLoop.currentCyclePhase || mission?.state?.current_cycle_phase || "plan";
  switch (phase) {
    case "plan":
      return "Fluxio is shaping the next bounded move and deciding what context it needs to carry forward.";
    case "execute":
      return "Fluxio is actively working the objective and turning the current plan into actions and proof.";
    case "verify":
      return "Fluxio is checking whether the work actually matches the mission proof bar.";
    case "replan":
      return "Fluxio is adapting after new evidence, failure, or a changed path to success.";
    case "approval_wait":
      return "Fluxio is waiting at an approval boundary and keeping continuity ready for resume.";
    default:
      return "Fluxio is maintaining the current mission loop and shared proof state.";
  }
}

export function resolveMissionPauseReason(mission) {
  const missionLoop = mission?.missionLoop || {};
  const timeBudget = missionLoop.timeBudget;
  return (
    missionLoop.pauseReason ||
    timeBudget?.lastPauseReason ||
    mission?.state?.last_budget_pause_reason ||
    mission?.proof?.pending_approvals?.[0] ||
    (missionLoop.continuityState === "approval_waiting" ? missionLoop.continuityDetail : "") ||
    mission?.state?.stop_reason ||
    mission?.state?.pause_reason ||
    mission?.state?.pauseReason ||
    ""
  );
}

export function resolveCurrentRuntimeLane(mission) {
  const currentRuntimeLane =
    mission?.missionLoop?.currentRuntimeLane || mission?.state?.current_runtime_lane;
  return (
    currentRuntimeLane ||
    `${runtimeLabel(mission?.runtime_id)} primary lane ${titleizeToken(
      mission?.state?.status || "draft",
    )}`
  );
}

export function firstPendingQuestion(pendingQuestions) {
  return Array.isArray(pendingQuestions) ? pendingQuestions[0] || null : null;
}

export function describeMissionKnownState(mission) {
  const missionLoop = mission?.missionLoop || {};
  const approvals = (mission?.proof?.pending_approvals || []).length;
  const failedChecks = (
    mission?.proof?.failed_checks ||
    mission?.state?.verification_failures ||
    []
  ).length;
  const phase = missionLoop.currentCyclePhase || mission?.state?.current_cycle_phase || "plan";
  return `${titleizeToken(mission?.state?.status || "draft")} in ${titleizeToken(phase)}. ${approvals} approval ${approvals === 1 ? "item" : "items"} waiting. ${failedChecks} failed check${failedChecks === 1 ? "" : "s"}.`;
}

export function describeMissionAssumption(mission, pendingQuestions) {
  if ((mission?.proof?.pending_approvals || []).length > 0) {
    return "The proposed next step is directionally right, but the risk is high enough to keep operator approval in the loop.";
  }
  if (firstPendingQuestion(pendingQuestions)) {
    return "Fluxio does not have enough scope clarity to keep moving safely without your answer.";
  }
  if ((mission?.state?.verification_failures || []).length > 0) {
    return "The first failed check is the best current lead, but the root cause may still be broader than the latest patch.";
  }
  const pauseReason = resolveMissionPauseReason(mission);
  if (pauseReason) {
    return `Fluxio can continue once this boundary is resolved: ${pauseReason}.`;
  }
  return "Current context is strong enough to keep moving inside the mission boundary without another clarification pass.";
}

export function describeMissionNeedsInput(mission, pendingQuestions) {
  const pendingApproval = mission?.proof?.pending_approvals?.[0];
  if (pendingApproval) {
    return pendingApproval;
  }
  const question = firstPendingQuestion(pendingQuestions);
  if (question?.question) {
    return question.question;
  }
  if ((mission?.state?.verification_failures || []).length > 0) {
    return `Review ${mission.state.verification_failures[0]} and decide whether Fluxio should repair, retry, or widen the diagnosis.`;
  }
  return "Nothing right now. Fluxio has enough context to continue.";
}

export function describeNextOperatorAction(mission, pendingQuestions) {
  const pendingApprovals = (mission?.proof?.pending_approvals || []).length;
  const pendingQuestionCount = Array.isArray(pendingQuestions) ? pendingQuestions.length : 0;
  const verificationFailures = (mission?.state?.verification_failures || []).length;
  const pauseReason = resolveMissionPauseReason(mission);

  if (pendingApprovals > 0) {
    return "Review the next approval so Fluxio can continue without losing the mission thread.";
  }
  if (pendingQuestionCount > 0) {
    return "Answer the pending planning question so Fluxio can continue with the right scope and context.";
  }
  if (verificationFailures > 0) {
    return "Inspect the first failed verification and decide whether Fluxio should repair, retry, or widen the search.";
  }
  if (pauseReason) {
    return `Resolve the pause reason: ${pauseReason}.`;
  }
  return "Let the mission run, watch proof and time budget, and step in only when the next real boundary appears.";
}

export function latestWorkspaceActionRecord(records, actionId) {
  const items = Array.isArray(records) ? records.slice().reverse() : [];
  return items.find(item => item?.proposal?.args?.workspaceActionId === actionId) || null;
}

export function latestSetupRecordForDependency(history, dependencyId) {
  const items = Array.isArray(history) ? history.slice().reverse() : [];
  return items.find(item => item?.proposal?.args?.dependencyId === dependencyId) || null;
}

export function previewLabel(previewMode, previewMeta) {
  if (previewMode === "live") {
    if (previewMeta?.id && previewMeta.id !== "live") {
      return `${previewMeta?.name || "Review fixture"} fallback`;
    }
    return "Live backend";
  }
  return `${previewMeta?.name || "Fixture"} preview`;
}
