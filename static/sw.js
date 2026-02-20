/* Service Worker ERPAC Congés - Web Push */
self.addEventListener('push', function(event) {
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
    self.registration.showNotification(payload.title, options).catch(function(err) {
      console.warn('showNotification failed', err);
    })
  );
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const url = event.notification.data && event.notification.data.url;
  if (url) {
    event.waitUntil(
      clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(windowClients) {
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
