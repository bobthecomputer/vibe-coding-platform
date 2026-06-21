import { useCallback, useMemo, useReducer, useRef } from "react";

import {
  appendTranscriptSegment,
  buildTranscriptSnapshot,
  clearTranscriptBuffer,
  createVoiceTranscriptState,
  finalizeInterimTranscript,
  replaceTranscriptSegment,
} from "./voiceTranscriptBuffer.js";
import {
  buildAccidentalSendGuard,
  buildVoiceCommandPacket,
  buildVoiceCommandReviewTarget,
  describeVoiceCommandResult,
  parseVoiceCommand,
} from "./voiceCommandGrammar.js";
import {
  buildVoiceErrorRecovery,
  describeVoiceCaptureStatus,
  detectVoiceInputSupport,
  getVoiceStatusCopy,
} from "./voiceAccessibility.js";
import { createVoiceCaptureAdapter } from "./voiceCaptureAdapters.js";

function createInitialState(options = {}) {
  const support = detectVoiceInputSupport(options.runtime || globalThis);
  const transcriptState = createVoiceTranscriptState(options.transcript || {});
  const transcript = { ...buildTranscriptSnapshot(transcriptState), inputMode: "command" };
  return {
    support,
    transcriptState,
    transcript,
    listening: false,
    error: "",
    captureLifecycle: {
      status: "idle",
      label: "Idle",
      detail: "Capture has not started.",
      source: support.label,
    },
    sendGuard: {
      status: "idle",
      reason: "no_command",
      label: "No command",
      detail: "Dictate or type a command before running it.",
    },
    inputMode: "command",
    pendingCommand: null,
    lastCommand: null,
    status: getVoiceStatusCopy({ support, transcript }),
  };
}

export function normalizeVoiceCommandOutcome(outcome, fallbackCommand = null) {
  if (outcome && typeof outcome === "object" && typeof outcome.status === "string") {
    return outcome;
  }
  return {
    status: "complete",
    reason: "handler_complete",
    label: "Complete",
    detail: describeVoiceCommandResult(fallbackCommand),
  };
}

