import { useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle,
  ClipboardText,
  ClockCounterClockwise,
  FileImage,
  ImageSquare,
  Plus,
  ShieldCheck,
  SlidersHorizontal,
  Stack,
  Trash,
  WarningCircle,
} from "@phosphor-icons/react";

import {
  CANVAS_SIZE_PRESETS,
  IMAGE_TOOL_DEFINITIONS,
  addHistoryEntry,
  createLayerFromSelection,
  loadImageProject,
  normalizeProject,
  saveImageProject,
  updateLayerInProject,
} from "../imagePlaygroundState.js";
import {
  IMAGE_STUDIO_MASK_MODES,
  IMAGE_STUDIO_PROVIDER_ROUTES,
  IMAGE_STUDIO_STORAGE_KEY,
  buildImageBreakdownWorkflow,
  buildImageStudioOperationPayload,
  buildImageStudioProofReview,
  buildImageStudioRequestDraft,
  createReferenceAssetFromFile,
  formatBytes,
  getProviderRoute,
  validateImageStudioRequestDraft,
} from "./imageStudioModel.js";
import "./image-studio.css";

const EMPTY_SESSION = {
  routeId: "openai-gpt-image-2",
  maskMode: "replace",
  matteSourceId: "",
  referenceAssets: [],
};

const SYNTHETIC_CHROMA_SAMPLE_URL = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 240">
  <rect width="320" height="240" fill="#00ff66"/>
  <ellipse cx="160" cy="180" rx="76" ry="14" fill="#04351e" opacity=".38"/>
  <rect x="112" y="78" width="96" height="108" rx="30" fill="#eef2ec"/>
  <circle cx="148" cy="118" r="8" fill="#18201d"/>
  <circle cx="184" cy="118" r="8" fill="#18201d"/>
  <path d="M138 146c14 13 32 13 46 0" fill="none" stroke="#18201d" stroke-width="8" stroke-linecap="round"/>
  <path d="M118 92c18-30 70-34 90 0" fill="#d6a84f" opacity=".82"/>
</svg>
`)}`;

