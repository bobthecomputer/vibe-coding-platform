import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import { buildFixtureSnapshot, listFixtureOptions } from "./fixtures.js";
import {
  activeProfileId,
  currentProfileParameters,
  describeAskBoundary,
  missionChecksPlaceholder,
  missionObjectivePlaceholder,
  previewLabel,
  profileDetails,
  runtimeLabel,
  selectedMission,
  selectedWorkspace,
  titleizeToken,
} from "./fluxioHelpers.js";
import {
  ActionButton,
  DataList,
  Field,
  MetricStrip,
  Modal,
  RailModule,
  StatusPill,
  SurfacePanel,
  TimelineItem,
} from "./MissionControlPrimitives.jsx";
import { buildMissionControlModel, buildRecentRuns } from "./missionControlModel.js";

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
    }, 3400);
  }, []);

  return { items, push };
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

function summarizeExternalApproval(record) {
  if (!record || typeof record !== "object") {
    return null;
  }
  const title =
    record.reason ||
    record.toolId ||
    record.tool_id ||
    record.approvalId ||
    record.approval_id ||
    "External approval is waiting";
  const note = [
    record.source,
    record.requestedAt,
    record.requested_at,
    record.requestId,
    record.request_id,
  ]
    .filter(Boolean)
    .join(" · ");
  return { title, note };
}

function summarizeServiceItem(item) {
  const health =
    item.currentHealthStatus || item.current_health_status || item.lastVerificationResult || "unknown";
  return {
    label: item.label || item.serviceId || "Service",
    value: titleizeToken(health),
    note: item.details || item.installSource || "",
  };
}

function ToastHost({ items }) {
  return (
    <div aria-atomic="true" aria-live="polite" className="toast-host">
      {items.map(item => (
        <div
          className={`toast tone-${item.kind === "error" ? "bad" : item.kind === "warn" ? "warn" : "neutral"}`.trim()}
          key={item.id}
        >
          {item.message}
        </div>
      ))}
    </div>
  );
}

function SidebarItem({ active = false, title, subtitle, tone = "neutral", onClick, trailing }) {
  return (
    <button
      className={`sidebar-item ${active ? "active" : ""}`.trim()}
      onClick={onClick}
      type="button"
    >
      <div className="sidebar-item-head">
        <strong>{title}</strong>
        {trailing ? trailing : <StatusPill tone={tone}>{titleizeToken(tone)}</StatusPill>}
      </div>
      {subtitle ? <p>{subtitle}</p> : null}
    </button>
  );
}

function QueueItem({ item }) {
  return (
    <article className={`queue-item tone-${item.tone || "neutral"}`.trim()}>
      <div className="queue-item-topline">
        <span>{item.type}</span>
      </div>
      <strong>{item.title}</strong>
      <p>{item.reason}</p>
    </article>
  );
}

