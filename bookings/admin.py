import json

from django.contrib import admin, messages
from django.core.files.storage import default_storage
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    CallRequest, FlooringRate, Invoice, InvoiceLineItem, Job, JobPhoto,
    Payment, QuoteRequest, QuoteSettings,
)


def _delete_stored(name):
    if not name:
        return
    try:
        default_storage.delete(name)
    except Exception:
        pass


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
        "reference", "contact_name", "service_option", "flooring_system",
        "area_display", "postcode", "status", "quote_display", "created_at",
    )
    list_filter = ("status", "service_option", "created_at")
    search_fields = ("reference", "contact_name", "contact_phone", "postcode", "details")
    ordering = ("-created_at",)
    list_editable = ("status",)
    readonly_fields = (
        "reference", "user", "created_at", "updated_at", "slug",
        "service_option", "flooring_system", "flooring_note",
        "area_sqm", "area_unknown", "rooms", "current_covering",
        "subfloor_type", "subfloor_condition", "removal_needed", "timescale",
        "postcode", "details", "contact_name", "contact_phone",
        "ai_questions", "ai_answers", "ai_result_pretty",
        "quote_low", "quote_high",
    )
    fieldsets = (
        ("Customer", {"fields": ("reference", "user", "contact_name",
                                 "contact_phone", "postcode")}),
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


# --------------------------------------------------------------------------
# "Your projects" - the customer portal
# --------------------------------------------------------------------------

class JobPhotoInline(admin.TabularInline):
    model = JobPhoto
    extra = 1
    fields = ("image", "caption", "created_at")
    readonly_fields = ("created_at",)

    def delete_model(self, request, obj):
        name = obj.image.name
        super().delete_model(request, obj)
        _delete_stored(name)


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ("amount", "kind", "method", "received_on", "reference", "note")


class InvoiceInline(admin.TabularInline):
    model = Invoice
    extra = 0
    fields = ("number", "kind", "issued_on", "agreed_total", "total_paid", "balance_display")
    readonly_fields = ("number", "agreed_total", "total_paid", "balance_display")

    @admin.display(description="balance")
    def balance_display(self, obj):
        return f"£{obj.balance:.2f}" if obj.pk else "-"

    def has_add_permission(self, request, obj=None):
        # Invoices are created by the "Issue …" actions so their money
        # fields get snapshotted from the job.
        return False


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "reference", "title", "customer", "status", "agreed_price",
        "balance_display", "start_date", "created_at",
    )
    list_filter = ("status", "start_date", "created_at")
    list_editable = ("status",)
    search_fields = ("reference", "title", "contact_name", "user__username",
                     "user__email", "site_address")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    inlines = (JobPhotoInline, PaymentInline, InvoiceInline)
    readonly_fields = (
        "reference", "slug", "user", "quote_request", "customer_note",
        "created_at", "updated_at", "confirmed_at",
        "booking_fee_display", "total_paid_display", "balance_display",
    )
    fieldsets = (
        ("Customer", {"fields": ("user", "contact_name", "contact_phone",
                                 "quote_request", "customer_note")}),
        ("The job", {"fields": ("title", "summary", "site_address")}),
        ("Agreed terms", {
            "fields": ("agreed_price", "start_date", "booking_fee_display",
                       "total_paid_display", "balance_display"),
        }),
        ("Status", {"fields": ("status", "staff_notes", "reference",
                               "created_at", "confirmed_at", "updated_at")}),
    )
    actions = ("confirm_booking", "issue_deposit_receipt", "issue_final_invoice")

    @admin.display(description="customer")
    def customer(self, obj):
        return obj.contact_name or obj.user.get_username()

    @admin.display(description="booking fee (20% of agreed price)")
    def booking_fee_display(self, obj):
        fee = obj.booking_fee
        return f"£{fee:.2f}" if fee is not None else "— (set the agreed price)"

    @admin.display(description="balance")
    def balance_display(self, obj):
        b = obj.balance_due
        return "-" if b is None else f"£{b:.2f}"

    @admin.display(description="paid so far")
    def total_paid_display(self, obj):
        return f"£{obj.total_paid:.2f}"

    @admin.action(description="Confirm booking (needs price + start date)")
    def confirm_booking(self, request, queryset):
        done = 0
        for job in queryset:
            if job.agreed_price is None or job.start_date is None:
                self.message_user(
                    request,
                    f"{job.reference}: set an agreed price and start date first.",
                    level=messages.WARNING,
                )
                continue
            job.status = Job.Status.AWAITING_DEPOSIT
            job.confirmed_at = timezone.now()
            job.save(update_fields=["status", "confirmed_at", "updated_at"])
            done += 1
        if done:
            self.message_user(
                request,
                f"{done} job(s) confirmed - the customer can now pay the booking fee.",
            )

    @admin.action(description="Issue booking fee receipt")
    def issue_deposit_receipt(self, request, queryset):
        self._issue(request, queryset, Invoice.Kind.DEPOSIT)

    @admin.action(description="Issue final invoice")
    def issue_final_invoice(self, request, queryset):
        self._issue(request, queryset, Invoice.Kind.FINAL)

    def _issue(self, request, queryset, kind):
        made = []
        for job in queryset:
            inv = Invoice(job=job, kind=kind)
            inv.snapshot_from_job()
            inv.save()
            inv.ensure_default_line_item()
            made.append(inv.number)
        if made:
            self.message_user(request, f"Created {', '.join(made)}.")

    def has_add_permission(self, request):
        # Jobs start life as a customer booking request; staff create them
        # only in the rare "we've only spoken on the phone" case, which is
        # still allowed via the customer's account. Keep the button off.
        return False

    def delete_model(self, request, obj):
        names = [p.image.name for p in obj.photos.all()]
        super().delete_model(request, obj)
        for name in names:
            _delete_stored(name)

    def delete_queryset(self, request, queryset):
        names = [p.image.name for job in queryset for p in job.photos.all()]
        super().delete_queryset(request, queryset)
        for name in names:
            _delete_stored(name)


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 1
    fields = ("description", "amount", "sort_order")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "job", "kind", "issued_on", "agreed_total",
                    "total_paid", "balance_display")
    list_filter = ("kind", "issued_on")
    search_fields = ("number", "job__reference", "job__title")
    ordering = ("-created_at",)
    inlines = (InvoiceLineItemInline,)
    readonly_fields = ("number", "job", "kind", "agreed_total", "total_paid",
                       "payments_snapshot", "created_at")
    fieldsets = (
        (None, {"fields": ("number", "job", "kind", "issued_on")}),
        ("Itemise the work in the lines below. The subtotal follows their sum.",
         {"fields": ("agreed_total", "total_paid", "notes")}),
        ("Frozen at issue", {"fields": ("payments_snapshot", "created_at"),
                             "classes": ("collapse",)}),
    )

    @admin.display(description="balance")
    def balance_display(self, obj):
        return f"£{obj.balance:.2f}"

    def has_add_permission(self, request):
        return False
