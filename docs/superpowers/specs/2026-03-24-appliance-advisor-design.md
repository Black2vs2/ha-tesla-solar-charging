# Appliance Advisor — Design Spec

## Overview

An isolated module within the `tesla_solar_charging` integration that advises household members when to run appliances based on solar surplus, battery state, and grid usage. Designed for non-technical family members using wall-mounted tablets, with technical details accessible for the system owner.

**Audience:** Family members (simple traffic-light view) + owner (technical details in sub-views)
**Display:** Two wall-mounted tablets running HA dashboard
**Control level:** Advice + monitoring (no automation). Smart plugs provide live wattage; the person still starts the appliance.

## Architecture

### Module Structure

```
custom_components/tesla_solar_charging/
    ├── ... (existing files unchanged)
    │
    ├── appliance_advisor/              # Self-contained package
    │   ├── __init__.py                 # Module setup, entity registration, cleanup
    │   ├── const.py                    # Appliance presets, thresholds
    │   ├── advisor.py                  # Core logic: energy state → recommendations
    │   ├── models.py                   # Dataclasses: ApplianceConfig, Recommendation, EnergyState
    │   ├── sensor.py                   # Sensor entities (per-appliance + summary)
    │   └── store.py                    # HA Store for deadlines (avoids config entry reload)
    │
    ├── frontend/
    │   ├── panel.js                    # Existing Tesla Solar panel (add Advisor debug tab)
    │   └── appliance-advisor-card.js   # New custom Lovelace card
```

### Isolation Boundary

The advisor module receives energy state as a simple dataclass — it never imports the coordinator directly:

```python
@dataclass
class EnergyState:
    solar_w: float | None       # For display only. Computed by the coordinator (which has access to all
                                # sensors) before passing into EnergyState. None if not available.
                                # Not used in traffic light formula.
    grid_export_w: float
    battery_soc: float
    battery_power_w: float      # positive = charging, negative = discharging
    tesla_charging_w: float     # Populated from coordinator: current_amps * grid_voltage (0 when not charging)
```

**Note:** `house_load_w` is excluded — the traffic light formula does not need it. `solar_w` is optional and derived for display purposes only; it is not used in the surplus computation.

The coordinator calls `advisor.evaluate(energy_state, appliances)` and receives a list of `Recommendation` objects. This means the advisor can be extracted into a separate integration later by swapping only the energy state source.

### Integration Point

The advisor piggybacks on the existing coordinator's 30-second update cycle. The coordinator passes the current `EnergyState` to the advisor after its own update, and the advisor computes fresh recommendations.

**Placement:** The advisor evaluation runs after grid sensor reads succeed (coordinator lines ~321-322) but is independent of the charging mode (solar/night/disabled). The advisor always runs when grid sensors are available, regardless of whether charging is enabled — because the traffic lights are about household surplus, not about charging the car. If grid sensors are unavailable, the advisor is skipped.

### Entity Registration

The advisor's sensors are registered from the main `sensor.py` via a setup function exported by `appliance_advisor/__init__.py`:

```python
# In main sensor.py async_setup_entry:
from .appliance_advisor import async_setup_advisor_sensors
await async_setup_advisor_sensors(hass, entry, async_add_entities, coordinator)
```

This avoids needing a separate platform entry and keeps the advisor as an internal module.

### Cleanup

`appliance_advisor/__init__.py` exports `async_unload(hass)`, called from the main `async_unload_entry`. This function:
- Unregisters the custom service via `hass.services.async_remove(DOMAIN, "set_appliance_deadline")`
- Cleans up the deadline store

All cleanup is consolidated in this one function — nothing split across files.

## Advisor Logic

### Surplus Formula

```
available_surplus = grid_export_w + (battery_soc > 95% ? battery_charge_w * 0.5 : 0)
                    - tesla_charging_w

For each appliance:
  GREEN  — surplus >= appliance_watts * 1.1   (10% margin)
  YELLOW — surplus >= appliance_watts * 0.5   (partial solar, some grid)
  RED    — surplus < appliance_watts * 0.5    (mostly grid)
```

**Divergence from charging logic:** This formula intentionally differs from `charging_logic.calculate_net_available()`. The charging logic counts total solar budget including what the car already uses (for ramp-up/down decisions). The advisor counts only *uncommitted* surplus visible to the grid, which is correct for appliance decisions since the appliance hasn't started yet.

### Cost Labels (Italian)

| Status | Label    | Meaning                    |
|--------|----------|----------------------------|
| GREEN  | Gratis   | Fully covered by solar     |
| YELLOW | Poco     | Partially from grid        |
| RED    | Costa    | Mostly from grid           |

### Running Detection

When a `power_entity` (smart plug) is configured for an appliance:
- **Running:** `power_entity` value > `running_threshold_w` (default: 30W per appliance, configurable)
- **Off/standby:** `power_entity` value <= `running_threshold_w`

The 30W default avoids false positives from standby power draw (typically 5-15W for most appliances).

### Deadline Logic

Each appliance can optionally have a deadline:

