"""Data-source adapters. Every call records success or failure in the evidence log.

LiveSources  — OpenStreetMap (Overpass, Nominatim), Open-Meteo / OpenTopoData elevation,
               OpenCelliD (API key or cached country CSV), user Google Earth KML/CSV,
               CTTX intelligence graph.
FixtureSources — deterministic synthetic world for the Test Mode scenarios.
"""
import csv
import datetime
import gzip
import json
import math
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from geo import haversine_km, local_xy_km

UA = "CTTX-Link-Assessment-Architect/1.0 (gerhard@cttx)"
SA_MNC = {1: "Vodacom", 2: "Telkom", 7: "Cell C", 10: "MTN", 38: "Rain", 74: "Rain"}
TODAY = datetime.date.today().isoformat()


class SourceLog:
    def __init__(self):
        self.entries = []  # {source, action, ok, detail, date}

    def ok(self, source, action, detail=""):
        self.entries.append({"source": source, "action": action, "ok": True, "detail": detail, "date": TODAY})

    def fail(self, source, action, detail):
        self.entries.append({"source": source, "action": action, "ok": False, "detail": detail, "date": TODAY})

    def failed(self, source):
        return any(e["source"] == source and not e["ok"] for e in self.entries)


def _http_json(url, data=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ------------------------------------------------------------------ user-supplied files

def load_kml_points(path):
    """Placemark points from a Google Earth KML/KMZ export: [{name, lat, lon, description}]."""
    import zipfile
    raw = zipfile.ZipFile(path).read(next(n for n in zipfile.ZipFile(path).namelist() if n.endswith(".kml"))) \
        if path.lower().endswith(".kmz") else open(path, "rb").read()
    root = ET.fromstring(raw)
    ns = {"k": root.tag.split("}")[0].strip("{")} if root.tag.startswith("{") else {}
    q = (lambda t: f"k:{t}") if ns else (lambda t: t)
    out = []
    for pm in root.iter(("{%s}Placemark" % ns["k"]) if ns else "Placemark"):
        name = pm.findtext(q("name"), default="", namespaces=ns)
        desc = pm.findtext(q("description"), default="", namespaces=ns)
        coords = pm.find(f".//{q('Point')}/{q('coordinates')}", ns)
        if coords is None or not coords.text:
            continue
        lon, lat = map(float, coords.text.strip().split(",")[:2])
        out.append({"name": name.strip(), "lat": lat, "lon": lon, "description": desc.strip()})
    return out


def load_points_csv(path):
    """CSV with columns name,lat,lon[,kind,height_m,operator,verified,note]."""
    with open(path, newline="") as f:
        return [{k.strip(): v.strip() for k, v in row.items() if k} for row in csv.DictReader(f)]


# ------------------------------------------------------------------ live sources

class LiveSources:
    name = "live"

    def __init__(self, log, opencellid_key=None, cell_csv=None, kml=None, points_csv=None,
                 elevation_provider="open-meteo"):
        self.log = log
        self.ocid_key = opencellid_key or os.environ.get("OPENCELLID_KEY")
        self.cell_csv = cell_csv
        self.kml = kml
        self.points_csv = points_csv
        self.elev_provider = elevation_provider
        self._elev_cache = {}

    # --- geocoding
    def geocode(self, query):
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
            {"q": query, "format": "json", "limit": 5, "countrycodes": "za,na,bw,zw,mz,ls,sz"})
        try:
            res = _http_json(url)
        except Exception as e:  # noqa: BLE001
            self.log.fail("Nominatim (OSM)", f"geocode '{query}'", str(e))
            return []
        self.log.ok("Nominatim (OSM)", f"geocode '{query}'", f"{len(res)} candidates")
        return [{"lat": float(r["lat"]), "lon": float(r["lon"]), "label": r.get("display_name", ""),
                 "type": r.get("type", ""), "osm_id": f"{r.get('osm_type')}/{r.get('osm_id')}"} for r in res]

    # --- elevation (metres ASL), batched
    def elevations(self, points):
        todo = [p for p in points if (round(p[0], 5), round(p[1], 5)) not in self._elev_cache]
        providers = [self.elev_provider] + [p for p in ("open-meteo", "opentopodata") if p != self.elev_provider]
        for i in range(0, len(todo), 100):
            chunk = todo[i:i + 100]
            got = None
            for prov in providers:
                try:
                    if prov == "open-meteo":
                        url = "https://api.open-meteo.com/v1/elevation?" + urllib.parse.urlencode({
                            "latitude": ",".join(f"{p[0]:.5f}" for p in chunk),
                            "longitude": ",".join(f"{p[1]:.5f}" for p in chunk)})
                        got = _http_json(url)["elevation"]
                    else:
                        url = "https://api.opentopodata.org/v1/srtm30m?locations=" + "|".join(
                            f"{p[0]:.5f},{p[1]:.5f}" for p in chunk)
                        got = [r["elevation"] for r in _http_json(url)["results"]]
                    self.log.ok(f"Elevation ({prov}, Copernicus/SRTM DEM)", "terrain sampling", f"{len(chunk)} pts")
                    break
                except Exception as e:  # noqa: BLE001
                    self.log.fail(f"Elevation ({prov})", "terrain sampling", str(e))
            if got is None:
                return None
            for p, z in zip(chunk, got):
                self._elev_cache[(round(p[0], 5), round(p[1], 5))] = z
        return [self._elev_cache[(round(p[0], 5), round(p[1], 5))] for p in points]

    # --- OpenStreetMap infrastructure
    def osm(self, lat, lon, radius_km):
        r = int(radius_km * 1000)
        q = f"""[out:json][timeout:90];
(
  nwr["man_made"~"^(mast|tower|communications_tower)$"](around:{r},{lat},{lon});
  nwr["tower:type"~"communication|telecommunication"](around:{r},{lat},{lon});
  nwr["telecom"](around:{r},{lat},{lon});
  node["natural"~"^(peak|hill)$"](around:{r},{lat},{lon});
  nwr["man_made"~"^(water_tower|silo)$"](around:{r},{lat},{lon});
  way["highway"~"^(motorway|trunk|primary)$"](around:{r},{lat},{lon});
  way["railway"="rail"](around:{r},{lat},{lon});
  way["power"="line"](around:{r},{lat},{lon});
  nwr["power"="substation"](around:{r},{lat},{lon});
);
out center tags;"""
        for host in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"):
            try:
                res = _http_json(host, data=urllib.parse.urlencode({"data": q}).encode(), timeout=120)
                self.log.ok("OpenStreetMap (Overpass)", f"infrastructure search {radius_km} km",
                            f"{len(res.get('elements', []))} elements via {host.split('/')[2]}")
                return _classify_osm(res.get("elements", []))
            except Exception as e:  # noqa: BLE001
                self.log.fail("OpenStreetMap (Overpass)", f"infrastructure search {radius_km} km ({host.split('/')[2]})", str(e))
        return None

    # --- OpenCelliD
    def cells(self, lat, lon, radius_km):
        if self.cell_csv and os.path.exists(self.cell_csv):
            return self._cells_from_csv(lat, lon, radius_km)
        if not self.ocid_key:
            self.log.fail("OpenCelliD", "cell search", "no OPENCELLID_KEY and no cached country CSV")
            return None
        # getInArea is limited to small boxes: tile 2 km squares, cap at 10 km radius
        rr = min(radius_km, 10)
        dlat = 2 / 111.32
        dlon = 2 / (111.32 * math.cos(math.radians(lat)))
        n = int(math.ceil(rr / 2))
        cells, errors = {}, 0
        for i in range(-n, n):
            for j in range(-n, n):
                bbox = f"{lat + i * dlat},{lon + j * dlon},{lat + (i + 1) * dlat},{lon + (j + 1) * dlon}"
                url = "https://opencellid.org/cell/getInArea?" + urllib.parse.urlencode(
                    {"key": self.ocid_key, "BBOX": bbox, "format": "json", "limit": 50})
                try:
                    for c in _http_json(url).get("cells", []):
                        cells[(c.get("mcc"), c.get("mnc"), c.get("lac"), c.get("cellid"))] = _cell(c, "OpenCelliD API")
                except Exception:  # noqa: BLE001
                    errors += 1
        if errors and not cells:
            self.log.fail("OpenCelliD", f"getInArea {rr} km", f"{errors} tile requests failed")
            return None
        self.log.ok("OpenCelliD", f"getInArea {rr} km", f"{len(cells)} cells, {errors} tile errors")
        return [c for c in cells.values() if haversine_km(lat, lon, c["lat"], c["lon"]) <= radius_km]

    def _cells_from_csv(self, lat, lon, radius_km):
        opener = gzip.open if self.cell_csv.endswith(".gz") else open
        out = []
        dlat = radius_km / 111.0
        with opener(self.cell_csv, "rt") as f:
            for row in csv.reader(f):
                try:
                    radio, mcc, mnc, lac, cid, _, clon, clat = row[:8]
                    clat, clon = float(clat), float(clon)
                except (ValueError, IndexError):
                    continue
                if abs(clat - lat) > dlat or haversine_km(lat, lon, clat, clon) > radius_km:
                    continue
                out.append(_cell({"radio": radio, "mcc": mcc, "mnc": mnc, "lac": lac, "cellid": cid,
                                  "lat": clat, "lon": clon, "updated": row[12] if len(row) > 12 else ""},
                                 "OpenCelliD country CSV"))
        self.log.ok("OpenCelliD", f"cached CSV search {radius_km} km", f"{len(out)} cells")
        return out

    # --- user-provided Google Earth pins / CSV
    def user_points(self):
        pts = []
        if self.kml:
            try:
                for p in load_kml_points(self.kml):
                    pts.append({**p, "source": f"Google Earth KML ({os.path.basename(self.kml)})"})
                self.log.ok("Google Earth KML (user)", "load placemarks", f"{len(pts)} points")
            except Exception as e:  # noqa: BLE001
                self.log.fail("Google Earth KML (user)", "load placemarks", str(e))
        if self.points_csv:
            try:
                rows = load_points_csv(self.points_csv)
                for r in rows:
                    pts.append({**r, "lat": float(r["lat"]), "lon": float(r["lon"]),
                                "source": f"User CSV ({os.path.basename(self.points_csv)})"})
                self.log.ok("User CSV", "load points", f"{len(rows)} points")
            except Exception as e:  # noqa: BLE001
                self.log.fail("User CSV", "load points", str(e))
        return pts


