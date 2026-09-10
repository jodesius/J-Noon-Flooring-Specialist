"""Delete stored gallery image files that no longer have a database row.

Deleting or replacing a photo in the admin removes the file too (see
`GalleryImageAdmin`), but files can still be orphaned by older deletes,
direct DB edits, or a failed cleanup. This command finds files under the
gallery folder with no matching row and deletes them.

    python manage.py prune_gallery_media --dry-run   # just list them
    python manage.py prune_gallery_media             # delete, with a prompt
    python manage.py prune_gallery_media --yes        # delete, no prompt
"""

from django.core.management.base import BaseCommand

from gallery.cleanup import delete_stored_files, list_stored_files
from gallery.models import GalleryImage


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
        orphans = sorted(self._list_stored_files() - used)

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

    # Thin wrappers around gallery.cleanup so tests can patch them.
    def _list_stored_files(self):
        return list_stored_files()

    def _delete_files(self, names):
        return delete_stored_files(names)
