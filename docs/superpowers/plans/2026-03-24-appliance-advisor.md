# Appliance Advisor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an isolated appliance advisor module that shows per-appliance traffic-light recommendations based on solar surplus, with a custom Lovelace card for tablet display and a debug tab in the existing panel.

**Architecture:** Self-contained `appliance_advisor/` subpackage inside the integration. Pure logic in `advisor.py` (no HA deps), sensor entities expose recommendations, custom Lovelace card renders the tablet-optimized dashboard. Appliances are fully dynamic (user-configurable, multiples allowed). Deadlines stored via HA Store (not config entry) to avoid reload on change.

**Tech Stack:** Python 3.12, Home Assistant custom integration APIs, vanilla JS web component (Lovelace card)

**Spec:** `docs/superpowers/specs/2026-03-24-appliance-advisor-design.md`

**Key codebase patterns:**
- Tests: pure-function style, `conftest.py` mocks all HA modules, import via `from tesla_solar_charging.xxx import ...`
- Sensors: `CoordinatorEntity` + `SensorEntity`, `_attr_unique_id = f"{entry.entry_id}_{suffix}"`
- Config flow: steps chain via `return await self.async_step_next()`, data accumulates in `self._options`
- Coordinator: `_entry_data` is merged `{**entry.data, **entry.options}`, `_get_float(entity_id)` reads sensors
- Panel: vanilla web component, `customElements.define` guarded with `.get()` check

---

### Task 1: Models — EnergyState, ApplianceConfig, Recommendation

**Files:**
- Create: `custom_components/tesla_solar_charging/appliance_advisor/__init__.py`
- Create: `custom_components/tesla_solar_charging/appliance_advisor/models.py`
- Test: `tests/test_advisor_models.py`

- [ ] **Step 1: Create empty package**

```python
"""Appliance Advisor — solar-aware appliance scheduling recommendations."""
```

- [ ] **Step 2: Write failing tests for models**

```python
"""Tests for appliance_advisor models — pure dataclasses."""

from tesla_solar_charging.appliance_advisor.models import (
    EnergyState, ApplianceConfig, DeadlineConfig, Recommendation, Status,
)


class TestEnergyState:
    def test_create_with_all_fields(self):
        state = EnergyState(solar_w=4200.0, grid_export_w=2000.0, battery_soc=85.0,
                            battery_power_w=500.0, tesla_charging_w=0.0)
        assert state.grid_export_w == 2000.0

    def test_solar_w_defaults_to_none(self):
        state = EnergyState(grid_export_w=2000.0, battery_soc=85.0,
                            battery_power_w=500.0, tesla_charging_w=0.0)
        assert state.solar_w is None


class TestApplianceConfig:
    def test_create_with_defaults(self):
        cfg = ApplianceConfig(key="dw_1", name="Lavastoviglie", icon="X", watts=2000)
        assert cfg.duration_minutes == 0
        assert cfg.power_entity is None
        assert cfg.running_threshold_w == 30.0

    def test_create_with_power_entity(self):
        cfg = ApplianceConfig(key="dw_1", name="Lavastoviglie", icon="X", watts=2000,
                              power_entity="sensor.plug_dw", running_threshold_w=50.0)
        assert cfg.power_entity == "sensor.plug_dw"


class TestRecommendation:
    def test_create_green(self):
        rec = Recommendation(appliance_key="dw_1", status=Status.GREEN,
                             cost_label="Gratis", reason="OK", appliance_name="Test", appliance_icon="X")
        assert rec.status == Status.GREEN
        assert rec.running is None
```

- [ ] **Step 3: Run tests — expect FAIL** (`python -m pytest tests/test_advisor_models.py -v`)

- [ ] **Step 4: Implement models.py**

```python
"""Dataclasses for the appliance advisor module."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class Status(Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


@dataclass
class EnergyState:
    grid_export_w: float
    battery_soc: float
    battery_power_w: float
    tesla_charging_w: float
    solar_w: float | None = None


@dataclass
class ApplianceConfig:
    key: str
    name: str
    icon: str
    watts: int
    duration_minutes: int = 0
    power_entity: str | None = None
    running_threshold_w: float = 30.0


@dataclass
class DeadlineConfig:
    deadline_type: str = "none"
    time: str | None = None


@dataclass
class Recommendation:
    appliance_key: str
    status: Status
    cost_label: str
    reason: str
    appliance_name: str
    appliance_icon: str
    running: bool | None = None
    current_watts: float | None = None
    deadline_message: str | None = None
    latest_start_time: str | None = None
```

- [ ] **Step 5: Run tests — expect PASS** (`python -m pytest tests/test_advisor_models.py -v`)

- [ ] **Step 6: Commit**

```bash
git add custom_components/tesla_solar_charging/appliance_advisor/__init__.py \
        custom_components/tesla_solar_charging/appliance_advisor/models.py \
        tests/test_advisor_models.py
git commit -m "feat(advisor): add models — EnergyState, ApplianceConfig, Recommendation"
```

---

### Task 2: Constants — Presets and Thresholds

**Files:**
- Create: `custom_components/tesla_solar_charging/appliance_advisor/const.py`

- [ ] **Step 1: Create constants file**

