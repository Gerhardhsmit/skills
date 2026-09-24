"""
CTTX Daily Commercial Brief Generator
Produces a structured daily brief: money, sales, comms, buyer signals, system health.
"""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from db.database import get_connection, get_nii_stats, DB_PATH, now_iso, log_health
from terrain.terrain_engine import api_health_check


def _days_since(iso_str: str) -> int:
    if not iso_str:
        return 9999
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return (datetime.now().astimezone() - dt).days
    except Exception:
        return 9999


def generate_daily_brief(db_path: str = DB_PATH) -> str:
    started = time.time()
    conn = get_connection(db_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "═" * 62,
        f"  CTTX DAILY COMMERCIAL BRIEF  —  {now}",
        "═" * 62,
        "",
    ]

    # ── MONEY WAITING ─────────────────────────────────────────────────────────
    lines += ["▌ MONEY WAITING", "─" * 40]
    # Outstanding invoices — placeholder for Outlook/Pastel integration
    lines.append("  Outstanding invoices:     [connect to accounting system]")
    lines.append("  Debtor follow-ups:        [connect to accounting system]")

    # Tenders awaiting outcome
    tenders_pending = conn.execute(
        "SELECT reference, issuing_org, submission_date FROM tenders "
        "WHERE status='SUBMITTED' ORDER BY submission_date DESC"
    ).fetchall()
    if tenders_pending:
        lines.append(f"  Tenders awaiting outcome: {len(tenders_pending)}")
        for t in tenders_pending[:5]:
            days = _days_since(t["submission_date"])
            lines.append(f"    • {t['reference'] or '?'} | {t['issuing_org'] or '?'} | {days}d since submission")
    else:
        lines.append("  Tenders awaiting outcome: None recorded")

    # Proposals awaiting decision
    proposals = conn.execute(
        "SELECT COUNT(*) FROM assessments WHERE status='COMPLETE'"
    ).fetchone()[0]
    lines.append(f"  Completed assessments:    {proposals}")
    lines.append("")

    # ── SALES ─────────────────────────────────────────────────────────────────
    lines += ["▌ SALES PIPELINE", "─" * 40]
    stats = get_nii_stats(conn)
    lines.append(f"  Total properties discovered: {stats['total_properties']}")

    high_opp = stats.get("by_opportunity", {}).get("HIGH", 0)
    mod_opp  = stats.get("by_opportunity", {}).get("MODERATE", 0)
    lines.append(f"  HIGH opportunity properties: {high_opp}")
    lines.append(f"  MODERATE opportunity:        {mod_opp}")

    pending_assessments = conn.execute(
        "SELECT COUNT(*) FROM assessments WHERE status='PENDING'"
    ).fetchone()[0]
    lines.append(f"  Assessments pending:         {pending_assessments}")

    lines.append("")
    lines.append("  By type:")
    for ptype, count in sorted(stats.get("by_type", {}).items()):
        lines.append(f"    {ptype:<30} {count}")
    lines.append("")

    # ── COMMUNICATION ─────────────────────────────────────────────────────────
    lines += ["▌ COMMUNICATION", "─" * 40]
    pending_drafts = conn.execute(
        "SELECT d.draft_id, d.subject, d.created_at, p.name "
        "FROM outreach_drafts d LEFT JOIN properties p ON d.property_id=p.property_id "
        "WHERE d.status='PENDING_REVIEW' ORDER BY d.created_at DESC"
    ).fetchall()

    stale_drafts = [d for d in pending_drafts if _days_since(d["created_at"]) >= 2]
    if stale_drafts:
        lines.append(f"  ⚠ Drafts older than 48h:  {len(stale_drafts)}")
        for d in stale_drafts[:5]:
            lines.append(f"    • [{d['draft_id']}] {d['subject'][:50]}")
    else:
        lines.append(f"  Drafts pending review:    {len(pending_drafts)}")

    lines.append("  Unanswered enquiries:     [connect to Outlook/CRM]")
    lines.append("")

    # ── BUYER SIGNALS ─────────────────────────────────────────────────────────
    lines += ["▌ BUYER SIGNALS", "─" * 40]
    lines.append("  New tender releases:      [connect to eTenders/CIDB]")

    # Recent OSM discoveries (last 7 days)
    recent = conn.execute(
        "SELECT COUNT(*) FROM properties "
        "WHERE discovery_date >= date('now','-7 days')"
    ).fetchone()[0]
    lines.append(f"  New properties discovered (7d): {recent}")

    # High-opportunity uncontacted
    uncontacted = conn.execute(
        "SELECT COUNT(*) FROM properties p "
        "WHERE p.opportunity_profile IN ('HIGH','MODERATE') "
        "AND NOT EXISTS (SELECT 1 FROM outreach_drafts d WHERE d.property_id=p.property_id)"
    ).fetchone()[0]
    lines.append(f"  Qualified properties with no draft: {uncontacted}")
    lines.append("")

    # ── SYSTEM HEALTH ─────────────────────────────────────────────────────────
    lines += ["▌ SYSTEM HEALTH", "─" * 40]

    db_ok = stats["total_properties"] >= 0
    lines.append(f"  Database:          {'PASS' if db_ok else 'FAIL'}")
    lines.append(f"    Path: {db_path}")
    lines.append(f"    Properties: {stats['total_properties']}")

    terrain = api_health_check()
    lines.append(f"  Terrain API:       {terrain['status']}")
    if terrain.get("error"):
        lines.append(f"    Error: {terrain['error']}")
    elif terrain.get("test_elevation_m"):
        lines.append(f"    Test point elevation: {terrain['test_elevation_m']} m")

    lines.append("  PDF engine:        [run diagnostic]")
    lines.append("  KMZ engine:        [run diagnostic]")
    lines.append("  Outlook:           [run diagnostic]")
    lines.append("  Discovery engine:  [run diagnostic]")
    lines.append("")

    # ── RECENT SYSTEM HEALTH LOG ──────────────────────────────────────────────
    recent_health = conn.execute(
        "SELECT component, status, detail, checked_at FROM system_health "
        "ORDER BY checked_at DESC LIMIT 10"
    ).fetchall()
    if recent_health:
        lines.append("  Recent health checks:")
        for h in recent_health:
            lines.append(f"    {h['component']:<25} {h['status']:<10} {h['checked_at'][:16]}")

    lines += [
        "",
        "─" * 62,
        f"  Brief generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"  Engine elapsed:  {round(time.time()-started,2)}s",
        "═" * 62,
    ]

    log_health(conn, "daily_brief", "PASS", f"generated at {now}")
    conn.close()
    return "\n".join(lines)
