# parse-site-report

Parse one or more OYA Project WhatsApp daily site reports and update the project tracker.

## Usage

```
/parse-site-report
```

Paste one or more WhatsApp report blocks when prompted, or pass them as the argument.

## Instructions

You are processing daily fiber optic site reports for the OYA Wind Farm project (WTG-01 to WTG-18).

### Step 1 — Extract reports from input

The user will paste raw WhatsApp chat text. It may contain multiple reports, chat noise, timestamps, sender names, and forwarded-message noise. Extract ONLY the structured report blocks. A report block contains these fields:

- TURBINE NUMBER
- DATE
- SPLICES COMPLETED TODAY
- RMU COMPLETED
- MATE/MASK COMPLETED
- TOTAL SPLICES / TERMINATIONS TESTED
- MARKED ON DRAWING (Y/N)
- AC → LC CONNECTOR CHANGES
- CHALLENGES / DELAYS
- PHOTOS ATTACHED (Y/N)

Normalize the turbine number: strip "WTG-", leading zeros, and location suffixes like "(Basement)" into a separate `location` field. Store as `WTG-XX` zero-padded to 2 digits (e.g. `WTG-09`).

### Step 2 — Update the tracker

Read the file `data/progress.json`. If it doesn't exist, create it with this structure:

```json
{
  "project": "OYA Wind Farm — Fiber Optic",
  "turbines": 18,
  "last_updated": "",
  "wtg": {}
}
```

For each parsed report, update `wtg["WTG-XX"]` as follows:
- Keep a `daily_reports` array — append the new entry (do not overwrite existing entries for the same date unless it's the same turbine+date+location combination, in which case merge by taking the higher splice count)
- Accumulate `total_splices` as the sum of all `splices_completed` entries
- Accumulate `total_ac_lc_changes` as the sum of all `ac_lc_changes` entries
- Set `rmu_completed`, `mate_mask_completed` to the latest non-zero value (or 0)
- Set `drawing_marked` to `true` if any report has Y
- Set `tested` to the latest `total_tested` value
- Set `has_challenges` to `true` if any report has a non-"No" challenge

Update `last_updated` to today's date.

Write the updated JSON back to `data/progress.json`.

### Step 3 — Show the dashboard

After saving, display a clean summary table:

```
OYA PROJECT — FIBER OPTIC PROGRESS
====================================
Date: [today]

WTG   | Splices | Tested | RMU | M/M | Drawing | AC→LC | Status
------|---------|--------|-----|-----|---------|-------|-------
WTG-07|   24    |   0    |  0  |  0  |    N    |  12   | ⚠ Untested
WTG-08|   24    |   0    |  0  |  0  |    N    |  12   | ⚠ Untested
WTG-09|   28    |   0    |  0  |  0  |    N    |  10   | ⚠ Untested
...
```

Status logic:
- `✅ Complete` — splices > 0 AND tested == splices AND drawing_marked == true
- `⚠ Untested` — splices > 0 but tested < splices
- `📋 Drawing pending` — splices > 0 and tested >= splices but drawing_marked == false  
- `🔴 No report` — no data at all

Then show a summary line:
```
Total splices across project: XXX
Turbines with reports: X/18
Turbines fully complete: X/18
Turbines with no report: [WTG-01, WTG-02, ...]
```

Then flag any issues:
- List turbines where splices > 0 but tested == 0 (untested work)
- List turbines where drawing is not marked
- Any reported challenges/delays
