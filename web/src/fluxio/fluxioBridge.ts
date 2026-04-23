import { invoke } from "@tauri-apps/api/core";

type JsonRecord = Record<string, unknown>;

const COMMANDS: Record<string, string> = {
  "mission.start": "start_control_room_mission_command",
  "mission.action": "apply_control_room_mission_action_command",
  "approval.resolve": "resolve_action_approval",
  "workspace.action": "apply_control_room_workspace_action_command",
};

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
    const snapshot = await invoke("get_control_room_snapshot_command", {
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
  const result = await invoke(tauriCommand, { payload });
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

export function replayEvents(snapshot: JsonRecord): JsonRecord[] {
  const timeline = asList(snapshot.activity);
  return timeline.map(item => ({
    kind: item.kind || "activity",
    message: item.message || "",
    timestamp: item.timestamp || "",
  }));
}
