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
