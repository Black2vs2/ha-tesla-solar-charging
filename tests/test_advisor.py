"""Tests for appliance_advisor.advisor — pure logic, no HA dependency."""

from tesla_solar_charging.appliance_advisor.models import (
    ApplianceConfig, DeadlineConfig, EnergyState, Recommendation, Status,
)
from tesla_solar_charging.appliance_advisor.advisor import (
    calculate_surplus, evaluate_appliance, evaluate,
)


def _energy(export=0.0, batt_soc=50.0, batt_power=0.0, tesla=0.0):
    return EnergyState(grid_export_w=export, battery_soc=batt_soc,
                       battery_power_w=batt_power, tesla_charging_w=tesla)


def _app(key="dw_1", watts=2000, name="Test", icon="X"):
    return ApplianceConfig(key=key, name=name, icon=icon, watts=watts)


class TestCalculateSurplus:
    def test_export_only(self):
        assert calculate_surplus(_energy(export=3000.0)) == 3000.0

    def test_subtracts_tesla(self):
        assert calculate_surplus(_energy(export=3000.0, tesla=1000.0)) == 2000.0

    def test_battery_near_full_adds_half_charge(self):
        assert calculate_surplus(_energy(export=1000.0, batt_soc=96.0, batt_power=1000.0)) == 1500.0

    def test_battery_not_near_full_ignores_charge(self):
        assert calculate_surplus(_energy(export=1000.0, batt_soc=80.0, batt_power=1000.0)) == 1000.0

    def test_battery_discharging_not_added(self):
        assert calculate_surplus(_energy(export=1000.0, batt_soc=96.0, batt_power=-500.0)) == 1000.0

    def test_negative_surplus_clamped_to_zero(self):
        assert calculate_surplus(_energy(export=0.0, tesla=1000.0)) == 0.0


class TestEvaluateAppliance:
    def test_green(self):
        rec = evaluate_appliance(_energy(), _app(watts=2000), surplus=2500.0)
        assert rec.status == Status.GREEN
        assert rec.cost_label == "Gratis"

    def test_yellow(self):
        rec = evaluate_appliance(_energy(), _app(watts=2000), surplus=1200.0)
        assert rec.status == Status.YELLOW

    def test_red(self):
        rec = evaluate_appliance(_energy(), _app(watts=2000), surplus=500.0)
        assert rec.status == Status.RED

    def test_green_threshold_boundary(self):
        assert evaluate_appliance(_energy(), _app(watts=2000), surplus=2199.0).status == Status.YELLOW
        assert evaluate_appliance(_energy(), _app(watts=2000), surplus=2200.0).status == Status.GREEN

    def test_octopus_upgrades_red(self):
        rec = evaluate_appliance(_energy(), _app(watts=2000), surplus=0.0, is_octopus_dispatching=True)
        assert rec.status == Status.YELLOW
        assert "Tariffa" in rec.reason

    def test_includes_name_and_icon(self):
        rec = evaluate_appliance(_energy(), _app(name="Forno", icon="F"), surplus=5000.0)
        assert rec.appliance_name == "Forno"
        assert rec.appliance_icon == "F"


class TestEvaluateAll:
    def test_returns_one_per_appliance(self):
        recs = evaluate(_energy(export=5000.0), [_app("a", 1000), _app("b", 2000)])
        assert len(recs) == 2
        assert recs[0].appliance_key == "a"

    def test_running_states_passed_through(self):
        recs = evaluate(_energy(export=5000.0), [_app("a", 1000)],
                        running_states={"a": (True, 950.0)})
        assert recs[0].running is True
        assert recs[0].current_watts == 950.0
