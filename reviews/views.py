from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import ReviewForm
from .models import Review

# How many approved postcards the home page shows.
HOME_REVIEW_LIMIT = 6


def _approved_reviews():
    return Review.objects.filter(is_approved=True).select_related("author")


def _can_delete(user, review):
    """A review can be removed by its author, a Site Administrator, or the
    superuser.
    """
    return review.author_id == user.id or user.is_site_admin


def review_list(request):
    """Public page: every approved review postcard."""
    return render(
        request,
        "reviews/review_list.html",
        {"reviews": _approved_reviews()},
    )


@login_required
def review_create(request):
    if request.method == "POST":
        form = ReviewForm(request.POST, request.FILES)
        if form.is_valid():
            review = form.save(commit=False)
            review.author = request.user
            review.is_approved = False
            review.save()
            messages.success(
                request,
                "Thanks! Your review has been submitted and will appear once "
                "it has been approved.",
            )
            return redirect("reviews:list")
    else:
        form = ReviewForm()

    return render(
        request,
        "reviews/review_form.html",
        {"form": form, "is_edit": False},
    )


@login_required
def review_update(request, slug):
    # Only the author may edit; look-up is by UUID slug, never a numeric id.
    review = get_object_or_404(Review, slug=slug, author=request.user)

    if request.method == "POST":
        form = ReviewForm(request.POST, request.FILES, instance=review)
        if form.is_valid():
            review = form.save(commit=False)
            # An edited review goes back into the moderation queue.
            review.is_approved = False
            review.save()
            messages.success(
                request,
                "Your review has been updated and will reappear once it has "
                "been approved again.",
            )
            return redirect("reviews:list")
    else:
        form = ReviewForm(instance=review)

    return render(
        request,
        "reviews/review_form.html",
        {"form": form, "is_edit": True, "review": review},
    )


@login_required
@require_http_methods(["GET", "POST"])
def review_delete(request, slug):
    review = get_object_or_404(Review, slug=slug)

    if not _can_delete(request.user, review):
        messages.error(request, "You cannot delete that review.")
        return redirect("reviews:list")

    if request.method == "POST":
        review.delete()
        messages.success(request, "The review has been deleted.")
        return redirect("reviews:list")

    return render(
        request,
        "reviews/review_confirm_delete.html",
        {"review": review},
    )
