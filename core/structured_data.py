"""schema.org structured data for the page <head> - the semantic markup a
search engine actually parses, unlike the (now largely ignored) meta
keywords tag."""

import json

from django.urls import reverse

# Chelmsford town centre - matches the coverage-map's own centre point.
_GEO = {"latitude": 51.7356, "longitude": 0.4685}

# The small "JN" monogram - a clean square-ish mark, what schema.org's
# `logo` property expects (not the full service-list badge in the footer).
_LOGO_URL = (
    "https://res.cloudinary.com/ddmslr9na/image/upload/"
    "f_png,q_auto,w_512/v1788910923/jn-logo-initials_def2ao.webp"
)


def local_business_jsonld(request, contact):
    """A schema.org LocalBusiness block, as a pre-escaped JSON string ready
    to drop straight into a <script type="application/ld+json"> tag with
    the `safe` filter.

    No street address: this is a mobile fitting business working at the
    customer's home, not a shop, so `areaServed` + the coverage radius is
    what schema.org expects instead - Google's own guidance for
    service-area businesses with no public storefront.
    """
    data = {
        "@context": "https://schema.org",
        "@type": "HomeAndConstructionBusiness",
        "name": "J-Noon Flooring Specialist",
        "image": _LOGO_URL,
        "logo": _LOGO_URL,
        "url": request.build_absolute_uri(reverse("core:home")),
        "description": (
            "Flooring specialist covering Chelmsford and a 25-mile radius "
            "of Essex - LVT, carpet, laminate, Amtico, vinyl, screeding "
            "and floor prep."
        ),
        "address": {
            "@type": "PostalAddress",
            "addressLocality": "Chelmsford",
            "addressRegion": "Essex",
            "addressCountry": "GB",
        },
        "geo": {"@type": "GeoCoordinates", **_GEO},
        "areaServed": contact.service_area or "Chelmsford, Essex",
        "priceRange": "££",
    }
    if contact.phone:
        data["telephone"] = contact.phone
    if contact.email:
        data["email"] = contact.email

    same_as = [url for url in (contact.facebook, contact.instagram) if url]
    if same_as:
        data["sameAs"] = same_as

    return _safe_json(data)


def faq_page_jsonld(items):
    """A schema.org FAQPage block for the FAQ page - built from the same
    `FAQItem` queryset the page renders, so it can never drift out of sync
    with what's actually on the page. Google can show these as rich
    results directly in search."""
    data = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item.question,
                "acceptedAnswer": {"@type": "Answer", "text": item.answer},
            }
            for item in items
        ],
    }
    return _safe_json(data)


def _safe_json(data):
    # Escape the same way Django's json_script filter does, so a stray
    # "</script>" inside any admin-edited text field can never break out
    # of the tag.
    return (
        json.dumps(data)
        .replace("<", "\\u003C")
        .replace(">", "\\u003E")
        .replace("&", "\\u0026")
    )