def _cell(c, source):
    mnc = int(c.get("mnc") or -1)
    return {"source": source, "radio": str(c.get("radio", "")).upper(), "mcc": int(c.get("mcc") or 0), "mnc": mnc,
            "lac": c.get("lac"), "cellid": c.get("cellid"), "lat": float(c["lat"]), "lon": float(c["lon"]),
            "operator": SA_MNC.get(mnc, f"MNC {mnc}") if int(c.get("mcc") or 0) == 655 else f"MCC {c.get('mcc')}",
            "updated": c.get("updated", "")}


def _classify_osm(elements):
    out = {"masts": [], "high_ground": [], "structures": [], "corridors": []}
    for e in elements:
        t = e.get("tags", {})
        lat = e.get("lat", e.get("center", {}).get("lat"))
        lon = e.get("lon", e.get("center", {}).get("lon"))
        if lat is None:
            continue
        ref = f"osm {e['type']}/{e['id']}"
        mm = t.get("man_made", "")
        if mm in ("mast", "tower", "communications_tower") or "telecom" in t or "tower:type" in t:
            if mm == "tower" and t.get("tower:type") not in (None, "communication", "telecommunication"):
                continue  # observation/cooling/lighting towers are not telecom
            out["masts"].append({"lat": lat, "lon": lon, "ref": ref, "name": t.get("name", ""),
                                 "operator": t.get("operator", ""), "height_m": _num(t.get("height")),
                                 "tags": {k: v for k, v in t.items() if k in (
                                     "man_made", "tower:type", "communication:mobile_phone", "telecom",
                                     "operator", "height", "tower:construction")}})
        elif t.get("natural") in ("peak", "hill"):
            out["high_ground"].append({"lat": lat, "lon": lon, "ref": ref, "name": t.get("name", ""),
                                       "ele": _num(t.get("ele")), "kind": t["natural"]})
        elif mm in ("water_tower", "silo"):
            out["structures"].append({"lat": lat, "lon": lon, "ref": ref, "name": t.get("name", ""),
                                      "kind": mm, "height_m": _num(t.get("height"))})
        else:
            kind = ("road:" + t["highway"]) if "highway" in t else "rail" if t.get("railway") else \
                "power_line" if t.get("power") == "line" else "substation" if t.get("power") == "substation" else None
            if kind:
                out["corridors"].append({"lat": lat, "lon": lon, "ref": ref, "kind": kind,
                                         "name": t.get("ref") or t.get("name", "")})
    return out


