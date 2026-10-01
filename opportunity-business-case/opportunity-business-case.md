# opportunity-business-case

Turn a researched CTTX opportunity into a customer-specific private-network business case, following the **Dutoit Langkloof reference pattern**.

This is the standard method for the CTTX Opportunity, Discovery and Sales Engines. It is not a one-off proposal template.

## Usage

```
/opportunity-business-case <customer or property name>
```

## Principle

CTTX does not prospect for internet connections.

CTTX finds business operations where a customer-owned private communications infrastructure improves operational visibility, control, resilience, efficiency, security, traceability or production outcomes. It then turns that into a paid **Private Infrastructure Network Assessment**, which leads to deployment and managed infrastructure.

The chain to reproduce in every case:

```
CUSTOMER OPERATION
→ BUSINESS PROBLEM
→ ECONOMIC / OPERATIONAL CONSEQUENCE
→ PRIVATE NETWORK OPPORTUNITY
→ CUSTOMER-SPECIFIC NETWORK CONCEPT
→ PROOF / ASSESSMENT
→ DEPLOYMENT
```

Reproduce the **thinking** of the Dutoit document, not its wording.

## Instructions

### Step 1 — Inspect what already exists

Before researching, check:

- Notion **CTTX Pipeline** for an existing record of this customer. Extend it; never create a duplicate.
- `data/learning-loop.json` for patterns from the same industry or region. Reuse the industry problems, objections and network patterns that are already recorded.
- Existing CTTX property intelligence (coordinates, terrain, LOS, mast dataset, Link Planner outputs) for this property or nearby sites.

### Step 2 — Do the customer and industry homework

Answer each question with evidence. Record the source for each answer. If something can't be found, write `UNKNOWN — validate with customer`.

1. What does the company actually operate (products, volumes, seasons, markets)?
2. Where are its physical assets (farms, blocks, packhouses, cellars, depots, dams, boreholes, offices, accommodation)? Give coordinates where possible.
3. How do people, product, machinery and information move through the operation?
4. Which operational processes depend on communications?
5. Where could delays, blind spots, manual processes, disconnected systems or outages affect business outcomes?
6. Which systems need connectivity: sensors, cameras, telemetry, irrigation, SCADA, access control, weighbridges, cold chain, logistics, traceability, workforce?
7. What carrier and communications infrastructure already exists (fibre, ISP, cellular, satellite)?
8. What private infrastructure already exists (towers, radios, Wi-Fi, LoRa, CCTV)?
9. What CTTX network architecture could plausibly fit?
10. Why would this customer care commercially?

Use the customer's own terminology, such as cultivar, block, harvest window, packhouse, cellar, export certification or plantation compartment. Do not use generic industry copy.

### Step 3 — Apply the existing-connectivity rule

Existing fibre, ISP, cellular, satellite, Wi-Fi, LoRa, CCTV, towers or radios are **evidence**, never a negative score or a disqualifier.

For each one, ask: *what does it enable today, and what does the customer still need to connect, control, monitor or make resilient?* Existing infrastructure often increases the value of an integrated private network.

### Step 4 — Frame the carrier + private-network relationship

Carrier connectivity is the external feed into the customer's private network. It is not the end product. CTTX is not positioned as a carrier reseller.

```
CARRIER (existing or proposed)
    ↓
CTTX PRIVATE NETWORK
    ↓
OPERATIONAL SITES
    ↓
APPLICATIONS / SYSTEMS / PEOPLE / ASSETS
```

### Step 5 — Property intelligence (where geography matters)

Run the CTTX property intelligence workflow as far as the available data allows:

```
property discovery → coordinates → terrain → LOS → candidate infrastructure
→ Link Planner → topology → resilience → provisional assessment
```

Do not fabricate engineering certainty. Tag every technical statement with one of:

| Tag | Meaning |
|-----|---------|
| `[PUBLIC]` | Public-information evidence, with the source cited |
| `[DESKTOP]` | Desktop engineering assumption |
| `[CONCEPT]` | Provisional network concept |
| `[CUSTOMER]` | Needs customer validation |
| `[SURVEY]` | Needs a site survey |

Feasibility comes before price. Do not include pricing in this document unless the `infrastructure-project-quoting-estimation` skill has produced it from approved pricing sources.

### Step 6 — Write the business-case package

Write for the customer's business, not for their IT department. Start from the business outcome. The technology follows the business case. Do not open with radios, towers, fibre, Wi-Fi or bandwidth.

Use exactly these six sections:

1. **WHAT DECIDES THIS CUSTOMER'S BUSINESS OUTCOME**: the few factors that make or break their year, such as yield, quality, export compliance, water, labour, security or uptime.
2. **THE CUSTOMER'S OPERATIONAL JOURNEY**: how product, people, machinery and information move from start to finish, and where communications fail or are missing along the way.
3. **WHAT CHANGES WITH ONE PRIVATE NETWORK**: before and after for each pain point, framed through the four ROI lenses (Avoided Loss, Operational Efficiency, Infrastructure Ownership, Executive Risk Reduction). Include a section titled exactly **Cost of Disconnection vs Value of Connected Operations**.
4. **WHAT THE PRIVATE NETWORK LOOKS LIKE**: the conceptual architecture in the customer's language (carrier feed → private backbone → sites → systems), with evidence tags.
5. **HOW IT CONNECTS THE PROPERTY / OPERATION**: sites, candidate high points, links, coverage and resilience, all marked `[DESKTOP]` / `[CONCEPT]` / `[SURVEY]` as appropriate.
6. **HOW CTTX WOULD START AND PROVE IT**: the Private Infrastructure Network Assessment as the next step. Give its scope, what it validates, what the customer receives, and an optional first proof site or pilot.

### Step 7 — The call to action

The initial research aims to **earn the conversation**, not to sell the whole network.

The CTA is always the **Private Infrastructure Network Assessment**. It bridges public-information discovery and a quote-ready CTTX design.

### Step 8 — Record

1. Update the customer's Notion **CTTX Pipeline** record with the stage, the business-case artefact link, the hypothesis and the next action.
2. Append a learning entry to `data/learning-loop.json` (see the schema in that file). Fill in what is known now and update the entry as the opportunity progresses.
3. Any outreach email is a **draft only**, prepared for Gerhard to send from `gerhard@cttx.co.za`. Never send.

## Quality gate — do not release the package unless

- [ ] Every section names the customer's actual assets, places and processes. No paragraph could apply to any farm.
- [ ] The business outcome comes before any technology.
- [ ] No existing infrastructure is treated as a negative.
- [ ] The carrier is positioned as a feed into the private network, not as the product.
- [ ] Every technical claim carries an evidence tag.
- [ ] No invented pricing, coordinates, contacts or engineering results.
- [ ] The CTA is the Private Infrastructure Network Assessment.
- [ ] Notion and the learning loop are updated.
