"""Tesla Solar Charging integration — Energy Orchestrator."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change

from .ble_controller import BLEController
from .const import (
    CONF_AVG_HOUSE_CONSUMPTION_KWH,
    CONF_BATTERY_SOC_ENTITY,
    CONF_BLE_CHARGER_SWITCH,
    CONF_BLE_CHARGING_AMPS,
    CONF_BLE_WAKE_BUTTON,
    CONF_DAILY_PRODUCTION_ENTITY,
    CONF_DEYE_BATTERY_DISCHARGE_ENTITY,
    CONF_DEYE_ENERGY_PATTERN_ENTITY,
    CONF_DEYE_WORK_MODE_ENTITY,
    CONF_FORECAST_SOLAR_AZIMUTH,
    CONF_FORECAST_SOLAR_DECLINATION,
    CONF_FORECAST_SOLAR_ENABLED,
    CONF_HOME_BATTERY_KWH,
    CONF_HOURLY_FORECAST_ENABLED,
    CONF_OCTOPUS_DEVICE_ID,
    CONF_OCTOPUS_EMAIL,
    CONF_OCTOPUS_ENABLED,
    CONF_OCTOPUS_PASSWORD,
    CONF_OCTOPUS_SMART_CHARGE_ENTITY,
    CONF_PERFORMANCE_RATIO,
    CONF_PLANNER_SAFETY_MARGIN,
    CONF_PLANNING_TIME,
    CONF_PV_SYSTEM_KWP,
    CONF_SOLCAST_API_KEY,
    CONF_SOLCAST_RESOURCE_ID,
    CONF_TELEGRAM_CHAT_ID,
    CONF_TESLA_BATTERY_ENTITY,
    CONF_TESLA_BATTERY_KWH,
    DEFAULT_AVG_HOUSE_CONSUMPTION_KWH,
    DEFAULT_FORECAST_SOLAR_AZIMUTH,
    DEFAULT_FORECAST_SOLAR_DECLINATION,
    DEFAULT_PERFORMANCE_RATIO,
    DEFAULT_PLANNER_SAFETY_MARGIN,
    DEFAULT_PLANNING_TIME,
    DEFAULT_TESLA_BATTERY_KWH,
    DOMAIN,
    PLATFORMS,
    VERSION,
    STATE_PLANNED_NIGHT,
    STATE_PLANNED_SOLAR,
)
from .coordinator import SolarChargingCoordinator
from .forecast_blend import ForecastSource, blend_forecasts
from .forecast_tracker import ForecastTracker
from .inverter_controller import InverterController
from .notification import CALLBACK_CHARGE_TONIGHT, CALLBACK_SKIP_CHARGE, send_action_notification, send_plan_notification
from .octopus_client import OctopusItalyClient
from .planner import create_charge_plan
from .weather_forecast import fetch_solar_forecast

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tesla Solar Charging from a config entry."""
    from .const import CONF_ENTRY_TYPE, ENTRY_TYPE_ADVISOR

    hass.data.setdefault(DOMAIN, {})

    entry_type = entry.data.get(CONF_ENTRY_TYPE)
    if entry_type == ENTRY_TYPE_ADVISOR:
        return await _async_setup_advisor_entry(hass, entry)

    return await _async_setup_charging_entry(hass, entry)


