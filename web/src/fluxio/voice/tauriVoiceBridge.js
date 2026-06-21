import { invoke as tauriInvoke } from "@tauri-apps/api/core";

const BRIDGE_MARKER = "__FLUXIO_TAURI_VOICE_BRIDGE_INSTALLED__";

function runtimeWindow(runtime = globalThis) {
  return runtime?.window || runtime;
}

function hasTauriRuntime(root) {
  return Boolean(root?.__TAURI__ || root?.__TAURI_INTERNALS__);
}

function mediaRecorderType(root) {
  const Recorder = root?.MediaRecorder;
  if (!Recorder) {
    return "";
  }
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/ogg",
    "audio/mp4",
  ];
  return candidates.find(type => Recorder.isTypeSupported?.(type)) || "";
}

function blobToDataUrl(blob, FileReaderCtor = FileReader) {
  return new Promise((resolve, reject) => {
    const reader = new FileReaderCtor();
    reader.onerror = () => reject(reader.error || new Error("Could not read recorded dictation audio."));
    reader.onloadend = () => resolve(String(reader.result || ""));
    reader.readAsDataURL(blob);
  });
}

export function installTauriVoiceBridge(runtime = globalThis, options = {}) {
  const root = runtimeWindow(runtime);
  if (!root || root[BRIDGE_MARKER] || !hasTauriRuntime(root)) {
    return root?.__FLUXIO_VOICE_BRIDGE__ || null;
  }
  const navigatorRef = options.navigator || root.navigator;
  const MediaRecorderCtor = options.MediaRecorder || root.MediaRecorder;
  const FileReaderCtor = options.FileReader || root.FileReader;
  const invoke = options.invoke || tauriInvoke;
  if (!navigatorRef?.mediaDevices?.getUserMedia || !MediaRecorderCtor || !FileReaderCtor) {
    return root.__FLUXIO_VOICE_BRIDGE__ || null;
  }

  let active = null;
  const bridge = {
    label: "Tauri local dictation",
    source: "tauri-local-dictation",
    async startDictation(callbacks = {}) {
      if (active) {
        callbacks.onLifecycle?.({
          status: "blocked",
          detail: "A Tauri dictation recording is already active.",
          source: "tauri-local-dictation",
        });
        return () => bridge.stopDictation();
      }
      callbacks.onLifecycle?.({
        status: "starting",
        detail: "Requesting microphone access for local dictation.",
        source: "tauri-local-dictation",
      });
      const stream = await navigatorRef.mediaDevices.getUserMedia({ audio: true });
      let session = null;
      try {
        const mimeType = options.mimeType || mediaRecorderType(root) || undefined;
        const recorder = mimeType
          ? new MediaRecorderCtor(stream, { mimeType })
          : new MediaRecorderCtor(stream);
        const chunks = [];
        recorder.ondataavailable = event => {
          if (event.data?.size > 0) {
            chunks.push(event.data);
          }
        };
        session = await invoke("start_dictation");
        active = {
          callbacks,
          chunks,
          mimeType: recorder.mimeType || mimeType || "audio/webm",
          recorder,
          sessionId: session?.sessionId || "",
          stream,
        };
        recorder.start();
      } catch (error) {
        stream.getTracks().forEach(track => track.stop());
        throw error;
      }
      callbacks.onLifecycle?.({
        status: "started",
        detail: "Recording real microphone audio for local STT.",
        source: "tauri-local-dictation",
      });
      return () => bridge.stopDictation();
    },
    async stopDictation() {
      const current = active;
      if (!current) {
        return null;
      }
      active = null;
      current.callbacks.onLifecycle?.({
        status: "stopping",
        detail: "Stopping Tauri microphone recording.",
        source: "tauri-local-dictation",
      });
      const stopped = new Promise(resolve => {
        current.recorder.onstop = resolve;
      });
      if (current.recorder.state !== "inactive") {
        current.recorder.stop();
        await stopped;
      }
      current.stream.getTracks().forEach(track => track.stop());
      try {
        const blob = new Blob(current.chunks, { type: current.mimeType });
        if (blob.size <= 0) {
          throw new Error("No dictation audio was captured.");
        }
        current.callbacks.onLifecycle?.({
          status: "saving",
          detail: "Saving recorded audio before local transcription.",
          source: "tauri-local-dictation",
        });
        const audioBase64 = await blobToDataUrl(blob, FileReaderCtor);
        const saved = await invoke("save_dictation_audio_blob", {
          payload: {
            sessionId: current.sessionId,
            audioBase64,
            mimeType: blob.type || current.mimeType,
          },
        });
        current.callbacks.onLifecycle?.({
          status: "transcribing",
          detail: "Passing recorded audio to the configured local STT command.",
          source: "tauri-local-dictation",
        });
        const session = await invoke("stop_dictation", {
          payload: { audioPath: saved?.audioPath || "" },
        });
        if (session?.status === "transcribed" && session?.transcript) {
          current.callbacks.onFinal?.({
            text: session.transcript,
            confidence: null,
            isFinal: true,
            source: "tauri-local-stt",
          });
        } else {
          current.callbacks.onError?.({
            code: "local_stt_fallback",
            message: session?.message || "Local dictation needs OS fallback.",
          });
        }
        current.callbacks.onStop?.({
          source: "tauri-local-dictation",
          detail: session?.message || "Tauri local dictation session ended.",
          stoppedAt: new Date().toISOString(),
        });
        return session;
      } catch (error) {
        const session = await invoke("stop_dictation", { payload: { audioPath: "" } }).catch(() => null);
        current.callbacks.onError?.({
          code: "tauri_recording_failed",
          message:
            error?.message ||
            session?.message ||
            "Tauri local dictation recording could not be transcribed.",
        });
        current.callbacks.onStop?.({
          source: "tauri-local-dictation",
          detail: session?.message || "Tauri local dictation stopped after a recording failure.",
          stoppedAt: new Date().toISOString(),
        });
        return session;
      }
    },
  };

  root.__FLUXIO_VOICE_BRIDGE__ = bridge;
  root[BRIDGE_MARKER] = true;
  return bridge;
}
