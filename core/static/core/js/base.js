(function () {
    "use strict";

    /* --- Main dropdown menu (top-left <details>) --- */
    var menu = document.getElementById("main-menu");
    if (menu) {
        document.addEventListener("click", function (event) {
            if (menu.open && !menu.contains(event.target)) {
                menu.open = false;
            }
        });
        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && menu.open) {
                menu.open = false;
                var summary = menu.querySelector("summary");
                if (summary) { summary.focus(); }
            }
        });
    }

    /* --- User menu (top-right). Opens on hover/focus via CSS; this adds
           click/tap support and keeps aria-expanded in sync. --- */
    var userBtn = document.querySelector(".user-badge--button");
    if (userBtn) {
        var wrap = userBtn.closest(".user-menu");

        userBtn.addEventListener("click", function () {
            var open = wrap.classList.toggle("is-open");
            userBtn.setAttribute("aria-expanded", String(open));
        });

        document.addEventListener("click", function (event) {
            if (wrap.classList.contains("is-open") && !wrap.contains(event.target)) {
                wrap.classList.remove("is-open");
                userBtn.setAttribute("aria-expanded", "false");
            }
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && wrap.classList.contains("is-open")) {
                wrap.classList.remove("is-open");
                userBtn.setAttribute("aria-expanded", "false");
                userBtn.focus();
            }
        });
    }
})();
