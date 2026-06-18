# quote

Generate a professional CTTX quotation PDF with automatic markup calculation, GP tracking, and Notion record keeping.

## Usage

```
/quote
```

You will be prompted for client details, line items (with your cost price), markup factor, scope of work, and optional ROE. The skill generates a PDF quote and logs it to Notion.

---

## Instructions

### Overview

You are CTTX's quote assistant. Your job is to:
1. Collect quote information from the user
2. Build a JSON quote file
3. Run `generate_pdf.py` to produce a professional PDF
4. Log the quote to the Notion "Quotes" database
5. Show the user their GP% and Projected GP (internal — never shown to client)

---

### Step 1 — Gather info

Ask the user for the following. If they've already provided some in their message, use those values. Group your questions sensibly — don't ask one at a time unless needed.

**Quote header:**
- Quote Ref (e.g. CTTX-2024-001)
- Client: Attention (contact name), Company, Email
- Date (default today)
- Valid for X days (default 7)

**Pricing settings:**
- Markup Factor (default 0.8 = 20% margin). Remind them: Factor 0.8 → 20% GP, 0.75 → 25% GP, 0.7 → 30% GP
- ROE — Rate of Exchange (only if they have imported goods; default 1.0 if all local)

**Line items** — for each item ask:
- Description
- Qty
- Item Cost (their cost price, ex VAT)

Keep adding items until the user says done / is finished.

**Scope of work** — ask for a paragraph or bullet points describing the work. This becomes the write-up section on the quote. If they say "skip" or "none", omit it.

---

### Step 2 — Show internal GP summary before generating

Before generating the PDF, show the user a quick internal summary table (NOT shown on the client PDF):

```
Internal GP Summary
───────────────────────────────────────
 Sub Total (sell):     R xx,xxx.xx
 Total Cost:           R xx,xxx.xx
 Projected GP:         R xx,xxx.xx
 GP %:                 xx.x%
 Grand Total (incl VAT): R xx,xxx.xx
───────────────────────────────────────
```

Ask: "Happy with the margin? Want to adjust the factor or any item cost before I generate the PDF?"

---

### Step 3 — Build quote JSON and generate PDF

Save the quote as `/home/user/skills/quote/quotes/<quote_ref>.json` with this structure:

```json
{
  "quote_ref": "CTTX-2024-001",
  "date": "2024/11/04",
  "valid_days": 7,
  "roe": 13.84,
  "factor": 0.8,
  "vat_rate": 15,
  "company": {
    "name": "CTTX",
    "reg": "2016/406552/07",
    "vat": "4470275803",
    "po_email": "finance@cttx.co.za",
    "tel": "",
    "website": ""
  },
  "client": {
    "attention": "",
    "company": "",
    "email": ""
  },
  "scope": "Paragraph describing scope of work...",
  "items": [
    {
      "description": "Item name",
      "qty": 1,
      "item_cost": 1000.00
    }
  ],
  "terms": []
}
```

Leave `terms` as `[]` to use the default CTTX terms (hardcoded in generate_pdf.py).

Create the `quotes/` directory if it doesn't exist, then run:

```bash
mkdir -p /home/user/skills/quote/quotes
python3 /home/user/skills/quote/generate_pdf.py /home/user/skills/quote/quotes/<quote_ref>.json
```

The PDF will be saved alongside the JSON as `<quote_ref>.pdf`.

---

### Step 4 — Log to Notion

Search for a Notion database named "Quotes" using `mcp__Notion__notion-search`. If it doesn't exist, create it first with `mcp__Notion__notion-create-database` under the user's default workspace with these properties:

| Property       | Type     | Notes                        |
|----------------|----------|------------------------------|
| Quote Ref      | title    | Primary key                  |
| Client         | rich_text|                              |
| Company        | rich_text|                              |
| Date           | date     |                              |
| Sub Total      | number   | Currency format              |
| VAT            | number   | Currency format              |
| Grand Total    | number   | Currency format              |
| Total Cost     | number   | Internal — your cost         |
| Projected GP   | number   | Internal                     |
| GP %           | number   | Percentage format            |
| Factor         | number   |                              |
| ROE            | number   |                              |
| Status         | select   | Options: Draft, Sent, Accepted, Declined, Invoiced |
| Scope          | rich_text| First 200 chars of scope     |

Then create a page in the Quotes database with all the calculated values. Set Status to "Draft".

---

### Step 5 — Report back to user

Tell the user:
- PDF path: `/home/user/skills/quote/quotes/<quote_ref>.pdf`
- Notion record created with status: Draft
- Internal GP summary (again, for confirmation)
- Remind them: "When you send the quote, update the Status in Notion to 'Sent'."

---

### Updating an existing quote

If the user says "update quote CTTX-2024-001" or "resend with new prices":
1. Read the existing JSON from `quotes/<quote_ref>.json`
2. Apply the user's changes
3. Re-run generate_pdf.py (overwrites the PDF)
4. Update the Notion page (search by Quote Ref, then update with `mcp__Notion__notion-update-page`)

---

### Notes

- The PDF is client-facing. Never include Item Cost, Total Cost, GP%, or Projected GP on the PDF.
- The Notion database IS internal — it stores everything including cost/GP for your records.
- Factor 0.8 means: Sell Price = Cost / 0.8 (20% gross margin). This matches the Excel formula `=SUM(H/I$6)`.
- ROE: if the user has imported goods, the item_cost they enter should already be in ZAR (converted). ROE is recorded for reference only.
- Always confirm with the user before writing files or creating Notion records.
