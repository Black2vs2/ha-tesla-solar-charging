"""Tests for multi-source forecast blending."""
from tesla_solar_charging.forecast_blend import blend_forecasts, ForecastSource

class TestBlendForecasts:
    def test_single_source(self):
        sources = [ForecastSource(name="open_meteo", production_kwh=20.0, weight=1.0)]
        result = blend_forecasts(sources)
        assert result.blended_kwh == 20.0

    def test_two_sources_equal_weight(self):
        sources = [
            ForecastSource(name="open_meteo", production_kwh=20.0, weight=1.0),
            ForecastSource(name="solcast", production_kwh=16.0, weight=1.0),
        ]
        result = blend_forecasts(sources)
        assert result.blended_kwh == 18.0

    def test_weighted_blend(self):
        sources = [
            ForecastSource(name="open_meteo", production_kwh=20.0, weight=0.5),
            ForecastSource(name="solcast", production_kwh=16.0, weight=1.5),
        ]
        result = blend_forecasts(sources)
        assert result.blended_kwh == 17.0

    def test_pessimistic_uses_lowest(self):
        sources = [
            ForecastSource(name="open_meteo", production_kwh=20.0, weight=1.0),
            ForecastSource(name="solcast", production_kwh=16.0, weight=1.0, pessimistic_kwh=12.0),
        ]
        result = blend_forecasts(sources)
        assert result.pessimistic_kwh == 12.0

    def test_empty_sources(self):
        result = blend_forecasts([])
        assert result.blended_kwh == 0.0
