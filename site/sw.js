/* Mediatrix service worker.
 * Cache the entire static surface on first install so the library
 * works offline on any device once visited.
 *
 * Cache strategy:
 *   - Precache: every HTML page, the stylesheet bundle, the JS bundle,
 *     the 27 woff2 fonts, the favicon, the manifest.
 *   - Runtime fetch fallback: JSON data files (anthology, search-index,
 *     etc.) are cached on first fetch; subsequent loads use cache.
 *   - Network-first for HTML so a content update propagates when the
 *     device is online; cache-first for fonts and static assets.
 *
 * Bump CACHE_NAME when CSS/JS/fonts change to invalidate.
 */

const CACHE_NAME = "mediatrix-v26";

const PRECACHE_HTML = [
  "index.html",
  "library.html",
  "ot-types.html",
  "nt-texts.html",
  "anthology.html",
  "rosary.html",
  "defense.html",
  "feasts.html",
  "apparitions.html",
  "litany.html",
  "office.html",
  "akathist.html",
  "iconography.html",
  "search.html",
  "about.html",
  "404.html",
];

const PRECACHE_STATIC = [
  "styles/mediatrix.css?v=26",
  "styles/fonts.css",
  "scripts/mediatrix.js?v=26",
  "favicon.svg",
  "favicon-16.png",
  "favicon-32.png",
  "apple-touch-icon-180.png",
  "og.png",
  "manifest.json",
];

const PRECACHE_DATA = [
  "data/search-index.json",
  "data/anthology.json",
];

const PRECACHE = [...PRECACHE_HTML, ...PRECACHE_STATIC, ...PRECACHE_DATA];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.all(
        PRECACHE.map((url) =>
          cache.add(new Request(url, { cache: "reload" })).catch(() => {
            /* Quietly skip resources that 404 (e.g. fonts/data not all required) */
          })
        )
      )
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  /* Network-first for HTML to keep content fresh when online. */
  if (req.destination === "document" || req.headers.get("accept")?.includes("text/html")) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req).then((r) => r || caches.match("index.html")))
    );
    return;
  }

  /* Cache-first for fonts, CSS, JS, SVG, JSON. */
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req).then((res) => {
        if (res && res.status === 200 && res.type === "basic") {
          const copy = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(req, copy));
        }
        return res;
      });
    })
  );
});
