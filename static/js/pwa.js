// PWA bits: registers the service worker, wires up the "Install Hangarin"
// button, and says something when the connection drops.
//
// The registration lives here (a file on our own domain) instead of in an
// inline <script>, because the Content-Security-Policy in middleware.py
// only allows scripts from this site.

(function () {
    "use strict";

    /* -----------------------------------------------------------
       Service worker
       ----------------------------------------------------------- */

    if ("serviceWorker" in navigator) {
        window.addEventListener("load", function () {
            navigator.serviceWorker
                .register("/serviceworker.js", { scope: "/" })
                .catch(function (err) {
                    // not fatal, the site just works like a normal website
                    console.warn("Service worker did not register:", err);
                });
        });
    }


    /* -----------------------------------------------------------
       Install button
       ----------------------------------------------------------- */

    var buttons = document.querySelectorAll("[data-install]");
    var savedPrompt = null;

    var alreadyInstalled =
        window.matchMedia("(display-mode: standalone)").matches ||
        window.navigator.standalone === true;

    // Safari on iPhone/iPad never fires beforeinstallprompt, you have to use
    // the Share sheet. iPads report themselves as a Mac, hence the second check.
    var onIos =
        /iphone|ipad|ipod/i.test(navigator.userAgent) ||
        (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

    function showInstall(visible) {
        buttons.forEach(function (btn) { btn.hidden = !visible; });
    }

    function say(message, kind) {
        // showToast comes from app.js
        if (typeof showToast === "function") showToast(message, kind);
    }

    if (!alreadyInstalled) {
        if (onIos) showInstall(true);

        window.addEventListener("beforeinstallprompt", function (e) {
            // hold on to it so the button can trigger it later
            e.preventDefault();
            savedPrompt = e;
            showInstall(true);
        });
    }

    buttons.forEach(function (btn) {
        btn.addEventListener("click", function () {
            if (savedPrompt) {
                savedPrompt.prompt();
                savedPrompt.userChoice.then(function () {
                    // the prompt can only be used once
                    savedPrompt = null;
                    showInstall(false);
                });
            } else if (onIos) {
                say('Tap the Share button, then "Add to Home Screen".', "success");
            }
        });
    });

    window.addEventListener("appinstalled", function () {
        savedPrompt = null;
        showInstall(false);
        say("Hangarin is installed. You'll find it with your other apps.", "success");
    });


    /* -----------------------------------------------------------
       Online / offline
       ----------------------------------------------------------- */

    window.addEventListener("offline", function () {
        say("You're offline. Changes won't save until you're back.", "error");
    });

    window.addEventListener("online", function () {
        say("Back online.", "success");
    });

    document.querySelectorAll("[data-logout-form]").forEach(function (form) {
        form.addEventListener("submit", function () {
            if (navigator.serviceWorker && navigator.serviceWorker.controller) {
                navigator.serviceWorker.controller.postMessage({ type: "HANGARIN_CLEAR_PRIVATE_CACHE" });
            }
        });
    });

})();
