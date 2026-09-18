from django.db import models


class FAQItem(models.Model):
    """One question/answer on the FAQ page. Answers are plain text - a
    blank line starts a new paragraph, rendered via the `linebreaks`
    template filter, same as everywhere else in this project that shows
    admin-written free text."""

    class Category(models.TextChoices):
        SITE = "site", "Using this site"
        MEASURING = "measuring", "Measuring your room"
        LAMINATE = "laminate", "Laminate"
        LVT = "lvt", "LVT"
        AMTICO = "amtico", "Amtico"
        WOOD = "wood", "Engineered & solid wood"
        VINYL = "vinyl", "Vinyl"
        CARPET = "carpet", "Carpet & carpet tiles"
        SCREEDING = "screeding", "Screeding & floor prep"

    category = models.CharField(max_length=12, choices=Category.choices)
    question = models.CharField(max_length=200)
    answer = models.TextField()
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "sort_order", "id"]

    def __str__(self):
        return f"{self.get_category_display()}: {self.question}"
