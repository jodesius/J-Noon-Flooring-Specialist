from django import forms

from .models import ContactEnquiry


class EnquiryForm(forms.ModelForm):
    """Contact us enquiry. Includes a honeypot field that real people never
    see; if it comes back filled in, the submission is treated as spam.
    """

    # Honeypot - hidden from people with CSS, tempting to bots.
    website = forms.CharField(
        required=False,
        label="Leave this field blank",
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )

    class Meta:
        model = ContactEnquiry
        fields = ["name", "email", "phone", "postcode", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel"}),
            "postcode": forms.TextInput(attrs={"autocomplete": "postal-code"}),
            "message": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Roughly what you're after, the rooms "
                    "involved, and anything else that helps.",
                }
            ),
        }
        labels = {
            "phone": "Phone (optional)",
            "postcode": "Postcode (optional)",
            "message": "Your message",
        }

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("This message could not be sent.")
        return ""

    def clean_name(self):
        return self.cleaned_data["name"].strip()

    def clean_message(self):
        return self.cleaned_data["message"].strip()
