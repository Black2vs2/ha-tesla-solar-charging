# Energy Dashboard Grid — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a configurable free-form grid dashboard card showing energy sources, storage, consumers, zones, and forecasts — with smart start-time recommendations and kWh budget view.

**Architecture:** Single web component (`energy-dashboard-card.js`) used as both Lovelace card and sidebar panel. Card types coded in JS; layout/entities from YAML config. One backend change: expose hourly forecast data in sensor attributes.

**Tech Stack:** Vanilla JS web component (no framework), CSS Grid, Home Assistant frontend API (`hass.states`), Python for sensor attribute addition.

---

### Task 1: Backend — Expose hourly forecast in sensor attributes

**Files:**
- Modify: `custom_components/tesla_solar_charging/coordinator.py:80-110`
- Modify: `custom_components/tesla_solar_charging/sensor.py:231-247`
- Modify: `custom_components/tesla_solar_charging/__init__.py:430-442`
- Test: `tests/test_hourly_forecast_attr.py`

The coordinator already receives hourly data in `__init__.py:431-442` but only extracts `cloud_strategy` and `best_charging_window`. We need to store the full hourly array and expose it on the forecast sensor.

- [ ] **Step 1: Write failing test for hourly forecast attribute**

Create `tests/test_hourly_forecast_attr.py`:

```python
"""Test that hourly forecast data is exposed on the forecast sensor."""
from custom_components.tesla_solar_charging.weather_forecast import (
    HourlyEntry,
    DailyHourlyForecast,
)


def test_hourly_forecast_to_attr():
    """DailyHourlyForecast.to_hourly_attr() returns list of dicts for sensor."""
    hours = [
        HourlyEntry(hour=h, radiation_w_m2=h * 100, cloud_cover=20.0,
                     cloud_cover_low=10.0, cloud_cover_mid=5.0, cloud_cover_high=5.0)
        for h in range(6, 21)
    ]
    dhf = DailyHourlyForecast(date="2026-03-28", hours=hours)
    result = dhf.to_hourly_attr()

    assert isinstance(result, list)
    assert len(result) == 15
    assert result[0] == {"hour": "06:00", "radiation_w_m2": 600, "cloud_cover": 20.0}
    assert result[-1] == {"hour": "20:00", "radiation_w_m2": 2000, "cloud_cover": 20.0}


def test_hourly_forecast_to_attr_empty():
    """Empty hours returns empty list."""
    dhf = DailyHourlyForecast(date="2026-03-28", hours=[])
    assert dhf.to_hourly_attr() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_hourly_forecast_attr.py -v`
Expected: FAIL — `AttributeError: 'DailyHourlyForecast' object has no attribute 'to_hourly_attr'`

- [ ] **Step 3: Add `to_hourly_attr()` method to DailyHourlyForecast**

In `custom_components/tesla_solar_charging/weather_forecast.py`, add after line 82 (after `best_window_desc` property):

```python
    def to_hourly_attr(self) -> list[dict]:
        """Convert hourly data to a list of dicts for sensor attributes."""
        return [
            {
                "hour": f"{h.hour:02d}:00",
                "radiation_w_m2": h.radiation_w_m2,
                "cloud_cover": h.cloud_cover,
            }
            for h in self.hours
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_hourly_forecast_attr.py -v`
Expected: PASS

- [ ] **Step 5: Store hourly data on coordinator**

In `custom_components/tesla_solar_charging/coordinator.py`, add to `__init__` after line 97 (`self._best_charging_window = "Unknown"`):

```python
        self._hourly_forecast_today: list[dict] = []
```

In `custom_components/tesla_solar_charging/__init__.py`, replace lines 437-442 (inside the `if today_str in hourly:` block):

```python
            if today_str in hourly:
                coordinator.cloud_strategy = hourly[today_str].cloud_strategy
                coordinator.best_charging_window = hourly[today_str].best_window_desc
                coordinator._hourly_forecast_today = hourly[today_str].to_hourly_attr()
            elif tomorrow_str in hourly:
                coordinator.cloud_strategy = hourly[tomorrow_str].cloud_strategy
                coordinator.best_charging_window = hourly[tomorrow_str].best_window_desc
                coordinator._hourly_forecast_today = []
```

- [ ] **Step 6: Expose hourly data on forecast sensor**

In `custom_components/tesla_solar_charging/sensor.py`, in `ForecastSensor.extra_state_attributes` (line 234), add to the `attrs` dict:

```python
        attrs = {
            "blended_kwh": c.forecast_kwh,
            "pessimistic_kwh": c._forecast_pessimistic_kwh,
            "sources": c._forecast_sources,
            "low_solar_warning": c.low_solar_warning,
            "multi_day_outlook": c.multi_day_outlook,
            "hourly_forecast": c._hourly_forecast_today,
        }
```

- [ ] **Step 7: Commit**

```bash
git add tests/test_hourly_forecast_attr.py custom_components/tesla_solar_charging/weather_forecast.py custom_components/tesla_solar_charging/coordinator.py custom_components/tesla_solar_charging/__init__.py custom_components/tesla_solar_charging/sensor.py
git commit -m "feat: expose hourly forecast data in sensor attributes for dashboard card"
```

---

### Task 2: Frontend — Card base infrastructure and grid system

**Files:**
- Create: `custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js`

This task creates the web component shell, YAML config parsing, CSS grid rendering with visible background, and the card registration. No card type renderers yet — just empty positioned boxes.

- [ ] **Step 1: Create the web component with config parsing and grid layout**

Create `custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js`:

