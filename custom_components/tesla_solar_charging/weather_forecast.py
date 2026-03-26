"""Open-Meteo weather forecast for solar production estimation."""

import logging
from dataclasses import dataclass, field
from datetime import datetime

from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass
class HourlyEntry:
    """One hour of forecast data."""

    hour: int
    radiation_w_m2: float  # GHI in W/m²
    cloud_cover: float  # total %
    cloud_cover_low: float
    cloud_cover_mid: float
    cloud_cover_high: float


@dataclass
class DailyHourlyForecast:
    """A day's worth of hourly forecast data with derived metrics."""

    date: str
    hours: list[HourlyEntry] = field(default_factory=list)

    @property
    def total_radiation_kwh(self) -> float:
        """Total radiation in kWh/m² (each hour entry is W/m² for 1h → Wh/m²)."""
        return round(sum(h.radiation_w_m2 for h in self.hours) / 1000, 2)

    @property
    def avg_cloud_cover(self) -> float:
        """Average cloud cover during daylight hours (6-20)."""
        daylight = [h for h in self.hours if 6 <= h.hour <= 20]
        if not daylight:
            return 100.0
        return round(sum(h.cloud_cover for h in daylight) / len(daylight), 1)

    @property
    def cloud_strategy(self) -> str:
        """Classify the day's cloud pattern for charging strategy."""
        avg = self.avg_cloud_cover
        if avg < 25:
            return "clear"
        if avg < 50:
            return "partly_cloudy"
        if avg < 75:
            return "mostly_cloudy"
        return "overcast"

    @property
    def best_window_start(self) -> int | None:
        """Find the start hour of the best 4-hour charging window."""
        if not self.hours:
            return None
        daylight = [h for h in self.hours if 6 <= h.hour <= 18]
        if len(daylight) < 4:
            return None
        best_start = 6
        best_sum = 0
        for i in range(len(daylight) - 3):
            window_sum = sum(daylight[i + j].radiation_w_m2 for j in range(4))
            if window_sum > best_sum:
                best_sum = window_sum
                best_start = daylight[i].hour
        return best_start

    @property
    def best_window_desc(self) -> str:
        """Human-readable description of best charging window."""
        start = self.best_window_start
        if start is None:
            return "No suitable window"
        end = min(start + 4, 24)
        return f"{start:02d}:00-{end:02d}:00"


def parse_hourly_forecast(data: dict) -> dict[str, DailyHourlyForecast]:
    """Parse Open-Meteo hourly response into per-day forecasts."""
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    ghi = hourly.get("shortwave_radiation", [])
    cloud = hourly.get("cloud_cover", [])
    cloud_low = hourly.get("cloud_cover_low", [])
    cloud_mid = hourly.get("cloud_cover_mid", [])
    cloud_high = hourly.get("cloud_cover_high", [])

    days: dict[str, DailyHourlyForecast] = {}

    for i, time_str in enumerate(times):
        date_str = time_str[:10]  # "2026-03-24"
        hour = int(time_str[11:13])  # "14" from "T14:00"

        if date_str not in days:
            days[date_str] = DailyHourlyForecast(date=date_str)

        days[date_str].hours.append(HourlyEntry(
            hour=hour,
            radiation_w_m2=ghi[i] if i < len(ghi) else 0,
            cloud_cover=cloud[i] if i < len(cloud) else 0,
            cloud_cover_low=cloud_low[i] if i < len(cloud_low) else 0,
            cloud_cover_mid=cloud_mid[i] if i < len(cloud_mid) else 0,
            cloud_cover_high=cloud_high[i] if i < len(cloud_high) else 0,
        ))

    return days


