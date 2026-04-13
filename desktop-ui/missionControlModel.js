import {
  describeMissionAssumption,
  describeMissionKnownState,
  describeMissionNeedsInput,
  describeNextOperatorAction,
  formatDurationCompact,
  missionStatusTone,
  resolveCurrentRuntimeLane,
  resolveMissionPauseReason,
  runtimeLabel,
  titleizeToken,
} from "./fluxioHelpers.js";

function asList(value) {
  return Array.isArray(value) ? value : [];
}

function uniq(items) {
  return [...new Set(asList(items).filter(Boolean).map(item => String(item).trim()))];
}

function topBarLiveStatus(mission, pendingQuestions, pendingApprovals) {
  const approvalCount =
    asList(pendingApprovals).length + asList(mission?.proof?.pending_approvals).length;
  if (!mission) {
    return { label: "No active mission", tone: "neutral" };
  }
  if (approvalCount > 0) {
    return { label: "Needs approval", tone: "warn" };
  }
  if (asList(pendingQuestions).length > 0) {
    return { label: "Needs operator input", tone: "warn" };
  }
  if (asList(mission?.state?.verification_failures).length > 0) {
    return { label: "Verification failed", tone: "bad" };
  }
  if (mission?.state?.status === "completed") {
    return { label: "Completed", tone: "good" };
  }
  if (mission?.state?.status === "running") {
    return { label: "Active run", tone: "good" };
  }
  return {
    label: titleizeToken(mission?.state?.status || mission?.missionLoop?.continuityState || "active"),
    tone: missionStatusTone(mission?.state?.status),
  };
}

function deriveCurrentTask(mission) {
  const latestRevision = asList(mission?.plan_revisions).slice(-1)[0];
  const revisionStep = asList(latestRevision?.steps).find(step => step?.status === "in_progress");
  if (revisionStep?.title) {
    return revisionStep.title;
  }
  if (asList(mission?.state?.remaining_steps).length > 0) {
    return mission.state.remaining_steps[0];
  }
  if (asList(mission?.delegated_runtime_sessions).length > 0) {
    const delegated = mission.delegated_runtime_sessions[0];
    return delegated?.detail || delegated?.last_event || "Delegated runtime lane active";
  }
  return mission?.proof?.summary || "Waiting for the next mission checkpoint.";
}

function deriveNextCheckpoint(mission) {
  const latestRevision = asList(mission?.plan_revisions).slice(-1)[0];
  const nextRevisionStep = asList(latestRevision?.steps).find(step => step?.status === "pending");
  if (nextRevisionStep?.title) {
    return nextRevisionStep.title;
  }
  const remaining = asList(mission?.state?.remaining_steps);
  if (remaining.length > 1) {
    return remaining[1];
  }
  if (mission?.state?.status === "completed") {
    return "Finalize review and close mission";
  }
  return "Awaiting next checkpoint";
}

function deriveChanged(mission, workspace) {
  if (asList(mission?.changed_files).length > 0) {
    return mission.changed_files;
  }
  const actionTitles = asList(mission?.action_history)
    .map(action => action?.proposal?.title)
    .filter(Boolean);
  if (actionTitles.length > 0) {
    return actionTitles.slice(0, 5);
  }
  const git = workspace?.gitSnapshot || {};
  if (git.repoDetected) {
    return [
      `${git.stagedCount || 0} staged`,
      `${git.unstagedCount || 0} unstaged`,
      `${git.untrackedCount || 0} untracked`,
    ];
  }
  return ["No changed files captured yet."];
}

function deriveChecks(mission) {
  const checks = [
    ...asList(mission?.proof?.passed_checks).map(item => `Passed: ${item}`),
    ...asList(mission?.proof?.failed_checks).map(item => `Failed: ${item}`),
    ...asList(mission?.state?.verification_failures).map(item => `Failure: ${item}`),
  ];
  const actionResults = asList(mission?.action_history).map(
    action => action?.result?.result_summary || action?.result?.error || action?.result?.stdout,
  );
  return uniq([...checks, ...actionResults]).slice(0, 8);
}

