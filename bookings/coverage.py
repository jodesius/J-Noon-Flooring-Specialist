"""Is a customer's postcode inside J-Noon's operating area?

Geocodes UK postcodes with the free, key-less postcodes.io API and measures
the straight-line distance from Chelmsford town centre against the coverage
radius (`SiteContact.radius_miles` - the same figure the coverage map uses).
Any failure (bad postcode, API down, timeout) returns "unknown" and the
quote just carries on as before; the fitter still sees every request.
"""

import json
import logging
import math
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

# Chelmsford town centre - matches contact/static/contact/js/contact.js.
DEFAULT_CENTRE = (51.7356, 0.4685)
DEFAULT_RADIUS_MILES = 25
# Slack for postcode-centroid imprecision (a postcode's point can sit a few
# hundred metres from any given address on it).
GRACE_MILES = 2

_API = "https://api.postcodes.io/postcodes/{}"


def coverage_radius():
    try:
        from contact.models import SiteContact

        return SiteContact.load().radius_miles or DEFAULT_RADIUS_MILES
    except Exception:
        return DEFAULT_RADIUS_MILES


def postcode_point(postcode):
    """(latitude, longitude) for a UK postcode, or None if it can't be found."""
    pc = (postcode or "").strip()
    if not pc:
        return None
    url = _API.format(urllib.parse.quote(pc, safe=""))
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "jnoon-flooring"})
        with urllib.request.urlopen(request, timeout=6) as resp:
            data = json.load(resp)
    except Exception as exc:
        logger.info("postcodes.io lookup failed for %r: %s", pc, exc)
        return None
    result = (data or {}).get("result") or {}
    lat, lng = result.get("latitude"), result.get("longitude")
    if lat is None or lng is None:
        return None
    return float(lat), float(lng)


def _haversine_miles(a, b):
    """Straight-line ("as the crow flies") distance between two lat/lng
    points, in miles."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def coverage_status(postcode):
    """Returns ("in" | "out" | "unknown", distance_in_miles_or_None)."""
    point = postcode_point(postcode)
    if point is None:
        return "unknown", None
    centre = getattr(settings, "BOOKINGS_COVERAGE_CENTRE", DEFAULT_CENTRE)
    distance = _haversine_miles(centre, point)
    within = distance <= coverage_radius() + GRACE_MILES
    return ("in" if within else "out"), round(distance, 1)
