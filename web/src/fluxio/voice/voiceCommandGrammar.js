const DEFAULT_MIN_CONFIDENCE = 0.72;
const GUARDED_ACTIONS = new Set([
  "approval.resolve",
  "composer.send",
  "mission.pause",
  "mission.resume",
]);
const VOICE_INPUT_MODES = new Set(["command", "dictation", "correction"]);
const COMMAND_LIKE_START = /^(?:send|submit|post|approve|deny|reject|pause|stop|resume|continue|open|show|go to|switch to|start|clear|reset|discard)\b/;

const SURFACE_ALIASES = {
  home: ["home", "start", "dashboard", "overview"],
  agent: ["agent", "agent mode", "conversation", "chat", "mission"],
  builder: ["builder", "builder mode", "review", "changes", "diff"],
  settings: ["settings", "setup", "configuration", "preferences"],
  apps: ["apps", "applications", "connected apps", "integrations"],
  skills: ["skills", "skill library", "rules", "rulesets", "rule sets"],
  images: ["images", "image studio", "image playground", "playground"],
  voice: ["voice", "voice input", "dictation", "dictation review"],
  proof: ["proof", "evidence", "receipts"],
  queue: ["queue", "decision queue", "approvals"],
  context: ["context", "memory", "notes"],
  runtime: ["runtime", "bridge", "work engines"],
  workbench: ["workbench", "workspace", "files"],
};

function normalizeCommandText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[.,!?;:]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function slotFromAliases(value, aliases) {
  const normalized = normalizeCommandText(value);
  for (const [slot, phrases] of Object.entries(aliases)) {
    if (phrases.some(phrase => normalized === phrase || normalized.includes(phrase))) {
      return slot;
    }
  }
  return "";
}

function withConfidenceGate(result, confidence, minConfidence) {
  if (!result.matched) {
    return result;
  }
  if (confidence < minConfidence) {
    return {
      ...result,
      matched: false,
      blockedReason: "low_confidence",
      recovery:
        "I may have misheard that. Please repeat it, type it, or choose the matching keyboard action.",
      candidate: {
        intent: result.intent,
        action: result.action,
        parameters: result.parameters,
      },
    };
  }
  return result;
}

function parseNavigationCommand(text) {
  const match =
    text.match(/^(?:open|show|go to|switch to|take me to|move to)\s+(.+)$/) ||
    text.match(/^(.+)\s+(?:screen|view|panel|tab)$/);
  if (!match) {
    return null;
  }
  const surface = slotFromAliases(match[1], SURFACE_ALIASES);
  if (!surface) {
    return {
      matched: false,
      blockedReason: "unknown_surface",
      recovery: `I could not match "${match[1]}" to a Fluxio screen. Try "open settings" or use the keyboard tabs.`,
    };
  }
  return {
    matched: true,
    intent: "navigate",
    action: "surface.open",
    label: `Open ${surface}`,
    parameters: { surface },
    requiresConfirmation: false,
  };
}

function parseDictationCommand(text) {
  if (/^(?:start|begin|turn on)\s+(?:dictation|voice input|voice)$/.test(text)) {
    return {
      matched: true,
      intent: "dictation.start",
      action: "voice.start",
      label: "Start dictation",
      parameters: {},
      requiresConfirmation: false,
    };
  }
  if (/^(?:stop|end|turn off)\s+(?:dictation|voice input|voice)$/.test(text)) {
    return {
      matched: true,
      intent: "dictation.stop",
      action: "voice.stop",
      label: "Stop dictation",
      parameters: {},
      requiresConfirmation: false,
    };
  }
  if (/^(?:clear|reset|discard)\s+(?:dictation|transcript|voice text)$/.test(text)) {
    return {
      matched: true,
      intent: "dictation.clear",
      action: "voice.clearTranscript",
      label: "Clear transcript",
      parameters: {},
      requiresConfirmation: true,
      confirmationPrompt: "Clear the current dictated text?",
    };
  }
  return null;
}

