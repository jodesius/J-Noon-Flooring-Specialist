from django.core.exceptions import ValidationError

# A job chat photo (e.g. a snag or a "is this right?" shot) is bigger than a
# profile picture, so it gets a more generous limit than accounts' 1MB one.
MESSAGE_PHOTO_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
MESSAGE_PHOTO_FORMATS = {"PNG", "JPEG"}


def validate_message_photo(image):
    """Chat photo rules:

    * 5 MB maximum
    * must genuinely be a PNG or JPEG - the file contents are parsed with
      Pillow, not trusted from the file extension
    """
    if image.size > MESSAGE_PHOTO_MAX_BYTES:
        raise ValidationError("Please keep the photo under 5MB.")

    # Import here so the rest of the module doesn't need Pillow.
    from PIL import Image, UnidentifiedImageError

    try:
        img = Image.open(image)
        image_format = img.format
        img.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("Please attach a PNG or JPEG photo.")
    finally:
        if hasattr(image, "seek"):
            image.seek(0)

    if image_format not in MESSAGE_PHOTO_FORMATS:
        raise ValidationError("Please attach a PNG or JPEG photo.")


# Work-in-progress photos are portfolio-quality shots, same rules as gallery.
JOB_PHOTO_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
JOB_PHOTO_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_job_photo(image):
    """Work photo rules:

    * 10 MB maximum
    * must genuinely be a JPEG, PNG or WebP - the file contents are parsed
      with Pillow, not trusted from the file extension
    """
    if image.size > JOB_PHOTO_MAX_BYTES:
        raise ValidationError("Please keep the photo under 10MB.")

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

    if image_format not in JOB_PHOTO_FORMATS:
        raise ValidationError("Please upload a valid JPEG, PNG or WebP image.")
