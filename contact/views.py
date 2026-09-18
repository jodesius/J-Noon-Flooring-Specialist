from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.shortcuts import redirect, render
from django.template.loader import render_to_string

from core.utils import client_ip

from .forms import EnquiryForm
from .models import SiteContact

# Throttle: the honeypot only stops naive bots, not a scripted attacker who
# simply leaves it blank. This caps how many enquiries one IP can submit
# per window - generous enough for a genuine customer resubmitting after a
# mistake, tight enough to stop a spam/flood script.
ENQUIRY_MAX_PER_WINDOW = 5
ENQUIRY_WINDOW_SECONDS = 60 * 60


def _enquiry_rate_limited(request):
    key = f"enquiry_submit:ip:{client_ip(request)}"
    cache.add(key, 0, ENQUIRY_WINDOW_SECONDS)
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, ENQUIRY_WINDOW_SECONDS)
        count = 1
    return count > ENQUIRY_MAX_PER_WINDOW


def _send_enquiry_email(enquiry, contact):
    """Email the business a new enquiry. Failures are swallowed - the
    enquiry is already saved in the database.
    """
    recipient = contact.enquiry_email
    if not recipient:
        return

    subject = render_to_string(
        "contact/enquiry_email_subject.txt", {"enquiry": enquiry}
    ).strip()
    body = render_to_string("contact/enquiry_email.txt", {"enquiry": enquiry})

    EmailMessage(
        subject=subject,
        body=body,
        to=[recipient],
        reply_to=[enquiry.email],
    ).send(fail_silently=True)


def index(request):
    contact = SiteContact.load()

    if request.method == "POST":
        if _enquiry_rate_limited(request):
            messages.error(
                request,
                "You've sent a few messages already - please give me a "
                "chance to catch up, or call instead.",
            )
            return redirect("contact:index")

        form = EnquiryForm(request.POST)
        if form.is_valid():
            enquiry = form.save()
            _send_enquiry_email(enquiry, contact)
            messages.success(
                request,
                "Thanks - your message has been sent. I'll get back to you "
                "as soon as I can.",
            )
            return redirect("contact:index")
    else:
        form = EnquiryForm()

    from bookings.models import Job

    return render(
        request,
        "contact/index.html",
        {
            "contact": contact,
            "form": form,
            "geoapify_key": settings.GEOAPIFY_API_KEY,
            "next_available": Job.next_available_date(),
        },
    )
