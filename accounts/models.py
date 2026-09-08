import uuid
from pathlib import Path

from django.contrib.auth.models import AbstractUser
from django.db import models

from .validators import validate_profile_image


class User(AbstractUser):
    """Project user.

    Same as Django's default user, but the email address is unique and
    required so it can be used to log in and to reset a password.
    """

    email = models.EmailField("email address", unique=True)
    email_verified = models.BooleanField("email verified", default=False)

    # username stays the USERNAME_FIELD; email is also asked for by
    # `createsuperuser` because it is listed here.
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return self.username

    @property
    def is_site_admin(self):
        """Superuser, or a member of the Site Administrators group."""
        return (
            self.is_superuser
            or self.groups.filter(name="Site Administrators").exists()
        )


def profile_image_upload_to(instance, filename):
    """Store uploads under a random name so the path never exposes the
    user's id or username.
    """
    suffix = Path(filename).suffix.lower() or ".png"
    return f"profile_images/{uuid.uuid4().hex}{suffix}"


class Profile(models.Model):
    """A user's optional public-facing details. One per user.

    Reached only via ``request.user`` - there is no id, username or other
    identifier in any profile URL, so one account cannot act on another.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile"
    )

    image = models.ImageField(
        "profile image",
        upload_to=profile_image_upload_to,
        blank=True,
        null=True,
        validators=[validate_profile_image],
        help_text="PNG or JPEG, 1MB maximum.",
    )

    pronouns = models.CharField(max_length=40, blank=True)
    phone = models.CharField("phone number", max_length=30, blank=True)
    contact_email = models.EmailField("contact email", blank=True)
    about = models.TextField("about me", blank=True)

    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    linkedin = models.URLField(blank=True)
    website = models.URLField("personal website", blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s profile"
