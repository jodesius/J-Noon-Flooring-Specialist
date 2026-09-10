from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .calendar_sync import CalendarUnavailable
from .models import (
    CallRequest, CardPayment, FlooringRate, Invoice, InvoiceLineItem, Job,
    JobPhoto, Payment, QuoteRequest, QuoteSettings,
)
from .quoting import (
    QuotingUnavailable, _preview_response, _sanitise, quoting_available,
)

User = get_user_model()

LOCMEM = override_settings(
    MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
)

IN_MEMORY_STORAGE = override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)


def tiny_png(name="work.png"):
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (4, 3), "sienna").save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/png")


def make_user(username="cust"):
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", password="pw1!pass"
    )


def clear_rate_card():
    s = QuoteSettings.load()
    s.rate_card = ""
    s.save()


def base_payload(**extra):
    data = {
        "service_option": QuoteRequest.Service.SUPPLY_FIT,
        "flooring_note": "laminate, something hard-wearing",
        "area_sqm": "22",
        "rooms": "living room",
        "current_covering": "old carpet",
        "subfloor_type": QuoteRequest.Subfloor.CONCRETE,
        "subfloor_condition": QuoteRequest.Condition.SOUND,
        "removal_needed": QuoteRequest.Removal.YES,
        "timescale": QuoteRequest.Timescale.SOON,
        "postcode": "CM1 1AA",
        "details": "",
        "contact_name": "Sam Buyer",
        "contact_phone": "07000 000000",
        "website": "",
    }
    data.update(extra)
    return data


