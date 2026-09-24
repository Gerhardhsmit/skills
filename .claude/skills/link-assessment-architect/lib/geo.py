"""Geodesy and RF path geometry used across the assessment engine."""
import math
import re
import urllib.parse

EARTH_R_KM = 6371.0
K_FACTOR = 4 / 3
FRESNEL_CLEAR = 0.6


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R_KM * math.asin(math.sqrt(min(1.0, h)))


def bearing_deg(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def destination(lat, lon, bearing, dist_km):
    d = dist_km / EARTH_R_KM
    b = math.radians(bearing)
    p1, l1 = math.radians(lat), math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), (math.degrees(l2) + 540) % 360 - 180


def interpolate(lat1, lon1, lat2, lon2, n):
    """n+1 evenly spaced points from A to B inclusive (linear is fine for < 100 km)."""
    return [(lat1 + (lat2 - lat1) * i / n, lon1 + (lon2 - lon1) * i / n) for i in range(n + 1)]


def local_xy_km(lat0, lon0, lat, lon):
    x = math.radians(lon - lon0) * EARTH_R_KM * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * EARTH_R_KM
    return x, y


def fspl_db(d_km, f_mhz):
    return 20 * math.log10(max(d_km, 0.001)) + 20 * math.log10(f_mhz) + 32.44


def fresnel_m(d1_km, d2_km, f_ghz):
    if d1_km <= 0 or d2_km <= 0:
        return 0.0
    return 17.32 * math.sqrt(d1_km * d2_km / (f_ghz * (d1_km + d2_km)))


def earth_bulge_m(d1_km, d2_km, k=K_FACTOR):
    return d1_km * d2_km / (12.74 * k)


# ---------------------------------------------------------------- location parsing

_DMS = re.compile(
    r"""(\d{1,3})\s*[°º]\s*(\d{1,2})?\s*['’′]?\s*(\d{1,2}(?:[.,]\d+)?)?\s*(?:"|”|″|'')?\s*([NSEW])\b""",
)


def _dms_to_dec(deg, mins, secs, hemi):
    v = float(deg) + float(mins or 0) / 60 + float(str(secs or 0).replace(",", ".")) / 3600
    return -v if hemi.upper() in "SW" else v


def parse_location(text):
    """Parse decimal, DMS, Google Maps / Earth URLs. Returns (lat, lon) or None. Never guesses."""
    if not text:
        return None
    s = urllib.parse.unquote(str(text)).strip()
    # Google Maps/Earth URL forms: @lat,lon  |  !3dlat!4dlon  |  q=lat,lon  |  ll=lat,lon
    for pat in (r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", r"@(-?\d+\.\d+),(-?\d+\.\d+)",
                r"[?&](?:q|ll|query|destination)=(-?\d+\.\d+),\s*(-?\d+\.\d+)"):
        m = re.search(pat, s)
        if m:
            return _valid(float(m.group(1)), float(m.group(2)))
    dms = _DMS.findall(s)
    if len(dms) >= 2:
        vals = {h.upper(): _dms_to_dec(d, m, sec, h) for d, m, sec, h in dms[:2]}
        lat = vals.get("S", vals.get("N"))
        lon = vals.get("E", vals.get("W"))
        if lat is not None and lon is not None:
            return _valid(lat, lon)
    m = re.search(r"(-?\d{1,2}\.\d+)\s*[,; ]\s*(-?\d{1,3}\.\d+)", s)
    if m:
        return _valid(float(m.group(1)), float(m.group(2)))
    return None


def _valid(lat, lon):
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return round(lat, 6), round(lon, 6)
    return None
