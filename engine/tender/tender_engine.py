"""
CTTX Tender Intelligence Engine
Finds, registers, audits, and cross-analyses historical tender submissions.
"""

import json
import sys
import time
from pathlib import Path
from typing import Optional
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from db.database import get_connection, DB_PATH, now_iso, new_id

EVIDENCE_LEVELS = [
    "EXPLICITLY_DEMONSTRATED",
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "NOT_EXPLICITLY_DEMONSTRATED",
    "NOT_FOUND",
]

STANDARD_AUDIT_CRITERIA = [
    "Mandatory compliance — all required documents submitted",
    "Valid tax clearance / B-BBEE certificate",
    "Company registration and legal entity status",
    "Technical capability — relevant experience stated",
    "Technical capability — evidence/references provided",
    "Proposed solution architecture — technically coherent",
    "Implementation methodology — sufficiently detailed",
    "Project timeline — realistic and sequenced",
    "Personnel CVs — relevant qualifications",
    "Similar projects — reference letters provided",
    "Equipment/hardware specifications",
    "Maintenance and support plan",
    "SLA commitments",
    "Pricing — internally consistent",
    "Pricing — aligned with tender schedule",
    "CAPEX / OPEX clearly separated",
    "Assumptions and exclusions listed",
    "Signed declarations",
    "Presentation — easy for evaluator to score",
]


