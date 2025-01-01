const CACHE_NAME = 'budget-app-v1';
const urlsToCache = [
  '/',
  '/static/css/styles.css',
  '/static/js/main.js',
  // Add other static assets you want to cache
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});
// app/static/js/service-worker.js
self.addEventListener('install', function(event) {
    event.waitUntil(
        caches.open('budget-app-v1').then(function(cache) {
            return cache.addAll([
                '/',
                '/static/css/style.css',
                '/static/js/main.js',
                '/static/images/icon.png'
            ]);
        })
    );
});

self.addEventListener('fetch', function(event) {
    event.respondWith(
        caches.match(event.request).then(function(response) {
            return response || fetch(event.request);
        })
    );
});
