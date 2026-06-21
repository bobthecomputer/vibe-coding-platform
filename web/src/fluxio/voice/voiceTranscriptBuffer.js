const DEFAULT_MAX_SEGMENTS = 80;
const DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.72;
const DEFAULT_AMBIGUITY_CONFIDENCE_THRESHOLD = 0.84;

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

function normalizeTextList(value) {
  const source = Array.isArray(value) ? value : [];
  return source
    .map(item => {
      if (typeof item === "string") {
        return normalizeText(item);
      }
      return normalizeText(item?.text ?? item?.transcript ?? "");
    })
    .filter(Boolean)
    .slice(0, 5);
}

function normalizeAlternatives(value) {
  const source = Array.isArray(value) ? value : [];
  return source
    .map(item => {
      if (typeof item === "string") {
        return { text: normalizeText(item), confidence: null };
      }
      return {
        text: normalizeText(item?.text ?? item?.transcript ?? ""),
        confidence: clampConfidence(item?.confidence),
      };
    })
    .filter(item => item.text)
    .slice(0, 5);
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
    alternatives: normalizeAlternatives(input.alternatives ?? fallback.alternatives),
    ambiguityReasons: normalizeTextList(input.ambiguityReasons ?? fallback.ambiguityReasons),
    correctionOf: input.correctionOf || fallback.correctionOf || "",
    correctedFrom: normalizeText(input.correctedFrom ?? fallback.correctedFrom ?? ""),
    correctedAt: input.correctedAt || fallback.correctedAt || "",
  };
}

export function createVoiceTranscriptState(options = {}) {
  return {
    segments: [],
    interim: null,
    maxSegments: Math.max(1, Number(options.maxSegments || DEFAULT_MAX_SEGMENTS)),
    lowConfidenceThreshold: clampConfidence(options.lowConfidenceThreshold) ?? DEFAULT_LOW_CONFIDENCE_THRESHOLD,
    ambiguityConfidenceThreshold:
      clampConfidence(options.ambiguityConfidenceThreshold) ?? DEFAULT_AMBIGUITY_CONFIDENCE_THRESHOLD,
    correctionLog: [],
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
  const target = current.segments.find(segment => segment.id === segmentId);
  if (!target) {
    return current;
  }
  const normalizedPatch = normalizeSegment(patch, {
    id: segmentId,
    revision: 1,
    correctedFrom: target.text,
    correctionOf: segmentId,
  });
  const correctedText = normalizedPatch.text || target.text;
  const correctionEntry = {
    id: makeSegmentId("voice-correction"),
    segmentId,
    from: target.text,
    to: correctedText,
    reason: normalizeText(patch.reason || patch.correctionReason || "manual correction"),
    at: patch.correctedAt || new Date().toISOString(),
  };
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
        text: correctedText,
        correctionOf: segment.id,
        correctedFrom: target.text,
        correctedAt: correctionEntry.at,
        revision: segment.revision + 1,
      };
    }),
    correctionLog: [...(Array.isArray(current.correctionLog) ? current.correctionLog : []), correctionEntry].slice(-20),
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
    correctionLog: [],
    revision: current.revision + 1,
  };
}

export function buildTranscriptQualityChecks(state) {
  const current = state || createVoiceTranscriptState();
  const segments = Array.isArray(current.segments) ? current.segments : [];
  const interim = current.interim;
  const lowConfidenceThreshold = current.lowConfidenceThreshold ?? DEFAULT_LOW_CONFIDENCE_THRESHOLD;
  const ambiguityConfidenceThreshold =
    current.ambiguityConfidenceThreshold ?? DEFAULT_AMBIGUITY_CONFIDENCE_THRESHOLD;
  const lowConfidenceSegments = segments.filter(
    segment => typeof segment.confidence === "number" && segment.confidence < lowConfidenceThreshold,
  );
  const ambiguousSegments = segments.filter(segment => {
    const hasAlternatives = Array.isArray(segment.alternatives) && segment.alternatives.length > 0;
    const hasExplicitReason = Array.isArray(segment.ambiguityReasons) && segment.ambiguityReasons.length > 0;
    const confidenceNeedsAttention =
      typeof segment.confidence === "number" &&
      segment.confidence >= lowConfidenceThreshold &&
      segment.confidence < ambiguityConfidenceThreshold;
    return hasAlternatives || hasExplicitReason || confidenceNeedsAttention;
  });
  const correctionLog = Array.isArray(current.correctionLog) ? current.correctionLog : [];

  return [
    {
      id: "final-text",
      label: "Final transcript",
      status: interim?.text ? "waiting" : segments.length > 0 ? "ready" : "empty",
      detail: interim?.text
        ? "Speech recognition still has interim text."
        : `${segments.length} final segment${segments.length === 1 ? "" : "s"}.`,
    },
    {
      id: "confidence",
      label: "Confidence",
      status: lowConfidenceSegments.length > 0 ? "review" : "ready",
      detail:
        lowConfidenceSegments.length > 0
          ? `${lowConfidenceSegments.length} segment${lowConfidenceSegments.length === 1 ? "" : "s"} below review threshold.`
          : "No final segment is below the review threshold.",
    },
    {
      id: "ambiguity",
      label: "Ambiguity",
      status: ambiguousSegments.length > 0 ? "review" : "ready",
      detail:
        ambiguousSegments.length > 0
          ? `${ambiguousSegments.length} segment${ambiguousSegments.length === 1 ? "" : "s"} has alternatives or ambiguous confidence.`
          : "No alternatives or ambiguity markers recorded.",
    },
    {
      id: "corrections",
      label: "Corrections",
      status: correctionLog.length > 0 ? "changed" : "ready",
      detail:
        correctionLog.length > 0
          ? `${correctionLog.length} correction${correctionLog.length === 1 ? "" : "s"} recorded.`
          : "No corrections recorded.",
    },
  ];
}

