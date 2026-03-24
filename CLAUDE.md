# Tesla Solar Charging — System Documentation

## What This Is

A Home Assistant custom integration that automatically charges a Tesla using solar excess energy via BLE (ESP32), with evening planning, night charging (Octopus Energy Italy), and multi-source weather forecasting.

**Owner:** @black2vs2 (Luca)
**Location:** Italy, home zone is "Piano di sotto" (ground floor)
**Hardware:** Deye hybrid inverter, 10.44 kWp solar (18x 580W panels, east/west split), 14 kWh home battery, Tesla with 75 kWh battery
**BLE Control:** ESP32 running ESPHome, communicates with Tesla via BLE

## Architecture Overview

```
Solar Panels (10.44 kWp)
    |
Deye Hybrid Inverter ──> Home Battery (14 kWh)
    |                         |
    |── House Load            |
    |── Grid (import/export)  |
    |                         |
ESP32 (ESPHome) ──BLE──> Tesla (75 kWh)
    |
Home Assistant ──> This Integration
```

### Control Loop (30-second cycle)

```
coordinator._async_update_data()
    ├── BLE health check
    ├── Detect mode:
    │   ├── Octopus dispatching? → Night mode (grid-limited charging)
    │   ├── Sun is up? → Solar mode (excess-based charging)
    │   └── Night, no dispatch → Wait for sunrise
    └── Execute mode handler
```

## Key Design Decisions

### 1. Home Battery Always Has Priority

The car NEVER drains the home battery. The code only counts **grid export** (energy being wasted to grid) as available for the car. If the battery is discharging, that power is subtracted from available amps.

```
net_available = grid_export_amps - safety_buffer - battery_discharge_amps
```

The Deye inverter itself prioritizes battery over export. We don't fight the inverter — we only use what it decides to export.

### 2. Battery SOC Threshold (98%) with Smart Override

The car can't start charging until the home battery reaches 98% SOC. This prevents the car from stealing energy the battery needs.

**Exception 1 — High export:** If grid export exceeds 2x `min_export_power` (default 1800W), the car starts even below 98%. This handles sunny midday when there's clearly enough for both.

**Exception 2 — Battery at threshold but still absorbing:** When battery hits 98% but the inverter is still pushing power into it (grid export = 0), the car starts at minimum amps (5A). The ramp-up logic will adjust once the inverter switches to exporting. Without this, the car would be stuck waiting for export that only comes when the battery hits 100%.

### 3. BLE via ESP32 (Not Tesla API)

Charging is controlled via BLE through an ESP32 running ESPHome. The integration calls HA services on ESPHome entities:

- `switch.tesla_ble_charger` — start/stop charging
- `number.tesla_ble_charging_amps` — set charging amps (5-28A)
- `number.tesla_ble_charging_limit` — set charge limit on the car
- `button.tesla_ble_wake_up` — wake the vehicle

The `number.tesla_charge_limit` slider (created by this integration) pushes to the car's BLE entity when changed.

### 4. Multi-Source Forecast Blending

Three forecast sources are blended with weighted averaging:

| Source | Weight | Notes |
|--------|--------|-------|
| Open-Meteo | 1.0 | Always available, free, radiation-based |
| Solcast | 1.5 | Higher trust, has P10/P50/P90 confidence bands |
| Forecast.Solar | 1.0 | Additional cross-reference |

Solcast supports **comma-separated resource IDs** for split PV arrays (east: `4fa8-bf13-e729-2dd9`, west: `1ad8-9b68-e049-8553`). Forecasts from both arrays are summed per day.

A rolling **correction factor** (actual/forecast ratio over 30 days, clamped 0.3–2.0) adjusts forecasts. A **seasonal correction factor** uses only current-month data (requires 3+ days).

### 5. PVGIS Monthly Baselines

On startup, fetches 15-year average monthly horizontal irradiance from the EU JRC PVGIS API (`MRcalc` endpoint with `horirrad=1`). Returns per-year entries that are averaged per month. Used for seasonal correction in the forecast tracker.

**API quirks:**
- Year range limited to 2005–2020
- Requires `horirrad=1` parameter to include `H(h)_m` field
- `monthly` is a list (not a dict with `"fixed"` key like `PVcalc`)

### 6. Night Mode (Octopus Energy Italy)

When Octopus dispatches a cheap-rate window:
1. Deye inverter switches to "Load first" mode + battery discharge = 0A
2. Car charges from grid with amps limited to stay under `grid_power_limit` (3000W, Italian meter protection at 3.3kW)
3. When sun comes up, inverter restores day mode

### 7. Evening Planner

Runs at configurable time (default 20:00). Compares Tesla's energy need (SOC gap × battery capacity) against tomorrow's forecast excess. Decides: charge tonight on cheap rate, or wait for solar.

Sends Telegram notification with plan details and inline keyboard for override.

### 8. Location Detection

Uses HA device tracker entity. The car must be in a configured "home" location to charge. Location states are comma-separated (e.g., `home, Piano di sotto`).

