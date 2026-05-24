import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  BookOpen,
  Bot,
  Check,
  ChevronDown,
  CircleCheckBig,
  CircleHelp,
  CircleDashed,
  Clock3,
  Code2,
  CreditCard,
  Database,
  Edit3,
  Expand,
  FileText,
  Filter,
  FolderOpen,
  Globe,
  Grid2x2,
  Hammer,
  History,
  Home,
  Laptop,
  LayoutGrid,
  Mic,
  Moon,
  Monitor,
  MoreHorizontal,
  NotebookPen,
  Palette,
  Paperclip,
  Play,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Shield,
  Smartphone,
  Sparkles,
  Star,
  SquareTerminal,
  SunMedium,
  Users,
  WandSparkles,
} from "lucide-react";

import { ImagePlaygroundSurface } from "./ImagePlayground.jsx";
import { RuntimeOperationsPanel } from "./RuntimeOperationsPanel.jsx";

function cx(...values) {
  return values.filter(Boolean).join(" ");
}

function asList(value) {
  return Array.isArray(value) ? value : [];
}

function uniq(values) {
  return Array.from(new Set(asList(values).filter(Boolean)));
}

function titleizeToken(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, char => char.toUpperCase());
}

const CONSISTENCY_STOP_WORDS = new Set([
  "about",
  "after",
  "agent",
  "also",
  "been",
  "before",
  "could",
  "from",
  "have",
  "hermes",
  "into",
  "just",
  "like",
  "make",
  "making",
  "message",
  "more",
  "only",
  "that",
  "their",
  "there",
  "these",
  "they",
  "this",
  "those",
  "turn",
  "very",
  "with",
  "would",
  "your",
]);

const CONSISTENCY_POSITIVE_TERMS = [
  "can",
  "able",
  "possible",
  "working",
  "works",
  "enabled",
  "ready",
  "completed",
  "done",
  "available",
  "succeeded",
];

const CONSISTENCY_NEGATIVE_TERMS = [
  "cannot",
  "can't",
  "unable",
  "impossible",
  "failed",
  "fails",
  "disabled",
  "blocked",
  "unavailable",
  "missing",
  "denied",
  "error",
];

function parseTimeMs(value) {
  if (!value) return 0;
  const timestamp = Date.parse(String(value));
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function formatElapsedDuration(ms) {
  const safeMs = Math.max(0, Number(ms) || 0);
  if (safeMs < 1000) return `${safeMs}ms`;
  if (safeMs < 10_000) return `${(safeMs / 1000).toFixed(1)}s`;
  if (safeMs < 60_000) return `${Math.round(safeMs / 1000)}s`;
  const minutes = Math.floor(safeMs / 60_000);
  const seconds = Math.floor((safeMs % 60_000) / 1000);
  return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
}

function extractLatencyMsFromMessage(message) {
  const text = [
    ...(asList(message?.chips).map(item => String(item || ""))),
    String(message?.detail || ""),
    String(message?.technicalDetail || ""),
  ].join(" ");
  const match = text.match(/\b(\d{2,6})\s*ms\b/i);
  if (!match) return 0;
  const value = Number(match[1]);
  return Number.isFinite(value) && value > 0 ? value : 0;
}

function tokenizeConsistencyText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .map(token => token.trim())
    .filter(token => token.length >= 4 && !CONSISTENCY_STOP_WORDS.has(token));
}

function consistencyPolarityScore(value) {
  const text = String(value || "").toLowerCase();
  let score = 0;
  for (const token of CONSISTENCY_POSITIVE_TERMS) {
    if (text.includes(token)) score += 1;
  }
  for (const token of CONSISTENCY_NEGATIVE_TERMS) {
    if (text.includes(token)) score -= 1;
  }
  if (score === 0) return 0;
  return score > 0 ? 1 : -1;
}

function detectPotentialContradiction(messages, index) {
  const current = messages[index];
  if (!current || current.role !== "assistant") return null;
  const currentText = `${current.title || ""} ${current.detail || ""}`.trim();
  const currentPolarity = consistencyPolarityScore(currentText);
  if (!currentText || currentPolarity === 0) return null;
  const currentTokens = new Set(tokenizeConsistencyText(currentText));
  if (currentTokens.size < 2) return null;

  for (let i = index - 1; i >= 0; i -= 1) {
    const previous = messages[i];
    if (!previous || previous.role !== "assistant") {
      continue;
    }
    const previousText = `${previous.title || ""} ${previous.detail || ""}`.trim();
    const previousPolarity = consistencyPolarityScore(previousText);
    if (!previousText || previousPolarity === 0 || previousPolarity === currentPolarity) {
      continue;
    }
    const previousTokens = new Set(tokenizeConsistencyText(previousText));
    const overlap = Array.from(currentTokens).filter(token => previousTokens.has(token));
    if (overlap.length >= 2) {
      return {
        subject: overlap.slice(0, 3).join(", "),
        previousId: previous.id,
      };
    }
  }
  return null;
}

function artifactBackendBaseUrl() {
  const configured =
    import.meta.env?.VITE_FLUXIO_BACKEND_URL ||
    globalThis.window?.__FLUXIO_BACKEND_URL__ ||
    "";
  return String(configured || "").trim().replace(/\/$/, "");
}

function resolveReferenceArtifactUrl(value) {
  const source = String(value || "").trim();
  if (!source) return "";
  if (/^(data:|blob:|https?:\/\/)/i.test(source)) return source;
  if (source.startsWith("/api/artifact")) return `${artifactBackendBaseUrl()}${source}`;
  const params = new URLSearchParams({ path: source });
  return `${artifactBackendBaseUrl()}/api/artifact?${params.toString()}`;
}

