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
    label: "OpenAI image route",
    providerId: "codex_subscription_gpt_image2",
    model: "gpt-image-2",
    status: "needs_connector",
    authMode: "external",
    supports: ["generate", "edit", "mask"],
    proofArtifacts: ["request manifest", "provider receipt", "output manifest", "artifact hash"],
  },
  {
    id: "codex-imagegen-skill",
    label: "Codex ImageGen skill",
    providerId: "codex-imagegen-skill",
    model: "imagegen-skill",
    status: "available_for_existing_artifacts",
    authMode: "codex_session",
    supports: ["inspect", "reuse-artifact"],
    proofArtifacts: ["artifact path", "manifest hash", "visual review receipt"],
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
  const references = Array.isArray(options.referenceAssets)
    ? options.referenceAssets
    : Array.isArray(draft?.references)
      ? draft.references
      : [];
  const annotationCounts = countImageAnnotations(normalized.annotationReadiness);
  const realHistory = normalized.history.filter(isRealImageSession);
  const validation = draft ? validateImageStudioRequestDraft(draft) : { ok: false, issues: ["No request draft prepared"] };
  const focusedHistoryId = normalized.focusedHistoryId || realHistory[0]?.id || "";

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
  ];

  return {
    generatedAt: nowIso(),
    route: {
      id: route.id,
      label: route.label,
      status: route.status,
      model: route.model,
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
    draft: {
      id: draft?.id || "",
      status: draft?.status || "not_prepared",
      valid: validation.ok,
      issues: validation.issues,
    },
    checks,
    readyForProviderHandoff: validation.ok && checks.every(check => check.status !== "blocked"),
    noGenerationClaim:
      "This proof review describes local preview, annotation, and request readiness only. It is not a provider completion receipt.",
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
    },
    operation,
    references,
    mask: {
      mode: options.maskMode || "replace",
      selection: providerPayload.inputs.editRegion,
    },
    payload: providerPayload,
    proofArtifacts: buildProofArtifactPlan(project, route, references, { operation }),
    noGenerationReason:
      "This surface prepares a provider request and proof plan. It does not call an image provider until a real connector is wired.",
  };
  draft.proofReview = buildImageStudioProofReview(project, draft, { referenceAssets: references, route });
  return draft;
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
