import { invoke } from "@tauri-apps/api/core";

type JsonRecord = Record<string, unknown>;

const COMMANDS: Record<string, string> = {
  "mission.start": "start_control_room_mission_command",
  "mission.action": "apply_control_room_mission_action_command",
  "approval.resolve": "resolve_action_approval",
  "workspace.action": "apply_control_room_workspace_action_command",
};

function hasTauriBackend(): boolean {
  return Boolean((globalThis as any).window?.__TAURI__ || (globalThis as any).window?.__TAURI_INTERNALS__);
}

function webBackendBaseUrl(): string {
  const configured =
    (import.meta as any).env?.VITE_FLUXIO_BACKEND_URL ||
    (globalThis as any).window?.__FLUXIO_BACKEND_URL__ ||
    "";
  return String(configured || "").trim().replace(/\/$/, "");
}

async function callFluxioBackend(command: string, payload: JsonRecord | null = null): Promise<JsonRecord> {
  if (hasTauriBackend()) {
    const result = payload === null ? await invoke(command) : await invoke(command, payload);
    return asRecord(result);
  }

  const response = await fetch(`${webBackendBaseUrl()}/api/backend`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command, payload }),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok || result?.ok === false) {
    throw new Error(result?.error || `${command} failed with HTTP ${response.status}`);
  }
  return asRecord(result?.data);
}

function asList(value: unknown): JsonRecord[] {
  return Array.isArray(value) ? (value as JsonRecord[]) : [];
}

function asRecord(value: unknown): JsonRecord {
  if (value && typeof value === "object") {
    return value as JsonRecord;
  }
  return {};
}

export async function getSnapshot(root: string | null = null): Promise<JsonRecord> {
  try {
    const snapshot = await callFluxioBackend("get_control_room_snapshot_command", {
      payload: { root },
    });
    return asRecord(snapshot);
  } catch {
    return {};
  }
}

export async function dispatchCommand(
  command: string,
  payload: JsonRecord = {},
): Promise<JsonRecord> {
  const tauriCommand = COMMANDS[command];
  if (!tauriCommand) {
    throw new Error(`Unsupported bridge command: ${command}`);
  }
  const result = await callFluxioBackend(tauriCommand, { payload });
  return asRecord(result);
}

export function getTurnDiff(snapshot: JsonRecord, missionId?: string): JsonRecord {
  const missions = asList(snapshot.missions);
  const target =
    missions.find(item => String(item.mission_id || "") === String(missionId || "")) ||
    missions[missions.length - 1] ||
    {};
  const changedFiles = asList(asRecord(target).changed_files).map(String);
  const actionHistory = asList(asRecord(target).action_history);
  return {
    missionId: asRecord(target).mission_id || "",
    changedFiles,
    actionCount: actionHistory.length,
  };
}

export function getFullThreadDiff(snapshot: JsonRecord): JsonRecord {
  const missions = asList(snapshot.missions);
  const changed = new Set<string>();
  for (const mission of missions) {
    const files = asList(asRecord(mission).changed_files);
    for (const file of files) {
      changed.add(String(file));
    }
  }
  return {
    missionCount: missions.length,
    changedFiles: [...changed],
  };
}

function textValue(value: unknown, fallback = ""): string {
  const next = String(value ?? "").trim();
  return next || fallback;
}

function firstTextValue(values: unknown[], fallback = ""): string {
  for (const value of values) {
    const next = textValue(value);
    if (next) {
      return next;
    }
  }
  return fallback;
}

function textList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map(item => textValue(item)).filter(Boolean);
  }
  const single = textValue(value);
  return single ? [single] : [];
}

export function replayEvents(snapshot: JsonRecord): JsonRecord[] {
  const timeline = asList(snapshot.activity);
  return timeline.map(item => ({
    kind: item.kind || "activity",
    message: item.message || "",
    timestamp: item.timestamp || "",
  }));
}

