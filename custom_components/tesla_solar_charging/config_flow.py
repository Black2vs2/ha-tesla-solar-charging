"""Config flow for Tesla Solar Charging."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_AVG_HOUSE_CONSUMPTION_KWH,
    CONF_BATTERY_DISCHARGE_THRESHOLD,
    CONF_BATTERY_POWER_ENTITY,
    CONF_DAILY_PRODUCTION_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_BATTERY_SOC_THRESHOLD,
    CONF_BLE_CHARGE_LIMIT,
    CONF_BLE_CHARGER_SWITCH,
    CONF_BLE_CHARGING_AMPS,
    CONF_BLE_WAKE_BUTTON,
    CONF_DEYE_BATTERY_DISCHARGE_ENTITY,
    CONF_DEYE_ENERGY_PATTERN_ENTITY,
    CONF_DEYE_WORK_MODE_ENTITY,
    CONF_FORECAST_SOLAR_AZIMUTH,
    CONF_FORECAST_SOLAR_DECLINATION,
    CONF_FORECAST_SOLAR_ENABLED,
    CONF_GRID_POWER_ENTITY,
    CONF_GRID_POWER_LIMIT,
    CONF_GRID_VOLTAGE_ENTITY,
    CONF_HOME_BATTERY_KWH,
    CONF_HOME_LOCATION_STATES,
    CONF_HOURLY_FORECAST_ENABLED,
    CONF_LOW_AMP_STOP_COUNT,
    CONF_MAX_CHARGING_AMPS,
    CONF_MIN_EXPORT_POWER,
    CONF_OCTOPUS_DEVICE_ID,
    CONF_OCTOPUS_DISPATCHING_ENTITY,
    CONF_OCTOPUS_EMAIL,
    CONF_OCTOPUS_ENABLED,
    CONF_OCTOPUS_PASSWORD,
    CONF_OCTOPUS_SMART_CHARGE_ENTITY,
    CONF_PERFORMANCE_RATIO,
    CONF_PLANNER_SAFETY_MARGIN,
    CONF_PLANNING_TIME,
    CONF_PV_SYSTEM_KWP,
    CONF_SAFETY_BUFFER_AMPS,
    CONF_TELEGRAM_CHAT_ID,
    CONF_TESLA_BATTERY_ENTITY,
    CONF_TESLA_BATTERY_KWH,
    CONF_TESLA_LOCATION_ENTITY,
    CONF_SOLCAST_API_KEY,
    CONF_SOLCAST_RESOURCE_ID,
    CONF_UPDATE_INTERVAL,
    DEFAULT_AVG_HOUSE_CONSUMPTION_KWH,
    DEFAULT_BATTERY_DISCHARGE_THRESHOLD,
    DEFAULT_FORECAST_SOLAR_AZIMUTH,
    DEFAULT_FORECAST_SOLAR_DECLINATION,
    DEFAULT_PLANNER_SAFETY_MARGIN,
    DEFAULT_BATTERY_SOC_THRESHOLD,
    DEFAULT_GRID_POWER_LIMIT,
    DEFAULT_HOME_LOCATION_STATES,
    DEFAULT_HOURLY_FORECAST_ENABLED,
    DEFAULT_LOW_AMP_STOP_COUNT,
    DEFAULT_MAX_CHARGING_AMPS,
    DEFAULT_MIN_EXPORT_POWER,
    DEFAULT_PERFORMANCE_RATIO,
    DEFAULT_PLANNING_TIME,
    DEFAULT_SAFETY_BUFFER_AMPS,
    DEFAULT_TESLA_BATTERY_KWH,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

SENSOR_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor")
)
SWITCH_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="switch")
)
NUMBER_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="number")
)
BUTTON_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="button")
)
TRACKER_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="device_tracker")
)
SELECT_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="select")
)


class TeslaSolarChargingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Tesla Solar Charging."""

    VERSION = 2

    def __init__(self):
        self._data = {}

    async def async_step_user(self, user_input=None):
        """Step 1: Sensor and BLE entity selection."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_inverter()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                # Required — Deye sensors
                vol.Required(CONF_GRID_POWER_ENTITY): SENSOR_SELECTOR,
                vol.Required(CONF_GRID_VOLTAGE_ENTITY): SENSOR_SELECTOR,
                vol.Required(CONF_BATTERY_SOC_ENTITY): SENSOR_SELECTOR,
                vol.Required(CONF_BATTERY_POWER_ENTITY): SENSOR_SELECTOR,
                # Required — BLE controls
                vol.Required(CONF_BLE_CHARGER_SWITCH): SWITCH_SELECTOR,
                vol.Required(CONF_BLE_CHARGING_AMPS): NUMBER_SELECTOR,
                vol.Required(CONF_BLE_WAKE_BUTTON): BUTTON_SELECTOR,
                vol.Optional(CONF_BLE_CHARGE_LIMIT): NUMBER_SELECTOR,
                # Optional — Tesla
                vol.Optional(CONF_TESLA_LOCATION_ENTITY): TRACKER_SELECTOR,
                vol.Optional(CONF_HOME_LOCATION_STATES, default=DEFAULT_HOME_LOCATION_STATES): str,
                vol.Optional(CONF_TESLA_BATTERY_ENTITY): SENSOR_SELECTOR,
                vol.Optional(CONF_DAILY_PRODUCTION_ENTITY): SENSOR_SELECTOR,
            }),
        )

    async def async_step_inverter(self, user_input=None):
        """Step 2: Inverter and Octopus configuration."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_energy()

        return self.async_show_form(
            step_id="inverter",
            data_schema=vol.Schema({
                # Deye inverter controls
                vol.Optional(CONF_DEYE_WORK_MODE_ENTITY): SELECT_SELECTOR,
                vol.Optional(CONF_DEYE_ENERGY_PATTERN_ENTITY): SELECT_SELECTOR,
                vol.Optional(CONF_DEYE_BATTERY_DISCHARGE_ENTITY): NUMBER_SELECTOR,
                # Octopus Energy
                vol.Optional(CONF_OCTOPUS_ENABLED, default=False): bool,
                vol.Optional(CONF_OCTOPUS_SMART_CHARGE_ENTITY): SWITCH_SELECTOR,
                vol.Optional(CONF_OCTOPUS_DISPATCHING_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                vol.Optional(CONF_OCTOPUS_EMAIL): str,
                vol.Optional(CONF_OCTOPUS_PASSWORD): str,
                vol.Optional(CONF_OCTOPUS_DEVICE_ID): str,
                # Telegram
                vol.Optional(CONF_TELEGRAM_CHAT_ID): vol.Coerce(int),
                # Planning
                vol.Optional(CONF_PLANNING_TIME, default=DEFAULT_PLANNING_TIME): str,
            }),
        )

    async def async_step_energy(self, user_input=None):
        """Step 3: Energy system parameters."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(
                title="Tesla Solar Charging",
                data=self._data,
            )

        return self.async_show_form(
            step_id="energy",
            data_schema=vol.Schema({
                vol.Required(CONF_PV_SYSTEM_KWP): vol.Coerce(float),
                vol.Required(CONF_HOME_BATTERY_KWH): vol.Coerce(float),
                vol.Optional(CONF_TESLA_BATTERY_KWH, default=DEFAULT_TESLA_BATTERY_KWH): vol.Coerce(float),
                vol.Optional(CONF_AVG_HOUSE_CONSUMPTION_KWH, default=DEFAULT_AVG_HOUSE_CONSUMPTION_KWH): vol.Coerce(float),
                vol.Optional(CONF_GRID_POWER_LIMIT, default=DEFAULT_GRID_POWER_LIMIT): vol.Coerce(int),
                vol.Optional(CONF_MIN_EXPORT_POWER, default=DEFAULT_MIN_EXPORT_POWER): vol.Coerce(int),
                vol.Optional(CONF_MAX_CHARGING_AMPS, default=DEFAULT_MAX_CHARGING_AMPS): vol.Coerce(int),
                vol.Optional(CONF_SAFETY_BUFFER_AMPS, default=DEFAULT_SAFETY_BUFFER_AMPS): vol.Coerce(int),
                vol.Optional(CONF_BATTERY_SOC_THRESHOLD, default=DEFAULT_BATTERY_SOC_THRESHOLD): vol.Coerce(int),
                vol.Optional(CONF_LOW_AMP_STOP_COUNT, default=DEFAULT_LOW_AMP_STOP_COUNT): vol.Coerce(int),
                vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.Coerce(int),
                vol.Optional(CONF_PERFORMANCE_RATIO, default=DEFAULT_PERFORMANCE_RATIO): vol.Coerce(float),
                vol.Optional(CONF_BATTERY_DISCHARGE_THRESHOLD, default=DEFAULT_BATTERY_DISCHARGE_THRESHOLD): vol.Coerce(int),

                vol.Optional(CONF_HOURLY_FORECAST_ENABLED, default=DEFAULT_HOURLY_FORECAST_ENABLED): bool,
                vol.Optional(CONF_PLANNER_SAFETY_MARGIN, default=DEFAULT_PLANNER_SAFETY_MARGIN): vol.Coerce(float),
                vol.Optional(CONF_SOLCAST_API_KEY): str,
                vol.Optional(CONF_SOLCAST_RESOURCE_ID): str,
                vol.Optional(CONF_FORECAST_SOLAR_ENABLED, default=False): bool,
                vol.Optional(CONF_FORECAST_SOLAR_DECLINATION, default=DEFAULT_FORECAST_SOLAR_DECLINATION): vol.Coerce(int),
                vol.Optional(CONF_FORECAST_SOLAR_AZIMUTH, default=DEFAULT_FORECAST_SOLAR_AZIMUTH): vol.Coerce(int),
            }),
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return TeslaSolarChargingOptionsFlow(config_entry)


class TeslaSolarChargingOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow — entities + parameters."""

    def __init__(self, config_entry):
        self._config_entry = config_entry
        self._options = {}

    async def async_step_init(self, user_input=None):
        """Step 1: Entity configuration."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_inverter()

        data = {**self._config_entry.data, **self._config_entry.options}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_GRID_POWER_ENTITY, default=data.get(CONF_GRID_POWER_ENTITY, "")): SENSOR_SELECTOR,
                vol.Required(CONF_GRID_VOLTAGE_ENTITY, default=data.get(CONF_GRID_VOLTAGE_ENTITY, "")): SENSOR_SELECTOR,
                vol.Required(CONF_BATTERY_SOC_ENTITY, default=data.get(CONF_BATTERY_SOC_ENTITY, "")): SENSOR_SELECTOR,
                vol.Required(CONF_BATTERY_POWER_ENTITY, default=data.get(CONF_BATTERY_POWER_ENTITY, "")): SENSOR_SELECTOR,
                vol.Required(CONF_BLE_CHARGER_SWITCH, default=data.get(CONF_BLE_CHARGER_SWITCH, "")): SWITCH_SELECTOR,
                vol.Required(CONF_BLE_CHARGING_AMPS, default=data.get(CONF_BLE_CHARGING_AMPS, "")): NUMBER_SELECTOR,
                vol.Required(CONF_BLE_WAKE_BUTTON, default=data.get(CONF_BLE_WAKE_BUTTON, "")): BUTTON_SELECTOR,
                vol.Optional(CONF_BLE_CHARGE_LIMIT, default=data.get(CONF_BLE_CHARGE_LIMIT, "")): NUMBER_SELECTOR,
                vol.Optional(CONF_TESLA_LOCATION_ENTITY, default=data.get(CONF_TESLA_LOCATION_ENTITY, "")): TRACKER_SELECTOR,
                vol.Optional(CONF_HOME_LOCATION_STATES, default=data.get(CONF_HOME_LOCATION_STATES, DEFAULT_HOME_LOCATION_STATES)): str,
                vol.Optional(CONF_TESLA_BATTERY_ENTITY, default=data.get(CONF_TESLA_BATTERY_ENTITY, "")): SENSOR_SELECTOR,
                vol.Optional(CONF_DAILY_PRODUCTION_ENTITY, default=data.get(CONF_DAILY_PRODUCTION_ENTITY, "")): SENSOR_SELECTOR,
            }),
        )

    async def async_step_inverter(self, user_input=None):
        """Step 2: Inverter and notifications."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_energy()

        data = {**self._config_entry.data, **self._config_entry.options}

        return self.async_show_form(
            step_id="inverter",
            data_schema=vol.Schema({
                vol.Optional(CONF_DEYE_WORK_MODE_ENTITY, default=data.get(CONF_DEYE_WORK_MODE_ENTITY, "")): SELECT_SELECTOR,
                vol.Optional(CONF_DEYE_ENERGY_PATTERN_ENTITY, default=data.get(CONF_DEYE_ENERGY_PATTERN_ENTITY, "")): SELECT_SELECTOR,
                vol.Optional(CONF_DEYE_BATTERY_DISCHARGE_ENTITY, default=data.get(CONF_DEYE_BATTERY_DISCHARGE_ENTITY, "")): NUMBER_SELECTOR,
                vol.Optional(CONF_OCTOPUS_ENABLED, default=data.get(CONF_OCTOPUS_ENABLED, False)): bool,
                vol.Optional(CONF_OCTOPUS_SMART_CHARGE_ENTITY, default=data.get(CONF_OCTOPUS_SMART_CHARGE_ENTITY, "")): SWITCH_SELECTOR,
                vol.Optional(CONF_OCTOPUS_DISPATCHING_ENTITY, default=data.get(CONF_OCTOPUS_DISPATCHING_ENTITY, "")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                vol.Optional(CONF_OCTOPUS_EMAIL, default=data.get(CONF_OCTOPUS_EMAIL, "")): str,
                vol.Optional(CONF_OCTOPUS_PASSWORD, default=data.get(CONF_OCTOPUS_PASSWORD, "")): str,
                vol.Optional(CONF_OCTOPUS_DEVICE_ID, default=data.get(CONF_OCTOPUS_DEVICE_ID, "")): str,
                vol.Optional(CONF_TELEGRAM_CHAT_ID, default=data.get(CONF_TELEGRAM_CHAT_ID, 0)): vol.Coerce(int),
                vol.Optional(CONF_PLANNING_TIME, default=data.get(CONF_PLANNING_TIME, DEFAULT_PLANNING_TIME)): str,
            }),
        )

    async def async_step_energy(self, user_input=None):
        """Step 3: Energy parameters."""
        if user_input is not None:
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        data = {**self._config_entry.data, **self._config_entry.options}

        return self.async_show_form(
            step_id="energy",
            data_schema=vol.Schema({
                vol.Optional(CONF_PV_SYSTEM_KWP, default=data.get(CONF_PV_SYSTEM_KWP, 6.0)): vol.Coerce(float),
                vol.Optional(CONF_HOME_BATTERY_KWH, default=data.get(CONF_HOME_BATTERY_KWH, 10.0)): vol.Coerce(float),
                vol.Optional(CONF_TESLA_BATTERY_KWH, default=data.get(CONF_TESLA_BATTERY_KWH, DEFAULT_TESLA_BATTERY_KWH)): vol.Coerce(float),
                vol.Optional(CONF_AVG_HOUSE_CONSUMPTION_KWH, default=data.get(CONF_AVG_HOUSE_CONSUMPTION_KWH, DEFAULT_AVG_HOUSE_CONSUMPTION_KWH)): vol.Coerce(float),
                vol.Optional(CONF_GRID_POWER_LIMIT, default=data.get(CONF_GRID_POWER_LIMIT, DEFAULT_GRID_POWER_LIMIT)): vol.Coerce(int),
                vol.Optional(CONF_MIN_EXPORT_POWER, default=data.get(CONF_MIN_EXPORT_POWER, DEFAULT_MIN_EXPORT_POWER)): vol.Coerce(int),
                vol.Optional(CONF_MAX_CHARGING_AMPS, default=data.get(CONF_MAX_CHARGING_AMPS, DEFAULT_MAX_CHARGING_AMPS)): vol.Coerce(int),
                vol.Optional(CONF_SAFETY_BUFFER_AMPS, default=data.get(CONF_SAFETY_BUFFER_AMPS, DEFAULT_SAFETY_BUFFER_AMPS)): vol.Coerce(int),
                vol.Optional(CONF_BATTERY_SOC_THRESHOLD, default=data.get(CONF_BATTERY_SOC_THRESHOLD, DEFAULT_BATTERY_SOC_THRESHOLD)): vol.Coerce(int),
                vol.Optional(CONF_LOW_AMP_STOP_COUNT, default=data.get(CONF_LOW_AMP_STOP_COUNT, DEFAULT_LOW_AMP_STOP_COUNT)): vol.Coerce(int),
                vol.Optional(CONF_UPDATE_INTERVAL, default=data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)): vol.Coerce(int),
                vol.Optional(CONF_PERFORMANCE_RATIO, default=data.get(CONF_PERFORMANCE_RATIO, DEFAULT_PERFORMANCE_RATIO)): vol.Coerce(float),
                vol.Optional(CONF_BATTERY_DISCHARGE_THRESHOLD, default=data.get(CONF_BATTERY_DISCHARGE_THRESHOLD, DEFAULT_BATTERY_DISCHARGE_THRESHOLD)): vol.Coerce(int),
                vol.Optional(CONF_HOURLY_FORECAST_ENABLED, default=data.get(CONF_HOURLY_FORECAST_ENABLED, DEFAULT_HOURLY_FORECAST_ENABLED)): bool,
                vol.Optional(CONF_PLANNER_SAFETY_MARGIN, default=data.get(CONF_PLANNER_SAFETY_MARGIN, DEFAULT_PLANNER_SAFETY_MARGIN)): vol.Coerce(float),
                vol.Optional(CONF_SOLCAST_API_KEY, default=data.get(CONF_SOLCAST_API_KEY, "")): str,
                vol.Optional(CONF_SOLCAST_RESOURCE_ID, default=data.get(CONF_SOLCAST_RESOURCE_ID, "")): str,
                vol.Optional(CONF_FORECAST_SOLAR_ENABLED, default=data.get(CONF_FORECAST_SOLAR_ENABLED, False)): bool,
                vol.Optional(CONF_FORECAST_SOLAR_DECLINATION, default=data.get(CONF_FORECAST_SOLAR_DECLINATION, DEFAULT_FORECAST_SOLAR_DECLINATION)): vol.Coerce(int),
                vol.Optional(CONF_FORECAST_SOLAR_AZIMUTH, default=data.get(CONF_FORECAST_SOLAR_AZIMUTH, DEFAULT_FORECAST_SOLAR_AZIMUTH)): vol.Coerce(int),
            }),
        )
