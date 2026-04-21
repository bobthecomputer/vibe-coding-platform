import {
  ArrowUp,
  BookOpen,
  Bot,
  ChevronDown,
  CircleCheckBig,
  CircleHelp,
  CircleDashed,
  Clock3,
  Code2,
  Expand,
  Filter,
  Grid2x2,
  Hammer,
  History,
  Home,
  Laptop,
  LayoutGrid,
  Mic,
  Monitor,
  MoreHorizontal,
  Paperclip,
  Play,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Smartphone,
  Sparkles,
  SquareTerminal,
  WandSparkles,
} from "lucide-react";

function cx(...values) {
  return values.filter(Boolean).join(" ");
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
    id: "general",
    title: "General",
    copy: "Browse documentation, guides, and resources.",
    tone: "blue",
    icon: Grid2x2,
  },
];

const BUILDER_METRICS = [
  {
    id: "projects",
    label: "Total Projects",
    value: "28",
    delta: "15% vs last month",
    tone: "up",
    icon: Code2,
  },
  {
    id: "runs",
    label: "Active Runs",
    value: "14",
    delta: "7% vs last month",
    tone: "up",
    icon: Play,
  },
  {
    id: "success",
    label: "Success Rate",
    value: "91%",
    delta: "5% vs last month",
    tone: "up",
    icon: CircleCheckBig,
  },
  {
    id: "turning-point",
    label: "Avg. Turning Point",
    value: "6m 47s",
    delta: "8% vs last month",
    tone: "down",
    icon: Clock3,
  },
];

