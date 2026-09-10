"""Build a downloadable PDF for a bookings `Invoice`.

`render_invoice_pdf(invoice)` returns the PDF as bytes. Money values come
from the invoice's own snapshot fields and its line items, so a file
downloaded today keeps saying the same thing next month.
"""

import datetime as dt
import logging
import urllib.request
from decimal import Decimal
from io import BytesIO

logger = logging.getLogger(__name__)

BUSINESS_NAME = "J-Noon Flooring Specialist"

# The company logo (same asset as the site footer), forced to PNG for reportlab.
LOGO_URL = (
    "https://res.cloudinary.com/ddmslr9na/image/upload/"
    "f_png,q_auto,h_240/v1788896276/"
    "ChatGPT_Image_Sep_8_2026_08_34_05_PM-_ycy2tz.webp"
)

# Fetched once per process; a failure is not cached so it retries next time.
_LOGO_CACHE = {}


def _logo_data():
    if "data" in _LOGO_CACHE:
        return _LOGO_CACHE["data"]
    try:
        request = urllib.request.Request(
            LOGO_URL, headers={"User-Agent": "jnoon-flooring-invoices"}
        )
        with urllib.request.urlopen(request, timeout=6) as resp:
            data = resp.read()
    except Exception:
        logger.warning("Invoice logo fetch failed", exc_info=True)
        return None
    _LOGO_CACHE["data"] = data or None
    return _LOGO_CACHE["data"]


def _logo_flowable():
    data = _logo_data()
    if not data:
        return None
    try:
        from reportlab.lib.units import mm
        from reportlab.lib.utils import ImageReader
        from reportlab.platypus import Image

        iw, ih = ImageReader(BytesIO(data)).getSize()
        height = 22 * mm
        width = iw * height / ih
        if width > 46 * mm:
            width = 46 * mm
            height = ih * width / iw
        return Image(BytesIO(data), width=width, height=height)
    except Exception:
        logger.warning("Invoice logo could not be rendered", exc_info=True)
        return None


def _business_lines():
    """Contact lines for the invoice header, from the Contact us settings."""
    lines = []
    try:
        from contact.models import SiteContact

        c = SiteContact.load()
        if c.phone:
            lines.append(f"Tel: {c.phone}")
        if c.email:
            lines.append(c.email)
        if c.service_area:
            lines.append(f"Covering {c.service_area.split(',')[0]} and surrounding areas")
    except Exception:  # contact app missing / no row / db not ready
        pass
    return [ln for ln in lines if ln]


def _money(value):
    return f"£{(value or Decimal('0.00')):,.2f}"


def _fmt_date(iso):
    try:
        return dt.date.fromisoformat(iso).strftime("%d %b %Y")
    except (TypeError, ValueError):
        return iso or ""


