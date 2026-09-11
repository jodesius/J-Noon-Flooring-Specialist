import datetime as dt
import uuid
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.text import slugify


# ==========================================================================
# AI quote engine
#
# FlooringRate is just the picklist shown on the quote form. QuoteSettings
# is the admin-edited rate card + rules the AI reads. QuoteRequest is one
# customer's answers plus whatever the AI (or the coverage check) decided.
# ==========================================================================

class FlooringRate(models.Model):
    """A flooring system the customer can pick on the quote form. Prices live
    in the rate card (`QuoteSettings.rate_card`), not here - this is just the
    picklist and its display order.
    """

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class QuoteSettings(models.Model):
    """The pricing and rules the AI quoting engine reads. Single row."""

    online_quotes_enabled = models.BooleanField(
        default=True,
        help_text="Master switch. Turn off to send everyone to 'book a call'.",
    )
    rate_card = models.TextField(
        blank=True,
        help_text="Your full pricing, in whatever layout suits you - the AI "
        "reads it as-is. Labour rates, subfloor prep, pattern floors, and how "
        "materials work for supply & fit. Quoting stays off until this is filled.",
    )
    quoting_rules = models.TextField(
        blank=True,
        help_text="How the AI should behave, one rule per line. e.g. 'Assume "
        "8% wastage', 'Minimum charge is half a day', 'I don't fit on stairs'.",
    )
    contingency_pct = models.PositiveSmallIntegerField(
        "estimate headroom (%)", default=10,
        help_text="The AI widens its range by roughly this much to stay safe.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Quote settings"
        verbose_name_plural = "Quote settings"

    def __str__(self):
        return "Quote settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class QuoteRequest(models.Model):
    """A customer's request for a rough quote, plus the AI's response."""

    class Service(models.TextChoices):
        SUPPLY_FIT = "supply_fit", "Supply & Fit"
        INSTALL_ONLY = "install_only", "Installation Only"
        REPAIRS = "repairs", "Repairs & Remedials"

    class Subfloor(models.TextChoices):
        CONCRETE = "concrete", "Concrete"
        FLOORBOARDS = "floorboards", "Timber floorboards"
        CHIPBOARD = "chipboard", "Chipboard / OSB"
        OTHER = "other", "Something else"
        UNKNOWN = "unknown", "Not sure"

    class Condition(models.TextChoices):
        SOUND = "sound", "Looks flat and sound"
        UNEVEN = "uneven", "Uneven / sloping / bouncy"
        DAMAGED = "damaged", "Damaged or damp"
        UNKNOWN = "unknown", "Not sure"

    class Removal(models.TextChoices):
        YES = "yes", "Yes, all of it"
        SOME = "some", "Some of it"
        NO = "no", "No"
        UNKNOWN = "unknown", "Not sure"

    class Beading(models.TextChoices):
        YES = "yes", "Yes please"
        NO = "no", "No thanks"
        UNKNOWN = "unknown", "Not sure - advise me"

    class Timescale(models.TextChoices):
        ASAP = "asap", "As soon as possible"
        SOON = "soon", "Within a month or so"
        FLEXIBLE = "flexible", "No rush / flexible"

    class Status(models.TextChoices):
        NEW = "new", "New"
        AWAITING_INFO = "awaiting_info", "Awaiting customer answers"
        QUOTED = "quoted", "Estimate given"
        CALL_REQUESTED = "call_requested", "Needs a call"
        OUT_OF_AREA = "out_of_area", "Outside coverage area"
        REVIEWED = "reviewed", "Reviewed by staff"

    slug = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    reference = models.CharField(
        max_length=12, editable=False, blank=True, default="", db_index=True,
        help_text="Short code the customer can quote when booking, e.g. JQ0007.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quote_requests"
    )

    service_option = models.CharField(max_length=20, choices=Service.choices)
    flooring_system = models.ForeignKey(
        FlooringRate, on_delete=models.SET_NULL, null=True, blank=True
    )
    flooring_note = models.CharField("flooring notes", max_length=200, blank=True)

    area_sqm = models.DecimalField(
        "floor area (m²)", max_digits=7, decimal_places=1, null=True, blank=True
    )
    area_unknown = models.BooleanField(default=False)
    rooms = models.CharField("rooms / areas", max_length=200, blank=True)
    current_covering = models.CharField(max_length=120, blank=True)
    subfloor_type = models.CharField(
        max_length=20, choices=Subfloor.choices, default=Subfloor.UNKNOWN
    )
    subfloor_condition = models.CharField(
        max_length=20, choices=Condition.choices, default=Condition.UNKNOWN
    )
    removal_needed = models.CharField(
        max_length=20, choices=Removal.choices, default=Removal.UNKNOWN
    )
    beading_wanted = models.CharField(
        max_length=10, choices=Beading.choices, default=Beading.UNKNOWN
    )
    door_trims = models.PositiveSmallIntegerField(null=True, blank=True)
    timescale = models.CharField(
        max_length=20, choices=Timescale.choices, default=Timescale.SOON
    )
    postcode = models.CharField(max_length=12)
    details = models.TextField(blank=True, max_length=2000)

    contact_name = models.CharField(max_length=120)
    contact_phone = models.CharField(max_length=30, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEW
    )
    ai_questions = models.JSONField(default=list, blank=True)
    ai_answers = models.JSONField(default=dict, blank=True)
    ai_result = models.JSONField(null=True, blank=True)
    quote_low = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True
    )
    quote_high = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True
    )
    staff_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.contact_name} - {self.get_service_option_display()} ({self.created_at:%d %b %Y})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.reference:
            self.reference = f"JQ{self.pk:04d}"
            super().save(update_fields=["reference"])

    @property
    def customer_message(self):
        return (self.ai_result or {}).get("customer_message", "")

    @property
    def breakdown(self):
        return (self.ai_result or {}).get("breakdown", [])

    @property
    def assumptions(self):
        return (self.ai_result or {}).get("assumptions", [])

    @property
    def suggested_job_title(self):
        """A first-guess job title to prefill the booking form from this quote."""
        floor = (
            self.flooring_system.name if self.flooring_system
            else (self.flooring_note or "New flooring")
        )
        title = f"{floor} to {self.rooms}" if self.rooms else (
            f"{self.get_service_option_display()} - {floor}"
        )
        return title.strip()[:140]


