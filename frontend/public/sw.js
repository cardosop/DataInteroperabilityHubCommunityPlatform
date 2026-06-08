/**
 * Service Worker — Web Push + Offline Cache (281.A.12.4).
 *
 * Registers for push notifications and caches critical assets
 * for offline resilience. Non-blocking — app works without it.
 */
const CACHE_NAME = 'meshant-v1';
const CRITICAL_ASSETS = ['/', '/index.html', '/assets/index.css', '/assets/index.js'];

// ── Install: pre-cache critical assets ──
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CRITICAL_ASSETS))
  );
  self.skipWaiting();
});

// ── Activate: clean old caches ──
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ── Push: receive and show notification ──
self.addEventListener('push', (event) => {
  if (!event.data) return;
  const payload = event.data.json();
  const { title, body, icon, tag, url } = payload;

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: icon || '/meshant-logo.png',
      badge: '/meshant-logo.png',
      tag: tag || 'meshant-notification',
      data: { url: url || '/' },
      requireInteraction: payload.requireInteraction || false,
      actions: payload.actions || [],
    })
  );
});

// ── Notification click: navigate to URL ──
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window' }).then((clients) => {
      const existing = clients.find((c) => c.url.includes(url));
      if (existing) {
        existing.focus();
      } else {
        self.clients.openWindow(url);
      }
    })
  );
});

// ── Push subscription change: notify server ──
self.addEventListener('pushsubscriptionchange', (event) => {
  event.waitUntil(
    fetch('/api/v1/notifications/push-subscription/', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        old_subscription: event.oldSubscription?.toJSON(),
        new_subscription: event.newSubscription?.toJSON(),
      }),
    })
  );
});
