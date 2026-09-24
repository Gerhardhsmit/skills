"""
CTTX Infrastructure Snapshot PDF Generator
Produces a client-safe one-page (or compact two-page) PDF.
No internal IDs, scores, or PII exposed.
"""

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from db.database import get_connection, DB_PATH, now_iso

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ─── CTTX BRAND PALETTE ──────────────────────────────────────────────────────
CTTX_DARK    = colors.HexColor("#0D1B2A")
CTTX_BLUE    = colors.HexColor("#1A6BAD")
CTTX_ACCENT  = colors.HexColor("#F28C28")
CTTX_LIGHT   = colors.HexColor("#F4F7FA")
CTTX_MID     = colors.HexColor("#8FA7BF")
CTTX_SUCCESS = colors.HexColor("#2E7D32")
CTTX_WARN    = colors.HexColor("#F57F17")

OUTPUT_DIR = os.environ.get("CTTX_OUTPUT_DIR",
    str(Path(__file__).parent.parent.parent / "engine" / "data" / "snapshots"))


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title",
            fontName="Helvetica-Bold", fontSize=18,
            textColor=CTTX_DARK, spaceAfter=2*mm),
        "subtitle": ParagraphStyle("subtitle",
            fontName="Helvetica", fontSize=11,
            textColor=CTTX_BLUE, spaceAfter=4*mm),
        "heading": ParagraphStyle("heading",
            fontName="Helvetica-Bold", fontSize=10,
            textColor=CTTX_BLUE, spaceBefore=4*mm, spaceAfter=2*mm),
        "body": ParagraphStyle("body",
            fontName="Helvetica", fontSize=9,
            textColor=CTTX_DARK, spaceAfter=1.5*mm, leading=13),
        "small": ParagraphStyle("small",
            fontName="Helvetica", fontSize=7.5,
            textColor=CTTX_MID, leading=10),
        "opening": ParagraphStyle("opening",
            fontName="Helvetica-Bold", fontSize=10.5,
            textColor=CTTX_DARK, spaceAfter=4*mm,
            borderPad=3*mm, leading=15),
        "footer": ParagraphStyle("footer",
            fontName="Helvetica", fontSize=7,
            textColor=CTTX_MID, alignment=TA_CENTER),
        "caveat": ParagraphStyle("caveat",
            fontName="Helvetica-Oblique", fontSize=8,
            textColor=CTTX_MID, spaceAfter=2*mm),
    }


def _opportunity_badge(profile: str) -> str:
    labels = {
        "HIGH": "● HIGH INFRASTRUCTURE OPPORTUNITY",
        "MODERATE": "◑ MODERATE INFRASTRUCTURE OPPORTUNITY",
        "LOW": "○ LOW INFRASTRUCTURE OPPORTUNITY",
        "UNKNOWN": "? OPPORTUNITY PROFILE: UNDER ASSESSMENT",
    }
    return labels.get(profile, "? UNKNOWN")