function parseComposerCommand(text) {
  if (/^(?:send|submit|post)\s+(?:message|reply|follow up)$/.test(text)) {
    return {
      matched: true,
      intent: "composer.send",
      action: "composer.send",
      label: "Send message",
      parameters: {},
      requiresConfirmation: true,
      confirmationPrompt: "Send the current message?",
      riskLevel: "high",
      guardKind: "accidental_send",
    };
  }
  const noteMatch = text.match(/^(?:add note|note|operator note)\s+(.+)$/);
  if (noteMatch) {
    return {
      matched: true,
      intent: "composer.note",
      action: "composer.addNote",
      label: "Add operator note",
      parameters: { text: noteMatch[1].trim() },
      requiresConfirmation: false,
    };
  }
  const commentMatch = text.match(/^(?:comment|add comment)\s+(.+)$/);
  if (commentMatch) {
    return {
      matched: true,
      intent: "composer.comment",
      action: "composer.addComment",
      label: "Add comment",
      parameters: { text: commentMatch[1].trim() },
      requiresConfirmation: false,
    };
  }
  return null;
}

function parseMissionCommand(text) {
  if (/^(?:pause|stop)\s+(?:agent|mission|run)$/.test(text)) {
    return {
      matched: true,
      intent: "mission.pause",
      action: "mission.pause",
      label: "Pause mission",
      parameters: {},
      requiresConfirmation: true,
      confirmationPrompt: "Pause the active mission?",
      riskLevel: "medium",
      guardKind: "mission_control",
    };
  }
  if (/^(?:resume|continue)\s+(?:agent|mission|run)$/.test(text)) {
    return {
      matched: true,
      intent: "mission.resume",
      action: "mission.resume",
      label: "Resume mission",
      parameters: {},
      requiresConfirmation: true,
      confirmationPrompt: "Resume the active mission?",
      riskLevel: "medium",
      guardKind: "mission_control",
    };
  }
  if (/^(?:approve)\s+(?:request|approval|action|command)$/.test(text)) {
    return {
      matched: true,
      intent: "approval.approve",
      action: "approval.resolve",
      label: "Approve request",
      parameters: { decision: "approved" },
      requiresConfirmation: true,
      confirmationPrompt: "Approve the currently selected request?",
      riskLevel: "high",
      guardKind: "approval",
    };
  }
  if (/^(?:deny|reject)\s+(?:request|approval|action|command)$/.test(text)) {
    return {
      matched: true,
      intent: "approval.deny",
      action: "approval.resolve",
      label: "Deny request",
      parameters: { decision: "denied" },
      requiresConfirmation: true,
      confirmationPrompt: "Deny the currently selected request?",
      riskLevel: "high",
      guardKind: "approval",
    };
  }
  return null;
}

function parseUtilityCommand(text) {
  if (/^(?:show|open)\s+(?:commands|voice commands|help)$/.test(text) || text === "help") {
    return {
      matched: true,
      intent: "help.commands",
      action: "voice.showCommands",
      label: "Show voice commands",
      parameters: {},
      requiresConfirmation: false,
    };
  }
  const searchMatch = text.match(/^(?:search|find|look for)\s+(.+)$/);
  if (searchMatch) {
    return {
      matched: true,
      intent: "search.query",
      action: "search.query",
      label: "Search",
      parameters: { query: searchMatch[1].trim() },
      requiresConfirmation: false,
    };
  }
  return null;
}

const PARSERS = [
  parseDictationCommand,
  parseNavigationCommand,
  parseComposerCommand,
  parseMissionCommand,
  parseUtilityCommand,
];

export function parseVoiceCommand(input, options = {}) {
  const text = normalizeCommandText(input);
  const confidence = Number.isFinite(Number(options.confidence)) ? Number(options.confidence) : 1;
  const minConfidence = Number.isFinite(Number(options.minConfidence))
    ? Number(options.minConfidence)
    : DEFAULT_MIN_CONFIDENCE;

  if (!text) {
    return {
      matched: false,
      blockedReason: "empty",
      recovery: "No voice text is ready yet. Dictate a phrase or use the keyboard command.",
    };
  }

  for (const parser of PARSERS) {
    const result = parser(text);
    if (result) {
      return withConfidenceGate(
        {
          sourceText: input,
          normalizedText: text,
          confidence,
          ...result,
        },
        confidence,
        minConfidence,
      );
    }
  }

  return {
    matched: false,
    sourceText: input,
    normalizedText: text,
    confidence,
    blockedReason: "unknown_command",
    recovery:
      "I did not find a matching voice command. Try a phrase like open settings, show commands, or send message.",
  };
}

export function getVoiceCommandExamples() {
  return [
    "Open settings",
    "Switch to agent",
    "Show proof",
    "Start dictation",
    "Stop dictation",
    "Send message",
    "Add note follow up after tests pass",
    "Approve request",
    "Show commands",
  ];
}