```python
"""Constants for the appliance advisor module."""

# Presets for quick-adding appliances (users pick a preset, then customize)
APPLIANCE_PRESETS = {
    "dishwasher":      {"name": "Lavastoviglie", "icon": "\U0001f37d\ufe0f", "watts": 2000, "duration": 120},
    "washing_machine": {"name": "Lavatrice",     "icon": "\U0001f455",       "watts": 2000, "duration": 90},
    "oven":            {"name": "Forno",          "icon": "\U0001f525",       "watts": 2500, "duration": 60},
    "dryer":           {"name": "Asciugatrice",   "icon": "\U0001f4a8",       "watts": 2500, "duration": 90},
    "ac":              {"name": "Condizionatore", "icon": "\u2744\ufe0f",     "watts": 1000, "duration": 0},
    "custom":          {"name": "Altro",          "icon": "\U0001f50c",       "watts": 1500, "duration": 60},
}

GREEN_THRESHOLD = 1.1
YELLOW_THRESHOLD = 0.5
BATTERY_NEAR_FULL_SOC = 95.0
BATTERY_NEAR_FULL_FACTOR = 0.5
DEADLINE_URGENT_MINUTES = 30
DEFAULT_RUNNING_THRESHOLD_W = 30.0
DEADLINE_STORE_KEY = "tesla_solar_charging.advisor_deadlines"
DEADLINE_STORE_VERSION = 1
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/tesla_solar_charging/appliance_advisor/const.py
git commit -m "feat(advisor): add constants — presets and thresholds"
```

---

### Task 3: Core Logic — Surplus and Traffic Light

**Files:**
- Create: `custom_components/tesla_solar_charging/appliance_advisor/advisor.py`
- Test: `tests/test_advisor.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for appliance_advisor.advisor — pure logic, no HA dependency."""

from tesla_solar_charging.appliance_advisor.models import (
    ApplianceConfig, DeadlineConfig, EnergyState, Recommendation, Status,
)
from tesla_solar_charging.appliance_advisor.advisor import (
    calculate_surplus, evaluate_appliance, evaluate,
)


def _energy(export=0.0, batt_soc=50.0, batt_power=0.0, tesla=0.0):
    return EnergyState(grid_export_w=export, battery_soc=batt_soc,
                       battery_power_w=batt_power, tesla_charging_w=tesla)


def _app(key="dw_1", watts=2000, name="Test", icon="X"):
    return ApplianceConfig(key=key, name=name, icon=icon, watts=watts)


class TestCalculateSurplus:
    def test_export_only(self):
        assert calculate_surplus(_energy(export=3000.0)) == 3000.0

    def test_subtracts_tesla(self):
        assert calculate_surplus(_energy(export=3000.0, tesla=1000.0)) == 2000.0

    def test_battery_near_full_adds_half_charge(self):
        assert calculate_surplus(_energy(export=1000.0, batt_soc=96.0, batt_power=1000.0)) == 1500.0

    def test_battery_not_near_full_ignores_charge(self):
        assert calculate_surplus(_energy(export=1000.0, batt_soc=80.0, batt_power=1000.0)) == 1000.0

    def test_battery_discharging_not_added(self):
        assert calculate_surplus(_energy(export=1000.0, batt_soc=96.0, batt_power=-500.0)) == 1000.0

    def test_negative_surplus_clamped_to_zero(self):
        assert calculate_surplus(_energy(export=0.0, tesla=1000.0)) == 0.0


class TestEvaluateAppliance:
    def test_green(self):
        rec = evaluate_appliance(_energy(), _app(watts=2000), surplus=2500.0)
        assert rec.status == Status.GREEN
        assert rec.cost_label == "Gratis"

    def test_yellow(self):
        rec = evaluate_appliance(_energy(), _app(watts=2000), surplus=1200.0)
        assert rec.status == Status.YELLOW

    def test_red(self):
        rec = evaluate_appliance(_energy(), _app(watts=2000), surplus=500.0)
        assert rec.status == Status.RED

    def test_green_threshold_boundary(self):
        # 2000 * 1.1 = 2200
        assert evaluate_appliance(_energy(), _app(watts=2000), surplus=2199.0).status == Status.YELLOW
        assert evaluate_appliance(_energy(), _app(watts=2000), surplus=2200.0).status == Status.GREEN

    def test_octopus_upgrades_red(self):
        rec = evaluate_appliance(_energy(), _app(watts=2000), surplus=0.0, is_octopus_dispatching=True)
        assert rec.status == Status.YELLOW
        assert "Tariffa" in rec.reason

    def test_includes_name_and_icon(self):
        rec = evaluate_appliance(_energy(), _app(name="Forno", icon="F"), surplus=5000.0)
        assert rec.appliance_name == "Forno"
        assert rec.appliance_icon == "F"


class TestEvaluateAll:
    def test_returns_one_per_appliance(self):
        recs = evaluate(_energy(export=5000.0), [_app("a", 1000), _app("b", 2000)])
        assert len(recs) == 2
        assert recs[0].appliance_key == "a"

    def test_running_states_passed_through(self):
        recs = evaluate(_energy(export=5000.0), [_app("a", 1000)],
                        running_states={"a": (True, 950.0)})
        assert recs[0].running is True
        assert recs[0].current_watts == 950.0
```

- [ ] **Step 2: Run tests — expect FAIL** (`python -m pytest tests/test_advisor.py -v`)

- [ ] **Step 3: Implement advisor.py**

