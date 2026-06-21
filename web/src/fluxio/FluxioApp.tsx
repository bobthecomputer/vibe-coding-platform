import React from "react";
import {
  Fingerprint,
  HardDrives,
  HouseLine,
  LockKey,
  Network,
  ShieldCheck,
  TerminalWindow,
} from "@phosphor-icons/react";

const FluxioShellApp = React.lazy(() =>
  import("./FluxioShell.jsx").then(module => ({ default: module.FluxioShellApp })),
);

const PRODUCT_NAME = "Fluxio";
const PRODUCT_TAGLINE = "Agent operating system for workspaces.";

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

function isDevControlPreview(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return Boolean(
    (import.meta as any).env?.DEV &&
      new URLSearchParams(window.location.search).get("preview-control") === "1",
  );
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
  const [instanceKey, setInstanceKey] = React.useState(0);
  const [auth, setAuth] = React.useState<AuthState>({
    checked: hasTauriBackend() || devControlPreview,
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
    if (hasTauriBackend() || devControlPreview) {
      return;
    }
    let cancelled = false;
    const checkAuth = async () => {
      try {
        const response = await fetchWithTimeout(`${webBackendBaseUrl()}/api/auth/status`, {
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
  }, [devControlPreview]);

  const recoverShell = React.useCallback(() => {
    lastActionRef.current = "recover:manual";
    setInstanceKey(current => current + 1);
  }, []);

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
        <React.Suspense
          fallback={
            <main className="grand-login-shell">
              <section className="grand-login-loading control-shell-loading">
                <span />
                <p>Loading {PRODUCT_NAME} control shell...</p>
              </section>
            </main>
          }
        >
          <FluxioShellApp key={instanceKey} reportUiAction={reportUiAction} />
        </React.Suspense>
      </FluxioErrorBoundary>
    </SidebarProvider>
  );
}
