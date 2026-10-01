#!/usr/bin/env python3
"""CTTX Property Intelligence Pre-Sales Worker.

    python3 prospect.py run <slug>      # projects/<slug>/prospect.json → intelligence.md, email.md, gate.json, linkplanner_candidates.csv

The email is the LAST output of the intelligence, never the first. Pipeline:
  1. property   — name, coordinates (with sources), operation facts
  2. masts      — CTTX historical mast dataset: nearest + backhaul-grade candidates (HISTORICAL, never "working")
  3. terrain    — DEM screening property→candidate (if a DEM source is reachable); else UNKNOWN + LINKPlanner export
  4. hypothesis — single site / hub / cluster / relay, only where evidence supports it
  5. email      — written by Claude from sourced facts; this worker scores personalisation and runs the quality gate
Nothing is sent from here. Sending is a separate, approved step (Microsoft 365 / Gmail) after the gate passes.
"""
import csv
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import masts  # noqa: E402
from engine import analyse_link  # noqa: E402
from sources import LiveSources, SourceLog  # noqa: E402

from paths import PROJECTS  # noqa: E402
TODAY = datetime.date.today().isoformat()
BANNED = ["leading provider", "cutting-edge", "cutting edge", "seamless", "revolutionary", "best-in-class",
          "best in class", "we specialise", "we specialize", "valued customer", "pleased to introduce",
          "state-of-the-art", "world-class", "one-stop", "please let us know if you are interested"]
CLAIM_WORDS = ["line of sight", "line-of-sight", "working mast", "live mast", "guaranteed", "will provide backhaul",
               "confirmed tower", "we confirmed"]


def compass(b):
    return ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"][int((b + 11.25) // 22.5) % 16]


def terrain_screen(prop, cands, src):
    """Preliminary DEM screening with ASSUMED heights (property 9 m, site 30 m). Never an RF design."""
    out = {}
    for c in cands:
        a = {"id": "PROPERTY", "lat": prop["lat"], "lon": prop["lon"], "h_design": 9, "h_max": 30}
        b = {"id": c["id"], "lat": c["lat"], "lon": c["lon"], "h_design": 30, "h_max": 30}
        r = analyse_link(a, b, src, 5.8)
        out[c["id"]] = r
        if r["status"] == "UNVERIFIED":
            break  # DEM unreachable — don't hammer it
    return out


