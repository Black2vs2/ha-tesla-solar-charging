# Smart BLE Polling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce Tesla 12V battery drain by replacing the ESP32's aggressive constant polling with HA-controlled adaptive polling modes (off/lazy/active/close).

**Architecture:** Fork `yoziru/esphome-tesla-ble` and add a `select` entity for polling mode. The HA integration's coordinator determines the right mode based on time of day, charging state, and SOC proximity to charge limit, then sets it via service call. The ESP32 firmware adjusts poll intervals and BLE connection state accordingly.

**Tech Stack:** ESPHome (C++/Python component), Home Assistant custom integration (Python), ESP-IDF BLE

---

### Task 1: Fork the upstream repo and clone it

**Files:**
- No code changes, just repository setup

- [ ] **Step 1: Fork the repo on GitHub**

Go to https://github.com/yoziru/esphome-tesla-ble and fork it to `black2vs2/esphome-tesla-ble`.

- [ ] **Step 2: Clone the fork locally**

```bash
cd C:/Projects/Projects/personal/ok
git clone https://github.com/black2vs2/esphome-tesla-ble.git
cd esphome-tesla-ble
```

- [ ] **Step 3: Verify the component structure**

```bash
ls components/tesla_ble_vehicle/
```

Expected: `__init__.py`, `tesla_ble_vehicle.cpp`, `tesla_ble_vehicle.h`, and other source files.

---

### Task 2: Add polling mode select entity to ESPHome Python config

**Files:**
- Modify: `components/tesla_ble_vehicle/__init__.py`

- [ ] **Step 1: Add the polling mode select schema**

In `__init__.py`, add import for `select` platform and define the polling mode select. Find where other entities are registered (buttons, switches, etc.) and add:

```python
# Near the top with other imports
from esphome.components import select

# Polling mode options
POLLING_MODES = ["off", "lazy", "active", "close"]

# In the CONFIG_SCHEMA or entity registration section, add:
CONF_POLLING_MODE = "polling_mode"
```

Add a select entity definition in the entity data lists (following the existing pattern for buttons/switches):

```python
# Add to the selects list (or create one if it doesn't exist)
POLLING_MODE_SELECT = {
    "name": "Polling Mode",
    "id": "polling_mode",
    "icon": "mdi:timer-cog",
    "options": POLLING_MODES,
    "initial_option": "lazy",
    "optimistic": True,
}
```

- [ ] **Step 2: Wire the select entity to the C++ component**

In the `async_to_code()` function (or equivalent code generation function), add code to:
1. Create the select entity variable
2. Call `cg.add(var.set_polling_mode_select(select_var))` to pass the select to the C++ component

```python
# In the code generation section
polling_select = await select.new_select(
    config[CONF_POLLING_MODE],
    options=POLLING_MODES,
)
cg.add(var.set_polling_mode_select(polling_select))
```

- [ ] **Step 3: Verify the Python config compiles**

```bash
# Test that the ESPHome config validates (exact command depends on your ESPHome setup)
esphome config your-tesla-ble.yaml
```

---

### Task 3: Add polling mode support to C++ header

**Files:**
- Modify: `components/tesla_ble_vehicle/tesla_ble_vehicle.h`

- [ ] **Step 1: Add polling mode enum and select pointer**

Add near the top of the file (after existing includes):

```cpp
#include "esphome/components/select/select.h"
```

Inside the `TeslaBLEVehicle` class, add:

```cpp
 public:
  void set_polling_mode_select(select::Select *sel) { this->polling_mode_select_ = sel; }

 protected:
  // Polling mode control
  select::Select *polling_mode_select_{nullptr};

  enum class PollingMode : uint8_t {
    OFF = 0,
    LAZY = 1,
    ACTIVE = 2,
    CLOSE = 3,
  };

  PollingMode current_polling_mode_{PollingMode::LAZY};
  uint32_t polling_interval_ms_{1800000};  // 30 min default (lazy)

  // Lazy mode: connect-poll-disconnect state
  bool lazy_poll_pending_{false};
  uint32_t lazy_disconnect_after_ms_{30000};  // 30s grace after poll
  uint32_t lazy_poll_started_at_{0};

  PollingMode parse_polling_mode_(const std::string &mode);
  uint32_t get_polling_interval_ms_(PollingMode mode);
  void apply_polling_mode_(PollingMode mode);
```

