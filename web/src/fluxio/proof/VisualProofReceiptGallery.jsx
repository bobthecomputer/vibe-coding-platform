function asList(value) {
  return Array.isArray(value) ? value : [];
}

function asRecord(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function artifactBackendBaseUrl() {
  const configured =
    import.meta.env?.VITE_FLUXIO_BACKEND_URL ||
    globalThis.window?.__FLUXIO_BACKEND_URL__ ||
    "";
  return String(configured || "").trim().replace(/\/$/, "");
}

function resolveControlArtifactUrl(value) {
  const source = String(value || "").trim();
  if (!source) return "";
  if (/^(data:|blob:|https?:\/\/)/i.test(source)) return source;
  if (source.startsWith("/api/artifact")) return `${artifactBackendBaseUrl()}${source}`;
  const params = new URLSearchParams({ path: source });
  return `${artifactBackendBaseUrl()}/api/artifact?${params.toString()}`;
}

function timestampLabel(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function cleanFramePath(value) {
  const source = String(value || "").trim();
  if (!source || source === "screenshots/latest.png" || source === "screenshots/previous.png") {
    return "";
  }
  return source;
}

function visualProofRows(receipts) {
  const seen = new Set();
  return asList(receipts)
    .slice()
    .reverse()
    .map((receipt, index) => {
      const visualPacket = asRecord(receipt?.visualProofPacket);
      const taskContext = asRecord(receipt?.taskContext);
      const currentAppProof = asRecord(visualPacket.currentAppProof || taskContext.currentAppProof);
      const screenshots = asList(taskContext.screenshots);
      const framePath = cleanFramePath(visualPacket.framePath || screenshots[0] || "");
      const artifactPath = receipt?.artifactPath || "";
      const receiptKind = receipt?.receiptKind || "live_review_receipt";
      const isLiveReviewReceipt = ["live_review_visual_proof", "live_review_structured_feedback"].includes(receiptKind);
      if (!isLiveReviewReceipt || !Boolean(framePath || artifactPath || screenshots.length)) return null;
      const eventId = receipt?.eventId || receipt?.sourceEventId || "";
      const handoffId = receipt?.plannerExecutorHandoffId || "";
      const key = `${receiptKind}:${eventId}:${handoffId}:${artifactPath}:${framePath}`;
      if (seen.has(key)) return null;
      seen.add(key);
      return {
        id: key || `visual-proof-${index}`,
        artifactPath,
        artifactUrl: resolveControlArtifactUrl(artifactPath),
        eventId,
        framePath,
        frameUrl: resolveControlArtifactUrl(framePath),
        handoffId,
        currentAppProof: {
          appSurface: currentAppProof.appSurface || "Fluxio current control shell",
          operatorLabel: currentAppProof.operatorLabel || "",
          previewUrl: currentAppProof.previewUrl || taskContext.previewUrl || visualPacket.previewUrl || "",
          isCurrentAppProof: Boolean(currentAppProof.isCurrentAppProof && framePath),
          staleFrameReason:
            currentAppProof.staleFrameReason ||
            (framePath ? "" : "Synthetic or missing frame path blocked for current-app proof."),
          schemaVersion: currentAppProof.schemaVersion || "current-app-preview-proof.v1",
        },
        proofTarget: visualPacket.proofTarget || taskContext.reviewTargetId || "",
        receiptKind,
        status: receipt?.status || "received",
        timestamp: receipt?.timestamp || "",
      };
    })
    .filter(Boolean)
    .slice(0, 5);
}

export function VisualProofReceiptGallery({ copyContextValue, receipts }) {
  const rows = visualProofRows(receipts);
  return (
    <article className="builder-visual-proof-receipts" aria-label="Visual proof receipts">
      <div className="builder-live-review-panel-head compact">
        <strong>Visual proof receipts</strong>
        <span className="mini-pill muted">{rows.length} captured</span>
      </div>
      {rows.length > 0 ? (
        <div className="builder-visual-proof-receipt-list" role="list">
          {rows.map(row => (
            <div className="builder-visual-proof-receipt-row" key={row.id} role="listitem">
              <div className="builder-live-review-receipt-history-meta">
                <strong>{row.receiptKind}</strong>
                <span>
                  {row.timestamp ? timestampLabel(row.timestamp) : "No timestamp"}
                  {row.status ? ` · ${row.status}` : ""}
                </span>
                <span>Event: {row.eventId || "none"} · Target: {row.proofTarget || "not captured"}</span>
                <span>
                  App: {row.currentAppProof.operatorLabel || row.currentAppProof.appSurface} ·{" "}
                  {row.currentAppProof.isCurrentAppProof ? "current-app proof" : "stale-frame blocked"}
                </span>
                <span>Capture URL: {row.currentAppProof.previewUrl || "not captured"}</span>
              </div>
              <div className="builder-live-review-receipt-handles compact">
                <button disabled={!row.artifactPath} onClick={() => copyContextValue(row.artifactPath)} title="Copy visual proof receipt artifact path" type="button">
                  Copy receipt artifact
                </button>
                <button disabled={!row.framePath} onClick={() => copyContextValue(row.framePath)} title="Copy visual proof frame path" type="button">
                  Copy frame path
                </button>
                <button disabled={!row.handoffId} onClick={() => copyContextValue(row.handoffId)} title="Copy visual proof handoff id" type="button">
                  Copy handoff
                </button>
                <button disabled={!row.artifactUrl} onClick={() => row.artifactUrl && window.open(row.artifactUrl, "_blank", "noopener,noreferrer")} title="Open receipt artifact" type="button">
                  Open receipt
                </button>
                <button disabled={!row.frameUrl} onClick={() => row.frameUrl && window.open(row.frameUrl, "_blank", "noopener,noreferrer")} title="Open frame artifact" type="button">
                  Open frame
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="builder-live-review-meta">
          No captured visual-proof receipts yet. Use Capture proof after selecting a preview frame.
        </p>
      )}
    </article>
  );
}

export default VisualProofReceiptGallery;
