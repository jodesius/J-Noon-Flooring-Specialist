from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_http_methods, require_POST

from .forms import LoginForm, ProfileForm, RegisterForm
from .models import Profile
from .tokens import email_verification_token

User = get_user_model()


def _send_verification_email(request, user):
    """Email `user` a signed link that verifies their email address."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    link = request.build_absolute_uri(
        reverse("accounts:verify_email", kwargs={"uidb64": uid, "token": token})
    )
    subject = render_to_string(
        "accounts/email_verification_subject.txt"
    ).strip()
    body = render_to_string(
        "accounts/email_verification.txt", {"user": user, "link": link}
    )
    send_mail(subject, body, None, [user.email], fail_silently=True)


def register_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            _send_verification_email(request, user)
            messages.success(
                request,
                "Account created. We've emailed you a link to verify your "
                "email address - you can log in now and verify any time.",
            )
            return redirect("accounts:login")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            next_url = request.POST.get("next") or request.GET.get("next")
            return redirect(next_url or "core:home")

        # Generic message (no user enumeration) and blank fields to retry.
        messages.error(request, "Username/email or password is incorrect.")
        return render(request, "accounts/login.html", {"form": LoginForm(request)})

    return render(request, "accounts/login.html", {"form": LoginForm(request)})


@require_http_methods(["GET", "POST"])
def logout_view(request):
    if request.method == "POST":
        logout(request)
        messages.success(request, "You have been logged out.")
        return redirect("core:home")

    return render(request, "accounts/logout.html")


@login_required
@require_POST
def send_verification_email(request):
    if request.user.email_verified:
        messages.info(request, "Your email address is already verified.")
    else:
        _send_verification_email(request, request.user)
        messages.success(
            request, "Verification email sent - check your inbox (and spam)."
        )
    return redirect("accounts:profile")


def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and email_verification_token.check_token(user, token):
        if not user.email_verified:
            user.email_verified = True
            user.save(update_fields=["email_verified"])
        messages.success(request, "Your email address is now verified.")
        if request.user.is_authenticated and request.user.pk == user.pk:
            return redirect("accounts:profile")
        return redirect("accounts:login")

    return render(request, "accounts/email_verification_invalid.html", status=400)


@login_required
def profile_view(request):
    # Always the logged-in user's own profile - never looked up by id.
    profile, _ = Profile.objects.get_or_create(user=request.user)

    # The page is read-only by default; ?edit=1 (or a failed save) shows the form.
    editing = request.GET.get("edit") == "1"

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            image_changed = "image" in form.changed_data
            form.save()
            if image_changed and profile.image:
                messages.success(request, "Upload complete.")
            else:
                messages.success(request, "Profile saved.")
            return redirect("accounts:profile")

        editing = True  # show the form again with its errors
        if form.errors.get("image"):
            messages.error(
                request,
                "Upload error - please use a PNG or JPEG and keep the file "
                "size under 1MB.",
            )
    else:
        form = ProfileForm(instance=profile)

    return render(
        request,
        "accounts/profile.html",
        {"form": form, "profile": profile, "editing": editing},
    )