- [ ] **Step 2: Commit**

```bash
git add components/tesla_ble_vehicle/tesla_ble_vehicle.h
git commit -m "feat: add polling mode fields and select pointer to header"
```

---

### Task 4: Implement polling mode logic in C++

**Files:**
- Modify: `components/tesla_ble_vehicle/tesla_ble_vehicle.cpp`

- [ ] **Step 1: Add polling mode helper methods**

Add these method implementations:

```cpp
TeslaBLEVehicle::PollingMode TeslaBLEVehicle::parse_polling_mode_(const std::string &mode) {
  if (mode == "off") return PollingMode::OFF;
  if (mode == "active") return PollingMode::ACTIVE;
  if (mode == "close") return PollingMode::CLOSE;
  return PollingMode::LAZY;  // default
}

uint32_t TeslaBLEVehicle::get_polling_interval_ms_(PollingMode mode) {
  switch (mode) {
    case PollingMode::OFF:    return 0;         // disabled
    case PollingMode::LAZY:   return 1800000;   // 30 min
    case PollingMode::ACTIVE: return 600000;    // 10 min
    case PollingMode::CLOSE:  return 300000;    // 5 min
    default:                  return 1800000;
  }
}

void TeslaBLEVehicle::apply_polling_mode_(PollingMode mode) {
  if (mode == this->current_polling_mode_) return;

  ESP_LOGI(TAG, "Polling mode changing: %d -> %d", (int)this->current_polling_mode_, (int)mode);
  this->current_polling_mode_ = mode;
  this->polling_interval_ms_ = this->get_polling_interval_ms_(mode);

  if (mode == PollingMode::OFF) {
    // Disconnect BLE, stop all polling
    ESP_LOGI(TAG, "Polling OFF — disconnecting BLE");
    this->parent()->set_enabled(false);
  } else if (mode == PollingMode::LAZY) {
    // Will connect on next poll tick, then disconnect after
    ESP_LOGI(TAG, "Polling LAZY — connect-poll-disconnect every 30 min");
    if (!this->parent()->enabled()) {
      // Don't connect yet — wait for next poll tick
    }
  } else {
    // ACTIVE or CLOSE — stay connected
    ESP_LOGI(TAG, "Polling %s — staying connected, interval %u ms",
             mode == PollingMode::ACTIVE ? "ACTIVE" : "CLOSE",
             this->polling_interval_ms_);
    if (!this->parent()->enabled()) {
      this->parent()->set_enabled(true);
    }
  }
}
```

- [ ] **Step 2: Hook select entity state changes into `setup()`**

In the `setup()` method, add a listener for the select entity state:

```cpp
if (this->polling_mode_select_ != nullptr) {
  this->polling_mode_select_->add_on_state_callback([this](const std::string &value, size_t index) {
    auto mode = this->parse_polling_mode_(value);
    this->apply_polling_mode_(mode);
  });
  // Set initial state
  this->polling_mode_select_->publish_state("lazy");
}
```

- [ ] **Step 3: Modify the `update()` method to respect polling mode**

Find the existing `update()` method. It currently has hardcoded interval checks using `Utils::has_elapsed()`. Replace the polling logic with mode-aware behavior:

```cpp
void TeslaBLEVehicle::update() {
  // If polling is off, skip everything
  if (this->current_polling_mode_ == PollingMode::OFF) {
    return;
  }

  uint32_t now = millis();

  // Lazy mode: handle connect-poll-disconnect cycle
  if (this->current_polling_mode_ == PollingMode::LAZY) {
    if (this->lazy_poll_pending_) {
      // We connected and polled — check if grace period expired
      if (Utils::has_elapsed(this->lazy_poll_started_at_, this->lazy_disconnect_after_ms_, now)) {
        ESP_LOGI(TAG, "Lazy mode: grace period expired, disconnecting");
        this->parent()->set_enabled(false);
        this->lazy_poll_pending_ = false;
      }
      return;
    }

    // Check if it's time for a new poll
    if (Utils::has_elapsed(this->last_vcsec_poll_, this->polling_interval_ms_, now)) {
      ESP_LOGI(TAG, "Lazy mode: connecting for poll");
      this->parent()->set_enabled(true);
      this->lazy_poll_pending_ = true;
      this->lazy_poll_started_at_ = now;
      // Fall through to do the actual poll below
    } else {
      return;
    }
  }

  // ACTIVE/CLOSE/LAZY(just connected): do the actual polling
  // Use polling_interval_ms_ for both VCSEC and infotainment
  if (Utils::has_elapsed(this->last_vcsec_poll_, this->polling_interval_ms_, now)) {
    // ... existing VCSEC poll code ...
  }

  if (Utils::has_elapsed(this->last_infotainment_poll_, this->polling_interval_ms_, now)) {
    // ... existing infotainment poll code ...
  }
}
```