const BUILDER_ROWS = [
  {
    id: "saas-landing",
    name: "SaaS Landing Page",
    description: "Next.js marketing site with auth",
    status: "Running",
    statusTone: "running",
    lastRun: "2m 14s",
    lastRunMeta: "Just now",
    turningPoint: "4m 21s",
    turningPointDelta: "12%",
    turningPointTone: "up",
    successRate: 96,
    runs: 24,
    updated: "Just now",
  },
  {
    id: "ai-chat",
    name: "AI Chat Dashboard",
    description: "React dashboard with real-time AI",
    status: "Completed",
    statusTone: "completed",
    lastRun: "6m 31s",
    lastRunMeta: "10 min ago",
    turningPoint: "7m 02s",
    turningPointDelta: "8%",
    turningPointTone: "down",
    successRate: 94,
    runs: 42,
    updated: "10 min ago",
  },
  {
    id: "cli-tool",
    name: "CLI Tool - Flux",
    description: "TypeScript CLI for project scaffolding",
    status: "Completed",
    statusTone: "completed",
    lastRun: "8m 47s",
    lastRunMeta: "1h ago",
    turningPoint: "5m 18s",
    turningPointDelta: "15%",
    turningPointTone: "up",
    successRate: 93,
    runs: 31,
    updated: "1h ago",
  },
  {
    id: "ecommerce-api",
    name: "Ecommerce API",
    description: "Node.js API with Stripe integration",
    status: "Running",
    statusTone: "running",
    lastRun: "3m 12s",
    lastRunMeta: "2h ago",
    turningPoint: "6m 34s",
    turningPointDelta: "5%",
    turningPointTone: "down",
    successRate: 88,
    runs: 17,
    updated: "2h ago",
  },
  {
    id: "mobile-onboarding",
    name: "Mobile App - Onboarding",
    description: "React Native onboarding flow",
    status: "Failed",
    statusTone: "failed",
    lastRun: "1m 33s",
    lastRunMeta: "2h ago",
    turningPoint: "2m 11s",
    turningPointDelta: "23%",
    turningPointTone: "down",
    successRate: 68,
    runs: 9,
    updated: "2h ago",
  },
  {
    id: "supabase-schema",
    name: "Supabase Schema",
    description: "Database schema and migrations",
    status: "Completed",
    statusTone: "completed",
    lastRun: "4m 05s",
    lastRunMeta: "3h ago",
    turningPoint: "3m 44s",
    turningPointDelta: "9%",
    turningPointTone: "up",
    successRate: 95,
    runs: 36,
    updated: "3h ago",
  },
  {
    id: "support-agent",
    name: "Support Agent",
    description: "RAG agent for docs and tickets",
    status: "Running",
    statusTone: "running",
    lastRun: "5m 18s",
    lastRunMeta: "Yesterday",
    turningPoint: "6m 09s",
    turningPointDelta: "4%",
    turningPointTone: "up",
    successRate: 91,
    runs: 21,
    updated: "Yesterday",
  },
  {
    id: "internal-admin",
    name: "Internal Admin Panel",
    description: "Vue 3 admin panel",
    status: "Paused",
    statusTone: "paused",
    lastRun: "—",
    lastRunMeta: "May 11, 2025",
    turningPoint: "—",
    turningPointDelta: "—",
    turningPointTone: "flat",
    successRate: 0,
    runs: 8,
    updated: "2 days ago",
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

function AgentIdleSurface(props) {
  const {
    draft,
    selectedRuntime,
    runtimeOptions,
    selectedModelLabel,
    selectedEffortLabel,
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
    selectedRuntime,
    selectedRuntimeLabel,
    selectedModelLabel,
    selectedEffortLabel,
    onAttach,
    onChangeDraft,
    onDictation,
    onPaste,
    onRuntimeChange,
    onSend,
  } = props;

  return (
    <section className="reference-agent-run">
      <div className="reference-chat-column">
        <div className="reference-user-bubble">
          <p>Analyze our customer support tickets from last week and identify the top recurring issues.</p>
          <span>10:42 AM</span>
        </div>

        <div className="reference-agent-thread">
          <div className="reference-agent-avatar">
            <div className="reference-brand-mark tiny">
              <span />
              <span />
              <span />
            </div>
          </div>
          <div className="reference-agent-thread-body">
            <p className="reference-thread-lead">
              I&apos;ll analyze last week&apos;s support tickets and identify the top recurring issues.
            </p>

            <article className="reference-status-panel">
              <h3>Searching tickets from May 6 – May 12, 2025</h3>
              <div className="reference-status-list">
                <StepState done label="Retrieving ticket data" />
                <StepState done label="Processing and clustering issues" />
                <StepState done label="Analyzing patterns" />
                <StepState pending label="Compiling results" />
              </div>
            </article>

            <article className="reference-report-panel">
              <h3>Here are the top 5 recurring issues from last week&apos;s tickets:</h3>
              <ol>
                <li>
                  <strong>Login Issues</strong>
                  <span>1,243 tickets</span>
                  <p>Customers experiencing problems logging in due to password resets, 2FA errors, and account lockouts.</p>
                </li>
                <li>
                  <strong>Billing &amp; Payments</strong>
                  <span>987 tickets</span>
                  <p>Issues with failed payments, subscription renewals, and invoice discrepancies.</p>
                </li>
                <li>
                  <strong>Feature Requests</strong>
                  <span>742 tickets</span>
                  <p>Requests for new features, integrations, and product improvements.</p>
                </li>
                <li>
                  <strong>Performance Issues</strong>
                  <span>531 tickets</span>
                  <p>Slow loading times, timeouts, and degraded performance.</p>
                </li>
                <li>
                  <strong>Account Management</strong>
                  <span>412 tickets</span>
                  <p>Questions around plan changes, cancellations, and data export.</p>
                </li>
              </ol>
              <div className="reference-report-foot">
                <div className="reference-report-actions">
                  <button type="button">Copy</button>
                  <button type="button">Like</button>
                  <button type="button">Retry</button>
                </div>
                <span>10:43 AM</span>
              </div>
            </article>
          </div>
        </div>
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
      </ComposerDock>
    </section>
  );
}

function LivePreviewSurface(props) {
  const {
    draft,
    onAttach,
    onChangeDraft,
    onDictation,
    onPaste,
    onSend,
    projectLabel,
  } = props;

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
          <p>I&apos;m updating the hero section to improve the value proposition visibility and adjust the CTA hierarchy.</p>
          <div className="reference-live-editing">
            <span>Editing: HeroSection.tsx</span>
            <CircleDashed size={18} strokeWidth={2.1} />
          </div>
        </article>

        <article className="reference-live-card">
          <div className="reference-live-agent user">
            <div className="reference-user-mini">O</div>
            <div>
              <strong>You</strong>
            </div>
          </div>
          <p>Can we make the primary CTA button a bit larger and with more contrast?</p>
        </article>

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
          <p>Good call. I&apos;ll increase the button size and improve contrast for better visibility.</p>
        </article>

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
            <StepState done label="Updating button size" />
            <StepState done label="Improving contrast" />
            <StepState pending label="Running preview" />
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
                <strong>Acme</strong>
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
                <strong>Acme 2.0 is here. Learn what&apos;s new</strong>
              </div>
              <h2>Ship faster with AI that understands your code.</h2>
              <p>Acme helps engineering teams build, test, and deploy better software together.</p>
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
              <p>Looks better! Can we make the button radius a bit smaller? Something more like 12px.</p>
              <div className="reference-preview-comment-foot">
                <button type="button">😊</button>
                <button className="send" type="button">Send</button>
              </div>
            </div>

            <div className="reference-preview-dashboard">
              <aside className="reference-preview-sidebar">
                <strong>Acme</strong>
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
                    <span>Deployments</span>
                    <strong>32</strong>
                    <p>12% vs last 7 days</p>
                  </article>
                  <article>
                    <span>Success Rate</span>
                    <strong>98.6%</strong>
                    <p>2.4% vs last 7 days</p>
                  </article>
                  <article>
                    <span>Build Time</span>
                    <strong>2m 45s</strong>
                    <p>8% vs last 7 days</p>
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

function BuilderSurface() {
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
        {BUILDER_METRICS.map(item => (
          <BuilderMetricCard item={item} key={item.id} />
        ))}
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

          {BUILDER_ROWS.map(row => (
            <div className="reference-builder-row" key={row.id}>
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
                <strong>{row.successRate > 0 ? `${row.successRate}%` : "—"}</strong>
                <div className="reference-success-track">
                  <span style={{ width: `${row.successRate}%` }} />
                </div>
              </div>
              <strong>{row.runs}</strong>
              <span className="reference-updated">{row.updated}</span>
              <IconButton icon={MoreHorizontal} label="Project actions" onClick={() => {}} />
            </div>
          ))}
        </div>

        <div className="reference-builder-pagination">
          <span>Showing 1 to 8 of 28 projects</span>
          <div className="reference-page-buttons">
            <button type="button">‹</button>
            <button className="active" type="button">1</button>
            <button type="button">2</button>
            <button type="button">3</button>
            <button type="button">4</button>
            <button type="button">›</button>
          </div>
        </div>
      </div>
    </section>
  );
}

function GeneralSurface() {
  return (
    <section className="reference-general-surface">
      <div className="reference-surface-intro left">
        <h1>General</h1>
        <p>Documentation, guidance, and resources will land here in the next pass.</p>
      </div>
      <div className="reference-general-grid">
        <article>
          <BookOpen size={24} strokeWidth={1.9} />
          <strong>Guides</strong>
          <p>Product documentation, onboarding flows, and operator instructions.</p>
        </article>
        <article>
          <SquareTerminal size={24} strokeWidth={1.9} />
          <strong>Reference</strong>
          <p>Runtime setup, dictation notes, and workflow references for the desktop shell.</p>
        </article>
        <article>
          <Sparkles size={24} strokeWidth={1.9} />
          <strong>Patterns</strong>
          <p>Approved UI motifs and reusable product surfaces for future screens.</p>
        </article>
      </div>
    </section>
  );
}

export function FluxioReferenceShell(props) {
  const {
    agentScene,
    currentProjectLabel,
    draft,
    onAttach,
    onChangeDraft,
    onDictation,
    onHistory,
    onIdleSubmit,
    onMore,
    onOpenSettings,
    onOpenSkillStudio,
    onPaste,
    onRuntimeChange,
    onSend,
    onSetAgentScene,
    onSetSurface,
    runtimeOptions,
    selectedEffortLabel,
    selectedModelLabel,
    selectedRuntime,
    surface,
  } = props;

  const builderLikeNav = surface === "builder" || agentScene === "live";

  return (
    <div className={cx("reference-shell", `surface-${surface}`)}>
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
              {builderLikeNav ? (
                <RailItem
                  active={false}
                  icon={LayoutGrid}
                  label="Skill Studio"
                  onClick={onOpenSkillStudio}
                />
              ) : (
                <RailItem
                  active={surface === "general"}
                  icon={Grid2x2}
                  label="General"
                  onClick={() => onSetSurface("general")}
                />
              )}
            </div>

            <div className="reference-sidebar-group">
              <span>Settings</span>
              <RailItem active={false} icon={Settings} label="Settings" onClick={onOpenSettings} />
            </div>
          </nav>
        </div>

        <SidebarProfile />
      </aside>

      <main className="reference-main">
        {surface === "home" ? (
          <div className="reference-topbar home">
            <div className="reference-topbar-title">
              <div>
                <strong>Agent Workspace</strong>
                <span>Build. Orchestrate. Ship.</span>
              </div>
            </div>
            <IconButton icon={CircleHelp} label="Help" onClick={() => {}} />
          </div>
        ) : surface === "builder" ? (
          <div className="reference-topbar">
            <div className="reference-topbar-title">
              <strong>Builder</strong>
            </div>
            <div className="reference-topbar-actions">
              <button className="reference-outline-button strong" onClick={() => {}} type="button">
                <Plus size={18} strokeWidth={1.9} />
                <span>New Project</span>
              </button>
              <IconButton icon={LayoutGrid} label="Layout" onClick={() => {}} />
            </div>
          </div>
        ) : (
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
        )}

        <div className="reference-main-body">
          {surface === "home" ? <HomeSurface onOpenSurface={onSetSurface} /> : null}
          {surface === "general" ? <GeneralSurface /> : null}
          {surface === "agent" && agentScene === "idle" ? (
            <AgentIdleSurface
              draft={draft}
              onAttach={onAttach}
              onChangeDraft={onChangeDraft}
              onDictation={onDictation}
              onIdleSubmit={onIdleSubmit}
              onPaste={onPaste}
              onRuntimeChange={onRuntimeChange}
              runtimeOptions={runtimeOptions}
              selectedEffortLabel={selectedEffortLabel}
              selectedModelLabel={selectedModelLabel}
              selectedRuntime={selectedRuntime}
            />
          ) : null}
          {surface === "agent" && agentScene === "run" ? (
            <AgentRunningSurface
              draft={draft}
              onAttach={onAttach}
              onChangeDraft={onChangeDraft}
              onDictation={onDictation}
              onPaste={onPaste}
              onRuntimeChange={onRuntimeChange}
              onSend={onSend}
              selectedEffortLabel={selectedEffortLabel}
              selectedModelLabel={selectedModelLabel}
              selectedRuntime={selectedRuntime}
              selectedRuntimeLabel={
                runtimeOptions.find(option => option.value === selectedRuntime)?.label || selectedRuntime
              }
            />
          ) : null}
          {surface === "agent" && agentScene === "live" ? (
            <LivePreviewSurface
              draft={draft}
              onAttach={onAttach}
              onChangeDraft={onChangeDraft}
              onDictation={onDictation}
              onPaste={onPaste}
              onSend={onSend}
              projectLabel={currentProjectLabel}
            />
          ) : null}
          {surface === "builder" ? <BuilderSurface /> : null}
        </div>
      </main>
    </div>
  );
}
