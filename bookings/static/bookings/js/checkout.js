/* Branded Stripe checkout. Card data goes browser -> Stripe only; our server
 * sees the PaymentIntent id and status, never a card number. */
(function () {
    "use strict";

    var dataEl = document.getElementById("checkout-data");
    var form = document.getElementById("checkout-form");
    if (!dataEl || !form || typeof Stripe === "undefined") {
        return;
    }
    var cfg = JSON.parse(dataEl.textContent);

    var stripe = Stripe(cfg.publishableKey);
    var appearance = {
        theme: "stripe",
        variables: {
            colorPrimary: "#8b4b07",
            colorText: "#3f3a35",
            colorDanger: "#a4291f",
            fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
            borderRadius: "6px",
            spacingUnit: "3px",
        },
    };
    var elements = stripe.elements({ clientSecret: cfg.clientSecret, appearance: appearance });

    var paymentElement = elements.create("payment", {
        fields: { billingDetails: { name: "never", email: "never", address: "never" } },
    });
    paymentElement.mount("#payment-element");

    var addressElement = elements.create("address", { mode: "billing" });
    addressElement.mount("#address-element");

    var button = document.getElementById("pay-button");
    var buttonText = document.getElementById("pay-button-text");
    var spinner = document.getElementById("pay-button-spinner");
    var errorBox = document.getElementById("pay-errors");
    var overlay = document.getElementById("bk-loading");
    var submitting = false;

    function showError(msg) {
        errorBox.textContent = msg;
        errorBox.hidden = false;
        errorBox.scrollIntoView({ block: "center", behavior: "smooth" });
    }

    // Warn on an accidental refresh/close while the payment is in flight -
    // closing now would leave it stuck "processing" with no record client-side
    // (the webhook / return page still catch it, but better to avoid it).
    function warnBeforeUnload(event) {
        event.preventDefault();
        event.returnValue = "";
    }

    // One switch for every "payment in progress" affordance: the full-screen
    // overlay (same one the quote page uses), the button's own spinner, and
    // the browser's "are you sure you want to leave" prompt.
    function setBusy(busy) {
        submitting = busy;
        button.disabled = busy;
        buttonText.hidden = busy;
        spinner.hidden = !busy;
        if (overlay) {
            overlay.classList.toggle("is-active", busy);
            document.body.style.overflow = busy ? "hidden" : "";
        }
        if (busy) {
            window.addEventListener("beforeunload", warnBeforeUnload);
        } else {
            window.removeEventListener("beforeunload", warnBeforeUnload);
        }
    }

    function csrfToken() {
        var el = form.querySelector("[name=csrfmiddlewaretoken]");
        return el ? el.value : "";
    }

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        if (submitting) {
            return;
        }
        errorBox.hidden = true;

        var firstName = document.getElementById("first-name").value.trim();
        var lastName = document.getElementById("last-name").value.trim();
        var email = document.getElementById("email").value.trim();
        var authorised = document.getElementById("authorise").checked;

        if (!firstName || !lastName) {
            showError("Please enter your first name and surname.");
            return;
        }
        if (!email) {
            showError("Please enter your email address.");
            return;
        }
        if (!authorised) {
            showError("Please tick the box to authorise the payment.");
            return;
        }

        setBusy(true);

        var fullName = firstName + " " + lastName;
        var billing = { name: fullName, email: email };

        var addr = await addressElement.getValue();
        if (addr.complete && addr.value && addr.value.address) {
            billing.address = addr.value.address;
        }

        // Record the authorisation + payer details on our server first.
        try {
            var body = new URLSearchParams();
            body.set("csrfmiddlewaretoken", csrfToken());
            body.set("name", fullName);
            body.set("email", email);
            body.set("billing", addr.value ? JSON.stringify(addr.value.address || {}) : "");
            var resp = await fetch(cfg.authoriseUrl, {
                method: "POST",
                headers: { "X-Requested-With": "XMLHttpRequest" },
                body: body,
            });
            if (!resp.ok) {
                var j = await resp.json().catch(function () { return {}; });
                showError(j.error || "Something went wrong - please try again.");
                setBusy(false);
                return;
            }
        } catch (e) {
            showError("Network problem - please check your connection and try again.");
            setBusy(false);
            return;
        }

        var result = await stripe.confirmPayment({
            elements: elements,
            confirmParams: {
                return_url: cfg.returnUrl,
                receipt_email: email,
                payment_method_data: { billing_details: billing },
            },
        });

        // Only reached if confirmPayment failed immediately (otherwise the
        // browser is redirected to return_url).
        if (result.error) {
            showError(result.error.message || "Your payment could not be completed.");
            setBusy(false);
        }
    });

    // Coming back via the browser's Back button can restore this page from
    // cache with the overlay still showing and the button still locked - the
    // payment attempt is over one way or another by then, so clear it.
    window.addEventListener("pageshow", function (event) {
        if (event.persisted && submitting) {
            setBusy(false);
        }
    });
})();
