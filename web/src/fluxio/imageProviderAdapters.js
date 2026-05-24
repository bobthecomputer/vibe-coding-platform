import { addHistoryEntry, makeId, nowIso, projectToProviderPayload } from "./imagePlaygroundState.js";

export const QUEUE_TIMELINE_STAGES = [
  "queued",
  "provider accepted",
  "generating",
  "artifact written",
  "layer handoff",
  "verified",
];

const BUILT_IN_IMAGE_PROVIDER_ADAPTERS = [
  {
    id: "codex_subscription_gpt_image2",
    name: "GPT-Image-2 via Codex subscription",
    model: "gpt-image-2",
    statusLabel: "Codex subscription route",
    description:
      "Runs OpenClaw image generation on the Codex subscription lane and only accepts strict provider/model route proof.",
    capabilities: ["generate", "edit", "composition", "region", "variations"],
    async request({ project, operation, payload, callBackend }) {
      if (typeof callBackend !== "function") {
        return createProviderBlockedResult(project, operation, "Web backend bridge is unavailable.");
      }
      try {
        const response = await callBackend("image_playground_operation_command", payload, {
          throwOnError: true,
        });
        if (response?.layer && response?.providerStatus === "available") {
          return {
            kind: "provider",
            provider: response.provider || "openai-codex",
            message: response.message || "Provider returned an editable layer.",
            layer: normalizeGeneratedLayer(response.layer, project),
            meta: {
              ...response,
              providerStatus: response.providerStatus || "available",
              outputArtifactPath: response.outputArtifactPath || response.imagePath || "",
              previewUrl: response.previewUrl || response.artifactUrl || "",
              manifestPath: response.manifestPath || "",
              manifestUrl: response.manifestUrl || "",
              receipt: response.receipt || {},
            },
          };
        }
        if (response?.status === "unavailable" || response?.providerStatus === "blocked") {
          return createProviderBlockedResult(
            project,
            operation,
            response.message || "Codex subscription image generation is unavailable on this runtime.",
            response,
          );
        }
      } catch (error) {
        return createProviderBlockedResult(project, operation, String(error?.message || error || "Provider request failed."));
      }
      return createProviderBlockedResult(project, operation, "Provider did not return Codex subscription route proof.");
    },
  },
  {
    id: "local-composition-draft",
    name: "Local composition draft",
    model: "canvas-only",
    statusLabel: "Offline fallback",
    description:
      "Creates editable draft layers locally so the canvas workflow remains usable without a remote image provider.",
    capabilities: ["generate", "edit", "composition", "region"],
    async request({ project, operation }) {
      return createLocalDraftResult(
        project,
        operation,
        "Using local composition draft. Connect Codex GPT-Image2 when the runtime exposes image generation.",
      );
    },
  },
];

const imageProviderRegistry = [...BUILT_IN_IMAGE_PROVIDER_ADAPTERS];

export const IMAGE_PROVIDER_ADAPTERS = imageProviderRegistry;