def _num(v):
    if v is None:
        return None
    m = re.search(r"\d+(\.\d+)?", str(v))
    return float(m.group(0)) if m else None


# ------------------------------------------------------------------ fixture world (Test Mode)

class FixtureSources:
    """Synthetic world: terrain = base + gaussian hills + gaussian ridges. Deterministic, offline."""
    name = "fixture"

    def __init__(self, log, world):
        self.log = log
        self.w = world

    def geocode(self, query):
        hits = [g for g in self.w.get("geocode", []) if query.lower() in g["label"].lower()]
        self.log.ok("Fixture geocoder", f"geocode '{query}'", f"{len(hits)} candidates")
        return hits

    def _z(self, lat, lon):
        lat0, lon0 = self.w["origin"]
        z = self.w.get("base_m", 0)
        x, y = local_xy_km(lat0, lon0, lat, lon)
        for h in self.w.get("hills", []):
            hx, hy = local_xy_km(lat0, lon0, h["lat"], h["lon"])
            z += h["height_m"] * math.exp(-((x - hx) ** 2 + (y - hy) ** 2) / (2 * h["sigma_km"] ** 2))
        for r in self.w.get("ridges", []):
            ax, ay = local_xy_km(lat0, lon0, *r["a"])
            bx, by = local_xy_km(lat0, lon0, *r["b"])
            dx, dy = bx - ax, by - ay
            t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
            d = math.hypot(x - ax - t * dx, y - ay - t * dy)
            z += r["height_m"] * math.exp(-d * d / (2 * r["sigma_km"] ** 2))
        return z

    def elevations(self, points):
        if self.w.get("fail", {}).get("elevation"):
            self.log.fail("Fixture elevation", "terrain sampling", "simulated outage")
            return None
        self.log.ok("Fixture elevation (synthetic DEM)", "terrain sampling", f"{len(points)} pts")
        return [self._z(*p) for p in points]

    def osm(self, lat, lon, radius_km):
        if self.w.get("fail", {}).get("osm"):
            self.log.fail("Fixture OSM", "infrastructure search", "simulated outage")
            return None
        near = lambda items: [i for i in items if haversine_km(lat, lon, i["lat"], i["lon"]) <= radius_km]  # noqa: E731
        o = self.w.get("osm", {})
        res = {k: near(o.get(k, [])) for k in ("masts", "high_ground", "structures", "corridors")}
        self.log.ok("Fixture OSM", f"infrastructure search {radius_km} km", f"{sum(map(len, res.values()))} elements")
        return res

    def cells(self, lat, lon, radius_km):
        if self.w.get("fail", {}).get("cells"):
            self.log.fail("Fixture OpenCelliD", "cell search", "simulated outage")
            return None
        res = [dict(c, source="Fixture OpenCelliD", operator=SA_MNC.get(c["mnc"], str(c["mnc"])))
               for c in self.w.get("cells", []) if haversine_km(lat, lon, c["lat"], c["lon"]) <= radius_km]
        self.log.ok("Fixture OpenCelliD", f"cell search {radius_km} km", f"{len(res)} cells")
        return res

    def user_points(self):
        return [dict(p, source="Fixture Google Earth KML") for p in self.w.get("user_points", [])]


# ------------------------------------------------------------------ intelligence graph

class IntelGraph:
    """data/intelligence-graph.json — verified knowledge that compounds across assessments."""

    def __init__(self, path):
        self.path = path
        self.g = {"version": 1, "nodes": [], "routes": [], "rejected_links": []}
        if path and os.path.exists(path):
            with open(path) as f:
                self.g = json.load(f)

    def nodes_near(self, lat, lon, radius_km):
        return [n for n in self.g["nodes"] if haversine_km(lat, lon, n["lat"], n["lon"]) <= radius_km]

    def rejected(self, a, b):
        return next((r for r in self.g["rejected_links"]
                     if {r["a"], r["b"]} == {a, b} and r.get("verified")), None)

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.g, f, indent=2, ensure_ascii=False)
            f.write("\n")
