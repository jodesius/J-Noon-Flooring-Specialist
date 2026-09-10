from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

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


@LOCMEM_MAIL
class EnquiryFormSubmissionTests(TestCase):
    def setUp(self):
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