function reducer(state, action) {
  if (action.type === "support") {
    const support = action.support || state.support;
    return {
      ...state,
      support,
      status: getVoiceStatusCopy({ ...state, support }),
    };
  }
  if (action.type === "listening") {
    const listening = Boolean(action.listening);
    return {
      ...state,
      listening,
      error: "",
      captureLifecycle: listening
        ? {
            status: "listening",
            label: "Listening",
            detail: "Live voice capture is active.",
            source: action.source || state.captureLifecycle?.source || state.support.label,
          }
        : state.captureLifecycle,
      status: getVoiceStatusCopy({ ...state, listening, error: "" }),
    };
  }
  if (action.type === "capture.stopped") {
    const source = action.event?.source || state.captureLifecycle?.source || state.support.label;
    return {
      ...state,
      listening: false,
      error: "",
      captureLifecycle: {
        status: "stopped",
        label: "Capture stopped",
        detail: action.event?.detail || "The active voice capture session ended.",
        source,
        stoppedAt: action.event?.stoppedAt || new Date().toISOString(),
        restartCount: Number(action.event?.restartCount ?? state.captureLifecycle?.restartCount ?? 0) || 0,
        lastCaptureEvent: "stopped",
        lastCaptureErrorCode: action.event?.errorCode || state.captureLifecycle?.lastCaptureErrorCode || "",
        updatedAt: action.event?.stoppedAt || new Date().toISOString(),
      },
      status: getVoiceStatusCopy({ ...state, listening: false, error: "" }),
    };
  }
  if (action.type === "capture.lifecycle") {
    const event = action.event || {};
    const status = event.status || state.captureLifecycle?.status || "idle";
    const restartCount = Number(event.restartCount ?? state.captureLifecycle?.restartCount ?? 0) || 0;
    const lastCaptureErrorCode = event.errorCode || state.captureLifecycle?.lastCaptureErrorCode || "";
    return {
      ...state,
      listening: ["started", "reconnecting", "restarted", "listening"].includes(status)
        ? true
        : status === "stopped" || status === "blocked" || status === "ended"
          ? false
          : state.listening,
      captureLifecycle: {
        ...state.captureLifecycle,
        status,
        label:
          status === "reconnecting"
            ? "Reconnecting"
            : status === "restarted"
              ? "Capture restarted"
              : status === "blocked"
                ? "Capture blocked"
                : status === "ended"
                  ? "Capture ended"
                  : status === "started"
                    ? "Listening"
                    : state.captureLifecycle?.label || "Capture event",
        detail: event.detail || state.captureLifecycle?.detail || "Voice capture lifecycle changed.",
        source: event.source || state.captureLifecycle?.source || state.support.label,
        restartCount,
        lastCaptureEvent: status,
        lastCaptureErrorCode,
        updatedAt: event.updatedAt || new Date().toISOString(),
      },
      status: getVoiceStatusCopy({ ...state, listening: status !== "blocked", error: "" }),
    };
  }
  if (action.type === "transcript.append") {
    const transcriptState = appendTranscriptSegment(state.transcriptState, action.segment);
    const transcript = { ...buildTranscriptSnapshot(transcriptState), inputMode: state.inputMode };
    return {
      ...state,
      transcriptState,
      transcript,
      error: "",
      pendingCommand: null,
      sendGuard: {
        status: transcript.reviewRequired ? "review_required" : "idle",
        reason: transcript.reviewRequired ? "transcript_quality" : "transcript_updated",
        label: transcript.reviewRequired ? "Review first" : "Transcript updated",
        detail: transcript.reviewRequired
          ? "The transcript has quality warnings that should be resolved before guarded actions run."
          : "Transcript is ready for command parsing.",
      },
      status: getVoiceStatusCopy({ ...state, transcript, error: "" }),
    };
  }
  if (action.type === "transcript.finalize") {
    const transcriptState = finalizeInterimTranscript(state.transcriptState, action.patch);
    const transcript = { ...buildTranscriptSnapshot(transcriptState), inputMode: state.inputMode };
    return {
      ...state,
      transcriptState,
      transcript,
      pendingCommand: null,
      sendGuard: {
        status: transcript.reviewRequired ? "review_required" : "idle",
        reason: transcript.reviewRequired ? "transcript_quality" : "transcript_finalized",
        label: transcript.reviewRequired ? "Review first" : "Transcript finalized",
        detail: transcript.reviewRequired
          ? "The finalized transcript still needs review before guarded actions run."
          : "Final transcript is ready for command parsing.",
      },
      status: getVoiceStatusCopy({ ...state, transcript }),
    };
  }
  if (action.type === "transcript.correct") {
    const transcriptState = replaceTranscriptSegment(state.transcriptState, action.segmentId, action.patch);
    const transcript = { ...buildTranscriptSnapshot(transcriptState), inputMode: state.inputMode };
    return {
      ...state,
      transcriptState,
      transcript,
      pendingCommand: null,
      sendGuard: {
        status: transcript.reviewRequired ? "review_required" : "idle",
        reason: transcript.reviewRequired ? "transcript_quality" : "transcript_corrected",
        label: transcript.reviewRequired ? "Review remaining text" : "Correction saved",
        detail: transcript.reviewRequired
          ? "One correction was saved, but other transcript quality warnings remain."
          : "The transcript correction is saved and the command can be reviewed again.",
      },
      status: getVoiceStatusCopy({ ...state, transcript, pendingCommand: null }),
    };
  }
  if (action.type === "transcript.clear") {
    const transcriptState = clearTranscriptBuffer(state.transcriptState, action.reason);
    const transcript = { ...buildTranscriptSnapshot(transcriptState), inputMode: state.inputMode };
    return {
      ...state,
      transcriptState,
      transcript,
      pendingCommand: null,
      sendGuard: {
        status: "idle",
        reason: "transcript_cleared",
        label: "No command",
        detail: "The transcript was cleared.",
      },
      status: getVoiceStatusCopy({ ...state, transcript, pendingCommand: null }),
    };
  }
  if (action.type === "inputMode.set") {
    const inputMode = action.inputMode === "dictation" || action.inputMode === "correction" ? action.inputMode : "command";
    const transcript = { ...state.transcript, inputMode };
    return {
      ...state,
      inputMode,
      transcript,
      pendingCommand: null,
      sendGuard: {
        status: "idle",
        reason: "mode_changed",
        label: inputMode === "dictation" ? "Dictation mode" : inputMode === "correction" ? "Correction mode" : "Command mode",
        detail:
          inputMode === "dictation"
            ? "Command-like phrases will be held for review until command mode is restored."
            : inputMode === "correction"
              ? "Use this mode to repair dictated text before running a command."
              : "Reviewed text can be parsed as a command.",
      },
      status:
        inputMode === "dictation"
          ? "Dictation mode is active. Command-like phrases will be reviewed before running."
          : inputMode === "correction"
            ? "Correction mode is active. Repair the transcript before running commands."
            : "Command mode is active. Reviewed transcript can be parsed as a command.",
    };
  }
  if (action.type === "command.pending") {
    return {
      ...state,
      pendingCommand: action.command,
      sendGuard: action.guard || state.sendGuard,
      lastCommand: action.command,
      status: describeVoiceCommandResult(action.command),
    };
  }
  if (action.type === "command.cancelPending") {
    return {
      ...state,
      pendingCommand: null,
      sendGuard: {
        status: "idle",
        reason: "operator_cancelled",
        label: "Canceled",
        detail: "The pending voice command was canceled before it reached the shell.",
      },
      status: "Pending voice command canceled.",
    };
  }
  if (action.type === "command.guardBlocked") {
    return {
      ...state,
      pendingCommand: null,
      sendGuard: action.guard,
      lastCommand: action.command || state.lastCommand,
      status: action.guard?.detail || describeVoiceCommandResult(action.command),
    };
  }
  if (action.type === "command.complete") {
    return {
      ...state,
      pendingCommand: null,
      sendGuard: action.guard || {
        status: "ready",
        reason: "command_complete",
        label: "Complete",
        detail: describeVoiceCommandResult(action.command || state.pendingCommand || state.lastCommand),
      },
      lastCommand: action.command || state.pendingCommand || state.lastCommand,
      status: describeVoiceCommandResult(action.command || state.pendingCommand || state.lastCommand),
    };
  }
  if (action.type === "command.handlerBlocked") {
    const outcome = normalizeVoiceCommandOutcome(action.outcome, action.command || state.pendingCommand || state.lastCommand);
    return {
      ...state,
      pendingCommand: null,
      sendGuard: {
        status: outcome.status === "canceled" ? "blocked" : outcome.status || "blocked",
        reason: outcome.reason || "handler_blocked",
        label: outcome.label || (outcome.status === "canceled" ? "Canceled" : "Blocked"),
        detail: outcome.detail || "The shell handler did not run this voice command.",
      },
      lastCommand: {
        ...(action.command || state.pendingCommand || state.lastCommand || {}),
        handlerOutcome: outcome,
      },
      status: outcome.detail || "Voice command did not run.",
    };
  }
  if (action.type === "error") {
    const error = action.message || buildVoiceErrorRecovery(action.code || "unknown");
    return {
      ...state,
      error,
      listening: false,
      sendGuard: {
        status: "blocked",
        reason: action.code || "error",
        label: "Blocked",
        detail: error,
      },
      status: getVoiceStatusCopy({ ...state, error, listening: false }),
    };
  }
  return state;
}