```javascript
/**
 * Energy Dashboard Card — configurable grid dashboard
 *
 * Usage (Lovelace YAML):
 *   type: custom:energy-dashboard-card
 *   grid:
 *     columns: 6
 *     rows: 6
 *     gap: 8
 *   cards:
 *     - type: solar
 *       col: 1
 *       row: 1
 *       span_col: 2
 *       span_row: 1
 *       entity: sensor.solar_production
 */

const CARD_VERSION = "1.0.0";

class EnergyDashboardCard extends HTMLElement {
  constructor() {
    super();
    this._config = null;
    this._hass = null;
    this._root = null;
  }

  setConfig(config) {
    if (!config.cards || !Array.isArray(config.cards)) {
      throw new Error("energy-dashboard-card: 'cards' array is required");
    }
    this._config = {
      grid: {
        columns: config.grid?.columns ?? 6,
        rows: config.grid?.rows ?? 6,
        gap: config.grid?.gap ?? 8,
      },
      cards: config.cards,
    };
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._root) {
      this._render();
    } else {
      this._update();
    }
  }

  getCardSize() {
    return (this._config?.grid?.rows ?? 6) * 2;
  }

  _render() {
    if (!this._config || !this._hass) return;

    const g = this._config.grid;

    this.innerHTML = `
      <style>
        .edg-wrapper {
          position: relative;
          margin-left: 24px;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          color: var(--primary-text-color, #e6edf3);
        }
        .edg-col-labels {
          display: grid;
          grid-template-columns: repeat(${g.columns}, 1fr);
          gap: ${g.gap}px;
          padding: 0 ${g.gap}px;
          margin-bottom: 4px;
        }
        .edg-col-labels span {
          text-align: center;
          font-size: 10px;
          color: var(--secondary-text-color, #484f58);
          font-family: monospace;
        }
        .edg-row-labels {
          position: absolute;
          left: -18px;
          top: 28px;
          display: flex;
          flex-direction: column;
          gap: ${g.gap}px;
        }
        .edg-row-labels span {
          height: 100px;
          display: flex;
          align-items: center;
          font-size: 10px;
          color: var(--secondary-text-color, #484f58);
          font-family: monospace;
        }
        .edg-grid {
          position: relative;
          display: grid;
          grid-template-columns: repeat(${g.columns}, 1fr);
          grid-template-rows: repeat(${g.rows}, 100px);
          gap: ${g.gap}px;
          padding: ${g.gap}px;
          border: 1px solid var(--divider-color, #21262d);
          border-radius: 12px;
          background-image:
            radial-gradient(circle, var(--divider-color, rgba(48,54,61,0.5)) 1.5px, transparent 1.5px);
          background-size: calc(100% / ${g.columns}) calc(100px + ${g.gap}px);
          background-position: calc(100% / ${g.columns} / 2) calc((100px + ${g.gap}px) / 2);
        }

        /* --- Card base --- */
        .edg-card {
          position: relative;
          background: var(--card-background-color, #161b22);
          border: 1px solid var(--divider-color, #30363d);
          border-radius: 10px;
          padding: 12px 14px;
          overflow: hidden;
          transition: border-color 0.2s;
          z-index: 1;
        }
        .edg-card:hover { border-color: var(--secondary-text-color, #484f58); }

        .edg-span-badge {
          position: absolute;
          top: 4px;
          right: 6px;
          font-size: 8px;
          color: var(--secondary-text-color, #484f58);
          font-family: monospace;
          background: rgba(33,38,45,0.8);
          padding: 2px 5px;
          border-radius: 4px;
        }

        /* --- Icon badge --- */
        .edg-icon {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 22px;
          height: 22px;
          border-radius: 6px;
          font-size: 11px;
          font-weight: 700;
          flex-shrink: 0;
        }

        .edg-header {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .edg-title { font-size: 14px; font-weight: 600; line-height: 1.2; }
        .edg-zone-label {
          font-size: 9px;
          color: var(--secondary-text-color, #484f58);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .edg-value { font-size: 22px; font-weight: 700; margin-top: 4px; }
        .edg-sub { font-size: 11px; color: var(--secondary-text-color, #8b949e); margin-top: 2px; }
        .edg-detail { font-size: 11px; color: var(--secondary-text-color, #8b949e); margin-top: 3px; }

        .edg-progress { background: var(--divider-color, #21262d); border-radius: 4px; height: 6px; margin-top: 6px; }
        .edg-progress-fill { border-radius: 4px; height: 6px; transition: width 0.5s; }

        .edg-row { display: flex; justify-content: space-between; align-items: baseline; margin-top: 4px; }

        /* --- Running indicator --- */
        .edg-dot {
          display: inline-block;
          width: 6px; height: 6px;
          border-radius: 50%;
          background: currentColor;
          animation: edg-pulse 1.5s infinite;
          margin-right: 3px;
          vertical-align: middle;
        }
        @keyframes edg-pulse {
          0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(52,211,153,0.4); }
          50% { opacity: 0.7; box-shadow: 0 0 0 4px rgba(52,211,153,0); }
        }

        .edg-dimmed { opacity: 0.45; }

        /* --- Colors --- */
        .edg-c-solar { color: #fbbf24; }
        .edg-c-green { color: #34d399; }
        .edg-c-red { color: #f85149; }
        .edg-c-blue { color: #60a5fa; }
        .edg-c-neutral { color: var(--primary-text-color, #e6edf3); }
        .edg-c-muted { color: var(--secondary-text-color, #484f58); }

        .edg-bg-solar { background: rgba(251,191,36,0.2); color: #fbbf24; }
        .edg-bg-grid { background: rgba(139,148,158,0.2); color: #8b949e; }
        .edg-bg-battery { background: rgba(52,211,153,0.2); color: #34d399; }
        .edg-bg-tesla { background: rgba(96,165,250,0.2); color: #60a5fa; }
        .edg-bg-green { background: rgba(52,211,153,0.2); color: #34d399; }
        .edg-bg-yellow { background: rgba(240,136,62,0.2); color: #f0883e; }
        .edg-bg-red { background: rgba(248,81,73,0.2); color: #f85149; }
        .edg-bg-zone { background: rgba(139,148,158,0.15); color: #8b949e; }
        .edg-bg-plan { background: rgba(163,113,247,0.2); color: #a371f7; }

        .edg-border-green { border-color: #238636 !important; }
        .edg-border-yellow { border-color: #f0883e !important; }
        .edg-border-red { border-color: #da3633 !important; }
        .edg-border-blue { border-color: #1f6feb !important; }

        /* --- Budget bar --- */
        .edg-budget { margin-top: 6px; }
        .edg-budget-label {
          font-size: 11px;
          color: var(--secondary-text-color, #8b949e);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 6px;
          font-weight: 600;
        }
        .edg-budget-bar {
          display: flex;
          height: 22px;
          border-radius: 6px;
          overflow: hidden;
          background: var(--divider-color, #21262d);
        }
        .edg-budget-seg {
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 9px;
          font-weight: 600;
          white-space: nowrap;
          overflow: hidden;
        }
        .edg-budget-legend {
          display: flex;
          gap: 10px;
          margin-top: 4px;
          flex-wrap: wrap;
        }
        .edg-budget-legend span {
          font-size: 10px;
          color: var(--secondary-text-color, #8b949e);
          display: flex;
          align-items: center;
          gap: 4px;
        }
        .edg-budget-dot {
          width: 8px; height: 8px;
          border-radius: 2px;
          display: inline-block;
        }

        /* --- Debug card --- */
        .edg-debug-group { margin-bottom: 12px; }
        .edg-debug-group summary {
          cursor: pointer;
          font-size: 12px;
          font-weight: 600;
          color: var(--primary-text-color, #e6edf3);
          padding: 4px 0;
        }
        .edg-debug-pre {
          font-size: 10px;
          font-family: monospace;
          background: var(--divider-color, #21262d);
          padding: 8px;
          border-radius: 6px;
          overflow-x: auto;
          white-space: pre-wrap;
          word-break: break-word;
          max-height: 300px;
          overflow-y: auto;
        }
        .edg-debug-health {
          display: inline-block;
          width: 8px; height: 8px;
          border-radius: 50%;
          margin-right: 4px;
        }
        .edg-debug-ok { background: #34d399; }
        .edg-debug-err { background: #f85149; }
        .edg-copy-btn {
          background: var(--divider-color, #21262d);
          color: var(--primary-text-color, #e6edf3);
          border: 1px solid var(--divider-color, #30363d);
          border-radius: 6px;
          padding: 4px 10px;
          font-size: 11px;
          cursor: pointer;
          margin-top: 8px;
        }
      </style>
      <div class="edg-wrapper">
        <div class="edg-col-labels">
          ${Array.from({length: g.columns}, (_, i) => `<span>${i + 1}</span>`).join("")}
        </div>
        <div class="edg-row-labels">
          ${Array.from({length: g.rows}, (_, i) => `<span>${i + 1}</span>`).join("")}
        </div>
        <div class="edg-grid" id="edg-grid">
        </div>
      </div>
    `;

    this._root = this.querySelector("#edg-grid");
    this._renderCards();
    this._update();
  }

  _renderCards() {
    const grid = this._root;
    grid.innerHTML = "";

    for (const cardCfg of this._config.cards) {
      const el = document.createElement("div");
      el.className = "edg-card";
      el.dataset.type = cardCfg.type;
      el.style.gridColumn = `${cardCfg.col} / span ${cardCfg.span_col ?? 1}`;
      el.style.gridRow = `${cardCfg.row} / span ${cardCfg.span_row ?? 1}`;

      const spanCol = cardCfg.span_col ?? 1;
      const spanRow = cardCfg.span_row ?? 1;
      el.innerHTML = `<span class="edg-span-badge">${spanCol}×${spanRow}</span>`;

      grid.appendChild(el);
    }
  }

  // ── Helpers ──

  _stateVal(entityId) {
    if (!entityId) return null;
    const s = this._hass.states[entityId];
    if (!s || s.state === "unavailable" || s.state === "unknown") return null;
    const n = parseFloat(s.state);
    return isNaN(n) ? null : n;
  }

  _stateStr(entityId) {
    if (!entityId) return null;
    const s = this._hass.states[entityId];
    if (!s) return null;
    return s.state;
  }

  _stateAttrs(entityId) {
    if (!entityId) return {};
    const s = this._hass.states[entityId];
    return s?.attributes ?? {};
  }

  _update() {
    if (!this._root || !this._hass || !this._config) return;

    const cardEls = this._root.querySelectorAll(".edg-card");
    const cardCfgs = this._config.cards;

    for (let i = 0; i < cardEls.length; i++) {
      const el = cardEls[i];
      const cfg = cardCfgs[i];
      if (!cfg) continue;

      const spanBadge = el.querySelector(".edg-span-badge")?.outerHTML ?? "";

      switch (cfg.type) {
        case "solar":    this._renderSolar(el, cfg, spanBadge); break;
        case "grid":     this._renderGrid(el, cfg, spanBadge); break;
        case "battery":  this._renderBattery(el, cfg, spanBadge); break;
        case "tesla":    this._renderTesla(el, cfg, spanBadge); break;
        case "appliance": this._renderAppliance(el, cfg, spanBadge); break;
        case "zone":     this._renderZone(el, cfg, spanBadge); break;
        case "forecast": this._renderForecast(el, cfg, spanBadge); break;
        case "debug":    this._renderDebug(el, cfg, spanBadge); break;
        default:
          el.innerHTML = `${spanBadge}<div class="edg-sub">Tipo sconosciuto: ${cfg.type}</div>`;
      }
    }
  }

  // ── Card Type Renderers (stubs — implemented in Tasks 3-9) ──

  _renderSolar(el, cfg, badge) {
    el.innerHTML = `${badge}<div class="edg-sub">solar — non implementato</div>`;
  }
  _renderGrid(el, cfg, badge) {
    el.innerHTML = `${badge}<div class="edg-sub">grid — non implementato</div>`;
  }
  _renderBattery(el, cfg, badge) {
    el.innerHTML = `${badge}<div class="edg-sub">battery — non implementato</div>`;
  }
  _renderTesla(el, cfg, badge) {
    el.innerHTML = `${badge}<div class="edg-sub">tesla — non implementato</div>`;
  }
  _renderAppliance(el, cfg, badge) {
    el.innerHTML = `${badge}<div class="edg-sub">appliance — non implementato</div>`;
  }
  _renderZone(el, cfg, badge) {
    el.innerHTML = `${badge}<div class="edg-sub">zone — non implementato</div>`;
  }
  _renderForecast(el, cfg, badge) {
    el.innerHTML = `${badge}<div class="edg-sub">forecast — non implementato</div>`;
  }
  _renderDebug(el, cfg, badge) {
    el.innerHTML = `${badge}<div class="edg-sub">debug — non implementato</div>`;
  }
}

// Register as custom card
if (!customElements.get("energy-dashboard-card")) {
  customElements.define("energy-dashboard-card", EnergyDashboardCard);
}
window.customCards = window.customCards || [];
if (!window.customCards.some(c => c.type === "energy-dashboard-card")) {
  window.customCards.push({
    type: "energy-dashboard-card",
    name: "Energy Dashboard Grid",
    description: "Griglia energetica configurabile con carte per solare, rete, batteria, Tesla, elettrodomestici e zone.",
  });
}
```

- [ ] **Step 2: Register static path for the new JS file**

In `custom_components/tesla_solar_charging/__init__.py`, inside the static paths registration (line 222), add the new file:

```python
    await hass.http.async_register_static_paths([
        StaticPathConfig(f"/{DOMAIN}/panel", str(frontend_path), cache_headers=False),
        StaticPathConfig(
            f"/{DOMAIN}/appliance-advisor-card.js",
            str(Path(__file__).parent / "frontend" / "appliance-advisor-card.js"),
            cache_headers=True,
        ),
        StaticPathConfig(
            f"/{DOMAIN}/energy-dashboard-card.js",
            str(Path(__file__).parent / "frontend" / "energy-dashboard-card.js"),
            cache_headers=False,
        ),
    ])
```

- [ ] **Step 3: Verify in browser**

Add to a HA Lovelace dashboard manually:

```yaml
type: custom:energy-dashboard-card
grid:
  columns: 6
  rows: 4
cards:
  - type: solar
    col: 1
    row: 1
    span_col: 2
    span_row: 1
  - type: grid
    col: 3
    row: 1
    span_col: 2
    span_row: 1
```

Expected: grid background with dot pattern, column/row numbers, two cards with stub text "solar — non implementato" and "grid — non implementato" at correct grid positions, span badges showing "2×1".

- [ ] **Step 4: Commit**

```bash
git add custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js custom_components/tesla_solar_charging/__init__.py
git commit -m "feat: energy dashboard card shell with grid system and stub renderers"
```

---

### Task 3: Card type — Solar (`_renderSolar`)

**Files:**
- Modify: `custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js`

Replace the `_renderSolar` stub with the full renderer.

- [ ] **Step 1: Implement `_renderSolar`**

Replace the `_renderSolar` method:

```javascript
  _renderSolar(el, cfg, badge) {
    const power = this._stateVal(cfg.entity);
    const attrs = this._stateAttrs(cfg.forecast_entity);
    const forecastKwh = attrs.blended_kwh ?? "—";
    const producing = power !== null && power > 10;

    // Try to get today's accumulated kWh from state sensor attributes
    const stateAttrs = this._stateAttrs(cfg.state_entity);
    const todayKwh = stateAttrs.daily_solar_kwh ?? "—";

    const powerKw = power !== null ? (power / 1000).toFixed(1) : "0";
    const statusText = producing ? "in produzione" : "spento";
    const dotHtml = producing ? `<span class="edg-dot" style="color:#fbbf24"></span>` : "";
    const valueClass = producing ? "edg-c-solar" : "edg-c-muted";

    el.innerHTML = `${badge}
      <div class="edg-header">
        <div class="edg-icon edg-bg-solar">S</div>
        <div>
          <div class="edg-title">Solare</div>
          <div class="edg-zone-label">fonte</div>
        </div>
      </div>
      <div class="edg-row">
        <div class="edg-value ${valueClass}">${powerKw} kW</div>
        <div class="edg-sub">${dotHtml}${statusText}</div>
      </div>
      <div class="edg-detail">Oggi: ${todayKwh} kWh &bull; Previsione: ${forecastKwh} kWh</div>
    `;
  }
```

- [ ] **Step 2: Test in browser**

Add a solar card to the Lovelace test config with real entity IDs. Verify:
- Yellow "S" icon badge
- Live power in kW
- Pulsing dot when producing
- Today's kWh and forecast shown

- [ ] **Step 3: Commit**

```bash
git add custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js
git commit -m "feat: solar card type renderer with live power and forecast"
```

---

### Task 4: Card type — Grid (`_renderGrid`)

**Files:**
- Modify: `custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js`

- [ ] **Step 1: Implement `_renderGrid`**

Replace the `_renderGrid` method:

```javascript
  _renderGrid(el, cfg, badge) {
    const power = this._stateVal(cfg.entity);
    const powerW = power ?? 0;
    const importing = powerW > 50;
    const exporting = powerW < -50;

    const absKw = (Math.abs(powerW) / 1000).toFixed(1);
    let arrow = "";
    let statusText = "inattiva";
    let valueClass = "edg-c-muted";
    let borderClass = "";

    if (exporting) {
      arrow = "&#9660; "; // ▼
      statusText = "esportazione";
      valueClass = "edg-c-green";
      borderClass = "edg-border-green";
    } else if (importing) {
      arrow = "&#9650; "; // ▲
      statusText = "importazione";
      valueClass = "edg-c-red";
      borderClass = "edg-border-red";
    }

    if (borderClass) el.classList.add(borderClass); else {
      el.classList.remove("edg-border-green", "edg-border-red");
    }

    el.innerHTML = `${badge}
      <div class="edg-header">
        <div class="edg-icon edg-bg-grid">R</div>
        <div>
          <div class="edg-title">Rete</div>
          <div class="edg-zone-label">fonte</div>
        </div>
      </div>
      <div class="edg-row">
        <div class="edg-value ${valueClass}">${arrow}${absKw} kW</div>
        <div class="edg-sub">${statusText}</div>
      </div>
    `;
  }
```

- [ ] **Step 2: Test in browser**

Verify: green when exporting, red when importing, neutral when idle. Arrow direction matches.

- [ ] **Step 3: Commit**

```bash
git add custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js
git commit -m "feat: grid card type renderer with import/export indicators"
```

---

### Task 5: Card type — Battery (`_renderBattery`)

**Files:**
- Modify: `custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js`

- [ ] **Step 1: Implement `_renderBattery`**

Replace the `_renderBattery` method:

```javascript
  _renderBattery(el, cfg, badge) {
    const soc = this._stateVal(cfg.soc_entity);
    const power = this._stateVal(cfg.power_entity);
    const socPct = soc ?? 0;
    const powerW = power ?? 0;
    const capacityKwh = cfg.capacity_kwh ?? 14;
    const threshold = cfg.threshold ?? 98;

    // Battery convention: positive = discharging, negative = charging
    const charging = powerW < -50;
    const discharging = powerW > 50;
    const absPowerKw = (Math.abs(powerW) / 1000).toFixed(1);

    let statusText = "inattiva";
    let dotHtml = "";
    let valueClass = "edg-c-neutral";
    let barColor = "#34d399";
    let borderClass = "";

    if (charging) {
      statusText = `&#9650; in carica ${absPowerKw} kW`;
      dotHtml = `<span class="edg-dot" style="color:#34d399"></span>`;
      valueClass = "edg-c-green";
    } else if (discharging) {
      statusText = `&#9660; in scarica ${absPowerKw} kW`;
      valueClass = "edg-c-red";
      barColor = "#f85149";
      borderClass = "edg-border-red";
    }

    if (borderClass) el.classList.add(borderClass); else {
      el.classList.remove("edg-border-red");
    }

    // Threshold marker position
    const thresholdLeft = Math.min(threshold, 100);

    el.innerHTML = `${badge}
      <div class="edg-header">
        <div class="edg-icon edg-bg-battery">B</div>
        <div>
          <div class="edg-title">Batteria Casa</div>
          <div class="edg-zone-label">accumulo</div>
        </div>
      </div>
      <div class="edg-row">
        <div class="edg-value ${valueClass}">${socPct.toFixed(0)}%</div>
        <div class="edg-sub">${dotHtml}${statusText}</div>
      </div>
      <div class="edg-progress" style="position:relative">
        <div class="edg-progress-fill" style="width:${socPct}%;background:${barColor}"></div>
        <div style="position:absolute;left:${thresholdLeft}%;top:-2px;width:1px;height:10px;background:var(--secondary-text-color,#484f58)"></div>
      </div>
      <div class="edg-detail">Capacit&agrave;: ${capacityKwh} kWh &bull; Soglia: ${threshold}%</div>
    `;
  }
```

- [ ] **Step 2: Test in browser**

Verify: SOC progress bar, threshold marker, green when charging, red when discharging, power in kW.

- [ ] **Step 3: Commit**

```bash
git add custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js
git commit -m "feat: battery card type with SOC bar and charge/discharge indicators"
```

---

### Task 6: Card type — Tesla (`_renderTesla`)

**Files:**
- Modify: `custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js`

- [ ] **Step 1: Implement `_renderTesla`**

Replace the `_renderTesla` method:

```javascript
  _renderTesla(el, cfg, badge) {
    const soc = this._stateVal(cfg.soc_entity);
    const stateStr = this._stateStr(cfg.state_entity);
    const stateAttrs = this._stateAttrs(cfg.state_entity);
    const amps = this._stateVal(cfg.amps_entity) ?? stateAttrs.current_amps ?? 0;
    const batteryKwh = cfg.battery_kwh ?? 75;
    const chargeLimit = stateAttrs.tesla_charge_limit ?? 80;
    const socPct = soc ?? 0;

    const isCharging = stateStr === "charging_solar" || stateStr === "charging_night";
    const gridVoltage = stateAttrs.grid_voltage_v ?? 230;
    const powerKw = isCharging ? ((amps * gridVoltage) / 1000).toFixed(1) : "0";
    const kwhNeeded = ((batteryKwh * (chargeLimit - socPct)) / 100).toFixed(1);
    const dailySolarKwh = stateAttrs.daily_solar_kwh ?? 0;

    // ETA calculation
    let etaText = "";
    if (isCharging && amps > 0) {
      const kwhRemaining = parseFloat(kwhNeeded);
      const chargePowerKw = (amps * gridVoltage) / 1000;
      if (chargePowerKw > 0) {
        const hoursRemaining = kwhRemaining / chargePowerKw;
        if (hoursRemaining < 1) {
          etaText = `${Math.round(hoursRemaining * 60)} min`;
        } else {
          etaText = `${Math.floor(hoursRemaining)}h ${Math.round((hoursRemaining % 1) * 60)}m`;
        }
      }
    }

    let statusText = "fermo";
    let dotHtml = "";
    let valueClass = "edg-c-neutral";

    if (stateStr === "charging_solar") {
      statusText = `in carica solare ${amps}A`;
      dotHtml = `<span class="edg-dot" style="color:#60a5fa"></span>`;
      valueClass = "edg-c-blue";
      el.classList.add("edg-border-blue");
    } else if (stateStr === "charging_night") {
      statusText = `in carica notturna ${amps}A`;
      dotHtml = `<span class="edg-dot" style="color:#60a5fa"></span>`;
      valueClass = "edg-c-blue";
      el.classList.add("edg-border-blue");
    } else if (stateStr === "waiting") {
      statusText = "in attesa";
      valueClass = "edg-c-solar";
    } else {
      el.classList.remove("edg-border-blue");
    }

    const limitLeft = Math.min(chargeLimit, 100);

    el.innerHTML = `${badge}
      <div class="edg-header">
        <div class="edg-icon edg-bg-tesla">T</div>
        <div>
          <div class="edg-title">Tesla</div>
          <div class="edg-zone-label">consumatore</div>
        </div>
      </div>
      <div class="edg-row">
        <div class="edg-value ${valueClass}">${socPct.toFixed(0)}%</div>
        <div class="edg-sub">${dotHtml}${statusText}</div>
      </div>
      <div class="edg-progress" style="position:relative">
        <div class="edg-progress-fill" style="width:${socPct}%;background:#60a5fa"></div>
        <div style="position:absolute;left:${limitLeft}%;top:-2px;width:1px;height:10px;background:var(--secondary-text-color,#484f58)"></div>
      </div>
      <div style="position:relative;height:10px">
        <div style="position:absolute;left:${limitLeft}%;transform:translateX(-50%);font-size:8px;color:var(--secondary-text-color,#484f58)">limite ${chargeLimit}%</div>
      </div>
      <div class="edg-detail">
        ${isCharging ? `~${powerKw} kW` : ""}${etaText ? ` &bull; Fine tra ${etaText}` : ""}<br>
        Solare oggi: ${dailySolarKwh} kWh<br>
        Servono: ${kwhNeeded} kWh per ${chargeLimit}%
      </div>
    `;
  }
```

- [ ] **Step 2: Test in browser**

Verify: SOC bar with limit marker, charging state with amps, ETA, kWh needed.

- [ ] **Step 3: Commit**

```bash
git add custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js
git commit -m "feat: tesla card type with SOC, ETA, charge state and kWh needed"
```

---

### Task 7: Card type — Appliance (`_renderAppliance`) with smart start-time

**Files:**
- Modify: `custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js`

This is the most complex card. It reads advisor status, computes smart start-time from hourly forecast, and shows avg kWh per run.

- [ ] **Step 1: Add smart start-time helper method**

Add before the card renderers, after the `_stateAttrs` helper:

```javascript
  /**
   * Find the best hour to start an appliance based on hourly solar forecast.
   * Returns {hour: "HH:00", status: "green"|"yellow"|"red"} or null.
   */
  _findStartTime(avgKwh, durationMinutes, forecastEntityId) {
    if (!avgKwh || avgKwh <= 0) return null;

    const attrs = this._stateAttrs(forecastEntityId);
    const hourly = attrs.hourly_forecast;
    if (!Array.isArray(hourly) || hourly.length === 0) return null;

    const durationHours = Math.ceil((durationMinutes || 60) / 60);

    // Sum currently running loads to subtract from each hour
    let runningW = 0;
    for (const c of this._config.cards) {
      if (c.type === "tesla") {
        const tState = this._stateStr(c.state_entity);
        if (tState === "charging_solar" || tState === "charging_night") {
          const tAttrs = this._stateAttrs(c.state_entity);
          const tAmps = this._stateVal(c.amps_entity) ?? tAttrs.current_amps ?? 0;
          const tV = tAttrs.grid_voltage_v ?? 230;
          runningW += tAmps * tV;
        }
      }
      if (c.type === "appliance" && c.power_entity) {
        const pw = this._stateVal(c.power_entity);
        if (pw !== null && pw > 50) runningW += pw;
      }
    }
    const runningKwhPerHour = runningW / 1000;

    // Scan hourly windows
    for (let i = 0; i <= hourly.length - durationHours; i++) {
      let windowKwh = 0;
      for (let j = 0; j < durationHours; j++) {
        const h = hourly[i + j];
        // Convert radiation W/m² to approx kWh using system size heuristic
        // radiation_w_m2 is GHI; rough conversion: (GHI * system_kwp * perf) / 1000
        // But we don't have system_kwp here — use raw surplus estimation
        // Simpler: radiation_w_m2 / 1000 gives kWh/m² for 1h, multiply by ~10 kWp * 0.6 perf
        const hourKwh = (h.radiation_w_m2 / 1000) * 10 * 0.6;
        windowKwh += Math.max(0, hourKwh - runningKwhPerHour);
      }
      if (windowKwh >= avgKwh) {
        return { hour: hourly[i].hour, status: "green" };
      }
    }

    // Check if any partial window gets close (>= 50%)
    for (let i = 0; i <= hourly.length - durationHours; i++) {
      let windowKwh = 0;
      for (let j = 0; j < durationHours; j++) {
        const h = hourly[i + j];
        const hourKwh = (h.radiation_w_m2 / 1000) * 10 * 0.6;
        windowKwh += Math.max(0, hourKwh - runningKwhPerHour);
      }
      if (windowKwh >= avgKwh * 0.5) {
        return { hour: hourly[i].hour, status: "yellow" };
      }
    }

    return null;
  }
```

- [ ] **Step 2: Implement `_renderAppliance`**

Replace the `_renderAppliance` method:

```javascript
  _renderAppliance(el, cfg, badge) {
    const advisorAttrs = this._stateAttrs(cfg.advisor_entity);
    const advisorState = this._stateStr(cfg.advisor_entity);
    const power = this._stateVal(cfg.power_entity);
    const name = cfg.name ?? advisorAttrs.appliance_name ?? "Elettrodomestico";
    const iconLetter = cfg.icon_letter ?? name.charAt(0).toUpperCase();
    const avgKwh = advisorAttrs.avg_consumption_kwh;
    const costLabel = advisorAttrs.cost_label ?? "";
    const reason = advisorAttrs.reason ?? "";
    const running = advisorAttrs.running === true;
    const currentW = power ?? advisorAttrs.current_watts ?? 0;

    // Status mapping
    let status = advisorState ?? "unknown";
    let bgClass = "edg-bg-zone";
    let borderClass = "";
    let statusColor = "edg-c-muted";
    let costText = "";

    if (status === "green") {
      bgClass = "edg-bg-green"; borderClass = "edg-border-green"; statusColor = "edg-c-green";
      costText = "Gratis";
    } else if (status === "yellow") {
      bgClass = "edg-bg-yellow"; borderClass = "edg-border-yellow"; statusColor = "edg-c-red";
      costText = "Poco";
    } else if (status === "red") {
      bgClass = "edg-bg-red"; borderClass = "edg-border-red"; statusColor = "edg-c-red";
      costText = "Costa";
    }

    if (costLabel) costText = costLabel;

    // Smart start time
    let startTimeHtml = "";
    const forecastEntity = this._findForecastEntity();
    if (forecastEntity && !running) {
      const startInfo = this._findStartTime(avgKwh, cfg.duration_minutes ?? 60, forecastEntity);
      if (startInfo) {
        const stColor = startInfo.status === "green" ? "edg-c-green" : "edg-c-solar";
        startTimeHtml = `<div class="edg-detail ${stColor}">Avvia alle ${startInfo.hour}</div>`;
      } else if (avgKwh) {
        startTimeHtml = `<div class="edg-detail edg-c-red">Solare insufficiente</div>`;
      }
    }

    // Running indicator
    const dotHtml = running ? `<span class="edg-dot" style="color:${status === 'green' ? '#34d399' : status === 'yellow' ? '#f0883e' : '#f85149'}"></span>` : "";
    const runningText = running ? `${dotHtml}${currentW}W` : "";

    // Dimmed if off and no useful recommendation
    const dimmed = !running && (status === "unknown" || !costText) ? "edg-dimmed" : "";

    el.className = `edg-card ${borderClass} ${dimmed}`;
    el.style.gridColumn = `${cfg.col} / span ${cfg.span_col ?? 1}`;
    el.style.gridRow = `${cfg.row} / span ${cfg.span_row ?? 1}`;

    el.innerHTML = `${badge}
      <div class="edg-header">
        <div class="edg-icon ${bgClass}">${iconLetter}</div>
        <div class="edg-title">${name}</div>
      </div>
      <div class="edg-value ${statusColor}" style="font-size:15px">${costText || "—"}</div>
      ${runningText ? `<div class="edg-sub">${runningText}</div>` : ""}
      <div class="edg-sub">Media: ${avgKwh ? avgKwh.toFixed(1) : "—"} kWh</div>
      ${startTimeHtml}
    `;
  }

  /** Find the first forecast entity from the config cards */
  _findForecastEntity() {
    for (const c of this._config.cards) {
      if (c.type === "forecast" && c.forecast_entity) return c.forecast_entity;
      if (c.type === "solar" && c.forecast_entity) return c.forecast_entity;
    }
    return null;
  }
```

- [ ] **Step 3: Test in browser**

Verify: status color (green/yellow/red), avg kWh, running indicator, smart start time showing "Avvia alle HH:00" or "Solare insufficiente".

- [ ] **Step 4: Commit**

```bash
git add custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js
git commit -m "feat: appliance card type with smart start-time and avg kWh per run"
```

---

### Task 8: Card type — Zone (`_renderZone`)

**Files:**
- Modify: `custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js`

- [ ] **Step 1: Implement `_renderZone`**

Replace the `_renderZone` method:

```javascript
  _renderZone(el, cfg, badge) {
    const power = this._stateVal(cfg.power_entity);
    const name = cfg.name ?? "Zona";
    const iconLetter = cfg.icon_letter ?? name.charAt(0).toUpperCase();
    const powerW = power ?? 0;
    const powerKw = (Math.abs(powerW) / 1000).toFixed(1);

    el.innerHTML = `${badge}
      <div class="edg-header">
        <div class="edg-icon edg-bg-zone">${iconLetter}</div>
        <div>
          <div class="edg-title">${name}</div>
          <div class="edg-zone-label">zona</div>
        </div>
      </div>
      <div class="edg-row">
        <div class="edg-value edg-c-neutral" style="font-size:18px">${powerKw} kW</div>
      </div>
    `;
  }
```

- [ ] **Step 2: Test in browser**

Verify: zone name, icon letter, live kW reading from the configured power entity.

- [ ] **Step 3: Commit**

```bash
git add custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js
git commit -m "feat: zone card type renderer"
```

---

### Task 9: Card type — Forecast with kWh budget bar (`_renderForecast`)

**Files:**
- Modify: `custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js`

- [ ] **Step 1: Implement `_renderForecast`**

Replace the `_renderForecast` method:

```javascript
  _renderForecast(el, cfg, badge) {
    const forecastAttrs = this._stateAttrs(cfg.forecast_entity);
    const advisorAttrs = this._stateAttrs(cfg.advisor_entity);
    const blendedKwh = forecastAttrs.blended_kwh ?? 0;
    const houseKwh = cfg.house_consumption_kwh ?? 10;

    // Compute consumer demands from all cards in config
    let teslaKwh = 0;
    let batteryKwh = 0;
    let applianceFreeKwh = 0;
    let appliancePartialKwh = 0;

    for (const c of this._config.cards) {
      if (c.type === "tesla") {
        const tSoc = this._stateVal(c.soc_entity) ?? 0;
        const tAttrs = this._stateAttrs(c.state_entity);
        const tLimit = tAttrs.tesla_charge_limit ?? 80;
        const tBat = c.battery_kwh ?? 75;
        teslaKwh = Math.max(0, (tBat * (tLimit - tSoc)) / 100);
      }
      if (c.type === "battery") {
        const bSoc = this._stateVal(c.soc_entity) ?? 0;
        const bCap = c.capacity_kwh ?? 14;
        batteryKwh = Math.max(0, (bCap * (100 - bSoc)) / 100);
      }
      if (c.type === "appliance") {
        const aAttrs = this._stateAttrs(c.advisor_entity);
        const aState = this._stateStr(c.advisor_entity);
        const aKwh = aAttrs.avg_consumption_kwh ?? 0;
        if (aState === "green") applianceFreeKwh += aKwh;
        else if (aState === "yellow") appliancePartialKwh += aKwh;
      }
    }

    const totalDemand = houseKwh + batteryKwh + teslaKwh + applianceFreeKwh + appliancePartialKwh;
    const excess = Math.max(0, blendedKwh - totalDemand);
    const deficit = Math.max(0, totalDemand - blendedKwh);
    const total = Math.max(blendedKwh, totalDemand);

    const pct = (v) => total > 0 ? ((v / total) * 100).toFixed(1) : 0;

    // Plan text
    const planAttrs = this._stateAttrs(cfg.plan_entity);
    const planStr = this._stateStr(cfg.plan_entity);
    const planText = planStr === "Night charge planned" ? "Carica notturna" : "Solo solare";

    const consumerKwh = (teslaKwh + applianceFreeKwh + appliancePartialKwh).toFixed(1);

    el.innerHTML = `${badge}
      <div class="edg-header">
        <div class="edg-icon edg-bg-plan">P</div>
        <div class="edg-title">Previsioni e Piano</div>
      </div>
      <div style="display:flex;gap:20px;margin-top:6px;flex-wrap:wrap">
        <div>
          <div style="font-size:10px" class="edg-c-muted">Domani</div>
          <div style="font-size:17px;font-weight:700" class="edg-c-solar">${blendedKwh.toFixed(1)} kWh</div>
        </div>
        <div>
          <div style="font-size:10px" class="edg-c-muted">Eccedenza</div>
          <div style="font-size:17px;font-weight:700" class="edg-c-green">${excess.toFixed(1)} kWh</div>
        </div>
        <div>
          <div style="font-size:10px" class="edg-c-muted">Fabbisogno</div>
          <div style="font-size:17px;font-weight:700" class="edg-c-blue">${consumerKwh} kWh</div>
        </div>
        <div>
          <div style="font-size:10px" class="edg-c-muted">Piano</div>
          <div style="font-size:17px;font-weight:700" class="${excess > 0 ? 'edg-c-green' : 'edg-c-red'}">${planText}</div>
        </div>
      </div>
      <div class="edg-budget">
        <div class="edg-budget-label">Budget energetico &mdash; ${blendedKwh.toFixed(1)} kWh previsti</div>
        <div class="edg-budget-bar">
          ${houseKwh > 0 ? `<div class="edg-budget-seg" style="width:${pct(houseKwh)}%;background:var(--divider-color,#21262d);color:var(--primary-text-color,#e6edf3)">Casa ${houseKwh.toFixed(0)}</div>` : ""}
          ${batteryKwh > 0 ? `<div class="edg-budget-seg" style="width:${pct(batteryKwh)}%;background:#1f6feb;color:#e6edf3">Batt ${batteryKwh.toFixed(0)}</div>` : ""}
          ${teslaKwh > 0 ? `<div class="edg-budget-seg" style="width:${pct(teslaKwh)}%;background:#60a5fa;color:#0d1117">Tesla ${teslaKwh.toFixed(0)}</div>` : ""}
          ${applianceFreeKwh > 0 ? `<div class="edg-budget-seg" style="width:${pct(applianceFreeKwh)}%;background:#34d399;color:#0d1117">${applianceFreeKwh.toFixed(1)}</div>` : ""}
          ${appliancePartialKwh > 0 ? `<div class="edg-budget-seg" style="width:${pct(appliancePartialKwh)}%;background:#f0883e;color:#0d1117">${appliancePartialKwh.toFixed(1)}</div>` : ""}
          ${excess > 0 ? `<div class="edg-budget-seg" style="width:${pct(excess)}%;background:#238636;color:#e6edf3">+${excess.toFixed(1)}</div>` : ""}
          ${deficit > 0 ? `<div class="edg-budget-seg" style="width:${pct(deficit)}%;background:#da3633;color:#e6edf3">-${deficit.toFixed(1)}</div>` : ""}
        </div>
        <div class="edg-budget-legend">
          <span><span class="edg-budget-dot" style="background:var(--divider-color,#21262d);border:1px solid var(--secondary-text-color)"></span>Casa</span>
          <span><span class="edg-budget-dot" style="background:#1f6feb"></span>Batteria</span>
          <span><span class="edg-budget-dot" style="background:#60a5fa"></span>Tesla</span>
          <span><span class="edg-budget-dot" style="background:#34d399"></span>Elettrod. (gratis)</span>
          <span><span class="edg-budget-dot" style="background:#f0883e"></span>Elettrod. (parziale)</span>
          <span><span class="edg-budget-dot" style="background:#238636"></span>Eccedenza</span>
        </div>
      </div>
    `;
  }
```

- [ ] **Step 2: Test in browser**

Verify: forecast values, budget bar with proportional segments, plan text, legend.

- [ ] **Step 3: Commit**

```bash
git add custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js
git commit -m "feat: forecast card type with kWh budget bar and plan"
```

---

### Task 10: Card type — Debug (`_renderDebug`)

**Files:**
- Modify: `custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js`

- [ ] **Step 1: Implement `_renderDebug`**

Replace the `_renderDebug` method:

```javascript
  _renderDebug(el, cfg, badge) {
    // Collect all entities from all cards in config
    const groups = {};
    const entityKeys = [
      "entity", "forecast_entity", "state_entity", "soc_entity",
      "power_entity", "amps_entity", "advisor_entity", "energy_entity",
      "plan_entity",
    ];

    for (const c of this._config.cards) {
      const groupName = c.type.charAt(0).toUpperCase() + c.type.slice(1);
      const label = c.name ? `${groupName} — ${c.name}` : groupName;
      if (!groups[label]) groups[label] = [];

      for (const key of entityKeys) {
        if (c[key]) {
          const state = this._hass.states[c[key]];
          const available = state && state.state !== "unavailable" && state.state !== "unknown";
          groups[label].push({
            entity_id: c[key],
            key: key,
            available: available,
            state: state?.state ?? "N/A",
            attributes: state?.attributes ?? {},
          });
        }
      }
    }

    // Build all entities JSON for copy
    const allData = {};
    for (const [group, entities] of Object.entries(groups)) {
      allData[group] = entities.map(e => ({
        entity_id: e.entity_id,
        state: e.state,
        attributes: e.attributes,
      }));
    }
    const jsonStr = JSON.stringify(allData, null, 2);

    // Render collapsible groups
    let groupsHtml = "";
    for (const [group, entities] of Object.entries(groups)) {
      let entitiesHtml = "";
      for (const e of entities) {
        const healthClass = e.available ? "edg-debug-ok" : "edg-debug-err";
        const healthLabel = e.available ? "disponibile" : "non disponibile";
        entitiesHtml += `
          <div style="margin-bottom:8px">
            <div style="font-size:11px">
              <span class="edg-debug-health ${healthClass}"></span>
              <b>${e.entity_id}</b>
              <span class="edg-c-muted">(${e.key})</span>
              — stato: <code>${e.state}</code>
              <span class="edg-c-muted">[${healthLabel}]</span>
            </div>
            <pre class="edg-debug-pre">${JSON.stringify(e.attributes, null, 2)}</pre>
          </div>
        `;
      }
      groupsHtml += `
        <details class="edg-debug-group" open>
          <summary>Entit&agrave; ${group} (${entities.length})</summary>
          ${entitiesHtml}
        </details>
      `;
    }

    el.innerHTML = `${badge}
      <div class="edg-header">
        <div class="edg-icon edg-bg-zone">D</div>
        <div class="edg-title">Debug Entit&agrave;</div>
      </div>
      <div style="margin-top:8px">${groupsHtml}</div>
      <button class="edg-copy-btn" id="edg-copy-debug">Copia JSON</button>
    `;

    const copyBtn = el.querySelector("#edg-copy-debug");
    if (copyBtn) {
      copyBtn.onclick = () => {
        navigator.clipboard.writeText(jsonStr).then(() => {
          copyBtn.textContent = "Copiato!";
          setTimeout(() => { copyBtn.textContent = "Copia JSON"; }, 2000);
        });
      };
    }
  }
```

- [ ] **Step 2: Test in browser**

Verify: collapsible groups per card type, entity health dots (green/red), full attribute JSON, copy button works.

- [ ] **Step 3: Commit**

```bash
git add custom_components/tesla_solar_charging/frontend/energy-dashboard-card.js
git commit -m "feat: debug card type with entity health, grouped attributes, and copy JSON"
```

---

### Task 11: Panel integration — wrap dashboard card in sidebar

**Files:**
- Modify: `custom_components/tesla_solar_charging/frontend/panel.js`

The existing panel.js (634 lines) gets a major simplification: it imports and renders the `energy-dashboard-card` at full width, passing a default config based on the integration's configured entities.

- [ ] **Step 1: Add dashboard card import to panel.js**

At the top of `panel.js`, before the class definition (line 1), add:

```javascript
// Import the energy dashboard card component
import "./energy-dashboard-card.js";
```

Note: This works because HA serves the `frontend/` directory. If the module import fails (some HA setups), fall back to dynamic import in step 2.

- [ ] **Step 2: Add dashboard rendering method to the panel class**

In `TeslaSolarChargingPanel`, add a new method after `_render()` that creates an `energy-dashboard-card` element with a default config built from the integration's known entities:

```javascript
  _renderDashboard() {
    // Build default card config from known integration entities
    const entryId = this._panel?.config?.entry_id ?? "";
    const prefix = "sensor.tesla_solar_charging_";

    const defaultConfig = {
      grid: { columns: 6, rows: 6, gap: 8 },
      cards: [
        {
          type: "solar",
          col: 1, row: 1, span_col: 2, span_row: 1,
          forecast_entity: `${prefix}solar_forecast`,
          state_entity: `${prefix}state`,
        },
        {
          type: "grid",
          col: 3, row: 1, span_col: 2, span_row: 1,
        },
        {
          type: "battery",
          col: 5, row: 1, span_col: 2, span_row: 2,
        },
        {
          type: "tesla",
          col: 1, row: 2, span_col: 2, span_row: 2,
          state_entity: `${prefix}state`,
          amps_entity: `${prefix}charging_amps`,
        },
        {
          type: "forecast",
          col: 1, row: 4, span_col: 4, span_row: 1,
          forecast_entity: `${prefix}solar_forecast`,
        },
        {
          type: "debug",
          col: 1, row: 5, span_col: 6, span_row: 2,
        },
      ],
    };

    // Check if dashboard element already exists
    let dashEl = this.querySelector("energy-dashboard-card");
    if (!dashEl) {
      dashEl = document.createElement("energy-dashboard-card");
      dashEl.setConfig(defaultConfig);
      this.appendChild(dashEl);
    }
    dashEl.hass = this._hass;
  }
```

- [ ] **Step 3: Call `_renderDashboard()` from the hass setter**

In the `set hass()` method (line 2), add a call to `_renderDashboard()` after the existing `_update()` call so the dashboard card gets hass updates:

```javascript
  set hass(hass) {
    this._hass = hass;
    if (!this.innerHTML) {
      this._render();
    }
    this._update();
    this._renderDashboard();
  }
```

- [ ] **Step 4: Test in browser**

Navigate to the Tesla Solar sidebar panel. Verify the energy dashboard grid appears below the existing panel content. All card types render correctly with live data.

- [ ] **Step 5: Commit**

```bash
git add custom_components/tesla_solar_charging/frontend/panel.js
git commit -m "feat: integrate energy dashboard card into sidebar panel"
```

---

### Task 12: Update FEATURES.md and bump version

**Files:**
- Modify: `docs/FEATURES.md`
- Modify: `custom_components/tesla_solar_charging/const.py:4`

- [ ] **Step 1: Update FEATURES.md checkboxes**

Mark all implemented features as done (`[x]`) in `docs/FEATURES.md`.

- [ ] **Step 2: Bump version**

In `custom_components/tesla_solar_charging/const.py`, change line 4:

```python
VERSION = "4.0.0"
```

- [ ] **Step 3: Commit all remaining changes**

```bash
git add docs/FEATURES.md custom_components/tesla_solar_charging/const.py
git commit -m "feat: energy dashboard grid v1 — configurable card grid with smart start-times and kWh budget"
```

---

## Self-Review Results

**Spec coverage check:**
- Free-form grid layout: Task 2
- Card types (solar, grid, battery, tesla, appliance, zone, forecast, debug): Tasks 3-10
- Smart start-time: Task 7 (`_findStartTime`)
- kWh budget bar: Task 9 (`_renderForecast`)
- Average kWh per run: Task 7 (reads `avg_consumption_kwh` from advisor)
- Zone cards: Task 8
- Debug card with all entities: Task 10
- Italian labels: All tasks use Italian
- Hourly forecast attribute: Task 1
- Panel integration: Task 11
- Both Lovelace card + panel: Task 2 (card registration) + Task 11 (panel)
- FEATURES.md: Task 12

**Placeholder scan:** No TBDs, TODOs, or vague instructions found. All steps contain actual code.

**Type consistency check:**
- `_stateVal`, `_stateStr`, `_stateAttrs` — used consistently across all renderers
- `_findStartTime` — used only in Task 7, signature matches
- Config keys (`entity`, `soc_entity`, `power_entity`, etc.) — consistent between YAML example and renderer code
- CSS classes (`edg-*` prefix) — consistent across all tasks