The exact integration depends on the existing `update()` structure — the key changes are:
1. Early return if `OFF`
2. Connect/disconnect cycle for `LAZY`
3. Use `polling_interval_ms_` instead of hardcoded intervals for both poll types

- [ ] **Step 4: Ensure commands still work in OFF/LAZY mode**

In command methods (e.g., `set_charging_state()`, `set_charging_amps()`, `wake()`), add reconnect logic:

```cpp
// At the start of command methods, ensure BLE is connected
if (!this->parent()->enabled()) {
  ESP_LOGI(TAG, "Reconnecting BLE for command delivery");
  this->parent()->set_enabled(true);
  // The command will be queued and sent once connected
}
```

The existing BLE write queue should handle the case where a command is issued before the connection is fully established — verify this in the existing `BleAdapterImpl` code.

- [ ] **Step 5: Commit**

```bash
git add components/tesla_ble_vehicle/tesla_ble_vehicle.cpp
git commit -m "feat: implement polling mode logic — off/lazy/active/close"
```

---

### Task 5: Add constants for BLE polling mode to HA integration

**Files:**
- Modify: `custom_components/tesla_solar_charging/const.py`

- [ ] **Step 1: Add polling mode constants**

Add after the existing BLE config keys:

```python
# Config keys — BLE polling mode
CONF_BLE_POLLING_MODE_ENTITY = "ble_polling_mode_entity"

# Polling modes
POLLING_MODE_OFF = "off"
POLLING_MODE_LAZY = "lazy"
POLLING_MODE_ACTIVE = "active"
POLLING_MODE_CLOSE = "close"

# SOC threshold for switching active -> close (percentage points below limit)
POLLING_SOC_CLOSE_THRESHOLD = 2
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/tesla_solar_charging/const.py
git commit -m "feat: add BLE polling mode constants"
```

---

### Task 6: Add `set_polling_mode()` to BLEController

**Files:**
- Modify: `custom_components/tesla_solar_charging/ble_controller.py`
- Test: `tests/test_ble_polling.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ble_polling.py`:

```python
"""Tests for BLE polling mode control."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tesla_solar_charging.ble_controller import BLEController


class TestBLEPollingMode:
    def _make_controller(self, polling_mode_entity="select.tesla_ble_polling_mode"):
        hass = MagicMock()
        hass.services = MagicMock()
        hass.services.async_call = AsyncMock()
        ble = BLEController(
            hass=hass,
            charger_switch="switch.tesla_ble_charger",
            charging_amps="number.tesla_ble_charging_amps",
            wake_button="button.tesla_ble_wake_up",
            polling_mode_entity=polling_mode_entity,
        )
        return ble, hass

    @pytest.mark.asyncio
    async def test_set_polling_mode_calls_select_service(self):
        ble, hass = self._make_controller()
        await ble.set_polling_mode("active")
        hass.services.async_call.assert_called_once_with(
            "select", "select_option",
            {"entity_id": "select.tesla_ble_polling_mode", "option": "active"},
            blocking=True,
        )

    @pytest.mark.asyncio
    async def test_set_polling_mode_off(self):
        ble, hass = self._make_controller()
        await ble.set_polling_mode("off")
        hass.services.async_call.assert_called_once_with(
            "select", "select_option",
            {"entity_id": "select.tesla_ble_polling_mode", "option": "off"},
            blocking=True,
        )

    @pytest.mark.asyncio
    async def test_set_polling_mode_no_entity_is_noop(self):
        ble, hass = self._make_controller(polling_mode_entity=None)
        await ble.set_polling_mode("active")
        hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_polling_mode_records_failure(self):
        ble, hass = self._make_controller()
        hass.services.async_call.side_effect = Exception("BLE timeout")
        with pytest.raises(Exception, match="BLE timeout"):
            await ble.set_polling_mode("active")
        assert ble.consecutive_failures == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:/Projects/Projects/personal/ok/ha-tesla-solar-charging
python -m pytest tests/test_ble_polling.py -v
```

