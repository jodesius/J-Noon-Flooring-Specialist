from django.db import migrations
from django.utils.text import slugify

# Starter set of flooring types. Edit / add / remove these freely in the
# admin afterwards - nothing in the code depends on a specific category.
INITIAL_CATEGORIES = [
    "Laminate",
    "LVT",
    "Amtico",
    "Herringbone & Parquet",
    "Engineered Wood",
    "Vinyl",
    "Carpet",
    "Carpet Tiles",
]


def add_categories(apps, schema_editor):
    Category = apps.get_model("gallery", "Category")
    for order, name in enumerate(INITIAL_CATEGORIES, start=1):
        Category.objects.get_or_create(
            slug=slugify(name),
            defaults={"name": name, "sort_order": order},
        )


def remove_categories(apps, schema_editor):
    Category = apps.get_model("gallery", "Category")
    Category.objects.filter(
        slug__in=[slugify(n) for n in INITIAL_CATEGORIES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("gallery", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_categories, remove_categories),
    ]
