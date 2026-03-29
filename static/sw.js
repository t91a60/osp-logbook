const CACHE_NAME = 'osp-logbook-v2';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
  // Pass-through fetch. This is just enough to satisfy PWA install requirements.
  event.respondWith(
    fetch(event.request).catch(() => {
      // Basic offline fallback could go here
      return new Response('Jesteś offline / You are offline.', {
        status: 503,
        statusText: 'Service Unavailable'
      });
    })
  );
});
