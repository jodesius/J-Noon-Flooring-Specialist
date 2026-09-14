/* Contact us - coverage map (Leaflet). Uses Geoapify tiles (commercial-use
 * free tier) when GEOAPIFY_API_KEY is set; falls back to OpenStreetMap's
 * own raw tile server otherwise - fine for occasional local dev, but not
 * meant for a live site's regular traffic (their usage policy blocks
 * anything that looks like automated/heavy use - see osm.wiki/Blocked). */
(function () {
    "use strict";

    var el = document.getElementById("coverage-map");
    if (!el || typeof L === "undefined") return;

    // Chelmsford town centre.
    var CENTRE = [51.7356, 0.4685];
    var miles = parseInt(el.getAttribute("data-radius"), 10) || 25;
    var radiusMetres = miles * 1609.34;
    var tileKey = el.getAttribute("data-tile-key");

    // An initial view must be set before layers can be projected.
    var map = L.map(el, { scrollWheelZoom: false }).setView(CENTRE, 9);

    var tileUrl, tileOptions;
    if (tileKey) {
        tileUrl = "https://maps.geoapify.com/v1/tile/osm-bright/{z}/{x}/{y}.png?apiKey=" + tileKey;
        tileOptions = {
            maxZoom: 20,
            attribution:
                'Powered by <a href="https://www.geoapify.com/" target="_blank">Geoapify</a> | ' +
                '<a href="https://openmaptiles.org/" target="_blank">&copy; OpenMapTiles</a> ' +
                '<a href="https://www.openstreetmap.org/copyright" target="_blank">&copy; OpenStreetMap</a> contributors',
        };
    } else {
        tileUrl = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
        tileOptions = {
            maxZoom: 18,
            attribution:
                '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        };
    }
    L.tileLayer(tileUrl, tileOptions).addTo(map);

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
