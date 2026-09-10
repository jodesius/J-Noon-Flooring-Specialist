import uuid
from pathlib import Path

from django.db import models

from .validators import validate_contact_photo

# Shown while no real photo has been uploaded.
DEFAULT_CONTACT_PHOTO = "https://placehold.co/560x720/3b2a21/e7d9c9?text=Photo+coming+soon"


def contact_photo_upload_to(instance, filename):
    suffix = Path(filename).suffix.lower() or ".jpg"
    return f"contact/{uuid.uuid4().hex}{suffix}"


class SiteContact(models.Model):
    """The business's public contact details - a single row, edited in the
    admin, that feeds the Contact us page.
    """

    photo = models.ImageField(
        upload_to=contact_photo_upload_to,
        blank=True,
        null=True,
        validators=[validate_contact_photo],
        help_text="A photo of you. JPEG / PNG / WebP, 3MB max.",
    )
    intro = models.TextField(
        blank=True,
        help_text="Short personal introduction shown beside the photo.",
    )

    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    enquiry_recipient = models.EmailField(
        blank=True,
        help_text="Where the enquiry form sends messages. Leave blank to use "
        "the email address above.",
    )

    response_time = models.CharField(
        max_length=120,
        blank=True,
        default="I usually reply the same day",
    )
    radius_miles = models.PositiveSmallIntegerField(
        default=25,
        help_text="Coverage radius drawn on the map, in miles.",
    )
    service_area = models.CharField(
        max_length=255,
        blank=True,
        default=(
            "Chelmsford, Braintree, Witham, Maldon, Billericay, Brentwood, "
            "South Woodham Ferrers and the surrounding villages"
        ),
        help_text="Towns listed under “Where we cover”.",
    )

    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site contact details"
        verbose_name_plural = "Site contact details"

    def __str__(self):
        return "Site contact details"

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce a single row
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def photo_url(self):
        return self.photo.url if self.photo else DEFAULT_CONTACT_PHOTO

    @property
    def enquiry_email(self):
        return self.enquiry_recipient or self.email


class ContactEnquiry(models.Model):
    """A message sent through the Contact us form. Stored so nothing is lost
    if the notification email fails.
    """

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    postcode = models.CharField(max_length=12, blank=True)
    message = models.TextField(max_length=3000)

    handled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Contact enquiries"

    def __str__(self):
        return f"{self.name} - {self.created_at:%d %b %Y}"
