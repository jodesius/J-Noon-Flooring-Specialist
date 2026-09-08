(function () {
    "use strict";

    /* Main dropdown menu (top-left <details>): close on outside-click / Escape.
       It still opens and closes without JS. */
    var menu = document.getElementById("main-menu");
    if (!menu) {
        return;
    }

    document.addEventListener("click", function (event) {
        if (menu.open && !menu.contains(event.target)) {
            menu.open = false;
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && menu.open) {
            menu.open = false;
            var summary = menu.querySelector("summary");
            if (summary) {
                summary.focus();
            }
        }
    });
})();
