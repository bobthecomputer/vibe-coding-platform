import {
  describeMissionAssumption,
  describeMissionKnownState,
  describeMissionLocus,
  describeMissionNeedsInput,
  describeMissionPhase,
  describeNextOperatorAction,
  formatDurationCompact,
  missionStatusTone,
  resolveCurrentRuntimeLane,
  resolveMissionPauseReason,
  runtimeLabel,
  titleizeToken,
} from "./fluxioHelpers.js";

function uniq(items) {
  return [...new Set(items.filter(Boolean))];
}

function humanRuntimeEnvironment(setupHealth, runtimeId) {
  const wslReady = (setupHealth?.dependencies || []).some(
    dependency => dependency.dependencyId === "wsl2" && dependency.stage === "healthy",
  );
  if (!runtimeId) {
    return wslReady ? "WSL2 ready" : "Environment blocked";
  }
  return `${wslReady ? "WSL2" : "Environment"} · ${runtimeLabel(runtimeId)}`;
}

function deriveTopBarLiveStatus(mission, pendingQuestions) {
  if (!mission) {
    return { label: "No active mission", tone: "neutral" };
  }
  if ((mission.proof?.pending_approvals || []).length > 0) {
    return { label: "Needs approval", tone: "warn" };
  }
  if ((pendingQuestions || []).length > 0) {
    return { label: "Needs operator input", tone: "warn" };
  }
  if ((mission.state?.verification_failures || []).length > 0) {
    return { label: "Verification failed", tone: "bad" };
  }
  if (mission.state?.status === "completed") {
    return { label: "Run completed", tone: "good" };
  }
  if (mission.state?.status === "running") {
    return { label: "Run active", tone: "good" };
  }
  return {
    label: titleizeToken(mission.state?.status || mission.missionLoop?.continuityState || "active"),
    tone: missionStatusTone(mission.state?.status),
  };
}

function derivePrimaryAction(mission, pendingQuestions) {
  if (!mission) {
    return {
      kind: "start",
      label: "Start first mission",
      reason: "Pick one real objective so Fluxio can supervise a real run instead of showing empty structure.",
    };
  }
  if ((mission.proof?.pending_approvals || []).length > 0) {
    return {
      kind: "urgent",
      label: "Review approval",
      reason: mission.proof.pending_approvals[0],
    };
  }
  if ((pendingQuestions || []).length > 0) {
    return {
      kind: "urgent",
      label: "Answer question",
      reason: pendingQuestions[0].question || "Fluxio needs operator input before it can continue safely.",
    };
  }
  if ((mission.state?.verification_failures || []).length > 0) {
    return {
      kind: "proof",
      label: "Review failure",
      reason: mission.state.verification_failures[0],
    };
  }
  if (mission.missionLoop?.continuityState === "resume_available" || mission.state?.status === "queued") {
    return {
      kind: "resume",
      label: "Resume mission",
      reason:
        mission.missionLoop?.continuityDetail ||
        mission.state?.continuity_detail ||
        "The run can continue from the last recorded checkpoint.",
    };
  }
  if (mission.state?.status === "completed") {
    return {
      kind: "proof",
      label: "Review proof",
      reason: mission.proof?.summary || "Review the final evidence before closing the run.",
    };
  }
  return {
    kind: "review",
    label: "Review live run",
    reason: describeNextOperatorAction(mission, pendingQuestions),
  };
}

function deriveCurrentTask(mission) {
  const latestRevision = mission?.plan_revisions?.[mission.plan_revisions.length - 1];
  const revisionStep = latestRevision?.steps?.find(step => step.status === "in_progress");
  if (revisionStep?.title) {
    return revisionStep.title;
  }
  if (mission?.state?.remaining_steps?.length) {
    return mission.state.remaining_steps[0];
  }
  if (mission?.delegated_runtime_sessions?.length) {
    const session = mission.delegated_runtime_sessions[0];
    return session.detail || session.last_event || "Delegated lane active";
  }
  if (mission?.state?.active_step_id) {
    return titleizeToken(mission.state.active_step_id);
  }
  return mission?.proof?.summary || "Waiting for the next checkpoint.";
}

function deriveNextCheckpoint(mission) {
  const latestRevision = mission?.plan_revisions?.[mission.plan_revisions.length - 1];
  const nextPendingStep = latestRevision?.steps?.find(step => step.status === "pending");
  if (nextPendingStep?.title) {
    return nextPendingStep.title;
  }
  if ((mission?.state?.remaining_steps || []).length > 1) {
    return mission.state.remaining_steps[1];
  }
  if (mission?.state?.status === "completed") {
    return "Operator review and close-out";
  }
  return "Await the next recorded checkpoint";
}

