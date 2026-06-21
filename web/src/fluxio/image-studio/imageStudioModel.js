import {
  isRealImageSession,
  makeId,
  normalizeProject,
  nowIso,
  projectToProviderPayload,
} from "../imagePlaygroundState.js";

export const IMAGE_STUDIO_STORAGE_KEY = "fluxio.image_studio.session.v1";

export const IMAGE_STUDIO_PROVIDER_ROUTES = [
  {
    id: "openai-gpt-image-2",
    label: "Codex subscription GPT-Image-2",
    providerId: "codex_subscription_gpt_image2",
    model: "gpt-image-2",
    status: "codex_subscription",
    authMode: "codex_subscription_oauth",
    supports: ["generate", "edit", "mask"],
    proofArtifacts: ["request manifest", "provider receipt", "output manifest", "artifact hash"],
    availability: {
      claim: "GPT-Image-2 runs through the local OpenClaw Codex subscription lane when backend capability proof is available.",
      localStatus: "codex_subscription_pending",
      runActionAvailable: false,
      officialSources: [
        "https://developers.openai.com/api/docs/guides/image-generation",
        "https://developers.openai.com/api/docs/models/gpt-image-2",
        "https://community.openai.com/t/introducing-gpt-image-2-available-today-in-the-api-and-codex/1379479",
      ],
    },
  },
  {
    id: "codex-imagegen-skill",
    label: "Existing Codex image artifacts",
    providerId: "codex-imagegen-skill",
    model: "imagegen-skill",
    status: "available_for_existing_artifacts",
    authMode: "codex_session",
    supports: ["inspect", "reuse-artifact"],
    proofArtifacts: ["artifact path", "manifest hash", "visual review receipt"],
    availability: {
      claim: "Codex can inspect or reuse existing image artifacts in this local session.",
      localStatus: "existing_artifacts_only",
      runActionAvailable: false,
      officialSources: [],
    },
  },
  {
    id: "local-request-draft",
    label: "Local request draft",
    providerId: "local-request-draft",
    model: "manual-handoff",
    status: "draft_only",
    authMode: "none",
    supports: ["generate", "edit", "mask", "handoff"],
    proofArtifacts: ["request payload", "mask geometry", "reference inventory"],
    availability: {
      claim: "Local draft mode prepares a provider request payload only.",
      localStatus: "draft_only",
      runActionAvailable: false,
      officialSources: [],
    },
  },
];

export const IMAGE_STUDIO_MASK_MODES = [
  { id: "replace", label: "Replace region" },
  { id: "preserve", label: "Preserve region" },
  { id: "extend", label: "Extend canvas" },
];

export function getProviderRoute(routeId) {
  return (
    IMAGE_STUDIO_PROVIDER_ROUTES.find(route => route.id === routeId) ||
    IMAGE_STUDIO_PROVIDER_ROUTES[0]
  );
}

export function getImageGenerationRouteStatus(route, options = {}) {
  const selected = route || getProviderRoute(options.routeId);
  const availability = selected.availability || {};
  const capability =
    selected.id === "openai-gpt-image-2" && options.capability && typeof options.capability === "object"
      ? options.capability
      : null;
  const hasAuth = Boolean(options.openAIReady || options.providerAuthReady);
  const runActionAvailable = capability
    ? Boolean(capability.runActionAvailable || capability.readyForRealRun)
    : Boolean(availability.runActionAvailable && hasAuth);
  const needsConnector =
    selected.status === "needs_connector" ||
    availability.localStatus === "connector_required";
  const localStatus = capability
    ? capability.providerStatus === "available"
      ? "provider_ready"
      : capability.blockedReason || "provider_blocked"
    : availability.localStatus || selected.status;
  return {
    routeId: selected.id,
    providerId: capability?.providerId || selected.providerId,
    model: capability?.model || selected.model,
    localStatus,
    runActionAvailable,
    readyForRealRun: runActionAvailable,
    handoffReady: selected.status !== "blocked",
    needsConnector: capability ? false : needsConnector,
    needsAuth: capability ? capability.blockedReason === "codex_auth_missing" : selected.authMode !== "none" && !hasAuth,
    claim: availability.claim || "",
    officialSources: Array.isArray(availability.officialSources)
      ? availability.officialSources
      : [],
    capability,
    blockedReason: capability?.blockedReason || "",
    message: capability?.message || "",
    checks: Array.isArray(capability?.checks) ? capability.checks : [],
    proofLimit: runActionAvailable
      ? "A real provider run must still return a provider receipt, output manifest, and artifact hash."
      : capability?.message || "This local surface can prepare and validate a request draft, but it has not completed a provider image run.",
  };
}

