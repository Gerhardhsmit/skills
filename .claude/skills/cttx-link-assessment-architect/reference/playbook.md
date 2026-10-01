# Operations playbook — what was learned on real CTTX jobs

Read the relevant section when a step stalls. These are field-tested lessons, not theory.

## 1. Where the information actually is
See `private-casebook.md` (shipped only in the private skill package): mailboxes, lead sources, carrier and supplier contacts.

## 2. Getting attachments out of Gmail
`get_thread`/`get_message` show attachment metadata but there is no download tool. Use `get_message(messageFormat="RAW")`; the result is too big for context and is saved to a file — base64url-decode `raw`, parse with `email.message_from_bytes`, and write every part that has a filename. Works for KMZ, LPP, PDF invoices, CSVs.

## 3. Cambium LINKPlanner `.lpp`
A `.lpp` is a **bzip2-compressed SQLite database** (tables: places, subscriber_places, hubs, access_points, subscribers, profiles, project…). `lib/lpp.py` imports it: APs (product, height, azimuth, tilt, beamwidth), subscribers (equipment, LINKPlanner verdict + error flags, per-SM AP gain and elevation), and terrain+clutter profiles (`ranges`, `heights`, `file_clutter` codes → `clutter_dict` heights). Typical design faults it exposes:
- **Default clutter** (e.g. 'D' Deciduous Forest 15 m) on every path point including at 10 m CPEs → links fail on modelled trees. Measure real tree heights.
- **AP tilt 0° on a hill** — subscribers 10° below get ~9–12 dB less antenna gain (visible as per-SM `ap_antenna_gain`).
- **Sector edge** — subscribers ±50–60° off a 120° sector.
- **PMP at 50–200 m** → "Receive level"/"Outside of range"; use cable/60 GHz/Wi-Fi instead.
A `.kmz` exported by LINKPlanner duplicates the sites and profiles.

## 4. The CTTX mast dataset
Two carrier KMZs (Vodacom-sourced, **confidential**):
- `BTS Site Location Report.csv.kmz` — ~14,439 placemarks: ATOLL_NAME, ATOLL_SITE_ID (e.g. LIM_15621), LATITUDE/LONGITUDE, SERVICE_LEVEL (BRONZE/SILVER/GOLD/PLATINUM), BS_NUMBER.
- `Afrigis New BTS Sites List 26 November 2024.kmz` — 1,465 sites with Site Owner, Backhaul (Fibre Ring / Fibre Not-Ring / MW Ring / MW Not-Ring), POC Type, Location type, Radwin PtP/sectors, CBNL, SIAE links, availability. Decimal commas in lat/lon.
`lib/masts.py build` merges them by Atoll ID → ~13,831 unique sites. Every record is **HISTORICAL**. Never put carrier names/site IDs in customer emails; say "a known infrastructure point ~X km NNE". Pattern seen: rural areas have BRONZE access sites within 10–20 km while POC/fibre-ring sites sit 50–80 km out in towns.

## 5. Environment constraints (Claude Code cloud sessions)
The default network policy blocked `overpass-api.de`, `nominatim.openstreetmap.org`, `api.open-meteo.com`, `api.opentopodata.org`, `opencellid.org`, `openstreetmap.org`, `mapcarta.com` and many lodge websites (WebFetch too). **WebSearch works** — use targeted searches to extract coordinates/contacts. To unlock terrain: allow those hosts in the environment's network settings, set `OPENCELLID_KEY`, or route terrain through Abel's LINKPlanner using `linkplanner_candidates.csv`. When blocked, the engine logs every failure and claims nothing.

## 6. Commercial facts, case notes and safety lessons
See `private-casebook.md` §6–8: current assessment prices, signature, real case patterns (urban fibre, lodge Wi-Fi rationalisation, cold outreach), and the rules that bit us.
