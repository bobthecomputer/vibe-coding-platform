import { useCallback, useMemo, useReducer } from "react";

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
  describeVoiceCommandResult,
  parseVoiceCommand,
} from "./voiceCommandGrammar.js";
import {
  buildVoiceErrorRecovery,
  detectVoiceInputSupport,
  getVoiceStatusCopy,
} from "./voiceAccessibility.js";

function createInitialState(options = {}) {
  const support = detectVoiceInputSupport(options.runtime || globalThis);
  const transcriptState = createVoiceTranscriptState(options.transcript || {});
  const transcript = buildTranscriptSnapshot(transcriptState);
  return {
    support,
    transcriptState,
    transcript,
    listening: false,
    error: "",
    sendGuard: {
      status: "idle",
      reason: "no_command",
      label: "No command",
      detail: "Dictate or type a command before running it.",
    },
    pendingCommand: null,
    lastCommand: null,
    status: getVoiceStatusCopy({ support, transcript }),
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
    return {
      ...state,
      listening: Boolean(action.listening),
      error: "",
      status: getVoiceStatusCopy({ ...state, listening: Boolean(action.listening), error: "" }),
    };
  }
  if (action.type === "transcript.append") {
    const transcriptState = appendTranscriptSegment(state.transcriptState, action.segment);
    const transcript = buildTranscriptSnapshot(transcriptState);
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
    const transcript = buildTranscriptSnapshot(transcriptState);
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
    const transcript = buildTranscriptSnapshot(transcriptState);
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
    const transcript = buildTranscriptSnapshot(transcriptState);
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
  if (action.type === "command.pending") {
    return {
      ...state,
      pendingCommand: action.command,
      sendGuard: action.guard || state.sendGuard,
      lastCommand: action.command,
      status: describeVoiceCommandResult(action.command),
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
} = {}) {
  const [state, dispatch] = useReducer(reducer, null, () => createInitialState({ runtime }));

  const refreshSupport = useCallback(() => {
    dispatch({ type: "support", support: detectVoiceInputSupport(runtime || globalThis) });
  }, [runtime]);

  const startListening = useCallback(async () => {
    refreshSupport();
    if (!state.support.supported && !speechAdapter?.start) {
      dispatch({ type: "error", code: "unsupported" });
      return false;
    }
    try {
      if (speechAdapter?.start) {
        await speechAdapter.start();
      }
      dispatch({ type: "listening", listening: true });
      return true;
    } catch (caught) {
      dispatch({
        type: "error",
        message: caught instanceof Error ? caught.message : String(caught || "Could not start dictation."),
      });
      return false;
    }
  }, [refreshSupport, speechAdapter, state.support.supported]);

  const stopListening = useCallback(async () => {
    try {
      if (speechAdapter?.stop) {
        await speechAdapter.stop();
      }
      dispatch({ type: "listening", listening: false });
      return true;
    } catch (caught) {
      dispatch({
        type: "error",
        message: caught instanceof Error ? caught.message : String(caught || "Could not stop dictation."),
      });
      return false;
    }
  }, [speechAdapter]);

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

  const runTranscriptCommand = useCallback(
    async (text = state.transcript.combinedText, confidence = state.transcript.averageConfidence ?? 1) => {
      const command = parseVoiceCommand(text, { confidence, minConfidence });
      if (!command.matched) {
        dispatch({ type: "error", message: command.recovery });
        return command;
      }
      const guard = buildAccidentalSendGuard({ command, transcript: state.transcript });
      if (guard.status === "review_required" || guard.status === "blocked") {
        const blockedCommand = {
          ...command,
          matched: false,
          blockedReason: guard.reason,
          recovery: guard.detail,
          guard,
        };
        dispatch({ type: "command.guardBlocked", command: blockedCommand, guard });
        return blockedCommand;
      }
      if (command.requiresConfirmation) {
        dispatch({ type: "command.pending", command: { ...command, guard }, guard });
        return command;
      }
      await onVoiceCommand?.(command);
      dispatch({ type: "command.complete", command, guard });
      return command;
    },
    [minConfidence, onVoiceCommand, state.transcript.averageConfidence, state.transcript.combinedText],
  );

  const confirmPendingCommand = useCallback(async () => {
    if (!state.pendingCommand) {
      return null;
    }
    await onVoiceCommand?.(state.pendingCommand);
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
      refreshSupport,
      startListening,
      stopListening,
      appendTranscript,
      correctTranscriptSegment,
      finalizeTranscript,
      clearTranscript,
      runTranscriptCommand,
      confirmPendingCommand,
    }),
    [
      appendTranscript,
      clearTranscript,
      confirmPendingCommand,
      correctTranscriptSegment,
      finalizeTranscript,
      refreshSupport,
      runTranscriptCommand,
      startListening,
      state,
      stopListening,
    ],
  );
}
