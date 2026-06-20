const DEFAULT_MAX_SEGMENTS = 80;
const DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.72;

function clampConfidence(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const next = Number(value);
  if (!Number.isFinite(next)) {
    return null;
  }
  return Math.max(0, Math.min(1, next));
}

function normalizeText(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim();
}

function makeSegmentId(prefix = "voice-segment") {
  const random =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  return `${prefix}-${random}`;
}

function normalizeSegment(input = {}, fallback = {}) {
  const text = normalizeText(input.text ?? input.transcript ?? "");
  return {
    id: input.id || fallback.id || makeSegmentId(),
    text,
    confidence: clampConfidence(input.confidence),
    source: input.source || fallback.source || "manual",
    isFinal: input.isFinal !== false,
    receivedAt: input.receivedAt || fallback.receivedAt || new Date().toISOString(),
    revision: Number.isInteger(input.revision) ? input.revision : fallback.revision || 0,
  };
}

export function createVoiceTranscriptState(options = {}) {
  return {
    segments: [],
    interim: null,
    maxSegments: Math.max(1, Number(options.maxSegments || DEFAULT_MAX_SEGMENTS)),
    lowConfidenceThreshold: clampConfidence(options.lowConfidenceThreshold) ?? DEFAULT_LOW_CONFIDENCE_THRESHOLD,
    revision: 0,
  };
}

export function appendTranscriptSegment(state, input = {}) {
  const current = state || createVoiceTranscriptState();
  const segment = normalizeSegment(input);
  if (!segment.text) {
    return current;
  }

  if (!segment.isFinal) {
    return {
      ...current,
      interim: segment,
      revision: current.revision + 1,
    };
  }

  const maxSegments = Math.max(1, Number(current.maxSegments || DEFAULT_MAX_SEGMENTS));
  return {
    ...current,
    segments: [...current.segments, segment].slice(-maxSegments),
    interim: input.clearInterim === false ? current.interim : null,
    revision: current.revision + 1,
  };
}

export function finalizeInterimTranscript(state, patch = {}) {
  const current = state || createVoiceTranscriptState();
  if (!current.interim) {
    return current;
  }
  return appendTranscriptSegment(current, {
    ...current.interim,
    ...patch,
    isFinal: true,
  });
}

export function replaceTranscriptSegment(state, segmentId, patch = {}) {
  const current = state || createVoiceTranscriptState();
  const normalizedPatch = normalizeSegment(patch, { id: segmentId, revision: 1 });
  return {
    ...current,
    segments: current.segments.map(segment => {
      if (segment.id !== segmentId) {
        return segment;
      }
      return {
        ...segment,
        ...normalizedPatch,
        id: segment.id,
        text: normalizedPatch.text || segment.text,
        revision: segment.revision + 1,
      };
    }),
    revision: current.revision + 1,
  };
}

export function clearTranscriptBuffer(state, reason = "manual_clear") {
  const current = state || createVoiceTranscriptState();
  return {
    ...current,
    segments: [],
    interim: null,
    lastClearReason: reason,
    revision: current.revision + 1,
  };
}

export function buildTranscriptSnapshot(state) {
  const current = state || createVoiceTranscriptState();
  const segments = Array.isArray(current.segments) ? current.segments : [];
  const finalText = segments.map(segment => segment.text).filter(Boolean).join(" ").trim();
  const interimText = current.interim?.text || "";
  const combinedText = [finalText, interimText].filter(Boolean).join(" ").trim();
  const confidenceValues = segments
    .map(segment => segment.confidence)
    .filter(value => typeof value === "number");
  const averageConfidence = confidenceValues.length
    ? confidenceValues.reduce((total, value) => total + value, 0) / confidenceValues.length
    : null;
  const lowConfidenceSegments = segments.filter(
    segment =>
      typeof segment.confidence === "number" &&
      segment.confidence < (current.lowConfidenceThreshold ?? DEFAULT_LOW_CONFIDENCE_THRESHOLD),
  );

  const warnings = [];
  if (lowConfidenceSegments.length > 0) {
    warnings.push("Some dictated words were unclear. Review the highlighted transcript before sending.");
  }
  if (current.interim?.text) {
    warnings.push("Listening result is still changing. Wait for final text before launching an action.");
  }

  return {
    segments,
    interim: current.interim,
    finalText,
    interimText,
    combinedText,
    averageConfidence,
    lowConfidenceSegments,
    warnings,
    isEmpty: !combinedText,
    revision: current.revision || 0,
  };
}

export function transcriptNeedsReview(state) {
  const snapshot = buildTranscriptSnapshot(state);
  return snapshot.lowConfidenceSegments.length > 0 || Boolean(snapshot.interim);
}