function deriveTaskItems(mission) {
  const latestRevision = mission?.plan_revisions?.[mission.plan_revisions.length - 1];
  const revisionSteps = Array.isArray(latestRevision?.steps) ? latestRevision.steps : [];
  if (revisionSteps.length > 0) {
    return revisionSteps.map((step, index) => ({
      id: step.step_id || `step-${index + 1}`,
      title: step.title || titleizeToken(step.step_id || `step ${index + 1}`),
      status: step.status || "pending",
      detail:
        step.description ||
        (step.status === "in_progress"
          ? mission?.proof?.summary || "Fluxio is actively working this step."
          : step.status === "completed"
            ? "Completed and carried forward into the current proof state."
            : "Queued behind the current step."),
    }));
  }

  const currentTask = deriveCurrentTask(mission);
  const nextSteps = Array.isArray(mission?.state?.remaining_steps) ? mission.state.remaining_steps : [];
  const items = [];

  if (currentTask) {
    items.push({
      id: "current-task",
      title: currentTask,
      status: mission?.state?.status === "completed" ? "completed" : "in_progress",
      detail:
        mission?.proof?.summary ||
        mission?.missionLoop?.lastVerificationSummary ||
        "Fluxio is supervising the active task.",
    });
  }

  nextSteps.forEach((title, index) => {
    if (!title || title === currentTask) {
      return;
    }
    items.push({
      id: `queued-step-${index + 1}`,
      title,
      status: "pending",
      detail: index === 0 ? "This is the next checkpoint after the focused task." : "Queued behind the current checkpoint.",
    });
  });

  if (items.length > 0) {
    return items;
  }

  return [
    {
      id: "await-checkpoint",
      title: "Await the next checkpoint",
      status: "pending",
      detail: "Fluxio has not recorded a task sequence for this run yet.",
    },
  ];
}

function deriveTaskNavigator(mission) {
  if (!mission) {
    return {
      subtitle:
        "Keep one task visible at a time. Once a real mission exists, Fluxio lets the operator move through the plan without flooding the screen.",
      positionLabel: "1 of 1",
      currentIndex: 0,
      previousLabel: "Start of plan",
      nextLabel: "Create first mission",
      items: [
        {
          id: "task-create-mission",
          title: "Create first mission",
          status: "pending",
          detail: "A real mission unlocks task focus, proof, approvals, and replayable runtime state.",
        },
      ],
    };
  }

  const items = deriveTaskItems(mission);
  let currentIndex = items.findIndex(item => item.status === "in_progress");
  if (currentIndex < 0) {
    currentIndex = items.findIndex(item => item.status === "pending");
  }
  if (currentIndex < 0) {
    currentIndex = Math.max(items.length - 1, 0);
  }

  return {
    subtitle:
      "Show one task at a time in the center lane. Use previous and next to move through the current plan instead of reading a wall of equal-weight cards.",
    positionLabel: `${currentIndex + 1} of ${items.length}`,
    currentIndex,
    previousLabel: currentIndex > 0 ? items[currentIndex - 1].title : "Start of plan",
    nextLabel:
      currentIndex < items.length - 1
        ? items[currentIndex + 1].title
        : mission?.state?.status === "completed"
          ? "Proof review"
          : deriveNextCheckpoint(mission),
    items,
  };
}

function deriveBlockerCount(mission, pendingQuestions) {
  return (
    (mission?.proof?.pending_approvals || []).length +
    (pendingQuestions || []).length +
    (mission?.state?.verification_failures || []).length
  );
}

function deriveElapsedLabel(mission) {
  const timeBudget = mission?.missionLoop?.timeBudget || {};
  if (typeof timeBudget.elapsedSeconds === "number") {
    return formatDurationCompact(timeBudget.elapsedSeconds);
  }
  if (typeof mission?.state?.elapsed_runtime_seconds === "number") {
    return formatDurationCompact(mission.state.elapsed_runtime_seconds);
  }
  return "Awaiting timer";
}

function deriveRemainingLabel(mission) {
  const timeBudget = mission?.missionLoop?.timeBudget || {};
  if (typeof timeBudget.remainingSeconds === "number") {
    return formatDurationCompact(timeBudget.remainingSeconds);
  }
  if (typeof mission?.state?.remaining_runtime_seconds === "number") {
    return formatDurationCompact(mission.state.remaining_runtime_seconds);
  }
  return "Unknown";
}

function deriveChangedFiles(mission, workspace) {
  if (Array.isArray(mission?.changed_files) && mission.changed_files.length) {
    return mission.changed_files;
  }
  const actionTitles = (mission?.action_history || [])
    .filter(action => ["file_patch", "write", "edit", "test_run"].includes(action.proposal?.kind))
    .map(action => action.proposal?.title);
  if (actionTitles.length) {
    return actionTitles;
  }
  const git = workspace?.gitSnapshot || {};
  if (git.repoDetected) {
    return [
      `${git.stagedCount || 0} staged change(s)`,
      `${git.unstagedCount || 0} unstaged change(s)`,
      `${git.untrackedCount || 0} untracked file(s)`,
    ];
  }
  return ["No file evidence recorded yet."];
}

function deriveDiffSummary(workspace) {
  const git = workspace?.gitSnapshot || {};
  if (!git.repoDetected) {
    return "No Git diff is available for this workspace.";
  }
  return `${git.branch || "unknown branch"} · ${git.stagedCount || 0} staged · ${git.unstagedCount || 0} unstaged · ${git.untrackedCount || 0} untracked`;
}

