export const IMAGE_PLAYGROUND_STORAGE_KEY = "fluxio.image_playground.project.v1";

export const CANVAS_SIZE_PRESETS = [
  { id: "square", label: "Square", width: 1024, height: 1024 },
  { id: "portrait", label: "Portrait", width: 1024, height: 1536 },
  { id: "landscape", label: "Landscape", width: 1536, height: 1024 },
  { id: "wide", label: "Wide", width: 1792, height: 1024 },
];

export const IMAGE_TOOL_DEFINITIONS = [
  { id: "select", label: "Move", hint: "Move, resize, and reorder layers." },
  { id: "region", label: "Edit area", hint: "Mark an area for inpainting or continuation." },
  { id: "mask", label: "Mask", hint: "Prepare mask-guided edits." },
  { id: "compare", label: "Compare", hint: "Review previous generations." },
];

export const IMAGEGEN_LIBRARY_ARTIFACT = {
  id: "generated-coastal-retreat-reference",
  title: "Generated coastal retreat image",
  kind: "generated-image",
  artifactPath: "web/public/image-studio/generated-coastal-retreat.png",
  previewSrc: "/image-studio/generated-coastal-retreat.png",
  sourceArtifactPath: ".agent_control/design_references/codex_image_artifacts/codex_image_playground_live_review_reference_20260511T071327Z.png",
  manifestPath: ".agent_control/design_references/codex_image_artifacts/codex_image_playground_live_review_reference_20260511T071327Z.manifest.json",
  requestId: "codex_image_playground_live_review_reference_20260511T071327Z",
  artifactId: "generated-coastal-retreat-reference",
  source: "codex_generated_design_reference_crop",
  provider: "Generated image reference",
  artifactSha256: "",
  manifestSha256: "7b6fca2704c5b4c5e8bfc102cce95070af06174ba085208fe435f1d0f62e5c96",
  selected: true,
  rationale: "Real generated bitmap cropped from the existing Codex-generated Image Studio reference artifact for default visual proof.",
};

export const DEFAULT_IMAGE_PROJECT = {
  id: "image-project-local",
  title: "Untitled image workspace",
  updatedAt: "",
  canvas: {
    width: 1024,
    height: 768,
    background: "#111313",
    zoom: 0.62,
  },
  prompt: {
    mode: "generate",
    text: "A cinematic product image of a matte black modular camera on dark stone, soft side light, precise reflections, premium editorial composition",
    negative: "blurry, distorted geometry, extra buttons, warped lens, unreadable text, plastic toy finish",
    style: "studio product photography, restrained contrast, clean shadows, high-detail black materials",
    strength: 0.58,
    preserveComposition: true,
  },
  provider: {
    id: "codex_subscription_gpt_image2",
    model: "gpt-image-2",
    quality: "high",
    size: "1024x1024",
  },
  chromaKey: {
    enabled: true,
    keyColor: "#00ff66",
    tolerance: 28,
    spillCleanup: 44,
    edgeFeather: 12,
    matteMode: "remove_background",
    replacementIntent: "transparent alpha matte with clean product edges",
    proofLabels: ["key color sampled", "spill cleanup planned", "edge feather planned"],
  },
  designReferences: [IMAGEGEN_LIBRARY_ARTIFACT],
  annotationReadiness: {
    pins: [],
    rectangles: [],
    layers: [],
    comments: [],
  },
  skillsEvidence: [],
  focusedHistoryId: "",
  opsThreads: [],
  selectedLayerId: "layer-generated-image",
  activeTool: "select",
  selection: {
    x: 650,
    y: 372,
    width: 228,
    height: 168,
    feather: 12,
    visible: false,
  },
  layers: [
    {
      id: "layer-background",
      name: "Local preview backdrop",
      type: "shape",
      locked: true,
      visible: true,
      opacity: 1,
      blendMode: "normal",
      x: 0,
      y: 0,
      width: 1024,
      height: 1024,
      rotation: 0,
      fill: "radial-gradient(circle at 18% 12%, rgba(238,242,236,.08), transparent 26%), radial-gradient(circle at 74% 28%, rgba(154,223,138,.12), transparent 28%), linear-gradient(135deg, #070808, #101414 58%, #050606)",
      promptRole: "local preview backdrop, not provider output",
    },
    {
      id: "layer-generated-image",
      name: "Generated coastal retreat image",
      type: "image",
      locked: false,
      visible: true,
      opacity: 1,
      blendMode: "normal",
      x: 96,
      y: 72,
      width: 832,
      height: 624,
      rotation: 0,
      src: "/image-studio/generated-coastal-retreat.png",
      radius: 24,
      promptRole: "real generated image reference displayed in the editable canvas",
    },
  ],
  history: [
    {
      id: "hist-generated-coastal-retreat-reference",
      title: "Generated coastal retreat image",
      prompt: "Modern coastal retreat at sunset, glass house on a cliff, infinity pool, warm interior lights, dramatic clouds, natural landscaping, photorealistic.",
      provider: "Generated image reference",
      providerId: "codex-generated-reference",
      createdAt: "2026-05-11T07:13:27+02:00",
      status: "generated",
      requestId: "codex_image_playground_live_review_reference_20260511T071327Z",
      providerStatus: "available",
      outputArtifactPath: "web/public/image-studio/generated-coastal-retreat.png",
      previewSrc: "/image-studio/generated-coastal-retreat.png",
      manifestPath: ".agent_control/design_references/codex_image_artifacts/codex_image_playground_live_review_reference_20260511T071327Z.manifest.json",
      manifestUrl: ".agent_control/design_references/codex_image_artifacts/codex_image_playground_live_review_reference_20260511T071327Z.manifest.json",
      layerCount: 1,
      receipt: {
        promptHash: "generated-reference",
        providerName: "Generated image reference",
        source: "Existing generated bitmap artifact",
        testStatus: "Displayed",
      },
    },
  ],
};

