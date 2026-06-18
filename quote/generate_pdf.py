#!/usr/bin/env python3
"""
CTTX Quote PDF Generator
Usage: python3 generate_pdf.py <quote_json_file> [output_pdf]
"""

import json
import sys
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

# ── Brand colours ────────────────────────────────────────────────────────────
BRAND_DARK  = colors.HexColor("#1A2E4A")   # dark navy
BRAND_BLUE  = colors.HexColor("#2563EB")   # accent blue
BRAND_LIGHT = colors.HexColor("#F1F5F9")   # table stripe
WHITE       = colors.white
BLACK       = colors.HexColor("#1E293B")

W, H = A4


def money(val):
    try:
        return f"R {float(val):,.2f}"
    except Exception:
        return str(val)


def pct(val):
    try:
        return f"{float(val)*100:.1f}%"
    except Exception:
        return ""


def build_pdf(data: dict, output_path: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=14*mm, bottomMargin=14*mm,
    )

    styles = getSampleStyleSheet()

    def style(name, **kw):
        s = ParagraphStyle(name, **kw)
        return s

    S_title   = style("title",   fontName="Helvetica-Bold", fontSize=22, textColor=WHITE,    leading=26)
    S_sub     = style("sub",     fontName="Helvetica",      fontSize=9,  textColor=WHITE,    leading=12)
    S_label   = style("label",   fontName="Helvetica-Bold", fontSize=8,  textColor=BRAND_DARK)
    S_value   = style("value",   fontName="Helvetica",      fontSize=9,  textColor=BLACK)
    S_small   = style("small",   fontName="Helvetica",      fontSize=7,  textColor=colors.HexColor("#64748B"))
    S_scope   = style("scope",   fontName="Helvetica",      fontSize=9,  textColor=BLACK,    leading=14)
    S_h2      = style("h2",      fontName="Helvetica-Bold", fontSize=10, textColor=BRAND_DARK)
    S_tc      = style("tc",      fontName="Helvetica",      fontSize=7.5,textColor=BLACK,    leading=11)

    story = []

    # ── Header banner ─────────────────────────────────────────────────────
    company   = data.get("company", {})
    co_name   = company.get("name",    "CTTX")
    co_reg    = company.get("reg",     "2016/406552/07")
    co_vat    = company.get("vat",     "4470275803")
    co_po     = company.get("po_email","finance@cttx.co.za")
    co_tel    = company.get("tel",     "")
    co_web    = company.get("website", "")

    header_data = [[
        Paragraph(co_name, S_title),
        Paragraph(
            f"Reg: {co_reg}<br/>VAT: {co_vat}<br/>"
            f"PO: {co_po}"
            + (f"<br/>Tel: {co_tel}" if co_tel else "")
            + (f"<br/>{co_web}" if co_web else ""),
            S_sub
        ),
        Paragraph("QUOTATION", S_title),
    ]]
    header_table = Table(header_data, colWidths=[80*mm, 70*mm, 50*mm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), BRAND_DARK),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING",(0,0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN",       (2, 0), (2, 0),   "RIGHT"),
        ("RIGHTPADDING",(2, 0), (2, 0),   10),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6*mm))

    # ── Quote meta + client info ───────────────────────────────────────────
    client     = data.get("client", {})
    quote_ref  = data.get("quote_ref",  "")
    quote_date = data.get("date",       datetime.today().strftime("%Y/%m/%d"))
    valid_days = data.get("valid_days", 7)

    meta_data = [
        [Paragraph("ATTENTION:", S_label),  Paragraph(client.get("attention",""), S_value),
         Paragraph("QUOTE REF:", S_label),  Paragraph(str(quote_ref), S_value)],
        [Paragraph("COMPANY:", S_label),    Paragraph(client.get("company",""), S_value),
         Paragraph("DATE:", S_label),       Paragraph(quote_date, S_value)],
        [Paragraph("EMAIL:", S_label),      Paragraph(client.get("email",""), S_value),
         Paragraph("VALID FOR:", S_label),  Paragraph(f"{valid_days} days", S_value)],
    ]
    meta_table = Table(meta_data, colWidths=[28*mm, 70*mm, 28*mm, 48*mm])
    meta_table.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",  (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0,0), (-1, -1), 3),
        ("LINEBELOW",   (0, -1), (-1, -1), 0.5, BRAND_BLUE),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 5*mm))

    # ── Scope / write-up ──────────────────────────────────────────────────
    scope = data.get("scope", "")
    if scope:
        story.append(Paragraph("SCOPE OF WORK", S_h2))
        story.append(Spacer(1, 2*mm))
        for line in scope.split("\n"):
            if line.strip():
                story.append(Paragraph(line, S_scope))
        story.append(Spacer(1, 5*mm))

    # ── Line items ────────────────────────────────────────────────────────
    factor    = float(data.get("factor", 0.8))
    roe       = float(data.get("roe",    1.0))
    items     = data.get("items", [])

    story.append(Paragraph("LINE ITEMS", S_h2))
    story.append(Spacer(1, 2*mm))

    col_headers = ["#", "Description", "Qty", "Unit Price", "Total"]
    col_widths  = [8*mm, 95*mm, 12*mm, 30*mm, 30*mm]

    rows = [col_headers]
    sub_total   = 0.0
    total_cost  = 0.0

    for i, item in enumerate(items, 1):
        qty        = float(item.get("qty", 1))
        desc       = item.get("description", "")
        item_cost  = float(item.get("item_cost", 0))
        # selling unit price = cost / factor
        unit_price = item_cost / factor if factor else item_cost
        line_total = qty * unit_price
        sub_total += line_total
        total_cost += qty * item_cost

        rows.append([
            str(i),
            desc,
            str(int(qty)) if qty == int(qty) else str(qty),
            money(unit_price),
            money(line_total),
        ])

    vat_rate   = float(data.get("vat_rate", 15)) / 100
    vat_amount = sub_total * vat_rate
    grand_total = sub_total + vat_amount
    proj_gp    = sub_total - total_cost
    gp_pct     = (proj_gp / sub_total * 100) if sub_total else 0

    # empty separator row then totals
    rows.append(["", "", "", "", ""])
    rows.append(["", "", "", "Sub Total",  money(sub_total)])
    rows.append(["", "", "", f"VAT ({int(data.get('vat_rate',15))}%)", money(vat_amount)])
    rows.append(["", "", "", "GRAND TOTAL", money(grand_total)])

    item_table = Table(rows, colWidths=col_widths, repeatRows=1)
    n = len(rows)
    item_table.setStyle(TableStyle([
        # header row
        ("BACKGROUND",   (0, 0), (-1, 0),  BRAND_DARK),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  WHITE),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0),  8),
        ("ALIGN",        (0, 0), (-1, 0),  "CENTER"),
        # data rows
        ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 1), (-1, -1), 8),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        # stripe alternating data rows
        *[("BACKGROUND", (0, r), (-1, r), BRAND_LIGHT)
          for r in range(2, len(items)+1, 2)],
        # right-align numbers
        ("ALIGN",        (2, 1), (-1, -1), "RIGHT"),
        # totals section
        ("LINEABOVE",    (0, len(items)+2), (-1, len(items)+2), 0.5, BRAND_BLUE),
        ("FONTNAME",     (0, len(items)+2), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND",   (0, n-1), (-1, n-1), BRAND_DARK),
        ("TEXTCOLOR",    (0, n-1), (-1, n-1), WHITE),
        ("GRID",         (0, 0), (-1, len(items)+1), 0.25, colors.HexColor("#CBD5E1")),
    ]))
    story.append(item_table)
    story.append(Spacer(1, 6*mm))

    # ── Terms & Conditions ────────────────────────────────────────────────
    terms = data.get("terms", [
        "This quote is valid for 7 days only.",
        "This quote is based on the information available at the time of presenting this costing.",
        "All imported material is subject to ROE exchange rate on the day of order number received.",
        "Prices quoted are based on the ROE of the day the quote was presented.",
        "Post order design changes may lead to additional cost, and needs to be approved by the client prior to change being effected.",
        "Final project cost to be agreed on, once an actual on-site agreement between CTTX and the client has been reached.",
        "Depending on the project size, 50% deposit will be required to cover materials cost.",
        "Final order settlement amount to be paid to CTTX within 30 days of invoice to client.",
    ])

    story.append(HRFlowable(width="100%", thickness=0.5, color=BRAND_BLUE))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("TERMS & CONDITIONS", S_h2))
    story.append(Spacer(1, 1*mm))
    for t in terms:
        story.append(Paragraph(f"• {t}", S_tc))

    # ── Footer note ───────────────────────────────────────────────────────
    story.append(Spacer(1, 4*mm))
    if roe != 1.0:
        story.append(Paragraph(f"ROE at time of quoting: {roe}", S_small))

    doc.build(story)
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 generate_pdf.py <quote.json> [output.pdf]")
        sys.exit(1)

    json_path = sys.argv[1]
    with open(json_path) as f:
        quote_data = json.load(f)

    out = sys.argv[2] if len(sys.argv) > 2 else json_path.replace(".json", ".pdf")
    result = build_pdf(quote_data, out)
    print(f"PDF generated: {result}")