function deriveArtifacts(mission, inbox) {
  const explicit = asList(mission?.proof_artifacts);
  if (explicit.length > 0) {
    return explicit.slice(0, 8);
  }
  return uniq([
    mission?.proof?.summary,
    mission?.missionLoop?.continuityDetail,
    inbox?.previewMessage,
    asList(mission?.delegated_runtime_sessions)[0]?.detail,
  ]).slice(0, 6);
}

function deriveVerificationSummary(mission) {
  return (
    mission?.missionLoop?.lastVerificationSummary ||
    mission?.state?.last_verification_summary ||
    mission?.proof?.summary ||
    "Verification detail has not been recorded yet."
  );
}

function deriveDiffSummary(workspace) {
  const git = workspace?.gitSnapshot || {};
  if (!git.repoDetected) {
    return "No Git diff detected for this workspace.";
  }
  return `${git.branch || "unknown"} · ${git.stagedCount || 0} staged · ${git.unstagedCount || 0} unstaged · ${git.untrackedCount || 0} untracked`;
}

function deriveQueueItems(mission, pendingQuestions, pendingApprovals) {
  const items = [];

  for (const approval of [
    ...asList(mission?.proof?.pending_approvals),
    ...asList(pendingApprovals).map(item => item?.reason || item?.toolId || item?.approval_id),
  ]) {
    if (!approval) {
      continue;
    }
    items.push({
      tone: "warn",
      type: "Approval",
      title: approval,
      reason: "Mission is paused at a review boundary.",
    });
  }

  for (const question of asList(pendingQuestions)) {
    items.push({
      tone: "warn",
      type: "Question",
      title: question?.question || "Operator input required",
      reason: question?.summary || "Fluxio needs a scope answer before it can continue safely.",
    });
  }

  for (const failure of asList(mission?.state?.verification_failures)) {
    items.push({
      tone: "bad",
      type: "Verification",
      title: failure,
      reason: "Review the failing check before approving additional execution.",
    });
  }

  if (items.length === 0) {
    items.push({
      tone: "good",
      type: "Recommended",
      title: describeNextOperatorAction(mission, pendingQuestions),
      reason:
        mission?.proof?.summary ||
        mission?.missionLoop?.continuityDetail ||
        "Run can continue inside the current guardrails.",
    });
  }

  return items.slice(0, 8);
}

function derivePrimaryAction(mission, queueItems) {
  const firstQueue = queueItems[0];
  if (!mission) {
    return {
      kind: "start",
      label: "Launch mission",
      reason: "Start one bounded mission to unlock proof, approvals, and a readable thread.",
    };
  }

  if (firstQueue?.tone === "warn" || firstQueue?.tone === "bad") {
    return {
      kind: "queue",
      label: "Review queue",
      reason: firstQueue?.title || "A boundary needs judgment before Fluxio can continue.",
    };
  }

  if (
    mission?.missionLoop?.continuityState === "resume_available" ||
    mission?.state?.status === "queued"
  ) {
    return {
      kind: "resume",
      label: "Resume mission",
      reason:
        mission?.missionLoop?.continuityDetail ||
        mission?.state?.continuity_detail ||
        "Resume from the last safe checkpoint.",
    };
  }

  if (mission?.state?.status === "completed") {
    return {
      kind: "proof",
      label: "Review proof",
      reason: deriveVerificationSummary(mission),
    };
  }

  return {
    kind: "proof",
    label: "Open proof",
    reason: deriveVerificationSummary(mission),
  };
}

