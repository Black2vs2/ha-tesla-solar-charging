"""Tests for planner.py — pure functions, no HA dependency."""

from tesla_solar_charging.planner import create_charge_plan


class TestCreateChargePlan:
    def _make_plan(self, **overrides):
        defaults = dict(
            tesla_soc=50,
            target_soc=80,
            tesla_battery_kwh=60,
            forecast_radiation_kwh_m2=4.0,
            sunshine_hours=8,
            pv_system_kwp=6.0,
            home_battery_kwh=10,
            home_battery_soc=50,
            avg_house_consumption_kwh=10,
            hours_until_deadline=48,
            safety_margin=1.0,
        )
        defaults.update(overrides)
        return create_charge_plan(**defaults)

    def test_already_at_target(self):
        plan = self._make_plan(tesla_soc=80, target_soc=80)
        assert plan.charge_tonight is False
        assert plan.kwh_needed == 0

    def test_urgent_deadline_charges_tonight(self):
        plan = self._make_plan(hours_until_deadline=12)
        assert plan.charge_tonight is True

    def test_good_solar_skips_night(self):
        # High radiation, low energy needed
        plan = self._make_plan(
            tesla_soc=70, target_soc=80,  # only 6 kWh needed
            forecast_radiation_kwh_m2=6.0,  # lots of sun
            home_battery_soc=90,  # battery nearly full
        )
        assert plan.charge_tonight is False

    def test_poor_solar_charges_tonight(self):
        # Low radiation, lots of energy needed
        plan = self._make_plan(
            tesla_soc=30, target_soc=80,  # 30 kWh needed
            forecast_radiation_kwh_m2=1.0,  # cloudy
            hours_until_deadline=24,
        )
        assert plan.charge_tonight is True

    def test_multi_day_deadline_with_partial_solar(self):
        # Enough days + partial solar covering >50% = skip tonight
        # production = 6.0 * 6.0 * 0.60 = 21.6 kWh
        # battery_needs = 10 * (100-90)/100 = 1.0 kWh
        # excess = 21.6 - 1.0 - 10 = 10.6 kWh (>50% of 12 kWh needed)
        plan = self._make_plan(
            tesla_soc=60, target_soc=80,  # 12 kWh needed
            forecast_radiation_kwh_m2=6.0,  # good sun
            home_battery_soc=90,  # battery nearly full
            hours_until_deadline=72,  # 3 days
        )
        assert plan.charge_tonight is False

    def test_safety_margin_makes_plan_charge_when_borderline(self):
        # excess ~12.4 kWh vs 12.0 kWh needed — without margin would skip night charge,
        # but 1.2x margin requires 14.4 kWh excess, so charges tonight
        plan = self._make_plan(
            tesla_soc=60, target_soc=80, forecast_radiation_kwh_m2=6.5,
            home_battery_soc=90, hours_until_deadline=30, safety_margin=1.2,
        )
        assert plan.charge_tonight is True
