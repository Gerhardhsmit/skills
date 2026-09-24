# CTTX Skills Repository

Claude Code skills and automation engine for CTTX Services commercial and infrastructure operations.

---

## CTTX ENGINE

`engine/` — Python automation engine. Run from the Windows PC where the terrain API and Outlook are available.

### Quick start

```bash
# System diagnostic
python3 engine/cttx_engine.py diagnostic

# Daily commercial brief
python3 engine/cttx_engine.py brief

# Discovery (OSM)
python3 engine/cttx_engine.py discover --sources game_reserve wind_farm

# Discovery (file batch)
python3 engine/cttx_engine.py discover --csv engine/data/input/batch.csv

# Full property pipeline (terrain + PDF + KMZ)
python3 engine/cttx_engine.py analyse --property-id CTTX-XX-YYYYMMDD-XXXXXX

# Run all acceptance tests
python3 engine/cttx_engine.py test
```

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `CTTX_DB_PATH` | `data/cttx_nii.db` | National Infrastructure Index database |
| `CTTX_TERRAIN_API` | `http://localhost:8080` | Local SRTM 30m terrain API |
| `CTTX_OUTPUT_DIR` | `engine/data/snapshots` | PDF snapshot output directory |
| `CTTX_DRAFTS_DIR` | `engine/data/drafts` | .eml draft output directory |

### Engine modules

| Module | Purpose |
|---|---|
| `engine/db/` | National Infrastructure Index (SQLite) |
| `engine/discovery/` | OSM + CSV/JSON batch ingestion |
| `engine/terrain/` | SRTM terrain API, LOS, Fresnel, high-site search |
| `engine/pdf/` | Infrastructure Snapshot PDF generator |
| `engine/kmz/` | Google Earth KMZ generator |
| `engine/outlook/` | Assessment-offer email draft engine |
| `engine/daily_brief/` | Daily commercial brief generator |
| `engine/field/` | Level 2 field checklist generator + ingestion |
| `engine/tender/` | Tender register, audit, cross-analysis |

---

## CLAUDE CODE SKILLS

| Skill | Purpose |
|---|---|
| `/cttx-status` | System diagnostic + NII statistics |
| `/cttx-discovery` | Run discovery engine (OSM / CSV / JSON) |
| `/cttx-snapshot` | Property intelligence pipeline (terrain + PDF + KMZ) |
| `/cttx-daily-brief` | Generate daily commercial brief |
| `/cttx-outreach` | Stage assessment-offer draft (human send only) |
| `/cttx-field-checklist` | Generate / ingest Level 2 field checklists |
| `/cttx-tender-audit` | Register, audit, and cross-analyse tenders |

---

## OYA WIND FARM SKILLS

| Skill | Purpose |
|---|---|
| `/parse-site-report` | Parse WhatsApp field reports, update tracker |
| `/site-dashboard` | Show OYA fibre project dashboard |

---

## Data

- `data/cttx_nii.db` — National Infrastructure Index (SQLite)
- `engine/data/snapshots/` — Generated PDF snapshots
- `engine/data/kmz/` — Generated KMZ files
- `engine/data/drafts/` — Staged .eml draft emails
- `engine/data/input/` — Batch discovery inputs (CSV / JSON)

---

## POPIA / Outbound safety

- Only public business contact information is stored
- Drafts require explicit human review and manual send
- `auto_send` is always `False` — immutable
- No automated LinkedIn engagement or mass emailing
