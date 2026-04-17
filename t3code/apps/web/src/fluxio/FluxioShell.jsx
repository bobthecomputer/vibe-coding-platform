import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import { buildFixtureSnapshot, listFixtureOptions } from "../../../../../desktop-ui/fixtures.js";
import {
  activeProfileId,
  currentProfileParameters,
  missionChecksPlaceholder,
  missionObjectivePlaceholder,
  previewLabel,
  runtimeLabel,
  selectedMission,
  selectedWorkspace,
  titleizeToken,
} from "../../../../../desktop-ui/fluxioHelpers.js";
import { ActionButton, Field, Modal, StatusPill } from "../../../../../desktop-ui/MissionControlPrimitives.jsx";
import { buildMissionControlModel } from "../../../../../desktop-ui/missionControlModel.js";

const STORAGE_KEYS = {
  uiMode: "fluxio.ui.mode",
  telegramChatId: "fluxio.telegram.chatId",
  previewMode: "fluxio.preview.mode",
  liveSyncSeconds: "fluxio.live_sync.seconds",
  codeExecutionEnabled: "fluxio.openai.code_execution.enabled",
  codeExecutionMemory: "fluxio.openai.code_execution.memory",
  workspaceSearch: "fluxio.sidebar.workspace.search",
  missionSearch: "fluxio.sidebar.mission.search",
  workspaceOrder: "fluxio.sidebar.workspace.order",
  missionOrder: "fluxio.sidebar.mission.order",
  splitViewEnabled: "fluxio.agent.split.enabled",
  splitMissionId: "fluxio.agent.split.mission_id",
  localTasks: "fluxio.tasks.local",
  memoryPolicy: "fluxio.memory.policy",
  memoryStore: "fluxio.memory.store",
  debugEvents: "fluxio.debug.events",
  persistedUiState: "fluxio.ui.state",
};

const FIXTURE_OPTIONS = [{ id: "live", name: "Live Backend" }, ...listFixtureOptions()];
const LIVE_SYNC_OPTIONS = [
  { value: "off", label: "Manual" },
  { value: "1", label: "1s" },
  { value: "5", label: "5s" },
  { value: "15", label: "15s" },
  { value: "30", label: "30s" },
];
const DEFAULT_OPENCLAW_GATEWAY_URL = "ws://127.0.0.1:8765";

const DEFAULT_WORKSPACE_FORM = {
  name: "",
  path: "",
  defaultRuntime: "openclaw",
  userProfile: "builder",
};

const DEFAULT_MISSION_FORM = {
  workspaceId: "",
  runtime: "openclaw",
  mode: "Autopilot",
  profile: "builder",
  budgetHours: 12,
  runUntil: "pause_on_failure",
  objective: "",
  successChecks: "",
};

const PREFERRED_HARNESS_OPTIONS = [
  { value: "fluxio_hybrid", label: "Fluxio Hybrid" },
  { value: "legacy_autonomous_engine", label: "Legacy Autonomous Engine" },
];

const ROUTING_STRATEGY_OPTIONS = [
  { value: "profile_default", label: "Profile Default" },
  { value: "planner_premium_executor_efficient", label: "Planner Premium / Executor Efficient" },
  { value: "uniform_quality", label: "Uniform Quality" },
  { value: "budget_first", label: "Budget First" },
];

const MINIMAX_AUTH_OPTIONS = [
  { value: "none", label: "Not Configured" },
  { value: "minimax-portal-oauth", label: "MiniMax Portal OAuth" },
  { value: "minimax-api", label: "MiniMax API Key" },
];
const OPENAI_CODEX_AUTH_OPTIONS = [
  { value: "none", label: "Not Configured" },
  { value: "chatgpt", label: "ChatGPT Portal" },
  { value: "api", label: "API Key" },
];

const COMMIT_STYLE_OPTIONS = [
  { value: "scoped", label: "Scoped" },
  { value: "concise", label: "Concise" },
  { value: "detailed", label: "Detailed" },
];

const EXECUTION_TARGET_OPTIONS = [
  { value: "profile_default", label: "Profile Default" },
  { value: "workspace_root", label: "Workspace Root" },
  { value: "isolated_worktree", label: "Isolated Worktree" },
];
const ROUTE_ROLE_OPTIONS = ["planner", "executor", "verifier"];
const MODEL_PROVIDER_OPTIONS = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "minimax", label: "MiniMax" },
  { value: "openrouter", label: "OpenRouter" },
];
const MODEL_EFFORT_OPTIONS = [
  { value: "default", label: "Default" },
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];
const CODE_EXECUTION_MEMORY_OPTIONS = [
  { value: "1g", label: "1 GB" },
  { value: "4g", label: "4 GB" },
  { value: "16g", label: "16 GB" },
  { value: "64g", label: "64 GB" },
];
const PROVIDER_SECRET_OPTIONS = [
  {
    id: "openai",
    label: "OpenAI / Codex",
    env: "OPENAI_API_KEY",
    note: "Used for GPT and Codex-family routes.",
  },
  {
    id: "anthropic",
    label: "Anthropic",
    env: "ANTHROPIC_API_KEY",
    note: "Used when planner or verifier routes target Claude.",
  },
  {
    id: "openrouter",
    label: "OpenRouter",
    env: "OPENROUTER_API_KEY",
    note: "Used when a route is delegated through OpenRouter.",
  },
  {
    id: "minimax",
    label: "MiniMax",
    env: "MINIMAX_API_KEY",
    note: "Used when a route targets MiniMax with API-key auth. Portal OAuth does not require a stored key.",
  },
];
const ROUTE_MODEL_OPTIONS = [
  "gpt-5.4",
  "gpt-5.4-mini",
  "codex",
  "claude-sonnet-4.5",
  "claude-opus-4.1",
  "MiniMax-M2.7",
  "MiniMax-M2.7-highspeed",
];
const MODEL_QUICK_PRESETS = [
  {
    id: "coding_fast",
    label: "Coding Fast",
    provider: "openai",
    model: "gpt-5.4-mini",
    effort: "medium",
  },
  {
    id: "planning_deep",
    label: "Planning Deep",
    provider: "openai",
    model: "gpt-5.4",
    effort: "high",
  },
  {
    id: "review_safe",
    label: "Review Safe",
    provider: "anthropic",
    model: "claude-sonnet-4.5",
    effort: "medium",
  },
  {
    id: "budget_route",
    label: "Budget Route",
    provider: "minimax",
    model: "MiniMax-M2.7",
    effort: "low",
  },
];
const DEFAULT_MEMORY_POLICY = {
  missionScoped: true,
  projectScoped: true,
  includeInFollowUps: true,
};
const DEFAULT_TASK_FORM = {
  name: "",
  prompt: "",
  trigger: "schedule",
  everyMinutes: 30,
  webhookToken: "",
  active: true,
};
const MAX_TASK_LOG = 120;
const MAX_DEBUG_LOG = 240;
const MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024;
const MAX_INLINE_ATTACHMENTS = 6;
const WINDOWED_THRESHOLD = 60;

const AGENT_BLOCKER_DRAWER_IDS = ["queue", "proof", "context"];
const AGENT_BUILDER_ONLY_DRAWERS = ["builder", "skills", "runtime", "profiles", "settings"];
const AGENT_BLOCKER_STATUSES = ["needs_approval", "blocked", "verification_failed"];
const AGENT_QUEUED_PAUSE_STATES = ["queued", "resume_available"];

function hasTauriBackend() {
  return Boolean(globalThis.window?.__TAURI__ || globalThis.window?.__TAURI_INTERNALS__);
}

function loadStoredJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) {
      return fallback;
    }
    const parsed = JSON.parse(raw);
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

function copyTextValue(text) {
  const value = String(text || "").trim();
  if (!value) {
    return Promise.resolve(false);
  }
  if (navigator?.clipboard?.writeText) {
    return navigator.clipboard.writeText(value).then(() => true).catch(() => false);
  }
  try {
    const temp = document.createElement("textarea");
    temp.value = value;
    temp.setAttribute("readonly", "true");
    temp.style.position = "absolute";
    temp.style.left = "-9999px";
    document.body.appendChild(temp);
    temp.select();
    const ok = document.execCommand("copy");
    temp.remove();
    return Promise.resolve(Boolean(ok));
  } catch {
    return Promise.resolve(false);
  }
}

const BACKEND_CALL_SUBSCRIBERS = new Set();

function subscribeBackendCalls(handler) {
  BACKEND_CALL_SUBSCRIBERS.add(handler);
  return () => {
    BACKEND_CALL_SUBSCRIBERS.delete(handler);
  };
}

async function callBackend(command, payload = undefined, options = {}) {
  const startedAt = performance.now();
  try {
    const response = payload === undefined ? await invoke(command) : await invoke(command, payload);
    const event = {
      id: `invoke-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      kind: "invoke.ok",
      command,
      durationMs: Math.round(performance.now() - startedAt),
      at: new Date().toISOString(),
    };
    BACKEND_CALL_SUBSCRIBERS.forEach(handler => {
      try {
        handler(event);
      } catch {
        return;
      }
    });
    return response;
  } catch (error) {
    const event = {
      id: `invoke-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      kind: "invoke.error",
      command,
      durationMs: Math.round(performance.now() - startedAt),
      at: new Date().toISOString(),
      error: String(error),
    };
    BACKEND_CALL_SUBSCRIBERS.forEach(handler => {
      try {
        handler(event);
      } catch {
        return;
      }
    });
    if (options.throwOnError) {
      throw error;
    }
    return null;
  }
}

function useToastQueue() {
  const [items, setItems] = useState([]);

  const push = useCallback((message, kind = "info") => {
    const item = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      kind,
      message,
    };
    setItems(current => [...current, item]);
    window.setTimeout(() => {
      setItems(current => current.filter(entry => entry.id !== item.id));
    }, 3600);
  }, []);

  return { items, push };
}

function toneClass(tone) {
  if (tone === "good") {
    return "tone-good";
  }
  if (tone === "warn") {
    return "tone-warn";
  }
  if (tone === "bad") {
    return "tone-bad";
  }
  return "tone-neutral";
}

function timestampLabel(value) {
  if (!value) {
    return "";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function timeValue(value) {
  if (!value) {
    return Number.NaN;
  }
  const parsed = new Date(value);
  const ms = parsed.getTime();
  return Number.isNaN(ms) ? Number.NaN : ms;
}

function asList(value) {
  return Array.isArray(value) ? value : [];
}

function boundaryTimestamp(boundary) {
  return (
    boundary?.created_at ||
    boundary?.createdAt ||
    boundary?.requested_at ||
    boundary?.requestedAt ||
    boundary?.updated_at ||
    boundary?.updatedAt ||
    boundary?.timestamp ||
    ""
  );
}

function isHeartbeatRuntimeKind(kind) {
  return String(kind || "").toLowerCase() === "session.heartbeat";
}

function isProcessRuntimeKind(kind) {
  return ["runtime.output", "runtime.stdout", "runtime.stderr"].includes(
    String(kind || "").toLowerCase(),
  );
}

function isTraceRuntimeKind(kind) {
  const normalized = String(kind || "").toLowerCase();
  return (
    isProcessRuntimeKind(normalized) ||
    [
      "runtime.phase",
      "runtime.plan",
      "runtime.thinking",
      "runtime.reasoning",
      "runtime.route_contract",
    ].includes(normalized)
  );
}

function phaseRouteRole(phase) {
  const normalized = String(phase || "").trim().toLowerCase();
  if (["plan", "replan"].includes(normalized)) {
    return "planner";
  }
  if (normalized === "verify") {
    return "verifier";
  }
  return "executor";
}

function isIgnorableAgentRuntimeEvent(event) {
  return isHeartbeatRuntimeKind(event?.kind);
}

function ToastHost({ items }) {
  return (
    <div aria-atomic="true" aria-live="polite" className="toast-host">
      {items.map(item => (
        <div className={`toast ${toneClass(item.kind === "error" ? "bad" : item.kind === "warn" ? "warn" : "neutral")}`} key={item.id}>
          {item.message}
        </div>
      ))}
    </div>
  );
}

function NavItem({
  active = false,
  draggable = false,
  title,
  subtitle,
  context = "",
  stats = [],
  onClick,
  onDragStart,
  onDragOver,
  onDrop,
  tone = "neutral",
  badge,
  icon = null,
  onCopy = () => {},
}) {
  return (
    <button
      className={`fluxio-nav-item ${active ? "active" : ""}`.trim()}
      draggable={draggable}
      onClick={onClick}
      onDragOver={onDragOver}
      onDragStart={onDragStart}
      onDrop={onDrop}
      type="button"
    >
      <div className="fluxio-nav-item-top">
        <div className="fluxio-nav-item-title">
          {icon ? <span aria-hidden="true" className="nav-item-icon">{icon}</span> : null}
          <strong>{title}</strong>
        </div>
        <span className={toneClass(tone)}>{badge || titleizeToken(tone)}</span>
      </div>
      {subtitle ? <p>{subtitle}</p> : null}
      {context ? (
        <div className="nav-context-row">
          <p className="fluxio-nav-context">{context}</p>
          <ActionButton
            onClick={event => {
              event.stopPropagation();
              onCopy(context);
            }}
            type="button"
          >
            Copy
          </ActionButton>
        </div>
      ) : null}
      {stats.length > 0 ? (
        <div className="fluxio-nav-stats">
          {stats.map(item => (
            <span className={`fluxio-nav-stat ${toneClass(item.tone)}`} key={`${title}-${item.label}`}>
              <strong>{item.value}</strong>
              <em>{item.label}</em>
            </span>
          ))}
        </div>
      ) : null}
    </button>
  );
}

function ThreadSection({ item }) {
  return (
    <article className={`thread-section ${toneClass(item.tone || "neutral")}`}>
      <div className="thread-section-top">
        <p>{item.label}</p>
      </div>
      <h3>{item.body}</h3>
      {item.detail ? (
        <details>
          <summary>Technical detail</summary>
          <p>{item.detail}</p>
        </details>
      ) : null}
    </article>
  );
}

function TranscriptMessage({
  item,
  highlighted = false,
  pinned = false,
  showTrace = false,
  onPinNexus = () => {},
  onSteer = () => {},
  onMemory = () => {},
  onValidate = () => {},
}) {
  const role = item.role || "fluxio";
  const roleLabel =
    item.roleLabel ||
    {
      fluxio: "Fluxio",
      operator: "Operator",
      runtime: "Runtime",
      bridge: "Bridge",
      queue: "Needs attention",
      system: "System",
    }[role] ||
    "Fluxio";
  const roleIcon =
    item.roleIcon ||
    {
      fluxio: "◎",
      operator: "◉",
      runtime: "◇",
      bridge: "⌁",
      queue: "!",
      system: "·",
    }[role] ||
    "·";

  return (
    <article
      className={`agent-message role-${role} ${toneClass(item.tone || "neutral")} ${item.emphasis ? "emphasis" : ""} ${item.processMessage ? "process-message" : ""} ${highlighted ? "highlighted" : ""} ${pinned ? "pinned" : ""}`.trim()}
      id={item.id}
    >
      <div className="agent-message-top">
        <div className="agent-message-role">
          <span aria-hidden="true" className="agent-message-avatar">{roleIcon}</span>
          <strong>{roleLabel}</strong>
        </div>
        {item.meta ? <span>{item.meta}</span> : null}
      </div>
      {item.label ? <p className="agent-message-label">{item.label}</p> : null}
      {item.title ? <h3>{item.title}</h3> : null}
      {item.detail ? <p>{item.detail}</p> : null}
      {item.technicalDetail ? (
        <details className="agent-message-details" open={showTrace}>
          <summary>{item.technicalSummary || "Technical detail"}</summary>
          <p>{item.technicalDetail}</p>
        </details>
      ) : null}
      {item.chips?.length ? (
        <div className="agent-message-chips">
          {item.chips.map(chip => (
            <span className="mini-pill muted" key={`${item.id}-${chip}`}>
              {chip}
            </span>
          ))}
        </div>
      ) : null}
      <div className="agent-message-actions">
        {(item.role === "queue" || item.tone === "bad" || item.processMessage) ? (
          <ActionButton onClick={() => onValidate(item)} type="button">
            Validate
          </ActionButton>
        ) : null}
        <ActionButton onClick={() => onSteer(item)} type="button">
          Steer
        </ActionButton>
        <ActionButton onClick={() => onMemory(item)} type="button">
          Memory
        </ActionButton>
        <ActionButton onClick={() => onPinNexus(item.id)} type="button">
          {pinned ? "Unpin nexus" : "Pin nexus"}
        </ActionButton>
      </div>
    </article>
  );
}

function AgentChatMessage({ item, highlighted = false, onFocusTrace = () => {} }) {
  const isUser = item.role === "operator";
  const speakerLabel = isUser ? "You" : item.roleLabel || "Fluxio";
  const speakerIcon = isUser ? "◉" : item.roleIcon || "◇";
  const secondaryText =
    !isUser && item.detail && item.detail !== item.title && item.detail !== item.meta
      ? item.detail
      : "";
  const hasTraceDetail = Boolean(item.technicalDetail || item.traceOnly);

  return (
    <article
      className={`agent-chat-message ${isUser ? "user" : "assistant"} ${toneClass(item.tone || "neutral")} ${highlighted ? "highlighted" : ""}`.trim()}
      id={item.id}
    >
      <div className="agent-chat-message-head">
        <div className="agent-chat-speaker">
          <span aria-hidden="true" className="agent-chat-avatar">{speakerIcon}</span>
          <strong>{speakerLabel}</strong>
        </div>
        {item.meta ? <span>{item.meta}</span> : null}
      </div>
      <div className="agent-chat-bubble">
        {item.label && !isUser ? <span className="agent-chat-label">{item.label}</span> : null}
        {item.title ? <p className="agent-chat-primary">{item.title}</p> : null}
        {secondaryText ? <p className="agent-chat-secondary">{secondaryText}</p> : null}
        {item.chips?.length ? (
          <div className="agent-chat-chips">
            {item.chips.slice(0, 4).map(chip => (
              <span className="mini-pill muted" key={`${item.id}-${chip}`}>
                {chip}
              </span>
            ))}
          </div>
        ) : null}
      </div>
      {!isUser && hasTraceDetail ? (
        <div className="agent-chat-actions">
          <ActionButton onClick={() => onFocusTrace(item.id)} type="button">
            Open trace
          </ActionButton>
        </div>
      ) : null}
    </article>
  );
}

function DrawerToggle({ active, label, count, tone, onClick }) {
  return (
    <button className={`drawer-toggle ${active ? "active" : ""}`.trim()} onClick={onClick} type="button">
      <span>{label}</span>
      <strong className={toneClass(tone)}>{count > 0 ? count : ""}</strong>
    </button>
  );
}

function TopbarShortcut({ active = false, label, onClick, tone = "neutral" }) {
  return (
    <button
      className={`topbar-shortcut ${active ? "active" : ""} ${toneClass(tone)}`.trim()}
      onClick={onClick}
      type="button"
    >
      {label}
    </button>
  );
}

function WindowedList({
  className = "",
  estimatedItemHeight = 140,
  items = [],
  overscan = 4,
  renderItem,
}) {
  const hostRef = useRef(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(0);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) {
      return undefined;
    }
    const syncSize = () => {
      setViewportHeight(host.clientHeight || 0);
    };
    syncSize();
    const resizeObserver = new ResizeObserver(syncSize);
    resizeObserver.observe(host);
    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  if (!Array.isArray(items) || items.length === 0) {
    return <div className={`windowed-list ${className}`.trim()} ref={hostRef} />;
  }

  if (items.length < WINDOWED_THRESHOLD) {
    return (
      <div className={`windowed-list ${className}`.trim()} ref={hostRef}>
        {items.map((item, index) => renderItem(item, index))}
      </div>
    );
  }

  const safeHeight = Math.max(1, estimatedItemHeight);
  const visibleCount = Math.ceil((viewportHeight || safeHeight * 4) / safeHeight);
  const startIndex = Math.max(0, Math.floor(scrollTop / safeHeight) - overscan);
  const endIndex = Math.min(items.length, startIndex + visibleCount + overscan * 2);
  const topPad = startIndex * safeHeight;
  const bottomPad = Math.max(0, (items.length - endIndex) * safeHeight);

  return (
    <div
      className={`windowed-list ${className}`.trim()}
      onScroll={event => setScrollTop(event.currentTarget.scrollTop)}
      ref={hostRef}
    >
      <div style={{ height: `${topPad}px` }} />
      {items.slice(startIndex, endIndex).map((item, index) =>
        renderItem(item, startIndex + index),
      )}
      <div style={{ height: `${bottomPad}px` }} />
    </div>
  );
}

function MenuButton({ label, onClick }) {
  return (
    <button className="app-menu-button" onClick={onClick} type="button">
      {label}
    </button>
  );
}

function GlobalRailButton({ active = false, icon = null, label, onClick, subtle = false }) {
  return (
    <button
      className={`global-rail-button ${active ? "active" : ""} ${subtle ? "subtle" : ""}`.trim()}
      onClick={onClick}
      type="button"
    >
      {icon ? <span aria-hidden="true" className="global-rail-icon">{icon}</span> : null}
      <span>{label}</span>
    </button>
  );
}

function missionActionAvailable(mission, action) {
  if (!mission) {
    return false;
  }
  if (action === "pause") {
    return !["completed", "failed"].includes(mission.state?.status || "");
  }
  if (action === "resume") {
    return (
      mission.missionLoop?.continuityState === "resume_available" ||
      ["queued", "blocked", "verification_failed", "needs_approval"].includes(
        mission.state?.status || "",
      )
    );
  }
  return true;
}

function listLabel(value) {
  if (!value) {
    return "No item";
  }
  return String(value);
}

function pathLeaf(value) {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }
  const parts = text.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] || text;
}

function saveableRouteOverrides(routeOverrides) {
  return asList(routeOverrides)
    .filter(item => item?.model?.trim())
    .map(item => ({
      role: item.role,
      provider: item.provider,
      model: item.model.trim(),
      ...(item.effort && item.effort !== "default" ? { effort: item.effort } : {}),
    }));
}

function updateRouteOverride(routeOverrides, role, patch) {
  return asList(routeOverrides).map(item =>
    item.role === role
      ? {
          ...item,
          ...patch,
        }
      : item,
  );
}

function profileFormFromWorkspace(workspace, fallbackProfile) {
  const overrides = Array.isArray(workspace?.route_overrides) ? workspace.route_overrides : [];
  const existingByRole = new Map(overrides.map(item => [String(item.role || "").toLowerCase(), item]));
  return {
    userProfile: workspace?.user_profile || fallbackProfile || "builder",
    preferredHarness: workspace?.preferred_harness || "fluxio_hybrid",
    routingStrategy: workspace?.routing_strategy || "profile_default",
    autoOptimizeRouting: Boolean(workspace?.auto_optimize_routing),
    openaiCodexAuthMode: workspace?.openai_codex_auth_mode || "none",
    minimaxAuthMode: workspace?.minimax_auth_mode || "none",
    commitMessageStyle: workspace?.commit_message_style || "scoped",
    executionTargetPreference: workspace?.execution_target_preference || "profile_default",
    routeOverrides: ROUTE_ROLE_OPTIONS.map(role => {
      const item = existingByRole.get(role) || {};
      return {
        role,
        provider: item.provider || "openai",
        model: item.model || "",
        effort: item.effort || "default",
      };
    }),
  };
}

function createSessionEntry(entry) {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    createdAt: new Date().toISOString(),
    ...entry,
  };
}

function deltaDetail(row) {
  const detailSources = [
    row?.detail,
    row?.metadata?.detail,
    row?.metadata?.reason,
    row?.metadata?.pauseReason,
    row?.metadata?.autopilotStatus,
    row?.metadata?.status,
    row?.data?.detail,
    row?.data?.decision,
    row?.data?.request_id,
  ];
  return detailSources.find(value => value) || "";
}

const OPERATOR_STEERING_PREFIXES = [
  "runtime preference:",
  "current mission phase:",
  "route preference for",
  "if the openai route is active,",
];

function extractOperatorSteeringHints(block) {
  return String(block || "")
    .split(/(?<=\.)\s+(?=[A-Z])|[\n]+/)
    .map(item => item.trim())
    .filter(Boolean)
    .filter(item =>
      OPERATOR_STEERING_PREFIXES.some(prefix => item.toLowerCase().startsWith(prefix)),
    );
}

function splitOperatorSteeringMessage(value) {
  const raw = String(value || "").replace(/\r\n?/g, "\n").trim();
  if (!raw) {
    return { visibleText: "", steeringHints: [] };
  }

  const blocks = raw.split(/\n\s*\n/).map(item => item.trim()).filter(Boolean);
  if (blocks.length > 1) {
    const steeringHints = extractOperatorSteeringHints(blocks[0]);
    if (steeringHints.length > 0) {
      return {
        visibleText: blocks.slice(1).join("\n\n").trim() || raw,
        steeringHints,
      };
    }
  }

  const steeringHints = [];
  const visibleLines = [];
  let inBody = false;
  for (const rawLine of raw.split("\n")) {
    const line = rawLine.trim();
    if (!line) {
      if (inBody && visibleLines[visibleLines.length - 1] !== "") {
        visibleLines.push("");
      }
      continue;
    }
    const steeringLine =
      !inBody &&
      OPERATOR_STEERING_PREFIXES.some(prefix => line.toLowerCase().startsWith(prefix));
    if (steeringLine) {
      steeringHints.push(line);
      continue;
    }
    inBody = true;
    visibleLines.push(line);
  }

  return {
    visibleText: visibleLines.join("\n").trim() || raw,
    steeringHints,
  };
}

