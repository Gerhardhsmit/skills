"""CTTX National Infrastructure Index — database connection and utilities."""

import sqlite3
import os
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = os.environ.get("CTTX_DB_PATH",
    str(Path(__file__).parent.parent.parent / "data" / "cttx_nii.db"))
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database(db_path: str = DB_PATH) -> dict:
    """Initialise database from schema. Idempotent."""
    conn = get_connection(db_path)
    schema = SCHEMA_PATH.read_text()
    conn.executescript(schema)
    conn.commit()

    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    conn.close()
    return {
        "status": "PASS",
        "db_path": db_path,
        "tables": tables,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def new_id(prefix: str = "") -> str:
    return (prefix + "-" if prefix else "") + str(uuid.uuid4())[:8].upper()


def property_id(province: str) -> str:
    pcode = (province or "XX")[:2].upper()
    date = datetime.now().strftime("%Y%m%d")
    return f"CTTX-{pcode}-{date}-{str(uuid.uuid4())[:6].upper()}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_property(conn: sqlite3.Connection, props: dict) -> str:
    pid = props.get("property_id") or property_id(props.get("province", "XX"))
    existing = conn.execute(
        "SELECT property_id FROM properties WHERE property_id=?", (pid,)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE properties SET updated_at=? WHERE property_id=?",
            (now_iso(), pid)
        )
        _audit(conn, "property", pid, "UPDATE", None, props.get("enrichment_status"))
    else:
        conn.execute("""
            INSERT INTO properties
              (property_id,name,property_type,province,municipality,
               latitude,longitude,area_ha,source,source_reference,
               discovery_date,enrichment_status,opportunity_profile,
               confidence,notes)
            VALUES
              (:property_id,:name,:property_type,:province,:municipality,
               :latitude,:longitude,:area_ha,:source,:source_reference,
               :discovery_date,:enrichment_status,:opportunity_profile,
               :confidence,:notes)
        """, {
            "property_id": pid,
            "name": props.get("name", "Unknown"),
            "property_type": props.get("property_type", "other"),
            "province": props.get("province"),
            "municipality": props.get("municipality"),
            "latitude": props.get("latitude"),
            "longitude": props.get("longitude"),
            "area_ha": props.get("area_ha"),
            "source": props.get("source", "manual"),
            "source_reference": props.get("source_reference"),
            "discovery_date": props.get("discovery_date", now_iso()[:10]),
            "enrichment_status": props.get("enrichment_status", "RAW"),
            "opportunity_profile": props.get("opportunity_profile", "UNKNOWN"),
            "confidence": props.get("confidence", "LOW"),
            "notes": props.get("notes"),
        })
        _audit(conn, "property", pid, "INSERT", None, props.get("name"))
    conn.commit()
    return pid


def upsert_observation(conn: sqlite3.Connection, property_id: str,
                       obs_type: str, key: str, value, unit: str = None,
                       source: str = "cttx-engine", confidence: str = "LOW",
                       notes: str = None):
    oid = new_id("OBS")
    existing = conn.execute(
        "SELECT obs_id FROM engineering_observations WHERE property_id=? AND obs_type=? AND obs_key=?",
        (property_id, obs_type, key)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE engineering_observations SET obs_value=?,unit=?,source=?,confidence=?,notes=?,created_at=? WHERE obs_id=?",
            (str(value), unit, source, confidence, notes, now_iso(), existing["obs_id"])
        )
    else:
        conn.execute("""
            INSERT INTO engineering_observations
              (obs_id,property_id,obs_type,obs_key,obs_value,unit,source,confidence,notes)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (oid, property_id, obs_type, key, str(value), unit, source, confidence, notes))
    conn.commit()


def get_nii_stats(conn: sqlite3.Connection) -> dict:
    stats = {}
    stats["total_properties"] = conn.execute(
        "SELECT COUNT(*) FROM properties").fetchone()[0]
    stats["by_province"] = dict(conn.execute(
        "SELECT province, COUNT(*) FROM properties GROUP BY province").fetchall())
    stats["by_type"] = dict(conn.execute(
        "SELECT property_type, COUNT(*) FROM properties GROUP BY property_type").fetchall())
    stats["by_enrichment"] = dict(conn.execute(
        "SELECT enrichment_status, COUNT(*) FROM properties GROUP BY enrichment_status").fetchall())
    stats["by_opportunity"] = dict(conn.execute(
        "SELECT opportunity_profile, COUNT(*) FROM properties GROUP BY opportunity_profile").fetchall())
    stats["assessments_complete"] = conn.execute(
        "SELECT COUNT(*) FROM assessments WHERE status='COMPLETE'").fetchone()[0]
    stats["drafts_pending"] = conn.execute(
        "SELECT COUNT(*) FROM outreach_drafts WHERE status='PENDING_REVIEW'").fetchone()[0]
    stats["tenders_found"] = conn.execute(
        "SELECT COUNT(*) FROM tenders").fetchone()[0]
    return stats


def log_health(conn: sqlite3.Connection, component: str, status: str, detail: str = None):
    conn.execute(
        "INSERT INTO system_health (component,status,detail) VALUES (?,?,?)",
        (component, status, detail)
    )
    conn.commit()


def _audit(conn, entity_type, entity_id, action, old_val, new_val):
    conn.execute(
        "INSERT INTO audit_trail (entity_type,entity_id,action,old_value,new_value) VALUES (?,?,?,?,?)",
        (entity_type, entity_id, action,
         json.dumps(old_val) if old_val else None,
         json.dumps(new_val) if new_val else None)
    )
