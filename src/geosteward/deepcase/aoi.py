"""Which committed grids define each event's AOI.

Both the facility and population builders derive their spatial scope from
grids the event has already committed, so neither can quietly cover ground
the event's own evidence does not. The mapping lives here once; a builder
importing it cannot drift from the others.

Multiple grids give multiple bboxes on purpose: Milton's two AOIs sit
200 km apart, and their union envelope would cover open gulf.
"""

EVENT_GRIDS: dict[str, dict] = {
    "eaton-2025": {
        "hazard": "wildfire",
        "grids": ["exposure/dins_h3_r9_damage_grid.geojson"],
    },
    "milton-2024": {
        "hazard": "hurricane",
        "grids": [
            "evidence/bitemporal_h3_r9_grid.geojson",
            "exposure/debris_h3_r9_grid.geojson",
        ],
    },
    "ian-2022": {
        "hazard": "hurricane",
        "grids": ["evidence/crossview_h3_r9_grid.geojson"],
    },
}
