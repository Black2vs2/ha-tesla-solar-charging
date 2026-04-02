"""Solar Charging Coordinator — runs the 30s control loop with day/night modes."""

import logging
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.sun import is_up
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .ble_controller import BLEController
from .charging_logic import Action, Config, SensorState, calculate_net_available, decide, decide_night_amps
from .const import (
    BLE_STATUS_OK,
    CONF_BATTERY_DISCHARGE_THRESHOLD,
    CONF_BATTERY_POWER_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_BATTERY_SOC_THRESHOLD,
    CONF_GRID_POWER_ENTITY,
    CONF_GRID_POWER_LIMIT,
    CONF_GRID_VOLTAGE_ENTITY,
    CONF_HOME_LOCATION_STATES,
    CONF_LOW_AMP_STOP_COUNT,
    CONF_MAX_CHARGING_AMPS,
    CONF_MIN_EXPORT_POWER,
    CONF_OCTOPUS_DISPATCHING_ENTITY,
    CONF_OCTOPUS_ENABLED,
    CONF_OCTOPUS_SMART_CHARGE_ENTITY,
    CONF_AVG_HOUSE_CONSUMPTION_KWH,
    CONF_HOME_BATTERY_KWH,
    CONF_PLANNING_TIME,
    CONF_SAFETY_BUFFER_AMPS,
    CONF_TELEGRAM_CHAT_ID,
    CONF_TESLA_BATTERY_ENTITY,
    CONF_TESLA_CT_POWER_ENTITY,
    CT_CHARGING_THRESHOLD,
    DEFAULT_AVG_HOUSE_CONSUMPTION_KWH,
    DEFAULT_BATTERY_DISCHARGE_THRESHOLD,
    CONF_TESLA_LOCATION_ENTITY,
    DOMAIN,
    CONF_UPDATE_INTERVAL,
    DEFAULT_BATTERY_SOC_THRESHOLD,
    DEFAULT_GRID_POWER_LIMIT,
    DEFAULT_HOME_LOCATION_STATES,
    DEFAULT_LOW_AMP_STOP_COUNT,
    DEFAULT_MAX_CHARGING_AMPS,
    DEFAULT_MIN_EXPORT_POWER,
    DEFAULT_SAFETY_BUFFER_AMPS,
    DEFAULT_UPDATE_INTERVAL,
    MIN_CHARGING_AMPS,
    POLLING_MODE_ACTIVE,
    POLLING_MODE_CLOSE,
    POLLING_MODE_LAZY,
    POLLING_MODE_OFF,
    POLLING_SOC_CLOSE_THRESHOLD,
    STATE_CHARGING_NIGHT,
    STATE_CHARGING_SOLAR,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PLANNED_NIGHT,
    STATE_PLANNED_SOLAR,
    STATE_STOPPED,
    STATE_WAITING,
)
from .inverter_controller import InverterController

_LOGGER = logging.getLogger(__name__)