```python
"""Core advisor logic — pure functions, no HA dependency."""
from __future__ import annotations

from .const import (BATTERY_NEAR_FULL_FACTOR, BATTERY_NEAR_FULL_SOC,
                    GREEN_THRESHOLD, YELLOW_THRESHOLD)
from .models import ApplianceConfig, EnergyState, Recommendation, Status


def calculate_surplus(state: EnergyState) -> float:
    surplus = state.grid_export_w
    if state.battery_soc > BATTERY_NEAR_FULL_SOC and state.battery_power_w > 0:
        surplus += state.battery_power_w * BATTERY_NEAR_FULL_FACTOR
    surplus -= state.tesla_charging_w
    return max(surplus, 0.0)


def evaluate_appliance(
    state: EnergyState,
    appliance: ApplianceConfig,
    surplus: float,
    *,
    running: bool | None = None,
    current_watts: float | None = None,
    is_octopus_dispatching: bool = False,
) -> Recommendation:
    watts = appliance.watts
    if surplus >= watts * GREEN_THRESHOLD:
        status, cost_label, reason = Status.GREEN, "Gratis", "Surplus solare sufficiente"
    elif surplus >= watts * YELLOW_THRESHOLD:
        status, cost_label, reason = Status.YELLOW, "Poco", "Parzialmente da rete"
    else:
        status, cost_label, reason = Status.RED, "Costa", "Prevalentemente da rete"

    if is_octopus_dispatching and status == Status.RED:
        status, cost_label, reason = Status.YELLOW, "Poco", "Tariffa economica attiva"

    return Recommendation(
        appliance_key=appliance.key, status=status, cost_label=cost_label,
        reason=reason, running=running, current_watts=current_watts,
        appliance_name=appliance.name, appliance_icon=appliance.icon,
    )


def evaluate(
    state: EnergyState,
    appliances: list[ApplianceConfig],
    *,
    running_states: dict[str, tuple[bool | None, float | None]] | None = None,
    is_octopus_dispatching: bool = False,
) -> list[Recommendation]:
    surplus = calculate_surplus(state)
    running_states = running_states or {}
    results = []
    for appliance in appliances:
        running, current_watts = running_states.get(appliance.key, (None, None))
        results.append(evaluate_appliance(
            state, appliance, surplus, running=running,
            current_watts=current_watts, is_octopus_dispatching=is_octopus_dispatching,
        ))
    return results
```

- [ ] **Step 4: Run tests — expect PASS** (`python -m pytest tests/test_advisor.py -v`)

- [ ] **Step 5: Commit**

```bash
git add custom_components/tesla_solar_charging/appliance_advisor/advisor.py tests/test_advisor.py
git commit -m "feat(advisor): add core logic — surplus calculation and traffic light"
```

---

### Task 4: Deadline Logic

**Files:**
- Modify: `custom_components/tesla_solar_charging/appliance_advisor/advisor.py`
- Test: `tests/test_advisor_deadlines.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for deadline-aware advisor logic."""
from tesla_solar_charging.appliance_advisor.models import Recommendation, Status
from tesla_solar_charging.appliance_advisor.advisor import apply_deadline, compute_latest_start
from tesla_solar_charging.appliance_advisor.models import DeadlineConfig


def _rec(status=Status.GREEN, cost_label="Gratis", reason="OK"):
    return Recommendation(appliance_key="dw_1", status=status, cost_label=cost_label,
                          reason=reason, appliance_name="Test", appliance_icon="X")


class TestComputeLatestStart:
    def test_finish_by_subtracts_duration(self):
        assert compute_latest_start(DeadlineConfig("finish_by", "19:30"), 120) == "17:30"

    def test_start_by_returns_time(self):
        assert compute_latest_start(DeadlineConfig("start_by", "15:00"), 120) == "15:00"

    def test_none_returns_none(self):
        assert compute_latest_start(DeadlineConfig("none"), 120) is None

    def test_finish_by_crossing_midnight(self):
        assert compute_latest_start(DeadlineConfig("finish_by", "01:00"), 120) == "23:00"


class TestApplyDeadline:
    def test_green_no_deadline(self):
        rec = _rec()
        apply_deadline(rec, DeadlineConfig("none"), 120, "14:00")
        assert rec.deadline_message is None
        assert "avvia ora" in rec.reason.lower()

    def test_yellow_approaching_shows_time(self):
        rec = _rec(Status.YELLOW, "Poco", "X")
        apply_deadline(rec, DeadlineConfig("finish_by", "19:30"), 120, "16:00")
        assert rec.latest_start_time == "17:30"
        assert "17:30" in rec.deadline_message

    def test_urgent_overrides(self):
        rec = _rec(Status.YELLOW, "Poco", "X")
        apply_deadline(rec, DeadlineConfig("finish_by", "18:00"), 120, "15:45")
        assert rec.deadline_message == "Avvia adesso!"

    def test_missed_deadline(self):
        rec = _rec(Status.YELLOW, "Poco", "X")
        apply_deadline(rec, DeadlineConfig("finish_by", "18:00"), 120, "16:30")
        assert rec.deadline_message == "Troppo tardi"

    def test_zero_duration_skips_deadline(self):
        rec = _rec()
        apply_deadline(rec, DeadlineConfig("finish_by", "19:00"), 0, "14:00")
        assert rec.deadline_message is None
```

- [ ] **Step 2: Run tests — expect FAIL** (`python -m pytest tests/test_advisor_deadlines.py -v`)

- [ ] **Step 3: Add deadline functions to advisor.py**

```python
from .const import DEADLINE_URGENT_MINUTES
from .models import DeadlineConfig


def compute_latest_start(deadline: DeadlineConfig, duration_minutes: int) -> str | None:
    if deadline.deadline_type == "none" or deadline.time is None:
        return None
    if deadline.deadline_type == "start_by":
        return deadline.time
    h, m = map(int, deadline.time.split(":"))
    total = h * 60 + m - duration_minutes
    if total < 0:
        total += 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"


def apply_deadline(rec: Recommendation, deadline: DeadlineConfig,
                   duration_minutes: int, current_time_str: str) -> None:
    if duration_minutes == 0:
        if rec.status == Status.GREEN:
            rec.reason = "Gratis \u2014 avvia ora"
        return

    latest = compute_latest_start(deadline, duration_minutes)
    if latest is None:
        if rec.status == Status.GREEN:
            rec.reason = "Gratis \u2014 avvia ora"
        return

    rec.latest_start_time = latest
    cur = int(current_time_str.split(":")[0]) * 60 + int(current_time_str.split(":")[1])
    ls = int(latest.split(":")[0]) * 60 + int(latest.split(":")[1])
    remaining = ls - cur
    if remaining < -12 * 60:
        remaining += 24 * 60

    if remaining < 0:
        rec.deadline_message = "Troppo tardi"
    elif remaining < DEADLINE_URGENT_MINUTES:
        rec.deadline_message = "Avvia adesso!"
    else:
        rec.deadline_message = f"Avvia entro {latest}"
        if rec.status == Status.GREEN:
            rec.reason = "Gratis \u2014 avvia ora"
```