function deriveCommandEvidence(mission) {
  const checks = [
    ...(mission?.proof?.passed_checks || []).map(check => `Passed: ${check}`),
    ...(mission?.proof?.failed_checks || []).map(check => `Failed: ${check}`),
  ];
  const actionResults = (mission?.action_history || []).map(
    action => action.result?.result_summary || action.result?.error || action.result?.stdout,
  );
  const delegatedEvents = (mission?.delegated_runtime_sessions || []).flatMap(
    session => (session.latest_events || []).map(event => event.message),
  );
  return uniq([...checks, ...actionResults, ...delegatedEvents]).slice(0, 6);
}

function deriveArtifacts(mission, inbox) {
  const explicitArtifacts = Array.isArray(mission?.proof_artifacts) ? mission.proof_artifacts : [];
  if (explicitArtifacts.length) {
    return explicitArtifacts;
  }
  const items = [
    mission?.proof?.summary,
    mission?.missionLoop?.continuityDetail,
    inbox?.previewMessage,
    mission?.delegated_runtime_sessions?.[0]?.detail,
  ];
  return uniq(items).slice(0, 4);
}

function deriveDecisionItems(mission, pendingQuestions) {
  const items = [];

  for (const approval of mission?.proof?.pending_approvals || []) {
    items.push({
      tone: "warn",
      type: "Approval",
      title: approval,
      reason: "The run is paused at a mutating or high-risk boundary.",
    });
  }

  for (const question of pendingQuestions || []) {
    items.push({
      tone: "warn",
      type: "Question",
      title: question.question || "Operator input required",
      reason: question.summary || "Fluxio does not have enough scope certainty to continue safely.",
    });
  }

  for (const failure of mission?.state?.verification_failures || []) {
    items.push({
      tone: "bad",
      type: "Failure",
      title: failure,
      reason: "Verification changed the path. Review this before approving more execution.",
    });
  }

  if (!items.length) {
    items.push({
      tone: "good",
      type: "Recommended",
      title: describeNextOperatorAction(mission, pendingQuestions),
      reason:
        mission?.proof?.summary ||
        mission?.missionLoop?.continuityDetail ||
        "The current run can continue inside the existing guardrails.",
    });
  }

  return items;
}

function timelineEntry(kind, title, detail, tone = "neutral", meta = "") {
  return { kind, title, detail, tone, meta };
}

function deriveTimelineEntries(mission, snapshot) {
  const entries = [];

  for (const event of (mission?.delegated_runtime_sessions || []).flatMap(
    session => session.latest_events || [],
  )) {
    entries.push(
      timelineEntry(
        event.kind || "runtime",
        event.message || "Delegated runtime update",
        mission?.delegated_runtime_sessions?.[0]?.detail || "",
        missionStatusTone(mission?.delegated_runtime_sessions?.[0]?.status),
        runtimeLabel(mission?.delegated_runtime_sessions?.[0]?.runtime_id),
      ),
    );
  }

  for (const action of mission?.action_history || []) {
    entries.push(
      timelineEntry(
        action.proposal?.kind || "action",
        action.proposal?.title || action.action_id,
        action.result?.result_summary || action.result?.error || action.result?.stdout || "",
        action.gate?.status === "pending"
          ? "warn"
          : action.result?.error
            ? "bad"
            : "neutral",
        action.proposal?.sourceKind || "",
      ),
    );
  }

  for (const revision of mission?.plan_revisions || []) {
    entries.push(
      timelineEntry(
        revision.trigger || "replan",
        revision.summary || revision.revision_id,
        (revision.steps || []).map(step => `${step.title} [${step.status}]`).join(" · "),
        "neutral",
        "Planner",
      ),
    );
  }

  for (const activity of snapshot?.activity || []) {
    entries.push(
      timelineEntry(
        activity.kind || "activity",
        activity.message,
        "",
        activity.kind === "approval.request" ? "warn" : "neutral",
        activity.timestamp || "",
      ),
    );
  }

  return entries.slice(0, 14);
}

export function buildRecentRuns(snapshot) {
  const harnessRuns = (snapshot?.harnessLab?.recentRuns || []).map(run => ({
    title: `${runtimeLabel(run.runtimeId)} · ${titleizeToken(run.autopilotStatus || "run")}`,
    subtitle: run.harnessId,
    tone: missionStatusTone(run.autopilotStatus),
  }));

  const missionRuns = (snapshot?.missions || [])
    .slice()
    .reverse()
    .slice(0, 3)
    .map(run => ({
      title: run.title || run.objective,
      subtitle: `${runtimeLabel(run.runtime_id)} · ${titleizeToken(run.state?.status || "run")}`,
      tone: missionStatusTone(run.state?.status),
    }));

  return [...missionRuns, ...harnessRuns].slice(0, 5);
}

function deriveConnectedAppSignals(snapshot) {
  return ((snapshot?.bridgeLab?.connectedSessions || []).slice(0, 3)).map(session => {
    const recentTask = session?.recent_tasks?.[0];
    const callbackDetail = session?.approval_callback?.detail;
    const contextPreview = session?.context_preview?.[0]?.summary;
    return {
      label: session?.app_name || "Connected app",
      value: titleizeToken(session?.status || session?.bridge_health || "connected"),
      note:
        recentTask?.resultSummary ||
        callbackDetail ||
        contextPreview ||
        "Ready to run a supervised bridge task and feed proof back into the mission thread.",
    };
  });
}

