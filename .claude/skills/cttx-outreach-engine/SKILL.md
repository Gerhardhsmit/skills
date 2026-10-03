---
name: cttx-outreach-engine
description: "CTTX Sales manager's autonomous outreach engine for the Eastern Cape and Western Cape: picks the next batch from CTTX Pipeline, runs business-first discovery on each prospect, finds the owner/director email, composes a customer-specific private network + carrier design concept, builds the SIGNAL brief and an owner-level outreach DRAFT, logs everything in Notion and feeds anonymised insight to Marketing (Buffer). Use when Gerhard says 'run the outreach engine', 'next batch', 'work the pipeline', 'EC/WC outreach', 'find owner emails', 'daily sales run', or when the scheduled Routine fires. Orchestrates existing skills; never replaces them."
---

# CTTX Outreach Engine (Sales manager orchestration)

This is the Sales manager's loop, not a new method. It sequences the skills Gerhard already built so a
batch of real prospects moves from **Not Contacted → researched → owner located → designed → drafted**
without Gerhard routing each step.

```
CTTX Pipeline (Notion)  ──► 1 SELECT batch (lib/batch_rank.py)
                        ──► 2 DISCOVER each prospect   = cttx-private-network-discovery-strategy (Full tier)
                        ──► 3 LOCATE the owner         = references/owner-contact-playbook.md (+ lib/contact_finder.py)
                        ──► 4 DESIGN the concept       = references/network-design-composer.md
                                                         (+ cttx-link-assessment-architect Mode B for masts/terrain)
                        ──► 5 GATE (9 items) ── FAIL → back to research, gaps logged
                        ──► 6 PACKAGE on PASS          = SIGNAL brief (PDF) + short owner email DRAFT
                        ──► 7 RECORD in Notion         = pipeline row + Discovery Record page
                        ──► 8 FEED Marketing           = anonymised insight idea to Buffer (never a client name)
                        ──► 9 REPORT                   = one table + "Next action"
```

## Binding rules (from the CTTX Global Command — not negotiable here)
- **Research each prospect as itself.** Batch mode never means template mode. Each prospect gets its own
  discovery; sector skills are toolsets selected after discovery.
- **Draft only. Gerhard sends.** The engine never sends email and never asks to.
- **Email path:** drafts belong in Outlook under gerhard@cttx.co.za. From a cloud session this cannot be
  reached, so drafts are written as files + JSON and pushed into Outlook on Gerhard's PC with
  `tools/push_outlook_drafts.ps1` (Outlook COM, creates drafts, never sends). Until that has run and the
  draft is seen under gerhard@cttx.co.za → Drafts, report **EMAIL INTEGRATION NOT VERIFIED**.
  A Gmail draft is not a CTTX draft; do not create one as a substitute.
- **Public repo:** this skill lives in a public GitHub repo. Prospect data, emails, records and briefs
  never go into the repo — only into Notion and the session scratchpad.
- **One source of truth:** CTTX Pipeline. Update the existing row; never create a parallel list.
  Duplicate rows found → flag them in the report, don't silently pick one.
- **POPIA:** business contact data only, every source recorded, opt-out line in every email,
  POPI Consent/Consent Source fields filled honestly (a cold researched approach has no consent yet —
  leave the box unticked and say so).
- **Apollo credits are finite.** Free people *search* first; spend reveal credits only on the single best
  decision-maker of a prospect whose gate already passes. Default cap: 2 per prospect, 10 per run.
  Surface every spend (estimated, actual, new balance).

## Step 1 — Select the batch
1. Query CTTX Pipeline (data source `collection://e2cdd4da-b824-4188-9f31-24365a3c8e0c`):
   `Province IN ('Eastern Cape','Western Cape') AND Stage = 'Not Contacted'` plus rows whose
   `Next Action Date` ≤ today.
2. Save the rows as JSON and run `python3 lib/batch_rank.py rows.json --size 5` — it de-duplicates by
   normalised company name, skips placeholder rows ("TBC", generic segment rows such as
   "Gamtoos Valley Agricultural Operations"), and ranks by priority, named decision-maker, sector fit,
   evidence already on the row and EC/WC balance. Placeholder segment rows are returned separately as
   **prospecting tasks** (find the named businesses inside the segment), not as outreach targets.
