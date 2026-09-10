from django.db import migrations
from django.utils.text import slugify

# The flooring systems shown on the quote form (prices live in the rate card).
SYSTEMS = [
    "Carpet",
    "Carpet Tiles",
    "Laminate",
    "LVT",
    "Amtico",
    "Vinyl",
    "Engineered & Solid Wood",
    "Herringbone / Parquet / Chevron",
]

# Starter rate card - J-Noon's own prices. Edited in the admin afterwards.
RATE_CARD = """\
All rates are per square metre unless noted. Ranges mean "simple end -> harder
end"; use judgement for the room and access described.

LABOUR - straight-lay fitting only (materials are extra on supply & fit jobs):
- Carpet: £8
- Carpet tiles: £10
- Laminate: £10
- LVT click: £10
- LVT dryback (glue-down): £15
- Amtico: £18-£20
- Vinyl (sheet): £10-£12
- Engineered wood: £15-£22

LABOUR - herringbone / parquet / chevron, fitting only (pick the target rate;
move toward the higher figure for borders, awkward rooms, or lots of cuts):
- Engineered herringbone: £35-£40 target, up to £50 complex
- Solid wood herringbone: £45 target, up to £60 complex
- Traditional parquet blocks: £45-£50 target, up to £65 complex
- LVT herringbone: £30-£35 target, up to £45 complex
- Laminate herringbone: £30 target, up to £40 complex
- Chevron: £50-£60 target, £75+ complex
- Double herringbone: £50-£55 target, up to £75 complex

SUBFLOOR PREP - add when the answers point to it:
- Ply overlay: £10-£12
- Latex screed: £12-£15
- Ardex (standard): £15
- Ardex (feathering / build-up): £18-£25
- Screwing down loose floorboards: £5
- Replacing a damaged board: £15-£20 per board
- Grinding back old adhesive / screed: £10-£15
- Major subfloor repairs: charged at a day / hourly rate - refer to a call

MATERIALS (supply & fit): the customer's product choice sets the material cost
and there is no material price in this card. Quote the labour + prep you can,
and state clearly that materials are on top, to be confirmed once they've
chosen a product.
"""


def seed(apps, schema_editor):
    FlooringRate = apps.get_model("bookings", "FlooringRate")
    QuoteSettings = apps.get_model("bookings", "QuoteSettings")
    for order, name in enumerate(SYSTEMS, start=1):
        FlooringRate.objects.get_or_create(
            slug=slugify(name),
            defaults={"name": name, "sort_order": order},
        )
    QuoteSettings.objects.update_or_create(
        pk=1, defaults={"rate_card": RATE_CARD},
    )


def unseed(apps, schema_editor):
    FlooringRate = apps.get_model("bookings", "FlooringRate")
    FlooringRate.objects.filter(slug__in=[slugify(n) for n in SYSTEMS]).delete()


class Migration(migrations.Migration):

    dependencies = [("bookings", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