export function formatBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function createReferenceAssetFromFile(file, options = {}) {
  return {
    id: options.id || makeId("ref"),
    name: String(file?.name || "untitled-reference"),
    mime: String(file?.type || "application/octet-stream"),
    size: Number(file?.size || 0),
    role: options.role || "visual reference",
    influence: Number.isFinite(Number(options.influence)) ? Number(options.influence) : 0.55,
    createdAt: options.createdAt || nowIso(),
    previewUrl: options.previewUrl || "",
    persisted: false,
  };
}

export function summarizeReferenceAsset(asset = {}) {
  return {
    id: String(asset.id || ""),
    name: String(asset.name || "untitled-reference"),
    mime: String(asset.mime || "application/octet-stream"),
    size: Number(asset.size || 0),
    role: String(asset.role || "visual reference"),
    influence: Math.min(1, Math.max(0, Number(asset.influence) || 0)),
    persisted: Boolean(asset.persisted),
  };
}

export function buildChromaKeyProof(project = {}) {
  const chromaKey = normalizeProject(project).chromaKey || {};
  const keyColor = String(chromaKey.keyColor || "").trim();
  const hasColor = /^#[0-9a-f]{6}$/i.test(keyColor);
  const tolerance = Math.max(0, Math.min(100, Number(chromaKey.tolerance) || 0));
  const spillCleanup = Math.max(0, Math.min(100, Number(chromaKey.spillCleanup) || 0));
  const edgeFeather = Math.max(0, Math.min(64, Number(chromaKey.edgeFeather) || 0));
  const enabled = Boolean(chromaKey.enabled);
  const ready = enabled && hasColor && tolerance > 0;
  const replacementIntent = String(chromaKey.replacementIntent || "");
  const hasReplacementIntent = replacementIntent.trim().length > 0;
  const matteStrength = ready ? Math.min(96, Math.max(8, Math.round(tolerance * 1.45 + spillCleanup * 0.28))) : 0;
  const edgeRisk =
    !ready ? "blocked" :
      edgeFeather < 6 ? "hard_edge_risk" :
        spillCleanup < 24 ? "spill_risk" :
          tolerance > 68 ? "over_key_risk" :
            "controlled";
  const qaChecklist = [
    {
      id: "key-color-sampled",
      label: "Key color sampled",
      status: enabled && hasColor ? "ready" : "blocked",
      detail: hasColor ? `${keyColor} selected for the matte key.` : "Choose a valid six-digit key color.",
    },
    {
      id: "tolerance-window",
      label: "Tolerance window",
      status: tolerance > 0 ? "ready" : "blocked",
      detail: tolerance > 0 ? `${tolerance}% key tolerance recorded.` : "Set tolerance above zero before handoff.",
    },
    {
      id: "spill-cleanup",
      label: "Spill cleanup",
      status: spillCleanup > 0 ? "ready" : "planned",
      detail: spillCleanup > 0 ? `${spillCleanup}% suppression planned for green edge spill.` : "No spill suppression is planned.",
    },
    {
      id: "edge-feather",
      label: "Edge feather",
      status: edgeFeather > 0 ? "ready" : "planned",
      detail: edgeFeather > 0 ? `${edgeFeather}px soft edge planned.` : "No matte edge softening is planned.",
    },
    {
      id: "background-replacement",
      label: "Background replacement",
      status: hasReplacementIntent ? "ready" : "empty",
      detail: hasReplacementIntent ? replacementIntent : "No transparent/export replacement intent recorded.",
    },
    {
      id: "comparison-artifact",
      label: "Comparison artifact",
      status: "planned",
      detail: "Attach before/after image, provider receipt, and artifact hash after a real run.",
    },
  ];
  return {
    enabled,
    ready,
    keyColor,
    tolerance,
    spillCleanup,
    edgeFeather,
    matteMode: String(chromaKey.matteMode || "remove_background"),
    replacementIntent,
    proofLabels: Array.isArray(chromaKey.proofLabels) ? chromaKey.proofLabels : [],
    matteStrength,
    edgeRisk,
    qaChecklist,
    exportStatus: ready
      ? hasReplacementIntent
        ? "Transparent export plan ready; provider proof still required."
        : "Matte settings are ready, but replacement/export intent is missing."
      : "Matte proof cannot be handed off until key color and tolerance are valid.",
    providerInstruction: enabled
      ? `Use chroma key ${keyColor || "unset"} with tolerance ${tolerance}, spill cleanup ${spillCleanup}, and ${edgeFeather}px edge feather before replacement.`
      : "Chroma-key matte preparation is disabled for this draft.",
    status: ready ? "ready" : enabled ? "blocked" : "empty",
    detail: ready
      ? `${keyColor} key, ${tolerance}% tolerance, ${spillCleanup}% spill cleanup, ${edgeFeather}px feather`
      : enabled
        ? "Enable a valid six-digit key color and non-zero tolerance."
        : "Chroma-key matte preparation is disabled.",
  };
}

