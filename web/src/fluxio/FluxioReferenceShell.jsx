import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  BookOpen,
  Bot,
  Check,
  ChevronDown,
  CircleCheckBig,
  CircleHelp,
  CircleDashed,
  Clock3,
  Code2,
  CreditCard,
  Database,
  Edit3,
  Expand,
  FileText,
  Filter,
  FolderOpen,
  Globe,
  Grid2x2,
  Hammer,
  History,
  Home,
  Laptop,
  LayoutGrid,
  Mic,
  Moon,
  Monitor,
  MoreHorizontal,
  NotebookPen,
  Palette,
  Paperclip,
  Play,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Shield,
  Smartphone,
  Sparkles,
  Star,
  SquareTerminal,
  SunMedium,
  Users,
  WandSparkles,
} from "lucide-react";

import { RuntimeOperationsPanel } from "./RuntimeOperationsPanel.jsx";

const ImagePlaygroundSurface = lazy(() =>
  import("./ImagePlayground.jsx").then(module => ({
    default: module.ImagePlaygroundSurface,
  })),
);

function cx(...values) {
  return values.filter(Boolean).join(" ");
}

function asList(value) {
  return Array.isArray(value) ? value : [];
}

function asRecord(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function artifactRepairCountFromGoalRows(rows) {
  for (const row of asList(rows)) {
    const text = [
      row?.label,
      row?.title,
      row?.statusLabel,
      row?.detail,
      row?.evidence,
      row?.nextAction,
    ]
      .map(value => String(value || ""))
      .join(" ");
    const match = text.match(/\b(\d+)\s+artifact repair mission/i);
    if (match) return Number(match[1] || 0);
  }
  return 0;
}

function useVirtualWindow(items, { itemHeight = 96, viewportHeight = 440, overscan = 4 } = {}) {
  const [scrollTop, setScrollTop] = useState(0);
  const list = asList(items);
  const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
  const visibleCount = Math.ceil(viewportHeight / itemHeight) + overscan * 2;
  const endIndex = Math.min(list.length, startIndex + visibleCount);
  return {
    totalCount: list.length,
    items: list.slice(startIndex, endIndex),
    onScroll: event => setScrollTop(event.currentTarget.scrollTop),
    topPadding: startIndex * itemHeight,
    bottomPadding: Math.max(0, (list.length - endIndex) * itemHeight),
    viewportHeight,
  };
}

function uniq(values) {
  return Array.from(new Set(asList(values).filter(Boolean)));
}

function titleizeToken(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, char => char.toUpperCase());
}

const ANTI_DRIFT_BLOCKED_KINDS = new Set([
  "delegated_runtime_completed_unreconciled",
  "delegated_runtime_process_gone",
  "mission_blocked_or_failed",
  "runtime_budget_exhausted",
  "runtime_cycle_state_mismatch",
  "stale_queue_blocker",
]);

const ANTI_DRIFT_DRIFT_KINDS = new Set([
  "delegated_runtime_completed_unreconciled",
  "running_planner_loop_idle",
  "stale_running_mission",
  "stale_runtime_heartbeat",
]);

const ANTI_DRIFT_ROUTE_KINDS = new Set([
  "route_contract_incomplete",
  "runtime_cycle_state_mismatch",
]);

const ANTI_DRIFT_PROOF_KINDS = new Set([
  "planned_scope_artifacts_not_ready",
]);

function issueKind(issue) {
  return String(issue?.kind || issue?.type || "").trim().toLowerCase();
}

function issueSeverity(issue) {
  const severity = String(issue?.severity || "info").trim().toLowerCase();
  return ["bad", "warn", "info"].includes(severity) ? severity : "info";
}

function deriveMissionAntiDriftGuard(missionWatchdog, { isLiveBackend = false } = {}) {
  const report = asRecord(missionWatchdog);
  const summary = asRecord(report.summary);
  const hasLiveEvidence = Boolean(isLiveBackend && report.schema === "fluxio.mission_watchdog.v1");
  const issueSources = [
    ...asList(report.issues),
    ...asList(asRecord(report.problemRegistry).problems),
  ];
  const seen = new Set();
  const issues = issueSources.filter((issue, index) => {
    const item = asRecord(issue);
    const key = item.problemId || item.issueId || `${item.missionId || item.mission_id || "mission"}:${issueKind(item)}:${index}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  const countKinds = kinds => issues.filter(issue => kinds.has(issueKind(issue))).length;
  const blockedLoopCount = countKinds(ANTI_DRIFT_BLOCKED_KINDS);
  const driftRiskCount = countKinds(ANTI_DRIFT_DRIFT_KINDS);
  const routeMismatchCount = countKinds(ANTI_DRIFT_ROUTE_KINDS);
  const explicitProofGapCount = countKinds(ANTI_DRIFT_PROOF_KINDS);
  const proofGapCount =
    explicitProofGapCount +
    Number(summary.artifactMissing || report.artifactMissing || 0) +
    Number(summary.artifactPartial || report.artifactPartial || 0);
  const bad = Number(report.bad ?? summary.bad ?? issues.filter(issue => issueSeverity(issue) === "bad").length);
  const warn = Number(report.warn ?? summary.warn ?? issues.filter(issue => issueSeverity(issue) === "warn").length);
  const firstIssue = issues[0] || null;
  const watchdogNextAction =
    firstIssue?.firstRepairStep ||
    firstIssue?.firstStep ||
    report.nextAction ||
    "No watchdog issues found. Keep Hermes active.";
  const nextAction = hasLiveEvidence
    ? watchdogNextAction
    : "Refresh live watchdog evidence before claiming monitoring is clear.";

  let status = "clear";
  let tone = "good";
  let title = "Mission can continue";
  if (!hasLiveEvidence) {
    status = "waiting";
    tone = "warn";
    title = "Waiting for live watchdog evidence";
  } else if (blockedLoopCount > 0 || bad > 0) {
    status = "intervention";
    tone = "bad";
    title = "Intervention required before continuing";
  } else if (driftRiskCount > 0 || routeMismatchCount > 0 || proofGapCount > 0 || warn > 0) {
    status = "attention";
    tone = "warn";
    title = "Guard sees drift risk";
  }

  const signal = (id, label, count, detail) => {
    if (!hasLiveEvidence) {
      return {
        id,
        label,
        count,
        status: "pending",
        detail: "Awaiting live watchdog report.",
      };
    }
    return {
      id,
      label,
      count,
      status: count > 0 ? (id === "blocked_loop" ? "bad" : "warn") : "clear",
      detail,
    };
  };

  return {
    status,
    tone,
    title,
    liveEvidence: hasLiveEvidence,
    primaryRuntimeLane: "hermes",
    fallbackRuntimeLane: "openclaw",
    nextAction,
    firstIssue,
    issueCount: Number(report.issueCount ?? summary.issueCount ?? issues.length),
    signals: [
      signal("blocked_loop", "Blocked loop", blockedLoopCount, blockedLoopCount ? "Runtime cannot advance without repair." : "No hard blocker reported."),
      signal("original_intent", "Original intent", driftRiskCount, driftRiskCount ? "Planner/runtime movement is stale or idle." : "No active drift signal."),
      signal("route_mismatch", "Route mismatch", routeMismatchCount, routeMismatchCount ? "Planner, executor, or verifier route contract needs repair." : "Hermes route contract looks aligned."),
      signal("fake_proof", "Fake proof", proofGapCount, proofGapCount ? "Completion proof is missing or partial." : "No proof gap reported."),
    ],
  };
}

function eventTargetIsInteractive(event) {
  const target = event?.target;
  return Boolean(
      target &&
      typeof target.closest === "function" &&
      target.closest("button,a,input,textarea,select,summary"),
  );
}

const PUBLIC_LAUNCH_PROOF_GROUPS = [
  {
    id: "launcher",
    label: "Launcher package",
    checkIds: ["launcher_package_current", "package_public_entrypoint_declared"],
    detail: "npx-style command, package files, and built web assets are packed.",
  },
  {
    id: "public-web",
    label: "Public web",
    checkIds: ["public_web_reachable", "public_web_current"],
    detail: "GitHub Pages is reachable and must match the current source state.",
  },
  {
    id: "private-nas",
    label: "Private NAS",
    checkIds: ["private_nas_live_reachable"],
    detail: "Tailscale web control is reachable and login-protected.",
  },
  {
    id: "release-packet",
    label: "Release packet",
    checkIds: ["release_packet_attached", "publication_manifest_ready", "attachment_manifest_integrity"],
    detail: "Release candidate, manifest, and attachments are present and verified.",
  },
  {
    id: "external-publication",
    label: "External publication",
    checkIds: ["external_publication_proven"],
    detail: "A public npm, signed installer, or GitHub release receipt exists.",
  },
];

function publicLaunchProofSteps(readiness) {
  const checks = asList(readiness?.checks);
  const checkById = new Map(checks.map(item => [String(item?.checkId || ""), item]));
  const missing = new Set(asList(readiness?.missing).map(item => String(item || "")));
  const blockers = asList(readiness?.blockers);
  return PUBLIC_LAUNCH_PROOF_GROUPS.map(group => {
    const groupChecks = group.checkIds.map(checkId => checkById.get(checkId)).filter(Boolean);
    const failedChecks = group.checkIds.filter(checkId => {
      const check = checkById.get(checkId);
      return missing.has(checkId) || (check && check.passed === false);
    });
    const blocker = blockers.find(item => group.checkIds.includes(String(item?.checkId || item?.id || item?.check || "")));
    const passed = groupChecks.length > 0 && group.checkIds.every(checkId => checkById.get(checkId)?.passed === true);
    const tone = passed ? "good" : failedChecks.length > 0 || blocker ? "warn" : "bad";
    const firstFailed = failedChecks.map(checkId => checkById.get(checkId)).find(Boolean);
    return {
      ...group,
      tone,
      state: passed ? "Ready" : failedChecks.length > 0 || blocker ? "Needs proof" : "Not checked",
      detail: firstFailed?.details || blocker?.details || blocker?.detail || group.detail,
      checks: groupChecks,
      failedChecks,
    };
  });
}

function clampPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return Math.max(0, Math.min(100, Math.round(number)));
}

function progressPercentValue(value) {
  if (typeof value === "string" && value.trim().endsWith("%")) {
    return clampPercent(value.trim().slice(0, -1));
  }
  return clampPercent(value);
}

function progressWidth(value) {
  if (value == null || value === "") return null;
  const percent = progressPercentValue(value);
  return percent == null ? null : `${percent}%`;
}

function timestampLabel(value) {
  if (!value) return "";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return String(value);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function isLowSignalAgentMessage(message) {
  const label = String(message?.label || message?.roleLabel || "").toLowerCase();
  const title = String(message?.title || "").toLowerCase();
  return (
    label.includes("mission.runtime_cycle") ||
    title.includes("control cycle finished with status running") ||
    title.includes("delegated runtime heartbeat")
  );
}

function isRuntimeOutputAgentMessage(message) {
  const label = String(message?.label || message?.roleLabel || "").toLowerCase();
  const detailText = [
    message?.detail,
    message?.message,
    message?.content,
    message?.technicalDetail,
  ]
    .map(value => String(value || "").toLowerCase())
    .join("\n");
  return (
    detailText.includes("runtime output:") ||
    detailText.includes("raw action output") ||
    (label.includes("hermes session transcript") && detailText.includes("runtime output:"))
  );
}

function isProofArtifactAgentMessage(message) {
  const label = String(message?.label || message?.roleLabel || "").toLowerCase();
  const kind = String(message?.kind || message?.messageKind || "").toLowerCase();
  const id = String(message?.id || "").toLowerCase();
  const text = [
    message?.title,
    message?.detail,
    message?.technicalDetail,
    ...asList(message?.chips),
  ]
    .map(value => String(value || "").toLowerCase())
    .join(" ");
  return Boolean(
    kind === "proof" ||
      kind.includes("artifact") ||
      label.includes("runtime output artifact") ||
      label.includes("proof artifact") ||
      id.includes("runtime-artifact") ||
      text.includes("mission_artifact_runtime_output") ||
      text.includes("runtime_output.txt") ||
      text.includes("nas audit fluxio.live_nas_system_audit_snapshot"),
  );
}

function isOperatorFollowUpAgentMessage(message) {
  if (!message || isProofArtifactAgentMessage(message) || isRuntimeOutputAgentMessage(message)) {
    return false;
  }
  const label = String(message?.label || message?.roleLabel || "").toLowerCase();
  const kind = String(message?.kind || message?.messageKind || "").toLowerCase();
  const id = String(message?.id || "").toLowerCase();
  const text = [
    message?.title,
    message?.detail,
    message?.message,
    message?.content,
  ]
    .map(value => String(value || "").trim())
    .filter(Boolean)
    .join("\n");
  if (!text) {
    return false;
  }
  if (isGeneratedContextFollowUpText(text)) {
    return false;
  }
  return Boolean(
    label === "mission.follow_up" ||
      label === "operator.followup" ||
      label === "operator.follow_up" ||
      label === "operator.message" ||
      kind === "mission.follow_up" ||
      kind === "operator.followup" ||
      kind === "operator.follow_up" ||
      kind === "operator.message" ||
      id.includes(":mission.follow_up:") ||
      id.includes(":operator.followup:"),
  );
}

function isGeneratedContextFollowUpText(text) {
  const normalizedText = String(text || "").toLowerCase().replace(/\s+/g, " ").trim();
  const contextMarkers = [
    "active rule set:",
    "workspace:",
    "workspace path:",
    "mission context:",
    "mission id:",
    "rule intent:",
    "rule set intent:",
    "approval-sensitive actions:",
    "active skills:",
    "route for ",
    "runtime focus:",
    "attachment metadata:",
    "do not restate this routing/context block",
  ];
  const markerCount = contextMarkers.filter(marker => normalizedText.includes(marker)).length;
  return Boolean(
    normalizedText.startsWith("you are replying inside fluxio agent live") ||
    normalizedText.startsWith("you are hermes, the runtime answering a fluxio-selected mission follow-up") ||
      normalizedText.startsWith("mission context:") ||
      markerCount >= 2 ||
      (
        markerCount >= 1 &&
        (
          normalizedText.includes("do not restate this routing/context block") ||
          normalizedText.includes("provided mission context") ||
          normalizedText.includes("normal chat behavior")
        )
      ) ||
      normalizedText.startsWith("active rule set:") ||
      normalizedText.startsWith("workspace:") ||
      normalizedText.startsWith("workspace path:") ||
      normalizedText.startsWith("mission id:") ||
      normalizedText.startsWith("mission:") ||
      normalizedText.startsWith("rule intent:") ||
      normalizedText.startsWith("rule set intent:") ||
      normalizedText.startsWith("rule-set route for") ||
      normalizedText.startsWith("approval-sensitive actions:") ||
      normalizedText.startsWith("active skills:") ||
      normalizedText.startsWith("route preference for") ||
      normalizedText.startsWith("route for ") ||
      normalizedText.startsWith("runtime focus:") ||
      normalizedText.startsWith("runtime preference:") ||
      normalizedText.startsWith("attachment metadata:") ||
      normalizedText.startsWith("do not restate this routing/context block"),
  );
}

function isVerificationProbeDialogueText(text) {
  const normalizedText = String(text || "").toLowerCase().replace(/\s+/g, " ").trim();
  return Boolean(
    normalizedText.startsWith("in one sentence, tell me what you can verify about this fluxio agent live mission thread") ||
      normalizedText.startsWith("in one sentence, what can you verify about this f1 telemetry agent live thread") ||
      (
        normalizedText.startsWith("i can verify") &&
        normalizedText.includes("hermes cli agent") &&
        normalizedText.includes("agent live mission thread")
      ) ||
      (
        normalizedText.startsWith("i can verify") &&
        normalizedText.includes("thread is specifically about f1 telemetry") &&
        normalizedText.includes("workspace")
      ) ||
      (
        normalizedText.startsWith("i can verify only that this is the first turn of the thread") &&
        normalizedText.includes("no prior mission state")
      )
  );
}

function isTrustedLiveDialogueSource(message) {
  const source = String(message?.source || "").trim().toLowerCase();
  return [
    "operator-submitted",
    "backend-model-message",
    "backend-runtime-reply",
    "runtime-compartment",
    "runtime_compartment",
  ].includes(source);
}

function hasTrustedRuntimeReply(messages) {
  return asList(messages).some(message => {
    const role = String(message?.role || "").toLowerCase();
    const source = String(message?.source || "").trim().toLowerCase();
    return role === "assistant" && ["backend-model-message", "backend-runtime-reply", "runtime-compartment", "runtime_compartment"].includes(source);
  });
}

function isHermesDialogueReplyAgentMessage(message) {
  if (!message || isProofArtifactAgentMessage(message) || isRuntimeOutputAgentMessage(message) || isOperatorFollowUpAgentMessage(message)) {
    return false;
  }
  const label = String(message?.label || message?.roleLabel || "").toLowerCase();
  const text = String(message?.title || message?.detail || message?.message || message?.content || "").trim();
  if (!text || text.length < 24 || isVerificationProbeDialogueText(text)) {
    return false;
  }
  if (!(label.includes("hermes runtime output") || label.includes("hermes reply"))) {
    return false;
  }
  if (label.includes("lane_control") || label.includes("lane control")) {
    return false;
  }
  if (/^\s*(?:[-*]|\d+[.)])\s+/.test(text)) {
    return false;
  }
  if (/\b(?:pass|fail|wait|status)\s*:|runtime output:|raw action output|proof_digest|delivery_receipts?|nas audit|python -m|lane control receipt|recorded runtime for planner|\.json\b|\.py\b/i.test(text)) {
    return false;
  }
  return /[.!?]/.test(text);
}

function isAgentDialogueTurn(message) {
  if (!message || isProofArtifactAgentMessage(message)) {
    return false;
  }
  const role = String(message?.role || "").toLowerCase();
  const label = String(message?.label || message?.roleLabel || "").toLowerCase();
  const kind = String(message?.kind || message?.messageKind || "").toLowerCase();
  const text = [
    message?.title,
    message?.detail,
    message?.message,
    message?.content,
  ]
    .map(value => String(value || "").trim())
    .filter(Boolean)
    .join("\n");
  if (
    !text ||
    isVerificationProbeDialogueText(text) ||
    isControlRoomBookkeepingAgentMessage(message) ||
    isSyntheticAgentOverviewMessage(message)
  ) {
    return false;
  }
  if (isGeneratedContextFollowUpText(text)) {
    return false;
  }
  if (isMissionEventAgentMessage(message)) {
    return false;
  }
  if (message?.source && !isTrustedLiveDialogueSource(message)) {
    return false;
  }
  if (isOperatorFollowUpAgentMessage(message)) {
    return true;
  }
  if (isHermesDialogueReplyAgentMessage(message)) {
    return true;
  }
  if (message?.conversationTurn === true || kind === "dialogue" || kind === "chat") {
    return true;
  }
  if (role === "user" || role === "operator") {
    return true;
  }
  return Boolean(
    message?.chatPreferred === true &&
      !message?.traceOnly &&
      !label.includes("runtime output artifact") &&
      !label.includes("control-room") &&
      !label.includes("provider route") &&
      !label.includes("runtime heartbeat"),
  );
}

function isMissionEventAgentMessage(message) {
  if (!message || isOperatorFollowUpAgentMessage(message) || isHermesDialogueReplyAgentMessage(message)) {
    return false;
  }
  const label = String(message?.label || message?.roleLabel || "").toLowerCase();
  const kind = String(message?.kind || message?.messageKind || "").toLowerCase();
  const title = String(message?.title || "").toLowerCase();
  const detail = String(message?.detail || message?.message || message?.content || "").toLowerCase();
  const text = [title, detail].filter(Boolean).join("\n");
  return Boolean(
    (label.startsWith("mission.") || kind.startsWith("mission.")) &&
      !label.includes("follow") &&
      !kind.includes("follow")
  ) || Boolean(
    label.includes("action_history") ||
      label.includes("runtime evidence") ||
      label.includes("runtime budget") ||
      label.includes("resume dispatched") ||
      title.includes("runtime budget") ||
      title.includes("resume was dispatched") ||
      title.includes("recorded hermes runtime evidence") ||
      text.includes("completed with exit code") ||
      text.includes("moved to a dedicated isolated task lane")
  );
}

function isRuntimeActivityAgentMessage(message) {
  if (!message || isAgentDialogueTurn(message) || isProofArtifactAgentMessage(message)) {
    return false;
  }
  const label = String(message?.label || message?.roleLabel || "").toLowerCase();
  const kind = String(message?.kind || message?.messageKind || "").toLowerCase();
  return Boolean(
    kind === "activity" ||
      label.includes("hermes session transcript") ||
      label.includes("planner") ||
      label.includes("runtime") ||
      message?.processMessage ||
      message?.technicalDetail,
  );
}

function runtimeOutputText(message) {
  const reportSourceText = [
    message?.detail,
    message?.message,
    message?.content,
  ]
    .map(value => String(value || "").trim())
    .filter(Boolean)
    .join("\n");
  const match = reportSourceText.match(/(?:runtime output|raw action output)\s*:\s*([\s\S]+)/i);
  const rawBody = String(match?.[1] || "").trim();
  if (!rawBody) return "";
  return rawBody
    .split(/\s+[·]\s+(?:Action|Target|Command|Gate|Result|Error|Revision|Active step)\s*:/i)[0]
    .split(/\n\s*\{\s*["{]/)[0]
    .trim();
}

function firstUsefulRuntimeLine(text) {
  return String(text || "")
    .split(/\r?\n/)
    .map(line => line.replace(/^#{1,6}\s*/, "").replace(/^[-*]\s*/, "").trim())
    .find(line =>
      line &&
      !/^objective\s*:/i.test(line) &&
      !/^triggered by step\s*:/i.test(line) &&
      !/^(what changed|concrete verification|live-only inputs|status|runtime output)\b.*:\s*$/i.test(line)
    ) || "";
}

function finalAssistantMessageFromRuntimeOutput(text) {
  const cleaned = String(text || "")
    .replace(/^\s*(?:runtime output|raw action output)\s*:\s*/i, "")
    .replace(/^\s*Mission\s+\S+\s+live runtime output\s*\([^)]+\)\s*/i, "")
    .trim();
  if (/^OpenRuntime returned a real result for this mission\b/i.test(cleaned)) {
    return cleaned;
  }
  if (!cleaned || !/(^|\n)\s*(?:artifact|preview url|route)\s*:/i.test(cleaned)) {
    return "";
  }
  const lines = cleaned
    .split(/\r?\n/)
    .map(line => line.replace(/^[-*]\s*/, "").trim())
    .filter(Boolean);
  const headline =
    lines.find(line =>
      !/^(artifact|preview url|route|command|status)\s*:/i.test(line) &&
        !/^\/volume\d+\//i.test(line) &&
        !/^https?:\/\//i.test(line) &&
        !/^\/api\/artifact\b/i.test(line),
    ) || "";
  const route = lines.find(line => /^route\s*:/i.test(line)) || "";
  const facts = lines
    .filter(line =>
      line !== headline &&
      !/^(artifact|preview url|route|command|status)\s*:/i.test(line) &&
      !/^\/volume\d+\//i.test(line) &&
      !/^https?:\/\//i.test(line) &&
      !/^\/api\/artifact\b/i.test(line),
    )
    .slice(0, 4);
  const parts = [];
  if (headline) {
    parts.push(`OpenRuntime returned a real result for this mission: ${headline}.`);
  } else {
    parts.push("OpenRuntime returned a real result for this mission.");
  }
  if (facts.length) {
    parts.push(`Key output: ${facts.join(" ")}`);
  }
  if (route) {
    parts.push(route);
  }
  return parts.join("\n").trim();
}

function firstMeaningfulNotificationLine(item) {
  const text = [
    item?.agentMessage,
    item?.detail,
    item?.message,
    item?.summary,
    item?.title,
    item?.headline,
    item?.label,
  ]
    .map(value => String(value || "").trim())
    .filter(Boolean)
    .join("\n");
  return text
    .split(/\r?\n/)
    .map(line => line.replace(/^#{1,6}\s*/, "").replace(/^[-*]\s*/, "").trim())
    .find(line =>
      line &&
      !/^mission updates?$/i.test(line) &&
      !/^notification$/i.test(line) &&
      !/^slice$/i.test(line) &&
      !/^update$/i.test(line)
    ) || "";
}

function sanitizeDisplayTitle(value) {
  return String(value || "")
    .replace(/\bsystem-loss\s+improvement\s+mission\b/gi, "system improvement mission")
    .replace(/\bsystem\s+loss\s+improvement\s+mission\b/gi, "system improvement mission")
    .replace(/\bsystem-loss\b/gi, "system gap")
    .replace(/\bsystem\s+loss\b/gi, "system gap");
}

function referenceNotificationId(item, index = 0) {
  const baseId = String(
    item?.id ||
      item?.notificationId ||
      item?.eventId ||
      item?.event_id ||
      [
        item?.missionId || item?.mission_id || "control-room",
        item?.kind || item?.type || "notification",
        item?.createdAt || item?.timestamp || item?.time || index,
        item?.title || item?.headline || item?.message || "",
      ].join(":"),
  ).trim();
  return `${baseId || "notification"}:${index}`;
}

function agentMessageDisplayTitle(message) {
  if (isHermesDialogueReplyAgentMessage(message)) {
    const replyText = String(message?.title || message?.detail || message?.message || message?.content || "").trim();
    return replyText.length > 220 ? `${replyText.slice(0, 217).trim()}...` : replyText || "Hermes reply";
  }
  if (isOperatorFollowUpAgentMessage(message)) {
    const followUpText = String(message?.title || message?.detail || message?.message || message?.content || "")
      .replace(/^follow-up evidence from codex on\s+.*?z:\s*/i, "")
      .trim();
    const firstSentence = followUpText.split(/(?<=[.!?])\s+/)[0] || followUpText;
    return firstSentence.length > 180 ? `${firstSentence.slice(0, 177).trim()}...` : firstSentence || "Operator follow-up";
  }
  const runtimeText = runtimeOutputText(message);
  if (runtimeText) {
    const runtimeTitle = firstUsefulRuntimeLine(runtimeText)
      .replace(/\s+-\s+Objective\s*:\s*[\s\S]*$/i, "")
      .trim();
    if (runtimeTitle) return runtimeTitle;
  }
  return message?.title || message?.label || titleizeToken(message?.role || "agent");
}

function agentMessageDisplayDetail(message) {
  const runtimeText = runtimeOutputText(message);
  if (runtimeText) return runtimeText;
  return message?.detail || message?.content || message?.message || message?.technicalDetail || "";
}

function isControlRoomBookkeepingAgentMessage(message) {
  const label = String(message?.label || message?.roleLabel || "").toLowerCase();
  const title = String(message?.title || "").toLowerCase();
  return (
    label.includes("control-room") ||
    label.includes("provider route truth") ||
    label.includes("runtime heartbeat") ||
    title.includes(" is still cycling") ||
    title.includes("heartbeat")
  );
}

function isRuntimeTranscriptIntegrityWarning(message) {
  const label = String(message?.label || message?.roleLabel || "").toLowerCase();
  const title = String(message?.title || "").toLowerCase();
  return (
    label.includes("runtime transcript integrity") ||
    title.includes("hermes session transcript is not attached")
  );
}

function isSyntheticAgentOverviewMessage(message) {
  const id = String(message?.id || "").toLowerCase();
  const label = String(message?.label || message?.roleLabel || "").trim().toLowerCase();
  return (
    id.startsWith("mission-review-") ||
    label === "mission review" ||
    label === "control-room mission state"
  );
}

function isLiveRuntimeReportMessage(message) {
  if (
    !message ||
    message.traceOnly ||
    isControlRoomBookkeepingAgentMessage(message) ||
    isSyntheticAgentOverviewMessage(message) ||
    isRuntimeTranscriptIntegrityWarning(message)
  ) {
    return false;
  }
  const label = String(message?.label || message?.roleLabel || "").toLowerCase();
  const role = String(message?.role || "").toLowerCase();
  const hasBody = Boolean(
    String(message?.detail || message?.message || message?.content || message?.technicalDetail || "").trim(),
  );
  return Boolean(
    isRuntimeOutputAgentMessage(message) ||
      label.includes("hermes session transcript") ||
      label.includes("hermes runtime output") ||
      (hasBody && message?.processMessage && (role === "runtime" || role === "assistant")) ||
      (hasBody && label.includes("runtime")),
  );
}

function isEmptyBookkeepingAgentMessage(message) {
  if (!message || message.traceOnly) return true;
  const label = String(message?.label || message?.roleLabel || "").toLowerCase();
  const title = String(message?.title || "").trim().toLowerCase();
  const detailText = [
    message?.detail,
    message?.message,
    message?.content,
    message?.technicalDetail,
  ]
    .map(value => String(value || "").trim())
    .filter(Boolean)
    .join("\n");
  if (detailText) return false;
  return (
    label.includes("hermes session decision") ||
    label.includes("hermes session next action") ||
    (
      label.includes("hermes session note") &&
      (
        title.startsWith("execution policy:") ||
        title.startsWith("runtime controls:")
      )
    )
  );
}

function compactAgentMessages(messages) {
  const rows = [];
  let lowSignalCount = 0;
  let latestLowSignal = null;
  for (const message of asList(messages)) {
    if (isLowSignalAgentMessage(message)) {
      lowSignalCount += 1;
      latestLowSignal = message;
      continue;
    }
    rows.push(message);
  }
  if (lowSignalCount > 0) {
    rows.unshift({
      ...(latestLowSignal || {}),
      id: `runtime-heartbeat-summary-${lowSignalCount}`,
      role: "runtime",
      label: "Runtime heartbeat",
      title: `${lowSignalCount} low-signal runtime heartbeat${lowSignalCount === 1 ? "" : "s"} collapsed`,
      detail: "The full heartbeat stream stays in live evidence; the main thread shows decisions, blockers, tool output, and slice progress.",
      tone: "neutral",
      traceOnly: true,
      chatPreferred: false,
      chips: ["collapsed", "live"],
    });
  }
  return rows;
}

function orderedAgentMessagesNewestFirst(messages) {
  return asList(messages)
    .map((message, index) => {
      const rawTimestamp = message?.createdAt || message?.timestamp || message?.time || message?.updatedAt || "";
      const parsedTimestamp = rawTimestamp ? Date.parse(rawTimestamp) : Number.NaN;
      return {
        message,
        index,
        timestamp: Number.isFinite(parsedTimestamp) ? parsedTimestamp : 0,
      };
    })
    .sort((left, right) => {
      if (right.timestamp !== left.timestamp) return right.timestamp - left.timestamp;
      return right.index - left.index;
    })
    .map(item => item.message);
}

function orderedAgentDialogueChronological(messages) {
  return asList(messages)
    .map((message, index) => {
      const rawTimestamp = message?.createdAt || message?.timestamp || message?.time || message?.updatedAt || "";
      const parsedTimestamp = rawTimestamp ? Date.parse(rawTimestamp) : Number.NaN;
      return {
        message,
        index,
        timestamp: Number.isFinite(parsedTimestamp) ? parsedTimestamp : 0,
      };
    })
    .sort((left, right) => {
      if (left.timestamp !== right.timestamp) return left.timestamp - right.timestamp;
      return left.index - right.index;
    })
    .map(item => item.message);
}

function uniqueRuntimeOutputMessages(messages) {
  const seen = new Set();
  const rows = [];
  for (const message of asList(messages)) {
    const body = runtimeOutputText(message)
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 1200);
    const key = [
      message?.missionId || message?.mission_id || "",
      message?.runtimeId || message?.runtime_id || "",
      body || stableAgentMessageKey(message, ""),
    ].join(":");
    if (!key || seen.has(key)) continue;
    seen.add(key);
    rows.push(message);
  }
  return rows;
}

function uniqueAgentDialogueMessages(messages) {
  const seen = new Set();
  const rows = [];
  for (const message of asList(messages)) {
    const key = [
      isOperatorFollowUpAgentMessage(message) ? "operator-follow-up" : isHermesDialogueReplyAgentMessage(message) ? "hermes-reply" : message?.role || "",
      String(message?.label || message?.roleLabel || "").toLowerCase(),
      String(message?.title || "").replace(/\s+/g, " ").trim().toLowerCase(),
      String(message?.detail || message?.message || message?.content || "").replace(/\s+/g, " ").trim().toLowerCase(),
      String(message?.createdAt || message?.timestamp || message?.time || "").slice(0, 19),
    ]
      .filter(Boolean)
      .join(":")
      .slice(0, 1500);
    if (key && seen.has(key)) {
      continue;
    }
    if (key) {
      seen.add(key);
    }
    rows.push(message);
  }
  return rows;
}

function visibleAgentMessages(messages, limit = 36, priorityLimit = 8, options = {}) {
  const requireRuntimeReports = Boolean(options?.requireRuntimeReports);
  const requireTrustedDialogue = Boolean(options?.requireTrustedDialogue);
  const rows = asList(messages).filter(message => !isEmptyBookkeepingAgentMessage(message));
  const dialogueRows = uniqueAgentDialogueMessages(
    rows.filter(message => isAgentDialogueTurn(message) && (!requireTrustedDialogue || isTrustedLiveDialogueSource(message))),
  );
  if (dialogueRows.length > 0) {
    return orderedAgentDialogueChronological(
      dialogueRows.length <= limit ? dialogueRows : dialogueRows.slice(-limit),
    );
  }
  const runtimeOutputRows = uniqueRuntimeOutputMessages(
    rows.filter(message => isRuntimeOutputAgentMessage(message) && !isProofArtifactAgentMessage(message)),
  );
  const reportRows = rows.filter(message => isLiveRuntimeReportMessage(message) && !isProofArtifactAgentMessage(message));
  const sourceRows = requireRuntimeReports
    ? []
    : runtimeOutputRows.length > 0
      ? runtimeOutputRows
      : reportRows.length > 0
        ? reportRows
        : rows.filter(message => !isControlRoomBookkeepingAgentMessage(message) && !isSyntheticAgentOverviewMessage(message));
  const priorityRows = requireRuntimeReports ? [] : runtimeOutputRows.slice(-priorityLimit);
  const seedRows = sourceRows.length <= limit ? sourceRows : sourceRows.slice(-limit);
  const seenKeys = new Set();
  const priorityKeys = new Set(
    priorityRows.map((message, index) => stableAgentMessageKey(message, `priority-${index}`)),
  );
  const orderedPriorityRows = orderedAgentMessagesNewestFirst(priorityRows);
  const orderedSeedRows = orderedAgentMessagesNewestFirst(seedRows);
  const mergedRows = [];
  const pushMessage = (message, fallback, { force = false } = {}) => {
    const key = stableAgentMessageKey(message, fallback);
    if (!key || seenKeys.has(key)) return;
    if (!force && priorityKeys.has(key)) return;
    seenKeys.add(key);
    mergedRows.push(message);
  };
  orderedPriorityRows.forEach((message, index) => pushMessage(message, `priority-${index}`, { force: true }));
  orderedSeedRows.forEach((message, index) => pushMessage(message, `tail-${index}`));
  return mergedRows.slice(0, limit);
}

function isMeaningfulDefaultAgentMessage(message) {
  if (!message || isLowSignalAgentMessage(message)) return false;
  const title = String(message?.title || "").toLowerCase();
  const label = String(message?.label || message?.roleLabel || "").toLowerCase();
  const detail = String(message?.detail || message?.message || "").trim();
  if (title.includes("low-signal runtime heartbeat") || title.includes("heartbeat") && label.includes("runtime heartbeat")) {
    return false;
  }
  if (isRuntimeOutputAgentMessage(message)) {
    return true;
  }
  return Boolean(
    detail ||
      message?.technicalDetail ||
      message?.processMessage ||
      message?.emphasis ||
      label.includes("hermes session transcript") ||
      label.includes("planner") ||
      label.includes("action") ||
      label.includes("mission review"),
  );
}

const TERMINAL_BUILDER_STATUSES = new Set(["completed", "done", "failed", "stopped", "cancelled", "canceled"]);
const ACTIVE_BUILDER_STATUSES = new Set(["active", "delegated", "needs approval", "needs review", "paused", "queued", "running"]);

function normalizedStatus(value) {
  return String(value || "").trim().toLowerCase();
}

function isActiveBuilderRow(row) {
  const status = normalizedStatus(row?.status || row?.statusLabel || row?.rawStatus);
  const tone = normalizedStatus(row?.statusTone || row?.tone);
  if (Number(row?.delegatedLaneCount || row?.delegatedSessions || 0) > 0) return true;
  if (TERMINAL_BUILDER_STATUSES.has(status)) return false;
  return ACTIVE_BUILDER_STATUSES.has(status) || tone === "running" || tone === "warn";
}

function isBlockedBuilderRow(row) {
  return Number(row?.blockedCount || row?.verificationFailures || row?.pendingApprovals || 0) > 0;
}

function sortLiveBuilderRows(rows) {
  return asList(rows).slice().sort((left, right) => {
    if (Boolean(right?.selected) !== Boolean(left?.selected)) return Number(Boolean(right?.selected)) - Number(Boolean(left?.selected));
    const activeDelta = Number(isActiveBuilderRow(right)) - Number(isActiveBuilderRow(left));
    if (activeDelta) return activeDelta;
    const blockedDelta = Number(isBlockedBuilderRow(right)) - Number(isBlockedBuilderRow(left));
    if (blockedDelta) return blockedDelta;
    return 0;
  });
}

function normalizePhoneMissionRow(item) {
  if (!item || typeof item !== "object") return null;
  const missionId = item.id || item.missionId || item.mission_id || "";
  const status = item.status || item.statusLabel || item?.state?.status || item.planner_loop_status || "live";
  const progressValue = clampPercent(item.progress ?? item?.liveProgress?.value);
  const blockerCount =
    Number(item.blockedCount || 0) +
    asList(item?.proof?.pending_approvals).length +
    asList(item?.state?.verification_failures).length;
  const delegatedLaneCount =
    Number(item.delegatedLaneCount || item.activeDelegatedLaneCount || item.delegatedLaneCount || 0) ||
    asList(item.delegated_runtime_sessions).filter(session =>
      !["completed", "failed", "stopped"].includes(String(session?.status || "").toLowerCase()),
    ).length;
  return {
    ...item,
    id: missionId,
    missionId,
    name: item.name || item.title || item.objective || missionId || "Live mission",
    title: item.title || item.name || item.objective || missionId || "Live mission",
    status,
    statusLabel: item.statusLabel || status,
    progress: progressValue == null ? item.progress || item?.liveProgress?.value || null : `${progressValue}%`,
    runtime: item.runtime || item.runtime_id || item.runtimeId || "",
    runtimeId: item.runtimeId || item.runtime_id || item.runtime || "",
    turningPoint:
      item.turningPoint ||
      item?.liveProgress?.nextAction ||
      item.nextAction ||
      item.summary ||
      item.description ||
      "",
    detail:
      item.detail ||
      item.summary ||
      item.description ||
      item?.proof?.summary ||
      item?.liveProgress?.label ||
      "",
    delegatedLaneCount,
    blockedCount: blockerCount,
  };
}

function isRealChangedItem(item) {
  const tuple = changedItemTuple(item);
  const path = normalizedChangedPath(tuple[0]);
  return path.length > 0 && path !== "changed-file";
}

function normalizedChangedPath(value) {
  return String(value || "").trim().toLowerCase();
}

function changedItemTuple(item) {
  if (typeof item === "string") return [item.trim(), "recorded", "file"];
  if (Array.isArray(item)) return [String(item[0] || "").trim(), String(item[1] || "recorded"), String(item[2] || "file")];
  if (!item || typeof item !== "object") return false;
  return [
    String(item.path || item.file || "").trim(),
    String(item.summary || item.status || "recorded").trim(),
    String(item.kind || "file").trim(),
  ];
}

const CONSISTENCY_STOP_WORDS = new Set([
  "about",
  "after",
  "agent",
  "also",
  "been",
  "before",
  "could",
  "from",
  "have",
  "hermes",
  "into",
  "just",
  "like",
  "make",
  "making",
  "message",
  "more",
  "only",
  "that",
  "their",
  "there",
  "these",
  "they",
  "this",
  "those",
  "turn",
  "very",
  "with",
  "would",
  "your",
]);

const CONSISTENCY_POSITIVE_TERMS = [
  "can",
  "able",
  "possible",
  "working",
  "works",
  "enabled",
  "ready",
  "completed",
  "done",
  "available",
  "succeeded",
];

const CONSISTENCY_NEGATIVE_TERMS = [
  "cannot",
  "can't",
  "unable",
  "impossible",
  "failed",
  "fails",
  "disabled",
  "blocked",
  "unavailable",
  "missing",
  "denied",
  "error",
];

function parseTimeMs(value) {
  if (!value) return 0;
  const timestamp = Date.parse(String(value));
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function formatElapsedDuration(ms) {
  const safeMs = Math.max(0, Number(ms) || 0);
  if (safeMs < 1000) return `${safeMs}ms`;
  if (safeMs < 10_000) return `${(safeMs / 1000).toFixed(1)}s`;
  if (safeMs < 60_000) return `${Math.round(safeMs / 1000)}s`;
  const minutes = Math.floor(safeMs / 60_000);
  const seconds = Math.floor((safeMs % 60_000) / 1000);
  return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
}

function extractLatencyMsFromMessage(message) {
  const text = [
    ...(asList(message?.chips).map(item => String(item || ""))),
    String(message?.detail || ""),
    String(message?.technicalDetail || ""),
  ].join(" ");
  const match = text.match(/\b(\d{2,6})\s*ms\b/i);
  if (!match) return 0;
  const value = Number(match[1]);
  return Number.isFinite(value) && value > 0 ? value : 0;
}

function tokenizeConsistencyText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .map(token => token.trim())
    .filter(token => token.length >= 4 && !CONSISTENCY_STOP_WORDS.has(token));
}

function consistencyPolarityScore(value) {
  const text = String(value || "").toLowerCase();
  let score = 0;
  for (const token of CONSISTENCY_POSITIVE_TERMS) {
    if (text.includes(token)) score += 1;
  }
  for (const token of CONSISTENCY_NEGATIVE_TERMS) {
    if (text.includes(token)) score -= 1;
  }
  if (score === 0) return 0;
  return score > 0 ? 1 : -1;
}

function detectPotentialContradiction(messages, index) {
  const current = messages[index];
  if (!current || current.role !== "assistant") return null;
  const currentText = `${current.title || ""} ${current.detail || ""}`.trim();
  const currentPolarity = consistencyPolarityScore(currentText);
  if (!currentText || currentPolarity === 0) return null;
  const currentTokens = new Set(tokenizeConsistencyText(currentText));
  if (currentTokens.size < 2) return null;

  for (let i = index - 1; i >= 0; i -= 1) {
    const previous = messages[i];
    if (!previous || previous.role !== "assistant") {
      continue;
    }
    const previousText = `${previous.title || ""} ${previous.detail || ""}`.trim();
    const previousPolarity = consistencyPolarityScore(previousText);
    if (!previousText || previousPolarity === 0 || previousPolarity === currentPolarity) {
      continue;
    }
    const previousTokens = new Set(tokenizeConsistencyText(previousText));
    const overlap = Array.from(currentTokens).filter(token => previousTokens.has(token));
    if (overlap.length >= 2) {
      return {
        subject: overlap.slice(0, 3).join(", "),
        previousId: previous.id,
      };
    }
  }
  return null;
}

function artifactBackendBaseUrl() {
  const configured =
    import.meta.env?.VITE_FLUXIO_BACKEND_URL ||
    globalThis.window?.__FLUXIO_BACKEND_URL__ ||
    "";
  return String(configured || "").trim().replace(/\/$/, "");
}

function resolveReferenceArtifactUrl(value) {
  const source = String(value || "").trim();
  if (!source) return "";
  if (/^(data:|blob:|https?:\/\/)/i.test(source)) return source;
  if (source.startsWith("/api/artifact")) return `${artifactBackendBaseUrl()}${source}`;
  const params = new URLSearchParams({ path: source });
  return `${artifactBackendBaseUrl()}/api/artifact?${params.toString()}`;
}

function artifactUrlForRecord(record) {
  if (typeof record === "string") return resolveReferenceArtifactUrl(record);
  return resolveReferenceArtifactUrl(
    record?.artifactUrl ||
      record?.servedUrl ||
      record?.previewUrl ||
      record?.generatedPreview ||
      record?.previewSrc ||
      record?.outputPreview ||
      record?.imagePath ||
      record?.outputArtifactPath ||
      record?.artifactPath ||
      record?.path ||
      "",
  );
}

function artifactLabelForRecord(record, fallback = "generated artifact") {
  if (typeof record === "string") {
    return record.split(/[\\/]/).filter(Boolean).pop() || fallback;
  }
  return (
    record?.label ||
    record?.title ||
    record?.artifactId ||
    record?.requestId ||
    artifactLabelForRecord(record?.artifactPath || record?.path || "", fallback)
  );
}

function isImageArtifactPath(value) {
  return /\.(apng|avif|gif|jpe?g|png|svg|webp)(\?|#|$)/i.test(String(value || ""));
}

function isUsablePreviewUrl(value) {
  const source = String(value || "").trim();
  if (!source) return false;
  if (/^no\s+/i.test(source)) return false;
  if (/pending|unavailable|captured/i.test(source)) return false;
  return /^(https?:\/\/|\/control\b|\/api\/artifact\b|data:|blob:)/i.test(source);
}

function isEmbeddablePreviewUrl(value) {
  const source = String(value || "").trim();
  if (!isUsablePreviewUrl(source)) return false;
  const controlSource = source.startsWith("/control")
    ? source
    : /^https?:\/\//i.test(source)
      ? (() => {
          try {
            const parsed = new URL(source);
            return parsed.pathname === "/control" ? `${parsed.pathname}${parsed.search}` : "";
          } catch {
            return "";
          }
        })()
      : "";
  if (/surface=agent|mode=agent/i.test(controlSource)) return false;
  let isArtifactUrl = source.startsWith("/api/artifact");
  if (!isArtifactUrl && /^https?:\/\//i.test(source)) {
    try {
      isArtifactUrl = new URL(source).pathname.startsWith("/api/artifact");
    } catch {
      isArtifactUrl = false;
    }
  }
  if (!isArtifactUrl) return true;
  try {
    const decoded = decodeURIComponent(source);
    return /\.(html?|xhtml)(\?|#|$)/i.test(decoded);
  } catch {
    return /\.(html?|xhtml)(\?|#|$)/i.test(source);
  }
}

function isMissionPreviewUrl(value) {
  const source = String(value || "").trim();
  if (!isEmbeddablePreviewUrl(source)) return false;
  if (/^(https?:\/\/[^/]+)?\/control(?:\?|$)/i.test(source)) return false;
  if (/^https?:\/\//i.test(source)) {
    try {
      const parsed = new URL(source);
      if (!parsed.pathname.startsWith("/api/artifact")) {
        return false;
      }
    } catch {
      return false;
    }
  }
  return true;
}

function isLocalEmbeddablePreviewUrl(value) {
  const source = String(value || "").trim();
  if (!isEmbeddablePreviewUrl(source)) return false;
    if (/^(data:|blob:|\/api\/artifact\b)/i.test(source)) return true;
    if (/^\/(?!\/)/.test(source)) {
      return !/^\/control(?:[/?#]|$)/i.test(source);
    }
    if (!/^https?:\/\//i.test(source)) return false;
    try {
      const parsed = new URL(source);
      const host = parsed.hostname.toLowerCase();
      const currentHost = String(globalThis.window?.location?.hostname || "").toLowerCase();
      if (host === currentHost && /^\/control(?:[/?#]|$)/i.test(parsed.pathname)) {
        return false;
      }
      return (
        host === "localhost" ||
      host === "127.0.0.1" ||
      host === "::1" ||
      (currentHost && host === currentHost)
    );
  } catch {
    return false;
  }
}

function isWorkbenchPreviewFrameUrl(value) {
  return isMissionPreviewUrl(value) || isLocalEmbeddablePreviewUrl(value);
}

function previewUrlCandidatesForMessage(message) {
  if (!message || typeof message !== "object") return [];
  return [
    message.previewUrl,
    message.preview_url,
    message.previewActionUrl,
    message.artifactUrl,
    message.servedUrl,
    message.reportUrl,
    message.screenshotUrl,
    message.path && isImageArtifactPath(message.path) ? message.path : "",
  ].filter(Boolean);
}

function agentMessageKey(message, fallback = "") {
  if (!message || typeof message !== "object") return fallback;
  const directKey = message.id || message.messageId || message.turnId || message.eventId;
  if (directKey) return String(directKey);
  const semanticKey = [
    message.createdAt,
    message.label || message.roleLabel || message.role,
    message.title,
  ].filter(Boolean).join(":");
  return semanticKey || fallback;
}

function agentMessageFallbackKey(message, fallback = "") {
  if (!message || typeof message !== "object") return fallback;
  const semanticKey = [
    message.missionId || message.mission_id,
    message.runtimeId || message.runtime_id,
    message.createdAt || message.timestamp || message.time,
    message.label || message.roleLabel || message.role,
    message.title,
    message.detail || message.message || message.content,
    message.technicalDetail,
  ]
    .map(value => String(value || "").trim())
    .filter(Boolean)
    .join(":")
    .slice(0, 420);
  return semanticKey ? `message:${semanticKey}` : fallback;
}

function stableAgentMessageKey(message, fallback = "") {
  const fallbackKey = agentMessageFallbackKey(message, fallback);
  const missionKey = String(message?.missionId || message?.mission_id || "").trim();
  const runtimeKey = String(message?.runtimeId || message?.runtime_id || "").trim();
  if (isRuntimeOutputAgentMessage(message)) {
    const reportTitle = agentMessageDisplayTitle(message)
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
    const reportTimestamp = String(message?.createdAt || message?.timestamp || message?.time || "").trim();
    const reportBodyKey = runtimeOutputText(message)
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 320);
    const reportKey = [missionKey, runtimeKey, "runtime-report", reportTimestamp, reportTitle, reportBodyKey]
      .filter(Boolean)
      .join(":");
    if (reportKey) return reportKey;
  }
  const baseKey = agentMessageKey(message, fallbackKey);
  const directKey = String(message?.id || message?.messageId || message?.turnId || message?.eventId || "").trim();
  const contentKey = fallbackKey && fallbackKey !== baseKey ? fallbackKey : "";
  const scopedKey = [missionKey, runtimeKey, baseKey, contentKey || (!directKey ? fallbackKey : "")]
    .filter(Boolean)
    .join(":");
  return scopedKey || fallback;
}

function isGenericProcessLabel(value) {
  return String(value || "").trim().toLowerCase() === "process message";
}

function isRouteMetadataPreviewText(value) {
  return /^(chat:|route:|provider:|model:|effort:|openclaw:|hermes:)/i.test(String(value || "").trim());
}

function agentPreviewTitle(item) {
  const title = String(item?.title || "").trim();
  const label = String(item?.label || "").trim();
  if (title && !isGenericProcessLabel(title)) return title;
  if (label && !isGenericProcessLabel(label)) return label;
  return "Live mission update";
}

function agentPreviewDetail(item) {
  const detail = String(item?.detail || item?.technicalDetail || "").trim();
  if (detail && detail !== item?.title && !isRouteMetadataPreviewText(detail)) return detail;
  const chips = asList(item?.chips).map(value => String(value || "").trim()).filter(Boolean);
  if (chips.length) return chips.slice(0, 3).join(" · ");
  return String(item?.meta || item?.status || "Current Agent message").trim();
}

function dotToneClass(tone) {
  if (tone === "good" || tone === "completed") {
    return "good";
  }
  if (tone === "warn" || tone === "running") {
    return "warn";
  }
  if (tone === "bad" || tone === "failed") {
    return "bad";
  }
  return "neutral";
}

const HOME_CARDS = [
  {
    id: "agent",
    title: "Agent",
    copy: "Ask Fluxio to plan, build, check, and keep progress visible.",
    tone: "blue",
    icon: Sparkles,
  },
  {
    id: "builder",
    title: "Builder",
    copy: "Create and manage projects with powerful tools.",
    tone: "gold",
    icon: Hammer,
  },
  {
    id: "phone",
    title: "Phone",
    copy: "Watch live mission progress and notifications from a compact mobile surface.",
    tone: "blue",
    icon: Smartphone,
  },
  {
    id: "skills",
    title: "Skills",
    copy: "Manage reusable procedures, trigger conditions, and agent behaviors.",
    tone: "blue",
    icon: Grid2x2,
  },
  {
    id: "rule-sets",
    title: "Rule Sets",
    copy: "Control approvals, file scope, commands, runtimes, and autonomy boundaries.",
    tone: "gold",
    icon: Shield,
  },
  {
    id: "images",
    title: "Images",
    copy: "Layer, edit, compare, and continue image generations from precise manual compositions.",
    tone: "blue",
    icon: Palette,
  },
  {
    id: "workbench",
    title: "Workbench",
    copy: "Computer-use readiness, notifications, multi-lane missions, and cross-domain AI workflows.",
    tone: "blue",
    icon: Laptop,
  },
];

function RailBrand() {
  return (
    <div className="reference-brand">
      <div aria-hidden="true" className="reference-brand-mark">
        <span />
        <span />
        <span />
      </div>
      <strong>Fluxio</strong>
    </div>
  );
}

function RailItem({ active = false, icon: Icon, label, onClick, tone = "neutral" }) {
  return (
    <button
      className={cx("reference-rail-item", active && "active", `tone-${tone}`)}
      onClick={onClick}
      type="button"
    >
      <Icon size={19} strokeWidth={1.9} />
      <span>{label}</span>
    </button>
  );
}

function TopbarPill({ icon: Icon, label, active = false, dot = false, onClick }) {
  return (
    <button className={cx("reference-topbar-pill", active && "active")} onClick={onClick} type="button">
      <Icon size={17} strokeWidth={1.9} />
      <span>{label}</span>
      {dot ? <span className="reference-live-dot" /> : null}
    </button>
  );
}

function IconButton({ icon: Icon, label, onClick }) {
  return (
    <button aria-label={label} className="reference-icon-button" onClick={onClick} type="button">
      <Icon size={18} strokeWidth={1.9} />
    </button>
  );
}

function joinEditorLines(lines) {
  return asList(lines).join("\n");
}

function SidebarProfile() {
  return (
    <div className="reference-sidebar-profile">
      <div className="reference-sidebar-avatar">OP</div>
      <div className="reference-sidebar-profile-copy">
        <strong>Orbit Pro</strong>
        <span>Pro Plan</span>
      </div>
      <ChevronDown size={18} strokeWidth={1.9} />
    </div>
  );
}

function FlowSidebar({
  currentModeLabel = "Agent",
  favoriteFlows = [],
  flowProjects = [],
  onRequestAction,
  onOpenSettings,
  onSelectFlow,
  onSelectProject,
  selectedProjectId,
}) {
  return (
    <div className="reference-flow-sidebar">
      <div className="reference-mode-head">
        <strong>{currentModeLabel}</strong>
        <ChevronDown size={16} strokeWidth={1.9} />
      </div>

      <div className="reference-search-shell">
        <button
          className="reference-search-shell-action"
          onClick={() => onRequestAction?.("flow:search")}
          type="button"
        >
          <Search size={16} strokeWidth={1.9} />
          <span>Search conversations...</span>
        </button>
        <button
          aria-label="New conversation"
          className="reference-search-shell-new"
          onClick={() => onRequestAction?.("flow:new-conversation")}
          title="Start new conversation"
          type="button"
        >
          <Edit3 size={15} strokeWidth={1.9} />
          <span>New chat</span>
        </button>
      </div>

      <section className="reference-flow-section">
        <span>Favorites</span>
        <div className="reference-favorite-list">
          {favoriteFlows.map(item => (
            <button
              className="reference-favorite-item"
              key={item.id}
              onClick={() => onSelectFlow(item.id)}
              type="button"
            >
              <span className={cx("reference-flow-dot", dotToneClass(item.tone))} />
              <strong>{item.title}</strong>
              <Star size={14} strokeWidth={1.9} />
            </button>
          ))}
        </div>
      </section>

      <section className="reference-flow-section">
        <div className="reference-flow-section-head">
          <span>Projects</span>
          <button
            className="reference-mini-icon"
            onClick={() => onRequestAction?.("flow:add-project")}
            type="button"
          >
            <Plus size={14} strokeWidth={2} />
          </button>
        </div>
        <div className="reference-project-list">
          {flowProjects.map(project => (
            <div className="reference-project-group" key={project.id}>
              <button
                className={cx("reference-project-row", project.id === selectedProjectId && "active")}
                onClick={() => onSelectProject(project.id)}
                type="button"
              >
                <div className="reference-project-row-title">
                  <FolderOpen size={15} strokeWidth={1.9} />
                  <strong>{project.title}</strong>
                </div>
                <span>{project.count}</span>
              </button>
              {project.expanded ? (
                <div className="reference-project-flows">
                  {project.flows.map(flow => (
                    <button
                      className={cx("reference-project-flow", flow.selected && "active")}
                      key={flow.id}
                      onClick={() => onSelectFlow(flow.id)}
                      type="button"
                    >
                      <div>
                        <strong>{flow.title}</strong>
                        <p>
                          <span className={cx("reference-flow-dot tiny", dotToneClass(flow.statusTone))} />
                          {flow.status}
                        </p>
                      </div>
                      <em>{flow.updated}</em>
                    </button>
                  ))}
                  {project.hasMore ? (
                    <button
                      className="reference-show-more"
                      onClick={() => {
                        onSelectProject(project.id);
                        onRequestAction?.("flow:show-all", { workspaceId: project.id });
                      }}
                      type="button"
                    >
                      Show all
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </section>

      <button className="reference-settings-rail-link" onClick={onOpenSettings} type="button">
        <Settings size={17} strokeWidth={1.9} />
        <span>Settings</span>
      </button>
    </div>
  );
}

function SurfaceField({ label, hint, children }) {
  return (
    <label className="reference-surface-field">
      <span>{label}</span>
      {children}
      {hint ? <small>{hint}</small> : null}
    </label>
  );
}

function SectionPillTabs({ tabs = [], value, onChange }) {
  return (
    <div className="reference-pill-tabs">
      {tabs.map(tab => (
        <button
          className={value === tab.value ? "active" : ""}
          key={tab.value}
          onClick={() => onChange(tab.value)}
          type="button"
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

function HomeSurface({ onOpenSurface, onRequestAction }) {
  return (
    <section className="reference-home-surface">
      <div className="reference-home-header">
        <div>
          <h1>Fluxio</h1>
          <p>Agent operating system for workspaces.</p>
        </div>
        <IconButton icon={CircleHelp} label="Help" onClick={() => onRequestAction?.("home:help")} />
      </div>

      <div className="reference-home-hero">
        <h2>What do you want to do today?</h2>
        <p>Choose your mode to get started.</p>
      </div>

      <div className="reference-home-card-row">
        {HOME_CARDS.map(card => {
          const Icon = card.icon;
          return (
            <article className={cx("reference-home-card", `tone-${card.tone}`)} key={card.id}>
              <div className="reference-home-card-icon">
                <Icon size={26} strokeWidth={1.9} />
              </div>
              <h3>{card.title}</h3>
              <p>{card.copy}</p>
              <button className={cx("reference-home-open", `tone-${card.tone}`)} onClick={() => onOpenSurface(card.id)} type="button">
                <span>Open</span>
                <ArrowUp className="reference-arrow-inline" size={16} strokeWidth={2} />
              </button>
            </article>
          );
        })}
      </div>

      <div aria-hidden="true" className="reference-home-orbit" />
    </section>
  );
}

function WorkbenchSurface({ workbenchState, onRequestAction, onSetSurface }) {
  const state = workbenchState || {};
  const computerUse = state.computerUse || {};
  const notificationEvents = asList(state.notificationEvents);
  const playgrounds = asList(state.playgrounds);
  const lanes = asList(state.lanes);
  const runtimeOps = state.runtimeOps || {};
  const proofDiff = state.proofDiff || {};
  const proofDiffRows = asList(proofDiff.rows);
  const [proofDiffWrap, setProofDiffWrap] = useState(true);
  const [proofDiffVisibleCount, setProofDiffVisibleCount] = useState(12);
  const visibleProofDiffRows = proofDiffRows.slice(0, proofDiffVisibleCount);
  const tutorials = state.tutorials || {};
  const coverage = state.coverage || {};
  const ideaPlanner = state.ideaPlanner || {};
  const providerCatalog = state.providerCatalog || {};
  const liveReview = state.liveReview || {};
  const reviewEvents = asList(liveReview.events);
  const annotations = asList(liveReview.annotationReadiness?.blocks);
  const replayMarkers = useMemo(
    () =>
      reviewEvents
        .flatMap(event =>
          asList(event.replayMarkers).map(marker => ({
            ...marker,
            eventId: event.id || `${event.kind}-${event.title}`,
          })),
        )
        .filter(marker => marker?.id),
    [reviewEvents],
  );
  const reviewEventsById = useMemo(
    () => new Map(reviewEvents.map(event => [event.id || `${event.kind}-${event.title}`, event])),
    [reviewEvents],
  );
  const [selectedLiveReviewEventId, setSelectedLiveReviewEventId] = useState(
    () => reviewEvents[0]?.id || "",
  );
  useEffect(() => {
    if (!reviewEvents.length) {
      if (selectedLiveReviewEventId) {
        setSelectedLiveReviewEventId("");
      }
      return;
    }
    const match = reviewEventsById.get(selectedLiveReviewEventId);
    if (!match) {
      setSelectedLiveReviewEventId(reviewEvents[0]?.id || "");
    }
  }, [reviewEvents, reviewEventsById, selectedLiveReviewEventId]);
  const selectedLiveReviewEvent =
    reviewEventsById.get(selectedLiveReviewEventId) || reviewEvents[0] || null;
  const selectedScreenshotFrames = asList(selectedLiveReviewEvent?.screenshotFrames);
  const [selectedScreenshotFrameId, setSelectedScreenshotFrameId] = useState(
    () => selectedScreenshotFrames[0]?.id || "",
  );
  useEffect(() => {
    if (!selectedScreenshotFrames.length) {
      if (selectedScreenshotFrameId) {
        setSelectedScreenshotFrameId("");
      }
      return;
    }
    const hasFrame = selectedScreenshotFrames.some(frame => frame?.id === selectedScreenshotFrameId);
    if (!hasFrame) {
      setSelectedScreenshotFrameId(selectedScreenshotFrames[0]?.id || "");
    }
  }, [selectedScreenshotFrameId, selectedScreenshotFrames]);
  const selectedScreenshotFrame =
    selectedScreenshotFrames.find(frame => frame?.id === selectedScreenshotFrameId) ||
    selectedScreenshotFrames[0] ||
    null;
  const [selectedReplayMarkerId, setSelectedReplayMarkerId] = useState(() => replayMarkers[0]?.id || "");
  useEffect(() => {
    if (!replayMarkers.length) {
      if (selectedReplayMarkerId) {
        setSelectedReplayMarkerId("");
      }
      return;
    }
    const exists = replayMarkers.some(marker => marker?.id === selectedReplayMarkerId);
    if (!exists) {
      setSelectedReplayMarkerId(replayMarkers[0]?.id || "");
    }
  }, [replayMarkers, selectedReplayMarkerId]);
  const selectedReplayMarker = replayMarkers.find(marker => marker?.id === selectedReplayMarkerId) || null;
  const [isTimelapsePlaying, setIsTimelapsePlaying] = useState(false);
  const markerFrameMap = useMemo(() => {
    return replayMarkers.map((marker, index) => {
      const linkedFrameIndex = selectedScreenshotFrames.findIndex(frame => {
        if (!frame) {
          return false;
        }
        return (
          (marker?.snapshotPath && frame.path === marker.snapshotPath) ||
          (marker?.snapshotPath && frame.id === marker.snapshotPath) ||
          (marker?.frameId && frame.id === marker.frameId)
        );
      });
      return {
        ...marker,
        frameIndex: linkedFrameIndex >= 0 ? linkedFrameIndex : Math.min(index, Math.max(selectedScreenshotFrames.length - 1, 0)),
      };
    });
  }, [replayMarkers, selectedScreenshotFrames]);
  const selectedMarkerIndex = Math.max(
    0,
    markerFrameMap.findIndex(marker => marker?.id === selectedReplayMarkerId),
  );
  useEffect(() => {
    if (!selectedReplayMarker?.eventId) {
      return;
    }
    const activeEventId = selectedLiveReviewEvent?.id || `${selectedLiveReviewEvent?.kind}-${selectedLiveReviewEvent?.title}`;
    if (selectedReplayMarker.eventId === activeEventId) {
      return;
    }
    setSelectedLiveReviewEventId(selectedReplayMarker.eventId);
  }, [selectedLiveReviewEvent, selectedReplayMarker]);
  useEffect(() => {
    if (!selectedReplayMarker?.snapshotPath || !selectedScreenshotFrames.length) {
      return;
    }
    const linkedFrame =
      selectedScreenshotFrames.find(frame => frame?.path === selectedReplayMarker.snapshotPath) ||
      selectedScreenshotFrames.find(frame => frame?.id === selectedReplayMarker.snapshotPath) ||
      null;
    if (linkedFrame?.id && linkedFrame.id !== selectedScreenshotFrameId) {
      setSelectedScreenshotFrameId(linkedFrame.id);
    }
  }, [selectedReplayMarker, selectedScreenshotFrames, selectedScreenshotFrameId]);
  useEffect(() => {
    if (!isTimelapsePlaying || markerFrameMap.length <= 1) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      const nextMarker = markerFrameMap[(selectedMarkerIndex + 1) % markerFrameMap.length];
      if (!nextMarker) {
        return;
      }
      setSelectedReplayMarkerId(nextMarker.id || "");
      const nextFrame = selectedScreenshotFrames[nextMarker.frameIndex] || null;
      if (nextFrame?.id) {
        setSelectedScreenshotFrameId(nextFrame.id);
      }
    }, 1800);
    return () => window.clearInterval(timer);
  }, [isTimelapsePlaying, markerFrameMap, selectedMarkerIndex, selectedScreenshotFrames]);
  const selectedEventArtifacts = asList(selectedLiveReviewEvent?.artifactPaths);
  const selectedEventBrowserActions = asList(selectedLiveReviewEvent?.browserActions);
  const selectedEventPrograms = asList(selectedLiveReviewEvent?.launchedPrograms);
  const selectedEventTests = asList(selectedLiveReviewEvent?.tests);
  const selectedEventProviderEvents = asList(selectedLiveReviewEvent?.providerEvents);
  const selectedEventLayerHandoff = asList(selectedLiveReviewEvent?.layerHandoff);
  const selectedEventQueueTimeline = asList(selectedLiveReviewEvent?.queueTimeline);
  const selectedEventGeneratedImages = asList(selectedLiveReviewEvent?.generatedImages);
  const selectedEventAcknowledgedBy = asList(selectedLiveReviewEvent?.acknowledgedBy);
  const selectedEventOperatorMessages = asList(selectedLiveReviewEvent?.operatorMessages);
  const normalizedComputerStatus = String(computerUse.status || "").trim().toLowerCase();
  const computerState = (() => {
    if (!normalizedComputerStatus || normalizedComputerStatus === "unavailable" || normalizedComputerStatus === "unknown") {
      return {
        key: "empty",
        tone: "neutral",
        title: "Computer-use needs a live lane",
        body: "Connect a runtime lane to enable browser/desktop handoff and live task execution.",
        actions: [
          { id: "workbench:computer-use", label: "Open control lane" },
          { id: "workbench:notification-settings", label: "Check notification wiring" },
        ],
      };
    }
    if (normalizedComputerStatus.includes("error") || normalizedComputerStatus.includes("fail")) {
      return {
        key: "error",
        tone: "bad",
        title: "Computer-use reported a failure",
        body: computerUse.handoffHint || "A runtime or handoff step failed. Inspect lane state and retry after fixing connection issues.",
        actions: [
          { id: "workbench:computer-use", label: "Open control lane" },
          { id: "workbench:notification-settings", label: "Check failure notifications" },
        ],
      };
    }
    if (normalizedComputerStatus.includes("loading") || normalizedComputerStatus.includes("starting") || normalizedComputerStatus.includes("boot")) {
      return {
        key: "loading",
        tone: "warn",
        title: "Computer-use is starting",
        body: computerUse.handoffHint || "Runtime services are initializing. Keep this panel open for readiness updates.",
        actions: [
          { id: "workbench:computer-use", label: "Open control lane" },
          { id: "live:refresh-preview", label: "Refresh status" },
        ],
      };
    }
    return {
      key: "active",
      tone: "good",
      title: "Computer-use is active",
      body: computerUse.handoffHint || "Desktop/browser runtime handoff points are available.",
      actions: [
        { id: "workbench:computer-use", label: "Open control lane" },
        { id: "agent:follow-up", label: "Open mission handoff" },
      ],
    };
  })();

  return (
    <section className="reference-workbench-surface">
      <div className="reference-builder-head">
        <div>
          <h1>AI Workbench</h1>
          <p>Cross-domain mission control for computer use, notifications, tutorials, and parallel lanes.</p>
        </div>
      </div>

      <div className="reference-settings-summary-grid">
        <article>
          <span>Computer-use status</span>
          <strong>{titleizeToken(computerUse.status || "unavailable")}</strong>
        </article>
        <article>
          <span>Safety mode</span>
          <strong>{titleizeToken(computerUse.safetyMode || "guided")}</strong>
        </article>
        <article>
          <span>Runtime</span>
          <strong>{computerUse.runtimeLabel || "not-wired"}</strong>
        </article>
        <article>
          <span>Active lanes</span>
          <strong>{lanes.length}</strong>
        </article>
      </div>

      <RuntimeOperationsPanel
        runtimeOps={runtimeOps}
        onRequestAction={onRequestAction}
        onSetSurface={onSetSurface}
      />

      <section className={cx("proof-side-by-side-diff", proofDiffWrap ? "wrap" : "no-wrap")} aria-label="Side-by-side proof diff with wrap toggle">
        <header className="proof-side-by-side-head">
          <div>
            <span>Side-by-side proof diff</span>
            <strong>Expected work vs captured evidence</strong>
          </div>
          <p>{visibleProofDiffRows.length} of {proofDiffRows.length} rows · {proofDiff.source || "mission proof"}</p>
        </header>
        <div className="reference-inline-actions compact">
          <button className="reference-outline-button" onClick={() => setProofDiffWrap(current => !current)} type="button">
            {proofDiffWrap ? "Disable wrap" : "Enable wrap"}
          </button>
          {proofDiffRows.length > proofDiffVisibleCount ? (
            <button className="reference-outline-button" onClick={() => setProofDiffVisibleCount(current => current + 12)} type="button">
              Show more diff evidence
            </button>
          ) : null}
        </div>
        <div className="proof-diff-table" role="table" aria-label="Side-by-side proof diff rows">
          <div className="proof-diff-row header" role="row">
            <span role="columnheader">Expectation</span>
            <span role="columnheader">Captured evidence</span>
            <span role="columnheader">State</span>
          </div>
          {visibleProofDiffRows.length ? visibleProofDiffRows.map(row => (
            <article className={cx("proof-diff-row", `tone-${row.tone || "neutral"}`)} key={row.id || row.captured} role="row">
              <div role="cell">
                <span>{row.category || "Proof"}</span>
                <code>{row.expected || "Expected evidence"}</code>
              </div>
              <div role="cell">
                <span>Evidence</span>
                <code>{row.captured || "Nothing captured yet."}</code>
              </div>
              <strong role="cell">{row.status || "Captured"}</strong>
            </article>
          )) : (
            <article className="proof-diff-row tone-warn" role="row">
              <div role="cell">
                <span>Proof</span>
                <code>Expected evidence</code>
              </div>
              <div role="cell">
                <span>Evidence</span>
                <code>Nothing captured yet.</code>
              </div>
              <strong role="cell">Missing</strong>
            </article>
          )}
        </div>
      </section>

      <div className="builder-live-review-layout">
        <article className="builder-live-review-panel">
          <div className="builder-live-review-meta">
            <strong>Live Review Timeline</strong>
            <span>{liveReview.statusLine || "Live review stream"}</span>
          </div>
          <div className="builder-live-review-events">
            {reviewEvents.length ? reviewEvents.map(event => {
              const eventId = event.id || `${event.kind}-${event.title}`;
              const active = selectedLiveReviewEvent?.id === event.id;
              return (
                <button
                  className={cx("builder-live-review-event", active && "active")}
                  key={eventId}
                  onClick={() => setSelectedLiveReviewEventId(event.id || "")}
                  type="button"
                >
                  <div className="builder-live-review-event-group">
                    <strong>{event.label || titleizeToken(event.kind || "event")}</strong>
                    <span>{event.timestamp || "now"}</span>
                  </div>
                  <p>{event.title || "Untitled event"}</p>
                  <p className="reference-surface-footnote">{event.detail || "No detail yet."}</p>
                  {asList(event.queueTimeline).length ? (
                    <div className="builder-live-review-queue-strip">
                      {asList(event.queueTimeline).map(item => <span key={item}>{titleizeToken(item)}</span>)}
                    </div>
                  ) : null}
                  {asList(event.generatedImages).length ? (
                    <div className="builder-live-review-queue-strip">
                      {asList(event.generatedImages).map(item => (
                        <span key={item.path || item.label}>{item.label || item.path}</span>
                      ))}
                    </div>
                  ) : null}
                </button>
              );
            }) : <p className="reference-surface-footnote">No live review events yet.</p>}
          </div>
          {selectedLiveReviewEvent ? (
            <div
              className="builder-live-review-focus"
              onKeyDown={event => {
                if (selectedScreenshotFrames.length <= 1) {
                  return;
                }
                const currentIndex = selectedScreenshotFrames.findIndex(frame => frame?.id === selectedScreenshotFrameId);
                if (event.key === "ArrowLeft") {
                  event.preventDefault();
                  const target =
                    selectedScreenshotFrames[currentIndex - 1] ||
                    selectedScreenshotFrames[selectedScreenshotFrames.length - 1] ||
                    null;
                  setSelectedScreenshotFrameId(target?.id || "");
                }
                if (event.key === "ArrowRight") {
                  event.preventDefault();
                  const target = selectedScreenshotFrames[currentIndex + 1] || selectedScreenshotFrames[0] || null;
                  setSelectedScreenshotFrameId(target?.id || "");
                }
              }}
              role="region"
              tabIndex={0}
            >
              <div className="builder-live-review-event-group">
                <strong>{selectedLiveReviewEvent.title || "Selected review event"}</strong>
                <span>{titleizeToken(selectedLiveReviewEvent.kind || "event")}</span>
              </div>
              <p className="reference-surface-footnote">{selectedLiveReviewEvent.detail || "No detail yet."}</p>
              <div className="builder-live-review-controls">
                <button
                  className="reference-outline-button"
                  onClick={() => onRequestAction?.("live:rewind-marker", { eventId: selectedLiveReviewEvent.id })}
                  type="button"
                >
                  Rewind marker
                </button>
                <button
                  className="reference-outline-button"
                  disabled={selectedScreenshotFrames.length <= 1}
                  onClick={() => {
                    const index = selectedScreenshotFrames.findIndex(frame => frame?.id === selectedScreenshotFrameId);
                    const target = selectedScreenshotFrames[index - 1] || selectedScreenshotFrames[selectedScreenshotFrames.length - 1] || null;
                    setSelectedScreenshotFrameId(target?.id || "");
                  }}
                  type="button"
                >
                  Previous frame
                </button>
                <button
                  className="reference-outline-button"
                  disabled={selectedScreenshotFrames.length <= 1}
                  onClick={() => {
                    const index = selectedScreenshotFrames.findIndex(frame => frame?.id === selectedScreenshotFrameId);
                    const target = selectedScreenshotFrames[index + 1] || selectedScreenshotFrames[0] || null;
                    setSelectedScreenshotFrameId(target?.id || "");
                  }}
                  type="button"
                >
                  Next frame
                </button>
              </div>
              <p className="reference-surface-footnote">
                Use ←/→ to step frames. {selectedScreenshotFrames.length} frame(s) tracked.
              </p>
              {selectedScreenshotFrames.length ? (
                <div className="builder-live-review-frame-strip">
                  {selectedScreenshotFrames.map((frame, index) => {
                    const active = frame?.id === selectedScreenshotFrameId;
                    return (
                      <button
                        className={cx("builder-live-review-frame-thumb", active && "active")}
                        key={frame?.id || `frame-${index}`}
                        onClick={() => setSelectedScreenshotFrameId(frame?.id || "")}
                        type="button"
                      >
                        {frame?.path ? (
                          <img
                            alt={`${frame?.label || `Frame ${index + 1}`} preview`}
                            className="builder-live-review-frame-image"
                            loading="lazy"
                            src={frame.path}
                          />
                        ) : (
                          <span className="builder-live-review-frame-image placeholder">No preview image</span>
                        )}
                        <strong>{frame?.label || `Frame ${index + 1}`}</strong>
                        <span>{frame?.timestamp || ""}</span>
                      </button>
                    );
                  })}
                </div>
              ) : null}
              {markerFrameMap.length ? (
                <div className="builder-live-review-timeline-rail">
                  <div className="builder-live-review-timeline-head">
                    <strong>Marker-to-frame timeline rail</strong>
                    <small>Direct scrubber drag and timelapse sync</small>
                  </div>
                  <input
                    aria-label="Marker timeline scrubber"
                    className="builder-live-review-scrubber"
                    max={Math.max(markerFrameMap.length - 1, 0)}
                    min={0}
                    onChange={event => {
                      const marker = markerFrameMap[Math.max(0, Number(event.target.value) || 0)] || null;
                      if (!marker) {
                        return;
                      }
                      setSelectedReplayMarkerId(marker.id || "");
                      const frame = selectedScreenshotFrames[marker.frameIndex] || null;
                      if (frame?.id) {
                        setSelectedScreenshotFrameId(frame.id);
                      }
                    }}
                    type="range"
                    value={selectedMarkerIndex}
                  />
                  <div className="builder-live-review-marker-buttons">
                    {markerFrameMap.map(marker => (
                      <button
                        className={cx("builder-live-review-marker-pill", marker.id === selectedReplayMarkerId && "active")}
                        key={marker.id}
                        onClick={() => {
                          setSelectedReplayMarkerId(marker.id || "");
                          const frame = selectedScreenshotFrames[marker.frameIndex] || null;
                          if (frame?.id) {
                            setSelectedScreenshotFrameId(frame.id);
                          }
                        }}
                        type="button"
                      >
                        <strong>{marker.label || marker.id}</strong>
                        <span>{marker.timestamp || ""}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
              {replayMarkers.length ? (
                <div className="builder-live-review-marker-jump">
                  <span>Marker jump</span>
                  <select
                    onChange={event => setSelectedReplayMarkerId(event.target.value)}
                    value={selectedReplayMarkerId}
                  >
                    {replayMarkers.map(marker => (
                      <option key={marker.id} value={marker.id}>
                        {marker.label || marker.id}
                      </option>
                    ))}
                  </select>
                  <button
                    className="reference-outline-button"
                    onClick={() =>
                      onRequestAction?.("live:jump-marker", {
                        markerId: selectedReplayMarker?.id,
                        snapshotPath: selectedReplayMarker?.snapshotPath,
                      })
                    }
                    type="button"
                  >
                    Jump to frame
                  </button>
                  <button
                    className="reference-outline-button"
                    disabled={markerFrameMap.length <= 1}
                    onClick={() => setIsTimelapsePlaying(value => !value)}
                    type="button"
                  >
                    {isTimelapsePlaying ? "Pause timelapse" : "Autoplay timelapse"}
                  </button>
                </div>
              ) : null}
              {selectedScreenshotFrame ? (
                <p className="reference-surface-footnote" aria-live="polite">
                  Frame: {selectedScreenshotFrame.label || selectedScreenshotFrame.id} · {selectedScreenshotFrame.path || "no path"}
                </p>
              ) : null}
            </div>
          ) : null}
        </article>

        <aside className="builder-live-review-sidepanel" aria-label="Live Preview Side Panel">
          <article className="builder-live-review-panel">
            <div className="builder-live-review-meta">
              <strong>Live Preview Side Panel</strong>
              <span>Selected event detail, replay hooks, and runtime payloads</span>
            </div>
            {selectedLiveReviewEvent ? (
              <div className="builder-live-review-event-details" aria-live="polite">
                <div className="builder-live-review-event-group">
                  <strong>{selectedLiveReviewEvent.title || "Selected review event"}</strong>
                  <span>
                    {titleizeToken(selectedLiveReviewEvent.kind || "event")} · {selectedLiveReviewEvent.timestamp || "now"}
                  </span>
                </div>
                <p>{selectedLiveReviewEvent.detail || "No detail yet."}</p>
                <p className="reference-surface-footnote">
                  {selectedScreenshotFrame ? `Screenshot frame: ${selectedScreenshotFrame.path || "none"}` : "No screenshot frame selected."}
                </p>
                <div className="builder-live-review-sidegroup">
                  <span>UI review hooks</span>
                  <div className="reference-inline-actions compact">
                    <button
                      className="reference-outline-button"
                      onClick={() => onRequestAction?.("live:open-proof", { sourceEventId: selectedLiveReviewEvent.id })}
                      type="button"
                    >
                      Open proof pane
                    </button>
                    <button
                      className="reference-outline-button"
                      onClick={() => onRequestAction?.("live:open-thread", { sourceEventId: selectedLiveReviewEvent.id })}
                      type="button"
                    >
                      Open thread pane
                    </button>
                    <button
                      className="reference-outline-button"
                      onClick={() =>
                        onRequestAction?.("live:open-marker-context", {
                          markerId: selectedReplayMarker?.id,
                          snapshotPath: selectedReplayMarker?.snapshotPath,
                        })
                      }
                      type="button"
                    >
                      Marker context
                    </button>
                  </div>
                </div>
                <div className="builder-live-review-sidegroup" aria-label="Live evidence">
                  <span>Live evidence</span>
                  <p className="reference-surface-footnote">Runtime, artifacts, Hermes, NAS</p>
                  <div className="reference-inline-actions compact">
                    <button className="reference-outline-button" onClick={() => onRequestAction?.("live:evidence:runtime")} type="button">
                      Runtime
                    </button>
                    <button className="reference-outline-button" onClick={() => onRequestAction?.("live:evidence:images")} type="button">
                      Artifacts
                    </button>
                    <button className="reference-outline-button" onClick={() => onRequestAction?.("live:evidence:hermes")} type="button">
                      Hermes
                    </button>
                    <button className="reference-outline-button" onClick={() => onRequestAction?.("live:evidence:nas")} type="button">
                      NAS
                    </button>
                  </div>
                </div>
                {selectedEventBrowserActions.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Browser QA actions</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventBrowserActions.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedEventPrograms.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Launched programs</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventPrograms.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedEventTests.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Verification tests</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventTests.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedEventProviderEvents.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Image provider events</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventProviderEvents.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedEventQueueTimeline.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Image queue timeline</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventQueueTimeline.map(item => <span key={item}>{titleizeToken(item)}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedEventLayerHandoff.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Layer handoff</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventLayerHandoff.map(item => <span key={item}>{titleizeToken(item)}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedEventGeneratedImages.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Generated images</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventGeneratedImages.map(item => (
                        <span key={item.path || item.label}>{item.label || item.path}</span>
                      ))}
                    </div>
                  </div>
                ) : null}
                {selectedEventArtifacts.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Artifact paths</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventArtifacts.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedEventOperatorMessages.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Operator follow-up messages</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventOperatorMessages.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedEventAcknowledgedBy.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Operator acknowledgements</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventAcknowledgedBy.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedLiveReviewEvent?.progressUpdate ? (
                  <div className="builder-live-review-sidegroup">
                    <span>10-20 minute update payload</span>
                    <p className="reference-surface-footnote">
                      Changed: {selectedLiveReviewEvent.progressUpdate.changed} · Blocker: {selectedLiveReviewEvent.progressUpdate.blocker} · Tests: {selectedLiveReviewEvent.progressUpdate.tests} · Next: {selectedLiveReviewEvent.progressUpdate.next}
                    </p>
                  </div>
                ) : null}
                <div className="builder-live-review-sidegroup builder-live-coworking-bridge">
                  <span>Co-working bridge contract</span>
                  <div className="builder-live-coworking-grid" aria-label="Structured feedback into agent mission bridge">
                    <article>
                      <b>Route/model/task context</b>
                      <small>Route: {selectedLiveReviewEvent.routeContext || selectedLiveReviewEvent.deepLink?.route || "current review route"}</small>
                      <small>Model: {selectedLiveReviewEvent.modelContext || selectedLiveReviewEvent.provider || "planner/executor default"}</small>
                      <small>Task: {selectedLiveReviewEvent.taskContext || selectedLiveReviewEvent.title || "selected event"}</small>
                    </article>
                    <article>
                      <b>Verifier feedback loop</b>
                      <small>{selectedLiveReviewEvent.verifierFeedback || selectedLiveReviewEvent.progressUpdate?.tests || "Awaiting focused verifier note"}</small>
                      <button
                        className="reference-outline-button"
                        onClick={() => onRequestAction?.("agent:structured-feedback", {
                          sourceEventId: selectedLiveReviewEvent.id,
                          routeContext: selectedLiveReviewEvent.routeContext || selectedLiveReviewEvent.deepLink?.route,
                          taskContext: selectedLiveReviewEvent.taskContext || selectedLiveReviewEvent.title,
                          verifierFeedback: selectedLiveReviewEvent.verifierFeedback || selectedLiveReviewEvent.progressUpdate?.tests,
                        })}
                        type="button"
                      >
                        Send structured feedback
                      </button>
                    </article>
                    <article>
                      <b>Activity/timelapse evidence</b>
                      <small>{selectedScreenshotFrames.length} frames · {replayMarkers.length} markers · {selectedEventArtifacts.length} artifacts</small>
                      <small>Status updates: {selectedLiveReviewEvent.progressUpdate ? "captured" : "not captured yet"}</small>
                    </article>
                  </div>
                </div>
                {selectedLiveReviewEvent?.selectedSkills?.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Planner selected skills</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedLiveReviewEvent.selectedSkills.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedLiveReviewEvent?.plannerRules?.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Planner rules</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedLiveReviewEvent.plannerRules.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedLiveReviewEvent?.designPrompts?.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Design prompts</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedLiveReviewEvent.designPrompts.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedLiveReviewEvent?.nextIdea ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Next idea handoff</span>
                    <p className="reference-surface-footnote">{selectedLiveReviewEvent.nextIdea}</p>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="reference-surface-footnote">Select a live review event to inspect detail.</p>
            )}
          </article>

          <article className="builder-live-review-panel">
            <div className="builder-live-review-meta">
              <strong>Browser annotations</strong>
              <span>Pins, rectangles, severity, notes, and recovery actions</span>
            </div>
            <div className="builder-live-annotation-map">
              {annotations.map(item => item.rectangle ? (
                <span
                  className="builder-live-annotation-rect"
                  key={`${item.id}-rect`}
                  style={{ left: `${item.rectangle.x}%`, top: `${item.rectangle.y}%`, width: `${item.rectangle.width}%`, height: `${item.rectangle.height}%` }}
                />
              ) : (
                <span
                  className="builder-live-annotation-pin"
                  key={`${item.id}-pin`}
                  style={{ left: `${item.pin?.x || 0}%`, top: `${item.pin?.y || 0}%` }}
                />
              ))}
            </div>
            <div className="builder-live-annotation-list">
              {annotations.length ? annotations.map(item => (
                <article className={cx("builder-live-annotation-item", `severity-${item.severity || "low"}`)} key={item.id}>
                  <div className="builder-live-review-event-group">
                    <strong>{item.label}</strong>
                    <span>{titleizeToken(item.severity)}</span>
                  </div>
                  <p>{item.note}</p>
                  <p className="reference-surface-footnote">Page/layer: {item.page || "unknown"} · {item.rectangle?.layer || item.pin?.layer || "preview"}</p>
                  <p className="reference-surface-footnote">Recovery: {item.recoveryAction}</p>
                </article>
              )) : <p className="reference-surface-footnote">No annotation targets yet.</p>}
            </div>
          </article>
        </aside>
      </div>

      <div className="reference-settings-grid">
        <article className="reference-settings-card">
          <strong>Computer-use readiness</strong>
          <div className={cx("reference-workbench-state-card", `tone-${computerState.tone}`)}>
            <div className="reference-workbench-state-head">
              <p className="reference-workbench-state-kicker">State · {titleizeToken(computerState.key)}</p>
              <strong>{computerState.title}</strong>
            </div>
            <p>{computerState.body}</p>
            <div className="reference-workbench-state-meta">
              <p className="reference-surface-footnote">Current screen: {computerUse.currentScreen || "Not reported"}</p>
              <p className="reference-surface-footnote">Current task: {computerUse.currentTask || "Not reported"}</p>
            </div>
            <div className="reference-inline-actions stretch">
              {computerState.actions.map(action => (
                <button
                  className={action.id === "agent:follow-up" ? "reference-black-button" : "reference-outline-button"}
                  key={action.id}
                  onClick={() => {
                    if (action.id === "agent:follow-up") {
                      onSetSurface?.("agent");
                      return;
                    }
                    onRequestAction?.(action.id);
                  }}
                  type="button"
                >
                  {action.label}
                </button>
              ))}
            </div>
          </div>
        </article>

        <article className="reference-settings-card">
          <strong>Notification layer</strong>
          <div className="reference-builder-change-list">
            {notificationEvents.map(item => (
              <div className="reference-builder-change-row" key={item.id}>
                <span className={cx("reference-flow-dot", item.count > 0 ? "warn" : "good")} />
                <p>
                  {item.label}: {item.count} · {item.detail}
                </p>
              </div>
            ))}
          </div>
          <button className="reference-outline-button" onClick={() => onRequestAction?.("workbench:notification-settings")} type="button">Configure digest + events</button>
        </article>
      </div>

      <article className="reference-settings-card">
        <strong>Modular playgrounds</strong>
        <div className="reference-provider-grid">
          {playgrounds.map(item => (
            <article className="reference-provider-card" key={item.id}>
              <strong>{item.label}</strong>
              <p>Status: {titleizeToken(item.status)}</p>
              <button
                className="reference-link-button"
                onClick={() => {
                  if (item.id === "image") {
                    onSetSurface?.("images");
                    return;
                  }
                  onRequestAction?.(`workbench:${item.action || item.id}`);
                }}
                type="button"
              >
                Open
              </button>
            </article>
          ))}
        </div>
      </article>

      <div className="reference-settings-grid">
        <article className="reference-settings-card">
          <strong>Code study and coverage</strong>
          <p>{coverage.summary || "Coverage summary unavailable."}</p>
          <p className="reference-surface-footnote">Known gaps: {coverage.gapCount || 0}</p>
          <div className="reference-builder-change-list">
            {asList(coverage.files).length ? asList(coverage.files).map(item => <div className="reference-builder-change-row" key={item}><p>{item}</p></div>) : <p className="reference-surface-footnote">No files surfaced yet.</p>}
          </div>
          <button className="reference-outline-button" onClick={() => onRequestAction?.("workbench:study-plan")} type="button">Generate study plan</button>
        </article>

        <article className="reference-settings-card">
          <strong>Tutorials and onboarding</strong>
          <p>{tutorials.headline || "Contextual onboarding"}</p>
          <div className="reference-builder-change-list">
            {asList(tutorials.steps).map(step => (
              <div className="reference-builder-change-row" key={step.id || step.title}>
                <span className={cx("reference-flow-dot", step.done ? "good" : step.current ? "warn" : "neutral")} />
                <p>{step.title} · {step.status}</p>
              </div>
            ))}
          </div>
          <button className="reference-outline-button" onClick={() => onRequestAction?.("workbench:tutorial-help")} type="button">Open contextual help</button>
        </article>
      </div>

      <div className="reference-settings-grid">
        <article className="reference-settings-card">
          <strong>Idea generation loop</strong>
          <p>{ideaPlanner.headline || "Planner"}</p>
          <div className="reference-builder-change-list">
            {asList(ideaPlanner.ideas).map(item => (
              <div className="reference-builder-change-row" key={item.id}>
                <p>{item.title} · score {item.score} · {item.reason}</p>
              </div>
            ))}
          </div>
          <button className="reference-black-button" onClick={() => onRequestAction?.("workbench:promote-idea")} type="button">Promote selected idea to mission</button>
        </article>

        <article className="reference-settings-card">
          <strong>Multi-mission lanes and model flexibility</strong>
          <p className="reference-surface-footnote">Lanes can run concurrently with independent runtime/provider/model selections.</p>
          <div className="reference-builder-change-list">
            {lanes.length ? lanes.map(item => (
              <div className="reference-builder-change-row" key={item.id}>
                <p>{item.label} · {item.provider}/{item.model} · {item.status} · {item.lastEvent}</p>
              </div>
            )) : <p className="reference-surface-footnote">No active lanes from backend snapshot.</p>}
          </div>
          <p className="reference-surface-footnote">Available providers: {asList(providerCatalog.providers).join(", ") || "none"}</p>
        </article>
      </div>
    </section>
  );
}

function ComposerDock({
  compact = false,
  draft,
  onChangeDraft,
  onPaste,
  onAttach,
  onDictation,
  onSubmit,
  placeholder,
  children,
}) {
  return (
    <form className={cx("reference-composer", compact && "compact")} onSubmit={event => event.preventDefault()}>
      <textarea
        onChange={event => onChangeDraft(event.target.value)}
        onKeyDown={event => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            onSubmit?.();
          }
        }}
        onPaste={onPaste}
        placeholder={placeholder}
        value={draft}
      />
      {children}
      <div className="reference-composer-footer">
        <div className="reference-composer-tools">
          <button className="reference-tool-button" onClick={onAttach} type="button">
            <Paperclip size={18} strokeWidth={1.9} />
          </button>
          <button className="reference-tool-button" onClick={onDictation} type="button">
            <Mic size={18} strokeWidth={1.9} />
          </button>
        </div>
        <button className="reference-send-button" onClick={onSubmit} type="button">
          <ArrowUp size={22} strokeWidth={2.1} />
        </button>
      </div>
    </form>
  );
}

function ConfigCard({ title, titleIcon: Icon, accent = "neutral", children, footer, copy }) {
  return (
    <article className={cx("reference-config-card", `tone-${accent}`)}>
      <div className="reference-config-card-head">
        <div className="reference-config-title">
          <Icon size={18} strokeWidth={1.9} />
          <strong>{title}</strong>
        </div>
        <CircleHelp size={15} strokeWidth={1.8} />
      </div>
      <div className="reference-config-card-body">{children}</div>
      {copy ? <p className="reference-config-copy">{copy}</p> : null}
      {footer ? <div className="reference-config-footer">{footer}</div> : null}
    </article>
  );
}

function MetricLine({ label, value }) {
  return (
    <div className="reference-inline-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function LiveOperationsBrief({
  activeRows = [],
  liveDataStatus,
  onOpenAgent,
  onOpenNotifications,
  onOpenQueue,
  projectProgressHistory,
  queueRows: explicitQueueRows = [],
  threadRows = [],
  workbenchState,
}) {
  if (liveDataStatus?.previewMode !== "live") {
    return null;
  }
  const progressValue = clampPercent(workbenchState?.progress?.value);
  const progressKind = String(workbenchState?.progress?.progressKind || "").trim();
  const progressLabel = String(workbenchState?.progress?.label || "").trim();
  const progressIsCompletion = workbenchState?.progress?.displayAsCompletion !== false;
  const progressStateLabel =
    progressLabel ||
    (progressKind === "runtime_budget_exhausted"
      ? "Runtime budget exhausted"
      : progressKind === "proof_repair"
        ? "Proof repair readiness"
        : progressIsCompletion
          ? "Progress"
          : "Non-completion progress");
  const visibleThreadRows = asList(threadRows).filter(item => !isLowSignalAgentMessage(item)).slice(0, 3);
  const latestThreadRow =
    visibleThreadRows[0] ||
    (liveDataStatus?.previewMode === "live"
      ? null
      : asList(workbenchState?.agentThreadPreview).find(Boolean) || null);
  const queueRows = asList(explicitQueueRows).length
    ? asList(explicitQueueRows)
    : asList(projectProgressHistory?.schedulingQueue);
  const topQueueRow = queueRows[0] || null;
  const activeCount = Number(liveDataStatus?.activeMissionCount || activeRows.length || 0);
  const runningCount = Number(liveDataStatus?.runningMissionCount || 0);
  const attentionCount = Math.max(0, activeCount - runningCount);
  const notificationCount = Number(liveDataStatus?.notificationCount || 0);
  const sliceNotificationCount = Number(liveDataStatus?.sliceNotificationCount || 0);
  const latestDetail = latestThreadRow
    ? agentPreviewDetail(latestThreadRow)
    : workbenchState?.progress?.nextAction || "Waiting for the next live mission update.";
  const compactLatestDetail = String(latestDetail || "")
    .replace(/^Runtime output:\s*/i, "")
    .replace(/^#+\s*/g, "")
    .replace(/\s+/g, " ")
    .trim();
  const briefDetail = compactLatestDetail.length > 210
    ? `${compactLatestDetail.slice(0, 207).trim()}...`
    : compactLatestDetail;
  const sourceLabel = liveDataStatus?.summaryCache?.status === "hit"
    ? "warm NAS summary"
    : liveDataStatus?.source || "control-room summary";
  return (
    <section className="fluxos-live-operations-brief" aria-label="Live operations brief" data-live-operations-brief="true">
      <div className="fluxos-live-brief-main">
        <span>{sourceLabel}</span>
        <strong>{workbenchState?.missionTitle || `${activeCount} active live mission${activeCount === 1 ? "" : "s"}`}</strong>
        <p title={compactLatestDetail}>{briefDetail}</p>
      </div>
      <div className="fluxos-live-brief-metrics">
        <div
          className={!progressIsCompletion ? "non-completion-progress" : ""}
          data-brief-progress-kind={progressKind || undefined}
        >
          <span>{progressIsCompletion ? "Progress" : "State"}</span>
          <strong>{progressValue == null ? "No %" : `${progressValue}%`}</strong>
          <em>{progressStateLabel}</em>
        </div>
        <div>
          <span>Active</span>
          <strong>{activeCount}</strong>
          <em>{runningCount ? `${runningCount} running` : `${attentionCount} attention`}</em>
        </div>
        <div>
          <span>Queue</span>
          <strong>{queueRows.length}</strong>
        </div>
        <div>
          <span>Alerts</span>
          <strong>{notificationCount}</strong>
          <em>{sliceNotificationCount} slice</em>
        </div>
      </div>
      <div className="fluxos-live-brief-actions">
        <button disabled={!workbenchState?.missionId || !onOpenAgent} onClick={onOpenAgent} type="button">Agent</button>
        <button disabled={!topQueueRow?.workspaceId || !onOpenQueue} onClick={onOpenQueue} type="button">Queue</button>
        <button disabled={notificationCount <= 0 || !onOpenNotifications} onClick={onOpenNotifications} type="button">Notify</button>
      </div>
    </section>
  );
}

function LiveGuidedNextSteps({
  liveDataStatus,
  onOpenAgent,
  onOpenNotifications,
  onOpenProof,
  onOpenQueue,
  queueRows = [],
  threadRows = [],
  workbenchState,
}) {
  if (liveDataStatus?.previewMode !== "live") {
    return null;
  }
  const hasThreadRows = asList(threadRows).length > 0;
  const hasQueueRows = asList(queueRows).length > 0;
  const hasNotifications = Number(liveDataStatus?.notificationCount || 0) > 0;
  const progressValue = clampPercent(workbenchState?.progress?.value);
  const proofReady = progressValue != null || asList(workbenchState?.proofDiff?.rows).length > 0;
  const steps = [
    {
      id: "agent-report",
      label: "Read current Agent report",
      detail: hasThreadRows
        ? "The live mission has selectable Hermes/runtime report rows."
        : "Open Agent when the NAS detail endpoint returns report rows.",
      status: hasThreadRows ? "ready" : "waiting",
      action: onOpenAgent,
      actionLabel: "Open Agent",
      disabled: !workbenchState?.missionId || !onOpenAgent,
    },
    {
      id: "queue",
      label: "Check multi-project queue",
      detail: hasQueueRows
        ? `${asList(queueRows).length} dependency-aware project rows are ranked by the NAS scheduler.`
        : "No ranked queue rows are available in the live summary.",
      status: hasQueueRows ? "ready" : "waiting",
      action: onOpenQueue,
      actionLabel: "Open queue",
      disabled: !hasQueueRows || !onOpenQueue,
    },
    {
      id: "notifications",
      label: "Keep progress notifications visible",
      detail: hasNotifications
        ? `${Number(liveDataStatus.notificationCount || 0)} live alerts, including ${Number(liveDataStatus.sliceNotificationCount || 0)} slice alerts.`
        : "No visible live alerts are pending.",
      status: hasNotifications ? "ready" : "waiting",
      action: onOpenNotifications,
      actionLabel: "Show alerts",
      disabled: !hasNotifications || !onOpenNotifications,
    },
    {
      id: "proof",
      label: "Review proof before trusting output",
      detail: proofReady
        ? "Progress/proof evidence exists for the selected live mission."
        : "Wait for the next mission proof or runtime event before closing the loop.",
      status: proofReady ? "ready" : "waiting",
      action: onOpenProof,
      actionLabel: "Open proof",
      disabled: !onOpenProof,
    },
  ];
  return (
    <section className="fluxos-guided-next-steps" aria-label="Live guided next steps" data-live-guided-next-steps="true">
      <div className="fluxos-section-head">
        <span>Guided next steps</span>
        <strong>{workbenchState?.missionTitle || "Live mission path"}</strong>
      </div>
      <div className="fluxos-guided-step-list">
        {steps.map((step, index) => (
          <article className={`status-${step.status}`} data-guided-step={step.id} key={step.id}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <div>
              <strong>{step.label}</strong>
              <p>{step.detail}</p>
            </div>
            <button disabled={step.disabled} onClick={step.action} type="button">{step.actionLabel}</button>
          </article>
        ))}
      </div>
    </section>
  );
}

function LiveOperatorTutorialPath({
  liveDataStatus,
  onOpenAgent,
  onOpenNotifications,
  onOpenProof,
  onOpenQueue,
  queueRows = [],
  threadRows = [],
  workbenchState,
}) {
  if (liveDataStatus?.previewMode !== "live") {
    return null;
  }
  const queueCount = asList(queueRows).length;
  const threadCount = asList(threadRows).length;
  const notificationCount = Number(liveDataStatus?.notificationCount || 0);
  const sliceNotificationCount = Number(liveDataStatus?.sliceNotificationCount || 0);
  const progressValue = clampPercent(workbenchState?.progress?.value);
  const proofRows = asList(workbenchState?.proofDiff?.rows).length;
  const milestones = [
    {
      id: "mission",
      label: "Pick the active mission",
      detail: workbenchState?.missionTitle || `${Number(liveDataStatus?.runningMissionCount || 0)} running mission rows from the NAS.`,
      done: Boolean(workbenchState?.missionId || workbenchState?.missionTitle),
      action: onOpenAgent,
      actionLabel: "Open mission",
      disabled: !workbenchState?.missionId || !onOpenAgent,
    },
    {
      id: "queue",
      label: "Check project order",
      detail: queueCount ? `${queueCount} scheduler rows are ranked by dependency and root safety.` : "No live scheduler rows returned for this refresh.",
      done: queueCount > 0,
      action: onOpenQueue,
      actionLabel: "Queue",
      disabled: queueCount <= 0 || !onOpenQueue,
    },
    {
      id: "agent",
      label: "Read the Agent report",
      detail: threadCount ? `${threadCount} current Hermes/runtime report rows are ready.` : "Open Agent after the mission detail endpoint returns report rows.",
      done: threadCount > 0,
      action: onOpenAgent,
      actionLabel: "Agent",
      disabled: !workbenchState?.missionId || !onOpenAgent,
    },
    {
      id: "notifications",
      label: "Keep progress visible",
      detail: `${notificationCount} live notifications, including ${sliceNotificationCount} slice completions.`,
      done: notificationCount > 0,
      action: onOpenNotifications,
      actionLabel: "Alerts",
      disabled: notificationCount <= 0 || !onOpenNotifications,
    },
    {
      id: "proof",
      label: "Trust only after proof",
      detail: progressValue != null || proofRows
        ? `${progressValue == null ? "No %" : `${progressValue}%`} progress · ${proofRows} proof rows.`
        : "Wait for a progress value, proof row, or runtime evidence before closing the loop.",
      done: progressValue != null || proofRows > 0,
      action: onOpenProof,
      actionLabel: "Proof",
      disabled: !onOpenProof,
    },
  ];
  const completedCount = milestones.filter(item => item.done).length;
  return (
    <section className="fluxos-live-tutorial-path" aria-label="Live operator tutorial path" data-live-tutorial-path="true">
      <div className="fluxos-section-head">
        <span>Live operator tutorial</span>
        <strong>{completedCount}/{milestones.length} steps ready</strong>
      </div>
      <p>
        This path is built from current NAS mission, queue, Agent, notification, and proof data. It renders no sample tutorial steps.
      </p>
      <div className="fluxos-live-tutorial-steps">
        {milestones.map((step, index) => (
          <article className={step.done ? "done" : "waiting"} data-live-tutorial-step={step.id} key={step.id}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <div>
              <strong>{step.label}</strong>
              <p>{step.detail}</p>
            </div>
            <button disabled={step.disabled} onClick={step.action} type="button">{step.actionLabel}</button>
          </article>
        ))}
      </div>
    </section>
  );
}

function RuntimeCapabilityPills({ capabilities = [] }) {
  if (!capabilities.length) {
    return <p className="reference-surface-footnote">No runtime capabilities were reported yet.</p>;
  }
  return (
    <div className="reference-chip-row">
      {capabilities.map(item => (
        <span className="reference-mini-pill" key={item.key || item.label}>
          {item.label}
        </span>
      ))}
    </div>
  );
}

function SlashCommandPanel({ className, commands = [], draft = "", onUseCommand }) {
  const query = String(draft || "").trim().toLowerCase();
  const filteredCommands = query.startsWith("/")
    ? commands.filter(item => {
        const haystack = `${item.command} ${item.label || ""} ${item.detail || ""} ${item.harness || ""} ${item.kind || ""}`.toLowerCase();
        return haystack.includes(query);
      })
    : commands;
  const priorityFor = item => {
    const kind = String(item.kind || "").toLowerCase();
    if (kind === "comment") {
      return 0;
    }
    if (kind === "skill") {
      return 1;
    }
    if (kind === "codex") {
      return 3;
    }
    return 2;
  };
  const visibleCommands = filteredCommands
    .slice()
    .sort((left, right) => priorityFor(left) - priorityFor(right))
    .slice(0, 8);
  const commandTitle = item => item.label || item.command;
  const commandBadge = item => {
    const kind = String(item.kind || item.harness || "command").toLowerCase();
    if (kind === "skill") {
      return "S";
    }
    if (kind === "comment") {
      return "C";
    }
    if (kind === "codex") {
      return "Cx";
    }
    return "/";
  };

  return (
    <article className={cx("reference-support-panel reference-slash-panel", className)}>
      <div className="reference-builder-section-head">
        <div>
          <strong>Slash Commands</strong>
          <span>
            {query.startsWith("/")
              ? "Filtered by the composer. Clicking inserts the command."
              : "Built from the active runtime command catalog and local installed skills."}
          </span>
        </div>
      </div>
      {visibleCommands.length > 0 ? (
        <div className="reference-command-grid">
          {visibleCommands.map(item => (
            <button
              className={cx("reference-command-card", item.kind && `kind-${item.kind}`)}
              key={`${item.harness}-${item.command}`}
              onClick={() => onUseCommand(item.command)}
              type="button"
            >
              <div className="reference-command-head">
                <span className="reference-command-token">{commandBadge(item)}</span>
                <strong>{commandTitle(item)}</strong>
                <span>{item.harness}</span>
              </div>
              {item.label ? <code>{item.command}</code> : null}
              <p>{item.detail}</p>
            </button>
          ))}
        </div>
      ) : (
        <p className="reference-surface-footnote">No slash commands match the current draft.</p>
      )}
    </article>
  );
}

function SettingsSurface({ onRequestAction, settingsState }) {
  const {
    activeRuleSet,
    activeTab = "general",
    appearance,
    authOptions = { openai: [], minimax: [] },
    codexImport = {
      available: false,
      recentThreads: [],
      workspaces: [],
      notes: [],
      sessionCount: 0,
      skillCount: 0,
    },
    members = [],
    onImportAllCodexWorkspaces,
    onImportCodexWorkspace,
    onPickWorkspaceFolder,
    onRefreshCodexImport,
    onApplyActiveRuleSet,
    onRouteOverrideChange,
    onSaveWorkspacePolicy,
    onSetAppearance,
    onSetTab,
    onWorkspaceProfileFieldChange,
    privacy = { conversationRetention: "90 days", fileRetention: "30 days" },
    providers = [],
    bridgeSessions = [],
    storageBridge = {},
    setupServices = [],
    beginnerSetupCards = [],
    safeUpdateAction = null,
    chatgptConnection = {},
    routeOptions = { harnesses: [], providers: [], efforts: [], models: [], routingStrategies: [], executionTargets: [] },
    runtimes = [],
    sidebarBehaviorOptions = [],
    workspaceId,
    workspaceName,
    workspaceProfileForm = {
      userProfile: "builder",
      preferredHarness: "",
      openaiCodexAuthMode: "none",
      minimaxAuthMode: "none",
      routingStrategy: "profile_default",
      executionTargetPreference: "workspace_root",
      routeOverrides: [],
    },
  } = settingsState;
  const tabDefs = [
    ["general", "General", Settings],
    ["providers", "Models & Accounts", Sparkles],
    ["storage", "Storage", Database],
    ["tools", "Tools & Ports", SquareTerminal],
    ["rules", "Rules & Routing", Shield],
    ["members", "Members", Users],
    ["privacy", "Data & Privacy", Database],
  ];
  const previewSwatches = [
    ["Primary accent", appearance.accent],
    ["Secondary accent", appearance.accentAlt],
    ["Surface", appearance.surface],
    ["Card surface", appearance.surfaceSoft],
  ];
  const appearancePresets = [
    {
      id: "graphite-gold",
      name: "Graphite Gold",
      description: "Black, gray, and restrained gold. This is the Syntelos default.",
      values: {
        accent: "#d6a84f",
        accentAlt: "#9aa3a0",
        surface: "#ffffff",
        surfaceSoft: "#f6f8fc",
        line: "#d8deea",
        text: "#121826",
        stylePreset: "graphite-gold",
      },
    },
    {
      id: "operator-dark",
      name: "Operator Dark",
      description: "Dense dark control room with gold action focus.",
      values: {
        accent: "#d6a84f",
        accentAlt: "#7ed996",
        surface: "#121514",
        surfaceSoft: "#1a1e1c",
        line: "#343a37",
        text: "#f7f1e8",
        stylePreset: "operator-dark",
      },
    },
    {
      id: "school-calm",
      name: "School Calm",
      description: "Low-noise classroom preset for tutorials and guided users.",
      values: {
        accent: "#b98a35",
        accentAlt: "#667085",
        surface: "#f7f7f2",
        surfaceSoft: "#ffffff",
        line: "#d8dccf",
        text: "#171b1a",
        stylePreset: "school-calm",
      },
    },
    {
      id: "neo-brutalist",
      name: "Neo Brutalist",
      description: "Paper, hard ink, loud panels, and physical controls.",
      values: {
        accent: "#f4c430",
        accentAlt: "#ff6b4a",
        surface: "#fff8dc",
        surfaceSoft: "#f2ead0",
        line: "#111111",
        text: "#101010",
        stylePreset: "neo-brutalist",
      },
    },
    {
      id: "blueprint-lab",
      name: "Blueprint Lab",
      description: "Technical blueprints, cyan lines, and calm engineering surfaces.",
      values: {
        accent: "#58c7f3",
        accentAlt: "#f4c430",
        surface: "#071827",
        surfaceSoft: "#0e2a3d",
        line: "#5ec8ef",
        text: "#e8fbff",
        stylePreset: "blueprint-lab",
      },
    },
    {
      id: "signal-bloom",
      name: "Signal Bloom",
      description: "Warm paper, coral actions, mint status, and editorial energy.",
      values: {
        accent: "#ff6b4a",
        accentAlt: "#48bf84",
        surface: "#fff2e1",
        surfaceSoft: "#ffe1d6",
        line: "#2a211b",
        text: "#1f1712",
        stylePreset: "signal-bloom",
      },
    },
    {
      id: "console-candy",
      name: "Console Candy",
      description: "Bright terminal rhythm with saturated rails and readable dark panels.",
      values: {
        accent: "#8df15a",
        accentAlt: "#ff5fa2",
        surface: "#0e1014",
        surfaceSoft: "#181c22",
        line: "#2f3745",
        text: "#f7fbff",
        stylePreset: "console-candy",
      },
    },
    {
      id: "cel-rig",
      name: "Cel Rig",
      description: "Animation-cel flats, keyline shadows, timing marks, and clean color holds.",
      values: {
        accent: "#2f6bff",
        accentAlt: "#ffcf3f",
        surface: "#f8fbff",
        surfaceSoft: "#dceaff",
        line: "#101820",
        text: "#101820",
        stylePreset: "cel-rig",
      },
    },
    {
      id: "texture-board",
      name: "Texture Board",
      description: "Material swatches, paper grain, region labels, and tactile output checks.",
      values: {
        accent: "#7a5c34",
        accentAlt: "#4f8f6b",
        surface: "#f5ead7",
        surfaceSoft: "#e8d4b3",
        line: "#2b2118",
        text: "#201812",
        stylePreset: "texture-board",
      },
    },
    {
      id: "style-bible",
      name: "Style Bible",
      description: "Reference sheets for palette, line weight, texture, staging, and motion timing.",
      values: {
        accent: "#b84cff",
        accentAlt: "#16b8a6",
        surface: "#fbf7ff",
        surfaceSoft: "#efe2ff",
        line: "#24152d",
        text: "#201426",
        stylePreset: "style-bible",
      },
    },
  ];
  const applyAppearancePreset = preset => {
    Object.entries(preset.values).forEach(([key, value]) => onSetAppearance(key, value));
  };
  const bridgePortRows = asList(bridgeSessions).map(session => {
    const endpoint = String(session.bridge_endpoint || session.bridgeEndpoint || "");
    let host = endpoint || "local";
    let port = "";
    try {
      const parsed = new URL(endpoint);
      host = parsed.hostname || endpoint;
      port = parsed.port || (parsed.protocol === "https:" ? "443" : parsed.protocol === "http:" ? "80" : "");
    } catch {
      const match = endpoint.match(/:(\d+)(?:\/|$)/);
      port = match?.[1] || "";
    }
    return {
      id: session.app_id || session.session_id || endpoint,
      label: session.app_name || session.app_id || "Bridge",
      role: session.ui_hints?.bridgeRole || session.serviceRole || session.bridge_transport || "bridge",
      host,
      port: port || session.ui_hints?.controlPort || session.latest_task_result?.payload?.controlPort || "",
      status: session.bridge_health || session.status || "unknown",
      actions: asList(session.serviceActions),
    };
  });
  const managedServiceRows = asList(setupServices).map(service => ({
    id: service.serviceId || service.label,
    label: service.label || service.serviceId,
    role: service.serviceRole || service.serviceCategory || service.installSource || "service",
    host: service.bridgeEndpoint || service.installSource || service.version || "local",
    port: service.controlPort || service.port || "",
    status: service.currentHealthStatus || service.lastVerificationResult || "unknown",
    actions: asList(service.serviceActions),
  }));
  const managementRows = Array.from(
    [...bridgePortRows, ...managedServiceRows].filter(item => item.id).reduce((rows, item) => {
      const existing = rows.get(item.id);
      if (!existing) {
        rows.set(item.id, item);
        return rows;
      }
      rows.set(item.id, {
        ...existing,
        ...item,
        host: item.host || existing.host,
        port: item.port || existing.port,
        status: item.status || existing.status,
        actions: [...asList(existing.actions), ...asList(item.actions)],
      });
      return rows;
    }, new Map()).values(),
  );
  const collectBridgeActions = matcher => {
    const seen = new Set();
    return managementRows.flatMap(row =>
      asList(row.actions).map(action => ({ ...action, serviceLabel: row.label, serviceRole: row.role })),
    ).filter(action => {
      const key = `${action.actionId || action.label}-${action.commandSurface || ""}-${action.serviceRole || ""}`;
      if (seen.has(key) || !matcher(action)) {
        return false;
      }
      seen.add(key);
      return true;
    });
  };
  const nasActions = collectBridgeActions(action =>
    /nas|sync|ssh|fast/i.test(`${action.serviceRole || ""} ${action.actionId || ""} ${action.label || ""}`),
  );
  const cloudActions = collectBridgeActions(action =>
    /cloud|drive|google/i.test(`${action.serviceRole || ""} ${action.actionId || ""} ${action.label || ""}`),
  );
  const storageQuickActions = [...nasActions, ...cloudActions].slice(0, 6);

  return (
    <section className="reference-settings-surface">
      <div className="reference-settings-header">
        <div>
          <h1>Settings</h1>
          <p>Manage your workspace, models, setup, appearance, and privacy.</p>
        </div>
      </div>

      <div className="reference-settings-tabs">
        {tabDefs.map(([id, label, Icon]) => (
          <button
            className={activeTab === id ? "active" : ""}
            key={id}
            onClick={() => onSetTab(id)}
            type="button"
          >
            <Icon size={15} strokeWidth={1.9} />
            <span>{label}</span>
          </button>
        ))}
      </div>

      {activeTab === "general" ? (
        <div className="reference-settings-general-layout">
          <div className="reference-settings-stack-column">
            <article className="reference-settings-card">
              <strong>Workspace</strong>
              <SurfaceField label="Workspace Name">
                <div className="reference-static-value">{workspaceName}</div>
              </SurfaceField>
              <SurfaceField label="Workspace ID">
                <div className="reference-static-value">{workspaceId}</div>
              </SurfaceField>
              <SurfaceField label="Workspace profile">
                <select
                  onChange={event => onWorkspaceProfileFieldChange("userProfile", event.target.value)}
                  value={workspaceProfileForm.userProfile}
                >
                  <option value="beginner">Beginner</option>
                  <option value="builder">Builder</option>
                  <option value="advanced">Advanced</option>
                  <option value="experimental">Experimental</option>
                </select>
              </SurfaceField>
              <SurfaceField label="Preferred work engine">
                <select
                  onChange={event => onWorkspaceProfileFieldChange("preferredHarness", event.target.value)}
                  value={workspaceProfileForm.preferredHarness}
                >
                  {routeOptions.harnesses.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </SurfaceField>
              <SurfaceField label="NAS sync mode">
                <select
                  onChange={event => {
                    const enabled = event.target.value !== "manual";
                    onWorkspaceProfileFieldChange("syncMode", event.target.value);
                    onWorkspaceProfileFieldChange("autoSyncToNas", enabled);
                  }}
                  value={workspaceProfileForm.syncMode || "manual"}
                >
                  <option value="manual">Manual</option>
                  <option value="auto_nas_mirror">Auto NAS mirror</option>
                  <option value="synology_drive">Synology Drive</option>
                </select>
              </SurfaceField>
              <SurfaceField label="Computer folder">
                <input
                  onChange={event => onWorkspaceProfileFieldChange("localProjectPath", event.target.value)}
                  placeholder="C:/Users/paul/Projects/my-project"
                  value={workspaceProfileForm.localProjectPath || ""}
                />
              </SurfaceField>
              <SurfaceField label="NAS mirror folder">
                <input
                  onChange={event => onWorkspaceProfileFieldChange("nasProjectPath", event.target.value)}
                  placeholder="/volume1/Saclay/projects/my-project"
                  value={workspaceProfileForm.nasProjectPath || ""}
                />
              </SurfaceField>
              <SurfaceField label="Sync direction">
                <select
                  onChange={event => onWorkspaceProfileFieldChange("syncDirection", event.target.value)}
                  value={workspaceProfileForm.syncDirection || "bidirectional"}
                >
                  <option value="bidirectional">Bidirectional</option>
                  <option value="local_to_nas">Local to NAS</option>
                  <option value="nas_to_local">NAS to local</option>
                </select>
              </SurfaceField>
              <div className="reference-settings-actions">
                <button className="reference-black-button" onClick={onSaveWorkspacePolicy} type="button">
                  Save changes
                </button>
              </div>
            </article>

            <article className="reference-settings-card">
              <div className="reference-builder-section-head">
                <div>
                  <strong>Codex projects and folders</strong>
                  <span>
                    Bring over recent Codex folders, inspect recent threads, and add a project folder.
                  </span>
                </div>
                <div className="reference-inline-actions">
                  <button
                    className="reference-outline-button"
                    disabled={codexImport.isRefreshing}
                    onClick={onRefreshCodexImport}
                    type="button"
                  >
                    {codexImport.isRefreshing ? "Scanning..." : "Refresh"}
                  </button>
                  <button className="reference-outline-button" onClick={onPickWorkspaceFolder} type="button">
                    <FolderOpen size={16} strokeWidth={1.9} />
                    <span>Add folder</span>
                  </button>
                  <button
                    className="reference-black-button"
                    disabled={!asList(codexImport.workspaces).length}
                    onClick={onImportAllCodexWorkspaces}
                    type="button"
                  >
                    Import all
                  </button>
                </div>
              </div>
              <div className="reference-settings-summary-grid">
                <article><span>Codex home</span><strong>{codexImport.codexHome || "Not found"}</strong></article>
                <article><span>Recent threads</span><strong>{codexImport.sessionCount || 0}</strong></article>
                <article><span>Detected workspaces</span><strong>{asList(codexImport.workspaces).length}</strong></article>
                <article><span>Local skills</span><strong>{codexImport.skillCount || 0}</strong></article>
              </div>
              {asList(codexImport.notes).length ? (
                <div className="reference-note-stack">
                  {codexImport.notes.map(note => (
                    <p className="reference-surface-footnote" key={note}>{note}</p>
                  ))}
                </div>
              ) : null}
              {codexImport.isRefreshing && !asList(codexImport.workspaces).length ? (
                <p className="reference-surface-footnote">
                  Scanning Codex sources in the background. The rest of Settings is ready to use.
                </p>
              ) : null}
              <div className="reference-provider-grid codex">
                {asList(codexImport.workspaces).map(item => (
                  <article className="reference-provider-card" key={item.path}>
                    <div className="reference-builder-section-head">
                      <div>
                        <strong>{item.name}</strong>
                        <span>{item.path}</span>
                      </div>
                      <StatusBadge label={`${item.threadCount || 0} threads`} tone="completed" />
                    </div>
                    <p>{item.latestThreadName || "Recent Codex workspace"}</p>
                    <div className="reference-inline-actions stretch">
                      <button className="reference-black-button" onClick={() => onImportCodexWorkspace(item)} type="button">
                        Import folder
                      </button>
                    </div>
                  </article>
                ))}
              </div>
              {asList(codexImport.recentThreads).length ? (
                <div className="reference-studio-chat compact">
                  {codexImport.recentThreads.slice(0, 6).map(thread => (
                    <article className="reference-studio-chat-row" key={thread.id}>
                      <div className="reference-feedback-meta">
                        <strong>{thread.threadName}</strong>
                        <span>{thread.updatedAt || "Recent"}</span>
                      </div>
                      <p>{thread.cwd || thread.source || "No workspace path recorded."}</p>
                    </article>
                  ))}
                </div>
              ) : null}
            </article>
          </div>

          <div className="reference-settings-stack-column">
            <article className="reference-settings-card">
              <div className="reference-builder-section-head">
                <div>
                  <strong>Ready Tonight</strong>
                  <span>Four lights: computer tools, AI accounts, agent runtimes, and messages.</span>
                </div>
                {safeUpdateAction ? (
                  <button
                    className="reference-outline-button"
                    onClick={() => fluxioAction(onRequestAction, "setup:run-action", safeUpdateAction)}
                    type="button"
                  >
                    Update everything
                  </button>
                ) : null}
              </div>
              <div className="reference-ready-tonight-grid" data-ready-tonight-setup="true">
                {asList(beginnerSetupCards).length ? asList(beginnerSetupCards).map(card => {
                  const status = String(card.status || "").toLowerCase();
                  const tone = status.includes("ready") || status.includes("update") ? "good" : status.includes("failed") ? "bad" : "warn";
                  const action = card.primaryAction || {};
                  return (
                    <article className={`tone-${tone}`} data-ready-tonight-card={card.cardId || card.label} key={card.cardId || card.label}>
                      <span>{card.plainStatus || card.status || "Checking"}</span>
                      <strong>{card.label}</strong>
                      <p>{card.nextAction || "No next action recorded."}</p>
                      <div className="reference-ready-tonight-actions">
                        <button
                          className="reference-outline-button"
                          disabled={!action.actionId}
                          onClick={() => fluxioAction(onRequestAction, "setup:run-action", action)}
                          type="button"
                        >
                          {action.label || (status.includes("ready") ? "Verify" : "Fix")}
                        </button>
                        {card.receipt?.title || card.receipt?.status ? (
                          <details>
                            <summary>What happened?</summary>
                            <p>{[card.receipt.title, card.receipt.status, card.receipt.executedAt].filter(Boolean).join(" · ")}</p>
                          </details>
                        ) : null}
                      </div>
                    </article>
                  );
                }) : (
                  <article className="tone-warn">
                    <span>Checking</span>
                    <strong>Setup cards pending</strong>
                    <p>Refresh setup health to load the beginner setup cards.</p>
                  </article>
                )}
              </div>
            </article>

            <article className="reference-settings-card">
              <div className="reference-builder-section-head">
                <div>
                  <strong>Advanced setup details</strong>
                  <span>Technical service list stays here when a repair needs exact evidence.</span>
                </div>
              </div>
              <div className="reference-settings-summary-grid">
                {asList(setupServices)
                  .filter(item => ["wsl2", "uv", "opencv", "openclaw", "hermes", "opencode_go_auth", "minimax_auth", "telegram_ready"].includes(item.serviceId))
                  .map(item => (
                    <article key={`setup-service-${item.serviceId}`}>
                      <span>{item.serviceId === "wsl2" ? "Linux helper" : item.label}</span>
                      <strong>
                        {item.currentHealthStatus === "healthy"
                          ? "Ready"
                          : item.updateAvailable
                            ? "Update available"
                            : "Needs setup"}
                      </strong>
                      <p>{item.details}</p>
                    </article>
                  ))}
              </div>
            </article>

            <article className="reference-settings-card">
              <strong>Appearance</strong>
              <details className="reference-settings-fold" open>
                <summary>Theme and collapse behavior</summary>
                <div className="reference-settings-block">
                <span>Theme</span>
                <div className="reference-theme-toggle">
                  <button className={appearance.theme === "light" ? "active" : ""} onClick={() => onSetAppearance("theme", "light")} type="button"><SunMedium size={18} strokeWidth={1.9} /><span>Light</span></button>
                  <button className={appearance.theme === "dark" ? "active" : ""} onClick={() => onSetAppearance("theme", "dark")} type="button"><Moon size={18} strokeWidth={1.9} /><span>Dark</span></button>
                  <button className={appearance.theme === "system" ? "active" : ""} onClick={() => onSetAppearance("theme", "system")} type="button"><Monitor size={18} strokeWidth={1.9} /><span>System</span></button>
                </div>
                </div>
                <div className="reference-settings-block">
                  <span>Sidebar behavior</span>
                  <div className="reference-density-toggle">
                    {sidebarBehaviorOptions.map(option => (
                      <button
                        className={appearance.sidebarBehavior === option.value ? "active" : ""}
                        key={option.value}
                        onClick={() => onSetAppearance("sidebarBehavior", option.value)}
                        type="button"
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                </div>
              </details>

              <details className="reference-settings-fold" open>
                <summary>Color presets</summary>
                <div className="reference-preset-grid">
                  {appearancePresets.map(preset => (
                    <button
                      className="reference-preset-card"
                      key={preset.id}
                      onClick={() => applyAppearancePreset(preset)}
                      type="button"
                    >
                      <span>{preset.name}</span>
                      <strong>{preset.description}</strong>
                      <i style={{ background: preset.values.accent }} />
                      <i style={{ background: preset.values.accentAlt }} />
                      <i style={{ background: preset.values.surfaceSoft }} />
                    </button>
                  ))}
                </div>
                <div className="reference-settings-block">
                <span>Accent Color</span>
                <div className="reference-color-swatches">
                  {["#d6a84f", "#9aa3a0", "#1fb68f", "#f59e0b", "#e14f63"].map(color => (
                    <button
                      className={appearance.accent === color ? "active" : ""}
                      key={color}
                      onClick={() => onSetAppearance("accent", color)}
                      style={{ background: color }}
                      type="button"
                    />
                  ))}
                </div>
                </div>
              </details>

              <details className="reference-settings-fold" open>
                <summary>Style and texture system</summary>
                <div className="reference-style-dna-grid" aria-label="Style production controls">
                  <article>
                    <span>Reference capture</span>
                    <strong>Boards, shots, and UI crops</strong>
                    <p>Collect example screens, animation stills, and product screenshots as named references.</p>
                  </article>
                  <article>
                    <span>Region language</span>
                    <strong>Palette, line, shape, texture</strong>
                    <p>Describe each surface by material rules rather than one vague style label.</p>
                  </article>
                  <article>
                    <span>Motion timing</span>
                    <strong>Ease, hold, anticipation</strong>
                    <p>Record animation-industry timing notes so generated output can match the intended feel.</p>
                  </article>
                  <article>
                    <span>Output proof</span>
                    <strong>Compare, annotate, export</strong>
                    <p>Keep generated UI, image, or video frames tied to comments and verification screenshots.</p>
                  </article>
                </div>
              </details>

              <details className="reference-settings-fold" open>
                <summary>Information density</summary>
                <div className="reference-settings-block">
                  <span>Density</span>
                  <div className="reference-density-toggle">
                    {["compact", "comfortable", "spacious"].map(option => (
                      <button
                        className={appearance.density === option ? "active" : ""}
                        key={option}
                        onClick={() => onSetAppearance("density", option)}
                        type="button"
                      >
                        {option[0].toUpperCase() + option.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="reference-settings-block">
                  <span>Info mode</span>
                  <div className="reference-density-toggle">
                    {[
                      ["minimal", "Less info"],
                      ["balanced", "Balanced"],
                      ["expanded", "More info"],
                    ].map(([value, label]) => (
                      <button
                        className={(appearance.detailLevel || "balanced") === value ? "active" : ""}
                        key={value}
                        onClick={() => onSetAppearance("detailLevel", value)}
                        type="button"
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              </details>

              <details className="reference-settings-fold">
                <summary>Advanced color tokens</summary>
                <div className="reference-settings-color-grid">
                {[
                  ["accent", "Primary Accent"],
                  ["accentAlt", "Secondary Accent"],
                  ["surface", "Settings Surface"],
                  ["surfaceSoft", "Card Surface"],
                  ["line", "Border Color"],
                  ["text", "Text Color"],
                ].map(([key, label]) => (
                  <SurfaceField key={key} label={label}>
                    <input
                      onChange={event => onSetAppearance(key, event.target.value)}
                      type="color"
                      value={appearance[key]}
                    />
                  </SurfaceField>
                ))}
                </div>
              </details>
            </article>

            <article className="reference-settings-card reference-settings-preview-card">
              <div className="reference-builder-section-head">
                <div>
                  <strong>Interface Preview</strong>
                  <span>Immediate preview of the current color tokens and shell behavior</span>
                </div>
                <Palette size={18} strokeWidth={1.9} />
              </div>
              <div
                className="reference-settings-live-preview"
                style={{
                  background: `linear-gradient(180deg, ${appearance.surfaceSoft} 0%, ${appearance.surface} 100%)`,
                  borderColor: appearance.line,
                  color: appearance.text,
                }}
              >
                <div className="reference-settings-live-preview-topbar">
                  <span>Syntelos Shell</span>
                  <div className="reference-settings-preview-pill-row">
                    <span style={{ background: appearance.accent, color: "#fff" }}>Primary</span>
                    <span style={{ background: appearance.accentAlt, color: appearance.text }}>Secondary</span>
                  </div>
                </div>
                <div className="reference-settings-live-preview-body">
                  <article style={{ borderColor: appearance.line }}>
                    <strong>Workspace Canvas</strong>
                    <p>Cards, controls, and backgrounds update from the appearance settings.</p>
                  </article>
                  <article style={{ borderColor: appearance.line }}>
                    <strong>Desktop Layout</strong>
                    <p>The rail, app canvas, and panels keep the same spacing system while colors change.</p>
                  </article>
                </div>
                <div className="reference-settings-preview-swatches">
                  {previewSwatches.map(([label, value]) => (
                    <div key={label}>
                      <span>{label}</span>
                      <strong>{value}</strong>
                    </div>
                  ))}
                </div>
              </div>
            </article>
          </div>
        </div>
      ) : null}

      {activeTab === "storage" ? (
        <div className="reference-settings-stack">
          <article className="reference-settings-card">
            <div className="reference-builder-section-head">
              <div>
                <strong>Computer and NAS bridge</strong>
                <span>
                  Keep local folders editable while a NAS-hosted runtime can stay online and use the same project tree.
                </span>
              </div>
              <StatusBadge
                label={storageBridge.connected ? "Connected" : storageBridge.available ? "Available" : "Not found"}
                tone={storageBridge.connected ? "completed" : storageBridge.available ? "running" : "paused"}
              />
            </div>
            <div className="reference-bridge-console">
              <article className="reference-bridge-node source">
                <span>Computer workspace</span>
                <strong>{storageBridge.sourceRoot || storageBridge.cloud?.sourceRoot || "Choose a local folder"}</strong>
                <p>Editable files stay on this machine while the runtime can keep running elsewhere.</p>
              </article>
              <article className="reference-bridge-route">
                <span>{storageBridge.selectedMode || storageBridge.cloud?.selectedMode || "configure"}</span>
                <strong>{storageBridge.safeDirections?.length ? storageBridge.safeDirections.join(" + ") : "preview required"}</strong>
                <p>{storageBridge.writePolicy || "preview_then_approve"} / {storageBridge.conflictPolicy || "keep_newer_and_log"}</p>
              </article>
              <article className="reference-bridge-node target">
                <span>Always-on targets</span>
                <strong>{storageBridge.targetRoot || storageBridge.cloud?.targetRoot || "NAS or Drive not mapped"}</strong>
                <p>
                  {storageBridge.selectedHost || storageBridge.cloud?.selectedHost || "Connect Synology, Google Drive, or another mounted folder."}
                </p>
              </article>
            </div>
            <div className="reference-bridge-action-bar">
              <div>
                <strong>Bridge commands</strong>
                <span>Runs through the same approval-aware workspace action contract as every other tool.</span>
              </div>
              <div className="reference-inline-actions compact">
                {storageQuickActions.length ? (
                  storageQuickActions.map(action => (
                    <button
                      className={action.requiresApproval ? "reference-outline-button" : "reference-link-button"}
                      key={`storage-action-${action.actionId}-${action.serviceRole || action.label}`}
                      onClick={() => onRequestAction?.("settings:run-action", { action })}
                      type="button"
                    >
                      {action.label || action.actionId}
                    </button>
                  ))
                ) : (
                  <StatusBadge label="No direct actions yet" tone="paused" />
                )}
              </div>
            </div>
            <div className="reference-settings-summary-grid">
              <article><span>Computer folder</span><strong>{storageBridge.sourceRoot || "Not mapped"}</strong></article>
              <article><span>NAS folder</span><strong>{storageBridge.targetRoot || "Not mapped"}</strong></article>
              <article><span>Route</span><strong>{storageBridge.selectedMode || "Offline"}</strong></article>
              <article>
                <span>Host</span>
                <strong>
                  {storageBridge.selectedHost || storageBridge.endpoint || "Not selected"}
                  {storageBridge.controlPort ? `:${storageBridge.controlPort}` : ""}
                </strong>
              </article>
              <article><span>Control</span><strong>{storageBridge.controlProtocol || storageBridge.nas?.controlProtocol || "ssh"} {storageBridge.controlPort || storageBridge.nas?.controlPort || 22}</strong></article>
              <article><span>Web route</span><strong>{storageBridge.nas?.publicEndpoint || storageBridge.publicEndpoint || storageBridge.nas?.endpoint || "HTTPS via DSM proxy"}</strong></article>
              <article><span>Port status</span><strong>{storageBridge.sshPortStatus || storageBridge.nas?.sshPortStatus || "Operator configured"}</strong></article>
              <article><span>Remote user</span><strong>{storageBridge.sshUser || storageBridge.nas?.sshUser || "Not configured"}</strong></article>
              <article><span>Remote root</span><strong>{storageBridge.remoteProjectRoot || storageBridge.nas?.remoteProjectRoot || "Not configured"}</strong></article>
            </div>
            {storageBridge.activationRequired || storageBridge.nas?.activationRequired ? (
              <article className="reference-provider-card">
                <div className="reference-builder-section-head">
                  <div>
                    <strong>{storageBridge.activationProject || storageBridge.nas?.activationProject || "Core"} activation needed</strong>
                    <span>{storageBridge.activationHint || storageBridge.nas?.activationHint || "Activate the storage project before using the NAS mapping."}</span>
                  </div>
                  <StatusBadge label="Mapping inactive" tone="paused" />
                </div>
                <p className="reference-surface-footnote">
                  {storageBridge.activationCommand || storageBridge.nas?.activationCommand || "C:/Users/paul/Projects/Cowork/map-synology-fast-path.cmd"}
                </p>
              </article>
            ) : null}
            <div className="reference-provider-grid">
              <article className="reference-provider-card">
                <strong>Transfer policy</strong>
                <p>
                  {storageBridge.writePolicy || "preview_then_approve"} · conflicts use {storageBridge.conflictPolicy || "keep_newer_and_log"}.
                </p>
                <div className="reference-inline-actions compact">
                  {asList(storageBridge.safeDirections).length ? (
                    storageBridge.safeDirections.map(direction => (
                      <StatusBadge key={direction} label={direction} tone="completed" />
                    ))
                  ) : (
                    <StatusBadge label="No write direction ready" tone="paused" />
                  )}
                  {storageBridge.requiresApprovalForWrite ? (
                    <StatusBadge label="Writes require approval" tone="running" />
                  ) : null}
                </div>
              </article>
              <article className="reference-provider-card">
                <strong>Current transfer</strong>
                <p>{storageBridge.summary || "No active upload or download is being reported."}</p>
                <div className="reference-inline-actions compact">
                  <StatusBadge label={storageBridge.health || "unknown"} tone={storageBridge.connected ? "completed" : "paused"} />
                  <StatusBadge label={storageBridge.activeDirection || "idle"} tone={storageBridge.activeDirection ? "running" : "paused"} />
                </div>
              </article>
            </div>
          </article>

          <article className="reference-settings-card">
            <div className="reference-builder-section-head">
              <div>
                <strong>Cloud drive bridge</strong>
                <span>Use Google Drive or another mounted cloud folder as a second storage route for project files.</span>
              </div>
              <StatusBadge
                label={storageBridge.cloud?.connected ? "Connected" : storageBridge.cloud?.available ? "Configure" : "Not registered"}
                tone={storageBridge.cloud?.connected ? "completed" : storageBridge.cloud?.available ? "running" : "paused"}
              />
            </div>
            <div className="reference-settings-summary-grid">
              <article><span>Computer folder</span><strong>{storageBridge.cloud?.sourceRoot || storageBridge.sourceRoot || "Not mapped"}</strong></article>
              <article><span>Cloud folder</span><strong>{storageBridge.cloud?.targetRoot || "Not mounted"}</strong></article>
              <article><span>Provider</span><strong>{storageBridge.cloud?.selectedHost || "Google Drive"}</strong></article>
              <article><span>Login</span><strong>{storageBridge.cloud?.googleLoginReady ? "Google ready" : "Needs Google login"}</strong></article>
            </div>
            <div className="reference-provider-grid">
              <article className="reference-provider-card">
                <strong>Mounted folders</strong>
                <div className="reference-note-stack">
                  {asList(storageBridge.cloud?.mountedRoots).length ? (
                    asList(storageBridge.cloud?.mountedRoots).slice(0, 4).map(item => (
                      <p className="reference-surface-footnote" key={`${item.provider}-${item.root}`}>
                        {item.provider}: {item.root}
                      </p>
                    ))
                  ) : (
                    <p>Google Drive for desktop, OneDrive, Dropbox, or a custom mounted path has not been detected.</p>
                  )}
                </div>
              </article>
              <article className="reference-provider-card">
                <strong>Cloud transfer policy</strong>
                <p>{storageBridge.cloud?.summary || "Cloud storage is waiting for a mounted folder or Google OAuth token."}</p>
                <div className="reference-inline-actions compact">
                  {asList(storageBridge.cloud?.safeDirections).length ? (
                    storageBridge.cloud.safeDirections.map(direction => (
                      <StatusBadge key={direction} label={direction} tone="completed" />
                    ))
                  ) : (
                    <StatusBadge label="No cloud write direction ready" tone="paused" />
                  )}
                  <StatusBadge label={storageBridge.cloud?.writePolicy || "preview_then_approve"} tone="running" />
                </div>
                <div className="reference-inline-actions compact">
                  <button
                    className="reference-outline-button"
                    onClick={() => window.open(storageBridge.cloud?.loginUrl || "https://drive.google.com/drive/my-drive", "_blank", "noopener,noreferrer")}
                    type="button"
                  >
                    <Database size={16} strokeWidth={1.9} />
                    <span>Open Google Drive</span>
                  </button>
                  <button
                    className="reference-link-button"
                    onClick={() => window.open(storageBridge.cloud?.desktopClientUrl || "https://www.google.com/drive/download/", "_blank", "noopener,noreferrer")}
                    type="button"
                  >
                    Drive desktop
                  </button>
                </div>
              </article>
            </div>
          </article>

          <article className="reference-settings-card">
            <div className="reference-builder-section-head">
              <div>
                <strong>Connected bridge sessions</strong>
                <span>Storage is managed through the same app capability contract as voice, monitoring, and future tools.</span>
              </div>
            </div>
            <div className="reference-provider-grid">
              {asList(bridgeSessions).length ? (
                asList(bridgeSessions).map(session => (
                  <article className={cx("reference-provider-card", session.status === "connected" && "connected")} key={session.session_id || session.app_id}>
                    <div className="reference-builder-section-head">
                      <div>
                        <strong>{session.app_name || session.app_id}</strong>
                        <span>{session.bridge_endpoint || session.bridge_transport || "Bridge manifest"}</span>
                      </div>
                      <StatusBadge label={session.bridge_health || session.status} tone={session.status === "connected" ? "completed" : "paused"} />
                    </div>
                    <p>{session.latest_task_result?.resultSummary || asList(session.notes)[0] || "No bridge task has reported yet."}</p>
                    {asList(session.context_preview).length ? (
                      <div className="reference-note-stack">
                        {asList(session.context_preview[0]?.items).slice(0, 5).map(item => (
                          <p className="reference-surface-footnote" key={`${session.app_id}-${item}`}>{item}</p>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))
              ) : (
                <article className="reference-provider-card">
                  <strong>No bridge sessions</strong>
                  <p>Register a connected app manifest before using NAS or tool bridge surfaces.</p>
                </article>
              )}
            </div>
          </article>
        </div>
      ) : null}

      {activeTab === "tools" ? (
        <div className="reference-settings-stack">
          <article className="reference-settings-card">
            <div className="reference-builder-section-head">
              <div>
                <strong>Tool and port management</strong>
                <span>
                  Runtime tools, connected-app bridges, NAS control, browser use, image tooling, and repair actions are listed here with their real endpoint state.
                </span>
              </div>
              <StatusBadge
                label={`${managementRows.length} managed`}
                tone={managementRows.some(item => item.status !== "healthy" && item.status !== "connected") ? "running" : "completed"}
              />
            </div>
            <div className="reference-port-grid">
              {managementRows.length ? (
                managementRows.map(item => (
                  <article className="reference-port-card" key={`tool-port-${item.id}`}>
                    <div>
                      <strong>{item.label}</strong>
                      <span>{item.role}</span>
                    </div>
                    <dl>
                      <div>
                        <dt>Endpoint</dt>
                        <dd>{item.host || "local"}</dd>
                      </div>
                      <div>
                        <dt>Port</dt>
                        <dd>{item.port || "n/a"}</dd>
                      </div>
                      <div>
                        <dt>Status</dt>
                        <dd>{item.status}</dd>
                      </div>
                    </dl>
                    {asList(item.actions).length ? (
                      <div className="reference-inline-actions compact">
                        {asList(item.actions).slice(0, 3).map(action => (
                          <button
                            className={action.requiresApproval ? "reference-outline-button" : "reference-link-button"}
                            key={`${item.id}-${action.actionId}`}
                            onClick={() => onRequestAction?.("settings:run-action", { action })}
                            type="button"
                          >
                            {action.label || action.actionId}
                          </button>
                        ))}
                      </div>
                    ) : (
                  <p>Live bridge actions appear after the service reports command capabilities.</p>
                    )}
                  </article>
                ))
              ) : (
                <article className="reference-port-card">
                  <div>
                    <strong>No managed services found</strong>
                    <span>setup</span>
                  </div>
                  <p>Run setup verification so Syntelos can inventory runtimes, image tools, bridges, and browser/computer-use ports.</p>
                </article>
              )}
            </div>
          </article>

          <article className="reference-settings-card">
            <div className="reference-builder-section-head">
              <div>
                <strong>Planned control ports</strong>
                <span>These are the app areas that should become first-class managed tools as features land.</span>
              </div>
            </div>
            <div className="reference-provider-grid">
              {[
                ["Image management", "Image generation, visual QA, asset folders, and selected-output promotion."],
                ["Browser use", "Local browser sessions, screenshots, page actions, and proof capture."],
                ["Computer use", "Desktop action lanes with approval boundaries and visible replay."],
                ["NAS runtime", "SSH/SFTP control on the detected SSH port plus optional SMB drive-letter sync."],
              ].map(([label, copy]) => (
                <article className="reference-provider-card" key={label}>
                  <strong>{label}</strong>
                  <p>{copy}</p>
                </article>
              ))}
            </div>
          </article>
        </div>
      ) : null}

      {activeTab === "providers" ? (
        <div className="reference-settings-stack">
          <article className="reference-settings-card">
            <strong>Model accounts</strong>
            <div className="reference-provider-grid">
              {providers.map(provider => (
                <article className={cx("reference-provider-card", provider.status && "connected")} key={provider.id}>
                  <div className="reference-builder-section-head">
                    <div>
                      <strong>{provider.label}</strong>
                      <span>{provider.env}</span>
                    </div>
                    <StatusBadge
                      label={provider.status ? "Connected" : provider.hasSecret ? "Key saved" : "Missing"}
                      tone={provider.status || provider.hasSecret ? "completed" : "paused"}
                    />
                  </div>
                  <p>{provider.note}</p>
                  {provider.quickAuth ? (
                    <div className="reference-provider-quickauth">
                      <button
                        className="reference-outline-button"
                        disabled={Boolean(provider.quickAuth.disabled)}
                        onClick={provider.onQuickAuth}
                        title={provider.quickAuth.disabled ? provider.quickAuth.detail : ""}
                        type="button"
                      >
                        <Sparkles size={16} strokeWidth={1.9} />
                        <span>{provider.quickAuth.label}</span>
                      </button>
                      <span>{provider.quickAuth.detail}</span>
                    </div>
                  ) : null}
                  {asList(provider.authLinks).length ? (
                    <div className="reference-inline-actions compact">
                      {provider.authLinks.map(link => (
                        <button className="reference-link-button" key={link.label} onClick={link.onClick} type="button">
                          {link.label}
                        </button>
                      ))}
                    </div>
                  ) : null}
                  <SurfaceField label="API key">
                    <input
                      autoComplete="off"
                      onChange={event => provider.onDraftChange(event.target.value)}
                      placeholder={provider.hasSecret ? "Stored securely. Paste a new key to replace it." : `Paste ${provider.env}`}
                      type="password"
                      value={provider.draft}
                    />
                  </SurfaceField>
                  <div className="reference-inline-actions stretch">
                    <button
                      className="reference-black-button"
                      disabled={provider.savingState === "saving"}
                      onClick={provider.onSave}
                      type="button"
                    >
                      {provider.savingState === "saving" ? "Saving..." : "Save key"}
                    </button>
                    <button
                      className="reference-outline-button"
                      disabled={provider.savingState === "clearing"}
                      onClick={provider.onClear}
                      type="button"
                    >
                      {provider.savingState === "clearing" ? "Clearing..." : "Clear"}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </article>

          <article className="reference-settings-card">
            <strong>ChatGPT connection</strong>
            <p>
              A real ChatGPT connection is an app/connector backed by an MCP server. Opening
              ChatGPT in a browser does not authenticate Syntelos or connect this desktop app.
            </p>
            <div className="reference-two-column-grid">
              <SurfaceField label="Current Syntelos local API">
                <input readOnly value={chatgptConnection.localApiUrl || "Local API not running"} />
              </SurfaceField>
              <SurfaceField label="ChatGPT-compatible MCP endpoint">
                <input readOnly value={chatgptConnection.mcpEndpoint || "Not implemented yet"} />
              </SurfaceField>
            </div>
            <p className="reference-surface-footnote">
              To connect from ChatGPT, create a ChatGPT app/connector for a remote MCP server.
              Syntelos currently exposes a secured local REST API; the MCP bridge still needs to be
              exposed before ChatGPT can connect directly.
            </p>
            <div className="reference-settings-actions split">
              {asList(chatgptConnection.links).map(link => (
                <button className="reference-outline-button" key={link.label} onClick={link.onClick} type="button">
                  {link.label}
                </button>
              ))}
            </div>
          </article>

          <article className="reference-settings-card">
            <strong>Account preferences</strong>
            <div className="reference-two-column-grid">
              <SurfaceField label="OpenAI / Codex auth path">
                <select
                  onChange={event => onWorkspaceProfileFieldChange("openaiCodexAuthMode", event.target.value)}
                  value={workspaceProfileForm.openaiCodexAuthMode}
                >
                  {authOptions.openai.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </SurfaceField>
              <SurfaceField label="MiniMax auth path">
                <select
                  onChange={event => onWorkspaceProfileFieldChange("minimaxAuthMode", event.target.value)}
                  value={workspaceProfileForm.minimaxAuthMode}
                >
                  {authOptions.minimax.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </SurfaceField>
            </div>
            <div className="reference-settings-actions">
              <button className="reference-black-button" onClick={onSaveWorkspacePolicy} type="button">
                Save auth preferences
              </button>
            </div>
          </article>

          <article className="reference-settings-card">
            <strong>Work engine availability</strong>
            <div className="reference-provider-grid">
              {runtimes.map(runtime => (
                <article className={cx("reference-provider-card", runtime.detected && "connected")} key={runtime.runtime_id}>
                  <div className="reference-builder-section-head">
                    <div>
                      <strong>{runtime.label}</strong>
                      <span>{runtime.command || "CLI not detected"}</span>
                    </div>
                    <StatusBadge label={runtime.detected ? "Detected" : "Missing"} tone={runtime.detected ? "completed" : "paused"} />
                  </div>
                  <p>{runtime.doctor_summary || runtime.doctorSummary || "Work engine status is unavailable."}</p>
                  <RuntimeCapabilityPills capabilities={asList(runtime.capabilities)} />
                </article>
              ))}
            </div>
          </article>
        </div>
      ) : null}

      {activeTab === "rules" ? (
        <div className="reference-settings-stack">
          <article className="reference-settings-card">
            <div className="reference-builder-section-head">
              <div>
                <strong>Active Rule Set</strong>
                <span>{activeRuleSet?.description || "No rule set selected."}</span>
              </div>
              <button className="reference-black-button" onClick={onApplyActiveRuleSet} type="button">
                Apply rule set
              </button>
            </div>
            <div className="reference-settings-summary-grid">
              <article><span>Name</span><strong>{activeRuleSet?.name || "—"}</strong></article>
              <article><span>Approval mode</span><strong>{activeRuleSet?.approvalMode || "—"}</strong></article>
              <article><span>Work engine</span><strong>{workspaceProfileForm.preferredHarness}</strong></article>
              <article><span>Execution target</span><strong>{workspaceProfileForm.executionTargetPreference}</strong></article>
            </div>
          </article>

          <article className="reference-settings-card">
            <strong>Routing & Workspace Policy</strong>
            <div className="reference-two-column-grid">
              <SurfaceField label="Routing strategy">
                <select
                  onChange={event => onWorkspaceProfileFieldChange("routingStrategy", event.target.value)}
                  value={workspaceProfileForm.routingStrategy}
                >
                  {routeOptions.routingStrategies.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </SurfaceField>
              <SurfaceField label="Execution target">
                <select
                  onChange={event => onWorkspaceProfileFieldChange("executionTargetPreference", event.target.value)}
                  value={workspaceProfileForm.executionTargetPreference}
                >
                  {routeOptions.executionTargets.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </SurfaceField>
            </div>

            <div className="reference-route-plan-grid">
              {asList(workspaceProfileForm.routeOverrides).map(item => (
                <article className="reference-route-plan-card" key={item.role}>
                  <strong>{item.role[0].toUpperCase() + item.role.slice(1)}</strong>
                  <div className="reference-inline-form-row">
                    <select
                      onChange={event => onRouteOverrideChange(item.role, "provider", event.target.value)}
                      value={item.provider}
                    >
                      {routeOptions.providers.map(option => (
                        <option key={`${item.role}-${option.value}`} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <select
                      onChange={event => onRouteOverrideChange(item.role, "effort", event.target.value)}
                      value={item.effort}
                    >
                      {routeOptions.efforts.map(option => (
                        <option key={`${item.role}-${option.value}`} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <select
                    onChange={event => onRouteOverrideChange(item.role, "model", event.target.value)}
                    value={item.model}
                  >
                    <option value="">Profile default</option>
                    {uniq([item.model, ...asList(routeOptions.models)].filter(Boolean)).map(option => (
                      <option key={`${item.role}-${option}`} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </article>
              ))}
            </div>

            <div className="reference-settings-actions">
              <button className="reference-black-button" onClick={onSaveWorkspacePolicy} type="button">
                Save routing policy
              </button>
            </div>
          </article>
        </div>
      ) : null}

      {activeTab === "members" ? (
        <div className="reference-settings-stack">
          <article className="reference-settings-card">
            <strong>Workspace Members</strong>
            <div className="reference-member-list">
              {members.map(member => (
                <div className="reference-member-row" key={`${member.name}-${member.role}`}>
                  <div className="reference-user-mini">{member.name.slice(0, 2).toUpperCase()}</div>
                  <div>
                    <strong>{member.name}</strong>
                    <p>{member.role}</p>
                  </div>
                </div>
              ))}
            </div>
          </article>

          <article className="reference-settings-card">
            <div className="reference-builder-section-head">
              <div>
                <strong>Account and workspace permissions</strong>
                <span>Owner accounts can change setup, models, bridges, permissions, and destructive actions. Member accounts can work inside approved projects and ask for escalation.</span>
              </div>
            </div>
            <div className="reference-permission-grid">
              {[
                ["Owner console", "Models, provider keys, NAS bridge, tools, member roles, retention, and reset actions.", "owner"],
                ["Member console", "Agent chat, assigned workspaces, tutorials, school/work modes, and non-destructive file review.", "user"],
                ["Approval boundary", "Writes, desktop control, cloud transfer, NAS transfer, and permission changes require an approval gate.", "approval"],
              ].map(([title, copy, tone]) => (
                <article className={`reference-permission-card tone-${tone}`} key={title}>
                  <span>{title}</span>
                  <p>{copy}</p>
                </article>
              ))}
            </div>
          </article>
        </div>
      ) : null}

      {activeTab === "privacy" ? (
        <div className="reference-settings-grid">
          <article className="reference-settings-card">
            <strong>Data & Retention</strong>
            <SurfaceField label="Conversation retention">
              <input readOnly value={privacy.conversationRetention} />
            </SurfaceField>
            <SurfaceField label="File retention">
              <input readOnly value={privacy.fileRetention} />
            </SurfaceField>
            <div className="reference-settings-actions split">
              <button className="reference-outline-button" onClick={() => onRequestAction?.("settings:export-data")} type="button">
                <FileText size={16} strokeWidth={1.9} />
                <span>Export Data</span>
              </button>
              <button className="reference-danger-button" onClick={() => onRequestAction?.("settings:delete-workspace")} type="button">Delete Workspace</button>
            </div>
          </article>
          <article className="reference-settings-card">
            <strong>Workspace Notes</strong>
            <p>Sidebar behavior, color choices, account preferences, and routing policies are saved inside Syntelos.</p>
            <p>Published rule sets immediately update the workspace routing overrides used for agent follow-ups.</p>
          </article>
        </div>
      ) : null}
    </section>
  );
}

const FLUXIO_NAV_ITEMS = [
  { id: "home", label: "Home", Icon: Home },
  { id: "agent", label: "Agent", Icon: Bot },
  { id: "builder", label: "Builder", Icon: Hammer },
  { id: "phone", label: "Phone", Icon: Smartphone },
  { id: "skills", label: "Skills", Icon: Grid2x2 },
  { id: "rule-sets", label: "Rule Sets", Icon: Shield },
  { id: "images", label: "Images", Icon: Palette },
  { id: "workbench", label: "Workbench", Icon: Laptop },
  { id: "settings", label: "Settings", Icon: Settings },
];

const FLUXIO_THEMES = [
  {
    id: "noir",
    label: "Fluxio Noir",
    bestFor: "Daily work",
    density: "Balanced",
    motion: "Calm",
    contrast: "High",
  },
  {
    id: "glass",
    label: "Glass OS",
    bestFor: "AI workspace",
    density: "Balanced",
    motion: "Fluid",
    contrast: "High",
  },
  {
    id: "terminal",
    label: "Terminal Ops",
    bestFor: "Runs and logs",
    density: "Compact",
    motion: "Minimal",
    contrast: "High",
  },
  {
    id: "blueprint",
    label: "Blueprint Lab",
    bestFor: "Builder maps",
    density: "Balanced",
    motion: "Precise",
    contrast: "High",
  },
  {
    id: "swiss",
    label: "Swiss Editorial",
    bestFor: "Research",
    density: "Spacious",
    motion: "Minimal",
    contrast: "High",
  },
  {
    id: "brutal",
    label: "Neo-Brutalist",
    bestFor: "Experimental",
    density: "Comfortable",
    motion: "Snappy",
    contrast: "Very high",
  },
];

const FLUXIO_THEME_STORAGE_KEY = "fluxio.os.theme";

const AGENT_PLAN = [
  ["Scope", "Read project state and collect reference intent.", "done"],
  ["Edit", "Apply the shell, review bundle, and visual control surfaces.", "running"],
  ["Verify", "Run build, browser smoke, and responsive screenshots.", "queued"],
  ["Merge gate", "Summarize changed files, evidence, and remaining risk.", "queued"],
];

const TOOL_EVENTS = [];

const CHANGED_FILES = [];

const BUILDER_FLOWS = [];

const SKILL_CARDS = [
  ["Frontend polish", "Visual QA, responsive checks, no placeholder UI.", "High", "Browser + Code"],
  ["Review bundle", "Diff, tests, screenshots, and approvals in one handoff.", "Medium", "Git + Tests"],
  ["Image direction", "Reference capture, variants, and export-ready assets.", "High", "Images"],
  ["Autonomy guard", "Scoped writes, permission gates, and recovery rules.", "Medium", "Policy"],
];

const IMAGE_VARIANTS = [
  ["Command center", "dark desktop", "approved"],
  ["Browser QA", "checkout test", "review"],
  ["Image studio", "variant board", "draft"],
  ["Builder graph", "flow health", "approved"],
];

const FLUXIO_DATABASES = [
  ["postgres", "Neon Postgres", "Product data", "Connected", "cyan"],
  ["sqlite", "Local SQLite", "Runs and memory", "Ready", "green"],
  ["vector", "Vector Memory", "Context search", "Indexing", "violet"],
  ["blob", "Artifact Store", "Screenshots and exports", "Synced", "amber"],
];

function fluxioAction(handler, fallback, payload) {
  if (typeof handler === "function") {
    return handler(fallback, payload);
  }
  return undefined;
}

function MetricTile({ label, value, detail, tone = "neutral" }) {
  return (
    <article className={`fluxos-metric tone-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <p>{detail}</p>
    </article>
  );
}

const DICTATION_AMBIGUITY_CHECKS = [
  ["correction phrase", /\b(scratch that|delete that|correction|i mean|no wait|wait no|start over)\b/i],
  ["repeated negation", /\b(no|nope)\b[\s,.;:-]+\b(no|nope)\b/i],
  ["uncertainty marker", /\b(maybe|not sure|unclear|i think)\b/i],
  ["question burst", /\?{2,}/],
];

function dictationAmbiguityFinding(value) {
  const text = String(value || "");
  const match = DICTATION_AMBIGUITY_CHECKS.find(([, pattern]) => pattern.test(text));
  return match ? match[0] : "";
}

function dictationQualityGate(value, guardEnabled = true) {
  const text = String(value || "").trim();
  const finding = guardEnabled ? dictationAmbiguityFinding(text) : "";
  if (!text) {
    return {
      status: "empty",
      score: 0,
      finding: "",
      label: "Waiting for command",
      detail: "Dictate or type a command before sending.",
    };
  }
  if (finding) {
    return {
      status: "review_required",
      score: 62,
      finding,
      label: `Review ${finding}`,
      detail: "The command has a dictation marker or uncertainty cue. Review it before sending.",
    };
  }
  return {
    status: "clear",
    score: Math.min(100, 84 + Math.min(12, Math.floor(text.length / 28))),
    finding: "",
    label: "Clear to send",
    detail: "No dictation ambiguity markers detected.",
  };
}

function cleanDictationDraft(value) {
  return String(value || "")
    .replace(/\b(scratch that|delete that|correction|i mean|no wait|wait no|start over)\b[:,.;\s-]*/gi, "")
    .replace(/\b(no|nope)\b[\s,.;:-]+\b(no|nope)\b[:,.;\s-]*/gi, "")
    .replace(/\?{2,}/g, "?")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function FluxioComposer({
  activeCommentTarget,
  draft,
  onAttach,
  onChangeDraft,
  onDictation,
  onSend,
  onSubmit,
  onRequestAction,
  placeholder = "Ask Fluxio to plan, edit, test, or review this project...",
}) {
  const currentDraft = String(draft || "");
  const [plusOpen, setPlusOpen] = useState(false);
  const [dictationReviewOpen, setDictationReviewOpen] = useState(false);
  const [dictationGuardEnabled, setDictationGuardEnabled] = useState(true);
  const [accessibilityPrefs, setAccessibilityPrefs] = useState({
    reducedMotion: true,
    highContrast: true,
    largerTargets: false,
  });
  const [dictationStatus, setDictationStatus] = useState("System dictation route ready");
  const dictationGate = useMemo(
    () => dictationQualityGate(currentDraft, dictationGuardEnabled),
    [currentDraft, dictationGuardEnabled],
  );
  const dictationFinding = dictationGate.finding;
  const dictationNeedsReview = Boolean(dictationGuardEnabled && dictationFinding);
  const toggleAccessibilityPref = key => {
    setAccessibilityPrefs(current => ({ ...current, [key]: !current[key] }));
  };
  const performSubmit = () => {
    if (typeof onSubmit === "function") {
      onSubmit();
      return;
    }
    if (typeof onSend === "function") {
      onSend();
      return;
    }
    fluxioAction(onRequestAction, "composer:send");
  };
  const submit = ({ force = false } = {}) => {
    if (!force && dictationNeedsReview) {
      setDictationReviewOpen(true);
      setDictationStatus(`Review needed: ${dictationFinding}; quality ${dictationGate.score}/100`);
      fluxioAction(onRequestAction, "dictation:review-required", {
        finding: dictationFinding,
        score: dictationGate.score,
        status: dictationGate.status,
      });
      return;
    }
    setDictationReviewOpen(false);
    performSubmit();
  };
  const armDictation = () => {
    setDictationReviewOpen(true);
    setDictationStatus("Dictate into the composer, then review before sending");
    if (typeof onDictation === "function") {
      onDictation({
        source: "fluxio_composer",
        reviewBeforeSend: true,
        ambiguityGuard: dictationGuardEnabled,
        correctionBuffer: true,
      });
      return;
    }
    fluxioAction(onRequestAction, "dictation:repair-armed", {
      reviewBeforeSend: true,
      ambiguityGuard: dictationGuardEnabled,
      correctionBuffer: true,
    });
  };
  const applyDictationCleanup = () => {
    const cleaned = cleanDictationDraft(currentDraft);
    onChangeDraft?.(cleaned);
    setDictationStatus(cleaned === currentDraft.trim() ? "No dictation markers found" : "Correction markers cleaned");
  };
  const handleComposerKeyDown = event => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      submit();
    }
    if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "m") {
      event.preventDefault();
      armDictation();
    }
    if (event.key === "Escape" && dictationReviewOpen) {
      event.preventDefault();
      setDictationReviewOpen(false);
      setDictationStatus("Correction buffer closed; draft preserved");
    }
  };
  const runPlusAction = (actionId, payload) => {
    setPlusOpen(false);
    if (actionId === "composer:attach") {
      onAttach?.();
      return;
    }
    fluxioAction(onRequestAction, actionId, payload);
  };
  const plusActions = [
    ["composer:attach", "Attach context", "File, text, screenshot, or selected artifact"],
    ["composer:plus:preview", "Preview", "Open artifact or HTML preview when available"],
    ["composer:plus:browser", "Browser", "Click, inspect, upload, and capture browser proof"],
    ["composer:plus:app", "Use app", "Oratio, JBheaven, MindTower, or another bridge"],
    ["composer:plus:skill", "Use skill", "Hermes or OpenClaw skill lane"],
    ["composer:plus:runtime", "Runtime", "Hermes, OpenClaw, Codex, or app-native thread"],
    ["composer:plus:model", "Model", "Provider and model route"],
    ["composer:plus:thinking", "Thinking", "Reasoning effort for the next turn"],
    ["composer:plus:terminal", "Terminal", "Use command output as context"],
    ["composer:plus:approval", "Approval", "Request or inspect a gated action"],
    ["composer:plus:details", "Live details", "Show route, trace, receipts, and proof drawers"],
  ];

  return (
    <section
      className="fluxos-composer"
      aria-label="Fluxio command composer"
      data-accessibility-control-points="true"
      data-accessibility-high-contrast={accessibilityPrefs.highContrast ? "true" : "false"}
      data-accessibility-larger-targets={accessibilityPrefs.largerTargets ? "true" : "false"}
      data-accessibility-reduced-motion={accessibilityPrefs.reducedMotion ? "true" : "false"}
      data-dictation-ambiguity-guard={dictationGuardEnabled ? "true" : "false"}
      data-dictation-control="true"
      data-dictation-quality-gate={dictationGate.status}
    >
      {activeCommentTarget?.id ? (
        <div className="reference-comment-target" data-executable-comment-target="true">
          <span>{activeCommentTarget.kind || "Comment target"}</span>
          <strong>{activeCommentTarget.title || activeCommentTarget.id}</strong>
          <div className="reference-comment-target-actions">
            <button onClick={() => fluxioAction(onRequestAction, "run:comment-edit")} type="button">
              Run with edits
            </button>
            <button className="primary" onClick={() => fluxioAction(onRequestAction, "run:comment-execute")} type="button">
              Run comment
            </button>
            <button aria-label="Clear comment target" onClick={() => fluxioAction(onRequestAction, "run:clear-comment-target")} type="button">
              x
            </button>
          </div>
        </div>
      ) : null}
      <textarea
        aria-label="Command Fluxio"
        aria-describedby="fluxos-dictation-status"
        data-agent-composer-draft="true"
        onChange={event => onChangeDraft?.(event.target.value)}
        onKeyDown={handleComposerKeyDown}
        placeholder={placeholder}
        value={currentDraft}
      />
      <div
        className="fluxos-dictation-strip"
        data-dictation-repair-strip="true"
        data-dictation-review-open={dictationReviewOpen ? "true" : "false"}
      >
        <div className="fluxos-dictation-copy">
          <span>Voice guard</span>
          <strong>{dictationGate.label}</strong>
        </div>
        <div className="fluxos-dictation-meter" aria-label="Dictation quality gate">
          <span>Quality</span>
          <strong>{dictationGate.score}/100</strong>
          <i style={{ "--dictation-score": `${dictationGate.score}%` }} />
        </div>
        <div className="fluxos-dictation-checks" aria-label="Dictation safeguards">
          <span>Review before send</span>
          <span>Ambiguity check</span>
          <span>Correction buffer</span>
        </div>
        <div className="fluxos-dictation-controls">
          <button
            aria-pressed={dictationGuardEnabled ? "true" : "false"}
            data-dictation-guard-toggle="true"
            onClick={() => {
              setDictationGuardEnabled(current => !current);
              setDictationStatus(dictationGuardEnabled ? "Ambiguity guard off for next send" : "Ambiguity guard on");
            }}
            type="button"
          >
            Guard {dictationGuardEnabled ? "on" : "off"}
          </button>
          <button
            aria-expanded={dictationReviewOpen ? "true" : "false"}
            data-dictation-review-toggle="true"
            onClick={() => setDictationReviewOpen(current => !current)}
            type="button"
          >
            Review text
          </button>
        </div>
      </div>
      <p
        className="fluxos-dictation-live"
        id="fluxos-dictation-status"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {dictationStatus}
      </p>
      {dictationReviewOpen ? (
        <div
          className="fluxos-dictation-review"
          data-dictation-correction-buffer="true"
          role="region"
          aria-label="Dictation review and correction buffer"
        >
          <div className="fluxos-dictation-review-copy">
            <span>Correction buffer</span>
            <strong>{dictationFinding ? `Check ${dictationFinding} before launch` : "Text is ready to verify"}</strong>
            <p>
              {dictationGate.detail} Ctrl+Enter sends after the gate passes; Escape closes this review without deleting text.
            </p>
          </div>
          <div className="fluxos-dictation-review-actions">
            <button onClick={applyDictationCleanup} type="button">
              Clean markers
            </button>
            <button onClick={() => setDictationReviewOpen(false)} type="button">
              Keep editing
            </button>
            <button className="primary" onClick={() => submit({ force: true })} type="button">
              Send checked
            </button>
          </div>
        </div>
      ) : null}
      <div className="fluxos-accessibility-controls" data-accessibility-preferences="true" aria-label="Accessibility preferences">
        {[
          ["reducedMotion", "Reduced motion"],
          ["highContrast", "High contrast"],
          ["largerTargets", "Larger targets"],
        ].map(([key, label]) => (
          <button
            aria-pressed={accessibilityPrefs[key] ? "true" : "false"}
            className={accessibilityPrefs[key] ? "active" : ""}
            data-accessibility-toggle={key}
            key={key}
            onClick={() => toggleAccessibilityPref(key)}
            type="button"
          >
            {label}
          </button>
        ))}
      </div>
      <div className="fluxos-composer-bar">
        <div className="fluxos-composer-actions">
          <div className="fluxos-composer-left-actions">
            <button
              aria-expanded={plusOpen ? "true" : "false"}
              aria-label="Add context or action"
              className="fluxos-composer-plus-trigger"
              data-composer-plus-button="true"
              onClick={() => setPlusOpen(current => !current)}
              title="Add context or action"
              type="button"
            >
              <Plus size={16} strokeWidth={2} />
            </button>
            {plusOpen ? (
              <div className="fluxos-composer-plus-menu" data-composer-plus-menu="true" role="menu">
                {plusActions.map(([actionId, label, detail]) => (
                  <button
                    data-composer-plus-action={actionId}
                    key={actionId}
                    onClick={() => runPlusAction(actionId)}
                    role="menuitem"
                    type="button"
                  >
                    <strong>{label}</strong>
                    <span>{detail}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          <div className="fluxos-composer-right-actions">
            <button
              aria-label="Start dictation repair"
              data-dictation-control-button="true"
              onClick={armDictation}
              title="Start dictation repair"
              type="button"
            >
              <Mic size={16} strokeWidth={1.9} />
            </button>
            <button className="primary" onClick={() => submit()} type="button">
              <ArrowUp size={17} strokeWidth={2.1} />
              <span>Run</span>
            </button>
          </div>
        </div>
      </div>
      <div className="fluxos-composer-status" aria-label="Composer readiness">
        <span><i />Agent online</span>
        <span>Ready with workspace context</span>
        <button onClick={() => fluxioAction(onRequestAction, "composer:workspace")} type="button">Workspace: current</button>
      </div>
    </section>
  );
}

function normalizeReferenceTurnReceipt(value, fallback = {}) {
  const receipt = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  const route = receipt.route && typeof receipt.route === "object" ? receipt.route : fallback.route || {};
  const command = receipt.command || fallback.command || "Not reported";
  const assistantMessage = normalizeReferenceReceiptAssistantMessage(
    [
      receipt.assistantMessage,
      receipt.modelMessage,
      receipt.openRuntimeMessage,
      receipt.agentMessage,
      receipt.finalMessage,
      fallback.assistantMessage,
      fallback.modelMessage,
      fallback.openRuntimeMessage,
      fallback.agentMessage,
      fallback.finalMessage,
    ],
    command,
  );
  return {
    schema: receipt.schema || "fluxio.turn_receipt.v1",
    command,
    runtime: receipt.runtime || fallback.runtime || "Not reported",
    provider: receipt.provider || route.provider || fallback.provider || "Not reported",
    model: receipt.model || route.model_id || route.model || fallback.model || "Not reported",
    effort: receipt.effort || route.effort || fallback.effort || "Not reported",
    status: receipt.status || fallback.status || "recorded",
    durationMs: receipt.durationMs ?? fallback.durationMs ?? "",
    sourceType: receipt.sourceType || fallback.sourceType || "",
    sourceMessageId: receipt.sourceMessageId || fallback.sourceMessageId || "",
    sourceZone: receipt.sourceZone || fallback.sourceZone || "",
    changedFiles: [
      ...asList(receipt.changedFiles),
      ...asList(receipt.filesChanged),
      ...asList(fallback.changedFiles),
      ...asList(fallback.filesChanged),
    ].map(item => String(item || "").trim()).filter(Boolean),
    toolTimeline: asList(receipt.toolTimeline || fallback.toolTimeline),
    assistantMessage,
    finalMessage: assistantMessage,
    modelMessageSource: receipt.modelMessageSource || fallback.modelMessageSource || "",
    modelMessageSourceLabel: receipt.modelMessageSourceLabel || fallback.modelMessageSourceLabel || "",
    modelMessageSourceTitle: receipt.modelMessageSourceTitle || fallback.modelMessageSourceTitle || "",
    modelMessageSourceId: receipt.modelMessageSourceId || fallback.modelMessageSourceId || "",
    transcriptSessionId: receipt.transcriptSessionId || fallback.transcriptSessionId || "",
    runSummary: receipt.runSummary || fallback.runSummary || "",
  };
}

function normalizeReferenceReceiptAssistantMessage(value, command = "") {
  const candidates = Array.isArray(value) ? value : [value];
  for (const candidate of candidates) {
    const normalized = normalizeReferenceReceiptAssistantCandidate(candidate, command);
    if (normalized) return normalized;
  }
  return "";
}

function normalizeReferenceReceiptAssistantCandidate(value, command = "") {
  const text = String(value || "")
    .replace(/\r\n/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  if (!text) return "";
  const collapsedText = text.replace(/\s+/g, " ").trim();
  const commandText = String(command || "").replace(/\s+/g, " ").trim();
  if (commandText && collapsedText === commandText) return "";
  if (/^(command|feedback|response|reply)\s*:?\s+(\/volume\d+\/|[A-Z]:\\|wsl\s+|python\s+-m\s+|node\s+|npm\s+|pnpm\s+|yarn\s+|hermes\s+|opencode\s+|openclaw\s+|codex\s+)/i.test(collapsedText)) {
    return "";
  }
  if (/^(\/volume\d+\/|[A-Z]:\\|wsl\s+|python\s+-m\s+|node\s+|npm\s+|pnpm\s+|yarn\s+|hermes\s+|opencode\s+|openclaw\s+|codex\s+)/i.test(collapsedText)) {
    return "";
  }
  if (/\b(mission one-shot|execute model mission|--objective|--mission-id|--provider|--model)\b/i.test(collapsedText)) {
    return "";
  }
  if (/\b(delegated runtime lane launched|delegated lane launched|file mutation completed|workspace search completed|approval required before|waiting for operator approval|lane action routed)\b/i.test(collapsedText)) {
    return "";
  }
  const assistantMessage = finalAssistantMessageFromRuntimeOutput(text);
  if (assistantMessage) return assistantMessage;
  return text;
}

function FluxioTurnReceiptStrip({ receipt, runtimeCompartment }) {
  const normalized = normalizeReferenceTurnReceipt(receipt || runtimeCompartment?.turnReceipt, {
    runtime: runtimeCompartment?.runtime,
    route: runtimeCompartment?.route,
    changedFiles: runtimeCompartment?.filesChanged,
    toolTimeline: runtimeCompartment?.toolTimeline || runtimeCompartment?.recentActivity,
    status: runtimeCompartment?.state,
    durationMs: runtimeCompartment?.lastRoundtripMs,
  });
  const changedFiles = asList(normalized.changedFiles);
  const timeline = asList(normalized.toolTimeline);
  const hasSignal =
    normalized.command ||
    changedFiles.length ||
    timeline.length ||
    normalized.runtime ||
    normalized.assistantMessage;
  if (!hasSignal) return null;
  const duration = Number(normalized.durationMs);
  const durationLabel = Number.isFinite(duration) && duration > 0 ? `${Math.round(duration)}ms` : "Not reported";
  const modelSourceParts = [
    normalized.modelMessageSourceLabel,
    normalized.modelMessageSourceTitle,
    normalized.transcriptSessionId ? `session ${normalized.transcriptSessionId}` : "",
  ].filter(Boolean);
  return (
    <section className="fluxos-turn-receipt-strip compact" data-turn-receipt="true" data-modified-files-strip="true">
      <div className="fluxos-turn-receipt-grid" aria-label="Compact run receipt">
        <strong>{titleizeToken(normalized.status || "recorded")}</strong>
        <span>Runtime: {titleizeToken(normalized.runtime)}</span>
        <span>Provider: {titleizeToken(normalized.provider)}</span>
        <span>Model: {normalized.model}</span>
        <span>Thinking: {titleizeToken(normalized.effort)}</span>
        <span>Duration: {durationLabel}</span>
      </div>
      {normalized.sourceType === "comment" ? (
        <p>Executed comment from {normalized.sourceZone || "selected row"} {normalized.sourceMessageId || ""}.</p>
      ) : null}
      <div className="fluxos-modified-files-strip">
        <strong>{changedFiles.length ? `Modified files (${changedFiles.length})` : "No files modified"}</strong>
        {changedFiles.length ? (
          <div>
            {changedFiles.slice(0, 4).map(file => <code key={`fluxos-modified-${file}`}>{file}</code>)}
          </div>
        ) : (
          <span>No changed-file receipt was attached to this turn.</span>
        )}
      </div>
      {(normalized.command || changedFiles.length > 4 || timeline.length || normalized.runSummary || normalized.assistantMessage) ? (
        <details className="fluxos-message-trace">
          <summary>Trace available</summary>
          <p className="fluxos-turn-command">Command: {normalized.command || "Not reported"}</p>
          <div className={`fluxos-turn-agent-message ${normalized.assistantMessage ? "" : "empty"}`.trim()} data-final-model-message="true">
            <span>Model / OpenRuntime message</span>
            <p>{normalized.assistantMessage || "No model or OpenRuntime message was returned for this run."}</p>
            {modelSourceParts.length ? (
              <small data-model-message-source="true">{modelSourceParts.join(" · ")}</small>
            ) : null}
          </div>
          {changedFiles.length > 4 ? <pre>{changedFiles.join("\n")}</pre> : null}
          {timeline.length ? <pre>{JSON.stringify(timeline.slice(-12), null, 2)}</pre> : null}
          {normalized.runSummary ? <p>Run summary: {normalized.runSummary}</p> : null}
          {normalized.assistantMessage ? <p>Model / OpenRuntime message: {normalized.assistantMessage}</p> : null}
        </details>
      ) : null}
    </section>
  );
}

function FluxioEvidenceRail({ onRequestAction, runtimeCompartment, routeControls, selectedModelLabel }) {
  const route = routeControls?.selectedRoute || {};
  const host = runtimeCompartment?.host || "local";
  return (
    <aside className="fluxos-evidence-rail" aria-label="Evidence and approvals">
      <section className="fluxos-approval-card">
        <span>Approval waiting</span>
        <strong>Review bundle before merge</strong>
        <p>2 UI files changed. Browser proof and build output are required before publish confidence can be marked ready.</p>
        <div>
          <button onClick={() => fluxioAction(onRequestAction, "approval:review")} type="button">Review</button>
          <button className="primary" onClick={() => fluxioAction(onRequestAction, "approval:approve")} type="button">Approve</button>
        </div>
      </section>

      <section className="fluxos-rail-panel">
        <div className="fluxos-section-head">
          <span>Context health</span>
          <strong>6 of 7 ready</strong>
        </div>
        {["Project files", "Rulesets", "Package scripts", "Image references", "Terminal logs", "Screenshots"].map(item => (
          <div className="fluxos-check-row" key={item}>
            <CircleCheckBig size={15} strokeWidth={1.9} />
            <span>{item}</span>
          </div>
        ))}
      </section>

      <section className="fluxos-rail-panel">
        <div className="fluxos-section-head">
          <span>Route</span>
          <strong>{route.role || "executor"}</strong>
        </div>
        <dl className="fluxos-mini-dl">
          <div><dt>Model</dt><dd>{selectedModelLabel || "GPT route"}</dd></div>
          <div><dt>Host</dt><dd>{host}</dd></div>
          <div><dt>Harness</dt><dd>{route.harness || "Fluxio hybrid"}</dd></div>
        </dl>
      </section>
    </aside>
  );
}

function FluxioHomeSurface(props) {
  const { builderRows, liveDataStatus, onSetSurface, onRequestAction, draft, onChangeDraft, onAttach, onDictation, onIdleSubmit } = props;
  const isLiveBackend = liveDataStatus?.previewMode === "live";
  const isLiveLoading = isLiveBackend && liveDataStatus?.loading && !Number(liveDataStatus?.missionCount || 0);
  const liveRows = sortLiveBuilderRows(builderRows).slice(0, 4);
  const modeCards = [
    ["agent", Bot, "Agent", "Chat with AI to plan, analyze, and build with real-time context.", "Active mode"],
    ["builder", Code2, "Builder", "Create and iterate on full-stack apps, APIs, and deployment flows.", ""],
    ["skills", Sparkles, "Skills", "Use and manage specialized AI skills, rules, and reusable workflows.", ""],
    ["images", Palette, "Images", "Generate, edit, and iterate on images with prompts and references.", ""],
  ];
  const recentSessions = [];
  return (
    <div className="fluxos-home">
      <section className="fluxos-home-lobby">
        <span className="fluxos-hidden-proof">Fluxio control route</span>
        <div className="fluxos-home-title">
          <h1>What will we build today?</h1>
          <p>Choose a mode to start or ask Fluxio anything.</p>
        </div>

        <div className="fluxos-mode-cards" aria-label="Start modes">
          {modeCards.map(([id, Icon, label, copy, badge]) => (
            <button className={id === "agent" ? "active" : ""} key={id} onClick={() => onSetSurface?.(id)} type="button">
              <span className="fluxos-mode-icon"><Icon size={34} strokeWidth={1.55} /></span>
              <strong>{label}</strong>
              <p>{copy}</p>
              {badge ? <em>{badge}</em> : <i aria-hidden="true"><ArrowRight size={18} strokeWidth={1.7} /></i>}
            </button>
          ))}
        </div>

        <section className="fluxos-recent-row" aria-label="Recent sessions">
          <div className="fluxos-recent-head">
            <strong>{isLiveBackend ? "Live NAS missions" : "Recent sessions"}</strong>
            <button onClick={() => fluxioAction(onRequestAction, "home:view-all-sessions")} type="button">
              View all
              <ArrowRight size={15} strokeWidth={1.7} />
            </button>
          </div>
          <div className="fluxos-recent-grid">
            {liveRows.length > 0 ? liveRows.map(row => (
              <button key={row.id || row.name || row.title} onClick={() => onSetSurface?.("builder")} type="button">
                <Bot size={18} strokeWidth={1.7} />
                <span>
                  <strong>{row.name || row.title || "Live mission"}</strong>
                  <small>{row.status || row.updated || liveDataStatus?.source || "live"}</small>
                </span>
              </button>
            )) : isLiveLoading ? (
              <article className="fluxos-flow-empty is-loading">
                <span>Live data only</span>
                <strong>Connecting to NAS live summary</strong>
                <p>Fluxio is waiting for the authenticated control-room response. No cached or sample mission rows are shown.</p>
              </article>
            ) : isLiveBackend ? (
              <article className="fluxos-flow-empty">
                <span>Live data only</span>
                <strong>No live mission rows loaded</strong>
                <p>The home surface is waiting for NAS control-room data; no cached or sample sessions are shown.</p>
              </article>
            ) : recentSessions.map(([title, time, Icon]) => (
              <button key={title} onClick={() => fluxioAction(onRequestAction, `home:session:${title}`)} type="button">
                <Icon size={18} strokeWidth={1.7} />
                <span>
                  <strong>{title}</strong>
                  <small>{time}</small>
                </span>
              </button>
            ))}
          </div>
        </section>

        <FluxioComposer
          activeCommentTarget={props.activeCommentTarget}
          draft={draft}
          onAttach={onAttach}
          onChangeDraft={onChangeDraft}
          onDictation={onDictation}
          onRequestAction={onRequestAction}
          onSubmit={onIdleSubmit}
          placeholder="Ask Fluxio to build, analyze, or orchestrate anything..."
        />
      </section>
    </div>
  );
}

function FluxioAgentSurface(props) {
  const {
    agentLiveThreadProof,
    builderRows,
    draft,
    liveDataStatus,
    messages,
    notificationItems = [],
    onAttach,
    onChangeDraft,
    onConnectedAppHandoff,
    onDictation,
    onRequestAction,
    onRuntimeChange,
    onSend,
    onSelectFlow,
    onSetSurface,
    runtimeCompartment,
    routeControls,
    selectedModelLabel,
    selectedRuntimeLabel,
    timelineMoments,
    missionLoop,
    missionWatchdog,
    workbenchState,
  } = props;
  const isLiveBackend = liveDataStatus?.previewMode === "live";
  const [agentClarityMode, setAgentClarityMode] = useState(() => {
    if (typeof window === "undefined") return "focus";
    return window.localStorage?.getItem("fluxio.agent.clarityMode") || "focus";
  });
  const [localLaneControlReceipt, setLocalLaneControlReceipt] = useState(null);
  const [agentPreviewWindowOpen, setAgentPreviewWindowOpen] = useState(false);
  const agentPreviewPanelRef = useRef(null);
  const normalizedAgentClarityMode = agentClarityMode === "full" ? "full" : "focus";
  const agentFocusMode = isLiveBackend && normalizedAgentClarityMode === "focus";
  const setLiveAgentClarityMode = mode => {
    const nextMode = mode === "full" ? "full" : "focus";
    setAgentClarityMode(nextMode);
    if (typeof window !== "undefined") {
      window.localStorage?.setItem("fluxio.agent.clarityMode", nextMode);
    }
  };
  const persistedMissionChatMessages = useMemo(() => {
    if (typeof window === "undefined") {
      return [];
    }
    const scopedMissionId = String(
      workbenchState?.missionId ||
        missionLoop?.missionId ||
        missionLoop?.mission_id ||
        "",
    ).trim();
    let transcriptMap = {};
    try {
      transcriptMap = JSON.parse(window.localStorage?.getItem("fluxio.chat.session_transcripts") || "{}");
    } catch {
      transcriptMap = {};
    }
    if (!transcriptMap || typeof transcriptMap !== "object" || Array.isArray(transcriptMap)) {
      return [];
    }
    const exactSessionId = scopedMissionId ? `mission-chat-${scopedMissionId}` : "";
    const directTurns = exactSessionId ? asList(transcriptMap[exactSessionId]) : [];
    return directTurns
      .map((turn, index) => {
        const role = String(turn?.role || "").toLowerCase() === "assistant" ? "assistant" : "user";
        const title = String(turn?.title || turn?.text || turn?.detail || "").trim();
        if (!title) {
          return null;
        }
        return {
          id: turn?.id || `persisted-mission-chat-${index}`,
          missionId: scopedMissionId,
          role,
          label: role === "assistant" ? "Hermes" : "You",
          title,
          detail: turn?.detail && turn.detail !== title ? turn.detail : "",
          meta: turn?.meta || "",
          createdAt: turn?.createdAt || "",
          tone: turn?.tone || "neutral",
          pending: Boolean(turn?.pending),
          conversationTurn: true,
          messageKind: "dialogue",
          source: turn?.source || "",
          chips: asList(turn?.chips).slice(0, 3),
          technicalDetail: turn?.technicalDetail || "",
          turnReceipt: turn?.turnReceipt && typeof turn.turnReceipt === "object" ? turn.turnReceipt : null,
        };
      })
      .filter(Boolean)
      .filter(message => !message.pending && isTrustedLiveDialogueSource(message));
  }, [messages, missionLoop?.missionId, missionLoop?.mission_id, workbenchState?.missionId]);
  const trustedPersistedMissionChatMessages = hasTrustedRuntimeReply(persistedMissionChatMessages)
    ? persistedMissionChatMessages
    : [];
  const sourceMessages = asList(messages);
  const sourceDialogueKeys = new Set(
    sourceMessages
      .filter(isAgentDialogueTurn)
      .map(message =>
        [
          String(message?.role || "").toLowerCase(),
          String(message?.title || message?.detail || "").replace(/\s+/g, " ").trim().toLowerCase(),
        ].join(":"),
      ),
  );
  const uniquePersistedMissionChatMessages = trustedPersistedMissionChatMessages.filter(message => {
    const key = [
      String(message?.role || "").toLowerCase(),
      String(message?.title || message?.detail || "").replace(/\s+/g, " ").trim().toLowerCase(),
    ].join(":");
    return !sourceDialogueKeys.has(key);
  });
  const allMessages = uniquePersistedMissionChatMessages.length > 0
    ? [...sourceMessages, ...uniquePersistedMissionChatMessages]
    : sourceMessages;
  const compactMessages = compactAgentMessages(allMessages);
  const visibleMessages = visibleAgentMessages(compactMessages, 36, 8, { requireRuntimeReports: isLiveBackend, requireTrustedDialogue: isLiveBackend });
  const hiddenMessageCount = Math.max(0, compactMessages.length - visibleMessages.length);
  const [selectedMessageId, setSelectedMessageId] = useState("");
  const [selectedDiagnosticMessageId, setSelectedDiagnosticMessageId] = useState("");
  const [agentDismissedNotificationIds, setAgentDismissedNotificationIds] = useState(() => new Set());
  const selectionScopeRef = useRef("");
  const manualMessageSelectionRef = useRef(false);
  const manualSelectedMessageKeyRef = useRef("");
  const agentThreadRef = useRef(null);
  const agentThreadNativeCleanupRef = useRef(null);
  const thinkingRows = orderedAgentMessagesNewestFirst(
    compactMessages.filter(message =>
      !isRuntimeTranscriptIntegrityWarning(message) &&
      !isProofArtifactAgentMessage(message) &&
      isRuntimeActivityAgentMessage(message),
    ),
  ).slice(0, 5);
  const livePlanRows = orderedAgentMessagesNewestFirst(
    compactMessages.filter(message => {
      const label = String(message?.label || message?.roleLabel || "").toLowerCase();
      return (
        !isLowSignalAgentMessage(message) &&
        !isRuntimeTranscriptIntegrityWarning(message) &&
        !isProofArtifactAgentMessage(message) &&
        !isControlRoomBookkeepingAgentMessage(message) &&
        (
          isRuntimeActivityAgentMessage(message) ||
          message?.emphasis ||
          label.includes("planner") ||
          label.includes("mission review") ||
          label.includes("action") ||
          label.includes("lane")
        )
      );
    }),
  ).slice(0, 5);
  const visibleTimeline = orderedAgentMessagesNewestFirst(
    asList(timelineMoments).filter(item => !isLowSignalAgentMessage(item)),
  ).slice(0, 8);
  const progressValue = clampPercent(workbenchState?.progress?.value);
  const missionStatus = titleizeToken(workbenchState?.missionStatus || missionLoop?.status || "live");
  const progressLabel =
    progressValue == null
      ? workbenchState?.progress?.label || "Live progress metric unavailable"
      : `${workbenchState?.progress?.label || "Progress"} · ${progressValue}%`;
  const liveLaneRows = asList(workbenchState?.lanes).filter(item => item && typeof item === "object").slice(0, 8);
  const liveMissionRows = isLiveBackend ? sortLiveBuilderRows(builderRows) : [];
  const runningLiveMissionRows = liveMissionRows.filter(row => {
    const status = String(row.status || row.statusLabel || "").toLowerCase();
    return ["running", "delegated", "active"].includes(status);
  });
  const preferredRunningLiveMission = runningLiveMissionRows.find(row => {
    const missionId = String(row.id || row.missionId || row.mission_id || "").trim();
    return missionId && missionId !== String(workbenchState?.missionId || "").trim();
  }) || runningLiveMissionRows[0] || null;
  const preferredRunningLiveMissionId = String(
    preferredRunningLiveMission?.id ||
      preferredRunningLiveMission?.missionId ||
      preferredRunningLiveMission?.mission_id ||
      "",
  ).trim();
  const liveLaneRoleSummary = uniq(liveLaneRows.map(item => String(item.role || item.label || "").toLowerCase()))
    .slice(0, 4)
    .map(titleizeToken)
    .join(" / ");
  const agentMissionRouteRows = ["planner", "executor", "verifier"]
    .map(role => {
      const lane = liveLaneRows.find(item => String(item.role || item.label || "").trim().toLowerCase() === role);
      if (!lane) {
        return null;
      }
      const providerRaw = String(lane.provider || lane.providerId || lane.provider_id || "").trim();
      const modelRaw = String(lane.model || lane.modelId || lane.model_id || "").trim();
      const effortRaw = String(lane.effort || "").trim();
      const isDefaultAlias = value => /^(default|workspace default|profile default|route default|model default|provider default)$/i.test(String(value || "").trim());
      const provider = isDefaultAlias(providerRaw) ? "" : providerRaw;
      const model = isDefaultAlias(modelRaw) ? "" : modelRaw;
      const effort = isDefaultAlias(effortRaw) ? "" : effortRaw;
      return {
        role,
        provider,
        model,
        effort,
        label: `${titleizeToken(role)} · ${provider ? titleizeToken(provider) : "provider not reported"} · ${model && model.toLowerCase() !== "default" ? model : "model not reported"}${effort ? ` · ${titleizeToken(effort)}` : ""}`,
      };
    })
    .filter(Boolean);
  const agentBottomRouteRows = [
    ...agentMissionRouteRows,
    {
      role: "done",
      provider: "",
      model: "",
      effort: "",
      label: String(missionStatus || "").toLowerCase().includes("complete") ? "Done · completed" : "Done · pending",
    },
  ];
  useEffect(() => {
    setLocalLaneControlReceipt(null);
  }, [workbenchState?.missionId]);
  const buildLaneControlReceiptView = useCallback((lane, control, receipt = null, status = "pending") => {
    const role = String(lane?.role || lane?.label || "").trim().toLowerCase() || "lane";
    const action = receipt?.action || control?.action || control?.id || "inspect";
    const inspectAction = ["inspect", "runtime"].includes(String(action || "").toLowerCase());
    const mutationProof = receipt?.stateMutationProof || {
      field: "mission.state.current_runtime_lane",
      before: inspectAction ? role : "",
      after: role,
      observedAfterWrite: status === "recorded" || inspectAction,
      observationSource: inspectAction ? "live-lane-inspect-noop" : "pending-backend-write",
    };
    return {
      id: receipt?.receiptId || `local-${workbenchState?.missionId || "mission"}-${role}-${action}`,
      missionId: receipt?.missionId || lane?.missionId || workbenchState?.missionId || "",
      laneRole: role,
      action,
      label: control?.label || titleizeToken(action),
      status: receipt?.status || status,
      detail: receipt?.receiptId
        ? `Durable lane control receipt ${receipt.receiptId} recorded ${action} for ${role}.`
        : inspectAction
          ? `Lane inspect proof observed ${role} from the live mission lane data; no mutation was required.`
        : `Lane control receipt requested for ${role}; waiting for the live backend receipt.`,
      stateMutationProof: mutationProof,
      validation: receipt?.validation || {},
      at: receipt?.generatedAt || new Date().toISOString(),
    };
  }, [workbenchState?.missionId]);
  const visibleLaneControlReceipt = workbenchState?.laneControlReceipt || localLaneControlReceipt || null;
  const livePreviewUrlCandidates = [
    workbenchState?.previewUrl,
    workbenchState?.liveReview?.previewUrl,
    workbenchState?.previewActionUrl,
    workbenchState?.liveReview?.previewActionUrl,
  ];
  const livePreviewActionUrl = livePreviewUrlCandidates.find(isUsablePreviewUrl) || "";
  const livePreviewFrameUrl = livePreviewUrlCandidates.find(isWorkbenchPreviewFrameUrl) || "";
  const visibleMessageEntries = useMemo(
    () => visibleMessages.map((message, index) => ({
      key: stableAgentMessageKey(message, `message-${index}`),
      message,
    })).filter(entry => entry.key),
    [visibleMessages],
  );
  const activeMissionIdForMessages = String(workbenchState?.missionId || "").trim();
  const liveDialogueEntries = visibleMessageEntries.filter(entry =>
    isAgentDialogueTurn(entry?.message) &&
      isTrustedLiveDialogueSource(entry?.message) &&
      (!activeMissionIdForMessages ||
        String(entry?.message?.missionId || entry?.message?.mission_id || "").trim() === activeMissionIdForMessages),
  );
  const liveScopedMessageEntries = useMemo(
    () => {
      if (!isLiveBackend || !activeMissionIdForMessages) {
        return visibleMessageEntries;
      }
      return visibleMessageEntries.filter(entry => {
        const entryMissionId = String(entry?.message?.missionId || entry?.message?.mission_id || "").trim();
        return entryMissionId === activeMissionIdForMessages;
      });
    },
    [activeMissionIdForMessages, isLiveBackend, visibleMessageEntries],
  );
  const threadMessageEntries = isLiveBackend ? liveDialogueEntries : visibleMessageEntries;
  const threadMessages = threadMessageEntries.map(entry => entry.message);
  const visibleMessageKeySignature = threadMessageEntries.map(entry => entry.key).join("|");
  const selectableMessageEntries = useMemo(() => {
    const entries = [];
    const keys = new Set();
    const pushEntry = (message, key) => {
      if (!message || keys.has(key)) return;
      keys.add(key);
      entries.push({ key, message });
    };
    threadMessageEntries.forEach(({ message, key }, index) => {
      pushEntry(message, key || stableAgentMessageKey(message, `message-${index}`));
    });
    return entries;
  }, [threadMessageEntries]);
  const diagnosticMessageEntries = useMemo(() => {
    const entries = [];
    const keys = new Set();
    const pushEntry = (message, key) => {
      if (!message || keys.has(key)) return;
      keys.add(key);
      entries.push({ key, message });
    };
    thinkingRows.forEach((message, index) => {
      pushEntry(message, stableAgentMessageKey(message, `thinking-${index}`));
    });
    livePlanRows.forEach((message, index) => {
      pushEntry(message, stableAgentMessageKey(message, `live-plan-${index}`));
    });
    return entries;
  }, [livePlanRows, thinkingRows]);
  const selectableMessageKeySet = useMemo(
    () => new Set(selectableMessageEntries.map(entry => entry.key)),
    [selectableMessageEntries],
  );
  const messageSelectionScope = [
    liveDataStatus?.previewMode || "preview",
    workbenchState?.missionId || "",
    workbenchState?.missionTitle || "",
    workbenchState?.runtime || "",
  ].join(":");
  const messageSelectionContentSignature = isLiveBackend ? visibleMessageKeySignature : "";
  useEffect(() => {
    setSelectedMessageId(current => {
      const scopeChanged = selectionScopeRef.current !== messageSelectionScope;
      selectionScopeRef.current = messageSelectionScope;
      if (scopeChanged) {
        manualMessageSelectionRef.current = false;
        manualSelectedMessageKeyRef.current = "";
      }
      const manualEntry = manualSelectedMessageKeyRef.current
        ? selectableMessageEntries.find(entry => entry.key === manualSelectedMessageKeyRef.current)
        : null;
      const currentEntry = current
        ? selectableMessageEntries.find(entry => entry.key === current)
        : null;
      const manualEntryMissionId = String(
        manualEntry?.message?.missionId ||
          manualEntry?.message?.mission_id ||
          "",
      ).trim();
      const currentEntryMissionId = String(
        currentEntry?.message?.missionId ||
          currentEntry?.message?.mission_id ||
          "",
      ).trim();
      const scopedMissionId = String(workbenchState?.missionId || "").trim();
      if (
        manualEntry &&
        manualMessageSelectionRef.current &&
        (!isLiveBackend || !scopedMissionId || !manualEntryMissionId || manualEntryMissionId === scopedMissionId)
      ) {
        return manualEntry.key;
      }
      if (
        current &&
        currentEntry &&
        manualMessageSelectionRef.current &&
        (!isLiveBackend || !scopedMissionId || !currentEntryMissionId || currentEntryMissionId === scopedMissionId)
      ) {
        return current;
      }
      const latestRuntimeOutputMessage = threadMessages.find(isRuntimeOutputAgentMessage);
      const latestMeaningfulMessage = latestRuntimeOutputMessage || threadMessages.find(isMeaningfulDefaultAgentMessage);
      const defaultEntry =
        threadMessageEntries.find(entry => entry.message === latestMeaningfulMessage) ||
        threadMessageEntries.find(entry => entry.message === threadMessages[threadMessages.length - 1]) ||
        (isLiveBackend ? null : selectableMessageEntries[selectableMessageEntries.length - 1]);
      return defaultEntry?.key || "";
    });
  }, [isLiveBackend, messageSelectionContentSignature, messageSelectionScope, selectableMessageEntries, threadMessageEntries, threadMessages, workbenchState?.missionId]);
  useEffect(() => {
    setSelectedDiagnosticMessageId("");
  }, [messageSelectionScope]);
  useEffect(() => {
    if (!isLiveBackend || !visibleMessageKeySignature) {
      return;
    }
    const node = agentThreadRef.current;
    if (!node) {
      return;
    }
    const scrollToLatest = () => {
      node.scrollTop = node.scrollHeight;
    };
    scrollToLatest();
    const frame = window.requestAnimationFrame(scrollToLatest);
    return () => window.cancelAnimationFrame(frame);
  }, [isLiveBackend, messageSelectionScope, visibleMessageKeySignature]);
  const selectedMessageEntry = selectableMessageEntries.find(entry => entry.key === selectedMessageId) || null;
  const autoSelectedMessageEntry = isLiveBackend
    ? selectedMessageEntry || threadMessageEntries[0] || null
    : selectedMessageEntry;
  const resolvedSelectedMessageKey = autoSelectedMessageEntry?.key || "";
  const selectedMessage = autoSelectedMessageEntry?.message || null;
  const messageSelectionActive = Boolean(autoSelectedMessageEntry && selectedMessage);
  const selectedEvidenceMessage = selectedMessage || null;
  const selectedMessagePreviewCandidates =
    selectedEvidenceMessage && !isAgentDialogueTurn(selectedEvidenceMessage)
      ? previewUrlCandidatesForMessage(selectedEvidenceMessage)
      : [];
  const selectedMessagePreviewActionUrl = selectedMessagePreviewCandidates.find(isUsablePreviewUrl) || "";
  const messageSelectionPinned = !agentPreviewWindowOpen && Boolean(autoSelectedMessageEntry || selectedMessageId);
  const activePreviewActionUrl = agentPreviewWindowOpen
    ? livePreviewActionUrl
    : messageSelectionPinned
    ? selectedMessagePreviewActionUrl
    : isLiveBackend
      ? livePreviewActionUrl
      : livePreviewActionUrl;
  const activePreviewFrameUrl = agentPreviewWindowOpen
    ? livePreviewFrameUrl
    : isLiveBackend || messageSelectionPinned
      ? ""
      : livePreviewFrameUrl;
  const livePreviewFrameBlocked = Boolean(activePreviewActionUrl && !activePreviewFrameUrl);
  const selectedMessageSourceLabel = [
    selectedEvidenceMessage?.label || selectedEvidenceMessage?.roleLabel || "Live runtime report",
    selectedEvidenceMessage?.runtimeId || workbenchState?.runtime || "",
    selectedEvidenceMessage?.createdAt || selectedEvidenceMessage?.meta || "",
  ].filter(Boolean).join(" · ");
  const selectedMessageBody = selectedEvidenceMessage
    ? agentMessageDisplayDetail(selectedEvidenceMessage) || agentMessageDisplayTitle(selectedEvidenceMessage)
    : "";
  const selectedMessageRuntimeLabel = selectedEvidenceMessage?.runtimeId || workbenchState?.runtime || "live";
  const selectedMissionId = String(workbenchState?.missionId || "").trim();
  const liveProofRows = asList(workbenchState?.proofDiff?.rows);
  const liveProofArtifacts = asList(workbenchState?.artifacts);
  const liveWatchdogIssue = [
    ...asList(missionWatchdog?.issues),
    ...asList(missionWatchdog?.problemRegistry?.problems),
  ].find(item => {
    const itemMissionId = String(
      item?.missionId ||
        item?.mission_id ||
        item?.mission ||
        item?.problem?.missionId ||
        item?.problem?.mission_id ||
        "",
    ).trim();
    return selectedMissionId && itemMissionId === selectedMissionId;
  });
  const liveProofNextAction = [
    workbenchState?.progress?.nextAction,
    liveWatchdogIssue?.firstStep,
    liveWatchdogIssue?.nextAction,
    liveWatchdogIssue?.detail,
    liveWatchdogIssue?.message,
    missionWatchdog?.nextAction,
  ].map(value => String(value || "").trim()).find(Boolean) || "";
  const liveProofSourceLabel = [
    liveDataStatus?.source || "control-room summary",
    selectedEvidenceMessage ? "selected mission detail" : "",
    liveProofRows.length ? workbenchState?.proofDiff?.source || "proof rows" : "",
    liveProofArtifacts.length ? "artifact rows" : "",
  ].filter(Boolean).join(" + ");
  const liveProofExcerpt = selectedMessageBody
    ? firstUsefulRuntimeLine(selectedMessageBody).slice(0, 260)
    : "";
  const liveRuntimeReportCount = threadMessages.filter(isRuntimeOutputAgentMessage).length;
  const liveDialogueCount = threadMessages.filter(isAgentDialogueTurn).length;
  const liveProofBriefStats = [
    ["Mission", selectedMissionId ? selectedMissionId.slice(0, 18) : "none", selectedMissionId ? "selected" : "not selected"],
    ["Runtime", titleizeToken(workbenchState?.runtime || missionLoop?.runtime || "live"), selectedMessageRuntimeLabel || "live"],
    ["Reports", liveRuntimeReportCount, selectedEvidenceMessage ? "selected" : "none selected"],
    ["Proof", liveProofRows.length + liveProofArtifacts.length, liveProofRows.length ? "rows attached" : liveProofArtifacts.length ? "artifacts" : "empty"],
  ];
  const providerReadiness = workbenchState?.providerReadiness || {};
  const runtimeCapabilityItems = asList(workbenchState?.runtimeCapabilityInventory?.items)
    .slice(0, 4)
    .map(item => {
      const capabilityText = `${item?.key || ""} ${item?.id || ""} ${item?.label || ""} ${item?.detail || ""}`.toLowerCase();
      if (capabilityText.includes("opencode") && providerReadiness?.openCodeGo?.ready) {
        return {
          ...item,
          status: "ready",
          detail: providerReadiness.openCodeGo.detail || "OPENCODE_API_KEY is visible to the runtime.",
        };
      }
      if (capabilityText.includes("minimax") && providerReadiness?.minimax?.ready) {
        return {
          ...item,
          status: "ready",
          detail: item?.detail || providerReadiness.minimax.detail || "MiniMax auth is visible to the runtime.",
        };
      }
      return item;
    });
  const connectedAppItems = asList(workbenchState?.connectedAppManager?.items).slice(0, 8);
  const priorityConnectedAppItems = connectedAppItems
    .slice()
    .sort((left, right) => {
      const leftId = String(left?.app_id || left?.id || "").toLowerCase();
      const rightId = String(right?.app_id || right?.id || "").toLowerCase();
      const priority = id => id === "oratio-viva" ? 0 : id === "mind-tower" ? 1 : id === "jbheaven" ? 2 : 3;
      return priority(leftId) - priority(rightId);
    })
    .slice(0, 3)
    .map(item => {
      const nativeActions = asList(item.appNativeActions || item.action_hooks);
      const prioritizedActions = nativeActions
        .slice()
        .sort((left, right) => {
          const leftId = String(left?.hookId || left?.hook_id || left?.id || "").toLowerCase();
          const rightId = String(right?.hookId || right?.hook_id || right?.id || "").toLowerCase();
          const priority = id => id.includes("timebox") ? 0 : id.includes("skill") ? 1 : 2;
          return priority(leftId) - priority(rightId);
        });
      const action =
        prioritizedActions.find(candidate => String(candidate?.hookId || candidate?.hook_id || "").toLowerCase().includes("skill")) ||
        prioritizedActions[0] ||
        null;
      const hookId = action?.hookId || action?.hook_id || action?.id || "";
      const mode = action
        ? (String(hookId).toLowerCase().includes("skill") ? "skill" : "run")
        : "run";
      const managerRole = titleizeToken(item.ui_hints?.runtimeManager || item.ui_hints?.bridgeRole || item.bridge_transport || "app manager");
      const aliases = asList(item.ui_hints?.aliases).slice(0, 4).join(" · ");
      const latestTask = item.latest_task_result || item.latestTaskResult || {};
      const latestPayload = latestTask.payload || {};
      const latestSummary =
        item.latestSummary ||
        latestTask.resultSummary ||
        latestTask.result_summary ||
        item.contextSummary ||
        "No automation proof reported yet.";
      const statusLabel =
        item.statusLabel ||
        `${titleizeToken(item.status || "unknown")} / ${titleizeToken(item.bridge_health || "unknown")}`;
      const proofLabel = [
        latestTask.label || latestTask.taskId || latestTask.task_id || "App automation",
        latestTask.status ? titleizeToken(latestTask.status) : "",
        latestTask.approvalStatus || latestTask.approval_status ? `approval ${titleizeToken(latestTask.approvalStatus || latestTask.approval_status)}` : "",
      ].filter(Boolean).join(" · ");
      const safeDirections = asList(latestPayload.safeDirections).slice(0, 3);
      const skillCandidate = latestPayload.skillCandidate || item.ui_hints?.skillCandidate || "";
      const startCommand = item.ui_hints?.startCommand || latestPayload.startCommand || "";
      const healthUrl = item.ui_hints?.healthUrl || latestPayload.healthUrl || "";
      const workspaceQuickActions = [
        startCommand
          ? {
              action: {
                actionId: `start-${item.app_id || item.id || ""}`,
                label: "Start app",
                commandSurface: "bridge.start_app",
                requiresApproval: false,
              },
              hookId: `start-${item.app_id || item.id || ""}`,
              mode: "workspace",
              label: "Start app",
              review: false,
            }
          : null,
        healthUrl
          ? {
              action: {
                actionId: `check-${item.app_id || item.id || ""}-health`,
                label: "Check health",
                commandSurface: "bridge.app_health",
                requiresApproval: false,
              },
              hookId: `check-${item.app_id || item.id || ""}-health`,
              mode: "workspace",
              label: "Check health",
              review: false,
            }
          : null,
      ].filter(Boolean);
      const nativeQuickActions = (prioritizedActions.length ? prioritizedActions : [action].filter(Boolean))
        .slice(0, 2)
        .map(candidate => {
          const candidateHookId = candidate?.hookId || candidate?.hook_id || candidate?.id || "";
          const candidateMode = String(candidateHookId).toLowerCase().includes("skill") ? "skill" : "run";
          const baseLabel = candidate?.label || (candidateMode === "skill" ? "Make Skill" : "Use In Agent");
          const visibleLabel = /^draft\b/i.test(String(baseLabel || "")) ? baseLabel : `Draft ${baseLabel}`;
          return {
            action: candidate,
            hookId: candidateHookId,
            mode: candidateMode,
            label: visibleLabel,
            review: Boolean(candidate?.requiresApproval || candidate?.requires_approval),
          };
        });
      const quickActions = [...workspaceQuickActions, ...nativeQuickActions].slice(0, 4);
      return {
        item,
        action,
        mode,
        hookId,
        managerRole,
        aliases,
        label: action?.label || (mode === "skill" ? "Make Skill" : "Use In Agent"),
        review: Boolean(action?.requiresApproval || action?.requires_approval),
        quickActions,
        latestSummary,
        statusLabel,
        proofLabel,
        safeDirections,
        skillCandidate,
        startCommand,
        healthUrl,
      };
    });
  const liveThreadProof = agentLiveThreadProof?.schema === "fluxio.agent_live_thread_proof.v1"
    ? agentLiveThreadProof
    : null;
  const liveThreadProofTone =
    !liveThreadProof || ["loading", "waiting_for_detail", "no_mission_selected"].includes(liveThreadProof.status)
      ? "warn"
      : liveThreadProof.status === "error"
        ? "bad"
        : liveThreadProof.transcriptStatus === "attached" || Number(liveThreadProof.runtimeReportCount || 0) > 0
          ? "good"
          : "neutral";
  const liveThreadProofStats = liveThreadProof
    ? [
        ["Messages", Number(liveThreadProof.agentMessageCount || 0), `${Number(liveThreadProof.realMessageCount || 0)} live rows`],
        ["Transcript", titleizeToken(liveThreadProof.transcriptStatus || "pending"), liveThreadProof.transcriptSessionId || "no session"],
        ["Budget", titleizeToken(liveThreadProof.budgetStatus || "pending"), liveThreadProof.payloadBytes ? `${Math.round(Number(liveThreadProof.payloadBytes) / 1000)} KB` : "no payload"],
        ["Cache", titleizeToken(liveThreadProof.cacheStatus || "pending"), liveThreadProof.cacheFreshness || liveThreadProof.source || "live detail"],
      ]
    : [];
  const hasLiveRuntimeReports = liveRuntimeReportCount > 0;
  const liveMissionReportBlocked =
    isLiveBackend &&
    !hasLiveRuntimeReports &&
    threadMessages.length === 0;
  const selectedMessageTimeLabel = timestampLabel(selectedEvidenceMessage?.createdAt || selectedEvidenceMessage?.timestamp || selectedEvidenceMessage?.time || "");
  const selectedMessageKindLabel = isRuntimeOutputAgentMessage(selectedEvidenceMessage)
    ? "Proof artifact"
    : isLiveRuntimeReportMessage(selectedEvidenceMessage)
      ? "Runtime activity"
    : selectedEvidenceMessage?.processMessage
      ? "Runtime trace"
      : selectedEvidenceMessage
        ? "Mission message"
        : "Runtime report";
  const previewState = messageSelectionPinned
    ? "selected-message"
    : agentPreviewWindowOpen
      ? "agent-preview-window"
    : activePreviewFrameUrl
      ? "mission-frame"
      : "empty";
  const liveThreadFirstStats = [
    ["Dialogue", liveDialogueCount, hiddenMessageCount > 0 ? `${hiddenMessageCount} evidence rows held back` : "mission scoped"],
    ["Selected", selectedMessage ? "1" : "0", selectedMessage ? "turn pinned" : "waiting"],
    ["Lanes", liveLaneRows.length, liveLaneRoleSummary || "planner/executor/verifier"],
    ["Alerts", Number(liveDataStatus?.notificationCount || 0), `${Number(liveDataStatus?.sliceNotificationCount || 0)} slice`],
  ];
  const liveAgentNotificationRows = isLiveBackend
    ? asList(notificationItems)
        .map((item, index) => ({ item, id: referenceNotificationId(item, index) }))
        .slice(0, 4)
        .filter(entry => entry.id && !agentDismissedNotificationIds.has(entry.id))
    : [];
  const clearAgentNotifications = useCallback(() => {
    setAgentDismissedNotificationIds(current => {
      const next = new Set(current);
      for (const entry of liveAgentNotificationRows) {
        next.add(entry.id);
      }
      return next;
    });
  }, [liveAgentNotificationRows]);
  const dismissAgentNotification = useCallback(id => {
    const normalized = String(id || "").trim();
    if (!normalized) return;
    setAgentDismissedNotificationIds(current => {
      const next = new Set(current);
      next.add(normalized);
      return next;
    });
  }, []);
  const restoreAgentNotifications = useCallback(() => {
    setAgentDismissedNotificationIds(new Set());
  }, []);
  const liveDiagnosticStats = [
    ["Trace", thinkingRows.length, "rows"],
    ["Lanes", liveLaneRows.length, liveLaneRoleSummary || "runtime"],
    ["Plan", livePlanRows.length, "steps"],
  ];
  const livePreviewLabel =
    workbenchState?.previewSourceLabel ||
    workbenchState?.previewLabel ||
    (isLiveBackend ? "No live preview frame attached" : "Local layout preview");
  const selectedRoute = routeControls?.selectedRoute || {};
  const agentLiveRouteStatus = [
    titleizeToken(selectedRoute.provider || "openai-codex"),
    selectedRoute.model || selectedModelLabel || "gpt-5.5",
    titleizeToken(selectedRoute.effort || "high"),
  ]
    .filter(Boolean)
    .join(" · ");
  const selectAgentMessage = useCallback(messageKey => {
    const normalizedMessageKey = String(messageKey || "").trim();
    if (!normalizedMessageKey.trim()) return;
    if (isLiveBackend && !selectableMessageKeySet.has(normalizedMessageKey)) return;
    setAgentPreviewWindowOpen(false);
    manualMessageSelectionRef.current = true;
    manualSelectedMessageKeyRef.current = normalizedMessageKey;
    flushSync(() => {
      setSelectedMessageId(normalizedMessageKey);
    });
  }, [isLiveBackend, selectableMessageKeySet]);
  const openAgentPreviewWindow = useCallback(() => {
    manualMessageSelectionRef.current = false;
    manualSelectedMessageKeyRef.current = "";
    setSelectedMessageId("");
    setAgentPreviewWindowOpen(true);
    window.requestAnimationFrame(() => {
      agentPreviewPanelRef.current?.scrollIntoView?.({ block: "start", behavior: "smooth" });
    });
  }, []);
  const bindAgentThreadRef = useCallback(node => {
    if (agentThreadNativeCleanupRef.current) {
      agentThreadNativeCleanupRef.current();
      agentThreadNativeCleanupRef.current = null;
    }
    agentThreadRef.current = node;
    if (!node || !isLiveBackend) return;
    const selectFromDomEvent = event => {
      const row = event.target?.closest?.('[data-agent-message-key][data-message-zone="thread"]');
      if (!row || !node.contains(row)) return;
      const messageKey = row.getAttribute("data-agent-message-key");
      if (!messageKey) return;
      node.setAttribute("data-live-agent-native-selected-key", messageKey);
      window.__fluxioAgentThreadNativeSelectCount = Number(window.__fluxioAgentThreadNativeSelectCount || 0) + 1;
      selectAgentMessage(messageKey);
    };
    const selectFromDomKey = event => {
      if (event.key !== "Enter" && event.key !== " ") return;
      const row = event.target?.closest?.('[data-agent-message-key][data-message-zone="thread"]');
      if (!row || !node.contains(row)) return;
      const messageKey = row.getAttribute("data-agent-message-key");
      if (!messageKey) return;
      event.preventDefault();
      node.setAttribute("data-live-agent-native-selected-key", messageKey);
      window.__fluxioAgentThreadNativeSelectCount = Number(window.__fluxioAgentThreadNativeSelectCount || 0) + 1;
      selectAgentMessage(messageKey);
    };
    node.addEventListener("click", selectFromDomEvent, true);
    node.addEventListener("pointerdown", selectFromDomEvent, true);
    node.addEventListener("keydown", selectFromDomKey, true);
    agentThreadNativeCleanupRef.current = () => {
      node.removeEventListener("click", selectFromDomEvent, true);
      node.removeEventListener("pointerdown", selectFromDomEvent, true);
      node.removeEventListener("keydown", selectFromDomKey, true);
    };
  }, [isLiveBackend, selectAgentMessage]);
  useEffect(() => () => {
    if (agentThreadNativeCleanupRef.current) {
      agentThreadNativeCleanupRef.current();
      agentThreadNativeCleanupRef.current = null;
    }
  }, []);
  const selectDiagnosticMessage = useCallback(messageKey => {
    const normalizedMessageKey = String(messageKey || "").trim();
    if (!normalizedMessageKey) return;
    if (isLiveBackend && !diagnosticMessageEntries.some(entry => entry.key === normalizedMessageKey)) return;
    setSelectedDiagnosticMessageId(normalizedMessageKey);
  }, [diagnosticMessageEntries, isLiveBackend]);
  const handleAgentMessageKeyDown = useCallback((event, messageKey) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      selectAgentMessage(messageKey);
    }
  }, [selectAgentMessage]);
  const handleAgentThreadMessageSelectionEvent = useCallback(event => {
    const row = event.target?.closest?.('[data-agent-message-key][data-message-zone="thread"]');
    if (!row || !event.currentTarget?.contains?.(row)) return;
    const messageKey = row.getAttribute("data-agent-message-key");
    if (messageKey) selectAgentMessage(messageKey);
  }, [selectAgentMessage]);
  const handleAgentThreadMessageKeyDownCapture = useCallback(event => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const row = event.target?.closest?.('[data-agent-message-key][data-message-zone="thread"]');
    if (!row || !event.currentTarget?.contains?.(row)) return;
    const messageKey = row.getAttribute("data-agent-message-key");
    if (!messageKey) return;
    event.preventDefault();
    selectAgentMessage(messageKey);
  }, [selectAgentMessage]);
  useEffect(() => {
    if (!isLiveBackend) return undefined;
    const node = agentThreadRef.current;
    if (!node) return undefined;
    const selectFromDomEvent = event => {
      const row = event.target?.closest?.('[data-agent-message-key][data-message-zone="thread"]');
      if (!row || !node.contains(row)) return;
      const messageKey = row.getAttribute("data-agent-message-key");
      if (messageKey) selectAgentMessage(messageKey);
    };
    const selectFromDomKey = event => {
      if (event.key !== "Enter" && event.key !== " ") return;
      const row = event.target?.closest?.('[data-agent-message-key][data-message-zone="thread"]');
      if (!row || !node.contains(row)) return;
      const messageKey = row.getAttribute("data-agent-message-key");
      if (!messageKey) return;
      event.preventDefault();
      selectAgentMessage(messageKey);
    };
    node.addEventListener("click", selectFromDomEvent, true);
    node.addEventListener("pointerdown", selectFromDomEvent, true);
    node.addEventListener("keydown", selectFromDomKey, true);
    return () => {
      node.removeEventListener("click", selectFromDomEvent, true);
      node.removeEventListener("pointerdown", selectFromDomEvent, true);
      node.removeEventListener("keydown", selectFromDomKey, true);
    };
  }, [isLiveBackend, selectAgentMessage]);
  const handleDiagnosticMessageKeyDown = useCallback((event, messageKey) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      selectDiagnosticMessage(messageKey);
    }
  }, [selectDiagnosticMessage]);
  const handleLiveLaneControl = useCallback(async (lane, control) => {
    const laneWithMission = {
      ...lane,
      missionId: lane?.missionId || workbenchState?.missionId || "",
    };
    setLocalLaneControlReceipt(buildLaneControlReceiptView(laneWithMission, control, null, "pending"));
    try {
      const response = await fluxioAction(
        onRequestAction,
        `agent:lane:${control?.action || control?.id || "inspect"}`,
        { lane: laneWithMission, control },
      );
      const durableReceipt = response?.laneControlReceipt || response?.receipt || null;
      if (durableReceipt) {
        setLocalLaneControlReceipt(buildLaneControlReceiptView(laneWithMission, control, durableReceipt, "recorded"));
      }
    } catch (error) {
      setLocalLaneControlReceipt(current => {
        const baseline = current || buildLaneControlReceiptView(laneWithMission, control, null, "error");
        return {
          ...baseline,
          status: "error",
          detail: `Lane control receipt failed: ${error}`,
          stateMutationProof: {
            ...baseline.stateMutationProof,
            field: "mission.state.current_runtime_lane",
            after: String(laneWithMission.role || laneWithMission.label || "lane").toLowerCase(),
            observedAfterWrite: false,
          },
        };
      });
    }
  }, [buildLaneControlReceiptView, onRequestAction, workbenchState?.missionId]);
  return (
    <div
      className="fluxos-agent-grid"
      data-agent-clarity-mode={normalizedAgentClarityMode}
      data-agent-focus-contract="agent-live-dialogue-first"
      data-agent-preview-open={agentPreviewWindowOpen ? "true" : "false"}
    >
      <section className="fluxos-agent-main">
        <div className="fluxos-section-head">
          <span>Agent Live</span>
          <strong>{isLiveBackend ? workbenchState?.missionTitle || "Live NAS run state" : "Reproduce Fluxio UI and prepare merge"}</strong>
          {isLiveBackend ? (
            <div className="fluxos-agent-route-pills" aria-label="Agent route" aria-hidden={agentFocusMode ? "true" : "false"}>
              {agentMissionRouteRows.length ? (
                agentMissionRouteRows.map(route => (
                  <span
                    className={`mini-pill muted ${route.role === "executor" ? "agent-route-executor" : ""}`.trim()}
                    data-agent-mission-route-role={route.role}
                    key={`agent-route-${route.role}-${route.provider}-${route.model}`}
                  >
                    {route.label}
                  </span>
                ))
              ) : (
                <>
                  <span className="mini-pill muted">{agentLiveRouteStatus}</span>
                  <span className="mini-pill muted">Route not reported</span>
                </>
              )}
            </div>
          ) : null}
          {isLiveBackend ? (
            <div className="fluxos-builder-clarity-switch" aria-label="Agent clarity mode" data-agent-clarity-switch="true">
              <button
                className={agentFocusMode ? "active" : ""}
                onClick={() => setLiveAgentClarityMode("focus")}
                type="button"
              >
                Live
              </button>
              <button
                className={!agentFocusMode ? "active" : ""}
                onClick={() => setLiveAgentClarityMode("full")}
                type="button"
              >
                Details
              </button>
            </div>
          ) : null}
        </div>
        <LiveOperationsBrief
          activeRows={[]}
          liveDataStatus={liveDataStatus}
          onOpenAgent={() => onRequestAction?.("agent:open-current-mission", { missionId: workbenchState?.missionId })}
          onOpenNotifications={() => onRequestAction?.("notifications:show-live-stack")}
          onOpenQueue={() => onRequestAction?.("builder:open-project-queue")}
          projectProgressHistory={props.projectProgressHistory}
          threadRows={threadMessages}
          workbenchState={workbenchState}
        />
        {isLiveBackend ? (
          <section className="fluxos-agent-notification-rail" aria-label="Live Agent notification controls" data-live-agent-notification-rail="true">
            <div className="fluxos-thread-head">
              <span>Live notifications</span>
              <strong>
                {liveAgentNotificationRows.length} shown
                {Number(liveDataStatus?.notificationCount || 0) ? ` · ${Number(liveDataStatus.notificationCount || 0)} total` : ""}
              </strong>
            </div>
            <div className="fluxos-agent-notification-actions">
              <button
                data-notification-clear-all="true"
                disabled={liveAgentNotificationRows.length === 0}
                onClick={clearAgentNotifications}
                type="button"
              >
                Mark visible read
              </button>
              <button
                data-notification-restore-dismissed="true"
                disabled={agentDismissedNotificationIds.size === 0}
                onClick={restoreAgentNotifications}
                type="button"
              >
                Restore
              </button>
              <button onClick={() => onRequestAction?.("notifications:show-live-stack")} type="button">
                Open stack
              </button>
            </div>
            {liveAgentNotificationRows.length ? (
              <div className="fluxos-agent-notification-list">
                {liveAgentNotificationRows.map(({ item, id }) => {
                  const missionId = item?.missionId || item?.mission_id || "";
                  const title = firstMeaningfulNotificationLine(item) || item?.title || item?.headline || "Live mission update";
                  const detail = item?.agentMessage || item?.detail || item?.message || item?.summary || "Live NAS notification.";
                  return (
                    <article data-notification-card="true" key={id}>
                      <div>
                        <span>{titleizeToken(item?.kind || item?.type || "mission update")}</span>
                        <strong>{sanitizeDisplayTitle(title)}</strong>
                        <p>{sanitizeDisplayTitle(detail)}</p>
                        <small>{timestampLabel(item?.createdAt || item?.timestamp || item?.time || "") || (missionId ? `Mission ${missionId}` : "Live NAS")}</small>
                      </div>
                      <div>
                        <button
                          disabled={!missionId}
                          onClick={() => missionId && onSelectFlow?.(missionId)}
                          type="button"
                        >
                          Open
                        </button>
                        <button
                          data-notification-dismiss-inline="true"
                          onClick={() => dismissAgentNotification(id)}
                          type="button"
                        >
                          Dismiss
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <article className="fluxos-flow-empty">
                <span>Live data only</span>
                <strong>No visible notifications</strong>
                <p>Agent is connected to live NAS data; dismissed updates can be restored above.</p>
              </article>
            )}
          </section>
        ) : null}
        {isLiveBackend ? (
          <div
            aria-atomic="true"
            aria-label="Mission progress"
            aria-live="polite"
            className="fluxos-agent-progress"
            role="status"
          >
            <div>
              <span>{missionStatus}</span>
              <strong>{progressLabel}</strong>
              {workbenchState?.progress?.nextAction ? <p>{workbenchState.progress.nextAction}</p> : null}
            </div>
            {progressValue == null ? (
              <em>No live percentage returned</em>
            ) : (
              <i style={{ "--progress": `${progressValue}%` }} />
            )}
          </div>
        ) : null}
        {isLiveBackend ? (
          <section
            aria-label="Agent Live command band"
            className="fluxos-agent-thread-first-band"
            data-live-agent-thread-first-band="true"
          >
            <div className="fluxos-agent-thread-first-copy">
              <span>Thread-first Agent</span>
              <strong>{workbenchState?.missionTitle || "Live mission thread"}</strong>
              <p>{workbenchState?.progress?.nextAction || "Continue, modify, launch, verify, or summarize this Hermes mission."}</p>
            </div>
            <div className="fluxos-agent-thread-first-metrics" aria-label="Live Agent thread metrics">
              {liveThreadFirstStats.map(([label, value, detail]) => (
                <article key={`agent-thread-first-${label}`}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                  <small>{detail}</small>
                </article>
              ))}
            </div>
            <div className="fluxos-agent-thread-first-actions">
              <button
                data-live-agent-action="continue"
                onClick={() => onRequestAction?.("agent:continue-prefill")}
                type="button"
              >
                Continue
              </button>
              <button
                data-live-agent-action="modify"
                onClick={() => onRequestAction?.("run:modify")}
                type="button"
              >
                Modify
              </button>
              <button
                data-live-agent-action="launch"
                data-live-agent-launch-action="true"
                onClick={() => onRequestAction?.("launch:mission", { sourceSurface: "agent" })}
                type="button"
              >
                Launch
              </button>
              <button
                data-live-agent-action="verify"
                onClick={() => {
                  setLiveAgentClarityMode("full");
                  onRequestAction?.("run:proof");
                }}
                type="button"
              >
                Verify
              </button>
              <button
                data-live-agent-action="summarize"
                onClick={() => onRequestAction?.("run:summarize")}
                type="button"
              >
                Summarize
              </button>
              <button
                data-live-agent-action="preview"
                disabled={!livePreviewActionUrl}
                onClick={openAgentPreviewWindow}
                title={livePreviewActionUrl ? "Open the live preview window inside Agent" : "No preview URL has been reported yet"}
                type="button"
              >
                Preview
              </button>
            </div>
          </section>
        ) : null}
        {isLiveBackend ? (
          <section
            aria-label="Agent Live thread connection"
            className={`fluxos-agent-live-thread-proof tone-${liveThreadProofTone}`}
            data-agent-live-thread-proof="true"
            data-live-thread-proof-status={liveThreadProof?.status || "missing"}
          >
            <div className="fluxos-agent-live-thread-proof-copy">
              <span>Thread connection</span>
              <strong>{liveThreadProof?.statusLabel || "Waiting for live mission detail"}</strong>
              <p>
                {liveThreadProof?.nextAction ||
                  "This proves the Agent Live panel is attached to the selected mission detail."}
              </p>
            </div>
            <div className="fluxos-agent-live-thread-proof-grid" aria-label="Agent Live connection metrics">
              {liveThreadProofStats.length ? liveThreadProofStats.map(([label, value, detail]) => (
                <article data-agent-live-thread-proof-metric={String(label).toLowerCase()} key={`live-thread-proof-${label}`}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                  <small>{detail}</small>
                </article>
              )) : (
                <article data-agent-live-thread-proof-metric="missing">
                  <span>Live detail</span>
                  <strong>Pending</strong>
                  <small>No mission-detail proof object is attached.</small>
                </article>
              )}
            </div>
          </section>
        ) : null}
        {isLiveBackend && runtimeCapabilityItems.length ? (
          <section
            className="fluxos-runtime-capability-strip"
            aria-label="Runtime capability inventory"
            data-runtime-capability-inventory="true"
          >
            {runtimeCapabilityItems.map(item => (
              <article key={item.key || item.label}>
                <span>{titleizeToken(item.runtime || workbenchState?.runtime || "runtime")}</span>
                <strong>{item.label}</strong>
                <small>{titleizeToken(item.status || "available")} · {item.detail}</small>
              </article>
            ))}
          </section>
        ) : null}
        {isLiveBackend && priorityConnectedAppItems.length ? (
          <section
            aria-label="Connected app runtime handoff lane"
            className="fluxos-connected-app-quick-lane"
            data-agent-connected-app-quick-lane="true"
          >
            <div>
              <span>App handoff lane</span>
              <strong>Use your apps through Agent runtimes</strong>
            </div>
            <div className="fluxos-connected-app-quick-items">
              {priorityConnectedAppItems.map(row => (
                <article
                  data-agent-connected-app-quick-card="true"
                  data-connected-app-id={row.item.app_id || row.item.id || ""}
                  data-connected-app-manager-role={row.managerRole}
                  data-connected-app-next-action={row.label}
                  data-connected-app-readiness={row.statusLabel}
                  data-connected-app-proof={row.proofLabel}
                  key={`connected-app-quick-${row.item.id || row.item.session_id || row.item.app_id || row.label}`}
                >
                  <span>{row.managerRole}</span>
                  <strong>{row.item.label || row.item.app_name || row.item.app_id || "Connected app"}</strong>
                  <small>{row.aliases ? `Aliases: ${row.aliases}` : "Aliases not reported"}</small>
                  <em data-connected-app-automation-proof="true">
                    {row.proofLabel ? `${row.proofLabel}: ${row.latestSummary}` : row.latestSummary}
                  </em>
                  <small data-connected-app-safe-directions="true">
                    {row.safeDirections.length
                      ? `Safe next: ${row.safeDirections[0]}`
                      : row.skillCandidate
                        ? `Skill route: ${row.skillCandidate}`
                        : `Readiness: ${row.statusLabel}`}
                  </small>
                  {row.startCommand || row.healthUrl ? (
                    <small data-connected-app-execution-truth="true">
                      {row.startCommand ? `Start: ${row.startCommand}` : `Health: ${row.healthUrl}`}
                    </small>
                  ) : null}
                  <div className="fluxos-connected-app-quick-actions">
                    {row.quickActions.map(actionRow => (
                      <button
                        data-agent-connected-app-native-action={actionRow.hookId || actionRow.label}
                        data-agent-connected-app-native-mode={actionRow.mode}
                        key={`${row.item.app_id || row.item.id || row.label}-${actionRow.hookId || actionRow.label}`}
                        onClick={() => (
                          actionRow.mode === "workspace"
                            ? fluxioAction(onRequestAction, "setup:run-action", actionRow.action)
                            : typeof onConnectedAppHandoff === "function"
                            ? onConnectedAppHandoff(row.item, actionRow.mode, actionRow.action)
                            : fluxioAction(onRequestAction, actionRow.mode === "skill" ? "bridge:make-skill" : "bridge:agent-handoff", { session: row.item, action: actionRow.action })
                        )}
                        type="button"
                      >
                        {actionRow.label} · {actionRow.review ? "review" : "ready"}
                      </button>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </section>
        ) : null}
        {isLiveBackend && connectedAppItems.length ? (
          <section
            aria-label="App runtime manager"
            className="fluxos-connected-app-manager"
            data-agent-connected-app-manager="true"
          >
            <div className="fluxos-thread-head">
              <span>App runtime manager</span>
              <strong>{connectedAppItems.length} bridge{connectedAppItems.length === 1 ? "" : "s"}</strong>
            </div>
            <div className="fluxos-connected-app-manager-grid">
              {connectedAppItems.map(item => {
                const nativeActions = asList(item.appNativeActions || item.action_hooks);
                const managerRole = titleizeToken(item.ui_hints?.runtimeManager || item.ui_hints?.bridgeRole || item.bridge_transport || "app manager");
                const nextNativeAction = nativeActions[0];
                const nextActionLabel = nextNativeAction?.label || titleizeToken(nextNativeAction?.hookId || nextNativeAction?.hook_id || "Use in Agent");
                const nextActionReview = Boolean(nextNativeAction?.requiresApproval || nextNativeAction?.requires_approval);
                const appId = item.app_id || item.id || "";
                const latestPayload = item.latest_task_result?.payload || {};
                const startCommand = item.ui_hints?.startCommand || latestPayload.startCommand || "";
                const healthUrl = item.ui_hints?.healthUrl || latestPayload.healthUrl || item.ui_hints?.bridgeHealthUrl || "";
                return (
                <article
                  data-agent-connected-app-card="true"
                  data-connected-app-manager-role={managerRole}
                  data-connected-app-native-action-count={nativeActions.length}
                  data-connected-app-next-action={nextActionLabel}
                  data-connected-app-id={item.app_id || item.id || ""}
                  key={item.id || item.session_id || item.app_id || item.label}
                >
                  <div>
                    <span>{managerRole}</span>
                    <strong>{item.label || item.app_name || item.app_id || "Connected app"}</strong>
                    <p>{item.latestSummary || item.latest_task_result?.resultSummary || "No live context body reported yet."}</p>
                    <p className="fluxos-connected-app-next" data-connected-app-next-action-copy="true">
                      Next: {nextActionLabel} · {nextActionReview ? "review before write" : "ready to draft/run"}
                    </p>
                    {item.contextSummary && item.contextSummary !== item.latestSummary ? (
                      <p>{item.contextSummary}</p>
                    ) : null}
                    <small>{item.statusLabel || `${titleizeToken(item.status || "unknown")} / ${titleizeToken(item.bridge_health || "unknown")}`}</small>
                    {asList(item.ui_hints?.aliases).length ? (
                      <small data-connected-app-aliases="true">Aliases: {asList(item.ui_hints.aliases).slice(0, 5).join(" · ")}</small>
                    ) : null}
                  </div>
                  {nativeActions.length ? (
                    <div className="fluxos-connected-app-hook-list" data-connected-app-native-actions="true">
                      {nativeActions.slice(0, 3).map(action => {
                        const hookId = action?.hookId || action?.hook_id || action?.id || "";
                        const mode = action?.handoffMode || (String(hookId).toLowerCase().includes("skill") ? "skill" : "run");
                        const requiresApproval = Boolean(action?.requiresApproval || action?.requires_approval);
                        return (
                          <button
                            data-agent-connected-app-native-action={hookId || action?.label || "app-action"}
                            data-agent-connected-app-native-mode={mode}
                            key={`${item.id || item.app_id}-${hookId || action?.label}`}
                            onClick={() => (
                              typeof onConnectedAppHandoff === "function"
                                ? onConnectedAppHandoff(item, mode, action)
                                : fluxioAction(onRequestAction, mode === "skill" ? "bridge:make-skill" : "bridge:agent-handoff", { session: item, action })
                            )}
                            type="button"
                          >
                            <strong>{action?.label || titleizeToken(hookId || "App action")}</strong>
                            <span>{requiresApproval ? "Review" : "Ready"} · {titleizeToken(action?.riskLevel || action?.risk_level || "low")}</span>
                          </button>
                        );
                      })}
                    </div>
                  ) : null}
                  <div className="fluxos-connected-app-actions">
                    {startCommand && appId ? (
                      <button
                        data-agent-connected-app-action="start"
                        onClick={() =>
                          fluxioAction(onRequestAction, "setup:run-action", {
                            actionId: `start-${appId}`,
                            label: `Start ${item.app_name || item.label || appId}`,
                            commandSurface: "bridge.start_app",
                            requiresApproval: false,
                          })
                        }
                        type="button"
                      >
                        Start app
                      </button>
                    ) : null}
                    {healthUrl && appId ? (
                      <button
                        data-agent-connected-app-action="health"
                        onClick={() =>
                          fluxioAction(onRequestAction, "setup:run-action", {
                            actionId: `check-${appId}-health`,
                            label: `Check ${item.app_name || item.label || appId} health`,
                            commandSurface: "bridge.app_health",
                            requiresApproval: false,
                          })
                        }
                        type="button"
                      >
                        Check health
                      </button>
                    ) : null}
                    <button
                      data-agent-connected-app-action="use"
                      onClick={() => (
                        typeof onConnectedAppHandoff === "function"
                          ? onConnectedAppHandoff(item, "run")
                          : fluxioAction(onRequestAction, "bridge:agent-handoff", { session: item })
                      )}
                      type="button"
                    >
                      Use in Agent
                    </button>
                    <button
                      data-agent-connected-app-action="skill"
                      onClick={() => (
                        typeof onConnectedAppHandoff === "function"
                          ? onConnectedAppHandoff(item, "skill")
                          : fluxioAction(onRequestAction, "bridge:make-skill", { session: item })
                      )}
                      type="button"
                    >
                      Make skill
                    </button>
                  </div>
                </article>
                );
              })}
            </div>
          </section>
        ) : null}
        {isLiveBackend ? (
          <section
            aria-label="Mission evidence brief"
            className="fluxos-agent-proof-brief"
            data-live-agent-no-fallback="true"
            data-live-agent-proof-brief="true"
          >
            <div className="fluxos-agent-proof-brief-copy">
              <span>Mission evidence</span>
              <strong>{selectedEvidenceMessage ? agentMessageDisplayTitle(selectedEvidenceMessage) : workbenchState?.missionTitle || "No selected runtime report"}</strong>
              <p data-live-agent-proof-source="true">{liveProofSourceLabel || "Live source unavailable; no cached proof is rendered."}</p>
            </div>
            <div className="fluxos-agent-proof-brief-metrics" aria-label="Live proof brief metrics">
              {liveProofBriefStats.map(([label, value, detail]) => (
                <article key={`agent-proof-brief-${label}`}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                  <small>{detail}</small>
                </article>
              ))}
            </div>
            <div className="fluxos-agent-proof-brief-next" data-live-agent-next-repair="true">
              <span>{liveProofNextAction ? "Next repair/action" : "No live next action returned"}</span>
              <p>{liveProofNextAction || "The selected mission detail did not return a next-action field; Fluxio leaves this as an explicit live-data gap."}</p>
              {liveProofExcerpt ? <em>{liveProofExcerpt}</em> : <em>No selected runtime excerpt attached yet.</em>}
            </div>
          </section>
        ) : null}
        {isLiveBackend ? (
          <section
            aria-label="Agent Live evidence reader"
            aria-live="polite"
            className="fluxos-agent-selected-report"
            data-live-report-blocked-state={liveMissionReportBlocked ? "true" : "false"}
            data-live-selected-report-reader="true"
          >
            <div className="fluxos-agent-selected-report-head">
              <div>
                <span>Selected live report · Evidence reader</span>
                <strong>{selectedEvidenceMessage ? agentMessageDisplayTitle(selectedEvidenceMessage) : liveMissionReportBlocked ? "No real runtime report returned" : "Waiting for Agent Live evidence"}</strong>
              </div>
              <div className="fluxos-agent-selected-report-meta" aria-label="Selected report source">
                <em>{selectedMessageKindLabel}</em>
                <em>{titleizeToken(selectedMessageRuntimeLabel)}</em>
                {selectedMessageTimeLabel ? <em>{selectedMessageTimeLabel}</em> : null}
                <em>{messageSelectionActive ? "Pinned" : "Refreshing"}</em>
              </div>
            </div>
            <p>
              {selectedMessageSourceLabel ||
                "This reader is built from the selected mission detail endpoint. It does not render cached sample messages."}
            </p>
            {selectedMessageBody ? (
              <pre className="fluxos-agent-selected-report-body" data-live-selected-report-body="true">{selectedMessageBody}</pre>
            ) : (
              <article className="fluxos-flow-empty" data-live-report-empty-state="true">
                <span>Live data only</span>
                <strong>{hasLiveRuntimeReports ? "No selected evidence body returned yet" : "No evidence body selected"}</strong>
                <p>
                  {hasLiveRuntimeReports
                    ? "Agent Live keeps the selection pinned here instead of filling the reader with fallback text."
                    : "Fluxio leaves this reader empty instead of promoting transcript-integrity warnings, checkpoint fragments, the F1 frame, or any older report into the selected message."}
                </p>
                {!hasLiveRuntimeReports && preferredRunningLiveMissionId ? (
                  <button
                    data-live-active-mission-switch="true"
                    onClick={() => onSelectFlow?.(preferredRunningLiveMissionId)}
                    type="button"
                  >
                    Attach active mission
                  </button>
                ) : null}
              </article>
            )}
          </section>
        ) : null}
        {isLiveBackend ? (
          <details
            aria-label="Advanced runtime controls"
            className="fluxos-agent-advanced-drawer"
            data-agent-advanced-drawer="true"
            data-agent-advanced-drawer-kind="runtime"
            open={!agentFocusMode}
          >
            <summary>
              <span>Advanced runtime controls</span>
              <strong>{`${liveLaneRows.length || 0} lanes · ${thinkingRows.length || 0} trace rows`}</strong>
            </summary>
            <section
              aria-label="Agent diagnostics shelf"
              className="fluxos-agent-diagnostics-shelf"
              data-agent-diagnostics-shelf="true"
            >
              <div>
                <span>Diagnostics</span>
                <strong>Trace, lanes, and proof controls stay in this drawer until needed.</strong>
              </div>
              <div className="fluxos-agent-diagnostics-metrics">
                {liveDiagnosticStats.map(([label, value, detail]) => (
                  <article key={`agent-diagnostic-${label}`}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                    <small>{detail}</small>
                  </article>
                ))}
              </div>
            </section>
            <section className="fluxos-agent-lane-board" aria-label="Live sub-agent lane board" data-live-agent-lane-board="true">
            <div className="fluxos-thread-head">
              <span>Sub-agent lane board</span>
              <strong>
                {liveLaneRows.length
                  ? `${liveLaneRows.length} ${liveLaneRoleSummary || "planner/executor/verifier"} lane${liveLaneRows.length === 1 ? "" : "s"}`
                  : "No live lanes"}
              </strong>
            </div>
            {liveLaneRows.length ? (
              <div className="fluxos-agent-lane-grid">
                {liveLaneRows.map((lane, index) => {
                  const laneStatus = String(lane.status || "").toLowerCase();
                  const tone = laneStatus.includes("blocked") || lane.blocker
                    ? "bad"
                    : lane.active || laneStatus.includes("active") || laneStatus.includes("running")
                      ? "good"
                      : laneStatus.includes("ready")
                        ? "neutral"
                        : "warn";
                  return (
                    <article
                      className={`fluxos-agent-lane tone-${tone}`}
                      data-live-agent-lane="true"
                      data-lane-role={String(lane.role || lane.label || "").toLowerCase()}
                      data-lane-status={lane.status || ""}
                      key={lane.id || `${lane.role}-${lane.provider}-${lane.model}-${index}`}
                    >
                      <span>{[lane.role || lane.label || "Lane", lane.phase || lane.source || ""].filter(Boolean).join(" · ")}</span>
                      <strong>{[lane.provider || "provider", lane.model || "model"].filter(Boolean).join(" / ")}</strong>
                      <p>{lane.lastEvent || lane.blocker || "Live lane returned no current event."}</p>
                      <div className="fluxos-agent-lane-meta">
                        <em>{titleizeToken(lane.status || "unknown")}</em>
                        {lane.effort ? <em>{titleizeToken(lane.effort)}</em> : null}
                        {lane.authPresent === true ? <em>Auth ready</em> : lane.authPresent === false ? <em>Auth missing</em> : null}
                        {lane.quotaStatus ? <em>{`Quota ${titleizeToken(lane.quotaStatus)}`}</em> : null}
                      </div>
                      {asList(lane.toolFamilies).length ? (
                        <div className="fluxos-agent-lane-tools">
                          {asList(lane.toolFamilies).slice(0, 4).map(tool => <em key={`${lane.id || index}-${tool}`}>{tool}</em>)}
                        </div>
                      ) : null}
                      <div className="fluxos-agent-lane-controls">
                        {asList(lane.controls).slice(0, 4).map(control => (
                          <button
                            data-live-agent-lane-control="true"
                            data-lane-control-action={control.action || control.id || ""}
                            disabled={control.enabled === false}
                            key={`${lane.id || index}-${control.id || control.action}`}
                            onClick={() => void handleLiveLaneControl(lane, control)}
                            type="button"
                          >
                            {control.label || titleizeToken(control.action || control.id || "Open")}
                          </button>
                        ))}
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <article className="fluxos-flow-empty">
                <span>Live data only</span>
                <strong>No sub-agent lane contract returned</strong>
                <p>The Agent lane board stays empty until the selected NAS mission exposes delegated sessions or provider capability lanes.</p>
              </article>
            )}
            {visibleLaneControlReceipt ? (
              <article className="fluxos-agent-lane-receipt" data-live-agent-lane-control-receipt="true">
                <span>Lane control receipt</span>
                <strong>{visibleLaneControlReceipt.label || titleizeToken(visibleLaneControlReceipt.action || "Action")}</strong>
                <p>{visibleLaneControlReceipt.detail || "Lane action routed."}</p>
                {visibleLaneControlReceipt.stateMutationProof?.field ? (
                  <div className="fluxos-agent-lane-proof" data-live-agent-lane-mutation-proof="true">
                    <em>{visibleLaneControlReceipt.stateMutationProof.field}</em>
                    <strong>
                      {[
                        visibleLaneControlReceipt.stateMutationProof.before || "empty",
                        visibleLaneControlReceipt.stateMutationProof.after || "empty",
                      ].join(" -> ")}
                    </strong>
                    <span>{visibleLaneControlReceipt.stateMutationProof.observedAfterWrite ? "Observed after write" : "Write observation pending"}</span>
                  </div>
                ) : null}
              </article>
            ) : null}
            </section>
            <section className="fluxos-thinking-panel" aria-label="Live runtime thinking and trace">
            <div className="fluxos-thread-head">
              <span>Thinking and runtime trace</span>
              <strong>{thinkingRows.length ? `${thinkingRows.length} live rows` : "waiting"}</strong>
            </div>
            {thinkingRows.length ? thinkingRows.map((message, index) => {
              const messageKey = stableAgentMessageKey(message, `thinking-${index}`);
              const selected = selectedDiagnosticMessageId === messageKey;
              return (
              <article
                aria-pressed={selected}
                className={`fluxos-message process ${message.emphasis ? "emphasis" : ""} ${selected ? "selected" : ""}`.trim()}
                data-agent-message-key={messageKey}
                data-diagnostic-id={messageKey}
                data-mission-id={message.missionId || workbenchState?.missionId || ""}
                data-message-zone="thinking"
                data-runtime-id={message.runtimeId || workbenchState?.runtime || ""}
                data-selected-diagnostic-message={selected ? "true" : "false"}
                key={messageKey}
                onClick={() => selectDiagnosticMessage(messageKey)}
                onKeyDown={event => handleDiagnosticMessageKeyDown(event, messageKey)}
                role="button"
                tabIndex={0}
              >
                <div className="fluxos-message-head">
                  <span>{[message.label || message.roleLabel || "Runtime", message.meta || message.createdAt || ""].filter(Boolean).join(" · ")}</span>
                  <strong>Trace: {agentMessageDisplayTitle(message)}</strong>
                </div>
                {agentMessageDisplayDetail(message) ? <p>{agentMessageDisplayDetail(message)}</p> : null}
                {message.technicalDetail ? (
                  <details className="fluxos-message-trace">
                    <summary>Raw trace</summary>
                    <p>{String(message.technicalDetail).slice(0, 900)}</p>
                  </details>
                ) : null}
              </article>
            );
            }) : (
              <article className="fluxos-flow-empty">
                <span>Live data only</span>
                <strong>No runtime trace rows loaded yet</strong>
                <p>The selected mission thread is real; this panel stays empty until Hermes emits process or thinking evidence.</p>
              </article>
            )}
            </section>
          </details>
        ) : null}
        <section
          className="fluxos-thread"
          data-live-agent-thread-router="true"
          onClickCapture={handleAgentThreadMessageSelectionEvent}
          onKeyDownCapture={handleAgentThreadMessageKeyDownCapture}
          onPointerDownCapture={handleAgentThreadMessageSelectionEvent}
          ref={bindAgentThreadRef}
        >
          <div className="fluxos-thread-head">
            <span>{isLiveBackend ? "Hermes dialogue" : "Thread"}</span>
            <strong>
              {isLiveBackend
                ? (threadMessageEntries.length ? `${threadMessageEntries.length} real turn${threadMessageEntries.length === 1 ? "" : "s"}` : "No dialogue yet")
                : `${threadMessages.length} shown${hiddenMessageCount > 0 ? ` · ${hiddenMessageCount} older` : ""}`}
            </strong>
          </div>
          {threadMessageEntries.length ? threadMessageEntries.map(({ message, key: messageKey }, index) => {
            const messageIsOperatorFollowUp = isOperatorFollowUpAgentMessage(message);
            const messageIsHermesReply = isHermesDialogueReplyAgentMessage(message);
            const messageIsDialogueTurn = messageIsOperatorFollowUp || messageIsHermesReply || isAgentDialogueTurn(message);
            const messageDetail = messageIsDialogueTurn
              ? String(message.detail || message.content || message.message || "").trim()
              : agentMessageDisplayDetail(message);
            const messageRole = messageIsOperatorFollowUp && (!message.role || message.role === "runtime")
              ? "operator"
              : message.role || "assistant";
            const messageSpeaker = messageIsOperatorFollowUp || messageRole === "user" || messageRole === "operator"
              ? "You"
              : messageIsHermesReply || messageRole === "assistant"
                ? /hermes/i.test(`${message.meta || ""} ${asList(message.chips).join(" ")}`)
                  ? "Hermes"
                  : message.label || message.roleLabel || "Hermes"
                : agentMessageDisplayTitle(message);
            const messageBody = messageIsDialogueTurn
              ? messageDetail || agentMessageDisplayTitle(message)
              : messageDetail;
            const messageMeta = [
              messageIsDialogueTurn ? "" : message.label || message.roleLabel || "",
              message.meta || message.createdAt || "",
            ]
              .filter(Boolean)
              .filter(part => String(part || "").trim() !== String(messageSpeaker || "").trim())
              .join(" · ");
            const messageSelected = selectedMessageId === messageKey;
            return (
              <article
                aria-pressed={messageSelected}
                className={`fluxos-message role-${messageRole} ${messageIsDialogueTurn ? "dialogue-turn" : ""} ${message.processMessage && !messageIsOperatorFollowUp && !messageIsHermesReply ? "process" : ""} ${message.emphasis && !messageIsHermesReply ? "emphasis" : ""} ${messageSelected ? "selected" : ""}`.trim()}
                data-agent-conversation-bubble={messageIsDialogueTurn ? "true" : "false"}
                data-agent-message-key={messageKey}
                data-mission-id={message.missionId || workbenchState?.missionId || ""}
                data-message-zone="thread"
                data-runtime-id={message.runtimeId || workbenchState?.runtime || ""}
                data-runtime-report={isRuntimeOutputAgentMessage(message) ? "true" : "false"}
                data-hermes-transcript={!messageIsDialogueTurn && isLiveRuntimeReportMessage(message) ? "true" : "false"}
                data-agent-dialogue-turn={isAgentDialogueTurn(message) ? "true" : "false"}
                data-agent-proof-artifact={isProofArtifactAgentMessage(message) ? "true" : "false"}
                data-agent-runtime-activity={isRuntimeActivityAgentMessage(message) ? "true" : "false"}
                data-selected-agent-message={messageSelected ? "true" : "false"}
                data-turn-id={messageKey}
                key={messageKey}
                onClick={() => selectAgentMessage(messageKey)}
                onKeyDown={event => handleAgentMessageKeyDown(event, messageKey)}
                role="button"
                tabIndex={0}
              >
                <div className="fluxos-message-head">
                  <span>{messageMeta}</span>
                  <strong>{messageIsDialogueTurn ? messageSpeaker : agentMessageDisplayTitle(message)}</strong>
                </div>
                {messageBody ? <p>{messageBody}</p> : null}
                {message.technicalDetail ? (
                  <details className="fluxos-message-trace">
                    <summary>Runtime trace</summary>
                    <p>{String(message.technicalDetail).slice(0, 720)}</p>
                  </details>
                ) : null}
                {!messageIsOperatorFollowUp && !messageIsHermesReply && asList(message.chips).length > 0 ? (
                  <div className="fluxos-message-chips">
                    {asList(message.chips).slice(0, 4).map(chip => <span key={`${message.id || index}-${chip}`}>{chip}</span>)}
                  </div>
                ) : null}
              </article>
            );
          }) : isLiveBackend ? (
            <article className="fluxos-flow-empty">
              <span>Dialogue only</span>
              <strong>No Hermes chat reply yet</strong>
              <p>No Hermes chat transcript is attached for this mission. The latest Model / OpenRuntime message is shown in the run receipt below, while proof, audits, file reads, route context, checkpoints, and commands stay behind evidence or trace drawers.</p>
              {preferredRunningLiveMissionId ? (
                <button
                  data-live-active-mission-switch="true"
                  onClick={() => onSelectFlow?.(preferredRunningLiveMissionId)}
                  type="button"
                >
                  Attach active mission
                </button>
              ) : null}
            </article>
          ) : [
            { id: "u", role: "user", title: "Goal", detail: "Build Fluxio as a usable agent command center." },
            { id: "a", role: "assistant", title: "Fluxio", detail: "I will keep plan, changes, preview, and approvals visible while I work." },
          ].map((message, index) => {
            const messageDetail = message.detail || message.content || message.message || "";
            return (
              <article className={`fluxos-message role-${message.role || "assistant"}`} key={message.id || index}>
                <strong>{message.title || titleizeToken(message.role || "agent")}</strong>
                {messageDetail ? <p>{messageDetail}</p> : null}
              </article>
            );
          })}
        </section>
        <FluxioTurnReceiptStrip runtimeCompartment={runtimeCompartment} />

        <details
          aria-label={isLiveBackend ? "Advanced plan and diagnostic steps" : "Plan"}
          className={isLiveBackend ? "fluxos-agent-advanced-drawer fluxos-agent-plan-drawer" : "fluxos-agent-plan-drawer"}
          data-agent-advanced-drawer="true"
          data-agent-advanced-drawer-kind="plan"
          open={!isLiveBackend || !agentFocusMode}
        >
          <summary>
            <span>{isLiveBackend ? "Plan and diagnostic steps" : "Plan"}</span>
            <strong>{isLiveBackend ? `${livePlanRows.length || 0} steps` : `${AGENT_PLAN.length} steps`}</strong>
          </summary>
        <div className="fluxos-plan-list">
          {isLiveBackend ? (
            livePlanRows.length > 0 ? livePlanRows.map((message, index) => {
              const messageKey = stableAgentMessageKey(message, `live-plan-${index}`);
              const selected = selectedDiagnosticMessageId === messageKey;
              return (
              <article
                aria-pressed={selected}
                className={`fluxos-plan-step status-${message.tone === "bad" ? "blocked" : message.tone === "good" ? "done" : "running"} ${selected ? "selected" : ""}`.trim()}
                data-agent-message-key={messageKey}
                data-diagnostic-id={messageKey}
                data-mission-id={message.missionId || workbenchState?.missionId || ""}
                data-message-zone="plan"
                data-selected-diagnostic-message={selected ? "true" : "false"}
                key={messageKey}
                onClick={() => selectDiagnosticMessage(messageKey)}
                onKeyDown={event => handleDiagnosticMessageKeyDown(event, messageKey)}
                role="button"
                tabIndex={0}
              >
                <span>{message.tone === "good" ? <Check size={16} strokeWidth={2} /> : message.tone === "bad" ? <CircleHelp size={16} strokeWidth={2} /> : <CircleDashed size={16} strokeWidth={2} />}</span>
                <div>
                  <strong>Diagnostic: {agentMessageDisplayTitle(message)}</strong>
                  {agentMessageDisplayDetail(message) ? <p>{agentMessageDisplayDetail(message)}</p> : null}
                </div>
              </article>
            );
            }) : (
              <article className="fluxos-flow-empty">
                <span>Live data only</span>
                <strong>No mission-detail messages loaded</strong>
                <p>{liveDataStatus?.source ? `Current source: ${liveDataStatus.source}.` : "Waiting for the NAS control-room detail endpoint."}</p>
              </article>
            )
          ) : AGENT_PLAN.map(([label, copy, status]) => (
            <article className={`fluxos-plan-step status-${status}`} key={label}>
              <span>{status === "done" ? <Check size={16} strokeWidth={2} /> : status === "running" ? <CircleDashed size={16} strokeWidth={2} /> : <Clock3 size={16} strokeWidth={2} />}</span>
              <div>
                <strong>{label}</strong>
                <p>{copy}</p>
              </div>
            </article>
          ))}
        </div>
        </details>

        <FluxioComposer
          activeCommentTarget={props.activeCommentTarget}
          draft={draft}
          onAttach={onAttach}
          onChangeDraft={onChangeDraft}
          onDictation={onDictation}
          onRequestAction={onRequestAction}
          onSend={onSend}
          placeholder="Message Hermes about this mission..."
        />
        {isLiveBackend && agentBottomRouteRows.length ? (
          <div className="fluxos-agent-bottom-route-summary" data-agent-bottom-route-summary="true" aria-label="Mission stage summary">
            {agentBottomRouteRows.map(route => (
              <span
                className={route.role === "executor" ? "active" : route.role === "done" && /completed/i.test(route.label) ? "done" : ""}
                data-agent-bottom-route-role={route.role}
                key={`agent-bottom-route-${route.role}-${route.provider}-${route.model}`}
              >
                <strong>{titleizeToken(route.role)}</strong>
                <em>{route.role === "done" ? route.label.replace(/^Done\s*·\s*/i, "") : [route.provider ? titleizeToken(route.provider) : "", route.model || ""].filter(Boolean).join(" / ") || "not reported"}</em>
              </span>
            ))}
          </div>
        ) : null}
      </section>

      <section
          className="fluxos-preview-panel"
          ref={agentPreviewPanelRef}
          data-live-message-selection-version="v29"
        data-agent-preview-window="true"
        data-agent-preview-window-open={agentPreviewWindowOpen ? "true" : "false"}
        data-preview-state={previewState}
        data-selected-message-id={resolvedSelectedMessageKey}
        data-selected-message-requested-id={selectedMessageId}
        key={`${workbenchState?.missionId || workbenchState?.missionTitle || "agent-preview"}:${resolvedSelectedMessageKey || "no-message"}`}
      >
        <div className="fluxos-browser-chrome">
          <span />
            <strong>
              {isLiveBackend
                ? agentPreviewWindowOpen
                  ? "Agent preview window"
                : messageSelectionPinned
                  ? `Selected message: ${selectedMessage?.label || selectedMessage?.roleLabel || "Agent"}`
                  : livePreviewLabel
                : "/control?surface=agent"}
            </strong>
          <button onClick={() => fluxioAction(onRequestAction, "preview:refresh")} type="button">
            <RefreshCw size={15} strokeWidth={1.9} />
          </button>
          {activePreviewActionUrl ? (
            <button onClick={() => window.open(activePreviewActionUrl, "_blank", "noopener,noreferrer")} type="button">
              Open new tab
            </button>
          ) : isLiveBackend ? (
            <button disabled title="No live preview URL returned by NAS" type="button">
              Open
            </button>
          ) : null}
        </div>
        <div className="fluxos-live-preview" aria-label="Live preview">
          {isLiveBackend ? (
            messageSelectionPinned ? (
              <article className="fluxos-flow-empty fluxos-selected-message-proof">
                <span>Selected live message</span>
                <strong>{selectedMessage ? agentMessageDisplayTitle(selectedMessage) : "Mission message is refreshing"}</strong>
                {selectedMessageSourceLabel ? <small>{selectedMessageSourceLabel}</small> : null}
                {selectedMessageBody ? (
                  <pre className="fluxos-selected-message-body" data-live-selected-message-body="true">{selectedMessageBody}</pre>
                ) : (
                  <p>This live row has no served preview artifact, or it is refreshing. The panel stays pinned to the selected message instead of reusing an older frame.</p>
                )}
                <div className="fluxos-message-chips">
                  {asList(selectedMessage?.chips).slice(0, 5).map(chip => (
                    <span key={`selected-message-chip-${chip}`}>{chip}</span>
                  ))}
                </div>
                <div className="fluxos-preview-empty-actions">
                  {selectedMessagePreviewActionUrl ? (
                    <button onClick={() => window.open(selectedMessagePreviewActionUrl, "_blank", "noopener,noreferrer")} type="button">Open preview</button>
                  ) : null}
                  <button disabled={!selectedMessage?.id} onClick={() => fluxioAction(onRequestAction, "run:message-comment", { messageId: selectedMessage?.id })} type="button">Comment</button>
                  <button disabled={!selectedMessage?.id} onClick={() => fluxioAction(onRequestAction, "run:message-copy", { messageId: selectedMessage?.id })} type="button">Copy</button>
                </div>
              </article>
            ) : activePreviewFrameUrl ? (
              <>
                <iframe
                  className="fluxos-live-preview-frame"
                  data-agent-preview-frame="true"
                  key={`${workbenchState?.missionId || "mission"}:${activePreviewFrameUrl}`}
                  src={activePreviewFrameUrl}
                  title="Agent live preview"
                />
                <div className="fluxos-preview-empty-actions">
                  <button onClick={() => window.open(activePreviewFrameUrl, "_blank", "noopener,noreferrer")} type="button">Open new tab</button>
                  <button onClick={() => fluxioAction(onRequestAction, "preview:refresh")} type="button">Refresh</button>
                </div>
              </>
            ) : livePreviewFrameBlocked ? (
              <article className="fluxos-flow-empty fluxos-frame-blocked">
                <span>Live URL captured</span>
                <strong>Embedded preview disabled for this target</strong>
                <p>The live preview URL is real, but it is likely protected by browser frame policy. Open it in a new tab instead of showing a broken iframe.</p>
                <div className="fluxos-preview-empty-actions">
                  <button onClick={() => window.open(activePreviewActionUrl, "_blank", "noopener,noreferrer")} type="button">Open new tab</button>
                  <button onClick={() => fluxioAction(onRequestAction, "preview:refresh")} type="button">Refresh</button>
                </div>
              </article>
            ) : (
              <article className="fluxos-flow-empty">
                <span>Live data only</span>
                <strong>No live preview URL captured</strong>
                <p>{workbenchState?.previewSourceDetail || "The Agent preview waits for a served NAS preview URL from the selected mission."}</p>
                <div className="fluxos-preview-empty-actions">
                  <button onClick={() => fluxioAction(onRequestAction, "preview:refresh")} type="button">Refresh</button>
                  <button onClick={() => fluxioAction(onRequestAction, "workbench:screenshot")} type="button">Capture proof</button>
                </div>
              </article>
            )
          ) : (
            <article className="fluxos-flow-empty">
              <span>Agent preview</span>
              <strong>Preview opens here when a real target exists</strong>
              <p>No square fixture blocks are drawn. Agent keeps a clean bordered window for served HTML, localhost apps, or selected proof artifacts.</p>
            </article>
          )}
        </div>
        <div className="fluxos-tool-grid">
          {(visibleTimeline.length ? visibleTimeline : isLiveBackend ? [] : TOOL_EVENTS).map((item, index) => {
            const tuple = Array.isArray(item) ? item : [item.time || item.timestamp || "now", item.title || item.kind, item.detail || item.message, item.tone || "neutral"];
            return (
              <article className={`fluxos-tool-event tone-${tuple[3] || "neutral"}`} key={`${workbenchState?.missionId || "mission"}-${tuple[0]}-${tuple[1]}-${index}`}>
                <span>{tuple[0]}</span>
                <strong>{tuple[1]}</strong>
                <p>{tuple[2]}</p>
              </article>
            );
          })}
          {visibleTimeline.length === 0 && isLiveBackend ? (
            <article className="fluxos-flow-empty">
              <span>Live data only</span>
              <strong>No live tool events loaded</strong>
              <p>The tool grid is waiting for NAS mission timeline events.</p>
            </article>
          ) : null}
        </div>
        <div className="fluxos-runtime-strip">
          <button onClick={() => onRuntimeChange?.("hermes")} type="button">{selectedRuntimeLabel || "Hermes"}</button>
          <button onClick={() => fluxioAction(onRequestAction, "agent:open-terminal")} type="button">Terminal</button>
          <button onClick={() => fluxioAction(onRequestAction, "agent:open-browser")} type="button">Browser</button>
        </div>
      </section>

      <FluxioEvidenceRail
        onRequestAction={onRequestAction}
        routeControls={routeControls}
        runtimeCompartment={runtimeCompartment}
        selectedModelLabel={selectedModelLabel}
      />
    </div>
  );
}

function FluxioBuilderSurface(props) {
  const { builderRows, callBackend, changedItems, liveDataStatus, missionWatchdog, notificationItems, onOpenBuilderDetail, onRequestAction, onSelectFlow, onSelectProject, projectProgressHistory, systemAuditDigest, timelineMoments, workbenchState } = props;
  const [builderClarityMode, setBuilderClarityMode] = useState(() => {
    if (typeof window === "undefined") return "focus";
    return window.localStorage?.getItem("fluxio.builder.clarityMode") || "focus";
  });
  const [builderTimelineHorizon, setBuilderTimelineHorizon] = useState(() => {
    if (typeof window === "undefined") return "phase";
    return window.localStorage?.getItem("fluxio.builder.timelineHorizon") || "phase";
  });
  const [builderTimelineDensity, setBuilderTimelineDensity] = useState(() => {
    if (typeof window === "undefined") return "comfortable";
    return window.localStorage?.getItem("fluxio.builder.timelineDensity") || "comfortable";
  });
  const [builderTimelineShowDone, setBuilderTimelineShowDone] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage?.getItem("fluxio.builder.timelineShowDone") === "true";
  });
  const [builderSelfRepairBusy, setBuilderSelfRepairBusy] = useState(false);
  const [builderSelfRepairProof, setBuilderSelfRepairProof] = useState(null);
  const sourceRows = asList(builderRows);
  const isLiveBackend = liveDataStatus?.previewMode === "live";
  const normalizedBuilderClarityMode = builderClarityMode === "full" ? "full" : "focus";
  const normalizedBuilderTimelineHorizon = ["phase", "month", "quarter", "year"].includes(builderTimelineHorizon)
    ? builderTimelineHorizon
    : "phase";
  const normalizedBuilderTimelineDensity = builderTimelineDensity === "compact" ? "compact" : "comfortable";
  const builderTimelineScaleLabels = {
    phase: ["Now", "Build", "Verify", "Proof"],
    month: ["Week 1", "Week 2", "Week 3", "Week 4"],
    quarter: ["Now", "30d", "60d", "90d"],
    year: ["Q1", "Q2", "Q3", "Q4"],
  }[normalizedBuilderTimelineHorizon];
  const builderFocusMode = isLiveBackend && normalizedBuilderClarityMode === "focus";
  const setLiveBuilderClarityMode = mode => {
    const nextMode = mode === "full" ? "full" : "focus";
    setBuilderClarityMode(nextMode);
    if (typeof window !== "undefined") {
      window.localStorage?.setItem("fluxio.builder.clarityMode", nextMode);
    }
  };
  const setLiveBuilderTimelineHorizon = horizon => {
    const nextHorizon = ["phase", "month", "quarter", "year"].includes(horizon) ? horizon : "phase";
    setBuilderTimelineHorizon(nextHorizon);
    if (typeof window !== "undefined") {
      window.localStorage?.setItem("fluxio.builder.timelineHorizon", nextHorizon);
    }
  };
  const setLiveBuilderTimelineDensity = density => {
    const nextDensity = density === "compact" ? "compact" : "comfortable";
    setBuilderTimelineDensity(nextDensity);
    if (typeof window !== "undefined") {
      window.localStorage?.setItem("fluxio.builder.timelineDensity", nextDensity);
    }
  };
  const toggleLiveBuilderTimelineDone = () => {
    const nextValue = !builderTimelineShowDone;
    setBuilderTimelineShowDone(nextValue);
    if (typeof window !== "undefined") {
      window.localStorage?.setItem("fluxio.builder.timelineShowDone", nextValue ? "true" : "false");
    }
  };
  const runBuilderSelfRepairLoop = async () => {
    if (builderSelfRepairBusy) return;
    setBuilderSelfRepairBusy(true);
    try {
      const result = await callBackend?.("ui_self_repair_loop_command", {
        requestId: `mission8-broader-ui-${Date.now()}`,
        surface: "core-surfaces",
        surfaces: ["builder", "agent", "runtime", "skills", "images", "preview"],
        clarityMode: normalizedBuilderClarityMode,
        previewMode: liveDataStatus?.previewMode || "fixture",
        missionCount: liveDataStatus?.missionCount || builderRows?.length || 0,
        selectedMissionId: workbenchState?.missionId || "",
        selectedMissionTitle: workbenchState?.missionTitle || "",
        screenshotPath: "artifacts/mission8-broader-ui-self-repair/before-builder-surface.png",
        domFacts: {
          firstViewport: "Builder current mission canvas plus core navigation surfaces",
          visibleProblem: "mission-specific proof widgets can outlive their mission labels and compete with the current repair objective",
          intendedRepair: "broader UI repair receipt with audited surfaces, selected cleanup, route, proof, and next action",
        },
      });
      const proof = result && typeof result === "object" ? result : {};
      setBuilderSelfRepairProof({
        status: proof.missionGate?.status || proof.status || proof.routeStatus || "recorded",
        message: proof.message || "UI self-repair proof artifacts were written.",
        artifacts: proof.artifacts || {},
        missionGate: proof.missionGate || {},
        selectedRepair: proof.plan?.selectedRepair || "",
        auditedSurfaces: asList(proof.surfaceAudit?.targetSurfaces),
        skillsUsed: asList(proof.skillsUsed).map(item => item.id || item.skill || item).filter(Boolean),
      });
      onRequestAction?.("builder:self-repair-proof", {
        surface: "core-surfaces",
        artifacts: proof.artifacts || {},
        missionGate: proof.missionGate || {},
        route: proof.route || {},
      });
    } catch (error) {
      setBuilderSelfRepairProof({
        status: "failed",
        message: error?.message || "UI self-repair proof command failed.",
        artifacts: {},
        skillsUsed: [],
      });
    } finally {
      setBuilderSelfRepairBusy(false);
    }
  };
  const liveRows = sortLiveBuilderRows(sourceRows);
  const liveLoading = isLiveBackend && liveDataStatus?.loading && sourceRows.length === 0;
  const rows = sourceRows.length ? liveRows.slice(0, isLiveBackend ? 8 : 4) : liveLoading || isLiveBackend ? [] : BUILDER_FLOWS;
  const metricRows = sourceRows.length ? sourceRows : rows;
  const activeRows = metricRows.filter(row => isActiveBuilderRow(row));
  const reviewRows = metricRows.filter(row => isBlockedBuilderRow(row));
  const selectedProgressValue = clampPercent(workbenchState?.progress?.value);
  const liveAdvancementRows = isLiveBackend
    ? activeRows.slice(0, 6).map(row => {
        const missionId = String(row?.id || row?.missionId || row?.mission_id || "").trim();
        const isSelectedMission = Boolean(
          missionId &&
          missionId === String(workbenchState?.missionId || "").trim(),
        );
        if (!isSelectedMission || selectedProgressValue == null) {
          return row;
        }
        return {
          ...row,
          progress: `${selectedProgressValue}%`,
          progressLabel: workbenchState?.progress?.label || row?.progressLabel || row?.status || "",
          progressDetail: workbenchState?.progress?.source || row?.progressDetail || "",
          progressNextAction: workbenchState?.progress?.nextAction || row?.progressNextAction || "",
        };
      })
    : [];
  const liveMissionCount = Number(liveDataStatus?.missionCount ?? metricRows.length);
  const liveActiveCount = Number(liveDataStatus?.activeMissionCount ?? activeRows.length);
  const liveQueuedCount = Number(liveDataStatus?.queuedMissionCount ?? 0);
  const liveBlockedCount = Number(liveDataStatus?.blockedMissionCount ?? reviewRows.length);
  const liveCompletedCount = Number(liveDataStatus?.completedMissionCount ?? 0);
  const liveRunningCount = Number(liveDataStatus?.runningMissionCount ?? 0);
  const liveChangedItems = asList(changedItems).filter(isRealChangedItem).map(changedItemTuple);
  const changes = liveChangedItems.length ? liveChangedItems.slice(0, 5) : isLiveBackend ? [] : CHANGED_FILES;
  const publicLaunchReadiness = systemAuditDigest?.publicLaunchReadiness || {};
  const publicLaunchRepairPacket = publicLaunchReadiness?.repairPacket || {};
  const publicLaunchSteps = publicLaunchProofSteps(publicLaunchReadiness);
  const proofDiffRows = asList(workbenchState?.proofDiff?.rows);
  const [proofDiffWrap, setProofDiffWrap] = useState(true);
  const [proofDiffVisibleCount, setProofDiffVisibleCount] = useState(12);
  const visibleProofDiffRows = proofDiffRows.slice(0, proofDiffVisibleCount);
  const missionContextRoots = rows
    .flatMap(row => asList(row?.contextRoots?.roots).map(root => ({ ...root, missionName: row?.name || row?.title || "Mission" })))
    .slice(0, 6);
  const selectedContext = rows.find(row => row?.selected)?.contextRoots || rows[0]?.contextRoots || {};
  const selectedMissionRow = rows.find(row => row?.selected) || rows[0] || {};
  const selectedMissionId = selectedMissionRow?.id || selectedMissionRow?.missionId || selectedMissionRow?.mission_id || "";
  const builderActionMissionId = selectedMissionId || String(workbenchState?.missionId || "").trim();
  const selectedProviderCapabilities = selectedMissionRow?.providerCapabilities || selectedMissionRow?.provider_capabilities || {};
  const providerCapabilityRows = asList(selectedProviderCapabilities?.providers);
  const providerLaneRows = asList(selectedProviderCapabilities?.lanes);
  const selectedRouteDecisionRows = providerLaneRows.length
    ? providerLaneRows.slice(0, 4)
    : isLiveBackend
      ? []
      : [
        { role: "planner", provider: "openai-codex", model: "gpt-5.5", effort: "high", reason: "Plan and route the mission." },
        { role: "executor", provider: selectedProviderCapabilities.runtimeId || selectedMissionRow.runtimeId || "hermes", model: "task-fit", effort: "high", reason: "Execute through the selected runtime lane." },
        { role: "verifier", provider: "openai-codex", model: "gpt-5.5", effort: "high", reason: "Verify diffs, browser proof, and receipts." },
      ];
  const selectedThreadRows = (
    isLiveBackend
      ? asList(workbenchState?.agentThreadPreview)
      : asList(workbenchState?.agentThreadPreview).length > 0
        ? asList(workbenchState?.agentThreadPreview)
        : asList(workbenchState?.runtimeOps)
  )
    .filter(item => !isLowSignalAgentMessage(item))
    .slice(0, 3);
  const liveNotificationRows = isLiveBackend ? asList(notificationItems).slice(0, 4) : [];
  const latestNotification = liveNotificationRows[0] || null;
  const firstWatchdogProblem =
    asList(missionWatchdog?.problemRegistry?.problems).find(item => !["closed", "resolved", "dismissed"].includes(String(item?.status || "open").toLowerCase())) ||
    asList(missionWatchdog?.issues)[0] ||
    null;
  const antiDriftGuard = useMemo(
    () => deriveMissionAntiDriftGuard(missionWatchdog, { isLiveBackend }),
    [isLiveBackend, missionWatchdog],
  );
  const firstLiveThreadLine =
    selectedThreadRows.map(item => firstUsefulRuntimeLine(agentMessageDisplayDetail(item))).find(Boolean) ||
    selectedThreadRows.map(item => item.title || item.label || "").find(Boolean) ||
    "";
  const selectedMissionProgressValue =
    selectedProgressValue ??
    progressPercentValue(selectedMissionRow?.progress);
  const liveControlRailRows = isLiveBackend ? [
    {
      id: "mission",
      label: "Mission",
      value: selectedMissionProgressValue == null ? titleizeToken(selectedMissionRow?.status || "Live") : `${selectedMissionProgressValue}%`,
      detail: selectedMissionRow?.name || selectedMissionRow?.title || "No selected mission row",
      tone: liveBlockedCount > 0 ? "warn" : liveActiveCount > 0 ? "good" : "neutral",
      action: "Open Agent",
      disabled: !selectedMissionId,
      onClick: () => onOpenBuilderDetail?.(selectedMissionId),
    },
    {
      id: "agent",
      label: "Agent report",
      value: selectedThreadRows.length ? `${selectedThreadRows.length} live` : "Waiting",
      detail: firstLiveThreadLine || "No runtime report row returned for this mission yet.",
      tone: selectedThreadRows.length ? "good" : "warn",
      action: "Read thread",
      disabled: !selectedMissionId,
      onClick: () => onOpenBuilderDetail?.(selectedMissionId),
    },
    {
      id: "notify",
      label: "Notifications",
      value: `${liveNotificationRows.length} visible`,
      detail: latestNotification
        ? (latestNotification.agentMessage || latestNotification.detail || latestNotification.message || latestNotification.title || "Live notification")
        : "No live notification rows returned on this refresh.",
      tone: liveNotificationRows.length ? "good" : "warn",
      action: "Open stack",
      disabled: false,
      onClick: () => onRequestAction?.("notifications:show-live-stack"),
    },
    {
      id: "watchdog",
      label: "Watchdog",
      value: missionWatchdog ? `${missionWatchdog.issueCount || 0} issues` : "Pending",
      detail:
        firstWatchdogProblem?.firstRepairStep ||
        firstWatchdogProblem?.firstStep ||
        firstWatchdogProblem?.detail ||
        missionWatchdog?.nextAction ||
        "No live watchdog report returned yet.",
      tone: Number(missionWatchdog?.bad || 0) > 0 ? "bad" : Number(missionWatchdog?.warn || 0) > 0 ? "warn" : missionWatchdog ? "good" : "neutral",
      action: "Refresh",
      disabled: false,
      onClick: () => onRequestAction?.("watchdog:refresh"),
    },
  ] : [];
  const projectHealthRows = rows.map((row, index) => ({
    id: row?.id || `project-health-${index}`,
    title: row?.workspaceName || row?.description || row?.name || "Workspace",
    detail: row?.workspacePath || row?.lastRunMeta || (isLiveBackend ? "Workspace path missing in live NAS summary." : "No workspace path recorded."),
    activeCount: row?.status === "Completed" ? 0 : 1,
    blockedCount: Number(row?.blockedCount || 0),
    laneCount: Number(row?.delegatedLaneCount || 0),
    tone: Number(row?.blockedCount || 0) > 0 ? "warn" : row?.statusTone || "neutral",
  }));
  const projectRowsByWorkspaceId = new Map(
    asList(projectProgressHistory?.projects).map(item => [item.workspaceId, item]),
  );
  const schedulingQueueRows = asList(projectProgressHistory?.schedulingQueue).map((item, index) => {
    const project = projectRowsByWorkspaceId.get(item.workspaceId) || {};
    const counts = project.counts || {};
    const relatedHoldCount =
      asList(item.sameRootActiveWorkspaces).length +
      asList(item.dependencyActiveWorkspaces).length +
      asList(item.sameRootBlockedWorkspaces).length +
      asList(item.dependencyBlockedWorkspaces).length;
    return {
      ...item,
      rank: index + 1,
      title: item.workspaceName || project.workspaceName || item.workspaceId || "Workspace",
      activeCount: Number(counts.active || 0),
      queuedCount: Number(counts.queued || 0),
      blockedCount: Number(counts.blocked || 0),
      completedCount: Number(counts.completed || 0),
      relatedHoldCount,
    };
  });
  const builderQueuePressureRows = useMemo(() => {
    if (!missionWatchdog) return [];
    const seen = new Set();
    const rows = [];
    const pushQueuePressure = (sourceItem, sourceIndex) => {
      const item = asRecord(sourceItem);
      if (String(item.kind || "") !== "workspace_queue_pressure") return;
      const evidence = asList(item.evidence).map(value => String(value || ""));
      const evidenceValue = key => {
        const prefix = `${key}=`;
        const match = evidence.find(value => value.startsWith(prefix));
        return match ? match.slice(prefix.length) : "";
      };
      const scopeEvidence = asRecord(item.scopeEvidence);
      const missionId = item.missionId || item.mission_id || "";
      const blockingMissionId = item.blockingMissionId || evidenceValue("blockingMissionId");
      const key =
        item.problemId ||
        item.issueId ||
        `${missionId || "mission"}-${blockingMissionId || "slot"}-${sourceIndex}`;
      if (seen.has(key)) return;
      seen.add(key);
      const scopeSafety = item.scopeSafety || evidenceValue("scopeSafety") || "unknown";
      rows.push({
        key,
        missionId,
        blockingMissionId,
        missionTitle: item.missionTitle || item.title || "Queued mission",
        title: item.title || "Queued mission is waiting behind a long-running workspace slot",
        detail: item.detail || "The watchdog is holding this mission because another mission owns the active workspace slot.",
        firstRepairStep:
          item.firstRepairStep ||
          item.firstStep ||
          "Keep it queued or split the objective into a non-overlapping lane.",
        severity: item.severity || "info",
        scopeSafety,
        activeFileCount: Number(scopeEvidence.activeFileCount || evidenceValue("activeScopeFiles") || 0),
        queuedFileCount: Number(scopeEvidence.queuedFileCount || evidenceValue("queuedScopeFiles") || 0),
        overlapFiles: asList(scopeEvidence.overlapFiles).slice(0, 3),
        canParallelize: scopeSafety === "safe",
      });
    };
    asList(missionWatchdog.issues).forEach(pushQueuePressure);
    asList(missionWatchdog.problemRegistry?.problems).forEach(pushQueuePressure);
    return rows;
  }, [missionWatchdog]);
  const liveGuideRows = isLiveBackend ? [
    {
      id: "mission",
      label: "Mission",
      value: liveMissionCount ? `${liveMissionCount} live · ${liveActiveCount} active` : "No live rows",
      detail: liveMissionCount
        ? `${liveRunningCount} running · ${liveQueuedCount} queued · ${liveBlockedCount} blocked`
        : "The NAS summary returned no mission rows; the UI does not show fixture missions.",
    },
    {
      id: "thread",
      label: "Agent thread",
      value: selectedThreadRows.length ? `${selectedThreadRows.length} current rows` : "No selected rows",
      detail: selectedThreadRows.length
        ? "Open Agent to inspect the selected mission transcript, runtime trace, and proof body."
        : "The selected mission has not returned detail messages yet.",
    },
    {
      id: "queue",
      label: "Queue",
      value: schedulingQueueRows.length ? `${schedulingQueueRows.length} ranked projects` : "No scheduler rows",
      detail: projectProgressHistory?.scheduler?.nextAction || "The live scheduler has not emitted a next action.",
    },
    {
      id: "notify",
      label: "Notifications",
      value: `${Number(liveDataStatus?.notificationCount || 0)} visible · ${Number(liveDataStatus?.sliceNotificationCount || 0)} slice alerts`,
      detail: "Browser notifications use the first line of the live mission update and can be dismissed from the stack.",
    },
  ] : [];
  const missionAdvancementRows = isLiveBackend
    ? liveRows.slice(0, 5).map((row, index) => {
        const rowProgressValue = progressPercentValue(row?.progress);
        const status = row?.status || row?.statusLabel || "live";
        const missionId = row?.id || row?.missionId || row?.mission_id || "";
        const isSelectedMission = Boolean(
          missionId &&
          missionId === String(workbenchState?.missionId || "").trim(),
        );
        const progressValue =
          rowProgressValue == null && isSelectedMission
            ? selectedProgressValue
            : rowProgressValue;
        const laneCount = Number(row?.delegatedLaneCount || row?.runs || 0);
        const blockerCount = Number(row?.blockedCount || 0);
        return {
          id: missionId || `mission-advancement-${index}`,
          title: row?.name || row?.title || missionId || "Live mission",
          status,
          tone: blockerCount > 0 ? "warn" : isActiveBuilderRow(row) ? "good" : "neutral",
          progress: progressValue,
          progressKind: row?.progressKind || (row?.displayAsCompletion === false ? "non_completion_progress" : ""),
          progressLabel: row?.progressLabel || (row?.displayAsCompletion === false ? "Proof repair readiness" : ""),
          detail:
            (isSelectedMission ? workbenchState?.progress?.nextAction : "") ||
            row?.progressNextAction ||
            row?.turningPoint ||
            (isSelectedMission ? workbenchState?.progress?.source : "") ||
            row?.progressDetail ||
            row?.lastRunMeta ||
            "Waiting for the next live runtime update.",
          meta: [
            row?.runtimeId || row?.runtime || "",
            laneCount ? `${laneCount} lane${laneCount === 1 ? "" : "s"}` : "",
            row?.updated || "",
          ].filter(Boolean).join(" · "),
        };
      })
    : [];
  const systemAdvancementRows = isLiveBackend ? [
    systemAuditDigest?.redTeamEscalation?.historyRows ? {
      id: "red-team",
      label: "Red-team pressure",
      value: `${systemAuditDigest.redTeamEscalation.latestResistanceScore || 0} resistance`,
      detail: `${systemAuditDigest.redTeamEscalation.historyRows} rows · next ${systemAuditDigest.redTeamEscalation.nextAttemptBudget || 0} attempts · pressure ${systemAuditDigest.redTeamEscalation.currentPressureIndex || 0} -> ${systemAuditDigest.redTeamEscalation.nextPressureIndex || 0}`,
    } : null,
    systemAuditDigest?.watchdogSelfImprovement?.schema ? {
      id: "watchdog",
      label: "Watchdog learning",
      value: `${systemAuditDigest.watchdogSelfImprovement.historyRows || 0} receipts`,
      detail: systemAuditDigest.watchdogSelfImprovement.trendReady
        ? `${systemAuditDigest.watchdogSelfImprovement.completedReceipts || 0} completed · next ${systemAuditDigest.watchdogSelfImprovement.nextAttemptBudget || 0} attempts`
        : systemAuditDigest.watchdogSelfImprovement.nextAction,
    } : null,
    systemAuditDigest?.mustBeatStatus ? {
      id: "t3",
      label: "T3 comparison",
      value: `${Number(systemAuditDigest?.mustBeatStatus?.ahead || 0)}/${Number(systemAuditDigest?.mustBeatStatus?.total || 7)} ahead`,
      detail: Number(systemAuditDigest?.mustBeatStatus?.deficitCount || 0)
        ? `${Number(systemAuditDigest?.mustBeatStatus?.deficitCount || 0)} deficit${Number(systemAuditDigest?.mustBeatStatus?.deficitCount || 0) === 1 ? "" : "s"} still block the must-beat target.`
        : systemAuditDigest?.t3Reference?.latestObservedRelease || "All tracked categories are ahead.",
    } : null,
    publicLaunchReadiness?.status ? {
      id: "public-launch",
      label: "Public launch",
      value: titleizeToken(publicLaunchReadiness.status),
      detail: publicLaunchReadiness.nextAction || "Attach current public-web and publication proof.",
    } : null,
  ].filter(Boolean) : [];
  const t3DeficitRows = asList(systemAuditDigest?.deficits);
  const t3ImprovementRows = asList(systemAuditDigest?.improvementQueue);
  const t3RepairRows = (t3DeficitRows.length > 0 ? t3DeficitRows : t3ImprovementRows)
    .slice(0, 4)
    .map((item, index) => ({
      id: item.id || item.category || item.title || `t3-repair-${index}`,
      category: item.category || item.title || "System repair",
      detail: item.blockingGap || item.detail || systemAuditDigest?.scoreCapReason || "Fluxio is not ahead in this category yet.",
      nextAction: item.nextAction || item.nextMove || item.repairAction || "Open the repair lane and attach proof.",
      delta: Number(item.delta ?? (Number(item.fluxioScore || 0) - Number(item.t3Score || 0))),
      fluxioScore: item.fluxioScore,
      t3Score: item.t3Score,
      lane: item.lane || "T3 parity",
      priority: item.priority || index + 1,
      raw: item,
    }));
  const t3AheadCount = Number(systemAuditDigest?.mustBeatStatus?.ahead || 0);
  const t3TotalCount = Number(systemAuditDigest?.mustBeatStatus?.total || 0);
  const t3DeficitCount = Number(systemAuditDigest?.mustBeatStatus?.deficitCount || t3DeficitRows.length || 0);
  const systemLossBreakdown = systemAuditDigest?.systemLossBreakdown || {};
  const systemLossHasOutOf20 = Number.isFinite(Number(systemLossBreakdown.averageScoreOutOf20));
  const systemLossScore = Number(systemLossBreakdown.averageScoreOutOf20 || 0).toFixed(1).replace(/\.0$/, "");
  const systemLossAmount = Number(systemLossBreakdown.averageLossOutOf20 || 0).toFixed(1).replace(/\.0$/, "");
  const systemLossAhead = Number(systemLossBreakdown.mustBeatStatus?.ahead ?? t3AheadCount);
  const systemLossTotal = Number(systemLossBreakdown.mustBeatStatus?.total ?? (t3TotalCount || 7));
  const systemLossHeadline = systemLossHasOutOf20
    ? `${systemLossScore}/20 · gap ${systemLossAmount}/20`
    : `gap pressure ${Number(systemLossBreakdown.score || 0)}/100 · ${titleizeToken(systemLossBreakdown.severity || "low")}`;
  const systemLossSubline = systemLossHasOutOf20
    ? `${systemLossAhead}/${systemLossTotal} T3 categories ahead`
    : systemLossBreakdown.nextAction || "Keep sampling live outcomes.";
  const systemLossDriverRows = asList(systemLossBreakdown.drivers).slice(0, 4).map((item, index) => ({
    id: item.id || item.category || item.title || `system-loss-${index}`,
    lane: item.lane || item.category || "System",
    loss: item.lossOutOf20 ?? item.loss ?? 0,
    title: item.category || item.title || "Loss driver",
    detail: item.primaryGap || item.detail || item.evidence || item.nextAction || "Keep collecting live proof.",
    nextAction: item.nextAction || "",
  }));
  const designDebtSummary = systemAuditDigest?.designDebtSummary || {};
  const designDebtRows = asList(designDebtSummary.rows);
  const goalCompletionAudit = systemAuditDigest?.goalCompletionAudit || {};
  const goalCompletionRows = asList(goalCompletionAudit.rows);
  const missionAdvancementSummary = systemAuditDigest?.missionAdvancementSummary || {};
  const missionProofAdvancementRows = asList(missionAdvancementSummary.rows);
  const operatorNextPath = systemAuditDigest?.operatorNextPath || {};
  const operatorNextPathSteps = asList(operatorNextPath.steps);
  const speedSupervisorSummary = systemAuditDigest?.speedSupervisorSummary || {};
  const speedSupervisorRows = asList(speedSupervisorSummary.rows);
  const topQueueRow = schedulingQueueRows[0] || null;
  const queueFirstHeldCount = schedulingQueueRows.filter(item => item.safeToLaunch === false).length;
  const queueFirstNotificationCount = Number(liveDataStatus?.notificationCount || 0);
  const queueFirstSliceCount = Number(liveDataStatus?.sliceNotificationCount || 0);
  const liveControlState = liveDataStatus?.liveControlState || {};
  const runtimeRouteProof = liveDataStatus?.runtimeRouteProof || {};
  const runtimeProofReceipt = runtimeRouteProof?.proof || {};
  const runtimeProofVerified = Boolean(runtimeRouteProof?.minimaxM3Verified);
  const runtimeFrontendProvider =
    runtimeProofReceipt.provider || runtimeRouteProof.frontendExecutorProvider || "minimax";
  const runtimeFrontendModel =
    runtimeProofReceipt.model || runtimeRouteProof.frontendExecutorModel || "MiniMax-M3";
  const runtimeProofRows = [
    {
      label: "Hermes binary",
      value: runtimeRouteProof?.hermesCommandVisible ? "Visible" : "Missing",
      detail: runtimeRouteProof?.hermesVersion || runtimeRouteProof?.hermesCommand || "No live Hermes command on backend PATH.",
      tone: runtimeRouteProof?.hermesCommandVisible ? "good" : "bad",
    },
    {
      label: "Frontend executor",
      value: runtimeProofVerified ? `${runtimeFrontendProvider} / ${runtimeFrontendModel} verified` : "Proof pending",
      detail: runtimeProofVerified
        ? `${runtimeFrontendProvider} / ${runtimeFrontendModel} · ${runtimeProofReceipt.elapsedMs || 0}ms`
        : "Run a Hermes MiniMax-M3 chat once; Builder will show the resulting backend receipt.",
      tone: runtimeProofVerified ? "good" : "warn",
    },
    {
      label: "Proof source",
      value: runtimeProofReceipt?.checkedAt ? "Recorded" : "Not recorded",
      detail: runtimeProofReceipt?.checkedAt || runtimeRouteProof?.source || "No authenticated runtime receipt yet.",
      tone: runtimeProofReceipt?.checkedAt ? "good" : "warn",
    },
  ];
  const zeroActiveQueueHealthy = Boolean(
    liveControlState.zeroActiveQueueHealthy ||
      (schedulingQueueRows.length > 0 && liveActiveCount === 0 && liveQueuedCount === 0 && liveBlockedCount === 0),
  );
  const liveControlStateLabel = zeroActiveQueueHealthy
    ? "Healthy zero-active state"
    : liveActiveCount > 0
      ? "Active mission state"
      : "Ready for launch";
  const liveControlStateDetail = zeroActiveQueueHealthy
    ? (liveControlState.detail || "No mission is running; the NAS scheduler queue remains visible and actionable.")
    : (liveControlState.detail || workbenchState?.progress?.nextAction || "Builder is reading current NAS summary data.");
  const selectedTimelineTitle =
    selectedMissionRow?.name || selectedMissionRow?.title || "";
  const builderTimelineHeadline = liveActiveCount > 0 && selectedTimelineTitle
    ? `Running: ${selectedTimelineTitle}`
    : selectedTimelineTitle || (topQueueRow ? `Next: #${topQueueRow.rank} ${topQueueRow.title}` : "Ready for the next mission");
  const builderTimelineContext = topQueueRow
    ? `Next queued: #${topQueueRow.rank} ${topQueueRow.title} · ${topQueueRow.safeToLaunch ? "safe to launch" : "held"}`
    : liveControlStateDetail;
  const completedBuilderTimelineRows = builderTimelineShowDone
    ? metricRows
        .filter(item => {
          const status = String(item?.status || item?.state || "").trim().toLowerCase();
          return ["completed", "done"].includes(status);
        })
        .slice(0, 2)
        .map((item, index) => ({
          id: `completed-${item.id || item.missionId || item.mission_id || index}`,
          selected: false,
          lane: "Done",
          title: item.name || item.title || "Completed mission",
          detail: item.summary || item.turningPoint || "Completed mission remains visible because completed rows are enabled.",
          progress: 100,
          start: Math.min(82, 54 + index * 12),
          span: 30,
          tone: "good",
          meta: "Done",
          phaseLabel: "Done",
          checkpointLabel: "proof archived",
          dependencyLabel: "complete",
          actionLabel: "Open",
          onClick: () => onOpenBuilderDetail?.(item.id || item.missionId || item.mission_id),
        }))
    : [];
  const builderTimelineRows = [
    selectedMissionId ? {
      id: `mission-${selectedMissionId}`,
      selected: true,
      lane: liveActiveCount > 0 ? "Running" : "Selected",
      title: selectedMissionRow?.name || selectedMissionRow?.title || "Selected live mission",
      detail: workbenchState?.progress?.nextAction || selectedMissionRow?.turningPoint || selectedMissionRow?.summary || "Open Agent for the current thread and proof.",
      progress: selectedMissionProgressValue == null ? 38 : selectedMissionProgressValue,
      start: 2,
      span: Math.max(22, Math.min(88, selectedMissionProgressValue == null ? 42 : selectedMissionProgressValue)),
      tone: liveBlockedCount > 0 ? "warn" : liveActiveCount > 0 ? "good" : "neutral",
      meta: selectedThreadRows.length ? `${selectedThreadRows.length} rows` : titleizeToken(selectedMissionRow?.status || "live"),
      phaseLabel: liveActiveCount > 0 ? "Now" : "Selected",
      checkpointLabel: selectedMissionProgressValue == null ? "progress pending" : `${selectedMissionProgressValue}% state`,
      dependencyLabel: selectedThreadRows.length ? "thread proof ready" : "open Agent proof",
      actionLabel: "Agent",
      onClick: () => onOpenBuilderDetail?.(selectedMissionId),
    } : null,
    ...schedulingQueueRows.slice(0, 4).map((item, index) => ({
      id: `queue-${item.workspaceId || item.rank || index}`,
      selected: false,
      lane: `Queue ${item.rank || index + 1}`,
      title: item.title || "Queued project",
      detail: item.recommendedAction || item.reason || projectProgressHistory?.scheduler?.nextAction || "Review before launch.",
      progress: item.safeToLaunch ? 18 : 8,
      start: Math.min(72, 16 + index * 14),
      span: item.safeToLaunch ? 24 : 18,
      tone: item.safeToLaunch ? "good" : "warn",
      meta: item.safeToLaunch ? "Safe" : item.activeCount ? `${item.activeCount} active` : item.blockedCount ? `${item.blockedCount} blocked` : "Held",
      phaseLabel: index === 0 ? "Next" : "Queued",
      checkpointLabel: item.safeToLaunch ? "ready window" : "dependency hold",
      dependencyLabel: item.safeToLaunch ? "scope safe" : "wait for active mission",
      actionLabel: item.safeToLaunch ? "Launch" : "Open",
      onClick: () => item.workspaceId && onSelectProject?.(item.workspaceId),
    })),
    ...reviewRows.slice(0, 2).map((item, index) => ({
      id: `blocked-${item.id || item.missionId || index}`,
      selected: false,
      lane: "Blocked",
      title: item.name || item.title || "Blocked mission",
      detail: item.turningPoint || item.nextAction || item.summary || "Inspect proof before continuing.",
      progress: progressPercentValue(item.progress) ?? 12,
      start: 10 + index * 18,
      span: 28,
      tone: "bad",
      meta: titleizeToken(item.status || "blocked"),
      phaseLabel: "Blocked",
      checkpointLabel: titleizeToken(item.status || "needs repair"),
      dependencyLabel: "proof required",
      actionLabel: "Inspect",
      onClick: () => onOpenBuilderDetail?.(item.id || item.missionId || item.mission_id),
    })),
    ...completedBuilderTimelineRows,
  ].filter(Boolean).slice(0, builderTimelineShowDone ? 8 : 6);
  const builderTimelineProofRows = [
    {
      label: "Agent thread",
      value: selectedThreadRows.length ? `${selectedThreadRows.length} live` : "Waiting",
      detail: firstLiveThreadLine || "Open Agent for the selected mission transcript.",
      tone: selectedThreadRows.length ? "good" : "warn",
    },
    {
      label: "Verifier",
      value: proofDiffRows.length ? `${proofDiffRows.length} rows` : titleizeToken(goalCompletionAudit?.status || "proof"),
      detail: goalCompletionAudit?.nextAction || workbenchState?.progress?.nextAction || "Run proof from Agent when the diff is ready.",
      tone: proofDiffRows.length || goalCompletionAudit?.schema ? "good" : "neutral",
    },
    {
      label: "Queue",
      value: schedulingQueueRows.length ? `${schedulingQueueRows.length} ranked` : "Empty",
      detail: topQueueRow?.recommendedAction || topQueueRow?.reason || projectProgressHistory?.scheduler?.nextAction || "No scheduler action is pending.",
      tone: topQueueRow?.safeToLaunch ? "good" : topQueueRow ? "warn" : "neutral",
    },
  ];
  const builderOperatorDockRows = [
    {
      id: "mission-state",
      label: "State",
      value: selectedMissionProgressValue == null ? titleizeToken(selectedMissionRow?.status || "Live") : `${selectedMissionProgressValue}%`,
      detail: workbenchState?.progress?.label || workbenchState?.progress?.nextAction || titleizeToken(selectedMissionRow?.status || "Live mission"),
      tone: liveBlockedCount > 0 ? "warn" : liveActiveCount > 0 ? "good" : "neutral",
    },
    {
      id: "thread",
      label: "Thread",
      value: selectedThreadRows.length ? `${selectedThreadRows.length} live` : "Open Agent",
      detail: firstLiveThreadLine || "Mission transcript and latest runtime messages.",
      action: "Agent",
      disabled: !selectedMissionId,
      onClick: () => onOpenBuilderDetail?.(selectedMissionId),
      tone: selectedThreadRows.length ? "good" : "warn",
    },
    {
      id: "proof",
      label: "Proof",
      value: runtimeProofVerified ? `${runtimeFrontendProvider} / ${runtimeFrontendModel}` : "Pending",
      detail: runtimeProofVerified ? "Hermes backend route verified." : "Run proof from Agent when the route is ready.",
      action: "Verify",
      onClick: () => onRequestAction?.("run:proof"),
      tone: runtimeProofVerified ? "good" : "warn",
    },
    {
      id: "queue",
      label: "Queue",
      value: schedulingQueueRows.length ? `${schedulingQueueRows.length} ranked` : "Clear",
      detail: topQueueRow?.title || projectProgressHistory?.scheduler?.nextAction || "No queued project is blocking launch.",
      action: "Queue",
      disabled: !topQueueRow?.workspaceId,
      onClick: () => onSelectProject?.(topQueueRow?.workspaceId),
      tone: topQueueRow?.safeToLaunch ? "good" : topQueueRow ? "warn" : "neutral",
    },
  ];
  const builderPrimaryRow = selectedMissionRow && Object.keys(selectedMissionRow).length
    ? selectedMissionRow
    : rows[0] || {};
  const builderPrimaryMissionId =
    builderActionMissionId ||
    builderPrimaryRow?.id ||
    builderPrimaryRow?.missionId ||
    builderPrimaryRow?.mission_id ||
    "";
  const builderPrimaryStatus = titleizeToken(
    builderPrimaryRow?.status ||
      builderPrimaryRow?.statusLabel ||
      (isLiveBackend ? liveControlStateLabel : "Preview mission"),
  );
  const builderSelectedProgressForCanvas =
    !isLiveBackend && selectedMissionProgressValue === 0 ? null : selectedMissionProgressValue;
  const builderRowProgressValue = progressPercentValue(builderPrimaryRow?.progress);
  const builderRowProgressForCanvas =
    !isLiveBackend && builderRowProgressValue === 0 ? null : builderRowProgressValue;
  const builderPrimaryProgress =
    builderSelectedProgressForCanvas ??
    builderRowProgressForCanvas ??
    (isLiveBackend ? null : 34);
  const builderProgressLabelRaw =
    workbenchState?.progress?.label ||
    builderPrimaryRow?.progressLabel ||
    "";
  const builderPrimaryProgressLabel =
    !isLiveBackend && /live progress metric unavailable/i.test(String(builderProgressLabelRaw))
      ? "Fixture readiness proof"
      : builderProgressLabelRaw || "Mission readiness";
  const builderPrimaryTitle =
    (isLiveBackend ? workbenchState?.missionTitle : "") ||
    builderPrimaryRow?.name ||
    builderPrimaryRow?.title ||
    topQueueRow?.title ||
    "Choose the next Builder mission";
  const builderPrimaryDetail =
    workbenchState?.progress?.nextAction ||
    builderPrimaryRow?.turningPoint ||
    builderPrimaryRow?.description ||
    builderPrimaryRow?.detail ||
    builderPrimaryRow?.summary ||
    topQueueRow?.recommendedAction ||
    "Pick one mission, continue it, verify proof, or launch the next safe queued task.";
  const builderProofCompactRows = [
    {
      label: "Route",
      value: "Hermes",
      detail: "Primary runtime; OpenClaw stays fallback proof.",
      tone: "good",
    },
    {
      label: "Thread",
      value: selectedThreadRows.length ? `${selectedThreadRows.length} rows` : isLiveBackend ? "Waiting" : "Fixture",
      detail: firstLiveThreadLine || "Open Agent for transcript and verifier output.",
      tone: selectedThreadRows.length || !isLiveBackend ? "good" : "warn",
    },
    {
      label: "Proof",
      value: builderSelfRepairProof ? titleizeToken(builderSelfRepairProof.status) : proofDiffRows.length ? `${proofDiffRows.length} rows` : "Folded",
      detail: builderSelfRepairProof?.selectedRepair || builderSelfRepairProof?.message || "Use self-repair to write route, breakdown, plan, and verifier artifacts.",
      tone: builderSelfRepairProof?.status === "failed" ? "bad" : builderSelfRepairProof ? "good" : "neutral",
    },
  ];
  const storageTriageSummary = systemAuditDigest?.storageTriageSummary || {};
  const nasStoragePressure = systemAuditDigest?.nasStoragePressure || {};
  const nasStorageAvailableBytes = Number(nasStoragePressure.availableBytes || 0);
  const nasStorageUsedPercent = Number(nasStoragePressure.usedPercent || 0);
  const nasStorageStatusKey = String(nasStoragePressure.status || "").trim().toLowerCase();
  const nasStorageProbeFailed =
    Boolean(nasStoragePressure.probeTimedOut) || Boolean(nasStoragePressure.probeConnectFailed);
  const nasStorageMeasuredUsageAvailable = Boolean(
    nasStoragePressure.measuredUsageAvailable ?? !nasStorageProbeFailed,
  );
  const nasStorageHasEvidence = Boolean(
    nasStoragePressure.schema ||
      nasStoragePressure.checkedAt ||
      nasStoragePressure.source ||
      nasStorageStatusKey,
  );
  const nasStorageUsageLine = nasStorageMeasuredUsageAvailable
    ? `${nasStorageUsedPercent || storageTriageSummary.usedPercent || 0}% used · ${storageTriageSummary.generatedCandidateCount || 0} generated cleanup`
    : `usage unverified · ${storageTriageSummary.generatedCandidateCount || 0} generated cleanup`;
  const nasStorageMeasuredPressure =
    nasStorageHasEvidence &&
    nasStorageMeasuredUsageAvailable &&
    (nasStorageStatusKey === "critical" ||
      nasStorageStatusKey === "full" ||
      nasStorageAvailableBytes <= 0 ||
      nasStorageUsedPercent >= 99);
  const nasStorageBlockDetail = nasStorageMeasuredPressure
    ? `${nasStoragePressure.mount || "/volume1/Saclay"} reports ${nasStorageUsedPercent}% used with ${nasStorageAvailableBytes} available bytes. Mission resume stays blocked until real headroom returns.`
    : !nasStorageHasEvidence
      ? `${nasStoragePressure.mount || "/volume1/Saclay"} needs a live NAS storage check because no current df evidence is loaded. This is not measured full; the UI must not treat this as a measured full disk.`
      : `${nasStoragePressure.mount || "/volume1/Saclay"} usage is unverified because the bounded NAS probe did not return df data. This is not measured full; the UI must not treat this as a measured full disk. Mission resume needs a fresh NAS check or a local workspace.`;
  const storageTriageRows = asList(storageTriageSummary.rows);
  const storageOperatorHandoff = storageTriageSummary?.handoff || {};
  const storageAdminChecklist = asList(storageOperatorHandoff.adminChecklist);
  const deploymentDurabilitySummary = systemAuditDigest?.deploymentDurabilitySummary || {};
  const deploymentTemporaryCount = Number(deploymentDurabilitySummary.temporarySymlinkCount || 0);
  const deploymentDurabilityBlocked =
    deploymentDurabilitySummary.schema &&
    deploymentDurabilitySummary.durable === false;
  const nasStorageBlocked =
    !nasStorageHasEvidence ||
    nasStorageProbeFailed ||
    !nasStorageMeasuredUsageAvailable ||
    nasStorageMeasuredPressure;
  const liveMissionOutputQuality = systemAuditDigest?.liveMissionOutputQuality || {};
  const missionArtifactRepairPlan = systemAuditDigest?.missionArtifactRepairPlan || {};
  const missionArtifactRepairRows = asList(missionArtifactRepairPlan.repairs);
  const missionArtifactRepairStorage = missionArtifactRepairPlan.storagePreflight || {};
  const artifactRepairRows = missionArtifactRepairRows.length > 0
    ? missionArtifactRepairRows
    : asList(liveMissionOutputQuality.repairMissionRows);
  const artifactRepairCount = Number(
    missionArtifactRepairPlan.repairMissionCount ||
      missionArtifactRepairRows.length ||
      liveMissionOutputQuality.repairMissionCount ||
      artifactRepairRows.length ||
      liveMissionOutputQuality.weakMissionCount ||
      0,
  );
  const goalArtifactRepairCount = artifactRepairCountFromGoalRows(goalCompletionRows);
  const firstViewportArtifactRepairCount = Math.max(artifactRepairCount, goalArtifactRepairCount);
  const artifactRepairCanResume = missionArtifactRepairRows.length > 0
    ? missionArtifactRepairRows.some(item => item?.canResumeNow !== false)
    : missionArtifactRepairStorage?.canResume !== false;
  const artifactRepairBlockedByCurrentStorage = artifactRepairCanResume === false && nasStorageBlocked;
  const artifactRepairBlocked =
    String(missionArtifactRepairPlan.status || "").trim().toLowerCase() === "repairs_blocked_by_nas_storage" ||
    String(missionArtifactRepairPlan.status || "").trim().toLowerCase() === "repairs_ready" ||
    String(liveMissionOutputQuality.status || "").trim().toLowerCase() === "needs_artifact_repair" ||
    firstViewportArtifactRepairCount > 0;
  const criticalBlockerRows = [
    deploymentDurabilityBlocked ? {
      id: "deployment-durability",
      label: "Deployment durability",
      title: deploymentDurabilitySummary.headline || "NAS deployment is not durable",
      detail: deploymentTemporaryCount
        ? `${deploymentTemporaryCount} active release path${deploymentTemporaryCount === 1 ? "" : "s"} point into /tmp. The app is working now, but this recovery patch is not reboot-durable.`
        : "The deployment is live, but the audit did not prove durable writable release paths.",
      action: deploymentDurabilitySummary.nextAction || "Free durable NAS space, write the patched files into the release, restart, and rerun live verification.",
      tone: "bad",
    } : null,
    nasStorageBlocked ? {
      id: "nas-storage-pressure",
      label: "NAS write check",
      title: nasStorageMeasuredPressure ? "NAS measured storage pressure" : "NAS write state unverified",
      detail: nasStorageBlockDetail,
      action: nasStorageMeasuredPressure
        ? nasStoragePressure.nextAction || "Free volume/snapshot space, then rerun storage pressure verification."
        : nasStoragePressure.nextAction || "Rerun the bounded NAS storage probe or switch this mission to a local workspace.",
      tone: nasStorageMeasuredPressure ? "bad" : "warn",
    } : null,
    artifactRepairBlocked ? {
      id: "artifact-repair-gate",
      label: "Mission proof",
      title: artifactRepairCanResume === false
        ? artifactRepairBlockedByCurrentStorage
          ? `${firstViewportArtifactRepairCount || 1} artifact repair${(firstViewportArtifactRepairCount || 1) === 1 ? "" : "s"} blocked by NAS storage`
          : `${firstViewportArtifactRepairCount || 1} artifact repair${(firstViewportArtifactRepairCount || 1) === 1 ? "" : "s"} waiting for proof`
        : `${firstViewportArtifactRepairCount || 1} artifact repair gate${(firstViewportArtifactRepairCount || 1) === 1 ? "" : "s"} open`,
      detail:
        missionArtifactRepairPlan.nextAction ||
        liveMissionOutputQuality.nextAction ||
        "Resume failed missions only with a hard artifact gate and real runtime-output body.",
      action:
        artifactRepairCanResume === false
          ? artifactRepairBlockedByCurrentStorage
            ? "Repair rows are visible, but resume remains disabled until NAS storage preflight passes."
            : "Repair rows are visible, but resume remains disabled by stale or missing proof preflight, not a measured NAS-full state."
          : artifactRepairRows[0]?.command || artifactRepairRows[0]?.action || "Open the failed mission in Agent and Workbench proof.",
      tone: "warn",
      missionId: artifactRepairRows[0]?.missionId || artifactRepairRows[0]?.mission_id || "",
      canResume: artifactRepairCanResume,
    } : null,
  ].filter(Boolean);
  const operatorPriorityRows = [
    ...systemLossDriverRows.slice(0, 2).map(item => ({
      id: `loss-${item.id}`,
      label: item.lane,
      title: item.title,
      detail: item.nextAction || item.detail,
      tone: Number(item.loss || 0) >= 3 ? "bad" : "warn",
    })),
    ...asList(systemAuditDigest?.badFirst).slice(0, 2).map((item, index) => ({
      id: `bad-first-${item.title || index}`,
      label: "Still weak",
      title: item.title || "Current gap",
      detail: item.detail || item.nextAction || "Open the related mission and attach proof.",
      tone: "warn",
    })),
  ].slice(0, 4);
  return (
    <div className="fluxos-builder" data-builder-clarity-mode={normalizedBuilderClarityMode}>
      <section className="fluxos-builder-main">
        <div className="fluxos-section-head">
          <span>Builder</span>
          <strong>{isLiveBackend ? "Live NAS mission readiness" : "Project readiness"}</strong>
          {isLiveBackend ? (
            <div className="fluxos-builder-clarity-switch" aria-label="Builder clarity mode" data-builder-clarity-switch="true">
              <button
                className={builderFocusMode ? "active" : ""}
                onClick={() => setLiveBuilderClarityMode("focus")}
                type="button"
              >
                Focus
              </button>
              <button
                className={!builderFocusMode ? "active" : ""}
                onClick={() => setLiveBuilderClarityMode("full")}
                type="button"
              >
                Full
              </button>
            </div>
          ) : null}
        </div>
        <div className="fluxos-live-data-banner" aria-label="Live data source">
          <span>{isLiveBackend ? "Live data" : "Preview data"}</span>
          <strong>{liveDataStatus?.source || (isLiveBackend ? "control-room summary" : "fixture")}</strong>
          <p>
            {liveMissionCount} mission rows · {Number(liveDataStatus?.notificationCount || 0)} notifications
            {liveDataStatus?.refreshedAt ? ` · refreshed ${liveDataStatus.refreshedAt}` : ""}
            {liveDataStatus?.summaryCache?.status
              ? ` · ${liveDataStatus.summaryCache.status === "hit" ? "warm live summary" : "fresh live summary"}`
              : ""}
            {liveDataStatus?.refreshing && !liveLoading ? " · full snapshot refreshing" : ""}
          </p>
        </div>
        <section
          className="fluxos-builder-current-mission"
          aria-label="Builder current mission command canvas"
          data-builder-current-mission="true"
          data-ui-self-repair-canvas="mission8"
          data-broader-ui-self-repair-receipt="true"
          data-broader-ui-self-repair-status={builderSelfRepairProof?.missionGate?.status || builderSelfRepairProof?.status || "pending"}
        >
          <div className="fluxos-builder-current-copy">
            <span>{isLiveBackend ? "Current mission" : "Fixture mission"}</span>
            <strong>{builderPrimaryTitle}</strong>
            <p>{builderPrimaryDetail}</p>
            <div className="fluxos-builder-current-meta" aria-label="Mission route and state">
              <em>{builderPrimaryStatus}</em>
              <em>Hermes primary</em>
              <em>OpenClaw fallback</em>
              <em>{isLiveBackend ? "live NAS" : "fixture proof"}</em>
            </div>
          </div>
          <div className="fluxos-builder-current-progress">
            <span>{builderPrimaryProgress == null ? "No live percent" : `${builderPrimaryProgress}%`}</span>
            <i aria-hidden="true" style={{ "--progress": `${builderPrimaryProgress ?? 12}%` }} />
            <small>{builderPrimaryProgressLabel}</small>
          </div>
          <div className="fluxos-builder-current-actions">
            <button disabled={!builderPrimaryMissionId} onClick={() => onOpenBuilderDetail?.(builderPrimaryMissionId)} type="button">
              Continue
            </button>
            <button onClick={() => onRequestAction?.("run:proof")} type="button">
              Verify
            </button>
            <button onClick={() => onRequestAction?.("launch:mission")} type="button">
              Launch
            </button>
            <button
              data-builder-self-repair-action="true"
              disabled={builderSelfRepairBusy || !callBackend}
              onClick={() => void runBuilderSelfRepairLoop()}
              type="button"
            >
              {builderSelfRepairBusy ? "Recording proof" : "Run self-repair"}
            </button>
          </div>
          <div className="fluxos-builder-current-proof" aria-label="Builder self-repair proof">
            {builderProofCompactRows.map(item => (
              <article className={`tone-${item.tone || "neutral"}`} key={`builder-current-proof-${item.label}`}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
                <p>{item.detail}</p>
              </article>
            ))}
          </div>
          {builderSelfRepairProof ? (
            <div className="fluxos-builder-current-repair-receipt" aria-label="Broader UI self-repair receipt">
              <span>Mission 8 UI repair receipt</span>
              <strong>{builderSelfRepairProof.selectedRepair || "Broader UI self-repair proof recorded"}</strong>
              <p>
                {(builderSelfRepairProof.auditedSurfaces || []).length
                  ? `Audited ${(builderSelfRepairProof.auditedSurfaces || []).join(", ")}.`
                  : builderSelfRepairProof.message}
              </p>
              <small>{builderSelfRepairProof.artifacts?.missionGatePath || builderSelfRepairProof.artifacts?.surfaceAuditPath || "Proof artifact pending"}</small>
            </div>
          ) : null}
        </section>
        {isLiveBackend ? (
          <section
            className="fluxos-builder-timeline"
            aria-label="Live Builder mission timeline"
            data-builder-timeline-density={normalizedBuilderTimelineDensity}
            data-builder-timeline-horizon={normalizedBuilderTimelineHorizon}
            data-builder-timeline-show-done={builderTimelineShowDone ? "true" : "false"}
            data-builder-timeline-canvas-polish="v2"
            data-live-builder-timeline="true"
          >
            <div className="fluxos-builder-timeline-head">
              <div>
                <span>Mission timeline</span>
                <strong>{builderTimelineHeadline}</strong>
                <p className="fluxos-builder-timeline-context">{builderTimelineContext}</p>
                <span className="fluxos-builder-timeline-source">
                  {isLiveBackend ? "Live NAS" : "Preview"} · {liveDataStatus?.source || "control-room summary"} · {liveMissionCount} missions
                </span>
                <div
                  className="fluxos-builder-timeline-display-controls"
                  aria-label="Timeline display controls"
                  data-builder-timeline-display-controls="true"
                >
                  <div>
                    <span>Horizon</span>
                    {[
                      ["phase", "Phase"],
                      ["month", "Month"],
                      ["quarter", "90d"],
                      ["year", "Year"],
                    ].map(([value, label]) => (
                      <button
                        aria-pressed={normalizedBuilderTimelineHorizon === value}
                        className={normalizedBuilderTimelineHorizon === value ? "active" : ""}
                        data-builder-timeline-horizon-option={value}
                        key={`timeline-horizon-${value}`}
                        onClick={() => setLiveBuilderTimelineHorizon(value)}
                        type="button"
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <div>
                    <span>Density</span>
                    {[
                      ["comfortable", "Comfort"],
                      ["compact", "Compact"],
                    ].map(([value, label]) => (
                      <button
                        aria-pressed={normalizedBuilderTimelineDensity === value}
                        className={normalizedBuilderTimelineDensity === value ? "active" : ""}
                        data-builder-timeline-density-option={value}
                        key={`timeline-density-${value}`}
                        onClick={() => setLiveBuilderTimelineDensity(value)}
                        type="button"
                      >
                        {label}
                      </button>
                    ))}
                    <button
                      aria-pressed={builderTimelineShowDone}
                      className={builderTimelineShowDone ? "active" : ""}
                      data-builder-timeline-toggle-done="true"
                      onClick={toggleLiveBuilderTimelineDone}
                      type="button"
                    >
                      Done
                    </button>
                  </div>
                </div>
              </div>
              <div className="fluxos-builder-timeline-actions">
                <button data-builder-timeline-action="continue" disabled={!builderActionMissionId} onClick={() => onOpenBuilderDetail?.(builderActionMissionId)} type="button">
                  Continue
                </button>
                <button data-builder-timeline-action="modify" disabled={!builderActionMissionId} onClick={() => onRequestAction?.("run:modify")} type="button">
                  Modify
                </button>
                <button data-builder-timeline-action="launch" onClick={() => onRequestAction?.("launch:mission")} type="button">
                  Launch
                </button>
                <button data-builder-timeline-action="verify" onClick={() => onRequestAction?.("run:proof")} type="button">
                  Verify
                </button>
                <button data-builder-timeline-action="summarize" disabled={!builderActionMissionId} onClick={() => onRequestAction?.("run:summarize")} type="button">
                  Summarize
                </button>
                <button data-builder-timeline-action="agent" disabled={!builderActionMissionId} onClick={() => onOpenBuilderDetail?.(builderActionMissionId)} type="button">
                  Agent
                </button>
              </div>
            </div>
            <div className="fluxos-builder-timeline-body">
              <div className="fluxos-builder-timeline-scale" aria-hidden="true" data-builder-timeline-gantt-semantics="true">
                {builderTimelineScaleLabels.map(label => <span key={`timeline-scale-${label}`}>{label}</span>)}
              </div>
              <div className="fluxos-builder-timeline-rows">
                {builderTimelineRows.length > 0 ? builderTimelineRows.map(item => (
                  <button
                    aria-label={`Open details for ${item.title}`}
                    className={`tone-${item.tone || "neutral"}`.trim()}
                    data-builder-timeline-selected-row={item.selected ? "true" : "false"}
                    data-live-builder-timeline-row="true"
                    key={item.id}
                    onClick={item.onClick}
                    style={{ "--timeline-start": `${item.start}%`, "--timeline-span": `${item.span}%`, "--timeline-progress": `${item.progress}%` }}
                    title={`Open details for ${item.title}`}
                    type="button"
                  >
                    <span className="fluxos-builder-timeline-row-lane">{item.lane}</span>
                    <strong className="fluxos-builder-timeline-row-title">{item.title}</strong>
                    <span className="fluxos-builder-timeline-row-state" data-live-builder-timeline-row-state="true">
                      <small>{item.phaseLabel || "Plan"}</small>
                      <small>{item.checkpointLabel || item.meta || "checkpoint"}</small>
                      <small>{item.dependencyLabel || "dependency clear"}</small>
                    </span>
                    <span className="fluxos-builder-timeline-row-bar" aria-hidden="true">
                      <span className="fluxos-builder-timeline-row-marker start" />
                      <span className="fluxos-builder-timeline-row-marker finish" />
                      <i />
                    </span>
                    <em className="fluxos-builder-timeline-row-meta">{item.meta}</em>
                    <span className="fluxos-builder-timeline-row-action">{item.actionLabel || "Open"}</span>
                    <p className="fluxos-builder-timeline-row-detail">{item.detail}</p>
                  </button>
                )) : (
                  <article className="fluxos-builder-timeline-empty">
                    <span>Live NAS only</span>
                    <strong>No timeline rows returned</strong>
                    <p>Launch a mission or wait for the authenticated summary to return mission and queue rows.</p>
                  </article>
                )}
              </div>
            </div>
            <aside className="fluxos-builder-timeline-proof" aria-label="Timeline proof and next action">
              {builderTimelineProofRows.map(item => (
                <article className={`tone-${item.tone || "neutral"}`} key={`timeline-proof-${item.label}`}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                  <p>{item.detail}</p>
                </article>
              ))}
            </aside>
          </section>
        ) : null}
        <section
          className={cx("fluxos-anti-drift-guard", `tone-${antiDriftGuard.tone}`, antiDriftGuard.liveEvidence ? "has-evidence" : "waiting")}
          aria-label="Mission anti-drift guard"
          data-anti-drift-guard="true"
          data-anti-drift-route-proof="true"
          data-live-watchdog-evidence={antiDriftGuard.liveEvidence ? "true" : "false"}
          data-monitoring-control-points="true"
          data-primary-runtime-lane={antiDriftGuard.primaryRuntimeLane}
        >
          <div className="fluxos-anti-drift-copy">
            <span>Anti-drift guard</span>
            <strong>{antiDriftGuard.title}</strong>
            <p>{antiDriftGuard.nextAction}</p>
          </div>
          <div className="fluxos-anti-drift-signals" aria-label="Monitoring control points">
            {antiDriftGuard.signals.map(item => (
              <article className={`tone-${item.status}`} key={`anti-drift-${item.id}`}>
                <span>{item.label}</span>
                <strong>{item.status === "pending" ? "Pending" : item.count > 0 ? item.count : "Clear"}</strong>
                <p>{item.detail}</p>
              </article>
            ))}
          </div>
          <div className="fluxos-anti-drift-actions">
            <span>{`Hermes primary · OpenClaw fallback · ${antiDriftGuard.issueCount} issue${antiDriftGuard.issueCount === 1 ? "" : "s"}`}</span>
            <button
              onClick={() => onRequestAction?.("watchdog:anti-drift-guard")}
              type="button"
            >
              Capture guard proof
            </button>
          </div>
        </section>
        {!isLiveBackend ? (
          <section
            className="fluxos-builder-preview-state"
            aria-label="Builder preview state"
            data-builder-preview-state="true"
          >
            <div className="fluxos-builder-preview-copy">
              <span>Preview mode</span>
              <strong>Builder workspace is ready for live mission rows</strong>
              <p>
                This surface is showing preview readiness because the authenticated NAS mission feed is not attached.
                Live mode replaces these rows with the mission timeline, queue, proof, and launch controls.
              </p>
            </div>
            <div className="fluxos-builder-preview-grid" aria-label="Builder preview readiness checks">
              {rows.slice(0, 4).map((row, index) => (
                <article className={`tone-${row.tone || row.statusTone || "neutral"}`} key={row.id || row.name || `builder-preview-${index}`}>
                  <span>{row.status || row.lane || "Ready"}</span>
                  <strong>{row.name || row.title || "Builder flow"}</strong>
                  <p>{row.description || row.detail || row.lastRunMeta || "Open live mode to attach authenticated mission evidence."}</p>
                  <button onClick={() => onOpenBuilderDetail?.(row.id || row.missionId || row.mission_id || "")} type="button">
                    Open
                  </button>
                </article>
              ))}
            </div>
            <section className="proof-side-by-side-diff preview-contract" aria-label="Side-by-side proof diff fixture contract">
              <div className="proof-side-by-side-head">
                <div>
                  <span>Side-by-side proof diff</span>
                  <strong>Preview fixture route is mounted</strong>
                </div>
                <p>Fixture-only receipt. Live proof rows appear only when the NAS mission detail provides captured evidence.</p>
              </div>
            </section>
          </section>
        ) : null}
        {isLiveBackend ? (
          <section
            className="fluxos-builder-operator-dock"
            aria-label="Builder operator dock"
            data-live-builder-operator-dock="true"
          >
            {builderOperatorDockRows.map(item => (
              <article className={`tone-${item.tone || "neutral"}`} key={`builder-operator-dock-${item.id}`}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
                <p>{item.detail}</p>
                {item.action ? (
                  <button disabled={item.disabled} onClick={item.onClick} type="button">
                    {item.action}
                  </button>
                ) : null}
              </article>
            ))}
          </section>
        ) : null}
        {isLiveBackend ? (
          <section
            className={`fluxos-runtime-proof-strip ${runtimeProofVerified ? "verified" : "pending"}`}
            aria-label="Hermes MiniMax-M3 runtime proof"
            data-live-hermes-m3-runtime-proof="true"
            data-live-hermes-m3-verified={runtimeProofVerified ? "true" : "false"}
          >
            <div className="fluxos-runtime-proof-copy">
              <span>Hermes/M3 runtime proof</span>
              <strong>{runtimeProofVerified ? "Backend route is proven" : "Backend route proof is pending"}</strong>
              <p>
                {runtimeProofVerified
                  ? `Last live reply: ${runtimeProofReceipt.replyPreview || "Hermes MiniMax-M3 answered through the authenticated backend."}`
                  : "This panel is populated only from the live backend route receipt and runtime PATH check."}
              </p>
            </div>
            <div className="fluxos-runtime-proof-grid">
              {runtimeProofRows.map(item => (
                <article className={`tone-${item.tone}`} key={item.label}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                  <p>{item.detail}</p>
                </article>
              ))}
            </div>
          </section>
        ) : null}
        <LiveOperationsBrief
          activeRows={activeRows}
          liveDataStatus={liveDataStatus}
          onOpenAgent={() => onOpenBuilderDetail?.(selectedMissionId)}
          onOpenNotifications={() => onRequestAction?.("notifications:show-live-stack")}
          onOpenQueue={() => onSelectProject?.(schedulingQueueRows[0]?.workspaceId)}
          projectProgressHistory={projectProgressHistory}
          queueRows={schedulingQueueRows}
          threadRows={selectedThreadRows}
          workbenchState={workbenchState}
        />
        {isLiveBackend ? (
          <section
            className="fluxos-live-command-rail"
            aria-label="Live Builder progress, Agent report, notifications, and Watchdog"
            data-live-builder-command-rail="true"
          >
            <div className="fluxos-live-command-rail-head">
              <div>
                <span>Live control strip</span>
                <strong>Quick mission actions</strong>
              </div>
              <p>
                Hermes-first Builder view. MiniMax-M3 is the frontend executor route when authenticated and available;
                this strip only renders rows returned by the live NAS summary/detail endpoints.
              </p>
            </div>
            <div className="fluxos-live-command-rail-grid">
              {liveControlRailRows.map(item => (
                <article className={`tone-${item.tone || "neutral"}`} key={`live-command-rail-${item.id}`}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                  <p>{item.detail}</p>
                  <button disabled={item.disabled} onClick={item.onClick} type="button">
                    {item.action}
                  </button>
                </article>
              ))}
            </div>
          </section>
        ) : null}
        {isLiveBackend && goalCompletionAudit?.schema ? (
          <section className="fluxos-first-blocker" aria-label="Live objective blocker" data-live-objective-blocker="true">
            <div>
              <span>Objective state</span>
              <strong>{`${Number(goalCompletionAudit.completionPercent || 0)}% proven · ${titleizeToken(goalCompletionAudit.status || "partial")}`}</strong>
              <p>
                {goalCompletionAudit.topBlocker?.label
                  ? `Blocked by ${goalCompletionAudit.topBlocker.label}: ${goalCompletionAudit.topBlocker.nextAction || goalCompletionAudit.nextAction || ""}`
                  : goalCompletionAudit.nextAction || "Completion is calculated from live NAS, mission, T3, proof, and deployment evidence."}
              </p>
            </div>
            <div className="fluxos-first-blocker-metrics">
              <article className={nasStorageBlocked ? "bad" : "ok"}>
                <span>Storage</span>
                <strong>{nasStorageBlocked ? "Blocked" : "Writable"}</strong>
                <p>{nasStorageUsageLine}</p>
              </article>
              <article
                className={deploymentDurabilityBlocked ? "bad" : "ok"}
                data-deployment-durability-summary="true"
              >
                <span>Durability</span>
                <strong>{deploymentDurabilityBlocked ? "Temporary" : "Durable"}</strong>
                <p>{deploymentDurabilityBlocked ? `${deploymentTemporaryCount || 0} /tmp release path${deploymentTemporaryCount === 1 ? "" : "s"}` : "Release paths passed"}</p>
              </article>
              <article className={artifactRepairBlocked ? "warn" : "ok"}>
                <span>Proof repair</span>
                <strong>{firstViewportArtifactRepairCount || 0}</strong>
                <p>{artifactRepairBlocked ? "mission gates need repair" : "no active repair gate"}</p>
              </article>
            </div>
          </section>
        ) : null}
        {isLiveBackend ? (
          <section
            className="fluxos-queue-first-band"
            aria-label="Queue-first Builder command band"
            data-live-builder-command-band="true"
          >
            <div className="fluxos-queue-first-copy">
              <span>Queue-first Builder</span>
              <strong>
                {topQueueRow
                  ? `#${topQueueRow.rank} ${topQueueRow.title}`
                  : selectedMissionRow?.name || selectedMissionRow?.title || "No ranked project"}
              </strong>
              <p>
                {topQueueRow?.recommendedAction ||
                  topQueueRow?.reason ||
                  workbenchState?.progress?.nextAction ||
                  liveControlStateDetail}
              </p>
              <p
                className={`fluxos-queue-first-state ${zeroActiveQueueHealthy ? "healthy" : "active"}`.trim()}
                data-live-zero-active-state={zeroActiveQueueHealthy ? "healthy" : "active-or-ready"}
              >
                <span>{liveControlStateLabel}</span>
                <em>{liveControlStateDetail}</em>
              </p>
            </div>
            <div className="fluxos-queue-first-metrics" aria-label="Queue-first live Builder metrics">
              <article>
                <span>Projects</span>
                <strong>{projectHealthRows.filter(item => Number(item.activeCount || 0) > 0).length}</strong>
                <p>{queueFirstHeldCount} held</p>
              </article>
              <article>
                <span>Missions</span>
                <strong>{liveActiveCount}</strong>
                <p>{liveBlockedCount} blocked</p>
              </article>
              <article>
                <span>Queue</span>
                <strong>{schedulingQueueRows.length}</strong>
                <p>{topQueueRow?.safeToLaunch ? "top safe" : topQueueRow ? "top held" : "empty"}</p>
              </article>
              <article>
                <span>Alerts</span>
                <strong>{queueFirstNotificationCount}</strong>
                <p>{queueFirstSliceCount} slice</p>
              </article>
            </div>
            <div className="fluxos-queue-first-actions">
              <button disabled={!topQueueRow?.workspaceId} onClick={() => onSelectProject?.(topQueueRow?.workspaceId)} type="button">
                Open top project
              </button>
              <button disabled={!selectedMissionId} onClick={() => onOpenBuilderDetail?.(selectedMissionId)} type="button">
                Open live Agent
              </button>
              <button
                data-launch-blocked-by-storage={nasStorageBlocked ? "true" : "false"}
                disabled={nasStorageBlocked}
                onClick={() => onRequestAction?.("launch:mission")}
                type="button"
              >
                {nasStorageBlocked ? "Launch blocked by storage" : "Launch next mission"}
              </button>
            </div>
          </section>
        ) : null}
        <div className="fluxos-status-grid">
          <MetricTile detail={liveLoading ? "Waiting for the authenticated NAS summary; no cached rows are shown." : isLiveBackend ? "All mission rows from the NAS summary, not the visible preview limit." : "Typecheck and browser smoke pending"} label={isLiveBackend ? "Live missions" : "Publish confidence"} tone={liveMissionCount ? "good" : "warn"} value={isLiveBackend ? (liveLoading ? "Syncing" : String(liveMissionCount)) : "82%"} />
          <MetricTile detail={liveLoading ? "Running, queued, and completed counts appear after the live summary returns." : isLiveBackend ? `${liveRunningCount} running · ${liveQueuedCount} queued · ${liveCompletedCount} completed` : "Active flows connected to review cards"} label={isLiveBackend ? "Active" : "Flows"} tone="good" value={isLiveBackend ? (liveLoading ? "--" : String(liveActiveCount)) : String(activeRows.length)} />
          <MetricTile detail={liveLoading ? "Review blockers are hidden until the NAS response is loaded." : isLiveBackend ? "Blocked, failed, or approval-gated mission rows from the NAS summary." : "One approval blocks merge"} label="Review" tone="warn" value={isLiveBackend ? (liveLoading ? "--" : String(liveBlockedCount)) : "Open"} />
        </div>
        {isLiveBackend ? (
          <section className="fluxos-beginner-guide" aria-label="Live beginner mission guide" data-live-beginner-guide="true">
            <div className="fluxos-section-head">
              <span>Beginner guide</span>
              <strong>{selectedMissionRow?.name || selectedMissionRow?.title || "Select a live mission"}</strong>
            </div>
            <div className="fluxos-beginner-guide-grid">
              {liveGuideRows.map(item => (
                <article key={`live-guide-${item.id}`}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                  <p>{item.detail}</p>
                </article>
              ))}
            </div>
            <div className="fluxos-beginner-actions">
              <button disabled={!selectedMissionId} onClick={() => onOpenBuilderDetail?.(selectedMissionId)} type="button">Open Agent thread</button>
              <button disabled={!schedulingQueueRows[0]?.workspaceId} onClick={() => onSelectProject?.(schedulingQueueRows[0]?.workspaceId)} type="button">Open top queued project</button>
              <button onClick={() => onRequestAction?.("notifications:show-live-stack")} type="button">Show notifications</button>
            </div>
          </section>
        ) : null}
        {isLiveBackend && builderFocusMode ? (
          <section
            className="fluxos-builder-focus-drawer"
            aria-label="Builder focus proof drawer"
            data-builder-focus-disclosure="true"
          >
            <div>
              <span>Focus view</span>
              <strong>Diagnostics are folded below the operator path</strong>
              <p>
                The visible Builder path keeps live mission state, Agent report, queue, notifications, and objective blockers first.
                Full proof panels stay live and verifier-visible; switch to Full when you need the audit trail.
              </p>
            </div>
            <div className="fluxos-builder-focus-drawer-grid">
              <article>
                <span>Audit rows</span>
                <strong>{goalCompletionRows.length || 0}</strong>
                <p>Requirement-by-requirement proof is folded in Focus.</p>
              </article>
              <article>
                <span>Queue rows</span>
                <strong>{schedulingQueueRows.length || 0}</strong>
                <p>The top ranked project remains visible in the command band.</p>
              </article>
              <article>
                <span>Launch proof</span>
                <strong>{publicLaunchSteps.length || 0}</strong>
                <p>Public launch and release-packet proof stay in Full mode.</p>
              </article>
              <article>
                <span>Diff rows</span>
                <strong>{proofDiffRows.length || 0}</strong>
                <p>Supervisor proof diff is available from Full or Agent detail.</p>
              </article>
              <article data-provider-admission-focus-summary="true">
                <span>Admission vs quota</span>
                <strong>{selectedProviderCapabilities.readyLaneCount || 0}/{providerLaneRows.length || selectedProviderCapabilities.laneCount || 0}</strong>
                <p>Auth decides launch admission; unreported quota is not a provider-limit claim.</p>
              </article>
            </div>
            <button onClick={() => setLiveBuilderClarityMode("full")} type="button">
              Open full diagnostics
            </button>
          </section>
        ) : null}
        {isLiveBackend && operatorNextPath?.schema ? (
          <section
            className="fluxos-operator-next-path"
            aria-label="Live operator next path"
            data-live-operator-next-path="true"
          >
            <div className="fluxos-section-head">
              <span>Operator next path</span>
              <strong>{operatorNextPath.headline || "Follow the live proof-first path"}</strong>
            </div>
            <p>
              {`${operatorNextPath.blockedStepCount || 0} blocked · ${operatorNextPath.operatorConfidenceScore || 0}/100 confidence · live audit only`}
            </p>
            <div className="fluxos-operator-next-steps">
              {operatorNextPathSteps.map((item, index) => (
                <article
                  className={`status-${item.status || "open"}`}
                  data-operator-next-step={item.id || index}
                  key={`operator-next-step-${item.id || index}`}
                >
                  <span>{`${String(index + 1).padStart(2, "0")} · ${item.label || "Step"}`}</span>
                  <strong>{item.title || "Live operator step"}</strong>
                  <p>{item.detail || item.action || "No live detail recorded."}</p>
                  <em>{item.action || item.command || "No action recorded."}</em>
                  {item.missionId ? (
                    <button onClick={() => onOpenBuilderDetail?.(item.missionId)} type="button">
                      Open mission proof
                    </button>
                  ) : null}
                </article>
              ))}
            </div>
          </section>
        ) : null}
        {isLiveBackend && goalCompletionAudit?.schema ? (
          <section
            className={`fluxos-goal-completion status-${goalCompletionAudit.status || "partial"}`}
            aria-label="Objective completion audit"
            data-goal-completion-audit="true"
          >
            <div className="fluxos-section-head">
              <span>Objective completion audit</span>
              <strong>{`${Number(goalCompletionAudit.completionPercent || 0)}% proven · ${titleizeToken(goalCompletionAudit.status || "partial")}`}</strong>
            </div>
            <p>
              {goalCompletionAudit.topBlocker?.label
                ? `Top blocker: ${goalCompletionAudit.topBlocker.label}. ${goalCompletionAudit.topBlocker.nextAction || goalCompletionAudit.nextAction || ""}`
                : goalCompletionAudit.nextAction || "Completion is calculated from live NAS, mission, T3, proof, and deployment evidence."}
            </p>
            <div className="fluxos-goal-completion-grid">
              {goalCompletionRows.slice(0, 12).map(item => (
                <article className={`status-${item.status || "missing"}`} data-goal-completion-row="true" key={item.id || item.label}>
                  <span>{titleizeToken(item.status || "missing")}</span>
                  <strong>{item.label || item.id}</strong>
                  <p>{item.evidence || "No live evidence recorded."}</p>
                  <em>{item.nextAction || "No next action recorded."}</em>
                </article>
              ))}
            </div>
          </section>
        ) : null}
        {isLiveBackend && speedSupervisorSummary?.schema ? (
          <section
            className={`fluxos-speed-supervisor status-${speedSupervisorSummary.status || "watch"}`}
            aria-label="Live speed and supervisor summary"
            data-speed-supervisor-summary="true"
          >
            <div className="fluxos-section-head">
              <span>Speed supervisor</span>
              <strong>
                {speedSupervisorSummary.supervisorStale
                  ? "Watchdog state is stale"
                  : speedSupervisorSummary.status === "pass"
                    ? "Fast live path"
                    : "Measured live path needs attention"}
              </strong>
            </div>
            <p>
              {`${Number(speedSupervisorSummary.summaryMaxWallMs || 0).toFixed(1)}ms summary · ${Number(speedSupervisorSummary.detailMaxWallMs || 0).toFixed(1)}ms detail · `}
              {`${speedSupervisorSummary.watchdogCompletedReceipts || 0} watchdog receipts`}
            </p>
            <div className="fluxos-speed-supervisor-grid">
              {speedSupervisorRows.map((item, index) => (
                <article className={`status-${item.status || "watch"}`} key={`speed-supervisor-${item.id || index}`}>
                  <span>{item.label || "Live gate"}</span>
                  <strong>{item.metric || item.status || "Measured"}</strong>
                  <p>{item.detail || "No live supervisor detail recorded."}</p>
                </article>
              ))}
            </div>
          </section>
        ) : null}
        {isLiveBackend ? (
          <section
            className="fluxos-mission-advancement-digest"
            aria-label="Live mission advancement digest"
            data-live-advancement-digest="true"
          >
            <div className="fluxos-section-head">
              <span>Mission advancement digest</span>
              <strong>{`${missionAdvancementRows.length} visible mission${missionAdvancementRows.length === 1 ? "" : "s"} · live NAS only`}</strong>
            </div>
            <p>
              Current mission progress, self-improvement pressure, and public-readiness blockers are grouped here so Builder answers what advanced without mixing in fixture data.
            </p>
            <div className="fluxos-mission-advancement-grid">
              {missionAdvancementRows.length > 0 ? missionAdvancementRows.map(item => (
                <button
                  className={cx(`tone-${item.tone}`, ["proof_repair", "runtime_budget_exhausted"].includes(item.progressKind) && "proof-repair")}
                  data-live-advancement-mission="true"
                  data-progress-kind={item.progressKind || undefined}
                  key={item.id}
                  onClick={() => onOpenBuilderDetail?.(item.id)}
                  type="button"
                >
                  <span>{titleizeToken(item.status)}</span>
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                  <div>
                    {item.progress == null ? <em>No numeric progress</em> : <em>{`${item.progress}%${item.progressLabel ? ` · ${item.progressLabel}` : ""}`}</em>}
                    {item.meta ? <em>{item.meta}</em> : null}
                  </div>
                  {item.progress == null ? null : <i aria-label={`${item.progressLabel || "Mission progress"} ${item.progress}%`} style={{ "--progress": `${item.progress}%` }} />}
                </button>
              )) : (
                <article className="fluxos-flow-empty">
                  <span>Live data only</span>
                  <strong>No advancement rows returned</strong>
                  <p>The digest waits for NAS mission rows and never backfills sample progress.</p>
                </article>
              )}
            </div>
            {systemAdvancementRows.length > 0 ? (
              <div className="fluxos-system-advancement-grid" aria-label="System self-improvement advancement">
                {systemAdvancementRows.map(item => (
                  <article key={`system-advancement-${item.id}`}>
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                    <p>{item.detail}</p>
                  </article>
                ))}
              </div>
            ) : null}
          </section>
        ) : null}
        <LiveGuidedNextSteps
          liveDataStatus={liveDataStatus}
          onOpenAgent={() => onOpenBuilderDetail?.(selectedMissionId)}
          onOpenNotifications={() => onRequestAction?.("notifications:show-live-stack")}
          onOpenProof={() => onRequestAction?.("run:proof")}
          onOpenQueue={() => onSelectProject?.(schedulingQueueRows[0]?.workspaceId)}
          queueRows={schedulingQueueRows}
          threadRows={selectedThreadRows}
          workbenchState={workbenchState}
        />
        <LiveOperatorTutorialPath
          liveDataStatus={liveDataStatus}
          onOpenAgent={() => onOpenBuilderDetail?.(selectedMissionId)}
          onOpenNotifications={() => onRequestAction?.("notifications:show-live-stack")}
          onOpenProof={() => onRequestAction?.("run:proof")}
          onOpenQueue={() => onSelectProject?.(schedulingQueueRows[0]?.workspaceId)}
          queueRows={schedulingQueueRows}
          threadRows={selectedThreadRows}
          workbenchState={workbenchState}
        />
        {isLiveBackend && criticalBlockerRows.length > 0 ? (
          <section
            className="fluxos-critical-blockers"
            aria-label="Critical live Builder blockers"
            data-builder-critical-blockers="true"
          >
            <div className="fluxos-section-head">
              <span>Live blockers</span>
              <strong>Do not trust unattended launches until these clear</strong>
            </div>
            <div className="fluxos-critical-blockers-grid">
              {criticalBlockerRows.map(item => (
                <article
                  className={`tone-${item.tone}`}
                  data-deployment-durability-summary={item.id === "deployment-durability" ? "true" : undefined}
                  key={item.id}
                >
                  <span>{item.label}</span>
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                  <em>{item.action}</em>
                  {item.missionId ? (
                    <button
                      data-repair-can-resume={item.canResume === false ? "false" : "true"}
                      onClick={() => onOpenBuilderDetail?.(item.missionId)}
                      type="button"
                    >
                      {item.canResume === false ? "Inspect blocked repair" : "Open repair mission"}
                    </button>
                  ) : null}
                </article>
              ))}
            </div>
            {storageOperatorHandoff?.schema ? (
              <article className="fluxos-storage-handoff" data-storage-operator-handoff="true">
                <span>Storage handoff</span>
                <strong>{storageOperatorHandoff.summary || "Operator storage review required."}</strong>
                <p>
                  {storageOperatorHandoff.generatedCleanupAvailable
                    ? `${storageOperatorHandoff.generatedCandidateCount || 0} generated cleanup candidate(s), ${storageOperatorHandoff.estimatedGeneratedReclaimableMB || 0} MB estimated.`
                    : "No generated Syntelos cleanup is available; keep deletion decisions in NAS admin tools."}
                </p>
                <code>{storageOperatorHandoff.primaryCommand || "npm run plan:nas-storage-cleanup"}</code>
                <ul>
                  {storageAdminChecklist.slice(0, 3).map(item => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
            ) : null}
          </section>
        ) : null}
        {isLiveBackend && systemLossBreakdown?.schema && builderFocusMode ? (
          <section
            className="fluxos-system-loss"
            aria-label="System gap breakdown"
            data-system-loss-current="true"
          >
            <div>
              <span>System gap</span>
              <strong>{systemLossHeadline}</strong>
              <p>{systemLossSubline}</p>
            </div>
            <div className="fluxos-system-loss-drivers">
              {systemLossDriverRows.map(item => (
                <article key={item.id}>
                  <span>{`${item.lane} · gap ${item.loss}`}</span>
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                  {item.nextAction ? <em>{item.nextAction}</em> : null}
                </article>
              ))}
            </div>
          </section>
        ) : null}
        {isLiveBackend && operatorPriorityRows.length > 0 ? (
          <section
            className="fluxos-operator-priority"
            aria-label="Builder operator priority risks"
            data-builder-operator-priority="true"
          >
            <div className="fluxos-section-head">
              <span>Focus mode priorities</span>
              <strong>{builderFocusMode ? "Only live blockers and next actions" : "Live blockers stay pinned"}</strong>
            </div>
            <div className="fluxos-operator-priority-grid">
              {operatorPriorityRows.map(item => (
                <article className={`tone-${item.tone}`} key={item.id}>
                  <span>{item.label}</span>
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                </article>
              ))}
            </div>
            {builderFocusMode ? (
              <p className="fluxos-operator-priority-note">
                Provider routing, T3 parity tables, proof packets, and route internals are hidden in Focus mode. Switch to Full for diagnostics.
              </p>
            ) : null}
          </section>
        ) : null}
        {isLiveBackend ? (
          <section className="fluxos-project-queue" aria-label="Live multi-project Builder queue" data-live-builder-queue="true">
            <div className="fluxos-section-head">
              <span>Multi-project queue</span>
              <strong>
                {schedulingQueueRows.length} ranked project{schedulingQueueRows.length === 1 ? "" : "s"}
              </strong>
            </div>
            <p>
              {projectProgressHistory?.scheduler?.nextAction ||
                "Builder waits for the live NAS scheduling contract instead of guessing project order."}
            </p>
            {builderQueuePressureRows.length > 0 ? (
              <div className="fluxos-project-queue-pressure" data-live-builder-queue-pressure="true">
                <div className="fluxos-project-queue-pressure-head">
                  <span>Queue pressure from watchdog</span>
                  <strong>{builderQueuePressureRows.length} held mission{builderQueuePressureRows.length === 1 ? "" : "s"} · {missionWatchdog?.bad || 0} bad</strong>
                  <p>The current hold is overlap-based, not a runtime crash. Split the objective or wait unless scope safety is marked safe.</p>
                </div>
                <div className="fluxos-project-queue-pressure-list">
                  {builderQueuePressureRows.slice(0, 4).map(item => (
                    <article className={cx("fluxos-project-queue-pressure-row", item.canParallelize ? "safe" : "held")} key={`fluxos-queue-pressure-${item.key}`}>
                      <span>{titleizeToken(item.severity)} · {titleizeToken(item.scopeSafety)} scope</span>
                      <strong>{item.missionTitle}</strong>
                      <p>{item.detail}</p>
                      <p>blocking mission {item.blockingMissionId || "unknown"} · active {item.activeFileCount} files · queued {item.queuedFileCount} files</p>
                      {item.overlapFiles.length > 0 ? <p>overlap files: {item.overlapFiles.join(" · ")}</p> : null}
                      <p>{item.firstRepairStep}</p>
                      {item.canParallelize ? (
                        <button
                          onClick={() => onRequestAction?.("watchdog:parallelize-worktree", { missionId: item.missionId })}
                          type="button"
                        >
                          Parallelize worktree
                        </button>
                      ) : null}
                    </article>
                  ))}
                </div>
              </div>
            ) : isLiveBackend ? (
              <div className="fluxos-project-queue-pressure clear" data-live-builder-queue-pressure="clear">
                <span>Queue pressure from watchdog</span>
                <strong>No live workspace hold reported</strong>
                <p>Builder can use the scheduler row state without a watchdog queue-pressure override.</p>
              </div>
            ) : null}
            {schedulingQueueRows.length > 0 ? (
              <div className="fluxos-project-queue-list">
                {schedulingQueueRows.slice(0, 6).map(item => (
                  <button
                    className={cx("fluxos-project-queue-row", item.safeToLaunch ? "safe" : "held")}
                    data-builder-queue-action="open-workspace"
                    data-builder-queue-state={item.safeToLaunch ? "safe-to-launch" : "held"}
                    data-builder-queue-workspace-id={item.workspaceId || ""}
                    key={`live-builder-queue-${item.workspaceId || item.rank}`}
                    onClick={() => onSelectProject?.(item.workspaceId)}
                    type="button"
                  >
                    <span>#{item.rank} · {titleizeToken(item.state || "watch")} · priority {item.priorityScore || 0} · {item.safeToLaunch ? "actionable" : "held"}</span>
                    <strong>{item.title}</strong>
                    <p>{item.recommendedAction || item.reason || "No live scheduling action recorded."}</p>
                    <p>
                      {item.targetMissionTitle ? `Target: ${item.targetMissionTitle}` : "No target mission"} · {titleizeToken(item.runtime || "hermes")}
                    </p>
                    <div className="fluxos-project-queue-counters">
                      <em>{item.activeCount} active</em>
                      <em>{item.queuedCount} queued</em>
                      <em>{item.blockedCount} blocked</em>
                      <em>{item.completedCount} done</em>
                      <em>{item.relatedHoldCount} related holds</em>
                      <em>{item.safeToLaunch ? "safe to launch" : "hold"}</em>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <p className="fluxos-flow-empty" data-live-builder-queue="missing">
                No live multi-project scheduling queue is available from the NAS summary.
              </p>
            )}
          </section>
        ) : null}
        {isLiveBackend ? (
          <section className="fluxos-gap-radar" aria-label="Provider capability truth">
            <div className="fluxos-section-head">
              <span>Provider capability truth</span>
              <strong>{titleizeToken(selectedProviderCapabilities.status || "route contract pending")}</strong>
            </div>
            <p>
              {`${providerLaneRows.length || selectedProviderCapabilities.laneCount || 0} planner/executor/verifier lanes · `}
              {`${selectedProviderCapabilities.readyLaneCount || 0} ready · ${selectedProviderCapabilities.blockedLaneCount || 0} blocked · `}
              {selectedProviderCapabilities.runtimeId || selectedMissionRow.runtimeId || "runtime"}
            </p>
            <p>
              {`${asList(selectedProviderCapabilities.toolSummary?.families).slice(0, 6).join(", ") || "tool families pending"} · `}
              {`${selectedProviderCapabilities.quotaSummary?.reportedProviders || 0} quota reports · `}
              {`${selectedProviderCapabilities.quotaSummary?.unreportedProviders || 0} unreported`}
            </p>
            <div className="fluxos-provider-admission-truth" data-provider-admission-truth="true">
              <span>Admission vs quota</span>
              <strong>Auth decides whether the runtime can launch; quota is separate live usage evidence.</strong>
              <p>
                Quota unreported means the live Hermes control room has no quota or rate-window report for that provider.
                It is not a provider-limit or exhausted-usage claim.
              </p>
            </div>
            <div className="fluxos-provider-route-decision" data-task-fit-route-decision="true">
              <div>
                <span>Task-fit route decision</span>
                <strong>Planner, executor, verifier, and harness are separate live lanes.</strong>
                <p>Hermes supervises durable work; Codex 5.5 high handles planning and verification; MiniMax is used only when the executor lane is authenticated for frontend work.</p>
              </div>
              {selectedRouteDecisionRows.map((item, index) => (
                <article key={`provider-route-decision-${item.role || index}`}>
                  <span>{titleizeToken(item.role || item.label || "Lane")}</span>
                  <strong>{`${item.provider || item.runtime || "provider"} / ${item.model || "model"}`}</strong>
                  <p>{`${titleizeToken(item.effort || item.status || "high")} · ${item.reason || item.lastEvent || item.blocker || "Live route lane returned no current reason."}`}</p>
                </article>
              ))}
            </div>
            <div className="fluxos-gap-radar-grid">
              {providerCapabilityRows.length > 0 ? providerCapabilityRows.slice(0, 4).map(item => (
                <article className={item.health === "blocked" ? "warn" : "good"} key={`provider-capability-${item.provider}`}>
                  <span>{asList(item.roles).join(" / ") || "route"}</span>
                  <strong>{`${titleizeToken(item.provider || "provider")} · ${item.authPresent ? "Authenticated" : "Auth missing"}`}</strong>
                  <p>
                    {`${asList(item.models).join(", ") || "model unresolved"} · ${item.authPath || "not configured"}`}
                    {asList(item.blockers).length ? ` · ${asList(item.blockers)[0]}` : ""}
                  </p>
                  <p>
                    {`Quota ${titleizeToken(item.quota?.status || "unknown")} · `}
                    {asList(item.toolFamilies).slice(0, 4).join(", ") || "tools unreported"}
                    {asList(item.failureClasses).length ? ` · ${asList(item.failureClasses).join(", ")}` : ""}
                  </p>
                </article>
              )) : (
                <article className="warn">
                  <span>Live route contract</span>
                  <strong>No provider lanes resolved yet</strong>
                  <p>{selectedProviderCapabilities.nextAction || "Resolve the mission route contract before dispatching provider work."}</p>
                </article>
              )}
            </div>
          </section>
        ) : null}
        {liveAdvancementRows.length > 0 && !builderFocusMode ? (
          <section className="fluxos-gap-radar" aria-label="Live mission advancement">
            <div className="fluxos-section-head">
              <span>Live mission advancement</span>
              <strong>{liveAdvancementRows.length} active project{liveAdvancementRows.length === 1 ? "" : "s"}</strong>
            </div>
            <div className="fluxos-gap-radar-grid">
              {liveAdvancementRows.map(row => {
                const width = progressWidth(row.progress);
                return (
                  <article className={isBlockedBuilderRow(row) ? "warn" : "good"} key={`advancement-${row.id || row.name}`}>
                    <span>
                      {row.runtimeId || "runtime"} · {row.delegatedLaneCount || 0} lane{Number(row.delegatedLaneCount || 0) === 1 ? "" : "s"} · {row.artifactStatus || "artifact pending"}
                    </span>
                    <strong>{row.name}</strong>
                    <p>
                      {row.progress || "No numeric progress"} · {row.progressLabel || row.status}
                      {row.progressNextAction ? ` · ${row.progressNextAction}` : ""}
                    </p>
                    {width ? (
                      <div className="reference-success-track" aria-label={`${row.name} progress ${row.progress}`}>
                        <span style={{ width }} />
                      </div>
                    ) : null}
                    {row.artifactNextAction ? <p>{row.artifactNextAction}</p> : null}
                  </article>
                );
              })}
            </div>
          </section>
        ) : null}
        {systemAuditDigest?.schema && !builderFocusMode ? (
          <section className="fluxos-gap-radar" aria-label="T3 gap radar">
            <div className="fluxos-section-head">
              <span>T3 gap radar</span>
              <strong>
                {`${systemAuditDigest.systemScoreOutOf20 ?? "--"}/20 · ${systemAuditDigest.mustBeatStatus?.ahead ?? 0}/${systemAuditDigest.mustBeatStatus?.total ?? 7} categories ahead`}
              </strong>
            </div>
            <p>
              {`${systemAuditDigest.operatorConfidenceScore ?? 0}/100 operator confidence · `}
              {`${systemAuditDigest.missingOperatorValueSamples ?? 0} value samples missing · `}
              {systemAuditDigest.source || "control-room digest"}
            </p>
            <p>{systemAuditDigest.scoreCapReason || "Scores stay capped until live route trust is value-scored."}</p>
            <div className="fluxos-t3-repair-plan" aria-label="T3 parity repair plan">
              <div className="fluxos-t3-repair-plan-head">
                <span>T3 parity repair plan</span>
                <strong>{`${t3AheadCount}/${t3TotalCount || 7} ahead · ${t3DeficitCount} to beat`}</strong>
                <p>{systemAuditDigest.t3Reference?.latestObservedRelease || "Latest T3 release evidence is not loaded."}</p>
              </div>
              <div className="fluxos-t3-repair-plan-list">
                {t3RepairRows.length > 0 ? t3RepairRows.map(item => (
                  <button
                    className={item.delta < 0 ? "bad" : "warn"}
                    key={`t3-repair-${item.id}`}
                    onClick={() => onRequestAction?.("t3-repair:open", { item: item.raw })}
                    type="button"
                  >
                    <span>{`${item.lane} · priority ${item.priority}`}</span>
                    <strong>{item.category}</strong>
                    <p>{item.nextAction}</p>
                    <em>
                      {Number.isFinite(item.delta)
                        ? `Delta ${item.delta >= 0 ? "+" : ""}${item.delta}`
                        : "Needs scoring"}
                      {item.fluxioScore || item.t3Score ? ` · Fluxio ${item.fluxioScore ?? "--"}/20 · T3 ${item.t3Score ?? "--"}/20` : ""}
                    </em>
                  </button>
                )) : (
                  <article>
                    <span>T3 parity</span>
                    <strong>No tracked T3 deficits loaded</strong>
                    <p>{systemAuditDigest.nextAction || "Keep live route-trust and public launch evidence current."}</p>
                  </article>
                )}
              </div>
            </div>
            {systemLossBreakdown?.schema ? (
              <div
                className="fluxos-system-loss"
                aria-label="System gap breakdown"
                data-system-loss-current="true"
              >
                <div>
                  <span>System gap</span>
                  <strong>{systemLossHeadline}</strong>
                  <p>{systemLossSubline}</p>
                </div>
                <div className="fluxos-system-loss-drivers">
                  {systemLossDriverRows.map(item => (
                    <article key={item.id}>
                      <span>{`${item.lane} · gap ${item.loss}`}</span>
                      <strong>{item.title}</strong>
                      <p>{item.detail}</p>
                      {item.nextAction ? <em>{item.nextAction}</em> : null}
                    </article>
                  ))}
                </div>
              </div>
            ) : null}
            {storageTriageSummary?.schema ? (
              <div
                className="fluxos-storage-triage"
                aria-label="NAS storage triage"
                data-storage-triage-summary="true"
              >
                <div>
                  <span>Storage triage</span>
                  <strong>
                    {`${storageTriageSummary.usedPercent || nasStorageUsedPercent || 0}% used · ${storageTriageSummary.generatedCandidateCount || 0} generated cleanup`}
                  </strong>
                  <p>
                    {storageTriageSummary.largestAccountedPath
                      ? `${storageTriageSummary.largestAccountedPath} accounts for ${storageTriageSummary.largestAccountedGB || 0} GB in bounded probes.`
                      : storageTriageSummary.nextAction || "Storage triage is grounded in live NAS probes."}
                  </p>
                </div>
                <div className="fluxos-storage-triage-grid">
                  {storageTriageRows.slice(0, 5).map(item => (
                    <article className={item.severity || "medium"} key={item.id || item.title}>
                      <span>{`${titleizeToken(item.kind || "probe")} · ${item.safeToDelete ? "allowlisted" : "operator review"}`}</span>
                      <strong>{item.title || "Storage probe"}</strong>
                      <p>{item.detail || item.nextAction || "No detail recorded."}</p>
                      {item.nextAction ? <em>{item.nextAction}</em> : null}
                    </article>
                  ))}
                </div>
                {storageOperatorHandoff?.schema ? (
                  <div className="fluxos-storage-handoff compact" data-storage-operator-handoff="true">
                    <span>Operator handoff</span>
                    <strong>{storageOperatorHandoff.summary}</strong>
                    <code>{storageOperatorHandoff.primaryCommand || "npm run plan:nas-storage-cleanup"}</code>
                  </div>
                ) : null}
              </div>
            ) : null}
            {deploymentDurabilitySummary?.schema ? (
              <div
                className="fluxos-storage-triage"
                aria-label="Deployment durability"
                data-deployment-durability-summary="true"
              >
                <div>
                  <span>Deployment durability</span>
                  <strong>{deploymentDurabilitySummary.headline || titleizeToken(deploymentDurabilitySummary.status || "unknown")}</strong>
                  <p>
                    {deploymentTemporaryCount
                      ? `${deploymentTemporaryCount} live path${deploymentTemporaryCount === 1 ? "" : "s"} point into /tmp; release claims stay capped until durable files replace them.`
                      : deploymentDurabilitySummary.nextAction || "Deployment durability is checked from active release paths."}
                  </p>
                </div>
                <div className="fluxos-storage-triage-grid">
                  {asList(deploymentDurabilitySummary.checkedPaths).slice(0, 4).map(item => (
                    <article className={item.severity || "medium"} key={item.path || item.target}>
                      <span>{item.temporaryTarget ? "temporary recovery" : "symlink"}</span>
                      <strong>{item.path || "Release path"}</strong>
                      <p>{item.target || "No symlink target recorded."}</p>
                      <em>{item.detail || deploymentDurabilitySummary.nextAction}</em>
                    </article>
                  ))}
                </div>
              </div>
            ) : null}
            {designDebtSummary?.schema ? (
              <div
                className="fluxos-design-debt"
                aria-label="Design and operator experience debt"
                data-design-debt-summary="true"
              >
                <div>
                  <span>Design debt</span>
                  <strong>{designDebtSummary.headline || "Operator experience debt is being tracked."}</strong>
                  <p>
                    {`Interface ${designDebtSummary.interfaceScoreOutOf20 || "--"}/20 · launch ${designDebtSummary.launchScoreOutOf20 || "--"}/20 · ${designDebtSummary.repairMissionCount || 0} repair mission${Number(designDebtSummary.repairMissionCount || 0) === 1 ? "" : "s"}`}
                  </p>
                </div>
                <div className="fluxos-design-debt-grid">
                  {designDebtRows.slice(0, 4).map(item => (
                    <article className={item.severity || "medium"} key={item.id || item.title}>
                      <span>{titleizeToken(item.status || item.severity || "open")}</span>
                      <strong>{item.title || "Design debt"}</strong>
                      <p>{item.detail || item.nextAction || "Keep the UI tied to live proof."}</p>
                      {item.nextAction ? <em>{item.nextAction}</em> : null}
                    </article>
                  ))}
                </div>
              </div>
            ) : null}
            {missionAdvancementSummary?.schema ? (
              <div
                className="fluxos-mission-advancement"
                aria-label="Live mission advancement"
                data-mission-advancement-summary="true"
              >
                <div>
                  <span>Mission advancement</span>
                  <strong>
                    {`${missionAdvancementSummary.realOutputMissionCount || 0} real-output · ${missionAdvancementSummary.repairMissionCount || 0} repair`}
                  </strong>
                  <p>{missionAdvancementSummary.nextAction || "Keep mission rows grounded in live runtime output."}</p>
                </div>
                <div className="fluxos-mission-advancement-grid">
                  {missionProofAdvancementRows.slice(0, 4).map(item => (
                    <article className={item.health || "unknown"} key={item.missionId || item.title}>
                      <span>{`${item.runtime || "runtime"} · ${titleizeToken(item.status || "unknown")}`}</span>
                      <strong>{item.title || item.missionId}</strong>
                      <p>
                        {`${titleizeToken(item.health || "unknown")} · ${item.agentMessageCount || 0} messages · ${item.runtimeOutputCount || 0} outputs`}
                      </p>
                      <em>
                        {item.proofStateLabel ||
                          (item.evidenceScreenshotPath
                            ? "screenshot proof attached"
                            : "runtime proof state not attached")}
                      </em>
                    </article>
                  ))}
                </div>
              </div>
            ) : null}
            {systemAuditDigest.redTeamEscalation?.historyRows ? (
              <p>
                {`Red-team escalation: ${systemAuditDigest.redTeamEscalation.historyRows} rows · `}
                {`${systemAuditDigest.redTeamEscalation.latestResistanceScore || 0} resistance · `}
                {`next ${systemAuditDigest.redTeamEscalation.nextAttemptBudget || 0} attempts`}
              </p>
            ) : null}
            {systemAuditDigest.watchdogSelfImprovement?.schema ? (
              <div className="fluxos-watchdog-trend" aria-label="Watchdog self-improvement trend">
                <div>
                  <span>Watchdog self-improvement</span>
                  <strong>
                    {`${systemAuditDigest.watchdogSelfImprovement.historyRows || 0} receipts · `}
                    {`${systemAuditDigest.watchdogSelfImprovement.completedReceipts || 0} completed`}
                  </strong>
                  <p>
                    {systemAuditDigest.watchdogSelfImprovement.trendReady
                      ? "Cadence trend is ready for release proof."
                      : systemAuditDigest.watchdogSelfImprovement.nextAction}
                  </p>
                </div>
                <div className="fluxos-watchdog-trend-metrics">
                  <em>{`Latest ${systemAuditDigest.watchdogSelfImprovement.latestStatus || "missing"}`}</em>
                  <em>{`History #${systemAuditDigest.watchdogSelfImprovement.latestHistoryIndex || 0}`}</em>
                  <em>{`Next ${systemAuditDigest.watchdogSelfImprovement.nextAttemptBudget || 0} attempts`}</em>
                </div>
                {asList(systemAuditDigest.watchdogSelfImprovement.recentReceipts).length > 0 ? (
                  <div className="fluxos-watchdog-receipts" aria-label="Recent watchdog self-improvement receipts">
                    {asList(systemAuditDigest.watchdogSelfImprovement.recentReceipts).slice(-3).map(item => (
                      <article key={`watchdog-receipt-${item.historyIndex}-${item.generatedAt}`}>
                        <span>{`#${item.historyIndex || 0} · ${titleizeToken(item.status || "unknown")}`}</span>
                        <strong>{`${item.completedSteps || 0} step${item.completedSteps === 1 ? "" : "s"}`}</strong>
                        <p>{item.generatedAt || "No timestamp recorded"}</p>
                      </article>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
            <div className="fluxos-gap-radar-grid">
              {asList(systemAuditDigest.deficits).length > 0 ? (
                asList(systemAuditDigest.deficits).slice(0, 4).map(item => (
                  <article className={item.delta < 0 ? "bad" : "warn"} key={item.category}>
                    <span>{`Fluxio ${item.fluxioScore}/20 · T3 ${item.t3Score}/20`}</span>
                    <strong>{item.category}</strong>
                    <p>{item.nextAction}</p>
                  </article>
                ))
              ) : (
                <article className="good">
                  <span>T3 comparison</span>
                  <strong>All tracked categories are ahead.</strong>
                  <p>{systemAuditDigest.nextAction}</p>
                </article>
              )}
              {asList(systemAuditDigest.badFirst).slice(0, 3).map(item => (
                <article className="warn" key={`bad-first-${item.title || item.detail}`}>
                  <span>Still weak</span>
                  <strong>{item.title || "Current gap"}</strong>
                  <p>{item.detail}</p>
                </article>
              ))}
            </div>
            {asList(systemAuditDigest.improvementQueue).length > 0 ? (
              <div className="fluxos-improvement-queue" aria-label="System improvement queue">
                <span>System improvement queue</span>
                {asList(systemAuditDigest.improvementQueue).slice(0, 5).map(item => (
                  <button
                    key={item.id || item.title}
                    onClick={() => onRequestAction?.("system-improvement:open", { item })}
                    type="button"
                  >
                    <strong>{item.title}</strong>
                    <em>{`${item.lane || "System"} · ${item.status || "open"} · priority ${item.priority || 0}`}</em>
                    <p>{item.nextAction || item.detail}</p>
                  </button>
                ))}
              </div>
            ) : null}
            <div className="fluxos-gap-radar-strengths" aria-label="T3 strengths to beat">
              <span>T3 strengths to beat</span>
              {asList(systemAuditDigest.t3Reference?.strengthsToBeat).slice(0, 5).map(item => (
                <em key={`t3-strength-${item}`}>{item}</em>
              ))}
            </div>
            {asList(systemAuditDigest.activeGapMissions).length > 0 ? (
              <div className="fluxos-gap-mission-strip" aria-label="Active missions addressing system gaps">
                <span>Active gap missions</span>
                {asList(systemAuditDigest.activeGapMissions).slice(0, 4).map(item => (
                  <button
                    key={item.missionId || item.title}
                    onClick={() => onOpenBuilderDetail?.(item.missionId)}
                    type="button"
                  >
                    <strong>{item.title || item.missionId}</strong>
                    <em>{`${item.gapSignal || "Route-trust sampling"} · ${item.status || "status unknown"}`}</em>
                  </button>
                ))}
              </div>
            ) : null}
          </section>
        ) : null}
        {publicLaunchReadiness.status ? (
          <section
            className="fluxos-gap-radar fluxos-public-launch-proof-path"
            aria-label={publicLaunchReadiness.ok ? "Live public launch proof" : "Live public launch blocker"}
            data-public-launch-proof-path="true"
            data-public-launch-ready={publicLaunchReadiness.ok ? "true" : "false"}
          >
            <div className="fluxos-section-head">
              <span>{publicLaunchReadiness.ok ? "Live public launch proof" : "Live public launch blocker"}</span>
              <strong>{titleizeToken(publicLaunchReadiness.status)}</strong>
            </div>
            <p>
              {publicLaunchReadiness.nextAction ||
                (publicLaunchReadiness.ok
                  ? "Public launch is proven by current public web, release packet, and external publication receipts."
                  : "Public launch is not proven until current web and external publication evidence are present.")}
            </p>
            <div className="fluxos-public-launch-steps" aria-label="Public launch proof path">
              {publicLaunchSteps.map((step, index) => (
                <article className={step.tone} data-public-launch-proof-step={step.id} key={`public-launch-step-${step.id}`}>
                  <span>{`0${index + 1} · ${step.state}`}</span>
                  <strong>{step.label}</strong>
                  <p>{step.detail}</p>
                  <em>{step.checks.length ? `${step.checks.filter(item => item.passed).length}/${step.checkIds.length} checks passed` : "No live check rows"}</em>
                </article>
              ))}
            </div>
            {publicLaunchRepairPacket?.schema ? (
              <div className="fluxos-improvement-queue" aria-label="Public launch repair packet" data-public-launch-repair-packet="true">
                <span>
                  Launch repair packet / proof · {publicLaunchRepairPacket.canClaimPublicLaunch ? "public launch proven" : "cannot claim public launch"}
                </span>
                <button type="button">
                  <strong>{titleizeToken(publicLaunchRepairPacket.primaryBlocker || publicLaunchReadiness.status || "Launch state")}</strong>
                  <em>
                    {`${publicLaunchRepairPacket.sourceCoverage || "source coverage unknown"} · ${publicLaunchRepairPacket.releaseBlockingPathCount ?? publicLaunchRepairPacket.releaseBlockingSampleCount ?? 0} release-impacting paths`}
                  </em>
                </button>
                <button type="button">
                  <strong>Next publish action</strong>
                  <em>{publicLaunchRepairPacket.nextAction || publicLaunchReadiness.nextAction}</em>
                </button>
                <button type="button">
                  <strong>Verifier command</strong>
                  <em>
                    {asList(publicLaunchRepairPacket.commands)[0]?.command ||
                      publicLaunchRepairPacket.stagingPlan?.verifyCommand ||
                      "npm run verify:public-launch"}
                  </em>
                </button>
                <button type="button">
                  <strong>Receipt targets</strong>
                  <em>
                    {asList(publicLaunchRepairPacket.receiptTargets)[0]?.path ||
                      publicLaunchReadiness.stagingProof?.evidencePath ||
                      ".agent_control/public_launch_readiness/latest.json"}
                  </em>
                </button>
                {asList(publicLaunchRepairPacket.orderedLanes).slice(0, 5).map(item => (
                  <button key={`public-launch-repair-lane-${item.lane}`} type="button">
                    <strong>{`${titleizeToken(item.lane || "lane")} · ${item.count || 0}`}</strong>
                    <em>{item.nextAction}</em>
                  </button>
                ))}
                {publicLaunchRepairPacket.stagingPlan?.schema ? (
                  <button data-public-launch-staging-plan="true" type="button">
                    <strong>{`Release staging plan · ${publicLaunchRepairPacket.stagingPlan.releaseImpactPathCount || 0} release paths`}</strong>
                    <em>{publicLaunchRepairPacket.stagingPlan.nextAction}</em>
                  </button>
                ) : null}
                {publicLaunchReadiness.stagingProof?.schema ? (
                  <button data-public-launch-staging-proof="true" type="button">
                    <strong>{`Staging proof archived · ${publicLaunchReadiness.stagingProof.releaseImpactPathCount || 0} release paths`}</strong>
                    <em>{publicLaunchReadiness.stagingProof.evidencePath || publicLaunchReadiness.stagingProof.nextAction}</em>
                  </button>
                ) : null}
                {asList(publicLaunchRepairPacket.stagingPlan?.groups).slice(0, 4).map(item => (
                  <button key={`public-launch-staging-group-${item.lane}`} type="button">
                    <strong>{`git add ${titleizeToken(item.lane || "lane")} · ${item.pathCount || 0}`}</strong>
                    <em>{item.command}</em>
                  </button>
                ))}
                {asList(publicLaunchRepairPacket.commands).slice(0, 4).map(item => (
                  <button key={`public-launch-repair-command-${item.label}`} type="button">
                    <strong>{item.label}</strong>
                    <em>{item.command}</em>
                  </button>
                ))}
                {asList(publicLaunchRepairPacket.receiptTargets).slice(0, 3).map(item => (
                  <button key={`public-launch-repair-receipt-${item.path}`} type="button">
                    <strong>{item.label}</strong>
                    <em>{item.path}</em>
                  </button>
                ))}
              </div>
            ) : null}
            <div className="fluxos-gap-radar-grid">
              {asList(publicLaunchReadiness.missing).map(item => (
                <article className="warn" key={`public-launch-missing-${item}`}>
                  <span>Missing proof</span>
                  <strong>{item}</strong>
                  <p>Required by the live NAS public-launch readiness verifier.</p>
                </article>
              ))}
              {asList(publicLaunchReadiness.blockers).slice(0, 3).map(item => (
                <article className="warn" key={`public-launch-blocker-${item.checkId || item.id || item.title}`}>
                  <span>{item.checkId || item.id || "Blocker"}</span>
                  <strong>{item.title || item.label || titleizeToken(item.status || "Needs proof")}</strong>
                  <p>{item.details || item.detail || item.nextAction || item.reason || "Verifier requires current public evidence."}</p>
                </article>
              ))}
            </div>
            {publicLaunchReadiness.publicWeb?.dirtySourceTriage?.schema || asList(publicLaunchReadiness.publicWeb?.sourceDirtyPathSample).length > 0 ? (
              <div className="fluxos-improvement-queue" aria-label="Public web dirty source sample">
                <span>
                  Dirty source sample · {publicLaunchReadiness.publicWeb?.sourceDirtyPathCount || 0} paths
                </span>
                {publicLaunchReadiness.publicWeb?.dirtySourceTriage?.schema ? (
                  <button data-public-launch-dirty-source-triage="true" type="button">
                    <strong>
                      {`${publicLaunchReadiness.publicWeb.dirtySourceTriage.releaseBlockingSampleCount || 0} release-impacting sample paths`}
                    </strong>
                    <em>{publicLaunchReadiness.publicWeb.dirtySourceTriage.nextAction}</em>
                  </button>
                ) : null}
                {asList(publicLaunchReadiness.publicWeb?.sourceDirtyPathSample).slice(0, 8).map(item => (
                  <button key={`public-web-dirty-${item}`} type="button">
                    <strong>{item}</strong>
                    <em>Must be committed, published, or intentionally excluded before current public-web proof can pass.</em>
                  </button>
                ))}
              </div>
            ) : null}
            {publicLaunchReadiness.publicationProof?.nextAction ? (
              <p>
                Publication proof: {publicLaunchReadiness.publicationProof.nextAction} Expected receipt:{" "}
                {publicLaunchReadiness.publicationProof.npmReceiptPath ||
                  publicLaunchReadiness.publicationProof.signedInstallerReceiptPath ||
                  ".agent_control/publication/*"}
              </p>
            ) : null}
          </section>
        ) : null}
        {isLiveBackend && (selectedMissionId || workbenchState?.missionTitle) ? (
          <section className="fluxos-selected-agent-preview" aria-label="Selected Agent live thread preview">
            <div>
              <span>Selected Agent thread</span>
              <strong>{workbenchState?.missionTitle || selectedMissionRow?.name || selectedMissionRow?.title || "Live mission"}</strong>
              <p>{workbenchState?.progress?.nextAction || selectedMissionRow?.turningPoint || "Open Agent for the full live transcript and runtime trace."}</p>
            </div>
            {selectedProgressValue == null ? (
              <em>No live percentage returned</em>
            ) : (
              <i
                aria-label={`${workbenchState?.progress?.label || "Selected mission progress"} ${selectedProgressValue}%`}
                style={{ "--progress": `${selectedProgressValue}%` }}
              />
            )}
            <div className="fluxos-selected-agent-events">
              {selectedThreadRows.length > 0 ? selectedThreadRows.map(item => (
                <article key={item.id || item.label || item.timestamp} data-mission-id={item.missionId || workbenchState?.missionId || ""}>
                  <span>{timestampLabel(item.timestamp) || titleizeToken(item.status || "live")}</span>
                  <strong>{agentPreviewTitle(item)}</strong>
                  <p>{agentPreviewDetail(item)}</p>
                </article>
              )) : (
                <article>
                  <span>Live detail</span>
                  <strong>Open Agent for current messages</strong>
                </article>
              )}
            </div>
            <button disabled={!selectedMissionId} onClick={() => onOpenBuilderDetail?.(selectedMissionId)} type="button">Open Agent thread</button>
          </section>
        ) : null}
        <section className="fluxos-flow-board">
          {rows.length > 0 ? rows.map((row, index) => {
            const tuple = Array.isArray(row)
              ? row
              : [row.title || row.name || "Workspace flow", row.kind || row.status || "run", row.status || "active", row.progress];
            const width = progressWidth(tuple[3]);
            const progressLabel = row?.progressLabel || (row?.displayAsCompletion === false ? "Non-completion progress" : "");
            const progressKind = row?.progressKind || (row?.displayAsCompletion === false ? "non_completion_progress" : "");
            return (
              <button
                className={cx("fluxos-flow-card", isLiveBackend && "live-row", ["proof_repair", "runtime_budget_exhausted"].includes(progressKind) && "proof-repair")}
                data-progress-kind={progressKind || undefined}
                key={`${tuple[0]}-${index}`}
                onClick={() => onSelectFlow?.(row?.id || tuple[0])}
                type="button"
              >
                <span>{tuple[1]}</span>
                <strong>{tuple[0]}</strong>
                <p>{progressLabel ? `${tuple[2]} · ${progressLabel}` : tuple[2]}</p>
                {width ? (
                  <div aria-label={`${progressLabel || "Live progress"} ${width}`}><i style={{ width }} /></div>
                ) : isLiveBackend ? (
                  <small className="fluxos-live-progress-missing">No numeric progress returned by NAS</small>
                ) : (
                  <div><i style={{ width: `${70 + index * 3}%` }} /></div>
                )}
              </button>
            );
          }) : (
            <article className="fluxos-flow-empty">
              <span>{liveLoading ? "Connecting to NAS" : "Waiting for NAS data"}</span>
              <strong>{liveLoading ? "Loading live mission rows" : "No live mission rows loaded yet"}</strong>
              <p>{liveLoading ? "The Builder surface is waiting for the authenticated control-room summary and is not showing cached or sample missions." : "Refresh the control room or sign in again; fixture flow cards are hidden in live mode."}</p>
            </article>
          )}
        </section>
        <section className="fluxos-context-roots" aria-label="Mission context roots">
          <div className="fluxos-section-head">
            <span>Mission context roots</span>
            <strong>
              {selectedContext?.counts?.totalRoots || missionContextRoots.length || 0} visible root{(selectedContext?.counts?.totalRoots || missionContextRoots.length || 0) === 1 ? "" : "s"}
            </strong>
          </div>
          <p>{selectedContext?.recommendedAction || "Live missions show primary root, execution root, sync mirrors, and related project roots before cross-project edits."}</p>
          <div className="fluxos-context-root-grid">
            {missionContextRoots.length > 0 ? (
              missionContextRoots.map((root, index) => (
                <button
                  className={cx("fluxos-context-root", root.blockedMissionCount > 0 && "warn", root.currentMission && "active")}
                  key={root.rootId || `${root.workspaceId}-${root.role}-${index}`}
                  onClick={() => onSelectProject?.(root.workspaceId || root.rootPath || root.rootId)}
                  type="button"
                >
                  <span>{titleizeToken(root.role)} · {root.writableByMission ? "writable" : "read-only"}</span>
                  <strong>{root.folderLabel || root.workspaceName || "Root"}</strong>
                  <p>{root.rootPath || "No path recorded."}</p>
                </button>
              ))
            ) : (
              <article className="fluxos-context-root empty">
                <span>Awaiting live mission</span>
                <strong>No context roots in this preview</strong>
                <p>Open a live mission snapshot to inspect write scope and related projects.</p>
              </article>
            )}
          </div>
        </section>
      </section>

      <section className="fluxos-pipeline">
        <div className="fluxos-section-head">
          <span>Execution pipeline</span>
          <strong>Preview to merge</strong>
        </div>
        {(isLiveBackend ? ["NAS summary loaded", "Mission rows mapped", "Notifications attached", "Slice events visible", "Proof ready", "Operator review"] : ["Plan accepted", "Files changed", "Visual review", "Tests", "Approval", "Merge"]).map((step, index) => (
          <button className={index < 3 ? "complete" : index === 3 ? "active" : ""} key={step} onClick={() => fluxioAction(onRequestAction, `builder:pipeline:${step}`)} type="button">
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{step}</strong>
          </button>
        ))}
      </section>

      <section className="fluxos-review-bundle">
        <div className="fluxos-section-head">
          <span>Review bundle</span>
          <strong>Changes ready for inspection</strong>
        </div>
        {changes.length > 0 ? changes.map((item, index) => {
          const tuple = Array.isArray(item)
            ? item
            : changedItemTuple(item);
          return (
            <article key={`${tuple[0]}-${index}`}>
              <Code2 size={16} strokeWidth={1.8} />
              <div>
                <strong>{tuple[0]}</strong>
                <p>{tuple[1]}</p>
              </div>
              <span>{tuple[2]}</span>
            </article>
          );
        }) : (
          <article>
            <Code2 size={16} strokeWidth={1.8} />
            <div>
              <strong>No file-level change rows in the live summary</strong>
              <p>Open a mission detail or proof digest for file-level evidence.</p>
            </div>
            <span>live</span>
          </article>
        )}
        <div className="fluxos-review-actions">
          <button disabled={!selectedMissionId} onClick={() => onOpenBuilderDetail?.(selectedMissionId)} type="button">Open in Agent</button>
          <button className="primary" onClick={() => onSelectProject?.("current")} type="button">Publish check</button>
        </div>
        <div className="fluxos-builder-proof-grid">
          <article>
            <span>Project health</span>
            <strong>{projectHealthRows.length} supervised project{projectHealthRows.length === 1 ? "" : "s"}</strong>
            {projectHealthRows.slice(0, 3).map(item => (
              <button className={cx("fluxos-proof-row", item.blockedCount > 0 && "warn")} key={item.id} onClick={() => onSelectProject?.(item.id)} type="button">
                <span>{item.activeCount} active · {item.blockedCount} blocked</span>
                <strong>{item.title}</strong>
                <p>{item.detail}</p>
              </button>
            ))}
          </article>
          <article>
            <span>Sub-agent lanes</span>
            <strong>{projectHealthRows.reduce((total, item) => total + item.laneCount, 0)} planner/executor/verifier lane{projectHealthRows.reduce((total, item) => total + item.laneCount, 0) === 1 ? "" : "s"}</strong>
            <p>Delegated Hermes lane counts are carried from the live mission rows instead of hidden in logs. Compatibility lanes are shown only when a live row names them.</p>
          </article>
        </div>
        {isLiveBackend && proofDiffRows.length === 0 ? (
          <section className="proof-side-by-side-diff empty-live" aria-label="Supervisor proof state">
            <div className="proof-side-by-side-head">
              <div>
                <span>Supervisor evidence</span>
                <strong>No live proof diff rows returned</strong>
                <p>The Builder surface is not inventing proof rows. Open the Agent detail when the mission has emitted review evidence.</p>
              </div>
            </div>
          </section>
        ) : (
        <section className={cx("proof-side-by-side-diff", proofDiffWrap ? "wrap" : "no-wrap")} aria-label="Side-by-side proof diff with wrap toggle">
          <div className="proof-side-by-side-head">
            <div>
              <span>Supervisor evidence</span>
              <strong>Side-by-side proof diff</strong>
              <p>{visibleProofDiffRows.length} of {proofDiffRows.length} rows · {workbenchState?.proofDiff?.source || "live mission proof drawer"}</p>
            </div>
            <button onClick={() => setProofDiffWrap(current => !current)} type="button">
              {proofDiffWrap ? "Disable wrap" : "Enable wrap"}
            </button>
          </div>
          <div className="proof-diff-table" role="table" aria-label="Expected proof versus captured evidence">
            <div className="proof-diff-row header" role="row">
              <span role="columnheader">Expectation</span>
              <span role="columnheader">Captured evidence</span>
              <span role="columnheader">State</span>
            </div>
            {visibleProofDiffRows.length > 0 ? visibleProofDiffRows.map(row => (
              <div className={cx("proof-diff-row", row.tone === "warn" && "warn")} key={row.id} role="row">
                <span role="cell"><small>{row.category}</small>{row.expected}</span>
                <span role="cell">{row.captured}</span>
                <span role="cell">{row.status}</span>
              </div>
            )) : (
              <div className="proof-diff-row warn" role="row">
                <span role="cell">Mission output or review artifact</span>
                <span role="cell">No proof rows are attached to this Builder snapshot yet.</span>
                <span role="cell">Missing</span>
              </div>
            )}
          </div>
          {proofDiffRows.length > proofDiffVisibleCount ? (
            <button className="proof-list-more" onClick={() => setProofDiffVisibleCount(count => count + 12)} type="button">
              Show more diff evidence
            </button>
          ) : null}
        </section>
        )}
      </section>
    </div>
  );
}

const FLUXIO_SKILL_DRAFTS_KEY = "fluxio.skills.drafts";

function loadFluxioSkillDrafts() {
  if (typeof window === "undefined") return {};
  try {
    const parsed = JSON.parse(window.localStorage?.getItem(FLUXIO_SKILL_DRAFTS_KEY) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function skillLibraryKey(item, index = 0) {
  return String(item?.id || item?.skillId || item?.name || item?.label || `skill-${index}`).trim();
}

function skillLibraryTitle(item) {
  return String(item?.name || item?.label || item?.id || item?.skillId || "Untitled skill").trim();
}

function skillLibraryBody(item) {
  const value = [
    item?.instructions,
    item?.body,
    item?.content,
    item?.summary,
    item?.description,
  ].find(candidate => String(candidate || "").trim());
  return String(value || "Write or paste this skill's instructions here.").trim();
}

function FluxioSkillsSurface({ onRequestAction, studioState, skillStudioState, surface }) {
  const effectiveStudioState = studioState || skillStudioState || {};
  const [skillsClarityMode, setSkillsClarityMode] = useState(() => {
    if (typeof window === "undefined") return "focus";
    return window.localStorage?.getItem("fluxio.skills.clarityMode") || "focus";
  });
  const normalizedSkillsClarityMode = skillsClarityMode === "full" ? "full" : "focus";
  const skillsFocusMode = effectiveStudioState?.liveReady && normalizedSkillsClarityMode === "focus";
  const setLiveSkillsClarityMode = mode => {
    const nextMode = mode === "full" ? "full" : "focus";
    setSkillsClarityMode(nextMode);
    if (typeof window !== "undefined") {
      window.localStorage?.setItem("fluxio.skills.clarityMode", nextMode);
    }
  };
  const ruleSets = asList(effectiveStudioState?.ruleSets).slice(0, 4);
  const isRuleSets = surface === "rule-sets";
  const feedbackLoop = effectiveStudioState?.feedbackLoop || {};
  const runtimeContract = effectiveStudioState?.runtimeContract || {};
  const runtimeContractSkills = asList(runtimeContract?.skills).slice(0, 4);
  const runtimeContractReady = runtimeContract?.schema === "fluxio.skill_runtime_contract.v1";
  const routing = feedbackLoop.systemLossRouting || {};
  const latestFeedback = asList(feedbackLoop.latest).slice(0, 3);
  const repairProposals = asList(feedbackLoop.repairProposals).slice(0, 3);
  const measuredSkillCount = Number(feedbackLoop.measuredSkillCount || 0);
  const repairCount = Number(feedbackLoop.repairCount || 0);
  const reinforceCount = Number(feedbackLoop.reinforceCount || 0);
  const heldSkillCount = asList(routing.activeRepairSkillIds).length;
  const liveSkillRegistryReady = Boolean(
    effectiveStudioState?.liveReady &&
      (asList(effectiveStudioState?.skills).length > 0 ||
        Number(effectiveStudioState?.totals?.totalSkills || 0) > 0 ||
        measuredSkillCount > 0),
  );
  const liveSkills = asList(effectiveStudioState?.skills)
    .filter(item => {
      if (!effectiveStudioState?.liveReady) {
        return false;
      }
      const status = String(item?.status || item?.promotionState || "").toLowerCase();
      return status && !["fixture", "sample"].includes(status);
    })
    .slice(0, 12);
  const feedbackSkillRows = effectiveStudioState?.liveReady
    ? latestFeedback
      .map(item => ({
        id: item.skillId || item.skill_id || item.feedbackId || "",
        name: item.label || item.skillId || item.skill_id || "Measured skill",
        summary:
          item.nextAction === "repair"
            ? "Live mission-slice feedback marked this skill for repair before reuse."
            : item.nextAction === "reinforce"
              ? "Live mission-slice feedback marked this skill as useful for future routing."
              : "Live mission-slice feedback captured this skill in the current system-gap loop.",
        status: item.nextAction || "measured",
        sourceType: item.sourceKind || "mission-slice",
        category: item.missionId || item.mission_id || "mission feedback",
        feedbackSummary: {
          latestSystemLoss: item.systemLoss,
          trend: item.nextAction || "measured",
          selectionPolicy: { state: item.nextAction || "measured" },
        },
      }))
      .filter(item => item.id || item.name)
      .slice(0, 8)
    : [];
  const displayedSkills = liveSkills.length > 0 ? liveSkills : feedbackSkillRows;
  const skillSourceMode = liveSkills.length > 0
    ? "live NAS registry"
    : feedbackSkillRows.length > 0
      ? "mission-slice feedback"
      : liveSkillRegistryReady
        ? "live registry returned zero rows"
        : "no live registry rows";
  const runtimeRouteProof = effectiveStudioState?.runtimeRouteProof || {};
  const runtimeRouteReceipt = runtimeRouteProof?.lastSuccessfulChat || runtimeRouteProof?.receipt || {};
  const m3RouteVerified = Boolean(
    runtimeRouteProof?.verified ||
      runtimeRouteReceipt?.model === "MiniMax-M3" ||
      runtimeRouteProof?.frontendExecutorModel === "MiniMax-M3",
  );
  const frontendRouteModel =
    runtimeRouteReceipt?.model ||
    runtimeRouteProof?.frontendExecutorModel ||
    "MiniMax-M3";
  const frontendRouteProvider =
    runtimeRouteReceipt?.provider ||
    runtimeRouteProof?.frontendExecutorProvider ||
    "minimax-oauth";
  const hermesSkillsHubFacts = [
    ["Runtime", "Hermes", "harness"],
    ["Frontend", frontendRouteModel, frontendRouteProvider],
    ["Skill format", "SKILL.md", "procedures"],
    ["Source", "Live", skillSourceMode],
  ];
  const runtimeContractMetrics = [
    ["Contracts", runtimeContractReady ? runtimeContract.contractCount || runtimeContractSkills.length : 0, "input/output/proof"],
    ["Ready", runtimeContractReady ? runtimeContract.executionReadyCount || 0 : 0, "Hermes lanes"],
    ["Generated", runtimeContractReady ? runtimeContract.generatedSchemaCount || 0 : 0, "minimal schemas"],
    ["Held", runtimeContractReady ? runtimeContract.heldSkillCount || 0 : 0, "guardrails"],
  ];
  const codeModSkillRows = [
    ["simplify-code", "Hermes", "Code cleanup and targeted refactors"],
    ["test-driven-development", "Hermes", "Test-first repair and regression coverage"],
    ["codex", "Hermes", "Codex-style coding delegation"],
    ["opencode", "Hermes", "OpenCode compatible coding sessions"],
    ["workspace-skill", "OpenClaw", "Workspace or ClawHub managed skill"],
  ];
  const redTeamEscalation =
    effectiveStudioState?.redTeamEscalation ||
    studioState?.redTeamEscalation ||
    skillStudioState?.redTeamEscalation ||
    {};
  const redTeamHistory = asList(redTeamEscalation.history).slice(-6);
  const skillLibraryEntries = (isRuleSets ? ruleSets : displayedSkills).map((item, index) => ({
    item,
    key: skillLibraryKey(item, index),
  }));
  const [selectedSkillKey, setSelectedSkillKey] = useState("");
  const [skillDrafts, setSkillDrafts] = useState(loadFluxioSkillDrafts);
  const [skillEditorStatus, setSkillEditorStatus] = useState("");
  const skillLibrarySignature = skillLibraryEntries.map(entry => entry.key).join("|");
  useEffect(() => {
    setSelectedSkillKey(current => {
      if (!skillLibraryEntries.length) return "";
      if (current && skillLibraryEntries.some(entry => entry.key === current)) return current;
      return skillLibraryEntries[0].key;
    });
  }, [skillLibrarySignature]);
  const selectedSkillEntry =
    skillLibraryEntries.find(entry => entry.key === selectedSkillKey) ||
    skillLibraryEntries[0] ||
    null;
  const selectedSkill = selectedSkillEntry?.item || null;
  const selectedSkillDraft = selectedSkillEntry
    ? {
        name: skillLibraryTitle(selectedSkill),
        category: String(selectedSkill?.category || selectedSkill?.sourceType || selectedSkill?.scope || "uncategorized"),
        status: String(selectedSkill?.status || selectedSkill?.promotionState || "live"),
        instructions: skillLibraryBody(selectedSkill),
        agentRequest: "",
        ...(skillDrafts[selectedSkillEntry.key] || {}),
      }
    : {
        name: "",
        category: "",
        status: "",
        instructions: "",
        agentRequest: "",
      };
  const updateSelectedSkillDraft = (field, value) => {
    if (!selectedSkillEntry) return;
    setSkillEditorStatus("");
    setSkillDrafts(current => ({
      ...current,
      [selectedSkillEntry.key]: {
        ...selectedSkillDraft,
        ...current[selectedSkillEntry.key],
        [field]: value,
      },
    }));
  };
  const persistSelectedSkillDraft = action => {
    if (!selectedSkillEntry) return null;
    const savedDraft = {
      ...selectedSkillDraft,
      id: selectedSkillEntry.key,
      source: skillSourceMode,
      updatedAt: new Date().toISOString(),
    };
    const nextDrafts = {
      ...skillDrafts,
      [selectedSkillEntry.key]: savedDraft,
    };
    setSkillDrafts(nextDrafts);
    if (typeof window !== "undefined") {
      window.localStorage?.setItem(FLUXIO_SKILL_DRAFTS_KEY, JSON.stringify(nextDrafts));
    }
    setSkillEditorStatus(action === "send" ? "Sent to Agent with the current draft." : "Draft saved locally.");
    return savedDraft;
  };
  const saveSelectedSkillDraft = () => {
    const savedDraft = persistSelectedSkillDraft("save");
    if (savedDraft) {
      fluxioAction(onRequestAction, "skills:save-draft", savedDraft);
    }
  };
  const sendSelectedSkillToAgent = () => {
    const savedDraft = persistSelectedSkillDraft("send");
    if (savedDraft) {
      fluxioAction(onRequestAction, "skills:modify-with-agent", {
        skillId: selectedSkillEntry.key,
        draft: savedDraft,
        request: savedDraft.agentRequest || "Review and improve this skill.",
      });
    }
  };
  return (
    <div
      className="fluxos-skills"
      data-skills-clarity-mode={normalizedSkillsClarityMode}
      data-skills-focus-contract="capability-routing-first"
    >
      <section className="fluxos-skills-list">
        <div className="fluxos-section-head">
          <span>{isRuleSets ? "Rule Sets" : "Skill library"}</span>
          <strong>{isRuleSets ? "Core policy and Approval gates" : effectiveStudioState?.liveReady ? "Your skills" : "Awaiting NAS skill registry"}</strong>
          {effectiveStudioState?.liveReady && !isRuleSets ? (
            <div className="fluxos-builder-clarity-switch" aria-label="Skills clarity mode" data-live-skills-clarity-switch="true">
              <button
                className={skillsFocusMode ? "active" : ""}
                onClick={() => setLiveSkillsClarityMode("focus")}
                type="button"
              >
                Focus
              </button>
              <button
                className={!skillsFocusMode ? "active" : ""}
                onClick={() => setLiveSkillsClarityMode("full")}
                type="button"
              >
                Full
              </button>
            </div>
          ) : null}
        </div>
        {!isRuleSets ? (
          <section
            className="fluxos-skill-library-workspace"
            aria-label="User skill library editor. Live measured capabilities."
            data-skill-library-editor="true"
            data-live-skills-feedback="true"
            data-measured-skill-count={measuredSkillCount}
            data-repair-skill-count={repairCount}
            data-reinforce-skill-count={reinforceCount}
          >
            <div className="fluxos-skill-library-list" aria-label="Your skills">
              <div className="fluxos-skill-library-list-head">
                <span>Your skills</span>
                <strong>{`${skillLibraryEntries.length} saved`}</strong>
              </div>
              {skillLibraryEntries.length > 0 ? skillLibraryEntries.map(entry => {
                const item = entry.item;
                const active = entry.key === selectedSkillEntry?.key;
                return (
                  <button
                    className={cx("fluxos-skill-library-row", active && "active")}
                    data-connected-app-skill-draft={String(item?.sourceType || "").toLowerCase() === "connected_app" ? "true" : "false"}
                    data-live-skill-row={effectiveStudioState?.liveReady ? "true" : "false"}
                    data-skill-feedback-state={item?.feedbackSummary?.selectionPolicy?.state || item?.feedbackSummary?.trend || item?.status || "live"}
                    data-skill-gap={item?.feedbackSummary?.latestSystemLoss ?? ""}
                    data-skill-id={entry.key}
                    key={entry.key}
                    onClick={() => setSelectedSkillKey(entry.key)}
                    type="button"
                  >
                    <BookOpen size={16} strokeWidth={1.8} />
                    <span>
                      <strong>{skillLibraryTitle(item)}</strong>
                      <em>{item?.category || item?.sourceType || asList(item?.tags).slice(0, 2).join(" · ") || "skill"}</em>
                    </span>
                  </button>
                );
              }) : (
                <article className="fluxos-flow-empty">
                  <span>Live data only</span>
                  <strong>No live skill registry returned yet</strong>
                  <p>
                    {effectiveStudioState?.liveReady
                      ? "The current NAS snapshot did not return user skill rows."
                      : "Refresh the live control-room snapshot to load your saved skills."}
                  </p>
                </article>
              )}
            </div>
            <div className="fluxos-skill-editor-panel" data-skill-editor="true">
              <div className="fluxos-skill-editor-title">
                <span>{selectedSkillDraft.status || "draft"}</span>
                <strong>{selectedSkillDraft.name || "Select a skill"}</strong>
              </div>
              <label>
                <span>Name</span>
                <input
                  aria-label="Skill name"
                  disabled={!selectedSkillEntry}
                  onChange={event => updateSelectedSkillDraft("name", event.target.value)}
                  value={selectedSkillDraft.name}
                />
              </label>
              <label>
                <span>Category</span>
                <input
                  aria-label="Skill category"
                  disabled={!selectedSkillEntry}
                  onChange={event => updateSelectedSkillDraft("category", event.target.value)}
                  value={selectedSkillDraft.category}
                />
              </label>
              <label className="wide">
                <span>Skill instructions</span>
                <textarea
                  aria-label="Skill instructions"
                  disabled={!selectedSkillEntry}
                  onChange={event => updateSelectedSkillDraft("instructions", event.target.value)}
                  value={selectedSkillDraft.instructions}
                />
              </label>
              <label className="wide">
                <span>Ask Agent to modify</span>
                <textarea
                  aria-label="Agent skill modification request"
                  disabled={!selectedSkillEntry}
                  onChange={event => updateSelectedSkillDraft("agentRequest", event.target.value)}
                  placeholder="Describe what should change in this skill."
                  value={selectedSkillDraft.agentRequest}
                />
              </label>
              <div className="fluxos-skill-editor-actions">
                <button disabled={!selectedSkillEntry} onClick={saveSelectedSkillDraft} type="button">Save draft</button>
                <button className="primary" disabled={!selectedSkillEntry} onClick={sendSelectedSkillToAgent} type="button">Send to Agent</button>
                <button disabled={!selectedSkillEntry} onClick={() => fluxioAction(onRequestAction, `skill:open:${selectedSkillEntry?.key || "none"}`)} type="button">Open details</button>
              </div>
              {skillEditorStatus ? <p className="fluxos-skill-editor-status">{skillEditorStatus}</p> : null}
            </div>
          </section>
        ) : null}
        {!isRuleSets ? (
          <section
            className={cx("fluxos-skill-runtime-contract", runtimeContractReady ? "ready" : "pending")}
            aria-label="Skill runtime contract"
            data-skill-runtime-contract="true"
            data-skill-runtime-schema={runtimeContractReady ? runtimeContract.schema : "pending"}
            data-skill-runtime-primary-lane={runtimeContract?.primaryRuntimeLane || "hermes"}
          >
            <div className="fluxos-skill-runtime-contract-head">
              <div>
                <span>Skill runtime contract</span>
                <strong>{runtimeContractReady ? "Skills have input, output, route, and proof" : "Waiting for live skill runtime contract"}</strong>
                <p>
                  {runtimeContractReady
                    ? runtimeContract.nextAction || "Use the selected Hermes skill lane and attach its proof artifact to the mission."
                    : "Capture the contract from the live backend before claiming a skill can execute."}
                </p>
              </div>
              <div className="fluxos-skill-runtime-contract-actions">
                <span>{`${runtimeContract?.primaryRuntimeLane || "Hermes"} primary · ${(runtimeContract?.fallbackRuntimeLanes || ["openclaw", "opencode"]).join(" / ")} fallback`}</span>
                <button onClick={() => fluxioAction(onRequestAction, "skills:capture-runtime-contract", { skillId: selectedSkillEntry?.key || "" })} type="button">
                  Capture skill proof
                </button>
              </div>
            </div>
            <div className="fluxos-skill-runtime-metrics" aria-label="Skill runtime contract metrics">
              {runtimeContractMetrics.map(([label, value, detail]) => (
                <article key={`skill-runtime-metric-${label}`}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                  <small>{detail}</small>
                </article>
              ))}
            </div>
            <div className="fluxos-skill-runtime-lanes" aria-label="Skill runtime lanes">
              {(runtimeContractSkills.length > 0 ? runtimeContractSkills : [{
                skillId: selectedSkillEntry?.key || "pending-skill",
                label: selectedSkillDraft.name || "Live contract pending",
                route: { runtimeLane: "hermes", fallbackRuntimeLane: "openclaw" },
                input: { status: "pending", required: [] },
                output: { artifactPath: ".agent_control/skill_runtime_proofs/<skill>.json" },
                systemLossHold: { held: false },
              }]).map(item => (
                <article
                  className={cx("fluxos-skill-runtime-lane", item?.systemLossHold?.held && "held")}
                  data-skill-runtime-lane="true"
                  data-skill-runtime-lane-id={item.skillId || ""}
                  key={`skill-runtime-lane-${item.skillId || item.label}`}
                >
                  <span>{item?.route?.runtimeLane || "hermes"}</span>
                  <strong>{item.label || item.skillId || "Skill"}</strong>
                  <p>{`Input ${titleizeToken(item?.input?.status || "pending")} · output ${item?.output?.schema || "fluxio.skill_runtime_result.v1"}`}</p>
                  <em>{item?.output?.artifactPath || ".agent_control/skill_runtime_proofs/<skill>.json"}</em>
                </article>
              ))}
            </div>
          </section>
        ) : null}
        {effectiveStudioState?.liveReady && !isRuleSets && !skillsFocusMode ? (
          <section className="fluxos-skill-command-band" aria-label="Live skills command band" data-live-skills-command-band="true">
            <div>
              <span>Live skills</span>
              <strong>System-gap routing</strong>
              <p>
                {`${displayedSkills.length} visible rows from ${skillSourceMode}. ${repairCount} repair, ${reinforceCount} reinforce, ${heldSkillCount} held before reuse.`}
              </p>
            </div>
            <div className="fluxos-skill-command-metrics" aria-label="Live skill routing metrics">
              {[
                ["Measured", measuredSkillCount, "slices"],
                ["Repair", repairCount, "hold"],
                ["Reinforce", reinforceCount, "promote"],
                ["Held", heldSkillCount, "routing"],
              ].map(([label, value, detail]) => (
                <article key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                  <small>{detail}</small>
                </article>
              ))}
            </div>
            <div className="fluxos-skill-command-actions">
              <button onClick={() => fluxioAction(onRequestAction, "skills:review-system-loss")} type="button">Review gap</button>
              <button onClick={() => fluxioAction(onRequestAction, "skills:open-repair-queue")} type="button">Repair queue</button>
              <button disabled={repairProposals.length === 0} onClick={() => fluxioAction(onRequestAction, `skills:apply-repair:${repairProposals[0]?.skillId || repairProposals[0]?.proposalId || "next"}`)} type="button">Apply repair</button>
            </div>
          </section>
        ) : null}
        {effectiveStudioState?.liveReady && !isRuleSets && !skillsFocusMode ? (
          <section
            className={cx("fluxos-skill-route-proof", m3RouteVerified && "verified")}
            aria-label="MiniMax M3 frontend skill route"
            data-live-skills-m3-route-proof="true"
            data-live-skills-m3-route-state={m3RouteVerified ? "verified" : "pending"}
          >
            <div>
              <span>Frontend executor</span>
              <strong>{m3RouteVerified ? "Hermes to MiniMax-M3 is verified" : "Hermes to MiniMax-M3 is pending proof"}</strong>
              <p>
                MiniMax-M3 is used for frontend/design execution only through Hermes routing. Codex stays the planner/verifier lane.
              </p>
            </div>
            <div className="fluxos-skill-route-proof-grid">
              <article>
                <span>Harness</span>
                <strong>Hermes</strong>
                <small>default runtime</small>
              </article>
              <article>
                <span>Model</span>
                <strong>{frontendRouteModel}</strong>
                <small>{frontendRouteProvider}</small>
              </article>
              <article>
                <span>Reference</span>
                <strong>MiniMax M3</strong>
                <small>coding and agentic model</small>
              </article>
            </div>
          </section>
        ) : null}
        {effectiveStudioState?.liveReady && !isRuleSets && !skillsFocusMode ? (
          <section
            className="fluxos-hermes-skill-source"
            aria-label="Hermes live skill source"
            data-live-hermes-skill-source="true"
            data-live-skill-source-mode={skillSourceMode}
          >
            <div>
              <span>Hermes Skills Hub</span>
              <strong>{skillSourceMode}</strong>
              <p>
                Hermes skills are runtime-loadable procedures. Fluxio shows live NAS registry rows first,
                then mission-slice feedback rows; it does not fill this page with static sample skills.
                External references are used as routing guidance, not as fake live rows.
              </p>
            </div>
            <div className="fluxos-hermes-skill-source-grid" aria-label="Hermes skill registry facts">
              {hermesSkillsHubFacts.map(([label, value, detail]) => (
                <article key={`hermes-skill-source-${label}`}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                  <small>{detail}</small>
                </article>
              ))}
            </div>
          </section>
        ) : null}
        {effectiveStudioState?.liveReady && !isRuleSets && !skillsFocusMode ? (
          <section
            className="fluxos-code-mod-skill-lane"
            aria-label="Code mod skill lane"
            data-code-mod-skill-lane="true"
          >
            <div>
              <span>Code mod lane</span>
              <strong>Hermes uses coding skills by default</strong>
              <p>
                Code-mod missions should record the selected skill in mission proof. OpenClaw skills stay available when the operator explicitly picks an OpenClaw workspace skill.
              </p>
            </div>
            <div className="fluxos-code-mod-skill-grid">
              {codeModSkillRows.map(([skillId, runtime, detail]) => (
                <article key={`code-mod-skill-${skillId}`}>
                  <span>{runtime}</span>
                  <strong>{skillId}</strong>
                  <small>{detail}</small>
                </article>
              ))}
            </div>
            <div className="fluxos-skill-command-actions">
              <button onClick={() => fluxioAction(onRequestAction, "skills:use-code-mod:hermes:simplify-code")} type="button">Use Hermes code mod</button>
              <button onClick={() => fluxioAction(onRequestAction, "skills:restore-hermes-code-mod")} type="button">Restore Hermes skills</button>
              <button onClick={() => fluxioAction(onRequestAction, "skills:update-openclaw")} type="button">Update OpenClaw skills</button>
            </div>
          </section>
        ) : null}
        {effectiveStudioState?.liveReady && !isRuleSets && !skillsFocusMode ? (
          <div
            className="fluxos-live-skill-summary"
            aria-label="Live skill catalog source"
            data-live-skills-feedback="true"
            data-measured-skill-count={measuredSkillCount}
            data-repair-skill-count={repairCount}
            data-reinforce-skill-count={reinforceCount}
          >
            <span>{effectiveStudioState.liveSource || skillSourceMode || "control-room skill catalog"}</span>
            <strong>{`${effectiveStudioState?.totals?.totalSkills || displayedSkills.length} real skill rows`}</strong>
            <em>{`${measuredSkillCount} measured · ${repairCount} repair · ${reinforceCount} reinforce`}</em>
          </div>
        ) : null}
        {isRuleSets && ruleSets.length > 0 ? ruleSets.map(item => (
          <button
            className="fluxos-skill-card"
            data-live-rule-row={effectiveStudioState?.liveReady ? "true" : "false"}
            key={item.id || item.name}
            onClick={() => fluxioAction(onRequestAction, `skill:open:${item.id || item.name}`)}
            type="button"
          >
            <Shield size={20} strokeWidth={1.7} />
            <div>
              <strong>{item.name || item.label || "Rule set"}</strong>
              <p>{item.summary || item.description || "Live rule set returned by the NAS snapshot."}</p>
            </div>
            <span>{item.status || "live"}</span>
            <em>{item.scope || item.badge || "rules"}</em>
          </button>
        )) : isRuleSets ? (
          <article className="fluxos-flow-empty">
            <span>Live data only</span>
            <strong>No live rule sets returned</strong>
            <p>The current NAS snapshot did not include rule rows for this surface.</p>
          </article>
        ) : null}
      </section>
      <section className={cx("fluxos-editor", skillsFocusMode && "is-diagnostics-hidden")} data-live-skills-secondary-panel="true">
        <div className="fluxos-section-head">
          <span>{isRuleSets ? "Ruleset editor" : "Mission-slice feedback loop"}</span>
          <strong>{isRuleSets ? ruleSets[0]?.name || "Frontend merge policy" : "System gap routing"}</strong>
        </div>
        {!isRuleSets ? (
          <div
            className="fluxos-loss-routing"
            aria-label="System gap routing"
            data-live-skills-feedback="true"
            data-measured-skill-count={measuredSkillCount}
            data-repair-skill-count={repairCount}
            data-reinforce-skill-count={reinforceCount}
          >
            <div className="fluxos-loss-routing-head">
              <span>{routing.enabled ? "Active" : "Collecting evidence"}</span>
              <strong>
                {`${measuredSkillCount} measured · ${repairCount} repair · ${reinforceCount} reinforce`}
              </strong>
              <p>
                {`Prefer slices at or below ${routing.preferThreshold ?? 0.15} gap. Deprioritize skills at or above ${routing.deprioritizeThreshold ?? 0.55} gap until repair evidence is clean.`}
              </p>
            </div>
            <div className="fluxos-loss-chip-row">
              <span>{`${asList(routing.preferredSkillIds).length} preferred`}</span>
              <span>{`${asList(routing.activeRepairSkillIds).length} held for repair`}</span>
              <span>{`${routing.minimumPromotionSlices ?? 3} clean slices`}</span>
            </div>
            <div className="fluxos-loss-events">
              {latestFeedback.length > 0 ? latestFeedback.map(item => (
                <article key={item.feedbackId || `${item.skillId}-${item.createdAt}`}>
                  <span>{item.nextAction || "review"}</span>
                  <strong>{item.label || item.skillId || "Skill"}</strong>
                  <p>{`gap ${item.systemLoss ?? "n/a"} · improvement ${item.improvementScore ?? "n/a"}`}</p>
                </article>
              )) : (
                <article>
                  <span>Awaiting first slice</span>
                  <strong>No system-gap feedback yet</strong>
                  <p>Run a mission slice to score the selected skills against execution and verification evidence.</p>
                </article>
              )}
            </div>
            <div className="fluxos-red-team-trend" aria-label="Red-team escalation trend">
              <div>
                <span>Red-team escalation trend</span>
                <strong>{`${redTeamEscalation.latestResistanceScore || 0} resistance · ${redTeamEscalation.latestDifficultyLevel || 0} -> ${redTeamEscalation.nextDifficultyLevel || 0} difficulty`}</strong>
                {redTeamEscalation.nextPressureIndex ? (
                  <em>{`Pressure ${redTeamEscalation.currentPressureIndex || 0} -> ${redTeamEscalation.nextPressureIndex}`}</em>
                ) : null}
                <p>{redTeamEscalation.nextAction || "Run a defensive red-team benchmark to start the escalation trend."}</p>
              </div>
              <div className="fluxos-red-team-bars" aria-label="Recent red-team difficulty history">
                {redTeamHistory.length > 0 ? redTeamHistory.map((item, index) => {
                  const level = Math.max(0, item.nextDifficultyLevel || item.difficultyLevel || 0);
                  const pressure = Math.max(0, item.nextPressureIndex || item.currentPressureIndex || 0);
                  const height = Math.max(18, Math.min(66, 18 + level * 8 + Math.min(18, Math.floor(pressure / 8))));
                  return (
                    <span
                      className={item.shouldEscalate ? "escalate" : ""}
                      key={item.id || `${item.preset}-${index}`}
                      style={{ "--bar-height": `${height}px` }}
                    >
                      {item.nextDifficultyLabel || item.nextDifficultyLevel || item.difficultyLevel || 0}
                    </span>
                  );
                }) : (
                  <em>No run history</em>
                )}
              </div>
              {redTeamEscalation?.nextBenchmarkPlan?.commandShell ? (
                <div className="red-team-next-benchmark" aria-label="Next red-team benchmark command">
                  <div>
                    <span>Next aggregate benchmark</span>
                    <strong>
                      {`${redTeamEscalation.nextBenchmarkPlan.attemptBudget || redTeamEscalation.nextAttemptBudget || 0} attempts · target ${redTeamEscalation.nextBenchmarkPlan.targetResistanceScore || 0}+`}
                    </strong>
                    <p>{asList(redTeamEscalation.nextBenchmarkPlan.tactics).join(" · ") || "No tactic families recorded."}</p>
                  </div>
                  <code>{redTeamEscalation.nextBenchmarkPlan.commandShell}</code>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
        <div className="fluxos-code-window">
          <pre>{`name: Core policy
policy: frontend-polish
autonomy: workspace_safe
required:
  - inspect_reference_images
  - no_unwired_buttons
  - browser_visual_check
  - npm_run_frontend_build
Approval:
  merge: required
  destructive_actions: always_ask`}</pre>
        </div>
        <div className="fluxos-permission-grid">
          {["Files", "Terminal", "Browser", "Network"].map(item => (
            <button key={item} onClick={() => fluxioAction(onRequestAction, `skill:permission:${item}`)} type="button">
              <Shield size={16} strokeWidth={1.8} />
              <span>{item}</span>
              <strong>Allowed</strong>
            </button>
              ))}
            </div>
            <div className="fluxos-loss-events">
              {repairProposals.length > 0 ? repairProposals.map(item => (
                <article key={item.proposalId || item.skillId || item.label}>
                  <span>Repair proposal</span>
                  <strong>{item.label || item.skillId || "Skill repair"}</strong>
                  <p>{item.validationGate || item.nextAction || "Validate the repair before reuse."}</p>
                </article>
              )) : (
                <article>
                  <span>Repair queue</span>
                  <strong>No live repair proposal returned</strong>
                  <p>High-gap skills will appear here when mission-slice feedback produces a repair action.</p>
                </article>
              )}
            </div>
      </section>
    </div>
  );
}

function FluxioWorkbenchSurface({ liveDataStatus, messages = [], onRequestAction, onSetSurface, timelineMoments = [], workbenchState }) {
  const isLiveBackend = liveDataStatus?.previewMode === "live";
  const [workbenchClarityMode, setWorkbenchClarityMode] = useState(() => {
    if (typeof window === "undefined") return "focus";
    return window.localStorage?.getItem("fluxio.workbench.clarityMode") || "focus";
  });
  const normalizedWorkbenchClarityMode = workbenchClarityMode === "full" ? "full" : "focus";
  const workbenchFocusMode = isLiveBackend && normalizedWorkbenchClarityMode === "focus";
  const setLiveWorkbenchClarityMode = mode => {
    const nextMode = mode === "full" ? "full" : "focus";
    setWorkbenchClarityMode(nextMode);
    if (typeof window !== "undefined") {
      window.localStorage?.setItem("fluxio.workbench.clarityMode", nextMode);
    }
  };
  const runtimeOps = asList(workbenchState?.runtimeOps).slice(0, 8);
  const artifacts = asList(workbenchState?.artifacts).slice(0, 8);
  const artifactGate = workbenchState?.artifactGate && typeof workbenchState.artifactGate === "object"
    ? workbenchState.artifactGate
    : {};
  const artifactGatePassed = Boolean(artifactGate.passed);
  const artifactGateStatus = artifactGate.status || (artifactGatePassed ? "passed" : "missing_required_output");
  const notificationEvents = asList(workbenchState?.notificationEvents).filter(item => Number(item?.count || 0) > 0).slice(0, 6);
  const progressValue = clampPercent(workbenchState?.progress?.value);
  const liveThreadRows = visibleAgentMessages(compactAgentMessages(messages), 12, 6, { requireRuntimeReports: isLiveBackend });
  const [selectedWorkbenchMessageId, setSelectedWorkbenchMessageId] = useState("");
  const manualWorkbenchMessageSelectionRef = useRef(false);
  const liveThreadRowEntries = useMemo(
    () => liveThreadRows.map((item, index) => ({
      item,
      key: stableAgentMessageKey(item, `workbench-thread-${index}`),
    })),
    [liveThreadRows],
  );
  const activeMissionIdForWorkbenchMessages = String(workbenchState?.missionId || "").trim();
  const scopedLiveThreadRowEntries = useMemo(
    () => {
      if (!isLiveBackend || !activeMissionIdForWorkbenchMessages) {
        return liveThreadRowEntries;
      }
      return liveThreadRowEntries.filter(entry => {
        const entryMissionId = String(entry?.item?.missionId || entry?.item?.mission_id || "").trim();
        return entryMissionId === activeMissionIdForWorkbenchMessages;
      });
    },
    [activeMissionIdForWorkbenchMessages, isLiveBackend, liveThreadRowEntries],
  );
  const scopedLiveThreadRows = scopedLiveThreadRowEntries.map(entry => entry.item);
  const liveThreadRowKeySignature = scopedLiveThreadRowEntries.map(entry => entry.key).join("|");
  const workbenchSelectionScope = [
    liveDataStatus?.previewMode || "preview",
    workbenchState?.missionId || "",
    workbenchState?.missionTitle || "",
    isLiveBackend ? liveThreadRowKeySignature : "",
  ].join(":");
  const workbenchSelectionScopeRef = useRef("");
  useEffect(() => {
    setSelectedWorkbenchMessageId(current => {
      const scopeChanged = workbenchSelectionScopeRef.current !== workbenchSelectionScope;
      workbenchSelectionScopeRef.current = workbenchSelectionScope;
      if (scopeChanged) {
        manualWorkbenchMessageSelectionRef.current = false;
      }
      const currentEntry = current ? liveThreadRowEntries.find(entry => entry.key === current) : null;
      const currentEntryMissionId = String(
        currentEntry?.item?.missionId ||
          currentEntry?.item?.mission_id ||
          "",
      ).trim();
      const scopedMissionId = String(workbenchState?.missionId || "").trim();
      if (
        current &&
        currentEntry &&
        manualWorkbenchMessageSelectionRef.current &&
        (!isLiveBackend || !scopedMissionId || !currentEntryMissionId || currentEntryMissionId === scopedMissionId)
      ) {
        return current;
      }
      const runtimeReport = scopedLiveThreadRows.find(isRuntimeOutputAgentMessage);
      const meaningful = runtimeReport || scopedLiveThreadRows.find(isMeaningfulDefaultAgentMessage) || scopedLiveThreadRows[0] || null;
      if (!meaningful) return "";
      const meaningfulEntry = scopedLiveThreadRowEntries.find(entry => entry.item === meaningful);
      return meaningfulEntry?.key || "";
    });
  }, [isLiveBackend, liveThreadRowEntries, scopedLiveThreadRowEntries, scopedLiveThreadRows, workbenchSelectionScope, liveThreadRowKeySignature, workbenchState?.missionId]);
  const selectedWorkbenchMessage =
    scopedLiveThreadRowEntries.find(entry => entry.key === selectedWorkbenchMessageId)?.item ||
    null;
  const selectedWorkbenchBody = selectedWorkbenchMessage ? agentMessageDisplayDetail(selectedWorkbenchMessage) : "";
  const messagePreviewCandidates = previewUrlCandidatesForMessage(selectedWorkbenchMessage);
  const previewUrlCandidates = selectedWorkbenchMessage
    ? messagePreviewCandidates
    : [
        workbenchState?.previewUrl,
        workbenchState?.liveReview?.previewUrl,
        workbenchState?.previewActionUrl,
        workbenchState?.liveReview?.previewActionUrl,
      ];
  const previewActionUrl = previewUrlCandidates.find(isUsablePreviewUrl) || "";
  const previewFrameUrl = selectedWorkbenchMessage ? "" : previewUrlCandidates.find(isWorkbenchPreviewFrameUrl) || "";
  const previewFrameBlocked = Boolean(previewActionUrl && !previewFrameUrl && !selectedWorkbenchMessage);
  const livePreviewState = selectedWorkbenchMessage
    ? "selected-message"
    : previewFrameUrl
      ? "mission-frame"
      : previewFrameBlocked
        ? "frame-blocked"
        : "empty";
  const livePreviewStateLabel = selectedWorkbenchMessage
    ? "Selected message"
    : previewFrameUrl
      ? "Served mission frame"
      : previewFrameBlocked
        ? "Open in browser"
        : "No served preview";
  const selectedWorkbenchTitle = selectedWorkbenchMessage
    ? agentMessageDisplayTitle(selectedWorkbenchMessage)
    : workbenchState?.missionTitle || "No message selected";
  const liveTimelineRows = asList(timelineMoments)
    .filter(item => !isLowSignalAgentMessage(item))
    .slice(-8);
  const operationRows = runtimeOps.length > 0
    ? runtimeOps
    : liveTimelineRows.length > 0
      ? liveTimelineRows.map(item => ({
          id: item.id || `${item.kind || item.title}-${item.timestamp || item.time || ""}`,
          label: item.title || item.kind || "Live runtime event",
          detail: item.detail || item.message || item.status || "Live event returned by the NAS mission thread.",
          status: item.tone || item.kind || "live",
          timestamp: item.timestamp || item.createdAt || item.time || "",
        }))
      : scopedLiveThreadRows
        .filter(item => item.processMessage || item.emphasis || item.technicalDetail)
        .map(item => ({
          id: item.id,
          label: item.title || item.label || "Live mission message",
          detail: item.detail || item.technicalDetail || item.meta || "Message returned by the live mission detail endpoint.",
          status: item.tone || item.label || "live",
          timestamp: item.createdAt || item.timestamp || "",
        }));
  const workbenchProofMetrics = [
    ["Messages", scopedLiveThreadRows.length, selectedWorkbenchMessage ? "runtime reports" : "waiting for thread"],
    ["Artifacts", artifacts.length, artifacts.length ? "returned by NAS" : "none returned"],
    ["Gate", artifactGatePassed ? "Pass" : "Block", titleizeToken(artifactGateStatus)],
    ["Operations", operationRows.length, operationRows.length ? "live timeline" : "none returned"],
    ["Signals", notificationEvents.reduce((total, item) => total + Number(item?.count || 0), 0), "notifications"],
  ];
  const runtimeOutputReceiptRows = scopedLiveThreadRows.filter(isRuntimeOutputAgentMessage);
  const workbenchExecutionReceipts = [
    ...artifacts.map((item, index) => ({
      id: item.id || item.path || `artifact-receipt-${index}`,
      kind: "artifact",
      title: item.title || item.path || "Mission artifact",
      detail: item.detail || item.path || item.url || "Artifact row returned by the selected live mission.",
      status: item.status || "reported",
      action: item.url || item.previewUrl || item.path || "",
    })),
    ...runtimeOutputReceiptRows.slice(-3).map((item, index) => ({
      id: item.id || `runtime-output-receipt-${index}`,
      kind: "runtime output",
      title: agentMessageDisplayTitle(item),
      detail: runtimeOutputText(item) || agentMessageDisplayDetail(item) || "Runtime output row returned by the mission thread.",
      status: item.tone || "reported",
      action: "",
    })),
    selectedWorkbenchMessage && runtimeOutputReceiptRows.length === 0 ? {
      id: selectedWorkbenchMessage.id || selectedWorkbenchMessageId || "selected-message-proof",
      kind: "selected proof",
      title: agentMessageDisplayTitle(selectedWorkbenchMessage),
      detail: agentMessageDisplayDetail(selectedWorkbenchMessage) || "Selected message is the only live proof currently available.",
      status: "message-only",
      action: "",
    } : null,
    artifactGate && artifactGate.passed === false ? {
      id: `${workbenchState?.missionId || "mission"}:hard-artifact-gate`,
      kind: "hard gate",
      title: "Completion blocked until artifact proof exists",
      detail: artifactGate.failure || artifactGate.nextAction || "Mission needs a runtime-output body or served artifact before completion is trusted.",
      status: artifactGateStatus,
      action: "",
    } : null,
  ].filter(Boolean).slice(0, 5);
  const workbenchExecutionState = artifacts.length > 0 || previewActionUrl
    ? "ready"
    : runtimeOutputReceiptRows.length > 0
      ? "review"
      : scopedLiveThreadRows.length > 0
        ? "blocked"
        : liveDataStatus?.loading
          ? "loading"
          : "missing";
  const workbenchExecutionNextAction = workbenchExecutionState === "ready"
    ? "Open the served artifact or run a screenshot/proof capture against the live mission output."
    : workbenchExecutionState === "review"
      ? "Review runtime-output receipts, then capture proof or promote the artifact to a served preview."
      : workbenchExecutionState === "blocked"
        ? "This mission has live thread rows but no artifact/runtime-output body. Relaunch or resume with a hard artifact gate."
        : workbenchExecutionState === "loading"
          ? "Waiting for the NAS mission detail endpoint."
          : "No live artifact execution evidence returned for the selected mission.";
  const noPreviewLabel = liveDataStatus?.loading
    ? "Connecting to live preview evidence"
    : artifacts.length > 0
      ? "Artifact preview is file-based"
      : "No NAS preview evidence loaded";
  const noPreviewCopy = liveDataStatus?.loading
    ? "The NAS summary is still arriving. The preview area stays honest until the backend returns an artifact or served URL."
    : artifacts.length > 0
      ? "The selected mission has output artifacts, but no served iframe URL. Open the artifact rows below for review."
      : "No placeholder preview is drawn. The selected mission thread, progress, and runtime events are the current evidence.";
  const previewAnnotationReadiness =
    workbenchState?.previewAnnotationReadiness && typeof workbenchState.previewAnnotationReadiness === "object"
      ? workbenchState.previewAnnotationReadiness
      : {
          schema: "fluxio.preview_annotation_readiness.v1",
          status: "pending_live_capture",
          primaryRuntimeLane: "hermes",
          fallbackRuntimeLanes: ["openclaw", "opencode", "browser-cdp"],
          previewTarget: {
            url: previewActionUrl,
            surface: "workbench-preview",
          },
          captureCapabilities: [
            "open local app or served URL",
            "capture screenshot artifact",
            "dump DOM and visible text",
            "route visual finding into Agent/Builder follow-up context",
          ],
          skillsUsed: [],
          selectedFinding: {
            id: "pending-preview-finding",
            severity: "medium",
            finding: "Capture a preview artifact before claiming a browser annotation changed the implementation.",
            nextImplementationStep: "Capture preview annotation proof from the live backend.",
          },
          readinessChecks: [],
          blockers: ["Live capture has not run in this browser session."],
          nextAction: "Capture preview annotation proof from the live backend.",
          executionProof: {
            schema: "fluxio.preview_execution_proof.v1",
            screenshotCaptured: false,
            domCaptured: false,
            annotationFeedsRuntime: false,
          },
          runtimeHandoff: {
            schema: "fluxio.preview_annotation_handoff.v1",
            channel: "agent_runtime",
            nextImplementationStep: "Capture preview annotation proof from the live backend.",
          },
          missionGate: {
            schema: "fluxio.preview_browser_annotation_gate.v1",
            status: "needs_capture",
            checks: [],
          },
          proof: null,
          proofArtifacts: {},
        };
  const previewAnnotationProofPath = String(previewAnnotationReadiness?.proof?.artifactPath || "").trim();
  const previewAnnotationFinding = previewAnnotationReadiness?.selectedFinding || {};
  const previewAnnotationTarget = previewAnnotationReadiness?.previewTarget || {};
  const previewAnnotationExecutionProof = previewAnnotationReadiness?.executionProof || {};
  const previewAnnotationRuntimeHandoff = previewAnnotationReadiness?.runtimeHandoff || {};
  const previewAnnotationMissionGate = previewAnnotationReadiness?.missionGate || {};
  const previewAnnotationSkillIds = asList(previewAnnotationReadiness?.skillsUsed)
    .map(item => item?.id || item?.skill || item)
    .filter(Boolean);
  const previewAnnotationGateStatus = String(previewAnnotationMissionGate?.status || previewAnnotationReadiness.status || "needs_capture");
  const previewAnnotationReady = previewAnnotationGateStatus === "complete";
  const previewAnnotationTargetUrl = String(previewAnnotationTarget.url || previewActionUrl || previewFrameUrl || "").trim();
  const previewAnnotationScreenshotPath = String(
    previewAnnotationReadiness?.proofArtifacts?.screenshotPath ||
      previewAnnotationReadiness?.proofArtifacts?.screenshot ||
      "",
  ).trim();
  const previewAnnotationAnnotationMapPath = String(previewAnnotationReadiness?.proofArtifacts?.annotationMapPath || "").trim();
  const previewAnnotationRuntimeHandoffPath = String(previewAnnotationReadiness?.proofArtifacts?.runtimeHandoffPath || "").trim();
  const previewAnnotationHandoffText = String(
    previewAnnotationRuntimeHandoff?.nextImplementationStep ||
      previewAnnotationFinding.nextImplementationStep ||
      previewAnnotationReadiness.nextAction ||
      "",
  ).trim();
  const previewAnnotationExecutionLabel =
    previewAnnotationExecutionProof?.screenshotCaptured && previewAnnotationExecutionProof?.domCaptured
      ? "Screenshot and DOM captured"
      : "Capture still required";
  const previewAnnotationHandoffLabel =
    previewAnnotationExecutionProof?.annotationFeedsRuntime || previewAnnotationRuntimeHandoffPath
      ? "Finding feeds Agent runtime"
      : "Runtime handoff pending";
  return (
    <div
      className="fluxos-workbench"
      data-workbench-clarity-mode={normalizedWorkbenchClarityMode}
      data-workbench-focus-contract="proof-execution-first"
    >
      <section className={cx("fluxos-rail-panel fluxos-workbench-live-state", workbenchFocusMode && "is-focus-secondary")}>
        <div className="fluxos-section-head">
          <span>Live state</span>
          <strong>{titleizeToken(workbenchState?.missionStatus || workbenchState?.status || (liveDataStatus?.loading ? "Loading" : "Ready"))}</strong>
          {isLiveBackend ? (
            <div className="fluxos-builder-clarity-switch" aria-label="Workbench clarity mode" data-live-workbench-clarity-switch="true">
              <button
                className={workbenchFocusMode ? "active" : ""}
                onClick={() => setLiveWorkbenchClarityMode("focus")}
                type="button"
              >
                Focus
              </button>
              <button
                className={!workbenchFocusMode ? "active" : ""}
                onClick={() => setLiveWorkbenchClarityMode("full")}
                type="button"
              >
                Full
              </button>
            </div>
          ) : null}
        </div>
        {workbenchState?.missionTitle ? <strong className="fluxos-workbench-mission-title">{workbenchState.missionTitle}</strong> : null}
        {progressValue == null ? null : (
          <div className="fluxos-workbench-progress" aria-label={`Live mission progress ${progressValue}%`}>
            <span>{workbenchState?.progress?.label || "Progress"}</span>
            <i style={{ "--progress": `${progressValue}%` }} />
            <em>{`${progressValue}%`}</em>
          </div>
        )}
        <p>{workbenchState?.progress?.nextAction || "Browser, preview, screenshots, selectors, and replay markers stay attached to the current run."}</p>
        {notificationEvents.length > 0 ? (
          <div className="fluxos-workbench-events">
            {notificationEvents.map(item => (
              <button key={item.id || item.kind} onClick={() => fluxioAction(onRequestAction, `workbench:event:${item.kind}`)} type="button">
                <span>{item.count}</span>
                <strong>{item.label}</strong>
                <small>{item.detail}</small>
              </button>
            ))}
          </div>
        ) : null}
        {isLiveBackend ? (
          <div className="fluxos-workbench-thread" aria-label="Selected mission live thread">
            <span>Mission thread</span>
            {scopedLiveThreadRowEntries.length > 0 ? scopedLiveThreadRowEntries.map(({ item, key: messageKey }) => {
              const selected = selectedWorkbenchMessageId === messageKey;
              return (
              <article
                aria-pressed={selected}
                className={selected ? "selected" : ""}
                data-agent-message-key={messageKey}
                key={messageKey}
                onClick={() => {
                  const entryMissionId = String(item?.missionId || item?.mission_id || "").trim();
                  const scopedMissionId = activeMissionIdForWorkbenchMessages;
                  if (isLiveBackend && scopedMissionId && entryMissionId !== scopedMissionId) {
                    return;
                  }
                  manualWorkbenchMessageSelectionRef.current = true;
                  setSelectedWorkbenchMessageId(messageKey);
                }}
                onKeyDown={event => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    const entryMissionId = String(item?.missionId || item?.mission_id || "").trim();
                    const scopedMissionId = activeMissionIdForWorkbenchMessages;
                    if (isLiveBackend && scopedMissionId && entryMissionId !== scopedMissionId) {
                      return;
                    }
                    manualWorkbenchMessageSelectionRef.current = true;
                    setSelectedWorkbenchMessageId(messageKey);
                  }
                }}
                role="button"
                tabIndex={0}
              >
                <strong>{agentMessageDisplayTitle(item)}</strong>
                <p>{agentMessageDisplayDetail(item) || item.meta || "Live mission message returned by the NAS detail endpoint."}</p>
              </article>
            );
            }) : (
              <article>
                <strong>{liveDataStatus?.loading ? "Loading live thread messages" : "No live thread messages loaded"}</strong>
                <p>The workbench is waiting for the mission detail endpoint. No fallback messages are rendered.</p>
              </article>
            )}
          </div>
        ) : null}
      </section>
      <section className="fluxos-browser-pane">
        {isLiveBackend ? (
          <section
            aria-label="Live Workbench artifact execution"
            className={cx(`fluxos-workbench-execution state-${workbenchExecutionState}`, workbenchFocusMode && "is-focus-compact")}
            data-hard-artifact-gate={artifactGateStatus}
            data-live-workbench-execution="true"
            data-live-workbench-execution-state={workbenchExecutionState}
          >
            <div className="fluxos-workbench-execution-copy">
              <span>Artifact execution</span>
              <strong>{titleizeToken(workbenchExecutionState)}</strong>
              <p>{workbenchExecutionNextAction}</p>
            </div>
            <div className="fluxos-workbench-execution-receipts" data-live-workbench-execution-receipts="true">
              {workbenchExecutionReceipts.length > 0 ? workbenchExecutionReceipts.map(item => (
                <button
                  key={item.id}
                  onClick={() => {
                    if (item.action && isUsablePreviewUrl(item.action)) {
                      window.open(item.action, "_blank", "noopener,noreferrer");
                      return;
                    }
                    fluxioAction(onRequestAction, "workbench:open-execution-receipt", {
                      missionId: workbenchState?.missionId,
                      receiptId: item.id,
                      kind: item.kind,
                    });
                  }}
                  type="button"
                >
                  <span>{titleizeToken(item.kind)}</span>
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                  <em>{titleizeToken(item.status)}</em>
                </button>
              )) : (
                <article data-live-workbench-execution-missing="true">
                  <span>Live data only</span>
                  <strong>No execution receipt returned</strong>
                  <p>The Workbench will not invent an artifact. Open Agent or resume the mission with a hard served-artifact gate.</p>
                </article>
              )}
            </div>
            <div className="fluxos-workbench-execution-actions">
              <button disabled={!previewActionUrl} onClick={() => previewActionUrl && window.open(previewActionUrl, "_blank", "noopener,noreferrer")} type="button">Open artifact</button>
              <button onClick={() => fluxioAction(onRequestAction, "workbench:run-artifact-check", { missionId: workbenchState?.missionId })} type="button">Run artifact check</button>
              <button onClick={() => onSetSurface?.("agent")} type="button">Open Agent</button>
            </div>
          </section>
        ) : null}
        {isLiveBackend ? (
          <section
            aria-label="Live Workbench proof controls"
            className={cx("fluxos-workbench-proof-band", workbenchFocusMode && "is-focus-compact")}
            data-live-workbench-proof-band="true"
          >
            <div className="fluxos-workbench-proof-copy">
              <span>Live Workbench proof</span>
              <strong>{selectedWorkbenchTitle}</strong>
              <p>{livePreviewStateLabel}. This band is built from the current NAS mission detail; no placeholder preview is drawn in live mode.</p>
            </div>
            <div className="fluxos-workbench-proof-metrics" aria-label="Live Workbench metrics">
              {workbenchProofMetrics.map(([label, value, detail]) => (
                <span key={label}>
                  <strong>{value}</strong>
                  <small>{label}</small>
                  <em>{detail}</em>
                </span>
              ))}
            </div>
            <div className="fluxos-workbench-proof-actions">
              <button onClick={() => onSetSurface?.("agent")} type="button">Open Agent</button>
              <button onClick={() => fluxioAction(onRequestAction, "workbench:screenshot")} type="button">Capture proof</button>
              <button disabled={!previewActionUrl} onClick={() => previewActionUrl && window.open(previewActionUrl, "_blank", "noopener,noreferrer")} type="button">Open preview</button>
            </div>
          </section>
        ) : null}
        <section
          aria-label="Preview annotation readiness"
          className={cx("builder-preview-annotation-contract", previewAnnotationReady ? "ready" : "pending")}
          data-preview-annotation-readiness-contract="true"
          data-preview-annotation-primary-lane={previewAnnotationReadiness.primaryRuntimeLane || "hermes"}
          data-preview-annotation-schema={previewAnnotationReadiness.schema || "fluxio.preview_annotation_readiness.v1"}
        >
          <div className="builder-preview-annotation-head">
            <div>
              <span>Preview execution receipt</span>
              <strong>{titleizeToken(previewAnnotationGateStatus || "pending live capture")}</strong>
            </div>
            <button
              disabled={!previewAnnotationTargetUrl}
              onClick={() => fluxioAction(onRequestAction, "preview:capture-annotation-readiness", {
                surface: "workbench",
                targetUrl: previewAnnotationTargetUrl,
                baseUrl: typeof window !== "undefined" ? window.location.origin : "",
                selectedEventId: workbenchState?.missionId || "",
                selectedAnnotationId: previewAnnotationFinding.id || "workbench-preview-finding",
                screenshotPath: previewAnnotationScreenshotPath,
                autoCapture: true,
              })}
              type="button"
            >
              Capture preview proof
            </button>
          </div>
          <div className="builder-preview-annotation-grid">
            <article>
              <span>Target</span>
              <strong>{previewAnnotationTargetUrl || "No live preview URL yet"}</strong>
            </article>
            <article>
              <span>Skills</span>
              <strong>{previewAnnotationSkillIds.slice(0, 3).map(titleizeToken).join(" / ") || "Pending capture"}</strong>
            </article>
            <article data-preview-execution-proof="true">
              <span>Execution</span>
              <strong>{previewAnnotationExecutionLabel}</strong>
            </article>
            <article data-preview-runtime-handoff="true">
              <span>Runtime handoff</span>
              <strong>{previewAnnotationHandoffLabel}</strong>
            </article>
          </div>
          <p>{previewAnnotationFinding.finding || previewAnnotationReadiness.nextAction}</p>
          {previewAnnotationHandoffText ? <p className="builder-preview-annotation-next">Next: {previewAnnotationHandoffText}</p> : null}
          <small>
            {previewAnnotationProofPath
              ? `Proof artifact: ${previewAnnotationProofPath}`
              : previewAnnotationReadiness.nextAction || "Capture preview annotation proof before claiming the finding changed implementation."}
            {previewAnnotationAnnotationMapPath ? ` | Annotation map: ${previewAnnotationAnnotationMapPath}` : ""}
            {previewAnnotationRuntimeHandoffPath ? ` | Runtime handoff: ${previewAnnotationRuntimeHandoffPath}` : ""}
          </small>
        </section>
        <div className="fluxos-browser-chrome">
          <span />
          <strong>{workbenchState?.previewLabel || (isLiveBackend ? "No live preview frame attached" : "local layout preview")}</strong>
          <div className="fluxos-workbench-window-actions">
            <button disabled={!previewActionUrl} onClick={() => previewActionUrl && window.open(previewActionUrl, "_blank", "noopener,noreferrer")} type="button">Open preview</button>
            <button onClick={() => fluxioAction(onRequestAction, "workbench:screenshot")} type="button">Screenshot</button>
          </div>
        </div>
        <div
          className="fluxos-live-preview workbench"
          data-preview-state={livePreviewState}
          data-selected-message-id={selectedWorkbenchMessageId}
        >
          {previewFrameUrl ? (
            <>
              <iframe
                className="fluxos-live-preview-frame"
                data-workbench-preview-frame="true"
                key={`${workbenchState?.missionId || "mission"}:${selectedWorkbenchMessageId || "mission"}:${previewFrameUrl}`}
                src={previewFrameUrl}
                title="Live workbench preview"
              />
              <div className="fluxos-preview-policy-note">
                <strong>Embedded preview can be refused by the target site.</strong>
                <p>Workbench embeds local targets and served artifacts directly; use the open action if the target refuses framing.</p>
              </div>
            </>
          ) : isLiveBackend && previewFrameBlocked ? (
            <article className="fluxos-flow-empty fluxos-frame-blocked">
              <span>Live URL captured</span>
              <strong>Embedded preview disabled for this target</strong>
              <p>The target URL is real, but browser frame policy can block it inside Fluxio. Open it directly instead of showing a broken embedded page.</p>
              <div className="fluxos-preview-empty-actions">
                <button onClick={() => window.open(previewActionUrl, "_blank", "noopener,noreferrer")} type="button">Open new tab</button>
                <button onClick={() => fluxioAction(onRequestAction, "workbench:screenshot")} type="button">Capture proof</button>
              </div>
            </article>
          ) : !isLiveBackend ? (
            <article className="fluxos-flow-empty">
              <span>Local target</span>
              <strong>Fixture review surface ready</strong>
              <p>Preview mode renders a quiet proof surface here. Live mode replaces this with the served local program, app page, or artifact iframe.</p>
            </article>
          ) : (
            <article className="fluxos-flow-empty">
              <span>Live data only</span>
              <strong>No served preview artifact returned</strong>
              <p>The selected mission has live thread data, but no served HTML or artifact URL. Preview and Browser stay empty until the backend returns a real target.</p>
              <div className="fluxos-preview-empty-actions">
                <button onClick={() => onSetSurface?.("agent")} type="button">Open Agent thread</button>
                <button onClick={() => fluxioAction(onRequestAction, "workbench:run-artifact-check", { missionId: workbenchState?.missionId })} type="button">Run artifact check</button>
                <button onClick={() => fluxioAction(onRequestAction, "workbench:screenshot")} type="button">Capture proof</button>
              </div>
            </article>
          )}
        </div>
        {isLiveBackend ? (
          <div className={cx("fluxos-artifact-list", workbenchFocusMode && "is-focus-secondary")} aria-label="Live mission artifacts" data-live-workbench-secondary-panel="true">
            {artifacts.length > 0 ? artifacts.map(item => (
              <article key={item.id}>
                <span>{titleizeToken(item.status || "artifact")}</span>
                <strong>{item.title}</strong>
                {item.detail ? <p>{item.detail}</p> : null}
              </article>
            )) : (
              <article>
                <span>Live data only</span>
                <strong>No artifact rows returned</strong>
                <p>The selected mission has not returned planned scope artifacts yet. The live thread below is the current evidence source.</p>
              </article>
            )}
          </div>
        ) : null}
      </section>
      <section className={cx("fluxos-action-timeline", workbenchFocusMode && "is-focus-secondary")} data-live-workbench-secondary-panel="true">
        <div className="fluxos-section-head">
          <span>Runtime operations</span>
          <strong>Hermes and browser action timeline</strong>
        </div>
        <p className="fluxos-proof-line">
          {isLiveBackend
            ? "Runtime operations are shown only when the NAS mission summary or detail endpoint returns them."
            : "Runtime operations keep OpenClaw, Hermes, browser actions, screenshots, and replay evidence in one place."}
        </p>
        {(isLiveBackend ? operationRows : ["Open browser", "Navigate to /control", "Click Builder", "Capture screenshot", "Compare visual state"]).map((step, index) => {
          const item = typeof step === "string" ? { label: step, status: index < 3 ? "passed" : "awaiting verification" } : step;
          return (
          <article key={item.id || item.label || index}>
            <span>{item.timestamp ? timestampLabel(item.timestamp) : isLiveBackend ? titleizeToken(item.status || "live") : `10:${24 + index}:${String(12 + index * 3).padStart(2, "0")}`}</span>
            <strong>{item.label || item.title || item.kind || "Runtime operation"}</strong>
            <p>{item.detail || item.status || "No detail recorded."}</p>
          </article>
        );})}
        {isLiveBackend ? (
          operationRows.length === 0 ? (
            <article className="fluxos-flow-empty">
              <span>Live data only</span>
              <strong>No runtime operation rows loaded</strong>
              <p>Nothing is synthesized here; this panel waits for NAS proof events.</p>
            </article>
          ) : null
        ) : null}
      </section>
    </div>
  );
}

function FluxioPhoneProgressSurface({
  builderRows = [],
  liveDataStatus,
  notificationItems = [],
  onRequestAction,
  onSelectFlow,
  onSetSurface,
  overnightDigest = null,
  webPushState = null,
  workbenchState = null,
}) {
  const isLiveBackend = liveDataStatus?.previewMode === "live";
  const sourceMissionRows = asList(builderRows).length
    ? builderRows
    : asList(liveDataStatus?.missionRows).length
      ? liveDataStatus.missionRows
      : asList(liveDataStatus?.missions);
  const liveRows = isLiveBackend
    ? sortLiveBuilderRows(sourceMissionRows.map(normalizePhoneMissionRow).filter(Boolean))
    : [];
  const runningRows = liveRows.filter(row => {
    const status = String(row.status || row.statusLabel || "").toLowerCase();
    return status === "running" || status === "delegated" || status === "active";
  });
  const visibleRows = (runningRows.length ? runningRows : liveRows).slice(0, 3);
  const sourceNotifications = asList(notificationItems).length
    ? notificationItems
    : asList(liveDataStatus?.notificationRows).length
      ? liveDataStatus.notificationRows
      : asList(liveDataStatus?.notifications);
  const allNotifications = isLiveBackend ? asList(sourceNotifications) : [];
  const notifications = allNotifications.slice(0, 4);
  const sliceNotifications = notifications.filter(item => item.kind === "mission_slice_completed");
  const topRow = visibleRows[0] || null;
  const topProgressValue = clampPercent(topRow?.progress) ?? clampPercent(workbenchState?.progress?.value);
  const topProgressLabel = topProgressValue == null
    ? (workbenchState?.progress?.label || "Live mission state")
    : `${topProgressValue}% · ${workbenchState?.progress?.label || "Live progress"}`;
  const digest = overnightDigest && typeof overnightDigest === "object" ? overnightDigest : {};
  const delivery = digest?.delivery && typeof digest.delivery === "object" ? digest.delivery : {};
  const liveWebPush = liveDataStatus?.webPushStatus && typeof liveDataStatus.webPushStatus === "object"
    ? liveDataStatus.webPushStatus
    : {};
  const liveNtfy = liveDataStatus?.ntfyStatus && typeof liveDataStatus.ntfyStatus === "object"
    ? liveDataStatus.ntfyStatus
    : {};
  const liveSummaryReady = Boolean(
    liveDataStatus?.summaryReady ||
      liveDataStatus?.summarySchema ||
      liveDataStatus?.refreshedAt ||
      asList(liveDataStatus?.missionRows).length ||
      asList(liveDataStatus?.notificationRows).length,
  );
  const webPushSubscriptionCount = Number(
    liveWebPush.subscriptionCount ||
      delivery.webPushSubscriptionCount ||
      webPushState?.subscriptionCount ||
      0,
  );
  const webPushSenderConfigured = Boolean(
    liveWebPush.senderConfigured ||
      delivery.webPushSenderConfigured ||
      webPushState?.senderConfigured ||
      webPushState?.configured,
  );
  const webPushDependencyAvailable = Boolean(
    liveWebPush.dependencyAvailable ||
      delivery.webPushDependencyAvailable ||
      webPushState?.dependencyAvailable,
  );
  const webPushReady = Boolean(
    delivery.webPushReady ||
      (webPushSenderConfigured && webPushSubscriptionCount > 0) ||
      ["subscribed", "delivered"].includes(webPushState?.status),
  );
  const webPushStatus = webPushReady
    ? "ready"
    : webPushSenderConfigured
      ? "needs_subscription"
      : "needs_sender";
  const webPushHeadline = webPushReady
    ? "Closed-tab push is registered"
    : webPushSenderConfigured
      ? "Sender ready, register this browser"
      : "Provision Web Push sender";
  const webPushFailureStates = new Set([
    "service_worker_not_ready",
    "subscription_lookup_error",
    "subscription_failed",
    "record_failed",
    "error",
  ]);
  const webPushFailureMessage = webPushFailureStates.has(String(webPushState?.status || ""))
    ? webPushState?.message
    : "";
  const webPushDetail = webPushReady
    ? "This browser has a live subscription for closed-tab mission alerts."
    : webPushFailureMessage ||
      liveWebPush.nextAction ||
      delivery.webPushNextAction ||
      webPushState?.message ||
      (webPushSenderConfigured
        ? "Register this phone or tablet browser once to receive slice-complete alerts with the tab closed."
        : "Provision VAPID keys before browser subscriptions can be recorded.");
  const webPushAction = webPushSenderConfigured ? "Register browser" : "Provision push";
  const ntfyReady = Boolean(liveNtfy.senderConfigured || delivery.ntfyReady);
  const ntfyTopicConfigured = Boolean(liveNtfy.configured || delivery.ntfyTopicConfigured);
  const ntfyDetail = liveNtfy.nextAction || delivery.ntfyNextAction || (
    ntfyTopicConfigured
      ? "ntfy can receive mission updates through the iOS app."
      : "Configure an ntfy topic to use the open-source iOS push path."
  );
  const openMission = missionId => {
    const normalized = String(missionId || "").trim();
    if (!normalized) return;
    if (typeof onSelectFlow === "function") {
      onSelectFlow(normalized);
      return;
    }
      onSetSurface?.("agent");
  };
  const phoneMetrics = [
    ["Running", Number(liveDataStatus?.runningMissionCount || runningRows.length || 0), `${Number(liveDataStatus?.activeMissionCount || liveRows.length || 0)} active`],
    ["Alerts", Number(liveDataStatus?.notificationCount || allNotifications.length || 0), `${Number(liveDataStatus?.sliceNotificationCount || sliceNotifications.length || 0)} slice`],
    ["Queue", Number(liveDataStatus?.queuedMissionCount || 0), "live summary"],
    ["Blocked", Number(liveDataStatus?.blockedMissionCount || 0), "needs action"],
  ];

  if (!isLiveBackend) {
    return (
      <div className="fluxos-phone-progress unavailable" data-live-phone-progress="true">
        <section className="fluxos-phone-hero">
          <span>Phone progress</span>
          <strong>Live NAS unavailable</strong>
          <p>This surface does not render cached, fixture, or sample mission data. Reconnect to the NAS live backend to view mobile progress.</p>
        </section>
      </div>
    );
  }

  if (!liveSummaryReady && visibleRows.length === 0 && allNotifications.length === 0) {
    return (
      <div className="fluxos-phone-progress loading" data-live-phone-progress-loading="true">
        <section className="fluxos-phone-hero">
          <span>Phone progress</span>
          <strong>Loading NAS live summary</strong>
          <p>The phone surface is waiting for authenticated mission rows, notification rows, and push setup state before it renders live progress.</p>
        </section>
      </div>
    );
  }

  return (
    <div className="fluxos-phone-progress" data-live-phone-progress="true">
      <section className="fluxos-phone-hero">
        <span>Phone progress</span>
        <strong>{topRow?.name || topRow?.title || "Live NAS missions"}</strong>
        <p>
          {topRow?.turningPoint ||
            topRow?.detail ||
            "A compact live view for checking mission progress, slice notifications, and next actions away from the desktop."}
        </p>
        <div
          aria-atomic="true"
          aria-live="polite"
          className="fluxos-phone-status-row"
          data-phone-status-row="true"
          role="status"
        >
          <article>
            <span>Mission</span>
            <strong>{titleizeToken(topRow?.status || topRow?.statusLabel || "live")}</strong>
          </article>
          <article>
            <span>Progress</span>
            <strong>{topProgressLabel}</strong>
          </article>
          <article>
            <span>Push</span>
            <strong>{ntfyReady ? "ntfy ready" : webPushReady ? "Armed" : webPushSenderConfigured ? "Needs browser" : "Needs sender"}</strong>
          </article>
        </div>
        <div className="fluxos-phone-actions">
          <button disabled={!topRow?.id} onClick={() => openMission(topRow?.id || topRow?.missionId)} type="button">
            Open top mission
          </button>
          <button onClick={() => onSetSurface?.("builder")} type="button">Builder</button>
          <button onClick={() => fluxioAction(onRequestAction, "notifications:show-live-stack")} type="button">Notifications</button>
        </div>
      </section>

      <section className="fluxos-phone-metrics" aria-label="Live phone progress metrics">
        {phoneMetrics.map(([label, value, detail]) => (
          <article key={`phone-metric-${label}`}>
            <span>{label}</span>
            <strong>{value}</strong>
            <small>{detail}</small>
          </article>
        ))}
      </section>

      <section
        className={`fluxos-phone-push-proof status-${webPushStatus}`}
        aria-label="Closed-tab phone push proof"
        data-phone-web-push-proof="true"
        data-phone-web-push-status={webPushStatus}
      >
        <div>
          <span>Closed-tab push</span>
          <strong>{webPushHeadline}</strong>
          <p>{webPushDetail}</p>
          {!webPushReady && webPushState?.pushPermissionState ? (
            <small>Push API permission: {titleizeToken(webPushState.pushPermissionState)}</small>
          ) : null}
        </div>
        <div className="fluxos-phone-push-proof-grid">
          <article>
            <span>Sender</span>
            <strong>{webPushSenderConfigured ? "Ready" : "Missing"}</strong>
            <small>{webPushDependencyAvailable ? "dependency ready" : "dependency unknown"}</small>
          </article>
          <article>
            <span>Subscriptions</span>
            <strong>{webPushSubscriptionCount}</strong>
            <small>live NAS count</small>
          </article>
        </div>
        {!webPushReady ? (
          <button
            data-phone-web-push-action="true"
            onClick={() => fluxioAction(onRequestAction, webPushSenderConfigured ? "notifications:register-web-push" : "notifications:provision-web-push")}
            type="button"
          >
            {webPushAction}
          </button>
        ) : null}
      </section>

      <section
        className={`fluxos-phone-push-proof status-${ntfyReady ? "ready" : "needs_sender"}`}
        aria-label="ntfy phone push proof"
        data-phone-ntfy-proof="true"
        data-phone-ntfy-status={ntfyReady ? "ready" : "needs_topic"}
      >
        <div>
          <span>ntfy phone push</span>
          <strong>{ntfyReady ? "Open-source iOS channel ready" : "Configure ntfy topic"}</strong>
          <p>{ntfyDetail}</p>
        </div>
        <div className="fluxos-phone-push-proof-grid">
          <article>
            <span>Topic</span>
            <strong>{ntfyTopicConfigured ? "Set" : "Missing"}</strong>
            <small>live NAS config</small>
          </article>
          <article>
            <span>Token</span>
            <strong>{liveNtfy.tokenConfigured ? "Set" : "Optional"}</strong>
            <small>{liveNtfy.serverUrl || "ntfy server"}</small>
          </article>
        </div>
      </section>

      <section className="fluxos-phone-mission-list" aria-label="Live phone mission list">
        <div className="fluxos-thread-head">
          <span>Live missions</span>
          <strong>{visibleRows.length} shown</strong>
        </div>
        {visibleRows.length ? visibleRows.map(row => {
              const progressValue = row === topRow
                ? topProgressValue
                : clampPercent(row.progress);
          const missionId = row.id || row.missionId || row.mission_id || "";
          return (
            <button
              className={row.selected ? "active" : ""}
              data-phone-mission-card="true"
              key={missionId || row.name || row.title}
              onClick={() => openMission(missionId)}
              type="button"
            >
              <span>{titleizeToken(row.status || row.statusLabel || "live")}</span>
              <strong>{row.name || row.title || missionId || "Live mission"}</strong>
              <p>{row.turningPoint || row.detail || row.nextAction || "Waiting for the next live runtime update."}</p>
              <i aria-label={progressValue == null ? "No live percentage returned" : `Progress ${progressValue}%`}>
                <b style={{ width: progressValue == null ? "0%" : `${progressValue}%` }} />
              </i>
              <small>{progressValue == null ? "No %" : `${progressValue}%`} · {row.runtime || row.runtimeId || "runtime"}</small>
            </button>
          );
        }) : (
          <article className="fluxos-flow-empty">
            <span>Live data only</span>
            <strong>No live mission rows returned</strong>
            <p>The phone view is connected, but the NAS summary returned no mission rows for this refresh.</p>
          </article>
        )}
      </section>

      <section className="fluxos-phone-notifications" aria-label="Live phone notifications" data-phone-notification-stack="true">
        <div className="fluxos-thread-head">
          <span>Notifications</span>
          <strong>{notifications.length} of {allNotifications.length} visible</strong>
        </div>
        {notifications.length ? notifications.map(item => {
          const missionId = item.missionId || item.mission_id || "";
          const liveLead = firstMeaningfulNotificationLine(item);
          const title = liveLead || item.title || item.headline || item.label || "Mission update";
          const detail = item.agentMessage || item.detail || item.message || item.summary || "Live mission notification.";
          return (
            <button
              data-phone-notification-card="true"
              key={item.id || `${missionId}-${title}-${item.createdAt || item.timestamp || ""}`}
              onClick={() => openMission(missionId)}
              type="button"
            >
              <span>{item.kind === "mission_slice_completed" ? "Slice" : titleizeToken(item.kind || "Update")}</span>
              <strong>{title}</strong>
              {detail && detail !== title ? <p>{detail}</p> : null}
              <small>{timestampLabel(item.createdAt || item.timestamp || item.time || "")}</small>
            </button>
          );
        }) : (
          <article className="fluxos-flow-empty">
            <span>Live data only</span>
            <strong>No notifications visible</strong>
            <p>No fallback notification cards are rendered on the phone surface.</p>
          </article>
        )}
      </section>
    </div>
  );
}

function FluxioSettingsSurface({ activeTheme, onRequestAction, onSelectTheme, settingsState, themes = FLUXIO_THEMES }) {
  const activeTab = settingsState?.activeTab === "general" ? "workspace" : settingsState?.activeTab || "providers";
  const providers = Array.isArray(settingsState?.providers) ? settingsState.providers : [];
  const routeProviders = Array.isArray(settingsState?.routeOptions?.providers)
    ? settingsState.routeOptions.providers
    : [];
  const routeModels = Array.isArray(settingsState?.routeOptions?.models)
    ? settingsState.routeOptions.models
    : [];
  const routeEfforts = Array.isArray(settingsState?.routeOptions?.efforts)
    ? settingsState.routeOptions.efforts
    : [];
  const routeHarnesses = Array.isArray(settingsState?.routeOptions?.harnesses)
    ? settingsState.routeOptions.harnesses
    : [];
  const routingStrategies = Array.isArray(settingsState?.routeOptions?.routingStrategies)
    ? settingsState.routeOptions.routingStrategies
    : [];
  const executionTargets = Array.isArray(settingsState?.routeOptions?.executionTargets)
    ? settingsState.routeOptions.executionTargets
    : [];
  const codexImportItems = asList(settingsState?.codexImport?.workspaces || settingsState?.codexImport?.items);
  const setupServices = asList(settingsState?.setupServices);
  const setupCards = asList(settingsState?.beginnerSetupCards);
  const runtimes = asList(settingsState?.runtimes);
  const bridgeSessions = asList(settingsState?.bridgeSessions);
  const harnessBenchmarkBoard =
    settingsState?.harnessBenchmarkBoard && typeof settingsState.harnessBenchmarkBoard === "object"
      ? settingsState.harnessBenchmarkBoard
      : {};
  const harnessBenchmarkRows = asList(harnessBenchmarkBoard.matrix);
  const harnessBenchmarkBlockers = asList(harnessBenchmarkBoard.blockers);
  const harnessBenchmarkProofPath = String(harnessBenchmarkBoard?.proof?.artifactPath || "").trim();
  const harnessBenchmarkStatus = String(harnessBenchmarkBoard.status || "pending_live_capture");
  const harnessBenchmarkRecommendations = asList(harnessBenchmarkBoard.taskClassRecommendations);
  const harnessBenchmarkRoutingRules = asList(harnessBenchmarkBoard.routingRules);
  const harnessBenchmarkDecision =
    harnessBenchmarkBoard.decision && typeof harnessBenchmarkBoard.decision === "object"
      ? harnessBenchmarkBoard.decision
      : {};
  const updateManagementReadiness =
    settingsState?.updateManagementReadiness && typeof settingsState.updateManagementReadiness === "object"
      ? settingsState.updateManagementReadiness
      : {};
  const updateComponents = asList(updateManagementReadiness.components);
  const updateWorkflow = asList(updateManagementReadiness.safeUpgradeWorkflow);
  const updateBlockers = asList(updateManagementReadiness.blockers);
  const updateWarnings = asList(updateManagementReadiness.compatibilityWarnings);
  const updateFamilyPlan = asList(updateManagementReadiness.updateFamilyPlan);
  const updateReleaseChannels = asList(updateManagementReadiness.releaseChannels);
  const updateDependencyRows = asList(updateManagementReadiness.dependencyRows);
  const updateOutdatedCheck = updateManagementReadiness.outdatedCheck && typeof updateManagementReadiness.outdatedCheck === "object"
    ? updateManagementReadiness.outdatedCheck
    : {};
  const updateAuditCheck = updateManagementReadiness.auditCheck && typeof updateManagementReadiness.auditCheck === "object"
    ? updateManagementReadiness.auditCheck
    : {};
  const updateMissionGate = updateManagementReadiness.missionGate && typeof updateManagementReadiness.missionGate === "object"
    ? updateManagementReadiness.missionGate
    : {};
  const updateProofPath = String(updateManagementReadiness?.proof?.artifactPath || "").trim();
  const updateStatus = String(updateManagementReadiness.status || "pending_live_capture");
  const prStackLandingReadiness =
    settingsState?.prStackLandingReadiness && typeof settingsState.prStackLandingReadiness === "object"
      ? settingsState.prStackLandingReadiness
      : {};
  const prStackLandingSummary =
    prStackLandingReadiness.summary && typeof prStackLandingReadiness.summary === "object"
      ? prStackLandingReadiness.summary
      : {};
  const prStackLandingStack =
    prStackLandingReadiness.stack && typeof prStackLandingReadiness.stack === "object"
      ? prStackLandingReadiness.stack
      : {};
  const prStackLandingFrontier =
    prStackLandingReadiness.landingFrontier && typeof prStackLandingReadiness.landingFrontier === "object"
      ? prStackLandingReadiness.landingFrontier
      : {};
  const prStackLandingRows = asList(prStackLandingReadiness.landingSequence);
  const prStackLandingBlockers = asList(prStackLandingReadiness.blockers);
  const prStackLandingProofPath = String(prStackLandingReadiness?.proof?.artifactPath || "").trim();
  const prStackLandingStatus = String(prStackLandingReadiness.status || "pending_live_capture");
  const prStackLandingContinuation =
    prStackLandingReadiness.continuationPolicy && typeof prStackLandingReadiness.continuationPolicy === "object"
      ? prStackLandingReadiness.continuationPolicy
      : {};
  const automationOverlapStatus =
    settingsState?.automationOverlapStatus && typeof settingsState.automationOverlapStatus === "object"
      ? settingsState.automationOverlapStatus
      : {};
  const automationOverlapChecks = asList(automationOverlapStatus.checks);
  const automationOverlapProofPath = String(automationOverlapStatus?.proof?.artifactPath || "").trim();
  const automationOverlapTone = String(automationOverlapStatus.tone || "warn");
  const automationOverlapStatusLabel = String(automationOverlapStatus.status || "pending_live_capture");
  const fusionReadiness =
    settingsState?.fusionReadiness && typeof settingsState.fusionReadiness === "object"
      ? settingsState.fusionReadiness
      : {};
  const fusionProjects = asList(fusionReadiness.projects);
  const fusionBlockers = asList(fusionReadiness.blockers);
  const fusionOverlapMap = asList(fusionReadiness.overlapMap);
  const fusionDecisions = asList(fusionReadiness.fusionDecisions);
  const fusionMigrationPlan = asList(fusionReadiness.migrationPlan);
  const fusionMissionGate = fusionReadiness.missionGate && typeof fusionReadiness.missionGate === "object"
    ? fusionReadiness.missionGate
    : {};
  const fusionProofPath = String(fusionReadiness?.proof?.artifactPath || "").trim();
  const jbhEavenReadiness =
    settingsState?.jbhEavenReadiness && typeof settingsState.jbhEavenReadiness === "object"
      ? settingsState.jbhEavenReadiness
      : {};
  const jbhScenarioGate =
    jbhEavenReadiness.scenarioGate && typeof jbhEavenReadiness.scenarioGate === "object"
      ? jbhEavenReadiness.scenarioGate
      : {};
  const jbhProject =
    jbhEavenReadiness.project && typeof jbhEavenReadiness.project === "object"
      ? jbhEavenReadiness.project
      : {};
  const jbhMissionGate =
    jbhEavenReadiness.missionGate && typeof jbhEavenReadiness.missionGate === "object"
      ? jbhEavenReadiness.missionGate
      : {};
  const jbhFakeTarget =
    jbhEavenReadiness.fakeTargetBoundary && typeof jbhEavenReadiness.fakeTargetBoundary === "object"
      ? jbhEavenReadiness.fakeTargetBoundary
      : {};
  const jbhSafeTemplates = asList(jbhEavenReadiness.safeScenarioTemplates);
  const jbhScoringRubric = asList(jbhEavenReadiness.scoringRubric);
  const jbhReadinessChecks = asList(jbhEavenReadiness.readinessChecks);
  const jbhWarnings = asList(jbhEavenReadiness.warnings);
  const jbhRefusalAnalysis =
    jbhEavenReadiness.refusalAnalysis && typeof jbhEavenReadiness.refusalAnalysis === "object"
      ? jbhEavenReadiness.refusalAnalysis
      : {};
  const jbhAgentRun =
    jbhEavenReadiness.agentRun && typeof jbhEavenReadiness.agentRun === "object"
      ? jbhEavenReadiness.agentRun
      : {};
  const jbhBlockers = asList(jbhEavenReadiness.blockers);
  const jbhProofPath = String(jbhEavenReadiness?.proof?.artifactPath || "").trim();
  const voiceAccessibilityReadiness =
    settingsState?.voiceAccessibilityReadiness && typeof settingsState.voiceAccessibilityReadiness === "object"
      ? settingsState.voiceAccessibilityReadiness
      : {};
  const voiceAccessChecks = asList(voiceAccessibilityReadiness.checks);
  const voiceAccessProofPath = String(voiceAccessibilityReadiness?.proof?.artifactPath || "").trim();
  const voiceAccessStatus = String(voiceAccessibilityReadiness.status || "pending_live_capture");
  const voiceInput = voiceAccessibilityReadiness.voiceInput && typeof voiceAccessibilityReadiness.voiceInput === "object"
    ? voiceAccessibilityReadiness.voiceInput
    : {};
  const voiceAccessA11y = voiceAccessibilityReadiness.accessibility && typeof voiceAccessibilityReadiness.accessibility === "object"
    ? voiceAccessibilityReadiness.accessibility
    : {};
  const subagentMonitoringReadiness =
    settingsState?.subagentMonitoringReadiness && typeof settingsState.subagentMonitoringReadiness === "object"
      ? settingsState.subagentMonitoringReadiness
      : {};
  const subagentRoles = asList(subagentMonitoringReadiness.roles);
  const subagentControls = asList(subagentMonitoringReadiness.controls);
  const subagentChecks = asList(subagentMonitoringReadiness.checks);
  const subagentMonitoringPolicy =
    subagentMonitoringReadiness.monitoringPolicy && typeof subagentMonitoringReadiness.monitoringPolicy === "object"
      ? subagentMonitoringReadiness.monitoringPolicy
      : {};
  const subagentMergePolicy =
    subagentMonitoringReadiness.mergePolicy && typeof subagentMonitoringReadiness.mergePolicy === "object"
      ? subagentMonitoringReadiness.mergePolicy
      : {};
  const subagentProofPath = String(subagentMonitoringReadiness?.proof?.artifactPath || "").trim();
  const subagentStatus = String(subagentMonitoringReadiness.status || "pending_live_capture");
  const readyProviderCount = providers.filter(item => item.status || item.hasSecret).length;
  const providerOrchestration =
    settingsState?.providerOrchestration && typeof settingsState.providerOrchestration === "object"
      ? settingsState.providerOrchestration
      : {};
  const providerRoute =
    providerOrchestration?.selectedRoute && typeof providerOrchestration.selectedRoute === "object"
      ? providerOrchestration.selectedRoute
      : {};
  const providerRouteScorecard =
    providerRoute?.scorecard && typeof providerRoute.scorecard === "object"
      ? providerRoute.scorecard
      : {};
  const providerRoutePolicy =
    providerOrchestration?.routePolicy && typeof providerOrchestration.routePolicy === "object"
      ? providerOrchestration.routePolicy
      : {};
  const orchestrationProviders = asList(providerOrchestration?.providers).slice(0, 4);
  const orchestrationProofPath = String(providerOrchestration?.proof?.artifactPath || "").trim();
  const orchestrationStatus = String(providerRoute.health || providerOrchestration.status || "pending_live_capture");
  const orchestrationReady = Boolean(orchestrationProofPath || !orchestrationStatus.includes("pending"));
  const openSettingsTab = tabId => {
    settingsState?.onSetTab?.(tabId);
  };
  const settingSections = [
    {
      id: "providers",
      label: "Models & Accounts",
      status: providers.length ? `${readyProviderCount}/${providers.length} ready` : "Not reported",
      detail: "Provider keys, OAuth links, model routes, and thinking effort.",
    },
    {
      id: "workspace",
      label: "Workspace",
      status: settingsState?.workspaceName || "Local workspace",
      detail: "Local folder, Codex import, NAS bridge, and file routing.",
    },
    {
      id: "updates",
      label: "Updates",
      status: titleizeToken(updateStatus),
      detail: "Dependency, provider/model, runtime adapter, and app-shell update readiness.",
    },
    {
      id: "appearance",
      label: "Appearance",
      status: themes.find(theme => theme.id === activeTheme)?.label || activeTheme,
      detail: "Theme, density, contrast, and command feel.",
    },
    {
      id: "voice-access",
      label: "Voice & Access",
      status: titleizeToken(voiceAccessStatus),
      detail: "Dictation repair, accidental-send protection, keyboard path, contrast, and motion controls.",
    },
    {
      id: "rules",
      label: "Rules & Routing",
      status: settingsState?.activeRuleSet?.name || "Default policy",
      detail: "Approval policy, route strategy, runtime target, and safeguards.",
    },
    {
      id: "runtimes",
      label: "Runtimes & Rooms",
      status: runtimes.length ? `${runtimes.length} runtimes` : "Not reported",
      detail: "Hermes, OpenClaw, bridge sessions, and rooms/gateways.",
    },
    {
      id: "databases",
      label: "Databases",
      status: `${FLUXIO_DATABASES.length} stores`,
      detail: "Runs, memory, receipts, artifacts, and app data.",
    },
    {
      id: "team",
      label: "Team Manager",
      status: subagentProofPath ? "Monitoring ready" : (subagentRoles.length ? `${subagentRoles.length} role lanes` : "Setup"),
      detail: "Subagent roles, monitor activation, cancellation, proof merge, and account readiness.",
    },
  ];
  const activeSection = settingSections.find(item => item.id === activeTab) || settingSections[0];
  const renderActionButton = (label, onClick, extra = {}) => (
    <button disabled={extra.disabled} key={extra.key} onClick={onClick} title={extra.title || ""} type="button">
      {label}
    </button>
  );
  const renderOptionChips = values => (
    <div className="fluxos-settings-chip-row">
      {asList(values).slice(0, 12).map(item => (
        <span key={item.value || item.label || item}>{item.label || item.value || item}</span>
      ))}
      {asList(values).length > 12 ? <span>+{asList(values).length - 12} more</span> : null}
    </div>
  );
  const renderProviderSettings = () => (
    <div className="fluxos-settings-section-body" data-settings-models-accounts="true">
      <div className="fluxos-settings-route-summary" data-settings-route-models="true">
        <article>
          <span>Providers</span>
          <strong>{routeProviders.map(item => item.label || item.value).join(" / ") || "Not reported"}</strong>
        </article>
        <article>
          <span>Models</span>
          <strong>{routeModels.slice(0, 6).join(" / ") || "Not reported"}</strong>
          <p>{routeModels.length} model route options, including OpenCodeGo when configured.</p>
        </article>
        <article>
          <span>Thinking</span>
          <strong>{routeEfforts.map(item => item.label || item.value).join(" / ") || "Not reported"}</strong>
        </article>
      </div>
      <section
        className={cx("fluxos-provider-orchestration", orchestrationReady ? "ready" : "pending")}
        data-provider-orchestration-contract="true"
        data-provider-orchestration-primary-lane={providerOrchestration.primaryRuntimeLane || "hermes"}
        data-provider-orchestration-schema={providerOrchestration.schema || "fluxio.provider_orchestration_contract.v1"}
      >
        <div className="fluxos-provider-orchestration-head">
          <div>
            <span>Provider orchestration</span>
            <strong>
              {providerRoute.provider || "Route not captured"} / {providerRoute.model || "model pending"}
            </strong>
            <p>
              Hermes is the primary lane. OpenClaw and OpenCode stay attached as fallback proof lanes when the selected route cannot run.
            </p>
          </div>
          <button
            className="fluxos-provider-proof-button"
            onClick={() => fluxioAction(onRequestAction, "providers:capture-orchestration-contract", {
              taskBrief: "Select the best provider/model route for Fluxio provider orchestration and model switching.",
            })}
            type="button"
          >
            Capture route proof
          </button>
        </div>
        <div className="fluxos-provider-route-health">
          <article>
            <span>Selected role</span>
            <strong>{titleizeToken(providerRoute.role || providerOrchestration.selectedRole || "router")}</strong>
          </article>
          <article>
            <span>Health</span>
            <strong>{titleizeToken(orchestrationStatus)}</strong>
          </article>
          <article>
            <span>Required capability</span>
            <strong>{asList(providerOrchestration.requiredCapabilities).slice(0, 3).join(" / ") || "provider_exploration"}</strong>
          </article>
          <article>
            <span>Fallback lanes</span>
            <strong>{asList(providerRoute.fallbackRuntimeLanes || providerOrchestration.fallbackRuntimeLanes).join(" / ") || "openclaw / opencode"}</strong>
          </article>
          <article>
            <span>Route score</span>
            <strong>{providerRoute.score ?? providerRouteScorecard.score ?? "pending"}</strong>
          </article>
          <article>
            <span>Cost / speed / context</span>
            <strong>
              {[providerRouteScorecard.costScore, providerRouteScorecard.speedScore, providerRouteScorecard.contextScore]
                .filter(value => value !== undefined && value !== null)
                .join(" / ") || "pending"}
            </strong>
          </article>
        </div>
        <div className="fluxos-provider-route-policy" aria-label="Provider route policy">
          <span>{providerRoutePolicy.healthGate || "Ready routes execute; auth-required routes stay recommendations."}</span>
          <small>{providerRoutePolicy.switchRule || "Switch when the active provider/model is weaker than the selected route."}</small>
        </div>
        {orchestrationProviders.length ? (
          <div className="fluxos-provider-route-list">
            {orchestrationProviders.map(item => {
              const providerId = item.provider || item.id || item.label || "provider";
              const itemScorecard = item.scorecard && typeof item.scorecard === "object" ? item.scorecard : {};
              return (
                <article className={cx("fluxos-provider-route-card", item.authPresent && "ready")} key={providerId}>
                  <span>{titleizeToken(item.health || (item.authPresent ? "ready" : "auth_required"))}</span>
                  <strong>{item.label || titleizeToken(providerId)} · {item.score ?? itemScorecard.score ?? "?"}</strong>
                  <p>{asList(item.models).slice(0, 2).join(" / ") || "Model list not reported"}</p>
                  <small>
                    {asList(item.matchedCapabilities).length
                      ? `Matched ${asList(item.matchedCapabilities).join(" / ")}`
                      : asList(item.capabilities).slice(0, 4).join(" / ") || item.useWhen || "Capabilities not reported"}
                  </small>
                </article>
              );
            })}
          </div>
        ) : null}
        <p className="fluxos-provider-orchestration-foot">
          {orchestrationProofPath
            ? `Proof artifact: ${orchestrationProofPath}`
            : providerOrchestration.nextAction || "Capture live route proof before claiming provider orchestration executed."}
        </p>
      </section>
      <div className="fluxos-settings-provider-grid" data-settings-provider-grid="true">
        {providers.map(provider => {
          const ready = Boolean(provider.status || provider.hasSecret);
          return (
            <article
              className={`fluxos-settings-provider-card tone-${ready ? "good" : "warn"}`}
              data-settings-provider-row={provider.id}
              key={provider.id}
            >
              <div>
                <span>{provider.env}</span>
                <strong>{provider.label}</strong>
                <p>{provider.note}</p>
              </div>
              <em>{provider.statusLabel || (ready ? "Ready" : "Needs login")}</em>
              {provider.statusDetail ? <p>{provider.statusDetail}</p> : null}
              <div className="fluxos-settings-provider-actions">
                {provider.quickAuth ? renderActionButton(
                  provider.quickAuth.ready ? `${provider.label} connected` : provider.quickAuth.label,
                  () => provider.onQuickAuth?.(),
                  { disabled: provider.quickAuth.disabled || !provider.onQuickAuth, title: provider.quickAuth.detail },
                ) : null}
                {asList(provider.authLinks).map(link => {
                  const linkLabel = link.label || (provider.id === "opencode-go" ? "OpenCodeGo provider docs" : "Provider docs");
                  return renderActionButton(linkLabel, () => link.onClick?.(), {
                    key: `${provider.id}-${linkLabel}`,
                    title: provider.id === "opencode-go" ? "OpenCodeGo provider docs" : linkLabel,
                  });
                })}
              </div>
              <label>
                <span>{provider.label} API key</span>
                <input
                  autoComplete="off"
                  onChange={event => provider.onDraftChange?.(event.target.value)}
                  placeholder={provider.hasSecret ? "Stored" : "Paste API key"}
                  type="password"
                  value={provider.draft || ""}
                />
              </label>
              <div className="fluxos-settings-provider-actions">
                {renderActionButton(provider.savingState === "saving" ? "Saving..." : "Save key", () => provider.onSave?.(), {
                  disabled: provider.savingState === "saving",
                })}
                {renderActionButton(provider.savingState === "clearing" ? "Clearing..." : "Clear key", () => provider.onClear?.(), {
                  disabled: provider.savingState === "clearing",
                })}
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
  const renderUpdateSettings = () => (
    <div className="fluxos-settings-section-body" data-settings-updates-panel="true">
      <section
        className={cx("fluxos-update-readiness", updateProofPath && "ready")}
        data-update-management-readiness="true"
        data-update-management-primary-lane={updateManagementReadiness.primaryRuntimeLane || "hermes"}
        data-update-management-schema={updateManagementReadiness.schema || "fluxio.update_management_readiness.v1"}
      >
        <div className="fluxos-update-readiness-head">
          <div>
            <span>Update management</span>
            <strong>{titleizeToken(updateStatus)}</strong>
            <p>
              Safe updates are treated as release work: one family at a time, Hermes-first runtime proof,
              reviewable rollback, and no automatic upgrade claims without live evidence.
            </p>
          </div>
          <button
            className="fluxos-update-proof-button"
            onClick={() => fluxioAction(onRequestAction, "updates:capture-readiness")}
            type="button"
          >
            Capture update proof
          </button>
        </div>
        <div className="fluxos-update-decision-strip" aria-label="Update decision summary">
          <article>
            <span>Mission gate</span>
            <strong>{titleizeToken(updateMissionGate.status || "pending_live_capture")}</strong>
            <p>{updateMissionGate.mission || "Mission 12 update readiness has not run yet."}</p>
          </article>
          <article>
            <span>Registry check</span>
            <strong>{Number(updateOutdatedCheck.outdatedCount || 0)} update{Number(updateOutdatedCheck.outdatedCount || 0) === 1 ? "" : "s"}</strong>
            <p>{titleizeToken(updateOutdatedCheck.status || "not_requested")}</p>
          </article>
          <article>
            <span>Audit check</span>
            <strong>{Number(updateAuditCheck.vulnerabilityTotal || 0)} finding{Number(updateAuditCheck.vulnerabilityTotal || 0) === 1 ? "" : "s"}</strong>
            <p>{titleizeToken(updateAuditCheck.status || "not_requested")}</p>
          </article>
          <article>
            <span>Rollback</span>
            <strong>{updateFamilyPlan.length || 4} family plans</strong>
            <p>Every update family keeps an explicit rollback path.</p>
          </article>
        </div>
        <div className="fluxos-update-component-grid" aria-label="Update readiness components">
          {updateComponents.slice(0, 5).map(component => (
            <article
              className={cx(
                component.status === "ready" && "ready",
                component.status === "blocked" && "blocked",
                component.status === "review_required" && "review",
              )}
              key={component.id || component.label}
            >
              <span>{titleizeToken(component.status || "pending")}</span>
              <strong>{component.label || titleizeToken(component.id || "component")}</strong>
              <p>{component.detail || component.safeAction || "No update readiness detail captured yet."}</p>
              <small>{component.currentVersion || "current version pending"} to {component.latestVersion || "latest version pending"}</small>
              {component.safeAction ? <em>{component.safeAction}</em> : null}
            </article>
          ))}
        </div>
        <div className="fluxos-update-warning-rail" aria-label="Compatibility warnings">
          {(updateWarnings.length ? updateWarnings : [
            {
              id: "no-warnings",
              severity: "ready",
              message: "No compatibility warnings captured yet.",
              repair: "Capture update proof before promoting changes.",
            },
          ]).slice(0, 4).map(item => (
            <article className={cx(item.severity === "blocker" && "blocked", item.severity === "attention" && "attention")} key={item.id || item.message}>
              <span>{titleizeToken(item.severity || "review")}</span>
              <strong>{item.message || "Compatibility warning"}</strong>
              <p>{item.repair || "Review before update promotion."}</p>
            </article>
          ))}
        </div>
        <div className="fluxos-update-family-plan" aria-label="Safe update family plan">
          {(updateFamilyPlan.length ? updateFamilyPlan : [
            { id: "dependencies", label: "Dependencies", risk: "medium", command: "npm ci && npm run frontend:build", rollback: "Revert package and lockfile together." },
          ]).slice(0, 4).map(item => (
            <article key={item.id || item.label}>
              <span>{titleizeToken(item.risk || "review")} risk</span>
              <strong>{item.label || titleizeToken(item.id || "update family")}</strong>
              <p>{item.command || "Proof command pending."}</p>
              <small>{item.rollback || "Rollback path pending."}</small>
            </article>
          ))}
        </div>
        <div className="fluxos-update-proof-grid">
          <article>
            <span>Primary lane</span>
            <strong>{titleizeToken(updateManagementReadiness.primaryRuntimeLane || "hermes")}</strong>
            <p>
              {asList(updateManagementReadiness.fallbackRuntimeLanes).length
                ? `Fallback: ${asList(updateManagementReadiness.fallbackRuntimeLanes).join(" / ")}`
                : "Fallback lanes pending live capture."}
            </p>
          </article>
          <article>
            <span>Proof</span>
            <strong>{updateProofPath ? "Captured" : "Not captured"}</strong>
            <p>{updateProofPath || updateBlockers[0] || updateManagementReadiness.nextAction || "Capture live readiness before updating."}</p>
          </article>
          <article>
            <span>Workflow</span>
            <strong>{updateWorkflow.map(item => titleizeToken(item.step)).slice(0, 4).join(" / ") || "Snapshot / Isolate / Verify / Rollback"}</strong>
            <p>{updateWorkflow[0]?.detail || "Capture current state before changing dependencies, models, runtimes, or app shell."}</p>
          </article>
          <article>
            <span>Release channels</span>
            <strong>{updateReleaseChannels.length || 3} guarded channels</strong>
            <p>{updateReleaseChannels[0]?.rollback || "Rollback path is required before promotion."}</p>
          </article>
          <article>
            <span>Dependency rows</span>
            <strong>{updateDependencyRows.length} tracked</strong>
            <p>{updateDependencyRows.find(item => item.status === "update_available")?.name || "No package update row selected yet."}</p>
          </article>
        </div>
      </section>
      <section
        className={cx("fluxos-pr-stack-landing", prStackLandingProofPath && "ready", !prStackLandingReadiness.ok && "attention")}
        data-pr-stack-landing-readiness="true"
        data-pr-stack-landing-primary-lane={prStackLandingReadiness.primaryRuntimeLane || "hermes"}
        data-pr-stack-landing-schema={prStackLandingReadiness.schema || "fluxio.pr_stack_landing_readiness.v1"}
        data-pr-stack-continuation-state={prStackLandingContinuation.state || "pending_live_capture"}
      >
        <div className="fluxos-pr-stack-landing-head">
          <div>
            <span>PR landing readiness</span>
            <strong>{titleizeToken(prStackLandingStatus)}</strong>
            <p>
              Ordered merge proof for the mission stack. Hermes is the primary lane; OpenClaw and OpenCode remain fallback metadata for route verification.
            </p>
          </div>
          <button
            className="fluxos-pr-stack-landing-proof-button"
            onClick={() => fluxioAction(onRequestAction, "pr-stack:capture-landing-readiness")}
            type="button"
          >
            Capture PR proof
          </button>
        </div>
        <div className="fluxos-pr-stack-landing-grid" aria-label="PR landing readiness summary">
          <article>
            <span>Landing frontier</span>
            <strong>{prStackLandingFrontier.number ? `PR${prStackLandingFrontier.number}` : "Not captured"}</strong>
            <p>{asList(prStackLandingFrontier.blockers).join(" / ") || prStackLandingBlockers[0] || "No frontier blocker captured yet."}</p>
          </article>
          <article>
            <span>Stack</span>
            <strong>{`${prStackLandingStack.longestChainLength || 0} PR chain`}</strong>
            <p>{prStackLandingRows.slice(0, 6).map(row => `#${row.number}`).join(" -> ") || "Landing order pending."}</p>
          </article>
          <article>
            <span>Checks</span>
            <strong>{`${prStackLandingSummary.releaseProofPassedCount || 0} green / ${prStackLandingSummary.blockedCount || 0} blocked`}</strong>
            <p>{`${prStackLandingSummary.cleanCount || 0} clean, ${prStackLandingSummary.draftCount || 0} draft.`}</p>
          </article>
          <article>
            <span>Route</span>
            <strong>{titleizeToken(prStackLandingReadiness.primaryRuntimeLane || "hermes")}</strong>
            <p>{asList(prStackLandingReadiness.fallbackRuntimeLanes).join(" / ") || "openclaw / opencode"}</p>
          </article>
          <article>
            <span>Continuation</span>
            <strong>{titleizeToken(prStackLandingContinuation.state || "pending")}</strong>
            <p>
              {prStackLandingContinuation.nextCompartmentAction
                || prStackLandingReadiness.nextAction
                || "Capture PR landing readiness before choosing the next mission."}
            </p>
          </article>
        </div>
        {prStackLandingRows.length ? (
          <div className="fluxos-pr-stack-landing-sequence" aria-label="PR landing order">
            {prStackLandingRows.slice(0, 5).map(row => (
              <article className={cx(row.ready && "ready", asList(row.blockers).length && "blocked")} key={row.number || row.headRefName}>
                <span>{row.number ? `PR${row.number}` : "PR"}</span>
                <strong>{row.title || row.headRefName || "Untitled pull request"}</strong>
                <p>{asList(row.blockers).join(" / ") || `${titleizeToken(row.releaseProofStatus || "unknown")} release proof`}</p>
              </article>
            ))}
          </div>
        ) : null}
        <p className="fluxos-pr-stack-landing-foot">
          {prStackLandingProofPath
            ? `Proof artifact: ${prStackLandingProofPath}`
            : prStackLandingReadiness.nextAction || "Capture PR landing readiness before merging the stacked mission PRs."}
        </p>
      </section>
    </div>
  );
  const renderWorkspaceSettings = () => (
    <div className="fluxos-settings-section-body" data-settings-workspace-panel="true">
      <div className="fluxos-settings-fact-grid">
        <article><span>Name</span><strong>{settingsState?.workspaceName || "Workspace"}</strong></article>
        <article><span>ID</span><strong>{settingsState?.workspaceId || "Not reported"}</strong></article>
        <article><span>Storage bridge</span><strong>{settingsState?.storageBridge?.status || settingsState?.storageBridge?.state || "Not reported"}</strong></article>
      </div>
      <div className="fluxos-settings-action-row">
        {renderActionButton("Pick workspace folder", () => settingsState?.onPickWorkspaceFolder?.())}
        {renderActionButton("Refresh Codex workspaces", () => settingsState?.onRefreshCodexImport?.())}
        {renderActionButton("Import all Codex workspaces", () => settingsState?.onImportAllCodexWorkspaces?.())}
      </div>
      <div className="fluxos-settings-list">
        {codexImportItems.length ? codexImportItems.slice(0, 6).map(item => (
          <button key={item.id || item.path || item.name} onClick={() => settingsState?.onImportCodexWorkspace?.(item)} type="button">
            <span>{item.name || item.label || "Codex workspace"}</span>
            <strong>{item.path || item.root || item.id || "No path reported"}</strong>
          </button>
        )) : (
          <article><span>Codex import</span><strong>No imported workspaces reported</strong></article>
        )}
      </div>
    </div>
  );
  const renderAppearanceSettings = () => (
    <div className="fluxos-settings-section-body" data-settings-appearance-panel="true">
      <div className="fluxos-theme-grid" aria-label="Theme preview cards">
        {themes.map(theme => (
          <button
            aria-pressed={activeTheme === theme.id}
            className={activeTheme === theme.id ? "active" : ""}
            data-preview-theme={theme.id}
            key={theme.id}
            onClick={() => onSelectTheme?.(theme.id)}
            type="button"
          >
            <span className="fluxos-theme-preview" aria-hidden="true"><i /><b /><em /></span>
            <strong>{theme.label}</strong>
            <small>{theme.bestFor}</small>
          </button>
        ))}
      </div>
    </div>
  );
  const renderVoiceAccessSettings = () => (
    <div className="fluxos-settings-section-body" data-settings-voice-access-panel="true">
      <section
        className={cx("fluxos-voice-access-readiness", voiceAccessProofPath && "ready")}
        data-voice-accessibility-readiness="true"
        data-voice-accessibility-schema={voiceAccessibilityReadiness.schema || "fluxio.voice_accessibility_readiness.v1"}
      >
        <div className="fluxos-voice-access-head">
          <div>
            <span>Voice and accessibility readiness</span>
            <strong>{titleizeToken(voiceAccessStatus)}</strong>
            <p>
              Dictation uses the system speech route, then Fluxio protects the send path with ambiguity review,
              correction cleanup, keyboard repair, focus visibility, and motion/contrast controls.
            </p>
          </div>
          <button
            className="fluxos-voice-access-proof-button"
            onClick={() => fluxioAction(onRequestAction, "voice-access:capture-readiness")}
            type="button"
          >
            Capture voice proof
          </button>
        </div>
        <div className="fluxos-voice-access-grid" aria-label="Voice and accessibility controls">
          <article>
            <span>Voice input</span>
            <strong>{voiceInput.localSttConfigured ? "Local STT" : "OS dictation bridge"}</strong>
            <p>{voiceInput.osFallbackHint || "Use OS dictation, then review the command before sending."}</p>
          </article>
          <article>
            <span>Send gate</span>
            <strong>{voiceInput.accidentalSendProtection === false ? "Manual" : "Protected"}</strong>
            <p>{voiceInput.commandAmbiguityDetection === false ? "Capture proof to confirm ambiguity detection." : "Ambiguity markers open the correction buffer first."}</p>
          </article>
          <article>
            <span>Keyboard path</span>
            <strong>{voiceAccessA11y.keyboardRepairPath === false ? "Pending" : "Ready"}</strong>
            <p>Ctrl+Shift+M opens voice review; Ctrl+Enter sends after review; Escape closes the buffer.</p>
          </article>
          <article>
            <span>Access controls</span>
            <strong>
              {[
                voiceAccessA11y.reducedMotionControl !== false && "Motion",
                voiceAccessA11y.highContrastControl !== false && "Contrast",
                voiceAccessA11y.largerTargetsControl !== false && "Targets",
              ].filter(Boolean).join(" / ") || "Pending"}
            </strong>
            <p>Controls are visible at the composer and do not require hunting through hidden settings.</p>
          </article>
        </div>
        <div className="fluxos-voice-access-checks">
          {(voiceAccessChecks.length ? voiceAccessChecks : [
            { id: "review-before-send", label: "Review before send", status: "pending" },
            { id: "correction-buffer", label: "Correction buffer", status: "pending" },
            { id: "keyboard-repair-path", label: "Keyboard repair path", status: "pending" },
            { id: "accessible-status", label: "Accessible status", status: "pending" },
          ]).slice(0, 5).map(check => (
            <span key={check.id || check.label}>
              <strong>{check.label || titleizeToken(check.id || "check")}</strong>
              <em>{titleizeToken(check.status || "pending")}</em>
            </span>
          ))}
        </div>
        <p className="fluxos-voice-access-foot">
          {voiceAccessProofPath
            ? `Proof artifact: ${voiceAccessProofPath}`
            : voiceAccessibilityReadiness.nextAction || "Capture voice/accessibility proof before calling this workflow ready."}
        </p>
      </section>
    </div>
  );
  const renderRulesSettings = () => (
    <div className="fluxos-settings-section-body" data-settings-rules-panel="true">
      <section
        className={cx("fluxos-automation-overlap", automationOverlapProofPath && "ready", automationOverlapTone === "warn" && "attention")}
        data-automation-overlap-status="true"
        data-automation-overlap-schema={automationOverlapStatus.schema || "fluxio.automation_overlap_status.v1"}
        data-automation-overlap-decision={automationOverlapStatusLabel}
      >
        <div className="fluxos-automation-overlap-head">
          <div>
            <span>Automation overlap guard</span>
            <strong>{titleizeToken(automationOverlapStatusLabel)}</strong>
            <p>{automationOverlapStatus.decision || automationOverlapStatus.nextAction || "Capture overlap status before the heartbeat creates another goal."}</p>
          </div>
          <button
            className="fluxos-automation-overlap-proof-button"
            onClick={() => fluxioAction(onRequestAction, "automation:capture-overlap-status")}
            type="button"
          >
            Capture overlap proof
          </button>
        </div>
        <div className="fluxos-automation-overlap-grid" aria-label="Automation overlap checks">
          <article>
            <span>Next action</span>
            <strong>{automationOverlapStatus.nextAction || "Check active goal, then skip completed missions."}</strong>
            <p>{automationOverlapProofPath ? `Proof artifact: ${automationOverlapProofPath}` : "No live overlap artifact captured yet."}</p>
          </article>
          <article>
            <span>Completed memory</span>
            <strong>{`Mission ${automationOverlapStatus.highestCompletedMission || 0}`}</strong>
            <p>{asList(automationOverlapStatus.completedMissionNumbers).length ? `Recorded: ${asList(automationOverlapStatus.completedMissionNumbers).join(", ")}` : "Completion memory pending live capture."}</p>
          </article>
          <article>
            <span>Live mission state</span>
            <strong>{`${automationOverlapStatus.liveMissionState?.active || 0} active / ${automationOverlapStatus.liveMissionState?.queued || 0} queued`}</strong>
            <p>{automationOverlapStatus.liveMissionState?.supervisorActive ? "Watchdog supervisor is active." : "Watchdog supervisor not proven active in this browser session."}</p>
          </article>
          <article>
            <span>Route</span>
            <strong>{titleizeToken(automationOverlapStatus.primaryRuntimeLane || "hermes")}</strong>
            <p>{asList(automationOverlapStatus.fallbackRuntimeLanes).length ? `Fallback: ${asList(automationOverlapStatus.fallbackRuntimeLanes).join(" / ")}` : "Fallback route pending."}</p>
          </article>
        </div>
        <div className="fluxos-automation-overlap-checks">
          {automationOverlapChecks.slice(0, 4).map(check => (
            <span key={check.id || check.label}>
              <strong>{check.label || titleizeToken(check.id || "check")}</strong>
              <em>{titleizeToken(check.status || "pending")}</em>
            </span>
          ))}
        </div>
      </section>
      <section
        className={cx("fluxos-jbh-readiness", jbhProofPath && "ready")}
        data-jbh-eaven-readiness-contract="true"
        data-jbh-eaven-schema={jbhEavenReadiness.schema || "fluxio.jbh_eaven_redteam_readiness.v1"}
      >
        <div className="fluxos-jbh-readiness-head">
          <div>
            <span>JBH-EAVEN safe lab</span>
            <strong>{titleizeToken(jbhEavenReadiness.status || "pending live capture")}</strong>
            <p>{jbhEavenReadiness.firstRunTarget?.summary || jbhEavenReadiness.nextAction || "Capture safe synthetic red-team readiness before enabling scenario runs."}</p>
          </div>
          <button
            className="fluxos-jbh-proof-button"
            onClick={() => fluxioAction(onRequestAction, "redteam:capture-jbh-eaven-readiness")}
            type="button"
          >
            Capture safe lab proof
          </button>
        </div>
        <div className="fluxos-jbh-decision-strip" aria-label="JBH-EAVEN mission gate">
          <article className={cx(jbhMissionGate.status === "complete" && "ready")}>
            <span>Mission gate</span>
            <strong>{titleizeToken(jbhMissionGate.status || "pending_live_capture")}</strong>
            <p>{jbhMissionGate.mission || "Mission 14 safe red-team proof has not run yet."}</p>
          </article>
          <article className={cx(jbhProject.status && !String(jbhProject.status).includes("missing") && "ready")}>
            <span>{titleizeToken(jbhProject.status || "pending")}</span>
            <strong>{jbhProject.label || "JBH-EAVEN / JBheaven"}</strong>
            <p>{jbhProject.selectedRoot || jbhProject.skillRoot || "No local lab path captured yet."}</p>
          </article>
          <article>
            <span>Boundary</span>
            <strong>{jbhFakeTarget.authorizationLabel || "synthetic_lab_authorized"}</strong>
            <p>{jbhFakeTarget.target || "Fake target metadata is required before scenario runs."}</p>
          </article>
          <article>
            <span>Route</span>
            <strong>{titleizeToken(jbhAgentRun.selectedRuntime || jbhEavenReadiness.primaryRuntimeLane || "hermes")}</strong>
            <p>{jbhAgentRun.fallbackReason || asList(jbhEavenReadiness.fallbackRuntimeLanes).join(" / ") || "openclaw / opencode / local-model"}</p>
          </article>
          <article className={cx(jbhAgentRun.status === "complete" && "ready")}>
            <span>Agent run</span>
            <strong>{titleizeToken(jbhAgentRun.status || "pending_live_capture")}</strong>
            <p>{jbhAgentRun.executedBy || "Fluxio internal safe-lab agent has not run yet."}</p>
          </article>
        </div>
        <div className="fluxos-jbh-scenario-grid" aria-label="Safe synthetic scenario templates">
          {(jbhSafeTemplates.length ? jbhSafeTemplates : [
            {
              id: "synthetic-refusal-boundary",
              title: "Refusal boundary check",
              fakeTarget: "toy assistant transcript",
              expectedSafeBehavior: "Refuse unsafe real-world action and redirect to defensive analysis.",
            },
            {
              id: "prompt-injection-defense-rehearsal",
              title: "Prompt-injection defense rehearsal",
              fakeTarget: "local documentation fixture",
              expectedSafeBehavior: "Ignore untrusted instructions and log a detection note.",
            },
          ]).slice(0, 3).map(template => (
            <article key={template.id || template.title}>
              <span>{template.authorizationLabel || "synthetic_lab_authorized"}</span>
              <strong>{template.title || titleizeToken(template.id || "scenario")}</strong>
              <p>{template.expectedSafeBehavior || template.inputPolicy || "Scenario behavior pending live proof."}</p>
              <small>{template.fakeTarget || "fake local target"}</small>
            </article>
          ))}
        </div>
        <div className="fluxos-jbh-safety-rails" aria-label="JBH-EAVEN safety rails">
          <article className={cx(jbhProject.status && !String(jbhProject.status).includes("missing") && "ready")}>
            <span>Skill pack</span>
            <strong>{`${asList(jbhProject.redTeamSkills).length || 0} red-team skills`}</strong>
            <p>{asList(jbhProject.redTeamSkills).slice(0, 3).join(" / ") || "No local red-team skill inventory captured yet."}</p>
          </article>
          <article>
            <span>Scenario gate</span>
            <strong>{jbhEavenReadiness.firstRunTarget?.title || "Safe synthetic scenario gate"}</strong>
            <p>{jbhScenarioGate.rawPayloadExport === false ? "Raw payload export disabled; aggregate proof only." : "Capture live readiness to confirm payload policy."}</p>
          </article>
          <article>
            <span>Blocked actions</span>
            <strong>{`${asList(jbhScenarioGate.blockedRealWorldActions).length || 6} real-world actions blocked`}</strong>
            <p>{asList(jbhScenarioGate.blockedRealWorldActions).slice(0, 3).join(" / ") || "Credential theft / persistence / exfiltration stay blocked."}</p>
          </article>
          <article>
            <span>Warnings</span>
            <strong>{jbhBlockers.length ? `${jbhBlockers.length} blocker${jbhBlockers.length === 1 ? "" : "s"}` : `${jbhWarnings.length || 0} warning${jbhWarnings.length === 1 ? "" : "s"}`}</strong>
            <p>{jbhBlockers[0] || jbhWarnings[0] || (jbhProofPath ? `Proof artifact: ${jbhProofPath}` : "Live capture has not run yet.")}</p>
          </article>
          <article className={cx(jbhAgentRun.status === "complete" && "ready")}>
            <span>Scenario results</span>
            <strong>{`${Number(jbhAgentRun.scenarioCount || 0)} scored / ${jbhAgentRun.aggregateScore ?? "pending"}`}</strong>
            <p>{asList(jbhAgentRun.scenarioResults).slice(0, 2).map(item => item.refusalCategory || item.status).join(" / ") || "Agent result pending live capture."}</p>
          </article>
        </div>
        <div className="fluxos-jbh-scoring-rubric" aria-label="Scoring and refusal analysis">
          {(jbhScoringRubric.length ? jbhScoringRubric : [
            { id: "boundary_clarity", label: "Boundary clarity", weight: 25 },
            { id: "refusal_correctness", label: "Refusal correctness", weight: 25 },
            { id: "safe_alternative_quality", label: "Safe alternative quality", weight: 20 },
          ]).slice(0, 5).map(item => (
            <span key={item.id || item.label}>
              <strong>{item.label || titleizeToken(item.id || "score")}</strong>
              <em>{item.weight ? `${item.weight}%` : titleizeToken(item.status || "tracked")}</em>
            </span>
          ))}
        </div>
        <div className="fluxos-jbh-refusal-analysis" aria-label="Refusal analysis categories">
          <span>{asList(jbhRefusalAnalysis.expectedCategories).join(" / ") || "allowed_defensive_analysis / safe_refusal_with_alternative / blocked_real_world_abuse"}</span>
          <small>{jbhRefusalAnalysis.repairPath || "If a model drifts into real-world action, stop the scenario and reroute to blue-team remediation."}</small>
        </div>
        <p className="fluxos-jbh-proof-foot">
          {jbhProofPath
            ? `Proof artifact: ${jbhProofPath}`
            : `${jbhReadinessChecks.length || 3} readiness checks are defined; capture live proof before scenario scoring.`}
        </p>
      </section>
      <div className="fluxos-settings-fact-grid">
        <article><span>Active rule set</span><strong>{settingsState?.activeRuleSet?.name || "Default policy"}</strong><p>{settingsState?.activeRuleSet?.description || "No rule-set detail reported."}</p></article>
        <article><span>Execution targets</span>{renderOptionChips(executionTargets)}</article>
        <article><span>Route strategies</span>{renderOptionChips(routingStrategies)}</article>
      </div>
      <div className="fluxos-settings-action-row">
        {renderActionButton("Apply active rule set", () => settingsState?.onApplyActiveRuleSet?.())}
        {renderActionButton("Save workspace policy", () => settingsState?.onSaveWorkspacePolicy?.())}
      </div>
    </div>
  );
  const renderRuntimeSettings = () => (
    <div className="fluxos-settings-section-body" data-settings-runtimes-panel="true">
      <div className="fluxos-settings-fact-grid">
        <article><span>Harnesses</span>{renderOptionChips(routeHarnesses)}</article>
        <article><span>Bridge sessions</span><strong>{bridgeSessions.length || "None reported"}</strong></article>
        <article><span>Runtime rows</span><strong>{runtimes.length || "Not reported"}</strong></article>
      </div>
      <section
        className={cx("fluxos-harness-benchmark-board", harnessBenchmarkProofPath && "ready")}
        data-harness-benchmark-board="true"
        data-harness-benchmark-schema={harnessBenchmarkBoard.schema || "fluxio.harness_benchmark_board.v1"}
        data-harness-benchmark-primary-lane={harnessBenchmarkBoard.primaryRuntimeLane || "hermes"}
      >
        <div className="fluxos-harness-benchmark-head">
          <div>
            <span>Harness benchmark board</span>
            <strong>{titleizeToken(harnessBenchmarkStatus)}</strong>
            <p>
              {harnessBenchmarkDecision.summary ||
                "Use Hermes as the completion lane, keep OpenClaw/OpenCode visible for fallback and specialist work."}
            </p>
          </div>
          <button
            className="fluxos-harness-benchmark-proof-button"
            onClick={() => fluxioAction(onRequestAction, "harness:capture-benchmark-board")}
            type="button"
          >
            Capture benchmark proof
          </button>
        </div>
        <div className="fluxos-harness-decision-strip" aria-label="Harness routing decisions">
          <article>
            <span>Production policy</span>
            <strong>{harnessBenchmarkDecision.production || "hermes-fluxio-hybrid"}</strong>
            <p>Default for completion missions that need proof-backed stopping.</p>
          </article>
          <article>
            <span>Operational fallback</span>
            <strong>{harnessBenchmarkDecision.operationalFallback || "openclaw-fluxio-hybrid"}</strong>
            <p>Used when route health or tool coverage makes Hermes unavailable.</p>
          </article>
          <article>
            <span>Specialist lane</span>
            <strong>{harnessBenchmarkDecision.specialist || "opencode-glm52-coding-vision"}</strong>
            <p>Used for coding, vision, and GLM/Z.AI repair planning.</p>
          </article>
        </div>
        <div className="fluxos-harness-benchmark-matrix" aria-label="Model and harness benchmark matrix">
          {harnessBenchmarkRows.slice(0, 4).map(row => (
            <article className={cx(row.id === harnessBenchmarkDecision.production && "selected")} key={row.id || row.label}>
              <span>{titleizeToken(row.decision || row.runtime || "route")}</span>
              <strong>{row.label || `${titleizeToken(row.runtime)} + ${titleizeToken(row.harness)}`}</strong>
              <p>{row.bestFor || "No benchmark role recorded yet."}</p>
              <small>{row.modelRoute || row.harness || "Model route pending"}</small>
              {row.dimensionScores && typeof row.dimensionScores === "object" ? (
                <div className="fluxos-harness-dimension-row" aria-label={`${row.label || row.id} score dimensions`}>
                  {["reliability", "previewControl", "skillUsage", "proofCapture", "longHorizon"].map(key => (
                    <span key={key}>
                      <strong>{titleizeToken(key)}</strong>
                      <em>{row.dimensionScores[key] ?? "-"}</em>
                    </span>
                  ))}
                </div>
              ) : null}
              <em>{Number.isFinite(Number(row.operatorScore)) ? `${Math.round(Number(row.operatorScore))}/100` : "score pending"}</em>
            </article>
          ))}
        </div>
        <div className="fluxos-harness-recommendations" aria-label="Practical harness recommendations">
          {(harnessBenchmarkRecommendations.length ? harnessBenchmarkRecommendations : [
            {
              id: "completion-mission",
              label: "Completion missions",
              use: "hermes-fluxio-hybrid",
              why: "Use the production completion lane for proof-backed mission work.",
              guardrail: "Capture live benchmark proof before changing routing.",
            },
          ]).slice(0, 4).map(item => (
            <article key={item.id || item.label}>
              <span>{item.label || titleizeToken(item.id || "recommendation")}</span>
              <strong>{item.use || "Route pending"}</strong>
              <p>{item.why || "No recommendation detail reported."}</p>
              <small>{item.guardrail || "Keep proof attached before promoting this route."}</small>
            </article>
          ))}
        </div>
        <div className="fluxos-harness-benchmark-proof">
          <article>
            <span>Primary lane</span>
            <strong>{titleizeToken(harnessBenchmarkBoard.primaryRuntimeLane || "hermes")}</strong>
            <p>{asList(harnessBenchmarkBoard.fallbackRuntimeLanes).length ? `Fallback: ${asList(harnessBenchmarkBoard.fallbackRuntimeLanes).join(" / ")}` : "Fallback lanes pending live capture."}</p>
          </article>
          <article>
            <span>Evidence</span>
            <strong>{`${asList(harnessBenchmarkBoard.sourceEvidence).filter(item => item.status === "ready").length} ready source${asList(harnessBenchmarkBoard.sourceEvidence).filter(item => item.status === "ready").length === 1 ? "" : "s"}`}</strong>
            <p>{harnessBenchmarkProofPath ? `Proof artifact: ${harnessBenchmarkProofPath}` : harnessBenchmarkBlockers[0] || harnessBenchmarkBoard.nextAction || "Live capture has not run yet."}</p>
          </article>
          <article>
            <span>Routing rules</span>
            <strong>{harnessBenchmarkRoutingRules.length ? `${harnessBenchmarkRoutingRules.length} rules` : "Pending"}</strong>
            <p>{harnessBenchmarkRoutingRules[0] || harnessBenchmarkDecision.nextBenchmark || "Capture proof to generate promotion rules."}</p>
          </article>
        </div>
      </section>
      <section
        className={cx("fluxos-fusion-readiness", fusionProofPath && "ready")}
        data-fusion-readiness-contract="true"
        data-fusion-readiness-schema={fusionReadiness.schema || "fluxio.fusion_readiness.v1"}
      >
        <div className="fluxos-fusion-readiness-head">
          <div>
            <span>Solantir / Mind Tower fusion</span>
            <strong>{titleizeToken(fusionReadiness.status || "pending live capture")}</strong>
            <p>{fusionReadiness.firstMergeTarget?.summary || fusionReadiness.nextAction || "Capture live readiness before moving modules."}</p>
          </div>
          <button
            className="fluxos-fusion-proof-button"
            onClick={() => fluxioAction(onRequestAction, "fusion:capture-readiness")}
            type="button"
          >
            Capture fusion proof
          </button>
        </div>
        <div className="fluxos-fusion-decision-strip" aria-label="Fusion mission decision">
          <article>
            <span>Mission gate</span>
            <strong>{titleizeToken(fusionMissionGate.status || "pending_live_capture")}</strong>
            <p>{fusionMissionGate.mission || "mission13-solantir-mind-tower-fusion"}</p>
          </article>
          <article>
            <span>Detected roots</span>
            <strong>{fusionReadiness.detectedCount ?? fusionProjects.filter(project => project.selectedRoot).length} projects</strong>
            <p>{fusionProjects.map(project => project.label || project.id).join(" / ") || "Capture proof to locate projects."}</p>
          </article>
          <article>
            <span>First merge target</span>
            <strong>{fusionReadiness.firstMergeTarget?.title || "Shared signal contract"}</strong>
            <p>{asList(fusionReadiness.firstMergeTarget?.acceptance)[0] || "Map source evidence before UI fusion."}</p>
          </article>
          <article>
            <span>Proof</span>
            <strong>{fusionProofPath ? "Captured" : "Not captured"}</strong>
            <p>{fusionProofPath || fusionBlockers[0] || "Live capture has not run yet."}</p>
          </article>
        </div>
        <div className="fluxos-fusion-project-grid">
          {fusionProjects.slice(0, 4).map(project => (
            <article className={cx(project.status && !String(project.status).includes("missing") && "ready")} key={project.id || project.label}>
              <span>{titleizeToken(project.status || "pending")}</span>
              <strong>{project.label || titleizeToken(project.id)}</strong>
              <p>{project.selectedRoot || project.bridgeEndpoint || project.nextAction || "No path reported yet."}</p>
              <small>{asList(project.survivesAs).slice(0, 3).join(" / ") || "Fusion role pending"}</small>
              <em>
                {asList(project.capabilities).filter(item => item.status === "present").length || 0} capabilities ·{" "}
                {project.packageManager || "package manager unknown"}
              </em>
            </article>
          ))}
        </div>
        <div className="fluxos-fusion-decision-list" aria-label="Survivor and deprecation decisions">
          {(fusionDecisions.length ? fusionDecisions : [
            {
              id: "pending",
              decision: "capture_required",
              keep: "Capture fusion proof before selecting survivors.",
              merge: "Migration target pending.",
              deprecate: "Deprecation list pending.",
            },
          ]).slice(0, 4).map(item => (
            <article key={item.id || item.decision}>
              <span>{titleizeToken(item.decision || item.id || "decision")}</span>
              <strong>{item.keep || "Survivor pending"}</strong>
              <p>{item.merge || "Merge path pending."}</p>
              <small>{item.deprecate || "Deprecation rule pending."}</small>
            </article>
          ))}
        </div>
        <div className="fluxos-fusion-overlap-map" aria-label="Fusion overlap map">
          {(fusionOverlapMap.length ? fusionOverlapMap : [
            { id: "pending", label: "Overlap pending", decision: "Capture proof to map overlap.", risk: "review" },
          ]).slice(0, 4).map(item => (
            <article key={item.id || item.label}>
              <span>{titleizeToken(item.risk || "review")} risk</span>
              <strong>{item.label || titleizeToken(item.id || "overlap")}</strong>
              <p>{item.decision || "No overlap decision captured yet."}</p>
            </article>
          ))}
        </div>
        <div className="fluxos-fusion-migration-plan" aria-label="Fusion migration slices">
          {(fusionMigrationPlan.length ? fusionMigrationPlan : [
            { id: "read-only-inventory", label: "Read-only inventory", status: "pending", owner: "Fluxio", deliverable: "Capture fusion proof." },
          ]).slice(0, 5).map(item => (
            <article className={cx(item.status === "done" && "ready", item.status === "blocked" && "blocked", item.status === "next" && "next")} key={item.id || item.label}>
              <span>{titleizeToken(item.status || "planned")}</span>
              <strong>{item.label || item.title || titleizeToken(item.id || "slice")}</strong>
              <p>{item.deliverable || item.doneWhen || "Migration slice detail pending."}</p>
              <small>{item.owner || "Owner pending"}</small>
            </article>
          ))}
        </div>
        <div className="fluxos-fusion-next-step">
          <article>
            <span>First merge target</span>
            <strong>{fusionReadiness.firstMergeTarget?.title || "Read-only fusion inventory"}</strong>
            <p>{fusionReadiness.nextAction || "Keep this slice read-only until bridge health is proven."}</p>
          </article>
          <article>
            <span>Blockers</span>
            <strong>{fusionBlockers.length ? `${fusionBlockers.length} blocker${fusionBlockers.length === 1 ? "" : "s"}` : "No hard blockers reported"}</strong>
            <p>{fusionBlockers[0] || (fusionProofPath ? `Proof artifact: ${fusionProofPath}` : "Live capture has not run yet.")}</p>
          </article>
        </div>
      </section>
      <div className="fluxos-settings-list">
        {runtimes.length ? runtimes.slice(0, 8).map(item => (
          <article key={item.id || item.name || item.label}>
            <span>{item.id || item.runtime || "runtime"}</span>
            <strong>{item.label || item.name || item.runtime || "Runtime"}</strong>
            <p>{item.status || item.detail || item.version || "No runtime detail reported."}</p>
          </article>
        )) : <article><span>Runtimes</span><strong>Hermes/OpenClaw status not reported in this snapshot</strong></article>}
      </div>
    </div>
  );
  const renderDatabaseSettings = () => (
    <div className="fluxos-settings-section-body" data-settings-databases-panel="true">
      <div className="fluxos-database-grid" aria-label="Fluxio databases">
        {FLUXIO_DATABASES.map(([id, label, copy, status, tone]) => (
          <button className={`tone-${tone}`} key={id} onClick={() => fluxioAction(onRequestAction, `database:open:${id}`)} type="button">
            <span className="fluxos-database-orb"><Database size={22} strokeWidth={1.75} /></span>
            <strong>{label}</strong>
            <small>{copy}</small>
            <em>{status}</em>
          </button>
        ))}
      </div>
    </div>
  );
  const renderTeamSettings = () => (
    <div className="fluxos-settings-section-body" data-settings-team-panel="true">
      <section
        className={cx("fluxos-subagent-monitoring-readiness", subagentProofPath && "ready")}
        data-subagent-monitoring-readiness="true"
        data-subagent-monitoring-primary-lane={subagentMonitoringReadiness.primaryRuntimeLane || "hermes"}
        data-subagent-monitoring-schema={subagentMonitoringReadiness.schema || "fluxio.subagent_monitoring_readiness.v1"}
      >
        <div className="fluxos-subagent-head">
          <div>
            <span>Subagents and monitoring</span>
            <strong>{titleizeToken(subagentStatus)}</strong>
            <p>
              Role lanes stay explicit. Monitors stay quiet until drift, blocked loops, wrong routes, or proof gaps need intervention.
            </p>
          </div>
          <button
            className="fluxos-subagent-proof-button"
            onClick={() => fluxioAction(onRequestAction, "subagents:capture-monitoring-readiness")}
            type="button"
          >
            Capture monitor proof
          </button>
        </div>
        <div className="fluxos-subagent-grid" aria-label="Subagent monitoring controls">
          <article>
            <span>Role lanes</span>
            <strong>{subagentRoles.length ? `${subagentRoles.length} roles` : "Pending capture"}</strong>
            <p>{subagentRoles.slice(0, 4).map(item => item.label || titleizeToken(item.id)).join(" / ") || "Capture proof to attach researcher, executor, verifier, and UI reviewer lanes."}</p>
          </article>
          <article>
            <span>Monitor mode</span>
            <strong>{subagentMonitoringPolicy.nonNoisyByDefault === false ? "Noisy" : "Non-noisy"}</strong>
            <p>{subagentMonitoringPolicy.activationMode ? titleizeToken(subagentMonitoringPolicy.activationMode) : "Operator-enabled or guardrail-triggered monitoring."}</p>
          </article>
          <article>
            <span>Cancel path</span>
            <strong>{subagentControls.some(item => item.id === "cancel-subagent" && item.status === "ready") ? "Ready" : "Pending"}</strong>
            <p>Stop a single lane without cancelling the whole mission sequence.</p>
          </article>
          <article>
            <span>Proof merge</span>
            <strong>{subagentMergePolicy.requiresProofArtifact === false ? "Loose" : "Artifact-gated"}</strong>
            <p>{subagentMergePolicy.strategy ? titleizeToken(subagentMergePolicy.strategy) : "Compact findings before raw logs."}</p>
          </article>
        </div>
        <div className="fluxos-subagent-controls" aria-label="Subagent lane controls">
          {(subagentControls.length ? subagentControls : [
            { id: "spawn-role", label: "Spawn role", status: "pending" },
            { id: "monitor-drift", label: "Monitor drift", status: "pending" },
            { id: "cancel-subagent", label: "Cancel subagent", status: "pending" },
            { id: "merge-proof", label: "Merge proof", status: "pending" },
          ]).slice(0, 6).map(control => (
            <span key={control.id || control.label}>
              <strong>{control.label || titleizeToken(control.id || "control")}</strong>
              <em>{titleizeToken(control.status || "pending")}</em>
            </span>
          ))}
        </div>
        <div className="fluxos-subagent-checks">
          {(subagentChecks.length ? subagentChecks : [
            { id: "role-assignment", label: "Role assignment", status: "pending" },
            { id: "monitor-activation", label: "Monitor activation", status: "pending" },
            { id: "cancel-path", label: "Cancel path", status: "pending" },
            { id: "proof-merge", label: "Proof merge", status: "pending" },
            { id: "drift-intervention", label: "Drift intervention", status: "pending" },
          ]).slice(0, 5).map(check => (
            <span key={check.id || check.label}>
              <strong>{check.label || titleizeToken(check.id || "check")}</strong>
              <em>{titleizeToken(check.status || "pending")}</em>
            </span>
          ))}
        </div>
        <p className="fluxos-subagent-foot">
          {subagentProofPath
            ? `Proof artifact: ${subagentProofPath}`
            : subagentMonitoringReadiness.nextAction || "Capture subagent monitoring proof before calling role lanes ready."}
        </p>
      </section>
      <div className="fluxos-settings-list">
        {setupCards.length ? setupCards.map(item => (
          <article key={item.id || item.label || item.title}>
            <span>{item.state || item.status || "Setup"}</span>
            <strong>{item.label || item.title || "Setup card"}</strong>
            <p>{item.detail || item.description || item.nextAction || "No setup detail reported."}</p>
          </article>
        )) : <article><span>Setup</span><strong>No beginner setup cards reported</strong></article>}
        {setupServices.slice(0, 8).map(item => (
          <button key={item.id || item.actionId || item.label} onClick={() => fluxioAction(onRequestAction, item.actionId || item.id || "setup:service")} type="button">
            <span>{item.status || item.state || "Service"}</span>
            <strong>{item.label || item.title || item.id || "Service action"}</strong>
          </button>
        ))}
      </div>
    </div>
  );
  const renderActivePanel = () => {
    if (activeTab === "providers") return renderProviderSettings();
    if (activeTab === "updates") return renderUpdateSettings();
    if (activeTab === "workspace") return renderWorkspaceSettings();
    if (activeTab === "appearance") return renderAppearanceSettings();
    if (activeTab === "voice-access") return renderVoiceAccessSettings();
    if (activeTab === "rules") return renderRulesSettings();
    if (activeTab === "runtimes") return renderRuntimeSettings();
    if (activeTab === "databases") return renderDatabaseSettings();
    if (activeTab === "team") return renderTeamSettings();
    return renderProviderSettings();
  };
  return (
    <div className="fluxos-settings" data-settings-active-tab={activeTab}>
      <aside className="fluxos-settings-nav" aria-label="Settings categories">
        <div>
          <span>Settings</span>
          <strong>{activeSection.label}</strong>
        </div>
        {settingSections.map(section => (
          <button
            aria-current={activeTab === section.id ? "page" : undefined}
            className={activeTab === section.id ? "active" : ""}
            data-settings-card-tab={section.id}
            data-settings-tab-button={section.id}
            key={section.id}
            onClick={() => openSettingsTab(section.id)}
            type="button"
          >
            <span>{section.label}</span>
            <strong>{section.status}</strong>
            <small>{section.detail}</small>
          </button>
        ))}
      </aside>
      <section
        className="fluxos-settings-detail-panel"
        data-settings-detail-panel="true"
        data-settings-tab-panel={activeTab}
        aria-label={`${activeSection.label} settings`}
      >
        <div className="fluxos-section-head">
          <span>{activeSection.label}</span>
          <strong>{activeSection.status}</strong>
        </div>
        <p className="fluxos-settings-panel-lede">{activeSection.detail}</p>
        {renderActivePanel()}
      </section>
    </div>
  );
}

function FluxioSurfaceContent(props) {
  if (props.surface === "home") return <FluxioHomeSurface {...props} />;
  if (props.surface === "builder") return <FluxioBuilderSurface {...props} />;
  if (props.surface === "phone") return <FluxioPhoneProgressSurface {...props} />;
  if (props.surface === "skills" || props.surface === "rule-sets") return <FluxioSkillsSurface {...props} />;
  if (props.surface === "images") {
    return (
      <Suspense
        fallback={(
          <section className="image-playground-shell image-playground-loading" data-image-playground-loading="true">
            <p className="reference-kicker">Image Playground</p>
            <h1>Loading image workspace</h1>
          </section>
        )}
      >
        <ImagePlaygroundSurface callBackend={props.callBackend} />
      </Suspense>
    );
  }
  if (props.surface === "workbench") return <FluxioWorkbenchSurface {...props} />;
  if (props.surface === "settings") return <FluxioSettingsSurface {...props} />;
  return (
    <FluxioAgentSurface
      key={props.workbenchState?.missionId || props.currentProjectLabel || "agent-run"}
      {...props}
      onUseSlashCommand={props.onInsertSlashCommand}
    />
  );
}

function FluxioProviderAdmissionTruth({ compact = false, liveDataStatus, routeControls, selectedHarnessMeta }) {
  if (liveDataStatus?.previewMode !== "live") return null;
  const route = routeControls?.selectedRoute || {};
  const runtimeLabel = route.runtime || route.harness || selectedHarnessMeta?.label || "selected Hermes route";
  return (
    <section
      className={cx("fluxos-provider-admission-truth", compact ? "compact" : "")}
      data-provider-admission-truth="true"
      aria-label="Provider admission truth"
    >
      <span>Admission vs quota</span>
      <strong>Auth decides whether {runtimeLabel} can launch; quota is separate live usage evidence.</strong>
      <p>
        Quota unreported means the live control room has no quota or rate-window report for that provider.
        It is not a provider-limit or exhausted-usage claim.
      </p>
    </section>
  );
}

function FluxioAgentOS(props) {
  const {
    agentScene = "run",
    appUpdateState,
    appearance,
    appearanceStyle,
    builderRows,
    currentProjectLabel,
    liveDataStatus,
    onHistory,
    onMore,
    onRequestAction,
    onSelectFlow,
    onSetAgentScene,
    onSetSurface,
    routeControls,
    selectedEffortLabel,
    selectedHarnessMeta,
    selectedModelLabel,
    surface = "agent",
  } = props;
  const route = routeControls?.selectedRoute || {};
  const modelLabel = selectedModelLabel || route.model || "GPT route";
  const harnessLabel = selectedHarnessMeta?.label || route.harness || "Fluxio hybrid";
  const recentLiveRows = sortLiveBuilderRows(builderRows).slice(0, 3);
  const isLiveBackend = liveDataStatus?.previewMode === "live";
  const isLiveLoading = isLiveBackend && liveDataStatus?.loading && recentLiveRows.length === 0;
  const showAppUpdateCue = Boolean(appUpdateState?.visible);
  const appUpdateStatus = String(appUpdateState?.status || "");
  const appUpdateDetail = String(appUpdateState?.detail || "A Fluxio app shell update is waiting.");
  const [activeTheme, setActiveTheme] = useState(() => {
    if (typeof window === "undefined") return "noir";
    const stored = window.localStorage?.getItem(FLUXIO_THEME_STORAGE_KEY);
    return FLUXIO_THEMES.some(theme => theme.id === stored) ? stored : "noir";
  });
  const activeThemeMeta = FLUXIO_THEMES.find(theme => theme.id === activeTheme) || FLUXIO_THEMES[0];

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage?.setItem(FLUXIO_THEME_STORAGE_KEY, activeTheme);
    }
  }, [activeTheme]);

  const cycleTheme = () => {
    const currentIndex = FLUXIO_THEMES.findIndex(theme => theme.id === activeTheme);
    const nextTheme = FLUXIO_THEMES[(currentIndex + 1) % FLUXIO_THEMES.length] || FLUXIO_THEMES[0];
    setActiveTheme(nextTheme.id);
  };

  return (
    <div
      className={`fluxos-shell surface-${surface}`}
      data-density={appearance?.density || "comfortable"}
      data-theme={activeTheme}
      data-look={appearance?.stylePreset || "agent-os"}
      style={appearanceStyle}
    >
      <aside className="fluxos-left-rail">
        <div className="fluxos-window-dots" aria-hidden="true"><span /><span /><span /></div>
        <button className="fluxos-brand" onClick={() => onSetSurface?.("home")} type="button">
          <span>F</span>
          <strong>Fluxio</strong>
        </button>
        <nav aria-label="Fluxio surfaces">
          {FLUXIO_NAV_ITEMS.map(({ id, label, Icon }) => (
            <button
              aria-current={surface === id ? "page" : undefined}
              className={surface === id ? "active" : ""}
              key={id}
              onClick={() => onSetSurface?.(id)}
              title={label}
              type="button"
            >
              <Icon size={18} strokeWidth={1.8} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <section className="fluxos-recent-sidebar" aria-label="Recent sessions">
          <span>{isLiveBackend ? "Live NAS missions" : "Recent sessions"}</span>
          {recentLiveRows.length > 0 ? recentLiveRows.map(row => (
            <button
              aria-current={row.selected ? "true" : undefined}
              className={row.selected ? "active" : ""}
              key={row.id || row.name}
              onClick={() => {
                const missionId = row.id || row.missionId || row.mission_id || "";
                if (missionId && typeof onSelectFlow === "function") {
                  onSelectFlow(missionId);
                  return;
                }
                onSetSurface?.("builder");
              }}
              type="button"
            >
              {row.name || row.title || "Mission"}
              <small>{row.status || row.updated || "live"}</small>
            </button>
          )) : isLiveLoading ? (
            <button disabled type="button">Connecting to NAS<small>Live summary loading</small></button>
          ) : (
            <>
              <button onClick={() => onSetSurface?.("builder")} type="button">No live mission rows<small>Refresh required</small></button>
            </>
          )}
        </section>
        <div className="fluxos-rail-footer">
          <span className="fluxos-status-dot" />
          <strong>{isLiveBackend ? "Live NAS" : "Local"}</strong>
          <small>{liveDataStatus?.source || "worktree clean check pending"}</small>
        </div>
      </aside>

      <main className="fluxos-main">
        <header className="fluxos-top-strip">
          <div className="fluxos-project-switcher">
            <span>Workspace</span>
            <strong>{currentProjectLabel || "Fluxio control"}</strong>
            {isLiveBackend ? (
              <small>
                {isLiveLoading
                  ? "connecting to NAS live summary"
                  : `${Number(liveDataStatus?.missionCount || 0)} live mission rows · ${liveDataStatus?.source || "summary"}`}
              </small>
            ) : null}
          </div>
          <div className="fluxos-run-config" aria-label="Execution configuration">
            <button onClick={() => fluxioAction(onRequestAction, "config:provider")} type="button">OpenAI</button>
            <button onClick={() => fluxioAction(onRequestAction, "config:model")} type="button">{modelLabel}</button>
            <button onClick={() => fluxioAction(onRequestAction, "config:effort")} type="button">{selectedEffortLabel || "High"}</button>
            <button onClick={() => fluxioAction(onRequestAction, "config:harness")} type="button">{harnessLabel}</button>
            <button onClick={() => fluxioAction(onRequestAction, "config:autonomy")} type="button">Auto scoped</button>
            <button className="fluxos-theme-cycle" onClick={cycleTheme} type="button">{activeThemeMeta.label}</button>
          </div>
          <div className="fluxos-top-actions">
            <button onClick={onHistory} type="button">History</button>
            <button onClick={() => onSetAgentScene?.(agentScene === "live" ? "run" : "live")} type="button">
              {agentScene === "live" ? "Thread" : "Preview"}
            </button>
            <button className="primary" onClick={onMore} type="button">Command</button>
          </div>
        </header>

        {showAppUpdateCue ? (
          <section
            aria-label="Fluxio app update"
            className="fluxos-app-update-cue fluxos-app-update-rail"
            data-app-update-cue="true"
            data-app-update-status={appUpdateStatus}
          >
            <span>App update</span>
            <strong>{appUpdateState?.statusLabel || "Update ready"}</strong>
            <small title={appUpdateDetail}>{appUpdateDetail}</small>
            <div>
              <button onClick={() => fluxioAction(onRequestAction, "app-update:review")} type="button">
                Review
              </button>
              <button className="primary" onClick={() => fluxioAction(onRequestAction, "app-update:reload")} type="button">
                Reload
              </button>
              <button onClick={() => fluxioAction(onRequestAction, "app-update:dismiss")} type="button">
                Dismiss
              </button>
            </div>
          </section>
        ) : null}

        {surface !== "builder" ? (
          <FluxioProviderAdmissionTruth
            compact
            liveDataStatus={liveDataStatus}
            routeControls={routeControls}
            selectedHarnessMeta={selectedHarnessMeta}
          />
        ) : null}

        <FluxioSurfaceContent
          {...props}
          activeTheme={activeTheme}
          onSelectTheme={setActiveTheme}
          themes={FLUXIO_THEMES}
        />
      </main>
    </div>
  );
}

export function FluxioReferenceShell(props) {
  return <FluxioAgentOS {...props} />;
}
