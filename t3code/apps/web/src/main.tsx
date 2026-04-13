import React from "react";
import { createRoot } from "react-dom/client";

import "./fluxio/styles.css";
import { FluxioApp } from "./fluxio/FluxioApp";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Fluxio web root element is missing.");
}

createRoot(rootElement).render(
  <React.StrictMode>
    <FluxioApp />
  </React.StrictMode>,
);