class LandingTests(TestCase):
    def test_landing_renders_for_anon(self):
        resp = self.client.get(reverse("bookings:index"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Sign in to get started")

    def test_landing_renders_for_user(self):
        self.client.force_login(make_user())
        resp = self.client.get(reverse("bookings:index"))
        self.assertContains(resp, "Start a quote")


class QuoteGateTests(TestCase):
    def test_login_required(self):
        resp = self.client.get(reverse("bookings:quote"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts:login"), resp["Location"])

    @override_settings(ANTHROPIC_API_KEY="", QUOTING_PREVIEW=False)
    def test_no_key_shows_unavailable(self):
        self.client.force_login(make_user())
        resp = self.client.get(reverse("bookings:quote"))
        self.assertTemplateUsed(resp, "bookings/quote_unavailable.html")

    @override_settings(ANTHROPIC_API_KEY="k", QUOTING_PREVIEW=False)
    def test_empty_rate_card_shows_unavailable(self):
        clear_rate_card()
        self.client.force_login(make_user())
        resp = self.client.get(reverse("bookings:quote"))
        self.assertTemplateUsed(resp, "bookings/quote_unavailable.html")

    @override_settings(ANTHROPIC_API_KEY="k", QUOTING_PREVIEW=False)
    def test_master_switch_off_shows_unavailable(self):
        s = QuoteSettings.load()
        s.online_quotes_enabled = False
        s.save()
        self.client.force_login(make_user())
        resp = self.client.get(reverse("bookings:quote"))
        self.assertTemplateUsed(resp, "bookings/quote_unavailable.html")


@LOCMEM
@override_settings(ANTHROPIC_API_KEY="test-key", QUOTING_PREVIEW=False)
class QuoteFlowTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def _post(self, **extra):
        return self.client.post(reverse("bookings:quote"), base_payload(**extra))

    def test_quote_form_has_please_wait_overlay(self):
        resp = self.client.get(reverse("bookings:quote"))
        self.assertContains(resp, 'id="bk-loading"')
        self.assertContains(resp, "quote-loading.js")
        self.assertContains(resp, "Your quote is being calculated")

    @patch("bookings.views.generate_quote")
    def test_valid_submission_creates_request_and_emails(self, mock_gen):
        mock_gen.return_value = {
            "outcome": "quote", "quote_low": 700, "quote_high": 950,
            "breakdown": [], "assumptions": ["1 room"], "questions": [],
            "customer_message": "Rough guide only.", "internal_note": "ok",
        }
        resp = self._post()

        qr = QuoteRequest.objects.get()
        self.assertRedirects(resp, reverse("bookings:quote_detail", kwargs={"slug": qr.slug}))
        self.assertEqual(qr.user, self.user)
        self.assertEqual(qr.status, QuoteRequest.Status.QUOTED)
        self.assertEqual(qr.quote_low, 700)
        self.assertEqual(len(mail.outbox), 1)

        page = self.client.get(resp["Location"])
        self.assertContains(page, "700")
        self.assertContains(page, "rough estimate")

    @patch("bookings.views.generate_quote")
    def test_need_info_then_followup_to_quote(self, mock_gen):
        mock_gen.side_effect = [
            {"outcome": "need_info", "questions": ["How many rooms exactly?"],
             "breakdown": [], "assumptions": [], "customer_message": "Need more.",
             "internal_note": ""},
            {"outcome": "quote", "quote_low": 800, "quote_high": 1100,
             "questions": [], "breakdown": [], "assumptions": [],
             "customer_message": "Here you go.", "internal_note": ""},
        ]
        resp = self._post()
        qr = QuoteRequest.objects.get()
        self.assertEqual(qr.status, QuoteRequest.Status.AWAITING_INFO)

        follow = self.client.get(resp["Location"])
        self.assertContains(follow, "How many rooms exactly?")
        self.assertContains(follow, "quote-loading.js")  # "please wait" overlay

        self.client.post(resp["Location"], {"q0": "three bedrooms"})
        qr.refresh_from_db()
        self.assertEqual(qr.status, QuoteRequest.Status.QUOTED)
        self.assertEqual(qr.ai_answers, {"How many rooms exactly?": "three bedrooms"})

    @patch("bookings.views.generate_quote", side_effect=QuotingUnavailable("boom"))
    def test_quoting_unavailable_falls_back_to_call(self, _mock):
        resp = self._post()
        qr = QuoteRequest.objects.get()
        self.assertEqual(qr.status, QuoteRequest.Status.CALL_REQUESTED)
        page = self.client.get(resp["Location"])
        self.assertContains(page, "give you a call")

    @patch("bookings.views.generate_quote")
    def test_honeypot_blocks(self, mock_gen):
        resp = self._post(website="http://spam.example")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(QuoteRequest.objects.count(), 0)
        mock_gen.assert_not_called()

    @patch("bookings.views.generate_quote")
    def test_area_or_unknown_required(self, _mock):
        payload = base_payload()
        payload.pop("area_sqm")
        resp = self.client.post(reverse("bookings:quote"), payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(QuoteRequest.objects.count(), 0)

    @patch("bookings.views.generate_quote", return_value={
        "outcome": "quote", "quote_low": 100, "quote_high": 200, "questions": [],
        "breakdown": [], "assumptions": [], "customer_message": "x", "internal_note": "",
    })
    @override_settings(QUOTE_DAILY_LIMIT=2)
    def test_daily_limit(self, _mock):
        self._post()
        self._post()
        resp = self._post()
        self.assertRedirects(resp, reverse("bookings:index"))
        self.assertEqual(QuoteRequest.objects.count(), 2)

    def test_cannot_view_another_users_request(self):
        other = QuoteRequest.objects.create(
            user=make_user("other"), service_option=QuoteRequest.Service.SUPPLY_FIT,
            postcode="CM2 2BB", contact_name="Other",
        )
        resp = self.client.get(
            reverse("bookings:quote_detail", kwargs={"slug": other.slug})
        )
        self.assertEqual(resp.status_code, 404)


class SanitiseTests(TestCase):
    def _qr(self, **extra):
        kw = dict(
            service_option=QuoteRequest.Service.SUPPLY_FIT,
            area_sqm=Decimal("20"), postcode="CM1 1AA", contact_name="X",
        )
        kw.update(extra)
        return QuoteRequest(**kw)

    def _quote(self, low, high):
        return {"outcome": "quote", "quote_low": low, "quote_high": high,
                "questions": [], "breakdown": [], "assumptions": [],
                "customer_message": "", "internal_note": ""}

    def test_sensible_quote_passes(self):
        out = _sanitise(self._quote(500, 700), self._qr())
        self.assertEqual(out["outcome"], "quote")
        self.assertEqual((out["quote_low"], out["quote_high"]), (500, 700))

    def test_far_too_cheap_referred_to_call(self):
        # 20 m² job priced at £30 total is nonsense
        out = _sanitise(self._quote(20, 30), self._qr())
        self.assertEqual(out["outcome"], "refer_to_call")

    def test_missing_numbers_referred_to_call(self):
        out = _sanitise(self._quote(None, None), self._qr())
        self.assertEqual(out["outcome"], "refer_to_call")

    def test_low_high_swapped_is_corrected(self):
        out = _sanitise(self._quote(700, 500), self._qr())
        self.assertEqual((out["quote_low"], out["quote_high"]), (500, 700))

    def test_no_area_skips_the_per_sqm_check(self):
        out = _sanitise(self._quote(300, 400), self._qr(area_sqm=None, area_unknown=True))
        self.assertEqual(out["outcome"], "quote")


class PreviewQuoteTests(TestCase):
    def _qr(self, **extra):
        kw = dict(
            service_option=QuoteRequest.Service.SUPPLY_FIT,
            area_sqm=Decimal("20"), postcode="CM1 1AA", contact_name="X",
            subfloor_condition=QuoteRequest.Condition.SOUND,
            removal_needed=QuoteRequest.Removal.NO,
        )
        kw.update(extra)
        return QuoteRequest(**kw)

    def test_no_removal_no_lifting_charge(self):
        out = _preview_response(self._qr(), final_round=True)
        self.assertEqual(out["outcome"], "quote")
        self.assertNotIn(
            "Lifting the old flooring", [b["label"] for b in out["breakdown"]]
        )
        self.assertNotIn("skip or bins", out["customer_message"])

    def test_removal_adds_50_flat_and_a_bins_note(self):
        base = _preview_response(self._qr(), final_round=True)
        out = _preview_response(
            self._qr(removal_needed=QuoteRequest.Removal.YES), final_round=True
        )
        self.assertEqual(out["quote_low"] - base["quote_low"], 50)
        self.assertEqual(out["quote_high"] - base["quote_high"], 50)
        self.assertIn(
            {"label": "Lifting the old flooring", "low": 50, "high": 50},
            out["breakdown"],
        )
        self.assertIn("skip or bins", out["customer_message"])


@LOCMEM
class CallRequestTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def _payload(self, **extra):
        data = {
            "name": "Jo Caller",
            "phone": "07111 222333",
            "preferred_date": (timezone.localdate() + timezone.timedelta(days=2)).isoformat(),
            "preferred_time": "14:30",
            "message": "",
            "website": "",
        }
        data.update(extra)
        return data

    def test_login_required(self):
        self.client.logout()
        resp = self.client.get(reverse("bookings:call"))
        self.assertEqual(resp.status_code, 302)

    @patch("bookings.views.create_call_event", return_value="evt-123")
    def test_booking_saves_creates_event_and_emails(self, mock_event):
        resp = self.client.post(reverse("bookings:call"), self._payload())

        self.assertRedirects(resp, reverse("bookings:index"))
        cr = CallRequest.objects.get()
        self.assertEqual(cr.user, self.user)
        self.assertEqual(cr.calendar_event_id, "evt-123")
        mock_event.assert_called_once()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("07111 222333", mail.outbox[0].body)

    @patch("bookings.views.create_call_event", side_effect=CalendarUnavailable("x"))
    def test_booking_still_works_without_calendar(self, _mock):
        resp = self.client.post(reverse("bookings:call"), self._payload())
        self.assertRedirects(resp, reverse("bookings:index"))
        cr = CallRequest.objects.get()
        self.assertEqual(cr.calendar_event_id, "")
        self.assertEqual(len(mail.outbox), 1)

    @patch("bookings.views.create_call_event", return_value="")
    def test_past_date_rejected(self, _mock):
        resp = self.client.post(
            reverse("bookings:call"),
            self._payload(preferred_date=(timezone.localdate() - timezone.timedelta(days=1)).isoformat()),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(CallRequest.objects.count(), 0)

    @patch("bookings.views.create_call_event", return_value="")
    def test_honeypot_blocks(self, mock_event):
        resp = self.client.post(
            reverse("bookings:call"), self._payload(website="http://spam")
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(CallRequest.objects.count(), 0)
        mock_event.assert_not_called()

    @patch("bookings.views.create_call_event", return_value="")
    @override_settings(CALL_DAILY_LIMIT=1)
    def test_daily_limit(self, _mock):
        self.client.post(reverse("bookings:call"), self._payload())
        resp = self.client.post(reverse("bookings:call"), self._payload())
        self.assertRedirects(resp, reverse("bookings:index"))
        self.assertEqual(CallRequest.objects.count(), 1)

    def test_landing_shows_book_a_call(self):
        resp = self.client.get(reverse("bookings:index"))
        self.assertContains(resp, reverse("bookings:call"))


class CallWindowTests(TestCase):
    def test_window_is_a_slot_at_the_chosen_time(self):
        import datetime as dt
        cr = CallRequest(
            preferred_date=dt.date(2026, 9, 15), preferred_time=dt.time(14, 30)
        )
        start, end = cr.window()
        self.assertEqual(start, dt.datetime(2026, 9, 15, 14, 30))
        self.assertEqual(end, dt.datetime(2026, 9, 15, 15, 0))

    def test_when_label(self):
        import datetime as dt
        self.assertEqual(CallRequest(preferred_time=dt.time(9, 0)).when_label, "9:00 am")
        self.assertEqual(CallRequest(preferred_time=dt.time(14, 30)).when_label, "2:30 pm")
        self.assertEqual(CallRequest(preferred_time=dt.time(12, 0)).when_label, "12:00 pm")


@LOCMEM
class BookJobTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def _payload(self, **extra):
        data = {
            "quote_reference": "",
            "title": "LVT to kitchen",
            "site_address": "1 Test Street, Chelmsford, CM1 1AA",
            "contact_name": "Sam Buyer",
            "contact_phone": "07000 000000",
            "customer_note": "",
            "website": "",
        }
        data.update(extra)
        return data

    def test_login_required(self):
        self.client.logout()
        resp = self.client.get(reverse("bookings:book"))
        self.assertEqual(resp.status_code, 302)

    def test_get_renders_form(self):
        resp = self.client.get(reverse("bookings:book"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Send booking request")

    def test_post_creates_requested_job_and_emails(self):
        resp = self.client.post(reverse("bookings:book"), self._payload())
        self.assertRedirects(resp, reverse("bookings:projects"))
        job = Job.objects.get()
        self.assertEqual(job.user, self.user)
        self.assertEqual(job.status, Job.Status.REQUESTED)
        self.assertEqual(job.title, "LVT to kitchen")
        self.assertEqual(job.contact_name, "Sam Buyer")
        self.assertTrue(job.reference.startswith("JN"))
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("Sam Buyer", body)
        self.assertIn("1 Test Street, Chelmsford", body)
        self.assertIn("LVT to kitchen", body)

    def test_name_and_address_are_required_without_a_quote(self):
        resp = self.client.post(
            reverse("bookings:book"),
            self._payload(contact_name="", site_address=""),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Job.objects.count(), 0)

    def test_honeypot_blocks(self):
        resp = self.client.post(
            reverse("bookings:book"), self._payload(website="http://spam")
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Job.objects.count(), 0)

    @override_settings(JOB_REQUEST_DAILY_LIMIT=1)
    def test_daily_limit(self):
        self.client.post(reverse("bookings:book"), self._payload())
        resp = self.client.post(reverse("bookings:book"), self._payload())
        self.assertRedirects(resp, reverse("bookings:projects"))
        self.assertEqual(Job.objects.count(), 1)

    def test_unknown_quote_reference_is_rejected(self):
        resp = self.client.post(
            reverse("bookings:book"), self._payload(quote_reference="JQ9999")
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Job.objects.count(), 0)

    def test_cannot_use_another_users_quote_reference(self):
        other_q = QuoteRequest.objects.create(
            user=make_user("other"), service_option=QuoteRequest.Service.SUPPLY_FIT,
            postcode="CM2 2BB", contact_name="Other",
        )
        resp = self.client.post(
            reverse("bookings:book"),
            self._payload(quote_reference=other_q.reference),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Job.objects.count(), 0)

    def test_landing_shows_book_and_projects(self):
        resp = self.client.get(reverse("bookings:index"))
        self.assertContains(resp, reverse("bookings:book"))
        self.assertContains(resp, reverse("bookings:projects"))


@LOCMEM
class QuoteToBookingTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.quote = QuoteRequest.objects.create(
            user=self.user, service_option=QuoteRequest.Service.SUPPLY_FIT,
            postcode="CM1 2AB", rooms="kitchen and hall", contact_name="Dana Floors",
            contact_phone="07123 456789", flooring_note="LVT herringbone",
            status=QuoteRequest.Status.QUOTED, quote_low=1200, quote_high=1500,
        )

    def test_quote_gets_a_reference(self):
        self.assertRegex(self.quote.reference, r"^JQ\d{4}$")

    def test_result_page_shows_reference_book_and_call_links(self):
        resp = self.client.get(
            reverse("bookings:quote_detail", kwargs={"slug": self.quote.slug})
        )
        self.assertContains(resp, self.quote.reference)
        self.assertContains(
            resp, reverse("bookings:book") + "?quote=" + self.quote.reference
        )
        self.assertContains(resp, reverse("bookings:call"))  # "Get in touch"

    def test_book_get_prefills_from_querystring(self):
        resp = self.client.get(
            reverse("bookings:book") + "?quote=" + self.quote.reference
        )
        self.assertContains(resp, "Dana Floors")
        self.assertContains(resp, "LVT herringbone")       # in the suggested title
        self.assertContains(resp, "CM1 2AB")

    def test_book_get_ignores_another_users_reference(self):
        mine = reverse("bookings:book")
        other = QuoteRequest.objects.create(
            user=make_user("stranger"), service_option=QuoteRequest.Service.SUPPLY_FIT,
            postcode="RM1 1AA", contact_name="Nope",
        )
        resp = self.client.get(mine + "?quote=" + other.reference)
        self.assertNotContains(resp, "Nope")

    def test_reference_links_quote_and_backfills_blank_fields(self):
        resp = self.client.post(reverse("bookings:book"), {
            "quote_reference": self.quote.reference.lower(),  # case-insensitive
            "title": "", "contact_name": "", "contact_phone": "",
            "site_address": "", "customer_note": "", "website": "",
        })
        self.assertRedirects(resp, reverse("bookings:projects"))
        job = Job.objects.get()
        self.assertEqual(job.quote_request, self.quote)
        self.assertEqual(job.contact_name, "Dana Floors")
        self.assertEqual(job.contact_phone, "07123 456789")
        self.assertIn("kitchen and hall", job.title)
        self.assertEqual(job.site_address, "CM1 2AB")
        body = mail.outbox[0].body
        self.assertIn("Dana Floors", body)
        self.assertIn("CM1 2AB", body)
        self.assertIn(self.quote.reference, body)

    def test_customer_can_override_prefilled_values(self):
        resp = self.client.post(reverse("bookings:book"), {
            "quote_reference": self.quote.reference,
            "title": "Just the hall", "contact_name": "Someone Else",
            "contact_phone": "07000 000000",
            "site_address": "9 New Road, Chelmsford CM2 0AA",
            "customer_note": "", "website": "",
        })
        self.assertRedirects(resp, reverse("bookings:projects"))
        job = Job.objects.get()
        self.assertEqual(job.quote_request, self.quote)
        self.assertEqual(job.title, "Just the hall")
        self.assertEqual(job.site_address, "9 New Road, Chelmsford CM2 0AA")


class PortalAccessTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner")
        self.job = Job.objects.create(user=self.owner, title="Hall & stairs")

    def test_projects_login_required(self):
        resp = self.client.get(reverse("bookings:projects"))
        self.assertEqual(resp.status_code, 302)

    def test_projects_lists_only_own_jobs(self):
        Job.objects.create(user=make_user("someone"), title="Not yours")
        self.client.force_login(self.owner)
        resp = self.client.get(reverse("bookings:projects"))
        self.assertContains(resp, "Hall &amp; stairs")
        self.assertNotContains(resp, "Not yours")

    def test_other_user_gets_404_on_detail(self):
        self.client.force_login(make_user("intruder"))
        resp = self.client.get(
            reverse("bookings:project_detail", kwargs={"slug": self.job.slug})
        )
        self.assertEqual(resp.status_code, 404)

    def test_owner_sees_detail(self):
        self.client.force_login(self.owner)
        resp = self.client.get(
            reverse("bookings:project_detail", kwargs={"slug": self.job.slug})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.job.reference)

    def test_staff_can_view_any_portal(self):
        staff = User.objects.create_user(
            username="boss", email="boss@example.com", password="pw1!pass",
            is_staff=True, is_superuser=True,
        )
        self.client.force_login(staff)
        resp = self.client.get(
            reverse("bookings:project_detail", kwargs={"slug": self.job.slug})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "as staff")


class JobMoneyTests(TestCase):
    def setUp(self):
        self.job = Job.objects.create(
            user=make_user(), title="Kitchen", status=Job.Status.AWAITING_DEPOSIT,
            agreed_price=Decimal("1200.00"),
        )

    def test_reference_is_assigned(self):
        self.assertEqual(self.job.reference, f"JN{self.job.pk:04d}")

    def test_booking_fee_is_20_percent_of_agreed_price(self):
        self.assertEqual(self.job.booking_fee, Decimal("240.00"))
        self.job.agreed_price = Decimal("1333.00")
        self.assertEqual(self.job.booking_fee, Decimal("266.60"))

    def test_booking_fee_is_none_before_price_is_set(self):
        self.assertIsNone(Job(user=self.job.user, title="x").booking_fee)

    def test_balance_tracks_payments(self):
        self.assertEqual(self.job.balance_due, Decimal("1200.00"))
        Payment.objects.create(
            job=self.job, amount=Decimal("100.00"), kind=Payment.Kind.BOOKING_FEE
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.total_paid, Decimal("100.00"))
        self.assertEqual(self.job.balance_due, Decimal("1100.00"))

    def test_booking_fee_payment_moves_job_to_booked(self):
        Payment.objects.create(
            job=self.job, amount=Decimal("100.00"), kind=Payment.Kind.BOOKING_FEE
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.NOT_STARTED)

    def test_balance_payment_does_not_change_status(self):
        self.job.status = Job.Status.UNDERWAY
        self.job.save()
        Payment.objects.create(job=self.job, amount=Decimal("500.00"))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.UNDERWAY)


class InvoiceTests(TestCase):
    def setUp(self):
        # Never hit the network for the logo during tests.
        patcher = patch("bookings.invoices._logo_data", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.job = Job.objects.create(
            user=make_user(), title="Lounge", agreed_price=Decimal("2000.00"),
        )
        Payment.objects.create(
            job=self.job, amount=Decimal("100.00"), kind=Payment.Kind.BOOKING_FEE
        )

    def _issue(self, kind=Invoice.Kind.FINAL):
        inv = Invoice(job=self.job, kind=kind)
        inv.snapshot_from_job()
        inv.save()
        inv.ensure_default_line_item()
        return inv

    def test_numbers_are_sequential(self):
        a = Invoice(job=self.job, kind=Invoice.Kind.DEPOSIT)
        a.snapshot_from_job()
        a.save()
        b = Invoice(job=self.job, kind=Invoice.Kind.FINAL)
        b.snapshot_from_job()
        b.save()
        self.assertNotEqual(a.number, b.number)
        self.assertTrue(a.number.startswith("INV-"))

    def test_deposit_snapshot_only_counts_booking_fee(self):
        Payment.objects.create(job=self.job, amount=Decimal("400.00"))
        inv = Invoice(job=self.job, kind=Invoice.Kind.DEPOSIT)
        inv.snapshot_from_job()
        self.assertEqual(inv.total_paid, Decimal("100.00"))

    def test_final_snapshot_counts_all_payments(self):
        Payment.objects.create(job=self.job, amount=Decimal("400.00"))
        inv = Invoice(job=self.job, kind=Invoice.Kind.FINAL)
        inv.snapshot_from_job()
        self.assertEqual(inv.total_paid, Decimal("500.00"))
        self.assertEqual(inv.balance, Decimal("1500.00"))

    def test_issue_creates_one_default_line_item(self):
        inv = self._issue(Invoice.Kind.FINAL)
        self.assertEqual(inv.line_items.count(), 1)
        self.assertEqual(inv.line_items.first().amount, Decimal("2000.00"))

    def test_line_items_drive_the_subtotal_and_balance(self):
        inv = self._issue(Invoice.Kind.FINAL)
        inv.line_items.all().delete()
        InvoiceLineItem.objects.create(
            invoice=inv, description="Supply & fit LVT", amount=Decimal("1500.00")
        )
        InvoiceLineItem.objects.create(
            invoice=inv, description="Lift the old floor", amount=Decimal("50.00")
        )
        inv.refresh_from_db()
        self.assertEqual(inv.agreed_total, Decimal("1550.00"))
        self.assertEqual(inv.balance, Decimal("1450.00"))  # 1550 - 100 paid

    def test_payments_are_frozen_at_issue(self):
        inv = self._issue(Invoice.Kind.FINAL)
        self.assertEqual(len(inv.payments_snapshot), 1)
        self.assertEqual(inv.payments_snapshot[0]["amount"], "100.00")
        Payment.objects.create(job=self.job, amount=Decimal("900.00"))
        inv.refresh_from_db()
        self.assertEqual(len(inv.payments_snapshot), 1)  # unchanged

    def test_pdf_download(self):
        inv = self._issue(Invoice.Kind.FINAL)
        self.client.force_login(self.job.user)
        resp = self.client.get(reverse(
            "bookings:invoice_pdf",
            kwargs={"slug": self.job.slug, "number": inv.number},
        ))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertTrue(resp.content.startswith(b"%PDF"))
        self.assertGreater(len(resp.content), 1000)

    def test_pdf_renders_with_a_logo(self):
        with patch("bookings.invoices._logo_data", return_value=tiny_png().read()):
            inv = self._issue(Invoice.Kind.DEPOSIT)
            from bookings.invoices import render_invoice_pdf
            pdf = render_invoice_pdf(inv)
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_pdf_denied_to_other_user(self):
        inv = self._issue(Invoice.Kind.FINAL)
        self.client.force_login(make_user("nope"))
        resp = self.client.get(reverse(
            "bookings:invoice_pdf",
            kwargs={"slug": self.job.slug, "number": inv.number},
        ))
        self.assertEqual(resp.status_code, 404)


@IN_MEMORY_STORAGE
class JobPhotoTests(TestCase):
    def test_photo_urls_and_detail_render(self):
        job = Job.objects.create(
            user=make_user(), title="Bedroom", status=Job.Status.COMPLETE,
            agreed_price=Decimal("900.00"),
        )
        JobPhoto.objects.create(job=job, image=tiny_png(), caption="All done")
        self.client.force_login(job.user)
        resp = self.client.get(
            reverse("bookings:project_detail", kwargs={"slug": job.slug})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "All done")


STRIPE_ON = override_settings(
    STRIPE_SECRET_KEY="sk_test_x",
    STRIPE_PUBLISHABLE_KEY="pk_test_x",
    STRIPE_WEBHOOK_SECRET="whsec_x",
)

FAKE_INTENT = {"id": "pi_test_1", "client_secret": "pi_test_1_secret_abc"}


@LOCMEM
@STRIPE_ON
class StripePaymentTests(TestCase):
    def setUp(self):
        self.user = make_user("payer")
        self.client.force_login(self.user)
        self.job = Job.objects.create(
            user=self.user, title="Kitchen LVT", agreed_price=Decimal("1000.00"),
            status=Job.Status.AWAITING_DEPOSIT, contact_name="Sam Payer",
            site_address="1 Test Rd, Chelmsford",
        )

    def _detail_url(self):
        return reverse("bookings:project_detail", kwargs={"slug": self.job.slug})

    # -- buttons show only when Stripe is on --------------------------

    @override_settings(STRIPE_SECRET_KEY="", STRIPE_PUBLISHABLE_KEY="")
    def test_no_pay_button_when_stripe_off(self):
        resp = self.client.get(self._detail_url())
        self.assertNotContains(
            resp, reverse("bookings:pay_deposit", kwargs={"slug": self.job.slug})
        )

    def test_pay_button_shows_when_stripe_on(self):
        resp = self.client.get(self._detail_url())
        self.assertContains(
            resp, reverse("bookings:pay_deposit", kwargs={"slug": self.job.slug})
        )

    # -- starting a deposit payment ----------------------------------

    @patch("bookings.views.create_payment_intent", return_value=FAKE_INTENT)
    def test_pay_deposit_creates_cardpayment_and_redirects(self, mock_pi):
        resp = self.client.post(
            reverse("bookings:pay_deposit", kwargs={"slug": self.job.slug})
        )
        cp = CardPayment.objects.get()
        self.assertEqual(cp.purpose, CardPayment.Purpose.BOOKING_FEE)
        self.assertEqual(cp.amount, Decimal("200.00"))  # 20% of 1000
        self.assertEqual(cp.stripe_payment_intent, "pi_test_1")
        self.assertRedirects(
            resp, reverse("bookings:checkout", kwargs={"slug": cp.slug})
        )
        mock_pi.assert_called_once()

    @patch("bookings.views.create_payment_intent", return_value=FAKE_INTENT)
    def test_pay_deposit_wrong_status_does_nothing(self, _mock):
        self.job.status = Job.Status.UNDERWAY
        self.job.save()
        self.client.post(
            reverse("bookings:pay_deposit", kwargs={"slug": self.job.slug})
        )
        self.assertEqual(CardPayment.objects.count(), 0)

    @patch("bookings.views.create_payment_intent", return_value=FAKE_INTENT)
    def test_staff_cannot_start_a_card_payment(self, _mock):
        boss = User.objects.create_user(
            username="boss2", email="boss2@example.com", password="pw1!pass",
            is_staff=True, is_superuser=True,
        )
        self.client.force_login(boss)
        resp = self.client.post(
            reverse("bookings:pay_deposit", kwargs={"slug": self.job.slug})
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(CardPayment.objects.count(), 0)

    # -- the checkout page -----------------------------------------

    def _card_payment(self, purpose=CardPayment.Purpose.BOOKING_FEE,
                      amount=Decimal("200.00")):
        return CardPayment.objects.create(
            job=self.job, user=self.user, purpose=purpose, amount=amount,
            stripe_payment_intent="pi_test_1",
            client_secret="pi_test_1_secret_abc",
        )

    def test_checkout_page_renders_with_keys(self):
        cp = self._card_payment()
        resp = self.client.get(
            reverse("bookings:checkout", kwargs={"slug": cp.slug})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "pk_test_x")
        self.assertContains(resp, "pi_test_1_secret_abc")
        self.assertContains(resp, "authorise")

    def test_checkout_post_records_authorisation(self):
        cp = self._card_payment()
        resp = self.client.post(
            reverse("bookings:checkout", kwargs={"slug": cp.slug}),
            {"name": "Sam Payer", "email": "sam@example.com", "billing": "{}"},
        )
        self.assertEqual(resp.json(), {"ok": True})
        cp.refresh_from_db()
        self.assertEqual(cp.payer_name, "Sam Payer")
        self.assertIsNotNone(cp.authorised_at)

    def test_checkout_belongs_to_another_user_is_404(self):
        cp = self._card_payment()
        self.client.force_login(make_user("intruder"))
        resp = self.client.get(
            reverse("bookings:checkout", kwargs={"slug": cp.slug})
        )
        self.assertEqual(resp.status_code, 404)

    # -- money lands: return page + webhook ------------------------

    @patch("bookings.views.retrieve_intent", return_value={"status": "succeeded"})
    def test_return_page_records_payment_and_moves_job(self, _mock):
        cp = self._card_payment()
        self.client.get(
            reverse("bookings:checkout_return", kwargs={"slug": cp.slug})
        )
        cp.refresh_from_db()
        self.job.refresh_from_db()
        self.assertEqual(cp.status, CardPayment.Status.SUCCEEDED)
        self.assertEqual(self.job.status, Job.Status.NOT_STARTED)
        p = Payment.objects.get()
        self.assertEqual(p.method, Payment.Method.CARD)
        self.assertEqual(p.amount, Decimal("200.00"))
        self.assertEqual(p.reference, "pi_test_1")

    def _webhook(self, event):
        with patch("bookings.views.verify_webhook", return_value=event):
            return self.client.post(
                reverse("bookings:stripe_webhook"), data="{}",
                content_type="application/json", HTTP_STRIPE_SIGNATURE="t=1,v1=x",
            )

    def test_webhook_success_records_payment(self):
        cp = self._card_payment()
        event = {"type": "payment_intent.succeeded",
                 "data": {"object": {"id": "pi_test_1",
                                     "metadata": {"card_payment": str(cp.slug)}}}}
        resp = self._webhook(event)
        self.assertEqual(resp.status_code, 200)
        cp.refresh_from_db()
        self.assertEqual(cp.status, CardPayment.Status.SUCCEEDED)
        self.assertEqual(Payment.objects.filter(reference="pi_test_1").count(), 1)

    def test_webhook_is_idempotent(self):
        cp = self._card_payment()
        event = {"type": "payment_intent.succeeded",
                 "data": {"object": {"id": "pi_test_1",
                                     "metadata": {"card_payment": str(cp.slug)}}}}
        self._webhook(event)
        self._webhook(event)
        self.assertEqual(Payment.objects.filter(reference="pi_test_1").count(), 1)

    def test_webhook_bad_signature_is_400(self):
        with patch("bookings.views.verify_webhook", side_effect=ValueError("bad")):
            resp = self.client.post(
                reverse("bookings:stripe_webhook"), data="{}",
                content_type="application/json", HTTP_STRIPE_SIGNATURE="x",
            )
        self.assertEqual(resp.status_code, 400)

    def test_webhook_failure_marks_failed(self):
        cp = self._card_payment()
        event = {"type": "payment_intent.payment_failed",
                 "data": {"object": {"id": "pi_test_1",
                                     "metadata": {"card_payment": str(cp.slug)},
                                     "last_payment_error": {"message": "Card declined"}}}}
        self._webhook(event)
        cp.refresh_from_db()
        self.assertEqual(cp.status, CardPayment.Status.FAILED)
        self.assertEqual(cp.error_message, "Card declined")

    # -- balance / part payments ----------------------------------

    def _live_job(self):
        Payment.objects.create(
            job=self.job, amount=Decimal("200.00"),
            kind=Payment.Kind.BOOKING_FEE, method=Payment.Method.CARD,
        )
        self.job.refresh_from_db()  # now NOT_STARTED, balance 800
        return self.job

    @patch("bookings.views.create_payment_intent", return_value=FAKE_INTENT)
    def test_pay_full_balance(self, _mock):
        self._live_job()
        resp = self.client.post(
            reverse("bookings:pay_balance", kwargs={"slug": self.job.slug}),
            {"choice": "full"},
        )
        cp = CardPayment.objects.filter(purpose=CardPayment.Purpose.BALANCE).get()
        self.assertEqual(cp.amount, Decimal("800.00"))
        self.assertRedirects(
            resp, reverse("bookings:checkout", kwargs={"slug": cp.slug})
        )

    @patch("bookings.views.create_payment_intent", return_value=FAKE_INTENT)
    def test_pay_part_balance(self, _mock):
        self._live_job()
        self.client.post(
            reverse("bookings:pay_balance", kwargs={"slug": self.job.slug}),
            {"choice": "part", "amount": "300"},
        )
        cp = CardPayment.objects.filter(purpose=CardPayment.Purpose.PART).get()
        self.assertEqual(cp.amount, Decimal("300.00"))

    @patch("bookings.views.create_payment_intent", return_value=FAKE_INTENT)
    def test_part_amount_over_balance_is_rejected(self, _mock):
        self._live_job()
        self.client.post(
            reverse("bookings:pay_balance", kwargs={"slug": self.job.slug}),
            {"choice": "part", "amount": "5000"},
        )
        self.assertEqual(CardPayment.objects.count(), 0)

    # -- auto-invoice + owner notification on success --------------

    def test_deposit_payment_auto_issues_receipt_and_emails_owner(self):
        cp = self._card_payment()
        event = {"type": "payment_intent.succeeded",
                 "data": {"object": {"id": "pi_test_1",
                                     "metadata": {"card_payment": str(cp.slug)}}}}
        self._webhook(event)
        cp.refresh_from_db()
        self.assertIsNotNone(cp.invoice_id)
        self.assertEqual(cp.invoice.kind, Invoice.Kind.DEPOSIT)
        self.assertEqual(cp.invoice.line_items.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("JN", body)
        self.assertIn("BOOKED", body)

    def test_finalise_is_idempotent_one_invoice_one_email(self):
        cp = self._card_payment()
        event = {"type": "payment_intent.succeeded",
                 "data": {"object": {"id": "pi_test_1",
                                     "metadata": {"card_payment": str(cp.slug)}}}}
        self._webhook(event)     # e.g. Stripe retries the webhook
        self._webhook(event)
        self.assertEqual(Invoice.objects.filter(job=self.job).count(), 1)
        self.assertEqual(Payment.objects.filter(reference="pi_test_1").count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    @patch("bookings.views.create_payment_intent", return_value=FAKE_INTENT)
    def test_part_payment_issues_a_receipt_kind_invoice(self, _mock):
        self._live_job()  # balance 800
        cp = CardPayment.objects.create(
            job=self.job, user=self.user, purpose=CardPayment.Purpose.PART,
            amount=Decimal("300.00"), stripe_payment_intent="pi_part",
        )
        with patch("bookings.views.retrieve_intent", return_value={"status": "succeeded"}):
            self.client.get(
                reverse("bookings:checkout_return", kwargs={"slug": cp.slug})
            )
        cp.refresh_from_db()
        self.assertEqual(cp.invoice.kind, Invoice.Kind.RECEIPT)
        self.job.refresh_from_db()
        self.assertEqual(self.job.balance_due, Decimal("500.00"))

    @patch("bookings.views.create_payment_intent", return_value=FAKE_INTENT)
    def test_balance_clearing_payment_issues_a_final_invoice(self, _mock):
        self._live_job()  # balance 800
        cp = CardPayment.objects.create(
            job=self.job, user=self.user, purpose=CardPayment.Purpose.BALANCE,
            amount=Decimal("800.00"), stripe_payment_intent="pi_bal",
        )
        with patch("bookings.views.retrieve_intent", return_value={"status": "succeeded"}):
            self.client.get(
                reverse("bookings:checkout_return", kwargs={"slug": cp.slug})
            )
        cp.refresh_from_db()
        self.assertEqual(cp.invoice.kind, Invoice.Kind.FINAL)
        self.job.refresh_from_db()
        self.assertEqual(self.job.balance_due, Decimal("0.00"))


@LOCMEM
class StaffManageTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="boss", email="boss@example.com", password="pw1!pass",
            is_staff=True, is_superuser=True,
        )
        self.customer = make_user("cust")
        self.job = Job.objects.create(
            user=self.customer, title="Hall LVT", contact_name="Cass Customer",
        )
        self.client.force_login(self.staff)

    def _detail(self):
        return reverse("bookings:project_detail", kwargs={"slug": self.job.slug})

    def _future(self, days=10):
        return (timezone.localdate() + timezone.timedelta(days=days)).isoformat()

    # -- dashboard -----------------------------------------------------

    def test_dashboard_lists_all_jobs(self):
        Job.objects.create(user=make_user("other"), title="Kitchen tiles")
        resp = self.client.get(reverse("bookings:manage"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Hall LVT")
        self.assertContains(resp, "Kitchen tiles")

    def test_dashboard_denied_to_normal_user(self):
        self.client.force_login(self.customer)
        resp = self.client.get(reverse("bookings:manage"))
        self.assertEqual(resp.status_code, 404)

    def test_dashboard_status_filter(self):
        Job.objects.create(
            user=self.customer, title="Underway one", status=Job.Status.UNDERWAY,
        )
        resp = self.client.get(reverse("bookings:manage") + "?status=underway")
        self.assertContains(resp, "Underway one")
        self.assertNotContains(resp, "Hall LVT")

    # -- accepting / progressing from the portal ----------------------

    def test_staff_panel_appears_on_detail(self):
        resp = self.client.get(self._detail())
        self.assertContains(resp, "Manage this job")
        self.assertContains(resp, "Accept &amp; confirm booking")

    def test_panel_shows_the_linked_quote_price_and_breakdown(self):
        quote = QuoteRequest.objects.create(
            user=self.customer, service_option=QuoteRequest.Service.SUPPLY_FIT,
            postcode="CM1 1AA", contact_name="Cass Customer",
            flooring_note="LVT", rooms="kitchen",
            status=QuoteRequest.Status.QUOTED,
            quote_low=Decimal("1400"), quote_high=Decimal("1700"),
            ai_result={"breakdown": [
                {"label": "LVT fitting labour", "low": 900, "high": 1100},
                {"label": "Lifting the old floor", "low": 50, "high": 50},
            ]},
        )
        job = Job.objects.create(
            user=self.customer, title="Kitchen LVT", quote_request=quote,
        )
        resp = self.client.get(
            reverse("bookings:project_detail", kwargs={"slug": job.slug})
        )
        self.assertContains(resp, quote.reference)
        self.assertContains(resp, "1400")
        self.assertContains(resp, "1700")
        self.assertContains(resp, "LVT fitting labour")
        self.assertContains(resp, "Lifting the old floor")

    def test_panel_has_no_quote_box_without_a_linked_quote(self):
        resp = self.client.get(self._detail())  # self.job has no quote_request
        self.assertNotContains(resp, "From quote")

    def test_confirm_booking_from_portal(self):
        resp = self.client.post(self._detail(), {
            "action": "confirm", "agreed_price": "1500",
            "start_date": self._future(),
            "summary": "LVT to the hall", "contact_name": "Cass Customer",
            "contact_phone": "", "site_address": "1 A Street, Chelmsford",
        })
        self.assertRedirects(resp, self._detail())
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.AWAITING_DEPOSIT)
        self.assertEqual(self.job.agreed_price, Decimal("1500"))
        self.assertEqual(self.job.booking_fee, Decimal("300.00"))  # 20%
        self.assertIsNotNone(self.job.confirmed_at)

    def test_confirm_needs_price_and_date(self):
        self.client.post(self._detail(), {
            "action": "confirm", "agreed_price": "", "start_date": "",
        })
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.REQUESTED)

    def test_record_fee_books_the_job_in_at_20_percent(self):
        Job.objects.filter(pk=self.job.pk).update(
            status=Job.Status.AWAITING_DEPOSIT, agreed_price=Decimal("1500"),
        )
        self.client.post(self._detail(), {"action": "record_fee", "method": "bank"})
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.NOT_STARTED)
        fee = self.job.payments.get(kind=Payment.Kind.BOOKING_FEE)
        self.assertEqual(fee.amount, Decimal("300.00"))

    def test_start_then_complete(self):
        Job.objects.filter(pk=self.job.pk).update(
            status=Job.Status.NOT_STARTED, agreed_price=Decimal("1500"),
        )
        self.client.post(self._detail(), {"action": "start"})
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.UNDERWAY)
        self.client.post(self._detail(), {"action": "complete"})
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.COMPLETE)

    def test_record_payment_from_portal(self):
        Job.objects.filter(pk=self.job.pk).update(
            status=Job.Status.UNDERWAY, agreed_price=Decimal("1500"),
        )
        self.client.post(self._detail(), {
            "action": "record_payment", "amount": "700", "kind": "balance",
            "method": "bank", "received_on": timezone.localdate().isoformat(),
            "reference": "", "note": "",
        })
        self.job.refresh_from_db()
        self.assertEqual(self.job.total_paid, Decimal("700"))

    def test_issue_final_invoice_from_portal(self):
        Job.objects.filter(pk=self.job.pk).update(
            status=Job.Status.COMPLETE, agreed_price=Decimal("1500"),
        )
        self.client.post(self._detail(), {"action": "issue_final"})
        self.assertEqual(self.job.invoices.count(), 1)

    def test_customer_cannot_post_staff_actions(self):
        self.client.force_login(self.customer)
        resp = self.client.post(self._detail(), {"action": "start"})
        self.assertEqual(resp.status_code, 404)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.REQUESTED)


class AvailabilityTests(TestCase):
    @override_settings(ANTHROPIC_API_KEY="", QUOTING_PREVIEW=False)
    def test_not_available_without_key(self):
        self.assertFalse(quoting_available())

    @override_settings(ANTHROPIC_API_KEY="k", QUOTING_PREVIEW=False)
    def test_available_with_rate_card_and_key(self):
        self.assertTrue(quoting_available())

    @override_settings(ANTHROPIC_API_KEY="", QUOTING_PREVIEW=True)
    def test_preview_mode_counts_as_available(self):
        self.assertTrue(quoting_available())

    @override_settings(ANTHROPIC_API_KEY="k", QUOTING_PREVIEW=False)
    def test_not_available_with_empty_rate_card(self):
        clear_rate_card()
        self.assertFalse(quoting_available())
