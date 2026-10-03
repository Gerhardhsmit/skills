#!/usr/bin/env python3
"""Hybrid network page: dedicated carrier links (Vodacom Business Connect from the mast) + the client's
own private backbone, drawn as one picture, with the carrier monthly cost and the break-even test.

    python3 hybrid_offer.py plan.json prices.json --primary 200 --backup 50 --out hybrid.html

plan.json   from site_workup.py (sites + links with roles "carrier option" / "carrier backup" / "backbone")
prices.json built AT RUN TIME from Notion "Vodacom Products & Pricing" (client price, 36 m, ex VAT, at the
            recommended markup). NEVER commit it: cost and price data stay out of this public repo.
            {"source": "...", "term_months": 36,
             "business_connect_client_ex_vat": {"50": .., "100": .., "200": ..},
             "nrc_client_ex_vat": ..}
Honesty rules: the incumbent's spend is UNKNOWN until the client shares it, so the page states a
break-even ("if your sites pay more than R X a month today, this is cheaper"), never "we beat your
provider". The owned backbone CAPEX comes from infrastructure-project-quoting-estimation after the
site walk; it is not priced here.
"""
import argparse, json, os, sys

VAT = 0.15


def money(x):
    return f"R{x:,.0f}".replace(",", " ")


def carrier_cost(prices, primary, backup=None):
    bc = prices["business_connect_client_ex_vat"]
    lines = [("Dedicated link into the hub", primary, bc[str(primary)])]
    if backup:
        lines.append(("Second dedicated link, different mast", backup, bc[str(backup)]))
    mrc = sum(l[2] for l in lines)
    nrc = prices["nrc_client_ex_vat"] * len(lines)
    return {"lines": lines, "mrc_ex_vat": round(mrc, 2), "mrc_incl_vat": round(mrc * (1 + VAT), 2),
            "nrc_ex_vat": round(nrc, 2), "term_months": prices.get("term_months", 36)}


def diagram(plan, w=520, h=300):
    """Layered picture: carrier network -> dedicated links -> owned backbone -> sites -> services."""
    S = plan["sites"]
    carriers = [n for n, s in S.items() if s.get("role") == "carrier"]
    relays = [n for n, s in S.items() if s.get("role") == "relay"]
    sites = [n for n, s in S.items() if s.get("role") not in ("carrier", "relay")]
    hub_links = {l["b"] if l["a"] in carriers else l["a"]: l for l in plan["links"] if "carrier" in l.get("role", "")}
    out = [f'<svg viewBox="0 0 {w} {h}" class="hyb">']
    labels = []
    def band(y, hh, label, cls):
        out.append(f'<rect x="8" y="{y}" width="{w-16}" height="{hh}" rx="8" class="{cls}"/>')
        labels.append(f'<rect x="12" y="{y+4}" width="{len(label)*5.3+10:.0f}" height="12" rx="3" class="{cls}"/>'
                      f'<text x="16" y="{y+13}" class="lbl">{label}</text>')
    band(8, 52, "CARRIER · Vodacom network, dedicated 1:1 links from the mast", "b1")
    band(78, 110, "YOUR NETWORK · owned by you, built and supported by CTTX", "b2")
    band(206, 86, "WHAT RIDES ON IT", "b3")
    pos = {}
    for i, c in enumerate(carriers):
        x = w * (i + 1) / (len(carriers) + 1); pos[c] = (x, 42)
        out.append(f'<rect x="{x-46}" y="30" width="92" height="22" rx="5" class="car"/>'
                   f'<text x="{x}" y="45" text-anchor="middle" class="t">{c}</text>')
    row = relays + sites
    for i, n in enumerate(row):
        x = 24 + (w - 48) * (i + 0.5) / len(row)
        y = 128 if n in relays else 164
        pos[n] = (x, y)
    for l in plan["links"]:
        a, b = pos[l["a"]], pos[l["b"]]
        cls = "lc" if "carrier" in l.get("role", "") else "lb"
        dash = ' stroke-dasharray="5 4"' if l.get("role") == "carrier backup" else ""
        out.append(f'<line x1="{a[0]:.0f}" y1="{a[1]:.0f}" x2="{b[0]:.0f}" y2="{b[1]:.0f}" class="{cls}"{dash}/>')
    for n in row:
        x, y = pos[n]
        cls = "nr" if n in relays else ("nh" if n in hub_links else "ns")
        out.append(f'<circle cx="{x:.0f}" cy="{y}" r="7" class="{cls}"/>'
                   f'<text x="{x:.0f}" y="{y+19}" text-anchor="middle" class="t">{n}</text>')
    services = plan.get("services", ["Herd & parlour systems", "Irrigation & pump alarms", "Cameras & gates", "Voice & office"])
    for i, sv in enumerate(services):
        x = 16 + (w - 32) * i / len(services)
        out.append(f'<rect x="{x+4}" y="232" width="{(w-32)/len(services)-8:.0f}" height="34" rx="6" class="sv"/>'
                   f'<text x="{x+(w-32)/len(services)/2:.0f}" y="253" text-anchor="middle" class="t">{sv}</text>')
    out.extend(labels)  # band labels on top of the lines
    out.append(f'<text x="{w-16}" y="284" text-anchor="end" class="lbl2">One network, one SLA, one support desk</text></svg>')
    return "".join(out)


