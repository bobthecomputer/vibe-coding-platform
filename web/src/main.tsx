import React from "react";
import { createRoot } from "react-dom/client";

import "./fluxio/styles.css";
import { FluxioApp } from "./fluxio/FluxioApp";
import { registerFluxioPwa } from "./pwa";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Fluxio web root element is missing.");
}

const strictModeEnabled =
  import.meta.env.DEV &&
  new URLSearchParams(window.location.search).get("strict") === "1";

const app = <FluxioApp />;

createRoot(rootElement).render(
  strictModeEnabled ? <React.StrictMode>{app}</React.StrictMode> : app,
);

registerFluxioPwa();