export function buildProofArtifactPlan(project, route, referenceAssets = [], options = {}) {
  const operation = options.operation || project?.prompt?.mode || "edit";
  const hasMask = Boolean(project?.selection?.visible);
  const hasHistory = Array.isArray(project?.history) && project.history.length > 0;
  const annotations = project?.annotationReadiness || {};
  const annotationCount =
    (Array.isArray(annotations.pins) ? annotations.pins.length : 0) +
    (Array.isArray(annotations.rectangles) ? annotations.rectangles.length : 0) +
    (Array.isArray(annotations.comments) ? annotations.comments.length : 0);
  const routeArtifacts = Array.isArray(route?.proofArtifacts) ? route.proofArtifacts : [];
  const chromaKeyProof = buildChromaKeyProof(project);

  return [
    {
      id: "request-manifest",
      label: "Request manifest",
      status: "ready",
      detail: `${operation} payload with prompt, canvas, provider, layer, and route metadata`,
    },
    {
      id: "reference-inventory",
      label: "Reference inventory",
      status: referenceAssets.length > 0 ? "ready" : "empty",
      detail: `${referenceAssets.length} local reference asset${referenceAssets.length === 1 ? "" : "s"}`,
    },
    {
      id: "mask-geometry",
      label: "Mask geometry",
      status: hasMask ? "ready" : "empty",
      detail: hasMask ? "Visible selected region with feather value" : "No selected region is visible",
    },
    {
      id: "history-link",
      label: "History link",
      status: hasHistory ? "ready" : "empty",
      detail: hasHistory ? "Existing artifact history is available for comparison" : "No generated artifact history yet",
    },
    {
      id: "annotation-review",
      label: "Annotation review",
      status: annotationCount > 0 ? "ready" : "empty",
      detail:
        annotationCount > 0
          ? `${annotationCount} annotation marker${annotationCount === 1 ? "" : "s"} captured for review`
          : "No annotation pins, rectangles, or comments are attached",
    },
    {
      id: "chroma-key-matte",
      label: "Chroma-key matte",
      status: chromaKeyProof.status,
      detail: chromaKeyProof.detail,
    },
    ...routeArtifacts.map((label, index) => ({
      id: `route-artifact-${index + 1}`,
      label,
      status: route?.status === "draft_only" ? "planned" : "requires_provider",
      detail: "Created after a real provider run or artifact import",
    })),
  ];
}

