// Hangarin service worker.
//
// django-pwa serves this file at /serviceworker.js (that's what lets it
// control the whole site, not just /static/js/). It does two things:
//
//   1. keeps the css, js and icons so the app opens fast
//   2. shows /offline/ when a page can't be loaded
//
// Pages with someone's tasks on them are NOT cached. They're private, they
// change all the time, and a saved copy would still be there after logging
// out on a shared computer. Since the tasks live on the server, going
// offline means you see the offline page, not old data.
//
// Changed a static file and don't see it? Bump VERSION below.

var VERSION = 'v1';
var STATIC_CACHE = 'hangarin-static-' + VERSION;
var OFFLINE_URL = '/offline/';

// same paths as STATIC_URL in settings.py
var PRECACHE = [
    OFFLINE_URL,
    '/static/css/style.css',
    '/static/js/app.js',
    '/static/js/pwa.js',
    '/static/img/icon-192.png',
    '/static/img/icon-512.png'
];


self.addEventListener('install', function (event) {
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(function (cache) { return cache.addAll(PRECACHE); })
            .then(function () { return self.skipWaiting(); })
    );
});


// clear out caches from older versions
self.addEventListener('activate', function (event) {
    event.waitUntil(
        caches.keys()
            .then(function (names) {
                return Promise.all(
                    names
                        .filter(function (name) {
                            return name.indexOf('hangarin-') === 0 && name !== STATIC_CACHE;
                        })
                        .map(function (name) { return caches.delete(name); })
                );
            })
            .then(function () { return self.clients.claim(); })
    );
});


self.addEventListener('fetch', function (event) {
    var request = event.request;

    // saving, deleting, logging in... always go straight to the server
    if (request.method !== 'GET') return;

    var url = new URL(request.url);

    // Google Fonts and anything else off-site: let the browser deal with it.
    // (The site's CSP only lets fetch() talk to our own domain anyway.)
    if (url.origin !== self.location.origin) return;

    // opening a page: always try the network, fall back to the offline page
    if (request.mode === 'navigate') {
        event.respondWith(
            fetch(request).catch(function () {
                return caches.match(OFFLINE_URL);
            })
        );
        return;
    }

    if (url.pathname.indexOf('/static/') === 0) {
        event.respondWith(staticFile(event));
    }
    // everything else (profile pictures, csv export, json) is not touched
});


// Serve the saved copy right away and refresh it in the background, so a
// changed stylesheet shows up on the next visit.
function staticFile(event) {
    var request = event.request;

    return caches.open(STATIC_CACHE).then(function (cache) {
        return cache.match(request).then(function (saved) {
            var fresh = fetch(request)
                .then(function (response) {
                    if (response && response.ok) cache.put(request, response.clone());
                    return response;
                })
                .catch(function () {
                    return saved || Response.error();
                });

            // keep the worker alive until the refresh has finished
            event.waitUntil(fresh);
            return saved || fresh;
        });
    });
}
