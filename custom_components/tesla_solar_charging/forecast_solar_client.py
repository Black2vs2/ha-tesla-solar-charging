"""Forecast.Solar API client — fetches PV production estimates."""
import logging
from dataclasses import dataclass
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)
FORECAST_SOLAR_URL = "https://api.forecast.solar/estimate/{lat}/{lon}/{dec}/{az}/{kwp}"

@dataclass
class ForecastSolarResult:
    date: str
    production_kwh: float

async def fetch_forecast_solar(hass, latitude: float, longitude: float, declination: int, azimuth: int, kwp: float) -> list[ForecastSolarResult] | None:
    session = async_get_clientsession(hass)
    url = FORECAST_SOLAR_URL.format(lat=latitude, lon=longitude, dec=declination, az=azimuth, kwp=kwp)
    try:
        resp = await session.get(url, timeout=15)
        if resp.status != 200:
            _LOGGER.error("Forecast.Solar returned status %d", resp.status)
            return None
        data = await resp.json()
        wh_days = data.get("result", {}).get("watt_hours_day", {})
        return [ForecastSolarResult(date=date, production_kwh=round(wh/1000, 1))
            for date, wh in sorted(wh_days.items())]
    except Exception as err:
        _LOGGER.error("Failed to fetch Forecast.Solar: %s", err)
        return None
