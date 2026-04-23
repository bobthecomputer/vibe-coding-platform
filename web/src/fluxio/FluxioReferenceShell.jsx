import { useMemo, useState } from "react";
import {
  ArrowLeft,
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

function cx(...values) {
  return values.filter(Boolean).join(" ");
}

function asList(value) {
  return Array.isArray(value) ? value : [];
}

function uniq(values) {
  return Array.from(new Set(asList(values).filter(Boolean)));
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
    title: "Agent Mode",
    copy: "Chat with your agents using Fluxio and Hermes.",
    tone: "violet",
    icon: Bot,
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
    title: "Skill Hub",
    copy: "Manage skills, environments, rules, and shared knowledge.",
    tone: "blue",
    icon: Grid2x2,
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
  currentModeLabel = "Agent Mode",
  favoriteFlows = [],
  flowProjects = [],
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

      <button className="reference-search-shell" type="button">
        <Search size={16} strokeWidth={1.9} />
        <span>Search conversations...</span>
        <Edit3 size={15} strokeWidth={1.9} />
      </button>

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
          <button className="reference-mini-icon" type="button">
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
                  {project.hasMore ? <button className="reference-show-more" type="button">Show all</button> : null}
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

function HomeSurface({ onOpenSurface }) {
  return (
    <section className="reference-home-surface">
      <div className="reference-home-header">
        <div>
          <h1>Agent Workspace</h1>
          <p>Build. Orchestrate. Ship.</p>
        </div>
        <IconButton icon={CircleHelp} label="Help" onClick={() => {}} />
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

function SlashCommandPanel({ commands = [], draft = "", onUseCommand }) {
  const query = String(draft || "").trim().toLowerCase();
  const filteredCommands = query.startsWith("/")
    ? commands.filter(item => {
        const haystack = `${item.command} ${item.label || ""} ${item.detail || ""} ${item.harness || ""}`.toLowerCase();
        return haystack.includes(query);
      })
    : commands;
  const visibleCommands = filteredCommands.slice(0, 8);

  return (
    <article className="reference-support-panel">
      <div className="reference-builder-section-head">
        <div>
          <strong>Harness Commands</strong>
          <span>
            {query.startsWith("/")
              ? "Filtered by the composer. Clicking inserts the command."
              : "Built from the active harness surfaces and local installed skills."}
          </span>
        </div>
      </div>
      {visibleCommands.length > 0 ? (
        <div className="reference-command-grid">
          {visibleCommands.map(item => (
            <button
              className="reference-command-card"
              key={`${item.harness}-${item.command}`}
              onClick={() => onUseCommand(item.command)}
              type="button"
            >
              <div className="reference-command-head">
                <strong>{item.command}</strong>
                <span>{item.harness}</span>
              </div>
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
    slashCommands = [],
    onAttach,
    onChangeDraft,
    onDictation,
    onIdleSubmit,
    onPaste,
    onRuntimeChange,
  } = props;

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
      />

      <div className="reference-config-grid">
        <ConfigCard
          accent="neutral"
          copy="Routing Strategy Balanced"
          title="Harness"
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
          <div className="reference-card-metric-stack">
            <MetricLine label="Cost Priority" value="Medium" />
            <MetricLine label="Latency Priority" value="Medium" />
          </div>
        </ConfigCard>

        <ConfigCard
          accent="neutral"
          copy="Temperature 0.6"
          title="Model"
          titleIcon={Bot}
        >
          <div className="reference-pill-select">{selectedModelLabel}</div>
          <div className="reference-card-metric-stack">
            <MetricLine label="Max Tokens" value="4096" />
          </div>
        </ConfigCard>

        <ConfigCard
          accent="neutral"
          copy="Balances speed and depth. Good for most tasks."
          title="Effort"
          titleIcon={Sparkles}
        >
          <div className="reference-pill-select">{selectedEffortLabel}</div>
        </ConfigCard>

        <ConfigCard
          accent="neutral"
          copy="2 active rules"
          title="Rules"
          titleIcon={BookOpen}
          footer={<button className="reference-link-button" type="button">Advanced settings</button>}
        >
          <div className="reference-pill-select">Project Rules</div>
        </ConfigCard>
      </div>

      <div className="reference-agent-support-grid">
        <article className="reference-support-panel">
          <div className="reference-builder-section-head">
            <div>
              <strong>{runtimeStatus?.label || "Selected runtime"}</strong>
              <span>
                {runtimeStatus?.doctor_summary ||
                  runtimeStatus?.doctorSummary ||
                  "Runtime readiness appears here once the backend reports it."}
              </span>
            </div>
            <StatusBadge
              label={runtimeStatus?.detected ? "Ready" : "Not detected"}
              tone={runtimeStatus?.detected ? "completed" : "paused"}
            />
          </div>
          <RuntimeCapabilityPills capabilities={asList(runtimeStatus?.capabilities)} />
        </article>

        <SlashCommandPanel commands={slashCommands} draft={draft} onUseCommand={onUseSlashCommand} />
      </div>

      <div className="reference-idle-footer">
        <button className="reference-reset-button" type="button">
          <RefreshCw size={16} strokeWidth={1.9} />
          <span>Reset to defaults</span>
        </button>
        <p>Fluxio can make mistakes. Please verify important information.</p>
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
    draft,
    feedbackItems = [],
    missionLoop,
    messages = [],
    onUseSlashCommand,
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
    onRuntimeChange,
    onSend,
  } = props;
  const [detailTab, setDetailTab] = useState("feedback");
  const processMoments = timelineMoments.slice(-4);
  const renderedMessages = messages.length > 0 ? messages : [];

  return (
    <section className="reference-agent-run">
      {missionLoop ? (
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
            <span>Runtime lane</span>
            <strong>{missionLoop.currentRuntimeLane || "Primary thread"}</strong>
          </div>
        </article>
      ) : null}

      <div className="reference-chat-column">
        {renderedMessages.map(item =>
          item.role === "user" ? (
            <div className="reference-user-bubble" key={item.id}>
              <p>{item.title}</p>
              <span>{item.meta || "Now"}</span>
            </div>
          ) : (
            <div className="reference-agent-thread" key={item.id}>
              <div className="reference-agent-avatar">
                <div className="reference-brand-mark tiny">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
              <div className="reference-agent-thread-body">
                <p className="reference-thread-lead">{item.title}</p>
                {item.detail ? (
                  <article className="reference-report-panel compact">
                    <p>{item.detail}</p>
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
                        <button type="button">Copy</button>
                        <button type="button">Comment</button>
                        <button type="button">Retry</button>
                      </div>
                      <span>{item.meta || "Now"}</span>
                    </div>
                  </article>
                ) : null}
              </div>
            </div>
          ),
        )}

        {processMoments.length > 0 ? (
          <article className="reference-status-panel">
            <h3>Live mission activity</h3>
            <div className="reference-status-list">
              {processMoments.map((moment, index) => (
                <StepState
                  done={index < processMoments.length - 1}
                  key={moment.id}
                  label={moment.title}
                  pending={index === processMoments.length - 1}
                />
              ))}
            </div>
          </article>
        ) : null}

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
                      <button type="button">Change applied</button>
                      <button type="button">View change</button>
                    </div>
                  ) : null}
                </article>
              ))}
          </div>
        </article>
      </div>

      <ComposerDock
        compact
        draft={draft}
        onAttach={onAttach}
        onChangeDraft={onChangeDraft}
        onDictation={onDictation}
        onPaste={onPaste}
        onSubmit={onSend}
        placeholder="Ask anything..."
      >
        <div className="reference-docked-controls">
          <label className="reference-inline-select">
            <span>Harness</span>
            <select onChange={event => onRuntimeChange(event.target.value)} value={selectedRuntime}>
              <option value={selectedRuntime}>{selectedRuntimeLabel}</option>
            </select>
          </label>
          <label className="reference-inline-select">
            <span>Model</span>
            <select value={selectedModelLabel}>
              <option>{selectedModelLabel}</option>
            </select>
          </label>
          <label className="reference-inline-select">
            <span>Effort</span>
            <select value={selectedEffortLabel}>
              <option>{selectedEffortLabel}</option>
            </select>
          </label>
          <label className="reference-inline-select">
            <span>Rules</span>
            <select value="Project Rules">
              <option>Project Rules</option>
            </select>
          </label>
        </div>

        {String(draft || "").trim().startsWith("/") ? (
          <SlashCommandPanel commands={slashCommands} draft={draft} onUseCommand={onUseSlashCommand} />
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
    messages = [],
    onAttach,
    onChangeDraft,
    onDictation,
    onPaste,
    onSend,
    projectLabel,
    timelineMoments = [],
  } = props;
  const assistantMoments = timelineMoments.slice(-3);
  const latestUserMessage = [...messages].reverse().find(item => item.role === "user");
  const latestAssistantMessage = [...messages].reverse().find(item => item.role === "assistant");

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
                <strong>Fluxio Agent</strong>
                <span>Working</span>
              </div>
            </div>
          </div>
          <p>
            {latestAssistantMessage?.title ||
              "I&apos;m updating the current UI and syncing the latest visible changes into the live preview."}
          </p>
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
                <strong>Fluxio Agent</strong>
                <span>Thinking</span>
              </div>
            </div>
            <p>{latestAssistantMessage.detail}</p>
          </article>
        ) : null}

        <article className="reference-live-card">
          <div className="reference-live-agent">
            <div className="reference-brand-mark tiny">
              <span />
              <span />
              <span />
            </div>
            <div>
              <strong>Fluxio Agent</strong>
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
        />
      </div>

      <div className="reference-preview-stage">
        <div className="reference-preview-toolbar">
          <div className="reference-preview-tabs">
            <button className="active" type="button">Preview</button>
            <button type="button">Files</button>
            <button type="button">Terminal</button>
          </div>
          <div className="reference-preview-actions">
            <div className="reference-device-toggle">
              <button className="active" type="button"><Monitor size={16} strokeWidth={1.9} /></button>
              <button type="button"><Laptop size={16} strokeWidth={1.9} /></button>
              <button type="button"><Smartphone size={16} strokeWidth={1.9} /></button>
            </div>
            <IconButton icon={RefreshCw} label="Refresh preview" onClick={() => {}} />
            <IconButton icon={Expand} label="Expand preview" onClick={() => {}} />
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
              <button className="reference-browser-cta" type="button">Get Started</button>
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
                <button className="primary" type="button">Start Building</button>
                <button className="secondary" type="button">View Demo</button>
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
                <button type="button">😊</button>
                <button className="send" type="button">Send</button>
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
    onSelectFlow,
    onSelectProject,
    projectLabel,
    ruleSets = [],
    activeRuleSetId = "",
    onOpenSkillStudio,
    selectedProjectId,
    timelineMoments = [],
  } = props;
  const selectedRow = builderRows.find(item => item.selected) || builderRows[0] || null;
  const activeProject =
    flowProjects.find(item => item.id === selectedProjectId) || flowProjects[0] || null;
  const builderHighlights = [
    ["Success rate", `${selectedRow?.successRate ?? 0}%`],
    ["Runs", `${selectedRow?.runs ?? 0}`],
    ["Turning point", selectedRow?.turningPoint || "—"],
    ["Last update", selectedRow?.updated || selectedRow?.lastRunMeta || "—"],
  ];
  const builderMetrics = buildBuilderMetrics(builderRows);

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
            <button type="button">Overview</button>
            <button className="active" type="button">Flows</button>
            <button type="button">Files</button>
            <button type="button">Settings</button>
          </div>
          <label className="reference-search-field">
            <Search size={18} strokeWidth={1.9} />
            <input placeholder="Search flows..." />
          </label>
          <div className="reference-flow-detail-list">
            {flowProjects.map(project => (
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
                <span>Runtime lane</span>
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
            <button className="reference-topbar-pill active" type="button">
              <Monitor size={16} strokeWidth={1.9} />
              <span>Live Preview</span>
            </button>
            <button className="reference-outline-button" type="button">
              <Hammer size={16} strokeWidth={1.9} />
              <span>Open in Builder</span>
            </button>
            <IconButton icon={MoreHorizontal} label="More" onClick={() => {}} />
          </div>
          <article className="reference-builder-preview-panel">
            <div className="reference-detail-tabs compact">
              <button className="active" type="button">Preview</button>
              <button type="button">Files</button>
              <button type="button">Changes ({changedItems.length})</button>
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
                <button className="primary" type="button">Primary Action</button>
                <button className="secondary" type="button">Secondary</button>
              </div>
            </div>
          </article>
          <article className="reference-feedback-panel builder">
            <div className="reference-feedback-tabs">
              <button className="active" type="button">Feedback</button>
              <button type="button">Notes</button>
            </div>
            <div className="reference-feedback-list">
              {feedbackItems.slice(0, 3).map(item => (
                <article className="reference-feedback-item" key={item.id}>
                  <div className="reference-feedback-meta">
                    <strong>{item.author}</strong>
                    <span>{item.meta}</span>
                  </div>
                  <p>{item.body}</p>
                  {item.role === "assistant" ? (
                    <div className="reference-feedback-actions">
                      <button type="button">Change applied</button>
                      <button type="button">View change</button>
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
          <button className="reference-outline-button strong" type="button">
            <Plus size={18} strokeWidth={1.9} />
            <span>New Project</span>
          </button>
          <IconButton icon={LayoutGrid} label="Grid view" onClick={() => {}} />
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
            <input placeholder="Search projects..." />
          </label>
          <button className="reference-select-button" type="button">
            <span>Status</span>
            <ChevronDown size={16} strokeWidth={1.9} />
          </button>
          <button className="reference-select-button" type="button">
            <span>Tech Stack</span>
            <ChevronDown size={16} strokeWidth={1.9} />
          </button>
          <button className="reference-select-button" type="button">
            <span>Last Updated</span>
            <ChevronDown size={16} strokeWidth={1.9} />
          </button>
          <button className="reference-select-button compact" type="button">
            <Filter size={17} strokeWidth={1.9} />
            <span>Filters</span>
          </button>
          <IconButton icon={Settings} label="Builder settings" onClick={() => {}} />
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

          {builderRows.map(row => {
            const successRate =
              typeof row.successRate === "number" && Number.isFinite(row.successRate)
                ? Math.max(0, Math.min(100, row.successRate))
                : null;
            return (
              <button className={cx("reference-builder-row action", row.selected && "selected")} key={row.id} onClick={() => onOpenBuilderDetail(row.id)} type="button">
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
                <IconButton icon={MoreHorizontal} label="Project actions" onClick={() => {}} />
              </button>
            );
          })}
          {!builderRows.length ? (
            <div className="reference-builder-empty-state">
              <strong>No builder runs yet</strong>
              <p>Start a mission from Agent Mode or create a workspace run; Builder will populate from real mission activity.</p>
            </div>
          ) : null}
        </div>

        <div className="reference-builder-pagination">
          <span>
            {builderRows.length > 0
              ? `Showing 1 to ${Math.min(builderRows.length, 8)} of ${builderRows.length} projects`
              : "No projects to show yet"}
          </span>
          {builderRows.length > 0 ? (
            <div className="reference-page-buttons">
              <button disabled type="button">‹</button>
              <button className="active" type="button">1</button>
              {builderRows.length > 8 ? <button type="button">2</button> : null}
              {builderRows.length > 16 ? <button type="button">3</button> : null}
              {builderRows.length > 24 ? <button type="button">4</button> : null}
              <button disabled={builderRows.length <= 8} type="button">›</button>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function SkillHubSurface({ studioState }) {
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
          <button className="reference-outline-button" type="button">
            <History size={16} strokeWidth={1.9} />
            <span>Version History</span>
          </button>
          <button className="reference-outline-button" onClick={onSaveDraft} type="button">
            <FileText size={16} strokeWidth={1.9} />
            <span>Save Draft</span>
          </button>
          <button className="reference-black-button" onClick={onPublish} type="button">
            Publish
          </button>
          <IconButton icon={MoreHorizontal} label="More actions" onClick={() => {}} />
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
            <input placeholder="Search skills & rule sets..." />
          </label>

          <div className="reference-studio-list-section">
            <div className="reference-builder-section-head">
              <strong>Skills</strong>
              <button className="reference-mini-icon" type="button">
                <Plus size={14} strokeWidth={2} />
              </button>
            </div>
            <div className="reference-skill-list">
              {skills.map(item => (
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
              <button className="reference-mini-icon" type="button">
                <Plus size={14} strokeWidth={2} />
              </button>
            </div>
            <div className="reference-skill-list">
              {ruleSets.map(item => (
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

          <button className="reference-studio-archive" type="button">
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
                  <button className="reference-link-button" type="button">Edit</button>
                  <button className="reference-link-button" type="button">Preview</button>
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
            </>
          ) : null}
        </article>

        <article className="reference-skill-panel reference-studio-assistant">
          <div className="reference-builder-section-head">
            <strong>Ask a model</strong>
            <button className="reference-link-button" type="button">Collapse</button>
          </div>
          <div className="reference-inline-form-row">
            <SurfaceField label="Model">
              <select
                onChange={event => onAssistantFieldChange("model", event.target.value)}
                value={assistant.model || "GPT-4o"}
              >
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
              <button className="reference-tool-button" type="button">
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

function SettingsSurface({ settingsState }) {
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
    ["providers", "Models & Providers", Sparkles],
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

  return (
    <section className="reference-settings-surface">
      <div className="reference-settings-header">
        <div>
          <h1>Settings</h1>
          <p>Manage your preferences, agents, models, and workspace settings.</p>
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
              <SurfaceField label="Preferred harness">
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
              <div className="reference-settings-actions">
                <button className="reference-black-button" onClick={onSaveWorkspacePolicy} type="button">
                  Save changes
                </button>
              </div>
            </article>

            <article className="reference-settings-card">
              <div className="reference-builder-section-head">
                <div>
                  <strong>Codex Import & Workspace Roots</strong>
                  <span>
                    Bring over recent Codex folders, inspect recent threads, and add a workspace root with the system picker.
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
              <strong>Appearance</strong>
              <div className="reference-settings-block">
                <span>Theme</span>
                <div className="reference-theme-toggle">
                  <button className={appearance.theme === "light" ? "active" : ""} onClick={() => onSetAppearance("theme", "light")} type="button"><SunMedium size={18} strokeWidth={1.9} /><span>Light</span></button>
                  <button className={appearance.theme === "dark" ? "active" : ""} onClick={() => onSetAppearance("theme", "dark")} type="button"><Moon size={18} strokeWidth={1.9} /><span>Dark</span></button>
                  <button type="button"><Monitor size={18} strokeWidth={1.9} /><span>System</span></button>
                </div>
              </div>
              <div className="reference-settings-block">
                <span>Accent Color</span>
                <div className="reference-color-swatches">
                  {["#6f5cff", "#d0d5dd", "#1fb68f", "#f59e0b", "#e14f63"].map(color => (
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
              <div className="reference-settings-block">
                <span>Density</span>
                <div className="reference-density-toggle">
                  {["comfortable", "compact", "spacious"].map(option => (
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
                <span>Flux bar behavior</span>
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
                  <span>Fluxio Shell</span>
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

      {activeTab === "providers" ? (
        <div className="reference-settings-stack">
          <article className="reference-settings-card">
            <strong>Provider Connections</strong>
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
                      <button className="reference-outline-button" onClick={provider.onQuickAuth} type="button">
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
            <strong>Workspace Auth Paths</strong>
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
            <strong>Harness Availability</strong>
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
                  <p>{runtime.doctor_summary || runtime.doctorSummary || "Runtime status is unavailable."}</p>
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
              <article><span>Harness</span><strong>{workspaceProfileForm.preferredHarness}</strong></article>
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
              <button className="reference-outline-button" type="button">
                <FileText size={16} strokeWidth={1.9} />
                <span>Export Data</span>
              </button>
              <button className="reference-danger-button" type="button">Delete Workspace</button>
            </div>
          </article>
          <article className="reference-settings-card">
            <strong>Workspace Notes</strong>
            <p>Flux bar auto-collapse, color tokens, provider auth, and routing policies are persisted inside the reference shell state.</p>
            <p>Published rule sets immediately update the workspace routing overrides used for agent follow-ups.</p>
          </article>
        </div>
      ) : null}
    </section>
  );
}

export function FluxioReferenceShell(props) {
  const {
    agentScene,
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
    messages,
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
    onRuntimeChange,
    onSend,
    onSelectFlow,
    onSelectProject,
    onSetAgentScene,
    onSetAppearance,
    onSetSurface,
    runtimeOptions,
    runtimeStatus,
    settingsState,
    selectedEffortLabel,
    selectedModelLabel,
    selectedProjectId,
    selectedRuntime,
    slashCommands,
    sidebarBehavior = "auto",
    skillStudioState,
    surface,
    timelineMoments,
    missionLoop,
  } = props;
  const runtimeLabel =
    runtimeOptions.find(option => option.value === selectedRuntime)?.label || selectedRuntime;
  const showFlowSidebar = surface === "agent";
  const showAgentTopbar = surface === "agent";

  const mainContent =
    surface === "home" ? (
      <HomeSurface onOpenSurface={onSetSurface} />
    ) : surface === "skills" ? (
      <SkillHubSurface studioState={skillStudioState} />
    ) : surface === "settings" ? (
      <SettingsSurface settingsState={settingsState} />
    ) : surface === "agent" && agentScene === "idle" ? (
      <AgentIdleSurface
        draft={draft}
        onAttach={onAttach}
        onChangeDraft={onChangeDraft}
        onDictation={onDictation}
        onIdleSubmit={onIdleSubmit}
        onPaste={onPaste}
        onRuntimeChange={onRuntimeChange}
        onUseSlashCommand={onInsertSlashCommand}
        runtimeOptions={runtimeOptions}
        runtimeStatus={runtimeStatus}
        selectedEffortLabel={selectedEffortLabel}
        selectedModelLabel={selectedModelLabel}
        selectedRuntime={selectedRuntime}
        slashCommands={slashCommands}
      />
    ) : surface === "agent" && agentScene === "run" ? (
      <AgentRunningSurface
        draft={draft}
        feedbackItems={feedbackItems}
        missionLoop={missionLoop}
        messages={messages}
        onAttach={onAttach}
        onChangeDraft={onChangeDraft}
        onDictation={onDictation}
        onPaste={onPaste}
        onRuntimeChange={onRuntimeChange}
        onSend={onSend}
        onUseSlashCommand={onInsertSlashCommand}
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
        messages={messages}
        onAttach={onAttach}
        onChangeDraft={onChangeDraft}
        onDictation={onDictation}
        onPaste={onPaste}
        onSend={onSend}
        projectLabel={currentProjectLabel}
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
      data-detail-mode={showFlowSidebar || builderDetailOpen ? "true" : "false"}
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
                label="Agent Mode"
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
                label="Skill Studio"
                onClick={onOpenSkillStudio}
              />
            </div>
          </nav>
        </div>

        <button className="reference-sidebar-settings" onClick={onOpenSettings} type="button">
          <Settings size={18} strokeWidth={1.9} />
          <span>Settings</span>
        </button>
        <SidebarProfile />
      </aside>

      <main className={cx("reference-main", showFlowSidebar && "with-flow-sidebar", surface === "settings" && "surface-settings")}>
        {showFlowSidebar ? (
          <>
            <FlowSidebar
              currentModeLabel="Agent Mode"
              favoriteFlows={favoriteFlows}
              flowProjects={flowProjects}
              onOpenSettings={onOpenSettings}
              onSelectFlow={onSelectFlow}
              onSelectProject={onSelectProject}
              selectedProjectId={selectedProjectId}
            />
            <div className="reference-main-panel">
              {showAgentTopbar ? (
                <div className="reference-topbar">
                  <div className="reference-topbar-title">
                    <strong>Agent Mode</strong>
                    <ChevronDown size={16} strokeWidth={2} />
                    {agentScene === "live" ? (
                      <div className="reference-project-pill">
                        <Bot size={15} strokeWidth={1.9} />
                        <span>Project: {currentProjectLabel}</span>
                        <ChevronDown size={15} strokeWidth={1.9} />
                      </div>
                    ) : null}
                  </div>
                  <div className="reference-topbar-actions">
                    {agentScene === "live" ? (
                      <TopbarPill
                        active
                        dot
                        icon={Monitor}
                        label="Live UI"
                        onClick={() => onSetAgentScene("live")}
                      />
                    ) : null}
                    <TopbarPill icon={History} label="History" onClick={onHistory} />
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
