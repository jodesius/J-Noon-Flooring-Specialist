from django.contrib import admin

from .models import FAQItem


@admin.register(FAQItem)
class FAQItemAdmin(admin.ModelAdmin):
    list_display = ("question", "category", "is_active", "sort_order")
    list_filter = ("category", "is_active")
    list_editable = ("is_active", "sort_order")
    search_fields = ("question", "answer")
    ordering = ("category", "sort_order", "id")