- **`finish_by`** — time the appliance must be done (e.g., 19:30)
- **`start_by`** — latest time to start (e.g., 15:00)
- **`duration_minutes`** — typical cycle length (e.g., 120 min). If 0 (continuous appliances like AC), deadline logic is skipped entirely.

Only one of `finish_by` or `start_by` is set (or neither). If `finish_by` is set, the latest start time is computed as `finish_by - duration_minutes`.

Deadline affects the displayed message:

| Situation | Message |
|-----------|---------|
| GREEN + no deadline | "Gratis — avvia ora" |
| GREEN + deadline far | "Gratis — avvia ora" |
| YELLOW + deadline approaching | "Poco — avvia entro HH:MM" |
| Any status + deadline imminent (< 30 min) | "Avvia adesso!" (urgent, overrides color logic) |
| Deadline passed, not started | "Troppo tardi" |

### Edge Cases

- **Tesla is charging:** Its current draw (`coordinator.current_amps * grid_voltage`, 0 when not charging) is subtracted from available surplus before evaluating appliances.
- **Night / no solar:** All RED, unless Octopus dispatching is active → YELLOW with "Tariffa economica attiva".
- **Smart plug not configured:** `running` and `current_watts` are `null`; traffic light still works based on surplus alone.
- **Battery SOC > 95% contributing:** When the home battery is nearly full and still absorbing, half the charge power is counted as available surplus (the inverter will soon switch to exporting).

## Appliance Configuration

### Dynamic Appliance List

Appliances are **fully user-configurable** — not a fixed list. Users can add, remove, and have multiples of the same type (e.g., 2 dishwashers, 3 ACs, 2 ovens). Each appliance has a unique key (auto-generated slug from name).

### Presets (Quick-Add Templates)

```python
APPLIANCE_PRESETS = {
    "dishwasher":      {"name": "Lavastoviglie", "icon": "🍽️", "watts": 2000, "duration": 120},
    "washing_machine": {"name": "Lavatrice",     "icon": "👕", "watts": 2000, "duration": 90},
    "oven":            {"name": "Forno",          "icon": "🔥", "watts": 2500, "duration": 60},
    "dryer":           {"name": "Asciugatrice",   "icon": "💨", "watts": 2500, "duration": 90},
    "ac":              {"name": "Condizionatore", "icon": "❄️", "watts": 1000, "duration": 0},
    "custom":          {"name": "Altro",          "icon": "🔌", "watts": 1500, "duration": 60},
}
```

Presets populate default values when adding a new appliance. The user can then customize the name, watts, etc.

### Per-Appliance Config (stored in entry.options["appliances"])

```python
# Example: entry.options["appliances"]
{
    "lavastoviglie_cucina_su": {
        "name": "Lavastoviglie Cucina Su",
        "icon": "🍽️",
        "watts": 2000,
        "duration": 120,
        "power_entity": "sensor.plug_lavastoviglie_su_power",  # optional
        "running_threshold_w": 30,                              # optional, default 30
    },
    "lavastoviglie_cucina_giu": {
        "name": "Lavastoviglie Cucina Giù",
        "icon": "🍽️",
        "watts": 2000,
        "duration": 120,
        "power_entity": null,
    },
    "ac_salotto": {
        "name": "AC Salotto",
        "icon": "❄️",
        "watts": 1000,
        "duration": 0,
        "power_entity": null,
    },
    # ... etc
}
```

Keys are auto-generated slugs from the appliance name (e.g., "Lavastoviglie Cucina Su" → "lavastoviglie_cucina_su"). Users manage appliances via the integration's options flow (step 4: "appliances"), which provides add/edit/remove.

### Initial Setup

On first install, the appliances list starts empty. The options flow step 4 guides the user to add appliances from presets. This avoids assuming what appliances the household has.

### Deadline Storage (HA Store, not config entry)

Deadlines are stored via `homeassistant.helpers.storage.Store` (file-based persistence), **not** in `entry.options`. This is critical: updating `entry.options` triggers `_async_update_listener` which reloads the entire integration. Deadlines change frequently (family members setting them from tablets) and must not cause reloads.

```python
# Store file: .storage/tesla_solar_charging.advisor_deadlines
{
    "lavastoviglie_cucina_su": {"type": "finish_by", "time": "19:30"},
    "ac_salotto": {"type": "none", "time": null},
}
```

The `Store` is loaded on startup and updated via the `set_appliance_deadline` service. Duration for deadline computation comes from the appliance config (not duplicated in the deadline).

Family members edit deadlines via the custom Lovelace card (tap an appliance → inline time picker), which calls the service:

```python
# Service: tesla_solar_charging.set_appliance_deadline
# Data: {"appliance": "lavastoviglie_cucina_su", "type": "finish_by", "time": "19:30"}
```

## Entities Created

### Unique ID Pattern

All advisor entities use the pattern `{entry_id}_advisor_{appliance_key}`, consistent with the existing integration convention. HA auto-generates entity_ids from the entity name and integration name.

### Summary Sensor

