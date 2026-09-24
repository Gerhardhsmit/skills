"""
CTTX Terrain & LOS Engine
Queries local SRTM terrain API (30m), calculates Fresnel zones, identifies
candidate high sites, computes LOS and upstream paths.

Local API assumed at CTTX_TERRAIN_API env var, default http://localhost:8080
Profile endpoint: GET /elevation?lat=XX&lon=YY  → {"elevation_m": NNN}
Transect endpoint: GET /profile?lat1=&lon1=&lat2=&lon2=&samples=N
  → {"profile": [{"lat":,"lon":,"elevation_m":}, ...]}
"""

import os
import math
import time
import logging
import requests
from typing import Optional
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from db.database import (get_connection, upsert_observation,
                         DB_PATH, now_iso, new_id)

log = logging.getLogger("cttx.terrain")

TERRAIN_API = os.environ.get("CTTX_TERRAIN_API", "http://localhost:8080")
EARTH_RADIUS_M = 6_371_000


# ─── SRTM API CALLS ──────────────────────────────────────────────────────────

def get_elevation(lat: float, lon: float, timeout: int = 10) -> Optional[float]:
    """Query local SRTM API for a single point elevation."""
    try:
        r = requests.get(f"{TERRAIN_API}/elevation",
                         params={"lat": lat, "lon": lon}, timeout=timeout)
        r.raise_for_status()
        return float(r.json()["elevation_m"])
    except Exception as exc:
        log.warning("Elevation query failed lat=%.5f lon=%.5f: %s", lat, lon, exc)
        return None


def get_terrain_profile(lat1: float, lon1: float,
                        lat2: float, lon2: float,
                        samples: int = 100, timeout: int = 30) -> Optional[list[dict]]:
    """Query local SRTM API for a terrain transect."""
    try:
        r = requests.get(f"{TERRAIN_API}/profile",
                         params={"lat1": lat1, "lon1": lon1,
                                 "lat2": lat2, "lon2": lon2,
                                 "samples": samples},
                         timeout=timeout)
        r.raise_for_status()
        return r.json()["profile"]
    except Exception as exc:
        log.warning("Profile query failed: %s", exc)
        return None


def api_health_check() -> dict:
    """Test connectivity to the terrain API."""
    try:
        r = requests.get(f"{TERRAIN_API}/elevation",
                         params={"lat": -26.2, "lon": 28.0}, timeout=5)
        r.raise_for_status()
        elev = r.json().get("elevation_m")
        return {"status": "PASS", "api": TERRAIN_API,
                "test_elevation_m": elev, "checked_at": now_iso()}
    except Exception as exc:
        return {"status": "FAIL", "api": TERRAIN_API,
                "error": str(exc), "checked_at": now_iso()}


# ─── GEOMETRY HELPERS ────────────────────────────────────────────────────────

def haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Distance in metres between two WGS84 points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bearing_deg(lat1, lon1, lat2, lon2) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    x = math.sin(dlam) * math.cos(phi2)
    y = math.cos(phi1)*math.sin(phi2) - math.sin(phi1)*math.cos(phi2)*math.cos(dlam)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def fresnel_radius_m(d1_m: float, d2_m: float, freq_ghz: float, zone: int = 1) -> float:
    """Fresnel zone radius at a transect point."""
    lam = 0.3 / freq_ghz  # wavelength in metres
    d = d1_m + d2_m
    return zone * math.sqrt(lam * d1_m * d2_m / d)


# ─── LOS CALCULATION ─────────────────────────────────────────────────────────

def calculate_los(lat_a: float, lon_a: float, elev_a_m: float, ht_a_m: float,
                  lat_b: float, lon_b: float, elev_b_m: float, ht_b_m: float,
                  freq_ghz: float = 5.8,
                  profile: list[dict] = None) -> dict:
    """
    Calculate LOS and Fresnel clearance between two sites.
    Returns status: CLEAR | MARGINAL | OBSTRUCTED | UNKNOWN
    """
    dist_m = haversine_m(lat_a, lon_a, lat_b, lon_b)
    dist_km = dist_m / 1000

    ant_a_m = elev_a_m + ht_a_m
    ant_b_m = elev_b_m + ht_b_m

    if not profile:
        return {
            "distance_km": round(dist_km, 3),
            "bearing_deg": round(bearing_deg(lat_a, lon_a, lat_b, lon_b), 1),
            "los_status": "UNKNOWN",
            "clearance_f1_m": None,
            "confidence": "LOW",
            "note": "No terrain profile available",
        }

    # Step through profile and find worst-case Fresnel clearance
    min_clearance = float("inf")
    obstruction_detail = None

    for i, pt in enumerate(profile):
        if i == 0 or i == len(profile) - 1:
            continue
        d_total = len(profile) - 1
        d1_frac = i / d_total
        d2_frac = 1 - d1_frac
        d1_m = d1_frac * dist_m
        d2_m = d2_frac * dist_m

        # Height of straight line at this point
        los_height = ant_a_m + (ant_b_m - ant_a_m) * d1_frac
        terrain_h = pt["elevation_m"]
        f1 = fresnel_radius_m(d1_m, d2_m, freq_ghz, zone=1)
        clearance = los_height - terrain_h - f1

        if clearance < min_clearance:
            min_clearance = clearance
            obstruction_detail = {
                "lat": pt["lat"], "lon": pt["lon"],
                "terrain_m": terrain_h,
                "los_m": round(los_height, 1),
                "f1_m": round(f1, 1),
                "clearance_m": round(clearance, 1),
            }

    if min_clearance == float("inf"):
        los_status = "UNKNOWN"
    elif min_clearance >= 0:
        los_status = "CLEAR"
    elif min_clearance >= -5:
        los_status = "MARGINAL"
    else:
        los_status = "OBSTRUCTED"

    return {
        "distance_km": round(dist_km, 3),
        "bearing_deg": round(bearing_deg(lat_a, lon_a, lat_b, lon_b), 1),
        "los_status": los_status,
        "clearance_f1_m": round(min_clearance, 1) if min_clearance != float("inf") else None,
        "worst_point": obstruction_detail,
        "confidence": "MEDIUM" if profile else "LOW",
        "frequency_ghz": freq_ghz,
    }