export function useVoiceInteractionController({
  runtime,
  speechAdapter,
  minConfidence,
  onVoiceCommand,
  getCommandReviewContext,
} = {}) {
  const [state, dispatch] = useReducer(reducer, null, () => createInitialState({ runtime }));
  const activeAdapterRef = useRef(null);
  const resolvedSpeechAdapter = useMemo(
    () => speechAdapter || createVoiceCaptureAdapter(runtime || globalThis),
    [runtime, speechAdapter],
  );
  const capture = useMemo(
    () => describeVoiceCaptureStatus({ support: state.support, speechAdapter: resolvedSpeechAdapter }),
    [resolvedSpeechAdapter, state.support],
  );

  const refreshSupport = useCallback(() => {
    dispatch({ type: "support", support: detectVoiceInputSupport(runtime || globalThis) });
  }, [runtime]);

  const startListening = useCallback(async () => {
    refreshSupport();
    const refreshedSupport = detectVoiceInputSupport(runtime || globalThis);
    const activeAdapter = speechAdapter || resolvedSpeechAdapter || createVoiceCaptureAdapter(runtime || globalThis);
    activeAdapterRef.current = activeAdapter;
    const refreshedCapture = describeVoiceCaptureStatus({ support: refreshedSupport, speechAdapter: activeAdapter });
    if (!refreshedCapture.canStartLiveCapture) {
      dispatch({
        type: "error",
        code: refreshedSupport.supported ? "adapter_unwired" : "unsupported",
        message: refreshedCapture.recovery || refreshedCapture.status,
      });
      return false;
    }
    try {
      dispatch({ type: "listening", listening: true, source: activeAdapter.source || activeAdapter.name });
      await activeAdapter.start({
        onInterim: segment => dispatch({ type: "transcript.append", segment: { ...segment, isFinal: false } }),
        onFinal: segment => dispatch({ type: "transcript.append", segment: { ...segment, isFinal: true } }),
        onStop: event =>
          dispatch({
            type: "capture.stopped",
            event: {
              source: event?.source || activeAdapter.source || activeAdapter.name,
              detail: event?.detail || "The speech adapter reported that capture ended.",
              restartCount: event?.restartCount,
              errorCode: event?.errorCode,
            },
          }),
        onLifecycle: event =>
          dispatch({
            type: "capture.lifecycle",
            event,
          }),
        onError: error =>
          dispatch({
            type: "error",
            code: error?.code || "capture_error",
            message: error?.message || buildVoiceErrorRecovery(error?.code || "unknown"),
          }),
      });
      return true;
    } catch (caught) {
      dispatch({
        type: "error",
        message: caught instanceof Error ? caught.message : String(caught || "Could not start dictation."),
      });
      return false;
    }
  }, [refreshSupport, resolvedSpeechAdapter, runtime, speechAdapter]);

  const stopListening = useCallback(async () => {
    try {
      const activeAdapter = speechAdapter || activeAdapterRef.current || resolvedSpeechAdapter;
      if (activeAdapter?.stop) {
        await activeAdapter.stop();
      }
      activeAdapterRef.current = null;
      dispatch({
        type: "capture.stopped",
        event: {
          source: activeAdapter?.source || activeAdapter?.name || "voice-capture",
          detail: "Capture was stopped by the operator.",
        },
      });
      return true;
    } catch (caught) {
      dispatch({
        type: "error",
        message: caught instanceof Error ? caught.message : String(caught || "Could not stop dictation."),
      });
      return false;
    }
  }, [resolvedSpeechAdapter, speechAdapter]);

  const appendTranscript = useCallback(segment => {
    dispatch({ type: "transcript.append", segment });
  }, []);

  const finalizeTranscript = useCallback(patch => {
    dispatch({ type: "transcript.finalize", patch });
  }, []);

  const correctTranscriptSegment = useCallback((segmentId, patch = {}) => {
    dispatch({ type: "transcript.correct", segmentId, patch });
  }, []);

  const clearTranscript = useCallback((reason = "manual_clear") => {
    dispatch({ type: "transcript.clear", reason });
  }, []);

  const setInputMode = useCallback(inputMode => {
    dispatch({ type: "inputMode.set", inputMode });
  }, []);

  const runTranscriptCommand = useCallback(
    async (text = state.transcript.combinedText, confidence = state.transcript.averageConfidence ?? 1) => {
      const command = parseVoiceCommand(text, { confidence, minConfidence });
      if (!command.matched) {
        const guard = buildAccidentalSendGuard({ command, transcript: state.transcript, activeMode: state.inputMode });
        const blockedCommand = {
          ...command,
          guard,
          voicePacket: buildVoiceCommandPacket({ command, guard, transcript: state.transcript }),
        };
        dispatch({ type: "command.guardBlocked", command: blockedCommand, guard });
        return blockedCommand;
      }
      const guard = buildAccidentalSendGuard({ command, transcript: state.transcript, activeMode: state.inputMode });
      const reviewContext =
        typeof getCommandReviewContext === "function" ? getCommandReviewContext(command) || {} : {};
      const reviewTarget = command.requiresConfirmation
        ? buildVoiceCommandReviewTarget({ command, context: reviewContext })
        : null;
      const voicePacket = buildVoiceCommandPacket({ command, guard, transcript: state.transcript, reviewTarget });
      if (guard.status === "review_required" || guard.status === "blocked") {
        const blockedCommand = {
          ...command,
          matched: false,
          blockedReason: guard.reason,
          recovery: guard.detail,
          guard,
          voicePacket,
        };
        dispatch({ type: "command.guardBlocked", command: blockedCommand, guard });
        return blockedCommand;
      }
      const commandWithPacket = {
        ...command,
        guard,
        reviewTarget,
        voicePacket,
      };
      if (command.requiresConfirmation) {
        dispatch({ type: "command.pending", command: commandWithPacket, guard });
        return commandWithPacket;
      }
      if (command.action === "voice.stop") {
        await stopListening();
      }
      const outcome = normalizeVoiceCommandOutcome(await onVoiceCommand?.(commandWithPacket), commandWithPacket);
      if (outcome.status === "blocked" || outcome.status === "canceled") {
        dispatch({ type: "command.handlerBlocked", command: commandWithPacket, outcome });
        return {
          ...commandWithPacket,
          matched: false,
          blockedReason: outcome.reason,
          recovery: outcome.detail,
          handlerOutcome: outcome,
        };
      }
      dispatch({ type: "command.complete", command: commandWithPacket, guard });
      return { ...commandWithPacket, handlerOutcome: outcome };
    },
    [getCommandReviewContext, minConfidence, onVoiceCommand, state.inputMode, state.transcript, stopListening],
  );

  const cancelPendingCommand = useCallback(() => {
    dispatch({ type: "command.cancelPending" });
    return true;
  }, []);

  const confirmPendingCommand = useCallback(async () => {
    if (!state.pendingCommand) {
      return null;
    }
    if (state.pendingCommand.reviewTarget?.blocked) {
      dispatch({
        type: "command.guardBlocked",
        command: state.pendingCommand,
        guard: {
          status: "blocked",
          reason: state.pendingCommand.reviewTarget.blockedReason || "review_target_blocked",
          label: "Cannot confirm",
          detail: state.pendingCommand.reviewTarget.detail || "Review the target before confirming this voice command.",
        },
      });
      return null;
    }
    if (state.pendingCommand.action === "voice.clearTranscript") {
      const outcome = normalizeVoiceCommandOutcome(await onVoiceCommand?.(state.pendingCommand), state.pendingCommand);
      if (outcome.status === "blocked" || outcome.status === "canceled") {
        dispatch({ type: "command.handlerBlocked", command: state.pendingCommand, outcome });
        return null;
      }
      dispatch({ type: "transcript.clear", reason: "voice_command" });
      return state.pendingCommand;
    }
    const outcome = normalizeVoiceCommandOutcome(await onVoiceCommand?.(state.pendingCommand), state.pendingCommand);
    if (outcome.status === "blocked" || outcome.status === "canceled") {
      dispatch({ type: "command.handlerBlocked", command: state.pendingCommand, outcome });
      return null;
    }
    dispatch({
      type: "command.complete",
      command: state.pendingCommand,
      guard: {
        status: "ready",
        reason: "confirmed",
        label: "Confirmed",
        detail: "The guarded voice command was confirmed and sent to the existing handler.",
      },
    });
    return state.pendingCommand;
  }, [onVoiceCommand, state.pendingCommand]);

  return useMemo(
    () => ({
      ...state,
      capture,
      status: getVoiceStatusCopy({ ...state, capture }),
      refreshSupport,
      startListening,
      stopListening,
      appendTranscript,
      correctTranscriptSegment,
      finalizeTranscript,
      clearTranscript,
      setInputMode,
      runTranscriptCommand,
      cancelPendingCommand,
      confirmPendingCommand,
    }),
    [
      appendTranscript,
      cancelPendingCommand,
      clearTranscript,
      confirmPendingCommand,
      correctTranscriptSegment,
      capture,
      finalizeTranscript,
      refreshSupport,
      runTranscriptCommand,
      setInputMode,
      startListening,
      state,
      stopListening,
    ],
  );
}
