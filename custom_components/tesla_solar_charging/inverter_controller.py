"""Deye inverter mode controller via HA entities."""

import logging

from homeassistant.core import HomeAssistant

from .const import (
    DEYE_ENERGY_PATTERN_BATTERY_FIRST,
    DEYE_ENERGY_PATTERN_LOAD_FIRST,
)

_LOGGER = logging.getLogger(__name__)


class InverterController:
    """Controls Deye inverter modes via HA service calls."""

    def __init__(
        self,
        hass: HomeAssistant,
        work_mode_entity: str | None,
        energy_pattern_entity: str | None,
        battery_discharge_entity: str | None,
    ) -> None:
        self.hass = hass
        self.work_mode_entity = work_mode_entity
        self.energy_pattern_entity = energy_pattern_entity
        self.battery_discharge_entity = battery_discharge_entity
        self._saved_discharge_current: float | None = None

    async def set_night_mode(self) -> None:
        """Set inverter to night charging mode.

        - Energy pattern: Load first (don't discharge batteries for house)
        - Battery discharge: 0A (prevent any battery drain)
        """
        _LOGGER.info("Setting Deye inverter to night mode")

        if self.energy_pattern_entity:
            await self.hass.services.async_call(
                "select", "select_option",
                {
                    "entity_id": self.energy_pattern_entity,
                    "option": DEYE_ENERGY_PATTERN_LOAD_FIRST,
                },
                blocking=True,
            )

        if self.battery_discharge_entity:
            # Save current discharge setting before overriding
            state = self.hass.states.get(self.battery_discharge_entity)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    self._saved_discharge_current = float(state.state)
                except (ValueError, TypeError):
                    self._saved_discharge_current = None

            await self.hass.services.async_call(
                "number", "set_value",
                {"entity_id": self.battery_discharge_entity, "value": 0},
                blocking=True,
            )

    async def restore_day_mode(self) -> None:
        """Restore inverter to normal daytime mode.

        - Energy pattern: Battery first
        - Battery discharge: restored to previous value
        """
        _LOGGER.info("Restoring Deye inverter to day mode")

        if self.energy_pattern_entity:
            await self.hass.services.async_call(
                "select", "select_option",
                {
                    "entity_id": self.energy_pattern_entity,
                    "option": DEYE_ENERGY_PATTERN_BATTERY_FIRST,
                },
                blocking=True,
            )

        if self.battery_discharge_entity and self._saved_discharge_current is not None:
            await self.hass.services.async_call(
                "number", "set_value",
                {
                    "entity_id": self.battery_discharge_entity,
                    "value": self._saved_discharge_current,
                },
                blocking=True,
            )
            self._saved_discharge_current = None

    def is_night_mode(self) -> bool:
        """Check if inverter is currently in night mode."""
        if not self.energy_pattern_entity:
            return False
        state = self.hass.states.get(self.energy_pattern_entity)
        if state is None:
            return False
        return state.state == DEYE_ENERGY_PATTERN_LOAD_FIRST