# ==========================================================================
# Book a call-back
# ==========================================================================

class CallRequest(models.Model):
    """A customer asking for a call-back at a chosen time. Creates an event on
    the fitter's Google Calendar when that's configured.
    """

    class Status(models.TextChoices):
        NEW = "new", "New"
        CALLED = "called", "Called"
        DONE = "done", "Done"

    # Length of the calendar slot the call-back reserves.
    SLOT_MINUTES = 30

    slug = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="call_requests"
    )

    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    preferred_date = models.DateField()
    preferred_time = models.TimeField()
    message = models.TextField(blank=True, max_length=1000)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW)
    calendar_event_id = models.CharField(max_length=200, blank=True)
    staff_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Call {self.name} - {self.preferred_date:%d %b} {self.when_label}"

    @property
    def when_label(self):
        t = self.preferred_time
        return f"{t.hour % 12 or 12}:{t.minute:02d} {'am' if t.hour < 12 else 'pm'}"

    def window(self):
        """Naive (start, end) datetimes for the requested slot."""
        start = dt.datetime.combine(self.preferred_date, self.preferred_time)
        return start, start + dt.timedelta(minutes=self.SLOT_MINUTES)


# ==========================================================================
# "Your projects" - the customer portal
#
# A Job is one booked piece of work. The customer requests it (against a
# quote they've had), Joseph sets the agreed price + start date and confirms
# it, the customer secures it with a non-refundable booking fee (20% of the
# agreed price), and from then on the portal is where progress, photos,
# payments and invoices all live. Payments are recorded by hand for now;
# card payments come later.
# ==========================================================================


