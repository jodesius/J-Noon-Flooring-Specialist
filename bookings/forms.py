import datetime as _dt

from django import forms
from django.utils import timezone

from .models import CallRequest, FlooringRate, Job, Payment, QuoteRequest


# ==========================================================================
# Get a free quote
# ==========================================================================

class QuoteStartForm(forms.ModelForm):
    website = forms.CharField(  # honeypot
        required=False, label="Leave this field blank",
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )

    class Meta:
        model = QuoteRequest
        fields = [
            "service_option", "flooring_system", "flooring_note",
            "area_sqm", "area_unknown", "rooms", "current_covering",
            "subfloor_type", "subfloor_condition", "removal_needed",
            "beading_wanted", "door_trims",
            "timescale", "postcode", "details",
            "contact_name", "contact_phone",
        ]
        widgets = {
            "service_option": forms.RadioSelect,
            "flooring_note": forms.TextInput(
                attrs={"placeholder": "e.g. something hard-wearing for a hallway"}
            ),
            "rooms": forms.TextInput(
                attrs={"placeholder": "e.g. two bedrooms and the landing"}
            ),
            "current_covering": forms.TextInput(
                attrs={"placeholder": "e.g. old carpet, tiles, bare boards"}
            ),
            "door_trims": forms.NumberInput(attrs={"min": 0, "placeholder": "e.g. 3"}),
            "details": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "flooring_system": "Flooring you're after",
            "flooring_note": "…or describe what you want",
            "area_sqm": "Approx floor area (m²)",
            "area_unknown": "I'm not sure of the area",
            "current_covering": "What's down at the moment?",
            "subfloor_type": "What's under the current floor?",
            "subfloor_condition": "How does the floor seem?",
            "removal_needed": "Does the old flooring need lifting?",
            "beading_wanted": "Beading around the edges?",
            "door_trims": "Doorway threshold bars",
            "details": "Anything else that helps",
            "contact_name": "Your name",
            "contact_phone": "Phone (optional)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # No blank "- Select an option -" choice on the radio group.
        self.fields["service_option"].choices = QuoteRequest.Service.choices

        self.fields["flooring_system"].queryset = FlooringRate.objects.filter(
            is_active=True
        )
        self.fields["flooring_system"].required = False
        self.fields["flooring_system"].empty_label = "Not sure / help me choose"

        self.fields["flooring_note"].help_text = (
            "Only if you're not sure which system - roughly what are you after?"
        )
        self.fields["area_sqm"].help_text = "A rough length x width of each room is fine."
        self.fields["beading_wanted"].help_text = (
            "The trim that covers the gap where a hard floor meets the skirting - "
            "£1 per metre. Most laminate / LVT / wood floors need it."
        )
        self.fields["door_trims"].required = False
        self.fields["door_trims"].help_text = (
            "£5 each. Roughly how many doorways into these rooms? "
            "Leave blank and I'll estimate."
        )
        self.fields["details"].help_text = (
            "Access, awkward corners, deadlines, anything unusual."
        )
        self.fields["postcode"].widget.attrs["placeholder"] = "CM1 1AA"

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("This request could not be sent.")
        return ""

    def clean_contact_name(self):
        return self.cleaned_data["contact_name"].strip()

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("area_unknown") and not cleaned.get("area_sqm"):
            self.add_error(
                "area_sqm",
                "Give a rough area, or tick \"I'm not sure of the area\".",
            )
        if not cleaned.get("flooring_system") and not cleaned.get("flooring_note"):
            self.add_error(
                "flooring_note",
                "Pick a flooring type, or tell us roughly what you want.",
            )
        return cleaned


# ==========================================================================
# Book a call-back
# ==========================================================================

def _time_choices():
    out = []
    for hour in range(8, 20):          # 8:00 am to 7:30 pm
        for minute in (0, 30):
            value = f"{hour:02d}:{minute:02d}"
            label = f"{hour % 12 or 12}:{minute:02d} {'am' if hour < 12 else 'pm'}"
            out.append((value, label))
    return out


class CallRequestForm(forms.ModelForm):
    website = forms.CharField(  # honeypot
        required=False, label="Leave this field blank",
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )
    preferred_time = forms.TypedChoiceField(
        choices=_time_choices(),
        coerce=lambda v: _dt.time(*(int(x) for x in v.split(":"))),
        label="What time suits you?",
        help_text="I'll aim to call around then.",
    )

    class Meta:
        model = CallRequest
        fields = ["name", "phone", "preferred_date", "preferred_time", "message"]
        widgets = {
            "preferred_date": forms.DateInput(attrs={"type": "date"}),
            "message": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Optional - anything you'd like me to know first"}
            ),
        }
        labels = {
            "name": "Your name",
            "phone": "Phone number",
            "preferred_date": "Day that suits you",
            "message": "Message (optional)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields["preferred_date"].widget.attrs["min"] = today.isoformat()
        self.fields["preferred_date"].widget.attrs["max"] = (
            today + timezone.timedelta(days=21)
        ).isoformat()

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("This request could not be sent.")
        return ""

    def clean_name(self):
        return self.cleaned_data["name"].strip()

    def clean_preferred_date(self):
        date = self.cleaned_data["preferred_date"]
        today = timezone.localdate()
        if date < today:
            raise forms.ValidationError("Please pick today or a day in the future.")
        if date > today + timezone.timedelta(days=21):
            raise forms.ValidationError("Please pick a day within the next three weeks.")
        return date


# ==========================================================================
# Book a job / "Your projects" portal
# ==========================================================================

class BookJobForm(forms.ModelForm):
    """Customer asks to book a job. Joseph then sets the price and confirms.

    Pasting a quote reference (`QuoteRequest.reference`) links that quote and
    fills any field the customer left blank from their quote answers.
    """

    website = forms.CharField(  # honeypot
        required=False, label="Leave this field blank",
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )
    quote_reference = forms.CharField(
        required=False, label="Quote reference",
        widget=forms.TextInput(
            attrs={"placeholder": "e.g. JQ0007", "autocapitalize": "characters"}
        ),
    )

    # Filled in by clean() so the view can link it to the new Job.
    matched_quote = None

    class Meta:
        model = Job
        fields = ["title", "site_address", "contact_name", "contact_phone",
                  "customer_note"]
        widgets = {
            "title": forms.TextInput(
                attrs={"placeholder": "e.g. LVT to the kitchen and hallway"}
            ),
            "site_address": forms.Textarea(
                attrs={"rows": 2, "placeholder": "House / flat, street, town, postcode"}
            ),
            "customer_note": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Anything you'd like me to know - "
                       "preferred start dates, access, questions about the quote…"}
            ),
        }
        labels = {
            "title": "What's the job?",
            "site_address": "Address where the work is",
            "contact_name": "Your name",
            "contact_phone": "Phone number",
            "customer_note": "Message (optional)",
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.matched_quote = None
        self.fields["quote_reference"].help_text = (
            "Had a quote online? Paste its reference and I'll bring your answers "
            "across so you don't retype them. No quote? Just leave it blank."
        )
        # Enforced in clean(), after any prefill from the quote.
        for name in ("title", "site_address", "contact_name"):
            self.fields[name].required = False
        self.fields["site_address"].help_text = (
            "Full address - house / flat, street, town and postcode."
        )
        self.fields["customer_note"].help_text = ""

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("This request could not be sent.")
        return ""

    def clean_quote_reference(self):
        ref = (self.cleaned_data.get("quote_reference") or "").strip().upper()
        if not ref:
            return ""
        self.matched_quote = QuoteRequest.objects.filter(
            reference__iexact=ref, user=self.user
        ).first()
        if self.matched_quote is None:
            raise forms.ValidationError(
                "I couldn't find a quote with that reference on your account. "
                "Check the code, or leave it blank and fill the details in below."
            )
        return ref

    def clean(self):
        cleaned = super().clean()
        quote = self.matched_quote
        if quote:
            if not cleaned.get("title"):
                cleaned["title"] = quote.suggested_job_title
            if not cleaned.get("contact_name"):
                cleaned["contact_name"] = quote.contact_name
            if not cleaned.get("contact_phone"):
                cleaned["contact_phone"] = quote.contact_phone
            if not cleaned.get("site_address"):
                cleaned["site_address"] = quote.postcode

        for name in ("title", "contact_name"):
            if cleaned.get(name):
                cleaned[name] = cleaned[name].strip()

        for name, message in (
            ("title", "Tell me what the job is, or paste a quote reference above."),
            ("contact_name", "I need a name for the booking."),
            ("site_address", "I need the address where the work is."),
        ):
            if not (cleaned.get(name) or "").strip():
                self.add_error(name, message)
        return cleaned


# Staff-only forms used by the manage panel (accept a booking, log a payment)
class ConfirmBookingForm(forms.ModelForm):
    """Staff-only: on the customer's portal page, set the agreed terms and
    accept a booking request."""

    class Meta:
        model = Job
        fields = ["agreed_price", "start_date", "summary",
                  "site_address", "contact_name", "contact_phone"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "summary": forms.Textarea(attrs={"rows": 3}),
            "site_address": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("agreed_price") is None:
            self.add_error("agreed_price", "Set the agreed price to confirm the booking.")
        if not cleaned.get("start_date"):
            self.add_error("start_date", "Set a start date to confirm the booking.")
        return cleaned


class RecordPaymentForm(forms.ModelForm):
    """Staff-only: log a payment the customer has made (cash / bank / card)."""

    class Meta:
        model = Payment
        fields = ["amount", "kind", "method", "received_on", "reference", "note"]
        widgets = {"received_on": forms.DateInput(attrs={"type": "date"})}

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount is None or amount <= 0:
            raise forms.ValidationError("Enter an amount greater than zero.")
        return amount


# Back to the AI quote flow: the follow-up questions page.
class FollowUpForm(forms.Form):
    """Built at runtime from the AI's follow-up questions."""

    def __init__(self, questions, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.questions = list(questions)
        for i, question in enumerate(self.questions):
            self.fields[f"q{i}"] = forms.CharField(
                label=question,
                widget=forms.Textarea(attrs={"rows": 2}),
                required=False,
            )

    def answers(self):
        return {
            self.questions[i]: self.cleaned_data.get(f"q{i}", "").strip()
            for i in range(len(self.questions))
        }
