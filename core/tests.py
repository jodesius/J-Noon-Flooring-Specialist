import json
import re
from xml.etree import ElementTree

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from bookings.models import Job, Payment, RefundRequest

User = get_user_model()


def make_user(username="cust"):
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", password="pw1!pass"
    )


class YourProjectsShortcutTests(TestCase):
    """The "Your projects" nav link + home hero button - shown only while
    the customer has a live (not complete/cancelled) job.
    """

    def setUp(self):
        self.user = make_user()

    def _get_home(self):
        return self.client.get(reverse("core:home"))

    def test_hidden_when_logged_out(self):
        resp = self._get_home()
        self.assertNotContains(resp, "Your projects")

    def test_hidden_with_no_jobs(self):
        self.client.force_login(self.user)
        resp = self._get_home()
        self.assertNotContains(resp, "Your projects")

    def test_shown_for_a_requested_job(self):
        Job.objects.create(user=self.user, title="Hall & stairs", status=Job.Status.REQUESTED)
        self.client.force_login(self.user)
        resp = self._get_home()
        self.assertContains(resp, "Your projects")
        self.assertContains(resp, reverse("bookings:projects"))

    def test_shown_for_an_underway_job(self):
        Job.objects.create(user=self.user, title="Hall & stairs", status=Job.Status.UNDERWAY)
        self.client.force_login(self.user)
        resp = self._get_home()
        self.assertContains(resp, "Your projects")

    def test_hidden_when_only_job_is_complete(self):
        Job.objects.create(user=self.user, title="Hall & stairs", status=Job.Status.COMPLETE)
        self.client.force_login(self.user)
        resp = self._get_home()
        self.assertNotContains(resp, "Your projects")

    def test_hidden_when_only_job_is_cancelled(self):
        Job.objects.create(user=self.user, title="Hall & stairs", status=Job.Status.CANCELLED)
        self.client.force_login(self.user)
        resp = self._get_home()
        self.assertNotContains(resp, "Your projects")

    def test_shown_on_another_page_too_not_just_home(self):
        Job.objects.create(user=self.user, title="Hall & stairs", status=Job.Status.NOT_STARTED)
        self.client.force_login(self.user)
        resp = self.client.get(reverse("contact:index"))
        self.assertContains(resp, "Your projects")


class ManageBookingsShortcutTests(TestCase):
    """The "Manage bookings" nav link + home hero button - admin/superuser
    only (Job.is_site_admin).
    """

    def _get_home(self):
        return self.client.get(reverse("core:home"))

    def test_hidden_when_logged_out(self):
        self.assertNotContains(self._get_home(), "Manage bookings")

    def test_hidden_for_an_ordinary_customer(self):
        self.client.force_login(make_user())
        self.assertNotContains(self._get_home(), "Manage bookings")

    def test_shown_for_a_superuser(self):
        staff = User.objects.create_user(
            username="boss", email="boss@example.com", password="pw1!pass",
            is_staff=True, is_superuser=True,
        )
        self.client.force_login(staff)
        resp = self._get_home()
        self.assertContains(resp, "Manage bookings")
        self.assertContains(resp, reverse("bookings:manage"))

    def test_shown_for_a_site_administrators_group_member(self):
        from django.contrib.auth.models import Group

        group, _ = Group.objects.get_or_create(name="Site Administrators")
        staff = make_user("groupstaff")
        staff.groups.add(group)
        self.client.force_login(staff)
        self.assertContains(self._get_home(), "Manage bookings")

    def test_shown_on_another_page_too_not_just_home(self):
        staff = User.objects.create_user(
            username="boss2", email="boss2@example.com", password="pw1!pass",
            is_staff=True, is_superuser=True,
        )
        self.client.force_login(staff)
        resp = self.client.get(reverse("contact:index"))
        self.assertContains(resp, "Manage bookings")


class RefundRequestNavPillTests(TestCase):
    """The "N refund" pill next to an admin's name, alongside the unread-
    messages one - open refund requests, admin/superuser only."""

    def setUp(self):
        self.customer = make_user()
        self.job = Job.objects.create(user=self.customer, title="Hall & stairs")
        Payment.objects.create(job=self.job, amount=100, kind=Payment.Kind.PART)
        RefundRequest.objects.create(
            job=self.job, requested_by=self.customer, reason="Not what I ordered"
        )

    def _get_home(self):
        return self.client.get(reverse("core:home"))

    def test_shown_for_an_admin(self):
        staff = User.objects.create_user(
            username="boss3", email="boss3@example.com", password="pw1!pass",
            is_staff=True, is_superuser=True,
        )
        self.client.force_login(staff)
        self.assertContains(self._get_home(), "1 refund")

    def test_hidden_for_a_customer(self):
        self.client.force_login(self.customer)
        self.assertNotContains(self._get_home(), "refund")

    def test_hidden_once_resolved(self):
        staff = User.objects.create_user(
            username="boss4", email="boss4@example.com", password="pw1!pass",
            is_staff=True, is_superuser=True,
        )
        self.job.open_refund_request.resolve()
        self.client.force_login(staff)
        self.assertNotContains(self._get_home(), "1 refund")