- [ ] **Step 4: Run tests — expect PASS** (`python -m pytest tests/test_advisor_deadlines.py tests/test_advisor.py -v`)

- [ ] **Step 5: Commit**

```bash
git add custom_components/tesla_solar_charging/appliance_advisor/advisor.py tests/test_advisor_deadlines.py
git commit -m "feat(advisor): add deadline logic — finish_by, start_by, urgent nudge"
```

---

### Task 5: Deadline Store

**Files:**
- Create: `custom_components/tesla_solar_charging/appliance_advisor/store.py`

- [ ] **Step 1: Implement store.py**

Uses `homeassistant.helpers.storage.Store` to persist deadlines without triggering config entry reload.

```python
"""Persistent deadline storage using HA Store."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DEADLINE_STORE_KEY, DEADLINE_STORE_VERSION


class DeadlineStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store(hass, DEADLINE_STORE_VERSION, DEADLINE_STORE_KEY)
        self._data: dict[str, dict] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load()
        self._data = data if isinstance(data, dict) else {}

    async def async_save(self) -> None:
        await self._store.async_save(self._data)

    def get(self, appliance_key: str) -> dict:
        return self._data.get(appliance_key, {"type": "none", "time": None})

    def get_all(self) -> dict[str, dict]:
        return dict(self._data)

    async def async_set(self, appliance_key: str, deadline_type: str, time: str | None) -> None:
        self._data[appliance_key] = {"type": deadline_type, "time": time}
        await self.async_save()

    async def async_remove(self) -> None:
        await self._store.async_remove()
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/tesla_solar_charging/appliance_advisor/store.py
git commit -m "feat(advisor): add deadline store using HA Store"
```

---

### Task 6: Module Init — evaluate_all, Setup, and Cleanup

**Files:**
- Modify: `custom_components/tesla_solar_charging/appliance_advisor/__init__.py`

- [ ] **Step 1: Write the full module init**

```python
"""Appliance Advisor — solar-aware appliance scheduling recommendations."""
from __future__ import annotations

from datetime import datetime

from .advisor import apply_deadline, calculate_surplus, evaluate
from .const import APPLIANCE_PRESETS
from .models import ApplianceConfig, DeadlineConfig, EnergyState


def build_energy_state(grid_power: float, grid_voltage: float, battery_soc: float,
                       battery_power: float, current_amps: float,
                       solar_w: float | None = None) -> EnergyState:
    tesla_w = current_amps * grid_voltage if current_amps > 0 and grid_voltage > 0 else 0.0
    return EnergyState(
        solar_w=solar_w, grid_export_w=max(-grid_power, 0.0),
        battery_soc=battery_soc, battery_power_w=battery_power, tesla_charging_w=tesla_w,
    )


def build_appliance_list(options: dict) -> list[ApplianceConfig]:
    appliances_cfg = options.get("appliances", {})
    result = []
    for key, cfg in appliances_cfg.items():
        result.append(ApplianceConfig(
            key=key, name=cfg.get("name", key),
            icon=cfg.get("icon", "\U0001f50c"),
            watts=cfg.get("watts", 1500),
            duration_minutes=cfg.get("duration", 0),
            power_entity=cfg.get("power_entity"),
            running_threshold_w=cfg.get("running_threshold_w", 30.0),
        ))
    return result


def get_running_states(hass, appliances: list[ApplianceConfig]) -> dict[str, tuple[bool | None, float | None]]:
    states = {}
    for app in appliances:
        if app.power_entity is None:
            continue
        entity_state = hass.states.get(app.power_entity)
        if entity_state is None or entity_state.state in ("unknown", "unavailable"):
            continue
        try:
            watts = float(entity_state.state)
        except (ValueError, TypeError):
            continue
        states[app.key] = (watts > app.running_threshold_w, watts)
    return states


def evaluate_all(hass, options: dict, grid_power: float, grid_voltage: float,
                 battery_soc: float, battery_power: float, current_amps: float,
                 is_octopus_dispatching: bool = False, solar_w: float | None = None,
                 deadline_data: dict | None = None) -> dict:
    energy = build_energy_state(grid_power, grid_voltage, battery_soc, battery_power, current_amps, solar_w)
    appliances = build_appliance_list(options)
    running_states = get_running_states(hass, appliances)
    recs = evaluate(energy, appliances, running_states=running_states,
                    is_octopus_dispatching=is_octopus_dispatching)

    deadline_data = deadline_data or {}
    now_str = datetime.now().strftime("%H:%M")
    result = {}
    for rec in recs:
        dl = deadline_data.get(rec.appliance_key, {})
        deadline = DeadlineConfig(deadline_type=dl.get("type", "none"), time=dl.get("time"))
        # Find duration from appliance config
        duration = 0
        for app in appliances:
            if app.key == rec.appliance_key:
                duration = app.duration_minutes
                break
        apply_deadline(rec, deadline, duration, now_str)
        result[rec.appliance_key] = rec
    return result


async def async_unload(hass) -> None:
    """Clean up advisor resources."""
    hass.services.async_remove("tesla_solar_charging", "set_appliance_deadline")
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/tesla_solar_charging/appliance_advisor/__init__.py
git commit -m "feat(advisor): add evaluate_all orchestrator and cleanup"
```

