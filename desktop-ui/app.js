import React from "react";
import { createRoot } from "react-dom/client";

import { FluxioDesktopApp } from "./FluxioDesktop.jsx";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Fluxio desktop root element is missing.");
}

createRoot(rootElement).render(React.createElement(FluxioDesktopApp));
