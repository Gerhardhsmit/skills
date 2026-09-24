#!/usr/bin/env python3
"""CTTX Link & Assessment Architect — orchestrator.

  architect.py init  <slug> [--email FILE] [--location "..."]   create projects/<slug>/input.json
  architect.py run   <slug> [--fixture WORLD.json]               execute discovery→terrain→route→report
  architect.py learn <slug>                                      push field-verification.json into the intel graph

Outputs: projects/<slug>/assessment.json, assessment.md. Desk results are also logged
(unverified) in data/intelligence-graph.json so the next assessment starts smarter.
"""
import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import assess  # noqa: E402
import drivers  # noqa: E402
from engine import (BACKHAUL_LABEL, CONF_ORDER, DEFAULT_HEIGHTS, RADII, RELAY_LABEL, Evidence, Planner,  # noqa: E402
                    backhaul_evidence, build_sites, compass, engineer, load_equipment, rejected_edges,
                    terrain_high_ground)
from geo import bearing_deg, haversine_km, parse_location  # noqa: E402
from sources import FixtureSources, IntelGraph, LiveSources, SourceLog  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
PROJECTS = os.path.join(REPO, "projects")
INTEL = os.path.join(REPO, "data", "intelligence-graph.json")
TODAY = datetime.date.today().isoformat()


# ============================================================ init

def cmd_init(a):
    pdir = os.path.join(PROJECTS, a.slug)
    os.makedirs(pdir, exist_ok=True)
    email = open(a.email).read() if a.email else ""
    if email:
        with open(os.path.join(pdir, "email.txt"), "w") as f:
            f.write(email)
    industry, chain = drivers.suggest(email)
    low = email.lower()
    mbps = [int(x) for x in re.findall(r"(\d{2,5})\s*mbps", low)]
    up = re.search(r"(\d{2,5})\s*(?:mbps\s*)?(?:up\b|upload|upstream)", low)
    down = re.search(r"(\d{2,5})\s*(?:mbps\s*)?(?:down\b|download|downstream)", low)
    pair = re.search(r"(\d{2,5})\s*/\s*(\d{2,5})\s*mbps", low)
    loc = a.location or ""
    if not loc:
        m = parse_location(email)
        loc = f"{m[0]}, {m[1]}" if m else ""
    inp = {
        "slug": a.slug,
        "customer": {
            "company": "", "contact": {"name": "", "email": ""}, "property": "", "industry": industry,
            "area": "remote",
            "context": {k: "" for k in ("location", "sites_buildings", "existing_connectivity", "existing_provider",
                                        "requested_service", "symmetry", "reliability", "growth",
                                        "existing_infrastructure", "deadline", "budget", "pain_points")},
            "drivers": chain,
            "requirement": {"down_mbps": int(down.group(1)) if down else int(pair.group(1)) if pair else (max(mbps) if mbps else None),
                            "up_mbps": int(up.group(1)) if up else int(pair.group(2)) if pair else (max(mbps) if mbps else None),
                            "because": "", "availability": "", "latency": "", "services": [],
                            "architecture": ""},
        },
        "property": {"query": loc, "lat": None, "lon": None, "source": "", "antenna_m": None,
                     "boundary": "BOUNDARY APPROXIMATION — not provided"},
        "extra_sites": [],
        "params": {"clutter_m": 0, "max_hops": 4, "freq_ghz": 5.8},
        "inputs": {"kml": None, "points_csv": None, "cell_csv": None},
    }
    path = os.path.join(pdir, "input.json")
    if os.path.exists(path) and not a.force:
        sys.exit(f"{path} exists (use --force to overwrite)")
    with open(path, "w") as f:
        json.dump(inp, f, indent=2, ensure_ascii=False)
    print(f"created {os.path.relpath(path, REPO)}  industry={industry}  location={'parsed' if loc else 'MISSING'}")


# ============================================================ run

def node(id_, lat, lon, role, confidence="UNKNOWN", **kw):
    design, mx = DEFAULT_HEIGHTS[{"customer": "customer", "carrier": "carrier", "relay": "relay",
                                  "structure": "structure"}[role]]
    return {"id": id_, "lat": lat, "lon": lon, "role": role, "confidence": confidence,
            "h_design": kw.pop("h_design", design), "h_max": kw.pop("h_max", mx), **kw}


def resolve_property(inp, src, ev):
    p = inp["property"]
    if p.get("lat") is not None and p.get("lon") is not None:
        ev.add(f"Property coordinate {p['lat']}, {p['lon']}", p.get("source") or "input.json", "High",
               status="VERIFIED" if p.get("verified") else "SOURCE-DERIVED")
        return p["lat"], p["lon"]
    parsed = parse_location(p.get("query"))
    if parsed:
        if not any(k.get("kind") == "property" and str(parsed[0]) in k["claim"] for k in inp.get("known_facts", [])):
            ev.add(f"Property coordinate {parsed[0]}, {parsed[1]}", f"Customer-supplied location '{p['query']}'", "High")
        p.update(lat=parsed[0], lon=parsed[1], source="customer")
        return parsed
    if p.get("query"):
        hits = src.geocode(p["query"])
        if hits:
            h = hits[0]
            ev.add(f"Property coordinate {h['lat']:.5f}, {h['lon']:.5f} ('{h['label'][:80]}')",
                   f"Geocoded '{p['query']}' ({h.get('osm_id', 'geocoder')}) — {len(hits)} candidate(s)",
                   "Medium" if len(hits) == 1 else "Low — confirm pin with customer", status="SOURCE-DERIVED")
            p.update(lat=h["lat"], lon=h["lon"], source="geocoded", geocode_candidates=hits[:5])
            return h["lat"], h["lon"]
    return None


