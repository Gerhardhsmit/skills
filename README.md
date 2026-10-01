# CTTX — Claude Code Skills

## Sales engine (Dutoit reference pattern)

The Dutoit Langkloof business case is the reference pattern for turning an opportunity into a private-network business case:

CUSTOMER OPERATION → BUSINESS PROBLEM → ECONOMIC / OPERATIONAL CONSEQUENCE → PRIVATE NETWORK OPPORTUNITY → CUSTOMER-SPECIFIC NETWORK CONCEPT → PROOF / ASSESSMENT → DEPLOYMENT

### `/opportunity-discovery`
Continuous national/regional discovery (Western Cape is an active priority: wine, olives, citrus, nuts, forestry). Scores on operational signal. Existing connectivity is never a negative score. Never pauses while other deals wait.

### `/opportunity-business-case`
Customer-specific homework → six-section business case → Private Infrastructure Network Assessment CTA → Notion + learning-loop record.

Data: `data/learning-loop.json` (learning loop), `data/discovery-segments.json` (segment signals).

## OYA Project

Skills for managing the OYA Wind Farm fiber optic project via WhatsApp reports.

## Skills

### `/parse-site-report`
Paste WhatsApp daily report messages. Claude extracts all reports, updates the tracker, and shows the project dashboard.

### `/site-dashboard`
Show the full project progress dashboard across all 18 turbines (WTG-01 to WTG-18).

## Data

Progress is tracked in `data/progress.json` — cumulative record of all reports received.

## Report Format

Technicians send this template daily before 17:00:

```
*TURBINE NUMBER: WTG-XX
*DATE: DD/MM/YYYY
*SPLICES COMPLETED TODAY: N
*RMU COMPLETED: N
*MATE/MASK COMPLETED: N
*TOTAL SPLICES / TERMINATIONS TESTED: N
*MARKED ON DRAWING (Y/N): Y/N
*AC → LC CONNECTOR CHANGES: N
*CHALLENGES / DELAYS: text or No
*PHOTOS ATTACHED (Y/N): Y/N
```