function loadStudioSession() {
  if (typeof window === "undefined") return EMPTY_SESSION;
  try {
    const raw = window.localStorage.getItem(IMAGE_STUDIO_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return {
      ...EMPTY_SESSION,
      ...(parsed && typeof parsed === "object" ? parsed : {}),
      routeId:
        new URLSearchParams(window.location.search).get("imageRoute") ||
        (parsed && typeof parsed === "object" ? parsed.routeId : "") ||
        EMPTY_SESSION.routeId,
      referenceAssets: Array.isArray(parsed?.referenceAssets) ? parsed.referenceAssets : [],
    };
  } catch {
    return EMPTY_SESSION;
  }
}

function saveStudioSession(session) {
  if (typeof window === "undefined") return;
  const serializable = {
    ...session,
    referenceAssets: (Array.isArray(session.referenceAssets) ? session.referenceAssets : []).map(asset => ({
      ...asset,
      previewUrl: "",
    })),
  };
  try {
    window.localStorage.setItem(IMAGE_STUDIO_STORAGE_KEY, JSON.stringify(serializable));
  } catch {
    return;
  }
}

function fieldId(name) {
  return `image-studio-${name}`;
}

function artifactBackendBaseUrl() {
  const configured =
    import.meta.env?.VITE_FLUXIO_BACKEND_URL ||
    globalThis.window?.__FLUXIO_BACKEND_URL__ ||
    "";
  return String(configured || "").trim().replace(/\/$/, "");
}

function artifactBackendHealthUrl() {
  return `${artifactBackendBaseUrl()}/health`;
}

function resolveImageStudioArtifactUrl(value) {
  const source = String(value || "").trim();
  if (!source) return "";
  if (/^(data:|blob:|https?:\/\/)/i.test(source)) return source;
  if (source.startsWith("/api/artifact")) return `${artifactBackendBaseUrl()}${source}`;
  const params = new URLSearchParams({ path: source });
  return `${artifactBackendBaseUrl()}/api/artifact?${params.toString()}`;
}

function imageUrlForRecord(record) {
  if (typeof record === "string") return resolveImageStudioArtifactUrl(record);
  return resolveImageStudioArtifactUrl(
    record?.artifactUrl ||
      record?.servedUrl ||
      record?.previewUrl ||
      record?.generatedPreview ||
      record?.previewSrc ||
      record?.outputPreview ||
      record?.imagePath ||
      record?.outputArtifactPath ||
      record?.artifactPath ||
      record?.path ||
      "",
  );
}

function imageLabelForRecord(record, fallback = "image artifact") {
  if (typeof record === "string") {
    return record.split(/[\\/]/).filter(Boolean).pop() || fallback;
  }
  return (
    record?.label ||
    record?.title ||
    record?.filename ||
    record?.artifactId ||
    record?.requestId ||
    imageLabelForRecord(record?.artifactPath || record?.path || "", fallback)
  );
}

function parseHexColor(value) {
  const match = String(value || "").trim().match(/^#?([0-9a-f]{6})$/i);
  if (!match) return null;
  const hex = match[1];
  return {
    r: Number.parseInt(hex.slice(0, 2), 16),
    g: Number.parseInt(hex.slice(2, 4), 16),
    b: Number.parseInt(hex.slice(4, 6), 16),
  };
}

function loadImageForCanvas(src) {
  return new Promise((resolve, reject) => {
    if (!src) {
      reject(new Error("No image source selected."));
      return;
    }
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("The selected image could not be loaded for local matte proof."));
    if (!String(src).startsWith("blob:") && !String(src).startsWith("data:")) {
      image.crossOrigin = "anonymous";
    }
    image.src = src;
  });
}

function renderChromaMattePreview({ image, proof, source }) {
  const key = parseHexColor(proof?.keyColor);
  if (!key || !proof?.ready) {
    throw new Error("Matte settings need a valid key color and non-zero tolerance.");
  }
  const maxSide = 420;
  const scale = Math.min(1, maxSide / Math.max(image.naturalWidth || image.width, image.naturalHeight || image.height));
  const width = Math.max(1, Math.round((image.naturalWidth || image.width) * scale));
  const height = Math.max(1, Math.round((image.naturalHeight || image.height) * scale));
  const canvas = document.createElement("canvas");
  const maskCanvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  maskCanvas.width = width;
  maskCanvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  const maskContext = maskCanvas.getContext("2d", { willReadFrequently: true });
  if (!context || !maskContext) {
    throw new Error("Canvas matte preview is unavailable in this browser.");
  }
  context.drawImage(image, 0, 0, width, height);
  const frame = context.getImageData(0, 0, width, height);
  const mask = maskContext.createImageData(width, height);
  const tolerance = Math.max(1, Math.min(100, Number(proof.tolerance) || 0));
  const threshold = 441.7 * (tolerance / 100);
  const softThreshold = threshold + Math.max(4, Number(proof.edgeFeather) || 0) * 1.9;
  const spillCleanup = Math.max(0, Math.min(1, Number(proof.spillCleanup) / 100 || 0));
  let removedPixels = 0;
  let softPixels = 0;
  for (let index = 0; index < frame.data.length; index += 4) {
    const red = frame.data[index];
    const green = frame.data[index + 1];
    const blue = frame.data[index + 2];
    const distance = Math.hypot(red - key.r, green - key.g, blue - key.b);
    let alpha = 255;
    if (distance <= threshold) {
      alpha = 0;
      removedPixels += 1;
    } else if (distance <= softThreshold) {
      alpha = Math.round(255 * ((distance - threshold) / Math.max(1, softThreshold - threshold)));
      softPixels += 1;
    }
    if (spillCleanup > 0 && green > red * 1.08 && green > blue * 1.08) {
      const average = Math.round((red + blue) / 2);
      frame.data[index + 1] = Math.round(green * (1 - spillCleanup) + average * spillCleanup);
    }
    frame.data[index + 3] = Math.min(frame.data[index + 3], alpha);
    mask.data[index] = alpha;
    mask.data[index + 1] = alpha;
    mask.data[index + 2] = alpha;
    mask.data[index + 3] = 255;
  }
  context.putImageData(frame, 0, 0);
  maskContext.putImageData(mask, 0, 0);
  const totalPixels = width * height;
  return {
    id: `matte-proof-${Date.now().toString(36)}`,
    createdAt: new Date().toISOString(),
    sourceId: source.id,
    sourceLabel: source.label,
    outputUrl: canvas.toDataURL("image/png"),
    maskUrl: maskCanvas.toDataURL("image/png"),
    width,
    height,
    removedPixels,
    softPixels,
    totalPixels,
    removedPercent: totalPixels ? Math.round((removedPixels / totalPixels) * 1000) / 10 : 0,
    softPercent: totalPixels ? Math.round((softPixels / totalPixels) * 1000) / 10 : 0,
    keyColor: proof.keyColor,
    tolerance: proof.tolerance,
    spillCleanup: proof.spillCleanup,
    edgeFeather: proof.edgeFeather,
  };
}

function StatusMark({ status }) {
  const ready = status === "ready";
  const empty = status === "empty";
  const blocked = status === "blocked";
  return (
    <span className={`image-studio-status-mark ${ready ? "is-ready" : empty ? "is-empty" : blocked ? "is-blocked" : "is-planned"}`}>
      {ready ? <CheckCircle size={16} weight="fill" /> : <WarningCircle size={16} weight="fill" />}
      <span>{status.replace(/_/g, " ")}</span>
    </span>
  );
}

function ProjectLayer({ layer, canvas }) {
  if (layer.visible === false) return null;
  const width = Number(canvas?.width || 1024);
  const height = Number(canvas?.height || 1024);
  const style = {
    left: `${(Number(layer.x || 0) / width) * 100}%`,
    top: `${(Number(layer.y || 0) / height) * 100}%`,
    width: `${(Number(layer.width || 1) / width) * 100}%`,
    height: `${(Number(layer.height || 1) / height) * 100}%`,
    transform: `rotate(${Number(layer.rotation || 0)}deg)`,
    opacity: Number(layer.opacity ?? 1),
    mixBlendMode: layer.blendMode || "normal",
    borderRadius: layer.radius ? `${layer.radius}px` : undefined,
    background: layer.src
      ? `url("${layer.src}") center / cover no-repeat`
      : layer.fill || "rgba(255,255,255,.24)",
  };
  return <div className="image-studio-canvas-layer" style={style} aria-hidden="true" />;
}

function SelectionOverlay({ selection, canvas, mode }) {
  if (!selection?.visible) return null;
  const width = Number(canvas?.width || 1024);
  const height = Number(canvas?.height || 1024);
  const style = {
    left: `${(Number(selection.x || 0) / width) * 100}%`,
    top: `${(Number(selection.y || 0) / height) * 100}%`,
    width: `${(Number(selection.width || 1) / width) * 100}%`,
    height: `${(Number(selection.height || 1) / height) * 100}%`,
  };
  return (
    <div className={`image-studio-selection is-${mode}`} style={style}>
      <span>Mask</span>
      <b>{Math.round(selection.feather || 0)}px feather</b>
    </div>
  );
}

function AnnotationOverlay({ annotations, canvas }) {
  const width = Number(canvas?.width || 1024);
  const height = Number(canvas?.height || 1024);
  const pins = Array.isArray(annotations?.pins) ? annotations.pins : [];
  const rectangles = Array.isArray(annotations?.rectangles) ? annotations.rectangles : [];
  return (
    <>
      {rectangles.map((rect, index) => {
        const style = {
          left: `${(Number(rect.x || 0) / width) * 100}%`,
          top: `${(Number(rect.y || 0) / height) * 100}%`,
          width: `${(Number(rect.width || 1) / width) * 100}%`,
          height: `${(Number(rect.height || 1) / height) * 100}%`,
        };
        return (
          <div className="image-studio-annotation-rect" style={style} key={rect.id || `rect-${index}`}>
            <span>{rect.label || rect.title || `Review ${index + 1}`}</span>
          </div>
        );
      })}
      {pins.map((pin, index) => {
        const style = {
          left: `${(Number(pin.x || 0) / width) * 100}%`,
          top: `${(Number(pin.y || 0) / height) * 100}%`,
        };
        return (
          <span className="image-studio-annotation-pin" style={style} key={pin.id || `pin-${index}`}>
            {index + 1}
          </span>
        );
      })}
    </>
  );
}

function ReferencePreview({ asset, onRemove }) {
  return (
    <li className="image-studio-reference-row">
      <div className="image-studio-reference-thumb">
        {asset.previewUrl ? <img src={asset.previewUrl} alt="" /> : <FileImage size={24} aria-hidden="true" />}
      </div>
      <div>
        <strong>{asset.name}</strong>
        <span>{asset.role} - {formatBytes(asset.size)}</span>
      </div>
      <button type="button" className="image-studio-icon-button" onClick={() => onRemove(asset.id)} aria-label={`Remove ${asset.name}`}>
        <Trash size={16} aria-hidden="true" />
      </button>
    </li>
  );
}

function HistoryRow({ item }) {
  return (
    <li className="image-studio-history-row">
      <div>
        <strong>{item.title || item.requestId || "Image artifact"}</strong>
        <span>{item.provider || item.providerId || "Provider"} - {item.status || "recorded"}</span>
      </div>
      <code>{item.receipt?.promptHash || item.requestId || "no receipt"}</code>
    </li>
  );
}

function GeneratedArtifactCard({ artifact }) {
  const imageUrl = imageUrlForRecord(artifact);
  const manifestUrl = artifact?.manifestUrl || "";
  const label = imageLabelForRecord(artifact, "Generated image artifact");
  const source = artifact?.provider || artifact?.source || artifact?.route || "served artifact";
  return (
    <article className="image-studio-generated-artifact">
      <div className="image-studio-generated-artifact-thumb">
        {imageUrl ? <img src={imageUrl} alt="" /> : <FileImage size={24} aria-hidden="true" />}
      </div>
      <div>
        <strong>{label}</strong>
        <span>{source}</span>
        {artifact?.artifactSha256 ? <code>sha {String(artifact.artifactSha256).slice(0, 12)}</code> : null}
      </div>
      <div className="image-studio-generated-artifact-actions">
        {imageUrl ? <a href={imageUrl}>Open image</a> : null}
        {manifestUrl ? <a href={manifestUrl}>Manifest</a> : null}
      </div>
    </article>
  );
}

function ProviderRunResult({ result, error }) {
  if (!result && !error) return null;
  if (error) {
    return (
      <div className="image-studio-run-result is-error" role="status">
        <strong>Provider run blocked</strong>
        <span>{error}</span>
      </div>
    );
  }
  const imageUrl = imageUrlForRecord(result);
  return (
    <div className="image-studio-run-result" role="status">
      <div>
        <strong>{result.message || "Provider image artifact recorded."}</strong>
        <span>{result.provider || result.providerId || "provider"} - {result.model || "model"}</span>
        {result.receipt?.artifactSha256 ? <code>sha {String(result.receipt.artifactSha256).slice(0, 12)}</code> : null}
      </div>
      <div className="image-studio-run-result-actions">
        {imageUrl ? <a href={imageUrl}>Open image</a> : null}
        {result.manifestUrl ? <a href={result.manifestUrl}>Manifest</a> : null}
      </div>
    </div>
  );
}

function buildOperationTimeline({ draft, draftValidation, routeAvailability, runState, project }) {
  const result = runState?.result || {};
  const hasResult = Boolean(result && Object.keys(result).length > 0);
  const runStatus = runState?.status || "idle";
  const hasBlockingRun = Boolean(runState?.error) || runStatus === "blocked" || runStatus === "error";
  const hasArtifact = Boolean(
    result.outputArtifactPath ||
      result.imagePath ||
      result.previewUrl ||
      result.artifactId ||
      result.receipt?.artifactSha256 ||
      project?.history?.some(item => item.requestId === (result.requestId || draft?.id)),
  );
  const hasLayer = Boolean(result.layer || project?.layers?.some(layer => layer.id === result.layer?.id));
  return [
    {
      id: "draft",
      label: "Draft prepared",
      status: draft
        ? draftValidation?.ok
          ? "complete"
          : "blocked"
        : "waiting",
      detail: draft
        ? draftValidation?.ok
          ? `${draft.operation || "edit"} payload ${draft.id || "prepared"}`
          : draftValidation?.issues?.join("; ") || "Draft needs review."
        : "Prepare a request draft before claiming provider readiness.",
    },
    {
      id: "route",
      label: "Provider route",
      status: routeAvailability?.readyForRealRun ? "complete" : hasBlockingRun ? "blocked" : "waiting",
      detail: routeAvailability?.readyForRealRun
        ? `${routeAvailability.model} can run when confirmed.`
        : routeAvailability?.blockedReason || routeAvailability?.proofLimit || "Provider route needs capability proof.",
    },
    {
      id: "receipt",
      label: "Provider receipt",
      status:
        runStatus === "running"
          ? "active"
          : hasResult && !hasBlockingRun && result.providerStatus !== "blocked"
            ? "complete"
            : hasBlockingRun
              ? "blocked"
              : "waiting",
      detail:
        runStatus === "running"
          ? "Waiting for backend receipt."
          : runState?.error || result.receipt?.promptHash || "No provider receipt has been returned yet.",
    },
    {
      id: "artifact",
      label: "Artifact written",
      status: hasArtifact ? "complete" : hasBlockingRun ? "blocked" : "waiting",
      detail: hasArtifact
        ? result.outputArtifactPath || result.imagePath || result.previewUrl || result.artifactId || "Artifact is recorded in history."
        : "Requires provider output manifest, image path, and hash.",
    },
    {
      id: "layer",
      label: "Layer handoff",
      status: hasLayer ? "complete" : hasArtifact ? "waiting" : hasBlockingRun ? "blocked" : "waiting",
      detail: hasLayer ? "Generated layer was attached to the local composition preview." : "Attach the generated artifact as a reviewable layer.",
    },
  ];
}

function OperationTimeline({ timeline }) {
  if (!Array.isArray(timeline) || timeline.length === 0) return null;
  const completeCount = timeline.filter(item => item.status === "complete").length;
  return (
    <section className="image-studio-operation-timeline" aria-label="Image operation timeline">
      <div className="image-studio-operation-timeline-head">
        <div>
          <span>Operation timeline</span>
          <strong>{completeCount}/{timeline.length} complete</strong>
        </div>
        <b>{timeline.some(item => item.status === "blocked") ? "Blocked honestly" : "Ready for proof"}</b>
      </div>
      <ol>
        {timeline.map((item, index) => (
          <li className={`is-${item.status}`} key={item.id} style={{ "--image-studio-timeline-index": index }}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <div>
              <strong>{item.label}</strong>
              <p>{item.detail}</p>
            </div>
            <em>{item.status.replace(/_/g, " ")}</em>
          </li>
        ))}
      </ol>
    </section>
  );
}

function ProofReviewSummary({ review }) {
  if (!review) return null;
  return (
    <div className="image-studio-proof-review" aria-label="Preview and annotation proof review">
      <div>
        <span>Preview</span>
        <strong>
          {review.preview.visibleLayerCount}/{review.preview.layerCount} layers
        </strong>
      </div>
      <div>
        <span>Annotations</span>
        <strong>{review.annotations.total}</strong>
      </div>
      <div>
        <span>References</span>
        <strong>{review.references.count}</strong>
      </div>
      <div>
        <span>Matte</span>
        <strong>{review.chromaKey.ready ? "Ready" : review.chromaKey.status.replace(/_/g, " ")}</strong>
      </div>
      <div>
        <span>Provider handoff</span>
        <strong>{review.readyForProviderHandoff ? "Ready" : "Needs review"}</strong>
      </div>
    </div>
  );
}

function ImageBreakdownWorkflow({ workflow, route, routeAvailability }) {
  if (!workflow) return null;
  const routeReady = Boolean(routeAvailability?.readyForRealRun);
  return (
    <section className="image-studio-breakdown" aria-label="Image breakdown workflow">
      <div className="image-studio-breakdown-head">
        <div>
          <span>Image breakdown</span>
          <strong>{workflow.handoffState.replace(/_/g, " ")}</strong>
        </div>
        <div className="image-studio-breakdown-badges">
          <b>{workflow.readyCount}/{workflow.stageCount} ready</b>
          <b>{routeReady ? "route ready" : "fallback logged"}</b>
        </div>
      </div>
      <p>{workflow.nextAction}</p>
      <p className="image-studio-breakdown-route">
        Preferred OpenCode / Z.AI / GLM-5.2; active proof chain: image_vision_breakdown, leon_lin_design_taste,
        ui_self_repair_planner, self_repair_verifier. Current route:{" "}
        {route?.providerId || route?.provider || "provider"} / {routeAvailability?.model || route?.model || "model"}.
      </p>
      <details className="image-studio-breakdown-details">
        <summary>{workflow.stageCount} stage checks</summary>
        <div className="image-studio-breakdown-rail">
          {workflow.stages.map((stage, index) => (
            <article
              className={`image-studio-breakdown-step is-${stage.status}`}
              key={stage.id}
              style={{ "--image-studio-step-index": index }}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{stage.label}</strong>
              <em>{stage.status.replace(/_/g, " ")}</em>
              <p>{stage.detail}</p>
              <code>{stage.evidence}</code>
            </article>
          ))}
        </div>
      </details>
    </section>
  );
}

function ChromaMatteDiagnostics({ proof }) {
  if (!proof) return null;
  const checklist = Array.isArray(proof.qaChecklist) ? proof.qaChecklist : [];
  return (
    <div className="image-studio-chroma-diagnostics" aria-label="Chroma-key matte diagnostics">
      <div
        className="image-studio-matte-preview"
        style={{
          "--image-studio-key-color": proof.keyColor || "#00ff66",
          "--image-studio-matte-strength": `${Math.max(8, Number(proof.matteStrength) || 0)}%`,
          "--image-studio-matte-feather": `${Math.min(28, Math.max(2, Number(proof.edgeFeather) || 0))}px`,
        }}
      >
        <span className="image-studio-matte-subject" aria-hidden="true" />
        <span className="image-studio-matte-cutline" aria-hidden="true" />
        <b>Configuration estimate</b>
      </div>
      <div className="image-studio-chroma-checklist">
        <div>
          <strong>Matte QA checklist</strong>
          <span>{proof.exportStatus}</span>
        </div>
        <ul>
          {checklist.map(item => (
            <li key={item.id}>
              <StatusMark status={item.status} />
              <span>{item.label}</span>
              <small>{item.detail}</small>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function ChromaMattePreviewPanel({ preview }) {
  if (!preview) {
    return (
      <p className="image-studio-empty">
        Select an attached or served image, then preview the matte to create local pixel proof.
      </p>
    );
  }
  return (
    <div className="image-studio-local-matte-proof" aria-label="Local matte proof preview">
      <figure>
        <img src={preview.outputUrl} alt="Local chroma-key transparent preview" />
        <figcaption>Transparent preview</figcaption>
      </figure>
      <figure>
        <img src={preview.maskUrl} alt="Local chroma-key black and white matte mask" />
        <figcaption>Matte mask</figcaption>
      </figure>
      <dl>
        <div>
          <dt>Removed</dt>
          <dd>{preview.removedPercent}%</dd>
        </div>
        <div>
          <dt>Soft edge</dt>
          <dd>{preview.softPercent}%</dd>
        </div>
        <div>
          <dt>Source</dt>
          <dd>{preview.sourceLabel}</dd>
        </div>
      </dl>
    </div>
  );
}

function ArtifactBackendHealthNote({ health }) {
  const status = health?.status || "checking";
  const label =
    status === "ready" ? "Artifact backend ready" :
      status === "offline" ? "Artifact backend offline" :
        "Checking artifact backend";
  return (
    <div className="image-studio-backend-health" data-status={status} aria-live="polite">
      <strong>{label}</strong>
      <span>{health?.detail || "Served artifact sources need the local web backend."}</span>
    </div>
  );
}

export function ImageStudioPlayground({
  generatedArtifacts = [],
  imageGenerationCapability = null,
  initialProject,
  onRequestDraft,
  onRunImageOperation,
}) {
  const [project, setProject] = useState(() => normalizeProject(initialProject || loadImageProject()));
  const [session, setSession] = useState(loadStudioSession);
  const [draft, setDraft] = useState(null);
  const [mattePreview, setMattePreview] = useState(null);
  const [runState, setRunState] = useState({
    status: "idle",
    result: null,
    error: "",
  });
  const [backendHealth, setBackendHealth] = useState({
    status: "checking",
    detail: "Checking whether served artifacts can load through the local backend.",
  });
  const [announcement, setAnnouncement] = useState("Image studio ready.");
  const fileInputRef = useRef(null);
  const referenceAssetsRef = useRef([]);

  const route = useMemo(() => getProviderRoute(session.routeId), [session.routeId]);
  const draftValidation = useMemo(() => (draft ? validateImageStudioRequestDraft(draft) : null), [draft]);
  const proofReview = useMemo(
    () =>
      buildImageStudioProofReview(project, draft, {
        capability: imageGenerationCapability,
        referenceAssets: session.referenceAssets,
        route,
      }),
    [draft, imageGenerationCapability, project, route, session.referenceAssets],
  );
  const breakdownWorkflow = useMemo(
    () =>
      buildImageBreakdownWorkflow(project, draft, {
        capability: imageGenerationCapability,
        referenceAssets: session.referenceAssets,
        route,
      }),
    [draft, imageGenerationCapability, project, route, session.referenceAssets],
  );
  const routeAvailability = proofReview.imageGenerationRouteStatus;
  const chromaProof = proofReview.chromaKey;
  const operationTimeline = useMemo(
    () => buildOperationTimeline({ draft, draftValidation, routeAvailability, runState, project }),
    [draft, draftValidation, routeAvailability, runState, project],
  );
  const servedGeneratedArtifacts = Array.isArray(generatedArtifacts) ? generatedArtifacts : [];
  const matteSources = useMemo(() => {
    const referenceSources = (session.referenceAssets || [])
      .filter(asset => asset.previewUrl)
      .map(asset => ({
        id: `ref:${asset.id}`,
        label: asset.name || "Reference image",
        src: asset.previewUrl,
        type: "reference",
      }));
    const artifactSources = servedGeneratedArtifacts
      .map((artifact, index) => ({
        id: `artifact:${artifact?.artifactId || artifact?.path || index}`,
        label: imageLabelForRecord(artifact, `Served artifact ${index + 1}`),
        src: imageUrlForRecord(artifact),
        type: "artifact",
      }))
      .filter(item => item.src);
    const historySources = (project.history || [])
      .map((item, index) => ({
        id: `history:${item?.id || item?.requestId || index}`,
        label: imageLabelForRecord(item, `History artifact ${index + 1}`),
        src: imageUrlForRecord(item),
        type: "history",
      }))
      .filter(item => item.src);
    const designSources = (project.designReferences || [])
      .filter(item => item?.kind === "generated-image")
      .map((item, index) => ({
        id: `reference-artifact:${item?.artifactId || item?.id || index}`,
        label: imageLabelForRecord(item, `Design reference ${index + 1}`),
        src: imageUrlForRecord(item),
        type: "design-reference",
      }))
      .filter(item => item.src)
      .sort((a, b) => {
        const aCurrent = a.src.includes("design_references") ? 1 : 0;
        const bCurrent = b.src.includes("design_references") ? 1 : 0;
        return bCurrent - aCurrent;
      });
    const deduped = new Map();
    const liveSources = [...referenceSources, ...artifactSources, ...designSources, ...historySources];
    const sampleSource = {
      id: "synthetic:green-screen-sample",
      label: "Sample only - synthetic green screen",
      src: SYNTHETIC_CHROMA_SAMPLE_URL,
      type: "synthetic-sample",
    };
    for (const source of [...liveSources, ...(liveSources.length ? [] : [sampleSource])]) {
      if (!deduped.has(source.src)) deduped.set(source.src, source);
    }
    return [...deduped.values()].slice(0, 12);
  }, [project.designReferences, project.history, servedGeneratedArtifacts, session.referenceAssets]);
  const selectedMatteSource = matteSources.find(item => item.id === session.matteSourceId) || matteSources[0] || null;

  useEffect(() => {
    saveImageProject(project);
  }, [project]);

  useEffect(() => {
    saveStudioSession(session);
  }, [session]);

  useEffect(() => {
    if (typeof fetch !== "function") {
      setBackendHealth({
        status: "offline",
        detail: "Fetch is unavailable, so served artifact health cannot be checked.",
      });
      return;
    }
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 2500);
    fetch(artifactBackendHealthUrl(), {
      cache: "no-store",
      signal: controller.signal,
    })
      .then(async response => {
        window.clearTimeout(timeout);
        if (!response.ok) {
          throw new Error(`Backend health returned HTTP ${response.status}.`);
        }
        const payload = await response.json().catch(() => ({}));
        setBackendHealth({
          status: payload?.ok === false ? "offline" : "ready",
          detail:
            payload?.ok === false
              ? "The backend responded, but did not report ready artifact serving."
              : "Served artifact sources can load through /api/artifact.",
        });
      })
      .catch(error => {
        window.clearTimeout(timeout);
        setBackendHealth({
          status: "offline",
          detail:
            error?.name === "AbortError"
              ? "Backend health timed out; use upload or the synthetic sample until it is started."
              : "Backend is not reachable; use upload or the synthetic sample until scripts/run_web_backend.py is running.",
        });
      });
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, []);

  useEffect(() => {
    referenceAssetsRef.current = session.referenceAssets || [];
  }, [session.referenceAssets]);

  useEffect(() => {
    return () => {
      for (const asset of referenceAssetsRef.current || []) {
        if (asset.previewUrl?.startsWith("blob:")) {
          URL.revokeObjectURL(asset.previewUrl);
        }
      }
    };
  }, []);

  function updatePrompt(patch) {
    setProject(current => ({
      ...current,
      updatedAt: new Date().toISOString(),
      prompt: {
        ...current.prompt,
        ...patch,
      },
    }));
  }

  function updateCanvas(presetId) {
    const preset = CANVAS_SIZE_PRESETS.find(item => item.id === presetId);
    if (!preset) return;
    setProject(current => ({
      ...current,
      updatedAt: new Date().toISOString(),
      canvas: {
        ...current.canvas,
        width: preset.width,
        height: preset.height,
      },
    }));
  }

  function updateSelection(field, value) {
    setProject(current => ({
      ...current,
      updatedAt: new Date().toISOString(),
      selection: {
        ...current.selection,
        [field]: field === "visible" ? Boolean(value) : Number(value),
      },
    }));
  }

  function updateChromaKey(field, value) {
    setProject(current => ({
      ...current,
      updatedAt: new Date().toISOString(),
      chromaKey: {
        ...current.chromaKey,
        [field]: field === "enabled" ? Boolean(value) : field === "keyColor" || field === "replacementIntent" ? value : Number(value),
      },
    }));
    setMattePreview(null);
  }

  function handleFilesSelected(event) {
    const files = Array.from(event.target.files || []);
    if (files.length === 0) return;
    const nextAssets = files.map(file =>
      createReferenceAssetFromFile(file, {
        previewUrl: file.type?.startsWith("image/") ? URL.createObjectURL(file) : "",
      }),
    );
    setSession(current => ({
      ...current,
      referenceAssets: [...current.referenceAssets, ...nextAssets].slice(0, 12),
    }));
    setAnnouncement(`${nextAssets.length} reference asset${nextAssets.length === 1 ? "" : "s"} added.`);
    event.target.value = "";
  }

  function removeReference(assetId) {
    setSession(current => {
      const target = current.referenceAssets.find(asset => asset.id === assetId);
      if (target?.previewUrl?.startsWith("blob:")) {
        URL.revokeObjectURL(target.previewUrl);
      }
      return {
        ...current,
        referenceAssets: current.referenceAssets.filter(asset => asset.id !== assetId),
      };
    });
  }

  function addMaskLayer() {
    setProject(current => createLayerFromSelection(current, { name: "Mask handoff layer", promptRole: "mask region" }));
    setAnnouncement("Mask handoff layer added to the local composition preview.");
  }

  function toggleLayerVisibility(layerId) {
    setProject(current => {
      const layer = current.layers.find(item => item.id === layerId);
      if (!layer) return current;
      return updateLayerInProject(current, layerId, { visible: layer.visible === false });
    });
  }

  function prepareDraft() {
    const nextDraft = buildImageStudioRequestDraft(project, {
      routeId: route.id,
      maskMode: session.maskMode,
      referenceAssets: session.referenceAssets,
    });
    setDraft(nextDraft);
    onRequestDraft?.(nextDraft);
    setAnnouncement("Provider request draft prepared. No image provider was called.");
  }

  async function runProviderImage() {
    const nextDraft = draft || buildImageStudioRequestDraft(project, {
      routeId: route.id,
      maskMode: session.maskMode,
      referenceAssets: session.referenceAssets,
    });
    setDraft(nextDraft);
    onRequestDraft?.(nextDraft);
    if (!routeAvailability.readyForRealRun || !routeAvailability.runActionAvailable) {
      const message = routeAvailability.blockedReason
        ? `Provider run blocked: ${routeAvailability.blockedReason}.`
        : routeAvailability.proofLimit;
      setRunState({ status: "blocked", result: null, error: message });
      setAnnouncement(message);
      return;
    }
    if (!onRunImageOperation) {
      const message = "Provider run is unavailable because the shell did not attach a backend operation handler.";
      setRunState({ status: "blocked", result: null, error: message });
      setAnnouncement(message);
      return;
    }
    setRunState({ status: "running", result: null, error: "" });
    setAnnouncement("Provider image run started. Waiting for backend receipt.");
    try {
      const result = await onRunImageOperation(buildImageStudioOperationPayload(nextDraft), nextDraft);
      if (!result || typeof result !== "object") {
        throw new Error("Backend did not return an image operation result.");
      }
      if (result.providerStatus === "blocked" || result.blockedReason) {
        const message = result.message || result.blockedReason || "Image provider run was blocked.";
        setRunState({ status: "blocked", result, error: message });
        setAnnouncement(message);
        return;
      }
      setProject(current => {
        const withHistory = addHistoryEntry(current, {
          id: result.requestId || result.artifactId,
          title: result.message || "Provider image artifact",
          prompt: nextDraft.payload?.prompt?.text || current.prompt?.text || "",
          provider: result.provider || result.providerId || "Image provider",
          providerId: result.providerId || nextDraft.route?.providerId || "",
          providerStatus: result.providerStatus || "available",
          status: "generated",
          requestId: result.requestId || nextDraft.id,
          outputArtifactPath: result.outputArtifactPath || result.imagePath || "",
          previewSrc: result.previewUrl || result.outputArtifactPath || "",
          manifestPath: result.manifestPath || "",
          manifestUrl: result.manifestUrl || "",
          artifactSha256: result.receipt?.artifactSha256 || result.artifactSha256 || "",
          receipt: result.receipt || {},
          layerCount: current.layers.length + (result.layer ? 1 : 0),
        });
        if (!result.layer) return withHistory;
        const layerExists = withHistory.layers.some(layer => layer.id === result.layer.id);
        return {
          ...withHistory,
          selectedLayerId: result.layer.id || withHistory.selectedLayerId,
          layers: layerExists ? withHistory.layers : [...withHistory.layers, result.layer],
        };
      });
      setRunState({ status: "completed", result, error: "" });
      setAnnouncement("Provider image artifact recorded with receipt and manifest links.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Provider image run failed.";
      setRunState({ status: "error", result: null, error: message });
      setAnnouncement(message);
    }
  }

  async function previewLocalMatte() {
    if (!selectedMatteSource) {
      setAnnouncement("Attach a reference image or use a served artifact before previewing the matte.");
      return;
    }
    try {
      const image = await loadImageForCanvas(selectedMatteSource.src);
      const preview = renderChromaMattePreview({ image, proof: chromaProof, source: selectedMatteSource });
      setMattePreview(preview);
      setAnnouncement(`Local matte proof ready for ${selectedMatteSource.label}.`);
    } catch (error) {
      setMattePreview(null);
      setAnnouncement(error instanceof Error ? error.message : "Local matte proof failed.");
    }
  }

  async function copyDraftJson() {
    if (!draft) return;
    const text = JSON.stringify(draft, null, 2);
    try {
      await navigator.clipboard.writeText(text);
      setAnnouncement("Request draft copied to clipboard.");
    } catch {
      setAnnouncement("Clipboard is unavailable. Draft JSON remains visible in the proof panel.");
    }
  }

  const currentPreset =
    CANVAS_SIZE_PRESETS.find(item => item.width === project.canvas.width && item.height === project.canvas.height)?.id ||
    "custom";

  return (
    <section className="image-studio" aria-labelledby="image-studio-title">
      <div className="image-studio-topbar">
        <div>
          <p className="image-studio-kicker">Image studio</p>
          <h2 id="image-studio-title">Provider-ready image playground</h2>
          <p className="image-studio-subtitle">
            Compose prompts, reference assets, mask geometry, route metadata, and proof records before a real provider run.
          </p>
        </div>
        <div className="image-studio-route-summary" aria-label="Selected provider route">
          <ShieldCheck size={20} aria-hidden="true" />
          <span>{route.label}</span>
          <b>{route.status.replace(/_/g, " ")}</b>
        </div>
      </div>

      <ImageBreakdownWorkflow workflow={breakdownWorkflow} route={route} routeAvailability={routeAvailability} />

      <div className="image-studio-grid">
        <aside className="image-studio-panel image-studio-controls" aria-label="Prompt and route controls">
          <section className="image-studio-control-group" aria-labelledby="image-studio-prompt-label">
            <div className="image-studio-section-title">
              <ImageSquare size={18} aria-hidden="true" />
              <h3 id="image-studio-prompt-label">Prompt</h3>
            </div>
            <label htmlFor={fieldId("prompt")}>Prompt text</label>
            <textarea
              id={fieldId("prompt")}
              value={project.prompt.text}
              onChange={event => updatePrompt({ text: event.target.value })}
              rows={5}
            />
            <label className="image-studio-checkbox">
              <input
                type="checkbox"
                checked={project.prompt.preserveComposition}
                onChange={event => updatePrompt({ preserveComposition: event.target.checked })}
              />
              <span>Preserve manual composition</span>
            </label>
            <details className="image-studio-advanced-disclosure">
              <summary>Advanced prompt controls</summary>
              <label htmlFor={fieldId("negative")}>Negative prompt</label>
              <textarea
                id={fieldId("negative")}
                value={project.prompt.negative}
                onChange={event => updatePrompt({ negative: event.target.value })}
                rows={3}
              />
              <label htmlFor={fieldId("style")}>Style notes</label>
              <input
                id={fieldId("style")}
                value={project.prompt.style}
                onChange={event => updatePrompt({ style: event.target.value })}
              />
              <div className="image-studio-inline-field">
                <label htmlFor={fieldId("strength")}>Prompt strength</label>
                <output>{Math.round(project.prompt.strength * 100)}%</output>
              </div>
              <input
                id={fieldId("strength")}
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={project.prompt.strength}
                onChange={event => updatePrompt({ strength: Number(event.target.value) })}
              />
            </details>
          </section>

          <section className="image-studio-control-group" aria-labelledby="image-studio-route-label">
            <div className="image-studio-section-title">
              <SlidersHorizontal size={18} aria-hidden="true" />
              <h3 id="image-studio-route-label">Provider route</h3>
            </div>
            <label htmlFor={fieldId("route")}>Route</label>
            <select
              id={fieldId("route")}
              value={route.id}
              onChange={event => setSession(current => ({ ...current, routeId: event.target.value }))}
            >
              {IMAGE_STUDIO_PROVIDER_ROUTES.map(item => (
                <option key={item.id} value={item.id}>{item.label}</option>
              ))}
            </select>
            <details className="image-studio-advanced-disclosure image-studio-route-details">
              <summary>Route details</summary>
              <dl className="image-studio-route-facts">
                <div>
                  <dt>Model</dt>
                  <dd>{route.model}</dd>
                </div>
                <div>
                  <dt>Auth</dt>
                  <dd>{route.authMode}</dd>
                </div>
                <div>
                  <dt>Capabilities</dt>
                  <dd>{route.supports.join(", ")}</dd>
                </div>
                <div>
                  <dt>Availability</dt>
                  <dd>{routeAvailability.localStatus.replace(/_/g, " ")}</dd>
                </div>
              </dl>
              <div className="image-studio-route-status" data-status={routeAvailability.localStatus}>
                <strong>{routeAvailability.readyForRealRun ? "Provider run available" : "Draft handoff only"}</strong>
                <p>{routeAvailability.claim}</p>
                <p>{routeAvailability.proofLimit}</p>
                {routeAvailability.blockedReason ? (
                  <code>{routeAvailability.blockedReason}</code>
                ) : null}
                {routeAvailability.checks.length > 0 ? (
                  <div className="image-studio-capability-checks" aria-label="Image generation capability checks">
                    {routeAvailability.checks.slice(0, 4).map(check => (
                      <span data-status={check.passed ? "ready" : "blocked"} key={check.checkId || check.label}>
                        {check.label}
                      </span>
                    ))}
                  </div>
                ) : null}
                {routeAvailability.officialSources.length > 0 ? (
                  <small>{routeAvailability.officialSources.length} official source{routeAvailability.officialSources.length === 1 ? "" : "s"} recorded for review.</small>
                ) : null}
              </div>
            </details>
          </section>

          <section className="image-studio-control-group image-studio-chroma-card" aria-labelledby="image-studio-chroma-label">
            <div className="image-studio-section-title">
              <SlidersHorizontal size={18} aria-hidden="true" />
              <h3 id="image-studio-chroma-label">Green screen matte</h3>
            </div>
            <label className="image-studio-checkbox">
              <input
                type="checkbox"
                checked={project.chromaKey.enabled}
                onChange={event => updateChromaKey("enabled", event.target.checked)}
              />
              <span>Prepare chroma-key removal</span>
            </label>
            <div className="image-studio-color-field image-studio-color-field-compact">
              <label htmlFor={fieldId("chroma-key")}>Key color</label>
              <input
                id={fieldId("chroma-key")}
                type="color"
                value={project.chromaKey.keyColor}
                onChange={event => updateChromaKey("keyColor", event.target.value)}
                aria-label="Green screen key color"
              />
              <code>{project.chromaKey.keyColor}</code>
            </div>
            <p className="image-studio-matte-status">
              {proofReview.chromaKey.ready ? "Matte proof ready" : "Matte needs review"} - {proofReview.chromaKey.providerInstruction}
            </p>
            <button type="button" className="image-studio-secondary-action" onClick={previewLocalMatte} disabled={!selectedMatteSource}>
              Preview matte
            </button>
            <details className="image-studio-advanced-disclosure">
              <summary>Advanced matte controls</summary>
              <div className="image-studio-local-matte-controls" aria-label="Local chroma-key proof controls">
                <label htmlFor={fieldId("matte-source")}>Proof source</label>
                <select
                  id={fieldId("matte-source")}
                  value={selectedMatteSource?.id || ""}
                  onChange={event => {
                    setSession(current => ({ ...current, matteSourceId: event.target.value }));
                    setMattePreview(null);
                  }}
                >
                  {matteSources.length === 0 ? <option value="">Attach an image first</option> : null}
                  {matteSources.map(source => (
                    <option key={source.id} value={source.id}>
                      {source.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="image-studio-chroma-proof" aria-label="Chroma-key proof status">
                <span
                  className="image-studio-chroma-swatch"
                  style={{ background: project.chromaKey.keyColor }}
                  aria-hidden="true"
                />
                <div>
                  <strong>{proofReview.chromaKey.ready ? "Matte proof ready" : "Matte needs review"}</strong>
                  <span>{proofReview.chromaKey.providerInstruction}</span>
                </div>
              </div>
              {[
                ["tolerance", "Tolerance", 100],
                ["spillCleanup", "Spill cleanup", 100],
                ["edgeFeather", "Edge feather", 64],
              ].map(([field, label, max]) => (
                <div className="image-studio-inline-field image-studio-slider-field" key={field}>
                  <label htmlFor={fieldId(`chroma-${field}`)}>{label}</label>
                  <output>{Math.round(project.chromaKey[field])}{field === "edgeFeather" ? "px" : "%"}</output>
                  <input
                    id={fieldId(`chroma-${field}`)}
                    type="range"
                    min="0"
                    max={max}
                    step="1"
                    value={project.chromaKey[field]}
                    onChange={event => updateChromaKey(field, event.target.value)}
                  />
                </div>
              ))}
              <label htmlFor={fieldId("chroma-intent")}>Replacement intent</label>
              <textarea
                id={fieldId("chroma-intent")}
                value={project.chromaKey.replacementIntent}
                onChange={event => updateChromaKey("replacementIntent", event.target.value)}
                rows={2}
              />
              <ChromaMatteDiagnostics proof={chromaProof} />
              <ArtifactBackendHealthNote health={backendHealth} />
              <ChromaMattePreviewPanel preview={mattePreview} />
            </details>
          </section>
        </aside>

        <main className="image-studio-panel image-studio-stage" aria-label="Canvas and mask workspace">
          <div className="image-studio-stage-toolbar">
            <div className="image-studio-tool-tabs" role="tablist" aria-label="Image tools">
              {IMAGE_TOOL_DEFINITIONS.map(tool => (
                <button
                  key={tool.id}
                  type="button"
                  className={tool.id === project.activeTool ? "is-active" : ""}
                  onClick={() => setProject(current => ({ ...current, activeTool: tool.id }))}
                  title={tool.hint}
                >
                  {tool.label}
                </button>
              ))}
            </div>
            <label htmlFor={fieldId("canvas")}>Canvas</label>
            <select id={fieldId("canvas")} value={currentPreset} onChange={event => updateCanvas(event.target.value)}>
              {CANVAS_SIZE_PRESETS.map(preset => (
                <option key={preset.id} value={preset.id}>{preset.label} {preset.width}x{preset.height}</option>
              ))}
              <option value="custom">Custom</option>
            </select>
          </div>

          <div className="image-studio-canvas-wrap">
            <div
              className="image-studio-canvas"
              style={{
                aspectRatio: `${project.canvas.width} / ${project.canvas.height}`,
                background: project.canvas.background,
              }}
              role="img"
              aria-label={`Local composition preview, not provider output, with ${project.layers.length} layers and ${project.selection.visible ? "one visible mask" : "no visible mask"}`}
            >
              {project.layers.map(layer => (
                <ProjectLayer key={layer.id} layer={layer} canvas={project.canvas} />
              ))}
              <div className="image-studio-local-preview-badge">
                Local composition preview - not provider output
              </div>
              <SelectionOverlay selection={project.selection} canvas={project.canvas} mode={session.maskMode} />
              <AnnotationOverlay annotations={project.annotationReadiness} canvas={project.canvas} />
            </div>
          </div>

          <div className="image-studio-stage-footer">
            <section aria-labelledby="image-studio-mask-label">
              <h3 id="image-studio-mask-label">Mask</h3>
              <div className="image-studio-mask-controls">
                <label>
                  Mode
                  <select
                    value={session.maskMode}
                    onChange={event => setSession(current => ({ ...current, maskMode: event.target.value }))}
                  >
                    {IMAGE_STUDIO_MASK_MODES.map(mode => (
                      <option key={mode.id} value={mode.id}>{mode.label}</option>
                    ))}
                  </select>
                </label>
                {["x", "y", "width", "height", "feather"].map(field => (
                  <label key={field}>
                    {field}
                    <input
                      type="number"
                      min="0"
                      value={Math.round(project.selection[field] || 0)}
                      onChange={event => updateSelection(field, event.target.value)}
                    />
                  </label>
                ))}
                <label className="image-studio-checkbox">
                  <input
                    type="checkbox"
                    checked={project.selection.visible}
                    onChange={event => updateSelection("visible", event.target.checked)}
                  />
                  <span>Visible</span>
                </label>
              </div>
              <button type="button" className="image-studio-secondary-action" onClick={addMaskLayer}>
                <Plus size={16} aria-hidden="true" />
                Add mask layer
              </button>
            </section>
          </div>
        </main>

        <aside className="image-studio-panel image-studio-right-rail" aria-label="References, history, and proof">
          <section className="image-studio-control-group" aria-labelledby="image-studio-reference-label">
            <div className="image-studio-section-title">
              <Stack size={18} aria-hidden="true" />
              <h3 id="image-studio-reference-label">References</h3>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              className="image-studio-hidden-input"
              onChange={handleFilesSelected}
            />
            <button type="button" className="image-studio-secondary-action" onClick={() => fileInputRef.current?.click()}>
              <Plus size={16} aria-hidden="true" />
              Add reference
            </button>
            {session.referenceAssets.length > 0 ? (
              <ul className="image-studio-reference-list">
                {session.referenceAssets.map(asset => (
                  <ReferencePreview key={asset.id} asset={asset} onRemove={removeReference} />
                ))}
              </ul>
            ) : (
              <p className="image-studio-empty">No local references attached.</p>
            )}
          </section>

          <section className="image-studio-control-group" aria-labelledby="image-studio-history-label">
            <div className="image-studio-section-title">
              <ClockCounterClockwise size={18} aria-hidden="true" />
              <h3 id="image-studio-history-label">History</h3>
            </div>
            {project.history.length > 0 ? (
              <ul className="image-studio-history-list">
                {project.history.slice(0, 5).map(item => (
                  <HistoryRow key={item.id || item.requestId} item={item} />
                ))}
              </ul>
            ) : (
              <p className="image-studio-empty">No real image artifact history is available.</p>
            )}
          </section>

          <section className="image-studio-control-group" aria-labelledby="image-studio-served-artifacts-label">
            <div className="image-studio-section-title">
              <FileImage size={18} aria-hidden="true" />
              <h3 id="image-studio-served-artifacts-label">Served artifacts</h3>
            </div>
            {servedGeneratedArtifacts.length > 0 ? (
              <div className="image-studio-generated-artifact-list">
                {servedGeneratedArtifacts.slice(0, 4).map((artifact, index) => (
                  <GeneratedArtifactCard artifact={artifact} key={artifact?.artifactId || artifact?.path || index} />
                ))}
              </div>
            ) : (
              <p className="image-studio-empty">No served generated image artifacts are available yet.</p>
            )}
          </section>

          <section className="image-studio-control-group" aria-labelledby="image-studio-layers-label">
            <div className="image-studio-section-title">
              <Stack size={18} aria-hidden="true" />
              <h3 id="image-studio-layers-label">Layers</h3>
            </div>
            <ul className="image-studio-layer-list">
              {project.layers.map(layer => (
                <li key={layer.id}>
                  <button type="button" onClick={() => toggleLayerVisibility(layer.id)}>
                    {layer.visible === false ? "Hidden" : "Visible"}
                  </button>
                  <span>{layer.name}</span>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>

      <section className="image-studio-proof-panel" aria-labelledby="image-studio-proof-label">
        <div>
          <p className="image-studio-kicker">Proof artifacts</p>
          <h3 id="image-studio-proof-label">Request handoff</h3>
        </div>
        <div className="image-studio-proof-actions">
          <button type="button" className="image-studio-primary-action" onClick={prepareDraft}>
            <ClipboardText size={17} aria-hidden="true" />
            Prepare request draft
          </button>
          <button
            type="button"
            className="image-studio-primary-action"
            onClick={runProviderImage}
            disabled={runState.status === "running" || !routeAvailability.readyForRealRun}
            title={!routeAvailability.readyForRealRun ? routeAvailability.proofLimit : ""}
          >
            <ImageSquare size={17} aria-hidden="true" />
            {runState.status === "running" ? "Running provider" : "Run provider image"}
          </button>
          <button type="button" className="image-studio-secondary-action" onClick={copyDraftJson} disabled={!draft}>
            Copy JSON
          </button>
        </div>
        <ProviderRunResult result={runState.result} error={runState.error} />
        <OperationTimeline timeline={operationTimeline} />
        <ProofReviewSummary review={proofReview} />
        <div className="image-studio-route-proof-note">
          <strong>{proofReview.imageGenerationRouteStatus.model}</strong>
          <span>{proofReview.imageGenerationRouteStatus.proofLimit}</span>
        </div>
        <div className="image-studio-proof-grid">
          {proofReview.checks.map(check => (
            <div className="image-studio-proof-item" key={check.id}>
              <StatusMark status={check.status} />
              <strong>{check.label}</strong>
              <span>{check.detail}</span>
            </div>
          ))}
        </div>
        {draft ? (
          <>
            <div className="image-studio-proof-grid">
              {draft.proofArtifacts.map(artifact => (
                <div className="image-studio-proof-item" key={artifact.id}>
                  <StatusMark status={artifact.status} />
                  <strong>{artifact.label}</strong>
                  <span>{artifact.detail}</span>
                </div>
              ))}
            </div>
            <div className="image-studio-draft-status">
              <span>{draft.proofReview?.noGenerationClaim || draft.noGenerationReason}</span>
              <b>{draftValidation?.ok ? "Draft valid" : draftValidation?.issues.join("; ")}</b>
            </div>
            <pre className="image-studio-json-preview" tabIndex="0">
              {JSON.stringify(draft, null, 2)}
            </pre>
          </>
        ) : (
          <p className="image-studio-empty">Prepare a request draft to review the provider payload and proof plan.</p>
        )}
      </section>

      <p className="image-studio-sr-status" role="status" aria-live="polite">{announcement}</p>
    </section>
  );
}

export default ImageStudioPlayground;
