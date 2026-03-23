"""Tests for charging_logic.py — pure functions, no HA dependency."""

from tesla_solar_charging.charging_logic import (
    Action,
    Config,
    SensorState,
    calculate_net_available,
    decide,
    decide_night_amps,
)


class TestCalculateNetAvailable:
    def test_exporting_with_no_battery_discharge(self):
        result = calculate_net_available(
            grid_power=-2300, grid_voltage=230, battery_power=0, safety_buffer=3
        )
        assert result == 7.0

    def test_importing_returns_zero_export(self):
        result = calculate_net_available(
            grid_power=500, grid_voltage=230, battery_power=0, safety_buffer=3
        )
        assert result == -3.0

    def test_battery_discharging_reduces_available(self):
        result = calculate_net_available(
            grid_power=-2300, grid_voltage=230, battery_power=460, safety_buffer=3
        )
        assert result == 5.0

    def test_zero_voltage_returns_zero(self):
        result = calculate_net_available(
            grid_power=-2300, grid_voltage=0, battery_power=0, safety_buffer=3
        )
        assert result == 0.0


class TestDecideSolar:
    def _make_state(self, **overrides):
        defaults = dict(
            grid_power=-2000, grid_voltage=230, battery_soc=100,
            battery_power=0, is_charging=False, current_amps=5,
            low_amp_count=0, tesla_battery=None, tesla_charge_limit=None,
        )
        defaults.update(overrides)
        return SensorState(**defaults)

    def _make_config(self, **overrides):
        defaults = dict(
            min_export_power=1200, max_charging_amps=16,
            safety_buffer_amps=3, battery_soc_threshold=80, low_amp_stop_count=3,
        )
        defaults.update(overrides)
        return Config(**defaults)

    # --- Start conditions ---

    def test_start_when_exporting_and_battery_healthy(self):
        state = self._make_state(grid_power=-1500, battery_soc=85)
        decision = decide(state, self._make_config())
        assert decision.action == Action.START

    def test_start_at_available_amps_not_minimum(self):
        # Exporting 3000W = 13A, minus 3 buffer = 10A
        state = self._make_state(grid_power=-3000, battery_soc=90)
        decision = decide(state, self._make_config())
        assert decision.action == Action.START
        assert decision.target_amps == 10

    def test_no_start_battery_too_low(self):
        # Battery at 50%, threshold 80% — let battery fill first
        state = self._make_state(grid_power=-1500, battery_soc=50)
        decision = decide(state, self._make_config())
        assert decision.action == Action.NONE
        assert "filling first" in decision.reason

    def test_no_start_not_exporting_enough(self):
        state = self._make_state(grid_power=-500, battery_soc=100)
        decision = decide(state, self._make_config())
        assert decision.action == Action.NONE

    def test_no_start_tesla_at_limit(self):
        state = self._make_state(
            grid_power=-1500, battery_soc=100, tesla_battery=80, tesla_charge_limit=80
        )
        decision = decide(state, self._make_config())
        assert decision.action == Action.NONE

    def test_stop_when_tesla_reaches_limit(self):
        state = self._make_state(
            is_charging=True, grid_power=-1500, battery_soc=100,
            tesla_battery=80, tesla_charge_limit=80
        )
        decision = decide(state, self._make_config())
        assert decision.action == Action.STOP

    # --- While charging: ramp up/down ---

    def test_ramp_up_fast_with_lots_of_excess(self):
        # Net available = 7A (>=4), should step +2
        state = self._make_state(
            is_charging=True, grid_power=-2300, current_amps=5, battery_soc=100
        )
        decision = decide(state, self._make_config())
        assert decision.action == Action.ADJUST
        assert decision.target_amps == 7

    def test_ramp_up_slow_with_moderate_excess(self):
        # Net available ~2.5A, should step +1
        state = self._make_state(
            is_charging=True, grid_power=-1300, current_amps=5, battery_soc=100
        )
        config = self._make_config(safety_buffer_amps=3)
        decision = decide(state, config)
        assert decision.action == Action.ADJUST
        assert decision.target_amps == 6

    def test_ramp_down_when_importing(self):
        state = self._make_state(
            is_charging=True, grid_power=500, current_amps=10, battery_soc=100
        )
        decision = decide(state, self._make_config())
        assert decision.action == Action.ADJUST
        assert decision.target_amps == 9

    def test_hold_when_stable(self):
        # Net available ~0A — stable
        state = self._make_state(
            is_charging=True, grid_power=-700, current_amps=5, battery_soc=100
        )
        config = self._make_config(safety_buffer_amps=3)
        decision = decide(state, config)
        assert decision.action == Action.NONE

    # --- Battery protection ---

    def test_reduce_fast_when_battery_discharging(self):
        # Battery discharging 500W while car charges — reduce aggressively
        state = self._make_state(
            is_charging=True, grid_power=-200, current_amps=8,
            battery_soc=90, battery_power=500
        )
        decision = decide(state, self._make_config())
        assert decision.action == Action.ADJUST
        assert decision.target_amps <= 6  # -2 step

    def test_stop_when_battery_discharging_at_minimum(self):
        # At minimum amps AND battery discharging for multiple checks
        state = self._make_state(
            is_charging=True, grid_power=100, current_amps=5,
            battery_soc=90, battery_power=500, low_amp_count=2
        )
        decision = decide(state, self._make_config())
        assert decision.action == Action.STOP

    # --- Graceful stop ---

    def test_stop_after_consecutive_low_counts(self):
        state = self._make_state(
            is_charging=True, grid_power=500, current_amps=5,
            battery_soc=100, low_amp_count=2
        )
        decision = decide(state, self._make_config())
        assert decision.action == Action.STOP

    # --- Force charge ---

    def test_force_bypasses_soc_threshold(self):
        # Battery at 50%, normally would wait — force overrides
        state = self._make_state(grid_power=-1500, battery_soc=50)
        decision = decide(state, self._make_config(), force=True)
        assert decision.action == Action.START

    def test_force_still_needs_export(self):
        # Force doesn't pull from grid — still needs export
        state = self._make_state(grid_power=-200, battery_soc=50)
        decision = decide(state, self._make_config(), force=True)
        assert decision.action == Action.NONE


