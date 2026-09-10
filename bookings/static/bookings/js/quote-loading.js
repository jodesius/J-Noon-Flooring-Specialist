/* Show the "please wait" overlay when the quote form is submitted, and stop
 * the customer double-submitting while the AI works. Progressive enhancement
 * only - with no JS the form still posts normally. */
(function () {
    "use strict";

    var form = document.querySelector("form.bk-form");
    var overlay = document.getElementById("bk-loading");
    if (!form || !overlay) {
        return;
    }

    var submitted = false;

    function lock() {
        submitted = true;
        overlay.classList.add("is-active");
        document.body.style.overflow = "hidden";
        // Defer disabling so the button's value is still included in the POST.
        window.setTimeout(function () {
            var buttons = form.querySelectorAll(
                "button[type=submit], input[type=submit]"
            );
            Array.prototype.forEach.call(buttons, function (btn) {
                btn.disabled = true;
                btn.setAttribute("aria-disabled", "true");
            });
        }, 0);
    }

    function unlock() {
        submitted = false;
        overlay.classList.remove("is-active");
        document.body.style.overflow = "";
        var buttons = form.querySelectorAll(
            "button[type=submit], input[type=submit]"
        );
        Array.prototype.forEach.call(buttons, function (btn) {
            btn.disabled = false;
            btn.removeAttribute("aria-disabled");
        });
    }

    form.addEventListener("submit", function (event) {
        if (submitted) {
            event.preventDefault();
            return;
        }
        // If the browser can tell the form is incomplete, let it show its own
        // validation and don't cover the page - the server will answer fast.
        if (typeof form.checkValidity === "function" && !form.checkValidity()) {
            return;
        }
        lock();
    });

    // Coming back via the browser's Back button can restore the page from
    // cache with the overlay still showing - clear it.
    window.addEventListener("pageshow", function (event) {
        if (event.persisted && submitted) {
            unlock();
        }
    });
})();
