/* Show the "please wait" overlay when a specific form is submitted, and
 * stop it being double/triple-submitted while the request is in flight -
 * same idea as quote-loading.js, but for a page that can have more than
 * one form on it. The overlay's own data-form-id attribute says which
 * form to lock; falls back to the first form.bk-form if it isn't set.
 * Progressive enhancement only - with no JS the form still posts normally.
 */
(function () {
    "use strict";

    var overlay = document.getElementById("bk-loading");
    if (!overlay) {
        return;
    }
    var formId = overlay.dataset.formId;
    var form = formId
        ? document.getElementById(formId)
        : document.querySelector("form.bk-form");
    if (!form) {
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
        if (typeof form.checkValidity === "function" && !form.checkValidity()) {
            return;
        }
        lock();
    });

    window.addEventListener("pageshow", function (event) {
        if (event.persisted && submitted) {
            unlock();
        }
    });
})();
