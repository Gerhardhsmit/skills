#!/usr/bin/env python3
"""One-command site workup: pins in -> link plan, carrier handover, satellite views, brief pages out.

    python3 site_workup.py sites.json <out_dir> [--no-imagery] [--carrier-km 25]

sites.json = {"<name>": {"lat": .., "lon": .., "role": "hub|site|dairy|lodge|office|pump", "status": "published|ESTIMATED"}}
(the hub is where the carrier should land / operations are run; at least one site has role "hub")

Steps (each one written to <out_dir> so a person can check it):
 1. screen.txt   every site pair at 12 m; blocked pairs retried at 18 and 24 m
 2. relays       any site with no CLEAR hop -> relay search on high ground; best relay added
 3. backbone     minimum spanning tree over CLEAR hops (shortest total km), from the hub outwards
 4. carrier.json known carrier points (CTTX mast dataset, Vodacom-sourced, HISTORICAL) screened from
                 every node; best CLEAR point with >= 20 dB fade (2 ft dish) becomes the carrier option,
                 the next diverse one the backup. INTERNAL: carrier names/IDs never go to the client.
 5. plan.json, plan_out/links.kml, plan.html (map, hop table, profiles for the brief)
 6. sat.png + sat_<relay>_zoom.png  Sentinel-2 views for tracks, paddocks, dams, power to each relay
The hill that blocks the valley is usually the opportunity: one relay serves the blocked site AND sees
the carrier mast. The workup looks for exactly that.
"""
import argparse, glob, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain_screen as ts  # noqa: E402

HEIGHTS = (12, 18, 24)
RELAY_H = 15
DISH = {"gain_dbi": 29}
MAST_KM_PER_M = 0.15   # planning weight: each metre of mast above 12 m "costs" like 150 m of hop


def _dump(obj, path):
    with open(path, "w") as f:
        json.dump(obj, f, indent=1)


def mast_index():
    env = os.environ.get("CTTX_MAST_INDEX")
    cands = [env] if env else []
    cands += glob.glob(os.path.expanduser("~/.claude/skills/**/cttx-link-assessment-architect/data/private/masts/mast_index.json"), recursive=True)
    for c in cands:
        if c and os.path.exists(c):
            return json.load(open(c))["sites"]
    return []


def best_hop(a, b, ha_opts, hb_opts):
    """Lowest heights that make a->b CLEAR with >= 20 dB fade. Returns (ha, hb, result, radio) or None."""
    for h in sorted({(x, y) for x in ha_opts for y in hb_opts}, key=lambda t: t[0] + t[1]):
        r = ts.screen(a, b, h[0], h[1], n=120)
        if r["verdict"] != "CLEAR":
            continue
        for radio in ({}, DISH):
            if ts.budget(r["km"], {**ts.PLAN_CLASS, **radio})["fade_db"] >= ts.MIN_FADE_DB:
                return h[0], h[1], r, radio
    return None


