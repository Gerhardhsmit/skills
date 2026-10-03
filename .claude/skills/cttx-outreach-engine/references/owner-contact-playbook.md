# Owner contact playbook — reaching the person who owns the outcome

Goal per prospect: a named owner / MD / director (or the senior person who owns the outcome found in
discovery) with an address that is PUBLISHED or VERIFIED. INFERRED is acceptable for a draft only if it is
labelled. NONE means a role-addressed, forwardable email to the general inbox — still a real draft.

Work the sources in order. Stop when you have a PUBLISHED/VERIFIED address for the right person.
Record every source with the date seen.

## 1. Find the right person (name before address)
| Source | What to look for | Notes |
|---|---|---|
| Company website | About / Our story / Team / Leadership / Contact / History / Press, PDFs (annual reports, sustainability reports, tariff sheets, brochures), page footers, `mailto:` links | Family businesses often name the family on the history page |
| Group / parent | Holding company site, hotel/lodge group, IPP owner, co-op | The decision often sits at group level (e.g. lodge owned by a hotel group) |
| CIPC / company records | Directors of the registered company (via public company-lookup sites that show CIPC data) | Confirms who the directors actually are; no email, but the name is solid |
| Industry bodies | Member directories and committee lists: Citrus Growers' Association, Hortgro, SATI (table grapes), Vinpro / WOSA, Fruit SA, Agri Western Cape / Agri Eastern Cape, Wildlife Ranching SA, EC Parks & Tourism, SAWEA (wind), SAPVIA (solar), Salt producers' bodies, local business chambers | Committee lists name owners; award/annual pages often carry quotes |
| Trade press & interviews | Farmer's Weekly, Landbouweekblad, Food For Mzansi, Fruit Journal, Engineering News, Tourism Update, regional papers (The Herald, Talk of the Town, Grocott's Mail) | Interviews give the owner's own words — gold for the SIGNAL brief |
| LinkedIn | `site:linkedin.com/in "<company>" (owner OR director OR "managing director" OR founder)` via WebSearch | Use for name/role confirmation; never scrape or message from here |
| Apollo — free search | `apollo_mixed_people_api_search` with `q_organization_domains_list=[domain]`, seniorities owner/founder/c_suite/director/vp | Free. Returns names/titles; email is not revealed |
| Job adverts | Pnet, Careers24, LinkedIn jobs, the company's careers page | Reveal reporting lines ("reports to the MD, X") and systems in use |

Pick the most senior person who owns the outcome. For multi-entity groups, write to the person who
can approve a property-wide infrastructure decision, cc nobody on a first approach.

## 2. Find the address
1. **Published** — the person's own address on the company site, a PDF, a press release, a tender
   document or an association listing → `PUBLISHED` (record the URL).
2. **Collect the domain's pattern** — gather every address published on the same domain (staff on
   contact pages, PDFs, job adverts "send CV to …", press contacts). Feed them with the person's name to
   `python3 lib/contact_finder.py --domain <d> --name "<First Last>" --known a@d b@d …`.
   It returns the inferred pattern, confidence and ranked candidates → `INFERRED — verify before sending`.
3. **Apollo reveal** (credits) — only for the single best decision-maker of a prospect whose gate passes,
   and only when steps 1–2 gave no published address. `apollo_people_match` with the name + domain.
   Apollo "verified" → `VERIFIED`; anything else → `INFERRED`. Cap 2 credits per prospect, report spend.
4. **MX sanity check** — `python3 lib/contact_finder.py --mx <domain>` where DNS is reachable (it is
   blocked in some cloud sessions; then record MX as UNKNOWN, don't guess).
5. **Never** guess a personal (gmail/yahoo etc.) address. Never use an address from a leaked list.

## 3. No name or no address → the forwardable email
To the general inbox (info@, reservations@, office@): "For the attention of the Managing Director".
Subject and first line must be so specific to their operation that reception forwards it.
Example subject shape: "<Their site/asset> — <the specific gap we saw>" — never "Connectivity assessment".

## 4. Classify and record (contact.json)
```json
{"name": "", "role": "", "email": "", "email_status": "PUBLISHED|VERIFIED|INFERRED|NONE",
 "pattern": "first|first.last|flast|…", "pattern_confidence": 0.0,
 "sources": [{"what": "", "url": "", "seen": "YYYY-MM-DD"}],
 "apollo_credits_spent": 0, "general_inbox": ""}
```

## 5. When everything fails
Raise a precise task for Gerhard, not a vague one: "Pumba: owner family name known (Howarth), no
address published; one 2-minute call to reception asking for the MD's email unlocks the draft."
That is the only time a phone call is suggested.

## Why this order
Names from the business's own public record carry the most weight and cost nothing; pattern inference
from the same domain is usually right for small SA businesses (first@ and first.last@ dominate);
Apollo credits are scarce (check balance with `apollo_users_api_profile`) and waterfall enrichment is
not enabled on the CTTX Apollo team — enabling it is a Gerhard decision (cost).
