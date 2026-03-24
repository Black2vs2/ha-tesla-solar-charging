"""Tests for deadline-aware advisor logic."""
from tesla_solar_charging.appliance_advisor.models import Recommendation, Status, DeadlineConfig
from tesla_solar_charging.appliance_advisor.advisor import apply_deadline, compute_latest_start


def _rec(status=Status.GREEN, cost_label="Gratis", reason="OK"):
    return Recommendation(appliance_key="dw_1", status=status, cost_label=cost_label,
                          reason=reason, appliance_name="Test", appliance_icon="X")


class TestComputeLatestStart:
    def test_finish_by_subtracts_duration(self):
        assert compute_latest_start(DeadlineConfig("finish_by", "19:30"), 120) == "17:30"

    def test_start_by_returns_time(self):
        assert compute_latest_start(DeadlineConfig("start_by", "15:00"), 120) == "15:00"

    def test_none_returns_none(self):
        assert compute_latest_start(DeadlineConfig("none"), 120) is None

    def test_finish_by_crossing_midnight(self):
        assert compute_latest_start(DeadlineConfig("finish_by", "01:00"), 120) == "23:00"


class TestApplyDeadline:
    def test_green_no_deadline(self):
        rec = _rec()
        apply_deadline(rec, DeadlineConfig("none"), 120, "14:00")
        assert rec.deadline_message is None
        assert "avvia ora" in rec.reason.lower()

    def test_yellow_approaching_shows_time(self):
        rec = _rec(Status.YELLOW, "Poco", "X")
        apply_deadline(rec, DeadlineConfig("finish_by", "19:30"), 120, "16:00")
        assert rec.latest_start_time == "17:30"
        assert "17:30" in rec.deadline_message

    def test_urgent_overrides(self):
        rec = _rec(Status.YELLOW, "Poco", "X")
        apply_deadline(rec, DeadlineConfig("finish_by", "18:00"), 120, "15:45")
        assert rec.deadline_message == "Avvia adesso!"

    def test_missed_deadline(self):
        rec = _rec(Status.YELLOW, "Poco", "X")
        apply_deadline(rec, DeadlineConfig("finish_by", "18:00"), 120, "16:30")
        assert rec.deadline_message == "Troppo tardi"

    def test_zero_duration_skips_deadline(self):
        rec = _rec()
        apply_deadline(rec, DeadlineConfig("finish_by", "19:00"), 0, "14:00")
        assert rec.deadline_message is None
