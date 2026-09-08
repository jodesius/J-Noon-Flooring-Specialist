from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Profile, User


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "is_staff", "is_active", "date_joined")
    ordering = ("-date_joined",)
    inlines = [ProfileInline]
