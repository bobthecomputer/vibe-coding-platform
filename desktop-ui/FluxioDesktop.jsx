// Legacy compatibility wrapper.
// The real shell now lives in t3code/apps/web/src/fluxio/FluxioShell.jsx.
import { FluxioShellApp } from "../t3code/apps/web/src/fluxio/FluxioShell.jsx";

export function FluxioDesktopApp() {
  return <FluxioShellApp />;
}
