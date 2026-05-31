/* ══════════════════════════════════════════
   Service Worker — 离线缓存与静态资源预缓存
   ══════════════════════════════════════════ */

const CACHE_NAME = 'index-fund-v1';
const STATIC_ASSETS = [
  '.',
  'index.html',
  'css/style.css',
  'js/config.js',
  'js/storage.js',
  'js/api.js',
  'js/charts.js',
  'js/dashboard.js',
  'js/strategy.js',
  'js/history.js',
  'js/profit.js',
  'js/manual.js',
  'js/app.js',
  'manifest.json',
  'assets/favicon.svg',
];

// ── 安装：预缓存静态资源 ──
self.addEventListener('install', (event) => {
  console.log('[SW] 安装中...');
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(STATIC_ASSETS);
    }).then(() => {
      console.log('[SW] 静态资源已缓存');
      return self.skipWaiting();
    })
  );
});

// ── 激活：清理旧缓存 ──
self.addEventListener('activate', (event) => {
  console.log('[SW] 激活');
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      );
    }).then(() => self.clients.claim())
  );
});

// ── 请求拦截：缓存优先策略 ──
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // CDN 资源（Chart.js）：网络优先
  if (url.hostname.includes('cdn.jsdelivr.net')) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        return cached || fetch(event.request).then(resp => {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          return resp;
        });
      })
    );
    return;
  }

  // GitHub Raw 数据：网络优先，失败时使用缓存
  if (url.hostname.includes('raw.githubusercontent.com')) {
    event.respondWith(
      fetch(event.request).then(resp => {
        const clone = resp.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        return resp;
      }).catch(() => {
        return caches.match(event.request);
      })
    );
    return;
  }

  // 静态资源：缓存优先
  event.respondWith(
    caches.match(event.request).then(cached => {
      return cached || fetch(event.request);
    })
  );
});
