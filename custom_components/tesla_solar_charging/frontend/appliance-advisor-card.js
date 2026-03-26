/**
 * Appliance Advisor Card — Custom Lovelace card for Home Assistant
 *
 * Reads all appliance data from the summary sensor's attributes.
 * No hardcoded appliance names or icons.
 *
 * Card YAML config:
 *   type: custom:appliance-advisor-card
 *   entity: sensor.tesla_solar_charging_appliance_advisor_summary
 *   solar_entity: sensor.solar_production
 *   battery_soc_entity: sensor.esp32_deye_inverter_battery_soc
 *   tesla_soc_entity: sensor.tesla_di_luca_battery
 *   navigation:
 *     - label: "Dettaglio"
 *       path: /dashboard-consumi/dettaglio-consumi-nuovo
 */

class ApplianceAdvisorCard extends HTMLElement {
  // ---------------------------------------------------------------------------
  // HA lifecycle: setConfig is called first, then hass is set on every update
  // ---------------------------------------------------------------------------

  setConfig(config) {
    if (!config.entity) {
      throw new Error("appliance-advisor-card: 'entity' is required");
    }
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

  getCardSize() {
    return 6;
  }

  // ---------------------------------------------------------------------------
  // Shadow DOM setup
  // ---------------------------------------------------------------------------

  _attachShadow() {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
  }

  // ---------------------------------------------------------------------------
  // Initial render — injects static HTML + CSS into shadow DOM
  // ---------------------------------------------------------------------------

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
        }

