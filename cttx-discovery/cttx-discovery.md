# /cttx-discovery

Run the CTTX National Discovery Engine to ingest properties into the NII.

## Usage

The user can say things like:
- `/cttx-discovery game reserves and wind farms`
- `/cttx-discovery from file data/input/batch.csv`
- `/cttx-discovery all sources`

## Instructions

1. Parse the user's request to determine discovery sources.

Available OSM sources: `game_reserve`, `wind_farm`, `solar_farm`, `mine`, `lodge_resort`, `hospital`, `substation`

For file input: check for CSV or JSON files in `engine/data/input/`

2. Run discovery:
```bash
# OSM sources
python3 engine/cttx_engine.py discover --sources game_reserve wind_farm

# CSV batch
python3 engine/cttx_engine.py discover --csv engine/data/input/batch.csv

# JSON batch
python3 engine/cttx_engine.py discover --json engine/data/input/batch.json
```

3. Report:
- Total input records
- Records written to NII
- Duplicates skipped
- Any errors
- Updated NII totals by province and type

4. Flag any properties that appear HIGH opportunity based on type (game_reserve, wind_project, solar_project, mine) for immediate pipeline processing.

## CSV Format

Required columns: `name`, `latitude`, `longitude`, `property_type`
Optional: `province`, `municipality`, `area_ha`, `notes`
