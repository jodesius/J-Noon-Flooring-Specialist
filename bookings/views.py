from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from .calendar_sync import CalendarUnavailable, create_call_event
from .forms import (
    BookJobForm, CallRequestForm, ConfirmBookingForm, FollowUpForm,
    QuoteStartForm, RecordPaymentForm,
)
from .invoices import render_invoice_pdf
from .models import CallRequest, Invoice, Job, Payment, QuoteRequest
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


def _booking_initial(request):
    """Prefill the booking form from ?quote=<reference> when it points at one
    of this customer's own quotes."""
    ref = request.GET.get("quote", "").strip()
    if not ref:
        return {}
    quote = QuoteRequest.objects.filter(
        reference__iexact=ref, user=request.user
    ).first()
    if quote is None:
        return {}
    return {
        "quote_reference": quote.reference,
        "title": quote.suggested_job_title,
        "contact_name": quote.contact_name,
        "contact_phone": quote.contact_phone,
        "site_address": quote.postcode,
    }


@login_required
def book(request):
    """Customer asks to book a job. Joseph confirms the price + date after."""
    if request.method == "POST":
        if _over_limit(Job, request.user, settings.JOB_REQUEST_DAILY_LIMIT):
            messages.error(
                request,
                "You've already sent a booking request today - I'll be in touch to "
                "confirm it. Give me a call if it's urgent.",
            )
            return redirect("bookings:projects")

        form = BookJobForm(request.POST, user=request.user)
        if form.is_valid():
            job = form.save(commit=False)
            job.user = request.user
            job.status = Job.Status.REQUESTED
            job.quote_request = form.matched_quote
            job.save()

            ctx = {
                "job": job,
                "url": request.build_absolute_uri(
                    f"/admin/bookings/job/{job.pk}/change/"
                ),
            }
            if job.quote_request:
                ctx["quote_url"] = request.build_absolute_uri(
                    f"/admin/bookings/quoterequest/{job.quote_request.pk}/change/"
                )
            _email_staff(
                request,
                "bookings/job_email_subject.txt", "bookings/job_email.txt", ctx,
            )
            messages.success(
                request,
                "Thanks - I've got your booking request. I'll confirm the price and a "
                "start date with you, then you'll be able to secure it in your projects.",
            )
            return redirect("bookings:projects")
    else:
        form = BookJobForm(user=request.user, initial=_booking_initial(request))

    return render(request, "bookings/book.html", {"form": form})


def _get_owned_job(request, slug):
    """The job at `slug` - for its owner, or for staff organising it."""
    job = get_object_or_404(
        Job.objects.select_related(
            "user", "quote_request", "quote_request__flooring_system"
        ),
        slug=slug,
    )
    if job.user_id != request.user.id and not request.user.is_site_admin:
        raise Http404
    return job


@login_required
def projects(request):
    jobs = Job.objects.filter(user=request.user)
    return render(request, "bookings/projects.html", {"jobs": jobs})


@login_required
def manage(request):
    """Staff dashboard: every booking, filterable by status."""
    if not request.user.is_site_admin:
        raise Http404

    status = request.GET.get("status", "")
    jobs = Job.objects.select_related("user")
    if status:
        jobs = jobs.filter(status=status)

    groups = [
        (value, label, Job.objects.filter(status=value).count())
        for value, label in Job.Status.choices
    ]
    return render(
        request,
        "bookings/manage.html",
        {
            "jobs": jobs,
            "status": status,
            "groups": groups,
            "total": Job.objects.count(),
            "needs_action": Job.objects.filter(
                status__in=[Job.Status.REQUESTED, Job.Status.AWAITING_DEPOSIT]
            ).count(),
        },
    )


def _handle_job_action(request, job):
    """Staff actions taken from the customer's portal page."""
    action = request.POST.get("action", "")
    who = job.contact_name or job.user.get_username()

    if action == "confirm":
        form = ConfirmBookingForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            job.status = Job.Status.AWAITING_DEPOSIT
            job.confirmed_at = timezone.now()
            job.save(update_fields=["status", "confirmed_at", "updated_at"])
            messages.success(
                request,
                f"Booking accepted. {who} can now pay the "
                f"£{job.booking_fee:.2f} booking fee (20% of £{job.agreed_price:.2f}).",
            )
        else:
            messages.error(
                request, "Set an agreed price and a start date to accept the booking."
            )
        return

    if action == "record_fee":
        method = request.POST.get("method") or Payment.Method.BANK
        Payment.objects.create(
            job=job, amount=job.booking_fee,
            kind=Payment.Kind.BOOKING_FEE, method=method,
        )  # Payment.save() moves the job on to "Booked - not started"
        messages.success(
            request, f"£{job.booking_fee:.2f} booking fee recorded - the job is booked in."
        )
        return

    if action == "record_payment":
        form = RecordPaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.job = job
            payment.save()
            messages.success(request, f"£{payment.amount:.2f} payment recorded.")
        else:
            messages.error(request, "Enter a valid payment amount.")
        return

    if action == "start":
        job.status = Job.Status.UNDERWAY
        job.save(update_fields=["status", "updated_at"])
        messages.success(request, "Job marked as underway.")
        return

    if action == "complete":
        job.status = Job.Status.COMPLETE
        job.save(update_fields=["status", "updated_at"])
        messages.success(request, "Job marked as complete.")
        return

    if action == "reopen":
        job.status = Job.Status.UNDERWAY
        job.save(update_fields=["status", "updated_at"])
        messages.success(request, "Job reopened.")
        return

    if action in ("issue_deposit", "issue_final"):
        kind = (
            Invoice.Kind.DEPOSIT if action == "issue_deposit" else Invoice.Kind.FINAL
        )
        invoice = Invoice(job=job, kind=kind)
        invoice.snapshot_from_job()
        invoice.save()
        invoice.ensure_default_line_item()
        messages.success(
            request, f"{invoice.get_kind_display()} {invoice.number} created "
            "- add or split the line items in the admin if you want.",
        )
        return

    if action == "cancel":
        job.status = Job.Status.CANCELLED
        job.save(update_fields=["status", "updated_at"])
        messages.success(request, "Booking cancelled.")
        return

    messages.error(request, "Unknown action.")


@login_required
def project_detail(request, slug):
    job = _get_owned_job(request, slug)
    can_manage = request.user.is_site_admin

    if request.method == "POST":
        if not can_manage:
            raise Http404
        _handle_job_action(request, job)
        return redirect("bookings:project_detail", slug=job.slug)

    return render(
        request,
        "bookings/project_detail.html",
        {
            "job": job,
            "photos": job.photos.all(),
            "payments": job.payments.all(),
            "invoices": job.invoices.all(),
            "can_manage": can_manage,
            "viewing_as_staff": can_manage and job.user_id != request.user.id,
            "confirm_form": ConfirmBookingForm(instance=job) if can_manage else None,
            "payment_form": RecordPaymentForm() if can_manage else None,
            "admin_url": f"/admin/bookings/job/{job.pk}/change/" if can_manage else None,
        },
    )


@login_required
def invoice_pdf(request, slug, number):
    job = _get_owned_job(request, slug)
    invoice = get_object_or_404(Invoice, job=job, number=number)
    pdf = render_invoice_pdf(invoice)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{invoice.number}.pdf"'
    return resp


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
