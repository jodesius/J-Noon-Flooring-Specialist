import datetime as dt
import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify


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

    class Timescale(models.TextChoices):
        ASAP = "asap", "As soon as possible"
        SOON = "soon", "Within a month or so"
        FLEXIBLE = "flexible", "No rush / flexible"

    class Status(models.TextChoices):
        NEW = "new", "New"
        AWAITING_INFO = "awaiting_info", "Awaiting customer answers"
        QUOTED = "quoted", "Estimate given"
        CALL_REQUESTED = "call_requested", "Needs a call"
        REVIEWED = "reviewed", "Reviewed by staff"

    slug = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
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

    @property
    def customer_message(self):
        return (self.ai_result or {}).get("customer_message", "")

    @property
    def breakdown(self):
        return (self.ai_result or {}).get("breakdown", [])

    @property
    def assumptions(self):
        return (self.ai_result or {}).get("assumptions", [])


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
