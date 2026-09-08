from django.contrib import admin
from django.utils.html import format_html

from .models import Category, GalleryImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order", "image_count")
    list_editable = ("sort_order",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("sort_order", "name")

    @admin.display(description="images")
    def image_count(self, obj):
        return obj.images.count()


@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = (
        "thumb",
        "title",
        "category",
        "is_published",
        "sort_order",
        "created_at",
    )
    list_display_links = ("thumb", "title")
    list_editable = ("category", "is_published", "sort_order")
    list_filter = ("is_published", "category")
    search_fields = ("title", "alt_text")
    ordering = ("sort_order", "-created_at")
    list_per_page = 40
    readonly_fields = ("preview", "width", "height", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("image", "preview", "title", "alt_text", "category")}),
        ("Display", {"fields": ("is_published", "sort_order")}),
        ("Details", {"fields": ("width", "height", "created_at", "updated_at")}),
    )

    @admin.display(description="")
    def thumb(self, obj):
        if not obj.image:
            return "-"
        return format_html(
            '<img src="{}" style="height:48px;width:64px;object-fit:cover;'
            'border-radius:4px;" alt="">',
            obj.thumb_url,
        )

    @admin.display(description="Preview")
    def preview(self, obj):
        if not obj.image:
            return "Upload an image and save to see a preview."
        return format_html(
            '<img src="{}" style="max-width:320px;height:auto;border-radius:6px;" '
            'alt="">',
            obj.thumb_url,
        )
