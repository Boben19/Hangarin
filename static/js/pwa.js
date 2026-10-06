// PWA bits: registers the service worker and runs the "Install Hangarin"
// button. (Online/offline messages live in offline.js.)
//
// The registration is here, in a file on our own domain, because the
// Content-Security-Policy in middleware.py only allows scripts from this site.

(function () {
    "use strict";

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
        if (typeof showToast === "function") showToast(message, kind);
    }

    if (!alreadyInstalled) {
        if (onIos) showInstall(true);

        window.addEventListener("beforeinstallprompt", function (e) {
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
                    savedPrompt = null;   // it can only be used once
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
        say("Hangarin is installed.", "success");
    });
})();
