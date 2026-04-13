import React from "react";

import { FluxioDesktopApp } from "../../../../../desktop-ui/FluxioDesktop.jsx";

function SidebarProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export function FluxioApp() {
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
      <FluxioDesktopApp />
    </SidebarProvider>
  );
}
