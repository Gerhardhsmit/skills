#!/usr/bin/env python3
"""Spec §28 Test Mode — 8 scenarios + outage/no-fabrication checks on synthetic worlds.

    python3 .claude/skills/link-assessment-architect/tests/test_scenarios.py [-v]

Synthetic worlds prove the ENGINE logic (discovery, confidence classes, terrain rejection,
relay search, radius expansion, routing, evidence). They do NOT satisfy §29 acceptance —
that requires a live run on a real customer email.
"""
import copy
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))

import drivers  # noqa: E402
from architect import report, run  # noqa: E402
from engine import load_equipment  # noqa: E402
from geo import destination, parse_location  # noqa: E402
from sources import FixtureSources, IntelGraph, SourceLog  # noqa: E402

VERBOSE = "-v" in sys.argv
OUT = os.path.join(HERE, "output")


def at(origin, north_km, east_km):
    lat, lon = destination(origin[0], origin[1], 0, north_km)
    return destination(lat, lon, 90, east_km)


def cells(origin, n, e, mnc, radios=("GSM", "UMTS", "LTE"), count=None):
    lat, lon = at(origin, n, e)
    out = []
    for i, r in enumerate(radios[:count] if count else radios):
        out.append({"radio": r, "mcc": 655, "mnc": mnc, "lac": 100 + i, "cellid": 5000 + i + 10 * mnc,
                    "lat": lat + 0.0004 * i, "lon": lon - 0.0003 * i})
    return out


def mast(origin, n, e, name, height=None, operator=""):
    lat, lon = at(origin, n, e)
    return {"lat": lat, "lon": lon, "ref": f"osm node/{abs(hash(name)) % 10**8}", "name": name,
            "operator": operator, "height_m": height, "tags": {"man_made": "mast"}}


def inp(slug, query, industry, area, email="", extra=None, **req):
    ind, chain = drivers.suggest(email, industry)
    return {"slug": slug,
            "customer": {"company": slug.replace("-", " ").title(), "industry": ind, "area": area, "context": {},
                         "drivers": chain, "requirement": req, "property": slug},
            "property": {"query": query}, "extra_sites": extra or [], "params": {"clutter_m": 0}}


# ------------------------------------------------------------------ scenarios

def s1_urban():
    o = (-33.9608, 25.6022)  # Gqeberha CBD-ish
    w = {"origin": o, "base_m": 40, "osm": {
        "masts": [mast(o, 1.1, 0.6, "Vodacom Newton Park", 35, "Vodacom")],
        "corridors": [dict(zip(("lat", "lon"), at(o, 0.3, 0.1)), kind="road:primary", ref="osm way/1", name="M4")]},
        "cells": cells(o, 1.1, 0.6, 1) + cells(o, 1.1, 0.6, 10, count=2)}
    i = inp("urban-business", f"{o[0]}, {o[1]}", "business", "urban", "office needs VoIP, cloud and CCTV", down_mbps=200, up_mbps=200)

    def check(r):
        assert r["primary"] and len(r["primary"]["hops"]) == 1, "urban should be a single hop"
        assert r["search"]["final_radius_km"] == 2, "urban search should stop at 2 km"
        top = r["infrastructure"][0]
        assert top["confidence"] == "PROBABLE" and top.get("cross_checked"), "OSM+cells should cross-check"
        assert top["vodacom"] and "MTN" in top["operators"]
    return "1 Urban business, fibre/mast nearby", i, w, check


