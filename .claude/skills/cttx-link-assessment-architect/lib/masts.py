#!/usr/bin/env python3
"""CTTX infrastructure intelligence layer — the historical mast dataset (~14,400 BTS sites).

    python3 masts.py build [KMZ_DIR]                  → data/private/masts/mast_index.json
    python3 masts.py near <lat> <lon> [radius_km] [n]  → nearest candidates (text)

Sources (carrier-confidential; kept in git-ignored data/private/masts/):
  * "BTS Site Location Report" KMZ — ~14,439 sites: name, Atoll ID, lat/lon, service level, BS number
  * "Afrigis New BTS Sites List 26 November 2024" KMZ — 1,465 sites with owner, backhaul
    (fibre/MW, ring/not-ring), POC type, Radwin/CBNL/SIAE presence, availability
Every record is HISTORICAL: it proves the site was in a carrier inventory, not that it is live,
available or usable. Status is never upgraded here; field/commercial confirmation does that.
"""
import glob
import json
import math
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo import bearing_deg, haversine_km  # noqa: E402

import paths  # noqa: E402

DEFAULT_DIR = paths.mast_kmz_dir() or paths.MAST_WRITE_DIR
INDEX = paths.mast_index()
WRITE_INDEX = os.path.join(paths.MAST_WRITE_DIR, "mast_index.json")


def _kml_text(path):
    if path.lower().endswith(".kmz"):
        z = zipfile.ZipFile(path)
        return z.read(next(n for n in z.namelist() if n.endswith(".kml"))).decode("utf-8", "replace")
    return open(path, encoding="utf-8", errors="replace").read()


def _f(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def build(kmz_dir=DEFAULT_DIR):
    sites = {}
    afrigis = {}
    for path in glob.glob(os.path.join(kmz_dir, "*.km[lz]")):
        s = _kml_text(path)
        base = os.path.basename(path)
        date = (re.search(r"(\d{1,2} \w+ 20\d\d)", base) or [None])[0]
        for pm in s.split("<Placemark>")[1:]:
            name = (re.search(r"<name>(.*?)</name>", pm) or [None, ""])[1]
            simple = dict(re.findall(r'<SimpleData name="([^"]+)">(.*?)</SimpleData>', pm))
            data = {k: v for k, v in re.findall(r'<Data name="([^"]+)">.*?<value>(.*?)</value>', pm, re.S)}
            coords = re.search(r"<coordinates>\s*([-\d.]+),([-\d.]+)", pm)
            if simple:  # BTS Site Location Report
                sid = simple.get("ATOLL_SITE_ID") or name
                lat, lon = (float(coords.group(2)), float(coords.group(1))) if coords else (_f(simple.get("LATITUDE")), _f(simple.get("LONGITUDE")))
                sites[sid] = {"id": sid, "name": simple.get("ATOLL_NAME") or name, "lat": lat, "lon": lon,
                              "service_level": simple.get("SERVICE_LEVEL"), "bs_number": simple.get("BS_NUMBER"),
                              "source": base, "status": "HISTORICAL"}
            elif data:  # Afrigis attributes
                sid = data.get("Atol ID") or name
                lat, lon = _f(data.get("latitude")), _f(data.get("longitude"))
                if (lat is None or lon is None) and coords:
                    lat, lon = float(coords.group(2)), float(coords.group(1))
                afrigis[sid] = {
                    "name": data.get("Site name") or name, "lat": lat, "lon": lon, "region": data.get("Region"),
                    "owner": data.get("Site Owner"), "classification": data.get("Classifica"),
                    "backhaul": data.get("Backhaul C"), "poc_type": data.get("POC Type"),
                    "location_type": data.get("Location E"), "termination": data.get("Terminatin"),
                    "radwin_ptp": data.get("Radwin PtP") == "1", "radwin_sectors": data.get("Radwin Sec") == "1",
                    "cbnl_sectors": data.get("CBNL Secto") == "1", "siae_links": _f(data.get("# SIAE Lin")),
                    "avg_availability": data.get("Average Ma"), "dataset_date": date, "source": base}
    # merge: Afrigis enriches BTS records; Afrigis-only sites are added
    for sid, a in afrigis.items():
        if sid in sites:
            sites[sid]["attrs"] = a
        else:
            sites[sid] = {"id": sid, "name": a["name"], "lat": a["lat"], "lon": a["lon"], "service_level": None,
                          "bs_number": None, "source": a["source"], "status": "HISTORICAL", "attrs": a}
    out = [s for s in sites.values() if s["lat"] is not None and s["lon"] is not None and -35.5 < s["lat"] < -21.5]
    target = INDEX if os.access(os.path.dirname(INDEX) or ".", os.W_OK) else WRITE_INDEX
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w") as f:
        json.dump({"built_from": sorted(os.path.basename(p) for p in glob.glob(os.path.join(kmz_dir, "*.km[lz]"))),
                   "count": len(out), "enriched": sum("attrs" in s for s in out), "sites": out}, f)
    return len(out), sum("attrs" in s for s in out)


_CACHE = {}


def load(path=None):
    path = path or (INDEX if os.path.exists(INDEX) else WRITE_INDEX)
    if not os.path.exists(path):
        if not paths.mast_kmz_dir():
            raise FileNotFoundError("No mast dataset: put the carrier KMZs in data/masts/ (skill) or set CTTX_MAST_DIR")
        build(paths.mast_kmz_dir())  # auto-build on first use
        path = WRITE_INDEX if os.path.exists(WRITE_INDEX) else INDEX
    if path not in _CACHE:
        with open(path) as f:
            _CACHE[path] = json.load(f)["sites"]
    return _CACHE[path]


def near(lat, lon, radius_km=40, n=15, path=None):
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(0.2, math.cos(math.radians(lat))))
    hits = []
    for s in load(path):
        if abs(s["lat"] - lat) > dlat or abs(s["lon"] - lon) > dlon:
            continue
        d = haversine_km(lat, lon, s["lat"], s["lon"])
        if d <= radius_km:
            hits.append(dict(s, distance_km=round(d, 2), bearing_deg=round(bearing_deg(lat, lon, s["lat"], s["lon"]))))
    return sorted(hits, key=lambda h: h["distance_km"])[:n]