def register_tender(
    reference: str,
    issuing_org: str,
    description: str,
    category: str = "telecoms",
    submission_date: Optional[str] = None,
    closing_date: Optional[str] = None,
    cttx_submission_path: Optional[str] = None,
    source_path: Optional[str] = None,
    db_path: str = DB_PATH,
) -> str:
    conn = get_connection(db_path)
    tender_id = new_id("TND")
    conn.execute("""
        INSERT OR IGNORE INTO tenders
          (tender_id, reference, issuing_org, description, category,
           submission_date, closing_date, cttx_submission_path, source_path, status)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (tender_id, reference, issuing_org, description, category,
          submission_date, closing_date, cttx_submission_path, source_path,
          "SUBMITTED" if submission_date else "DISCOVERED"))
    conn.commit()
    conn.close()
    return tender_id


def run_submission_audit(
    tender_id: str,
    criteria: Optional[list[dict]] = None,
    db_path: str = DB_PATH,
) -> dict:
    """
    Scaffold an evidence-based audit for a tender submission.
    Returns the audit template pre-populated with standard criteria.
    Human analyst completes evidence fields after reviewing the submission.
    """
    conn = get_connection(db_path)
    tender = conn.execute(
        "SELECT * FROM tenders WHERE tender_id=?", (tender_id,)
    ).fetchone()
    if not tender:
        conn.close()
        return {"status": "FAIL", "reason": f"Tender {tender_id} not found"}

    criteria_list = criteria or [
        {"criterion": c, "available_points": None} for c in STANDARD_AUDIT_CRITERIA
    ]

    audit_records = []
    for cr in criteria_list:
        audit_id = new_id("AUD")
        conn.execute("""
            INSERT OR IGNORE INTO tender_audit
              (audit_id, tender_id, criterion, available_points,
               evidence_strength, compliance_status)
            VALUES (?,?,?,?,?,?)
        """, (audit_id, tender_id, cr["criterion"],
              cr.get("available_points"),
              "NOT_FOUND", "UNKNOWN"))
        audit_records.append(audit_id)

    conn.execute(
        "UPDATE tenders SET audit_status='IN_PROGRESS' WHERE tender_id=?",
        (tender_id,)
    )
    conn.commit()
    conn.close()

    return {
        "status": "PASS",
        "tender_id": tender_id,
        "reference": tender["reference"],
        "issuing_org": tender["issuing_org"],
        "audit_records_created": len(audit_records),
        "next_step": (
            "Review CTTX submission at the path recorded in the tender register. "
            "Update each audit record's evidence_strength and compliance_status. "
            "Run cross_tender_analysis() after all tenders are audited."
        ),
    }


def update_audit_criterion(
    audit_id: str,
    cttx_response: Optional[str] = None,
    evidence_location: Optional[str] = None,
    evidence_strength: Optional[str] = None,
    missing_information: Optional[str] = None,
    compliance_status: Optional[str] = None,
    auditor_notes: Optional[str] = None,
    db_path: str = DB_PATH,
) -> dict:
    if evidence_strength and evidence_strength not in EVIDENCE_LEVELS:
        return {"status": "FAIL", "reason": f"Invalid evidence_strength: {evidence_strength}"}

    conn = get_connection(db_path)
    updates = {}
    if cttx_response is not None:
        updates["cttx_response"] = cttx_response
    if evidence_location is not None:
        updates["evidence_location"] = evidence_location
    if evidence_strength is not None:
        updates["evidence_strength"] = evidence_strength
    if missing_information is not None:
        updates["missing_information"] = missing_information
    if compliance_status is not None:
        updates["compliance_status"] = compliance_status
    if auditor_notes is not None:
        updates["auditor_notes"] = auditor_notes

    if updates:
        set_clause = ", ".join(f"{k}=?" for k in updates)
        conn.execute(
            f"UPDATE tender_audit SET {set_clause} WHERE audit_id=?",
            list(updates.values()) + [audit_id]
        )
        conn.commit()
    conn.close()
    return {"status": "PASS", "audit_id": audit_id, "updated": list(updates.keys())}


def cross_tender_analysis(db_path: str = DB_PATH) -> dict:
    """
    Identify recurring strengths and weaknesses across all audited tenders.
    """
    conn = get_connection(db_path)
    tenders = conn.execute(
        "SELECT tender_id, reference, issuing_org FROM tenders "
        "WHERE audit_status IN ('IN_PROGRESS','COMPLETE')"
    ).fetchall()

    if not tenders:
        conn.close()
        return {"status": "PARTIAL", "reason": "No audited tenders found"}

    strength_counts: dict[str, int] = {}
    weakness_counts: dict[str, int] = {}
    gap_counts: dict[str, int] = {}

    for tender in tenders:
        rows = conn.execute(
            "SELECT criterion, evidence_strength, compliance_status, missing_information "
            "FROM tender_audit WHERE tender_id=?",
            (tender["tender_id"],)
        ).fetchall()

        for row in rows:
            crit = row["criterion"]
            es = row["evidence_strength"] or "NOT_FOUND"
            if es in ("EXPLICITLY_DEMONSTRATED", "SUPPORTED"):
                strength_counts[crit] = strength_counts.get(crit, 0) + 1
            elif es in ("NOT_EXPLICITLY_DEMONSTRATED", "NOT_FOUND"):
                weakness_counts[crit] = weakness_counts.get(crit, 0) + 1
            if row["missing_information"]:
                gap_counts[crit] = gap_counts.get(crit, 0) + 1

    conn.close()

    top_strengths = sorted(strength_counts.items(), key=lambda x: -x[1])[:10]
    top_weaknesses = sorted(weakness_counts.items(), key=lambda x: -x[1])[:10]
    top_gaps = sorted(gap_counts.items(), key=lambda x: -x[1])[:10]

    return {
        "status": "PASS",
        "tenders_analysed": len(tenders),
        "recurring_strengths": [{"criterion": k, "tenders": v} for k, v in top_strengths],
        "recurring_weaknesses": [{"criterion": k, "tenders": v} for k, v in top_weaknesses],
        "recurring_gaps": [{"criterion": k, "tenders": v} for k, v in top_gaps],
        "analysis_date": now_iso(),
        "note": (
            "Use this to distinguish between a CAPABILITY PROBLEM and an "
            "EVIDENCE/PACKAGING PROBLEM. If CTTX can demonstrate work done, "
            "the issue is presentation, not capability."
        ),
    }


def get_tender_summary(db_path: str = DB_PATH) -> dict:
    conn = get_connection(db_path)
    total = conn.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]
    by_status = dict(conn.execute(
        "SELECT status, COUNT(*) FROM tenders GROUP BY status"
    ).fetchall())
    by_audit = dict(conn.execute(
        "SELECT audit_status, COUNT(*) FROM tenders GROUP BY audit_status"
    ).fetchall())
    conn.close()
    return {
        "total_tenders": total,
        "by_status": by_status,
        "by_audit_status": by_audit,
    }