function deriveThreadSections({ mission, pendingQuestions, workspace }) {
  if (!mission) {
    return [];
  }

  const currentTask = deriveCurrentTask(mission);
  const nextCheckpoint = deriveNextCheckpoint(mission);
  const pauseReason = resolveMissionPauseReason(mission);
  const knownState = describeMissionKnownState(mission);
  const assumptions = describeMissionAssumption(mission, pendingQuestions);
  const needsInput = describeMissionNeedsInput(mission, pendingQuestions);
  const changed = deriveChanged(mission, workspace).join(" · ");
  const verification = deriveVerificationSummary(mission);

  return [
    {
      id: "current-task",
      label: "Current task",
      body: currentTask,
      detail: `Next checkpoint: ${nextCheckpoint}`,
      tone: missionStatusTone(mission?.state?.status),
    },
    {
      id: "known-state",
      label: "What Fluxio knows",
      body: knownState,
      detail: resolveCurrentRuntimeLane(mission),
      tone: "neutral",
    },
    {
      id: "assumptions",
      label: "What Fluxio assumes",
      body: assumptions,
      detail: pauseReason ? `Pause boundary: ${pauseReason}` : "",
      tone: "neutral",
    },
    {
      id: "needs-input",
      label: "What Fluxio needs from operator",
      body: needsInput,
      detail: describeNextOperatorAction(mission, pendingQuestions),
      tone: "warn",
    },
    {
      id: "changed",
      label: "What changed",
      body: changed,
      detail: deriveDiffSummary(workspace),
      tone: "neutral",
    },
    {
      id: "proof",
      label: "What proof exists",
      body: verification,
      detail: mission?.proof?.summary || "Proof keeps accumulating while the mission runs.",
      tone: asList(mission?.state?.verification_failures).length > 0 ? "bad" : "good",
    },
  ];
}

function timelineEntry(kind, title, detail, tone = "neutral", meta = "") {
  return { kind, title, detail, tone, meta };
}

function deriveEvents(mission, snapshot) {
  const events = [];

  for (const session of asList(mission?.delegated_runtime_sessions)) {
    for (const event of asList(session?.latest_events)) {
      events.push(
        timelineEntry(
          event?.kind || "runtime",
          event?.message || "Runtime update",
          session?.detail || session?.last_event || "",
          missionStatusTone(session?.status),
          runtimeLabel(session?.runtime_id),
        ),
      );
    }
  }

  for (const action of asList(mission?.action_history)) {
    events.push(
      timelineEntry(
        action?.proposal?.kind || "action",
        action?.proposal?.title || action?.action_id || "Action",
        action?.result?.result_summary || action?.result?.error || action?.result?.stdout || "",
        action?.result?.error ? "bad" : action?.gate?.status === "pending" ? "warn" : "neutral",
        action?.executed_at || "",
      ),
    );
  }

  for (const activity of asList(snapshot?.activity)) {
    events.push(
      timelineEntry(
        activity?.kind || "activity",
        activity?.message || "Activity update",
        "",
        activity?.kind === "approval.request" ? "warn" : "neutral",
        activity?.timestamp || "",
      ),
    );
  }

  if (events.length === 0) {
    events.push(
      timelineEntry(
        "timeline",
        "Mission thread is waiting for the next event",
        "New actions, delegated lane events, and approvals will appear here.",
      ),
    );
  }

  return events.slice(0, 24);
}

function classifyFeatureTruth({ mission, snapshot, setupHealth, previewMode }) {
  const realReady = [];
  const realSecondary = [];
  const fixtureOnly = [];
  const notReady = [];

  if (mission) {
    realReady.push("Mission thread and action history");
  }
  if ((snapshot?.workspaces || []).length > 0) {
    realReady.push("Workspace registration and runtime selection");
  }
  if ((snapshot?.runtimes || []).some(item => item?.detected)) {
    realReady.push("Runtime detection and health telemetry");
  }
  if ((snapshot?.bridgeLab?.connectedSessions || []).length > 0) {
    realSecondary.push("Connected app bridge telemetry");
  }
  if ((snapshot?.workflowStudio?.recipes || []).length > 0) {
    realSecondary.push("Workflow recipe catalog");
  }
  if ((snapshot?.skillLibrary?.recommendedPacks || []).length > 0) {
    realSecondary.push("Skill recommendation signals");
  }

  if (previewMode !== "live") {
    fixtureOnly.push("Fixture-backed snapshot review");
  }
  fixtureOnly.push("Builder review controls");
  fixtureOnly.push("Live sync cadence controls");

  for (const blocker of asList(setupHealth?.blockerExplanations)) {
    notReady.push(blocker);
  }

  if (asList(snapshot?.workspaces).length === 0) {
    notReady.push("No workspace selected");
  }
  if (!mission) {
    notReady.push("No active mission");
  }

  return {
    realReady: uniq(realReady),
    realSecondary: uniq(realSecondary),
    fixtureOnly: uniq(fixtureOnly),
    notReady: uniq(notReady),
  };
}

