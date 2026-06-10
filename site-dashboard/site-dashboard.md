# site-dashboard

Show the current OYA Wind Farm fiber optic progress dashboard across all 18 turbines.

## Usage

```
/site-dashboard
```

## Instructions

Read `data/progress.json`. If it doesn't exist, tell the user no reports have been logged yet and suggest running `/parse-site-report`.

Display the full project dashboard:

```
OYA PROJECT — FIBER OPTIC PROGRESS DASHBOARD
=============================================
Last updated: [date]

WTG   | Splices | Tested | RMU | M/M | Drawing | AC→LC | Status
------|---------|--------|-----|-----|---------|-------|--------
...all 18 turbines...
```

For turbines with no data, show dashes and status `🔴 No report`.

Status logic:
- `✅ Complete` — splices > 0 AND tested >= splices AND drawing_marked == true
- `⚠ Untested` — splices > 0 but tested < splices
- `📋 Drawing pending` — splices > 0, tested >= splices, drawing_marked == false
- `🔴 No report` — no data

Summary section:
```
SUMMARY
-------
Total splices logged:     XXX
Total AC→LC changes:      XXX
Turbines with activity:   X/18
Turbines fully complete:  X/18
Turbines not started:     [list]

ACTION ITEMS
------------
⚠ Untested splices at: [list turbines]
📋 Drawings not marked: [list turbines]
🔴 No report received: [list turbines]
💬 Active challenges: [list turbine: challenge text]
```

Then show a recent activity log — the last 5 report entries received, sorted by date descending:
```
RECENT REPORTS
--------------
[date] WTG-09 — 20 splices, 10 AC→LC changes (Freddy)
[date] WTG-08 — 24 splices, 12 AC→LC changes
...
```