class CustomErrorPageTests(TestCase):
    """The test runner sets DEBUG=False, so Django uses the project's own
    templates/404.html here (in local dev with DEBUG=True you still get the
    Django debug page).
    """

    def test_unknown_url_renders_the_custom_404_page(self):
        resp = self.client.get("/no-such-page-anywhere/")

        self.assertEqual(resp.status_code, 404)
        self.assertTemplateUsed(resp, "404.html")
        self.assertContains(resp, "404 URL error", status_code=404)
        self.assertContains(resp, "Back to the home page", status_code=404)


def _meta_content(html, name=None, prop=None):
    """Pull a meta tag's content attribute out of rendered HTML - either
    <meta name="..."> or <meta property="..."> (Open Graph uses property=)."""
    attr, value = ("name", name) if name else ("property", prop)
    m = re.search(
        rf'<meta {attr}="{re.escape(value)}" content="([^"]*)"', html
    )
    return m.group(1) if m else None


class SeoBoilerplateTests(TestCase):
    """The SEO/semantic head boilerplate added ahead of deployment: meta
    description, robots, canonical, Open Graph, favicons and the
    LocalBusiness JSON-LD block. Covers a public page (default index/follow)
    and a private one (noindex/nofollow override) so both branches of the
    {% block robots %} default are exercised.
    """

    def test_public_page_has_default_index_follow_and_description(self):
        resp = self.client.get(reverse("core:home"))
        html = resp.content.decode()

        self.assertEqual(_meta_content(html, name="robots"), "index, follow")
        self.assertTrue(_meta_content(html, name="description"))
        self.assertTrue(_meta_content(html, name="author"))

    def test_public_page_has_open_graph_and_canonical(self):
        resp = self.client.get(reverse("core:home"))
        html = resp.content.decode()

        self.assertTrue(_meta_content(html, prop="og:title"))
        self.assertTrue(_meta_content(html, prop="og:description"))
        self.assertEqual(_meta_content(html, prop="og:type"), "website")
        self.assertIn('rel="canonical"', html)
        self.assertIn(reverse("core:home"), html)

    def test_private_page_is_noindex_nofollow(self):
        resp = self.client.get(reverse("accounts:login"))
        html = resp.content.decode()

        self.assertEqual(_meta_content(html, name="robots"), "noindex, nofollow")

    def test_favicon_links_present(self):
        resp = self.client.get(reverse("core:home"))
        html = resp.content.decode()

        self.assertIn('rel="icon"', html)
        self.assertIn('rel="apple-touch-icon"', html)

    def test_json_ld_is_valid_and_reflects_site_contact(self):
        from contact.models import SiteContact

        contact = SiteContact.load()
        contact.phone = "01234 567890"
        contact.email = "info@example.com"
        contact.service_area = "Chelmsford and a 25-mile radius of Essex"
        contact.save()

        resp = self.client.get(reverse("core:home"))
        html = resp.content.decode()

        m = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            html,
            re.S,
        )
        self.assertIsNotNone(m)
        data = json.loads(m.group(1))

        self.assertEqual(data["@type"], "HomeAndConstructionBusiness")
        self.assertEqual(data["name"], "J-Noon Flooring Specialist")
        self.assertEqual(data["telephone"], contact.phone)
        self.assertEqual(data["email"], contact.email)
        self.assertEqual(data["areaServed"], contact.service_area)
        self.assertIn("geo", data)
        self.assertNotIn("streetAddress", data["address"])


class RobotsTxtTests(TestCase):
    def test_robots_txt_is_served_as_plain_text(self):
        resp = self.client.get("/robots.txt")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/plain")

    def test_robots_txt_disallows_private_areas_and_names_sitemap(self):
        resp = self.client.get("/robots.txt")
        body = resp.content.decode()

        self.assertIn("Disallow: /admin/", body)
        self.assertIn("Disallow: /accounts/", body)
        self.assertIn("Disallow: /bookings/manage/", body)
        self.assertRegex(body, r"Sitemap: https?://\S+/sitemap\.xml")


class SitemapTests(TestCase):
    def test_sitemap_lists_the_public_pages(self):
        resp = self.client.get("/sitemap.xml")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/xml")

        root = ElementTree.fromstring(resp.content)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = {el.text for el in root.findall("sm:url/sm:loc", ns)}

        for name in ("core:home", "bookings:index", "gallery:index",
                     "reviews:list", "contact:index"):
            path = reverse(name)
            self.assertTrue(
                any(loc.endswith(path) for loc in locs),
                f"{path} not found in sitemap: {locs}",
            )


class LegalPageTests(TestCase):
    """Privacy Policy / Terms & Conditions - added during the pre-launch
    security/compliance review, alongside the registration consent
    checkbox in accounts/tests.py::RegistrationTermsTests."""

    def test_privacy_page_renders(self):
        resp = self.client.get(reverse("core:privacy"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Privacy Policy")

    def test_terms_page_renders(self):
        resp = self.client.get(reverse("core:terms"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Terms")

    def test_footer_links_to_both_on_any_page(self):
        resp = self.client.get(reverse("core:home"))
        self.assertContains(resp, reverse("core:privacy"))
        self.assertContains(resp, reverse("core:terms"))