export function countImageAnnotations(annotationReadiness = {}) {
  const pins = Array.isArray(annotationReadiness.pins) ? annotationReadiness.pins : [];
  const rectangles = Array.isArray(annotationReadiness.rectangles) ? annotationReadiness.rectangles : [];
  const layers = Array.isArray(annotationReadiness.layers) ? annotationReadiness.layers : [];
  const comments = Array.isArray(annotationReadiness.comments) ? annotationReadiness.comments : [];
  return {
    pins: pins.length,
    rectangles: rectangles.length,
    layers: layers.length,
    comments: comments.length,
    total: pins.length + rectangles.length + comments.length,
  };
}

export function buildImageStudioProofReview(project, draft = null, options = {}) {
  const normalized = normalizeProject(project);
  const route = options.route || getProviderRoute(options.routeId || draft?.route?.id || normalized.provider?.routeId);
  const routeStatus = getImageGenerationRouteStatus(route, options);
  const references = Array.isArray(options.referenceAssets)
    ? options.referenceAssets
    : Array.isArray(draft?.references)
      ? draft.references
      : [];
  const annotationCounts = countImageAnnotations(normalized.annotationReadiness);
  const realHistory = normalized.history.filter(isRealImageSession);
  const validation = draft ? validateImageStudioRequestDraft(draft) : { ok: false, issues: ["No request draft prepared"] };
  const focusedHistoryId = normalized.focusedHistoryId || realHistory[0]?.id || "";
  const chromaKeyProof = buildChromaKeyProof(normalized);

  const checks = [
    {
      id: "draft-validity",
      label: "Draft validity",
      status: validation.ok ? "ready" : "blocked",
      detail: validation.ok ? "Provider payload validates locally." : validation.issues.join("; "),
    },
    {
      id: "preview-model",
      label: "Preview model",
      status: normalized.layers.length > 0 ? "ready" : "blocked",
      detail: `${normalized.layers.length} layer${normalized.layers.length === 1 ? "" : "s"} on ${normalized.canvas.width}x${normalized.canvas.height} canvas.`,
    },
    {
      id: "mask-coverage",
      label: "Mask coverage",
      status: normalized.selection?.visible ? "ready" : "empty",
      detail: normalized.selection?.visible
        ? `${Math.round(normalized.selection.width || 0)}x${Math.round(normalized.selection.height || 0)} selection, ${Math.round(normalized.selection.feather || 0)}px feather.`
        : "No visible mask region.",
    },
    {
      id: "annotation-coverage",
      label: "Annotation coverage",
      status: annotationCounts.total > 0 ? "ready" : "empty",
      detail: `${annotationCounts.pins} pins, ${annotationCounts.rectangles} rectangles, ${annotationCounts.comments} comments.`,
    },
    {
      id: "artifact-history",
      label: "Artifact history",
      status: realHistory.length > 0 ? "ready" : "empty",
      detail:
        realHistory.length > 0
          ? `${realHistory.length} real image artifact${realHistory.length === 1 ? "" : "s"} available for comparison.`
          : "No real provider artifact is available for comparison.",
    },
    {
      id: "chroma-key-readiness",
      label: "Green screen matte",
      status: chromaKeyProof.status,
      detail: chromaKeyProof.detail,
    },
  ];

  return {
    generatedAt: nowIso(),
    route: {
      id: route.id,
      label: route.label,
      status: route.status,
      model: route.model,
      availability: routeStatus,
    },
    preview: {
      canvas: {
        width: normalized.canvas.width,
        height: normalized.canvas.height,
      },
      layerCount: normalized.layers.length,
      visibleLayerCount: normalized.layers.filter(layer => layer.visible !== false).length,
      maskVisible: Boolean(normalized.selection?.visible),
      focusedHistoryId,
      hasRealArtifact: realHistory.length > 0,
    },
    references: {
      count: references.length,
      persistedCount: references.filter(asset => asset.persisted).length,
    },
    annotations: annotationCounts,
    chromaKey: chromaKeyProof,
    draft: {
      id: draft?.id || "",
      status: draft?.status || "not_prepared",
      valid: validation.ok,
      issues: validation.issues,
    },
    checks,
    readyForProviderHandoff: validation.ok && checks.every(check => check.status !== "blocked"),
    imageGenerationRouteStatus: routeStatus,
    noGenerationClaim:
      "This proof review describes local preview, annotation, and request readiness only. It is not a provider completion receipt.",
  };
}

