/* Pay-a-part-of-the-balance form: the amount box only appears once "Pay
 * part of it" is actually selected, so there's no way to type an amount and
 * have it silently ignored because "full balance" was still the one ticked. */
(function () {
    "use strict";

    var radios = document.querySelectorAll('input[name="choice"]');
    var partRadio = document.querySelector('input[name="choice"][value="part"]');
    var amountWrap = document.getElementById("pay-choose-amount");
    var amountInput = document.getElementById("pay-choose-amount-input");
    if (!radios.length || !partRadio || !amountWrap) {
        return;
    }

    function sync() {
        var partChosen = partRadio.checked;
        amountWrap.hidden = !partChosen;
        if (partChosen) {
            amountInput.focus();
        }
    }

    radios.forEach(function (radio) {
        radio.addEventListener("change", sync);
    });
    sync();
})();
