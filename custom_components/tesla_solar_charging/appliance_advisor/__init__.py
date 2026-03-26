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
                 deadline_data: dict | None = None,
                 run_history_store=None) -> dict:
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
        duration = 0
        for app in appliances:
            if app.key == rec.appliance_key:
                duration = app.duration_minutes
                break
        apply_deadline(rec, deadline, duration, now_str)

        # Attach run history data
        if run_history_store:
            last_run = run_history_store.get_last_run(rec.appliance_key)
            if last_run:
                rec.last_run_end = last_run.get("end")
                rec.last_run_kwh = last_run.get("energy_kwh")
                rec.last_run_duration_min = last_run.get("duration_min")
            rec.avg_consumption_kwh = run_history_store.get_avg_consumption_kwh(rec.appliance_key)

        result[rec.appliance_key] = rec
    return result


async def async_unload(hass) -> None:
    """Clean up advisor resources."""
    hass.services.async_remove("tesla_solar_charging", "set_appliance_deadline")
