import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
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
    .find(line => line && !/^objective\s*:/i.test(line) && !/^triggered by step\s*:/i.test(line)) || "";
}

function agentMessageDisplayTitle(message) {
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
  if (!message || message.traceOnly || isControlRoomBookkeepingAgentMessage(message) || isSyntheticAgentOverviewMessage(message)) {
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

function visibleAgentMessages(messages, limit = 36, priorityLimit = 8, options = {}) {
  const requireRuntimeReports = Boolean(options?.requireRuntimeReports);
  const rows = asList(messages).filter(message => !isEmptyBookkeepingAgentMessage(message));
  const runtimeOutputRows = uniqueRuntimeOutputMessages(rows.filter(isRuntimeOutputAgentMessage));
  const reportRows = rows.filter(isLiveRuntimeReportMessage);
  const sourceRows = requireRuntimeReports
    ? (runtimeOutputRows.length > 0 ? runtimeOutputRows : reportRows)
    : runtimeOutputRows.length > 0
      ? runtimeOutputRows
      : reportRows.length > 0
        ? reportRows
        : rows.filter(message => !isControlRoomBookkeepingAgentMessage(message) && !isSyntheticAgentOverviewMessage(message));
  const priorityRows = runtimeOutputRows.slice(-priorityLimit);
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
        title: "Computer-use is not configured yet",
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
  const notificationCount = Number(liveDataStatus?.notificationCount || 0);
  const sliceNotificationCount = Number(liveDataStatus?.sliceNotificationCount || 0);
  const latestDetail = latestThreadRow
    ? agentPreviewDetail(latestThreadRow)
    : workbenchState?.progress?.nextAction || "Waiting for the next live mission update.";
  const sourceLabel = liveDataStatus?.summaryCache?.status === "hit"
    ? "warm NAS summary"
    : liveDataStatus?.source || "control-room summary";
  return (
    <section className="fluxos-live-operations-brief" aria-label="Live operations brief" data-live-operations-brief="true">
      <div className="fluxos-live-brief-main">
        <span>{sourceLabel}</span>
        <strong>{workbenchState?.missionTitle || `${activeCount} active live mission${activeCount === 1 ? "" : "s"}`}</strong>
        <p>{latestDetail}</p>
      </div>
      <div className="fluxos-live-brief-metrics">
        <div>
          <span>Progress</span>
          <strong>{progressValue == null ? "No %" : `${progressValue}%`}</strong>
        </div>
        <div>
          <span>Running</span>
          <strong>{runningCount}</strong>
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

function AgentIdleSurface(props) {
  const {
    draft,
    onUseSlashCommand,
    selectedRuntime,
    runtimeOptions,
    runtimeStatus,
    selectedModelLabel,
    selectedEffortLabel,
    selectedHarnessMeta = [],
    slashCommands = [],
    onAttach,
    onChangeDraft,
    onDictation,
    onIdleSubmit,
    onRequestAction,
    onPaste,
    onRuntimeChange,
    routeControls = {},
  } = props;
  const showSlashCommands = String(draft || "").trim().startsWith("/");
  const selectedRoute = routeControls.selectedRoute || {};
  const routeOptions = routeControls.routeOptions || {};
  const actionModes = routeControls.actionModes || [];
  const routeRows = asList(routeOptions.roles).map(role => ({
    role,
    route:
      routeControls.routeByRole?.[role] ||
      (role === routeControls.role ? selectedRoute : null) ||
      {},
  }));

  return (
    <section className="reference-agent-idle">
      <div className="reference-surface-intro">
        <h1>What are we working on today?</h1>
        <p>Describe your task or ask anything.</p>
      </div>

      <ComposerDock
        draft={draft}
        onAttach={onAttach}
        onChangeDraft={onChangeDraft}
        onDictation={onDictation}
        onPaste={onPaste}
        onSubmit={onIdleSubmit}
        placeholder="Ask your agent anything..."
      >
        {actionModes.length > 0 ? (
          <div className="reference-mode-strip" aria-label="Run mode">
            {actionModes.map(option => (
              <button
                className={routeControls.actionMode === option.value ? "active" : ""}
                key={`composer-mode-${option.value}`}
                onClick={() => routeControls.onActionModeChange?.(option.value)}
                type="button"
              >
                {option.label}
              </button>
            ))}
          </div>
        ) : null}
        {showSlashCommands ? (
          <SlashCommandPanel
            className="in-composer"
            commands={slashCommands}
            draft={draft}
            onUseCommand={onUseSlashCommand}
          />
        ) : null}
      </ComposerDock>

      <div className="reference-config-grid compact">
        <ConfigCard
          accent="neutral"
          copy={runtimeStatus?.detected ? "Work engine ready for launch." : "Syntelos checks this automatically before the first run."}
          title="Work engine"
          titleIcon={WandSparkles}
        >
          <label className="reference-select-shell">
            <select onChange={event => onRuntimeChange(event.target.value)} value={selectedRuntime}>
              {runtimeOptions.map(option => (
                <option key={`idle-runtime-${option.value}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          {selectedHarnessMeta.length > 0 ? (
            <div className="reference-card-metric-stack">
              {selectedHarnessMeta.map(item => (
                <MetricLine key={`${item.label}-${item.value}`} label={item.label} value={item.value} />
              ))}
            </div>
          ) : null}
        </ConfigCard>

        <ConfigCard
          accent="neutral"
          copy="Planner, executor, and verifier roles route automatically by phase. You only tune provider/model per role."
          title="Model Routes"
          titleIcon={Bot}
        >
          <div className="reference-route-matrix compact">
            {routeRows.map(({ role, route }) => (
              <article className={routeControls.role === role ? "active" : ""} key={`route-row-${role}`}>
                <button onClick={() => routeControls.onRoleChange?.(role)} type="button">
                  {titleizeToken(role)}
                </button>
                <select
                  aria-label={`${role} provider`}
                  onChange={event => routeControls.onRoleFieldChange?.(role, "provider", event.target.value)}
                  value={route.provider || "openai"}
                >
                  {asList(routeOptions.providers).map(option => (
                    <option key={`${role}-provider-${option.value}`} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <select
                  aria-label={`${role} model`}
                  onChange={event => routeControls.onRoleFieldChange?.(role, "model", event.target.value)}
                  value={route.model || ""}
                >
                  <option value="">Provider default</option>
                  {asList(routeOptions.models).map(option => (
                    <option key={`${role}-model-${option}`} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
                <select
                  aria-label={`${role} effort`}
                  onChange={event => routeControls.onRoleFieldChange?.(role, "effort", event.target.value)}
                  value={route.effort || "default"}
                >
                  {asList(routeOptions.efforts).map(option => (
                    <option key={`${role}-effort-${option.value}`} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </article>
            ))}
          </div>
        </ConfigCard>

        {actionModes.length > 0 ? (
          <ConfigCard
            accent="neutral"
            copy="The arrow follows this mode. Auto keeps short greetings/questions as chat and opens a mission for larger work."
            title="Run Mode"
            titleIcon={Sparkles}
          >
            <div className="reference-card-control-stack">
              <div className="reference-mode-strip vertical" aria-label="Run mode">
                {actionModes.map(option => (
                  <button
                    className={routeControls.actionMode === option.value ? "active" : ""}
                    key={`card-mode-${option.value}`}
                    onClick={() => routeControls.onActionModeChange?.(option.value)}
                    type="button"
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <button className="reference-link-button strong" onClick={() => routeControls.onSave?.()} type="button">
                Save routes
              </button>
            </div>
          </ConfigCard>
        ) : null}

        <ConfigCard
          accent="neutral"
          copy={`${selectedEffortLabel} · ${selectedModelLabel}`}
          title="Rules"
          titleIcon={BookOpen}
          footer={(
            <button
              className="reference-link-button"
              onClick={() => onRequestAction?.("idle:advanced-settings")}
              type="button"
            >
              Advanced settings
            </button>
          )}
        >
          <div className="reference-card-control-stack">
            <div className="reference-pill-select">Project Rules</div>
            <button className="reference-link-button" onClick={() => routeControls.onToggleCodeExecution?.()} type="button">
              Code execution {routeControls.codeExecutionEnabled ? `on (${routeControls.codeExecutionMemory})` : "off"}
            </button>
          </div>
        </ConfigCard>
      </div>

      <div className="reference-agent-support-grid single">
        <article className="reference-support-panel">
          <div className="reference-builder-section-head">
            <div>
              <strong>{runtimeStatus?.label || "Selected work engine"}</strong>
              <span>
                {runtimeStatus?.doctor_summary ||
                  runtimeStatus?.doctorSummary ||
                  "Readiness appears here after Syntelos checks setup."}
              </span>
            </div>
            <StatusBadge
              label={runtimeStatus?.detected ? "Ready" : "Not detected"}
              tone={runtimeStatus?.detected ? "completed" : "paused"}
            />
          </div>
          <RuntimeCapabilityPills capabilities={asList(runtimeStatus?.capabilities)} />
        </article>
      </div>

      <div className="reference-idle-footer">
        <button
          className="reference-reset-button"
          onClick={() => onRequestAction?.("idle:reset-defaults")}
          type="button"
        >
          <RefreshCw size={16} strokeWidth={1.9} />
          <span>Reset to defaults</span>
        </button>
        <p>Syntelos can make mistakes. Please verify important information.</p>
      </div>
    </section>
  );
}

function StepState({ label, done = false, pending = false }) {
  return (
    <div className="reference-step-state">
      {done ? (
        <CircleCheckBig className="done" size={16} strokeWidth={2.2} />
      ) : (
        <CircleDashed className={pending ? "pending" : ""} size={16} strokeWidth={2.2} />
      )}
      <span>{label}</span>
    </div>
  );
}

function AgentRunningSurface(props) {
  const {
    activeCommentTarget = null,
    conversationMode = "chat",
    draft,
    feedbackItems = [],
    generatedImageArtifacts = [],
    hermesEvidenceItems = [],
    missionLoop,
    messages = [],
    nasDeployChecks = [],
    onUseSlashCommand,
    runtimeCompartment = null,
    selectedRuntime,
    selectedRuntimeLabel,
    selectedModelLabel,
    selectedEffortLabel,
    slashCommands = [],
    timelineMoments = [],
    workbenchState = null,
    onAttach,
    onChangeDraft,
    onDictation,
    onPaste,
    onRequestAction,
    onRuntimeChange,
    runtimeOptions = [],
    routeControls = {},
    onSend,
  } = props;
  const [detailTab, setDetailTab] = useState("feedback");
  const [showTraceDetail, setShowTraceDetail] = useState(false);
  const processMoments = timelineMoments.slice(-4);
  const renderedMessages = messages.length > 0 ? messages : [];
  const transcriptWindow = useVirtualWindow(renderedMessages, {
    itemHeight: 176,
    viewportHeight: 620,
    overscan: 6,
  });
  const transcriptVirtualized = transcriptWindow.totalCount > 32;
  const transcriptRows = transcriptVirtualized ? transcriptWindow.items : renderedMessages;
  const showMissionPanels = conversationMode === "mission" || Boolean(missionLoop);
  const showSlashCommands = String(draft || "").trim().startsWith("/");
  const selectedRoute = routeControls.selectedRoute || {};
  const activeMissionId =
    workbenchState?.missionId ||
    missionLoop?.missionId ||
    missionLoop?.mission_id ||
    "";
  const activeRuntimeId =
    selectedRuntime ||
    runtimeCompartment?.runtime ||
    missionLoop?.runtimeId ||
    missionLoop?.runtime_id ||
    "";
  const routeOptions = routeControls.routeOptions || {};
  const actionModes = routeControls.actionModes || [];
  const runtimeSelectOptions = runtimeOptions.length > 0
    ? runtimeOptions
    : [{ value: selectedRuntime, label: selectedRuntimeLabel }];
  const delegatedLanes = asList(
    missionLoop?.delegatedRuntimeSessions || missionLoop?.delegated_runtime_sessions || missionLoop?.lanes,
  );
  const runtimeModeLabel =
    missionLoop?.approvalMode === "hands_free" || routeControls.actionMode === "mission"
      ? "Hands-free"
      : "Supervised";
  const checkpointSummary =
    missionLoop?.checkpointSummary || missionLoop?.continuityDetail || missionLoop?.continuityState || "No checkpoint yet";
  const lazyProofArtifactPageSize = 4;
  const lazyHermesEvidencePageSize = 5;
  const [generatedArtifactPage, setGeneratedArtifactPage] = useState(1);
  const [hermesEvidencePage, setHermesEvidencePage] = useState(1);
  const artifactItems = asList(missionLoop?.artifacts || missionLoop?.proofArtifacts || missionLoop?.proof_artifacts).slice(0, 3);
  const diffSummary = missionLoop?.diffSummary || missionLoop?.gitDiffSummary || missionLoop?.workspaceDiffSummary || "Diff pending";
  const compartmentEvents = asList(runtimeCompartment?.toolTimeline).slice(-5);
  const compartmentFiles = asList(runtimeCompartment?.filesChanged).slice(0, 5);
  const compartmentApprovals = asList(runtimeCompartment?.approvals).slice(0, 3);
  const generatedArtifactRows = asList(generatedImageArtifacts);
  const hermesEvidenceRows = asList(hermesEvidenceItems);
  const visibleGeneratedArtifacts = generatedArtifactRows.slice(
    0,
    generatedArtifactPage * lazyProofArtifactPageSize,
  );
  const visibleHermesEvidence = hermesEvidenceRows.slice(
    0,
    hermesEvidencePage * lazyHermesEvidencePageSize,
  );
  const visibleNasChecks = asList(nasDeployChecks).slice(0, 6);
  const [workbenchTab, setWorkbenchTab] = useState("browser");
  const workbenchTabs = [
    { id: "browser", label: "Browser" },
    { id: "snapshot", label: "UI Snapshot" },
    { id: "terminal", label: "Terminal" },
    { id: "diff", label: "Diff" },
    { id: "files", label: `Files (${compartmentFiles.length})` },
    { id: "control", label: "Computer Control" },
  ];
  const [diagnosticNowMs, setDiagnosticNowMs] = useState(() => Date.now());
  const messageDiagnostics = useMemo(() => {
    return renderedMessages.map((item, index) => {
      const createdAtMs = parseTimeMs(item.createdAt);
      const pendingMs = item.pending && createdAtMs > 0 ? Math.max(0, diagnosticNowMs - createdAtMs) : 0;
      const latencyMs = !item.pending ? extractLatencyMsFromMessage(item) : 0;
      return {
        id: item.id,
        pendingMs,
        latencyMs,
        contradiction: detectPotentialContradiction(renderedMessages, index),
      };
    });
  }, [diagnosticNowMs, renderedMessages]);
  const messageDiagnosticsById = useMemo(
    () => new Map(messageDiagnostics.map(entry => [entry.id, entry])),
    [messageDiagnostics],
  );
  const runMessageEntries = useMemo(
    () =>
      renderedMessages.map((item, index) => ({
        item,
        key: stableAgentMessageKey(item, `reference-run-message-${index}`),
      })),
    [renderedMessages],
  );
  const runMessageKeySignature = runMessageEntries.map(entry => entry.key).join("|");
  const [selectedRunMessageId, setSelectedRunMessageId] = useState("");
  const runMessageScopeRef = useRef("");
  const selectedRunMessageScope = [
    conversationMode,
    activeMissionId,
    activeRuntimeId,
    runMessageKeySignature,
  ].join(":");
  useEffect(() => {
    setSelectedRunMessageId(current => {
      const scopeChanged = runMessageScopeRef.current !== selectedRunMessageScope;
      runMessageScopeRef.current = selectedRunMessageScope;
      const currentEntry = current ? runMessageEntries.find(entry => entry.key === current) : null;
      if (!scopeChanged && currentEntry) {
        return current;
      }
      const runtimeReport =
        [...runMessageEntries].reverse().find(entry => isRuntimeOutputAgentMessage(entry.item) || isLiveRuntimeReportMessage(entry.item)) ||
        null;
      const meaningful =
        runtimeReport ||
        [...runMessageEntries].reverse().find(entry => isMeaningfulDefaultAgentMessage(entry.item)) ||
        runMessageEntries[runMessageEntries.length - 1] ||
        null;
      return meaningful?.key || "";
    });
  }, [runMessageEntries, selectedRunMessageScope]);
  const selectedRunMessageEntry = runMessageEntries.find(entry => entry.key === selectedRunMessageId) || null;
  const selectedRunMessage = selectedRunMessageEntry?.item || null;
  const selectedRunMessageBody = selectedRunMessage ? agentMessageDisplayDetail(selectedRunMessage) : "";
  const selectedRunMessageMeta = [
    selectedRunMessage?.label || selectedRunMessage?.roleLabel || "",
    selectedRunMessage?.runtimeId || activeRuntimeId || "",
    selectedRunMessage?.meta || selectedRunMessage?.createdAt || "",
  ].filter(Boolean).join(" · ");
  const selectRunMessage = useCallback((messageKey, event = null) => {
    if (eventTargetIsInteractive(event)) {
      return;
    }
    const normalizedMessageKey = String(messageKey || "").trim();
    if (!normalizedMessageKey) {
      return;
    }
    setSelectedRunMessageId(normalizedMessageKey);
  }, []);
  const handleRunMessageKeyDown = useCallback((event, messageKey) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      selectRunMessage(messageKey, null);
    }
  }, [selectRunMessage]);
  const pendingMessageCount = useMemo(
    () => messageDiagnostics.filter(entry => entry.pendingMs > 0).length,
    [messageDiagnostics],
  );
  const contradictionCount = useMemo(
    () => messageDiagnostics.filter(entry => Boolean(entry.contradiction)).length,
    [messageDiagnostics],
  );
  const latestLatencyMs = useMemo(() => {
    for (let index = messageDiagnostics.length - 1; index >= 0; index -= 1) {
      if (messageDiagnostics[index].latencyMs > 0) {
        return messageDiagnostics[index].latencyMs;
      }
    }
    return 0;
  }, [messageDiagnostics]);
  useEffect(() => {
    if (pendingMessageCount <= 0) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      setDiagnosticNowMs(Date.now());
    }, 1000);
    return () => window.clearInterval(timer);
  }, [pendingMessageCount]);

  if (!showMissionPanels) {
    return (
      <section className={cx("reference-agent-run", "mode-chat", "reference-agent-pro-chat")}>
        <div className="reference-chat-workbench">
          <section className="reference-chat-panel">
            <header className="reference-chat-session-head">
              <div>
                <strong>{selectedRoute.model || selectedModelLabel || "Conversation"}</strong>
                <p>
                  Provider: {selectedRoute.provider || runtimeCompartment?.route?.provider || "openai-codex"}
                  {"  "} Model: {selectedRoute.model || runtimeCompartment?.route?.model || selectedModelLabel}
                  {"  "} Route: {selectedRoute.role || "primary"}
                </p>
                <div className="reference-chat-health-strip" aria-label="Conversation diagnostics">
                  <span className={cx("reference-health-pill", pendingMessageCount > 0 && "is-live")}>
                    {pendingMessageCount > 0
                      ? `Thinking: ${pendingMessageCount}`
                      : "Thinking: idle"}
                  </span>
                  <span className="reference-health-pill">
                    {latestLatencyMs > 0
                      ? `Last response: ${formatElapsedDuration(latestLatencyMs)}`
                      : "Last response: n/a"}
                  </span>
                  <span className={cx("reference-health-pill", contradictionCount > 0 ? "is-warn" : "is-good")}>
                    {contradictionCount > 0
                      ? `Consistency watch: ${contradictionCount} flagged`
                      : "Consistency watch: clear"}
                  </span>
                  <span className="reference-health-pill">
                    {transcriptVirtualized
                      ? `Virtualized transcript: ${transcriptWindow.items.length}/${transcriptWindow.totalCount}`
                      : `Transcript: ${renderedMessages.length}`}
                  </span>
                </div>
              </div>
              <span className={cx("reference-session-state", runtimeCompartment?.streaming === "live" && "live")}>
                {runtimeCompartment?.streaming === "live" ? "Live" : "Recorded"}
              </span>
            </header>

            <div
              className={cx("reference-chat-thread-canvas", transcriptVirtualized && "virtualized")}
              onScroll={transcriptVirtualized ? transcriptWindow.onScroll : undefined}
              style={transcriptVirtualized ? { maxHeight: transcriptWindow.viewportHeight } : undefined}
            >
              {renderedMessages.length === 0 ? (
                <article className="reference-conversation-blank">
                  <strong>New conversation</strong>
                  <p>Send a message to begin a direct chat with Hermes.</p>
                  <button
                    className="reference-black-button"
                    onClick={() => onRequestAction?.("flow:new-conversation")}
                    type="button"
                  >
                    Start new conversation
                  </button>
                </article>
              ) : null}

              {transcriptVirtualized && transcriptWindow.topPadding > 0 ? (
                <div
                  aria-hidden="true"
                  className="reference-chat-virtual-spacer"
                  style={{ height: transcriptWindow.topPadding }}
                />
              ) : null}

              {transcriptRows.map(item => {
                const diagnostics = messageDiagnosticsById.get(item.id) || {};
                const contradictionSignal = diagnostics.contradiction || null;
                if (item.role === "user") {
                  return (
                    <div
                      className="reference-user-bubble"
                      data-mission-id={item.missionId || activeMissionId}
                      data-runtime-id={item.runtimeId || activeRuntimeId}
                      data-turn-id={item.id}
                      key={item.id}
                    >
                      <p>{item.title}</p>
                      <span>{item.meta || "Now"}</span>
                    </div>
                  );
                }
                return (
                  <div
                    className={cx("reference-agent-thread", item.pending ? "is-pending" : "")}
                    data-mission-id={item.missionId || activeMissionId}
                    data-runtime-id={item.runtimeId || activeRuntimeId}
                    data-turn-id={item.id}
                    key={item.id}
                  >
                    <div className="reference-agent-avatar">
                      <div className="reference-brand-mark tiny">
                        <span />
                        <span />
                        <span />
                      </div>
                    </div>
                    <div className="reference-agent-thread-body">
                      <p className="reference-thread-lead">
                        {item.pending ? <CircleDashed className="pending" size={16} strokeWidth={2.1} /> : null}
                        <span>{item.title}</span>
                        {item.pending && diagnostics.pendingMs > 0 ? (
                          <span className="reference-diagnostic-pill is-live">
                            Thinking {formatElapsedDuration(diagnostics.pendingMs)}
                          </span>
                        ) : null}
                        {!item.pending && diagnostics.latencyMs > 0 ? (
                          <span className="reference-diagnostic-pill">
                            Responded {formatElapsedDuration(diagnostics.latencyMs)}
                          </span>
                        ) : null}
                        {contradictionSignal ? (
                          <span className="reference-diagnostic-pill is-warn">Possible contradiction</span>
                        ) : null}
                      </p>
                      {contradictionSignal ? (
                        <div className="reference-contradiction-callout">
                          <strong>Consistency signal</strong>
                          <p>
                            Potential contradiction with an earlier assistant message on:{" "}
                            {contradictionSignal.subject || "shared context"}.
                          </p>
                        </div>
                      ) : null}
                      {item.detail || item.technicalDetail || item.chips?.length ? (
                        <article className={cx("reference-report-panel compact", item.technicalDetail && !item.detail ? "trace-only" : "")}>
                          {item.detail ? <p>{item.detail}</p> : null}
                          {item.technicalDetail ? (
                            <details className="reference-inline-trace">
                              <summary>Route detail</summary>
                              <p>{item.technicalDetail}</p>
                            </details>
                          ) : null}
                          {item.chips?.length ? (
                            <div className="reference-chip-row">
                              {item.chips.map(chip => (
                                <span className="reference-mini-pill" key={`${item.id}-${chip}`}>
                                  {chip}
                                </span>
                              ))}
                            </div>
                          ) : null}
                          <div className="reference-report-foot">
                            <div className="reference-report-actions">
                              <button onClick={() => onRequestAction?.("run:message-copy", { messageId: item.id })} type="button">Copy</button>
                              <button onClick={() => onRequestAction?.("run:message-comment", { messageId: item.id })} type="button">Comment</button>
                              <button onClick={() => onRequestAction?.("run:message-retry", { messageId: item.id })} type="button">Retry</button>
                            </div>
                            <span>{item.meta || "Now"}</span>
                          </div>
                        </article>
                      ) : null}
                    </div>
                  </div>
                );
              })}
              {transcriptVirtualized && transcriptWindow.bottomPadding > 0 ? (
                <div
                  aria-hidden="true"
                  className="reference-chat-virtual-spacer"
                  style={{ height: transcriptWindow.bottomPadding }}
                />
              ) : null}
            </div>

            <ComposerDock
              compact
              draft={draft}
              onAttach={onAttach}
              onChangeDraft={onChangeDraft}
              onDictation={onDictation}
              onPaste={onPaste}
              onSubmit={onSend}
              placeholder="Message Hermes..."
            >
              {showSlashCommands ? (
                <SlashCommandPanel
                  className="in-composer"
                  commands={slashCommands}
                  draft={draft}
                  onUseCommand={onUseSlashCommand}
                />
              ) : null}
            </ComposerDock>
          </section>

          <aside className="reference-workbench-side">
            <div className="reference-workbench-tabs">
              {workbenchTabs.map(tab => (
                <button
                  className={workbenchTab === tab.id ? "active" : ""}
                  key={tab.id}
                  onClick={() => setWorkbenchTab(tab.id)}
                  type="button"
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="reference-workbench-url">
              <span>{runtimeCompartment?.cwd || "workspace://current"}</span>
              <b>{runtimeCompartment?.streaming === "live" ? "Live" : "Idle"}</b>
            </div>
            <div className="reference-workbench-canvas">
              {workbenchTab === "browser" || workbenchTab === "snapshot" ? (
                <article className="reference-workbench-card">
                  <h4>Overview</h4>
                  <p>Session: {runtimeCompartment?.sessionId || "pending"}</p>
                  <p>Host: {runtimeCompartment?.host || "local"}</p>
                  <p>Runtime: {titleizeToken(runtimeCompartment?.runtime || selectedRuntime)}</p>
                  <p>Model: {runtimeCompartment?.route?.model || selectedRoute.model || selectedModelLabel}</p>
                </article>
              ) : null}
              {workbenchTab === "terminal" ? (
                <article className="reference-workbench-card">
                  <h4>Runtime terminal</h4>
                  <p>{compartmentEvents[compartmentEvents.length - 1]?.summary || "No terminal events yet."}</p>
                </article>
              ) : null}
              {workbenchTab === "diff" ? (
                <article className="reference-workbench-card">
                  <h4>Diff summary</h4>
                  <p>{processMoments[processMoments.length - 1]?.detail || "No diff summary reported yet."}</p>
                </article>
              ) : null}
              {workbenchTab === "files" ? (
                <article className="reference-workbench-card">
                  <h4>Files changed</h4>
                  {compartmentFiles.length ? (
                    <ul>
                      {compartmentFiles.map(file => <li key={`workbench-file-${file}`}>{file}</li>)}
                    </ul>
                  ) : (
                    <p>No file receipts yet (chat replies can be read-only).</p>
                  )}
                </article>
              ) : null}
              {workbenchTab === "control" ? (
                <article className="reference-workbench-card">
                  <h4>Computer control</h4>
                  <p>{runtimeCompartment?.restartControls?.canResume ? "Resume available" : "No resume control exposed yet."}</p>
                </article>
              ) : null}
            </div>
            <div className="reference-workbench-annotations">
              <div className="reference-workbench-annotations-head">
                <span>Annotations</span>
                <b>{feedbackItems.length}</b>
              </div>
              {feedbackItems.slice(0, 3).map(item => (
                <article className="reference-workbench-annotation" key={`annotation-${item.id}`}>
                  <strong>{item.author}</strong>
                  <p>{item.body}</p>
                </article>
              ))}
            </div>
          </aside>
        </div>

        <section className="reference-runtime-dock">
          <article className="reference-runtime-card">
            <h4>Tool calls</h4>
            <ul>
              {compartmentEvents.length ? compartmentEvents.map((event, index) => (
                <li key={`tool-call-${event.kind || index}`}>{event.kind || "event"} - {event.summary || "recorded"}</li>
              )) : <li>No tool calls yet.</li>}
            </ul>
          </article>
          <article className="reference-runtime-card">
            <h4>Files changed</h4>
            <ul>
              {compartmentFiles.length ? compartmentFiles.map(file => <li key={`file-change-${file}`}>{file}</li>) : <li>No file changes yet.</li>}
            </ul>
          </article>
          <article className="reference-runtime-card">
            <h4>Approvals</h4>
            <ul>
              {compartmentApprovals.length ? compartmentApprovals.map((approval, index) => (
                <li key={`approval-${approval?.id || index}`}>{approval?.status || approval?.decision || "approved"}</li>
              )) : <li>No approvals yet.</li>}
            </ul>
          </article>
          <article className="reference-runtime-card">
            <h4>Runtime status</h4>
            <p>Current branch: {runtimeCompartment?.cwd || "workspace not attached"}</p>
            <p>Session ID: {runtimeCompartment?.sessionId || "pending"}</p>
            <p>Tokens: recorded in runtime events</p>
          </article>
          <article className="reference-runtime-card">
            <h4>Event stream</h4>
            <ul>
              {processMoments.length ? processMoments.map(item => <li key={`stream-${item.id}`}>{item.title}</li>) : <li>No event stream yet.</li>}
            </ul>
          </article>
        </section>
      </section>
    );
  }

  return (
    <section className={cx("reference-agent-run", `mode-${conversationMode}`)}>
      {showMissionPanels && missionLoop ? (
        <article className="reference-run-summary">
          <div>
            <span>Cycle phase</span>
            <strong>{missionLoop.currentCyclePhase || "Plan"}</strong>
          </div>
          <div>
            <span>Cycles</span>
            <strong>{missionLoop.cycleCount || 0}</strong>
          </div>
          <div>
            <span>Continuity</span>
            <strong>{missionLoop.continuityDetail || missionLoop.continuityState || "Steady"}</strong>
          </div>
          <div>
            <span>Work engine</span>
            <strong>{missionLoop.currentRuntimeLane || "Primary thread"}</strong>
          </div>
        </article>
      ) : null}

      {showMissionPanels && missionLoop ? (
        <article className="reference-run-summary t3-lane-surface">
          <div>
            <span>Runtime mode</span>
            <strong>{runtimeModeLabel}</strong>
          </div>
          <div>
            <span>Provider/runtime</span>
            <strong>{selectedRoute.provider || "auto"} · {selectedRoute.model || selectedModelLabel}</strong>
          </div>
          <div>
            <span>Checkpoint</span>
            <strong>{checkpointSummary}</strong>
          </div>
          <div>
            <span>Diff</span>
            <strong>{diffSummary}</strong>
          </div>
          <div>
            <span>Lanes</span>
            <strong>{Math.max(1, delegatedLanes.length + 1)}</strong>
          </div>
          <div>
            <span>Artifacts</span>
            <strong>{artifactItems.length || 0}</strong>
          </div>
        </article>
      ) : null}

      {showMissionPanels ? (
        <article
          className="reference-selected-report-reader"
          data-reference-selected-report-reader="true"
          data-selected-message-id={selectedRunMessageId}
          data-preview-state="selected-message"
        >
          <div className="reference-selected-report-head">
            <div>
              <span>Selected live report</span>
              <strong>{selectedRunMessage ? agentMessageDisplayTitle(selectedRunMessage) : "Waiting for Hermes/runtime output"}</strong>
            </div>
            <small>{selectedRunMessageMeta || "Mission thread evidence"}</small>
          </div>
          {selectedRunMessageBody ? (
            <pre data-reference-selected-report-body="true">{selectedRunMessageBody}</pre>
          ) : (
            <p>
              {renderedMessages.length
                ? "This selected row has no detailed runtime body yet. The reader stays empty instead of keeping an older frame."
                : "The mission detail endpoint has not returned Hermes/runtime messages yet."}
            </p>
          )}
        </article>
      ) : null}

      {runtimeCompartment ? (
        <article className="agent-compartment-box" aria-label="Active agent runtime compartment">
          <div className="agent-compartment-box-head">
            <div>
              <p className="eyebrow">Live runtime compartments · Runtime compartment</p>
              <h2>{runtimeCompartment.sessionId || "pending session"}</h2>
            </div>
            <div className="agent-compartment-status">
              <span className={cx("agent-live-dot", runtimeCompartment.streaming === "live" && "live")} />
              <strong>{titleizeToken(runtimeCompartment.state || "recorded")}</strong>
              <span>{runtimeCompartment.streaming === "live" ? "streaming" : "recorded"}</span>
            </div>
          </div>
          <div className="agent-compartment-matrix">
            <div>
              <span>Runtime</span>
              <strong>{titleizeToken(runtimeCompartment.runtime || selectedRuntime)}</strong>
            </div>
            <div>
              <span>Route</span>
              <strong>
                {runtimeCompartment.route?.provider
                  ? `${titleizeToken(runtimeCompartment.route.provider)} / ${runtimeCompartment.route?.model || runtimeCompartment.route?.model_id || selectedModelLabel}`
                  : selectedModelLabel}
              </strong>
            </div>
            <div>
              <span>Host</span>
              <strong>{titleizeToken(runtimeCompartment.host || "local")}</strong>
            </div>
            <div>
              <span>Execution root</span>
              <strong>{runtimeCompartment.cwd || "Not selected"}</strong>
            </div>
          </div>
          <div className="agent-compartment-body agent-live-workbench-grid">
            <div className="agent-compartment-lane">
              <div className="agent-compartment-subhead">
                <span>Hermes mission evidence · Tool/action timeline</span>
                <b>{compartmentEvents.length}</b>
              </div>
              <div className="agent-compartment-event-list">
                {compartmentEvents.length ? compartmentEvents.map((event, index) => (
                  <div className="agent-compartment-event" key={`${event.kind || "event"}-${event.at || index}`}>
                    <span>{titleizeToken(event.kind || event.status || "event")}</span>
                    <strong>{event.summary || "Runtime event recorded"}</strong>
                    <small>{event.at || event.status || "recorded"}</small>
                  </div>
                )) : <p className="agent-compartment-empty">No live tool events have reached the compartment yet.</p>}
              </div>
            </div>
            <div className="agent-compartment-lane">
              <div className="agent-compartment-subhead">
                <span>NAS deploy readiness · Files and approvals</span>
                <b>{compartmentFiles.length + compartmentApprovals.length}</b>
              </div>
              <div className="agent-compartment-chip-list">
                {compartmentFiles.map(file => <code key={`file-${file}`}>{file}</code>)}
                {compartmentApprovals.map((approval, index) => (
                  <span key={`approval-${approval?.id || index}`}>{approval?.status || approval?.decision || "approval recorded"}</span>
                ))}
                {compartmentFiles.length + compartmentApprovals.length === 0 ? (
                  <p className="agent-compartment-empty">No changed file or approval receipts attached yet.</p>
                ) : null}
              </div>
            </div>
          </div>
          <div className="agent-compartment-body agent-live-workbench-grid">
            <div className="agent-compartment-lane">
              <div className="agent-compartment-subhead">
                <span>Generated image artifacts</span>
                <b>{visibleGeneratedArtifacts.length}/{generatedArtifactRows.length}</b>
              </div>
              <div className="agent-artifact-grid">
                {visibleGeneratedArtifacts.length ? visibleGeneratedArtifacts.map((artifact, index) => {
                  const imageUrl = artifactUrlForRecord(artifact);
                  const manifestUrl = resolveReferenceArtifactUrl(artifact?.manifestUrl || artifact?.manifestPath || "");
                  const label = artifactLabelForRecord(artifact, `artifact-${index + 1}`);
                  return (
                    <figure className="agent-artifact-card" key={`${artifact?.artifactId || label}-${index}`}>
                      {imageUrl ? <img alt={label} src={imageUrl} /> : <div className="builder-live-review-image-missing">Preview not served</div>}
                      <figcaption>
                        <strong>{label}</strong>
                        <span>{artifact?.servedArtifactId ? `served ${String(artifact.servedArtifactId).slice(0, 10)}` : artifact?.provider || "served artifact"}</span>
                        {manifestUrl ? <a href={manifestUrl} rel="noreferrer" target="_blank">Manifest</a> : null}
                      </figcaption>
                    </figure>
                  );
                }) : <p className="agent-compartment-empty">No served image artifacts are available yet.</p>}
              </div>
              {visibleGeneratedArtifacts.length < generatedArtifactRows.length ? (
                <button
                  className="agent-proof-page-button"
                  onClick={() => setGeneratedArtifactPage(page => page + 1)}
                  type="button"
                >
                  Show more artifacts
                </button>
              ) : null}
            </div>
            <div className="agent-compartment-lane">
              <div className="agent-compartment-subhead">
                <span>Hermes mission evidence</span>
                <b>{visibleHermesEvidence.length}/{hermesEvidenceRows.length}</b>
              </div>
              <div className="agent-compartment-event-list">
                {visibleHermesEvidence.length ? visibleHermesEvidence.map((item, index) => (
                  <div className="agent-compartment-event" key={`${item.missionId || "hermes"}-${item.timestamp || index}`}>
                    <span>{titleizeToken(item.source || item.status || "evidence")}</span>
                    <strong>{item.message || item.objective || "Hermes evidence recorded"}</strong>
                    <small>{item.timestamp || item.status || "recorded"}</small>
                    {asList(item.artifacts).length ? (
                      <div className="agent-evidence-artifact-strip">
                        {asList(item.artifacts).slice(0, 3).map((artifact, artifactIndex) => {
                          const artifactUrl = artifactUrlForRecord(artifact);
                          const artifactLabel = artifactLabelForRecord(artifact, `evidence-${artifactIndex + 1}`);
                          const artifactPath = artifact?.path || artifact?.artifactPath || artifact?.servedUrl || artifactUrl;
                          return (
                            <a href={artifactUrl || "#"} key={`${item.missionId || "evidence"}-${artifactLabel}-${artifactIndex}`} rel="noreferrer" target="_blank">
                              {isImageArtifactPath(artifactPath) && artifactUrl ? <img alt="" src={artifactUrl} /> : null}
                              <span>{artifactLabel}</span>
                            </a>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                )) : <p className="agent-compartment-empty">No Hermes evidence has been captured yet.</p>}
              </div>
              {visibleHermesEvidence.length < hermesEvidenceRows.length ? (
                <button
                  className="agent-proof-page-button"
                  onClick={() => setHermesEvidencePage(page => page + 1)}
                  type="button"
                >
                  Show more evidence
                </button>
              ) : null}
            </div>
          </div>
          <div className="agent-compartment-lane agent-nas-readiness-panel">
            <div className="agent-compartment-subhead">
              <span>NAS deploy readiness</span>
              <b>{visibleNasChecks.filter(check => check?.passed).length}/{visibleNasChecks.length}</b>
            </div>
            <div className="agent-nas-check-grid">
              {visibleNasChecks.length ? visibleNasChecks.map(check => (
                <article className={cx("agent-nas-check", check.passed ? "passed" : check.required ? "blocked" : "warn")} key={check.checkId || check.label}>
                  <span>{check.required ? "Required" : "Offline check"}</span>
                  <strong>{check.label}</strong>
                  <p>{check.details}</p>
                </article>
              )) : <p className="agent-compartment-empty">NAS deploy readiness has not been reported by the backend yet.</p>}
            </div>
          </div>
          <div className="agent-compartment-actions">
            <button onClick={() => onRequestAction?.("run:resume")} type="button">Resume</button>
            <button onClick={() => onRequestAction?.("run:proof")} type="button">Proof</button>
            <button onClick={() => onRequestAction?.("run:queue")} type="button">Queue</button>
          </div>
        </article>
      ) : null}

      {showMissionPanels && delegatedLanes.length > 0 ? (
        <article className="reference-status-panel">
          <div className="reference-status-panel-head">
            <h3>Concurrent runtime lanes</h3>
          </div>
          <div className="reference-status-list">
            {delegatedLanes.slice(0, 6).map((lane, index) => (
              <div className="reference-status-row" key={lane.id || lane.session_id || `lane-${index}`}>
                <StepState
                  done={String(lane.status || "").toLowerCase() === "completed"}
                  pending={String(lane.status || "").toLowerCase() === "running"}
                  label={`${lane.role || `Lane ${index + 1}`} · ${lane.provider || lane.runtime_id || "runtime"}`}
                />
                <p>{lane.detail || lane.last_event || lane.status || "Active"}</p>
              </div>
            ))}
          </div>
        </article>
      ) : null}

      <div className="reference-chat-column">
        {renderedMessages.length === 0 ? (
          <article className="reference-conversation-blank">
            <strong>{showMissionPanels ? "Mission conversation is ready" : "New conversation"}</strong>
            <p>
              {showMissionPanels
                ? "Send a message or wait for the runtime to publish its next readable update."
                : "Ask a question or switch the mode to Mission when you want file changes and a tracked work loop."}
            </p>
            {!showMissionPanels ? (
              <button className="reference-black-button" onClick={() => onRequestAction?.("flow:new-conversation")} type="button">
                Start new conversation
              </button>
            ) : null}
          </article>
        ) : null}

        {renderedMessages.map((item, index) => {
          const messageKey = stableAgentMessageKey(item, `reference-run-message-${index}`);
          const selected = selectedRunMessageId === messageKey;
          return item.role === "user" ? (
            <div
              aria-pressed={selected}
              className={cx("reference-user-bubble", selected && "selected")}
              data-mission-id={item.missionId || activeMissionId}
              data-runtime-id={item.runtimeId || activeRuntimeId}
              data-selected-agent-message={selected ? "true" : "false"}
              data-turn-id={item.id}
              onClick={event => selectRunMessage(messageKey, event)}
              onKeyDown={event => handleRunMessageKeyDown(event, messageKey)}
              role="button"
              tabIndex={0}
              key={item.id}
            >
              <p>{item.title}</p>
              <span>{item.meta || "Now"}</span>
            </div>
          ) : (
            <div
              aria-pressed={selected}
              className={cx("reference-agent-thread", item.pending ? "is-pending" : "", selected && "selected")}
              data-mission-id={item.missionId || activeMissionId}
              data-runtime-id={item.runtimeId || activeRuntimeId}
              data-runtime-report={isRuntimeOutputAgentMessage(item) ? "true" : "false"}
              data-selected-agent-message={selected ? "true" : "false"}
              data-turn-id={item.id}
              onClick={event => selectRunMessage(messageKey, event)}
              onKeyDown={event => handleRunMessageKeyDown(event, messageKey)}
              role="button"
              tabIndex={0}
              key={item.id}
            >
              <div className="reference-agent-avatar">
                <div className="reference-brand-mark tiny">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
              <div className="reference-agent-thread-body">
                <p className="reference-thread-lead">
                  {item.pending ? <CircleDashed className="pending" size={16} strokeWidth={2.1} /> : null}
                  <span>{item.title}</span>
                </p>
                {item.detail || item.technicalDetail || item.chips?.length ? (
                  <article className={cx("reference-report-panel compact", item.technicalDetail && !item.detail ? "trace-only" : "")}>
                    {item.detail ? <p>{item.detail}</p> : null}
                    {item.technicalDetail ? (
                      <details className="reference-inline-trace">
                        <summary>Route detail</summary>
                        <p>{item.technicalDetail}</p>
                      </details>
                    ) : null}
                    {item.chips?.length ? (
                      <div className="reference-chip-row">
                        {item.chips.map(chip => (
                          <span className="reference-mini-pill" key={`${item.id}-${chip}`}>
                            {chip}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    <div className="reference-report-foot">
                      <div className="reference-report-actions">
                        <button onClick={() => onRequestAction?.("run:message-copy", { messageId: item.id })} type="button">Copy</button>
                        <button onClick={() => onRequestAction?.("run:message-comment", { messageId: item.id })} type="button">Comment</button>
                        <button onClick={() => onRequestAction?.("run:message-retry", { messageId: item.id })} type="button">Retry</button>
                      </div>
                      <span>{item.meta || "Now"}</span>
                    </div>
                  </article>
                ) : null}
              </div>
            </div>
          );
        })}

        {showMissionPanels && processMoments.length > 0 ? (
          <article className="reference-status-panel">
            <div className="reference-status-panel-head">
              <h3>Live mission activity</h3>
              <button onClick={() => setShowTraceDetail(current => !current)} type="button">
                {showTraceDetail ? "Hide trace" : "Show trace"}
              </button>
            </div>
            <div className="reference-status-list">
              {processMoments.map((moment, index) => (
                <div className="reference-status-row" key={moment.id}>
                  <StepState
                    done={index < processMoments.length - 1}
                    label={moment.title}
                    pending={index === processMoments.length - 1}
                  />
                  {showTraceDetail && (moment.detail || moment.preview) ? (
                    <p>{moment.preview || moment.detail}</p>
                  ) : null}
                  <button
                    className="reference-row-comment"
                    onClick={() => onRequestAction?.("run:moment-comment", { momentId: moment.id })}
                    type="button"
                  >
                    Comment
                  </button>
                </div>
              ))}
            </div>
          </article>
        ) : null}

        {showMissionPanels && feedbackItems.length > 0 ? (
        <article className="reference-feedback-panel">
          <div className="reference-feedback-tabs">
            <button
              className={detailTab === "feedback" ? "active" : ""}
              onClick={() => setDetailTab("feedback")}
              type="button"
            >
              Feedback
            </button>
            <button
              className={detailTab === "notes" ? "active" : ""}
              onClick={() => setDetailTab("notes")}
              type="button"
            >
              Notes
            </button>
          </div>
          <div className="reference-feedback-list">
            {feedbackItems
              .filter(item => (detailTab === "feedback" ? item.role !== "note" : true))
              .slice(0, 3)
              .map(item => (
                <article className="reference-feedback-item" key={item.id}>
                  <div className="reference-feedback-meta">
                    <strong>{item.author}</strong>
                    <span>{item.meta}</span>
                  </div>
                  <p>{item.body}</p>
                  {item.role === "assistant" ? (
                    <div className="reference-feedback-actions">
                      <button onClick={() => onRequestAction?.("run:feedback-apply", { feedbackId: item.id })} type="button">Change applied</button>
                      <button onClick={() => onRequestAction?.("run:feedback-view", { feedbackId: item.id })} type="button">View change</button>
                    </div>
                  ) : null}
                </article>
              ))}
          </div>
        </article>
        ) : null}
      </div>

      <ComposerDock
        compact
        draft={draft}
        onAttach={onAttach}
        onChangeDraft={onChangeDraft}
        onDictation={onDictation}
        onPaste={onPaste}
        onSubmit={onSend}
        placeholder={
          activeCommentTarget
            ? "Add a live comment..."
            : showMissionPanels
              ? "Comment live or steer the mission..."
              : "Reply in this conversation..."
        }
      >
        {activeCommentTarget ? (
          <div className="reference-comment-target">
            <span>Commenting on {activeCommentTarget.kind || "item"}</span>
            <strong>{activeCommentTarget.title}</strong>
            <button onClick={() => onRequestAction?.("run:clear-comment-target")} type="button">Clear</button>
          </div>
        ) : null}
        {showMissionPanels ? (
          <>
            {actionModes.length > 0 ? (
              <div className="reference-mode-strip compact" aria-label="Run mode">
                {actionModes.map(option => (
                  <button
                    className={routeControls.actionMode === option.value ? "active" : ""}
                    key={`run-mode-${option.value}`}
                    onClick={() => routeControls.onActionModeChange?.(option.value)}
                    type="button"
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            ) : null}
            <div className="reference-docked-controls">
              <label className="reference-inline-select">
                <span>Work engine</span>
                <select onChange={event => onRuntimeChange(event.target.value)} value={selectedRuntime}>
                  {runtimeSelectOptions.map(option => (
                    <option key={`run-runtime-${option.value}`} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="reference-inline-select">
                <span>Route role</span>
                <input readOnly value={`${titleizeToken(routeControls.role || "executor")} (auto)`} />
              </label>
              <label className="reference-inline-select">
                <span>Model</span>
                <select onChange={event => routeControls.onFieldChange?.("model", event.target.value)} value={selectedRoute.model || ""}>
                  <option value="">{selectedModelLabel}</option>
                  {asList(routeOptions.models).map(option => (
                    <option key={`run-route-model-${option}`} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="reference-inline-select">
                <span>Effort</span>
                <select onChange={event => routeControls.onFieldChange?.("effort", event.target.value)} value={selectedRoute.effort || "default"}>
                  {asList(routeOptions.efforts).map(option => (
                    <option key={`run-route-effort-${option.value}`} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <button className="reference-tool-button" onClick={() => routeControls.onSave?.()} type="button">
                Save route
              </button>
            </div>
          </>
        ) : null}

        {showSlashCommands ? (
          <SlashCommandPanel
            className="in-composer"
            commands={slashCommands}
            draft={draft}
            onUseCommand={onUseSlashCommand}
          />
        ) : null}
      </ComposerDock>
    </section>
  );
}

function LivePreviewSurface(props) {
  const {
    changedItems = [],
    draft,
    feedbackItems = [],
    generatedImageArtifacts = [],
    hermesEvidenceItems = [],
    messages = [],
    nasDeployChecks = [],
    onAttach,
    onChangeDraft,
    onDictation,
    onPaste,
    onRequestAction,
    onSend,
    onUseSlashCommand,
    projectLabel,
    runtimeCompartment,
    slashCommands = [],
    timelineMoments = [],
  } = props;
  const [previewTab, setPreviewTab] = useState("preview");
  const [previewDevice, setPreviewDevice] = useState("desktop");
  const assistantMoments = timelineMoments.slice(-3);
  const latestUserMessage = [...messages].reverse().find(item => item.role === "user");
  const latestAssistantMessage = [...messages].reverse().find(item => item.role === "assistant");
  const showSlashCommands = String(draft || "").trim().startsWith("/");
  const hasRuntimeCompartment = Boolean(runtimeCompartment);
  const agentActivityLabel = hasRuntimeCompartment
    ? runtimeCompartment?.streaming === "live"
      ? "Working"
      : "Recorded"
    : "Waiting for runtime";
  const agentActivityDetail = hasRuntimeCompartment
    ? latestAssistantMessage?.title || "Runtime evidence is attached to this live preview."
    : "The preview is open, but no live runtime session has attached yet.";
  const evidenceRows = [
    {
      id: "runtime",
      action: "live:evidence:runtime",
      label: "Runtime compartment",
      value: runtimeCompartment?.sessionId || "No live session",
      detail: runtimeCompartment?.state || runtimeCompartment?.runtime || "Waiting for runtime lane",
      tone: runtimeCompartment ? "good" : "warn",
    },
    {
      id: "images",
      action: "live:evidence:images",
      label: "Generated image artifacts",
      value: String(asList(generatedImageArtifacts).length),
      detail: asList(generatedImageArtifacts)[0]?.provider || "No served image artifacts",
      tone: asList(generatedImageArtifacts).length ? "good" : "neutral",
    },
    {
      id: "hermes",
      action: "live:evidence:hermes",
      label: "Hermes mission evidence",
      value: String(asList(hermesEvidenceItems).length),
      detail: asList(hermesEvidenceItems)[0]?.status || "No Hermes evidence captured",
      tone: asList(hermesEvidenceItems).length ? "good" : "warn",
    },
    {
      id: "nas",
      action: "live:evidence:nas",
      label: "NAS deploy readiness",
      value: `${asList(nasDeployChecks).filter(check => check?.passed).length}/${asList(nasDeployChecks).length}`,
      detail: asList(nasDeployChecks).length ? "Readiness checks attached" : "No readiness report",
      tone: asList(nasDeployChecks).some(check => check?.required && !check?.passed) ? "warn" : "good",
    },
  ];

  return (
    <section className="reference-live-surface">
      <div className="reference-live-sidebar-column">
        <article className="reference-live-card">
          <div className="reference-live-card-head">
            <div className="reference-live-agent">
              <div className="reference-brand-mark tiny">
                <span />
                <span />
                <span />
              </div>
              <div>
                <strong>Syntelos Agent</strong>
                <span>{agentActivityLabel}</span>
              </div>
            </div>
          </div>
          <p>{agentActivityDetail}</p>
          <div className="reference-live-editing">
            <span>
              Editing: {changedItems[0] || "Current project surface"}
            </span>
            <CircleDashed size={18} strokeWidth={2.1} />
          </div>
        </article>

        {latestUserMessage ? (
          <article className="reference-live-card">
            <div className="reference-live-agent user">
              <div className="reference-user-mini">O</div>
              <div>
                <strong>You</strong>
              </div>
            </div>
            <p>{latestUserMessage.title}</p>
          </article>
        ) : null}

        {latestAssistantMessage?.detail ? (
          <article className="reference-live-card">
            <div className="reference-live-agent">
              <div className="reference-brand-mark tiny">
                <span />
                <span />
                <span />
              </div>
              <div>
                <strong>Syntelos Agent</strong>
                <span>Thinking</span>
              </div>
            </div>
            <p>{latestAssistantMessage.detail}</p>
          </article>
        ) : null}

        <article className="reference-live-card reference-live-evidence-card">
          <div className="reference-live-agent">
            <div className="reference-brand-mark tiny">
              <span />
              <span />
              <span />
            </div>
            <div>
              <strong>Live evidence</strong>
              <span>Runtime, artifacts, Hermes, NAS</span>
            </div>
          </div>
          <div className="reference-live-evidence-grid">
            {evidenceRows.map(row => (
              <button
                className={cx("reference-live-evidence-row", row.tone)}
                key={row.id}
                onClick={() => onRequestAction?.(row.action)}
                type="button"
              >
                <span>{row.label}</span>
                <strong>{row.value}</strong>
                <small>{row.detail}</small>
              </button>
            ))}
          </div>
        </article>

        <article className="reference-live-card">
          <div className="reference-live-agent">
            <div className="reference-brand-mark tiny">
              <span />
              <span />
              <span />
            </div>
            <div>
              <strong>Syntelos Agent</strong>
              <span>Applying changes</span>
            </div>
          </div>
          <div className="reference-checklist">
            {assistantMoments.map((moment, index) => (
              <StepState
                done={index < assistantMoments.length - 1}
                key={moment.id}
                label={moment.title}
                pending={index === assistantMoments.length - 1}
              />
            ))}
          </div>
        </article>

        <ComposerDock
          compact
          draft={draft}
          onAttach={onAttach}
          onChangeDraft={onChangeDraft}
          onDictation={onDictation}
          onPaste={onPaste}
          onSubmit={onSend}
          placeholder="Ask your agent anything..."
        >
          {showSlashCommands ? (
            <SlashCommandPanel
              className="in-composer"
              commands={slashCommands}
              draft={draft}
              onUseCommand={onUseSlashCommand}
            />
          ) : null}
        </ComposerDock>
      </div>

      <div className="reference-preview-stage">
        <div className="reference-preview-toolbar">
          <div className="reference-preview-tabs">
            <button
              className={previewTab === "preview" ? "active" : ""}
              onClick={() => setPreviewTab("preview")}
              type="button"
            >
              Preview
            </button>
            <button
              className={previewTab === "files" ? "active" : ""}
              onClick={() => setPreviewTab("files")}
              type="button"
            >
              Files
            </button>
            <button
              className={previewTab === "terminal" ? "active" : ""}
              onClick={() => setPreviewTab("terminal")}
              type="button"
            >
              Terminal
            </button>
          </div>
          <div className="reference-preview-actions">
            <div className="reference-device-toggle">
              <button
                className={previewDevice === "desktop" ? "active" : ""}
                onClick={() => setPreviewDevice("desktop")}
                type="button"
              >
                <Monitor size={16} strokeWidth={1.9} />
              </button>
              <button
                className={previewDevice === "laptop" ? "active" : ""}
                onClick={() => setPreviewDevice("laptop")}
                type="button"
              >
                <Laptop size={16} strokeWidth={1.9} />
              </button>
              <button
                className={previewDevice === "mobile" ? "active" : ""}
                onClick={() => setPreviewDevice("mobile")}
                type="button"
              >
                <Smartphone size={16} strokeWidth={1.9} />
              </button>
            </div>
            <IconButton icon={RefreshCw} label="Refresh preview" onClick={() => onRequestAction?.("live:refresh-preview")} />
            <IconButton icon={Expand} label="Expand preview" onClick={() => onRequestAction?.("live:expand-preview")} />
          </div>
        </div>

        <div className="reference-preview-canvas">
          <div className="reference-preview-browser">
            <div className="reference-browser-nav">
              <div className="reference-browser-brand">
                <div className="reference-brand-mark tiny">
                  <span />
                  <span />
                  <span />
                </div>
                <strong>{projectLabel}</strong>
              </div>
              <nav>
                <span>Product</span>
                <span>Features</span>
                <span>Pricing</span>
                <span>Resources</span>
              </nav>
              <button
                className="reference-browser-cta"
                onClick={() => onRequestAction?.("live:cta-start")}
                type="button"
              >
                Get Started
              </button>
            </div>

            <div className="reference-browser-hero">
              <div className="reference-browser-chip">
                <span>New</span>
                <strong>{changedItems[0] || `${projectLabel} is updating live`}</strong>
              </div>
              <h2>{latestAssistantMessage?.title || `Build better software with ${projectLabel}.`}</h2>
              <p>
                {latestAssistantMessage?.detail ||
                  "Live preview updates reflect the latest active mission decisions and UI edits."}
              </p>
              <div className="reference-browser-actions">
                <button className="primary" onClick={() => onRequestAction?.("live:start-building")} type="button">Start Building</button>
                <button className="secondary" onClick={() => onRequestAction?.("live:view-demo")} type="button">View Demo</button>
              </div>
              <div className="reference-browser-benefits">
                <span>No credit card required</span>
                <span>14-day free trial</span>
                <span>Cancel anytime</span>
              </div>
            </div>

            <div className="reference-preview-comment">
              <div className="reference-preview-comment-head">
                <span>{projectLabel}</span>
                <strong>You</strong>
                <em>Just now</em>
              </div>
              <p>{latestUserMessage?.title || "Add feedback or ask the agent..."}</p>
              <div className="reference-preview-comment-foot">
                <button onClick={() => onRequestAction?.("live:comment-react")} type="button">React</button>
                <button className="send" onClick={() => onRequestAction?.("live:comment-send")} type="button">Send</button>
              </div>
            </div>

            <div className="reference-preview-dashboard">
              <aside className="reference-preview-sidebar">
                <strong>{projectLabel}</strong>
                <span className="active">Overview</span>
                <span>Projects</span>
                <span>Deployments</span>
                <span>Analytics</span>
              </aside>
              <div className="reference-preview-dashboard-main">
                <div className="reference-preview-dashboard-head">
                  <strong>Overview</strong>
                </div>
                <div className="reference-preview-stats">
                  <article>
                    <span>Tracked changes</span>
                    <strong>{Math.max(changedItems.length, 1)}</strong>
                    <p>Visible in this mission</p>
                  </article>
                  <article>
                    <span>Feedback items</span>
                    <strong>{feedbackItems.length}</strong>
                    <p>Across notes and comments</p>
                  </article>
                  <article>
                    <span>Timeline moments</span>
                    <strong>{timelineMoments.length}</strong>
                    <p>Captured in the live trace</p>
                  </article>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function BuilderMetricCard({ item }) {
  const Icon = item.icon;
  return (
    <article className="reference-builder-metric">
      <div className="reference-builder-metric-icon">
        <Icon size={24} strokeWidth={1.9} />
      </div>
      <div className="reference-builder-metric-copy">
        <span>{item.label}</span>
        <strong>{item.value}</strong>
        <p className={cx("reference-metric-delta", item.tone)}>{item.delta}</p>
      </div>
      {item.id === "projects" ? <div aria-hidden="true" className="reference-mini-sparkline" /> : null}
    </article>
  );
}

function StatusBadge({ tone, label }) {
  return <span className={cx("reference-status-badge", tone)}>{label}</span>;
}

function parseDurationSeconds(value) {
  const text = String(value || "");
  let total = 0;
  const minutes = text.match(/(\d+)\s*m/);
  const seconds = text.match(/(\d+)\s*s/);
  if (minutes) {
    total += Number(minutes[1]) * 60;
  }
  if (seconds) {
    total += Number(seconds[1]);
  }
  return total || 0;
}

function formatMetricDuration(seconds) {
  if (!seconds) {
    return "—";
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return minutes > 0 ? `${minutes}m ${String(remainder).padStart(2, "0")}s` : `${remainder}s`;
}

function buildBuilderMetrics(rows) {
  const safeRows = asList(rows);
  const activeRuns = safeRows.filter(item => item.statusTone === "running").length;
  const blockedRuns = safeRows.filter(item => ["failed", "warn"].includes(item.statusTone)).length;
  const successRates = safeRows
    .map(item => item.successRate)
    .filter(value => typeof value === "number" && Number.isFinite(value));
  const averageSuccess = successRates.length
    ? Math.round(successRates.reduce((total, value) => total + value, 0) / successRates.length)
    : 0;
  const turningPoints = safeRows.map(item => parseDurationSeconds(item.turningPoint)).filter(Boolean);
  const averageTurningPoint = turningPoints.length
    ? Math.round(turningPoints.reduce((total, value) => total + value, 0) / turningPoints.length)
    : 0;
  return [
    {
      id: "projects",
      label: "Total Projects",
      value: String(safeRows.length),
      delta: safeRows.length ? "Tracked from live missions" : "No live missions yet",
      tone: safeRows.length ? "up" : "flat",
      icon: Code2,
    },
    {
      id: "runs",
      label: "Active Runs",
      value: String(activeRuns),
      delta: blockedRuns ? `${blockedRuns} need attention` : "No blockers recorded",
      tone: blockedRuns ? "down" : activeRuns ? "up" : "flat",
      icon: Play,
    },
    {
      id: "success",
      label: "Success Rate",
      value: averageSuccess ? `${averageSuccess}%` : "—",
      delta: successRates.length ? `${successRates.length} run signal${successRates.length === 1 ? "" : "s"}` : "Waiting for run data",
      tone: averageSuccess >= 90 ? "up" : averageSuccess ? "down" : "flat",
      icon: CircleCheckBig,
    },
    {
      id: "turning-point",
      label: "Avg. Turning Point",
      value: formatMetricDuration(averageTurningPoint),
      delta: turningPoints.length ? "Derived from mission state" : "Waiting for timing data",
      tone: averageTurningPoint ? "up" : "flat",
      icon: Clock3,
    },
  ];
}

function BuilderSurface(props) {
  const {
    builderDetailOpen = false,
    builderRows = [],
    changedItems = [],
    feedbackItems = [],
    flowProjects = [],
    onBackFromBuilder,
    onOpenBuilderDetail,
    onRequestAction,
    onSelectFlow,
    onSelectProject,
    projectLabel,
    ruleSets = [],
    activeRuleSetId = "",
    onOpenSkillStudio,
    selectedProjectId,
    timelineMoments = [],
  } = props;
  const [builderSearch, setBuilderSearch] = useState("");
  const [builderPage, setBuilderPage] = useState(1);
  const [detailFlowSearch, setDetailFlowSearch] = useState("");
  const [detailTab, setDetailTab] = useState("flows");
  const [detailPreviewTab, setDetailPreviewTab] = useState("preview");
  const [detailFeedbackTab, setDetailFeedbackTab] = useState("feedback");
  const pageSize = 8;
  const builderSearchQuery = String(builderSearch || "").trim().toLowerCase();
  const filteredBuilderRows =
    builderSearchQuery.length === 0
      ? builderRows
      : builderRows.filter(row =>
          [row.name, row.description, row.status, row.id]
            .map(value => String(value || "").toLowerCase())
            .some(value => value.includes(builderSearchQuery)),
        );
  const totalPages = Math.max(1, Math.ceil(filteredBuilderRows.length / pageSize));
  const effectiveBuilderPage = Math.min(builderPage, totalPages);
  const pageStart = (effectiveBuilderPage - 1) * pageSize;
  const pagedBuilderRows = filteredBuilderRows.slice(pageStart, pageStart + pageSize);
  const selectedRow = builderRows.find(item => item.selected) || builderRows[0] || null;
  const activeProject =
    flowProjects.find(item => item.id === selectedProjectId) || flowProjects[0] || null;
  const detailFlowQuery = String(detailFlowSearch || "").trim().toLowerCase();
  const detailFlowProjects =
    detailFlowQuery.length === 0
      ? flowProjects
      : flowProjects
          .map(project => {
            const filteredFlows = asList(project.flows).filter(flow =>
              [flow.title, flow.status, flow.updated]
                .map(value => String(value || "").toLowerCase())
                .some(value => value.includes(detailFlowQuery)),
            );
            const projectMatches = String(project.title || "").toLowerCase().includes(detailFlowQuery);
            return {
              ...project,
              flows: projectMatches ? asList(project.flows) : filteredFlows,
            };
          })
          .filter(project => asList(project.flows).length > 0);
  const builderHighlights = [
    ["Success rate", `${selectedRow?.successRate ?? 0}%`],
    ["Runs", `${selectedRow?.runs ?? 0}`],
    ["Turning point", selectedRow?.turningPoint || "—"],
    ["Last update", selectedRow?.updated || selectedRow?.lastRunMeta || "—"],
  ];
  const virtualTimeline = useVirtualWindow(timelineMoments, {
    itemHeight: 92,
    viewportHeight: 430,
    overscan: 5,
  });
  const builderMetrics = buildBuilderMetrics(builderRows);
  const openBuilderDetailFromKey = (event, rowId) => {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }
    event.preventDefault();
    onOpenBuilderDetail(rowId);
  };

  if (builderDetailOpen && selectedRow) {
    return (
      <section className="reference-builder-detail">
        <div className="reference-builder-detail-column left">
          <button className="reference-back-link" onClick={onBackFromBuilder} type="button">
            <ArrowLeft size={15} strokeWidth={2} />
            <span>Back to Projects</span>
          </button>
          <div className="reference-builder-detail-head">
            <strong>{activeProject?.title || projectLabel}</strong>
            <StatusBadge label={selectedRow.status} tone={selectedRow.statusTone} />
          </div>
          <div className="reference-detail-tabs">
            <button className={detailTab === "overview" ? "active" : ""} onClick={() => setDetailTab("overview")} type="button">Overview</button>
            <button className={detailTab === "flows" ? "active" : ""} onClick={() => setDetailTab("flows")} type="button">Flows</button>
            <button className={detailTab === "files" ? "active" : ""} onClick={() => setDetailTab("files")} type="button">Files</button>
            <button className={detailTab === "settings" ? "active" : ""} onClick={() => setDetailTab("settings")} type="button">Settings</button>
          </div>
          <label className="reference-search-field">
            <Search size={18} strokeWidth={1.9} />
            <input
              onChange={event => setDetailFlowSearch(event.target.value)}
              placeholder="Search flows..."
              value={detailFlowSearch}
            />
          </label>
          <div className="reference-flow-detail-list">
            {detailFlowProjects.map(project => (
              <div className="reference-flow-detail-group" key={project.id}>
                <button className="reference-project-row" onClick={() => onSelectProject(project.id)} type="button">
                  <div className="reference-project-row-title">
                    <FolderOpen size={15} strokeWidth={1.9} />
                    <strong>{project.title}</strong>
                  </div>
                  <span>{project.count}</span>
                </button>
                {project.id === (activeProject?.id || selectedProjectId) ? (
                  <div className="reference-flow-detail-items">
                    {project.flows.map(flow => (
                      <button
                        className={cx("reference-flow-detail-item", flow.selected && "active")}
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
                  </div>
                ) : null}
              </div>
            ))}
          </div>
          <article className="reference-builder-side-card">
            <div className="reference-builder-section-head">
              <div>
                <strong>Flow Snapshot</strong>
                <span>Current status for the selected workstream</span>
              </div>
            </div>
            <div className="reference-builder-stat-grid compact">
              {builderHighlights.map(([label, value]) => (
                <article key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </article>
              ))}
            </div>
          </article>
        </div>

        <div className="reference-builder-detail-column middle">
          <div className="reference-builder-detail-title">
            <div>
              <h1>{selectedRow.name}</h1>
              <p>{selectedRow.lastRunMeta} · {selectedRow.runs} changes · {selectedRow.description}</p>
            </div>
          </div>
          <article className="reference-builder-timeline">
            <div className="reference-builder-section-head">
              <div>
                <strong>Timeline</strong>
                <span>
                  Key moments from this flow · {virtualTimeline.totalCount} item{virtualTimeline.totalCount === 1 ? "" : "s"}
                </span>
              </div>
            </div>
            <div
              className="reference-builder-moments virtualized"
              onScroll={virtualTimeline.onScroll}
              style={{ maxHeight: virtualTimeline.viewportHeight }}
            >
              {virtualTimeline.topPadding > 0 ? (
                <div aria-hidden="true" className="reference-builder-virtual-spacer" style={{ height: virtualTimeline.topPadding }} />
              ) : null}
              {virtualTimeline.items.map(item => (
                <article className={cx("reference-builder-moment", item.tone)} key={item.id}>
                  <div className="reference-builder-moment-time">
                    <span>{item.time}</span>
                  </div>
                  <div className="reference-builder-moment-body">
                    <strong>{item.title}</strong>
                    <p>{item.detail}</p>
                    {item.preview ? <div className="reference-builder-preview-chip">{item.preview}</div> : null}
                  </div>
                </article>
              ))}
              {virtualTimeline.bottomPadding > 0 ? (
                <div aria-hidden="true" className="reference-builder-virtual-spacer" style={{ height: virtualTimeline.bottomPadding }} />
              ) : null}
            </div>
          </article>
          <article className="reference-builder-summary-panel">
            <div className="reference-builder-section-head">
              <div>
                <strong>Change Ledger</strong>
                <span>Files, comments, and execution signals from this run</span>
              </div>
            </div>
            <div className="reference-builder-stat-grid">
              <article>
                <span>Files touched</span>
                <strong>{changedItems.length}</strong>
              </article>
              <article>
                <span>Feedback items</span>
                <strong>{feedbackItems.length}</strong>
              </article>
              <article>
                <span>Work engine</span>
                <strong>{activeProject?.title || projectLabel}</strong>
              </article>
            </div>
            <div className="reference-builder-change-list">
              {(changedItems.length ? changedItems : ["No file changes recorded for this flow yet."]).slice(0, 4).map(item => (
                <div className="reference-builder-change-row" key={item}>
                  <span className={cx("reference-flow-dot", changedItems.length ? "good" : "neutral")} />
                  <p>{item}</p>
                </div>
              ))}
            </div>
          </article>
        </div>

        <div className="reference-builder-detail-column right">
          <div className="reference-builder-detail-actions">
            <button className="reference-topbar-pill active" onClick={() => onRequestAction?.("builder:detail-live-preview", { missionId: selectedRow.id })} type="button">
              <Monitor size={16} strokeWidth={1.9} />
              <span>Live Preview</span>
            </button>
            <button
              className="reference-outline-button"
              onClick={() => onRequestAction?.("builder:open-in-builder", { missionId: selectedRow.id })}
              type="button"
            >
              <Hammer size={16} strokeWidth={1.9} />
              <span>Open in Builder</span>
            </button>
            <IconButton
              icon={MoreHorizontal}
              label="More"
              onClick={() => onRequestAction?.("builder:detail-more", { missionId: selectedRow.id })}
            />
          </div>
          <article className="reference-builder-preview-panel">
            <div className="reference-detail-tabs compact">
              <button className={detailPreviewTab === "preview" ? "active" : ""} onClick={() => setDetailPreviewTab("preview")} type="button">Preview</button>
              <button className={detailPreviewTab === "files" ? "active" : ""} onClick={() => setDetailPreviewTab("files")} type="button">Files</button>
              <button className={detailPreviewTab === "changes" ? "active" : ""} onClick={() => setDetailPreviewTab("changes")} type="button">Changes ({changedItems.length})</button>
            </div>
            <div className="reference-builder-preview-surface">
              <div className="reference-browser-brand">
                <div className="reference-brand-mark tiny">
                  <span />
                  <span />
                  <span />
                </div>
              <strong>{projectLabel}</strong>
            </div>
            <h2>{selectedRow.name}</h2>
              <p>{changedItems[0] || "No live preview changes have been recorded for this flow yet."}</p>
              <div className="reference-browser-actions">
                <button className="primary" onClick={() => onRequestAction?.("builder:detail-primary", { missionId: selectedRow.id })} type="button">Primary Action</button>
                <button className="secondary" onClick={() => onRequestAction?.("builder:detail-secondary", { missionId: selectedRow.id })} type="button">Secondary</button>
              </div>
            </div>
          </article>
          <article className="reference-feedback-panel builder">
            <div className="reference-feedback-tabs">
              <button className={detailFeedbackTab === "feedback" ? "active" : ""} onClick={() => setDetailFeedbackTab("feedback")} type="button">Feedback</button>
              <button className={detailFeedbackTab === "notes" ? "active" : ""} onClick={() => setDetailFeedbackTab("notes")} type="button">Notes</button>
            </div>
            <div className="reference-feedback-list">
              {feedbackItems
                .filter(item => (detailFeedbackTab === "feedback" ? item.role !== "note" : true))
                .slice(0, 3)
                .map(item => (
                <article className="reference-feedback-item" key={item.id}>
                  <div className="reference-feedback-meta">
                    <strong>{item.author}</strong>
                    <span>{item.meta}</span>
                  </div>
                  <p>{item.body}</p>
                  {item.role === "assistant" ? (
                    <div className="reference-feedback-actions">
                      <button onClick={() => onRequestAction?.("builder:feedback-apply", { feedbackId: item.id, missionId: selectedRow.id })} type="button">Change applied</button>
                      <button onClick={() => onRequestAction?.("builder:feedback-view", { feedbackId: item.id, missionId: selectedRow.id })} type="button">View change</button>
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
            <div className="reference-feedback-composer">
              <span>Add feedback or ask the agent...</span>
              <ArrowUp size={16} strokeWidth={2} />
            </div>
          </article>
        </div>
      </section>
    );
  }

  return (
    <section className="reference-builder-surface">
      <div className="reference-builder-head">
        <div>
          <h1>Builder</h1>
          <p>Build, run, and iterate on all your vibe coding projects.</p>
        </div>
        <div className="reference-builder-head-actions">
          <button
            className="reference-outline-button strong"
            onClick={() => onRequestAction?.("builder:new-project")}
            type="button"
          >
            <Plus size={18} strokeWidth={1.9} />
            <span>New Project</span>
          </button>
          <IconButton
            icon={LayoutGrid}
            label="Grid view"
            onClick={() => onRequestAction?.("builder:toggle-view")}
          />
        </div>
      </div>

      <div className="reference-builder-metrics-row">
        {builderMetrics.map(item => (
          <BuilderMetricCard item={item} key={item.id} />
        ))}
      </div>

      <div className="reference-builder-rule-strip">
        <div>
          <span>Rule Sets</span>
          <strong>
            {ruleSets.find(item => item.id === activeRuleSetId)?.name ||
              ruleSets[0]?.name ||
              "No rule set selected"}
          </strong>
          <p>
            {ruleSets.find(item => item.id === activeRuleSetId)?.description ||
              "Configure routing, approvals, autonomy, and execution targets before a builder run starts."}
          </p>
        </div>
        <div className="reference-inline-actions">
          {ruleSets.slice(0, 3).map(item => (
            <StatusBadge
              key={`builder-rule-${item.id}`}
              label={item.name}
              tone={item.id === activeRuleSetId ? "completed" : "paused"}
            />
          ))}
          <button className="reference-outline-button strong" onClick={onOpenSkillStudio} type="button">
            Edit rule sets
          </button>
        </div>
      </div>

      <div className="reference-builder-table-shell">
        <div className="reference-builder-toolbar">
          <label className="reference-search-field">
            <Search size={18} strokeWidth={1.9} />
            <input
              onChange={event => {
                setBuilderSearch(event.target.value);
                setBuilderPage(1);
              }}
              placeholder="Search projects..."
              value={builderSearch}
            />
          </label>
          <button className="reference-select-button" onClick={() => onRequestAction?.("builder:filter-status")} type="button">
            <span>Status</span>
            <ChevronDown size={16} strokeWidth={1.9} />
          </button>
          <button className="reference-select-button" onClick={() => onRequestAction?.("builder:filter-stack")} type="button">
            <span>Tech Stack</span>
            <ChevronDown size={16} strokeWidth={1.9} />
          </button>
          <button className="reference-select-button" onClick={() => onRequestAction?.("builder:filter-updated")} type="button">
            <span>Last Updated</span>
            <ChevronDown size={16} strokeWidth={1.9} />
          </button>
          <button className="reference-select-button compact" onClick={() => onRequestAction?.("builder:filters")} type="button">
            <Filter size={17} strokeWidth={1.9} />
            <span>Filters</span>
          </button>
          <IconButton
            icon={Settings}
            label="Builder settings"
            onClick={() => onRequestAction?.("builder:settings")}
          />
        </div>

        <div className="reference-builder-table">
          <div className="reference-builder-table-head">
            <span>Project</span>
            <span>Status</span>
            <span>Last Run</span>
            <span>Turning Point</span>
            <span>Success Rate</span>
            <span>Runs</span>
            <span>Updated</span>
            <span />
          </div>

          {pagedBuilderRows.map(row => {
            const successRate =
              typeof row.successRate === "number" && Number.isFinite(row.successRate)
                ? Math.max(0, Math.min(100, row.successRate))
                : null;
            return (
              <article
                className={cx("reference-builder-row action", row.selected && "selected")}
                key={row.id}
                onClick={() => onOpenBuilderDetail(row.id)}
                onKeyDown={event => openBuilderDetailFromKey(event, row.id)}
                role="button"
                tabIndex={0}
              >
                <div className="reference-project-cell">
                  <div className="reference-project-icon">
                    <Code2 size={18} strokeWidth={1.9} />
                  </div>
                  <div>
                    <strong>{row.name}</strong>
                    <p>{row.description}</p>
                  </div>
                </div>
                <div>
                  <StatusBadge label={row.status} tone={row.statusTone} />
                </div>
                <div className="reference-table-dual">
                  <strong>{row.lastRun}</strong>
                  <span>{row.lastRunMeta}</span>
                </div>
                <div className="reference-table-dual">
                  <strong>{row.turningPoint}</strong>
                  <span className={cx("reference-turning-delta", row.turningPointTone)}>{row.turningPointDelta}</span>
                </div>
                <div className="reference-success-cell">
                  <strong>{successRate === null ? "—" : `${successRate}%`}</strong>
                  <div className="reference-success-track">
                    <span style={{ width: `${successRate ?? 0}%` }} />
                  </div>
                </div>
                <strong>{row.runs}</strong>
                <span className="reference-updated">{row.updated}</span>
                <IconButton
                  icon={MoreHorizontal}
                  label="Project actions"
                  onClick={event => {
                    event.stopPropagation();
                    onRequestAction?.("builder:project-actions", { missionId: row.id });
                  }}
                />
              </article>
            );
          })}
          {!filteredBuilderRows.length ? (
            <div className="reference-builder-empty-state">
              <strong>{builderRows.length ? "No matches found" : "No builder runs yet"}</strong>
              <p>
                {builderRows.length
                  ? "Try a different project search term."
                  : "Start a mission from Agent or create a workspace run; Builder will populate from real mission activity."}
              </p>
            </div>
          ) : null}
        </div>

        <div className="reference-builder-pagination">
          <span>
            {filteredBuilderRows.length > 0
              ? `Showing ${pageStart + 1} to ${Math.min(pageStart + pageSize, filteredBuilderRows.length)} of ${filteredBuilderRows.length} projects`
              : "No projects to show yet"}
          </span>
          {filteredBuilderRows.length > 0 ? (
            <div className="reference-page-buttons">
              <button disabled={effectiveBuilderPage <= 1} onClick={() => setBuilderPage(page => Math.max(1, page - 1))} type="button">‹</button>
              {Array.from({ length: totalPages }, (_, index) => index + 1).slice(0, 6).map(page => (
                <button
                  className={page === effectiveBuilderPage ? "active" : ""}
                  key={`builder-page-${page}`}
                  onClick={() => setBuilderPage(page)}
                  type="button"
                >
                  {page}
                </button>
              ))}
              <button disabled={effectiveBuilderPage >= totalPages} onClick={() => setBuilderPage(page => Math.min(totalPages, page + 1))} type="button">›</button>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function SkillHubSurface({ onRequestAction, studioState }) {
  const {
    activeRuleSetId,
    activeSkillIds = [],
    collectionTab = "skill",
    onApplyProposal,
    onAssistantFieldChange,
    onAssistantSubmit,
    onFieldChange,
    onInsertDraft,
    onListChange,
    onPublish,
    onRouteFieldChange,
    onSaveDraft,
    onSelectItem,
    ruleSets = [],
    selectedItem,
    skills = [],
    totals = { totalSkills: 0, activeSkills: 0, totalRuleSets: 0, activeRuleSets: 0, environments: 0, knowledgeBases: 0 },
  } = studioState;
  const assistant = selectedItem?.assistant || {};
  const proposal = assistant.proposal || null;
  const isRule = selectedItem?.kind === "rule";
  const historyRows = asList(assistant.conversation);
  const overridesValue = asList(selectedItem?.overrides)
    .map(item => `${item.target} :: ${item.mode} :: ${item.detail}`)
    .join("\n");
  const [skillSearch, setSkillSearch] = useState("");
  const searchTerm = String(skillSearch || "").trim().toLowerCase();
  const visibleSkills =
    searchTerm.length === 0
      ? skills
      : skills.filter(item =>
          [item.name, item.summary, item.description]
            .map(value => String(value || "").toLowerCase())
            .some(value => value.includes(searchTerm)),
        );
  const visibleRuleSets =
    searchTerm.length === 0
      ? ruleSets
      : ruleSets.filter(item =>
          [item.name, item.summary, item.description]
            .map(value => String(value || "").toLowerCase())
            .some(value => value.includes(searchTerm)),
        );

  return (
    <section className="reference-skill-surface detail-mode">
      <div className="reference-skill-toolbar">
        <div>
          <p className="reference-breadcrumb">
            Skills Hub / <strong>{selectedItem?.name || "Skill Studio"}</strong>
          </p>
          <div className="reference-inline-badges">
            <h1>{selectedItem?.name || "Skills Hub"}</h1>
            {selectedItem?.badge ? <span className="reference-surface-badge">{selectedItem.badge}</span> : null}
          </div>
        </div>
        <div className="reference-builder-head-actions">
          <button className="reference-outline-button" onClick={() => onRequestAction?.("skills:version-history")} type="button">
            <History size={16} strokeWidth={1.9} />
            <span>Version History</span>
          </button>
          <button className="reference-outline-button" onClick={() => onRequestAction?.("skills:propose-from-mission")} type="button">
            <Sparkles size={16} strokeWidth={1.9} />
            <span>Propose from mission</span>
          </button>
          <button className="reference-outline-button" onClick={onSaveDraft} type="button">
            <FileText size={16} strokeWidth={1.9} />
            <span>Save Draft</span>
          </button>
          <button className="reference-black-button" onClick={onPublish} type="button">
            Publish
          </button>
          <IconButton icon={MoreHorizontal} label="More actions" onClick={() => onRequestAction?.("skills:more-actions")} />
        </div>
      </div>

      <div className="reference-skill-detail-grid">
        <article className="reference-skill-panel reference-studio-sidebar">
          <SectionPillTabs
            onChange={value => onSelectItem(value, value === "rule" ? ruleSets[0]?.id : skills[0]?.id)}
            tabs={[
              { value: "skill", label: "Skill" },
              { value: "rule", label: "Rule Set" },
            ]}
            value={collectionTab}
          />

          <label className="reference-search-field">
            <Search size={18} strokeWidth={1.9} />
            <input
              onChange={event => setSkillSearch(event.target.value)}
              placeholder="Search skills & rule sets..."
              value={skillSearch}
            />
          </label>

          <div className="reference-studio-list-section">
            <div className="reference-builder-section-head">
              <strong>Skills</strong>
              <button aria-label="Add skill" className="reference-mini-icon" onClick={() => onRequestAction?.("skills:add-skill")} type="button">
                <Plus size={14} strokeWidth={2} />
              </button>
            </div>
            <div className="reference-skill-list">
              {visibleSkills.map(item => (
                <button
                  className={cx("reference-skill-row", selectedItem?.id === item.id && "active")}
                  key={item.id}
                  onClick={() => onSelectItem("skill", item.id)}
                  type="button"
                >
                  <div>
                    <strong>{item.name}</strong>
                    <p>{item.summary}</p>
                  </div>
                  <div className="reference-list-item-meta">
                    {activeSkillIds.includes(item.id) ? <span className="reference-flow-dot good" /> : null}
                    <StatusBadge
                      label={item.status}
                      tone={item.status === "Draft" ? "paused" : "completed"}
                    />
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="reference-studio-list-section">
            <div className="reference-builder-section-head">
              <strong>Rule Sets</strong>
              <button aria-label="Add rule set" className="reference-mini-icon" onClick={() => onRequestAction?.("skills:add-rule-set")} type="button">
                <Plus size={14} strokeWidth={2} />
              </button>
            </div>
            <div className="reference-skill-list">
              {visibleRuleSets.map(item => (
                <button
                  className={cx("reference-skill-row", selectedItem?.id === item.id && "active")}
                  key={item.id}
                  onClick={() => onSelectItem("rule", item.id)}
                  type="button"
                >
                  <div>
                    <strong>{item.name}</strong>
                    <p>{item.summary}</p>
                  </div>
                  <div className="reference-list-item-meta">
                    {activeRuleSetId === item.id ? <span className="reference-flow-dot good" /> : null}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <button className="reference-studio-archive" onClick={() => onRequestAction?.("skills:view-archived")} type="button">
            <BookOpen size={16} strokeWidth={1.9} />
            <span>View archived</span>
          </button>
        </article>

        <article className="reference-skill-panel reference-studio-editor">
          {selectedItem ? (
            <>
              <div className="reference-builder-section-head">
                <strong>{selectedItem.badge}</strong>
                <div className="reference-inline-actions">
                  <button className="reference-link-button" onClick={() => onRequestAction?.("skills:edit-item", { itemId: selectedItem.id })} type="button">Edit</button>
                  <button className="reference-link-button" onClick={() => onRequestAction?.("skills:preview-item", { itemId: selectedItem.id })} type="button">Preview</button>
                </div>
              </div>

              <SurfaceField label="Name">
                <input onChange={event => onFieldChange("name", event.target.value)} value={selectedItem.name} />
              </SurfaceField>

              <SurfaceField label="Description">
                <textarea
                  onChange={event => onFieldChange("description", event.target.value)}
                  rows={3}
                  value={selectedItem.description}
                />
              </SurfaceField>
              {selectedItem.kind === "skill" ? (
                <div className="reference-studio-lifecycle">
                  <div className="reference-inline-badges">
                    <StatusBadge label={`Validation: ${selectedItem.validationStatus || "Pending"}`} tone={(selectedItem.validationStatus || "").includes("Pass") ? "completed" : "running"} />
                    <StatusBadge label={`Tests: ${selectedItem.testStatus || "Not run"}`} tone={(selectedItem.testStatus || "").includes("Pass") ? "completed" : "running"} />
                    <StatusBadge label={`Publish: ${selectedItem.publishReadiness || "Needs review"}`} tone={(selectedItem.publishReadiness || "").includes("Ready") ? "completed" : "paused"} />
                  </div>
                  <p>{selectedItem.lastValidationSummary || "Validation summary unavailable."}</p>
                  <p>{selectedItem.lastTestSummary || "Test summary unavailable."}</p>
                  <div className="reference-inline-actions">
                    <button className="reference-outline-button" onClick={() => onRequestAction?.("skills:validate-item")} type="button">Validate</button>
                    <button className="reference-outline-button" onClick={() => onRequestAction?.("skills:test-item")} type="button">Run tests</button>
                    <button className="reference-outline-button" onClick={() => onRequestAction?.("skills:promote-learned")} type="button">Promote learned</button>
                  </div>
                  {selectedItem.reviewRequired ? <p>Human review required before publish.</p> : <p>Ready for publish review.</p>}
                </div>
              ) : null}
            </>
          ) : null}
        </article>

        <article className="reference-skill-panel reference-studio-assistant">
          <div className="reference-builder-section-head">
            <strong>Ask a model</strong>
            <button className="reference-link-button" onClick={() => onRequestAction?.("skills:collapse-assistant")} type="button">Collapse</button>
          </div>
          <div className="reference-inline-form-row">
            <SurfaceField label="Model">
              <select
                onChange={event => onAssistantFieldChange("model", event.target.value)}
                value={assistant.model || "gpt-5.5"}
              >
                <option value="gpt-5.5">gpt-5.5</option>
                <option value="GPT-4o">GPT-4o</option>
                <option value="gpt-5.4-mini">gpt-5.4-mini</option>
                <option value="gpt-5.4">gpt-5.4</option>
                <option value="claude-sonnet-4.5">claude-sonnet-4.5</option>
              </select>
            </SurfaceField>
            <SurfaceField label="Effort">
              <select
                onChange={event => onAssistantFieldChange("effort", event.target.value)}
                value={assistant.effort || "Balanced"}
              >
                <option value="Low">Low</option>
                <option value="Balanced">Balanced</option>
                <option value="High">High</option>
              </select>
            </SurfaceField>
          </div>

          <div className="reference-studio-chat">
            {historyRows.length > 0 ? (
              historyRows.map((row, index) => (
                <article className="reference-studio-chat-row" key={`${row.role}-${index}`}>
                  <div className="reference-feedback-meta">
                    <strong>{row.author}</strong>
                    <span>{row.meta}</span>
                  </div>
                  <p>{row.body}</p>
                </article>
              ))
            ) : (
              <article className="reference-studio-chat-row empty">
                <p>Use this panel to refine the selected skill or rule set and apply the proposal directly.</p>
              </article>
            )}
          </div>

          {proposal ? (
            <div className="reference-studio-proposal">
              <div className="reference-builder-section-head">
                <strong>{isRule ? "Proposed changes" : "Guardrails (changes)"}</strong>
                <StatusBadge label="Added" tone="completed" />
              </div>
              <pre>{proposal.changes.map(line => `+ ${line}`).join("\n")}</pre>
              <div className="reference-inline-actions stretch">
                <button className="reference-black-button" onClick={onApplyProposal} type="button">
                  Apply changes
                </button>
                <button className="reference-outline-button" onClick={onInsertDraft} type="button">
                  Insert as draft
                </button>
              </div>
            </div>
          ) : null}

          <div className="reference-studio-compose">
            <textarea
              onChange={event => onAssistantFieldChange("prompt", event.target.value)}
              placeholder={isRule ? "Ask the model to refine this rule set..." : "Ask the model to refine this skill..."}
              rows={4}
              value={assistant.prompt || ""}
            />
            <div className="reference-composer-footer compact">
              <button className="reference-tool-button" onClick={() => onRequestAction?.("skills:attach-context")} type="button">
                <Paperclip size={18} strokeWidth={1.9} />
              </button>
              <button className="reference-send-button solid" onClick={onAssistantSubmit} type="button">
                <ArrowUp size={16} strokeWidth={2} />
              </button>
            </div>
          </div>
        </article>
      </div>

      {selectedItem ? (
        <div className="reference-skill-detail-lower">
          {isRule ? (
            <>
              <div className="reference-two-column-grid">
                <SurfaceField label="Scope / Applies to">
                  <input onChange={event => onFieldChange("scope", event.target.value)} value={selectedItem.scope} />
                </SurfaceField>
                <SurfaceField label="Autonomy mode">
                  <input
                    onChange={event => onFieldChange("autonomyMode", event.target.value)}
                    value={selectedItem.autonomyMode}
                  />
                </SurfaceField>
                <SurfaceField label="Approval mode">
                  <input
                    onChange={event => onFieldChange("approvalMode", event.target.value)}
                    value={selectedItem.approvalMode}
                  />
                </SurfaceField>
                <SurfaceField label="Default reviewer">
                  <input onChange={event => onFieldChange("reviewer", event.target.value)} value={selectedItem.reviewer} />
                </SurfaceField>
              </div>

              <div className="reference-rule-matrix">
                <article>
                  <strong>Allowed actions</strong>
                  <textarea
                    onChange={event => onListChange("allowedActions", event.target.value)}
                    rows={4}
                    value={joinEditorLines(selectedItem.allowedActions)}
                  />
                </article>
                <article>
                  <strong>Requires approval</strong>
                  <textarea
                    onChange={event => onListChange("requiresApproval", event.target.value)}
                    rows={4}
                    value={joinEditorLines(selectedItem.requiresApproval)}
                  />
                </article>
                <article>
                  <strong>Restricted actions</strong>
                  <textarea
                    onChange={event => onListChange("restrictedActions", event.target.value)}
                    rows={4}
                    value={joinEditorLines(selectedItem.restrictedActions)}
                  />
                </article>
                <article>
                  <strong>Special cases</strong>
                  <textarea
                    onChange={event => onListChange("specialCases", event.target.value)}
                    rows={4}
                    value={joinEditorLines(selectedItem.specialCases)}
                  />
                </article>
              </div>

              <div className="reference-route-plan-grid">
                {Object.entries(selectedItem.routePlan || {}).map(([role, route]) => (
                  <article className="reference-route-plan-card" key={role}>
                    <strong>{role[0].toUpperCase() + role.slice(1)}</strong>
                    <div className="reference-inline-form-row">
                      <select
                        onChange={event => onRouteFieldChange(role, "provider", event.target.value)}
                        value={route.provider}
                      >
                        <option value="openai">OpenAI</option>
                        <option value="anthropic">Anthropic</option>
                        <option value="minimax">MiniMax</option>
                        <option value="openrouter">OpenRouter</option>
                      </select>
                      <select
                        onChange={event => onRouteFieldChange(role, "effort", event.target.value)}
                        value={route.effort}
                      >
                        <option value="low">Low</option>
                        <option value="medium">Balanced</option>
                        <option value="high">High</option>
                      </select>
                    </div>
                    <input
                      onChange={event => onRouteFieldChange(role, "model", event.target.value)}
                      value={route.model}
                    />
                  </article>
                ))}
              </div>

              <SurfaceField label="Folder or environment-specific overrides">
                <textarea
                  onChange={event =>
                    onFieldChange(
                      "overrides",
                      event.target.value
                        .split("\n")
                        .map(line => line.trim())
                        .filter(Boolean)
                        .map(line => {
                          const [target, mode, detail] = line.split("::").map(part => part.trim());
                          return { target: target || "", mode: mode || "", detail: detail || "" };
                        }),
                    )
                  }
                  rows={5}
                  value={overridesValue}
                />
              </SurfaceField>
            </>
          ) : (
            <>
              <SurfaceField label="Trigger conditions">
                <textarea
                  onChange={event => onFieldChange("triggerConditions", event.target.value)}
                  rows={3}
                  value={selectedItem.triggerConditions}
                />
              </SurfaceField>
              <SurfaceField label="Instructions">
                <textarea
                  onChange={event => onListChange("instructions", event.target.value)}
                  rows={7}
                  value={joinEditorLines(selectedItem.instructions)}
                />
              </SurfaceField>
              <SurfaceField label="Output style">
                <textarea
                  onChange={event => onListChange("outputStyle", event.target.value)}
                  rows={4}
                  value={joinEditorLines(selectedItem.outputStyle)}
                />
              </SurfaceField>
              <SurfaceField label="Guardrails">
                <textarea
                  onChange={event => onListChange("guardrails", event.target.value)}
                  rows={6}
                  value={joinEditorLines(selectedItem.guardrails)}
                />
              </SurfaceField>
            </>
          )}
        </div>
      ) : null}

      <div className="reference-skill-overview compact">
        <article><Code2 size={20} strokeWidth={1.9} /><strong>{totals.totalSkills}</strong><span>Total Skills</span><p>{totals.activeSkills} active</p></article>
        <article><FileText size={20} strokeWidth={1.9} /><strong>{totals.totalRuleSets}</strong><span>Rule Sets</span><p>{totals.activeRuleSets} active</p></article>
        <article><Database size={20} strokeWidth={1.9} /><strong>{totals.environments}</strong><span>Environments</span><p>4 active</p></article>
        <article><BookOpen size={20} strokeWidth={1.9} /><strong>{totals.knowledgeBases}</strong><span>Knowledge Bases</span><p>3 synced</p></article>
      </div>
    </section>
  );
}

function RuleSetsSurface({ onRequestAction, studioState }) {
  const {
    activeRuleSetId,
    onSelectItem,
    ruleSets = [],
    selectedItem,
    totals = { totalRuleSets: 0, activeRuleSets: 0 },
  } = studioState || {};
  const selectedRule =
    ruleSets.find(item => item.id === activeRuleSetId) ||
    (selectedItem?.kind === "rule" ? selectedItem : null) ||
    ruleSets[0] ||
    null;

  return (
    <section className="reference-skill-surface detail-mode">
      <div className="reference-skill-toolbar">
        <div>
          <p className="reference-breadcrumb">
            Workspace / <strong>Rule Sets</strong>
          </p>
          <div className="reference-inline-badges">
            <h1>Rule Sets</h1>
            <span className="reference-surface-badge">Core policy</span>
          </div>
        </div>
        <div className="reference-builder-head-actions">
          <button className="reference-outline-button" onClick={() => onRequestAction?.("rule-sets:audit")} type="button">
            <Shield size={16} strokeWidth={1.9} />
            <span>Audit permissions</span>
          </button>
          <button className="reference-outline-button" onClick={() => onRequestAction?.("skills:add-rule-set")} type="button">
            <Plus size={16} strokeWidth={1.9} />
            <span>New rule set</span>
          </button>
        </div>
      </div>

      <div className="reference-skill-detail-grid rule-set-overview-grid">
        <article className="reference-skill-panel reference-studio-sidebar">
          <div className="reference-builder-section-head">
            <strong>Permission modes</strong>
            <StatusBadge label={`${totals.activeRuleSets || 0} active`} tone="completed" />
          </div>
          <div className="reference-skill-list">
            {ruleSets.map(item => (
              <button
                className={cx("reference-skill-row", selectedRule?.id === item.id && "active")}
                key={item.id}
                onClick={() => onSelectItem?.("rule", item.id)}
                type="button"
              >
                <div>
                  <strong>{item.name}</strong>
                  <p>{item.summary}</p>
                </div>
                <div className="reference-list-item-meta">
                  {activeRuleSetId === item.id ? <span className="reference-flow-dot good" /> : null}
                  <StatusBadge label={item.approvalMode || "Policy"} tone={activeRuleSetId === item.id ? "completed" : "paused"} />
                </div>
              </button>
            ))}
          </div>
        </article>

        <article className="reference-skill-panel reference-studio-editor">
          <div className="reference-builder-section-head">
            <strong>{selectedRule?.name || "No rule set selected"}</strong>
            <div className="reference-inline-actions">
              <button className="reference-link-button" onClick={() => onRequestAction?.("rule-sets:duplicate", { ruleSetId: selectedRule?.id })} type="button">Duplicate</button>
              <button className="reference-link-button" onClick={() => onRequestAction?.("rule-sets:edit", { ruleSetId: selectedRule?.id })} type="button">Edit</button>
            </div>
          </div>
          {selectedRule ? (
            <>
              <div className="reference-two-column-grid">
                <SurfaceField label="Applies to">
                  <input readOnly value={selectedRule.scope || "Workspace"} />
                </SurfaceField>
                <SurfaceField label="Autonomy">
                  <input readOnly value={selectedRule.autonomyMode || "Not configured"} />
                </SurfaceField>
                <SurfaceField label="Approval mode">
                  <input readOnly value={selectedRule.approvalMode || "Not configured"} />
                </SurfaceField>
                <SurfaceField label="Reviewer">
                  <input readOnly value={selectedRule.reviewer || "Operator"} />
                </SurfaceField>
              </div>

              <div className="reference-rule-matrix">
                <article>
                  <strong>Allowed</strong>
                  <ul>{asList(selectedRule.allowedActions).map(item => <li key={item}>{item}</li>)}</ul>
                </article>
                <article>
                  <strong>Approval required</strong>
                  <ul>{asList(selectedRule.requiresApproval).map(item => <li key={item}>{item}</li>)}</ul>
                </article>
                <article>
                  <strong>Restricted</strong>
                  <ul>{asList(selectedRule.restrictedActions).map(item => <li key={item}>{item}</li>)}</ul>
                </article>
                <article>
                  <strong>Special cases</strong>
                  <ul>{asList(selectedRule.specialCases).map(item => <li key={item}>{item}</li>)}</ul>
                </article>
              </div>
            </>
          ) : (
            <p>No rule sets are available for this workspace.</p>
          )}
        </article>

        <article className="reference-skill-panel reference-studio-assistant">
          <div className="reference-builder-section-head">
            <strong>Runtime guardrails</strong>
            <StatusBadge label="Visible" tone="completed" />
          </div>
          <div className="reference-skill-overview compact nested">
            <article><Shield size={20} strokeWidth={1.9} /><strong>{totals.totalRuleSets || ruleSets.length}</strong><span>Total</span><p>Rule sets</p></article>
            <article><CircleCheckBig size={20} strokeWidth={1.9} /><strong>{totals.activeRuleSets || 0}</strong><span>Active</span><p>Applied now</p></article>
            <article><SquareTerminal size={20} strokeWidth={1.9} /><strong>{asList(selectedRule?.requiresApproval).length}</strong><span>Approval gates</span><p>Commands and writes</p></article>
          </div>
          <p>
            Rule Sets control how much autonomy the agent has before it reads files,
            writes files, runs commands, uses tools, changes branches, or reaches outside
            the selected workspace.
          </p>
          <button className="reference-black-button" onClick={() => onRequestAction?.("rule-sets:apply-active", { ruleSetId: selectedRule?.id })} type="button">
            Apply to current run
          </button>
        </article>
      </div>
    </section>
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
    ["providers", "Models", Sparkles],
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
                  <strong>Linux and setup</strong>
                  <span>Syntelos checks these for you and shows install or update buttons when something is missing.</span>
                </div>
              </div>
              <div className="reference-settings-summary-grid">
                {asList(setupServices)
                  .filter(item => ["wsl2", "uv", "opencv", "openclaw", "hermes"].includes(item.serviceId))
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
                      <p>No direct action is exposed yet.</p>
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

function LegacyFluxioReferenceShell(props) {
  const {
    agentScene,
    activeCommentTarget,
    appearance,
    appearanceStyle,
    builderDetailOpen,
    builderRows,
    changedItems,
    currentProjectLabel,
    draft,
    favoriteFlows,
    feedbackItems,
    flowProjects,
    generatedImageArtifacts,
    hermesEvidenceItems,
    messages,
    nasDeployChecks,
    conversationMode = "chat",
    onAttach,
    onBackFromBuilder,
    onChangeDraft,
    onDictation,
    onHistory,
    onIdleSubmit,
    onInsertSlashCommand,
    onMore,
    onOpenBuilderDetail,
    onOpenSettings,
    onOpenSkillStudio,
    onPaste,
    onRequestAction,
    onRuntimeChange,
    onSend,
    onSelectFlow,
    onSelectProject,
    onSetAgentScene,
    onSetAppearance,
    onSetSurface,
    callBackend,
    runtimeOptions,
    runtimeStatus,
    runtimeCompartment,
    routeControls,
    settingsState,
    selectedEffortLabel,
    selectedModelLabel,
    selectedHarnessMeta,
    selectedProjectId,
    selectedRuntime,
    slashCommands,
    sidebarBehavior = "auto",
    skillStudioState,
    surface,
    timelineMoments,
    missionLoop,
    workbenchState,
  } = props;
  const runtimeLabel =
    runtimeOptions.find(option => option.value === selectedRuntime)?.label || selectedRuntime;
  const showFlowSidebar = surface === "agent";
  const showAgentTopbar = surface === "agent";
  const topbarRoute = routeControls?.selectedRoute || {};
  const topbarWorkspacePath = String(runtimeCompartment?.cwd || "").replace(/\\/g, "/");
  const topbarWorkspaceLabel = topbarWorkspacePath
    ? topbarWorkspacePath.split("/").filter(Boolean).slice(-2).join("/")
    : "workspace";
  const topbarHost = runtimeCompartment?.host || "local";
  const topbarOnline = Boolean(runtimeCompartment);

  const mainContent =
    surface === "home" ? (
      <HomeSurface onOpenSurface={onSetSurface} onRequestAction={onRequestAction} />
    ) : surface === "skills" ? (
      <SkillHubSurface onRequestAction={onRequestAction} studioState={skillStudioState} />
    ) : surface === "rule-sets" ? (
      <RuleSetsSurface onRequestAction={onRequestAction} studioState={skillStudioState} />
    ) : surface === "images" ? (
      <Suspense fallback={
        <article className="fluxos-flow-empty">
          <span>Images</span>
          <strong>Loading image studio</strong>
          <p>The mission-control shell is already interactive while the image playground bundle loads.</p>
        </article>
      }>
        <ImagePlaygroundSurface callBackend={callBackend} />
      </Suspense>
    ) : surface === "workbench" ? (
      <WorkbenchSurface
        key={workbenchState?.missionId || currentProjectLabel || "workbench"}
        onRequestAction={onRequestAction}
        onSetSurface={onSetSurface}
        workbenchState={workbenchState}
      />
    ) : surface === "settings" ? (
      <SettingsSurface onRequestAction={onRequestAction} settingsState={settingsState} />
    ) : surface === "agent" && agentScene === "idle" ? (
      <AgentIdleSurface
        draft={draft}
        onAttach={onAttach}
        onChangeDraft={onChangeDraft}
        onDictation={onDictation}
        onIdleSubmit={onIdleSubmit}
        onRequestAction={onRequestAction}
        onPaste={onPaste}
        onRuntimeChange={onRuntimeChange}
        onUseSlashCommand={onInsertSlashCommand}
        runtimeOptions={runtimeOptions}
        runtimeStatus={runtimeStatus}
        routeControls={routeControls}
        selectedEffortLabel={selectedEffortLabel}
        selectedHarnessMeta={selectedHarnessMeta}
        selectedModelLabel={selectedModelLabel}
        selectedRuntime={selectedRuntime}
        slashCommands={slashCommands}
      />
    ) : surface === "agent" && agentScene === "run" ? (
      <AgentRunningSurface
        key={workbenchState?.missionId || currentProjectLabel || "agent-run"}
        draft={draft}
        activeCommentTarget={activeCommentTarget}
        conversationMode={conversationMode}
        feedbackItems={feedbackItems}
        generatedImageArtifacts={generatedImageArtifacts}
        hermesEvidenceItems={hermesEvidenceItems}
        missionLoop={missionLoop}
        messages={messages}
        nasDeployChecks={nasDeployChecks}
        onAttach={onAttach}
        onChangeDraft={onChangeDraft}
        onDictation={onDictation}
        onPaste={onPaste}
        onRequestAction={onRequestAction}
        onRuntimeChange={onRuntimeChange}
        onSend={onSend}
        onUseSlashCommand={onInsertSlashCommand}
        runtimeCompartment={runtimeCompartment}
        routeControls={routeControls}
        runtimeOptions={runtimeOptions}
        selectedEffortLabel={selectedEffortLabel}
        selectedModelLabel={selectedModelLabel}
        selectedRuntime={selectedRuntime}
        selectedRuntimeLabel={runtimeLabel}
        slashCommands={slashCommands}
        timelineMoments={timelineMoments}
        workbenchState={workbenchState}
      />
    ) : surface === "agent" && agentScene === "live" ? (
      <LivePreviewSurface
        key={workbenchState?.missionId || currentProjectLabel || "agent-live"}
        changedItems={changedItems}
        draft={draft}
        feedbackItems={feedbackItems}
        generatedImageArtifacts={generatedImageArtifacts}
        hermesEvidenceItems={hermesEvidenceItems}
        messages={messages}
        nasDeployChecks={nasDeployChecks}
        onAttach={onAttach}
        onChangeDraft={onChangeDraft}
        onDictation={onDictation}
        onPaste={onPaste}
        onRequestAction={onRequestAction}
        onSend={onSend}
        onUseSlashCommand={onInsertSlashCommand}
        projectLabel={currentProjectLabel}
        runtimeCompartment={runtimeCompartment}
        slashCommands={slashCommands}
        timelineMoments={timelineMoments}
      />
    ) : surface === "builder" ? (
      <BuilderSurface
        builderDetailOpen={builderDetailOpen}
        builderRows={builderRows}
        changedItems={changedItems}
        feedbackItems={feedbackItems}
        flowProjects={flowProjects}
        onBackFromBuilder={onBackFromBuilder}
        onOpenBuilderDetail={onOpenBuilderDetail}
        onRequestAction={onRequestAction}
        onOpenSkillStudio={onOpenSkillStudio}
        onSelectFlow={onSelectFlow}
        onSelectProject={onSelectProject}
        projectLabel={currentProjectLabel}
        activeRuleSetId={skillStudioState?.activeRuleSetId}
        ruleSets={skillStudioState?.ruleSets}
        selectedProjectId={selectedProjectId}
        timelineMoments={timelineMoments}
      />
    ) : null;

  return (
    <div
      className={cx("reference-shell", `surface-${surface}`)}
      data-agent-scene={surface === "agent" ? agentScene : undefined}
      data-detail-mode={showFlowSidebar || builderDetailOpen ? "true" : "false"}
      data-density={appearance?.density || "comfortable"}
      data-info-mode={appearance?.detailLevel || "balanced"}
      data-look={appearance?.stylePreset || "graphite-gold"}
      data-sidebar-behavior={sidebarBehavior}
      style={appearanceStyle}
    >
      <aside className="reference-sidebar">
        <div className="reference-sidebar-main">
          <RailBrand />

          <nav className="reference-sidebar-nav">
            {surface === "home" ? (
              <RailItem active icon={Home} label="Home" onClick={() => onSetSurface("home")} tone="home" />
            ) : (
              <RailItem active={surface === "home"} icon={Home} label="Home" onClick={() => onSetSurface("home")} />
            )}

            <div className="reference-sidebar-group">
              <span>Workspace</span>
              <RailItem
                active={surface === "agent"}
                icon={Bot}
                label="Agent"
                onClick={() => onSetSurface("agent")}
              />
              <RailItem
                active={surface === "builder"}
                icon={Hammer}
                label="Builder"
                onClick={() => onSetSurface("builder")}
                tone={surface === "builder" ? "gold" : "neutral"}
              />
              <RailItem
                active={surface === "skills"}
                icon={Grid2x2}
                label="Skills"
                onClick={onOpenSkillStudio}
              />
              <RailItem
                active={surface === "rule-sets"}
                icon={Shield}
                label="Rule Sets"
                onClick={() => onSetSurface("rule-sets")}
                tone={surface === "rule-sets" ? "gold" : "neutral"}
              />
              <RailItem
                active={surface === "images"}
                icon={Palette}
                label="Images"
                onClick={() => onSetSurface("images")}
                tone={surface === "images" ? "gold" : "neutral"}
              />
              <RailItem
                active={surface === "workbench"}
                icon={Laptop}
                label="Workbench"
                onClick={() => onSetSurface("workbench")}
              />
              <RailItem
                active={surface === "settings"}
                icon={Settings}
                label="Settings"
                onClick={onOpenSettings}
              />
            </div>
          </nav>
        </div>

        <SidebarProfile />
      </aside>

      <main className={cx("reference-main", showFlowSidebar && "with-flow-sidebar", surface === "settings" && "surface-settings")}>
        {showFlowSidebar ? (
          <>
            <FlowSidebar
              currentModeLabel="Agent"
              favoriteFlows={favoriteFlows}
              flowProjects={flowProjects}
              onRequestAction={onRequestAction}
              onOpenSettings={onOpenSettings}
              onSelectFlow={onSelectFlow}
              onSelectProject={onSelectProject}
              selectedProjectId={selectedProjectId}
            />
            <div className="reference-main-panel">
              {showAgentTopbar ? (
                <div className="reference-topbar">
                  <div className="reference-topbar-title">
                    <strong>Agent Chat</strong>
                    <div className="reference-project-pill">
                      <Bot size={15} strokeWidth={1.9} />
                      <span>Mission: {currentProjectLabel}</span>
                      <ChevronDown size={15} strokeWidth={1.9} />
                    </div>
                    <div className="reference-chat-topbar-meta">
                      <span>Model: {selectedModelLabel}</span>
                      <span>Route: {topbarRoute.role || "primary"}</span>
                      <span>Workspace: {topbarWorkspaceLabel}</span>
                      <span>Host: {topbarHost}</span>
                      <span className={cx("status", topbarOnline ? "online" : "offline")}>
                        {topbarOnline ? "Online" : "Offline"}
                      </span>
                    </div>
                  </div>
                  <div className="reference-topbar-actions">
                    <button className="reference-black-button" onClick={onHistory} type="button">
                      Stop Agent
                    </button>
                    <button className="reference-outline-button" onClick={onMore} type="button">
                      Pause
                    </button>
                    <button className="reference-outline-button" onClick={onMore} type="button">
                      Share
                    </button>
                    <IconButton icon={MoreHorizontal} label="More actions" onClick={onMore} />
                  </div>
                </div>
              ) : null}
              <div className={cx("reference-main-body", surface === "settings" && "settings-body")}>{mainContent}</div>
            </div>
          </>
        ) : (
          <>
            <div className="reference-main-body">{mainContent}</div>
          </>
        )}
      </main>
    </div>
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
    handler(fallback, payload);
  }
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

function FluxioComposer({
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
  const submit = () => {
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

  return (
    <section className="fluxos-composer" aria-label="Fluxio command composer">
      <textarea
        aria-label="Command Fluxio"
        onChange={event => onChangeDraft?.(event.target.value)}
        placeholder={placeholder}
        value={currentDraft}
      />
      <div className="fluxos-composer-bar">
        <div className="fluxos-chip-row">
          {["repo", "screenshot", "terminal", "approval"].map(token => (
            <button key={token} onClick={() => fluxioAction(onRequestAction, `composer:chip:${token}`)} type="button">
              {titleizeToken(token)}
            </button>
          ))}
        </div>
        <div className="fluxos-composer-actions">
          <button aria-label="Attach context" onClick={onAttach} title="Attach context" type="button">
            <Paperclip size={16} strokeWidth={1.9} />
          </button>
          <button aria-label="Start dictation" onClick={onDictation} title="Start dictation" type="button">
            <Mic size={16} strokeWidth={1.9} />
          </button>
          <button className="primary" onClick={submit} type="button">
            <ArrowUp size={17} strokeWidth={2.1} />
            <span>Run</span>
          </button>
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
    builderRows,
    draft,
    liveDataStatus,
    messages,
    onAttach,
    onChangeDraft,
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
    workbenchState,
  } = props;
  const isLiveBackend = liveDataStatus?.previewMode === "live";
  const allMessages = asList(messages);
  const compactMessages = compactAgentMessages(allMessages);
  const visibleMessages = visibleAgentMessages(compactMessages, 36, 8, { requireRuntimeReports: isLiveBackend });
  const hiddenMessageCount = Math.max(0, compactMessages.length - visibleMessages.length);
  const [selectedMessageId, setSelectedMessageId] = useState("");
  const [selectedDiagnosticMessageId, setSelectedDiagnosticMessageId] = useState("");
  const selectionScopeRef = useRef("");
  const manualMessageSelectionRef = useRef(false);
  const thinkingRows = orderedAgentMessagesNewestFirst(
    compactMessages.filter(message =>
      !message?.traceOnly &&
      !isRuntimeOutputAgentMessage(message) &&
      !isControlRoomBookkeepingAgentMessage(message) &&
      (
        String(message?.label || message?.roleLabel || "").toLowerCase().includes("hermes") ||
        String(message?.label || "").toLowerCase().includes("thinking") ||
        String(message?.label || "").toLowerCase().includes("trace") ||
        (message?.technicalDetail && !message?.traceOnly)
      ),
    ),
  ).slice(0, 5);
  const livePlanRows = orderedAgentMessagesNewestFirst(
    compactMessages.filter(message => {
      const label = String(message?.label || message?.roleLabel || "").toLowerCase();
      return (
        !isLowSignalAgentMessage(message) &&
        !message?.traceOnly &&
        !isRuntimeOutputAgentMessage(message) &&
        !isControlRoomBookkeepingAgentMessage(message) &&
        (
          message?.processMessage ||
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
  const livePreviewUrlCandidates = [
    workbenchState?.previewUrl,
    workbenchState?.liveReview?.previewUrl,
    workbenchState?.previewActionUrl,
    workbenchState?.liveReview?.previewActionUrl,
  ];
  const livePreviewActionUrl = livePreviewUrlCandidates.find(isUsablePreviewUrl) || "";
  const livePreviewFrameUrl = livePreviewUrlCandidates.find(isMissionPreviewUrl) || "";
  const visibleMessageEntries = useMemo(
    () => visibleMessages.map((message, index) => ({
      key: stableAgentMessageKey(message, `message-${index}`),
      message,
    })).filter(entry => entry.key),
    [visibleMessages],
  );
  const visibleMessageKeySignature = visibleMessageEntries.map(entry => entry.key).join("|");
  const selectableMessageEntries = useMemo(() => {
    const entries = [];
    const keys = new Set();
    const pushEntry = (message, key) => {
      if (!message || keys.has(key)) return;
      keys.add(key);
      entries.push({ key, message });
    };
    visibleMessages.forEach((message, index) => {
      pushEntry(message, stableAgentMessageKey(message, `message-${index}`));
    });
    return entries;
  }, [visibleMessages]);
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
      }
      const currentEntry = current
        ? selectableMessageEntries.find(entry => entry.key === current)
        : null;
      const currentEntryMissionId = String(
        currentEntry?.message?.missionId ||
          currentEntry?.message?.mission_id ||
          workbenchState?.missionId ||
          "",
      ).trim();
      const scopedMissionId = String(workbenchState?.missionId || "").trim();
      if (
        current &&
        currentEntry &&
        manualMessageSelectionRef.current &&
        (!isLiveBackend || !scopedMissionId || currentEntryMissionId === scopedMissionId)
      ) {
        return current;
      }
      const latestRuntimeOutputMessage = visibleMessages.find(isRuntimeOutputAgentMessage);
      const latestMeaningfulMessage = latestRuntimeOutputMessage || visibleMessages.find(isMeaningfulDefaultAgentMessage);
      const defaultEntry =
        visibleMessageEntries.find(entry => entry.message === latestMeaningfulMessage) ||
        visibleMessageEntries.find(entry => entry.message === visibleMessages[visibleMessages.length - 1]) ||
        (isLiveBackend ? null : selectableMessageEntries[selectableMessageEntries.length - 1]);
      return defaultEntry?.key || "";
    });
  }, [isLiveBackend, messageSelectionContentSignature, messageSelectionScope, selectableMessageEntries, visibleMessageEntries, visibleMessages, workbenchState?.missionId]);
  useEffect(() => {
    setSelectedDiagnosticMessageId("");
  }, [messageSelectionScope]);
  const selectedMessageEntry = selectableMessageEntries.find(entry => entry.key === selectedMessageId) || null;
  const autoSelectedMessageEntry = isLiveBackend
    ? selectedMessageEntry || visibleMessageEntries[0] || null
    : selectedMessageEntry;
  const resolvedSelectedMessageKey = autoSelectedMessageEntry?.key || "";
  const selectedMessage = autoSelectedMessageEntry?.message || null;
  const messageSelectionActive = Boolean(autoSelectedMessageEntry && selectedMessage);
  const selectedMessagePreviewCandidates = previewUrlCandidatesForMessage(selectedMessage);
  const selectedMessagePreviewActionUrl = selectedMessagePreviewCandidates.find(isUsablePreviewUrl) || "";
  const messageSelectionPinned = Boolean(autoSelectedMessageEntry || selectedMessageId);
  const activePreviewActionUrl = messageSelectionPinned
    ? selectedMessagePreviewActionUrl
    : isLiveBackend
      ? ""
      : livePreviewActionUrl;
  const activePreviewFrameUrl = isLiveBackend || messageSelectionPinned ? "" : livePreviewFrameUrl;
  const livePreviewFrameBlocked = Boolean(activePreviewActionUrl && !activePreviewFrameUrl);
  const selectedMessageSourceLabel = [
    selectedMessage?.label || selectedMessage?.roleLabel || "Live mission row",
    selectedMessage?.runtimeId || workbenchState?.runtime || "",
    selectedMessage?.createdAt || selectedMessage?.meta || "",
  ].filter(Boolean).join(" · ");
  const selectedMessageBody = selectedMessage ? agentMessageDisplayDetail(selectedMessage) : "";
  const liveRuntimeReportCount = visibleMessages.filter(isRuntimeOutputAgentMessage).length;
  const hasLiveRuntimeReports = liveRuntimeReportCount > 0;
  const selectedMessageRuntimeLabel = selectedMessage?.runtimeId || workbenchState?.runtime || "live";
  const selectedMessageTimeLabel = timestampLabel(selectedMessage?.createdAt || selectedMessage?.timestamp || selectedMessage?.time || "");
  const selectedMessageKindLabel = isRuntimeOutputAgentMessage(selectedMessage)
    ? "Hermes runtime report"
    : isLiveRuntimeReportMessage(selectedMessage)
      ? "Hermes transcript"
    : selectedMessage?.processMessage
      ? "Runtime trace"
      : selectedMessage
        ? "Mission message"
        : "Runtime report";
  const previewState = messageSelectionPinned
    ? "selected-message"
    : activePreviewFrameUrl
      ? "mission-frame"
      : "empty";
  const liveThreadFirstStats = [
    ["Messages", visibleMessages.length, hiddenMessageCount > 0 ? `${hiddenMessageCount} older` : "shown"],
    ["Selected", selectedMessage ? "1" : "0", selectedMessage ? "report pinned" : "waiting"],
    ["Lanes", liveLaneRows.length, liveLaneRoleSummary || "planner/executor/verifier"],
    ["Alerts", Number(liveDataStatus?.notificationCount || 0), `${Number(liveDataStatus?.sliceNotificationCount || 0)} slice`],
  ];
  const liveDiagnosticStats = [
    ["Trace", thinkingRows.length, "rows"],
    ["Lanes", liveLaneRows.length, liveLaneRoleSummary || "runtime"],
    ["Plan", livePlanRows.length, "steps"],
  ];
  const livePreviewLabel =
    workbenchState?.previewSourceLabel ||
    workbenchState?.previewLabel ||
    (isLiveBackend ? "No live preview frame attached" : "Local layout preview");
  const selectAgentMessage = useCallback(messageKey => {
    const normalizedMessageKey = String(messageKey || "").trim();
    if (!normalizedMessageKey) return;
    if (isLiveBackend && !selectableMessageKeySet.has(normalizedMessageKey)) return;
    if (isLiveBackend) {
      const entry = selectableMessageEntries.find(item => item.key === normalizedMessageKey);
      const scopedMissionId = String(workbenchState?.missionId || "").trim();
      const entryMissionId = String(entry?.message?.missionId || entry?.message?.mission_id || "").trim();
      if (scopedMissionId && entryMissionId && entryMissionId !== scopedMissionId) {
        return;
      }
    }
    manualMessageSelectionRef.current = true;
    setSelectedMessageId(normalizedMessageKey);
  }, [isLiveBackend, selectableMessageEntries, selectableMessageKeySet, workbenchState?.missionId]);
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
  const handleDiagnosticMessageKeyDown = useCallback((event, messageKey) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      selectDiagnosticMessage(messageKey);
    }
  }, [selectDiagnosticMessage]);
  return (
    <div className="fluxos-agent-grid">
      <section className="fluxos-agent-main">
        <div className="fluxos-section-head">
          <span>Active run</span>
          <strong>{isLiveBackend ? workbenchState?.missionTitle || "Live NAS run state" : "Reproduce Fluxio UI and prepare merge"}</strong>
        </div>
        <LiveOperationsBrief
          activeRows={[]}
          liveDataStatus={liveDataStatus}
          onOpenAgent={() => onRequestAction?.("agent:open-current-mission", { missionId: workbenchState?.missionId })}
          onOpenNotifications={() => onRequestAction?.("notifications:show-live-stack")}
          onOpenQueue={() => onRequestAction?.("builder:open-project-queue")}
          projectProgressHistory={props.projectProgressHistory}
          threadRows={visibleMessages}
          workbenchState={workbenchState}
        />
        {isLiveBackend ? (
          <div className="fluxos-agent-progress" aria-label="Mission progress">
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
            aria-label="Thread-first Agent command band"
            className="fluxos-agent-thread-first-band"
            data-live-agent-thread-first-band="true"
          >
            <div className="fluxos-agent-thread-first-copy">
              <span>Thread-first Agent</span>
              <strong>{workbenchState?.missionTitle || "Live mission thread"}</strong>
              <p>{workbenchState?.progress?.nextAction || "Read the current Hermes/runtime report, then inspect proof or lane controls only when needed."}</p>
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
                disabled={!selectedMessage}
                onClick={() => document.querySelector(".fluxos-selected-message-proof")?.scrollIntoView({ block: "nearest", behavior: "smooth" })}
                type="button"
              >
                Focus selected report
              </button>
              <button onClick={() => onSetSurface?.("workbench")} type="button">
                Open Workbench
              </button>
              <button onClick={() => onRequestAction?.("notifications:show-live-stack")} type="button">
                Show notifications
              </button>
            </div>
          </section>
        ) : null}
        {isLiveBackend ? (
          <section
            aria-label="Selected live Agent report reader"
            className="fluxos-agent-selected-report"
            data-live-selected-report-reader="true"
          >
            <div className="fluxos-agent-selected-report-head">
              <div>
                <span>Selected live report</span>
                <strong>{selectedMessage ? agentMessageDisplayTitle(selectedMessage) : "Waiting for live Agent report"}</strong>
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
                <strong>{hasLiveRuntimeReports ? "No selected report body returned yet" : "No Hermes runtime reports on this selected mission"}</strong>
                <p>
                  {hasLiveRuntimeReports
                    ? "The Agent keeps the selection pinned here instead of filling the reader with fallback text."
                    : "This mission detail returned no Runtime output body, so Fluxio leaves the reader empty instead of reusing the F1 frame or any older report."}
                </p>
                {!hasLiveRuntimeReports && preferredRunningLiveMissionId ? (
                  <button
                    data-live-active-mission-switch="true"
                    onClick={() => onSelectFlow?.(preferredRunningLiveMissionId)}
                    type="button"
                  >
                    Open running Hermes mission
                  </button>
                ) : null}
              </article>
            )}
          </section>
        ) : null}
        {isLiveBackend ? (
          <section
            aria-label="Agent diagnostics shelf"
            className="fluxos-agent-diagnostics-shelf"
            data-agent-diagnostics-shelf="true"
          >
            <div>
              <span>Diagnostics</span>
              <strong>Trace, lanes, and plan stay below the report thread.</strong>
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
        ) : null}
        {isLiveBackend ? (
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
                            onClick={() => fluxioAction(onRequestAction, `agent:lane:${control.action || control.id || "inspect"}`, { lane, control })}
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
            {workbenchState?.laneControlReceipt ? (
              <article className="fluxos-agent-lane-receipt" data-live-agent-lane-control-receipt="true">
                <span>Lane control receipt</span>
                <strong>{workbenchState.laneControlReceipt.label || titleizeToken(workbenchState.laneControlReceipt.action || "Action")}</strong>
                <p>{workbenchState.laneControlReceipt.detail || "Lane action routed."}</p>
                {workbenchState.laneControlReceipt.stateMutationProof?.field ? (
                  <div className="fluxos-agent-lane-proof" data-live-agent-lane-mutation-proof="true">
                    <em>{workbenchState.laneControlReceipt.stateMutationProof.field}</em>
                    <strong>
                      {[
                        workbenchState.laneControlReceipt.stateMutationProof.before || "empty",
                        workbenchState.laneControlReceipt.stateMutationProof.after || "empty",
                      ].join(" -> ")}
                    </strong>
                    <span>{workbenchState.laneControlReceipt.stateMutationProof.observedAfterWrite ? "Observed after write" : "Write observation pending"}</span>
                  </div>
                ) : null}
              </article>
            ) : null}
          </section>
        ) : null}
        {isLiveBackend ? (
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
                  <strong>{agentMessageDisplayTitle(message)}</strong>
                </div>
                {agentMessageDisplayDetail(message) ? <p>{agentMessageDisplayDetail(message)}</p> : null}
                {message.technicalDetail ? (
                  <details className="fluxos-message-trace" open={index === thinkingRows.length - 1}>
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
        ) : null}
        <section className="fluxos-thread">
          <div className="fluxos-thread-head">
            <span>{isLiveBackend ? "Live Hermes/runtime reports" : "Thread"}</span>
            <strong>
              {visibleMessages.length} shown
              {hiddenMessageCount > 0 ? ` · ${hiddenMessageCount} older` : ""}
            </strong>
          </div>
          {visibleMessages.length ? visibleMessages.map((message, index) => {
            const messageDetail = agentMessageDisplayDetail(message);
            const messageMeta = [message.label || message.roleLabel || "", message.meta || message.createdAt || ""]
              .filter(Boolean)
              .join(" · ");
            const messageKey = stableAgentMessageKey(message, `message-${index}`);
            const messageSelected = selectedMessageId === messageKey;
            return (
              <article
                aria-pressed={messageSelected}
                className={`fluxos-message role-${message.role || "assistant"} ${message.processMessage ? "process" : ""} ${message.emphasis ? "emphasis" : ""} ${messageSelected ? "selected" : ""}`.trim()}
                data-agent-message-key={messageKey}
                data-mission-id={message.missionId || workbenchState?.missionId || ""}
                data-message-zone="thread"
                data-runtime-id={message.runtimeId || workbenchState?.runtime || ""}
                data-runtime-report={isRuntimeOutputAgentMessage(message) ? "true" : "false"}
                data-hermes-transcript={isLiveRuntimeReportMessage(message) ? "true" : "false"}
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
                  <strong>{agentMessageDisplayTitle(message)}</strong>
                </div>
                {messageDetail ? <p>{messageDetail}</p> : null}
                {message.technicalDetail ? (
                  <details className="fluxos-message-trace">
                    <summary>Runtime trace</summary>
                    <p>{String(message.technicalDetail).slice(0, 720)}</p>
                  </details>
                ) : null}
                {asList(message.chips).length > 0 ? (
                  <div className="fluxos-message-chips">
                    {asList(message.chips).slice(0, 4).map(chip => <span key={`${message.id || index}-${chip}`}>{chip}</span>)}
                  </div>
                ) : null}
              </article>
            );
          }) : isLiveBackend ? (
            <article className="fluxos-flow-empty">
              <span>Live data only</span>
              <strong>No Hermes/runtime report rows loaded for this mission</strong>
              <p>The agent thread will stay empty until the NAS returns current mission messages. Planner steps, file reads, and archived bookkeeping stay out of the main message list. The live thread shows concrete Runtime output bodies first, then real Hermes transcript rows for historical missions that did not emit a final Runtime output body. It never reuses an older frame or bundled sample message.</p>
              {preferredRunningLiveMissionId ? (
                <button
                  data-live-active-mission-switch="true"
                  onClick={() => onSelectFlow?.(preferredRunningLiveMissionId)}
                  type="button"
                >
                  Open running Hermes mission
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
                  <strong>{agentMessageDisplayTitle(message)}</strong>
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

        <FluxioComposer
          draft={draft}
          onAttach={onAttach}
          onChangeDraft={onChangeDraft}
          onDictation={onDictation}
          onRequestAction={onRequestAction}
          onSend={onSend}
          placeholder="Continue the run, ask for a review, or request a browser check..."
        />
      </section>

      <section
          className="fluxos-preview-panel"
          data-live-message-selection-version="v21"
        data-preview-state={previewState}
        data-selected-message-id={resolvedSelectedMessageKey}
        data-selected-message-requested-id={selectedMessageId}
        key={`${workbenchState?.missionId || workbenchState?.missionTitle || "agent-preview"}:${resolvedSelectedMessageKey || "no-message"}`}
      >
        <div className="fluxos-browser-chrome">
          <span />
            <strong>
              {isLiveBackend
                ? messageSelectionPinned
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
              <article className="fluxos-flow-empty fluxos-frame-blocked">
                <span>Live URL captured</span>
                <strong>Open the live artifact in a new tab</strong>
                <p>The Agent surface no longer embeds live mission frames. It stays on Hermes/runtime messages so an older served preview cannot remain stuck while you switch rows.</p>
                <div className="fluxos-preview-empty-actions">
                  <button onClick={() => window.open(activePreviewFrameUrl, "_blank", "noopener,noreferrer")} type="button">Open new tab</button>
                  <button onClick={() => fluxioAction(onRequestAction, "preview:refresh")} type="button">Refresh</button>
                </div>
              </article>
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
            <>
              <div className="fluxos-preview-card wide" />
              <div className="fluxos-preview-card active" />
              <div className="fluxos-preview-card narrow" />
              <div className="fluxos-selector one">Hero</div>
              <div className="fluxos-selector two">CTA passes</div>
            </>
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
  const { builderRows, changedItems, liveDataStatus, onOpenBuilderDetail, onRequestAction, onSelectFlow, onSelectProject, projectProgressHistory, systemAuditDigest, timelineMoments, workbenchState } = props;
  const sourceRows = asList(builderRows);
  const isLiveBackend = liveDataStatus?.previewMode === "live";
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
  const selectedProviderCapabilities = selectedMissionRow?.providerCapabilities || selectedMissionRow?.provider_capabilities || {};
  const providerCapabilityRows = asList(selectedProviderCapabilities?.providers);
  const providerLaneRows = asList(selectedProviderCapabilities?.lanes);
  const selectedRouteDecisionRows = providerLaneRows.length
    ? providerLaneRows.slice(0, 4)
    : [
        { role: "planner", provider: "openai-codex", model: "gpt-5.5", effort: "high", reason: "Plan and route the mission." },
        { role: "executor", provider: selectedProviderCapabilities.runtimeId || selectedMissionRow.runtimeId || "hermes", model: "task-fit", effort: "high", reason: "Execute through the selected runtime lane." },
        { role: "verifier", provider: "openai-codex", model: "gpt-5.5", effort: "high", reason: "Verify diffs, browser proof, and receipts." },
      ];
  const selectedThreadRows = (
    asList(workbenchState?.agentThreadPreview).length > 0
      ? asList(workbenchState?.agentThreadPreview)
      : asList(workbenchState?.runtimeOps)
  )
    .filter(item => !isLowSignalAgentMessage(item))
    .slice(0, 3);
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
  const topQueueRow = schedulingQueueRows[0] || null;
  const queueFirstHeldCount = schedulingQueueRows.filter(item => item.safeToLaunch === false).length;
  const queueFirstNotificationCount = Number(liveDataStatus?.notificationCount || 0);
  const queueFirstSliceCount = Number(liveDataStatus?.sliceNotificationCount || 0);
  return (
    <div className="fluxos-builder">
      <section className="fluxos-builder-main">
        <div className="fluxos-section-head">
          <span>Builder overview</span>
          <strong>{isLiveBackend ? "Live NAS mission readiness" : "Project readiness"}</strong>
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
                  "Open the live Agent thread or launch a mission to create the next ranked project row."}
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
              <button onClick={() => onRequestAction?.("launch:mission")} type="button">
                Launch next mission
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
                  className={`tone-${item.tone}`}
                  data-live-advancement-mission="true"
                  key={item.id}
                  onClick={() => onOpenBuilderDetail?.(item.id)}
                  type="button"
                >
                  <span>{titleizeToken(item.status)}</span>
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                  <div>
                    {item.progress == null ? <em>No numeric progress</em> : <em>{`${item.progress}%`}</em>}
                    {item.meta ? <em>{item.meta}</em> : null}
                  </div>
                  {item.progress == null ? null : <i aria-label={`Mission progress ${item.progress}%`} style={{ "--progress": `${item.progress}%` }} />}
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
            {schedulingQueueRows.length > 0 ? (
              <div className="fluxos-project-queue-list">
                {schedulingQueueRows.slice(0, 6).map(item => (
                  <button
                    className={cx("fluxos-project-queue-row", item.safeToLaunch ? "safe" : "held")}
                    key={`live-builder-queue-${item.workspaceId || item.rank}`}
                    onClick={() => onSelectProject?.(item.workspaceId)}
                    type="button"
                  >
                    <span>#{item.rank} · {titleizeToken(item.state || "watch")} · priority {item.priorityScore || 0}</span>
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
        {isLiveBackend && selectedProviderCapabilities?.schema ? (
          <section className="fluxos-gap-radar" aria-label="Provider capability truth">
            <div className="fluxos-section-head">
              <span>Provider capability truth</span>
              <strong>{titleizeToken(selectedProviderCapabilities.status || "unknown")}</strong>
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
                Quota unreported means Hermes/OpenClaw has no live quota or rate-window report for that provider.
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
        {liveAdvancementRows.length > 0 ? (
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
        {systemAuditDigest?.schema ? (
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
            {systemAuditDigest.systemLossBreakdown?.schema ? (
              <div className="fluxos-system-loss" aria-label="System loss breakdown">
                <div>
                  <span>System loss</span>
                  <strong>{`${systemAuditDigest.systemLossBreakdown.score ?? 0}/100 · ${titleizeToken(systemAuditDigest.systemLossBreakdown.severity || "low")}`}</strong>
                  <p>{systemAuditDigest.systemLossBreakdown.nextAction || "Keep sampling live outcomes."}</p>
                </div>
                <div className="fluxos-system-loss-drivers">
                  {asList(systemAuditDigest.systemLossBreakdown.drivers).slice(0, 4).map(item => (
                    <article key={item.id || item.title}>
                      <span>{`${item.lane || "System"} · loss ${item.loss ?? 0}`}</span>
                      <strong>{item.title || "Loss driver"}</strong>
                      <p>{item.detail || item.evidence || item.nextAction}</p>
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
        {publicLaunchReadiness.status &&
        publicLaunchReadiness.status !== "ready_for_public_launch" ? (
          <section className="fluxos-gap-radar fluxos-public-launch-proof-path" aria-label="Live public launch blocker" data-public-launch-proof-path="true">
            <div className="fluxos-section-head">
              <span>Live public launch blocker</span>
              <strong>{titleizeToken(publicLaunchReadiness.status)}</strong>
            </div>
            <p>
              {publicLaunchReadiness.nextAction ||
                "Public launch is not proven until current web and external publication evidence are present."}
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
                  Launch repair packet · {publicLaunchRepairPacket.canClaimPublicLaunch ? "claim enabled" : "cannot claim public launch"}
                </span>
                <button type="button">
                  <strong>{titleizeToken(publicLaunchRepairPacket.primaryBlocker || publicLaunchReadiness.status || "Next blocker")}</strong>
                  <em>
                    {`${publicLaunchRepairPacket.sourceCoverage || "source coverage unknown"} · ${publicLaunchRepairPacket.releaseBlockingPathCount ?? publicLaunchRepairPacket.releaseBlockingSampleCount ?? 0} release-impacting paths`}
                  </em>
                </button>
                <button type="button">
                  <strong>Next publish action</strong>
                  <em>{publicLaunchRepairPacket.nextAction || publicLaunchReadiness.nextAction}</em>
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
            {asList(publicLaunchReadiness.publicWeb?.sourceDirtyPathSample).length > 0 ? (
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
              <i aria-label={`Selected mission progress ${selectedProgressValue}%`} style={{ "--progress": `${selectedProgressValue}%` }} />
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
            return (
              <button className={cx("fluxos-flow-card", isLiveBackend && "live-row")} key={`${tuple[0]}-${index}`} onClick={() => onSelectFlow?.(row?.id || tuple[0])} type="button">
                <span>{tuple[1]}</span>
                <strong>{tuple[0]}</strong>
                <p>{tuple[2]}</p>
                {width ? (
                  <div aria-label={`Live progress ${width}`}><i style={{ width }} /></div>
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
            <p>Delegated Hermes/OpenClaw lane counts are carried from the live mission rows instead of hidden in logs.</p>
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

function FluxioSkillsSurface({ onRequestAction, studioState, skillStudioState, surface }) {
  const effectiveStudioState = studioState || skillStudioState || {};
  const ruleSets = asList(effectiveStudioState?.ruleSets).slice(0, 4);
  const isRuleSets = surface === "rule-sets";
  const feedbackLoop = effectiveStudioState?.feedbackLoop || {};
  const routing = feedbackLoop.systemLossRouting || {};
  const latestFeedback = asList(feedbackLoop.latest).slice(0, 3);
  const repairProposals = asList(feedbackLoop.repairProposals).slice(0, 3);
  const measuredSkillCount = Number(feedbackLoop.measuredSkillCount || 0);
  const repairCount = Number(feedbackLoop.repairCount || 0);
  const reinforceCount = Number(feedbackLoop.reinforceCount || 0);
  const heldSkillCount = asList(routing.activeRepairSkillIds).length;
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
              : "Live mission-slice feedback captured this skill in the current system-loss loop.",
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
  const redTeamEscalation =
    effectiveStudioState?.redTeamEscalation ||
    studioState?.redTeamEscalation ||
    skillStudioState?.redTeamEscalation ||
    {};
  const redTeamHistory = asList(redTeamEscalation.history).slice(-6);
  return (
    <div className="fluxos-skills">
      <section className="fluxos-skills-list">
        <div className="fluxos-section-head">
          <span>{isRuleSets ? "Rule Sets" : "Skill library"}</span>
          <strong>{isRuleSets ? "Core policy and Approval gates" : effectiveStudioState?.liveReady ? "Live measured capabilities" : "Awaiting NAS skill registry"}</strong>
        </div>
        {effectiveStudioState?.liveReady && !isRuleSets ? (
          <section className="fluxos-skill-command-band" aria-label="Live skills command band" data-live-skills-command-band="true">
            <div>
              <span>Live skills</span>
              <strong>System-loss routing</strong>
              <p>
                {`${displayedSkills.length} visible NAS skill rows. ${repairCount} repair, ${reinforceCount} reinforce, ${heldSkillCount} held before reuse.`}
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
              <button onClick={() => fluxioAction(onRequestAction, "skills:review-system-loss")} type="button">Review loss</button>
              <button onClick={() => fluxioAction(onRequestAction, "skills:open-repair-queue")} type="button">Repair queue</button>
              <button disabled={repairProposals.length === 0} onClick={() => fluxioAction(onRequestAction, `skills:apply-repair:${repairProposals[0]?.skillId || repairProposals[0]?.proposalId || "next"}`)} type="button">Apply repair</button>
            </div>
          </section>
        ) : null}
        {effectiveStudioState?.liveReady && !isRuleSets ? (
          <div className="fluxos-live-skill-summary" aria-label="Live skill catalog source">
            <span>{effectiveStudioState.liveSource || "control-room skill catalog"}</span>
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
        )) : displayedSkills.length > 0 ? displayedSkills.map(item => (
          <button
            className="fluxos-skill-card"
            data-live-skill-row={effectiveStudioState?.liveReady ? "true" : "false"}
            data-skill-feedback-state={item?.feedbackSummary?.selectionPolicy?.state || item?.feedbackSummary?.trend || item?.status || "live"}
            data-skill-id={item.id || item.name || ""}
            key={item.id || item.name}
            onClick={() => fluxioAction(onRequestAction, `skill:open:${item.id || item.name}`)}
            type="button"
          >
            <WandSparkles size={20} strokeWidth={1.7} />
            <div>
              <strong>{item.name || item.label || item.id || "Skill"}</strong>
              <p>{item.summary || item.description || "Live skill returned by the NAS snapshot."}</p>
            </div>
            <span>{item.status || item.promotionState || "live"}</span>
            <em>
              {item?.feedbackSummary?.latestSystemLoss != null
                ? `loss ${item.feedbackSummary.latestSystemLoss} · ${item.feedbackSummary.selectionPolicy?.state || item.feedbackSummary.trend || "measured"}`
                : asList(item.tags).slice(0, 2).join(" · ") || item.category || "measured"}
            </em>
          </button>
        )) : (
          <article className="fluxos-flow-empty">
            <span>Live data only</span>
            <strong>{isRuleSets ? "No live rule sets returned" : "No live skill registry returned yet"}</strong>
            <p>
              {effectiveStudioState?.liveReady
                ? "The NAS snapshot did not include measured skill rows for this surface."
                : "This surface no longer renders the bundled static skill catalog in live mode. Refresh and wait for the full control-room snapshot."}
            </p>
          </article>
        )}
      </section>
      <section className="fluxos-editor">
        <div className="fluxos-section-head">
          <span>{isRuleSets ? "Ruleset editor" : "Mission-slice feedback loop"}</span>
          <strong>{isRuleSets ? ruleSets[0]?.name || "Frontend merge policy" : "System loss routing"}</strong>
        </div>
        {!isRuleSets ? (
          <div className="fluxos-loss-routing" aria-label="System loss routing">
            <div className="fluxos-loss-routing-head">
              <span>{routing.enabled ? "Active" : "Collecting evidence"}</span>
              <strong>
                {`${measuredSkillCount} measured · ${repairCount} repair · ${reinforceCount} reinforce`}
              </strong>
              <p>
                {`Prefer slices at or below ${routing.preferThreshold ?? 0.15} loss. Deprioritize skills at or above ${routing.deprioritizeThreshold ?? 0.55} loss until repair evidence is clean.`}
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
                  <p>{`loss ${item.systemLoss ?? "n/a"} · improvement ${item.improvementScore ?? "n/a"}`}</p>
                </article>
              )) : (
                <article>
                  <span>Awaiting first slice</span>
                  <strong>No system-loss feedback yet</strong>
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
                  <p>High-loss skills will appear here when mission-slice feedback produces a repair action.</p>
                </article>
              )}
            </div>
      </section>
    </div>
  );
}

const FLUXIO_REAL_IMAGE_SESSIONS_KEY = "fluxio.images.real_sessions";

function loadFluxioRealImageSessions() {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(FLUXIO_REAL_IMAGE_SESSIONS_KEY) || "[]");
    return Array.isArray(parsed) ? parsed.filter(item => item?.requestId && item?.previewUrl).slice(0, 12) : [];
  } catch {
    return [];
  }
}

function FluxioImagesSurface({ callBackend, onRequestAction }) {
  const [prompt, setPrompt] = useState("Create a calm Fluxio agent command center with live preview, evidence rail, and approval state.");
  const [sessions, setSessions] = useState(loadFluxioRealImageSessions);
  const [status, setStatus] = useState({ state: "idle", message: "" });
  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(FLUXIO_REAL_IMAGE_SESSIONS_KEY, JSON.stringify(sessions.slice(0, 12)));
  }, [sessions]);

  const generateImage = async () => {
    const text = prompt.trim();
    if (!text) {
      setStatus({ state: "blocked", message: "Write an image prompt first." });
      return;
    }
    if (typeof callBackend !== "function") {
      setStatus({ state: "blocked", message: "Live backend bridge is unavailable." });
      return;
    }
    const requestId = `imgreq-ui-${Date.now().toString(36)}`;
    setStatus({ state: "running", message: "Generating through Codex GPT-Image..." });
    try {
      const result = await callBackend("image_playground_operation_command", {
        requestId,
        operation: "generate",
        providerId: "codex_subscription_gpt_image2",
        size: "1024x1024",
        canvas: { width: 1024, height: 1024 },
        prompt: { text },
      });
      if (!result?.previewUrl || result?.providerStatus !== "available") {
        throw new Error(result?.message || "Image provider did not return a generated artifact.");
      }
      const session = {
        requestId: result.requestId || requestId,
        prompt: text,
        previewUrl: result.previewUrl,
        manifestUrl: result.manifestUrl || "",
        manifestPath: result.manifestPath || "",
        outputArtifactPath: result.outputArtifactPath || result.imagePath || "",
        provider: result.provider || "openai-codex",
        model: result.model || "gpt-image-2",
        createdAt: new Date().toISOString(),
        receipt: result.receipt || {},
      };
      setSessions(current => [session, ...current.filter(item => item.requestId !== session.requestId)].slice(0, 12));
      setStatus({ state: "ready", message: "Minted real Codex image session with artifact proof." });
    } catch (error) {
      setStatus({ state: "blocked", message: String(error?.message || error || "Image generation failed.") });
    }
  };

  return (
    <div className="fluxos-images">
      <section className="fluxos-image-prompt">
        <div className="fluxos-section-head">
          <span>Image studio</span>
          <strong>Codex GPT-Image sessions</strong>
        </div>
        <textarea aria-label="Image prompt" onChange={event => setPrompt(event.target.value)} value={prompt} />
        <div className="fluxos-review-actions">
          <button onClick={() => fluxioAction(onRequestAction, "images:add-reference")} type="button">Add reference</button>
          <button className="primary" disabled={status.state === "running"} onClick={() => void generateImage()} type="button">
            {status.state === "running" ? "Generating..." : "Generate"}
          </button>
        </div>
        {status.message ? <p className={`fluxos-image-status state-${status.state}`}>{status.message}</p> : null}
        <div className="fluxos-reference-strip">
          <span>Provider openai-codex</span>
          <span>Model gpt-image-2</span>
          <span>{sessions.length} minted session{sessions.length === 1 ? "" : "s"}</span>
        </div>
      </section>
      <section className="fluxos-variant-grid">
        {sessions.length ? sessions.map((session, index) => (
          <button className="fluxos-variant-card minted" key={session.requestId} onClick={() => fluxioAction(onRequestAction, `images:variant:${session.requestId}`)} type="button">
            <img alt={`Generated Fluxio session ${index + 1}`} src={resolveReferenceArtifactUrl(session.previewUrl)} />
            <strong>{session.prompt.slice(0, 42) || "Generated image"}</strong>
            <span>{session.provider} · {session.model}</span>
            <em>{new Date(session.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</em>
          </button>
        )) : (
          <article className="fluxos-empty-minted-session">
            <strong>No minted image sessions yet</strong>
            <p>Generate through the Codex GPT-Image lane to create a real artifact-backed session.</p>
          </article>
        )}
      </section>
      <section className="fluxos-image-inspector">
        <div className="fluxos-section-head">
          <span>Inspector</span>
          <strong>{sessions[0]?.requestId || "Awaiting artifact"}</strong>
        </div>
        <p>
          {sessions[0]
            ? `${sessions[0].provider} / ${sessions[0].model} wrote ${sessions[0].outputArtifactPath || "a served artifact"}.`
            : "Generated sessions keep prompt, provider proof, manifest, preview URL, and export target together."}
        </p>
        <button onClick={() => fluxioAction(onRequestAction, "images:send-to-builder")} type="button">Attach to review bundle</button>
        <button disabled={!sessions[0]?.previewUrl} onClick={() => callBackend?.("image.export", { prompt, session: sessions[0] })} type="button">Export asset</button>
      </section>
    </div>
  );
}

function FluxioWorkbenchSurface({ liveDataStatus, messages = [], onRequestAction, onSetSurface, timelineMoments = [], workbenchState }) {
  const isLiveBackend = liveDataStatus?.previewMode === "live";
  const runtimeOps = asList(workbenchState?.runtimeOps).slice(0, 8);
  const artifacts = asList(workbenchState?.artifacts).slice(0, 8);
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
  const liveThreadRowKeySignature = liveThreadRowEntries.map(entry => entry.key).join("|");
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
          workbenchState?.missionId ||
          "",
      ).trim();
      const scopedMissionId = String(workbenchState?.missionId || "").trim();
      if (
        current &&
        currentEntry &&
        manualWorkbenchMessageSelectionRef.current &&
        (!isLiveBackend || !scopedMissionId || currentEntryMissionId === scopedMissionId)
      ) {
        return current;
      }
      const runtimeReport = liveThreadRows.find(isRuntimeOutputAgentMessage);
      const meaningful = runtimeReport || liveThreadRows.find(isMeaningfulDefaultAgentMessage) || liveThreadRows[0] || null;
      if (!meaningful) return "";
      const meaningfulEntry = liveThreadRowEntries.find(entry => entry.item === meaningful);
      return meaningfulEntry?.key || "";
    });
  }, [isLiveBackend, liveThreadRowEntries, liveThreadRows, workbenchSelectionScope, liveThreadRowKeySignature, workbenchState?.missionId]);
  const selectedWorkbenchMessage =
    liveThreadRowEntries.find(entry => entry.key === selectedWorkbenchMessageId)?.item ||
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
  const previewFrameUrl = selectedWorkbenchMessage || isLiveBackend ? "" : previewUrlCandidates.find(isMissionPreviewUrl) || "";
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
      : liveThreadRows
        .filter(item => item.processMessage || item.emphasis || item.technicalDetail)
        .map(item => ({
          id: item.id,
          label: item.title || item.label || "Live mission message",
          detail: item.detail || item.technicalDetail || item.meta || "Message returned by the live mission detail endpoint.",
          status: item.tone || item.label || "live",
          timestamp: item.createdAt || item.timestamp || "",
        }));
  const workbenchProofMetrics = [
    ["Messages", liveThreadRows.length, selectedWorkbenchMessage ? "runtime reports" : "waiting for thread"],
    ["Artifacts", artifacts.length, artifacts.length ? "returned by NAS" : "none returned"],
    ["Operations", operationRows.length, operationRows.length ? "live timeline" : "none returned"],
    ["Signals", notificationEvents.reduce((total, item) => total + Number(item?.count || 0), 0), "notifications"],
  ];
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
  return (
    <div className="fluxos-workbench">
      <section className="fluxos-rail-panel fluxos-workbench-live-state">
        <div className="fluxos-section-head">
          <span>Live state</span>
          <strong>{titleizeToken(workbenchState?.missionStatus || workbenchState?.status || (liveDataStatus?.loading ? "Loading" : "Ready"))}</strong>
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
            {liveThreadRowEntries.length > 0 ? liveThreadRowEntries.map(({ item, key: messageKey }) => {
              const selected = selectedWorkbenchMessageId === messageKey;
              return (
              <article
                aria-pressed={selected}
                className={selected ? "selected" : ""}
                data-agent-message-key={messageKey}
                key={messageKey}
                onClick={() => {
                  manualWorkbenchMessageSelectionRef.current = true;
                  setSelectedWorkbenchMessageId(messageKey);
                }}
                onKeyDown={event => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
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
            aria-label="Live Workbench proof controls"
            className="fluxos-workbench-proof-band"
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
        <div className="fluxos-browser-chrome">
          <span />
          <strong>{workbenchState?.previewLabel || (isLiveBackend ? "No live preview frame attached" : "local layout preview")}</strong>
          <button onClick={() => fluxioAction(onRequestAction, "workbench:screenshot")} type="button">Screenshot</button>
        </div>
        <div
          className="fluxos-live-preview workbench"
          data-preview-state={livePreviewState}
          data-selected-message-id={selectedWorkbenchMessageId}
        >
          {isLiveBackend && selectedWorkbenchMessage ? (
            <article className="fluxos-flow-empty fluxos-selected-message-proof">
              <span>Selected live message</span>
              <strong>{agentMessageDisplayTitle(selectedWorkbenchMessage)}</strong>
              {selectedWorkbenchBody ? (
                <pre className="fluxos-selected-message-body" data-live-selected-message-body="true">{selectedWorkbenchBody}</pre>
              ) : (
                <p>{selectedWorkbenchMessage.meta || "This row has no served preview artifact. The Workbench stays pinned to the selected message instead of reusing an older frame."}</p>
              )}
              <div className="fluxos-preview-empty-actions">
                {previewActionUrl ? (
                  <button onClick={() => window.open(previewActionUrl, "_blank", "noopener,noreferrer")} type="button">Open preview</button>
                ) : null}
                <button onClick={() => fluxioAction(onRequestAction, "run:message-comment", { messageId: selectedWorkbenchMessage.id })} type="button">Comment</button>
              </div>
            </article>
          ) : isLiveBackend && previewFrameUrl ? (
            <>
              <iframe
                className="fluxos-live-preview-frame"
                key={`${workbenchState?.missionId || "mission"}:${selectedWorkbenchMessageId || "mission"}:${previewFrameUrl}`}
                src={previewFrameUrl}
                title="Live workbench preview"
              />
              <div className="fluxos-preview-policy-note">
                <strong>Embedded preview can be refused by the target site.</strong>
                <p>Open the served URL or artifact directly; this panel will not draw placeholder UI over live mode.</p>
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
            <>
              <div className="fluxos-preview-card wide" />
              <div className="fluxos-preview-card active" />
              <div className="fluxos-selector one">{isLiveBackend ? "Live target" : "Local target"}</div>
              <div className="fluxos-selector two">Layout diff</div>
            </>
          ) : (
            <article className="fluxos-flow-empty">
              <span>Live data only</span>
              <strong>{noPreviewLabel}</strong>
              <p>{noPreviewCopy}</p>
              <div className="fluxos-preview-empty-actions">
                <button onClick={() => onSetSurface?.("agent")} type="button">Open Agent thread</button>
                <button onClick={() => fluxioAction(onRequestAction, "workbench:screenshot")} type="button">Capture proof</button>
              </div>
            </article>
          )}
        </div>
        {isLiveBackend ? (
          <div className="fluxos-artifact-list" aria-label="Live mission artifacts">
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
      <section className="fluxos-action-timeline">
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
}) {
  const isLiveBackend = liveDataStatus?.previewMode === "live";
  const liveRows = isLiveBackend ? sortLiveBuilderRows(builderRows) : [];
  const runningRows = liveRows.filter(row => {
    const status = String(row.status || row.statusLabel || "").toLowerCase();
    return status === "running" || status === "delegated" || status === "active";
  });
  const visibleRows = (runningRows.length ? runningRows : liveRows).slice(0, 6);
  const notifications = isLiveBackend ? asList(notificationItems).slice(0, 8) : [];
  const sliceNotifications = notifications.filter(item => item.kind === "mission_slice_completed");
  const topRow = visibleRows[0] || null;
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
    ["Alerts", Number(liveDataStatus?.notificationCount || notifications.length || 0), `${Number(liveDataStatus?.sliceNotificationCount || sliceNotifications.length || 0)} slice`],
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

      <section className="fluxos-phone-mission-list" aria-label="Live phone mission list">
        <div className="fluxos-thread-head">
          <span>Live missions</span>
          <strong>{visibleRows.length} shown</strong>
        </div>
        {visibleRows.length ? visibleRows.map(row => {
          const progressValue = clampPercent(row.progress);
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
          <strong>{notifications.length} visible</strong>
        </div>
        {notifications.length ? notifications.map(item => {
          const missionId = item.missionId || item.mission_id || "";
          const title = item.title || item.headline || item.label || "Mission update";
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
              <p>{detail}</p>
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
  return (
    <div className="fluxos-settings">
      <section className="fluxos-theme-lab">
        <div className="fluxos-section-head">
          <span>Theme engine</span>
          <strong>One layout, multiple operating moods</strong>
        </div>
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
              <span className="fluxos-theme-preview" aria-hidden="true">
                <i />
                <b />
                <em />
              </span>
              <strong>{theme.label}</strong>
              <small>Best for {theme.bestFor}</small>
              <span>Density: {theme.density}</span>
              <span>Motion: {theme.motion}</span>
              <span>Contrast: {theme.contrast}</span>
            </button>
          ))}
        </div>
      </section>
      <section className="fluxos-database-lab">
        <div className="fluxos-section-head">
          <span>Databases</span>
          <strong>Colorful data layer for runs, memory, and artifacts</strong>
        </div>
        <div className="fluxos-database-grid" aria-label="Fluxio databases">
          {FLUXIO_DATABASES.map(([id, label, copy, status, tone]) => (
            <button
              className={`tone-${tone}`}
              key={id}
              onClick={() => fluxioAction(onRequestAction, `database:open:${id}`)}
              type="button"
            >
              <span className="fluxos-database-orb">
                <Database size={24} strokeWidth={1.75} />
              </span>
              <strong>{label}</strong>
              <small>{copy}</small>
              <em>{status}</em>
            </button>
          ))}
        </div>
      </section>
      {[
        ["Models", "Provider accounts, model routes, reasoning level, and fallbacks."],
        ["Rules & Routing", "Approval policy, write scope, destructive action handling."],
        ["Workspace", "Local path, NAS bridge, runtime compartment, and file watching."],
        ["Appearance", "Density, contrast, reduced motion, and command palette."],
      ].map(([title, copy]) => (
        <section className="fluxos-settings-card" key={title}>
          <div className="fluxos-section-head">
            <span>{title}</span>
            <strong>{settingsState?.activeTab === title.toLowerCase() ? "Active" : "Configured"}</strong>
          </div>
          <p>{copy}</p>
          <button onClick={() => fluxioAction(onRequestAction, `settings:${title.toLowerCase()}`)} type="button">Open {title}</button>
        </section>
      ))}
    </div>
  );
}

function FluxioSurfaceContent(props) {
  if (props.surface === "home") return <FluxioHomeSurface {...props} />;
  if (props.surface === "builder") return <FluxioBuilderSurface {...props} />;
  if (props.surface === "phone") return <FluxioPhoneProgressSurface {...props} />;
  if (props.surface === "skills" || props.surface === "rule-sets") return <FluxioSkillsSurface {...props} />;
  if (props.surface === "images") return <FluxioImagesSurface {...props} />;
  if (props.surface === "workbench") return <FluxioWorkbenchSurface {...props} />;
  if (props.surface === "settings") return <FluxioSettingsSurface {...props} />;
  if (props.agentScene === "idle") {
    return <AgentIdleSurface {...props} onUseSlashCommand={props.onInsertSlashCommand} />;
  }
  return (
    <FluxioAgentSurface
      key={props.workbenchState?.missionId || props.currentProjectLabel || "agent-run"}
      {...props}
      onUseSlashCommand={props.onInsertSlashCommand}
    />
  );
}

function FluxioAgentOS(props) {
  const {
    agentScene = "run",
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
