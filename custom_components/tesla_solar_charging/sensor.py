"""Sensor entities for solar charging state."""

import json

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_BATTERY_SOC_THRESHOLD,
    CONF_HOME_BATTERY_KWH,
    CONF_MIN_EXPORT_POWER,
    CONF_MAX_CHARGING_AMPS,
    CONF_SAFETY_BUFFER_AMPS,
    CONF_BATTERY_DISCHARGE_THRESHOLD,
    CONF_LOW_AMP_STOP_COUNT,
    CONF_GRID_POWER_LIMIT,
    CONF_TESLA_BATTERY_KWH,
    CONF_TESLA_BATTERY_ENTITY,
    DEFAULT_BATTERY_SOC_THRESHOLD,
    DEFAULT_MIN_EXPORT_POWER,
    DEFAULT_MAX_CHARGING_AMPS,
    DEFAULT_SAFETY_BUFFER_AMPS,
    DEFAULT_BATTERY_DISCHARGE_THRESHOLD,
    DEFAULT_LOW_AMP_STOP_COUNT,
    DEFAULT_GRID_POWER_LIMIT,
    DEFAULT_TESLA_BATTERY_KWH,
    DOMAIN,
)
from .coordinator import SolarChargingCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from config entry."""
    from .const import CONF_ENTRY_TYPE, ENTRY_TYPE_ADVISOR

    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Advisor entry only creates advisor sensors
    if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_ADVISOR:
        from .appliance_advisor.sensor import async_setup_advisor_sensors
        await async_setup_advisor_sensors(hass, entry, async_add_entities, coordinator)
        return

    # Charging entry creates the standard sensors
    async_add_entities([
        StateSensor(coordinator, entry),
        AmpsSensor(coordinator, entry),
        NetAvailableSensor(coordinator, entry),
        ReasonSensor(coordinator, entry),
        ForecastSensor(coordinator, entry),
        PlanSensor(coordinator, entry),
        ForecastAccuracySensor(coordinator, entry),
        BLEStatusSensor(coordinator, entry),
        CloudStrategySensor(coordinator, entry),
        DebugSensor(coordinator, entry),
    ])


def _eta_minutes(current_pct, target_pct, capacity_kwh, power_w):
    """Estimate minutes to go from current_pct to target_pct at given power."""
    if power_w <= 0 or current_pct >= target_pct:
        return None
    kwh_needed = capacity_kwh * (target_pct - current_pct) / 100
    hours = kwh_needed / (power_w / 1000)
    return round(hours * 60, 0)


class StateSensor(CoordinatorEntity, SensorEntity):
    """Current charging controller state."""

    _attr_has_entity_name = True
    _attr_name = "State"
    _attr_icon = "mdi:state-machine"

    def __init__(self, coordinator: SolarChargingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_state"

    @property
    def native_value(self) -> str:
        return self.coordinator.state

    @property
    def extra_state_attributes(self) -> dict:
        c = self.coordinator
        data = c._entry_data
        bat_soc = c._last_battery_soc
        bat_thresh = data.get(CONF_BATTERY_SOC_THRESHOLD, DEFAULT_BATTERY_SOC_THRESHOLD)
        bat_kwh = data.get(CONF_HOME_BATTERY_KWH, 10.0)
        bat_power = c._last_battery_power
        tesla_kwh = data.get(CONF_TESLA_BATTERY_KWH, DEFAULT_TESLA_BATTERY_KWH)
        voltage = c._last_grid_voltage or 230

        # Home battery ETA: charging power = negative battery_power
        home_bat_charge_w = max(0, -bat_power) if bat_power < 0 else 0
        home_bat_eta = _eta_minutes(bat_soc, bat_thresh, bat_kwh, home_bat_charge_w)

        # Tesla ETA: based on current charging amps
        tesla_soc = None
        if data.get(CONF_TESLA_BATTERY_ENTITY):
            state = c.hass.states.get(data[CONF_TESLA_BATTERY_ENTITY])
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    tesla_soc = float(state.state)
                except (ValueError, TypeError):
                    pass
        tesla_limit = c._get_own_float("charge_limit")
        tesla_charge_w = c.current_amps * voltage if c.current_amps > 0 else 0
        tesla_eta = None
        if tesla_soc is not None and tesla_limit is not None:
            tesla_eta = _eta_minutes(tesla_soc, tesla_limit, tesla_kwh, tesla_charge_w)

        attrs = {
            "enabled": c.enabled,
            "force_charge": c.force_charge,
            "night_mode_active": c._night_mode_active,
            "night_charge_planned": c.night_charge_planned,
            "low_amp_count": c._low_amp_count,
            # Home battery
            "battery_soc": bat_soc,
            "battery_soc_threshold": bat_thresh,
            "battery_power_w": bat_power,
            "home_battery_eta_min": home_bat_eta,
            "battery_discharge_threshold_w": data.get(CONF_BATTERY_DISCHARGE_THRESHOLD, DEFAULT_BATTERY_DISCHARGE_THRESHOLD),
            # Tesla
            "tesla_soc": tesla_soc,
            "tesla_charge_limit": tesla_limit,
            "tesla_charge_power_w": tesla_charge_w,
            "tesla_eta_min": tesla_eta,
            # Grid
            "grid_power_w": c._last_grid_power,
            "grid_voltage_v": voltage,
            # Config thresholds
            "min_export_power_w": data.get(CONF_MIN_EXPORT_POWER, DEFAULT_MIN_EXPORT_POWER),
            "max_charging_amps": data.get(CONF_MAX_CHARGING_AMPS, DEFAULT_MAX_CHARGING_AMPS),
            "safety_buffer_amps": data.get(CONF_SAFETY_BUFFER_AMPS, DEFAULT_SAFETY_BUFFER_AMPS),
            "low_amp_stop_count": data.get(CONF_LOW_AMP_STOP_COUNT, DEFAULT_LOW_AMP_STOP_COUNT),
            "grid_power_limit_w": data.get(CONF_GRID_POWER_LIMIT, DEFAULT_GRID_POWER_LIMIT),
            # Daily stats
            "daily_solar_kwh": c.daily_solar_kwh,
            "daily_grid_kwh": c.daily_grid_kwh,
            "daily_peak_amps": c._daily_peak_amps,
            "daily_charge_minutes": round(c._daily_charge_seconds / 60, 1),
        }
        return attrs


class AmpsSensor(CoordinatorEntity, SensorEntity):
    """Current charging amps being set."""

    _attr_has_entity_name = True
    _attr_name = "Charging Amps"
    _attr_icon = "mdi:current-ac"
    _attr_native_unit_of_measurement = "A"

    def __init__(self, coordinator: SolarChargingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_amps"

    @property
    def native_value(self) -> int:
        return self.coordinator.current_amps


class NetAvailableSensor(CoordinatorEntity, SensorEntity):
    """Net available amps from solar."""

    _attr_has_entity_name = True
    _attr_name = "Net Available"
    _attr_icon = "mdi:solar-power-variant"
    _attr_native_unit_of_measurement = "A"

    def __init__(self, coordinator: SolarChargingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_net_available"

    @property
    def native_value(self) -> float:
        return round(self.coordinator.net_available, 1)

    @property
    def extra_state_attributes(self) -> dict:
        c = self.coordinator
        v = c._last_grid_voltage or 230
        return {
            "grid_export_amps": round(-c._last_grid_power / v, 1) if c._last_grid_power < 0 else 0,
            "battery_discharge_amps": round(c._last_battery_power / v, 1) if c._last_battery_power > 0 else 0,
            "safety_buffer_amps": c._entry_data.get(CONF_SAFETY_BUFFER_AMPS, DEFAULT_SAFETY_BUFFER_AMPS),
        }


class ReasonSensor(CoordinatorEntity, SensorEntity):
    """Human-readable reason for last action."""

    _attr_has_entity_name = True
    _attr_name = "Reason"
    _attr_icon = "mdi:information-outline"

    def __init__(self, coordinator: SolarChargingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_reason"

    @property
    def native_value(self) -> str:
        return self.coordinator.reason


class ForecastSensor(CoordinatorEntity, SensorEntity):
    """Tomorrow's estimated solar production."""

    _attr_has_entity_name = True
    _attr_name = "Solar Forecast"
    _attr_icon = "mdi:weather-sunny"
    _attr_native_unit_of_measurement = "kWh"

    def __init__(self, coordinator: SolarChargingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_forecast"

    @property
    def native_value(self) -> float:
        return self.coordinator.forecast_kwh

    @property
    def extra_state_attributes(self) -> dict:
        c = self.coordinator
        attrs = {
            "blended_kwh": c.forecast_kwh,
            "today_kwh": c._forecast_today_kwh,
            "pessimistic_kwh": c._forecast_pessimistic_kwh,
            "sources": c._forecast_sources,
            "low_solar_warning": c.low_solar_warning,
            "multi_day_outlook": c.multi_day_outlook,
            "hourly_forecast": c._hourly_forecast_today,
        }
        tracker = getattr(c, 'forecast_tracker', None)
        if tracker:
            attrs["correction_factor"] = tracker.correction_factor
            attrs["seasonal_correction_factor"] = tracker.seasonal_correction_factor
            if tracker._monthly_baselines:
                attrs["pvgis_monthly_baselines"] = tracker._monthly_baselines
        return attrs


class PlanSensor(CoordinatorEntity, SensorEntity):
    """Current charging plan."""

    _attr_has_entity_name = True
    _attr_name = "Plan"
    _attr_icon = "mdi:clipboard-text"

    def __init__(self, coordinator: SolarChargingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_plan"

    @property
    def native_value(self) -> str:
        if self.coordinator.night_charge_planned:
            return "Night charge planned"
        return "Solar only"

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "detail": self.coordinator.plan_message or "No plan yet (runs at planning time)",
        }


class ForecastAccuracySensor(CoordinatorEntity, SensorEntity):
    """Forecast accuracy correction factor."""

    _attr_has_entity_name = True
    _attr_name = "Forecast Accuracy"
    _attr_icon = "mdi:chart-line"

    def __init__(self, coordinator: SolarChargingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_forecast_accuracy"

    @property
    def native_value(self) -> float:
        tracker = getattr(self.coordinator, 'forecast_tracker', None)
        if tracker:
            return tracker.correction_factor
        return 1.0

    @property
    def extra_state_attributes(self) -> dict:
        tracker = getattr(self.coordinator, 'forecast_tracker', None)
        if tracker:
            return tracker.stats
        return {}


class BLEStatusSensor(CoordinatorEntity, SensorEntity):
    """ESP32 / BLE connection health status."""

    _attr_has_entity_name = True
    _attr_name = "BLE Status"
    _attr_icon = "mdi:bluetooth-connect"

    def __init__(self, coordinator: SolarChargingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_ble_status"

    @property
    def native_value(self) -> str:
        return self.coordinator.ble_status

    @property
    def icon(self) -> str:
        status = self.coordinator.ble_status
        if status == "ok":
            return "mdi:bluetooth-connect"
        if status == "esp32_offline":
            return "mdi:bluetooth-off"
        return "mdi:bluetooth-settings"

    @property
    def extra_state_attributes(self) -> dict:
        ble = self.coordinator._ble
        return {
            "detail": self.coordinator.ble_status_detail,
            "consecutive_failures": ble.consecutive_failures,
            "charger_switch": ble.charger_switch,
            "charging_amps": ble.charging_amps,
            "wake_button": ble.wake_button,
        }


class CloudStrategySensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Cloud Strategy"
    _attr_icon = "mdi:weather-partly-cloudy"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_cloud_strategy"

    @property
    def native_value(self):
        return self.coordinator.cloud_strategy

    @property
    def icon(self):
        icons = {"clear": "mdi:weather-sunny", "partly_cloudy": "mdi:weather-partly-cloudy",
                 "mostly_cloudy": "mdi:weather-cloudy", "overcast": "mdi:weather-fog"}
        return icons.get(self.coordinator.cloud_strategy, "mdi:weather-partly-cloudy")

    @property
    def extra_state_attributes(self):
        return {"best_charging_window": self.coordinator.best_charging_window}


class DebugSensor(CoordinatorEntity, SensorEntity):
    """Full debug dump — copy the JSON attribute to share for troubleshooting."""

    _attr_has_entity_name = True
    _attr_name = "Debug"
    _attr_icon = "mdi:bug"
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator: SolarChargingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_debug"

    @property
    def native_value(self) -> str:
        return self.coordinator.state

    @property
    def extra_state_attributes(self) -> dict:
        c = self.coordinator
        data = c._entry_data
        tracker = getattr(c, 'forecast_tracker', None)

        dump = {
            "version": data.get("version", "unknown"),
            "state": c.state,
            "reason": c.reason,
            "enabled": c.enabled,
            "force_charge": c.force_charge,
            "night_mode_active": c._night_mode_active,
            "night_charge_planned": c.night_charge_planned,
            "current_amps": c.current_amps,
            "net_available": round(c.net_available, 1),
            "low_amp_count": c._low_amp_count,
            # Sensors
            "grid_power_w": c._last_grid_power,
            "grid_voltage_v": c._last_grid_voltage,
            "battery_soc": c._last_battery_soc,
            "battery_power_w": c._last_battery_power,
            # Tesla
            "tesla_soc": None,
            "tesla_charge_limit": c._get_own_float("charge_limit"),
            # Forecast
            "forecast_kwh": c.forecast_kwh,
            "forecast_pessimistic_kwh": c._forecast_pessimistic_kwh,
            "forecast_sources": c._forecast_sources,
            "cloud_strategy": c.cloud_strategy,
            "best_charging_window": c.best_charging_window,
            "low_solar_warning": c.low_solar_warning,
            "multi_day_outlook": c.multi_day_outlook,
            # Accuracy
            "correction_factor": tracker.correction_factor if tracker else None,
            "seasonal_correction_factor": tracker.seasonal_correction_factor if tracker else None,
            "pvgis_baselines": tracker._monthly_baselines if tracker else None,
            "forecast_days_tracked": tracker.days_tracked if tracker else 0,
            # BLE
            "ble_status": c.ble_status,
            "ble_detail": c.ble_status_detail,
            "ble_failures": c._ble.consecutive_failures,
            # Config
            "config": {
                "min_export_power": data.get(CONF_MIN_EXPORT_POWER, DEFAULT_MIN_EXPORT_POWER),
                "max_charging_amps": data.get(CONF_MAX_CHARGING_AMPS, DEFAULT_MAX_CHARGING_AMPS),
                "safety_buffer_amps": data.get(CONF_SAFETY_BUFFER_AMPS, DEFAULT_SAFETY_BUFFER_AMPS),
                "battery_soc_threshold": data.get(CONF_BATTERY_SOC_THRESHOLD, DEFAULT_BATTERY_SOC_THRESHOLD),
                "low_amp_stop_count": data.get(CONF_LOW_AMP_STOP_COUNT, DEFAULT_LOW_AMP_STOP_COUNT),
                "grid_power_limit": data.get(CONF_GRID_POWER_LIMIT, DEFAULT_GRID_POWER_LIMIT),
                "battery_discharge_threshold": data.get(CONF_BATTERY_DISCHARGE_THRESHOLD, DEFAULT_BATTERY_DISCHARGE_THRESHOLD),
                "home_battery_kwh": data.get(CONF_HOME_BATTERY_KWH, 10.0),
                "tesla_battery_kwh": data.get(CONF_TESLA_BATTERY_KWH, DEFAULT_TESLA_BATTERY_KWH),
            },
            # Daily stats
            "daily_solar_kwh": c.daily_solar_kwh,
            "daily_grid_kwh": c.daily_grid_kwh,
            "daily_peak_amps": c._daily_peak_amps,
            "daily_charge_minutes": round(c._daily_charge_seconds / 60, 1),
            # Plan
            "plan_message": c.plan_message,
        }

        # Fill Tesla SOC from sensor
        if data.get(CONF_TESLA_BATTERY_ENTITY):
            state = c.hass.states.get(data[CONF_TESLA_BATTERY_ENTITY])
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    dump["tesla_soc"] = float(state.state)
                except (ValueError, TypeError):
                    pass

        return {"json": json.dumps(dump, indent=2, default=str)}
