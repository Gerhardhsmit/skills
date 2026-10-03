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
- **Email path:** drafts belong in Outlook under gerhard@cttx.co.za. Use the EXISTING loader —
  "Load CTTX Drafts" (`outbound-communication/load_drafts.py`, Gerhardhsmit/cttx-infrastructure-intelligence),
  which loads `.eml` files from `Desktop\CTTX Prospect Drafts` into Drafts and never sends. The engine
  writes each draft with `lib/write_eml.py` (loader naming + `X-CTTX-Attach` header) and hands the `.eml` +
  brief PDF to Gerhard — never commits them to a public repo. Until a draft is seen under
  gerhard@cttx.co.za → Drafts, report **EMAIL INTEGRATION NOT VERIFIED**.
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

## Step 0 — Reply desk and reconciliation (ALWAYS FIRST — before any new research)
Work every live reply with `references/win-patterns.md` — especially "we already have X" replies.
Live conversations beat new names. The first live run (3 Oct 2026) found 7 replies to the 25–28 Sep
wave sitting unanswered while the pipeline still showed those prospects as "Not Contacted", and the
engine re-researched a warm lead (Buffalo Kloof) as if it were cold. Never again:
1. **Reply desk.** Gmail: `newer_than:14d -from:gerhard@cttx.co.za` threads whose first message is from
   gerhard@cttx.co.za (Gerhard cc's himself, so his sends are visible). For every thread where the
   prospect spoke last: summarise what they asked, draft the reply (DRAFT only — answer their actual
   question, give one concrete next step), and list it at the top of the run report as **Live
   conversations**. A meeting already offered outranks everything else in the report.
2. **Reconcile stages.** Every sent thread → the prospect's pipeline row gets `Stage` = Contacted
   (or Replied if they answered) and `Last Contact` = the date. This is the one case where the engine
   moves Stage, because the evidence is in the mailbox. Write the domains into `contacted.txt`.
3. **Duplicate-send check.** Two identical sends to one address within minutes → flag in the report
   (it means an outbound worker double-fired); never draft a third.
4. Only then go to Step 1, passing `--contacted contacted.txt` so warm prospects are never re-pitched cold.

## Step 1 — Select the batch
1. Query CTTX Pipeline (data source `collection://e2cdd4da-b824-4188-9f31-24365a3c8e0c`):
   `Province IN ('Eastern Cape','Western Cape') AND Stage = 'Not Contacted'` plus rows whose
   `Next Action Date` ≤ today.
2. Save the rows as JSON and run `python3 lib/batch_rank.py rows.json --size 5 --contacted contacted.txt`
   (domains or company names already in a Gmail thread are excluded and returned as `warm`) — it de-duplicates by
   normalised company name, skips placeholder rows ("TBC", generic segment rows such as
   "Gamtoos Valley Agricultural Operations"), and ranks by priority, named decision-maker, sector fit,
   evidence already on the row and EC/WC balance. Placeholder segment rows are returned separately as
   **prospecting tasks** (find the named businesses inside the segment), not as outreach targets.
3. Default batch: 5 prospects (3 Full discovery + 2 Screen). Gerhard can say "batch 10".

## Step 2 — Discover (per prospect)
Run `cttx-private-network-discovery-strategy` at **Full** tier: Phase 0 (Notion, Gmail, Drive for prior
contact) through Phase 8. **Phase 0 is a hard stop, not a formality:** search Gmail for the company
name, the domain, and every person's name/address before any research. Any hit → stop, return the
thread to the orchestrator as WARM, no cold draft. Workers must report "Phase 0: searched <queries>,
found <n> threads" in their return. Parallelise prospects with sub-agents when available; each worker gets one
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

**Desk-study rule (added 3 Oct 2026 after a brief claimed a valley backbone with no terrain
check).** Before the brief describes ANY route, hub, relay or "joins site A to site B":
1. Get pins for every site named (published coordinates, ≥1 source each; mark ASSUMED where estimated).
2. Run `python3 lib/terrain_screen.py sites.json` (AWS terrain tiles, reachable from cloud sessions) and,
   for any BLOCKED site, `--relay <site> --to <a>,<b>` to look for high ground.
3. The brief may only describe what the screen supports, in screen language: "a terrain screen of public
   elevation data suggests the main dairy needs a hilltop relay; the two southern dairies look clear". Never "line of
   sight confirmed", never a route the screen shows BLOCKED, never a site with no pin.
4. No pins / screen not run → the brief describes the business problem and offers the desk study as the
   next step; it does NOT draw a backbone. Gate item 7 (hypothesis) fails if a route is claimed unscreened.
5. Record the screen table in the Discovery Record (internal) with assumed heights and frequency.

**Large sites: the link plan IS part of the first proposal (Gerhard, 3 Oct 2026).** A prospect is LARGE
when it has 3 or more sites to join, or sites more than 3 km apart (multi-dairy hubs, estates with
several farms, reserves with several lodges, plantations, wind farms). For a large site:
1. Build `plan.json` (sites with pins and assumed mast heights, hops with roles: carrier option /
   backbone / backup) and run `python3 lib/terrain_screen.py plan.json --plan <out>`. Iterate:
   blocked hop → `--relay` search → re-plan, until every backbone hop is CLEAR with ≥ 20 dB fade
   margin (use `"radio": {"gain_dbi": 29}` for a 2 ft dish on long hops).
2. The brief gets a **Link plan page** (map, hop table with km/azimuth/mast/Fresnel/fade margin) and a
   **Terrain profiles page**, from `plan_files()` output. Model: the MTO hop-by-hop plan that won the PO.
3. The plan states its limits on the page: public elevation data, planning-class radios, pins marked
   estimated, relay sites "candidate — field verify", hubs not yet studied.
4. Send `links.kml` with the draft (Abel's LINKPlanner and the client's Google Earth both open it).
5. A large site with no pins for its main sites FAILS the gate: research the pins (listings, Maps,
   company pages, satellite) — never send a large-site brief without its link plan.

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
| `lib/terrain_screen.py` | Desk-study terrain/Fresnel screen + relay search (stdlib, AWS terrain tiles) |
| `lib/write_eml.py` | Draft → `.eml` in the existing Load CTTX Drafts loader's convention |
| `references/win-patterns.md` | How CTTX deals actually advance (MTO, Kwandwe) — the moves the engine must enable |
| `tests/test_engine.py` | Offline tests for both libs (`python3 tests/test_engine.py`) |
