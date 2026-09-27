"""
CTTX Property Intelligence Pre-Sales Worker

Sequence: Research → Terrain → Infrastructure → Opportunity → Email draft
Never send a generic email. Every email must pass the quality gate.
"""

import json
import math
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PropertyRecord:
    name: str
    latitude: float
    longitude: float
    province: str
    nearest_town: str
    distance_to_town_km: float
    bearing_to_town_deg: float
    property_type: str          # lodge / reserve / farm / mine / industrial
    accommodation_units: Optional[int] = None
    website: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_name: Optional[str] = None
    operational_notes: str = ""
    connectivity_notes: str = ""
    elevation_m: Optional[float] = None
    source_notes: str = ""


@dataclass
class InfrastructureCandidate:
    identifier: str
    latitude: float
    longitude: float
    distance_km: float
    bearing_deg: float
    elevation_m: Optional[float]
    source: str                 # CTTX_HISTORICAL / MNO / WISP / OSM / INFERRED
    status: str                 # VERIFIED_CURRENT / HISTORICAL / CANDIDATE
    notes: str = ""
    los_assessment: str = "NOT_ASSESSED"   # CLEAR / MARGINAL / OBSTRUCTED / NOT_ASSESSED


@dataclass
class TerrainAssessment:
    property_elevation_m: Optional[float]
    terrain_character: str      # PLATEAU / MOUNTAIN / VALLEY / FLAT / COMPLEX
    elevation_range_local: str  # e.g. "1080m–1800m within reserve"
    ridge_candidates: list = field(default_factory=list)
    los_notes: str = ""
    data_source: str = ""
    assessed: bool = False


@dataclass
class OpportunityHypothesis:
    primary_need: str           # BACKBONE / LAST_MILE / CLUSTER_HUB / SINGLE_SITE
    likely_applications: list = field(default_factory=list)
    cluster_opportunity: bool = False
    cluster_lodges: list = field(default_factory=list)
    backhaul_candidate: Optional[str] = None
    confidence: str = "LOW"     # LOW / MEDIUM / HIGH
    notes: str = ""


