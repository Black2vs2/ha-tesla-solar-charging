"""Constants for Tesla Solar Charging integration."""

DOMAIN = "tesla_solar_charging"
VERSION = "4.0.0"

# Config keys — required sensor entities
CONF_GRID_POWER_ENTITY = "grid_power_entity"
CONF_GRID_VOLTAGE_ENTITY = "grid_voltage_entity"
CONF_BATTERY_SOC_ENTITY = "battery_soc_entity"
CONF_BATTERY_POWER_ENTITY = "battery_power_entity"

# Config keys — required BLE control entities
CONF_BLE_CHARGER_SWITCH = "ble_charger_switch"
CONF_BLE_CHARGING_AMPS = "ble_charging_amps"
CONF_BLE_WAKE_BUTTON = "ble_wake_button"
CONF_BLE_CHARGE_LIMIT = "ble_charge_limit"
CONF_BLE_POLLING_MODE_ENTITY = "ble_polling_mode_entity"

# Polling modes
POLLING_MODE_OFF = "off"
POLLING_MODE_LAZY = "lazy"
POLLING_MODE_ACTIVE = "active"
POLLING_MODE_CLOSE = "close"

# SOC threshold for switching active -> close (percentage points below limit)
POLLING_SOC_CLOSE_THRESHOLD = 2

# Config keys — optional entities
CONF_TESLA_LOCATION_ENTITY = "tesla_location_entity"
CONF_TESLA_BATTERY_ENTITY = "tesla_battery_entity"
CONF_TESLA_CHARGE_LIMIT_ENTITY = "tesla_charge_limit_entity"

# Config keys — Deye inverter control entities
CONF_DEYE_WORK_MODE_ENTITY = "deye_work_mode_entity"
CONF_DEYE_ENERGY_PATTERN_ENTITY = "deye_energy_pattern_entity"
CONF_DEYE_BATTERY_DISCHARGE_ENTITY = "deye_battery_discharge_entity"

# Config keys — Octopus Energy
CONF_OCTOPUS_ENABLED = "octopus_enabled"
CONF_OCTOPUS_SMART_CHARGE_ENTITY = "octopus_smart_charge_entity"
CONF_OCTOPUS_DISPATCHING_ENTITY = "octopus_dispatching_entity"
CONF_OCTOPUS_EMAIL = "octopus_email"
CONF_OCTOPUS_PASSWORD = "octopus_password"
CONF_OCTOPUS_DEVICE_ID = "octopus_device_id"

# Config keys — tunable parameters
CONF_MIN_EXPORT_POWER = "min_export_power"
CONF_MAX_CHARGING_AMPS = "max_charging_amps"
CONF_SAFETY_BUFFER_AMPS = "safety_buffer_amps"
CONF_BATTERY_SOC_THRESHOLD = "battery_soc_threshold"
CONF_LOW_AMP_STOP_COUNT = "low_amp_stop_count"
CONF_UPDATE_INTERVAL = "update_interval"

# Config keys — energy orchestrator
CONF_GRID_POWER_LIMIT = "grid_power_limit"
CONF_PV_SYSTEM_KWP = "pv_system_kwp"
CONF_HOME_BATTERY_KWH = "home_battery_kwh"
CONF_TESLA_BATTERY_KWH = "tesla_battery_kwh"
CONF_AVG_HOUSE_CONSUMPTION_KWH = "avg_house_consumption_kwh"
CONF_PLANNING_TIME = "planning_time"
CONF_TELEGRAM_CHAT_ID = "telegram_chat_id"

# Config keys — newly configurable
CONF_PERFORMANCE_RATIO = "performance_ratio"
CONF_BATTERY_DISCHARGE_THRESHOLD = "battery_discharge_threshold"
CONF_HOME_LOCATION_STATES = "home_location_states"
CONF_TESLA_DEADLINE_ENTITY = "tesla_deadline_entity"
CONF_TESLA_TARGET_SOC_ENTITY = "tesla_target_soc_entity"
CONF_HOURLY_FORECAST_ENABLED = "hourly_forecast_enabled"

