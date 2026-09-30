// Hangarin front-end extras.
// Everything here is a bonus: every page still works with JavaScript off.

var REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

document.addEventListener("DOMContentLoaded", function () {
    initStatCounters();
    initMobileNavClose();
    initToasts();
    initStatusToggles();
    initSearchAutoSubmit();
    initThemeToggle();
    initAvatarPreview();
});


/* ---------------------------------------------------------------
   Small helpers
   --------------------------------------------------------------- */

// The CSRF cookie is HttpOnly (so scripts can't steal it), which means
// document.cookie can't see it. The page puts the token in a <meta> tag.
function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
}

function swapPrefixedClass(el, prefix, newValue) {
    Array.from(el.classList).forEach(function (cls) {
        // "status-toggle" is a hook for this script, not a status colour
        if (cls.indexOf(prefix) === 0 && cls !== "status-toggle") el.classList.remove(cls);
    });
    el.classList.add(prefix + newValue);
}

function isTyping(target) {
    if (!target) return false;
    return target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName);
}


/* ---------------------------------------------------------------
   Numbers count up on load
   --------------------------------------------------------------- */

function initStatCounters() {
    document.querySelectorAll("[data-count]").forEach(function (el) {
        var target = parseInt(el.getAttribute("data-count"), 10) || 0;

        // the server already wrote the real number, so no-JS and reduced
        // motion both just keep it
        if (REDUCED_MOTION || target === 0) {
            el.textContent = target;
            return;
        }

        var duration = 700;
        var start = null;
        el.textContent = "0";

        function step(timestamp) {
            if (start === null) start = timestamp;
            var progress = Math.min((timestamp - start) / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = Math.round(eased * target);
            if (progress < 1) window.requestAnimationFrame(step);
        }
        window.requestAnimationFrame(step);
    });
}


/* ---------------------------------------------------------------
   Mobile menu closes after you pick something
   --------------------------------------------------------------- */

function initMobileNavClose() {
    var navToggle = document.getElementById("nav-toggle");
    document.querySelectorAll(".sidebar a").forEach(function (link) {
        link.addEventListener("click", function () {
            if (navToggle) navToggle.checked = false;
        });
    });
}


/* ---------------------------------------------------------------
   Toasts
   --------------------------------------------------------------- */

function armToast(toast) {
    function dismiss() {
        toast.classList.add("toast-leaving");
        window.setTimeout(function () { toast.remove(); }, 250);
    }
    var timer = window.setTimeout(dismiss, 4500);
    var closeBtn = toast.querySelector(".toast-close");
    if (closeBtn) {
        closeBtn.addEventListener("click", function () {
            window.clearTimeout(timer);
            dismiss();
        });
    }
}

function initToasts() {
    document.querySelectorAll("#toast-stack .toast").forEach(armToast);
}

// used for things that happen without a page load (level up, goal reached)
function showToast(message, kind) {
    var stack = document.getElementById("toast-stack");
    if (!stack) {
        stack = document.createElement("div");
        stack.id = "toast-stack";
        stack.className = "toast-stack";
        stack.setAttribute("role", "status");
        document.body.appendChild(stack);
    }
    var toast = document.createElement("div");
    toast.className = "toast toast-" + (kind || "success");

    var text = document.createElement("span");
    text.textContent = message;
    var close = document.createElement("button");
    close.type = "button";
    close.className = "toast-close";
    close.setAttribute("aria-label", "Dismiss");
    close.innerHTML = "&times;";

    toast.appendChild(text);
    toast.appendChild(close);
    stack.appendChild(toast);
    armToast(toast);
}


/* ---------------------------------------------------------------
   Click a status to cycle Pending -> In Progress -> Completed
   --------------------------------------------------------------- */

function initStatusToggles() {
    document.querySelectorAll("[data-toggle-url]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            if (btn.disabled) return;
            var url = btn.getAttribute("data-toggle-url");
            btn.disabled = true;
            btn.classList.add("is-updating");

            fetch(url, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": csrfToken(),
                },
            })
                .then(function (res) {
                    if (!res.ok) throw new Error("toggle failed");
                    return res.json();
                })
                .then(function (data) {
                    applyStatus(btn, data);
                    celebrate(btn, data);
                })
                .catch(function () {
                    // something went wrong (logged out, offline...), so show
                    // the real state instead of pretending
                    window.location.reload();
                })
                .finally(function () {
                    btn.disabled = false;
                    btn.classList.remove("is-updating");
                });
        });
    });
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

    if (data.progress && data.parent) updateProgress(data.parent, data.progress);

    el.classList.remove("pop");
    void el.offsetWidth; // restart the animation
    el.classList.add("pop");
    window.setTimeout(function () { el.classList.remove("pop"); }, 450);
}