def run(slug):
    pdir = os.path.join(PROJECTS, slug)
    p = json.load(open(os.path.join(pdir, "prospect.json")))
    loc = p["property"]["location"]
    log = SourceLog()
    # 2. masts
    near = masts.near(loc["lat"], loc["lon"], p.get("mast_radius_km", 40), 15)
    wide = masts.near(loc["lat"], loc["lon"], 120, 5000)
    backhaul = [h for h in wide if (h.get("attrs") or {}).get("poc_type") or "Fibre" in str((h.get("attrs") or {}).get("backhaul"))][:6]
    log.ok("CTTX mast dataset", "query", f"{len(near)} within {p.get('mast_radius_km', 40)} km; {len(backhaul)} backhaul-grade within 120 km")
    # 3. terrain
    src = LiveSources(log)
    screen = terrain_screen(loc, near[:6], src)
    dem_ok = any(r["status"] != "UNVERIFIED" for r in screen.values())
    # LINKPlanner export so the existing CTTX Link Planner can do the terrain step when the DEM here is unavailable
    with open(os.path.join(pdir, "linkplanner_candidates.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "latitude", "longitude", "role", "distance_km", "bearing_deg", "note"])
        w.writerow([p["property"]["name"], loc["lat"], loc["lon"], "customer", 0, "", "property (" + loc["source_summary"] + ")"])
        for h in near[:8] + [b for b in backhaul[:3] if b not in near]:
            w.writerow([h["name"], h["lat"], h["lon"], "candidate (HISTORICAL)", h["distance_km"], h["bearing_deg"],
                        "; ".join(masts.backhaul_notes(h))])
    # 4/5. gate
    email = p.get("email", {})
    gate = quality_gate(p, near, dem_ok, email)
    intel = intelligence_md(p, near, backhaul, screen, dem_ok, log, gate)
    open(os.path.join(pdir, "intelligence.md"), "w").write(intel)
    open(os.path.join(pdir, "email.md"), "w").write(email_md(p, email, gate))
    json.dump(gate, open(os.path.join(pdir, "gate.json"), "w"), indent=2)
    print(f"{p['property']['name']}: {len(near)} masts ≤{p.get('mast_radius_km', 40)} km (nearest {near[0]['distance_km'] if near else '—'} km), "
          f"DEM {'OK' if dem_ok else 'UNAVAILABLE'}, personalisation {gate['personalisation_score']}, decision {gate['decision']}")
    return gate


def quality_gate(p, near, dem_ok, email):
    facts = {f["id"]: f for f in p.get("facts", [])}
    used = [facts[i] for i in email.get("facts_used", []) if i in facts]
    personal = [f for f in used if f.get("property_specific") and f.get("source")]
    body = (email.get("body") or "").lower()
    banned = [b for b in BANNED if b in body]
    claims = [c for c in CLAIM_WORDS if c in body and not any(c in (f.get("text", "").lower()) and f.get("status") == "VERIFIED" for f in used)]
    loc = p["property"]["location"]
    contact = p.get("contact", {})
    checks = {
        "PROPERTY CORRECT": bool(p["property"].get("identity_sources")) and len(p["property"]["identity_sources"]) >= 2,
        "CONTACT CORRECT": email.get("to") == contact.get("email") and len(contact.get("sources", [])) >= 2,
        "LOCATION VERIFIED": len(loc.get("sources", [])) >= 2,
        "INFRASTRUCTURE ANALYSED": bool(near),
        "TERRAIN CHECKED": dem_ok or bool(p.get("terrain_checked_by")),
        "FACTS SOURCED": all(f.get("source") for f in used) and bool(used),
        "NO INVENTED CLAIMS": not claims,
        "PERSONALISATION ≥ 3 FACTS": len(personal) >= 3,
        "NO GENERIC MARKETING LANGUAGE": not banned,
        "CTA CLEAR": bool(email.get("cta")) and email.get("cta", "").lower() in body,
        "ASSESSMENT POSITIONING CORRECT": "assessment" in body and not re.search(r"\bfree (design|study)\b", body),
    }
    critical = ["PROPERTY CORRECT", "CONTACT CORRECT", "LOCATION VERIFIED", "INFRASTRUCTURE ANALYSED", "TERRAIN CHECKED", "FACTS SOURCED",
                "NO INVENTED CLAIMS", "PERSONALISATION ≥ 3 FACTS", "CTA CLEAR"]
    failed = [k for k in critical if not checks[k]]
    return {"date": TODAY, "checks": checks, "failed_critical": failed, "personalisation_score": len(personal),
            "personal_facts": [f["id"] for f in personal], "banned_phrases": banned, "unsupported_claims": claims,
            "decision": "READY FOR GERHARD'S APPROVAL" if not failed else "DO NOT SEND"}


def intelligence_md(p, near, backhaul, screen, dem_ok, log, gate):
    pr, loc = p["property"], p["property"]["location"]
    L = [f"# Property Intelligence — {pr['name']} (INTERNAL)", f"{TODAY} · decision: **{gate['decision']}**", "",
         "## 1. Property", f"- **Location:** {loc['lat']}, {loc['lon']} — {loc['source_summary']} "
         f"([map](https://www.google.com/maps?q={loc['lat']},{loc['lon']}))"]
    L += [f"- {f['text']} — _{f['status']}: {f['source']}_" for f in p.get("facts", []) if f.get("section") == "property"]
    L += ["", "## 2. Contact"]
    c = p.get("contact", {})
    L += [f"- **Verified address:** {c.get('email')} ({'; '.join(c.get('sources', []))})",
          f"- **Decision-maker:** {c.get('person') or 'UNKNOWN — write so the email can be forwarded internally'}"]
    L += [f"- {x}" for x in c.get("notes", [])]
    L += ["", "## 3. Infrastructure (CTTX mast dataset — every point HISTORICAL, status unknown)",
          "| # | Site | Dist | Bearing | Service level | Backhaul attributes | Terrain screen |", "|---|---|---|---|---|---|---|"]
    for i, h in enumerate(near, 1):
        t = screen.get(h["id"])
        ts = (t["status"] + (f" ({t.get('reason')})" if t.get("reason") else "")) if t else "not screened"
        a = (h.get("attrs") or {})
        L.append(f"| {i} | {h['name']} ({h['id']}) | {h['distance_km']} km | {h['bearing_deg']}° {compass(h['bearing_deg'])} | "
                 f"{h.get('service_level') or '—'} | {a.get('backhaul') or 'not in attribute set'} | {ts} |")
    L += ["", "**Nearest backhaul-grade points in the dataset (POC / fibre attributes):**"]
    L += [f"- {h['name']} — {h['distance_km']} km {compass(h['bearing_deg'])}: " + "; ".join(masts.backhaul_notes(h)) for h in backhaul]
    L += ["", "## 4. Terrain", ("- DEM screening ran (CALCULATED, ASSUMED heights 9 m / 30 m) — preliminary only." if dem_ok else
                                "- **NOT SCREENED** — no elevation source reachable. Nearest ≠ best is unresolved. "
                                "`linkplanner_candidates.csv` is ready for the CTTX Link Planner to profile property → top candidates.")]
    L += [f"- {x}" for x in p.get("terrain_notes", [])]
    L += ["", "## 5. Opportunity hypothesis (INFERRED — to be proven in the assessment)"] + [f"- {x}" for x in p.get("hypothesis", [])]
    L += ["", "## 6. Likely requirements"] + [f"- {x}" for x in p.get("likely_needs", [])]
    L += ["", "## 7. Quality gate", "| Check | Result |", "|---|---|"]
    L += [f"| {k} | {'YES' if v else '**NO**'} |" for k, v in gate["checks"].items()]
    L += ["", f"Personalisation score: **{gate['personalisation_score']}** ({', '.join(gate['personal_facts'])})",
          f"**Decision: {gate['decision']}**" + (f" — blocked by: {', '.join(gate['failed_critical'])}" if gate["failed_critical"] else "")]
    L += ["", "## 8. Evidence", "| ID | Fact | Status | Source |", "|---|---|---|---|"]
    L += [f"| {f['id']} | {f['text']} | {f['status']} | {f['source']} |" for f in p.get("facts", [])]
    L += ["", "### Source log"] + [f"- {'✅' if e['ok'] else '❌'} {e['source']} — {e['action']}: {e['detail'][:120]}" for e in log.entries]
    return "\n".join(L)


def email_md(p, email, gate):
    return "\n".join([f"# Draft — {p['property']['name']} (NOT SENT)", f"**Gate:** {gate['decision']}"
                      + (f" — blocked by {', '.join(gate['failed_critical'])}" if gate["failed_critical"] else ""), "",
                      f"**To:** {email.get('to')}", f"**Subject:** {email.get('subject')}", "", email.get("body", ""), "",
                      "---", "Facts used: " + ", ".join(email.get("facts_used", []))])


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "run":
        sys.exit(__doc__)
    run(sys.argv[2])
