// Counts each stat card up from 0 to its real value once, on page load.
// Everything else on the page (nav, forms) works fine with JS off —
// this is just the one bit of polish on top.

document.addEventListener("DOMContentLoaded", function () {
    var prefersReducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
    ).matches;

    var numbers = document.querySelectorAll(".stat-number[data-count]");

    numbers.forEach(function (el) {
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

    // Close the mobile nav automatically after picking a link,
    // so it doesn't stay open when the next page loads.
    var navToggle = document.getElementById("nav-toggle");
    document.querySelectorAll(".sidebar a").forEach(function (link) {
        link.addEventListener("click", function () {
            if (navToggle) navToggle.checked = false;
        });
    });
});
