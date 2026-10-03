#!/usr/bin/env python3
"""Desk-study terrain screen: path profile, earth bulge and Fresnel clearance between sites.

Elevation: AWS Terrain Tiles (terrarium PNG, SRTM-derived, ~15 m pixels at zoom 13), which the cloud
egress proxy allows when opentopodata/open-meteo are blocked. Stdlib only (PNG decoded with zlib).

This is a SCREEN, not a design: bare-earth model, no trees/buildings, heights assumed. Result labels:
CLEAR (>= 0.6 F1), MARGINAL (0-0.6 F1), BLOCKED (< 0). Customer text may say "terrain screen suggests";
never "line of sight confirmed" — that needs LINKPlanner and a field check.

CLI:  python3 terrain_screen.py sites.json [--freq 5.8] [--max-km 15] [--relay <site> --to <a>,<b>]
      python3 terrain_screen.py plan.json --plan <out_dir>   (link plan for the proposal: hops, KML)
sites.json = {"<name>": [lat, lon, height_m], ...}
"""
import argparse, itertools, json, math, os, struct, sys, urllib.request, zlib

Z = 13
CACHE = os.environ.get("CTTX_TILE_CACHE", os.path.join(os.path.expanduser("~"), ".cache", "cttx-terrain"))
URL = "https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png"
_tiles = {}


