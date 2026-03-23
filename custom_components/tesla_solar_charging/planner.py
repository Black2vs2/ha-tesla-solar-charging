"""Evening decision engine — decides whether to charge tonight or wait for solar."""

import logging
from dataclasses import dataclass

from .weather_forecast import estimate_solar_excess, estimate_solar_production

_LOGGER = logging.getLogger(__name__)


@dataclass
class ChargePlan:
    """Result of the evening planning decision."""
    charge_tonight: bool
    reason: str
    tesla_current_soc: float
    tesla_target_soc: float
    kwh_needed: float
    forecast_production_kwh: float
    forecast_excess_kwh: float
    sunshine_hours: float
    days_until_deadline: float


def create_charge_plan(
    tesla_soc: float,
    target_soc: float,
    tesla_battery_kwh: float,
    forecast_radiation_kwh_m2: float,
    sunshine_hours: float,
    pv_system_kwp: float,
    home_battery_kwh: float,
    home_battery_soc: float,
    avg_house_consumption_kwh: float,
    hours_until_deadline: float,
    correction_factor: float = 1.0,
    safety_margin: float = 1.0,
) -> ChargePlan:
    """Create a charging plan for tonight.

    Pure function — no HA dependencies.
    """
    # How much energy the Tesla needs
    soc_gap = max(0, target_soc - tesla_soc)
    kwh_needed = tesla_battery_kwh * soc_gap / 100

    # How much solar we expect tomorrow
    production = estimate_solar_production(forecast_radiation_kwh_m2, pv_system_kwp, correction_factor=correction_factor)
    excess = estimate_solar_excess(
        production, home_battery_kwh, home_battery_soc, avg_house_consumption_kwh
    )

    days_until_deadline = hours_until_deadline / 24

    # Decision logic
    if kwh_needed <= 0:
        return ChargePlan(
            charge_tonight=False,
            reason="Tesla already at or above target SOC",
            tesla_current_soc=tesla_soc,
            tesla_target_soc=target_soc,
            kwh_needed=0,
            forecast_production_kwh=production,
            forecast_excess_kwh=excess,
            sunshine_hours=sunshine_hours,
            days_until_deadline=days_until_deadline,
        )

    # If deadline is very soon (< 18 hours), charge tonight to be safe
    if hours_until_deadline < 18:
        return ChargePlan(
            charge_tonight=True,
            reason=f"Deadline in {hours_until_deadline:.0f}h — charging tonight to be safe",
            tesla_current_soc=tesla_soc,
            tesla_target_soc=target_soc,
            kwh_needed=round(kwh_needed, 1),
            forecast_production_kwh=production,
            forecast_excess_kwh=excess,
            sunshine_hours=sunshine_hours,
            days_until_deadline=days_until_deadline,
        )

    # If solar excess can cover what we need, skip night charging
    if excess >= kwh_needed * safety_margin:
        return ChargePlan(
            charge_tonight=False,
            reason=f"Solar should cover it: {excess:.1f} kWh excess vs {kwh_needed:.1f} kWh needed",
            tesla_current_soc=tesla_soc,
            tesla_target_soc=target_soc,
            kwh_needed=round(kwh_needed, 1),
            forecast_production_kwh=production,
            forecast_excess_kwh=excess,
            sunshine_hours=sunshine_hours,
            days_until_deadline=days_until_deadline,
        )

    # If we have multiple days, check if partial solar + next night could work
    if days_until_deadline > 1.5 and excess > kwh_needed * 0.5 * safety_margin:
        return ChargePlan(
            charge_tonight=False,
            reason=f"Deadline in {days_until_deadline:.1f} days, solar covers {excess:.1f}/{kwh_needed:.1f} kWh — can catch up tomorrow",
            tesla_current_soc=tesla_soc,
            tesla_target_soc=target_soc,
            kwh_needed=round(kwh_needed, 1),
            forecast_production_kwh=production,
            forecast_excess_kwh=excess,
            sunshine_hours=sunshine_hours,
            days_until_deadline=days_until_deadline,
        )

    # Poor forecast or tight deadline — charge tonight
    return ChargePlan(
        charge_tonight=True,
        reason=f"Insufficient solar: {excess:.1f} kWh excess vs {kwh_needed:.1f} kWh needed",
        tesla_current_soc=tesla_soc,
        tesla_target_soc=target_soc,
        kwh_needed=round(kwh_needed, 1),
        forecast_production_kwh=production,
        forecast_excess_kwh=excess,
        sunshine_hours=sunshine_hours,
        days_until_deadline=days_until_deadline,
    )


def format_plan_message(plan: ChargePlan) -> str:
    """Format a charge plan into a human-readable message."""
    status = "Charge tonight" if plan.charge_tonight else "Skip night charge — use solar"
    weather = "sunny" if plan.sunshine_hours > 8 else "partly cloudy" if plan.sunshine_hours > 4 else "cloudy"

    lines = [
        f"*Tesla Charging Plan*",
        f"",
        f"Car: {plan.tesla_current_soc:.0f}% → target {plan.tesla_target_soc:.0f}% ({plan.kwh_needed:.1f} kWh needed)",
        f"Deadline: {plan.days_until_deadline:.1f} days",
        f"",
        f"Tomorrow: {weather} ({plan.sunshine_hours:.0f}h sun)",
        f"Expected solar: {plan.forecast_production_kwh:.0f} kWh",
        f"Excess for Tesla: {plan.forecast_excess_kwh:.0f} kWh",
        f"",
        f"*Decision: {status}*",
        f"Reason: {plan.reason}",
    ]
    return "\n".join(lines)
