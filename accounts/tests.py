from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


def valid_registration(**extra):
    data = {
        "email": "newuser@example.com",
        "username": "newuser",
        "password": "pw1!pass",
        "password_confirm": "pw1!pass",
        "terms_accepted": "on",
    }
    data.update(extra)
    return data


class LoginRedirectTests(TestCase):
    """`?next=` after login must only ever point back at this site - an
    unchecked redirect target is an open-redirect / phishing vector (found
    and fixed during the pre-deploy security review)."""

    def setUp(self):
        cache.clear()  # each test starts with a clean login-throttle slate
        self.user = User.objects.create_user(
            username="nextuser", email="nextuser@example.com", password="pw1!pass",
        )

    def _login(self, next_url):
        return self.client.post(
            f"/accounts/login/?next={next_url}",
            {"username": "nextuser", "password": "pw1!pass"},
        )

    def test_offsite_next_is_ignored(self):
        resp = self._login("https://evil.example/steal")
        self.assertEqual(resp.url, "/")

    def test_protocol_relative_next_is_ignored(self):
        resp = self._login("//evil.example/steal")
        self.assertEqual(resp.url, "/")

    def test_same_site_next_is_honoured(self):
        resp = self._login("/bookings/")
        self.assertEqual(resp.url, "/bookings/")


class LoginThrottleTests(TestCase):
    """After LOGIN_MAX_ATTEMPTS wrong passwords, further attempts against
    that account are refused for the lockout window - found missing (no
    brute-force protection at all) during the pre-deploy security review."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="throttleuser", email="throttleuser@example.com",
            password="pw1!pass",
        )

    def _attempt(self, password):
        return self.client.post(
            "/accounts/login/", {"username": "throttleuser", "password": password},
        )

    def test_locks_out_after_max_attempts(self):
        for _ in range(5):
            resp = self._attempt("wrong")
            self.assertEqual(resp.status_code, 200)

        # 6th attempt - even with the CORRECT password - is refused.
        resp = self._attempt("pw1!pass")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Too many failed attempts")
        self.assertFalse(resp.wsgi_request.user.is_authenticated)

    def test_successful_login_clears_the_counter(self):
        for _ in range(4):
            self._attempt("wrong")

        resp = self._attempt("pw1!pass")  # 5th attempt, correct - still allowed
        self.assertEqual(resp.status_code, 302)

        # Counter reset - a fresh run of wrong attempts starts from zero again.
        self.client.logout()
        for _ in range(4):
            resp = self._attempt("wrong")
            self.assertEqual(resp.status_code, 200)
            self.assertNotContains(resp, "Too many failed attempts")

    def test_lockout_does_not_affect_a_different_account_from_a_different_ip(self):
        # The lockout is keyed on IP as well as account (so an attacker can't
        # dodge it by spraying many accounts from one IP) - a genuinely
        # unrelated visitor, on a different IP, must be unaffected.
        other = User.objects.create_user(
            username="otheruser", email="otheruser@example.com", password="pw1!pass",
        )
        for _ in range(5):
            self._attempt("wrong")

        resp = self.client.post(
            "/accounts/login/", {"username": "otheruser", "password": "pw1!pass"},
            REMOTE_ADDR="10.0.0.5",
        )
        self.assertEqual(resp.status_code, 302)

    def test_ip_lockout_blocks_spraying_different_accounts_from_one_ip(self):
        # Failing five different accounts from the same IP locks out that
        # IP too, even against an account it hasn't touched before.
        for i in range(5):
            self.client.post(
                "/accounts/login/",
                {"username": f"no-such-user-{i}", "password": "wrong"},
                REMOTE_ADDR="10.0.0.9",
            )

        resp = self.client.post(
            "/accounts/login/", {"username": "throttleuser", "password": "pw1!pass"},
            REMOTE_ADDR="10.0.0.9",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Too many failed attempts")


class RegistrationTermsTests(TestCase):
    """Registration requires agreeing to the Terms & Privacy Policy, and
    records exactly when - added alongside those pages during the
    pre-launch security/compliance review."""

    def test_registration_requires_accepting_terms(self):
        resp = self.client.post(
            reverse("accounts:register"), valid_registration(terms_accepted=""),
        )
        self.assertEqual(resp.status_code, 200)  # re-rendered with the error
        self.assertFalse(User.objects.filter(username="newuser").exists())
        self.assertContains(resp, "accept the Terms")

    def test_registration_records_when_terms_were_accepted(self):
        resp = self.client.post(reverse("accounts:register"), valid_registration())
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(username="newuser")
        self.assertIsNotNone(user.terms_accepted_at)

    def test_registration_form_links_to_both_documents(self):
        resp = self.client.get(reverse("accounts:register"))
        self.assertContains(resp, reverse("core:terms"))
        self.assertContains(resp, reverse("core:privacy"))
