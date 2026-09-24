# /cttx-daily-brief

Generate and display the CTTX daily commercial brief.

## Instructions

1. Run:
```bash
python3 engine/cttx_engine.py brief
```

2. Display the full brief output.

3. After displaying, highlight:
   - Any items in MONEY WAITING that need immediate attention
   - Any HIGH opportunity properties with no draft queued
   - Any drafts older than 48h waiting for human review
   - Any system component showing FAIL or PARTIAL

4. Suggest the one or two most commercially valuable next actions for today.

## Connecting live data

The brief currently shows placeholders for:
- **Outstanding invoices**: Connect to Pastel/accounting export or Outlook search
- **Tender releases**: Set up eTenders/CIDB RSS monitoring
- **Unanswered enquiries**: Connect to Outlook inbox search

To extend the brief with Outlook data on Windows, set:
```
CTTX_OUTLOOK_ENABLED=1
```
The draft engine will then use win32com to query Drafts and Sent folders directly.