class SolarChargingCoordinator(DataUpdateCoordinator):
    """Coordinator that runs the solar charging control loop."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        entry_data: dict,
        ble: BLEController,
        inverter: InverterController,
    ) -> None:
        interval = entry_data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name="tesla_solar_charging",
            update_interval=timedelta(seconds=interval),
        )
        self._entry_id = entry_id
        self._entry_data = entry_data
        self._ble = ble
        self._inverter = inverter
        self._chat_id = entry_data.get(CONF_TELEGRAM_CHAT_ID)
        self._enabled = False
        self._low_amp_count = 0
        self._stop_cooldown = 0
        self._state = STATE_IDLE
        self._current_amps = 0
        self._net_available = 0.0
        self._reason = "Initializing"
        self._night_mode_active = False
        self._night_charge_planned = False
        self._forecast_kwh = 0.0
        self._plan_message = ""
        self._force_charge = False
        self._prev_charger_connected = None
        self._cloud_strategy = "unknown"
        self._best_charging_window = "Unknown"
        self._hourly_forecast_today: list[dict] = []
        self._forecast_today_kwh = 0.0
        self._daily_solar_kwh = 0.0
        self._daily_grid_kwh = 0.0
        self._daily_peak_amps = 0
        self._daily_charge_seconds = 0
        self._forecast_sources: list[dict] = []
        self._forecast_pessimistic_kwh = 0.0
        self._low_solar_warning: str | None = None
        self._multi_day_outlook: dict | None = None
        self._last_grid_power = 0.0
        self._last_grid_voltage = 0.0
        self._last_battery_soc = 0.0
        self._last_battery_power = 0.0
        self._current_polling_mode: str = POLLING_MODE_LAZY
        self._last_tesla_soc: float | None = None
        self._last_tesla_limit: float | None = None

    # --- Public properties ---

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
        if not value:
            self._state = STATE_IDLE
            self._reason = "Disabled by user"

    @property
    def state(self) -> str:
        return self._state

    @property
    def current_amps(self) -> int:
        return self._current_amps

    @property
    def net_available(self) -> float:
        return self._net_available

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def night_charge_planned(self) -> bool:
        return self._night_charge_planned

    @night_charge_planned.setter
    def night_charge_planned(self, value: bool) -> None:
        self._night_charge_planned = value
        if value:
            self._state = STATE_PLANNED_NIGHT
        else:
            self._state = STATE_PLANNED_SOLAR

    @property
    def forecast_kwh(self) -> float:
        return self._forecast_kwh

    @forecast_kwh.setter
    def forecast_kwh(self, value: float) -> None:
        self._forecast_kwh = value

    @property
    def plan_message(self) -> str:
        return self._plan_message

    @plan_message.setter
    def plan_message(self, value: str) -> None:
        self._plan_message = value

    @property
    def force_charge(self) -> bool:
        return self._force_charge

    @force_charge.setter
    def force_charge(self, value: bool) -> None:
        self._force_charge = value

    @property
    def low_solar_warning(self) -> str | None:
        return self._low_solar_warning

    @low_solar_warning.setter
    def low_solar_warning(self, value: str | None) -> None:
        self._low_solar_warning = value

    @property
    def multi_day_outlook(self) -> dict | None:
        return self._multi_day_outlook

    @multi_day_outlook.setter
    def multi_day_outlook(self, value: dict | None) -> None:
        self._multi_day_outlook = value

    @property
    def cloud_strategy(self) -> str:
        return self._cloud_strategy

    @cloud_strategy.setter
    def cloud_strategy(self, value: str) -> None:
        self._cloud_strategy = value

    @property
    def best_charging_window(self) -> str:
        return self._best_charging_window

    @best_charging_window.setter
    def best_charging_window(self, value: str) -> None:
        self._best_charging_window = value

    @property
    def ble_status(self) -> str:
        """Current BLE/ESP32 health status."""
        return self._ble.status

    @property
    def ble_status_detail(self) -> str:
        """Human-readable BLE/ESP32 status detail."""
        return self._ble.status_detail

    @property
    def daily_solar_kwh(self) -> float:
        return round(self._daily_solar_kwh, 1)

    @property
    def daily_grid_kwh(self) -> float:
        return round(self._daily_grid_kwh, 1)

    def reset_daily_stats(self) -> None:
        self._daily_solar_kwh = self._daily_grid_kwh = 0.0
        self._daily_peak_amps = self._daily_charge_seconds = 0


    # --- Helpers ---

    async def _notify(self, message: str) -> None:
        """Send a Telegram alert if chat_id is configured."""
        if self._chat_id:
            from .notification import send_alert_notification
            await send_alert_notification(self.hass, int(self._chat_id), message)

    def _get_float(self, entity_id: str, default: float = 0.0) -> float | None:
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _get_own_entity_id(self, domain: str, suffix: str) -> str | None:
        """Look up entity_id for one of our own entities by unique_id suffix."""
        from homeassistant.helpers import entity_registry as er
        registry = er.async_get(self.hass)
        unique_id = f"{self._entry_id}_{suffix}"
        return registry.async_get_entity_id(domain, DOMAIN, unique_id)

    def _get_own_float(self, suffix: str) -> float | None:
        """Read a float value from one of our own number entities."""
        entity_id = self._get_own_entity_id("number", suffix)
        if entity_id:
            return self._get_float(entity_id)
        return None

    def _is_home(self) -> bool:
        entity_id = self._entry_data.get(CONF_TESLA_LOCATION_ENTITY)
        if not entity_id:
            return True
        state = self.hass.states.get(entity_id)
        if state is None:
            return True
        if state.state in ("unavailable", "unknown"):
            _LOGGER.debug(
                "Tesla location entity %s is %s — assuming at home",
                entity_id, state.state,
            )
            return True
        home_states = self._entry_data.get(
            CONF_HOME_LOCATION_STATES, DEFAULT_HOME_LOCATION_STATES
        )
        valid_states = [s.strip().lower() for s in home_states.split(",")]
        actual = state.state.lower()
        is_home = actual in valid_states
        if not is_home:
            _LOGGER.debug(
                "Tesla location '%s' (entity %s) not in home states %s",
                state.state, entity_id, valid_states,
            )
        return is_home

    def _determine_polling_mode(self, sun_up: bool) -> str:
        """Determine BLE polling mode based on current charging state.

        Uses CT clamp as ground truth when available — if the CT clamp shows
        power draw, the car is definitely charging regardless of BLE state.
        """
        if not self._enabled:
            return POLLING_MODE_OFF

        if not self._is_home():
            return POLLING_MODE_OFF

        is_charging = self._state in (STATE_CHARGING_SOLAR, STATE_CHARGING_NIGHT)

        # CT clamp overrides BLE state — it's real-time ground truth
        ct_charging = self._is_ct_charging()
        if ct_charging is not None:
            is_charging = is_charging or ct_charging

        # Night + not charging + not force_charge + not night_charge_planned → off
        if not sun_up and not is_charging and not self._force_charge and not self._night_charge_planned:
            return POLLING_MODE_OFF

        # Not charging + not force_charge → lazy (60 min)
        if not is_charging and not self._force_charge:
            return POLLING_MODE_LAZY

        # Charging or force_charge: check SOC proximity
        if (
            self._last_tesla_soc is not None
            and self._last_tesla_limit is not None
            and self._last_tesla_limit - self._last_tesla_soc <= POLLING_SOC_CLOSE_THRESHOLD
        ):
            return POLLING_MODE_CLOSE

        return POLLING_MODE_ACTIVE

    def _is_charger_on(self) -> bool:
        state = self.hass.states.get(self._ble.charger_switch)
        if state is None:
            return False
        return state.state == "on"

    def _is_ct_charging(self) -> bool | None:
        """Check if CT clamp shows the car is actually drawing power.

        Returns True/False if configured, None if not configured or unavailable.
        """
        entity_id = self._entry_data.get(CONF_TESLA_CT_POWER_ENTITY)
        if not entity_id:
            return None
        power = self._get_float(entity_id)
        if power is None:
            return None
        return power > CT_CHARGING_THRESHOLD

    def _get_current_amps(self) -> float:
        val = self._get_float(self._ble.charging_amps, MIN_CHARGING_AMPS)
        return val if val is not None else MIN_CHARGING_AMPS

    def _get_effective_amps(self, grid_voltage: float) -> float:
        """Get actual charging amps — prefer CT clamp (ground truth) over BLE entity.

        BLE entities can be stale (e.g. switch shows 'off', amps shows 5)
        while the car is actually charging at 16A. The CT clamp measures
        real power draw on the charger circuit.
        """
        ct_entity = self._entry_data.get(CONF_TESLA_CT_POWER_ENTITY)
        if ct_entity:
            ct_power = self._get_float(ct_entity)
            if ct_power is not None and ct_power > CT_CHARGING_THRESHOLD:
                return ct_power / grid_voltage if grid_voltage > 0 else 0.0
        return self._get_current_amps()

    def _is_octopus_dispatching(self) -> bool:
        """Check if Octopus Intelligent is actively dispatching (cheap rate window)."""
        if not self._entry_data.get(CONF_OCTOPUS_ENABLED, False):
            return False
        entity_id = self._entry_data.get(CONF_OCTOPUS_DISPATCHING_ENTITY)
        if entity_id:
            state = self.hass.states.get(entity_id)
            if state and state.state == "on":
                return True
        # Fallback: nighttime + charger on + planned
        if not is_up(self.hass) and self._is_charger_on() and self._night_charge_planned:
            return True
        return False

    # --- Main loop ---

    async def _async_update_data(self) -> dict:
        # Update polling mode (even when disabled, to set off)
        sun_up = is_up(self.hass)
        desired_mode = self._determine_polling_mode(sun_up)
        if desired_mode != self._current_polling_mode:
            try:
                await self._ble.set_polling_mode(desired_mode)
                self._current_polling_mode = desired_mode
                _LOGGER.info("BLE polling mode changed to: %s", desired_mode)
            except Exception as err:
                _LOGGER.warning("Failed to set polling mode: %s", err)

        if not self._enabled:
            return {}

        # Check BLE/ESP32 health before doing anything
        if not self._ble.is_healthy:
            ble_status = self._ble.status
            if self._state != STATE_ERROR:  # only notify on transition
                from .notification import format_ble_alert
                await self._notify(format_ble_alert(ble_status, self._ble.status_detail))
            _LOGGER.warning("BLE unhealthy (%s): %s", ble_status, self._ble.status_detail)
            self._state = STATE_ERROR
            self._reason = f"BLE unhealthy ({ble_status}): {self._ble.status_detail}"
            return {}

        # Auto-reset force charge when car is re-plugged
        charger_connected = self._is_charger_on()
        if self._prev_charger_connected is not None:
            if charger_connected and not self._prev_charger_connected:
                # Car just plugged in — reset force charge
                if self._force_charge:
                    self._force_charge = False
                    _LOGGER.info("Car plugged in — force charge reset")
        self._prev_charger_connected = charger_connected

        # Read grid sensors
        grid_power = self._get_float(self._entry_data[CONF_GRID_POWER_ENTITY])
        grid_voltage = self._get_float(self._entry_data[CONF_GRID_VOLTAGE_ENTITY])

        if grid_power is None or grid_voltage is None:
            self._state = STATE_ERROR
            self._reason = "Grid sensors unavailable"
            return {}

        # Detect mode
        if self._is_octopus_dispatching():
            await self._handle_night_mode(grid_power, grid_voltage)
        elif is_up(self.hass):
            # Restore day mode if we were in night mode
            if self._night_mode_active:
                await self._exit_night_mode()
            await self._handle_solar_mode(grid_power, grid_voltage)
        else:
            # Nighttime, no Octopus dispatch — stop charging unless force is on
            # Use CT clamp as ground truth if available, fall back to BLE switch
            ct_charging = self._is_ct_charging()
            actually_charging = ct_charging if ct_charging is not None else self._is_charger_on()
            if actually_charging and not self._force_charge:
                try:
                    await self._ble.stop_charging()
                    self._current_amps = 0
                    _LOGGER.info("Night: stopped charging (no force charge, no dispatch)")
                except Exception as err:
                    _LOGGER.error("Night stop BLE failed: %s", err)
            self._state = STATE_WAITING
            self._reason = "Nighttime — waiting for sunrise"

        return {}

    # --- Night mode ---

    async def _handle_night_mode(self, grid_power: float, grid_voltage: float) -> None:
        """Handle night charging — manage Deye mode and limit grid draw."""
        # Enter night mode if not already
        if not self._night_mode_active:
            await self._enter_night_mode()

        # Track Tesla SOC/limit for polling mode decisions
        if self._entry_data.get(CONF_TESLA_BATTERY_ENTITY):
            self._last_tesla_soc = self._get_float(self._entry_data[CONF_TESLA_BATTERY_ENTITY])
        self._last_tesla_limit = self._get_own_float("charge_limit")

        grid_limit = self._entry_data.get(CONF_GRID_POWER_LIMIT, DEFAULT_GRID_POWER_LIMIT)
        max_amps = self._entry_data.get(CONF_MAX_CHARGING_AMPS, DEFAULT_MAX_CHARGING_AMPS)

        decision = decide_night_amps(
            grid_power=grid_power,
            grid_voltage=grid_voltage,
            current_amps=self._get_current_amps(),
            grid_power_limit=grid_limit,
            max_charging_amps=max_amps,
        )

        self._reason = decision.reason
        self._net_available = (grid_limit - grid_power) / grid_voltage if grid_voltage > 0 else 0

        try:
            if decision.action == Action.STOP:
                await self._ble.set_charging_amps(MIN_CHARGING_AMPS)
                self._current_amps = MIN_CHARGING_AMPS
                self._state = STATE_CHARGING_NIGHT
            elif decision.action == Action.ADJUST:
                if decision.target_amps != int(self._get_current_amps()):
                    await self._ble.set_charging_amps(decision.target_amps)
                self._current_amps = decision.target_amps
                self._state = STATE_CHARGING_NIGHT
            else:
                self._state = STATE_CHARGING_NIGHT
        except Exception as err:
            _LOGGER.error("Night mode BLE command failed: %s", err)
            self._state = STATE_ERROR
            self._reason = f"BLE error: {err}"

        # Accumulate daily grid charging stats
        if self._state == STATE_CHARGING_NIGHT:
            interval = self._entry_data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            kwh_this_tick = (self._current_amps * grid_voltage * interval) / 3_600_000
            self._daily_grid_kwh += kwh_this_tick
            self._daily_charge_seconds += interval
            self._daily_peak_amps = max(self._daily_peak_amps, self._current_amps)

    async def _enter_night_mode(self) -> None:
        """Switch Deye inverter to night mode."""
        _LOGGER.info("Entering night charging mode")
        self._night_mode_active = True
        try:
            await self._inverter.set_night_mode()
            from .notification import format_night_mode_change
            await self._notify(format_night_mode_change(entering=True))
        except Exception as err:
            _LOGGER.error("Failed to set inverter night mode: %s", err)
            self._state = STATE_ERROR
            self._reason = f"Inverter night mode failed: {err}"

    async def _exit_night_mode(self) -> None:
        """Restore Deye inverter to day mode."""
        _LOGGER.info("Exiting night charging mode")
        self._night_mode_active = False
        self._night_charge_planned = False
        try:
            await self._inverter.restore_day_mode()
            from .notification import format_night_mode_change
            await self._notify(format_night_mode_change(entering=False))
        except Exception as err:
            _LOGGER.error("Failed to restore inverter day mode: %s", err)
            self._state = STATE_ERROR
            self._reason = f"Inverter day mode restore failed: {err}"

    # --- Solar mode (existing v1 logic) ---

    async def _handle_solar_mode(self, grid_power: float, grid_voltage: float) -> None:
        """Handle daytime solar excess charging."""
        if not self._is_home():
            self._state = STATE_WAITING
            self._reason = "Tesla not at home"
            return

        battery_soc = self._get_float(
            self._entry_data[CONF_BATTERY_SOC_ENTITY], 0.0
        ) or 0.0
        battery_power = self._get_float(
            self._entry_data[CONF_BATTERY_POWER_ENTITY], 0.0
        ) or 0.0
        self._last_grid_power = grid_power
        self._last_grid_voltage = grid_voltage
        self._last_battery_soc = battery_soc
        self._last_battery_power = battery_power

        tesla_battery = None
        if self._entry_data.get(CONF_TESLA_BATTERY_ENTITY):
            tesla_battery = self._get_float(self._entry_data[CONF_TESLA_BATTERY_ENTITY])
        tesla_limit = self._get_own_float("charge_limit")

        # Track for polling mode decisions
        self._last_tesla_soc = tesla_battery
        self._last_tesla_limit = tesla_limit

        # Use CT clamp as ground truth for charging detection when available
        ct_charging = self._is_ct_charging()
        ble_charging = self._is_charger_on()
        is_charging = ct_charging if ct_charging is not None else ble_charging

        # After STOP, if BLE still shows "on", retry stop instead of
        # re-entering charging logic (BLE commands can take a few cycles)
        if self._stop_cooldown > 0:
            self._stop_cooldown -= 1
            if is_charging:
                _LOGGER.info("Stop cooldown %d: BLE still on, retrying stop", self._stop_cooldown)
                try:
                    await self._ble.stop_charging()
                except Exception as err:
                    _LOGGER.error("Stop retry BLE failed: %s", err)
                self._reason = f"Stopping — waiting for car to respond ({self._stop_cooldown} cycles left)"
                return
            else:
                # Car actually stopped, clear cooldown
                self._stop_cooldown = 0
                _LOGGER.info("Stop cooldown: car confirmed stopped")

        # Use CT clamp as ground truth for amps when available — BLE entities
        # can be stale (switch "off", amps stuck at 5) while the car is actually
        # charging at 16A. CT measures real power on the charger circuit.
        effective_amps = self._get_effective_amps(grid_voltage) if is_charging else 0.0

        sensor_state = SensorState(
            grid_power=grid_power,
            grid_voltage=grid_voltage,
            battery_soc=battery_soc,
            battery_power=battery_power,
            is_charging=is_charging,
            current_amps=effective_amps if is_charging else self._get_current_amps(),
            low_amp_count=self._low_amp_count,
            tesla_battery=tesla_battery,
            tesla_charge_limit=tesla_limit,
        )

        config = Config(
            min_export_power=self._entry_data.get(CONF_MIN_EXPORT_POWER, DEFAULT_MIN_EXPORT_POWER),
            max_charging_amps=self._entry_data.get(CONF_MAX_CHARGING_AMPS, DEFAULT_MAX_CHARGING_AMPS),
            safety_buffer_amps=self._entry_data.get(CONF_SAFETY_BUFFER_AMPS, DEFAULT_SAFETY_BUFFER_AMPS),
            battery_soc_threshold=self._entry_data.get(CONF_BATTERY_SOC_THRESHOLD, DEFAULT_BATTERY_SOC_THRESHOLD),
            low_amp_stop_count=self._entry_data.get(CONF_LOW_AMP_STOP_COUNT, DEFAULT_LOW_AMP_STOP_COUNT),
            battery_discharge_threshold=self._entry_data.get(
                CONF_BATTERY_DISCHARGE_THRESHOLD, DEFAULT_BATTERY_DISCHARGE_THRESHOLD
            ),
        )

        self._net_available = calculate_net_available(
            grid_power, grid_voltage, battery_power, config.safety_buffer_amps,
            current_charging_amps=effective_amps,
        )

        decision = decide(sensor_state, config, force=self._force_charge)
        self._low_amp_count = decision.new_low_amp_count
        self._reason = decision.reason

        try:
            if decision.action == Action.START:
                await self._ble.wake()
                await self._ble.set_charging_amps(decision.target_amps)
                await self._ble.start_charging()
                self._state = STATE_CHARGING_SOLAR
                self._current_amps = decision.target_amps
            elif decision.action == Action.STOP:
                await self._ble.stop_charging()
                self._state = STATE_STOPPED
                self._current_amps = 0
                self._low_amp_count = 0
                self._stop_cooldown = 3
                if "reached limit" in decision.reason:
                    from .notification import format_charge_limit_reached
                    tesla_bat = self._get_float(self._entry_data.get(CONF_TESLA_BATTERY_ENTITY, "")) or 0
                    tesla_lim = self._get_own_float("charge_limit") or 0
                    await self._notify(format_charge_limit_reached(tesla_bat, tesla_lim))
                else:
                    from .notification import format_charge_stopped
                    await self._notify(format_charge_stopped(decision.reason))
            elif decision.action == Action.ADJUST:
                if decision.target_amps != int(sensor_state.current_amps):
                    await self._ble.set_charging_amps(decision.target_amps)
                self._current_amps = decision.target_amps
                self._state = STATE_CHARGING_SOLAR
            else:
                if sensor_state.is_charging:
                    self._state = STATE_CHARGING_SOLAR
        except Exception as err:
            _LOGGER.error("Solar mode BLE command failed: %s", err)
            self._state = STATE_ERROR
            self._reason = f"BLE error: {err}"

        # Accumulate daily solar charging stats
        if self._state == STATE_CHARGING_SOLAR:
            interval = self._entry_data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            kwh_this_tick = (self._current_amps * grid_voltage * interval) / 3_600_000
            self._daily_solar_kwh += kwh_this_tick
            self._daily_charge_seconds += interval
            self._daily_peak_amps = max(self._daily_peak_amps, self._current_amps)
