"""Seed the FAQ page's starting content - a first draft for the business
owner to review and correct before/after it goes live, not gospel. Uses
get_or_create keyed on (category, question) so re-running this migration
(e.g. after a squash) never duplicates rows."""

from django.db import migrations

# (category, question, answer) - order here is the order they'll appear
# within each category (sort_order = index within its own category).
ITEMS = [
    # -- Using this site ---------------------------------------------------
    ("site", "How do I book a job?",
     "Head to Book a job from the menu, tell me the address and a bit "
     "about what you need doing, and send it over. There's no charge for "
     "this - I'll look it over, confirm the price and a start date with "
     "you, and then you can secure the booking. If you've already had an "
     "online quote, paste its reference (e.g. JQ0007) and I'll bring your "
     "answers across so you don't have to type them twice."),
    ("site", "How do I get a call back?",
     "If you'd rather talk it through first, use Book a call from the "
     "menu, leave your number and a good time, and I'll ring you back."),
    ("site", "How does the booking fee work?",
     "Once we've agreed a price and start date, there's a booking fee of "
     "20% of the agreed price to secure your slot. It's non-refundable, "
     "but it comes straight off your final invoice - it's part of what "
     "you're paying for the job, not on top of it."),
    ("site", "How do I pay the balance?",
     "From your project page you can pay the full balance, or a "
     "part-payment of any amount up to what's outstanding - come back and "
     "pay more whenever suits you. Card payments are handled by Stripe; "
     "your card details never touch our servers."),
    ("site", "How do refunds work? What's the difference between a "
     "Credit refund and a Cash / Bank refund?",
     "If something needs putting right, get in touch and I'll agree it "
     "with you first. A Credit refund is a book entry - it comes off "
     "what's outstanding on the job, no money changes hands yet. A Cash, "
     "Bank transfer or Cheque refund means real money has actually been "
     "handed back to you - if I already owe you something, that payment "
     "settles what's owed rather than adding to it. Either way, you'll "
     "see it reflected on your project page and on the invoice."),
    ("site", "What happens after I request a quote?",
     "You'll get an instant estimate range based on what you tell me - "
     "it's a rough guide, not a fixed price. If you'd like to go ahead, "
     "book the job (pasting the quote reference saves retyping "
     "everything) and I'll confirm the exact price and a start date with "
     "you before anything's charged."),
    ("site", "Is my payment information safe?",
     "Yes - card payments go through Stripe, a PCI-compliant payment "
     "processor. Your card details are entered directly into Stripe's own "
     "secure fields and never pass through or get stored on our servers."),
    ("site", "Where do I find my invoices?",
     "On your project page, under Invoices. You'll get a proper PDF for "
     "the booking fee, any part-payments, the final invoice, and any "
     "refund - each one itemised, dated and downloadable any time."),
    ("site", "Can I message you about my job?",
     "Yes - once your booking fee's paid, a Messages thread opens on your "
     "project page. Use it for questions, updates, or to send a photo - "
     "I'll get an email whenever you post."),

    # -- Measuring your room -----------------------------------------------
    ("measuring", "How do I measure a room for flooring?",
     "Measure the room's length and width in metres at the longest "
     "points, and multiply them together for the area in square metres. "
     "For an L-shaped or awkward room, split it into two or more simple "
     "rectangles, measure each one, and add the areas together."),
    ("measuring", "Do I need to allow extra for wastage?",
     "Yes - I'd always add around 10% on top of the bare floor area, more "
     "for patterned products like herringbone or a diagonal lay, to cover "
     "cutting, trims and any mistakes. It's much cheaper to order a bit "
     "extra up front than to run short mid-job and wait on a second "
     "delivery."),
    ("measuring", "What if my room isn't a simple rectangle?",
     "Break it down into rectangles - a bay window, a chimney breast "
     "recess, an opening into a hallway - measure each section on its own "
     "and add them together. If it's a genuinely awkward shape, don't "
     "worry about getting it perfect; I'll always do my own exact "
     "measure-up before ordering materials."),
    ("measuring", "Do you come and measure it for me?",
     "Yes - once we've agreed to go ahead, I'll come out and take proper "
     "measurements myself before ordering anything, so what gets ordered "
     "matches the room exactly."),

    # -- Laminate ------------------------------------------------------------
    ("laminate", "What is laminate flooring?",
     "A hard-wearing floating floor - a printed image layer under a tough "
     "wear layer, over a fibreboard core, click-fitted together in "
     "planks. It's one of the most budget-friendly ways to get a "
     "wood-look floor."),
    ("laminate", "What's a damp-proof membrane (DPM) and do I need one?",
     "A DPM is a thin plastic sheet laid under the underlay to stop "
     "moisture rising up from the subfloor into the laminate. I fit one "
     "on solid (concrete) subfloors as standard - timber subfloors "
     "usually don't need it, since they're not a moisture source in the "
     "same way."),
    ("laminate", "Do I need underlay under laminate?",
     "Yes - it cushions the floor underfoot, helps deaden sound, and "
     "evens out very minor imperfections in the subfloor. It's laid "
     "loose under the laminate, not fixed down."),
    ("laminate", "What's an expansion gap, and why does it matter?",
     "Laminate expands and contracts slightly with changes in "
     "temperature and humidity. Leaving a small gap (usually 8-10mm) "
     "around the edge of the room stops the floor pushing against the "
     "walls and buckling. Beading covers that gap so it's invisible once "
     "fitted."),
    ("laminate", "What is beading, and do I need it?",
     "Beading is the slim trim fitted around the room's edge to hide the "
     "expansion gap between the laminate and the skirting board or wall. "
     "I'd always recommend it - without it, that gap is left on show, and "
     "it's the neatest way to finish the edge properly."),
    ("laminate", "How long does a laminate floor take to fit?",
     "Depends on the room size and how much prep the subfloor needs, but "
     "a straightforward single room is often a one-day job. I'll give "
     "you a proper time estimate once I've seen the room."),

    # -- LVT ------------------------------------------------------------------
    ("lvt", "What is LVT?",
     "Luxury Vinyl Tile - a resilient, waterproof floor covering that "
     "comes in realistic wood- and stone-look finishes. It's glued down "
     "flat to the subfloor rather than floating, so it feels solid "
     "underfoot."),
    ("lvt", "Does LVT need underlay?",
     "No - LVT is bonded directly to a smooth, prepared subfloor. What "
     "matters far more than underlay is the subfloor prep - it needs to "
     "be flat and smooth, since LVT will show up every bump or dip "
     "underneath it."),
    ("lvt", "What is mastic, and why does LVT need it?",
     "Mastic is a flexible sealant used to finish the edge where the LVT "
     "meets a wall, doorway or another floor covering - it gives a neat, "
     "waterproof finish and allows for the tiny amount of movement floors "
     "naturally have, without cracking like a rigid filler would."),
    ("lvt", "What subfloor prep does LVT need?",
     "The subfloor gets skimmed with a smoothing compound to give a flat, "
     "smooth base - any lumps, dips or old adhesive residue will show "
     "through a floor this thin, so this step matters more than with "
     "most other floor types."),
    ("lvt", "Is LVT waterproof?",
     "Yes - that's one of its main advantages over laminate or wood, "
     "which is why it's such a popular choice for kitchens and "
     "bathrooms."),

    # -- Amtico ---------------------------------------------------------------
    ("amtico", "What is Amtico, and how's it different from standard LVT?",
     "Amtico is a premium LVT brand, with a wider choice of finishes and "
     "the option of bespoke patterns, borders and inlays. The fitting "
     "process is similar to standard LVT, just with more attention paid "
     "to design and setting-out, and it's moisture-tested first to make "
     "sure the subfloor's within Amtico's own tolerances."),
    ("amtico", "Can Amtico have a border or pattern?",
     "Yes - that's one of the main reasons people choose it. I mark out "
     "the laying pattern, any borders and bespoke inlays before fitting, "
     "so it's worth deciding on the design early, before I order the "
     "materials."),
    ("amtico", "What subfloor prep does Amtico need?",
     "Same principle as standard LVT - a smoothing compound feathered to "
     "a flat, primed finish - plus a moisture test first, since Amtico "
     "has its own stricter tolerance for subfloor moisture than cheaper "
     "LVT products."),

    # -- Engineered & solid wood ---------------------------------------------
    ("wood", "What's the difference between engineered and solid wood "
     "flooring?",
     "Solid wood is exactly that - one solid piece of timber through its "
     "full thickness. Engineered wood has a real wood veneer on top "
     "bonded to layers of plywood underneath, which makes it more stable "
     "and better suited to a wider range of subfloors, including with "
     "underfloor heating."),
    ("wood", "Does wood flooring need to acclimatise before fitting?",
     "Yes - the boards need to sit in the room for a period beforehand to "
     "adjust to the room's temperature and humidity. Skipping this is one "
     "of the most common causes of gaps or movement in a wood floor after "
     "fitting."),
    ("wood", "Can solid wood go over underfloor heating?",
     "Generally engineered wood is the safer choice over underfloor "
     "heating - it's more dimensionally stable. Solid wood can move more "
     "with the heat cycling on and off, so I'd talk this through with you "
     "before recommending it in that situation."),
    ("wood", "What's the difference between secret-nailing, gluing and "
     "floating?",
     "Secret-nailing fixes solid boards down through their tongue so no "
     "nails show. Gluing bonds the boards to the subfloor - common for "
     "engineered boards over a solid subfloor. Floating means the boards "
     "click together and sit on an underlay without being fixed down at "
     "all, similar to laminate. Which one's right depends on the product "
     "and the subfloor."),

    # -- Vinyl ----------------------------------------------------------------
    ("vinyl", "What's the difference between sheet vinyl and LVT?",
     "Sheet vinyl comes in large rolls and is welded or sealed at the "
     "seams for a fully waterproof finish - it's the practical choice for "
     "a wet room, bathroom or utility. LVT comes in individual planks or "
     "tiles and gives more of a premium, wood-plank look."),
    ("vinyl", "Why does vinyl need mastic or sealant at the edges?",
     "The edges where vinyl meets a wall, door bar or another floor need "
     "sealing so water can't get underneath - that's what keeps a wet "
     "room genuinely waterproof, not just water-resistant."),
    ("vinyl", "Where is vinyl best used?",
     "Anywhere fully waterproof flooring matters most - kitchens, "
     "bathrooms, utility rooms - since the sheet and its welded seams "
     "give a genuinely sealed floor."),

    # -- Carpet & carpet tiles ------------------------------------------------
    ("carpet", "What is gripper rod?",
     "A thin batten with angled pins, fixed around the edge of the room "
     "against the skirting. The carpet is stretched onto those pins to "
     "hold it taut and in place, without needing to be glued down."),
    ("carpet", "What is carpet underlay, and why does it matter?",
     "It's the cushioning layer laid down before the carpet, and it makes "
     "a bigger difference than people expect - it affects how the carpet "
     "feels underfoot, how long it lasts, and how well it insulates sound "
     "and heat. A good underlay is worth the money."),
    ("carpet", "What are door bars, and do I need them?",
     "A door bar is a trim strip fitted in a doorway to neatly finish the "
     "edge where carpet meets another floor covering, and to stop the "
     "carpet fraying or lifting at that edge over time. I'd fit one at "
     "any doorway where the flooring changes."),
    ("carpet", "What's the difference between carpet and carpet tiles?",
     "Broadloom carpet comes in one continuous roll and is stretched "
     "wall-to-wall over gripper rods - the usual choice for a living room "
     "or bedroom. Carpet tiles are laid individually, usually in a brick "
     "or quarter-turn pattern, and are more common in hard-wearing or "
     "commercial-style spaces since a damaged tile can be replaced on its "
     "own."),
    ("carpet", "How is carpet actually fitted?",
     "For broadloom, I fit the gripper rods and door bars, lay and join "
     "the underlay, then roll out the carpet, cut it in and power-stretch "
     "it onto the grippers so it sits taut with no wrinkles. Carpet tiles "
     "are set out from the centre of the room and laid to a brick or "
     "quarter-turn pattern instead."),

    # -- Screeding & floor prep ----------------------------------------------
    ("screeding", "What is screeding?",
     "Screeding is levelling and preparing the subfloor so whatever goes "
     "on top of it - laminate, LVT, carpet, wood - has a flat, sound, "
     "even base. It's the groundwork that every other floor depends on."),
    ("screeding", "How is screed laid?",
     "I start with a survey of the existing floor - moisture readings, "
     "checking it's structurally sound, and a level check. Then I strip "
     "out any old flooring and adhesive residue, repair or fill any major "
     "defects, prime the surface, and apply either a latex smoothing "
     "compound or a flow screed depending on how much levelling is "
     "needed."),
    ("screeding", "What's the difference between screed and smoothing "
     "compound?",
     "They do a similar job but at different scales. A latex smoothing "
     "compound is a thinner layer for fine-levelling a floor that's "
     "already reasonably flat. A flow screed handles bigger dips and more "
     "serious levelling, laid thicker."),
    ("screeding", "How long does screed take to dry?",
     "It depends on the product, the thickness, and conditions in the "
     "room. As a general guide, a latex smoothing compound is often "
     "walkable within a few hours and ready for flooring the next day, "
     "while a full flow screed can need considerably longer, especially "
     "if it's laid thick - always allow extra time on a bigger job. I'll "
     "give you an accurate drying time for your specific job before we "
     "start."),
    ("screeding", "My floor already looks flat - do I still need "
     "screeding?",
     "Not always, but it's worth checking - some dips and unevenness are "
     "only obvious once you kneel down and sight along the floor, or they "
     "only cause a problem with certain flooring types (LVT and Amtico "
     "show up far more than carpet, for instance). I'll always check the "
     "subfloor properly before recommending whether it needs it."),
]


def seed_faq_items(apps, schema_editor):
    FAQItem = apps.get_model("core", "FAQItem")
    counters = {}
    for category, question, answer in ITEMS:
        sort_order = counters.get(category, 0)
        counters[category] = sort_order + 1
        FAQItem.objects.get_or_create(
            category=category, question=question,
            defaults={"answer": answer, "sort_order": sort_order},
        )


def unseed_faq_items(apps, schema_editor):
    FAQItem = apps.get_model("core", "FAQItem")
    questions = [question for _, question, _ in ITEMS]
    FAQItem.objects.filter(question__in=questions).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_faq_items, unseed_faq_items),
    ]