function updateProgress(parentId, p) {
    var selector = '[data-progress-for="' + parentId + '"], [data-progress-bar="' + parentId + '"]';
    document.querySelectorAll(selector).forEach(function (box) {
        var done = box.querySelector("[data-done]");
        var total = box.querySelector("[data-total]");
        if (done) done.textContent = p.done;
        if (total) total.textContent = p.total;

        var bar = box.classList.contains("bar") ? box : box.querySelector(".bar");
        if (bar) {
            bar.setAttribute("aria-valuenow", p.pct);
            var fill = bar.querySelector(".bar-fill");
            if (fill) fill.style.setProperty("--p", p.pct + "%");
        }
    });
}

function celebrate(btn, data) {
    if (!data.celebrate) return;
    var rect = btn.getBoundingClientRect();
    var big = !!(data.goal_hit || data.level_up);
    confetti(rect.left + rect.width / 2, rect.top + rect.height / 2, big);

    if (data.level_up) {
        showToast(
            "Level up! You're level " + data.level_up.level + " now: " + data.level_up.title + ".",
            "level"
        );
    } else if (data.goal_hit) {
        showToast("That's your daily goal of " + data.goal + ". Nice work.", "level");
    }
}


/* ---------------------------------------------------------------
   Confetti (a short burst from wherever you clicked)
   --------------------------------------------------------------- */

function confetti(originX, originY, big) {
    if (REDUCED_MOTION) return;

    var old = document.querySelector(".confetti-canvas");
    if (old) old.remove();

    var canvas = document.createElement("canvas");
    canvas.className = "confetti-canvas";
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    canvas.setAttribute("aria-hidden", "true");
    document.body.appendChild(canvas);

    var ctx = canvas.getContext("2d");
    if (!ctx) { canvas.remove(); return; }

    var colors = ["#3ea673", "#8fe3ab", "#2f8a5f", "#f0b556", "#7cb0f2", "#ffffff"];
    var count = big ? 150 : 42;
    var pieces = [];

    for (var i = 0; i < count; i++) {
        var angle = (-Math.PI / 2) + (Math.random() - 0.5) * (big ? 2.6 : 1.7);
        var speed = (big ? 9 : 6) + Math.random() * (big ? 9 : 5);
        pieces.push({
            x: originX,
            y: originY,
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed,
            size: 5 + Math.random() * 5,
            spin: (Math.random() - 0.5) * 0.4,
            rot: Math.random() * Math.PI,
            color: colors[Math.floor(Math.random() * colors.length)],
        });
    }

    var startedAt = null;
    var lifetime = big ? 2600 : 1800;

    function frame(now) {
        if (startedAt === null) startedAt = now;
        var age = now - startedAt;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        pieces.forEach(function (p) {
            p.vy += 0.32;      // gravity
            p.vx *= 0.99;      // air drag
            p.x += p.vx;
            p.y += p.vy;
            p.rot += p.spin;

            ctx.save();
            ctx.globalAlpha = Math.max(0, 1 - age / lifetime);
            ctx.translate(p.x, p.y);
            ctx.rotate(p.rot);
            ctx.fillStyle = p.color;
            ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
            ctx.restore();
        });

        if (age < lifetime) {
            window.requestAnimationFrame(frame);
        } else {
            canvas.remove();
        }
    }
    window.requestAnimationFrame(frame);
}