CSS = """.hyb{width:100%;display:block}.hyb .b1{fill:#1b1416;stroke:#5a2a2a}.hyb .b2{fill:#141a14;stroke:#2f5a3a}
.hyb .b3{fill:#13161b;stroke:#2a3340}.hyb .lbl{fill:#edb230;font-size:8px;letter-spacing:1px;font-weight:700}
.hyb .lbl2{fill:#98a0a8;font-size:8px}.hyb .t{fill:#e8ecef;font-size:8.5px}.hyb .car{fill:#5a2323;stroke:#c0392b}
.hyb .lc{stroke:#e0574a;stroke-width:2.5}.hyb .lb{stroke:#3fbf73;stroke-width:2.5}.hyb .nr{fill:#e0a100}
.hyb .nh{fill:#e8ecef;stroke:#e0574a;stroke-width:2}.hyb .ns{fill:#1d2b3a;stroke:#e8ecef;stroke-width:1.5}
.hyb .sv{fill:#1a1e24;stroke:#2a3340}"""


def page(plan, prices, primary, backup, n_sites_today, area=""):
    c = carrier_cost(prices, primary, backup)
    rows = "".join(f"<tr><td>{d}</td><td>{m} Mbps, uncontended 1:1, symmetrical</td><td>{money(v)}</td></tr>" for d, m, v in c["lines"])
    per_site = c["mrc_ex_vat"] / max(n_sites_today, 1)
    return c, f"""<style>{CSS}</style>{diagram(plan)}
<table class="lp" style="margin-top:8px"><tr><th>Carrier service</th><th>What it is</th><th>Per month, ex VAT</th></tr>{rows}
<tr><td><b>Total carrier, {c['term_months']}-month term</b></td><td>Vodacom Business Connect, supplied by CTTX</td><td><b>{money(c['mrc_ex_vat'])}</b></td></tr></table>
<p style="font-size:9pt;margin-top:6px">Once-off connection {money(c['nrc_ex_vat'])} ex VAT. Subject to Vodacom feasibility at each site.
<b>The test:</b> if your {n_sites_today} {area + " " if area else ""}sites together pay more than <b>{money(c['mrc_ex_vat'])}</b> a month today
(about {money(per_site)} per site), the hybrid costs less on the carrier side alone, and every site moves from shared
internet to dedicated, uncontended capacity. The owned backbone is a once-off build, priced after the site walk.</p>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan"); ap.add_argument("prices")
    ap.add_argument("--primary", type=int, required=True); ap.add_argument("--backup", type=int)
    ap.add_argument("--sites-today", type=int, help="sites that buy their own service today (default: non-relay sites)")
    ap.add_argument("--area", default="", help='e.g. "Golden Valley"')
    ap.add_argument("--out", default="hybrid.html")
    o = ap.parse_args()
    plan = json.load(open(o.plan)); prices = json.load(open(o.prices))
    n = o.sites_today or sum(1 for s in plan["sites"].values() if s.get("role") not in ("carrier", "relay"))
    c, html = page(plan, prices, o.primary, o.backup, n, o.area)
    with open(o.out, "w") as f:
        f.write(html)
    print(json.dumps(c, indent=1))


if __name__ == "__main__":
    sys.exit(main())
