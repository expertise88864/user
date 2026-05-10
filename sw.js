/* ChenDermatologist service worker — offline-first for static, network-first for HTML
 * v4: + new articles, offline.html, LRU runtime cache, fetch retry, broken cache cleanup
 */
const CACHE = 'cd-v109';
const RUNTIME = 'cd-runtime-v109';
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
  '/blog/blog-shared.min.js',
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
  // Bypass the SW reset page so it can talk to the SW directly
  if (url.pathname === '/reset-sw' || url.pathname === '/reset-sw.html') return;

  // Network-first for HTML navigation (changed from stale-while-revalidate
  // because SWR was serving stale HTML referencing old `?v=...` cache-busted
  // assets even after a deploy, causing site to break for hours after release).
  // Cache only used as offline fallback. Redirect responses are NEVER cached
  // (they previously caused redirect-loop ERR_FAILED on /blog/).
  if (req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html')) {
    e.respondWith(
      fetchWithRetry(req)
        .then((resp) => {
          // Only cache successful, non-redirected, non-opaque responses
          if (resp && resp.ok && !resp.redirected && resp.type === 'basic') {
            const copy = resp.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return resp;
        })
        .catch(() => caches.match(req).then((c) => c || caches.match('/offline.html').then((o) => o || caches.match('/'))))
    );
    return;
  }

  // Network-first for versioned assets (URLs containing `?v=`):
  // we use cache-bust query strings (?v=YYYYMMDDhhmm) on every deploy, so the
  // version param IS the freshness signal. Going network-first guarantees the
  // browser ALWAYS picks up the new bundle on the same-day deploy, even if the
  // SW was installed days ago. Falls back to cache only if offline.
  if (url.search.includes('v=')) {
    e.respondWith(
      fetchWithRetry(req)
        .then((resp) => {
          if (resp && resp.status === 200) {
            const copy = resp.clone();
            caches.open(RUNTIME).then((c) => {
              c.put(req, copy);
              trimCache(RUNTIME, RUNTIME_MAX_ENTRIES);
            });
          }
          return resp;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // Cache-first for static assets without version, runtime cache for non-precached
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
  // I11 — Precache list of articles the page tells us about (popular picks).
  // Page does: navigator.serviceWorker.controller.postMessage({type:'PRECACHE',urls:[...]})
  // SW fetches them when network is idle so they're available offline.
  if (e.data && e.data.type === 'PRECACHE' && Array.isArray(e.data.urls)) {
    e.waitUntil((async () => {
      try {
        const cache = await caches.open(RUNTIME);
        // Limit concurrency to avoid hammering: 3 at a time
        const queue = e.data.urls.slice(0, 20);
        for (let i = 0; i < queue.length; i += 3) {
          await Promise.allSettled(queue.slice(i, i + 3).map(async (u) => {
            try {
              const resp = await fetch(u, { credentials: 'omit' });
              if (resp && resp.ok) await cache.put(u, resp);
            } catch (_) {}
          }));
        }
        await trimCache(RUNTIME, RUNTIME_MAX_ENTRIES);
      } catch (_) {}
    })());
  }
});

// ─────────────────────────────────────────────────────────────────────
// Push notifications (R32+) — handler is ready; full activation needs
// VAPID keys + push server. When server pushes a payload, this displays
// it as a native notification. Click → opens article URL.
// Payload schema: { title, body, url, tag?, icon? }
// ─────────────────────────────────────────────────────────────────────
self.addEventListener('push', (e) => {
  let data = {};
  try { data = e.data ? e.data.json() : {}; } catch { data = { title: 'ChenDermatologist', body: e.data ? e.data.text() : '' }; }
  const title = data.title || 'ChenDermatologist 衛教更新';
  const opts = {
    body: data.body || '新文章上架',
    icon: data.icon || '/apple-touch-icon.png',
    badge: '/icon.svg',
    tag: data.tag || 'cd-update',
    data: { url: data.url || '/blog/' },
    requireInteraction: false,
    silent: false,
  };
  e.waitUntil(self.registration.showNotification(title, opts));
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || '/blog/';
  e.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
      // Focus existing tab if it's already on the destination
      for (const w of wins) {
        if (w.url.endsWith(url) && 'focus' in w) return w.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
