/* ChenDermatologist service worker — offline-first for static, network-first for HTML
 * v4: + new articles, offline.html, LRU runtime cache, fetch retry, broken cache cleanup
 */
const CACHE = 'cd-v163';
const RUNTIME = 'cd-runtime-v161';
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
  // 2026-05-26 — RE-ADDED self.skipWaiting(). The previous "let the toast
  // own activation" model left users STUCK: a returning visitor whose old
  // SW kept cache-first-serving a previous-generation HTML (with the old
  // unstyled / text-based nav) only updated if they happened to click the
  // "網站已更新" toast OR closed every tab. Across several deploys this
  // meant the homepage nav rendered broken for days. There is NO
  // controllerchange→reload handler in blog-shared.js (the toast reloads
  // only on explicit click, line ~733), so skipWaiting cannot cause a
  // reload loop — it just makes a freshly-installed SW activate + claim
  // immediately, purge old caches (see activate handler), and serve fresh
  // content on the user's very next navigation. The toast remains as a
  // same-tab backup. Trade-off accepted: instantly-correct content beats
  // a theoretical double-reload that the current code can't actually
  // trigger.
  self.skipWaiting();
  // CODE_REVIEW 2026-05-25 — `Promise.allSettled` swallows install
  // failures; if /offline.html ever fails to cache the offline-fallback
  // chain in the fetch handler resolves to undefined and the browser
  // shows its own error page. Hard-require /offline.html (other
  // PRECACHE entries can fail without harming the user).
  e.waitUntil((async () => {
    const c = await caches.open(CACHE);
    await Promise.allSettled(PRECACHE.map((u) => c.add(u)));
    // Re-fetch /offline.html explicitly so a transient install failure
    // doesn't leave us without an offline fallback for the lifetime of
    // this SW generation.
    if (!(await c.match('/offline.html'))) {
      await c.add('/offline.html');
    }
  })());
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