def workup(sites, out, imagery=True, carrier_km=25, max_hop_km=15):
    os.makedirs(out, exist_ok=True)
    log = open(os.path.join(out, "screen.txt"), "w")
    P = {n: (s["lat"], s["lon"]) for n, s in sites.items()}
    hub = next((n for n, s in sites.items() if s.get("role") == "hub"), next(iter(sites)))
    nodes = {n: {**s, "h": 12} for n, s in sites.items()}
    hops = {}  # (a,b) -> (ha, hb, km, radio)

    def try_pair(a, b, ha_opts=HEIGHTS, hb_opts=HEIGHTS):
        if ts.km(P[a], P[b]) > max_hop_km:
            return
        got = best_hop(P[a], P[b], ha_opts, hb_opts)
        log.write(f"{a:18s} {b:18s} {ts.km(P[a], P[b]):5.2f} km  " +
                  (f"CLEAR at {got[0]}/{got[1]} m{' (2 ft dish)' if got[3] else ''}\n" if got else "BLOCKED at 12-24 m\n"))
        if got:
            hops[(a, b)] = (got[0], got[1], got[2]["km"], got[3])

    names = list(sites)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            try_pair(a, b)

    # 2. relays for sites that cannot reach the hub's component
    def component(start):
        seen, stack = {start}, [start]
        while stack:
            x = stack.pop()
            for (a, b) in hops:
                for y in ((b,) if a == x else (a,) if b == x else ()):
                    if y not in seen:
                        seen.add(y); stack.append(y)
        return seen

    # A site that only connects with tall masts (or not at all) gets a relay search too: the hill that
    # blocks it is usually cheaper than two 24 m masts, and often sees the carrier mast as well.
    def low_ok(n, comp):  # n has a hop into the hub network with no more than 12 m at n's end
        for (a, b), v in hops.items():
            if a == n and b in comp and v[0] <= 12 and (b in nodes and nodes[b].get("role") == "relay" or v[1] <= 12):
                return True
            if b == n and a in comp and v[1] <= 12 and (a in nodes and nodes[a].get("role") == "relay" or v[0] <= 12):
                return True
        return False

    masts = mast_index()
    relay_n = 0
    for n in names:
        comp = component(hub)
        if n in comp and (low_ok(n, comp - {n}) or n == hub and any(low_ok(m, {n}) for m in comp - {n})):
            continue
        # an existing relay may already serve this site
        reuse = [r for r in nodes if nodes[r].get("role") == "relay"]
        for r in reuse:
            try_pair(r, n, (RELAY_H, 24), HEIGHTS)
        if n in component(hub) and low_ok(n, component(hub) - {n}):
            continue
        targets = {t: P[t] for t in names if t != n}
        cands = ts.relay_search(P[n], targets, h_relay=RELAY_H, h_site=12)
        log.write(f"\n{n}: {'only tall-mast hops' if n in comp else 'no CLEAR hop'} -> relay search: {len(cands)} candidates\n")
        if not cands:
            log.write(f"{n}: NO RELAY FOUND within 5 km — field study / taller mast needed\n")
            continue
        relay_n += 1
        rname = f"Relay {relay_n}"
        c = cands[0]
        # prefer a crest that also sees a carrier point: one site does relay AND handover
        for cand in cands[:40]:
            rp = tuple(cand["relay"])
            near = [m for m in masts if ts.km(rp, (m["lat"], m["lon"])) <= 10]
            hit = next((m for m in sorted(near, key=lambda m: ts.km(rp, (m["lat"], m["lon"])))
                        if best_hop(rp, (m["lat"], m["lon"]), (RELAY_H,), (30,))), None)
            if hit:
                c = cand
                log.write(f"{rname}: chose candidate that also sees carrier point {hit['id']} "
                          f"({ts.km(rp, (hit['lat'], hit['lon'])):.1f} km) at {RELAY_H} m\n")
                break
        P[rname] = tuple(c["relay"])
        nodes[rname] = {"lat": c["relay"][0], "lon": c["relay"][1], "role": "relay",
                        "status": "candidate - field verify", "h": RELAY_H}
        log.write(f"{rname} at {c['relay']} (ground {c['ground_m']} m) sees {n} and {list(c['sees'])}\n")
        try_pair(rname, n, (RELAY_H, 24), HEIGHTS)
        for t in c["sees"]:
            try_pair(rname, t, (RELAY_H, 24), HEIGHTS)

    # 3. minimum spanning tree over CLEAR hops (Kruskal)
    parent = {n: n for n in P}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    tree = []
    cost = lambda v: v[2] + MAST_KM_PER_M * (max(v[0] - 12, 0) + max(v[1] - 12, 0)) + (0.5 if v[3] else 0)
    for (a, b), v in sorted(hops.items(), key=lambda kv: cost(kv[1])):
        if find(a) != find(b):
            parent[find(a)] = find(b); tree.append((a, b, v))
    for a, b, v in tree:  # set node mast heights to what the chosen hops need
        nodes[a]["h"] = max(nodes[a]["h"], v[0]); nodes[b]["h"] = max(nodes[b]["h"], v[1])
    unreached = [n for n in sites if find(n) != find(hub)]

    # 4. carrier handover: screen known points from every node
    car = []
    for m in masts:
        mp = (m["lat"], m["lon"])
        for n in nodes:
            d = ts.km(P[n], mp)
            if d > carrier_km or d < 0.05:
                continue
            got = best_hop(P[n], mp, (nodes[n]["h"], 24, 30), (30,))
            if got:
                car.append({"node": n, "point": m["id"], "name": m["name"], "level": m.get("service_level"),
                            "km": got[2]["km"], "node_h": got[0], "f1": got[2]["f1_ratio"],
                            "dish": bool(got[3]), "lat": m["lat"], "lon": m["lon"]})
    car.sort(key=lambda c: (c["km"] + (0 if c["node"] == hub else 1.0)))
    best = car[0] if car else None
    backup = next((c for c in car if best and c["point"] != best["point"] and c["node"] != best["node"]), None) \
        or next((c for c in car if best and c["point"] != best["point"]), None)
    _dump({"note": "INTERNAL. Vodacom-sourced historical dataset; never name carrier or site ID to the client.",
               "primary": best, "backup": backup, "all_clear": car[:20]}, os.path.join(out, "carrier.json"))

    # 5. plan + brief pages
    plan = {"sites": {n: {k: v for k, v in s.items()} for n, s in nodes.items()}, "links": []}
    for tag, c in (("Carrier point A", best), ("Carrier point B", backup)):
        if c:
            plan["sites"][tag] = {"lat": c["lat"], "lon": c["lon"], "h": 30, "role": "carrier", "status": "historical dataset"}
            nodes[c["node"]]["h"] = max(nodes[c["node"]]["h"], c["node_h"])
            plan["links"].append({"a": tag, "b": c["node"], "role": "carrier option" if tag.endswith("A") else "carrier backup",
                                  **({"radio": DISH} if c["dish"] else {})})
    for a, b, v in tree:
        plan["links"].append({"a": a, "b": b, "role": "backbone", **({"radio": DISH} if v[3] else {})})
    for n in plan["sites"]:
        if n in nodes:
            plan["sites"][n]["h"] = nodes[n]["h"]
    _dump(plan, os.path.join(out, "plan.json"))
    rows, H = ts.plan_files(plan, os.path.join(out, "plan_out"))
    prof = "".join(f'<div class="pcard"><div class="ph">{r["a"]} – {r["b"]} · {r["km"]} km</div>{s}</div>'
                   for r, s in zip(rows, H["profiles"]))
    with open(os.path.join(out, "plan.html"), "w") as f:
        f.write(
        '<style>svg .bg{fill:#101317} svg .gnd{fill:#3b3324} svg .txt{fill:#c9ced4} svg .ink{stroke:#c9ced4}'
        '.map,.prof{width:100%;display:block}.pgrid{display:grid;grid-template-columns:1fr 1fr;gap:8px}</style>'
        f'{H["map"]}<table class="lp"><tr><th>Hop</th><th>Role</th><th>km</th><th>Azimuth</th><th>Mast</th>'
        f'<th>Fresnel</th><th>Fade margin</th><th>Screen</th></tr>{H["table"]}</table><div class="pgrid">{prof}</div>')

    # 6. imagery
    imgs = []
    if imagery:
        try:
            import site_imagery as si
            pts = {n: {"lat": s["lat"], "lon": s["lon"], "kind": s.get("role")} for n, s in plan["sites"].items()}
            lk = [{"a": l["a"], "b": l["b"], "role": l["role"]} for l in plan["links"]]
            sc = si.render(pts, lk, os.path.join(out, "sat.png"))
            imgs.append(f"sat.png (Sentinel-2 {sc['date']}, cloud {sc['cloud']}%)")
            for n, s in plan["sites"].items():
                if s.get("role") == "relay":
                    z = os.path.join(out, f"sat_{n.replace(' ', '_')}_zoom.png")
                    si.crop(pts, n, z); imgs.append(os.path.basename(z))
        except Exception as e:  # imagery is a check, not a blocker
            imgs.append(f"IMAGERY FAILED: {e}")
    log.close()
    summary = {"hub": hub, "relays": [n for n, s in nodes.items() if s.get("role") == "relay"],
               "backbone": [(a, b, v[2]) for a, b, v in tree], "unreached": unreached,
               "carrier_primary": best and {k: best[k] for k in ("node", "km", "level")},
               "carrier_backup": backup and {k: backup[k] for k in ("node", "km", "level")},
               "all_hops_pass": all(r["pass"] for r in rows), "imagery": imgs,
               "carrier_dataset": f"{len(masts)} points" if masts else "NOT FOUND - carrier screen not run (needs cttx-link-assessment-architect private data)"}
    _dump(summary, os.path.join(out, "summary.json"))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sites"); ap.add_argument("out")
    ap.add_argument("--no-imagery", action="store_true")
    ap.add_argument("--carrier-km", type=float, default=25)
    o = ap.parse_args()
    print(json.dumps(workup(json.load(open(o.sites)), o.out, not o.no_imagery, o.carrier_km), indent=1))


if __name__ == "__main__":
    sys.exit(main())