function derivePreviewSurface(previewMode, snapshot) {
  const uiReviewRecipe = (snapshot?.workflowStudio?.recipes || []).find(
    item =>
      item?.workflowId === "ui_review_loop" ||
      /live ui review/i.test(item?.label || ""),
  );
  return {
    label: "Live review surface",
    value: previewMode === "live" ? "Live backend" : titleizeToken(previewMode || "preview"),
    note:
      previewMode === "live"
        ? "Real desktop state, proof, and event replay stay attached to the active mission."
        : uiReviewRecipe?.description ||
          "Fixture-backed review keeps UI iteration fast without faking the supervision model.",
  };
}

function deriveSkillSignal(snapshot) {
  const userInstalled = snapshot?.skillLibrary?.userInstalledSkills || [];
  const learned = snapshot?.skillLibrary?.learnedSkills || [];
  const reviewedReusable = snapshot?.skillLibrary?.curatedPacks || [];
  const activeSkill =
    userInstalled[0]?.label || reviewedReusable[0]?.label || learned[0]?.label || "No reusable skill selected";
  return {
    label: "Skill library",
    value: `${userInstalled.length + reviewedReusable.length} reviewed · ${learned.length} learned`,
    note: `${activeSkill} keeps recurring work out of the prompt and inside a managed library.`,
  };
}

function deriveWorkflowSignal(snapshot) {
  const recipes = snapshot?.workflowStudio?.recipes || [];
  const primaryRecipe =
    recipes.find(item => item?.workflowId === "agent_long_run") ||
    recipes.find(item => item?.reviewStatus === "reviewed") ||
    recipes[0];
  return {
    label: "Workflow recipes",
    value: `${recipes.length} reviewed`,
    note:
      primaryRecipe?.description ||
      "Reviewed recipes capture runtime choice, skills, services, and verification defaults.",
  };
}

function looksLikeNetworkRoot(path) {
  const value = String(path || "").toLowerCase();
  return (
    value.startsWith("\\\\") ||
    value.startsWith("//") ||
    value.includes("synology") ||
    value.includes("/volume") ||
    value.includes("\\volume") ||
    value.includes("/nas/") ||
    value.includes("\\nas\\")
  );
}

function executionTargetLabel(target) {
  switch (target) {
    case "nas":
      return "NAS or network path";
    case "worktree":
      return "Local worktree";
    case "workspace":
      return "Local workspace";
    default:
      return "Unresolved";
  }
}

function activeExecutionSource(mission, workspace) {
  const delegated = (mission?.delegated_runtime_sessions || []).find(item =>
    ["launching", "running", "waiting_for_approval"].includes(item.status) &&
    (item?.execution_root || item?.workspace_root || item?.execution_target),
  );
  if (delegated) {
    return {
      execution_target: delegated.execution_target,
      execution_target_detail: delegated.execution_target_detail,
      execution_root: delegated.execution_root || workspace?.root_path || "",
      workspace_root: delegated.workspace_root || workspace?.root_path || delegated.execution_root || "",
      strategy: "delegated_runtime",
    };
  }
  const scope = mission?.execution_scope || mission?.state?.execution_scope || {};
  return {
    execution_target: scope.execution_target,
    execution_target_detail: scope.execution_target_detail,
    execution_root: scope.execution_root || workspace?.root_path || "",
    workspace_root: scope.workspace_root || workspace?.root_path || scope.execution_root || "",
    strategy: scope.strategy || "direct",
  };
}

function deriveExecutionLocation(mission, workspace) {
  const source = activeExecutionSource(mission, workspace);
  const executionRoot = source.execution_root || workspace?.root_path || "";
  const workspaceRoot = source.workspace_root || workspace?.root_path || executionRoot;
  const strategy = titleizeToken(source.strategy || "direct");

  if (source.execution_target && source.execution_target !== "unresolved") {
    return {
      label: "Execution location",
      value: executionTargetLabel(source.execution_target),
      note: source.execution_target_detail || `${strategy} execution is running at ${executionRoot}.`,
    };
  }

  if (!executionRoot) {
    return {
      label: "Execution location",
      value: "Unresolved",
      note: "Fluxio has not resolved where the active run is executing yet.",
    };
  }

  if (looksLikeNetworkRoot(executionRoot) || looksLikeNetworkRoot(workspaceRoot)) {
    return {
      label: "Execution location",
      value: "NAS or network path",
      note: `${strategy} execution is currently pointed at ${executionRoot}.`,
    };
  }

  if (executionRoot !== workspaceRoot) {
    return {
      label: "Execution location",
      value: "Local worktree",
      note: `${strategy} execution is isolated at ${executionRoot}.`,
    };
  }

  return {
    label: "Execution location",
    value: "Local workspace",
    note: `${strategy} execution is running directly in ${executionRoot}.`,
  };
}