export function isRealImageSession(item) {
  if (!item || typeof item !== "object") return false;
  const provider = String(item.provider || item.providerId || "").toLowerCase();
  if (provider.includes("local composition") || provider === "local project") return false;
  const requestId = String(item.requestId || "").trim();
  const status = String(item.status || "").toLowerCase();
  const providerStatus = String(item.providerStatus || "").toLowerCase();
  const persistedArtifact = [
    item.outputArtifactPath,
    item.manifestPath,
    item.manifestUrl,
    item.artifactPath,
    item.previewSrc,
  ].some(value => {
    const source = String(value || "").trim();
    return source && !source.startsWith("data:");
  });
  if (status.includes("provider_blocked") || providerStatus === "blocked") {
    return Boolean(requestId) && (provider.includes("codex") || provider.includes("openai"));
  }
  return Boolean(requestId && persistedArtifact) && (
    status.includes("generated") ||
    status.includes("edited") ||
    providerStatus === "available"
  );
}

export function nowIso() {
  return new Date().toISOString();
}

export function makeId(prefix = "id") {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function keyboardScopeLabel(scope) {
  return scope === "queue" ? "Queue" : "History";
}

export function buildKeyboardTraversalAnnouncement({
  fromScope = "history",
  fromIndex = 0,
  fromCount = 0,
  toScope = "history",
  toIndex = 0,
  toCount = 0,
  reason = "focus",
} = {}) {
  const fromText = `${keyboardScopeLabel(fromScope)} ${Math.max(0, Number(fromIndex) || 0)}/${Math.max(0, Number(fromCount) || 0)}`;
  const toText = `${keyboardScopeLabel(toScope)} ${Math.max(0, Number(toIndex) || 0)}/${Math.max(0, Number(toCount) || 0)}`;
  if (reason === "group-jump" || reason === "edge-jump") {
    return `${fromText} -> ${toText}`;
  }
  return `${toText} focused`;
}

export function appendKeyboardJumpTrail(trail = [], transition = {}, options = {}) {
  const maxEntries = Math.max(1, Number(options.maxEntries) || 3);
  const nextEntry = {
    at: String(options.at || nowIso()),
    announcement: buildKeyboardTraversalAnnouncement(transition),
    fromScope: transition.fromScope || "history",
    toScope: transition.toScope || "history",
    reason: String(transition.reason || "focus"),
  };
  return [...(Array.isArray(trail) ? trail : []), nextEntry].slice(-maxEntries);
}

export function keyboardTraversalReasonLabel(reason = "focus") {
  const normalized = String(reason || "focus").toLowerCase();
  if (normalized === "group-jump") return "Scope jump";
  if (normalized === "edge-jump") return "Edge jump";
  if (normalized === "arrow") return "Arrow move";
  return "Focus";
}

export function formatKeyboardJumpTrailEntry(entry = {}) {
  const label = String(entry.announcement || "").trim() || "Traversal";
  const at = entry.at;
  if (!at) return label;
  try {
    const time = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(at));
    return `${time} ${label}`;
  } catch {
    return `Recently ${label}`;
  }
}