def s2_farm_behind_mountain():
    o = (-33.60, 24.80)
    w = {"origin": o, "base_m": 600,
         "ridges": [{"a": at(o, 8, -25), "b": at(o, 8, 3), "height_m": 520, "sigma_km": 1.3}],
         "hills": [{"lat": at(o, 7, 9)[0], "lon": at(o, 7, 9)[1], "height_m": 560, "sigma_km": 1.8}],
         "osm": {"masts": [mast(o, 17, -2, "Town mast", 40)],
                 "high_ground": [dict(zip(("lat", "lon"), at(o, 7, 9)), ref="osm node/77", name="Rooiberg", ele=1160, kind="peak")]},
         "cells": cells(o, 17, -2, 1)}
    i = inp("farm-behind-mountain", f"{o[0]}, {o[1]}", "farm", "rural", "irrigation pivots, cameras and VoIP")

    def check(r):
        direct = {e["b"]: e for e in r["direct_candidates"]}
        assert any(e["status"] in ("BLOCKED", "MARGINAL") for e in direct.values()), "direct path must be rejected by the ridge"
        assert r["primary"] and len(r["primary"]["hops"]) == 2, "expect property → relay → carrier"
        relay = r["primary"]["nodes"][1]
        assert relay.startswith("R"), "middle node must be a high-ground relay"
        assert any("REJECTED" in e["claim"] for e in r["evidence"]), "rejection must be evidenced"
    return "2 Remote farm behind a mountain", i, w, check


def s3_reserve_lodges():
    o = (-24.40, 31.30)
    w = {"origin": o, "base_m": 420,
         "hills": [{"lat": at(o, -3, 4)[0], "lon": at(o, -3, 4)[1], "height_m": 140, "sigma_km": 0.6},
                   {"lat": at(o, 2, 2)[0], "lon": at(o, 2, 2)[1], "height_m": 180, "sigma_km": 0.8}],
         "osm": {"masts": [mast(o, 14, -3, "Hoedspruit road mast")],
                 "corridors": [dict(zip(("lat", "lon"), at(o, 14.5, -3)), kind="road:trunk", ref="osm way/9", name="R40")]},
         "cells": cells(o, 14, -3, 1) + cells(o, 14, -3, 10)}
    i = inp("reserve-lodges", f"{o[0]}, {o[1]}", "game_reserve", "remote",
            "Main lodge plus two bush lodges need guest wifi, bookings, CCTV and radio for rangers", down_mbps=100,
            extra=[{"name": "River Lodge", "lat": at(o, -6, 7)[0], "lon": at(o, -6, 7)[1]},
                   {"name": "Ridge Camp", "lat": at(o, 5, 6)[0], "lon": at(o, 5, 6)[1]}])

    def check(r):
        assert r["primary"], "main lodge must reach carrier"
        assert len(r["distribution"]) == 2 and all(d["route"] for d in r["distribution"]), "each lodge must be routed"
        assert r["infrastructure"][0]["backhaul_evidence"], "multi-operator + trunk road → backhaul evidence"
    return "3 Game reserve, multiple lodges", i, w, check


def s4_wind():
    o = (-32.95, 25.00)
    w = {"origin": o, "base_m": 1200,
         "osm": {"masts": [mast(o, -11, 4, "Cookhouse relay", 60, "Sentech")],
                 "corridors": [dict(zip(("lat", "lon"), at(o, -3, 0)), kind="substation", ref="osm way/5", name="WEF substation")]},
         "cells": cells(o, 6, -3, 1, count=1)}
    i = inp("wind-farm", f"{o[0]}, {o[1]}", "wind", "rural", "SCADA backup, CCTV at WTGs, O&M office internet")

    def check(r):
        confs = {s["confidence"] for s in r["infrastructure"]}
        assert "CELL LOCATION ONLY" in confs, "single cell must not be promoted to a mast"
        assert r["primary"]
        assert any(d["key"] == "scada" for d in r["customer"]["drivers"])
    return "4 Wind farm", i, w, check


def s5_solar_cells_down():
    o = (-28.80, 21.30)
    w = {"origin": o, "base_m": 850, "fail": {"cells": True},
         "osm": {"masts": [mast(o, 9, 5, "N14 tower", 45)],
                 "corridors": [dict(zip(("lat", "lon"), at(o, 9.3, 5)), kind="road:trunk", ref="osm way/14", name="N14")]}}
    i = inp("solar-farm", f"{o[0]}, {o[1]}", "solar", "remote", "PV plant SCADA and security cameras")

    def check(r):
        assert any(not e["ok"] and "OpenCelliD" in e["source"] for e in r["source_log"]), "cell outage must be logged"
        assert r["primary"], "must continue with OSM when cell DB fails"
    return "5 Solar farm (cell DB outage)", i, w, check


