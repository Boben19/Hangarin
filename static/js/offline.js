// Offline support, page side.
//
// The service worker keeps pages and holds changes made offline. This file
// does the rest:
//   - warms the cache with the pages you're likely to want offline
//   - shows a small status pill ("Offline", "2 changes waiting to sync")
//   - sends the waiting changes when the connection comes back
//   - makes search work on the page you have open when there's no network
//   - protects against logging out with unsynced changes
//
// Everything is skipped on pages without the hangarin-uid tag (login etc.).

(function () {
    "use strict";

    var uidMeta = document.querySelector('meta[name="hangarin-uid"]');
    var UID = uidMeta ? uidMeta.content : "";
    if (!UID || !window.HangarinStore || !("indexedDB" in window)) return;

    var WARM_KEY = "hangarin-warmed-at";
    var WARM_EVERY_MS = 5 * 60 * 1000;
    var BASE_PAGES = [
        "/", "/tasks/", "/subtasks/", "/notes/", "/categories/", "/priorities/", "/profile/",
        "/tasks/new/", "/subtasks/new/", "/notes/new/", "/categories/new/", "/priorities/new/"
    ];

    var bar = null, pill = null, panel = null, list = null, note = null;
    var flushing = false;
    var entries = [];

    function toast(message, kind) {
        if (typeof showToast === "function") showToast(message, kind);
    }

    function plural(n, word) { return n + " " + word + (n === 1 ? "" : "s"); }

    function icon(name) {
        var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("class", "i");
        svg.setAttribute("aria-hidden", "true");
        var use = document.createElementNS("http://www.w3.org/2000/svg", "use");
        use.setAttribute("href", "#i-" + name);
        svg.appendChild(use);
        return svg;
    }


    /* -----------------------------------------------------------
       The waiting list
       ----------------------------------------------------------- */

    function mine() {
        return HangarinStore.all().then(function (all) {
            entries = all.filter(function (e) { return e.uid === UID || !e.uid; });
            return entries;
        }).catch(function () { entries = []; return entries; });
    }

    function buildBar() {
        bar = document.createElement("div");
        bar.className = "sync-bar";
        bar.hidden = true;

        panel = document.createElement("div");
        panel.className = "sync-panel";
        panel.hidden = true;
        var title = document.createElement("h2");
        title.textContent = "Waiting to sync";
        note = document.createElement("p");
        note.className = "sync-note";
        list = document.createElement("ul");
        list.className = "sync-list";
        panel.appendChild(title);
        panel.appendChild(note);
        panel.appendChild(list);

        pill = document.createElement("button");
        pill.type = "button";
        pill.className = "sync-pill";
        pill.setAttribute("aria-expanded", "false");
        pill.addEventListener("click", function () {
            panel.hidden = !panel.hidden;
            pill.setAttribute("aria-expanded", String(!panel.hidden));
        });

        bar.appendChild(panel);
        bar.appendChild(pill);
        document.body.appendChild(bar);
    }

    function render() {
        if (!bar) buildBar();
        var offline = !navigator.onLine;
        var queued = entries.filter(function (e) { return e.state !== "failed"; });
        var failed = entries.filter(function (e) { return e.state === "failed"; });

        bar.classList.toggle("is-offline", offline);
        bar.classList.toggle("is-failed", !offline && failed.length > 0 && !flushing);
        bar.classList.toggle("is-syncing", flushing);

        var text = "";
        var iconName = "sync";
        if (flushing) {
            text = "Syncing " + plural(queued.length, "change") + "…";
        } else if (offline) {
            iconName = "offline";
            text = queued.length ? "Offline · " + queued.length + " waiting" : "Offline";
        } else if (failed.length) {
            iconName = "alert";
            text = plural(failed.length, "change") + " couldn't sync";
        } else if (queued.length) {
            text = plural(queued.length, "change") + " waiting to sync";
        }

        bar.hidden = !text;
        if (!text) { panel.hidden = true; return; }

        pill.textContent = "";
        pill.appendChild(icon(iconName));
        var span = document.createElement("span");
        span.textContent = text;
        pill.appendChild(span);

        note.textContent = offline
            ? "You're offline. Changes are saved on this device and sent when you reconnect."
            : "These are saved on this device and will be sent now.";

        list.textContent = "";
        entries.forEach(function (entry) {
            var li = document.createElement("li");
            li.className = "sync-item" + (entry.state === "failed" ? " is-failed" : "");
            var label = document.createElement("span");
            label.textContent = entry.label + (entry.state === "failed" ? " (rejected by the server)" : "");
            var drop = document.createElement("button");
            drop.type = "button";
            drop.textContent = "Discard";
            drop.addEventListener("click", function () {
                HangarinStore.remove(entry.id).then(refresh);
            });
            li.appendChild(label);
            li.appendChild(drop);
            list.appendChild(li);
        });
        if (!entries.length) panel.hidden = true;
    }

    function refresh() {
        return mine().then(render);
    }


    /* -----------------------------------------------------------
       Sending what was saved offline
       ----------------------------------------------------------- */

    function send(entry) {
        var body = new URLSearchParams();
        entry.fields.forEach(function (pair) {
            // the token saved with the form may belong to an older session
            body.append(pair[0], pair[0] === "csrfmiddlewaretoken" ? csrfToken() : pair[1]);
        });
        var headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": csrfToken(),
            "X-Hangarin-Replay": "1"
        };
        if (entry.xhr) headers["X-Requested-With"] = "XMLHttpRequest";
        return fetch(entry.url, { method: "POST", body: body, headers: headers, credentials: "same-origin" });
    }

    function flush() {
        if (flushing || !navigator.onLine) return Promise.resolve();
        flushing = true;
        var sent = 0;
        var stop = false;

        return mine().then(function () {
            var todo = entries.filter(function (e) { return e.state !== "failed"; })
                              .sort(function (a, b) { return a.id - b.id; });
            if (!todo.length) return;
            render();

            // one at a time, in the order they were made (a delete must not
            // overtake the edit before it)
            return todo.reduce(function (chain, entry) {
                return chain.then(function () {
                    if (stop) return;
                    return send(entry).then(function (res) {
                        if (res.redirected && /\/accounts\/login/.test(res.url)) {
                            stop = true;   // session ended: keep everything
                            toast("Log in again to sync your offline changes.", "error");
                            return;
                        }
                        if (res.status >= 500) { stop = true; return; }
                        var rejected = res.status >= 400 || (!entry.xhr && !res.redirected);
                        if (rejected) {
                            return HangarinStore.update(entry.id, { state: "failed" });
                        }
                        sent += 1;
                        return HangarinStore.remove(entry.id);
                    }).catch(function () { stop = true; });
                });
            }, Promise.resolve());
        }).then(function () {
            flushing = false;
            return refresh();
        }).then(function () {
            if (!sent) return;
            toast(plural(sent, "change") + " synced.", "success");
            // show the new state of the page, unless someone is mid-form
            if (!document.querySelector(".stack-form")) {
                window.setTimeout(function () { window.location.reload(); }, 700);
            }
        }).catch(function () {
            flushing = false;
            render();
        });
    }


    /* -----------------------------------------------------------
       Pages worth having offline
       ----------------------------------------------------------- */

    function send_to_worker(message) {
        if (!("serviceWorker" in navigator)) return;
        navigator.serviceWorker.ready.then(function (reg) {
            if (reg.active) reg.active.postMessage(message);
        });
    }

    // Pages linked from the one you're looking at (each task's page and edit
    // form, the next page of results). Only the ones not saved yet are fetched.
    function linkedPages() {
        var found = [];
        function add(path) { if (found.indexOf(path) === -1) found.push(path); }

        document.querySelectorAll("main a[href]").forEach(function (a) {
            var path = a.getAttribute("href");
            if (/^\/(tasks|subtasks|notes)\/\d+\/(edit\/)?$/.test(path)) add(path);
        });
        document.querySelectorAll("a.pager-btn[href]").forEach(function (a) {
            try {
                var u = new URL(a.getAttribute("href"), window.location.href);
                if (u.origin === window.location.origin) add(u.pathname + u.search);
            } catch (err) { /* ignore */ }
        });
        return found;
    }

    function warm() {
        if (!navigator.onLine) return;

        send_to_worker({ type: "warm", urls: linkedPages(), onlyMissing: true });

        // the main pages are refreshed at most every few minutes
        try {
            var last = parseInt(window.localStorage.getItem(WARM_KEY) || "0", 10);
            if (Date.now() - last < WARM_EVERY_MS) return;
            window.localStorage.setItem(WARM_KEY, String(Date.now()));
        } catch (err) { /* storage blocked: warm anyway */ }

        send_to_worker({ type: "warm", urls: BASE_PAGES.slice(), onlyMissing: false });
    }


    /* -----------------------------------------------------------
       Searching without a network: filter what's on the page
       ----------------------------------------------------------- */

    var filterNote = null;

    window.hgOfflineFilter = function (input) {
        var needle = input.value.trim().toLowerCase();
        document.querySelectorAll("[data-offline-item]").forEach(function (item) {
            var show = !needle || item.textContent.toLowerCase().indexOf(needle) !== -1;
            item.hidden = !show;
        });
        if (!filterNote) {
            filterNote = document.createElement("p");
            filterNote.className = "offline-filter-note";
            var toolbar = input.closest(".toolbar");
            if (toolbar) toolbar.insertAdjacentElement("afterend", filterNote);
        }
        filterNote.textContent = "Offline: searching only the items on this page.";
    };

    document.addEventListener("submit", function (e) {
        if (navigator.onLine) return;
        var form = e.target;
        if (form.classList && form.classList.contains("toolbar")) {
            e.preventDefault();
            var input = form.querySelector(".toolbar-search");
            if (input) window.hgOfflineFilter(input);
        }
    }, true);


    /* -----------------------------------------------------------
       Logging out
       ----------------------------------------------------------- */

    document.addEventListener("submit", function (e) {
        var form = e.target;
        if (!form.hasAttribute || !form.hasAttribute("data-logout")) return;

        if (!navigator.onLine) {
            e.preventDefault();
            toast("You need a connection to log out.", "error");
            return;
        }
        var waiting = entries.filter(function (x) { return x.state !== "failed"; }).length;
        if (waiting && !window.confirm(
            plural(waiting, "change") + " haven't synced yet. Log out anyway? " +
            "They stay on this device and sync the next time you log in."
        )) {
            e.preventDefault();
        }
    }, true);


    /* -----------------------------------------------------------
       Start
       ----------------------------------------------------------- */

    function showQueuedNotice() {
        var params = new URLSearchParams(window.location.search);
        if (!params.has("queued")) return;
        toast("Saved on this device. It will sync when you're back online.", "success");
        params.delete("queued");
        var query = params.toString();
        window.history.replaceState(null, "", window.location.pathname + (query ? "?" + query : ""));
    }

    // Status buttons clicked offline keep showing their new state when the
    // page is opened again from the saved copy.
    function replayStatusClicks() {
        entries.forEach(function (entry) {
            if (entry.state === "failed" || !/toggle-status\/$/.test(entry.url)) return;
            document.querySelectorAll('[data-toggle-url="' + entry.url + '"]').forEach(function (btn) {
                if (typeof localCycle === "function") {
                    localCycle(btn);
                    btn.classList.add("is-queued");
                }
            });
        });
    }

    window.addEventListener("online", function () {
        toast("Back online.", "success");
        refresh().then(flush).then(warm);
    });
    window.addEventListener("offline", function () {
        toast("You're offline. You can keep working; changes sync later.", "warning");
        render();
    });

    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.addEventListener("message", function (e) {
            if (e.data && e.data.type === "outbox-changed") refresh();
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        showQueuedNotice();
        mine().then(function () {
            replayStatusClicks();
            render();
            return flush();
        }).then(warm);
    });
})();
