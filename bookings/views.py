from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from .calendar_sync import CalendarUnavailable, create_call_event
from .forms import CallRequestForm, FollowUpForm, QuoteStartForm
from .models import CallRequest, QuoteRequest
from .quoting import QuotingUnavailable, generate_quote, quoting_available


def index(request):
    return render(
        request,
        "bookings/index.html",
        {"quoting_available": quoting_available()},
    )


def _profile_defaults(user):
    profile = getattr(user, "profile", None)
    phone = (profile.phone or "") if profile else ""
    return {
        "contact_name": user.get_username(), "contact_phone": phone,
        "name": user.get_username(), "phone": phone,
    }


def _over_limit(model, user, limit):
    since = timezone.now() - timedelta(days=1)
    return model.objects.filter(user=user, created_at__gte=since).count() >= limit


def _email_staff(request, subject_template, body_template, ctx):
    subject = render_to_string(subject_template, ctx).strip()
    body = render_to_string(body_template, ctx)
    EmailMessage(subject=subject, body=body, to=[settings.DEFAULT_FROM_EMAIL]).send(
        fail_silently=True
    )


def _notify_staff(request, qr):
    _email_staff(
        request, "bookings/quote_email_subject.txt", "bookings/quote_email.txt",
        {"qr": qr, "url": request.build_absolute_uri(
            f"/admin/bookings/quoterequest/{qr.pk}/change/"
        )},
    )


def _run_quoting(request, qr, final_round=False):
    try:
        result = generate_quote(qr, final_round=final_round)
    except QuotingUnavailable:
        qr.status = QuoteRequest.Status.CALL_REQUESTED
        qr.ai_result = {
            "customer_message": "Thanks - I'll give you a call to talk through the "
            "details and get you a quote.",
            "internal_note": "Automated quote unavailable; call the customer.",
        }
        qr.save()
        return

    qr.ai_result = result
    outcome = result["outcome"]

    if outcome == "need_info" and not final_round:
        qr.ai_questions = result["questions"]
        qr.status = QuoteRequest.Status.AWAITING_INFO
    elif outcome == "quote":
        qr.quote_low = result.get("quote_low")
        qr.quote_high = result.get("quote_high")
        qr.status = QuoteRequest.Status.QUOTED
    else:  # refer_to_call, or need_info on the final round
        qr.status = QuoteRequest.Status.CALL_REQUESTED
    qr.save()


@login_required
def quote(request):
    if not quoting_available():
        return render(request, "bookings/quote_unavailable.html")

    if request.method == "POST":
        if _over_limit(QuoteRequest, request.user, settings.QUOTE_DAILY_LIMIT):
            messages.error(
                request,
                "You've sent a few quote requests today already - please give me "
                "a chance to catch up, or call instead.",
            )
            return redirect("bookings:index")

        form = QuoteStartForm(request.POST)
        if form.is_valid():
            qr = form.save(commit=False)
            qr.user = request.user
            qr.save()
            _run_quoting(request, qr)
            _notify_staff(request, qr)
            return redirect("bookings:quote_detail", slug=qr.slug)
    else:
        form = QuoteStartForm(initial=_profile_defaults(request.user))

    return render(request, "bookings/quote.html", {"form": form})


@login_required
def call(request):
    if request.method == "POST":
        if _over_limit(CallRequest, request.user, settings.CALL_DAILY_LIMIT):
            messages.error(
                request,
                "You've already asked for a call-back today - I'll be in touch.",
            )
            return redirect("bookings:index")

        form = CallRequestForm(request.POST)
        if form.is_valid():
            call_request = form.save(commit=False)
            call_request.user = request.user
            call_request.save()

            try:
                call_request.calendar_event_id = create_call_event(call_request)
                call_request.save(update_fields=["calendar_event_id"])
            except CalendarUnavailable:
                pass  # saved + emailed below is enough

            _email_staff(
                request,
                "bookings/call_email_subject.txt", "bookings/call_email.txt",
                {"call": call_request, "url": request.build_absolute_uri(
                    f"/admin/bookings/callrequest/{call_request.pk}/change/"
                )},
            )
            messages.success(
                request,
                "Thanks - I've got your details and I'll call you around "
                f"{call_request.when_label} on {call_request.preferred_date:%A %d %B}.",
            )
            return redirect("bookings:index")
    else:
        form = CallRequestForm(initial=_profile_defaults(request.user))

    return render(request, "bookings/call.html", {"form": form})


@login_required
def quote_detail(request, slug):
    qr = get_object_or_404(QuoteRequest, slug=slug, user=request.user)

    if qr.status == QuoteRequest.Status.AWAITING_INFO:
        if request.method == "POST":
            form = FollowUpForm(qr.ai_questions, request.POST)
            if form.is_valid():
                qr.ai_answers = form.answers()
                qr.save(update_fields=["ai_answers"])
                _run_quoting(request, qr, final_round=True)
                return redirect("bookings:quote_detail", slug=qr.slug)
        else:
            form = FollowUpForm(qr.ai_questions)
        return render(
            request, "bookings/quote_followup.html", {"qr": qr, "form": form}
        )

    return render(request, "bookings/quote_result.html", {"qr": qr})