function BulletList({ title, items, emptyLabel = "Nothing recorded yet." }) {
  return (
    <section className="proof-block">
      <h3>{title}</h3>
      {items.length ? (
        <ul className="bullet-list">
          {items.map(item => (
            <li key={`${title}-${item}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="empty-copy">{emptyLabel}</p>
      )}
    </section>
  );
}

export function FluxioDesktopApp() {
  const searchParams = useMemo(() => new URLSearchParams(window.location.search), []);
  const storedUiMode = localStorage.getItem(STORAGE_KEYS.uiMode) || "agent";
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
  const [telegramChatId, setTelegramChatId] = useState(storedChatId);
  const [telegramBotToken, setTelegramBotToken] = useState("");
  const [lastPushReason, setLastPushReason] = useState("");
  const [liveSyncSuspended, setLiveSyncSuspended] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [data, setData] = useState({
    snapshot: null,
    onboarding: null,
    pendingApprovals: [],
    pendingQuestions: [],
    telegramReady: false,
    previewMeta: null,
  });

  const decisionQueueRef = useRef(null);
  const proofPanelRef = useRef(null);
  const urgentRailRef = useRef(null);
  const { items: toasts, push: pushToast } = useToastQueue();

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
      setIsRefreshing(true);
      try {
        if (previewMode !== "live") {
          const fixturePayload = buildFixtureSnapshot(previewMode);
          if (!fixturePayload) {
            setPreviewMode("live");
            return;
          }
          setData({
            snapshot: fixturePayload.snapshot,
            onboarding: fixturePayload.onboarding,
            pendingApprovals: fixturePayload.pendingApprovals,
            pendingQuestions: fixturePayload.pendingQuestions,
            telegramReady: fixturePayload.telegramReady,
            previewMeta: fixturePayload.meta,
          });
          return;
        }

        if (!hasTauriBackend()) {
          const fallbackPayload = buildFixtureSnapshot("live_review");
          setData({
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
          });
          return;
        }

        const [snapshot, onboarding, pendingApprovals, pendingQuestions, telegramReady] =
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
          ]);

        setData({
          snapshot,
          onboarding,
          pendingApprovals: Array.isArray(pendingApprovals) ? pendingApprovals : [],
          pendingQuestions: Array.isArray(pendingQuestions) ? pendingQuestions : [],
          telegramReady: Boolean(telegramReady),
          previewMeta: null,
        });

        if (reason !== "initialize") {
          setLastPushReason(reason);
        }
      } catch (error) {
        pushToast(`Refresh failed: ${error}`, "error");
      } finally {
        setIsRefreshing(false);
      }
    },
    [previewMode, pushToast],
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

    return () => {
      if (typeof unlistenChanged === "function") {
        unlistenChanged();
      }
      if (typeof unlistenDelta === "function") {
        unlistenDelta();
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
  const profileMeta = profileDetails(snapshot, profileId);
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
      }),
    [
      data.pendingApprovals,
      data.pendingQuestions,
      data.telegramReady,
      inboxItems,
      mission,
      profileId,
      profileParams,
      setupHealth,
      snapshot,
      workspace,
    ],
  );

  const recentRuns = useMemo(() => buildRecentRuns(snapshot), [snapshot]);
  const showUtilityControls = import.meta.hot || previewMode !== "live";
  const missionOptions = workspaceMissions.length ? workspaceMissions : missions;
  const isGuidedProfile = profileParams.visibilityLevel === "guided";
  const isDenseProfile =
    ["detailed", "expert"].includes(profileParams.visibilityLevel || "") || uiMode === "builder";

  const serviceRows = useMemo(
    () =>
      (workspace?.serviceManagement || [])
        .filter(item =>
          ["runtime", "runtime_substrate", "mcp_tool_server", "connected_app_bridge"].includes(
            item.serviceCategory,
          ),
        )
        .slice(0, 4)
        .map(summarizeServiceItem),
    [workspace],
  );

  const quickSetupActions = useMemo(
    () => [...(setupHealth.repairActions || []), ...(setupHealth.globalActions || [])].slice(0, 3),
    [setupHealth.globalActions, setupHealth.repairActions],
  );

  const externalApprovalItems = useMemo(
    () =>
      (data.pendingApprovals || [])
        .map(summarizeExternalApproval)
        .filter(Boolean)
        .map(item => ({
          tone: "warn",
          type: "Approval",
          title: item.title,
          reason: item.note || "Pending approval surfaced outside the current mission payload.",
        })),
    [data.pendingApprovals],
  );

  const supervisionQueue = useMemo(() => {
    const missionItems = viewModel.decisionQueue.items || [];
    return [...missionItems, ...externalApprovalItems].slice(0, 5);
  }, [externalApprovalItems, viewModel.decisionQueue.items]);

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

  const scrollTo = useCallback(targetRef => {
    targetRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const runMissionAction = useCallback(
    async (action, successMessage) => {
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
    [mission, previewMode, pushToast, refreshAll],
  );

  const runWorkspaceAction = useCallback(
    async (surface, actionId, approved = false) => {
      if (previewMode !== "live" || !hasTauriBackend()) {
        pushToast("Preview mode is read-only for setup and service actions.", "warn");
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
    [previewMode, pushToast, refreshAll, workspace?.workspace_id],
  );

  const openMissionDialog = useCallback(() => {
    setMissionForm(current => ({
      ...current,
      workspaceId: workspace?.workspace_id || current.workspaceId || "",
      runtime: mission?.runtime_id || workspace?.default_runtime || current.runtime,
      profile: mission?.selected_profile || workspace?.user_profile || profileId,
    }));
    setShowMissionDialog(true);
  }, [
    mission?.runtime_id,
    mission?.selected_profile,
    profileId,
    workspace?.default_runtime,
    workspace?.user_profile,
    workspace?.workspace_id,
  ]);

  const handleReviewAction = useCallback(() => {
    if (viewModel.decisionQueue.urgent) {
      scrollTo(decisionQueueRef);
      return;
    }
    scrollTo(proofPanelRef);
  }, [scrollTo, viewModel.decisionQueue.urgent]);

  const handlePrimaryAction = useCallback(() => {
    switch (viewModel.missionHeader.primaryAction.kind) {
      case "start":
        openMissionDialog();
        return;
      case "resume":
        void runMissionAction("resume", "Mission resume requested.");
        return;
      case "urgent":
        scrollTo(urgentRailRef);
        return;
      case "proof":
        scrollTo(proofPanelRef);
        return;
      default:
        handleReviewAction();
    }
  }, [
    handleReviewAction,
    openMissionDialog,
    runMissionAction,
    scrollTo,
    viewModel.missionHeader.primaryAction.kind,
  ]);

  const handleWorkspaceSubmit = useCallback(
    async event => {
      event.preventDefault();
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
    [previewMode, pushToast, refreshAll, workspaceForm],
  );

  const handleMissionSubmit = useCallback(
    async event => {
      event.preventDefault();
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
    [missionForm, previewMode, pushToast, refreshAll, telegramChatId],
  );

  const handleSaveTelegram = useCallback(
    async event => {
      event.preventDefault();

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
    [previewMode, pushToast, refreshAll, telegramBotToken],
  );

  const handleClearTelegram = useCallback(async () => {
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
  }, [previewMode, pushToast, refreshAll]);

  const handleSendTestPing = useCallback(async () => {
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
  }, [previewMode, pushToast, telegramChatId]);

  const currentMissionSubtitle = mission
    ? `${runtimeLabel(mission.runtime_id)} · ${titleizeToken(mission.state?.status || "active")}`
    : "Pick or launch the first supervised run.";
  const topBarInboxLabel =
    viewModel.topBar.inboxCount > 0 ? `Inbox ${viewModel.topBar.inboxCount}` : "Inbox";
  const profileSummary =
    profileMeta.description ||
    "Fluxio adapts safety, explanation, and density to the operator profile.";
  const latestInboxPreview =
    inboxItems[0]?.previewMessage ||
    data.pendingQuestions?.[0]?.question ||
    "No escalations or remote inbox events are waiting.";

  return (
    <div className="mission-control-shell" data-mode={uiMode} data-profile={profileId}>
      <header className="mission-topbar">
        <div className="topbar-leading">
          <div className="product-lockup">
            <span className="product-mark">F</span>
            <div>
              <strong>Fluxio</strong>
              <p>Supervised mission control for real agent runs</p>
            </div>
          </div>

          <Field className="topbar-select" label="Workspace">
            <select
              aria-label="Select workspace"
              onChange={event => setSelectedWorkspaceId(event.target.value || null)}
              value={selectedWorkspaceId || ""}
            >
              {workspaces.length === 0 ? <option value="">No workspace</option> : null}
              {workspaces.map(item => (
                <option key={item.workspace_id} value={item.workspace_id}>
                  {item.name}
                </option>
              ))}
            </select>
          </Field>

          <Field className="topbar-select" label="Mission">
            <select
              aria-label="Select mission"
              onChange={event => setSelectedMissionId(event.target.value || null)}
              value={selectedMissionId || ""}
            >
              {missionOptions.length === 0 ? <option value="">No mission</option> : null}
              {missionOptions.map(item => (
                <option key={item.mission_id} value={item.mission_id}>
                  {item.title || item.objective}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <div className="topbar-statuses">
          <StatusPill tone="neutral">{viewModel.topBar.environmentLabel}</StatusPill>
          <StatusPill strong tone={viewModel.topBar.liveStatus.tone}>
            {viewModel.topBar.liveStatus.label}
          </StatusPill>
          {showUtilityControls ? (
            <div className="utility-cluster">
              <Field className="utility-field" label="Preview">
                <select onChange={event => setPreviewMode(event.target.value)} value={previewMode}>
                  {FIXTURE_OPTIONS.map(option => (
                    <option key={option.id} value={option.id}>
                      {option.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field className="utility-field" label="Sync">
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
            </div>
          ) : null}
        </div>

        <div className="topbar-actions">
          <div aria-label="Fluxio mode" className="mode-toggle" role="tablist">
            {["agent", "builder"].map(mode => (
              <button
                aria-selected={uiMode === mode}
                className={uiMode === mode ? "active" : ""}
                key={mode}
                onClick={() => setUiMode(mode)}
                role="tab"
                type="button"
              >
                {titleizeToken(mode)}
              </button>
            ))}
          </div>

          <ActionButton onClick={openMissionDialog} variant="primary">
            Start
          </ActionButton>
          <ActionButton
            disabled={!missionActionAvailable(mission, "pause")}
            onClick={() => void runMissionAction("pause", "Mission pause requested.")}
          >
            Pause
          </ActionButton>
          <ActionButton
            disabled={!missionActionAvailable(mission, "resume")}
            onClick={() => void runMissionAction("resume", "Mission resume requested.")}
          >
            Resume
          </ActionButton>
          <ActionButton onClick={handleReviewAction}>Review</ActionButton>
          <ActionButton onClick={() => scrollTo(urgentRailRef)}>{topBarInboxLabel}</ActionButton>
        </div>
      </header>

      <div className="mission-layout">
        {/* Left rail stays narrow and navigation-first so setup forms do not compete with the live run. */}
        <aside className="mission-left-rail">
          <div className="left-rail-scroll">
            <section className="rail-section">
              <div className="rail-section-topline">
                <p className="eyebrow">Launch</p>
              </div>
              <ActionButton onClick={openMissionDialog} variant="primary">
                New mission
              </ActionButton>
            </section>

            <section className="rail-section">
              <div className="rail-section-topline">
                <div>
                  <p className="eyebrow">Workspaces</p>
                  <h2>Project roots</h2>
                </div>
                <ActionButton onClick={() => setShowWorkspaceDialog(true)}>Add</ActionButton>
              </div>
              <div className="sidebar-list">
                {workspaces.length ? (
                  workspaces.map(item => (
                    <SidebarItem
                      active={item.workspace_id === selectedWorkspaceId}
                      key={item.workspace_id}
                      onClick={() => setSelectedWorkspaceId(item.workspace_id)}
                      subtitle={item.root_path}
                      title={item.name}
                      tone={item.runtimeStatus?.detected ? "good" : "warn"}
                      trailing={
                        <StatusPill tone={item.runtimeStatus?.detected ? "good" : "warn"}>
                          {item.runtimeStatus?.detected ? "Ready" : "Check runtime"}
                        </StatusPill>
                      }
                    />
                  ))
                ) : (
                  <div className="empty-note">
                    Add a real workspace so Fluxio can supervise one concrete mission.
                  </div>
                )}
              </div>
            </section>

            <section className="rail-section">
              <div className="rail-section-topline">
                <div>
                  <p className="eyebrow">Missions</p>
                  <h2>Active threads</h2>
                </div>
              </div>
              <div className="sidebar-list">
                {missionOptions.length ? (
                  missionOptions.map(item => (
                    <SidebarItem
                      active={item.mission_id === selectedMissionId}
                      key={item.mission_id}
                      onClick={() => setSelectedMissionId(item.mission_id)}
                      subtitle={`${runtimeLabel(item.runtime_id)} · ${titleizeToken(item.state?.status || "draft")}`}
                      title={item.title || item.objective}
                      tone={
                        item.proof?.pending_approvals?.length
                          ? "warn"
                          : String(item.state?.status || "").includes("failed")
                            ? "bad"
                            : "neutral"
                      }
                      trailing={
                        <StatusPill
                          tone={
                            item.proof?.pending_approvals?.length
                              ? "warn"
                              : String(item.state?.status || "").includes("failed")
                                ? "bad"
                                : "neutral"
                          }
                        >
                          {item.proof?.pending_approvals?.length
                            ? `${item.proof.pending_approvals.length} waiting`
                            : titleizeToken(item.state?.status || "draft")}
                        </StatusPill>
                      }
                    />
                  ))
                ) : (
                  <div className="empty-note">
                    Your first mission becomes the center of the supervision surface.
                  </div>
                )}
              </div>
            </section>

            <section className="rail-section">
              <div className="rail-section-topline">
                <div>
                  <p className="eyebrow">Inbox</p>
                  <h2>{topBarInboxLabel}</h2>
                </div>
                <ActionButton onClick={() => scrollTo(urgentRailRef)}>Open</ActionButton>
              </div>
              <div className="inbox-preview-card">
                <strong>{viewModel.topBar.inboxCount > 0 ? "Needs review" : "Queue clear"}</strong>
                <p>{latestInboxPreview}</p>
              </div>
            </section>

            <section className="rail-section">
              <div className="rail-section-topline">
                <div>
                  <p className="eyebrow">Recent runs</p>
                  <h2>Proof trail</h2>
                </div>
              </div>
              <div className="sidebar-list">
                {recentRuns.length ? (
                  recentRuns.map(item => (
                    <SidebarItem
                      key={`${item.title}-${item.subtitle}`}
                      subtitle={item.subtitle}
                      title={item.title}
                      tone={item.tone}
                      trailing={<StatusPill tone={item.tone}>{titleizeToken(item.tone)}</StatusPill>}
                    />
                  ))
                ) : (
                  <div className="empty-note">Completed runs will appear here for fast recall.</div>
                )}
              </div>
            </section>

            {!setupHealth.environmentReady ? (
              <section className="rail-section setup-attention-card">
                <p className="eyebrow">Setup attention</p>
                <strong>{setupHealth.blockerExplanations?.[0] || "Environment needs repair."}</strong>
                <p>
                  Fluxio should not imply readiness while Hermes or required tooling is still
                  blocked.
                </p>
              </section>
            ) : null}
          </div>
        </aside>

        {/* The center column is intentionally proof-first: current mission, live run state, then evidence and decisions. */}
        <main className="mission-center">
          <section className="mission-header-card">
            <div className="mission-header-copy">
              <p className="eyebrow">Mission</p>
              <div className="mission-title-line">
                <h1>{viewModel.missionHeader.title}</h1>
                <StatusPill strong tone={viewModel.topBar.liveStatus.tone}>
                  {currentMissionSubtitle}
                </StatusPill>
              </div>
              <p className="mission-objective">{viewModel.missionHeader.objective}</p>
              <div className="mission-pill-row">
                {viewModel.missionHeader.pills.map(item => (
                  <StatusPill key={item.label} tone={item.tone}>
                    {item.label}
                  </StatusPill>
                ))}
              </div>
              <p className="mission-summary">{viewModel.missionHeader.summary}</p>

              <div className="operator-strip">
                <div>
                  <span>What Fluxio is doing</span>
                  <strong>
                    {viewModel.missionHeader.operatorSummary?.now || viewModel.currentRun.title}
                  </strong>
                </div>
                <div>
                  <span>Why the next action exists</span>
                  <strong>
                    {viewModel.missionHeader.operatorSummary?.reason ||
                      viewModel.missionHeader.primaryAction.reason}
                  </strong>
                </div>
              </div>
            </div>

            <aside className="mission-cta-card">
              <p className="eyebrow">Safest next action</p>
              <strong>{viewModel.missionHeader.primaryAction.label}</strong>
              <p>{viewModel.missionHeader.primaryAction.reason}</p>
              <ActionButton onClick={handlePrimaryAction} variant="primary">
                {viewModel.missionHeader.primaryAction.label}
              </ActionButton>
              <div className="cta-footnotes">
                <span>{profileSummary}</span>
                {showUtilityControls ? (
                  <span>{previewLabel(previewMode, data.previewMeta)}</span>
                ) : null}
                {lastPushReason ? <span>Synced from {lastPushReason}</span> : null}
              </div>
            </aside>
          </section>

          <section className={`current-run-card tone-${viewModel.topBar.liveStatus.tone}`.trim()}>
            <div className="current-run-topline">
              <div>
                <p className="eyebrow">Current run</p>
                <h2>{viewModel.currentRun.title}</h2>
                <p>{viewModel.currentRun.summary}</p>
              </div>
              <div className="run-state-column">
                <StatusPill strong tone={viewModel.topBar.liveStatus.tone}>
                  {viewModel.topBar.liveStatus.label}
                </StatusPill>
                <span>{isRefreshing ? "Refreshing" : "Stable mission snapshot"}</span>
              </div>
            </div>

            <MetricStrip columns={4} items={viewModel.currentRun.metrics} />

            <div className="run-detail-grid">
              <DataList items={viewModel.currentRun.details.slice(0, 2)} />
              <DataList items={viewModel.currentRun.details.slice(2)} />
            </div>

            {!setupHealth.environmentReady && quickSetupActions.length ? (
              <div className="setup-action-strip">
                <strong>Environment still blocks clean supervision.</strong>
                <div className="inline-actions">
                  {quickSetupActions.map(action => (
                    <ActionButton
                      key={action.actionId}
                      onClick={() => void runWorkspaceAction("setup", action.actionId)}
                    >
                      {action.label}
                    </ActionButton>
                  ))}
                </div>
              </div>
            ) : null}
          </section>

          <div className="mission-evidence-grid">
            <div ref={proofPanelRef}>
              <SurfacePanel
                className="proof-panel"
                eyebrow="Proof"
                summary="Concrete evidence should outweigh explanatory chrome on the main screen."
                title="Evidence and outputs"
              >
                <div className="proof-hero">
                  <span>Verification</span>
                  <strong>{viewModel.proof.verificationSummary}</strong>
                  <p>{viewModel.proof.diffSummary}</p>
                </div>

                <div className="proof-grid">
                  <BulletList items={viewModel.proof.filesTouched} title="Files touched" />
                  <BulletList
                    emptyLabel="No command or log evidence recorded yet."
                    items={viewModel.proof.commandEvidence}
                    title="Commands and logs"
                  />
                  <BulletList items={viewModel.proof.artifacts} title="Artifacts" />
                  <section className="proof-block">
                    <h3>Diff summary</h3>
                    <p className="proof-diff-copy">{viewModel.proof.diffSummary}</p>
                    {workspace?.gitSnapshot ? (
                      <div className="proof-diff-stats">
                        <span>{workspace.gitSnapshot.branch || "unknown branch"}</span>
                        <span>{workspace.gitSnapshot.stagedCount || 0} staged</span>
                        <span>{workspace.gitSnapshot.unstagedCount || 0} unstaged</span>
                        <span>{workspace.gitSnapshot.untrackedCount || 0} untracked</span>
                      </div>
                    ) : null}
                  </section>
                </div>
              </SurfacePanel>
            </div>

            <div ref={decisionQueueRef}>
              <SurfacePanel
                className={`decision-queue-panel ${viewModel.decisionQueue.urgent ? "urgent" : ""}`.trim()}
                eyebrow="Decision queue"
                summary="Show approvals, questions, and the recommended next move in one concentrated lane."
                title="What needs operator judgment"
              >
                <div
                  className={`queue-recommendation tone-${viewModel.decisionQueue.urgent ? "warn" : "good"}`.trim()}
                >
                  <span>Recommended next action</span>
                  <strong>{viewModel.decisionQueue.recommendation.title}</strong>
                  <p>{viewModel.decisionQueue.recommendation.reason}</p>
                </div>

                <div className="queue-list">
                  {supervisionQueue.map(item => (
                    <QueueItem item={item} key={`${item.type}-${item.title}`} />
                  ))}
                </div>
              </SurfacePanel>
            </div>
          </div>

          <SurfacePanel
            className="timeline-panel"
            eyebrow="Timeline"
            summary="Keep the mission legible as a chronological proof trail, not an opaque state machine."
            title="Chronology"
          >
            <div className="timeline-list">
              {viewModel.timeline.map(item => (
                <TimelineItem
                  detail={item.detail}
                  key={`${item.kind}-${item.title}-${item.meta}`}
                  kind={item.kind}
                  meta={item.meta}
                  title={item.title}
                  tone={item.tone}
                />
              ))}
            </div>
          </SurfacePanel>
        </main>

        {/* The right rail combines urgency, guardrails, runtime truth, and escalation into a compact supervision lane. */}
        <aside className="supervision-rail">
          <div className="supervision-scroll">
            <div ref={urgentRailRef}>
              <RailModule
                className="urgent-module"
                eyebrow="Needs review now"
                summary="Approval pressure should be impossible to miss from anywhere in the shell."
                title={
                  supervisionQueue.length
                    ? `${supervisionQueue.length} item${supervisionQueue.length === 1 ? "" : "s"} waiting`
                    : "Queue clear"
                }
                tone={supervisionQueue.length ? "warn" : "good"}
              >
                <div className="urgent-list">
                  {supervisionQueue.length ? (
                    supervisionQueue.map(item => (
                      <div className="urgent-row" key={`${item.type}-${item.title}`}>
                        <strong>{item.title}</strong>
                        <p>
                          {item.type} · {item.reason}
                        </p>
                      </div>
                    ))
                  ) : (
                    <div className="empty-note">No approvals or operator questions are waiting.</div>
                  )}
                </div>
                <div className="rail-actions">
                  <ActionButton onClick={handleReviewAction} variant="primary">
                    Review queue
                  </ActionButton>
                  <ActionButton onClick={() => scrollTo(proofPanelRef)}>Review proof</ActionButton>
                </div>
              </RailModule>
            </div>

            <RailModule
              eyebrow="Guardrails and runtime"
              summary="Keep safety policy and environment truth adjacent so operators do not confuse permission with readiness."
              title="Safety boundary"
              tone={setupHealth.environmentReady ? "neutral" : "warn"}
            >
              <DataList items={viewModel.rail.guardrails} />
              <p className="rail-footnote">
                {describeAskBoundary(
                  profileParams,
                  mission?.missionLoop?.timeBudget?.runUntilBehavior ||
                    mission?.run_budget?.run_until_behavior ||
                    profileParams.autoContinueBehavior,
                )}
              </p>
              {serviceRows.length ? (
                <div className="service-stack">
                  {serviceRows.map(item => (
                    <div className="service-row" key={`${item.label}-${item.value}`}>
                      <strong>{item.label}</strong>
                      <span>{item.value}</span>
                      <p>{item.note}</p>
                    </div>
                  ))}
                </div>
              ) : null}
              {quickSetupActions.length ? (
                <div className="rail-actions">
                  {quickSetupActions.map(action => (
                    <ActionButton
                      key={action.actionId}
                      onClick={() => void runWorkspaceAction("setup", action.actionId)}
                    >
                      {action.label}
                    </ActionButton>
                  ))}
                </div>
              ) : null}
            </RailModule>

            <RailModule
              eyebrow="Context"
              summary="Operators need to know what memory and context Fluxio is actually using before they trust the next step."
              title="Memory and context"
              tone="neutral"
            >
              <DataList items={viewModel.rail.context.slice(0, isGuidedProfile ? 2 : 4)} />
              {isDenseProfile ? (
                <div className="context-detail-callout">
                  <strong>Operator mode</strong>
                  <p>
                    {uiMode === "builder"
                      ? "Builder mode keeps more repo and runtime detail visible without leaving the supervision shell."
                      : "Agent mode keeps the run, proof, and next action as the primary read."}
                  </p>
                </div>
              ) : null}
            </RailModule>

            <RailModule
              eyebrow="Escalation"
              summary="Long autonomous runs only feel safe when the interruption path is obvious and testable."
              title="Remote reachability"
              tone={data.telegramReady ? "good" : "warn"}
            >
              <div className="escalation-card">
                <strong>{data.telegramReady ? "Telegram ready" : "Telegram not configured"}</strong>
                <p>{latestInboxPreview}</p>
              </div>
              <Field label="Telegram chat ID">
                <input
                  onChange={event => setTelegramChatId(event.target.value)}
                  placeholder="123456789"
                  value={telegramChatId}
                />
              </Field>
              <div className="rail-actions">
                <ActionButton onClick={() => setShowEscalationDialog(true)} variant="primary">
                  Configure
                </ActionButton>
                <ActionButton onClick={() => void handleSendTestPing()}>Send test ping</ActionButton>
              </div>
            </RailModule>
          </div>
        </aside>
      </div>

      <Modal
        actions={
          <ActionButton onClick={handleWorkspaceSubmit} type="submit" variant="primary">
            Save workspace
          </ActionButton>
        }
        onClose={() => setShowWorkspaceDialog(false)}
        open={showWorkspaceDialog}
        summary="Workspace creation lives in a dialog so the left rail stays focused on navigation."
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
        summary="This launch form is kept separate so the main screen stays centered on supervision rather than configuration."
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
        summary="Remote escalation belongs to supervision, but configuration stays out of the main run lane."
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
