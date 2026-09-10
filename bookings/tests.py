from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .calendar_sync import CalendarUnavailable
from .models import CallRequest, FlooringRate, QuoteRequest, QuoteSettings
from .quoting import QuotingUnavailable, _sanitise, quoting_available

User = get_user_model()

LOCMEM = override_settings(
    MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
)


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