export function buildImageBreakdownWorkflow(project, draft = null, options = {}) {
  const normalized = normalizeProject(project);
  const review = buildImageStudioProofReview(normalized, draft, options);
  const routeStatus = review.imageGenerationRouteStatus;
  const promptText = String(normalized.prompt?.text || "").trim();
  const styleText = String(normalized.prompt?.style || "").trim();
  const hasPromptIntent = promptText.length >= 24 && styleText.length >= 8;
  const hasReferences = review.references.count > 0 || review.preview.hasRealArtifact;
  const hasMask = Boolean(normalized.selection?.visible);
  const matteReady = Boolean(review.chromaKey.ready);
  const hasAnnotations = review.annotations.total > 0;
  const providerReceiptReady = Boolean(routeStatus.readyForRealRun && routeStatus.runActionAvailable);
  const stages = [
    {
      id: "source-intake",
      label: "Source intake",
      status: hasReferences ? "ready" : "needs_input",
      detail: hasReferences
        ? `${review.references.count} reference${review.references.count === 1 ? "" : "s"} and ${review.preview.hasRealArtifact ? "real artifact history" : "no history"} available.`
        : "Attach a reference, served artifact, or real history item before claiming visual grounding.",
      evidence: review.preview.hasRealArtifact ? "history artifact" : review.references.count ? "reference inventory" : "missing source",
    },
    {
      id: "region-plan",
      label: "Region plan",
      status: hasMask ? "ready" : "needs_input",
      detail: hasMask
        ? `${Math.round(normalized.selection.width || 0)}x${Math.round(normalized.selection.height || 0)} mask with ${Math.round(normalized.selection.feather || 0)}px feather.`
        : "Select a visible region or explicitly run full-canvas generation.",
      evidence: "mask geometry",
    },
    {
      id: "matte-quality",
      label: "Matte quality",
      status: matteReady ? review.chromaKey.edgeRisk === "controlled" ? "ready" : "review" : "blocked",
      detail: review.chromaKey.exportStatus,
      evidence: "chroma-key matte checklist",
    },
    {
      id: "prompt-intent",
      label: "Prompt intent",
      status: hasPromptIntent ? "ready" : "needs_input",
      detail: hasPromptIntent
        ? `${promptText.length} prompt chars with style notes and preserve-composition ${normalized.prompt.preserveComposition ? "on" : "off"}.`
        : "Write a concrete prompt and style direction before provider handoff.",
      evidence: "prompt, negative prompt, style, strength",
    },
    {
      id: "review-markup",
      label: "Review markup",
      status: hasAnnotations ? "ready" : "optional",
      detail: hasAnnotations
        ? `${review.annotations.total} annotation marker${review.annotations.total === 1 ? "" : "s"} will travel with the proof packet.`
        : "No annotations attached; acceptable for simple matte tasks but weaker for image breakdown.",
      evidence: "annotation pins, rectangles, comments",
    },
    {
      id: "provider-route",
      label: "Provider route",
      status: providerReceiptReady ? "ready" : "draft_only",
      detail: providerReceiptReady
        ? "A provider run action is available; require receipt, manifest, and artifact hash after execution."
        : routeStatus.proofLimit,
      evidence: routeStatus.model,
    },
  ];
  const blockedStages = stages.filter(stage => ["blocked", "needs_input"].includes(stage.status));
  const readyStages = stages.filter(stage => stage.status === "ready");
  const reviewStages = stages.filter(stage => ["review", "optional", "draft_only"].includes(stage.status));
  const nextStage = blockedStages[0] || reviewStages[0] || stages[stages.length - 1];
  return {
    generatedAt: nowIso(),
    stageCount: stages.length,
    readyCount: readyStages.length,
    blockedCount: blockedStages.length,
    reviewCount: reviewStages.length,
    handoffState:
      blockedStages.length === 0 && review.readyForProviderHandoff
        ? providerReceiptReady
          ? "provider_run_ready"
          : "draft_handoff_ready"
        : "needs_breakdown",
    nextAction: nextStage
      ? `${nextStage.label}: ${nextStage.detail}`
      : "Review provider receipt, output manifest, and artifact hash after the run.",
    stages,
  };
}

