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
        )

    # Poor forecast — charge tonight
    return ChargePlan(
        charge_tonight=True,
        reason=f"Insufficient solar: {excess:.1f} kWh excess vs {kwh_needed:.1f} kWh needed",
        tesla_current_soc=tesla_soc,
        tesla_target_soc=target_soc,
        kwh_needed=round(kwh_needed, 1),
        forecast_production_kwh=production,
        forecast_excess_kwh=excess,
        sunshine_hours=sunshine_hours,
    )


@dataclass
class MultiDayOutlook:
    """Result of checking multi-day solar forecast."""
    poor_days: int
    total_days_checked: int
    daily_forecasts: list[dict]
    total_excess_kwh: float
    kwh_needed: float
    warning: str | None


def check_multi_day_outlook(
    daily_production_list: list[tuple[str, float]],
    tesla_soc: float,
    target_soc: float,
    tesla_battery_kwh: float,
    home_battery_kwh: float,
    home_battery_soc: float,
    avg_house_consumption_kwh: float,
) -> MultiDayOutlook:
    """Check if upcoming days have enough solar to charge the Tesla.

    Returns a warning if the cumulative solar excess over the next days
    can't cover what the Tesla needs.
    """
    soc_gap = max(0, target_soc - tesla_soc)
    kwh_needed = tesla_battery_kwh * soc_gap / 100

    if kwh_needed <= 0:
        return MultiDayOutlook(
            poor_days=0, total_days_checked=len(daily_production_list),
            daily_forecasts=[], total_excess_kwh=0, kwh_needed=0, warning=None,
        )

    daily_forecasts = []
    total_excess = 0.0
    poor_days = 0

    for date, production in daily_production_list:
        excess = estimate_solar_excess(
            production, home_battery_kwh, home_battery_soc, avg_house_consumption_kwh
        )
        daily_forecasts.append({
            "date": date,
            "production_kwh": round(production, 1),
            "excess_kwh": round(excess, 1),
        })
        total_excess += excess
        if excess < 5.0:
            poor_days += 1

    warning = None
    if poor_days > 0 and total_excess < kwh_needed and len(daily_production_list) > 0:
        shortfall = kwh_needed - total_excess
        warning = (
            f"Low solar outlook: {total_excess:.0f} kWh excess expected "
            f"over the next {len(daily_production_list)} days, "
            f"but Tesla needs {kwh_needed:.0f} kWh ({shortfall:.0f} kWh shortfall). "
            f"Consider charging more today."
        )

    return MultiDayOutlook(
        poor_days=poor_days,
        total_days_checked=len(daily_production_list),
        daily_forecasts=daily_forecasts,
        total_excess_kwh=round(total_excess, 1),
        kwh_needed=round(kwh_needed, 1),
        warning=warning,
    )


def format_plan_message(plan: ChargePlan) -> str:
    """Format a charge plan into a human-readable message."""
    status = "Charge tonight" if plan.charge_tonight else "Skip night charge — use solar"
    weather = "sunny" if plan.sunshine_hours > 8 else "partly cloudy" if plan.sunshine_hours > 4 else "cloudy"

    lines = [
        f"*Tesla Charging Plan*",
        f"",
        f"Car: {plan.tesla_current_soc:.0f}% → target {plan.tesla_target_soc:.0f}% ({plan.kwh_needed:.1f} kWh needed)",
        f"",
        f"Tomorrow: {weather} ({plan.sunshine_hours:.0f}h sun)",
        f"Expected solar: {plan.forecast_production_kwh:.0f} kWh",
        f"Excess for Tesla: {plan.forecast_excess_kwh:.0f} kWh",
        f"",
        f"*Decision: {status}*",
        f"Reason: {plan.reason}",
    ]
    return "\n".join(lines)