def run(inp, src, intel, eq):
    ev = Evidence()
    log = src.log
    cust = inp["customer"]
    params = inp.get("params", {})
    out = {"slug": inp["slug"], "date": TODAY, "sources_mode": src.name, "customer": cust}

    for k in inp.get("known_facts", []):
        ev.add(k["claim"], k["source"], k.get("confidence", "Medium"), k.get("date", TODAY),
               status=k.get("status", "SOURCE-DERIVED"))
    loc = resolve_property(inp, src, ev)
    if not loc:
        out["status"] = "BLOCKED: property location unresolved"
        out["evidence"], out["source_log"] = ev.rows, log.entries
        return out
    lat, lon = loc
    prop = {"lat": lat, "lon": lon}
    out["property"] = inp["property"]
    out["known_facts"] = inp.get("known_facts", [])
    out["summary"] = inp.get("summary", [])
    out["field_checks"] = inp.get("field_checks", [])
    out["commercial"] = inp.get("commercial", [])
    out["risks"] = inp.get("risks", [])

    pg = src.elevations([(lat, lon)])
    prop_ground = pg[0] if pg else None
    if prop_ground is not None:
        ev.add(f"Property ground elevation {prop_ground:.0f} m ASL", log.entries[-1]["source"], "Medium")
    out["property_ground_m"] = prop_ground

    radii = RADII.get(cust.get("area", "remote"), RADII["remote"])
    user_pts = src.user_points() + [
        dict(k, source=k.get("source", "input.json known_infrastructure"),
             verified=k.get("status") == "VERIFIED" or k.get("verified", False),
             kind=k.get("kind", "") + (" mast" if k.get("kind") in ("carrier_mast", "fibre_pop", "exchange", "datacentre", "cttx") else ""))
        for k in inp.get("known_infrastructure", []) if k.get("lat") is not None]
    rounds = []
    result = None
    for r in radii:
        osm = src.osm(lat, lon, r)
        cells = src.cells(lat, lon, r)
        intel_nodes = intel.nodes_near(lat, lon, r) if intel else []
        pts = [p for p in user_pts if haversine_km(lat, lon, p["lat"], p["lon"]) <= r]
        sites = build_sites(prop, osm, cells, pts, intel_nodes, ev)
        corridors = (osm or {}).get("corridors", [])
        for s in sites:
            s["backhaul_evidence"] = backhaul_evidence(s, corridors)
        high = list((osm or {}).get("high_ground", [])) + list((osm or {}).get("structures", []))
        high += [dict(p, kind=p.get("kind", "user relay point"), ref=p["source"]) for p in pts
                 if any(k in (p.get("kind") or p.get("name", "")).lower() for k in ("relay", "peak", "ridge", "hill", "koppie"))]
        dem_high = terrain_high_ground(prop, r, src, prop_ground) if prop_ground is not None else None
        if dem_high:
            high += dem_high
        route = plan(inp, prop, sites, high, src, intel, eq, params)
        rounds.append({"radius_km": r, "sites": len(sites), "relay_candidates": len(high),
                       "osm_ok": osm is not None, "cells_ok": cells is not None,
                       "route_found": bool(route["primary"])})
        result = (r, sites, high, corridors, route, osm, cells)
        dense = cust.get("area") in ("urban", "suburban")
        if route["primary"] and (route["alternative"] or dense):
            break  # adaptive stop: viable route + alternative (or dense area where the first hit is enough)
    r, sites, high, corridors, route, osm, cells = result
    out["search"] = {"rounds": rounds, "final_radius_km": r}

    # evidence for infrastructure
    for s in sites:
        ev.add(f"{s['name']}: {s['confidence']} site at {s['lat']:.5f}, {s['lon']:.5f}"
               + (f", height {s['height_m']} m" if s.get("height_m") else ", height UNKNOWN"),
               " + ".join(s["evidence"]) or "—", {"CONFIRMED": "High", "PROBABLE": "Medium"}.get(s["confidence"], "Low"),
               status="VERIFIED" if s["confidence"] == "CONFIRMED" else "SOURCE-DERIVED")
    if cells is not None and not cells:
        ev.add("No cells returned by cell database in search radius", "OpenCelliD", "Does NOT mean no mobile infrastructure",
               status="UNKNOWN")
    for h in high:
        ev.add(f"{h.get('name') or h['kind']} at {h['lat']:.5f}, {h['lon']:.5f}"
               + (f" ({h['ele']:.0f} m)" if h.get("ele") else "") + f" — {RELAY_LABEL}", h.get("ref", ""), "Low",
               status="INFERRED")

    out["infrastructure"] = sorted(sites, key=lambda s: (CONF_ORDER.index(s["confidence"]), s["distance_km"]))
    out["relay_candidates"] = high
    out["corridors"] = nearest_corridors(prop, corridors)
    out.update(route)
    for key in ("primary", "alternative"):
        rt = route.get(key)
        if rt:
            for hop in rt["hops"]:
                ev.add(f"Hop {hop['a']} → {hop['b']} ({hop['distance_km']} km): terrain {hop['status']}"
                       + (f", Fresnel clearance {hop.get('fresnel_clearance_m')} m" if "fresnel_clearance_m" in hop else ""),
                       "Terrain profile from " + terrain_source(log), "Preliminary",
                       status="CALCULATED" if hop["status"] != "UNVERIFIED" else "UNKNOWN")
    for e in route["rejected"]:
        ev.add(f"REJECTED {e['a']} → {e['b']} ({e['distance_km']} km): {e.get('reason', e['status'])}",
               "Terrain profile from " + terrain_source(log), "Preliminary", status="CALCULATED")
    for src_name in sorted({e["source"] for e in log.entries if not e["ok"]}):
        ev.add(f"{src_name} unavailable — its evidence is missing from this assessment", "Source log", "—", status="UNKNOWN")
    ev.add(f"Design antenna heights where unknown (customer {DEFAULT_HEIGHTS['customer'][0]} m, carrier {DEFAULT_HEIGHTS['carrier'][0]} m, "
           f"relay {DEFAULT_HEIGHTS['relay'][0]} m)", "CTTX planning defaults", "—", status="ASSUMED")
    ev.add(f"Clutter allowance {params.get('clutter_m', 0)} m (DEM excludes trees/buildings)", "input params", "—", status="ASSUMED")
    ev.add("Radio parameters from planning classes, not datasheets", "equipment-library.json", "—", status="ASSUMED")
    out["all_corridors"] = corridors
    out["mast_candidates"] = assess.mast_candidates(dict(out, nodes=route["nodes"]), route.pop("_memo"))
    out["evidence"], out["source_log"] = ev.rows, log.entries
    blocked = any(not e["ok"] for e in log.entries) and not sites
    fibre = any(k.get("kind") == "fibre" for k in inp.get("known_facts", []))
    if route["primary"]:
        out["status"] = "ROUTE FOUND"
    elif fibre:
        out["status"] = "FIBRE AVAILABLE (carrier-confirmed) — wireless route " + (
            "NOT ASSESSED: discovery sources unavailable" if blocked else "not found")
    elif blocked:
        out["status"] = "INCOMPLETE — discovery sources unavailable; no route claimed"
    else:
        out["status"] = "NO DESK ROUTE — field survey / wider search required"
    return out


