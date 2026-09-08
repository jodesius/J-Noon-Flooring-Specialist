from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "headline",
        "author",
        "rating",
        "is_approved",
        "created_at",
        "updated_at",
    )
    list_editable = ("is_approved",)
    list_filter = ("is_approved", "rating", "created_at")
    search_fields = ("headline", "body", "author__username", "author__email")
    ordering = ("-created_at",)
    readonly_fields = ("slug", "author", "created_at", "updated_at")
    list_per_page = 30

    fieldsets = (
        (None, {"fields": ("author", "rating", "headline", "body", "image")}),
        ("Moderation", {"fields": ("is_approved",)}),
        ("Details", {"fields": ("slug", "created_at", "updated_at")}),
    )

    @admin.action(description="Approve selected reviews")
    def approve_reviews(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f"{updated} review(s) approved.")

    @admin.action(description="Unapprove selected reviews")
    def unapprove_reviews(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f"{updated} review(s) unapproved.")

    actions = ["approve_reviews", "unapprove_reviews"]

    def has_add_permission(self, request):
        # Reviews are created by clients through the site, not in the admin.
        return False
