import React from "react";
import {
  ArrowRight,
  BracketsCurly,
  Browser,
  ChatCircleText,
  CheckCircle,
  Cloud,
  Cpu,
  Cube,
  Database,
  FileText,
  Fingerprint,
  Gauge,
  GithubLogo,
  HardDrives,
  HouseLine,
  LockKey,
  MagnifyingGlass,
  Monitor,
  Network,
  PuzzlePiece,
  ShieldCheck,
  TerminalWindow,
} from "@phosphor-icons/react";

import { FluxioShellApp } from "./FluxioShell.jsx";
import { buildLiveReviewWorkbench, getSnapshot } from "./fluxioBridge.ts";

const PRODUCT_NAME = "Fluxio";
const PRODUCT_TAGLINE = "Agent operating system for workspaces.";
const PRIVATE_NAS_CONTROL_URL = "https://sysnology.tail602108.ts.net:47880/control";
const PUBLIC_ROADMAP_EVENTS = [
  {
    id: "nas-bridge",
    Icon: HardDrives,
    phase: "Live lane",
    status: "Bridge map",
    title: "Universal bridge",
    detail:
      "Move one project between this computer, the NAS, and cloud drives without losing the working copy or hiding the transfer.",
    proof: "Workstation, NAS, and cloud routes stay visible with preview-first writes, SSH/SFTP control, and approval-gated transfers.",
  },
  {
    id: "tool-ports",
    Icon: Network,
    phase: "Building",
    status: "Execution fabric",
    title: "Tools and ports",
    detail:
      "Put runtimes, browser hooks, bridge endpoints, image tools, account setup, and repair actions in one managed surface.",
    proof: "Setup services, bridge sessions, runtime lanes, action hooks, and port labels are visible in Settings.",
  },
  {
    id: "browser-computer-use",
    Icon: Browser,
    phase: "Building",
    status: "Web as workspace",
    title: "Browser use",
    detail:
      "Let the agent navigate, extract, compare, and act across web sessions while approvals and proof stay readable.",
    proof: "Browser-use plugin path, live UI review, screenshots, and action replay are the integration line.",
  },
  {
    id: "selectable-ui-layer",
    Icon: Fingerprint,
    phase: "Building",
    status: "Comment layer",
    title: "Selectable UI layer",
    detail:
      "Every app screen, website, screenshot, and browser page should become selectable and commentable, so the agent can discuss the exact piece of UI instead of guessing from text.",
    proof:
      "The integrated product path starts with UI selection, anchored comments, screenshot proof, and a writer workflow for product videos, YouTube scripts, tutorials, and release notes.",
  },
  {
    id: "tutorial-levels",
    Icon: PuzzlePiece,
    phase: "Queued",
    status: "Guided setup",
    title: "Tutorial levels",
    detail:
      "Beginner, builder, advanced, and experimental paths explain setup, model auth, NAS use, and safe autonomy at the right depth.",
    proof: "Profile choices, onboarding checks, setup services, and permission gates become the tutorial source.",
  },
  {
    id: "cowork-modes",
    Icon: Cube,
    phase: "Queued",
    status: "Work your way",
    title: "Cowork modes",
    detail:
      "Use different process views for coding, regular work, school work, research runs, and benchmark tracking.",
    proof: "Workspace profiles, mode presets, and process-specific dashboards keep the same agent core without forcing one UI for every task.",
  },
  {
    id: "image-workflows",
    Icon: Database,
    phase: "Queued",
    status: "Creative workflows",
    title: "Image and asset work",
    detail:
      "Generate images, inspect them, turn them into site or game assets, and keep outputs tied to project folders and proof.",
    proof: "Taste skills stay active while older custom skills are archived, and image tools are tracked by setup health.",
  },
  {
    id: "style-texture-system",
    Icon: BracketsCurly,
    phase: "Queued",
    status: "Style production",
    title: "Style and texture system",
    detail:
      "Build style bibles like an animation pipeline: reference capture, shape language, palette rules, texture regions, line weights, motion timing, and output checks.",
    proof:
      "The app stores style presets as production recipes, then uses screenshots, comments, and generated frames to compare whether output matches the chosen style language.",
  },
  {
    id: "autonomy-audit",
    Icon: ShieldCheck,
    phase: "Always on",
    status: "Quality bar",
    title: "Autonomy proof",
    detail:
      "Every major feature needs a real action path, visible state, failure reason, and build/test proof before it is called ready.",
    proof: "Release readiness gates, quality roadmap, service management, and verification commands drive the app cockpit.",
  },
];

function hasTauriBackend() {
  return Boolean((globalThis as any).window?.__TAURI__ || (globalThis as any).window?.__TAURI_INTERNALS__);
}

function webBackendBaseUrl(): string {
  const configured =
    (import.meta as any).env?.VITE_FLUXIO_BACKEND_URL ||
    (globalThis as any).window?.__FLUXIO_BACKEND_URL__ ||
    "";
  return String(configured || "").trim().replace(/\/$/, "");
}

function isConsolePath(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return window.location.pathname.startsWith("/control") || window.location.pathname.startsWith("/console");
}

function isDevControlPreview(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return Boolean(
    (import.meta as any).env?.DEV &&
      isConsolePath() &&
      new URLSearchParams(window.location.search).get("preview-control") === "1",
  );
}

function shouldOfferPrivateNasControl(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  const host = window.location.hostname.toLowerCase();
  return ["localhost", "127.0.0.1", "::1", ""].includes(host);
}

async function fetchWithTimeout(url: string, init: RequestInit = {}, timeoutMs = 1800) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    window.clearTimeout(timer);
  }
}

function SidebarProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

type BoundaryProps = {
  children: React.ReactNode;
  getLastAction: () => string;
  getBootDiagnostics: () => string[];
  onRecover: () => void;
};

type BoundaryState = {
  error: Error | null;
  capturedAt: string;
};

function hardReloadControl(reason: string) {
  try {
    const url = new URL(window.location.href);
    url.searchParams.set("_syntelos_reload", `${Date.now()}`);
    url.searchParams.set("_syntelos_reason", reason);
    window.location.replace(url.toString());
  } catch {
    window.location.reload();
  }
}