export function describeVoiceCommandResult(result) {
  if (!result?.matched) {
    return result?.recovery || "Voice command was not understood.";
  }
  if (result.requiresConfirmation) {
    return result.confirmationPrompt || `${result.label || "Voice command"} needs confirmation.`;
  }
  return `${result.label || "Voice command"} is ready.`;
}

export function getVoiceCommandRisk(command = {}) {
  const action = command?.action || "";
  const guarded = GUARDED_ACTIONS.has(action) || Boolean(command?.requiresConfirmation);
  return {
    guarded,
    riskLevel: command?.riskLevel || (guarded ? "medium" : "low"),
    guardKind: command?.guardKind || (guarded ? "confirmation" : "none"),
  };
}

export function normalizeVoiceInputMode(mode = "command") {
  const normalized = String(mode || "command").toLowerCase();
  return VOICE_INPUT_MODES.has(normalized) ? normalized : "command";
}

export function buildVoiceModeCheckpoint({ text = "", transcript = {}, activeMode = "command", command = null } = {}) {
  const normalizedMode = normalizeVoiceInputMode(activeMode);
  const sourceText = text || transcript?.combinedText || transcript?.finalText || "";
  const normalizedText = normalizeCommandText(sourceText);
  const parsedCommand = command || parseVoiceCommand(sourceText, { confidence: transcript?.averageConfidence ?? 1 });
  const commandLike = Boolean(parsedCommand?.matched) || COMMAND_LIKE_START.test(normalizedText);
  const guardedIntent = Boolean(parsedCommand?.requiresConfirmation) || getVoiceCommandRisk(parsedCommand).guarded;
  const dictationConflict = normalizedMode === "dictation" && commandLike;
  const correctionConflict = normalizedMode === "correction" && guardedIntent;
  const modeConflict = dictationConflict || correctionConflict;

  return {
    schemaVersion: "fluxio.voice-mode-checkpoint.v1",
    activeMode: normalizedMode,
    label:
      normalizedMode === "dictation"
        ? "Dictation mode"
        : normalizedMode === "correction"
          ? "Correction mode"
          : "Command mode",
    commandLike,
    guardedIntent,
    modeConflict,
    reason: modeConflict
      ? dictationConflict
        ? "dictation_contains_command"
        : "correction_contains_guarded_intent"
      : commandLike
        ? "command_intent_detected"
        : normalizedText
          ? "freeform_dictation"
          : "empty_transcript",
    route:
      modeConflict
        ? "hold_for_mode_review"
        : commandLike && normalizedMode === "command"
          ? "parse_as_command"
          : "keep_as_dictation",
    detail: modeConflict
      ? "The dictated text looks like a command in a non-command mode. Review or switch mode before it can run."
      : commandLike
        ? "The text looks command-like and will use the command parser when the transcript gate is clear."
        : "The text is treated as dictation until the operator switches to command mode.",
  };
}

export function buildAccidentalSendGuard({ command, transcript, activeMode = "command" } = {}) {
  if (!command?.matched) {
    return {
      status: "blocked",
      reason: command?.blockedReason || "unmatched_command",
      label: "Command blocked",
      detail: command?.recovery || "The voice command did not match a runnable action.",
    };
  }

  const modeCheckpoint = buildVoiceModeCheckpoint({
    text: command.sourceText || transcript?.combinedText || "",
    transcript,
    activeMode,
    command,
  });
  if (modeCheckpoint.modeConflict) {
    return {
      status: "review_required",
      reason: modeCheckpoint.reason,
      label: "Check mode",
      detail: modeCheckpoint.detail,
      modeCheckpoint,
      risk: getVoiceCommandRisk(command),
    };
  }

  const risk = getVoiceCommandRisk(command);
  if (!risk.guarded) {
    return {
      status: "ready",
      reason: "low_risk_command",
      label: "Ready",
      detail: "This command does not perform a risky send, approval, or mission action.",
      modeCheckpoint,
      risk,
    };
  }

  if (transcript?.interimText || transcript?.interim?.text) {
    return {
      status: "review_required",
      reason: "interim_transcript",
      label: "Review first",
      detail: "The dictated command is still changing. Wait for final text before running it.",
      modeCheckpoint,
      risk,
    };
  }

  if (
    transcript?.reviewRequired ||
    transcript?.lowConfidenceSegments?.length > 0 ||
    transcript?.ambiguousSegments?.length > 0
  ) {
    return {
      status: "review_required",
      reason: "transcript_quality",
      label: "Review first",
      detail: "The transcript has low-confidence or ambiguous text. Correct it before this guarded action can run.",
      modeCheckpoint,
      risk,
    };
  }

  if (command.requiresConfirmation) {
    return {
      status: "confirmation_required",
      reason: "guarded_action",
      label: "Confirm",
      detail: command.confirmationPrompt || "Confirm this guarded voice command before it runs.",
      modeCheckpoint,
      risk,
    };
  }

  return {
    status: "ready",
    reason: "guard_passed",
    label: "Ready",
    detail: "The guarded command passed transcript review.",
    modeCheckpoint,
    risk,
  };
}