function isRuntimeRouteMetaKind(kind) {
  return [
    "runtime.phase_entered",
    "runtime.route_switch_reason",
    "runtime.handoff",
    "runtime.route_contract",
  ].includes(String(kind || "").toLowerCase());
}

function controlRoomDeltaToLiveItem(payload, mission, delegatedSessions = []) {
  const row = payload?.row;
  const source = payload?.source || "delta";
  if (!row || !mission) {
    return null;
  }

  if (source === "mission_event") {
    if (row.mission_id !== mission.mission_id) {
      return null;
    }
    const kind = row.kind || "mission.event";
    const isOperatorFollowUp = kind === "mission.follow_up";
    const operatorPrompt = isOperatorFollowUp
      ? splitOperatorSteeringMessage(row.message || "")
      : null;
    return {
      id: `mission-${row.mission_id}-${row.timestamp || payload.detectedAt}-${kind}-${row.message || "event"}`,
      kind,
      role: isOperatorFollowUp ? "operator" : kind === "mission.approval" ? "queue" : "system",
      runtimeId: row.metadata?.runtimeId || row.metadata?.runtime_id || "",
      roleLabel:
        isOperatorFollowUp
          ? "Operator"
          : kind === "mission.approval"
            ? "Needs attention"
            : "Fluxio",
      roleIcon:
        isOperatorFollowUp
          ? "◉"
          : kind === "mission.approval"
            ? "!"
            : "·",
      label: titleizeToken(kind),
      title: operatorPrompt?.visibleText || row.message || "Mission event",
      detail:
        operatorPrompt?.steeringHints?.join(" · ") ||
        deltaDetail(row),
      meta: timestampLabel(row.timestamp || payload.detectedAt),
      timestampRaw: row.timestamp || payload.detectedAt,
      tone:
        kind === "mission.approval"
          ? "warn"
          : /failed|error/i.test(`${kind} ${row.message || ""}`)
            ? "bad"
            : "neutral",
      technicalDetail:
        operatorPrompt?.steeringHints?.length > 0
          ? operatorPrompt.steeringHints.join("\n")
          : "",
      technicalSummary:
        operatorPrompt?.steeringHints?.length > 0 ? "Routing note" : "",
      chatPreferred: isOperatorFollowUp,
      chips: [
        row.metadata?.runtimeId ? runtimeLabel(row.metadata.runtimeId) : "",
        row.metadata?.queuedForRuntime ? "Queued for runtime" : "",
      ].filter(Boolean),
    };
  }

  if (source === "runtime_event") {
    const delegatedId = row.delegated_id || row.delegatedId || "";
    const delegatedIds = new Set(
      delegatedSessions.map(item => item?.delegated_id).filter(Boolean),
    );
    if (delegatedIds.size > 0 && delegatedId && !delegatedIds.has(delegatedId)) {
      return null;
    }
    if (delegatedIds.size > 0 && !delegatedId) {
      return null;
    }
    const kind = row.kind || "runtime.event";
    const processMessage = isTraceRuntimeKind(kind);
    const heartbeat = isHeartbeatRuntimeKind(kind);
    const normalizedKind = String(kind).toLowerCase();
    const routeSwitch = normalizedKind === "runtime.route_contract";
    const phaseEntered = normalizedKind === "runtime.phase_entered";
    const routeSwitchReason = normalizedKind === "runtime.route_switch_reason";
    const handoffEvent = normalizedKind === "runtime.handoff";
    const detail = deltaDetail(row);
    const operatorPrompt =
      normalizedKind === "operator.followup"
        ? splitOperatorSteeringMessage(row.message || "")
        : null;
    return {
      id: `runtime-${delegatedId || mission.mission_id}-${row.event_id || row.created_at || payload.detectedAt}-${kind}`,
      kind,
      role: kind === "operator.followup" ? "operator" : "runtime",
      runtimeId: row.runtime_id || mission.runtime_id,
      roleLabel:
        kind === "operator.followup" ? "Operator" : runtimeLabel(row.runtime_id || mission.runtime_id),
      roleIcon:
        kind === "operator.followup"
          ? "◉"
          : row.runtime_id === "hermes"
            ? "⬢"
            : "◇",
      label: phaseEntered
        ? "Phase entered"
        : routeSwitchReason
          ? "Route switch reason"
          : handoffEvent
            ? "Runtime handoff"
            : processMessage
        ? "Process message"
        : heartbeat
          ? "Runtime heartbeat"
          : titleizeToken(kind),
      title: operatorPrompt?.visibleText || row.message || "Runtime event",
      detail:
        (operatorPrompt?.steeringHints?.join(" · ") ||
        (phaseEntered
          ? `${titleizeToken(row?.data?.phase || "execute")} phase via ${titleizeToken(
              row?.data?.role || "route",
            )}${row?.data?.provider ? ` · ${titleizeToken(row.data.provider)}` : ""}${row?.data?.model ? ` · ${row.data.model}` : ""}`
          : routeSwitchReason
            ? detail || row.message || "Route switch reason emitted by runtime supervision."
            : handoffEvent
              ? detail || row?.data?.reason || "Runtime handoff emitted by supervision."
              : routeSwitch
          ? `${titleizeToken(row?.data?.phase || "execute")} phase · ${titleizeToken(
              row?.data?.role || "route",
            )} route`
          : detail) ||
        (processMessage
          ? `${runtimeLabel(row.runtime_id || mission.runtime_id)} emitted process output.`
          : heartbeat
            ? "Heartbeat telemetry from the delegated runtime lane."
            : "")),
      meta: timestampLabel(row.created_at || payload.detectedAt),
      timestampRaw: row.created_at || payload.detectedAt,
      tone:
        row.status === "failed"
          ? "bad"
          : /approval|waiting/i.test(`${kind} ${row.status || ""}`)
            ? "warn"
            : "neutral",
      technicalDetail:
        operatorPrompt?.steeringHints?.length > 0
          ? operatorPrompt.steeringHints.join("\n")
          : processMessage && detail && detail !== row.message
          ? detail
          : row?.metadata?.trace || row?.data?.trace || "",
      technicalSummary:
        operatorPrompt?.steeringHints?.length > 0
          ? "Routing note"
          : processMessage
            ? "Thinking trace"
            : "",
      processMessage,
      chatPreferred:
        normalizedKind === "operator.followup" ||
        (processMessage && !isRuntimeRouteMetaKind(kind)),
      traceOnly: isRuntimeRouteMetaKind(kind),
      heartbeat,
      emphasis:
        processMessage ||
        phaseEntered ||
        routeSwitchReason ||
        handoffEvent ||
        row.status === "failed" ||
        /approval|blocked|error/i.test(`${kind} ${row.message || ""}`),
      chips: [
        row.runtime_id ? runtimeLabel(row.runtime_id) : "",
        routeSwitch && row?.data?.phase ? titleizeToken(row.data.phase) : "",
        routeSwitch && row?.data?.role ? titleizeToken(row.data.role) : "",
        phaseEntered && row?.data?.provider ? titleizeToken(row.data.provider) : "",
        phaseEntered && row?.data?.model ? row.data.model : "",
        routeSwitchReason && row?.data?.reason ? row.data.reason : "",
        row.status ? titleizeToken(row.status) : "",
      ].filter(Boolean),
    };
  }

  return null;
}

function inferSurfaceFromAction(action) {
  if (action?.surface) {
    return action.surface;
  }
  const commandSurface = action?.commandSurface || "";
  if (commandSurface.startsWith("git.") || commandSurface.startsWith("deploy.")) {
    return "git";
  }
  if (commandSurface.startsWith("validate.")) {
    return "validate";
  }
  return "setup";
}