async def _async_setup_advisor_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Appliance Advisor entry."""
    from .appliance_advisor.coordinator import AdvisorCoordinator
    from .appliance_advisor.store import DeadlineStore

    data = {**entry.data, **entry.options}

    deadline_store = DeadlineStore(hass)
    await deadline_store.async_load()

    coordinator = AdvisorCoordinator(hass, entry.entry_id, data, deadline_store)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    # Register static path for the card
    from homeassistant.components.http import StaticPathConfig
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            f"/{DOMAIN}/appliance-advisor-card.js",
            str(Path(__file__).parent / "frontend" / "appliance-advisor-card.js"),
            cache_headers=True,
        ),
    ])

    # Register service
    async def handle_set_deadline(call):
        appliance = call.data["appliance"]
        dtype = call.data.get("type", "none")
        dtime = call.data.get("time")
        await deadline_store.async_set(appliance, dtype, dtime)

    if not hass.services.has_service(DOMAIN, "set_appliance_deadline"):
        hass.services.async_register(DOMAIN, "set_appliance_deadline", handle_set_deadline)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_setup_charging_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Tesla Solar Charging entry."""
    data = {**entry.data, **entry.options}

    ble = BLEController(
        hass=hass,
        charger_switch=data[CONF_BLE_CHARGER_SWITCH],
        charging_amps=data[CONF_BLE_CHARGING_AMPS],
        wake_button=data[CONF_BLE_WAKE_BUTTON],
    )

    inverter = InverterController(
        hass=hass,
        work_mode_entity=data.get(CONF_DEYE_WORK_MODE_ENTITY),
        energy_pattern_entity=data.get(CONF_DEYE_ENERGY_PATTERN_ENTITY),
        battery_discharge_entity=data.get(CONF_DEYE_BATTERY_DISCHARGE_ENTITY),
    )

    coordinator = SolarChargingCoordinator(hass, entry.entry_id, data, ble, inverter)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Initialize forecast tracker
    tracker = ForecastTracker(hass)
    await tracker.async_load()
    coordinator.forecast_tracker = tracker

    # Fetch PVGIS monthly baselines for seasonal correction
    from .pvgis_client import fetch_pvgis_monthly
    pvgis_data = await fetch_pvgis_monthly(hass, hass.config.latitude, hass.config.longitude)
    if pvgis_data:
        tracker.set_monthly_baselines(pvgis_data)

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register custom panel (sidebar page)
    from homeassistant.components.http import StaticPathConfig
    from homeassistant.components.frontend import async_register_built_in_panel
    frontend_path = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths([
        StaticPathConfig(f"/{DOMAIN}/panel", str(frontend_path), cache_headers=False),
        StaticPathConfig(
            f"/{DOMAIN}/appliance-advisor-card.js",
            str(Path(__file__).parent / "frontend" / "appliance-advisor-card.js"),
            cache_headers=True,
        ),
    ])
    async_register_built_in_panel(
        hass,
        component_name="custom",
        frontend_url_path=DOMAIN,
        sidebar_title="Tesla Solar",
        sidebar_icon="mdi:solar-power",
        require_admin=False,
        config={
            "_panel_custom": {
                "name": "tesla-solar-charging-panel",
                "module_url": f"/{DOMAIN}/panel/panel.js?v={VERSION}",
                "embed_iframe": False,
                "trust_external": False,
            },
            "entry_id": entry.entry_id,
        },
    )

    # Fetch forecast on startup (don't send notification, just populate sensors)
    async def _startup_forecast(now=None):
        await _update_forecast(hass, coordinator, data)

    if hass.is_running:
        # Integration reloaded after HA already started — fetch immediately
        hass.async_create_task(_startup_forecast())
    else:
        entry.async_on_unload(
            hass.bus.async_listen_once("homeassistant_started", _startup_forecast)
        )

    # Schedule evening planner
    planning_time = data.get(CONF_PLANNING_TIME, DEFAULT_PLANNING_TIME)
    hour, minute = (int(x) for x in planning_time.split(":"))

    async def _run_planner(now):
        await _execute_planner(hass, coordinator, data)

    unsub_planner = async_track_time_change(
        hass, _run_planner, hour=hour, minute=minute, second=0
    )

    # Listen for Telegram callbacks
    @callback
    def _handle_telegram_callback(event):
        callback_data = event.data.get("data", "")
        chat_id = data.get(CONF_TELEGRAM_CHAT_ID)

        if callback_data == CALLBACK_CHARGE_TONIGHT:
            hass.async_create_task(_apply_plan(hass, coordinator, data, charge=True, chat_id=chat_id))
        elif callback_data == CALLBACK_SKIP_CHARGE:
            hass.async_create_task(_apply_plan(hass, coordinator, data, charge=False, chat_id=chat_id))

    unsub_telegram = hass.bus.async_listen("telegram_callback", _handle_telegram_callback)

    # Store cleanup functions
    entry.async_on_unload(unsub_planner)
    entry.async_on_unload(unsub_telegram)

    # Schedule daily actual production capture at 21:00
    daily_prod_entity = data.get(CONF_DAILY_PRODUCTION_ENTITY)
    if daily_prod_entity and hasattr(coordinator, 'forecast_tracker'):
        async def _capture_actual(now):
            state = hass.states.get(daily_prod_entity)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    actual = float(state.state)
                    today = datetime.now().strftime("%Y-%m-%d")
                    await coordinator.forecast_tracker.record_actual(today, actual)
                except (ValueError, TypeError):
                    _LOGGER.warning("Could not read daily production from %s", daily_prod_entity)

        unsub_capture = async_track_time_change(
            hass, _capture_actual, hour=21, minute=0, second=0
        )
        entry.async_on_unload(unsub_capture)

    # Schedule daily charging report at 21:30
    async def _send_daily_report(now):
        chat_id = data.get(CONF_TELEGRAM_CHAT_ID)
        if not chat_id:
            return
        from .notification import format_daily_report, send_alert_notification
        actual_prod = 0.0
        daily_prod_entity = data.get(CONF_DAILY_PRODUCTION_ENTITY)
        if daily_prod_entity:
            state = hass.states.get(daily_prod_entity)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    actual_prod = float(state.state)
                except (ValueError, TypeError):
                    pass
        msg = format_daily_report(
            solar_kwh=coordinator.daily_solar_kwh,
            grid_kwh=coordinator.daily_grid_kwh,
            total_kwh=coordinator.daily_solar_kwh + coordinator.daily_grid_kwh,
            peak_amps=coordinator._daily_peak_amps,
            hours_charged=coordinator._daily_charge_seconds / 3600,
            forecast_kwh=coordinator.forecast_kwh,
            actual_production_kwh=actual_prod,
        )
        await send_alert_notification(hass, int(chat_id), msg)
        coordinator.reset_daily_stats()

    unsub_report = async_track_time_change(
        hass, _send_daily_report, hour=21, minute=30, second=0
    )
    entry.async_on_unload(unsub_report)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _update_forecast(hass: HomeAssistant, coordinator: SolarChargingCoordinator, data: dict) -> None:
    """Fetch forecast from multiple sources, blend, and update coordinator sensors."""
    lat = hass.config.latitude
    lon = hass.config.longitude
    sources: list[ForecastSource] = []

    # Source 1: Open-Meteo (always available)
    forecast = await fetch_solar_forecast(hass, lat, lon)
    if forecast and "tomorrow" in forecast:
        from .weather_forecast import estimate_solar_production
        tomorrow = forecast["tomorrow"]
        perf_ratio = data.get(CONF_PERFORMANCE_RATIO, DEFAULT_PERFORMANCE_RATIO)
        correction = 1.0
        if hasattr(coordinator, 'forecast_tracker') and coordinator.forecast_tracker:
            correction = coordinator.forecast_tracker.seasonal_correction_factor
        production = estimate_solar_production(
            tomorrow["radiation_kwh_m2"],
            data.get(CONF_PV_SYSTEM_KWP, 6.0),
            performance_ratio=perf_ratio,
            correction_factor=correction,
        )
        sources.append(ForecastSource(name="open_meteo", production_kwh=production))
        # Record to tracker
        if hasattr(coordinator, 'forecast_tracker') and coordinator.forecast_tracker:
            tomorrow_date = tomorrow.get("date", "")
            if tomorrow_date:
                coordinator.forecast_tracker.record_forecast(
                    tomorrow_date,
                    tomorrow["radiation_kwh_m2"],
                    production,
                    tomorrow.get("sunshine_hours", 0),
                    perf_ratio,
                )

    # Source 2: Solcast (if configured)
    solcast_key = data.get(CONF_SOLCAST_API_KEY)
    solcast_rid = data.get(CONF_SOLCAST_RESOURCE_ID)
    if solcast_key and solcast_rid:
        from .solcast_client import fetch_solcast_forecast
        solcast = await fetch_solcast_forecast(hass, solcast_key, solcast_rid)
        if solcast and len(solcast) >= 2:
            tomorrow_sc = solcast[1]
            sources.append(ForecastSource(
                name="solcast",
                production_kwh=tomorrow_sc.production_kwh_p50,
                weight=1.5,
                pessimistic_kwh=tomorrow_sc.production_kwh_p10,
            ))

    # Source 3: Forecast.Solar (if enabled)
    if data.get(CONF_FORECAST_SOLAR_ENABLED):
        from .forecast_solar_client import fetch_forecast_solar
        fc_solar = await fetch_forecast_solar(
            hass,
            lat,
            lon,
            data.get(CONF_FORECAST_SOLAR_DECLINATION, DEFAULT_FORECAST_SOLAR_DECLINATION),
            data.get(CONF_FORECAST_SOLAR_AZIMUTH, DEFAULT_FORECAST_SOLAR_AZIMUTH),
            data.get(CONF_PV_SYSTEM_KWP, 6.0),
        )
        if fc_solar and len(fc_solar) >= 2:
            sources.append(ForecastSource(
                name="forecast_solar",
                production_kwh=fc_solar[1].production_kwh,
            ))

    # Blend all sources
    blended = blend_forecasts(sources)
    coordinator.forecast_kwh = blended.blended_kwh
    coordinator._forecast_pessimistic_kwh = blended.pessimistic_kwh
    coordinator._forecast_sources = [
        {
            "name": s.name,
            "production_kwh": round(s.production_kwh, 1),
            "weight": s.weight,
            "pessimistic_kwh": round(s.pessimistic_kwh, 1) if s.pessimistic_kwh else None,
        }
        for s in blended.sources
    ]
    _LOGGER.info(
        "Forecast updated: %.1f kWh (blended from %d sources)",
        blended.blended_kwh,
        len(sources),
    )

    # Hourly cloud forecast
    if data.get(CONF_HOURLY_FORECAST_ENABLED, True):
        from .weather_forecast import fetch_hourly_solar_forecast
        hourly = await fetch_hourly_solar_forecast(hass, lat, lon)
        if hourly:
            today_str = datetime.now().strftime("%Y-%m-%d")
            tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            if today_str in hourly:
                coordinator.cloud_strategy = hourly[today_str].cloud_strategy
                coordinator.best_charging_window = hourly[today_str].best_window_desc
            elif tomorrow_str in hourly:
                coordinator.cloud_strategy = hourly[tomorrow_str].cloud_strategy
                coordinator.best_charging_window = hourly[tomorrow_str].best_window_desc


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    from .const import CONF_ENTRY_TYPE, ENTRY_TYPE_ADVISOR

    entry_type = entry.data.get(CONF_ENTRY_TYPE)

    if entry_type == ENTRY_TYPE_ADVISOR:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
        if unload_ok:
            hass.data[DOMAIN].pop(entry.entry_id, None)
        # Only remove service if no other advisor entries remain
        advisor_entries = [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if e.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_ADVISOR and e.entry_id != entry.entry_id
        ]
        if not advisor_entries:
            hass.services.async_remove(DOMAIN, "set_appliance_deadline")
        return unload_ok

    # Charging entry
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    from homeassistant.components.frontend import async_remove_panel
    async_remove_panel(hass, DOMAIN)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _execute_planner(hass: HomeAssistant, coordinator: SolarChargingCoordinator, data: dict) -> None:
    """Run the evening planning decision."""
    _LOGGER.info("Running evening charge planner")

    lat = hass.config.latitude
    lon = hass.config.longitude

    # Fetch weather forecast
    forecast = await fetch_solar_forecast(hass, lat, lon)
    if not forecast or "tomorrow" not in forecast:
        _LOGGER.error("Failed to fetch forecast, defaulting to night charge")
        coordinator.night_charge_planned = True
        coordinator.plan_message = "Forecast unavailable — charging tonight as precaution"
        return

    tomorrow = forecast["tomorrow"]

    # Read Tesla SOC from configured sensor
    tesla_soc = 50.0
    if data.get(CONF_TESLA_BATTERY_ENTITY):
        state = hass.states.get(data[CONF_TESLA_BATTERY_ENTITY])
        if state and state.state not in ("unknown", "unavailable"):
            try:
                tesla_soc = float(state.state)
            except (ValueError, TypeError):
                pass

    # Read charge limit from integration's own number entity
    from homeassistant.helpers import entity_registry as er
    registry = er.async_get(hass)
    entry_id = coordinator._entry_id
    target_soc = 80.0
    charge_limit_entity = registry.async_get_entity_id("number", DOMAIN, f"{entry_id}_charge_limit")
    if charge_limit_entity:
        state = hass.states.get(charge_limit_entity)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                target_soc = float(state.state)
            except (ValueError, TypeError):
                pass

    home_battery_soc = 50.0
    if data.get(CONF_BATTERY_SOC_ENTITY):
        state = hass.states.get(data[CONF_BATTERY_SOC_ENTITY])
        if state and state.state not in ("unknown", "unavailable"):
            try:
                home_battery_soc = float(state.state)
            except (ValueError, TypeError):
                pass

    # Get weather-aware correction factor from forecast tracker
    cloud_category = getattr(coordinator, 'cloud_strategy', "")
    if cloud_category and cloud_category != "unknown" and hasattr(coordinator, 'forecast_tracker') and coordinator.forecast_tracker:
        correction_factor = coordinator.forecast_tracker.correction_factor_for_weather(cloud_category)
    elif hasattr(coordinator, 'forecast_tracker') and coordinator.forecast_tracker:
        correction_factor = coordinator.forecast_tracker.seasonal_correction_factor
    else:
        correction_factor = 1.0

    # Create plan
    plan = create_charge_plan(
        tesla_soc=tesla_soc,
        target_soc=target_soc,
        tesla_battery_kwh=data.get(CONF_TESLA_BATTERY_KWH, DEFAULT_TESLA_BATTERY_KWH),
        forecast_radiation_kwh_m2=tomorrow["radiation_kwh_m2"],
        sunshine_hours=tomorrow["sunshine_hours"],
        pv_system_kwp=data.get(CONF_PV_SYSTEM_KWP, 6.0),
        home_battery_kwh=data.get(CONF_HOME_BATTERY_KWH, 10.0),
        home_battery_soc=home_battery_soc,
        avg_house_consumption_kwh=data.get(CONF_AVG_HOUSE_CONSUMPTION_KWH, DEFAULT_AVG_HOUSE_CONSUMPTION_KWH),
        correction_factor=correction_factor,
        safety_margin=data.get(CONF_PLANNER_SAFETY_MARGIN, DEFAULT_PLANNER_SAFETY_MARGIN),
    )

    coordinator.forecast_kwh = plan.forecast_production_kwh
    coordinator.plan_message = plan.reason

    # Send notification
    chat_id = data.get(CONF_TELEGRAM_CHAT_ID)
    if chat_id:
        await send_plan_notification(hass, int(chat_id), plan)

    # Auto-execute after 30 minutes if no response
    async def _auto_execute(now):
        if coordinator.state in (STATE_PLANNED_NIGHT, STATE_PLANNED_SOLAR):
            # No override received — execute the plan
            await _apply_plan(hass, coordinator, data, charge=plan.charge_tonight, chat_id=chat_id)

    from homeassistant.helpers.event import async_call_later
    async_call_later(hass, 30 * 60, _auto_execute)

    # Set planned state (will be overridden by auto-execute or callback)
    coordinator.night_charge_planned = plan.charge_tonight


