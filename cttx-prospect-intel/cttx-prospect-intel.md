# /cttx-prospect-intel

CTTX Property Intelligence Pre-Sales Worker.

Sequence: Research → Terrain → Infrastructure → Opportunity → Email draft.

**NEVER generate a generic assessment email.**
The email is the final output of the intelligence. Not the starting point.

## Usage

- `/cttx-prospect-intel Sekala Private Game Lodge`
- `/cttx-prospect-intel for Welgevonden`
- `/cttx-prospect-intel batch` (process prospects_batch1.json)

## Instructions

### STEP 1 — IDENTIFY THE PROPERTY

Before anything else, confirm the correct property:
- Exact name and any name variants
- GPS coordinates (do not invent — source them)
- Province, nearest town, distance and bearing to town
- Property type: lodge / reserve / farm / mine / industrial / estate
- Accommodation units, operational characteristics
- Website, contact email, contact phone, contact name if discoverable

Cross-check multiple sources. If uncertain between similar-named properties, resolve before proceeding.

### STEP 2 — TERRAIN ASSESSMENT

```bash
python3 -c "
import sys; sys.path.insert(0,'engine')
from intelligence.property_intelligence import TerrainAssessment
# Populate from research, then pass to run_property_intelligence()
"
```

Determine:
- Elevation band (use SRTM API if available: `CTTX_TERRAIN_API`)
- Terrain character: PLATEAU / MOUNTAIN / VALLEY / FLAT / COMPLEX
- Obvious ridge or elevated candidates within 15-20 km
- Whether terrain favours LOS relay

If formal SRTM data is unavailable, use public sources and record:
`"Preliminary geographic screening only — formal terrain profile required"`

### STEP 3 — INFRASTRUCTURE CANDIDATES

Query the 14,000-mast dataset:

```bash
python3 -c "
import sys; sys.path.insert(0,'engine')
from intelligence.property_intelligence import query_mast_dataset
candidates = query_mast_dataset(
    lat=-24.2023, lon=27.9025,
    radius_km=25.0,
    dataset_path='engine/data/masts/cttx_masts.csv',  # adjust path
)
for c in candidates:
    print(f'{c.identifier:30s} {c.distance_km:6.1f} km  {c.bearing_deg:.0f}  [{c.status}]')
"
```

Set `CTTX_MAST_DB` environment variable to point to the dataset file.

**Do NOT just pick the closest mast.**
Rank by: distance, bearing, elevation, likely LOS, terrain obstruction.
Status must be: VERIFIED_CURRENT / HISTORICAL / CANDIDATE — never claim verified unless confirmed.

### STEP 4 — OPPORTUNITY HYPOTHESIS

Determine:
- PRIMARY NEED: LAST_MILE / BACKBONE / CLUSTER_HUB / SINGLE_SITE
- Likely applications: guest Wi-Fi / staff comms / CCTV / IoT / VoIP / PMS
- Is there a lodge/property cluster? (shared infrastructure opportunity)
- Is there a potential hub or relay candidate?

### STEP 5 — RUN INTELLIGENCE REPORT

```bash
python3 engine/intelligence/property_intelligence.py
```

Or programmatically:

```python
from engine.intelligence.property_intelligence import (
    PropertyRecord, TerrainAssessment, OpportunityHypothesis,
    run_property_intelligence
)

report = run_property_intelligence(
    property_record=prop,
    terrain_assessment=terrain,
    opportunity=opp,
    mast_dataset_path='engine/data/masts/cttx_masts.csv',
    output_dir='engine/data/intelligence',
)
```

### STEP 6 — QUALITY GATE

Check `report.quality_gate["READY_TO_SEND"]`.

If any gate fails:
- `INFRASTRUCTURE_ANALYSED` FAIL → load mast dataset or note absence explicitly
- `PERSONALISATION_GE_3` FAIL → add more researched facts
- `LOCATION_VERIFIED` FAIL → confirm coordinates from a second source

**Do NOT send if gate is not passed.**

### STEP 7 — PRESENT TO GERHARD

Show:
1. Property intelligence summary (facts found, sources)
2. Infrastructure candidates table
3. Terrain assessment
4. Opportunity hypothesis
5. Personalisation score and quality gate
6. Draft email

**Remind Gerhard:**
- Review and edit the draft
- Confirm contact is correct
- Send manually — never automatically

## Quality gate checklist

| Check | Required |
|---|---|
| PROPERTY_CORRECT | YES |
| CONTACT_CORRECT | YES |
| LOCATION_VERIFIED | YES |
| INFRASTRUCTURE_ANALYSED | YES |
| TERRAIN_CHECKED | YES |
| FACTS_SOURCED | YES |
| NO_INVENTED_CLAIMS | YES |
| PERSONALISATION_GE_3 | YES |
| CTA_CLEAR | YES |
| ASSESSMENT_POSITIONING | YES |

## Mast dataset

Set environment variable:
```
CTTX_MAST_DB=C:\path\to\cttx_masts.csv
```

Expected columns: `lat`, `lon`, `id` or `name`, `elevation`, `source`, `status`, `notes`

## POPIA note

Only use publicly available business contact information.
Do not scrape private individuals' personal contact details.
