"""Solution-architect layer (spec v1.0 'Solution Architect' edition).

Turns the raw discovery/routing result into: evidence statuses, graph edge classes, candidate
mast positions, technology options, the six-layer architecture, redundancy by failure mode,
assessment pricing band and the §17 architect checklist. Nothing here invents data: every
output is derived from the run result or labelled ASSUMED / UNKNOWN / FIELD VERIFY.
"""
from geo import haversine_km

STATUSES = ["VERIFIED", "SOURCE-DERIVED", "CALCULATED", "INFERRED", "ASSUMED", "UNKNOWN", "FIELD VERIFY"]
EDGE_CLASSES = ["VERIFIED", "PROBABLE", "CANDIDATE", "UNKNOWN", "REJECTED"]
MAST_LABEL = "Candidate mast position — requires field verification"
CRITICAL_DRIVERS = {"scada", "production", "safety", "security", "pos"}
PRICE_MIN, PRICE_MAX = 7500, 25000


# ------------------------------------------------------------------ graph edges

def edge_class(e, nodes, intel=None):
    """VERIFIED only when a field-verified route contains both ends; terrain-clear edges between
    evidenced endpoints are PROBABLE; clear edges touching an unverified relay are CANDIDATE."""
    if e["status"] in ("BLOCKED", "MARGINAL"):
        return "REJECTED"
    if e["status"] == "UNVERIFIED":
        return "UNKNOWN"
    if intel:
        for r in intel.g.get("routes", []):
            if r.get("verified") and _route_has(r, nodes[e["a"]]) and _route_has(r, nodes[e["b"]]):
                return "VERIFIED"
    ends = [nodes[e["a"]], nodes[e["b"]]]
    if all(n["role"] == "customer" or n["confidence"] in ("CONFIRMED", "PROBABLE") for n in ends):
        return "PROBABLE"
    return "CANDIDATE"


def _route_has(route, n):
    return any(haversine_km(p["lat"], p["lon"], n["lat"], n["lon"]) < 0.15 for p in route.get("nodes", []))


# ------------------------------------------------------------------ mast-location engine

def mast_candidates(o, memo_edges):
    """Profile every relay/structure node (spec §8)."""
    nodes = {n["id"]: n for n in o["nodes"]}
    prop = nodes["PROPERTY"]
    carriers = [n for n in o["nodes"] if n["role"] == "carrier"]
    roads = [c for c in o.get("all_corridors", []) if c["kind"].startswith("road:")]
    power = [c for c in o.get("all_corridors", []) if c["kind"] in ("power_line", "substation")]
    prop_ele = o.get("property_ground_m")
    used = {x for rt in filter(None, [o.get("primary"), o.get("alternative")]) for x in rt["nodes"]}
    out = []
    for n in o["nodes"]:
        if n["role"] not in ("relay", "structure"):
            continue
        near_c = sorted(carriers, key=lambda c: haversine_km(n["lat"], n["lon"], c["lat"], c["lon"]))[:2]
        vis = {}
        for other in [prop] + near_c:
            e = memo_edges.get(tuple(sorted((n["id"], other["id"]))))
            vis[other["id"]] = e["status"] if e else "not analysed"
        road = min((haversine_km(n["lat"], n["lon"], c["lat"], c["lon"]) for c in roads), default=None)
        pw = min((haversine_km(n["lat"], n["lon"], c["lat"], c["lon"]) for c in power), default=None)
        kind = n.get("name") or ""
        reason = ("mapped peak/hill" if "osm" in str(n.get("ref", "")) and n["role"] == "relay" else
                  "existing tall structure" if n["role"] == "structure" else
                  "DEM local maximum above the property" if "DEM" in str(n.get("ref", "")) else "user-supplied point")
        out.append({
            "id": n["id"], "name": kind, "lat": round(n["lat"], 5), "lon": round(n["lon"], 5),
            "ele_m": n.get("ele"), "relative_m": round(n["ele"] - prop_ele) if n.get("ele") and prop_ele is not None else None,
            "dist_property_km": round(haversine_km(n["lat"], n["lon"], prop["lat"], prop["lon"]), 2),
            "dist_carriers": {c["id"]: round(haversine_km(n["lat"], n["lon"], c["lat"], c["lon"]), 2) for c in near_c},
            "visibility": vis,
            "access": f"nearest mapped major road {road:.1f} km (farm tracks not mapped)" if road is not None else "UNKNOWN — no road data",
            "power": f"mapped power line/substation {pw:.1f} km" if pw is not None else "UNKNOWN — assume solar until surveyed",
            "ownership": "UNKNOWN — landowner/servitude to be identified",
            "reason": reason, "in_route": n["id"] in used,
            "confidence": "INFERRED", "label": MAST_LABEL})
    return sorted(out, key=lambda m: (not m["in_route"], -(m["ele_m"] or 0)))


