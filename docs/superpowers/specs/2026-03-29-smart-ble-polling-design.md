# Smart BLE Polling — Design Spec

**Date:** 2026-03-29
**Problem:** The ESPHome Tesla BLE component polls aggressively (VCSEC every 10s, infotainment every 30s), constantly waking the Tesla and draining its 12V battery — even when no charging is happening.

**Solution:** Fork `yoziru/esphome-tesla-ble`, add an HA-controllable polling mode select entity. The HA coordinator sets the mode based on charging state, time of day, and SOC proximity to charge limit.

## Polling Modes

| Mode | VCSEC Interval | Infotainment Interval | BLE Connection | When Used |
|------|---------------|----------------------|----------------|-----------|
| `off` | disabled | disabled | disconnected | Night + not charging + not force; integration disabled; car away |
| `lazy` | 30 min | 30 min | connect → poll → disconnect | Daytime not charging; pre-planner SOC grab |
| `active` | 10 min | 10 min | stay connected | Charging, SOC more than 2% below limit |
| `close` | 5 min | 5 min | stay connected | Charging, SOC within 2% of limit |

Default on ESP32 boot: `lazy`.

## ESP32 Firmware Changes (Fork)

**Repo:** Fork `yoziru/esphome-tesla-ble` → `black2vs2/esphome-tesla-ble`

### New Select Entity

`select.tesla_ble_polling_mode` with options: `off`, `lazy`, `active`, `close`.

### Polling Behavior

- **`off`:** Stop all polling timers. Disconnect BLE. No scanning. Car sleeps fully.
- **`lazy`:** On each 30-min tick: connect BLE → run VCSEC + infotainment poll → disconnect BLE. Car can sleep between polls.
- **`active`:** Stay connected. Poll both VCSEC and infotainment every 10 min.
- **`close`:** Stay connected. Poll both VCSEC and infotainment every 5 min.

### Command Handling

Commands (start/stop charging, set amps, wake) always work regardless of polling mode:
- If BLE is disconnected (`off`/`lazy` between polls), the ESP32 connects first, delivers the command, then disconnects after a ~30s grace period.
- The HA coordinator is responsible for setting an appropriate mode (e.g., `active`) before sending charge commands, so it should not normally need to send commands in `off` mode.

### C++ Changes

Modify `tesla_ble_vehicle.cpp`:
- Replace hardcoded poll intervals in `update()` with mode-dependent intervals.
- Add BLE disconnect logic for `off` and `lazy` (post-poll disconnect).
- Register the select entity in `__init__.py` and wire it to the C++ component.
- On mode change, immediately adjust timers (don't wait for next tick).

## HA Integration Changes

### `ble_controller.py`

New method:
```python
async def set_polling_mode(self, mode: str) -> None:
    """Set the ESP32 polling mode via select entity."""
    await self.hass.services.async_call(
        "select", "select_option",
        {"entity_id": self.polling_mode_entity, "option": mode},
        blocking=True,
    )
```

Constructor accepts a new `polling_mode_entity: str` parameter (e.g., `select.tesla_ble_polling_mode`).

### `coordinator.py`

New internal state: `_current_polling_mode: str = "lazy"`.

New method `_determine_polling_mode()` returns the desired mode based on:

| Condition | Mode |
|-----------|------|
| `enabled=False` | `off` |
| Night + not charging + not force charge | `off` |
| Car not at home | `off` |
| Daytime + not charging | `lazy` |
| Pre-planner window (planner_time - 10 min) | `lazy` |
| Post-planner (after planner_time) + no night charge planned | `off` |
| Charging + SOC > 2% below limit | `active` |
| Charging + SOC ≤ 2% below limit | `close` |

At the top of `_async_update_data()`:
1. Call `_determine_polling_mode()`
2. If mode changed from `_current_polling_mode`, call `ble.set_polling_mode(new_mode)`
3. Update `_current_polling_mode`

### `config_flow.py`

Add optional field for the polling mode select entity ID in the config flow (step where BLE entities are configured).

### Command Sequencing

When the coordinator needs to send a charge command while in `off` mode:
1. Set polling mode to `active` (or `close`)
2. Wait one coordinator cycle (~30s) for BLE to connect
3. Send the charge command on the next cycle

## ESPHome YAML Changes

Update the external component source to the fork:
```yaml
external_components:
  - components: [tesla_ble_vehicle]
    source:
      type: git
      url: https://github.com/black2vs2/esphome-tesla-ble.git
      ref: main
      path: components
```

No additional YAML needed — the polling mode select is registered by the component.

## Edge Cases

- **ESP32 reboot:** Defaults to `lazy`. HA sets correct mode on next 30s tick.
- **HA restart:** Coordinator re-evaluates immediately and sets mode.
- **Car leaves home:** Coordinator sets `off`. BLE will fail anyway (out of range), but stops scanning.
- **Force charge at night:** Coordinator sets `active`/`close`, starts charging.
- **Planner SOC grab:** At planner_time - 10 min, set `lazy`. After planner runs, set `off` (unless night charge planned → then `active`/`close` when Octopus dispatches).
- **SOC crosses 2% threshold during charge:** Coordinator upgrades from `active` → `close` on next tick.
- **Charge completes (car hits limit):** Coordinator stops charging, sets `lazy` (daytime) or `off` (night).

## Scope

### In scope
- Fork and modify `esphome-tesla-ble` C++ component (polling mode select, adaptive intervals, BLE disconnect)
- Update `__init__.py` (ESPHome component Python config)
- Update HA integration (`ble_controller.py`, `coordinator.py`, `config_flow.py`)
- Update ESPHome device YAML to point to fork

### Out of scope
- Changes to charging logic (`charging_logic.py`)
- Changes to forecast/planner logic
- Frontend panel changes
- Any other Tesla BLE component features (locks, climate, etc.)
