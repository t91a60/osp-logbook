const CACHE_NAME = 'osp-logbook-v2';
const PRECACHE_URLS = [
  '/static/main.css',
  '/static/app.js',
  '/static/manifest.json'
];

self.addEventListener('install', (event) => {
  // Pre-cache the app shell (CSS/JS/manifest)
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  // Clean up old caches
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_NAME)
          .map((k) => caches.delete(k))
      )
    ).then(() => clients.claim())
  );
});

function isNavigationRequest(request) {
  return request.mode === 'navigate' || (request.destination === '' || request.headers.get('accept')?.includes('text/html'));
}

self.addEventListener('fetch', (event) => {
  const req = event.request;

  // Static assets: cache-first strategy
  if (req.url.includes('/static/') && (req.url.endsWith('.css') || req.url.endsWith('.js') || req.url.endsWith('.json'))) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) return cached;
        return fetch(req).then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
          }
          return res;
        }).catch(() => caches.match('/static/manifest.json'));
      })
    );
    return;
  }

  // HTML/navigation: network-first with cache fallback
  if (isNavigationRequest(req)) {
    event.respondWith(
      fetch(req)
        .then((networkResp) => {
          // Optionally cache navigations
          if (networkResp && networkResp.ok) {
            const copy = networkResp.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
          }
          return networkResp;
        })
        .catch(() => caches.match(req).then((cached) => cached || caches.match('/')))
    );
    return;
  }

  // Default: just try network then fallback to cache
  event.respondWith(
    fetch(req).catch(() => caches.match(req))
  );
});
