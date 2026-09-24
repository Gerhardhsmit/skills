---
name: parse-site-report
description: Parse OYA Wind Farm WhatsApp daily fibre site reports (WTG-01 to WTG-18), update data/progress.json and show the dashboard. Use when Gerhard pastes WhatsApp report text containing "TURBINE NUMBER", "SPLICES COMPLETED TODAY", or says "log these reports" / "update the tracker".
---

# /parse-site-report

The one thing you do here is **extract**. The script handles the merge rules, totals and dashboard. Don't do those by hand.

## Step 1 — Extract

From the pasted WhatsApp text (ignore timestamps, sender prefixes, forwarded noise, chatter), pull every report block:

`TURBINE NUMBER, DATE, SPLICES COMPLETED TODAY, RMU COMPLETED, MATE/MASK COMPLETED, TOTAL SPLICES / TERMINATIONS TESTED, MARKED ON DRAWING (Y/N), AC → LC CONNECTOR CHANGES, CHALLENGES / DELAYS, PHOTOS ATTACHED (Y/N)`

Map each one to this JSON. Put a suffix like "(Basement)" into `location`. Use the WhatsApp sender name if you can see it.

```json
[{"wtg": "WTG-09", "date": "10/06/2026", "location": "Basement", "splices": 20, "rmu": 0, "mate_mask": 0,
  "tested": 0, "drawing": false, "ac_lc": 10, "challenges": "No", "photos": true, "sender": "Freddy"}]
```

## Step 2 — Merge and show the dashboard (one command)

```
python3 .claude/skills/site-dashboard/oya.py add - <<'JSON'
[ ...extracted reports... ]
JSON
```

The script normalises WTG numbers and dates, de-duplicates (same WTG + date + location keeps the higher splice count), updates the totals, tested, RMU, mate/mask, drawing and challenge flags, writes `data/progress.json` and prints the dashboard.

## Step 3 — Reply

Paste the dashboard output. Then add at most three lines: what was logged, anything odd in the input (a missing field, an unreadable turbine number), and the top action item.
