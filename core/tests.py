from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from bookings.models import Job

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