# ------------------------------------------------------------------ technology options

def technology_options(o):
    drivers = {d["key"] for d in o["customer"].get("drivers", [])}
    req = o["customer"].get("requirement", {})
    facts = o.get("known_facts", [])
    hops = [h for rt in filter(None, [o.get("primary"), o.get("alternative")]) for h in rt["hops"]]
    n_sites = 1 + len(o.get("distribution", []))
    opts = []
    add = lambda tech, role, why, status="INFERRED": opts.append(  # noqa: E731
        {"technology": tech, "role": role, "why": why, "status": status})
    if any(f.get("kind") == "fibre" for f in facts):
        add("Carrier fibre (e.g. Vodacom Business Connect / BI Fibre)", "Layer 2 backhaul — primary",
            "Fibre confirmed at/near the property by the carrier; highest capacity, no mast build", "SOURCE-DERIVED")
    if any(f.get("kind") == "coverage" for f in facts):
        add("Carrier fixed-wireless service", "Interim / relocatable backhaul",
            "Carrier offer on record — check it meets the capacity requirement")
    if hops:
        short = [h for h in hops if h["distance_km"] <= 1.5]
        mid = [h for h in hops if 1.5 < h["distance_km"] <= 5]
        long_ = [h for h in hops if h["distance_km"] > 5]
        if short:
            add("60 GHz PtP (Siklu / Cambium 60 GHz)", "Short high-capacity hops",
                f"{len(short)} hop(s) ≤ 1.5 km; licence-exempt, multi-gigabit class, rain/oxygen limits range")
        if mid:
            add("E-band 70/80 GHz (Siklu EtherHaul class) or 5 GHz PtP", "Mid hops",
                f"{len(mid)} hop(s) 1.5–5 km; E-band for capacity (light licence, rain fade to calculate), 5 GHz for robustness")
        if long_:
            add("5 GHz carrier-grade PtP (Cambium PTP 670/550, Proxim Tsunami)", "Long hops",
                f"{len(long_)} hop(s) > 5 km; licence-exempt, needs spectrum scan & fade margin ≥ 20 dB")
        if drivers & {"scada", "production", "safety"} or "99.9" in str(req.get("availability", "")):
            add("Licensed microwave (6–23 GHz)", "Carrier-grade backhaul for critical services",
                "Protected spectrum for SCADA/POS/security SLAs; ICASA licence & lead time required")
    if n_sites >= 3:
        add("PMP distribution (Cambium PMP 450 / ePMP, Proxim)", "Layer 3 distribution",
            f"{n_sites} customer sites — one sector serves several buildings")
    elif n_sites == 2:
        add("Distribution PtP", "Layer 3 distribution", "Second customer site")
    if drivers & {"guest", "staff", "cloud", "voip"}:
        add("Managed Wi-Fi / LAN (Cambium cnPilot/XV class, switches)", "Layer 4 access",
            "Guest/staff/office access driven by stated business drivers")
    if "mobility" in drivers:
        add("LEO satellite (OneWeb / Starlink business)", "Relocatable / mobile sites",
            "Connectivity must move with projects; also a diverse backup path")
    if not opts:
        add("UNKNOWN — insufficient route/requirement data", "—", "Complete discovery first", "UNKNOWN")
    return opts


def rf_notes(hop, eng):
    f = eng.get("freq_mhz") or 0
    rain = ("negligible below ~10 GHz (INFERRED)" if f and f < 10000 else
            "significant — ITU-R P.530/P.838 calculation required (UNKNOWN)" if f else "UNKNOWN")
    intf = ("licence-exempt band — interference risk UNKNOWN until spectrum scan (FIELD VERIFY)" if f and f < 10000 or 57000 <= f <= 66000
            else "licensed/light-licensed — coordinate via ICASA (FIELD VERIFY)")
    return {"rain": rain, "interference": intf,
            "modulation_throughput": ("from verified radio profile" if eng.get("capacity_mbps")
                                      else "UNKNOWN — requires manufacturer profile (LINKPlanner) — not estimated")}


# ------------------------------------------------------------------ six-layer architecture

