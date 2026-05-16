const CACHE_NAME = '__SW_CACHE_NAME__';
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

// --- Background Sync / Offline Queue ---
function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('osp-offline-db', 1);
    request.onupgradeneeded = (e) => {
      e.target.result.createObjectStore('sync-queue', { keyPath: 'id', autoIncrement: true });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-logbook-entries') {
    event.waitUntil(flushQueue());
  }
});

async function flushQueue() {
  const db = await openDB();
  const tx = db.transaction('sync-queue', 'readwrite');
  const store = tx.objectStore('sync-queue');
  const getReq = store.getAll();
  
  return new Promise((resolve, reject) => {
    getReq.onsuccess = async () => {
      const items = getReq.result;
      if (!items || items.length === 0) return resolve();
      
      let allSuccess = true;
      let sessionExpiredNotified = false;
      for (const item of items) {
        try {
          const bodyData = new URLSearchParams(item.payload).toString();
          const response = await fetch(item.endpoint, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
              'Accept': 'application/json',
              'X-CSRFToken': item.csrfToken
            },
            body: bodyData
          });
          
          if (response.ok) {
            await deleteQueueItem(db, item.id);
            // Notify client if available
            self.clients.matchAll().then(clients => {
              clients.forEach(client => client.postMessage({ type: 'SYNC_SUCCESS', message: 'Zsynchronizowano zaległy wpis z bazy offline.' }));
            });
          } else if (response.status === 403 || response.status === 401) {
            await deleteQueueItem(db, item.id);
            if (!sessionExpiredNotified) {
              sessionExpiredNotified = true;
              self.clients.matchAll().then(clients => {
                clients.forEach(client => client.postMessage({
                  type: 'SYNC_SESSION_EXPIRED',
                  message: 'Sesja wygasła. Zaloguj się ponownie, aby kontynuować synchronizację.'
                }));
              });
            }
          } else {
            allSuccess = false;
          }
        } catch (e) {
          allSuccess = false;
        }
      }
      allSuccess ? resolve() : reject(new Error('Sync failed for some items'));
    };
    getReq.onerror = () => reject(getReq.error);
  });
}

function deleteQueueItem(db, itemId) {
  return new Promise((resolve, reject) => {
    const delTx = db.transaction('sync-queue', 'readwrite');
    const deleteReq = delTx.objectStore('sync-queue').delete(itemId);
    deleteReq.onsuccess = () => resolve();
    deleteReq.onerror = () => reject(deleteReq.error);
  });
}
