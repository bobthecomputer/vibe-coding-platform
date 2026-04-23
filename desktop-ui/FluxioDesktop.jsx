// Legacy compatibility wrapper.
// The real shell now lives in web/src/fluxio/FluxioShell.jsx.
import { FluxioShellApp } from "../web/src/fluxio/FluxioShell.jsx";

export function FluxioDesktopApp() {
  return <FluxioShellApp />;
}
