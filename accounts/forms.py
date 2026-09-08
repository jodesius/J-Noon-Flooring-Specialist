from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator

from .models import Profile

User = get_user_model()


class RegisterForm(forms.ModelForm):
    """Create a new account. Email, username and both password fields are
    required, and the two passwords must match.
    """

    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=(
            "6 to 12 characters, with at least one number and one special "
            "character."
        ),
    )
    password_confirm = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ["email", "username", "password"]
        widgets = {
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "username": forms.TextInput(attrs={"autocomplete": "username"}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if username and User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is already taken.")
        return username

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirm = cleaned.get("password_confirm")

        if password and confirm and password != confirm:
            self.add_error("password_confirm", "The two passwords do not match.")

        if password:
            stub = User(
                username=cleaned.get("username") or "",
                email=cleaned.get("email") or "",
            )
            try:
                validate_password(password, stub)
            except forms.ValidationError as exc:
                self.add_error("password", exc)

        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """Login form - the "username" field also accepts an email address."""

    username = forms.CharField(
        label="Email or username",
        widget=forms.TextInput(
            attrs={"autofocus": True, "autocomplete": "username"}
        ),
    )


class ProfileForm(forms.ModelForm):
    """The user's own profile. Always bound to request.user - no identifier
    is ever taken from the request.
    """

    username = forms.CharField(
        label="Username",
        max_length=150,
        validators=[UnicodeUsernameValidator()],
        help_text="Letters, digits and @ . + - _ only.",
    )

    class Meta:
        model = Profile
        fields = [
            "image",
            "pronouns",
            "phone",
            "contact_email",
            "about",
            "facebook",
            "instagram",
            "linkedin",
            "website",
        ]
        widgets = {
            "about": forms.Textarea(attrs={"rows": 5}),
            "pronouns": forms.TextInput(attrs={"placeholder": "e.g. she/her"}),
            # Plain file input - no "Currently / Clear" checkbox. To change the
            # picture the user just uploads a new one, which replaces the old.
            "image": forms.FileInput(attrs={"accept": "image/png,image/jpeg"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].initial = self.instance.user.username

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        clash = (
            User.objects.filter(username__iexact=username)
            .exclude(pk=self.instance.user_id)
            .exists()
        )
        if clash:
            raise forms.ValidationError("That username is already taken.")
        return username

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.user.username = self.cleaned_data["username"]
        if commit:
            profile.user.save(update_fields=["username"])
            profile.save()
        return profile
