# Input schemas

## `projects/<slug>/input.json` — assessment engine (`architect.py run`)
```json
{
  "slug": "barefoot-addo",
  "customer": {
    "company": "", "contact": {"name": "", "email": ""}, "property": "", "industry": "game_reserve|hospitality|farm|wind|solar|mining|engineering|business",
    "area": "urban|suburban|rural|remote",
    "context": {"location": "", "sites_buildings": "", "existing_connectivity": "", "existing_provider": "", "requested_service": "",
                "symmetry": "", "reliability": "", "growth": "", "existing_infrastructure": "", "deadline": "", "budget": "", "pain_points": ""},
    "drivers": [{"key": "guest", "driver": "", "operational": "", "network": "", "solution": "", "stated": true}],
    "requirement": {"down_mbps": null, "up_mbps": null, "because": "", "availability": "", "latency": "", "services": [], "architecture": ""}
  },
  "property": {"query": "-33.30, 25.73 | DMS | Maps URL | name", "lat": null, "lon": null, "antenna_m": null, "max_antenna_m": null,
               "boundary": "BOUNDARY APPROXIMATION — …", "features": [{"name": "", "kind": "", "lat": null, "lon": null}]},
  "extra_sites": [{"name": "River Lodge", "lat": 0, "lon": 0}],
  "params": {"clutter_m": 0, "max_hops": 4, "freq_ghz": 5.8},
  "inputs": {"kml": null, "points_csv": null, "cell_csv": null, "lpp": "inputs/design.lpp", "use_masts": true},
  "known_facts": [{"claim": "", "source": "", "date": "YYYY-MM-DD", "confidence": "High|Medium|Low",
                   "kind": "property|fibre|carrier|coverage|infrastructure|requirement", "status": "SOURCE-DERIVED"}],
  "known_infrastructure": [{"name": "", "kind": "carrier_mast|fibre_pop|exchange|datacentre|cttx", "lat": 0, "lon": 0, "height_m": null, "source": "", "status": "VERIFIED|SOURCE-DERIVED"}],
  "assessment_quote": {"zar_excl": 3500, "terms": ""},
  "summary": [], "field_checks": [], "risks": [], "commercial": []
}
```
Evidence statuses: VERIFIED (CTTX confirmed) · SOURCE-DERIVED · CALCULATED · INFERRED · ASSUMED · UNKNOWN · FIELD VERIFY. A carrier's written statement is SOURCE-DERIVED, not VERIFIED.

## `projects/<slug>/prospect.json` — pre-sales worker (`prospect.py run`)
```json
{
  "slug": "sekala",
  "property": {"name": "", "identity_sources": ["≥2"],
               "location": {"lat": 0, "lon": 0, "sources": ["≥2 for LOCATION VERIFIED"], "source_summary": ""}},
  "contact": {"email": "", "person": null, "sources": ["≥2"], "notes": []},
  "mast_radius_km": 40,
  "terrain_checked_by": null,
  "facts": [{"id": "F1", "section": "property|infra", "property_specific": true, "status": "SOURCE-DERIVED", "text": "", "source": ""}],
  "terrain_notes": [], "hypothesis": [], "likely_needs": [],
  "email": {"to": "", "subject": "", "body": "", "cta": "phrase that appears in body", "facts_used": ["F1", "F3", "F5"]}
}
```

## `projects/<slug>/field-verification.json` — `architect.py learn`
```json
{"date": "YYYY-MM-DD",
 "nodes": [{"name": "", "lat": 0, "lon": 0, "kind": "carrier", "operator": "", "height_m": 0}],
 "rejected_links": [{"a": "PROPERTY", "b": "C2", "reason": ""}],
 "verified_routes": [{"nodes": [], "equipment": "", "rx_dbm": 0}],
 "commercial_outcome": "", "findings": ""}
```
