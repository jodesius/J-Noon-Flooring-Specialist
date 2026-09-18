from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import (
    url_has_allowed_host_and_scheme, urlsafe_base64_decode, urlsafe_base64_encode,
)
from django.views.decorators.http import require_http_methods, require_POST

from core.utils import client_ip

from .forms import LoginForm, ProfileForm, RegisterForm
from .models import Profile
from .tokens import email_verification_token

User = get_user_model()

# Login brute-force protection: after this many failed attempts against
# either the same account or the same IP within the window, further
# attempts are refused for the rest of the window. Keyed on both so an
# attacker can't dodge the lockout by spraying many accounts from one IP,
# or hammering one account from many IPs.
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60


def _login_throttle_keys(request, username):
    keys = [f"login_fail:ip:{client_ip(request)}"]
    username = (username or "").strip().lower()
    if username:
        keys.append(f"login_fail:user:{username}")
    return keys


def _login_is_locked(request, username):
    return any(
        cache.get(key, 0) >= LOGIN_MAX_ATTEMPTS
        for key in _login_throttle_keys(request, username)
    )


def _login_register_failure(request, username):
    for key in _login_throttle_keys(request, username):
        cache.add(key, 0, LOGIN_LOCKOUT_SECONDS)
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, LOGIN_LOCKOUT_SECONDS)


def _login_clear_failures(request, username):
    for key in _login_throttle_keys(request, username):
        cache.delete(key)


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
            user.backend = "django.contrib.auth.backends.ModelBackend"
            login(request, user)
            messages.success(
                request,
                "Account created - you're logged in. We've emailed you a "
                "link to verify your email address - you can do that any "
                "time from your profile.",
            )
            return redirect("core:home")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


def _safe_next_url(request, next_url):
    """Only follow `next` if it points back at this site - an unchecked
    redirect target is an open-redirect / phishing vector (attacker sends a
    login link with next=https://evil.example, victim logs in for real, then
    lands on the attacker's page)."""
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return None


def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    if request.method == "POST":
        username = request.POST.get("username", "")

        if _login_is_locked(request, username):
            messages.error(
                request,
                "Too many failed attempts - please wait 15 minutes and try again.",
            )
            return render(request, "accounts/login.html", {"form": LoginForm(request)})

        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            _login_clear_failures(request, username)
            login(request, form.get_user())
            next_url = request.POST.get("next") or request.GET.get("next")
            return redirect(_safe_next_url(request, next_url) or "core:home")

        _login_register_failure(request, username)
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
    """GET just checks the link and shows a "confirm" button - it never
    changes anything by itself, so an email client or security scanner
    silently prefetching the link can't burn through it before the
    person actually gets there. Only a POST (a real click on that
    button) actually verifies the address."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None or not email_verification_token.check_token(user, token):
        return render(request, "accounts/email_verification_invalid.html", status=400)

    if request.method == "POST":
        if not user.email_verified:
            user.email_verified = True
            user.save(update_fields=["email_verified"])
        messages.success(request, "Your email address is now verified.")
        if request.user.is_authenticated and request.user.pk == user.pk:
            return redirect("accounts:profile")
        return redirect("accounts:login")

    return render(request, "accounts/email_verification_confirm.html", {
        "uidb64": uidb64, "token": token,
    })


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