Expected: FAIL — `BLEController.__init__()` doesn't accept `polling_mode_entity`.

- [ ] **Step 3: Implement the changes to BLEController**

Modify `custom_components/tesla_solar_charging/ble_controller.py`:

```python
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
```

Add the `set_polling_mode()` method after `wake()`:

```python
    async def set_polling_mode(self, mode: str) -> None:
        """Set the ESP32 BLE polling mode via select entity."""
        if not self.polling_mode_entity:
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_ble_polling.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ble_polling.py custom_components/tesla_solar_charging/ble_controller.py
git commit -m "feat: add set_polling_mode() to BLEController"
```

---

### Task 7: Add `_determine_polling_mode()` to coordinator

**Files:**
- Modify: `custom_components/tesla_solar_charging/coordinator.py`
- Test: `tests/test_ble_polling.py` (extend)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ble_polling.py`:

```python
from tesla_solar_charging.coordinator import SolarChargingCoordinator
from tesla_solar_charging.const import (
    CONF_PLANNING_TIME,
    CONF_TESLA_BATTERY_ENTITY,
    POLLING_MODE_OFF,
    POLLING_MODE_LAZY,
    POLLING_MODE_ACTIVE,
    POLLING_MODE_CLOSE,
    POLLING_SOC_CLOSE_THRESHOLD,
    STATE_CHARGING_SOLAR,
    STATE_CHARGING_NIGHT,
    STATE_IDLE,
    STATE_WAITING,
)


