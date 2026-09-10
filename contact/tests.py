from django.test import TestCase
from django.urls import reverse


class ContactPageTests(TestCase):
    def test_page_renders(self):
        resp = self.client.get(reverse("contact:index"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "contact/index.html")
