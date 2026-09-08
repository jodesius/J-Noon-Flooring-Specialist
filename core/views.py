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
