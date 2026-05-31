type FluxioPwaStatus = {
  status: "unsupported" | "registering" | "ready" | "updated" | "failed";
  detail: string;
};

const FLUXIO_PWA_BUILD = "20260531-reference-agent-proof-ready-v22";
const FLUXIO_PWA_UPDATE_INTERVAL_MS = 60_000;
const FLUXIO_PWA_BUILD_STORAGE_KEY = "fluxio:pwa-build";
const FLUXIO_PWA_RELOAD_STORAGE_KEY = "fluxio:pwa-reloaded-build";

function emitPwaStatus(status: FluxioPwaStatus) {
  window.dispatchEvent(new CustomEvent("fluxio:pwa-status", { detail: status }));
  document.documentElement.dataset.fluxioPwa = status.status;
}

export function registerFluxioPwa() {
  if (!("serviceWorker" in navigator)) {
    emitPwaStatus({ status: "unsupported", detail: "Service workers are not available in this browser." });
    return;
  }

  let reloadedForControllerUpdate = false;
  const previousBuild = localStorage.getItem(FLUXIO_PWA_BUILD_STORAGE_KEY) || "";
  const buildChanged = previousBuild !== FLUXIO_PWA_BUILD;
  if (buildChanged && "caches" in window) {
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key.startsWith("fluxio-pwa-"))
          .map((key) => caches.delete(key)),
      ))
      .catch(() => undefined);
  }
  localStorage.setItem(FLUXIO_PWA_BUILD_STORAGE_KEY, FLUXIO_PWA_BUILD);
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (reloadedForControllerUpdate) {
      return;
    }
    reloadedForControllerUpdate = true;
    window.location.reload();
  });

  emitPwaStatus({ status: "registering", detail: "Registering Fluxio app shell." });
  window.addEventListener("load", () => {
    navigator.serviceWorker.register(`/service-worker.js?build=${encodeURIComponent(FLUXIO_PWA_BUILD)}`, { scope: "/" })
      .then((registration) => {
        const activateWaitingWorker = () => {
          if (registration.waiting) {
            registration.waiting.postMessage({ type: "SKIP_WAITING" });
          }
        };
        registration.addEventListener("updatefound", () => {
          const worker = registration.installing;
          if (!worker) {
            return;
          }
          worker.addEventListener("statechange", () => {
            if (worker.state === "installed" && navigator.serviceWorker.controller) {
              emitPwaStatus({
                status: "updated",
                detail: "Fluxio app shell update is ready; refreshing the live interface.",
              });
              activateWaitingWorker();
            }
          });
        });
        registration.update().catch(() => undefined);
        document.addEventListener("visibilitychange", () => {
          if (document.visibilityState === "visible") {
            registration.update().catch(() => undefined);
            activateWaitingWorker();
          }
        });
        window.setInterval(() => {
          registration.update().catch(() => undefined);
          activateWaitingWorker();
        }, FLUXIO_PWA_UPDATE_INTERVAL_MS);
        if (registration.active) {
          registration.active.postMessage({
            type: "PURGE_FLUXIO_CACHES",
            build: FLUXIO_PWA_BUILD,
          });
        }
        activateWaitingWorker();
        if (buildChanged && navigator.serviceWorker.controller) {
          const alreadyReloadedBuild = localStorage.getItem(FLUXIO_PWA_RELOAD_STORAGE_KEY) || "";
          if (alreadyReloadedBuild !== FLUXIO_PWA_BUILD) {
            localStorage.setItem(FLUXIO_PWA_RELOAD_STORAGE_KEY, FLUXIO_PWA_BUILD);
            window.setTimeout(() => window.location.reload(), 250);
          }
        }
        const waiting = registration.waiting || registration.installing;
        emitPwaStatus({
          status: waiting ? "updated" : "ready",
          detail: waiting
            ? "Fluxio app shell update is activating."
            : "Fluxio app shell is ready for installed use.",
        });
      })
      .catch((error: unknown) => {
        emitPwaStatus({
          status: "failed",
          detail: error instanceof Error ? error.message : "Fluxio app shell registration failed.",
        });
      });
  }, { once: true });
}
