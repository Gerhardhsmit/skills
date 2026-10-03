# Network design composer — carrier link + client-owned private backbone

Purpose: turn a Discovery Record into a **customer-specific network concept** an owner can picture,
without claiming feasibility. The concept is built from THEIR assets and THEIR losses, found in discovery.
It is never copied from another client or a sector template.

Feasibility (terrain, LOS, Fresnel, capacity, power, mast heights) comes later in the paid assessment via
`cttx-link-assessment-architect`. Pricing only via `infrastructure-project-quoting-estimation`.

## Layer 0 — Inventory (from discovery, every item sourced)
List each place where value is made, stored, moved or lost:

| # | Site / asset | Where (coords if known) | Who works there / when | What can go wrong | Source |
|---|---|---|---|---|---|

Typical asset *types* to look for (look, don't assume): offices, packhouses, cold/CA rooms, processing
plants, workshops, fuel and chemical stores, pump stations, boreholes, dams, reservoirs, pans, pivots,
gates and fences, lodges and staff villages, camps, hides, substations, turbines/inverters, weighbridges,
loading bays, vehicles, remote outposts. Skip any type with no evidence for this prospect.

## Layer 1 — Carrier (the dedicated link into the property)
- **Landing point:** the building where operations are coordinated (from discovery), not "the farm".
- **Primary:** dedicated carrier-grade link (CTTX arranges the carrier service — e.g. via the Vodacom
  reseller channel or fibre where it reaches) — capacity sized to their systems, stated as a range to confirm.
- **Resilience:** second path (second carrier, LTE/5G failover or a diverse radio route) where an outage
  costs money (export cut-off, guest arrival, SCADA, security). State the failure it protects against.
- **Nearby infrastructure:** from the CTTX mast dataset / property intelligence, written as "a known
  infrastructure point about X km <bearing>" — HISTORICAL, field verify. No carrier names, no LOS claim.

## Layer 2 — Private backbone (client-owned)
Topology chosen from the geography found, as a hypothesis:
- **Single site** — one campus; fibre/short radio inside.
- **Hub and spoke** — central office/packhouse hub, PtP/PtMP to outlying sites.
- **Ring / dual-homed** — where one failure must not cut critical sites (e.g. flood-exposed valley floor:
  place relays on high ground, keep a path that avoids the flood line).
- **Relay chain** — long, narrow properties or valleys; off-grid solar relays with battery telemetry.
- **Cluster** — several neighbouring farms/reserves sharing a high site (neutral-host angle).

## Layer 3 — Services per asset (what rides the backbone)
| Asset | Services | Business outcome | ROI lens | Magnitude (sourced or UNKNOWN) |
|---|---|---|---|---|
Services vocabulary: telemetry/SCADA (pumps, levels, power, cold-room temperature), CCTV and analytics,
access control and gate/fence alarms, VoIP/radio-over-IP, LoRaWAN gateways for sensors, ERP/packhouse
systems, guest/staff Wi-Fi, vehicle/asset tracking, remote management of plant.

ROI lenses (exactly these four): **Avoided Loss · Operational Efficiency · Infrastructure Ownership ·
Executive Risk Reduction**.

## Layer 4 — Ownership and support
The backbone is the client's asset; CTTX designs, builds, monitors (NOC: radio + power) and supports it
under SLA. Phrase in their terms: "your network, on your property, carrying your operations".

## Cost of Disconnection vs Value of Connected Operations
Every concept ends with this section, titled exactly so:
- **Cost of disconnection** — what one missed window / one incident / one day of blindness costs THIS
  business (sourced figures or the calculation from sourced inputs; otherwise "to confirm in assessment").
- **Value of connected operations** — the outcomes above, by lens.
- Formula reminder: avoided losses + operational savings + improved response capability +
  infrastructure asset value + future expansion potential.

## Output block for the Discovery Record
```markdown
## Network concept — carrier + private backbone (CONCEPT, not a design — field verify)
**Landing point:** … **Primary carrier:** … **Resilience:** … (protects against …)
**Backbone topology:** … because …
| Asset | Services | Outcome | Lens |
|---|---|---|---|
**Owned & supported:** …
### Cost of Disconnection vs Value of Connected Operations
…
**What the paid assessment will verify:** terrain/LOS per hop, mast/relay positions, power, capacity, cost.
```

## Quality bar
If you could paste the concept into another prospect's record by changing the name, it fails. Each row
must point to an asset found in this prospect's research.
