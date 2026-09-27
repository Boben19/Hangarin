// A handful of small, independent bits of front-end polish.
// None of it is load-bearing — every page still works with JS off,
// this just makes the ones with it on feel a little more alive.

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

// Counts each stat card up from 0 to its real value once, on page load.
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

// Close the mobile nav automatically after picking a link, so it
// doesn't stay open when the next page loads.
function initMobileNavClose() {
    var navToggle = document.getElementById("nav-toggle");
    document.querySelectorAll(".sidebar a").forEach(function (link) {
        link.addEventListener("click", function () {
            if (navToggle) navToggle.checked = false;
        });
    });
}

// Success/error messages fade themselves out, or can be dismissed
// by hand with the little × button.
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

// Status badges/dots with a data-toggle-url double as buttons: one
// click cycles Pending -> In Progress -> Completed without leaving
// the page, via the toggle-status endpoints.
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
                    // Something went wrong (offline, expired session…) —
                    // reload so the page reflects whatever the real state is.
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

// Search boxes on the list pages submit themselves a moment after
// you stop typing, so results update without reaching for Enter.
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