/* ---------------------------------------------------------------
   Light / dark button (the choice is saved on your profile, so it
   follows you to other devices)
   --------------------------------------------------------------- */

function currentTheme() {
    var set = document.documentElement.getAttribute("data-theme") || "system";
    if (set === "system") {
        return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    return set;
}

function initThemeToggle() {
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var next = currentTheme() === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", next);

            btn.classList.add("is-spinning");
            window.setTimeout(function () { btn.classList.remove("is-spinning"); }, 450);

            var url = btn.getAttribute("data-theme-url");
            if (!url) return;
            fetch(url, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": csrfToken(),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                body: "theme=" + encodeURIComponent(next),
            }).catch(function () {
                // not saved, but the page already changed and that's fine
            });
        });
    });
}


/* ---------------------------------------------------------------
   Search boxes send themselves half a second after you stop typing
   --------------------------------------------------------------- */

var SEARCH_FOCUS_KEY = "hangarin-keep-search-focus";

function initSearchAutoSubmit() {
    document.querySelectorAll(".toolbar-search").forEach(function (input) {
        var timer = null;

        // the page reloads on every search, so give the cursor back
        try {
            if (window.sessionStorage.getItem(SEARCH_FOCUS_KEY) === "1") {
                window.sessionStorage.removeItem(SEARCH_FOCUS_KEY);
                input.focus();
                var end = input.value.length;
                input.setSelectionRange(end, end);
            }
        } catch (err) { /* storage can be blocked, nothing to do */ }

        input.addEventListener("input", function () {
            window.clearTimeout(timer);
            timer = window.setTimeout(function () {
                try { window.sessionStorage.setItem(SEARCH_FOCUS_KEY, "1"); } catch (err) { /* ignore */ }
                input.form.submit();
            }, 500);
        });
    });
}


/* ---------------------------------------------------------------
   Picking a new profile picture shows it right away
   --------------------------------------------------------------- */

function initAvatarPreview() {
    var input = document.querySelector("input.avatar-file");
    var box = document.querySelector("[data-avatar-preview]");
    if (!input || !box) return;

    input.addEventListener("change", function () {
        var file = input.files && input.files[0];
        if (!file || file.type.indexOf("image/") !== 0) return;

        var img = document.createElement("img");
        img.className = "avatar avatar-xl";
        img.alt = "";
        img.src = URL.createObjectURL(file);
        box.textContent = "";
        box.appendChild(img);
    });
}


/* ---------------------------------------------------------------
   Pointer glow and button ripple
   --------------------------------------------------------------- */

document.addEventListener("pointermove", function (e) {
    if (REDUCED_MOTION || !e.target.closest) return;
    var el = e.target.closest("[data-glow]");
    if (!el) return;
    var rect = el.getBoundingClientRect();
    el.style.setProperty("--mx", (e.clientX - rect.left) + "px");
    el.style.setProperty("--my", (e.clientY - rect.top) + "px");
});

document.addEventListener("click", function (e) {
    if (REDUCED_MOTION || !e.target.closest) return;
    var btn = e.target.closest(".btn");
    if (!btn) return;

    var rect = btn.getBoundingClientRect();
    var size = Math.max(rect.width, rect.height);
    var wave = document.createElement("span");
    wave.className = "ripple";
    wave.style.width = wave.style.height = size + "px";
    wave.style.left = (e.clientX - rect.left - size / 2) + "px";
    wave.style.top = (e.clientY - rect.top - size / 2) + "px";
    btn.appendChild(wave);
    window.setTimeout(function () { wave.remove(); }, 600);
});


/* ---------------------------------------------------------------
   Keyboard shortcuts:  N new task,  / search,  ? help,  Esc close
   --------------------------------------------------------------- */

