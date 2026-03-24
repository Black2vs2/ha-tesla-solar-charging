"""Switch entity to enable/disable solar charging."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolarChargingCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        SolarChargingSwitch(coordinator, entry),
        ForceChargeSwitch(coordinator, entry),
    ])


class SolarChargingSwitch(RestoreEntity, CoordinatorEntity, SwitchEntity):
    """Switch to enable/disable solar charging controller.

    Persists state across HA restarts.
    """

    _attr_has_entity_name = True
    _attr_name = "Solar Charging"
    _attr_icon = "mdi:solar-power"

    def __init__(self, coordinator: SolarChargingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_switch"

    async def async_added_to_hass(self) -> None:
        """Restore previous on/off state."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state == "on":
            self.coordinator.enabled = True

    @property
    def is_on(self) -> bool:
        return self.coordinator.enabled

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.enabled = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.enabled = False
        self.async_write_ha_state()


class ForceChargeSwitch(CoordinatorEntity, SwitchEntity):
    """Force charge — bypass battery SOC threshold for this session.

    Auto-resets when the car is unplugged and replugged.
    """

    _attr_has_entity_name = True
    _attr_name = "Force Charge"
    _attr_icon = "mdi:flash-alert"

    def __init__(self, coordinator: SolarChargingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_force_charge"

    @property
    def is_on(self) -> bool:
        return self.coordinator.force_charge

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.force_charge = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.force_charge = False
        self.async_write_ha_state()