class TestSensorBoundsChecking:
    def test_extreme_negative_grid_power_clamped(self):
        """Sensor glitch: -999999W should not produce insane amps."""
        result = calculate_net_available(
            grid_power=-999999, grid_voltage=230, battery_power=0, safety_buffer=3
        )
        assert result <= 50  # sanity bound

    def test_negative_voltage_returns_zero(self):
        """Negative voltage is a sensor error, not real."""
        result = calculate_net_available(
            grid_power=-2300, grid_voltage=-230, battery_power=0, safety_buffer=3
        )
        assert result == 0.0

    def test_negative_battery_power_does_not_inflate_available(self):
        """Sensor glitch: battery_power=-5000 (impossible) should not boost available amps."""
        result = calculate_net_available(
            grid_power=-2300, grid_voltage=230, battery_power=-5000, safety_buffer=3
        )
        assert result <= 10  # not inflated by negative battery glitch


class TestDecideNightAmps:
    def test_reduce_when_over_limit(self):
        decision = decide_night_amps(
            grid_power=3500, grid_voltage=230, current_amps=10,
            grid_power_limit=3000, max_charging_amps=16,
        )
        assert decision.action == Action.ADJUST
        assert decision.target_amps < 10

    def test_increase_when_headroom(self):
        decision = decide_night_amps(
            grid_power=2000, grid_voltage=230, current_amps=8,
            grid_power_limit=3000, max_charging_amps=16,
        )
        assert decision.action == Action.ADJUST
        assert decision.target_amps == 9

    def test_maintain_when_stable(self):
        decision = decide_night_amps(
            grid_power=2800, grid_voltage=230, current_amps=8,
            grid_power_limit=3000, max_charging_amps=16,
        )
        assert decision.action == Action.NONE

    def test_stop_when_way_over_limit(self):
        decision = decide_night_amps(
            grid_power=3500, grid_voltage=230, current_amps=5,
            grid_power_limit=3000, max_charging_amps=16,
        )
        assert decision.action == Action.STOP