function tinyHash(value) {
  const source = String(value || "");
  let hash = 2166136261;
  for (let index = 0; index < source.length; index += 1) {
    hash ^= source.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return Math.abs(hash >>> 0).toString(16).padStart(8, "0").slice(0, 8);
}

export function buildIssueThreadRef(receiptHash, requestId) {
  const hash = String(receiptHash || "unknown").trim() || "unknown";
  const request = String(requestId || "pending-request-id").trim() || "pending-request-id";
  return `${hash}:${request}`;
}

export function snapshotOverlayAnnotations(project, threadRef = "") {
  const source = project?.annotationReadiness || {};
  const normalizePoint = pin => ({
    id: pin?.id || makeId("pin"),
    x: Number(pin?.x || 0),
    y: Number(pin?.y || 0),
    comment: String(pin?.comment || ""),
    threadRef: pin?.threadRef || threadRef || "",
  });
  const normalizeRect = rect => ({
    id: rect?.id || makeId("rect"),
    x: Number(rect?.x || 0),
    y: Number(rect?.y || 0),
    width: Number(rect?.width || rect?.w || 0),
    height: Number(rect?.height || rect?.h || 0),
    comment: String(rect?.comment || ""),
    threadRef: rect?.threadRef || threadRef || "",
  });
  return {
    canvasWidth: Number(project?.canvas?.width || 1),
    canvasHeight: Number(project?.canvas?.height || 1),
    pins: Array.isArray(source.pins) ? source.pins.map(normalizePoint).slice(0, 24) : [],
    rectangles: Array.isArray(source.rectangles) ? source.rectangles.map(normalizeRect).slice(0, 24) : [],
  };
}

export function registerImageProviderAdapter(adapter) {
  if (!adapter || typeof adapter !== "object") {
    throw new TypeError("Image provider adapter must be an object.");
  }
  const id = String(adapter.id || "").trim();
  if (!id) {
    throw new TypeError("Image provider adapter requires an id.");
  }
  if (imageProviderRegistry.some(provider => provider.id === id)) {
    throw new Error(`Image provider adapter already registered: ${id}`);
  }
  const request = typeof adapter.request === "function"
    ? adapter.request
    : async ({ project, operation }) => createLocalDraftResult(project, operation, `${adapter.name || id} has no request transport configured yet.`);
  const normalized = {
    statusLabel: "Provider adapter",
    description: "Modular image provider adapter.",
    capabilities: [],
    ...adapter,
    id,
    request,
  };
  imageProviderRegistry.push(normalized);
  return normalized;
}

export function getProviderAdapter(providerId) {
  return imageProviderRegistry.find(provider => provider.id === providerId) || imageProviderRegistry[0];
}

export async function requestProviderOperation(project, operation, { callBackend, snapshotDataUrl, imagePluginMode = false } = {}) {
  const basePayload = projectToProviderPayload(project, operation);
  const requestId = makeId("imgreq");
  const queuedAt = nowIso();
  const providerId = imagePluginMode ? "codex_subscription_gpt_image2" : project.provider.id;
  const payload = {
    ...basePayload,
    requestId,
    providerId,
    snapshotDataUrl: imagePluginMode ? "" : snapshotDataUrl,
    renderMode: imagePluginMode ? "provider-image" : "composition-snapshot",
    inputs: {
      ...(basePayload.inputs || {}),
      snapshotDataUrl: imagePluginMode ? "" : snapshotDataUrl || "",
    },
  };
  const adapter = imagePluginMode ? getProviderAdapter("codex_subscription_gpt_image2") : getProviderAdapter(project.provider.id);
  const startedAt = nowIso();
  const result = await adapter.request({ project, operation, payload, callBackend, snapshotDataUrl });
  const completedAt = nowIso();
  const requestTimeline = {
    queuedAt,
    startedAt: queuedAt,
    completedAt,
    durationMs: Math.max(0, new Date(completedAt).getTime() - new Date(queuedAt).getTime()),
  };
  const mergedMeta = {
    ...(result?.meta || {}),
    requestId: result?.meta?.requestId || requestId,
    providerStatus: result?.meta?.providerStatus || (result?.kind === "provider" ? "available" : "blocked"),
    outputArtifactPath: result?.meta?.outputArtifactPath || "",
    requestTimeline: {
      ...requestTimeline,
      ...(result?.meta?.requestTimeline || {}),
    },
    queueTimeline: result?.meta?.queueTimeline || buildQueueTimeline({ queuedAt, startedAt, completedAt }),
    layerHandoff: {
      layerId: result?.layer?.id || "",
      layerName: result?.layer?.name || "",
      stage: result?.layer ? "layer_ready" : "no_layer",
      at: completedAt,
      ...(result?.meta?.layerHandoff || {}),
    },
  };
  const promptHash = mergedMeta?.receipt?.promptHash || tinyHash(project?.prompt?.text || payload?.prompt?.text || "");
  mergedMeta.receipt = {
    ...(mergedMeta.receipt || {}),
    promptHash,
  };
  if (mergedMeta.providerStatus !== "available") {
    mergedMeta.receipt = {
      ...mergedMeta.receipt,
      failureReason: mergedMeta.receipt.failureReason || "Codex subscription route unavailable",
      promptEvidence: project?.prompt?.text || "",
      specEvidence: payload?.compositionIntent || "",
    };
  }

  if (result?.layer) {
    return {
      ...result,
      provider: result.provider || adapter.name,
      layer: normalizeGeneratedLayer(result.layer, project),
      meta: mergedMeta,
    };
  }

  const fallbackResult = result || createLocalDraftResult(project, operation, `${adapter.name} did not return an editable layer.`);
  return {
    ...fallbackResult,
    meta: {
      ...mergedMeta,
      ...(fallbackResult?.meta || {}),
    },
  };
}

function normalizeGeneratedLayer(layer, project) {
  return {
    id: layer.id || makeId("layer-provider"),
    name: layer.name || "Provider result",
    type: layer.src ? "image" : "shape",
    visible: true,
    locked: false,
    opacity: 1,
    blendMode: "normal",
    x: Number(layer.x ?? 0),
    y: Number(layer.y ?? 0),
    width: Number(layer.width ?? project.canvas.width),
    height: Number(layer.height ?? project.canvas.height),
    rotation: Number(layer.rotation || 0),
    src: layer.src || "",
    fill: layer.fill || "linear-gradient(135deg, rgba(255,255,255,.26), rgba(214,168,79,.22))",
    radius: layer.radius || 24,
    promptRole: layer.promptRole || "provider output",
  };
}

function buildQueueTimeline({ queuedAt, startedAt, completedAt }) {
  return [
    { stage: "queued", at: queuedAt, severity: "info", recoveryAction: "Monitor queue" },
    { stage: "provider accepted", at: startedAt, severity: "info", recoveryAction: "Check provider status" },
    { stage: "generating", at: startedAt, severity: "info", recoveryAction: "Wait for generation" },
    { stage: "artifact written", at: completedAt, severity: "info", recoveryAction: "Open artifact preview" },
    { stage: "layer handoff", at: completedAt, severity: "info", recoveryAction: "Apply output as layer" },
    { stage: "verified", at: completedAt, severity: "good", recoveryAction: "Publish receipt evidence" },
  ];
}

function createProviderBlockedResult(project, operation, message, response = null) {
  return {
    kind: "provider-blocked",
    status: "unavailable",
    provider: "openai-codex",
    message,
    meta: {
      ...(response || {}),
      providerStatus: "blocked",
      blockedReason: response?.blockedReason || "provider_unavailable",
    },
  };
}

export function createLocalDraftResult(project, operation, message) {
  const selected = project.layers.find(layer => layer.id === project.selectedLayerId) || project.layers[1] || project.layers[0];
  const draftPng = createLocalDraftPng(project, operation, selected);
  return {
    kind: "local-draft",
    provider: "Local composition draft",
    message,
    layer: {
      id: makeId("layer-draft"),
      name: operation === "edit" ? "Edited composition draft" : "Generated composition draft",
      type: "image",
      visible: true,
      locked: false,
      opacity: 0.92,
      blendMode: "normal",
      x: 0,
      y: 0,
      width: project.canvas.width,
      height: project.canvas.height,
      rotation: 0,
      src: draftPng,
      promptRole: "draft output from modular provider adapter",
    },
  };
}

function createLocalDraftPng(project, operation, selected) {
  const width = Math.max(320, Math.min(2048, Number(project?.canvas?.width || 1024)));
  const height = Math.max(240, Math.min(2048, Number(project?.canvas?.height || 1024)));
  if (typeof document === "undefined" || typeof document.createElement !== "function") {
    return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=";
  }
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=";
  }
  const palette = operation === "edit" ? ["#111414", "#d0aa52", "#72d36f"] : ["#081111", "#31535a", "#d0aa52"];
  const gradient = ctx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, palette[0]);
  gradient.addColorStop(0.58, palette[1]);
  gradient.addColorStop(1, palette[2]);
  ctx.fillStyle = "#050606";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = gradient;
  roundedRect(ctx, Math.round(width * 0.09), Math.round(height * 0.1), Math.round(width * 0.82), Math.round(height * 0.68), Math.round(width * 0.055));
  ctx.fill();
  const halo = ctx.createRadialGradient(width * 0.52, height * 0.36, 0, width * 0.52, height * 0.36, Math.max(width, height) * 0.36);
  halo.addColorStop(0, "rgba(238,242,236,0.58)");
  halo.addColorStop(1, "rgba(238,242,236,0)");
  ctx.fillStyle = halo;
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "rgba(238,242,236,0.42)";
  ctx.lineWidth = Math.max(2, width * 0.003);
  roundedRect(
    ctx,
    Number(selected?.x || width * 0.3),
    Number(selected?.y || height * 0.3),
    Number(selected?.width || width * 0.24),
    Number(selected?.height || height * 0.2),
    Math.max(12, width * 0.02),
  );
  ctx.stroke();
  ctx.fillStyle = "rgba(238,242,236,0.74)";
  ctx.font = `${Math.max(18, Math.round(width * 0.026))}px system-ui, sans-serif`;
  ctx.textAlign = "center";
  ctx.fillText(`Composition draft · ${operation}`, width / 2, height * 0.88);
  return canvas.toDataURL("image/png");
}

function roundedRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + width, y, x + width, y + height, r);
  ctx.arcTo(x + width, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + width, y, r);
  ctx.closePath();
}

export function applyProviderResult(project, result, operation) {
  const nextLayers = result.layer ? [...project.layers, result.layer] : project.layers;
  const nextProject = {
    ...project,
    selectedLayerId: result.layer?.id || project.selectedLayerId,
    layers: nextLayers,
    updatedAt: nowIso(),
  };
  const receiptHash = result?.meta?.receipt?.promptHash || tinyHash(project.prompt.text || "");
  const requestId = result?.meta?.requestId || "pending-request-id";
  const threadRef = buildIssueThreadRef(receiptHash, requestId);
  const annotationSnapshot = snapshotOverlayAnnotations(project, threadRef);
  return addHistoryEntry(nextProject, {
    title: operation === "edit" ? "Composition edit" : "Image generation",
    prompt: project.prompt.text,
    provider: result.provider,
    providerId: project.provider.id,
    status: result.kind === "provider" ? "generated" : "provider_blocked",
    note: result.message,
    requestId: result?.meta?.requestId || "",
    providerStatus: result?.meta?.providerStatus || (result.kind === "provider" ? "available" : "blocked"),
    outputArtifactPath: result?.meta?.outputArtifactPath || "",
    previewSrc: result?.meta?.previewUrl || result?.layer?.src || "",
    manifestPath: result?.meta?.manifestPath || "",
    manifestUrl: result?.meta?.manifestUrl || "",
    requestTimeline: result?.meta?.requestTimeline || {},
    queueTimeline: result?.meta?.queueTimeline || [],
    layerHandoff: result?.meta?.layerHandoff || {},
    receipt: result?.meta?.receipt || {},
    annotationSnapshot,
    issueThread: {
      id: threadRef,
      requestId,
      receiptHash,
      href: `#issue-thread-${encodeURIComponent(threadRef)}`,
    },
  });
}
