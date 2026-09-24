"""
CTTX KMZ Generator — native zipfile-based KML/KMZ builder.
No simplekml dependency. Produces Google Earth-compatible KMZ.
"""

import os
import zipfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from db.database import now_iso

OUTPUT_DIR = os.environ.get("CTTX_OUTPUT_DIR",
    str(Path(__file__).parent.parent / "data" / "kmz"))


def _kml_color(r, g, b, a=255) -> str:
    return f"{a:02X}{b:02X}{g:02X}{r:02X}"


# KML color constants (AABBGGRR)
COLOR_PROPERTY   = _kml_color(26, 107, 173)    # CTTX blue
COLOR_HIGH_SITE  = _kml_color(242, 140, 40)    # CTTX accent
COLOR_BACKBONE   = _kml_color(46, 125, 50)     # green
COLOR_KNOWN_INFRA = _kml_color(200, 50, 50)    # red
COLOR_BOUNDARY   = _kml_color(26, 107, 173, 80)


def _placemark(name: str, desc: str, lat: float, lon: float,
               style_url: str, elev_m: float = 0) -> str:
    return f"""
    <Placemark>
      <name>{name}</name>
      <description><![CDATA[{desc}]]></description>
      <styleUrl>{style_url}</styleUrl>
      <Point>
        <altitudeMode>clampToGround</altitudeMode>
        <coordinates>{lon},{lat},{elev_m}</coordinates>
      </Point>
    </Placemark>"""


def _linestring(name: str, desc: str, coords: list[tuple],
                style_url: str) -> str:
    coord_str = " ".join(f"{lon},{lat},0" for lat, lon in coords)
    return f"""
    <Placemark>
      <name>{name}</name>
      <description><![CDATA[{desc}]]></description>
      <styleUrl>{style_url}</styleUrl>
      <LineString>
        <tessellate>1</tessellate>
        <coordinates>{coord_str}</coordinates>
      </LineString>
    </Placemark>"""


def _polygon(name: str, desc: str, coords: list[tuple],
             style_url: str) -> str:
    coord_str = " ".join(f"{lon},{lat},0" for lat, lon in coords)
    return f"""
    <Placemark>
      <name>{name}</name>
      <description><![CDATA[{desc}]]></description>
      <styleUrl>{style_url}</styleUrl>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>{coord_str}</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>"""


