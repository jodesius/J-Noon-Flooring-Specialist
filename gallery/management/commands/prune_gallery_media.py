"""Delete stored gallery image files that no longer have a database row.

Django removes the `GalleryImage` row when a photo is deleted (or replaced)
in the admin, but it deliberately leaves the underlying file in place. Over
time that leaves orphans in Cloudinary (or the local `media/` folder). This
command finds files under the gallery folder with no matching row and
deletes them.

    python manage.py prune_gallery_media --dry-run   # just list them
    python manage.py prune_gallery_media             # delete, with a prompt
    python manage.py prune_gallery_media --yes        # delete, no prompt
"""

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from gallery.models import GalleryImage

GALLERY_SUBDIR = "gallery/"


def _is_cloudinary():
    try:
        from cloudinary_storage.storage import MediaCloudinaryStorage
    except ImportError:
        return False
    return isinstance(default_storage, MediaCloudinaryStorage)


class Command(BaseCommand):
    help = "Delete gallery image files that have no matching GalleryImage row."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List orphaned files without deleting anything.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Delete without the confirmation prompt.",
        )

    def handle(self, *args, **options):
        used = {
            name
            for name in GalleryImage.objects.values_list("image", flat=True)
            if name
        }
        stored = self._list_stored_files()
        orphans = sorted(stored - used)

        if not orphans:
            self.stdout.write(self.style.SUCCESS("No orphaned gallery files."))
            return

        self.stdout.write(f"{len(orphans)} orphaned file(s):")
        for name in orphans:
            self.stdout.write(f"  {name}")

        if options["dry_run"]:
            self.stdout.write("Dry run - nothing deleted.")
            return

        if not options["yes"]:
            answer = input(f"Delete these {len(orphans)} file(s)? [y/N] ")
            if answer.strip().lower() not in {"y", "yes"}:
                self.stdout.write("Aborted.")
                return

        deleted = self._delete_files(orphans)
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} file(s)."))

    # -- storage helpers ---------------------------------------------------

    def _list_stored_files(self):
        """Every file under <storage>/gallery/, as storage names."""
        if _is_cloudinary():
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

    def _delete_files(self, names):
        if _is_cloudinary():
            import cloudinary.api

            deleted = 0
            names = list(names)
            for i in range(0, len(names), 100):  # API takes 100 ids per call
                resp = cloudinary.api.delete_resources(names[i : i + 100])
                deleted += sum(
                    1 for v in resp.get("deleted", {}).values() if v == "deleted"
                )
            return deleted

        deleted = 0
        for name in names:
            default_storage.delete(name)
            deleted += 1
        return deleted
