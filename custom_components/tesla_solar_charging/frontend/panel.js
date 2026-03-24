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

  _getState(suffix) {
    // Try common entity ID patterns
    const candidates = [
      `sensor.${suffix}`,
      `switch.${suffix}`,
      `number.${suffix}`,
      `device_tracker.${suffix}`,
    ];
    for (const id of candidates) {
      const s = this._hass.states[id];
      if (s) return s;
    }
    return null;
  }

  _val(entityId) {
    const s = this._hass.states[entityId];
    return s ? s.state : "N/A";
  }

  _attr(entityId, attr) {
    const s = this._hass.states[entityId];
    if (!s || !s.attributes) return null;
    return s.attributes[attr];
  }

  _numAttr(entityId, attr) {
    const v = this._attr(entityId, attr);
    if (v == null) return "N/A";
    if (typeof v === "number") return v;
    return v;
  }

  _render() {
    this.innerHTML = `
      <style>
        :host { display: block; }
        .tsc-wrap {
          max-width: 1100px;
          margin: 0 auto;
          padding: 16px;
          font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
          color: var(--primary-text-color, #333);
        }
        .tsc-header {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 24px;
        }
        .tsc-header h1 {
          margin: 0;
          font-size: 24px;
          font-weight: 500;
        }
        .tsc-header .version {
          font-size: 12px;
          opacity: 0.6;
          background: var(--secondary-background-color, #f5f5f5);
          padding: 2px 8px;
          border-radius: 8px;
        }
        .tsc-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
          gap: 16px;
        }
        .tsc-card {
          background: var(--card-background-color, #fff);
          border-radius: 12px;
          padding: 16px;
          box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0,0,0,.1));
        }
        .tsc-card h2 {
          margin: 0 0 12px 0;
          font-size: 14px;
          font-weight: 500;
          text-transform: uppercase;
          opacity: 0.6;
          letter-spacing: 0.5px;
        }
        .tsc-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 6px 0;
          border-bottom: 1px solid var(--divider-color, #eee);
        }
        .tsc-row:last-child { border-bottom: none; }
        .tsc-label {
          font-size: 13px;
          opacity: 0.8;
        }
        .tsc-value {
          font-size: 14px;
          font-weight: 500;
          text-align: right;
        }
        .tsc-badge {
          display: inline-block;
          padding: 2px 10px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 600;
        }
        .tsc-badge.green { background: #c8e6c9; color: #2e7d32; }
        .tsc-badge.orange { background: #ffe0b2; color: #e65100; }
        .tsc-badge.red { background: #ffcdd2; color: #c62828; }
        .tsc-badge.blue { background: #bbdefb; color: #1565c0; }
        .tsc-badge.grey { background: var(--secondary-background-color, #eee); color: var(--primary-text-color, #666); }
        .tsc-progress {
          width: 100%;
          height: 6px;
          background: var(--secondary-background-color, #eee);
          border-radius: 3px;
          margin: 4px 0;
          overflow: hidden;
        }
        .tsc-progress-bar {
          height: 100%;
          border-radius: 3px;
          transition: width 0.5s ease;
        }
        .tsc-source-row {
          display: flex;
          gap: 8px;
          align-items: center;
          padding: 4px 0;
          font-size: 13px;
        }
        .tsc-source-name {
          min-width: 100px;
          font-weight: 500;
        }
        .tsc-source-val { opacity: 0.8; }
        .tsc-accuracy-row {
          display: flex;
          gap: 4px;
          align-items: center;
          padding: 2px 0;
          font-size: 12px;
        }
        .tsc-bar-wrap {
          flex: 1;
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .tsc-bar {
          flex: 1;
          height: 4px;
          background: var(--secondary-background-color, #eee);
          border-radius: 2px;
          overflow: hidden;
        }
        .tsc-bar-fill {
          height: 100%;
          border-radius: 2px;
        }
        .tsc-wide { grid-column: 1 / -1; }
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
          white-space: nowrap;
        }
        .tsc-advisor-table td {
          padding: 5px 8px;
          border-bottom: 1px solid var(--divider-color, #eee);
          vertical-align: middle;
        }
        .tsc-advisor-table tr:last-child td { border-bottom: none; }
        .tsc-advisor-summary {
          margin-top: 10px;
          font-size: 13px;
          font-weight: 500;
          opacity: 0.85;
        }
        @media (max-width: 700px) {
          .tsc-grid { grid-template-columns: 1fr; }
          .tsc-advisor-table { font-size: 11px; }
          .tsc-advisor-table th, .tsc-advisor-table td { padding: 4px 4px; }
        }
      </style>
      <div class="tsc-wrap">
        <div class="tsc-header">
          <ha-icon icon="mdi:solar-power" style="--mdc-icon-size:28px;color:var(--primary-color)"></ha-icon>
          <h1>Tesla Solar Charging</h1>
          <span class="version" id="tsc-version"></span>
        </div>
        <div class="tsc-grid">
          <!-- Status Card -->
          <div class="tsc-card" id="card-status">
            <h2>System Status</h2>
            <div id="status-rows"></div>
          </div>

          <!-- Power Card -->
          <div class="tsc-card" id="card-power">
            <h2>Power & Charging</h2>
            <div id="power-rows"></div>
          </div>

          <!-- Tesla Card -->
          <div class="tsc-card" id="card-tesla">
            <h2>Tesla</h2>
            <div id="tesla-rows"></div>
          </div>

          <!-- BLE Card -->
          <div class="tsc-card" id="card-ble">
            <h2>BLE / ESP32</h2>
            <div id="ble-rows"></div>
          </div>

          <!-- Forecast Card -->
          <div class="tsc-card" id="card-forecast">
            <h2>Solar Forecast</h2>
            <div id="forecast-rows"></div>
          </div>

          <!-- Forecast Accuracy Card -->
          <div class="tsc-card" id="card-accuracy">
            <h2>Forecast Accuracy</h2>
            <div id="accuracy-rows"></div>
          </div>

          <!-- Config Card -->
          <div class="tsc-card" id="card-config">
            <h2>Configuration</h2>
            <div id="config-rows"></div>
          </div>

          <!-- Daily Stats Card -->
          <div class="tsc-card" id="card-daily">
            <h2>Daily Stats</h2>
            <div id="daily-rows"></div>
          </div>

          <!-- Advisor Debug Card -->
          <div class="tsc-card tsc-wide" id="card-advisor">
            <h2>Advisor Debug <button id="tsc-advisor-copy-btn" style="float:right;font-size:12px;padding:4px 12px;border-radius:6px;border:1px solid var(--divider-color,#ccc);background:var(--secondary-background-color,#f5f5f5);cursor:pointer">Copy JSON</button></h2>
            <div id="advisor-summary" class="tsc-advisor-summary"></div>
            <div id="advisor-table-wrap" style="overflow-x:auto;margin-top:8px">
              <table class="tsc-advisor-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Status</th>
                    <th>Cost</th>
                    <th>Reason</th>
                    <th>Running</th>
                    <th>Watts</th>
                    <th>Deadline</th>
                    <th>Latest Start</th>
                  </tr>
                </thead>
                <tbody id="advisor-tbody"></tbody>
              </table>
            </div>
          </div>

          <!-- Debug Card -->
          <div class="tsc-card tsc-wide" id="card-debug">
            <h2>Debug JSON <button id="tsc-copy-btn" style="float:right;font-size:12px;padding:4px 12px;border-radius:6px;border:1px solid var(--divider-color,#ccc);background:var(--secondary-background-color,#f5f5f5);cursor:pointer">Copy</button></h2>
            <pre id="debug-json" style="font-size:11px;max-height:300px;overflow:auto;background:var(--secondary-background-color,#f5f5f5);padding:8px;border-radius:6px;white-space:pre-wrap;word-break:break-all"></pre>
          </div>
        </div>
      </div>
    `;
    // Copy button handler (main debug)
    this.querySelector("#tsc-copy-btn")?.addEventListener("click", () => {
      const json = this.querySelector("#debug-json")?.textContent || "";
      navigator.clipboard.writeText(json).then(() => {
        const btn = this.querySelector("#tsc-copy-btn");
        if (btn) { btn.textContent = "Copied!"; setTimeout(() => btn.textContent = "Copy", 2000); }
      });
    });
    // Copy button handler (advisor debug)
    this.querySelector("#tsc-advisor-copy-btn")?.addEventListener("click", () => {
      const s = this._hass?.states["sensor.tesla_solar_charging_appliance_advisor_summary"];
      const payload = s ? JSON.stringify({ state: s.state, attributes: s.attributes }, null, 2) : "{}";
      navigator.clipboard.writeText(payload).then(() => {
        const btn = this.querySelector("#tsc-advisor-copy-btn");
        if (btn) { btn.textContent = "Copied!"; setTimeout(() => btn.textContent = "Copy JSON", 2000); }
      });
    });
  }

  _stateBadge(state) {
    const map = {
      charging_solar: ["green", "Charging (Solar)"],
      charging_night: ["blue", "Charging (Night)"],
      waiting: ["orange", "Waiting"],
      stopped: ["grey", "Stopped"],
      idle: ["grey", "Idle"],
      error: ["red", "Error"],
      planned_solar: ["green", "Planned Solar"],
      planned_night: ["blue", "Planned Night"],
    };
    const [cls, label] = map[state] || ["grey", state || "Unknown"];
    return `<span class="tsc-badge ${cls}">${label}</span>`;
  }

  _row(label, value) {
    return `<div class="tsc-row"><span class="tsc-label">${label}</span><span class="tsc-value">${value}</span></div>`;
  }

  _progressBar(pct, color) {
    const p = Math.max(0, Math.min(100, pct || 0));
    return `<div class="tsc-progress"><div class="tsc-progress-bar" style="width:${p}%;background:${color}"></div></div>`;
  }

  _update() {
    if (!this._hass) return;

    const state = this._val("sensor.state");
    const stateAttrs = this._hass.states["sensor.state"]?.attributes || {};
    const reason = this._val("sensor.reason");
    const forecastAttrs = this._hass.states["sensor.solar_forecast"]?.attributes || {};
    const bleAttrs = this._hass.states["sensor.ble_status"]?.attributes || {};
    const accuracyAttrs = this._hass.states["sensor.forecast_accuracy"]?.attributes || {};
    const cloudAttrs = this._hass.states["sensor.cloud_strategy"]?.attributes || {};
    const netAttrs = this._hass.states["sensor.net_available"]?.attributes || {};

    // Version
    const ver = this.querySelector("#tsc-version");
    if (ver) ver.textContent = `v${stateAttrs.version || ""}`;

    // Status
    const statusEl = this.querySelector("#status-rows");
    if (statusEl) {
      const enabled = stateAttrs.enabled;
      const force = stateAttrs.force_charge;
      const night = stateAttrs.night_mode_active;
      statusEl.innerHTML = [
        this._row("State", this._stateBadge(state)),
        this._row("Reason", `<span style="font-size:12px">${reason}</span>`),
        this._row("Enabled", enabled ? '<span class="tsc-badge green">ON</span>' : '<span class="tsc-badge grey">OFF</span>'),
        this._row("Force Charge", force ? '<span class="tsc-badge orange">ON</span>' : '<span class="tsc-badge grey">OFF</span>'),
        this._row("Night Mode", night ? '<span class="tsc-badge blue">Active</span>' : '<span class="tsc-badge grey">Inactive</span>'),
        this._row("Night Planned", stateAttrs.night_charge_planned ? '<span class="tsc-badge blue">Yes</span>' : '<span class="tsc-badge grey">No</span>'),
        this._row("Cloud Strategy", this._val("sensor.cloud_strategy") + (cloudAttrs.best_charging_window ? ` (${cloudAttrs.best_charging_window})` : "")),
      ].join("");
    }

    // Power
    const powerEl = this.querySelector("#power-rows");
    if (powerEl) {
      const gridW = stateAttrs.grid_power_w;
      const gridV = stateAttrs.grid_voltage_v;
      const batSoc = stateAttrs.battery_soc;
      const batThresh = stateAttrs.battery_soc_threshold;
      const batPower = stateAttrs.battery_power_w;
      const amps = this._val("sensor.charging_amps");
      const netA = this._val("sensor.net_available");

      const exporting = gridW != null && gridW < 0;
      const gridLabel = exporting ? `${Math.abs(gridW)}W exporting` : `${gridW}W importing`;
      const gridColor = exporting ? "#4caf50" : "#f44336";

      powerEl.innerHTML = [
        this._row("Grid Power", `<span style="color:${gridColor};font-weight:600">${gridLabel}</span>`),
        this._row("Grid Voltage", `${gridV ?? "N/A"}V`),
        this._row("Home Battery", `${batSoc ?? "N/A"}% / ${batThresh ?? 98}% threshold`),
        this._progressBar(batSoc, batSoc >= batThresh ? "#4caf50" : "#ff9800"),
        batSoc != null && batThresh != null && batSoc < batThresh
          ? this._row("", `<span style="font-size:11px;color:#e65100">Waiting for battery to reach ${batThresh}% (currently ${batSoc}%)</span>`)
          : "",
        this._row("Battery Power", `${batPower ?? "N/A"}W ${batPower > 0 ? "(discharging)" : batPower < 0 ? "(charging)" : ""}`),
        stateAttrs.home_battery_eta_min != null
          ? this._row("Home Battery Full In", `~${stateAttrs.home_battery_eta_min} min`)
          : "",
        this._row("Charging Amps", `<b>${amps}A</b>`),
        this._row("Net Available", `${netA}A`),
        netAttrs.grid_export_amps != null
          ? this._row("", `<span style="font-size:11px;opacity:0.7">export ${netAttrs.grid_export_amps}A - buffer ${netAttrs.safety_buffer_amps}A - bat discharge ${netAttrs.battery_discharge_amps}A</span>`)
          : "",
      ].join("");
    }

    // Tesla
    const teslaEl = this.querySelector("#tesla-rows");
    if (teslaEl) {
      const limit = this._val("number.tesla_charge_limit");
      // Try to find tesla battery sensor
      let teslaSoc = "N/A";
      for (const [id, s] of Object.entries(this._hass.states)) {
        if (id.includes("tesla") && id.includes("battery") && id.startsWith("sensor.") && !id.includes("power")) {
          teslaSoc = s.state;
          break;
        }
      }
      // Try to find location tracker
      let location = "N/A";
      for (const [id, s] of Object.entries(this._hass.states)) {
        if (id.includes("tesla") && id.startsWith("device_tracker.")) {
          location = s.state;
          break;
        }
      }

      const teslaEta = stateAttrs.tesla_eta_min;
      teslaEl.innerHTML = [
        this._row("Battery SOC", `${teslaSoc}%`),
        this._row("Charge Limit", `${limit}%`),
        teslaSoc !== "N/A" && limit !== "N/A"
          ? this._progressBar(parseFloat(teslaSoc), parseFloat(teslaSoc) >= parseFloat(limit) ? "#4caf50" : "#2196f3")
          : "",
        teslaEta != null
          ? this._row("Charged In", `~${teslaEta} min (${Math.round(teslaEta/60*10)/10}h)`)
          : "",
        this._row("Charge Power", `${stateAttrs.tesla_charge_power_w ?? 0}W`),
        this._row("Location", location),
      ].join("");
    }

    // BLE
    const bleEl = this.querySelector("#ble-rows");
    if (bleEl) {
      const bleState = this._val("sensor.ble_status");
      const bleColor = bleState === "ok" ? "green" : bleState === "esp32_offline" ? "red" : "orange";
      bleEl.innerHTML = [
        this._row("Status", `<span class="tsc-badge ${bleColor}">${bleState}</span>`),
        this._row("Detail", bleAttrs.detail || "None"),
        this._row("Failures", bleAttrs.consecutive_failures ?? 0),
        this._row("Charger Switch", `<code style="font-size:11px">${bleAttrs.charger_switch || "N/A"}</code>`),
        this._row("Amps Entity", `<code style="font-size:11px">${bleAttrs.charging_amps || "N/A"}</code>`),
        this._row("Wake Button", `<code style="font-size:11px">${bleAttrs.wake_button || "N/A"}</code>`),
      ].join("");
    }

    // Forecast
    const forecastEl = this.querySelector("#forecast-rows");
    if (forecastEl) {
      const blended = forecastAttrs.blended_kwh ?? this._val("sensor.solar_forecast");
      const pessimistic = forecastAttrs.pessimistic_kwh;
      const sources = forecastAttrs.sources || [];
      const corrFactor = forecastAttrs.correction_factor;
      const seasonalFactor = forecastAttrs.seasonal_correction_factor;

      let html = [
        this._row("Blended Forecast", `<b>${blended} kWh</b>`),
        this._row("Pessimistic", `${pessimistic ?? "N/A"} kWh`),
        this._row("Correction Factor", corrFactor ?? "N/A"),
        this._row("Seasonal Factor", seasonalFactor ?? "N/A"),
      ].join("");

      if (sources.length > 0) {
        html += `<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--divider-color,#eee)">`;
        html += `<div style="font-size:12px;opacity:0.6;margin-bottom:4px">SOURCES</div>`;
        for (const src of sources) {
          const pess = src.pessimistic_kwh ? ` (P10: ${src.pessimistic_kwh})` : "";
          html += `<div class="tsc-source-row">
            <span class="tsc-source-name">${src.name}</span>
            <span class="tsc-source-val">${src.production_kwh} kWh${pess}</span>
            <span style="font-size:11px;opacity:0.5">w:${src.weight}</span>
          </div>`;
        }
        html += `</div>`;
      } else {
        html += this._row("Sources", '<span style="opacity:0.5">No forecast data yet (updates after HA start)</span>');
      }

      // PVGIS baselines
      const pvgis = forecastAttrs.pvgis_monthly_baselines;
      if (pvgis) {
        html += `<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--divider-color,#eee)">`;
        html += `<div style="font-size:12px;opacity:0.6;margin-bottom:4px">PVGIS MONTHLY BASELINES (kWh/m\u00b2)</div>`;
        const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
        const maxVal = Math.max(...Object.values(pvgis));
        for (const [m, val] of Object.entries(pvgis)) {
          const pct = (val / maxVal) * 100;
          html += `<div style="display:flex;align-items:center;gap:6px;font-size:12px;padding:1px 0">
            <span style="min-width:28px">${months[parseInt(m)-1]}</span>
            <div style="flex:1;height:4px;background:var(--secondary-background-color,#eee);border-radius:2px;overflow:hidden"><div style="height:100%;width:${pct}%;background:#ffb74d;border-radius:2px"></div></div>
            <span style="min-width:40px;text-align:right">${Math.round(val)}</span>
          </div>`;
        }
        html += `</div>`;
      }

      forecastEl.innerHTML = html;
    }

    // Accuracy
    const accEl = this.querySelector("#accuracy-rows");
    if (accEl) {
      const factor = this._val("sensor.forecast_accuracy");
      const days = accuracyAttrs.days_tracked ?? 0;
      const avgF = accuracyAttrs.avg_forecast_kwh ?? 0;
      const avgA = accuracyAttrs.avg_actual_kwh ?? 0;
      const last7 = accuracyAttrs.last_7_days || [];

      let html = [
        this._row("Correction Factor", `<b>${factor}</b>`),
        this._row("Days Tracked", days),
        this._row("Avg Forecast", `${avgF} kWh`),
        this._row("Avg Actual", `${avgA} kWh`),
      ].join("");

      if (last7.length > 0) {
        html += `<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--divider-color,#eee)">`;
        html += `<div style="font-size:12px;opacity:0.6;margin-bottom:4px">LAST 7 DAYS</div>`;
        const maxKwh = Math.max(...last7.map(d => Math.max(d.forecast || 0, d.actual || 0)), 1);
        for (const day of last7) {
          const fPct = ((day.forecast || 0) / maxKwh) * 100;
          const aPct = ((day.actual || 0) / maxKwh) * 100;
          html += `<div class="tsc-accuracy-row">
            <span style="min-width:70px">${day.date?.slice(5) || "?"}</span>
            <div class="tsc-bar-wrap">
              <div class="tsc-bar"><div class="tsc-bar-fill" style="width:${fPct}%;background:#90caf9"></div></div>
              <span style="min-width:35px;text-align:right">${day.forecast}</span>
            </div>
            <div class="tsc-bar-wrap">
              <div class="tsc-bar"><div class="tsc-bar-fill" style="width:${aPct}%;background:#a5d6a7"></div></div>
              <span style="min-width:35px;text-align:right">${day.actual}</span>
            </div>
          </div>`;
        }
        html += `<div style="display:flex;gap:16px;font-size:11px;opacity:0.5;margin-top:4px">
          <span><span style="display:inline-block;width:10px;height:10px;background:#90caf9;border-radius:2px"></span> Forecast</span>
          <span><span style="display:inline-block;width:10px;height:10px;background:#a5d6a7;border-radius:2px"></span> Actual</span>
        </div>`;
        html += `</div>`;
      }

      accEl.innerHTML = html;
    }

    // Config
    const cfgEl = this.querySelector("#config-rows");
    if (cfgEl) {
      cfgEl.innerHTML = [
        this._row("Min Export Power", `${stateAttrs.min_export_power_w ?? "N/A"}W`),
        this._row("Max Charging Amps", `${stateAttrs.max_charging_amps ?? "N/A"}A`),
        this._row("Safety Buffer", `${stateAttrs.safety_buffer_amps ?? "N/A"}A`),
        this._row("Battery SOC Threshold", `${stateAttrs.battery_soc_threshold ?? "N/A"}%`),
        this._row("Battery Discharge Threshold", `${stateAttrs.battery_discharge_threshold_w ?? "N/A"}W`),
        this._row("Low Amp Stop Count", stateAttrs.low_amp_stop_count ?? "N/A"),
        this._row("Grid Power Limit", `${stateAttrs.grid_power_limit_w ?? "N/A"}W`),
      ].join("");
    }

    // Daily
    const dailyEl = this.querySelector("#daily-rows");
    if (dailyEl) {
      const solarKwh = stateAttrs.daily_solar_kwh ?? 0;
      const gridKwh = stateAttrs.daily_grid_kwh ?? 0;
      const totalKwh = (parseFloat(solarKwh) + parseFloat(gridKwh)).toFixed(1);
      dailyEl.innerHTML = [
        this._row("Solar Charged", `${solarKwh} kWh`),
        this._row("Grid Charged", `${gridKwh} kWh`),
        this._row("Total Charged", `<b>${totalKwh} kWh</b>`),
        this._row("Peak Amps", `${stateAttrs.daily_peak_amps ?? 0}A`),
        this._row("Charge Time", `${stateAttrs.daily_charge_minutes ?? 0} min`),
        this._row("Plan", this._val("sensor.plan")),
        this._row("Plan Detail", `<span style="font-size:11px">${this._hass.states["sensor.plan"]?.attributes?.detail || "No plan yet (runs at planning time)"}</span>`),
      ].join("");
    }

    // Advisor Debug
    const advisorState = this._hass.states["sensor.tesla_solar_charging_appliance_advisor_summary"];
    const advisorSummaryEl = this.querySelector("#advisor-summary");
    const advisorTbody = this.querySelector("#advisor-tbody");
    if (advisorSummaryEl) {
      advisorSummaryEl.textContent = advisorState ? advisorState.state : "No advisor data";
    }
    if (advisorTbody) {
      const appliances = advisorState?.attributes?.appliances || [];
      if (appliances.length === 0) {
        advisorTbody.innerHTML = `<tr><td colspan="8" style="text-align:center;opacity:0.5;padding:12px">No appliance data available</td></tr>`;
      } else {
        const statusColor = { free: "green", paid: "orange", skipped: "grey", running: "blue", error: "red" };
        advisorTbody.innerHTML = appliances.map(a => {
          const cls = statusColor[a.status] || "grey";
          const badge = `<span class="tsc-badge ${cls}">${a.status ?? "?"}</span>`;
          const running = a.running != null ? (a.running ? '<span class="tsc-badge blue">Yes</span>' : '<span class="tsc-badge grey">No</span>') : "N/A";
          const cost = a.cost != null ? `${a.cost}` : "N/A";
          const watts = a.watts != null ? `${a.watts}W` : "N/A";
          const deadline = a.deadline ?? "—";
          const latestStart = a.latest_start ?? "—";
          const reason = `<span style="font-size:11px;opacity:0.8">${a.reason ?? ""}</span>`;
          return `<tr>
            <td><b>${a.name ?? "?"}</b></td>
            <td>${badge}</td>
            <td>${cost}</td>
            <td>${reason}</td>
            <td>${running}</td>
            <td>${watts}</td>
            <td>${deadline}</td>
            <td>${latestStart}</td>
          </tr>`;
        }).join("");
      }
    }

    // Debug JSON
    const debugEl = this.querySelector("#debug-json");
    if (debugEl) {
      const debugState = this._hass.states["sensor.debug"];
      const debugJson = debugState?.attributes?.json || "{}";
      debugEl.textContent = debugJson;
    }
  }
}

if (!customElements.get("tesla-solar-charging-panel")) {
  customElements.define("tesla-solar-charging-panel", TeslaSolarChargingPanel);
}
