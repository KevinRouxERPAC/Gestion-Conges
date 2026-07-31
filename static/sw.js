/* Service Worker ERPAC Congés — Web Push + cache offline (PWA)
 *
 * Stratégie de cache :
 *  - assets statiques (static/*)         : cache-first, mise à jour en arrière-plan (stale-while-revalidate)
 *  - pages HTML de l'application          : network-first, fallback cache si hors-ligne
 *  - routes d'API et requêtes POST        : toujours réseau (jamais mises en cache)
 */
const CACHE_VERSION = 'erpac-conges-v1';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const PAGE_CACHE = `${CACHE_VERSION}-pages`;

// Ressources statiques pré-cachées à l'installation (shell hors-ligne minimal).
const PRECACHE_URLS = [
  '/static/manifest.webmanifest',
  '/static/offline.html',
  '/static/img/logo_seul.png',
  '/static/img/logo_complet_vert.png',
  '/static/img/icon-192.png',
  '/static/img/icon-512.png',
  '/static/css/erpac-tokens.css',
  '/static/css/erpac-composants.css',
  '/static/css/tailwind.css',
  '/static/css/custom.css',
  '/static/vendor/alpine.min.js',
  '/static/js/app.js',
];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(function (cache) {
        // On ajoute ce qu'on peut ; les assets manquants ne bloquent pas l'install.
        return cache.addAll(PRECACHE_URLS).catch(function (err) {
          console.warn('[SW] Pré-cache partiel :', err);
        });
      })
      .then(function () {
        return self.skipWaiting();
      })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(
          keys
            .filter(function (k) { return k !== STATIC_CACHE && k !== PAGE_CACHE; })
            .map(function (k) { return caches.delete(k); })
        );
      })
      .then(function () { return self.clients.claim(); })
  );
});

// Helpers de stratégie.
function isStaticAsset(url) {
  return url.pathname.startsWith('/static/');
}

function isHtmlRequest(request) {
  return request.mode === 'navigate' ||
    (request.headers.get('accept') || '').includes('text/html');
}

function isCacheable(request) {
  // On ne met jamais en cache les requêtes non-GET ni les API.
  if (request.method !== 'GET') return false;
  const url = new URL(request.url);
  if (url.pathname.startsWith('/api/')) return false;
  if (url.pathname.startsWith('/notifications/')) return false;
  if (url.pathname.startsWith('/auth/')) return false;
  if (isHtmlRequest(request)) return false;
  return true;
}

// Stale-while-revalidate pour les assets statiques.
function staleWhileRevalidate(request) {
  return caches.open(STATIC_CACHE).then(function (cache) {
    return cache.match(request).then(function (cached) {
      const fetchPromise = fetch(request).then(function (response) {
        if (response && response.status === 200) {
          cache.put(request, response.clone());
        }
        return response;
      }).catch(function () { return cached; });
      return cached || fetchPromise;
    });
  });
}

// Network-first pour les pages HTML, fallback cache si hors-ligne.
function networkFirst(request) {
  return caches.open(PAGE_CACHE).then(function (cache) {
    return fetch(request).then(function (response) {
      if (response && response.status === 200) {
        cache.put(request, response.clone());
      }
      return response;
    }).catch(function () {
        return cache.match(request).then(function (cached) {
        return cached || cache.match('/static/offline.html');
      });
    });
  });
}

self.addEventListener('fetch', function (event) {
  const request = event.request;
  if (!isCacheable(request)) return;

  const url = new URL(request.url);
  // On ne gère que les requêtes same-origin.
  if (url.origin !== self.location.origin) return;

  if (isHtmlRequest(request)) {
    event.respondWith(fetch(request).catch(function () { return caches.match('/static/offline.html'); }));
  } else if (isStaticAsset(url)) {
    event.respondWith(staleWhileRevalidate(request));
  }
});

// Page de secours hors-ligne générée à la volée si /offline.html manque.
self.addEventListener('message', function (event) {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});

/* ------------------------- Web Push ------------------------- */

self.addEventListener('push', function (event) {
  if (!event.data) return;
  let payload = { title: 'ERPAC Congés', body: '', url: '/notifications/' };
  try {
    const data = event.data.json();
    if (data.title) payload.title = data.title;
    if (data.body) payload.body = data.body;
    if (data.url) payload.url = data.url;
  } catch (e) {
    payload.body = event.data.text();
  }
  const options = {
    body: payload.body,
    tag: 'erpac-conges',
    requireInteraction: false,
    data: { url: payload.url }
  };
  event.waitUntil(
    self.registration.showNotification(payload.title, options).catch(function (err) {
      console.warn('showNotification failed', err);
    })
  );
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  const url = event.notification.data && event.notification.data.url;
  if (url) {
    event.waitUntil(
      clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (windowClients) {
        for (let i = 0; i < windowClients.length; i++) {
          if (windowClients[i].url.indexOf(self.location.origin) === 0 && 'focus' in windowClients[i]) {
            windowClients[i].navigate(url);
            return windowClients[i].focus();
          }
        }
        if (clients.openWindow) {
          return clients.openWindow(self.location.origin + url);
        }
      })
    );
  }
});
