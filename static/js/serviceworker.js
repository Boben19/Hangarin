// Hangarin service worker.
//
// django-pwa serves this file at /serviceworker.js, which is what lets it
// control the whole site and not just /static/js/.
//
// What it does:
//   1. keeps the css, js and icons so the app opens instantly
//   2. keeps a copy of every signed-in page you open, and serves it when the
//      network is slow or gone (so your tasks are readable offline)
//   3. when you save something offline (new task, edit, delete, status
//      click...) it keeps the request in IndexedDB. The page sends it for
//      real once you're back online (see offline.js).
//
// Privacy: saved pages are wiped when you log out, and also when a different
// person signs in on this browser (each page the server sends carries an
// X-Hangarin-Uid tag, a one-way hash of the account).
//
// Changed a static file and don't see it? Bump VERSION below.

importScripts("/static/js/offline-store.js");

var VERSION = "v4";
var STATIC_CACHE = "hangarin-static-" + VERSION;
var PAGES_CACHE = "hangarin-pages";   // no version: an update shouldn't empty it
var MEDIA_CACHE = "hangarin-media";
var OFFLINE_URL = "/offline/";
var SLOW_NETWORK_MS = 4000;

// same paths as STATIC_URL in settings.py
var PRECACHE = [
    OFFLINE_URL,
    "/static/css/style.css",
    "/static/js/app.js",
    "/static/js/offline-store.js",
    "/static/js/offline.js",
    "/static/js/pwa.js",
    "/static/img/icon-192.png",
    "/static/img/icon-512.png"
];

// Saves that can wait for a connection: create/edit/delete/status for
// tasks, subtasks, notes, categories and priorities. Everything else
// (login, profile with its picture upload, account deletion) needs the server.
var QUEUEABLE = /^\/(tasks|subtasks|notes|categories|priorities)\/(new\/|\d+\/(edit|delete|toggle-status)\/)$/;


self.addEventListener("install", function (event) {
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(function (cache) { return cache.addAll(PRECACHE); })
            .then(function () { return self.skipWaiting(); })
    );
});

self.addEventListener("activate", function (event) {
    event.waitUntil(
        caches.keys()
            .then(function (names) {
                return Promise.all(names
                    .filter(function (n) { return n.indexOf("hangarin-static-") === 0 && n !== STATIC_CACHE; })
                    .map(function (n) { return caches.delete(n); }));
            })
            .then(function () { return self.clients.claim(); })
    );
});


/* ---------------------------------------------------------------
   Requests
   --------------------------------------------------------------- */

self.addEventListener("fetch", function (event) {
    var request = event.request;
    var url = new URL(request.url);
    if (url.origin !== self.location.origin) return;

    if (request.method === "POST") {
        handlePost(event, request, url);
        return;
    }
    if (request.method !== "GET") return;

    if (request.mode === "navigate") {
        event.respondWith(openPage(event, request, url));
    } else if (url.pathname.indexOf("/static/") === 0) {
        event.respondWith(cachedFile(event, STATIC_CACHE));
    } else if (url.pathname.indexOf("/media/") === 0) {
        event.respondWith(cachedFile(event, MEDIA_CACHE));
    }
    // everything else (csv export, json, manifest) goes straight through
});


// ---- opening a page ----

function neverSave(url) {
    return url.pathname.indexOf("/accounts/") === 0 ||
           url.pathname === OFFLINE_URL ||
           url.pathname.indexOf("/admin/") === 0 ||
           url.pathname === "/tasks/export/";
}

function openPage(event, request, url) {
    if (neverSave(url)) {
        return fetch(request).catch(offlineFallback);
    }

    var network = fetch(request).then(function (response) {
        // keep a copy for later, but hand the original straight back
        event.waitUntil(savePage(request, response.clone()));
        return response;
    });

    return caches.open(PAGES_CACHE).then(function (cache) {
        return cache.match(request, { ignoreVary: true }).then(function (saved) {
            if (!saved) {
                return network.catch(function () { return savedOrOffline(cache, request); });
            }
            // We have a copy. The network gets a few seconds; if it is slow
            // or down we show the copy instead of a spinner.
            event.waitUntil(network.catch(function () {}));
            return Promise.race([
                network.catch(function () { return saved; }),
                new Promise(function (resolve) { setTimeout(function () { resolve(saved); }, SLOW_NETWORK_MS); })
            ]);
        });
    });
}

// no exact copy (say, a search you never ran): the same page without the
// query string is better than nothing
function savedOrOffline(cache, request) {
    return cache.match(request, { ignoreSearch: true, ignoreVary: true })
        .then(function (saved) { return saved || offlineFallback(); });
}

function offlineFallback() {
    return caches.match(OFFLINE_URL);
}

function savePage(request, response) {
    var type = response.headers.get("Content-Type") || "";
    var uid = response.headers.get("X-Hangarin-Uid");
    // only signed-in HTML pages, never redirects or errors
    if (!uid || response.type !== "basic" || response.status !== 200 || type.indexOf("text/html") !== 0) {
        return Promise.resolve();
    }
    return switchUserIfNeeded(uid).then(function () {
        return caches.open(PAGES_CACHE);
    }).then(function (cache) {
        return cache.put(request, response);
    });
}

// If the tag changed, somebody else is signed in now: forget the old pages.
function switchUserIfNeeded(uid) {
    return HangarinStore.getMeta("uid").then(function (saved) {
        if (saved === uid) return;
        return purgeSaved().then(function () { return HangarinStore.setMeta("uid", uid); });
    });
}

function purgeSaved() {
    return Promise.all([caches.delete(PAGES_CACHE), caches.delete(MEDIA_CACHE)]);
}


// ---- css, js, icons and profile pictures: show the saved one, refresh behind it ----