export function formatKeyboardJumpTrailTooltip(entry = {}) {
  const label = String(entry.announcement || "").trim() || "Traversal";
  const reason = keyboardTraversalReasonLabel(entry.reason);
  const at = entry.at;
  if (!at) return `${reason} • ${label}`;
  try {
    const fullTime = new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date(at));
    return `${fullTime} • ${reason} • ${label}`;
  } catch {
    return `${reason} • ${label}`;
  }
}

export function normalizeProject(project) {
  const base = structuredCloneSafe(DEFAULT_IMAGE_PROJECT);
  const next = { ...base, ...(project && typeof project === "object" ? project : {}) };
  next.canvas = { ...base.canvas, ...(next.canvas || {}) };
  next.prompt = { ...base.prompt, ...(next.prompt || {}) };
  next.provider = { ...base.provider, ...(next.provider || {}) };
  next.chromaKey = { ...base.chromaKey, ...(next.chromaKey || {}) };
  next.chromaKey.enabled = Boolean(next.chromaKey.enabled);
  next.chromaKey.keyColor = String(next.chromaKey.keyColor || base.chromaKey.keyColor);
  next.chromaKey.tolerance = Math.max(0, Math.min(100, Number(next.chromaKey.tolerance) || 0));
  next.chromaKey.spillCleanup = Math.max(0, Math.min(100, Number(next.chromaKey.spillCleanup) || 0));
  next.chromaKey.edgeFeather = Math.max(0, Math.min(64, Number(next.chromaKey.edgeFeather) || 0));
  next.designReferences = Array.isArray(next.designReferences) ? next.designReferences : base.designReferences;
  for (const reference of base.designReferences) {
    if (!next.designReferences.some(item => item?.id === reference.id || item?.artifactId === reference.artifactId)) {
      next.designReferences.unshift(reference);
    }
  }
  next.annotationReadiness = { ...base.annotationReadiness, ...(next.annotationReadiness || {}) };
  next.skillsEvidence = Array.isArray(next.skillsEvidence) ? next.skillsEvidence : base.skillsEvidence;
  next.focusedHistoryId = String(next.focusedHistoryId || "");
  next.opsThreads = Array.isArray(next.opsThreads) ? next.opsThreads : base.opsThreads;
  next.selection = { ...base.selection, ...(next.selection || {}) };
  next.layers = Array.isArray(next.layers) && next.layers.length ? next.layers : base.layers;
  const layerIds = next.layers.map(layer => String(layer?.id || ""));
  const hasLegacyBlobPreview =
    layerIds.includes("layer-subject") &&
    layerIds.includes("layer-shadow") &&
    layerIds.includes("layer-background");
  if (next.id === base.id && hasLegacyBlobPreview) {
    next.layers = base.layers;
    next.selection = base.selection;
    next.selectedLayerId = base.selectedLayerId;
  }
  next.history = (Array.isArray(next.history) ? next.history : base.history).filter(isRealImageSession);
  for (const item of base.history) {
    if (!next.history.some(entry => entry?.id === item.id || entry?.requestId === item.requestId)) {
      next.history.unshift(item);
    }
  }
  next.history = next.history.filter(isRealImageSession);
  next.updatedAt = next.updatedAt || nowIso();
  return next;
}

export function structuredCloneSafe(value) {
  if (typeof structuredClone === "function") {
    return structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value));
}