async def fetch_hourly_solar_forecast(
    hass,
    latitude: float,
    longitude: float,
) -> dict[str, DailyHourlyForecast] | None:
    """Fetch hourly solar + cloud forecast from Open-Meteo."""
    session = async_get_clientsession(hass)

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "shortwave_radiation,cloud_cover,cloud_cover_low,cloud_cover_mid,cloud_cover_high",
        "timezone": "auto",
        "forecast_days": 3,
    }

    try:
        resp = await session.get(OPEN_METEO_URL, params=params, timeout=10)
        if resp.status != 200:
            _LOGGER.error("Open-Meteo hourly returned status %d", resp.status)
            return None

        data = await resp.json()
        return parse_hourly_forecast(data)

    except Exception as err:
        _LOGGER.error("Failed to fetch hourly forecast: %s", err)
        return None


async def fetch_solar_forecast(
    hass,
    latitude: float,
    longitude: float,
) -> dict | None:
    """Fetch solar radiation forecast from Open-Meteo.

    Returns dict with 'today' and 'tomorrow' keys, each containing:
    - radiation_kwh_m2: total solar radiation in kWh/m²
    - sunshine_hours: hours of sunshine
    Or None if fetch fails.
    """
    session = async_get_clientsession(hass)

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "shortwave_radiation_sum,sunshine_duration",
        "timezone": "auto",
        "forecast_days": 7,
    }

    try:
        resp = await session.get(OPEN_METEO_URL, params=params, timeout=10)
        if resp.status != 200:
            _LOGGER.error("Open-Meteo returned status %d", resp.status)
            return None

        data = await resp.json()
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        radiation = daily.get("shortwave_radiation_sum", [])
        sunshine = daily.get("sunshine_duration", [])

        if len(dates) < 2 or len(radiation) < 2:
            _LOGGER.error("Open-Meteo returned insufficient data")
            return None

        result = {}
        all_days = []
        today_str = datetime.now().strftime("%Y-%m-%d")

        for i, date_str in enumerate(dates):
            # radiation is in MJ/m², convert to kWh/m²
            rad_kwh = radiation[i] / 3.6 if radiation[i] else 0
            sun_hours = sunshine[i] / 3600 if sunshine[i] else 0  # seconds to hours

            day_entry = {
                "radiation_kwh_m2": round(rad_kwh, 2),
                "sunshine_hours": round(sun_hours, 1),
                "date": date_str,
            }
            all_days.append(day_entry)

            if date_str == today_str:
                result["today"] = day_entry
            elif "today" in result and "tomorrow" not in result:
                result["tomorrow"] = day_entry

        if "tomorrow" not in result and len(dates) >= 2:
            rad_kwh = radiation[1] / 3.6 if radiation[1] else 0
            sun_hours = sunshine[1] / 3600 if sunshine[1] else 0
            result["tomorrow"] = {
                "radiation_kwh_m2": round(rad_kwh, 2),
                "sunshine_hours": round(sun_hours, 1),
                "date": dates[1],
            }

        result["days"] = all_days
        return result

    except Exception as err:
        _LOGGER.error("Failed to fetch Open-Meteo forecast: %s", err)
        return None


def estimate_solar_production(
    radiation_kwh_m2: float,
    system_kwp: float,
    performance_ratio: float = 0.60,
    correction_factor: float = 1.0,
) -> float:
    """Estimate daily solar production in kWh."""
    return round(radiation_kwh_m2 * system_kwp * performance_ratio * correction_factor, 1)


def estimate_solar_excess(
    production_kwh: float,
    home_battery_kwh: float,
    battery_soc_percent: float,
    avg_house_consumption_kwh: float,
) -> float:
    """Estimate solar excess available for Tesla charging.

    Args:
        production_kwh: Estimated solar production in kWh
        home_battery_kwh: Home battery total capacity in kWh
        battery_soc_percent: Current home battery SOC %
        avg_house_consumption_kwh: Average daily house consumption in kWh
    Returns:
        Estimated excess kWh available for Tesla
    """
    battery_needs = home_battery_kwh * (100 - battery_soc_percent) / 100
    excess = production_kwh - battery_needs - avg_house_consumption_kwh
    return round(max(0, excess), 1)
