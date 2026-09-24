# OYA Project — Claude Code Skills

Skills for managing the OYA Wind Farm fiber optic project via WhatsApp reports.

## Skills

All skills live in `.claude/skills/<name>/SKILL.md`. Claude Code picks them up automatically as `/<name>`. Tracker logic lives in scripts, so updates are fast and give the same result every time.

### `/parse-site-report`
Paste WhatsApp daily report messages. Claude extracts all reports, updates the tracker, and shows the project dashboard.

### `/site-dashboard`
Show the full project progress dashboard across all 18 turbines (WTG-01 to WTG-18).
Script: `python3 .claude/skills/site-dashboard/oya.py dashboard`

## Data

Progress is tracked in `data/progress.json` — cumulative record of all reports received.

## Report Format

Technicians send this template daily before 17:00:

```
*TURBINE NUMBER: WTG-XX
*DATE: DD/MM/YYYY
*SPLICES COMPLETED TODAY: N
*RMU COMPLETED: N
*MATE/MASK COMPLETED: N
*TOTAL SPLICES / TERMINATIONS TESTED: N
*MARKED ON DRAWING (Y/N): Y/N
*AC → LC CONNECTOR CHANGES: N
*CHALLENGES / DELAYS: text or No
*PHOTOS ATTACHED (Y/N): Y/N
```

### `/link-planner`
Wireless link pipeline: site assessment → link design (Fresnel, link budget) → proposal → Gmail draft to the client → execution tracking.
Skill: `.claude/skills/link-planner/` · client jobs: `projects/<client-slug>/`
