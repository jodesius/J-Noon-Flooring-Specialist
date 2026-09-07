/* Close the header dropdown on outside-click or Escape.
   The menu still opens/closes without JS (native <details>). */
(function () {
    "use strict";

    var menu = document.getElementById("main-menu");
    if (!menu) { return; }

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
})();