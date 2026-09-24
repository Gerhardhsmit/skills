---
name: link-assessment-architect
description: CTTX Link & Assessment Architect. Turns a customer request (Outlook email, website form, pin drop, coordinates, Google Maps/Earth link, property/farm/reserve/wind/solar/mine name) into an evidence-backed preliminary feasibility assessment. It covers business drivers, property location, infrastructure discovery (OSM + OpenCelliD + Google Earth KML), terrain/Fresnel analysis, minimum-hop relay routing, link budgets, a confidence split, field verification and the commercial opportunity, and ends with delivery to the client's mailbox. Use for "link planner", "site assessment", "can we get connectivity to…", "nearest tower/mast", "backhaul", "LOS", "Fresnel", "100 Mbps to a remote site", any new connectivity enquiry, or "assessment for <prospect>".
---

# CTTX Link & Assessment Architect

Specifications (binding): `reference/spec-v1.0.md` (discovery, site confidence, test and acceptance) and `reference/spec-v1.0-solution-architect.md` (evidence labels, the §14 output, graph edge classes, mast-location, technology, layers, redundancy and assessment pricing). The solution-architect edition governs wherever the two overlap. This file is the operating procedure.

**Evidence labels, used on every statement:** VERIFIED · SOURCE-DERIVED · CALCULATED · INFERRED · ASSUMED · UNKNOWN · FIELD VERIFY. **Graph edges:** VERIFIED / PROBABLE / CANDIDATE / UNKNOWN (and REJECTED, with its evidence).
**IMPLEMENT → EXECUTE → VERIFY → REPORT.** Do the work. Don't describe what you would do.

Engine: `lib/architect.py` (discovery → terrain → hop graph → link budgets → report + evidence register).
Customer jobs live in `projects/<slug>/`. Cross-project knowledge lives in `data/intelligence-graph.json`.

```
A=.claude/skills/link-assessment-architect/lib/architect.py
python3 $A init  <slug> --email projects/<slug>/email.txt [--location "<coords|maps link>"]
python3 $A run   <slug>          # live sources
python3 $A learn <slug>          # after field verification
python3 .claude/skills/link-assessment-architect/tests/test_scenarios.py   # Test Mode (§28)
```

## Step 1 — Intake (the customer, before the network)
1. **Get the request.** For Outlook, use the Microsoft 365 connector (`outlook_email_search`, then `read_resource`) and find the enquiry and any replies. For Gmail, use `search_threads`/`get_thread`. Save the raw text to `projects/<slug>/email.txt`. For a website form or pin drop, save what arrived.
2. Run `init`. It creates `input.json` with a draft driver chain (from `lib/drivers.py`), any Mbps figure it finds and any coordinates it can parse (decimal, DMS, Google Maps/Earth URLs).
3. **You** then complete `input.json → customer` from the customer's own words:
   - `context`: company, property, industry, sites/buildings, existing connectivity/provider, requested service, symmetry, reliability, growth, deadline, budget, pain points.
   - `drivers`: keep, edit or add chains of **driver → operational → network → solution**. Set `stated: true` only when the customer said it. Delete drivers that clearly don't apply.
   - `requirement.because`: the reason behind the number ("100 Mbps *because* cloud accounting, VoIP and CCTV drop on LTE…"). Also fill `architecture` (internet vs site-to-site vs private network vs multi-building), `availability` and `latency`.
   - `area`: `urban | suburban | rural | remote`. This drives the adaptive search radius (2→10 km up to 5→60 km).
   - `extra_sites`: other lodges, buildings or WTG O&M points that need distribution links.
   - `property.features`: the customer's buildings, gates, pumps, boreholes, workshops and high points (`{name, kind, lat, lon}`). Leave `lat` null when it's unknown; the report then lists it as an information gap.
   - `known_facts`: facts from correspondence (`{claim, source, date, confidence, kind: property|fibre|carrier|coverage|infrastructure|requirement, status}`). A carrier's written statement is **SOURCE-DERIVED**. Only CTTX's own confirmation is **VERIFIED**.
   - `known_infrastructure`: towers, fibre POPs, exchanges, data centres or CTTX sites you have coordinates for (`{name, kind: carrier_mast|fibre_pop|exchange|datacentre|cttx, lat, lon, height_m, source, status}`). These become routing targets.
   - `summary`, `field_checks`, `risks`, `commercial`: write these in plain language once the engine has run.
   Don't ask the customer anything that the email, maps or tools can answer.

## Step 2 — Property
- Coordinates from the customer are best: `property.query` = pin, DMS or a Maps link.
- Name only: the engine geocodes it (Nominatim). If there are several matches, it's flagged "confirm pin with customer".
- A customer KML/KMZ boundary or Google Earth pins go in `inputs.kml` (the engine reads Placemarks). No boundary means it's labelled `BOUNDARY APPROXIMATION`.

