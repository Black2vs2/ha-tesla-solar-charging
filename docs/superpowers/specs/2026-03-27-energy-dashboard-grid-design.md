# Energy Dashboard Grid — Design Spec

**Date:** 2026-03-27
**Status:** Approved

## Overview

A configurable free-form grid dashboard for the Tesla Solar Charging integration. Displays energy sources, storage, consumers, zones, and forecasts as individual cards on an N×M CSS grid. Card types are coded; layout and entity bindings are YAML-configurable.

Works both as a **Lovelace card** (`custom:energy-dashboard-card`) and as the **sidebar panel** (panel.js wraps the card full-width).

## Goals

1. Show real-time energy flow status for all system components
2. Per-appliance smart start-time based on hourly solar forecast
3. kWh-based budget view — does today's solar cover all consumers?
4. Average kWh per run for each appliance (from run history)
5. Physical zone consumption (piano di sopra / piano di sotto)
6. Full entity debug view with all attributes as JSON
7. All labels in Italian

## Architecture

### Two targets, one component

```
energy-dashboard-card.js (web component)
  ├── Used as Lovelace card: type: custom:energy-dashboard-card
  └── Used in panel.js: imported and rendered full-width
```

### Data flow

```
HA entities (sensors, switches, numbers)
    ↓
energy-dashboard-card.js reads hass.states
    ↓
Card type renderers (solar, grid, battery, tesla, appliance, zone, forecast, debug)
    ↓
CSS Grid layout from YAML config
```

### Backend additions

- **Hourly forecast attribute**: Expose `hourly_forecast` array on the forecast sensor — `[{hour: "10:00", kwh: 2.3}, ...]` for today's remaining hours. Data already fetched from Open-Meteo but not currently in sensor attributes.
- All other data already exists in sensor attributes.

## YAML Configuration

```yaml
type: custom:energy-dashboard-card
grid:
  columns: 6
  rows: 6
  gap: 8
cards:
  - type: solar
    col: 1
    row: 1
    span_col: 2
    span_row: 1
    entity: sensor.solar_production
    forecast_entity: sensor.tesla_solar_charging_solar_forecast

  - type: grid
    col: 3
    row: 1
    span_col: 2
    span_row: 1
    entity: sensor.grid_power

  - type: battery
    col: 5
    row: 1
    span_col: 2
    span_row: 2
    soc_entity: sensor.battery_soc
    power_entity: sensor.battery_power
    capacity_kwh: 14
    threshold: 98

  - type: tesla
    col: 1
    row: 2
    span_col: 2
    span_row: 2
    state_entity: sensor.tesla_solar_charging_state
    soc_entity: sensor.tesla_battery
    amps_entity: sensor.tesla_solar_charging_charging_amps
    battery_kwh: 75

  - type: appliance
    col: 3
    row: 2
    span_col: 1
    span_row: 1
    name: Lavastoviglie
    icon_letter: L
    advisor_entity: sensor.appliance_advisor_lavastoviglie
    power_entity: sensor.presa_su_lavastoviglie_power
    energy_entity: sensor.presa_su_lavastoviglie_energy

  - type: appliance
    col: 4
    row: 2
    span_col: 1
    span_row: 1
    name: Lavatrice
    icon_letter: L
    advisor_entity: sensor.appliance_advisor_lavatrice
    power_entity: sensor.presa_su_lavatrice_power
    energy_entity: sensor.presa_su_lavatrice_energy

  - type: zone
    col: 5
    row: 3
    span_col: 2
    span_row: 1
    name: Piano di sopra
    icon_letter: PS
    power_entity: sensor.openbk_ct_2_power

  - type: zone
    col: 5
    row: 4
    span_col: 2
    span_row: 1
    name: Piano di sotto
    icon_letter: PG
    power_entity: sensor.openbk_ct_2_current

  - type: forecast
    col: 1
    row: 4
    span_col: 4
    span_row: 1
    forecast_entity: sensor.tesla_solar_charging_solar_forecast
    advisor_entity: sensor.appliance_advisor_summary
    house_consumption_kwh: 10

  - type: debug
    col: 1
    row: 5
    span_col: 6
    span_row: 2
```

## Card Types

