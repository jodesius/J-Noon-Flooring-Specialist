import re

from django.core.exceptions import ValidationError

PROFILE_IMAGE_MAX_BYTES = 1 * 1024 * 1024  # 1 MB
PROFILE_IMAGE_FORMATS = {"PNG", "JPEG"}


def validate_profile_image(image):
    """Profile image rules:

    * 1 MB maximum
    * must genuinely be a PNG or JPEG - the file contents are parsed with
      Pillow, not trusted from the file extension
    """
    if image.size > PROFILE_IMAGE_MAX_BYTES:
        raise ValidationError(
            "Please use the correct format and keep the file size under 1MB."
        )

    # Import here so the rest of the module doesn't need Pillow.
    from PIL import Image, UnidentifiedImageError

    try:
        img = Image.open(image)
        image_format = img.format
        img.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError(
            "Please use the correct format and keep the file size under 1MB."
        )
    finally:
        if hasattr(image, "seek"):
            image.seek(0)

    if image_format not in PROFILE_IMAGE_FORMATS:
        raise ValidationError(
            "Please use the correct format and keep the file size under 1MB."
        )


class SixToTwelvePasswordValidator:
    """Password policy for this project:

    * between 6 and 12 characters long
    * at least one number
    * at least one special (non alphanumeric) character
    """

    def validate(self, password, user=None):
        errors = []

        if not 6 <= len(password) <= 12:
            errors.append(
                ValidationError(
                    "This password must be between 6 and 12 characters long.",
                    code="password_length",
                )
            )
        if not re.search(r"\d", password):
            errors.append(
                ValidationError(
                    "This password must contain at least one number.",
                    code="password_no_number",
                )
            )
        if not re.search(r"[^A-Za-z0-9]", password):
            errors.append(
                ValidationError(
                    "This password must contain at least one special character.",
                    code="password_no_special",
                )
            )

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return (
            "Your password must be 6 to 12 characters long and include at "
            "least one number and one special character."
        )
