#!/usr/bin/env python3
"""Point-to-point wireless link calculator for the /link-planner skill.

Usage:
    python3 .claude/skills/link-planner/linkcalc.py <project.json> [--json]

Reads a project file (see .claude/skills/link-planner/example-project.json), computes the
path geometry, Fresnel/earth-bulge clearance and link budget for every link,
and prints a markdown report (or JSON with --json).
"""
import json
import math
import sys

EARTH_R_KM = 6371.0
K_FACTOR = 4 / 3  # standard atmosphere
MIN_FADE_MARGIN_DB = 20.0  # CTTX design rule for >99.99% availability
FRESNEL_CLEAR = 0.6  # required fraction of first Fresnel zone


def haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_R_KM * math.asin(math.sqrt(h))


def bearing_deg(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def fspl_db(d_km, f_mhz):
    return 20 * math.log10(d_km) + 20 * math.log10(f_mhz) + 32.44


def fresnel_m(d1_km, d2_km, f_ghz):
    return 17.32 * math.sqrt(d1_km * d2_km / (f_ghz * (d1_km + d2_km)))


def earth_bulge_m(d1_km, d2_km):
    return d1_km * d2_km / (12.74 * K_FACTOR)


def check_point(d1, d_total, h_a, h_b, f_ghz, ground_or_obstacle_m):
    """Clearance (m) of the 0.6 F1 ellipse over an obstacle at d1 km from site A."""
    d2 = d_total - d1
    los = h_a + (h_b - h_a) * d1 / d_total
    need = ground_or_obstacle_m + earth_bulge_m(d1, d2) + FRESNEL_CLEAR * fresnel_m(d1, d2, f_ghz)
    return los - need


def plan_link(link, sites):
    a, b = sites[link["from"]], sites[link["to"]]
    radio = link["radio"]
    f_mhz = radio["freq_mhz"]
    f_ghz = f_mhz / 1000
    d = haversine_km(a, b)
    # antenna heights above sea level
    h_a = a.get("ground_m", 0) + link.get("from_height_m", a.get("mast_m", 0))
    h_b = b.get("ground_m", 0) + link.get("to_height_m", b.get("mast_m", 0))

    points = link.get("obstructions", [])
    worst = None
    for p in points:
        c = check_point(p["dist_km"], d, h_a, h_b, f_ghz, p["height_m"])
        if worst is None or c < worst["clearance_m"]:
            worst = {"dist_km": p["dist_km"], "label": p.get("label", ""), "clearance_m": round(c, 1)}
    # midpoint check against the lower site ground level when no profile given
    mid_ground = min(a.get("ground_m", 0), b.get("ground_m", 0))
    mid_c = check_point(d / 2, d, h_a, h_b, f_ghz, mid_ground)
    if worst is None or mid_c < worst["clearance_m"]:
        worst = {"dist_km": round(d / 2, 2), "label": "midpoint (flat ground assumed)", "clearance_m": round(mid_c, 1)}

    loss = fspl_db(d, f_mhz)
    misc = radio.get("misc_loss_db", 2.0)
    rx = radio["tx_dbm"] + radio["gain_a_dbi"] + radio["gain_b_dbi"] - loss - misc
    margin = rx - radio["sensitivity_dbm"]
    eirp = radio["tx_dbm"] + radio["gain_a_dbi"]

    issues = []
    if worst["clearance_m"] < 0:
        issues.append(f"Fresnel/LOS blocked by {abs(worst['clearance_m'])} m at {worst['dist_km']} km ({worst['label']}) — raise masts")
    if margin < MIN_FADE_MARGIN_DB:
        issues.append(f"Fade margin {margin:.1f} dB < {MIN_FADE_MARGIN_DB:.0f} dB — larger antennas or shorter hop")
    limit = radio.get("eirp_limit_dbm")
    if limit is not None and eirp > limit:
        issues.append(f"EIRP {eirp:.1f} dBm exceeds {limit} dBm ICASA limit — reduce Tx power")

    return {
        "name": link.get("name", f"{link['from']} → {link['to']}"),
        "from": link["from"],
        "to": link["to"],
        "distance_km": round(d, 2),
        "azimuth_a_deg": round(bearing_deg(a, b), 1),
        "azimuth_b_deg": round(bearing_deg(b, a), 1),
        "freq_mhz": f_mhz,
        "fspl_db": round(loss, 1),
        "fresnel_mid_m": round(fresnel_m(d / 2, d / 2, f_ghz), 1),
        "earth_bulge_mid_m": round(earth_bulge_m(d / 2, d / 2), 1),
        "worst_clearance": worst,
        "rx_dbm": round(rx, 1),
        "fade_margin_db": round(margin, 1),
        "eirp_dbm": round(eirp, 1),
        "status": "PASS" if not issues else "FAIL",
        "issues": issues,
    }


def report_md(project, results):
    out = [f"# Link Plan — {project.get('client', 'Client')} / {project.get('site', 'Site')}", ""]
    out.append("| Link | Dist (km) | Az A→B / B→A | Band | FSPL | Rx (dBm) | Margin (dB) | Worst clearance | Status |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        wc = r["worst_clearance"]
        out.append(
            f"| {r['name']} | {r['distance_km']} | {r['azimuth_a_deg']}° / {r['azimuth_b_deg']}° | "
            f"{r['freq_mhz']} MHz | {r['fspl_db']} dB | {r['rx_dbm']} | {r['fade_margin_db']} | "
            f"{wc['clearance_m']} m @ {wc['dist_km']} km | {'✅' if r['status'] == 'PASS' else '❌'} {r['status']} |"
        )
    failing = [r for r in results if r["issues"]]
    if failing:
        out += ["", "## Issues"]
        for r in failing:
            for i in r["issues"]:
                out.append(f"- **{r['name']}** — {i}")
    out += ["", f"_Design rules: {FRESNEL_CLEAR:.0%} F1 clearance, k={K_FACTOR:.2f}, fade margin ≥ {MIN_FADE_MARGIN_DB:.0f} dB._"]
    return "\n".join(out)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    with open(sys.argv[1]) as f:
        project = json.load(f)
    sites = project["sites"]
    results = [plan_link(l, sites) for l in project["links"]]
    if "--json" in sys.argv:
        print(json.dumps({"project": project.get("site"), "links": results}, indent=2, ensure_ascii=False))
    else:
        print(report_md(project, results))


if __name__ == "__main__":
    main()
