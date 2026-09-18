from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import ContactEnquiry, SiteContact

LOCMEM_MAIL = override_settings(
    MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
)


def valid_payload(**extra):
    data = {
        "name": "Sam Client",
        "email": "sam@example.com",
        "phone": "07000 000000",
        "postcode": "CM1 1AA",
        "message": "Please could you quote for laminate in two bedrooms.",
        "website": "",  # honeypot left empty
    }
    data.update(extra)
    return data


class ContactPageTests(TestCase):
    def test_page_renders(self):
        resp = self.client.get(reverse("contact:index"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "contact/index.html")
        self.assertContains(resp, "Contact us")
        self.assertContains(resp, "coverage-map")
        self.assertContains(resp, "contact-map-card__logo")

    @override_settings(GEOAPIFY_API_KEY="")
    def test_map_has_no_tile_key_when_unconfigured(self):
        resp = self.client.get(reverse("contact:index"))
        self.assertContains(resp, 'data-tile-key=""')

    @override_settings(GEOAPIFY_API_KEY="test-geoapify-key")
    def test_map_carries_the_configured_tile_key(self):
        resp = self.client.get(reverse("contact:index"))
        self.assertContains(resp, 'data-tile-key="test-geoapify-key"')


class SiteContactModelTests(TestCase):
    def test_load_always_returns_the_single_row(self):
        a = SiteContact.load()
        a.phone = "01245 000000"
        a.save()
        b = SiteContact.load()
        self.assertEqual(b.pk, 1)
        self.assertEqual(SiteContact.objects.count(), 1)
        self.assertEqual(b.phone, "01245 000000")

    def test_enquiry_email_falls_back_to_the_main_email(self):
        c = SiteContact.load()
        c.email = "main@example.com"
        c.save()
        self.assertEqual(c.enquiry_email, "main@example.com")
        c.enquiry_recipient = "leads@example.com"
        self.assertEqual(c.enquiry_email, "leads@example.com")

    def test_photo_url_uses_a_placeholder_when_empty(self):
        self.assertIn("placehold", SiteContact.load().photo_url)


class AvailabilityOnContactPageTests(TestCase):
    """The "Availability" line on Contact us - computed automatically from
    booked Job rows (bookings.models.Job.next_available_date), not set by
    hand. See bookings/tests.py for the computation itself; this just
    checks the Contact page actually shows it."""

    def test_shows_available_now_with_nothing_booked(self):
        resp = self.client.get(reverse("contact:index"))
        self.assertContains(resp, "Available now")

    def test_shows_next_available_once_a_job_is_booked(self):
        from django.contrib.auth import get_user_model

        from bookings.models import Job

        User = get_user_model()
        user = User.objects.create_user(
            username="cust", email="cust@example.com", password="pw1!pass"
        )
        start = timezone.localdate() + timedelta(days=5)
        Job.objects.create(
            user=user, title="Hall LVT", status=Job.Status.NOT_STARTED,
            agreed_price=500, start_date=start,
        )
        resp = self.client.get(reverse("contact:index"))
        self.assertNotContains(resp, "Available now")
        self.assertContains(resp, "Next available")
        self.assertContains(resp, (start + timedelta(days=3)).strftime("%Y"))


@LOCMEM_MAIL
class EnquiryFormSubmissionTests(TestCase):
    def setUp(self):
        cache.clear()  # each test starts with a clean submission-throttle slate
        c = SiteContact.load()
        c.email = "joseph@example.com"
        c.save()

    def test_valid_enquiry_is_saved_and_emailed(self):
        resp = self.client.post(reverse("contact:index"), valid_payload())

        self.assertRedirects(resp, reverse("contact:index"))
        enquiry = ContactEnquiry.objects.get()
        self.assertEqual(enquiry.name, "Sam Client")
        self.assertFalse(enquiry.handled)

        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["joseph@example.com"])
        self.assertEqual(msg.reply_to, ["sam@example.com"])
        self.assertIn("laminate in two bedrooms", msg.body)

    def test_honeypot_blocks_spam(self):
        resp = self.client.post(
            reverse("contact:index"), valid_payload(website="http://spam.example")
        )

        self.assertEqual(resp.status_code, 200)  # re-rendered, not redirected
        self.assertEqual(ContactEnquiry.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_name_email_and_message_are_required(self):
        resp = self.client.post(
            reverse("contact:index"),
            {"name": "", "email": "", "message": "", "website": ""},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ContactEnquiry.objects.count(), 0)
        self.assertContains(resp, "This field is required.")

    def test_missing_recipient_still_saves_the_enquiry(self):
        c = SiteContact.load()
        c.email = ""
        c.enquiry_recipient = ""
        c.save()

        resp = self.client.post(reverse("contact:index"), valid_payload())

        self.assertRedirects(resp, reverse("contact:index"))
        self.assertEqual(ContactEnquiry.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)


@LOCMEM_MAIL
class EnquiryThrottleTests(TestCase):
    """A scripted client can leave the honeypot blank, so it alone doesn't
    stop a flood of submissions - found missing (no rate limiting at all)
    during the pre-deploy security review."""

    def setUp(self):
        cache.clear()

    def test_blocks_after_max_submissions_per_window(self):
        for i in range(5):
            resp = self.client.post(
                reverse("contact:index"), valid_payload(email=f"sam{i}@example.com")
            )
            self.assertRedirects(resp, reverse("contact:index"))

        resp = self.client.post(
            reverse("contact:index"), valid_payload(email="sam-over-limit@example.com"),
            follow=True,
        )
        self.assertContains(resp, "sent a few messages already")
        self.assertEqual(ContactEnquiry.objects.count(), 5)

    def test_different_ip_is_not_affected(self):
        for i in range(5):
            self.client.post(
                reverse("contact:index"), valid_payload(email=f"sam{i}@example.com")
            )

        resp = self.client.post(
            reverse("contact:index"), valid_payload(email="other-ip@example.com"),
            REMOTE_ADDR="10.0.0.5",
        )
        self.assertRedirects(resp, reverse("contact:index"))
        self.assertEqual(ContactEnquiry.objects.count(), 6)
