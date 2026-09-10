import json

from django.contrib import admin
from django.utils.html import format_html

from .models import CallRequest, FlooringRate, QuoteRequest, QuoteSettings


@admin.register(CallRequest)
class CallRequestAdmin(admin.ModelAdmin):
    list_display = (
        "name", "phone", "preferred_date", "preferred_time", "status",
        "on_calendar", "created_at",
    )
    list_filter = ("status", "preferred_date")
    list_editable = ("status",)
    search_fields = ("name", "phone", "message")
    ordering = ("-created_at",)
    readonly_fields = (
        "user", "name", "phone", "preferred_date", "preferred_time",
        "message", "calendar_event_id", "created_at", "updated_at",
    )
    fieldsets = (
        (None, {"fields": ("user", "name", "phone")}),
        ("Requested", {"fields": ("preferred_date", "preferred_time", "message")}),
        ("Handling", {"fields": ("status", "staff_notes", "calendar_event_id",
                                 "created_at", "updated_at")}),
    )

    def has_add_permission(self, request):
        return False

    @admin.display(description="calendar", boolean=True)
    def on_calendar(self, obj):
        return bool(obj.calendar_event_id)


@admin.register(FlooringRate)
class FlooringRateAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("sort_order", "name")


@admin.register(QuoteSettings)
class QuoteSettingsAdmin(admin.ModelAdmin):
    readonly_fields = ("updated_at",)
    fieldsets = (
        (None, {"fields": ("online_quotes_enabled",)}),
        ("Pricing the AI reads", {
            "fields": ("rate_card", "quoting_rules", "contingency_pct"),
        }),
        (None, {"fields": ("updated_at",)}),
    )

    def has_add_permission(self, request):
        return not QuoteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(QuoteRequest)
class QuoteRequestAdmin(admin.ModelAdmin):
    list_display = (
        "contact_name", "service_option", "flooring_system", "area_display",
        "postcode", "status", "quote_display", "created_at",
    )
    list_filter = ("status", "service_option", "created_at")
    search_fields = ("contact_name", "contact_phone", "postcode", "details")
    ordering = ("-created_at",)
    list_editable = ("status",)
    readonly_fields = (
        "user", "created_at", "updated_at", "slug",
        "service_option", "flooring_system", "flooring_note",
        "area_sqm", "area_unknown", "rooms", "current_covering",
        "subfloor_type", "subfloor_condition", "removal_needed", "timescale",
        "postcode", "details", "contact_name", "contact_phone",
        "ai_questions", "ai_answers", "ai_result_pretty",
        "quote_low", "quote_high",
    )
    fieldsets = (
        ("Customer", {"fields": ("user", "contact_name", "contact_phone", "postcode")}),
        ("What they want", {
            "fields": ("service_option", "flooring_system", "flooring_note",
                       "area_sqm", "area_unknown", "rooms", "current_covering",
                       "subfloor_type", "subfloor_condition", "removal_needed",
                       "timescale", "details"),
        }),
        ("AI estimate", {
            "fields": ("ai_questions", "ai_answers", "quote_low", "quote_high",
                       "ai_result_pretty"),
        }),
        ("Handling", {"fields": ("status", "staff_notes", "created_at", "updated_at")}),
    )

    def has_add_permission(self, request):
        return False

    @admin.display(description="area")
    def area_display(self, obj):
        if obj.area_unknown:
            return "?"
        return f"{obj.area_sqm} m²" if obj.area_sqm else "-"

    @admin.display(description="estimate")
    def quote_display(self, obj):
        if obj.quote_low and obj.quote_high:
            return f"£{obj.quote_low:.0f}–£{obj.quote_high:.0f}"
        return "-"

    @admin.display(description="AI result (full)")
    def ai_result_pretty(self, obj):
        if not obj.ai_result:
            return "-"
        return format_html(
            "<pre style='white-space:pre-wrap'>{}</pre>",
            json.dumps(obj.ai_result, indent=2),
        )
