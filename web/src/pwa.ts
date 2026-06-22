type FluxioPwaStatus = {
  status: "unsupported" | "registering" | "ready" | "updated" | "failed";
  detail: string;
  waiting?: boolean;
};

const FLUXIO_PWA_BUILD = "20260602-web-push-diagnostics-v31";
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
        window.addEventListener("fluxio:pwa-activate-update", activateWaitingWorker);
        registration.addEventListener("updatefound", () => {
          const worker = registration.installing;
          if (!worker) {
            return;
          }
          worker.addEventListener("statechange", () => {
            if (worker.state === "installed" && navigator.serviceWorker.controller) {
              emitPwaStatus({
                status: "updated",
                detail: "Fluxio app shell update is ready. Reload when convenient.",
                waiting: true,
              });
            }
          });
        });
        registration.update().catch(() => undefined);
        document.addEventListener("visibilitychange", () => {
          if (document.visibilityState === "visible") {
            registration.update().catch(() => undefined);
            if (registration.waiting) {
              emitPwaStatus({
                status: "updated",
                detail: "Fluxio app shell update is waiting.",
                waiting: true,
              });
            }
          }
        });
        window.setInterval(() => {
          registration.update().catch(() => undefined);
          if (registration.waiting) {
            emitPwaStatus({
              status: "updated",
              detail: "Fluxio app shell update is waiting.",
              waiting: true,
            });
          }
        }, FLUXIO_PWA_UPDATE_INTERVAL_MS);
        if (registration.active) {
          registration.active.postMessage({
            type: "PURGE_FLUXIO_CACHES",
            build: FLUXIO_PWA_BUILD,
          });
        }
        if (buildChanged && navigator.serviceWorker.controller) {
          const alreadyReloadedBuild = localStorage.getItem(FLUXIO_PWA_RELOAD_STORAGE_KEY) || "";
          if (alreadyReloadedBuild !== FLUXIO_PWA_BUILD) {
            localStorage.setItem(FLUXIO_PWA_RELOAD_STORAGE_KEY, FLUXIO_PWA_BUILD);
            window.setTimeout(() => window.location.reload(), 250);
          }
        }
        const waiting = navigator.serviceWorker.controller ? registration.waiting : null;
        emitPwaStatus({
          status: waiting ? "updated" : "ready",
          detail: waiting
            ? "Fluxio app shell update is waiting."
            : "Fluxio app shell is ready for installed use.",
          waiting: Boolean(waiting),
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
