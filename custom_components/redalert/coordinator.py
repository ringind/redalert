"""Zentraler Poller: fragt /config der App ab und teilt es allen Entities.

/config liefert alles, was die vier Entities brauchen (running, presets,
current_preset) in einem Aufruf – ein separater /health-Poll ist nicht nötig.
"""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RedAlertApiClient, RedAlertApiError
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class RedAlertDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Hält den letzten /config-Stand der App vor."""

    def __init__(self, hass: HomeAssistant, client: RedAlertApiClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        try:
            return await self.client.async_get_config()
        except RedAlertApiError as exc:
            raise UpdateFailed(str(exc)) from exc
