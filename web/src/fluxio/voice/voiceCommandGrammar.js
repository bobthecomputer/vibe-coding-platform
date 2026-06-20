const DEFAULT_MIN_CONFIDENCE = 0.72;

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

export { SURFACE_ALIASES };
