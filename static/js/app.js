// Hangarin front-end extras.
// Everything here is a bonus: every page still works with JavaScript off.

var REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

document.addEventListener("DOMContentLoaded", function () {
    initStatCounters();
    initMobileNavClose();
    initToasts();
    initStatusToggles();
    initSearchAutoSubmit();
    initAutoSubmitSelects();
    initThemeToggle();
    initAvatarPreview();
    initBackButtons();
    initPasswordToggles();
    initAuthForms();
    initMenuKeys();
    initFormDrafts();
    initEmojiField();
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


function svgIcon(name) {
    var ns = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(ns, "svg");
    svg.setAttribute("class", "i");
    svg.setAttribute("aria-hidden", "true");
    var use = document.createElementNS(ns, "use");
    use.setAttribute("href", "#i-" + name);
    svg.appendChild(use);
    return svg;
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
            var label = btn.getAttribute("data-label") || "";
            btn.disabled = true;
            btn.classList.add("is-updating");

            fetch(url, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": csrfToken(),
                    // what the "waiting to sync" list calls this if it has to be saved
                    "X-Hangarin-Label": encodeURIComponent(label ? "Change status of: " + label : ""),
                },
            })
                .then(function (res) {
                    if (!res.ok && res.status !== 202) throw new Error("toggle failed");
                    return res.json();
                })
                .then(function (data) {
                    if (data.queued) {
                        // no connection: the service worker kept it. Show the
                        // new status now, it is sent when we're back online.
                        localCycle(btn);
                        btn.classList.add("is-queued");
                        showToast("Saved on this device. It will sync when you're back online.", "success");
                        return;
                    }
                    applyStatus(btn, data);
                    celebrate(btn, data);
                })
                .catch(function () {
                    if (!navigator.onLine) {
                        showToast("You're offline and this page can't save changes yet.", "error");
                    } else {
                        // something went wrong (logged out...), so show the real state
                        window.location.reload();
                    }
                })
                .finally(function () {
                    btn.disabled = false;
                    btn.classList.remove("is-updating");
                });
        });
    });
}

var STATUS_ORDER = [
    { slug: "pending", label: "Pending" },
    { slug: "in-progress", label: "In Progress" },
    { slug: "completed", label: "Completed" },
];

function slugOf(el) {
    var found = null;
    Array.from(el.classList).forEach(function (cls) {
        var m = cls.match(/^(?:status|badge)-(pending|in-progress|completed)$/);
        if (m) found = m[1];
    });
    return found || "pending";
}

// Move a status button to the next status without asking the server (used
// offline). Mirrors _next_status() in views.py.
function localCycle(btn) {
    var at = STATUS_ORDER.findIndex(function (o) { return o.slug === slugOf(btn); });
    var next = STATUS_ORDER[(at + 1) % STATUS_ORDER.length];
    var data = { slug: next.slug, label: next.label };

    var parent = btn.getAttribute("data-parent");
    if (parent) {
        var box = document.querySelector('[data-progress-for="' + parent + '"]');
        var doneEl = box && box.querySelector("[data-done]");
        var totalEl = box && box.querySelector("[data-total]");
        if (doneEl && totalEl) {
            var done = parseInt(doneEl.textContent, 10) || 0;
            var total = parseInt(totalEl.textContent, 10) || 0;
            if (next.slug === "completed") done += 1;
            if (STATUS_ORDER[at].slug === "completed") done -= 1;
            done = Math.max(0, Math.min(total, done));
            data.parent = parent;
            data.progress = { done: done, total: total, pct: total ? Math.round(done * 100 / total) : 0 };
        }
    }
    applyStatus(btn, data);
    return data;
}

