// Service worker: cache the app shell so a flaky gym connection doesn't leave
// you staring at a blank page.
//
// The pose model and its wasm come from a CDN and are NOT precached here -- they
// are large and versioned by URL, so the browser's own HTTP cache handles them.
// API calls are never cached: a stale rep count is worse than no rep count.
const CACHE = "kinetiq-shell-v1";
const SHELL = [
  "./", "./index.html", "./styles.css", "./app.js",
  "./config.js", "./severities.json", "./manifest.json", "./icon.svg",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;                    // never cache an assess POST
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;     // CDN + API pass straight through

  // Network-first for config.js so a redeploy's new API URL is picked up
  // immediately rather than being pinned by a stale cache entry.
  if (url.pathname.endsWith("/config.js")) {
    e.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
        return res;
      }).catch(() => caches.match(req))
    );
    return;
  }

  e.respondWith(caches.match(req).then((hit) => hit || fetch(req)));
});
