import uuid
from pathlib import Path

from django.conf import settings
from django.db import models

from .validators import validate_review_image

# Shown on postcards that have no uploaded photo. Swap for your own asset.
DEFAULT_REVIEW_IMAGE = (
    "https://res.cloudinary.com/ddmslr9na/image/upload/"
    "f_auto,q_auto,w_800/v1788896276/"
    "ChatGPT_Image_Sep_8_2026_08_34_05_PM-_ycy2tz.webp"
)


def review_image_upload_to(instance, filename):
    suffix = Path(filename).suffix.lower() or ".jpg"
    return f"reviews/{uuid.uuid4().hex}{suffix}"


class Review(models.Model):
    """A client's postcard-style review of a completed job."""

    class Rating(models.IntegerChoices):
        ONE = 1, "1 - Poor"
        TWO = 2, "2 - Fair"
        THREE = 3, "3 - Good"
        FOUR = 4, "4 - Very good"
        FIVE = 5, "5 - Excellent"

    # Public identifier used in edit/delete URLs (never the sequential pk).
    slug = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )

    rating = models.PositiveSmallIntegerField(choices=Rating.choices)
    headline = models.CharField(max_length=80)
    body = models.TextField(max_length=1500)
    image = models.ImageField(
        upload_to=review_image_upload_to,
        blank=True,
        null=True,
        validators=[validate_review_image],
        help_text="Optional photo of the finished work. JPEG / PNG / WebP, 4MB max.",
    )

    # Reviews are hidden from the site until an admin approves them.
    is_approved = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.headline} - {self.author}"

    @property
    def image_url(self):
        return self.image.url if self.image else DEFAULT_REVIEW_IMAGE

    @property
    def star_range(self):
        """1..5 as a list, for rendering filled/empty stars in templates."""
        return range(1, 6)