def s6_mine():
    o = (-26.20, 27.00)
    w = {"origin": o, "base_m": 1500,
         "hills": [{"lat": at(o, 0, 0)[0], "lon": at(o, 0, 0)[1], "height_m": -120, "sigma_km": 1.2}],  # open pit
         "ridges": [{"a": at(o, 4, -6), "b": at(o, 4, 6), "height_m": 160, "sigma_km": 0.7}],
         "osm": {"masts": [mast(o, 22, 1, "Town tower", 50)],
                 "high_ground": [dict(zip(("lat", "lon"), at(o, 4, 0)), ref="osm node/88", name="Pit rim koppie", ele=1660, kind="hill")]},
         "cells": cells(o, 22, 1, 1) + cells(o, 22, 1, 10)}
    i = inp("mine-site", f"{o[0]}, {o[1]}", "mining", "remote", "production telemetry, safety comms, control room")

    def check(r):
        assert r["search"]["final_radius_km"] >= 40, "must expand radius to reach town tower at 22 km"
        assert r["primary"] and len(r["primary"]["hops"]) >= 2, "pit needs relay"
    return "6 Mining site in a pit", i, w, check


def s7_remote_hospitality():
    o = (-33.40, 20.40)
    w = {"origin": o, "base_m": 500,
         "ridges": [{"a": at(o, 8, -20), "b": at(o, 8, 20), "height_m": 700, "sigma_km": 1.0},
                    {"a": at(o, 28, -20), "b": at(o, 28, 20), "height_m": 650, "sigma_km": 1.0}],
         "osm": {"masts": [mast(o, 45, 0, "Laingsburg mast", 45)],
                 "high_ground": [dict(zip(("lat", "lon"), at(o, 8, 0)), ref="osm node/1", name="Swartberg shoulder", ele=1200, kind="peak"),
                                 dict(zip(("lat", "lon"), at(o, 28, 0)), ref="osm node/2", name="Klein Swartberg", ele=1150, kind="peak")]},
         "cells": cells(o, 45, 0, 1)}
    i = inp("remote-hospitality", f"{o[0]}, {o[1]}", "hospitality", "remote", "boutique hotel guest wifi, POS, bookings")

    def check(r):
        assert r["search"]["final_radius_km"] == 60, "must expand to 60 km"
        assert r["primary"] and len(r["primary"]["hops"]) >= 2
    return "7 Remote hospitality behind two ranges", i, w, check


EMAIL8 = """Subject: Internet for our business
Hi CTTX, we run a remote business (engineering workshop + 3 staff houses) at
33°57'38.9"S 25°36'07.9"E. We need 100 Mbps up / 100 Mbps down, our cloud accounting,
VoIP phones and cameras keep dropping on the LTE router. Regards, Pieter"""


def s8_email():
    loc = parse_location(EMAIL8)
    assert loc == (-33.960806, 25.602194), f"DMS parse wrong: {loc}"
    w, _ = s1_urban()[2], None
    ind, chain = drivers.suggest(EMAIL8)
    i = inp("email-100-symmetric", EMAIL8, ind, "suburban", EMAIL8, down_mbps=100, up_mbps=100,
            because="cloud accounting, VoIP and CCTV fail on LTE; staff housing adds load")

    def check(r):
        keys = {d["key"] for d in r["customer"]["drivers"] if d["stated"]}
        assert {"cloud", "voip", "cctv", "staff"} <= keys, f"stated drivers missing: {keys}"
        assert r["property"]["source"] == "customer"
        assert r["primary"]
    return "8 Email: 100/100 Mbps remote business", i, w, check


