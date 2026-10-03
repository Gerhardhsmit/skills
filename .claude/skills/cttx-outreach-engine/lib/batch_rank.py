#!/usr/bin/env python3
"""Rank CTTX Pipeline rows into the next outreach batch (stdlib only).

Input: JSON list of row objects as returned by the Notion SQL query (keys = property names,
e.g. "Company", "Sector", "Province", "Contact Person", "Email", "Priority", "Pain Signal", "url").

  python3 batch_rank.py rows.json --size 5

Output JSON: {"batch": [...], "prospecting_tasks": [...], "duplicates": [...], "skipped": [...]}
"""
import argparse
import json
import re
import sys

GENERIC_LOCALS = {"info", "reservations", "sales", "office", "admin", "explore", "pgr", "bookings",
                  "enquiries", "reception", "res", "contact", "hello"}
# Rows that describe a segment, not a business: they become prospecting tasks.
SEGMENT_HINTS = re.compile(r"\b(operations|farms|estates|contractors|concessions|backhaul|"
                           r"tbc|inbound enquiry)\b", re.I)
PLACEHOLDER_CONTACT = re.compile(r"\b(tbc|not yet identified|owner / |manager / |farm owner)\b", re.I)
SECTOR_FIT = {  # CTTX target markets (Global Command §11); fit only, never a template.
    "Private Game Reserve": 3, "Farm / Agriculture": 3, "Wind Farm": 3, "Solar Farm": 3,
    "Mining": 3, "Wine Estate": 2, "Luxury Lodge": 2, "Logistics": 2, "Industrial Park": 2,
    "Renewable Energy": 2, "Security Estate": 1, "Other": 1,
}
STOP = {"pty", "ltd", "the", "private", "game", "reserve", "group", "farms", "farm", "company",
        "wildlife", "wind", "(pty)", "and", "&"}


def norm_company(name):
    s = re.sub(r"\(.*?\)", " ", (name or "").lower())
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    toks = [t for t in s.split() if t not in STOP]
    return " ".join(toks) or (name or "").lower().strip()


def email_kind(email):
    if not email or "@" not in email:
        return "none"
    local = email.split("@", 1)[0].lower()
    return "generic" if local in GENERIC_LOCALS else "named"


def is_segment(row):
    company = row.get("Company") or ""
    contact = row.get("Contact Person") or ""
    if not row.get("Website") and (SEGMENT_HINTS.search(company) or PLACEHOLDER_CONTACT.search(contact)):
        return True
    return bool(re.search(r"\b(tbc|inbound enquiry)\b", company, re.I))


def score(row):
    s = {"High": 30, "Medium": 15, "Low": 5}.get(row.get("Priority"), 10)
    s += 4 * SECTOR_FIT.get(row.get("Sector"), 1)
    contact = row.get("Contact Person") or ""
    if contact and not PLACEHOLDER_CONTACT.search(contact):
        s += 12  # a named decision-maker already on file
    s += {"named": 10, "generic": 3, "none": 0}[email_kind(row.get("Email"))]
    if row.get("Pain Signal"):
        s += 8  # evidence already gathered
    if row.get("Website"):
        s += 3
    return s


def completeness(row):
    return sum(1 for k in ("Contact Person", "Email", "Website", "Pain Signal", "Town", "Role") if row.get(k))


def _domain(url_or_email):
    s = (url_or_email or "").lower().strip()
    if "@" in s:
        s = s.split("@", 1)[1]
    s = re.sub(r"^https?://", "", s).split("/")[0]
    return s[4:] if s.startswith("www.") else s


def is_contacted(row, contacted):
    """contacted: set of lowercase domains and/or normalised company names seen in Gmail threads."""
    if not contacted:
        return False
    keys = {_domain(row.get("Email")), _domain(row.get("Website")), norm_company(row.get("Company"))}
    return bool(keys - {""} & contacted)


def rank(rows, size=5, balance=True, contacted=None):
    contacted = {c.strip().lower() for c in (contacted or []) if c.strip()}
    contacted |= {norm_company(c) for c in list(contacted) if "." not in c}
    warm = [r for r in rows if is_contacted(r, contacted)]
    rows = [r for r in rows if not is_contacted(r, contacted)]
    groups = {}
    for r in rows:
        groups.setdefault(norm_company(r.get("Company")), []).append(r)
    duplicates, unique = [], []
    for key, rs in groups.items():
        rs = sorted(rs, key=lambda r: (-completeness(r), -score(r)))
        unique.append(rs[0])
        if len(rs) > 1:
            duplicates.append({"company": rs[0].get("Company"), "keep": rs[0].get("url"),
                               "duplicates": [r.get("url") for r in rs[1:]]})
    prospecting, candidates = [], []
    for r in unique:
        (prospecting if is_segment(r) else candidates).append(r)
    candidates.sort(key=lambda r: -score(r))
    batch = []
    if balance:
        by_prov = {}
        for r in candidates:
            by_prov.setdefault(r.get("Province") or "?", []).append(r)
        provs = sorted(by_prov, key=lambda p: -score(by_prov[p][0]))
        while len(batch) < size and any(by_prov.values()):
            for p in provs:
                if by_prov[p] and len(batch) < size:
                    batch.append(by_prov[p].pop(0))
    else:
        batch = candidates[:size]
    out = lambda r: {"company": r.get("Company"), "province": r.get("Province"), "sector": r.get("Sector"),
                     "score": score(r), "contact": r.get("Contact Person"), "email": r.get("Email"),
                     "email_kind": email_kind(r.get("Email")), "url": r.get("url"),
                     "tier": None}
    batch_out = [out(r) for r in batch]
    for i, b in enumerate(batch_out):
        b["tier"] = "Full" if i < max(1, round(size * 0.6)) else "Screen"
    return {
        "batch": batch_out,
        "prospecting_tasks": [{"segment": r.get("Company"), "province": r.get("Province"),
                               "sector": r.get("Sector"), "url": r.get("url"),
                               "task": "Name 5 real businesses in this segment and add them as pipeline rows"}
                              for r in prospecting],
        "duplicates": duplicates,
        "warm": [{"company": r.get("Company"), "url": r.get("url"),
                  "task": "Prior contact in Gmail: route to reply desk, update Stage; never cold-pitch"}
                 for r in warm],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("rows")
    ap.add_argument("--size", type=int, default=5)
    ap.add_argument("--no-balance", action="store_true")
    ap.add_argument("--contacted", help="file of domains/company names already in Gmail threads, one per line")
    a = ap.parse_args(argv)
    with open(a.rows) as f:
        data = json.load(f)
    rows = data.get("results", data) if isinstance(data, dict) else data
    contacted = open(a.contacted).read().splitlines() if a.contacted else []
    print(json.dumps(rank(rows, a.size, not a.no_balance, contacted), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
