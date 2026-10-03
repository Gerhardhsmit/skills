#!/usr/bin/env python3
"""Satellite look at a site area: Sentinel-2 true colour (10 m) with sites, hops and carrier points drawn on.

Why: the hill that blocks a valley route is usually the relay AND the carrier handover. Before it goes
into a proposal, look at it: farm tracks and cattle paths up the slope (access, and the farm uses the
land), fences/paddocks (ownership), pivots, dams, power lines, existing structures on the crest.

Cloud sessions: Google/Esri/Bing tiles are blocked; the Sentinel-2 COG bucket on AWS is reachable.
10 m pixels show roads, wide tracks, paddocks, pivots, dams and bare crest areas — not a 1 m cattle path.
For sub-metre detail, open the KML from `terrain_screen.py --plan` in Google Earth Pro on the PC
(historical imagery slider: tracks show best in dry months).

Needs: pip install rasterio pyproj mgrs pillow   (not stdlib — this is the one heavy tool)
CLI:  python3 site_imagery.py plan.json out.png [--pad-km 1.5] [--days 90] [--extra extra.json]
      extra.json = [{"name":..,"lat":..,"lon":..,"kind":"carrier"}]  (e.g. Vodacom points; INTERNAL only)
"""
import argparse, datetime as dt, json, math, os, re, sys, urllib.request

BUCKET = "https://sentinel-cogs.s3.us-west-2.amazonaws.com"
os.environ.setdefault("CURL_CA_BUNDLE", "/root/.ccr/ca-bundle.crt" if os.path.exists("/root/.ccr/ca-bundle.crt") else "")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")


def _get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()


def clearest_scene(lat, lon, days=90, max_cloud=5.0, today=None):
    """Lowest-cloud Sentinel-2 L2A scene for the MGRS tile containing (lat, lon) in the last `days`."""
    import mgrs
    tile = mgrs.MGRS().toMGRS(lat, lon, MGRSPrecision=0)
    zone, band, sq = tile[:2], tile[2], tile[3:5]
    today = today or dt.date.today()
    best = None
    for back in range(0, days // 28 + 2):
        m = (today.replace(day=1) - dt.timedelta(days=28 * back))
        prefix = f"sentinel-s2-l2a-cogs/{int(zone)}/{band}/{sq}/{m.year}/{m.month}/"
        xml = _get(f"{BUCKET}/?list-type=2&prefix={prefix}&delimiter=/").decode()
        for scene in re.findall(r"<Prefix>" + re.escape(prefix) + r"([^<]+)/</Prefix>", xml):
            date = dt.datetime.strptime(scene.split("_")[2], "%Y%m%d").date()
            if (today - date).days > days:
                continue
            meta = json.loads(_get(f"{BUCKET}/{prefix}{scene}/{scene}.json"))
            cc = meta["properties"].get("eo:cloud_cover", 100)
            if best is None or (cc, -date.toordinal()) < (best["cloud"], -best["date"].toordinal()):
                best = {"scene": scene, "date": date, "cloud": round(cc, 2), "url": f"{BUCKET}/{prefix}{scene}/TCI.tif"}
        if best and best["cloud"] <= max_cloud:
            break
    return best


def render(points, links, out_png, pad_km=1.5, days=90, scale=4):
    """points: {name: {lat, lon, kind}}; links: [{a, b, ok, role}]. Writes PNG; returns scene info."""
    import rasterio
    from rasterio.windows import from_bounds
    from pyproj import Transformer
    from PIL import Image, ImageDraw
    lats = [p["lat"] for p in points.values()]; lons = [p["lon"] for p in points.values()]
    cy, cx = sum(lats) / len(lats), sum(lons) / len(lons)
    sc = clearest_scene(cy, cx, days)
    if not sc:
        raise RuntimeError("no Sentinel-2 scene found")
    with rasterio.open(sc["url"]) as src:
        tf = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        xy = {n: tf.transform(p["lon"], p["lat"]) for n, p in points.items()}
        pad = pad_km * 1000
        xs = [v[0] for v in xy.values()]; ys = [v[1] for v in xy.values()]
        win = from_bounds(min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad, src.transform)
        arr = src.read([1, 2, 3], window=win)
        wt = src.window_transform(win)
    img = Image.fromarray(arr.transpose(1, 2, 0)).resize((arr.shape[2] * scale, arr.shape[1] * scale), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    px = lambda n: ((xy[n][0] - wt.c) / wt.a * scale, (xy[n][1] - wt.f) / wt.e * scale)
    for ln in links:
        col = (40, 200, 110) if ln.get("ok", True) else (230, 70, 60)
        a, b = px(ln["a"]), px(ln["b"])
        if ln.get("role") == "backup":
            n = 24
            for i in range(0, n, 2):
                d.line([a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n,
                        a[0] + (b[0] - a[0]) * (i + 1) / n, a[1] + (b[1] - a[1]) * (i + 1) / n], fill=col, width=4)
        else:
            d.line([a, b], fill=col, width=4)
    colours = {"relay": (240, 170, 0), "carrier": (230, 70, 60)}
    for n, p in points.items():
        if p.get("kind") == "hidden":
            continue
        x, y = px(n); c = colours.get(p.get("kind"), (255, 255, 255))
        d.ellipse([x - 8, y - 8, x + 8, y + 8], fill=c, outline=(0, 0, 0), width=2)
        d.text((x + 11, y - 7), n, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
    bar = 1000 / wt.a * scale
    d.line([20, img.height - 20, 20 + bar, img.height - 20], fill=(255, 255, 255), width=3)
    d.text((20, img.height - 36), "1 km", fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
    d.text((img.width - 250, img.height - 22), f"Sentinel-2 {sc['date']} · cloud {sc['cloud']}%",
           fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
    img.save(out_png)
    return sc


def crop(points, centre, out_png, half_km=0.8, days=90, scale=8):
    """Close-up of one point (e.g. the relay crest) for track/fence inspection."""
    lat, lon = points[centre]["lat"], points[centre]["lon"]
    dlat = half_km / 111.32; dlon = half_km / (111.32 * math.cos(math.radians(lat)))
    box = {centre: points[centre], "_nw": {"lat": lat + dlat, "lon": lon - dlon, "kind": "hidden"},
           "_se": {"lat": lat - dlat, "lon": lon + dlon, "kind": "hidden"}}
    return render(box, [], out_png, pad_km=0, days=days, scale=scale)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan"); ap.add_argument("out")
    ap.add_argument("--pad-km", type=float, default=1.5)
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--extra")
    ap.add_argument("--zoom", help="site name for an extra close-up PNG (<out>_zoom.png)")
    o = ap.parse_args()
    p = json.load(open(o.plan))
    pts = {n: {"lat": s["lat"], "lon": s["lon"], "kind": s.get("role")} for n, s in p["sites"].items()}
    links = [{"a": l["a"], "b": l["b"], "role": l.get("role"), "ok": l.get("ok", True)} for l in p["links"]]
    if o.extra:
        for e in json.load(open(o.extra)):
            pts[e["name"]] = {"lat": e["lat"], "lon": e["lon"], "kind": e.get("kind", "carrier")}
    sc = render(pts, links, o.out, o.pad_km, o.days)
    print(json.dumps({k: str(v) for k, v in sc.items()}))
    if o.zoom:
        z = o.out.rsplit(".", 1)[0] + "_zoom.png"
        crop(pts, o.zoom, z, days=o.days)
        print(z)


if __name__ == "__main__":
    sys.exit(main())