export function buildImageStudioRequestDraft(project, options = {}) {
  const route = getProviderRoute(options.routeId || project?.provider?.routeId);
  const operation = options.operation || project?.prompt?.mode || "edit";
  const references = (Array.isArray(options.referenceAssets) ? options.referenceAssets : []).map(
    summarizeReferenceAsset,
  );
  const providerPayload = projectToProviderPayload(
    {
      ...project,
      provider: {
        ...(project?.provider || {}),
        routeId: route.id,
        id: route.providerId,
        model: route.model,
      },
    },
    operation,
    options.payloadOptions || {},
  );
  const draft = {
    id: options.id || makeId("image-request"),
    createdAt: options.createdAt || nowIso(),
    status: "draft_only",
    route: {
      id: route.id,
      label: route.label,
      providerId: route.providerId,
      model: route.model,
      status: route.status,
      authMode: route.authMode,
      supports: route.supports,
      availability: getImageGenerationRouteStatus(route, options),
    },
    operation,
    references,
    mask: {
      mode: options.maskMode || "replace",
      selection: providerPayload.inputs.editRegion,
    },
    chromaKey: buildChromaKeyProof(project),
    payload: providerPayload,
    proofArtifacts: buildProofArtifactPlan(project, route, references, { operation }),
    noGenerationReason:
      "This surface prepares a provider request and proof plan. It does not call an image provider until a real connector is wired.",
  };
  draft.proofReview = buildImageStudioProofReview(project, draft, { referenceAssets: references, route });
  draft.breakdownWorkflow = buildImageBreakdownWorkflow(project, draft, { referenceAssets: references, route });
  return draft;
}

export function buildImageStudioOperationPayload(draft = {}) {
  const payload = draft.payload && typeof draft.payload === "object" ? draft.payload : {};
  const route = draft.route && typeof draft.route === "object" ? draft.route : {};
  return {
    ...payload,
    requestId: draft.id || payload.requestId || makeId("image-request"),
    operation: draft.operation || payload.operation || "edit",
    providerId: route.providerId || payload.providerId || payload.provider?.id || "",
    provider: {
      ...(payload.provider && typeof payload.provider === "object" ? payload.provider : {}),
      id: route.providerId || payload.provider?.id || "",
      model: route.model || payload.provider?.model || "",
      routeId: route.id || payload.provider?.routeId || "",
    },
    route: {
      id: route.id || "",
      label: route.label || "",
      model: route.model || "",
      authMode: route.authMode || "",
      status: route.status || "",
    },
    mask: draft.mask || {},
    chromaKey: draft.chromaKey || payload.chromaKey || {},
    proofReview: draft.proofReview || {},
    breakdownWorkflow: draft.breakdownWorkflow || {},
    proofArtifacts: Array.isArray(draft.proofArtifacts) ? draft.proofArtifacts : [],
    noGenerationReason: draft.noGenerationReason || "",
  };
}

export function validateImageStudioRequestDraft(draft = {}) {
  const issues = [];
  if (!draft.id) issues.push("Missing draft id");
  if (!draft.route?.id) issues.push("Missing provider route");
  if (!draft.payload?.prompt?.text?.trim()) issues.push("Missing prompt text");
  if (!draft.payload?.canvas?.width || !draft.payload?.canvas?.height) {
    issues.push("Missing canvas dimensions");
  }
  if (!Array.isArray(draft.proofArtifacts) || draft.proofArtifacts.length === 0) {
    issues.push("Missing proof artifact plan");
  }
  return {
    ok: issues.length === 0,
    issues,
  };
}
