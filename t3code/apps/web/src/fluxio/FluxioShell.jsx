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
  { value: "openrouter", label: "OpenRouter" },
];
const MODEL_EFFORT_OPTIONS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];
const ROUTE_MODEL_OPTIONS = [
  "gpt-5.4",
  "gpt-5.4-mini",
  "codex",
  "claude-sonnet-4.5",
  "claude-opus-4.1",
];

function hasTauriBackend() {
  return Boolean(globalThis.window?.__TAURI__ || globalThis.window?.__TAURI_INTERNALS__);
}

async function callBackend(command, payload = undefined, options = {}) {
  try {
    return payload === undefined ? await invoke(command) : await invoke(command, payload);
  } catch (error) {
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

function NavItem({ active = false, title, subtitle, onClick, tone = "neutral", badge, icon = null }) {
  return (
    <button
      className={`fluxio-nav-item ${active ? "active" : ""}`.trim()}
      onClick={onClick}
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

function TranscriptMessage({ item }) {
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
    <article className={`agent-message role-${role} ${toneClass(item.tone || "neutral")} ${item.emphasis ? "emphasis" : ""}`.trim()}>
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
      {item.chips?.length ? (
        <div className="agent-message-chips">
          {item.chips.map(chip => (
            <span className="mini-pill muted" key={`${item.id}-${chip}`}>
              {chip}
            </span>
          ))}
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

function profileFormFromWorkspace(workspace, fallbackProfile) {
  const overrides = Array.isArray(workspace?.route_overrides) ? workspace.route_overrides : [];
  const existingByRole = new Map(overrides.map(item => [String(item.role || "").toLowerCase(), item]));
  return {
    userProfile: workspace?.user_profile || fallbackProfile || "builder",
    preferredHarness: workspace?.preferred_harness || "fluxio_hybrid",
    routingStrategy: workspace?.routing_strategy || "profile_default",
    autoOptimizeRouting: Boolean(workspace?.auto_optimize_routing),
    minimaxAuthMode: workspace?.minimax_auth_mode || "none",
    commitMessageStyle: workspace?.commit_message_style || "scoped",
    executionTargetPreference: workspace?.execution_target_preference || "profile_default",
    routeOverrides: ROUTE_ROLE_OPTIONS.map(role => {
      const item = existingByRole.get(role) || {};
      return {
        role,
        provider: item.provider || "openai",
        model: item.model || "",
        effort: item.effort || (role === "executor" ? "medium" : "high"),
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
  const [lastPushReason, setLastPushReason] = useState("");
  const [liveSyncSuspended, setLiveSyncSuspended] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [activeDrawer, setActiveDrawer] = useState("context");
  const [operatorDraft, setOperatorDraft] = useState("");
  const [operatorNotes, setOperatorNotes] = useState([]);
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
  });

  const mountedRef = useRef(true);
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

  const refreshAll = useCallback(
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
          onboarding,
          pendingApprovals,
          pendingQuestions,
          telegramReady,
          openClawStatus,
          openClawHasToken,
        ] =
          await Promise.all([
            callBackend(
              "get_control_room_snapshot_command",
              { payload: { root: null } },
              { throwOnError: true },
            ),
            callBackend(
              "get_onboarding_status_command",
              { payload: { root: null } },
              { throwOnError: true },
            ),
            callBackend("list_pending_approvals"),
            callBackend("list_pending_questions"),
            callBackend("has_telegram_bot_token_command"),
            callBackend("get_openclaw_status"),
            callBackend("has_openclaw_gateway_token"),
          ]);

        if (!mountedRef.current) {
          return;
        }

        setData(current => ({
          ...current,
          snapshot,
          onboarding,
          pendingApprovals: Array.isArray(pendingApprovals) ? pendingApprovals : [],
          pendingQuestions: Array.isArray(pendingQuestions) ? pendingQuestions : [],
          telegramReady: Boolean(telegramReady),
          previewMeta: null,
          openClawStatus: openClawStatus || null,
          openClawHasToken: Boolean(openClawHasToken),
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

    let unlistenChanged = null;
    let unlistenDelta = null;
    let unlistenOpenClawStatus = null;
    let unlistenOpenClawMessage = null;

    void listen("control-room://changed", event => {
      const reason = event?.payload?.reason || "backend-event";
      setLastPushReason(reason);
      void refreshAll(reason);
    })
      .then(unlisten => {
        unlistenChanged = unlisten;
      })
      .catch(() => undefined);

    void listen("control-room://delta", event => {
      const reason = event?.payload?.source || "backend-delta";
      setLastPushReason(reason);
      void refreshAll(reason);
    })
      .then(unlisten => {
        unlistenDelta = unlisten;
      })
      .catch(() => undefined);

    void listen("openclaw://status", event => {
      setData(current => ({
        ...current,
        openClawStatus: event?.payload || current.openClawStatus,
      }));
    })
      .then(unlisten => {
        unlistenOpenClawStatus = unlisten;
      })
      .catch(() => undefined);

    void listen("openclaw://message", event => {
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
    })
      .then(unlisten => {
        unlistenOpenClawMessage = unlisten;
      })
      .catch(() => undefined);

    return () => {
      if (typeof unlistenChanged === "function") {
        unlistenChanged();
      }
      if (typeof unlistenDelta === "function") {
        unlistenDelta();
      }
      if (typeof unlistenOpenClawStatus === "function") {
        unlistenOpenClawStatus();
      }
      if (typeof unlistenOpenClawMessage === "function") {
        unlistenOpenClawMessage();
      }
    };
  }, [previewMode, refreshAll]);

  const snapshot = data.snapshot || {};
  const onboarding = data.onboarding || snapshot.onboarding || {};
  const setupHealth = snapshot.setupHealth || onboarding.setupHealth || {};
  const workspaces = snapshot.workspaces || [];
  const missions = snapshot.missions || [];
  const inboxItems = snapshot.inbox || [];

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
  const showPersistentDrawer =
    uiMode === "builder" || !mission || ["draft", "queued", "needs_approval", "blocked"].includes(missionStatus);
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
    const gatewayUrl = data.openClawStatus?.gatewayUrl;
    if (gatewayUrl) {
      setOpenClawGatewayUrl(gatewayUrl);
    }
  }, [data.openClawStatus?.gatewayUrl]);

  useEffect(() => {
    if (!mission && uiMode === "agent") {
      setActiveDrawer("context");
    }
  }, [mission, uiMode]);

  useEffect(() => {
    if (uiMode === "agent" && ["builder", "skills", "runtime", "profiles", "settings"].includes(activeDrawer)) {
      setActiveDrawer("context");
    }
  }, [activeDrawer, uiMode]);

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
            routeOverrides: workspaceProfileForm.routeOverrides
              .filter(item => item.model.trim())
              .map(item => ({
                role: item.role,
                provider: item.provider,
                model: item.model.trim(),
                effort: item.effort,
              })),
            autoOptimizeRouting: Boolean(workspaceProfileForm.autoOptimizeRouting),
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

  const openMissionDialog = useCallback(() => {
    markAction("open:mission-dialog");
    setMissionForm(current => ({
      ...current,
      workspaceId: workspace?.workspace_id || current.workspaceId || "",
      runtime: mission?.runtime_id || workspace?.default_runtime || current.runtime,
      profile: mission?.selected_profile || workspace?.user_profile || profileId,
    }));
    setShowMissionDialog(true);
  }, [
    markAction,
    mission?.runtime_id,
    mission?.selected_profile,
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
    [markAction, missionForm, previewMode, pushToast, refreshAll, telegramChatId],
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

  const handleOperatorNote = useCallback(
    event => {
      event.preventDefault();
      if (!operatorDraft.trim()) {
        return;
      }
      markAction("composer:add-note");
      appendOperatorEntry({
        title: "Operator note",
        detail: operatorDraft.trim(),
        meta: "Local note",
        tone: "neutral",
        channel: "note",
      });
      setOperatorDraft("");
      pushToast("Operator note added to this session.", "info");
    },
    [appendOperatorEntry, markAction, operatorDraft, pushToast],
  );

  const handleAgentFollowUp = useCallback(async () => {
    if (!operatorDraft.trim()) {
      pushToast("Write a follow-up first.", "warn");
      return;
    }
    if (mission?.runtime_id !== "openclaw") {
      pushToast("Live follow-up is currently wired for OpenClaw missions only.", "warn");
      return;
    }
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot send runtime follow-ups.", "warn");
      return;
    }

    markAction("composer:send-follow-up");
    try {
      await callBackend(
        "send_openclaw_message",
        { payload: { message: operatorDraft.trim() } },
        { throwOnError: true },
      );
      appendOperatorEntry({
        title: "Operator follow-up",
        detail: operatorDraft.trim(),
        meta: "Sent to OpenClaw",
        tone: "neutral",
        channel: "followup",
      });
      setOperatorDraft("");
      pushToast("Follow-up sent to OpenClaw.", "info");
    } catch (error) {
      pushToast(`OpenClaw follow-up failed: ${error}`, "error");
    }
  }, [appendOperatorEntry, markAction, mission?.runtime_id, operatorDraft, previewMode, pushToast]);

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

  const composerEvents = useMemo(
    () =>
      operatorNotes.map(note => ({
        kind: "note",
        title: note.title,
        detail: note.detail,
        tone: note.tone,
        meta: timestampLabel(note.createdAt),
      })),
    [operatorNotes],
  );

  const threadEvents = useMemo(
    () => [...composerEvents, ...(viewModel.thread.events || [])].slice(0, 24),
    [composerEvents, viewModel.thread.events],
  );

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
          ]
        : [],
    [
      mission,
      profileId,
      workspace?.preferred_harness,
      workspace?.user_profile,
    ],
  );
  const runtimeTruth = useMemo(() => {
    const items = [
      openClawRuntimeActive
        ? openClawStatus?.connected
          ? "OpenClaw gateway connected"
          : "OpenClaw gateway not connected"
        : `Mission runtime: ${runtimeLabel(mission?.runtime_id || workspace?.default_runtime || "openclaw")}`,
      data.openClawHasToken ? "Gateway token stored" : "Gateway token missing",
    ];

    if (delegatedSessions.length > 0) {
      items.push(
        `${delegatedSessions.length} delegated runtime lane${delegatedSessions.length > 1 ? "s" : ""} visible in-thread`,
      );
    }
    if (bridgeSessions.length > 0) {
      items.push(
        `${bridgeSessions.length} connected app bridge${bridgeSessions.length > 1 ? "s" : ""} reporting`,
      );
    }

    items.push("Builder can install, repair, and update runtimes without leaving the shell.");
    return items;
  }, [
    bridgeSessions.length,
    data.openClawHasToken,
    delegatedSessions.length,
    mission?.runtime_id,
    openClawRuntimeActive,
    openClawStatus?.connected,
    workspace?.default_runtime,
  ]);

  const agentTranscript = useMemo(() => {
    const items = [];

    if (mission) {
      items.push({
        id: "agent-contract",
        role: "fluxio",
        roleIcon: "◎",
        label: "Agent contract",
        title: "This view stays on the mission conversation.",
        detail:
          "You can follow the run, answer boundaries, and send follow-ups without carrying builder-only controls all the time.",
        chips: ["Calmer layout", "Inline follow-up", "Builder chrome hidden"],
        tone: "neutral",
        emphasis: true,
      });
    }

    for (const item of viewModel.thread.sections || []) {
      items.push({
        id: `section-${item.id}`,
        role: "fluxio",
        roleIcon: "◎",
        label: item.label,
        title: item.body,
        detail: item.detail,
        tone: item.tone || "neutral",
      });
    }

    for (const approval of data.pendingApprovals.slice(0, 3)) {
      items.push({
        id: `approval-${approval.approval_id || approval.request_id || approval.title}`,
        role: "queue",
        roleIcon: "!",
        label: "Approval boundary",
        title: approval.title || approval.summary || "Approval required",
        detail: approval.reason || approval.detail || "Fluxio is waiting on an explicit operator decision.",
        tone: "warn",
      });
    }

    for (const question of data.pendingQuestions.slice(0, 3)) {
      items.push({
        id: `question-${question.question_id || question.request_id || question.prompt}`,
        role: "queue",
        roleIcon: "?",
        label: "Question",
        title: question.prompt || question.title || "Clarification needed",
        detail: question.detail || question.context || "Answering this helps the mission continue.",
        tone: "warn",
      });
    }

    for (const note of [...operatorNotes].reverse()) {
      items.push({
        id: `operator-${note.id}`,
        role: "operator",
        roleIcon: "◉",
        label: note.channel === "followup" ? "Follow-up sent" : "Operator note",
        title: note.detail,
        detail: note.meta,
        meta: timestampLabel(note.createdAt),
        tone: note.tone || "neutral",
      });
    }

    for (const session of delegatedSessions) {
      const delegatedMessageId =
        session.delegated_id ||
        `${session.runtime_id || "runtime"}-${session.updated_at || session.last_event || "session"}`;
      items.push({
        id: `delegated-${delegatedMessageId}`,
        role: "runtime",
        roleLabel: runtimeLabel(session.runtime_id),
        roleIcon: "◇",
        label: `${runtimeLabel(session.runtime_id)} lane`,
        title: session.detail || session.last_event || `${runtimeLabel(session.runtime_id)} session ${titleizeToken(session.status || "active")}`,
        detail:
          session.heartbeat_status === "stale"
            ? "Heartbeat is stale. Builder runtime view can inspect the lane in detail."
            : session.execution_target_detail || session.execution_root || "Delegated runtime lane is being supervised from Fluxio.",
        meta: timestampLabel(session.updated_at),
        tone: session.heartbeat_status === "stale" ? "warn" : session.status === "failed" ? "bad" : "neutral",
        chips: [
          titleizeToken(session.status || "unknown"),
          session.heartbeat_status ? `Heartbeat ${titleizeToken(session.heartbeat_status)}` : "",
          session.execution_target ? titleizeToken(session.execution_target) : "",
        ].filter(Boolean),
      });

      for (const [index, event] of [...(Array.isArray(session.latest_events) ? session.latest_events : [])]
        .slice(-2)
        .reverse()
        .entries()) {
        items.push({
          id: `delegated-${delegatedMessageId}-event-${event.event_id || index}`,
          role: "runtime",
          roleLabel: runtimeLabel(session.runtime_id),
          roleIcon: session.runtime_id === "hermes" ? "⬢" : "◇",
          label: titleizeToken(event.kind || "runtime event"),
          title: event.message || "Runtime event",
          detail:
            event.detail ||
            session.execution_target_detail ||
            "Delegated runtime supervision is still flowing into the thread.",
          tone:
            event.status === "failed"
              ? "bad"
              : /approval|blocked|stale/i.test(`${event.kind || ""} ${event.message || ""}`)
                ? "warn"
                : "neutral",
          chips: [
            session.status ? titleizeToken(session.status) : "",
            session.execution_target ? titleizeToken(session.execution_target) : "",
            event.status ? titleizeToken(event.status) : "",
          ].filter(Boolean),
        });
      }
    }

    for (const message of data.openClawMessages) {
      items.push({
        id: `openclaw-${message.id}`,
        role: "runtime",
        roleLabel: "OpenClaw",
        roleIcon: "◇",
        label: "OpenClaw",
        title: message.detail,
        detail: message.meta || "Gateway message",
        meta: timestampLabel(message.createdAt),
        tone: message.tone || "neutral",
      });
    }

    for (const session of bridgeSessions.slice(0, 3)) {
      items.push({
        id: `bridge-${session.session_id || session.app_id}`,
        role: "bridge",
        roleLabel: session.app_name || "Connected app",
        roleIcon: "⌁",
        label: `${session.app_name || session.app_id} bridge`,
        title:
          session.latest_task_result?.label ||
          `${titleizeToken(session.status || "connected")} bridge session`,
        detail:
          session.latest_task_result?.resultSummary ||
          session.notes?.[0] ||
          "Bridge session is connected and reporting.",
        meta: timestampLabel(session.last_seen_at),
        tone:
          session.bridge_health === "healthy"
            ? "neutral"
            : session.bridge_health === "manifest_only"
              ? "warn"
              : "bad",
        chips: [
          session.bridge_transport ? titleizeToken(session.bridge_transport) : "",
          session.bridge_health ? titleizeToken(session.bridge_health) : "",
          Array.isArray(session.active_tasks) && session.active_tasks.length > 0
            ? `${session.active_tasks.length} active`
            : "",
        ].filter(Boolean),
      });
    }

    for (const event of (viewModel.thread.events || []).slice(0, 6)) {
      const runtimeLike = ["runtime", "activity"].includes(event.kind);
      items.push({
        id: `event-${event.kind}-${event.title}-${event.meta}`,
        role: runtimeLike ? "runtime" : "system",
        roleIcon: runtimeLike ? "◇" : "·",
        label: titleizeToken(event.kind || "event"),
        title: event.title,
        detail: event.detail,
        meta: timestampLabel(event.meta),
        tone: event.tone || "neutral",
      });
    }

    return items;
  }, [
    bridgeSessions,
    data.openClawMessages,
    data.pendingApprovals,
    data.pendingQuestions,
    delegatedSessions,
    mission,
    operatorNotes,
    viewModel.thread.events,
    viewModel.thread.sections,
  ]);

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
              Hermes does not yet have an OpenClaw-style dedicated Tauri gateway in this shell. Its live supervision currently comes through delegated runtime sessions and connected-app bridge snapshots.
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
                setActiveDrawer("context");
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
                  setActiveDrawer(current =>
                    ["builder", "skills", "runtime", "profiles", "proof", "queue", "settings"].includes(
                      current,
                    )
                      ? current
                      : "builder",
                  );
                  return;
                }
                setActiveDrawer(viewModel.drawers.queue.urgent ? "queue" : "context");
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
            active={uiMode === "builder"}
            label="Views"
            onClick={() => {
              markAction("open:view-builder");
              setUiMode("builder");
              setActiveDrawer("builder");
            }}
            tone="neutral"
          />
        </div>

        <div className="topbar-confidence">
          <span>1.0 confidence</span>
          <strong className={toneClass(viewModel.drawers.builder.confidence.tone)}>
            {viewModel.drawers.builder.confidence.score}%
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
                label="Operator"
                onClick={() => {
                  markAction("rail:operator");
                  setUiMode("agent");
                  setActiveDrawer(viewModel.drawers.queue.urgent ? "queue" : "context");
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
                      setActiveDrawer("builder");
                    }}
                  />
                  <GlobalRailButton
                    active={activeDrawer === "skills"}
                    icon="✦"
                    label="Skills"
                    onClick={() => {
                      markAction("rail:skills");
                      setSkillStudioFilter("all");
                      setActiveDrawer("skills");
                    }}
                  />
                  <GlobalRailButton
                    active={activeDrawer === "runtime"}
                    icon="◇"
                    label="Runtime"
                    onClick={() => {
                      markAction("rail:runtime");
                      setActiveDrawer("runtime");
                    }}
                  />
                  <GlobalRailButton
                    active={activeDrawer === "profiles"}
                    icon="◫"
                    label="Profiles"
                    onClick={() => {
                      markAction("rail:profiles");
                      setActiveDrawer("profiles");
                    }}
                  />
                </>
              ) : null}
            </section>

            <section className="fluxio-nav-section">
              <div className="fluxio-nav-heading">
                <p className="eyebrow">Workspaces</p>
                <ActionButton onClick={() => setShowWorkspaceDialog(true)}>Add</ActionButton>
              </div>
              <div className="fluxio-nav-list">
                {workspaces.length > 0 ? (
                  workspaces.map(item => (
                    <NavItem
                      active={item.workspace_id === selectedWorkspaceId}
                      badge={item.runtimeStatus?.detected ? "Ready" : "Check"}
                      icon="▣"
                      key={item.workspace_id}
                      onClick={() => setSelectedWorkspaceId(item.workspace_id)}
                      subtitle={item.root_path}
                      title={item.name}
                      tone={item.runtimeStatus?.detected ? "good" : "warn"}
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
                  missionOptions.map(item => (
                    <NavItem
                      active={item.mission_id === selectedMissionId}
                      badge={titleizeToken(item.state?.status || "draft")}
                      icon="◆"
                      key={item.mission_id}
                      onClick={() => setSelectedMissionId(item.mission_id)}
                      subtitle={runtimeLabel(item.runtime_id)}
                      title={item.title || item.objective}
                      tone={item.proof?.pending_approvals?.length ? "warn" : viewModel.topBar.liveStatus.tone}
                    />
                  ))
                ) : (
                  <p className="fluxio-empty-copy">Mission thread appears after first launch.</p>
                )}
              </div>
            </section>
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
              <header className="builder-head">
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
                    <ActionButton onClick={() => setActiveDrawer("profiles")}>Profiles</ActionButton>
                  </div>
                </header>

                <section className="mode-story mode-builder">
                  <strong>Builder mode is the control workbench.</strong>
                  <p>Use it to shape runtime policy, routing, services, and proof review. The tradeoff is more density and more operational detail.</p>
                </section>

                <div className="builder-workbench-grid">
                  <section className="builder-primary-column">
                    <article className="builder-panel builder-panel-hero">
                      <p className="eyebrow">Launch readiness</p>
                      <h2>{viewModel.emptyState.confidenceLabel}</h2>
                      <p>{viewModel.emptyState.confidencePhase}</p>
                      <div className="empty-confidence">
                        <p>Recommended workflow: {viewModel.emptyState.recommendedWorkflow}</p>
                        <p>{viewModel.emptyState.qualityRoadmapHeadline}</p>
                      </div>
                      <ul>
                        {viewModel.emptyState.readiness.map(item => (
                          <li key={`builder-readiness-${item}`}>{item}</li>
                        ))}
                      </ul>
                      <div className="drawer-actions">
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
                    <article className="builder-panel">
                      <p className="eyebrow">Profiles</p>
                      <h3>{titleizeToken(workspaceProfileForm.userProfile)}</h3>
                      <p>{viewModel.drawers.builder.profileStudio.behavior[0]?.value || "No profile selected."}</p>
                      <ActionButton onClick={() => setActiveDrawer("profiles")}>Open profiles</ActionButton>
                    </article>

                    <article className="builder-panel">
                      <p className="eyebrow">Runtime</p>
                      <h3>
                        {viewModel.drawers.builder.serviceStudio.summary.healthyCount}/
                        {viewModel.drawers.builder.serviceStudio.summary.totalItems} healthy
                      </h3>
                      <p>
                        {viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount} service(s) need attention.
                      </p>
                      <ActionButton onClick={() => setActiveDrawer("runtime")}>Open runtime</ActionButton>
                    </article>

                    <article className="builder-panel">
                      <p className="eyebrow">Skills</p>
                      <h3>{viewModel.drawers.builder.skillStudio.summary.executionReadyCount} execution-ready</h3>
                      <p>{viewModel.drawers.builder.skillStudio.nextQualityActions[0] || "Skill quality is stable."}</p>
                      <ActionButton onClick={() => setActiveDrawer("skills")}>Open skills</ActionButton>
                    </article>
                  </aside>
                </div>
              </section>
            ) : (
              <section className="fluxio-empty agent-shell">
                <section className="mode-story mode-agent">
                  <strong>Agent mode keeps launch calm.</strong>
                  <p>Pick a workspace, launch a mission, and keep the UI focused on the thread instead of the tooling.</p>
                </section>
                <p className="eyebrow">Readiness</p>
                <h1>{viewModel.emptyState.title}</h1>
                <p>{viewModel.emptyState.summary}</p>
                <div className="empty-confidence">
                  <strong className={toneClass(viewModel.drawers.builder.confidence.tone)}>
                    {viewModel.emptyState.confidenceLabel}
                  </strong>
                  <p>{viewModel.emptyState.confidencePhase}</p>
                  <p>Recommended workflow: {viewModel.emptyState.recommendedWorkflow}</p>
                  <p>{viewModel.emptyState.qualityRoadmapHeadline}</p>
                </div>
                <ul>
                  {viewModel.emptyState.readiness.map(item => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
                <div className="fluxio-empty-actions">
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
                  {quickSetupActions.map(action => (
                    <ActionButton
                      key={action.actionId}
                      onClick={() => void runWorkspaceAction("setup", action.actionId)}
                    >
                      {action.label}
                    </ActionButton>
                  ))}
                </div>
              </section>
            )
          ) : uiMode === "builder" ? (
            <section className="builder-shell">
              <header className="builder-head">
                <div>
                  <p className="eyebrow">Builder workbench</p>
                  <h1>{viewModel.thread.title}</h1>
                  <p>{viewModel.thread.objective || viewModel.thread.summary}</p>
                </div>
                <div className="builder-head-actions">
                  <ActionButton onClick={() => setActiveDrawer("proof")} variant="primary">
                    Proof review
                  </ActionButton>
                  <ActionButton onClick={() => setActiveDrawer("queue")}>Queue</ActionButton>
                  <ActionButton onClick={() => setActiveDrawer("runtime")}>Runtime</ActionButton>
                </div>
              </header>

              <section className="mode-story mode-builder">
                <strong>Builder keeps deep controls visible.</strong>
                <p>Routing, services, skills, and proof stay available here because this view is for shaping the system, not just following the run.</p>
              </section>

              <div className="builder-workbench-grid">
                <section className="builder-primary-column">
                  <article className="builder-panel builder-panel-hero">
                    <p className="eyebrow">Mission state</p>
                    <div className="thread-chip-row">
                      {viewModel.thread.chips.map(item => (
                        <StatusPill key={`builder-chip-${item.label}`} tone={item.tone}>
                          {item.label}
                        </StatusPill>
                      ))}
                      <StatusPill strong tone={viewModel.thread.status.tone}>
                        {viewModel.thread.status.label}
                      </StatusPill>
                    </div>
                    <p>{viewModel.drawers.builder.confidence.label}</p>
                    <div className="milestone-strip">
                      {viewModel.drawers.builder.confidence.milestones.slice(0, 3).map(item => (
                        <article className="milestone-card" key={`builder-milestone-${item.id}`}>
                          <span>{item.label}</span>
                          <strong>{item.percent}%</strong>
                          <p>{item.detail}</p>
                        </article>
                      ))}
                    </div>
                  </article>

                  <article className="builder-panel">
                    <div className="section-header">
                      <div className="section-title-block">
                        <p className="eyebrow">Thread insight</p>
                        <h2>Mission supervision</h2>
                      </div>
                    </div>
                    <div className="builder-thread-list">
                      {viewModel.thread.sections.slice(0, 5).map(item => (
                        <article className={`builder-thread-item ${toneClass(item.tone || "neutral")}`} key={`builder-thread-${item.id}`}>
                          <span>{item.label}</span>
                          <strong>{item.body}</strong>
                          {item.detail ? <p>{item.detail}</p> : null}
                        </article>
                      ))}
                    </div>
                  </article>

                  <article className="builder-panel">
                    <div className="section-header">
                      <div className="section-title-block">
                        <p className="eyebrow">Transcript</p>
                        <h2>Recent activity</h2>
                      </div>
                    </div>
                    <div className="thread-event-list">
                      {threadEvents.slice(0, 6).map(item => (
                        <article className={`thread-event ${toneClass(item.tone || "neutral")}`} key={`builder-event-${item.kind}-${item.title}-${item.meta}`}>
                          <div className="thread-event-top">
                            <span>{titleizeToken(item.kind || "event")}</span>
                            <span>{timestampLabel(item.meta)}</span>
                          </div>
                          <strong>{item.title}</strong>
                          {item.detail ? <p>{item.detail}</p> : null}
                        </article>
                      ))}
                    </div>
                  </article>

                  <form className="builder-note-panel" onSubmit={handleOperatorNote}>
                    <label htmlFor="builder-thread-note">Builder note</label>
                    <textarea
                      id="builder-thread-note"
                      onChange={event => setOperatorDraft(event.target.value)}
                      placeholder="Capture a runtime note, builder observation, or next technical move."
                      value={operatorDraft}
                    />
                    <div className="thread-composer-actions">
                      <ActionButton type="submit" variant="primary">
                        Save note
                      </ActionButton>
                      <ActionButton onClick={() => setActiveDrawer("builder")} type="button">
                        Open builder drawer
                      </ActionButton>
                    </div>
                  </form>
                </section>

                <aside className="builder-secondary-column">
                  <article className="builder-panel builder-panel-focus">
                    <p className="eyebrow">Profiles</p>
                    <h3>{titleizeToken(workspaceProfileForm.userProfile)}</h3>
                    <p>{viewModel.drawers.builder.profileStudio.behavior[0]?.value || "No profile policy yet."}</p>
                    <div className="builder-inline-list">
                      {viewModel.drawers.builder.profileStudio.behavior.slice(1, 4).map(item => (
                        <span key={`behavior-${item.label}`}>{item.label}: {item.value}</span>
                      ))}
                    </div>
                    <ActionButton onClick={() => setActiveDrawer("profiles")}>Open profiles</ActionButton>
                  </article>

                  <article className="builder-panel builder-panel-focus">
                    <p className="eyebrow">Runtime</p>
                    <h3>{viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount} need attention</h3>
                    <div className="builder-inline-list">
                      {viewModel.drawers.builder.serviceStudio.urgent.slice(0, 3).map(item => (
                        <span key={`service-${item.serviceId}`}>{item.label}: {item.status}</span>
                      ))}
                    </div>
                    <ActionButton onClick={() => setActiveDrawer("runtime")}>Open runtime</ActionButton>
                  </article>

                  <article className="builder-panel builder-panel-focus">
                    <p className="eyebrow">Skills</p>
                    <h3>{viewModel.drawers.builder.skillStudio.summary.executionReadyCount} execution-ready</h3>
                    <p>{viewModel.drawers.builder.skillStudio.nextQualityActions[0] || "Skill quality is stable."}</p>
                    <ActionButton onClick={() => setActiveDrawer("skills")}>Open skills</ActionButton>
                  </article>

                  <article className="builder-panel">
                    <p className="eyebrow">Workflow</p>
                    <h3>
                      {viewModel.drawers.builder.workflowStudio.recommended?.label ||
                        "Workflow recommendation pending"}
                    </h3>
                    <p>
                      {viewModel.drawers.builder.workflowStudio.recommended?.description ||
                        "Open the builder drawer for workflow details."}
                    </p>
                    <div className="builder-inline-list">
                      <span>Gap: {viewModel.drawers.builder.qualityRoadmap.gap}%</span>
                      <span>Release: {viewModel.drawers.builder.confidence.releaseStatus}</span>
                    </div>
                    <ActionButton onClick={() => setActiveDrawer("builder")}>Open builder</ActionButton>
                  </article>
                </aside>
              </div>
            </section>
          ) : (
            <section className="thread-shell agent-shell">
              <header className="thread-head agent-thread-head">
                <p className="eyebrow">Mission thread</p>
                <h1>{viewModel.thread.title}</h1>
                <p>{viewModel.thread.objective || viewModel.thread.summary}</p>
                <div className="thread-chip-row">
                  {viewModel.thread.chips.map(item => (
                    <StatusPill key={item.label} tone={item.tone}>
                      {item.label}
                    </StatusPill>
                  ))}
                  <StatusPill strong tone={viewModel.thread.status.tone}>
                    {viewModel.thread.status.label}
                  </StatusPill>
                  <StatusPill tone="neutral">
                    {isRefreshing ? "Refreshing" : "Stable"}
                  </StatusPill>
                </div>
              </header>

              <section className="mode-story mode-agent">
                <strong>Agent mode is the mission conversation.</strong>
                <p>
                  {showPersistentDrawer
                    ? "You are still in launch or setup, so the right rail stays available long enough to finish configuration."
                    : "The right rail drops away during active execution so you can just read the run, answer boundaries, and send follow-ups."}
                </p>
              </section>

              <section className="agent-runtime-strip">
                {runtimeTruth.map(item => (
                  <article className="agent-runtime-item" key={item}>
                    <span>Runtime truth</span>
                    <strong>{item}</strong>
                  </article>
                ))}
              </section>

              <section className="agent-transcript-shell">
                <div className="agent-transcript-head">
                  <p className="eyebrow">Conversation</p>
                  <span>
                    {previewLabel(previewMode, data.previewMeta)}
                    {lastPushReason ? ` · ${lastPushReason}` : ""}
                  </span>
                </div>
                <div className="agent-transcript">
                  {agentTranscript.map(item => (
                    <TranscriptMessage item={item} key={item.id} />
                  ))}
                </div>
              </section>

              <section className="thread-proof-inline agent-proof-inline">
                <div className="thread-proof-head">
                  <p className="eyebrow">Proof and review</p>
                  <ActionButton
                    onClick={() => {
                      if (!showPersistentDrawer) {
                        setUiMode("builder");
                      }
                      setActiveDrawer("proof");
                    }}
                  >
                    Open proof review
                  </ActionButton>
                </div>
                <div className="thread-proof-items">
                  {viewModel.thread.proofItems.map(item => (
                    <span className="proof-pill" key={item}>
                      {listLabel(item)}
                    </span>
                  ))}
                </div>
              </section>

              <form className="thread-composer agent-composer agent-chat-composer" onSubmit={event => event.preventDefault()}>
                <label htmlFor="thread-note">Follow-up or note</label>
                <textarea
                  id="thread-note"
                  onChange={event => setOperatorDraft(event.target.value)}
                  placeholder={
                    openClawRuntimeActive
                      ? "Send a direct follow-up to the runtime, or keep a local operator note."
                      : viewModel.thread.composerPlaceholder
                  }
                  value={operatorDraft}
                />
                <div className="thread-composer-actions">
                  {openClawRuntimeActive ? (
                    <ActionButton onClick={() => void handleAgentFollowUp()} type="button" variant="primary">
                      Send to agent
                    </ActionButton>
                  ) : null}
                  <ActionButton onClick={handleOperatorNote} type="button" variant={openClawRuntimeActive ? undefined : "primary"}>
                    Save note
                  </ActionButton>
                  <ActionButton
                    onClick={() => {
                      if (!showPersistentDrawer) {
                        setUiMode("builder");
                      }
                      setActiveDrawer("queue");
                    }}
                    type="button"
                  >
                    Review queue
                  </ActionButton>
                  <ActionButton
                    disabled={!missionActionAvailable(mission, "pause")}
                    onClick={() => void runMissionAction("pause", "Mission pause requested.")}
                    type="button"
                  >
                    Pause
                  </ActionButton>
                  <ActionButton
                    disabled={!missionActionAvailable(mission, "resume")}
                    onClick={() => void runMissionAction("resume", "Mission resume requested.")}
                    type="button"
                  >
                    Resume
                  </ActionButton>
                </div>
              </form>
            </section>
          )}
        </main>

        {showPersistentDrawer ? (
          <aside className={`fluxio-drawer ${activeDrawer ? "open" : ""}`.trim()}>
            <div className="drawer-toggle-row">
              {drawerItems.map(item => (
                <DrawerToggle
                  active={activeDrawer === item.id}
                  count={item.count}
                  key={item.id}
                  label={item.label}
                  onClick={() => setActiveDrawer(item.id)}
                  tone={item.tone}
                />
              ))}
            </div>
            {viewModel.drawers.queue.urgent && activeDrawer !== "queue" ? (
              <section className="drawer-priority">
                <div className="drawer-priority-head">
                  <div>
                    <p className="eyebrow">Queue Spotlight</p>
                    <strong>{viewModel.drawers.queue.items[0]?.title || "Queue needs attention"}</strong>
                  </div>
                  <StatusPill strong tone="warn">
                    {viewModel.drawers.queue.count} pending
                  </StatusPill>
                </div>
                <p>{viewModel.drawers.queue.items[0]?.reason || viewModel.drawers.queue.recommendation.reason}</p>
                <div className="drawer-actions">
                  <ActionButton onClick={() => setActiveDrawer("queue")} variant="primary">
                    Review queue
                  </ActionButton>
                  <ActionButton
                    disabled={!missionActionAvailable(mission, "resume")}
                    onClick={() => void runMissionAction("resume", "Mission resume requested.")}
                  >
                    Resume mission
                  </ActionButton>
                </div>
              </section>
            ) : null}
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
