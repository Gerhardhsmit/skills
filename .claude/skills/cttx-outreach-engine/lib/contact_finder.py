#!/usr/bin/env python3
"""Email pattern inference for CTTX owner outreach (stdlib only).

Given addresses already PUBLISHED on a company domain and the name of the decision-maker,
infer the domain's local-part pattern and rank candidate addresses. Output is always
labelled INFERRED unless the exact address was itself published.

  python3 contact_finder.py --domain example.co.za --name "Jan van der Merwe" \
      --known piet@example.co.za info@example.co.za
  python3 contact_finder.py --mx example.co.za
"""
import argparse
import json
import re
import socket
import sys
import unicodedata

GENERIC = {
    "info", "admin", "office", "sales", "reception", "reservations", "bookings", "enquiries",
    "enquiry", "accounts", "hr", "careers", "jobs", "support", "marketing", "contact", "hello",
    "mail", "manager", "gm", "md", "ceo", "explore", "res", "pgr", "noreply", "no-reply",
}
PARTICLES = {"van", "der", "de", "du", "le", "la", "von", "den", "ter", "te"}


def _ascii(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def split_name(full):
    """Return (first, last_parts) where last_parts keeps SA surname particles: 'van der Merwe'."""
    words = [w for w in re.split(r"[\s]+", _ascii(full).strip()) if w]
    words = [re.sub(r"[^a-z\-']", "", w) for w in words]
    words = [w for w in words if w]
    if not words:
        raise ValueError("empty name")
    if len(words) == 1:
        return words[0], []
    return words[0], words[1:]


def surname_forms(last_parts):
    """'van der merwe' -> ['vandermerwe', 'merwe', 'van-der-merwe'] (most likely first)."""
    if not last_parts:
        return []
    joined = "".join(p.replace("'", "") for p in last_parts)
    core = [p for p in last_parts if p not in PARTICLES] or last_parts
    forms = [joined, core[-1].replace("'", ""), "-".join(last_parts)]
    seen, out = set(), []
    for f in forms:
        if f and f not in seen:
            seen.add(f)
            out.append(f)
    return out


PATTERNS = {
    "first": lambda f, l: f,
    "first.last": lambda f, l: f"{f}.{l}",
    "firstlast": lambda f, l: f"{f}{l}",
    "flast": lambda f, l: f"{f[0]}{l}",
    "f.last": lambda f, l: f"{f[0]}.{l}",
    "firstl": lambda f, l: f"{f}{l[0]}",
    "first_last": lambda f, l: f"{f}_{l}",
    "last": lambda f, l: l,
    "last.first": lambda f, l: f"{l}.{f}",
}
# Prior weights for small/medium South African businesses when no evidence exists.
PRIOR = {"first": 0.34, "first.last": 0.26, "flast": 0.12, "firstl": 0.07, "f.last": 0.06,
         "firstlast": 0.06, "last": 0.04, "first_last": 0.03, "last.first": 0.02}


def classify_local(local, first=None, last=None):
    """Which patterns could produce this local part? Without a name we can only test shape."""
    local = local.lower()
    if local in GENERIC:
        return []
    if first and last:
        return [p for p, fn in PATTERNS.items() if fn(first, last) == local]
    # Shape-only heuristics for a published address whose owner we don't know.
    if "." in local:
        a, _, b = local.partition(".")
        return ["f.last"] if len(a) == 1 else ["first.last"]
    if "_" in local:
        return ["first_last"]
    return ["first"]  # weak: could also be flast/firstlast/last — handled by low weight


def infer(domain, name, known):
    domain = domain.lower().strip()
    first, last_parts = split_name(name)
    forms = surname_forms(last_parts)
    evidence = {}
    published_exact = None
    used = []
    for addr in known:
        addr = addr.strip().lower()
        if "@" not in addr:
            continue
        local, _, dom = addr.partition("@")
        if dom != domain:
            continue
        if local in GENERIC:
            continue
        used.append(addr)
        # Shape-only evidence; plain single tokens are weak evidence for "first".
        for p in classify_local(local):
            w = 0.5 if (p == "first" and "." not in local) else 1.0
            evidence[p] = evidence.get(p, 0) + w
    scores = {}
    for p, prior in PRIOR.items():
        scores[p] = prior + evidence.get(p, 0)
    total = sum(scores.values())
    scores = {p: s / total for p, s in scores.items()}

    candidates = {}
    for p, fn in PATTERNS.items():
        if p != "first" and not forms:
            continue
        for i, l in enumerate(forms or [""]):
            local = fn(first, l) if l or p == "first" else None
            if not local:
                continue
            addr = f"{local}@{domain}"
            s = scores.get(p, 0) * (1.0 if i == 0 else 0.35)
            candidates[addr] = max(candidates.get(addr, 0), s)
    ranked = sorted(candidates.items(), key=lambda kv: -kv[1])
    for addr in (a.strip().lower() for a in known):
        if addr in candidates:
            published_exact = addr
    best_pattern = max(scores, key=scores.get)
    return {
        "domain": domain,
        "name": name,
        "evidence_addresses": used,
        "pattern": best_pattern,
        "pattern_confidence": round(scores[best_pattern], 2),
        "evidence_strength": "none" if not used else ("weak" if len(used) == 1 else "moderate"),
        "candidates": [{"email": a, "score": round(s, 3)} for a, s in ranked[:6]],
        "email": published_exact or (ranked[0][0] if ranked else None),
        "email_status": "PUBLISHED" if published_exact else "INFERRED",
        "label": None if published_exact else "INFERRED — verify before sending",
    }


def mx_lookup(domain):
    """Best-effort MX check without third-party libs: resolve the domain itself.
    Real MX records need dnspython or `dig`; we report what we could establish."""
    import shutil
    import subprocess
    for tool, args in (("dig", ["+short", "mx", domain]), ("nslookup", ["-type=mx", domain])):
        if shutil.which(tool):
            try:
                out = subprocess.run([tool, *args], capture_output=True, text=True, timeout=10).stdout
                return {"domain": domain, "method": tool, "mx": out.strip() or None,
                        "status": "FOUND" if out.strip() else "UNKNOWN"}
            except Exception as e:  # noqa: BLE001
                return {"domain": domain, "method": tool, "status": "UNKNOWN", "error": str(e)}
    try:
        socket.gethostbyname(domain)
        return {"domain": domain, "method": "A-record", "status": "DOMAIN_RESOLVES_MX_UNKNOWN"}
    except OSError as e:
        return {"domain": domain, "method": "A-record", "status": "UNKNOWN", "error": str(e)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--domain")
    ap.add_argument("--name")
    ap.add_argument("--known", nargs="*", default=[])
    ap.add_argument("--mx")
    a = ap.parse_args(argv)
    if a.mx:
        print(json.dumps(mx_lookup(a.mx), indent=2))
        return 0
    if not (a.domain and a.name):
        ap.error("--domain and --name are required (or use --mx)")
    print(json.dumps(infer(a.domain, a.name, a.known), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
