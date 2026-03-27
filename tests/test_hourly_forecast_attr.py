"""Test that hourly forecast data is exposed on the forecast sensor."""
from custom_components.tesla_solar_charging.weather_forecast import (
    HourlyEntry,
    DailyHourlyForecast,
)


def test_hourly_forecast_to_attr():
    """DailyHourlyForecast.to_hourly_attr() returns list of dicts for sensor."""
    hours = [
        HourlyEntry(hour=h, radiation_w_m2=h * 100, cloud_cover=20.0,
                     cloud_cover_low=10.0, cloud_cover_mid=5.0, cloud_cover_high=5.0)
        for h in range(6, 21)
    ]
    dhf = DailyHourlyForecast(date="2026-03-28", hours=hours)
    result = dhf.to_hourly_attr()

    assert isinstance(result, list)
    assert len(result) == 15
    assert result[0] == {"hour": "06:00", "radiation_w_m2": 600, "cloud_cover": 20.0}
    assert result[-1] == {"hour": "20:00", "radiation_w_m2": 2000, "cloud_cover": 20.0}


def test_hourly_forecast_to_attr_empty():
    """Empty hours returns empty list."""
    dhf = DailyHourlyForecast(date="2026-03-28", hours=[])
    assert dhf.to_hourly_attr() == []
