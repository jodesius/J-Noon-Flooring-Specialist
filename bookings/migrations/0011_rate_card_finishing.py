"""Add beading and door-trim charges to the rate card.

Beading £1 per linear metre; door trim / threshold bar £5 each. Inserted
ahead of the SUBFLOOR PREP section when that anchor is present, else
appended; skipped if a hand-edited version already mentions the marker.
"""

from django.db import migrations

MARKER = "FINISHING - BEADING"
ANCHOR = "SUBFLOOR PREP - add when the answers point to it:"

FINISHING_BLOCK = """\
FINISHING - BEADING & DOOR TRIMS (add when the floor type needs them - most
laminate / LVT / wood jobs do; carpet usually just needs door bars):
- Beading (scotia / quadrant) around the room perimeter: £1 per linear
  metre. If the customer hasn't given a perimeter, estimate it from the room
  sizes and say so in your assumptions.
- Door trim / threshold bar: £5 per doorway. If the customer hasn't said how
  many, assume one per room being done and say so.

"""


def add_finishing(apps, schema_editor):
    QuoteSettings = apps.get_model("bookings", "QuoteSettings")
    qs = QuoteSettings.objects.filter(pk=1).first()
    if not qs or MARKER in qs.rate_card:
        return
    card = qs.rate_card
    if ANCHOR in card:
        card = card.replace(ANCHOR, FINISHING_BLOCK + ANCHOR, 1)
    else:
        card = card.rstrip() + "\n\n" + FINISHING_BLOCK.rstrip() + "\n"
    qs.rate_card = card
    qs.save()


def remove_finishing(apps, schema_editor):
    QuoteSettings = apps.get_model("bookings", "QuoteSettings")
    qs = QuoteSettings.objects.filter(pk=1).first()
    if not qs or MARKER not in qs.rate_card:
        return
    qs.rate_card = qs.rate_card.replace(FINISHING_BLOCK, "", 1).replace(
        FINISHING_BLOCK.rstrip() + "\n", "", 1
    )
    qs.save()


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0010_cardpayment_invoice_alter_invoice_kind"),
    ]

    operations = [
        migrations.RunPython(add_finishing, remove_finishing),
    ]
