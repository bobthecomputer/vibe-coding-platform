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

function NavItem({ active = false, title, subtitle, onClick, tone = "neutral", badge }) {
  return (
    <button
      className={`fluxio-nav-item ${active ? "active" : ""}`.trim()}
      onClick={onClick}
      type="button"
    >
      <div className="fluxio-nav-item-top">
        <strong>{title}</strong>
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

function DrawerToggle({ active, label, count, tone, onClick }) {
  return (
    <button className={`drawer-toggle ${active ? "active" : ""}`.trim()} onClick={onClick} type="button">
      <span>{label}</span>
      <strong className={toneClass(tone)}>{count > 0 ? count : ""}</strong>
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
  return {
    userProfile: workspace?.user_profile || fallbackProfile || "builder",
    preferredHarness: workspace?.preferred_harness || "fluxio_hybrid",
    routingStrategy: workspace?.routing_strategy || "profile_default",
    autoOptimizeRouting: Boolean(workspace?.auto_optimize_routing),
    minimaxAuthMode: workspace?.minimax_auth_mode || "none",
    commitMessageStyle: workspace?.commit_message_style || "scoped",
    executionTargetPreference: workspace?.execution_target_preference || "profile_default",
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

        if (!mountedRef.current) {
          return;
        }

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
    if (viewModel.drawers.queue.urgent) {
      setActiveDrawer("queue");
      return;
    }
    if (uiMode === "builder" && activeDrawer !== "builder") {
      setActiveDrawer("builder");
      return;
    }
    if (!mission && uiMode === "agent") {
      setActiveDrawer("context");
    }
  }, [activeDrawer, mission, uiMode, viewModel.drawers.queue.urgent]);

  useEffect(() => {
    if (uiMode === "agent" && activeDrawer === "builder") {
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
        pushToast("No service repair action is currently available.", "warn");
        return;
      }
      if (actionKind === "skill") {
        setSkillStudioFilter("needs_attention");
        setActiveDrawer("builder");
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

  const handleOperatorNote = useCallback(
    event => {
      event.preventDefault();
      if (!operatorDraft.trim()) {
        return;
      }
      markAction("composer:add-note");
      setOperatorNotes(current => [
        {
          id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
          title: "Operator note",
          detail: operatorDraft.trim(),
          meta: "Local note",
          tone: "neutral",
          createdAt: new Date().toISOString(),
        },
        ...current,
      ]);
      setOperatorDraft("");
      pushToast("Operator note added to this session.", "info");
    },
    [markAction, operatorDraft, pushToast],
  );

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
    ];
    if (uiMode === "builder") {
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
            <p className="eyebrow">Builder review</p>
            <h2>Confidence and control surfaces</h2>
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
    <div className="fluxio-shell" data-mode={uiMode} data-profile={profileId}>
      <header className="fluxio-topbar">
        <Field className="fluxio-control" label="Workspace">
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

        <Field className="fluxio-control" label="Mission">
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

        <div aria-label="Fluxio mode" className="fluxio-mode" role="tablist">
          {["agent", "builder"].map(mode => (
            <button
              aria-selected={uiMode === mode}
              className={uiMode === mode ? "active" : ""}
              key={mode}
              onClick={() => {
                markAction(`mode:${mode}`);
                setUiMode(mode);
              }}
              role="tab"
              type="button"
            >
              {titleizeToken(mode)}
            </button>
          ))}
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
        <aside className="fluxio-nav">
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
        </aside>

        <main className="fluxio-main">
          {!mission ? (
            <section className="fluxio-empty">
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
          ) : (
            <section className="thread-shell">
              <header className="thread-head">
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

              <div className="thread-lane">
                {viewModel.thread.sections.map(item => (
                  <ThreadSection item={item} key={item.id} />
                ))}
              </div>

              {uiMode === "builder" ? (
                <section className="builder-inline">
                  <article className="builder-inline-card">
                    <p className="eyebrow">Release confidence</p>
                    <h3>{viewModel.drawers.builder.confidence.label}</h3>
                    <p>{viewModel.drawers.builder.confidence.phase}</p>
                    <div className="milestone-strip">
                      {viewModel.drawers.builder.confidence.milestones.map(item => (
                        <article className="milestone-card" key={item.id}>
                          <span>{item.label}</span>
                          <strong>{item.percent}%</strong>
                          <p>{item.detail}</p>
                        </article>
                      ))}
                    </div>
                  </article>

                  <article className="builder-inline-card">
                    <p className="eyebrow">Workflow studio</p>
                    <h3>
                      {viewModel.drawers.builder.workflowStudio.recommended?.label ||
                        "Workflow recommendation pending"}
                    </h3>
                    <p>
                      {viewModel.drawers.builder.workflowStudio.recommended?.description ||
                        "Select a recipe in the Builder drawer."}
                    </p>
                    <p>
                      {viewModel.drawers.builder.qualityRoadmap.headline}
                      {` · Gap ${viewModel.drawers.builder.qualityRoadmap.gap}%`}
                    </p>
                    {viewModel.drawers.builder.workflowStudio.recommended ? (
                      <div className="builder-inline-list">
                        <span>
                          Audience:{" "}
                          {viewModel.drawers.builder.workflowStudio.recommended.audience}
                        </span>
                        <span>
                          Runtime:{" "}
                          {viewModel.drawers.builder.workflowStudio.recommended.runtimeChoice}
                        </span>
                        <span>
                          Status: {viewModel.drawers.builder.workflowStudio.recommended.status}
                        </span>
                      </div>
                    ) : null}
                  </article>
                </section>
              ) : null}

              <section className="thread-proof-inline">
                <div className="thread-proof-head">
                  <p className="eyebrow">Proof deltas</p>
                  <ActionButton onClick={() => setActiveDrawer("proof")}>Open drawer</ActionButton>
                </div>
                <div className="thread-proof-items">
                  {viewModel.thread.proofItems.map(item => (
                    <span className="proof-pill" key={item}>
                      {listLabel(item)}
                    </span>
                  ))}
                </div>
              </section>

              <section className="thread-events">
                <div className="thread-events-head">
                  <p className="eyebrow">Activity transcript</p>
                  <span>
                    {previewLabel(previewMode, data.previewMeta)}
                    {lastPushReason ? ` · ${lastPushReason}` : ""}
                  </span>
                </div>
                <div className="thread-event-list">
                  {threadEvents.map(item => (
                    <article className={`thread-event ${toneClass(item.tone || "neutral")}`} key={`${item.kind}-${item.title}-${item.meta}`}>
                      <div className="thread-event-top">
                        <span>{titleizeToken(item.kind || "event")}</span>
                        <span>{timestampLabel(item.meta)}</span>
                      </div>
                      <strong>{item.title}</strong>
                      {item.detail ? <p>{item.detail}</p> : null}
                    </article>
                  ))}
                </div>
              </section>

              <form className="thread-composer" onSubmit={handleOperatorNote}>
                <label htmlFor="thread-note">Operator note</label>
                <textarea
                  id="thread-note"
                  onChange={event => setOperatorDraft(event.target.value)}
                  placeholder={viewModel.thread.composerPlaceholder}
                  value={operatorDraft}
                />
                <div className="thread-composer-actions">
                  <ActionButton type="submit" variant="primary">
                    Add note
                  </ActionButton>
                  <ActionButton onClick={() => setActiveDrawer("queue")} type="button">
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
          <div className="drawer-content">{renderDrawerPanel()}</div>
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