- **`sensor.tesla_solar_charging_appliance_advisor_summary`**
  - Unique ID: `{entry_id}_advisor_summary`
  - State: "4 di 6 gratis" (count of green appliances)
  - Attributes: list of all appliances with their full status (including name, icon)

### Per-Appliance Sensors

One sensor per configured appliance (dynamically created):

- **Unique ID:** `{entry_id}_advisor_{appliance_key}`
- **State:** "green" / "yellow" / "red"
- **Attributes:**
  - `appliance_name` — display name (e.g., "Lavastoviglie Cucina Su")
  - `appliance_icon` — emoji icon
  - `reason` — Italian explanation
  - `cost_label` — "Gratis" / "Poco" / "Costa"
  - `running` — bool (from smart plug, or null if no plug configured)
  - `current_watts` — float (from smart plug, or null)
  - `deadline_message` — "Avvia entro 17:30" / "Avvia adesso!" / null
  - `latest_start_time` — computed latest start as HH:MM, or null

### Custom Service

- **`tesla_solar_charging.set_appliance_deadline`** — allows the custom card to update deadline config per appliance without causing integration reload. Requires `services.yaml` descriptor.

## Dashboard — Custom Lovelace Card

### Why a Custom Card

The dashboard requires dynamic gradient backgrounds, pulsing glow effects, inline time pickers, and tight visual integration between the status banner and appliance grid. Standard HA cards (Mushroom, entities, etc.) cannot achieve this. A custom Lovelace card (`appliance-advisor-card.js`) provides full control over rendering and interaction.

This follows the same pattern as the existing `frontend/panel.js` — a web component registered with `customElements.define`, served as a static asset by the integration.

### Card Configuration (in dashboard YAML)

```yaml
type: custom:appliance-advisor-card
entity: sensor.tesla_solar_charging_appliance_advisor_summary
solar_entity: sensor.solar_production
battery_soc_entity: sensor.esp32_deye_inverter_battery_soc
tesla_soc_entity: sensor.tesla_di_luca_battery
```

Minimal config — the card reads all appliance data (including names and icons) from the summary sensor's attributes. No hardcoded appliance list in the card.

### Card Layout — Layout A (Status Banner + Grid)

**Top section — Status Banner:**
- Full-width colored banner with gradient background
  - Green gradient: running mostly on solar
  - Yellow gradient: mixed solar/grid
  - Red gradient: mostly grid
- Shows "STATO CASA" + status text (e.g., "Solare al 100%")
- Three key metrics below: Solare (kW), Batteria (%), Tesla (%)
- Large fonts: 32px status, 26px metrics — readable from 2+ meters

**Middle section — Appliance Grid:**
- 2-column grid of appliance cards (dynamic — adapts to however many appliances are configured)
- Each card: emoji icon (32px), appliance name (20px), cost label (18px)
- Names and icons come from the sensor attributes (not hardcoded in JS)
- Left border colored by status (green/yellow/red, 5px)
- When running (smart plug detected): pulsing glow effect + live wattage displayed
- When deadline is close: deadline message replaces cost label
- Tap an appliance card → expands inline to show deadline time picker (calls `set_appliance_deadline` service)

**Bottom section — Navigation:**
- Row of large buttons: Dettaglio, Meteo, Comandi, Camera
- 16px text, 14px padding — easy tablet touch targets
- Navigation paths configurable in card YAML

### Static Asset Registration

The card JS file is registered alongside the existing panel in the same `async_register_static_paths` call, using keyword arguments consistent with existing code:

```python
StaticPathConfig(
    url_path=f"/{DOMAIN}/appliance-advisor-card.js",
    path=str(Path(__file__).parent / "frontend" / "appliance-advisor-card.js"),
    cache_headers=True,
)
```

Cache-busted via `?v={VERSION}` query string, same pattern as the existing panel.

## Existing Panel — Advisor Debug Tab

### Addition to panel.js

The existing `frontend/panel.js` (Tesla Solar sidebar panel) gets a new tab: **"Advisor"**. This tab shows technical/debug info for the appliance advisor:

- **All appliance states** — table with key, name, status, surplus, watts, running, current_watts, deadline, latest_start
- **Energy state snapshot** — grid_export_w, battery_soc, battery_power_w, tesla_charging_w, surplus
- **Deadline store contents** — raw JSON of all deadlines
- **Copy JSON button** — copies the full advisor debug state as JSON to clipboard (same pattern as existing Debug card's Copy button)

This reuses the existing panel's tab/card pattern and CSS. The advisor data comes from the summary sensor's attributes plus the per-appliance sensor attributes.

## Future Considerations (Not in Scope)

- **Auto-learning wattage:** When a smart plug is configured, track average draw per cycle and auto-update the `watts` default over time.
- **Appliance state detection:** Infer cycle start/end from power patterns (e.g., dishwasher draws 2000W then drops to 0 = cycle complete).
- **Notifications:** Telegram alert when a deadline is approaching and the appliance hasn't started.
- **Separate integration:** Extract `appliance_advisor/` into its own `solar_home_manager` integration.
