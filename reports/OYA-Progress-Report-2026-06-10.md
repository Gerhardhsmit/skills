# OYA WIND ENERGY FACILITY
## Fiber Optic Installation — Field Progress Report
**Report Date:** 10 June 2026
**Prepared by:** Site Manager — OYA Fiber Team
**Field Technician:** Freddy Mackay
**Submitted to:** Specafrica / Sinohydro
**Project Reference:** ZA-OYA0-EN-EL-CC-9526 (WEF Fibre Optic Single Line Diagram REV 7)

---

## 1. EXECUTIVE SUMMARY

Fiber optic splicing and termination works are actively progressing across the OYA Wind Energy Facility. As of 10 June 2026, splicing has been completed at WTG-07, WTG-08, and WTG-09, with OTDR testing confirmed passing on all inter-turbine spans from WTG-01 through to WTG-04. One fiber fault has been identified on the WTG-01 to PV route and is flagged for remedial action.

---

## 2. WORK COMPLETED — PERIOD TO 10 JUNE 2026

| Turbine | Splices Completed | AC→LC Connector Changes | Location | Date |
|---------|------------------|------------------------|----------|------|
| WTG-07  | 24               | 12                     | Main tray | 10 Jun 2026 |
| WTG-08  | 24               | 12                     | Main tray | 10 Jun 2026 |
| WTG-09  | 8                | 0                      | Basement dome | 10 Jun 2026 |
| WTG-09  | 20               | 10                     | Main tray | 10 Jun 2026 |
| **TOTAL** | **76**         | **34**                 | | |

**Notes:**
- WTG-09 basement splices expand through-fiber capacity to accommodate WTG-11 future connection
- Additional overhead fiber splices completed at WTG-09 main tray
- Dome closure installed between WTG-08 and WTG-09 on inter-turbine cable route
- All work performed in accordance with port layout: ports 1–12 mainline input, 13–24 mainline output, 25–28 RMU, 29–32 Met Mast, 33–36 spare

---

## 3. OTDR TEST RESULTS — WTG-01 TO WTG-04

All testing performed using EXFO MaxTester, 1310 nm, SM/9µm single-mode fiber.

### 3.1 Inter-Turbine Spans

| Span | Fibers Tested | Result | Distance |
|------|--------------|--------|----------|
| WTG-01 → WTG-02 | F1, F2, F3, F4 | ✅ ALL PASS | ~1.96 km |
| WTG-02 → WTG-03 | F1, F2, F4, F13, F15, F16 | ✅ ALL PASS | ~0.79–1.8 km |
| WTG-03 → WTG-02 | F1, F2, F3, F4 | ✅ ALL PASS | ~0.8 km |
| WTG-03 → WTG-04 | F13, F15, F16 | ✅ ALL PASS | ~2.0 km |

### 3.2 PV Connection — WTG-01

| Fiber | Result | Notes |
|-------|--------|-------|
| F01 | ❌ **FAIL** | High loss event at 4.927 km — 4.216 dB splice loss, 43.77 dB/km attenuation. Resplice required. |
| F02 | ✅ PASS | Cumulative loss 2.542 dB — within spec |
| F03 | ✅ PASS | End reflectance >-19.6 dB — acceptable |
| F04 | ✅ PASS | Clean trace |

**Test Summary: 22 tests conducted — 21 PASS / 1 FAIL (95.5% pass rate)**

---

## 4. OUTSTANDING ISSUES & ACTION ITEMS

| # | Issue | Location | Action Required | Priority |
|---|-------|----------|----------------|----------|
| 1 | Fiber fault — high splice loss 4.216 dB | WTG-01 → PV route, 4.927 km | Locate joint at ~4.93 km, resplice or replace connector | HIGH |
| 2 | OTDR testing not yet commenced | WTG-04 through WTG-18 | Testing to proceed as splicing advances | MEDIUM |
| 3 | As-built drawings not yet marked | All turbines | Mark completed splices, tested spans, and connector changes on drawing | MEDIUM |
| 4 | AC→LC connector changes pending | WTG-01 (yellow pigtails visible) | Complete connector upgrades at WTG-01 tray | MEDIUM |

---

## 5. SITE PHOTOS

The following photos were submitted by field technicians on 10 June 2026:

**WTG-07** — Splice tray completed. Colored pigtails (mainline input, ports 1–12) and white pigtails (mainline output, ports 13–24) terminated. LC connectors installed along front panel.

**WTG-08** — Splice tray installed and terminated. Both mainline input and output fiber groups completed.

**WTG-09** — Splice tray mounted and populated with LC connectors. Overhead fiber additions confirmed.

**WTG-09 Basement** — Dome splice enclosure installed and mounted on cable ladder in tower base. Carries through-fiber for WTG-11 route expansion.

**Dome — WTG-08/09 inter-turbine** — Inline dome splice closure installed on overhead cable between WTG-08 and WTG-09.

**WTG-01 Splice Tray** — Tray labeled: ports 1–12 to WTG-02 (mainline), ports 13–32 overhead fiber (OVH). Currently carrying yellow (old-type) pigtails on overhead zone — AC→LC connector changes pending.

---

## 6. NETWORK TOPOLOGY — CONFIRMED FIELD OBSERVATIONS

Based on field drawings and site verification:
- Fiber ring chain: WTG-01 → WTG-02 → WTG-03 → ... → WTG-18
- Two Eskom OPGW feeds into network backbone
- RMU dome splices located at: WTG-03, WTG-07, WTG-09
- Vodacom mast termination confirmed on network
- PV plant fiber connection off WTG-01

---

## 7. PLANNED WORK — NEXT PERIOD

- Continue splicing at WTG-10 through WTG-12
- Resolve fiber fault on WTG-01 → PV F01 route
- OTDR testing to advance in line with completed splicing
- Update as-built drawings at all completed turbines
- Complete remaining AC→LC connector changes at WTG-01

---

## 8. OVERALL PROJECT PROGRESS

| Category | Status |
|----------|--------|
| Turbines spliced (full) | 3 / 18 (WTG-07, WTG-08, WTG-09) |
| Turbines with partial/testing work | 3 / 18 (WTG-01, WTG-02, WTG-03) |
| Turbines not yet started | 12 / 18 |
| OTDR spans tested and passed | 14 spans |
| OTDR spans with faults | 1 (WTG-01→PV F01) |
| Drawings marked | 0 / 18 |
| Total splices to date | 76 |
| Total AC→LC changes | 34 |

---

*Report compiled from daily field technician WhatsApp reports and OTDR test photographs submitted on 10 June 2026.*
*Field work conducted and documented by Freddy Mackay.*
*All OTDR tests performed on EXFO MaxTester unit 084 464 2245.*