def _decode_png(data):
    """Return rows of RGB(A) bytes for an 8-bit non-interlaced PNG."""
    pos, idat, w = 8, b"", 0
    while pos < len(data):
        n, typ = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + n]
        if typ == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", chunk[:10])
            bpp = {2: 3, 6: 4}[ctype]
        elif typ == b"IDAT":
            idat += chunk
        pos += 12 + n
    raw, stride, rows, prev = zlib.decompress(idat), w * bpp, [], bytearray(w * bpp)
    for r in range(h):
        f, line = raw[r * (stride + 1)], bytearray(raw[r * (stride + 1) + 1:(r + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b, c = prev[i], prev[i - bpp] if i >= bpp else 0
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append((line, bpp)); prev = line
    return rows


def _tile(x, y):
    if (x, y) not in _tiles:
        os.makedirs(CACHE, exist_ok=True)
        path = os.path.join(CACHE, f"{Z}_{x}_{y}.png")
        if not os.path.exists(path):
            with urllib.request.urlopen(URL.format(z=Z, x=x, y=y), timeout=30) as r, open(path, "wb") as f:
                f.write(r.read())
        with open(path, "rb") as f:
            _tiles[(x, y)] = _decode_png(f.read())
    return _tiles[(x, y)]


def _px(tx, ty, ix, iy):
    tx, ix = tx + ix // 256, ix % 256
    ty, iy = ty + iy // 256, iy % 256
    line, bpp = _tile(tx, ty)[iy]
    r, g, b = line[ix * bpp:ix * bpp + 3]
    return r * 256 + g + b / 256 - 32768


def elev(lat, lon):
    n = 2 ** Z
    xf = (lon + 180) / 360 * n
    yf = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    tx, ty = int(xf), int(yf)
    px, py = (xf - tx) * 256, (yf - ty) * 256
    i, j = int(px), int(py)
    fx, fy = px - i, py - j
    return (_px(tx, ty, i, j) * (1 - fx) * (1 - fy) + _px(tx, ty, i + 1, j) * fx * (1 - fy)
            + _px(tx, ty, i, j + 1) * (1 - fx) * fy + _px(tx, ty, i + 1, j + 1) * fx * fy)


def km(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def verdict(ratio):
    return "CLEAR" if ratio >= 0.6 else "MARGINAL" if ratio >= 0 else "BLOCKED"


def screen(a, b, ha, hb, freq_ghz=5.8, k=4 / 3, n=200, elev_fn=None):
    """Worst Fresnel-ratio point on the path a->b. ha/hb are antenna heights above ground (m)."""
    elev_fn = elev_fn or (lambda la, lo: elev(la, lo))
    d = km(a, b)
    if d == 0:
        raise ValueError("identical points")
    ea, eb, lam = elev_fn(*a), elev_fn(*b), 0.3 / freq_ghz
    worst, prof = None, [(0.0, ea)]
    for i in range(1, n):
        t = i / n
        d1, d2 = d * t, d * (1 - t)
        g = elev_fn(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        bulge = d1 * d2 / (12.74 * k)                     # metres, d in km
        los = ea + ha + (eb + hb - ea - ha) * t
        f1 = math.sqrt(lam * d1 * d2 * 1000 / d)          # metres
        clear = los - g - bulge
        prof.append((d1, g + bulge))
        if worst is None or clear / f1 < worst["f1_ratio"]:
            worst = {"f1_ratio": round(clear / f1, 2), "at_km": round(d1, 2), "ground_m": round(g), "clear_m": round(clear, 1)}
    prof.append((d, eb))
    return {"km": round(d, 2), "ground_a": round(ea), "ground_b": round(eb), **worst,
            "verdict": verdict(worst["f1_ratio"]), "profile": prof}


def relay_search(anchor, targets, h_relay=15, h_site=12, radius_km=5, step=0.0015, freq_ghz=5.8):
    """Grid-search high ground that clears to `anchor` AND at least one target. Shortest total first."""
    out = []
    span = int(radius_km / 0.167)
    for i in range(-span, span + 1):
        for j in range(-span, span + 1):
            p = (anchor[0] + i * step, anchor[1] + j * step * 1.2)
            if (i, j) == (0, 0) or km(p, anchor) > radius_km:
                continue
            a = screen(p, anchor, h_relay, h_site, freq_ghz, n=80)
            if a["verdict"] != "CLEAR":
                continue
            hits = {name: screen(p, t, h_relay, h_site, freq_ghz, n=80) for name, t in targets.items()}
            ok = {nm: r for nm, r in hits.items() if r["verdict"] == "CLEAR"}
            if ok:
                out.append({"relay": [round(p[0], 5), round(p[1], 5)], "ground_m": round(elev(*p)),
                            "to_anchor_km": a["km"], "sees": {nm: [r["km"], r["f1_ratio"]] for nm, r in ok.items()}})
    out.sort(key=lambda r: (-len(r["sees"]), r["to_anchor_km"] + min(v[0] for v in r["sees"].values())))
    return out


# --- Link plan (large sites: goes into the first proposal) -------------------------------------------
# Planning class: 5 GHz carrier-grade PtP, integrated ~25 dBi (CTTX desk default, NOT a datasheet value).
PLAN_CLASS = {"label": "5 GHz carrier-grade PtP, ~25 dBi integrated (planning class)",
              "freq_mhz": 5800, "tx_dbm": 20, "gain_dbi": 25, "sens_dbm": -75, "misc_db": 2}
MIN_FADE_DB = 20


def bearing(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    x = math.sin(lo2 - lo1) * math.cos(la2)
    y = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(lo2 - lo1)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def budget(d_km, c=PLAN_CLASS):
    fspl = 20 * math.log10(d_km) + 20 * math.log10(c["freq_mhz"]) + 32.44
    rx = c["tx_dbm"] + 2 * c["gain_dbi"] - fspl - c["misc_db"]
    return {"fspl_db": round(fspl, 1), "rx_dbm": round(rx, 1), "fade_db": round(rx - c["sens_dbm"], 1)}


def plan(p):
    """p = {"sites": {name: {"lat","lon","h","role","status"}}, "links": [{"a","b","role"}]}"""
    rows = []
    for ln in p["links"]:
        A, B = p["sites"][ln["a"]], p["sites"][ln["b"]]
        c = {**PLAN_CLASS, **ln.get("radio", {})}   # per-hop override, e.g. {"gain_dbi": 29} for a 2 ft dish
        r = screen((A["lat"], A["lon"]), (B["lat"], B["lon"]), A["h"], B["h"], c["freq_mhz"] / 1000)
        bud = budget(r["km"], c)
        rows.append({**ln, **r, **bud, "gain_dbi": c["gain_dbi"], "lat_far": B["lat"] if B.get("role") == "carrier" else A["lat"],
                     "lon_far": B["lon"] if B.get("role") == "carrier" else A["lon"], "az_a": round(bearing((A["lat"], A["lon"]), (B["lat"], B["lon"]))),
                     "az_b": round(bearing((B["lat"], B["lon"]), (A["lat"], A["lon"]))),
                     "pass": r["verdict"] == "CLEAR" and bud["fade_db"] >= MIN_FADE_DB})
    return rows


def profile_svg(row, w=520, h=150):
    pr = row["profile"]; d = pr[-1][0]
    ea, eb = pr[0][1] + row["h_a"], pr[-1][1] + row["h_b"]
    lo = min(z for _, z in pr) - 10; hi = max(max(z for _, z in pr), ea, eb) + 15
    X = lambda x: 30 + x / d * (w - 40); Y = lambda z: h - 18 - (z - lo) / (hi - lo) * (h - 30)
    ground = " ".join(f"{X(x):.1f},{Y(z):.1f}" for x, z in pr)
    col = {"CLEAR": "#1f8a4c", "MARGINAL": "#c98a00", "BLOCKED": "#c0392b"}[row["verdict"]]
    return (f'<svg viewBox="0 0 {w} {h}" class="prof"><polygon points="{X(0):.1f},{h-18} {ground} {X(d):.1f},{h-18}" fill="#d9cbb0" class="gnd"/>'
            f'<line x1="{X(0):.1f}" y1="{Y(pr[0][1]):.1f}" x2="{X(0):.1f}" y2="{Y(ea):.1f}" stroke="#333" stroke-width="2" class="ink"/>'
            f'<line x1="{X(d):.1f}" y1="{Y(pr[-1][1]):.1f}" x2="{X(d):.1f}" y2="{Y(eb):.1f}" stroke="#333" stroke-width="2" class="ink"/>'
            f'<line x1="{X(0):.1f}" y1="{Y(ea):.1f}" x2="{X(d):.1f}" y2="{Y(eb):.1f}" stroke="{col}" stroke-width="2"/>'
            f'<text class="txt" x="30" y="11" font-size="10">{row["a"]} ({row["h_a"]} m)</text>'
            f'<text class="txt" x="{w-10}" y="11" font-size="10" text-anchor="end">{row["b"]} ({row["h_b"]} m)</text>'
            f'<text class="txt" x="{w/2}" y="{h-4}" font-size="9" text-anchor="middle">{row["km"]} km · ground {round(lo+10)}–{round(hi-15)} m ASL</text></svg>')


def map_svg(p, rows, w=520, h=340):
    # a far-off backup carrier point would shrink the hub to a dot: list it in a corner note instead
    far = {r["a"] if p["sites"][r["a"]].get("role") == "carrier" else r["b"]: r for r in rows if r.get("role") == "carrier backup"}
    p = {"sites": {n: s for n, s in p["sites"].items() if n not in far}}
    notes = [f'{n}: {r["km"]} km {compass(bearing((p["sites"][r["b"] if r["a"] == n else r["a"]]["lat"], p["sites"][r["b"] if r["a"] == n else r["a"]]["lon"]), (r_site["lat"], r_site["lon"])))} of {r["b"] if r["a"] == n else r["a"]}'
             for n, r in far.items() for r_site in [{"lat": r["lat_far"], "lon": r["lon_far"]}]]
    rows = [r for r in rows if r.get("role") != "carrier backup"]
    pts = [(s["lat"], s["lon"]) for s in p["sites"].values()]
    la0, la1 = min(x for x, _ in pts), max(x for x, _ in pts); lo0, lo1 = min(y for _, y in pts), max(y for _, y in pts)
    kx = math.cos(math.radians((la0 + la1) / 2))
    sc = min((w - 160) / max((lo1 - lo0) * kx, 1e-6), (h - 50) / max(la1 - la0, 1e-6))  # px per degree lat
    cx, cy = (lo0 + lo1) / 2, (la0 + la1) / 2
    X = lambda lo: w / 2 - 40 + (lo - cx) * kx * sc; Y = lambda la: h / 2 - (la - cy) * sc
    out = [f'<svg viewBox="0 0 {w} {h}" class="map"><rect width="{w}" height="{h}" fill="#f4f1ea" class="bg"/>']
    for r in rows:
        A, B = p["sites"][r["a"]], p["sites"][r["b"]]
        col = "#1f8a4c" if r["pass"] else "#c0392b"; dash = ' stroke-dasharray="6 4"' if r.get("role") == "backup" else ""
        out.append(f'<line x1="{X(A["lon"]):.1f}" y1="{Y(A["lat"]):.1f}" x2="{X(B["lon"]):.1f}" y2="{Y(B["lat"]):.1f}" stroke="{col}" stroke-width="3"{dash}/>')
    for n, s in p["sites"].items():
        shape = {"relay": "#e0a100", "carrier": "#c0392b"}.get(s.get("role"), "#1d2b3a")
        out.append(f'<circle cx="{X(s["lon"]):.1f}" cy="{Y(s["lat"]):.1f}" r="6" fill="{shape}" stroke="#fff" stroke-width="1.5"/>'
                   f'<text class="txt" x="{X(s["lon"])+9:.1f}" y="{Y(s["lat"])+4:.1f}" font-size="11">{n}</text>')
    # 1 km scale bar
    px = sc / 111.32
    out.append(f'<line x1="20" y1="{h-15}" x2="{20+px:.1f}" y2="{h-15}" stroke="#333" stroke-width="2" class="ink"/><text class="txt" x="20" y="{h-20}" font-size="9">1 km</text>'
               f'<text class="txt" x="{w-10}" y="{h-8}" font-size="9" text-anchor="end">N ↑</text>')
    for i, t in enumerate(notes):
        out.append(f'<text class="txt" x="{w-10}" y="{16 + 12 * i}" font-size="9" text-anchor="end">{t} (dashed in KML)</text>')
    out.append("</svg>")
    return "".join(out)


def compass(b):
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int((b + 22.5) // 45) % 8]


def kml(p, rows):
    pm = "".join(f'<Placemark><name>{n}</name><description>{s.get("role","site")} · mast {s["h"]} m · pin {s.get("status","")}</description>'
                 f'<Point><coordinates>{s["lon"]},{s["lat"]},0</coordinates></Point></Placemark>' for n, s in p["sites"].items())
    ls = "".join(f'<Placemark><name>{r["a"]} – {r["b"]} ({r["km"]} km, {r["verdict"]})</name><LineString><coordinates>'
                 f'{p["sites"][r["a"]]["lon"]},{p["sites"][r["a"]]["lat"]},0 {p["sites"][r["b"]]["lon"]},{p["sites"][r["b"]]["lat"]},0'
                 f'</coordinates></LineString></Placemark>' for r in rows)
    return f'<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>{pm}{ls}</Document></kml>'


def plan_files(p, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    rows = plan(p)
    for r in rows:
        r["h_a"], r["h_b"] = p["sites"][r["a"]]["h"], p["sites"][r["b"]]["h"]
    with open(os.path.join(out_dir, "links.kml"), "w") as f:
        f.write(kml(p, rows))
    table = "".join(f'<tr><td>{r["a"]} – {r["b"]}</td><td>{r.get("role","")}</td><td>{r["km"]}</td><td>{r["az_a"]}° / {r["az_b"]}°</td>'
                    f'<td>{r["h_a"]} / {r["h_b"]} m</td><td>{r["f1_ratio"]}</td><td>{r["fade_db"]} dB</td>'
                    f'<td class="{"ok" if r["pass"] else "no"}">{"CLEAR" if r["pass"] else r["verdict"]}</td></tr>' for r in rows)
    html = {"map": map_svg(p, rows), "table": table, "profiles": [profile_svg(r) for r in rows]}
    json.dump({"rows": [{k: v for k, v in r.items() if k != "profile"} for r in rows], "class": PLAN_CLASS},
              open(os.path.join(out_dir, "plan.json"), "w"), indent=1)
    return rows, html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sites")
    ap.add_argument("--freq", type=float, default=5.8)
    ap.add_argument("--max-km", type=float, default=15)
    ap.add_argument("--relay", help="site that needs a relay")
    ap.add_argument("--to", help="comma-separated sites the relay should also see")
    ap.add_argument("--plan", help="output dir: sites.json is a plan {sites, links}; writes plan.json, links.kml")
    o = ap.parse_args()
    sites = json.load(open(o.sites))
    if o.plan:
        rows, _ = plan_files(sites, o.plan)
        for r in rows:
            print(f"{r['a']:12s} {r['b']:12s} {r['km']:5.2f} km  F1 {r['f1_ratio']:5.2f}  fade {r['fade_db']:5.1f} dB  "
                  f"{'PASS' if r['pass'] else 'FAIL'}")
        return
    if o.relay:
        anchor = sites[o.relay][:2]
        targets = {n: sites[n][:2] for n in o.to.split(",")}
        for r in relay_search(anchor, targets, freq_ghz=o.freq)[:8]:
            print(json.dumps(r))
        return
    print(f"{'from':14s} {'to':14s} {'km':>6s} {'F1':>6s}  verdict   worst point")
    for (na, a), (nb, b) in itertools.combinations(sites.items(), 2):
        if km(a[:2], b[:2]) > o.max_km:
            continue
        r = screen(a[:2], b[:2], a[2], b[2], o.freq)
        print(f"{na:14s} {nb:14s} {r['km']:6.2f} {r['f1_ratio']:6.2f}  {r['verdict']:8s}  "
              f"{r['at_km']} km, ground {r['ground_m']} m, clearance {r['clear_m']} m")


if __name__ == "__main__":
    sys.exit(main())