## Step 3 — Execute
Run `python3 $A run <slug>`. The engine does all of this and records every source call in the source log:
- **Discovery** in expanding radii. It queries OSM (masts, towers, `telecom=*`, peaks and hills, water towers, silos, primary/trunk roads, rail, power lines, substations), OpenCelliD (the `OPENCELLID_KEY` env var, or a cached country CSV `655.csv.gz` in `inputs.cell_csv`), user KML/CSV pins, the intelligence graph, and DEM local maxima as high-ground relays. It stops once there is a viable route plus an alternative, or immediately in dense areas.
- **Confidence classes.** CONFIRMED only when field-verified (intel graph, or a user pin with `verified`). PROBABLE when a mapped structure is present, or ≥ 3 cells on ≥ 2 radio technologies. CELL LOCATION ONLY for a lone cell observation. Cells within 300 m are clustered into one probable site, and mapped structures within 500 m absorb them (marked cross-checked). Vodacom is prioritised as the carrier POP. Backhaul evidence (multiple operators, a mapped structure, a trunk road within 2 km, a substation) is listed, never assumed.
- **Terrain** for every candidate from the property and for every hop. Terrain comes from DEM profiles (Open-Meteo Copernicus, falling back to OpenTopoData SRTM) with k = 4/3 earth bulge and 60 % first-Fresnel clearance. Each link gets one verdict: CLEAR, CLEAR WITH TALLER MASTS (with the heights needed), MARGINAL or BLOCKED (how many metres and where). With no DEM the verdict is UNVERIFIED, and LOS is never assumed.
- **Hop graph.** Nodes are the property, carrier candidates, relays and extra sites. Dijkstra costs each hop at 10 km-equivalent plus distance, with penalties for taller masts, new relay sites and unverified terrain, and a target penalty by confidence (a Vodacom site gets a bonus). The result is the primary route with the fewest practical hops, an alternative that avoids the primary's carrier, and multi-site distribution routes.
- **Link budget** per hop, using the first planning class in `lib/equipment-library.json` that reaches ≥ 20 dB fade margin. These classes are **desk defaults, not datasheets**, so they're reported as INFERRED. When authoritative Cambium LINKPlanner profiles are available, put them into the library with `verified: true`.

The engine also produces:
- **The infrastructure graph**, with every analysed edge classified.
- **The mast-location engine**: every candidate relay gets coordinates, elevation and height relative to the property, distances, CALCULATED visibility to the property and its two nearest carrier sites, access (mapped roads), power (mapped lines and substations), ownership (UNKNOWN), the reason it was chosen and the label *Candidate mast position — requires field verification*.
- **Link engineering** per hop: FSPL, EIRP, received level and fade margin (CALCULATED from ASSUMED planning classes). Rain is negligible below 10 GHz; above that, the ITU calculation is required and the value is UNKNOWN. Interference stays UNKNOWN until a spectrum scan. Modulation and throughput are **not estimated** without manufacturer profiles.
- **Technology options**, driven by the requirement: fibre, carrier services, 60 GHz, E-band, 5 GHz PtP, licensed microwave (for SCADA, production or safety only), PMP, Wi-Fi and LEO.
- **The six network layers** (physical → management) and **redundancy tied to named failure modes**. It only recommends redundancy when there is a critical driver or an availability target.
- **The assessment band** within R7,500–R25,000, built from sites, hops, relays, terrain, remoteness and missing routes. Simple carrier-fibre cases are marked "paid assessment not justified".
- **The §17 architect checklist.**

## Step 4 — Verify (before anything leaves)
Read `projects/<slug>/assessment.md` and check it against the spec:
- Every factual claim has an evidence row. Nothing CELL LOCATION ONLY is called a mast. No "Vodacom will provide backhaul".
- Each failed source is named in the summary, and confidence is lowered to match.
- If there's no route, look at the rejected-path evidence. Add known high points or structures (KML/CSV) or raise `params.max_hops`, then re-run. The engine already expands the radius and searches relays automatically.
- Use Google Earth/Maps and the imagery in the customer's email to sanity-check the top candidates. CellMapper is **reference only**: label it `REFERENCE / VISUAL VERIFICATION` and never feed it into the engine.
- Write the executive summary in plain language in §1 of the report. Add the architecture (what the customer's network could look like) from `requirement.architecture`.

## Step 5 — Report and deliver
- In chat: status, the route line (PROPERTY → … → CARRIER), the confidence split, the top 3 field checks and the recommended sale (the assessment first).
- The client-facing version goes through the `infrastructure-project-quoting-estimation` skill for assessment and infrastructure pricing, and becomes a PDF (`pdf` skill).
- Create a draft to the client (Outlook `outlook_create_draft` or Gmail `create_draft`). **Send only when Gerhard says "send".**

## Step 6 — Learn (§30)
Every `run` logs desk results (unverified, deduplicated) to `data/intelligence-graph.json`: carrier sites, relay candidates, rejected relay-to-carrier links, source reliability, and an assessment record (industry, drivers, requirement, architecture, hop distances, equipment classes, assessment band). Links to customer locations stay in the project folder. The knowledge base is **git-ignored while the repo is public**. After the site visit, write `projects/<slug>/field-verification.json`:
```json
{"date": "YYYY-MM-DD",
 "nodes": [{"name": "Vodacom Kareedouw", "lat": -33.9, "lon": 24.3, "kind": "carrier", "operator": "Vodacom", "height_m": 45}],
 "rejected_links": [{"a": "PROPERTY", "b": "C2", "reason": "blue-gum plantation 25 m at 3 km"}],
 "verified_routes": [{"nodes": ["..."], "equipment": "PTP 670 + 2ft", "rx_dbm": -52}],
 "commercial_outcome": "assessment sold R12 500", "findings": "blue-gums 25 m on bearing 312°"}
```
Then run `learn <slug>`. Verified nodes come back as CONFIRMED in every future assessment nearby.

## Never
Invent coordinates, heights, fibre, ownership, backhaul or LOS. Never treat a cell as a tower, coverage as backhaul, or a desktop result as final feasibility. Never bury uncertainty. Never stop at a plan.