function applyStatus(el, data) {
    if (el.classList.contains("badge")) {
        swapPrefixedClass(el, "badge-", data.slug);
        el.textContent = data.label;
    } else {
        swapPrefixedClass(el, "status-", data.slug);
    }

    if (el.classList.contains("subtask-check")) {
        el.textContent = "";
        if (data.slug === "completed") el.appendChild(svgIcon("check"));
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
            "You reached level " + data.level_up.level + ": " + data.level_up.title + ".",
            "level"
        );
    } else if (data.goal_hit) {
        showToast("Daily goal reached (" + data.goal + ").", "level");
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
                // no connection: filter what's already on the page instead
                if (!navigator.onLine && window.hgOfflineFilter) {
                    window.hgOfflineFilter(input);
                    return;
                }
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
   Emoji in the background shy away from the pointer
   (they keep wiggling on their own either way)
   --------------------------------------------------------------- */

function initEmojiField() {
    var field = document.querySelector(".emoji-field");
    if (!field || REDUCED_MOTION) return;
    // phones have no hovering pointer, the wiggle alone is plenty there
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;

    var items = Array.prototype.slice.call(field.querySelectorAll(".emo"));
    var RADIUS = 190;      // how close the pointer has to get
    var PUSH = 70;         // the furthest an emoji gets nudged, in px
    var pointer = null;
    var queued = false;

    function paint() {
        queued = false;
        items.forEach(function (item) {
            if (!pointer) {
                item.style.setProperty("--px", "0px");
                item.style.setProperty("--py", "0px");
                return;
            }
            // offsetLeft/Top ignore transforms, so the nudge can't feed back into itself
            var cx = item.offsetLeft + item.offsetWidth / 2;
            var cy = item.offsetTop + item.offsetHeight / 2;
            var dx = cx - pointer.x;
            var dy = cy - pointer.y;
            var dist = Math.sqrt(dx * dx + dy * dy) || 1;
            if (dist > RADIUS) {
                item.style.setProperty("--px", "0px");
                item.style.setProperty("--py", "0px");
                return;
            }
            var force = (1 - dist / RADIUS) * PUSH;
            item.style.setProperty("--px", ((dx / dist) * force).toFixed(1) + "px");
            item.style.setProperty("--py", ((dy / dist) * force).toFixed(1) + "px");
        });
    }

    function queue() {
        if (!queued) {
            queued = true;
            window.requestAnimationFrame(paint);
        }
    }

    document.addEventListener("pointermove", function (e) {
        pointer = { x: e.clientX, y: e.clientY };
        queue();
    }, { passive: true });
    document.addEventListener("pointerleave", function () {
        pointer = null;
        queue();
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
    if (e.defaultPrevented) return;   // something else stopped it (offline guard, logout confirm)
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
    if (link.target === "_blank" || link.hasAttribute("download") || link.hasAttribute("data-back")) return;
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


/* ---------------------------------------------------------------
   Sort and filter dropdowns send the form as soon as you pick
   --------------------------------------------------------------- */

function initAutoSubmitSelects() {
    document.querySelectorAll("select[data-autosubmit]").forEach(function (select) {
        select.addEventListener("change", function () {
            if (!navigator.onLine) {
                showToast("Sorting and filtering need a connection.", "error");
                return;
            }
            if (select.form) select.form.submit();
        });
    });
}


/* ---------------------------------------------------------------
   Back button: really goes back to the page you came from. Without
   history (a bookmark, the installed app) the link's own address is used.
   --------------------------------------------------------------- */

function initBackButtons() {
    var cameFromHere = false;
    var cameFromAForm = false;
    try {
        if (document.referrer) {
            var ref = new URL(document.referrer);
            cameFromHere = ref.origin === window.location.origin && document.referrer !== window.location.href;
            // after saving a form you land on the next page; going "back" to
            // the finished form isn't what anyone wants
            cameFromAForm = /\/(new|edit|delete)\/$/.test(ref.pathname);
        }
    } catch (err) { /* no usable referrer */ }

    var canGoBack = window.history.length > 1 && cameFromHere && !cameFromAForm;

    document.querySelectorAll("[data-back]").forEach(function (link) {
        if (link.hasAttribute("data-back-optional") && canGoBack) link.hidden = false;
        link.addEventListener("click", function (e) {
            if (!canGoBack) return;
            e.preventDefault();
            window.history.back();
        });
    });
}


/* ---------------------------------------------------------------
   Show / hide password
   --------------------------------------------------------------- */

function initPasswordToggles() {
    document.querySelectorAll("[data-pw-toggle]").forEach(function (btn) {
        var input = btn.parentElement.querySelector("input");
        if (!input) return;
        btn.hidden = false;   // hidden until now so it never shows without JavaScript
        btn.addEventListener("click", function () {
            var show = input.type === "password";
            input.type = show ? "text" : "password";
            btn.setAttribute("aria-pressed", String(show));
            btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
        });
    });
}


/* ---------------------------------------------------------------
   Log in / sign up pages
   --------------------------------------------------------------- */

function initAuthForms() {
    // Focus the first field on computers. Not on phones, where it would pop
    // the keyboard up over the page before it has been read.
    var form = document.querySelector(".auth-form");
    if (form && window.matchMedia("(pointer: fine)").matches) {
        var target = form.querySelector('[aria-invalid="true"]') ||
                     form.querySelector('input:not([type="hidden"]):not([type="checkbox"])');
        if (target) target.focus();
    }

    // These forms need the server. Say so instead of failing with a browser error.
    document.addEventListener("submit", function (e) {
        var f = e.target;
        if (!f.hasAttribute || !f.hasAttribute("data-needs-online") || navigator.onLine) return;
        e.preventDefault();
        var notice = f.querySelector(".form-offline-note") ||
                     (f.closest(".auth-card") && f.closest(".auth-card").querySelector(".form-offline-note"));
        if (notice) notice.hidden = false;
        else showToast("You're offline. This needs a connection.", "error");
    }, true);

    window.addEventListener("online", function () {
        document.querySelectorAll(".form-offline-note").forEach(function (n) { n.hidden = true; });
    });

    // Passwords on the sign-up form: say right away if the two don't match
    var p1 = document.getElementById("id_password1");
    var p2 = document.getElementById("id_password2");
    if (p1 && p2) {
        var hint = document.createElement("p");
        hint.className = "field-error";
        hint.hidden = true;
        hint.textContent = "The passwords don't match yet.";
        p2.closest(".auth-field").appendChild(hint);
        var check = function () { hint.hidden = !p2.value || p1.value === p2.value; };
        p1.addEventListener("input", check);
        p2.addEventListener("input", check);
    }
}


/* ---------------------------------------------------------------
   Mobile menu: Escape closes it
   --------------------------------------------------------------- */

function initMenuKeys() {
    var navToggle = document.getElementById("nav-toggle");
    if (!navToggle) return;
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && navToggle.checked) {
            navToggle.checked = false;
            var burger = document.querySelector(".hamburger");
            if (burger) burger.focus();
        }
    });
}


/* ---------------------------------------------------------------
   Drafts: what you typed into a form is kept on this device until you
   save it, so a dropped connection or an accidental tab close doesn't
   lose it. Cleared on save, and on logout (see offline.js) so nothing
   is left behind on a shared computer.
   --------------------------------------------------------------- */

var DRAFT_PREFIX = "hangarin-draft-";

function clearDrafts() {
    try {
        Object.keys(window.localStorage).forEach(function (key) {
            if (key.indexOf(DRAFT_PREFIX) === 0) window.localStorage.removeItem(key);
        });
    } catch (err) { /* storage blocked */ }
}

function initFormDrafts() {
    document.querySelectorAll("form[data-draft-key]").forEach(function (form) {
        var key = form.getAttribute("data-draft-key");
        if (!key) return;

        // a form the server sent back with errors already holds what the
        // person typed; a draft would only get in the way
        var hasErrors = !!form.querySelector(".has-error");

        if (!hasErrors) {
            try {
                var saved = window.localStorage.getItem(key);
                if (saved) {
                    var data = JSON.parse(saved);
                    var restored = false;
                    Object.keys(data).forEach(function (name) {
                        var field = form.elements.namedItem(name);
                        if (field && field.value !== undefined && field.value !== data[name]) {
                            field.value = data[name];
                            restored = true;
                        }
                    });
                    if (restored) showToast("Restored what you were typing.", "success");
                }
            } catch (err) { /* storage blocked or bad data */ }
        }

        form.addEventListener("input", function () {
            try {
                var draft = {};
                Array.from(form.elements).forEach(function (field) {
                    var skip = ["hidden", "submit", "button", "file", "password"];
                    if (!field.name || skip.indexOf(field.type) !== -1) return;
                    draft[field.name] = field.value;
                });
                window.localStorage.setItem(key, JSON.stringify(draft));
            } catch (err) { /* ignore */ }
        });
        form.addEventListener("submit", function () {
            try { window.localStorage.removeItem(key); } catch (err) { /* ignore */ }
        });
    });
}

// any logout form: drop saved drafts (unless a confirm in offline.js cancelled it)
document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!e.defaultPrevented && form.hasAttribute && form.hasAttribute("data-logout")) clearDrafts();
});
