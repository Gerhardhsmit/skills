"""Discovery → terrain → hop graph → link engineering. Pure logic; data comes from a Sources adapter."""
import heapq
import itertools
import json
import math
import os

from geo import (FRESNEL_CLEAR, bearing_deg, destination, earth_bulge_m, fresnel_m, fspl_db,
                 haversine_km, interpolate)
from sources import TODAY

HERE = os.path.dirname(os.path.abspath(__file__))

RADII = {"urban": [2, 5, 10], "suburban": [5, 10, 20], "rural": [5, 10, 20, 40], "remote": [5, 10, 20, 40, 60]}
CONF_ORDER = ["CONFIRMED", "PROBABLE", "CELL LOCATION ONLY", "UNKNOWN"]
TARGET_PENALTY = {"CONFIRMED": 0, "PROBABLE": 4, "CELL LOCATION ONLY": 12, "UNKNOWN": 25}

# Design heights are ASSUMPTIONS (labelled as such in the report), never presented as facts.
DEFAULT_HEIGHTS = {  # (design_m, max_m)
    "customer": (9, 30),
    "carrier": (30, 30),      # unknown mast: assume 30 m mounting position is available → field verify
    "relay": (12, 30),        # new relay mast on high ground
    "structure": (15, 15),    # water tower / silo
}
RELAY_LABEL = "POTENTIAL RELAY LOCATION — FIELD VERIFICATION REQUIRED"
BACKHAUL_LABEL = "POTENTIAL CARRIER INTERCONNECT / BACKHAUL POINT"


class Evidence:
    def __init__(self):
        self.rows = []

    def add(self, claim, source, confidence, date=TODAY, status="SOURCE-DERIVED"):
        self.rows.append({"claim": claim, "status": status, "source": source, "date": date, "confidence": confidence})


def load_equipment():
    with open(os.path.join(HERE, "equipment-library.json")) as f:
        return json.load(f)


# ============================================================ discovery

def cluster_cells(cells, join_km=0.3):
    clusters = []
    for c in sorted(cells, key=lambda c: (c["lat"], c["lon"])):
        for cl in clusters:
            if haversine_km(cl["lat"], cl["lon"], c["lat"], c["lon"]) <= join_km:
                cl["cells"].append(c)
                n = len(cl["cells"])
                cl["lat"] += (c["lat"] - cl["lat"]) / n
                cl["lon"] += (c["lon"] - cl["lon"]) / n
                break
        else:
            clusters.append({"lat": c["lat"], "lon": c["lon"], "cells": [c]})
    return clusters


