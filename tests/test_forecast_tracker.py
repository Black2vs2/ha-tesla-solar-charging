"""Tests for forecast_tracker.py — test the pure logic without HA storage."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from tesla_solar_charging.forecast_tracker import ForecastTracker


@pytest.fixture
def tracker():
    """Create a ForecastTracker with mocked HA dependencies."""
    hass = MagicMock()
    t = ForecastTracker.__new__(ForecastTracker)
    t._hass = hass
    t._store = MagicMock()
    t._store.async_save = AsyncMock()
    t._history = {}
    return t


class TestCorrectionFactor:
    def test_default_when_no_data(self, tracker):
        assert tracker.correction_factor == 1.0

    def test_default_when_insufficient_data(self, tracker):
        # Only 3 days, need 7
        for i in range(3):
            tracker._history[f"2026-03-{i+10:02d}"] = {
                "forecast_production_kwh": 10,
                "actual_production_kwh": 8,
            }
        assert tracker.correction_factor == 1.0

    def test_correction_with_enough_data(self, tracker):
        # 10 days where actual is 80% of forecast
        for i in range(10):
            tracker._history[f"2026-03-{i+10:02d}"] = {
                "forecast_production_kwh": 10.0,
                "actual_production_kwh": 8.0,
            }
        assert tracker.correction_factor == 0.8

    def test_correction_varies(self, tracker):
        # Mix of over and under predictions
        for i in range(7):
            tracker._history[f"2026-03-{i+10:02d}"] = {
                "forecast_production_kwh": 10.0,
                "actual_production_kwh": 10.0 + (i - 3),  # 7,8,9,10,11,12,13
            }
        factor = tracker.correction_factor
        assert 0.9 < factor < 1.1  # roughly centered


class TestRecordForecast:
    def test_records_new_forecast(self, tracker):
        tracker.record_forecast("2026-03-22", 4.2, 15.1, 9.2, 0.60)
        assert "2026-03-22" in tracker._history
        assert tracker._history["2026-03-22"]["forecast_production_kwh"] == 15.1

    def test_updates_existing_entry(self, tracker):
        tracker._history["2026-03-22"] = {"actual_production_kwh": 13.0}
        tracker.record_forecast("2026-03-22", 4.2, 15.1, 9.2, 0.60)
        assert tracker._history["2026-03-22"]["actual_production_kwh"] == 13.0
        assert tracker._history["2026-03-22"]["forecast_production_kwh"] == 15.1


class TestRecordActual:
    @pytest.mark.asyncio
    async def test_records_actual_and_saves(self, tracker):
        tracker._history["2026-03-22"] = {"forecast_production_kwh": 15.0}
        await tracker.record_actual("2026-03-22", 13.8)
        assert tracker._history["2026-03-22"]["actual_production_kwh"] == 13.8
        tracker._store.async_save.assert_called_once()


class TestStats:
    def test_empty_stats(self, tracker):
        stats = tracker.stats
        assert stats["days_tracked"] == 0
        assert stats["last_7_days"] == []

    def test_populated_stats(self, tracker):
        # Use dates within the last 30 days from "today" to avoid cutoff issues
        from datetime import datetime, timedelta
        base = datetime.now()
        for i in range(10):
            date = (base - timedelta(days=i)).strftime("%Y-%m-%d")
            tracker._history[date] = {
                "forecast_production_kwh": 15.0,
                "actual_production_kwh": 12.0,
            }
        stats = tracker.stats
        assert stats["days_tracked"] == 10
        assert stats["avg_forecast_kwh"] == 15.0
        assert stats["avg_actual_kwh"] == 12.0
        # 7-day window includes today + 7 days back = up to 8 entries
        assert len(stats["last_7_days"]) <= 8


class TestSeedHistory:
    def test_seeds_when_no_complete_days(self, tracker):
        tracker._seed_initial_history()
        assert len(tracker._history) == 8
        assert tracker._history["2026-03-19"]["forecast_production_kwh"] == 34.0
        assert tracker._history["2026-03-19"]["actual_production_kwh"] == 36.1
        # Should have enough data for a real correction factor
        assert tracker.correction_factor != 1.0
        assert 0.9 < tracker.correction_factor < 1.0

    def test_does_not_overwrite_existing_data(self, tracker):
        tracker._history["2026-03-19"] = {
            "forecast_production_kwh": 99.0,
            "actual_production_kwh": 99.0,
        }
        tracker._seed_initial_history()
        # Existing entry preserved
        assert tracker._history["2026-03-19"]["actual_production_kwh"] == 99.0
        # Other seed entries still added
        assert "2026-03-16" in tracker._history


class TestCorrectionFactorEdgeCases:
    def test_tiny_forecast_does_not_explode_ratio(self, tracker):
        """A near-zero forecast with real actual should not make factor 1000x."""
        from datetime import datetime, timedelta
        base = datetime.now()
        for i in range(10):
            date = (base - timedelta(days=i)).strftime("%Y-%m-%d")
            tracker._history[date] = {
                "forecast_production_kwh": 0.01,
                "actual_production_kwh": 10.0,
            }
        factor = tracker.correction_factor
        assert factor <= 2.0  # Capped, not 1000


class TestCleanup:
    def test_removes_old_entries(self, tracker):
        tracker._history["2020-01-01"] = {"forecast_production_kwh": 10}
        tracker._history["2026-03-22"] = {"forecast_production_kwh": 15}
        tracker.cleanup_old_data(keep_days=90)
        assert "2020-01-01" not in tracker._history
        assert "2026-03-22" in tracker._history


class TestWeatherPatternCorrection:
    def test_cloudy_days_get_separate_factor(self, tracker):
        from datetime import datetime, timedelta
        base = datetime.now()
        for i in range(10):
            date = (base - timedelta(days=i)).strftime("%Y-%m-%d")
            if i < 5:
                tracker._history[date] = {
                    "forecast_production_kwh": 20.0, "actual_production_kwh": 19.0,
                    "cloud_category": "clear",
                }
            else:
                tracker._history[date] = {
                    "forecast_production_kwh": 10.0, "actual_production_kwh": 6.0,
                    "cloud_category": "overcast",
                }
        clear_factor = tracker.correction_factor_for_weather("clear")
        overcast_factor = tracker.correction_factor_for_weather("overcast")
        assert clear_factor > overcast_factor
