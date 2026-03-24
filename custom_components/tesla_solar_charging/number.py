"""Number entities for Tesla charging parameters."""

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_BLE_CHARGE_LIMIT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities from config entry."""
    data = {**entry.data, **entry.options}
    async_add_entities([
        TeslaChargeLimitNumber(entry, data.get(CONF_BLE_CHARGE_LIMIT)),
    ])


class TeslaChargeLimitNumber(RestoreEntity, NumberEntity):
    """Tesla charge limit percentage."""

    _attr_has_entity_name = True
    _attr_name = "Tesla Charge Limit"
    _attr_icon = "mdi:battery-lock"
    _attr_native_min_value = 50
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.SLIDER

    def __init__(self, entry: ConfigEntry, ble_entity: str | None = None) -> None:
        self._attr_unique_id = f"{entry.entry_id}_charge_limit"
        self._attr_native_value = 80.0
        self._ble_entity = ble_entity

    async def async_added_to_hass(self) -> None:
        """Restore last value on startup."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self._attr_native_value = float(last_state.state)
            except (ValueError, TypeError):
                pass

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
        # Push to Tesla via BLE
        if self._ble_entity:
            try:
                await self.hass.services.async_call(
                    "number", "set_value",
                    {"entity_id": self._ble_entity, "value": int(value)},
                    blocking=True,
                )
                _LOGGER.info("Set Tesla charge limit to %d%% via BLE", int(value))
            except Exception as err:
                _LOGGER.error("Failed to set charge limit via BLE: %s", err)