async def _apply_plan(hass: HomeAssistant, coordinator: SolarChargingCoordinator, data: dict, charge: bool, chat_id: int | None) -> None:
    """Apply the charging decision — enable/disable Octopus smart charge."""
    octopus_entity = data.get(CONF_OCTOPUS_SMART_CHARGE_ENTITY) if data.get(CONF_OCTOPUS_ENABLED, False) else None

    # Build Octopus client if enabled and credentials are available
    octopus_client = None
    if data.get(CONF_OCTOPUS_ENABLED, False) and data.get(CONF_OCTOPUS_EMAIL) and data.get(CONF_OCTOPUS_PASSWORD) and data.get(CONF_OCTOPUS_DEVICE_ID):
        octopus_client = OctopusItalyClient(
            data[CONF_OCTOPUS_EMAIL],
            data[CONF_OCTOPUS_PASSWORD],
            data[CONF_OCTOPUS_DEVICE_ID],
        )

    if charge:
        coordinator.night_charge_planned = True
        if octopus_entity:
            await hass.services.async_call(
                "switch", "turn_on",
                {"entity_id": octopus_entity},
                blocking=True,
            )
        elif octopus_client:
            try:
                await octopus_client.enable_smart_charge()
            except Exception as err:
                _LOGGER.error("Octopus API enable failed: %s", err)
        msg = "Night charging ENABLED — Octopus will schedule overnight charging."
        _LOGGER.info(msg)
    else:
        coordinator.night_charge_planned = False
        if octopus_entity:
            await hass.services.async_call(
                "switch", "turn_off",
                {"entity_id": octopus_entity},
                blocking=True,
            )
        elif octopus_client:
            try:
                await octopus_client.disable_smart_charge()
            except Exception as err:
                _LOGGER.error("Octopus API disable failed: %s", err)
        msg = "Night charging SKIPPED — relying on solar tomorrow."
        _LOGGER.info(msg)

    if chat_id:
        await send_action_notification(hass, int(chat_id), msg)
