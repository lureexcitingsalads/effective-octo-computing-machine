"""Standard pre-shift inspection checklist for heavy equipment. Fixed rather than
per-equipment-configurable for now -- these items are broadly standard across machine
types, and keeping this simple avoids needing a whole template-editing UI for v1."""

CHECKLIST = [
    ("engine_oil", "Engine oil level"),
    ("coolant", "Coolant level"),
    ("hydraulic_fluid", "Hydraulic fluid level"),
    ("fuel", "Fuel level"),
    ("leaks", "Visible leaks (fuel / oil / hydraulic)"),
    ("tracks_tires", "Tracks or tires condition"),
    ("hoses_belts", "Hoses and belts condition"),
    ("lights", "Lights and backup alarm"),
    ("mirrors_visibility", "Mirrors / visibility"),
    ("seatbelt", "Seatbelt and ROPS/FOPS"),
    ("fire_extinguisher", "Fire extinguisher present and charged"),
    ("gauges_warning_lights", "Gauges and warning lights on startup"),
    ("controls", "Controls operate smoothly"),
    ("brakes", "Brakes / parking brake"),
    ("structure", "Structure and attachment points (cracks, damage)"),
]

# Items serious enough that a single failure alone should raise severity to "high".
CRITICAL_ITEMS = {"brakes", "structure"}
