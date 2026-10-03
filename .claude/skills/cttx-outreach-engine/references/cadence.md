# Cadence — how the engine runs without Gerhard driving it

## Daily (weekdays, scheduled Routine in a fresh cloud session)
0. Reply desk + stage reconciliation (SKILL.md Step 0) — live conversations first, always.
1. Run the engine on a batch of 5 EC/WC prospects (Steps 1–9 of SKILL.md).
2. Check Follow-Ups Due (`Next Action Date` ≤ today) and prepare follow-up DRAFTS for rows where
   Gerhard has sent (Stage = Contacted) and no reply exists in Gmail (search the thread first).
3. Write the run report to Notion as a page under 📈 Sales & Pipeline titled
   `Outreach Engine Run — YYYY-MM-DD` and end with **Next action**.
Gerhard's part: open the run page, review the drafts, run `push_outlook_drafts.ps1` (or paste), send
from Outlook, move Stage to Contacted.

## Follow-up sequence (all drafts, Gerhard sends)
| When | Draft | Content rule |
|---|---|---|
| Day 0 | First email + SIGNAL brief | From the discovery record |
| Day 5 | Short follow-up | One NEW fact about their business, not "just checking in" |
| Day 12 | Value follow-up | One relevant anonymised outcome or the Sandy Mountain reference if it genuinely matches |
| Day 21 | Close-the-loop | Polite, permission to close the file; opt-out honoured |
A reply at any point stops the sequence; route to Meeting Booked / Assessment.

## Weekly (Monday run adds)
- Pipeline health: rows Not Contacted with no email, duplicates, rows with stale Next Action Date.
- Segment rows ("Gamtoos Valley Agricultural Operations", "PE Security Estates" …) → name 5 real
  businesses inside each segment and add them to CTTX Pipeline as new rows (Lead Source: Prospecting).
- Apollo credit balance and spend.
- Marketing: count of Buffer ideas added; Marketing manager picks what to post.

## KPIs the run report tracks
Researched this week · Gate PASS rate · Named decision-makers found · PUBLISHED/VERIFIED email rate ·
Drafts ready · Sent (from Stage changes) · Replies · Meetings · Assessments.

## Routine prompt (used when the daily Routine is created)
```
Run the CTTX outreach engine. First: git fetch origin claude/trusting-thompson-x64q4y and read
.claude/skills/cttx-outreach-engine/SKILL.md from that branch, then follow it: batch of 5
Eastern Cape / Western Cape prospects from CTTX Pipeline (Notion). Full discovery per prospect using the
cttx-private-network-discovery-strategy skill, owner contact playbook, network design composer, gate.
Draft only — never send email, never create Gmail drafts. Apollo cap: 2 credits per prospect, 10 per run.
Never write prospect data into the git repo. Log every prospect on its existing CTTX Pipeline row and
write the run report page under Sales & Pipeline. End with one Next action.
```
