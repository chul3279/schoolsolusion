// SchoolUs Service Worker v3.0
const CACHE_NAME = 'schoolus-v3';
const STATIC_CACHE = 'schoolus-static-v3';
const API_CACHE = 'schoolus-api-v3';

// 오프라인 시 캐시할 핵심 정적 리소스
const PRECACHE_URLS = [
  '/index.html',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  '/manifest.json'
];

// 캐시 대상 정적 리소스 패턴 (HTML 제외 — HTML은 Network-first)
const STATIC_PATTERNS = [
  /\.css$/,
  /\.js$/,
  /\.png$/,
  /\.jpg$/,
  /\.jpeg$/,
  /\.gif$/,
  /\.svg$/,
  /\.ico$/,
  /\.woff2?$/,
  /fonts\.googleapis\.com/,
  /cdnjs\.cloudflare\.com/
];

// 캐시 제외 패턴
const NO_CACHE_PATTERNS = [
  /\/api\//,
  /\/login_process/,
  /google-analytics\.com/,
  /googletagmanager\.com/
];

// ============================================
// Install: 핵심 리소스 프리캐시
// ============================================
self.addEventListener('install', (event) => {
  console.log('[SW] Installing Service Worker v3');
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => {
        console.log('[SW] Pre-caching core assets');
        return cache.addAll(PRECACHE_URLS);
      })
      .then(() => self.skipWaiting())
  );
});

// ============================================
// Activate: 오래된 캐시 정리
// ============================================
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating Service Worker v3');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== STATIC_CACHE && name !== API_CACHE && name !== CACHE_NAME)
          .map((name) => {
            console.log('[SW] Deleting old cache:', name);
            return caches.delete(name);
          })
      );
    }).then(() => self.clients.claim())
  );
});

// ============================================
// Fetch: Network-first (API), Cache-first (정적)
// ============================================
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // POST 등 GET 아닌 요청은 캐시하지 않음
  if (request.method !== 'GET') return;

  // 캐시 제외 대상
  if (NO_CACHE_PATTERNS.some((p) => p.test(url.href))) return;

  // HTML 페이지: Network-first (항상 최신 버전 우선)
  if (request.destination === 'document' || /\.html$/.test(url.pathname) || url.pathname === '/') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match(request).then((c) => c || caches.match('/index.html')))
    );
    return;
  }

  // 정적 리소스(CSS/JS/이미지): Cache-first, network fallback
  if (STATIC_PATTERNS.some((p) => p.test(url.pathname) || p.test(url.href))) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(STATIC_CACHE).then((cache) => cache.put(request, clone));
          }
          return response;
        });
      }).catch(() => {
        // 오프라인 fallback
        if (request.destination === 'document') {
          return caches.match('/index.html');
        }
      })
    );
    return;
  }

  // 기타: Network-first
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      })
      .catch(() => caches.match(request))
  );
});

// ============================================
// Push: 알림 수신
// ============================================
self.addEventListener('push', (event) => {
  console.log('[SW] Push received');
  let data = { title: 'SchoolUs', body: '새로운 알림이 있습니다.', icon: '/static/icons/icon-192x192.png' };

  if (event.data) {
    try {
      data = { ...data, ...event.data.json() };
    } catch (e) {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: data.icon || '/static/icons/icon-192x192.png',
    badge: '/static/icons/icon-72x72.png',
    vibrate: [100, 50, 100],
    data: {
      url: data.url || '/',
      dateOfArrival: Date.now()
    },
    actions: data.actions || []
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// ============================================
// Notification Click: 알림 클릭 시 앱 열기
// ============================================
self.addEventListener('notificationclick', (event) => {
  console.log('[SW] Notification clicked');
  event.notification.close();

  const targetUrl = event.notification.data?.url || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        // 이미 열린 창이 있으면 포커스
        for (const client of clientList) {
          if (client.url.includes(self.location.origin) && 'focus' in client) {
            client.navigate(targetUrl);
            return client.focus();
          }
        }
        // 없으면 새 창
        return clients.openWindow(targetUrl);
      })
  );
});
