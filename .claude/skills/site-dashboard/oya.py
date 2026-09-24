#!/usr/bin/env python3
"""OYA fibre tracker: merge parsed reports and print the dashboard.

Usage:
    python3 .claude/skills/site-dashboard/oya.py dashboard
    python3 .claude/skills/site-dashboard/oya.py add <reports.json | ->

`add` takes a JSON list of reports, each with: wtg, date (DD/MM/YYYY or ISO),
location, splices, rmu, mate_mask, tested, drawing (bool), ac_lc,
challenges, photos (bool), sender. It merges them into data/progress.json
and then prints the dashboard.
"""
import datetime
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PROGRESS = os.path.join(ROOT, "data", "progress.json")


def load():
    if not os.path.exists(PROGRESS):
        return {"project": "OYA Wind Farm — Fiber Optic", "turbines": 18, "last_updated": "", "wtg": {}}
    with open(PROGRESS) as f:
        return json.load(f)


def save(d):
    with open(PROGRESS, "w") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.write("\n")


def norm_wtg(raw):
    m = re.search(r"(\d+)", str(raw))
    return f"WTG-{int(m.group(1)):02d}"


def iso_date(s):
    """Accept DD/MM/YYYY (WhatsApp) or YYYY-MM-DD; return YYYY-MM-DD."""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(str(s).strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return str(s)


def date_key(s):
    return iso_date(s)


def has_challenge(text):
    return bool(text) and text.strip().lower() not in ("no", "none", "n", "-", "nil")


def add(reports):
    d = load()
    for r in reports:
        key = norm_wtg(r["wtg"])
        w = d["wtg"].setdefault(key, {"total_splices": 0, "total_ac_lc_changes": 0, "rmu_completed": 0,
                                      "mate_mask_completed": 0, "drawing_marked": False, "tested": 0,
                                      "has_challenges": False, "daily_reports": []})
        w.setdefault("daily_reports", [])
        entry = {
            "date": iso_date(r.get("date", "")), "location": r.get("location", ""),
            "splices_completed": int(r.get("splices", 0) or 0), "rmu_completed": int(r.get("rmu", 0) or 0),
            "mate_mask_completed": int(r.get("mate_mask", 0) or 0), "total_tested": int(r.get("tested", 0) or 0),
            "drawing_marked": bool(r.get("drawing")), "ac_lc_changes": int(r.get("ac_lc", 0) or 0),
            "challenges": r.get("challenges", "No"), "photos": bool(r.get("photos")), "sender": r.get("sender", ""),
        }
        same = next((e for e in w["daily_reports"]
                     if e["date"] == entry["date"] and e.get("location", "") == entry["location"]), None)
        if same and entry["splices_completed"] < same["splices_completed"]:
            continue  # duplicate with a lower count: keep the higher one
        old = same or {"splices_completed": 0, "ac_lc_changes": 0}
        w["total_splices"] += entry["splices_completed"] - old["splices_completed"]
        w["total_ac_lc_changes"] += entry["ac_lc_changes"] - old["ac_lc_changes"]
        if same:
            same.update(entry)
        else:
            w["daily_reports"].append(entry)
        latest = max(w["daily_reports"], key=lambda e: e["date"])
        if latest["total_tested"]:
            w["tested"] = latest["total_tested"]
        for k in ("rmu_completed", "mate_mask_completed"):
            if entry[k]:
                w[k] = entry[k]
        w["drawing_marked"] = w["drawing_marked"] or entry["drawing_marked"]
        w["has_challenges"] = w["has_challenges"] or has_challenge(entry["challenges"])
    d["last_updated"] = datetime.date.today().isoformat()
    save(d)
    return d


def status(w):
    if not w or not w.get("total_splices"):
        return "🔴 No report"
    if w.get("tested", 0) < w["total_splices"]:
        return "⚠ Untested"
    if not w.get("drawing_marked"):
        return "📋 Drawing pending"
    return "✅ Complete"


def dashboard(d):
    n = d.get("turbines", 18)
    keys = [f"WTG-{i:02d}" for i in range(1, n + 1)]
    out = ["OYA PROJECT — FIBER OPTIC PROGRESS DASHBOARD", "=" * 45, f"Last updated: {d.get('last_updated', '-')}", "",
           "WTG    | Splices | Tested | RMU | M/M | Drawing | AC→LC | OTDR   | Status",
           "-------|---------|--------|-----|-----|---------|-------|--------|-------------"]
    groups = {"⚠ Untested": [], "📋 Drawing pending": [], "🔴 No report": [], "✅ Complete": []}
    challenges, otdr_fail, recent = [], [], []
    for k in keys:
        w = d["wtg"].get(k)
        s = status(w)
        groups[s].append(k)
        if not w or not w.get("total_splices"):
            out.append(f"{k} |    -    |   -    |  -  |  -  |    -    |   -   |   -    | {s}")
            continue
        otdr = w.get("otdr_results", [])
        fails = [o for o in otdr if o.get("result") == "FAIL"]
        otdr_txt = f"{len(otdr) - len(fails)}/{len(otdr)}" if otdr else "-"
        for o in fails:
            f = o.get("fault", {})
            otdr_fail.append(f"{k} {o['span']} {o['fiber']}" + (f" — {f.get('loss_db')} dB @ {f.get('position_km')} km" if f else ""))
        out.append(f"{k} | {w['total_splices']:^7} | {w.get('tested', 0):^6} | {w.get('rmu_completed', 0):^3} | "
                   f"{w.get('mate_mask_completed', 0):^3} | {'Y' if w.get('drawing_marked') else 'N':^7} | "
                   f"{w.get('total_ac_lc_changes', 0):^5} | {otdr_txt:^6} | {s}")
        for e in w.get("daily_reports", []):
            recent.append((date_key(e["date"]), k, e))
            if has_challenge(e.get("challenges")):
                challenges.append(f"{k}: {e['challenges']}")
    active = [w for w in d["wtg"].values() if w.get("total_splices")]
    out += ["", "SUMMARY", "-------",
            f"Total splices logged:     {sum(w['total_splices'] for w in active)}",
            f"Total AC→LC changes:      {sum(w.get('total_ac_lc_changes', 0) for w in active)}",
            f"Turbines with activity:   {len(active)}/{n}",
            f"Turbines fully complete:  {len(groups['✅ Complete'])}/{n}",
            "", "ACTION ITEMS", "------------",
            f"⚠ Untested splices at: {', '.join(groups['⚠ Untested']) or 'none'}",
            f"📋 Drawings not marked: {', '.join(groups['📋 Drawing pending']) or 'none'}",
            f"🔴 No report received: {', '.join(groups['🔴 No report']) or 'none'}",
            f"❌ OTDR failures: {'; '.join(otdr_fail) or 'none'}",
            f"💬 Active challenges: {'; '.join(challenges) or 'none'}"]
    if recent:
        out += ["", "RECENT REPORTS", "--------------"]
        for _, k, e in sorted(recent, key=lambda x: x[0], reverse=True)[:5]:
            who = f" ({e['sender']})" if e.get("sender") else ""
            out.append(f"{e['date']} {k} — {e['splices_completed']} splices, {e['ac_lc_changes']} AC→LC changes{who}")
    return "\n".join(out)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "dashboard"
    if cmd == "add":
        src = sys.argv[2] if len(sys.argv) > 2 else "-"
        reports = json.load(sys.stdin if src == "-" else open(src))
        print(dashboard(add(reports if isinstance(reports, list) else [reports])))
    elif cmd == "dashboard":
        print(dashboard(load()))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
