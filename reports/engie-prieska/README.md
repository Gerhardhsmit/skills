# Engie / MBP Prieska Solar PV: alternate point of entry (desktop screen)

Deal: RD-14, Engie via Paratus SA (Johan Wolfaardt). Trigger: Duane Forlee (Vodacom), 2 Oct 2026 16:15. Vodacom has non-R1 coverage at 4 of the 5 Engie sites. Prieska is the limited one. CTTX was asked to look at a point of entry from two towers.

Site pin: -30.0220257, 22.3551282 (Google pin for the plant, not a confirmed delivery point). SRTM ground level is 1,100 m.

| Path | Distance | Bearing tower→site | Tower ground | Result (SRTM, k=4/3) |
|---|---|---|---|---|
| T2 Alkantpan CEN_64770 (-29.95869, 22.30183) | 8.71 km | 144° | 1,084 m | Clear. ≥60% F1 at 5.8 GHz with a 20 m tower mount and a 6 m site pole. At 18 GHz the clearance is ≥150%. |
| T1 (-29.95972, 22.41956), not in the CTTX mast dataset | 9.30 km | 222° | 1,114 m | Clear with a higher mount. The ridge at 4.3 km (1,119 m) needs a ≥30 m tower mount and a ≥10 m site mast at 5.8 GHz. At 18 GHz, 30 m / 6 m is enough. A 20 m tower mount gives only partial Fresnel clearance. |

**Recommendation:** use T2 (Alkantpan) as primary. It is shorter, needs lower mounting heights and has the better profile. Use T1 as the diverse backup path. The two towers are 11.3 km apart and approach the site from opposite sides.

## Caveats (NOT VERIFIED)
- SRTM is from 2000, before the PV plant was built. PV trackers, buildings, the substation and fencing are not modelled. The site-end mount has to clear the arrays, so plan for 10 m or more until a site survey is done.
- Tower heights and free aperture on both towers are unknown. Vodacom must confirm them.
- The exact delivery point (O&M building, substation or control room) is unknown. Moving it changes the profile.
- This is a desktop screen. It is not a LINKPlanner design. Before the price is firm: LINKPlanner by Abel → site survey → confirm the licensed (SIAE) or unlicensed band.

Files: `prieska_poe_profiles.png`, `T1_profile.csv`, `T2_profile.csv`, `prof.py` (terrain source: AWS SRTM 1-arcsec tiles S30E022/S31E022).
