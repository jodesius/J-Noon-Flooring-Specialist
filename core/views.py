from django.shortcuts import render

from reviews.models import Review

# Latest approved reviews shown in the home page "Reviews" section.
HOME_REVIEW_COUNT = 6


def home(request):
    reviews = (
        Review.objects.filter(is_approved=True)
        .select_related("author")[:HOME_REVIEW_COUNT]
    )
    return render(request, "core/home.html", {"reviews": reviews})


def robots_txt(request):
    """Tells crawlers which parts of the site are worth indexing - the
    marketing pages, not the customer portal, checkout or admin. The
    per-page `noindex` meta tags are the real enforcement (a crawler that
    ignores robots.txt still won't index a noindex page); this just saves
    well-behaved ones the trip."""
    return render(
        request,
        "robots.txt",
        {"sitemap_url": request.build_absolute_uri("/sitemap.xml")},
        content_type="text/plain",
    )
