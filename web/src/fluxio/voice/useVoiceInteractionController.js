import { useCallback, useMemo, useReducer } from "react";

import {
  appendTranscriptSegment,
  buildTranscriptSnapshot,
  clearTranscriptBuffer,
  createVoiceTranscriptState,
  finalizeInterimTranscript,
} from "./voiceTranscriptBuffer.js";
import { describeVoiceCommandResult, parseVoiceCommand } from "./voiceCommandGrammar.js";
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
      status: getVoiceStatusCopy({ ...state, transcript }),
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
      status: getVoiceStatusCopy({ ...state, transcript, pendingCommand: null }),
    };
  }
  if (action.type === "command.pending") {
    return {
      ...state,
      pendingCommand: action.command,
      lastCommand: action.command,
      status: describeVoiceCommandResult(action.command),
    };
  }
  if (action.type === "command.complete") {
    return {
      ...state,
      pendingCommand: null,
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
      if (command.requiresConfirmation) {
        dispatch({ type: "command.pending", command });
        return command;
      }
      await onVoiceCommand?.(command);
      dispatch({ type: "command.complete", command });
      return command;
    },
    [minConfidence, onVoiceCommand, state.transcript.averageConfidence, state.transcript.combinedText],
  );

  const confirmPendingCommand = useCallback(async () => {
    if (!state.pendingCommand) {
      return null;
    }
    await onVoiceCommand?.(state.pendingCommand);
    dispatch({ type: "command.complete", command: state.pendingCommand });
    return state.pendingCommand;
  }, [onVoiceCommand, state.pendingCommand]);

  return useMemo(
    () => ({
      ...state,
      refreshSupport,
      startListening,
      stopListening,
      appendTranscript,
      finalizeTranscript,
      clearTranscript,
      runTranscriptCommand,
      confirmPendingCommand,
    }),
    [
      appendTranscript,
      clearTranscript,
      confirmPendingCommand,
      finalizeTranscript,
      refreshSupport,
      runTranscriptCommand,
      startListening,
      state,
      stopListening,
    ],
  );
}

