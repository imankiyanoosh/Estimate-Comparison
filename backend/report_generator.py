from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import os

BRAND_BLUE = colors.HexColor("#1e40af")
BRAND_RED = colors.HexColor("#dc2626")
BRAND_GREEN = colors.HexColor("#16a34a")
BRAND_ORANGE = colors.HexColor("#ea580c")
BRAND_YELLOW = colors.HexColor("#ca8a04")
LIGHT_GRAY = colors.HexColor("#f3f4f6")
MEDIUM_GRAY = colors.HexColor("#6b7280")


def fmt_money(v):
    if v is None:
        return "-"
    return f"${v:,.2f}"


def fmt_pct(v):
    if v is None:
        return "-"
    return f"{v:.1f}%"


def state_color(state: str):
    return {
        "exact_match": BRAND_GREEN,
        "qty_diff": BRAND_YELLOW,
        "price_diff": BRAND_ORANGE,
        "scope_diff": BRAND_ORANGE,
        "missing_from_carrier": BRAND_RED,
        "only_in_carrier": MEDIUM_GRAY,
        "unresolved": MEDIUM_GRAY,
    }.get(state, colors.black)


def generate_pdf_report(report_data: dict, output_path: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(letter),
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=20, textColor=BRAND_BLUE, spaceAfter=6)
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=14, textColor=BRAND_BLUE, spaceAfter=4)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11, textColor=BRAND_BLUE, spaceAfter=4)
    normal = styles["Normal"]
    small = ParagraphStyle("Small", parent=normal, fontSize=8)
    small_bold = ParagraphStyle("SmallBold", parent=small, fontName="Helvetica-Bold")
    center = ParagraphStyle("Center", parent=normal, alignment=TA_CENTER)

    story = []

    # ---- Cover Page ----
    job = report_data.get("job", {})
    carrier_est = report_data.get("carrier_estimate") or {}
    pa_est = report_data.get("pa_estimate") or {}
    exec_s = report_data.get("executive_summary", {})

    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("Xactimate Estimate Reconciliation Report", title_style))
    story.append(HRFlowable(width="100%", thickness=2, color=BRAND_BLUE))
    story.append(Spacer(1, 0.2 * inch))

    meta_data = [
        ["Carrier Estimate File:", job.get("carrier_filename", "-"), "PA Estimate File:", job.get("pa_filename", "-")],
        ["Insured:", carrier_est.get("insured_name", "-"), "Claim #:", carrier_est.get("claim_number", "-")],
        ["Carrier Price List:", carrier_est.get("price_list_code", "-"), "PA Price List:", pa_est.get("price_list_code", "-")],
        ["Date:", carrier_est.get("date_entered", "-"), "PA Date:", pa_est.get("date_entered", "-")],
    ]
    meta_table = Table(meta_data, colWidths=[1.5 * inch, 3 * inch, 1.5 * inch, 3 * inch])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.25 * inch))

    # Price list warning
    if exec_s.get("price_list_warning"):
        story.append(Paragraph(
            "⚠ WARNING: The two estimates use different price lists. Some apparent differences may reflect pricing "
            "context rather than true scope disagreements.",
            ParagraphStyle("Warn", parent=normal, textColor=BRAND_RED, fontName="Helvetica-Bold", fontSize=9)
        ))
        story.append(Spacer(1, 0.1 * inch))

    # Executive Summary
    story.append(Paragraph("Executive Summary", h1))

    total_delta = exec_s.get("total_delta", 0)
    delta_color = BRAND_RED if total_delta > 0 else BRAND_GREEN

    summary_data = [
        ["Metric", "PA Estimate", "Carrier Estimate", "Delta"],
        ["Total RCV", fmt_money(exec_s.get("pa_total")), fmt_money(exec_s.get("carrier_total")), fmt_money(total_delta)],
        ["Matched Items", str(exec_s.get("matched_count", 0)), "", ""],
        ["Missing from Carrier", str(exec_s.get("missing_count", 0)), "", "supplement opportunity"],
        ["Only in Carrier", str(exec_s.get("only_in_carrier_count", 0)), "", ""],
        ["Qty Differences", str(exec_s.get("qty_diff_count", 0)), "", ""],
        ["Price Differences", str(exec_s.get("price_diff_count", 0)), "", ""],
        ["Unresolved", str(exec_s.get("unresolved_count", 0)), "", "needs review"],
    ]

    sum_table = Table(summary_data, colWidths=[2.5 * inch, 2 * inch, 2 * inch, 2 * inch])
    sum_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("TEXTCOLOR", (3, 1), (3, 1), delta_color),
        ("FONTNAME", (3, 1), (3, 1), "Helvetica-Bold"),
    ]))
    story.append(sum_table)
    story.append(PageBreak())

    # ---- Room Breakdown ----
    story.append(Paragraph("Room-by-Room Comparison", h1))
    room_data = [["Room", "PA RCV", "Carrier RCV", "Delta ($)", "Delta (%)", "PA Lines", "Carrier Lines", "Missing"]]
    for r in report_data.get("room_breakdown", []):
        c_rcv = r.get("carrier_rcv", 0)
        p_rcv = r.get("pa_rcv", 0)
        delta = r.get("rcv_delta", 0)
        pct = (delta / max(c_rcv, 0.01)) * 100 if c_rcv else 0
        room_data.append([
            r.get("room_name", ""),
            fmt_money(p_rcv), fmt_money(c_rcv), fmt_money(delta), fmt_pct(pct),
            str(r.get("line_count_pa", 0)), str(r.get("line_count_carrier", 0)),
            str(r.get("missing_count", 0)),
        ])

    if len(room_data) > 1:
        rt = Table(room_data, colWidths=[2 * inch, 1.2 * inch, 1.2 * inch, 1.2 * inch, 0.9 * inch, 0.8 * inch, 0.9 * inch, 0.8 * inch])
        rt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(rt)
    story.append(Spacer(1, 0.2 * inch))

    # ---- Category Breakdown ----
    story.append(Paragraph("Category Summary", h1))
    cat_data = [["Category Code", "Category Name", "PA RCV", "Carrier RCV", "Delta ($)", "Variance %", "Missing"]]
    for c in report_data.get("category_breakdown", []):
        cat_data.append([
            c.get("category_code", ""),
            c.get("category_name", ""),
            fmt_money(c.get("pa_rcv")), fmt_money(c.get("carrier_rcv")),
            fmt_money(c.get("rcv_delta")), fmt_pct(c.get("pct_variance")),
            str(c.get("missing_count", 0)),
        ])

    if len(cat_data) > 1:
        ct = Table(cat_data, colWidths=[1 * inch, 2.2 * inch, 1.2 * inch, 1.2 * inch, 1.2 * inch, 0.9 * inch, 0.8 * inch])
        ct.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(ct)
    story.append(PageBreak())

    # ---- Line Item Discrepancies ----
    story.append(Paragraph("Line-Item Discrepancies", h1))

    # Only non-exact matches
    discrepancies = [m for m in report_data.get("line_matches", []) if m["match_state"] != "exact_match"]
    if discrepancies:
        li_data = [["State", "PA Description", "PA Qty/Unit/Price/RCV", "Carrier Description", "Carrier Qty/Unit/Price/RCV", "RCV Delta"]]
        for m in discrepancies[:200]:  # cap for PDF size
            pa = m.get("pa_item") or {}
            ca = m.get("carrier_item") or {}
            state = m.get("match_state", "")
            pa_line = f"{pa.get('description_raw', '-')[:60]}" if pa else "-"
            ca_line = f"{ca.get('description_raw', '-')[:60]}" if ca else "-"
            pa_vals = f"{pa.get('qty','-')} {pa.get('unit','')} @ {fmt_money(pa.get('unit_price'))} = {fmt_money(pa.get('rcv'))}" if pa else "-"
            ca_vals = f"{ca.get('qty','-')} {ca.get('unit','')} @ {fmt_money(ca.get('unit_price'))} = {fmt_money(ca.get('rcv'))}" if ca else "-"

            li_data.append([
                state.replace("_", " ").title(),
                Paragraph(pa_line, small),
                Paragraph(pa_vals, small),
                Paragraph(ca_line, small),
                Paragraph(ca_vals, small),
                fmt_money(m.get("rcv_delta")),
            ])

        lit = Table(li_data, colWidths=[1 * inch, 2.2 * inch, 1.9 * inch, 2.2 * inch, 1.9 * inch, 0.8 * inch])
        lit.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(lit)
    else:
        story.append(Paragraph("All line items matched exactly.", normal))

    story.append(PageBreak())

    # ---- Financial Deltas ----
    story.append(Paragraph("Financial Deltas (Add-Ons & Totals)", h1))
    fin_data = [["Component", "PA Value", "Carrier Value", "Delta", "Notes"]]
    for fd in report_data.get("financial_deltas", []):
        kind = fd.get("kind", "").replace("_", " ").title()
        fin_data.append([
            kind,
            fmt_money(fd.get("pa_value")),
            fmt_money(fd.get("carrier_value")),
            fmt_money(fd.get("delta")),
            (fd.get("rationale") or "")[:80],
        ])

    if len(fin_data) > 1:
        ft = Table(fin_data, colWidths=[1.5 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch, 4 * inch])
        ft.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(ft)

    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(
        "This report was generated by the Xactimate Estimate Reconciliation System. "
        "All matches should be verified by a licensed public adjuster before use in claims negotiations.",
        ParagraphStyle("Footer", parent=small, textColor=MEDIUM_GRAY)
    ))

    doc.build(story)


