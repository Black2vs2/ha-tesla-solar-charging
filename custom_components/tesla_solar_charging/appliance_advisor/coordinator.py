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
from . import evaluate_all, get_running_states, build_appliance_list

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
        run_history_store=None,
        appliance_store=None,
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
        self._run_history_store = run_history_store
        self._appliance_store = appliance_store
        self._advisor_recommendations: dict | None = None
        # Previous running states for transition detection
        self._prev_running: dict[str, bool] = {}

    @property
    def advisor_recommendations(self):
        return self._advisor_recommendations

    @property
    def run_history_store(self):
        return self._run_history_store

    @property
    def appliance_store(self):
        return self._appliance_store

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

        batt_soc = self._get_float(self._entry_data.get(CONF_ADVISOR_BATTERY_SOC_ENTITY, "")) or 0.0
        batt_power = self._get_float(self._entry_data.get(CONF_ADVISOR_BATTERY_POWER_ENTITY, "")) or 0.0

        deadline_data = self._deadline_store.get_all() if self._deadline_store else {}

        # Merge appliances: config entry + service-managed store
        merged_data = dict(self._entry_data)
        if self._appliance_store:
            store_appliances = self._appliance_store.get_all()
            if store_appliances:
                entry_appliances = dict(merged_data.get("appliances", {}))
                entry_appliances.update(store_appliances)
                merged_data["appliances"] = entry_appliances

        # Track running state transitions for run history
        if self._run_history_store:
            await self._track_run_history(merged_data)

        # Use 0.0 defaults if sensors unavailable — appliances still show with "red" status
        try:
            self._advisor_recommendations = evaluate_all(
                self.hass,
                merged_data,
                grid_power or 0.0, grid_voltage or 230.0,
                batt_soc, batt_power,
                current_amps=0.0,
                deadline_data=deadline_data,
                run_history_store=self._run_history_store,
            )
        except Exception:
            _LOGGER.exception("Advisor evaluation failed")

        return {}

    async def _track_run_history(self, merged_data: dict) -> None:
        """Detect running→stopped transitions and record runs."""
        appliances = build_appliance_list(merged_data)
        running_states = get_running_states(self.hass, appliances)

        for app in appliances:
            if app.power_entity is None:
                continue

            running_now, watts_now = running_states.get(app.key, (None, None))
            was_running = self._prev_running.get(app.key, False)

            if running_now and not was_running:
                # Transition: stopped → running — start tracking
                self._run_history_store.start_run(app.key, watts_now or 0)
                _LOGGER.debug("Run started: %s", app.key)
            elif running_now and was_running:
                # Still running — add power sample
                self._run_history_store.update_run(app.key, watts_now or 0)
            elif not running_now and was_running:
                # Transition: running → stopped — end run
                await self._run_history_store.end_run(app.key)
                _LOGGER.debug("Run ended: %s", app.key)

            if running_now is not None:
                self._prev_running[app.key] = bool(running_now)
