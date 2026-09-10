"""Shared helpers for removing gallery image files from storage.

Django never deletes an upload when its model row goes away, so both the
admin (`GalleryImageAdmin.delete_model` / `delete_queryset`) and the
`prune_gallery_media` command use these to keep Cloudinary (or the local
`media/` folder) tidy.
"""

from django.conf import settings
from django.core.files.storage import default_storage

GALLERY_SUBDIR = "gallery/"


def is_cloudinary():
    try:
        from cloudinary_storage.storage import MediaCloudinaryStorage
    except ImportError:
        return False
    return isinstance(default_storage, MediaCloudinaryStorage)


def list_stored_files():
    """Every file under ``<storage>/gallery/``, as storage names."""
    if is_cloudinary():
        import cloudinary.api

        prefix = settings.CLOUDINARY_STORAGE.get("PREFIX", "media")
        folder = f"{prefix}/{GALLERY_SUBDIR}"
        names, cursor = set(), None
        while True:
            resp = cloudinary.api.resources(
                type="upload",
                prefix=folder,
                max_results=500,
                next_cursor=cursor,
            )
            names.update(r["public_id"] for r in resp.get("resources", []))
            cursor = resp.get("next_cursor")
            if not cursor:
                break
        return names

    try:
        _dirs, files = default_storage.listdir(GALLERY_SUBDIR)
    except FileNotFoundError:
        return set()
    return {f"{GALLERY_SUBDIR}{name}" for name in files}


def delete_stored_files(names):
    """Best-effort deletion of stored files by name; returns the count removed.

    Failures are swallowed - `prune_gallery_media` is the backstop for any
    file this misses.
    """
    names = [n for n in names if n]
    if not names:
        return 0

    if is_cloudinary():
        import cloudinary.api

        deleted = 0
        for i in range(0, len(names), 100):  # API takes 100 ids per call
            try:
                resp = cloudinary.api.delete_resources(names[i : i + 100])
            except Exception:
                continue
            deleted += sum(
                1 for v in resp.get("deleted", {}).values() if v == "deleted"
            )
        return deleted

    deleted = 0
    for name in names:
        try:
            default_storage.delete(name)
            deleted += 1
        except Exception:
            continue
    return deleted
