"""Add a mastic edge-sealant charge to the rate card, for LVT/vinyl jobs
that need a sealed edge (bathrooms, kitchens, wet areas - see the FAQ's
"What is mastic" entries).

£1 per linear metre, same rate and same "estimate from room size if not
given" pattern as the existing beading charge. Inserted ahead of the
SUBFLOOR PREP section when that anchor is present, else appended; skipped
if a hand-edited version already mentions the marker.
"""

from django.db import migrations

MARKER = "MASTIC EDGE SEALANT"
ANCHOR = "SUBFLOOR PREP - add when the answers point to it:"

MASTIC_BLOCK = """\
MASTIC EDGE SEALANT (add for LVT / vinyl jobs where the edge needs
sealing - bathrooms, kitchens, utility rooms and other wet areas; not
needed for carpet, laminate or wood):
- Mastic sealant where LVT or vinyl meets a wall, door bar or another
  floor covering, around the room perimeter: £1 per linear metre. If the
  customer hasn't given a perimeter, estimate it from the room sizes and
  say so in your assumptions.

"""


def add_mastic(apps, schema_editor):
    QuoteSettings = apps.get_model("bookings", "QuoteSettings")
    qs = QuoteSettings.objects.filter(pk=1).first()
    if not qs or MARKER in qs.rate_card:
        return
    card = qs.rate_card
    if ANCHOR in card:
        card = card.replace(ANCHOR, MASTIC_BLOCK + ANCHOR, 1)
    else:
        card = card.rstrip() + "\n\n" + MASTIC_BLOCK.rstrip() + "\n"
    qs.rate_card = card
    qs.save()


def remove_mastic(apps, schema_editor):
    QuoteSettings = apps.get_model("bookings", "QuoteSettings")
    qs = QuoteSettings.objects.filter(pk=1).first()
    if not qs or MARKER not in qs.rate_card:
        return
    qs.rate_card = qs.rate_card.replace(MASTIC_BLOCK, "", 1).replace(
        MASTIC_BLOCK.rstrip() + "\n", "", 1
    )
    qs.save()


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0020_job_duration_days"),
    ]

    operations = [
        migrations.RunPython(add_mastic, remove_mastic),
    ]
