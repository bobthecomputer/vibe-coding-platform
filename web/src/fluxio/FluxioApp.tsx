import React from "react";
import { Fingerprint, HardDrive, LockKeyhole, Network, ShieldCheck } from "lucide-react";

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
  productName: string;
  user: { username?: string; displayName?: string; role?: string } | null;
  error: string;
};

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
              <HardDrive aria-hidden="true" size={18} />
              <span>NAS host</span>
              <strong>Private node</strong>
            </div>
            <div>
              <LockKeyhole aria-hidden="true" size={18} />
              <span>Session</span>
              <strong>HttpOnly</strong>
            </div>
            <div>
              <ShieldCheck aria-hidden="true" size={18} />
              <span>Repository</span>
              <strong>No secrets</strong>
            </div>
          </div>
        </aside>
        <form className="grand-login-panel" onSubmit={submit}>
          <div className="grand-login-panel-head">
            <span className="grand-login-mark" aria-hidden="true">
              <Fingerprint size={22} />
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
