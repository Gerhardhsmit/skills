# /cttx-field-checklist

Generate a Level 2 field assessment checklist for a field-partner technician,
or ingest a completed checklist back into the NII.

## Usage

- `/cttx-field-checklist generate for Welgevonden Game Reserve`
- `/cttx-field-checklist ingest completed checklist` (then paste JSON)

## Instructions — GENERATE

1. Find the property:
```bash
python3 -c "
import sys; sys.path.insert(0,'engine')
from db.database import get_connection
conn = get_connection()
row = conn.execute(\"SELECT property_id, name FROM properties WHERE name LIKE '%SEARCH%' LIMIT 1\").fetchone()
print(dict(row))
"
```

2. Generate the checklist:
```bash
python3 -c "
import sys; sys.path.insert(0,'engine')
from field.field_checklist import generate_checklist_text, generate_checklist_json
import json

# Plain text version for WhatsApp / SMS to field tech
text = generate_checklist_text('Property Name', 'CTTX-XX-YYYYMMDD-XXXXXX')
print(text)

# JSON version for digital completion
cl = generate_checklist_json('Property Name', 'CTTX-XX-YYYYMMDD-XXXXXX')
with open('engine/data/output/checklist_PROPERTY.json','w') as f:
    json.dump(cl, f, indent=2)
"
```

3. Display the plain-text checklist to the user for forwarding to the field technician.

4. Note: Technician uses PASS / FAIL / NOT_PRESENT / UNKNOWN / PHOTO_REQUIRED.
   Items marked [📷] require a photograph. Critical observations require photographic evidence.

## Instructions — INGEST

When a completed JSON checklist is returned by the field tech:

1. Paste the JSON or provide the file path.

2. Ingest:
```bash
python3 -c "
import sys, json; sys.path.insert(0,'engine')
from field.field_checklist import ingest_completed_checklist
with open('PATH_TO_COMPLETED.json') as f:
    data = json.load(f)
result = ingest_completed_checklist(data)
print(result)
"
```

3. Report:
   - Observations written to NII
   - Property assessment status updated
   - Confirm source=field_survey and confidence recorded
   - Flag any FAIL items for engineering review

## Scope reminder

Field technicians record observations only.
They do not make engineering design decisions.
CTTX engineering team analyses the data.
