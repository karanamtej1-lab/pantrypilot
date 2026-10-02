// PantryPilot service worker: lets the app open and show the pantry list with no internet.
//
// How it decides:
//   Pages, CSS, JS, icons  -> try the network first (always fresh when online), fall back to the saved copy.
//   /pantries              -> network first; offline, the saved list is returned with an
//                             "X-PantryPilot-Saved: 1" header so app.js can say it's an older copy.
//   Leaflet from cdnjs     -> saved copy first (those files never change at a versioned URL).
//   /ask, /forecast (POST), map tiles -> always the network; nothing private is stored.
//
// After changing the list of files below, bump VERSION so phones throw away the old copies.

const VERSION = "pantrypilot-v1";
const SHELL_CACHE = `${VERSION}-shell`;
const DATA_CACHE = `${VERSION}-data`;
const CDN_CACHE = `${VERSION}-cdn`;

const APP_SHELL = [
  "/", "/index.html", "/hours.html", "/ask.html",
  "/style.css", "/hours.css", "/ask.css",
  "/i18n.js", "/settings.js", "/app.js", "/hours.js", "/ask.js",
  "/manifest.json", "/icons/icon.svg", "/icons/icon-192.png", "/icons/icon-512.png",
  "/icons/apple-touch-icon.png",
];
const CDN_FILES = [
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js",
];
const DATA_URLS = ["/pantries", "/volunteer"];

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    await (await caches.open(SHELL_CACHE)).addAll(APP_SHELL);
    // Extras are "nice to have": one failing must not stop the app from installing.
    const cdn = await caches.open(CDN_CACHE);
    await Promise.all(CDN_FILES.map((url) => cdn.add(url).catch(() => {})));
    const data = await caches.open(DATA_CACHE);
    await Promise.all(DATA_URLS.map((url) => data.add(url).catch(() => {})));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) {
      if (!name.startsWith(VERSION)) await caches.delete(name); // old versions
    }
    await self.clients.claim();
  })());
});

async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response.ok && response.type === "basic") cache.put(request, response.clone());
    return response;
  } catch (error) {
    const saved = await cache.match(request, { ignoreSearch: true });
    if (saved) return saved;
    if (request.mode === "navigate") return (await cache.match("/")) || Response.error();
    return Response.error();
  }
}

async function pantriesNetworkFirst(request) {
  const cache = await caches.open(DATA_CACHE);
  const url = new URL(request.url);
  try {
    const response = await fetch(request);
    // Only the plain, unfiltered list is saved; offline, app.js filters it itself.
    if (response.ok && url.search === "") cache.put("/pantries", response.clone());
    return response;
  } catch (error) {
    const saved = await cache.match("/pantries");
    if (!saved) {
      return new Response(JSON.stringify({ detail: "offline" }), {
        status: 503, headers: { "Content-Type": "application/json" },
      });
    }
    const headers = new Headers(saved.headers);
    headers.set("X-PantryPilot-Saved", "1");
    return new Response(await saved.blob(), { status: 200, headers });
  }
}

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const saved = await cache.match(request);
  if (saved) return saved;
  const response = await fetch(request);
  if (response.ok) cache.put(request, response.clone());
  return response;
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return; // questions and forecasts always go to the server

  const url = new URL(request.url);
  if (url.origin === self.location.origin) {
    if (url.pathname === "/pantries") return event.respondWith(pantriesNetworkFirst(request));
    if (url.pathname === "/volunteer") return event.respondWith(networkFirst(request, DATA_CACHE));
    if (["/health", "/docs", "/openapi.json", "/sw.js"].includes(url.pathname)) return;
    return event.respondWith(networkFirst(request, SHELL_CACHE));
  }
  if (url.hostname === "cdnjs.cloudflare.com") return event.respondWith(cacheFirst(request, CDN_CACHE));
  // Everything else (OpenStreetMap tiles, the AI) goes straight to the network.
});
