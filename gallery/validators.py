from django.core.exceptions import ValidationError

GALLERY_IMAGE_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
GALLERY_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_gallery_image(image):
    """Gallery photo rules: 10 MB max, and genuinely a JPEG / PNG / WebP image
    (the file is parsed with Pillow, not trusted from its extension).
    """
    if image.size > GALLERY_IMAGE_MAX_BYTES:
        raise ValidationError("Please keep the image under 10MB.")

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

    if image_format not in GALLERY_IMAGE_FORMATS:
        raise ValidationError("Please upload a valid JPEG, PNG or WebP image.")
