"""Core advisor logic — pure functions, no HA dependency."""
from __future__ import annotations

from .const import (BATTERY_NEAR_FULL_FACTOR, BATTERY_NEAR_FULL_SOC,
                    GREEN_THRESHOLD, YELLOW_THRESHOLD, DEADLINE_URGENT_MINUTES)
from .models import ApplianceConfig, DeadlineConfig, EnergyState, Recommendation, Status


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