@dataclass
class PropertyIntelligenceReport:
    property: PropertyRecord
    infrastructure_candidates: list = field(default_factory=list)
    terrain: Optional[TerrainAssessment] = None
    opportunity: Optional[OpportunityHypothesis] = None
    personalisation_facts: list = field(default_factory=list)
    personalisation_score: int = 0
    quality_gate: dict = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    draft_email: Optional[str] = None
    draft_subject: Optional[str] = None
    draft_approved: bool = False


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def bearing_deg(lat1, lon1, lat2, lon2) -> float:
    """Initial bearing from point 1 to point 2 (degrees, 0=N)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1)*math.sin(phi2) - math.sin(phi1)*math.cos(phi2)*math.cos(dlambda)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def compass(deg: float) -> str:
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
            "S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[round(deg / 22.5) % 16]


# ---------------------------------------------------------------------------
# Mast dataset query
# ---------------------------------------------------------------------------

def query_mast_dataset(
    lat: float,
    lon: float,
    radius_km: float = 25.0,
    dataset_path: Optional[str] = None,
    top_n: int = 10,
) -> list:
    """
    Query the CTTX 14,000-mast historical dataset for candidates near a property.

    Returns a list of InfrastructureCandidate sorted by distance.

    If dataset_path is None, looks for CTTX_MAST_DB env var, then
    engine/data/masts/ directory.  Returns empty list if not found.
    """
    path = dataset_path or os.environ.get("CTTX_MAST_DB")
    if not path:
        candidates_dir = Path(__file__).parent.parent / "data" / "masts"
        for ext in ("*.csv", "*.json"):
            matches = list(candidates_dir.glob(ext))
            if matches:
                path = str(matches[0])
                break

    if not path or not Path(path).exists():
        return []

    candidates = []
    suffix = Path(path).suffix.lower()

    if suffix == ".csv":
        import csv
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    mlat = float(row.get("lat") or row.get("latitude") or row.get("LAT") or 0)
                    mlon = float(row.get("lon") or row.get("longitude") or row.get("LON") or 0)
                    dist = haversine_km(lat, lon, mlat, mlon)
                    if dist <= radius_km:
                        candidates.append({
                            "id": row.get("id") or row.get("name") or row.get("site_id") or "UNKNOWN",
                            "lat": mlat, "lon": mlon, "dist": dist,
                            "elev": row.get("elevation") or row.get("elev"),
                            "source": row.get("source") or "CTTX_HISTORICAL",
                            "status": row.get("status") or "HISTORICAL",
                            "notes": row.get("notes") or row.get("name") or "",
                        })
                except (ValueError, TypeError):
                    continue

    elif suffix == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        items = data if isinstance(data, list) else data.get("masts") or data.get("sites") or []
        for row in items:
            try:
                mlat = float(row.get("lat") or row.get("latitude") or 0)
                mlon = float(row.get("lon") or row.get("longitude") or 0)
                dist = haversine_km(lat, lon, mlat, mlon)
                if dist <= radius_km:
                    candidates.append({
                        "id": row.get("id") or row.get("name") or "UNKNOWN",
                        "lat": mlat, "lon": mlon, "dist": dist,
                        "elev": row.get("elevation") or row.get("elev"),
                        "source": row.get("source") or "CTTX_HISTORICAL",
                        "status": row.get("status") or "HISTORICAL",
                        "notes": row.get("notes") or row.get("name") or "",
                    })
            except (ValueError, TypeError):
                continue

    candidates.sort(key=lambda x: x["dist"])
    results = []
    for c in candidates[:top_n]:
        try:
            elev = float(c["elev"]) if c["elev"] else None
        except (TypeError, ValueError):
            elev = None
        results.append(InfrastructureCandidate(
            identifier=c["id"],
            latitude=c["lat"],
            longitude=c["lon"],
            distance_km=round(c["dist"], 2),
            bearing_deg=round(bearing_deg(lat, lon, c["lat"], c["lon"]), 1),
            elevation_m=elev,
            source=c["source"],
            status=c["status"],
            notes=c["notes"],
        ))
    return results


# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------

def run_quality_gate(report: PropertyIntelligenceReport) -> dict:
    p = report.property
    gate = {
        "PROPERTY_CORRECT":        bool(p.name and p.latitude and p.longitude),
        "CONTACT_CORRECT":         bool(p.contact_email or p.contact_phone),
        "LOCATION_VERIFIED":       bool(p.latitude and p.longitude and p.source_notes),
        "INFRASTRUCTURE_ANALYSED": bool(report.infrastructure_candidates),
        "TERRAIN_CHECKED":         bool(report.terrain and report.terrain.assessed),
        "FACTS_SOURCED":           bool(p.source_notes),
        "NO_INVENTED_CLAIMS":      True,   # set False manually if fabrication detected
        "PERSONALISATION_GE_3":    report.personalisation_score >= 3,
        "CTA_CLEAR":               bool(report.draft_email and "assessment" in report.draft_email.lower()),
        "ASSESSMENT_POSITIONING":  bool(report.opportunity),
    }
    gate["READY_TO_SEND"] = all(gate.values())
    return gate


# ---------------------------------------------------------------------------
# Email generator
# ---------------------------------------------------------------------------

def generate_email(report: PropertyIntelligenceReport) -> tuple[str, str]:
    """
    Returns (subject, body) from the intelligence report.
    Must be called after terrain, infrastructure, and opportunity are populated.
    """
    p = report.property
    opp = report.opportunity
    terrain = report.terrain
    candidates = report.infrastructure_candidates

    # Subject
    subject = f"Connectivity infrastructure — {p.name}"

    # Salutation
    if p.contact_name:
        salutation = f"Hi {p.contact_name.split()[0]},"
    else:
        salutation = (
            f"I'm trying to reach whoever looks after telecommunications "
            f"or infrastructure at {p.name} — apologies if this lands with the wrong person."
        )

    # Opening — specific to the property
    opening = (
        f"My name is Gerhard Smith from CTTX Services. We design and install "
        f"private wireless infrastructure for farms, lodges, and reserves across South Africa.\n\n"
        f"I did a preliminary desktop review of {p.name} in Welgevonden "
        f"and wanted to share what I found before reaching out."
    )

    # Intelligence paragraph — built from facts
    intel_lines = []

    if terrain and terrain.assessed:
        intel_lines.append(
            f"The Waterberg terrain around the reserve ranges from roughly "
            f"{terrain.elevation_range_local}, which is classic line-of-sight "
            f"territory — the plateau edges and ridgelines in the area are "
            f"the kind of geography where a properly positioned relay can reach "
            f"properties that satellite or standard cellular cannot serve well."
        )

    if candidates:
        best = candidates[0]
        intel_lines.append(
            f"Our preliminary desktop scan identified a {best.status.lower().replace('_',' ')} "
            f"infrastructure point approximately {best.distance_km:.0f} km from the property "
            f"at a bearing of {best.bearing_deg:.0f}° ({compass(best.bearing_deg)}). "
            f"Whether that translates into a practical backhaul path depends on the "
            f"terrain profile between here and there — that is what a formal assessment establishes."
        )
    elif p.nearest_town and p.distance_to_town_km:
        intel_lines.append(
            f"Vaalwater is approximately {p.distance_to_town_km:.0f} km to the north. "
            f"WaterbergNET operates fixed-wireless infrastructure out of Vaalwater, "
            f"and the key question is whether there is a viable elevated relay point "
            f"between town and the property."
        )

    if opp and opp.cluster_opportunity and opp.cluster_lodges:
        lodge_list = ", ".join(opp.cluster_lodges[:3])
        intel_lines.append(
            f"Welgevonden has multiple commercial lodges ({lodge_list} and others) "
            f"all facing the same last-mile challenge. If the terrain allows, "
            f"a shared infrastructure arrangement across the reserve makes more "
            f"sense technically and commercially than each property solving this independently."
        )

    if opp and opp.likely_applications:
        apps = ", ".join(opp.likely_applications[:4])
        intel_lines.append(
            f"Beyond guest Wi-Fi, the applications worth looking at for a property "
            f"like this include {apps} — "
            f"the sort of backbone that makes remote management and security practical."
        )

    intel_body = "\n\n".join(intel_lines)

    # What we are NOT doing
    not_selling = (
        "I am not proposing a solution at this stage. "
        "The desktop review identifies whether a proper assessment is worth doing."
    )

    # CTA
    cta = (
        "If connectivity across the property is something you're looking at, "
        "I'd be happy to walk you through what the preliminary desktop review found "
        "and explain what a formal infrastructure assessment would establish.\n\n"
        "A short call is usually enough to determine whether it's worth taking further."
    )

    # Sign-off
    signoff = (
        "Regards,\n"
        "Gerhard Smith\n"
        "CTTX Services\n"
        "gerhard@cttx.co.za\n"
        "+27 82 XXX XXXX"
    )

    body = "\n\n".join([salutation, opening, intel_body, not_selling, cta, signoff])
    return subject, body


# ---------------------------------------------------------------------------
# Main intelligence runner
# ---------------------------------------------------------------------------

def run_property_intelligence(
    property_record: PropertyRecord,
    terrain_assessment: TerrainAssessment,
    opportunity: OpportunityHypothesis,
    mast_dataset_path: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> PropertyIntelligenceReport:
    """
    Full intelligence pass for a single property.
    Returns a PropertyIntelligenceReport with draft email if quality gate passes.
    """
    report = PropertyIntelligenceReport(property=property_record)
    report.terrain = terrain_assessment
    report.opportunity = opportunity

    # Query mast dataset
    report.infrastructure_candidates = query_mast_dataset(
        property_record.latitude,
        property_record.longitude,
        radius_km=25.0,
        dataset_path=mast_dataset_path,
    )

    # Build personalisation facts
    facts = []
    if property_record.latitude and property_record.longitude:
        facts.append(f"Property geocoded: {property_record.latitude}, {property_record.longitude}")
    if property_record.nearest_town:
        facts.append(f"Nearest town: {property_record.nearest_town} (~{property_record.distance_to_town_km:.0f} km)")
    if terrain_assessment.terrain_character:
        facts.append(f"Terrain: {terrain_assessment.terrain_character} — {terrain_assessment.elevation_range_local}")
    if report.infrastructure_candidates:
        c = report.infrastructure_candidates[0]
        facts.append(f"Nearest infrastructure candidate: {c.identifier} @ {c.distance_km:.1f} km, {compass(c.bearing_deg)}")
    if opportunity.cluster_opportunity:
        facts.append(f"Lodge cluster: {len(opportunity.cluster_lodges)} properties in same reserve")
    if opportunity.likely_applications:
        facts.append(f"Likely applications: {', '.join(opportunity.likely_applications)}")
    if property_record.operational_notes:
        facts.append(f"Operations: {property_record.operational_notes}")

    report.personalisation_facts = facts
    report.personalisation_score = len(facts)

    # Generate email if score is sufficient
    if report.personalisation_score >= 3:
        subject, body = generate_email(report)
        report.draft_subject = subject
        report.draft_email = body

    # Quality gate
    report.quality_gate = run_quality_gate(report)

    # Save report
    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        slug = property_record.name.lower().replace(" ", "_")[:30]
        fname = out / f"intel_{slug}_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(asdict(report), f, indent=2, default=str)

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # --- Sekala case study ---

    prop = PropertyRecord(
        name="Sekala Private Game Lodge",
        latitude=-24.2023,
        longitude=27.9025,
        province="Limpopo",
        nearest_town="Vaalwater",
        distance_to_town_km=24.0,
        bearing_to_town_deg=352.0,
        property_type="lodge",
        accommodation_units=6,
        website="https://www.sekala.com",
        contact_email="info@sekala.com",
        contact_phone="+27 60 572 4559",
        operational_notes="Big 5 photographic safari, 5 suites + 1 villa, max 10 guests, malaria-free",
        connectivity_notes="Wi-Fi listed as amenity — no infrastructure details public",
        source_notes="sekala.com official site; welgevondengamereserve.org; GPS from sekala.co.za/about-us/location",
    )

    terrain = TerrainAssessment(
        property_elevation_m=None,  # requires SRTM query — not yet performed
        terrain_character="PLATEAU",
        elevation_range_local="1,080 m (north/gate area) to 1,800 m (southern plateau)",
        ridge_candidates=[
            "Plateau escarpment edges within reserve (southern section)",
            "Geelhoutkop area — 1,830 m, broader Waterberg",
        ],
        los_notes=(
            "Preliminary geographic screening only. Waterberg sandstone plateau with "
            "steep valley incisions — ridge edges are natural relay candidates. "
            "Formal SRTM terrain profile required before any LOS claim."
        ),
        data_source="Wikipedia/Welgevonden public sources — elevation not surveyed",
        assessed=True,
    )

    opp = OpportunityHypothesis(
        primary_need="LAST_MILE",
        likely_applications=[
            "guest Wi-Fi across multiple buildings",
            "ranger/staff comms",
            "remote camera/CCTV",
            "property management systems",
            "VoIP / admin",
        ],
        cluster_opportunity=True,
        cluster_lodges=[
            "Makweti Safari Lodge",
            "Ekuthuleni Lodge",
            "Tshwene Lodge",
            "Pitse Lodge",
            "Clifftop Safari Hideaway",
        ],
        backhaul_candidate="WaterbergNET (Vaalwater) — WAPA/ICASA registered WISP",
        confidence="MEDIUM",
        notes=(
            "Welgevonden FAQ acknowledges reserve-wide connectivity issues — "
            "cluster arrangement commercially attractive if terrain allows shared backhaul."
        ),
    )

    report = run_property_intelligence(
        property_record=prop,
        terrain_assessment=terrain,
        opportunity=opp,
        output_dir="engine/data/intelligence",
    )

    print("=" * 70)
    print("CTTX PROPERTY INTELLIGENCE REPORT")
    print("=" * 70)
    print(f"Property:       {report.property.name}")
    print(f"Location:       {report.property.latitude}, {report.property.longitude}")
    print(f"Nearest town:   {report.property.nearest_town} ({report.property.distance_to_town_km:.0f} km, {compass(report.property.bearing_to_town_deg)})")
    print(f"Terrain:        {report.terrain.terrain_character} — {report.terrain.elevation_range_local}")
    print()
    print(f"Infrastructure candidates from mast dataset: {len(report.infrastructure_candidates)}")
    for c in report.infrastructure_candidates:
        print(f"  {c.identifier:30s} {c.distance_km:6.1f} km  {compass(c.bearing_deg):4s}  [{c.status}]")
    print()
    print("PERSONALISATION FACTS:")
    for i, fact in enumerate(report.personalisation_facts, 1):
        print(f"  {i}. {fact}")
    print(f"\nPersonalisation score: {report.personalisation_score}/10 (minimum 3 required)")
    print()
    print("QUALITY GATE:")
    for k, v in report.quality_gate.items():
        status = "PASS" if v else "FAIL"
        print(f"  {k:35s} {status}")
    print()
    if report.quality_gate.get("READY_TO_SEND"):
        print("STATUS: READY TO SEND (pending human approval)")
    else:
        fails = [k for k, v in report.quality_gate.items() if not v and k != "READY_TO_SEND"]
        print(f"STATUS: NOT READY — gate failures: {', '.join(fails)}")
    print()
    if report.draft_email:
        print("=" * 70)
        print(f"DRAFT SUBJECT: {report.draft_subject}")
        print("=" * 70)
        print(report.draft_email)
        print("=" * 70)
        print()
        print("NOTE: This draft requires human review and manual send.")
        print("      It must NOT be sent automatically.")
