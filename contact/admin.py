from django.contrib import admin
from django.utils.html import format_html

from .models import ContactEnquiry, SiteContact


@admin.register(SiteContact)
class SiteContactAdmin(admin.ModelAdmin):
    readonly_fields = ("preview", "updated_at")
    fieldsets = (
        ("You", {"fields": ("photo", "preview", "intro")}),
        ("Contact details", {"fields": ("phone", "email", "enquiry_recipient")}),
        ("Coverage & response", {
            "fields": ("radius_miles", "service_area", "response_time"),
        }),
        ("Social", {"fields": ("facebook", "instagram")}),
        (None, {"fields": ("updated_at",)}),
    )

    def has_add_permission(self, request):
        # Only ever one row.
        return not SiteContact.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Preview")
    def preview(self, obj):
        if not obj or not obj.photo:
            return "Upload a photo and save to see a preview."
        return format_html(
            '<img src="{}" style="max-width:220px;height:auto;border-radius:6px;" '
            'alt="">',
            obj.photo.url,
        )


@admin.register(ContactEnquiry)
class ContactEnquiryAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "postcode", "created_at", "handled")
    list_editable = ("handled",)
    list_filter = ("handled", "created_at")
    search_fields = ("name", "email", "phone", "postcode", "message")
    ordering = ("-created_at",)
    readonly_fields = (
        "name", "email", "phone", "postcode", "message", "created_at",
    )
    fieldsets = (
        (None, {"fields": ("name", "email", "phone", "postcode", "message")}),
        ("Status", {"fields": ("handled", "created_at")}),
    )

    def has_add_permission(self, request):
        # Enquiries only come from the public form.
        return False
