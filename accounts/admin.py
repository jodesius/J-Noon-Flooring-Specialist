from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Profile, User

# Fields a non-superuser must never be able to set (privilege escalation).
SUPERUSER_ONLY_FIELDS = ("is_superuser", "groups", "user_permissions")


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "email_verified",
        "is_staff",
        "is_active",
        "date_joined",
    )
    list_editable = ("email_verified",)
    list_filter = UserAdmin.list_filter + ("email_verified",)
    fieldsets = UserAdmin.fieldsets + (
        ("Verification", {"fields": ("email_verified",)}),
    )
    ordering = ("-date_joined",)
    inlines = [ProfileInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            # Non-superusers can't see, open, edit or bulk-delete a superuser.
            qs = qs.exclude(is_superuser=True)
        return qs

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.is_superuser:
            return fieldsets
        # Hide the superuser-only fields from everyone else.
        trimmed = []
        for name, opts in fieldsets:
            fields = tuple(
                f for f in opts.get("fields", ())
                if f not in SUPERUSER_ONLY_FIELDS
            )
            trimmed.append((name, {**opts, "fields": fields}))
        return trimmed

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)
