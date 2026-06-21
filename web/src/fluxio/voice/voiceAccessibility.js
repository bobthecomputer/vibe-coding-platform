export function detectVoiceInputSupport(runtime = globalThis) {
  const root = runtime?.window || runtime || {};
  const bridge = root.__FLUXIO_VOICE_BRIDGE__ || runtime?.__FLUXIO_VOICE_BRIDGE__;
  const hasBridge =
    bridge &&
    (typeof bridge.startDictation === "function" ||
      typeof bridge.start === "function" ||
      typeof bridge.record === "function");
  if (hasBridge) {
    return {
      supported: true,
      mode: "bridge",
      canStartLiveCapture: true,
      requiresPermission: true,
      label: "Voice bridge detected",
      status: "Voice input can use the local bridge after microphone permission is granted.",
    };
  }

  const SpeechRecognition = root.SpeechRecognition || root.webkitSpeechRecognition;
  if (typeof SpeechRecognition === "function") {
    return {
      supported: true,
      mode: "browser-speech-api",
      canStartLiveCapture: true,
      requiresPermission: true,
      label: "Browser speech recognition detected",
      status: "Voice input can use browser speech recognition after microphone permission is granted.",
    };
  }

  return {
    supported: false,
    mode: "none",
    canStartLiveCapture: false,
    requiresPermission: false,
    label: "Voice input unavailable",
    status:
      "Live dictation is not available in this browser yet. Use OS dictation, paste text, or connect the local voice bridge.",
  };
}

export function describeVoiceCaptureStatus({ support = detectVoiceInputSupport({}), speechAdapter = null } = {}) {
  const adapterName =
    speechAdapter?.label ||
    speechAdapter?.name ||
    (speechAdapter?.source ? String(speechAdapter.source) : "") ||
    "";
  const hasStart = typeof speechAdapter?.start === "function";
  const hasStop = typeof speechAdapter?.stop === "function";
  const hasAdapter = hasStart || hasStop;

  if (hasStart) {
    return {
      adapterAvailable: true,
      canStartLiveCapture: true,
      mode: support.mode || "adapter",
      source: adapterName || support.label || "Voice adapter",
      label: adapterName || "Capture adapter ready",
      status: `Live capture is wired through ${adapterName || support.label || "the voice adapter"}.`,
      recovery: "",
    };
  }

  if (hasAdapter) {
    return {
      adapterAvailable: true,
      canStartLiveCapture: false,
      mode: support.mode || "adapter",
      source: adapterName || "Partial voice adapter",
      label: "Capture adapter incomplete",
      status: "A voice adapter is present, but it does not expose a start method for live capture.",
      recovery: "Reconnect the bridge with a start method or use OS dictation and paste the result.",
    };
  }

  if (support.supported) {
    const sourceLabel = String(support.label || "Voice support").replace(/\s+detected$/i, "");
    return {
      adapterAvailable: false,
      canStartLiveCapture: false,
      mode: support.mode,
      source: support.label,
      label: "Adapter not wired",
      status: `${sourceLabel} was detected, but Fluxio has no active capture adapter wired to this panel.`,
      recovery: "Use system dictation, paste text, or connect the browser/local speech adapter before starting.",
    };
  }

  return {
    adapterAvailable: false,
    canStartLiveCapture: false,
    mode: "none",
    source: "No live capture source",
    label: "Capture unavailable",
    status: support.status,
    recovery: "Use OS dictation, paste text, or connect the local voice bridge.",
  };
}

export function buildKeyboardParityLabel({ label, shortcut = "", voice = "" }) {
  const parts = [label || "Action"];
  if (shortcut) {
    parts.push(`Keyboard: ${shortcut}`);
  }
  if (voice) {
    parts.push(`Voice: say ${voice}`);
  }
  return parts.join(". ");
}

export function getVoiceStatusCopy({
  support = detectVoiceInputSupport({}),
  capture = null,
  listening = false,
  transcript = null,
  pendingCommand = null,
  error = "",
} = {}) {
  if (error) {
    return `Voice input needs attention. ${error}`;
  }
  if (!support.supported) {
    return support.status;
  }
  if (capture && !capture.canStartLiveCapture) {
    return capture.status;
  }
  if (pendingCommand?.requiresConfirmation) {
    return pendingCommand.confirmationPrompt || "Voice command needs confirmation before it runs.";
  }
  if (listening) {
    return "Listening. Speak naturally, then review the transcript before sending.";
  }
  if (transcript?.warnings?.length) {
    return transcript.warnings[0];
  }
  if (transcript?.combinedText) {
    return "Dictation is ready for review.";
  }
  return support.status;
}

export function prefersReducedMotion(runtime = globalThis) {
  const root = runtime?.window || runtime || {};
  if (typeof root.matchMedia !== "function") {
    return false;
  }
  return Boolean(root.matchMedia("(prefers-reduced-motion: reduce)")?.matches);
}

export function getVoiceMotionAffordance(reducedMotion = prefersReducedMotion()) {
  if (reducedMotion) {
    return {
      "data-motion": "reduced",
      "aria-live": "polite",
      description: "Status changes use text and steady color instead of pulsing motion.",
    };
  }
  return {
    "data-motion": "available",
    "aria-live": "polite",
    description: "Status changes may use short opacity transitions and no continuous animation.",
  };
}

export function buildVoiceErrorRecovery(errorCode, detail = "") {
  const detailText = detail ? ` ${detail}` : "";
  const copy = {
    unsupported:
      "This browser cannot start live dictation. Use OS dictation, type the phrase, or connect the local bridge.",
    permission_denied:
      "Microphone permission was denied. Enable microphone access or use keyboard input.",
    low_confidence:
      "That sounded unclear. Repeat the command, type it, or choose the matching keyboard action.",
    unknown_command:
      "That did not match a Fluxio command. Say show commands to see examples.",
    bridge_offline:
      "The local voice bridge is offline. Start the bridge or continue with OS dictation.",
    adapter_unwired:
      "Voice support was detected, but no start-capable capture adapter is wired to this panel.",
  };
  return `${copy[errorCode] || "Voice input could not complete the action."}${detailText}`;
}
