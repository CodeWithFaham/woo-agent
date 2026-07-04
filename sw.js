// Minimal service worker - sirf PWA "install to home screen" ko enable karne
// ke liye zaroori hai. Koi offline caching complex nahi kar raha, taake
// live data hamesha fresh rahe.

self.addEventListener('install', function(event) {
  self.skipWaiting();
});

self.addEventListener('activate', function(event) {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', function(event) {
  // Network-first - hamesha live backend se fetch karo
  event.respondWith(fetch(event.request).catch(function() {
    return new Response('Offline - internet connection check karein.', {
      status: 503,
      headers: { 'Content-Type': 'text/plain' }
    });
  }));
});