def s9_all_down():
    o = (-30.0, 22.0)
    w = {"origin": o, "base_m": 1000, "fail": {"cells": True, "osm": True, "elevation": True}}
    i = inp("outage", f"{o[0]}, {o[1]}", "farm", "rural")

    def check(r):
        assert not r["primary"] and not r["infrastructure"], "no data → no invented sites/routes"
        assert sum(not e["ok"] for e in r["source_log"]) >= 3
    return "9 All sources down → no fabrication", i, w, check


def s10_no_dem():
    name, i, w, _ = s1_urban()
    w = copy.deepcopy(w)
    w["fail"] = {"elevation": True}

    def check(r):
        assert all(h["status"] == "UNVERIFIED" for h in r["primary"]["hops"]), "no DEM → LOS must not be claimed"
    return "10 DEM outage → LOS unverified", dict(i, slug="no-dem"), w, check


SECTIONS = ["Executive Summary", "Business Requirement", "Existing Environment", "Infrastructure Discovery",
            "Geographic Analysis", "Candidate Architecture", "Terrain / LOS Analysis", "Technology Options", "Risks",
            "Information Gaps", "Field Survey Requirements", "Recommended Next Engineering Step", "Evidence register"]


def generic_checks(r, md):
    """Solution-architect spec checks applied to every scenario."""
    import assess
    missing = [h for h in SECTIONS if h not in md] if "property" in r else []
    assert not missing, f"report sections missing: {missing}"
    bad = [e for e in r["evidence"] if e.get("status") not in assess.STATUSES]
    assert not bad, f"evidence rows without a valid status: {bad[:2]}"
    assert any(e["status"] == "ASSUMED" for e in r["evidence"]) or "property" not in r, "assumptions must be declared"
    for e in r.get("graph_edges", []):
        assert e["edge_class"] in assess.EDGE_CLASSES
        if e["status"] in ("BLOCKED", "MARGINAL"):
            assert e["edge_class"] == "REJECTED"
        if e["status"] == "UNVERIFIED":
            assert e["edge_class"] == "UNKNOWN", "no-DEM edges must stay UNKNOWN"
    for m in r.get("mast_candidates", []):
        for k in ("lat", "lon", "dist_property_km", "visibility", "access", "power", "ownership", "reason", "confidence"):
            assert k in m, f"mast candidate missing {k}"
        assert m["label"] == assess.MAST_LABEL
    if "property" in r:
        b = assess.assessment_band(r)
        assert assess.PRICE_MIN <= b["low"] <= b["high"] <= assess.PRICE_MAX


SCENARIOS = [s1_urban, s2_farm_behind_mountain, s3_reserve_lodges, s4_wind, s5_solar_cells_down, s6_mine,
             s7_remote_hospitality, s8_email, s9_all_down, s10_no_dem]


def main():
    eq = load_equipment()
    os.makedirs(OUT, exist_ok=True)
    passed = 0
    for fn in SCENARIOS:
        name, i, w, check = fn()
        log = SourceLog()
        r = run(copy.deepcopy(i), FixtureSources(log, w), IntelGraph(None), eq)
        try:
            check(r)
            md = report(r)
            generic_checks(r, md)
            with open(os.path.join(OUT, f"{i['slug']}.md"), "w") as f:
                f.write(md)
            passed += 1
            route = " → ".join(r["primary"]["nodes"]) if r.get("primary") else "—"
            print(f"PASS  {name:45s} radius {r.get('search', {}).get('final_radius_km')} km  route {route}")
        except AssertionError as e:
            print(f"FAIL  {name}: {e}")
            if VERBOSE:
                print(json.dumps({k: r.get(k) for k in ("status", "search", "direct_candidates")}, indent=1, default=str)[:3000])
    print(f"\n{passed}/{len(SCENARIOS)} scenarios passed")
    sys.exit(0 if passed == len(SCENARIOS) else 1)


if __name__ == "__main__":
    main()
