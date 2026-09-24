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
    mbps = [int(x) for x in re.findall(r"(\d{2,5})\s*mbps", email.lower())]
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
            "requirement": {"down_mbps": max(mbps) if mbps else None, "up_mbps": max(mbps) if mbps else None,
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
        ev.add(f"Property coordinate {p['lat']}, {p['lon']}", p.get("source") or "input.json", "High")
        return p["lat"], p["lon"]
    parsed = parse_location(p.get("query"))
    if parsed:
        ev.add(f"Property coordinate {parsed[0]}, {parsed[1]}", f"Customer-supplied location '{p['query']}'", "High")
        p.update(lat=parsed[0], lon=parsed[1], source="customer")
        return parsed
    if p.get("query"):
        hits = src.geocode(p["query"])
        if hits:
            h = hits[0]
            ev.add(f"Property coordinate {h['lat']:.5f}, {h['lon']:.5f} ('{h['label'][:80]}')",
                   f"Geocoded '{p['query']}' ({h.get('osm_id', 'geocoder')}) — {len(hits)} candidate(s)",
                   "Medium" if len(hits) == 1 else "Low — confirm pin with customer")
            p.update(lat=h["lat"], lon=h["lon"], source="geocoded", geocode_candidates=hits[:5])
            return h["lat"], h["lon"]
    return None


def run(inp, src, intel, eq):
    ev = Evidence()
    log = src.log
    cust = inp["customer"]
    params = inp.get("params", {})
    out = {"slug": inp["slug"], "date": TODAY, "sources_mode": src.name, "customer": cust}

    loc = resolve_property(inp, src, ev)
    if not loc:
        out["status"] = "BLOCKED: property location unresolved"
        out["evidence"], out["source_log"] = ev.rows, log.entries
        return out
    lat, lon = loc
    prop = {"lat": lat, "lon": lon}
    out["property"] = inp["property"]

    pg = src.elevations([(lat, lon)])
    prop_ground = pg[0] if pg else None
    if prop_ground is not None:
        ev.add(f"Property ground elevation {prop_ground:.0f} m ASL", log.entries[-1]["source"], "Medium")

    radii = RADII.get(cust.get("area", "remote"), RADII["remote"])
    user_pts = src.user_points()
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
               " + ".join(s["evidence"]) or "—", {"CONFIRMED": "High", "PROBABLE": "Medium"}.get(s["confidence"], "Low"))
    if cells is not None and not cells:
        ev.add("No cells returned by cell database in search radius", "OpenCelliD", "Does NOT mean no mobile infrastructure")
    for h in high:
        ev.add(f"{h.get('name') or h['kind']} at {h['lat']:.5f}, {h['lon']:.5f}"
               + (f" ({h['ele']:.0f} m)" if h.get("ele") else "") + f" — {RELAY_LABEL}", h.get("ref", ""), "Inferred")

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
                       "Terrain profile from " + terrain_source(log), "Preliminary")
    for e in route["rejected"]:
        ev.add(f"REJECTED {e['a']} → {e['b']} ({e['distance_km']} km): {e.get('reason', e['status'])}",
               "Terrain profile from " + terrain_source(log), "Preliminary")
    out["evidence"], out["source_log"] = ev.rows, log.entries
    out["status"] = "ROUTE FOUND" if route["primary"] else "NO DESK ROUTE — field survey / wider search required"
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
    return {"nodes": [{k: v for k, v in n.items() if k != "site"} for n in nodes], "direct_candidates": direct,
            "primary": primary, "alternative": alternative, "distribution": distribution,
            "rejected": rejected_edges(pl)}


# ============================================================ report

def fmt_route(rt, nodes):
    names = {n["id"]: n for n in nodes}
    parts = []
    for nid in rt["nodes"]:
        n = names[nid]
        tag = {"customer": "", "carrier": f" [{n['confidence']}]", "relay": " [RELAY — FIELD VERIFY]",
               "structure": " [STRUCTURE — FIELD VERIFY]"}[n["role"]]
        parts.append(f"**{nid}** {n.get('name', '')}{tag}")
    return "\n→ ".join(parts)


