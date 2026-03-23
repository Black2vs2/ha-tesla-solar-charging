"""Solcast API client — fetches PV production forecasts with confidence bands."""
import logging
from dataclasses import dataclass
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)
SOLCAST_URL = "https://api.solcast.com.au/rooftop_sites/{resource_id}/forecasts"

@dataclass
class SolcastForecast:
    date: str
    production_kwh_p10: float
    production_kwh_p50: float
    production_kwh_p90: float

async def fetch_solcast_forecast(hass, api_key: str, resource_id: str) -> list[SolcastForecast] | None:
    session = async_get_clientsession(hass)
    url = SOLCAST_URL.format(resource_id=resource_id)
    try:
        resp = await session.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=15)
        if resp.status != 200:
            _LOGGER.error("Solcast returned status %d", resp.status)
            return None
        data = await resp.json()
        forecasts = data.get("forecasts", [])
        daily: dict[str, dict[str, float]] = {}
        for entry in forecasts:
            period_end = entry.get("period_end", "")
            date = period_end[:10]
            if date not in daily:
                daily[date] = {"p10": 0, "p50": 0, "p90": 0}
            daily[date]["p10"] += entry.get("pv_estimate10", 0) / 2
            daily[date]["p50"] += entry.get("pv_estimate", 0) / 2
            daily[date]["p90"] += entry.get("pv_estimate90", 0) / 2
        return [SolcastForecast(date=d, production_kwh_p10=round(v["p10"],1),
            production_kwh_p50=round(v["p50"],1), production_kwh_p90=round(v["p90"],1))
            for d, v in sorted(daily.items())]
    except Exception as err:
        _LOGGER.error("Failed to fetch Solcast forecast: %s", err)
        return None
