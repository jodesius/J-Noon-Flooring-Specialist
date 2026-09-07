/* Register page: show/hide password toggles. */
(function () {
    "use strict";

    var toggles = document.querySelectorAll(".pw-toggle");

    toggles.forEach(function (btn) {
        btn.addEventListener("click", function () {
            var input = btn.parentElement.querySelector("input");
            if (!input) {
                return;
            }

            var reveal = input.type === "password";
            input.type = reveal ? "text" : "password";

            btn.classList.toggle("is-on", reveal);
            btn.setAttribute("aria-pressed", String(reveal));
            btn.setAttribute("aria-label", reveal ? "Hide password" : "Show password");
        });
    });
})();
