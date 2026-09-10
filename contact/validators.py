from django.core.exceptions import ValidationError

CONTACT_PHOTO_MAX_BYTES = 3 * 1024 * 1024  # 3 MB
CONTACT_PHOTO_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_contact_photo(image):
    """Contact photo rules: 3 MB max, and genuinely a JPEG / PNG / WebP image
    (the file is parsed with Pillow, not trusted from its extension).
    """
    if image.size > CONTACT_PHOTO_MAX_BYTES:
        raise ValidationError("Please keep the image under 3MB.")

    from PIL import Image, UnidentifiedImageError

    try:
        img = Image.open(image)
        image_format = img.format
        img.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("Please upload a valid JPEG, PNG or WebP image.")
    finally:
        if hasattr(image, "seek"):
            image.seek(0)

    if image_format not in CONTACT_PHOTO_FORMATS:
        raise ValidationError("Please upload a valid JPEG, PNG or WebP image.")
