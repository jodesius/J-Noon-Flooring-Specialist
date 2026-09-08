/* Work Gallery - category filtering + lightbox.
   No dependencies. Progressive: with JS off, every photo shows and each
   card is still a link-free button (clicking just does nothing). */
(function () {
    "use strict";

    var grid = document.getElementById("gallery-grid");
    if (!grid) return;

    var items = Array.prototype.slice.call(
        grid.querySelectorAll(".gallery-grid__item")
    );
    var filterButtons = Array.prototype.slice.call(
        document.querySelectorAll(".gallery__filter")
    );
    var noResults = document.querySelector(".gallery__noresults");

    /* ---------- Filtering ---------- */
    var currentFilter = "all";

    function applyFilter(filter) {
        currentFilter = filter;
        var shown = 0;

        items.forEach(function (item) {
            var match =
                filter === "all" ||
                item.getAttribute("data-category") === filter;
            item.hidden = !match;
            if (match) shown++;
        });

        filterButtons.forEach(function (btn) {
            var active = btn.getAttribute("data-filter") === filter;
            btn.classList.toggle("is-active", active);
            btn.setAttribute("aria-pressed", active ? "true" : "false");
        });

        if (noResults) noResults.hidden = shown !== 0;
    }

    filterButtons.forEach(function (btn) {
        btn.addEventListener("click", function () {
            applyFilter(btn.getAttribute("data-filter"));
        });
    });

    /* ---------- Lightbox ---------- */
    var lightbox = document.getElementById("lightbox");
    var lbImg = document.getElementById("lightbox-img");
    var lbCaption = document.getElementById("lightbox-caption");
    var lbClose = lightbox
        ? lightbox.querySelector("[data-lb-close]")
        : null;
    var lbPrev = lightbox ? lightbox.querySelector("[data-lb-prev]") : null;
    var lbNext = lightbox ? lightbox.querySelector("[data-lb-next]") : null;

    var visibleCards = [];
    var activeIndex = -1;
    var lastFocused = null;

    function refreshVisibleCards() {
        visibleCards = items
            .filter(function (item) {
                return !item.hidden;
            })
            .map(function (item) {
                return item.querySelector(".gallery-card");
            });
    }

    function showAt(index) {
        if (!visibleCards.length) return;
        activeIndex = (index + visibleCards.length) % visibleCards.length;
        var card = visibleCards[activeIndex];
        lbImg.src = card.getAttribute("data-full");
        lbImg.alt = card.querySelector("img").alt;
        lbCaption.textContent = card.getAttribute("data-title") || "";
    }

    function openLightbox(card) {
        if (!lightbox) return;
        refreshVisibleCards();
        var index = visibleCards.indexOf(card);
        if (index === -1) return;
        lastFocused = document.activeElement;
        lightbox.hidden = false;
        document.body.style.overflow = "hidden";
        showAt(index);
        if (lbClose) lbClose.focus();
        document.addEventListener("keydown", onKeydown);
    }

    function closeLightbox() {
        lightbox.hidden = true;
        document.body.style.overflow = "";
        lbImg.src = "";
        document.removeEventListener("keydown", onKeydown);
        if (lastFocused && typeof lastFocused.focus === "function") {
            lastFocused.focus();
        }
    }

    function onKeydown(e) {
        if (e.key === "Escape") closeLightbox();
        else if (e.key === "ArrowLeft") showAt(activeIndex - 1);
        else if (e.key === "ArrowRight") showAt(activeIndex + 1);
    }

    grid.addEventListener("click", function (e) {
        var card = e.target.closest(".gallery-card");
        if (card) openLightbox(card);
    });

    if (lbClose) lbClose.addEventListener("click", closeLightbox);
    if (lbPrev)
        lbPrev.addEventListener("click", function () {
            showAt(activeIndex - 1);
        });
    if (lbNext)
        lbNext.addEventListener("click", function () {
            showAt(activeIndex + 1);
        });
    if (lightbox)
        lightbox.addEventListener("click", function (e) {
            if (e.target === lightbox || e.target === lbImg.parentNode) {
                closeLightbox();
            }
        });
})();
