"""Dataclasses for the appliance advisor module."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class Status(Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


@dataclass
class EnergyState:
    grid_export_w: float
    battery_soc: float
    battery_power_w: float
    tesla_charging_w: float
    solar_w: float | None = None


@dataclass
class ApplianceConfig:
    key: str
    name: str
    icon: str
    watts: int
    duration_minutes: int = 0
    power_entity: str | None = None
    running_threshold_w: float = 30.0


@dataclass
class DeadlineConfig:
    deadline_type: str = "none"
    time: str | None = None


@dataclass
class Recommendation:
    appliance_key: str
    status: Status
    cost_label: str
    reason: str
    appliance_name: str
    appliance_icon: str
    running: bool | None = None
    current_watts: float | None = None
    deadline_message: str | None = None
    latest_start_time: str | None = None