def terrain_source(log):
    ok = [e["source"] for e in log.entries if e["ok"] and "levation" in e["source"]]
    return ok[-1] if ok else "UNAVAILABLE"


def nearest_corridors(prop, corridors):
    best = {}
    for c in corridors:
        d = haversine_km(prop["lat"], prop["lon"], c["lat"], c["lon"])
        if c["kind"] not in best or d < best[c["kind"]]["distance_km"]:
            best[c["kind"]] = dict(c, distance_km=round(d, 1),
                                   bearing=compass(bearing_deg(prop["lat"], prop["lon"], c["lat"], c["lon"])))
    return sorted(best.values(), key=lambda c: c["distance_km"])


def plan(inp, prop, sites, high, src, intel, eq, params):
    p = inp["property"]
    nodes = [node("PROPERTY", prop["lat"], prop["lon"], "customer", "CONFIRMED",
                  h_design=p.get("antenna_m") or DEFAULT_HEIGHTS["customer"][0],
                  h_max=p.get("max_antenna_m") or DEFAULT_HEIGHTS["customer"][1], name=inp["customer"].get("property") or "Property")]
    # rank carrier candidates by evidence, keep a bounded set for terrain analysis
    ranked = sorted(sites, key=lambda s: (CONF_ORDER.index(s["confidence"]), -s["vodacom"], s["distance_km"]))[:10]
    for i, s in enumerate(ranked, 1):
        h = s.get("height_m")
        nodes.append(node(f"C{i}", s["lat"], s["lon"], "carrier", s["confidence"], name=s["name"],
                          vodacom=s["vodacom"], backhaul_evidence=s["backhaul_evidence"], site=s,
                          h_design=(h - 3) if h else DEFAULT_HEIGHTS["carrier"][0],
                          h_max=(h - 3) if h else DEFAULT_HEIGHTS["carrier"][1], height_known=bool(h)))
    # relays: dedupe within 1 km, keep highest
    rel = []
    for h in sorted(high, key=lambda x: -(x.get("ele") or 0)):
        if all(haversine_km(h["lat"], h["lon"], r["lat"], r["lon"]) > 1 for r in rel):
            rel.append(h)
    for i, h in enumerate(rel[:8], 1):
        role = "structure" if h.get("kind") in ("water_tower", "silo") else "relay"
        nodes.append(node(f"R{i}", h["lat"], h["lon"], role if role == "structure" else "relay", "UNKNOWN",
                          name=h.get("name") or h["kind"], ele=h.get("ele"), ref=h.get("ref")))
    for i, x in enumerate(inp.get("extra_sites", []), 1):
        ll = (x["lat"], x["lon"]) if x.get("lat") is not None else parse_location(x.get("query"))
        if ll:
            nodes.append(node(f"S{i}", ll[0], ll[1], "customer", "CONFIRMED", name=x.get("name", f"Site {i}"),
                              h_design=x.get("antenna_m") or 9))
    pl = Planner(nodes, src, eq, f_ghz=params.get("freq_ghz", 5.8), clutter_m=params.get("clutter_m", 0),
                 max_hops=params.get("max_hops", 4), intel=intel)
    targets = {n["id"] for n in nodes if n["role"] == "carrier"}

    # per-candidate direct assessment (spec §13) — every carrier candidate gets a terrain verdict
    direct = []
    for n in nodes:
        if n["role"] == "carrier" and haversine_km(prop["lat"], prop["lon"], n["lat"], n["lon"]) <= pl.max_hop:
            direct.append(pl.edge("PROPERTY", n["id"]))
    primary = pl.best_path("PROPERTY", targets) if targets else None
    alternative = None
    if primary:
        excl = {primary["nodes"][-1]}
        alternative = pl.best_path("PROPERTY", targets - excl, exclude=excl)
        if alternative and alternative["nodes"] == primary["nodes"]:
            alternative = None
    distribution = []
    for n in nodes:
        if n["role"] == "customer" and n["id"] != "PROPERTY":
            distribution.append({"site": n["id"], "name": n["name"],
                                 "route": pl.best_path(n["id"], {"PROPERTY"} | {d["site"] for d in distribution
                                                                               if d["route"]})})
    for rt in filter(None, [primary, alternative] + [d["route"] for d in distribution]):
        rt["engineering"] = [engineer(h, eq) for h in rt["hops"]]
        rt["rf_notes"] = [assess.rf_notes(h, e) for h, e in zip(rt["hops"], rt["engineering"])]
    # mast-location engine: every relay gets a verdict to the property and its 2 nearest carriers
    carriers = [n for n in nodes if n["role"] == "carrier"]
    for n in nodes:
        if n["role"] in ("relay", "structure"):
            near = sorted(carriers, key=lambda c: haversine_km(n["lat"], n["lon"], c["lat"], c["lon"]))[:2]
            for other in [nodes[0]] + near:
                if haversine_km(n["lat"], n["lon"], other["lat"], other["lon"]) <= pl.max_hop:
                    pl.edge(n["id"], other["id"])
    nd = {n["id"]: n for n in nodes}
    graph_edges = [dict(e, edge_class=assess.edge_class(e, nd, intel)) for e in pl.memo.values()]
    return {"nodes": [{k: v for k, v in n.items() if k != "site"} for n in nodes], "direct_candidates": direct,
            "primary": primary, "alternative": alternative, "distribution": distribution,
            "rejected": rejected_edges(pl), "graph_edges": graph_edges, "_memo": pl.memo}


