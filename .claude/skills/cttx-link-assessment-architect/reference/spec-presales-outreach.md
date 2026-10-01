# CTTX Property Intelligence + Personalised Assessment Outreach — specification

> Issued by Gerhard Smit. Governs every first-contact email to a property owner, lodge, reserve, farm, industrial site or infrastructure project. Works with `spec-v1.0.md` (assessment engine) and `spec-v1.0-solution-architect.md` (evidence labels, output).

## Principle
STOP GENERATING GENERIC ASSESSMENT EMAILS. Every important first contact must feel like *"CTTX has already looked at YOUR property"*, not *"CTTX offers connectivity assessments"*. The email is the **final output of the intelligence**, never the starting point.

## Sequence (the future "Assess <property>" workflow)
1. Identify the property (resolve similar names; never assume the first search result).
2. Geocode it — coordinates from ≥2 independent sources where practical. Never invent coordinates.
3. Query the CTTX mast dataset (~14,000 historical sites).
4. Find candidate sites — **not just the nearest**: distance, bearing, elevation, terrain, LOS, obstructions, relative height, potential path, relay requirement. A mast 8 km away behind a mountain may be useless; one 15 km away on a ridge may be excellent.
5. Analyse terrain (property elevation, candidate elevation, profile, ridges, valleys, obstructions, LOS, path geometry). If a proper RF/LOS calculation can't be done, DO NOT PRETEND — say "Preliminary geographic screening suggests…" and state what still needs formal assessment.
6. Use the existing CTTX Link Planner where it works; do not build another planner. Record exactly what was and was not verified.
7. Research the property: location, nearest town, province, size, lodge position, units, operations, existing connectivity, telecom clues, website, contacts, management/owner.
8. Identify business context and likely needs — the property's telecommunications **backbone**, not just "internet": hospitality (guest Wi-Fi, staff, POS/booking, VoIP, admin), operations (management systems, inter-site, telemetry, IoT, remote access), security (CCTV, perimeter, access control, remote cameras, ranger comms), property (buildings, staff housing, camps, gates, workshops, remote facilities).
9. Opportunity hypothesis — could the property be a SINGLE-SITE solution, a HUB, part of a PROPERTY CLUSTER, a RELAY or a PRIVATE NETWORK NODE? Only claim what the evidence supports.
10. Generate the personalised approach; present the evidence to Gerhard; prepare the email; obtain approval; send through the approved Microsoft 365 channel; record receipt; schedule follow-up.

## Historical mast data
Classify every candidate: **VERIFIED CURRENT** (current evidence confirms it) · **HISTORICAL** (in the CTTX dataset, current status unknown) · **CANDIDATE** (potential point needing field verification). Never tell a customer "there is a working mast here" unless verified. Say: *"Our preliminary desktop review identified a historical/known infrastructure point approximately X km from the property…"*.

## Writing the email
- Contains evidence CTTX has actually looked at the property; wording must come from the evidence. Do not fabricate technical conclusions.
- Do NOT give away the engineering study — the preliminary intelligence creates curiosity and credibility; the paid assessment does terrain, RF design, path analysis, architecture, equipment, implementation, costing, resilience.
- CTA specific and matched to the sales process (e.g. a short call to show the preliminary review and decide whether a formal assessment is worthwhile) — never "please let us know if you are interested".
- Banned: "leading provider", "cutting-edge", "seamless connectivity", "revolutionary", "best-in-class", "we specialise in…", generic paragraphs about CTTX.
- Tone: intelligent, concise, technically credible, commercial, human, South African, direct — "I looked at your property and noticed something interesting."
- Use the decision-maker's name when known. With only a generic info address, don't pretend to know the recipient — write so it can be forwarded internally ("I am trying to reach whoever looks after telecommunications/infrastructure for…").

## Internal Property Intelligence record (before the email)
Property, coordinates and sources, contact, infrastructure candidates, terrain screening, business context, likely needs, hypothesis, evidence, gate result. Internal — not sent.

## Personalisation score
At least **3 genuine, sourced, property-specific facts** (location, nearby infrastructure, terrain characteristic, operational characteristic, likely requirement, business context). 0–1 facts → DO NOT SEND; improve the research.

## Quality gate (all critical answers must be YES, else DO NOT SEND)
PROPERTY CORRECT · CONTACT CORRECT · LOCATION VERIFIED · INFRASTRUCTURE ANALYSED · TERRAIN CHECKED · FACTS SOURCED · NO INVENTED CLAIMS · PERSONALISATION ≥ 3 FACTS · CTA CLEAR · ASSESSMENT POSITIONING CORRECT.

## Final rule
Never send a generic CTTX assessment email when enough property intelligence exists to personalise it. KNOW THE PROPERTY. KNOW THE TERRAIN. KNOW THE INFRASTRUCTURE. KNOW THE BUSINESS. KNOW THE PERSON. THEN WRITE.
