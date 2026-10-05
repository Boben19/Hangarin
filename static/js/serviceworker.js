var VERSION = 'v2';
var STATIC_CACHE = 'hangarin-static-' + VERSION;
var PAGE_CACHE = 'hangarin-pages-' + VERSION;
var OFFLINE_URL = '/offline/';
var PRECACHE = [OFFLINE_URL, '/static/css/style.css', '/static/js/app.js', '/static/js/pwa.js', '/static/img/icon-192.png', '/static/img/icon-512.png'];

self.addEventListener('install', function (event) {
    event.waitUntil(caches.open(STATIC_CACHE).then(function (cache) { return cache.addAll(PRECACHE); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (event) {
    event.waitUntil(caches.keys().then(function (names) {
        return Promise.all(names.filter(function (name) { return name.indexOf('hangarin-') === 0 && name !== STATIC_CACHE && name !== PAGE_CACHE; }).map(function (name) { return caches.delete(name); }));
    }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('message', function (event) {
    if (event.data && event.data.type === 'HANGARIN_CLEAR_PRIVATE_CACHE') event.waitUntil(caches.delete(PAGE_CACHE));
});

self.addEventListener('fetch', function (event) {
    var request = event.request;
    if (request.method !== 'GET') return;
    var url = new URL(request.url);
    if (url.origin !== self.location.origin) return;

    if (request.mode === 'navigate') {
        var blocked = url.pathname.indexOf('/accounts/') === 0 || url.pathname.indexOf('/admin/') === 0 || url.pathname === OFFLINE_URL || url.pathname === '/serviceworker.js' || url.pathname === '/manifest.json';
        if (blocked) {
            event.respondWith(fetch(request).catch(function () { return caches.match(OFFLINE_URL); }));
            return;
        }
        event.respondWith(fetch(request).then(function (response) {
            if (response && response.ok && response.type === 'basic') caches.open(PAGE_CACHE).then(function (cache) { cache.put(request, response.clone()); });
            return response;
        }).catch(function () {
            return caches.match(request).then(function (cached) { return cached || caches.match(OFFLINE_URL); });
        }));
        return;
    }
    if (url.pathname.indexOf('/static/') === 0) event.respondWith(staticFile(request));
});

function staticFile(request) {
    return caches.open(STATIC_CACHE).then(function (cache) {
        return cache.match(request).then(function (saved) {
            return fetch(request).then(function (response) {
                if (response && response.ok) cache.put(request, response.clone());
                return response;
            }).catch(function () { return saved || Response.error(); }) || saved;
        });
    });
}
