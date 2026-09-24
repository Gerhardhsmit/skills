"""
CTTX Outreach Draft Engine
Stages assessment-offer email drafts to Outlook.
STRICT: Creates drafts ONLY. Human must review and manually send.
Never sends automatically.
Supports: win32com (Windows), .eml file fallback, database staging.
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from db.database import get_connection, DB_PATH, now_iso, new_id

log = logging.getLogger("cttx.drafts")

DRAFTS_DIR = os.environ.get("CTTX_DRAFTS_DIR",
    str(Path(__file__).parent.parent / "data" / "drafts"))

ASSESSMENT_OFFER_TEMPLATE = """Subject: {subject}

Dear {salutation},

{opening_line}

CTTX Services specialises in the design and deployment of telecommunications infrastructure
for geographically distributed operations — not device connectivity, but engineered networks
that give your operation reliable, owned communications backbone.

Based on our preliminary desk study of {property_name}, we believe a formal Infrastructure
Assessment would deliver meaningful value. Our assessment provides:

  • A complete infrastructure observation and terrain analysis
  • Candidate network topology and high-site evaluation
  • Line-of-sight calculations and link-budget assumptions
  • A structured proposal for owned-network architecture options

Our Level 1 Remote Desk Assessment gives you a detailed picture before any site visit.
Our Level 2 On-Site Infrastructure Assessment (R3,500 ex VAT) provides verified field data
and is the basis for a full owned-network proposal.

{specific_observation}

We would welcome the opportunity to present our preliminary findings.

Kind regards,

{sender_name}
CTTX Services (Pty) Ltd
{sender_contact}
"""


def _build_email_body(
    property_name: str,
    contact_name: Optional[str],
    organisation: Optional[str],
    snapshot_path: Optional[str],
    specific_observation: str = "",
    sender_name: str = "CTTX Services",
    sender_contact: str = "www.cttx.co.za",
) -> dict:
    salutation = f"{contact_name}" if contact_name else "Sir/Madam"
    if organisation:
        salutation = f"{contact_name or 'Sir/Madam'} ({organisation})"

    opening_line = (
        f"We have completed a preliminary infrastructure desk study of {property_name} "
        f"and would like to share our findings with your team."
    )

    subject = f"CTTX Infrastructure Assessment — {property_name}"

    body = ASSESSMENT_OFFER_TEMPLATE.format(
        subject=subject,
        salutation=salutation,
        opening_line=opening_line,
        property_name=property_name,
        specific_observation=specific_observation or
            "Our analysis identified several candidate high sites and potential backbone corridors.",
        sender_name=sender_name,
        sender_contact=sender_contact,
    )
    return {"subject": subject, "body": body}


def _stage_to_outlook_windows(to_email: str, subject: str, body: str,
                               attachments: list[str] = None) -> dict:
    """Use win32com to create an Outlook draft (Windows only)."""
    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # 0 = olMailItem
        mail.To = to_email
        mail.Subject = subject
        mail.Body = body
        if attachments:
            for att in attachments:
                if Path(att).exists():
                    mail.Attachments.Add(att)
        mail.Save()  # saves to Drafts folder — does NOT send
        return {"status": "PASS", "method": "outlook_win32", "draft": "saved_to_drafts"}
    except ImportError:
        return {"status": "SKIP", "reason": "win32com not available (not Windows)"}
    except Exception as exc:
        return {"status": "FAIL", "reason": str(exc)}


def _save_eml_draft(to_email: str, subject: str, body: str,
                    attachments: list[str] = None) -> str:
    """Save draft as .eml file for manual import to any mail client."""
    Path(DRAFTS_DIR).mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_subj = "".join(c if c.isalnum() or c in "-_" else "_" for c in subject[:40])
    eml_path = str(Path(DRAFTS_DIR) / f"DRAFT_{date_str}_{safe_subj}.eml")

    eml_content = (
        f"To: {to_email}\r\n"
        f"Subject: {subject}\r\n"
        f"MIME-Version: 1.0\r\n"
        f"Content-Type: text/plain; charset=UTF-8\r\n"
        f"X-CTTX-Status: DRAFT-PENDING-HUMAN-REVIEW\r\n"
        f"X-CTTX-AutoSend: NEVER\r\n"
        f"\r\n"
        f"{body}"
    )
    Path(eml_path).write_text(eml_content, encoding="utf-8")
    return eml_path


def create_assessment_draft(
    property_id: str,
    property_name: str,
    to_email: str,
    contact_name: Optional[str] = None,
    organisation: Optional[str] = None,
    snapshot_path: Optional[str] = None,
    specific_observation: str = "",
    db_path: str = DB_PATH,
) -> dict:
    """
    Create an assessment-offer email draft.
    NEVER sends automatically. Human must review and send.
    """
    email_content = _build_email_body(
        property_name, contact_name, organisation, snapshot_path,
        specific_observation
    )

    attachments = []
    if snapshot_path and Path(snapshot_path).exists():
        attachments.append(snapshot_path)

    # Try Outlook (Windows); fall back to .eml file
    outlook_result = _stage_to_outlook_windows(
        to_email, email_content["subject"], email_content["body"], attachments
    )

    eml_path = None
    if outlook_result["status"] != "PASS":
        eml_path = _save_eml_draft(
            to_email, email_content["subject"], email_content["body"], attachments
        )

    # Always stage in database regardless of method
    conn = get_connection(db_path)
    draft_id = new_id("DRAFT")

    # Find contact_id if available
    contact_row = conn.execute(
        "SELECT contact_id FROM commercial_contacts WHERE property_id=? LIMIT 1",
        (property_id,)
    ).fetchone()
    contact_id = contact_row["contact_id"] if contact_row else None

    conn.execute("""
        INSERT INTO outreach_drafts
          (draft_id,property_id,contact_id,subject,body_path,status)
        VALUES (?,?,?,?,?,?)
    """, (draft_id, property_id, contact_id,
          email_content["subject"],
          eml_path or "outlook_drafts_folder",
          "PENDING_REVIEW"))
    conn.commit()
    conn.close()

    return {
        "status": "PASS",
        "draft_id": draft_id,
        "method": outlook_result.get("method", "eml_file"),
        "draft_path": eml_path,
        "subject": email_content["subject"],
        "staged_for_human_review": True,
        "auto_send": False,  # ALWAYS false — immutable
        "created_at": now_iso(),
        "SAFETY_NOTE": "This draft requires explicit human review and manual send action.",
    }


def list_pending_drafts(db_path: str = DB_PATH) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT d.draft_id, d.subject, d.status, d.created_at,
               p.name as property_name
        FROM outreach_drafts d
        LEFT JOIN properties p ON d.property_id = p.property_id
        WHERE d.status = 'PENDING_REVIEW'
        ORDER BY d.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_draft_sent_by_human(draft_id: str, sent_by: str,
                              db_path: str = DB_PATH) -> dict:
    """
    Records that a human has sent the draft.
    This function must only be called by explicit human confirmation.
    """
    conn = get_connection(db_path)
    conn.execute("""
        UPDATE outreach_drafts
        SET status='SENT', sent_at=?, sent_by=?
        WHERE draft_id=? AND status='PENDING_REVIEW'
    """, (now_iso(), sent_by, draft_id))
    conn.commit()
    conn.close()
    return {"status": "RECORDED", "draft_id": draft_id, "sent_by": sent_by}
