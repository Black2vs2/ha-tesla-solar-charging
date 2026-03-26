"""Persistent appliance configuration storage with auto-detection from entity IDs."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    APPLIANCE_PRESETS,
    APPLIANCE_STORE_KEY,
    APPLIANCE_STORE_VERSION,
    ENTITY_KEYWORD_TO_PRESET,
    LOCATION_KEYWORDS,
)


def _detect_from_entity_id(entity_id: str) -> dict:
    """Auto-detect appliance name, icon, watts, duration from an entity ID."""
    # e.g. "sensor.presa_su_lavastoviglie_power" → parts = "presa_su_lavastoviglie_power"
    entity_part = entity_id.split(".", 1)[-1].lower()

    # Detect appliance type
    preset_key = "custom"
    for keyword, p_key in ENTITY_KEYWORD_TO_PRESET.items():
        if keyword in entity_part:
            preset_key = p_key
            break
    preset = APPLIANCE_PRESETS[preset_key]

    # Detect location suffix
    location = ""
    for keyword, suffix in LOCATION_KEYWORDS.items():
        if keyword in entity_part:
            location = suffix
            break

    name = preset["name"] + location

    return {
        "name": name,
        "icon": preset["icon"],
        "watts": preset["watts"],
        "duration": preset["duration"],
        "power_entity": entity_id,
    }


def _make_key(entity_id: str) -> str:
    """Generate a unique key from an entity ID."""
    return entity_id.split(".", 1)[-1].replace("_power", "").replace("_energy", "")


class ApplianceConfigStore:
    """Persistent store for appliance configurations (service-managed, no restart needed)."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store(hass, APPLIANCE_STORE_VERSION, APPLIANCE_STORE_KEY)
        self._data: dict[str, dict] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load()
        self._data = data if isinstance(data, dict) else {}

    async def async_save(self) -> None:
        await self._store.async_save(self._data)

    def get_all(self) -> dict[str, dict]:
        return dict(self._data)

    async def async_configure_from_entities(self, entity_ids: list[str]) -> dict[str, dict]:
        """Replace all appliances by auto-detecting from a list of entity IDs."""
        self._data = {}
        for entity_id in entity_ids:
            key = _make_key(entity_id)
            self._data[key] = _detect_from_entity_id(entity_id)
        await self.async_save()
        return dict(self._data)

    async def async_add(self, entity_id: str, name: str | None = None,
                        watts: int | None = None, duration: int | None = None) -> str:
        """Add a single appliance (auto-detects if name/watts not provided)."""
        detected = _detect_from_entity_id(entity_id)
        if name:
            detected["name"] = name
        if watts is not None:
            detected["watts"] = watts
        if duration is not None:
            detected["duration"] = duration
        key = _make_key(entity_id)
        self._data[key] = detected
        await self.async_save()
        return key

    async def async_remove(self, key: str) -> bool:
        """Remove an appliance by key."""
        if key in self._data:
            del self._data[key]
            await self.async_save()
            return True
        return False

    async def async_remove_store(self) -> None:
        await self._store.async_remove()
