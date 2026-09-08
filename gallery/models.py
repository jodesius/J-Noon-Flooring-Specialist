import uuid
from pathlib import Path

from django.db import models
from django.utils.text import slugify

from .validators import validate_gallery_image


def gallery_image_upload_to(instance, filename):
    suffix = Path(filename).suffix.lower() or ".jpg"
    return f"gallery/{uuid.uuid4().hex}{suffix}"


def _cloudinary_variant(url, transform):
    """Insert a Cloudinary transformation into an upload URL.

    `https://res.cloudinary.com/<cloud>/image/upload/v123/foo.jpg`
      -> `.../image/upload/<transform>/v123/foo.jpg`

    Any non-Cloudinary URL (e.g. the local `media/` fallback) is returned
    unchanged.
    """
    marker = "/image/upload/"
    if marker in url:
        head, tail = url.split(marker, 1)
        return f"{head}{marker}{transform}/{tail}"
    return url


class Category(models.Model):
    """A flooring type used to group and filter gallery photos."""

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)
    sort_order = models.PositiveIntegerField(
        default=0, help_text="Lower numbers show first in the filter bar."
    )

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class GalleryImage(models.Model):
    """One photo of completed work, uploaded through the admin."""

    image = models.ImageField(
        upload_to=gallery_image_upload_to,
        validators=[validate_gallery_image],
        width_field="width",
        height_field="height",
        help_text="JPEG, PNG or WebP. 10MB maximum.",
    )
    title = models.CharField(max_length=120)
    alt_text = models.CharField(
        max_length=160,
        blank=True,
        help_text=(
            "Short description of the photo for screen readers and search "
            "engines. Falls back to the title if left blank."
        ),
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name="images",
    )

    is_published = models.BooleanField("show on site", default=True)
    sort_order = models.PositiveIntegerField(
        default=0, help_text="Lower numbers show first. Ties break by newest."
    )

    width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    height = models.PositiveIntegerField(null=True, blank=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def display_alt(self):
        return self.alt_text or self.title

    @property
    def thumb_url(self):
        """Optimised image for the grid."""
        return _cloudinary_variant(self.image.url, "f_auto,q_auto,c_limit,w_900")

    @property
    def full_url(self):
        """Larger optimised image for the lightbox."""
        return _cloudinary_variant(self.image.url, "f_auto,q_auto,c_limit,w_1800")