function cachedFile(event, cacheName) {
    var request = event.request;
    return caches.open(cacheName).then(function (cache) {
        return cache.match(request).then(function (saved) {
            var fresh = fetch(request)
                .then(function (response) {
                    if (response && response.ok) cache.put(request, response.clone());
                    return response;
                })
                .catch(function () { return saved || Response.error(); });
            event.waitUntil(fresh);
            return saved || fresh;
        });
    });
}


/* ---------------------------------------------------------------
   Saving while offline
   --------------------------------------------------------------- */

function handlePost(event, request, url) {
    // Logging out wipes everything saved on this device. Only after the
    // server has confirmed, so a failed attempt doesn't empty the cache.
    if (url.pathname === "/accounts/logout/") {
        event.respondWith(
            fetch(request).then(
                function (response) { return purgeSaved().then(function () { return response; }); },
                offlineFallback
            )
        );
        return;
    }

    // the page is replaying something it saved earlier: send it as it is
    if (request.headers.get("X-Hangarin-Replay")) return;

    if (!QUEUEABLE.test(url.pathname)) {
        if (request.mode === "navigate") {
            event.respondWith(fetch(request).catch(offlineFallback));
        }
        return;
    }

    var copy = request.clone();
    event.respondWith(fetch(request).catch(function () { return queueRequest(copy, url); }));
}

function describe(path, fields) {
    var f = {};
    fields.forEach(function (pair) { f[pair[0]] = pair[1]; });
    var snippet = function (text) {
        text = (text || "").replace(/\s+/g, " ").trim();
        return text.length > 40 ? text.slice(0, 40) + "…" : text;
    };
    var kind = path.split("/")[1];
    var what = {
        tasks: "task", subtasks: "subtask", notes: "note", categories: "category", priorities: "priority"
    }[kind];
    var name = snippet(f.title || f.content || f.name);

    if (/toggle-status\/$/.test(path)) return "Change a " + what + " status";
    if (/delete\/$/.test(path)) return "Delete a " + what;
    if (/edit\/$/.test(path)) return "Edit " + what + (name ? ": " + name : "");
    return "New " + what + (name ? ": " + name : "");
}

// where to send the person after a queued form, so it feels like it saved
function landingFor(path, search, fields) {
    var next = "";
    fields.forEach(function (pair) { if (pair[0] === "next") next = pair[1]; });
    if (next && next.charAt(0) === "/" && next.charAt(1) !== "/") return next;

    var m = path.match(/^\/(tasks|subtasks|notes|categories|priorities)\/(?:(\d+)\/)?/);
    var section = m[1];
    var asked = (search.match(/[?&]task=(\d+)/) || [])[1];

    if (section === "tasks") return /edit\/$/.test(path) ? "/tasks/" + m[2] + "/" : "/tasks/";
    if (section === "subtasks" || section === "notes") return asked ? "/tasks/" + asked + "/" : "/" + section + "/";
    return "/" + section + "/";
}

function queueRequest(request, url) {
    var xhr = request.headers.get("X-Requested-With") === "XMLHttpRequest";
    var label = "";
    try { label = decodeURIComponent(request.headers.get("X-Hangarin-Label") || ""); } catch (e) { /* keep empty */ }

    // The status buttons send no body at all (the CSRF token is in a header),
    // and formData() throws on that, so an unreadable body just means "no fields".
    return request.formData().catch(function () { return new FormData(); }).then(function (data) {
        var fields = [];
        data.forEach(function (value, key) {
            if (typeof value === "string") fields.push([key, value]);
        });
        return HangarinStore.getMeta("uid").then(function (uid) {
            return HangarinStore.add({
                ts: Date.now(),
                uid: uid || "",
                url: url.pathname + url.search,
                fields: fields,
                xhr: xhr,
                label: label || describe(url.pathname, fields),
                state: "queued"
            }).then(function () {
                tellPages({ type: "outbox-changed" });
                if (xhr) {
                    return new Response(JSON.stringify({ queued: true }), {
                        status: 202,
                        headers: { "Content-Type": "application/json" }
                    });
                }
                var target = landingFor(url.pathname, url.search, fields);
                target += (target.indexOf("?") === -1 ? "?" : "&") + "queued=1";
                return Response.redirect(new URL(target, self.location.origin).href, 303);
            });
        });
    });
}

function tellPages(message) {
    return self.clients.matchAll({ type: "window" }).then(function (clients) {
        clients.forEach(function (client) { client.postMessage(message); });
    });
}


/* ---------------------------------------------------------------
   Messages from the page
   --------------------------------------------------------------- */

// "warm" = fetch these pages now, while there's a connection, so they are
// there when there isn't one.
self.addEventListener("message", function (event) {
    var data = event.data || {};

    if (data.type === "purge") {
        event.waitUntil(purgeSaved());
    } else if (data.type === "warm" && Array.isArray(data.urls)) {
        event.waitUntil(warm(data.urls, !!data.onlyMissing));
    }
});

function warm(urls, onlyMissing) {
    var queue = urls.slice(0, 60);
    return caches.open(PAGES_CACHE).then(function (cache) {
        var workers = [0, 1, 2].map(function () {
            return (function next() {
                var path = queue.shift();
                if (!path) return Promise.resolve();
                var already = onlyMissing
                    ? cache.match(path, { ignoreVary: true })
                    : Promise.resolve(null);
                return already.then(function (hit) {
                    if (hit) return;
                    return fetch(path, { credentials: "same-origin" })
                        .then(function (response) { return savePage(new Request(path), response); });
                }).catch(function () { /* one failure shouldn't stop the rest */ }).then(next);
            })();
        });
        return Promise.all(workers);
    });
}
