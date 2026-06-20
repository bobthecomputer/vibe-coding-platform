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
  buildImageStudioRequestDraft,
  createReferenceAssetFromFile,
  formatBytes,
  getProviderRoute,
  validateImageStudioRequestDraft,
} from "./imageStudioModel.js";
import "./image-studio.css";

const EMPTY_SESSION = {
  routeId: "local-request-draft",
  maskMode: "replace",
  referenceAssets: [],
};

function loadStudioSession() {
  if (typeof window === "undefined") return EMPTY_SESSION;
  try {
    const raw = window.localStorage.getItem(IMAGE_STUDIO_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return {
      ...EMPTY_SESSION,
      ...(parsed && typeof parsed === "object" ? parsed : {}),
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

function StatusMark({ status }) {
  const ready = status === "ready";
  const empty = status === "empty";
  return (
    <span className={`image-studio-status-mark ${ready ? "is-ready" : empty ? "is-empty" : "is-planned"}`}>
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
    background: layer.fill || "rgba(255,255,255,.24)",
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

export function ImageStudioPlayground({ initialProject, onRequestDraft }) {
  const [project, setProject] = useState(() => normalizeProject(initialProject || loadImageProject()));
  const [session, setSession] = useState(loadStudioSession);
  const [draft, setDraft] = useState(null);
  const [announcement, setAnnouncement] = useState("Image studio ready.");
  const fileInputRef = useRef(null);
  const referenceAssetsRef = useRef([]);

  const route = useMemo(() => getProviderRoute(session.routeId), [session.routeId]);
  const draftValidation = useMemo(() => (draft ? validateImageStudioRequestDraft(draft) : null), [draft]);

  useEffect(() => {
    saveImageProject(project);
  }, [project]);

  useEffect(() => {
    saveStudioSession(session);
  }, [session]);

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
    setAnnouncement("Mask handoff layer added to the canvas model.");
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
              rows={6}
            />
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
            <label className="image-studio-checkbox">
              <input
                type="checkbox"
                checked={project.prompt.preserveComposition}
                onChange={event => updatePrompt({ preserveComposition: event.target.checked })}
              />
              <span>Preserve manual composition</span>
            </label>
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
            </dl>
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
              aria-label={`Canvas model with ${project.layers.length} layers and ${project.selection.visible ? "one visible mask" : "no visible mask"}`}
            >
              {project.layers.map(layer => (
                <ProjectLayer key={layer.id} layer={layer} canvas={project.canvas} />
              ))}
              <SelectionOverlay selection={project.selection} canvas={project.canvas} mode={session.maskMode} />
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
          <button type="button" className="image-studio-secondary-action" onClick={copyDraftJson} disabled={!draft}>
            Copy JSON
          </button>
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
              <span>{draft.noGenerationReason}</span>
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
