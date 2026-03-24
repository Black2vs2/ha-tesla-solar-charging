"""Integration test for the full advisor evaluation flow."""
from unittest.mock import MagicMock
from tesla_solar_charging.appliance_advisor import build_energy_state, build_appliance_list, evaluate_all
from tesla_solar_charging.appliance_advisor.models import Status


class TestBuildEnergyState:
    def test_computes_tesla_watts(self):
        s = build_energy_state(grid_power=-2000, grid_voltage=230, battery_soc=85,
                               battery_power=0, current_amps=10)
        assert s.tesla_charging_w == 2300.0
        assert s.grid_export_w == 2000.0

    def test_zero_amps_zero_tesla(self):
        s = build_energy_state(grid_power=-2000, grid_voltage=230, battery_soc=85,
                               battery_power=0, current_amps=0)
        assert s.tesla_charging_w == 0.0

    def test_import_zero_export(self):
        s = build_energy_state(grid_power=500, grid_voltage=230, battery_soc=85,
                               battery_power=0, current_amps=0)
        assert s.grid_export_w == 0.0


class TestBuildApplianceList:
    def test_empty_options(self):
        assert build_appliance_list({}) == []

    def test_reads_from_options(self):
        opts = {"appliances": {
            "dw_1": {"name": "Lavastoviglie", "icon": "X", "watts": 1800, "duration": 120},
        }}
        apps = build_appliance_list(opts)
        assert len(apps) == 1
        assert apps[0].watts == 1800

    def test_multiple_of_same_type(self):
        opts = {"appliances": {
            "dw_su": {"name": "Lavastoviglie Su", "icon": "X", "watts": 2000},
            "dw_giu": {"name": "Lavastoviglie Giu", "icon": "X", "watts": 2000},
        }}
        apps = build_appliance_list(opts)
        assert len(apps) == 2


class TestEvaluateAll:
    def _hass(self):
        hass = MagicMock()
        hass.states.get.return_value = None
        return hass

    def test_high_export_green(self):
        opts = {"appliances": {"ac": {"name": "AC", "icon": "X", "watts": 1000}}}
        result = evaluate_all(self._hass(), opts, grid_power=-6000, grid_voltage=230,
                              battery_soc=100, battery_power=0, current_amps=0)
        assert result["ac"].status == Status.GREEN

    def test_no_export_red(self):
        opts = {"appliances": {"ac": {"name": "AC", "icon": "X", "watts": 1000}}}
        result = evaluate_all(self._hass(), opts, grid_power=0, grid_voltage=230,
                              battery_soc=50, battery_power=0, current_amps=0)
        assert result["ac"].status == Status.RED

    def test_octopus_upgrades(self):
        opts = {"appliances": {"ac": {"name": "AC", "icon": "X", "watts": 1000}}}
        result = evaluate_all(self._hass(), opts, grid_power=0, grid_voltage=230,
                              battery_soc=50, battery_power=0, current_amps=0,
                              is_octopus_dispatching=True)
        assert result["ac"].status == Status.YELLOW

    def test_deadlines_applied(self):
        opts = {"appliances": {"dw": {"name": "DW", "icon": "X", "watts": 2000, "duration": 120}}}
        deadlines = {"dw": {"type": "finish_by", "time": "19:30"}}
        result = evaluate_all(self._hass(), opts, grid_power=-5000, grid_voltage=230,
                              battery_soc=100, battery_power=0, current_amps=0,
                              deadline_data=deadlines)
        assert result["dw"].latest_start_time == "17:30"

    def test_empty_appliances_returns_empty(self):
        result = evaluate_all(self._hass(), {}, grid_power=-5000, grid_voltage=230,
                              battery_soc=100, battery_power=0, current_amps=0)
        assert result == {}