# ─── CANDIDATE HIGH-SITE SEARCH ──────────────────────────────────────────────

def _grid_points(lat: float, lon: float, radius_km: float,
                 step_km: float = 0.5) -> list[tuple[float, float]]:
    """Generate a grid of candidate points around a centre."""
    step_lat = step_km / 111.0
    step_lon = step_km / (111.0 * math.cos(math.radians(lat)))
    pts = []
    n = int(radius_km / step_km) + 1
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            cand_lat = lat + i * step_lat
            cand_lon = lon + j * step_lon
            if haversine_m(lat, lon, cand_lat, cand_lon) <= radius_km * 1000:
                pts.append((cand_lat, cand_lon))
    return pts


def find_candidate_high_sites(property_lat: float, property_lon: float,
                               search_radius_km: float = 5.0,
                               top_n: int = 5) -> list[dict]:
    """
    Sample a grid around the property, query elevations, return top-N highest points.
    Falls back gracefully if terrain API is unavailable.
    """
    candidates = []
    grid = _grid_points(property_lat, property_lon, search_radius_km, step_km=0.5)

    for lat, lon in grid:
        elev = get_elevation(lat, lon)
        if elev is not None:
            dist = haversine_m(property_lat, property_lon, lat, lon)
            candidates.append({
                "latitude": lat,
                "longitude": lon,
                "elevation_m": elev,
                "distance_from_property_m": round(dist, 0),
            })

    if not candidates:
        return []

    candidates.sort(key=lambda x: x["elevation_m"], reverse=True)
    return candidates[:top_n]


# ─── FULL PROPERTY INTELLIGENCE RUN ──────────────────────────────────────────

def run_property_intelligence(property_id: str, lat: float, lon: float,
                               db_path: str = DB_PATH,
                               freq_ghz: float = 5.8) -> dict:
    """
    Full terrain intelligence pass for one property.
    Queries terrain API, finds high sites, calculates candidate LOS links,
    writes observations to database.
    Returns a summary dict.
    """
    started = time.time()
    conn = get_connection(db_path)
    results = {
        "property_id": property_id,
        "started_at": now_iso(),
        "site_elevation_m": None,
        "candidate_high_sites": [],
        "los_links": [],
        "api_available": False,
        "confidence": "LOW",
    }

    # 1. Site elevation
    elev = get_elevation(lat, lon)
    if elev is not None:
        results["site_elevation_m"] = elev
        results["api_available"] = True
        upsert_observation(conn, property_id, "terrain", "site_elevation_m",
                           elev, "m", "srtm_local", "MEDIUM")

    # 2. Candidate high sites
    high_sites = find_candidate_high_sites(lat, lon, search_radius_km=5.0, top_n=5)
    results["candidate_high_sites"] = high_sites

    from db.database import new_id as _new_id
    for idx, hs in enumerate(high_sites):
        site_id = _new_id("SITE")
        conn.execute("""
            INSERT OR IGNORE INTO infrastructure_sites
              (site_id,property_id,site_name,site_type,latitude,longitude,
               elevation_m,classification,source,confidence)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (site_id, property_id,
              f"HighSite-{idx+1}",
              "candidate_high",
              hs["latitude"], hs["longitude"], hs["elevation_m"],
              "Engineering_candidate", "srtm_local", "LOW"))

        # 3. LOS from property to each candidate high site
        if elev is not None:
            profile = get_terrain_profile(lat, lon, hs["latitude"], hs["longitude"])
            los = calculate_los(
                lat, lon, elev, 0,
                hs["latitude"], hs["longitude"], hs["elevation_m"], 30,
                freq_ghz=freq_ghz, profile=profile
            )
            los["site_a"] = "property_centre"
            los["site_b"] = f"HighSite-{idx+1}"
            results["los_links"].append(los)

            link_id = _new_id("LINK")
            conn.execute("""
                INSERT OR IGNORE INTO los_links
                  (link_id,property_id,distance_km,bearing_deg,
                   clearance_f1_m,los_status,frequency_ghz,
                   calculation_source,confidence)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (link_id, property_id,
                  los["distance_km"], los["bearing_deg"],
                  los.get("clearance_f1_m"), los["los_status"],
                  freq_ghz, "srtm_local", los["confidence"]))

    conn.commit()
    conn.close()

    results["elapsed_s"] = round(time.time() - started, 2)
    results["confidence"] = "MEDIUM" if results["api_available"] else "LOW"
    return results
