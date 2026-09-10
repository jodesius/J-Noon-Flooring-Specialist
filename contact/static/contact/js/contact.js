/* Contact us - coverage map (Leaflet + OpenStreetMap, no API key). */
(function () {
    "use strict";

    var el = document.getElementById("coverage-map");
    if (!el || typeof L === "undefined") return;

    // Chelmsford town centre.
    var CENTRE = [51.7356, 0.4685];
    var miles = parseInt(el.getAttribute("data-radius"), 10) || 25;
    var radiusMetres = miles * 1609.34;

    // An initial view must be set before layers can be projected.
    var map = L.map(el, { scrollWheelZoom: false }).setView(CENTRE, 9);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var circle = L.circle(CENTRE, {
        radius: radiusMetres,
        color: "#8b4b07",
        weight: 2,
        fillColor: "#8b4b07",
        fillOpacity: 0.1,
    }).addTo(map);

    L.marker(CENTRE)
        .addTo(map)
        .bindPopup("J-Noon Flooring Specialist &mdash; Chelmsford");

    map.fitBounds(circle.getBounds(), { padding: [15, 15] });

    // Re-measure once the container has settled at its final size.
    setTimeout(function () {
        map.invalidateSize();
        map.fitBounds(circle.getBounds(), { padding: [15, 15] });
    }, 250);
})();
