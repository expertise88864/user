/* ChenDermatologist service worker — offline-first for static, network-first for HTML
 * v4: + new articles, offline.html, LRU runtime cache, fetch retry, broken cache cleanup
 */
const CACHE = 'cd-v139';
const RUNTIME = 'cd-runtime-v137';
// 2026-05-17 — bumped 60 → 150 after deep audit showed 48 articles × ≥3
// lazy bundles each + cache-bust HTMLs were thrashing the previous cap.
// Popular articles getting evicted after ~5 navigations caused repeat-
// visit LCP regressions of ~300 ms on mobile.
const RUNTIME_MAX_ENTRIES = 150;
// CODE_REVIEW — the HTML cache (CACHE) previously had no entry cap;
// a long-tail reader who navigated ≥100 articles would grow it
// unbounded. Cap matches RUNTIME_MAX_ENTRIES rationale — generous
// enough for the current 50-article catalog + ~50 future articles.
const HTML_CACHE_MAX_ENTRIES = 150;

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
  // 2026-05-17 — REMOVED '/assets/tw-mini.css' from PRECACHE. The HTML
  // requests it as `tw-mini.css?v=22` (cache-busted), which doesn't
  // match the unversioned PRECACHE key — so the precache entry was a
  // useless duplicate. The versioned URL falls through to network-first
  // for ?v= which already caches it in cd-runtime.
  '/blog/'
];

self.addEventListener('install', (e) => {
  // CODE_REVIEW — dropped self.skipWaiting() from install. Reason:
  // blog-shared.js bindSWUpdateToast() already shows a "new version
  // available" toast and posts {type:'SKIP_WAITING'} when the user
  // clicks it (handler at line 186 of this file). When install also
  // skipped waiting, the new SW activated immediately AND the toast
  // would post SKIP_WAITING redundantly, sometimes causing a double
  // reload via controllerchange. Letting the toast own activation
  // gives the user warning that something is changing.
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => Promise.allSettled(PRECACHE.map((u) => c.add(u))))
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

// FIFO eviction for cache (CODE_REVIEW — renamed from "LRU" since
// cache.keys() returns insertion order, not access order — no
// read-tracking exists to implement true LRU).
async function trimCache(cacheName, max) {
  try {
    const cache = await caches.open(cacheName);
    const keys = await cache.keys();
    if (keys.length <= max) return;
    const toDelete = keys.slice(0, keys.length - max);
    await Promise.all(toDelete.map((req) => cache.delete(req)));
  } catch (e) { /* ignore */ }
}

// CODE_REVIEW — fetchWithRetry was retrying ALL non-OK responses
// including 404s, wasting a round-trip. Now only retries on network
// errors (TypeError from fetch) or >=500 server errors. Client-error
// responses (4xx) are returned as-is.
async function fetchWithRetry(req, retries = 1) {
  try {
    const r = await fetch(req);
    if (r && (r.ok || r.type === 'opaque')) return r;
    if (r && r.status >= 500 && retries > 0) {
      return fetchWithRetry(req, retries - 1);
    }
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
            // CODE_REVIEW — cap HTML cache same as runtime to avoid
            // unbounded growth for long-tail readers (≥100 articles).
            caches.open(CACHE).then((c) => {
              c.put(req, copy);
              trimCache(CACHE, HTML_CACHE_MAX_ENTRIES);
            });
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

  // Network-first for generated data that changes with content updates.
  // Search results should reflect newly published/edited articles quickly;
  // cache is only an offline fallback.
  if (url.pathname === '/assets/search-index.json') {
    e.respondWith(
      fetchWithRetry(req)
        .then((resp) => {
          if (resp && resp.status === 200 && resp.type === 'basic') {
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
      // CODE_REVIEW — was `w.url.endsWith(url)` which matched
      // `/blog/myths` against `/blog/acne-myths` (false positive).
      // Use proper URL pathname comparison anchored to the origin.
      let targetPath;
      try {
        targetPath = new URL(url, self.location.origin).pathname;
      } catch { targetPath = url; }
      for (const w of wins) {
        let winPath;
        try { winPath = new URL(w.url).pathname; } catch { winPath = ''; }
        if (winPath === targetPath && 'focus' in w) return w.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