def generate_kmz(
    property_data: dict,
    engineering_data: dict,
    output_path: Optional[str] = None,
) -> dict:
    """
    Generate KMZ for a property.

    property_data: name, latitude, longitude, province, property_type,
                   boundary_coords (list of [lat,lon] pairs, optional)
    engineering_data: candidate_high_sites, los_links,
                      backbone_coords (list of [[lat,lon],...] routes),
                      known_infrastructure (list of dicts with lat,lon,name,type)
    """
    started = time.time()
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    prop_name = property_data.get("name", "Unknown")
    date_str = datetime.now().strftime("%Y%m%d")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in prop_name)

    if not output_path:
        output_path = str(Path(OUTPUT_DIR) /
                          f"CTTX_{safe_name}_Infrastructure_Study_{date_str}.kmz")

    lat = property_data.get("latitude", 0)
    lon = property_data.get("longitude", 0)

    # ── STYLES ────────────────────────────────────────────────────────────────
    styles = f"""
  <Style id="propStyle">
    <IconStyle>
      <color>{COLOR_PROPERTY}</color>
      <scale>1.2</scale>
      <Icon><href>http://maps.google.com/mapfiles/kml/shapes/target.png</href></Icon>
    </IconStyle>
  </Style>
  <Style id="highSiteStyle">
    <IconStyle>
      <color>{COLOR_HIGH_SITE}</color>
      <scale>1.1</scale>
      <Icon><href>http://maps.google.com/mapfiles/kml/shapes/triangle.png</href></Icon>
    </IconStyle>
  </Style>
  <Style id="knownInfraStyle">
    <IconStyle>
      <color>{COLOR_KNOWN_INFRA}</color>
      <scale>1.0</scale>
      <Icon><href>http://maps.google.com/mapfiles/kml/shapes/antenna.png</href></Icon>
    </IconStyle>
  </Style>
  <Style id="backboneStyle">
    <LineStyle>
      <color>{COLOR_BACKBONE}</color>
      <width>2.5</width>
    </LineStyle>
  </Style>
  <Style id="losStyle">
    <LineStyle>
      <color>{_kml_color(26, 107, 173, 180)}</color>
      <width>1.5</width>
    </LineStyle>
  </Style>
  <Style id="boundaryStyle">
    <LineStyle>
      <color>{COLOR_PROPERTY}</color>
      <width>2</width>
    </LineStyle>
    <PolyStyle>
      <color>{COLOR_BOUNDARY}</color>
    </PolyStyle>
  </Style>"""

    placemarks = []

    # ── PROPERTY CENTRE ───────────────────────────────────────────────────────
    desc = (f"<b>{prop_name}</b><br/>"
            f"Type: {property_data.get('property_type','—')}<br/>"
            f"Province: {property_data.get('province','—')}<br/>"
            f"Co-ordinates: {lat:.5f}, {lon:.5f}<br/>"
            f"Generated: {date_str} by CTTX Services")
    placemarks.append(_placemark(
        f"🏢 {prop_name}", desc, lat, lon, "#propStyle"
    ))

    # ── BOUNDARY (if provided) ────────────────────────────────────────────────
    boundary = property_data.get("boundary_coords")
    if boundary and len(boundary) >= 3:
        closed = boundary + [boundary[0]]
        placemarks.append(_polygon(
            f"{prop_name} — Boundary",
            "Property boundary (source: cadastral/OSM)",
            closed, "#boundaryStyle"
        ))

    # ── CANDIDATE HIGH SITES ──────────────────────────────────────────────────
    for idx, hs in enumerate(engineering_data.get("candidate_high_sites", [])[:10]):
        hs_desc = (f"Elevation: {hs.get('elevation_m','—')} m AMSL<br/>"
                   f"Distance from property: {hs.get('distance_from_property_m',0)/1000:.2f} km<br/>"
                   f"Classification: {hs.get('classification','Engineering candidate')}<br/>"
                   f"Source: SRTM 30m")
        placemarks.append(_placemark(
            f"▲ High Site {idx+1}", hs_desc,
            hs["latitude"], hs["longitude"],
            "#highSiteStyle", hs.get("elevation_m", 0)
        ))

        # LOS line from property to high site
        placemarks.append(_linestring(
            f"LOS candidate → HS-{idx+1}",
            f"Distance: {hs.get('distance_from_property_m',0)/1000:.2f} km",
            [(lat, lon), (hs["latitude"], hs["longitude"])],
            "#losStyle"
        ))

    # ── LOS LINKS with status ─────────────────────────────────────────────────
    for link in engineering_data.get("los_links", [])[:10]:
        status = link.get("los_status", "UNKNOWN")
        placemarks.append(_linestring(
            f"LOS: {link.get('site_a','A')} → {link.get('site_b','B')} [{status}]",
            (f"Distance: {link.get('distance_km','—')} km<br/>"
             f"Status: {status}<br/>"
             f"F1 clearance: {link.get('clearance_f1_m','—')} m<br/>"
             f"Bearing: {link.get('bearing_deg','—')}°<br/>"
             f"Confidence: {link.get('confidence','LOW')}"),
            [(lat, lon), (lat + 0.01, lon + 0.01)],  # placeholder if no site coords
            "#losStyle"
        ))

    # ── BACKBONE CORRIDORS ────────────────────────────────────────────────────
    for idx, corridor in enumerate(engineering_data.get("backbone_coords", [])[:5]):
        if len(corridor) >= 2:
            placemarks.append(_linestring(
                f"Backbone corridor {idx+1}",
                "Candidate backbone corridor — desk study",
                corridor, "#backboneStyle"
            ))

    # ── KNOWN INFRASTRUCTURE ─────────────────────────────────────────────────
    for ki in engineering_data.get("known_infrastructure", [])[:20]:
        ki_desc = (f"Type: {ki.get('type','—')}<br/>"
                   f"Source: {ki.get('source','—')}<br/>"
                   f"Status: {ki.get('classification','Mapped')}")
        placemarks.append(_placemark(
            f"📡 {ki.get('name','Known infrastructure')}",
            ki_desc,
            ki["latitude"], ki["longitude"],
            "#knownInfraStyle"
        ))

    # ── ASSEMBLE KML ──────────────────────────────────────────────────────────
    kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <name>CTTX Infrastructure Study — {prop_name} — {date_str}</name>
  <description>
    CTTX Services (Pty) Ltd — Infrastructure Desk Study
    Property: {prop_name}
    Date: {date_str}
    Classification: CONFIDENTIAL
    This document contains preliminary engineering observations only.
    All observations require field verification by a qualified CTTX engineer.
  </description>
  {styles}
  <Folder>
    <name>Property</name>
    {''.join(placemarks[:2])}
  </Folder>
  <Folder>
    <name>Candidate High Sites</name>
    {''.join(p for p in placemarks if 'High Site' in p or '▲' in p)}
  </Folder>
  <Folder>
    <name>LOS &amp; Corridors</name>
    {''.join(p for p in placemarks if 'LOS' in p or 'Backbone' in p or 'backbone' in p)}
  </Folder>
  <Folder>
    <name>Known Infrastructure</name>
    {''.join(p for p in placemarks if '📡' in p)}
  </Folder>
</Document>
</kml>"""

    # ── WRITE KMZ (KML in zip) ────────────────────────────────────────────────
    kml_path = output_path.replace(".kmz", ".kml")
    Path(kml_path).write_text(kml_content, encoding="utf-8")

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(kml_path, "doc.kml")
    Path(kml_path).unlink()

    elapsed = time.time() - started
    return {
        "status": "PASS",
        "output_path": output_path,
        "placemarks": len(placemarks),
        "elapsed_s": round(elapsed, 2),
        "generated_at": now_iso(),
    }