3. Default batch: 5 prospects (3 Full discovery + 2 Screen). Gerhard can say "batch 10".

## Step 2 — Discover (per prospect)
Run `cttx-private-network-discovery-strategy` at **Full** tier: Phase 0 (Notion, Gmail, Drive for prior
contact) through Phase 8. Parallelise prospects with sub-agents when available; each worker gets one
prospect and the rules above. Prior contact found in Phase 0 changes the draft — never cold-pitch a
warm relationship.

**Cloud-session lesson (first run, 3 Oct 2026):** the cloud egress proxy blocks direct fetches of most
company websites and trade press, so workers rely on search-result extracts. That is acceptable for
discovery, but every draft must carry a "re-open these source pages before sending" note listing the
URLs behind any figure quoted to the client. Apollo "verified" on a catch-all domain counts as
INFERRED (the draft JSON gets `email_status: INFERRED`, which prefixes "[VERIFY ADDRESS]").

## Step 3 — Locate the owner (the bottleneck)
Follow `references/owner-contact-playbook.md` end to end. Record `contact.json` per prospect:
name, role, email, `email_status` (PUBLISHED / VERIFIED / INFERRED / NONE), every source, credits spent.
Use `python3 lib/contact_finder.py` to infer the domain's address pattern from published addresses and
rank candidate addresses for the named person. INFERRED addresses are labelled in the draft header.

## Step 4 — Design the concept
Follow `references/network-design-composer.md`: carrier layer → private backbone → per-asset services →
outcome and ROI lens → "Cost of Disconnection vs Value of Connected Operations". Use
`cttx-link-assessment-architect` Mode B (`lib/masts.py near <lat> <lon> 40`) where coordinates exist;
historical mast points are never called "working masts" and no LOS is claimed without terrain data.

## Step 5–6 — Gate and package
Run the nine-item Outreach Quality Gate. PASS → SIGNAL brief (`assets/signal-brief-template.html`
from the discovery skill, rendered to PDF with `/opt/pw-browsers/chromium` in cloud sessions) and a
short owner email. FAIL → no draft; list the gaps and the next research action.

## Step 7 — Record in Notion
On the existing pipeline row update: `Contact Person`, `Role`, `Email` (only PUBLISHED/VERIFIED, or
INFERRED with "INFERRED — verify" in Notes), `Pain Signal` (one sourced line), `Notes`
(fit verdict, gate n/9, hypothesis, email status, sources), `Next Action` ("Review draft + send from
Outlook" or the research gap), `Next Action Date`. Create the Discovery Record as a child page of the
row (or under 📈 Sales & Pipeline) and link it in Notes. Do not change `Stage` to Contacted — only
Gerhard's send does that.

## Step 8 — Feed Marketing (Buffer)
For each completed discovery, create one Buffer **idea** (never a scheduled post) via the Buffer
connector: an anonymised, sector-level insight ("Packhouses lose X when cold-room alarms reach no-one
after hours…") with no client name, location or identifiable detail. Marketing decides what posts.
Buffer is for LinkedIn content only — it is not an email-finding or outreach channel.

## Step 9 — Report
One table: Prospect · Tier · Fit · Gate · Decision-maker · Email status · Design headline · Draft ready? ·
Next action. Then: Apollo credits used/remaining, duplicates found, prospecting tasks raised,
EMAIL INTEGRATION status, and one line **Next action: …**.

## Files
| Path | Role |
|---|---|
| `references/owner-contact-playbook.md` | Ordered method to reach the owner/director, SA-specific sources |
| `references/network-design-composer.md` | Carrier + private backbone concept builder, per-asset outcome mapping |
| `references/cadence.md` | Daily/weekly loop, Routine prompt, follow-up sequence, KPIs |
| `lib/batch_rank.py` | Dedupe + rank pipeline rows into a batch |
| `lib/contact_finder.py` | Email pattern inference and candidate ranking (stdlib only) |
| `tools/push_outlook_drafts.ps1` | Gerhard's PC: create Outlook drafts in the CTTX account from draft JSON |
| `tests/test_engine.py` | Offline tests for both libs (`python3 tests/test_engine.py`) |
