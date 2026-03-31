/**
 * Energy Dashboard Card — configurable grid dashboard
 */

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
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          color: var(--primary-text-color, #e6edf3);
        }
        .edg-grid {
          display: grid;
          grid-template-columns: repeat(${g.columns}, 1fr);
          grid-template-rows: repeat(${g.rows}, minmax(90px, auto));
          gap: ${g.gap}px;
          padding: ${g.gap}px;
        }
        .edg-card {
          background: var(--card-background-color, #161b22);
          border: 1px solid var(--divider-color, #30363d);
          border-radius: 10px;
          padding: 12px 14px;
          overflow: hidden;
          transition: border-color 0.2s;
        }
        .edg-card:hover { border-color: var(--secondary-text-color, #484f58); }
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
        .edg-header { display: flex; align-items: center; gap: 8px; }
        .edg-title { font-size: 13px; font-weight: 600; line-height: 1.2; }
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
        .edg-dimmed { opacity: 0.4; }
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
        /* Consumption bar for zones */
        .edg-cons-bar {
          height: 4px;
          border-radius: 2px;
          margin-top: 6px;
          background: var(--divider-color, #21262d);
          overflow: hidden;
        }
        .edg-cons-fill {
          height: 100%;
          border-radius: 2px;
          transition: width 0.5s;
        }
      </style>
      <div class="edg-wrapper">
        <div class="edg-grid" id="edg-grid"></div>
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
      grid.appendChild(el);
    }
  }

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
      switch (cfg.type) {
        case "solar":    this._renderSolar(el, cfg); break;
        case "grid":     this._renderGrid(el, cfg); break;
        case "battery":  this._renderBattery(el, cfg); break;
        case "tesla":    this._renderTesla(el, cfg); break;
        case "appliance": this._renderAppliance(el, cfg); break;
        case "zone":     this._renderZone(el, cfg); break;
        case "forecast": this._renderForecast(el, cfg); break;
        default:
          el.innerHTML = `<div class="edg-sub">Unknown: ${cfg.type}</div>`;
      }
    }
  }

  _findForecastEntity() {
    for (const c of this._config.cards) {
      if (c.type === "forecast" && c.forecast_entity) return c.forecast_entity;
      if (c.type === "solar" && c.forecast_entity) return c.forecast_entity;
    }
    return null;
  }

  // ── Solar Card ──
  _renderSolar(el, cfg) {
    const power = this._stateVal(cfg.entity);
    const attrs = this._stateAttrs(cfg.forecast_entity);
    const stateAttrs = this._stateAttrs(cfg.state_entity);
    const blendedKwh = attrs.blended_kwh;
    const todayProduced = stateAttrs.daily_solar_kwh;
    const producing = power !== null && power > 10;
    const powerKw = power !== null ? (power / 1000).toFixed(1) : "0";

    let todayPct = 0;
    if (blendedKwh > 0 && typeof todayProduced === "number") {
      todayPct = Math.min(100, (todayProduced / blendedKwh) * 100);
    }
    const todayStr = typeof todayProduced === "number" ? todayProduced.toFixed(1) : "0";
    const fcStr = typeof blendedKwh === "number" ? blendedKwh.toFixed(1) : "—";

    el.innerHTML = `
      <div class="edg-header">
        <div class="edg-icon edg-bg-solar">S</div>
        <div>
          <div class="edg-title">Solare</div>
          <div class="edg-zone-label">fonte</div>
        </div>
      </div>
      <div class="edg-row">
        <div class="edg-value ${producing ? 'edg-c-solar' : 'edg-c-muted'}">${powerKw} kW</div>
        <div class="edg-sub">${producing ? '<span class="edg-dot" style="color:#fbbf24"></span>in produzione' : 'spento'}</div>
      </div>
      <div class="edg-detail">Oggi: ${todayStr} / ${fcStr} kWh</div>
      <div class="edg-progress">
        <div class="edg-progress-fill" style="width:${todayPct}%;background:#fbbf24"></div>
      </div>`;
  }

  // ── Grid Card ──
  _renderGrid(el, cfg) {
    const power = this._stateVal(cfg.entity);
    const powerW = power ?? 0;
    const importing = powerW > 50;
    const exporting = powerW < -50;
    const absKw = (Math.abs(powerW) / 1000).toFixed(1);

    let statusText = "bilanciata", valueClass = "edg-c-muted";
    el.classList.remove("edg-border-green", "edg-border-red");
    if (exporting) {
      statusText = "esportazione"; valueClass = "edg-c-green";
      el.classList.add("edg-border-green");
    } else if (importing) {
      statusText = "importazione"; valueClass = "edg-c-red";
      el.classList.add("edg-border-red");
    }

    // Consumption bar: scale 0-3kW (Italian meter limit)
    const barPct = Math.min(100, (Math.abs(powerW) / 3000) * 100);
    const barColor = exporting ? "#34d399" : importing ? "#f85149" : "#484f58";

    el.innerHTML = `
      <div class="edg-header">
        <div class="edg-icon edg-bg-grid">R</div>
        <div>
          <div class="edg-title">Rete</div>
          <div class="edg-zone-label">${statusText}</div>
        </div>
      </div>
      <div class="edg-value ${valueClass}">${absKw} kW</div>
      <div class="edg-cons-bar">
        <div class="edg-cons-fill" style="width:${barPct}%;background:${barColor}"></div>
      </div>`;
  }

  // ── Battery Card ──
  _renderBattery(el, cfg) {
    const soc = this._stateVal(cfg.soc_entity);
    const power = this._stateVal(cfg.power_entity);
    const socPct = soc ?? 0;
    const powerW = power ?? 0;
    const capacityKwh = cfg.capacity_kwh ?? 14;
    const threshold = cfg.threshold ?? 98;
    const charging = powerW < -50;
    const discharging = powerW > 50;
    const absPowerKw = (Math.abs(powerW) / 1000).toFixed(1);
    let statusText = "inattiva", valueClass = "edg-c-neutral", barColor = "#34d399";
    el.classList.remove("edg-border-red");
    if (charging) {
      statusText = `\u25b2 in carica ${absPowerKw} kW`;
      valueClass = "edg-c-green";
    } else if (discharging) {
      statusText = `\u25bc in scarica ${absPowerKw} kW`;
      valueClass = "edg-c-red"; barColor = "#f85149";
      el.classList.add("edg-border-red");
    }
    const thresholdLeft = Math.min(threshold, 100);
    el.innerHTML = `
      <div class="edg-header">
        <div class="edg-icon edg-bg-battery">B</div>
        <div>
          <div class="edg-title">Batteria Casa</div>
          <div class="edg-zone-label">accumulo</div>
        </div>
      </div>
      <div class="edg-row">
        <div class="edg-value ${valueClass}">${socPct.toFixed(0)}%</div>
        <div class="edg-sub">${charging ? '<span class="edg-dot" style="color:#34d399"></span>' : ''}${statusText}</div>
      </div>
      <div class="edg-progress" style="position:relative">
        <div class="edg-progress-fill" style="width:${socPct}%;background:${barColor}"></div>
        <div style="position:absolute;left:${thresholdLeft}%;top:-2px;width:1px;height:10px;background:var(--secondary-text-color,#484f58)"></div>
      </div>
      <div class="edg-detail">Capacit\u00e0: ${capacityKwh} kWh \u00b7 Soglia: ${threshold}%</div>`;
  }

  // ── Tesla Card ──
  _renderTesla(el, cfg) {
    const soc = this._stateVal(cfg.soc_entity);
    const stateStr = this._stateStr(cfg.state_entity);
    const stateAttrs = this._stateAttrs(cfg.state_entity);
    const amps = this._stateVal(cfg.amps_entity) ?? stateAttrs.current_amps ?? 0;
    const batteryKwh = cfg.battery_kwh ?? 75;
    const chargeLimit = stateAttrs.tesla_charge_limit ?? 80;
    const socPct = soc ?? 0;
    const isCharging = stateStr === "charging_solar" || stateStr === "charging_night";
    const gridVoltage = stateAttrs.grid_voltage_v ?? 230;
    const kwhNeeded = ((batteryKwh * (chargeLimit - socPct)) / 100).toFixed(1);
    const dailySolarKwh = stateAttrs.daily_solar_kwh ?? 0;

    let etaText = "";
    if (isCharging && amps > 0) {
      const chargePowerKw = (amps * gridVoltage) / 1000;
      if (chargePowerKw > 0) {
        const hours = parseFloat(kwhNeeded) / chargePowerKw;
        etaText = hours < 1 ? `${Math.round(hours * 60)}min` : `${Math.floor(hours)}h${Math.round((hours % 1) * 60)}m`;
      }
    }

    let statusText = "fermo", valueClass = "edg-c-neutral", dotHtml = "";
    el.classList.remove("edg-border-blue");
    if (stateStr === "charging_solar") {
      statusText = `solare ${amps}A`; dotHtml = '<span class="edg-dot" style="color:#60a5fa"></span>';
      valueClass = "edg-c-blue"; el.classList.add("edg-border-blue");
    } else if (stateStr === "charging_night") {
      statusText = `notturna ${amps}A`; dotHtml = '<span class="edg-dot" style="color:#60a5fa"></span>';
      valueClass = "edg-c-blue"; el.classList.add("edg-border-blue");
    } else if (stateStr === "waiting") {
      statusText = "in attesa"; valueClass = "edg-c-solar";
    }

    const limitLeft = Math.min(chargeLimit, 100);
    el.innerHTML = `
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
        ${isCharging ? `~${((amps * gridVoltage) / 1000).toFixed(1)} kW` : ""}${etaText ? ` \u00b7 Fine tra ${etaText}` : ""}<br>
        Solare oggi: ${typeof dailySolarKwh === "number" ? dailySolarKwh.toFixed(1) : dailySolarKwh} kWh<br>
        Servono: ${kwhNeeded} kWh per ${chargeLimit}%
      </div>`;
  }

  // ── Appliance Card ──
  _renderAppliance(el, cfg) {
    const power = this._stateVal(cfg.power_entity);
    const energy = this._stateVal(cfg.energy_entity);
    const name = cfg.name ?? "Elettrodomestico";
    const iconLetter = cfg.icon_letter ?? name.charAt(0).toUpperCase();
    const running = power !== null && power > 30;
    const powerW = power ?? 0;
    const avgKwh = cfg.avg_kwh ?? null;

    // Determine status from advisor entity if available, else from power
    const advisorAttrs = this._stateAttrs(cfg.advisor_entity);
    const advisorState = this._stateStr(cfg.advisor_entity);
    let status = advisorState;
    let costText = "";

    if (status === "green") { costText = "Gratis"; }
    else if (status === "yellow") { costText = "Parziale"; }
    else if (status === "red") { costText = "Costa"; }
    else {
      // No advisor — estimate from solar forecast
      const forecastEntity = this._findForecastEntity();
      if (forecastEntity) {
        const startInfo = this._findStartTime(avgKwh ?? 1.5, cfg.duration_minutes ?? 60, forecastEntity);
        if (startInfo) {
          status = startInfo.status;
          costText = startInfo.status === "green" ? "Gratis" : "Parziale";
        }
      }
    }

    let bgClass = "edg-bg-zone", borderClass = "";
    if (running) {
      bgClass = "edg-bg-blue"; borderClass = "edg-border-blue";
    } else if (status === "green") {
      bgClass = "edg-bg-green"; borderClass = "edg-border-green";
    } else if (status === "yellow") {
      bgClass = "edg-bg-yellow"; borderClass = "edg-border-yellow";
    }

    // Start time suggestion
    let startHtml = "";
    if (!running) {
      const forecastEntity = this._findForecastEntity();
      if (forecastEntity) {
        const startInfo = this._findStartTime(avgKwh ?? 1.5, cfg.duration_minutes ?? 60, forecastEntity);
        if (startInfo) {
          const stColor = startInfo.status === "green" ? "edg-c-green" : "edg-c-solar";
          startHtml = `<div class="edg-detail ${stColor}">Avvia alle ${startInfo.hour}</div>`;
        }
      }
    }

    const dimmed = !running && !costText ? "edg-dimmed" : "";
    el.className = `edg-card ${borderClass} ${dimmed}`;
    el.style.gridColumn = `${cfg.col} / span ${cfg.span_col ?? 1}`;
    el.style.gridRow = `${cfg.row} / span ${cfg.span_row ?? 1}`;

    // Running status
    let statusHtml = "";
    if (running) {
      const durMin = cfg.duration_minutes ?? 60;
      statusHtml = `<div class="edg-sub"><span class="edg-dot" style="color:#60a5fa"></span>${powerW.toFixed(0)}W</div>`;
    } else if (costText) {
      const statusColor = status === "green" ? "edg-c-green" : status === "yellow" ? "edg-c-solar" : "edg-c-muted";
      statusHtml = `<div class="edg-sub ${statusColor}">${costText}</div>`;
    } else {
      statusHtml = `<div class="edg-sub edg-c-muted">\u2014</div>`;
    }

    // Energy today
    const energyStr = energy !== null ? `${energy.toFixed(1)} kWh oggi` : "";

    el.innerHTML = `
      <div class="edg-header">
        <div class="edg-icon ${bgClass}">${iconLetter}</div>
        <div class="edg-title">${name}</div>
      </div>
      ${statusHtml}
      ${energyStr ? `<div class="edg-detail">${energyStr}</div>` : ""}
      ${startHtml}`;
  }

  // ── Zone Card ──
  _renderZone(el, cfg) {
    const power = this._stateVal(cfg.power_entity);
    const name = cfg.name ?? "Zona";
    const iconLetter = cfg.icon_letter ?? name.charAt(0).toUpperCase();
    const powerW = power ?? 0;
    const powerKw = (Math.abs(powerW) / 1000).toFixed(1);
    // Consumption bar: scale 0-3kW
    const maxW = cfg.max_power ?? 3000;
    const barPct = Math.min(100, (Math.abs(powerW) / maxW) * 100);
    const barColor = powerW > 1500 ? "#f85149" : powerW > 500 ? "#f0883e" : "#34d399";

    el.innerHTML = `
      <div class="edg-header">
        <div class="edg-icon edg-bg-zone">${iconLetter}</div>
        <div>
          <div class="edg-title">${name}</div>
          <div class="edg-zone-label">consumo</div>
        </div>
      </div>
      <div class="edg-value edg-c-neutral" style="font-size:18px">${powerKw} kW</div>
      <div class="edg-cons-bar">
        <div class="edg-cons-fill" style="width:${barPct}%;background:${barColor}"></div>
      </div>`;
  }

  // ── Forecast Card ──
  _renderForecast(el, cfg) {
    const forecastAttrs = this._stateAttrs(cfg.forecast_entity);
    const blendedKwh = forecastAttrs.blended_kwh ?? 0;
    const houseKwh = cfg.house_consumption_kwh ?? 10;
    let teslaKwh = 0, batteryKwh = 0;
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
    }
    const totalDemand = houseKwh + batteryKwh + teslaKwh;
    const excess = Math.max(0, blendedKwh - totalDemand);
    const deficit = Math.max(0, totalDemand - blendedKwh);
    const total = Math.max(blendedKwh, totalDemand);
    const pct = (v) => total > 0 ? ((v / total) * 100).toFixed(1) : 0;
    const planStr = this._stateStr(cfg.plan_entity);
    const planText = planStr === "Night charge planned" ? "Carica notturna" : "Solo solare";

    el.innerHTML = `
      <div class="edg-header">
        <div class="edg-icon edg-bg-plan">P</div>
        <div class="edg-title">Previsioni e Piano</div>
      </div>
      <div style="display:flex;gap:20px;margin-top:6px;flex-wrap:wrap">
        <div>
          <div style="font-size:10px" class="edg-c-muted">Produzione</div>
          <div style="font-size:17px;font-weight:700" class="edg-c-solar">${blendedKwh.toFixed(1)} kWh</div>
        </div>
        <div>
          <div style="font-size:10px" class="edg-c-muted">Eccedenza</div>
          <div style="font-size:17px;font-weight:700" class="edg-c-green">${excess.toFixed(1)} kWh</div>
        </div>
        <div>
          <div style="font-size:10px" class="edg-c-muted">Fabbisogno</div>
          <div style="font-size:17px;font-weight:700" class="edg-c-blue">${teslaKwh.toFixed(1)} kWh</div>
        </div>
        <div>
          <div style="font-size:10px" class="edg-c-muted">Piano</div>
          <div style="font-size:17px;font-weight:700" class="${excess > 0 ? 'edg-c-green' : 'edg-c-red'}">${planText}</div>
        </div>
      </div>
      <div class="edg-budget">
        <div class="edg-budget-label">Budget energetico \u2014 ${blendedKwh.toFixed(1)} kWh previsti</div>
        <div class="edg-budget-bar">
          ${houseKwh > 0 ? `<div class="edg-budget-seg" style="width:${pct(houseKwh)}%;background:var(--divider-color,#21262d);color:var(--primary-text-color,#e6edf3)">Casa ${houseKwh.toFixed(0)}</div>` : ""}
          ${batteryKwh > 0 ? `<div class="edg-budget-seg" style="width:${pct(batteryKwh)}%;background:#1f6feb;color:#e6edf3">Batt ${batteryKwh.toFixed(0)}</div>` : ""}
          ${teslaKwh > 0 ? `<div class="edg-budget-seg" style="width:${pct(teslaKwh)}%;background:#60a5fa;color:#0d1117">Tesla ${teslaKwh.toFixed(0)}</div>` : ""}
          ${excess > 0 ? `<div class="edg-budget-seg" style="width:${pct(excess)}%;background:#238636;color:#e6edf3">+${excess.toFixed(1)}</div>` : ""}
          ${deficit > 0 ? `<div class="edg-budget-seg" style="width:${pct(deficit)}%;background:#da3633;color:#e6edf3">-${deficit.toFixed(1)}</div>` : ""}
        </div>
        <div class="edg-budget-legend">
          <span><span class="edg-budget-dot" style="background:var(--divider-color,#21262d);border:1px solid var(--secondary-text-color)"></span>Casa</span>
          <span><span class="edg-budget-dot" style="background:#1f6feb"></span>Batteria</span>
          <span><span class="edg-budget-dot" style="background:#60a5fa"></span>Tesla</span>
          <span><span class="edg-budget-dot" style="background:#238636"></span>Eccedenza</span>
        </div>
      </div>`;
  }

  _findStartTime(avgKwh, durationMinutes, forecastEntityId) {
    if (!avgKwh || avgKwh <= 0) return null;
    const attrs = this._stateAttrs(forecastEntityId);
    const hourly = attrs.hourly_forecast;
    if (!Array.isArray(hourly) || hourly.length === 0) return null;
    const durationHours = Math.ceil((durationMinutes || 60) / 60);
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
    for (let i = 0; i <= hourly.length - durationHours; i++) {
      let windowKwh = 0;
      for (let j = 0; j < durationHours; j++) {
        const h = hourly[i + j];
        const hourKwh = (h.radiation_w_m2 / 1000) * 10 * 0.6;
        windowKwh += Math.max(0, hourKwh - runningKwhPerHour);
      }
      if (windowKwh >= avgKwh) return { hour: hourly[i].hour, status: "green" };
    }
    for (let i = 0; i <= hourly.length - durationHours; i++) {
      let windowKwh = 0;
      for (let j = 0; j < durationHours; j++) {
        const h = hourly[i + j];
        const hourKwh = (h.radiation_w_m2 / 1000) * 10 * 0.6;
        windowKwh += Math.max(0, hourKwh - runningKwhPerHour);
      }
      if (windowKwh >= avgKwh * 0.5) return { hour: hourly[i].hour, status: "yellow" };
    }
    return null;
  }
}

if (!customElements.get("energy-dashboard-card")) {
  customElements.define("energy-dashboard-card", EnergyDashboardCard);
}
window.customCards = window.customCards || [];
if (!window.customCards.some(c => c.type === "energy-dashboard-card")) {
  window.customCards.push({
    type: "energy-dashboard-card",
    name: "Energy Dashboard Grid",
    description: "Griglia energetica configurabile",
  });
}