**Fail-safe:** If the location entity is `unavailable` or `unknown` (common when car is asleep), assumes "at home" to avoid blocking charging.

## File Structure

| File | Purpose |
|------|---------|
| `__init__.py` | Setup, event scheduling, forecast fetching, planner execution, panel registration |
| `coordinator.py` | 30s control loop, day/night mode handling, sensor reading |
| `charging_logic.py` | Pure decision functions (no HA deps): `decide()`, `decide_night_amps()`, `calculate_net_available()` |
| `config_flow.py` | 3-step UI config wizard + options flow |
| `const.py` | All constants, defaults, config keys |
| `sensor.py` | 10 sensor entities including Debug sensor with full JSON dump |
| `switch.py` | Enable/disable switch (persists across restarts), force charge switch |
| `number.py` | Tesla Charge Limit slider (syncs to car via BLE) |
| `ble_controller.py` | ESP32 BLE command wrapper with health tracking |
| `inverter_controller.py` | Deye inverter mode switching (night/day) |
| `planner.py` | Evening decision engine: charge tonight vs wait for solar |
| `weather_forecast.py` | Open-Meteo API client (daily + hourly cloud forecasts) |
| `solcast_client.py` | Solcast API client (multi-array support, P10/P50/P90) |
| `forecast_solar_client.py` | Forecast.Solar API client |
| `forecast_blend.py` | Weighted average blending of multiple forecast sources |
| `forecast_tracker.py` | Accuracy tracking, correction factors (rolling, seasonal, weather-aware) |
| `pvgis_client.py` | EU JRC PVGIS monthly irradiance baselines |
| `notification.py` | Telegram alerts with inline keyboards |
| `octopus_client.py` | Octopus Energy Italy GraphQL API |
| `frontend/panel.js` | Custom sidebar panel (web component) |

## Charging Logic Flow (Solar Mode)

```
1. Tesla at charge limit? → STOP
2. Not charging:
   a. Battery < 98% AND export < 1800W? → WAIT (filling battery)
   b. Battery >= 98% AND battery still absorbing? → START at 5A
   c. Export < 900W? → WAIT (not enough)
   d. Export >= 900W → START at calculated amps
3. Currently charging:
   a. Battery discharging > 100W? → REDUCE amps (solar dropped)
   b. Net available >= 4A? → RAMP UP by 2A
   c. Net available >= 2A? → RAMP UP by 1A
   d. Net available <= -2A? → RAMP DOWN by 1A
   e. At min amps for 3 consecutive checks? → STOP
   f. Otherwise → HOLD
```

## Configuration Defaults

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_export_power` | 900 W* | Grid export needed to start charging |
| `max_charging_amps` | 28 A* | Maximum charging current |
| `safety_buffer_amps` | 3 A | Reserved amps (never used for car) |
| `battery_soc_threshold` | 98 % | Home battery must reach this before car starts |
| `battery_discharge_threshold` | 100 W | Battery discharge triggers reduced car charging |
| `low_amp_stop_count` | 3 | Consecutive low readings before stopping |
| `grid_power_limit` | 3000 W | Max grid draw in night mode (Italian 3.3kW meter) |
| `performance_ratio` | 0.60 | PV system efficiency (60% of STC rating) |
| `planner_safety_margin` | 1.2 | 20% extra needed to skip night charge |
| `update_interval` | 30 s | Control loop frequency |

*User has customized these from defaults.

## Entities Created

**Sensors:** State, Charging Amps, Net Available, Reason, Solar Forecast, Plan, Forecast Accuracy, BLE Status, Cloud Strategy, Debug
**Switches:** Solar Charging (persists on/off across restarts), Force Charge
**Numbers:** Tesla Charge Limit (syncs to car via BLE)

## Custom Panel

Sidebar item "Tesla Solar" — a web component (`frontend/panel.js`) showing 9 cards:
Status, Power & Charging (with ETAs), Tesla, BLE/ESP32, Solar Forecast (with PVGIS baselines chart), Forecast Accuracy (with 7-day bar chart), Configuration, Daily Stats, Debug JSON (with Copy button).

Cache-busted via `?v={VERSION}` query string on the module URL.

## Known Quirks

- **PVGIS API** only accepts years 2005–2020, returns entries per-year that must be averaged
- **Solcast** returns `text/html` content type for JSON responses — use `content_type=None` in `resp.json()`
- **HA panel registration** uses `async_register_built_in_panel` with `config._panel_custom` dict (not keyword args)
- **HA static paths** use `async_register_static_paths` with `StaticPathConfig` objects
- **customElements.define** must be guarded with `.get()` check to prevent errors on integration reload
- **Startup forecast** — on reload, HA has already started so `homeassistant_started` event won't fire; detect `hass.is_running` and fetch immediately
- **Tesla location** can be a custom zone name (e.g., "Piano di sotto") — configurable via comma-separated home states