class TestDeterminePollingMode:
    """Tests for coordinator._determine_polling_mode()."""

    def _make_coordinator(self, enabled=True, state=STATE_IDLE, force_charge=False,
                          is_home=True, sun_up=True, tesla_soc=50.0,
                          tesla_limit=80.0, planning_time="20:00",
                          night_charge_planned=False):
        hass = MagicMock()
        ble = MagicMock()
        inverter = MagicMock()
        entry_data = {
            CONF_PLANNING_TIME: planning_time,
        }
        coord = SolarChargingCoordinator(hass, "test_entry", entry_data, ble, inverter)
        coord._enabled = enabled
        coord._state = state
        coord._force_charge = force_charge
        coord._night_charge_planned = night_charge_planned
        # Mock internal methods
        coord._is_home = MagicMock(return_value=is_home)
        # Mock tesla SOC/limit
        coord._last_tesla_soc = tesla_soc
        coord._last_tesla_limit = tesla_limit
        return coord

    def test_disabled_returns_off(self):
        coord = self._make_coordinator(enabled=False)
        assert coord._determine_polling_mode(sun_up=True) == POLLING_MODE_OFF

    def test_night_not_charging_returns_off(self):
        coord = self._make_coordinator(state=STATE_WAITING)
        assert coord._determine_polling_mode(sun_up=False) == POLLING_MODE_OFF

    def test_night_force_charge_far_from_limit_returns_active(self):
        coord = self._make_coordinator(state=STATE_CHARGING_SOLAR, force_charge=True,
                                       tesla_soc=50.0, tesla_limit=80.0)
        assert coord._determine_polling_mode(sun_up=False) == POLLING_MODE_ACTIVE

    def test_night_force_charge_near_limit_returns_close(self):
        coord = self._make_coordinator(state=STATE_CHARGING_SOLAR, force_charge=True,
                                       tesla_soc=79.0, tesla_limit=80.0)
        assert coord._determine_polling_mode(sun_up=False) == POLLING_MODE_CLOSE

    def test_night_charging_octopus_returns_active(self):
        coord = self._make_coordinator(state=STATE_CHARGING_NIGHT,
                                       tesla_soc=50.0, tesla_limit=80.0,
                                       night_charge_planned=True)
        assert coord._determine_polling_mode(sun_up=False) == POLLING_MODE_ACTIVE

    def test_car_not_home_returns_off(self):
        coord = self._make_coordinator(is_home=False)
        assert coord._determine_polling_mode(sun_up=True) == POLLING_MODE_OFF

    def test_day_not_charging_returns_lazy(self):
        coord = self._make_coordinator(state=STATE_WAITING)
        assert coord._determine_polling_mode(sun_up=True) == POLLING_MODE_LAZY

    def test_day_idle_returns_lazy(self):
        coord = self._make_coordinator(state=STATE_IDLE)
        assert coord._determine_polling_mode(sun_up=True) == POLLING_MODE_LAZY

    def test_charging_far_from_limit_returns_active(self):
        coord = self._make_coordinator(state=STATE_CHARGING_SOLAR,
                                       tesla_soc=50.0, tesla_limit=80.0)
        assert coord._determine_polling_mode(sun_up=True) == POLLING_MODE_ACTIVE

    def test_charging_near_limit_returns_close(self):
        coord = self._make_coordinator(state=STATE_CHARGING_SOLAR,
                                       tesla_soc=78.5, tesla_limit=80.0)
        assert coord._determine_polling_mode(sun_up=True) == POLLING_MODE_CLOSE

    def test_charging_exactly_at_threshold_returns_close(self):
        coord = self._make_coordinator(state=STATE_CHARGING_SOLAR,
                                       tesla_soc=78.0, tesla_limit=80.0)
        assert coord._determine_polling_mode(sun_up=True) == POLLING_MODE_CLOSE

    def test_charging_just_outside_threshold_returns_active(self):
        coord = self._make_coordinator(state=STATE_CHARGING_SOLAR,
                                       tesla_soc=77.9, tesla_limit=80.0)
        assert coord._determine_polling_mode(sun_up=True) == POLLING_MODE_ACTIVE

    def test_no_tesla_soc_defaults_to_active_when_charging(self):
        coord = self._make_coordinator(state=STATE_CHARGING_SOLAR,
                                       tesla_soc=None, tesla_limit=80.0)
        assert coord._determine_polling_mode(sun_up=True) == POLLING_MODE_ACTIVE
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_ble_polling.py::TestDeterminePollingMode -v
```

Expected: FAIL — `_determine_polling_mode` doesn't exist, `_last_tesla_soc` doesn't exist.

- [ ] **Step 3: Implement `_determine_polling_mode()` in coordinator**

Add to `coordinator.py` imports:

```python
from .const import (
    # ... existing imports ...
    CONF_PLANNING_TIME,
    POLLING_MODE_OFF,
    POLLING_MODE_LAZY,
    POLLING_MODE_ACTIVE,
    POLLING_MODE_CLOSE,
    POLLING_SOC_CLOSE_THRESHOLD,
)
```

Add new instance variables in `__init__`:

```python
self._current_polling_mode: str = POLLING_MODE_LAZY
self._last_tesla_soc: float | None = None
self._last_tesla_limit: float | None = None
```

Add the method:

```python
def _determine_polling_mode(self, sun_up: bool) -> str:
    """Determine the desired BLE polling mode based on current state."""
    # Disabled → off
    if not self._enabled:
        return POLLING_MODE_OFF

    # Car not home → off
    if not self._is_home():
        return POLLING_MODE_OFF

    is_charging = self._state in (STATE_CHARGING_SOLAR, STATE_CHARGING_NIGHT)

    # Night rules
    if not sun_up:
        if not is_charging and not self._force_charge and not self._night_charge_planned:
            return POLLING_MODE_OFF

    # Not charging → lazy (daytime) or off (night, handled above)
    if not is_charging and not self._force_charge:
        return POLLING_MODE_LAZY

    # Charging or force charge — check SOC proximity
    if self._last_tesla_soc is not None and self._last_tesla_limit is not None:
        gap = self._last_tesla_limit - self._last_tesla_soc
        if gap <= POLLING_SOC_CLOSE_THRESHOLD:
            return POLLING_MODE_CLOSE

    return POLLING_MODE_ACTIVE
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_ble_polling.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ble_polling.py custom_components/tesla_solar_charging/coordinator.py
git commit -m "feat: add _determine_polling_mode() to coordinator"
```

---

### Task 8: Wire polling mode into the coordinator's main loop

**Files:**
- Modify: `custom_components/tesla_solar_charging/coordinator.py`

- [ ] **Step 1: Update `_async_update_data()` to set polling mode**

At the top of `_async_update_data()`, after the `if not self._enabled` check, add:

```python
# Determine and apply BLE polling mode
sun_up = is_up(self.hass)
desired_mode = self._determine_polling_mode(sun_up)
if desired_mode != self._current_polling_mode:
    try:
        await self._ble.set_polling_mode(desired_mode)
        self._current_polling_mode = desired_mode
        _LOGGER.info("BLE polling mode changed to: %s", desired_mode)
    except Exception as err:
        _LOGGER.warning("Failed to set polling mode: %s", err)