function artifactUrlForRecord(record) {
  if (typeof record === "string") return resolveReferenceArtifactUrl(record);
  return resolveReferenceArtifactUrl(
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

function artifactLabelForRecord(record, fallback = "generated artifact") {
  if (typeof record === "string") {
    return record.split(/[\\/]/).filter(Boolean).pop() || fallback;
  }
  return (
    record?.label ||
    record?.title ||
    record?.artifactId ||
    record?.requestId ||
    artifactLabelForRecord(record?.artifactPath || record?.path || "", fallback)
  );
}

function isImageArtifactPath(value) {
  return /\.(apng|avif|gif|jpe?g|png|svg|webp)(\?|#|$)/i.test(String(value || ""));
}

function dotToneClass(tone) {
  if (tone === "good" || tone === "completed") {
    return "good";
  }
  if (tone === "warn" || tone === "running") {
    return "warn";
  }
  if (tone === "bad" || tone === "failed") {
    return "bad";
  }
  return "neutral";
}

const HOME_CARDS = [
  {
    id: "agent",
    title: "Agent",
    copy: "Ask Fluxio to plan, build, check, and keep progress visible.",
    tone: "blue",
    icon: Sparkles,
  },
  {
    id: "builder",
    title: "Builder",
    copy: "Create and manage projects with powerful tools.",
    tone: "gold",
    icon: Hammer,
  },
  {
    id: "skills",
    title: "Skills",
    copy: "Manage reusable procedures, trigger conditions, and agent behaviors.",
    tone: "blue",
    icon: Grid2x2,
  },
  {
    id: "rule-sets",
    title: "Rule Sets",
    copy: "Control approvals, file scope, commands, runtimes, and autonomy boundaries.",
    tone: "gold",
    icon: Shield,
  },
  {
    id: "images",
    title: "Images",
    copy: "Layer, edit, compare, and continue image generations from precise manual compositions.",
    tone: "blue",
    icon: Palette,
  },
  {
    id: "workbench",
    title: "Workbench",
    copy: "Computer-use readiness, notifications, multi-lane missions, and cross-domain AI workflows.",
    tone: "blue",
    icon: Laptop,
  },
];

function RailBrand() {
  return (
    <div className="reference-brand">
      <div aria-hidden="true" className="reference-brand-mark">
        <span />
        <span />
        <span />
      </div>
      <strong>Fluxio</strong>
    </div>
  );
}

function RailItem({ active = false, icon: Icon, label, onClick, tone = "neutral" }) {
  return (
    <button
      className={cx("reference-rail-item", active && "active", `tone-${tone}`)}
      onClick={onClick}
      type="button"
    >
      <Icon size={19} strokeWidth={1.9} />
      <span>{label}</span>
    </button>
  );
}

function TopbarPill({ icon: Icon, label, active = false, dot = false, onClick }) {
  return (
    <button className={cx("reference-topbar-pill", active && "active")} onClick={onClick} type="button">
      <Icon size={17} strokeWidth={1.9} />
      <span>{label}</span>
      {dot ? <span className="reference-live-dot" /> : null}
    </button>
  );
}

function IconButton({ icon: Icon, label, onClick }) {
  return (
    <button aria-label={label} className="reference-icon-button" onClick={onClick} type="button">
      <Icon size={18} strokeWidth={1.9} />
    </button>
  );
}

function joinEditorLines(lines) {
  return asList(lines).join("\n");
}

function SidebarProfile() {
  return (
    <div className="reference-sidebar-profile">
      <div className="reference-sidebar-avatar">OP</div>
      <div className="reference-sidebar-profile-copy">
        <strong>Orbit Pro</strong>
        <span>Pro Plan</span>
      </div>
      <ChevronDown size={18} strokeWidth={1.9} />
    </div>
  );
}

function FlowSidebar({
  currentModeLabel = "Agent",
  favoriteFlows = [],
  flowProjects = [],
  onRequestAction,
  onOpenSettings,
  onSelectFlow,
  onSelectProject,
  selectedProjectId,
}) {
  return (
    <div className="reference-flow-sidebar">
      <div className="reference-mode-head">
        <strong>{currentModeLabel}</strong>
        <ChevronDown size={16} strokeWidth={1.9} />
      </div>

      <div className="reference-search-shell">
        <button
          className="reference-search-shell-action"
          onClick={() => onRequestAction?.("flow:search")}
          type="button"
        >
          <Search size={16} strokeWidth={1.9} />
          <span>Search conversations...</span>
        </button>
        <button
          aria-label="New conversation"
          className="reference-search-shell-new"
          onClick={() => onRequestAction?.("flow:new-conversation")}
          type="button"
        >
          <Edit3 size={15} strokeWidth={1.9} />
          <span>New chat</span>
        </button>
      </div>

      <section className="reference-flow-section">
        <span>Favorites</span>
        <div className="reference-favorite-list">
          {favoriteFlows.map(item => (
            <button
              className="reference-favorite-item"
              key={item.id}
              onClick={() => onSelectFlow(item.id)}
              type="button"
            >
              <span className={cx("reference-flow-dot", dotToneClass(item.tone))} />
              <strong>{item.title}</strong>
              <Star size={14} strokeWidth={1.9} />
            </button>
          ))}
        </div>
      </section>

      <section className="reference-flow-section">
        <div className="reference-flow-section-head">
          <span>Projects</span>
          <button
            className="reference-mini-icon"
            onClick={() => onRequestAction?.("flow:add-project")}
            type="button"
          >
            <Plus size={14} strokeWidth={2} />
          </button>
        </div>
        <div className="reference-project-list">
          {flowProjects.map(project => (
            <div className="reference-project-group" key={project.id}>
              <button
                className={cx("reference-project-row", project.id === selectedProjectId && "active")}
                onClick={() => onSelectProject(project.id)}
                type="button"
              >
                <div className="reference-project-row-title">
                  <FolderOpen size={15} strokeWidth={1.9} />
                  <strong>{project.title}</strong>
                </div>
                <span>{project.count}</span>
              </button>
              {project.expanded ? (
                <div className="reference-project-flows">
                  {project.flows.map(flow => (
                    <button
                      className={cx("reference-project-flow", flow.selected && "active")}
                      key={flow.id}
                      onClick={() => onSelectFlow(flow.id)}
                      type="button"
                    >
                      <div>
                        <strong>{flow.title}</strong>
                        <p>
                          <span className={cx("reference-flow-dot tiny", dotToneClass(flow.statusTone))} />
                          {flow.status}
                        </p>
                      </div>
                      <em>{flow.updated}</em>
                    </button>
                  ))}
                  {project.hasMore ? (
                    <button
                      className="reference-show-more"
                      onClick={() => {
                        onSelectProject(project.id);
                        onRequestAction?.("flow:show-all", { workspaceId: project.id });
                      }}
                      type="button"
                    >
                      Show all
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </section>

      <button className="reference-settings-rail-link" onClick={onOpenSettings} type="button">
        <Settings size={17} strokeWidth={1.9} />
        <span>Settings</span>
      </button>
    </div>
  );
}

function SurfaceField({ label, hint, children }) {
  return (
    <label className="reference-surface-field">
      <span>{label}</span>
      {children}
      {hint ? <small>{hint}</small> : null}
    </label>
  );
}

function SectionPillTabs({ tabs = [], value, onChange }) {
  return (
    <div className="reference-pill-tabs">
      {tabs.map(tab => (
        <button
          className={value === tab.value ? "active" : ""}
          key={tab.value}
          onClick={() => onChange(tab.value)}
          type="button"
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

function HomeSurface({ onOpenSurface, onRequestAction }) {
  return (
    <section className="reference-home-surface">
      <div className="reference-home-header">
        <div>
          <h1>Fluxio</h1>
          <p>Agent operating system for workspaces.</p>
        </div>
        <IconButton icon={CircleHelp} label="Help" onClick={() => onRequestAction?.("home:help")} />
      </div>

      <div className="reference-home-hero">
        <h2>What do you want to do today?</h2>
        <p>Choose your mode to get started.</p>
      </div>

      <div className="reference-home-card-row">
        {HOME_CARDS.map(card => {
          const Icon = card.icon;
          return (
            <article className={cx("reference-home-card", `tone-${card.tone}`)} key={card.id}>
              <div className="reference-home-card-icon">
                <Icon size={26} strokeWidth={1.9} />
              </div>
              <h3>{card.title}</h3>
              <p>{card.copy}</p>
              <button className={cx("reference-home-open", `tone-${card.tone}`)} onClick={() => onOpenSurface(card.id)} type="button">
                <span>Open</span>
                <ArrowUp className="reference-arrow-inline" size={16} strokeWidth={2} />
              </button>
            </article>
          );
        })}
      </div>

      <div aria-hidden="true" className="reference-home-orbit" />
    </section>
  );
}

function WorkbenchSurface({ workbenchState, onRequestAction, onSetSurface }) {
  const state = workbenchState || {};
  const computerUse = state.computerUse || {};
  const notificationEvents = asList(state.notificationEvents);
  const playgrounds = asList(state.playgrounds);
  const lanes = asList(state.lanes);
  const runtimeOps = state.runtimeOps || {};
  const tutorials = state.tutorials || {};
  const coverage = state.coverage || {};
  const ideaPlanner = state.ideaPlanner || {};
  const providerCatalog = state.providerCatalog || {};
  const liveReview = state.liveReview || {};
  const reviewEvents = asList(liveReview.events);
  const annotations = asList(liveReview.annotationReadiness?.blocks);
  const replayMarkers = useMemo(
    () =>
      reviewEvents
        .flatMap(event =>
          asList(event.replayMarkers).map(marker => ({
            ...marker,
            eventId: event.id || `${event.kind}-${event.title}`,
          })),
        )
        .filter(marker => marker?.id),
    [reviewEvents],
  );
  const reviewEventsById = useMemo(
    () => new Map(reviewEvents.map(event => [event.id || `${event.kind}-${event.title}`, event])),
    [reviewEvents],
  );
  const [selectedLiveReviewEventId, setSelectedLiveReviewEventId] = useState(
    () => reviewEvents[0]?.id || "",
  );
  useEffect(() => {
    if (!reviewEvents.length) {
      if (selectedLiveReviewEventId) {
        setSelectedLiveReviewEventId("");
      }
      return;
    }
    const match = reviewEventsById.get(selectedLiveReviewEventId);
    if (!match) {
      setSelectedLiveReviewEventId(reviewEvents[0]?.id || "");
    }
  }, [reviewEvents, reviewEventsById, selectedLiveReviewEventId]);
  const selectedLiveReviewEvent =
    reviewEventsById.get(selectedLiveReviewEventId) || reviewEvents[0] || null;
  const selectedScreenshotFrames = asList(selectedLiveReviewEvent?.screenshotFrames);
  const [selectedScreenshotFrameId, setSelectedScreenshotFrameId] = useState(
    () => selectedScreenshotFrames[0]?.id || "",
  );
  useEffect(() => {
    if (!selectedScreenshotFrames.length) {
      if (selectedScreenshotFrameId) {
        setSelectedScreenshotFrameId("");
      }
      return;
    }
    const hasFrame = selectedScreenshotFrames.some(frame => frame?.id === selectedScreenshotFrameId);
    if (!hasFrame) {
      setSelectedScreenshotFrameId(selectedScreenshotFrames[0]?.id || "");
    }
  }, [selectedScreenshotFrameId, selectedScreenshotFrames]);
  const selectedScreenshotFrame =
    selectedScreenshotFrames.find(frame => frame?.id === selectedScreenshotFrameId) ||
    selectedScreenshotFrames[0] ||
    null;
  const [selectedReplayMarkerId, setSelectedReplayMarkerId] = useState(() => replayMarkers[0]?.id || "");
  useEffect(() => {
    if (!replayMarkers.length) {
      if (selectedReplayMarkerId) {
        setSelectedReplayMarkerId("");
      }
      return;
    }
    const exists = replayMarkers.some(marker => marker?.id === selectedReplayMarkerId);
    if (!exists) {
      setSelectedReplayMarkerId(replayMarkers[0]?.id || "");
    }
  }, [replayMarkers, selectedReplayMarkerId]);
  const selectedReplayMarker = replayMarkers.find(marker => marker?.id === selectedReplayMarkerId) || null;
  const [isTimelapsePlaying, setIsTimelapsePlaying] = useState(false);
  const markerFrameMap = useMemo(() => {
    return replayMarkers.map((marker, index) => {
      const linkedFrameIndex = selectedScreenshotFrames.findIndex(frame => {
        if (!frame) {
          return false;
        }
        return (
          (marker?.snapshotPath && frame.path === marker.snapshotPath) ||
          (marker?.snapshotPath && frame.id === marker.snapshotPath) ||
          (marker?.frameId && frame.id === marker.frameId)
        );
      });
      return {
        ...marker,
        frameIndex: linkedFrameIndex >= 0 ? linkedFrameIndex : Math.min(index, Math.max(selectedScreenshotFrames.length - 1, 0)),
      };
    });
  }, [replayMarkers, selectedScreenshotFrames]);
  const selectedMarkerIndex = Math.max(
    0,
    markerFrameMap.findIndex(marker => marker?.id === selectedReplayMarkerId),
  );
  useEffect(() => {
    if (!selectedReplayMarker?.eventId) {
      return;
    }
    const activeEventId = selectedLiveReviewEvent?.id || `${selectedLiveReviewEvent?.kind}-${selectedLiveReviewEvent?.title}`;
    if (selectedReplayMarker.eventId === activeEventId) {
      return;
    }
    setSelectedLiveReviewEventId(selectedReplayMarker.eventId);
  }, [selectedLiveReviewEvent, selectedReplayMarker]);
  useEffect(() => {
    if (!selectedReplayMarker?.snapshotPath || !selectedScreenshotFrames.length) {
      return;
    }
    const linkedFrame =
      selectedScreenshotFrames.find(frame => frame?.path === selectedReplayMarker.snapshotPath) ||
      selectedScreenshotFrames.find(frame => frame?.id === selectedReplayMarker.snapshotPath) ||
      null;
    if (linkedFrame?.id && linkedFrame.id !== selectedScreenshotFrameId) {
      setSelectedScreenshotFrameId(linkedFrame.id);
    }
  }, [selectedReplayMarker, selectedScreenshotFrames, selectedScreenshotFrameId]);
  useEffect(() => {
    if (!isTimelapsePlaying || markerFrameMap.length <= 1) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      const nextMarker = markerFrameMap[(selectedMarkerIndex + 1) % markerFrameMap.length];
      if (!nextMarker) {
        return;
      }
      setSelectedReplayMarkerId(nextMarker.id || "");
      const nextFrame = selectedScreenshotFrames[nextMarker.frameIndex] || null;
      if (nextFrame?.id) {
        setSelectedScreenshotFrameId(nextFrame.id);
      }
    }, 1800);
    return () => window.clearInterval(timer);
  }, [isTimelapsePlaying, markerFrameMap, selectedMarkerIndex, selectedScreenshotFrames]);
  const selectedEventArtifacts = asList(selectedLiveReviewEvent?.artifactPaths);
  const selectedEventBrowserActions = asList(selectedLiveReviewEvent?.browserActions);
  const selectedEventPrograms = asList(selectedLiveReviewEvent?.launchedPrograms);
  const selectedEventTests = asList(selectedLiveReviewEvent?.tests);
  const selectedEventProviderEvents = asList(selectedLiveReviewEvent?.providerEvents);
  const selectedEventLayerHandoff = asList(selectedLiveReviewEvent?.layerHandoff);
  const selectedEventQueueTimeline = asList(selectedLiveReviewEvent?.queueTimeline);
  const selectedEventGeneratedImages = asList(selectedLiveReviewEvent?.generatedImages);
  const selectedEventAcknowledgedBy = asList(selectedLiveReviewEvent?.acknowledgedBy);
  const selectedEventOperatorMessages = asList(selectedLiveReviewEvent?.operatorMessages);
  const normalizedComputerStatus = String(computerUse.status || "").trim().toLowerCase();
  const computerState = (() => {
    if (!normalizedComputerStatus || normalizedComputerStatus === "unavailable" || normalizedComputerStatus === "unknown") {
      return {
        key: "empty",
        tone: "neutral",
        title: "Computer-use is not configured yet",
        body: "Connect a runtime lane to enable browser/desktop handoff and live task execution.",
        actions: [
          { id: "workbench:computer-use", label: "Open control lane" },
          { id: "workbench:notification-settings", label: "Check notification wiring" },
        ],
      };
    }
    if (normalizedComputerStatus.includes("error") || normalizedComputerStatus.includes("fail")) {
      return {
        key: "error",
        tone: "bad",
        title: "Computer-use reported a failure",
        body: computerUse.handoffHint || "A runtime or handoff step failed. Inspect lane state and retry after fixing connection issues.",
        actions: [
          { id: "workbench:computer-use", label: "Open control lane" },
          { id: "workbench:notification-settings", label: "Check failure notifications" },
        ],
      };
    }
    if (normalizedComputerStatus.includes("loading") || normalizedComputerStatus.includes("starting") || normalizedComputerStatus.includes("boot")) {
      return {
        key: "loading",
        tone: "warn",
        title: "Computer-use is starting",
        body: computerUse.handoffHint || "Runtime services are initializing. Keep this panel open for readiness updates.",
        actions: [
          { id: "workbench:computer-use", label: "Open control lane" },
          { id: "live:refresh-preview", label: "Refresh status" },
        ],
      };
    }
    return {
      key: "active",
      tone: "good",
      title: "Computer-use is active",
      body: computerUse.handoffHint || "Desktop/browser runtime handoff points are available.",
      actions: [
        { id: "workbench:computer-use", label: "Open control lane" },
        { id: "agent:follow-up", label: "Open mission handoff" },
      ],
    };
  })();

  return (
    <section className="reference-workbench-surface">
      <div className="reference-builder-head">
        <div>
          <h1>AI Workbench</h1>
          <p>Cross-domain mission control for computer use, notifications, tutorials, and parallel lanes.</p>
        </div>
      </div>

      <div className="reference-settings-summary-grid">
        <article>
          <span>Computer-use status</span>
          <strong>{titleizeToken(computerUse.status || "unavailable")}</strong>
        </article>
        <article>
          <span>Safety mode</span>
          <strong>{titleizeToken(computerUse.safetyMode || "guided")}</strong>
        </article>
        <article>
          <span>Runtime</span>
          <strong>{computerUse.runtimeLabel || "not-wired"}</strong>
        </article>
        <article>
          <span>Active lanes</span>
          <strong>{lanes.length}</strong>
        </article>
      </div>

      <RuntimeOperationsPanel
        runtimeOps={runtimeOps}
        onRequestAction={onRequestAction}
        onSetSurface={onSetSurface}
      />

      <div className="builder-live-review-layout">
        <article className="builder-live-review-panel">
          <div className="builder-live-review-meta">
            <strong>Live Review Timeline</strong>
            <span>{liveReview.statusLine || "Live review stream"}</span>
          </div>
          <div className="builder-live-review-events">
            {reviewEvents.length ? reviewEvents.map(event => {
              const eventId = event.id || `${event.kind}-${event.title}`;
              const active = selectedLiveReviewEvent?.id === event.id;
              return (
                <button
                  className={cx("builder-live-review-event", active && "active")}
                  key={eventId}
                  onClick={() => setSelectedLiveReviewEventId(event.id || "")}
                  type="button"
                >
                  <div className="builder-live-review-event-group">
                    <strong>{event.label || titleizeToken(event.kind || "event")}</strong>
                    <span>{event.timestamp || "now"}</span>
                  </div>
                  <p>{event.title || "Untitled event"}</p>
                  <p className="reference-surface-footnote">{event.detail || "No detail yet."}</p>
                  {asList(event.queueTimeline).length ? (
                    <div className="builder-live-review-queue-strip">
                      {asList(event.queueTimeline).map(item => <span key={item}>{titleizeToken(item)}</span>)}
                    </div>
                  ) : null}
                  {asList(event.generatedImages).length ? (
                    <div className="builder-live-review-queue-strip">
                      {asList(event.generatedImages).map(item => (
                        <span key={item.path || item.label}>{item.label || item.path}</span>
                      ))}
                    </div>
                  ) : null}
                </button>
              );
            }) : <p className="reference-surface-footnote">No live review events yet.</p>}
          </div>
          {selectedLiveReviewEvent ? (
            <div
              className="builder-live-review-focus"
              onKeyDown={event => {
                if (selectedScreenshotFrames.length <= 1) {
                  return;
                }
                const currentIndex = selectedScreenshotFrames.findIndex(frame => frame?.id === selectedScreenshotFrameId);
                if (event.key === "ArrowLeft") {
                  event.preventDefault();
                  const target =
                    selectedScreenshotFrames[currentIndex - 1] ||
                    selectedScreenshotFrames[selectedScreenshotFrames.length - 1] ||
                    null;
                  setSelectedScreenshotFrameId(target?.id || "");
                }
                if (event.key === "ArrowRight") {
                  event.preventDefault();
                  const target = selectedScreenshotFrames[currentIndex + 1] || selectedScreenshotFrames[0] || null;
                  setSelectedScreenshotFrameId(target?.id || "");
                }
              }}
              role="region"
              tabIndex={0}
            >
              <div className="builder-live-review-event-group">
                <strong>{selectedLiveReviewEvent.title || "Selected review event"}</strong>
                <span>{titleizeToken(selectedLiveReviewEvent.kind || "event")}</span>
              </div>
              <p className="reference-surface-footnote">{selectedLiveReviewEvent.detail || "No detail yet."}</p>
              <div className="builder-live-review-controls">
                <button
                  className="reference-outline-button"
                  onClick={() => onRequestAction?.("live:rewind-marker", { eventId: selectedLiveReviewEvent.id })}
                  type="button"
                >
                  Rewind marker
                </button>
                <button
                  className="reference-outline-button"
                  disabled={selectedScreenshotFrames.length <= 1}
                  onClick={() => {
                    const index = selectedScreenshotFrames.findIndex(frame => frame?.id === selectedScreenshotFrameId);
                    const target = selectedScreenshotFrames[index - 1] || selectedScreenshotFrames[selectedScreenshotFrames.length - 1] || null;
                    setSelectedScreenshotFrameId(target?.id || "");
                  }}
                  type="button"
                >
                  Previous frame
                </button>
                <button
                  className="reference-outline-button"
                  disabled={selectedScreenshotFrames.length <= 1}
                  onClick={() => {
                    const index = selectedScreenshotFrames.findIndex(frame => frame?.id === selectedScreenshotFrameId);
                    const target = selectedScreenshotFrames[index + 1] || selectedScreenshotFrames[0] || null;
                    setSelectedScreenshotFrameId(target?.id || "");
                  }}
                  type="button"
                >
                  Next frame
                </button>
              </div>
              <p className="reference-surface-footnote">
                Use ←/→ to step frames. {selectedScreenshotFrames.length} frame(s) tracked.
              </p>
              {selectedScreenshotFrames.length ? (
                <div className="builder-live-review-frame-strip">
                  {selectedScreenshotFrames.map((frame, index) => {
                    const active = frame?.id === selectedScreenshotFrameId;
                    return (
                      <button
                        className={cx("builder-live-review-frame-thumb", active && "active")}
                        key={frame?.id || `frame-${index}`}
                        onClick={() => setSelectedScreenshotFrameId(frame?.id || "")}
                        type="button"
                      >
                        {frame?.path ? (
                          <img
                            alt={`${frame?.label || `Frame ${index + 1}`} preview`}
                            className="builder-live-review-frame-image"
                            loading="lazy"
                            src={frame.path}
                          />
                        ) : (
                          <span className="builder-live-review-frame-image placeholder">No preview image</span>
                        )}
                        <strong>{frame?.label || `Frame ${index + 1}`}</strong>
                        <span>{frame?.timestamp || ""}</span>
                      </button>
                    );
                  })}
                </div>
              ) : null}
              {markerFrameMap.length ? (
                <div className="builder-live-review-timeline-rail">
                  <div className="builder-live-review-timeline-head">
                    <strong>Marker-to-frame timeline rail</strong>
                    <small>Direct scrubber drag and timelapse sync</small>
                  </div>
                  <input
                    aria-label="Marker timeline scrubber"
                    className="builder-live-review-scrubber"
                    max={Math.max(markerFrameMap.length - 1, 0)}
                    min={0}
                    onChange={event => {
                      const marker = markerFrameMap[Math.max(0, Number(event.target.value) || 0)] || null;
                      if (!marker) {
                        return;
                      }
                      setSelectedReplayMarkerId(marker.id || "");
                      const frame = selectedScreenshotFrames[marker.frameIndex] || null;
                      if (frame?.id) {
                        setSelectedScreenshotFrameId(frame.id);
                      }
                    }}
                    type="range"
                    value={selectedMarkerIndex}
                  />
                  <div className="builder-live-review-marker-buttons">
                    {markerFrameMap.map(marker => (
                      <button
                        className={cx("builder-live-review-marker-pill", marker.id === selectedReplayMarkerId && "active")}
                        key={marker.id}
                        onClick={() => {
                          setSelectedReplayMarkerId(marker.id || "");
                          const frame = selectedScreenshotFrames[marker.frameIndex] || null;
                          if (frame?.id) {
                            setSelectedScreenshotFrameId(frame.id);
                          }
                        }}
                        type="button"
                      >
                        <strong>{marker.label || marker.id}</strong>
                        <span>{marker.timestamp || ""}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
              {replayMarkers.length ? (
                <div className="builder-live-review-marker-jump">
                  <span>Marker jump</span>
                  <select
                    onChange={event => setSelectedReplayMarkerId(event.target.value)}
                    value={selectedReplayMarkerId}
                  >
                    {replayMarkers.map(marker => (
                      <option key={marker.id} value={marker.id}>
                        {marker.label || marker.id}
                      </option>
                    ))}
                  </select>
                  <button
                    className="reference-outline-button"
                    onClick={() =>
                      onRequestAction?.("live:jump-marker", {
                        markerId: selectedReplayMarker?.id,
                        snapshotPath: selectedReplayMarker?.snapshotPath,
                      })
                    }
                    type="button"
                  >
                    Jump to frame
                  </button>
                  <button
                    className="reference-outline-button"
                    disabled={markerFrameMap.length <= 1}
                    onClick={() => setIsTimelapsePlaying(value => !value)}
                    type="button"
                  >
                    {isTimelapsePlaying ? "Pause timelapse" : "Autoplay timelapse"}
                  </button>
                </div>
              ) : null}
              {selectedScreenshotFrame ? (
                <p className="reference-surface-footnote" aria-live="polite">
                  Frame: {selectedScreenshotFrame.label || selectedScreenshotFrame.id} · {selectedScreenshotFrame.path || "no path"}
                </p>
              ) : null}
            </div>
          ) : null}
        </article>

        <aside className="builder-live-review-sidepanel" aria-label="Live Preview Side Panel">
          <article className="builder-live-review-panel">
            <div className="builder-live-review-meta">
              <strong>Live Preview Side Panel</strong>
              <span>Selected event detail, replay hooks, and runtime payloads</span>
            </div>
            {selectedLiveReviewEvent ? (
              <div className="builder-live-review-event-details" aria-live="polite">
                <div className="builder-live-review-event-group">
                  <strong>{selectedLiveReviewEvent.title || "Selected review event"}</strong>
                  <span>
                    {titleizeToken(selectedLiveReviewEvent.kind || "event")} · {selectedLiveReviewEvent.timestamp || "now"}
                  </span>
                </div>
                <p>{selectedLiveReviewEvent.detail || "No detail yet."}</p>
                <p className="reference-surface-footnote">
                  {selectedScreenshotFrame ? `Screenshot frame: ${selectedScreenshotFrame.path || "none"}` : "No screenshot frame selected."}
                </p>
                <div className="builder-live-review-sidegroup">
                  <span>UI review hooks</span>
                  <div className="reference-inline-actions compact">
                    <button
                      className="reference-outline-button"
                      onClick={() => onRequestAction?.("live:open-proof", { sourceEventId: selectedLiveReviewEvent.id })}
                      type="button"
                    >
                      Open proof pane
                    </button>
                    <button
                      className="reference-outline-button"
                      onClick={() => onRequestAction?.("live:open-thread", { sourceEventId: selectedLiveReviewEvent.id })}
                      type="button"
                    >
                      Open thread pane
                    </button>
                    <button
                      className="reference-outline-button"
                      onClick={() =>
                        onRequestAction?.("live:open-marker-context", {
                          markerId: selectedReplayMarker?.id,
                          snapshotPath: selectedReplayMarker?.snapshotPath,
                        })
                      }
                      type="button"
                    >
                      Marker context
                    </button>
                  </div>
                </div>
                {selectedEventBrowserActions.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Browser QA actions</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventBrowserActions.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedEventPrograms.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Launched programs</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventPrograms.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedEventTests.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Verification tests</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventTests.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedEventProviderEvents.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Image provider events</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventProviderEvents.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedEventQueueTimeline.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Image queue timeline</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventQueueTimeline.map(item => <span key={item}>{titleizeToken(item)}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedEventLayerHandoff.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Layer handoff</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventLayerHandoff.map(item => <span key={item}>{titleizeToken(item)}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedEventGeneratedImages.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Generated images</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventGeneratedImages.map(item => (
                        <span key={item.path || item.label}>{item.label || item.path}</span>
                      ))}
                    </div>
                  </div>
                ) : null}
                {selectedEventArtifacts.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Artifact paths</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventArtifacts.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedEventOperatorMessages.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Operator follow-up messages</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventOperatorMessages.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedEventAcknowledgedBy.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Operator acknowledgements</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedEventAcknowledgedBy.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedLiveReviewEvent?.progressUpdate ? (
                  <div className="builder-live-review-sidegroup">
                    <span>10-20 minute update payload</span>
                    <p className="reference-surface-footnote">
                      Changed: {selectedLiveReviewEvent.progressUpdate.changed} · Blocker: {selectedLiveReviewEvent.progressUpdate.blocker} · Tests: {selectedLiveReviewEvent.progressUpdate.tests} · Next: {selectedLiveReviewEvent.progressUpdate.next}
                    </p>
                  </div>
                ) : null}
                <div className="builder-live-review-sidegroup builder-live-coworking-bridge">
                  <span>Co-working bridge contract</span>
                  <div className="builder-live-coworking-grid" aria-label="Structured feedback into agent mission bridge">
                    <article>
                      <b>Route/model/task context</b>
                      <small>Route: {selectedLiveReviewEvent.routeContext || selectedLiveReviewEvent.deepLink?.route || "current review route"}</small>
                      <small>Model: {selectedLiveReviewEvent.modelContext || selectedLiveReviewEvent.provider || "planner/executor default"}</small>
                      <small>Task: {selectedLiveReviewEvent.taskContext || selectedLiveReviewEvent.title || "selected event"}</small>
                    </article>
                    <article>
                      <b>Verifier feedback loop</b>
                      <small>{selectedLiveReviewEvent.verifierFeedback || selectedLiveReviewEvent.progressUpdate?.tests || "Awaiting focused verifier note"}</small>
                      <button
                        className="reference-outline-button"
                        onClick={() => onRequestAction?.("agent:structured-feedback", {
                          sourceEventId: selectedLiveReviewEvent.id,
                          routeContext: selectedLiveReviewEvent.routeContext || selectedLiveReviewEvent.deepLink?.route,
                          taskContext: selectedLiveReviewEvent.taskContext || selectedLiveReviewEvent.title,
                          verifierFeedback: selectedLiveReviewEvent.verifierFeedback || selectedLiveReviewEvent.progressUpdate?.tests,
                        })}
                        type="button"
                      >
                        Send structured feedback
                      </button>
                    </article>
                    <article>
                      <b>Activity/timelapse evidence</b>
                      <small>{selectedScreenshotFrames.length} frames · {replayMarkers.length} markers · {selectedEventArtifacts.length} artifacts</small>
                      <small>Status updates: {selectedLiveReviewEvent.progressUpdate ? "captured" : "not captured yet"}</small>
                    </article>
                  </div>
                </div>
                {selectedLiveReviewEvent?.selectedSkills?.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Planner selected skills</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedLiveReviewEvent.selectedSkills.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedLiveReviewEvent?.plannerRules?.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Planner rules</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedLiveReviewEvent.plannerRules.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedLiveReviewEvent?.designPrompts?.length ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Design prompts</span>
                    <div className="builder-live-review-queue-strip">
                      {selectedLiveReviewEvent.designPrompts.map(item => <span key={item}>{item}</span>)}
                    </div>
                  </div>
                ) : null}
                {selectedLiveReviewEvent?.nextIdea ? (
                  <div className="builder-live-review-sidegroup">
                    <span>Next idea handoff</span>
                    <p className="reference-surface-footnote">{selectedLiveReviewEvent.nextIdea}</p>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="reference-surface-footnote">Select a live review event to inspect detail.</p>
            )}
          </article>

          <article className="builder-live-review-panel">
            <div className="builder-live-review-meta">
              <strong>Browser annotations</strong>
              <span>Pins, rectangles, severity, notes, and recovery actions</span>
            </div>
            <div className="builder-live-annotation-map">
              {annotations.map(item => item.rectangle ? (
                <span
                  className="builder-live-annotation-rect"
                  key={`${item.id}-rect`}
                  style={{ left: `${item.rectangle.x}%`, top: `${item.rectangle.y}%`, width: `${item.rectangle.width}%`, height: `${item.rectangle.height}%` }}
                />
              ) : (
                <span
                  className="builder-live-annotation-pin"
                  key={`${item.id}-pin`}
                  style={{ left: `${item.pin?.x || 0}%`, top: `${item.pin?.y || 0}%` }}
                />
              ))}
            </div>
            <div className="builder-live-annotation-list">
              {annotations.length ? annotations.map(item => (
                <article className={cx("builder-live-annotation-item", `severity-${item.severity || "low"}`)} key={item.id}>
                  <div className="builder-live-review-event-group">
                    <strong>{item.label}</strong>
                    <span>{titleizeToken(item.severity)}</span>
                  </div>
                  <p>{item.note}</p>
                  <p className="reference-surface-footnote">Page/layer: {item.page || "unknown"} · {item.rectangle?.layer || item.pin?.layer || "preview"}</p>
                  <p className="reference-surface-footnote">Recovery: {item.recoveryAction}</p>
                </article>
              )) : <p className="reference-surface-footnote">No annotation targets yet.</p>}
            </div>
          </article>
        </aside>
      </div>

      <div className="reference-settings-grid">
        <article className="reference-settings-card">
          <strong>Computer-use readiness</strong>
          <div className={cx("reference-workbench-state-card", `tone-${computerState.tone}`)}>
            <div className="reference-workbench-state-head">
              <p className="reference-workbench-state-kicker">State · {titleizeToken(computerState.key)}</p>
              <strong>{computerState.title}</strong>
            </div>
            <p>{computerState.body}</p>
            <div className="reference-workbench-state-meta">
              <p className="reference-surface-footnote">Current screen: {computerUse.currentScreen || "Not reported"}</p>
              <p className="reference-surface-footnote">Current task: {computerUse.currentTask || "Not reported"}</p>
            </div>
            <div className="reference-inline-actions stretch">
              {computerState.actions.map(action => (
                <button
                  className={action.id === "agent:follow-up" ? "reference-black-button" : "reference-outline-button"}
                  key={action.id}
                  onClick={() => {
                    if (action.id === "agent:follow-up") {
                      onSetSurface?.("agent");
                      return;
                    }
                    onRequestAction?.(action.id);
                  }}
                  type="button"
                >
                  {action.label}
                </button>
              ))}
            </div>
          </div>
        </article>

        <article className="reference-settings-card">
          <strong>Notification layer</strong>
          <div className="reference-builder-change-list">
            {notificationEvents.map(item => (
              <div className="reference-builder-change-row" key={item.id}>
                <span className={cx("reference-flow-dot", item.count > 0 ? "warn" : "good")} />
                <p>
                  {item.label}: {item.count} · {item.detail}
                </p>
              </div>
            ))}
          </div>
          <button className="reference-outline-button" onClick={() => onRequestAction?.("workbench:notification-settings")} type="button">Configure digest + events</button>
        </article>
      </div>

      <article className="reference-settings-card">
        <strong>Modular playgrounds</strong>
        <div className="reference-provider-grid">
          {playgrounds.map(item => (
            <article className="reference-provider-card" key={item.id}>
              <strong>{item.label}</strong>
              <p>Status: {titleizeToken(item.status)}</p>
              <button
                className="reference-link-button"
                onClick={() => {
                  if (item.id === "image") {
                    onSetSurface?.("images");
                    return;
                  }
                  onRequestAction?.(`workbench:${item.action || item.id}`);
                }}
                type="button"
              >
                Open
              </button>
            </article>
          ))}
        </div>
      </article>

      <div className="reference-settings-grid">
        <article className="reference-settings-card">
          <strong>Code study and coverage</strong>
          <p>{coverage.summary || "Coverage summary unavailable."}</p>
          <p className="reference-surface-footnote">Known gaps: {coverage.gapCount || 0}</p>
          <div className="reference-builder-change-list">
            {asList(coverage.files).length ? asList(coverage.files).map(item => <div className="reference-builder-change-row" key={item}><p>{item}</p></div>) : <p className="reference-surface-footnote">No files surfaced yet.</p>}
          </div>
          <button className="reference-outline-button" onClick={() => onRequestAction?.("workbench:study-plan")} type="button">Generate study plan</button>
        </article>

        <article className="reference-settings-card">
          <strong>Tutorials and onboarding</strong>
          <p>{tutorials.headline || "Contextual onboarding"}</p>
          <div className="reference-builder-change-list">
            {asList(tutorials.steps).map(step => (
              <div className="reference-builder-change-row" key={step.id || step.title}>
                <span className={cx("reference-flow-dot", step.done ? "good" : step.current ? "warn" : "neutral")} />
                <p>{step.title} · {step.status}</p>
              </div>
            ))}
          </div>
          <button className="reference-outline-button" onClick={() => onRequestAction?.("workbench:tutorial-help")} type="button">Open contextual help</button>
        </article>
      </div>

      <div className="reference-settings-grid">
        <article className="reference-settings-card">
          <strong>Idea generation loop</strong>
          <p>{ideaPlanner.headline || "Planner"}</p>
          <div className="reference-builder-change-list">
            {asList(ideaPlanner.ideas).map(item => (
              <div className="reference-builder-change-row" key={item.id}>
                <p>{item.title} · score {item.score} · {item.reason}</p>
              </div>
            ))}
          </div>
          <button className="reference-black-button" onClick={() => onRequestAction?.("workbench:promote-idea")} type="button">Promote selected idea to mission</button>
        </article>

        <article className="reference-settings-card">
          <strong>Multi-mission lanes and model flexibility</strong>
          <p className="reference-surface-footnote">Lanes can run concurrently with independent runtime/provider/model selections.</p>
          <div className="reference-builder-change-list">
            {lanes.length ? lanes.map(item => (
              <div className="reference-builder-change-row" key={item.id}>
                <p>{item.label} · {item.provider}/{item.model} · {item.status} · {item.lastEvent}</p>
              </div>
            )) : <p className="reference-surface-footnote">No active lanes from backend snapshot.</p>}
          </div>
          <p className="reference-surface-footnote">Available providers: {asList(providerCatalog.providers).join(", ") || "none"}</p>
        </article>
      </div>
    </section>
  );
}

function ComposerDock({
  compact = false,
  draft,
  onChangeDraft,
  onPaste,
  onAttach,
  onDictation,
  onSubmit,
  placeholder,
  children,
}) {
  return (
    <form className={cx("reference-composer", compact && "compact")} onSubmit={event => event.preventDefault()}>
      <textarea
        onChange={event => onChangeDraft(event.target.value)}
        onKeyDown={event => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            onSubmit?.();
          }
        }}
        onPaste={onPaste}
        placeholder={placeholder}
        value={draft}
      />
      {children}
      <div className="reference-composer-footer">
        <div className="reference-composer-tools">
          <button className="reference-tool-button" onClick={onAttach} type="button">
            <Paperclip size={18} strokeWidth={1.9} />
          </button>
          <button className="reference-tool-button" onClick={onDictation} type="button">
            <Mic size={18} strokeWidth={1.9} />
          </button>
        </div>
        <button className="reference-send-button" onClick={onSubmit} type="button">
          <ArrowUp size={22} strokeWidth={2.1} />
        </button>
      </div>
    </form>
  );
}

function ConfigCard({ title, titleIcon: Icon, accent = "neutral", children, footer, copy }) {
  return (
    <article className={cx("reference-config-card", `tone-${accent}`)}>
      <div className="reference-config-card-head">
        <div className="reference-config-title">
          <Icon size={18} strokeWidth={1.9} />
          <strong>{title}</strong>
        </div>
        <CircleHelp size={15} strokeWidth={1.8} />
      </div>
      <div className="reference-config-card-body">{children}</div>
      {copy ? <p className="reference-config-copy">{copy}</p> : null}
      {footer ? <div className="reference-config-footer">{footer}</div> : null}
    </article>
  );
}

function MetricLine({ label, value }) {
  return (
    <div className="reference-inline-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function RuntimeCapabilityPills({ capabilities = [] }) {
  if (!capabilities.length) {
    return <p className="reference-surface-footnote">No runtime capabilities were reported yet.</p>;
  }
  return (
    <div className="reference-chip-row">
      {capabilities.map(item => (
        <span className="reference-mini-pill" key={item.key || item.label}>
          {item.label}
        </span>
      ))}
    </div>
  );
}

function SlashCommandPanel({ className, commands = [], draft = "", onUseCommand }) {
  const query = String(draft || "").trim().toLowerCase();
  const filteredCommands = query.startsWith("/")
    ? commands.filter(item => {
        const haystack = `${item.command} ${item.label || ""} ${item.detail || ""} ${item.harness || ""} ${item.kind || ""}`.toLowerCase();
        return haystack.includes(query);
      })
    : commands;
  const priorityFor = item => {
    const kind = String(item.kind || "").toLowerCase();
    if (kind === "comment") {
      return 0;
    }
    if (kind === "skill") {
      return 1;
    }
    if (kind === "codex") {
      return 3;
    }
    return 2;
  };
  const visibleCommands = filteredCommands
    .slice()
    .sort((left, right) => priorityFor(left) - priorityFor(right))
    .slice(0, 8);
  const commandTitle = item => item.label || item.command;
  const commandBadge = item => {
    const kind = String(item.kind || item.harness || "command").toLowerCase();
    if (kind === "skill") {
      return "S";
    }
    if (kind === "comment") {
      return "C";
    }
    if (kind === "codex") {
      return "Cx";
    }
    return "/";
  };

  return (
    <article className={cx("reference-support-panel reference-slash-panel", className)}>
      <div className="reference-builder-section-head">
        <div>
          <strong>Slash Commands</strong>
          <span>
            {query.startsWith("/")
              ? "Filtered by the composer. Clicking inserts the command."
              : "Built from the active runtime command catalog and local installed skills."}
          </span>
        </div>
      </div>
      {visibleCommands.length > 0 ? (
        <div className="reference-command-grid">
          {visibleCommands.map(item => (
            <button
              className={cx("reference-command-card", item.kind && `kind-${item.kind}`)}
              key={`${item.harness}-${item.command}`}
              onClick={() => onUseCommand(item.command)}
              type="button"
            >
              <div className="reference-command-head">
                <span className="reference-command-token">{commandBadge(item)}</span>
                <strong>{commandTitle(item)}</strong>
                <span>{item.harness}</span>
              </div>
              {item.label ? <code>{item.command}</code> : null}
              <p>{item.detail}</p>
            </button>
          ))}
        </div>
      ) : (
        <p className="reference-surface-footnote">No slash commands match the current draft.</p>
      )}
    </article>
  );
}

function AgentIdleSurface(props) {
  const {
    draft,
    onUseSlashCommand,
    selectedRuntime,
    runtimeOptions,
    runtimeStatus,
    selectedModelLabel,
    selectedEffortLabel,
    selectedHarnessMeta = [],
    slashCommands = [],
    onAttach,
    onChangeDraft,
    onDictation,
    onIdleSubmit,
    onRequestAction,
    onPaste,
    onRuntimeChange,
    routeControls = {},
  } = props;
  const showSlashCommands = String(draft || "").trim().startsWith("/");
  const selectedRoute = routeControls.selectedRoute || {};
  const routeOptions = routeControls.routeOptions || {};
  const actionModes = routeControls.actionModes || [];
  const routeRows = asList(routeOptions.roles).map(role => ({
    role,
    route:
      routeControls.routeByRole?.[role] ||
      (role === routeControls.role ? selectedRoute : null) ||
      {},
  }));

  return (
    <section className="reference-agent-idle">
      <div className="reference-surface-intro">
        <h1>What are we working on today?</h1>
        <p>Describe your task or ask anything.</p>
      </div>

      <ComposerDock
        draft={draft}
        onAttach={onAttach}
        onChangeDraft={onChangeDraft}
        onDictation={onDictation}
        onPaste={onPaste}
        onSubmit={onIdleSubmit}
        placeholder="Ask your agent anything..."
      >
        {actionModes.length > 0 ? (
          <div className="reference-mode-strip" aria-label="Run mode">
            {actionModes.map(option => (
              <button
                className={routeControls.actionMode === option.value ? "active" : ""}
                key={`composer-mode-${option.value}`}
                onClick={() => routeControls.onActionModeChange?.(option.value)}
                type="button"
              >
                {option.label}
              </button>
            ))}
          </div>
        ) : null}
        {showSlashCommands ? (
          <SlashCommandPanel
            className="in-composer"
            commands={slashCommands}
            draft={draft}
            onUseCommand={onUseSlashCommand}
          />
        ) : null}
      </ComposerDock>

      <div className="reference-config-grid compact">
        <ConfigCard
          accent="neutral"
          copy={runtimeStatus?.detected ? "Work engine ready for launch." : "Syntelos checks this automatically before the first run."}
          title="Work engine"
          titleIcon={WandSparkles}
        >
          <label className="reference-select-shell">
            <select onChange={event => onRuntimeChange(event.target.value)} value={selectedRuntime}>
              {runtimeOptions.map(option => (
                <option key={`idle-runtime-${option.value}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          {selectedHarnessMeta.length > 0 ? (
            <div className="reference-card-metric-stack">
              {selectedHarnessMeta.map(item => (
                <MetricLine key={`${item.label}-${item.value}`} label={item.label} value={item.value} />
              ))}
            </div>
          ) : null}
        </ConfigCard>

        <ConfigCard
          accent="neutral"
          copy="Planner, executor, and verifier roles route automatically by phase. You only tune provider/model per role."
          title="Model Routes"
          titleIcon={Bot}
        >
          <div className="reference-route-matrix compact">
            {routeRows.map(({ role, route }) => (
              <article className={routeControls.role === role ? "active" : ""} key={`route-row-${role}`}>
                <button onClick={() => routeControls.onRoleChange?.(role)} type="button">
                  {titleizeToken(role)}
                </button>
                <select
                  aria-label={`${role} provider`}
                  onChange={event => routeControls.onRoleFieldChange?.(role, "provider", event.target.value)}
                  value={route.provider || "openai"}
                >
                  {asList(routeOptions.providers).map(option => (
                    <option key={`${role}-provider-${option.value}`} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <select
                  aria-label={`${role} model`}
                  onChange={event => routeControls.onRoleFieldChange?.(role, "model", event.target.value)}
                  value={route.model || ""}
                >
                  <option value="">Provider default</option>
                  {asList(routeOptions.models).map(option => (
                    <option key={`${role}-model-${option}`} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
                <select
                  aria-label={`${role} effort`}
                  onChange={event => routeControls.onRoleFieldChange?.(role, "effort", event.target.value)}
                  value={route.effort || "default"}
                >
                  {asList(routeOptions.efforts).map(option => (
                    <option key={`${role}-effort-${option.value}`} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </article>
            ))}
          </div>
        </ConfigCard>

        {actionModes.length > 0 ? (
          <ConfigCard
            accent="neutral"
            copy="The arrow follows this mode. Auto keeps short greetings/questions as chat and opens a mission for larger work."
            title="Run Mode"
            titleIcon={Sparkles}
          >
            <div className="reference-card-control-stack">
              <div className="reference-mode-strip vertical" aria-label="Run mode">
                {actionModes.map(option => (
                  <button
                    className={routeControls.actionMode === option.value ? "active" : ""}
                    key={`card-mode-${option.value}`}
                    onClick={() => routeControls.onActionModeChange?.(option.value)}
                    type="button"
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <button className="reference-link-button strong" onClick={() => routeControls.onSave?.()} type="button">
                Save routes
              </button>
            </div>
          </ConfigCard>
        ) : null}

        <ConfigCard
          accent="neutral"
          copy={`${selectedEffortLabel} · ${selectedModelLabel}`}
          title="Rules"
          titleIcon={BookOpen}
          footer={(
            <button
              className="reference-link-button"
              onClick={() => onRequestAction?.("idle:advanced-settings")}
              type="button"
            >
              Advanced settings
            </button>
          )}
        >
          <div className="reference-card-control-stack">
            <div className="reference-pill-select">Project Rules</div>
            <button className="reference-link-button" onClick={() => routeControls.onToggleCodeExecution?.()} type="button">
              Code execution {routeControls.codeExecutionEnabled ? `on (${routeControls.codeExecutionMemory})` : "off"}
            </button>
          </div>
        </ConfigCard>
      </div>

      <div className="reference-agent-support-grid single">
        <article className="reference-support-panel">
          <div className="reference-builder-section-head">
            <div>
              <strong>{runtimeStatus?.label || "Selected work engine"}</strong>
              <span>
                {runtimeStatus?.doctor_summary ||
                  runtimeStatus?.doctorSummary ||
                  "Readiness appears here after Syntelos checks setup."}
              </span>
            </div>
            <StatusBadge
              label={runtimeStatus?.detected ? "Ready" : "Not detected"}
              tone={runtimeStatus?.detected ? "completed" : "paused"}
            />
          </div>
          <RuntimeCapabilityPills capabilities={asList(runtimeStatus?.capabilities)} />
        </article>
      </div>

      <div className="reference-idle-footer">
        <button
          className="reference-reset-button"
          onClick={() => onRequestAction?.("idle:reset-defaults")}
          type="button"
        >
          <RefreshCw size={16} strokeWidth={1.9} />
          <span>Reset to defaults</span>
        </button>
        <p>Syntelos can make mistakes. Please verify important information.</p>
      </div>
    </section>
  );
}

function StepState({ label, done = false, pending = false }) {
  return (
    <div className="reference-step-state">
      {done ? (
        <CircleCheckBig className="done" size={16} strokeWidth={2.2} />
      ) : (
        <CircleDashed className={pending ? "pending" : ""} size={16} strokeWidth={2.2} />
      )}
      <span>{label}</span>
    </div>
  );
}

function AgentRunningSurface(props) {
  const {
    activeCommentTarget = null,
    conversationMode = "chat",
    draft,
    feedbackItems = [],
    generatedImageArtifacts = [],
    hermesEvidenceItems = [],
    missionLoop,
    messages = [],
    nasDeployChecks = [],
    onUseSlashCommand,
    runtimeCompartment = null,
    selectedRuntime,
    selectedRuntimeLabel,
    selectedModelLabel,
    selectedEffortLabel,
    slashCommands = [],
    timelineMoments = [],
    onAttach,
    onChangeDraft,
    onDictation,
    onPaste,
    onRequestAction,
    onRuntimeChange,
    runtimeOptions = [],
    routeControls = {},
    onSend,
  } = props;
  const [detailTab, setDetailTab] = useState("feedback");
  const [showTraceDetail, setShowTraceDetail] = useState(false);
  const processMoments = timelineMoments.slice(-4);
  const renderedMessages = messages.length > 0 ? messages : [];
  const showMissionPanels = conversationMode === "mission" || Boolean(missionLoop);
  const showSlashCommands = String(draft || "").trim().startsWith("/");
  const selectedRoute = routeControls.selectedRoute || {};
  const routeOptions = routeControls.routeOptions || {};
  const actionModes = routeControls.actionModes || [];
  const runtimeSelectOptions = runtimeOptions.length > 0
    ? runtimeOptions
    : [{ value: selectedRuntime, label: selectedRuntimeLabel }];
  const delegatedLanes = asList(
    missionLoop?.delegatedRuntimeSessions || missionLoop?.delegated_runtime_sessions || missionLoop?.lanes,
  );
  const runtimeModeLabel =
    missionLoop?.approvalMode === "hands_free" || routeControls.actionMode === "mission"
      ? "Hands-free"
      : "Supervised";
  const checkpointSummary =
    missionLoop?.checkpointSummary || missionLoop?.continuityDetail || missionLoop?.continuityState || "No checkpoint yet";
  const artifactItems = asList(missionLoop?.artifacts || missionLoop?.proofArtifacts || missionLoop?.proof_artifacts).slice(0, 3);
  const diffSummary = missionLoop?.diffSummary || missionLoop?.gitDiffSummary || missionLoop?.workspaceDiffSummary || "Diff pending";
  const compartmentEvents = asList(runtimeCompartment?.toolTimeline).slice(-5);
  const compartmentFiles = asList(runtimeCompartment?.filesChanged).slice(0, 5);
  const compartmentApprovals = asList(runtimeCompartment?.approvals).slice(0, 3);
  const visibleGeneratedArtifacts = asList(generatedImageArtifacts).slice(0, 4);
  const visibleHermesEvidence = asList(hermesEvidenceItems).slice(0, 5);
  const visibleNasChecks = asList(nasDeployChecks).slice(0, 6);
  const [workbenchTab, setWorkbenchTab] = useState("browser");
  const workbenchTabs = [
    { id: "browser", label: "Browser" },
    { id: "snapshot", label: "UI Snapshot" },
    { id: "terminal", label: "Terminal" },
    { id: "diff", label: "Diff" },
    { id: "files", label: `Files (${compartmentFiles.length})` },
    { id: "control", label: "Computer Control" },
  ];
  const [diagnosticNowMs, setDiagnosticNowMs] = useState(() => Date.now());
  const messageDiagnostics = useMemo(() => {
    return renderedMessages.map((item, index) => {
      const createdAtMs = parseTimeMs(item.createdAt);
      const pendingMs = item.pending && createdAtMs > 0 ? Math.max(0, diagnosticNowMs - createdAtMs) : 0;
      const latencyMs = !item.pending ? extractLatencyMsFromMessage(item) : 0;
      return {
        id: item.id,
        pendingMs,
        latencyMs,
        contradiction: detectPotentialContradiction(renderedMessages, index),
      };
    });
  }, [diagnosticNowMs, renderedMessages]);
  const messageDiagnosticsById = useMemo(
    () => new Map(messageDiagnostics.map(entry => [entry.id, entry])),
    [messageDiagnostics],
  );
  const pendingMessageCount = useMemo(
    () => messageDiagnostics.filter(entry => entry.pendingMs > 0).length,
    [messageDiagnostics],
  );
  const contradictionCount = useMemo(
    () => messageDiagnostics.filter(entry => Boolean(entry.contradiction)).length,
    [messageDiagnostics],
  );
  const latestLatencyMs = useMemo(() => {
    for (let index = messageDiagnostics.length - 1; index >= 0; index -= 1) {
      if (messageDiagnostics[index].latencyMs > 0) {
        return messageDiagnostics[index].latencyMs;
      }
    }
    return 0;
  }, [messageDiagnostics]);
  useEffect(() => {
    if (pendingMessageCount <= 0) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      setDiagnosticNowMs(Date.now());
    }, 1000);
    return () => window.clearInterval(timer);
  }, [pendingMessageCount]);

  if (!showMissionPanels) {
    return (
      <section className={cx("reference-agent-run", "mode-chat", "reference-agent-pro-chat")}>
        <div className="reference-chat-workbench">
          <section className="reference-chat-panel">
            <header className="reference-chat-session-head">
              <div>
                <strong>{selectedRoute.model || selectedModelLabel || "Conversation"}</strong>
                <p>
                  Provider: {selectedRoute.provider || runtimeCompartment?.route?.provider || "openai-codex"}
                  {"  "} Model: {selectedRoute.model || runtimeCompartment?.route?.model || selectedModelLabel}
                  {"  "} Route: {selectedRoute.role || "primary"}
                </p>
                <div className="reference-chat-health-strip" aria-label="Conversation diagnostics">
                  <span className={cx("reference-health-pill", pendingMessageCount > 0 && "is-live")}>
                    {pendingMessageCount > 0
                      ? `Thinking: ${pendingMessageCount}`
                      : "Thinking: idle"}
                  </span>
                  <span className="reference-health-pill">
                    {latestLatencyMs > 0
                      ? `Last response: ${formatElapsedDuration(latestLatencyMs)}`
                      : "Last response: n/a"}
                  </span>
                  <span className={cx("reference-health-pill", contradictionCount > 0 ? "is-warn" : "is-good")}>
                    {contradictionCount > 0
                      ? `Consistency watch: ${contradictionCount} flagged`
                      : "Consistency watch: clear"}
                  </span>
                </div>
              </div>
              <span className={cx("reference-session-state", runtimeCompartment?.streaming === "live" && "live")}>
                {runtimeCompartment?.streaming === "live" ? "Live" : "Recorded"}
              </span>
            </header>

            <div className="reference-chat-thread-canvas">
              {renderedMessages.length === 0 ? (
                <article className="reference-conversation-blank">
                  <strong>New conversation</strong>
                  <p>Send a message to begin a direct chat with Hermes.</p>
                  <button
                    className="reference-black-button"
                    onClick={() => onRequestAction?.("flow:new-conversation")}
                    type="button"
                  >
                    Start new conversation
                  </button>
                </article>
              ) : null}

              {renderedMessages.map(item => {
                const diagnostics = messageDiagnosticsById.get(item.id) || {};
                const contradictionSignal = diagnostics.contradiction || null;
                if (item.role === "user") {
                  return (
                    <div className="reference-user-bubble" key={item.id}>
                      <p>{item.title}</p>
                      <span>{item.meta || "Now"}</span>
                    </div>
                  );
                }
                return (
                  <div className={cx("reference-agent-thread", item.pending ? "is-pending" : "")} key={item.id}>
                    <div className="reference-agent-avatar">
                      <div className="reference-brand-mark tiny">
                        <span />
                        <span />
                        <span />
                      </div>
                    </div>
                    <div className="reference-agent-thread-body">
                      <p className="reference-thread-lead">
                        {item.pending ? <CircleDashed className="pending" size={16} strokeWidth={2.1} /> : null}
                        <span>{item.title}</span>
                        {item.pending && diagnostics.pendingMs > 0 ? (
                          <span className="reference-diagnostic-pill is-live">
                            Thinking {formatElapsedDuration(diagnostics.pendingMs)}
                          </span>
                        ) : null}
                        {!item.pending && diagnostics.latencyMs > 0 ? (
                          <span className="reference-diagnostic-pill">
                            Responded {formatElapsedDuration(diagnostics.latencyMs)}
                          </span>
                        ) : null}
                        {contradictionSignal ? (
                          <span className="reference-diagnostic-pill is-warn">Possible contradiction</span>
                        ) : null}
                      </p>
                      {contradictionSignal ? (
                        <div className="reference-contradiction-callout">
                          <strong>Consistency signal</strong>
                          <p>
                            Potential contradiction with an earlier assistant message on:{" "}
                            {contradictionSignal.subject || "shared context"}.
                          </p>
                        </div>
                      ) : null}
                      {item.detail || item.technicalDetail || item.chips?.length ? (
                        <article className={cx("reference-report-panel compact", item.technicalDetail && !item.detail ? "trace-only" : "")}>
                          {item.detail ? <p>{item.detail}</p> : null}
                          {item.technicalDetail ? (
                            <details className="reference-inline-trace">
                              <summary>Route detail</summary>
                              <p>{item.technicalDetail}</p>
                            </details>
                          ) : null}
                          {item.chips?.length ? (
                            <div className="reference-chip-row">
                              {item.chips.map(chip => (
                                <span className="reference-mini-pill" key={`${item.id}-${chip}`}>
                                  {chip}
                                </span>
                              ))}
                            </div>
                          ) : null}
                          <div className="reference-report-foot">
                            <div className="reference-report-actions">
                              <button onClick={() => onRequestAction?.("run:message-copy", { messageId: item.id })} type="button">Copy</button>
                              <button onClick={() => onRequestAction?.("run:message-comment", { messageId: item.id })} type="button">Comment</button>
                              <button onClick={() => onRequestAction?.("run:message-retry", { messageId: item.id })} type="button">Retry</button>
                            </div>
                            <span>{item.meta || "Now"}</span>
                          </div>
                        </article>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>

            <ComposerDock
              compact
              draft={draft}
              onAttach={onAttach}
              onChangeDraft={onChangeDraft}
              onDictation={onDictation}
              onPaste={onPaste}
              onSubmit={onSend}
              placeholder="Message Hermes..."
            >
              {showSlashCommands ? (
                <SlashCommandPanel
                  className="in-composer"
                  commands={slashCommands}
                  draft={draft}
                  onUseCommand={onUseSlashCommand}
                />
              ) : null}
            </ComposerDock>
          </section>

          <aside className="reference-workbench-side">
            <div className="reference-workbench-tabs">
              {workbenchTabs.map(tab => (
                <button
                  className={workbenchTab === tab.id ? "active" : ""}
                  key={tab.id}
                  onClick={() => setWorkbenchTab(tab.id)}
                  type="button"
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="reference-workbench-url">
              <span>{runtimeCompartment?.cwd || "workspace://current"}</span>
              <b>{runtimeCompartment?.streaming === "live" ? "Live" : "Idle"}</b>
            </div>
            <div className="reference-workbench-canvas">
              {workbenchTab === "browser" || workbenchTab === "snapshot" ? (
                <article className="reference-workbench-card">
                  <h4>Overview</h4>
                  <p>Session: {runtimeCompartment?.sessionId || "pending"}</p>
                  <p>Host: {runtimeCompartment?.host || "local"}</p>
                  <p>Runtime: {titleizeToken(runtimeCompartment?.runtime || selectedRuntime)}</p>
                  <p>Model: {runtimeCompartment?.route?.model || selectedRoute.model || selectedModelLabel}</p>
                </article>
              ) : null}
              {workbenchTab === "terminal" ? (
                <article className="reference-workbench-card">
                  <h4>Runtime terminal</h4>
                  <p>{compartmentEvents[compartmentEvents.length - 1]?.summary || "No terminal events yet."}</p>
                </article>
              ) : null}
              {workbenchTab === "diff" ? (
                <article className="reference-workbench-card">
                  <h4>Diff summary</h4>
                  <p>{processMoments[processMoments.length - 1]?.detail || "No diff summary reported yet."}</p>
                </article>
              ) : null}
              {workbenchTab === "files" ? (
                <article className="reference-workbench-card">
                  <h4>Files changed</h4>
                  {compartmentFiles.length ? (
                    <ul>
                      {compartmentFiles.map(file => <li key={`workbench-file-${file}`}>{file}</li>)}
                    </ul>
                  ) : (
                    <p>No file receipts yet (chat replies can be read-only).</p>
                  )}
                </article>
              ) : null}
              {workbenchTab === "control" ? (
                <article className="reference-workbench-card">
                  <h4>Computer control</h4>
                  <p>{runtimeCompartment?.restartControls?.canResume ? "Resume available" : "No resume control exposed yet."}</p>
                </article>
              ) : null}
            </div>
            <div className="reference-workbench-annotations">
              <div className="reference-workbench-annotations-head">
                <span>Annotations</span>
                <b>{feedbackItems.length}</b>
              </div>
              {feedbackItems.slice(0, 3).map(item => (
                <article className="reference-workbench-annotation" key={`annotation-${item.id}`}>
                  <strong>{item.author}</strong>
                  <p>{item.body}</p>
                </article>
              ))}
            </div>
          </aside>
        </div>

        <section className="reference-runtime-dock">
          <article className="reference-runtime-card">
            <h4>Tool calls</h4>
            <ul>
              {compartmentEvents.length ? compartmentEvents.map((event, index) => (
                <li key={`tool-call-${event.kind || index}`}>{event.kind || "event"} - {event.summary || "recorded"}</li>
              )) : <li>No tool calls yet.</li>}
            </ul>
          </article>
          <article className="reference-runtime-card">
            <h4>Files changed</h4>
            <ul>
              {compartmentFiles.length ? compartmentFiles.map(file => <li key={`file-change-${file}`}>{file}</li>) : <li>No file changes yet.</li>}
            </ul>
          </article>
          <article className="reference-runtime-card">
            <h4>Approvals</h4>
            <ul>
              {compartmentApprovals.length ? compartmentApprovals.map((approval, index) => (
                <li key={`approval-${approval?.id || index}`}>{approval?.status || approval?.decision || "approved"}</li>
              )) : <li>No approvals yet.</li>}
            </ul>
          </article>
          <article className="reference-runtime-card">
            <h4>Runtime status</h4>
            <p>Current branch: {runtimeCompartment?.cwd || "workspace not attached"}</p>
            <p>Session ID: {runtimeCompartment?.sessionId || "pending"}</p>
            <p>Tokens: recorded in runtime events</p>
          </article>
          <article className="reference-runtime-card">
            <h4>Event stream</h4>
            <ul>
              {processMoments.length ? processMoments.map(item => <li key={`stream-${item.id}`}>{item.title}</li>) : <li>No event stream yet.</li>}
            </ul>
          </article>
        </section>
      </section>
    );
  }

  return (
    <section className={cx("reference-agent-run", `mode-${conversationMode}`)}>
      {showMissionPanels && missionLoop ? (
        <article className="reference-run-summary">
          <div>
            <span>Cycle phase</span>
            <strong>{missionLoop.currentCyclePhase || "Plan"}</strong>
          </div>
          <div>
            <span>Cycles</span>
            <strong>{missionLoop.cycleCount || 0}</strong>
          </div>
          <div>
            <span>Continuity</span>
            <strong>{missionLoop.continuityDetail || missionLoop.continuityState || "Steady"}</strong>
          </div>
          <div>
            <span>Work engine</span>
            <strong>{missionLoop.currentRuntimeLane || "Primary thread"}</strong>
          </div>
        </article>
      ) : null}

      {showMissionPanels && missionLoop ? (
        <article className="reference-run-summary t3-lane-surface">
          <div>
            <span>Runtime mode</span>
            <strong>{runtimeModeLabel}</strong>
          </div>
          <div>
            <span>Provider/runtime</span>
            <strong>{selectedRoute.provider || "auto"} · {selectedRoute.model || selectedModelLabel}</strong>
          </div>
          <div>
            <span>Checkpoint</span>
            <strong>{checkpointSummary}</strong>
          </div>
          <div>
            <span>Diff</span>
            <strong>{diffSummary}</strong>
          </div>
          <div>
            <span>Lanes</span>
            <strong>{Math.max(1, delegatedLanes.length + 1)}</strong>
          </div>
          <div>
            <span>Artifacts</span>
            <strong>{artifactItems.length || 0}</strong>
          </div>
        </article>
      ) : null}

      {runtimeCompartment ? (
        <article className="agent-compartment-box" aria-label="Active agent runtime compartment">
          <div className="agent-compartment-box-head">
            <div>
              <p className="eyebrow">Live runtime compartments · Runtime compartment</p>
              <h2>{runtimeCompartment.sessionId || "pending session"}</h2>
            </div>
            <div className="agent-compartment-status">
              <span className={cx("agent-live-dot", runtimeCompartment.streaming === "live" && "live")} />
              <strong>{titleizeToken(runtimeCompartment.state || "recorded")}</strong>
              <span>{runtimeCompartment.streaming === "live" ? "streaming" : "recorded"}</span>
            </div>
          </div>
          <div className="agent-compartment-matrix">
            <div>
              <span>Runtime</span>
              <strong>{titleizeToken(runtimeCompartment.runtime || selectedRuntime)}</strong>
            </div>
            <div>
              <span>Route</span>
              <strong>
                {runtimeCompartment.route?.provider
                  ? `${titleizeToken(runtimeCompartment.route.provider)} / ${runtimeCompartment.route?.model || runtimeCompartment.route?.model_id || selectedModelLabel}`
                  : selectedModelLabel}
              </strong>
            </div>
            <div>
              <span>Host</span>
              <strong>{titleizeToken(runtimeCompartment.host || "local")}</strong>
            </div>
            <div>
              <span>Execution root</span>
              <strong>{runtimeCompartment.cwd || "Not selected"}</strong>
            </div>
          </div>
          <div className="agent-compartment-body agent-live-workbench-grid">
            <div className="agent-compartment-lane">
              <div className="agent-compartment-subhead">
                <span>Hermes mission evidence · Tool/action timeline</span>
                <b>{compartmentEvents.length}</b>
              </div>
              <div className="agent-compartment-event-list">
                {compartmentEvents.length ? compartmentEvents.map((event, index) => (
                  <div className="agent-compartment-event" key={`${event.kind || "event"}-${event.at || index}`}>
                    <span>{titleizeToken(event.kind || event.status || "event")}</span>
                    <strong>{event.summary || "Runtime event recorded"}</strong>
                    <small>{event.at || event.status || "recorded"}</small>
                  </div>
                )) : <p className="agent-compartment-empty">No live tool events have reached the compartment yet.</p>}
              </div>
            </div>
            <div className="agent-compartment-lane">
              <div className="agent-compartment-subhead">
                <span>NAS deploy readiness · Files and approvals</span>
                <b>{compartmentFiles.length + compartmentApprovals.length}</b>
              </div>
              <div className="agent-compartment-chip-list">
                {compartmentFiles.map(file => <code key={`file-${file}`}>{file}</code>)}
                {compartmentApprovals.map((approval, index) => (
                  <span key={`approval-${approval?.id || index}`}>{approval?.status || approval?.decision || "approval recorded"}</span>
                ))}
                {compartmentFiles.length + compartmentApprovals.length === 0 ? (
                  <p className="agent-compartment-empty">No changed-file or approval receipts attached yet.</p>
                ) : null}
              </div>
            </div>
          </div>
          <div className="agent-compartment-body agent-live-workbench-grid">
            <div className="agent-compartment-lane">
              <div className="agent-compartment-subhead">
                <span>Generated image artifacts</span>
                <b>{visibleGeneratedArtifacts.length}</b>
              </div>
              <div className="agent-artifact-grid">
                {visibleGeneratedArtifacts.length ? visibleGeneratedArtifacts.map((artifact, index) => {
                  const imageUrl = artifactUrlForRecord(artifact);
                  const manifestUrl = resolveReferenceArtifactUrl(artifact?.manifestUrl || artifact?.manifestPath || "");
                  const label = artifactLabelForRecord(artifact, `artifact-${index + 1}`);
                  return (
                    <figure className="agent-artifact-card" key={`${artifact?.artifactId || label}-${index}`}>
                      {imageUrl ? <img alt={label} src={imageUrl} /> : <div className="builder-live-review-image-missing">Preview not served</div>}
                      <figcaption>
                        <strong>{label}</strong>
                        <span>{artifact?.servedArtifactId ? `served ${String(artifact.servedArtifactId).slice(0, 10)}` : artifact?.provider || "served artifact"}</span>
                        {manifestUrl ? <a href={manifestUrl} rel="noreferrer" target="_blank">Manifest</a> : null}
                      </figcaption>
                    </figure>
                  );
                }) : <p className="agent-compartment-empty">No served image artifacts are available yet.</p>}
              </div>
            </div>
            <div className="agent-compartment-lane">
              <div className="agent-compartment-subhead">
                <span>Hermes mission evidence</span>
                <b>{visibleHermesEvidence.length}</b>
              </div>
              <div className="agent-compartment-event-list">
                {visibleHermesEvidence.length ? visibleHermesEvidence.map((item, index) => (
                  <div className="agent-compartment-event" key={`${item.missionId || "hermes"}-${item.timestamp || index}`}>
                    <span>{titleizeToken(item.source || item.status || "evidence")}</span>
                    <strong>{item.message || item.objective || "Hermes evidence recorded"}</strong>
                    <small>{item.timestamp || item.status || "recorded"}</small>
                    {asList(item.artifacts).length ? (
                      <div className="agent-evidence-artifact-strip">
                        {asList(item.artifacts).slice(0, 3).map((artifact, artifactIndex) => {
                          const artifactUrl = artifactUrlForRecord(artifact);
                          const artifactLabel = artifactLabelForRecord(artifact, `evidence-${artifactIndex + 1}`);
                          const artifactPath = artifact?.path || artifact?.artifactPath || artifact?.servedUrl || artifactUrl;
                          return (
                            <a href={artifactUrl || "#"} key={`${item.missionId || "evidence"}-${artifactLabel}-${artifactIndex}`} rel="noreferrer" target="_blank">
                              {isImageArtifactPath(artifactPath) && artifactUrl ? <img alt="" src={artifactUrl} /> : null}
                              <span>{artifactLabel}</span>
                            </a>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                )) : <p className="agent-compartment-empty">No Hermes evidence has been captured yet.</p>}
              </div>
            </div>
          </div>
          <div className="agent-compartment-lane agent-nas-readiness-panel">
            <div className="agent-compartment-subhead">
              <span>NAS deploy readiness</span>
              <b>{visibleNasChecks.filter(check => check?.passed).length}/{visibleNasChecks.length}</b>
            </div>
            <div className="agent-nas-check-grid">
              {visibleNasChecks.length ? visibleNasChecks.map(check => (
                <article className={cx("agent-nas-check", check.passed ? "passed" : check.required ? "blocked" : "warn")} key={check.checkId || check.label}>
                  <span>{check.required ? "Required" : "Offline check"}</span>
                  <strong>{check.label}</strong>
                  <p>{check.details}</p>
                </article>
              )) : <p className="agent-compartment-empty">NAS deploy readiness has not been reported by the backend yet.</p>}
            </div>
          </div>
          <div className="agent-compartment-actions">
            <button onClick={() => onRequestAction?.("run:resume")} type="button">Resume</button>
            <button onClick={() => onRequestAction?.("run:proof")} type="button">Proof</button>
            <button onClick={() => onRequestAction?.("run:queue")} type="button">Queue</button>
          </div>
        </article>
      ) : null}

      {showMissionPanels && delegatedLanes.length > 0 ? (
        <article className="reference-status-panel">
          <div className="reference-status-panel-head">
            <h3>Concurrent runtime lanes</h3>
          </div>
          <div className="reference-status-list">
            {delegatedLanes.slice(0, 6).map((lane, index) => (
              <div className="reference-status-row" key={lane.id || lane.session_id || `lane-${index}`}>
                <StepState
                  done={String(lane.status || "").toLowerCase() === "completed"}
                  pending={String(lane.status || "").toLowerCase() === "running"}
                  label={`${lane.role || `Lane ${index + 1}`} · ${lane.provider || lane.runtime_id || "runtime"}`}
                />
                <p>{lane.detail || lane.last_event || lane.status || "Active"}</p>
              </div>
            ))}
          </div>
        </article>
      ) : null}

      <div className="reference-chat-column">
        {renderedMessages.length === 0 ? (
          <article className="reference-conversation-blank">
            <strong>{showMissionPanels ? "Mission conversation is ready" : "New conversation"}</strong>
            <p>
              {showMissionPanels
                ? "Send a message or wait for the runtime to publish its next readable update."
                : "Ask a question or switch the mode to Mission when you want file changes and a tracked work loop."}
            </p>
            {!showMissionPanels ? (
              <button className="reference-black-button" onClick={() => onRequestAction?.("flow:new-conversation")} type="button">
                Start new conversation
              </button>
            ) : null}
          </article>
        ) : null}

        {renderedMessages.map(item =>
          item.role === "user" ? (
            <div className="reference-user-bubble" key={item.id}>
              <p>{item.title}</p>
              <span>{item.meta || "Now"}</span>
            </div>
          ) : (
            <div className={cx("reference-agent-thread", item.pending ? "is-pending" : "")} key={item.id}>
              <div className="reference-agent-avatar">
                <div className="reference-brand-mark tiny">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
              <div className="reference-agent-thread-body">
                <p className="reference-thread-lead">
                  {item.pending ? <CircleDashed className="pending" size={16} strokeWidth={2.1} /> : null}
                  <span>{item.title}</span>
                </p>
                {item.detail || item.technicalDetail || item.chips?.length ? (
                  <article className={cx("reference-report-panel compact", item.technicalDetail && !item.detail ? "trace-only" : "")}>
                    {item.detail ? <p>{item.detail}</p> : null}
                    {item.technicalDetail ? (
                      <details className="reference-inline-trace">
                        <summary>Route detail</summary>
                        <p>{item.technicalDetail}</p>
                      </details>
                    ) : null}
                    {item.chips?.length ? (
                      <div className="reference-chip-row">
                        {item.chips.map(chip => (
                          <span className="reference-mini-pill" key={`${item.id}-${chip}`}>
                            {chip}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    <div className="reference-report-foot">
                      <div className="reference-report-actions">
                        <button onClick={() => onRequestAction?.("run:message-copy", { messageId: item.id })} type="button">Copy</button>
                        <button onClick={() => onRequestAction?.("run:message-comment", { messageId: item.id })} type="button">Comment</button>
                        <button onClick={() => onRequestAction?.("run:message-retry", { messageId: item.id })} type="button">Retry</button>
                      </div>
                      <span>{item.meta || "Now"}</span>
                    </div>
                  </article>
                ) : null}
              </div>
            </div>
          ),
        )}

        {showMissionPanels && processMoments.length > 0 ? (
          <article className="reference-status-panel">
            <div className="reference-status-panel-head">
              <h3>Live mission activity</h3>
              <button onClick={() => setShowTraceDetail(current => !current)} type="button">
                {showTraceDetail ? "Hide trace" : "Show trace"}
              </button>
            </div>
            <div className="reference-status-list">
              {processMoments.map((moment, index) => (
                <div className="reference-status-row" key={moment.id}>
                  <StepState
                    done={index < processMoments.length - 1}
                    label={moment.title}
                    pending={index === processMoments.length - 1}
                  />
                  {showTraceDetail && (moment.detail || moment.preview) ? (
                    <p>{moment.preview || moment.detail}</p>
                  ) : null}
                  <button
                    className="reference-row-comment"
                    onClick={() => onRequestAction?.("run:moment-comment", { momentId: moment.id })}
                    type="button"
                  >
                    Comment
                  </button>
                </div>
              ))}
            </div>
          </article>
        ) : null}

        {showMissionPanels && feedbackItems.length > 0 ? (
        <article className="reference-feedback-panel">
          <div className="reference-feedback-tabs">
            <button
              className={detailTab === "feedback" ? "active" : ""}
              onClick={() => setDetailTab("feedback")}
              type="button"
            >
              Feedback
            </button>
            <button
              className={detailTab === "notes" ? "active" : ""}
              onClick={() => setDetailTab("notes")}
              type="button"
            >
              Notes
            </button>
          </div>
          <div className="reference-feedback-list">
            {feedbackItems
              .filter(item => (detailTab === "feedback" ? item.role !== "note" : true))
              .slice(0, 3)
              .map(item => (
                <article className="reference-feedback-item" key={item.id}>
                  <div className="reference-feedback-meta">
                    <strong>{item.author}</strong>
                    <span>{item.meta}</span>
                  </div>
                  <p>{item.body}</p>
                  {item.role === "assistant" ? (
                    <div className="reference-feedback-actions">
                      <button onClick={() => onRequestAction?.("run:feedback-apply", { feedbackId: item.id })} type="button">Change applied</button>
                      <button onClick={() => onRequestAction?.("run:feedback-view", { feedbackId: item.id })} type="button">View change</button>
                    </div>
                  ) : null}
                </article>
              ))}
          </div>
        </article>
        ) : null}
      </div>

      <ComposerDock
        compact
        draft={draft}
        onAttach={onAttach}
        onChangeDraft={onChangeDraft}
        onDictation={onDictation}
        onPaste={onPaste}
        onSubmit={onSend}
        placeholder={
          activeCommentTarget
            ? "Add a live comment..."
            : showMissionPanels
              ? "Comment live or steer the mission..."
              : "Reply in this conversation..."
        }
      >
        {activeCommentTarget ? (
          <div className="reference-comment-target">
            <span>Commenting on {activeCommentTarget.kind || "item"}</span>
            <strong>{activeCommentTarget.title}</strong>
            <button onClick={() => onRequestAction?.("run:clear-comment-target")} type="button">Clear</button>
          </div>
        ) : null}
        {showMissionPanels ? (
          <>
            {actionModes.length > 0 ? (
              <div className="reference-mode-strip compact" aria-label="Run mode">
                {actionModes.map(option => (
                  <button
                    className={routeControls.actionMode === option.value ? "active" : ""}
                    key={`run-mode-${option.value}`}
                    onClick={() => routeControls.onActionModeChange?.(option.value)}
                    type="button"
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            ) : null}
            <div className="reference-docked-controls">
              <label className="reference-inline-select">
                <span>Work engine</span>
                <select onChange={event => onRuntimeChange(event.target.value)} value={selectedRuntime}>
                  {runtimeSelectOptions.map(option => (
                    <option key={`run-runtime-${option.value}`} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="reference-inline-select">
                <span>Route role</span>
                <input readOnly value={`${titleizeToken(routeControls.role || "executor")} (auto)`} />
              </label>
              <label className="reference-inline-select">
                <span>Model</span>
                <select onChange={event => routeControls.onFieldChange?.("model", event.target.value)} value={selectedRoute.model || ""}>
                  <option value="">{selectedModelLabel}</option>
                  {asList(routeOptions.models).map(option => (
                    <option key={`run-route-model-${option}`} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="reference-inline-select">
                <span>Effort</span>
                <select onChange={event => routeControls.onFieldChange?.("effort", event.target.value)} value={selectedRoute.effort || "default"}>
                  {asList(routeOptions.efforts).map(option => (
                    <option key={`run-route-effort-${option.value}`} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <button className="reference-tool-button" onClick={() => routeControls.onSave?.()} type="button">
                Save route
              </button>
            </div>
          </>
        ) : null}

        {showSlashCommands ? (
          <SlashCommandPanel
            className="in-composer"
            commands={slashCommands}
            draft={draft}
            onUseCommand={onUseSlashCommand}
          />
        ) : null}
      </ComposerDock>
    </section>
  );
}

function LivePreviewSurface(props) {
  const {
    changedItems = [],
    draft,
    feedbackItems = [],
    generatedImageArtifacts = [],
    hermesEvidenceItems = [],
    messages = [],
    nasDeployChecks = [],
    onAttach,
    onChangeDraft,
    onDictation,
    onPaste,
    onRequestAction,
    onSend,
    onUseSlashCommand,
    projectLabel,
    runtimeCompartment,
    slashCommands = [],
    timelineMoments = [],
  } = props;
  const [previewTab, setPreviewTab] = useState("preview");
  const [previewDevice, setPreviewDevice] = useState("desktop");
  const assistantMoments = timelineMoments.slice(-3);
  const latestUserMessage = [...messages].reverse().find(item => item.role === "user");
  const latestAssistantMessage = [...messages].reverse().find(item => item.role === "assistant");
  const showSlashCommands = String(draft || "").trim().startsWith("/");
  const hasRuntimeCompartment = Boolean(runtimeCompartment);
  const agentActivityLabel = hasRuntimeCompartment
    ? runtimeCompartment?.streaming === "live"
      ? "Working"
      : "Recorded"
    : "Waiting for runtime";
  const agentActivityDetail = hasRuntimeCompartment
    ? latestAssistantMessage?.title || "Runtime evidence is attached to this live preview."
    : "The preview is open, but no live runtime session has attached yet.";
  const evidenceRows = [
    {
      id: "runtime",
      action: "live:evidence:runtime",
      label: "Runtime compartment",
      value: runtimeCompartment?.sessionId || "No live session",
      detail: runtimeCompartment?.state || runtimeCompartment?.runtime || "Waiting for runtime lane",
      tone: runtimeCompartment ? "good" : "warn",
    },
    {
      id: "images",
      action: "live:evidence:images",
      label: "Generated image artifacts",
      value: String(asList(generatedImageArtifacts).length),
      detail: asList(generatedImageArtifacts)[0]?.provider || "No served image artifacts",
      tone: asList(generatedImageArtifacts).length ? "good" : "neutral",
    },
    {
      id: "hermes",
      action: "live:evidence:hermes",
      label: "Hermes mission evidence",
      value: String(asList(hermesEvidenceItems).length),
      detail: asList(hermesEvidenceItems)[0]?.status || "No Hermes evidence captured",
      tone: asList(hermesEvidenceItems).length ? "good" : "warn",
    },
    {
      id: "nas",
      action: "live:evidence:nas",
      label: "NAS deploy readiness",
      value: `${asList(nasDeployChecks).filter(check => check?.passed).length}/${asList(nasDeployChecks).length}`,
      detail: asList(nasDeployChecks).length ? "Readiness checks attached" : "No readiness report",
      tone: asList(nasDeployChecks).some(check => check?.required && !check?.passed) ? "warn" : "good",
    },
  ];

  return (
    <section className="reference-live-surface">
      <div className="reference-live-sidebar-column">
        <article className="reference-live-card">
          <div className="reference-live-card-head">
            <div className="reference-live-agent">
              <div className="reference-brand-mark tiny">
                <span />
                <span />
                <span />
              </div>
              <div>
                <strong>Syntelos Agent</strong>
                <span>{agentActivityLabel}</span>
              </div>
            </div>
          </div>
          <p>{agentActivityDetail}</p>
          <div className="reference-live-editing">
            <span>
              Editing: {changedItems[0] || "Current project surface"}
            </span>
            <CircleDashed size={18} strokeWidth={2.1} />
          </div>
        </article>

        {latestUserMessage ? (
          <article className="reference-live-card">
            <div className="reference-live-agent user">
              <div className="reference-user-mini">O</div>
              <div>
                <strong>You</strong>
              </div>
            </div>
            <p>{latestUserMessage.title}</p>
          </article>
        ) : null}

        {latestAssistantMessage?.detail ? (
          <article className="reference-live-card">
            <div className="reference-live-agent">
              <div className="reference-brand-mark tiny">
                <span />
                <span />
                <span />
              </div>
              <div>
                <strong>Syntelos Agent</strong>
                <span>Thinking</span>
              </div>
            </div>
            <p>{latestAssistantMessage.detail}</p>
          </article>
        ) : null}

        <article className="reference-live-card reference-live-evidence-card">
          <div className="reference-live-agent">
            <div className="reference-brand-mark tiny">
              <span />
              <span />
              <span />
            </div>
            <div>
              <strong>Live evidence</strong>
              <span>Runtime, artifacts, Hermes, NAS</span>
            </div>
          </div>
          <div className="reference-live-evidence-grid">
            {evidenceRows.map(row => (
              <button
                className={cx("reference-live-evidence-row", row.tone)}
                key={row.id}
                onClick={() => onRequestAction?.(row.action)}
                type="button"
              >
                <span>{row.label}</span>
                <strong>{row.value}</strong>
                <small>{row.detail}</small>
              </button>
            ))}
          </div>
        </article>

        <article className="reference-live-card">
          <div className="reference-live-agent">
            <div className="reference-brand-mark tiny">
              <span />
              <span />
              <span />
            </div>
            <div>
              <strong>Syntelos Agent</strong>
              <span>Applying changes</span>
            </div>
          </div>
          <div className="reference-checklist">
            {assistantMoments.map((moment, index) => (
              <StepState
                done={index < assistantMoments.length - 1}
                key={moment.id}
                label={moment.title}
                pending={index === assistantMoments.length - 1}
              />
            ))}
          </div>
        </article>

        <ComposerDock
          compact
          draft={draft}
          onAttach={onAttach}
          onChangeDraft={onChangeDraft}
          onDictation={onDictation}
          onPaste={onPaste}
          onSubmit={onSend}
          placeholder="Ask your agent anything..."
        >
          {showSlashCommands ? (
            <SlashCommandPanel
              className="in-composer"
              commands={slashCommands}
              draft={draft}
              onUseCommand={onUseSlashCommand}
            />
          ) : null}
        </ComposerDock>
      </div>

      <div className="reference-preview-stage">
        <div className="reference-preview-toolbar">
          <div className="reference-preview-tabs">
            <button
              className={previewTab === "preview" ? "active" : ""}
              onClick={() => setPreviewTab("preview")}
              type="button"
            >
              Preview
            </button>
            <button
              className={previewTab === "files" ? "active" : ""}
              onClick={() => setPreviewTab("files")}
              type="button"
            >
              Files
            </button>
            <button
              className={previewTab === "terminal" ? "active" : ""}
              onClick={() => setPreviewTab("terminal")}
              type="button"
            >
              Terminal
            </button>
          </div>
          <div className="reference-preview-actions">
            <div className="reference-device-toggle">
              <button
                className={previewDevice === "desktop" ? "active" : ""}
                onClick={() => setPreviewDevice("desktop")}
                type="button"
              >
                <Monitor size={16} strokeWidth={1.9} />
              </button>
              <button
                className={previewDevice === "laptop" ? "active" : ""}
                onClick={() => setPreviewDevice("laptop")}
                type="button"
              >
                <Laptop size={16} strokeWidth={1.9} />
              </button>
              <button
                className={previewDevice === "mobile" ? "active" : ""}
                onClick={() => setPreviewDevice("mobile")}
                type="button"
              >
                <Smartphone size={16} strokeWidth={1.9} />
              </button>
            </div>
            <IconButton icon={RefreshCw} label="Refresh preview" onClick={() => onRequestAction?.("live:refresh-preview")} />
            <IconButton icon={Expand} label="Expand preview" onClick={() => onRequestAction?.("live:expand-preview")} />
          </div>
        </div>

        <div className="reference-preview-canvas">
          <div className="reference-preview-browser">
            <div className="reference-browser-nav">
              <div className="reference-browser-brand">
                <div className="reference-brand-mark tiny">
                  <span />
                  <span />
                  <span />
                </div>
                <strong>{projectLabel}</strong>
              </div>
              <nav>
                <span>Product</span>
                <span>Features</span>
                <span>Pricing</span>
                <span>Resources</span>
              </nav>
              <button
                className="reference-browser-cta"
                onClick={() => onRequestAction?.("live:cta-start")}
                type="button"
              >
                Get Started
              </button>
            </div>

            <div className="reference-browser-hero">
              <div className="reference-browser-chip">
                <span>New</span>
                <strong>{changedItems[0] || `${projectLabel} is updating live`}</strong>
              </div>
              <h2>{latestAssistantMessage?.title || `Build better software with ${projectLabel}.`}</h2>
              <p>
                {latestAssistantMessage?.detail ||
                  "Live preview updates reflect the latest active mission decisions and UI edits."}
              </p>
              <div className="reference-browser-actions">
                <button className="primary" onClick={() => onRequestAction?.("live:start-building")} type="button">Start Building</button>
                <button className="secondary" onClick={() => onRequestAction?.("live:view-demo")} type="button">View Demo</button>
              </div>
              <div className="reference-browser-benefits">
                <span>No credit card required</span>
                <span>14-day free trial</span>
                <span>Cancel anytime</span>
              </div>
            </div>

            <div className="reference-preview-comment">
              <div className="reference-preview-comment-head">
                <span>{projectLabel}</span>
                <strong>You</strong>
                <em>Just now</em>
              </div>
              <p>{latestUserMessage?.title || "Add feedback or ask the agent..."}</p>
              <div className="reference-preview-comment-foot">
                <button onClick={() => onRequestAction?.("live:comment-react")} type="button">React</button>
                <button className="send" onClick={() => onRequestAction?.("live:comment-send")} type="button">Send</button>
              </div>
            </div>

            <div className="reference-preview-dashboard">
              <aside className="reference-preview-sidebar">
                <strong>{projectLabel}</strong>
                <span className="active">Overview</span>
                <span>Projects</span>
                <span>Deployments</span>
                <span>Analytics</span>
              </aside>
              <div className="reference-preview-dashboard-main">
                <div className="reference-preview-dashboard-head">
                  <strong>Overview</strong>
                </div>
                <div className="reference-preview-stats">
                  <article>
                    <span>Tracked changes</span>
                    <strong>{Math.max(changedItems.length, 1)}</strong>
                    <p>Visible in this mission</p>
                  </article>
                  <article>
                    <span>Feedback items</span>
                    <strong>{feedbackItems.length}</strong>
                    <p>Across notes and comments</p>
                  </article>
                  <article>
                    <span>Timeline moments</span>
                    <strong>{timelineMoments.length}</strong>
                    <p>Captured in the live trace</p>
                  </article>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function BuilderMetricCard({ item }) {
  const Icon = item.icon;
  return (
    <article className="reference-builder-metric">
      <div className="reference-builder-metric-icon">
        <Icon size={24} strokeWidth={1.9} />
      </div>
      <div className="reference-builder-metric-copy">
        <span>{item.label}</span>
        <strong>{item.value}</strong>
        <p className={cx("reference-metric-delta", item.tone)}>{item.delta}</p>
      </div>
      {item.id === "projects" ? <div aria-hidden="true" className="reference-mini-sparkline" /> : null}
    </article>
  );
}

function StatusBadge({ tone, label }) {
  return <span className={cx("reference-status-badge", tone)}>{label}</span>;
}

function parseDurationSeconds(value) {
  const text = String(value || "");
  let total = 0;
  const minutes = text.match(/(\d+)\s*m/);
  const seconds = text.match(/(\d+)\s*s/);
  if (minutes) {
    total += Number(minutes[1]) * 60;
  }
  if (seconds) {
    total += Number(seconds[1]);
  }
  return total || 0;
}

function formatMetricDuration(seconds) {
  if (!seconds) {
    return "—";
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return minutes > 0 ? `${minutes}m ${String(remainder).padStart(2, "0")}s` : `${remainder}s`;
}

function buildBuilderMetrics(rows) {
  const safeRows = asList(rows);
  const activeRuns = safeRows.filter(item => item.statusTone === "running").length;
  const blockedRuns = safeRows.filter(item => ["failed", "warn"].includes(item.statusTone)).length;
  const successRates = safeRows
    .map(item => item.successRate)
    .filter(value => typeof value === "number" && Number.isFinite(value));
  const averageSuccess = successRates.length
    ? Math.round(successRates.reduce((total, value) => total + value, 0) / successRates.length)
    : 0;
  const turningPoints = safeRows.map(item => parseDurationSeconds(item.turningPoint)).filter(Boolean);
  const averageTurningPoint = turningPoints.length
    ? Math.round(turningPoints.reduce((total, value) => total + value, 0) / turningPoints.length)
    : 0;
  return [
    {
      id: "projects",
      label: "Total Projects",
      value: String(safeRows.length),
      delta: safeRows.length ? "Tracked from live missions" : "No live missions yet",
      tone: safeRows.length ? "up" : "flat",
      icon: Code2,
    },
    {
      id: "runs",
      label: "Active Runs",
      value: String(activeRuns),
      delta: blockedRuns ? `${blockedRuns} need attention` : "No blockers recorded",
      tone: blockedRuns ? "down" : activeRuns ? "up" : "flat",
      icon: Play,
    },
    {
      id: "success",
      label: "Success Rate",
      value: averageSuccess ? `${averageSuccess}%` : "—",
      delta: successRates.length ? `${successRates.length} run signal${successRates.length === 1 ? "" : "s"}` : "Waiting for run data",
      tone: averageSuccess >= 90 ? "up" : averageSuccess ? "down" : "flat",
      icon: CircleCheckBig,
    },
    {
      id: "turning-point",
      label: "Avg. Turning Point",
      value: formatMetricDuration(averageTurningPoint),
      delta: turningPoints.length ? "Derived from mission state" : "Waiting for timing data",
      tone: averageTurningPoint ? "up" : "flat",
      icon: Clock3,
    },
  ];
}

function BuilderSurface(props) {
  const {
    builderDetailOpen = false,
    builderRows = [],
    changedItems = [],
    feedbackItems = [],
    flowProjects = [],
    onBackFromBuilder,
    onOpenBuilderDetail,
    onRequestAction,
    onSelectFlow,
    onSelectProject,
    projectLabel,
    ruleSets = [],
    activeRuleSetId = "",
    onOpenSkillStudio,
    selectedProjectId,
    timelineMoments = [],
  } = props;
  const [builderSearch, setBuilderSearch] = useState("");
  const [builderPage, setBuilderPage] = useState(1);
  const [detailFlowSearch, setDetailFlowSearch] = useState("");
  const [detailTab, setDetailTab] = useState("flows");
  const [detailPreviewTab, setDetailPreviewTab] = useState("preview");
  const [detailFeedbackTab, setDetailFeedbackTab] = useState("feedback");
  const pageSize = 8;
  const builderSearchQuery = String(builderSearch || "").trim().toLowerCase();
  const filteredBuilderRows =
    builderSearchQuery.length === 0
      ? builderRows
      : builderRows.filter(row =>
          [row.name, row.description, row.status, row.id]
            .map(value => String(value || "").toLowerCase())
            .some(value => value.includes(builderSearchQuery)),
        );
  const totalPages = Math.max(1, Math.ceil(filteredBuilderRows.length / pageSize));
  const effectiveBuilderPage = Math.min(builderPage, totalPages);
  const pageStart = (effectiveBuilderPage - 1) * pageSize;
  const pagedBuilderRows = filteredBuilderRows.slice(pageStart, pageStart + pageSize);
  const selectedRow = builderRows.find(item => item.selected) || builderRows[0] || null;
  const activeProject =
    flowProjects.find(item => item.id === selectedProjectId) || flowProjects[0] || null;
  const detailFlowQuery = String(detailFlowSearch || "").trim().toLowerCase();
  const detailFlowProjects =
    detailFlowQuery.length === 0
      ? flowProjects
      : flowProjects
          .map(project => {
            const filteredFlows = asList(project.flows).filter(flow =>
              [flow.title, flow.status, flow.updated]
                .map(value => String(value || "").toLowerCase())
                .some(value => value.includes(detailFlowQuery)),
            );
            const projectMatches = String(project.title || "").toLowerCase().includes(detailFlowQuery);
            return {
              ...project,
              flows: projectMatches ? asList(project.flows) : filteredFlows,
            };
          })
          .filter(project => asList(project.flows).length > 0);
  const builderHighlights = [
    ["Success rate", `${selectedRow?.successRate ?? 0}%`],
    ["Runs", `${selectedRow?.runs ?? 0}`],
    ["Turning point", selectedRow?.turningPoint || "—"],
    ["Last update", selectedRow?.updated || selectedRow?.lastRunMeta || "—"],
  ];
  const builderMetrics = buildBuilderMetrics(builderRows);
  const openBuilderDetailFromKey = (event, rowId) => {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }
    event.preventDefault();
    onOpenBuilderDetail(rowId);
  };

  if (builderDetailOpen && selectedRow) {
    return (
      <section className="reference-builder-detail">
        <div className="reference-builder-detail-column left">
          <button className="reference-back-link" onClick={onBackFromBuilder} type="button">
            <ArrowLeft size={15} strokeWidth={2} />
            <span>Back to Projects</span>
          </button>
          <div className="reference-builder-detail-head">
            <strong>{activeProject?.title || projectLabel}</strong>
            <StatusBadge label={selectedRow.status} tone={selectedRow.statusTone} />
          </div>
          <div className="reference-detail-tabs">
            <button className={detailTab === "overview" ? "active" : ""} onClick={() => setDetailTab("overview")} type="button">Overview</button>
            <button className={detailTab === "flows" ? "active" : ""} onClick={() => setDetailTab("flows")} type="button">Flows</button>
            <button className={detailTab === "files" ? "active" : ""} onClick={() => setDetailTab("files")} type="button">Files</button>
            <button className={detailTab === "settings" ? "active" : ""} onClick={() => setDetailTab("settings")} type="button">Settings</button>
          </div>
          <label className="reference-search-field">
            <Search size={18} strokeWidth={1.9} />
            <input
              onChange={event => setDetailFlowSearch(event.target.value)}
              placeholder="Search flows..."
              value={detailFlowSearch}
            />
          </label>
          <div className="reference-flow-detail-list">
            {detailFlowProjects.map(project => (
              <div className="reference-flow-detail-group" key={project.id}>
                <button className="reference-project-row" onClick={() => onSelectProject(project.id)} type="button">
                  <div className="reference-project-row-title">
                    <FolderOpen size={15} strokeWidth={1.9} />
                    <strong>{project.title}</strong>
                  </div>
                  <span>{project.count}</span>
                </button>
                {project.id === (activeProject?.id || selectedProjectId) ? (
                  <div className="reference-flow-detail-items">
                    {project.flows.map(flow => (
                      <button
                        className={cx("reference-flow-detail-item", flow.selected && "active")}
                        key={flow.id}
                        onClick={() => onSelectFlow(flow.id)}
                        type="button"
                      >
                        <div>
                          <strong>{flow.title}</strong>
                          <p>
                            <span className={cx("reference-flow-dot tiny", dotToneClass(flow.statusTone))} />
                            {flow.status}
                          </p>
                        </div>
                        <em>{flow.updated}</em>
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
          <article className="reference-builder-side-card">
            <div className="reference-builder-section-head">
              <div>
                <strong>Flow Snapshot</strong>
                <span>Current status for the selected workstream</span>
              </div>
            </div>
            <div className="reference-builder-stat-grid compact">
              {builderHighlights.map(([label, value]) => (
                <article key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </article>
              ))}
            </div>
          </article>
        </div>

        <div className="reference-builder-detail-column middle">
          <div className="reference-builder-detail-title">
            <div>
              <h1>{selectedRow.name}</h1>
              <p>{selectedRow.lastRunMeta} · {selectedRow.runs} changes · {selectedRow.description}</p>
            </div>
          </div>
          <article className="reference-builder-timeline">
            <div className="reference-builder-section-head">
              <div>
                <strong>Timeline</strong>
                <span>Key moments from this flow</span>
              </div>
            </div>
            <div className="reference-builder-moments">
              {timelineMoments.map(item => (
                <article className={cx("reference-builder-moment", item.tone)} key={item.id}>
                  <div className="reference-builder-moment-time">
                    <span>{item.time}</span>
                  </div>
                  <div className="reference-builder-moment-body">
                    <strong>{item.title}</strong>
                    <p>{item.detail}</p>
                    {item.preview ? <div className="reference-builder-preview-chip">{item.preview}</div> : null}
                  </div>
                </article>
              ))}
            </div>
          </article>
          <article className="reference-builder-summary-panel">
            <div className="reference-builder-section-head">
              <div>
                <strong>Change Ledger</strong>
                <span>Files, comments, and execution signals from this run</span>
              </div>
            </div>
            <div className="reference-builder-stat-grid">
              <article>
                <span>Files touched</span>
                <strong>{changedItems.length}</strong>
              </article>
              <article>
                <span>Feedback items</span>
                <strong>{feedbackItems.length}</strong>
              </article>
              <article>
                <span>Work engine</span>
                <strong>{activeProject?.title || projectLabel}</strong>
              </article>
            </div>
            <div className="reference-builder-change-list">
              {(changedItems.length ? changedItems : ["No file changes recorded for this flow yet."]).slice(0, 4).map(item => (
                <div className="reference-builder-change-row" key={item}>
                  <span className={cx("reference-flow-dot", changedItems.length ? "good" : "neutral")} />
                  <p>{item}</p>
                </div>
              ))}
            </div>
          </article>
        </div>

        <div className="reference-builder-detail-column right">
          <div className="reference-builder-detail-actions">
            <button className="reference-topbar-pill active" onClick={() => onRequestAction?.("builder:detail-live-preview", { missionId: selectedRow.id })} type="button">
              <Monitor size={16} strokeWidth={1.9} />
              <span>Live Preview</span>
            </button>
            <button
              className="reference-outline-button"
              onClick={() => onRequestAction?.("builder:open-in-builder", { missionId: selectedRow.id })}
              type="button"
            >
              <Hammer size={16} strokeWidth={1.9} />
              <span>Open in Builder</span>
            </button>
            <IconButton
              icon={MoreHorizontal}
              label="More"
              onClick={() => onRequestAction?.("builder:detail-more", { missionId: selectedRow.id })}
            />
          </div>
          <article className="reference-builder-preview-panel">
            <div className="reference-detail-tabs compact">
              <button className={detailPreviewTab === "preview" ? "active" : ""} onClick={() => setDetailPreviewTab("preview")} type="button">Preview</button>
              <button className={detailPreviewTab === "files" ? "active" : ""} onClick={() => setDetailPreviewTab("files")} type="button">Files</button>
              <button className={detailPreviewTab === "changes" ? "active" : ""} onClick={() => setDetailPreviewTab("changes")} type="button">Changes ({changedItems.length})</button>
            </div>
            <div className="reference-builder-preview-surface">
              <div className="reference-browser-brand">
                <div className="reference-brand-mark tiny">
                  <span />
                  <span />
                  <span />
                </div>
              <strong>{projectLabel}</strong>
            </div>
            <h2>{selectedRow.name}</h2>
              <p>{changedItems[0] || "No live preview changes have been recorded for this flow yet."}</p>
              <div className="reference-browser-actions">
                <button className="primary" onClick={() => onRequestAction?.("builder:detail-primary", { missionId: selectedRow.id })} type="button">Primary Action</button>
                <button className="secondary" onClick={() => onRequestAction?.("builder:detail-secondary", { missionId: selectedRow.id })} type="button">Secondary</button>
              </div>
            </div>
          </article>
          <article className="reference-feedback-panel builder">
            <div className="reference-feedback-tabs">
              <button className={detailFeedbackTab === "feedback" ? "active" : ""} onClick={() => setDetailFeedbackTab("feedback")} type="button">Feedback</button>
              <button className={detailFeedbackTab === "notes" ? "active" : ""} onClick={() => setDetailFeedbackTab("notes")} type="button">Notes</button>
            </div>
            <div className="reference-feedback-list">
              {feedbackItems
                .filter(item => (detailFeedbackTab === "feedback" ? item.role !== "note" : true))
                .slice(0, 3)
                .map(item => (
                <article className="reference-feedback-item" key={item.id}>
                  <div className="reference-feedback-meta">
                    <strong>{item.author}</strong>
                    <span>{item.meta}</span>
                  </div>
                  <p>{item.body}</p>
                  {item.role === "assistant" ? (
                    <div className="reference-feedback-actions">
                      <button onClick={() => onRequestAction?.("builder:feedback-apply", { feedbackId: item.id, missionId: selectedRow.id })} type="button">Change applied</button>
                      <button onClick={() => onRequestAction?.("builder:feedback-view", { feedbackId: item.id, missionId: selectedRow.id })} type="button">View change</button>
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
            <div className="reference-feedback-composer">
              <span>Add feedback or ask the agent...</span>
              <ArrowUp size={16} strokeWidth={2} />
            </div>
          </article>
        </div>
      </section>
    );
  }

  return (
    <section className="reference-builder-surface">
      <div className="reference-builder-head">
        <div>
          <h1>Builder</h1>
          <p>Build, run, and iterate on all your vibe coding projects.</p>
        </div>
        <div className="reference-builder-head-actions">
          <button
            className="reference-outline-button strong"
            onClick={() => onRequestAction?.("builder:new-project")}
            type="button"
          >
            <Plus size={18} strokeWidth={1.9} />
            <span>New Project</span>
          </button>
          <IconButton
            icon={LayoutGrid}
            label="Grid view"
            onClick={() => onRequestAction?.("builder:toggle-view")}
          />
        </div>
      </div>

      <div className="reference-builder-metrics-row">
        {builderMetrics.map(item => (
          <BuilderMetricCard item={item} key={item.id} />
        ))}
      </div>

      <div className="reference-builder-rule-strip">
        <div>
          <span>Rule Sets</span>
          <strong>
            {ruleSets.find(item => item.id === activeRuleSetId)?.name ||
              ruleSets[0]?.name ||
              "No rule set selected"}
          </strong>
          <p>
            {ruleSets.find(item => item.id === activeRuleSetId)?.description ||
              "Configure routing, approvals, autonomy, and execution targets before a builder run starts."}
          </p>
        </div>
        <div className="reference-inline-actions">
          {ruleSets.slice(0, 3).map(item => (
            <StatusBadge
              key={`builder-rule-${item.id}`}
              label={item.name}
              tone={item.id === activeRuleSetId ? "completed" : "paused"}
            />
          ))}
          <button className="reference-outline-button strong" onClick={onOpenSkillStudio} type="button">
            Edit rule sets
          </button>
        </div>
      </div>

      <div className="reference-builder-table-shell">
        <div className="reference-builder-toolbar">
          <label className="reference-search-field">
            <Search size={18} strokeWidth={1.9} />
            <input
              onChange={event => {
                setBuilderSearch(event.target.value);
                setBuilderPage(1);
              }}
              placeholder="Search projects..."
              value={builderSearch}
            />
          </label>
          <button className="reference-select-button" onClick={() => onRequestAction?.("builder:filter-status")} type="button">
            <span>Status</span>
            <ChevronDown size={16} strokeWidth={1.9} />
          </button>
          <button className="reference-select-button" onClick={() => onRequestAction?.("builder:filter-stack")} type="button">
            <span>Tech Stack</span>
            <ChevronDown size={16} strokeWidth={1.9} />
          </button>
          <button className="reference-select-button" onClick={() => onRequestAction?.("builder:filter-updated")} type="button">
            <span>Last Updated</span>
            <ChevronDown size={16} strokeWidth={1.9} />
          </button>
          <button className="reference-select-button compact" onClick={() => onRequestAction?.("builder:filters")} type="button">
            <Filter size={17} strokeWidth={1.9} />
            <span>Filters</span>
          </button>
          <IconButton
            icon={Settings}
            label="Builder settings"
            onClick={() => onRequestAction?.("builder:settings")}
          />
        </div>

        <div className="reference-builder-table">
          <div className="reference-builder-table-head">
            <span>Project</span>
            <span>Status</span>
            <span>Last Run</span>
            <span>Turning Point</span>
            <span>Success Rate</span>
            <span>Runs</span>
            <span>Updated</span>
            <span />
          </div>

          {pagedBuilderRows.map(row => {
            const successRate =
              typeof row.successRate === "number" && Number.isFinite(row.successRate)
                ? Math.max(0, Math.min(100, row.successRate))
                : null;
            return (
              <article
                className={cx("reference-builder-row action", row.selected && "selected")}
                key={row.id}
                onClick={() => onOpenBuilderDetail(row.id)}
                onKeyDown={event => openBuilderDetailFromKey(event, row.id)}
                role="button"
                tabIndex={0}
              >
                <div className="reference-project-cell">
                  <div className="reference-project-icon">
                    <Code2 size={18} strokeWidth={1.9} />
                  </div>
                  <div>
                    <strong>{row.name}</strong>
                    <p>{row.description}</p>
                  </div>
                </div>
                <div>
                  <StatusBadge label={row.status} tone={row.statusTone} />
                </div>
                <div className="reference-table-dual">
                  <strong>{row.lastRun}</strong>
                  <span>{row.lastRunMeta}</span>
                </div>
                <div className="reference-table-dual">
                  <strong>{row.turningPoint}</strong>
                  <span className={cx("reference-turning-delta", row.turningPointTone)}>{row.turningPointDelta}</span>
                </div>
                <div className="reference-success-cell">
                  <strong>{successRate === null ? "—" : `${successRate}%`}</strong>
                  <div className="reference-success-track">
                    <span style={{ width: `${successRate ?? 0}%` }} />
                  </div>
                </div>
                <strong>{row.runs}</strong>
                <span className="reference-updated">{row.updated}</span>
                <IconButton
                  icon={MoreHorizontal}
                  label="Project actions"
                  onClick={event => {
                    event.stopPropagation();
                    onRequestAction?.("builder:project-actions", { missionId: row.id });
                  }}
                />
              </article>
            );
          })}
          {!filteredBuilderRows.length ? (
            <div className="reference-builder-empty-state">
              <strong>{builderRows.length ? "No matches found" : "No builder runs yet"}</strong>
              <p>
                {builderRows.length
                  ? "Try a different project search term."
                  : "Start a mission from Agent or create a workspace run; Builder will populate from real mission activity."}
              </p>
            </div>
          ) : null}
        </div>

        <div className="reference-builder-pagination">
          <span>
            {filteredBuilderRows.length > 0
              ? `Showing ${pageStart + 1} to ${Math.min(pageStart + pageSize, filteredBuilderRows.length)} of ${filteredBuilderRows.length} projects`
              : "No projects to show yet"}
          </span>
          {filteredBuilderRows.length > 0 ? (
            <div className="reference-page-buttons">
              <button disabled={effectiveBuilderPage <= 1} onClick={() => setBuilderPage(page => Math.max(1, page - 1))} type="button">‹</button>
              {Array.from({ length: totalPages }, (_, index) => index + 1).slice(0, 6).map(page => (
                <button
                  className={page === effectiveBuilderPage ? "active" : ""}
                  key={`builder-page-${page}`}
                  onClick={() => setBuilderPage(page)}
                  type="button"
                >
                  {page}
                </button>
              ))}
              <button disabled={effectiveBuilderPage >= totalPages} onClick={() => setBuilderPage(page => Math.min(totalPages, page + 1))} type="button">›</button>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function SkillHubSurface({ onRequestAction, studioState }) {
  const {
    activeRuleSetId,
    activeSkillIds = [],
    collectionTab = "skill",
    onApplyProposal,
    onAssistantFieldChange,
    onAssistantSubmit,
    onFieldChange,
    onInsertDraft,
    onListChange,
    onPublish,
    onRouteFieldChange,
    onSaveDraft,
    onSelectItem,
    ruleSets = [],
    selectedItem,
    skills = [],
    totals = { totalSkills: 0, activeSkills: 0, totalRuleSets: 0, activeRuleSets: 0, environments: 0, knowledgeBases: 0 },
  } = studioState;
  const assistant = selectedItem?.assistant || {};
  const proposal = assistant.proposal || null;
  const isRule = selectedItem?.kind === "rule";
  const historyRows = asList(assistant.conversation);
  const overridesValue = asList(selectedItem?.overrides)
    .map(item => `${item.target} :: ${item.mode} :: ${item.detail}`)
    .join("\n");
  const [skillSearch, setSkillSearch] = useState("");
  const searchTerm = String(skillSearch || "").trim().toLowerCase();
  const visibleSkills =
    searchTerm.length === 0
      ? skills
      : skills.filter(item =>
          [item.name, item.summary, item.description]
            .map(value => String(value || "").toLowerCase())
            .some(value => value.includes(searchTerm)),
        );
  const visibleRuleSets =
    searchTerm.length === 0
      ? ruleSets
      : ruleSets.filter(item =>
          [item.name, item.summary, item.description]
            .map(value => String(value || "").toLowerCase())
            .some(value => value.includes(searchTerm)),
        );

  return (
    <section className="reference-skill-surface detail-mode">
      <div className="reference-skill-toolbar">
        <div>
          <p className="reference-breadcrumb">
            Skills Hub / <strong>{selectedItem?.name || "Skill Studio"}</strong>
          </p>
          <div className="reference-inline-badges">
            <h1>{selectedItem?.name || "Skills Hub"}</h1>
            {selectedItem?.badge ? <span className="reference-surface-badge">{selectedItem.badge}</span> : null}
          </div>
        </div>
        <div className="reference-builder-head-actions">
          <button className="reference-outline-button" onClick={() => onRequestAction?.("skills:version-history")} type="button">
            <History size={16} strokeWidth={1.9} />
            <span>Version History</span>
          </button>
          <button className="reference-outline-button" onClick={() => onRequestAction?.("skills:propose-from-mission")} type="button">
            <Sparkles size={16} strokeWidth={1.9} />
            <span>Propose from mission</span>
          </button>
          <button className="reference-outline-button" onClick={onSaveDraft} type="button">
            <FileText size={16} strokeWidth={1.9} />
            <span>Save Draft</span>
          </button>
          <button className="reference-black-button" onClick={onPublish} type="button">
            Publish
          </button>
          <IconButton icon={MoreHorizontal} label="More actions" onClick={() => onRequestAction?.("skills:more-actions")} />
        </div>
      </div>

      <div className="reference-skill-detail-grid">
        <article className="reference-skill-panel reference-studio-sidebar">
          <SectionPillTabs
            onChange={value => onSelectItem(value, value === "rule" ? ruleSets[0]?.id : skills[0]?.id)}
            tabs={[
              { value: "skill", label: "Skill" },
              { value: "rule", label: "Rule Set" },
            ]}
            value={collectionTab}
          />

          <label className="reference-search-field">
            <Search size={18} strokeWidth={1.9} />
            <input
              onChange={event => setSkillSearch(event.target.value)}
              placeholder="Search skills & rule sets..."
              value={skillSearch}
            />
          </label>

          <div className="reference-studio-list-section">
            <div className="reference-builder-section-head">
              <strong>Skills</strong>
              <button aria-label="Add skill" className="reference-mini-icon" onClick={() => onRequestAction?.("skills:add-skill")} type="button">
                <Plus size={14} strokeWidth={2} />
              </button>
            </div>
            <div className="reference-skill-list">
              {visibleSkills.map(item => (
                <button
                  className={cx("reference-skill-row", selectedItem?.id === item.id && "active")}
                  key={item.id}
                  onClick={() => onSelectItem("skill", item.id)}
                  type="button"
                >
                  <div>
                    <strong>{item.name}</strong>
                    <p>{item.summary}</p>
                  </div>
                  <div className="reference-list-item-meta">
                    {activeSkillIds.includes(item.id) ? <span className="reference-flow-dot good" /> : null}
                    <StatusBadge
                      label={item.status}
                      tone={item.status === "Draft" ? "paused" : "completed"}
                    />
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="reference-studio-list-section">
            <div className="reference-builder-section-head">
              <strong>Rule Sets</strong>
              <button aria-label="Add rule set" className="reference-mini-icon" onClick={() => onRequestAction?.("skills:add-rule-set")} type="button">
                <Plus size={14} strokeWidth={2} />
              </button>
            </div>
            <div className="reference-skill-list">
              {visibleRuleSets.map(item => (
                <button
                  className={cx("reference-skill-row", selectedItem?.id === item.id && "active")}
                  key={item.id}
                  onClick={() => onSelectItem("rule", item.id)}
                  type="button"
                >
                  <div>
                    <strong>{item.name}</strong>
                    <p>{item.summary}</p>
                  </div>
                  <div className="reference-list-item-meta">
                    {activeRuleSetId === item.id ? <span className="reference-flow-dot good" /> : null}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <button className="reference-studio-archive" onClick={() => onRequestAction?.("skills:view-archived")} type="button">
            <BookOpen size={16} strokeWidth={1.9} />
            <span>View archived</span>
          </button>
        </article>

        <article className="reference-skill-panel reference-studio-editor">
          {selectedItem ? (
            <>
              <div className="reference-builder-section-head">
                <strong>{selectedItem.badge}</strong>
                <div className="reference-inline-actions">
                  <button className="reference-link-button" onClick={() => onRequestAction?.("skills:edit-item", { itemId: selectedItem.id })} type="button">Edit</button>
                  <button className="reference-link-button" onClick={() => onRequestAction?.("skills:preview-item", { itemId: selectedItem.id })} type="button">Preview</button>
                </div>
              </div>

              <SurfaceField label="Name">
                <input onChange={event => onFieldChange("name", event.target.value)} value={selectedItem.name} />
              </SurfaceField>

              <SurfaceField label="Description">
                <textarea
                  onChange={event => onFieldChange("description", event.target.value)}
                  rows={3}
                  value={selectedItem.description}
                />
              </SurfaceField>
              {selectedItem.kind === "skill" ? (
                <div className="reference-studio-lifecycle">
                  <div className="reference-inline-badges">
                    <StatusBadge label={`Validation: ${selectedItem.validationStatus || "Pending"}`} tone={(selectedItem.validationStatus || "").includes("Pass") ? "completed" : "running"} />
                    <StatusBadge label={`Tests: ${selectedItem.testStatus || "Not run"}`} tone={(selectedItem.testStatus || "").includes("Pass") ? "completed" : "running"} />
                    <StatusBadge label={`Publish: ${selectedItem.publishReadiness || "Needs review"}`} tone={(selectedItem.publishReadiness || "").includes("Ready") ? "completed" : "paused"} />
                  </div>
                  <p>{selectedItem.lastValidationSummary || "Validation summary unavailable."}</p>
                  <p>{selectedItem.lastTestSummary || "Test summary unavailable."}</p>
                  <div className="reference-inline-actions">
                    <button className="reference-outline-button" onClick={() => onRequestAction?.("skills:validate-item")} type="button">Validate</button>
                    <button className="reference-outline-button" onClick={() => onRequestAction?.("skills:test-item")} type="button">Run tests</button>
                    <button className="reference-outline-button" onClick={() => onRequestAction?.("skills:promote-learned")} type="button">Promote learned</button>
                  </div>
                  {selectedItem.reviewRequired ? <p>Human review required before publish.</p> : <p>Ready for publish review.</p>}
                </div>
              ) : null}
            </>
          ) : null}
        </article>

        <article className="reference-skill-panel reference-studio-assistant">
          <div className="reference-builder-section-head">
            <strong>Ask a model</strong>
            <button className="reference-link-button" onClick={() => onRequestAction?.("skills:collapse-assistant")} type="button">Collapse</button>
          </div>
          <div className="reference-inline-form-row">
            <SurfaceField label="Model">
              <select
                onChange={event => onAssistantFieldChange("model", event.target.value)}
                value={assistant.model || "gpt-5.5"}
              >
                <option value="gpt-5.5">gpt-5.5</option>
                <option value="GPT-4o">GPT-4o</option>
                <option value="gpt-5.4-mini">gpt-5.4-mini</option>
                <option value="gpt-5.4">gpt-5.4</option>
                <option value="claude-sonnet-4.5">claude-sonnet-4.5</option>
              </select>
            </SurfaceField>
            <SurfaceField label="Effort">
              <select
                onChange={event => onAssistantFieldChange("effort", event.target.value)}
                value={assistant.effort || "Balanced"}
              >
                <option value="Low">Low</option>
                <option value="Balanced">Balanced</option>
                <option value="High">High</option>
              </select>
            </SurfaceField>
          </div>

          <div className="reference-studio-chat">
            {historyRows.length > 0 ? (
              historyRows.map((row, index) => (
                <article className="reference-studio-chat-row" key={`${row.role}-${index}`}>
                  <div className="reference-feedback-meta">
                    <strong>{row.author}</strong>
                    <span>{row.meta}</span>
                  </div>
                  <p>{row.body}</p>
                </article>
              ))
            ) : (
              <article className="reference-studio-chat-row empty">
                <p>Use this panel to refine the selected skill or rule set and apply the proposal directly.</p>
              </article>
            )}
          </div>

          {proposal ? (
            <div className="reference-studio-proposal">
              <div className="reference-builder-section-head">
                <strong>{isRule ? "Proposed changes" : "Guardrails (changes)"}</strong>
                <StatusBadge label="Added" tone="completed" />
              </div>
              <pre>{proposal.changes.map(line => `+ ${line}`).join("\n")}</pre>
              <div className="reference-inline-actions stretch">
                <button className="reference-black-button" onClick={onApplyProposal} type="button">
                  Apply changes
                </button>
                <button className="reference-outline-button" onClick={onInsertDraft} type="button">
                  Insert as draft
                </button>
              </div>
            </div>
          ) : null}

          <div className="reference-studio-compose">
            <textarea
              onChange={event => onAssistantFieldChange("prompt", event.target.value)}
              placeholder={isRule ? "Ask the model to refine this rule set..." : "Ask the model to refine this skill..."}
              rows={4}
              value={assistant.prompt || ""}
            />
            <div className="reference-composer-footer compact">
              <button className="reference-tool-button" onClick={() => onRequestAction?.("skills:attach-context")} type="button">
                <Paperclip size={18} strokeWidth={1.9} />
              </button>
              <button className="reference-send-button solid" onClick={onAssistantSubmit} type="button">
                <ArrowUp size={16} strokeWidth={2} />
              </button>
            </div>
          </div>
        </article>
      </div>

      {selectedItem ? (
        <div className="reference-skill-detail-lower">
          {isRule ? (
            <>
              <div className="reference-two-column-grid">
                <SurfaceField label="Scope / Applies to">
                  <input onChange={event => onFieldChange("scope", event.target.value)} value={selectedItem.scope} />
                </SurfaceField>
                <SurfaceField label="Autonomy mode">
                  <input
                    onChange={event => onFieldChange("autonomyMode", event.target.value)}
                    value={selectedItem.autonomyMode}
                  />
                </SurfaceField>
                <SurfaceField label="Approval mode">
                  <input
                    onChange={event => onFieldChange("approvalMode", event.target.value)}
                    value={selectedItem.approvalMode}
                  />
                </SurfaceField>
                <SurfaceField label="Default reviewer">
                  <input onChange={event => onFieldChange("reviewer", event.target.value)} value={selectedItem.reviewer} />
                </SurfaceField>
              </div>

              <div className="reference-rule-matrix">
                <article>
                  <strong>Allowed actions</strong>
                  <textarea
                    onChange={event => onListChange("allowedActions", event.target.value)}
                    rows={4}
                    value={joinEditorLines(selectedItem.allowedActions)}
                  />
                </article>
                <article>
                  <strong>Requires approval</strong>
                  <textarea
                    onChange={event => onListChange("requiresApproval", event.target.value)}
                    rows={4}
                    value={joinEditorLines(selectedItem.requiresApproval)}
                  />
                </article>
                <article>
                  <strong>Restricted actions</strong>
                  <textarea
                    onChange={event => onListChange("restrictedActions", event.target.value)}
                    rows={4}
                    value={joinEditorLines(selectedItem.restrictedActions)}
                  />
                </article>
                <article>
                  <strong>Special cases</strong>
                  <textarea
                    onChange={event => onListChange("specialCases", event.target.value)}
                    rows={4}
                    value={joinEditorLines(selectedItem.specialCases)}
                  />
                </article>
              </div>

              <div className="reference-route-plan-grid">
                {Object.entries(selectedItem.routePlan || {}).map(([role, route]) => (
                  <article className="reference-route-plan-card" key={role}>
                    <strong>{role[0].toUpperCase() + role.slice(1)}</strong>
                    <div className="reference-inline-form-row">
                      <select
                        onChange={event => onRouteFieldChange(role, "provider", event.target.value)}
                        value={route.provider}
                      >
                        <option value="openai">OpenAI</option>
                        <option value="anthropic">Anthropic</option>
                        <option value="minimax">MiniMax</option>
                        <option value="openrouter">OpenRouter</option>
                      </select>
                      <select
                        onChange={event => onRouteFieldChange(role, "effort", event.target.value)}
                        value={route.effort}
                      >
                        <option value="low">Low</option>
                        <option value="medium">Balanced</option>
                        <option value="high">High</option>
                      </select>
                    </div>
                    <input
                      onChange={event => onRouteFieldChange(role, "model", event.target.value)}
                      value={route.model}
                    />
                  </article>
                ))}
              </div>

              <SurfaceField label="Folder or environment-specific overrides">
                <textarea
                  onChange={event =>
                    onFieldChange(
                      "overrides",
                      event.target.value
                        .split("\n")
                        .map(line => line.trim())
                        .filter(Boolean)
                        .map(line => {
                          const [target, mode, detail] = line.split("::").map(part => part.trim());
                          return { target: target || "", mode: mode || "", detail: detail || "" };
                        }),
                    )
                  }
                  rows={5}
                  value={overridesValue}
                />
              </SurfaceField>
            </>
          ) : (
            <>
              <SurfaceField label="Trigger conditions">
                <textarea
                  onChange={event => onFieldChange("triggerConditions", event.target.value)}
                  rows={3}
                  value={selectedItem.triggerConditions}
                />
              </SurfaceField>
              <SurfaceField label="Instructions">
                <textarea
                  onChange={event => onListChange("instructions", event.target.value)}
                  rows={7}
                  value={joinEditorLines(selectedItem.instructions)}
                />
              </SurfaceField>
              <SurfaceField label="Output style">
                <textarea
                  onChange={event => onListChange("outputStyle", event.target.value)}
                  rows={4}
                  value={joinEditorLines(selectedItem.outputStyle)}
                />
              </SurfaceField>
              <SurfaceField label="Guardrails">
                <textarea
                  onChange={event => onListChange("guardrails", event.target.value)}
                  rows={6}
                  value={joinEditorLines(selectedItem.guardrails)}
                />
              </SurfaceField>
            </>
          )}
        </div>
      ) : null}

      <div className="reference-skill-overview compact">
        <article><Code2 size={20} strokeWidth={1.9} /><strong>{totals.totalSkills}</strong><span>Total Skills</span><p>{totals.activeSkills} active</p></article>
        <article><FileText size={20} strokeWidth={1.9} /><strong>{totals.totalRuleSets}</strong><span>Rule Sets</span><p>{totals.activeRuleSets} active</p></article>
        <article><Database size={20} strokeWidth={1.9} /><strong>{totals.environments}</strong><span>Environments</span><p>4 active</p></article>
        <article><BookOpen size={20} strokeWidth={1.9} /><strong>{totals.knowledgeBases}</strong><span>Knowledge Bases</span><p>3 synced</p></article>
      </div>
    </section>
  );
}

function RuleSetsSurface({ onRequestAction, studioState }) {
  const {
    activeRuleSetId,
    onSelectItem,
    ruleSets = [],
    selectedItem,
    totals = { totalRuleSets: 0, activeRuleSets: 0 },
  } = studioState || {};
  const selectedRule =
    ruleSets.find(item => item.id === activeRuleSetId) ||
    (selectedItem?.kind === "rule" ? selectedItem : null) ||
    ruleSets[0] ||
    null;

  return (
    <section className="reference-skill-surface detail-mode">
      <div className="reference-skill-toolbar">
        <div>
          <p className="reference-breadcrumb">
            Workspace / <strong>Rule Sets</strong>
          </p>
          <div className="reference-inline-badges">
            <h1>Rule Sets</h1>
            <span className="reference-surface-badge">Core policy</span>
          </div>
        </div>
        <div className="reference-builder-head-actions">
          <button className="reference-outline-button" onClick={() => onRequestAction?.("rule-sets:audit")} type="button">
            <Shield size={16} strokeWidth={1.9} />
            <span>Audit permissions</span>
          </button>
          <button className="reference-outline-button" onClick={() => onRequestAction?.("skills:add-rule-set")} type="button">
            <Plus size={16} strokeWidth={1.9} />
            <span>New rule set</span>
          </button>
        </div>
      </div>

      <div className="reference-skill-detail-grid rule-set-overview-grid">
        <article className="reference-skill-panel reference-studio-sidebar">
          <div className="reference-builder-section-head">
            <strong>Permission modes</strong>
            <StatusBadge label={`${totals.activeRuleSets || 0} active`} tone="completed" />
          </div>
          <div className="reference-skill-list">
            {ruleSets.map(item => (
              <button
                className={cx("reference-skill-row", selectedRule?.id === item.id && "active")}
                key={item.id}
                onClick={() => onSelectItem?.("rule", item.id)}
                type="button"
              >
                <div>
                  <strong>{item.name}</strong>
                  <p>{item.summary}</p>
                </div>
                <div className="reference-list-item-meta">
                  {activeRuleSetId === item.id ? <span className="reference-flow-dot good" /> : null}
                  <StatusBadge label={item.approvalMode || "Policy"} tone={activeRuleSetId === item.id ? "completed" : "paused"} />
                </div>
              </button>
            ))}
          </div>
        </article>

        <article className="reference-skill-panel reference-studio-editor">
          <div className="reference-builder-section-head">
            <strong>{selectedRule?.name || "No rule set selected"}</strong>
            <div className="reference-inline-actions">
              <button className="reference-link-button" onClick={() => onRequestAction?.("rule-sets:duplicate", { ruleSetId: selectedRule?.id })} type="button">Duplicate</button>
              <button className="reference-link-button" onClick={() => onRequestAction?.("rule-sets:edit", { ruleSetId: selectedRule?.id })} type="button">Edit</button>
            </div>
          </div>
          {selectedRule ? (
            <>
              <div className="reference-two-column-grid">
                <SurfaceField label="Applies to">
                  <input readOnly value={selectedRule.scope || "Workspace"} />
                </SurfaceField>
                <SurfaceField label="Autonomy">
                  <input readOnly value={selectedRule.autonomyMode || "Not configured"} />
                </SurfaceField>
                <SurfaceField label="Approval mode">
                  <input readOnly value={selectedRule.approvalMode || "Not configured"} />
                </SurfaceField>
                <SurfaceField label="Reviewer">
                  <input readOnly value={selectedRule.reviewer || "Operator"} />
                </SurfaceField>
              </div>

              <div className="reference-rule-matrix">
                <article>
                  <strong>Allowed</strong>
                  <ul>{asList(selectedRule.allowedActions).map(item => <li key={item}>{item}</li>)}</ul>
                </article>
                <article>
                  <strong>Approval required</strong>
                  <ul>{asList(selectedRule.requiresApproval).map(item => <li key={item}>{item}</li>)}</ul>
                </article>
                <article>
                  <strong>Restricted</strong>
                  <ul>{asList(selectedRule.restrictedActions).map(item => <li key={item}>{item}</li>)}</ul>
                </article>
                <article>
                  <strong>Special cases</strong>
                  <ul>{asList(selectedRule.specialCases).map(item => <li key={item}>{item}</li>)}</ul>
                </article>
              </div>
            </>
          ) : (
            <p>No rule sets are available for this workspace.</p>
          )}
        </article>

        <article className="reference-skill-panel reference-studio-assistant">
          <div className="reference-builder-section-head">
            <strong>Runtime guardrails</strong>
            <StatusBadge label="Visible" tone="completed" />
          </div>
          <div className="reference-skill-overview compact nested">
            <article><Shield size={20} strokeWidth={1.9} /><strong>{totals.totalRuleSets || ruleSets.length}</strong><span>Total</span><p>Rule sets</p></article>
            <article><CircleCheckBig size={20} strokeWidth={1.9} /><strong>{totals.activeRuleSets || 0}</strong><span>Active</span><p>Applied now</p></article>
            <article><SquareTerminal size={20} strokeWidth={1.9} /><strong>{asList(selectedRule?.requiresApproval).length}</strong><span>Approval gates</span><p>Commands and writes</p></article>
          </div>
          <p>
            Rule Sets control how much autonomy the agent has before it reads files,
            writes files, runs commands, uses tools, changes branches, or reaches outside
            the selected workspace.
          </p>
          <button className="reference-black-button" onClick={() => onRequestAction?.("rule-sets:apply-active", { ruleSetId: selectedRule?.id })} type="button">
            Apply to current run
          </button>
        </article>
      </div>
    </section>
  );
}

function SettingsSurface({ onRequestAction, settingsState }) {
  const {
    activeRuleSet,
    activeTab = "general",
    appearance,
    authOptions = { openai: [], minimax: [] },
    codexImport = {
      available: false,
      recentThreads: [],
      workspaces: [],
      notes: [],
      sessionCount: 0,
      skillCount: 0,
    },
    members = [],
    onImportAllCodexWorkspaces,
    onImportCodexWorkspace,
    onPickWorkspaceFolder,
    onRefreshCodexImport,
    onApplyActiveRuleSet,
    onRouteOverrideChange,
    onSaveWorkspacePolicy,
    onSetAppearance,
    onSetTab,
    onWorkspaceProfileFieldChange,
    privacy = { conversationRetention: "90 days", fileRetention: "30 days" },
    providers = [],
    bridgeSessions = [],
    storageBridge = {},
    setupServices = [],
    chatgptConnection = {},
    routeOptions = { harnesses: [], providers: [], efforts: [], models: [], routingStrategies: [], executionTargets: [] },
    runtimes = [],
    sidebarBehaviorOptions = [],
    workspaceId,
    workspaceName,
    workspaceProfileForm = {
      userProfile: "builder",
      preferredHarness: "",
      openaiCodexAuthMode: "none",
      minimaxAuthMode: "none",
      routingStrategy: "profile_default",
      executionTargetPreference: "workspace_root",
      routeOverrides: [],
    },
  } = settingsState;
  const tabDefs = [
    ["general", "General", Settings],
    ["providers", "Models", Sparkles],
    ["storage", "Storage", Database],
    ["tools", "Tools & Ports", SquareTerminal],
    ["rules", "Rules & Routing", Shield],
    ["members", "Members", Users],
    ["privacy", "Data & Privacy", Database],
  ];
  const previewSwatches = [
    ["Primary accent", appearance.accent],
    ["Secondary accent", appearance.accentAlt],
    ["Surface", appearance.surface],
    ["Card surface", appearance.surfaceSoft],
  ];
  const appearancePresets = [
    {
      id: "graphite-gold",
      name: "Graphite Gold",
      description: "Black, gray, and restrained gold. This is the Syntelos default.",
      values: {
        accent: "#d6a84f",
        accentAlt: "#9aa3a0",
        surface: "#ffffff",
        surfaceSoft: "#f6f8fc",
        line: "#d8deea",
        text: "#121826",
        stylePreset: "graphite-gold",
      },
    },
    {
      id: "operator-dark",
      name: "Operator Dark",
      description: "Dense dark control room with gold action focus.",
      values: {
        accent: "#d6a84f",
        accentAlt: "#7ed996",
        surface: "#121514",
        surfaceSoft: "#1a1e1c",
        line: "#343a37",
        text: "#f7f1e8",
        stylePreset: "operator-dark",
      },
    },
    {
      id: "school-calm",
      name: "School Calm",
      description: "Low-noise classroom preset for tutorials and guided users.",
      values: {
        accent: "#b98a35",
        accentAlt: "#667085",
        surface: "#f7f7f2",
        surfaceSoft: "#ffffff",
        line: "#d8dccf",
        text: "#171b1a",
        stylePreset: "school-calm",
      },
    },
    {
      id: "neo-brutalist",
      name: "Neo Brutalist",
      description: "Paper, hard ink, loud panels, and physical controls.",
      values: {
        accent: "#f4c430",
        accentAlt: "#ff6b4a",
        surface: "#fff8dc",
        surfaceSoft: "#f2ead0",
        line: "#111111",
        text: "#101010",
        stylePreset: "neo-brutalist",
      },
    },
    {
      id: "blueprint-lab",
      name: "Blueprint Lab",
      description: "Technical blueprints, cyan lines, and calm engineering surfaces.",
      values: {
        accent: "#58c7f3",
        accentAlt: "#f4c430",
        surface: "#071827",
        surfaceSoft: "#0e2a3d",
        line: "#5ec8ef",
        text: "#e8fbff",
        stylePreset: "blueprint-lab",
      },
    },
    {
      id: "signal-bloom",
      name: "Signal Bloom",
      description: "Warm paper, coral actions, mint status, and editorial energy.",
      values: {
        accent: "#ff6b4a",
        accentAlt: "#48bf84",
        surface: "#fff2e1",
        surfaceSoft: "#ffe1d6",
        line: "#2a211b",
        text: "#1f1712",
        stylePreset: "signal-bloom",
      },
    },
    {
      id: "console-candy",
      name: "Console Candy",
      description: "Bright terminal rhythm with saturated rails and readable dark panels.",
      values: {
        accent: "#8df15a",
        accentAlt: "#ff5fa2",
        surface: "#0e1014",
        surfaceSoft: "#181c22",
        line: "#2f3745",
        text: "#f7fbff",
        stylePreset: "console-candy",
      },
    },
    {
      id: "cel-rig",
      name: "Cel Rig",
      description: "Animation-cel flats, keyline shadows, timing marks, and clean color holds.",
      values: {
        accent: "#2f6bff",
        accentAlt: "#ffcf3f",
        surface: "#f8fbff",
        surfaceSoft: "#dceaff",
        line: "#101820",
        text: "#101820",
        stylePreset: "cel-rig",
      },
    },
    {
      id: "texture-board",
      name: "Texture Board",
      description: "Material swatches, paper grain, region labels, and tactile output checks.",
      values: {
        accent: "#7a5c34",
        accentAlt: "#4f8f6b",
        surface: "#f5ead7",
        surfaceSoft: "#e8d4b3",
        line: "#2b2118",
        text: "#201812",
        stylePreset: "texture-board",
      },
    },
    {
      id: "style-bible",
      name: "Style Bible",
      description: "Reference sheets for palette, line weight, texture, staging, and motion timing.",
      values: {
        accent: "#b84cff",
        accentAlt: "#16b8a6",
        surface: "#fbf7ff",
        surfaceSoft: "#efe2ff",
        line: "#24152d",
        text: "#201426",
        stylePreset: "style-bible",
      },
    },
  ];
  const applyAppearancePreset = preset => {
    Object.entries(preset.values).forEach(([key, value]) => onSetAppearance(key, value));
  };
  const bridgePortRows = asList(bridgeSessions).map(session => {
    const endpoint = String(session.bridge_endpoint || session.bridgeEndpoint || "");
    let host = endpoint || "local";
    let port = "";
    try {
      const parsed = new URL(endpoint);
      host = parsed.hostname || endpoint;
      port = parsed.port || (parsed.protocol === "https:" ? "443" : parsed.protocol === "http:" ? "80" : "");
    } catch {
      const match = endpoint.match(/:(\d+)(?:\/|$)/);
      port = match?.[1] || "";
    }
    return {
      id: session.app_id || session.session_id || endpoint,
      label: session.app_name || session.app_id || "Bridge",
      role: session.ui_hints?.bridgeRole || session.serviceRole || session.bridge_transport || "bridge",
      host,
      port: port || session.ui_hints?.controlPort || session.latest_task_result?.payload?.controlPort || "",
      status: session.bridge_health || session.status || "unknown",
      actions: asList(session.serviceActions),
    };
  });
  const managedServiceRows = asList(setupServices).map(service => ({
    id: service.serviceId || service.label,
    label: service.label || service.serviceId,
    role: service.serviceRole || service.serviceCategory || service.installSource || "service",
    host: service.bridgeEndpoint || service.installSource || service.version || "local",
    port: service.controlPort || service.port || "",
    status: service.currentHealthStatus || service.lastVerificationResult || "unknown",
    actions: asList(service.serviceActions),
  }));
  const managementRows = Array.from(
    [...bridgePortRows, ...managedServiceRows].filter(item => item.id).reduce((rows, item) => {
      const existing = rows.get(item.id);
      if (!existing) {
        rows.set(item.id, item);
        return rows;
      }
      rows.set(item.id, {
        ...existing,
        ...item,
        host: item.host || existing.host,
        port: item.port || existing.port,
        status: item.status || existing.status,
        actions: [...asList(existing.actions), ...asList(item.actions)],
      });
      return rows;
    }, new Map()).values(),
  );
  const collectBridgeActions = matcher => {
    const seen = new Set();
    return managementRows.flatMap(row =>
      asList(row.actions).map(action => ({ ...action, serviceLabel: row.label, serviceRole: row.role })),
    ).filter(action => {
      const key = `${action.actionId || action.label}-${action.commandSurface || ""}-${action.serviceRole || ""}`;
      if (seen.has(key) || !matcher(action)) {
        return false;
      }
      seen.add(key);
      return true;
    });
  };
  const nasActions = collectBridgeActions(action =>
    /nas|sync|ssh|fast/i.test(`${action.serviceRole || ""} ${action.actionId || ""} ${action.label || ""}`),
  );
  const cloudActions = collectBridgeActions(action =>
    /cloud|drive|google/i.test(`${action.serviceRole || ""} ${action.actionId || ""} ${action.label || ""}`),
  );
  const storageQuickActions = [...nasActions, ...cloudActions].slice(0, 6);

  return (
    <section className="reference-settings-surface">
      <div className="reference-settings-header">
        <div>
          <h1>Settings</h1>
          <p>Manage your workspace, models, setup, appearance, and privacy.</p>
        </div>
      </div>

      <div className="reference-settings-tabs">
        {tabDefs.map(([id, label, Icon]) => (
          <button
            className={activeTab === id ? "active" : ""}
            key={id}
            onClick={() => onSetTab(id)}
            type="button"
          >
            <Icon size={15} strokeWidth={1.9} />
            <span>{label}</span>
          </button>
        ))}
      </div>

      {activeTab === "general" ? (
        <div className="reference-settings-general-layout">
          <div className="reference-settings-stack-column">
            <article className="reference-settings-card">
              <strong>Workspace</strong>
              <SurfaceField label="Workspace Name">
                <div className="reference-static-value">{workspaceName}</div>
              </SurfaceField>
              <SurfaceField label="Workspace ID">
                <div className="reference-static-value">{workspaceId}</div>
              </SurfaceField>
              <SurfaceField label="Workspace profile">
                <select
                  onChange={event => onWorkspaceProfileFieldChange("userProfile", event.target.value)}
                  value={workspaceProfileForm.userProfile}
                >
                  <option value="beginner">Beginner</option>
                  <option value="builder">Builder</option>
                  <option value="advanced">Advanced</option>
                  <option value="experimental">Experimental</option>
                </select>
              </SurfaceField>
              <SurfaceField label="Preferred work engine">
                <select
                  onChange={event => onWorkspaceProfileFieldChange("preferredHarness", event.target.value)}
                  value={workspaceProfileForm.preferredHarness}
                >
                  {routeOptions.harnesses.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </SurfaceField>
              <SurfaceField label="NAS sync mode">
                <select
                  onChange={event => {
                    const enabled = event.target.value !== "manual";
                    onWorkspaceProfileFieldChange("syncMode", event.target.value);
                    onWorkspaceProfileFieldChange("autoSyncToNas", enabled);
                  }}
                  value={workspaceProfileForm.syncMode || "manual"}
                >
                  <option value="manual">Manual</option>
                  <option value="auto_nas_mirror">Auto NAS mirror</option>
                  <option value="synology_drive">Synology Drive</option>
                </select>
              </SurfaceField>
              <SurfaceField label="Computer folder">
                <input
                  onChange={event => onWorkspaceProfileFieldChange("localProjectPath", event.target.value)}
                  placeholder="C:/Users/paul/Projects/my-project"
                  value={workspaceProfileForm.localProjectPath || ""}
                />
              </SurfaceField>
              <SurfaceField label="NAS mirror folder">
                <input
                  onChange={event => onWorkspaceProfileFieldChange("nasProjectPath", event.target.value)}
                  placeholder="/volume1/Saclay/projects/my-project"
                  value={workspaceProfileForm.nasProjectPath || ""}
                />
              </SurfaceField>
              <SurfaceField label="Sync direction">
                <select
                  onChange={event => onWorkspaceProfileFieldChange("syncDirection", event.target.value)}
                  value={workspaceProfileForm.syncDirection || "bidirectional"}
                >
                  <option value="bidirectional">Bidirectional</option>
                  <option value="local_to_nas">Local to NAS</option>
                  <option value="nas_to_local">NAS to local</option>
                </select>
              </SurfaceField>
              <div className="reference-settings-actions">
                <button className="reference-black-button" onClick={onSaveWorkspacePolicy} type="button">
                  Save changes
                </button>
              </div>
            </article>

            <article className="reference-settings-card">
              <div className="reference-builder-section-head">
                <div>
                  <strong>Codex projects and folders</strong>
                  <span>
                    Bring over recent Codex folders, inspect recent threads, and add a project folder.
                  </span>
                </div>
                <div className="reference-inline-actions">
                  <button
                    className="reference-outline-button"
                    disabled={codexImport.isRefreshing}
                    onClick={onRefreshCodexImport}
                    type="button"
                  >
                    {codexImport.isRefreshing ? "Scanning..." : "Refresh"}
                  </button>
                  <button className="reference-outline-button" onClick={onPickWorkspaceFolder} type="button">
                    <FolderOpen size={16} strokeWidth={1.9} />
                    <span>Add folder</span>
                  </button>
                  <button
                    className="reference-black-button"
                    disabled={!asList(codexImport.workspaces).length}
                    onClick={onImportAllCodexWorkspaces}
                    type="button"
                  >
                    Import all
                  </button>
                </div>
              </div>
              <div className="reference-settings-summary-grid">
                <article><span>Codex home</span><strong>{codexImport.codexHome || "Not found"}</strong></article>
                <article><span>Recent threads</span><strong>{codexImport.sessionCount || 0}</strong></article>
                <article><span>Detected workspaces</span><strong>{asList(codexImport.workspaces).length}</strong></article>
                <article><span>Local skills</span><strong>{codexImport.skillCount || 0}</strong></article>
              </div>
              {asList(codexImport.notes).length ? (
                <div className="reference-note-stack">
                  {codexImport.notes.map(note => (
                    <p className="reference-surface-footnote" key={note}>{note}</p>
                  ))}
                </div>
              ) : null}
              {codexImport.isRefreshing && !asList(codexImport.workspaces).length ? (
                <p className="reference-surface-footnote">
                  Scanning Codex sources in the background. The rest of Settings is ready to use.
                </p>
              ) : null}
              <div className="reference-provider-grid codex">
                {asList(codexImport.workspaces).map(item => (
                  <article className="reference-provider-card" key={item.path}>
                    <div className="reference-builder-section-head">
                      <div>
                        <strong>{item.name}</strong>
                        <span>{item.path}</span>
                      </div>
                      <StatusBadge label={`${item.threadCount || 0} threads`} tone="completed" />
                    </div>
                    <p>{item.latestThreadName || "Recent Codex workspace"}</p>
                    <div className="reference-inline-actions stretch">
                      <button className="reference-black-button" onClick={() => onImportCodexWorkspace(item)} type="button">
                        Import folder
                      </button>
                    </div>
                  </article>
                ))}
              </div>
              {asList(codexImport.recentThreads).length ? (
                <div className="reference-studio-chat compact">
                  {codexImport.recentThreads.slice(0, 6).map(thread => (
                    <article className="reference-studio-chat-row" key={thread.id}>
                      <div className="reference-feedback-meta">
                        <strong>{thread.threadName}</strong>
                        <span>{thread.updatedAt || "Recent"}</span>
                      </div>
                      <p>{thread.cwd || thread.source || "No workspace path recorded."}</p>
                    </article>
                  ))}
                </div>
              ) : null}
            </article>
          </div>

          <div className="reference-settings-stack-column">
            <article className="reference-settings-card">
              <div className="reference-builder-section-head">
                <div>
                  <strong>Linux and setup</strong>
                  <span>Syntelos checks these for you and shows install or update buttons when something is missing.</span>
                </div>
              </div>
              <div className="reference-settings-summary-grid">
                {asList(setupServices)
                  .filter(item => ["wsl2", "uv", "opencv", "openclaw", "hermes"].includes(item.serviceId))
                  .map(item => (
                    <article key={`setup-service-${item.serviceId}`}>
                      <span>{item.serviceId === "wsl2" ? "Linux helper" : item.label}</span>
                      <strong>
                        {item.currentHealthStatus === "healthy"
                          ? "Ready"
                          : item.updateAvailable
                            ? "Update available"
                            : "Needs setup"}
                      </strong>
                      <p>{item.details}</p>
                    </article>
                  ))}
              </div>
            </article>

            <article className="reference-settings-card">
              <strong>Appearance</strong>
              <details className="reference-settings-fold" open>
                <summary>Theme and collapse behavior</summary>
                <div className="reference-settings-block">
                <span>Theme</span>
                <div className="reference-theme-toggle">
                  <button className={appearance.theme === "light" ? "active" : ""} onClick={() => onSetAppearance("theme", "light")} type="button"><SunMedium size={18} strokeWidth={1.9} /><span>Light</span></button>
                  <button className={appearance.theme === "dark" ? "active" : ""} onClick={() => onSetAppearance("theme", "dark")} type="button"><Moon size={18} strokeWidth={1.9} /><span>Dark</span></button>
                  <button className={appearance.theme === "system" ? "active" : ""} onClick={() => onSetAppearance("theme", "system")} type="button"><Monitor size={18} strokeWidth={1.9} /><span>System</span></button>
                </div>
                </div>
                <div className="reference-settings-block">
                  <span>Sidebar behavior</span>
                  <div className="reference-density-toggle">
                    {sidebarBehaviorOptions.map(option => (
                      <button
                        className={appearance.sidebarBehavior === option.value ? "active" : ""}
                        key={option.value}
                        onClick={() => onSetAppearance("sidebarBehavior", option.value)}
                        type="button"
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                </div>
              </details>

              <details className="reference-settings-fold" open>
                <summary>Color presets</summary>
                <div className="reference-preset-grid">
                  {appearancePresets.map(preset => (
                    <button
                      className="reference-preset-card"
                      key={preset.id}
                      onClick={() => applyAppearancePreset(preset)}
                      type="button"
                    >
                      <span>{preset.name}</span>
                      <strong>{preset.description}</strong>
                      <i style={{ background: preset.values.accent }} />
                      <i style={{ background: preset.values.accentAlt }} />
                      <i style={{ background: preset.values.surfaceSoft }} />
                    </button>
                  ))}
                </div>
                <div className="reference-settings-block">
                <span>Accent Color</span>
                <div className="reference-color-swatches">
                  {["#d6a84f", "#9aa3a0", "#1fb68f", "#f59e0b", "#e14f63"].map(color => (
                    <button
                      className={appearance.accent === color ? "active" : ""}
                      key={color}
                      onClick={() => onSetAppearance("accent", color)}
                      style={{ background: color }}
                      type="button"
                    />
                  ))}
                </div>
                </div>
              </details>

              <details className="reference-settings-fold" open>
                <summary>Style and texture system</summary>
                <div className="reference-style-dna-grid" aria-label="Style production controls">
                  <article>
                    <span>Reference capture</span>
                    <strong>Boards, shots, and UI crops</strong>
                    <p>Collect example screens, animation stills, and product screenshots as named references.</p>
                  </article>
                  <article>
                    <span>Region language</span>
                    <strong>Palette, line, shape, texture</strong>
                    <p>Describe each surface by material rules rather than one vague style label.</p>
                  </article>
                  <article>
                    <span>Motion timing</span>
                    <strong>Ease, hold, anticipation</strong>
                    <p>Record animation-industry timing notes so generated output can match the intended feel.</p>
                  </article>
                  <article>
                    <span>Output proof</span>
                    <strong>Compare, annotate, export</strong>
                    <p>Keep generated UI, image, or video frames tied to comments and verification screenshots.</p>
                  </article>
                </div>
              </details>

              <details className="reference-settings-fold" open>
                <summary>Information density</summary>
                <div className="reference-settings-block">
                  <span>Density</span>
                  <div className="reference-density-toggle">
                    {["compact", "comfortable", "spacious"].map(option => (
                      <button
                        className={appearance.density === option ? "active" : ""}
                        key={option}
                        onClick={() => onSetAppearance("density", option)}
                        type="button"
                      >
                        {option[0].toUpperCase() + option.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="reference-settings-block">
                  <span>Info mode</span>
                  <div className="reference-density-toggle">
                    {[
                      ["minimal", "Less info"],
                      ["balanced", "Balanced"],
                      ["expanded", "More info"],
                    ].map(([value, label]) => (
                      <button
                        className={(appearance.detailLevel || "balanced") === value ? "active" : ""}
                        key={value}
                        onClick={() => onSetAppearance("detailLevel", value)}
                        type="button"
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              </details>

              <details className="reference-settings-fold">
                <summary>Advanced color tokens</summary>
                <div className="reference-settings-color-grid">
                {[
                  ["accent", "Primary Accent"],
                  ["accentAlt", "Secondary Accent"],
                  ["surface", "Settings Surface"],
                  ["surfaceSoft", "Card Surface"],
                  ["line", "Border Color"],
                  ["text", "Text Color"],
                ].map(([key, label]) => (
                  <SurfaceField key={key} label={label}>
                    <input
                      onChange={event => onSetAppearance(key, event.target.value)}
                      type="color"
                      value={appearance[key]}
                    />
                  </SurfaceField>
                ))}
                </div>
              </details>
            </article>

            <article className="reference-settings-card reference-settings-preview-card">
              <div className="reference-builder-section-head">
                <div>
                  <strong>Interface Preview</strong>
                  <span>Immediate preview of the current color tokens and shell behavior</span>
                </div>
                <Palette size={18} strokeWidth={1.9} />
              </div>
              <div
                className="reference-settings-live-preview"
                style={{
                  background: `linear-gradient(180deg, ${appearance.surfaceSoft} 0%, ${appearance.surface} 100%)`,
                  borderColor: appearance.line,
                  color: appearance.text,
                }}
              >
                <div className="reference-settings-live-preview-topbar">
                  <span>Syntelos Shell</span>
                  <div className="reference-settings-preview-pill-row">
                    <span style={{ background: appearance.accent, color: "#fff" }}>Primary</span>
                    <span style={{ background: appearance.accentAlt, color: appearance.text }}>Secondary</span>
                  </div>
                </div>
                <div className="reference-settings-live-preview-body">
                  <article style={{ borderColor: appearance.line }}>
                    <strong>Workspace Canvas</strong>
                    <p>Cards, controls, and backgrounds update from the appearance settings.</p>
                  </article>
                  <article style={{ borderColor: appearance.line }}>
                    <strong>Desktop Layout</strong>
                    <p>The rail, app canvas, and panels keep the same spacing system while colors change.</p>
                  </article>
                </div>
                <div className="reference-settings-preview-swatches">
                  {previewSwatches.map(([label, value]) => (
                    <div key={label}>
                      <span>{label}</span>
                      <strong>{value}</strong>
                    </div>
                  ))}
                </div>
              </div>
            </article>
          </div>
        </div>
      ) : null}

      {activeTab === "storage" ? (
        <div className="reference-settings-stack">
          <article className="reference-settings-card">
            <div className="reference-builder-section-head">
              <div>
                <strong>Computer and NAS bridge</strong>
                <span>
                  Keep local folders editable while a NAS-hosted runtime can stay online and use the same project tree.
                </span>
              </div>
              <StatusBadge
                label={storageBridge.connected ? "Connected" : storageBridge.available ? "Available" : "Not found"}
                tone={storageBridge.connected ? "completed" : storageBridge.available ? "running" : "paused"}
              />
            </div>
            <div className="reference-bridge-console">
              <article className="reference-bridge-node source">
                <span>Computer workspace</span>
                <strong>{storageBridge.sourceRoot || storageBridge.cloud?.sourceRoot || "Choose a local folder"}</strong>
                <p>Editable files stay on this machine while the runtime can keep running elsewhere.</p>
              </article>
              <article className="reference-bridge-route">
                <span>{storageBridge.selectedMode || storageBridge.cloud?.selectedMode || "configure"}</span>
                <strong>{storageBridge.safeDirections?.length ? storageBridge.safeDirections.join(" + ") : "preview required"}</strong>
                <p>{storageBridge.writePolicy || "preview_then_approve"} / {storageBridge.conflictPolicy || "keep_newer_and_log"}</p>
              </article>
              <article className="reference-bridge-node target">
                <span>Always-on targets</span>
                <strong>{storageBridge.targetRoot || storageBridge.cloud?.targetRoot || "NAS or Drive not mapped"}</strong>
                <p>
                  {storageBridge.selectedHost || storageBridge.cloud?.selectedHost || "Connect Synology, Google Drive, or another mounted folder."}
                </p>
              </article>
            </div>
            <div className="reference-bridge-action-bar">
              <div>
                <strong>Bridge commands</strong>
                <span>Runs through the same approval-aware workspace action contract as every other tool.</span>
              </div>
              <div className="reference-inline-actions compact">
                {storageQuickActions.length ? (
                  storageQuickActions.map(action => (
                    <button
                      className={action.requiresApproval ? "reference-outline-button" : "reference-link-button"}
                      key={`storage-action-${action.actionId}-${action.serviceRole || action.label}`}
                      onClick={() => onRequestAction?.("settings:run-action", { action })}
                      type="button"
                    >
                      {action.label || action.actionId}
                    </button>
                  ))
                ) : (
                  <StatusBadge label="No direct actions yet" tone="paused" />
                )}
              </div>
            </div>
            <div className="reference-settings-summary-grid">
              <article><span>Computer folder</span><strong>{storageBridge.sourceRoot || "Not mapped"}</strong></article>
              <article><span>NAS folder</span><strong>{storageBridge.targetRoot || "Not mapped"}</strong></article>
              <article><span>Route</span><strong>{storageBridge.selectedMode || "Offline"}</strong></article>
              <article>
                <span>Host</span>
                <strong>
                  {storageBridge.selectedHost || storageBridge.endpoint || "Not selected"}
                  {storageBridge.controlPort ? `:${storageBridge.controlPort}` : ""}
                </strong>
              </article>
              <article><span>Control</span><strong>{storageBridge.controlProtocol || storageBridge.nas?.controlProtocol || "ssh"} {storageBridge.controlPort || storageBridge.nas?.controlPort || 22}</strong></article>
              <article><span>Web route</span><strong>{storageBridge.nas?.publicEndpoint || storageBridge.publicEndpoint || storageBridge.nas?.endpoint || "HTTPS via DSM proxy"}</strong></article>
              <article><span>Port status</span><strong>{storageBridge.sshPortStatus || storageBridge.nas?.sshPortStatus || "Operator configured"}</strong></article>
              <article><span>Remote user</span><strong>{storageBridge.sshUser || storageBridge.nas?.sshUser || "Not configured"}</strong></article>
              <article><span>Remote root</span><strong>{storageBridge.remoteProjectRoot || storageBridge.nas?.remoteProjectRoot || "Not configured"}</strong></article>
            </div>
            {storageBridge.activationRequired || storageBridge.nas?.activationRequired ? (
              <article className="reference-provider-card">
                <div className="reference-builder-section-head">
                  <div>
                    <strong>{storageBridge.activationProject || storageBridge.nas?.activationProject || "Core"} activation needed</strong>
                    <span>{storageBridge.activationHint || storageBridge.nas?.activationHint || "Activate the storage project before using the NAS mapping."}</span>
                  </div>
                  <StatusBadge label="Mapping inactive" tone="paused" />
                </div>
                <p className="reference-surface-footnote">
                  {storageBridge.activationCommand || storageBridge.nas?.activationCommand || "C:/Users/paul/Projects/Cowork/map-synology-fast-path.cmd"}
                </p>
              </article>
            ) : null}
            <div className="reference-provider-grid">
              <article className="reference-provider-card">
                <strong>Transfer policy</strong>
                <p>
                  {storageBridge.writePolicy || "preview_then_approve"} · conflicts use {storageBridge.conflictPolicy || "keep_newer_and_log"}.
                </p>
                <div className="reference-inline-actions compact">
                  {asList(storageBridge.safeDirections).length ? (
                    storageBridge.safeDirections.map(direction => (
                      <StatusBadge key={direction} label={direction} tone="completed" />
                    ))
                  ) : (
                    <StatusBadge label="No write direction ready" tone="paused" />
                  )}
                  {storageBridge.requiresApprovalForWrite ? (
                    <StatusBadge label="Writes require approval" tone="running" />
                  ) : null}
                </div>
              </article>
              <article className="reference-provider-card">
                <strong>Current transfer</strong>
                <p>{storageBridge.summary || "No active upload or download is being reported."}</p>
                <div className="reference-inline-actions compact">
                  <StatusBadge label={storageBridge.health || "unknown"} tone={storageBridge.connected ? "completed" : "paused"} />
                  <StatusBadge label={storageBridge.activeDirection || "idle"} tone={storageBridge.activeDirection ? "running" : "paused"} />
                </div>
              </article>
            </div>
          </article>

          <article className="reference-settings-card">
            <div className="reference-builder-section-head">
              <div>
                <strong>Cloud drive bridge</strong>
                <span>Use Google Drive or another mounted cloud folder as a second storage route for project files.</span>
              </div>
              <StatusBadge
                label={storageBridge.cloud?.connected ? "Connected" : storageBridge.cloud?.available ? "Configure" : "Not registered"}
                tone={storageBridge.cloud?.connected ? "completed" : storageBridge.cloud?.available ? "running" : "paused"}
              />
            </div>
            <div className="reference-settings-summary-grid">
              <article><span>Computer folder</span><strong>{storageBridge.cloud?.sourceRoot || storageBridge.sourceRoot || "Not mapped"}</strong></article>
              <article><span>Cloud folder</span><strong>{storageBridge.cloud?.targetRoot || "Not mounted"}</strong></article>
              <article><span>Provider</span><strong>{storageBridge.cloud?.selectedHost || "Google Drive"}</strong></article>
              <article><span>Login</span><strong>{storageBridge.cloud?.googleLoginReady ? "Google ready" : "Needs Google login"}</strong></article>
            </div>
            <div className="reference-provider-grid">
              <article className="reference-provider-card">
                <strong>Mounted folders</strong>
                <div className="reference-note-stack">
                  {asList(storageBridge.cloud?.mountedRoots).length ? (
                    asList(storageBridge.cloud?.mountedRoots).slice(0, 4).map(item => (
                      <p className="reference-surface-footnote" key={`${item.provider}-${item.root}`}>
                        {item.provider}: {item.root}
                      </p>
                    ))
                  ) : (
                    <p>Google Drive for desktop, OneDrive, Dropbox, or a custom mounted path has not been detected.</p>
                  )}
                </div>
              </article>
              <article className="reference-provider-card">
                <strong>Cloud transfer policy</strong>
                <p>{storageBridge.cloud?.summary || "Cloud storage is waiting for a mounted folder or Google OAuth token."}</p>
                <div className="reference-inline-actions compact">
                  {asList(storageBridge.cloud?.safeDirections).length ? (
                    storageBridge.cloud.safeDirections.map(direction => (
                      <StatusBadge key={direction} label={direction} tone="completed" />
                    ))
                  ) : (
                    <StatusBadge label="No cloud write direction ready" tone="paused" />
                  )}
                  <StatusBadge label={storageBridge.cloud?.writePolicy || "preview_then_approve"} tone="running" />
                </div>
                <div className="reference-inline-actions compact">
                  <button
                    className="reference-outline-button"
                    onClick={() => window.open(storageBridge.cloud?.loginUrl || "https://drive.google.com/drive/my-drive", "_blank", "noopener,noreferrer")}
                    type="button"
                  >
                    <Database size={16} strokeWidth={1.9} />
                    <span>Open Google Drive</span>
                  </button>
                  <button
                    className="reference-link-button"
                    onClick={() => window.open(storageBridge.cloud?.desktopClientUrl || "https://www.google.com/drive/download/", "_blank", "noopener,noreferrer")}
                    type="button"
                  >
                    Drive desktop
                  </button>
                </div>
              </article>
            </div>
          </article>

          <article className="reference-settings-card">
            <div className="reference-builder-section-head">
              <div>
                <strong>Connected bridge sessions</strong>
                <span>Storage is managed through the same app capability contract as voice, monitoring, and future tools.</span>
              </div>
            </div>
            <div className="reference-provider-grid">
              {asList(bridgeSessions).length ? (
                asList(bridgeSessions).map(session => (
                  <article className={cx("reference-provider-card", session.status === "connected" && "connected")} key={session.session_id || session.app_id}>
                    <div className="reference-builder-section-head">
                      <div>
                        <strong>{session.app_name || session.app_id}</strong>
                        <span>{session.bridge_endpoint || session.bridge_transport || "Bridge manifest"}</span>
                      </div>
                      <StatusBadge label={session.bridge_health || session.status} tone={session.status === "connected" ? "completed" : "paused"} />
                    </div>
                    <p>{session.latest_task_result?.resultSummary || asList(session.notes)[0] || "No bridge task has reported yet."}</p>
                    {asList(session.context_preview).length ? (
                      <div className="reference-note-stack">
                        {asList(session.context_preview[0]?.items).slice(0, 5).map(item => (
                          <p className="reference-surface-footnote" key={`${session.app_id}-${item}`}>{item}</p>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))
              ) : (
                <article className="reference-provider-card">
                  <strong>No bridge sessions</strong>
                  <p>Register a connected app manifest before using NAS or tool bridge surfaces.</p>
                </article>
              )}
            </div>
          </article>
        </div>
      ) : null}

      {activeTab === "tools" ? (
        <div className="reference-settings-stack">
          <article className="reference-settings-card">
            <div className="reference-builder-section-head">
              <div>
                <strong>Tool and port management</strong>
                <span>
                  Runtime tools, connected-app bridges, NAS control, browser use, image tooling, and repair actions are listed here with their real endpoint state.
                </span>
              </div>
              <StatusBadge
                label={`${managementRows.length} managed`}
                tone={managementRows.some(item => item.status !== "healthy" && item.status !== "connected") ? "running" : "completed"}
              />
            </div>
            <div className="reference-port-grid">
              {managementRows.length ? (
                managementRows.map(item => (
                  <article className="reference-port-card" key={`tool-port-${item.id}`}>
                    <div>
                      <strong>{item.label}</strong>
                      <span>{item.role}</span>
                    </div>
                    <dl>
                      <div>
                        <dt>Endpoint</dt>
                        <dd>{item.host || "local"}</dd>
                      </div>
                      <div>
                        <dt>Port</dt>
                        <dd>{item.port || "n/a"}</dd>
                      </div>
                      <div>
                        <dt>Status</dt>
                        <dd>{item.status}</dd>
                      </div>
                    </dl>
                    {asList(item.actions).length ? (
                      <div className="reference-inline-actions compact">
                        {asList(item.actions).slice(0, 3).map(action => (
                          <button
                            className={action.requiresApproval ? "reference-outline-button" : "reference-link-button"}
                            key={`${item.id}-${action.actionId}`}
                            onClick={() => onRequestAction?.("settings:run-action", { action })}
                            type="button"
                          >
                            {action.label || action.actionId}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p>No direct action is exposed yet.</p>
                    )}
                  </article>
                ))
              ) : (
                <article className="reference-port-card">
                  <div>
                    <strong>No managed services found</strong>
                    <span>setup</span>
                  </div>
                  <p>Run setup verification so Syntelos can inventory runtimes, image tools, bridges, and browser/computer-use ports.</p>
                </article>
              )}
            </div>
          </article>

          <article className="reference-settings-card">
            <div className="reference-builder-section-head">
              <div>
                <strong>Planned control ports</strong>
                <span>These are the app areas that should become first-class managed tools as features land.</span>
              </div>
            </div>
            <div className="reference-provider-grid">
              {[
                ["Image management", "Image generation, visual QA, asset folders, and selected-output promotion."],
                ["Browser use", "Local browser sessions, screenshots, page actions, and proof capture."],
                ["Computer use", "Desktop action lanes with approval boundaries and visible replay."],
                ["NAS runtime", "SSH/SFTP control on the detected SSH port plus optional SMB drive-letter sync."],
              ].map(([label, copy]) => (
                <article className="reference-provider-card" key={label}>
                  <strong>{label}</strong>
                  <p>{copy}</p>
                </article>
              ))}
            </div>
          </article>
        </div>
      ) : null}

      {activeTab === "providers" ? (
        <div className="reference-settings-stack">
          <article className="reference-settings-card">
            <strong>Model accounts</strong>
            <div className="reference-provider-grid">
              {providers.map(provider => (
                <article className={cx("reference-provider-card", provider.status && "connected")} key={provider.id}>
                  <div className="reference-builder-section-head">
                    <div>
                      <strong>{provider.label}</strong>
                      <span>{provider.env}</span>
                    </div>
                    <StatusBadge
                      label={provider.status ? "Connected" : provider.hasSecret ? "Key saved" : "Missing"}
                      tone={provider.status || provider.hasSecret ? "completed" : "paused"}
                    />
                  </div>
                  <p>{provider.note}</p>
                  {provider.quickAuth ? (
                    <div className="reference-provider-quickauth">
                      <button
                        className="reference-outline-button"
                        disabled={Boolean(provider.quickAuth.disabled)}
                        onClick={provider.onQuickAuth}
                        title={provider.quickAuth.disabled ? provider.quickAuth.detail : ""}
                        type="button"
                      >
                        <Sparkles size={16} strokeWidth={1.9} />
                        <span>{provider.quickAuth.label}</span>
                      </button>
                      <span>{provider.quickAuth.detail}</span>
                    </div>
                  ) : null}
                  {asList(provider.authLinks).length ? (
                    <div className="reference-inline-actions compact">
                      {provider.authLinks.map(link => (
                        <button className="reference-link-button" key={link.label} onClick={link.onClick} type="button">
                          {link.label}
                        </button>
                      ))}
                    </div>
                  ) : null}
                  <SurfaceField label="API key">
                    <input
                      autoComplete="off"
                      onChange={event => provider.onDraftChange(event.target.value)}
                      placeholder={provider.hasSecret ? "Stored securely. Paste a new key to replace it." : `Paste ${provider.env}`}
                      type="password"
                      value={provider.draft}
                    />
                  </SurfaceField>
                  <div className="reference-inline-actions stretch">
                    <button
                      className="reference-black-button"
                      disabled={provider.savingState === "saving"}
                      onClick={provider.onSave}
                      type="button"
                    >
                      {provider.savingState === "saving" ? "Saving..." : "Save key"}
                    </button>
                    <button
                      className="reference-outline-button"
                      disabled={provider.savingState === "clearing"}
                      onClick={provider.onClear}
                      type="button"
                    >
                      {provider.savingState === "clearing" ? "Clearing..." : "Clear"}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </article>

          <article className="reference-settings-card">
            <strong>ChatGPT connection</strong>
            <p>
              A real ChatGPT connection is an app/connector backed by an MCP server. Opening
              ChatGPT in a browser does not authenticate Syntelos or connect this desktop app.
            </p>
            <div className="reference-two-column-grid">
              <SurfaceField label="Current Syntelos local API">
                <input readOnly value={chatgptConnection.localApiUrl || "Local API not running"} />
              </SurfaceField>
              <SurfaceField label="ChatGPT-compatible MCP endpoint">
                <input readOnly value={chatgptConnection.mcpEndpoint || "Not implemented yet"} />
              </SurfaceField>
            </div>
            <p className="reference-surface-footnote">
              To connect from ChatGPT, create a ChatGPT app/connector for a remote MCP server.
              Syntelos currently exposes a secured local REST API; the MCP bridge still needs to be
              exposed before ChatGPT can connect directly.
            </p>
            <div className="reference-settings-actions split">
              {asList(chatgptConnection.links).map(link => (
                <button className="reference-outline-button" key={link.label} onClick={link.onClick} type="button">
                  {link.label}
                </button>
              ))}
            </div>
          </article>

          <article className="reference-settings-card">
            <strong>Account preferences</strong>
            <div className="reference-two-column-grid">
              <SurfaceField label="OpenAI / Codex auth path">
                <select
                  onChange={event => onWorkspaceProfileFieldChange("openaiCodexAuthMode", event.target.value)}
                  value={workspaceProfileForm.openaiCodexAuthMode}
                >
                  {authOptions.openai.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </SurfaceField>
              <SurfaceField label="MiniMax auth path">
                <select
                  onChange={event => onWorkspaceProfileFieldChange("minimaxAuthMode", event.target.value)}
                  value={workspaceProfileForm.minimaxAuthMode}
                >
                  {authOptions.minimax.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </SurfaceField>
            </div>
            <div className="reference-settings-actions">
              <button className="reference-black-button" onClick={onSaveWorkspacePolicy} type="button">
                Save auth preferences
              </button>
            </div>
          </article>

          <article className="reference-settings-card">
            <strong>Work engine availability</strong>
            <div className="reference-provider-grid">
              {runtimes.map(runtime => (
                <article className={cx("reference-provider-card", runtime.detected && "connected")} key={runtime.runtime_id}>
                  <div className="reference-builder-section-head">
                    <div>
                      <strong>{runtime.label}</strong>
                      <span>{runtime.command || "CLI not detected"}</span>
                    </div>
                    <StatusBadge label={runtime.detected ? "Detected" : "Missing"} tone={runtime.detected ? "completed" : "paused"} />
                  </div>
                  <p>{runtime.doctor_summary || runtime.doctorSummary || "Work engine status is unavailable."}</p>
                  <RuntimeCapabilityPills capabilities={asList(runtime.capabilities)} />
                </article>
              ))}
            </div>
          </article>
        </div>
      ) : null}

      {activeTab === "rules" ? (
        <div className="reference-settings-stack">
          <article className="reference-settings-card">
            <div className="reference-builder-section-head">
              <div>
                <strong>Active Rule Set</strong>
                <span>{activeRuleSet?.description || "No rule set selected."}</span>
              </div>
              <button className="reference-black-button" onClick={onApplyActiveRuleSet} type="button">
                Apply rule set
              </button>
            </div>
            <div className="reference-settings-summary-grid">
              <article><span>Name</span><strong>{activeRuleSet?.name || "—"}</strong></article>
              <article><span>Approval mode</span><strong>{activeRuleSet?.approvalMode || "—"}</strong></article>
              <article><span>Work engine</span><strong>{workspaceProfileForm.preferredHarness}</strong></article>
              <article><span>Execution target</span><strong>{workspaceProfileForm.executionTargetPreference}</strong></article>
            </div>
          </article>

          <article className="reference-settings-card">
            <strong>Routing & Workspace Policy</strong>
            <div className="reference-two-column-grid">
              <SurfaceField label="Routing strategy">
                <select
                  onChange={event => onWorkspaceProfileFieldChange("routingStrategy", event.target.value)}
                  value={workspaceProfileForm.routingStrategy}
                >
                  {routeOptions.routingStrategies.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </SurfaceField>
              <SurfaceField label="Execution target">
                <select
                  onChange={event => onWorkspaceProfileFieldChange("executionTargetPreference", event.target.value)}
                  value={workspaceProfileForm.executionTargetPreference}
                >
                  {routeOptions.executionTargets.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </SurfaceField>
            </div>

            <div className="reference-route-plan-grid">
              {asList(workspaceProfileForm.routeOverrides).map(item => (
                <article className="reference-route-plan-card" key={item.role}>
                  <strong>{item.role[0].toUpperCase() + item.role.slice(1)}</strong>
                  <div className="reference-inline-form-row">
                    <select
                      onChange={event => onRouteOverrideChange(item.role, "provider", event.target.value)}
                      value={item.provider}
                    >
                      {routeOptions.providers.map(option => (
                        <option key={`${item.role}-${option.value}`} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <select
                      onChange={event => onRouteOverrideChange(item.role, "effort", event.target.value)}
                      value={item.effort}
                    >
                      {routeOptions.efforts.map(option => (
                        <option key={`${item.role}-${option.value}`} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <select
                    onChange={event => onRouteOverrideChange(item.role, "model", event.target.value)}
                    value={item.model}
                  >
                    <option value="">Profile default</option>
                    {uniq([item.model, ...asList(routeOptions.models)].filter(Boolean)).map(option => (
                      <option key={`${item.role}-${option}`} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </article>
              ))}
            </div>

            <div className="reference-settings-actions">
              <button className="reference-black-button" onClick={onSaveWorkspacePolicy} type="button">
                Save routing policy
              </button>
            </div>
          </article>
        </div>
      ) : null}

      {activeTab === "members" ? (
        <div className="reference-settings-stack">
          <article className="reference-settings-card">
            <strong>Workspace Members</strong>
            <div className="reference-member-list">
              {members.map(member => (
                <div className="reference-member-row" key={`${member.name}-${member.role}`}>
                  <div className="reference-user-mini">{member.name.slice(0, 2).toUpperCase()}</div>
                  <div>
                    <strong>{member.name}</strong>
                    <p>{member.role}</p>
                  </div>
                </div>
              ))}
            </div>
          </article>

          <article className="reference-settings-card">
            <div className="reference-builder-section-head">
              <div>
                <strong>Account and workspace permissions</strong>
                <span>Owner accounts can change setup, models, bridges, permissions, and destructive actions. Member accounts can work inside approved projects and ask for escalation.</span>
              </div>
            </div>
            <div className="reference-permission-grid">
              {[
                ["Owner console", "Models, provider keys, NAS bridge, tools, member roles, retention, and reset actions.", "owner"],
                ["Member console", "Agent chat, assigned workspaces, tutorials, school/work modes, and non-destructive file review.", "user"],
                ["Approval boundary", "Writes, desktop control, cloud transfer, NAS transfer, and permission changes require an approval gate.", "approval"],
              ].map(([title, copy, tone]) => (
                <article className={`reference-permission-card tone-${tone}`} key={title}>
                  <span>{title}</span>
                  <p>{copy}</p>
                </article>
              ))}
            </div>
          </article>
        </div>
      ) : null}

      {activeTab === "privacy" ? (
        <div className="reference-settings-grid">
          <article className="reference-settings-card">
            <strong>Data & Retention</strong>
            <SurfaceField label="Conversation retention">
              <input readOnly value={privacy.conversationRetention} />
            </SurfaceField>
            <SurfaceField label="File retention">
              <input readOnly value={privacy.fileRetention} />
            </SurfaceField>
            <div className="reference-settings-actions split">
              <button className="reference-outline-button" onClick={() => onRequestAction?.("settings:export-data")} type="button">
                <FileText size={16} strokeWidth={1.9} />
                <span>Export Data</span>
              </button>
              <button className="reference-danger-button" onClick={() => onRequestAction?.("settings:delete-workspace")} type="button">Delete Workspace</button>
            </div>
          </article>
          <article className="reference-settings-card">
            <strong>Workspace Notes</strong>
            <p>Sidebar behavior, color choices, account preferences, and routing policies are saved inside Syntelos.</p>
            <p>Published rule sets immediately update the workspace routing overrides used for agent follow-ups.</p>
          </article>
        </div>
      ) : null}
    </section>
  );
}

function LegacyFluxioReferenceShell(props) {
  const {
    agentScene,
    activeCommentTarget,
    appearance,
    appearanceStyle,
    builderDetailOpen,
    builderRows,
    changedItems,
    currentProjectLabel,
    draft,
    favoriteFlows,
    feedbackItems,
    flowProjects,
    generatedImageArtifacts,
    hermesEvidenceItems,
    messages,
    nasDeployChecks,
    conversationMode = "chat",
    onAttach,
    onBackFromBuilder,
    onChangeDraft,
    onDictation,
    onHistory,
    onIdleSubmit,
    onInsertSlashCommand,
    onMore,
    onOpenBuilderDetail,
    onOpenSettings,
    onOpenSkillStudio,
    onPaste,
    onRequestAction,
    onRuntimeChange,
    onSend,
    onSelectFlow,
    onSelectProject,
    onSetAgentScene,
    onSetAppearance,
    onSetSurface,
    callBackend,
    runtimeOptions,
    runtimeStatus,
    runtimeCompartment,
    routeControls,
    settingsState,
    selectedEffortLabel,
    selectedModelLabel,
    selectedHarnessMeta,
    selectedProjectId,
    selectedRuntime,
    slashCommands,
    sidebarBehavior = "auto",
    skillStudioState,
    surface,
    timelineMoments,
    missionLoop,
    workbenchState,
  } = props;
  const runtimeLabel =
    runtimeOptions.find(option => option.value === selectedRuntime)?.label || selectedRuntime;
  const showFlowSidebar = surface === "agent";
  const showAgentTopbar = surface === "agent";
  const topbarRoute = routeControls?.selectedRoute || {};
  const topbarWorkspacePath = String(runtimeCompartment?.cwd || "").replace(/\\/g, "/");
  const topbarWorkspaceLabel = topbarWorkspacePath
    ? topbarWorkspacePath.split("/").filter(Boolean).slice(-2).join("/")
    : "workspace";
  const topbarHost = runtimeCompartment?.host || "local";
  const topbarOnline = Boolean(runtimeCompartment);

  const mainContent =
    surface === "home" ? (
      <HomeSurface onOpenSurface={onSetSurface} onRequestAction={onRequestAction} />
    ) : surface === "skills" ? (
      <SkillHubSurface onRequestAction={onRequestAction} studioState={skillStudioState} />
    ) : surface === "rule-sets" ? (
      <RuleSetsSurface onRequestAction={onRequestAction} studioState={skillStudioState} />
    ) : surface === "images" ? (
      <ImagePlaygroundSurface callBackend={callBackend} />
    ) : surface === "workbench" ? (
      <WorkbenchSurface onRequestAction={onRequestAction} onSetSurface={onSetSurface} workbenchState={workbenchState} />
    ) : surface === "settings" ? (
      <SettingsSurface onRequestAction={onRequestAction} settingsState={settingsState} />
    ) : surface === "agent" && agentScene === "idle" ? (
      <AgentIdleSurface
        draft={draft}
        onAttach={onAttach}
        onChangeDraft={onChangeDraft}
        onDictation={onDictation}
        onIdleSubmit={onIdleSubmit}
        onRequestAction={onRequestAction}
        onPaste={onPaste}
        onRuntimeChange={onRuntimeChange}
        onUseSlashCommand={onInsertSlashCommand}
        runtimeOptions={runtimeOptions}
        runtimeStatus={runtimeStatus}
        routeControls={routeControls}
        selectedEffortLabel={selectedEffortLabel}
        selectedHarnessMeta={selectedHarnessMeta}
        selectedModelLabel={selectedModelLabel}
        selectedRuntime={selectedRuntime}
        slashCommands={slashCommands}
      />
    ) : surface === "agent" && agentScene === "run" ? (
      <AgentRunningSurface
        draft={draft}
        activeCommentTarget={activeCommentTarget}
        conversationMode={conversationMode}
        feedbackItems={feedbackItems}
        generatedImageArtifacts={generatedImageArtifacts}
        hermesEvidenceItems={hermesEvidenceItems}
        missionLoop={missionLoop}
        messages={messages}
        nasDeployChecks={nasDeployChecks}
        onAttach={onAttach}
        onChangeDraft={onChangeDraft}
        onDictation={onDictation}
        onPaste={onPaste}
        onRequestAction={onRequestAction}
        onRuntimeChange={onRuntimeChange}
        onSend={onSend}
        onUseSlashCommand={onInsertSlashCommand}
        runtimeCompartment={runtimeCompartment}
        routeControls={routeControls}
        runtimeOptions={runtimeOptions}
        selectedEffortLabel={selectedEffortLabel}
        selectedModelLabel={selectedModelLabel}
        selectedRuntime={selectedRuntime}
        selectedRuntimeLabel={runtimeLabel}
        slashCommands={slashCommands}
        timelineMoments={timelineMoments}
      />
    ) : surface === "agent" && agentScene === "live" ? (
      <LivePreviewSurface
        changedItems={changedItems}
        draft={draft}
        feedbackItems={feedbackItems}
        generatedImageArtifacts={generatedImageArtifacts}
        hermesEvidenceItems={hermesEvidenceItems}
        messages={messages}
        nasDeployChecks={nasDeployChecks}
        onAttach={onAttach}
        onChangeDraft={onChangeDraft}
        onDictation={onDictation}
        onPaste={onPaste}
        onRequestAction={onRequestAction}
        onSend={onSend}
        onUseSlashCommand={onInsertSlashCommand}
        projectLabel={currentProjectLabel}
        runtimeCompartment={runtimeCompartment}
        slashCommands={slashCommands}
        timelineMoments={timelineMoments}
      />
    ) : surface === "builder" ? (
      <BuilderSurface
        builderDetailOpen={builderDetailOpen}
        builderRows={builderRows}
        changedItems={changedItems}
        feedbackItems={feedbackItems}
        flowProjects={flowProjects}
        onBackFromBuilder={onBackFromBuilder}
        onOpenBuilderDetail={onOpenBuilderDetail}
        onRequestAction={onRequestAction}
        onOpenSkillStudio={onOpenSkillStudio}
        onSelectFlow={onSelectFlow}
        onSelectProject={onSelectProject}
        projectLabel={currentProjectLabel}
        activeRuleSetId={skillStudioState?.activeRuleSetId}
        ruleSets={skillStudioState?.ruleSets}
        selectedProjectId={selectedProjectId}
        timelineMoments={timelineMoments}
      />
    ) : null;

  return (
    <div
      className={cx("reference-shell", `surface-${surface}`)}
      data-agent-scene={surface === "agent" ? agentScene : undefined}
      data-detail-mode={showFlowSidebar || builderDetailOpen ? "true" : "false"}
      data-density={appearance?.density || "comfortable"}
      data-info-mode={appearance?.detailLevel || "balanced"}
      data-look={appearance?.stylePreset || "graphite-gold"}
      data-sidebar-behavior={sidebarBehavior}
      style={appearanceStyle}
    >
      <aside className="reference-sidebar">
        <div className="reference-sidebar-main">
          <RailBrand />

          <nav className="reference-sidebar-nav">
            {surface === "home" ? (
              <RailItem active icon={Home} label="Home" onClick={() => onSetSurface("home")} tone="home" />
            ) : (
              <RailItem active={surface === "home"} icon={Home} label="Home" onClick={() => onSetSurface("home")} />
            )}

            <div className="reference-sidebar-group">
              <span>Workspace</span>
              <RailItem
                active={surface === "agent"}
                icon={Bot}
                label="Agent"
                onClick={() => onSetSurface("agent")}
              />
              <RailItem
                active={surface === "builder"}
                icon={Hammer}
                label="Builder"
                onClick={() => onSetSurface("builder")}
                tone={surface === "builder" ? "gold" : "neutral"}
              />
              <RailItem
                active={surface === "skills"}
                icon={Grid2x2}
                label="Skills"
                onClick={onOpenSkillStudio}
              />
              <RailItem
                active={surface === "rule-sets"}
                icon={Shield}
                label="Rule Sets"
                onClick={() => onSetSurface("rule-sets")}
                tone={surface === "rule-sets" ? "gold" : "neutral"}
              />
              <RailItem
                active={surface === "images"}
                icon={Palette}
                label="Images"
                onClick={() => onSetSurface("images")}
                tone={surface === "images" ? "gold" : "neutral"}
              />
              <RailItem
                active={surface === "workbench"}
                icon={Laptop}
                label="Workbench"
                onClick={() => onSetSurface("workbench")}
              />
              <RailItem
                active={surface === "settings"}
                icon={Settings}
                label="Settings"
                onClick={onOpenSettings}
              />
            </div>
          </nav>
        </div>

        <SidebarProfile />
      </aside>

      <main className={cx("reference-main", showFlowSidebar && "with-flow-sidebar", surface === "settings" && "surface-settings")}>
        {showFlowSidebar ? (
          <>
            <FlowSidebar
              currentModeLabel="Agent"
              favoriteFlows={favoriteFlows}
              flowProjects={flowProjects}
              onRequestAction={onRequestAction}
              onOpenSettings={onOpenSettings}
              onSelectFlow={onSelectFlow}
              onSelectProject={onSelectProject}
              selectedProjectId={selectedProjectId}
            />
            <div className="reference-main-panel">
              {showAgentTopbar ? (
                <div className="reference-topbar">
                  <div className="reference-topbar-title">
                    <strong>Agent Chat</strong>
                    <div className="reference-project-pill">
                      <Bot size={15} strokeWidth={1.9} />
                      <span>Mission: {currentProjectLabel}</span>
                      <ChevronDown size={15} strokeWidth={1.9} />
                    </div>
                    <div className="reference-chat-topbar-meta">
                      <span>Model: {selectedModelLabel}</span>
                      <span>Route: {topbarRoute.role || "primary"}</span>
                      <span>Workspace: {topbarWorkspaceLabel}</span>
                      <span>Host: {topbarHost}</span>
                      <span className={cx("status", topbarOnline ? "online" : "offline")}>
                        {topbarOnline ? "Online" : "Offline"}
                      </span>
                    </div>
                  </div>
                  <div className="reference-topbar-actions">
                    <button className="reference-black-button" onClick={onHistory} type="button">
                      Stop Agent
                    </button>
                    <button className="reference-outline-button" onClick={onMore} type="button">
                      Pause
                    </button>
                    <button className="reference-outline-button" onClick={onMore} type="button">
                      Share
                    </button>
                    <IconButton icon={MoreHorizontal} label="More actions" onClick={onMore} />
                  </div>
                </div>
              ) : null}
              <div className={cx("reference-main-body", surface === "settings" && "settings-body")}>{mainContent}</div>
            </div>
          </>
        ) : (
          <>
            <div className="reference-main-body">{mainContent}</div>
          </>
        )}
      </main>
    </div>
  );
}

const FLUXIO_NAV_ITEMS = [
  { id: "home", label: "Home", Icon: Home },
  { id: "agent", label: "Agent", Icon: Bot },
  { id: "builder", label: "Builder", Icon: Hammer },
  { id: "skills", label: "Skills", Icon: Grid2x2 },
  { id: "rule-sets", label: "Rule Sets", Icon: Shield },
  { id: "images", label: "Images", Icon: Palette },
  { id: "workbench", label: "Workbench", Icon: Laptop },
  { id: "settings", label: "Settings", Icon: Settings },
];

const FLUXIO_THEMES = [
  {
    id: "noir",
    label: "Fluxio Noir",
    bestFor: "Daily work",
    density: "Balanced",
    motion: "Calm",
    contrast: "High",
  },
  {
    id: "glass",
    label: "Glass OS",
    bestFor: "AI workspace",
    density: "Balanced",
    motion: "Fluid",
    contrast: "High",
  },
  {
    id: "terminal",
    label: "Terminal Ops",
    bestFor: "Runs and logs",
    density: "Compact",
    motion: "Minimal",
    contrast: "High",
  },
  {
    id: "blueprint",
    label: "Blueprint Lab",
    bestFor: "Builder maps",
    density: "Balanced",
    motion: "Precise",
    contrast: "High",
  },
  {
    id: "swiss",
    label: "Swiss Editorial",
    bestFor: "Research",
    density: "Spacious",
    motion: "Minimal",
    contrast: "High",
  },
  {
    id: "brutal",
    label: "Neo-Brutalist",
    bestFor: "Experimental",
    density: "Comfortable",
    motion: "Snappy",
    contrast: "Very high",
  },
];

const FLUXIO_THEME_STORAGE_KEY = "fluxio.os.theme";

const AGENT_PLAN = [
  ["Scope", "Read project state and collect reference intent.", "done"],
  ["Edit", "Apply the shell, review bundle, and visual control surfaces.", "running"],
  ["Verify", "Run build, browser smoke, and responsive screenshots.", "queued"],
  ["Merge gate", "Summarize changed files, evidence, and remaining risk.", "queued"],
];

const TOOL_EVENTS = [
  ["13:44:12", "Read image pack", "17 references indexed", "good"],
  ["13:46:03", "Inspect app shell", "React/Vite control route", "good"],
  ["13:48:27", "Patch UI", "Agent OS surface active", "warn"],
  ["13:51:09", "Visual QA", "Browser pass required", "neutral"],
];

const CHANGED_FILES = [
  ["FluxioReferenceShell.jsx", "+agent OS shell", "ui"],
  ["styles.css", "+visual system", "css"],
  ["FluxioShell.jsx", "runtime data source", "state"],
];

const BUILDER_FLOWS = [
  ["Checkout QA", "Browser test", "needs review", "83%"],
  ["Market research", "Evidence pack", "running", "61%"],
  ["Landing polish", "Preview diff", "ready", "94%"],
  ["Image variants", "Asset studio", "queued", "18%"],
];

const SKILL_CARDS = [
  ["Frontend polish", "Visual QA, responsive checks, no placeholder UI.", "High", "Browser + Code"],
  ["Review bundle", "Diff, tests, screenshots, and approvals in one handoff.", "Medium", "Git + Tests"],
  ["Image direction", "Reference capture, variants, and export-ready assets.", "High", "Images"],
  ["Autonomy guard", "Scoped writes, permission gates, and recovery rules.", "Medium", "Policy"],
];

const IMAGE_VARIANTS = [
  ["Command center", "dark desktop", "approved"],
  ["Browser QA", "checkout test", "review"],
  ["Image studio", "variant board", "draft"],
  ["Builder graph", "flow health", "approved"],
];

const FLUXIO_DATABASES = [
  ["postgres", "Neon Postgres", "Product data", "Connected", "cyan"],
  ["sqlite", "Local SQLite", "Runs and memory", "Ready", "green"],
  ["vector", "Vector Memory", "Context search", "Indexing", "violet"],
  ["blob", "Artifact Store", "Screenshots and exports", "Synced", "amber"],
];

function fluxioAction(handler, fallback) {
  if (typeof handler === "function") {
    handler(fallback);
  }
}

function MetricTile({ label, value, detail, tone = "neutral" }) {
  return (
    <article className={`fluxos-metric tone-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <p>{detail}</p>
    </article>
  );
}

function FluxioComposer({
  draft,
  onAttach,
  onChangeDraft,
  onDictation,
  onSend,
  onSubmit,
  onRequestAction,
  placeholder = "Ask Fluxio to plan, edit, test, or review this project...",
}) {
  const currentDraft = String(draft || "");
  const submit = () => {
    if (typeof onSubmit === "function") {
      onSubmit();
      return;
    }
    if (typeof onSend === "function") {
      onSend();
      return;
    }
    fluxioAction(onRequestAction, "composer:send");
  };

  return (
    <section className="fluxos-composer" aria-label="Fluxio command composer">
      <textarea
        aria-label="Command Fluxio"
        onChange={event => onChangeDraft?.(event.target.value)}
        placeholder={placeholder}
        value={currentDraft}
      />
      <div className="fluxos-composer-bar">
        <div className="fluxos-chip-row">
          {["repo", "screenshot", "terminal", "approval"].map(token => (
            <button key={token} onClick={() => fluxioAction(onRequestAction, `composer:chip:${token}`)} type="button">
              {titleizeToken(token)}
            </button>
          ))}
        </div>
        <div className="fluxos-composer-actions">
          <button aria-label="Attach context" onClick={onAttach} title="Attach context" type="button">
            <Paperclip size={16} strokeWidth={1.9} />
          </button>
          <button aria-label="Start dictation" onClick={onDictation} title="Start dictation" type="button">
            <Mic size={16} strokeWidth={1.9} />
          </button>
          <button className="primary" onClick={submit} type="button">
            <ArrowUp size={17} strokeWidth={2.1} />
            <span>Run</span>
          </button>
        </div>
      </div>
      <div className="fluxos-composer-status" aria-label="Composer readiness">
        <span><i />Agent online</span>
        <span>Ready with workspace context</span>
        <button onClick={() => fluxioAction(onRequestAction, "composer:workspace")} type="button">Workspace: current</button>
      </div>
    </section>
  );
}

function FluxioEvidenceRail({ onRequestAction, runtimeCompartment, routeControls, selectedModelLabel }) {
  const route = routeControls?.selectedRoute || {};
  const host = runtimeCompartment?.host || "local";
  return (
    <aside className="fluxos-evidence-rail" aria-label="Evidence and approvals">
      <section className="fluxos-approval-card">
        <span>Approval waiting</span>
        <strong>Review bundle before merge</strong>
        <p>2 UI files changed. Browser proof and build output are required before publish confidence can be marked ready.</p>
        <div>
          <button onClick={() => fluxioAction(onRequestAction, "approval:review")} type="button">Review</button>
          <button className="primary" onClick={() => fluxioAction(onRequestAction, "approval:approve")} type="button">Approve</button>
        </div>
      </section>

      <section className="fluxos-rail-panel">
        <div className="fluxos-section-head">
          <span>Context health</span>
          <strong>6 of 7 ready</strong>
        </div>
        {["Project files", "Rulesets", "Package scripts", "Image references", "Terminal logs", "Screenshots"].map(item => (
          <div className="fluxos-check-row" key={item}>
            <CircleCheckBig size={15} strokeWidth={1.9} />
            <span>{item}</span>
          </div>
        ))}
      </section>

      <section className="fluxos-rail-panel">
        <div className="fluxos-section-head">
          <span>Route</span>
          <strong>{route.role || "executor"}</strong>
        </div>
        <dl className="fluxos-mini-dl">
          <div><dt>Model</dt><dd>{selectedModelLabel || "GPT route"}</dd></div>
          <div><dt>Host</dt><dd>{host}</dd></div>
          <div><dt>Harness</dt><dd>{route.harness || "Fluxio hybrid"}</dd></div>
        </dl>
      </section>
    </aside>
  );
}

function FluxioHomeSurface(props) {
  const { onSetSurface, onRequestAction, draft, onChangeDraft, onAttach, onDictation, onIdleSubmit } = props;
  const modeCards = [
    ["agent", Bot, "Agent", "Chat with AI to plan, analyze, and build with real-time context.", "Active mode"],
    ["builder", Code2, "Builder", "Create and iterate on full-stack apps, APIs, and deployment flows.", ""],
    ["skills", Sparkles, "Skills", "Use and manage specialized AI skills, rules, and reusable workflows.", ""],
    ["images", Palette, "Images", "Generate, edit, and iterate on images with prompts and references.", ""],
  ];
  const recentSessions = [
    ["User analytics panel", "Updated 2m ago", Bot],
    ["Stripe integration", "Updated 1h ago", Code2],
    ["Email onboarding flow", "Updated 3h ago", Sparkles],
    ["Dashboard redesign", "Updated yesterday", Palette],
  ];
  return (
    <div className="fluxos-home">
      <section className="fluxos-home-lobby">
        <span className="fluxos-hidden-proof">Fluxio control route</span>
        <div className="fluxos-home-title">
          <h1>What will we build today?</h1>
          <p>Choose a mode to start or ask Fluxio anything.</p>
        </div>

        <div className="fluxos-mode-cards" aria-label="Start modes">
          {modeCards.map(([id, Icon, label, copy, badge]) => (
            <button className={id === "agent" ? "active" : ""} key={id} onClick={() => onSetSurface?.(id)} type="button">
              <span className="fluxos-mode-icon"><Icon size={34} strokeWidth={1.55} /></span>
              <strong>{label}</strong>
              <p>{copy}</p>
              {badge ? <em>{badge}</em> : <i aria-hidden="true"><ArrowRight size={18} strokeWidth={1.7} /></i>}
            </button>
          ))}
        </div>

        <section className="fluxos-recent-row" aria-label="Recent sessions">
          <div className="fluxos-recent-head">
            <strong>Recent sessions</strong>
            <button onClick={() => fluxioAction(onRequestAction, "home:view-all-sessions")} type="button">
              View all
              <ArrowRight size={15} strokeWidth={1.7} />
            </button>
          </div>
          <div className="fluxos-recent-grid">
            {recentSessions.map(([title, time, Icon]) => (
              <button key={title} onClick={() => fluxioAction(onRequestAction, `home:session:${title}`)} type="button">
                <Icon size={18} strokeWidth={1.7} />
                <span>
                  <strong>{title}</strong>
                  <small>{time}</small>
                </span>
              </button>
            ))}
          </div>
        </section>

        <FluxioComposer
          draft={draft}
          onAttach={onAttach}
          onChangeDraft={onChangeDraft}
          onDictation={onDictation}
          onRequestAction={onRequestAction}
          onSubmit={onIdleSubmit}
          placeholder="Ask Fluxio to build, analyze, or orchestrate anything..."
        />
      </section>
    </div>
  );
}

function FluxioAgentSurface(props) {
  const {
    draft,
    messages,
    onAttach,
    onChangeDraft,
    onDictation,
    onRequestAction,
    onRuntimeChange,
    onSend,
    runtimeCompartment,
    routeControls,
    selectedModelLabel,
    selectedRuntimeLabel,
    timelineMoments,
  } = props;
  const visibleMessages = asList(messages).slice(-4);
  const visibleTimeline = asList(timelineMoments).slice(0, 4);
  return (
    <div className="fluxos-agent-grid">
      <section className="fluxos-agent-main">
        <div className="fluxos-section-head">
          <span>Active run</span>
          <strong>Reproduce Fluxio UI and prepare merge</strong>
        </div>
        <div className="fluxos-plan-list">
          {AGENT_PLAN.map(([label, copy, status]) => (
            <article className={`fluxos-plan-step status-${status}`} key={label}>
              <span>{status === "done" ? <Check size={16} strokeWidth={2} /> : status === "running" ? <CircleDashed size={16} strokeWidth={2} /> : <Clock3 size={16} strokeWidth={2} />}</span>
              <div>
                <strong>{label}</strong>
                <p>{copy}</p>
              </div>
            </article>
          ))}
        </div>

        <section className="fluxos-thread">
          {(visibleMessages.length ? visibleMessages : [
            { id: "u", role: "user", title: "Goal", detail: "Build Fluxio as a usable agent command center." },
            { id: "a", role: "assistant", title: "Fluxio", detail: "I will keep plan, changes, preview, and approvals visible while I work." },
          ]).map((message, index) => {
            const messageDetail = message.detail || message.content || message.message || "";
            return (
              <article className={`fluxos-message role-${message.role || "assistant"}`} key={message.id || index}>
                <strong>{message.title || titleizeToken(message.role || "agent")}</strong>
                {messageDetail ? <p>{messageDetail}</p> : null}
              </article>
            );
          })}
        </section>

        <FluxioComposer
          draft={draft}
          onAttach={onAttach}
          onChangeDraft={onChangeDraft}
          onDictation={onDictation}
          onRequestAction={onRequestAction}
          onSend={onSend}
          placeholder="Continue the run, ask for a review, or request a browser check..."
        />
      </section>

      <section className="fluxos-preview-panel">
        <div className="fluxos-browser-chrome">
          <span />
          <strong>/control?surface=agent</strong>
          <button onClick={() => fluxioAction(onRequestAction, "preview:refresh")} type="button">
            <RefreshCw size={15} strokeWidth={1.9} />
          </button>
        </div>
        <div className="fluxos-live-preview" aria-label="Live preview">
          <div className="fluxos-preview-card wide" />
          <div className="fluxos-preview-card active" />
          <div className="fluxos-preview-card narrow" />
          <div className="fluxos-selector one">Hero</div>
          <div className="fluxos-selector two">CTA passes</div>
        </div>
        <div className="fluxos-tool-grid">
          {(visibleTimeline.length ? visibleTimeline : TOOL_EVENTS).map((item, index) => {
            const tuple = Array.isArray(item) ? item : [item.time || item.timestamp || "now", item.title || item.kind, item.detail || item.message, item.tone || "neutral"];
            return (
              <article className={`fluxos-tool-event tone-${tuple[3] || "neutral"}`} key={`${tuple[0]}-${index}`}>
                <span>{tuple[0]}</span>
                <strong>{tuple[1]}</strong>
                <p>{tuple[2]}</p>
              </article>
            );
          })}
        </div>
        <div className="fluxos-runtime-strip">
          <button onClick={() => onRuntimeChange?.("openclaw")} type="button">{selectedRuntimeLabel || "OpenClaw"}</button>
          <button onClick={() => fluxioAction(onRequestAction, "agent:open-terminal")} type="button">Terminal</button>
          <button onClick={() => fluxioAction(onRequestAction, "agent:open-browser")} type="button">Browser</button>
        </div>
      </section>

      <FluxioEvidenceRail
        onRequestAction={onRequestAction}
        routeControls={routeControls}
        runtimeCompartment={runtimeCompartment}
        selectedModelLabel={selectedModelLabel}
      />
    </div>
  );
}

function FluxioBuilderSurface(props) {
  const { builderRows, changedItems, onOpenBuilderDetail, onRequestAction, onSelectFlow, onSelectProject, timelineMoments } = props;
  const rows = asList(builderRows).length ? asList(builderRows).slice(0, 4) : BUILDER_FLOWS;
  const changes = asList(changedItems).length ? asList(changedItems).slice(0, 5) : CHANGED_FILES;
  return (
    <div className="fluxos-builder">
      <section className="fluxos-builder-main">
        <div className="fluxos-section-head">
          <span>Builder overview</span>
          <strong>Project readiness</strong>
        </div>
        <div className="fluxos-status-grid">
          <MetricTile detail="Typecheck and browser smoke pending" label="Publish confidence" tone="warn" value="82%" />
          <MetricTile detail="Active flows connected to review cards" label="Flows" tone="good" value={String(rows.length)} />
          <MetricTile detail="One approval blocks merge" label="Review" tone="warn" value="Open" />
        </div>
        <section className="fluxos-flow-board">
          {rows.map((row, index) => {
            const tuple = Array.isArray(row)
              ? row
              : [row.title || row.name || "Workspace flow", row.kind || row.status || "run", row.status || "active", row.progress || `${70 + index * 3}%`];
            return (
              <button className="fluxos-flow-card" key={`${tuple[0]}-${index}`} onClick={() => onSelectFlow?.(row?.id || tuple[0])} type="button">
                <span>{tuple[1]}</span>
                <strong>{tuple[0]}</strong>
                <p>{tuple[2]}</p>
                <div><i style={{ width: tuple[3] }} /></div>
              </button>
            );
          })}
        </section>
      </section>

      <section className="fluxos-pipeline">
        <div className="fluxos-section-head">
          <span>Execution pipeline</span>
          <strong>Preview to merge</strong>
        </div>
        {["Plan accepted", "Files changed", "Visual review", "Tests", "Approval", "Merge"].map((step, index) => (
          <button className={index < 3 ? "complete" : index === 3 ? "active" : ""} key={step} onClick={() => fluxioAction(onRequestAction, `builder:pipeline:${step}`)} type="button">
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{step}</strong>
          </button>
        ))}
      </section>

      <section className="fluxos-review-bundle">
        <div className="fluxos-section-head">
          <span>Review bundle</span>
          <strong>Changes ready for inspection</strong>
        </div>
        {changes.map((item, index) => {
          const tuple = Array.isArray(item)
            ? item
            : [item.path || item.file || "changed-file", item.summary || item.status || "changed", item.kind || "file"];
          return (
            <article key={`${tuple[0]}-${index}`}>
              <Code2 size={16} strokeWidth={1.8} />
              <div>
                <strong>{tuple[0]}</strong>
                <p>{tuple[1]}</p>
              </div>
              <span>{tuple[2]}</span>
            </article>
          );
        })}
        <div className="fluxos-review-actions">
          <button onClick={onOpenBuilderDetail} type="button">Open details</button>
          <button className="primary" onClick={() => onSelectProject?.("current")} type="button">Publish check</button>
        </div>
      </section>
    </div>
  );
}

function FluxioSkillsSurface({ onRequestAction, studioState, surface }) {
  const ruleSets = asList(studioState?.ruleSets).slice(0, 4);
  const isRuleSets = surface === "rule-sets";
  return (
    <div className="fluxos-skills">
      <section className="fluxos-skills-list">
        <div className="fluxos-section-head">
          <span>{isRuleSets ? "Rule Sets" : "Skill library"}</span>
          <strong>{isRuleSets ? "Core policy and Approval gates" : "Reusable agent capabilities"}</strong>
        </div>
        {SKILL_CARDS.map(([title, copy, effort, harness]) => (
          <button className="fluxos-skill-card" key={title} onClick={() => fluxioAction(onRequestAction, `skill:open:${title}`)} type="button">
            <WandSparkles size={20} strokeWidth={1.7} />
            <div>
              <strong>{title}</strong>
              <p>{copy}</p>
            </div>
            <span>{effort}</span>
            <em>{harness}</em>
          </button>
        ))}
      </section>
      <section className="fluxos-editor">
        <div className="fluxos-section-head">
          <span>Ruleset editor</span>
          <strong>{ruleSets[0]?.name || "Frontend merge policy"}</strong>
        </div>
        <div className="fluxos-code-window">
          <pre>{`name: Core policy
policy: frontend-polish
autonomy: workspace_safe
required:
  - inspect_reference_images
  - no_unwired_buttons
  - browser_visual_check
  - npm_run_frontend_build
Approval:
  merge: required
  destructive_actions: always_ask`}</pre>
        </div>
        <div className="fluxos-permission-grid">
          {["Files", "Terminal", "Browser", "Network"].map(item => (
            <button key={item} onClick={() => fluxioAction(onRequestAction, `skill:permission:${item}`)} type="button">
              <Shield size={16} strokeWidth={1.8} />
              <span>{item}</span>
              <strong>Allowed</strong>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

const FLUXIO_REAL_IMAGE_SESSIONS_KEY = "fluxio.images.real_sessions";

function loadFluxioRealImageSessions() {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(FLUXIO_REAL_IMAGE_SESSIONS_KEY) || "[]");
    return Array.isArray(parsed) ? parsed.filter(item => item?.requestId && item?.previewUrl).slice(0, 12) : [];
  } catch {
    return [];
  }
}

function FluxioImagesSurface({ callBackend, onRequestAction }) {
  const [prompt, setPrompt] = useState("Create a calm Fluxio agent command center with live preview, evidence rail, and approval state.");
  const [sessions, setSessions] = useState(loadFluxioRealImageSessions);
  const [status, setStatus] = useState({ state: "idle", message: "" });
  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(FLUXIO_REAL_IMAGE_SESSIONS_KEY, JSON.stringify(sessions.slice(0, 12)));
  }, [sessions]);

  const generateImage = async () => {
    const text = prompt.trim();
    if (!text) {
      setStatus({ state: "blocked", message: "Write an image prompt first." });
      return;
    }
    if (typeof callBackend !== "function") {
      setStatus({ state: "blocked", message: "Live backend bridge is unavailable." });
      return;
    }
    const requestId = `imgreq-ui-${Date.now().toString(36)}`;
    setStatus({ state: "running", message: "Generating through Codex GPT-Image..." });
    try {
      const result = await callBackend("image_playground_operation_command", {
        requestId,
        operation: "generate",
        providerId: "codex_subscription_gpt_image2",
        size: "1024x1024",
        canvas: { width: 1024, height: 1024 },
        prompt: { text },
      });
      if (!result?.previewUrl || result?.providerStatus !== "available") {
        throw new Error(result?.message || "Image provider did not return a generated artifact.");
      }
      const session = {
        requestId: result.requestId || requestId,
        prompt: text,
        previewUrl: result.previewUrl,
        manifestUrl: result.manifestUrl || "",
        manifestPath: result.manifestPath || "",
        outputArtifactPath: result.outputArtifactPath || result.imagePath || "",
        provider: result.provider || "openai-codex",
        model: result.model || "gpt-image-2",
        createdAt: new Date().toISOString(),
        receipt: result.receipt || {},
      };
      setSessions(current => [session, ...current.filter(item => item.requestId !== session.requestId)].slice(0, 12));
      setStatus({ state: "ready", message: "Minted real Codex image session with artifact proof." });
    } catch (error) {
      setStatus({ state: "blocked", message: String(error?.message || error || "Image generation failed.") });
    }
  };

  return (
    <div className="fluxos-images">
      <section className="fluxos-image-prompt">
        <div className="fluxos-section-head">
          <span>Image studio</span>
          <strong>Codex GPT-Image sessions</strong>
        </div>
        <textarea aria-label="Image prompt" onChange={event => setPrompt(event.target.value)} value={prompt} />
        <div className="fluxos-review-actions">
          <button onClick={() => fluxioAction(onRequestAction, "images:add-reference")} type="button">Add reference</button>
          <button className="primary" disabled={status.state === "running"} onClick={() => void generateImage()} type="button">
            {status.state === "running" ? "Generating..." : "Generate"}
          </button>
        </div>
        {status.message ? <p className={`fluxos-image-status state-${status.state}`}>{status.message}</p> : null}
        <div className="fluxos-reference-strip">
          <span>Provider openai-codex</span>
          <span>Model gpt-image-2</span>
          <span>{sessions.length} minted session{sessions.length === 1 ? "" : "s"}</span>
        </div>
      </section>
      <section className="fluxos-variant-grid">
        {sessions.length ? sessions.map((session, index) => (
          <button className="fluxos-variant-card minted" key={session.requestId} onClick={() => fluxioAction(onRequestAction, `images:variant:${session.requestId}`)} type="button">
            <img alt={`Generated Fluxio session ${index + 1}`} src={resolveReferenceArtifactUrl(session.previewUrl)} />
            <strong>{session.prompt.slice(0, 42) || "Generated image"}</strong>
            <span>{session.provider} · {session.model}</span>
            <em>{new Date(session.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</em>
          </button>
        )) : (
          <article className="fluxos-empty-minted-session">
            <strong>No minted image sessions yet</strong>
            <p>Generate through the Codex GPT-Image lane to create a real artifact-backed session.</p>
          </article>
        )}
      </section>
      <section className="fluxos-image-inspector">
        <div className="fluxos-section-head">
          <span>Inspector</span>
          <strong>{sessions[0]?.requestId || "Awaiting artifact"}</strong>
        </div>
        <p>
          {sessions[0]
            ? `${sessions[0].provider} / ${sessions[0].model} wrote ${sessions[0].outputArtifactPath || "a served artifact"}.`
            : "Generated sessions keep prompt, provider proof, manifest, preview URL, and export target together."}
        </p>
        <button onClick={() => fluxioAction(onRequestAction, "images:send-to-builder")} type="button">Attach to review bundle</button>
        <button disabled={!sessions[0]?.previewUrl} onClick={() => callBackend?.("image.export", { prompt, session: sessions[0] })} type="button">Export asset</button>
      </section>
    </div>
  );
}

function FluxioWorkbenchSurface({ onRequestAction, workbenchState }) {
  return (
    <div className="fluxos-workbench">
      <section className="fluxos-browser-pane">
        <div className="fluxos-browser-chrome">
          <span />
          <strong>localhost preview</strong>
          <button onClick={() => fluxioAction(onRequestAction, "workbench:screenshot")} type="button">Screenshot</button>
        </div>
        <div className="fluxos-live-preview workbench">
          <div className="fluxos-preview-card wide" />
          <div className="fluxos-preview-card active" />
          <div className="fluxos-selector one">Click target</div>
          <div className="fluxos-selector two">Diff region</div>
        </div>
      </section>
      <section className="fluxos-action-timeline">
        <div className="fluxos-section-head">
          <span>Runtime operations</span>
          <strong>OpenClaw and Hermes browser action timeline</strong>
        </div>
        <p className="fluxos-proof-line">Runtime operations keep OpenClaw, Hermes, browser actions, screenshots, and replay evidence in one place.</p>
        {["Open browser", "Navigate to /control", "Click Builder", "Capture screenshot", "Compare visual state"].map((step, index) => (
          <article key={step}>
            <span>{`10:${24 + index}:${String(12 + index * 3).padStart(2, "0")}`}</span>
            <strong>{step}</strong>
            <p>{index < 3 ? "passed" : "awaiting verification"}</p>
          </article>
        ))}
      </section>
      <section className="fluxos-rail-panel">
        <div className="fluxos-section-head">
          <span>Live state</span>
          <strong>{workbenchState?.status || "Ready"}</strong>
        </div>
        <p>Browser, preview, screenshots, selectors, and replay markers stay attached to the current run.</p>
      </section>
    </div>
  );
}

function FluxioSettingsSurface({ activeTheme, onRequestAction, onSelectTheme, settingsState, themes = FLUXIO_THEMES }) {
  return (
    <div className="fluxos-settings">
      <section className="fluxos-theme-lab">
        <div className="fluxos-section-head">
          <span>Theme engine</span>
          <strong>One layout, multiple operating moods</strong>
        </div>
        <div className="fluxos-theme-grid" aria-label="Theme preview cards">
          {themes.map(theme => (
            <button
              aria-pressed={activeTheme === theme.id}
              className={activeTheme === theme.id ? "active" : ""}
              data-preview-theme={theme.id}
              key={theme.id}
              onClick={() => onSelectTheme?.(theme.id)}
              type="button"
            >
              <span className="fluxos-theme-preview" aria-hidden="true">
                <i />
                <b />
                <em />
              </span>
              <strong>{theme.label}</strong>
              <small>Best for {theme.bestFor}</small>
              <span>Density: {theme.density}</span>
              <span>Motion: {theme.motion}</span>
              <span>Contrast: {theme.contrast}</span>
            </button>
          ))}
        </div>
      </section>
      <section className="fluxos-database-lab">
        <div className="fluxos-section-head">
          <span>Databases</span>
          <strong>Colorful data layer for runs, memory, and artifacts</strong>
        </div>
        <div className="fluxos-database-grid" aria-label="Fluxio databases">
          {FLUXIO_DATABASES.map(([id, label, copy, status, tone]) => (
            <button
              className={`tone-${tone}`}
              key={id}
              onClick={() => fluxioAction(onRequestAction, `database:open:${id}`)}
              type="button"
            >
              <span className="fluxos-database-orb">
                <Database size={24} strokeWidth={1.75} />
              </span>
              <strong>{label}</strong>
              <small>{copy}</small>
              <em>{status}</em>
            </button>
          ))}
        </div>
      </section>
      {[
        ["Models", "Provider accounts, model routes, reasoning level, and fallbacks."],
        ["Rules & Routing", "Approval policy, write scope, destructive action handling."],
        ["Workspace", "Local path, NAS bridge, runtime compartment, and file watching."],
        ["Appearance", "Density, contrast, reduced motion, and command palette."],
      ].map(([title, copy]) => (
        <section className="fluxos-settings-card" key={title}>
          <div className="fluxos-section-head">
            <span>{title}</span>
            <strong>{settingsState?.activeTab === title.toLowerCase() ? "Active" : "Configured"}</strong>
          </div>
          <p>{copy}</p>
          <button onClick={() => fluxioAction(onRequestAction, `settings:${title.toLowerCase()}`)} type="button">Open {title}</button>
        </section>
      ))}
    </div>
  );
}

function FluxioSurfaceContent(props) {
  if (props.surface === "home") return <FluxioHomeSurface {...props} />;
  if (props.surface === "builder") return <FluxioBuilderSurface {...props} />;
  if (props.surface === "skills" || props.surface === "rule-sets") return <FluxioSkillsSurface {...props} />;
  if (props.surface === "images") return <FluxioImagesSurface {...props} />;
  if (props.surface === "workbench") return <FluxioWorkbenchSurface {...props} />;
  if (props.surface === "settings") return <FluxioSettingsSurface {...props} />;
  return <FluxioAgentSurface {...props} />;
}

function FluxioAgentOS(props) {
  const {
    appearance,
    appearanceStyle,
    currentProjectLabel,
    onHistory,
    onMore,
    onRequestAction,
    onSetAgentScene,
    onSetSurface,
    routeControls,
    selectedEffortLabel,
    selectedHarnessMeta,
    selectedModelLabel,
    surface = "agent",
  } = props;
  const route = routeControls?.selectedRoute || {};
  const modelLabel = selectedModelLabel || route.model || "GPT route";
  const harnessLabel = selectedHarnessMeta?.label || route.harness || "Fluxio hybrid";
  const [activeTheme, setActiveTheme] = useState(() => {
    if (typeof window === "undefined") return "noir";
    const stored = window.localStorage?.getItem(FLUXIO_THEME_STORAGE_KEY);
    return FLUXIO_THEMES.some(theme => theme.id === stored) ? stored : "noir";
  });
  const activeThemeMeta = FLUXIO_THEMES.find(theme => theme.id === activeTheme) || FLUXIO_THEMES[0];

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage?.setItem(FLUXIO_THEME_STORAGE_KEY, activeTheme);
    }
  }, [activeTheme]);

  const cycleTheme = () => {
    const currentIndex = FLUXIO_THEMES.findIndex(theme => theme.id === activeTheme);
    const nextTheme = FLUXIO_THEMES[(currentIndex + 1) % FLUXIO_THEMES.length] || FLUXIO_THEMES[0];
    setActiveTheme(nextTheme.id);
  };

  return (
    <div
      className={`fluxos-shell surface-${surface}`}
      data-density={appearance?.density || "comfortable"}
      data-theme={activeTheme}
      data-look={appearance?.stylePreset || "agent-os"}
      style={appearanceStyle}
    >
      <aside className="fluxos-left-rail">
        <div className="fluxos-window-dots" aria-hidden="true"><span /><span /><span /></div>
        <button className="fluxos-brand" onClick={() => onSetSurface?.("home")} type="button">
          <span>F</span>
          <strong>Fluxio</strong>
        </button>
        <nav aria-label="Fluxio surfaces">
          {FLUXIO_NAV_ITEMS.map(({ id, label, Icon }) => (
            <button
              aria-current={surface === id ? "page" : undefined}
              className={surface === id ? "active" : ""}
              key={id}
              onClick={() => onSetSurface?.(id)}
              title={label}
              type="button"
            >
              <Icon size={18} strokeWidth={1.8} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <section className="fluxos-recent-sidebar" aria-label="Recent sessions">
          <span>Recent sessions</span>
          <button onClick={() => onSetSurface?.("builder")} type="button">User analytics panel<small>2m ago</small></button>
          <button onClick={() => onSetSurface?.("builder")} type="button">Stripe integration<small>1h ago</small></button>
          <button onClick={() => onSetSurface?.("builder")} type="button">Dashboard redesign<small>Yesterday</small></button>
        </section>
        <div className="fluxos-rail-footer">
          <span className="fluxos-status-dot" />
          <strong>Local</strong>
          <small>worktree clean check pending</small>
        </div>
      </aside>

      <main className="fluxos-main">
        <header className="fluxos-top-strip">
          <div className="fluxos-project-switcher">
            <span>Workspace</span>
            <strong>{currentProjectLabel || "Fluxio control"}</strong>
          </div>
          <div className="fluxos-run-config" aria-label="Execution configuration">
            <button onClick={() => fluxioAction(onRequestAction, "config:provider")} type="button">OpenAI</button>
            <button onClick={() => fluxioAction(onRequestAction, "config:model")} type="button">{modelLabel}</button>
            <button onClick={() => fluxioAction(onRequestAction, "config:effort")} type="button">{selectedEffortLabel || "High"}</button>
            <button onClick={() => fluxioAction(onRequestAction, "config:harness")} type="button">{harnessLabel}</button>
            <button onClick={() => fluxioAction(onRequestAction, "config:autonomy")} type="button">Auto scoped</button>
            <button className="fluxos-theme-cycle" onClick={cycleTheme} type="button">{activeThemeMeta.label}</button>
          </div>
          <div className="fluxos-top-actions">
            <button onClick={onHistory} type="button">History</button>
            <button onClick={() => onSetAgentScene?.("live")} type="button">Preview</button>
            <button className="primary" onClick={onMore} type="button">Command</button>
          </div>
        </header>

        <FluxioSurfaceContent
          {...props}
          activeTheme={activeTheme}
          onSelectTheme={setActiveTheme}
          themes={FLUXIO_THEMES}
        />
      </main>
    </div>
  );
}

export function FluxioReferenceShell(props) {
  return <FluxioAgentOS {...props} />;
}
