"""Tests for weather_forecast.py — pure parsing logic."""

from tesla_solar_charging.weather_forecast import (
    parse_hourly_forecast,
    DailyHourlyForecast,
)


class TestParseHourlyForecast:
    def _make_api_response(self):
        """Minimal Open-Meteo hourly response for 2 days."""
        hours = []
        ghi = []
        cloud = []
        cloud_low = []
        cloud_mid = []
        cloud_high = []
        for day in range(2):
            for h in range(24):
                hours.append(f"2026-03-2{4+day}T{h:02d}:00")
                # Simulate: sun from 6-18, peak at noon
                if 6 <= h <= 18:
                    radiation = max(0, 800 - abs(h - 12) * 120)
                    c = 30 if day == 0 else 80  # day 0 partly cloudy, day 1 overcast
                else:
                    radiation = 0
                    c = 50
                ghi.append(radiation)
                cloud.append(c)
                cloud_low.append(c * 0.5)
                cloud_mid.append(c * 0.3)
                cloud_high.append(c * 0.2)
        return {
            "hourly": {
                "time": hours,
                "shortwave_radiation": ghi,
                "cloud_cover": cloud,
                "cloud_cover_low": cloud_low,
                "cloud_cover_mid": cloud_mid,
                "cloud_cover_high": cloud_high,
            }
        }

    def test_parses_into_daily_blocks(self):
        data = self._make_api_response()
        result = parse_hourly_forecast(data)
        assert "2026-03-24" in result
        assert "2026-03-25" in result

    def test_each_day_has_hourly_entries(self):
        data = self._make_api_response()
        result = parse_hourly_forecast(data)
        day = result["2026-03-24"]
        assert len(day.hours) == 24

    def test_best_window_identifies_peak(self):
        data = self._make_api_response()
        result = parse_hourly_forecast(data)
        day = result["2026-03-24"]
        assert day.best_window_start is not None
        assert 10 <= day.best_window_start <= 13

    def test_cloud_strategy_partly_cloudy(self):
        data = self._make_api_response()
        result = parse_hourly_forecast(data)
        day = result["2026-03-24"]  # 30% clouds
        assert day.cloud_strategy in ("clear", "partly_cloudy")

    def test_cloud_strategy_overcast(self):
        data = self._make_api_response()
        result = parse_hourly_forecast(data)
        day = result["2026-03-25"]  # 80% clouds
        assert day.cloud_strategy in ("overcast", "mostly_cloudy")

    def test_total_radiation_kwh(self):
        data = self._make_api_response()
        result = parse_hourly_forecast(data)
        day = result["2026-03-24"]
        assert day.total_radiation_kwh > 0
