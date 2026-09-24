"""Industry driver library (spec §3–4). Claude refines these from the customer's own words;
the templates guarantee nothing is skipped and the DRIVER → OPERATIONAL → NETWORK → SOLUTION chain is present."""

CHAINS = {
    "guest": ("Guest experience", "Reliable guest internet", "High downstream capacity + predictable availability",
              "Dedicated high-capacity wireless/fibre backhaul"),
    "cctv": ("CCTV / surveillance", "Continuous video transport", "Upstream capacity + low packet loss + resilience",
             "Symmetrical infrastructure network"),
    "scada": ("SCADA / telemetry", "Continuous site telemetry", "High availability + low latency",
              "Protected carrier-grade path"),
    "security": ("Security", "Remote surveillance and access", "Reliable upstream connectivity",
                 "Dedicated backhaul + redundancy"),
    "pos": ("POS / reservations / booking", "Transactions and bookings never stop", "Low latency, high availability, SLA",
            "Business-grade backhaul with failover"),
    "voip": ("VoIP / staff communications", "Clear calls, staff reachable", "Low jitter/latency, QoS",
             "QoS-managed private network"),
    "cloud": ("Cloud systems / remote administration", "Access to cloud ERP, email, management systems",
              "Symmetric capacity, availability", "Business backhaul + managed routing"),
    "intersite": ("Inter-site / multi-building operations", "Buildings and sites work as one network",
                  "Private site-to-site links, capacity per site", "Private PtP/PtMP distribution network"),
    "iot": ("IoT / irrigation / sensors", "Automated monitoring and control", "Wide-area low-rate coverage + backhaul",
            "LoRaWAN/field network on the backhaul"),
    "safety": ("Safety / emergency communications", "Reach people in an emergency", "Resilient, always-on path",
               "Redundant route + backup power"),
    "production": ("Production / control systems", "Operations run without interruption",
                   "Deterministic latency, high availability", "Carrier-grade protected network"),
    "staff": ("Staff accommodation connectivity", "Staff retention and welfare", "Shared capacity, managed",
              "Segmented access network on the backhaul"),
}

INDUSTRY = {
    "hospitality": ["guest", "pos", "voip", "cloud", "cctv", "staff"],
    "game_reserve": ["guest", "pos", "security", "cctv", "intersite", "voip", "safety"],
    "farm": ["iot", "cctv", "voip", "cloud", "staff", "security"],
    "wind": ["scada", "cctv", "security", "cloud", "intersite"],
    "solar": ["scada", "cctv", "security", "cloud"],
    "mining": ["production", "safety", "iot", "cctv", "voip", "cloud"],
    "business": ["cloud", "voip", "cctv", "pos"],
}

KEYWORDS = {
    "game_reserve": ["reserve", "lodge", "safari", "game farm", "anti-poach", "ranger", "conservancy"],
    "hospitality": ["hotel", "guest", "b&b", "guesthouse", "resort", "restaurant", "wedding venue", "lodge"],
    "farm": ["farm", "irrigation", "pivot", "borehole", "orchard", "citrus", "dairy", "livestock", "boerdery"],
    "wind": ["wind farm", "wtg", "turbine", "wind energy"],
    "solar": ["solar", "pv plant", "pv farm"],
    "mining": ["mine", "mining", "quarry", "pit", "shaft", "plant"],
}

SERVICE_HINTS = {
    "cctv": ["cctv", "camera", "surveillance"], "voip": ["voip", "phone", "pbx", "call"],
    "pos": ["pos", "point of sale", "booking", "reservation", "card machine"],
    "guest": ["guest", "wifi", "wi-fi"], "scada": ["scada", "telemetry", "plc"],
    "cloud": ["cloud", "office 365", "microsoft 365", "erp", "email", "sage"],
    "intersite": ["lodges", "sites", "buildings", "link between", "site-to-site", "offices"],
    "security": ["security", "access control", "alarm", "fence"], "staff": ["staff", "accommodation"],
    "iot": ["sensor", "iot", "lorawan", "irrigation", "pump"], "safety": ["emergency", "safety"],
}


def classify(text):
    t = (text or "").lower()
    scores = {ind: sum(t.count(k) for k in kws) for ind, kws in KEYWORDS.items()}
    ind = max(scores, key=scores.get)
    return ind if scores[ind] else "business"


def suggest(text, industry=None):
    """Return a draft driver model. Items the customer actually mentioned are marked stated=True."""
    industry = industry or classify(text)
    t = (text or "").lower()
    keys = list(INDUSTRY.get(industry, INDUSTRY["business"]))
    for k, kws in SERVICE_HINTS.items():
        if any(w in t for w in kws) and k not in keys:
            keys.append(k)
    out = []
    for k in keys:
        d, o, n, s = CHAINS[k]
        out.append({"key": k, "driver": d, "operational": o, "network": n, "solution": s,
                    "stated": any(w in t for w in SERVICE_HINTS.get(k, []))})
    out.sort(key=lambda x: not x["stated"])
    return industry, out
