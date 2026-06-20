import React from "react";
import {
  CheckCircle,
  Keyboard,
  Microphone,
  MicrophoneSlash,
  WarningCircle,
} from "@phosphor-icons/react";

import { buildKeyboardParityLabel, getVoiceMotionAffordance } from "./voiceAccessibility.js";
import { getVoiceCommandExamples } from "./voiceCommandGrammar.js";
import { useVoiceInteractionController } from "./useVoiceInteractionController.js";
import "./voice.css";

export function VoiceCommandPanel({ controller, onVoiceCommand, reducedMotion = false }) {
  const ownedController = useVoiceInteractionController({ onVoiceCommand });
  const voice = controller || ownedController;
  const motion = getVoiceMotionAffordance(reducedMotion);
  const examples = getVoiceCommandExamples();
  const MicIcon = voice.listening ? MicrophoneSlash : Microphone;

  return (
    <section className="fluxio-voice-panel" aria-label="Voice command controls" {...motion}>
      <div className="fluxio-voice-panel-head">
        <div>
          <p className="eyebrow">Voice input</p>
          <h2>Dictation review</h2>
        </div>
        <span className="fluxio-voice-status-pill" data-supported={voice.support.supported}>
          {voice.support.label}
        </span>
      </div>

      <p className="fluxio-voice-live-status" aria-atomic="true" aria-live="polite">
        {voice.status}
      </p>

      <div className="fluxio-voice-transcript" aria-label="Current voice transcript">
        {voice.transcript.combinedText ? (
          <p>{voice.transcript.combinedText}</p>
        ) : (
          <p className="fluxio-voice-empty">
            Dictated text will appear here after browser or bridge support is available.
          </p>
        )}
        {voice.transcript.warnings.map(item => (
          <span className="fluxio-voice-warning" key={item}>
            <WarningCircle aria-hidden="true" size={16} weight="duotone" />
            {item}
          </span>
        ))}
      </div>

      <div className="fluxio-voice-actions">
        <button
          aria-label={buildKeyboardParityLabel({
            label: voice.listening ? "Stop dictation" : "Start dictation",
            shortcut: "Ctrl+Shift+V",
            voice: voice.listening ? "stop dictation" : "start dictation",
          })}
          disabled={!voice.support.supported && !voice.listening}
          onClick={() => (voice.listening ? voice.stopListening() : voice.startListening())}
          type="button"
        >
          <MicIcon aria-hidden="true" size={17} weight="duotone" />
          <span>{voice.listening ? "Stop" : "Start"}</span>
        </button>
        <button
          aria-label={buildKeyboardParityLabel({
            label: "Run voice command",
            shortcut: "Ctrl+Enter",
            voice: "send message",
          })}
          disabled={!voice.transcript.combinedText}
          onClick={() => voice.runTranscriptCommand()}
          type="button"
        >
          <CheckCircle aria-hidden="true" size={17} weight="duotone" />
          <span>Run</span>
        </button>
        <button
          aria-label={buildKeyboardParityLabel({
            label: "Clear voice transcript",
            shortcut: "Escape",
            voice: "clear transcript",
          })}
          disabled={!voice.transcript.combinedText && !voice.pendingCommand}
          onClick={() => voice.clearTranscript()}
          type="button"
        >
          Clear
        </button>
      </div>

      {voice.pendingCommand ? (
        <div className="fluxio-voice-confirm">
          <p>{voice.pendingCommand.confirmationPrompt || "Confirm this voice command before it runs."}</p>
          <button onClick={() => voice.confirmPendingCommand()} type="button">
            Confirm
          </button>
        </div>
      ) : null}

      <details className="fluxio-voice-help">
        <summary>
          <Keyboard aria-hidden="true" size={16} weight="duotone" />
          Voice command examples
        </summary>
        <ul>
          {examples.map(example => (
            <li key={example}>{example}</li>
          ))}
        </ul>
      </details>
    </section>
  );
}
