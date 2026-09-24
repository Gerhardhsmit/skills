"""CTTX National Discovery Engine — batch ingestion from OSM and structured sources."""

import json
import csv
import time
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import overpy
import requests

# overpy >= 0.7 renamed API to Overpass
if not hasattr(overpy, "API"):
    overpy.API = overpy.Overpass

sys_path = str(Path(__file__).parent.parent)
import sys
sys.path.insert(0, sys_path)
from db.database import get_connection, upsert_property, log_health, now_iso, DB_PATH

log = logging.getLogger("cttx.discovery")

# ─── OSM QUERY TEMPLATES ─────────────────────────────────────────────────────

OSM_QUERIES = {
    "game_reserve": """
        [out:json][timeout:60];
        area["ISO3166-1"="ZA"]->.za;
        (
          nwr["leisure"="nature_reserve"](area.za);
          nwr["boundary"="protected_area"](area.za);
          nwr["landuse"="conservation"](area.za);
        );
        out center tags;
    """,
    "wind_farm": """
        [out:json][timeout:60];
        area["ISO3166-1"="ZA"]->.za;
        (
          nwr["power"="generator"]["generator:source"="wind"](area.za);
          nwr["plant:source"="wind"](area.za);
        );
        out center tags;
    """,
    "solar_farm": """
        [out:json][timeout:60];
        area["ISO3166-1"="ZA"]->.za;
        (
          nwr["power"="generator"]["generator:source"="solar"](area.za);
          nwr["plant:source"="solar"](area.za);
        );
        out center tags;
    """,
    "mine": """
        [out:json][timeout:60];
        area["ISO3166-1"="ZA"]->.za;
        (
          nwr["landuse"="quarry"](area.za);
          nwr["industrial"="mine"](area.za);
        );
        out center tags;
    """,
    "lodge_resort": """
        [out:json][timeout:60];
        area["ISO3166-1"="ZA"]->.za;
        (
          nwr["tourism"="hotel"](area.za);
          nwr["tourism"="resort"](area.za);
          nwr["tourism"="guest_house"](area.za);
        );
        out center tags;
    """,
    "hospital": """
        [out:json][timeout:60];
        area["ISO3166-1"="ZA"]->.za;
        (
          nwr["amenity"="hospital"](area.za);
        );
        out center tags;
    """,
    "substation": """
        [out:json][timeout:60];
        area["ISO3166-1"="ZA"]->.za;
        (
          nwr["power"="substation"](area.za);
        );
        out center tags;
    """,
}

PROPERTY_TYPE_MAP = {
    "game_reserve": "game_reserve",
    "wind_farm": "wind_project",
    "solar_farm": "solar_project",
    "mine": "mine",
    "lodge_resort": "lodge",
    "hospital": "hospital",
    "substation": "utility",
}


def _lat_lon_from_element(el) -> tuple[float | None, float | None]:
    if hasattr(el, "lat"):
        return el.lat, el.lon
    if hasattr(el, "center_lat") and el.center_lat:
        return el.center_lat, el.center_lon
    return None, None


def _province_from_tags(tags: dict) -> str | None:
    return tags.get("addr:province") or tags.get("is_in:province") or tags.get("addr:state")


def query_osm(category: str, api: overpy.API = None) -> list[dict]:
    """Run one OSM Overpass query, return normalised property dicts."""
    if category not in OSM_QUERIES:
        raise ValueError(f"Unknown OSM category: {category}")
    if api is None:
        api = overpy.Overpass()

    query = OSM_QUERIES[category]
    prop_type = PROPERTY_TYPE_MAP.get(category, "other")

    results = []
    try:
        result = api.query(query)
        elements = list(result.nodes) + list(result.ways) + list(result.relations)
        for el in elements:
            tags = el.tags or {}
            lat, lon = _lat_lon_from_element(el)
            if lat is None:
                continue
            name = (tags.get("name") or tags.get("operator") or
                    tags.get("ref") or f"{prop_type.upper()}-{el.id}")
            results.append({
                "name": name,
                "property_type": prop_type,
                "latitude": float(lat),
                "longitude": float(lon),
                "province": _province_from_tags(tags),
                "source": "osm",
                "source_reference": f"osm:{el.id}",
                "discovery_date": now_iso()[:10],
                "enrichment_status": "RAW",
                "confidence": "LOW",
                "notes": f"OSM id={el.id} category={category}",
            })
    except Exception as exc:
        log.error("OSM query failed for %s: %s", category, exc)
    return results


