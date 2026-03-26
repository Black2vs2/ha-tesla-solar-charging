"""Sensor entities for the appliance advisor."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .models import Status


class AdvisorApplianceSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry, appliance_key: str, appliance_name: str) -> None:
        super().__init__(coordinator)
        self._appliance_key = appliance_key
        self._attr_name = f"Advisor {appliance_name}"
        self._attr_unique_id = f"{entry.entry_id}_advisor_{appliance_key}"
        self._attr_icon = "mdi:lightbulb-on"

    @property
    def native_value(self) -> str | None:
        recs = self.coordinator.advisor_recommendations or {}
        rec = recs.get(self._appliance_key)
        return rec.status.value if rec else None

    @property
    def extra_state_attributes(self) -> dict:
        recs = self.coordinator.advisor_recommendations or {}
        rec = recs.get(self._appliance_key)
        if not rec:
            return {}
        return {
            "appliance_name": rec.appliance_name,
            "appliance_icon": rec.appliance_icon,
            "cost_label": rec.cost_label,
            "reason": rec.reason,
            "running": rec.running,
            "current_watts": rec.current_watts,
            "deadline_message": rec.deadline_message,
            "latest_start_time": rec.latest_start_time,
            "last_run_end": rec.last_run_end,
            "last_run_kwh": rec.last_run_kwh,
            "last_run_duration_min": rec.last_run_duration_min,
            "avg_consumption_kwh": rec.avg_consumption_kwh,
        }


class AdvisorSummarySensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Appliance Advisor Summary"
    _attr_icon = "mdi:home-lightning-bolt"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_advisor_summary"

    @property
    def native_value(self) -> str | None:
        recs = self.coordinator.advisor_recommendations
        if not recs:
            return None
        green = sum(1 for r in recs.values() if r.status == Status.GREEN)
        return f"{green} di {len(recs)} gratis"

    @property
    def extra_state_attributes(self) -> dict:
        recs = self.coordinator.advisor_recommendations
        if not recs:
            return {}
        return {
            "appliances": [
                {
                    "key": r.appliance_key,
                    "name": r.appliance_name,
                    "icon": r.appliance_icon,
                    "status": r.status.value,
                    "cost_label": r.cost_label,
                    "reason": r.reason,
                    "running": r.running,
                    "current_watts": r.current_watts,
                    "deadline_message": r.deadline_message,
                    "latest_start_time": r.latest_start_time,
                    "last_run_end": r.last_run_end,
                    "last_run_kwh": r.last_run_kwh,
                    "last_run_duration_min": r.last_run_duration_min,
                    "avg_consumption_kwh": r.avg_consumption_kwh,
                }
                for r in recs.values()
            ]
        }


async def async_setup_advisor_sensors(
    hass: HomeAssistant, entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback, coordinator,
) -> None:
    appliances_cfg = entry.options.get("appliances", {})
    entities: list[SensorEntity] = [AdvisorSummarySensor(coordinator, entry)]
    for key, cfg in appliances_cfg.items():
        entities.append(AdvisorApplianceSensor(coordinator, entry, key, cfg.get("name", key)))
    async_add_entities(entities)
