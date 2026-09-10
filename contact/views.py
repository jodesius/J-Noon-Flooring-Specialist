from django.contrib import messages
from django.core.mail import EmailMessage
from django.shortcuts import redirect, render
from django.template.loader import render_to_string

from .forms import EnquiryForm
from .models import SiteContact


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

    return render(
        request,
        "contact/index.html",
        {"contact": contact, "form": form},
    )
