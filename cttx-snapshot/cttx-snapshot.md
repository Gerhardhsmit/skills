# /cttx-snapshot

Run the full CTTX property intelligence pipeline for a specific property:
terrain analysis → candidate high sites → LOS → Snapshot PDF → KMZ.

## Usage

The user can say things like:
- `/cttx-snapshot for Welgevonden Game Reserve`
- `/cttx-snapshot property-id CTTX-LP-20260924-XXXXXX`
- `/cttx-snapshot all HIGH opportunity properties`

## Instructions

1. Find the property in the NII:
```bash
python3 -c "
import sys; sys.path.insert(0,'engine')
from db.database import get_connection
conn = get_connection()
rows = conn.execute(\"SELECT property_id, name, latitude, longitude, opportunity_profile FROM properties WHERE name LIKE '%SEARCH%'\").fetchall()
for r in rows: print(dict(r))
"
```

2. Run the pipeline:
```bash
python3 engine/cttx_engine.py analyse --property-id CTTX-XX-YYYYMMDD-XXXXXX
```

3. Report:
- Opportunity profile and evidence
- Number of candidate high sites found
- LOS link statuses
- PDF path
- KMZ path
- Total processing time vs 45s target

4. If terrain API is unavailable (FAIL), note that PDF/KMZ are generated with LOW confidence and terrain data must be re-run when CTTX_TERRAIN_API is set.

5. If PDF and KMZ were generated, confirm file sizes and that they contain matching coordinates.

## For batch processing of HIGH opportunity properties:

```bash
python3 -c "
import sys, subprocess; sys.path.insert(0,'engine')
from db.database import get_connection
conn = get_connection()
props = conn.execute(\"SELECT property_id FROM properties WHERE opportunity_profile='HIGH'\").fetchall()
for p in props:
    subprocess.run(['python3','engine/cttx_engine.py','analyse','--property-id',p['property_id']])
"
```