# Defaults
DEFAULT_MIN_EXPORT_POWER = 1200
DEFAULT_MAX_CHARGING_AMPS = 16
DEFAULT_SAFETY_BUFFER_AMPS = 3
DEFAULT_BATTERY_SOC_THRESHOLD = 98
DEFAULT_LOW_AMP_STOP_COUNT = 3
DEFAULT_UPDATE_INTERVAL = 30
DEFAULT_GRID_POWER_LIMIT = 3000
DEFAULT_TESLA_BATTERY_KWH = 60
DEFAULT_AVG_HOUSE_CONSUMPTION_KWH = 10
DEFAULT_PLANNING_TIME = "20:00"
MIN_CHARGING_AMPS = 5

# Defaults — newly configurable
DEFAULT_PERFORMANCE_RATIO = 0.60
DEFAULT_BATTERY_DISCHARGE_THRESHOLD = 100  # W
DEFAULT_HOME_LOCATION_STATES = "home"
DEFAULT_HOURLY_FORECAST_ENABLED = True
CONF_PLANNER_SAFETY_MARGIN = "planner_safety_margin"
DEFAULT_PLANNER_SAFETY_MARGIN = 1.2

# Config keys — Solcast forecast
CONF_SOLCAST_API_KEY = "solcast_api_key"
CONF_SOLCAST_RESOURCE_ID = "solcast_resource_id"

# Config keys — Forecast.Solar
CONF_FORECAST_SOLAR_ENABLED = "forecast_solar_enabled"
CONF_FORECAST_SOLAR_DECLINATION = "forecast_solar_declination"
CONF_FORECAST_SOLAR_AZIMUTH = "forecast_solar_azimuth"
DEFAULT_FORECAST_SOLAR_DECLINATION = 30
DEFAULT_FORECAST_SOLAR_AZIMUTH = 180

# Config keys — appliance advisor
CONF_APPLIANCES = "appliances"
CONF_ENTRY_TYPE = "entry_type"
ENTRY_TYPE_CHARGING = "charging"
ENTRY_TYPE_ADVISOR = "advisor"

# Advisor-specific config keys (grid/battery sensors needed independently)
CONF_ADVISOR_GRID_POWER_ENTITY = "advisor_grid_power_entity"
CONF_ADVISOR_GRID_VOLTAGE_ENTITY = "advisor_grid_voltage_entity"
CONF_ADVISOR_BATTERY_SOC_ENTITY = "advisor_battery_soc_entity"
CONF_ADVISOR_BATTERY_POWER_ENTITY = "advisor_battery_power_entity"

# Config keys — forecast tracking
CONF_DAILY_PRODUCTION_ENTITY = "daily_production_entity"

# Defaults — forecast tracking
DEFAULT_CORRECTION_FACTOR = 1.0
FORECAST_STORAGE_KEY = "tesla_solar_charging_forecast_history"
FORECAST_STORAGE_VERSION = 1
MIN_DAYS_FOR_CORRECTION = 7
ROLLING_WINDOW_DAYS = 30

# Charging states
STATE_IDLE = "idle"
STATE_WAITING = "waiting"
STATE_CHARGING = "charging"
STATE_CHARGING_SOLAR = "charging_solar"
STATE_CHARGING_NIGHT = "charging_night"
STATE_STOPPED = "stopped"
STATE_ERROR = "error"
STATE_PLANNED_SOLAR = "planned_solar"
STATE_PLANNED_NIGHT = "planned_night"

# BLE / ESP32 health states
BLE_STATUS_OK = "ok"
BLE_STATUS_ESP32_OFFLINE = "esp32_offline"
BLE_STATUS_BLE_ERROR = "ble_error"
BLE_STATUS_UNKNOWN = "unknown"

# Consecutive failures before declaring BLE error
BLE_MAX_CONSECUTIVE_FAILURES = 3

# Deye modes
DEYE_WORK_MODE_SELLING_FIRST = "Selling First"
DEYE_WORK_MODE_ZERO_EXPORT = "Zero Export + Limit to Load Only"
DEYE_ENERGY_PATTERN_BATTERY_FIRST = "Battery first"
DEYE_ENERGY_PATTERN_LOAD_FIRST = "Load first"

# Platforms
PLATFORMS = ["switch", "sensor", "number"]
