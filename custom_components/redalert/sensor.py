"""Sensor: Name des aktuell geladenen Effektsets (None = Ad-hoc-Start / nichts geladen)."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import RedAlertDataUpdateCoordinator
from .entity import RedAlertEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: RedAlertDataUpdateCoordinator = entry.runtime_data
    async_add_entities([RedAlertCurrentPresetSensor(coordinator, entry)])


class RedAlertCurrentPresetSensor(RedAlertEntity, SensorEntity):
    """Spiegelt ``current_preset`` aus GET /config."""

    _attr_translation_key = "current_preset"
    _attr_icon = "mdi:star-four-points-outline"

    def __init__(self, coordinator: RedAlertDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "current_preset")

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.get("current_preset")
