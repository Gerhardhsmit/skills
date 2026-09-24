# /cttx-tender-audit

Register, audit, and cross-analyse CTTX tender submissions.
Distinguishes capability problems from evidence/packaging problems.

## Usage

- `/cttx-tender-audit register new tender`
- `/cttx-tender-audit audit tender REF-001`
- `/cttx-tender-audit cross-analysis`
- `/cttx-tender-audit status`

## Instructions — REGISTER

```bash
python3 -c "
import sys; sys.path.insert(0,'engine')
from tender.tender_engine import register_tender
tid = register_tender(
    reference='TENDER-REF',
    issuing_org='Issuing Organisation',
    description='Brief description',
    category='telecoms',  # telecoms|fibre|wireless|managed_services|other
    submission_date='2026-01-15',
    cttx_submission_path='/path/to/cttx/submission.pdf',
    source_path='/path/to/original/tender.pdf',
)
print('Registered:', tid)
"
```

## Instructions — AUDIT

1. Register the tender first.
2. Scaffold the audit criteria:
```bash
python3 -c "
import sys; sys.path.insert(0,'engine')
from tender.tender_engine import run_submission_audit
result = run_submission_audit('TENDER-ID-HERE')
print(result)
"
```

3. Read the CTTX submission at the recorded path.

4. For each of the 19 standard criteria, assess the submission and update:
```bash
python3 -c "
import sys; sys.path.insert(0,'engine')
from tender.tender_engine import update_audit_criterion
update_audit_criterion(
    audit_id='AUD-XXXXXX',
    cttx_response='CTTX explicitly described their fibre experience in section 4.2',
    evidence_location='Section 4.2, page 18',
    evidence_strength='EXPLICITLY_DEMONSTRATED',  # or SUPPORTED|PARTIALLY_SUPPORTED|NOT_EXPLICITLY_DEMONSTRATED|NOT_FOUND
    compliance_status='COMPLIANT',
    auditor_notes='Reference letter from OYA attached as Annexure B',
)
"
```

Evidence strength options:
- `EXPLICITLY_DEMONSTRATED` — directly stated with evidence
- `SUPPORTED` — implied with supporting material
- `PARTIALLY_SUPPORTED` — mentioned but evidence weak
- `NOT_EXPLICITLY_DEMONSTRATED` — not addressed directly
- `NOT_FOUND` — absent from submission

## Instructions — CROSS-ANALYSIS

Run after auditing at least 3 tenders:
```bash
python3 -c "
import sys, json; sys.path.insert(0,'engine')
from tender.tender_engine import cross_tender_analysis
result = cross_tender_analysis()
print(json.dumps(result, indent=2))
"
```

Report:
- Recurring strengths (what CTTX consistently demonstrates well)
- Recurring weaknesses (what is consistently absent or weak)
- Gaps (missing evidence patterns)
- Conclusion: capability problem or evidence/packaging problem?

## IMPORTANT

Do NOT predict win probability.
Do NOT attribute outcomes to political or procurement bias without documented evidence.
The question is: How strong was the submission CTTX actually submitted?
