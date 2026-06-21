function voiceRuntimeRoot(runtime = globalThis) {
  return runtime?.window || runtime || {};
}

function normalizeText(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeConfidence(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const next = Number(value);
  if (!Number.isFinite(next)) {
    return null;
  }
  return Math.max(0, Math.min(1, next));
}

function normalizeCaptureSegment(input = {}, fallback = {}) {
  const text = normalizeText(input.text ?? input.transcript ?? input.phrase ?? "");
  if (!text) {
    return null;
  }
  const alternatives = Array.from(input.alternatives || input.candidates || [])
    .map(item => ({
      text: normalizeText(item?.text ?? item?.transcript ?? item),
      confidence: normalizeConfidence(item?.confidence),
    }))
    .filter(item => item.text)
    .slice(0, 5);
  return {
    text,
    confidence: normalizeConfidence(input.confidence),
    isFinal: input.isFinal ?? input.final ?? fallback.isFinal ?? true,
    source: input.source || fallback.source || "voice-capture",
    alternatives,
    ambiguityReasons: input.ambiguityReasons || [],
    receivedAt: input.receivedAt || new Date().toISOString(),
  };
}

export function normalizeSpeechRecognitionResult(result, fallback = {}) {
  if (!result) {
    return null;
  }
  const alternatives = Array.from(result)
    .map(item => ({
      text: normalizeText(item?.transcript ?? item?.text ?? ""),
      confidence: normalizeConfidence(item?.confidence),
    }))
    .filter(item => item.text)
    .slice(0, 5);
  const primary = alternatives[0];
  return normalizeCaptureSegment(
    {
      text: primary?.text || result.transcript || "",
      confidence: primary?.confidence ?? result.confidence,
      alternatives: alternatives.slice(1),
      isFinal: Boolean(result.isFinal),
    },
    fallback,
  );
}

function emitSegment(handlers = {}, segment) {
  if (!segment) {
    return;
  }
  if (segment.isFinal) {
    handlers.onFinal?.(segment);
  } else {
    handlers.onInterim?.(segment);
  }
}

export function createBrowserSpeechAdapter(runtime = globalThis) {
  const root = voiceRuntimeRoot(runtime);
  const SpeechRecognition = root.SpeechRecognition || root.webkitSpeechRecognition;
  if (typeof SpeechRecognition !== "function") {
    return null;
  }
  let recognition = null;

  return {
    name: "browser-speech-api",
    label: "Browser speech adapter",
    source: "Browser SpeechRecognition",
    async start(handlers = {}) {
      recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.onresult = event => {
        const startIndex = Number.isInteger(event.resultIndex) ? event.resultIndex : 0;
        for (let index = startIndex; index < event.results.length; index += 1) {
          emitSegment(
            handlers,
            normalizeSpeechRecognitionResult(event.results[index], {
              source: "browser-speech-api",
            }),
          );
        }
      };
      recognition.onerror = event => {
        handlers.onError?.({
          code: event?.error === "not-allowed" ? "permission_denied" : event?.error || "browser_speech_error",
          message: event?.message || event?.error || "Browser speech recognition failed.",
        });
      };
      recognition.onend = () => {
        handlers.onStop?.({ source: "browser-speech-api" });
      };
      recognition.start();
    },
    async stop() {
      if (recognition) {
        recognition.stop();
        recognition = null;
      }
    },
  };
}

export function createBridgeSpeechAdapter(runtime = globalThis) {
  const root = voiceRuntimeRoot(runtime);
  const bridge = root.__FLUXIO_VOICE_BRIDGE__ || runtime?.__FLUXIO_VOICE_BRIDGE__;
  if (!bridge) {
    return null;
  }
  const startMethod = bridge.startDictation || bridge.start || bridge.record;
  if (typeof startMethod !== "function") {
    return null;
  }
  let unsubscribe = null;

  return {
    name: "fluxio-voice-bridge",
    label: bridge.label || "Fluxio voice bridge",
    source: "Local voice bridge",
    async start(handlers = {}) {
      const callbacks = {
        onResult: result =>
          emitSegment(
            handlers,
            normalizeCaptureSegment(result, {
              source: "fluxio-voice-bridge",
            }),
          ),
        onInterim: result =>
          handlers.onInterim?.(
            normalizeCaptureSegment(
              { ...result, isFinal: false },
              { source: "fluxio-voice-bridge" },
            ),
          ),
        onFinal: result =>
          handlers.onFinal?.(
            normalizeCaptureSegment(
              { ...result, isFinal: true },
              { source: "fluxio-voice-bridge" },
            ),
          ),
        onError: error =>
          handlers.onError?.({
            code: error?.code || "bridge_offline",
            message: error?.message || String(error || "The local voice bridge failed."),
          }),
      };
      const started = await startMethod.call(bridge, callbacks);
      if (typeof started === "function") {
        unsubscribe = started;
      } else if (typeof started?.unsubscribe === "function") {
        unsubscribe = () => started.unsubscribe();
      }
    },
    async stop() {
      if (typeof bridge.stopDictation === "function") {
        await bridge.stopDictation();
      } else if (typeof bridge.stop === "function") {
        await bridge.stop();
      }
      if (unsubscribe) {
        unsubscribe();
        unsubscribe = null;
      }
    },
  };
}

export function createVoiceCaptureAdapter(runtime = globalThis) {
  return createBridgeSpeechAdapter(runtime) || createBrowserSpeechAdapter(runtime);
}
