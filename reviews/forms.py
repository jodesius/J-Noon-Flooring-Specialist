from django import forms

from .models import Review


class ReviewForm(forms.ModelForm):
    """Post or edit a review postcard. Bound to the logged-in author in the
    view - the form never accepts an author or an id from the request.
    """

    class Meta:
        model = Review
        fields = ["rating", "headline", "body", "image"]
        widgets = {
            "rating": forms.Select(),
            "headline": forms.TextInput(
                attrs={"placeholder": "e.g. Beautiful new laminate floor"}
            ),
            "body": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": "Tell others about the work and how it went.",
                }
            ),
            # Plain file input - no "Currently / Clear" checkbox.
            "image": forms.FileInput(
                attrs={"accept": "image/png,image/jpeg,image/webp"}
            ),
        }
        labels = {
            "rating": "Your rating",
            "headline": "Headline",
            "body": "Your review",
            "image": "Photo of the work (optional)",
        }

    def clean_headline(self):
        return self.cleaned_data["headline"].strip()

    def clean_body(self):
        return self.cleaned_data["body"].strip()
