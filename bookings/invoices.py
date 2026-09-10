"""Build a downloadable PDF for a bookings `Invoice`.

`render_invoice_pdf(invoice)` returns the PDF as bytes. Money values come
from the invoice's own snapshot fields, so a file downloaded today keeps
saying the same thing next month.
"""

from decimal import Decimal
from io import BytesIO

BUSINESS_NAME = "J-Noon Flooring Specialist"


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
    value = value or Decimal("0.00")
    return f"£{value:,.2f}"


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
        topMargin=20 * mm, bottomMargin=20 * mm,
        title=f"{invoice.number} - {BUSINESS_NAME}",
    )

    styles = getSampleStyleSheet()
    brown = colors.HexColor("#5a3b28")
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=brown, fontSize=20,
                        alignment=0, spaceAfter=2)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=9,
                           textColor=colors.HexColor("#555555"), leading=13)
    label = ParagraphStyle("label", parent=styles["Normal"], fontSize=8,
                           textColor=colors.HexColor("#8a6b4f"), spaceAfter=1)
    body = styles["Normal"]

    doc_title = {
        invoice.Kind.DEPOSIT: "Booking fee receipt",
        invoice.Kind.FINAL: "Invoice",
    }.get(invoice.kind, "Invoice")

    story = [
        Paragraph(BUSINESS_NAME, h1),
        Paragraph("<br/>".join(_business_lines()), small),
        Spacer(1, 10 * mm),
    ]

    meta = [
        [Paragraph("DOCUMENT", label), Paragraph(f"{doc_title} {invoice.number}", body)],
        [Paragraph("DATE", label), Paragraph(invoice.issued_on.strftime("%d %B %Y"), body)],
        [Paragraph("JOB", label), Paragraph(f"{job.reference} - {job.title}", body)],
        [Paragraph("CUSTOMER", label),
         Paragraph(job.contact_name or job.user.get_username(), body)],
    ]
    if job.site_address:
        meta.append([Paragraph("SITE", label), Paragraph(job.site_address, body)])
    meta_table = Table(meta, colWidths=[30 * mm, 130 * mm])
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    story += [meta_table, Spacer(1, 8 * mm)]

    if job.summary:
        story += [Paragraph("Work", label), Paragraph(job.summary, body),
                  Spacer(1, 6 * mm)]

    rows = [["Description", "Amount"]]
    if invoice.kind == invoice.Kind.DEPOSIT:
        rows.append(["Non-refundable booking fee (deducted from the final balance)",
                     _money(invoice.total_paid)])
        rows.append(["Received", _money(invoice.total_paid)])
        totals_note = "Thank you - your booking is secured."
    else:
        rows.append(["Agreed price for the work", _money(invoice.agreed_total)])
        rows.append(["Less payments received (inc. booking fee)",
                     "-" + _money(invoice.total_paid)])
        rows.append(["Balance due", _money(invoice.balance)])
        totals_note = (
            "Balance settled - thank you." if invoice.balance <= 0
            else "Please settle the balance once the work is complete, "
                 "or as otherwise agreed."
        )

    money_table = Table(rows, colWidths=[125 * mm, 35 * mm])
    money_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#efe6da")),
        ("TEXTCOLOR", (0, 0), (-1, 0), brown),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#c8a27c")),
        ("LINEBELOW", (0, -1), (-1, -1), 0.75, brown),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [money_table, Spacer(1, 6 * mm), Paragraph(totals_note, small)]

    if invoice.notes:
        story += [Spacer(1, 6 * mm), Paragraph("Notes", label),
                  Paragraph(invoice.notes, small)]

    story += [
        Spacer(1, 16 * mm),
        Paragraph(
            f"{BUSINESS_NAME}. This document was generated from your online "
            f"project portal on {invoice.issued_on.strftime('%d %B %Y')}.",
            small,
        ),
    ]

    doc.build(story)
    buf.seek(0)
    return buf.read()
