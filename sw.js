/* ChenDermatologist service worker — offline-first for static, network-first for HTML */
const CACHE = 'cd-v2';
const PRECACHE = [
  '/',
  '/index.html',
  '/about',
  '/privacy',
  '/icon.svg',
  '/manifest.json',
  '/blog/',
  '/blog/topics',
  '/blog/feed.xml',
  '/blog/blog-shared.js',
  '/blog/acne-myths',
  '/blog/sunscreen-myths',
  '/blog/eczema-myths',
  '/blog/melasma-myths',
  '/blog/rosacea-myths',
  '/blog/hairloss-myths',
  '/blog/tinea-myths',
  '/blog/topical-acids-patient',
  '/blog/isotretinoin-patient',
  '/blog/topical-acids-clinical',
  '/blog/isotretinoin-clinical'
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
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  // Skip /admin to ensure user always gets fresh editor
  if (url.pathname.startsWith('/admin')) return;

  if (req.mode === 'navigate' || req.headers.get('accept')?.includes('text/html')) {
    e.respondWith(
      fetch(req)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
          return resp;
        })
        .catch(() => caches.match(req).then((r) => r || caches.match('/')))
    );
    return;
  }

  e.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req).then((resp) => {
        if (resp && resp.status === 200) {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return resp;
      }).catch(() => cached);
    })
  );
});