export function loadImageProject() {
  if (typeof window === "undefined") {
    return normalizeProject();
  }
  try {
    const raw = window.localStorage.getItem(IMAGE_PLAYGROUND_STORAGE_KEY);
    return normalizeProject(raw ? JSON.parse(raw) : undefined);
  } catch {
    return normalizeProject();
  }
}

export function saveImageProject(project) {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(IMAGE_PLAYGROUND_STORAGE_KEY, JSON.stringify(project));
  } catch {
    return;
  }
}

export function addHistoryEntry(project, entry) {
  const nextEntry = {
    id: makeId("hist"),
    createdAt: nowIso(),
    layerCount: project.layers.length,
    ...entry,
  };
  if (!isRealImageSession(nextEntry)) {
    return {
      ...project,
      updatedAt: nowIso(),
      history: (Array.isArray(project.history) ? project.history : []).filter(isRealImageSession),
    };
  }
  return {
    ...project,
    updatedAt: nowIso(),
    history: [nextEntry, ...(Array.isArray(project.history) ? project.history : [])]
      .filter(isRealImageSession)
      .slice(0, 40),
  };
}

export function projectToProviderPayload(project, operation = "edit", options = {}) {
  const normalized = normalizeProject(project);
  const layers = normalized.layers.map(layer => ({
    id: layer.id,
    name: layer.name,
    type: layer.type,
    visible: layer.visible,
    opacity: layer.opacity,
    blendMode: layer.blendMode,
    x: Math.round(layer.x),
    y: Math.round(layer.y),
    width: Math.round(layer.width),
    height: Math.round(layer.height),
    rotation: Number(layer.rotation || 0),
    promptRole: layer.promptRole || "",
    hasImage: Boolean(layer.src),
  }));
  const visibleLayers = layers.filter(layer => layer.visible !== false);
  return {
    operation,
    provider: normalized.provider,
    canvas: normalized.canvas,
    prompt: normalized.prompt,
    chromaKey: normalized.chromaKey,
    selection: normalized.selection,
    layers,
    compositionIntent: normalized.prompt.preserveComposition
      ? "Preserve the manual layer positions and selected region geometry as much as possible. Treat the canvas as the source composition for the next image operation."
      : "Use the canvas as loose visual context and allow broader reinterpretation.",
    inputs: {
      snapshotDataUrl: options.snapshotDataUrl || "",
      visibleLayerCount: visibleLayers.length,
      editRegion: {
        x: Math.round(normalized.selection.x || 0),
        y: Math.round(normalized.selection.y || 0),
        width: Math.round(normalized.selection.width || 0),
        height: Math.round(normalized.selection.height || 0),
        feather: Math.round(normalized.selection.feather || 0),
      },
    },
  };
}

export function createLayerFromSelection(project, options = {}) {
  const normalized = normalizeProject(project);
  const selection = normalized.selection || {};
  const layer = {
    id: options.id || makeId("layer-selection"),
    name: options.name || "Selected region",
    type: "shape",
    locked: false,
    visible: true,
    opacity: 0.78,
    blendMode: "screen",
    x: Math.round(selection.x || 0),
    y: Math.round(selection.y || 0),
    width: Math.max(1, Math.round(selection.width || 1)),
    height: Math.max(1, Math.round(selection.height || 1)),
    rotation: 0,
    fill: "linear-gradient(145deg, rgba(255,255,255,.58), rgba(214,168,79,.24))",
    radius: 20,
    mask: {
      feather: Math.max(0, Math.round(selection.feather || 0)),
    },
    promptRole: options.promptRole || "selected region",
  };
  return {
    ...normalized,
    selectedLayerId: layer.id,
    updatedAt: nowIso(),
    layers: [...normalized.layers, layer],
  };
}

export function updateLayerInProject(project, layerId, patch = {}) {
  const normalized = normalizeProject(project);
  return {
    ...normalized,
    updatedAt: nowIso(),
    layers: normalized.layers.map(layer => (layer.id === layerId ? { ...layer, ...patch } : layer)),
  };
}