---

### Task 7: Integration Tests — Full Flow

**Files:**
- Test: `tests/test_advisor_integration.py`

- [ ] **Step 1: Write integration tests**

```python
"""Integration test for the full advisor evaluation flow."""
from unittest.mock import MagicMock
from tesla_solar_charging.appliance_advisor import build_energy_state, build_appliance_list, evaluate_all
from tesla_solar_charging.appliance_advisor.models import Status


class TestBuildEnergyState:
    def test_computes_tesla_watts(self):
        s = build_energy_state(grid_power=-2000, grid_voltage=230, battery_soc=85,
                               battery_power=0, current_amps=10)
        assert s.tesla_charging_w == 2300.0
        assert s.grid_export_w == 2000.0

    def test_zero_amps_zero_tesla(self):
        s = build_energy_state(grid_power=-2000, grid_voltage=230, battery_soc=85,
                               battery_power=0, current_amps=0)
        assert s.tesla_charging_w == 0.0

    def test_import_zero_export(self):
        s = build_energy_state(grid_power=500, grid_voltage=230, battery_soc=85,
                               battery_power=0, current_amps=0)
        assert s.grid_export_w == 0.0


class TestBuildApplianceList:
    def test_empty_options(self):
        assert build_appliance_list({}) == []

    def test_reads_from_options(self):
        opts = {"appliances": {
            "dw_1": {"name": "Lavastoviglie", "icon": "X", "watts": 1800, "duration": 120},
        }}
        apps = build_appliance_list(opts)
        assert len(apps) == 1
        assert apps[0].watts == 1800

    def test_multiple_of_same_type(self):
        opts = {"appliances": {
            "dw_su": {"name": "Lavastoviglie Su", "icon": "X", "watts": 2000},
            "dw_giu": {"name": "Lavastoviglie Giù", "icon": "X", "watts": 2000},
        }}
        apps = build_appliance_list(opts)
        assert len(apps) == 2


class TestEvaluateAll:
    def _hass(self):
        hass = MagicMock()
        hass.states.get.return_value = None
        return hass

    def test_high_export_green(self):
        opts = {"appliances": {"ac": {"name": "AC", "icon": "X", "watts": 1000}}}
        result = evaluate_all(self._hass(), opts, grid_power=-6000, grid_voltage=230,
                              battery_soc=100, battery_power=0, current_amps=0)
        assert result["ac"].status == Status.GREEN

    def test_no_export_red(self):
        opts = {"appliances": {"ac": {"name": "AC", "icon": "X", "watts": 1000}}}
        result = evaluate_all(self._hass(), opts, grid_power=0, grid_voltage=230,
                              battery_soc=50, battery_power=0, current_amps=0)
        assert result["ac"].status == Status.RED

    def test_octopus_upgrades(self):
        opts = {"appliances": {"ac": {"name": "AC", "icon": "X", "watts": 1000}}}
        result = evaluate_all(self._hass(), opts, grid_power=0, grid_voltage=230,
                              battery_soc=50, battery_power=0, current_amps=0,
                              is_octopus_dispatching=True)
        assert result["ac"].status == Status.YELLOW

    def test_deadlines_applied(self):
        opts = {"appliances": {"dw": {"name": "DW", "icon": "X", "watts": 2000, "duration": 120}}}
        deadlines = {"dw": {"type": "finish_by", "time": "19:30"}}
        result = evaluate_all(self._hass(), opts, grid_power=-5000, grid_voltage=230,
                              battery_soc=100, battery_power=0, current_amps=0,
                              deadline_data=deadlines)
        assert result["dw"].latest_start_time == "17:30"

    def test_empty_appliances_returns_empty(self):
        result = evaluate_all(self._hass(), {}, grid_power=-5000, grid_voltage=230,
                              battery_soc=100, battery_power=0, current_amps=0)
        assert result == {}
```

- [ ] **Step 2: Run all advisor tests** (`python -m pytest tests/test_advisor*.py -v`)
  Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_advisor_integration.py