export function FluxioShellApp({ reportUiAction = () => {} }) {
  const searchParams = useMemo(() => new URLSearchParams(window.location.search), []);
  const storedUiMode = searchParams.get("mode") || localStorage.getItem(STORAGE_KEYS.uiMode) || "agent";
  const storedChatId = localStorage.getItem(STORAGE_KEYS.telegramChatId) || "";
  const storedPreviewMode =
    searchParams.get("fixture") || localStorage.getItem(STORAGE_KEYS.previewMode) || "live";
  const storedLiveSyncSeconds = localStorage.getItem(STORAGE_KEYS.liveSyncSeconds) || "off";
  const storedCodeExecutionEnabled =
    localStorage.getItem(STORAGE_KEYS.codeExecutionEnabled) === "true";
  const storedCodeExecutionMemory =
    localStorage.getItem(STORAGE_KEYS.codeExecutionMemory) || "4g";
  const storedWorkspaceSearch = localStorage.getItem(STORAGE_KEYS.workspaceSearch) || "";
  const storedMissionSearch = localStorage.getItem(STORAGE_KEYS.missionSearch) || "";
  const storedWorkspaceOrder = loadStoredJson(STORAGE_KEYS.workspaceOrder, []);
  const storedMissionOrder = loadStoredJson(STORAGE_KEYS.missionOrder, []);
  const storedSplitViewEnabled = localStorage.getItem(STORAGE_KEYS.splitViewEnabled) === "true";
  const storedSplitMissionId = localStorage.getItem(STORAGE_KEYS.splitMissionId) || "";
  const storedLocalTasks = loadStoredJson(STORAGE_KEYS.localTasks, []);
  const storedMemoryPolicy = loadStoredJson(STORAGE_KEYS.memoryPolicy, DEFAULT_MEMORY_POLICY);
  const storedMemoryStore = loadStoredJson(STORAGE_KEYS.memoryStore, {
    workspace: {},
    mission: {},
  });
  const storedDebugEvents = loadStoredJson(STORAGE_KEYS.debugEvents, []);
  const storedUiState = loadStoredJson(STORAGE_KEYS.persistedUiState, {});

  const [uiMode, setUiMode] = useState(
    ["agent", "builder"].includes(storedUiMode) ? storedUiMode : "agent",
  );
  const [previewMode, setPreviewMode] = useState(
    FIXTURE_OPTIONS.some(option => option.id === storedPreviewMode) ? storedPreviewMode : "live",
  );
  const [liveSyncSeconds, setLiveSyncSeconds] = useState(
    LIVE_SYNC_OPTIONS.some(option => option.value === storedLiveSyncSeconds)
      ? storedLiveSyncSeconds
      : "off",
  );
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState(null);
  const [selectedMissionId, setSelectedMissionId] = useState(null);
  const [showWorkspaceDialog, setShowWorkspaceDialog] = useState(false);
  const [showMissionDialog, setShowMissionDialog] = useState(false);
  const [showEscalationDialog, setShowEscalationDialog] = useState(false);
  const [workspaceForm, setWorkspaceForm] = useState(DEFAULT_WORKSPACE_FORM);
  const [missionForm, setMissionForm] = useState(DEFAULT_MISSION_FORM);
  const [workspaceProfileForm, setWorkspaceProfileForm] = useState(
    profileFormFromWorkspace(null, "builder"),
  );
  const [skillStudioFilter, setSkillStudioFilter] = useState("all");
  const [skillStudioQuery, setSkillStudioQuery] = useState("");
  const [telegramChatId, setTelegramChatId] = useState(storedChatId);
  const [telegramBotToken, setTelegramBotToken] = useState("");
  const [openClawGatewayUrl, setOpenClawGatewayUrl] = useState(DEFAULT_OPENCLAW_GATEWAY_URL);
  const [openClawGatewayToken, setOpenClawGatewayToken] = useState("");
  const [providerSecretDrafts, setProviderSecretDrafts] = useState(
    Object.fromEntries(PROVIDER_SECRET_OPTIONS.map(item => [item.id, ""])),
  );
  const [codeExecutionEnabled, setCodeExecutionEnabled] = useState(storedCodeExecutionEnabled);
  const [codeExecutionMemory, setCodeExecutionMemory] = useState(
    CODE_EXECUTION_MEMORY_OPTIONS.some(option => option.value === storedCodeExecutionMemory)
      ? storedCodeExecutionMemory
      : "4g",
  );
  const [lastPushReason, setLastPushReason] = useState("");
  const [liveSyncSuspended, setLiveSyncSuspended] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [activeDrawer, setActiveDrawer] = useState(storedUiState.activeDrawer || null);
  const [operatorDraft, setOperatorDraft] = useState("");
  const [operatorNotes, setOperatorNotes] = useState(storedUiState.operatorNotes || []);
  const [liveControlEvents, setLiveControlEvents] = useState(storedUiState.liveControlEvents || []);
  const [operatorAttachments, setOperatorAttachments] = useState([]);
  const [agentRouteRole, setAgentRouteRole] = useState("executor");
  const [agentRuntimeFocus, setAgentRuntimeFocus] = useState("all");
  const [showThinkingTrace, setShowThinkingTrace] = useState(true);
  const [pinnedNexusIds, setPinnedNexusIds] = useState(storedUiState.pinnedNexusIds || []);
  const [highlightedTurnId, setHighlightedTurnId] = useState("");
  const [selectedReviewTargetId, setSelectedReviewTargetId] = useState(
    storedUiState.selectedReviewTargetId || "",
  );
  const [workspaceSearchQuery, setWorkspaceSearchQuery] = useState(storedWorkspaceSearch);
  const [missionSearchQuery, setMissionSearchQuery] = useState(storedMissionSearch);
  const [workspaceOrder, setWorkspaceOrder] = useState(
    Array.isArray(storedWorkspaceOrder) ? storedWorkspaceOrder : [],
  );
  const [missionOrder, setMissionOrder] = useState(
    Array.isArray(storedMissionOrder) ? storedMissionOrder : [],
  );
  const [splitViewEnabled, setSplitViewEnabled] = useState(storedSplitViewEnabled);
  const [splitMissionId, setSplitMissionId] = useState(storedSplitMissionId);
  const [localTasks, setLocalTasks] = useState(
    Array.isArray(storedLocalTasks) ? storedLocalTasks : [],
  );
  const [taskForm, setTaskForm] = useState(DEFAULT_TASK_FORM);
  const [memoryPolicy, setMemoryPolicy] = useState({
    ...DEFAULT_MEMORY_POLICY,
    ...(storedMemoryPolicy || {}),
  });
  const [memoryStore, setMemoryStore] = useState({
    workspace: storedMemoryStore?.workspace || {},
    mission: storedMemoryStore?.mission || {},
  });
  const [debugEvents, setDebugEvents] = useState(
    Array.isArray(storedDebugEvents) ? storedDebugEvents.slice(-MAX_DEBUG_LOG) : [],
  );
  const [data, setData] = useState({
    snapshot: null,
    onboarding: null,
    pendingApprovals: [],
    pendingQuestions: [],
    telegramReady: false,
    previewMeta: null,
    openClawStatus: null,
    openClawHasToken: false,
    openClawMessages: [],
    providerSecretPresence: {},
  });

  const mountedRef = useRef(true);
  const currentMissionRef = useRef(null);
  const currentDelegatedSessionsRef = useRef([]);
  const transcriptCacheRef = useRef({});
  const refreshPromiseRef = useRef(null);
  const queuedRefreshReasonRef = useRef("");
  const authPromptedRef = useRef(false);
  const { items: toasts, push: pushToast } = useToastQueue();

  const markAction = useCallback(
    action => {
      reportUiAction(action);
    },
    [reportUiAction],
  );

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.uiMode, uiMode);
  }, [uiMode]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.previewMode, previewMode);
  }, [previewMode]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.liveSyncSeconds, liveSyncSeconds);
  }, [liveSyncSeconds]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.telegramChatId, telegramChatId);
  }, [telegramChatId]);

  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEYS.codeExecutionEnabled,
      codeExecutionEnabled ? "true" : "false",
    );
  }, [codeExecutionEnabled]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.codeExecutionMemory, codeExecutionMemory);
  }, [codeExecutionMemory]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.workspaceSearch, workspaceSearchQuery);
  }, [workspaceSearchQuery]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.missionSearch, missionSearchQuery);
  }, [missionSearchQuery]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.splitViewEnabled, splitViewEnabled ? "true" : "false");
  }, [splitViewEnabled]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.splitMissionId, splitMissionId || "");
  }, [splitMissionId]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.workspaceOrder, JSON.stringify(workspaceOrder));
  }, [workspaceOrder]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.missionOrder, JSON.stringify(missionOrder));
  }, [missionOrder]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.localTasks, JSON.stringify(localTasks));
  }, [localTasks]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.memoryPolicy, JSON.stringify(memoryPolicy));
  }, [memoryPolicy]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.memoryStore, JSON.stringify(memoryStore));
  }, [memoryStore]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.debugEvents, JSON.stringify(debugEvents.slice(-MAX_DEBUG_LOG)));
  }, [debugEvents]);

  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEYS.persistedUiState,
      JSON.stringify({
        activeDrawer,
        pinnedNexusIds,
        selectedReviewTargetId,
        operatorNotes: operatorNotes.slice(-40),
        liveControlEvents: liveControlEvents.slice(-60),
      }),
    );
  }, [activeDrawer, liveControlEvents, operatorNotes, pinnedNexusIds, selectedReviewTargetId]);

  useEffect(() => {
    return subscribeBackendCalls(event => {
      setDebugEvents(current =>
        [event, ...current].slice(0, MAX_DEBUG_LOG),
      );
    });
  }, []);

  useEffect(() => {
    const onError = event => {
      setDebugEvents(current =>
        [
          {
            id: `window-error-${Date.now()}-${Math.random().toString(36).slice(2)}`,
            kind: "window.error",
            at: new Date().toISOString(),
            message: event.message || "Unhandled browser error",
            source: event.filename || "",
            line: event.lineno || 0,
            column: event.colno || 0,
          },
          ...current,
        ].slice(0, MAX_DEBUG_LOG),
      );
    };
    const onUnhandled = event => {
      setDebugEvents(current =>
        [
          {
            id: `window-unhandled-${Date.now()}-${Math.random().toString(36).slice(2)}`,
            kind: "window.unhandledrejection",
            at: new Date().toISOString(),
            message: String(event.reason || "Unhandled rejection"),
          },
          ...current,
        ].slice(0, MAX_DEBUG_LOG),
      );
    };
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onUnhandled);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onUnhandled);
    };
  }, []);

  useEffect(() => {
    setLiveControlEvents([]);
  }, [previewMode, selectedMissionId]);

  const performRefresh = useCallback(
    async (reason = "manual") => {
      markAction(`refresh:${reason}`);
      setIsRefreshing(true);
      try {
        if (previewMode !== "live") {
          const fixturePayload = buildFixtureSnapshot(previewMode);
          if (!fixturePayload) {
            setPreviewMode("live");
            return;
          }
          setData(current => ({
            ...current,
            snapshot: fixturePayload.snapshot,
            onboarding: fixturePayload.onboarding,
            pendingApprovals: fixturePayload.pendingApprovals,
            pendingQuestions: fixturePayload.pendingQuestions,
            telegramReady: fixturePayload.telegramReady,
            previewMeta: fixturePayload.meta,
            openClawStatus: null,
            openClawHasToken: false,
            openClawMessages: [],
            providerSecretPresence: {},
          }));
          return;
        }

        if (!hasTauriBackend()) {
          const fallbackPayload = buildFixtureSnapshot("live_review");
          setData(current => ({
            ...current,
            snapshot: fallbackPayload.snapshot,
            onboarding: fallbackPayload.onboarding,
            pendingApprovals: fallbackPayload.pendingApprovals,
            pendingQuestions: fallbackPayload.pendingQuestions,
            telegramReady: fallbackPayload.telegramReady,
            previewMeta: {
              id: "fallback",
              name: "Local Fallback",
              description:
                "Tauri backend is unavailable, so Fluxio is showing a local supervision fixture.",
            },
            openClawStatus: null,
            openClawHasToken: false,
            openClawMessages: [],
          }));
          return;
        }

        const [
          snapshot,
          pendingApprovals,
          pendingQuestions,
          telegramReady,
          openClawStatus,
          openClawHasToken,
          providerSecretPresencePrimary,
        ] =
          await Promise.all([
            callBackend(
              "get_control_room_snapshot_command",
              { payload: { root: null } },
              { throwOnError: true },
            ),
            callBackend("list_pending_approvals"),
            callBackend("list_pending_questions"),
            callBackend("has_telegram_bot_token_command"),
            callBackend("get_openclaw_status"),
            callBackend("has_openclaw_gateway_token"),
            callBackend("get_provider_secret_presence_command", {
              providerIds: PROVIDER_SECRET_OPTIONS.map(item => item.id),
            }),
          ]);

        if (!mountedRef.current) {
          return;
        }

        const providerSecretPresence =
          (snapshot?.providerSecretPresence && typeof snapshot.providerSecretPresence === "object"
            ? snapshot.providerSecretPresence
            : null) ||
          providerSecretPresencePrimary ||
          (await callBackend("get_provider_secret_presence_command", {
            provider_ids: PROVIDER_SECRET_OPTIONS.map(item => item.id),
          })) ||
          {};

        setData(current => ({
          ...current,
          snapshot,
          onboarding: snapshot?.onboarding || current.onboarding || null,
          pendingApprovals: Array.isArray(pendingApprovals) ? pendingApprovals : [],
          pendingQuestions: Array.isArray(pendingQuestions) ? pendingQuestions : [],
          telegramReady: Boolean(telegramReady),
          previewMeta: null,
          openClawStatus: openClawStatus || null,
          openClawHasToken: Boolean(openClawHasToken),
          providerSecretPresence:
            providerSecretPresence && typeof providerSecretPresence === "object"
              ? providerSecretPresence
              : {},
        }));

        if (reason !== "initialize") {
          setLastPushReason(reason);
        }
      } catch (error) {
        pushToast(`Refresh failed: ${error}`, "error");
      } finally {
        if (mountedRef.current) {
          setIsRefreshing(false);
        }
      }
    },
    [markAction, previewMode, pushToast],
  );

  const refreshAll = useCallback(
    async (reason = "manual") => {
      const normalizedReason = String(reason || "manual");
      if (refreshPromiseRef.current) {
        queuedRefreshReasonRef.current = normalizedReason;
        return refreshPromiseRef.current;
      }

      const refreshPromise = (async () => {
        let nextReason = normalizedReason;
        while (nextReason) {
          queuedRefreshReasonRef.current = "";
          await performRefresh(nextReason);
          nextReason = queuedRefreshReasonRef.current;
        }
      })().finally(() => {
        if (refreshPromiseRef.current === refreshPromise) {
          refreshPromiseRef.current = null;
        }
      });

      refreshPromiseRef.current = refreshPromise;
      return refreshPromise;
    },
    [performRefresh],
  );

  useEffect(() => {
    void refreshAll("initialize");
  }, [refreshAll]);

  useEffect(() => {
    const workspaces = data.snapshot?.workspaces || [];
    setSelectedWorkspaceId(current =>
      workspaces.some(item => item.workspace_id === current)
        ? current
        : workspaces[0]?.workspace_id || null,
    );
  }, [data.snapshot]);

  useEffect(() => {
    const missions = data.snapshot?.missions || [];
    setSelectedMissionId(current =>
      missions.some(item => item.mission_id === current)
        ? current
        : missions[missions.length - 1]?.mission_id || null,
    );
  }, [data.snapshot]);

  useEffect(() => {
    const handleVisibility = () => {
      const hidden = document.visibilityState !== "visible";
      const shouldSuspend = previewMode === "live" && liveSyncSeconds !== "off" && hidden;
      setLiveSyncSuspended(shouldSuspend);
      if (!hidden && previewMode === "live" && liveSyncSeconds !== "off") {
        void refreshAll("visibility-resume");
      }
    };

    handleVisibility();
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [liveSyncSeconds, previewMode, refreshAll]);

  useEffect(() => {
    if (previewMode !== "live" || liveSyncSeconds === "off" || liveSyncSuspended) {
      return undefined;
    }

    const interval = window.setInterval(() => {
      void refreshAll("live-sync");
    }, Number(liveSyncSeconds) * 1000);

    return () => {
      window.clearInterval(interval);
    };
  }, [liveSyncSeconds, liveSyncSuspended, previewMode, refreshAll]);

  useEffect(() => {
    if (previewMode !== "live" || !hasTauriBackend()) {
      return undefined;
    }

    let cancelled = false;
    const unlisteners = [];
    const registerListener = async (eventName, handler) => {
      try {
        const unlisten = await listen(eventName, handler);
        if (cancelled) {
          unlisten();
          return;
        }
        unlisteners.push(unlisten);
      } catch {
        return undefined;
      }
      return undefined;
    };

    void registerListener("control-room://changed", event => {
      const reason = event?.payload?.reason || "backend-event";
      setLastPushReason(reason);
      void refreshAll(reason);
    });

    void registerListener("control-room://delta", event => {
      const reason = event?.payload?.source || "backend-delta";
      setLastPushReason(reason);
      const liveItem = controlRoomDeltaToLiveItem(
        event?.payload,
        currentMissionRef.current,
        currentDelegatedSessionsRef.current,
      );
      if (liveItem) {
        setLiveControlEvents(current =>
          [liveItem, ...current.filter(entry => entry.id !== liveItem.id)].slice(0, 24),
        );
      }
    });

    void registerListener("openclaw://status", event => {
      setData(current => ({
        ...current,
        openClawStatus: event?.payload || current.openClawStatus,
      }));
    });

    void registerListener("openclaw://message", event => {
      const content = event?.payload?.content;
      if (!content) {
        return;
      }
      setData(current => ({
        ...current,
        openClawMessages: [
          ...current.openClawMessages,
          createSessionEntry({
            title: "OpenClaw message",
            detail: String(content),
            meta: "Gateway message",
            tone: "neutral",
          }),
        ].slice(-16),
      }));
    });

    return () => {
      cancelled = true;
      for (const unlisten of unlisteners) {
        if (typeof unlisten === "function") {
          unlisten();
        }
      }
    };
  }, [previewMode, refreshAll]);

  const snapshot = data.snapshot || {};
  const onboarding = data.onboarding || snapshot.onboarding || {};
  const setupHealth = snapshot.setupHealth || onboarding.setupHealth || {};
  const workspaces = snapshot.workspaces || [];
  const missions = snapshot.missions || [];
  const inboxItems = snapshot.inbox || [];
  const initialLiveSnapshotPending =
    previewMode === "live" && data.snapshot === null && data.previewMeta === null;

  const workspace = useMemo(
    () => selectedWorkspace(snapshot, selectedWorkspaceId),
    [selectedWorkspaceId, snapshot],
  );
  const mission = useMemo(
    () => selectedMission(snapshot, selectedMissionId),
    [selectedMissionId, snapshot],
  );
  const workspaceMissions = useMemo(
    () =>
      missions.filter(item =>
        selectedWorkspaceId ? item.workspace_id === selectedWorkspaceId : true,
      ),
    [missions, selectedWorkspaceId],
  );

  const profileId = activeProfileId(snapshot, onboarding, workspace, mission);
  const profileParams = currentProfileParameters(snapshot, profileId, workspace);

  const viewModel = useMemo(
    () =>
      buildMissionControlModel({
        mission,
        workspace,
        setupHealth,
        snapshot,
        pendingQuestions: data.pendingQuestions,
        pendingApprovals: data.pendingApprovals,
        telegramReady: data.telegramReady,
        profileId,
        profileParams,
        inbox: inboxItems,
        previewMode,
        uiMode,
        lastPushReason,
        isRefreshing,
        liveSyncSeconds,
        liveSyncSuspended,
      }),
    [
      data.pendingApprovals,
      data.pendingQuestions,
      data.telegramReady,
      inboxItems,
      isRefreshing,
      lastPushReason,
      liveSyncSeconds,
      liveSyncSuspended,
      mission,
      previewMode,
      profileId,
      profileParams,
      setupHealth,
      snapshot,
      uiMode,
      workspace,
    ],
  );

  const missionOptions = workspaceMissions.length > 0 ? workspaceMissions : missions;
  const quickSetupActions = useMemo(
    () => [...(setupHealth.repairActions || []), ...(setupHealth.globalActions || [])].slice(0, 3),
    [setupHealth.globalActions, setupHealth.repairActions],
  );
  const missionStatus = mission?.state?.status || "";
  const agentBlockedState = useMemo(() => {
    const approvalCount = asList(mission?.proof?.pending_approvals).length + asList(data.pendingApprovals).length;
    const questionCount = asList(data.pendingQuestions).length;
    const verificationFailureCount = asList(mission?.state?.verification_failures).length;
    const continuityState =
      mission?.missionLoop?.continuityState ||
      mission?.missionLoop?.timeBudget?.status ||
      mission?.missionLoop?.time_budget?.status ||
      "";
    const hasApprovalBoundary = approvalCount > 0;
    const hasQuestionBoundary = questionCount > 0;
    const hasVerificationFailure =
      verificationFailureCount > 0 || missionStatus === "verification_failed";
    const hasBlockedMissionState = AGENT_BLOCKER_STATUSES.includes(missionStatus);
    const hasQueuedPauseState =
      AGENT_QUEUED_PAUSE_STATES.includes(missionStatus) ||
      AGENT_QUEUED_PAUSE_STATES.includes(continuityState);
    const isBlocked = Boolean(
      mission &&
        (hasApprovalBoundary ||
          hasQuestionBoundary ||
          hasVerificationFailure ||
          hasBlockedMissionState ||
          hasQueuedPauseState),
    );

    return {
      approvalCount,
      questionCount,
      verificationFailureCount,
      hasApprovalBoundary,
      hasQuestionBoundary,
      hasVerificationFailure,
      hasBlockedMissionState,
      hasQueuedPauseState,
      isBlocked,
      defaultDrawer:
        hasApprovalBoundary || hasQuestionBoundary ? "queue" : hasVerificationFailure ? "proof" : "context",
    };
  }, [data.pendingApprovals, data.pendingQuestions, mission, missionStatus]);
  const agentVisibleDrawers = useMemo(
    () => AGENT_BLOCKER_DRAWER_IDS,
    [],
  );
  const showPersistentDrawer =
    Boolean(activeDrawer) && (uiMode === "builder" || agentBlockedState.isBlocked);
  const focusedRuntimeServices = useMemo(() => {
    const services = viewModel.drawers.builder.serviceStudio.services || [];
    const byNeedle = needle =>
      services.filter(item => needle.test(`${item.serviceId} ${item.label} ${item.details}`));
    return {
      hermes: byNeedle(/hermes/i),
      openClaw: byNeedle(/openclaw|open claw|opencode/i),
      bridges: byNeedle(/telegram|bridge|message|imessage|sms/i),
    };
  }, [viewModel.drawers.builder.serviceStudio.services]);

  useEffect(() => {
    setWorkspaceProfileForm(profileFormFromWorkspace(workspace, profileId));
  }, [
    profileId,
    workspace?.auto_optimize_routing,
    workspace?.commit_message_style,
    workspace?.execution_target_preference,
    workspace?.openai_codex_auth_mode,
    workspace?.minimax_auth_mode,
    workspace?.preferred_harness,
    workspace?.routing_strategy,
    workspace?.user_profile,
    workspace?.workspace_id,
  ]);

  useEffect(() => {
    setMissionForm(current => ({
      ...current,
      workspaceId: workspace?.workspace_id || current.workspaceId || "",
      runtime: mission?.runtime_id || workspace?.default_runtime || current.runtime,
      profile: mission?.selected_profile || workspace?.user_profile || profileId,
    }));
  }, [
    mission?.runtime_id,
    mission?.selected_profile,
    profileId,
    workspace?.default_runtime,
    workspace?.user_profile,
    workspace?.workspace_id,
  ]);

  useEffect(() => {
    if (mission?.mission_id) {
      setAgentRuntimeFocus("all");
      return;
    }
    setAgentRuntimeFocus(missionForm.runtime || "openclaw");
  }, [mission?.mission_id, missionForm.runtime]);

  useEffect(() => {
    const gatewayUrl = data.openClawStatus?.gatewayUrl;
    if (gatewayUrl) {
      setOpenClawGatewayUrl(gatewayUrl);
    }
  }, [data.openClawStatus?.gatewayUrl]);

  useEffect(() => {
    if (!mission && uiMode === "agent") {
      setActiveDrawer(null);
    }
  }, [mission, uiMode]);

  useEffect(() => {
    if (uiMode === "agent" && AGENT_BUILDER_ONLY_DRAWERS.includes(activeDrawer)) {
      setActiveDrawer(agentBlockedState.isBlocked ? agentBlockedState.defaultDrawer : null);
    }
  }, [activeDrawer, agentBlockedState.defaultDrawer, agentBlockedState.isBlocked, uiMode]);

  useEffect(() => {
    if (uiMode === "agent" && agentBlockedState.isBlocked) {
      setActiveDrawer(agentBlockedState.defaultDrawer);
    }
  }, [agentBlockedState.defaultDrawer, agentBlockedState.isBlocked, uiMode]);

  const runMissionAction = useCallback(
    async (action, successMessage) => {
      markAction(`mission:${action}`);
      if (!mission) {
        return;
      }
      if (previewMode !== "live" || !hasTauriBackend()) {
        pushToast("Preview mode is read-only for mission actions.", "warn");
        return;
      }

      const backendAction = action === "pause" ? "stop" : action;
      try {
        await callBackend(
          "apply_control_room_mission_action_command",
          { payload: { missionId: mission.mission_id, action: backendAction, root: null } },
          { throwOnError: true },
        );
        pushToast(successMessage, "info");
        await refreshAll(`mission-${backendAction}`);
      } catch (error) {
        pushToast(`Mission action failed: ${error}`, "error");
      }
    },
    [markAction, mission, previewMode, pushToast, refreshAll],
  );

  const runWorkspaceAction = useCallback(
    async (surface, actionId, approved = false) => {
      markAction(`workspace:${surface}:${actionId}`);
      if (previewMode !== "live" || !hasTauriBackend()) {
        pushToast("Preview mode is read-only for setup actions.", "warn");
        return;
      }

      try {
        await callBackend(
          "apply_control_room_workspace_action_command",
          {
            payload: {
              root: null,
              workspaceId: workspace?.workspace_id || null,
              surface,
              actionId,
              approved,
            },
          },
          { throwOnError: true },
        );
        pushToast("Workspace action started.", "info");
        await refreshAll(`workspace-${actionId}`);
      } catch (error) {
        pushToast(`Workspace action failed: ${error}`, "error");
      }
    },
    [markAction, previewMode, pushToast, refreshAll, workspace?.workspace_id],
  );

  const runWorkspaceActionSpec = useCallback(
    async action => {
      if (!action?.actionId) {
        pushToast("Action is missing an action id.", "warn");
        return;
      }
      const surface = inferSurfaceFromAction(action);
      const requiresApproval = Boolean(action.requiresApproval);
      let approved = false;
      if (requiresApproval) {
        const confirmed = window.confirm(
          `Run "${action.label || action.actionId}" now?\n\nThis action is approval-gated and may mutate workspace state.`,
        );
        if (!confirmed) {
          return;
        }
        approved = true;
      }
      await runWorkspaceAction(surface, action.actionId, approved);
    },
    [pushToast, runWorkspaceAction],
  );

  const saveWorkspacePolicy = useCallback(async () => {
    markAction("submit:workspace-policy");
    if (!workspace) {
      pushToast("Select a workspace first.", "warn");
      return;
    }
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot save workspace policy.", "warn");
      return;
    }

    try {
      await callBackend(
        "save_workspace_profile_command",
        {
          payload: {
            root: null,
            workspaceId: workspace.workspace_id,
            name: workspace.name,
            path: workspace.root_path,
            defaultRuntime: workspace.default_runtime,
            userProfile: workspaceProfileForm.userProfile,
            preferredHarness: workspaceProfileForm.preferredHarness,
            routingStrategy: workspaceProfileForm.routingStrategy,
            routeOverrides: saveableRouteOverrides(workspaceProfileForm.routeOverrides),
            autoOptimizeRouting: Boolean(workspaceProfileForm.autoOptimizeRouting),
            openaiCodexAuthMode: workspaceProfileForm.openaiCodexAuthMode,
            minimaxAuthMode: workspaceProfileForm.minimaxAuthMode,
            commitMessageStyle: workspaceProfileForm.commitMessageStyle,
            executionTargetPreference: workspaceProfileForm.executionTargetPreference,
          },
        },
        { throwOnError: true },
      );
      pushToast("Workspace policy saved.", "info");
      await refreshAll("workspace-policy-save");
    } catch (error) {
      pushToast(`Workspace policy save failed: ${error}`, "error");
    }
  }, [markAction, previewMode, pushToast, refreshAll, workspace, workspaceProfileForm]);

  const applyPreferredHarness = useCallback(
    async nextHarness => {
      if (!nextHarness) {
        return;
      }
      markAction(`workspace:harness:${nextHarness}`);
      setWorkspaceProfileForm(current => ({ ...current, preferredHarness: nextHarness }));
      if (!workspace) {
        pushToast("Select a workspace first.", "warn");
        return;
      }
      if (previewMode !== "live" || !hasTauriBackend()) {
        pushToast(`Harness preference staged as ${titleizeToken(nextHarness)} in preview mode.`, "info");
        return;
      }

      try {
        await callBackend(
          "save_workspace_profile_command",
          {
            payload: {
              root: null,
              workspaceId: workspace.workspace_id,
              name: workspace.name,
              path: workspace.root_path,
              defaultRuntime: workspace.default_runtime,
              userProfile: workspaceProfileForm.userProfile,
              preferredHarness: nextHarness,
              routingStrategy: workspaceProfileForm.routingStrategy,
              routeOverrides: saveableRouteOverrides(workspaceProfileForm.routeOverrides),
              autoOptimizeRouting: Boolean(workspaceProfileForm.autoOptimizeRouting),
              openaiCodexAuthMode: workspaceProfileForm.openaiCodexAuthMode,
              minimaxAuthMode: workspaceProfileForm.minimaxAuthMode,
              commitMessageStyle: workspaceProfileForm.commitMessageStyle,
              executionTargetPreference: workspaceProfileForm.executionTargetPreference,
            },
          },
          { throwOnError: true },
        );
        pushToast(`Harness switched to ${titleizeToken(nextHarness)}.`, "info");
        await refreshAll(`workspace-harness-${nextHarness}`);
      } catch (error) {
        pushToast(`Harness switch failed: ${error}`, "error");
      }
    },
    [markAction, previewMode, pushToast, refreshAll, workspace, workspaceProfileForm],
  );

  const handleAgentRouteFieldChange = useCallback((field, value) => {
    setWorkspaceProfileForm(current => ({
      ...current,
      routeOverrides: updateRouteOverride(current.routeOverrides, agentRouteRole, {
        [field]: value,
      }),
    }));
  }, [agentRouteRole]);

  const handleAgentRouteSave = useCallback(async () => {
    markAction(`agent:route-save:${agentRouteRole}`);
    if (!workspace) {
      pushToast("Select a workspace before saving route controls.", "warn");
      return;
    }
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Route controls are staged in preview mode.", "info");
      return;
    }
    await saveWorkspacePolicy();
  }, [agentRouteRole, markAction, previewMode, pushToast, saveWorkspacePolicy, workspace]);

  const focusTranscriptTurn = useCallback(turnId => {
    if (!turnId) {
      return;
    }
    setHighlightedTurnId(turnId);
    window.requestAnimationFrame(() => {
      document.getElementById(turnId)?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }, []);

  const togglePinnedNexus = useCallback(turnId => {
    if (!turnId) {
      return;
    }
    setPinnedNexusIds(current =>
      current.includes(turnId) ? current.filter(item => item !== turnId) : [...current, turnId],
    );
  }, []);

  const handleAgentSteerFromTurn = useCallback(item => {
    const prefix = item?.meta ? `From ${item.meta}` : "From this step";
    setHighlightedTurnId(item?.id || "");
    setOperatorDraft(
      `${prefix}: ${item?.title || "revisit this decision"}.\nDo this differently: `,
    );
    document.getElementById("thread-note")?.focus();
  }, []);

  const handleAgentMemoryFromTurn = useCallback(item => {
    setHighlightedTurnId(item?.id || "");
    setOperatorDraft(
      `Memory correction for ${item?.title || "this step"}:\nThis was not okay because \nNext time do this instead: `,
    );
    document.getElementById("thread-note")?.focus();
  }, []);

  const handleAgentValidateTurn = useCallback(item => {
    markAction(`agent:validate:${item?.id || "turn"}`);
    setHighlightedTurnId(item?.id || "");
    if (item?.role === "queue" || /approval/i.test(`${item?.label || ""} ${item?.title || ""}`)) {
      setActiveDrawer("queue");
      return;
    }
    if (item?.tone === "bad" || /verification|failed|error/i.test(`${item?.label || ""} ${item?.title || ""}`)) {
      setActiveDrawer("proof");
      return;
    }
    setActiveDrawer("context");
  }, [markAction]);

  const openMissionDialog = useCallback(() => {
    markAction("open:mission-dialog");
    setMissionForm(current => ({
      ...current,
      workspaceId: workspace?.workspace_id || current.workspaceId || "",
      runtime: mission?.runtime_id || workspace?.default_runtime || current.runtime,
      profile: mission?.selected_profile || workspace?.user_profile || profileId,
      objective:
        !mission && operatorDraft.trim() && !current.objective.trim()
          ? operatorDraft.trim()
          : current.objective,
    }));
    setShowMissionDialog(true);
  }, [
    markAction,
    mission,
    mission?.runtime_id,
    mission?.selected_profile,
    operatorDraft,
    profileId,
    workspace?.default_runtime,
    workspace?.user_profile,
    workspace?.workspace_id,
  ]);

  const handleQualityRoadmapAction = useCallback(
    async item => {
      const actionKind = item?.actionKind || "";
      markAction(`quality-roadmap:${item?.id || "unknown"}`);
      if (actionKind === "validate") {
        const validateAction = viewModel.drawers.builder.validationActions[0];
        if (validateAction) {
          await runWorkspaceActionSpec(validateAction);
          return;
        }
        pushToast("No validation action is currently available.", "warn");
        return;
      }
      if (actionKind === "mission") {
        openMissionDialog();
        return;
      }
      if (actionKind === "service") {
        const serviceAction = viewModel.drawers.builder.serviceStudio.services
          .flatMap(service => service.actions)
          .find(action => action);
        if (serviceAction) {
          await runWorkspaceActionSpec(serviceAction);
          return;
        }
        setUiMode("builder");
        setActiveDrawer("runtime");
        pushToast("No service repair action is currently available.", "warn");
        return;
      }
      if (actionKind === "skill") {
        setSkillStudioFilter("needs_attention");
        setUiMode("builder");
        setActiveDrawer("skills");
        return;
      }
      if (actionKind === "workflow") {
        const suggested = viewModel.drawers.builder.workflowStudio.recommended;
        if (suggested?.label) {
          pushToast(`Open workflow: ${suggested.label}`, "info");
        }
        openMissionDialog();
        return;
      }
      pushToast("No executable action is mapped for this roadmap item yet.", "warn");
    },
    [markAction, openMissionDialog, pushToast, runWorkspaceActionSpec, viewModel],
  );

  const handleBuilderFeatureAction = useCallback(
    async (actionId, payload = {}) => {
      markAction(`builder:feature:${actionId || "open"}`);
      switch (actionId) {
        case "open_workspace":
          setShowWorkspaceDialog(true);
          return;
        case "open_mission":
          if (workspaces.length === 0) {
            setShowWorkspaceDialog(true);
            return;
          }
          openMissionDialog();
          return;
        case "open_runtime":
          setUiMode("builder");
          setActiveDrawer("runtime");
          return;
        case "open_auth":
          setUiMode("builder");
          setActiveDrawer("runtime");
          window.setTimeout(() => {
            document.getElementById("provider-auth-panel")?.scrollIntoView({
              behavior: "smooth",
              block: "start",
            });
          }, 0);
          return;
        case "open_profiles":
          setUiMode("builder");
          setActiveDrawer("profiles");
          return;
        case "open_skills":
          setSkillStudioFilter(payload.filter || "needs_attention");
          setUiMode("builder");
          setActiveDrawer("skills");
          return;
        case "open_escalation":
          setShowEscalationDialog(true);
          return;
        case "open_queue":
          setActiveDrawer("queue");
          return;
        case "open_proof":
          setActiveDrawer("proof");
          return;
        case "open_context":
          setActiveDrawer("context");
          return;
        case "open_builder":
          setUiMode("builder");
          setActiveDrawer("builder");
          return;
        case "run_validation": {
          const validateAction = viewModel.drawers.builder.validationActions[0];
          if (validateAction) {
            await runWorkspaceActionSpec(validateAction);
            return;
          }
          pushToast("No validation action is currently available.", "warn");
          setActiveDrawer("proof");
          return;
        }
        case "open_workflow": {
          const suggested = viewModel.drawers.builder.workflowStudio.recommended;
          if (suggested?.label) {
            pushToast(`Workflow focus: ${suggested.label}`, "info");
          }
          openMissionDialog();
          return;
        }
        case "focus_thread": {
          const nextMissionId =
            payload?.missionId || builderPrimaryConversation?.missionId || mission?.mission_id;
          if (nextMissionId) {
            setSelectedMissionId(nextMissionId);
          }
          return;
        }
        case "focus_conversations":
          if (builderPrimaryConversation?.missionId) {
            setSelectedMissionId(builderPrimaryConversation.missionId);
          }
          return;
        default:
          setActiveDrawer("builder");
      }
    },
    [
      markAction,
      mission?.mission_id,
      openMissionDialog,
      pushToast,
      runWorkspaceActionSpec,
      viewModel.drawers.builder.validationActions,
      viewModel.drawers.builder.workflowStudio.recommended,
      workspaces.length,
    ],
  );

  const handleBuilderReviewTargetSeed = useCallback(
    target => {
      if (!target) {
        return;
      }
      setSelectedReviewTargetId(target.id || "");
      setOperatorDraft(target.commentSeed || `${target.title || "Review target"}:\n`);
      window.requestAnimationFrame(() => {
        document.getElementById("builder-thread-note")?.focus();
      });
    },
    [],
  );

  const handleWorkspaceSubmit = useCallback(
    async event => {
      event.preventDefault();
      markAction("submit:workspace");
      if (!workspaceForm.name.trim() || !workspaceForm.path.trim()) {
        pushToast("Workspace name and path are required.", "warn");
        return;
      }

      if (previewMode !== "live" || !hasTauriBackend()) {
        pushToast("Preview mode cannot save workspaces.", "warn");
        setShowWorkspaceDialog(false);
        return;
      }

      try {
        await callBackend(
          "save_workspace_profile_command",
          {
            payload: {
              root: null,
              workspaceId: null,
              name: workspaceForm.name.trim(),
              path: workspaceForm.path.trim(),
              defaultRuntime: workspaceForm.defaultRuntime,
              userProfile: workspaceForm.userProfile,
            },
          },
          { throwOnError: true },
        );
        pushToast("Workspace saved.", "info");
        setShowWorkspaceDialog(false);
        setWorkspaceForm(DEFAULT_WORKSPACE_FORM);
        await refreshAll("workspace-save");
      } catch (error) {
        pushToast(`Workspace save failed: ${error}`, "error");
      }
    },
    [markAction, previewMode, pushToast, refreshAll, workspaceForm],
  );

  const handleMissionSubmit = useCallback(
    async event => {
      event.preventDefault();
      markAction("submit:mission");
      if (!missionForm.workspaceId || !missionForm.objective.trim()) {
        pushToast("Choose a workspace and enter a mission objective.", "warn");
        return;
      }

      if (previewMode !== "live" || !hasTauriBackend()) {
        pushToast("Preview mode cannot launch missions.", "warn");
        setShowMissionDialog(false);
        return;
      }

      try {
        await callBackend(
          "start_control_room_mission_command",
          {
            payload: {
              root: null,
              workspaceId: missionForm.workspaceId,
              runtime: missionForm.runtime,
              objective: missionForm.objective.trim(),
              successChecks: missionForm.successChecks
                .split("\n")
                .map(line => line.trim())
                .filter(Boolean),
              mode: missionForm.mode,
              budgetHours: Number(missionForm.budgetHours || 12),
              runUntil: missionForm.runUntil,
              profile: missionForm.profile,
              escalationDestination: telegramChatId.trim() || null,
              codeExecution: codeExecutionEnabled,
              codeExecutionMemory: codeExecutionMemory,
              codeExecutionRequired: false,
            },
          },
          { throwOnError: true },
        );
        pushToast("Mission launched.", "info");
        setShowMissionDialog(false);
        setMissionForm(DEFAULT_MISSION_FORM);
        await refreshAll("mission-start");
      } catch (error) {
        pushToast(`Mission launch failed: ${error}`, "error");
      }
    },
    [
      codeExecutionEnabled,
      codeExecutionMemory,
      markAction,
      missionForm,
      previewMode,
      pushToast,
      refreshAll,
      telegramChatId,
    ],
  );

  const handleSaveTelegram = useCallback(
    async event => {
      event.preventDefault();
      markAction("submit:telegram");
      if (previewMode !== "live" || !hasTauriBackend()) {
        pushToast("Preview mode cannot change escalation settings.", "warn");
        setShowEscalationDialog(false);
        return;
      }

      try {
        if (telegramBotToken.trim()) {
          await callBackend(
            "save_telegram_bot_token_command",
            { token: telegramBotToken.trim() },
            { throwOnError: true },
          );
        }
        pushToast("Escalation settings saved.", "info");
        setTelegramBotToken("");
        setShowEscalationDialog(false);
        await refreshAll("telegram-save");
      } catch (error) {
        pushToast(`Telegram save failed: ${error}`, "error");
      }
    },
    [markAction, previewMode, pushToast, refreshAll, telegramBotToken],
  );

  const handleClearTelegram = useCallback(async () => {
    markAction("clear:telegram");
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot clear escalation settings.", "warn");
      return;
    }
    try {
      await callBackend("clear_telegram_bot_token_command", undefined, { throwOnError: true });
      setTelegramBotToken("");
      pushToast("Telegram token cleared.", "info");
      await refreshAll("telegram-clear");
    } catch (error) {
      pushToast(`Telegram clear failed: ${error}`, "error");
    }
  }, [markAction, previewMode, pushToast, refreshAll]);

  const handleSendTestPing = useCallback(async () => {
    markAction("send:telegram-test");
    if (!telegramChatId.trim()) {
      pushToast("Enter a Telegram chat ID first.", "warn");
      return;
    }
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot send escalation pings.", "warn");
      return;
    }

    try {
      await callBackend(
        "send_telegram_message_command",
        {
          payload: {
            chatId: telegramChatId.trim(),
            text: "Fluxio supervision test ping: approvals and mission escalations are reachable.",
          },
        },
        { throwOnError: true },
      );
      pushToast("Telegram test ping sent.", "info");
    } catch (error) {
      pushToast(`Telegram message failed: ${error}`, "error");
    }
  }, [markAction, previewMode, pushToast, telegramChatId]);

  const handlePrimaryAction = useCallback(() => {
    const action = viewModel.topBar.primaryAction;
    markAction(`primary:${action.kind}`);
    if (action.kind === "start") {
      openMissionDialog();
      return;
    }
    if (action.kind === "resume") {
      void runMissionAction("resume", "Mission resume requested.");
      return;
    }
    if (action.kind === "queue") {
      setActiveDrawer("queue");
      return;
    }
    setActiveDrawer("proof");
  }, [markAction, openMissionDialog, runMissionAction, viewModel.topBar.primaryAction]);

  const appendOperatorEntry = useCallback(
    entry => {
      setOperatorNotes(current => [createSessionEntry(entry), ...current]);
    },
    [],
  );

  const clearOperatorAttachments = useCallback(() => {
    setOperatorAttachments([]);
  }, []);

  const removeOperatorAttachment = useCallback(attachmentId => {
    setOperatorAttachments(current => current.filter(item => item.id !== attachmentId));
  }, []);

  const handleComposerPaste = useCallback(
    event => {
      const items = Array.from(event.clipboardData?.items || []);
      const imageItems = items.filter(item => item.kind === "file" && item.type.startsWith("image/"));
      if (imageItems.length === 0) {
        return;
      }
      event.preventDefault();

      const slotsLeft = Math.max(0, MAX_INLINE_ATTACHMENTS - operatorAttachments.length);
      if (slotsLeft <= 0) {
        pushToast(`Only ${MAX_INLINE_ATTACHMENTS} inline attachments are allowed.`, "warn");
        return;
      }

      const selectedItems = imageItems.slice(0, slotsLeft);
      selectedItems.forEach((item, index) => {
        const file = item.getAsFile();
        if (!file) {
          return;
        }
        if (file.size > MAX_ATTACHMENT_BYTES) {
          pushToast(
            `Attachment ${file.name || index + 1} exceeds ${Math.round(
              MAX_ATTACHMENT_BYTES / (1024 * 1024),
            )}MB.`,
            "warn",
          );
          return;
        }
        const reader = new FileReader();
        reader.onload = () => {
          setOperatorAttachments(current =>
            [
              {
                id: `attachment-${Date.now()}-${Math.random().toString(36).slice(2)}`,
                name: file.name || `pasted-image-${index + 1}.png`,
                mime: file.type || "image/png",
                size: file.size,
                previewUrl: typeof reader.result === "string" ? reader.result : "",
                createdAt: new Date().toISOString(),
              },
              ...current,
            ].slice(0, MAX_INLINE_ATTACHMENTS),
          );
        };
        reader.readAsDataURL(file);
      });

      pushToast("Image attachment added to the active composer.", "info");
    },
    [operatorAttachments.length, pushToast],
  );

  const applyModelQuickPreset = useCallback(
    preset => {
      if (!preset) {
        return;
      }
      handleAgentRouteFieldChange("provider", preset.provider);
      handleAgentRouteFieldChange("model", preset.model);
      handleAgentRouteFieldChange("effort", preset.effort);
      pushToast(`Applied preset: ${preset.label}`, "info");
    },
    [handleAgentRouteFieldChange, pushToast],
  );

  const runTaskPrompt = useCallback(
    async (task, source = "schedule") => {
      const prompt = String(task?.prompt || "").trim();
      if (!prompt) {
        return;
      }
      if (!mission?.mission_id || previewMode !== "live" || !hasTauriBackend()) {
        appendOperatorEntry({
          title: `Task queued (${source})`,
          detail: prompt,
          meta: "Task log only (no live mission selected)",
          tone: "warn",
        });
        return;
      }
      try {
        await callBackend(
          "send_control_room_mission_follow_up_command",
          { payload: { missionId: mission.mission_id, message: prompt, root: null } },
          { throwOnError: true },
        );
        appendOperatorEntry({
          title: `Task executed (${source})`,
          detail: prompt,
          meta: timestampLabel(new Date().toISOString()),
          tone: "good",
        });
      } catch (error) {
        appendOperatorEntry({
          title: `Task failed (${source})`,
          detail: `${prompt}\n\n${String(error)}`,
          meta: timestampLabel(new Date().toISOString()),
          tone: "bad",
        });
      }
    },
    [appendOperatorEntry, mission?.mission_id, previewMode],
  );

  const handleOperatorNote = useCallback(
    event => {
      event.preventDefault();
      if (!operatorDraft.trim()) {
        return;
      }
      markAction("composer:add-note");
      const attachmentSummary = operatorAttachments
        .map(item => `${item.name} (${Math.max(1, Math.round(item.size / 1024))}KB)`)
        .join(", ");
      appendOperatorEntry({
        title: "Operator note",
        detail: operatorAttachments.length
          ? `${operatorDraft.trim()}\n\nAttachments: ${attachmentSummary}`
          : operatorDraft.trim(),
        meta: operatorAttachments.length
          ? `Local note · ${operatorAttachments.length} attachment${operatorAttachments.length === 1 ? "" : "s"}`
          : "Local note",
        tone: "neutral",
        channel: "note",
      });
      if (mission?.mission_id) {
        setMemoryStore(current => ({
          ...current,
          mission: {
            ...current.mission,
            [mission.mission_id]: operatorDraft.trim().slice(0, 600),
          },
        }));
      }
      if (workspace?.workspace_id) {
        setMemoryStore(current => ({
          ...current,
          workspace: {
            ...current.workspace,
            [workspace.workspace_id]: operatorDraft.trim().slice(0, 600),
          },
        }));
      }
      setOperatorDraft("");
      clearOperatorAttachments();
      pushToast("Operator note added to this session.", "info");
    },
    [
      appendOperatorEntry,
      clearOperatorAttachments,
      markAction,
      mission?.mission_id,
      operatorAttachments,
      operatorDraft,
      pushToast,
      workspace?.workspace_id,
    ],
  );

  const handleAgentFollowUp = useCallback(async () => {
    const followUp = operatorDraft.trim();
    if (!followUp) {
      pushToast("Write a follow-up first.", "warn");
      return;
    }
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot send runtime follow-ups.", "warn");
      return;
    }
    if (!mission?.mission_id) {
      pushToast("Select a mission before sending a follow-up.", "warn");
      return;
    }

    markAction("composer:send-follow-up");
    try {
      const steeringLines = [];
      const currentPhase =
        mission?.missionLoop?.currentCyclePhase || mission?.state?.current_cycle_phase || "execute";
      if (mission && agentRuntimeFocus !== "all") {
        steeringLines.push(`Runtime preference: ${runtimeLabel(agentRuntimeFocus)}.`);
      }
      steeringLines.push(
        `Current mission phase: ${titleizeToken(currentPhase)} via ${titleizeToken(
          phaseRouteRole(currentPhase),
        )}.`,
      );
      const selectedRoute =
        workspaceProfileForm.routeOverrides.find(item => item.role === agentRouteRole) || {};
      const effectiveRoute =
        asList(mission?.effectiveRouteContract?.roles).find(item => item.role === agentRouteRole) ||
        {};
      const routeChanged =
        (selectedRoute.provider || "openai") !== (effectiveRoute.provider || "openai") ||
        (selectedRoute.model || "").trim() !== (effectiveRoute.model || "").trim() ||
        (selectedRoute.effort || "default") !== (effectiveRoute.effort || "default");
      if (routeChanged && selectedRoute.model?.trim()) {
        steeringLines.push(
          `Route preference for ${titleizeToken(agentRouteRole)}: ${titleizeToken(selectedRoute.provider)} / ${selectedRoute.model.trim()}${
            selectedRoute.effort && selectedRoute.effort !== "default"
              ? ` / ${selectedRoute.effort}`
              : ""
          }.`,
        );
      }
      const activeProvider = String(
        selectedRoute.provider || effectiveRoute.provider || "openai",
      ).trim().toLowerCase();
      if (codeExecutionEnabled && ["openai", "openai-codex"].includes(activeProvider)) {
        steeringLines.push(
          `If the OpenAI route is active, use the python tool / code execution when it will ground the work. Prefer a ${codeExecutionMemory} container budget.`,
        );
      }
      const memorySnippets = [];
      if (memoryPolicy.includeInFollowUps) {
        if (memoryPolicy.projectScoped && workspace?.workspace_id) {
          const workspaceMemo = String(memoryStore?.workspace?.[workspace.workspace_id] || "").trim();
          if (workspaceMemo) {
            memorySnippets.push(`Workspace memory: ${workspaceMemo}`);
          }
        }
        if (memoryPolicy.missionScoped && mission?.mission_id) {
          const missionMemo = String(memoryStore?.mission?.[mission.mission_id] || "").trim();
          if (missionMemo) {
            memorySnippets.push(`Mission memory: ${missionMemo}`);
          }
        }
      }
      const attachmentLines = operatorAttachments.map(
        item => `[attachment:${item.name}|${item.mime}|${Math.max(1, Math.round(item.size / 1024))}KB]`,
      );
      const composedFollowUpParts = [];
      if (steeringLines.length > 0) {
        composedFollowUpParts.push(steeringLines.join(" "));
      }
      if (memorySnippets.length > 0) {
        composedFollowUpParts.push(memorySnippets.join("\n"));
      }
      composedFollowUpParts.push(followUp);
      if (attachmentLines.length > 0) {
        composedFollowUpParts.push(`Attachments:\n${attachmentLines.join("\n")}`);
      }
      const composedFollowUp = composedFollowUpParts.filter(Boolean).join("\n\n");
      const hasActiveDelegatedRuntime = asList(mission?.delegated_runtime_sessions).some(session =>
        ["waiting_for_approval", "running", "launching"].includes(
          String(session?.status || "").trim().toLowerCase(),
        ),
      );
      let sentLive = false;
      if (
        mission.runtime_id === "openclaw" &&
        data.openClawStatus?.connected &&
        !hasActiveDelegatedRuntime
      ) {
        try {
          await callBackend(
            "send_openclaw_message",
            { payload: { message: composedFollowUp } },
            { throwOnError: true },
          );
          sentLive = true;
        } catch (error) {
          pushToast(`OpenClaw live send failed, keeping the follow-up in mission thread: ${error}`, "warn");
        }
      }
      await callBackend(
        "send_control_room_mission_follow_up_command",
        { payload: { missionId: mission.mission_id, message: composedFollowUp, root: null } },
        { throwOnError: true },
      );
      setMemoryStore(current => ({
        ...current,
        mission: {
          ...current.mission,
          [mission.mission_id]: followUp.slice(0, 800),
        },
        workspace: workspace?.workspace_id
          ? {
              ...current.workspace,
              [workspace.workspace_id]: followUp.slice(0, 800),
            }
          : current.workspace,
      }));
      setOperatorDraft("");
      clearOperatorAttachments();
      pushToast(sentLive ? "Follow-up sent live and recorded in the mission thread." : "Follow-up recorded in the mission thread.", "info");
    } catch (error) {
      pushToast(`Mission follow-up failed: ${error}`, "error");
    }
  }, [
    codeExecutionEnabled,
    codeExecutionMemory,
    agentRouteRole,
    agentRuntimeFocus,
    data.openClawStatus?.connected,
    markAction,
    mission,
    memoryPolicy.includeInFollowUps,
    memoryPolicy.missionScoped,
    memoryPolicy.projectScoped,
    memoryStore?.mission,
    memoryStore?.workspace,
    operatorAttachments,
    operatorDraft,
    previewMode,
    pushToast,
    workspace?.workspace_id,
    workspaceProfileForm.routeOverrides,
    mission?.effectiveRouteContract?.roles,
    clearOperatorAttachments,
  ]);

  const handleOpenClawConnect = useCallback(async () => {
    markAction("runtime:openclaw-connect");
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot change OpenClaw gateway state.", "warn");
      return;
    }
    try {
      await callBackend(
        "connect_openclaw_gateway",
        { payload: { gatewayUrl: openClawGatewayUrl.trim() || null } },
        { throwOnError: true },
      );
      pushToast("OpenClaw gateway connect requested.", "info");
      await refreshAll("openclaw-connect");
    } catch (error) {
      pushToast(`OpenClaw connect failed: ${error}`, "error");
    }
  }, [markAction, openClawGatewayUrl, previewMode, pushToast, refreshAll]);

  const handleOpenClawDisconnect = useCallback(async () => {
    markAction("runtime:openclaw-disconnect");
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot change OpenClaw gateway state.", "warn");
      return;
    }
    try {
      await callBackend("disconnect_openclaw_gateway", undefined, { throwOnError: true });
      pushToast("OpenClaw gateway disconnected.", "info");
      await refreshAll("openclaw-disconnect");
    } catch (error) {
      pushToast(`OpenClaw disconnect failed: ${error}`, "error");
    }
  }, [markAction, previewMode, pushToast, refreshAll]);

  const handleOpenClawSaveToken = useCallback(async () => {
    markAction("runtime:openclaw-save-token");
    if (!openClawGatewayToken.trim()) {
      pushToast("Paste a gateway token first.", "warn");
      return;
    }
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot change OpenClaw gateway state.", "warn");
      return;
    }
    try {
      await callBackend(
        "save_openclaw_gateway_token",
        { token: openClawGatewayToken.trim() },
        { throwOnError: true },
      );
      setOpenClawGatewayToken("");
      pushToast("OpenClaw gateway token saved.", "info");
      await refreshAll("openclaw-token-save");
    } catch (error) {
      pushToast(`OpenClaw token save failed: ${error}`, "error");
    }
  }, [markAction, openClawGatewayToken, previewMode, pushToast, refreshAll]);

  const handleOpenClawClearToken = useCallback(async () => {
    markAction("runtime:openclaw-clear-token");
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot change OpenClaw gateway state.", "warn");
      return;
    }
    try {
      await callBackend("clear_openclaw_gateway_token", undefined, { throwOnError: true });
      pushToast("OpenClaw gateway token cleared.", "info");
      await refreshAll("openclaw-token-clear");
    } catch (error) {
      pushToast(`OpenClaw token clear failed: ${error}`, "error");
    }
  }, [markAction, previewMode, pushToast, refreshAll]);

  const handleProviderSecretSave = useCallback(async providerId => {
    markAction(`provider-secret:save:${providerId}`);
    const secret = String(providerSecretDrafts?.[providerId] || "").trim();
    if (!secret) {
      pushToast("Paste a provider API key first.", "warn");
      return;
    }
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot change provider authentication.", "warn");
      return;
    }
    try {
      const payload = { providerId, secret };
      const saved =
        (await callBackend("save_provider_secret_command", payload)) ??
        (await callBackend("save_provider_secret_command", {
          provider_id: providerId,
          secret,
        }));
      if (!saved) {
        throw new Error("Provider secret save did not complete.");
      }
      setProviderSecretDrafts(current => ({ ...current, [providerId]: "" }));
      pushToast(`${titleizeToken(providerId)} secret saved.`, "info");
      await refreshAll(`provider-secret-save-${providerId}`);
    } catch (error) {
      pushToast(`Provider secret save failed: ${error}`, "error");
    }
  }, [markAction, previewMode, providerSecretDrafts, pushToast, refreshAll]);

  const handleProviderSecretClear = useCallback(async providerId => {
    markAction(`provider-secret:clear:${providerId}`);
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot change provider authentication.", "warn");
      return;
    }
    try {
      const cleared =
        (await callBackend("clear_provider_secret_command", { providerId })) ??
        (await callBackend("clear_provider_secret_command", {
          provider_id: providerId,
        }));
      if (!cleared) {
        throw new Error("Provider secret clear did not complete.");
      }
      setProviderSecretDrafts(current => ({ ...current, [providerId]: "" }));
      pushToast(`${titleizeToken(providerId)} secret cleared.`, "info");
      await refreshAll(`provider-secret-clear-${providerId}`);
    } catch (error) {
      pushToast(`Provider secret clear failed: ${error}`, "error");
    }
  }, [markAction, previewMode, pushToast, refreshAll]);

  const openClawRuntimeActive = mission?.runtime_id === "openclaw";
  const openClawStatus = data.openClawStatus;
  const delegatedSessions = useMemo(
    () => (Array.isArray(mission?.delegated_runtime_sessions) ? mission.delegated_runtime_sessions : []),
    [mission?.delegated_runtime_sessions],
  );
  const bridgeSessions = useMemo(
    () => (Array.isArray(snapshot?.bridgeLab?.connectedSessions) ? snapshot.bridgeLab.connectedSessions : []),
    [snapshot?.bridgeLab?.connectedSessions],
  );
  const effectiveRouteRows = useMemo(
    () => (Array.isArray(mission?.effectiveRouteContract?.roles) ? mission.effectiveRouteContract.roles : []),
    [mission?.effectiveRouteContract?.roles],
  );
  const missionRuntimeContract = useMemo(
    () =>
      mission
        ? [
            {
              label: "Runtime",
              value: runtimeLabel(mission?.runtime_id),
            },
            {
              label: "Profile",
              value: titleizeToken(mission?.selected_profile || workspace?.user_profile || profileId),
            },
            {
              label: "Mode",
              value: titleizeToken(mission?.run_budget?.mode || mission?.missionLoop?.timeBudget?.mode || "autopilot"),
            },
            {
              label: "Run until",
              value: titleizeToken(
                mission?.missionLoop?.timeBudget?.runUntilBehavior ||
                  mission?.run_budget?.run_until_behavior ||
                  "pause_on_failure",
              ),
            },
            {
              label: "Harness",
              value: titleizeToken(mission?.harness_id || workspace?.preferred_harness || "fluxio_hybrid"),
            },
            {
              label: "Active route",
              value: (() => {
                const truth =
                  mission?.providerTruth ||
                  mission?.missionLoop?.providerTruth ||
                  mission?.state?.provider_runtime_truth ||
                  {};
                const active = truth?.activeRoute || {};
                if (!active?.provider && !active?.model) {
                  return "Not resolved";
                }
                return `${titleizeToken(active.provider)} · ${active.model || "default"}`;
              })(),
            },
            {
              label: "Blocker class",
              value: titleizeToken(
                mission?.state?.blocker_classification?.class ||
                  mission?.missionLoop?.blocker?.class ||
                  "none",
              ),
            },
            {
              label: "Code execution",
              value: (() => {
                const codeState =
                  mission?.state?.code_execution ||
                  mission?.missionLoop?.codeExecution ||
                  {};
                if (!codeState?.enabled) {
                  return "Off";
                }
                return codeState?.container_id
                  ? `On · ${codeState.container_id}`
                  : "On · auto container";
              })(),
            },
          ]
        : [],
    [
      mission,
      profileId,
      workspace?.preferred_harness,
      workspace?.user_profile,
    ],
  );
  const builderBoard = viewModel.drawers.builder.board;
  const workspaceById = useMemo(
    () => new Map(workspaces.map(item => [item.workspace_id, item])),
    [workspaces],
  );
  const workspaceNavItems = useMemo(
    () =>
      workspaces.map(item => {
        const workspaceMissionRows = missions.filter(entry => entry?.workspace_id === item.workspace_id);
        const activeCount = workspaceMissionRows.filter(
          entry => !["completed", "failed"].includes(entry?.state?.status || ""),
        ).length;
        const blockedCount = workspaceMissionRows.filter(
          entry =>
            asList(entry?.proof?.pending_approvals).length > 0 ||
            asList(entry?.state?.verification_failures).length > 0 ||
            ["needs_approval", "blocked", "verification_failed", "queued"].includes(
              entry?.state?.status || "",
            ),
        ).length;
        return {
          workspaceId: item.workspace_id,
          title: item.name,
          subtitle: `${runtimeLabel(item.default_runtime)} default`,
          context: item.root_path,
          tone: blockedCount > 0 ? "warn" : item.runtimeStatus?.detected ? "good" : "warn",
          badge: pathLeaf(item.root_path) || titleizeToken(item.workspace_type || "workspace"),
          stats: [
            activeCount > 0 ? { label: "threads", value: activeCount, tone: "good" } : null,
            blockedCount > 0 ? { label: "blocked", value: blockedCount, tone: "warn" } : null,
          ].filter(Boolean),
        };
      }),
    [missions, workspaces],
  );
  const missionNavItems = useMemo(
    () =>
      missionOptions.map(item => {
        const ownerWorkspace = workspaceById.get(item.workspace_id) || null;
        const executionPath =
          item?.delegated_runtime_sessions?.find(session => session?.execution_root)?.execution_root ||
          item?.execution_scope?.execution_root ||
          item?.state?.execution_scope?.execution_root ||
          ownerWorkspace?.root_path ||
          "";
        const approvalCount = asList(item?.proof?.pending_approvals).length;
        const verificationCount = asList(item?.state?.verification_failures).length;
        const delegatedCount = asList(item?.delegated_runtime_sessions).filter(
          session => !["completed", "failed", "stopped"].includes(session?.status || ""),
        ).length;
        const queuedCount = ["queued", "needs_approval", "blocked"].includes(item?.state?.status || "")
          ? 1
          : 0;
        const tone =
          verificationCount > 0
            ? "bad"
            : approvalCount > 0 || queuedCount > 0
              ? "warn"
              : delegatedCount > 0 || item?.state?.status === "running"
                ? "good"
                : "neutral";
        return {
          missionId: item.mission_id,
          title: item.title || item.objective,
          subtitle: `${runtimeLabel(item.runtime_id)} · ${titleizeToken(item.state?.status || "draft")}`,
          context: executionPath,
          tone,
          badge:
            pathLeaf(executionPath) ||
            pathLeaf(ownerWorkspace?.root_path) ||
            titleizeToken(item.state?.status || "draft"),
          stats: [
            approvalCount > 0 ? { label: "approvals", value: approvalCount, tone: "warn" } : null,
            verificationCount > 0 ? { label: "failures", value: verificationCount, tone: "bad" } : null,
            delegatedCount > 0 ? { label: "lanes", value: delegatedCount, tone: "good" } : null,
            queuedCount > 0 && approvalCount === 0
              ? { label: "queued", value: queuedCount, tone: "warn" }
              : null,
          ].filter(Boolean),
        };
      }),
    [missionOptions, workspaceById],
  );
  const builderRootItems = useMemo(() => builderBoard.roots || [], [builderBoard.roots]);
  const builderNexusItems = useMemo(() => builderBoard.nexuses || [], [builderBoard.nexuses]);
  const builderPrimaryConversation = useMemo(
    () =>
      builderBoard.activeConversations.find(item => item.selected) ||
      builderBoard.activeConversations.find(item => item.blocked) ||
      builderBoard.activeConversations[0] ||
      null,
    [builderBoard.activeConversations],
  );
  const builderSecondaryConversations = useMemo(
    () =>
      builderBoard.activeConversations.filter(
        item => item.missionId !== builderPrimaryConversation?.missionId,
      ),
    [builderBoard.activeConversations, builderPrimaryConversation?.missionId],
  );
  const tutorialStudio = viewModel.drawers.builder.tutorialStudio;
  const recommendationStudio = viewModel.drawers.builder.recommendationStudio;
  const liveReviewStudio = viewModel.drawers.builder.liveReviewStudio;
  const builderSelectedReviewTarget = useMemo(
    () =>
      liveReviewStudio.targets.find(item => item.id === selectedReviewTargetId) ||
      liveReviewStudio.targets[0] ||
      null,
    [liveReviewStudio.targets, selectedReviewTargetId],
  );
  const topbarStatus = useMemo(() => {
    if (uiMode === "builder") {
      return {
        label: "Builder focus",
        value:
          builderBoard.activeConversations.length > 0
            ? `${builderBoard.activeConversations.length} active conversation${builderBoard.activeConversations.length === 1 ? "" : "s"}`
            : "No active conversations",
        tone:
          builderBoard.activeConversations.length > 0
            ? builderBoard.activeConversations.some(item => item.blocked)
              ? "warn"
              : "good"
            : "neutral",
      };
    }
    if (agentBlockedState.isBlocked) {
      return {
        label: "Blocker state",
        value: viewModel.topBar.liveStatus.label,
        tone: viewModel.topBar.liveStatus.tone,
      };
    }
    return {
      label: mission ? "Mission state" : "Workspace state",
      value: mission ? viewModel.topBar.liveStatus.label : setupHealth.environmentReady ? "Environment ready" : "Needs setup",
      tone: mission ? viewModel.topBar.liveStatus.tone : setupHealth.environmentReady ? "good" : "warn",
    };
  }, [
    agentBlockedState.isBlocked,
    builderBoard.activeConversations,
    mission,
    setupHealth.environmentReady,
    uiMode,
    viewModel.topBar.liveStatus.label,
    viewModel.topBar.liveStatus.tone,
  ]);
  const runtimeOptions = useMemo(
    () =>
      asList(snapshot?.runtimes).map(item => ({
        value: item.runtime_id,
        label: item.label || runtimeLabel(item.runtime_id),
      })),
    [snapshot?.runtimes],
  );
  const bridgeSummary = useMemo(() => {
    const connected = bridgeSessions.filter(item => item?.status === "connected").length;
    const callbackReady = bridgeSessions.filter(item => item?.approval_callback).length;
    return {
      connected,
      callbackReady,
      totalApps: asList(snapshot?.bridgeLab?.discoveredApps).length,
      recommendation:
        snapshot?.bridgeLab?.recommendation ||
        "Bridge hand-offs between runtimes and connected apps will appear here.",
    };
  }, [bridgeSessions, snapshot?.bridgeLab?.discoveredApps, snapshot?.bridgeLab?.recommendation]);
  const selectedAgentRoute = useMemo(
    () => {
      const explicit = workspaceProfileForm.routeOverrides.find(item => item.role === agentRouteRole) || {};
      const effective = effectiveRouteRows.find(item => item.role === agentRouteRole) || {};
      return {
        role: agentRouteRole,
        provider: explicit.provider || effective.provider || "openai",
        model: explicit.model || effective.model || "",
        effort: explicit.effort || effective.effort || "default",
      };
    },
    [agentRouteRole, effectiveRouteRows, workspaceProfileForm.routeOverrides],
  );
  const activeEffectiveRoute = useMemo(
    () =>
      effectiveRouteRows.find(item => item.role === agentRouteRole) || {
        role: agentRouteRole,
        provider: selectedAgentRoute.provider,
        model: selectedAgentRoute.model,
        effort: selectedAgentRoute.effort,
      },
    [
      agentRouteRole,
      effectiveRouteRows,
      selectedAgentRoute.effort,
      selectedAgentRoute.model,
      selectedAgentRoute.provider,
    ],
  );
  const builderStudioCards = useMemo(
    () => [
      {
        id: "runtime",
        eyebrow: "Runtime studio",
        title: "Hermes and OpenClaw",
        detail: "Update runtimes, inspect service drift, and repair failing bridges without leaving the shell.",
        meta: `${viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount} need attention · ${viewModel.drawers.builder.serviceStudio.availableActionCount} actions`,
        tone:
          viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount > 0 ? "warn" : "good",
      },
      {
        id: "skills",
        eyebrow: "Skill studio",
        title: "Reusable capability packs",
        detail: "Review skill coverage, tighten quality, and keep execution-ready packs visible.",
        meta: `${viewModel.drawers.builder.skillStudio.summary.executionReadyCount} ready · ${viewModel.drawers.builder.skillStudio.summary.needsTestCount} need tests`,
        tone:
          viewModel.drawers.builder.skillStudio.summary.needsTestCount > 0 ? "warn" : "neutral",
      },
      {
        id: "profiles",
        eyebrow: "Routing studio",
        title: "Profiles and model routes",
        detail: "Pin planner, executor, and verifier behavior when the default profile is not enough.",
        meta: `${viewModel.drawers.builder.profileStudio.profileRows.length} profiles · ${effectiveRouteRows.length} active route role${effectiveRouteRows.length === 1 ? "" : "s"}`,
        tone: "neutral",
      },
      {
        id: "proof",
        eyebrow: "Review studio",
        title: "Proof, queue, and release truth",
        detail: "Audit what is ready, what is secondary, and what still needs explicit operator review.",
        meta: `${viewModel.drawers.builder.reviewCount} review surface${viewModel.drawers.builder.reviewCount === 1 ? "" : "s"} · ${viewModel.drawers.builder.confidence.score}% confidence`,
        tone: viewModel.drawers.builder.confidence.tone,
      },
    ],
    [
      effectiveRouteRows.length,
      viewModel.drawers.builder.confidence.score,
      viewModel.drawers.builder.confidence.tone,
      viewModel.drawers.builder.profileStudio.profileRows.length,
      viewModel.drawers.builder.reviewCount,
      viewModel.drawers.builder.serviceStudio.availableActionCount,
      viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount,
      viewModel.drawers.builder.skillStudio.summary.executionReadyCount,
      viewModel.drawers.builder.skillStudio.summary.needsTestCount,
    ],
  );
  const workspaceGitSnapshot = workspace?.gitSnapshot || {};
  const branchInspectAction = useMemo(
    () =>
      asList(viewModel.drawers.builder.gitActions).find(
        item => item.actionId === "inspect_repo_state",
      ) ||
      asList(viewModel.drawers.builder.gitActions)[0] ||
      null,
    [viewModel.drawers.builder.gitActions],
  );
  const branchPullAction = useMemo(
    () =>
      asList(viewModel.drawers.builder.gitActions).find(
        item => item.actionId === "pull_branch",
      ) || null,
    [viewModel.drawers.builder.gitActions],
  );
  const branchPushAction = useMemo(
    () =>
      asList(viewModel.drawers.builder.gitActions).find(
        item => item.actionId === "push_branch",
      ) || null,
    [viewModel.drawers.builder.gitActions],
  );
  const sidebarAccessLabel = previewMode === "live" ? "Full access" : "Read-only preview";
  const sidebarLocalPath = workspace?.root_path || snapshot?.workspaceRoot || "";
  const sidebarLocalLeaf = pathLeaf(sidebarLocalPath) || "workspace";
  const sidebarBranchName = String(workspaceGitSnapshot?.branch || "").trim() || "No branch";
  const sidebarBranchTone = !workspaceGitSnapshot?.repoDetected
    ? "warn"
    : workspaceGitSnapshot?.dirty ||
        Number(workspaceGitSnapshot?.behind || 0) > 0
      ? "warn"
      : "good";
  const sidebarBranchContext = !workspaceGitSnapshot?.repoDetected
    ? "Git repository not detected for selected workspace."
    : [
        workspaceGitSnapshot?.trackingBranch
          ? `tracking ${workspaceGitSnapshot.trackingBranch}`
          : "no tracking branch",
        `${workspaceGitSnapshot?.stagedCount || 0} staged`,
        `${workspaceGitSnapshot?.unstagedCount || 0} unstaged`,
        `${workspaceGitSnapshot?.untrackedCount || 0} untracked`,
      ].join(" · ");

  const handleSidebarAccess = useCallback(() => {
    markAction("quick:access");
    setUiMode("builder");
    setActiveDrawer("settings");
  }, [markAction]);

  const handleSidebarLocal = useCallback(() => {
    markAction("quick:local");
    if (workspaces.length === 0) {
      setShowWorkspaceDialog(true);
      return;
    }
    const fallbackWorkspaceId = workspaces[0]?.workspace_id || "";
    const targetWorkspaceId = workspace?.workspace_id || fallbackWorkspaceId;
    if (targetWorkspaceId) {
      setSelectedWorkspaceId(targetWorkspaceId);
    }
    setUiMode("agent");
    setActiveDrawer(agentBlockedState.isBlocked ? agentBlockedState.defaultDrawer : null);
  }, [
    agentBlockedState.defaultDrawer,
    agentBlockedState.isBlocked,
    markAction,
    workspace?.workspace_id,
    workspaces,
  ]);

  const handleSidebarFolders = useCallback(() => {
    markAction("quick:folders");
    setUiMode("builder");
    setActiveDrawer("builder");
  }, [markAction]);

  const handleSidebarBranch = useCallback(async () => {
    markAction("quick:branch");
    if (branchInspectAction) {
      await runWorkspaceActionSpec(branchInspectAction);
      return;
    }
    setUiMode("builder");
    setActiveDrawer("builder");
  }, [branchInspectAction, markAction, runWorkspaceActionSpec]);

  const handleSidebarBranchPull = useCallback(async () => {
    if (!branchPullAction) {
      return;
    }
    await runWorkspaceActionSpec(branchPullAction);
  }, [branchPullAction, runWorkspaceActionSpec]);

  const handleSidebarBranchPush = useCallback(async () => {
    if (!branchPushAction) {
      return;
    }
    await runWorkspaceActionSpec(branchPushAction);
  }, [branchPushAction, runWorkspaceActionSpec]);

  useEffect(() => {
    currentMissionRef.current = mission;
  }, [mission]);

  useEffect(() => {
    currentDelegatedSessionsRef.current = delegatedSessions;
  }, [delegatedSessions]);

  const agentTranscript = useMemo(() => {
    const timelineTurns = [];
    const seenTurnKeys = new Set();
    const pushTurn = item => {
      if (!item || (!item.title && !item.detail)) {
        return;
      }
      const timestampRaw = item.timestampRaw || "";
      const dedupeKey =
        item.dedupeKey ||
        [
          item.role || "",
          item.label || "",
          item.title || "",
          item.detail || "",
          timestampRaw,
        ].join("|");
      if (seenTurnKeys.has(dedupeKey)) {
        return;
      }
      seenTurnKeys.add(dedupeKey);
      timelineTurns.push({
        ...item,
        timestampRaw,
        sortValue: Number.isFinite(item.sortValue) ? item.sortValue : timeValue(timestampRaw),
        sortOrder: timelineTurns.length,
      });
    };

    for (const note of operatorNotes) {
      pushTurn({
        id: `operator-${note.id}`,
        dedupeKey: `operator:${note.id}`,
        role: "operator",
        roleIcon: "◉",
        label: note.channel === "followup" ? "Follow-up sent" : "Operator note",
        title: note.detail,
        detail: note.meta,
        meta: timestampLabel(note.createdAt),
        timestampRaw: note.createdAt,
        tone: note.tone || "neutral",
        chatPreferred: note.channel === "followup",
      });
    }

    const codeArtifacts = asList(
      mission?.state?.code_execution?.artifacts ||
        mission?.missionLoop?.codeExecution?.artifacts,
    )
      .slice()
      .reverse()
      .slice(0, 4);
    for (const artifact of codeArtifacts) {
      pushTurn({
        id: `code-artifact-${artifact.artifact_id || artifact.created_at || artifact.action_id}`,
        dedupeKey: `code-artifact:${artifact.artifact_id || artifact.created_at || artifact.action_id}`,
        role: "runtime",
        runtimeId: mission?.runtime_id || "",
        roleLabel: "Code execution",
        roleIcon: "◇",
        label: titleizeToken(artifact.kind || "artifact"),
        title: artifact.title || artifact.action_id || "Code execution artifact",
        detail: artifact.summary || "No summary captured.",
        meta: timestampLabel(artifact.created_at),
        timestampRaw: artifact.created_at,
        tone: artifact.ok ? "neutral" : "bad",
        processMessage: true,
        emphasis: true,
        traceOnly: true,
        chips: [
          artifact.container_id ? artifact.container_id : "",
          artifact.runtime ? titleizeToken(artifact.runtime) : "",
        ].filter(Boolean),
      });
    }

    for (const action of asList(mission?.action_history).slice(-6)) {
      const actionKind = action?.proposal?.kind || action?.action_id || "action";
      const actionGatePending = action?.gate?.status === "pending";
      const actionStdout = action?.result?.stdout || "";
      const actionError = action?.result?.error || "";
      const actionRuntimeLike =
        action?.proposal?.sourceKind === "delegated" ||
        /runtime|delegate|test|verify|command/i.test(actionKind);
      const actionResult = actionError || actionStdout;
      if (actionGatePending || !actionResult) {
        continue;
      }
      pushTurn({
        id: `action-${action?.action_id || actionKind}-${action?.executed_at || actionResult}`,
        dedupeKey: `action:${action?.action_id || actionKind}:${action?.executed_at || actionResult}`,
        role: actionRuntimeLike ? "runtime" : "system",
        runtimeId: actionRuntimeLike ? mission?.runtime_id : "",
        roleLabel:
          actionRuntimeLike
            ? runtimeLabel(mission?.runtime_id)
            : "Fluxio",
        roleIcon:
          actionRuntimeLike ? (mission?.runtime_id === "hermes" ? "⬢" : "◇") : "·",
        label: actionRuntimeLike ? "Process message" : titleizeToken(actionKind),
        title: action?.proposal?.title || action?.action_id || "Mission action",
        detail: actionResult,
        technicalDetail: actionStdout && actionStdout !== actionResult ? actionStdout : "",
        technicalSummary: actionStdout && actionStdout !== actionResult ? "Thinking trace" : "",
        meta: timestampLabel(action?.executed_at),
        timestampRaw: action?.executed_at,
        tone: actionError ? "bad" : "neutral",
        processMessage: actionRuntimeLike,
        emphasis: Boolean(actionError || actionRuntimeLike),
        traceOnly: true,
      });
    }

    for (const event of liveControlEvents) {
      if (!event.processMessage && event.role !== "operator" && event.role !== "bridge") {
        continue;
      }
      pushTurn({
        ...event,
        dedupeKey: `live:${event.role || ""}:${event.kind || ""}:${event.title || ""}:${event.timestampRaw || ""}`,
      });
    }

    for (const session of delegatedSessions) {
      const delegatedMessageId =
        session.delegated_id ||
        `${session.runtime_id || "runtime"}-${session.updated_at || session.last_event || "session"}`;
      const latestEvents = asList(session.latest_events);
      const meaningfulEvents = latestEvents.filter(
        event =>
          isTraceRuntimeKind(event.kind) ||
          ["runtime.phase_entered", "runtime.route_switch_reason", "runtime.handoff"].includes(
            String(event.kind || "").toLowerCase(),
          ) ||
          event.status === "failed",
      );
      if (meaningfulEvents.length === 0 && (session.status === "failed" || session.heartbeat_status === "stale")) {
        pushTurn({
          id: `delegated-${delegatedMessageId}`,
          dedupeKey: `delegated:${delegatedMessageId}`,
          role: "runtime",
          runtimeId: session.runtime_id,
          roleLabel: runtimeLabel(session.runtime_id),
          roleIcon: session.runtime_id === "hermes" ? "⬢" : "◇",
          label: `${runtimeLabel(session.runtime_id)} lane`,
          title:
            session.detail ||
            session.last_event ||
            `${runtimeLabel(session.runtime_id)} session ${titleizeToken(session.status || "active")}`,
          detail:
            session.heartbeat_status === "stale"
              ? "Heartbeat is stale. Builder runtime view can inspect the lane in detail."
              : session.execution_target_detail ||
                session.execution_root ||
                "Delegated runtime lane is being supervised from Fluxio.",
          meta: timestampLabel(session.updated_at),
          timestampRaw: session.updated_at,
          tone:
            session.heartbeat_status === "stale"
              ? "warn"
              : session.status === "failed"
                ? "bad"
                : "neutral",
          emphasis: session.status === "failed" || session.heartbeat_status === "stale",
          traceOnly: true,
          chips: [
            titleizeToken(session.status || "unknown"),
            session.execution_target ? titleizeToken(session.execution_target) : "",
          ].filter(Boolean),
        });
      }

      for (const [index, event] of meaningfulEvents.slice(-4).entries()) {
        const processMessage = isTraceRuntimeKind(event.kind);
        const normalizedKind = String(event.kind || "").toLowerCase();
        const routeSwitch = normalizedKind === "runtime.route_contract";
        const phaseEntered = normalizedKind === "runtime.phase_entered";
        const routeSwitchReason = normalizedKind === "runtime.route_switch_reason";
        const handoffEvent = normalizedKind === "runtime.handoff";
        pushTurn({
          id: `delegated-${delegatedMessageId}-event-${event.event_id || index}`,
          dedupeKey: `delegated-event:${delegatedMessageId}:${event.event_id || event.message || index}`,
          role: "runtime",
          runtimeId: session.runtime_id,
          roleLabel: runtimeLabel(session.runtime_id),
          roleIcon: session.runtime_id === "hermes" ? "⬢" : "◇",
          label: phaseEntered
            ? "Phase entered"
            : routeSwitchReason
              ? "Route switch reason"
              : handoffEvent
                ? "Runtime handoff"
                : processMessage
                  ? "Process message"
                  : titleizeToken(event.kind || "runtime event"),
          title: event.message || "Runtime event",
          detail:
            (phaseEntered
              ? `${titleizeToken(event?.data?.phase || "execute")} phase via ${titleizeToken(
                  event?.data?.role || "route",
                )}${event?.data?.provider ? ` · ${titleizeToken(event.data.provider)}` : ""}${event?.data?.model ? ` · ${event.data.model}` : ""}`
              : routeSwitchReason
                ? event?.data?.reason || event.message || "Route switch reason emitted by runtime supervision."
                : handoffEvent
                  ? event?.data?.reason || event.message || "Runtime handoff emitted by supervision."
                  : routeSwitch
              ? `${titleizeToken(event?.data?.phase || "execute")} phase · ${titleizeToken(
                  event?.data?.role || "route",
                )} route`
              : event.detail) ||
            (processMessage
              ? session.execution_target_detail || "Delegated runtime process output."
              : session.execution_target_detail ||
                "Delegated runtime supervision is still flowing into the thread."),
          meta: timestampLabel(event.created_at || session.updated_at),
          timestampRaw: event.created_at || session.updated_at,
          tone:
            event.status === "failed"
              ? "bad"
              : /approval|blocked|stale/i.test(`${event.kind || ""} ${event.message || ""}`)
                ? "warn"
                : "neutral",
          technicalDetail:
            processMessage
              ? event.trace ||
                session.detail ||
                session.execution_target_detail ||
                session.execution_root ||
                ""
              : "",
          technicalSummary: processMessage ? "Thinking trace" : "",
          processMessage,
          chatPreferred: processMessage && !isRuntimeRouteMetaKind(event.kind),
          traceOnly: !processMessage || isRuntimeRouteMetaKind(event.kind),
          emphasis:
            processMessage ||
            phaseEntered ||
            routeSwitchReason ||
            handoffEvent ||
            event.status === "failed" ||
            /approval|blocked|error/i.test(`${event.kind || ""} ${event.message || ""}`),
          chips: [
            session.status ? titleizeToken(session.status) : "",
            session.execution_target ? titleizeToken(session.execution_target) : "",
            routeSwitch && event?.data?.phase ? titleizeToken(event.data.phase) : "",
            routeSwitch && event?.data?.role ? titleizeToken(event.data.role) : "",
            phaseEntered && event?.data?.provider ? titleizeToken(event.data.provider) : "",
            phaseEntered && event?.data?.model ? event.data.model : "",
            routeSwitchReason && event?.data?.reason ? event.data.reason : "",
            handoffEvent && event?.data?.source_delegated_id ? event.data.source_delegated_id : "",
            event.status ? titleizeToken(event.status) : "",
          ].filter(Boolean),
        });
      }
    }

    for (const activity of asList(snapshot.activity).slice(0, 12)) {
      const kind = activity?.kind || "activity";
      const activityMissionId =
        activity?.mission_id ||
        activity?.missionId ||
        activity?.metadata?.mission_id ||
        activity?.metadata?.missionId ||
        "";
      if (activityMissionId && activityMissionId !== mission?.mission_id) {
        continue;
      }
      const role = /bridge|app/i.test(kind)
        ? "bridge"
        : /approval|question/i.test(kind)
          ? "queue"
          : /runtime|delegate|verification|activity/i.test(kind)
            ? "runtime"
            : "system";
      const isOperatorFollowUp = kind === "mission.follow_up";
      const operatorPrompt = isOperatorFollowUp
        ? splitOperatorSteeringMessage(activity?.message || "")
        : null;
      if (!isOperatorFollowUp && role !== "bridge" && role !== "queue") {
        continue;
      }
      pushTurn({
        id: `activity-${kind}-${activity?.timestamp || activity?.message}`,
        dedupeKey: `activity:${kind}:${activity?.message || ""}:${activity?.timestamp || ""}`,
        role: isOperatorFollowUp ? "operator" : role,
        roleLabel:
          isOperatorFollowUp
            ? "Operator"
            : role === "bridge"
            ? "Bridge"
            : role === "queue"
              ? "Needs attention"
              : role === "runtime"
                ? "Runtime"
                : "Fluxio",
        roleIcon:
          isOperatorFollowUp
            ? "◉"
            : role === "bridge"
              ? "⌁"
              : role === "queue"
                ? "!"
                : role === "runtime"
                  ? "◇"
                  : "·",
        label: titleizeToken(kind),
        title: operatorPrompt?.visibleText || activity?.message || "Activity update",
        detail: operatorPrompt?.steeringHints?.join(" · ") || activity?.detail || "",
        meta: timestampLabel(activity?.timestamp),
        timestampRaw: activity?.timestamp,
        tone: role === "queue" ? "warn" : activity?.tone || "neutral",
        technicalDetail:
          operatorPrompt?.steeringHints?.length > 0
            ? operatorPrompt.steeringHints.join("\n")
            : "",
        technicalSummary:
          operatorPrompt?.steeringHints?.length > 0 ? "Routing note" : "",
        chatPreferred: isOperatorFollowUp,
        traceOnly: !isOperatorFollowUp,
      });
    }

    for (const message of data.openClawMessages) {
      pushTurn({
        id: `openclaw-${message.id}`,
        dedupeKey: `openclaw:${message.id || message.createdAt || message.detail}`,
        role: "runtime",
        runtimeId: "openclaw",
        roleLabel: "OpenClaw",
        roleIcon: "◇",
        label: "Process message",
        title: message.detail,
        detail: message.meta || "Gateway message",
        meta: timestampLabel(message.createdAt),
        timestampRaw: message.createdAt,
        tone: message.tone || "neutral",
        processMessage: true,
        emphasis: true,
        chatPreferred: true,
      });
    }

    const sortedTurns = timelineTurns
      .filter(item => item.title || item.detail)
      .sort((left, right) => {
        const leftHasTime = Number.isFinite(left.sortValue);
        const rightHasTime = Number.isFinite(right.sortValue);
        if (leftHasTime && rightHasTime && left.sortValue !== right.sortValue) {
          return left.sortValue - right.sortValue;
        }
        if (leftHasTime !== rightHasTime) {
          return leftHasTime ? -1 : 1;
        }
        return left.sortOrder - right.sortOrder;
      });

    return sortedTurns
      .filter(item => !item.heartbeat)
      .map(({ sortOrder, sortValue, ...item }) => item);
  }, [
    data.openClawMessages,
    data.pendingApprovals,
    data.pendingQuestions,
    delegatedSessions,
    liveControlEvents,
    mission,
    operatorNotes,
    snapshot.activity,
  ]);
  const agentVisibleTranscript = useMemo(
    () =>
      agentTranscript.filter(item => {
        if (!mission || agentRuntimeFocus === "all") {
          return true;
        }
        if (item.role !== "runtime") {
          return true;
        }
        return !item.runtimeId || item.runtimeId === agentRuntimeFocus;
      }),
    [agentRuntimeFocus, agentTranscript, mission],
  );
  const agentConversationTurns = useMemo(
    () =>
      agentTranscript.filter(item => {
        if (item.traceOnly) {
          return false;
        }
        if (item.chatPreferred) {
          return true;
        }
        return item.role === "operator";
      }),
    [agentTranscript],
  );
  const agentTraceTurns = useMemo(
    () =>
      agentVisibleTranscript.filter(item => {
        if (item.traceOnly) {
          return true;
        }
        if (item.role === "queue" || item.role === "system") {
          return true;
        }
        return Boolean(item.technicalDetail);
      }),
    [agentVisibleTranscript],
  );
  const agentThinkingTurns = useMemo(
    () => agentTraceTurns.filter(item => item.processMessage || item.technicalDetail),
    [agentTraceTurns],
  );
  const agentNexusTurns = useMemo(() => {
    const direct = agentTraceTurns.filter(item => {
      const text = `${item.label || ""} ${item.title || ""} ${item.detail || ""}`.toLowerCase();
      return (
        pinnedNexusIds.includes(item.id) ||
        item.role === "queue" ||
        item.tone === "bad" ||
        /approval|verification|blocked|replan|switch|route|review|deploy|patch/.test(text) ||
        (item.processMessage && /plan|patch|review|approval|verify|switch/.test(text))
      );
    });
    return direct.slice(-6);
  }, [agentTraceTurns, pinnedNexusIds]);
  const agentHasTurns = agentConversationTurns.length > 0;
  const agentIdleState = !mission ? "no-mission" : agentHasTurns ? "active" : "no-turns";
  const agentCenterTitle = mission?.title || mission?.objective || workspace?.name || "Fluxio workspace";
  const agentComposerLabel = !mission ? "Mission prompt" : "Follow-up or note";
  const agentComposerPlaceholder = !mission
    ? workspaces.length > 0
      ? "Describe the next mission you want Fluxio to run."
      : "Add a workspace, then describe the next mission you want Fluxio to run."
    : openClawRuntimeActive
      ? "Send a direct follow-up to the runtime, or keep a local operator note."
      : viewModel.thread.composerPlaceholder;
  const handleAgentIdlePrimaryAction = useCallback(() => {
    if (workspaces.length === 0) {
      setShowWorkspaceDialog(true);
      return;
    }
    openMissionDialog();
  }, [openMissionDialog, workspaces.length]);
  const agentRuntimeSelectValue = mission ? agentRuntimeFocus : missionForm.runtime;
  const agentRuntimeHint = !mission
    ? "Choose the runtime for the next mission launch."
    : agentRuntimeFocus === "all"
      ? `Main conversation stays intact. Trace is showing every visible runtime lane. Active lane: ${runtimeLabel(mission?.runtime_id)}.`
      : `Main conversation stays intact. Trace is filtered to ${runtimeLabel(agentRuntimeFocus)} while the chat view keeps the full exchange visible.`;
  const agentCyclePhase =
    mission?.missionLoop?.currentCyclePhase || mission?.state?.current_cycle_phase || "plan";
  const agentCycleRole = phaseRouteRole(agentCyclePhase);
  const agentRouteStatus = `${titleizeToken(activeEffectiveRoute.provider || selectedAgentRoute.provider)} · ${activeEffectiveRoute.model || selectedAgentRoute.model || "Profile default"} · ${
    activeEffectiveRoute.effort || selectedAgentRoute.effort || "default"
  }`;
  const providerSecretPresence = data.providerSecretPresence || {};
  const providerSetupStatus = snapshot?.providerSetupStatus || {};
  const openAIProviderStatus =
    (providerSetupStatus && typeof providerSetupStatus === "object"
      ? providerSetupStatus.openai
      : null) || {};
  const minimaxProviderStatus =
    (providerSetupStatus && typeof providerSetupStatus === "object"
      ? providerSetupStatus.minimax
      : null) || {};
  const missionProviderTruth =
    mission?.providerTruth ||
    mission?.missionLoop?.providerTruth ||
    mission?.state?.provider_runtime_truth ||
    {};
  const missionCodeExecutionState =
    mission?.state?.code_execution ||
    mission?.missionLoop?.codeExecution ||
    {};
  const codeExecutionArtifacts = asList(missionCodeExecutionState?.artifacts)
    .slice()
    .reverse()
    .slice(0, 4);
  const openAISecretReady = Boolean(
    providerSecretPresence.openai || providerSecretPresence["openai-codex"],
  );
  const openAICodexAuthReady = Boolean(
    openAIProviderStatus?.authPresent || openAIProviderStatus?.configured || openAISecretReady,
  );
  const openAICodexAuthPath = String(
    openAIProviderStatus?.authPath ||
      (openAISecretReady ? "API key" : "not configured"),
  );
  const minimaxSecretReady = Boolean(
    providerSecretPresence.minimax || providerSecretPresence["minimax-cn"],
  );
  const minimaxAuthReady = Boolean(
    minimaxProviderStatus?.authPresent || minimaxProviderStatus?.configured || minimaxSecretReady,
  );
  const minimaxAuthPath = String(
    minimaxProviderStatus?.authPath ||
      (minimaxSecretReady ? "API key" : "not configured"),
  );
  const modelAuthReady = openAICodexAuthReady || minimaxAuthReady;
  const latestThinkingTurn = agentThinkingTurns[agentThinkingTurns.length - 1] || null;

  const openAuthDrawer = useCallback(() => {
    setUiMode("builder");
    setActiveDrawer("runtime");
    window.setTimeout(() => {
      document.getElementById("provider-auth-panel")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 0);
  }, []);

  useEffect(() => {
    if (previewMode !== "live" || mission || workspaces.length === 0 || modelAuthReady || authPromptedRef.current) {
      return;
    }
    authPromptedRef.current = true;
    openAuthDrawer();
  }, [mission, modelAuthReady, openAuthDrawer, previewMode, workspaces.length]);

  const drawerItems = useMemo(() => {
    const items = [
      {
        id: "queue",
        label: "Queue",
        count: viewModel.drawers.queue.count,
        tone: viewModel.drawers.queue.urgent ? "warn" : "neutral",
      },
      {
        id: "proof",
        label: "Proof",
        count: viewModel.drawers.proof.itemsCount,
        tone: viewModel.drawers.proof.tone,
      },
      {
        id: "context",
        label: "Context",
        count: viewModel.drawers.context.count,
        tone: "neutral",
      },
      {
        id: "skills",
        label: "Skills",
        count: viewModel.drawers.builder.skillStudio.summary.needsTestCount,
        tone:
          viewModel.drawers.builder.skillStudio.summary.needsTestCount > 0 ? "warn" : "neutral",
      },
      {
        id: "runtime",
        label: "Runtime",
        count: viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount,
        tone:
          viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount > 0
            ? "warn"
            : "neutral",
      },
      {
        id: "settings",
        label: "Settings",
        count: 0,
        tone: "neutral",
      },
    ];
    if (uiMode === "builder") {
      items.push({
        id: "profiles",
        label: "Profiles",
        count: viewModel.drawers.builder.profileStudio.profileRows.length,
        tone: "neutral",
      });
      items.push({
        id: "builder",
        label: "Builder",
        count: viewModel.drawers.builder.reviewCount,
        tone: "neutral",
      });
    }
    return items;
  }, [uiMode, viewModel]);
  const visibleDrawerItems = useMemo(
    () =>
      uiMode === "builder"
        ? drawerItems
        : drawerItems.filter(item => agentVisibleDrawers.includes(item.id)),
    [agentVisibleDrawers, drawerItems, uiMode],
  );
  const activeDrawerMeta = useMemo(
    () =>
      visibleDrawerItems.find(item => item.id === activeDrawer) ||
      drawerItems.find(item => item.id === activeDrawer) ||
      null,
    [activeDrawer, drawerItems, visibleDrawerItems],
  );

  const renderDrawerPanel = () => {
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
          {viewModel.drawers.proof.sections.map(section => (
            <section className="drawer-block" key={section.title}>
              <h3>{section.title}</h3>
              <ul>
                {section.items.length > 0 ? (
                  section.items.map(item => <li key={`${section.title}-${item}`}>{listLabel(item)}</li>)
                ) : (
                  <li>Nothing captured yet.</li>
                )}
              </ul>
            </section>
          ))}
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
            <h2>Runtime and integrations</h2>
            <p>Keep Hermes, OpenClaw, and bridge surfaces manageable from one focused review panel.</p>
          </header>

          <section className="drawer-block" id="provider-auth-panel">
            <h3>Provider auth and model tools</h3>
            <div className="context-grid compact-metrics">
              <article className="context-item">
                <span>OpenAI / Codex auth</span>
                <strong>{`${openAICodexAuthPath} · ${openAICodexAuthReady ? "Ready" : "Missing"}`}</strong>
                <p>
                  {openAICodexAuthPath.toLowerCase().includes("chatgpt")
                    ? "Portal auth is configured for Codex sign-in."
                    : "Saved API keys are injected into Fluxio runtime launches."}
                </p>
              </article>
              <article className="context-item">
                <span>MiniMax auth</span>
                <strong>{`${minimaxAuthPath} · ${minimaxAuthReady ? "Ready" : "Missing"}`}</strong>
                <p>
                  {minimaxAuthPath.toLowerCase().includes("oauth")
                    ? "Portal OAuth is treated as a valid runtime auth path even without a stored API key."
                    : "Save a MiniMax API key when the route is configured for API-key auth."}
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
                    : "Route role will appear once the mission resolves planner/executor/verifier usage."}
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
                    "Failures are promoted into this surface when a provider route errors."}
                </p>
              </article>
            </div>

            <div className="drawer-list">
              {PROVIDER_SECRET_OPTIONS.map(item => {
                const hasSecret = Boolean(providerSecretPresence[item.id]);
                const providerTruthRow =
                  (providerSetupStatus && typeof providerSetupStatus === "object"
                    ? providerSetupStatus[item.id]
                    : null) || {};
                return (
                  <article className={`drawer-card ${toneClass(hasSecret ? "good" : "warn")}`} key={`provider-${item.id}`}>
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
                    <Field label={`${item.label} API key`}>
                      <input
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
                      <ActionButton onClick={() => void handleProviderSecretSave(item.id)}>
                        Save key
                      </ActionButton>
                      <ActionButton onClick={() => void handleProviderSecretClear(item.id)}>
                        Clear
                      </ActionButton>
                    </div>
                  </article>
                );
              })}
            </div>

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
            <h3>OpenClaw gateway</h3>
            <div className="context-grid compact-metrics">
              <article className="context-item">
                <span>Gateway</span>
                <strong>{openClawStatus?.connected ? "Connected" : "Disconnected"}</strong>
                <p>{openClawStatus?.gatewayUrl || openClawGatewayUrl || DEFAULT_OPENCLAW_GATEWAY_URL}</p>
              </article>
              <article className="context-item">
                <span>Queued outbound</span>
                <strong>{openClawStatus?.queuedOutbound ?? 0}</strong>
                <p>{openClawStatus?.reconnectAttempt ? `Reconnect ${openClawStatus.reconnectAttempt}` : "No reconnect pressure"}</p>
              </article>
              <article className="context-item">
                <span>Gateway token</span>
                <strong>{data.openClawHasToken ? "Stored" : "Missing"}</strong>
                <p>{openClawStatus?.lastError || "No gateway error reported."}</p>
              </article>
            </div>

            <Field label="Gateway URL">
              <input
                onChange={event => setOpenClawGatewayUrl(event.target.value)}
                placeholder={DEFAULT_OPENCLAW_GATEWAY_URL}
                value={openClawGatewayUrl}
              />
            </Field>
            <Field label="Gateway token">
              <input
                onChange={event => setOpenClawGatewayToken(event.target.value)}
                placeholder={data.openClawHasToken ? "Token stored in keyring" : "Paste a gateway token"}
                type="password"
                value={openClawGatewayToken}
              />
            </Field>
            <div className="drawer-actions">
              <ActionButton onClick={() => void handleOpenClawConnect()} variant="primary">
                Connect gateway
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
              Gateway messaging is live in this app. Builder now surfaces install, repair, and update actions for Hermes and OpenClaw when the backend detects version drift.
            </p>
          </section>

          <section className="drawer-block">
            <h3>Core runtimes</h3>
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
                  <strong>Hermes and OpenClaw are not surfaced by the backend yet.</strong>
                  <p>Once those services report through control-room service management, they will appear here.</p>
                </article>
              )}
            </div>
          </section>

          {mission ? (
            <section className="drawer-block">
              <h3>Mission execution contract</h3>
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
                        {item.effort ? ` · ${titleizeToken(item.effort)} effort` : ""}
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
            <h3>Delegated runtime lanes</h3>
            <div className="drawer-list">
              {delegatedSessions.length > 0 ? (
                delegatedSessions.map(session => (
                  <article
                    className={`drawer-card ${toneClass(session.heartbeat_status === "stale" ? "warn" : session.status === "failed" ? "bad" : "neutral")}`}
                    key={`delegated-session-${session.delegated_id}`}
                  >
                    <span>{runtimeLabel(session.runtime_id)}</span>
                    <strong>{titleizeToken(session.status || "unknown")}</strong>
                    <p>{session.detail || session.last_event || "Delegated runtime lane is active."}</p>
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
                  <strong>No delegated runtime lane is active.</strong>
                  <p>When Hermes or OpenClaw is actively executing, heartbeat, last event, and execution target will show here.</p>
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
                    {Array.isArray(session.active_tasks) && session.active_tasks.length > 0 ? (
                      <div className="pill-row">
                        {session.active_tasks.slice(0, 3).map(item => (
                          <span className="mini-pill muted" key={`bridge-task-${session.session_id}-${item}`}>
                            {item}
                          </span>
                        ))}
                      </div>
                    ) : null}
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
              <Field label="Preferred harness">
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
                    <input
                      list={`route-models-${item.role}`}
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
                      placeholder={item.role === "executor" ? "gpt-5.4-mini" : "gpt-5.4"}
                      value={item.model}
                    />
                  </Field>
                  <datalist id={`route-models-${item.role}`}>
                    {ROUTE_MODEL_OPTIONS.map(option => (
                      <option key={`${item.role}-${option}`} value={option} />
                    ))}
                  </datalist>
                </article>
              ))}
            </div>
            <p className="drawer-footnote">
              Leave a role blank to keep using the routing strategy default. Planner, executor, and verifier overrides are saved into workspace policy and forwarded to the harness.
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
                {FIXTURE_OPTIONS.map(option => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
              </select>
            </Field>
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
      return (
        <section className="drawer-panel">
          <header>
            <h2>Confidence and operations</h2>
            <p>{viewModel.drawers.builder.liveSurface.note}</p>
          </header>

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

          <section className="drawer-block">
            <h3>Road to 100%</h3>
            <p>
              {viewModel.drawers.builder.qualityRoadmap.headline}
              {` · Gap ${viewModel.drawers.builder.qualityRoadmap.gap}%`}
            </p>
            <div className="roadmap-grid">
              {viewModel.drawers.builder.qualityRoadmap.tracks.map(item => (
                <article className={`roadmap-item ${toneClass(item.tone)}`} key={item.id}>
                  <span>{titleizeToken(item.state)}</span>
                  <strong>{item.label}</strong>
                  <p>{item.detail}</p>
                  <p>{item.hint}</p>
                  <div className="drawer-actions">
                    <ActionButton
                      onClick={() => void handleQualityRoadmapAction(item)}
                      type="button"
                    >
                      {item.suggestedAction || "Open"}
                    </ActionButton>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="drawer-block">
            <h3>Live surface</h3>
            <Field label="Preview">
              <select onChange={event => setPreviewMode(event.target.value)} value={previewMode}>
                {FIXTURE_OPTIONS.map(option => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
              </select>
            </Field>
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
              <Field label="Preferred harness">
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
  };

  if (initialLiveSnapshotPending) {
    return (
      <div
        className="fluxio-shell"
        data-drawer="collapsed"
        data-mode={uiMode}
        data-profile={profileId}
      >
        <header className="fluxio-topbar">
          <div className="topbar-app">
            <div className="topbar-context">
              <strong>Fluxio workspace</strong>
              <span>Loading live control-room state</span>
            </div>
          </div>

          <div className="topbar-confidence">
            <span>Workspace state</span>
            <strong className={toneClass("warn")}>Detecting environment</strong>
          </div>
        </header>

        <div className="fluxio-body">
          <main className="fluxio-main">
            <section className="thread-shell agent-shell agent-idle-shell">
              <header className="thread-head agent-thread-head agent-title-head">
                <h1>Loading workspace state</h1>
              </header>

              <article className="builder-panel builder-panel-hero builder-feature-card">
                <p>
                  Fluxio is loading the first live control-room snapshot. Runtime,
                  workspace, and setup detection can take a couple of seconds on startup.
                </p>
                <div className="thread-chip-row">
                  <span className="mini-pill muted">Live backend</span>
                  <span className="mini-pill muted">
                    {isRefreshing ? "Refreshing snapshot" : "Starting snapshot"}
                  </span>
                </div>
                <div className="drawer-actions">
                  <ActionButton
                    onClick={() => void refreshAll("bootstrap-retry")}
                    variant="primary"
                  >
                    Retry now
                  </ActionButton>
                </div>
              </article>
            </section>
          </main>
        </div>
      </div>
    );
  }

  return (
    <div
      className="fluxio-shell"
      data-drawer={showPersistentDrawer ? "open" : "collapsed"}
      data-mode={uiMode}
      data-profile={profileId}
    >
      <header className="fluxio-topbar">
        <div className="topbar-app">
          <div className="app-menu">
            <button aria-label="Fluxio menu" className="app-menu-glyph" type="button">
              +
            </button>
            <MenuButton label="File" onClick={() => setShowWorkspaceDialog(true)} />
            <MenuButton
              label="Edit"
              onClick={() => {
                if (workspaces.length === 0) {
                  setShowWorkspaceDialog(true);
                  return;
                }
                openMissionDialog();
              }}
            />
            <MenuButton
              label="View"
              onClick={() => {
                setUiMode("builder");
                setActiveDrawer("builder");
              }}
            />
            <MenuButton
              label="Window"
              onClick={() => {
                setUiMode("builder");
                setActiveDrawer("runtime");
              }}
            />
            <MenuButton
              label="Help"
              onClick={() => {
                setUiMode("agent");
                setActiveDrawer(agentBlockedState.defaultDrawer);
              }}
            />
          </div>

          <div className="topbar-context">
            <strong>{mission?.title || mission?.objective || workspace?.name || "Fluxio workspace"}</strong>
            <span>{workspace?.name || "Select a workspace"}</span>
          </div>
        </div>

        <div aria-label="Fluxio mode" className="fluxio-mode" role="tablist">
          {["agent", "builder"].map(mode => (
            <button
              aria-selected={uiMode === mode}
              className={uiMode === mode ? "active" : ""}
              key={mode}
              onClick={() => {
                markAction(`mode:${mode}`);
                setUiMode(mode);
                if (mode === "builder") {
                  setActiveDrawer(null);
                  return;
                }
                setActiveDrawer(agentBlockedState.isBlocked ? agentBlockedState.defaultDrawer : null);
              }}
              role="tab"
              type="button"
            >
              {titleizeToken(mode)}
            </button>
          ))}
        </div>

        <div className="topbar-shortcuts">
          <TopbarShortcut
            active={showPersistentDrawer}
            label={showPersistentDrawer && activeDrawerMeta ? `${activeDrawerMeta.label} panel` : "Open panel"}
            onClick={() => {
              markAction("toggle:panel");
              if (uiMode === "builder") {
                setActiveDrawer(current => (current ? null : "builder"));
                return;
              }
              if (agentBlockedState.isBlocked) {
                setActiveDrawer(agentBlockedState.defaultDrawer);
              }
            }}
            tone="neutral"
          />
        </div>

        <div className="topbar-confidence">
          <span>{topbarStatus.label}</span>
          <strong className={toneClass(topbarStatus.tone)}>
            {topbarStatus.value}
          </strong>
        </div>

        <ActionButton onClick={handlePrimaryAction} variant="primary">
          {viewModel.topBar.primaryAction.label}
        </ActionButton>
      </header>

      <div className="fluxio-body">
        <aside className="fluxio-sidebar">
          <div className="fluxio-sidebar-scroll">
            <section className="sidebar-surface-list">
              <GlobalRailButton
                active={uiMode === "agent"}
                icon="◎"
                label="Agent"
                onClick={() => {
                  markAction("rail:operator");
                  setUiMode("agent");
                  setActiveDrawer(agentBlockedState.isBlocked ? agentBlockedState.defaultDrawer : null);
                }}
              />
              {uiMode === "builder" ? (
                <>
                  <GlobalRailButton
                    active={activeDrawer === "builder"}
                    icon="⌘"
                    label="Builder"
                    onClick={() => {
                      markAction("rail:builder");
                      setActiveDrawer(current => (current === "builder" ? null : "builder"));
                    }}
                  />
                  <GlobalRailButton
                    active={activeDrawer === "skills"}
                    icon="✦"
                    label="Skills"
                    onClick={() => {
                      markAction("rail:skills");
                      setSkillStudioFilter("all");
                      setActiveDrawer(current => (current === "skills" ? null : "skills"));
                    }}
                  />
                  <GlobalRailButton
                    active={activeDrawer === "runtime"}
                    icon="◇"
                    label="Runtime"
                    onClick={() => {
                      markAction("rail:runtime");
                      setActiveDrawer(current => (current === "runtime" ? null : "runtime"));
                    }}
                  />
                  <GlobalRailButton
                    active={activeDrawer === "profiles"}
                    icon="◫"
                    label="Profiles"
                    onClick={() => {
                      markAction("rail:profiles");
                      setActiveDrawer(current => (current === "profiles" ? null : "profiles"));
                    }}
                  />
                </>
              ) : null}
            </section>

            <section className="fluxio-nav-section">
              <div className="fluxio-nav-heading">
                <p className="eyebrow">Quick controls</p>
              </div>
              <div className="fluxio-nav-list">
                <NavItem
                  badge={previewMode === "live" ? "full" : "read-only"}
                  context={previewMode === "live" ? "Live backend access is enabled." : "Fixture mode keeps actions read-only."}
                  icon="⛨"
                  onClick={handleSidebarAccess}
                  subtitle={sidebarAccessLabel}
                  title="Access"
                  tone={previewMode === "live" ? "good" : "warn"}
                />
                <NavItem
                  badge={sidebarLocalLeaf}
                  context={sidebarLocalPath || "No workspace selected yet."}
                  icon="⌂"
                  onClick={handleSidebarLocal}
                  subtitle={workspace?.name || "Pick workspace"}
                  title="Local"
                  tone={workspace ? "good" : "warn"}
                />
                <NavItem
                  badge={`${builderRootItems.length} root${builderRootItems.length === 1 ? "" : "s"}`}
                  context={
                    builderPrimaryConversation?.executionPath ||
                    builderPrimaryConversation?.workspacePath ||
                    "Folder map appears once Builder has active conversations."
                  }
                  icon="📁"
                  onClick={handleSidebarFolders}
                  subtitle={builderPrimaryConversation?.folderLabel || "Open folder map"}
                  title="Folders"
                  tone={builderRootItems.length > 0 ? "neutral" : "warn"}
                />
                <NavItem
                  badge={sidebarBranchName}
                  context={sidebarBranchContext}
                  icon="⑂"
                  onClick={() => void handleSidebarBranch()}
                  subtitle={workspaceGitSnapshot?.repoDetected ? "Git branch controls" : "No git workspace"}
                  title="Branch"
                  tone={sidebarBranchTone}
                />
              </div>
              {workspaceGitSnapshot?.repoDetected ? (
                <div className="fluxio-sidebar-branch-actions">
                  <ActionButton onClick={() => void handleSidebarBranch()} type="button">
                    Inspect branch
                  </ActionButton>
                  {branchPullAction ? (
                    <ActionButton onClick={() => void handleSidebarBranchPull()} type="button">
                      Pull
                    </ActionButton>
                  ) : null}
                  {branchPushAction ? (
                    <ActionButton onClick={() => void handleSidebarBranchPush()} type="button">
                      Push
                    </ActionButton>
                  ) : null}
                </div>
              ) : null}
            </section>

            {uiMode === "builder" ? (
              <>
                <section className="fluxio-nav-section">
                  <div className="fluxio-nav-heading">
                    <p className="eyebrow">Board</p>
                    <ActionButton onClick={openMissionDialog}>Launch</ActionButton>
                  </div>
                  <div className="builder-sidebar-metrics">
                    {builderBoard.metrics.slice(0, 3).map(item => (
                      <article className={`builder-sidebar-card ${toneClass(item.tone)}`} key={`builder-rail-${item.id}`}>
                        <span>{item.label}</span>
                        <strong>{item.value}</strong>
                        <p>{item.detail}</p>
                      </article>
                    ))}
                  </div>
                </section>

                <section className="fluxio-nav-section">
                  <div className="fluxio-nav-heading">
                    <p className="eyebrow">Roots</p>
                  </div>
                  <div className="fluxio-nav-list">
                    {builderRootItems.length > 0 ? (
                      builderRootItems.map(item => (
                        <NavItem
                          active={item.workspaceId === selectedWorkspaceId}
                          badge={item.folderLabel || "root"}
                          context={item.path}
                          icon="▣"
                          key={`builder-root-${item.workspaceId}`}
                          onClick={() => setSelectedWorkspaceId(item.workspaceId)}
                          stats={[
                            item.activeCount > 0
                              ? { label: "threads", value: item.activeCount, tone: "good" }
                              : null,
                            item.blockedCount > 0
                              ? { label: "blocked", value: item.blockedCount, tone: "warn" }
                              : null,
                            item.delegatedCount > 0
                              ? { label: "lanes", value: item.delegatedCount, tone: "good" }
                              : null,
                          ].filter(Boolean)}
                          subtitle={item.activeCount > 0 ? "Conversation root" : "Workspace root"}
                          title={item.title}
                          tone={item.tone}
                        />
                      ))
                    ) : (
                      <p className="fluxio-empty-copy">Workspace roots will appear once Builder has projects to supervise.</p>
                    )}
                  </div>
                </section>

                <section className="fluxio-nav-section">
                  <div className="fluxio-nav-heading">
                    <p className="eyebrow">Nexuses</p>
                    <ActionButton onClick={() => setActiveDrawer("context")}>Open</ActionButton>
                  </div>
                  <div className="builder-sidebar-nexus-list">
                    {builderNexusItems.length > 0 ? (
                      builderNexusItems.map(item => (
                        <button
                          className={`builder-sidebar-nexus ${toneClass(item.tone)}`.trim()}
                          key={item.id}
                          onClick={() => {
                            if (item.missionId) {
                              setSelectedMissionId(item.missionId);
                            }
                            setActiveDrawer(item.tone === "bad" ? "proof" : "context");
                          }}
                          type="button"
                        >
                          <span>{item.label}</span>
                          <strong>{item.title}</strong>
                          <p>{item.reason}</p>
                          <em>{item.folderLabel || item.workspaceName}</em>
                        </button>
                      ))
                    ) : (
                      <p className="fluxio-empty-copy">Important operator decisions will collect here.</p>
                    )}
                  </div>
                </section>

                <section className="fluxio-nav-section">
                  <div className="fluxio-nav-heading">
                    <p className="eyebrow">Bridge</p>
                    <ActionButton onClick={() => setActiveDrawer("runtime")}>Inspect</ActionButton>
                  </div>
                  <article className="builder-sidebar-bridge">
                    <span>Hermes ↔ OpenClaw bridge</span>
                    <strong>{bridgeSummary.connected} live app bridge{bridgeSummary.connected === 1 ? "" : "s"}</strong>
                    <p>{bridgeSummary.recommendation}</p>
                    <div className="fluxio-nav-stats">
                      <span className="fluxio-nav-stat tone-good">
                        <strong>{bridgeSummary.callbackReady}</strong>
                        <em>callbacks</em>
                      </span>
                      <span className="fluxio-nav-stat tone-neutral">
                        <strong>{bridgeSummary.totalApps}</strong>
                        <em>apps</em>
                      </span>
                    </div>
                  </article>
                </section>
              </>
            ) : (
              <>
                <section className="fluxio-nav-section">
                  <div className="fluxio-nav-heading">
                    <p className="eyebrow">Workspaces</p>
                    <ActionButton onClick={() => setShowWorkspaceDialog(true)}>Add</ActionButton>
                  </div>
                  <div className="fluxio-nav-list">
                    {workspaceNavItems.length > 0 ? (
                      workspaceNavItems.map(item => (
                        <NavItem
                          active={item.workspaceId === selectedWorkspaceId}
                          badge={item.badge}
                          context={item.context}
                          icon="▣"
                          key={item.workspaceId}
                          onClick={() => setSelectedWorkspaceId(item.workspaceId)}
                          stats={item.stats}
                          subtitle={item.subtitle}
                          title={item.title}
                          tone={item.tone}
                        />
                      ))
                    ) : (
                      <p className="fluxio-empty-copy">Add one workspace to begin.</p>
                    )}
                  </div>
                </section>

                <section className="fluxio-nav-section">
                  <div className="fluxio-nav-heading">
                    <p className="eyebrow">Missions</p>
                    <ActionButton onClick={openMissionDialog}>New</ActionButton>
                  </div>
                  <div className="fluxio-nav-list">
                    {missionOptions.length > 0 ? (
                      missionNavItems.map(item => (
                        <NavItem
                          active={item.missionId === selectedMissionId}
                          badge={item.badge}
                          context={item.context}
                          icon="◆"
                          key={item.missionId}
                          onClick={() => setSelectedMissionId(item.missionId)}
                          stats={item.stats}
                          subtitle={item.subtitle}
                          title={item.title}
                          tone={item.tone}
                        />
                      ))
                    ) : (
                      <p className="fluxio-empty-copy">Mission thread appears after first launch.</p>
                    )}
                  </div>
                </section>
              </>
            )}
          </div>

          <div className="fluxio-sidebar-bottom">
            <GlobalRailButton
              active={activeDrawer === "settings"}
              icon="⚙"
              label="Settings"
              onClick={() => {
                markAction("rail:settings");
                setUiMode("builder");
                setActiveDrawer("settings");
              }}
              subtle
            />
          </div>
        </aside>

        <main className="fluxio-main">
          {!mission ? (
            uiMode === "builder" ? (
              <section className="builder-shell builder-launch-shell">
                <header className="builder-head builder-studio-head">
                  <div>
                    <p className="eyebrow">Builder workbench</p>
                    <h1>{viewModel.emptyState.title}</h1>
                    <p>{viewModel.emptyState.summary}</p>
                  </div>
                  <div className="builder-head-actions">
                    <ActionButton
                      onClick={() => {
                        if (workspaces.length === 0) {
                          setShowWorkspaceDialog(true);
                          return;
                        }
                        openMissionDialog();
                      }}
                      variant="primary"
                    >
                      {viewModel.emptyState.launchEntryLabel}
                    </ActionButton>
                    <ActionButton onClick={() => handleBuilderFeatureAction("open_builder")}>
                      Open panel
                    </ActionButton>
                  </div>
                </header>

                <div className="builder-workbench-grid">
                  <section className="builder-primary-column">
                    <article className="builder-panel builder-panel-hero builder-feature-card">
                      <div className="builder-feature-head">
                        <div>
                          <p className="eyebrow">Guided tutorial</p>
                          <h2>{tutorialStudio.headline}</h2>
                        </div>
                        <div className="builder-feature-meta">
                          <span className="mini-pill muted">{tutorialStudio.progressLabel}</span>
                          <span className="mini-pill muted">{tutorialStudio.motionMode} motion</span>
                        </div>
                      </div>
                      <p>{tutorialStudio.summary}</p>
                      <div className="builder-step-grid">
                        {tutorialStudio.steps.map(item => (
                          <button
                            className={`builder-step-card ${toneClass(item.tone)} ${item.current ? "current" : ""}`.trim()}
                            key={item.id}
                            onClick={() => void handleBuilderFeatureAction(item.actionId)}
                            type="button"
                          >
                            <span>{item.panel}</span>
                            <strong>{item.title}</strong>
                            <p>{item.description}</p>
                            <em>{item.status}</em>
                          </button>
                        ))}
                      </div>
                      {tutorialStudio.cards.length > 0 ? (
                        <div className="builder-inline-list builder-inline-list-actions">
                          {tutorialStudio.cards.map(item => (
                            <button
                              className="builder-inline-action"
                              key={item.id}
                              onClick={() => void handleBuilderFeatureAction(item.actionId)}
                              type="button"
                            >
                              <strong>{item.title}</strong>
                              <span>{item.body}</span>
                            </button>
                          ))}
                        </div>
                      ) : null}
                      <div className="drawer-actions">
                        <ActionButton
                          onClick={() => void handleBuilderFeatureAction(tutorialStudio.primaryActionId)}
                          variant="primary"
                        >
                          {tutorialStudio.primaryActionLabel}
                        </ActionButton>
                        {quickSetupActions.map(action => (
                          <ActionButton
                            key={`builder-empty-${action.actionId}`}
                            onClick={() => void runWorkspaceAction("setup", action.actionId)}
                          >
                            {action.label}
                          </ActionButton>
                        ))}
                      </div>
                    </article>

                    <div className="builder-feature-grid">
                      <article className="builder-panel builder-feature-card">
                        <div className="builder-feature-head">
                          <div>
                            <p className="eyebrow">Recommendations</p>
                            <h2>{recommendationStudio.headline}</h2>
                          </div>
                          <div className="builder-feature-meta">
                            <span className="mini-pill muted">
                              {recommendationStudio.skillRecommendations.length} skill leads
                            </span>
                          </div>
                        </div>
                        <p>{recommendationStudio.summary}</p>
                        <div className="builder-thread-list">
                          {recommendationStudio.struggleSignals.map(item => (
                            <button
                              className={`builder-thread-item ${toneClass(item.tone)}`.trim()}
                              key={item.id}
                              onClick={() => void handleBuilderFeatureAction(item.actionId)}
                              type="button"
                            >
                              <span>{item.label}</span>
                              <strong>{item.detail}</strong>
                            </button>
                          ))}
                        </div>
                        {recommendationStudio.skillRecommendations.length > 0 ? (
                          <div className="builder-inline-list">
                            {recommendationStudio.skillRecommendations.map(item => (
                              <span className="builder-inline-pill" key={item.id}>
                                <strong>{item.label}</strong>
                                <span>{item.reason}</span>
                              </span>
                            ))}
                          </div>
                        ) : null}
                        <div className="drawer-actions">
                          {recommendationStudio.nextMoves.slice(0, 2).map(item => (
                            <ActionButton
                              key={item.id}
                              onClick={() => void handleBuilderFeatureAction(item.actionId)}
                              variant={item === recommendationStudio.nextMoves[0] ? "primary" : "secondary"}
                            >
                              {item.label}
                            </ActionButton>
                          ))}
                        </div>
                      </article>

                      <article className="builder-panel builder-feature-card">
                        <div className="builder-feature-head">
                          <div>
                            <p className="eyebrow">Live UI review</p>
                            <h2>{liveReviewStudio.statusLine}</h2>
                          </div>
                          <div className="builder-feature-meta">
                            <span className="mini-pill muted">{liveReviewStudio.targets.length} review blocks</span>
                          </div>
                        </div>
                        <p>{liveReviewStudio.summary}</p>
                        <div className="builder-review-grid">
                          {liveReviewStudio.targets.map(item => (
                            <button
                              className={`builder-review-target ${toneClass(item.tone)} ${builderSelectedReviewTarget?.id === item.id ? "active" : ""}`.trim()}
                              key={item.id}
                              onClick={() => handleBuilderReviewTargetSeed(item)}
                              type="button"
                            >
                              <span>{item.label}</span>
                              <strong>{item.title}</strong>
                              <p>{item.detail}</p>
                            </button>
                          ))}
                        </div>
                        {builderSelectedReviewTarget ? (
                          <article className={`builder-review-focus ${toneClass(builderSelectedReviewTarget.tone)}`}>
                            <span>{builderSelectedReviewTarget.label}</span>
                            <strong>{builderSelectedReviewTarget.title}</strong>
                            <p>{builderSelectedReviewTarget.detail}</p>
                          </article>
                        ) : null}
                        <div className="drawer-actions">
                          <ActionButton
                            onClick={() => builderSelectedReviewTarget && handleBuilderReviewTargetSeed(builderSelectedReviewTarget)}
                            variant="primary"
                          >
                            Comment selected block
                          </ActionButton>
                          <ActionButton onClick={() => void handleBuilderFeatureAction("open_builder")}>
                            Open preview controls
                          </ActionButton>
                        </div>
                      </article>
                    </div>

                    <article className="builder-panel">
                      <div className="section-header">
                        <div className="section-title-block">
                          <p className="eyebrow">Road to 100%</p>
                          <h2>{viewModel.drawers.builder.qualityRoadmap.headline}</h2>
                        </div>
                      </div>
                      <div className="roadmap-grid">
                        {viewModel.drawers.builder.qualityRoadmap.tracks.slice(0, 4).map(item => (
                          <article className={`roadmap-item ${toneClass(item.tone)}`} key={`empty-roadmap-${item.id}`}>
                            <span>{titleizeToken(item.state)}</span>
                            <strong>{item.label}</strong>
                            <p>{item.detail}</p>
                            <ActionButton onClick={() => void handleQualityRoadmapAction(item)}>
                              {item.suggestedAction || "Open"}
                            </ActionButton>
                          </article>
                        ))}
                      </div>
                    </article>
                  </section>

                  <aside className="builder-secondary-column">
                    <article className="builder-panel builder-panel-focus">
                      <p className="eyebrow">Guided readiness</p>
                      <h3>{tutorialStudio.recommendedWorkflow}</h3>
                      <p>{viewModel.emptyState.qualityRoadmapHeadline}</p>
                      <div className="builder-inline-list">
                        {tutorialStudio.readiness.map(item => (
                          <span key={`readiness-${item}`}>{item}</span>
                        ))}
                      </div>
                    </article>

                    <article className="builder-panel builder-panel-focus">
                      <p className="eyebrow">Profiles</p>
                      <h3>{titleizeToken(workspaceProfileForm.userProfile)}</h3>
                      <p>{viewModel.drawers.builder.profileStudio.behavior[0]?.value || "No profile selected."}</p>
                      <ActionButton onClick={() => void handleBuilderFeatureAction("open_profiles")}>
                        Open profiles
                      </ActionButton>
                    </article>

                    <article className="builder-panel builder-panel-focus">
                      <p className="eyebrow">Feature backlog</p>
                      <h3>
                        {tutorialStudio.improvements.length + recommendationStudio.learningQueue.length} queued improvement{tutorialStudio.improvements.length + recommendationStudio.learningQueue.length === 1 ? "" : "s"}
                      </h3>
                      <div className="builder-thread-list">
                        {tutorialStudio.improvements.map(item => (
                          <article className={`builder-thread-item ${toneClass(item.tone)}`} key={item.id}>
                            <span>{item.category}</span>
                            <strong>{item.title}</strong>
                            <p>{item.reason}</p>
                          </article>
                        ))}
                        {recommendationStudio.learningQueue.map(item => (
                          <article className={`builder-thread-item ${toneClass(item.tone)}`} key={item.id}>
                            <span>{item.priority}</span>
                            <strong>{item.title}</strong>
                            <p>Turn repeated friction into a reviewed skill or workflow.</p>
                          </article>
                        ))}
                      </div>
                      <ActionButton onClick={() => void handleBuilderFeatureAction("open_skills")}>
                        Open improvement flow
                      </ActionButton>
                    </article>
                  </aside>
                </div>
              </section>
            ) : (
              <section className="thread-shell agent-shell agent-idle-shell">
                <header className="thread-head agent-thread-head agent-title-head">
                  <h1>{agentCenterTitle}</h1>
                </header>

                <form
                  className="thread-composer agent-composer agent-chat-composer agent-idle-composer"
                  onSubmit={event => event.preventDefault()}
                >
                  <div className="agent-control-grid">
                    <Field label="Launch runtime">
                      <select
                        onChange={event =>
                          setMissionForm(current => ({ ...current, runtime: event.target.value }))
                        }
                        value={missionForm.runtime}
                      >
                        {runtimeOptions.map(option => (
                          <option key={`idle-runtime-${option.value}`} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Route role">
                      <select onChange={event => setAgentRouteRole(event.target.value)} value={agentRouteRole}>
                        {ROUTE_ROLE_OPTIONS.map(option => (
                          <option key={`idle-role-${option}`} value={option}>
                            {titleizeToken(option)}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Provider">
                      <select
                        onChange={event => handleAgentRouteFieldChange("provider", event.target.value)}
                        value={selectedAgentRoute.provider}
                      >
                        {MODEL_PROVIDER_OPTIONS.map(option => (
                          <option key={`idle-provider-${option.value}`} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Model">
                      <input
                        list="agent-route-models-idle"
                        onChange={event => handleAgentRouteFieldChange("model", event.target.value)}
                        placeholder="Profile default"
                        value={selectedAgentRoute.model}
                      />
                      <datalist id="agent-route-models-idle">
                        {ROUTE_MODEL_OPTIONS.map(option => (
                          <option key={`idle-model-${option}`} value={option} />
                        ))}
                      </datalist>
                    </Field>
                    <Field label="Reasoning">
                      <select
                        onChange={event => handleAgentRouteFieldChange("effort", event.target.value)}
                        value={selectedAgentRoute.effort || "default"}
                      >
                        {MODEL_EFFORT_OPTIONS.map(option => (
                          <option key={`idle-effort-${option.value}`} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </Field>
                  </div>
                  <div className="agent-control-strip">
                    <p>{agentRuntimeHint}</p>
                    <div className="thread-chip-row">
                      <span className="mini-pill muted">{agentRouteStatus}</span>
                      <span className="mini-pill muted">{titleizeToken(agentRouteRole)} route</span>
                      <span className="mini-pill muted">
                        Code execution {codeExecutionEnabled ? "on" : "off"}
                      </span>
                      <span className="mini-pill muted">
                        {modelAuthReady ? "Model auth ready" : "Model auth missing"}
                      </span>
                    </div>
                    <div className="thread-composer-actions">
                      <ActionButton onClick={() => void handleAgentRouteSave()} type="button">
                        Apply route
                      </ActionButton>
                      <ActionButton
                        onClick={() => setCodeExecutionEnabled(current => !current)}
                        type="button"
                      >
                        {codeExecutionEnabled ? "Disable code execution" : "Enable code execution"}
                      </ActionButton>
                    </div>
                  </div>
                  <label htmlFor="thread-note-idle">{agentComposerLabel}</label>
                  <textarea
                    id="thread-note-idle"
                    onChange={event => setOperatorDraft(event.target.value)}
                    placeholder={agentComposerPlaceholder}
                    value={operatorDraft}
                  />
                  <div className="thread-composer-actions">
                    <ActionButton onClick={handleAgentIdlePrimaryAction} type="button" variant="primary">
                      {workspaces.length > 0 ? "Launch mission" : "Add workspace"}
                    </ActionButton>
                  </div>
                </form>
              </section>
            )
          ) : uiMode === "builder" ? (
            <section className="builder-shell">
              <header className="builder-head builder-studio-head">
                <div>
                  <p className="eyebrow">Conversation command board</p>
                  <h1>{viewModel.thread.title}</h1>
                  <p>{builderBoard.summary}</p>
                </div>
                <div className="builder-head-actions">
                  <ActionButton onClick={() => setActiveDrawer("builder")} variant="primary">
                    Open panel
                  </ActionButton>
                  <ActionButton onClick={openMissionDialog}>Launch mission</ActionButton>
                </div>
              </header>

              <div className="builder-workbench-grid">
                <section className="builder-primary-column">
                  <article className="builder-panel builder-panel-hero builder-command-deck">
                    <div className="builder-command-head">
                      <div className="builder-command-copy">
                        <p className="eyebrow">{builderBoard.headline}</p>
                        {builderPrimaryConversation ? (
                          <>
                            <div className="thread-chip-row">
                              <StatusPill tone={builderPrimaryConversation.blocked ? "warn" : builderPrimaryConversation.tone}>
                                {builderPrimaryConversation.runtime}
                              </StatusPill>
                              <StatusPill tone="neutral">{builderPrimaryConversation.harnessLabel}</StatusPill>
                              <StatusPill strong tone={builderPrimaryConversation.blocked ? "warn" : builderPrimaryConversation.tone}>
                                {builderPrimaryConversation.statusLabel}
                              </StatusPill>
                            </div>
                            <h2>{builderPrimaryConversation.title}</h2>
                            <p>{builderPrimaryConversation.current}</p>
                            <p className="builder-conversation-path">
                              {builderPrimaryConversation.workspaceName}
                              {builderPrimaryConversation.executionPath ? ` · ${builderPrimaryConversation.executionPath}` : ""}
                            </p>
                            <div className="builder-primary-summary">
                              <article className="builder-summary-card">
                                <span>Current point</span>
                                <strong>{builderPrimaryConversation.current}</strong>
                                <p>{builderPrimaryConversation.lastMovement}</p>
                              </article>
                              <article className="builder-summary-card">
                                <span>Next step</span>
                                <strong>{builderPrimaryConversation.next}</strong>
                                <p>{builderPrimaryConversation.updatedAt ? `Updated ${timestampLabel(builderPrimaryConversation.updatedAt)}` : "Active now"}</p>
                              </article>
                            </div>
                          </>
                        ) : (
                          <>
                            <h2>{viewModel.drawers.builder.confidence.label}</h2>
                            <p>{builderBoard.summary}</p>
                          </>
                        )}
                      </div>

                      <div className="builder-board-metrics">
                        {builderBoard.metrics.map(item => (
                          <article className={`builder-metric-card ${toneClass(item.tone)}`} key={item.id}>
                            <span>{item.label}</span>
                            <strong>{item.value}</strong>
                            <p>{item.detail}</p>
                          </article>
                        ))}
                      </div>
                    </div>

                    <div className="drawer-actions">
                      {builderPrimaryConversation ? (
                        <ActionButton onClick={() => setSelectedMissionId(builderPrimaryConversation.missionId)} variant="primary">
                          Focus thread
                        </ActionButton>
                      ) : null}
                      <ActionButton onClick={() => setActiveDrawer("builder")} variant="primary">
                        Command panel
                      </ActionButton>
                      <ActionButton onClick={() => setActiveDrawer("queue")}>Queue review</ActionButton>
                      <ActionButton onClick={() => setActiveDrawer("proof")}>Proof review</ActionButton>
                      <ActionButton onClick={() => setActiveDrawer("context")}>Context</ActionButton>
                    </div>
                  </article>

                  <article className="builder-panel">
                    <div className="section-header">
                      <div className="section-title-block">
                        <p className="eyebrow">Other Active Conversations</p>
                        <h2>Smaller live threads around the main focus</h2>
                      </div>
                    </div>
                    {builderSecondaryConversations.length > 0 ? (
                      <div className="builder-conversation-grid">
                        {builderSecondaryConversations.map(item => (
                          <button
                            className={`builder-conversation-card ${toneClass(item.tone)} ${item.selected ? "active" : ""}`.trim()}
                            key={item.missionId}
                            onClick={() => setSelectedMissionId(item.missionId)}
                            type="button"
                          >
                            <div className="builder-conversation-top">
                              <div>
                                <span>{item.runtime} · {item.workspaceName}</span>
                                <h3>{item.title}</h3>
                              </div>
                              <StatusPill strong tone={item.blocked ? "warn" : item.tone}>
                                {item.statusLabel}
                              </StatusPill>
                            </div>
                            <p>{item.current}</p>
                            {item.executionPath ? (
                              <p className="builder-conversation-path">
                                {item.folderLabel ? `${item.folderLabel} · ` : ""}
                                {item.executionPath}
                              </p>
                            ) : null}
                            <div className="builder-conversation-meta">
                              {item.pendingApprovals > 0 ? (
                                <span>{item.pendingApprovals} approval{item.pendingApprovals === 1 ? "" : "s"}</span>
                              ) : null}
                              {item.verificationFailures > 0 ? (
                                <span>{item.verificationFailures} verification issue{item.verificationFailures === 1 ? "" : "s"}</span>
                              ) : null}
                              {item.delegatedSessions > 0 ? (
                                <span>{item.delegatedSessions} delegated lane{item.delegatedSessions === 1 ? "" : "s"}</span>
                              ) : null}
                              {!item.pendingApprovals && !item.verificationFailures && !item.delegatedSessions ? (
                                <span>No active blocker</span>
                              ) : null}
                            </div>
                            <div className="builder-conversation-foot">
                              <span>Next: {item.next}</span>
                              <span>{item.updatedAt ? timestampLabel(item.updatedAt) : item.selected ? "Selected" : "Focus thread"}</span>
                            </div>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className="fluxio-empty-copy">
                        {builderPrimaryConversation
                          ? "No secondary conversations are active right now."
                          : "No active conversations yet. Launch a mission and Builder will track every live thread here."}
                      </p>
                    )}
                  </article>

                  <div className="builder-feature-grid">
                    <article className="builder-panel builder-feature-card">
                      <div className="builder-feature-head">
                        <div>
                          <p className="eyebrow">Guided tutorial</p>
                          <h2>{tutorialStudio.headline}</h2>
                        </div>
                        <div className="builder-feature-meta">
                          <span className="mini-pill muted">{tutorialStudio.progressLabel}</span>
                          <span className="mini-pill muted">{tutorialStudio.motionMode} motion</span>
                        </div>
                      </div>
                      <p>{tutorialStudio.summary}</p>
                      <div className="builder-step-grid compact">
                        {tutorialStudio.steps.map(item => (
                          <button
                            className={`builder-step-card ${toneClass(item.tone)} ${item.current ? "current" : ""}`.trim()}
                            key={`builder-step-${item.id}`}
                            onClick={() => void handleBuilderFeatureAction(item.actionId)}
                            type="button"
                          >
                            <span>{item.panel}</span>
                            <strong>{item.title}</strong>
                            <p>{item.description}</p>
                            <em>{item.status}</em>
                          </button>
                        ))}
                      </div>
                      <div className="drawer-actions">
                        <ActionButton
                          onClick={() => void handleBuilderFeatureAction(tutorialStudio.primaryActionId)}
                          variant="primary"
                        >
                          {tutorialStudio.primaryActionLabel}
                        </ActionButton>
                        {tutorialStudio.cards[0] ? (
                          <ActionButton
                            onClick={() => void handleBuilderFeatureAction(tutorialStudio.cards[0].actionId)}
                          >
                            {tutorialStudio.cards[0].title}
                          </ActionButton>
                        ) : null}
                      </div>
                    </article>

                    <article className="builder-panel builder-feature-card">
                      <div className="builder-feature-head">
                        <div>
                          <p className="eyebrow">Recommendations</p>
                          <h2>{recommendationStudio.headline}</h2>
                        </div>
                        <div className="builder-feature-meta">
                          <span className="mini-pill muted">
                            {recommendationStudio.blockedConversationCount} blocked
                          </span>
                          <span className="mini-pill muted">
                            {recommendationStudio.skillRecommendations.length} skill leads
                          </span>
                        </div>
                      </div>
                      <p>{recommendationStudio.summary}</p>
                      <div className="builder-thread-list">
                        {recommendationStudio.struggleSignals.map(item => (
                          <button
                            className={`builder-thread-item ${toneClass(item.tone)}`.trim()}
                            key={item.id}
                            onClick={() => void handleBuilderFeatureAction(item.actionId)}
                            type="button"
                          >
                            <span>{item.label}</span>
                            <strong>{item.detail}</strong>
                          </button>
                        ))}
                      </div>
                      {recommendationStudio.skillRecommendations.length > 0 ? (
                        <div className="builder-inline-list">
                          {recommendationStudio.skillRecommendations.slice(0, 3).map(item => (
                            <span className="builder-inline-pill" key={item.id}>
                              <strong>{item.label}</strong>
                              <span>{item.reason}</span>
                            </span>
                          ))}
                        </div>
                      ) : null}
                      <div className="drawer-actions">
                        {recommendationStudio.nextMoves.slice(0, 2).map((item, index) => (
                          <ActionButton
                            key={item.id}
                            onClick={() => void handleBuilderFeatureAction(item.actionId)}
                            variant={index === 0 ? "primary" : "ghost"}
                          >
                            {item.label}
                          </ActionButton>
                        ))}
                      </div>
                    </article>

                    <article className="builder-panel builder-feature-card builder-feature-card-wide">
                      <div className="builder-feature-head">
                        <div>
                          <p className="eyebrow">Live UI review</p>
                          <h2>{liveReviewStudio.statusLine}</h2>
                        </div>
                        <div className="builder-feature-meta">
                          <span className="mini-pill muted">{liveReviewStudio.targets.length} review blocks</span>
                          {latestThinkingTurn ? (
                            <span className="mini-pill muted">{latestThinkingTurn.roleLabel || "Runtime"} trace live</span>
                          ) : null}
                        </div>
                      </div>
                      <p>{liveReviewStudio.summary}</p>
                      <div className="builder-review-grid">
                        {liveReviewStudio.targets.map(item => (
                          <button
                            className={`builder-review-target ${toneClass(item.tone)} ${builderSelectedReviewTarget?.id === item.id ? "active" : ""}`.trim()}
                            key={item.id}
                            onClick={() => handleBuilderReviewTargetSeed(item)}
                            type="button"
                          >
                            <span>{item.label}</span>
                            <strong>{item.title}</strong>
                            <p>{item.detail}</p>
                          </button>
                        ))}
                      </div>
                      {builderSelectedReviewTarget ? (
                        <div className="builder-review-lower">
                          <article className={`builder-review-focus ${toneClass(builderSelectedReviewTarget.tone)}`}>
                            <span>{builderSelectedReviewTarget.label}</span>
                            <strong>{builderSelectedReviewTarget.title}</strong>
                            <p>{builderSelectedReviewTarget.detail}</p>
                          </article>
                          {latestThinkingTurn ? (
                            <article className="builder-review-trace">
                              <span>{latestThinkingTurn.roleLabel || "Runtime"} trace</span>
                              <strong>{latestThinkingTurn.title}</strong>
                              <p>{latestThinkingTurn.detail}</p>
                            </article>
                          ) : null}
                        </div>
                      ) : null}
                      <p className="builder-review-hint">{liveReviewStudio.compareHint}</p>
                      <div className="drawer-actions">
                        <ActionButton
                          onClick={() => builderSelectedReviewTarget && handleBuilderReviewTargetSeed(builderSelectedReviewTarget)}
                          variant="primary"
                        >
                          Comment selected block
                        </ActionButton>
                        <ActionButton onClick={() => void handleBuilderFeatureAction("open_builder")}>
                          Open preview controls
                        </ActionButton>
                        {mission ? (
                          <ActionButton disabled={!operatorDraft.trim()} onClick={() => void handleAgentFollowUp()}>
                            Send to agent
                          </ActionButton>
                        ) : null}
                      </div>
                    </article>
                  </div>

                  <div className="builder-board-grid">
                    <article className="builder-panel">
                      <div className="section-header">
                        <div className="section-title-block">
                          <p className="eyebrow">What Happens Next</p>
                          <h2>Predicted checkpoints across live threads</h2>
                        </div>
                      </div>
                      {builderBoard.nextUp.length > 0 ? (
                        <div className="builder-digest-list">
                          {builderBoard.nextUp.map(item => (
                            <button
                              className={`builder-digest-item ${toneClass(item.tone)} ${item.selected ? "active" : ""}`.trim()}
                              key={`next-${item.missionId}`}
                              onClick={() => setSelectedMissionId(item.missionId)}
                              type="button"
                            >
                              <div className="builder-digest-top">
                                <span>{item.runtime}</span>
                                <span>{item.updatedAt ? timestampLabel(item.updatedAt) : item.statusLabel}</span>
                              </div>
                              <strong>{item.title}</strong>
                              <p>{item.summary}</p>
                              {item.checkpoint ? <p className="builder-digest-detail">Checkpoint: {item.checkpoint}</p> : null}
                              {item.routeLabel ? <p className="builder-digest-detail">Route: {item.routeLabel}</p> : null}
                              {item.detail ? <p className="builder-digest-detail">{item.detail}</p> : null}
                              <div className="builder-digest-meta">
                                <span>{item.statusLabel}</span>
                                <span>{item.selected ? "Current thread" : "Open thread"}</span>
                              </div>
                            </button>
                          ))}
                        </div>
                      ) : (
                        <p className="fluxio-empty-copy">
                          Launch a mission to see predicted checkpoints and queued follow-up work.
                        </p>
                      )}
                    </article>

                    <article className="builder-panel">
                      <div className="section-header">
                        <div className="section-title-block">
                          <p className="eyebrow">While You Were Away</p>
                          <h2>Recent mission and runtime movement</h2>
                        </div>
                      </div>
                      {builderBoard.whileAway.length > 0 ? (
                        <div className="builder-digest-list">
                          {builderBoard.whileAway.map(item => (
                            <article className={`builder-digest-item ${toneClass(item.tone)}`} key={item.id}>
                              <div className="builder-digest-top">
                                <span>{item.label}</span>
                                <span>{item.timestamp ? timestampLabel(item.timestamp) : ""}</span>
                              </div>
                              <strong>{item.missionTitle}</strong>
                              <p>{item.message}</p>
                              {item.detail ? <p className="builder-digest-detail">{item.detail}</p> : null}
                            </article>
                          ))}
                        </div>
                      ) : (
                        <p className="fluxio-empty-copy">
                          Activity summaries will appear here as missions, approvals, and runtime events land.
                        </p>
                      )}
                    </article>
                  </div>

                  <form className="builder-note-panel" onSubmit={handleOperatorNote}>
                    <label htmlFor="builder-thread-note">
                      {builderSelectedReviewTarget ? `Review note for ${builderSelectedReviewTarget.title}` : "Builder note"}
                    </label>
                    {builderSelectedReviewTarget ? (
                      <p className="builder-note-context">
                        {builderSelectedReviewTarget.label} · {builderSelectedReviewTarget.detail}
                      </p>
                    ) : null}
                    <textarea
                      id="builder-thread-note"
                      onChange={event => setOperatorDraft(event.target.value)}
                      placeholder={
                        builderSelectedReviewTarget
                          ? "Describe what is wrong with this block and what the model should change."
                          : "Capture a technical observation, routing decision, or runtime intervention plan."
                      }
                      value={operatorDraft}
                    />
                    <div className="thread-composer-actions">
                      <ActionButton type="submit" variant="primary">
                        Save note
                      </ActionButton>
                      {mission ? (
                        <ActionButton
                          disabled={!operatorDraft.trim()}
                          onClick={() => void handleAgentFollowUp()}
                          type="button"
                        >
                          Send to agent
                        </ActionButton>
                      ) : null}
                      <ActionButton onClick={() => setActiveDrawer("builder")} type="button">
                        Open builder drawer
                      </ActionButton>
                    </div>
                  </form>
                </section>

                <aside className="builder-secondary-column">
                  <article className="builder-panel builder-panel-focus">
                    <p className="eyebrow">Nexuses</p>
                    <h3>{builderNexusItems.length} decision point{builderNexusItems.length === 1 ? "" : "s"}</h3>
                    <p>Jump back to the moments that most likely changed direction, risk, or final output.</p>
                    <div className="builder-thread-list">
                      {builderNexusItems.slice(0, 4).map(item => (
                        <button
                          className={`builder-thread-item ${toneClass(item.tone)}`.trim()}
                          key={`nexus-${item.id}`}
                          onClick={() => {
                            if (item.missionId) {
                              setSelectedMissionId(item.missionId);
                            }
                            setActiveDrawer(item.tone === "bad" ? "proof" : "context");
                          }}
                          type="button"
                        >
                          <span>{item.label}</span>
                          <strong>{item.title}</strong>
                          <p>{item.reason}</p>
                        </button>
                      ))}
                    </div>
                  </article>

                  <article className="builder-panel builder-panel-focus">
                    <p className="eyebrow">Runtime leaders</p>
                    <h3>{builderBoard.winningRoutes?.length || 0} active route pattern{(builderBoard.winningRoutes?.length || 0) === 1 ? "" : "s"}</h3>
                    <p>Builder tracks which runtime/provider/model combinations are clearing threads versus getting stuck.</p>
                    <div className="builder-thread-list">
                      {asList(builderBoard.winningRoutes).slice(0, 3).map(item => (
                        <article className={`builder-thread-item ${toneClass(item.tone)}`} key={`winning-route-${item.key || item.label}`}>
                          <span>{item.runtime}</span>
                          <strong>{item.label}</strong>
                          <p>{item.detail}</p>
                        </article>
                      ))}
                    </div>
                    <div className="builder-thread-list">
                      {asList(builderBoard.stuckThreads).slice(0, 3).map(item => (
                        <button
                          className={`builder-thread-item ${toneClass(item.tone)}`.trim()}
                          key={`stuck-${item.missionId || item.title}`}
                          onClick={() => item.missionId && setSelectedMissionId(item.missionId)}
                          type="button"
                        >
                          <span>{item.blockerClass}</span>
                          <strong>{item.title}</strong>
                          <p>{item.reason}</p>
                        </button>
                      ))}
                    </div>
                  </article>

                  <article className="builder-panel builder-panel-focus">
                    <p className="eyebrow">Harnesses</p>
                    <h3>{titleizeToken(workspaceProfileForm.preferredHarness)}</h3>
                    <div className="builder-inline-list">
                      <span>Production: {titleizeToken(snapshot.harnessLab?.productionHarness || workspaceProfileForm.preferredHarness)}</span>
                      <span>
                        Shadow: {snapshot.harnessLab?.shadowCandidates?.length > 0
                          ? snapshot.harnessLab.shadowCandidates.map(item => titleizeToken(item)).join(", ")
                          : "None"}
                      </span>
                      <span>{snapshot.harnessLab?.recommendation || "Builder keeps the production and shadow harnesses visible here."}</span>
                    </div>
                    <div className="drawer-actions">
                      <ActionButton onClick={() => void applyPreferredHarness("fluxio_hybrid")} variant="primary">
                        Use Fluxio Hybrid
                      </ActionButton>
                      <ActionButton onClick={() => void applyPreferredHarness("legacy_autonomous_engine")}>
                        Use Legacy Harness
                      </ActionButton>
                      <ActionButton onClick={() => setActiveDrawer("runtime")} type="button">
                        Compare both
                      </ActionButton>
                    </div>
                  </article>

                  <article className="builder-panel builder-panel-focus">
                    <p className="eyebrow">Runtime bridge</p>
                    <h3>{bridgeSummary.connected} live bridge{bridgeSummary.connected === 1 ? "" : "s"}</h3>
                    <p>{bridgeSummary.recommendation}</p>
                    <div className="builder-inline-list">
                      <span>{bridgeSummary.callbackReady} approval callback{bridgeSummary.callbackReady === 1 ? "" : "s"} ready</span>
                      <span>{bridgeSummary.totalApps} connected app definition{bridgeSummary.totalApps === 1 ? "" : "s"}</span>
                      <span>Use Builder to compare Hermes and OpenClaw bridge hand-offs.</span>
                    </div>
                    <ActionButton onClick={() => setActiveDrawer("runtime")}>Open runtime bridge</ActionButton>
                  </article>

                  <article className="builder-panel builder-panel-focus">
                    <p className="eyebrow">Feature backlog</p>
                    <h3>
                      {tutorialStudio.improvements.length + recommendationStudio.learningQueue.length} guided follow-up{tutorialStudio.improvements.length + recommendationStudio.learningQueue.length === 1 ? "" : "s"}
                    </h3>
                    <p>Turn repeated friction into better defaults, stronger guidance, and reusable skill or workflow patterns.</p>
                    <div className="builder-thread-list">
                      {tutorialStudio.improvements.slice(0, 2).map(item => (
                        <article className={`builder-thread-item ${toneClass(item.tone)}`} key={item.id}>
                          <span>{item.category}</span>
                          <strong>{item.title}</strong>
                          <p>{item.reason}</p>
                        </article>
                      ))}
                      {recommendationStudio.learningQueue.slice(0, 2).map(item => (
                        <article className={`builder-thread-item ${toneClass(item.tone)}`} key={item.id}>
                          <span>{item.priority}</span>
                          <strong>{item.title}</strong>
                          <p>Promote the pattern into Builder-visible guidance and reusable skill coverage.</p>
                        </article>
                      ))}
                    </div>
                    <ActionButton onClick={() => void handleBuilderFeatureAction("open_skills")}>
                      Open skill studio
                    </ActionButton>
                  </article>
                </aside>
              </div>
            </section>
          ) : (
            <section className="thread-shell agent-shell">
              <header className="thread-head agent-thread-head agent-title-head">
                <h1>{agentCenterTitle}</h1>
              </header>

              {agentNexusTurns.length > 0 ? (
                <section className="agent-nexus-strip">
                  <div className="section-title-block">
                    <p className="eyebrow">Nexuses</p>
                    <h2>Jump back to the decisions that changed the mission</h2>
                  </div>
                  <div className="agent-nexus-row">
                    {agentNexusTurns.map(item => (
                      <button
                        className={`agent-nexus-chip ${toneClass(item.tone || "neutral")} ${pinnedNexusIds.includes(item.id) ? "pinned" : ""}`.trim()}
                        key={`agent-nexus-${item.id}`}
                        onClick={() => focusTranscriptTurn(item.id)}
                        type="button"
                      >
                        <span>{item.label || item.roleLabel || "Nexus"}</span>
                        <strong>{item.title}</strong>
                      </button>
                    ))}
                  </div>
                </section>
              ) : null}

              <section className={`agent-chat-stage ${agentIdleState === "no-turns" ? "agent-chat-stage-empty" : ""}`.trim()}>
                {agentHasTurns ? (
                  <section className="agent-conversation-shell">
                    <div className="agent-conversation-feed">
                      {agentConversationTurns.map(item => (
                        <AgentChatMessage
                          highlighted={highlightedTurnId === item.id}
                          item={item}
                          key={item.id}
                          onFocusTrace={turnId => {
                            setShowThinkingTrace(true);
                            focusTranscriptTurn(turnId);
                          }}
                        />
                      ))}
                    </div>
                  </section>
                ) : (
                  <section className="agent-conversation-empty">
                    <p className="eyebrow">{mission ? "Conversation ready" : "Mission launch"}</p>
                    <h2>
                      {mission
                        ? "Talk to the mission like a normal chat."
                        : "Start with a mission prompt in the center composer."}
                    </h2>
                    <p>
                      {mission
                        ? "The technical trace stays available below, but the primary surface is the exchange between you and the agent."
                      : "Choose the route you want, write the objective, and Fluxio will switch into a real conversation once the mission is active."}
                    </p>
                  </section>
                )}

                {agentTraceTurns.length > 0 ? (
                  <section className="agent-trace-shell">
                    <div className="agent-trace-head">
                      <div className="section-title-block">
                        <p className="eyebrow">Live trace</p>
                        <h2>Route changes, approvals, and technical output</h2>
                      </div>
                      <div className="thread-composer-actions">
                        <ActionButton onClick={() => setShowThinkingTrace(current => !current)} type="button">
                          {showThinkingTrace ? "Hide trace" : "Show trace"}
                        </ActionButton>
                      </div>
                    </div>
                    {showThinkingTrace ? (
                      <div className="agent-trace-list">
                        {agentTraceTurns.slice(-8).map(item => (
                          <TranscriptMessage
                            highlighted={highlightedTurnId === item.id}
                            item={item}
                            key={item.id}
                            onMemory={handleAgentMemoryFromTurn}
                            onPinNexus={togglePinnedNexus}
                            onSteer={handleAgentSteerFromTurn}
                            onValidate={handleAgentValidateTurn}
                            pinned={pinnedNexusIds.includes(item.id)}
                            showTrace={showThinkingTrace}
                          />
                        ))}
                      </div>
                    ) : (
                      <p className="fluxio-empty-copy">
                        Trace is hidden. Fluxio is still recording runtime decisions in the background.
                      </p>
                    )}
                  </section>
                ) : null}

                <form
                  className={`thread-composer agent-composer agent-chat-composer ${agentIdleState === "no-turns" ? "agent-idle-composer" : "agent-docked-composer"}`.trim()}
                  onSubmit={event => event.preventDefault()}
                >
                  <div className="agent-composer-toolbar">
                    <Field label={mission ? "Trace runtime" : "Launch runtime"}>
                      <select
                        onChange={event =>
                          mission
                            ? setAgentRuntimeFocus(event.target.value)
                            : setMissionForm(current => ({
                                ...current,
                                runtime: event.target.value,
                              }))
                        }
                        value={agentRuntimeSelectValue}
                      >
                        {mission ? <option value="all">All traces</option> : null}
                        {runtimeOptions.map(option => (
                          <option key={`agent-runtime-${option.value}`} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Route role">
                      <select onChange={event => setAgentRouteRole(event.target.value)} value={agentRouteRole}>
                        {ROUTE_ROLE_OPTIONS.map(option => (
                          <option key={`agent-role-${option}`} value={option}>
                            {titleizeToken(option)}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Provider">
                      <select
                        onChange={event => handleAgentRouteFieldChange("provider", event.target.value)}
                        value={selectedAgentRoute.provider}
                      >
                        {MODEL_PROVIDER_OPTIONS.map(option => (
                          <option key={`agent-provider-${option.value}`} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Model">
                      <input
                        list="agent-route-models-live"
                        onChange={event => handleAgentRouteFieldChange("model", event.target.value)}
                        placeholder="Profile default"
                        value={selectedAgentRoute.model}
                      />
                      <datalist id="agent-route-models-live">
                        {ROUTE_MODEL_OPTIONS.map(option => (
                          <option key={`agent-model-${option}`} value={option} />
                        ))}
                      </datalist>
                    </Field>
                    <Field label="Reasoning">
                      <select
                        onChange={event => handleAgentRouteFieldChange("effort", event.target.value)}
                        value={selectedAgentRoute.effort || "default"}
                      >
                        {MODEL_EFFORT_OPTIONS.map(option => (
                          <option key={`agent-effort-${option.value}`} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </Field>
                  </div>
                  <p className="agent-composer-hint">{agentRuntimeHint}</p>
                  <div className="agent-composer-status">
                    <span className="mini-pill muted">{agentRouteStatus}</span>
                    {mission ? (
                      <span className="mini-pill muted">
                        {titleizeToken(agentCyclePhase)} phase via {titleizeToken(agentCycleRole)}
                      </span>
                    ) : null}
                    <span className="mini-pill muted">
                      {latestThinkingTurn
                        ? `${latestThinkingTurn.roleLabel || "Runtime"} trace live`
                        : mission?.state?.status === "running"
                          ? "Awaiting the next runtime trace"
                          : "No live trace right now"}
                    </span>
                    <span className="mini-pill muted">
                      {agentThinkingTurns.length} trace moment{agentThinkingTurns.length === 1 ? "" : "s"}
                    </span>
                    <span className="mini-pill muted">
                      Code execution {codeExecutionEnabled ? `on · ${codeExecutionMemory}` : "off"}
                    </span>
                    <span className="mini-pill muted">
                      {modelAuthReady ? "Model auth ready" : "Model auth missing"}
                    </span>
                  </div>
                  <textarea
                    id="thread-note"
                    onChange={event => setOperatorDraft(event.target.value)}
                    placeholder={agentComposerPlaceholder}
                    value={operatorDraft}
                  />
                  <div className="thread-composer-actions">
                    <ActionButton onClick={() => void handleAgentRouteSave()} type="button">
                      Apply model
                    </ActionButton>
                    <ActionButton
                      onClick={() => setCodeExecutionEnabled(current => !current)}
                      type="button"
                    >
                      {codeExecutionEnabled ? "Disable code execution" : "Enable code execution"}
                    </ActionButton>
                    {mission ? (
                      <>
                        <ActionButton onClick={handleOperatorNote} type="button">
                          Save note
                        </ActionButton>
                        <ActionButton onClick={() => void handleAgentFollowUp()} type="button" variant="primary">
                          Send message
                        </ActionButton>
                      </>
                    ) : (
                      <ActionButton
                        onClick={handleAgentIdlePrimaryAction}
                        type="button"
                        variant="primary"
                      >
                        {workspaces.length > 0 ? "Launch mission" : "Add workspace"}
                      </ActionButton>
                    )}
                  </div>
                </form>
              </section>
            </section>
          )}
        </main>

        {showPersistentDrawer ? (
          <aside className={`fluxio-drawer ${activeDrawer ? "open" : ""}`.trim()}>
            <div className="drawer-shell-head">
              <div>
                <p className="eyebrow">{uiMode === "builder" ? "Builder panel" : "Blocker panel"}</p>
                <strong>{activeDrawerMeta?.label || titleizeToken(activeDrawer || "panel")}</strong>
              </div>
              {uiMode === "builder" ? (
                <ActionButton onClick={() => setActiveDrawer(null)} type="button">
                  Close
                </ActionButton>
              ) : null}
            </div>
            <div className="drawer-content">{renderDrawerPanel()}</div>
          </aside>
        ) : null}
      </div>

      <Modal
        actions={
          <ActionButton onClick={handleWorkspaceSubmit} type="submit" variant="primary">
            Save workspace
          </ActionButton>
        }
        onClose={() => setShowWorkspaceDialog(false)}
        open={showWorkspaceDialog}
        summary="Workspace ownership stays in T3 shell state. Legacy shell no longer controls this flow."
        title="Add workspace"
      >
        <form className="dialog-form" onSubmit={handleWorkspaceSubmit}>
          <Field label="Workspace name">
            <input
              onChange={event =>
                setWorkspaceForm(current => ({ ...current, name: event.target.value }))
              }
              placeholder="Fluxio Platform"
              value={workspaceForm.name}
            />
          </Field>
          <Field label="Workspace path">
            <input
              onChange={event =>
                setWorkspaceForm(current => ({ ...current, path: event.target.value }))
              }
              placeholder="C:/Users/paul/projects/vibe-coding-platform"
              value={workspaceForm.path}
            />
          </Field>
          <div className="field-row">
            <Field label="Default runtime">
              <select
                onChange={event =>
                  setWorkspaceForm(current => ({
                    ...current,
                    defaultRuntime: event.target.value,
                  }))
                }
                value={workspaceForm.defaultRuntime}
              >
                <option value="openclaw">OpenClaw</option>
                <option value="hermes">Hermes</option>
              </select>
            </Field>
            <Field label="Operator profile">
              <select
                onChange={event =>
                  setWorkspaceForm(current => ({ ...current, userProfile: event.target.value }))
                }
                value={workspaceForm.userProfile}
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
          </div>
        </form>
      </Modal>

      <Modal
        actions={
          <ActionButton onClick={handleMissionSubmit} type="submit" variant="primary">
            Launch mission
          </ActionButton>
        }
        onClose={() => setShowMissionDialog(false)}
        open={showMissionDialog}
        summary="Mission launch remains available, but operational clutter is removed from the top bar."
        title="Start mission"
      >
        <form className="dialog-form" onSubmit={handleMissionSubmit}>
          <div className="field-row">
            <Field label="Workspace">
              <select
                onChange={event =>
                  setMissionForm(current => ({ ...current, workspaceId: event.target.value }))
                }
                value={missionForm.workspaceId}
              >
                {workspaces.map(item => (
                  <option key={item.workspace_id} value={item.workspace_id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Runtime">
              <select
                onChange={event =>
                  setMissionForm(current => ({ ...current, runtime: event.target.value }))
                }
                value={missionForm.runtime}
              >
                <option value="openclaw">OpenClaw</option>
                <option value="hermes">Hermes</option>
              </select>
            </Field>
          </div>

          <div className="field-row">
            <Field label="Run mode">
              <select
                onChange={event =>
                  setMissionForm(current => ({ ...current, mode: event.target.value }))
                }
                value={missionForm.mode}
              >
                <option value="Autopilot">Autopilot</option>
                <option value="Deep Run">Deep Run</option>
                <option value="Proof First">Proof First</option>
              </select>
            </Field>
            <Field label="Profile">
              <select
                onChange={event =>
                  setMissionForm(current => ({ ...current, profile: event.target.value }))
                }
                value={missionForm.profile}
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
          </div>

          <div className="field-row">
            <Field label="Budget hours">
              <input
                min="1"
                onChange={event =>
                  setMissionForm(current => ({
                    ...current,
                    budgetHours: Number(event.target.value || 12),
                  }))
                }
                type="number"
                value={missionForm.budgetHours}
              />
            </Field>
            <Field label="Run until">
              <select
                onChange={event =>
                  setMissionForm(current => ({ ...current, runUntil: event.target.value }))
                }
                value={missionForm.runUntil}
              >
                <option value="pause_on_failure">Pause on failure</option>
                <option value="continue_until_blocked">Continue until blocked</option>
              </select>
            </Field>
          </div>

          <Field label="Mission objective">
            <textarea
              onChange={event =>
                setMissionForm(current => ({ ...current, objective: event.target.value }))
              }
              placeholder={missionObjectivePlaceholder(missionForm.profile)}
              value={missionForm.objective}
            />
          </Field>

          <Field label="Success checks">
            <textarea
              onChange={event =>
                setMissionForm(current => ({ ...current, successChecks: event.target.value }))
              }
              placeholder={missionChecksPlaceholder(missionForm.profile)}
              value={missionForm.successChecks}
            />
          </Field>
        </form>
      </Modal>

      <Modal
        actions={
          <div className="inline-actions">
            <ActionButton onClick={handleClearTelegram}>Clear token</ActionButton>
            <ActionButton onClick={handleSaveTelegram} type="submit" variant="primary">
              Save escalation
            </ActionButton>
          </div>
        }
        onClose={() => setShowEscalationDialog(false)}
        open={showEscalationDialog}
        summary="Escalation stays accessible, but only opens when the operator needs it."
        title="Configure Telegram escalation"
      >
        <form className="dialog-form" onSubmit={handleSaveTelegram}>
          <Field label="Telegram bot token">
            <input
              onChange={event => setTelegramBotToken(event.target.value)}
              placeholder="123456:ABCDEF..."
              type="password"
              value={telegramBotToken}
            />
          </Field>
          <Field label="Telegram chat ID">
            <input
              onChange={event => setTelegramChatId(event.target.value)}
              placeholder="123456789"
              value={telegramChatId}
            />
          </Field>
        </form>
      </Modal>

      <ToastHost items={toasts} />
    </div>
  );
}
