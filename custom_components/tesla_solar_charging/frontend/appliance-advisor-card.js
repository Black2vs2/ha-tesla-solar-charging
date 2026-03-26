/**
 * Appliance Advisor Card — Custom Lovelace card for Home Assistant
 *
 * Card YAML config:
 *   type: custom:appliance-advisor-card
 *   entity: sensor.appliance_advisor_summary_2
 *   solar_entity: sensor.solar_production
 *   battery_soc_entity: sensor.esp32_deye_inverter_battery_soc
 *   tesla_soc_entity: sensor.tesla_di_luca_battery
 *   tesla_state_entity: sensor.tesla_solar_charging_state
 *   tesla_amps_entity: sensor.tesla_solar_charging_charging_amps
 *   tesla_charge_limit_entity: number.tesla_solar_charging_charge_limit
 *   tesla_battery_kwh: 75
 *   navigation:
 *     - label: "Dettaglio"
 *       path: /dashboard-consumi/dettaglio-consumi-nuovo
 */

class ApplianceAdvisorCard extends HTMLElement {

  setConfig(config) {
    if (!config.entity) throw new Error("appliance-advisor-card: 'entity' is required");
    this._config = config;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._attachShadow();
      this._render();
      this._initialized = true;
    }
    this._update();
  }

  getCardSize() { return 10; }

  _attachShadow() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
        }
        .aa-card {
          background: var(--ha-card-background, var(--card-background-color, #fff));
          border-radius: 16px; overflow: hidden;
          box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0,0,0,.12));
          color: var(--primary-text-color, #333);
        }

        /* ---- Banner ---- */
        .aa-banner { padding: 20px 20px 16px; transition: background 0.6s ease; }
        .aa-banner-label {
          font-size: 13px; font-weight: 700; letter-spacing: 1.5px;
          text-transform: uppercase; opacity: 0.75; color: #fff; margin-bottom: 4px;
        }
        .aa-banner-status {
          font-size: 28px; font-weight: 700; color: #fff;
          line-height: 1.15; text-shadow: 0 1px 4px rgba(0,0,0,.25);
        }

        /* ---- Metrics ---- */
        .aa-metrics { display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap; }
        .aa-metric {
          background: rgba(255,255,255,0.18); border-radius: 10px;
          padding: 6px 14px; flex: 1; min-width: 70px; text-align: center;
        }
        .aa-metric-label {
          font-size: 10px; font-weight: 700; letter-spacing: 1px;
          text-transform: uppercase; color: rgba(255,255,255,0.8); margin-bottom: 1px;
        }
        .aa-metric-value {
          font-size: 22px; font-weight: 700; color: #fff;
          line-height: 1.15; text-shadow: 0 1px 3px rgba(0,0,0,.2);
        }

        /* ---- Tesla section ---- */
        .aa-tesla {
          display: flex; align-items: center; gap: 14px;
          padding: 14px 16px;
          border-bottom: 1px solid var(--divider-color, rgba(0,0,0,.08));
          background: var(--secondary-background-color, rgba(0,0,0,.02));
        }
        .aa-tesla-icon { font-size: 28px; flex-shrink: 0; }
        .aa-tesla-body { flex: 1; }
        .aa-tesla-header {
          display: flex; align-items: center; gap: 8px; margin-bottom: 2px;
        }
        .aa-tesla-name { font-size: 16px; font-weight: 600; }
        .aa-tesla-badge {
          font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px;
          letter-spacing: 0.5px; text-transform: uppercase;
        }
        .aa-tesla-badge.charging { background: #e3f2fd; color: #1565c0; }
        .aa-tesla-badge.idle     { background: #f5f5f5; color: #757575; }
        .aa-tesla-badge.full     { background: #e8f5e9; color: #2e7d32; }
        .aa-tesla-detail {
          font-size: 13px; color: var(--secondary-text-color, #888);
        }
        .aa-tesla-charging-bar {
          margin-top: 6px; height: 6px; border-radius: 3px;
          background: var(--divider-color, #e0e0e0); overflow: hidden;
        }
        .aa-tesla-charging-fill {
          height: 100%; border-radius: 3px;
          background: linear-gradient(90deg, #1565c0, #42a5f5);
          transition: width 0.6s ease;
        }
        .aa-tesla-charging-fill.full-bar {
          background: linear-gradient(90deg, #2e7d32, #66bb6a);
        }

        /* ---- Area header ---- */
        .aa-area-header {
          padding: 10px 16px 4px;
          font-size: 12px; font-weight: 700; letter-spacing: 1.2px;
          text-transform: uppercase;
          color: var(--secondary-text-color, #999);
          border-top: 1px solid var(--divider-color, rgba(0,0,0,.08));
        }
        .aa-area-header:first-child { border-top: none; }

        /* ---- Appliance row ---- */
        .aa-appliance {
          display: flex; align-items: flex-start; gap: 14px;
          padding: 12px 16px;
          border-bottom: 1px solid var(--divider-color, rgba(0,0,0,.06));
          border-left: 5px solid transparent; box-sizing: border-box;
          transition: background 0.15s ease;
        }
        .aa-appliance:last-child { border-bottom: none; }
        .aa-appliance.aa-status-green  { border-left-color: #43a047; }
        .aa-appliance.aa-status-yellow { border-left-color: #fb8c00; }
        .aa-appliance.aa-status-red    { border-left-color: #e53935; }

        /* Running state — green background tint + glow */
        .aa-appliance.aa-running {
          background: rgba(67, 160, 71, 0.06);
          animation: aa-running-glow 2s ease-in-out infinite;
        }
        @keyframes aa-running-glow {
          0%   { box-shadow: inset 0 0 0 1px rgba(67,160,71,0.2); }
          50%  { box-shadow: inset 0 0 0 1px rgba(67,160,71,0.4), 0 0 6px 1px rgba(67,160,71,0.15); }
          100% { box-shadow: inset 0 0 0 1px rgba(67,160,71,0.2); }
        }
        /* Idle/off state — slightly dimmed */
        .aa-appliance.aa-idle {
          opacity: 0.65;
        }

        .aa-app-icon { font-size: 26px; line-height: 1; flex-shrink: 0; margin-top: 2px; }
        .aa-app-body { flex: 1; min-width: 0; }

        .aa-app-header { display: flex; align-items: center; gap: 8px; margin-bottom: 2px; }
        .aa-app-name {
          font-size: 15px; font-weight: 600;
          color: var(--primary-text-color, #333);
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .aa-badge {
          font-size: 10px; font-weight: 700; letter-spacing: 0.5px;
          padding: 2px 7px; border-radius: 5px; flex-shrink: 0;
          text-transform: uppercase;
        }
        .aa-badge.green  { background: #e8f5e9; color: #2e7d32; }
        .aa-badge.yellow { background: #fff3e0; color: #e65100; }
        .aa-badge.red    { background: #ffebee; color: #c62828; }

        .aa-app-reason {
          font-size: 12px; color: var(--secondary-text-color, #888); margin-bottom: 1px;
        }

        /* Running indicator */
        .aa-app-live {
          font-size: 13px; font-weight: 600; color: #2e7d32; margin-bottom: 1px;
          display: flex; align-items: center; gap: 4px;
        }
        .aa-running-dot {
          display: inline-block; width: 8px; height: 8px;
          background: #43a047; border-radius: 50%;
          animation: aa-pulse-dot 1.5s ease-in-out infinite;
        }
        @keyframes aa-pulse-dot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.5; transform: scale(1.5); }
        }

        .aa-app-deadline { font-size: 12px; font-weight: 600; margin-bottom: 1px; }
        .aa-app-deadline.free    { color: #2e7d32; }
        .aa-app-deadline.warning { color: #e65100; }
        .aa-app-deadline.urgent  { color: #c62828; animation: aa-pulse-text 1s ease-in-out infinite alternate; }
        .aa-app-deadline.missed  { color: #9e9e9e; }
        @keyframes aa-pulse-text { from { opacity: 1; } to { opacity: 0.6; } }

        .aa-app-history {
          font-size: 11px; color: var(--secondary-text-color, #aaa);
          display: flex; gap: 10px; flex-wrap: wrap; margin-top: 1px;
        }

        /* ---- Nav ---- */
        .aa-nav {
          display: flex; gap: 8px; padding: 14px 16px;
          border-top: 1px solid var(--divider-color, rgba(0,0,0,.08)); flex-wrap: wrap;
        }
        .aa-nav-btn {
          flex: 1; min-width: 70px; padding: 10px;
          background: var(--secondary-background-color, #f0f0f0);
          color: var(--primary-text-color, #333);
          border: none; border-radius: 10px;
          font-size: 15px; font-weight: 600; cursor: pointer;
          font-family: inherit; text-align: center;
        }
        .aa-nav-btn:hover { background: var(--divider-color, #e0e0e0); }

        .aa-empty {
          padding: 32px 20px; text-align: center;
          color: var(--secondary-text-color, #888); font-size: 16px;
        }
      </style>
      <div class="aa-card">
        <div class="aa-banner" id="aa-banner">
          <div class="aa-banner-label">Stato Casa</div>
          <div class="aa-banner-status" id="aa-banner-status">—</div>
          <div class="aa-metrics" id="aa-metrics"></div>
        </div>
        <div id="aa-tesla"></div>
        <div id="aa-appliances"></div>
        <div class="aa-nav" id="aa-nav"></div>
      </div>
    `;
    this._renderNav();
  }

  _renderNav() {
    const nav = this._config.navigation || [];
    const navEl = this.shadowRoot.getElementById("aa-nav");
    if (!navEl) return;
    if (nav.length === 0) { navEl.style.display = "none"; return; }
    navEl.innerHTML = nav.map(item =>
      `<button class="aa-nav-btn" data-path="${this._esc(item.path || "")}">${this._esc(item.label || "?")}</button>`
    ).join("");
    navEl.querySelectorAll(".aa-nav-btn").forEach(btn => {
      btn.addEventListener("click", () => { if (btn.dataset.path) window.location.href = btn.dataset.path; });
    });
  }

  // ---------------------------------------------------------------------------
  // Update
  // ---------------------------------------------------------------------------

  _update() {
    if (!this._hass || !this._config) return;
    const summaryState = this._hass.states[this._config.entity];
    const appliances   = summaryState?.attributes?.appliances || [];
    this._updateBanner(appliances);
    this._updateMetrics();
    this._updateTesla();
    this._updateAppliances(appliances);
  }

  _updateBanner(appliances) {
    const bannerEl = this.shadowRoot.getElementById("aa-banner");
    const statusEl = this.shadowRoot.getElementById("aa-banner-status");
    if (!bannerEl || !statusEl) return;
    const total = appliances.length;
    if (total === 0) {
      bannerEl.style.background = "linear-gradient(135deg, #607d8b 0%, #455a64 100%)";
      statusEl.textContent = "Nessun elettrodomestico"; return;
    }
    const green = appliances.filter(a => a.status === "green").length;
    const yellow = appliances.filter(a => a.status === "yellow").length;
    const ratio = green / total;
    if (ratio >= 0.75) {
      bannerEl.style.background = "linear-gradient(135deg, #2e7d32 0%, #43a047 50%, #66bb6a 100%)";
      statusEl.textContent = green === total ? "Solare al 100%" : `Solare — ${green} di ${total} gratis`;
    } else if (ratio >= 0.4 || yellow > 0) {
      bannerEl.style.background = "linear-gradient(135deg, #f57f17 0%, #fb8c00 40%, #ffa726 100%)";
      statusEl.textContent = green > 0 ? `Parziale — ${green} gratis, ${yellow} misto` : "Costo elevato — solare insufficiente";
    } else {
      bannerEl.style.background = "linear-gradient(135deg, #b71c1c 0%, #e53935 50%, #ef5350 100%)";
      statusEl.textContent = "Prevalentemente da rete";
    }
  }

  _updateMetrics() {
    const el = this.shadowRoot.getElementById("aa-metrics");
    if (!el) return;
    const solar = this._solarDisplay();
    const batt  = this._numVal(this._config.battery_soc_entity);
    const tesla = this._numVal(this._config.tesla_soc_entity);
    el.innerHTML = `
      <div class="aa-metric"><div class="aa-metric-label">Solare</div><div class="aa-metric-value">${solar}</div></div>
      <div class="aa-metric"><div class="aa-metric-label">Batteria</div><div class="aa-metric-value">${batt !== null ? batt + "%" : "—"}</div></div>
      <div class="aa-metric"><div class="aa-metric-label">Tesla</div><div class="aa-metric-value">${tesla !== null ? tesla + "%" : "—"}</div></div>
    `;
  }

  _solarDisplay() {
    const s = this._stateVal(this._config.solar_entity);
    if (s === null) return "—";
    return s >= 1000 ? (s / 1000).toFixed(1) + " kW" : Math.round(s) + " W";
  }

  _numVal(entityId) {
    const v = this._stateVal(entityId);
    return v !== null ? Math.round(v) : null;
  }

  _stateVal(entityId) {
    if (!entityId) return null;
    const state = this._hass.states[entityId];
    if (!state || state.state === "unavailable" || state.state === "unknown") return null;
    const v = parseFloat(state.state);
    return isNaN(v) ? null : v;
  }

  _stateStr(entityId) {
    if (!entityId) return null;
    const state = this._hass.states[entityId];
    if (!state || state.state === "unavailable" || state.state === "unknown") return null;
    return state.state;
  }

  // ---------------------------------------------------------------------------
  // Tesla section
  // ---------------------------------------------------------------------------

  _updateTesla() {
    const el = this.shadowRoot.getElementById("aa-tesla");
    if (!el) return;

    const soc = this._numVal(this._config.tesla_soc_entity);
    const stateStr = this._stateStr(this._config.tesla_state_entity);
    const amps = this._numVal(this._config.tesla_amps_entity);
    const limitVal = this._numVal(this._config.tesla_charge_limit_entity);
    const limit = limitVal || 80;
    const battKwh = this._config.tesla_battery_kwh || 75;

    // Don't show Tesla section if no state entity configured
    if (!this._config.tesla_state_entity && !this._config.tesla_soc_entity) {
      el.innerHTML = ""; return;
    }

    const isCharging = stateStr && (stateStr.toLowerCase().includes("charg") || stateStr.toLowerCase().includes("solar") || (amps && amps > 0));
    const isFull = soc !== null && soc >= limit;

    let badgeText, badgeClass, detailText;
    if (isCharging) {
      badgeText = "In carica"; badgeClass = "charging";
      const watts = (amps || 0) * 230;
      const wattsStr = watts >= 1000 ? (watts / 1000).toFixed(1) + " kW" : watts + " W";
      detailText = `${amps || 0}A — ${wattsStr}`;
      // ETA
      if (soc !== null && soc < limit && amps > 0) {
        const kwhRemaining = battKwh * (limit - soc) / 100;
        const chargePowerKw = amps * 230 / 1000;
        const hoursLeft = kwhRemaining / chargePowerKw;
        if (hoursLeft < 1) {
          detailText += ` — ~${Math.round(hoursLeft * 60)} min rimasti`;
        } else {
          const h = Math.floor(hoursLeft);
          const m = Math.round((hoursLeft - h) * 60);
          detailText += ` — ~${h}h${m > 0 ? m + "m" : ""} rimasti`;
        }
      }
    } else if (isFull) {
      badgeText = "Completa"; badgeClass = "full";
      detailText = `${soc}% — limite ${limit}%`;
    } else {
      badgeText = "In attesa"; badgeClass = "idle";
      detailText = soc !== null ? `${soc}% — limite ${limit}%` : "—";
    }

    const barPct = soc !== null ? Math.min(100, Math.max(0, (soc / limit) * 100)) : 0;
    const barClass = isFull ? " full-bar" : "";

    el.innerHTML = `
      <div class="aa-tesla">
        <span class="aa-tesla-icon">\u{1F697}</span>
        <div class="aa-tesla-body">
          <div class="aa-tesla-header">
            <span class="aa-tesla-name">Tesla</span>
            <span class="aa-tesla-badge ${badgeClass}">${badgeText}</span>
          </div>
          <div class="aa-tesla-detail">${this._esc(detailText)}</div>
          <div class="aa-tesla-charging-bar">
            <div class="aa-tesla-charging-fill${barClass}" style="width:${barPct}%"></div>
          </div>
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // Appliance list — grouped by area
  // ---------------------------------------------------------------------------

  _updateAppliances(appliances) {
    const container = this.shadowRoot.getElementById("aa-appliances");
    if (!container) return;

    if (appliances.length === 0) {
      container.innerHTML = `<div class="aa-empty">Nessun elettrodomestico configurato.</div>`;
      return;
    }

    // Group by area: parse "Su" / "Giù" from name
    const groups = {};
    for (const app of appliances) {
      const area = this._detectArea(app.name || app.key || "");
      if (!groups[area]) groups[area] = [];
      groups[area].push(app);
    }

    // Render order: Piano di Sopra first, then Piano di Sotto, then Others
    const order = ["Piano di Sopra", "Piano di Sotto", "Altro"];
    const sortedKeys = Object.keys(groups).sort((a, b) => {
      const ia = order.indexOf(a); const ib = order.indexOf(b);
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    });

    let html = "";
    for (const area of sortedKeys) {
      html += `<div class="aa-area-header">${this._esc(area)}</div>`;
      for (const app of groups[area]) {
        html += this._renderAppliance(app);
      }
    }
    container.innerHTML = html;
  }

  _detectArea(name) {
    const lower = name.toLowerCase();
    if (lower.includes(" su") || lower.includes("_su")) return "Piano di Sopra";
    if (lower.includes(" gi") || lower.includes("_gi") || lower.includes(" giu") || lower.includes("_giu")) return "Piano di Sotto";
    return "Altro";
  }

  _renderAppliance(app) {
    const statusClass  = `aa-status-${app.status || "red"}`;
    const isRunning    = app.running === true;
    const isIdle       = app.running === false && (app.current_watts == null || app.current_watts === 0);
    const stateClass   = isRunning ? " aa-running" : (isIdle ? " aa-idle" : "");
    const badgeClass   = app.status || "red";
    const icon         = this._esc(app.icon || this._fallbackIcon(app.key || ""));
    // Strip area suffix from display name for cleaner look
    const name         = this._esc(this._stripArea(app.name || app.key || "?"));

    // Running indicator
    let liveHtml = "";
    if (isRunning && app.current_watts != null) {
      liveHtml = `<div class="aa-app-live"><span class="aa-running-dot"></span> In funzione — ${Math.round(app.current_watts)} W</div>`;
    }

    // Deadline / suggestion
    let deadlineHtml = "";
    if (app.deadline_message) {
      let cls = "warning";
      if (app.deadline_message === "Avvia adesso!") cls = "urgent";
      else if (app.deadline_message === "Troppo tardi") cls = "missed";
      deadlineHtml = `<div class="aa-app-deadline ${cls}">${this._esc(app.deadline_message)}</div>`;
    } else if (app.status === "green") {
      deadlineHtml = `<div class="aa-app-deadline free">Avvia ora — gratis con il solare</div>`;
    } else if (app.latest_start_time) {
      deadlineHtml = `<div class="aa-app-deadline warning">Avvia entro ${this._esc(app.latest_start_time)}</div>`;
    }

    // History
    const histParts = [];
    if (app.last_run_end) {
      const ago = this._formatTimeAgo(app.last_run_end);
      const kwh = app.last_run_kwh != null ? ` (${app.last_run_kwh} kWh)` : "";
      const dur = app.last_run_duration_min != null ? `, ${Math.round(app.last_run_duration_min)} min` : "";
      histParts.push(`Ultimo: ${ago}${dur}${kwh}`);
    }
    if (app.avg_consumption_kwh != null) {
      histParts.push(`Media: ${app.avg_consumption_kwh} kWh/ciclo`);
    }
    const historyHtml = histParts.length > 0
      ? `<div class="aa-app-history">${histParts.map(p => `<span>${this._esc(p)}</span>`).join("")}</div>`
      : "";

    return `
      <div class="aa-appliance ${statusClass}${stateClass}">
        <span class="aa-app-icon">${icon}</span>
        <div class="aa-app-body">
          <div class="aa-app-header">
            <span class="aa-app-name">${name}</span>
            <span class="aa-badge ${badgeClass}">${this._esc(app.cost_label || "—")}</span>
          </div>
          <div class="aa-app-reason">${this._esc(app.reason || "")}</div>
          ${liveHtml}
          ${deadlineHtml}
          ${historyHtml}
        </div>
      </div>`;
  }

  _stripArea(name) {
    return name.replace(/\s+(Su|Gi[uù])$/i, "").trim();
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  _esc(s) {
    if (s == null) return "";
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  _formatTimeAgo(isoStr) {
    if (!isoStr) return "";
    try {
      const d = new Date(isoStr), now = new Date(), ms = now - d;
      const min = Math.floor(ms / 60000), hrs = Math.floor(ms / 3600000), days = Math.floor(ms / 86400000);
      if (min < 1) return "adesso";
      if (min < 60) return `${min} min fa`;
      if (hrs < 24) return `${hrs}h fa`;
      if (days === 1) return "ieri";
      if (days < 7) return `${days}g fa`;
      return d.toLocaleDateString("it-IT", { day: "numeric", month: "short" });
    } catch { return ""; }
  }

  _fallbackIcon(key) {
    const k = (key || "").toLowerCase();
    if (k.includes("lavastoviglie")) return "\u{1F37D}\uFE0F";
    if (k.includes("lavatrice")) return "\u{1F455}";
    if (k.includes("forno")) return "\u{1F525}";
    if (k.includes("asciuga")) return "\u{1F4A8}";
    if (k.includes("condi") || k.includes("_ac")) return "\u2744\uFE0F";
    return "\u{1F50C}";
  }
}

if (!customElements.get("appliance-advisor-card")) {
  customElements.define("appliance-advisor-card", ApplianceAdvisorCard);
}
window.customCards = window.customCards || [];
if (!window.customCards.some(c => c.type === "appliance-advisor-card")) {
  window.customCards.push({
    type: "appliance-advisor-card",
    name: "Appliance Advisor",
    description: "Solar-aware appliance recommendations grouped by area.",
    preview: false,
  });
}
