/* "Book a job" - live address suggestions on the site_address field, via
 * Geoapify's autocomplete API (same key already used for the contact page's
 * coverage map). Purely a UX aid - the address the customer ends up
 * submitting is still validated server-side (a real, resolvable postcode is
 * required), so this working or not doesn't change what's actually allowed
 * through. Any fetch failure just leaves the field as a plain text input.
 */
(function () {
    var input = document.getElementById("id_site_address");
    if (!input) return;

    var apiKey = input.dataset.geoapifyKey;
    if (!apiKey) return;

    var box = document.createElement("div");
    box.className = "address-suggest";
    box.hidden = true;
    input.insertAdjacentElement("afterend", box);
    input.parentElement.style.position = "relative";

    var debounceTimer = null;
    var activeIndex = -1;
    var items = [];

    function hide() {
        box.hidden = true;
        box.innerHTML = "";
        items = [];
        activeIndex = -1;
    }

    function choose(item) {
        input.value = item.formatted;
        hide();
    }

    function render(results) {
        box.innerHTML = "";
        items = results;
        activeIndex = -1;
        if (!results.length) {
            hide();
            return;
        }
        results.forEach(function (item, index) {
            var row = document.createElement("button");
            row.type = "button";
            row.className = "address-suggest__item";
            row.textContent = item.formatted;
            row.addEventListener("mousedown", function (e) {
                e.preventDefault();  // fires before the input's blur
                choose(item);
            });
            row.addEventListener("mouseenter", function () {
                setActive(index);
            });
            box.appendChild(row);
        });
        box.hidden = false;
    }

    function setActive(index) {
        var rows = box.querySelectorAll(".address-suggest__item");
        rows.forEach(function (row) { row.classList.remove("is-active"); });
        if (index >= 0 && index < rows.length) {
            rows[index].classList.add("is-active");
            activeIndex = index;
        }
    }

    function search(text) {
        var url = "https://api.geoapify.com/v1/geocode/autocomplete"
            + "?text=" + encodeURIComponent(text)
            + "&filter=countrycode:gb&format=json&limit=5&apiKey=" + apiKey;
        fetch(url)
            .then(function (resp) { return resp.ok ? resp.json() : null; })
            .then(function (data) {
                if (data && Array.isArray(data.results)) render(data.results);
            })
            .catch(function () { /* silent - manual typing still works */ });
    }

    input.addEventListener("input", function () {
        var text = input.value.trim();
        clearTimeout(debounceTimer);
        if (text.length < 3) {
            hide();
            return;
        }
        debounceTimer = setTimeout(function () { search(text); }, 300);
    });

    input.addEventListener("keydown", function (e) {
        if (box.hidden) return;
        if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive(Math.min(activeIndex + 1, items.length - 1));
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive(Math.max(activeIndex - 1, 0));
        } else if (e.key === "Enter") {
            if (activeIndex >= 0) {
                e.preventDefault();
                choose(items[activeIndex]);
            }
        } else if (e.key === "Escape") {
            hide();
        }
    });

    document.addEventListener("click", function (e) {
        if (e.target !== input && !box.contains(e.target)) hide();
    });
})();
