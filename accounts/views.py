from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import LoginForm, ProfileForm, RegisterForm
from .models import Profile


def register_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created - you can now log in.")
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
def profile_view(request):
    # Always the logged-in user's own profile - never looked up by id.
    profile, _ = Profile.objects.get_or_create(user=request.user)

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

        if form.errors.get("image"):
            messages.error(
                request,
                "Upload error - please use a PNG or JPEG and keep the file "
                "size under 1MB.",
            )
    else:
        form = ProfileForm(instance=profile)

    return render(request, "accounts/profile.html", {"form": form, "profile": profile})
