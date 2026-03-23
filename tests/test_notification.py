"""Tests for notification message formatting."""
from tesla_solar_charging.notification import (
    format_ble_alert,
    format_charge_stopped,
    format_charge_limit_reached,
    format_night_mode_change,
    format_daily_report,
)


class TestFormatBleAlert:
    def test_esp32_offline(self):
        msg = format_ble_alert("esp32_offline", "Entities unavailable: switch.charger")
        assert "ESP32" in msg or "offline" in msg

    def test_ble_error(self):
        msg = format_ble_alert("ble_error", "3 consecutive failures")
        assert "BLE" in msg or "error" in msg

    def test_esp32_offline_includes_detail(self):
        detail = "Entities unavailable: switch.charger"
        msg = format_ble_alert("esp32_offline", detail)
        assert detail in msg

    def test_ble_error_includes_detail(self):
        detail = "3 consecutive failures"
        msg = format_ble_alert("ble_error", detail)
        assert detail in msg


class TestFormatChargeStopped:
    def test_includes_reason(self):
        msg = format_charge_stopped("Grid price too high")
        assert "Grid price too high" in msg

    def test_indicates_stopped(self):
        msg = format_charge_stopped("manual override")
        assert "Stopped" in msg or "stopped" in msg or "Charging" in msg


class TestFormatChargeLimitReached:
    def test_includes_soc(self):
        msg = format_charge_limit_reached(tesla_soc=85, limit=80)
        assert "85" in msg

    def test_includes_limit(self):
        msg = format_charge_limit_reached(tesla_soc=85, limit=80)
        assert "80" in msg

    def test_indicates_limit_reached(self):
        msg = format_charge_limit_reached(tesla_soc=85, limit=80)
        assert "limit" in msg.lower() or "Limit" in msg


class TestFormatNightModeChange:
    def test_entering_night_mode(self):
        msg = format_night_mode_change(entering=True)
        assert "Night" in msg or "night" in msg

    def test_leaving_night_mode(self):
        msg = format_night_mode_change(entering=False)
        assert "Night" in msg or "night" in msg or "Ended" in msg or "resumed" in msg

    def test_entering_vs_leaving_differ(self):
        entering = format_night_mode_change(entering=True)
        leaving = format_night_mode_change(entering=False)
        assert entering != leaving


class TestFormatDailyReport:
    def test_includes_kwh(self):
        msg = format_daily_report(
            solar_kwh=12.5,
            grid_kwh=0,
            total_kwh=12.5,
            peak_amps=14,
            hours_charged=4.2,
            forecast_kwh=15.0,
            actual_production_kwh=13.8,
        )
        assert "12.5" in msg
        assert "kWh" in msg

    def test_includes_accuracy(self):
        msg = format_daily_report(
            solar_kwh=10.0,
            grid_kwh=2.0,
            total_kwh=12.0,
            peak_amps=16,
            hours_charged=3.5,
            forecast_kwh=20.0,
            actual_production_kwh=15.0,
        )
        # accuracy = 15 / 20 * 100 = 75%
        assert "75" in msg
        assert "%" in msg

    def test_includes_peak_amps(self):
        msg = format_daily_report(
            solar_kwh=5.0,
            grid_kwh=0.0,
            total_kwh=5.0,
            peak_amps=10,
            hours_charged=2.0,
            forecast_kwh=8.0,
            actual_production_kwh=7.0,
        )
        assert "10" in msg

    def test_zero_forecast_no_crash(self):
        msg = format_daily_report(
            solar_kwh=0.0,
            grid_kwh=0.0,
            total_kwh=0.0,
            peak_amps=0,
            hours_charged=0.0,
            forecast_kwh=0.0,
            actual_production_kwh=0.0,
        )
        assert "N/A" in msg