def _cloudinary_variant(url, transform):
    """Insert a Cloudinary transform into an upload URL; leave other URLs be."""
    marker = "/image/upload/"
    if marker in url:
        head, tail = url.split(marker, 1)
        return f"{head}{marker}{transform}/{tail}"
    return url


def job_photo_upload_to(instance, filename):
    """Random path - never exposes a user id, job id or reference."""
    suffix = Path(filename).suffix.lower() or ".jpg"
    return f"jobs/{uuid.uuid4().hex}{suffix}"


class Job(models.Model):
    """One booked job, and everything the customer sees about it."""

    class Status(models.TextChoices):
        REQUESTED = "requested", "Booking requested"
        AWAITING_DEPOSIT = "awaiting_deposit", "Awaiting booking fee"
        NOT_STARTED = "not_started", "Booked - not started"
        UNDERWAY = "underway", "Underway"
        COMPLETE = "complete", "Complete"
        CANCELLED = "cancelled", "Cancelled"

    # Statuses where the job is a live booking the customer can follow.
    LIVE_STATUSES = {
        Status.NOT_STARTED, Status.UNDERWAY, Status.COMPLETE,
    }

    # The non-refundable booking fee is this percentage of the agreed price.
    BOOKING_FEE_PERCENT = Decimal("20")

    slug = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    reference = models.CharField(max_length=12, unique=True, editable=False, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jobs"
    )
    quote_request = models.ForeignKey(
        QuoteRequest, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="jobs",
        help_text="The quote this booking came from, if any.",
    )

    contact_name = models.CharField("customer name", max_length=120, blank=True, default="")
    contact_phone = models.CharField("phone", max_length=30, blank=True, default="")

    title = models.CharField(
        max_length=140, help_text="Short name for the job, e.g. 'LVT to kitchen & hall'."
    )
    summary = models.TextField(
        blank=True, help_text="What the work involves - shown to the customer."
    )
    site_address = models.CharField(
        "address of works", max_length=255, blank=True,
        help_text="Where the work is.",
    )

    agreed_price = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True,
        help_text="The price you and the customer have agreed (inc. VAT if applicable). "
        "The booking fee is 20% of this.",
    )
    start_date = models.DateField(
        null=True, blank=True, help_text="Agreed start date."
    )

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.REQUESTED
    )
    customer_note = models.TextField(
        blank=True, max_length=2000,
        help_text="Anything the customer said when they asked to book.",
    )
    staff_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When you confirmed the price and start date.",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference or 'Job'} - {self.title}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.reference:
            self.reference = f"JN{self.pk:04d}"
            super().save(update_fields=["reference"])

    # -- money -----------------------------------------------------------

    @property
    def booking_fee(self):
        """Non-refundable deposit that secures the booking - 20% of the
        agreed price. Comes off the final balance. ``None`` until the price
        is set."""
        if self.agreed_price is None:
            return None
        return (self.agreed_price * self.BOOKING_FEE_PERCENT / 100).quantize(
            Decimal("0.01")
        )

    @property
    def total_paid(self):
        total = self.payments.aggregate(t=Sum("amount"))["t"]
        return total or Decimal("0.00")

    @property
    def balance_due(self):
        if self.agreed_price is None:
            return None
        return self.agreed_price - self.total_paid

    @property
    def deposit_paid(self):
        return self.payments.filter(kind=Payment.Kind.BOOKING_FEE).exists()

    @property
    def is_live(self):
        return self.status in self.LIVE_STATUSES

    @property
    def status_step(self):
        """1-3 for the not started / underway / complete progress bar."""
        return {
            self.Status.NOT_STARTED: 1,
            self.Status.UNDERWAY: 2,
            self.Status.COMPLETE: 3,
        }.get(self.status, 0)

    def recompute_after_payment(self):
        """Move a job on once its booking fee lands. Called after a Payment
        is saved (admin inline today, Stripe webhook later)."""
        if self.status == self.Status.AWAITING_DEPOSIT and self.deposit_paid:
            self.status = self.Status.NOT_STARTED
            self.save(update_fields=["status", "updated_at"])


# ---- work photos ---------------------------------------------------------

