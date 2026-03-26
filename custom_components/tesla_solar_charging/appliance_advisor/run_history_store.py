"""Persistent run history storage for appliances."""
from __future__ import annotations

from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

RUN_HISTORY_STORE_KEY = "tesla_solar_charging.advisor_run_history"
RUN_HISTORY_STORE_VERSION = 1
MAX_RUNS_PER_APPLIANCE = 30


class RunHistoryStore:
    """Tracks per-appliance run history: start/end times and energy consumed."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store(hass, RUN_HISTORY_STORE_VERSION, RUN_HISTORY_STORE_KEY)
        self._data: dict[str, dict] = {}
        # Track in-progress runs (not persisted, rebuilt from running state)
        self._active_runs: dict[str, dict] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load()
        self._data = data if isinstance(data, dict) else {}

    async def async_save(self) -> None:
        await self._store.async_save(self._data)

    def get(self, appliance_key: str) -> dict:
        """Get run history for one appliance."""
        return self._data.get(appliance_key, {"runs": [], "last_run": None})

    def get_all(self) -> dict[str, dict]:
        return dict(self._data)

    def start_run(self, appliance_key: str, watts: float) -> None:
        """Mark an appliance as starting a run."""
        self._active_runs[appliance_key] = {
            "start": datetime.now().isoformat(),
            "samples_w": [watts],
        }

    def update_run(self, appliance_key: str, watts: float) -> None:
        """Add a power sample to an in-progress run."""
        active = self._active_runs.get(appliance_key)
        if active:
            active["samples_w"].append(watts)

    async def end_run(self, appliance_key: str) -> None:
        """Finish a run and persist it."""
        active = self._active_runs.pop(appliance_key, None)
        if not active or not active["samples_w"]:
            return

        start_time = active["start"]
        end_time = datetime.now().isoformat()
        samples = active["samples_w"]
        avg_watts = sum(samples) / len(samples)
        # Each sample is ~30s apart (coordinator update interval)
        duration_hours = (len(samples) * 30) / 3600
        energy_kwh = round(avg_watts * duration_hours / 1000, 3)

        run_entry = {
            "start": start_time,
            "end": end_time,
            "avg_watts": round(avg_watts, 1),
            "energy_kwh": energy_kwh,
            "duration_min": round(len(samples) * 30 / 60, 1),
        }

        if appliance_key not in self._data:
            self._data[appliance_key] = {"runs": [], "last_run": None}

        history = self._data[appliance_key]
        history["last_run"] = run_entry
        history["runs"].append(run_entry)
        # Keep only recent runs
        history["runs"] = history["runs"][-MAX_RUNS_PER_APPLIANCE:]

        await self.async_save()

    def is_active(self, appliance_key: str) -> bool:
        return appliance_key in self._active_runs

    def get_last_run(self, appliance_key: str) -> dict | None:
        history = self._data.get(appliance_key, {})
        return history.get("last_run")

    def get_avg_consumption_kwh(self, appliance_key: str) -> float | None:
        history = self._data.get(appliance_key, {})
        runs = history.get("runs", [])
        if not runs:
            return None
        total = sum(r.get("energy_kwh", 0) for r in runs)
        return round(total / len(runs), 3)

    async def async_remove(self) -> None:
        await self._store.async_remove()