def generate_snapshot(
    property_data: dict,
    engineering_data: dict,
    output_path: Optional[str] = None,
    db_path: str = DB_PATH,
) -> dict:
    """
    Generate Infrastructure Snapshot PDF.

    property_data keys:
        name, property_type, province, municipality, latitude, longitude,
        area_ha, opportunity_profile, opportunity_evidence

    engineering_data keys:
        n_operational_locations (int)
        n_candidate_high_sites (int)
        n_backbone_corridors (int)
        site_elevation_m
        candidate_high_sites (list of dicts)
        los_links (list of dicts)
        infrastructure_observations (list of str)
        constraints (list of str)
        assessment_recommendation (str)
        confidence_note (str)
    """
    started = time.time()
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    prop_name = property_data.get("name", "Unknown Property")
    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in prop_name)

    if not output_path:
        output_path = str(Path(OUTPUT_DIR) /
                          f"CTTX_{safe_name}_Infrastructure_Snapshot_{date_str}.pdf")

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=18*mm, leftMargin=18*mm,
        topMargin=18*mm, bottomMargin=18*mm,
        title=f"CTTX Infrastructure Snapshot — {prop_name}",
        author="CTTX Services (Pty) Ltd",
    )

    S = _styles()
    story = []

    # ── HEADER ───────────────────────────────────────────────────────────────
    header_data = [
        [Paragraph("CTTX SERVICES", ParagraphStyle("hdr",
            fontName="Helvetica-Bold", fontSize=14, textColor=colors.white)),
         Paragraph("INFRASTRUCTURE SNAPSHOT", ParagraphStyle("hdr2",
            fontName="Helvetica-Bold", fontSize=11,
            textColor=colors.white, alignment=TA_RIGHT))],
    ]
    header_tbl = Table(header_data, colWidths=["50%", "50%"])
    header_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CTTX_DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 5*mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5*mm),
        ("LEFTPADDING", (0, 0), (0, -1), 4*mm),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 4*mm),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 4*mm))

    # ── PROPERTY TITLE ───────────────────────────────────────────────────────
    story.append(Paragraph(prop_name.upper(), S["title"]))
    location_parts = filter(None, [
        property_data.get("municipality"),
        property_data.get("province"),
        "South Africa",
    ])
    story.append(Paragraph(" | ".join(location_parts), S["subtitle"]))
    story.append(Paragraph(date_str, S["small"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=CTTX_BLUE,
                            spaceAfter=4*mm))

    # ── OPENING STATEMENT ────────────────────────────────────────────────────
    n_op = engineering_data.get("n_operational_locations", "N/A")
    n_hs = engineering_data.get("n_candidate_high_sites", "N/A")
    n_bb = engineering_data.get("n_backbone_corridors", "N/A")
    opening = (f"We identified <b>{n_op}</b> operational locations, "
               f"<b>{n_hs}</b> potential high sites and "
               f"<b>{n_bb}</b> possible backbone corridors.")
    story.append(Paragraph(opening, S["opening"]))

    # ── OPPORTUNITY PROFILE ──────────────────────────────────────────────────
    opp = property_data.get("opportunity_profile", "UNKNOWN")
    badge_text = _opportunity_badge(opp)
    badge_color = {
        "HIGH": CTTX_ACCENT, "MODERATE": CTTX_BLUE,
        "LOW": CTTX_MID, "UNKNOWN": CTTX_MID
    }.get(opp, CTTX_MID)
    badge_tbl = Table([[Paragraph(badge_text,
        ParagraphStyle("badge", fontName="Helvetica-Bold", fontSize=9,
                       textColor=colors.white))]], colWidths=["60%"])
    badge_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), badge_color),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5*mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5*mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 3*mm),
    ]))
    story.append(badge_tbl)
    story.append(Spacer(1, 3*mm))

    if property_data.get("opportunity_evidence"):
        story.append(Paragraph(f"<i>Basis: {property_data['opportunity_evidence']}</i>",
                                S["small"]))
        story.append(Spacer(1, 2*mm))

    # ── PROPERTY OVERVIEW ────────────────────────────────────────────────────
    story.append(Paragraph("PROPERTY OVERVIEW", S["heading"]))
    prop_rows = [
        ["Type", property_data.get("property_type", "—").replace("_", " ").title()],
        ["Province", property_data.get("province") or "—"],
        ["Municipality", property_data.get("municipality") or "—"],
        ["Area", f"{property_data.get('area_ha', '—')} ha" if property_data.get('area_ha') else "—"],
        ["Co-ordinates",
         f"{property_data.get('latitude', '—'):.4f}°, {property_data.get('longitude', '—'):.4f}°"
         if property_data.get("latitude") else "—"],
        ["Site elevation", f"{engineering_data.get('site_elevation_m', '—')} m AMSL"
         if engineering_data.get("site_elevation_m") else "—"],
    ]
    prop_tbl = Table(prop_rows, colWidths=["35%", "65%"])
    prop_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), CTTX_BLUE),
        ("TEXTCOLOR", (1, 0), (1, -1), CTTX_DARK),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [CTTX_LIGHT, colors.white]),
        ("TOPPADDING", (0, 0), (-1, -1), 2*mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2*mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 3*mm),
    ]))
    story.append(prop_tbl)

    # ── INFRASTRUCTURE OBSERVATIONS ──────────────────────────────────────────
    story.append(Paragraph("INFRASTRUCTURE OBSERVATIONS", S["heading"]))
    obs_list = engineering_data.get("infrastructure_observations", [])
    if obs_list:
        for obs in obs_list:
            story.append(Paragraph(f"• {obs}", S["body"]))
    else:
        story.append(Paragraph("No infrastructure observations recorded at this stage.", S["body"]))

    # ── CANDIDATE HIGH SITES ─────────────────────────────────────────────────
    if engineering_data.get("candidate_high_sites"):
        story.append(Paragraph("CANDIDATE HIGH SITES", S["heading"]))
        hs_rows = [["Site", "Elevation (m)", "Distance", "Status"]]
        for idx, hs in enumerate(engineering_data["candidate_high_sites"][:5]):
            hs_rows.append([
                f"HS-{idx+1}",
                str(hs.get("elevation_m", "—")),
                f"{hs.get('distance_from_property_m', 0)/1000:.2f} km",
                hs.get("classification", "Engineering candidate"),
            ])
        hs_tbl = Table(hs_rows, colWidths=["15%", "20%", "25%", "40%"])
        hs_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), CTTX_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CTTX_LIGHT, colors.white]),
            ("TOPPADDING", (0, 0), (-1, -1), 2*mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2*mm),
            ("LEFTPADDING", (0, 0), (-1, -1), 2.5*mm),
        ]))
        story.append(hs_tbl)

    # ── LOS LINKS ────────────────────────────────────────────────────────────
    los_links = engineering_data.get("los_links", [])
    if los_links:
        story.append(Paragraph("LINE-OF-SIGHT CANDIDATES", S["heading"]))
        los_rows = [["Link", "Distance", "LOS Status", "F1 Clearance"]]
        for link in los_links[:5]:
            los_rows.append([
                f"{link.get('site_a','A')} → {link.get('site_b','B')}",
                f"{link.get('distance_km', '—')} km",
                link.get("los_status", "UNKNOWN"),
                f"{link.get('clearance_f1_m', '—')} m" if link.get("clearance_f1_m") is not None else "—",
            ])
        los_tbl = Table(los_rows, colWidths=["30%", "18%", "22%", "30%"])
        los_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), CTTX_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CTTX_LIGHT, colors.white]),
            ("TOPPADDING", (0, 0), (-1, -1), 2*mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2*mm),
            ("LEFTPADDING", (0, 0), (-1, -1), 2.5*mm),
        ]))
        story.append(los_tbl)

    # ── CONSTRAINTS ──────────────────────────────────────────────────────────
    constraints = engineering_data.get("constraints", [])
    if constraints:
        story.append(Paragraph("MAJOR CONSTRAINTS", S["heading"]))
        for c in constraints:
            story.append(Paragraph(f"⚠ {c}", S["body"]))

    # ── ASSESSMENT RECOMMENDATION ────────────────────────────────────────────
    story.append(Paragraph("ASSESSMENT RECOMMENDATION", S["heading"]))
    rec = engineering_data.get("assessment_recommendation",
        "A Remote Desk Assessment is recommended to establish preliminary link budgets "
        "and refine the candidate infrastructure topology before mobilising a physical survey.")
    story.append(Paragraph(rec, S["body"]))

    # ── CONFIDENCE / CAVEAT ──────────────────────────────────────────────────
    story.append(Spacer(1, 3*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=CTTX_MID,
                            spaceAfter=2*mm))
    conf_note = engineering_data.get("confidence_note",
        "This snapshot is based on publicly available geographic data and remote terrain analysis. "
        "All observations are preliminary and require verification by a qualified CTTX field engineer.")
    story.append(Paragraph(conf_note, S["caveat"]))

    # ── FOOTER ───────────────────────────────────────────────────────────────
    footer_text = (
        "CTTX Services (Pty) Ltd  |  We build infrastructure.  |  "
        "www.cttx.co.za  |  "
        f"Generated {date_str}  |  CONFIDENTIAL — NOT FOR DISTRIBUTION"
    )
    story.append(Paragraph(footer_text, S["footer"]))

    doc.build(story)

    elapsed = time.time() - started
    return {
        "status": "PASS",
        "output_path": output_path,
        "elapsed_s": round(elapsed, 2),
        "generated_at": now_iso(),
    }
