// small extras, the site still works without JS

document.addEventListener("DOMContentLoaded", function () {
    initStatCounters();
    initMobileNavClose();
    initToasts();
    initStatusToggles();
    initSearchAutoSubmit();
});

function getCookie(name) {
    var value = null;
    document.cookie.split(";").forEach(function (part) {
        part = part.trim();
        if (part.indexOf(name + "=") === 0) {
            value = decodeURIComponent(part.slice(name.length + 1));
        }
    });
    return value;
}

// stat numbers count up on load
function initStatCounters() {
    var prefersReducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
    ).matches;

    document.querySelectorAll(".stat-number[data-count]").forEach(function (el) {
        var target = parseInt(el.getAttribute("data-count"), 10) || 0;

        if (prefersReducedMotion || target === 0) {
            el.textContent = target;
            return;
        }

        var duration = 700;
        var start = null;

        function step(timestamp) {
            if (start === null) start = timestamp;
            var progress = Math.min((timestamp - start) / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = Math.round(eased * target);
            if (progress < 1) {
                window.requestAnimationFrame(step);
            }
        }

        window.requestAnimationFrame(step);
    });
}

// close the mobile menu after tapping a link
function initMobileNavClose() {
    var navToggle = document.getElementById("nav-toggle");
    document.querySelectorAll(".sidebar a").forEach(function (link) {
        link.addEventListener("click", function () {
            if (navToggle) navToggle.checked = false;
        });
    });
}

// toasts fade out on their own, or close with the x
function initToasts() {
    var stack = document.getElementById("toast-stack");
    if (!stack) return;

    function dismiss(toast) {
        toast.classList.add("toast-leaving");
        window.setTimeout(function () {
            toast.remove();
        }, 250);
    }

    stack.querySelectorAll(".toast").forEach(function (toast) {
        var timer = window.setTimeout(function () { dismiss(toast); }, 4500);
        var closeBtn = toast.querySelector(".toast-close");
        if (closeBtn) {
            closeBtn.addEventListener("click", function () {
                window.clearTimeout(timer);
                dismiss(toast);
            });
        }
    });
}

// click a status badge to cycle Pending -> In Progress -> Completed
function initStatusToggles() {
    document.querySelectorAll("[data-toggle-url]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            if (btn.disabled) return;
            var url = btn.getAttribute("data-toggle-url");
            btn.disabled = true;
            btn.classList.add("is-updating");

            fetch(url, {
                method: "POST",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": getCookie("csrftoken"),
                },
            })
                .then(function (res) {
                    if (!res.ok) throw new Error("toggle failed");
                    return res.json();
                })
                .then(function (data) { applyStatus(btn, data); })
                .catch(function () {
                    // request failed, just reload
                    window.location.reload();
                })
                .finally(function () {
                    btn.disabled = false;
                    btn.classList.remove("is-updating");
                });
        });
    });
}

function swapPrefixedClass(el, prefix, newValue) {
    Array.from(el.classList).forEach(function (cls) {
        if (cls.indexOf(prefix) === 0) el.classList.remove(cls);
    });
    el.classList.add(prefix + newValue);
}

function applyStatus(el, data) {
    if (el.classList.contains("badge")) {
        swapPrefixedClass(el, "badge-", data.slug);
        el.textContent = data.label;
    } else {
        swapPrefixedClass(el, "status-", data.slug);
    }

    if (el.classList.contains("subtask-check")) {
        el.textContent = data.slug === "completed" ? "\u2713" : "";
    }

    var row = el.closest(".subtask-row");
    if (row) {
        var badge = row.querySelector(".subtask-badge");
        if (badge) {
            swapPrefixedClass(badge, "badge-", data.slug);
            badge.textContent = data.label;
        }
    }

    var card = el.closest(".task-card");
    if (card) swapPrefixedClass(card, "status-", data.slug);

    var head = el.closest(".detail-head");
    if (head) swapPrefixedClass(head, "status-", data.slug);
}

// list search submits half a second after you stop typing
function initSearchAutoSubmit() {
    document.querySelectorAll(".toolbar-search").forEach(function (input) {
        var timer = null;
        input.addEventListener("input", function () {
            window.clearTimeout(timer);
            timer = window.setTimeout(function () {
                input.form.submit();
            }, 500);
        });
    });
}

// fade out before following an internal link (not new tabs, downloads, #anchors)
document.addEventListener("click", function (e) {
    var link = e.target.closest("a[href]");
    if (!link) return;
    var href = link.getAttribute("href");
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    if (link.target === "_blank" || link.hasAttribute("download")) return;
    if (!href || href.charAt(0) === "#" || link.origin !== window.location.origin) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    e.preventDefault();
    document.body.classList.add("is-leaving");
    window.setTimeout(function () { window.location.href = link.href; }, 170);
});

// back button restores the page with the fade class still on
window.addEventListener("pageshow", function () {
    document.body.classList.remove("is-leaving");
});