function closeShortcutSheet() {
    var sheet = document.querySelector(".shortcut-sheet");
    if (sheet) sheet.remove();
}

function openShortcutSheet() {
    if (document.querySelector(".shortcut-sheet")) return;

    var sheet = document.createElement("div");
    sheet.className = "shortcut-sheet";
    sheet.setAttribute("role", "dialog");
    sheet.setAttribute("aria-modal", "true");
    sheet.setAttribute("aria-label", "Keyboard shortcuts");

    var card = document.createElement("div");
    card.className = "shortcut-card";

    var title = document.createElement("h2");
    title.textContent = "Keyboard shortcuts";
    card.appendChild(title);

    var list = document.createElement("ul");
    [
        ["N", "Add a new task"],
        ["/", "Jump to search"],
        ["?", "Show this list"],
        ["Esc", "Close or leave a box"],
    ].forEach(function (row) {
        var li = document.createElement("li");
        var label = document.createElement("span");
        label.textContent = row[1];
        var key = document.createElement("kbd");
        key.textContent = row[0];
        li.appendChild(label);
        li.appendChild(key);
        list.appendChild(li);
    });
    card.appendChild(list);

    var close = document.createElement("button");
    close.type = "button";
    close.className = "btn btn-outline-green btn-small shortcut-close";
    close.textContent = "Got it";
    close.addEventListener("click", closeShortcutSheet);
    card.appendChild(close);

    sheet.appendChild(card);
    sheet.addEventListener("click", function (e) {
        if (e.target === sheet) closeShortcutSheet();
    });
    document.body.appendChild(sheet);
    close.focus();
}

document.addEventListener("keydown", function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;

    if (e.key === "Escape") {
        closeShortcutSheet();
        if (isTyping(e.target)) e.target.blur();
        return;
    }
    if (isTyping(e.target)) return;

    if (e.key === "n" || e.key === "N") {
        var newLink = document.querySelector("[data-new-task]");
        if (newLink) {
            e.preventDefault();
            window.location.href = newLink.href;
        }
    } else if (e.key === "/") {
        var box = document.querySelector(".toolbar-search") || document.querySelector(".quick-add-input");
        if (box) {
            e.preventDefault();
            box.focus();
            if (box.select) box.select();
        }
    } else if (e.key === "?") {
        e.preventDefault();
        openShortcutSheet();
    }
});


/* ---------------------------------------------------------------
   Forms can only be sent once (no duplicate tasks from a double click)
   --------------------------------------------------------------- */

document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form || !form.method || form.method.toLowerCase() !== "post") return;

    var buttons = form.querySelectorAll('button[type="submit"], button:not([type])');
    // wait a tick: the browser has to read the form before we disable anything
    window.setTimeout(function () {
        buttons.forEach(function (b) {
            b.classList.add("is-busy");
            b.disabled = true;
        });
    }, 0);
});


/* ---------------------------------------------------------------
   Page changes: fade out before an internal link
   --------------------------------------------------------------- */

document.addEventListener("click", function (e) {
    var link = e.target.closest && e.target.closest("a[href]");
    if (!link) return;
    var href = link.getAttribute("href");
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    if (link.target === "_blank" || link.hasAttribute("download")) return;
    if (!href || href.charAt(0) === "#" || link.origin !== window.location.origin) return;
    if (REDUCED_MOTION) return;

    e.preventDefault();
    document.body.classList.add("is-leaving");
    window.setTimeout(function () { window.location.href = link.href; }, 170);

    // A link that turns out to be a file download never leaves this page.
    // If we're still here a moment later, bring the content back.
    window.setTimeout(function () { document.body.classList.remove("is-leaving"); }, 2500);
});

// back button restores the page in whatever state it was left in
window.addEventListener("pageshow", function () {
    document.body.classList.remove("is-leaving");
    document.querySelectorAll(".is-busy").forEach(function (b) {
        b.classList.remove("is-busy");
        b.disabled = false;
    });
});
