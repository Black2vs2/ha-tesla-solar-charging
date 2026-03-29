"""Tests for BLE polling: BLEController.set_polling_mode() and coordinator._determine_polling_mode()."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from tesla_solar_charging.ble_controller import BLEController
from tesla_solar_charging.coordinator import SolarChargingCoordinator
from tesla_solar_charging.const import (
    POLLING_MODE_ACTIVE,
    POLLING_MODE_CLOSE,
    POLLING_MODE_LAZY,
    POLLING_MODE_OFF,
    STATE_CHARGING_NIGHT,
    STATE_CHARGING_SOLAR,
    STATE_IDLE,
    STATE_WAITING,
)


def _make_controller(polling_mode_entity=None):
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.states.get = MagicMock(return_value=MagicMock(state="on"))
    ctrl = BLEController(
        hass=hass,
        charger_switch="switch.tesla_ble_charger",
        charging_amps="number.tesla_ble_charging_amps",
        wake_button="button.tesla_ble_wake_up",
        polling_mode_entity=polling_mode_entity,
    )
    return ctrl


class TestSetPollingMode:
    @pytest.mark.asyncio
    async def test_active_calls_correct_service(self):
        ctrl = _make_controller("select.tesla_ble_polling")
        await ctrl.set_polling_mode("active")
        ctrl.hass.services.async_call.assert_called_once_with(
            "select", "select_option",
            {"entity_id": "select.tesla_ble_polling", "option": "active"},
            blocking=True,
        )

    @pytest.mark.asyncio
    async def test_off_calls_correct_service(self):
        ctrl = _make_controller("select.tesla_ble_polling")
        await ctrl.set_polling_mode("off")
        ctrl.hass.services.async_call.assert_called_once_with(
            "select", "select_option",
            {"entity_id": "select.tesla_ble_polling", "option": "off"},
            blocking=True,
        )

    @pytest.mark.asyncio
    async def test_noop_when_entity_is_none(self):
        ctrl = _make_controller(polling_mode_entity=None)
        await ctrl.set_polling_mode("active")
        ctrl.hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_failure_increments_consecutive_failures(self):
        ctrl = _make_controller("select.tesla_ble_polling")
        ctrl.hass.services.async_call = AsyncMock(side_effect=Exception("BLE timeout"))
        assert ctrl.consecutive_failures == 0
        with pytest.raises(Exception, match="BLE timeout"):
            await ctrl.set_polling_mode("active")
        assert ctrl.consecutive_failures == 1


# --- Coordinator._determine_polling_mode() tests ---


def _make_coordinator(enabled=True, state=STATE_IDLE, force_charge=False,
                      is_home=True, tesla_soc=50.0, tesla_limit=80.0,
                      night_charge_planned=False):
    hass = MagicMock()
    ble = MagicMock()
    inverter = MagicMock()
    entry_data = {}
    coord = SolarChargingCoordinator(hass, "test_entry", entry_data, ble, inverter)
    coord._enabled = enabled
    coord._state = state
    coord._force_charge = force_charge
    coord._night_charge_planned = night_charge_planned
    coord._is_home = MagicMock(return_value=is_home)
    coord._last_tesla_soc = tesla_soc
    coord._last_tesla_limit = tesla_limit
    return coord


class TestDeterminePollingMode:
    def test_disabled_returns_off(self):
        coord = _make_coordinator(enabled=False)
        assert coord._determine_polling_mode(sun_up=True) == POLLING_MODE_OFF

    def test_night_not_charging_returns_off(self):
        coord = _make_coordinator(state=STATE_WAITING)
        assert coord._determine_polling_mode(sun_up=False) == POLLING_MODE_OFF

    def test_night_force_charge_far_from_limit_returns_active(self):
        coord = _make_coordinator(force_charge=True, tesla_soc=50.0, tesla_limit=80.0)
        assert coord._determine_polling_mode(sun_up=False) == POLLING_MODE_ACTIVE

    def test_night_force_charge_near_limit_returns_close(self):
        coord = _make_coordinator(force_charge=True, tesla_soc=79.0, tesla_limit=80.0)
        assert coord._determine_polling_mode(sun_up=False) == POLLING_MODE_CLOSE

    def test_night_charging_octopus_returns_active(self):
        coord = _make_coordinator(
            state=STATE_CHARGING_NIGHT, night_charge_planned=True,
            tesla_soc=50.0, tesla_limit=80.0,
        )
        assert coord._determine_polling_mode(sun_up=False) == POLLING_MODE_ACTIVE

    def test_car_not_home_returns_off(self):
        coord = _make_coordinator(is_home=False)
        assert coord._determine_polling_mode(sun_up=True) == POLLING_MODE_OFF

    def test_day_not_charging_returns_lazy(self):
        coord = _make_coordinator(state=STATE_WAITING)
        assert coord._determine_polling_mode(sun_up=True) == POLLING_MODE_LAZY

    def test_charging_far_from_limit_returns_active(self):
        coord = _make_coordinator(state=STATE_CHARGING_SOLAR, tesla_soc=50.0, tesla_limit=80.0)
        assert coord._determine_polling_mode(sun_up=True) == POLLING_MODE_ACTIVE

    def test_charging_near_limit_returns_close(self):
        coord = _make_coordinator(state=STATE_CHARGING_SOLAR, tesla_soc=78.5, tesla_limit=80.0)
        assert coord._determine_polling_mode(sun_up=True) == POLLING_MODE_CLOSE

    def test_charging_exactly_at_threshold_returns_close(self):
        coord = _make_coordinator(state=STATE_CHARGING_SOLAR, tesla_soc=78.0, tesla_limit=80.0)
        assert coord._determine_polling_mode(sun_up=True) == POLLING_MODE_CLOSE

    def test_charging_just_outside_threshold_returns_active(self):
        coord = _make_coordinator(state=STATE_CHARGING_SOLAR, tesla_soc=77.9, tesla_limit=80.0)
        assert coord._determine_polling_mode(sun_up=True) == POLLING_MODE_ACTIVE

    def test_no_tesla_soc_defaults_to_active_when_charging(self):
        coord = _make_coordinator(state=STATE_CHARGING_SOLAR, tesla_soc=None, tesla_limit=80.0)
        assert coord._determine_polling_mode(sun_up=True) == POLLING_MODE_ACTIVE
