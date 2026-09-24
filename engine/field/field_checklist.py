"""
CTTX Level 2 Field Assessment Checklist Generator
Produces mobile-friendly text checklist for field-partner technicians.
Technicians record PASS/FAIL/NOT_PRESENT/UNKNOWN/PHOTO_REQUIRED per item.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from db.database import get_connection, upsert_observation, DB_PATH, now_iso, new_id

CHECKLIST_SECTIONS = [
    {
        "section": "SITE IDENTIFICATION",
        "items": [
            {"id": "SI-01", "item": "GPS coordinates recorded (to 5 decimal places)", "photo": True},
            {"id": "SI-02", "item": "Site name / address confirmed"},
            {"id": "SI-03", "item": "Access road condition — usable by service vehicle", "photo": True},
            {"id": "SI-04", "item": "Security / gated access confirmed"},
        ],
    },
    {
        "section": "MAST CONDITION",
        "items": [
            {"id": "MA-01", "item": "Mast present on site", "photo": True},
            {"id": "MA-02", "item": "Mast type (guyed/self-support/rooftop/wall)"},
            {"id": "MA-03", "item": "Estimated mast height (metres)"},
            {"id": "MA-04", "item": "Mast visually vertical — no observable lean", "photo": True},
            {"id": "MA-05", "item": "Mast structure in good condition — no visible corrosion/damage", "photo": True},
            {"id": "MA-06", "item": "Guy wires intact and tensioned (if applicable)", "photo": True},
            {"id": "MA-07", "item": "Mounting space available for new hardware"},
            {"id": "MA-08", "item": "Safe ladder/climbing access available"},
        ],
    },
    {
        "section": "POWER",
        "items": [
            {"id": "PW-01", "item": "Mains power available at site (Eskom/municipal)", "photo": True},
            {"id": "PW-02", "item": "Estimated supply voltage (V)"},
            {"id": "PW-03", "item": "Estimated available load (A / kVA)"},
            {"id": "PW-04", "item": "Generator present on site", "photo": True},
            {"id": "PW-05", "item": "Solar / battery system present", "photo": True},
            {"id": "PW-06", "item": "DB board accessible for new circuit", "photo": True},
            {"id": "PW-07", "item": "Earthing infrastructure visible", "photo": True},
            {"id": "PW-08", "item": "Lightning protection present"},
        ],
    },
    {
        "section": "EQUIPMENT SPACE",
        "items": [
            {"id": "EQ-01", "item": "Enclosed equipment room/shelter available", "photo": True},
            {"id": "EQ-02", "item": "Equipment space dimensions (m)"},
            {"id": "EQ-03", "item": "Temperature controlled / ventilated"},
            {"id": "EQ-04", "item": "Existing network equipment present", "photo": True},
            {"id": "EQ-05", "item": "Existing fibre patch panel present", "photo": True},
            {"id": "EQ-06", "item": "Existing antennas/radios on structure", "photo": True},
        ],
    },
    {
        "section": "LINE OF SIGHT",
        "items": [
            {"id": "LO-01", "item": "Clear horizon visible towards target direction 1 (specify bearing)"},
            {"id": "LO-02", "item": "Clear horizon visible towards target direction 2 (specify bearing)"},
            {"id": "LO-03", "item": "Vegetation obstructing LOS within 500m", "photo": True},
            {"id": "LO-04", "item": "Buildings/structures obstructing LOS", "photo": True},
            {"id": "LO-05", "item": "Known tower/mast visible from site", "photo": True},
        ],
    },
    {
        "section": "CABLE ROUTES",
        "items": [
            {"id": "CA-01", "item": "Overhead cable route from mast to building feasible"},
            {"id": "CA-02", "item": "Underground cable route feasible"},
            {"id": "CA-03", "item": "Estimated cable run length mast-to-equipment (m)"},
            {"id": "CA-04", "item": "Fibre duct/conduit present"},
        ],
    },
    {
        "section": "SECURITY & ENVIRONMENT",
        "items": [
            {"id": "SE-01", "item": "Fenced perimeter", "photo": True},
            {"id": "SE-02", "item": "CCTV present on site"},
            {"id": "SE-03", "item": "Armed response / monitored security"},
            {"id": "SE-04", "item": "Wildlife risk (electric fence / game area)"},
            {"id": "SE-05", "item": "Flood risk / low-lying area observed"},
        ],
    },
    {
        "section": "TECHNICIAN OBSERVATIONS",
        "items": [
            {"id": "TO-01", "item": "Overall site suitability for RF installation (SUITABLE/UNSUITABLE/CONDITIONAL)"},
            {"id": "TO-02", "item": "Major obstacles not listed above"},
            {"id": "TO-03", "item": "Recommended follow-up actions"},
            {"id": "TO-04", "item": "All required photos captured (Y/N)"},
        ],
    },
]

RESULT_OPTIONS = ["PASS", "FAIL", "NOT_PRESENT", "UNKNOWN", "PHOTO_REQUIRED"]


def generate_checklist_text(
    property_name: str,
    property_id: str,
    assessment_date: Optional[str] = None,
    technician: str = "Field Technician",
) -> str:
    """Generate mobile-friendly plain-text checklist."""
    date_str = assessment_date or datetime.now().strftime("%Y-%m-%d")
    lines = [
        "═" * 50,
        "CTTX LEVEL 2 FIELD ASSESSMENT",
        "═" * 50,
        f"Property:    {property_name}",
        f"Property ID: {property_id}",
        f"Date:        {date_str}",
        f"Technician:  {technician}",
        f"Ref:         {new_id('CHK')}",
        "─" * 50,
        "OPTIONS: PASS | FAIL | NOT_PRESENT | UNKNOWN | PHOTO_REQUIRED",
        "Items marked [📷] REQUIRE a photo.",
        "─" * 50,
        "",
    ]
    for section in CHECKLIST_SECTIONS:
        lines.append(f"▌ {section['section']}")
        lines.append("─" * 40)
        for item in section["items"]:
            photo_flag = " [📷]" if item.get("photo") else ""
            lines.append(f"  {item['id']}{photo_flag}")
            lines.append(f"  {item['item']}")
            lines.append(f"  Result: _______________  Notes: ___________________________")
            lines.append("")
        lines.append("")

    lines += [
        "─" * 50,
        "SIGN-OFF",
        "─" * 50,
        "Technician signature: _______________________",
        "Date/time completed:  _______________________",
        "Photo count:          _______________________",
        "",
        "IMPORTANT: Do not make engineering design decisions.",
        "Record observations only. CTTX engineering team will",
        "analyse data and produce the technical report.",
        "═" * 50,
    ]
    return "\n".join(lines)


def generate_checklist_json(property_name: str, property_id: str) -> dict:
    """Generate a structured JSON checklist for digital completion."""
    return {
        "checklist_type": "CTTX_LEVEL2_FIELD_ASSESSMENT",
        "property_name": property_name,
        "property_id": property_id,
        "generated_at": now_iso(),
        "version": "1.0",
        "sections": CHECKLIST_SECTIONS,
        "result_options": RESULT_OPTIONS,
        "instructions": (
            "Record PASS/FAIL/NOT_PRESENT/UNKNOWN/PHOTO_REQUIRED for each item. "
            "Items marked photo:true require a photograph. "
            "Do not make engineering design decisions — record observations only."
        ),
    }


def ingest_completed_checklist(
    completed_json: dict,
    db_path: str = DB_PATH,
) -> dict:
    """
    Ingest a completed field checklist back into the NII.
    Writes verified engineering facts with source=field_survey.
    """
    conn = get_connection(db_path)
    property_id = completed_json.get("property_id")
    if not property_id:
        return {"status": "FAIL", "reason": "No property_id in completed checklist"}

    written = 0
    for section in completed_json.get("sections", []):
        for item in section.get("items", []):
            result = item.get("result")
            if not result:
                continue
            notes = item.get("notes", "")
            upsert_observation(
                conn, property_id,
                obs_type="field_survey",
                key=item["id"],
                value=result,
                source="field_survey",
                confidence="HIGH" if result == "PASS" else "MEDIUM",
                notes=f"{item['item']} | {notes}",
            )
            written += 1

    # Update assessment status
    conn.execute(
        "UPDATE properties SET assessment_status='SITE_SURVEY', "
        "enrichment_status='ENRICHED', updated_at=? WHERE property_id=?",
        (now_iso(), property_id)
    )
    conn.commit()
    conn.close()

    return {
        "status": "PASS",
        "property_id": property_id,
        "observations_written": written,
        "ingested_at": now_iso(),
    }