```

Note: this must go AFTER the `if not self._enabled: return {}` check but BEFORE the BLE health check, because we want to set `off` mode even if BLE is unhealthy.

Actually, reconsider — if disabled, we need to set `off` first. Restructure:

```python
async def _async_update_data(self) -> dict:
    # Always update polling mode, even when disabled
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

    # ... rest of existing logic ...
```

- [ ] **Step 2: Track Tesla SOC and limit for polling decisions**

In `_handle_solar_mode()`, after reading `tesla_battery` and `tesla_limit`, store them:

```python
# After the existing lines that read tesla_battery and tesla_limit:
self._last_tesla_soc = tesla_battery
self._last_tesla_limit = tesla_limit
```

In `_handle_night_mode()`, also read and store Tesla SOC if available:

```python
# At the start of _handle_night_mode, read Tesla SOC for polling mode decisions
if self._entry_data.get(CONF_TESLA_BATTERY_ENTITY):
    self._last_tesla_soc = self._get_float(self._entry_data[CONF_TESLA_BATTERY_ENTITY])
self._last_tesla_limit = self._get_own_float("charge_limit")
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/tesla_solar_charging/coordinator.py
git commit -m "feat: wire polling mode into coordinator main loop"
```

---

### Task 9: Add pre-planner polling wake-up

**Files:**
- Modify: `custom_components/tesla_solar_charging/__init__.py`

- [ ] **Step 1: Schedule lazy mode 10 min before planner**

In `_async_setup_charging_entry()`, after the planner scheduling code, add a pre-planner wake-up:

```python
# Schedule pre-planner BLE wake-up (10 min before planner)
pre_plan_hour = hour
pre_plan_minute = minute - 10
if pre_plan_minute < 0:
    pre_plan_minute += 60
    pre_plan_hour = (pre_plan_hour - 1) % 24

async def _pre_planner_wake(now):
    """Switch to lazy mode to grab fresh Tesla SOC before planner runs."""
    from .const import POLLING_MODE_LAZY
    if coordinator._current_polling_mode == "off":
        try:
            await coordinator._ble.set_polling_mode(POLLING_MODE_LAZY)
            coordinator._current_polling_mode = POLLING_MODE_LAZY
            _LOGGER.info("Pre-planner: switched to lazy polling for SOC grab")
        except Exception as err:
            _LOGGER.warning("Pre-planner: failed to set lazy mode: %s", err)