def build_sites(prop, osm, cells, user_pts, intel_nodes, ev):
    """Merge independent evidence into physical-site candidates with a confidence class."""
    sites = []
    for n in intel_nodes:
        if n.get("kind") in ("carrier", "mast", "tower", "fibre_pop"):
            sites.append({"name": n.get("name", "Intel node"), "lat": n["lat"], "lon": n["lon"],
                          "height_m": n.get("height_m"), "operator": n.get("operator", ""),
                          "evidence": [f"CTTX Intelligence Graph ({'field-verified' if n.get('verified') else 'desk'})"],
                          "verified": bool(n.get("verified")), "structure": True, "cells": []})
    for m in (osm or {}).get("masts", []):
        sites.append({"name": m.get("name") or "OSM mast", "lat": m["lat"], "lon": m["lon"],
                      "height_m": m.get("height_m"), "operator": m.get("operator", ""),
                      "evidence": [f"OpenStreetMap {m['ref']} {m.get('tags', {})}"], "verified": False,
                      "structure": True, "cells": []})
    for p in user_pts:
        kind = (p.get("kind") or p.get("name", "")).lower()
        if any(k in kind for k in ("mast", "tower", "vodacom", "mtn", "telkom", "cell c", "carrier", "pop")):
            sites.append({"name": p.get("name", "User point"), "lat": p["lat"], "lon": p["lon"],
                          "height_m": float(p["height_m"]) if p.get("height_m") else None,
                          "operator": p.get("operator", ""), "evidence": [p["source"]],
                          "verified": str(p.get("verified", "")).lower() in ("1", "true", "yes", "y"),
                          "structure": True, "cells": []})
    # de-duplicate structures from different sources within 150 m (keeps independent evidence together)
    merged = []
    for s in sites:
        twin = next((m for m in merged if haversine_km(m["lat"], m["lon"], s["lat"], s["lon"]) <= 0.15), None)
        if twin:
            twin["evidence"] += s["evidence"]
            twin["verified"] = twin["verified"] or s["verified"]
            twin["height_m"] = twin["height_m"] or s["height_m"]
            twin["operator"] = twin["operator"] or s["operator"]
            if twin["name"] in ("OSM mast", "User point") and s["name"] not in ("OSM mast", "User point"):
                twin["name"] = s["name"]
        else:
            merged.append(s)
    sites = merged
    for cl in cluster_cells(cells or []):
        host = min(sites, key=lambda s: haversine_km(s["lat"], s["lon"], cl["lat"], cl["lon"]), default=None)
        if host and haversine_km(host["lat"], host["lon"], cl["lat"], cl["lon"]) <= 0.5:
            host["cells"] += cl["cells"]
        else:
            sites.append({"name": "Cell cluster", "lat": cl["lat"], "lon": cl["lon"], "height_m": None,
                          "operator": "", "evidence": [], "verified": False, "structure": False,
                          "cells": cl["cells"]})
    for s in sites:
        ops = sorted({c["operator"] for c in s["cells"]})
        radios = sorted({c["radio"] for c in s["cells"]})
        if s["cells"]:
            s["evidence"].append(f"{s['cells'][0]['source']}: {len(s['cells'])} cells, {'/'.join(ops)}, {'/'.join(radios)}")
        s["operators"] = sorted(set(ops) | ({s["operator"]} if s["operator"] else set()))
        s["radios"] = radios
        s["vodacom"] = any("vodacom" in o.lower() for o in s["operators"])
        independent = len({e.split(" ")[0] for e in s["evidence"]})
        if s["verified"]:
            s["confidence"] = "CONFIRMED"
        elif s["structure"] and s["cells"]:
            s["confidence"] = "PROBABLE"
            s["cross_checked"] = True
        elif s["structure"]:
            s["confidence"] = "PROBABLE"
        elif len(s["cells"]) >= 3 and len(radios) >= 2:
            s["confidence"] = "PROBABLE"
        elif s["cells"]:
            s["confidence"] = "CELL LOCATION ONLY"
        else:
            s["confidence"] = "UNKNOWN"
        s["independent_sources"] = independent
        s["distance_km"] = round(haversine_km(prop["lat"], prop["lon"], s["lat"], s["lon"]), 2)
        s["bearing_deg"] = round(bearing_deg(prop["lat"], prop["lon"], s["lat"], s["lon"]), 1)
        if s["name"] == "Cell cluster":
            s["name"] = f"{'/'.join(s['operators']) or 'Cell'} site {s['distance_km']} km {compass(s['bearing_deg'])}"
    return sites