class JobPhoto(models.Model):
    """A photo of the work, uploaded by Joseph through the admin."""

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to=job_photo_upload_to)
    caption = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.caption or f"Photo for {self.job.reference}"

    @property
    def thumb_url(self):
        return _cloudinary_variant(self.image.url, "f_auto,q_auto,c_limit,w_900")

    @property
    def full_url(self):
        return _cloudinary_variant(self.image.url, "f_auto,q_auto,c_limit,w_1800")


# ---- money: payments, invoices, itemised invoice lines -------------------
# Payment is the ledger - the single source of truth for what's been paid,
# whether entered by hand or written by a successful CardPayment below.
# Invoice / InvoiceLineItem are what the customer downloads; their totals
# are snapshotted from the ledger at issue time so a PDF never changes later.

class Payment(models.Model):
    """A payment against a job. Recorded by hand for now."""

    class Kind(models.TextChoices):
        BOOKING_FEE = "booking_fee", "Booking fee (deposit)"
        BALANCE = "balance", "Balance payment"
        PART = "part", "Part payment"

    class Method(models.TextChoices):
        CARD = "card", "Card (online)"
        CASH = "cash", "Cash"
        BANK = "bank", "Bank transfer"
        CHEQUE = "cheque", "Cheque"
        OTHER = "other", "Other"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.BALANCE)
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.BANK)
    reference = models.CharField(
        max_length=120, blank=True,
        help_text="Card receipt id, bank reference, etc.",
    )
    note = models.CharField(max_length=200, blank=True)
    received_on = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["received_on", "created_at"]

    def __str__(self):
        return f"£{self.amount} {self.get_kind_display()} - {self.job.reference}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.job.recompute_after_payment()


class Invoice(models.Model):
    """A downloadable invoice / receipt. Values are snapshotted at issue so a
    saved PDF stays a true record even if the job changes afterwards."""

    class Kind(models.TextChoices):
        DEPOSIT = "deposit", "Booking fee receipt"
        RECEIPT = "receipt", "Payment receipt"
        FINAL = "final", "Final invoice"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="invoices")
    number = models.CharField(max_length=16, unique=True, editable=False, blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.FINAL)
    issued_on = models.DateField(default=timezone.localdate)

    agreed_total = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    total_paid = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    # Frozen list of the payments this invoice accounts for, captured at issue
    # so a re-download always shows the same ledger. Each entry:
    # {"label": str, "method": str, "date": "YYYY-MM-DD", "amount": "123.45"}
    payments_snapshot = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.number or f"Invoice for {self.job.reference}"

    def save(self, *args, **kwargs):
        if not self.number:
            last = Invoice.objects.order_by("-id").first()
            seq = (last.id + 1) if last else 1
            self.number = f"INV-{seq:04d}"
        super().save(*args, **kwargs)

    @property
    def balance(self):
        return self.agreed_total - self.total_paid

    def _relevant_payments(self):
        qs = self.job.payments.all()
        if self.kind == self.Kind.DEPOSIT:
            qs = qs.filter(kind=Payment.Kind.BOOKING_FEE)
        return qs.order_by("received_on", "created_at")

    def snapshot_from_job(self):
        """Freeze the money fields and the payment ledger from the job as it
        stands right now."""
        payments = list(self._relevant_payments())
        self.total_paid = sum((p.amount for p in payments), Decimal("0.00"))
        self.agreed_total = self.job.agreed_price or Decimal("0.00")
        self.payments_snapshot = [
            {
                "label": p.get_kind_display(),
                "method": p.get_method_display(),
                "date": p.received_on.isoformat(),
                "amount": str(p.amount),
            }
            for p in payments
        ]

    def ensure_default_line_item(self):
        """Give a freshly issued invoice one sensible line so the PDF is never
        empty. Joseph can then split / rename it in the admin."""
        if self.line_items.exists():
            return
        if self.kind == self.Kind.DEPOSIT:
            desc = (
                "Booking fee to secure your booking - 20% of the "
                f"£{self.job.agreed_price or 0:,.2f} agreed price, non-refundable "
                "and deducted from your final invoice"
            )
            amount = self.total_paid or (self.job.booking_fee or Decimal("0.00"))
        else:
            desc = f"{self.job.title} - flooring supplied and fitted as agreed"
            amount = self.agreed_total
        self.line_items.create(description=desc, amount=amount)

    def sync_total_from_line_items(self):
        """Keep `agreed_total` equal to the sum of the line items (so the PDF,
        the manage panel and the model never disagree). No-op with no items."""
        items = list(self.line_items.all())
        if not items:
            return
        total = sum((li.amount for li in items), Decimal("0.00"))
        if total != self.agreed_total:
            self.agreed_total = total
            self.save(update_fields=["agreed_total"])


