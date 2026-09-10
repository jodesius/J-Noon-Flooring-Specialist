from django.test import TestCase


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
