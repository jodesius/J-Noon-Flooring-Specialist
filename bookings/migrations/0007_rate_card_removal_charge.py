"""Add a flat £50 "lift the old flooring" charge to the rate card, plus a
note that the customer supplies the bins for the waste.

Inserts the block ahead of the SUBFLOOR PREP section when that anchor is
present; otherwise appends it. Skips entirely if the block (or a hand-edited
version mentioning the marker) is already there, so it never clobbers
Joseph's own edits.
"""

from django.db import migrations

MARKER = "LIFTING / REMOVING OLD FLOORING"
ANCHOR = "SUBFLOOR PREP - add when the answers point to it:"

REMOVAL_BLOCK = """\
LIFTING / REMOVING OLD FLOORING:
- Lifting up the old flooring (carpet, laminate, vinyl, wood, etc.) ready
  for the new floor: a flat £50 per job. Add this whenever the customer
  wants the old flooring taken up (they answered "Yes, all of it" or "Some
  of it" to lifting the old flooring).
- This covers lifting and bagging up only - we do NOT take the waste away.
  Whenever removal is included you MUST tell the customer in
  customer_message that they need to provide their own skip or bins for the
  old flooring and offcuts.
- Firmly stuck-down floors (bonded parquet, bitumen, large areas of adhesive
  residue) can need grinding back on top - see SUBFLOOR PREP, and refer to a
  call if the answers point to a glued floor over a big area.

"""


def add_removal_charge(apps, schema_editor):
    QuoteSettings = apps.get_model("bookings", "QuoteSettings")
    qs = QuoteSettings.objects.filter(pk=1).first()
    if not qs or MARKER in qs.rate_card:
        return
    card = qs.rate_card
    if ANCHOR in card:
        card = card.replace(ANCHOR, REMOVAL_BLOCK + ANCHOR, 1)
    else:
        card = card.rstrip() + "\n\n" + REMOVAL_BLOCK.rstrip() + "\n"
    qs.rate_card = card
    qs.save()


def remove_removal_charge(apps, schema_editor):
    QuoteSettings = apps.get_model("bookings", "QuoteSettings")
    qs = QuoteSettings.objects.filter(pk=1).first()
    if not qs or MARKER not in qs.rate_card:
        return
    qs.rate_card = qs.rate_card.replace(REMOVAL_BLOCK, "", 1).replace(
        REMOVAL_BLOCK.rstrip() + "\n", "", 1
    )
    qs.save()


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0006_remove_job_booking_fee_alter_job_agreed_price"),
    ]

    operations = [
        migrations.RunPython(add_removal_charge, remove_removal_charge),
    ]
