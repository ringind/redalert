"""Switch: Animation an/aus (POST /start bzw. /stop).

Turn-on startet erneut mit dem zuletzt geladenen Effektset
(``current_preset``, siehe select.py), falls eines geladen ist – sonst mit
den App-eigenen Standardwerten (leerer Body), genau wie ein Aufruf ohne
``preset`` im main.py-``/start``.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import RedAlertApiError
from .coordinator import RedAlertDataUpdateCoordinator
from .entity import RedAlertEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: RedAlertDataUpdateCoordinator = entry.runtime_data
    async_add_entities([RedAlertAnimationSwitch(coordinator, entry)])


class RedAlertAnimationSwitch(RedAlertEntity, SwitchEntity):
    """Spiegelt ``running`` und schaltet den Effekt per REST-API."""

    _attr_translation_key = "animation"
    _attr_icon = "mdi:alert-octagram"

    def __init__(self, coordinator: RedAlertDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "animation")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("running"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        preset = self.coordinator.data.get("current_preset")
        try:
            await self.coordinator.client.async_start(preset=preset)
        except RedAlertApiError as exc:
            raise HomeAssistantError(f"Red Alert konnte nicht gestartet werden: {exc}") from exc
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.client.async_stop()
        except RedAlertApiError as exc:
            raise HomeAssistantError(f"Red Alert konnte nicht gestoppt werden: {exc}") from exc
        await self.coordinator.async_request_refresh()
