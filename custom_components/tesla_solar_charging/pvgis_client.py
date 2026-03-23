"""PVGIS client — fetches monthly irradiance baselines from the EU JRC."""
import logging
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)
PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_2/MRcalc"

def parse_pvgis_monthly(data: dict) -> dict[int, float]:
    monthly = data.get("outputs", {}).get("monthly", {}).get("fixed", [])
    return {entry["month"]: entry["H(h)_m"] for entry in monthly}

async def fetch_pvgis_monthly(hass, latitude: float, longitude: float) -> dict[int, float] | None:
    session = async_get_clientsession(hass)
    params = {"lat": latitude, "lon": longitude, "outputformat": "json", "startyear": 2015, "endyear": 2023}
    try:
        resp = await session.get(PVGIS_URL, params=params, timeout=30)
        if resp.status != 200:
            _LOGGER.error("PVGIS returned status %d", resp.status)
            return None
        data = await resp.json()
        result = parse_pvgis_monthly(data)
        if len(result) == 12:
            return result
        return None
    except Exception as err:
        _LOGGER.error("Failed to fetch PVGIS data: %s", err)
        return None
