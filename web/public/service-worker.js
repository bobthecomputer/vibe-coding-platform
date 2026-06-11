const CACHE_VERSION = "fluxio-pwa-v31-web-push-diagnostics-20260602";
const APP_SHELL = [
  "/offline.html",
  "/manifest.webmanifest",
  "/icons/fluxio-icon.svg",
  "/icons/fluxio-maskable.svg",
];

function shouldBypass(request) {
  const url = new URL(request.url);
  return (
    request.method !== "GET" ||
    url.origin !== self.location.origin ||
    url.pathname.startsWith("/api") ||
    url.pathname.startsWith("/assets/") ||
    /\.(?:js|css|html?)$/i.test(url.pathname) ||
    url.pathname === "/health"
  );
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_VERSION).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
      .then(() => self.clients.matchAll({ type: "window", includeUncontrolled: true }))
      .then((clients) => Promise.all(
        clients
          .filter((client) => {
            try {
              return new URL(client.url).pathname.startsWith("/control");
            } catch {
              return false;
            }
          })
          .map((client) => (client.navigate ? client.navigate(client.url) : undefined)),
      )),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (shouldBypass(request)) {
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .catch(() => caches.match("/offline.html")),
    );
    return;
  }

  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok && response.type === "basic") {
          const copy = response.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(() => caches.match(request)),
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
  if (event.data && event.data.type === "PURGE_FLUXIO_CACHES") {
    event.waitUntil(
      caches.keys()
        .then((keys) => Promise.all(
          keys
            .filter((key) => key.startsWith("fluxio-pwa-") && key !== CACHE_VERSION)
            .map((key) => caches.delete(key)),
        )),
    );
  }
});

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = { body: event.data ? event.data.text() : "" };
  }
  const title = payload.title || "Fluxio mission update";
  const body = payload.body || payload.detail || payload.message || "Mission status changed.";
  const targetUrl = payload.url || payload.targetUrl || "/control?mode=builder&surface=builder";
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      tag: payload.tag || payload.id || "fluxio-mission-update",
      data: {
        url: targetUrl,
        missionId: payload.missionId || "",
      },
    }),
  );
});

self.addEventListener("pushsubscriptionchange", (event) => {
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true })
      .then((clients) => {
        for (const client of clients) {
          client.postMessage({ type: "fluxio:pushsubscriptionchange" });
        }
      }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = event.notification.data && event.notification.data.url
    ? event.notification.data.url
    : "/control?mode=builder&surface=builder";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true })
      .then((clients) => {
        const existing = clients.find((client) => client.url.includes("/control"));
        if (existing) {
          existing.focus();
          return existing.navigate ? existing.navigate(targetUrl) : undefined;
        }
        return self.clients.openWindow(targetUrl);
      }),
  );
});
