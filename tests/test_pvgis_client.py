"""Tests for PVGIS monthly baseline parsing."""
from tesla_solar_charging.pvgis_client import parse_pvgis_monthly

class TestParsePvgisMonthly:
    def _make_response(self):
        return {"outputs": {"monthly": {"fixed": [
            {"month": m, "H(h)_m": v, "SD_m": 0.3}
            for m, v in [(1,1.83),(2,2.75),(3,3.89),(4,4.67),(5,5.33),(6,5.78),(7,5.89),(8,5.22),(9,3.89),(10,2.78),(11,1.83),(12,1.50)]
        ]}}}
    def test_returns_12_months(self):
        assert len(parse_pvgis_monthly(self._make_response())) == 12
    def test_month_keys(self):
        r = parse_pvgis_monthly(self._make_response())
        assert 1 in r and 12 in r
    def test_values_are_radiation(self):
        r = parse_pvgis_monthly(self._make_response())
        assert r[7] > r[1]
