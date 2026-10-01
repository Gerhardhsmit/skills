# opportunity-discovery

Continuous national and regional discovery of operations where a CTTX private network creates business value. Discovery feeds `/opportunity-business-case`.

## Usage

```
/opportunity-discovery [region] [vertical]
```

Example: `/opportunity-discovery "Western Cape" wine`

## Operating rules

- **Discovery never pauses.** It does not stop because another opportunity is waiting on a meeting, reply, assessment, pilot or decision. Discovery, research, outreach, assessment preparation and opportunity progression all run at the same time.
- **Expand beyond the Eastern Cape.** Active priority: the Western Cape.
- **Look for operations, not connections.** Score the operational signal, not the absence of internet.
- **The learning loop sharpens discovery but never gates it.** Read `data/learning-loop.json` first and use what is there, but don't wait for it to be complete.

## Target segments

Segments are listed in `data/discovery-segments.json`. Current Western Cape priority segments:

- wine farms
- olive farms
- citrus
- nuts
- forestry
- other geographically distributed agricultural and operational properties

Apply the same method to any other vertical whose operating characteristics point to a private-network opportunity.

## Instructions

### Step 1 — Load context

1. Read `data/learning-loop.json` for patterns in the target vertical or region.
2. Read `data/discovery-segments.json` for the segment's operational signals.
3. Check the Notion **CTTX Pipeline** so that customers already in the pipeline are not rediscovered as new.

### Step 2 — Find candidates

Use public sources (company websites, industry bodies, export and certification registers, news, property and cadastral data, OpenStreetMap, CTTX mast dataset). Comply with POPIA: collect business information only, and record a source for every fact.

### Step 3 — Score on operational signal

Score each candidate on these **positive** signals only:

| Signal | Examples |
|--------|----------|
| Geographic spread | Multiple farms, blocks, sites or valleys |
| Operational technology | Irrigation control, telemetry, cold chain, SCADA, weighbridges, cameras |
| Time-critical process | Harvest windows, export deadlines, cold chain, water allocation |
| Loss exposure | Theft, security incidents, crop or quality loss, downtime |
| Scale / economics | Hectares, volumes, staff, export value |
| Existing infrastructure | Fibre, towers, radios, CCTV, LoRa: **evidence of need and integration value** |

**Existing connectivity is never a negative score or a disqualifier.**

### Step 4 — Maturity gate

| Stage | Criteria | Next action |
|-------|----------|-------------|
| `SIGNAL` | Operation identified, segment matches | Continue homework |
| `RESEARCHED` | Homework questions 1–6 answered with sources | Property intelligence |
| `CASE-READY` | Assets located, operational journey understood, hypothesis formed | Run `/opportunity-business-case` |
| `OUTREACH` | Business-case package complete | Draft outreach for Gerhard. Assessment CTA |

### Step 5 — Record

- Log or update every candidate in the Notion **CTTX Pipeline** with its stage, region, segment, infrastructure hypothesis and next action.
- Add new segment signals to `data/discovery-segments.json`.
- Add new patterns to `data/learning-loop.json`.

## Output

A table of candidates with: name, region, segment, operational signals found (with sources), stage, infrastructure hypothesis and next action. End with the single highest-value next action.
