#!/usr/bin/env python3
"""Desk-study terrain screen: path profile, earth bulge and Fresnel clearance between sites.

Elevation: AWS Terrain Tiles (terrarium PNG, SRTM-derived, ~15 m pixels at zoom 13), which the cloud
egress proxy allows when opentopodata/open-meteo are blocked. Stdlib only (PNG decoded with zlib).

This is a SCREEN, not a design: bare-earth model, no trees/buildings, heights assumed. Result labels:
CLEAR (>= 0.6 F1), MARGINAL (0-0.6 F1), BLOCKED (< 0). Customer text may say "terrain screen suggests";
never "line of sight confirmed" — that needs LINKPlanner and a field check.

CLI:  python3 terrain_screen.py sites.json [--freq 5.8] [--max-km 15] [--relay <site> --to <a>,<b>]
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


def screen(a, b, ha, hb, freq_ghz=5.8, k=4 / 3, n=200, elev_fn=elev):
    """Worst Fresnel-ratio point on the path a->b. ha/hb are antenna heights above ground (m)."""
    d = km(a, b)
    if d == 0:
        raise ValueError("identical points")
    ea, eb, lam = elev_fn(*a), elev_fn(*b), 0.3 / freq_ghz
    worst = None
    for i in range(1, n):
        t = i / n
        d1, d2 = d * t, d * (1 - t)
        g = elev_fn(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        bulge = d1 * d2 / (12.74 * k)                     # metres, d in km
        los = ea + ha + (eb + hb - ea - ha) * t
        f1 = math.sqrt(lam * d1 * d2 * 1000 / d)          # metres
        clear = los - g - bulge
        if worst is None or clear / f1 < worst["f1_ratio"]:
            worst = {"f1_ratio": round(clear / f1, 2), "at_km": round(d1, 2), "ground_m": round(g), "clear_m": round(clear, 1)}
    return {"km": round(d, 2), "ground_a": round(ea), "ground_b": round(eb), **worst, "verdict": verdict(worst["f1_ratio"])}


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sites")
    ap.add_argument("--freq", type=float, default=5.8)
    ap.add_argument("--max-km", type=float, default=15)
    ap.add_argument("--relay", help="site that needs a relay")
    ap.add_argument("--to", help="comma-separated sites the relay should also see")
    o = ap.parse_args()
    sites = json.load(open(o.sites))
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