unsub_pre_planner = async_track_time_change(
    hass, _pre_planner_wake, hour=pre_plan_hour, minute=pre_plan_minute, second=0
)
entry.async_on_unload(unsub_pre_planner)
```

- [ ] **Step 2: After planner executes, return to off if no night charge**

In `_execute_planner()`, at the end, after setting `coordinator.night_charge_planned`:

```python
# After planner decision, set polling mode back to off if no night charge
from .const import POLLING_MODE_OFF
if not plan.charge_tonight:
    try:
        await coordinator._ble.set_polling_mode(POLLING_MODE_OFF)
        coordinator._current_polling_mode = POLLING_MODE_OFF
        _LOGGER.info("Post-planner: no night charge, polling set to off")
    except Exception as err:
        _LOGGER.warning("Post-planner: failed to set polling mode: %s", err)
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/tesla_solar_charging/__init__.py
git commit -m "feat: add pre-planner BLE wake-up and post-planner sleep"
```

---

### Task 10: Add polling mode entity to config flow

**Files:**
- Modify: `custom_components/tesla_solar_charging/config_flow.py`
- Modify: `custom_components/tesla_solar_charging/const.py` (already done in Task 5)

- [ ] **Step 1: Add polling mode entity field to config flow step 1**

In `config_flow.py`, in `async_step_charging_sensors()`, add after the BLE wake button field:

```python
vol.Optional(CONF_BLE_POLLING_MODE_ENTITY): SELECT_SELECTOR,
```

Add the import at the top:

```python
from .const import (
    # ... existing imports ...
    CONF_BLE_POLLING_MODE_ENTITY,
)
```

- [ ] **Step 2: Add to options flow step 1**

In `TeslaSolarChargingOptionsFlow.async_step_init()`, add:

```python
vol.Optional(CONF_BLE_POLLING_MODE_ENTITY, default=data.get(CONF_BLE_POLLING_MODE_ENTITY, "")): SELECT_SELECTOR,
```

- [ ] **Step 3: Wire the entity into BLEController initialization**

In `__init__.py`, in `_async_setup_charging_entry()`, update the BLEController construction:

```python
ble = BLEController(
    hass=hass,
    charger_switch=data[CONF_BLE_CHARGER_SWITCH],
    charging_amps=data[CONF_BLE_CHARGING_AMPS],
    wake_button=data[CONF_BLE_WAKE_BUTTON],
    polling_mode_entity=data.get(CONF_BLE_POLLING_MODE_ENTITY),
)
```

Add the import:

```python
from .const import (
    # ... existing imports ...
    CONF_BLE_POLLING_MODE_ENTITY,
)
```

- [ ] **Step 4: Commit**

```bash
git add custom_components/tesla_solar_charging/config_flow.py custom_components/tesla_solar_charging/__init__.py
git commit -m "feat: add polling mode entity to config flow and wire into BLEController"
```

---

### Task 11: Run all existing tests to verify no regressions

**Files:**
- No changes

- [ ] **Step 1: Run the full test suite**

```bash
cd C:/Projects/Projects/personal/ok/ha-tesla-solar-charging
python -m pytest tests/ -v
```

Expected: All tests PASS. The existing tests don't mock `BLEController.__init__` with positional args, but check. If any fail due to the new `polling_mode_entity` parameter, fix them by adding `polling_mode_entity=None` to the mocked constructors.

- [ ] **Step 2: Fix any test failures**

If existing tests construct `BLEController` without the new param, they should still work because `polling_mode_entity` defaults to `None`. If any test breaks, add the kwarg.

- [ ] **Step 3: Commit fixes if needed**

```bash
git add tests/
git commit -m "fix: update existing tests for new BLEController parameter"
```

---

### Task 12: Update ESPHome device YAML to use the fork

**Files:**
- The user's ESPHome YAML (not in this repo — separate ESPHome config)

- [ ] **Step 1: Update the external_components source**

Change:
```yaml
external_components:
  - components: [tesla_ble_vehicle]
    source:
      type: git
      url: https://github.com/yoziru/esphome-tesla-ble.git
      ref: main
      path: components
```

To:
```yaml
external_components:
  - components: [tesla_ble_vehicle]
    source:
      type: git
      url: https://github.com/black2vs2/esphome-tesla-ble.git
      ref: main
      path: components
```

- [ ] **Step 2: Flash the ESP32**

```bash
esphome run tesla-ble.yaml
```

Verify the new `select.tesla_ble_polling_mode` entity appears in Home Assistant.

- [ ] **Step 3: Configure the entity in the HA integration**

Go to Settings → Integrations → Tesla Solar Charging → Configure. Set the "BLE Polling Mode" entity to `select.tesla_ble_polling_mode`.

---

### Task 13: Integration test — verify end-to-end behavior

**Files:**
- No code changes, manual testing

- [ ] **Step 1: Verify OFF mode**

Set integration to disabled. Check:
- `select.tesla_ble_polling_mode` shows `off`
- ESP32 logs show "Polling OFF — disconnecting BLE"
- Tesla goes to sleep within ~15 min

- [ ] **Step 2: Verify LAZY mode**

Enable integration during daytime, car not charging. Check:
- `select.tesla_ble_polling_mode` shows `lazy`
- ESP32 connects every ~30 min, grabs data, disconnects
- Tesla SOC sensor updates every ~30 min

- [ ] **Step 3: Verify ACTIVE mode**

Start solar charging with car at 50% (limit 80%). Check:
- Mode switches to `active`
- Polling every ~10 min
- BLE stays connected

- [ ] **Step 4: Verify CLOSE mode**

Wait until car SOC reaches within 2% of limit (or set limit to current SOC + 2%). Check:
- Mode switches to `close`
- Polling every ~5 min

- [ ] **Step 5: Verify pre-planner wake-up**

Wait for 10 min before planner time. Check:
- Mode switches from `off` to `lazy`
- Fresh SOC is available when planner runs at the configured time
- After planner (if no night charge), mode returns to `off`
