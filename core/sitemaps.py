from django.contrib.sitemaps import Sitemap
from django.urls import reverse

# The site's fixed public marketing pages. No per-object pages here - the
# gallery and reviews are each a single page (grid + lightbox / list), not
# one URL per photo or review, so there's nothing to list beyond this.
_PUBLIC_PAGES = [
    "core:home",
    "bookings:index",
    "gallery:index",
    "reviews:list",
    "contact:index",
]


class StaticViewSitemap(Sitemap):
    changefreq = "monthly"

    def items(self):
        return _PUBLIC_PAGES

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return 1.0 if item == "core:home" else 0.7