// CODE_REVIEW 2026-05-31 - maybeTrim was CALLED by the HTML stale-while-
// revalidate handler but never DEFINED: a prior pass renamed a trimCache()
// call intending a probabilistic wrapper and never added the function. The
// call threw a ReferenceError swallowed by waitUntil, so the HTML CACHE was
// never trimmed and HTML_CACHE_MAX_ENTRIES (150) was silently defeated.
// Define it as a probabilistic trim: the real trim does an O(n) cache.keys()
// scan, and a SOFT FIFO cap need not run on every single write, so running it
// ~1-in-5 fixes the bug AND cuts ~80% of the scan work.
async function maybeTrim(cacheName, max) {
  if (Math.random() < 0.2) await trimCache(cacheName, max);
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
  // API responses must never enter service-worker caches. OAuth callback
  // HTML can carry one-time credentials, and dynamic API reads must honor
  // their server/CDN cache policy.
  if (url.pathname.startsWith('/api/')) return;
  // Always bypass /admin so user gets the freshest editor
  if (url.pathname.startsWith('/admin')) return;
  // Bypass the SW reset page so it can talk to the SW directly
  if (url.pathname === '/reset-sw' || url.pathname === '/reset-sw.html') return;

  // Stale-while-revalidate for HTML navigation.
  // 2026-05-24 — switched from network-first to SWR to cut Vercel Edge
  // Requests (was ~31k/day, hitting 75% of free-tier 1M/month at day 24).
  // Safety against stale HTML referencing old `?v=...` assets: every
  // deploy that changes asset references MUST bump CACHE_VERSION above —
  // the `activate` handler purges old caches, so SWR never serves HTML
  // from a previous deploy generation. Within the same cache generation,
  // ?v= strings are identical, so SWR cannot cause asset/HTML mismatch.
  // Redirect responses are NEVER cached (they previously caused
  // redirect-loop ERR_FAILED on /blog/).
  if (req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html')) {
    e.respondWith((async () => {
      const cache = await caches.open(CACHE);
      const cached = await cache.match(req);

      // Background revalidate — fires regardless of cache hit so the
      // NEXT visit gets fresh content. Errors swallowed so offline
      // visits still resolve to the cached copy.
      // CODE_REVIEW 2026-05-26 — the cache.put now lives INSIDE the awaited
      // networkPromise chain, and the whole promise is passed to
      // event.waitUntil() up-front. Previously, on a fast cache HIT the
      // handler returned `cached` (resolving respondWith) and only THEN —
      // when the in-flight fetch settled — called e.waitUntil() inside .then.
      // Calling waitUntil() after respondWith has already settled can be a
      // no-op (or throw "called too late"), so SW termination right after a
      // cache hit could silently kill the revalidation, weakening the
      // "next visit gets fresh" guarantee that prevents stale HTML.
      const networkPromise = fetchWithRetry(req)
        .then(async (resp) => {
          if (resp && resp.ok && !resp.redirected && resp.type === 'basic') {
            await cache.put(req, resp.clone());
            await maybeTrim(CACHE, HTML_CACHE_MAX_ENTRIES);
          }
          return resp;
        })
        .catch(() => null);
      // Keep the SW alive through the background fetch + cache write even if
      // we return the cached copy immediately below.
      e.waitUntil(networkPromise);

      // Serve cached HTML immediately if we have it (the SWR win).
      // First-ever visit to this URL waits for network.
      if (cached) return cached;
      const fresh = await networkPromise;
      if (fresh) return fresh;
      // Offline + no cache for this URL → fallback chain.
      return (await cache.match('/offline.html')) || (await cache.match('/'));
    })());
    return;
  }

  // Cache-first for versioned assets (URLs with `?v=YYYYMMDDhhmm` or
  // `&v=YYYYMMDDhhmm`): the version string IS the freshness signal,
  // so an exact URL+query cache hit is BY DEFINITION fresh. A new
  // deploy ships a new `?v=` → new URL → cache miss → fetch → cache.
  // Old `?v=` keys are no longer referenced by any HTML and naturally
  // fall out via `trimCache`.
  //
  // 2026-05-25 — switched from network-first to cache-first to slash
  // Vercel Edge Requests (network-first was making every repeat visitor
  // re-fetch every versioned asset, defeating the whole cache-bust
  // strategy). Tightened the matcher to require `v=` to be a real
  // query parameter (preceded by `?` or `&`), not a substring of any
  // other param like `?nav=1`, `?prev=foo`, or `?view=...`.
  if (/[?&]v=/.test(url.search)) {
    e.respondWith((async () => {
      const cached = await caches.match(req);
      if (cached) return cached;
      try {
        const resp = await fetchWithRetry(req);
        if (resp && resp.status === 200 && resp.type === 'basic') {
          const copy = resp.clone();
          // CODE_REVIEW — wrap cache.put + trimCache in waitUntil so SW
          // termination mid-eviction can't leave RUNTIME permanently
          // over-cap.
          e.waitUntil((async () => {
            const c = await caches.open(RUNTIME);
            await c.put(req, copy);
            await trimCache(RUNTIME, RUNTIME_MAX_ENTRIES);
          })());
        }
        return resp;
      } catch (_) {
        // network failed and no cache — bubble up
        return Response.error();
      }
    })());
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
            // CODE_REVIEW 2026-05-25 — waitUntil for cache.put + trimCache.
            e.waitUntil((async () => {
              const c = await caches.open(RUNTIME);
              await c.put(req, copy);
              await trimCache(RUNTIME, RUNTIME_MAX_ENTRIES);
            })());
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
        if (resp && resp.status === 200 && resp.type === 'basic') {
          const copy = resp.clone();
          // CODE_REVIEW 2026-05-25 — (a) waitUntil for cache.put +
          // trimCache. (b) gate on resp.type === 'basic' so opaque
          // CORS responses (potentially 5xx in disguise) aren't cached.
          e.waitUntil((async () => {
            const c = await caches.open(RUNTIME);
            await c.put(req, copy);
            await trimCache(RUNTIME, RUNTIME_MAX_ENTRIES);
          })());
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
    // CODE_REVIEW 2026-05-25 — same-origin + path-allowlist guard.
    // Previous implementation accepted ANY URL in the message — any
    // page (or compromised 3rd-party script like adsbygoogle/gtag/Giscus)
    // could ask the SW to fetch + cache attacker-controlled URLs.
    // Cache poisoning primitive. Now: only accept same-origin URLs
    // under /blog/, /en/blog/, /assets/, or root html pages.
    const safe = e.data.urls.filter((u) => {
      try {
        const url = new URL(u, self.location.origin);
        if (url.origin !== self.location.origin) return false;
        const p = url.pathname;
        return (
          p === '/' ||
          p.startsWith('/blog/') ||
          p.startsWith('/en/') ||
          p.startsWith('/assets/') ||
          p === '/offline.html' ||
          p === '/manifest.json' ||
          p === '/icon.svg'
        );
      } catch (_) {
        return false;
      }
    });
    e.waitUntil((async () => {
      try {
        const cache = await caches.open(RUNTIME);
        // Limit concurrency to avoid hammering: 3 at a time
        const queue = safe.slice(0, 20);
        for (let i = 0; i < queue.length; i += 3) {
          await Promise.allSettled(queue.slice(i, i + 3).map(async (u) => {
            try {
              // Skip if already cached — avoid wasting Edge Requests.
              const existing = await cache.match(u);
              if (existing) return;
              const resp = await fetch(u, { credentials: 'omit' });
              // CODE_REVIEW 2026-05-26 — exclude redirected responses (match the
              // navigation SWR guard) so a 308 isn't cached under the pre-redirect key.
              if (resp && resp.ok && !resp.redirected && resp.type === 'basic') await cache.put(u, resp);
            } catch (_) {}
          }));
        }
        await trimCache(RUNTIME, RUNTIME_MAX_ENTRIES);
      } catch (_) {}
    })());
  }
});
