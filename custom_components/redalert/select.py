"""Select: gespeichertes Effektset auswählen.

Die Auswahl ruft immer ``POST /select`` auf – genau wie „Laden" im Web-UI. Das
lädt das Set (merkt es als ``current_preset`` und übernimmt seine Bridge-
``area_id``s). Läuft gerade eine Animation bzw. ist eine Bridge scharf-
geschaltet, schaltet der Server den laufenden Effekt sofort ohne
Neustart/Handshake auf das neue Set um – vorausgesetzt, das Set hat pro
aktiver Bridge dieselbe ``area_id``. Andernfalls antwortet ``/select`` mit
einem Fehler (HTTP 409), der hier als ``HomeAssistantError`` sichtbar wird.
"""

from __future__ import annotations

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN, SelectEntity
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
    async_add_entities([RedAlertPresetSelect(coordinator, entry)])


class RedAlertPresetSelect(RedAlertEntity, SelectEntity):
    """Optionen = gespeicherte Effektsets (``presets`` aus GET /config)."""

    _attr_translation_key = "preset"
    _attr_icon = "mdi:star-four-points"

    def __init__(self, coordinator: RedAlertDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "preset", domain=SELECT_DOMAIN)

    @property
    def options(self) -> list[str]:
        return list(self.coordinator.data.get("presets") or [])

    @property
    def current_option(self) -> str | None:
        current = self.coordinator.data.get("current_preset")
        # Kein aktuelles Set, oder inzwischen gelöscht (z. B. im Web-UI) –
        # SelectEntity verlangt None statt eines Werts außerhalb von options.
        return current if current in self.options else None

    async def async_select_option(self, option: str) -> None:
        try:
            await self.coordinator.client.async_select_preset(option)
        except RedAlertApiError as exc:
            raise HomeAssistantError(
                f"Effektset '{option}' konnte nicht geladen werden: {exc}"
            ) from exc
        await self.coordinator.async_request_refresh()