def generate_csv_report(line_matches: list) -> str:
    """Generate CSV string from line matches."""
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "match_state", "match_type", "confidence",
        "pa_description", "pa_room", "pa_category", "pa_qty", "pa_unit", "pa_unit_price", "pa_rcv",
        "carrier_description", "carrier_room", "carrier_category", "carrier_qty", "carrier_unit",
        "carrier_unit_price", "carrier_rcv",
        "qty_delta", "unit_price_delta", "rcv_delta",
    ])

    for m in line_matches:
        pa = m.get("pa_item") or {}
        carrier = m.get("carrier_item") or {}
        writer.writerow([
            m.get("match_state", ""),
            m.get("match_type", ""),
            f"{m.get('confidence', 0):.3f}",
            pa.get("description_raw", ""),
            pa.get("room_name", ""),
            pa.get("category_code", ""),
            pa.get("qty", ""),
            pa.get("unit", ""),
            pa.get("unit_price", ""),
            pa.get("rcv", ""),
            carrier.get("description_raw", ""),
            carrier.get("room_name", ""),
            carrier.get("category_code", ""),
            carrier.get("qty", ""),
            carrier.get("unit", ""),
            carrier.get("unit_price", ""),
            carrier.get("rcv", ""),
            m.get("qty_delta", ""),
            m.get("unit_price_delta", ""),
            m.get("rcv_delta", ""),
        ])

    return output.getvalue()
