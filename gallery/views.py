from django.shortcuts import render

from .models import Category, GalleryImage


def index(request):
    images = (
        GalleryImage.objects.filter(is_published=True)
        .select_related("category")
    )
    # Only show filter buttons for categories that actually have a photo.
    categories = (
        Category.objects.filter(images__is_published=True)
        .distinct()
        .order_by("sort_order", "name")
    )
    return render(
        request,
        "gallery/index.html",
        {"images": images, "categories": categories},
    )
