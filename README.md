# Tesla Solar Charging

A Home Assistant custom integration that automatically manages Tesla charging based on solar excess production, with evening planning, multi-source weather forecasts, PVGIS seasonal correction, and optional Octopus Energy night charging.

## Features

- **Solar excess charging**: 30-second control loop reads inverter sensors, calculates available export, starts/stops/adjusts Tesla charging via BLE
- **Night charging**: Grid-limit-aware charging during cheap rate windows (3.3kW Italian meter protection)
- **Evening planner**: Daily weather forecast → Telegram notification with charge/skip decision
- **Forecast learning**: Tracks forecast vs actual production, auto-corrects future estimates
- **Inverter control**: Automatic Deye inverter mode switching (day/night)
- **Force charge**: Bypass home battery SOC threshold for this session, auto-resets on replug
- **BLE/ESP32 health monitoring**: Detects ESP32 offline or BLE command failures, auto-stops charging to prevent blind operation
- **Hourly cloud-aware forecasts**: Open-Meteo hourly forecast with cloud cover by layer (low/mid/high), cloud strategy sensor (clear/partly_cloudy/mostly_cloudy/overcast), best charging window selection
- **Multi-source forecast blending**: Weighted average of Open-Meteo, Solcast (P10/P50/P90), and Forecast.Solar; each source weight is configurable
- **PVGIS seasonal correction**: Monthly production baselines for Padua calibrate daily estimates to real seasonal curves
- **Weather-pattern correction**: Separate forecast accuracy tracking for clear vs cloudy days, per-pattern correction factors
- **Telegram notifications**: Alerts for BLE offline, charge stopped, Tesla charge limit reached, night mode entry/exit, and a daily charge report at configurable time (default 21:30)
- **Configurable planner safety margin**: Require extra solar headroom before skipping night charge (default 20%)

## Installation

### Via HACS (recommended)

1. Add a GitHub personal access token in HACS settings (needs `repo` scope)
2. HACS → ⋮ → Custom Repositories → paste this repo URL → Category: Integration
3. Install, restart Home Assistant
4. Settings → Integrations → Add → "Tesla Solar Charging"

### Manual

Copy `custom_components/tesla_solar_charging/` to your HA `custom_components/` directory and restart.

## Configuration

The integration uses a multi-step config flow:

1. **Sensors & BLE**: Deye inverter sensors + Tesla BLE control entities
2. **Inverter & Notifications**: Deye mode controls, Octopus Energy (optional), Telegram
3. **Energy Parameters**: PV size, battery capacity, grid limits, tuning
4. **Forecast Sources**: Open-Meteo (built-in), Solcast (optional), Forecast.Solar (optional)

### Key configuration options

| Option | Default | Description |
|--------|---------|-------------|
| `performance_ratio` | 0.60 | PV efficiency ratio used for daily production estimates |
| `battery_discharge_threshold` | 100 W | Minimum discharge power before battery is considered idle |
| `home_location_states` | `"home"` | Comma-separated Tesla location states treated as "at home" |
| `tesla_deadline_entity` | — | HA entity holding the departure deadline (input_datetime) |
| `tesla_target_soc_entity` | — | HA entity holding the desired target SOC (input_number) |
| `hourly_forecast_enabled` | true | Enable hourly Open-Meteo cloud-cover forecast |
| `planning_time` | `"20:00"` | Time of day the evening planner runs |
| `planner_safety_margin` | 1.2 | Multiplier: solar forecast must be ≥ this × needed energy to skip night charge |
| `solcast_api_key` | — | Solcast API key (optional; enables Solcast blending) |
| `solcast_resource_id` | — | Solcast rooftop resource ID |
| `forecast_solar_enabled` | false | Enable Forecast.Solar as an additional source |
| `forecast_solar_declination` | 30 | Panel tilt angle in degrees |
| `forecast_solar_azimuth` | 180 | Panel azimuth in degrees (180 = south) |

## Entities

| Entity | Type | Description |
|--------|------|-------------|
| `switch.solar_charging` | Switch | Enable/disable controller |
| `switch.force_charge` | Switch | Bypass battery SOC threshold (auto-resets on replug) |
| `sensor.*_state` | Sensor | Controller state (idle/charging_solar/charging_night/etc) |
| `sensor.*_charging_amps` | Sensor | Current charging amps |
| `sensor.*_net_available` | Sensor | Net available amps from solar |
| `sensor.*_reason` | Sensor | Human-readable reason for last action |
| `sensor.*_solar_forecast` | Sensor | Tomorrow's estimated solar production (kWh) |
| `sensor.*_plan` | Sensor | Current plan (night charge / solar only) |
| `sensor.*_forecast_accuracy` | Sensor | Forecast correction factor with history |
| `sensor.*_ble_status` | Sensor | ESP32/BLE health (ok/esp32_offline/ble_error) |
| `sensor.*_cloud_strategy` | Sensor | Cloud-based charging strategy (clear/partly_cloudy/mostly_cloudy/overcast) |

## Example Dashboard Card

See [`example_card.yaml`](example_card.yaml) for a ready-to-use Lovelace card configuration.

## Requirements

- ESPHome Tesla BLE (ESP32 with `tesla_ble_vehicle` component)
- Deye hybrid inverter with ESPHome Modbus sensors
- Optional: Octopus Energy Italy account
- Optional: Telegram bot (for notifications and daily report)
- Optional: Solcast account + API key (for P10/P50/P90 forecast blending)
- Optional: Forecast.Solar (free tier; for additional forecast blending)
