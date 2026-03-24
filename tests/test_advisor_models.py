"""Tests for appliance_advisor models — pure dataclasses."""

from tesla_solar_charging.appliance_advisor.models import (
    EnergyState, ApplianceConfig, DeadlineConfig, Recommendation, Status,
)


class TestEnergyState:
    def test_create_with_all_fields(self):
        state = EnergyState(solar_w=4200.0, grid_export_w=2000.0, battery_soc=85.0,
                            battery_power_w=500.0, tesla_charging_w=0.0)
        assert state.grid_export_w == 2000.0

    def test_solar_w_defaults_to_none(self):
        state = EnergyState(grid_export_w=2000.0, battery_soc=85.0,
                            battery_power_w=500.0, tesla_charging_w=0.0)
        assert state.solar_w is None


class TestApplianceConfig:
    def test_create_with_defaults(self):
        cfg = ApplianceConfig(key="dw_1", name="Lavastoviglie", icon="X", watts=2000)
        assert cfg.duration_minutes == 0
        assert cfg.power_entity is None
        assert cfg.running_threshold_w == 30.0

    def test_create_with_power_entity(self):
        cfg = ApplianceConfig(key="dw_1", name="Lavastoviglie", icon="X", watts=2000,
                              power_entity="sensor.plug_dw", running_threshold_w=50.0)
        assert cfg.power_entity == "sensor.plug_dw"


class TestRecommendation:
    def test_create_green(self):
        rec = Recommendation(appliance_key="dw_1", status=Status.GREEN,
                             cost_label="Gratis", reason="OK", appliance_name="Test", appliance_icon="X")
        assert rec.status == Status.GREEN
        assert rec.running is None
