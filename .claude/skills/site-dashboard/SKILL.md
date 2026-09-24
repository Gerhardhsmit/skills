---
name: site-dashboard
description: Show the OYA Wind Farm fibre optic progress dashboard across all 18 turbines (splices, testing, RMU, mate/mask, drawings, AC→LC, OTDR pass/fail, action items). Use when Gerhard asks "where are we on OYA", "show the dashboard", "project status", or "which turbines are outstanding".
---

# /site-dashboard

Run:

```
python3 .claude/skills/site-dashboard/oya.py dashboard
```

Show its output as-is in a code block. If `data/progress.json` doesn't exist, say that no reports have been logged yet and suggest `/parse-site-report`.

After the block, add a short **Next actions** list (three bullets at most) drawn from the ACTION ITEMS. Put OTDR failures and untested splices first. For OTDR failure detail, read `data/otdr-results.json`; for the port layout, read `data/wtg-spec.json`. Only read those files when they're needed.
