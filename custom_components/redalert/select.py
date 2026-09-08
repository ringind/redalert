"""Select: gespeichertes Effektset auswählen.

Die Auswahl **startet den Effekt nicht** – sie merkt das Set nur als *geladen*
(``POST /select`` → ``current_preset``), genau wie „Laden" im Web-UI. Ausnahme:
läuft gerade eine Animation, wird sofort mit dem neuen Set weitergefahren
(``POST /stop`` + ``POST /start {"preset": …}``), weil ein reines ``/start`` bei
bereits laufenden Bridges nur übersprungen würde.
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
        running = bool(self.coordinator.data.get("running"))
        try:
            if running:
                # Animation läuft – sofort mit dem neuen Set weiterfahren.
                await self.coordinator.client.async_stop()
                await self.coordinator.client.async_start(preset=option)
            else:
                # Nur laden/merken, nicht starten.
                await self.coordinator.client.async_select_preset(option)
        except RedAlertApiError as exc:
            raise HomeAssistantError(
                f"Effektset '{option}' konnte nicht geladen werden: {exc}"
            ) from exc
        await self.coordinator.async_request_refresh()
