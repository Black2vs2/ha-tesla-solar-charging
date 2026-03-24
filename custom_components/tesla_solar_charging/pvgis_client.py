"""PVGIS client — fetches monthly irradiance baselines from the EU JRC."""
import logging
from collections import defaultdict

from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)
PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_2/MRcalc"

def parse_pvgis_monthly(data: dict) -> dict[int, float]:
    monthly = data.get("outputs", {}).get("monthly", [])
    if isinstance(monthly, dict):
        monthly = monthly.get("fixed", [])
    # MRcalc returns one entry per year per month — average across years
    by_month: dict[int, list[float]] = defaultdict(list)
    for entry in monthly:
        month = entry.get("month")
        irrad = entry.get("H(h)_m")
        if month is not None and irrad is not None:
            by_month[month].append(irrad)
    return {m: sum(vals) / len(vals) for m, vals in by_month.items() if vals}

async def fetch_pvgis_monthly(hass, latitude: float, longitude: float) -> dict[int, float] | None:
    session = async_get_clientsession(hass)
    params = {
        "lat": latitude, "lon": longitude,
        "outputformat": "json",
        "startyear": 2005, "endyear": 2020,
        "horirrad": 1,
    }
    try:
        resp = await session.get(PVGIS_URL, params=params, timeout=30)
        if resp.status != 200:
            body = await resp.text()
            _LOGGER.error("PVGIS returned status %d: %s", resp.status, body[:500])
            return None
        data = await resp.json()
        result = parse_pvgis_monthly(data)
        if len(result) == 12:
            return result
        _LOGGER.warning("PVGIS returned %d months (expected 12)", len(result))
        return None
    except Exception as err:
        _LOGGER.error("Failed to fetch PVGIS data: %s", err)
        return None