function deriveRuntimeReason(mission) {
  const delegated =
    (mission?.delegated_runtime_sessions || []).find(item =>
      ["launching", "running", "waiting_for_approval"].includes(item.status),
    ) ||
    [...(mission?.delegated_runtime_sessions || [])].reverse().find(item => item?.status);
  if (delegated) {
    const executionLocation =
      delegated?.execution_target && delegated.execution_target !== "unresolved"
        ? ` on ${executionTargetLabel(delegated.execution_target).toLowerCase()}`
        : "";
    return `${runtimeLabel(delegated.runtime_id)} is active because the delegated lane is still in flight${executionLocation} and Fluxio is preserving continuity across the handoff.`;
  }

  const routingDecision = [...(mission?.routing_decisions || [])]
    .reverse()
    .find(item => item?.reason || item?.model);
  if (routingDecision) {
    return `${titleizeToken(routingDecision.role)} is routed to ${routingDecision.model}${
      routingDecision.reason ? ` because ${routingDecision.reason}` : "."
    }`;
  }

  const route = (mission?.route_configs || []).find(item => item?.explanation || item?.model);
  if (route) {
    return `${titleizeToken(route.role || "primary lane")} is using ${route.model}${
      route.explanation ? ` because ${route.explanation}` : "."
    }`;
  }

  return `Fluxio is staying on ${runtimeLabel(mission?.runtime_id)} because no runtime switch or delegated lane has been recorded.`;
}

function deriveHandoffHistory(mission) {
  const items = [];

  for (const decision of [...(mission?.routing_decisions || [])].reverse()) {
    if (!decision?.model) {
      continue;
    }
    items.push(
      `${titleizeToken(decision.role || "route")} routed to ${decision.model}${
        decision.reason ? ` because ${decision.reason}` : ""
      }`,
    );
  }

  for (const session of [...(mission?.delegated_runtime_sessions || [])].reverse()) {
    const latestEvent = session?.latest_events?.[session.latest_events.length - 1];
    const detail = latestEvent?.message || session?.last_event || session?.detail;
    const executionLocation =
      session?.execution_target && session.execution_target !== "unresolved"
        ? ` on ${executionTargetLabel(session.execution_target).toLowerCase()}`
        : "";
    if (!detail && !session?.status) {
      continue;
    }
    items.push(
      `${runtimeLabel(session.runtime_id)} lane ${titleizeToken(session.status || "recorded")}${executionLocation}${
        detail ? ` - ${detail}` : ""
      }`,
    );
  }

  return uniq(items).slice(0, 4);
}

function deriveProofReview(mission, pendingQuestions) {
  if ((mission?.state?.verification_failures || []).length > 0) {
    return {
      tone: "bad",
      headline: "Verification changed the path",
      note:
        mission.state.verification_failures[0] ||
        "Review the exact failure before approving more execution.",
    };
  }

  if ((mission?.proof?.pending_approvals || []).length > 0 || (pendingQuestions || []).length > 0) {
    return {
      tone: "warn",
      headline: "A review boundary is active",
      note: describeNextOperatorAction(mission, pendingQuestions),
    };
  }

  if (mission?.state?.status === "completed") {
    return {
      tone: "good",
      headline: "Proof is ready for sign-off",
      note:
        mission?.missionLoop?.lastVerificationSummary ||
        mission?.proof?.summary ||
        "Review the final proof bundle and close the mission.",
    };
  }

  if ((mission?.delegated_runtime_sessions || []).some(item => ["launching", "running", "waiting_for_approval"].includes(item.status))) {
    const delegated = (mission?.delegated_runtime_sessions || []).find(item =>
      ["launching", "running", "waiting_for_approval"].includes(item.status),
    );
    return {
      tone: "good",
      headline: "Runtime proof is still arriving",
      note:
        delegated?.last_event ||
        delegated?.detail ||
        mission?.proof?.summary ||
        "Fluxio is still collecting runtime evidence.",
    };
  }

  return {
    tone: "neutral",
    headline: "Proof is accumulating",
    note:
      mission?.proof?.summary ||
      "Fluxio is collecting changes, verification, and bridge evidence for the active run.",
  };
}

function deriveLiveSurfaceEvidence(snapshot, previewMode) {
  const items = [];

  const previewSurface = derivePreviewSurface(previewMode, snapshot);
  items.push(`${previewSurface.label}: ${previewSurface.value} - ${previewSurface.note}`);

  for (const session of snapshot?.bridgeLab?.connectedSessions || []) {
    const recentTask = session?.recent_tasks?.[0];
    const summary =
      recentTask?.resultSummary ||
      session?.approval_callback?.detail ||
      session?.context_preview?.[0]?.summary;
    items.push(
      `${session?.app_name || "Connected app"}: ${summary || "Connected and waiting for the next supervised task."}`,
    );
  }

  const recipe = (snapshot?.workflowStudio?.recipes || []).find(
    item => item?.workflowId === "ui_review_loop" || /live ui review/i.test(item?.label || ""),
  );
  if (recipe?.description) {
    items.push(`Workflow: ${recipe.label} - ${recipe.description}`);
  }

  return uniq(items).slice(0, 6);
}

