// A tiny IndexedDB wrapper shared by the service worker and the pages.
//
// "outbox" holds changes made while offline (new tasks, edits, status
// clicks...) until they can be sent. "meta" holds small facts, such as whose
// pages are currently saved in this browser.
//
// Loaded with importScripts() in the service worker and with a <script> tag
// on every page, hence the `self`.

(function (root) {
    "use strict";

    var DB_NAME = "hangarin-offline";
    var DB_VERSION = 1;

    function open() {
        return new Promise(function (resolve, reject) {
            var request = indexedDB.open(DB_NAME, DB_VERSION);
            request.onupgradeneeded = function () {
                var db = request.result;
                if (!db.objectStoreNames.contains("outbox")) {
                    db.createObjectStore("outbox", { keyPath: "id", autoIncrement: true });
                }
                if (!db.objectStoreNames.contains("meta")) {
                    db.createObjectStore("meta");
                }
            };
            request.onsuccess = function () { resolve(request.result); };
            request.onerror = function () { reject(request.error); };
        });
    }

    // run one request inside a transaction and resolve with its result
    function run(storeName, mode, make) {
        return open().then(function (db) {
            return new Promise(function (resolve, reject) {
                var tx = db.transaction(storeName, mode);
                var req = make(tx.objectStore(storeName));
                tx.oncomplete = function () { db.close(); resolve(req ? req.result : undefined); };
                tx.onerror = tx.onabort = function () { db.close(); reject(tx.error); };
            });
        });
    }

    root.HangarinStore = {
        add: function (entry) {
            return run("outbox", "readwrite", function (s) { return s.add(entry); });
        },
        all: function () {
            return run("outbox", "readonly", function (s) { return s.getAll(); });
        },
        get: function (id) {
            return run("outbox", "readonly", function (s) { return s.get(id); });
        },
        remove: function (id) {
            return run("outbox", "readwrite", function (s) { return s.delete(id); });
        },
        update: function (id, patch) {
            return this.get(id).then(function (entry) {
                if (!entry) return;
                Object.keys(patch).forEach(function (key) { entry[key] = patch[key]; });
                return run("outbox", "readwrite", function (s) { return s.put(entry); });
            });
        },
        getMeta: function (key) {
            return run("meta", "readonly", function (s) { return s.get(key); });
        },
        setMeta: function (key, value) {
            return run("meta", "readwrite", function (s) { return s.put(value, key); });
        },
    };
})(self);