function deriveStateAudit({ mission, setupHealth }) {
  const status = mission?.state?.status || "none";
  const approvalWait =
    asList(mission?.proof?.pending_approvals).length > 0 ||
    status === "needs_approval" ||
    status === "waiting_for_approval";
  const verificationFailure =
    asList(mission?.state?.verification_failures).length > 0 || status === "verification_failed";
  const firstRun = !mission;
  const blockedSetup = !setupHealth?.environmentReady;

  return [
    {
      id: "first-run",
      label: "First run",
      state: firstRun ? "active" : "resolved",
      nextAction: firstRun ? "Pick workspace and launch one bounded mission." : "Already passed.",
    },
    {
      id: "no-mission",
      label: "No mission",
      state: firstRun ? "active" : "resolved",
      nextAction: firstRun ? "Launch mission from the primary action button." : "Mission exists.",
    },
    {
      id: "blocked-setup",
      label: "Blocked setup",
      state: blockedSetup ? "active" : "resolved",
      nextAction: blockedSetup
        ? asList(setupHealth?.blockerExplanations)[0] || "Run setup repair actions."
        : "Setup health is ready.",
    },
    {
      id: "mission-launch",
      label: "Mission launch",
      state: mission ? "resolved" : "waiting",
      nextAction: mission ? "Mission launched." : "Pending first launch.",
    },
    {
      id: "approval-wait",
      label: "Approval wait",
      state: approvalWait ? "active" : "resolved",
      nextAction: approvalWait ? "Review queue and approve or reject." : "No approval boundary active.",
    },
    {
      id: "active-run",
      label: "Active run",
      state: status === "running" ? "active" : "resolved",
      nextAction:
        status === "running" ? "Monitor thread and proof deltas." : "Run is not currently active.",
    },
    {
      id: "verification-failure",
      label: "Verification failure",
      state: verificationFailure ? "active" : "resolved",
      nextAction: verificationFailure
        ? asList(mission?.state?.verification_failures)[0] || "Open proof drawer."
        : "No current failure.",
    },
    {
      id: "resumed-run",
      label: "Resumed run",
      state:
        mission?.missionLoop?.continuityState === "resume_available" || status === "queued"
          ? "active"
          : "resolved",
      nextAction:
        mission?.missionLoop?.continuityState === "resume_available" || status === "queued"
          ? "Use Resume mission."
          : "No resume boundary active.",
    },
    {
      id: "completed-run",
      label: "Completed run",
      state: status === "completed" ? "active" : "resolved",
      nextAction:
        status === "completed" ? "Review proof and close out." : "Mission has not completed yet.",
    },
  ];
}

function deriveEnvironmentLabel(setupHealth, mission, workspace) {
  const runtime =
    mission?.runtime_id ||
    workspace?.default_runtime ||
    asList(setupHealth?.dependencies).find(item => item?.category === "agent_runtime")?.dependencyId;
  if (!runtime) {
    return "Environment status";
  }
  return `${runtimeLabel(runtime)} lane`;
}

function deriveElapsed(mission) {
  const seconds =
    mission?.missionLoop?.timeBudget?.elapsedSeconds || mission?.state?.elapsed_runtime_seconds;
  if (typeof seconds === "number") {
    return formatDurationCompact(seconds);
  }
  return "0m";
}

