"""Solcast API client — fetches PV production forecasts with confidence bands.

Supports multiple resource IDs (comma-separated) for split arrays (e.g. east/west).
"""
import logging
from dataclasses import dataclass
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)
SOLCAST_URL = "https://api.solcast.com.au/rooftop_sites/{resource_id}/forecasts?format=json"

@dataclass
class SolcastForecast:
    date: str
    production_kwh_p10: float
    production_kwh_p50: float
    production_kwh_p90: float

async def fetch_solcast_forecast(hass, api_key: str, resource_id: str) -> list[SolcastForecast] | None:
    """Fetch forecasts from one or more Solcast rooftop sites and sum them."""
    session = async_get_clientsession(hass)
    resource_ids = [rid.strip() for rid in resource_id.split(",") if rid.strip()]

    daily: dict[str, dict[str, float]] = {}

    for rid in resource_ids:
        url = SOLCAST_URL.format(resource_id=rid)
        try:
            resp = await session.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=15)
            if resp.status == 429:
                _LOGGER.warning("Solcast rate limited for %s — will use other sources", rid)
                continue
            if resp.status != 200:
                body = await resp.text()
                _LOGGER.warning("Solcast returned status %d for %s: %s", resp.status, rid, body[:300])
                continue
            data = await resp.json(content_type=None)
            forecasts = data.get("forecasts", [])
            for entry in forecasts:
                period_end = entry.get("period_end", "")
                date = period_end[:10]
                if date not in daily:
                    daily[date] = {"p10": 0, "p50": 0, "p90": 0}
                daily[date]["p10"] += entry.get("pv_estimate10", 0) / 2
                daily[date]["p50"] += entry.get("pv_estimate", 0) / 2
                daily[date]["p90"] += entry.get("pv_estimate90", 0) / 2
            _LOGGER.info("Solcast fetched %d periods from %s", len(forecasts), rid)
        except Exception as err:
            _LOGGER.error("Failed to fetch Solcast forecast for %s: %s", rid, err)

    if not daily:
        return None

    return [SolcastForecast(date=d, production_kwh_p10=round(v["p10"], 1),
        production_kwh_p50=round(v["p50"], 1), production_kwh_p90=round(v["p90"], 1))
        for d, v in sorted(daily.items())]
