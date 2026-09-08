from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import Review

User = get_user_model()


def make_user(username, **extra):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="pass1!word",
        **extra,
    )


def make_review(author, **extra):
    defaults = {
        "rating": 5,
        "headline": "Great work",
        "body": "Really happy with the floor.",
        "is_approved": True,
    }
    defaults.update(extra)
    return Review.objects.create(author=author, **defaults)


class ReviewListTests(TestCase):
    def test_only_approved_reviews_are_listed(self):
        author = make_user("alice")
        make_review(author, headline="Approved one", is_approved=True)
        make_review(author, headline="Pending one", is_approved=False)

        resp = self.client.get(reverse("reviews:list"))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Approved one")
        self.assertNotContains(resp, "Pending one")


class ReviewCreateTests(TestCase):
    def test_login_required(self):
        resp = self.client.get(reverse("reviews:create"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts:login"), resp["Location"])

    def test_new_review_starts_unapproved_and_is_attributed_to_the_poster(self):
        user = make_user("bob")
        self.client.force_login(user)

        resp = self.client.post(
            reverse("reviews:create"),
            {
                "rating": 4,
                "headline": "Nice job",
                "body": "Tidy and quick.",
            },
        )

        self.assertRedirects(resp, reverse("reviews:list"))
        review = Review.objects.get()
        self.assertEqual(review.author, user)
        self.assertFalse(review.is_approved)


class ReviewUpdateTests(TestCase):
    def test_author_can_edit_and_it_returns_to_moderation(self):
        user = make_user("carol")
        review = make_review(user, is_approved=True)
        self.client.force_login(user)

        resp = self.client.post(
            reverse("reviews:update", kwargs={"slug": review.slug}),
            {"rating": 3, "headline": "Edited", "body": "Updated text."},
        )

        self.assertRedirects(resp, reverse("reviews:list"))
        review.refresh_from_db()
        self.assertEqual(review.headline, "Edited")
        self.assertFalse(review.is_approved)

    def test_other_user_cannot_edit_someone_elses_review(self):
        owner = make_user("dave")
        intruder = make_user("erin")
        review = make_review(owner)
        self.client.force_login(intruder)

        resp = self.client.post(
            reverse("reviews:update", kwargs={"slug": review.slug}),
            {"rating": 1, "headline": "Hacked", "body": "nope"},
        )

        self.assertEqual(resp.status_code, 404)
        review.refresh_from_db()
        self.assertNotEqual(review.headline, "Hacked")


class ReviewDeleteTests(TestCase):
    def test_author_can_delete_their_own_review(self):
        user = make_user("frank")
        review = make_review(user)
        self.client.force_login(user)

        resp = self.client.post(
            reverse("reviews:delete", kwargs={"slug": review.slug})
        )

        self.assertRedirects(resp, reverse("reviews:list"))
        self.assertFalse(Review.objects.filter(pk=review.pk).exists())

    def test_stranger_cannot_delete_a_review(self):
        owner = make_user("grace")
        stranger = make_user("heidi")
        review = make_review(owner)
        self.client.force_login(stranger)

        resp = self.client.post(
            reverse("reviews:delete", kwargs={"slug": review.slug})
        )

        self.assertRedirects(resp, reverse("reviews:list"))
        self.assertTrue(Review.objects.filter(pk=review.pk).exists())

    def test_site_administrator_can_delete_any_review(self):
        owner = make_user("ivan")
        admin = make_user("judy")
        admin.groups.add(Group.objects.get_or_create(name="Site Administrators")[0])
        review = make_review(owner)
        self.client.force_login(admin)

        resp = self.client.post(
            reverse("reviews:delete", kwargs={"slug": review.slug})
        )

        self.assertRedirects(resp, reverse("reviews:list"))
        self.assertFalse(Review.objects.filter(pk=review.pk).exists())

    def test_superuser_can_delete_any_review(self):
        owner = make_user("ken")
        root = make_user("root", is_superuser=True, is_staff=True)
        review = make_review(owner)
        self.client.force_login(root)

        resp = self.client.post(
            reverse("reviews:delete", kwargs={"slug": review.slug})
        )

        self.assertRedirects(resp, reverse("reviews:list"))
        self.assertFalse(Review.objects.filter(pk=review.pk).exists())
