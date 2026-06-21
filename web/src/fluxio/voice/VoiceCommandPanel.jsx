import React, { useEffect, useMemo, useState } from "react";
import {
  CheckCircle,
  Info,
  Keyboard,
  Microphone,
  MicrophoneSlash,
  ShieldCheck,
  WarningCircle,
} from "@phosphor-icons/react";

import { buildKeyboardParityLabel, getVoiceMotionAffordance } from "./voiceAccessibility.js";
import { getVoiceCommandExamples } from "./voiceCommandGrammar.js";
import { useVoiceInteractionController } from "./useVoiceInteractionController.js";
import "./voice.css";

export function VoiceCommandPanel({ controller, onVoiceCommand, reducedMotion = false, speechAdapter = null }) {
  const ownedController = useVoiceInteractionController({ onVoiceCommand, speechAdapter });
  const voice = controller || ownedController;
  const motion = getVoiceMotionAffordance(reducedMotion);
  const examples = getVoiceCommandExamples();
  const MicIcon = voice.listening ? MicrophoneSlash : Microphone;
  const confidenceLabel =
    typeof voice.transcript.averageConfidence === "number"
      ? `${Math.round(voice.transcript.averageConfidence * 100)}%`
      : "No final text";
  const segmentList = voice.transcript.segments || [];
  const sendGateLabel =
    voice.sendGuard?.status === "confirmation_required"
      ? "Confirm before send"
      : voice.sendGuard?.status === "review_required" || voice.sendGuard?.status === "blocked"
        ? "Blocked until reviewed"
        : voice.pendingCommand
          ? "Waiting for confirmation"
          : "Safe to review";
  const capture = voice.capture || {
    canStartLiveCapture: Boolean(voice.support.supported),
    label: voice.support.label,
    source: voice.support.label,
    status: voice.support.status,
  };
  const captureLifecycle = voice.captureLifecycle || {
    status: voice.listening ? "listening" : "idle",
    label: voice.listening ? "Listening" : "Idle",
    detail: voice.listening ? "Live capture is active." : "Capture has not started.",
    source: capture.source || capture.label,
  };
  const startDisabled = !capture.canStartLiveCapture && !voice.listening;
  const repairQueue = voice.transcript.repairQueue || {
    status: voice.transcript.reviewRequired ? "review" : voice.transcript.combinedText ? "ready" : "empty",
    label: voice.transcript.reviewRequired ? "Repair before send" : "Ready after review",
    summary: voice.transcript.reviewRequired
      ? "Review highlighted dictation before running a command."
      : "No dictation repair is queued.",
    lowConfidenceCount: voice.transcript.lowConfidenceSegments?.length || 0,
    ambiguousCount: voice.transcript.ambiguousSegments?.length || 0,
    interimActive: Boolean(voice.transcript.interimText),
    nextSegmentText: voice.transcript.lowConfidenceSegments?.[0]?.text || voice.transcript.ambiguousSegments?.[0]?.text || "",
  };
  const reviewSegments = useMemo(() => {
    const seen = new Set();
    return [
      ...(voice.transcript.lowConfidenceSegments || []),
      ...(voice.transcript.ambiguousSegments || []),
    ].filter(segment => {
      if (!segment?.id || seen.has(segment.id)) {
        return false;
      }
      seen.add(segment.id);
      return true;
    });
  }, [voice.transcript.ambiguousSegments, voice.transcript.lowConfidenceSegments]);
  const nextRepairSegment =
    reviewSegments.find(segment => segment.id === repairQueue.nextSegmentId) ||
    reviewSegments[0] ||
    null;
  const reviewConsoleStatus = voice.transcript.interimText
    ? "waiting"
    : nextRepairSegment
      ? "review"
      : voice.transcript.combinedText
        ? "ready"
        : "empty";
  const reviewConsoleLabel =
    reviewConsoleStatus === "waiting"
      ? "Wait for final text"
      : reviewConsoleStatus === "review"
        ? "Fix the next segment"
        : reviewConsoleStatus === "ready"
          ? "Ready to run"
          : "No dictation yet";
  const reviewConsoleSummary =
    reviewConsoleStatus === "waiting"
      ? "The transcript is still changing, so command sending remains paused."
      : reviewConsoleStatus === "review"
        ? "Edit the highlighted phrase or mark it reviewed before running a guarded action."
        : reviewConsoleStatus === "ready"
          ? "The transcript has passed the visible review checks."
          : "Start capture, use system dictation, or paste text through the normal composer.";
  const [manualCorrectionDraft, setManualCorrectionDraft] = useState(nextRepairSegment?.text || "");

  useEffect(() => {
    setManualCorrectionDraft(nextRepairSegment?.text || "");
  }, [nextRepairSegment?.id, nextRepairSegment?.text]);

  const applyManualCorrection = () => {
    const correctedText = manualCorrectionDraft.trim();
    if (!nextRepairSegment || !correctedText) {
      return;
    }
    voice.correctTranscriptSegment?.(nextRepairSegment.id, {
      text: correctedText,
      confidence: Math.max(nextRepairSegment.confidence ?? 0.92, 0.92),
      reason: "manual dictation repair",
    });
  };
  const manualCorrectionChanged =
    Boolean(nextRepairSegment) &&
    manualCorrectionDraft.trim() &&
    manualCorrectionDraft.trim() !== nextRepairSegment.text;

  return (
    <section className="fluxio-voice-panel" aria-label="Voice command controls" {...motion}>
      <div className="fluxio-voice-panel-head">
        <div>
          <p className="eyebrow">Voice input</p>
          <h2>Dictation review</h2>
        </div>
        <span className="fluxio-voice-status-pill" data-supported={capture.canStartLiveCapture}>
          {capture.label}
        </span>
      </div>

      <p className="fluxio-voice-live-status" aria-atomic="true" aria-live="polite">
        {voice.status}
      </p>

      <div className="fluxio-voice-quality-grid" aria-label="Transcription quality checks">
        <div className="fluxio-voice-quality-card">
          <span>Confidence</span>
          <strong>{confidenceLabel}</strong>
        </div>
        <div className="fluxio-voice-quality-card">
          <span>Review</span>
          <strong>{voice.transcript.reviewRequired ? "Needed" : "Clear"}</strong>
        </div>
        <div className="fluxio-voice-quality-card">
          <span>Corrections</span>
          <strong>{voice.transcript.correctionCount || 0}</strong>
        </div>
        <div className="fluxio-voice-quality-card">
          <span>Pre-send gate</span>
          <strong>{sendGateLabel}</strong>
        </div>
        <div className="fluxio-voice-quality-card">
          <span>Capture source</span>
          <strong>{capture.source || capture.label}</strong>
        </div>
        <div className="fluxio-voice-quality-card">
          <span>Capture state</span>
          <strong>{captureLifecycle.label}</strong>
        </div>
      </div>

      <div
        className="fluxio-voice-capture-diagnostics"
        data-ready={capture.canStartLiveCapture}
        aria-label="Voice capture diagnostics"
      >
        <div>
          <strong>{capture.canStartLiveCapture ? "Live capture ready" : "Live capture not wired"}</strong>
          <p>{capture.status}</p>
          <p>{captureLifecycle.detail}</p>
        </div>
        {capture.recovery ? <span>{capture.recovery}</span> : null}
        {captureLifecycle.status === "stopped" ? <span>Capture stopped by {captureLifecycle.source}</span> : null}
        <div className="fluxio-voice-capture-facts" aria-label="Voice capture lifecycle facts">
          <span>Last event: {captureLifecycle.lastCaptureEvent || captureLifecycle.status || "idle"}</span>
          <span>Restart attempts: {captureLifecycle.restartCount || 0}</span>
          <span>Last error: {captureLifecycle.lastCaptureErrorCode || "none"}</span>
        </div>
      </div>

      <div className="fluxio-voice-transcript" aria-label="Current voice transcript">
        {segmentList.length > 0 ? (
          <ol className="fluxio-voice-segment-list">
            {segmentList.map(segment => (
              <li
                className={
                  voice.transcript.lowConfidenceSegments?.some(item => item.id === segment.id) ||
                  voice.transcript.ambiguousSegments?.some(item => item.id === segment.id)
                    ? "needs-review"
                    : ""
                }
                key={segment.id}
              >
                <p>{segment.text}</p>
                <span>
                  {typeof segment.confidence === "number"
                    ? `${Math.round(segment.confidence * 100)}% confidence`
                    : "No confidence score"}
                  {segment.correctedFrom ? ` - corrected from "${segment.correctedFrom}"` : ""}
                </span>
                {segment.alternatives?.length ? (
                  <small>Alternatives: {segment.alternatives.map(item => item.text).join(", ")}</small>
                ) : null}
                <div className="fluxio-voice-correction-actions" aria-label={`Correction actions for ${segment.text}`}>
                  {segment.alternatives?.slice(0, 3).map(alternative => (
                    <button
                      key={`${segment.id}-${alternative.text}`}
                      onClick={() =>
                        voice.correctTranscriptSegment?.(segment.id, {
                          text: alternative.text,
                          confidence: alternative.confidence ?? segment.confidence,
                          reason: "selected speech alternative",
                        })
                      }
                      type="button"
                    >
                      Use "{alternative.text}"
                    </button>
                  ))}
                  <button
                    onClick={() =>
                      voice.correctTranscriptSegment?.(segment.id, {
                        text: segment.text,
                        confidence: Math.max(segment.confidence ?? 0.92, 0.92),
                        reason: "operator reviewed text",
                      })
                    }
                    type="button"
                  >
                    Mark reviewed
                  </button>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className="fluxio-voice-empty">
            {capture.canStartLiveCapture
              ? "Dictated text will appear here after capture starts."
              : "Use system dictation, paste text, or connect the voice adapter before starting live capture."}
          </p>
        )}
        {voice.transcript.interimText ? (
          <p className="fluxio-voice-interim">Still listening: {voice.transcript.interimText}</p>
        ) : null}
        {voice.transcript.warnings.map(item => (
          <span className="fluxio-voice-warning" key={item}>
            <WarningCircle aria-hidden="true" size={16} weight="duotone" />
            {item}
          </span>
        ))}
      </div>

      <div className="fluxio-voice-checks" aria-label="Voice quality check details">
        {(voice.transcript.qualityChecks || []).map(check => (
          <span className="fluxio-voice-check" data-status={check.status} key={check.id} title={check.detail}>
            <Info aria-hidden="true" size={15} weight="duotone" />
            {check.label}: {check.status}
          </span>
        ))}
      </div>

      <div className="fluxio-voice-repair-queue" data-status={repairQueue.status} aria-label="Dictation repair queue">
        <div>
          <span>Repair queue</span>
          <strong>{repairQueue.label}</strong>
          <p>{repairQueue.summary}</p>
        </div>
        <div className="fluxio-voice-repair-counts">
          <span>Low confidence: {repairQueue.lowConfidenceCount}</span>
          <span>Ambiguous: {repairQueue.ambiguousCount}</span>
          <span>Interim: {repairQueue.interimActive ? "active" : "clear"}</span>
        </div>
        {repairQueue.nextSegmentText ? (
          <p className="fluxio-voice-next-repair">
            Next repair: {repairQueue.nextSegmentText}
          </p>
        ) : null}
      </div>

      <div
        className="fluxio-voice-review-console"
        data-status={reviewConsoleStatus}
        aria-label="Dictation review console"
      >
        <div className="fluxio-voice-review-head">
          <div>
            <span>Review console</span>
            <strong>{reviewConsoleLabel}</strong>
            <p>{reviewConsoleSummary}</p>
          </div>
          <span className="fluxio-voice-review-status">{sendGateLabel}</span>
        </div>
        <div className="fluxio-voice-review-checks" aria-label="Dictation send readiness">
          <span data-status={voice.transcript.interimText ? "waiting" : "ready"}>Final text</span>
          <span data-status={repairQueue.lowConfidenceCount > 0 ? "review" : "ready"}>Confidence</span>
          <span data-status={repairQueue.ambiguousCount > 0 ? "review" : "ready"}>Command ambiguity</span>
          <span data-status={voice.sendGuard?.status === "blocked" ? "blocked" : "ready"}>Accidental-send check</span>
        </div>
        {nextRepairSegment ? (
          <div className="fluxio-voice-manual-repair">
            <label htmlFor={`voice-manual-correction-${nextRepairSegment.id}`}>
              Correction text
              <input
                id={`voice-manual-correction-${nextRepairSegment.id}`}
                onChange={event => setManualCorrectionDraft(event.target.value)}
                type="text"
                value={manualCorrectionDraft}
              />
            </label>
            <div className="fluxio-voice-manual-repair-actions">
              <button
                disabled={!manualCorrectionChanged}
                onClick={applyManualCorrection}
                type="button"
              >
                Apply correction
              </button>
              <button
                onClick={() =>
                  voice.correctTranscriptSegment?.(nextRepairSegment.id, {
                    text: nextRepairSegment.text,
                    confidence: Math.max(nextRepairSegment.confidence ?? 0.92, 0.92),
                    reason: "operator reviewed text",
                  })
                }
                type="button"
              >
                Mark reviewed
              </button>
            </div>
            <p>
              Next repair is tracked as {repairQueue.nextRepairKind || "dictation review"} so the command cannot be sent silently.
            </p>
          </div>
        ) : (
          <div className="fluxio-voice-manual-repair is-empty">
            <label htmlFor="voice-manual-correction-empty">
              Correction text
              <input
                disabled
                id="voice-manual-correction-empty"
                placeholder="Waiting for dictated text"
                type="text"
                value=""
              />
            </label>
            <p className="fluxio-voice-review-empty">
              {voice.transcript.interimText
                ? "Stop capture or wait for final text before correction controls unlock."
                : voice.transcript.combinedText
                  ? "No correction is queued. Use Run when the pre-send gate is acceptable."
                  : "Correction controls unlock when dictated text needs review."}
            </p>
          </div>
        )}
      </div>

      <div className="fluxio-voice-actions">
        <button
          aria-label={buildKeyboardParityLabel({
            label: voice.listening ? "Stop dictation" : "Start dictation",
            shortcut: "Ctrl+Shift+V",
            voice: voice.listening ? "stop dictation" : "start dictation",
          })}
          disabled={startDisabled}
          onClick={() => (voice.listening ? voice.stopListening() : voice.startListening())}
          type="button"
          title={startDisabled ? capture.recovery || capture.status : undefined}
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

      <div className="fluxio-voice-send-gate" aria-label="Voice pre-send safety gate">
        <strong>{sendGateLabel}</strong>
        <p>{voice.sendGuard?.detail || "Dictate, review, then run the command when the gate is clear."}</p>
        <span>
          {voice.transcript.reviewRequired
            ? "Correction flow is active."
            : voice.transcript.combinedText
              ? "Transcript is ready for command parsing."
              : "No dictated text is ready yet."}
        </span>
      </div>

      {voice.pendingCommand ? (
        <div className="fluxio-voice-confirm">
          <p>{voice.pendingCommand.confirmationPrompt || "Confirm this voice command before it runs."}</p>
          <button onClick={() => voice.confirmPendingCommand()} type="button">
            Confirm
          </button>
        </div>
      ) : null}

      {voice.sendGuard?.status && voice.sendGuard.status !== "idle" ? (
        <div className="fluxio-voice-guard" data-status={voice.sendGuard.status}>
          <ShieldCheck aria-hidden="true" size={17} weight="duotone" />
          <div>
            <strong>{voice.sendGuard.label}</strong>
            <p>{voice.sendGuard.detail}</p>
          </div>
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