class InvoiceLineItem(models.Model):
    """One itemised line on an invoice - what the customer is paying for."""

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="line_items"
    )
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.description} - £{self.amount}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invoice.sync_total_from_line_items()

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        invoice.sync_total_from_line_items()


# ---- Stripe card payments -------------------------------------------------
# Card data never reaches this model - only Stripe's PaymentIntent id and
# its status. mark_succeeded() is the one place a card payment turns into
# real money (a Payment row) and, from there, moves the job along.

class CardPayment(models.Model):
    """One online card payment attempt, tracked through its Stripe lifecycle.

    Created when the customer starts a checkout; `mark_succeeded()` (called by
    the Stripe webhook and/or the return page) writes the money into the
    `Payment` ledger, which in turn moves the job on.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class Purpose(models.TextChoices):
        BOOKING_FEE = "booking_fee", "Booking fee"
        BALANCE = "balance", "Balance in full"
        PART = "part", "Part payment"

    _LEDGER_KIND = {
        Purpose.BOOKING_FEE: "booking_fee",
        Purpose.BALANCE: "balance",
        Purpose.PART: "part",
    }

    slug = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    job = models.ForeignKey(
        Job, on_delete=models.CASCADE, related_name="card_payments"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="card_payments",
    )
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )

    stripe_payment_intent = models.CharField(max_length=64, blank=True, db_index=True)
    client_secret = models.CharField(max_length=255, blank=True)

    payer_name = models.CharField(max_length=160, blank=True)
    payer_email = models.EmailField(blank=True)
    billing_address = models.CharField(max_length=400, blank=True)

    authorised_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=300, blank=True)

    payment = models.OneToOneField(
        Payment, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="card_payment",
    )
    invoice = models.OneToOneField(
        "Invoice", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="source_card_payment",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"£{self.amount} {self.get_purpose_display()} - {self.job.reference}"

    @property
    def amount_pence(self):
        return int((self.amount * 100).quantize(Decimal("1")))

    @property
    def ledger_kind(self):
        return self._LEDGER_KIND[self.purpose]

    @property
    def is_settled(self):
        return self.status == self.Status.SUCCEEDED

    def mark_succeeded(self):
        """Idempotently record the money and move the job on. Safe to call
        from both the webhook and the checkout return page, more than once."""
        if self.status == self.Status.SUCCEEDED and self.payment_id:
            return

        payment = Payment.objects.filter(
            job=self.job, reference=self.stripe_payment_intent
        ).first()
        if payment is None:
            payment = Payment.objects.create(
                job=self.job,
                amount=self.amount,
                kind=self.ledger_kind,
                method=Payment.Method.CARD,
                reference=self.stripe_payment_intent,
                note="Paid online by card",
            )  # Payment.save() runs Job.recompute_after_payment()

        self.status = self.Status.SUCCEEDED
        self.paid_at = self.paid_at or timezone.now()
        self.payment = payment
        self.error_message = ""
        self.save(update_fields=["status", "paid_at", "payment",
                                 "error_message", "updated_at"])

    def mark_failed(self, message=""):
        if self.status == self.Status.SUCCEEDED:
            return
        self.status = self.Status.FAILED
        self.error_message = (message or "")[:300]
        self.save(update_fields=["status", "error_message", "updated_at"])
