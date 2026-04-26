import React from "react";
import {
  ArrowRight,
  BracketsCurly,
  Browser,
  ChatCircleText,
  CheckCircle,
  Code,
  Cpu,
  Cube,
  Database,
  Fingerprint,
  GithubLogo,
  HardDrives,
  HouseLine,
  LockKey,
  Network,
  PuzzlePiece,
  ShieldCheck,
  TerminalWindow,
} from "@phosphor-icons/react";

import topologyImage from "./assets/grand-agent-topology.png";
import { FluxioShellApp } from "./FluxioShell.jsx";

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
    console.error("Fluxio UI crashed", {
      error,
      info,
      lastAction: this.props.getLastAction(),
      capturedAt: new Date().toISOString(),
    });
  }

  handleRecover = () => {
    this.setState({ error: null, capturedAt: "" });
    this.props.onRecover();
  };

  render() {
    if (!this.state.error) {
      return this.props.children;
    }

    return (
      <main className="fluxio-error-screen">
        <section className="fluxio-error-panel">
          <p className="eyebrow">Recoverable UI error</p>
          <h1>Fluxio hit a render failure.</h1>
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
            <button className="action-btn" onClick={() => window.location.reload()} type="button">
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
  error: string;
};

function PublicProductPage() {
  const githubUrl = "https://github.com/bobthecomputer/vibe-coding-platform";
  const agents = [
    ["General Agent", "Active"],
    ["Research Agent", "Active"],
    ["Code Agent", "Idle"],
    ["Data Agent", "Active"],
    ["NAS Jobs", "Running"],
  ];
  const logs = [
    ["10:21:25", "INFO", "Scheduler: local backup completed"],
    ["10:21:24", "INFO", "General Agent answered in 1.24s"],
    ["10:21:24", "INFO", "Vector index ready"],
    ["10:21:23", "WARN", "Disk usage is at 78% on volume1"],
  ];

  return (
    <main className="grand-public-page">
      <nav className="grand-public-nav" aria-label="Grand Agent">
        <a className="grand-public-brand" href="/">
          Grand Agent
        </a>
        <div className="grand-public-nav-links">
          <a href="#overview">Overview</a>
          <a href="#setup">Setup</a>
          <a href="#console">Console</a>
        </div>
        <div className="grand-public-nav-actions">
          <a className="grand-public-ghost" href={githubUrl} rel="noreferrer" target="_blank">
            <GithubLogo aria-hidden="true" size={17} weight="bold" />
            View GitHub
          </a>
          <a className="grand-public-primary" href="/control">
            Open NAS Console
          </a>
        </div>
      </nav>

      <section className="grand-public-hero" id="overview">
        <div className="grand-public-copy">
          <p className="grand-public-kicker">Open-source local agent control</p>
          <h1>Grand Agent</h1>
          <p className="grand-public-lede">
            Install on your computer or NAS. Keep agent messages, provider setup, jobs, and
            runtime state under your own roof instead of inside a hosted dashboard.
          </p>
          <div className="grand-public-actions">
            <a className="grand-public-primary" href={githubUrl} rel="noreferrer" target="_blank">
              <GithubLogo aria-hidden="true" size={18} weight="bold" />
              View GitHub
            </a>
            <a className="grand-public-ghost" href="#setup">
              Install on NAS
              <ArrowRight aria-hidden="true" size={16} weight="bold" />
            </a>
          </div>
          <div className="grand-public-proof" aria-label="Project properties">
            <div>
              <LockKey aria-hidden="true" size={22} weight="duotone" />
              <strong>Local first</strong>
              <span>No hosted control plane required.</span>
            </div>
            <div>
              <HardDrives aria-hidden="true" size={22} weight="duotone" />
              <strong>NAS ready</strong>
              <span>Run it on Synology or a normal server.</span>
            </div>
            <div>
              <PuzzlePiece aria-hidden="true" size={22} weight="duotone" />
              <strong>Extensible</strong>
              <span>Skills, apps, models, and bridges.</span>
            </div>
          </div>
        </div>

        <section className="grand-console-preview" id="console" aria-label="Grand Agent console preview">
          <div className="grand-console-windowbar">
            <span />
            <span />
            <span />
            <strong>nas.local:47880/control</strong>
          </div>
          <div className="grand-console-layout">
            <aside className="grand-console-rail">
              <div className="grand-console-rail-head">
                <strong>Grand Agent</strong>
                <span>Private node</span>
              </div>
              <div className="grand-console-agent-list">
                {agents.map(([name, state]) => (
                  <div className="grand-console-agent" key={name} data-state={state}>
                    <Cube aria-hidden="true" size={17} weight="duotone" />
                    <span>{name}</span>
                    <i>{state}</i>
                  </div>
                ))}
              </div>
              <div className="grand-console-menu">
                <span><ChatCircleText aria-hidden="true" size={16} />Console</span>
                <span><TerminalWindow aria-hidden="true" size={16} />Jobs</span>
                <span><Database aria-hidden="true" size={16} />Models</span>
                <span><BracketsCurly aria-hidden="true" size={16} />Skills</span>
              </div>
            </aside>
            <div className="grand-console-main">
              <header>
                <div>
                  <strong>General Agent</strong>
                  <span>Active</span>
                </div>
                <button type="button">New Thread</button>
              </header>
              <div className="grand-console-thread">
                <div className="grand-message user">
                  <strong>You</strong>
                  <p>Summarize system status and recent jobs.</p>
                </div>
                <div className="grand-message agent">
                  <strong>General Agent</strong>
                  <p>All core services are healthy. 3 jobs completed today. No provider errors detected.</p>
                </div>
              </div>
              <div className="grand-console-composer">
                <span>Message General Agent...</span>
                <button aria-label="Send preview message" type="button">
                  <ArrowRight aria-hidden="true" size={16} weight="bold" />
                </button>
              </div>
              <div className="grand-console-logs">
                <strong>Runtime logs</strong>
                {logs.map(([time, level, text]) => (
                  <div key={`${time}-${text}`}>
                    <span>{time}</span>
                    <i>{level}</i>
                    <p>{text}</p>
                  </div>
                ))}
              </div>
            </div>
            <aside className="grand-console-side">
              <div>
                <strong>System status</strong>
                <span><Cpu aria-hidden="true" size={15} />CPU 18%</span>
                <span><Database aria-hidden="true" size={15} />Disk 78%</span>
                <span><Network aria-hidden="true" size={15} />Network 1.2 MB/s</span>
              </div>
              <div>
                <strong>Providers</strong>
                <span>Local LLM <i>Online</i></span>
                <span>Vector DB <i>Online</i></span>
                <span>Browser <i>Online</i></span>
              </div>
              <div>
                <strong>Secure local admin</strong>
                <p>Session is local. Secrets stay on this system.</p>
              </div>
            </aside>
          </div>
        </section>
      </section>

      <section className="grand-public-setup" id="setup">
        <div>
          <p className="grand-public-kicker">Install paths</p>
          <h2>Use the public page to understand it. Use the NAS console to run it.</h2>
        </div>
        <div className="grand-public-install-grid">
          <article>
            <HouseLine aria-hidden="true" size={24} weight="duotone" />
            <h3>Computer</h3>
            <p>Run the desktop/local stack for your own workstation and agent experiments.</p>
            <code>npm run web:serve</code>
          </article>
          <article>
            <HardDrives aria-hidden="true" size={24} weight="duotone" />
            <h3>NAS</h3>
            <p>Generate a local admin password, build the web app, and serve the private console.</p>
            <code>npm run nas:setup</code>
          </article>
          <article>
            <Browser aria-hidden="true" size={24} weight="duotone" />
            <h3>Public website</h3>
            <p>Deploy the static product page. The private controls only appear on installed systems.</p>
            <code>npm run frontend:build</code>
          </article>
          <article>
            <Code aria-hidden="true" size={24} weight="duotone" />
            <h3>Open source</h3>
            <p>Read the code, fork it, and adapt the local bridge without publishing credentials.</p>
            <a href={githubUrl} rel="noreferrer" target="_blank">Open repository</a>
          </article>
        </div>
      </section>
    </main>
  );
}

function GrandAgentLogin({
  auth,
  onAuthenticated,
}: {
  auth: AuthState;
  onAuthenticated: (next: AuthState) => void;
}) {
  const [username, setUsername] = React.useState("admin");
  const [password, setPassword] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState(auth.error || "");

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
          productName: payload?.data?.productName || "Grand Agent",
          user: payload?.data?.user || { username, role: "admin" },
          error: "",
        });
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : String(caught));
      } finally {
        setSubmitting(false);
      }
    },
    [onAuthenticated, password, username],
  );

  return (
    <main className="grand-login-screen">
      <section className="grand-login-shell">
        <aside className="grand-login-hero">
          <p className="grand-login-kicker">
            <span aria-hidden="true" />
            Systemology login
          </p>
          <h1>Grand Agent</h1>
          <p>
            Your private control layer for local agents, NAS bridge jobs, runtime setup, and
            provider readiness. Credentials stay on the host, outside the open-source branch.
          </p>
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
        </aside>
        <form className="grand-login-panel" onSubmit={submit}>
          <div className="grand-login-panel-head">
            <span className="grand-login-mark" aria-hidden="true">
              <Fingerprint size={22} weight="duotone" />
            </span>
            <div>
              <span className="grand-login-eyebrow">Administrator</span>
              <h2>Enter the control room</h2>
              <p>Use the password generated during NAS setup.</p>
            </div>
          </div>
          <div className="grand-login-topology" aria-label="Local agent topology preview">
            <img alt="" src={topologyImage} />
            <div>
              <Network aria-hidden="true" size={17} />
              <span>Local agent topology</span>
            </div>
          </div>
          <label>
            <span>Username</span>
            <input
              autoComplete="username"
              onChange={event => setUsername(event.target.value)}
              value={username}
            />
          </label>
          <label>
            <span>Password</span>
            <input
              autoComplete="current-password"
              onChange={event => setPassword(event.target.value)}
              type="password"
              value={password}
            />
          </label>
          {error ? <p className="grand-login-error">{error}</p> : null}
          <button disabled={submitting || !username.trim() || !password} type="submit">
            {submitting ? "Checking..." : "Enter Grand Agent"}
          </button>
          <p className="grand-login-note">
            The admin file lives under `.agent_control` and stays out of Git.
          </p>
        </form>
      </section>
    </main>
  );
}