export function buildVoiceRepairQueue(snapshot = {}) {
  const lowConfidence = Array.isArray(snapshot.lowConfidenceSegments) ? snapshot.lowConfidenceSegments : [];
  const ambiguous = Array.isArray(snapshot.ambiguousSegments) ? snapshot.ambiguousSegments : [];
  const interim = snapshot.interim || (snapshot.interimText ? { text: snapshot.interimText } : null);
  const reviewItems = [
    ...lowConfidence.map(segment => ({ ...segment, repairKind: "low_confidence" })),
    ...ambiguous
      .filter(segment => !lowConfidence.some(item => item.id === segment.id))
      .map(segment => ({ ...segment, repairKind: "ambiguity" })),
  ];
  const nextItem = reviewItems[0] || null;
  const blocked = Boolean(interim?.text || reviewItems.length > 0);
  return {
    status: blocked ? "review" : snapshot.combinedText ? "ready" : "empty",
    label: blocked ? "Repair before send" : snapshot.combinedText ? "Ready after review" : "No dictation yet",
    summary: interim?.text
      ? "Wait for final text or stop capture before running a command."
      : reviewItems.length > 0
        ? `${reviewItems.length} dictated segment${reviewItems.length === 1 ? "" : "s"} need review.`
        : snapshot.combinedText
          ? "Transcript can be parsed after operator review."
          : "Dictate, paste, or connect a voice adapter.",
    lowConfidenceCount: lowConfidence.length,
    ambiguousCount: ambiguous.length,
    interimActive: Boolean(interim?.text),
    nextSegmentId: nextItem?.id || "",
    nextSegmentText: nextItem?.text || interim?.text || "",
    nextRepairKind: nextItem?.repairKind || (interim?.text ? "interim" : ""),
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
  const ambiguousSegments = segments.filter(segment => {
    const hasAlternatives = Array.isArray(segment.alternatives) && segment.alternatives.length > 0;
    const hasExplicitReason = Array.isArray(segment.ambiguityReasons) && segment.ambiguityReasons.length > 0;
    const confidenceNeedsAttention =
      typeof segment.confidence === "number" &&
      segment.confidence >= (current.lowConfidenceThreshold ?? DEFAULT_LOW_CONFIDENCE_THRESHOLD) &&
      segment.confidence < (current.ambiguityConfidenceThreshold ?? DEFAULT_AMBIGUITY_CONFIDENCE_THRESHOLD);
    return hasAlternatives || hasExplicitReason || confidenceNeedsAttention;
  });
  const correctionLog = Array.isArray(current.correctionLog) ? current.correctionLog : [];
  const qualityChecks = buildTranscriptQualityChecks(current);

  const warnings = [];
  if (lowConfidenceSegments.length > 0) {
    warnings.push("Some dictated words were unclear. Review the highlighted transcript before sending.");
  }
  if (ambiguousSegments.length > 0) {
    warnings.push("Speech recognition recorded alternatives or ambiguous confidence. Check the transcript before sending.");
  }
  if (current.interim?.text) {
    warnings.push("Listening result is still changing. Wait for final text before launching an action.");
  }

  const snapshot = {
    segments,
    interim: current.interim,
    finalText,
    interimText,
    combinedText,
    averageConfidence,
    lowConfidenceSegments,
    ambiguousSegments,
    correctionLog,
    correctionCount: correctionLog.length,
    qualityChecks,
    warnings,
    reviewRequired: qualityChecks.some(check => check.status === "review" || check.status === "waiting"),
    isEmpty: !combinedText,
    revision: current.revision || 0,
  };
  return {
    ...snapshot,
    repairQueue: buildVoiceRepairQueue(snapshot),
  };
}

export function transcriptNeedsReview(state) {
  const snapshot = buildTranscriptSnapshot(state);
  return snapshot.reviewRequired;
}