function compactSegment(segment = {}) {
  return {
    id: segment.id || "",
    text: segment.text || "",
    confidence: typeof segment.confidence === "number" ? segment.confidence : null,
    source: segment.source || "",
    correctedFrom: segment.correctedFrom || "",
    reviewedAt: segment.reviewedAt || "",
    reviewedBy: segment.reviewedBy || "",
    alternatives: Array.isArray(segment.alternatives)
      ? segment.alternatives.slice(0, 3).map(item => ({
          text: item.text || "",
          confidence: typeof item.confidence === "number" ? item.confidence : null,
        }))
      : [],
  };
}

export function fingerprintVoiceText(value = "") {
  const text = String(value || "");
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `${text.length}:${(hash >>> 0).toString(36)}`;
}

export function buildVoiceCommandReviewTarget({ command, context = {} } = {}) {
  const action = command?.action || "";
  const composerText = String(context.composerText || context.operatorDraft || "").trim();
  const missionTitle = String(context.missionTitle || context.missionObjective || "").trim();
  const chatTitle = String(context.chatTitle || context.chatSessionTitle || "").trim();
  const attachmentCount = Number(context.attachmentCount || 0) || 0;
  const textPreview = composerText.length > 280 ? `${composerText.slice(0, 277)}...` : composerText;

  if (action === "composer.send") {
    const destinationLabel = context.missionId
      ? "Mission follow-up"
      : context.chatConversationActive
        ? "Chat message"
        : context.idleSendMode === "chat"
          ? "Workspace chat message"
        : "Mission prompt";
    const destinationDetail = context.missionId
      ? missionTitle || `Mission ${context.missionId}`
      : chatTitle || context.workspaceName || "Current workspace";
    const blocked = !composerText;
    return {
      action,
      kind: "composer",
      label: destinationLabel,
      destination: destinationDetail,
      textPreview,
      textLength: composerText.length,
      textFingerprint: fingerprintVoiceText(composerText),
      attachmentCount,
      blocked,
      blockedReason: blocked ? "empty_composer" : "",
      confirmationLabel: blocked
        ? "Write or dictate text before confirming."
        : `Confirm send to ${destinationLabel.toLowerCase()}.`,
      detail: blocked
        ? "The composer is empty, so this voice command cannot send anything yet."
        : "Confirming will send the visible composer text through the existing shell handler.",
    };
  }

  if (action === "voice.clearTranscript") {
    return {
      action,
      kind: "voice-transcript",
      label: "Voice transcript",
      destination: "Current dictation buffer",
      textPreview: context.transcriptText || "",
      textLength: String(context.transcriptText || "").length,
      textFingerprint: fingerprintVoiceText(context.transcriptText || ""),
      attachmentCount: 0,
      blocked: false,
      blockedReason: "",
      confirmationLabel: "Confirm transcript clear.",
      detail: "Confirming clears only the reviewed voice transcript.",
    };
  }

  return {
    action,
    kind: action ? "shell-action" : "unknown",
    label: command?.label || "Voice action",
    destination: context.destination || "Fluxio shell",
    textPreview: context.previewText || "",
    textLength: String(context.previewText || "").length,
    textFingerprint: fingerprintVoiceText(context.previewText || ""),
    attachmentCount,
    blocked: false,
    blockedReason: "",
    confirmationLabel: command?.confirmationPrompt || "Confirm this voice action.",
    detail: "Confirming sends this voice command to the existing shell handler.",
  };
}