function deriveOrchestrationStrip({
  mission,
  workspace,
  snapshot,
  pendingQuestions,
  runtimeLane,
  pauseReason,
  profileParams,
}) {
  if (!mission) {
    return {
      tone: "neutral",
      headline: "Supervise one real mission",
      detail:
        "Fluxio becomes valuable once a real run starts producing proof, approvals, and replayable runtime state.",
      chips: [],
    };
  }

  const delegated = mission?.delegated_runtime_sessions?.[0];
  const routes = mission?.route_configs || [];
  const alternateRuntime = (snapshot?.runtimes || []).find(
    item => item?.detected && item?.runtime_id !== mission.runtime_id,
  );
  const runUntil =
    mission?.missionLoop?.timeBudget?.runUntilBehavior ||
    mission?.run_budget?.run_until_behavior ||
    profileParams?.autoContinueBehavior ||
    "pause_on_failure";
  const continuityState =
    mission?.missionLoop?.continuityState || mission?.state?.continuity_state || "fresh_only";
  const verificationFailed = (mission?.state?.verification_failures || []).length > 0;
  const approvalsWaiting =
    (mission?.proof?.pending_approvals || []).length > 0 || (pendingQuestions || []).length > 0;
  const execution = deriveExecutionLocation(mission, workspace);
  const whyThisRuntime = deriveRuntimeReason(mission);
  const handoffs = deriveHandoffHistory(mission);
  const policy = `Approval ${titleizeToken(
    mission?.execution_policy?.approval_mode || profileParams?.approvalStrictness || "tiered",
  )} · Auto-continue ${titleizeToken(runUntil)}`;
  const continuityDetail =
    mission?.missionLoop?.continuityDetail || mission?.state?.continuity_detail || "";
  const continuity = continuityDetail
    ? `${titleizeToken(continuityState)}. ${continuityDetail}`
    : `${titleizeToken(continuityState)}.`;

  let tone = "neutral";
  let headline = `${runtimeLabel(mission.runtime_id)} is supervising the current run`;
  let detail =
    mission?.proof?.summary ||
    delegated?.detail ||
    describeNextOperatorAction(mission, pendingQuestions);

  if (verificationFailed) {
    tone = "bad";
    headline = "Verification changed the path";
    detail =
      mission?.state?.verification_failures?.[0] ||
      "Fluxio needs review before it continues execution.";
  } else if (approvalsWaiting) {
    tone = "warn";
    headline = "The run is paused at a review boundary";
    detail = pauseReason || delegated?.detail || "Resolve the open approval or question to continue.";
  } else if (mission?.state?.status === "completed") {
    tone = "good";
    headline = "The run completed with proof attached";
    detail =
      mission?.missionLoop?.lastVerificationSummary ||
      mission?.proof?.summary ||
      "Review the captured changes and verification output.";
  } else if (delegated) {
    tone = "good";
    headline = `${runtimeLabel(mission.runtime_id)} and ${runtimeLabel(delegated.runtime_id)} are handing work off cleanly`;
    detail =
      delegated?.detail ||
      "Fluxio can continue across delegated runtime activity without losing continuity.";
  } else if (mission?.state?.status === "running") {
    tone = "good";
    headline = `${runtimeLabel(mission.runtime_id)} is actively executing`;
    detail =
      mission?.missionLoop?.lastVerificationSummary ||
      mission?.proof?.summary ||
      "Fluxio is recording proof, timing, and checkpoints while the run moves.";
  }

  const chips = uniq([
    runtimeLane,
    `Auto-continue ${titleizeToken(runUntil)}`,
    `Continuity ${titleizeToken(continuityState)}`,
    routes.length
      ? routes.map(route => `${titleizeToken(route.role || "model")}: ${route.model}`).join(" · ")
      : "",
    alternateRuntime?.label ? `${alternateRuntime.label} ready` : "",
  ]).slice(0, 5);

  return {
    tone,
    headline,
    detail,
    chips,
    whyThisRuntime,
    policy,
    continuity,
    execution,
    handoffs,
  };
}

