from io import BytesIO, StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .management.commands.prune_gallery_media import Command as PruneCommand
from .models import Category, GalleryImage

# Keep test uploads off Cloudinary / the real disk - saving an ImageField
# goes through the configured storage, and a rolled-back test would still
# leave the uploaded file behind.
IN_MEMORY_STORAGE = override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)


def tiny_png():
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (4, 3), "sienna").save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile("shot.png", buf.read(), content_type="image/png")


@IN_MEMORY_STORAGE
class GalleryViewTests(TestCase):
    def setUp(self):
        # A seed migration ships a starter set of categories, so fetch-or-create.
        self.laminate = Category.objects.get_or_create(name="Laminate")[0]
        self.carpet = Category.objects.get_or_create(name="Carpet")[0]

    def test_only_published_images_are_shown(self):
        GalleryImage.objects.create(
            image=tiny_png(), title="Live one", category=self.laminate,
            is_published=True,
        )
        GalleryImage.objects.create(
            image=tiny_png(), title="Hidden one", category=self.laminate,
            is_published=False,
        )

        resp = self.client.get(reverse("gallery:index"))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Live one")
        self.assertNotContains(resp, "Hidden one")

    def test_filter_bar_only_lists_categories_with_published_photos(self):
        GalleryImage.objects.create(
            image=tiny_png(), title="A laminate floor", category=self.laminate,
            is_published=True,
        )

        resp = self.client.get(reverse("gallery:index"))

        self.assertContains(resp, 'data-filter="laminate"')
        self.assertNotContains(resp, 'data-filter="carpet"')

    def test_empty_gallery_renders(self):
        resp = self.client.get(reverse("gallery:index"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Photos coming soon.")


class CategoryModelTests(TestCase):
    def test_slug_is_auto_generated(self):
        cat = Category.objects.create(name="Polished Concrete Look")
        self.assertEqual(cat.slug, "polished-concrete-look")


@IN_MEMORY_STORAGE
class GalleryImageModelTests(TestCase):
    def test_dimensions_are_captured_on_save(self):
        img = GalleryImage.objects.create(image=tiny_png(), title="Sized")
        self.assertEqual((img.width, img.height), (4, 3))

    def test_display_alt_falls_back_to_title(self):
        img = GalleryImage.objects.create(image=tiny_png(), title="Just a title")
        self.assertEqual(img.display_alt, "Just a title")


@IN_MEMORY_STORAGE
class GalleryImageAdminDeleteTests(TestCase):
    """The admin's Delete button and 'Delete selected images' bulk action
    both remove the row *and* the underlying storage file.
    """

    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="root", email="root@example.com", password="pw"
        )
        self.client.force_login(self.admin)

    def test_change_page_delete_removes_row_and_file(self):
        img = GalleryImage.objects.create(image=tiny_png(), title="Mistake")
        name = img.image.name

        with patch("gallery.admin.delete_stored_files") as mock_delete:
            self.client.post(
                reverse("admin:gallery_galleryimage_delete", args=[img.pk]),
                {"post": "yes"},
            )

        self.assertFalse(GalleryImage.objects.filter(pk=img.pk).exists())
        mock_delete.assert_called_once_with([name])

    def test_bulk_delete_action_removes_rows_and_files(self):
        a = GalleryImage.objects.create(image=tiny_png(), title="A")
        b = GalleryImage.objects.create(image=tiny_png(), title="B")

        with patch("gallery.admin.delete_stored_files") as mock_delete:
            self.client.post(
                reverse("admin:gallery_galleryimage_changelist"),
                {
                    "action": "delete_selected",
                    "_selected_action": [a.pk, b.pk],
                    "post": "yes",
                },
            )

        self.assertEqual(GalleryImage.objects.count(), 0)
        mock_delete.assert_called_once()
        self.assertCountEqual(mock_delete.call_args[0][0], [a.image.name, b.image.name])


@IN_MEMORY_STORAGE
class PruneGalleryMediaTests(TestCase):
    def test_deletes_only_files_with_no_row(self):
        kept = GalleryImage.objects.create(image=tiny_png(), title="Kept")
        stored = {kept.image.name, "gallery/orphan-1.jpg", "gallery/orphan-2.jpg"}

        out = StringIO()
        with patch.object(
            PruneCommand, "_list_stored_files", return_value=stored
        ), patch.object(
            PruneCommand, "_delete_files", return_value=2
        ) as delete_mock:
            call_command("prune_gallery_media", "--yes", stdout=out)

        deleted_arg = sorted(delete_mock.call_args[0][0])
        self.assertEqual(deleted_arg, ["gallery/orphan-1.jpg", "gallery/orphan-2.jpg"])
        self.assertIn("Deleted 2 file(s).", out.getvalue())

    def test_dry_run_deletes_nothing(self):
        GalleryImage.objects.create(image=tiny_png(), title="Kept")

        out = StringIO()
        with patch.object(
            PruneCommand, "_list_stored_files", return_value={"gallery/orphan.jpg"}
        ), patch.object(PruneCommand, "_delete_files") as delete_mock:
            call_command("prune_gallery_media", "--dry-run", stdout=out)

        delete_mock.assert_not_called()
        self.assertIn("Dry run", out.getvalue())