def layers(o):
    nodes = {n["id"]: n for n in o["nodes"]}
    pr, alt = o.get("primary"), o.get("alternative")
    drivers = [d for d in o["customer"].get("drivers", [])]
    L = {}
    phys = []
    for rt in filter(None, [pr, alt]):
        for nid in rt["nodes"]:
            n = nodes[nid]
            if n["role"] == "carrier":
                phys.append(f"{nid} existing carrier structure ({n['confidence']}) — mounting space FIELD VERIFY")
            elif n["role"] in ("relay", "structure"):
                phys.append(f"{nid} new/borrowed relay mast ~{n['h_design']} m (ASSUMED), solar power (ASSUMED) — {MAST_LABEL}")
    if pr or alt:
        phys.append(f"Customer mast/roof mount ~{nodes['PROPERTY']['h_design']} m (ASSUMED)")
    if any(f.get("kind") == "fibre" for f in o.get("known_facts", [])):
        phys.append("Fibre entry, demarcation and internal cable route (FIELD VERIFY)")
    L["1 Physical infrastructure"] = list(dict.fromkeys(phys))
    bh = []
    if any(f.get("kind") == "fibre" for f in o.get("known_facts", [])):
        bh.append("Carrier fibre service (SOURCE-DERIVED availability)")
    if pr:
        bh.append("Primary: " + " → ".join(pr["nodes"]) + f" ({len(pr['hops'])} hop(s), planning classes)")
    if alt:
        bh.append("Alternative: " + " → ".join(alt["nodes"]))
    L["2 Backhaul"] = bh or ["UNKNOWN — no backhaul path established"]
    dist = [f"{d['name']}: " + (" → ".join(d["route"]["nodes"]) if d["route"] else "no desk path") for d in o.get("distribution", [])]
    L["3 Distribution"] = dist or ["Single site — core switch/router at property"]
    access_map = {"guest": "Guest Wi-Fi (segregated SSID, captive portal)", "staff": "Staff / accommodation Wi-Fi (segregated)",
                  "cloud": "Office LAN / Wi-Fi", "voip": "Voice VLAN with QoS", "pos": "POS VLAN (isolated)",
                  "cctv": "CCTV network (PoE, isolated VLAN)", "security": "Security/access-control network",
                  "scada": "SCADA/OT network (segregated)", "iot": "Field IoT (LoRaWAN) gateways",
                  "intersite": "Site LANs per building", "mobility": "Portable site kits (LEO terminal + router)",
                  "production": "OT/production network (segregated)", "safety": "Emergency comms endpoints"}
    acc = [access_map[d["key"]] for d in drivers if d.get("key") in access_map]
    L["4 Access"] = acc or ["Customer LAN (requirements UNKNOWN)"]
    L["5 Services"] = [d["driver"] for d in drivers] or ["UNKNOWN"]
    L["6 Management"] = ["Radio/NMS monitoring and alerting, remote management, as-built documentation and link records"]
    return L


# ------------------------------------------------------------------ redundancy by failure mode

def redundancy(o):
    drivers = {d["key"] for d in o["customer"].get("drivers", [])}
    critical = drivers & CRITICAL_DRIVERS
    avail = str(o["customer"].get("requirement", {}).get("availability", "")).lower()
    pr, alt = o.get("primary"), o.get("alternative")
    out = []
    if not critical and not any(w in avail for w in ("99.9", "critical", "sla", "high")):
        out.append({"measure": "None beyond good engineering practice", "protects_against": "—",
                    "justification": "No business-critical driver or availability target stated — redundancy not justified yet"})
        return out
    if alt:
        out.append({"measure": "Diverse second path: " + " → ".join(alt["nodes"]),
                    "protects_against": f"loss of carrier site {pr['nodes'][-1]} or any primary hop",
                    "justification": f"critical drivers: {', '.join(sorted(critical)) or avail}"})
    elif pr:
        out.append({"measure": "Diverse path UNKNOWN — none found at desk", "protects_against": "single-point failure of the primary route",
                    "justification": "investigate during survey"})
    out.append({"measure": "Alternate-carrier / LEO failover", "protects_against": "carrier backhaul outage, fibre cut, cable theft",
                "justification": "independent upstream provider"})
    if pr and any(n.startswith("R") for n in pr["nodes"]):
        out.append({"measure": "Battery/solar autonomy at relay sites (days TBD)", "protects_against": "grid failure / load shedding at relays",
                    "justification": "relay sites have no confirmed power"})
    return out


# ------------------------------------------------------------------ assessment pricing (spec §13)

