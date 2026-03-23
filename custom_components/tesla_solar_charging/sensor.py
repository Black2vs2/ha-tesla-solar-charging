"""Sensor entities for solar charging state."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolarChargingCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
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
    ])


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
