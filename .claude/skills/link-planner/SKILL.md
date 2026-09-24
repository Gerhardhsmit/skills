---
name: link-planner
description: CTTX end-to-end wireless link planning — site assessment → link design → proposal → delivery to the client's mailbox → execution tracking. Use when Gerhard says "link planner", "plan a link", "PtP link", "backhaul", "site assessment", "link budget", "Fresnel", "tower to lodge", or asks to get a link proposal to a client.
---

# /link-planner

One pipeline, five stages. Every client job lives in `projects/<client-slug>/`.

```
projects/<client-slug>/
  link-plan.json        # sites + links (input to the calculator)
  assessment.md         # stage 1 output
  link-report.md        # stage 2 output (calculator + notes)
  proposal.md           # stage 3 output — the document the client receives
  status.json           # stage 5 tracker
```

## Stage 1 — Site assessment (intake)

Gather, from the user's message, emails, site photos, KMZ or Google Earth pins:

- Client name, contact name and email, site name
- Every site: name, lat/lon (decimal), ground elevation (m ASL), available mast/roof height, power (grid/solar), access
- The purpose of each link: required throughput (Mbps), latency, and SLA (e.g. SCADA, CCTV, guest Wi-Fi)
- Known obstructions along each path: ridges, tree lines, buildings, with distance from site A and height (m ASL)
- Regulatory band preference: 5 GHz licence-exempt (ICASA, EIRP ≤ 53 dBm for PtP on 5.725–5.875), 60 GHz, or licensed

If a field is missing, mark it `TBC` and list it under "Open items" in `assessment.md`. Don't invent coordinates or elevations.
Write `projects/<slug>/assessment.md` and `projects/<slug>/link-plan.json`. Use `example-project.json` in this folder for the schema.

## Stage 2 — Link design

Run:

```
python3 .claude/skills/link-planner/linkcalc.py projects/<slug>/link-plan.json > projects/<slug>/link-report.md
```

The calculator gives distance, azimuths, FSPL, 60 % F1 + earth-bulge (k=4/3) clearance, Rx level, fade margin and EIRP check.
For any link that fails, iterate. Raise the mast, use a bigger dish, add a repeater, or change the band. Update `link-plan.json` and re-run until every link passes, or explain why one can't pass.
Radio defaults are Cambium PTP 670/PTP 550 and ePMP Force 300/400 series, or Ubiquiti airFiber where the budget is tight.

## Stage 3 — Proposal

Invoke the `infrastructure-project-quoting-estimation` skill for ZAR pricing, BOM, margin, CAPEX and monthly recurring costs. Then write `projects/<slug>/proposal.md` with:

1. Executive summary (the problem, the solution, the price, and when it's done)
2. Site assessment summary and a map or link diagram
3. Link design table from `link-report.md`, in plain language
4. BOM and pricing (CAPEX + monthly)
5. Delivery plan: survey, install, alignment, test and handover, with dates
6. Assumptions, exclusions, validity (30 days) and acceptance

Render it to PDF (`pdf` skill) as `projects/<slug>/<Client>-Link-Proposal-<YYYY-MM-DD>.pdf`.

## Stage 4 — Delivery to the client's mailbox

- Use Gmail `create_draft` to the client contact. Subject: `<Site> — Wireless Link Proposal (CTTX)`. The body is a short cover note with three bullets (solution, price, timeline) and the PDF attached.
- **Always create a draft first and show it to Gerhard.** Send only after an explicit "send". Never send on inference.
- Once it's sent, record the date and message ID in `status.json` and create a Google Calendar follow-up 3 working days later.

## Stage 5 — Execution tracking

`status.json` stages: `assessment → designed → proposed → sent → accepted → installed → aligned → tested → handed_over`.
On each update from the user or field team, advance the stage, log the date and note, and record the achieved RSSI/SNR/throughput against the planned values in `link-report.md`. If the achieved Rx is more than 6 dB below plan, flag an alignment or obstruction problem.

## Output to chat

Keep the chat reply short: which stage you're at, the link table (PASS/FAIL), open items, and the next action you need from Gerhard.
