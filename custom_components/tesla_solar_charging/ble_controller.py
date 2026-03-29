"""BLE Controller — wraps HA service calls to ESPHome Tesla BLE entities."""

import logging

from homeassistant.core import HomeAssistant

from .const import (
    BLE_MAX_CONSECUTIVE_FAILURES,
    BLE_STATUS_BLE_ERROR,
    BLE_STATUS_ESP32_OFFLINE,
    BLE_STATUS_OK,
    BLE_STATUS_UNKNOWN,
)

_LOGGER = logging.getLogger(__name__)


class BLEController:
    """Controls Tesla charging via ESPHome BLE entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        charger_switch: str,
        charging_amps: str,
        wake_button: str,
        polling_mode_entity: str | None = None,
    ) -> None:
        self.hass = hass
        self.charger_switch = charger_switch
        self.charging_amps = charging_amps
        self.wake_button = wake_button
        self.polling_mode_entity = polling_mode_entity
        self._consecutive_failures = 0
        self._last_error: str | None = None

    @property
    def entity_ids(self) -> list[str]:
        """All BLE entity IDs this controller depends on."""
        return [self.charger_switch, self.charging_amps, self.wake_button]

    @property
    def status(self) -> str:
        """Current health status of the BLE/ESP32 connection."""
        if not self._are_entities_available():
            return BLE_STATUS_ESP32_OFFLINE
        if self._consecutive_failures >= BLE_MAX_CONSECUTIVE_FAILURES:
            return BLE_STATUS_BLE_ERROR
        return BLE_STATUS_OK

    @property
    def status_detail(self) -> str:
        """Human-readable detail about current status."""
        status = self.status
        if status == BLE_STATUS_ESP32_OFFLINE:
            unavailable = [
                eid for eid in self.entity_ids
                if not self._is_entity_available(eid)
            ]
            return f"Entities unavailable: {', '.join(unavailable)}"
        if status == BLE_STATUS_BLE_ERROR:
            return f"{self._consecutive_failures} consecutive failures. Last: {self._last_error}"
        return "All entities available, commands succeeding"

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    @property
    def is_healthy(self) -> bool:
        """True if ESP32 is online and BLE commands are not persistently failing."""
        return self.status == BLE_STATUS_OK

    def _is_entity_available(self, entity_id: str) -> bool:
        state = self.hass.states.get(entity_id)
        return state is not None and state.state not in ("unavailable",)

    def _are_entities_available(self) -> bool:
        return all(self._is_entity_available(eid) for eid in self.entity_ids)

    def _record_success(self) -> None:
        if self._consecutive_failures > 0:
            _LOGGER.info("BLE command succeeded, clearing %d failure(s)", self._consecutive_failures)
        self._consecutive_failures = 0
        self._last_error = None

    def _record_failure(self, err: Exception) -> None:
        self._consecutive_failures += 1
        self._last_error = str(err)
        _LOGGER.warning(
            "BLE command failed (%d consecutive): %s",
            self._consecutive_failures, err,
        )

    async def start_charging(self) -> None:
        """Turn on the charger switch."""
        _LOGGER.info("Starting Tesla charging")
        try:
            await self.hass.services.async_call(
                "switch", "turn_on",
                {"entity_id": self.charger_switch},
                blocking=True,
            )
            self._record_success()
        except Exception as err:
            self._record_failure(err)
            raise

    async def stop_charging(self) -> None:
        """Turn off the charger switch."""
        _LOGGER.info("Stopping Tesla charging")
        try:
            await self.hass.services.async_call(
                "switch", "turn_off",
                {"entity_id": self.charger_switch},
                blocking=True,
            )
            self._record_success()
        except Exception as err:
            self._record_failure(err)
            raise

    async def set_charging_amps(self, amps: int) -> None:
        """Set the charging amps via number entity."""
        _LOGGER.info("Setting Tesla charging amps to %d", amps)
        try:
            await self.hass.services.async_call(
                "number", "set_value",
                {"entity_id": self.charging_amps, "value": amps},
                blocking=True,
            )
            self._record_success()
        except Exception as err:
            self._record_failure(err)
            raise

    async def wake(self) -> None:
        """Wake the vehicle via button press."""
        _LOGGER.info("Waking Tesla")
        try:
            await self.hass.services.async_call(
                "button", "press",
                {"entity_id": self.wake_button},
                blocking=True,
            )
            self._record_success()
        except Exception as err:
            self._record_failure(err)
            raise

    async def set_polling_mode(self, mode: str) -> None:
        if self.polling_mode_entity is None:
            return
        _LOGGER.info("Setting BLE polling mode to %s", mode)
        try:
            await self.hass.services.async_call(
                "select", "select_option",
                {"entity_id": self.polling_mode_entity, "option": mode},
                blocking=True,
            )
            self._record_success()
        except Exception as err:
            self._record_failure(err)
            raise