# ============================================================ report (spec §14 structure)

def fmt_route(rt, nodes):
    names = {n["id"]: n for n in nodes}
    parts = []
    for nid in rt["nodes"]:
        n = names[nid]
        tag = {"customer": "", "carrier": f" [{n['confidence']}]", "relay": " [CANDIDATE MAST — FIELD VERIFY]",
               "structure": " [STRUCTURE — FIELD VERIFY]"}[n["role"]]
        parts.append(f"**{nid}** {n.get('name', '')}{tag}")
    return "\n→ ".join(parts)


def edge_cls(o, a, b):
    for e in o.get("graph_edges", []):
        if {e["a"], e["b"]} == {a, b}:
            return e["edge_class"]
    return "UNKNOWN"


def hop_table(rt, o):
    rows = ["| Hop | Edge class | Dist | Az A/B | Terrain | Heights A/B (ASSUMED) | 60 % F1 clr | Class | FSPL | EIRP | Rx | Margin | Rain | Throughput |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for h, e, r in zip(rt["hops"], rt["engineering"], rt.get("rf_notes", [{}] * len(rt["hops"]))):
        rows.append(f"| {h['a']}→{h['b']} | {edge_cls(o, h['a'], h['b'])} | {h['distance_km']} km | "
                    f"{h.get('bearing_ab', '–')}°/{h.get('bearing_ba', '–')}° | {h['status']} | "
                    f"{h.get('h_a_m', '–')}/{h.get('h_b_m', '–')} m | {h.get('fresnel_clearance_m', '–')} m | "
                    f"{e.get('class') or '—'} | {e.get('fspl_db', '–')} dB | {e.get('eirp_dbm', '–')} dBm | "
                    f"{e.get('rx_dbm', '–')} dBm | {e.get('fade_margin_db', '–')} dB | "
                    f"{r.get('rain', '–').split(' (')[0]} | {r.get('modulation_throughput', 'UNKNOWN').split(' —')[0]} |")
    return "\n".join(rows)


def nodes_by(nodes):
    return {n["id"]: n for n in nodes}


def report(o):
    c = o["customer"]
    L = ["# CTTX Private Infrastructure Network Assessment — Preliminary Desk Study",
         f"**{c.get('company') or c.get('property') or o['slug']}** · {o['date']} · status: **{o['status']}** · data mode: {o['sources_mode']}",
         "", "_Evidence labels: VERIFIED · SOURCE-DERIVED · CALCULATED · INFERRED · ASSUMED · UNKNOWN · FIELD VERIFY. "
         "This is a desk study, not a field survey._", ""]
    if "property" not in o:
        L += ["Property location could not be resolved — obtain a pin drop / coordinates from the customer.", ""]
        return "\n".join(L + evidence_md(o))
    nodes = o["nodes"]
    nb = nodes_by(nodes)
    pr, alt = o.get("primary"), o.get("alternative")
    req = c.get("requirement", {})
    facts = o.get("known_facts", [])
    fibre = any(k.get("kind") == "fibre" for k in facts)
    failed = sorted({e["source"] for e in o["source_log"] if not e["ok"]})
    band = assess.assessment_band(o)

    # 1 Executive summary
    L += ["## 1. Executive Summary"]
    L += [f"- {x}" for x in o.get("summary", [])]
    need = f"{req.get('down_mbps') or '?'} / {req.get('up_mbps') or '?'} Mbps" if req.get("down_mbps") else "capacity UNKNOWN"
    because = req.get("because") or "; ".join(d["driver"] for d in c.get("drivers", [])[:3])
    L.append(f"- **Need:** {need} because {because}.")
    if pr:
        L.append(f"- **Discovered:** a {len(pr['hops'])}-hop path appears engineerable to {nb[pr['nodes'][-1]]['name']} "
                 f"({nb[pr['nodes'][-1]]['confidence']}) — CALCULATED from DEM, not field-verified.")
    elif fibre:
        L.append("- **Discovered:** carrier-confirmed fibre at the property is the primary path (SOURCE-DERIVED); no wireless route is claimed.")
    else:
        L.append("- **Discovered:** no desk-verifiable path — survey required.")
    if failed:
        L.append(f"- **Limits:** {', '.join(failed)} unavailable — affected findings are UNKNOWN, not negative.")
    L.append("- **Assessment:** " + ("recommend a paid Private Infrastructure Network Assessment, indicative R"
                                     + f"{band['low']:,}–R{band['high']:,}".replace(",", " ") if band["recommend_paid_assessment"] else band["note"]))

    # 2 Business requirement
    L += ["", "## 2. Business Requirement", "| Business driver | Operational requirement | Network requirement | Technical solution | Evidence |",
          "|---|---|---|---|---|"]
    for d in c.get("drivers", []):
        L.append(f"| {d['driver']} | {d['operational']} | {d['network']} | {d['solution']} | {'SOURCE-DERIVED (customer)' if d.get('stated') else 'INFERRED'} |")
    L.append("")
    for k in ("down_mbps", "up_mbps", "because", "availability", "latency", "architecture"):
        if req.get(k):
            L.append(f"- **{k.replace('_', ' ')}:** {req[k]}")
    if req.get("services"):
        L.append(f"- **services:** {', '.join(req['services'])}")

    # 3 Existing environment
    p = o["property"]
    L += ["", "## 3. Existing Environment",
          f"- **Property:** {p['lat']}, {p['lon']} ({'VERIFIED' if p.get('verified') else 'SOURCE-DERIVED'}: {p.get('source')}) — "
          f"[map](https://www.google.com/maps?q={p['lat']},{p['lon']})"
          + (f"; ground {o['property_ground_m']:.0f} m ASL (SOURCE-DERIVED DEM)" if o.get("property_ground_m") is not None else "; ground elevation UNKNOWN"),
          f"- **Boundary:** {p.get('boundary', 'BOUNDARY APPROXIMATION')}"]
    for f in p.get("features", []):
        loc = f"{f['lat']}, {f['lon']}" if f.get("lat") is not None else "coordinates UNKNOWN — obtain"
        L.append(f"- **{f.get('kind', 'feature')}:** {f.get('name', '')} — {loc}")
    for k, v in c.get("context", {}).items():
        if v:
            L.append(f"- **{k.replace('_', ' ')}:** {v}")

    # 4 Infrastructure discovery
    L += ["", "## 4. Infrastructure Discovery",
          "| # | Candidate | Site class | Dist / bearing | Operators | Height | Direct path from property | Backhaul evidence |",
          "|---|---|---|---|---|---|---|---|"]
    direct = {e["b"]: e for e in o["direct_candidates"]}
    for n in [n for n in nodes if n["role"] == "carrier"]:
        s = n
        d = direct.get(n["id"])
        verdict = (f"{d['status']} ({edge_cls(o, 'PROPERTY', n['id'])})" + (f" — {d['reason']}" if d.get("reason") else "")) if d else "beyond max hop"
        L.append(f"| {n['id']} | {n['name']} | {n['confidence']} | "
                 f"{round(haversine_km(p['lat'], p['lon'], n['lat'], n['lon']), 2)} km "
                 f"{compass(bearing_deg(p['lat'], p['lon'], n['lat'], n['lon']))} | "
                 f"{'Vodacom' if n.get('vodacom') else '—'} | {'known' if n.get('height_known') else 'UNKNOWN'} | {verdict} | "
                 f"{'; '.join(n.get('backhaul_evidence', [])) or '—'} |")
    conf_facts = [k for k in facts if k.get("kind") in ("fibre", "carrier", "coverage", "infrastructure")]
    if conf_facts:
        L += ["", "**Carrier / operator information (from correspondence):**"]
        L += [f"- {k['claim']} — {k.get('status', 'SOURCE-DERIVED')}: _{k['source']}, {k.get('date', '')}_" for k in conf_facts]
    if not o["infrastructure"]:
        L += ["", "_No tower/mast candidates from automated sources"
              + (" — sources unavailable (UNKNOWN), this does NOT mean none exist._" if failed else "._")]
    L += ["", "_OSM = geographic evidence, not current-infrastructure truth; OpenCelliD = observations (Observed/Candidate/Unverified) "
          "unless cross-checked; CellMapper = reference only; coverage ≠ usable carrier site._"]

    # 5 Geographic analysis
    L += ["", "## 5. Geographic Analysis",
          "Search rounds: " + "; ".join(f"{r['radius_km']} km → {r['sites']} sites, {r['relay_candidates']} high points"
                                        + ("" if r["osm_ok"] else " (OSM UNKNOWN)") for r in o["search"]["rounds"])]
    if o["corridors"]:
        L.append("Corridors (nearest, SOURCE-DERIVED OSM): " + "; ".join(
            f"{x['kind']} {x.get('name') or ''} {x['distance_km']} km {x['bearing']}" for x in o["corridors"][:8]))
    if o.get("mast_candidates"):
        L += ["", "### Mast-location engine (every candidate: " + assess.MAST_LABEL.split(" — ")[1] + ")",
              "| ID | Name / reason | Coordinates | Elev (rel.) | To property | Visibility (CALCULATED) | Access | Power | Ownership | In route |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for m in o["mast_candidates"]:
            vis = ", ".join(f"{k}: {v}" for k, v in m["visibility"].items())
            L.append(f"| {m['id']} | {m['name']} — {m['reason']} | {m['lat']}, {m['lon']} | "
                     f"{m['ele_m'] or '–'} m ({'+' if (m['relative_m'] or 0) >= 0 else ''}{m['relative_m'] if m['relative_m'] is not None else '?'} m) | "
                     f"{m['dist_property_km']} km | {vis} | {m['access']} | {m['power']} | {m['ownership']} | {'✔' if m['in_route'] else ''} |")

    # 6 Candidate architecture
    L += ["", "## 6. Candidate Architecture", "### Primary path"]
    L += [fmt_route(pr, nodes), "", hop_table(pr, o)] if pr else (
        ["Carrier fibre service to the property (see §4) — no wireless path required/claimed."] if fibre else ["None established at desk."])
    L += ["", "### Alternative path"]
    L += [fmt_route(alt, nodes), "", hop_table(alt, o)] if alt else ["None established at desk."]
    if o.get("distribution"):
        L += ["", "### Multi-site distribution"]
        for d in o["distribution"]:
            L += [f"**{d['name']}**"] + ([fmt_route(d["route"], nodes), "", hop_table(d["route"], o)] if d["route"] else ["No desk path — survey."])
    cls_count = {k: sum(e["edge_class"] == k for e in o.get("graph_edges", [])) for k in assess.EDGE_CLASSES}
    L += ["", f"**Infrastructure graph:** {len(nodes)} nodes, {len(o.get('graph_edges', []))} edges analysed — "
          + (", ".join(f"{k} {v}" for k, v in cls_count.items() if v) or "no wireless edges analysed")]
    L += ["", "### Network layers"]
    for k, v in assess.layers(o).items():
        L.append(f"- **L{k}:** " + "; ".join(v))
    L += ["", "### Redundancy (by failure mode)", "| Measure | Protects against | Justification |", "|---|---|---|"]
    L += [f"| {r['measure']} | {r['protects_against']} | {r['justification']} |" for r in assess.redundancy(o)]

    # 7 Terrain / LOS
    L += ["", "## 7. Terrain / LOS Analysis"]
    if not any("levation" in e["source"] and e["ok"] for e in o["source_log"]):
        L.append("- **UNKNOWN** — no elevation source reachable. No LOS is claimed for any path.")
    for rt in filter(None, [pr, alt]):
        for h in rt["hops"]:
            if "highest_obstruction" in h:
                L.append(f"- {h['a']}→{h['b']} (CALCULATED, DEM k=4/3, 60 % F1): endpoints {h['ground_a_m']}/{h['ground_b_m']} m ASL; "
                         f"highest obstruction {h['highest_obstruction']['ele_m']} m at {h['highest_obstruction']['at_km']} km; "
                         f"lowest {h['lowest_point']['ele_m']} m; F1 mid {h['fresnel_mid_m']} m; earth bulge {h['earth_bulge_mid_m']} m; "
                         f"worst clearance {h['fresnel_clearance_m']} m. Trees/buildings NOT in DEM → FIELD VERIFY.")
    if o["rejected"]:
        L += ["", "**Rejected paths (CALCULATED evidence):**"]
        L += [f"- ❌ {e['a']}→{e['b']} {e['distance_km']} km — {e.get('reason', e['status'])}"
              for e in sorted(o["rejected"], key=lambda e: e["distance_km"])[:12]]

    # 8 Technology options
    L += ["", "## 8. Technology Options", "| Technology | Role | Why / when | Evidence |", "|---|---|---|---|"]
    L += [f"| {t['technology']} | {t['role']} | {t['why']} | {t['status']} |" for t in assess.technology_options(o)]
    L.append("\n_Radio figures use planning classes (ASSUMED) until manufacturer profiles are loaded; modulation and throughput are not estimated._")

    # 9 Risks
    L += ["", "## 9. Risks"]
    risks = []
    if failed:
        risks.append("Discovery incomplete — sources unavailable; undiscovered infrastructure may change the recommendation")
    if pr and any(n.startswith("R") for n in pr["nodes"]):
        risks.append("Relay site access, landowner consent, power and security are UNKNOWN")
    if pr:
        risks.append("Carrier mounting space/interconnect/backhaul terms not confirmed — commercial risk")
        risks.append("Vegetation/buildings not in DEM — LOS may fail on site")
        if any(e.get("freq_mhz", 0) < 10000 for e in pr["engineering"] if e.get("freq_mhz")):
            risks.append("Licence-exempt 5 GHz interference — capacity/availability risk until spectrum scan")
    if fibre:
        risks.append("Fibre lead time, wayleave/host-site approval and contract term vs customer tenure")
    risks += o.get("risks", [])
    L += [f"- {r}" for r in dict.fromkeys(risks)] or ["- None identified at desk"]

    # 10 Information gaps
    L += ["", "## 10. Information Gaps"] + [f"- UNKNOWN: {g}" for g in assess.information_gaps(o)]

    # 11 Field survey
    L += ["", "## 11. Field Survey Requirements"]
    fv = ["Confirm property pin and the exact buildings/rooms to be served"]
    if pr or alt:
        fv += ["Customer mounting position and achievable mast height",
               "Visual LOS at each hop bearing (binoculars/drone/photo) incl. trees & buildings",
               "5 GHz / 60 GHz spectrum scan at each endpoint"]
    for rt in filter(None, [pr, alt]):
        for nid in rt["nodes"]:
            n = nb[nid]
            if n["role"] == "carrier":
                fv.append(f"{nid} {n['name']}: structure, owner/operator, height, free mounting space, power, interconnect/backhaul terms")
            elif n["role"] in ("relay", "structure"):
                fv.append(f"{nid} {n['name']}: landowner consent, access road, power (solar), foundation, ~{n['h_design']} m mast")
    fv += o.get("field_checks", [])
    L += [f"- [ ] FIELD VERIFY: {x}" for x in dict.fromkeys(fv)]

    # 12 Next step + commercial
    L += ["", "## 12. Recommended Next Engineering Step"]
    if o.get("commercial"):
        L += [f"- {x}" for x in o["commercial"]]
    elif pr:
        L += ["- Sell the **Private Infrastructure Network Assessment** (survey the route above, confirm LOS/heights/permissions, "
              "final radio profiles and price)."]
    else:
        L += ["- Resolve the information gaps (§10), then re-run discovery; a field search may be needed."]
    rand = lambda v: "R" + f"{v:,}".replace(",", " ")  # noqa: E731
    if band["recommend_paid_assessment"]:
        L += ["", f"**Assessment band (indicative, spec §13):** {rand(band['low'])}–{rand(band['high'])}"
              + (" — factors: " + ", ".join(f"{k} (+{rand(v)})" for k, v in band["factors"]) if band["factors"] else " — base scope")
              + f". {band['note']}"]
    else:
        L += ["", f"**Paid assessment:** not recommended — {band['note']}"]
    L += ["", "### Architect's checklist (§17)", "| Question | Answer |", "|---|---|"]
    L += [f"| {q} | {a} |" for q, a in assess.checklist(o)]
    L += [""] + evidence_md(o)
    return "\n".join(L)


def evidence_md(o):
    L = ["## Evidence register", "| Claim | Status | Source | Date | Confidence |", "|---|---|---|---|---|"]
    order = {s: i for i, s in enumerate(assess.STATUSES)}
    for r in sorted(o["evidence"], key=lambda r: order.get(r.get("status"), 9)):
        L.append(f"| {r['claim']} | {r.get('status', 'SOURCE-DERIVED')} | {r['source']} | {r['date']} | {r['confidence']} |")
    L += ["", "### Source log"]
    for e in o["source_log"]:
        L.append(f"- {'✅' if e['ok'] else '❌ FAILED'} {e['source']} — {e['action']}: {e['detail'][:160]}")
    return L


# ============================================================ store / learn

def store(o, intel):
    """§18 continuous learning: log desk knowledge (unverified) without duplicating it.
    Field-verified knowledge is added by `learn`; verified entries are never overwritten here."""
    if not intel or "property" not in o:
        return
    g = intel.g
    for k in ("nodes", "routes", "rejected_links", "relay_candidates", "assessments", "sources"):
        g.setdefault(k, [])
    near = lambda lst, la, lo, km=0.15: next((x for x in lst if haversine_km(x["lat"], x["lon"], la, lo) <= km), None)  # noqa: E731
    for s in o["infrastructure"]:
        n = near(g["nodes"], s["lat"], s["lon"])
        if n is None:
            g["nodes"].append({"name": s["name"], "lat": s["lat"], "lon": s["lon"], "kind": "carrier",
                               "operator": ", ".join(s["operators"]), "height_m": s.get("height_m"),
                               "verified": False, "confidence": s["confidence"], "first_seen": o["date"],
                               "last_seen": o["date"], "evidence": s["evidence"][:4]})
        elif not n.get("verified"):
            n["last_seen"] = o["date"]
            n["height_m"] = n.get("height_m") or s.get("height_m")
    for m in o.get("mast_candidates", []):
        r = near(g["relay_candidates"], m["lat"], m["lon"], 0.5)
        if r is None:
            g["relay_candidates"].append({k: m[k] for k in ("name", "lat", "lon", "ele_m", "reason")}
                                         | {"verified": False, "used_in_route": m["in_route"], "first_seen": o["date"]})
        elif m["in_route"]:
            r["used_in_route"] = True
    nd = {n["id"]: n for n in o["nodes"]}
    for e in o.get("rejected", []):
        A, B = nd[e["a"]], nd[e["b"]]
        if A["role"] == "customer" or B["role"] == "customer":
            continue  # customer-location edges stay in the project folder, not the shared graph
        if not any(near([x["a_pt"]], A["lat"], A["lon"]) and near([x["b_pt"]], B["lat"], B["lon"]) for x in g["rejected_links"]):
            g["rejected_links"].append({"a": A.get("name"), "b": B.get("name"), "a_pt": {"lat": A["lat"], "lon": A["lon"]},
                                        "b_pt": {"lat": B["lat"], "lon": B["lon"]}, "distance_km": e["distance_km"],
                                        "reason": e.get("reason"), "verified": False, "date": o["date"]})
    for e in o["source_log"]:
        row = next((x for x in g["sources"] if x["source"] == e["source"]), None)
        if row is None:
            row = {"source": e["source"], "ok": 0, "failed": 0}
            g["sources"].append(row)
        row["ok" if e["ok"] else "failed"] += 1
        row["last"] = e["date"]
    band = assess.assessment_band(o)
    pr = o.get("primary")
    g["assessments"] = [x for x in g["assessments"] if x.get("project") != o["slug"]]
    g["assessments"].append({
        "project": o["slug"], "date": o["date"], "industry": o["customer"].get("industry"), "area": o["customer"].get("area"),
        "requirement_mbps": [o["customer"].get("requirement", {}).get("down_mbps"), o["customer"].get("requirement", {}).get("up_mbps")],
        "drivers": [d["key"] for d in o["customer"].get("drivers", [])], "status": o["status"],
        "architecture": o["customer"].get("requirement", {}).get("architecture") or (" → ".join(pr["nodes"]) if pr else None),
        "hops": len(pr["hops"]) if pr else 0, "hop_km": [h["distance_km"] for h in pr["hops"]] if pr else [],
        "equipment": [e.get("class") for e in pr["engineering"]] if pr else [],
        "assessment_band": [band["low"], band["high"]], "commercial_outcome": None, "field_findings": None})
    intel.save()


def cmd_learn(a):
    pdir = os.path.join(PROJECTS, a.slug)
    fv = json.load(open(os.path.join(pdir, "field-verification.json")))
    intel = IntelGraph(INTEL)
    for n in fv.get("nodes", []):
        n.setdefault("verified", True)
        n["verified_date"] = fv.get("date", TODAY)
        n["project"] = a.slug
        intel.g["nodes"] = [x for x in intel.g["nodes"] if haversine_km(x["lat"], x["lon"], n["lat"], n["lon"]) > 0.15]
        intel.g["nodes"].append(n)
    for r in fv.get("rejected_links", []):
        intel.g["rejected_links"].append(dict(r, verified=True, date=fv.get("date", TODAY), project=a.slug))
    for r in fv.get("verified_routes", []):
        intel.g["routes"].append(dict(r, verified=True, project=a.slug))
    for x in intel.g.setdefault("assessments", []):
        if x.get("project") == a.slug:
            x["commercial_outcome"] = fv.get("commercial_outcome", x.get("commercial_outcome"))
            x["field_findings"] = fv.get("findings", x.get("field_findings"))
    intel.save()
    print(f"intelligence graph: {len(intel.g['nodes'])} nodes, {len(intel.g['routes'])} routes, "
          f"{len(intel.g['rejected_links'])} rejected links")


def cmd_run(a):
    pdir = os.path.join(PROJECTS, a.slug) if not a.input else os.path.dirname(a.input)
    inp = json.load(open(a.input or os.path.join(pdir, "input.json")))
    log = SourceLog()
    ins = inp.get("inputs", {})
    rel = lambda p: os.path.join(pdir, p) if p and not os.path.isabs(p) else p  # noqa: E731
    if a.fixture:
        src = FixtureSources(log, json.load(open(a.fixture)))
        intel = IntelGraph(None)
    else:
        src = LiveSources(log, cell_csv=rel(ins.get("cell_csv")), kml=rel(ins.get("kml")),
                          points_csv=rel(ins.get("points_csv")))
        intel = IntelGraph(INTEL)
    o = run(inp, src, intel, load_equipment())
    o["customer"]["clutter_m"] = inp.get("params", {}).get("clutter_m", 0)
    out_dir = a.out or pdir
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "assessment.json"), "w") as f:
        json.dump(o, f, indent=2, ensure_ascii=False, default=str)
    md = report(o)
    with open(os.path.join(out_dir, "assessment.md"), "w") as f:
        f.write(md)
    if not a.fixture:
        store(o, intel)
    fails = [e for e in o["source_log"] if not e["ok"]]
    print(f"{o['status']} | radius {o.get('search', {}).get('final_radius_km')} km | "
          f"candidates {len(o.get('infrastructure', []))} | relays {len(o.get('relay_candidates', []))} | "
          f"primary {' → '.join(o['primary']['nodes']) if o.get('primary') else '—'} | "
          f"alt {' → '.join(o['alternative']['nodes']) if o.get('alternative') else '—'} | source failures {len(fails)}")
    print(f"report: {os.path.relpath(os.path.join(out_dir, 'assessment.md'), REPO)}")
    return o


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init"); i.add_argument("slug"); i.add_argument("--email"); i.add_argument("--location")  # noqa: E702
    i.add_argument("--force", action="store_true")
    r = sub.add_parser("run"); r.add_argument("slug"); r.add_argument("--fixture"); r.add_argument("--input")  # noqa: E702
    r.add_argument("--out")
    lr = sub.add_parser("learn"); lr.add_argument("slug")  # noqa: E702
    a = ap.parse_args()
    {"init": cmd_init, "run": cmd_run, "learn": cmd_learn}[a.cmd](a)


if __name__ == "__main__":
    main()