        /* ---- Outer card shell ---- */
        .aa-card {
          background: var(--ha-card-background, var(--card-background-color, #fff));
          border-radius: 16px;
          overflow: hidden;
          box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0,0,0,.12));
          color: var(--primary-text-color, #333);
        }

        /* ---- Status banner ---- */
        .aa-banner {
          padding: 20px 20px 16px;
          transition: background 0.6s ease;
        }
        .aa-banner-label {
          font-size: 13px;
          font-weight: 700;
          letter-spacing: 1.5px;
          text-transform: uppercase;
          opacity: 0.75;
          color: #fff;
          margin-bottom: 4px;
        }
        .aa-banner-status {
          font-size: 32px;
          font-weight: 700;
          color: #fff;
          line-height: 1.15;
          text-shadow: 0 1px 4px rgba(0,0,0,.25);
        }

        /* ---- Three metric chips ---- */
        .aa-metrics {
          display: flex;
          gap: 12px;
          margin-top: 16px;
          flex-wrap: wrap;
        }
        .aa-metric {
          background: rgba(255,255,255,0.18);
          border-radius: 12px;
          padding: 8px 16px;
          flex: 1;
          min-width: 80px;
          text-align: center;
        }
        .aa-metric-label {
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 1px;
          text-transform: uppercase;
          color: rgba(255,255,255,0.8);
          margin-bottom: 2px;
        }
        .aa-metric-value {
          font-size: 26px;
          font-weight: 700;
          color: #fff;
          line-height: 1.15;
          text-shadow: 0 1px 3px rgba(0,0,0,.2);
        }

        /* ---- Appliance grid ---- */
        .aa-appliances {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 0;
        }
        .aa-appliance {
          padding: 16px 14px 14px;
          border-bottom: 1px solid var(--divider-color, rgba(0,0,0,.08));
          border-right: 1px solid var(--divider-color, rgba(0,0,0,.08));
          cursor: pointer;
          transition: background 0.15s ease;
          position: relative;
          border-left: 5px solid transparent;
          box-sizing: border-box;
        }
        .aa-appliance:nth-child(even) {
          border-right: none;
        }
        /* Remove bottom border from last two items */
        .aa-appliance.aa-last-row {
          border-bottom: none;
        }
        .aa-appliance:hover {
          background: var(--secondary-background-color, rgba(0,0,0,.03));
        }
        .aa-appliance.aa-status-green  { border-left-color: #43a047; }
        .aa-appliance.aa-status-yellow { border-left-color: #fb8c00; }
        .aa-appliance.aa-status-red    { border-left-color: #e53935; }

        .aa-app-icon {
          font-size: 32px;
          line-height: 1;
          margin-bottom: 6px;
          display: block;
        }
        .aa-app-name {
          font-size: 20px;
          font-weight: 600;
          color: var(--primary-text-color, #333);
          margin-bottom: 4px;
          line-height: 1.2;
        }
        .aa-app-cost {
          font-size: 18px;
          font-weight: 500;
          line-height: 1.2;
        }
        .aa-app-cost.green  { color: #2e7d32; }
        .aa-app-cost.yellow { color: #e65100; }
        .aa-app-cost.red    { color: #c62828; }

        .aa-app-watts {
          font-size: 13px;
          color: var(--secondary-text-color, #888);
          margin-top: 2px;
        }
        .aa-app-deadline {
          font-size: 13px;
          font-weight: 600;
          margin-top: 4px;
          color: #e65100;
        }
        .aa-app-deadline.urgent { color: #c62828; animation: aa-pulse-text 1s ease-in-out infinite alternate; }
        .aa-app-deadline.missed { color: #9e9e9e; }

        .aa-app-history {
          font-size: 12px;
          color: var(--secondary-text-color, #888);
          margin-top: 4px;
          line-height: 1.4;
        }
        .aa-app-history-icon {
          font-size: 11px;
          opacity: 0.7;
        }

        /* Pulsing glow for running appliances */
        @keyframes aa-running-glow {
          0%   { box-shadow: inset 0 0 0 1px rgba(67,160,71,0.3), 0 0 0 0 rgba(67,160,71,0); }
          50%  { box-shadow: inset 0 0 0 1px rgba(67,160,71,0.5), 0 0 8px 2px rgba(67,160,71,0.25); }
          100% { box-shadow: inset 0 0 0 1px rgba(67,160,71,0.3), 0 0 0 0 rgba(67,160,71,0); }
        }
        .aa-appliance.aa-running {
          animation: aa-running-glow 2s ease-in-out infinite;
        }
        .aa-running-dot {
          display: inline-block;
          width: 8px;
          height: 8px;
          background: #43a047;
          border-radius: 50%;
          margin-right: 5px;
          vertical-align: middle;
          animation: aa-pulse-dot 1.5s ease-in-out infinite;
        }
        @keyframes aa-pulse-dot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.6; transform: scale(1.4); }
        }
        @keyframes aa-pulse-text {
          from { opacity: 1; }
          to   { opacity: 0.6; }
        }

        /* ---- Inline deadline picker ---- */
        .aa-deadline-picker {
          display: none;
          background: var(--secondary-background-color, #f5f5f5);
          border-top: 1px solid var(--divider-color, rgba(0,0,0,.1));
          padding: 12px 14px;
          grid-column: 1 / -1;
        }
        .aa-deadline-picker.aa-open {
          display: block;
        }
        .aa-picker-title {
          font-size: 13px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.8px;
          color: var(--secondary-text-color, #888);
          margin-bottom: 10px;
        }
        .aa-picker-row {
          display: flex;
          gap: 8px;
          align-items: center;
          flex-wrap: wrap;
          margin-bottom: 10px;
        }
        .aa-picker-select,
        .aa-picker-time {
          padding: 8px 10px;
          border-radius: 8px;
          border: 1px solid var(--divider-color, #ccc);
          background: var(--ha-card-background, #fff);
          color: var(--primary-text-color, #333);
          font-size: 15px;
          font-family: inherit;
        }
        .aa-picker-select { min-width: 130px; }
        .aa-picker-time   { width: 110px; }
        .aa-picker-save {
          padding: 8px 20px;
          background: var(--primary-color, #03a9f4);
          color: #fff;
          border: none;
          border-radius: 8px;
          font-size: 15px;
          font-weight: 600;
          cursor: pointer;
          font-family: inherit;
        }
        .aa-picker-save:hover { opacity: 0.9; }
        .aa-picker-clear {
          padding: 8px 14px;
          background: transparent;
          color: var(--secondary-text-color, #888);
          border: 1px solid var(--divider-color, #ccc);
          border-radius: 8px;
          font-size: 15px;
          cursor: pointer;
          font-family: inherit;
        }
        .aa-picker-clear:hover { background: var(--divider-color, #eee); }

        /* ---- Navigation ---- */
        .aa-nav {
          display: flex;
          gap: 8px;
          padding: 14px 16px;
          border-top: 1px solid var(--divider-color, rgba(0,0,0,.08));
          flex-wrap: wrap;
        }
        .aa-nav-btn {
          flex: 1;
          min-width: 70px;
          padding: 12px 10px;
          background: var(--secondary-background-color, #f0f0f0);
          color: var(--primary-text-color, #333);
          border: none;
          border-radius: 10px;
          font-size: 16px;
          font-weight: 600;
          cursor: pointer;
          font-family: inherit;
          text-align: center;
          transition: background 0.15s, transform 0.1s;
        }
        .aa-nav-btn:hover  { background: var(--divider-color, #e0e0e0); }
        .aa-nav-btn:active { transform: scale(0.97); }

        /* ---- Empty state ---- */
        .aa-empty {
          padding: 32px 20px;
          text-align: center;
          color: var(--secondary-text-color, #888);
          font-size: 16px;
        }
      </style>
      <div class="aa-card">
        <div class="aa-banner" id="aa-banner">
          <div class="aa-banner-label">Stato Casa</div>
          <div class="aa-banner-status" id="aa-banner-status">—</div>
          <div class="aa-metrics" id="aa-metrics"></div>
        </div>
        <div class="aa-appliances" id="aa-appliances"></div>
        <div class="aa-nav" id="aa-nav"></div>
      </div>
    `;

    // Render static navigation buttons once (they don't depend on hass state)
    this._renderNav();
  }

  // ---------------------------------------------------------------------------
  // Navigation buttons — rendered once from config
  // ---------------------------------------------------------------------------

  _renderNav() {
    const nav = this._config.navigation || [];
    const navEl = this.shadowRoot.getElementById("aa-nav");
    if (!navEl) return;
    if (nav.length === 0) {
      navEl.style.display = "none";
      return;
    }
    navEl.innerHTML = nav.map(item => `
      <button class="aa-nav-btn" data-path="${this._esc(item.path || "")}">
        ${this._esc(item.label || item.path || "?")}
      </button>
    `).join("");

    navEl.querySelectorAll(".aa-nav-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const path = btn.dataset.path;
        if (path && this._hass) {
          // Use HA navigation service
          this._hass.callService("browser_mod", "navigate", { path }).catch(() => {
            // Fallback: direct location change
            window.location.href = path;
          });
        }
      });
    });
  }

  // ---------------------------------------------------------------------------
  // Main update — called on every hass state change
  // ---------------------------------------------------------------------------

  _update() {
    if (!this._hass || !this._config) return;

    const summaryEntityId = this._config.entity;
    const summaryState    = this._hass.states[summaryEntityId];
    const appliances      = summaryState?.attributes?.appliances || [];

    this._updateBanner(appliances);
    this._updateMetrics();
    this._updateAppliances(appliances);
  }

  // ---------------------------------------------------------------------------
  // Banner — gradient + status text based on green ratio
  // ---------------------------------------------------------------------------

  _updateBanner(appliances) {
    const bannerEl = this.shadowRoot.getElementById("aa-banner");
    const statusEl = this.shadowRoot.getElementById("aa-banner-status");
    if (!bannerEl || !statusEl) return;

    const total = appliances.length;
    if (total === 0) {
      bannerEl.style.background = "linear-gradient(135deg, #607d8b 0%, #455a64 100%)";
      statusEl.textContent = "Nessun elettrodomestico";
      return;
    }

    const greenCount  = appliances.filter(a => a.status === "green").length;
    const yellowCount = appliances.filter(a => a.status === "yellow").length;
    const ratio = greenCount / total;

    let gradient, statusText;

    if (ratio >= 0.75) {
      gradient = "linear-gradient(135deg, #2e7d32 0%, #43a047 50%, #66bb6a 100%)";
      statusText = greenCount === total ? "Solare al 100%" : `Solare — ${greenCount} di ${total} gratis`;
    } else if (ratio >= 0.4 || yellowCount > 0) {
      // Mixed — blend green→yellow proportionally
      const g = Math.round(ratio * 100);
      gradient = `linear-gradient(135deg, #f57f17 0%, #fb8c00 40%, #ffa726 100%)`;
      statusText = greenCount > 0
        ? `Parziale — ${greenCount} gratis, ${yellowCount} misto`
        : `Costo elevato — solare insufficiente`;
    } else {
      gradient = "linear-gradient(135deg, #b71c1c 0%, #e53935 50%, #ef5350 100%)";
      statusText = "Prevalentemente da rete";
    }

    bannerEl.style.background = gradient;
    statusEl.textContent = statusText;
  }

  // ---------------------------------------------------------------------------
  // Metrics row — Solar, Battery, Tesla
  // ---------------------------------------------------------------------------

  _updateMetrics() {
    const metricsEl = this.shadowRoot.getElementById("aa-metrics");
    if (!metricsEl) return;

    const solarVal   = this._solarDisplay();
    const batteryVal = this._numVal(this._config.battery_soc_entity);
    const teslaVal   = this._numVal(this._config.tesla_soc_entity);

    metricsEl.innerHTML = `
      <div class="aa-metric">
        <div class="aa-metric-label">Solare</div>
        <div class="aa-metric-value">${solarVal}</div>
      </div>
      <div class="aa-metric">
        <div class="aa-metric-label">Batteria</div>
        <div class="aa-metric-value">${batteryVal !== null ? batteryVal + "%" : "—"}</div>
      </div>
      <div class="aa-metric">
        <div class="aa-metric-label">Tesla</div>
        <div class="aa-metric-value">${teslaVal !== null ? teslaVal + "%" : "—"}</div>
      </div>
    `;
  }

  _solarDisplay() {
    const entityId = this._config.solar_entity;
    if (!entityId) return "—";
    const state = this._hass.states[entityId];
    if (!state || state.state === "unavailable" || state.state === "unknown") return "—";
    const raw = parseFloat(state.state);
    if (isNaN(raw)) return "—";
    if (raw >= 1000) {
      return (raw / 1000).toFixed(1) + " kW";
    }
    return Math.round(raw) + " W";
  }

  _numVal(entityId) {
    if (!entityId) return null;
    const state = this._hass.states[entityId];
    if (!state || state.state === "unavailable" || state.state === "unknown") return null;
    const v = parseFloat(state.state);
    return isNaN(v) ? null : Math.round(v);
  }

  // ---------------------------------------------------------------------------
  // Appliance grid
  // ---------------------------------------------------------------------------

  _updateAppliances(appliances) {
    const container = this.shadowRoot.getElementById("aa-appliances");
    if (!container) return;

    if (appliances.length === 0) {
      container.innerHTML = `
        <div class="aa-empty" style="grid-column:1/-1">
          Nessun elettrodomestico configurato.<br>
          <small>Aggiungi elettrodomestici nelle impostazioni dell'integrazione.</small>
        </div>`;
      return;
    }

    // Preserve open picker state across updates
    const openKey = this._openPickerKey || null;

    // Build new HTML
    const rows = appliances.map((app, idx) => {
      const isLastRow = idx >= appliances.length - (appliances.length % 2 === 0 ? 2 : 1);
      const lastRowClass = isLastRow ? " aa-last-row" : "";
      const runningClass = app.running ? " aa-running" : "";
      const statusClass  = `aa-status-${app.status || "red"}`;
      const costClass    = app.status || "red";
      const icon         = this._esc(app.icon || this._fallbackIcon(app.key || ""));
      const name         = this._esc(app.name || app.key || "?");

      // Cost / deadline label
      let costHtml = "";
      if (app.deadline_message) {
        let deadlineClass = "";
        if (app.deadline_message === "Avvia adesso!") deadlineClass = " urgent";
        else if (app.deadline_message === "Troppo tardi") deadlineClass = " missed";
        costHtml = `<div class="aa-app-deadline${deadlineClass}">${this._esc(app.deadline_message)}</div>`;
      } else {
        costHtml = `<div class="aa-app-cost ${costClass}">${this._esc(app.cost_label || "—")}</div>`;
      }

      // Running wattage
      const wattsHtml = app.running && app.current_watts != null
        ? `<div class="aa-app-watts"><span class="aa-running-dot"></span>${Math.round(app.current_watts)} W</div>`
        : "";

      // Run history
      let historyHtml = "";
      const parts = [];
      if (app.last_run_end) {
        parts.push(`<span class="aa-app-history-icon">🕐</span> ${this._formatTimeAgo(app.last_run_end)}`);
      }
      if (app.avg_consumption_kwh != null) {
        parts.push(`<span class="aa-app-history-icon">⚡</span> ${app.avg_consumption_kwh} kWh media`);
      }
      if (parts.length > 0) {
        historyHtml = `<div class="aa-app-history">${parts.join(" · ")}</div>`;
      }

      return `
        <div class="aa-appliance ${statusClass}${runningClass}${lastRowClass}"
             data-key="${this._esc(app.key || "")}"
             tabindex="0"
             role="button"
             aria-label="${name}">
          <span class="aa-app-icon">${icon}</span>
          <div class="aa-app-name">${name}</div>
          ${costHtml}
          ${wattsHtml}
          ${historyHtml}
        </div>`;
    }).join("");

    container.innerHTML = rows;

    // Re-attach click handlers
    container.querySelectorAll(".aa-appliance").forEach(el => {
      el.addEventListener("click", (e) => this._onApplianceTap(e, el));
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          this._onApplianceTap(e, el);
        }
      });
    });

    // Re-open picker if it was open before (key may have changed on rerender)
    if (openKey) {
      const target = container.querySelector(`[data-key="${CSS.escape(openKey)}"]`);
      if (target) {
        this._insertPickerAfter(target, openKey, appliances);
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Appliance tap — open/close inline deadline picker
  // ---------------------------------------------------------------------------

  _onApplianceTap(e, el) {
    const key = el.dataset.key;
    if (!key) return;

    // If picker is already open for this key, close it
    if (this._openPickerKey === key) {
      this._closePicker();
      return;
    }

    this._closePicker();

    const summaryState = this._hass.states[this._config.entity];
    const appliances   = summaryState?.attributes?.appliances || [];
    this._openPickerKey = key;
    this._insertPickerAfter(el, key, appliances);
  }

  _insertPickerAfter(el, key, appliances) {
    // Find current deadline for this appliance from summary sensor
    // (the deadline_message and latest_start_time are in the sensor attrs)
    const app = appliances.find(a => a.key === key) || {};

    // Determine current picker values from existing deadline data stored in attributes
    // We parse latest_start_time to pre-fill the time input if a deadline exists
    const currentTime        = app.latest_start_time || "";
    const hasDeadline        = !!app.deadline_message || !!app.latest_start_time;
    const currentType        = hasDeadline ? "finish_by" : "none";

    // Build picker element using class selectors (avoids ID-uniqueness requirements)
    const picker = document.createElement("div");
    picker.className = "aa-deadline-picker aa-open";
    picker.dataset.pickerKey = key;
    picker.innerHTML = `
      <div class="aa-picker-title">Scadenza — ${this._esc(app.name || key)}</div>
      <div class="aa-picker-row">
        <select class="aa-picker-select aa-picker-type">
          <option value="none"${currentType === "none" ? " selected" : ""}>Nessuna scadenza</option>
          <option value="finish_by"${currentType === "finish_by" ? " selected" : ""}>Finisci entro</option>
          <option value="start_by"${currentType === "start_by" ? " selected" : ""}>Inizia entro</option>
        </select>
        <input type="time" class="aa-picker-time aa-picker-timeval"
               value="${this._esc(currentTime)}" step="300" />
      </div>
      <div class="aa-picker-row">
        <button class="aa-picker-save aa-picker-btn-save">Salva</button>
        <button class="aa-picker-clear aa-picker-btn-cancel">Annulla</button>
      </div>
    `;

    // Insert after the appliance tile's row-pair in the 2-column grid
    const container = this.shadowRoot.getElementById("aa-appliances");
    const allTiles  = Array.from(container.querySelectorAll(".aa-appliance"));
    const tileIdx   = allTiles.indexOf(el);

    // Pair partner: even index → next tile; odd → same tile (already right column)
    const pairIdx   = tileIdx % 2 === 0 ? tileIdx + 1 : tileIdx;
    const pairTile  = allTiles[pairIdx] || el;

    container.insertBefore(picker, pairTile.nextSibling || null);

    // Wire up buttons via class selectors scoped to picker
    const typeSelect = picker.querySelector(".aa-picker-type");
    const timeInput  = picker.querySelector(".aa-picker-timeval");

    picker.querySelector(".aa-picker-btn-save").addEventListener("click", () => {
      const dtype = typeSelect ? typeSelect.value : "none";
      const dtime = (timeInput && timeInput.value) ? timeInput.value : null;
      this._saveDeadline(key, dtype, dtime);
    });

    picker.querySelector(".aa-picker-btn-cancel").addEventListener("click", () => {
      this._closePicker();
    });

    // Show/hide time input based on type selection
    const _toggleTime = () => {
      if (timeInput) {
        timeInput.style.display = typeSelect && typeSelect.value === "none" ? "none" : "";
      }
    };
    _toggleTime();
    if (typeSelect) typeSelect.addEventListener("change", _toggleTime);
  }

  _closePicker() {
    const container = this.shadowRoot.getElementById("aa-appliances");
    if (!container) return;
    container.querySelectorAll(".aa-deadline-picker").forEach(p => p.remove());
    this._openPickerKey = null;
  }

  // ---------------------------------------------------------------------------
  // Service call — set_appliance_deadline
  // ---------------------------------------------------------------------------

  _saveDeadline(applianceKey, deadlineType, deadlineTime) {
    if (!this._hass) return;
    const data = {
      appliance: applianceKey,
      type:      deadlineType,
    };
    if (deadlineTime && deadlineType !== "none") {
      data.time = deadlineTime;
    }
    this._hass.callService("tesla_solar_charging", "set_appliance_deadline", data)
      .then(() => {
        this._closePicker();
      })
      .catch(err => {
        console.error("appliance-advisor-card: failed to set deadline", err);
        // Keep picker open on error so user can retry
      });
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  /** HTML-escape a string to prevent XSS when injected via innerHTML */
  _esc(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /**
   * Format an ISO datetime string as a relative "time ago" label in Italian.
   */
  _formatTimeAgo(isoStr) {
    if (!isoStr) return "";
    try {
      const date = new Date(isoStr);
      const now = new Date();
      const diffMs = now - date;
      const diffMin = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);

      if (diffMin < 1) return "adesso";
      if (diffMin < 60) return `${diffMin} min fa`;
      if (diffHours < 24) return `${diffHours}h fa`;
      if (diffDays === 1) return "ieri";
      if (diffDays < 7) return `${diffDays}g fa`;
      // Show date for older runs
      return date.toLocaleDateString("it-IT", { day: "numeric", month: "short" });
    } catch {
      return "";
    }
  }

  /**
   * Fallback icon lookup by appliance key.
   * Uses actual emoji characters (not Python unicode escapes).
   * The sensor stores the real emoji, so this is only used if icon is missing.
   */
  _fallbackIcon(key) {
    const lower = (key || "").toLowerCase();
    if (lower.includes("lava") && lower.includes("toviglie")) return "🍽️";
    if (lower.includes("lavatrice"))  return "👕";
    if (lower.includes("forno"))      return "🔥";
    if (lower.includes("asciuga"))    return "💨";
    if (lower.includes("condi") || lower.includes("_ac")) return "❄️";
    return "🔌";
  }
}

// ---------------------------------------------------------------------------
// Register custom element (guarded for HA integration reload safety)
// ---------------------------------------------------------------------------

if (!customElements.get("appliance-advisor-card")) {
  customElements.define("appliance-advisor-card", ApplianceAdvisorCard);
}

// ---------------------------------------------------------------------------
// Register in window.customCards for the HA card picker UI
// ---------------------------------------------------------------------------

window.customCards = window.customCards || [];
if (!window.customCards.some(c => c.type === "appliance-advisor-card")) {
  window.customCards.push({
    type:        "appliance-advisor-card",
    name:        "Appliance Advisor",
    description: "Traffic-light appliance recommendations based on solar surplus. Part of Tesla Solar Charging.",
    preview:     false,
  });
}
