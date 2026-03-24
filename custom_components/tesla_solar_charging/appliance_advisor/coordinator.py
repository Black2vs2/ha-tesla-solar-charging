"""Coordinator for the Appliance Advisor — 30s update cycle."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..const import (
    CONF_ADVISOR_BATTERY_POWER_ENTITY,
    CONF_ADVISOR_BATTERY_SOC_ENTITY,
    CONF_ADVISOR_GRID_POWER_ENTITY,
    CONF_ADVISOR_GRID_VOLTAGE_ENTITY,
)
from . import evaluate_all

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = 30  # seconds


class AdvisorCoordinator(DataUpdateCoordinator):
    """Coordinator that evaluates appliance recommendations every 30s."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        entry_data: dict,
        deadline_store,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="appliance_advisor",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self._entry_id = entry_id
        self._entry_data = entry_data
        self._deadline_store = deadline_store
        self._advisor_recommendations: dict | None = None

    @property
    def advisor_recommendations(self):
        return self._advisor_recommendations

    def _get_float(self, entity_id: str) -> float | None:
        """Read a float sensor value, returning None if unavailable."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    async def _async_update_data(self) -> dict:
        """Read sensors and evaluate all appliances."""
        grid_power = self._get_float(self._entry_data.get(CONF_ADVISOR_GRID_POWER_ENTITY, ""))
        grid_voltage = self._get_float(self._entry_data.get(CONF_ADVISOR_GRID_VOLTAGE_ENTITY, ""))

        if grid_power is None or grid_voltage is None:
            return {}

        batt_soc = self._get_float(self._entry_data.get(CONF_ADVISOR_BATTERY_SOC_ENTITY, "")) or 0.0
        batt_power = self._get_float(self._entry_data.get(CONF_ADVISOR_BATTERY_POWER_ENTITY, "")) or 0.0

        deadline_data = self._deadline_store.get_all() if self._deadline_store else {}

        try:
            self._advisor_recommendations = evaluate_all(
                self.hass,
                self._entry_data,
                grid_power, grid_voltage,
                batt_soc, batt_power,
                current_amps=0.0,  # Advisor doesn't know about Tesla charging
                deadline_data=deadline_data,
            )
        except Exception:
            _LOGGER.exception("Advisor evaluation failed")

        return {}