export function FluxioApp() {
  const [instanceKey, setInstanceKey] = React.useState(0);
  const [auth, setAuth] = React.useState<AuthState>({
    checked: hasTauriBackend(),
    authenticated: hasTauriBackend(),
    backendAvailable: hasTauriBackend(),
    productName: "Grand Agent",
    user: null,
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
    if (hasTauriBackend()) {
      return;
    }
    let cancelled = false;
    const checkAuth = async () => {
      try {
        const response = await fetch(`${webBackendBaseUrl()}/api/auth/status`, {
          credentials: "include",
        });
        const payload = await response.json().catch(() => ({}));
        if (cancelled) {
          return;
        }
        setAuth({
          checked: true,
          authenticated: Boolean(payload?.data?.authenticated),
          backendAvailable: response.ok,
          productName: payload?.data?.productName || "Grand Agent",
          user: payload?.data?.user || null,
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
          productName: "Grand Agent",
          user: null,
          error: "Local backend is offline. Start `npm run web:backend` on the NAS or workstation.",
        });
      }
    };
    void checkAuth();
    return () => {
      cancelled = true;
    };
  }, []);

  const recoverShell = React.useCallback(() => {
    lastActionRef.current = "recover:manual";
    setInstanceKey(current => current + 1);
  }, []);

  if (!auth.checked) {
    return (
      <main className="grand-login-screen">
        <section className="grand-login-loading">
          <span />
          <p>Checking Grand Agent session...</p>
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
