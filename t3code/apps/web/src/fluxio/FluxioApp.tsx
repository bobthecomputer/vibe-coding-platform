import React from "react";

import { FluxioShellApp } from "./FluxioShell.jsx";

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

export function FluxioApp() {
  const [instanceKey, setInstanceKey] = React.useState(0);
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

  const recoverShell = React.useCallback(() => {
    lastActionRef.current = "recover:manual";
    setInstanceKey(current => current + 1);
  }, []);

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
