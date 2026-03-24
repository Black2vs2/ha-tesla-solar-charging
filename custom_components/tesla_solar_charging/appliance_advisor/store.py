"""Persistent deadline storage using HA Store."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DEADLINE_STORE_KEY, DEADLINE_STORE_VERSION


class DeadlineStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store(hass, DEADLINE_STORE_VERSION, DEADLINE_STORE_KEY)
        self._data: dict[str, dict] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load()
        self._data = data if isinstance(data, dict) else {}

    async def async_save(self) -> None:
        await self._store.async_save(self._data)

    def get(self, appliance_key: str) -> dict:
        return self._data.get(appliance_key, {"type": "none", "time": None})

    def get_all(self) -> dict[str, dict]:
        return dict(self._data)

    async def async_set(self, appliance_key: str, deadline_type: str, time: str | None) -> None:
        self._data[appliance_key] = {"type": deadline_type, "time": time}
        await self.async_save()

    async def async_remove(self) -> None:
        await self._store.async_remove()