export function removeLayerFromProject(project, layerId) {
  const normalized = normalizeProject(project);
  if (normalized.layers.length <= 1) {
    return normalized;
  }
  const nextLayers = normalized.layers.filter(layer => layer.id !== layerId);
  if (nextLayers.length === 0) {
    return normalized;
  }
  const selectedLayerId =
    normalized.selectedLayerId === layerId
      ? nextLayers[nextLayers.length - 1].id
      : normalized.selectedLayerId;
  return {
    ...normalized,
    updatedAt: nowIso(),
    layers: nextLayers,
    selectedLayerId,
  };
}

export function setFocusedHistoryItem(project, historyId) {
  const normalized = normalizeProject(project);
  const nextFocusedId = String(historyId || "");
  const target = normalized.history.find(item => item.id === nextFocusedId);
  const snapshot = target?.annotationSnapshot || {
    pins: [],
    rectangles: [],
    layers: [],
    comments: [],
  };
  return {
    ...normalized,
    focusedHistoryId: target ? target.id : "",
    annotationReadiness: {
      ...normalized.annotationReadiness,
      pins: Array.isArray(snapshot.pins) ? snapshot.pins : [],
      rectangles: Array.isArray(snapshot.rectangles) ? snapshot.rectangles : [],
      layers: Array.isArray(snapshot.layers) ? snapshot.layers : [],
      comments: Array.isArray(snapshot.comments) ? snapshot.comments : [],
    },
  };
}

export function updateFocusedHistoryAnnotations(project, annotationPatch = {}) {
  const normalized = normalizeProject(project);
  const focusedHistoryId = normalized.focusedHistoryId || normalized.history[0]?.id || "";
  const nextAnnotationReadiness = {
    ...normalized.annotationReadiness,
    ...annotationPatch,
  };
  const nextHistory = normalized.history.map(item => {
    if (item.id !== focusedHistoryId) {
      return item;
    }
    return {
      ...item,
      annotationSnapshot: {
        ...(item.annotationSnapshot || {}),
        pins: Array.isArray(nextAnnotationReadiness.pins) ? nextAnnotationReadiness.pins : [],
        rectangles: Array.isArray(nextAnnotationReadiness.rectangles) ? nextAnnotationReadiness.rectangles : [],
        layers: Array.isArray(nextAnnotationReadiness.layers) ? nextAnnotationReadiness.layers : [],
        comments: Array.isArray(nextAnnotationReadiness.comments) ? nextAnnotationReadiness.comments : [],
      },
    };
  });
  return {
    ...normalized,
    focusedHistoryId,
    updatedAt: nowIso(),
    annotationReadiness: nextAnnotationReadiness,
    history: nextHistory,
  };
}

export function createOpsThreadForFocusedHistory(project, options = {}) {
  const normalized = normalizeProject(project);
  const focusedHistoryId = normalized.focusedHistoryId || normalized.history[0]?.id || "";
  if (!focusedHistoryId) {
    return normalized;
  }
  const focused = normalized.history.find(item => item.id === focusedHistoryId);
  const requestId = focused?.requestId || "pending-request-id";
  const receiptHash = focused?.receipt?.promptHash || "unknown";
  const threadId = focused?.issueThread?.id || `${receiptHash}:${requestId}`;
  const existing = normalized.opsThreads.find(thread => thread.id === threadId);
  const stamp = nowIso();
  const threadRecord = existing || {
    id: threadId,
    historyId: focusedHistoryId,
    requestId,
    receiptHash,
    title: options.title || `Image Playground issue ${threadId}`,
    status: "open",
    createdAt: stamp,
    updatedAt: stamp,
    messages: [],
  };
  const opsThreads = existing
    ? normalized.opsThreads.map(thread => (thread.id === threadId ? { ...thread, updatedAt: stamp } : thread))
    : [threadRecord, ...normalized.opsThreads];
  const history = normalized.history.map(item => (
    item.id === focusedHistoryId
      ? {
          ...item,
          issueThread: {
            id: threadId,
            requestId,
            receiptHash,
            href: `#issue-thread-${encodeURIComponent(threadId)}`,
            status: "open",
            syncedAt: stamp,
          },
        }
      : item
  ));
  return {
    ...normalized,
    focusedHistoryId,
    updatedAt: stamp,
    opsThreads,
    history,
    annotationReadiness: {
      ...normalized.annotationReadiness,
      activeThreadRef: threadId,
    },
  };
}
