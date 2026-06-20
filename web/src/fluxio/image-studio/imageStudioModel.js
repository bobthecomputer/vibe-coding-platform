import {
  makeId,
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
    ...routeArtifacts.map((label, index) => ({
      id: `route-artifact-${index + 1}`,
      label,
      status: route?.status === "draft_only" ? "planned" : "requires_provider",
      detail: "Created after a real provider run or artifact import",
    })),
  ];
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
