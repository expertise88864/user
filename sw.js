/* ChenDermatologist service worker — offline-first for static, network-first for HTML
 * v4: + new articles, offline.html, LRU runtime cache, fetch retry, broken cache cleanup
 */
const CACHE = 'cd-v63';
const RUNTIME = 'cd-runtime-v63';
const RUNTIME_MAX_ENTRIES = 60;

// R31: Slim precache — only critical shell + offline page + assets that EVERY page uses.
// Articles are cached on-demand by network-first / runtime cache. Saves ~3 MB initial install
// (was caching 30+ blog HTML × ~50 KB each = ~1.5 MB) and avoids slow SW activation on mobile.
const PRECACHE = [
  '/',
  '/index.html',
  '/offline.html',
  '/icon.svg',
  '/favicon.ico',
  '/apple-touch-icon.png',
  '/manifest.json',
  '/assets/tw-mini.css',
  '/blog/blog-shared.js',
  '/blog/'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => Promise.allSettled(PRECACHE.map((u) => c.add(u))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== CACHE && k !== RUNTIME).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// LRU eviction for runtime cache
async function trimCache(cacheName, max) {
  try {
    const cache = await caches.open(cacheName);
    const keys = await cache.keys();
    if (keys.length <= max) return;
    // Delete oldest entries (FIFO; cache.keys() preserves insertion order)
    const toDelete = keys.slice(0, keys.length - max);
    await Promise.all(toDelete.map((req) => cache.delete(req)));
  } catch (e) { /* ignore */ }
}

// Fetch with retry once on transient errors
async function fetchWithRetry(req, retries = 1) {
  try {
    const r = await fetch(req);
    if (r && (r.ok || r.type === 'opaque')) return r;
    if (retries > 0) return fetchWithRetry(req, retries - 1);
    return r;
  } catch (err) {
    if (retries > 0) return fetchWithRetry(req, retries - 1);
    throw err;
  }
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  // Always bypass /admin so user gets the freshest editor
  if (url.pathname.startsWith('/admin')) return;

  // Network-first for HTML (navigations + accept text/html)
  if (req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html')) {
    e.respondWith(
      fetchWithRetry(req)
        .then((resp) => {
          // Only cache successful 2xx responses
          if (resp && resp.ok) {
            const copy = resp.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return resp;
        })
        .catch(() => caches.match(req).then((r) =>
          r || caches.match('/offline.html').then((o) => o || caches.match('/'))
        ))
    );
    return;
  }

  // Cache-first for static assets, runtime cache for non-precached
  e.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetchWithRetry(req).then((resp) => {
        if (resp && resp.status === 200) {
          const copy = resp.clone();
          caches.open(RUNTIME).then((c) => {
            c.put(req, copy);
            trimCache(RUNTIME, RUNTIME_MAX_ENTRIES);
          });
        }
        return resp;
      }).catch(() => cached);
    })
  );
});

// Allow page to trigger immediate update via postMessage({type:'SKIP_WAITING'})
self.addEventListener('message', (e) => {
  if (e.data && e.data.type === 'SKIP_WAITING') self.skipWaiting();
});