### 1. `solar`

| Field | Source |
|-------|--------|
| Potenza attuale (kW) | `entity` state |
| Stato | "in produzione" / "spento" with running dot |
| Oggi (kWh) | entity attribute or HA daily accumulation |
| Previsione (kWh) | `forecast_entity` attribute `blended_kwh` |

- Yellow (#fbbf24) color theme
- Icon badge: colored square with letter "S"

### 2. `grid`

| Field | Source |
|-------|--------|
| Potenza attuale (kW) | `entity` state |
| Direzione | Import (▲ rosso) / Export (▼ verde) |
| Importata oggi (kWh) | entity attribute |
| Esportata oggi (kWh) | entity attribute |

- Green when exporting, red when importing
- Icon badge: "R"

### 3. `battery`

| Field | Source |
|-------|--------|
| SOC % | `soc_entity` state |
| Potenza (kW) | `power_entity` state |
| Stato | "in carica ▲" (verde) / "in scarica ▼" (rosso) |
| Barra progresso | SOC% with threshold marker at configured % |
| Capacita | from `capacity_kwh` config |
| Caricata/scaricata oggi | entity attributes |

- Green when charging, red when discharging
- Icon badge: "B"

### 4. `tesla`

| Field | Source |
|-------|--------|
| SOC % | `soc_entity` state |
| Ampere | `amps_entity` state or `state_entity` attributes |
| Stato | "in carica solare" / "in carica notturna" / "in attesa" / "fermo" |
| Barra progresso | SOC% with charge limit marker |
| Potenza (~kW) | calculated from amps × voltage |
| ETA | from `state_entity` attributes |
| Solare oggi (kWh) | `state_entity` attribute `daily_solar_kwh` |
| Servono (kWh) | calculated: `battery_kwh × (limit - soc) / 100` |

- Blue (#60a5fa) color theme
- Icon badge: "T"

### 5. `appliance`

| Field | Source |
|-------|--------|
| Nome | from `name` config |
| Stato | Gratis (verde) / Poco (giallo) / Costa (rosso) |
| Watt attuali | `power_entity` state |
| In funzione | running dot if watts > threshold |
| Media kWh | `advisor_entity` attribute `avg_consumption_kwh` |
| Orario avvio | smart start-time calculation (see below) |

- Border color matches status
- Icon badge: `icon_letter` from config
- Dimmed (opacity 0.45) when off and no recommendation

### 6. `zone`

| Field | Source |
|-------|--------|
| Nome | from `name` config |
| Potenza attuale (kW) | `power_entity` state |
| Oggi (kWh) | HA daily accumulation or entity attribute |

- Neutral grey theme
- Icon badge: `icon_letter` from config

### 7. `forecast`

| Field | Source |
|-------|--------|
| Domani (kWh) | `forecast_entity` attribute `blended_kwh` |
| Eccedenza (kWh) | forecast - battery needs - house consumption |
| Fabbisogno (kWh) | sum of all appliance avg_kwh + tesla needs |
| Piano | "Solo solare" / "Carica notturna" |
| Budget bar | proportional segments for each consumer |

- Budget bar segments:
  - Casa (grigio): `house_consumption_kwh`
  - Batteria (blu scuro): capacity × (100% - SOC)
  - Tesla (blu chiaro): kWh needed to reach limit
  - Elettrodomestici gratis (verde): sum of avg_kwh for green appliances
  - Elettrodomestici parziale (arancione): yellow appliances
  - Eccedenza (verde scuro): surplus
  - Deficit (rosso): if demand > forecast, shown as overflow

### 8. `debug`

| Field | Source |
|-------|--------|
| All configured entities | iterates over all cards in config |
| Per entity: state + full attributes | `hass.states[entity_id]` |
| Entity health | verde = available, rosso = unavailable/unknown |
| Grouped by card type | "Entita Solare", "Entita Tesla", etc. |

- Copy JSON button for full dump
- Collapsible sections per group

## Grid System

### Rendering

- `display: grid` with `grid-template-columns: repeat(columns, 1fr)`
- `grid-template-rows: repeat(rows, 100px)` (fixed row height)
- Each card positioned with `grid-column: col / span span_col` and `grid-row: row / span span_row`
- Background: dot pattern at cell intersections + faint grid lines
- Column/row numbers along edges

### Edit mode (future)

Not in first version. Positions set manually in YAML. Future enhancement: drag-to-reposition UI that generates YAML.

## Smart Start Time

### Algorithm

For each appliance card:

1. Read `avg_consumption_kwh` from advisor sensor attributes (average kWh per run from run history)
2. Read `hourly_forecast` from forecast sensor attributes — array of `{hour, kwh}` for today
3. For each remaining hour in the day:
   - `surplus = forecast_hour_kwh - house_baseline_per_hour`
   - Subtract currently running loads: Tesla power, active appliances (read from their power entities)
   - If cumulative surplus over the appliance's duration covers `avg_consumption_kwh` → that hour is the recommended start
4. Display result:
   - Window found: "Avvia alle HH:MM" (colored green)
   - Window found but tight: "Avvia entro HH:MM" (colored yellow)
   - No window: "Solare insufficiente" (colored red)

### Currently running deduction

Only real-time power is subtracted — no future scheduling. If Tesla is charging at 1.8 kW right now, that's subtracted from each hour's surplus. If it stops later, the next update cycle (30s) recalculates.

## kWh Per Run Tracking

Already implemented in `run_history_store.py`:
- Detects run start/end via power sensor threshold
- Records kWh per run
- Keeps last 30 runs
- Exposes `avg_consumption_kwh` in advisor sensor attributes

The appliance card reads this directly. No new backend work needed.

## Real-Time Flow Indicators

### Visual language

| State | Value color | Border | Dot |
|-------|------------|--------|-----|
| Solar producing | #fbbf24 (giallo) | default | pulsing |
| Battery charging | #34d399 (verde) | default | pulsing |
| Battery discharging | #f85149 (rosso) | red | none |
| Tesla charging | #60a5fa (blu) | blue | pulsing |
| Tesla idle | #484f58 (grigio) | default | none |
| Grid exporting | #34d399 (verde) | default | none |
| Grid importing | #f85149 (rosso) | red | none |
| Appliance running | status color | status color | pulsing |
| Appliance off | dimmed | default | none |
| Sun down / no solar | dimmed | default | none |

### Direction arrows

- `▲` = energy flowing in (charging, importing)
- `▼` = energy flowing out (discharging, exporting)

### Icon badges

Compact 22px rounded squares with colored background. Letter(s) from config or card type default:
- S (Solare), R (Rete), B (Batteria), T (Tesla)
- Appliances/zones: from `icon_letter` in YAML

## File Changes

### New files

| File | Purpose |
|------|---------|
| `frontend/energy-dashboard-card.js` | Main grid dashboard web component |

### Modified files

| File | Change |
|------|--------|
| `frontend/panel.js` | Import and render `energy-dashboard-card` full-width |
| `sensor.py` | Add `hourly_forecast` attribute to solar forecast sensor |
| `__init__.py` | Register static path for new JS file |

### No changes needed

- `coordinator.py` — all data already in sensors
- `appliance_advisor/` — avg_consumption_kwh already exposed
- `run_history_store.py` — already tracking per-run kWh
- `config_flow.py` — dashboard config is YAML, not config flow

## Italian Labels Reference

| English | Italian |
|---------|---------|
| Source | Fonte |
| Storage | Accumulo |
| Consumer | Consumatore |
| Zone | Zona |
| Producing | In produzione |
| Charging | In carica |
| Discharging | In scarica |
| Exporting | Esportazione |
| Importing | Importazione |
| Free | Gratis |
| Partial | Poco |
| Expensive | Costa |
| Start by | Avvia entro |
| Start now | Avvia adesso |
| Not enough solar | Solare insufficiente |
| Off | Spenta |
| Forecast | Previsione |
| Excess | Eccedenza |
| Demand | Fabbisogno |
| Plan | Piano |
| Solar only | Solo solare |
| Night charge | Carica notturna |
| Capacity | Capacita |
| Threshold | Soglia |
| Today | Oggi |
| Tomorrow | Domani |
| Average | Media |
| Budget | Budget energetico |
| Edit mode | Modalita modifica |
| Finish editing | Fine modifica |
