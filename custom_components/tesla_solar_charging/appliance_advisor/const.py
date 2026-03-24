"""Constants for the appliance advisor module."""

# Presets for quick-adding appliances (users pick a preset, then customize)
APPLIANCE_PRESETS = {
    "dishwasher":      {"name": "Lavastoviglie", "icon": "\U0001f37d\ufe0f", "watts": 2000, "duration": 120},
    "washing_machine": {"name": "Lavatrice",     "icon": "\U0001f455",       "watts": 2000, "duration": 90},
    "oven":            {"name": "Forno",          "icon": "\U0001f525",       "watts": 2500, "duration": 60},
    "dryer":           {"name": "Asciugatrice",   "icon": "\U0001f4a8",       "watts": 2500, "duration": 90},
    "ac":              {"name": "Condizionatore", "icon": "\u2744\ufe0f",     "watts": 1000, "duration": 0},
    "custom":          {"name": "Altro",          "icon": "\U0001f50c",       "watts": 1500, "duration": 60},
}

GREEN_THRESHOLD = 1.1
YELLOW_THRESHOLD = 0.5
BATTERY_NEAR_FULL_SOC = 95.0
BATTERY_NEAR_FULL_FACTOR = 0.5
DEADLINE_URGENT_MINUTES = 30
DEFAULT_RUNNING_THRESHOLD_W = 30.0
DEADLINE_STORE_KEY = "tesla_solar_charging.advisor_deadlines"
DEADLINE_STORE_VERSION = 1
