/* Show / hide password toggle.

   Works on any `.pw-toggle` button that sits next to an <input> inside a
   `.pw-field` wrapper (see accounts/templates/accounts/_password_input.html).
   Used on the register, login and set-new-password forms.

   Click once -> the input shows plain text; click again -> back to dots. */
(function () {
    "use strict";

    document.querySelectorAll(".pw-toggle").forEach(function (btn) {
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