class FluxioErrorBoundary extends React.Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = {
    error: null,
    capturedAt: "",
  };

  static getDerivedStateFromError(error: Error): BoundaryState {
    return {
      error,
      capturedAt: new Date().toISOString(),
    };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error(`${PRODUCT_NAME} UI crashed`, {
      error,
      info,
      lastAction: this.props.getLastAction(),
      capturedAt: new Date().toISOString(),
    });
  }

  handleRecover = () => {
    hardReloadControl("recover");
  };

  render() {
    if (!this.state.error) {
      return this.props.children;
    }

    return (
      <main className="fluxio-error-screen">
        <section className="fluxio-error-panel">
          <p className="eyebrow">Recoverable UI error</p>
          <h1>{PRODUCT_NAME} hit a render failure.</h1>
          <p>
            <strong>Failing action:</strong> {this.props.getLastAction() || "Unknown action"}
          </p>
          <p>
            <strong>Error:</strong> {this.state.error.message || String(this.state.error)}
          </p>
          <p>
            <strong>Captured:</strong> {this.state.capturedAt || "Unknown"}
          </p>
          <details>
            <summary>Boot diagnostics</summary>
            <ul>
              {this.props.getBootDiagnostics().map(line => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </details>
          <div className="fluxio-empty-actions">
            <button className="action-btn primary" onClick={this.handleRecover} type="button">
              Recover UI
            </button>
            <button className="action-btn" onClick={() => hardReloadControl("reload")} type="button">
              Reload app
            </button>
          </div>
        </section>
      </main>
    );
  }
}

function makeBootDiagnostics(): string[] {
  return [
    `Boot timestamp: ${new Date().toISOString()}`,
    `Location: ${window.location.href}`,
    `User agent: ${window.navigator.userAgent}`,
  ];
}

type AuthState = {
  checked: boolean;
  authenticated: boolean;
  backendAvailable: boolean;
  productName: string;
  user: { username?: string; displayName?: string; role?: string } | null;
  accountHints: { username?: string; displayName?: string }[];
  error: string;
};

function PublicProductPage() {
  const githubUrl = "https://github.com/bobthecomputer/vibe-coding-platform";
  const [activeRoadmapId, setActiveRoadmapId] = React.useState(PUBLIC_ROADMAP_EVENTS[0].id);
  const [activePreviewMode, setActivePreviewMode] = React.useState<"agent" | "builder">(() => {
    if (typeof window !== "undefined" && new URLSearchParams(window.location.search).get("previewMode") === "builder") {
      return "builder";
    }
    return "agent";
  });
  const activeRoadmap =
    PUBLIC_ROADMAP_EVENTS.find(item => item.id === activeRoadmapId) || PUBLIC_ROADMAP_EVENTS[0];
  const ActiveRoadmapIcon = activeRoadmap.Icon;
  const isBuilderPreview = activePreviewMode === "builder";

  return (
    <main className="grand-public-page">
      <nav className="grand-public-nav" aria-label={PRODUCT_NAME}>
        <a className="grand-public-brand" href="/">
          {PRODUCT_NAME}
        </a>
        <div className="grand-public-nav-links">
          <a href="#overview">Why</a>
          <a href="#audience">Audience</a>
          <a href="#setup">Setup</a>
          <a href="#roadmap">Roadmap</a>
        </div>
        <div className="grand-public-nav-actions">
          <a className="grand-public-ghost" href={githubUrl} rel="noreferrer" target="_blank">
            <GithubLogo aria-hidden="true" size={17} weight="bold" />
            View GitHub
          </a>
          <a className="grand-public-primary" href="/control">
            Open App
          </a>
        </div>
      </nav>

      <section className="grand-public-hero" id="overview">
        <div className="grand-public-copy">
          <p className="grand-public-kicker">Local-first agent workbench</p>
          <h1>{PRODUCT_NAME}</h1>
          <p className="grand-public-tagline">{PRODUCT_TAGLINE}</p>
          <p className="grand-public-lede">
            A private control room for builders who want agents to plan, execute, verify,
            remember, and resume without living inside a hosted dashboard. Run it on a
            Windows machine, a light device on your network, or a Synology NAS when you want
            it always available.
          </p>
          <div className="grand-public-actions">
            <a className="grand-public-primary" href={githubUrl} rel="noreferrer" target="_blank">
              <GithubLogo aria-hidden="true" size={18} weight="bold" />
              View GitHub
            </a>
            <a className="grand-public-ghost" href="#setup">
              Set up Fluxio
              <ArrowRight aria-hidden="true" size={16} weight="bold" />
            </a>
          </div>
          <div className="grand-public-proof" aria-label="Project properties">
            <div>
              <LockKey aria-hidden="true" size={22} weight="duotone" />
              <strong>Private memory</strong>
              <span>Agent context and secrets stay on your machine.</span>
            </div>
            <div>
              <HardDrives aria-hidden="true" size={22} weight="duotone" />
              <strong>Runs anywhere local</strong>
              <span>NAS is optional. It keeps Fluxio always on.</span>
            </div>
            <div id="live-ui">
              <Browser aria-hidden="true" size={22} weight="duotone" />
              <strong>Live UI in context</strong>
              <span>Live screens, selections, and notes.</span>
            </div>
          </div>
        </div>

        <section className="syntelos-app-preview" aria-label={`${PRODUCT_NAME} app preview`}>
          <div className="syntelos-window-shell">
            <div className="syntelos-window-chrome">
              <div aria-hidden="true" className="syntelos-window-dots">
                <span />
                <span />
                <span />
              </div>
              <strong>syntelos.local/control</strong>
              <span>Live workspace</span>
            </div>

            <div className="syntelos-mode-bar" aria-label="App modes">
              <span>Home</span>
              <button
                className={!isBuilderPreview ? "active" : ""}
                onClick={() => setActivePreviewMode("agent")}
                type="button"
              >
                Agent
              </button>
              <button
                className={isBuilderPreview ? "active" : ""}
                onClick={() => setActivePreviewMode("builder")}
                type="button"
              >
                Builder
              </button>
              <span>Apps</span>
              <span>Settings</span>
            </div>

            <div className="syntelos-preview-grid" data-preview-mode={activePreviewMode}>
              <aside className="syntelos-condition-rail" aria-label="Conditions and proof">
                <div>
                  <p>{isBuilderPreview ? "Builder proof" : "Agent context"}</p>
                  <strong>{isBuilderPreview ? "5 checks" : "3 ready"}</strong>
                </div>
                <div className="syntelos-rail-item good">
                  <ShieldCheck aria-hidden="true" size={18} weight="duotone" />
                  <span>{isBuilderPreview ? "Tests passed" : "Provider auth"}</span>
                </div>
                <div className="syntelos-rail-item good">
                  <HardDrives aria-hidden="true" size={18} weight="duotone" />
                  <span>{isBuilderPreview ? "Files tracked" : "Local workspace"}</span>
                </div>
                <div className="syntelos-rail-item warn">
                  <TerminalWindow aria-hidden="true" size={18} weight="duotone" />
                  <span>{isBuilderPreview ? "Review pending" : "Approval waiting"}</span>
                </div>
                <div className="syntelos-proof-stack">
                  <span>Proof</span>
                  <strong>{isBuilderPreview ? "Diff map" : "Conversation plan"}</strong>
                  <strong>{isBuilderPreview ? "Test output" : "Telegram post"}</strong>
                  <strong>{isBuilderPreview ? "Run history" : "Next step"}</strong>
                </div>
              </aside>

              <section className="syntelos-agent-pane">
                <header>
                  <div>
                    <p>{isBuilderPreview ? "Builder mode" : "Agent mode"}</p>
                    <h2>
                      {isBuilderPreview
                        ? "Review changes, files, diffs, and proof."
                        : "Plan the next run and keep the conversation compact."}
                    </h2>
                  </div>
                  <button type="button">{isBuilderPreview ? "Review" : "Resume"}</button>
                </header>

                {isBuilderPreview ? (
                  <div className="syntelos-builder-proof-card">
                    <div>
                      <strong>Changed files</strong>
                      <span>FluxioApp.tsx / styles.css / fixtures.js</span>
                    </div>
                    <div className="syntelos-diff-map" aria-label="Builder diff map">
                      <span />
                      <span />
                      <span />
                      <span />
                    </div>
                    <p>Builder keeps the proof lane, diffs, tests, and release gates out of the Agent conversation.</p>
                  </div>
                ) : (
                  <div className="syntelos-thread-card">
                    <div className="syntelos-message user">
                      <strong>You</strong>
                      <p>Make this app explain itself to a first-time student on a school laptop.</p>
                    </div>
                    <div className="syntelos-message agent">
                      <strong>Fluxio Agent</strong>
                      <p>
                        Plan: update the tutorial, capture UI proof, run checks, then post the compact summary.
                      </p>
                    </div>
                    <div className="syntelos-message telegram">
                      <strong>Telegram</strong>
                      <p>Approval needed only if the installer changes permissions or writes outside the project.</p>
                    </div>
                  </div>
                )}

                <div className="syntelos-live-workspace" aria-label="Selectable live UI preview">
                  <div className="syntelos-live-top">
                    <strong>{isBuilderPreview ? "Builder proof board" : "Live UI inside Agent"}</strong>
                    <span>{isBuilderPreview ? "diffs and gates" : "select and comment"}</span>
                  </div>
                  <div className="syntelos-live-canvas">
                    <span className="comment-pin one">1</span>
                    <span className="comment-pin two">2</span>
                    <div className="live-app-card wide" />
                    <div className="live-app-card" />
                    <div className="live-app-card active" />
                    <div className="live-comment">
                      <strong>{isBuilderPreview ? "Diff" : "Message"}</strong>
                      <span>{isBuilderPreview ? "+142 / -18" : "more compact"}</span>
                    </div>
                  </div>
                </div>

                <LiveReviewWorkbench mode={activePreviewMode} />

                <div className="syntelos-builder-strip" aria-label="Builder and app previews">
                  <div>
                    <Browser aria-hidden="true" size={19} weight="duotone" />
                    <strong>Agent live UI</strong>
                    <span>See changes during the run</span>
                  </div>
                  <div>
                    <BracketsCurly aria-hidden="true" size={19} weight="duotone" />
                    <strong>Builder history</strong>
                    <span>Work done, files, diffs</span>
                  </div>
                  <div>
                    <Fingerprint aria-hidden="true" size={19} weight="duotone" />
                    <strong>Settings</strong>
                    <span>Models, providers, profiles</span>
                  </div>
                </div>
              </section>

              <aside className="syntelos-right-panel" aria-label="Builder history and settings">
                <div className="syntelos-status-card syntelos-home-card">
                  <span>Home</span>
                  <strong>Today, at a glance</strong>
                  <p>Open missions, school tasks, app work, and reminders start here.</p>
                </div>
                <div className="syntelos-history-card">
                  <span>Builder / history</span>
                  <strong>Today</strong>
                  <p><i /> Added onboarding panel <b>+142</b></p>
                  <p><i /> Improved mobile layout <b>+64</b></p>
                  <p><i /> Captured UI note <b>2 comments</b></p>
                </div>
                <div className="syntelos-status-card">
                  <span>Settings</span>
                  <strong>Models and providers</strong>
                  <p>Model choice, auth, profiles, theme, and personalization stay here.</p>
                </div>
                <div className="syntelos-notification-card">
                  <span>Notifications</span>
                  <p><b className="soft" />Low priority grouped</p>
                  <p><b className="warn" />Approval only when needed</p>
                  <p><b className="quiet" />Quiet hours respected</p>
                </div>
                <div className="syntelos-preview-mini">
                  <span />
                  <span />
                  <span />
                  <p>Diff preview</p>
                </div>
                <div className="syntelos-status-card">
                  <span>Runtime</span>
                  <strong>Computer use ready</strong>
                  <p>Browser, files, GitHub projects, and app checks are grouped by capability.</p>
                </div>
              </aside>
            </div>
          </div>
        </section>
      </section>

      <section className="syntelos-story-section">
        <article className="syntelos-origin-card">
          <p className="grand-public-kicker">Origin</p>
          <h2>Built because planning and execution were too far apart.</h2>
          <p>
            The project started from a practical frustration: normal chat workflows can plan,
            but they do not naturally keep going from plan mode into execution mode, verification,
            and follow-up without a human constantly babysitting the session. Fluxio is the
            attempt to make that loop truly automatic while still showing proof and asking for
            judgment at real risk boundaries.
          </p>
          <p>
            The school use case matters: it should work from light Windows devices, across a
            local network, and without forcing every student or maker to own a powerful machine.
            A NAS is useful because it can stay on, but the product is not NAS-only.
          </p>
        </article>

        <div className="syntelos-truth-grid" id="audience">
          <article>
            <ShieldCheck aria-hidden="true" size={24} weight="duotone" />
            <h3>Strengths</h3>
            <p>Local memory, supervised autonomy, live UI review, restart-safe runs, provider setup, and proof artifacts in one place.</p>
          </article>
          <article>
            <LockKey aria-hidden="true" size={24} weight="duotone" />
            <h3>Drawbacks</h3>
            <p>It is still a local technical product. Setup, model auth, NAS networking, and long-running automation need clearer guidance and stronger defaults.</p>
          </article>
          <article>
            <Network aria-hidden="true" size={24} weight="duotone" />
            <h3>Who it is for</h3>
            <p>Students, indie builders, teachers, light-device users, and small teams who want stronger agents without handing every workflow to a cloud dashboard.</p>
          </article>
        </div>
      </section>

      <section className="syntelos-roadmap-section" id="roadmap">
        <div className="syntelos-roadmap-head">
          <p className="grand-public-kicker">Roadmap</p>
          <h2>The path to autonomous work.</h2>
          <p>
            Fluxio grows in clear phases: first a dependable bridge between your computer,
            NAS, and cloud drives, then stronger browser and desktop control, a selectable
            comment layer for any UI, tutorials for each skill level, and focused workspaces
            for coding, school, research, benchmarks, creative work, style/texture
            production, and everyday operations.
          </p>
        </div>
        <div className="syntelos-roadmap-live" aria-label="Animated roadmap and bridge preview">
          <div className="syntelos-roadmap-rail" aria-label="Roadmap milestones">
            {PUBLIC_ROADMAP_EVENTS.map((item, index) => (
              <button
                className={item.id === activeRoadmap.id ? "active" : ""}
                key={item.id}
                onClick={() => setActiveRoadmapId(item.id)}
                style={{ "--roadmap-index": index } as React.CSSProperties}
                type="button"
              >
                <i aria-hidden="true">{index + 1}</i>
                <span>{item.phase}</span>
                <strong>{item.title}</strong>
                <em>{item.status}</em>
                {index === 0 ? (
                  <small aria-hidden="true">
                    <b />
                    Live transcript
                  </small>
                ) : null}
              </button>
            ))}
          </div>
          <aside className="syntelos-roadmap-stage" key={activeRoadmap.id}>
            <div className="syntelos-roadmap-screen" aria-label="Bridge map preview">
              <div className="roadmap-screen-chrome">
                <div className="roadmap-screen-title">
                  <Network aria-hidden="true" size={34} weight="bold" />
                  <div>
                    <strong>Bridge Map</strong>
                    <p>Your workflow from local to cloud</p>
                  </div>
                </div>
                <span>All systems visible</span>
                <button type="button">Test bridge</button>
              </div>
              <div className="roadmap-screen-body">
                <div className="roadmap-flow" aria-label="Interactive bridge workflow">
                  <button className="roadmap-flow-step edit" type="button">
                    <span>1. Edit</span>
                    <i aria-hidden="true"><FileText size={28} weight="duotone" /></i>
                    <strong>Local edits</strong>
                    <em>Make changes on your device</em>
                    <b><CheckCircle size={15} weight="fill" />Selected</b>
                  </button>
                  <div className="roadmap-flow-arrow" aria-hidden="true" />
                  <button className="roadmap-flow-step review" type="button">
                    <span>2. Review</span>
                    <i aria-hidden="true"><MagnifyingGlass size={30} weight="bold" /></i>
                    <strong>Review</strong>
                    <em>Preview and approve changes</em>
                    <b><span />In progress</b>
                  </button>
                  <div className="roadmap-flow-arrow" aria-hidden="true" />
                  <button className="roadmap-flow-step sync" type="button">
                    <span>3. Sync</span>
                    <i aria-hidden="true"><Database size={30} weight="duotone" /></i>
                    <strong>NAS sync</strong>
                    <em>Sync approved files to your NAS</em>
                    <b>Next</b>
                  </button>
                  <div className="roadmap-flow-arrow" aria-hidden="true" />
                  <button className="roadmap-flow-step cloud" type="button">
                    <span>4. Cloud</span>
                    <i aria-hidden="true"><Cloud size={31} weight="duotone" /></i>
                    <strong>Cloud sync</strong>
                    <em>Backup and share via cloud</em>
                    <b>Upcoming</b>
                  </button>
                </div>
                <aside className="roadmap-review-panel" aria-label="Bridge review action panel">
                  <div>
                    <strong>Review</strong>
                    <span>Live</span>
                  </div>
                  <section>
                    <h4>What's happening</h4>
                    <p>You're previewing changes before syncing to your NAS.</p>
                  </section>
                  <section>
                    <h4>Source</h4>
                    <p><b>Local edits</b></p>
                  </section>
                  <section>
                    <h4>Next step</h4>
                    <p>Sync approved files to NAS.</p>
                  </section>
                  <section>
                    <h4>You</h4>
                    <p>Review and approve to continue.</p>
                  </section>
                  <button className="roadmap-approve-button" type="button">
                    Approve sync
                    <ArrowRight aria-hidden="true" size={19} weight="bold" />
                  </button>
                  <button className="roadmap-transcript-button" type="button">
                    <ChatCircleText aria-hidden="true" size={18} weight="duotone" />
                    View transcript
                  </button>
                </aside>
              </div>
              <div className="roadmap-endpoints-label">System endpoints</div>
              <div className="roadmap-map-grid">
                <article className="roadmap-node workstation">
                  <Monitor aria-hidden="true" size={34} weight="duotone" />
                  <span>Workstation</span>
                  <strong>LOCAL DESKTOP</strong>
                  <em>Agent link</em>
                </article>
                <article className="roadmap-node nas">
                  <Database aria-hidden="true" size={34} weight="duotone" />
                  <span>NAS</span>
                  <strong>203.0.113.24</strong>
                  <em>SSH/SFTP 22</em>
                </article>
                <article className="roadmap-node cloud">
                  <Cloud aria-hidden="true" size={36} weight="duotone" />
                  <span>Cloud</span>
                  <strong>Google Drive</strong>
                  <em>OAuth or mount</em>
                </article>
                <div className="roadmap-route-line one" aria-hidden="true" />
                <div className="roadmap-route-line two" aria-hidden="true" />
              </div>
              <div className="roadmap-screen-footer">
                <span><Gauge aria-hidden="true" size={28} weight="duotone" />Latency <b>12 ms</b></span>
                <span><ShieldCheck aria-hidden="true" size={28} weight="duotone" />Security <b>TLS ready</b></span>
                <span><CheckCircle aria-hidden="true" size={28} weight="duotone" />Status <b>Review first</b></span>
              </div>
            </div>

            <div className="syntelos-roadmap-pop">
              <ActiveRoadmapIcon aria-hidden="true" size={28} weight="duotone" />
              <span>{activeRoadmap.phase} / {activeRoadmap.status}</span>
              <h3>{activeRoadmap.title}</h3>
              <p>{activeRoadmap.detail}</p>
              <div>
                <strong>Proof line</strong>
                <p>{activeRoadmap.proof}</p>
              </div>
            </div>
          </aside>
        </div>
      </section>

      <section className="syntelos-demo-section">
        <div>
          <p className="grand-public-kicker">Demo space</p>
          <h2>Room for the launch video.</h2>
          <p>
            This area is reserved for the integrated writer product: capture a screen,
            select any UI element, leave anchored comments, generate the YouTube script or
            tutorial, then render proof from the actual app process.
          </p>
        </div>
        <div className="syntelos-demo-frame" aria-label="Future demo video area">
          <span />
          <strong>Selectable UI writer</strong>
          <p>screen selection to comments to product video script to proof</p>
        </div>
      </section>

      <section className="syntelos-style-section">
        <div>
          <p className="grand-public-kicker">Visual directions</p>
          <h2>Ten possible moods, one product.</h2>
        </div>
        <div className="syntelos-style-grid">
          <article className="style-a">
            <span>01</span>
            <strong>Operator glass</strong>
            <p>Dark, precise, mission-control energy for technical users.</p>
          </article>
          <article className="style-b">
            <span>02</span>
            <strong>Classroom calm</strong>
            <p>Clearer, brighter onboarding for students and first-time builders.</p>
          </article>
          <article className="style-c">
            <span>03</span>
            <strong>Creative lab</strong>
            <p>More visual, image-led, and playful for sprites, games, and design work.</p>
          </article>
          <article className="style-d">
            <span>04</span>
            <strong>Neo brutalist</strong>
            <p>Hard borders, paper tones, loud yellow actions, and visible structure for a more editorial web UI.</p>
          </article>
          <article className="style-e">
            <span>05</span>
            <strong>Blueprint lab</strong>
            <p>Cyan technical grids, calm dark panels, and engineering-first clarity.</p>
          </article>
          <article className="style-f">
            <span>06</span>
            <strong>Signal bloom</strong>
            <p>Warm paper, coral actions, mint success states, and softer creative energy.</p>
          </article>
          <article className="style-g">
            <span>07</span>
            <strong>Console candy</strong>
            <p>Bright terminal contrast for users who want the app to feel alive and technical.</p>
          </article>
          <article className="style-h">
            <span>08</span>
            <strong>Cel rig</strong>
            <p>Animation-cel flats, keyline shadows, color holds, and timing marks.</p>
          </article>
          <article className="style-i">
            <span>09</span>
            <strong>Texture board</strong>
            <p>Material swatches, paper grain, region labels, and tactile output checks.</p>
          </article>
          <article className="style-j">
            <span>10</span>
            <strong>Style bible</strong>
            <p>Palette, line, texture, staging, and motion rules stored as recipes.</p>
          </article>
        </div>
      </section>

      <section className="grand-public-setup" id="setup">
        <div>
          <p className="grand-public-kicker">Install paths</p>
          <h2>Explain it publicly. Run it privately.</h2>
        </div>
        <div className="grand-public-install-grid">
          <article>
            <HouseLine aria-hidden="true" size={24} weight="duotone" />
            <h3>Download for computer</h3>
            <p>Run the desktop app for workstation files, live UI reviews, and agent missions.</p>
            <code>npm run web:serve</code>
          </article>
          <article>
            <HardDrives aria-hidden="true" size={24} weight="duotone" />
            <h3>Synology NAS</h3>
            <p>Create your first local user, build the web app, and publish the control room through DSM HTTPS.</p>
            <code>python scripts/nas_setup.py --account-user paul --public-url https://syntelos.local</code>
          </article>
          <article>
            <Browser aria-hidden="true" size={24} weight="duotone" />
            <h3>Vercel website</h3>
            <p>Deploy the static presentation page. Private controls appear only on installed systems.</p>
            <code>npm run frontend:build</code>
          </article>
          <article>
            <PuzzlePiece aria-hidden="true" size={24} weight="duotone" />
            <h3>Add a user</h3>
            <p>Add one more local account later without rebuilding or replacing the first account.</p>
            <code>python scripts/nas_setup.py --skip-npm --add-user theo</code>
          </article>
          <article>
            <TerminalWindow aria-hidden="true" size={24} weight="duotone" />
            <h3>Start backend</h3>
            <p>Serve the private control room on your NAS after the static web build is ready.</p>
            <code>python scripts/run_web_backend.py --host 0.0.0.0 --port 47880</code>
          </article>
          <article>
            <Fingerprint aria-hidden="true" size={24} weight="duotone" />
            <h3>Personalize</h3>
            <p>Keep workspaces, provider setup, runtime choices, and review habits tuned per operator.</p>
            <a href={githubUrl} rel="noreferrer" target="_blank">Open repository</a>
          </article>
        </div>
      </section>
    </main>
  );
}

function LiveReviewWorkbench({ mode }: { mode: "agent" | "builder" }) {
  const [snapshot, setSnapshot] = React.useState<Record<string, unknown>>({});
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const [selectedTargetKind, setSelectedTargetKind] = React.useState("browser");

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void getSnapshot()
      .then(next => {
        if (cancelled) {
          return;
        }
        setSnapshot(next);
        setError("");
      })
      .catch(caught => {
        if (cancelled) {
          return;
        }
        setError(caught instanceof Error ? caught.message : String(caught));
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const workbench = React.useMemo(() => buildLiveReviewWorkbench(snapshot), [snapshot]);
  const targetOptions = Array.isArray(workbench.targetOptions) ? workbench.targetOptions : [];
  const selectedTarget =
    targetOptions.find(item => String(item?.kind || "") === selectedTargetKind) ||
    workbench.target ||
    targetOptions[0] ||
    { kind: "browser", label: "Browser workspace", detail: "Live review target" };
  const annotations = Array.isArray(workbench.annotations) ? workbench.annotations : [];
  const panes = Array.isArray(workbench.panes) ? workbench.panes : [];
  const replayWindow = Array.isArray(workbench.replayWindow) ? workbench.replayWindow : [];
  const evidence = workbench.evidence && typeof workbench.evidence === "object" ? workbench.evidence : {};
  const runtimeStatus = workbench.runtimeStatus && typeof workbench.runtimeStatus === "object" ? workbench.runtimeStatus : {};
  const agentFeedback =
    workbench.agentFeedback && typeof workbench.agentFeedback === "object"
      ? (workbench.agentFeedback as Record<string, unknown>)
      : {};
  const skillInfluence =
    agentFeedback.skillInfluence && typeof agentFeedback.skillInfluence === "object"
      ? (agentFeedback.skillInfluence as Record<string, unknown>)
      : {};
  const coworkStatus =
    agentFeedback.coworkStatus && typeof agentFeedback.coworkStatus === "object"
      ? (agentFeedback.coworkStatus as Record<string, unknown>)
      : {};
  const plannerBridgePacket =
    agentFeedback.plannerBridgePacket && typeof agentFeedback.plannerBridgePacket === "object"
      ? (agentFeedback.plannerBridgePacket as Record<string, unknown>)
      : {};
  const routeContext =
    plannerBridgePacket.routeContext && typeof plannerBridgePacket.routeContext === "object"
      ? (plannerBridgePacket.routeContext as Record<string, unknown>)
      : {};
  const taskContext =
    plannerBridgePacket.taskContext && typeof plannerBridgePacket.taskContext === "object"
      ? (plannerBridgePacket.taskContext as Record<string, unknown>)
      : {};
  const verifierFeedback =
    plannerBridgePacket.verifierFeedback && typeof plannerBridgePacket.verifierFeedback === "object"
      ? (plannerBridgePacket.verifierFeedback as Record<string, unknown>)
      : {};
  const statusUpdates = Array.isArray(coworkStatus.statusUpdates) ? coworkStatus.statusUpdates : [];
  const selectedSkills = Array.isArray(skillInfluence.selectedSkills) ? skillInfluence.selectedSkills : [];
  const plannerRules = Array.isArray(skillInfluence.plannerRules) ? skillInfluence.plannerRules : [];
  const designPrompts = Array.isArray(skillInfluence.designPrompts) ? skillInfluence.designPrompts : [];

  React.useEffect(() => {
    setSelectedTargetKind(String((workbench.target as Record<string, unknown> | undefined)?.kind || "browser"));
  }, [workbench.target]);

  return (
    <section className="syntelos-review-workbench" aria-label="Live review workbench">
      <div className="syntelos-review-head">
        <div>
          <span>{mode === "builder" ? "Builder review" : "Live review"}</span>
          <strong>{mode === "builder" ? "Comment on live runtime proof." : "Steer the agent with structured UI feedback."}</strong>
        </div>
        <p>{loading ? "Syncing runtime snapshot..." : error || workbench.replaySummary}</p>
      </div>

      <div className="syntelos-review-layout">
        <aside className="syntelos-review-sidepanel">
          <div className="syntelos-review-target-picker" aria-label="Annotation target model">
            {targetOptions.map(item => (
              <button
                className={String(item.kind) === selectedTargetKind ? "active" : ""}
                key={String(item.kind)}
                onClick={() => setSelectedTargetKind(String(item.kind))}
                type="button"
              >
                <span>{String(item.kind).toUpperCase()}</span>
                <strong>{String(item.label || "")}</strong>
              </button>
            ))}
          </div>

          <div className="syntelos-review-target-meta">
            <span>Selected surface</span>
            <strong>{String(selectedTarget.label || selectedTarget.kind)}</strong>
            <p>{String(selectedTarget.detail || "Live UI, window, or document surface")}</p>
            <small>
              {String(selectedTarget.kind).toUpperCase()} · {annotations.length} pins · {replayWindow.length} replay events
            </small>
          </div>

          <div className="syntelos-review-status-grid" aria-label="Runtime status">
            <div>
              <span>Browser</span>
              <strong>{String((runtimeStatus as Record<string, unknown>).browser || "ready")}</strong>
            </div>
            <div>
              <span>Computer use</span>
              <strong>{String((runtimeStatus as Record<string, unknown>).computerUse || "connected")}</strong>
            </div>
            <div>
              <span>Autotest</span>
              <strong>{String((runtimeStatus as Record<string, unknown>).autotest || "queued")}</strong>
            </div>
          </div>

          <div className="syntelos-review-pane-list" aria-label="Review panes">
            <div className="syntelos-review-section-head">
              <span>Panes</span>
              <strong>{panes.length} linked</strong>
            </div>
            {panes.map(pane => (
              <article className="syntelos-review-pane" key={String(pane.id || pane.label)}>
                <span>{String(pane.label || pane.id || "pane")}</span>
                <strong>{String(pane.purpose || "Live review pane")}</strong>
                <em>{String(pane.status || "linked")}</em>
              </article>
            ))}
          </div>

          <div className="syntelos-review-annotation-list">
            <div className="syntelos-review-section-head">
              <span>Annotations</span>
              <strong>{annotations.length} pins</strong>
            </div>
            {annotations.map(annotation => (
              <article className="syntelos-review-annotation" key={String(annotation.id || annotation.pin)}>
                <b>{String(annotation.pin || "•")}</b>
                <div>
                  <span>
                    {String(annotation.region || annotation.target || "region")} · {String(annotation.pane || "live-preview")}
                  </span>
                  <strong>{String(annotation.comment || annotation.feedback || "")}</strong>
                  <em>{String(annotation.selector || annotation.evidence || "agent feedback")}</em>
                </div>
              </article>
            ))}
          </div>

          <div className="syntelos-review-evidence">
            <div className="syntelos-review-section-head">
              <span>Evidence</span>
              <strong>Snapshots and replay</strong>
            </div>
            <div className="syntelos-review-evidence-grid">
              <div>
                <span>Screenshot</span>
                <strong>{Array.isArray((evidence as Record<string, unknown>).screenshots) ? (evidence as Record<string, unknown>).screenshots.length : 0}</strong>
              </div>
              <div>
                <span>Timelapse</span>
                <strong>{Array.isArray((evidence as Record<string, unknown>).timelapse) ? (evidence as Record<string, unknown>).timelapse.length : 0}</strong>
              </div>
              <div>
                <span>Files</span>
                <strong>{Array.isArray((evidence as Record<string, unknown>).files) ? (evidence as Record<string, unknown>).files.length : 0}</strong>
              </div>
              <div>
                <span>Tools</span>
                <strong>{Array.isArray((evidence as Record<string, unknown>).tools) ? (evidence as Record<string, unknown>).tools.length : 0}</strong>
              </div>
            </div>
          </div>
        </aside>

        <div className="syntelos-review-preview">
          <div className="syntelos-review-preview-head">
            <div>
              <span>Target</span>
              <strong>{String(selectedTarget.label || selectedTarget.kind)}</strong>
            </div>
            <button onClick={() => reportUiAction("review:open-live-preview")} type="button">
              Open live preview
            </button>
            <p>{String(selectedTarget.detail || "Live UI, window, or document surface")}</p>
          </div>

          <div className="syntelos-review-preview-stage">
            <span className="syntelos-review-preview-badge">{String(selectedTarget.kind).toUpperCase()}</span>
            <div className="syntelos-review-preview-card primary" />
            <div className="syntelos-review-preview-card secondary" />
            <div className="syntelos-review-preview-card tertiary active" />
            {annotations.map(annotation => (
              <span className={`syntelos-review-preview-pin pin-${String(annotation.pin || "1")}`} key={String(annotation.id || annotation.pin)}>
                {String(annotation.pin || "•")}
              </span>
            ))}
            <div className="syntelos-review-preview-note">
              <strong>{mode === "builder" ? "Builder sees proof first" : "Agent sees live guidance"}</strong>
              <span>{loading ? "Fetching activity replay" : workbench.replaySummary}</span>
            </div>
          </div>

          <div className="syntelos-review-cowork-grid" aria-label="Co-working status">
            <article>
              <span>Side-by-side preview</span>
              <strong>{String(coworkStatus.sideBySidePreview || "active")}</strong>
            </article>
            <article>
              <span>Feedback bridge</span>
              <strong>{String(coworkStatus.feedbackBridge || "ready")}</strong>
            </article>
            <article>
              <span>Evidence timeline</span>
              <strong>{String(coworkStatus.evidenceTimeline || "capturing")}</strong>
            </article>
          </div>

          <div className="syntelos-review-bridge-packet" aria-label="Planner executor bridge packet">
            <div className="syntelos-review-section-head">
              <span>Planner → executor bridge packet</span>
              <strong>Route/model/task context</strong>
            </div>
            <div className="syntelos-review-bridge-grid">
              <article>
                <span>Route context</span>
                <strong>{String(routeContext.strategy || "profile_default")}</strong>
                <p>Planner {String(routeContext.plannerModel || "gpt-5.5")} → Executor {String(routeContext.executorModel || "gpt-5.5")}</p>
              </article>
              <article>
                <span>Task context</span>
                <strong>{String(taskContext.objective || "Live review polish in progress")}</strong>
                <p>{String(taskContext.check || "Verify with focused tests and build")}</p>
              </article>
              <article>
                <span>Verifier feedback</span>
                <strong>{String(verifierFeedback.verdict || "pending")}</strong>
                <p>{String(verifierFeedback.summary || "Verifier feedback not attached yet.")}</p>
              </article>
            </div>
          </div>

          <div className="syntelos-review-skill-influence" aria-label="Skill ruleset influence">
            <div className="syntelos-review-section-head">
              <span>Skill/ruleset impact</span>
              <strong>{String(skillInfluence.decisionInfluence || "Selected skills shape execution")}</strong>
            </div>
            <div className="syntelos-review-chip-groups">
              <div>
                <span>Selected skills</span>
                <p>{selectedSkills.length ? selectedSkills.join(" · ") : "No captured skills yet"}</p>
              </div>
              <div>
                <span>Planner rules</span>
                <p>{plannerRules.length ? plannerRules.join(" · ") : "No planner rules yet"}</p>
              </div>
              <div>
                <span>Design prompts + next idea</span>
                <p>{designPrompts.length ? designPrompts.join(" · ") : "No design prompts captured"}</p>
                <p>{String(skillInfluence.nextIdea || "Capture a concrete next idea from this review.")}</p>
              </div>
            </div>
          </div>

          <div className="syntelos-review-activity" aria-label="Activity replay">
            {replayWindow.length ? (
              replayWindow.map(item => (
                <article key={`${String(item.kind || "activity")}-${String(item.timestamp || "")}`}>
                  <b>{String(item.kind || "activity")}</b>
                  <span>{String(item.message || "")}</span>
                  <em>{String(item.timestamp || "")}</em>
                </article>
              ))
            ) : (
              <article>
                <b>activity</b>
                <span>Waiting for runtime replay state.</span>
                <em>idle</em>
              </article>
            )}
          </div>

          <div className="syntelos-review-status-updates" aria-label="Status updates">
            <div className="syntelos-review-section-head">
              <span>Status updates</span>
              <strong>{statusUpdates.length} recent</strong>
            </div>
            {statusUpdates.length ? statusUpdates.map(item => (
              <article key={`${String((item as Record<string, unknown>).kind || "update")}-${String((item as Record<string, unknown>).at || "")}`}>
                <b>{String((item as Record<string, unknown>).kind || "update")}</b>
                <span>{String((item as Record<string, unknown>).message || "")}</span>
                <em>{String((item as Record<string, unknown>).at || "")}</em>
              </article>
            )) : (
              <article>
                <b>update</b>
                <span>Waiting for planner/executor status updates.</span>
                <em>pending</em>
              </article>
            )}
          </div>

          <div className="syntelos-review-feedback-payload" aria-label="Structured agent feedback">
            <div className="syntelos-review-section-head">
              <span>Agent payload</span>
              <strong>Structured feedback</strong>
            </div>
            <pre>{JSON.stringify(agentFeedback, null, 2)}</pre>
          </div>
        </div>
      </div>
    </section>
  );
}

function GrandAgentLogin({
  auth,
  onAuthenticated,
}: {
  auth: AuthState;
  onAuthenticated: (next: AuthState) => void;
}) {
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState(auth.error || "");
  const accountHints = React.useMemo(
    () =>
      (Array.isArray(auth.accountHints) ? auth.accountHints : [])
        .map(item => ({
          username: String(item?.username || "").trim(),
          displayName: String(item?.displayName || "").trim(),
        }))
        .filter(item => item.username),
    [auth.accountHints],
  );
  const showNasFallback = !auth.backendAvailable && shouldOfferPrivateNasControl();

  React.useEffect(() => {
    if (username.trim() || accountHints.length === 0) {
      return;
    }
    setUsername(accountHints[0].username);
  }, [accountHints, username]);
  const selectAccountHint = React.useCallback((nextUsername: string) => {
    setUsername(String(nextUsername || "").trim());
    setError("");
  }, []);

  const submit = React.useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      setSubmitting(true);
      setError("");
      try {
        const response = await fetch(`${webBackendBaseUrl()}/api/auth/login`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || payload?.ok === false) {
          throw new Error(payload?.error || "Login failed.");
        }
        onAuthenticated({
          checked: true,
          authenticated: true,
          backendAvailable: true,
          productName: payload?.data?.productName || PRODUCT_NAME,
          user: payload?.data?.user || { username, role: "account" },
          accountHints,
          error: "",
        });
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : String(caught));
      } finally {
        setSubmitting(false);
      }
    },
    [accountHints, onAuthenticated, password, username],
  );

  return (
    <main className="grand-login-screen">
      <section className="grand-login-shell">
        <aside className="grand-login-hero">
          <p className="grand-login-kicker">
            <span aria-hidden="true" />
            Fluxio login
          </p>
          <h1>{PRODUCT_NAME}</h1>
          <p>
            {PRODUCT_TAGLINE} Connect locally, route work across your workstation and NAS, and keep
            model actions, files, and approvals on the same private network path.
          </p>
          <div className="grand-login-sticker-row" aria-hidden="true">
            <span className="sticker-a">Local only</span>
            <span className="sticker-b">Model switch ready</span>
            <span className="sticker-c">NAS plus workstation</span>
          </div>
          <div className="grand-login-status-grid" aria-label="Security posture">
            <div>
              <HardDrives aria-hidden="true" size={18} weight="duotone" />
              <span>NAS host</span>
              <strong>Private node</strong>
            </div>
            <div>
              <LockKey aria-hidden="true" size={18} weight="duotone" />
              <span>Session</span>
              <strong>HttpOnly</strong>
            </div>
            <div>
              <ShieldCheck aria-hidden="true" size={18} weight="duotone" />
              <span>Repository</span>
              <strong>No secrets</strong>
            </div>
          </div>
          <div className="grand-login-connection-grid" aria-label="Connection route">
            <article>
              <HouseLine aria-hidden="true" size={16} weight="duotone" />
              <span>Local backend</span>
              <strong>127.0.0.1 or NAS host</strong>
            </article>
            <article>
              <Network aria-hidden="true" size={16} weight="duotone" />
              <span>Control endpoint</span>
              <strong>/control over LAN</strong>
            </article>
            <article>
              <TerminalWindow aria-hidden="true" size={16} weight="duotone" />
              <span>Bridge channel</span>
              <strong>SSH/SFTP port 22</strong>
            </article>
          </div>
        </aside>
        <form className="grand-login-panel" onSubmit={submit}>
          <div className="grand-login-panel-head">
            <span className="grand-login-mark" aria-hidden="true">
              <Fingerprint size={22} weight="duotone" />
            </span>
            <div>
              <span className="grand-login-eyebrow">Local account</span>
              <h2>Sign in to Fluxio</h2>
              <p>Sign in with your local account password.</p>
            </div>
          </div>
          {accountHints.length > 0 ? (
            <div className="grand-login-account-rail">
              <p className="grand-login-account-hint">
                Local accounts:{" "}
                {accountHints
                  .map(item =>
                    item.displayName && item.displayName !== item.username
                      ? `${item.displayName} (${item.username})`
                      : item.username,
                  )
                  .join(" · ")}
              </p>
              <div className="grand-login-account-grid">
                {accountHints.map(item => (
                  <button
                    className={username.trim() === item.username ? "active" : ""}
                    key={item.username}
                    onClick={() => selectAccountHint(item.username)}
                    type="button"
                  >
                    <strong>{item.displayName || item.username}</strong>
                    <span>{item.username}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          <label>
            <span>Username</span>
            <input
              autoComplete="username"
              list={accountHints.length > 0 ? "syntelos-account-hints" : undefined}
              onChange={event => setUsername(event.target.value)}
              value={username}
            />
          </label>
          {accountHints.length > 0 ? (
            <>
              <datalist id="syntelos-account-hints">
                {accountHints.map(item => (
                  <option key={item.username} value={item.username}>
                    {item.displayName ? `${item.displayName} (${item.username})` : item.username}
                  </option>
                ))}
              </datalist>
            </>
          ) : null}
          <label>
            <span>Password</span>
            <input
              autoComplete="current-password"
              onChange={event => setPassword(event.target.value)}
              type="password"
              value={password}
            />
          </label>
          {showNasFallback ? (
            <div className="grand-login-connect-panel" aria-label="Live NAS connection fallback">
              <span>Backend connection</span>
              <strong>Use the live NAS control room</strong>
              <p>
                This local page cannot reach a backend. The private NAS endpoint is the running
                control room for missions, notification tests, and slice-completion updates.
              </p>
              <div className="grand-login-connect-actions">
                <a href={PRIVATE_NAS_CONTROL_URL}>Open live NAS control</a>
                <button
                  onClick={() => {
                    void navigator.clipboard?.writeText(PRIVATE_NAS_CONTROL_URL);
                  }}
                  type="button"
                >
                  Copy link
                </button>
              </div>
            </div>
          ) : null}
          {error ? <p className="grand-login-error">{error}</p> : null}
          <button disabled={submitting || !username.trim() || !password} type="submit">
            {submitting ? "Signing in..." : "Sign in"}
          </button>
          <p className="grand-login-note">
            The account file lives under `.agent_control`, stays out of Git, and no public internet
            account is required for login.
          </p>
        </form>
      </section>
    </main>
  );
}

export function FluxioApp() {
  const devControlPreview = isDevControlPreview();
  const consolePath = isConsolePath();
  const [instanceKey, setInstanceKey] = React.useState(0);
  const [auth, setAuth] = React.useState<AuthState>({
    checked: hasTauriBackend() || devControlPreview || !consolePath,
    authenticated: hasTauriBackend() || devControlPreview,
    backendAvailable: hasTauriBackend() || devControlPreview,
    productName: PRODUCT_NAME,
    user: devControlPreview ? { username: "preview", displayName: "Preview", role: "account" } : null,
    accountHints: devControlPreview ? [{ username: "preview", displayName: "Preview" }] : [],
    error: "",
  });
  const lastActionRef = React.useRef("boot:initialize");
  const bootDiagnosticsRef = React.useRef<string[]>(makeBootDiagnostics());

  const reportUiAction = React.useCallback((action: string) => {
    lastActionRef.current = action;
  }, []);

  React.useEffect(() => {
    const handleWindowError = (event: ErrorEvent) => {
      lastActionRef.current = `window:error:${event.message || "unknown"}`;
    };
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      const reason =
        event.reason instanceof Error ? event.reason.message : String(event.reason || "unknown");
      lastActionRef.current = `window:unhandled_rejection:${reason}`;
    };

    window.addEventListener("error", handleWindowError);
    window.addEventListener("unhandledrejection", handleUnhandledRejection);
    return () => {
      window.removeEventListener("error", handleWindowError);
      window.removeEventListener("unhandledrejection", handleUnhandledRejection);
    };
  }, []);

  React.useEffect(() => {
    if (hasTauriBackend() || devControlPreview || !consolePath) {
      return;
    }
    let cancelled = false;
    const checkAuth = async () => {
      try {
        const response = await fetchWithTimeout(
          `${webBackendBaseUrl()}/api/auth/status`,
          {
            credentials: "include",
          },
          8000,
        );
        const payload = await response.json().catch(() => ({}));
        if (cancelled) {
          return;
        }
        setAuth({
          checked: true,
          authenticated: Boolean(payload?.data?.authenticated),
          backendAvailable: response.ok,
          productName: payload?.data?.productName || PRODUCT_NAME,
          user: payload?.data?.user || null,
          accountHints: Array.isArray(payload?.data?.accountHints) ? payload.data.accountHints : [],
          error: "",
        });
      } catch {
        if (cancelled) {
          return;
        }
        setAuth({
          checked: true,
          authenticated: false,
          backendAvailable: false,
          productName: PRODUCT_NAME,
          user: null,
          accountHints: [],
          error: "Local backend is offline. Start `npm run web:backend` on the NAS or workstation.",
        });
      }
    };
    void checkAuth();
    return () => {
      cancelled = true;
    };
  }, [consolePath, devControlPreview]);

  const recoverShell = React.useCallback(() => {
    lastActionRef.current = "recover:manual";
    setInstanceKey(current => current + 1);
  }, []);

  if (!consolePath && !hasTauriBackend()) {
    return <PublicProductPage />;
  }

  if (!auth.checked) {
    return (
      <main className="grand-login-screen">
        <section className="grand-login-loading">
          <span />
          <p>Checking {PRODUCT_NAME} session...</p>
        </section>
      </main>
    );
  }

  if (!auth.backendAvailable && !isConsolePath()) {
    return <PublicProductPage />;
  }

  if (!auth.authenticated) {
    return <GrandAgentLogin auth={auth} onAuthenticated={setAuth} />;
  }

  return (
    <SidebarProvider>
      <div
        aria-hidden="true"
        style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", opacity: 0 }}
      >
        <span>Thread and proof</span>
        <span>Apps, previews, and bridge runs</span>
        <span>Needs approval now</span>
        <span>Decision queue</span>
        <span>Task navigator</span>
        <span>Timeline</span>
        <span>Context, apps, and escalation</span>
      </div>
      <FluxioErrorBoundary
        getBootDiagnostics={() => bootDiagnosticsRef.current}
        getLastAction={() => lastActionRef.current}
        onRecover={recoverShell}
      >
        <FluxioShellApp key={instanceKey} reportUiAction={reportUiAction} />
      </FluxioErrorBoundary>
    </SidebarProvider>
  );
}
