from django.core.exceptions import ValidationError

REVIEW_IMAGE_MAX_BYTES = 4 * 1024 * 1024  # 4 MB
REVIEW_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_review_image(image):
    """Review photo rules: 4 MB max, and genuinely a JPEG / PNG / WebP image
    (the file is parsed with Pillow, not trusted from its extension).
    """
    if image.size > REVIEW_IMAGE_MAX_BYTES:
        raise ValidationError("Please keep the image under 4MB.")

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

    if image_format not in REVIEW_IMAGE_FORMATS:
        raise ValidationError("Please upload a valid JPEG, PNG or WebP image.")
