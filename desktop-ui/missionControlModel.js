import {
  describeApprovalBehavior,
  describeExplanationBehavior,
  describeMissionAssumption,
  describeMissionKnownState,
  describeMissionNeedsInput,
  describeNextOperatorAction,
  describeProfileFit,
  previewLabel,
  describeVisibilityBehavior,
  formatDurationCompact,
  missionStatusTone,
  resolveCurrentRuntimeLane,
  resolveMissionPauseReason,
  runtimeLabel,
  titleizeToken,
  visibilityProfileState,
} from "./fluxioHelpers.js";

function asList(value) {
  return Array.isArray(value) ? value : [];
}

function uniq(items) {
  return [...new Set(asList(items).filter(Boolean).map(item => String(item).trim()))];
}

function asInt(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.round(parsed) : fallback;
}

function clampPercent(value) {
  return Math.max(0, Math.min(100, asInt(value)));
}

function listLabel(value) {
  if (!value) {
    return "Item";
  }
  return String(value);
}

function ratioPercent(part, total) {
  if (total <= 0) {
    return 0;
  }
  return clampPercent(Math.round((part / total) * 100));
}

function scoreTone(score) {
  if (score >= 85) {
    return "good";
  }
  if (score >= 65) {
    return "warn";
  }
  return "bad";
}

function flattenQuarantinedRoutes(value) {
  const rows = [];
  const source = value && typeof value === "object" ? value : {};
  for (const [taskType, taskRows] of Object.entries(source)) {
    if (!taskRows || typeof taskRows !== "object") {
      continue;
    }
    for (const [role, roleRows] of Object.entries(taskRows)) {
      for (const item of asList(roleRows)) {
        if (!item || typeof item !== "object") {
          continue;
        }
        rows.push({
          ...item,
          taskType: item.taskType || taskType,
          role: item.role || role,
          provider: item.provider || "",
          model: item.model || "",
          status: item.status || "quarantined_until_clean_value_sample",
          quarantineReason: item.quarantineReason || "Low-value or failing route outcome trend.",
          requiredAction:
            item.requiredAction ||
            "Run a clean value-scored route-trust sample before this lane can be selected automatically again.",
        });
      }
    }
  }
  return rows;
}