def compass(b):
    return ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"][
        int((b + 11.25) // 22.5) % 16]


def backhaul_evidence(site, corridors):
    ev = []
    if len(site["operators"]) >= 2:
        ev.append(f"multiple operators observed ({', '.join(site['operators'])})")
    if site["confidence"] in ("CONFIRMED", "PROBABLE") and site["structure"]:
        ev.append("established telecom structure mapped")
    for c in corridors:
        d = haversine_km(site["lat"], site["lon"], c["lat"], c["lon"])
        if c["kind"].startswith("road:") and d <= 2:
            ev.append(f"{c['kind'].split(':')[1]} road {c.get('name') or ''} {d:.1f} km".replace("  ", " "))
            break
    if any(c["kind"] == "substation" and haversine_km(site["lat"], site["lon"], c["lat"], c["lon"]) <= 3
           for c in corridors):
        ev.append("substation/utility corridor within 3 km")
    return ev


def _grid(prop, radius_km, n):
    step = 2 * radius_km / n
    pts = []
    for i in range(n + 1):
        for j in range(n + 1):
            dy, dx = -radius_km + i * step, -radius_km + j * step
            if math.hypot(dx, dy) <= radius_km:
                lat, lon = destination(prop["lat"], prop["lon"], 0, dy)
                pts.append(((i, j), destination(lat, lon, 90, dx)))
    return pts, step


def terrain_high_ground(prop, radius_km, src, prop_ground):
    """Grid-sample the DEM (fine inner grid ≤ 10 km + coarse outer grid) and return local maxima
    that rise ≥ 30 m above the property. Candidates only — never claimed as usable sites."""
    out = []
    grids = [(min(radius_km, 10), 24)] + ([(radius_km, 24)] if radius_km > 10 else [])
    for rad, n in grids:
        pts, step = _grid(prop, rad, n)
        z = src.elevations([p for _, p in pts])
        if z is None:
            return None
        zmap = {ij: (p, zz) for (ij, p), zz in zip(pts, z)}
        for (i, j), (p, zz) in zmap.items():
            neigh = [zmap[(i + a, j + b)][1] for a in (-1, 0, 1) for b in (-1, 0, 1)
                     if (a or b) and (i + a, j + b) in zmap]
            if len(neigh) >= 5 and zz >= max(neigh) and zz >= prop_ground + 30:
                out.append({"lat": p[0], "lon": p[1], "ele": round(zz), "kind": "terrain local maximum",
                            "ref": f"DEM grid {step:.1f} km"})
    return sorted(out, key=lambda p: -p["ele"])[:8]


# ============================================================ terrain per link

def profile(a, b, src, clutter_m=0.0):
    d = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
    n = int(min(120, max(20, d / 0.15)))
    pts = interpolate(a["lat"], a["lon"], b["lat"], b["lon"], n)
    z = src.elevations(pts)
    return {"d_km": d, "pts": pts, "z": z, "clutter_m": clutter_m}


def clearance(pr, ha, hb, f_ghz):
    """Return worst Fresnel clearance, worst LOS clearance and where, for antenna heights above ground."""
    d, z, n = pr["d_km"], pr["z"], len(pr["z"]) - 1
    top_a, top_b = z[0] + ha, z[-1] + hb
    worst = (math.inf, None)
    worst_los = math.inf
    for i in range(1, n):
        d1 = d * i / n
        d2 = d - d1
        los = top_a + (top_b - top_a) * i / n
        ground = z[i] + pr["clutter_m"] + earth_bulge_m(d1, d2)
        c_los = los - ground
        c_f = c_los - FRESNEL_CLEAR * fresnel_m(d1, d2, f_ghz)
        worst_los = min(worst_los, c_los)
        if c_f < worst[0]:
            worst = (c_f, i)
    return worst[0], worst_los, worst[1]


def analyse_link(a, b, src, f_ghz, clutter_m=0.0):
    """Terrain verdict for A↔B trying design heights, then max heights."""
    d = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
    res = {"a": a["id"], "b": b["id"], "distance_km": round(d, 2),
           "bearing_ab": round(bearing_deg(a["lat"], a["lon"], b["lat"], b["lon"]), 1),
           "bearing_ba": round(bearing_deg(b["lat"], b["lon"], a["lat"], a["lon"]), 1)}
    pr = profile(a, b, src, clutter_m)
    if pr["z"] is None:
        res.update(status="UNVERIFIED", reason="no elevation data — terrain not analysed; LOS NOT assumed")
        return res
    z, n = pr["z"], len(pr["z"]) - 1
    hi = max(range(1, n), key=lambda i: z[i])
    lo = min(range(1, n), key=lambda i: z[i])
    res.update(ground_a_m=round(z[0]), ground_b_m=round(z[-1]),
               highest_obstruction={"ele_m": round(z[hi]), "at_km": round(d * hi / n, 2)},
               lowest_point={"ele_m": round(z[lo]), "at_km": round(d * lo / n, 2)},
               elevation_diff_m=round(z[-1] - z[0]), fresnel_mid_m=round(fresnel_m(d / 2, d / 2, f_ghz), 1),
               earth_bulge_mid_m=round(earth_bulge_m(d / 2, d / 2), 1))
    ha, hb = a["h_design"], b["h_design"]
    cf, cl, wi = clearance(pr, ha, hb, f_ghz)
    res.update(h_a_m=ha, h_b_m=hb, fresnel_clearance_m=round(cf, 1), los_clearance_m=round(cl, 1),
               worst_at_km=round(d * wi / n, 2) if wi else None, worst_ground_m=round(z[wi]) if wi else None)
    if cf >= 0:
        res["status"] = "CLEAR"
        return res
    # try raising the raisable ends (bisection between design and max heights)
    ma, mb = a["h_max"], b["h_max"]
    cf_max, cl_max, _ = clearance(pr, ma, mb, f_ghz)
    if cf_max >= 0:
        lo_t, hi_t = 0.0, 1.0
        for _ in range(20):
            t = (lo_t + hi_t) / 2
            if clearance(pr, ha + (ma - ha) * t, hb + (mb - hb) * t, f_ghz)[0] >= 0:
                hi_t = t
            else:
                lo_t = t
        ra, rb = ha + (ma - ha) * hi_t, hb + (mb - hb) * hi_t
        res.update(status="CLEAR WITH TALLER MASTS", h_a_m=math.ceil(ra), h_b_m=math.ceil(rb),
                   extra_height_m=round((ra - ha) + (rb - hb), 1),
                   reason=f"needs ~{math.ceil(ra)} m at {a['id']} and ~{math.ceil(rb)} m at {b['id']}")
        return res
    if cl_max >= 0:
        res.update(status="MARGINAL", reason=f"optical LOS only at max heights; Fresnel intruded by {abs(cf_max):.1f} m "
                   f"at {res['worst_at_km']} km", h_a_m=ma, h_b_m=mb)
        return res
    res.update(status="BLOCKED", reason=f"terrain blocks LOS by {abs(cl_max):.0f} m at ~{res['worst_at_km']} km "
               f"(ground {res['worst_ground_m']} m ASL) even at {ma} m / {mb} m masts")
    return res


# ============================================================ link engineering

def engineer(link, eq, required_mbps=None):
    d = link["distance_km"]
    for cls in eq["classes"]:
        if d > cls["max_km"]:
            continue
        loss = fspl_db(d, cls["freq_mhz"]) + cls.get("gaseous_loss_db_per_km", 0) * d
        rx = cls["tx_dbm"] + 2 * cls["gain_dbi"] - loss - 2.0
        margin = rx - cls["sensitivity_dbm"]
        if margin >= eq["min_fade_margin_db"]:
            eirp = cls["tx_dbm"] + cls["gain_dbi"]
            return {"class": cls["id"], "label": cls["label"], "family": cls["family"],
                    "freq_mhz": cls["freq_mhz"], "fspl_db": round(loss, 1), "rx_dbm": round(rx, 1),
                    "fade_margin_db": round(margin, 1), "eirp_dbm": round(eirp, 1),
                    "capacity_mbps": cls.get("capacity_mbps"),
                    "confidence": "PRELIMINARY" if cls.get("verified") else "INFERRED (planning class, not datasheet)"}
    return {"class": None, "label": "No planning class closes this link at ≥ "
            f"{eq['min_fade_margin_db']} dB margin — split the hop or use licensed microwave", "confidence": "INFERRED"}


# ============================================================ hop graph

class Planner:
    def __init__(self, nodes, src, eq, f_ghz=5.8, clutter_m=0.0, max_hop_km=40, max_hops=4, intel=None):
        self.nodes = {n["id"]: n for n in nodes}
        self.src, self.eq, self.f = src, eq, f_ghz
        self.clutter, self.max_hop, self.max_hops = clutter_m, max_hop_km, max_hops
        self.intel = intel
        self.memo = {}

    def edge(self, a, b):
        key = tuple(sorted((a, b)))
        if key not in self.memo:
            A, B = self.nodes[key[0]], self.nodes[key[1]]
            known = self.intel.rejected(key[0], key[1]) if self.intel else None
            if known:
                self.memo[key] = {"a": key[0], "b": key[1], "status": "BLOCKED",
                                  "reason": f"field-verified rejection ({known.get('date')}): {known.get('reason')}",
                                  "distance_km": round(haversine_km(A["lat"], A["lon"], B["lat"], B["lon"]), 2)}
            else:
                self.memo[key] = analyse_link(A, B, self.src, self.f, self.clutter)
        e = dict(self.memo[key])
        if e["a"] != a:  # orient
            e["a"], e["b"] = a, b
            e["bearing_ab"], e["bearing_ba"] = e.get("bearing_ba"), e.get("bearing_ab")
            e["h_a_m"], e["h_b_m"] = e.get("h_b_m"), e.get("h_a_m")
            e["ground_a_m"], e["ground_b_m"] = e.get("ground_b_m"), e.get("ground_a_m")
        return e

    @staticmethod
    def cost(e, node_b):
        if e["status"] in ("BLOCKED", "MARGINAL"):
            return None
        c = 10 + e["distance_km"]                       # hop penalty = minimum practical hops
        c += {"CLEAR": 0, "CLEAR WITH TALLER MASTS": 3 + e.get("extra_height_m", 0) / 3, "UNVERIFIED": 20}[e["status"]]
        if node_b["role"] == "relay":
            c += 8                                       # new site: permission, power, access
        return c

    def target_cost(self, n):
        c = TARGET_PENALTY[n["confidence"]]
        c -= 3 if n.get("vodacom") else 0
        c -= min(3, len(n.get("backhaul_evidence", [])))
        return c

    def best_path(self, start, targets, exclude=()):
        dist, prev = {start: (0.0, 0)}, {}
        pq = [(0.0, 0, start)]
        best = None
        while pq:
            c, hops, u = heapq.heappop(pq)
            if c > dist[u][0] or (best and c >= best[0]):
                continue
            if u in targets and u != start:
                tc = c + self.target_cost(self.nodes[u])
                if best is None or tc < best[0]:
                    best = (tc, u)
                # a carrier site can still relay onward, keep expanding
            if hops >= self.max_hops:
                continue
            for v, nv in self.nodes.items():
                if v == u or v in exclude or nv["role"] == "customer" and v not in targets:
                    continue
                if haversine_km(self.nodes[u]["lat"], self.nodes[u]["lon"], nv["lat"], nv["lon"]) > self.max_hop:
                    continue
                e = self.edge(u, v)
                w = self.cost(e, nv)
                if w is None:
                    continue
                if v not in dist or c + w < dist[v][0]:
                    dist[v] = (c + w, hops + 1)
                    prev[v] = u
                    heapq.heappush(pq, (c + w, hops + 1, v))
        if not best:
            return None
        path, u = [best[1]], best[1]
        while u != start:
            u = prev[u]
            path.append(u)
        path.reverse()
        return {"nodes": path, "cost": round(best[0], 1),
                "hops": [self.edge(x, y) for x, y in zip(path, path[1:])]}


def rejected_edges(planner):
    return [e for e in planner.memo.values() if e["status"] in ("BLOCKED", "MARGINAL")]
