# /cttx-status

Run a full CTTX system diagnostic and show NII statistics.

## Instructions

1. Run the diagnostic:
```bash
cd /path/to/cttx && python3 engine/cttx_engine.py diagnostic
```

2. Report the system status table, NII property counts, and any FAIL/PARTIAL components.

3. For FAIL components, state the exact blocker and what is needed to resolve it (e.g. "Terrain API: FAIL — set CTTX_TERRAIN_API env var to point to local SRTM service at http://localhost:8080").

4. Show the current NII stats: total properties, by province, by type, by opportunity profile.

5. List any drafts pending human review.
