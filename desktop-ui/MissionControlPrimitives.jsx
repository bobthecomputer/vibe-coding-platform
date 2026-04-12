import { titleizeToken } from "./fluxioHelpers.js";

// Shared mission-control building blocks.
// These stay intentionally small so the screen hierarchy is driven by information architecture,
// not by a pile of one-off dashboard widgets.

export function StatusPill({ tone = "neutral", children, strong = false }) {
  return (
    <span className={`status-pill tone-${tone} ${strong ? "strong" : ""}`.trim()}>
      {children}
    </span>
  );
}

export function ActionButton({
  children,
  onClick,
  variant = "ghost",
  disabled = false,
  title = "",
  type = "button",
}) {
  return (
    <button
      className={`action-btn ${variant}`.trim()}
      disabled={disabled}
      onClick={onClick}
      title={title}
      type={type}
    >
      {children}
    </button>
  );
}

export function Field({ label, children, className = "" }) {
  return (
    <label className={`field ${className}`.trim()}>
      <span>{label}</span>
      {children}
    </label>
  );
}

export function SectionHeader({ eyebrow, title, summary, actions }) {
  return (
    <div className="section-header">
      <div className="section-title-block">
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h2>{title}</h2>
        {summary ? <p className="section-summary">{summary}</p> : null}
      </div>
      {actions ? <div className="section-actions">{actions}</div> : null}
    </div>
  );
}

export function SurfacePanel({ className = "", eyebrow, title, summary, actions, children }) {
  return (
    <section className={`surface-panel ${className}`.trim()}>
      {(eyebrow || title || summary || actions) && (
        <SectionHeader
          actions={actions}
          eyebrow={eyebrow}
          summary={summary}
          title={title}
        />
      )}
      <div className="surface-body">{children}</div>
    </section>
  );
}

export function RailModule({ className = "", eyebrow, title, summary, children, tone = "neutral" }) {
  return (
    <section className={`rail-module tone-${tone} ${className}`.trim()}>
      <SectionHeader eyebrow={eyebrow} summary={summary} title={title} />
      <div className="rail-body">{children}</div>
    </section>
  );
}

export function MetricStrip({ items, columns = 4, className = "" }) {
  return (
    <div
      className={`metric-strip ${className}`.trim()}
      style={{ "--metric-columns": columns }}
    >
      {items.map(item => (
        <div className="metric-cell" key={`${item.label}-${item.value}`}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
          {item.note ? <p>{item.note}</p> : null}
        </div>
      ))}
    </div>
  );
}

export function TimelineItem({ tone = "neutral", kind, title, detail, meta }) {
  return (
    <article className={`timeline-item tone-${tone}`.trim()}>
      <div className="timeline-marker" />
      <div className="timeline-content">
        <div className="timeline-topline">
          <span className="timeline-kind">{titleizeToken(kind || "event")}</span>
          {meta ? <span className="timeline-meta">{meta}</span> : null}
        </div>
        <strong>{title}</strong>
        {detail ? <p>{detail}</p> : null}
      </div>
    </article>
  );
}

export function DataList({ items, className = "" }) {
  return (
    <div className={`data-list ${className}`.trim()}>
      {items.map(item => (
        <div className="data-row" key={`${item.label}-${item.value}`}>
          <span>{item.label}</span>
          <div>
            <strong>{item.value}</strong>
            {item.note ? <p>{item.note}</p> : null}
          </div>
        </div>
      ))}
    </div>
  );
}

export function Modal({ open, title, summary, onClose, children, actions }) {
  if (!open) {
    return null;
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        aria-modal="true"
        className="modal-panel"
        onClick={event => event.stopPropagation()}
        role="dialog"
      >
        <SectionHeader
          actions={
            <ActionButton onClick={onClose} variant="ghost">
              Close
            </ActionButton>
          }
          summary={summary}
          title={title}
        />
        <div className="modal-body">{children}</div>
        {actions ? <div className="modal-actions">{actions}</div> : null}
      </section>
    </div>
  );
}
