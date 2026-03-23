"""Forecast accuracy tracker — compares predicted vs actual solar production."""

import logging
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    DEFAULT_CORRECTION_FACTOR,
    FORECAST_STORAGE_KEY,
    FORECAST_STORAGE_VERSION,
    MIN_DAYS_FOR_CORRECTION,
    ROLLING_WINDOW_DAYS,
)

_LOGGER = logging.getLogger(__name__)


class ForecastTracker:
    """Tracks daily forecast vs actual solar production."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._store = Store(hass, FORECAST_STORAGE_VERSION, FORECAST_STORAGE_KEY)
        self._history: dict[str, dict] = {}
        self._monthly_baselines: dict[int, float] | None = None

    async def async_load(self) -> None:
        """Load history from storage."""
        data = await self._store.async_load()
        if data and isinstance(data, dict):
            self._history = data
        else:
            self._history = {}

        # Seed with historical data if no complete days exist yet
        if not self._get_recent_complete_days():
            self._seed_initial_history()

        _LOGGER.debug("Loaded %d days of forecast history", len(self._history))

    def _seed_initial_history(self) -> None:
        """Seed tracker with historical forecast vs actual data from CSV analysis.

        Based on Open-Meteo forecasts vs Deye inverter actual production
        recorded 2026-03-16 to 2026-03-23.  Only entries that don't already
        exist are added so real data is never overwritten.
        """
        seed_data = {
            "2026-03-16": {"forecast_production_kwh": 42.1, "actual_production_kwh": 30.6},
            "2026-03-17": {"forecast_production_kwh": 36.9, "actual_production_kwh": 28.9},
            "2026-03-18": {"forecast_production_kwh": 18.5, "actual_production_kwh": 17.3},
            "2026-03-19": {"forecast_production_kwh": 34.0, "actual_production_kwh": 36.1},
            "2026-03-20": {"forecast_production_kwh": 34.3, "actual_production_kwh": 34.4},
            "2026-03-21": {"forecast_production_kwh": 21.6, "actual_production_kwh": 22.3},
            "2026-03-22": {"forecast_production_kwh": 26.7, "actual_production_kwh": 31.0},
            "2026-03-23": {"forecast_production_kwh": 35.2, "actual_production_kwh": 32.2},
        }
        added = 0
        for date_str, entry in seed_data.items():
            if date_str not in self._history:
                self._history[date_str] = entry
                added += 1
        if added:
            _LOGGER.info(
                "Seeded forecast tracker with %d historical days (correction factor: %.3f)",
                added,
                self.correction_factor,
            )

    async def async_save(self) -> None:
        """Persist history to storage."""
        await self._store.async_save(self._history)

    def record_forecast(
        self,
        date_str: str,
        radiation_kwh_m2: float,
        production_kwh: float,
        sunshine_hours: float,
        performance_ratio: float,
        cloud_category: str = "",
    ) -> None:
        """Record a forecast for a given date."""
        if date_str not in self._history:
            self._history[date_str] = {}
        entry: dict = {
            "forecast_radiation_kwh_m2": round(radiation_kwh_m2, 2),
            "forecast_production_kwh": round(production_kwh, 1),
            "sunshine_hours_forecast": round(sunshine_hours, 1),
            "performance_ratio_used": performance_ratio,
        }
        if cloud_category:
            entry["cloud_category"] = cloud_category
        self._history[date_str].update(entry)

    async def record_actual(self, date_str: str, actual_kwh: float) -> None:
        """Record actual production for a given date and persist."""
        if date_str not in self._history:
            self._history[date_str] = {}
        self._history[date_str]["actual_production_kwh"] = round(actual_kwh, 1)
        await self.async_save()
        _LOGGER.info(
            "Recorded actual production for %s: %.1f kWh (forecast was %.1f kWh)",
            date_str,
            actual_kwh,
            self._history[date_str].get("forecast_production_kwh", 0),
        )

    @property
    def correction_factor(self) -> float:
        """Calculate rolling correction factor from recent history."""
        recent = self._get_recent_complete_days()
        if len(recent) < MIN_DAYS_FOR_CORRECTION:
            return DEFAULT_CORRECTION_FACTOR

        ratios = []
        for day in recent:
            forecast = day.get("forecast_production_kwh", 0)
            actual = day.get("actual_production_kwh", 0)
            if forecast > 1.0:  # Skip days with negligible forecast
                ratio = actual / forecast
                ratios.append(max(0.3, min(ratio, 2.0)))  # Clamp to [0.3, 2.0]

        if not ratios:
            return DEFAULT_CORRECTION_FACTOR

        return round(sum(ratios) / len(ratios), 3)

    def set_monthly_baselines(self, baselines: dict[int, float]) -> None:
        """Store PVGIS monthly irradiance baselines for seasonal correction."""
        self._monthly_baselines = baselines

    @property
    def seasonal_correction_factor(self) -> float:
        """Calculate correction factor restricted to the current calendar month.

        Groups recent complete days by month, then returns the mean actual/forecast
        ratio for the current month if at least 3 days are available.  Falls back
        to the overall rolling correction_factor when insufficient data exist.
        """
        current_month = datetime.now().month
        recent = self._get_recent_complete_days()

        # Collect ratios only for days in the current month
        month_ratios = []
        for day in recent:
            date_str = day.get("date", "")
            try:
                day_month = int(date_str[5:7])
            except (ValueError, IndexError):
                continue
            if day_month != current_month:
                continue
            forecast = day.get("forecast_production_kwh", 0)
            actual = day.get("actual_production_kwh", 0)
            if forecast > 1.0:
                ratio = actual / forecast
                month_ratios.append(max(0.3, min(ratio, 2.0)))

        if len(month_ratios) >= 3:
            return round(sum(month_ratios) / len(month_ratios), 3)

        return self.correction_factor

    def correction_factor_for_weather(self, cloud_category: str) -> float:
        """Return a correction factor computed only from days matching cloud_category.

        Falls back to the overall correction_factor when fewer than 3 matching
        days are available in the recent history window.
        """
        recent = self._get_recent_complete_days()
        matching = [d for d in recent if d.get("cloud_category") == cloud_category]
        if len(matching) < 3:
            return self.correction_factor
        ratios = []
        for day in matching:
            forecast = day.get("forecast_production_kwh", 0)
            actual = day.get("actual_production_kwh", 0)
            if forecast > 1.0:
                ratios.append(max(0.3, min(actual / forecast, 2.0)))
        if not ratios:
            return self.correction_factor
        return round(sum(ratios) / len(ratios), 3)

    @property
    def days_tracked(self) -> int:
        """Number of days with complete data (both forecast and actual)."""
        return len(self._get_recent_complete_days())

    @property
    def stats(self) -> dict:
        """Summary statistics for sensor attributes."""
        recent = self._get_recent_complete_days()
        if not recent:
            return {
                "days_tracked": 0,
                "avg_forecast_kwh": 0,
                "avg_actual_kwh": 0,
                "correction_factor": DEFAULT_CORRECTION_FACTOR,
                "last_7_days": [],
            }

        forecasts = [d["forecast_production_kwh"] for d in recent]
        actuals = [d["actual_production_kwh"] for d in recent]

        last_7 = self._get_recent_complete_days(7)

        return {
            "days_tracked": len(recent),
            "avg_forecast_kwh": round(sum(forecasts) / len(forecasts), 1),
            "avg_actual_kwh": round(sum(actuals) / len(actuals), 1),
            "correction_factor": self.correction_factor,
            "last_7_days": [
                {
                    "date": d.get("date", ""),
                    "forecast": d["forecast_production_kwh"],
                    "actual": d["actual_production_kwh"],
                }
                for d in last_7
            ],
        }

    def _get_recent_complete_days(self, max_days: int = ROLLING_WINDOW_DAYS) -> list[dict]:
        """Get recent days that have both forecast and actual data."""
        cutoff = (datetime.now() - timedelta(days=max_days)).strftime("%Y-%m-%d")
        result = []
        for date_str in sorted(self._history.keys(), reverse=True):
            if date_str < cutoff:
                break
            day = self._history[date_str]
            if "forecast_production_kwh" in day and "actual_production_kwh" in day:
                day_with_date = {**day, "date": date_str}
                result.append(day_with_date)
        return result

    def cleanup_old_data(self, keep_days: int = 90) -> None:
        """Remove entries older than keep_days."""
        cutoff = (datetime.now() - timedelta(days=keep_days)).strftime("%Y-%m-%d")
        old_keys = [k for k in self._history if k < cutoff]
        for k in old_keys:
            del self._history[k]
        if old_keys:
            _LOGGER.debug("Cleaned up %d old forecast entries", len(old_keys))
