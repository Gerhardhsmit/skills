# /cttx-outreach

Stage an assessment-offer email draft for a qualified CTTX prospect.
STRICT RULE: Creates a draft only. Human must review and manually send.

## Usage

The user can say:
- `/cttx-outreach for Welgevonden Game Reserve`
- `/cttx-outreach all HIGH properties with snapshots`

## Instructions

1. Find the property and its snapshot:
```bash
python3 -c "
import sys; sys.path.insert(0,'engine')
from db.database import get_connection
conn = get_connection()
row = conn.execute(\"\"\"
    SELECT p.property_id, p.name, p.opportunity_profile,
           a.file_path as snapshot_path,
           c.public_contact_email, c.public_contact_name, c.organisation
    FROM properties p
    LEFT JOIN artifacts a ON a.property_id=p.property_id AND a.artifact_type='SNAPSHOT_PDF'
    LEFT JOIN commercial_contacts c ON c.property_id=p.property_id
    WHERE p.name LIKE '%SEARCH%'
    LIMIT 1
\"\"\").fetchone()
if row: print(dict(row))
"
```

2. If no snapshot PDF exists, run `/cttx-snapshot` first.

3. If no commercial contact exists, ask Gerhard for the contact details before proceeding. Do NOT scrape private contact information.

4. Create the draft:
```bash
python3 -c "
import sys; sys.path.insert(0,'engine')
from outlook.draft_engine import create_assessment_draft
result = create_assessment_draft(
    property_id='CTTX-XX-YYYYMMDD-XXXXXX',
    property_name='Property Name',
    to_email='contact@company.co.za',
    contact_name='Contact Name',
    organisation='Organisation Name',
    snapshot_path='/path/to/snapshot.pdf',
    specific_observation='We identified 3 candidate high sites and clear LOS corridors across the reserve.',
)
print(result)
"
```

5. Report:
   - Draft ID
   - Method (Outlook Drafts folder / .eml file path)
   - Subject line
   - Confirm: `auto_send=False`, `staged_for_human_review=True`

6. **Remind Gerhard**: Open the draft, review it, edit as needed, and send manually.

## POPIA reminder

Only use public business contact information. Source must be recorded.
Do not draft emails to private individuals without a clear business basis.