def render_invoice_pdf(invoice):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )

    job = invoice.job
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"{invoice.number} - {BUSINESS_NAME}",
    )

    styles = getSampleStyleSheet()
    brown = colors.HexColor("#5a3b28")
    accent = colors.HexColor("#c8a27c")
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=brown, fontSize=20,
                        alignment=0, spaceAfter=2)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=9,
                           textColor=colors.HexColor("#555555"), leading=13)
    label = ParagraphStyle("label", parent=styles["Normal"], fontSize=8,
                           textColor=colors.HexColor("#8a6b4f"), spaceAfter=1)
    body = styles["Normal"]
    cell = ParagraphStyle("cell", parent=body, fontSize=9.5, leading=13)
    cell_r = ParagraphStyle("cell_r", parent=cell, alignment=2)  # right

    doc_title = {
        invoice.Kind.DEPOSIT: "Booking fee receipt",
        invoice.Kind.FINAL: "Invoice",
    }.get(invoice.kind, "Invoice")

    # ---- letterhead: name + contact on the left, logo on the right --------
    name_block = [Paragraph(BUSINESS_NAME, h1)]
    lines = _business_lines()
    if lines:
        name_block.append(Paragraph("<br/>".join(lines), small))

    logo = _logo_flowable()
    if logo is not None:
        header = Table([[name_block, logo]],
                       colWidths=[doc.width - 48 * mm, 48 * mm])
        header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story = [header, Spacer(1, 9 * mm)]
    else:
        story = name_block + [Spacer(1, 9 * mm)]

    # ---- who / what / when ----------------------------------------------
    meta = [
        [Paragraph("DOCUMENT", label), Paragraph(f"{doc_title} {invoice.number}", body)],
        [Paragraph("DATE", label), Paragraph(invoice.issued_on.strftime("%d %B %Y"), body)],
        [Paragraph("JOB", label), Paragraph(f"{job.reference} - {job.title}", body)],
        [Paragraph("CUSTOMER", label),
         Paragraph(job.contact_name or job.user.get_username(), body)],
    ]
    if job.site_address:
        meta.append([Paragraph("SITE", label), Paragraph(job.site_address, body)])
    meta_table = Table(meta, colWidths=[30 * mm, doc.width - 30 * mm])
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    story += [meta_table, Spacer(1, 7 * mm)]

    if job.summary:
        story += [Paragraph("Work", label), Paragraph(job.summary, body),
                  Spacer(1, 5 * mm)]

    # ---- itemised table -------------------------------------------------
    line_items = list(invoice.line_items.all())
    if not line_items:  # defensive - issuing always creates one
        line_items = [type("L", (), {
            "description": f"{job.title} - flooring work as agreed",
            "amount": invoice.agreed_total,
        })()]

    subtotal = sum((li.amount for li in line_items), Decimal("0.00"))
    total_paid = invoice.total_paid or Decimal("0.00")
    balance = subtotal - total_paid

    rows = [[Paragraph("<b>Description</b>", cell), Paragraph("<b>Amount</b>", cell_r)]]
    for li in line_items:
        rows.append([Paragraph(li.description, cell),
                     Paragraph(_money(li.amount), cell_r)])

    subtotal_row = len(rows)
    rows.append([Paragraph("<b>Subtotal</b>", cell),
                 Paragraph("<b>%s</b>" % _money(subtotal), cell_r)])

    for pay in invoice.payments_snapshot:
        amount = Decimal(str(pay.get("amount", "0")))
        desc = "%s received %s" % (pay.get("label", "Payment"),
                                   _fmt_date(pay.get("date")))
        method = pay.get("method")
        if method:
            desc += " (%s)" % method
        rows.append([Paragraph(desc, cell),
                     Paragraph("- " + _money(amount), cell_r)])

    if invoice.kind == invoice.Kind.FINAL and balance > 0:
        balance_label = "Balance due"
    else:
        balance_label = "Balance"
    rows.append([Paragraph("<b>%s</b>" % balance_label, cell),
                 Paragraph("<b>%s</b>" % _money(balance), cell_r)])

    table = Table(rows, colWidths=[doc.width - 32 * mm, 32 * mm])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#efe6da")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, accent),
        ("LINEABOVE", (0, subtotal_row), (-1, subtotal_row), 0.5, accent),
        ("LINEABOVE", (0, -1), (-1, -1), 1, brown),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    story += [table, Spacer(1, 6 * mm)]
    table.setStyle(TableStyle(style))

    if invoice.kind == invoice.Kind.DEPOSIT:
        totals_note = ("Thank you - your booking fee is paid and your booking is "
                       "secured. It's non-refundable and comes off your final invoice.")
    elif balance <= 0:
        totals_note = "Paid in full - thank you."
    else:
        totals_note = ("Please settle the balance once the work is complete, or as "
                       "otherwise agreed.")
    story.append(Paragraph(totals_note, small))

    if invoice.notes:
        story += [Spacer(1, 5 * mm), Paragraph("Notes", label),
                  Paragraph(invoice.notes, small)]

    story += [
        Spacer(1, 14 * mm),
        Paragraph(
            f"{BUSINESS_NAME}. This document was generated from your online "
            f"project portal on {invoice.issued_on.strftime('%d %B %Y')}.",
            small,
        ),
    ]

    doc.build(story)
    buf.seek(0)
    return buf.read()