def assessment_band(o):
    """Indicative CTTX Private Infrastructure Network Assessment band within R7,500–R25,000."""
    f = []
    pr = o.get("primary")
    n_sites = 1 + len(o.get("distribution", []))
    hops = len(pr["hops"]) if pr else 0
    if n_sites > 1:
        f.append((f"{n_sites} sites", 2500 * min(3, n_sites - 1)))
    if hops > 1:
        f.append((f"{hops}-hop route", 2500 * min(2, hops - 1)))
    if pr and any(n.startswith("R") for n in pr["nodes"]):
        f.append(("new relay position(s) to survey", 2500))
    if len(o.get("rejected", [])) >= 3:
        f.append(("terrain-constrained (multiple rejected paths)", 2500))
    if o["customer"].get("area") == "remote":
        f.append(("remote site / travel", 2500))
    if not pr and not any(k.get("kind") == "fibre" for k in o.get("known_facts", [])):
        f.append(("no desk route — wider field search", 2500))
    complexity = sum(v for _, v in f)
    lo = PRICE_MIN + complexity
    hi = min(PRICE_MAX, lo + 5000)
    lo = min(lo, PRICE_MAX)
    simple = complexity == 0 and any(k.get("kind") == "fibre" for k in o.get("known_facts", []))
    return {"low": lo, "high": hi, "factors": f, "recommend_paid_assessment": not simple,
            "note": ("Straightforward carrier-service case — a paid assessment is not justified; "
                     "offer a site visit only if on-premises works are needed." if simple else
                     "Indicative range per CTTX spec §13; final price via the quoting skill.")}


# ------------------------------------------------------------------ §17 architect checklist

def checklist(o):
    pr, alt = o.get("primary"), o.get("alternative")
    req = o["customer"].get("requirement", {})
    fibre = any(k.get("kind") == "fibre" for k in o.get("known_facts", []))
    near = o["infrastructure"][0] if o.get("infrastructure") else None
    direct_blocked = [e for e in o.get("direct_candidates", []) if e["status"] in ("BLOCKED", "MARGINAL")]
    band = assessment_band(o)
    return [
        ("What is the customer trying to achieve?", req.get("because") or "UNKNOWN — confirm with customer"),
        ("What infrastructure already exists?", f"{len(o.get('infrastructure', []))} candidate site(s)"
         + ("; carrier-confirmed fibre" if fibre else "")),
        ("Nearest useful infrastructure?", f"{near['name']} {near['distance_km']} km ({near['confidence']})" if near else
         ("carrier fibre at the property" if fibre else "UNKNOWN")),
        ("Shortest practical path?", " → ".join(pr["nodes"]) if pr else ("fibre" if fibre else "none established")),
        ("What terrain prevents it?", f"{len(direct_blocked)} direct path(s) blocked/marginal" if direct_blocked else
         ("not analysed (no DEM)" if not any("levation" in e["source"] and e["ok"] for e in o["source_log"]) else "none on the chosen path")),
        ("Can an intermediate mast solve it?", "yes — " + ", ".join(x for x in pr["nodes"] if x.startswith("R")) if pr and any(x.startswith("R") for x in pr["nodes"]) else "not required / not established"),
        ("Can an existing tower solve it?", "yes — " + pr["nodes"][-1] if pr else "UNKNOWN"),
        ("Can fibre solve part of the route?", "yes (carrier-confirmed)" if fibre else "UNKNOWN — no fibre evidence"),
        ("What redundancy is required?", "; ".join(r["measure"] for r in redundancy(o))),
        ("What must be physically surveyed?", "see Field Survey Requirements"),
        ("What is commercially viable?", "carrier fibre" if fibre and not pr else
         (f"{len(pr['hops'])}-hop private backhaul" if pr else "UNKNOWN until survey")),
        ("What assessment should CTTX sell?", ("Private Infrastructure Network Assessment R"
                                               + f"{band['low']:,}–R{band['high']:,}".replace(",", " ")
                                               if band["recommend_paid_assessment"] else band["note"])),
    ]


# ------------------------------------------------------------------ information gaps

def information_gaps(o):
    gaps = []
    c = o["customer"]
    for k, v in c.get("context", {}).items():
        if not v or str(v).lower().startswith("not stated"):
            gaps.append(f"Customer {k.replace('_', ' ')} — not stated")
    for f in o.get("property", {}).get("features", []):
        if f.get("lat") is None:
            gaps.append(f"Coordinates for property feature '{f.get('name')}' ({f.get('kind', '')}) — obtain pin")
    if "BOUNDARY APPROXIMATION" in str(o.get("property", {}).get("boundary", "")):
        gaps.append("Property boundary — obtain KML/cadastral")
    for s in o.get("infrastructure", []):
        if not s.get("height_m"):
            gaps.append(f"Height of {s['name']} — not in any source")
    for src in sorted({e["source"] for e in o.get("source_log", []) if not e["ok"]}):
        gaps.append(f"Source unavailable: {src}")
    gaps.append("Radio modulation/throughput — requires manufacturer profiles (not estimated)")
    return list(dict.fromkeys(gaps))
