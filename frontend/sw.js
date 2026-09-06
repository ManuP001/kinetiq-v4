// sw.js — minimal offline shell for the Kinetiq v4 PWA.
// Caches the static app shell only. The pose model (CDN) and the detector API both need the
// network at run time; this just makes the shell installable and fast to reopen.
const CACHE = "kinetiq-v4-shell-v1";
const SHELL = [
  "./index.html",
  "./styles.css",
  "./app.js",
  "./config.js",
  "./severities.json",
  "./manifest.json",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // Only serve the same-origin static shell from cache; never intercept CDN or API calls.
  if (url.origin === self.location.origin && e.request.method === "GET") {
    e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request)));
  }
});