def backhaul_notes(s):
    """Plain-language backhaul evidence from dataset attributes (still HISTORICAL)."""
    a = s.get("attrs") or {}
    notes = []
    if a.get("owner"):
        notes.append(f"owner {a['owner']}")
    if a.get("backhaul"):
        notes.append(f"backhaul {a['backhaul']}")
    if a.get("poc_type"):
        notes.append(a["poc_type"])
    if a.get("radwin_sectors") or a.get("radwin_ptp"):
        notes.append("Radwin equipment listed")
    if a.get("siae_links"):
        notes.append(f"{int(a['siae_links'])} SIAE MW link(s)")
    if s.get("service_level"):
        notes.append(f"service level {s['service_level']}")
    return notes


def to_user_points(hits):
    """Feed the assessment engine: carrier candidates with historical evidence (never 'verified')."""
    return [{"name": h["name"], "lat": h["lat"], "lon": h["lon"], "kind": "carrier_mast mast",
             "operator": (h.get("attrs") or {}).get("owner", ""), "verified": False,
             "source": f"CTTX mast dataset ({h['source']}, {h['id']}) — HISTORICAL"} for h in hits]


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "near"
    if cmd == "build":
        print("indexed %d sites (%d with carrier attributes) → %s" % (*build(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DIR), INDEX))
    elif cmd == "near":
        la, lo = float(sys.argv[2]), float(sys.argv[3])
        r = float(sys.argv[4]) if len(sys.argv) > 4 else 40
        k = int(sys.argv[5]) if len(sys.argv) > 5 else 15
        for h in near(la, lo, r, k):
            print(f"{h['distance_km']:6.2f} km {h['bearing_deg']:4d}°  {h['name'][:28]:28} {h['id']:12} {h['lat']:.5f},{h['lon']:.5f}  "
                  + "; ".join(backhaul_notes(h)))
