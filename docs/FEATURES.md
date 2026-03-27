# Feature Wishlist & Analysis

Tracked features for the Tesla Solar Charging integration.

## Energy Dashboard Grid

**Status:** Design approved, pending implementation
**Spec:** [2026-03-27-energy-dashboard-grid-design.md](superpowers/specs/2026-03-27-energy-dashboard-grid-design.md)

### Core Features

- [ ] **Free-form grid layout** — configurable N×M CSS grid with visible cell background (dots + lines), column/row numbers
- [ ] **Card types in code, layout in YAML** — 8 card types (solar, grid, battery, tesla, appliance, zone, forecast, debug), positioned via col/row/span_col/span_row in YAML
- [ ] **Single component, two targets** — `energy-dashboard-card.js` works as Lovelace card AND sidebar panel
- [ ] **All labels in Italian**

### Real-Time Energy Flow

- [ ] **Solar card** — live kW, today kWh, forecast kWh, producing indicator
- [ ] **Grid card** — live kW, import/export direction with color (verde/rosso), daily import/export kWh
- [ ] **Battery card** — SOC%, charge/discharge state with color, progress bar with threshold marker, daily charge/discharge kWh
- [ ] **Tesla card** — SOC%, charging amps, ETA, power kW, kWh needed to limit, daily solar kWh
- [ ] **Zone cards** — piano di sopra / piano di sotto live kW + daily kWh (from openbk_ct_2_power / openbk_ct_2_current)
- [ ] **Running indicators** — pulsing dot on active entities, direction arrows (up/down), color-coded borders

### Smart Appliance Scheduling

- [ ] **Average kWh per run** — from run history (last 30 runs), shown on each appliance card
- [ ] **Smart start-time** — per appliance, finds best hour based on hourly solar forecast minus currently running loads
- [ ] **kWh budget bar** — proportional bar showing daily solar allocation: casa, batteria, tesla, elettrodomestici, eccedenza/deficit

### Debug & Entity Info

- [ ] **Debug card type** — shows all configured entities with full state + attributes as JSON
- [ ] **Entity health indicators** — verde/rosso per entity (available vs unavailable)
- [ ] **Grouped by card type** — collapsible sections
- [ ] **Copy JSON button**

### Backend Changes

- [ ] **Hourly forecast attribute** — expose `hourly_forecast` array on forecast sensor (data already fetched, just not in attributes)

### Future (Not First Version)

- [ ] **Edit mode** — drag-to-reposition cards, resize handles, generates YAML
- [ ] **Appliance overlap detection** — scheduling optimizer that accounts for multiple appliances running simultaneously