export function buildLiveReviewWorkbench(snapshot: JsonRecord): JsonRecord {
  const missions = asList(snapshot.missions);
  const latestMission = asRecord(missions[missions.length - 1]);
  const activity = replayEvents(snapshot);
  const targetKind = textValue(
    snapshot.reviewTargetKind || snapshot.targetKind || latestMission.target_kind,
    "browser",
  );
  const changedFiles = textList(latestMission.changed_files).slice(0, 6);
  const targetMap: Record<string, JsonRecord> = {
    app: {
      kind: "app",
      label: firstTextValue(
        [snapshot.targetApp, latestMission.app_name, latestMission.workspace_name, snapshot.productName],
        "Connected app",
      ),
      detail: firstTextValue(
        [snapshot.targetWindow, latestMission.window_title, snapshot.windowTitle],
        "Desktop or installed app surface",
      ),
    },
    browser: {
      kind: "browser",
      label: firstTextValue(
        [snapshot.browserLabel, latestMission.browser_label, snapshot.browserUrl],
        "Browser workspace",
      ),
      detail: firstTextValue(
        [snapshot.browserUrl, latestMission.browser_url, latestMission.url],
        "Web session under review",
      ),
    },
    html: {
      kind: "html",
      label: firstTextValue(
        [snapshot.htmlLabel, latestMission.html_label, snapshot.pageTitle],
        "HTML surface",
      ),
      detail: firstTextValue(
        [snapshot.pageTitle, latestMission.page_title, snapshot.htmlPath],
        "Rendered document or component tree",
      ),
    },
    program: {
      kind: "program",
      label: firstTextValue(
        [snapshot.programLabel, latestMission.program_name, latestMission.command],
        "Program trace",
      ),
      detail: firstTextValue(
        [latestMission.command, snapshot.programPath, latestMission.program_path],
        "Executable, script, or CLI surface",
      ),
    },
    window: {
      kind: "window",
      label: firstTextValue(
        [snapshot.windowLabel, latestMission.window_title, snapshot.windowTitle],
        "Window review",
      ),
      detail: firstTextValue(
        [snapshot.windowTitle, latestMission.window_title, latestMission.session_id],
        "Focused window and layout state",
      ),
    },
  };
  const target = targetMap[targetKind] || targetMap.browser;
  const runtimeStatus = {
    browser: firstTextValue(
      [snapshot.browserStatus, snapshot.runtimeBrowserStatus, latestMission.browser_status],
      "ready",
    ),
    computerUse: firstTextValue(
      [snapshot.computerUseStatus, snapshot.runtimeComputerUseStatus, latestMission.computer_use_status],
      "connected",
    ),
    autotest: firstTextValue(
      [snapshot.autotestStatus, snapshot.runtimeAutotestStatus, latestMission.autotest_status],
      "queued",
    ),
  };
  const panes = [
    {
      id: "agent-instructions",
      label: "Agent feedback",
      purpose: "Convert visual comments into structured guidance for the next agent turn.",
      status: modeText(runtimeStatus.autotest),
    },
    {
      id: "live-preview",
      label: "Live preview",
      purpose: `Show the selected ${target.kind} surface with pins, panes, and region context.`,
      status: modeText(runtimeStatus.browser),
    },
    {
      id: "proof-evidence",
      label: "Evidence",
      purpose: "Keep screenshots, timelapse, files, tools, and replay activity attached to each review.",
      status: modeText(runtimeStatus.computerUse),
    },
  ];
  const evidence = {
    screenshots: textList(snapshot.screenshots || snapshot.screenshotEvidence || latestMission.screenshots || latestMission.screenshot),
    timelapse: textList(snapshot.timelapse || snapshot.timelapseFrames || latestMission.timelapse || latestMission.timelapse_frames),
    files: textList(snapshot.files || snapshot.fileEvidence || latestMission.file_evidence).concat(changedFiles).slice(0, 8),
    tools: textList(snapshot.tools || snapshot.toolEvidence || latestMission.tools || latestMission.tool_history),
    activity: activity.slice(-6),
  };
  const annotations = [
    {
      id: "annotation-1",
      pin: "1",
      target: target.kind,
      pane: "live-preview",
      region: "primary surface",
      selector: firstTextValue([snapshot.annotationSelector, latestMission.selector], "main viewport"),
      comment: firstTextValue(
        [snapshot.annotationComment, latestMission.summary, latestMission.objective],
        "Keep the most important UI region visible.",
      ),
      feedback: "Agent-facing note",
      evidence: "screenshot",
    },
    {
      id: "annotation-2",
      pin: "2",
      target: target.kind,
      pane: "agent-instructions",
      region: "supporting panel",
      selector: firstTextValue([snapshot.annotationSelector2, latestMission.panel_selector], "right side panel"),
      comment: firstTextValue(
        [snapshot.annotationComment2, latestMission.next_actions, latestMission.action],
        "Use the side panel for proof, not for noise.",
      ),
      feedback: "Review comment",
      evidence: "activity replay",
    },
    {
      id: "annotation-3",
      pin: "3",
      target: target.kind,
      pane: "proof-evidence",
      region: "evidence lane",
      selector: firstTextValue([snapshot.annotationSelector3, latestMission.evidence_selector], "proof drawer"),
      comment: changedFiles.length ? `Track ${changedFiles[0]}` : "Attach screenshot or tool output as proof.",
      feedback: "Structured evidence",
      evidence: "file/tool output",
    },
  ];
  const targetOptions = Object.values(targetMap);
  const agentFeedback = {
    target,
    targetOptions,
    selectedTargetKind: target.kind,
    panes: panes.map(pane => ({ id: pane.id, label: pane.label, status: pane.status })),
    annotations: annotations.map(annotation => ({
      pin: annotation.pin,
      target: annotation.target,
      pane: annotation.pane,
      region: annotation.region,
      selector: annotation.selector,
      comment: annotation.comment,
      feedback: annotation.feedback,
      evidence: annotation.evidence,
    })),
    runtimeStatus,
    evidence,
    evidenceCounts: {
      screenshots: evidence.screenshots.length,
      timelapse: evidence.timelapse.length,
      files: evidence.files.length,
      tools: evidence.tools.length,
      activity: evidence.activity.length,
    },
    replayWindow: activity.slice(-4),
    replaySummary: firstTextValue(
      [snapshot.replaySummary, latestMission.summary, snapshot.status],
      "Live replay follows the current runtime state.",
    ),
  };

  return {
    target,
    targetOptions,
    panes,
    annotations,
    agentFeedback,
    runtimeStatus,
    evidence,
    activity,
    replayWindow: activity.slice(-4),
    replaySummary: firstTextValue(
      [snapshot.replaySummary, latestMission.summary, snapshot.status],
      "Live replay follows the current runtime state.",
    ),
  };
}

function modeText(value: unknown): string {
  return textValue(value, "linked");
}
