"""Cambium LINKPlanner (.lpp) importer and independent design review.

A .lpp file is a bzip2-compressed SQLite database. We read sites, hubs/APs, subscribers,
equipment, LINKPlanner's own per-link verdicts and its terrain+clutter profiles, then re-check
every path independently (k=4/3, 60 % F1) with the clutter as modelled and with a lighter
clutter scenario. Nothing is invented: LINKPlanner values are SOURCE-DERIVED, our checks are
CALCULATED, alternative clutter is an ASSUMED scenario.
"""
import bz2
import collections
import json
import os
import sqlite3
import tempfile

from geo import bearing_deg, earth_bulge_m, fresnel_m, haversine_km

ALT_CLUTTER_M = 5.0  # "Light Trees - Shrubs" scenario (ASSUMED) for sensitivity


def _num(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def load(path):
    raw = open(path, "rb").read()
    if raw[:3] == b"BZh":
        raw = bz2.decompress(raw)
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.write(raw)
    tmp.close()
    con = sqlite3.connect(tmp.name)
    con.row_factory = sqlite3.Row
    try:
        return _parse(con, os.path.basename(path))
    finally:
        con.close()
        os.unlink(tmp.name)


def _parse(c, fname):
    meta = json.loads(c.execute("select metadata from project").fetchone()[0] or "{}")
    pattrs = json.loads(c.execute("select attrs from project").fetchone()[0] or "{}")
    clutter = json.loads(c.execute("select clutter_dict from project").fetchone()[0] or "{}")
    places = {int(r["id"]): json.loads(r["attrs"]) for r in c.execute("select * from places")}
    subplaces = {int(r["id"]): json.loads(r["attrs"]) for r in c.execute("select * from subscriber_places")}
    hubs = {int(r["id"]): int(r["place_id"]) for r in c.execute("select * from hubs")
            if r["id"] not in (None, "None") and r["place_id"] not in (None, "None")}
    aps = {}
    for r in c.execute("select * from access_points"):
        a, e = json.loads(r["attrs"]), json.loads(r["equipment"])
        hp = places[hubs[int(r["hub_id"])]]
        aps[int(r["id"])] = {"site": hp["name"], "lat": _num(hp["latitude"]), "lon": _num(hp["longitude"]),
                             "height_m": _num(a.get("antenna_height")), "azimuth": _num(a.get("antenna_azimuth")),
                             "tilt": _num(a.get("tilt")), "beamwidth": _num(a.get("modelled_beamwidth")),
                             "product": e.get("product"), "band": e.get("band"), "bandwidth_mhz": e.get("bandwidth"),
                             "max_mod": e.get("pmp_max_mod_mode"), "sm_range_km": _num(e.get("sm_range")),
                             "regulation": e.get("regulation")}
    profiles = [dict(r) for r in c.execute("select * from profiles")]

    def prof(A, B):
        for p in profiles:
            if (abs(p["from_lat"] - A[0]) < 1e-5 and abs(p["from_long"] - A[1]) < 1e-5
                    and abs(p["to_lat"] - B[0]) < 1e-5 and abs(p["to_long"] - B[1]) < 1e-5):
                return p

    links = []
    for r in c.execute("select * from subscribers"):
        s = subplaces[int(r["place_id"])]
        ap = aps[int(r["access_point_id"])]
        eq, pl, at = json.loads(r["equipment"]), json.loads(r["pmp_link"] or "{}"), json.loads(r["attrs"])
        A, B = (ap["lat"], ap["lon"]), (_num(s["latitude"]), _num(s["longitude"]))
        errs = json.loads(pl.get("error_messages") or "{}")
        link = {"sm": s["name"], "sm_lat": B[0], "sm_lon": B[1], "ap_site": ap["site"], "sm_product": eq.get("product"),
                "sm_height_m": _num(at.get("antenna_height")), "ap_height_m": ap["height_m"],
                "distance_m": round(haversine_km(*A, *B) * 1000),
                "bearing_from_ap": round(bearing_deg(*A, *B)),
                "off_boresight_deg": round(((bearing_deg(*A, *B) - (ap["azimuth"] or 0) + 540) % 360) - 180),
                "lp_link_ok": pl.get("link_ok") == "true",
                "lp_errors": sorted(set(errs.get("local", []) + errs.get("remote", []))),
                "lp_ap_gain_dbi": _num(at.get("ap_antenna_gain")),
                "lp_elev_to_sm_deg": _num(at.get("ap_tilt")),
                "required_availability": pl.get("minimum_availability_required_sm")}
        p = prof(A, B)
        if p:
            link.update(_clearance(p, clutter, ap["height_m"] or 0, link["sm_height_m"] or 0))
        links.append(link)
    return {"file": fname, "app_version": meta.get("app_version"), "created": meta.get("description"),
            "model": pattrs.get("model"), "use_clutter": pattrs.get("use_clutter") == "1",
            "clutter_dict": clutter, "sites": [{"name": p["name"], "lat": _num(p["latitude"]), "lon": _num(p["longitude"]),
                                                "max_height_m": _num(p.get("maximum_height")), "kind": "network site"}
                                               for p in places.values()],
            "subscriber_sites": [{"name": p["name"], "lat": _num(p["latitude"]), "lon": _num(p["longitude"])}
                                 for p in subplaces.values()],
            "access_points": list(aps.values()), "links": links}


def _clearance(p, clutter, h_ap, h_sm, f_ghz=5.8):
    rg = [float(x) for x in p["ranges"].split(",")]
    hg = [float(x) for x in p["heights"].split(",")]
    codes = (json.loads(p["attrs"] or "{}").get("file_clutter") or "")
    cl = [clutter.get(ch, ["?", 0])[1] for ch in codes] + [0] * len(rg)
    D = rg[-1] / 1000
    top_a, top_b = hg[0] + h_ap, hg[-1] + h_sm
    res = {}
    for label, ch in (("modelled", None), ("light", ALT_CLUTTER_M)):
        worst = (1e9, None)
        for i in range(1, len(rg) - 1):
            d1 = rg[i] / 1000
            d2 = D - d1
            los = top_a + (top_b - top_a) * d1 / D
            c = cl[i] if ch is None else (min(cl[i], ch) if cl[i] else 0)
            v = los - (hg[i] + c + earth_bulge_m(d1, d2) + 0.6 * fresnel_m(d1, d2, f_ghz))
            if v < worst[0]:
                worst = (v, d1)
        res[f"clr_{label}_m"] = round(worst[0], 1)
        res[f"clr_{label}_at_m"] = round(worst[1] * 1000) if worst[1] is not None else None
    res.update(ground_ap_m=round(hg[0]), ground_sm_m=round(hg[-1]),
               clutter_classes="".join(sorted(set(codes))),
               clutter_height_m=max(cl[:len(codes)]) if codes else 0)
    return res


def review(net):
    """Findings about the imported design, each with an evidence status."""
    L = net["links"]
    f = []
    ok = sum(x["lp_link_ok"] for x in L)
    f.append({"finding": f"LINKPlanner verdict: {ok}/{len(L)} subscriber links meet their targets",
              "status": "SOURCE-DERIVED", "source": f"{net['file']} (LINKPlanner {net['app_version']}, {net['model']})"})
    errs = collections.Counter(e for x in L for e in x["lp_errors"])
    if errs:
        f.append({"finding": "LINKPlanner error flags: " + ", ".join(f"{k} ×{v}" for k, v in errs.most_common()),
                  "status": "SOURCE-DERIVED", "source": net["file"]})
    classes = collections.Counter(x.get("clutter_classes", "") for x in L)
    if net["use_clutter"] and classes:
        top, n = classes.most_common(1)[0]
        name = net["clutter_dict"].get(top[:1], ["?", "?"])
        f.append({"finding": f"Clutter class '{top}' ({name[0]}, {name[1]} m) is applied along {n}/{len(L)} paths, including at the "
                             f"subscriber ends, while subscriber antennas are {'/'.join(f'{h:g}' for h in sorted({x['sm_height_m'] for x in L}))} m high",
                  "status": "SOURCE-DERIVED", "source": net["file"] + " profile clutter"})
        blocked_mod = sum((x.get("clr_modelled_m") or 0) < 0 for x in L)
        clear_light = sum((x.get("clr_light_m") or 0) >= 0 for x in L)
        f.append({"finding": f"Independent check with modelled clutter: {blocked_mod}/{len(L)} paths intrude the 60 % Fresnel zone; "
                             f"with {ALT_CLUTTER_M:.0f} m shrub clutter {clear_light}/{len(L)} clear",
                  "status": "CALCULATED", "source": "LINKPlanner terrain profiles, k=4/3, 60 % F1 (light-clutter case ASSUMED)"})
    for ap in net["access_points"]:
        all_subs = [x for x in L if x["ap_site"] == ap["site"]]
        subs = [x for x in all_subs if x["lp_ap_gain_dbi"] is not None]
        edge = [x for x in all_subs if abs(x["off_boresight_deg"]) > (ap["beamwidth"] or 120) / 2 - 10]
        if edge:
            f.append({"finding": f"{len(edge)} subscribers of AP '{ap['site']}' are {min(abs(x['off_boresight_deg']) for x in edge)}–"
                                 f"{max(abs(x['off_boresight_deg']) for x in edge)}° off boresight (sector edge or outside, azimuth "
                                 f"{ap['azimuth']:.0f}°, {ap['beamwidth']:.0f}° sector): " + ", ".join(sorted({x['sm'] for x in edge}))[:160],
                      "status": "CALCULATED", "source": "site coordinates vs AP azimuth/beamwidth"})
        if not subs:
            continue
        steep = [x for x in subs if (x["lp_elev_to_sm_deg"] or 0) <= -5]
        if steep and (ap["tilt"] or 0) == 0:
            g_steep = [x["lp_ap_gain_dbi"] for x in steep]
            g_best = max(x["lp_ap_gain_dbi"] for x in subs)
            f.append({"finding": f"AP '{ap['site']}' ({ap['product']}, {ap['height_m']} m) has 0° tilt but {len(steep)} subscribers sit "
                                 f"{min(x['lp_elev_to_sm_deg'] for x in steep):.0f}° to {max(x['lp_elev_to_sm_deg'] for x in steep):.0f}° below it; "
                                 f"LINKPlanner gives them {min(g_steep):.1f}–{max(g_steep):.1f} dBi vs {g_best:.1f} dBi near boresight "
                                 f"(≈{g_best - max(g_steep):.0f}–{g_best - min(g_steep):.0f} dB lost to elevation mis-pointing)",
                      "status": "SOURCE-DERIVED", "source": net["file"] + " per-subscriber AP gain"})
    near = [x for x in L if x["distance_m"] < 250]
    if near:
        f.append({"finding": f"{len(near)} subscribers are only {min(x['distance_m'] for x in near)}–{max(x['distance_m'] for x in near)} m from "
                             f"their AP ({', '.join(sorted({x['ap_site'] for x in near}))}); LINKPlanner flags "
                             f"{sum('Outside of range' in x['lp_errors'] or 'Receive level' in x['lp_errors'] for x in near)} with "
                             "'Receive level'/'Outside of range'. PMP is a poor fit at this distance — cable, 60 GHz or Wi-Fi is usually better",
                  "status": "INFERRED", "source": net["file"] + " distances + error flags"})
    return f


def to_features(net):
    """Sites become property features. Proposed network sites are NOT backhaul targets."""
    return ([{"name": s["name"], "kind": "proposed network site (LINKPlanner)", "lat": s["lat"], "lon": s["lon"]}
             for s in net["sites"]]
            + [{"name": s["name"], "kind": "subscriber site (LINKPlanner)", "lat": s["lat"], "lon": s["lon"]}
               for s in net["subscriber_sites"]])