git commit -m "test(advisor): add integration tests for full evaluate_all flow"
```

---

### Task 8: Sensor Entities

**Files:**
- Create: `custom_components/tesla_solar_charging/appliance_advisor/sensor.py`
- Modify: `custom_components/tesla_solar_charging/sensor.py` (line ~53, after existing entities)

- [ ] **Step 1: Create advisor sensor.py**

```python
"""Sensor entities for the appliance advisor."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .models import Status


class AdvisorApplianceSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry, appliance_key: str, appliance_name: str) -> None:
        super().__init__(coordinator)
        self._appliance_key = appliance_key
        self._attr_name = f"Advisor {appliance_name}"
        self._attr_unique_id = f"{entry.entry_id}_advisor_{appliance_key}"
        self._attr_icon = "mdi:lightbulb-on"

    @property
    def native_value(self) -> str | None:
        recs = self.coordinator.advisor_recommendations or {}
        rec = recs.get(self._appliance_key)
        return rec.status.value if rec else None

    @property
    def extra_state_attributes(self) -> dict:
        recs = self.coordinator.advisor_recommendations or {}
        rec = recs.get(self._appliance_key)
        if not rec:
            return {}
        return {
            "appliance_name": rec.appliance_name,
            "appliance_icon": rec.appliance_icon,
            "cost_label": rec.cost_label,
            "reason": rec.reason,
            "running": rec.running,
            "current_watts": rec.current_watts,
            "deadline_message": rec.deadline_message,
            "latest_start_time": rec.latest_start_time,
        }


class AdvisorSummarySensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Appliance Advisor Summary"
    _attr_icon = "mdi:home-lightning-bolt"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_advisor_summary"

    @property
    def native_value(self) -> str | None:
        recs = self.coordinator.advisor_recommendations
        if not recs:
            return None
        green = sum(1 for r in recs.values() if r.status == Status.GREEN)
        return f"{green} di {len(recs)} gratis"

    @property
    def extra_state_attributes(self) -> dict:
        recs = self.coordinator.advisor_recommendations
        if not recs:
            return {}
        return {
            "appliances": [
                {
                    "key": r.appliance_key,
                    "name": r.appliance_name,
                    "icon": r.appliance_icon,
                    "status": r.status.value,
                    "cost_label": r.cost_label,
                    "reason": r.reason,
                    "running": r.running,
                    "current_watts": r.current_watts,
                    "deadline_message": r.deadline_message,
                    "latest_start_time": r.latest_start_time,
                }
                for r in recs.values()
            ]
        }


async def async_setup_advisor_sensors(
    hass: HomeAssistant, entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback, coordinator,
) -> None:
    appliances_cfg = entry.options.get("appliances", {})
    entities: list[SensorEntity] = [AdvisorSummarySensor(coordinator, entry)]
    for key, cfg in appliances_cfg.items():
        entities.append(AdvisorApplianceSensor(coordinator, entry, key, cfg.get("name", key)))
    async_add_entities(entities)
```

- [ ] **Step 2: Add setup call to main sensor.py**

In `custom_components/tesla_solar_charging/sensor.py`, after line 53 (`DebugSensor(coordinator, entry),` + `])`), add:

```python
    from .appliance_advisor.sensor import async_setup_advisor_sensors
    await async_setup_advisor_sensors(hass, entry, async_add_entities, coordinator)
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/tesla_solar_charging/appliance_advisor/sensor.py \
        custom_components/tesla_solar_charging/sensor.py
git commit -m "feat(advisor): add sensor entities — per-appliance + summary"
```

---

### Task 9: Coordinator Wiring

**Files:**
- Modify: `custom_components/tesla_solar_charging/coordinator.py`

- [ ] **Step 1: Add advisor property to coordinator**

In `coordinator.py __init__` (around line 105), add:

```python
        self._advisor_recommendations: dict | None = None
```

Add property (after existing properties):

```python
    @property
    def advisor_recommendations(self):
        return self._advisor_recommendations
```

- [ ] **Step 2: Restructure _async_update_data for advisor independence**

The advisor must run even when charging is disabled. The current method exits early at line 296 (`if not self._enabled: return {}`). Restructure to:

1. Move grid sensor reads **above** the `_enabled` check
2. Run advisor after grid reads succeed
3. Then check `_enabled` for charging logic

Replace the start of `_async_update_data` (lines 295-341) with:

```python
    async def _async_update_data(self) -> dict:
        # Read grid sensors unconditionally (needed for advisor even when disabled)
        grid_power = self._get_float(self._entry_data[CONF_GRID_POWER_ENTITY])
        grid_voltage = self._get_float(self._entry_data[CONF_GRID_VOLTAGE_ENTITY])

        # Run appliance advisor regardless of charging state
        if grid_power is not None and grid_voltage is not None:
            try:
                from .appliance_advisor import evaluate_all
                deadline_data = {}
                if hasattr(self, '_deadline_store') and self._deadline_store is not None:
                    deadline_data = self._deadline_store.get_all()
                batt_soc = self._get_float(self._entry_data.get(CONF_BATTERY_SOC_ENTITY)) or 0.0
                batt_power = self._get_float(self._entry_data.get(CONF_BATTERY_POWER_ENTITY)) or 0.0
                self._advisor_recommendations = evaluate_all(
                    self.hass,
                    self._entry_data,
                    grid_power, grid_voltage,
                    batt_soc, batt_power,
                    self._current_amps,
                    is_octopus_dispatching=self._is_octopus_dispatching(),
                    deadline_data=deadline_data,
                )
            except Exception:
                pass  # Advisor failure must never break charging

        if not self._enabled:
            return {}

        # Check BLE/ESP32 health before doing anything
        if not self._ble.is_healthy:
            # ... (existing BLE health check code unchanged)
```

The rest of the method (BLE check, auto-reset, grid sensor validation, mode detection) stays the same. The grid sensor reads at lines 321-327 become redundant and should be removed (they're now at the top).

**Import needed:** Add `CONF_BATTERY_SOC_ENTITY, CONF_BATTERY_POWER_ENTITY` to the imports at the top of coordinator.py if not already present.

- [ ] **Step 3: Run full test suite** (`python -m pytest tests/ -v`)
  Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add custom_components/tesla_solar_charging/coordinator.py
git commit -m "feat(advisor): wire into coordinator — runs every 30s independently of charging"
```

---

### Task 10: Service + Store Setup + Cleanup

**Files:**
- Modify: `custom_components/tesla_solar_charging/__init__.py`
- Create: `custom_components/tesla_solar_charging/services.yaml`

- [ ] **Step 1: Register service and store in async_setup_entry**

In `__init__.py`, after the coordinator setup and before platform forwarding (around line 100), add:

```python
    # --- Appliance Advisor: deadline store + service ---
    from .appliance_advisor.store import DeadlineStore
    deadline_store = DeadlineStore(hass)
    await deadline_store.async_load()
    coordinator._deadline_store = deadline_store

    async def handle_set_deadline(call):
        appliance = call.data["appliance"]
        dtype = call.data.get("type", "none")
        dtime = call.data.get("time")
        await deadline_store.async_set(appliance, dtype, dtime)

    hass.services.async_register(DOMAIN, "set_appliance_deadline", handle_set_deadline)
```

- [ ] **Step 2: Add cleanup to async_unload_entry**

In `async_unload_entry()`, before `return unload_ok`, add:

```python
    from .appliance_advisor import async_unload as advisor_unload
    await advisor_unload(hass)
```

- [ ] **Step 3: Add static path for the card**

In `__init__.py`, in the existing `async_register_static_paths` call (around line 103), add to the list:

```python
    StaticPathConfig(
        url_path=f"/{DOMAIN}/appliance-advisor-card.js",
        path=str(Path(__file__).parent / "frontend" / "appliance-advisor-card.js"),
        cache_headers=True,
    ),
```

- [ ] **Step 4: Create services.yaml**

```yaml
set_appliance_deadline:
  name: Set Appliance Deadline
  description: Set or clear a deadline for an appliance in the advisor.
  fields:
    appliance:
      name: Appliance
      description: The appliance key (e.g., "lavastoviglie_cucina_su")
      required: true
      selector:
        text:
    type:
      name: Deadline Type
      description: "finish_by", "start_by", or "none"
      required: true
      selector:
        select:
          options:
            - "finish_by"
            - "start_by"
            - "none"
    time:
      name: Time
      description: Deadline time in HH:MM format
      required: false
      selector:
        time:
```

- [ ] **Step 5: Commit**

```bash
git add custom_components/tesla_solar_charging/__init__.py \
        custom_components/tesla_solar_charging/services.yaml
git commit -m "feat(advisor): add deadline service, store, static path, cleanup"
```

---

### Task 11: Options Flow — Appliance Management (Step 4)

**Files:**
- Modify: `custom_components/tesla_solar_charging/config_flow.py`
- Modify: `custom_components/tesla_solar_charging/const.py` (add CONF_APPLIANCES constant)

- [ ] **Step 1: Add CONF_APPLIANCES to const.py**

```python
CONF_APPLIANCES = "appliances"
```

- [ ] **Step 2: Chain step 4 from async_step_energy**

In `config_flow.py`, in `TeslaSolarChargingOptionsFlow.async_step_energy()` (line 259), change:

```python
            return self.async_create_entry(title="", data=self._options)
```

to:

```python
            return await self.async_step_appliances()
```

- [ ] **Step 3: Add async_step_appliances — menu with add/done**

```python
    async def async_step_appliances(self, user_input=None):
        """Step 4: Manage appliances for the advisor."""
        data = {**self._config_entry.data, **self._config_entry.options, **self._options}
        appliances = dict(data.get(CONF_APPLIANCES, {}))

        if user_input is not None:
            action = user_input.get("action", "done")
            if action == "done":
                self._options[CONF_APPLIANCES] = appliances
                return self.async_create_entry(title="", data=self._options)
            if action == "add":
                return await self.async_step_add_appliance()
            # Edit/remove: action is the appliance key
            if action.startswith("remove_"):
                key = action[7:]
                appliances.pop(key, None)
                self._options[CONF_APPLIANCES] = appliances
                return await self.async_step_appliances()
            if action.startswith("edit_"):
                self._editing_key = action[5:]
                return await self.async_step_edit_appliance()

        # Build menu: list existing + add/done buttons
        options_list = [{"value": "done", "label": "Salva e chiudi"}]
        options_list.append({"value": "add", "label": "+ Aggiungi elettrodomestico"})
        for key, cfg in appliances.items():
            options_list.append({"value": f"edit_{key}", "label": f"Modifica: {cfg.get('name', key)}"})
            options_list.append({"value": f"remove_{key}", "label": f"Rimuovi: {cfg.get('name', key)}"})

        return self.async_show_form(
            step_id="appliances",
            data_schema=vol.Schema({
                vol.Required("action", default="done"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options_list, mode="list")
                ),
            }),
            description_placeholders={"count": str(len(appliances))},
        )
```

- [ ] **Step 4: Add async_step_add_appliance — preset selection + config**

```python
    async def async_step_add_appliance(self, user_input=None):
        """Add a new appliance from a preset."""
        from .appliance_advisor.const import APPLIANCE_PRESETS

        if user_input is not None:
            preset_key = user_input.get("preset", "custom")
            preset = APPLIANCE_PRESETS.get(preset_key, APPLIANCE_PRESETS["custom"])
            name = user_input.get("name", preset["name"])
            # Generate unique key from name
            key = name.lower().replace(" ", "_").replace("'", "").replace("`", "")
            # Ensure uniqueness
            data = {**self._config_entry.data, **self._config_entry.options, **self._options}
            appliances = dict(data.get(CONF_APPLIANCES, {}))
            base_key = key
            counter = 2
            while key in appliances:
                key = f"{base_key}_{counter}"
                counter += 1

            appliances[key] = {
                "name": name,
                "icon": preset["icon"],
                "watts": user_input.get("watts", preset["watts"]),
                "duration": user_input.get("duration", preset["duration"]),
                "power_entity": user_input.get("power_entity") or None,
            }
            self._options[CONF_APPLIANCES] = appliances
            return await self.async_step_appliances()

        preset_options = [
            {"value": k, "label": v["name"]} for k, v in APPLIANCE_PRESETS.items()
        ]

        return self.async_show_form(
            step_id="add_appliance",
            data_schema=vol.Schema({
                vol.Required("preset", default="custom"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=preset_options)
                ),
                vol.Required("name", default=""): str,
                vol.Optional("watts", default=1500): vol.Coerce(int),
                vol.Optional("duration", default=60): vol.Coerce(int),
                vol.Optional("power_entity", default=""): SENSOR_SELECTOR,
            }),
        )
```

- [ ] **Step 5: Add async_step_edit_appliance**

```python
    async def async_step_edit_appliance(self, user_input=None):
        """Edit an existing appliance."""
        data = {**self._config_entry.data, **self._config_entry.options, **self._options}
        appliances = dict(data.get(CONF_APPLIANCES, {}))
        key = self._editing_key
        current = appliances.get(key, {})

        if user_input is not None:
            appliances[key] = {
                "name": user_input.get("name", current.get("name", key)),
                "icon": current.get("icon", "\U0001f50c"),
                "watts": user_input.get("watts", current.get("watts", 1500)),
                "duration": user_input.get("duration", current.get("duration", 0)),
                "power_entity": user_input.get("power_entity") or None,
            }
            self._options[CONF_APPLIANCES] = appliances
            return await self.async_step_appliances()

        return self.async_show_form(
            step_id="edit_appliance",
            data_schema=vol.Schema({
                vol.Required("name", default=current.get("name", key)): str,
                vol.Optional("watts", default=current.get("watts", 1500)): vol.Coerce(int),
                vol.Optional("duration", default=current.get("duration", 0)): vol.Coerce(int),
                vol.Optional("power_entity", default=current.get("power_entity", "")): SENSOR_SELECTOR,
            }),
        )
```

- [ ] **Step 6: Add strings for the new steps**

Add step descriptions to `strings.json` and `translations/en.json` (if they exist) or create them. Minimally, the steps need titles shown in the HA UI.

- [ ] **Step 7: Commit**

```bash
git add custom_components/tesla_solar_charging/config_flow.py \
        custom_components/tesla_solar_charging/const.py
git commit -m "feat(advisor): add options flow step 4 — add/edit/remove appliances"
```

---

### Task 12: Custom Lovelace Card

**Files:**
- Create: `custom_components/tesla_solar_charging/frontend/appliance-advisor-card.js`

- [ ] **Step 1: Create the card**

Full vanilla web component. Key design points:
- Reads appliance list from summary sensor attributes (fully dynamic — no hardcoded appliances)
- Names and icons come from sensor attributes
- Status banner gradient based on green ratio
- Pulsing glow for running appliances
- Tap to expand deadline picker (calls `set_appliance_deadline` service)
- Large fonts for tablet readability (32px status, 26px metrics, 20px names)
- Navigation buttons from card YAML config
- `customElements.define` guarded with `.get()` check
- Registered in `window.customCards` for HA card picker

See spec "Card Layout — Layout A" section for exact layout. Use actual emoji characters in JS (not Python unicode escapes).

- [ ] **Step 2: Commit**

```bash
git add custom_components/tesla_solar_charging/frontend/appliance-advisor-card.js
git commit -m "feat(advisor): add custom Lovelace card for tablet dashboard"
```

---

### Task 12: Panel Debug Tab

**Files:**
- Modify: `custom_components/tesla_solar_charging/frontend/panel.js`

- [ ] **Step 1: Add Advisor tab to existing panel**

The existing panel renders 9 cards in a grid. Add a tab system (or a 10th card section "Advisor Debug") that shows:

1. **Advisor State table** — reads `sensor.tesla_solar_charging_appliance_advisor_summary` attributes, renders as table: key | name | status | cost_label | reason | running | watts | deadline | latest_start
2. **Energy State** — reads the summary sensor + individual sensors to show: grid_export, battery_soc, battery_power, tesla_charging, surplus
3. **Deadline Store** — raw JSON of all deadline data from summary attributes
4. **Copy JSON button** — copies all advisor debug data as formatted JSON (follow existing Copy button pattern from Debug card, lines ~243-249)

Reuse existing card CSS (`.tsc-card`, `h2` headings, `_row()` helper pattern).

- [ ] **Step 2: Commit**

```bash
git add custom_components/tesla_solar_charging/frontend/panel.js
git commit -m "feat(advisor): add debug tab to existing Tesla Solar panel"
```

---

### Task 13: Dashboard YAML

**Files:**
- Modify: `dash.yaml` (repo root)

- [ ] **Step 1: Replace power-flow-card with advisor card on Home view**

Replace lines 16-100 (the `custom:power-flow-card-plus-custom` block) with:

```yaml
          - type: custom:appliance-advisor-card
            entity: sensor.tesla_solar_charging_appliance_advisor_summary
            solar_entity: sensor.solar_production
            battery_soc_entity: sensor.esp32_deye_inverter_battery_soc
            tesla_soc_entity: sensor.tesla_di_luca_battery
            navigation:
              - label: "Dettaglio"
                path: /dashboard-consumi/dettaglio-consumi-nuovo
              - label: "Meteo"
                path: /dashboard-consumi/dettaglio-meteo
              - label: "Comandi"
                path: /dashboard-consumi/comandi
              - label: "Camera"
                path: /dashboard-consumi/zoom-camera
            grid_options:
              columns: 18
              rows: 8
```

Remove the now-redundant standalone navigation buttons (lines 101-180) since they're built into the card.

- [ ] **Step 2: Commit**

```bash
git add dash.yaml
git commit -m "feat(advisor): update dashboard — replace power-flow with advisor card"
```

---

### Task 14: Final Verification

- [ ] **Step 1: Verify file structure**

```bash
ls custom_components/tesla_solar_charging/appliance_advisor/
# Expected: __init__.py  advisor.py  const.py  models.py  sensor.py  store.py

ls custom_components/tesla_solar_charging/frontend/
# Expected: panel.js  appliance-advisor-card.js

ls custom_components/tesla_solar_charging/services.yaml
# Expected: exists
```

- [ ] **Step 2: Run full test suite**

`python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Verify no regressions in existing tests**

`python -m pytest tests/test_charging_logic.py tests/test_forecast_blend.py tests/test_planner.py -v`
Expected: ALL PASS