// This adapter converts raw backend/fixture payloads into operator-facing supervision surfaces.
// The layout consumes this model so the screen stays centered on decisions, proof, and safety.
export function buildMissionControlModel({
  mission,
  workspace,
  setupHealth,
  snapshot,
  pendingQuestions,
  pendingApprovals,
  telegramReady,
  profileId,
  profileParams,
  inbox,
  previewMode,
}) {
  const capabilitySignals = {
    preview: derivePreviewSurface(previewMode, snapshot),
    apps: deriveConnectedAppSignals(snapshot),
    skills: deriveSkillSignal(snapshot),
    workflows: deriveWorkflowSignal(snapshot),
  };

  if (!mission) {
    return {
      topBar: {
        environmentLabel: humanRuntimeEnvironment(setupHealth, workspace?.default_runtime),
        liveStatus: { label: "No active mission", tone: "neutral" },
        inboxCount: (pendingApprovals || []).length + (pendingQuestions || []).length + (inbox || []).length,
      },
      missionHeader: {
        title: "No active mission",
        objective:
          "Fluxio is ready to supervise one real workspace mission. Start with a bounded proving run, not a synthetic demo.",
        summary:
          setupHealth?.blockerExplanations?.[0] ||
          "Pick a workspace, define the objective, and launch one supervised run.",
        pills: [
          { label: titleizeToken(profileId), tone: "neutral" },
          { label: humanRuntimeEnvironment(setupHealth, workspace?.default_runtime), tone: "neutral" },
          { label: "Awaiting mission", tone: "neutral" },
        ],
        primaryAction: {
          label: "Start first mission",
          reason:
            "The main screen should become operational only after one real mission supplies proof, checkpoints, and decisions.",
        },
      },
      orchestration: deriveOrchestrationStrip({
        mission,
        workspace,
        snapshot,
        pendingQuestions,
        runtimeLane: "No runtime lane",
        pauseReason: "",
        profileParams,
      }),
      currentRun: {
        title: "Mission supervision starts here",
        summary:
          "Once a run exists, this surface will show the current task, checkpoint pressure, blockers, and live runtime state.",
        metrics: [
          { label: "Current task", value: "No active run" },
          { label: "Elapsed", value: "0m" },
          { label: "Blockers", value: String((setupHealth?.blockerExplanations || []).length) },
          { label: "Next checkpoint", value: "Create mission" },
        ],
        details: setupHealth?.nextActions || snapshot?.onboarding?.nextActions || [],
      },
      taskNavigator: deriveTaskNavigator(mission),
      proof: {
        review: {
          tone: "neutral",
          headline: "Proof appears after the first run",
          note: "The first real mission turns the thread into a proof surface instead of empty structure.",
        },
        verificationSummary: "Proof appears after the first run.",
        filesTouched: ["No file evidence yet."],
        diffSummary: workspace ? deriveDiffSummary(workspace) : "No workspace selected.",
        commandEvidence: ["No commands or logs yet."],
        liveSurfaces: deriveLiveSurfaceEvidence(snapshot, previewMode),
        artifacts: [
          "Mission proof will capture changed files, verification results, runtime output, and escalation events.",
        ],
      },
      decisionQueue: {
        urgent: false,
        items: [
          {
            tone: "neutral",
            type: "Next action",
            title: "Create a mission",
            reason: "Without a real run, Fluxio cannot show approvals, proof, or checkpoints.",
          },
        ],
        recommendation: {
          title: "Start with one bounded objective",
          reason:
            "A proving mission creates the supervision baseline for the rest of the workspace.",
        },
      },
      timeline: [
        timelineEntry(
          "setup",
          "Setup contract loaded",
          "Fluxio is waiting for the first supervised mission.",
          "neutral",
          "Control room",
        ),
      ],
      rail: {
        urgent: {
          title: "Nothing needs approval",
          tone: "good",
          items: [{ label: "Inbox", value: "0 waiting", note: "Approvals and operator questions will surface here." }],
        },
        guardrails: [
          { label: "Approval mode", value: titleizeToken(profileParams?.approvalStrictness || "tiered") },
          { label: "Run until", value: titleizeToken(profileParams?.autoContinueBehavior || "pause_on_failure") },
          { label: "Setup blockers", value: `${(setupHealth?.blockerExplanations || []).length}`, note: setupHealth?.blockerExplanations?.[0] || "None recorded" },
          { label: "Runtime health", value: `${(snapshot?.runtimes || []).filter(item => item.detected).length}/${(snapshot?.runtimes || []).length}` },
        ],
        context: [
          { label: "Workspace root", value: workspace?.root_path || snapshot?.workspaceRoot || "Not selected" },
          { label: "Context profile", value: titleizeToken(profileId) },
          { label: "Connected bridges", value: `${(snapshot?.bridgeLab?.connectedSessions || []).length}` },
          { label: "Escalation", value: telegramReady ? "Telegram ready" : "Not configured" },
        ],
      },
      capabilities: capabilitySignals,
    };
  }

  const currentTask = deriveCurrentTask(mission);
  const nextCheckpoint = deriveNextCheckpoint(mission);
  const blockerCount = deriveBlockerCount(mission, pendingQuestions);
  const runtimeLane = resolveCurrentRuntimeLane(mission);
  const pauseReason = resolveMissionPauseReason(mission);
  const primaryAction = derivePrimaryAction(mission, pendingQuestions);
  const decisionItems = deriveDecisionItems(mission, pendingQuestions);
  const firstInbox = inbox?.[0];
  const executionLocation = deriveExecutionLocation(mission, workspace);
  const proofReview = deriveProofReview(mission, pendingQuestions);
  const handoffs = deriveHandoffHistory(mission);
  const whyThisRuntime = deriveRuntimeReason(mission);

  return {
    topBar: {
      environmentLabel: humanRuntimeEnvironment(setupHealth, mission.runtime_id || workspace?.default_runtime),
      liveStatus: deriveTopBarLiveStatus(mission, pendingQuestions),
      inboxCount: (pendingApprovals || []).length + (pendingQuestions || []).length + (inbox || []).length,
    },
    missionHeader: {
      title: mission.title || mission.objective,
      objective: mission.objective,
      summary:
        mission.state?.last_plan_summary ||
        mission.proof?.summary ||
        describeMissionPhase(mission),
      pills: [
        { label: runtimeLabel(mission.runtime_id), tone: "neutral" },
        { label: titleizeToken(mission.selected_profile || profileId), tone: "neutral" },
        { label: titleizeToken(mission.state?.status || "active"), tone: missionStatusTone(mission.state?.status) },
      ],
      operatorSummary: {
        now: currentTask,
        reason: pauseReason || describeNextOperatorAction(mission, pendingQuestions),
      },
      primaryAction,
    },
    orchestration: deriveOrchestrationStrip({
      mission,
      workspace,
      snapshot,
      pendingQuestions,
      runtimeLane,
      pauseReason,
      profileParams,
    }),
    currentRun: {
      title: currentTask,
      summary:
        mission.proof?.summary ||
        mission.missionLoop?.lastVerificationSummary ||
        "Fluxio is supervising the current task and checkpoint.",
      metrics: [
        { label: "Elapsed", value: deriveElapsedLabel(mission) },
        { label: "Remaining", value: deriveRemainingLabel(mission) },
        { label: "Blockers", value: String(blockerCount) },
        { label: "Next checkpoint", value: nextCheckpoint },
      ],
      details: [
        { label: "Run state", value: titleizeToken(mission.state?.status || "active"), note: runtimeLane },
        {
          label: executionLocation.label || "Execution location",
          value: executionLocation.value,
          note: executionLocation.note,
        },
        {
          label: "Current phase",
          value: titleizeToken(mission.missionLoop?.currentCyclePhase || mission.state?.current_cycle_phase || "plan"),
          note: `Cycle ${mission.missionLoop?.cycleCount || mission.state?.cycle_count || 0}`,
        },
        {
          label: "Continuity",
          value: titleizeToken(mission.missionLoop?.continuityState || mission.state?.continuity_state || "fresh_only"),
          note:
            mission.missionLoop?.continuityDetail ||
            mission.state?.continuity_detail ||
            "No continuity detail recorded.",
        },
        {
          label: "Runtime handoff",
          value: handoffs.length > 0 ? `${handoffs.length} recorded` : "Single-runtime run",
          note: handoffs[0] || whyThisRuntime,
        },
        {
          label: "Safest next move",
          value: describeNextOperatorAction(mission, pendingQuestions),
          note: primaryAction.reason,
        },
      ],
    },
    taskNavigator: deriveTaskNavigator(mission),
    proof: {
      review: proofReview,
      verificationSummary:
        mission.missionLoop?.lastVerificationSummary ||
        mission.state?.last_verification_summary ||
        mission.proof?.summary ||
        "Verification status has not been recorded yet.",
      filesTouched: deriveChangedFiles(mission, workspace),
      diffSummary: deriveDiffSummary(workspace),
      commandEvidence: deriveCommandEvidence(mission),
      liveSurfaces: deriveLiveSurfaceEvidence(snapshot, previewMode),
      artifacts: deriveArtifacts(mission, firstInbox),
    },
    decisionQueue: {
      urgent: decisionItems.some(item => item.tone === "warn" || item.tone === "bad"),
      items: decisionItems,
      recommendation: {
        title: describeNextOperatorAction(mission, pendingQuestions),
        reason:
          pauseReason ||
          describeMissionNeedsInput(mission, pendingQuestions) ||
          describeMissionAssumption(mission, pendingQuestions),
      },
    },
    timeline: deriveTimelineEntries(mission, snapshot),
    rail: {
      urgent: {
        title:
          decisionItems[0]?.tone === "good"
            ? "Queue clear"
            : decisionItems[0]?.title || "Needs review",
        tone: decisionItems[0]?.tone || "neutral",
        items: decisionItems.slice(0, 3).map(item => ({
          label: item.type,
          value: item.title,
          note: item.reason,
        })),
      },
      guardrails: [
        {
          label: "Approval mode",
          value: titleizeToken(
            mission.execution_policy?.approval_mode || profileParams?.approvalStrictness || "tiered",
          ),
        },
        {
          label: "Run until",
          value: titleizeToken(
            mission.missionLoop?.timeBudget?.runUntilBehavior ||
              mission.run_budget?.run_until_behavior ||
              profileParams?.autoContinueBehavior ||
              "pause_on_failure",
          ),
          note: pauseReason || "No active pause",
        },
        {
          label: "Execution scope",
          value: executionLocation.value,
          note:
            executionLocation.note,
        },
        {
          label: "Runtime health",
          value: runtimeLane,
          note:
            (setupHealth?.dependencies || [])
              .filter(item => item.category === "agent_runtime" || item.serviceCategory === "runtime")
              .map(item => `${item.label}: ${titleizeToken(item.stage || item.currentHealthStatus || "unknown")}`)
              .join(" · ") || "Runtime health is not fully recorded yet.",
        },
      ],
      context: [
        {
          label: "Workspace root",
          value: workspace?.root_path || snapshot?.workspaceRoot || "Not selected",
        },
        {
          label: "Context in use",
          value: describeMissionKnownState(mission),
          note: describeMissionAssumption(mission, pendingQuestions),
        },
        {
          label: "Models in play",
          value:
            (mission.route_configs || [])
              .map(route => `${route.role}: ${route.model}`)
              .join(" · ") || "No routed models recorded",
        },
        {
          label: "Escalation",
          value: telegramReady ? "Telegram ready" : "Not configured",
          note:
            firstInbox?.previewMessage ||
            (snapshot?.bridgeLab?.connectedSessions || [])
              .slice(0, 1)
              .map(session => `${session.app_name} connected`)
              .join(" · ") ||
            "No escalation event recorded.",
        },
      ],
    },
    capabilities: capabilitySignals,
  };
}