export function buildVoiceCommandPacket({ command, guard, transcript, reviewTarget = null } = {}) {
  const safeCommand = command || {};
  const safeTranscript = transcript || {};
  const safeGuard = guard || buildAccidentalSendGuard({ command: safeCommand, transcript: safeTranscript });
  const safeReviewTarget = reviewTarget || null;
  const modeCheckpoint =
    safeGuard.modeCheckpoint ||
    buildVoiceModeCheckpoint({
      text: safeCommand.sourceText || safeTranscript.combinedText || "",
      transcript: safeTranscript,
      activeMode: safeTranscript.inputMode || safeTranscript.activeMode || "command",
      command: safeCommand,
    });
  const lowConfidenceSegments = Array.isArray(safeTranscript.lowConfidenceSegments)
    ? safeTranscript.lowConfidenceSegments
    : [];
  const unknownConfidenceSegments = Array.isArray(safeTranscript.unknownConfidenceSegments)
    ? safeTranscript.unknownConfidenceSegments
    : [];
  const ambiguousSegments = Array.isArray(safeTranscript.ambiguousSegments)
    ? safeTranscript.ambiguousSegments
    : [];
  const correctionLog = Array.isArray(safeTranscript.correctionLog) ? safeTranscript.correctionLog : [];
  const repairQueue = safeTranscript.repairQueue || {};
  const blockedBy = [
    safeTranscript.interimText ? "interim_transcript" : "",
    lowConfidenceSegments.length > 0 ? "low_confidence" : "",
    unknownConfidenceSegments.length > 0 ? "unknown_confidence" : "",
    ambiguousSegments.length > 0 ? "ambiguous_transcript" : "",
    safeTranscript.reviewRequired ? "review_required" : "",
    safeGuard.status === "blocked" ? safeGuard.reason || "guard_blocked" : "",
  ].filter(Boolean);

  return {
    schemaVersion: "fluxio.voice-command-packet.v1",
    createdAt: new Date().toISOString(),
    command: {
      matched: Boolean(safeCommand.matched),
      intent: safeCommand.intent || "",
      action: safeCommand.action || "",
      label: safeCommand.label || "",
      parameters: safeCommand.parameters || {},
      sourceText: safeCommand.sourceText || "",
      normalizedText: safeCommand.normalizedText || "",
      confidence: typeof safeCommand.confidence === "number" ? safeCommand.confidence : null,
      requiresConfirmation: Boolean(safeCommand.requiresConfirmation),
      riskLevel: safeCommand.riskLevel || safeGuard.risk?.riskLevel || "low",
      guardKind: safeCommand.guardKind || safeGuard.risk?.guardKind || "none",
      blockedReason: safeCommand.blockedReason || "",
    },
    guard: {
      status: safeGuard.status || "idle",
      reason: safeGuard.reason || "",
      label: safeGuard.label || "",
      detail: safeGuard.detail || "",
      risk: safeGuard.risk || getVoiceCommandRisk(safeCommand),
      modeCheckpoint,
    },
    transcript: {
      finalText: safeTranscript.finalText || "",
      interimText: safeTranscript.interimText || "",
      combinedText: safeTranscript.combinedText || "",
      averageConfidence:
        typeof safeTranscript.averageConfidence === "number" ? safeTranscript.averageConfidence : null,
      segmentCount: Array.isArray(safeTranscript.segments) ? safeTranscript.segments.length : 0,
      lowConfidenceCount: lowConfidenceSegments.length,
      unknownConfidenceCount: unknownConfidenceSegments.length,
      ambiguousCount: ambiguousSegments.length,
      correctionCount: correctionLog.length || safeTranscript.correctionCount || 0,
      reviewRequired: Boolean(safeTranscript.reviewRequired),
      warnings: Array.isArray(safeTranscript.warnings) ? safeTranscript.warnings.slice(0, 5) : [],
      lowConfidenceSegments: lowConfidenceSegments.slice(0, 5).map(compactSegment),
      unknownConfidenceSegments: unknownConfidenceSegments.slice(0, 5).map(compactSegment),
      ambiguousSegments: ambiguousSegments.slice(0, 5).map(compactSegment),
      repairQueue: {
        status: repairQueue.status || "",
        label: repairQueue.label || "",
        nextSegmentId: repairQueue.nextSegmentId || "",
        nextSegmentText: repairQueue.nextSegmentText || "",
        nextRepairKind: repairQueue.nextRepairKind || "",
      },
      inputMode: modeCheckpoint.activeMode,
    },
    review: {
      sendable: safeCommand.matched === true && safeGuard.status === "ready",
      confirmationRequired: safeGuard.status === "confirmation_required" || Boolean(safeCommand.requiresConfirmation),
      blockedBy: Array.from(new Set([...blockedBy, modeCheckpoint.modeConflict ? modeCheckpoint.reason : ""])).filter(Boolean),
      correctionCount: correctionLog.length || safeTranscript.correctionCount || 0,
      modeCheckpoint,
      target: safeReviewTarget,
    },
  };
}

export { SURFACE_ALIASES };
