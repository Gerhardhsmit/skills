# Site workup — executing a large site with precision

One command turns pins into the engineering that goes into the first proposal. Use it for every LARGE
site (3+ sites to join, or sites more than 3 km apart). Model: the MTO hop-by-hop plan that won the PO.

```bash
pip install -q rasterio pyproj mgrs pillow          # once per session (imagery only)
python3 lib/site_workup.py sites.json <out_dir>     # ~20 s for 4 sites
```
`sites.json` = `{"<name>": {"lat":..,"lon":..,"role":"hub|site|dairy|lodge|office|pump","status":"published|ESTIMATED"}}`.
The **hub** is where operations are run and the carrier should land.

## What it does (and writes, so a person can check every step)
| Step | Output | Rule |
|---|---|---|
| 1 Screen every pair at 12 m, retry 18 / 24 m | `screen.txt` | AWS terrain tiles, 5.8 GHz, k=4/3, CLEAR ≥ 0.6 F1 |
| 2 Relay search for any site that is blocked or needs tall masts | `screen.txt` | Grid search ≤ 5 km; prefers a crest that **also sees a carrier point**; reuses an existing relay first |
| 3 Backbone = minimum-cost tree | `plan.json` | Cost = km + 0.15 km per metre of mast above 12 m (+0.5 for a dish) |
| 4 Carrier handover | `carrier.json` (INTERNAL) | CTTX mast dataset (Vodacom-sourced, HISTORICAL) screened from every node; primary + diverse backup, ≥ 20 dB fade |
| 5 Brief pages | `plan.html`, `plan_out/links.kml` | Map, hop table (km, azimuth, mast, Fresnel, fade), terrain profile per hop |
| 6 Satellite views | `sat.png`, `sat_<relay>_zoom.png` | Sentinel-2 true colour, clearest scene in 90 days |
| Summary | `summary.json` | `unreached` must be empty and `all_hops_pass` true before a brief goes out |

## The hill is the opportunity
A ridge that blocks the valley route is usually the best asset on the property: one relay on it serves
the hidden site AND sees the carrier mast, replacing two tall masts. A multi-dairy hub (Oct 2026): the
ridge beside the largest site served the processing plant, two other sites and the carrier point from one 15 m relay.
Say it that way to the client: *"the hill between your sites is where your network should live."*

## Look at the relay before it goes in a proposal
**Cloud (automatic):** `sat_<relay>_zoom.png` at 10 m shows roads, wide tracks, dams, paddocks, pivots,
power-line corridors and bare crest. Record what you see in the Discovery Record.

**Google Earth Pro on the PC (sub-metre — Gerhard / Abel, 5 minutes per relay):** open `plan_out/links.kml`.
Use the historical imagery slider; tracks show best in dry months. For each relay crest, note:
1. **Cattle paths and farm tracks** reaching the crest. Cows walking up to graze mean vehicle or foot
   access exists and the farm uses (likely owns) that land.
2. **Fences and paddock lines.** Whose land is the crest on? Same owner as the sites = no lease.
3. **Power**: an Eskom line, a borehole pump or a reservoir near the crest. Otherwise plan solar.
4. **Existing structures** on the crest (reservoir, repeater, old mast) = a ready mounting point.
5. **Tree height** on the path. Bush on the slope can eat Fresnel clearance that bare-earth data misses.
6. **Move the pin** if a better spot is 100–300 m away on the track or the open crest, then re-run.

## What may be said to the client
- From the screen: "a terrain study of public elevation data shows…", "candidate relay — to be field verified".
- Never: "line of sight confirmed", carrier names or site IDs, a hop that is not CLEAR, sites without pins,
  hubs or regions that were not worked up.
- Every ESTIMATED pin is named on the page together with what it affects (e.g. "plant pin estimated;
  1 km east makes the relay hop marginal").

## Limits
Bare-earth DEM (no trees or buildings) · planning-class radios, not datasheets · historical mast points ·
10 m imagery. The paid assessment replaces each of these with LINKPlanner, real profiles and a site walk.