function deriveRemaining(mission) {
  const seconds =
    mission?.missionLoop?.timeBudget?.remainingSeconds || mission?.state?.remaining_runtime_seconds;
  if (typeof seconds === "number") {
    return formatDurationCompact(seconds);
  }
  return "Unknown";
}

export function buildRecentRuns(snapshot) {
  const missionRuns = asList(snapshot?.missions)
    .slice()
    .reverse()
    .slice(0, 4)
    .map(item => ({
      title: item?.title || item?.objective || "Mission",
      subtitle: `${runtimeLabel(item?.runtime_id)} · ${titleizeToken(item?.state?.status || "run")}`,
      tone: missionStatusTone(item?.state?.status),
    }));

  const harnessRuns = asList(snapshot?.harnessLab?.recentRuns).map(item => ({
    title: `${runtimeLabel(item?.runtimeId)} · ${titleizeToken(item?.autopilotStatus || "run")}`,
    subtitle: item?.harnessId || "Harness",
    tone: missionStatusTone(item?.autopilotStatus),
  }));

  return [...missionRuns, ...harnessRuns].slice(0, 6);
}

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
  previewMode = "live",
  uiMode = "agent",
  lastPushReason = "",
  isRefreshing = false,
  liveSyncSeconds = "off",
  liveSyncSuspended = false,
}) {
  const queueItems = deriveQueueItems(mission, pendingQuestions, pendingApprovals);
  const primaryAction = derivePrimaryAction(mission, queueItems);
  const liveStatus = topBarLiveStatus(mission, pendingQuestions, pendingApprovals);
  const events = deriveEvents(mission, snapshot);
  const inboxPreview = asList(inbox)[0];
  const featureTruth = classifyFeatureTruth({ mission, snapshot, setupHealth, previewMode });
  const proofTone =
    asList(mission?.state?.verification_failures).length > 0
      ? "bad"
      : asList(mission?.proof?.pending_approvals).length > 0
        ? "warn"
        : mission?.state?.status === "completed"
          ? "good"
          : "neutral";

  const proofSections = [
    {
      title: "Files touched",
      items: deriveChanged(mission, workspace),
    },
    {
      title: "Checks and commands",
      items: deriveChecks(mission),
    },
    {
      title: "Artifacts",
      items: deriveArtifacts(mission, inboxPreview),
    },
  ];

  const contextGroups = [
    {
      title: "Guardrails",
      items: [
        {
          label: "Approval mode",
          value: titleizeToken(
            mission?.execution_policy?.approval_mode || profileParams?.approvalStrictness || "tiered",
          ),
        },
        {
          label: "Run until",
          value: titleizeToken(
            mission?.missionLoop?.timeBudget?.runUntilBehavior ||
              mission?.run_budget?.run_until_behavior ||
              profileParams?.autoContinueBehavior ||
              "pause_on_failure",
          ),
          note: resolveMissionPauseReason(mission) || "No active pause",
        },
        {
          label: "Setup blockers",
          value: `${asList(setupHealth?.blockerExplanations).length}`,
          note: asList(setupHealth?.blockerExplanations)[0] || "None",
        },
      ],
    },
    {
      title: "Runtime and scope",
      items: [
        {
          label: "Current lane",
          value: resolveCurrentRuntimeLane(mission),
        },
        {
          label: "Workspace root",
          value: workspace?.root_path || snapshot?.workspaceRoot || "Not selected",
        },
        {
          label: "Execution",
          value: mission?.execution_scope?.execution_root || "Not recorded",
          note: titleizeToken(mission?.execution_scope?.strategy || "direct"),
        },
      ],
    },
    {
      title: "Context",
      items: [
        {
          label: "Profile",
          value: titleizeToken(profileId),
        },
        {
          label: "Known state",
          value: describeMissionKnownState(mission),
        },
        {
          label: "Escalation",
          value: telegramReady ? "Telegram ready" : "Not configured",
          note: inboxPreview?.previewMessage || "",
        },
      ],
    },
  ];

  const threadSections = deriveThreadSections({ mission, pendingQuestions, workspace });

  const emptyReadiness = uniq([
    ...asList(setupHealth?.blockerExplanations),
    asList(snapshot?.workspaces).length === 0 ? "Add at least one workspace" : "",
    previewMode !== "live" ? "Preview mode is active; actions are read-only." : "",
  ]);

  return {
    topBar: {
      liveStatus,
      environmentLabel: deriveEnvironmentLabel(setupHealth, mission, workspace),
      inboxCount:
        queueItems.filter(item => item.tone === "warn" || item.tone === "bad").length +
        asList(inbox).length,
      primaryAction,
    },
    shell: {
      isEmpty: !mission,
      missionLabel: mission ? mission.title || mission.objective : "No mission",
    },
    emptyState: {
      title: "Ready for a focused first mission",
      summary:
        emptyReadiness[0] ||
        "Launch one real mission to replace scaffolding with a thread, proof, and review boundaries.",
      readiness: emptyReadiness.length > 0 ? emptyReadiness : ["Environment appears ready."],
      recommendedAction:
        asList(setupHealth?.globalActions)[0]?.label || "Launch mission",
      launchEntryLabel: asList(snapshot?.workspaces).length > 0 ? "Launch mission" : "Add workspace",
    },
    thread: {
      title: mission ? mission.title || mission.objective : "Mission thread",
      objective: mission?.objective || "",
      summary:
        mission?.state?.last_plan_summary ||
        mission?.proof?.summary ||
        "The mission thread captures task, assumptions, operator needs, and proof deltas.",
      status: liveStatus,
      chips: mission
        ? [
            { label: runtimeLabel(mission?.runtime_id), tone: "neutral" },
            { label: titleizeToken(mission?.state?.status || "active"), tone: missionStatusTone(mission?.state?.status) },
            { label: `Elapsed ${deriveElapsed(mission)}`, tone: "neutral" },
            { label: `Remaining ${deriveRemaining(mission)}`, tone: "neutral" },
          ]
        : [],
      sections: threadSections,
      events,
      proofItems: uniq([
        deriveVerificationSummary(mission),
        ...proofSections.flatMap(section => section.items),
      ]).slice(0, 8),
      composerPlaceholder:
        "Write an operator note, scope clarification, or approval rationale for this mission thread.",
    },
    drawers: {
      queue: {
        label: "Queue",
        urgent: queueItems.some(item => item.tone === "warn" || item.tone === "bad"),
        count: queueItems.filter(item => item.tone === "warn" || item.tone === "bad").length,
        items: queueItems,
        recommendation: {
          title: describeNextOperatorAction(mission, pendingQuestions),
          reason: queueItems[0]?.reason || "",
        },
      },
      proof: {
        label: "Proof",
        tone: proofTone,
        headline: deriveVerificationSummary(mission),
        diffSummary: deriveDiffSummary(workspace),
        sections: proofSections,
        itemsCount: proofSections.reduce((total, section) => total + section.items.length, 0),
      },
      context: {
        label: "Context",
        count: contextGroups.reduce((total, group) => total + group.items.length, 0),
        groups: contextGroups,
      },
      builder: {
        label: "Builder review",
        reviewCount:
          featureTruth.notReady.length +
          deriveStateAudit({ mission, setupHealth }).filter(item => item.state === "active").length,
        liveSurface: {
          previewMode,
          liveSyncSeconds,
          liveSyncSuspended,
          lastPushReason,
          isRefreshing,
          note:
            previewMode === "live"
              ? liveSyncSuspended
                ? "Live sync paused while the window is hidden."
                : `Live backend${lastPushReason ? ` · last push ${lastPushReason}` : ""}`
              : "Fixture-backed review mode is active.",
        },
        featureTruth,
        stateAudit: deriveStateAudit({ mission, setupHealth }),
        events: events.slice(0, 10),
        mode: uiMode,
      },
    },
  };
}
