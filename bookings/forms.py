from django import forms
from django.utils import timezone

from .models import CallRequest, FlooringRate, QuoteRequest


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


import datetime as _dt


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