function serviceStatusTone(status) {
  if (["healthy", "connected", "ready", "passed"].includes(status)) {
    return "good";
  }
  if (
    [
      "missing",
      "blocked",
      "failed",
      "error",
      "degraded",
      "unavailable",
      "stale",
    ].includes(status)
  ) {
    return "bad";
  }
  return "warn";
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
      const kind = String(event?.kind || "runtime").toLowerCase();
      const eventDetail =
        kind === "runtime.phase_entered"
          ? `${titleizeToken(event?.data?.phase || "execute")} phase via ${titleizeToken(
              event?.data?.role || "route",
            )}${event?.data?.provider ? ` · ${titleizeToken(event.data.provider)}` : ""}${event?.data?.model ? ` · ${event.data.model}` : ""}`
          : kind === "runtime.route_switch_reason"
            ? event?.data?.reason || event?.message || session?.detail || ""
            : kind === "runtime.handoff"
              ? event?.data?.reason || event?.message || session?.detail || ""
              : session?.detail || session?.last_event || "";
      events.push(
        timelineEntry(
          event?.kind || "runtime",
          event?.message || "Runtime update",
          eventDetail,
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

function deriveConfidenceSurface({
  mission,
  snapshot,
  setupHealth,
  queueItems,
  pendingQuestions,
  pendingApprovals,
}) {
  const release = snapshot?.releaseReadiness || {};
  const requiredGateSummary = release?.requiredGateSummary || {};
  const requiredPassed = asInt(requiredGateSummary?.passed);
  const requiredTotal = asInt(requiredGateSummary?.total);
  const requiredScore = clampPercent(
    requiredGateSummary?.score ?? ratioPercent(requiredPassed, requiredTotal),
  );
  const qualityScore = clampPercent(release?.qualityScore ?? 0);
  const releaseScore = clampPercent(release?.score ?? 0);
  const verificationFailures = asList(mission?.state?.verification_failures).length;
  const questionCount = asList(pendingQuestions).length;
  const approvalCount =
    asList(mission?.proof?.pending_approvals).length + asList(pendingApprovals).length;
  const missingDependencyCount = asList(setupHealth?.missingDependencies).length;
  const urgentQueueCount = queueItems.filter(
    item => item?.tone === "warn" || item?.tone === "bad",
  ).length;
  const frictionPenalty = Math.min(
    36,
    urgentQueueCount * 4 +
      questionCount * 4 +
      approvalCount * 3 +
      verificationFailures * 6 +
      missingDependencyCount * 5,
  );

  const fallbackBase = requiredTotal > 0 ? requiredScore : qualityScore;
  const blendedBase = releaseScore > 0 ? releaseScore : fallbackBase;
  const confidenceScore = clampPercent(
    Math.round(blendedBase * 0.78 + requiredScore * 0.14 + qualityScore * 0.08) -
      frictionPenalty +
      (mission ? 4 : -4),
  );

  const setupSummary =
    setupHealth?.serviceManagementSummary || {
      totalItems: asList(setupHealth?.serviceManagement).length,
      healthyCount: asList(setupHealth?.serviceManagement).filter(
        item => serviceStatusTone(item?.currentHealthStatus) === "good",
      ).length,
    };
  const environmentPercent =
    asInt(setupSummary?.totalItems) > 0
      ? ratioPercent(asInt(setupSummary?.healthyCount), asInt(setupSummary?.totalItems))
      : setupHealth?.environmentReady
        ? 100
        : 40;

  const proofChecks = asList(release?.proofReadiness?.proofs);
  const proofPassed = proofChecks.filter(item => item?.passed).length;
  const proofPercent =
    proofChecks.length > 0
      ? ratioPercent(proofPassed, proofChecks.length)
      : mission
        ? 60
        : 0;

  const continuityPercent = !mission
    ? 0
    : mission?.state?.status === "completed"
      ? 100
      : mission?.state?.status === "running"
        ? 84
        : mission?.missionLoop?.continuityState === "resume_available"
          ? 78
          : mission?.state?.status === "queued"
            ? 62
            : 70;

  const operatorPercent = clampPercent(
    100 - Math.min(75, questionCount * 12 + approvalCount * 10 + verificationFailures * 15),
  );

  const phase =
    confidenceScore >= 85 && requiredPassed === requiredTotal && requiredTotal > 0
      ? "Validation ready"
      : confidenceScore >= 70
        ? "Close to validation"
        : "Hardening required";

  const nextActions = uniq([
    ...asList(release?.nextActions),
    ...queueItems
      .filter(item => item?.tone === "warn" || item?.tone === "bad")
      .map(item => item?.title || item?.reason),
    ...asList(setupHealth?.blockerExplanations),
  ]).slice(0, 6);

  const gates = asList(release?.gates).slice(0, 10).map(gate => ({
    gateId: gate?.gateId || gate?.label || "",
    label: gate?.label || "Gate",
    required: Boolean(gate?.required),
    passed: Boolean(gate?.passed),
    details: gate?.details || "",
    tone: gate?.passed ? "good" : gate?.required ? "bad" : "warn",
  }));

  return {
    score: confidenceScore,
    tone: scoreTone(confidenceScore),
    label: `${confidenceScore}% release confidence`,
    phase,
    releaseStatus: titleizeToken(release?.status || "building"),
    releaseScore,
    qualityScore,
    qualitySignals: {
      completionRate: asInt(release?.qualitySignals?.completionRate),
      delegatedRunRate: asInt(release?.qualitySignals?.delegatedRunRate),
      resumeRunRate: asInt(release?.qualitySignals?.resumeRunRate),
      resumeCompletionRate: asInt(release?.qualitySignals?.resumeCompletionRate),
      verificationPauseRate: asInt(release?.qualitySignals?.verificationPauseRate),
    },
    proofReady: Boolean(release?.proofReadiness?.ready),
    requiredGateSummary: {
      passed: requiredPassed,
      total: requiredTotal,
      score: requiredScore,
      label:
        requiredTotal > 0
          ? `${requiredPassed}/${requiredTotal} required gates passed`
          : "Required gates not reported yet",
    },
    calculatedAt: release?.calculatedAt || "",
    milestones: [
      {
        id: "environment",
        label: "Environment and services",
        percent: environmentPercent,
        detail:
          asInt(setupSummary?.totalItems) > 0
            ? `${asInt(setupSummary?.healthyCount)}/${asInt(setupSummary?.totalItems)} services healthy`
            : "Service health snapshot unavailable",
      },
      {
        id: "continuity",
        label: "Mission continuity",
        percent: continuityPercent,
        detail: mission
          ? titleizeToken(
              mission?.missionLoop?.continuityState || mission?.state?.status || "active",
            )
          : "No active mission yet",
      },
      {
        id: "proof",
        label: "Proof and verification",
        percent: proofPercent,
        detail:
          proofChecks.length > 0
            ? `${proofPassed}/${proofChecks.length} proving checks passed`
            : "Proof checks appear after first proving cycle",
      },
      {
        id: "operator",
        label: "Operator confidence",
        percent: operatorPercent,
        detail:
          questionCount + approvalCount + verificationFailures > 0
            ? `${questionCount} questions · ${approvalCount} approvals · ${verificationFailures} failures`
            : "No active friction in queue",
      },
    ],
    gates,
    nextActions,
  };
}

function deriveProfileStudio(snapshot, workspace, profileId, profileParams) {
  const profiles = snapshot?.profiles || {};
  const availableProfiles = asList(profiles?.availableProfiles);
  const details = profiles?.details || {};
  const activeDetail = details?.[profileId] || {};
  const activeAgent = activeDetail?.agent || {};
  const visibilityState = visibilityProfileState(profileParams);
  const profileRows = availableProfiles.slice(0, 10).map(name => {
    const item = details?.[name] || {};
    const params = item?.parameters || {};
    return {
      id: name,
      label: titleizeToken(name),
      description: item?.description || describeProfileFit(name),
      approval: titleizeToken(params?.approvalStrictness || "tiered"),
      autonomy: titleizeToken(params?.autonomyLevel || "balanced"),
      visibility: titleizeToken(params?.visibilityLevel || "balanced"),
      density: titleizeToken(params?.uiDensity || "comfortable"),
      tone: name === profileId ? "good" : "neutral",
    };
  });

  return {
    activeProfileId: profileId,
    activeProfileLabel: titleizeToken(profileId),
    availableProfiles,
    activeDescription: activeDetail?.description || describeProfileFit(profileId),
    behavior: [
      {
        label: "Approval boundary",
        value: describeApprovalBehavior(profileParams?.approvalStrictness || "tiered"),
      },
      {
        label: "Explanation style",
        value: describeExplanationBehavior(
          profileParams?.explanationLevel || activeAgent?.explanation_depth || "medium",
        ),
      },
      {
        label: "Visibility policy",
        value: describeVisibilityBehavior(profileParams?.visibilityLevel || "balanced"),
      },
      {
        label: "Profile fit",
        value: describeProfileFit(profileId),
      },
    ],
    visibilityState: {
      level: visibilityState?.level || "balanced",
      guided: Boolean(visibilityState?.guided),
      detailed: Boolean(visibilityState?.detailed),
      expert: Boolean(visibilityState?.expert),
    },
    workspacePolicy: [
      {
        label: "Current workspace profile",
        value: titleizeToken(workspace?.user_profile || profileId),
      },
      {
        label: "Preferred harness",
        value: titleizeToken(workspace?.preferred_harness || "fluxio_hybrid"),
      },
      {
        label: "Routing strategy",
        value: titleizeToken(workspace?.routing_strategy || "profile_default"),
      },
      {
        label: "Auto-optimize routing",
        value: workspace?.auto_optimize_routing ? "Enabled" : "Disabled",
      },
      {
        label: "Commit style",
        value: titleizeToken(workspace?.commit_message_style || "scoped"),
      },
      {
        label: "Execution target",
        value: titleizeToken(workspace?.execution_target_preference || "profile_default"),
      },
    ],
    profileRows,
  };
}

function deriveServiceStudio(workspace, setupHealth) {
  const workspaceServices = asList(workspace?.serviceManagement);
  const setupServices = asList(setupHealth?.serviceManagement);
  const services = workspaceServices.length > 0 ? workspaceServices : setupServices;
  const summary = workspace?.serviceManagementSummary || setupHealth?.serviceManagementSummary || {};

  const normalized = services
    .map(item => {
      const status =
        item?.currentHealthStatus || item?.lastVerificationResult || item?.status || "unknown";
      const tone = serviceStatusTone(status);
      const actions = [
        ...asList(item?.serviceActions),
        ...(item?.verifyAction?.actionId ? [item.verifyAction] : []),
      ]
        .filter(action => action?.actionId)
        .map(action => {
          const surface = action?.surface
            ? action.surface
            : action?.commandSurface?.startsWith("git.")
              ? "git"
            : action?.commandSurface?.startsWith("validate.")
              ? "validate"
              : action?.commandSurface?.startsWith("bridge.")
                ? "bridge"
                : "setup";
          return {
            actionId: action.actionId,
            label: action.label || action.actionId,
            commandSurface: action.commandSurface || "",
            detail: action.description || action.detail || action.followUp || "",
            requiresApproval: Boolean(action.requiresApproval),
            autoRunVerify: Boolean(action.autoRunVerify),
            followUp: action.followUp || "",
            surface,
          };
        });

      return {
        serviceId: item?.serviceId || item?.label || "service",
        label: item?.label || item?.serviceId || "Service",
        category: titleizeToken(item?.serviceCategory || "service"),
        status: titleizeToken(status),
        tone,
        managementMode: titleizeToken(item?.managementMode || "externally_managed"),
        required: Boolean(item?.required),
        details: [
          item?.details || "",
          item?.updateAvailable && item?.latestVersion
            ? `Latest ${item.latestVersion}`
            : "",
        ]
          .filter(Boolean)
          .join(" · "),
        version: item?.version || "",
        latestVersion: item?.latestVersion || "",
        updateAvailable: Boolean(item?.updateAvailable),
        actions,
      };
    })
    .sort((left, right) => {
      const rank = { bad: 0, warn: 1, good: 2, neutral: 3 };
      const leftRank = rank[left.tone] ?? 3;
      const rightRank = rank[right.tone] ?? 3;
      if (leftRank !== rightRank) {
        return leftRank - rightRank;
      }
      return left.label.localeCompare(right.label);
    });

  return {
    summary: {
      totalItems: asInt(summary?.totalItems, normalized.length),
      healthyCount: asInt(
        summary?.healthyCount,
        normalized.filter(item => item.tone === "good").length,
      ),
      needsAttentionCount: asInt(
        summary?.needsAttentionCount,
        normalized.filter(item => item.tone !== "good").length,
      ),
      runtimeCount: asInt(summary?.runtimeCount),
      toolServerCount: asInt(summary?.toolServerCount),
      bridgeCount: asInt(summary?.bridgeCount),
    },
    services: normalized.slice(0, 20),
    urgent: normalized.filter(item => item.tone === "bad" || item.tone === "warn").slice(0, 6),
    availableActionCount: normalized.reduce((total, item) => total + item.actions.length, 0),
  };
}

function skillPackTone(item) {
  if (item?.installed && item?.testStatus === "reviewed") {
    return "good";
  }
  if (item?.installed) {
    return "warn";
  }
  return item?.recommended ? "neutral" : "warn";
}

function deriveSkillStudio(snapshot, workspace) {
  const skillLibrary = snapshot?.skillLibrary || {};
  const routeTrustCoverage = snapshot?.harnessLab?.routeTrustCoverage || {};
  const routeOutcomeTrends = snapshot?.harnessLab?.routeOutcomeTrends || {};
  const quarantinedRoutes = flattenQuarantinedRoutes(
    routeTrustCoverage?.quarantinedRoutes || routeOutcomeTrends?.quarantinedRoutes,
  );
  const auditRedTeam = snapshot?.systemAuditDigest?.redTeamEscalation || {};
  const snapshotRedTeam = snapshot?.redTeamEscalation || {};
  const redTeam =
    asList(snapshotRedTeam?.history).length > 0 ||
    asInt(snapshotRedTeam?.summary?.runCount) > 0 ||
    asInt(snapshotRedTeam?.historyRows) > 0
      ? snapshotRedTeam
      : auditRedTeam;
  const redTeamSummary = redTeam?.summary || {};
  const redTeamTrend = redTeam?.trend || {};
  const redTeamNextBenchmarkPlan = redTeam?.nextBenchmarkPlan || {};
  const redTeamHistory = asList(redTeam?.history).slice(-6).map((item, index) => ({
    id: `${item?.preset || "red-team"}-${item?.recordedAt || index}`,
    preset: item?.preset || "red-team",
    recordedAt: item?.recordedAt || "",
    status: titleizeToken(item?.status || "unknown"),
    resistanceScore: asInt(item?.resistance_score),
    difficultyLevel: asInt(item?.difficultyLevel),
    nextDifficultyLevel: asInt(item?.nextDifficultyLevel),
    currentPressureIndex: asInt(item?.currentPressureIndex),
    nextPressureIndex: asInt(item?.nextPressureIndex),
    pressureDelta: asInt(item?.pressureDelta),
    nextDifficultyLabel: item?.nextDifficultyLabel || "",
    nextAttemptBudget: asInt(item?.nextAttemptBudget),
    passStreak: asInt(item?.passStreak),
    cleanPass: Boolean(item?.cleanPass),
    shouldEscalate: Boolean(item?.shouldEscalate),
    nextTactics: asList(item?.nextTactics).slice(0, 4),
    tone: item?.shouldEscalate ? "good" : asInt(item?.resistance_score) >= 70 ? "warn" : "bad",
  }));
  const summary = skillLibrary?.managementSummary || {};
  const curatedPacks = asList(skillLibrary?.curatedPacks);
  const recommendedPacks = asList(skillLibrary?.recommendedPacks);
  const workspaceRecommendations = asList(workspace?.recommendedSkillPacks);
  const recommended = (
    workspaceRecommendations.length > 0 ? workspaceRecommendations : recommendedPacks
  )
    .slice(0, 8)
    .map(item => ({
      id: item?.packId || item?.pack_id || item?.label,
      label: item?.label || item?.packId || "Pack",
      description: item?.description || "",
      audience: titleizeToken(item?.audience || "all"),
      status: titleizeToken(item?.testStatus || item?.promotionState || "recommended"),
      tone: skillPackTone(item),
      installed: Boolean(item?.installed),
      executionCapable: Boolean(item?.execution_capable),
      guidanceOnly: Boolean(item?.guidance_only),
      permissions: asList(item?.permissions),
      profileSuitability: asList(item?.profile_suitability).map(entry => titleizeToken(entry)),
      originType: titleizeToken(item?.originType || item?.source?.kind || "recommended"),
      testStatus: titleizeToken(item?.testStatus || "recommended"),
      feedbackSummary: item?.feedbackSummary || {},
    }));

  const curated = curatedPacks.slice(0, 10).map(item => ({
    id: item?.packId || item?.pack_id || item?.label,
    label: item?.label || item?.packId || "Pack",
    status: titleizeToken(item?.testStatus || item?.promotionState || "active"),
    usageCount: asInt(item?.usageCount),
    helpedCount: asInt(item?.helpedCount),
    tone: skillPackTone(item),
    installed: Boolean(item?.installed),
    executionCapable: Boolean(item?.execution_capable),
    guidanceOnly: Boolean(item?.guidance_only),
    permissions: asList(item?.permissions),
    profileSuitability: asList(item?.profile_suitability).map(entry => titleizeToken(entry)),
    originType: titleizeToken(item?.originType || item?.source?.kind || "curated"),
    testStatus: titleizeToken(item?.testStatus || "active"),
    feedbackSummary: item?.feedbackSummary || {},
  }));

  const allPacks = uniq([...recommended.map(item => item.id), ...curated.map(item => item.id)]);
  const needsAttention = curated.filter(
    item =>
      item.status !== "Reviewed" ||
      !item.installed ||
      item.testStatus !== "Reviewed",
  );
  const executionReadyCount = curated.filter(
    item => item.installed && item.executionCapable && item.testStatus === "Reviewed",
  ).length;
  const coverageByProfile = {
    Beginner: curated.filter(item => item.profileSuitability.includes("Beginner")).length,
    Builder: curated.filter(item => item.profileSuitability.includes("Builder")).length,
    Advanced: curated.filter(item => item.profileSuitability.includes("Advanced")).length,
  };
  const nextQualityActions = uniq([
    asInt(summary?.needsTestCount) > 0
      ? `Review and test ${asInt(summary?.needsTestCount)} skill pack(s) with missing verification status.`
      : "",
    recommended.some(item => !item.installed)
      ? "Install or promote recommended packs before claiming full workflow coverage."
      : "",
    executionReadyCount < Math.max(1, Math.ceil(curated.length * 0.6))
      ? "Increase execution-capable reviewed packs to support broader operator workflows."
      : "",
    asInt(summary?.repairCount) > 0
      ? `Repair or hold ${asInt(summary?.repairCount)} skill pack(s) with high system-loss feedback before reuse.`
      : "",
    asInt(summary?.learnedCount) === 0
      ? "Capture at least one learned skill event from a real mission cycle."
      : "",
  ]).slice(0, 4);

  return {
    summary: {
      totalSkills: asInt(summary?.totalSkills, curatedPacks.length),
      reviewedReusableCount: asInt(summary?.reviewedReusableCount),
      needsTestCount: asInt(summary?.needsTestCount),
      learnedCount: asInt(summary?.learnedCount),
      disabledCount: asInt(summary?.disabledCount),
      feedbackSliceCount: asInt(summary?.feedbackSliceCount),
      repairCount: asInt(summary?.repairCount),
      installedCount: curatedPacks.filter(item => item?.installed).length,
      executionReadyCount,
      uniquePackCount: allPacks.length,
    },
    recommended,
    curated,
    needsAttention: needsAttention.slice(0, 8),
    coverageByProfile,
    nextQualityActions,
    feedbackLoop: skillLibrary?.feedbackLoop || { cadence: "mission_slice_end" },
    routeTrustCoverage: {
      schema: routeTrustCoverage?.schema || "fluxio.route_trust_coverage.v1",
      provenTaskCount: asInt(routeTrustCoverage?.provenTaskCount),
      samplingTaskCount: asInt(routeTrustCoverage?.samplingTaskCount),
      activeSamplingMissionCount: asInt(routeTrustCoverage?.activeSamplingMissionCount),
      lowValueCloseoutCount: asInt(routeTrustCoverage?.lowValueCloseoutCount),
      quarantinedRouteCount: asInt(routeTrustCoverage?.quarantinedRouteCount, quarantinedRoutes.length),
      quarantinedRoutes: quarantinedRoutes.slice(0, 8),
      routeOutcomeTrendSchema: routeTrustCoverage?.routeOutcomeTrendSchema || routeOutcomeTrends?.schema || "",
      operatorConfidenceScore: asInt(routeTrustCoverage?.operatorConfidenceScore),
      repairPlanStatus: routeTrustCoverage?.repairPlanStatus || "clear",
      nextRepairStep: routeTrustCoverage?.nextRepairStep || "",
      requiredOperatorValueSamples: asInt(routeTrustCoverage?.requiredOperatorValueSamples, 2),
      nextAction:
        routeTrustCoverage?.nextAction ||
        "Run value-scored missions per task category so route and skill trust can become reliable.",
      nextSamplingPlan: asList(routeTrustCoverage?.nextSamplingPlan).slice(0, 6),
      taskCoverage: asList(routeTrustCoverage?.taskCoverage).slice(0, 8),
      repairPlan: asList(routeTrustCoverage?.repairPlan).slice(0, 5),
    },
    redTeamEscalation: {
      schema: redTeam?.schema || "fluxio.red_team_escalation_snapshot.v1",
      runCount: asInt(redTeamSummary?.runCount || redTeam?.historyRows, redTeamHistory.length),
      status: titleizeToken(redTeamSummary?.status || redTeamTrend?.status || "empty"),
      latestPreset: redTeamSummary?.latestPreset || redTeamHistory[redTeamHistory.length - 1]?.preset || "",
      latestResistanceScore: asInt(redTeamSummary?.latestResistanceScore || redTeam?.latestResistanceScore),
      latestDifficultyLevel: asInt(redTeamSummary?.latestDifficultyLevel || redTeam?.latestDifficultyLevel),
      nextDifficultyLevel: asInt(redTeamSummary?.nextDifficultyLevel || redTeam?.nextDifficultyLevel),
      currentPressureIndex: asInt(redTeamSummary?.currentPressureIndex || redTeam?.currentPressureIndex),
      nextPressureIndex: asInt(redTeamSummary?.nextPressureIndex || redTeam?.nextPressureIndex),
      pressureDelta: asInt(redTeamSummary?.pressureDelta || redTeam?.pressureDelta),
      nextDifficultyLabel: redTeamSummary?.nextDifficultyLabel || redTeam?.nextDifficultyLabel || "",
      nextAttemptBudget: asInt(redTeamSummary?.nextAttemptBudget || redTeam?.nextAttemptBudget),
      passStreak: asInt(redTeamSummary?.passStreak || redTeam?.passStreak),
      cleanPass: Boolean(redTeamSummary?.cleanPass),
      shouldEscalate: Boolean(redTeamSummary?.shouldEscalate),
      resistanceTrend: asInt(redTeamSummary?.resistanceTrend || redTeamTrend?.resistanceTrend),
      difficultyTrend: asInt(redTeamSummary?.difficultyTrend || redTeamTrend?.difficultyTrend),
      pressureTrend: asInt(redTeamSummary?.pressureTrend || redTeamTrend?.pressureTrend),
      nextAction:
        redTeamSummary?.nextAction ||
        redTeamTrend?.nextAction ||
        "Run the first red-team benchmark and record its escalation row.",
      nextBenchmarkPlan: {
        schema: redTeamNextBenchmarkPlan?.schema || "fluxio.red_team_next_benchmark_plan.v1",
        status: redTeamNextBenchmarkPlan?.status || "",
        preset: redTeamNextBenchmarkPlan?.preset || redTeamSummary?.latestPreset || "",
        attemptBudget: asInt(redTeamNextBenchmarkPlan?.attemptBudget || redTeamSummary?.nextAttemptBudget),
        targetResistanceScore: asInt(redTeamNextBenchmarkPlan?.targetResistanceScore),
        targetDifficultyLevel: asInt(redTeamNextBenchmarkPlan?.targetDifficultyLevel || redTeamSummary?.nextDifficultyLevel),
        difficultyLabel:
          redTeamNextBenchmarkPlan?.difficultyLabel ||
          redTeamSummary?.nextDifficultyLabel ||
          (redTeamSummary?.nextDifficultyLevel ? `L${redTeamSummary.nextDifficultyLevel}` : ""),
        levelCapReached: Boolean(redTeamNextBenchmarkPlan?.levelCapReached),
        currentPressureIndex: asInt(
          redTeamNextBenchmarkPlan?.currentPressureIndex || redTeamSummary?.currentPressureIndex,
        ),
        nextPressureIndex: asInt(redTeamNextBenchmarkPlan?.nextPressureIndex || redTeamSummary?.nextPressureIndex),
        pressureDelta: asInt(redTeamNextBenchmarkPlan?.pressureDelta || redTeamSummary?.pressureDelta),
        tactics: asList(redTeamNextBenchmarkPlan?.tactics).slice(0, 6),
        operatorReviewRequired: Boolean(redTeamNextBenchmarkPlan?.operatorReviewRequired),
        aggregateOnly: redTeamNextBenchmarkPlan?.aggregateOnly !== false,
        rawPayloadExport: Boolean(redTeamNextBenchmarkPlan?.rawPayloadExport),
        successCriteria: asList(redTeamNextBenchmarkPlan?.successCriteria).slice(0, 4),
        commandShell: redTeamNextBenchmarkPlan?.command?.shell || "",
        nextAction: redTeamNextBenchmarkPlan?.nextAction || redTeamSummary?.nextAction || "",
      },
      history: redTeamHistory,
    },
    capabilitiesNote:
      "Skill CRUD is not exposed as a dedicated control-room command yet, so this studio is review-first.",
  };
}

function workflowTone(status) {
  if (status === "ready") {
    return "good";
  }
  if (status === "blocked") {
    return "bad";
  }
  return "warn";
}

function deriveWorkflowStudio(snapshot, profileId) {
  const studio = snapshot?.workflowStudio || {};
  const recipes = asList(studio?.recipes).map(item => ({
    workflowId: item?.workflowId || item?.label || "",
    label: item?.label || "Workflow",
    description: item?.description || "",
    status: titleizeToken(item?.status || "available"),
    audience: titleizeToken(item?.audience || "all"),
    surface: titleizeToken(item?.surface || "builder_view"),
    reviewStatus: titleizeToken(item?.reviewStatus || "reviewed"),
    runtimeChoice: runtimeLabel(item?.runtimeChoice),
    skillIds: asList(item?.skillIds),
    serviceIds: asList(item?.serviceIds),
    verificationDefaults: asList(item?.verificationDefaults),
    tone: workflowTone(item?.status),
  }));
  const recommended =
    recipes.find(
      item =>
        item.tone !== "bad" &&
        ["All", titleizeToken(profileId), "Builder", "Beginner", "Advanced"].includes(
          item.audience,
        ),
    ) || recipes[0] || null;

  return {
    summary: {
      recipeCount: asInt(studio?.managementSummary?.recipeCount, recipes.length),
      reviewedCount: asInt(studio?.managementSummary?.reviewedCount),
      blockedCount: asInt(studio?.managementSummary?.blockedCount),
      recommendedMode: titleizeToken(studio?.recommendedMode || "agent"),
    },
    recipes: recipes.slice(0, 10),
    recommended,
    learningQueue: asList(studio?.learningQueue).slice(0, 6),
  };
}

function deriveBuilderOps(workspace) {
  return {
    gitActions: asList(workspace?.gitActions).map(item => ({
      actionId: item?.actionId || "",
      label: item?.label || item?.actionId || "Git action",
      detail: item?.detail || item?.command || "",
      requiresApproval: Boolean(item?.requiresApproval),
      surface: "git",
      tone: item?.requiresApproval ? "warn" : "neutral",
    })),
    validationActions: asList(workspace?.validationActions).map(item => ({
      actionId: item?.actionId || "",
      label: item?.label || item?.actionId || "Validation action",
      detail: item?.detail || item?.command || "",
      requiresApproval: Boolean(item?.requiresApproval),
      surface: "validate",
      tone: item?.requiresApproval ? "warn" : "good",
    })),
  };
}

function parseWorkspaceSyncStatus(workspace) {
  const entry = asList(workspace?.goals).find(item => String(item || "").startsWith("sync_status:"));
  if (!entry) {
    return {};
  }
  try {
    const payload = JSON.parse(String(entry).slice("sync_status:".length));
    return payload && typeof payload === "object" ? payload : {};
  } catch {
    return {};
  }
}

function parseWorkspaceSyncConflictResolutions(workspace) {
  return asList(workspace?.goals)
    .map(item => String(item || "").trim())
    .filter(item => item.startsWith("sync_conflict_resolution:"))
    .map(item => {
      try {
        const payload = JSON.parse(item.slice("sync_conflict_resolution:".length));
        return payload && typeof payload === "object" ? payload : null;
      } catch {
        return null;
      }
    })
    .filter(Boolean)
    .slice(-8);
}

function parseWorkspaceSyncConflictBatchResolutions(workspace) {
  return asList(workspace?.goals)
    .map(item => String(item || "").trim())
    .filter(item => item.startsWith("sync_conflict_batch_resolution:"))
    .map(item => {
      try {
        const payload = JSON.parse(item.slice("sync_conflict_batch_resolution:".length));
        return payload && typeof payload === "object" ? payload : null;
      } catch {
        return null;
      }
    })
    .filter(Boolean)
    .slice(-5);
}

function deriveMissionContextRoots(mission, workspace, snapshot) {
  const payload = mission?.contextRoots || mission?.context_roots || {};
  const payloadRoots = asList(payload?.roots);
  const workspaces = asList(snapshot?.workspaces);
  const workspaceById = new Map(workspaces.map(item => [item?.workspace_id, item]));
  const missionWorkspace = workspaceById.get(mission?.workspace_id) || workspace || {};
  const baseRoots =
    payloadRoots.length > 0
      ? payloadRoots
      : [
          {
            role: "primary",
            relationship: "mission_workspace",
            rootPath: missionWorkspace?.root_path || "",
            workspaceId: missionWorkspace?.workspace_id || mission?.workspace_id || "",
            workspaceName: missionWorkspace?.name || "Workspace",
            currentMission: true,
            writableByMission: true,
            detail: "Primary mission workspace.",
          },
        ];
  const normalized = baseRoots
    .filter(item => item?.rootPath || item?.root_path)
    .slice(0, 10)
    .map((item, index) => {
      const owner = workspaceById.get(item?.workspaceId || item?.workspace_id) || missionWorkspace;
      const role = item?.role || (index === 0 ? "primary" : "related_workspace");
      const rootPath = item?.rootPath || item?.root_path || owner?.root_path || "";
      const blockedCount = asInt(item?.blockedMissionCount || item?.blocked_count);
      const activeCount = asInt(item?.activeMissionCount || item?.active_count);
      return {
        rootId: item?.rootId || `${item?.workspaceId || owner?.workspace_id || "root"}-${role}-${index}`,
        workspaceId: item?.workspaceId || item?.workspace_id || owner?.workspace_id || "",
        workspaceName: item?.workspaceName || item?.workspace_name || owner?.name || "Workspace",
        role,
        relationship: item?.relationship || "mission_workspace",
        rootPath,
        folderLabel: item?.folderLabel || pathLeafLabel(rootPath),
        runtime: runtimeLabel(item?.runtime || owner?.default_runtime),
        profile: titleizeToken(item?.profile || owner?.user_profile || "builder"),
        harness: titleizeToken(item?.harness || owner?.preferred_harness || "fluxio_hybrid"),
        syncMode: titleizeToken(item?.syncMode || owner?.sync_mode || "manual"),
        syncDirection: titleizeToken(item?.syncDirection || owner?.sync_direction || "bidirectional"),
        autoSyncToNas: Boolean(item?.autoSyncToNas || owner?.auto_sync_to_nas),
        missionCount: asInt(item?.missionCount),
        activeMissionCount: activeCount,
        blockedMissionCount: blockedCount,
        completedMissionCount: asInt(item?.completedMissionCount),
        currentMission: Boolean(item?.currentMission || index === 0),
        writableByMission: item?.writableByMission !== false,
        detail: item?.detail || "",
        tone: blockedCount > 0 ? "warn" : activeCount > 0 || item?.currentMission ? "good" : "neutral",
      };
    });
  const related = normalized.filter(item => item.role === "related_workspace");
  const dependencyEdges = asList(payload?.dependencyEdges || payload?.dependency_edges).map((item, index) => ({
    edgeId: item?.edgeId || item?.edge_id || `edge-${index}`,
    fromRootId: item?.fromRootId || item?.from_root_id || "",
    toRootId: item?.toRootId || item?.to_root_id || "",
    type: item?.type || "dependency",
    direction: item?.direction || "read_only",
    writePolicy: item?.writePolicy || item?.write_policy || "read_only_until_selected",
    summary: item?.summary || "",
  }));
  const writeScopePreflight = payload?.writeScopePreflight || payload?.write_scope_preflight || {};
  return {
    schema: payload?.schema || "fluxio.mission.context_roots.v1",
    missionId: payload?.missionId || mission?.mission_id || "",
    mode: payload?.mode || (normalized.length > 1 ? "multi_root" : "single_root"),
    primary: payload?.primary || normalized[0] || {},
    roots: normalized,
    related,
    dependencyEdges,
    writeScopePreflight: {
      schema: writeScopePreflight?.schema || "fluxio.write_scope_preflight.v1",
      status: writeScopePreflight?.status || "unknown",
      writePolicy: writeScopePreflight?.writePolicy || writeScopePreflight?.write_policy || "read_only",
      allowedRootIds: asList(writeScopePreflight?.allowedRootIds || writeScopePreflight?.allowed_root_ids),
      readOnlyRootIds: asList(writeScopePreflight?.readOnlyRootIds || writeScopePreflight?.read_only_root_ids),
      dependencyEdgeCount: asInt(writeScopePreflight?.dependencyEdgeCount, dependencyEdges.length),
      warnings: asList(writeScopePreflight?.warnings),
      nextAction:
        writeScopePreflight?.nextAction ||
        writeScopePreflight?.next_action ||
        "Review write scope before cross-project edits.",
    },
    counts: {
      totalRoots: asInt(payload?.counts?.totalRoots, normalized.length),
      relatedWorkspaces: asInt(payload?.counts?.relatedWorkspaces, related.length),
      writableRoots: asInt(
        payload?.counts?.writableRoots,
        normalized.filter(item => item.writableByMission).length,
      ),
      syncPairs: asInt(
        payload?.counts?.syncPairs,
        normalized.filter(item => item.relationship === "workspace_sync_pair").length,
      ),
      dependencyEdges: asInt(payload?.counts?.dependencyEdges, dependencyEdges.length),
      preflightWarnings: asInt(
        payload?.counts?.preflightWarnings,
        asList(writeScopePreflight?.warnings).length,
      ),
    },
    execution: payload?.execution || {},
    policy: payload?.policy || {
      writeScope: "primary_and_declared_mirrors",
      relatedWorkspaceWritePolicy: "read_only_until_selected",
      beginnerSafety: "Show every root before cross-project edits.",
    },
    recommendedAction:
      payload?.recommendedAction ||
      (related.length > 0
        ? "Review related roots before planning cross-project edits."
        : "Add related workspaces when this mission depends on another project."),
  };
}

function roadmapState(done, blocked = false) {
  if (done) {
    return "done";
  }
  return blocked ? "blocked" : "next";
}

function roadmapTone(state) {
  if (state === "done") {
    return "good";
  }
  if (state === "blocked") {
    return "bad";
  }
  return "warn";
}

function deriveQualityRoadmap({
  confidence,
  mission,
  setupHealth,
  serviceStudio,
  skillStudio,
  workflowStudio,
  builderOps,
}) {
  const requiredDone =
    confidence?.requiredGateSummary?.total > 0 &&
    confidence?.requiredGateSummary?.passed >= confidence?.requiredGateSummary?.total;
  const completionRate = asInt(confidence?.qualitySignals?.completionRate);
  const delegatedRate = asInt(confidence?.qualitySignals?.delegatedRunRate);
  const resumeCompletionRate = asInt(confidence?.qualitySignals?.resumeCompletionRate);
  const verificationPauseRate = asInt(confidence?.qualitySignals?.verificationPauseRate);
  const serviceHealthy =
    asInt(serviceStudio?.summary?.needsAttentionCount) === 0 &&
    asInt(setupHealth?.missingDependencies?.length) === 0;
  const skillQualityReady = asInt(skillStudio?.summary?.needsTestCount) === 0;
  const workflowReady = asInt(workflowStudio?.summary?.blockedCount) === 0;
  const proofReady = Boolean(confidence?.proofReady);
  const hasMission = Boolean(mission);
  const hasValidationAction = asList(builderOps?.validationActions).length > 0;

  const tracks = [
    {
      id: "required-gates",
      label: "Required gates stay green",
      state: roadmapState(requiredDone),
      detail: confidence?.requiredGateSummary?.label || "Required gate summary unavailable.",
      hint: requiredDone
        ? "All required gates are currently passing."
        : "Resolve failed required gates before quality tuning.",
      suggestedAction: hasValidationAction ? "Run validation action" : "",
      actionKind: hasValidationAction ? "validate" : "",
    },
    {
      id: "completion-rate",
      label: "Lift completion rate above 50%",
      state: roadmapState(completionRate >= 50, !hasMission),
      detail: `Current completion rate: ${completionRate}%`,
      hint: hasMission
        ? "Run bounded missions end-to-end and close them with proof."
        : "Launch a mission first to generate quality data.",
      suggestedAction: hasMission ? "Launch one bounded run" : "Start first mission",
      actionKind: "mission",
    },
    {
      id: "delegated-usage",
      label: "Lift delegated run rate above 20%",
      state: roadmapState(delegatedRate >= 20, !hasMission),
      detail: `Current delegated run rate: ${delegatedRate}%`,
      hint: "Use runtime lanes that exercise delegated execution with approval boundaries.",
      suggestedAction: "Launch delegated mission",
      actionKind: "mission",
    },
    {
      id: "resume-reliability",
      label: "Lift resumed-run completion above 60%",
      state: roadmapState(resumeCompletionRate >= 60, !hasMission),
      detail: `Current resumed completion rate: ${resumeCompletionRate}%`,
      hint: "Pause/resume real runs and ensure they still close with proof.",
      suggestedAction: "Run resume scenario",
      actionKind: "mission",
    },
    {
      id: "verification-friction",
      label: "Keep verification pauses below 25%",
      state: roadmapState(verificationPauseRate < 25),
      detail: `Current verification pause rate: ${verificationPauseRate}%`,
      hint: "Use validation actions continuously and tighten proof expectations.",
      suggestedAction: hasValidationAction ? "Run validation action" : "Review verification defaults",
      actionKind: hasValidationAction ? "validate" : "",
    },
    {
      id: "skill-quality",
      label: "Skill studio quality bar",
      state: roadmapState(skillQualityReady),
      detail: `${asInt(skillStudio?.summary?.needsTestCount)} pack(s) still need test/review coverage.`,
      hint: skillQualityReady
        ? "Skill packs are currently reviewed."
        : "Focus on packs marked as not reviewed or not installed.",
      suggestedAction:
        asList(skillStudio?.nextQualityActions)[0] || "Review skill studio inventory",
      actionKind: "skill",
    },
    {
      id: "service-health",
      label: "Service health stays stable",
      state: roadmapState(serviceHealthy),
      detail: `${asInt(serviceStudio?.summary?.needsAttentionCount)} service(s) need attention.`,
      hint: serviceHealthy
        ? "All tracked services are currently healthy."
        : "Repair service blockers before long unattended runs.",
      suggestedAction: "Run service repair action",
      actionKind: "service",
    },
    {
      id: "workflow-readiness",
      label: "Workflow recipes stay ready",
      state: roadmapState(workflowReady && proofReady),
      detail: `${asInt(workflowStudio?.summary?.blockedCount)} workflow(s) blocked · proof cycle ${proofReady ? "ready" : "not ready"}.`,
      hint: "Use one recommended workflow end-to-end and capture proof.",
      suggestedAction: "Execute recommended workflow",
      actionKind: "workflow",
    },
  ].map(item => ({
    ...item,
    tone: roadmapTone(item.state),
  }));

  const doneCount = tracks.filter(item => item.state === "done").length;
  const nextCount = tracks.filter(item => item.state === "next").length;
  const blockedCount = tracks.filter(item => item.state === "blocked").length;

  return {
    targetScore: 100,
    currentScore: confidence?.score || 0,
    gap: Math.max(0, 100 - (confidence?.score || 0)),
    doneCount,
    nextCount,
    blockedCount,
    tracks,
    headline:
      nextCount === 0 && blockedCount === 0
        ? "Quality roadmap is complete."
        : `${nextCount + blockedCount} quality step(s) remain for 100%.`,
  };
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
  if ((snapshot?.workspaces || []).some(item => asList(item?.serviceManagement).length > 0)) {
    realReady.push("Service management summary and health detail");
  }
  if ((snapshot?.skillLibrary?.curatedPacks || []).length > 0) {
    realReady.push("Skill catalog with reviewed pack metadata");
  }
  if ((snapshot?.workflowStudio?.recipes || []).length > 0) {
    realReady.push("Workflow recipe studio");
  }
  if (snapshot?.releaseReadiness?.score !== undefined) {
    realReady.push("Release-readiness scoring and gate evidence");
  }
  if ((snapshot?.runtimes || []).some(item => item?.detected)) {
    realReady.push("Runtime detection and health telemetry");
  }
  if ((snapshot?.bridgeLab?.connectedSessions || []).length > 0) {
    realSecondary.push("Connected app bridge telemetry");
  }
  if ((snapshot?.skillLibrary?.recommendedPacks || []).length > 0) {
    realSecondary.push("Skill recommendation signals");
  }
  if (snapshot?.profiles?.availableProfiles?.length > 0) {
    realSecondary.push("Profile parameter matrix and behavior defaults");
  }

  if (previewMode !== "live") {
    fixtureOnly.push("Fixture-backed snapshot review");
    fixtureOnly.push("Builder review controls");
    fixtureOnly.push("Live sync cadence controls");
  } else {
    realSecondary.push("Builder review controls");
    realSecondary.push("Live sync cadence controls");
  }

  for (const blocker of asList(setupHealth?.blockerExplanations)) {
    notReady.push(blocker);
  }
  for (const gate of asList(snapshot?.releaseReadiness?.gates)) {
    if (gate?.required && !gate?.passed) {
      notReady.push(`${gate.label}: ${gate.details}`);
    }
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

function timeValue(value) {
  if (!value) {
    return Number.NaN;
  }
  const parsed = Date.parse(String(value));
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

function latestTimestamp(...values) {
  let best = "";
  let bestValue = Number.NEGATIVE_INFINITY;
  for (const value of values.flat()) {
    const score = timeValue(value);
    if (Number.isFinite(score) && score >= bestValue) {
      best = String(value);
      bestValue = score;
    }
  }
  return best;
}

function isTerminalMissionStatus(status) {
  return ["completed", "failed", "cancelled", "stopped"].includes(
    String(status || "").toLowerCase(),
  );
}

function latestMeaningfulDelegatedEvent(mission) {
  for (const session of asList(mission?.delegated_runtime_sessions).slice().reverse()) {
    const event = asList(session?.latest_events)
      .slice()
      .reverse()
      .find(item => item?.message && item?.kind !== "session.heartbeat");
    if (event) {
      return event;
    }
  }
  return null;
}

function deriveMissionLatestTimestamp(mission) {
  return latestTimestamp(
    mission?.updated_at,
    mission?.state?.updated_at,
    mission?.missionLoop?.updatedAt,
    asList(mission?.action_history).map(item => item?.executed_at),
    asList(mission?.plan_revisions).map(item => item?.created_at),
    asList(mission?.delegated_runtime_sessions).map(item => item?.updated_at),
  );
}

function deriveMissionLastMovement(mission) {
  const latestAction = asList(mission?.action_history).slice(-1)[0];
  if (latestAction?.result?.result_summary || latestAction?.proposal?.title) {
    return (
      latestAction?.result?.result_summary ||
      latestAction?.result?.error ||
      latestAction?.proposal?.title
    );
  }
  const delegatedEvent = latestMeaningfulDelegatedEvent(mission);
  if (delegatedEvent?.message) {
    return delegatedEvent.message;
  }
  return (
    mission?.state?.last_plan_summary ||
    mission?.missionLoop?.continuityDetail ||
    mission?.proof?.summary ||
    "Waiting for the next mission movement."
  );
}

function deriveMissionExecutionPath(mission, workspace) {
  const delegated = asList(mission?.delegated_runtime_sessions).find(
    item => item?.execution_root || item?.workspace_root,
  );
  return (
    delegated?.execution_root ||
    delegated?.workspace_root ||
    mission?.execution_scope?.execution_root ||
    mission?.state?.execution_scope?.execution_root ||
    workspace?.root_path ||
    ""
  );
}

function pathLeafLabel(value) {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }
  const parts = text.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] || text;
}

function missionNeedsAttention(mission) {
  return Boolean(
    asList(mission?.proof?.pending_approvals).length > 0 ||
      asList(mission?.state?.verification_failures).length > 0 ||
      ["needs_approval", "blocked", "verification_failed", "queued"].includes(
        mission?.state?.status || "",
      ),
  );
}

function activityTone(activity) {
  const kind = String(activity?.kind || "").toLowerCase();
  const action = String(activity?.metadata?.action || "").toLowerCase();
  const message = `${kind} ${activity?.message || ""}`;
  if (/failed|error|verification_failed/.test(message)) {
    return "bad";
  }
  if (kind === "approval.request" || kind === "mission.queued" || /approval|blocked|queued/.test(message)) {
    return "warn";
  }
  if (action === "complete" || /completed|healthy|ready/.test(message)) {
    return "good";
  }
  return "neutral";
}

function deriveActivityDetail(activity, missionById) {
  const metadata = activity?.metadata || {};
  const missionTitle =
    missionById.get(activity?.mission_id)?.title ||
    missionById.get(activity?.mission_id)?.objective ||
    "";
  const blockingMissionTitle =
    missionById.get(metadata.blockingMissionId)?.title ||
    missionById.get(metadata.blockingMissionId)?.objective ||
    metadata.blockingMissionId ||
    "";
  return uniq([
    missionTitle,
    metadata.runtimeId ? runtimeLabel(metadata.runtimeId) : metadata.runtime_id ? runtimeLabel(metadata.runtime_id) : "",
    metadata.provider ? `${titleizeToken(metadata.provider)}${metadata.model ? `:${metadata.model}` : ""}` : "",
    metadata.queuePosition ? `Queue ${metadata.queuePosition}` : "",
    metadata.action ? `Action ${titleizeToken(metadata.action)}` : "",
    metadata.autopilotStatus ? titleizeToken(metadata.autopilotStatus) : "",
    metadata.pauseReason ? `Pause ${titleizeToken(metadata.pauseReason)}` : "",
    metadata.blockerClass ? `Blocker ${titleizeToken(metadata.blockerClass)}` : "",
    blockingMissionTitle ? `Blocked by ${blockingMissionTitle}` : "",
  ]).join(" · ");
}

function deriveMissionNexus(mission, workspace) {
  const pendingApproval = asList(mission?.proof?.pending_approvals)[0];
  const verificationFailure = asList(mission?.state?.verification_failures)[0];
  const latestPlan = asList(mission?.plan_revisions).slice(-1)[0];
  const delegatedEvent = latestMeaningfulDelegatedEvent(mission);
  const status = mission?.state?.status || mission?.missionLoop?.continuityState || "active";
  const executionPath = deriveMissionExecutionPath(mission, workspace);

  let label = "";
  let reason = "";
  let tone = "neutral";

  if (verificationFailure) {
    label = "Verification nexus";
    reason = verificationFailure;
    tone = "bad";
  } else if (pendingApproval) {
    label = "Approval nexus";
    reason = pendingApproval;
    tone = "warn";
  } else if (["needs_approval", "blocked", "queued"].includes(status)) {
    label = "Operator nexus";
    reason =
      mission?.state?.last_plan_summary ||
      mission?.missionLoop?.continuityDetail ||
      deriveMissionLastMovement(mission);
    tone = "warn";
  } else if (latestPlan?.summary) {
    label = "Plan nexus";
    reason = latestPlan.summary;
    tone = "neutral";
  } else if (delegatedEvent?.message) {
    label = "Runtime nexus";
    reason = delegatedEvent.message;
    tone = missionStatusTone(status);
  } else {
    return null;
  }

  return {
    id: `nexus-${mission?.mission_id || mission?.title || reason}`,
    missionId: mission?.mission_id || "",
    title: mission?.title || mission?.objective || "Mission",
    label,
    reason,
    detail: deriveCurrentTask(mission),
    next: deriveNextCheckpoint(mission),
    tone,
    timestamp: deriveMissionLatestTimestamp(mission),
    workspaceName: workspace?.name || "Workspace",
    executionPath,
    folderLabel: pathLeafLabel(executionPath) || pathLeafLabel(workspace?.root_path || ""),
  };
}

function routeRowsForMission(mission, workspace) {
  const contract = mission?.effectiveRouteContract || mission?.effective_route_contract || {};
  const contractRows = asList(contract?.roles || mission?.effectiveRouteContract || mission?.route_configs);
  const routeReceipts = asList(contract?.mutationReceipts || contract?.mutation_receipts);
  const workspaceRows = asList(workspace?.route_overrides);
  const roles = ["planner", "executor", "verifier"];
  return roles.map(role => {
    const row =
      contractRows.find(item => String(item?.role || "").toLowerCase() === role) ||
      workspaceRows.find(item => String(item?.role || "").toLowerCase() === role) ||
      {};
      return {
        role,
        provider: row?.provider || "",
        model: row?.model || "",
        effort: row?.effort || row?.reasoningEffort || "",
        source: row?.source || (row?.provider ? "workspace" : "profile_default"),
        fallbackPolicy: row?.fallbackPolicy || row?.fallback_policy || "same_provider",
        taskType: row?.taskType || row?.task_type || "general_coding",
        routeIntent: row?.routeIntent || row?.route_intent || "",
        fitScore: asInt(row?.fitScore || row?.fit_score),
        outcomeSampleCount: asInt(row?.outcomeSampleCount || row?.outcome_sample_count),
        outcomeSuccessRate: asInt(row?.outcomeSuccessRate || row?.outcome_success_rate),
        outcomeTrend: row?.outcomeTrend || row?.outcome_trend || "",
        reason: row?.reason || row?.explanation || "",
        routeReceipt:
          routeReceipts
            .slice()
            .reverse()
            .find(receipt => String(receipt?.role || "").toLowerCase() === role) || {},
    };
  });
}

function deriveSubAgentLanes(missions, workspaceById, fallbackWorkspace, productionHarness) {
  const recent = missions
    .slice()
    .sort((left, right) => timeValue(deriveMissionLatestTimestamp(right)) - timeValue(deriveMissionLatestTimestamp(left)))
    .slice(0, 4);
  const rows = [];
  for (const mission of recent) {
    const ownerWorkspace = workspaceById.get(mission?.workspace_id) || fallbackWorkspace || {};
    const sessions = asList(mission?.delegated_runtime_sessions);
    const activeSessionCount = sessions.filter(
      session => !["completed", "failed", "stopped"].includes(String(session?.status || "").toLowerCase()),
    ).length;
    const status = String(mission?.state?.status || mission?.missionLoop?.continuityState || "idle").toLowerCase();
    const missionBlocked = missionNeedsAttention(mission);
    for (const route of routeRowsForMission(mission, ownerWorkspace)) {
      const roleSession = sessions.find(session =>
        [session?.target_role, session?.role, session?.source_step_id, session?.delegated_id]
          .filter(Boolean)
          .some(value => String(value).toLowerCase().includes(route.role)),
      );
      const sessionStatus = String(roleSession?.status || "").toLowerCase();
      const active =
        Boolean(roleSession && !["completed", "failed", "stopped"].includes(sessionStatus)) ||
        (route.role === "executor" && activeSessionCount > 0);
      const tone =
        sessionStatus === "failed" || status === "failed"
          ? "bad"
          : missionBlocked
            ? "warn"
            : active || status === "running"
              ? "good"
              : "neutral";
      const failedChecks = asList(mission?.proof?.failed_checks || mission?.failedChecks);
      const pendingApprovals = asList(mission?.proof?.pending_approvals || mission?.pendingApprovals);
      const laneProof = {
        summary:
          roleSession?.last_event ||
          roleSession?.detail ||
          mission?.proof?.summary ||
          deriveVerificationSummary(mission),
        sessionId: roleSession?.delegated_id || roleSession?.session_id || "",
        heartbeatStatus: roleSession?.heartbeat_status || "",
        heartbeatAgeSeconds: Number(roleSession?.heartbeat_age_seconds || 0),
        passedChecks: Number(mission?.proof?.passed_checks?.length || mission?.passedChecks || 0),
        failedChecks: failedChecks.length,
        pendingApprovals: pendingApprovals.length,
        changedFiles: asList(roleSession?.changed_files || mission?.changed_files).length,
        routeReceipt: route.routeReceipt || {},
      };
      const laneControls = [
        {
          id: "inspect-events",
          label: "Inspect",
          action: "runtime",
          enabled: true,
          detail: "Open the runtime timeline and recent lane events.",
        },
        {
          id: "proof-drilldown",
          label: "Proof",
          action: "proof",
          enabled: true,
          detail: "Open proof digest, checks, approvals, and artifacts for this lane.",
        },
        {
          id: active ? "pause-lane" : "resume-lane",
          label: active ? "Pause" : "Resume",
          action: active ? "pause" : "resume",
          enabled: Boolean(mission?.mission_id),
          detail: active ? "Stop the supervised mission lane safely." : "Resume this mission from the latest checkpoint.",
        },
        {
          id: "reroute-lane",
          label: "Reroute",
          action: "reroute",
          enabled: true,
          detail: "Open runtime routing context before changing provider/model choices.",
        },
      ];
      rows.push({
        id: `${mission?.mission_id || "mission"}-${route.role}`,
        missionId: mission?.mission_id || "",
        missionTitle: mission?.title || mission?.objective || "Mission",
        workspaceName: ownerWorkspace?.name || "Workspace",
        role: titleizeToken(route.role),
        provider: route.provider ? titleizeToken(route.provider) : "Profile default",
        model: route.model || "Profile default",
        effort: route.effort ? titleizeToken(route.effort) : "Default",
        runtime: runtimeLabel(mission?.runtime_id || ownerWorkspace?.default_runtime),
        harness: titleizeToken(mission?.harness_id || ownerWorkspace?.preferred_harness || productionHarness),
        statusLabel: active
          ? "running"
          : missionBlocked
            ? "needs attention"
            : status === "completed"
              ? "complete"
              : "ready",
        fallbackPolicy: route.fallbackPolicy,
        source: route.source,
        taskType: route.taskType,
        routeIntent: route.routeIntent,
        fitScore: route.fitScore,
        outcomeSampleCount: route.outcomeSampleCount,
        outcomeSuccessRate: route.outcomeSuccessRate,
        outcomeTrend: route.outcomeTrend,
        routeReason: route.reason,
        detail: roleSession?.detail || deriveNextCheckpoint(mission),
        laneProof,
        controls: laneControls,
        tone,
      });
    }
  }
  return rows.slice(0, 12);
}

function deriveProjectProgressHistory(snapshot) {
  const raw = snapshot?.projectProgressHistory || {};
  const projects = asList(raw.projects);
  const byWorkspace = new Map(projects.map(item => [item?.workspaceId, item]));
  return {
    schema: raw.schema || "",
    source: raw.source || "",
    eventLimit: asInt(raw.eventLimit),
    projects,
    byWorkspace,
    schedulingQueue: asList(raw.schedulingQueue),
    scheduler: raw.scheduler || {},
    liveData: raw.schema === "fluxio.project_progress_history.v1",
  };
}

function deriveWorkspaceHealth(workspaces, missions, activeConversations, workspaceById, projectProgressHistory) {
  return workspaces.map(workspace => {
    const rows = missions.filter(item => item?.workspace_id === workspace?.workspace_id);
    const progress = projectProgressHistory?.byWorkspace?.get(workspace?.workspace_id) || null;
    const artifactRows = rows.map(deriveMissionArtifactReadiness);
    const readyArtifacts = artifactRows.filter(item => item.status === "ready").length;
    const missingArtifacts = artifactRows.filter(item => ["missing", "partial"].includes(item.status)).length;
    const latest = rows
      .slice()
      .sort((left, right) => timeValue(deriveMissionLatestTimestamp(right)) - timeValue(deriveMissionLatestTimestamp(left)))[0];
    const active = activeConversations.filter(item => item.workspaceId === workspace?.workspace_id);
    const blocked = rows.filter(item => missionNeedsAttention(item)).length;
    const completed = rows.filter(item => isTerminalMissionStatus(item?.state?.status) && item?.state?.status === "completed").length;
    const delegated = rows.reduce((total, item) => total + asList(item?.delegated_runtime_sessions).length, 0);
    const nextAction =
      active[0]?.next ||
      deriveNextCheckpoint(latest) ||
      "Launch a mission from this project.";
    const syncStatus = parseWorkspaceSyncStatus(workspace);
    const conflictSamples = asList(syncStatus?.conflictSamples || syncStatus?.syncReceipt?.conflictSamples);
    const firstConflict = conflictSamples[0] || {};
    const conflictResolutionReceipts = parseWorkspaceSyncConflictResolutions(workspace);
    const conflictBatchResolutionReceipts = parseWorkspaceSyncConflictBatchResolutions(workspace);
    const syncReceipt = syncStatus?.syncReceipt || {};
    const conflictCount = asInt(syncStatus?.conflictsDetected || syncReceipt?.conflictsDetected);
    const manualReviewRequired = Boolean(syncStatus?.manualReviewRequired || syncReceipt?.manualReviewRequired);
    const syncLabel = syncReceipt?.receiptId
      ? "NAS sync receipt"
      : Object.keys(syncStatus).length > 0
        ? "NAS sync recorded"
        : workspace?.auto_sync_to_nas ? "NAS sync enabled" : "Manual sync";
    return {
      workspaceId: workspace?.workspace_id || "",
      title: workspace?.name || "Workspace",
      path: workspace?.root_path || "",
      folderLabel: pathLeafLabel(workspace?.root_path),
      runtime: runtimeLabel(workspace?.default_runtime),
      missionCount: rows.length,
      activeCount: active.length,
      blockedCount: blocked,
      completedCount: completed,
      delegatedCount: delegated,
      progressHistory: progress,
      progressMilestones: asList(progress?.milestones),
      progressBuckets: asList(progress?.buckets),
      scheduleRecommendation: progress?.scheduleRecommendation || {},
      syncAuthority: progress?.syncAuthority || {},
      launchRehearsal: progress?.launchRehearsal || {},
      liveProgressSource: progress?.source || projectProgressHistory?.source || "",
      liveProgressEventCount: asInt(progress?.counts?.events),
      artifactReadyCount: readyArtifacts,
      artifactMissingCount: missingArtifacts,
      latestMissionId: latest?.mission_id || "",
      latestMissionTitle: latest?.title || latest?.objective || "No mission yet",
      latestStatus: titleizeToken(latest?.state?.status || "not_started"),
      latestUpdatedAt: deriveMissionLatestTimestamp(latest),
      nextAction,
      syncLabel,
      syncStatus: {
        schema: syncReceipt?.schema || syncStatus?.schema || "fluxio.workspace_sync_status.v1",
        receiptId: syncReceipt?.receiptId || "",
        generatedAt: syncReceipt?.generatedAt || "",
        effectiveDirection: syncStatus?.effectiveDirection || syncReceipt?.effectiveDirection || "",
        conflictPolicy: syncStatus?.sync_conflict_policy || syncReceipt?.conflictPolicy || workspace?.sync_conflict_policy || "",
        filesCopied: asInt(syncStatus?.filesCopied || syncReceipt?.filesCopied),
        filesSkipped: asInt(syncStatus?.filesSkipped || syncReceipt?.filesSkipped),
        conflictCount,
        manualReviewRequired,
        conflictSamples,
        conflictResolutionReceipts,
        conflictBatchResolutionReceipts,
        firstConflictRelativePath: firstConflict?.relativePath || "",
        batchConflictRelativePaths: conflictSamples.map(item => item?.relativePath).filter(Boolean).slice(0, 20),
        resolutionControls: conflictCount > 0
          ? [
              { id: "keep_newer", label: "Keep newer", resolution: "keep_newer" },
              { id: "local_wins", label: "Use computer", resolution: "local_wins" },
              { id: "nas_wins", label: "Use NAS", resolution: "nas_wins" },
            ]
          : [],
        batchResolutionControls: conflictCount > 1
          ? [
              { id: "batch_keep_newer", label: "Batch keep newer", resolution: "keep_newer" },
              { id: "batch_local_wins", label: "Batch use computer", resolution: "local_wins" },
              { id: "batch_nas_wins", label: "Batch use NAS", resolution: "nas_wins" },
            ]
          : [],
      },
      tone: manualReviewRequired || blocked > 0 || missingArtifacts > 0 ? "warn" : active.length > 0 || completed > 0 || syncReceipt?.receiptId ? "good" : "neutral",
      known: Boolean(workspaceById.get(workspace?.workspace_id)),
    };
  });
}

function deriveMissionArtifactReadiness(mission) {
  const raw = mission?.plannedScopeArtifacts || mission?.planned_scope_artifacts || {};
  const status = String(raw.status || "unplanned").toLowerCase();
  const entries = asList(raw.entries);
  const firstReady = entries.find(item => item?.previewable || item?.status === "ready") || entries[0] || {};
  const counts = {
    scopeCount: asInt(raw.scopeCount),
    existingCount: asInt(raw.existingCount),
    readyCount: asInt(raw.readyCount),
    partialCount: asInt(raw.partialCount),
    missingCount: asInt(raw.missingCount),
    readmeCount: asInt(raw.readmeCount),
    previewableCount: asInt(raw.previewableCount),
  };
  return {
    status,
    tone:
      status === "ready"
        ? "good"
        : status === "missing" || status === "partial"
          ? "warn"
          : "neutral",
    label:
      status === "ready"
        ? "Artifacts ready"
        : status === "missing"
          ? "Artifacts missing"
          : status === "partial"
            ? "Artifacts partial"
            : "Artifacts unplanned",
    counts,
    path: firstReady?.path || firstReady?.resolvedPath || "",
    readmePath: firstReady?.readmePath || "",
    indexHtmlPath: firstReady?.indexHtmlPath || "",
    previewFiles: asList(firstReady?.previewFiles).slice(0, 3),
    sampleFiles: asList(firstReady?.sampleFiles).slice(0, 4),
    nextAction: raw.nextAction || "",
  };
}

function deriveMissionArtifactEntrypoints(mission) {
  const raw = mission?.plannedScopeArtifacts || mission?.planned_scope_artifacts || {};
  return asList(raw.entries)
    .filter(item => item?.path || item?.resolvedPath || item?.readmePath || item?.indexHtmlPath)
    .map((item, index) => {
      const previewFiles = asList(item?.previewFiles).filter(Boolean);
      const sampleFiles = asList(item?.sampleFiles).filter(Boolean);
      const primaryPath =
        item?.readmePath ||
        item?.indexHtmlPath ||
        previewFiles[0] ||
        sampleFiles[0] ||
        item?.path ||
        item?.resolvedPath ||
        "";
      const path = item?.path || item?.resolvedPath || primaryPath;
      return {
        id: `${mission?.mission_id || "mission"}-artifact-${index}`,
        missionId: mission?.mission_id || "",
        missionTitle: mission?.title || mission?.objective || "Mission",
        status: String(item?.status || raw.status || "unplanned").toLowerCase(),
        label: pathLeafLabel(path) || `Artifact ${index + 1}`,
        path,
        readmePath: item?.readmePath || "",
        indexHtmlPath: item?.indexHtmlPath || "",
        primaryPath,
        previewFiles: previewFiles.slice(0, 3),
        sampleFiles: sampleFiles.slice(0, 4),
        tone: item?.status === "ready" || raw.status === "ready" ? "good" : "warn",
      };
    })
    .filter(item => item.primaryPath)
    .slice(0, 12);
}

function deriveBuilderArtifactReadiness(snapshot, missions) {
  const summary = snapshot?.missionWatchdog?.summary || {};
  const missionArtifacts = asList(missions).map(deriveMissionArtifactReadiness);
  const ready = asInt(summary.artifactReady, missionArtifacts.filter(item => item.status === "ready").length);
  const partial = asInt(summary.artifactPartial, missionArtifacts.filter(item => item.status === "partial").length);
  const missing = asInt(summary.artifactMissing, missionArtifacts.filter(item => item.status === "missing").length);
  const unplanned = asInt(summary.artifactUnplanned, missionArtifacts.filter(item => item.status === "unplanned").length);
  const issueRows = asList(snapshot?.missionWatchdog?.issues)
    .filter(item => item?.kind === "planned_scope_artifacts_not_ready")
    .slice(0, 4);
  const entrypoints = asList(missions)
    .flatMap(deriveMissionArtifactEntrypoints)
    .filter(item => item.status === "ready" || item.readmePath || item.indexHtmlPath)
    .slice(0, 8);
  return {
    schema: "fluxio.builder_artifact_readiness.v1",
    ready,
    partial,
    missing,
    unplanned,
    total: ready + partial + missing + unplanned || asList(missions).length,
    status: missing > 0 ? "missing" : partial > 0 ? "partial" : unplanned > 0 ? "unplanned" : "ready",
    tone: missing > 0 || partial > 0 ? "warn" : "good",
    issueRows,
    entrypoints,
    nextAction:
      issueRows[0]?.firstStep ||
      (missing > 0
        ? "Repair missing planned artifact folders before marking those missions useful."
        : entrypoints.length > 0
          ? "Open a ready mission report or preview from Artifact entrypoints."
          : "Open ready artifacts from the mission or project row."),
  };
}

function deriveBuilderBoard({ mission, workspace, snapshot, confidence, uiMode = "agent" }) {
  const workspaceId = uiMode === "builder" ? "" : workspace?.workspace_id || "";
  const workspaces = asList(snapshot?.workspaces);
  const workspaceById = new Map(workspaces.map(item => [item?.workspace_id, item]));
  const missions = asList(snapshot?.missions).filter(item =>
    workspaceId ? item?.workspace_id === workspaceId : true,
  );
  const missionById = new Map(missions.map(item => [item?.mission_id, item]));
  const activeMissions = missions.filter(item => !isTerminalMissionStatus(item?.state?.status));
  const blockedCount = activeMissions.filter(item => missionNeedsAttention(item)).length;
  const delegatedLaneCount = activeMissions.reduce(
    (total, item) =>
      total +
      asList(item?.delegated_runtime_sessions).filter(
        session => !["completed", "failed", "stopped"].includes(session?.status || ""),
      ).length,
    0,
  );
  const runtimeCount = new Set(activeMissions.map(item => item?.runtime_id).filter(Boolean)).size;
  const selectedMissionId = mission?.mission_id || "";
  const productionHarness =
    snapshot?.harnessLab?.productionHarness || workspace?.preferred_harness || "fluxio_hybrid";

  const activeConversations = activeMissions
    .slice()
    .sort((left, right) => {
      const delta = timeValue(deriveMissionLatestTimestamp(right)) - timeValue(deriveMissionLatestTimestamp(left));
      if (Number.isFinite(delta) && delta !== 0) {
        return delta;
      }
      return String(left?.title || left?.objective || "").localeCompare(
        String(right?.title || right?.objective || ""),
      );
    })
    .map(item => {
      const ownerWorkspace = workspaceById.get(item?.workspace_id) || workspace;
      const status = item?.state?.status || item?.missionLoop?.continuityState || "active";
      const artifactReadiness = deriveMissionArtifactReadiness(item);
      const executionPath = deriveMissionExecutionPath(item, ownerWorkspace);
      const contextRoots = deriveMissionContextRoots(item, ownerWorkspace, snapshot);
      const providerTruth =
        item?.providerTruth ||
        item?.missionLoop?.providerTruth ||
        item?.state?.provider_runtime_truth ||
        {};
      const activeRoute = providerTruth?.activeRoute || {};
      const blocker =
        item?.missionLoop?.blocker ||
        item?.state?.blocker_classification ||
        {};
      const stuckReason =
        blocker?.summary ||
        resolveMissionPauseReason(item) ||
        "";
      return {
        missionId: item?.mission_id || "",
        workspaceId: item?.workspace_id || "",
        workspaceName: ownerWorkspace?.name || "Workspace",
        workspacePath: ownerWorkspace?.root_path || "",
        folderLabel: pathLeafLabel(executionPath) || pathLeafLabel(ownerWorkspace?.root_path || ""),
        title: item?.title || item?.objective || "Mission",
        runtime: runtimeLabel(item?.runtime_id),
        statusLabel: titleizeToken(status),
        tone: missionStatusTone(item?.state?.status),
        selected: item?.mission_id === selectedMissionId,
        blocked: missionNeedsAttention(item),
        current: deriveCurrentTask(item),
        next: deriveNextCheckpoint(item),
        lastMovement: deriveMissionLastMovement(item),
        updatedAt: deriveMissionLatestTimestamp(item),
        pendingApprovals: asList(item?.proof?.pending_approvals).length,
        verificationFailures: asList(item?.state?.verification_failures).length,
        delegatedSessions: asList(item?.delegated_runtime_sessions).filter(
          session => !["completed", "failed", "stopped"].includes(session?.status || ""),
        ).length,
        executionPath,
        contextRoots,
        contextRootCount: contextRoots.counts.totalRoots,
        relatedRootCount: contextRoots.counts.relatedWorkspaces,
        harnessLabel: titleizeToken(item?.harness_id || productionHarness),
        providerLabel: activeRoute?.provider ? titleizeToken(activeRoute.provider) : "Unresolved",
        modelLabel: activeRoute?.model || "Profile default",
        routeRole: activeRoute?.role ? titleizeToken(activeRoute.role) : "Route",
        blockerClass: blocker?.class || "",
        stuckReason,
        nextCheckpointPrediction: deriveNextCheckpoint(item),
        artifactReadiness,
        artifactStatus: artifactReadiness.status,
        artifactLabel: artifactReadiness.label,
        artifactPath: artifactReadiness.readmePath || artifactReadiness.indexHtmlPath || artifactReadiness.path,
      };
    });

  const projectProgressHistory = deriveProjectProgressHistory(snapshot);
  const workspaceHealth = deriveWorkspaceHealth(
    workspaces,
    missions,
    activeConversations,
    workspaceById,
    projectProgressHistory,
  );
  const artifactReadiness = deriveBuilderArtifactReadiness(snapshot, missions);

  const roots = workspaces
    .filter(item => (workspaceId ? item?.workspace_id === workspaceId : true))
    .map(item => {
      const workspaceConversations = activeConversations.filter(
        entry => entry.workspaceId === item?.workspace_id,
      );
      const health = workspaceHealth.find(row => row.workspaceId === item?.workspace_id) || {};
      const blocked = workspaceConversations.filter(entry => entry.blocked).length;
      const delegated = workspaceConversations.reduce(
        (total, entry) => total + asInt(entry.delegatedSessions),
        0,
      );
      return {
        workspaceId: item?.workspace_id || "",
        title: item?.name || "Workspace",
        path: item?.root_path || "",
        folderLabel: pathLeafLabel(item?.root_path),
        activeCount: workspaceConversations.length,
        blockedCount: blocked,
        delegatedCount: delegated,
        artifactReadyCount: health.artifactReadyCount || 0,
        artifactMissingCount: health.artifactMissingCount || 0,
        tone:
          blocked > 0 || health.artifactMissingCount > 0
            ? "warn"
            : workspaceConversations.length > 0 || item?.runtimeStatus?.detected
              ? "good"
              : "neutral",
      };
    })
    .sort((left, right) => {
      if (left.blockedCount !== right.blockedCount) {
        return right.blockedCount - left.blockedCount;
      }
      if (left.activeCount !== right.activeCount) {
        return right.activeCount - left.activeCount;
      }
      return String(left.title).localeCompare(String(right.title));
    });

  const nexuses = activeMissions
    .map(item => deriveMissionNexus(item, workspaceById.get(item?.workspace_id) || workspace))
    .filter(Boolean)
    .sort((left, right) => timeValue(right.timestamp) - timeValue(left.timestamp))
    .slice(0, 8);

  const whileAway = asList(snapshot?.activity)
    .filter(item => {
      if (!item?.mission_id) {
        return true;
      }
      const missionRow = missionById.get(item.mission_id);
      return workspaceId ? missionRow?.workspace_id === workspaceId : true;
    })
    .slice(0, 10)
    .map((item, index) => ({
      id: `${item?.mission_id || "workspace"}-${item?.timestamp || index}-${item?.kind || "activity"}`,
      missionId: item?.mission_id || "",
      missionTitle:
        missionById.get(item?.mission_id)?.title ||
        missionById.get(item?.mission_id)?.objective ||
        "Workspace activity",
      label: titleizeToken(item?.kind || "activity"),
      message: item?.message || "Activity update",
      detail: deriveActivityDetail(item, missionById),
      tone: activityTone(item),
      timestamp: item?.timestamp || "",
    }));

  const nextUpSource = activeConversations.length > 0 ? activeConversations : [];
  const nextUp = nextUpSource.slice(0, 8).map(item => ({
    missionId: item.missionId,
    title: item.title,
    statusLabel: item.statusLabel,
    runtime: item.runtime,
    summary: item.next,
    detail: item.blocked ? item.lastMovement : item.current,
    routeLabel: `${item.providerLabel} · ${item.modelLabel}`,
    checkpoint: item.nextCheckpointPrediction,
    artifactLabel: item.artifactLabel,
    artifactPath: item.artifactPath,
    tone: item.blocked ? "warn" : item.tone,
    updatedAt: item.updatedAt,
    selected: item.selected,
  }));

  const stuckThreads = activeConversations
    .filter(item => item.blocked || item.blockerClass || item.stuckReason)
    .slice(0, 6)
    .map(item => ({
      missionId: item.missionId,
      title: item.title,
      blockerClass: titleizeToken(item.blockerClass || "operator_only"),
      reason: item.stuckReason || item.lastMovement || "Blocked without a recorded reason.",
      routeLabel: `${item.providerLabel} · ${item.modelLabel}`,
      runtime: item.runtime,
      tone: item.tone === "bad" ? "bad" : "warn",
    }));

  const winningRouteMap = new Map();
  for (const item of activeConversations) {
    const key = `${item.runtime}|${item.providerLabel}|${item.modelLabel}`;
    const existing = winningRouteMap.get(key) || {
      key,
      runtime: item.runtime,
      provider: item.providerLabel,
      model: item.modelLabel,
      activeCount: 0,
      blockedCount: 0,
    };
    existing.activeCount += 1;
    if (item.blocked) {
      existing.blockedCount += 1;
    }
    winningRouteMap.set(key, existing);
  }
  const winningRoutes = [...winningRouteMap.values()]
    .sort((left, right) => {
      if (left.blockedCount !== right.blockedCount) {
        return left.blockedCount - right.blockedCount;
      }
      return right.activeCount - left.activeCount;
    })
    .slice(0, 4)
    .map(item => ({
      ...item,
      tone: item.blockedCount > 0 ? "warn" : "good",
      label: `${item.runtime} · ${item.provider} · ${item.model}`,
      detail:
        item.blockedCount > 0
          ? `${item.activeCount} active · ${item.blockedCount} blocked`
          : `${item.activeCount} active and clear`,
    }));

  const predictedCheckpoints = nextUp
    .map(item => `${item.title}: ${item.checkpoint || item.summary}`)
    .slice(0, 6);

  const changedWhileAway = whileAway
    .slice(0, 6)
    .map(item => `${item.missionTitle}: ${item.message}`);

  const summary =
    activeConversations.length > 0
      ? `${activeConversations.length} active conversation${activeConversations.length === 1 ? "" : "s"} across ${Math.max(runtimeCount, 1)} runtime lane${Math.max(runtimeCount, 1) === 1 ? "" : "s"}. ${blockedCount > 0 ? `${blockedCount} need operator attention.` : "No operator block is active right now."} Top route: ${winningRoutes[0]?.label || "not resolved yet"}.`
      : "No active conversations. Builder stays ready for launch, runtime tuning, and review.";
  const subAgentLanes = deriveSubAgentLanes(
    missions,
    workspaceById,
    workspace,
    productionHarness,
  );
  const selectedContextRoots =
    (selectedMissionId
      ? activeConversations.find(item => item.missionId === selectedMissionId)?.contextRoots
      : null) ||
    activeConversations[0]?.contextRoots ||
    (mission ? deriveMissionContextRoots(mission, workspace, snapshot) : null);

  return {
    headline:
      activeConversations.length > 0
        ? "Builder command deck"
        : "Builder readiness deck",
    summary,
    metrics: [
      {
        id: "active",
        label: "Active conversations",
        value: `${activeConversations.length}`,
        detail: activeConversations.length > 0 ? "Visible in the control board" : "Launch a mission to start the board",
        tone: activeConversations.length > 0 ? "good" : "neutral",
      },
      {
        id: "blocked",
        label: "Need attention",
        value: `${blockedCount}`,
        detail: blockedCount > 0 ? "Approvals, queue, or verification boundaries are open" : "No active blockers",
        tone: blockedCount > 0 ? "warn" : "good",
      },
      {
        id: "delegated",
        label: "Delegated lanes",
        value: `${delegatedLaneCount}`,
        detail: delegatedLaneCount > 0 ? "Hermes/OpenClaw sessions in flight" : "No live delegated lane right now",
        tone: delegatedLaneCount > 0 ? "neutral" : "warn",
      },
      {
        id: "artifacts",
        label: "Ready artifacts",
        value: `${artifactReadiness.ready}`,
        detail:
          artifactReadiness.missing > 0 || artifactReadiness.partial > 0
            ? `${artifactReadiness.missing} missing · ${artifactReadiness.partial} partial`
            : `${artifactReadiness.ready}/${artifactReadiness.total} mission scopes ready`,
        tone: artifactReadiness.tone,
      },
      {
        id: "harness",
        label: "Production harness",
        value: titleizeToken(productionHarness),
        detail: snapshot?.harnessLab?.recommendation || "Harness comparison is visible in Builder.",
        tone: blockedCount > 0 ? "warn" : "good",
      },
    ],
    activeConversations,
    artifactReadiness,
    roots,
    workspaceHealth,
    projectProgressHistory: {
      schema: projectProgressHistory.schema,
      source: projectProgressHistory.source,
      eventLimit: projectProgressHistory.eventLimit,
      liveData: projectProgressHistory.liveData,
      projects: projectProgressHistory.projects,
    },
    subAgentLanes,
    contextRoots: selectedContextRoots,
    nexuses,
    whileAway,
    nextUp,
    stuckThreads,
    winningRoutes,
    changedWhileAway,
    predictedCheckpoints,
    selectedFocus: mission
      ? {
          missionId: mission.mission_id,
          title: mission.title || mission.objective || "Mission",
          current: deriveCurrentTask(mission),
          next: deriveNextCheckpoint(mission),
          lastMovement: deriveMissionLastMovement(mission),
          proof: deriveVerificationSummary(mission),
          updatedAt: deriveMissionLatestTimestamp(mission),
        }
      : null,
  };
}

function priorityTone(priority) {
  const normalized = String(priority || "").toLowerCase();
  if (normalized === "high") {
    return "bad";
  }
  if (normalized === "medium") {
    return "warn";
  }
  if (normalized === "low") {
    return "good";
  }
  return "neutral";
}

function actionForGuidancePanel(panel) {
  const normalized = String(panel || "").toLowerCase();
  if (normalized === "auth") {
    return "open_auth";
  }
  if (normalized === "setup") {
    return "open_runtime";
  }
  if (normalized === "guidance") {
    return "open_profiles";
  }
  if (normalized === "projects") {
    return "open_workspace";
  }
  if (normalized === "missions") {
    return "open_mission";
  }
  if (normalized === "integrations") {
    return "open_escalation";
  }
  if (normalized === "builder_view" || normalized === "builder") {
    return "open_builder";
  }
  if (normalized === "skill_studio" || normalized === "skills") {
    return "open_skills";
  }
  return "open_builder";
}

function deriveTutorialStudio({
  mission,
  snapshot,
  setupHealth,
  profileId,
  workflowStudio,
}) {
  const onboarding = snapshot?.onboarding || {};
  const guidance = snapshot?.guidance || {};
  const tutorial = onboarding?.tutorial || {};
  const completedSteps = asList(tutorial?.completedSteps);
  const steps = asList(tutorial?.steps).map((item, index) => {
    const status = String(
      item?.status ||
        (completedSteps.includes(item?.step_id)
          ? "completed"
          : item?.step_id === tutorial?.currentStepId
            ? "current"
            : "pending"),
    ).toLowerCase();
    return {
      id: item?.step_id || `step-${index}`,
      title: item?.title || `Step ${index + 1}`,
      description: item?.description || "",
      panel: item?.panel || "Builder",
      status: titleizeToken(status),
      done: status === "completed",
      current: status === "current" || status === "in_progress" || item?.step_id === tutorial?.currentStepId,
      tone: status === "completed" ? "good" : status === "pending" ? "neutral" : "warn",
      actionId: actionForGuidancePanel(item?.panel),
    };
  });
  const currentStep =
    steps.find(item => item.current) ||
    steps.find(item => !item.done) ||
    steps[steps.length - 1] ||
    null;
  const motionMode =
    snapshot?.profiles?.details?.[profileId]?.ui?.motion ||
    asList(guidance?.profileChoices).find(item => item?.name === profileId)?.motion ||
    "standard";
  const readiness = uniq([
    ...asList(onboarding?.nextActions),
    ...asList(setupHealth?.blockerExplanations),
  ]).slice(0, 4);
  const cards = asList(guidance?.guidanceCards)
    .slice(0, 4)
    .map(item => ({
      id: item?.card_id || item?.title || "guide",
      title: item?.title || "Guidance",
      body: item?.body || "",
      panel: item?.panel || "Builder",
      kind: titleizeToken(item?.kind || "guide"),
      actionId: actionForGuidancePanel(item?.panel || item?.kind),
    }));
  const improvements = asList(guidance?.productImprovements)
    .slice(0, 3)
    .map(item => ({
      id: item?.item_id || item?.title || "improvement",
      title: item?.title || "Improvement",
      reason: item?.reason || "",
      priority: titleizeToken(item?.priority || "medium"),
      category: titleizeToken(item?.category || "product"),
      tone: priorityTone(item?.priority),
    }));

  return {
    headline: tutorial?.isComplete ? "Tutorial complete" : currentStep?.title || "Finish guided setup",
    summary: tutorial?.isComplete
      ? "Builder is ready for real mission work. Keep the guide nearby for deliberate setup and escalation."
      : currentStep?.description ||
        "Finish the guided path so Builder, runtime policy, and escalation all stay coherent.",
    progressLabel: `${completedSteps.length}/${Math.max(steps.length, 1)} complete`,
    currentStep,
    steps,
    cards,
    improvements,
    readiness,
    motionMode: titleizeToken(motionMode),
    recommendedWorkflow: workflowStudio?.recommended?.label || "Long-Run Agent Session",
    primaryActionId: currentStep?.actionId || "open_mission",
    primaryActionLabel:
      currentStep?.panel ? `Open ${currentStep.panel}` : mission ? "Keep building" : "Launch first mission",
  };
}

function deriveRecommendationStudio({
  mission,
  workspace,
  setupHealth,
  serviceStudio,
  skillStudio,
  workflowStudio,
  qualityRoadmap,
  builderBoard,
}) {
  const struggleSignals = [];
  const approvalCount = asInt(asList(mission?.proof?.pending_approvals).length);
  const verificationCount = asInt(asList(mission?.state?.verification_failures).length);
  const serviceAttention = asInt(serviceStudio?.summary?.needsAttentionCount);
  const skillAttention = asInt(skillStudio?.summary?.needsTestCount);

  if (approvalCount > 0) {
    struggleSignals.push({
      id: "approval-friction",
      label: "Approval friction",
      detail: `${approvalCount} approval boundary is slowing the loop right now.`,
      tone: "warn",
      actionId: "open_queue",
    });
  }
  if (verificationCount > 0) {
    struggleSignals.push({
      id: "verification-friction",
      label: "Verification friction",
      detail: `${verificationCount} failed verification signal needs proof-first attention.`,
      tone: "bad",
      actionId: "open_proof",
    });
  }
  if (serviceAttention > 0) {
    struggleSignals.push({
      id: "runtime-drift",
      label: "Runtime drift",
      detail: `${serviceAttention} runtime or service item still needs repair or review.`,
      tone: "warn",
      actionId: "open_runtime",
    });
  }
  if (skillAttention > 0) {
    struggleSignals.push({
      id: "skill-gap",
      label: "Skill coverage gap",
      detail: `${skillAttention} skill pack(s) still need tests or promotion before they can be trusted.`,
      tone: "warn",
      actionId: "open_skills",
    });
  }
  if (struggleSignals.length === 0) {
    struggleSignals.push({
      id: "clear-lane",
      label: "No major blocker",
      detail: "Use the recommended workflow and keep Builder focused on the highest-value active conversation.",
      tone: "good",
      actionId: "open_mission",
    });
  }

  const skillRecommendations = uniq([
    ...asList(workspace?.skillRecommendations).map(item => `${item?.label || "Skill"}||${item?.reason || ""}`),
    ...skillStudio.recommended.map(item => `${item?.label || "Pack"}||${item?.description || ""}`),
  ])
    .slice(0, 4)
    .map((item, index) => {
      const [label, reason] = String(item).split("||");
      return {
        id: `skill-recommendation-${index}-${label}`,
        label,
        reason,
      };
    });

  const nextMoves = uniq([
    ...asList(qualityRoadmap?.tracks)
      .filter(item => item?.state !== "done")
      .slice(0, 3)
      .map(item => `${item?.label || "Next move"}||${item?.suggestedAction || "Open"}||${item?.actionKind || ""}`),
    workflowStudio?.recommended?.label
      ? `${workflowStudio.recommended.label}||Recommended workflow for the current profile||workflow`
      : "",
    asList(setupHealth?.blockerExplanations)[0]
      ? `${asList(setupHealth?.blockerExplanations)[0]}||Resolve setup blocker before long unattended runs||runtime`
      : "",
  ])
    .slice(0, 4)
    .map((item, index) => {
      const [label, detail, actionKind] = String(item).split("||");
      return {
        id: `recommendation-next-${index}`,
        label,
        detail,
        actionId:
          actionKind === "validate"
            ? "run_validation"
            : actionKind === "workflow"
              ? "open_workflow"
              : actionKind === "skill"
                ? "open_skills"
                : actionKind === "service" || actionKind === "runtime"
                  ? "open_runtime"
                  : "open_mission",
      };
    });

  return {
    headline:
      workflowStudio?.recommended?.label || "Builder recommendations",
    summary:
      builderBoard.activeConversations.length > 0
        ? "Recommendations adapt to the active conversations, current blockers, and the packs that still need work."
        : "Recommendations are based on setup state, workflow readiness, and the gaps still blocking a strong first run.",
    struggleSignals: struggleSignals.slice(0, 4),
    skillRecommendations,
    nextMoves,
    learningQueue: asList(workflowStudio?.learningQueue).slice(0, 4).map((item, index) => ({
      id: `learning-${index}-${item?.title || item}`,
      title: item?.title || listLabel(item),
      priority: titleizeToken(item?.priority || "medium"),
      tone: priorityTone(item?.priority),
    })),
    activeConversationCount: builderBoard.activeConversations.length,
    blockedConversationCount: builderBoard.activeConversations.filter(item => item.blocked).length,
    recommendedSurface: titleizeToken(workflowStudio?.recommended?.surface || "builder_view"),
  };
}

function deriveLiveReviewStudio({
  mission,
  workspace,
  snapshot,
  previewMode,
  liveSyncSeconds,
  liveSyncSuspended,
  lastPushReason,
  isRefreshing,
  builderBoard,
}) {
  const bridgeSessions = asList(snapshot?.bridgeLab?.connectedSessions);
  const missionFiles = deriveChanged(mission, workspace).slice(0, 3);
  const reviewTargets = [];

  reviewTargets.push({
    id: "review-preview",
    label: previewMode === "live" ? "Live surface" : "Fixture surface",
    title: previewMode === "live" ? "Live Builder review" : previewLabel(previewMode, snapshot?.previewMeta),
    detail:
      previewMode === "live"
        ? liveSyncSuspended
          ? "Live sync is paused while the surface is hidden."
          : lastPushReason
            ? `Latest backend push: ${lastPushReason}.`
            : "Live backend state is active for review."
        : "Fixture mode is active for repeatable review and screenshot work.",
    tone: previewMode === "live" ? (liveSyncSuspended ? "warn" : "good") : "neutral",
    actionId: "open_builder",
    commentSeed:
      previewMode === "live"
        ? "Live UI review note for the current Builder surface:\nWhat feels wrong:\nWhat should change:\n"
        : "Fixture review note:\nThis scenario should read differently because \n",
  });

  if (mission) {
    reviewTargets.push({
      id: `review-mission-${mission?.mission_id || "current"}`,
      label: "Mission focus",
      title: mission?.title || mission?.objective || "Current mission",
      detail: `${deriveCurrentTask(mission)} · Next ${deriveNextCheckpoint(mission)}`,
      tone: missionNeedsAttention(mission) ? "warn" : missionStatusTone(mission?.state?.status),
      actionId: "focus_thread",
      commentSeed: `Mission UI review for ${mission?.title || "the current mission"}:\nThis decision point should look different because \n`,
    });
  }

  if (builderBoard.activeConversations.length > 1) {
    reviewTargets.push({
      id: "review-conversations",
      label: "Conversation grid",
      title: `${builderBoard.activeConversations.length} active conversations`,
      detail: `${builderBoard.activeConversations.filter(item => item.blocked).length} blocked · ${builderBoard.activeConversations.length - 1} secondary thread card(s) visible.`,
      tone: builderBoard.activeConversations.some(item => item.blocked) ? "warn" : "good",
      actionId: "focus_conversations",
      commentSeed: "Conversation board review:\nWhich thread deserves more visual weight and why:\n",
    });
  }

  for (const [index, item] of bridgeSessions.slice(0, 2).entries()) {
    reviewTargets.push({
      id: item?.session_id || `review-bridge-${index}`,
      label: titleizeToken(item?.bridge_transport || "bridge"),
      title: item?.app_name || "Connected app",
      detail:
        asList(item?.context_preview).map(entry => entry?.summary).find(Boolean) ||
        item?.latest_task_result?.resultSummary ||
        "Connected app review target is ready.",
      tone: item?.bridge_health === "healthy" ? "good" : "warn",
      actionId: "open_runtime",
      commentSeed: `Bridge review for ${item?.app_name || "this app"}:\nThis hand-off or preview block should change because \n`,
    });
  }

  for (const [index, file] of missionFiles.entries()) {
    reviewTargets.push({
      id: `review-file-${index}-${file}`,
      label: "Changed file",
      title: file,
      detail: "Use this as a review anchor when pointing at what should change in the live UI flow.",
      tone: "neutral",
      actionId: "open_proof",
      commentSeed: `Review note for ${file}:\nThe visible UI behavior should change like this:\n`,
    });
  }

  const rawPreviewUrl = mission?.state?.last_preview_url || mission?.state?.preview_url || "";
  const liveReviewMissionKey =
    mission?.mission_id ||
    mission?.id ||
    workspace?.workspace_id ||
    workspace?.id ||
    "no-mission";
  const liveReviewEventId = suffix => `mission:${liveReviewMissionKey}:${suffix}`;
  const controlPreviewUrl = mission?.mission_id
    ? `/control?mode=agent&surface=agent&agentScene=run&missionId=${encodeURIComponent(mission.mission_id)}`
    : "/control?mode=builder&surface=builder";
  const previewUrl = rawPreviewUrl || "No preview URL captured";
  const hasServedLivePreview = previewMode === "live" && Boolean(rawPreviewUrl);
  const previewSourceLabel = hasServedLivePreview
    ? "Served live preview"
    : previewMode === "live"
      ? "Agent live surface"
      : "Fixture review surface";
  const previewSourceDetail = hasServedLivePreview
    ? rawPreviewUrl
    : previewMode === "live"
      ? "No browser-served preview URL has been captured; open the selected mission inside the live Agent surface."
      : "Fixture mode is useful for repeatable layout review, but it is not production proof.";
  const screenshotPath =
    mission?.proof?.latest_screenshot_path ||
    mission?.state?.last_screenshot_path ||
    (previewMode === "live" ? "" : "screenshots/latest.png");
  const verificationStep =
    asList(mission?.state?.verification_failures).length > 0 ? "Verification blocked by failing checks" : "Verification checks in progress";
  const imageArtifacts = asList(mission?.proof?.artifacts)
    .map(item => item?.path || item?.artifact_path || "")
    .filter(Boolean)
    .slice(0, 2);
  const nowDate = new Date();
  const nowTimestamp = nowDate.toISOString();
  const progressWindow =
    mission?.state?.last_progress_update_at || mission?.state?.updated_at || mission?.updated_at || mission?.created_at || "";
  const progressWindowDate = progressWindow ? new Date(progressWindow) : null;
  const progressWindowAgeMinutes =
    progressWindowDate && Number.isFinite(progressWindowDate.getTime())
      ? Math.max(0, Math.round((nowDate.getTime() - progressWindowDate.getTime()) / 60000))
      : null;
  const progressCadenceState =
    progressWindowAgeMinutes == null
      ? "missing"
      : progressWindowAgeMinutes <= 20
        ? "healthy"
        : progressWindowAgeMinutes <= 35
          ? "stale"
          : "overdue";
  const runtimeActivitySignals = uniq(
    asList(snapshot?.activity)
      .slice(0, 10)
      .map(item => item?.message || item?.kind || "")
      .filter(Boolean),
  ).slice(0, 4);
  const latestPlanRevision = asList(mission?.plan_revisions).slice(-1)[0] || {};
  const plannerSelectedSkills = uniq([
    ...asList(latestPlanRevision?.selected_skills),
    ...asList(latestPlanRevision?.selectedSkills),
    ...asList(mission?.state?.selected_skills),
    ...asList(mission?.state?.selectedSkills),
  ]).slice(0, 6);
  const plannerRules = uniq([
    ...asList(latestPlanRevision?.rules),
    ...asList(latestPlanRevision?.guardrails),
    ...asList(mission?.state?.rules),
    ...asList(mission?.state?.guardrails),
  ]).slice(0, 5);
  const plannerDesignPrompts = uniq([
    ...asList(latestPlanRevision?.design_prompts),
    ...asList(latestPlanRevision?.designPrompts),
    ...asList(mission?.state?.design_prompts),
    ...asList(mission?.state?.designPrompts),
  ]).slice(0, 4);
  const plannerNextIdea =
    latestPlanRevision?.next_idea ||
    latestPlanRevision?.nextIdea ||
    mission?.state?.next_idea ||
    mission?.state?.nextIdea ||
    "No next-idea handoff captured yet.";
  const latestStructuredFeedbackReceiptRaw = asList(snapshot?.connectedDeviceBridge?.receipts)
    .slice()
    .reverse()
    .find(receipt => receipt?.receiptKind === "live_review_structured_feedback") || null;
  const latestStructuredFeedbackReceipt = latestStructuredFeedbackReceiptRaw
    ? {
        receiptKind: "live_review_structured_feedback",
        eventId: latestStructuredFeedbackReceiptRaw.eventId || latestStructuredFeedbackReceiptRaw.event_id || "",
        plannerExecutorHandoffId:
          latestStructuredFeedbackReceiptRaw.plannerExecutorHandoffId ||
          latestStructuredFeedbackReceiptRaw.planner_executor_handoff_id ||
          "",
        nextIdea: latestStructuredFeedbackReceiptRaw.nextIdea || latestStructuredFeedbackReceiptRaw.next_idea || "",
        timestamp: latestStructuredFeedbackReceiptRaw.timestamp || "",
        status: latestStructuredFeedbackReceiptRaw.status || "received",
      }
    : null;
  const structuredFeedbackReceipt = latestStructuredFeedbackReceipt;
  const decisionInfluence = [
    {
      id: "skills-to-layout",
      source: plannerSelectedSkills.length > 0 ? plannerSelectedSkills.map(titleizeToken).join(" · ") : "No selected skill captured",
      appliedTo: "UI hierarchy and mobile-safe component density",
      evidence: plannerDesignPrompts[0] || "Design prompt not captured yet",
      verifierFeedback: asList(mission?.state?.verification_failures)[0] || "No verifier objection recorded",
    },
    {
      id: "rules-to-execution",
      source: plannerRules.length > 0 ? plannerRules.join(" · ") : "Default planner guardrails",
      appliedTo: "Executor scope, route preservation, and proof collection",
      evidence: plannerNextIdea,
      verifierFeedback: verificationStep,
    },
  ];
  const internalSupervisorState = snapshot?.internalContinuationSupervisor || {};
  const continuationSupervisor = {
    enabled: internalSupervisorState.enabled !== false,
    hardenedHarness: true,
    state:
      mission?.state?.continuation_reconcile_decision ||
      internalSupervisorState.lastDecision ||
      mission?.missionLoop?.continuityState ||
      mission?.state?.continuity_state ||
      (mission?.state?.status === "running" ? "active" : mission ? "queued" : "idle"),
    lastCompletionAt:
      mission?.state?.continuation_completed_at ||
      mission?.missionLoop?.lastCompletionAt ||
      mission?.state?.last_delegate_completed_at ||
      mission?.state?.updated_at ||
      "",
    reconcileRecordedAt:
      mission?.state?.continuation_dispatch_at || internalSupervisorState.lastDispatchAt || internalSupervisorState.lastRunAt || "",
    expectedDispatchWindowMinutes: "0-2",
    dispatchLagMinutes:
      Number.isFinite(progressWindowAgeMinutes) && progressWindowAgeMinutes >= 0
        ? progressWindowAgeMinutes
        : null,
    failureReason:
      mission?.state?.continuation_reconcile_reason ||
      internalSupervisorState.lastSkippedReason ||
      mission?.missionLoop?.continuityDetail ||
      mission?.state?.continuity_detail ||
      (mission ? "No immediate-continuation failure recorded." : "No active mission to supervise."),
    reconcileLatencyMs:
      asInt(
        mission?.state?.continuation_reconcile_latency_ms ??
          internalSupervisorState.lastContinuationLatencyMs ??
          0,
      ),
    blockerReason:
      mission?.state?.blocker_classification?.reason ||
      internalSupervisorState.lastSkippedReason ||
      mission?.state?.continuation_reconcile_reason ||
      "",
    externalHeartbeatRequired: Boolean(internalSupervisorState.externalHeartbeatRequired),
    safeToStop: Boolean(mission?.missionLoop?.safeToStop || mission?.state?.safe_to_stop),
    budgetGuard: mission?.run_budget?.run_until_behavior || mission?.state?.run_until_behavior || "pause_on_failure",
    routePreservation: {
      selectedSkills: plannerSelectedSkills,
      designPrompts: plannerDesignPrompts,
      nextIdea: plannerNextIdea,
      model:
        mission?.model_route?.executor?.model ||
        mission?.model_route?.planner?.model ||
        mission?.state?.model ||
        "unrecorded",
      provider:
        mission?.model_route?.executor?.provider ||
        mission?.model_route?.planner?.provider ||
        mission?.state?.model_provider ||
        "unrecorded",
      effort:
        mission?.model_route?.executor?.effort ||
        mission?.model_route?.planner?.effort ||
        mission?.state?.model_effort ||
        "unrecorded",
      executionRoot:
        mission?.execution_scope?.execution_root || mission?.state?.execution_root || workspace?.root_path || "unrecorded",
    },
  };
  const missionWatchdogRaw = snapshot?.missionWatchdog || {};
  const missionWatchdogSummary = missionWatchdogRaw.summary || {};
  const missionWatchdogIssues = asList(missionWatchdogRaw.issues);
  const missionWatchdogSupervisor = missionWatchdogRaw.supervisor || {};
  const missionWatchdogRegistry = missionWatchdogRaw.problemRegistry || {};
  const missionWatchdogCadence = missionWatchdogSupervisor.cadencePolicy || {};
  const missionWatchdog = {
    enabled: true,
    schema: missionWatchdogRaw.schema || "fluxio.mission_watchdog.v1",
    supervisorSchema: missionWatchdogSupervisor.schema || "fluxio.mission_watchdog_supervisor.v1",
    checkedAt: missionWatchdogRaw.checkedAt || nowTimestamp,
    staleMinutes: asInt(missionWatchdogRaw.staleMinutes || 60),
    loopStatus: missionWatchdogSupervisor.status || "missing",
    loopMode: missionWatchdogSupervisor.loopMode || "none",
    loopActive: Boolean(missionWatchdogSupervisor.supervisorActive),
    loopStale: Boolean(missionWatchdogSupervisor.stale),
    loopProcessAlive: Boolean(missionWatchdogSupervisor.processAlive),
    loopPid: asInt(missionWatchdogSupervisor.processPid || 0),
    loopLastRunAt: missionWatchdogSupervisor.lastRunAt || "",
    loopNextRunAt: missionWatchdogSupervisor.nextRunAt || "",
    loopIntervalSeconds: asInt(missionWatchdogSupervisor.intervalSeconds || 0),
    loopRunsCompleted: asInt(missionWatchdogSupervisor.runsCompleted || 0),
    loopNotificationStatus: missionWatchdogSupervisor.notificationStatus || "",
    cadencePolicy: {
      schema: missionWatchdogCadence.schema || "fluxio.mission_watchdog_cadence.v1",
      activeIntervalSeconds: asInt(
        missionWatchdogCadence.activeIntervalSeconds || missionWatchdogSupervisor.intervalSeconds || 0,
      ),
      staleMinutes: asInt(missionWatchdogCadence.staleMinutes || missionWatchdogSupervisor.staleMinutes || 60),
      configureCommand:
        missionWatchdogCadence.configureCommand ||
        "python -m grant_agent.cli mission-watchdog --loop --max-runs 0 --interval-seconds <seconds>",
      presets: asList(missionWatchdogCadence.presets).slice(0, 5),
    },
    issueCount: asInt(missionWatchdogSummary.issueCount || missionWatchdogIssues.length),
    bad: asInt(missionWatchdogSummary.bad || 0),
    warn: asInt(missionWatchdogSummary.warn || 0),
    info: asInt(missionWatchdogSummary.info || 0),
    queuePressure: asInt(missionWatchdogSummary.queuePressure || 0),
    queuePressureSafe: asInt(missionWatchdogSummary.queuePressureSafe || 0),
    queuePressureUnknown: asInt(missionWatchdogSummary.queuePressureUnknown || 0),
    queuePressureOverlap: asInt(missionWatchdogSummary.queuePressureOverlap || 0),
    artifactReady: asInt(missionWatchdogSummary.artifactReady || 0),
    artifactPartial: asInt(missionWatchdogSummary.artifactPartial || 0),
    artifactMissing: asInt(missionWatchdogSummary.artifactMissing || 0),
    artifactUnplanned: asInt(missionWatchdogSummary.artifactUnplanned || 0),
    missionCount: asInt(missionWatchdogSummary.missionCount || asList(snapshot?.missions).length),
    activeWorkspaceCount: asInt(missionWatchdogSummary.activeWorkspaceCount || 0),
    nextAction:
      missionWatchdogSupervisor.nextAction && (missionWatchdogSupervisor.stale || !missionWatchdogSupervisor.supervisorActive)
        ? missionWatchdogSupervisor.nextAction
        : missionWatchdogRaw.nextAction ||
          "No watchdog issues found. Keep the scheduled watchdog active.",
    issues: missionWatchdogIssues.slice(0, 8),
    problemRegistry: {
      schema: missionWatchdogRegistry.schema || "fluxio.watchdog_problem_registry.v1",
      status: missionWatchdogRegistry.status || "clear",
      openProblemCount: asInt(missionWatchdogRegistry.openProblemCount || 0),
      resolvedProblemCount: asInt(missionWatchdogRegistry.resolvedProblemCount || 0),
      newProblemCount: asInt(missionWatchdogRegistry.newProblemCount || 0),
      firstOpenProblem: missionWatchdogRegistry.firstOpenProblem || {},
      nextAction:
        missionWatchdogRegistry.nextAction ||
        missionWatchdogRaw?.problemReport?.nextAction ||
        "No open watchdog problems. Keep the external loop active.",
      problems: asList(missionWatchdogRegistry.problems).slice(0, 8),
    },
    artifactEntryPoints: asList(builderBoard?.artifactReadiness?.entrypoints).slice(0, 8),
  };

  const events = [
    {
      id: liveReviewEventId("file-change"),
      kind: "file_change",
      label: "File changes",
      title: missionFiles[0] || "No tracked file changes yet",
      detail: missionFiles.length > 0 ? `${missionFiles.join(" · ")}` : "Run a mission to capture changed paths.",
      tone: missionFiles.length > 0 ? "good" : "neutral",
      timestamp: progressWindow,
      artifactPaths: missionFiles,
      source: "workspace_diff",
      liveEvidence: missionFiles.length > 0,
    },
    {
      id: liveReviewEventId("browser-qa"),
      kind: "browser_qa",
      label: "Browser QA",
      title: hasServedLivePreview ? "Browser-use actions" : "Preview proof not captured",
      detail: `Preview URL: ${previewUrl}`,
      tone: hasServedLivePreview ? "good" : previewMode === "live" ? "warn" : "neutral",
      timestamp: nowTimestamp,
      previewUrl: rawPreviewUrl,
      previewSourceLabel,
      previewSourceDetail,
      browserActions: ["open_page", "audit_layout", "report_issue"],
      deepLink: { type: "review_target", targetId: reviewTargets[0]?.id || "" },
      liveEvidence: Boolean(rawPreviewUrl),
    },
    {
      id: liveReviewEventId("computer-use"),
      kind: "computer_use",
      label: "Computer-use",
      title: "Program launch and handoff",
      detail:
        mission?.state?.current_runtime_lane || mission?.runtime_id
          ? `Lane ${mission?.state?.current_runtime_lane || mission?.runtime_id} active`
          : "No runtime lane reported yet",
      tone: mission?.state?.current_runtime_lane || mission?.runtime_id ? "good" : "warn",
      timestamp: nowTimestamp,
      launchedPrograms: asList(mission?.state?.launched_programs).slice(0, 3),
      runtimeActivity: runtimeActivitySignals,
      deepLink: { type: "drawer", drawerId: "runtime" },
      liveEvidence: Boolean(mission?.state?.current_runtime_lane || mission?.runtime_id),
    },
    {
      id: liveReviewEventId("screenshot"),
      kind: "preview_refresh",
      label: "Preview refresh",
      title: "Screenshot and preview sync",
      detail: screenshotPath
        ? `Latest screenshot artifact: ${screenshotPath}`
        : "No screenshot artifact captured by the live mission yet.",
      tone: liveSyncSuspended ? "warn" : "good",
      timestamp: mission?.state?.last_preview_refresh_at || nowTimestamp,
      screenshotFrames: [
        {
          id: "frame-latest",
          label: "Latest",
          path: screenshotPath,
          thumbnailPath: screenshotPath,
          timestamp: mission?.state?.last_preview_refresh_at || nowTimestamp,
        },
        {
          id: "frame-previous",
          label: "Previous",
          path: mission?.state?.previous_screenshot_path || (previewMode === "live" ? "" : "screenshots/previous.png"),
          thumbnailPath: mission?.state?.previous_screenshot_path || (previewMode === "live" ? "" : "screenshots/previous.png"),
          timestamp: mission?.state?.previous_preview_refresh_at || mission?.updated_at || nowTimestamp,
        },
      ],
      liveEvidence: Boolean(screenshotPath),
    },
    {
      id: liveReviewEventId("verification"),
      kind: "verification",
      label: "Verification",
      title: "Test and gate checks",
      detail: verificationStep,
      tone: asList(mission?.state?.verification_failures).length > 0 ? "bad" : "warn",
      timestamp: mission?.state?.last_verification_at || nowTimestamp,
      tests:
        asList(mission?.proof?.passed_checks).length > 0
          ? asList(mission?.proof?.passed_checks).slice(0, 4)
          : ["python -m compileall -q src", "frontend build pending"],
      deepLink: { type: "drawer", drawerId: "proof" },
      liveEvidence: Boolean(
        mission?.state?.last_verification_at ||
          asList(mission?.state?.verification_failures).length > 0 ||
          asList(mission?.proof?.passed_checks).length > 0 ||
          asList(mission?.proof?.failed_checks).length > 0,
      ),
    },
    {
      id: liveReviewEventId("image-playground"),
      kind: "image_playground",
      label: "Image Playground",
      title: "Provider route, queue timeline, and layer handoff",
      detail: imageArtifacts.length > 0 ? `Artifacts: ${imageArtifacts.join(" · ")}` : "Awaiting generated image artifacts",
      tone: imageArtifacts.length > 0 ? "good" : "neutral",
      timestamp: mission?.state?.last_image_event_at || nowTimestamp,
      queueTimeline: ["queued", "provider", "layer_handoff", "artifact", "verified"],
      providerEvents: ["provider_selected", "image_generated", "artifact_registered"],
      layerHandoff: ["prompt_layer", "render_layer", "artifact_layer"],
      generatedImages:
        imageArtifacts.length > 0
          ? imageArtifacts.map(path => ({ path, label: path.split("/").slice(-1)[0] || "artifact" }))
          : previewMode === "live"
            ? []
            : [{ path: "screenshots/latest.png", label: "latest.png" }],
      artifactPaths: imageArtifacts,
      liveEvidence: imageArtifacts.length > 0,
    },
    {
      id: liveReviewEventId("operator-followup"),
      kind: "operator_followup",
      label: "Operator follow-up",
      title: "Messages and acknowledgements",
      detail:
        asList(mission?.state?.operator_notes).length > 0
          ? `${asList(mission?.state?.operator_notes).length} follow-up note(s) recorded`
          : "No operator follow-up message recorded yet",
      tone: asList(mission?.state?.operator_notes).length > 0 ? "good" : "neutral",
      timestamp: mission?.state?.last_operator_note_at || nowTimestamp,
      operatorMessages: asList(mission?.state?.operator_notes).slice(0, 3),
      acknowledgedBy: asList(mission?.state?.operator_acks).slice(0, 3),
      liveEvidence: asList(mission?.state?.operator_notes).length > 0,
    },
    {
      id: liveReviewEventId("progress-window"),
      kind: "progress_update",
      label: "10-20 min update",
      title: "Periodic progress snapshot",
      detail:
        mission
          ? `Changed: ${missionFiles[0] || "none"} · Blocker: ${asList(mission?.state?.verification_failures)[0] || "none"} · Next: ${deriveNextCheckpoint(mission)}`
          : "Progress updates appear every 10-20 minutes once a mission is running.",
      tone: mission ? "warn" : "neutral",
      timestamp: progressWindow || nowTimestamp,
      cadenceMinutes: "10-20",
      cadenceState: progressCadenceState,
      cadenceAgeMinutes: progressWindowAgeMinutes,
      progressUpdate: {
        changed: missionFiles[0] || "none",
        blocker: asList(mission?.state?.verification_failures)[0] || "none",
        tests:
          asList(mission?.proof?.passed_checks).length > 0
            ? mission.proof.passed_checks.slice(0, 2).join(" · ")
            : "pending",
        next: mission ? deriveNextCheckpoint(mission) : "Start mission",
      },
      selectedSkills: plannerSelectedSkills,
      plannerRules,
      designPrompts: plannerDesignPrompts,
      nextIdea: plannerNextIdea,
      structuredFeedbackReceipt,
      liveEvidence: Boolean(progressWindow),
    },
    {
      id: liveReviewEventId("runtime-activity"),
      kind: "runtime_activity",
      label: "Runtime activity",
      title: "Recent tool and lane actions",
      detail:
        runtimeActivitySignals.length > 0
          ? runtimeActivitySignals.join(" · ")
          : "No runtime activity stream captured yet.",
      tone: runtimeActivitySignals.length > 0 ? "good" : "neutral",
      timestamp: asList(snapshot?.activity)[0]?.timestamp || nowTimestamp,
      runtimeActivity: runtimeActivitySignals,
      deepLink: { type: "drawer", drawerId: "context" },
      liveEvidence: runtimeActivitySignals.length > 0,
    },
    {
      id: liveReviewEventId("continuation-supervisor"),
      kind: "continuation_supervisor",
      label: "Internal supervisor",
      title: "Immediate continuation reconcile",
      detail: `State ${titleizeToken(continuationSupervisor.state)} · dispatch window ${continuationSupervisor.expectedDispatchWindowMinutes}m`,
      tone:
        continuationSupervisor.state === "failed" || continuationSupervisor.state === "stale"
          ? "bad"
          : continuationSupervisor.state === "queued"
            ? "warn"
            : "good",
      timestamp: continuationSupervisor.lastCompletionAt || nowTimestamp,
      continuationSupervisor,
      selectedSkills: continuationSupervisor.routePreservation.selectedSkills,
      designPrompts: continuationSupervisor.routePreservation.designPrompts,
      nextIdea: continuationSupervisor.routePreservation.nextIdea,
      structuredFeedbackReceipt,
      deepLink: { type: "drawer", drawerId: "context" },
      liveEvidence: Boolean(mission),
    },
    {
      id: liveReviewEventId("mission-watchdog"),
      kind: "mission_watchdog",
      label: "External watchdog",
      title: "Cross-mission loop watchdog",
      detail:
      missionWatchdog.issueCount > 0
          ? `${missionWatchdog.issueCount} issue(s) across ${missionWatchdog.missionCount} mission(s) · next: ${missionWatchdog.nextAction}`
          : `All ${missionWatchdog.missionCount} mission(s) passed the external watchdog scan · loop ${missionWatchdog.loopActive ? "active" : "needs attention"} · ${missionWatchdog.artifactReady} artifact scope(s) ready.`,
      tone: missionWatchdog.bad > 0 ? "bad" : missionWatchdog.warn > 0 ? "warn" : "good",
      timestamp: missionWatchdog.checkedAt,
      missionWatchdog,
      deepLink: { type: "drawer", drawerId: "context" },
      liveEvidence: Boolean(missionWatchdogRaw.schema || missionWatchdogRaw.checkedAt || missionWatchdogIssues.length),
    },
    {
      id: liveReviewEventId("replay"),
      kind: "replay_marker",
      label: "Replay marker",
      title: "Rewind and timelapse snapshot",
      detail:
        asList(builderBoard?.nexuses || builderBoard?.nexus).length > 0
          ? `${asList(builderBoard?.nexuses || builderBoard?.nexus).length} timeline marker(s) available for replay`
          : "No timeline markers yet",
      tone: asList(builderBoard?.nexuses || builderBoard?.nexus).length > 0 ? "good" : "neutral",
      timestamp: nowTimestamp,
      replayMarkers: asList(builderBoard?.nexuses || builderBoard?.nexus)
        .slice(0, 3)
        .map((item, index) => ({
          id: item?.id || `marker-${index}`,
          label: item?.title || item?.label || "marker",
          timestamp: item?.updatedAt || item?.timestamp || nowTimestamp,
          snapshotPath: item?.artifactPath || item?.path || screenshotPath,
          frameId: index === 0 ? "frame-latest" : "frame-previous",
          deepLink: {
            proofTarget: item?.proofId || mission?.id || "",
            threadTarget: item?.threadId || mission?.mission_id || mission?.id || "",
          },
        })),
      liveEvidence: asList(builderBoard?.nexuses || builderBoard?.nexus).length > 0,
    },
  ];
  const liveEvidenceEvents = previewMode === "live"
    ? events.filter(item => item.liveEvidence)
    : events;

  const annotationReadiness = {
    enabled: true,
    blocks: [
      {
        id: "anno-home-hero",
        label: "Hero layout",
        severity: "high",
        note: "CTA stack overlaps in compact width; preserve hierarchy and spacing rhythm.",
        recoveryAction: "Reduce heading width, keep CTA buttons stacked with safe gap.",
        page: "landing",
        rectangle: { x: 6, y: 14, width: 88, height: 34, layer: "preview" },
      },
      {
        id: "anno-right-panel",
        label: "Live panel card",
        severity: "medium",
        note: "Queue chips become dense during long runs; trim microcopy before wrapping.",
        recoveryAction: "Collapse details under a disclosure after 3 visible lines.",
        page: "review-panel",
        rectangle: { x: 54, y: 48, width: 42, height: 42, layer: "live-review" },
      },
      {
        id: "anno-operator-pin",
        label: "Operator follow-up pin",
        severity: "low",
        note: "Acknowledge follow-up quickly so mission thread and review panel stay in sync.",
        recoveryAction: "Auto-add acknowledgement row after send succeeds.",
        page: "operator-thread",
        pin: { x: 80, y: 26, layer: "sidebar" },
      },
    ],
  };

  return {
    headline: "Live UI review",
    summary:
      "Pick a visible block, annotate what feels wrong, and push the feedback back into the mission without leaving Builder.",
    statusLine:
      previewMode === "live"
        ? `${isRefreshing ? "Refreshing" : "Live"} · ${liveSyncSeconds === "off" ? "manual sync" : `${liveSyncSeconds}s sync`}`
        : `${previewLabel(previewMode, snapshot?.previewMeta)} · repeatable review`,
    targets: reviewTargets.slice(0, 6),
    previewUrl,
    previewActionUrl: rawPreviewUrl || controlPreviewUrl,
    previewSourceLabel,
    previewSourceDetail,
    hasServedLivePreview,
    compareHint:
      builderBoard.activeConversations.length > 0
        ? "Use live review targets to steer the active mission, then jump back through nexuses if the direction changes."
        : previewMode === "live"
          ? "No live review targets are available yet; the panel waits for current NAS mission evidence."
          : "Use local review data now, then launch the UI review loop once a real mission is active.",
    events: liveEvidenceEvents,
    annotationReadiness,
    plannerProof: {
      selectedSkills: plannerSelectedSkills,
      plannerRules,
      designPrompts: plannerDesignPrompts,
      nextIdea: plannerNextIdea,
      structuredFeedbackReceipt,
      latestStructuredFeedbackReceipt,
      decisionInfluence,
    },
    continuationSupervisor,
    missionWatchdog,
  };
}

function deriveMissionActivityPulse({ mission, workspace, snapshot, pendingQuestions, pendingApprovals }) {
  const delegatedSessions = asList(mission?.delegated_runtime_sessions).filter(
    item => !["completed", "failed", "stopped"].includes(String(item?.status || "").toLowerCase()),
  );
  const approvals = asList(mission?.proof?.pending_approvals).length + asList(pendingApprovals).length;
  const questions = asList(pendingQuestions).length;
  const verificationFailures = asList(mission?.state?.verification_failures).length;
  const changedFiles = deriveChanged(mission, workspace).slice(0, 5);
  const toolMentions = uniq([
    ...asList(mission?.action_history).map(item => item?.proposal?.tool_id || item?.proposal?.toolId || ""),
    ...delegatedSessions.map(item => item?.runtime_id || ""),
    ...asList(snapshot?.activity)
      .slice(0, 20)
      .map(item => {
        const message = String(item?.message || "").toLowerCase();
        if (message.includes("browser")) return "browser";
        if (message.includes("terminal")) return "terminal";
        if (message.includes("pytest") || message.includes("test")) return "tests";
        if (message.includes("build")) return "build";
        return "";
      }),
  ]).slice(0, 6);
  const current = deriveCurrentTask(mission);
  const next = deriveNextCheckpoint(mission);
  const timeline = asList(snapshot?.activity).slice(0, 8);
  const stage =
    mission?.state?.status === "running"
      ? "Executing"
      : mission?.state?.status === "completed"
        ? "Completed"
        : mission?.state?.status === "failed"
          ? "Failed"
          : approvals > 0 || questions > 0
            ? "Awaiting operator"
            : delegatedSessions.length > 0
              ? "Delegating"
              : "Planning";
  const tone =
    mission?.state?.status === "failed"
      ? "bad"
      : verificationFailures > 0 || approvals > 0 || questions > 0
        ? "warn"
        : mission?.state?.status === "completed"
          ? "good"
          : "neutral";

  return {
    stage,
    tone,
    current,
    next,
    changedFiles,
    toolMentions,
    delegatedCount: delegatedSessions.length,
    approvals,
    questions,
    verificationFailures,
    backgroundSummary:
      delegatedSessions[0]?.detail ||
      delegatedSessions[0]?.last_event ||
      (delegatedSessions.length > 0 ? `${delegatedSessions.length} delegated lane(s) active.` : "No delegated lane active."),
    timeline: timeline.map(item => ({
      label: titleizeToken(item?.kind || "activity"),
      message: item?.message || "Activity event",
      timestamp: item?.timestamp || "",
    })),
  };
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
  const confidence = deriveConfidenceSurface({
    mission,
    snapshot,
    setupHealth,
    queueItems,
    pendingQuestions,
    pendingApprovals,
  });
  const profileStudio = deriveProfileStudio(snapshot, workspace, profileId, profileParams);
  const serviceStudio = deriveServiceStudio(workspace, setupHealth);
  const skillStudio = deriveSkillStudio(snapshot, workspace);
  const workflowStudio = deriveWorkflowStudio(snapshot, profileId);
  const builderOps = deriveBuilderOps(workspace);
  const stateAudit = deriveStateAudit({ mission, setupHealth });
  const qualityRoadmap = deriveQualityRoadmap({
    confidence,
    mission,
    setupHealth,
    serviceStudio,
    skillStudio,
    workflowStudio,
    builderOps,
  });
  const builderBoard = deriveBuilderBoard({ mission, workspace, snapshot, confidence, uiMode });
  const tutorialStudio = deriveTutorialStudio({
    mission,
    snapshot,
    setupHealth,
    profileId,
    workflowStudio,
  });
  const recommendationStudio = deriveRecommendationStudio({
    mission,
    workspace,
    setupHealth,
    serviceStudio,
    skillStudio,
    workflowStudio,
    qualityRoadmap,
    builderBoard,
  });
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
    {
      title: "Confidence",
      items: [
        {
          label: "1.0 progress",
          value: confidence.label,
          note: confidence.phase,
        },
        {
          label: "Release status",
          value: confidence.releaseStatus,
          note: confidence.requiredGateSummary.label,
        },
        {
          label: "Quality score",
          value: `${confidence.qualityScore}%`,
          note: confidence.nextActions[0] || "No blocker reported.",
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
  const activeAuditCount = stateAudit.filter(item => item.state === "active").length;
  const requiredGateFailures = confidence.gates.filter(
    item => item.required && item.passed === false,
  ).length;
  const builderReviewCount =
    featureTruth.notReady.length +
    activeAuditCount +
    asInt(serviceStudio.summary.needsAttentionCount) +
    asInt(skillStudio.summary.needsTestCount) +
    qualityRoadmap.nextCount +
    qualityRoadmap.blockedCount +
    requiredGateFailures;
  const activityPulse = deriveMissionActivityPulse({
    mission,
    workspace,
    snapshot,
    pendingQuestions,
    pendingApprovals,
  });

  return {
    topBar: {
      liveStatus,
      environmentLabel: deriveEnvironmentLabel(setupHealth, mission, workspace),
      inboxCount:
        queueItems.filter(item => item.tone === "warn" || item.tone === "bad").length +
        asList(inbox).length,
      primaryAction,
      confidence,
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
      recommendedAction: primaryAction.label,
      confidenceLabel: confidence.label,
      confidencePhase: confidence.phase,
      qualityRoadmapHeadline: qualityRoadmap.headline,
      recommendedWorkflow:
        workflowStudio?.recommended?.label || "Long-Run Agent Session",
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
            {
              label: `${confidence.score}% confidence`,
              tone: confidence.tone,
            },
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
      activityPulse,
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
        operatorValueFeedback: mission?.state?.operator_value_feedback || {},
      },
      context: {
        label: "Context",
        count: contextGroups.reduce((total, group) => total + group.items.length, 0),
        groups: contextGroups,
      },
      builder: {
        label: "Builder review",
        reviewCount: builderReviewCount,
        confidence,
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
        tutorialStudio,
        recommendationStudio,
        liveReviewStudio: deriveLiveReviewStudio({
          mission,
          workspace,
          snapshot,
          previewMode,
          liveSyncSeconds,
          liveSyncSuspended,
          lastPushReason,
          isRefreshing,
          builderBoard,
        }),
        profileStudio,
        serviceStudio,
        skillStudio,
        workflowStudio,
        gitActions: builderOps.gitActions,
        validationActions: builderOps.validationActions,
        qualityRoadmap,
        featureTruth,
        stateAudit,
        events: events.slice(0, 10),
        board: builderBoard,
        activityPulse,
        mode: uiMode,
      },
    },
  };
}
