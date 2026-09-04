"""Binary-Sensor: läuft der Effekt gerade (state["task"] aktiv)?"""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import RedAlertDataUpdateCoordinator
from .entity import RedAlertEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: RedAlertDataUpdateCoordinator = entry.runtime_data
    async_add_entities([RedAlertRunningSensor(coordinator, entry)])


class RedAlertRunningSensor(RedAlertEntity, BinarySensorEntity):
    """Spiegelt ``running`` aus GET /config (== /health)."""

    _attr_translation_key = "running"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: RedAlertDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "running")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("running"))