def hop_table(rt):
    rows = ["| Hop | Dist | Az A/B | Terrain | Heights (A/B) | Fresnel clr | Class | FSPL | Rx | Margin | Confidence |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for h, e in zip(rt["hops"], rt["engineering"]):
        rows.append(f"| {h['a']}→{h['b']} | {h['distance_km']} km | {h.get('bearing_ab', '–')}°/{h.get('bearing_ba', '–')}° | "
                    f"{h['status']} | {h.get('h_a_m', '–')} m / {h.get('h_b_m', '–')} m | {h.get('fresnel_clearance_m', '–')} m | "
                    f"{e.get('class') or '—'} | {e.get('fspl_db', '–')} dB | {e.get('rx_dbm', '–')} dBm | "
                    f"{e.get('fade_margin_db', '–')} dB | {e['confidence']} |")
    return "\n".join(rows)


def report(o):
    c = o["customer"]
    L = [f"# CTTX Private Infrastructure Network Assessment — Preliminary Desk Study",
         f"**{c.get('company') or c.get('property') or o['slug']}** · {o['date']} · status: **{o['status']}** · data mode: {o['sources_mode']}", ""]
    if "property" not in o:
        L += ["Property location could not be resolved. Obtain a pin drop / coordinates from the customer.", ""]
        return "\n".join(L + evidence_md(o))
    nodes = o["nodes"]
    pr, alt = o.get("primary"), o.get("alternative")
    req = c.get("requirement", {})
    failed = sorted({e["source"] for e in o["source_log"] if not e["ok"]})

    # 1 executive summary
    L += ["## 1. Executive summary"]
    need = f"{req.get('down_mbps') or '?'} / {req.get('up_mbps') or '?'} Mbps" if req.get("down_mbps") else "capacity TBC"
    because = req.get("because") or "; ".join(d["driver"] for d in c.get("drivers", [])[:3])
    L.append(f"- **Need:** {need} because {because}.")
    L.append(f"- **Searched:** adaptive radius to {o['search']['final_radius_km']} km — "
             f"{len(o['infrastructure'])} infrastructure candidates, {len(o['relay_candidates'])} potential relay positions.")
    if pr:
        L.append(f"- **Desk finding:** a {len(pr['hops'])}-hop path appears engineerable to "
                 f"{nodes_by(nodes)[pr['nodes'][-1]]['name']} ({nodes_by(nodes)[pr['nodes'][-1]]['confidence']}).")
    else:
        L.append("- **Desk finding:** no desk-verifiable route within the search limits — a site survey is required.")
    if failed:
        L.append(f"- **Data gaps:** {', '.join(failed)} unavailable — confidence reduced accordingly.")
    L.append("- This is a desktop feasibility study. **Nothing here is final engineering feasibility** until the field "
             "verification items in §11 are closed.")

    # 2 drivers
    L += ["", "## 2. Business drivers", "| Business driver | Operational requirement | Network requirement | Technical solution | Stated by customer |",
          "|---|---|---|---|---|"]
    for d in c.get("drivers", []):
        L.append(f"| {d['driver']} | {d['operational']} | {d['network']} | {d['solution']} | {'Yes' if d.get('stated') else 'Inferred'} |")

    # 3 requirement
    L += ["", "## 3. Requirement"]
    for k in ("down_mbps", "up_mbps", "because", "availability", "latency", "architecture"):
        if req.get(k):
            L.append(f"- **{k.replace('_', ' ')}:** {req[k]}")
    if req.get("services"):
        L.append(f"- **services:** {', '.join(req['services'])}")
    ctx = {k: v for k, v in c.get("context", {}).items() if v}
    for k, v in ctx.items():
        L.append(f"- **{k.replace('_', ' ')}:** {v}")

    # 4 property
    p = o["property"]
    L += ["", "## 4. Property", f"- Coordinates: **{p['lat']}, {p['lon']}** (source: {p.get('source')}) — "
          f"[Google Maps](https://www.google.com/maps?q={p['lat']},{p['lon']})",
          f"- Boundary: {p.get('boundary', 'BOUNDARY APPROXIMATION')}"]
    if p.get("geocode_candidates") and len(p["geocode_candidates"]) > 1:
        L.append("- ⚠ Multiple geocoder matches — confirm the pin with the customer.")

    # 5 infrastructure
    L += ["", "## 5. Existing infrastructure", "| # | Candidate | Confidence | Dist / bearing | Operators | Height | Direct path from property | Backhaul evidence |",
          "|---|---|---|---|---|---|---|---|"]
    direct = {e["b"]: e for e in o["direct_candidates"]}
    for n in [n for n in nodes if n["role"] == "carrier"]:
        s = next(x for x in o["infrastructure"] if abs(x["lat"] - n["lat"]) < 1e-9 and abs(x["lon"] - n["lon"]) < 1e-9)
        d = direct.get(n["id"])
        verdict = f"{d['status']}" + (f" — {d['reason']}" if d and d.get("reason") else "") if d else "beyond max hop"
        L.append(f"| {n['id']} | {s['name']} | {s['confidence']}{' (cross-checked)' if s.get('cross_checked') else ''} | "
                 f"{s['distance_km']} km {compass(s['bearing_deg'])} | {', '.join(s['operators']) or '—'} | "
                 f"{str(s['height_m']) + ' m' if s.get('height_m') else 'UNKNOWN'} | {verdict} | "
                 f"{'; '.join(s['backhaul_evidence']) or '—'} |")
    if o["corridors"]:
        L += ["", "**Corridors (nearest):** " + "; ".join(f"{c_['kind']} {c_.get('name') or ''} {c_['distance_km']} km {c_['bearing']}"
                                                          for c_ in o["corridors"][:6])]
    if o["relay_candidates"]:
        L += ["", f"**High ground / structures** — {RELAY_LABEL}:"]
        for n in [n for n in nodes if n["role"] in ("relay", "structure")]:
            L.append(f"- {n['id']} {n['name']} {n['lat']:.5f}, {n['lon']:.5f}" + (f" · {n['ele']:.0f} m ASL" if n.get("ele") else "")
                     + f" · {n.get('ref', '')}")

    # 6/7 routes
    L += ["", "## 6. Primary route"]
    if pr:
        L += [fmt_route(pr, nodes), "", hop_table(pr), "",
              f"Termination: {BACKHAUL_LABEL} — carrier interconnect, rack/space, power and backhaul capacity "
              "require commercial confirmation with the site owner/operator."]
    else:
        L.append("No route passed terrain analysis. See rejected paths in §8.")
    L += ["", "## 7. Alternative route"]
    L += [fmt_route(alt, nodes), "", hop_table(alt)] if alt else ["No independent alternative found within the search limits."]
    if o.get("distribution"):
        L += ["", "### Multi-site distribution"]
        for d in o["distribution"]:
            L += [f"**{d['name']}**"] + ([fmt_route(d["route"], nodes), "", hop_table(d["route"])] if d["route"]
                                          else ["No desk-verifiable path — survey required."])

    # 8 terrain
    L += ["", "## 8. Terrain"]
    for rt in filter(None, [pr, alt]):
        for h in rt["hops"]:
            if "highest_obstruction" in h:
                L.append(f"- {h['a']}→{h['b']}: endpoints {h['ground_a_m']} / {h['ground_b_m']} m ASL; highest obstruction "
                         f"{h['highest_obstruction']['ele_m']} m at {h['highest_obstruction']['at_km']} km; lowest "
                         f"{h['lowest_point']['ele_m']} m; F1 mid {h['fresnel_mid_m']} m; earth bulge {h['earth_bulge_mid_m']} m; "
                         f"worst 60 % F1 clearance {h['fresnel_clearance_m']} m.")
            else:
                L.append(f"- {h['a']}→{h['b']}: {h.get('reason', 'terrain not analysed')}")
    if o["rejected"]:
        L += ["", "**Rejected paths (evidence):**"]
        for e in sorted(o["rejected"], key=lambda e: e["distance_km"])[:12]:
            L.append(f"- ❌ {e['a']}→{e['b']} {e['distance_km']} km — {e.get('reason', e['status'])}")

    # 9 link engineering summary
    L += ["", "## 9. Link engineering",
          "Planning classes from `equipment-library.json` (desk defaults, not datasheets). Throughput must be confirmed in "
          "Cambium LINKPlanner with the final radio profile; availability target per §3.",
          f"Fade-margin rule ≥ 20 dB; 60 % first-Fresnel clearance; k = 4/3; clutter allowance {o['customer'].get('clutter_m', 0)} m."]

    # 10 confidence
    L += ["", "## 10. Confidence"]
    conf = {"CONFIRMED": [], "PROBABLE": [], "INFERRED": [], "UNKNOWN": []}
    conf["CONFIRMED"].append(f"Property location ({p.get('source')})") if p.get("source") == "customer" else conf["PROBABLE"].append("Property location (geocoded)")
    for s in o["infrastructure"]:
        k = {"CONFIRMED": "CONFIRMED", "PROBABLE": "PROBABLE"}.get(s["confidence"], "UNKNOWN")
        conf[k].append(f"{s['name']} physical site")
    if pr:
        conf["INFERRED"].append("Primary route LOS/Fresnel (DEM, no clutter survey)")
        conf["INFERRED"].append("Link budgets (planning classes)")
    conf["UNKNOWN"] += ["Mast heights not in any source", "Carrier backhaul / interconnect availability",
                        "Access permissions & power at relay/carrier sites"]
    for k, v in conf.items():
        L.append(f"- **{k}:** " + ("; ".join(v) if v else "—"))

    # 11 field verification
    L += ["", "## 11. Field verification"]
    fv = ["Confirm property pin, mounting position and achievable mast height at the customer site",
          "Line-of-sight check from each hop endpoint (binoculars/drone/photo at bearing) incl. trees & buildings"]
    for rt in filter(None, [pr, alt]):
        for nid in rt["nodes"]:
            n = nodes_by(nodes)[nid]
            if n["role"] == "carrier":
                fv.append(f"{nid} {n['name']}: confirm structure exists, owner/operator, height, free mounting space, power, "
                          "interconnect/backhaul terms")
            elif n["role"] in ("relay", "structure"):
                fv.append(f"{nid} {n['name']}: landowner permission, access road, power (solar), mast foundation, "
                          f"{'~' + str(n['h_design']) + ' m mast'}")
    fv.append("Spectrum scan at each endpoint (5 GHz noise floor)")
    L += [f"- [ ] {x}" for x in dict.fromkeys(fv)]

    # 12 commercial
    L += ["", "## 12. Commercial opportunity",
          "- **Sell first:** CTTX Private Infrastructure Network Assessment (site survey + LOS verification + final design).",
          f"- **Infrastructure:** {len(pr['hops']) if pr else '?'}-hop private backhaul"
          + (f" to {nodes_by(nodes)[pr['nodes'][-1]]['name']}" if pr else "") + ".",
          "- **Redundant route:** " + ("alternative path identified — offer as resilience phase." if alt else "to be designed after survey."),
          "- **Private network:** " + ("multi-site distribution across customer sites." if o.get("distribution") else
                                       "on-site LAN/Wi-Fi, CCTV and VoIP segments driven by §2."),
          "", "### What we know / believe / need to verify / what the network could look like / what the assessment will confirm",
          f"- **Know:** property location; {sum(s['confidence'] == 'CONFIRMED' for s in o['infrastructure'])} confirmed sites.",
          f"- **Believe:** {sum(s['confidence'] == 'PROBABLE' for s in o['infrastructure'])} probable carrier sites; "
          + ("desk route clears terrain." if pr else "no desk route yet."),
          "- **Verify:** see §11.",
          "- **Could look like:** " + (" → ".join(nodes_by(nodes)[x]["name"] for x in pr["nodes"]) + " → network core" if pr else "TBD after survey"),
          "- **Assessment confirms:** LOS, heights, permissions, backhaul terms, final radio selection & price."]
    L += [""] + evidence_md(o)
    return "\n".join(L)


def nodes_by(nodes):
    return {n["id"]: n for n in nodes}


def evidence_md(o):
    L = ["## Evidence register", "| Claim | Source | Date | Confidence |", "|---|---|---|---|"]
    for r in o["evidence"]:
        L.append(f"| {r['claim']} | {r['source']} | {r['date']} | {r['confidence']} |")
    L += ["", "### Source log"]
    for e in o["source_log"]:
        L.append(f"- {'✅' if e['ok'] else '❌ FAILED'} {e['source']} — {e['action']}: {e['detail'][:160]}")
    L += ["", "### Assumptions (not facts)",
          f"- Design antenna heights where unknown: customer {DEFAULT_HEIGHTS['customer'][0]} m (max {DEFAULT_HEIGHTS['customer'][1]} m), "
          f"carrier mast mounting {DEFAULT_HEIGHTS['carrier'][0]} m, new relay mast {DEFAULT_HEIGHTS['relay'][0]}–{DEFAULT_HEIGHTS['relay'][1]} m.",
          "- DEM terrain excludes vegetation/buildings unless clutter allowance is set."]
    return L


# ============================================================ store / learn

def store(o, intel):
    """Log desk results (unverified) so future assessments reuse them."""
    if not intel or "property" not in o:
        return
    g = intel.g
    for s in o["infrastructure"]:
        if not any(abs(n["lat"] - s["lat"]) < 1e-4 and abs(n["lon"] - s["lon"]) < 1e-4 for n in g["nodes"]):
            g["nodes"].append({"name": s["name"], "lat": s["lat"], "lon": s["lon"], "kind": "carrier",
                               "operator": ", ".join(s["operators"]), "height_m": s.get("height_m"),
                               "verified": False, "confidence": s["confidence"], "first_seen": o["date"],
                               "project": o["slug"]})
    g["routes"] = [r for r in g["routes"] if r.get("project") != o["slug"]]
    if o.get("primary"):
        g["routes"].append({"project": o["slug"], "date": o["date"], "verified": False,
                            "nodes": [dict(lat=n["lat"], lon=n["lon"], name=n.get("name"), id=n["id"])
                                      for n in o["nodes"] if n["id"] in o["primary"]["nodes"]]})
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
