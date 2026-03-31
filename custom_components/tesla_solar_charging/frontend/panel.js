class TeslaSolarChargingPanel extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._initialized = true;
      this._render();
    }
    this._update();
  }

  set panel(panel) {
    this._config = panel.config || {};
  }

  // Resolve entity ID — tries full ID first, then with tesla_solar_charging_ prefix
  _e(shortId) {
    // Already a full entity ID
    if (this._hass.states[shortId]) return shortId;
    // Try adding prefix: sensor.state → sensor.tesla_solar_charging_state
    const dot = shortId.indexOf(".");
    if (dot > 0) {
      const domain = shortId.slice(0, dot);
      const name = shortId.slice(dot + 1);
      const prefixed = `${domain}.tesla_solar_charging_${name}`;
      if (this._hass.states[prefixed]) return prefixed;
    }
    return shortId;
  }

  _val(entityId) {
    const resolved = this._e(entityId);
    const s = this._hass.states[resolved];
    return s ? s.state : "N/A";
  }

  _states(entityId) {
    const resolved = this._e(entityId);
    return this._hass.states[resolved];
  }

  _render() {
    this.innerHTML = `
      <style>
        :host { display: block; }
        .tsc-wrap {
          max-width: 900px;
          margin: 0 auto;
          padding: 16px;
          font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
          color: var(--primary-text-color, #333);
        }

        /* Hero banner */
        .tsc-hero {
          border-radius: 16px;
          padding: 20px 24px;
          margin-bottom: 16px;
          display: flex;
          align-items: center;
          gap: 16px;
        }
        .tsc-hero-icon {
          font-size: 36px;
          line-height: 1;
        }
        .tsc-hero-text { flex: 1; }
        .tsc-hero-state {
          font-size: 22px;
          font-weight: 600;
          margin-bottom: 2px;
        }
        .tsc-hero-reason {
          font-size: 13px;
          opacity: 0.85;
        }
        .tsc-hero-badges {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }
        .tsc-hero.idle     { background: var(--card-background-color, #fff); border: 2px solid var(--divider-color, #ddd); }
        .tsc-hero.waiting   { background: #fff3e0; border: 2px solid #ffb74d; }
        .tsc-hero.charging  { background: #e8f5e9; border: 2px solid #66bb6a; }
        .tsc-hero.night     { background: #e3f2fd; border: 2px solid #42a5f5; }
        .tsc-hero.error     { background: #ffebee; border: 2px solid #ef5350; }
        .tsc-hero.planned   { background: #f3e5f5; border: 2px solid #ab47bc; }

        /* Grid */
        .tsc-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
        }
        .tsc-card {
          background: var(--card-background-color, #fff);
          border-radius: 12px;
          padding: 16px;
          box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0,0,0,.08));
        }
        .tsc-card.wide { grid-column: 1 / -1; }
        .tsc-card.alert { border-left: 4px solid #ef5350; }
        .tsc-card.highlight { border-left: 4px solid #ff9800; }
        .tsc-card h2 {
          margin: 0 0 10px 0;
          font-size: 12px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.8px;
          opacity: 0.5;
        }

        /* Metric rows */
        .tsc-metric {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 5px 0;
        }
        .tsc-metric + .tsc-metric {
          border-top: 1px solid var(--divider-color, rgba(0,0,0,.06));
        }
        .tsc-metric-label {
          font-size: 13px;
          opacity: 0.7;
        }
        .tsc-metric-value {
          font-size: 15px;
          font-weight: 600;
          text-align: right;
        }

        /* Big number */
        .tsc-big {
          font-size: 28px;
          font-weight: 700;
          line-height: 1.1;
        }
        .tsc-big-unit {
          font-size: 14px;
          font-weight: 400;
          opacity: 0.6;
        }
        .tsc-big-sub {
          font-size: 12px;
          font-weight: 400;
          opacity: 0.6;
          margin-top: 2px;
        }

        /* Progress bar */
        .tsc-progress {
          width: 100%;
          height: 8px;
          background: var(--secondary-background-color, #eee);
          border-radius: 4px;
          margin: 6px 0;
          overflow: hidden;
        }
        .tsc-progress-bar {
          height: 100%;
          border-radius: 4px;
          transition: width 0.5s ease;
        }

        /* Badge */
        .tsc-tag {
          display: inline-block;
          padding: 3px 10px;
          border-radius: 12px;
          font-size: 11px;
          font-weight: 600;
        }
        .tsc-tag.green  { background: #c8e6c9; color: #2e7d32; }
        .tsc-tag.orange { background: #ffe0b2; color: #e65100; }
        .tsc-tag.red    { background: #ffcdd2; color: #c62828; }
        .tsc-tag.blue   { background: #bbdefb; color: #1565c0; }
        .tsc-tag.grey   { background: var(--secondary-background-color, #eee); color: var(--primary-text-color, #666); }
        .tsc-tag.purple { background: #e1bee7; color: #6a1b9a; }

        /* Outlook bars */
        .tsc-outlook-day {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 3px 0;
          font-size: 12px;
        }
        .tsc-outlook-label { min-width: 36px; font-weight: 500; }
        .tsc-outlook-bar {
          flex: 1;
          height: 6px;
          background: var(--secondary-background-color, #eee);
          border-radius: 3px;
          overflow: hidden;
        }
        .tsc-outlook-fill {
          height: 100%;
          border-radius: 3px;
        }
        .tsc-outlook-val { min-width: 50px; text-align: right; opacity: 0.7; }

        /* Accuracy bars */
        .tsc-acc-row {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 2px 0;
          font-size: 12px;
        }
        .tsc-acc-date { min-width: 42px; opacity: 0.6; }
        .tsc-acc-bar {
          flex: 1;
          height: 5px;
          background: var(--secondary-background-color, #eee);
          border-radius: 2px;
          overflow: hidden;
        }
        .tsc-acc-fill { height: 100%; border-radius: 2px; }
        .tsc-acc-val { min-width: 30px; text-align: right; opacity: 0.7; }

        /* Collapsible debug */
        .tsc-toggle {
          cursor: pointer;
          user-select: none;
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .tsc-toggle-arrow {
          transition: transform 0.2s;
          font-size: 10px;
        }
        .tsc-toggle-arrow.open { transform: rotate(90deg); }
        .tsc-collapsible {
          max-height: 0;
          overflow: hidden;
          transition: max-height 0.3s ease;
        }
        .tsc-collapsible.open { max-height: 2000px; }

        /* Color utilities */
        .c-green  { color: #2e7d32; }
        .c-orange { color: #e65100; }
        .c-red    { color: #c62828; }
        .c-blue   { color: #1565c0; }

        /* Advisor table */
        .tsc-advisor-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 12px;
          margin-top: 4px;
        }
        .tsc-advisor-table th {
          text-align: left;
          padding: 4px 8px;
          font-size: 11px;
          font-weight: 600;
          opacity: 0.6;
          border-bottom: 1px solid var(--divider-color, #eee);
        }
        .tsc-advisor-table td {
          padding: 5px 8px;
          border-bottom: 1px solid var(--divider-color, #eee);
        }
        .tsc-advisor-table tr:last-child td { border-bottom: none; }

        @media (max-width: 700px) {
          .tsc-grid { grid-template-columns: 1fr; }
        }
      </style>
      <div class="tsc-wrap">
        <!-- Hero status banner -->
        <div class="tsc-hero idle" id="tsc-hero">
          <div class="tsc-hero-text">
            <div class="tsc-hero-state" id="hero-state">Loading...</div>
            <div class="tsc-hero-reason" id="hero-reason"></div>
          </div>
          <div class="tsc-hero-badges" id="hero-badges"></div>
        </div>

        <div class="tsc-grid">
          <!-- Live Power -->
          <div class="tsc-card" id="card-power">
            <h2>Power</h2>
            <div id="power-content"></div>
          </div>

          <!-- Tesla -->
          <div class="tsc-card" id="card-tesla">
            <h2>Tesla</h2>
            <div id="tesla-content"></div>
          </div>

          <!-- Today's Forecast -->
          <div class="tsc-card" id="card-forecast">
            <h2>Today's Solar</h2>
            <div id="forecast-content"></div>
          </div>

          <!-- Today's Charging -->
          <div class="tsc-card" id="card-today">
            <h2>Today's Charging</h2>
            <div id="today-content"></div>
          </div>

          <!-- Week Outlook -->
          <div class="tsc-card wide" id="card-outlook">
            <h2>Week Outlook</h2>
            <div id="outlook-content"></div>
          </div>

          <!-- Forecast Accuracy (collapsible) -->
          <div class="tsc-card wide" id="card-accuracy">
            <div class="tsc-toggle" id="acc-toggle">
              <span class="tsc-toggle-arrow" id="acc-arrow">&#9654;</span>
              <h2 style="margin:0">Forecast Accuracy</h2>
            </div>
            <div class="tsc-collapsible" id="acc-body">
              <div id="accuracy-content" style="padding-top:10px"></div>
            </div>
          </div>

          <!-- Advisor -->
          <div class="tsc-card wide" id="card-advisor" style="display:none">
            <div class="tsc-toggle" id="adv-toggle">
              <span class="tsc-toggle-arrow" id="adv-arrow">&#9654;</span>
              <h2 style="margin:0">Appliance Advisor</h2>
            </div>
            <div class="tsc-collapsible" id="adv-body">
              <div id="advisor-content" style="padding-top:10px"></div>
            </div>
          </div>

          <!-- Debug (collapsible) -->
          <div class="tsc-card wide">
            <div class="tsc-toggle" id="debug-toggle">
              <span class="tsc-toggle-arrow" id="debug-arrow">&#9654;</span>
              <h2 style="margin:0">Debug</h2>
              <button id="tsc-copy-btn" style="margin-left:auto;font-size:11px;padding:3px 10px;border-radius:6px;border:1px solid var(--divider-color,#ccc);background:var(--secondary-background-color,#f5f5f5);cursor:pointer">Copy JSON</button>
            </div>
            <div class="tsc-collapsible" id="debug-body">
              <pre id="debug-json" style="font-size:11px;max-height:300px;overflow:auto;background:var(--secondary-background-color,#f5f5f5);padding:8px;border-radius:6px;white-space:pre-wrap;word-break:break-all;margin-top:10px"></pre>
            </div>
          </div>
        </div>
      </div>
    `;

    // Toggle handlers
    const toggles = [
      ["acc-toggle", "acc-body", "acc-arrow"],
      ["adv-toggle", "adv-body", "adv-arrow"],
      ["debug-toggle", "debug-body", "debug-arrow"],
    ];
    for (const [togId, bodyId, arrowId] of toggles) {
      this.querySelector(`#${togId}`)?.addEventListener("click", () => {
        const body = this.querySelector(`#${bodyId}`);
        const arrow = this.querySelector(`#${arrowId}`);
        if (body && arrow) {
          body.classList.toggle("open");
          arrow.classList.toggle("open");
        }
      });
    }

    // Copy JSON
    this.querySelector("#tsc-copy-btn")?.addEventListener("click", (e) => {
      e.stopPropagation();
      const json = this.querySelector("#debug-json")?.textContent || "";
      navigator.clipboard.writeText(json).then(() => {
        const btn = this.querySelector("#tsc-copy-btn");
        if (btn) { btn.textContent = "Copied!"; setTimeout(() => btn.textContent = "Copy JSON", 2000); }
      });
    });
  }

  _metric(label, value, cls) {
    const extra = cls ? ` class="${cls}"` : "";
    return `<div class="tsc-metric"><span class="tsc-metric-label">${label}</span><span class="tsc-metric-value"${extra}>${value}</span></div>`;
  }

  _update() {
    if (!this._hass) return;

    const stateVal = this._val("sensor.state");
    const stateAttrs = this._states("sensor.state")?.attributes || {};
    const reason = this._val("sensor.reason");
    const forecastAttrs = this._states("sensor.solar_forecast")?.attributes || {};
    const accuracyAttrs = this._states("sensor.forecast_accuracy")?.attributes || {};
    const bleAttrs = this._states("sensor.ble_status")?.attributes || {};

    // ── Hero Banner ──
    const hero = this.querySelector("#tsc-hero");
    const heroState = this.querySelector("#hero-state");
    const heroReason = this.querySelector("#hero-reason");
    const heroBadges = this.querySelector("#hero-badges");

    if (hero) {
      const stateMap = {
        charging_solar: ["charging", "Charging (Solar)", "mdi:solar-power"],
        charging_night: ["night", "Charging (Night)", "mdi:weather-night"],
        waiting: ["waiting", "Waiting", "mdi:clock-outline"],
        stopped: ["idle", "Stopped", "mdi:stop-circle-outline"],
        idle: ["idle", "Idle", "mdi:sleep"],
        error: ["error", "Error", "mdi:alert-circle"],
        planned_solar: ["planned", "Solar Planned", "mdi:calendar-check"],
        planned_night: ["planned", "Night Planned", "mdi:calendar-check"],
      };
      const [cls, label] = stateMap[stateVal] || ["idle", stateVal || "Unknown"];
      hero.className = `tsc-hero ${cls}`;
      if (heroState) heroState.textContent = label;
      if (heroReason) heroReason.textContent = reason !== "N/A" ? reason : "";

      // Badges for active flags
      let badges = "";
      if (stateAttrs.force_charge) badges += `<span class="tsc-tag orange">Force Charge</span>`;
      if (stateAttrs.night_mode_active) badges += `<span class="tsc-tag blue">Night Mode</span>`;
      if (stateAttrs.night_charge_planned) badges += `<span class="tsc-tag purple">Night Planned</span>`;

      const bleState = this._val("sensor.ble_status");
      if (bleState !== "ok" && bleState !== "N/A") {
        badges += `<span class="tsc-tag red">BLE: ${bleState}</span>`;
      }
      if (!stateAttrs.enabled) badges += `<span class="tsc-tag grey">Disabled</span>`;
      if (heroBadges) heroBadges.innerHTML = badges;
    }

    // ── Power Card ──
    const powerEl = this.querySelector("#power-content");
    if (powerEl) {
      const gridW = stateAttrs.grid_power_w;
      const batSoc = stateAttrs.battery_soc;
      const batThresh = stateAttrs.battery_soc_threshold ?? 98;
      const batPower = stateAttrs.battery_power_w;
      const amps = this._val("sensor.charging_amps");
      const netA = this._val("sensor.net_available");

      const exporting = gridW != null && gridW < 0;
      const gridText = gridW != null
        ? (exporting ? `${Math.abs(gridW).toFixed(0)}W` : `${Math.round(gridW)}W`)
        : "N/A";
      const gridLabel = exporting ? "Exporting" : "Importing";
      const gridColor = exporting ? "c-green" : "c-red";

      const batColor = batSoc >= batThresh ? "#4caf50" : batSoc >= 80 ? "#ff9800" : "#f44336";
      const batBlocking = batSoc < batThresh;

      let html = this._metric(gridLabel, `<span class="${gridColor}">${gridText}</span>`);
      html += this._metric("Home Battery", `${batSoc ?? "N/A"}%`);
      html += `<div class="tsc-progress"><div class="tsc-progress-bar" style="width:${batSoc || 0}%;background:${batColor}"></div></div>`;
      if (batBlocking && batSoc != null) {
        html += `<div style="font-size:11px;color:#e65100;padding:2px 0">Filling to ${batThresh}% before car charges</div>`;
      }
      if (batPower != null) {
        const batDir = batPower > 0 ? "discharging" : batPower < 0 ? "charging" : "idle";
        html += this._metric("Battery", `${Math.abs(batPower).toFixed(0)}W ${batDir}`);
      }
      html += this._metric("Charging", `<span class="${parseFloat(amps) > 0 ? "c-green" : ""}" style="font-size:18px;font-weight:700">${amps}A</span>`);
      html += this._metric("Available", `${netA}A`);

      // Add card highlight if battery is blocking
      const card = this.querySelector("#card-power");
      if (card) card.className = `tsc-card${batBlocking ? " highlight" : ""}`;

      powerEl.innerHTML = html;
    }

    // ── Tesla Card ──
    const teslaEl = this.querySelector("#tesla-content");
    if (teslaEl) {
      const limit = parseFloat(this._val("number.tesla_charge_limit")) || 0;
      let teslaSoc = null;
      for (const [id, s] of Object.entries(this._hass.states)) {
        if (id.includes("tesla") && id.includes("battery") && id.startsWith("sensor.") && !id.includes("power")) {
          teslaSoc = parseFloat(s.state);
          break;
        }
      }

      const pct = teslaSoc ?? 0;
      const atLimit = teslaSoc != null && limit > 0 && teslaSoc >= limit;
      const barColor = atLimit ? "#4caf50" : "#2196f3";
      const kwhNeeded = limit > 0 && teslaSoc != null
        ? ((limit - teslaSoc) / 100 * (stateAttrs.tesla_battery_kwh ?? 75)).toFixed(1)
        : null;

      let html = `<div style="display:flex;align-items:baseline;gap:8px">`;
      html += `<span class="tsc-big">${teslaSoc != null ? teslaSoc : "?"}<span class="tsc-big-unit">%</span></span>`;
      html += `<span style="font-size:13px;opacity:0.5">/ ${limit || "?"}%</span>`;
      html += `</div>`;
      html += `<div class="tsc-progress"><div class="tsc-progress-bar" style="width:${pct}%;background:${barColor}"></div></div>`;

      if (atLimit) {
        html += `<div style="font-size:12px" class="c-green">At charge limit</div>`;
      } else if (kwhNeeded != null && parseFloat(kwhNeeded) > 0) {
        html += `<div class="tsc-big-sub">Needs ${kwhNeeded} kWh to reach ${limit}%</div>`;

        // Charge time estimates
        const kwhNeed = parseFloat(kwhNeeded);
        const currentAmps = parseFloat(this._val("sensor.charging_amps")) || 0;
        const gridV = stateAttrs.grid_voltage_v || 230;
        const maxAmps = stateAttrs.max_charging_amps ?? 28;
        const efficiency = 0.9; // AC charging efficiency

        // If actively charging, show ETA at current rate
        const teslaEta = stateAttrs.tesla_eta_min;
        if (teslaEta != null) {
          const hrs = (teslaEta / 60).toFixed(1);
          html += this._metric("ETA (current)", `<b>${hrs}h</b>`);
        } else if (currentAmps > 0) {
          const powerKw = (currentAmps * gridV * efficiency) / 1000;
          const hrs = (kwhNeed / powerKw).toFixed(1);
          html += this._metric("ETA (current)", `<b>${hrs}h</b> at ${currentAmps}A`);
        }

        // Always show ETA at max amps
        const maxPowerKw = (maxAmps * gridV * efficiency) / 1000;
        const maxHrs = (kwhNeed / maxPowerKw).toFixed(1);
        html += this._metric(`ETA (${maxAmps}A max)`, `${maxHrs}h`);

        // Show ETA at min amps (5A) for worst case
        const minPowerKw = (5 * gridV * efficiency) / 1000;
        const minHrs = (kwhNeed / minPowerKw).toFixed(1);
        html += this._metric("ETA (5A min)", `${minHrs}h`);

        // Today's excess estimate
        const outlook = stateAttrs.multi_day_outlook ?? forecastAttrs.multi_day_outlook;
        const todayExcess = outlook?.daily_forecasts?.[0]?.excess_kwh;
        if (todayExcess != null && todayExcess > 0) {
          const pctFromExcess = Math.min((todayExcess * efficiency / (stateAttrs.tesla_battery_kwh ?? 75)) * 100, kwhNeed / (stateAttrs.tesla_battery_kwh ?? 75) * 100).toFixed(0);
          const socAfter = teslaSoc != null ? Math.min(limit, teslaSoc + parseFloat(pctFromExcess)).toFixed(0) : "?";
          html += this._metric("Today's excess", `~${todayExcess.toFixed(0)} kWh → ${socAfter}%`);
        }
      }

      const chargePower = stateAttrs.tesla_charge_power_w;
      if (chargePower != null && chargePower > 0) {
        html += this._metric("Power", `<span class="c-green">${chargePower}W</span>`);
      }

      // Location
      let location = null;
      for (const [id, s] of Object.entries(this._hass.states)) {
        if (id.includes("tesla") && id.startsWith("device_tracker.")) {
          location = s.state;
          break;
        }
      }
      if (location && location !== "home" && location !== "Piano di sotto") {
        html += this._metric("Location", `<span class="c-orange">${location}</span>`);
      }

      teslaEl.innerHTML = html;
    }

    // ── Today's Forecast ──
    const forecastEl = this.querySelector("#forecast-content");
    if (forecastEl) {
      const blended = forecastAttrs.blended_kwh ?? this._val("sensor.solar_forecast");
      const pessimistic = forecastAttrs.pessimistic_kwh;
      const sources = forecastAttrs.sources || [];
      const cloudStrategy = this._val("sensor.cloud_strategy");
      const cloudAttrs = this._states("sensor.cloud_strategy")?.attributes || {};
      const bestWindow = cloudAttrs.best_charging_window;

      let html = `<div class="tsc-big">${blended}<span class="tsc-big-unit"> kWh</span></div>`;
      if (pessimistic) {
        html += `<div class="tsc-big-sub">Pessimistic: ${pessimistic} kWh</div>`;
      }

      if (cloudStrategy && cloudStrategy !== "N/A") {
        const strategyTag = cloudStrategy.includes("clear") ? "green"
          : cloudStrategy.includes("partly") ? "orange"
          : cloudStrategy.includes("overcast") || cloudStrategy.includes("rain") ? "red"
          : "grey";
        html += `<div style="margin-top:8px">`;
        html += `<span class="tsc-tag ${strategyTag}">${cloudStrategy}</span>`;
        if (bestWindow) html += ` <span style="font-size:12px;opacity:0.6">Best: ${bestWindow}</span>`;
        html += `</div>`;
      }

      if (sources.length > 0) {
        html += `<div style="margin-top:10px;font-size:12px;opacity:0.5">`;
        html += sources.map(s => `${s.name}: ${s.production_kwh}`).join(" &middot; ");
        html += `</div>`;
      }

      forecastEl.innerHTML = html;
    }

    // ── Today's Charging ──
    const todayEl = this.querySelector("#today-content");
    if (todayEl) {
      const solarKwh = parseFloat(stateAttrs.daily_solar_kwh ?? 0);
      const gridKwh = parseFloat(stateAttrs.daily_grid_kwh ?? 0);
      const totalKwh = (solarKwh + gridKwh).toFixed(1);
      const peakAmps = stateAttrs.daily_peak_amps ?? 0;
      const chargeMin = stateAttrs.daily_charge_minutes ?? 0;

      let html = `<div class="tsc-big">${totalKwh}<span class="tsc-big-unit"> kWh</span></div>`;
      html += `<div class="tsc-big-sub">charged today</div>`;

      if (solarKwh > 0 || gridKwh > 0) {
        html += `<div style="margin-top:8px">`;
        if (solarKwh > 0) html += `<span class="tsc-tag green">Solar: ${solarKwh.toFixed(1)}</span> `;
        if (gridKwh > 0) html += `<span class="tsc-tag blue">Grid: ${gridKwh.toFixed(1)}</span>`;
        html += `</div>`;
      }

      if (peakAmps > 0) html += this._metric("Peak", `${peakAmps}A`);
      if (chargeMin > 0) {
        const hrs = (chargeMin / 60).toFixed(1);
        html += this._metric("Time", chargeMin >= 60 ? `${hrs}h` : `${Math.round(chargeMin)}min`);
      }

      const planState = this._states("sensor.plan");
      if (planState && planState.state && planState.state !== "N/A" && planState.state !== "unknown") {
        html += `<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--divider-color,#eee)">`;
        html += this._metric("Plan", planState.state);
        html += `</div>`;
      }

      todayEl.innerHTML = html;
    }

    // ── Week Outlook ──
    const outlookEl = this.querySelector("#outlook-content");
    if (outlookEl) {
      const outlook = stateAttrs.multi_day_outlook ?? forecastAttrs.multi_day_outlook;
      const dailyForecasts = outlook?.daily_forecasts || [];
      const kwhNeeded = outlook?.kwh_needed;
      const totalExcess = outlook?.total_excess_kwh;

      if (dailyForecasts.length === 0) {
        outlookEl.innerHTML = `<div style="opacity:0.5;font-size:13px">No forecast data yet</div>`;
      } else {
        const maxProd = Math.max(...dailyForecasts.map(d => d.production_kwh || 0), 1);
        const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

        const maxExcess = Math.max(...dailyForecasts.map(d => d.excess_kwh || 0), 1);

        let html = "";
        for (const day of dailyForecasts) {
          const d = new Date(day.date + "T00:00:00");
          const label = dayNames[d.getDay()];
          const excess = day.excess_kwh || 0;
          const pct = (excess / maxExcess) * 100;
          const barColor = excess <= 0 ? "#ef5350" : excess < 10 ? "#ff9800" : "#4caf50";

          html += `<div class="tsc-outlook-day">
            <span class="tsc-outlook-label">${label}</span>
            <div class="tsc-outlook-bar">
              <div class="tsc-outlook-fill" style="width:${pct}%;background:${barColor}"></div>
            </div>
            <span class="tsc-outlook-val" style="color:${barColor}">${excess > 0 ? `+${excess.toFixed(0)}` : "0"} kWh</span>
          </div>`;
        }

        if (kwhNeeded != null && totalExcess != null) {
          const enough = totalExcess >= kwhNeeded;
          html += `<div style="margin-top:8px;font-size:12px">`;
          html += `Need <b>${kwhNeeded}</b> kWh &middot; Week excess <b class="${enough ? "c-green" : "c-red"}">${totalExcess}</b> kWh`;
          html += enough
            ? ` <span class="tsc-tag green" style="margin-left:4px">Enough</span>`
            : ` <span class="tsc-tag red" style="margin-left:4px">Short</span>`;
          html += `</div>`;
        }

        outlookEl.innerHTML = html;
      }
    }

    // ── Forecast Accuracy ──
    const accEl = this.querySelector("#accuracy-content");
    if (accEl) {
      const factor = this._val("sensor.forecast_accuracy");
      const days = accuracyAttrs.days_tracked ?? 0;
      const last7 = accuracyAttrs.last_7_days || [];

      let html = this._metric("Correction Factor", `<b>${factor}</b>`);
      html += this._metric("Days Tracked", days);

      if (last7.length > 0) {
        const maxKwh = Math.max(...last7.map(d => Math.max(d.forecast || 0, d.actual || 0)), 1);
        html += `<div style="margin-top:8px">`;
        for (const day of last7) {
          const fPct = ((day.forecast || 0) / maxKwh) * 100;
          const aPct = ((day.actual || 0) / maxKwh) * 100;
          html += `<div class="tsc-acc-row">
            <span class="tsc-acc-date">${day.date?.slice(5) || "?"}</span>
            <div class="tsc-acc-bar"><div class="tsc-acc-fill" style="width:${fPct}%;background:#90caf9"></div></div>
            <span class="tsc-acc-val">${day.forecast}</span>
            <div class="tsc-acc-bar"><div class="tsc-acc-fill" style="width:${aPct}%;background:#a5d6a7"></div></div>
            <span class="tsc-acc-val">${day.actual}</span>
          </div>`;
        }
        html += `<div style="display:flex;gap:16px;font-size:11px;opacity:0.5;margin-top:4px">
          <span><span style="display:inline-block;width:8px;height:8px;background:#90caf9;border-radius:2px"></span> Forecast</span>
          <span><span style="display:inline-block;width:8px;height:8px;background:#a5d6a7;border-radius:2px"></span> Actual</span>
        </div>`;
        html += `</div>`;
      }

      accEl.innerHTML = html;
    }

    // ── Advisor ──
    const advisorState = this._states("sensor.tesla_solar_charging_appliance_advisor_summary");
    const advisorCard = this.querySelector("#card-advisor");
    const advisorEl = this.querySelector("#advisor-content");
    if (advisorCard && advisorEl) {
      const appliances = advisorState?.attributes?.appliances || [];
      if (appliances.length > 0) {
        advisorCard.style.display = "";
        const statusColor = { free: "green", paid: "orange", skipped: "grey", running: "blue", error: "red" };
        let html = `<div style="font-size:13px;margin-bottom:8px">${advisorState?.state || ""}</div>`;
        html += `<table class="tsc-advisor-table"><thead><tr>
          <th>Name</th><th>Status</th><th>Reason</th>
        </tr></thead><tbody>`;
        for (const a of appliances) {
          const cls = statusColor[a.status] || "grey";
          html += `<tr>
            <td><b>${a.name ?? "?"}</b></td>
            <td><span class="tsc-tag ${cls}">${a.status ?? "?"}</span></td>
            <td style="font-size:11px;opacity:0.8">${a.reason ?? ""}</td>
          </tr>`;
        }
        html += `</tbody></table>`;
        advisorEl.innerHTML = html;
      } else {
        advisorCard.style.display = "none";
      }
    }

    // ── Debug ──
    const debugEl = this.querySelector("#debug-json");
    if (debugEl) {
      const debugState = this._states("sensor.debug");
      debugEl.textContent = debugState?.attributes?.json || "{}";
    }

    // ── Low solar warning ──
    const lowWarn = stateAttrs.low_solar_warning;
    const forecastCard = this.querySelector("#card-forecast");
    if (forecastCard) {
      forecastCard.className = `tsc-card${lowWarn ? " alert" : ""}`;
    }
  }

}

if (!customElements.get("tesla-solar-charging-panel")) {
  customElements.define("tesla-solar-charging-panel", TeslaSolarChargingPanel);
}