def ingest_csv_batch(csv_path: str) -> list[dict]:
    """
    Ingest a CSV property batch.
    Required columns: name, latitude, longitude, property_type
    Optional: province, municipality, area_ha, website, notes
    """
    records = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if not row.get("name") or not row.get("latitude"):
                continue
            records.append({
                "name": row["name"].strip(),
                "property_type": row.get("property_type", "other").strip(),
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "province": row.get("province", "").strip() or None,
                "municipality": row.get("municipality", "").strip() or None,
                "area_ha": float(row["area_ha"]) if row.get("area_ha") else None,
                "source": "manual_batch",
                "source_reference": f"csv:{Path(csv_path).name}",
                "discovery_date": now_iso()[:10],
                "enrichment_status": "RAW",
                "confidence": "LOW",
                "notes": row.get("notes", "").strip() or None,
            })
    return records


def ingest_json_batch(json_path: str) -> list[dict]:
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    records = data if isinstance(data, list) else data.get("properties", [])
    for r in records:
        r.setdefault("source", "json_batch")
        r.setdefault("source_reference", f"json:{Path(json_path).name}")
        r.setdefault("discovery_date", now_iso()[:10])
        r.setdefault("enrichment_status", "RAW")
        r.setdefault("confidence", "LOW")
    return records


def deduplicate(records: list[dict], conn) -> tuple[list[dict], int]:
    """Remove records whose OSM source_reference already exists in the DB."""
    new_records = []
    skipped = 0
    for r in records:
        ref = r.get("source_reference")
        if ref and ref.startswith("osm:"):
            exists = conn.execute(
                "SELECT 1 FROM properties WHERE source_reference=?", (ref,)
            ).fetchone()
            if exists:
                skipped += 1
                continue
        new_records.append(r)
    return new_records, skipped


def run_batch_discovery(
    sources: list[str] = None,
    csv_path: str = None,
    json_path: str = None,
    db_path: str = DB_PATH,
) -> dict:
    """
    Main entry: ingest from OSM categories and/or file inputs.
    sources: list of OSM category keys, e.g. ["game_reserve","wind_farm"]
    """
    started = time.time()
    conn = get_connection(db_path)
    api = overpy.Overpass()

    all_records: list[dict] = []

    if sources:
        for cat in sources:
            log.info("Querying OSM: %s", cat)
            records = query_osm(cat, api)
            log.info("  → %d records from %s", len(records), cat)
            all_records.extend(records)
            time.sleep(1)  # be polite to Overpass

    if csv_path:
        all_records.extend(ingest_csv_batch(csv_path))

    if json_path:
        all_records.extend(ingest_json_batch(json_path))

    unique_records, skipped = deduplicate(all_records, conn)

    written = 0
    errors = 0
    for r in unique_records:
        try:
            upsert_property(conn, r)
            written += 1
        except Exception as exc:
            log.error("Failed to write property %s: %s", r.get("name"), exc)
            errors += 1

    elapsed = time.time() - started
    log_health(conn, "discovery_engine", "PASS" if errors == 0 else "PARTIAL",
               f"written={written} skipped={skipped} errors={errors}")
    conn.close()

    return {
        "status": "PASS" if errors == 0 else "PARTIAL",
        "total_input": len(all_records),
        "deduplicated_skipped": skipped,
        "written": written,
        "errors": errors,
        "elapsed_s": round(elapsed, 2),
        "checked_at": now_iso(),
    }
